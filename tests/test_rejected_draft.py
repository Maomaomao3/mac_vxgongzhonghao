import unittest
from unittest.mock import patch
from wechat import WeChatClient, WeChatRejected


class RejectedTests(unittest.TestCase):
    @patch('wechat.json_request', return_value={'errcode': 45002})
    @patch.object(WeChatClient, 'upload', return_value='cover')
    @patch.object(WeChatClient, 'access_token', return_value='token')
    def test_rejection_not_reported_as_unknown(self, token, upload, request):
        with self.assertRaises(WeChatRejected) as result:
            WeChatClient({'AUTHOR': ''}).draft('# 标题\n正文', [], '', lambda _: None)
        self.assertEqual(result.exception.code, 45002)
        self.assertNotIn('草稿可能已创建', str(result.exception))
