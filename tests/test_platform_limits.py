import unittest
from unittest.mock import patch
from wechat import WeChatClient
from rendering import split_markdown


class PlatformLimitsTests(unittest.TestCase):
    @patch('wechat.json_request', return_value={'media_id': 'draft'})
    @patch.object(WeChatClient, 'upload', return_value='cover')
    @patch.object(WeChatClient, 'access_token', return_value='token')
    def test_large_article_submitted_without_local_length_limits(self, token, upload, request):
        title = '长标题' * 30
        body = '技术正文' * 90000
        author = '作者名称' * 10
        text = '# ' + title + '\n\n' + body
        self.assertEqual(split_markdown(text)[0], title)
        WeChatClient({'AUTHOR': author}).draft(text, [], 'https://mp.weixin.qq.com/s/a', lambda _: None)
        article = request.call_args.kwargs['json']['articles'][0]
        self.assertEqual(article['title'], title)
        self.assertEqual(article['author'], author)
        self.assertIn(body, article['content'])
        self.assertGreater(len(article['content'].encode()), 1000000)
