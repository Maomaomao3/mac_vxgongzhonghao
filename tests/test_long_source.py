import unittest
from unittest.mock import patch
from ai import AIClient, split_source
from crawler import fetch
from rendering import render


class LongSourceTests(unittest.TestCase):
    def test_split_preserves_every_character(self):
        text = ('段落内容\n' * 3500) + '单段' * 15000
        chunks = split_source(text)
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(c) <= 12000 for c in chunks))

    def test_long_manual_input_accepted(self):
        text = '正文' * 25000
        self.assertEqual(fetch('https://mp.weixin.qq.com/s/test', text)['text'], text)

    def test_summarizes_every_chunk_then_rewrites(self):
        client = AIClient({})
        text = '资料' * 25000
        chunks = split_source(text)
        with patch.object(client, 'complete', side_effect=['摘要'] * len(chunks) + ['# 标题\n正文']) as call:
            self.assertEqual(client.rewrite({'title': '原文', 'text': text}), '# 标题\n正文')
            self.assertEqual([c.args[1] for c in call.call_args_list[:-1]], chunks)
            self.assertLess(len(call.call_args.args[1]), 40000)

    def test_no_progress_stops(self):
        client = AIClient({})
        with patch.object(client, 'complete', side_effect=lambda system, user: user):
            with self.assertRaisesRegex(RuntimeError, '未有效压缩'):
                client.rewrite({'title': '原文', 'text': '文' * 50000})

    def test_local_photo_has_no_false_pexels_credit(self):
        _, html = render('# 标题\n正文', [{'path': '/tmp/a.jpg', 'page': '', 'photographer': ''}])
        self.assertIn('<img', html)
        self.assertNotIn('Pexels', html)
