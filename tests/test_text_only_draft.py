import unittest
from unittest.mock import patch
from wechat import WeChatClient


class TextOnlyTests(unittest.TestCase):
    @patch('wechat.json_request', return_value={'media_id': 'draft-id'})
    @patch.object(WeChatClient, 'upload', return_value='cover-id')
    @patch.object(WeChatClient, 'access_token', return_value='token')
    def test_text_only_gets_cover_without_body_images(self, token, upload, request):
        client = WeChatClient({'AUTHOR': ''})
        photos = []
        self.assertEqual(client.draft('# 标题\n\n纯文字正文', photos,
                         'https://mp.weixin.qq.com/s/test', lambda _: None), 'draft-id')
        self.assertEqual(photos, [])
        upload.assert_called_once()
        self.assertTrue(upload.call_args.kwargs['cover'])
        article = request.call_args.kwargs['json']['articles'][0]
        self.assertEqual(article['thumb_media_id'], 'cover-id')
        self.assertNotIn('<img', article['content'])
        self.assertIn('纯文字正文', article['content'])
