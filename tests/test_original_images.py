import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import json
from crawler import parse_html
from config import load_config
from rendering import render


class OriginalTests(unittest.TestCase):
    def test_lazy_image_dedup(self):
        html = '<div id="js_content">' + '正文' * 30 + '<img data-src="https://mmbiz.qpic.cn/a" src="placeholder"><img data-src="https://mmbiz.qpic.cn/a"><img src="https://evil.example/a"></div>'
        self.assertEqual(parse_html(html)['images'], ['https://mmbiz.qpic.cn/a'])

    def test_legacy_count_is_ignored(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps({'IMAGE_COUNT': 0}))
            with patch('config.CONFIG_PATH', path):
                self.assertNotIn('IMAGE_COUNT', load_config())
                self.assertEqual(load_config()['IMAGE_SOURCE'], 'original')

    def test_original_not_credited_to_pexels(self):
        _, html = render('# 标题\n正文', [{'path': '/tmp/a.jpg', 'source': 'original', 'page': 'https://mp.weixin.qq.com/s/a'}])
        self.assertIn('参考文章', html)
        self.assertNotIn('Pexels', html)

    def test_downloads_more_than_three_images(self):
        from io import BytesIO
        from PIL import Image
        from images import download_original_images
        from unittest.mock import MagicMock
        image = BytesIO()
        Image.new('RGB', (200, 200)).save(image, format='PNG')
        response = MagicMock()
        response.__enter__.return_value = response
        response.is_redirect = False
        response.iter_content.side_effect = lambda size: iter([image.getvalue()])
        urls = [f'https://mmbiz.qpic.cn/{i}' for i in range(5)]
        with TemporaryDirectory() as folder, patch('images.request', return_value=response):
            photos = download_original_images(urls, 'https://mp.weixin.qq.com/s/test', Path(folder))
            self.assertEqual(len(photos), 5)
