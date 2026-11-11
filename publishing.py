"""版本绑定、发表尝试持久化；不自动重试提交。"""
import hashlib
import json
import time
from pathlib import Path
from network import AppError


def fingerprint(text, photos, url):
    from rendering import render
    title, html = render(text, photos)
    payload = {'rendered_title': title, 'rendered_html': html, 'text': text, 'url': url, 'photos': [
        {**p, 'sha256': hashlib.sha256(Path(p['path']).read_bytes()).hexdigest()} for p in photos]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def remote_fingerprint(data):
    fields = ('title', 'author', 'digest', 'content', 'content_source_url', 'thumb_media_id',
              'need_open_comment', 'only_fans_can_comment')
    items = data.get('news_item')
    if not isinstance(items, list) or not items:
        raise AppError('无法读取微信草稿内容，不能发表。')
    return hashlib.sha256(json.dumps([{k: i.get(k) for k in fields} for i in items],
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def publish_reviewed(client, record, current_hash, directory, log):
    if current_hash != record['fingerprint']:
        raise AppError('文章或图片已修改，请重新同步新版本并审核。')
    if client.cfg['WECHAT_APP_ID'] != record['appid']:
        raise AppError('公众号 AppID 已改变，请重新同步草稿。')
    path = Path(directory) / ('publish_' + current_hash + '.json')
    if path.exists():
        state = json.loads(path.read_text())
        if not state.get('publish_id'):
            raise AppError('该版本已有发表尝试但结果未知，请到公众号后台核对，禁止重复提交。')
    else:
        remote = remote_fingerprint(client.get_draft(record['media_id']))
        if remote != record['remote_fingerprint']:
            raise AppError('后台草稿已被修改，请重新同步并审核。')
        state = {'status': 'submitting', 'approved_at': time.time(),
                 'fingerprint': current_hash, 'media_id': record['media_id'], 'appid': record['appid']}
        # 排他创建：同版本只能发起一次提交，即使进程崩溃也不盲目重试。
        with path.open('x') as file:
            json.dump(state, file)
        log('审核通过，正在提交发表…')
        try:
            state['publish_id'] = client.submit_publish(record['media_id'])
        except Exception:
            raise AppError('发表提交未确认，请先核对微信后台；未自动重试。') from None
        state['status'] = 'submitted'
        path.write_text(json.dumps(state))
    for attempt in range(12):
        data = client.publish_status(state['publish_id'])
        state['result'] = data
        state['status'] = 'published' if data.get('publish_status') == 0 else 'pending'
        path.write_text(json.dumps(state, ensure_ascii=False))
        status = data.get('publish_status')
        if status == 0:
            urls = [item.get('article_url', '') for item in data.get('article_detail', {}).get('item', [])]
            log('发表成功：' + ' '.join(urls))
            return state
        if status != 1:
            state['status'] = 'failed'
            path.write_text(json.dumps(state, ensure_ascii=False))
            raise AppError(f'微信发表未成功，状态码 {status}；请到后台查看原因。')
        log(f'微信正在处理发表任务（{attempt + 1}/12）…')
        if attempt < 11:
            time.sleep(5)
    log('仍在处理中，稍后点击查询发表结果；不会再次提交。')
    return state
