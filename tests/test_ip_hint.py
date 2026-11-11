import unittest
from wechat import WeChatClient
from network import AppError


class IPHintTests(unittest.TestCase):
    def test_ipv4_hint(self):
        with self.assertRaisesRegex(AppError, '203.0.113.5') as result:
            WeChatClient.check({'errcode':40164, 'errmsg':'invalid ip 203.0.113.5 ipv6 ::ffff:203.0.113.5, not in whitelist rid: secret'})
        self.assertNotIn('secret', str(result.exception))

    def test_ipv6_hint(self):
        with self.assertRaisesRegex(AppError, '2001:db8::1'):
            WeChatClient.check({'errcode':40164,'errmsg':'invalid ip 2001:db8::1, not in whitelist'})

    def test_invalid_address_not_echoed(self):
        with self.assertRaises(AppError) as result:
            WeChatClient.check({'errcode':40164,'errmsg':'invalid ip secret-value, not in whitelist'})
        self.assertNotIn('secret-value', str(result.exception))
