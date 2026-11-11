from html import escape
import markdown
import bleach
from bs4 import BeautifulSoup
from network import AppError
from structure import clean_html, image_marker
from formatting import compact_html


def split_markdown(text):
    lines = text.strip().splitlines()
    if not lines or not lines[0].startswith('# '):
        raise AppError('文章第一行必须是“# 标题”。')
    title = lines[0][2:].strip()
    if not title:
        raise AppError('标题不能为空。')
    body = '\n'.join(lines[1:]).strip()
    if not body:
        raise AppError('正文不能为空。')
    return title, body


def render(text, photos, urls=None):
    title, body = split_markdown(text)
    html = clean_html(markdown.markdown(body, extensions=['fenced_code', 'tables']))
    soup = BeautifulSoup(html, 'html.parser')
    styles = {'p': 'font-size:16px;line-height:1.8;margin:16px 0;',
              'h2': 'font-size:22px;margin-top:28px;', 'blockquote': 'color:#666;border-left:3px solid #aaa;padding-left:12px;'}
    for tag, style in styles.items():
        for node in soup.find_all(tag):
            if not node.has_attr('style'):
                node['style'] = style
    fragments = []
    for i, photo in enumerate(photos):
        from pathlib import Path
        src = urls[i] if urls is not None else Path(photo['path']).as_uri()
        fragment = f'<p><img src="{escape(src, quote=True)}" style="max-width:100%;" /></p>'
        if photo.get('source') == 'original':
            fragment += '<p style="font-size:12px;color:#777;">图片来源：参考文章</p>'
        elif photo.get('page'):
            fragment += (f'<p style="font-size:12px;color:#777;">Photo by {escape(photo["photographer"])} on '
                         f'<a href="{escape(photo["page"], quote=True)}">Pexels</a></p>')
        marker = image_marker(photo['source_url']) if photo.get('source_url') else None
        matches = list(soup.find_all(string=lambda value: value and marker and marker in value)) if marker else []
        if matches:
            for node in matches:
                parts = str(node).split(marker)
                replacements = []
                for j, part in enumerate(parts):
                    if j:
                        replacements.extend(list(BeautifulSoup(fragment, 'html.parser').contents))
                    replacements.append(part)
                node.replace_with(*replacements)
        else:
            fragments.append(fragment)
    import re
    for node in list(soup.find_all(string=re.compile(r'\[\[SOURCE_IMAGE:[0-9a-f]+\]\]'))):
        node.replace_with(re.sub(r'\[\[SOURCE_IMAGE:[0-9a-f]+\]\]', '[原文图片未下载，请补充配图]', str(node)))
    # 第一张作为开篇图，其他配图放在正文之后，避免破坏 Markdown 结构。
    content = (fragments[0] if fragments else '') + str(soup) + ''.join(fragments[1:])
    return title, compact_html(content)
