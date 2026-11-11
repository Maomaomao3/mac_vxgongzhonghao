import time
import re
import ipaddress
from pathlib import Path
from network import json_request, AppError
from rendering import render


class WeChatRejected(AppError):
    """微信已返回明确业务错误，与传输结果未知区分。"""
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class WeChatClient:
    BASE = 'https://api.weixin.qq.com/cgi-bin/'

    def __init__(self, cfg):
        self.cfg, self.token, self.expires = cfg, '', 0

    @staticmethod
    def check(data):
        code = data.get('errcode', 0)
        if code:
            if code == 40164:
                # 只提取经校验的 IP，不显示可能包含其他信息的整段响应。
                message = str(data.get('errmsg', ''))
                match = re.search(r'invalid ip\s+([^\s,;]+)', message, re.I)
                if match:
                    try:
                        address = ipaddress.ip_address(match.group(1).strip('[]'))
                    except ValueError:
                        pass
                    else:
                        raise AppError(f'微信 API 错误 40164：本次请求出口 IP 为 {address}。'
                                       '请将此 IP 加入公众号 API IP 白名单；切换 VPN 节点后可能变化。')
            hints = {45002: '微信拒绝创建：消息内容超过平台限制（包含正文 HTML 排版代码），不是网络超时。请精简排版或拆篇后再提交。', 40164: '请在公众号后台配置当前公网出口 IP 白名单。',
                48001: '公众号没有该接口权限，请检查账号接口权限。',
                40125: 'AppSecret 无效。', 40013: 'AppID 无效。',
                40001: 'access_token 无效，请稍后重试。', 42001: 'access_token 过期。'}
            raise WeChatRejected(code, f'微信 API 错误 {code}：' + hints.get(code, '请根据官方错误码检查配置或内容。'))
        return data

    def access_token(self):
        if self.token and time.monotonic() < self.expires:
            return self.token
        if not self.cfg['WECHAT_APP_ID'] or not self.cfg['WECHAT_APP_SECRET']:
            raise AppError('请配置 WECHAT_APP_ID 和 WECHAT_APP_SECRET。')
        data = self.check(json_request('POST', self.BASE + 'stable_token', json={
            'grant_type': 'client_credential', 'appid': self.cfg['WECHAT_APP_ID'],
            'secret': self.cfg['WECHAT_APP_SECRET'], 'force_refresh': False}))
        self.token = data['access_token']
        self.expires = time.monotonic() + max(0, int(data['expires_in']) - 120)
        return self.token

    def upload(self, path, cover=False):
        endpoint = 'material/add_material' if cover else 'media/uploadimg'
        params = {'access_token': self.access_token()}
        if cover:
            params['type'] = 'image'
        with Path(path).open('rb') as file:
            data = self.check(json_request('POST', self.BASE + endpoint, params=params,
                files={'media': (Path(path).name, file, 'image/jpeg')}))
        return data['media_id' if cover else 'url']

    def draft(self, text, photos, source_url, log, output_directory=None):
        render(text, photos)  # 仅检查稿件结构，大小由微信接口判定
        log('上传永久封面素材…')
        if photos:
            cover = self.upload(photos[0]['path'], cover=True)
        else:
            # 封面是接口素材，不计入正文配图，也不修改待审正文。
            from tempfile import TemporaryDirectory
            from images import create_default_cover
            log('正文无配图，自动生成默认封面，仅用于文章封面。')
            with TemporaryDirectory() as directory:
                path = create_default_cover(Path(directory) / 'cover.jpg')
                cover = self.upload(path, cover=True)
        urls = []
        for i, photo in enumerate(photos):
            log(f'上传正文配图 {i + 1}/{len(photos)}…')
            urls.append(self.upload(photo['path']))
        title, content = render(text, photos, urls)
        if output_directory is not None:
            (Path(output_directory) / 'submitted_content.html').write_text(content, encoding='utf-8')
        log('创建草稿（不会发布）…')
        try:
            data = self.check(json_request('POST', self.BASE + 'draft/add',
                params={'access_token': self.access_token()}, json={'articles': [{
                    'title': title, 'author': self.cfg['AUTHOR'], 'content': content,
                    'content_source_url': source_url, 'thumb_media_id': cover,
                    'need_open_comment': 0, 'only_fans_can_comment': 0}]}))
        except WeChatRejected:
            raise
        except AppError as exc:
            raise AppError(str(exc) + ' 若请求超时，草稿可能已创建；请先检查后台，避免重复提交。') from None
        if not data.get('media_id'):
            raise AppError('草稿响应缺少 media_id，请先检查后台，不要直接重试。')
        return data['media_id']

    def get_draft(self, media_id):
        return self.check(json_request('POST', self.BASE + 'draft/get',
            params={'access_token': self.access_token()}, json={'media_id': media_id}))

    def submit_publish(self, media_id):
        data = self.check(json_request('POST', self.BASE + 'freepublish/submit',
            params={'access_token': self.access_token()}, json={'media_id': media_id}))
        if not data.get('publish_id'):
            raise AppError('发表响应缺少 publish_id，提交结果未知。')
        return data['publish_id']

    def publish_status(self, publish_id):
        return self.check(json_request('POST', self.BASE + 'freepublish/get',
            params={'access_token': self.access_token()}, json={'publish_id': publish_id}))
