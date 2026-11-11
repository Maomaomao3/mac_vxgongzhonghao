import json
import unittest
from unittest.mock import patch, Mock
from network import json_request


class UTF8TransportTests(unittest.TestCase):
    @patch('network.requests.request')
    def test_actual_wire_body_preserves_chinese_and_code(self, call):
        response = Mock()
        response.json.return_value = {'media_id': 'id'}
        call.return_value = response
        payload = {'articles': [{'title': '集群巡检', 'content': '<p>中文正文</p><pre>literal = "\\u96c6"\npath = "C:\\temp"</pre>'}]}
        json_request('POST', 'https://api.weixin.qq.com/cgi-bin/draft/add', json=payload)
        kwargs = call.call_args.kwargs
        raw = kwargs['data']
        self.assertIsInstance(raw, bytes)
        self.assertIn('集群巡检'.encode(), raw)
        self.assertEqual(json.loads(raw), payload)
        self.assertNotIn('json', kwargs)
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/json; charset=utf-8')

    @patch('network.requests.request')
    def test_multipart_untouched(self, call):
        call.return_value.json.return_value = {'media_id': 'id'}
        files = {'media': ('x.jpg', b'image', 'image/jpeg')}
        json_request('POST', 'https://api.weixin.qq.com/cgi-bin/material/add_material', files=files)
        self.assertEqual(call.call_args.kwargs['files'], files)
        self.assertNotIn('data', call.call_args.kwargs)
