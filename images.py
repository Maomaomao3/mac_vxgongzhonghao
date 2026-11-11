from io import BytesIO
from urllib.parse import urlparse
from PIL import Image, ImageOps
from network import json_request, request, AppError


def compress_image(content):
    with Image.open(BytesIO(content)) as raw:
        img = ImageOps.exif_transpose(raw).convert('RGB')
        img.thumbnail((1600, 1600))
        for quality in (88, 75, 60, 45, 30):
            out = BytesIO()
            img.save(out, format='JPEG', quality=quality, optimize=True)
            if len(out.getvalue()) < 950000:
                return out.getvalue()
    raise AppError('图片压缩后仍过大。')


def search_images(cfg, query, directory):
    if not cfg['PEXELS_API_KEY']:
        raise AppError('请配置 PEXELS_API_KEY。')
    data = json_request('GET', 'https://api.pexels.com/v1/search',
        headers={'Authorization': cfg['PEXELS_API_KEY']},
        params={'query': query, 'per_page': 2, 'orientation': 'landscape'})
    photos = data.get('photos', [])
    if not photos:
        raise AppError('未找到配图，请调整文章或稍后再试。')
    results = []
    for i, photo in enumerate(photos):
        url = photo['src']['large']
        if urlparse(url).hostname != 'images.pexels.com':
            raise AppError('图库返回了非预期图片域名。')
        response = request('GET', url)
        if len(response.content) > 20000000:
            raise AppError('图片文件过大。')
        path = directory / f'image_{i + 1}.jpg'
        path.write_bytes(compress_image(response.content))
        results.append({'path': str(path), 'photographer': photo['photographer'], 'page': photo['url']})
    return results


def download_original_images(urls, article_url, directory, log=lambda msg: None):
    """保存原始字节及适合微信上传的 JPEG；失败图片跳过。"""
    results = []
    for url in dict.fromkeys(urls):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.qpic.cn'):
            continue
        try:
            with request('GET', url, headers={'Referer': article_url, 'User-Agent': 'Mozilla/5.0'},
                         stream=True, allow_redirects=False) as response:
                if response.is_redirect:
                    raise AppError('图片发生重定向')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 20000000:
                        raise AppError('原图超过 20 MB')
            with Image.open(BytesIO(content)) as img:
                if min(img.size) < 100:
                    continue  # 跳过小图标；二维码和广告仍需人工核对
                ext = (img.format or 'bin').lower()
            compressed = compress_image(bytes(content))
            number = len(results) + 1
            original = directory / f'original_{number}.{ext}'
            original.write_bytes(content)
            path = directory / f'original_{number}_upload.jpg'
            path.write_bytes(compressed)
            results.append({'path': str(path), 'original_path': str(original),
                'source': 'original', 'source_url': url, 'page': article_url, 'photographer': ''})
            log(f'原图已下载：{number}（GIF 上传时转换为静态图）')
        except (AppError, OSError, ValueError, Image.DecompressionBombError):
            log('一张原图无法读取，已跳过。')
    return results


def create_default_cover(path):
    """本地绘制固定几何封面，无图库/AI 请求，不插入正文。"""
    from PIL import ImageDraw
    image = Image.new('RGB', (900, 384))
    draw = ImageDraw.Draw(image)
    for y in range(384):
        draw.line((0, y, 900, y), fill=(18 + y // 16, 40 + y // 7, 76 + y // 5))
    draw.ellipse((600, -150, 1100, 350), outline=(90, 175, 200), width=3)
    draw.ellipse((650, -100, 1050, 300), outline=(90, 175, 200), width=2)
    for y in (160, 190, 220):
        draw.rounded_rectangle((90, y, 420 if y != 220 else 320, y + 8), radius=4, fill=(210, 231, 240))
    image.save(path, 'JPEG', quality=85)
    return path
