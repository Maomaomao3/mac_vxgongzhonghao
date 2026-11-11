import unittest
from bs4 import BeautifulSoup
from formatting import compact_html,to_markdown
from rendering import render


class FormattingTests(unittest.TestCase):
    def test_redundant_style_without_text_loss(self):
        original='<div style="color: red"><span style="color: red">中文</span><pre>x = 1\n    y = 2</pre></div>'
        compact=compact_html(original)
        self.assertNotIn('<span', compact)
        self.assertEqual(BeautifulSoup(original,'html.parser').get_text(),BeautifulSoup(compact,'html.parser').get_text())

    def test_markdown_roundtrip_preserves_complex_table_and_code(self):
        original='<h2>步骤</h2><pre style="font-family:monospace">if x:\n    run()</pre><table><tr><td colspan="2">内容</td></tr></table>'
        md=to_markdown(original)
        self.assertIn('## 步骤',md)
        _,html=render('# 标题\n\n'+md,[])
        soup=BeautifulSoup(html,'html.parser')
        self.assertEqual(soup.pre.get_text(),'if x:\n    run()')
        self.assertEqual(soup.td['colspan'],'2')
