import json
import requests


class AppError(RuntimeError):
    pass


def request(method, url, **kwargs):
    # 明确发送 UTF-8 JSON，避免平台把中文的 ASCII Unicode 转义当作字面文本。
    # 不对正文做 unicode_escape 解码，以免损坏代码片段。
    if 'json' in kwargs:
        payload = kwargs.pop('json')
        kwargs['data'] = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        headers = dict(kwargs.pop('headers', {}) or {})
        headers['Content-Type'] = 'application/json; charset=utf-8'
        kwargs['headers'] = headers
    try:
        response = requests.request(method, url, timeout=kwargs.pop('timeout', (10, 60)), **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        status = getattr(exc.response, 'status_code', None)
        raise AppError(f'网络请求失败（HTTP {status or "未知/超时"}）；请检查网络、密钥和额度。') from None


def json_request(method, url, **kwargs):
    try:
        data = request(method, url, **kwargs).json()
    except ValueError:
        raise AppError('接口未返回有效 JSON。') from None
    if not isinstance(data, dict):
        raise AppError('接口响应结构异常。')
    return data
