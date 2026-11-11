"""Markdown 编辑格式；代码和复杂表格用少量 HTML 保真。"""
import re
from bs4 import BeautifulSoup
from markdownify import markdownify


def compact_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.find_all(True):
        style = node.get('style', '')
        if style:
            declarations = []
            for part in style.split(';'):
                if ':' in part:
                    key, value = part.split(':', 1)
                    key, value = key.strip(), value.strip()
                    if value:
                        declarations.append(f'{key}:{value}')
            if declarations:
                node['style'] = ';'.join(dict.fromkeys(declarations))
            else:
                node.attrs.pop('style', None)
    # Collapse identical inherited styles rather than discard original typography.
    for node in soup.find_all(True):
        if node.get('style'):
            own = dict(part.split(':', 1) for part in node['style'].split(';'))
            parent = node.parent
            inherited = {}
            while getattr(parent, 'attrs', None) is not None:
                for part in parent.get('style', '').split(';'):
                    if ':' in part:
                        k, v = part.split(':', 1)
                        inherited.setdefault(k, v)
                parent = parent.parent
            inheritable = {'color', 'font-size', 'font-family', 'font-weight', 'font-style', 'line-height', 'text-align', 'white-space'}
            own = {k: v for k, v in own.items() if k not in inheritable or inherited.get(k) != v}
            if own:
                node['style'] = ';'.join(f'{k}:{v}' for k, v in own.items())
            else:
                node.attrs.pop('style', None)
    for span in list(soup.select('span')):
        if not span.attrs:
            span.unwrap()
    normalize_code_blocks(soup)
    for span in list(soup.select('span')):
        if not span.attrs:
            span.unwrap()
    return str(soup)


def to_markdown(html):
    soup = BeautifulSoup(compact_html(html), 'html.parser')
    protected = {}
    def protect(node, value):
        key = f'PRESERVEDBLOCK{len(protected):06d}TOKEN'
        protected[key] = value
        node.replace_with(key)
    # Keep styled blocks/merged tables as HTML: Markdown cannot encode these faithfully.
    # Protect outer styled blocks first to avoid nested token expansion issues.
    for node in list(soup.find_all(True)):
        if node.parent is None:
            continue
        if node.name in ('pre', 'table') or node.get('style'):
            if any(p.name in ('pre', 'table') or p.get('style') for p in node.parents if getattr(p, 'attrs', None) is not None):
                continue
            protect(node, '\n\n' + str(node) + '\n\n')
    # Protect image placeholders against Markdown escaping.
    for node in list(soup.find_all(string=re.compile(r'\[\[SOURCE_IMAGE:'))):
        protect(node, str(node))
    result = markdownify(str(soup), heading_style='ATX', bullets='-', wrap=False)
    for key, value in protected.items():
        result = result.replace(key, value)
    return result.strip()


def normalize_code_blocks(soup):
    """统一浅底深字，防止复制来的深色主题与新背景冲突；不改动文本节点。"""
    for pre in soup.select('pre'):
        pre['style'] = ('white-space:pre-wrap;font-family:Menlo,Consolas,monospace;'
                        'font-size:14px;line-height:1.6;color:#24292f;'
                        'background-color:#f4f5f7;padding:12px')
        for child in pre.find_all(True):
            kept = []
            for part in child.get('style', '').split(';'):
                if ':' not in part:
                    continue
                key, value = part.split(':', 1)
                if key.strip() not in {'color', 'background-color', 'font-family', 'font-size',
                                      'font-weight', 'line-height', 'padding', 'opacity'}:
                    kept.append(key.strip() + ':' + value.strip())
            if child.name == 'code':
                kept.extend(['color:#24292f', 'background-color:#f4f5f7',
                             'font-family:Menlo,Consolas,monospace', 'white-space:pre-wrap'])
            if kept:
                child['style'] = ';'.join(kept)
            else:
                child.attrs.pop('style', None)
