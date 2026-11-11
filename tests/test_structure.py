import json
import unittest
from unittest.mock import Mock
from bs4 import BeautifulSoup
from crawler import parse_html
from structure import rewrite_structure
from rendering import render


class StructureTests(unittest.TestCase):
    def sample(self):
        return parse_html('<h1 id="activity-name">技术教程</h1><div id="js_content"><h2>步骤一</h2><p>' + '这是一段用于说明具体技术操作的普通叙述。' * 3 + '</p><pre><code>if x &lt; 2:\n    print("ok")</code></pre><table><tr><th>参数</th><td>42</td></tr></table><p><code>rm -rf</code> 不得执行</p></div>')

    def test_rewrite_keeps_technical_elements(self):
        source = self.sample()
        client = Mock()
        def complete(system, user):
            if 'JSON数组' in system:
                return json.dumps([{'id': row['id'], 'text': '改写后的普通讲解。'} for row in json.loads(user)])
            return '这是单独的分析推断。'
        client.complete.side_effect = complete
        output = rewrite_structure(client, source, lambda _: None)
        _, html = render(output, [])
        original = BeautifulSoup(source['html'], 'html.parser')
        result = BeautifulSoup(html, 'html.parser')
        self.assertEqual(result.pre.get_text(), original.pre.get_text())
        self.assertEqual(result.table.get_text(), original.table.get_text())
        self.assertIn('rm -rf', result.get_text())
        self.assertNotIn('AI 补充分析', result.get_text())
        self.assertEqual(client.complete.call_count, 1)
        self.assertIn('不是评论员', client.complete.call_args.args[0])
        self.assertIn('必要说明自然融入正文', client.complete.call_args.args[0])
        self.assertIn('改写后的普通讲解', result.get_text())

    def test_markdown_code_and_table(self):
        _, html = render('# 标题\n\n```python\nprint(42)\n```\n\n|a|b|\n|-|-|\n|1|2|', [])
        self.assertIsNotNone(BeautifulSoup(html, 'html.parser').pre)
        self.assertIn('<table>', html)

    def test_bad_response_does_not_silently_drop_paragraph(self):
        client = Mock()
        client.complete.return_value = '[]'
        with self.assertRaisesRegex(RuntimeError, '响应结构不完整'):
            rewrite_structure(client, self.sample(), lambda _: None)
