import unittest
from unittest.mock import patch
from crawler import parse_html, validate_url
from rendering import render
from network import AppError
from wechat import WeChatClient


class CoreTests(unittest.TestCase):
    def test_verification_not_article(self):
        with self.assertRaises(AppError):
            parse_html('<html>环境异常，请完成验证</html>')

    def test_ad_removal(self):
        result = parse_html('<h1 id="activity-name">标题</h1><div id="js_content">' + '正文内容' * 20 + '<script>bad()</script><div class="ad">广告</div></div>')
        self.assertNotIn('广告', result['text'])
        self.assertNotIn('bad()', result['text'])

    def test_url_validation(self):
        with self.assertRaises(AppError):
            validate_url('https://mp.weixin.qq.com.evil.example/article')

    def test_untrusted_markdown(self):
        _, html = render('# 标题\n\n![x](https://evil.example/x)\n<script>alert(1)</script>', [])
        self.assertNotIn('<script', html)
        self.assertNotIn('<img', html)

    def test_wechat_permission(self):
        with self.assertRaisesRegex(AppError, '权限'):
            WeChatClient.check({'errcode': 48001})

    @patch('wechat.json_request')
    def test_token_cache(self, mock):
        mock.return_value = {'access_token': 'test', 'expires_in': 7200}
        client = WeChatClient({'WECHAT_APP_ID': 'id', 'WECHAT_APP_SECRET': 'secret'})
        self.assertEqual(client.access_token(), 'test')
        self.assertEqual(client.access_token(), 'test')
        self.assertEqual(mock.call_count, 1)

class DraftTests(unittest.TestCase):
    @patch('wechat.json_request')
    @patch.object(WeChatClient, 'upload')
    @patch.object(WeChatClient, 'access_token', return_value='test-token')
    def test_draft_uses_uploaded_image_urls(self, token, upload, request):
        upload.side_effect = ['cover-media-id', 'https://mmbiz.qpic.cn/body.jpg']
        request.return_value = {'media_id': 'draft-id'}
        cfg = {'AUTHOR': '', 'WECHAT_APP_ID': 'id', 'WECHAT_APP_SECRET': 'secret'}
        photo = {'path': '/tmp/photo.jpg', 'photographer': 'Artist', 'page': 'https://pexels.com/photo/1'}
        result = WeChatClient(cfg).draft('# 标题\n\n正文', [photo], 'https://mp.weixin.qq.com/s/test', lambda _: None)
        self.assertEqual(result, 'draft-id')
        payload = request.call_args.kwargs['json']['articles'][0]
        self.assertEqual(payload['thumb_media_id'], 'cover-media-id')
        self.assertIn('https://mmbiz.qpic.cn/body.jpg', payload['content'])
        self.assertNotIn('file://', payload['content'])
        self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
