import unittest
from bs4 import BeautifulSoup
from formatting import compact_html
from rendering import render


class CodeContrastTests(unittest.TestCase):
    def test_dark_theme_foreground_not_left_on_light_background(self):
        original = '<pre style="background-color:#f4f5f7"><code style="color:#e6e6e6;padding:1em"><span style="color:white">if x:\n    run()</span></code></pre>'
        result = compact_html(original)
        soup = BeautifulSoup(result, 'html.parser')
        self.assertEqual(soup.pre.get_text(), 'if x:\n    run()')
        self.assertIn('color:#24292f', soup.code['style'])
        self.assertNotIn('#e6e6e6', result)
        self.assertNotIn('color:white', result)
        self.assertEqual(compact_html(result), result)

    def test_existing_article_submission_render_fixed(self):
        _, html = render('# 标题\n\n<pre><code style="color:#e6e6e6">print(42)</code></pre>', [])
        self.assertIn('color:#24292f', html)
        self.assertNotIn('#e6e6e6', html)
