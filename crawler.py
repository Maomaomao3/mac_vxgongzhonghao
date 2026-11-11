from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from network import request, AppError
from structure import source_structure
from formatting import to_markdown


def validate_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname != 'mp.weixin.qq.com' or p.username or p.port:
        raise AppError('请输入 https://mp.weixin.qq.com/ 开头的文章链接。')
    return url


def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('#js_content')
    title = soup.select_one('#activity-name')
    if root is None:
        raise AppError('未取得正文，可能遇到验证页。请在浏览器阅读后，将正文粘贴到备用输入框。')
    # 只移除明确的脚本/广告节点，避免按关键词误删正文。
    for node in root.select('script, style, iframe, .ad, .advertisement, #js_sponsor_ad_area'):
        node.decompose()
    images = []
    for img in root.select('img'):
        src = img.get('data-src') or img.get('src') or ''
        src = urljoin('https://mp.weixin.qq.com/', src)
        parsed = urlparse(src)
        if parsed.scheme == 'https' and (parsed.hostname or '').endswith('.qpic.cn') and src not in images:
            images.append(src)
    text = root.get_text('\n', strip=True)
    if len(text) < 30:
        raise AppError('正文过短或未加载，请使用备用正文输入。')
    structured = source_structure(root, images)
    return {'title': title.get_text(' ', strip=True) if title else '参考文章', 'text': text, 'images': images, 'html': structured, 'markdown': to_markdown(structured)}


def fetch(url, manual=''):
    validate_url(url)
    if manual.strip():
        result = {'title': '用户提供的参考文章', 'text': manual.strip(), 'images': []}
    else:
        response = request('GET', url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        response.encoding = 'utf-8'
        result = parse_html(response.text)
    return result
