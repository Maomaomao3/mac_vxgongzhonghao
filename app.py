import sys
import json
import uuid
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QTextBrowser, QProgressBar,
    QLabel, QSplitter, QMessageBox, QFileDialog, QTabWidget)
from config import load_config, ensure_config, DATA_DIR, CONFIG_PATH
from crawler import fetch
from ai import AIClient
from images import search_images, compress_image, download_original_images
from rendering import render, split_markdown
from wechat import WeChatClient, WeChatRejected
from publishing import fingerprint, remote_fingerprint, publish_reviewed
from network import AppError


class Worker(QThread):
    progress = Signal(int, str)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    def run(self):
        try:
            self.result.emit(self.operation(self.progress.emit))
        except (AppError, ValueError) as exc:
            self.failed.emit(str(exc))
        except ModuleNotFoundError as exc:
            self.failed.emit(f'缺少依赖：{exc.name}；请使用运行程序的 Python 安装 requirements.txt。')
        except Exception as exc:
            self.failed.emit(f'操作失败（{type(exc).__name__}），请检查配置和输出目录权限。')


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('公众号 AI Studio')
        self.resize(1150, 850)
        self.job = None
        self.bundle = None
        self.source_cache = None
        self.synced = False
        self.draft_record = None
        self.root = QWidget()
        self.setCentralWidget(self.root)
        layout = QVBoxLayout(self.root)
        layout.addWidget(QLabel('输入参考文章 → AI 独立重构 → 审核编辑 → 同步草稿'))
        self.url = QLineEdit()
        self.url.setPlaceholderText('https://mp.weixin.qq.com/s/...')
        layout.addWidget(self.url)
        self.manual = QTextEdit()
        self.manual.setPlaceholderText('备用正文：遇到微信验证页时，在浏览器阅读后将正文粘贴到这里。')
        self.manual.setMaximumHeight(100)
        layout.addWidget(self.manual)
        row = QHBoxLayout()
        self.read_source = QPushButton('读取原文（不调用 AI）')
        self.generate = QPushButton('AI 润色（保留技术结构）')
        self.sync = QPushButton('一键同步至公众号草稿箱')
        self.sync.setEnabled(False)
        self.publish = QPushButton('审核通过并发表')
        self.publish.setEnabled(False)
        self.add_images = QPushButton('选择本地配图')
        self.add_images.setEnabled(False)
        settings = QPushButton('打开配置文件')
        folder = QPushButton('打开输出目录')
        for button in (self.read_source, self.generate, self.add_images, self.sync, self.publish, settings, folder):
            row.addWidget(button)
        layout.addLayout(row)
        self.bar = QProgressBar()
        layout.addWidget(self.bar)
        split = QSplitter()
        self.editor = QTextEdit()
        self.editor.setPlaceholderText('生成后在此编辑 Markdown；第一行使用 # 标题')
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        split.addWidget(self.editor)
        split.addWidget(self.preview)
        self.tabs = QTabWidget()
        self.original = QTextBrowser()
        self.original.setOpenExternalLinks(True)
        self.tabs.addTab(self.original, '原文展示 · 只读')
        self.tabs.addTab(split, 'AI 润色 · 编辑与预览')
        layout.addWidget(self.tabs, 1)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        layout.addWidget(self.log)
        credit = QLabel('Photos provided by <a href="https://www.pexels.com">Pexels</a> · AI 内容需核对事实后发布')
        credit.setOpenExternalLinks(True)
        layout.addWidget(credit)
        self.read_source.clicked.connect(self.start_read_source)
        self.tabs.currentChanged.connect(self.refresh_actions)
        self.generate.clicked.connect(self.start_generate)
        self.sync.clicked.connect(self.start_sync)
        self.publish.clicked.connect(self.start_publish)
        self.add_images.clicked.connect(self.select_images)
        self.editor.textChanged.connect(self.update_preview)
        settings.clicked.connect(self.open_settings)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR))))

    def open_settings(self):
        try:
            ensure_config()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_PATH)))
        except OSError:
            QMessageBox.warning(self, '配置错误', f'无法创建或打开配置文件：{CONFIG_PATH}')

    def progress(self, value, message):
        self.bar.setValue(value)
        self.log.append(message)

    def run_job(self, operation, callback):
        self.read_source.setEnabled(False)
        self.generate.setEnabled(False)
        self.add_images.setEnabled(False)
        self.sync.setEnabled(False)
        self.publish.setEnabled(False)
        self.editor.setReadOnly(True)
        self.job = Worker(operation)
        self.job.progress.connect(self.progress)
        self.job.result.connect(callback)
        self.job.failed.connect(lambda msg: self.progress(0, msg))
        self.job.finished.connect(self.finished)
        self.job.start()

    def finished(self):
        self.read_source.setEnabled(True)
        self.generate.setEnabled(True)
        self.add_images.setEnabled(self.bundle is not None and not self.synced)
        self.editor.setReadOnly(False)
        self.sync.setEnabled(self.bundle is not None and bool(self.bundle["photos"]) and not self.synced)
        self.publish.setEnabled(self.draft_record is not None and self.synced)
        self.job.deleteLater()
        self.job = None
        self.refresh_actions()

    def refresh_actions(self, *args):
        ready = self.job is None and self.bundle is not None
        self.sync.setEnabled(ready)
        self.publish.setEnabled(ready)
        self.add_images.setEnabled(ready)
        self.publish.setText('审核通过并发表')

    def current_article(self):
        if self.tabs.currentIndex() == 0:
            from html import escape
            source = self.bundle['source']
            body = source.get('markdown') or source.get('html') or '<pre>' + escape(source['text']) + '</pre>'
            return '# ' + source['title'] + '\n\n' + body, self.bundle.copy()
        return self.editor.toPlainText(), self.bundle.copy()

    def show_source(self, source, photos):
        from html import escape
        body = source.get('markdown') or source.get('html') or '<pre>' + escape(source['text']) + '</pre>'
        _, html = render('# ' + source['title'] + '\n\n' + body, photos)
        self.original.setHtml('<p><b>原文 · 未经 AI 改写</b></p><h1>' + escape(source['title']) + '</h1>' + html)

    def start_read_source(self):
        url, manual = self.url.text().strip(), self.manual.toPlainText()
        def operation(progress):
            progress(10, '读取原文结构，不调用 AI…')
            source = fetch(url, manual)
            directory = DATA_DIR / 'outputs' / uuid.uuid4().hex
            directory.mkdir(parents=True)
            (directory / 'source.json').write_text(json.dumps(source, ensure_ascii=False, indent=2))
            (directory / 'source.html').write_text(source.get('html', ''), encoding='utf-8')
            (directory / 'source.md').write_text('# ' + source['title'] + '\n\n' + source.get('markdown', source['text']), encoding='utf-8')
            photos = download_original_images(source.get('images', []), url, directory,
                log=lambda message: progress(60, message))
            progress(100, '原文已保存；请查看原文标签页，随后可选择 AI 改写。')
            return {'source': source, 'photos': photos, 'input': (url, manual), 'directory': str(directory)}
        self.run_job(operation, self.source_loaded)

    def source_loaded(self, result):
        self.bundle = {'source': result['source'], 'photos': result['photos'],
                       'url': result['input'][0], 'directory': result['directory']}
        self.draft_record = None
        self.synced = False
        from html import escape
        source = result['source']
        self.bundle['text'] = '# ' + source['title'] + '\n\n' + (source.get('markdown') or source.get('html') or '<pre>' + escape(source['text']) + '</pre>')
        self.editor.setPlainText(self.bundle['text'])
        self.preview.clear()
        self.source_cache = result
        self.show_source(result['source'], result['photos'])
        self.tabs.setCurrentIndex(0)
        self.refresh_actions()

    def start_generate(self):
        url, manual = self.url.text().strip(), self.manual.toPlainText()
        cached = self.source_cache if self.source_cache and self.source_cache['input'] == (url, manual) else None
        def operation(progress):
            cfg = load_config()
            progress(10, '读取参考文章…')
            source = cached['source'] if cached else fetch(url, manual)
            directory = DATA_DIR / 'outputs' / uuid.uuid4().hex
            directory.mkdir(parents=True)
            (directory / 'source.json').write_text(json.dumps(source, ensure_ascii=False, indent=2))
            (directory / 'source.html').write_text(source.get('html', ''), encoding='utf-8')
            (directory / 'source.md').write_text('# ' + source['title'] + '\n\n' + source.get('markdown', source['text']), encoding='utf-8')
            ai = AIClient(cfg)
            progress(25, 'AI 正在润色正文，完善讲解…')
            text = ai.rewrite(source, lambda message: progress(35, message))
            title, _ = split_markdown(text)
            (directory / 'article.md').write_text(text, encoding='utf-8')
            photos = []
            if cfg['IMAGE_SOURCE'] == 'none':
                progress(85, '配置为不自动配图，仍可手动选择本地封面。')
            elif cfg['IMAGE_SOURCE'] == 'original':
                progress(65, f'发现 {len(source.get("images", []))} 个原文图片链接，正在下载…')
                photos = download_original_images(source.get('images', []), url, directory, log=lambda msg: progress(75, msg))
                if not photos:
                    progress(85, '未取得可用原图；纯文本备用输入不含图片，可选择本地图片。')
            elif cfg.get('PEXELS_API_KEY', '').strip():
                progress(65, '提取图片关键词并匹配 Pexels 配图…')
                photos = search_images(cfg, ai.image_query(title), directory)
            else:
                progress(85, '未配置图库密钥，跳过自动配图；生成后可选择本地图片作为封面。')
            bundle = {'text': text, 'photos': photos, 'url': url, 'directory': str(directory), 'source': source}
            (directory / 'bundle.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
            progress(100, f'生成成功，已保存到 {directory}；请审核右侧预览。')
            return bundle
        self.run_job(operation, self.generated)

    def generated(self, bundle):
        self.bundle = bundle
        self.draft_record = None
        self.publish.setText("审核通过并发表")
        self.synced = False
        self.editor.setPlainText(bundle['text'])
        if bundle.get('source'):
            self.show_source(bundle['source'], bundle['photos'])
        self.tabs.setCurrentIndex(1)

    def update_preview(self):
        if self.draft_record and self.editor.toPlainText() != self.draft_record['text']:
            self.synced = False
            self.draft_record = None
            self.publish.setEnabled(False)
            self.publish.setText('审核通过并发表')
            self.add_images.setEnabled(True)
            self.sync.setEnabled(bool(self.bundle and self.bundle['photos']))
        if not self.bundle:
            return
        try:
            title, html = render(self.editor.toPlainText(), self.bundle['photos'])
            from html import escape
            self.preview.setHtml(f'<h1>{escape(title)}</h1>' + html)
        except AppError:
            self.preview.setPlainText('第一行需为 # 标题，正文不能为空。')

    def select_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '选择有权使用的图片（可多选），第一张作为封面', '', '图片 (*.jpg *.jpeg *.png *.webp)')
        if not paths:
            return
        try:
            photos = []
            directory = Path(self.bundle['directory'])
            for i, path in enumerate(paths):
                target = directory / f'local_{uuid.uuid4().hex}_{i}.jpg'
                target.write_bytes(compress_image(Path(path).read_bytes()))
                photos.append({'path': str(target), 'photographer': '', 'page': ''})
            self.bundle['photos'] = photos
            self.bundle['text'] = self.editor.toPlainText()
            (directory / 'bundle.json').write_text(json.dumps(self.bundle, ensure_ascii=False, indent=2))
            self.update_preview()
            self.show_source(self.bundle['source'], photos)
            self.refresh_actions()
            self.log.append('本地配图已载入，第一张用作封面。')
        except Exception:
            QMessageBox.warning(self, '配图失败', '图片读取或压缩失败，请检查文件格式和大小。')

    def prepare_draft(self, client, text, bundle, progress):
        render(text, bundle['photos'])
        directory = Path(bundle['directory'])
        version = fingerprint(text, bundle['photos'], bundle['url'])
        # 同一版本在不同公众号使用不同同步记录。
        import hashlib
        account = hashlib.sha256(client.cfg['WECHAT_APP_ID'].encode()).hexdigest()[:16]
        record_path = directory / ('review_' + account + '_' + version + '.json')
        if record_path.exists():
            progress(70, '已存在此版本草稿，复用已有记录。')
            return json.loads(record_path.read_text())
        marker = directory / ('sync_' + account + '_' + version + '.json')
        if marker.exists():
            state = json.loads(marker.read_text())
            if state.get('status') == 'rejected':
                marker.unlink()  # 明确拒绝允许手动重试；超时/未知仍保持阻止
            else:
                raise AppError('此版本旧尝试结果未知，请先核对后台草稿；明确失败的新尝试不会再锁住重试。')
        client.access_token()
        (directory / 'article.md').write_text(text, encoding='utf-8')
        with marker.open('x') as file:
            json.dump({'status': 'started'}, file)
        try:
            media_id = client.draft(text, bundle['photos'], bundle['url'], lambda msg: progress(65, msg), output_directory=directory)
        except WeChatRejected as exc:
            marker.write_text(json.dumps({'status': 'rejected', 'errcode': exc.code}))
            raise
        marker.write_text(json.dumps({'status': 'success', 'media_id': media_id}))
        record = {'media_id': media_id, 'fingerprint': version, 'appid': client.cfg['WECHAT_APP_ID'],
                  'remote_fingerprint': remote_fingerprint(client.get_draft(media_id)), 'text': text}
        record_path.write_text(json.dumps(record, ensure_ascii=False))
        return record

    def start_sync(self):
        text, bundle = self.current_article()
        def operation(progress):
            record = self.prepare_draft(WeChatClient(load_config()), text, bundle, progress)
            progress(100, '草稿已就绪：' + record['media_id'])
            return record
        self.run_job(operation, self.sync_done)

    def sync_done(self, record):
        self.draft_record = record
        self.synced = True

    def start_publish(self):
        # 本次点击即批准当前标签页对应的版本；后台自动衔接草稿。
        text, bundle = self.current_article()
        def operation(progress):
            client = WeChatClient(load_config())
            record = self.prepare_draft(client, text, bundle, progress)
            return publish_reviewed(client, record, fingerprint(text, bundle['photos'], bundle['url']),
                bundle['directory'], lambda msg: progress(85, msg))
        self.run_job(operation, self.publish_done)

    def publish_done(self, state):
        self.publish.setText('查询发表结果')
        if state['status'] == 'published':
            self.draft_record = None
            self.progress(100, '已确认发表成功，发表结果已保存到任务目录。')


    def closeEvent(self, event):
        if self.job is not None:
            QMessageBox.information(self, '任务执行中', '请等待当前请求结束后关闭窗口。')
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
