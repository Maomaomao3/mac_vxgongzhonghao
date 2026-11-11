import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from publishing import publish_reviewed, remote_fingerprint
from network import AppError


class PublishTests(unittest.TestCase):
    def setup_case(self):
        client = Mock()
        client.cfg = {'WECHAT_APP_ID': 'a'}
        remote = {'news_item': [{'title': 'Title', 'content': 'Body'}]}
        client.get_draft.return_value = remote
        client.submit_publish.return_value = 'publish-1'
        client.publish_status.return_value = {'publish_status': 0, 'article_detail': {'item': [{'article_url': 'https://mp.weixin.qq.com/s/test'}]}}
        record = {'appid': 'a', 'fingerprint': 'hash', 'remote_fingerprint': remote_fingerprint(remote), 'media_id': 'draft'}
        return client, record

    def test_success_and_repeat_only_queries(self):
        client, record = self.setup_case()
        with TemporaryDirectory() as directory:
            self.assertEqual(publish_reviewed(client, record, 'hash', directory, lambda _: None)['status'], 'published')
            publish_reviewed(client, record, 'hash', directory, lambda _: None)
            client.submit_publish.assert_called_once()

    def test_changed_local_version_blocks(self):
        client, record = self.setup_case()
        with TemporaryDirectory() as directory, self.assertRaises(AppError):
            publish_reviewed(client, record, 'changed', directory, lambda _: None)
        client.submit_publish.assert_not_called()

    def test_remote_changes_block(self):
        client, record = self.setup_case()
        client.get_draft.return_value = {'news_item': [{'title': 'Changed'}]}
        with TemporaryDirectory() as directory, self.assertRaises(AppError):
            publish_reviewed(client, record, 'hash', directory, lambda _: None)
        client.submit_publish.assert_not_called()

    def test_timeout_not_resubmitted(self):
        client, record = self.setup_case()
        client.submit_publish.side_effect = AppError('timeout')
        with TemporaryDirectory() as directory:
            for _ in range(2):
                with self.assertRaises(AppError):
                    publish_reviewed(client, record, 'hash', directory, lambda _: None)
        client.submit_publish.assert_called_once()

    def test_platform_rejection_is_not_success(self):
        client, record = self.setup_case()
        client.publish_status.return_value = {'publish_status': 4}
        with TemporaryDirectory() as directory, self.assertRaisesRegex(AppError, '状态码 4'):
            publish_reviewed(client, record, 'hash', directory, lambda _: None)
