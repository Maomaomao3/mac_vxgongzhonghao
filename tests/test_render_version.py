import unittest
from unittest.mock import patch
from publishing import fingerprint


class RenderVersionTests(unittest.TestCase):
    def test_style_change_invalidates_cached_draft(self):
        with patch('rendering.render', return_value=('标题', '<pre style="color:white">code</pre>')):
            before = fingerprint('# 标题\ncode', [], 'url')
        with patch('rendering.render', return_value=('标题', '<pre style="color:black">code</pre>')):
            after = fingerprint('# 标题\ncode', [], 'url')
        self.assertNotEqual(before, after)
