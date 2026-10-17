"""Offline WordPress integration checks; no account or network access required."""
import json
import contextlib
import io
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import newsletter
import wordpress_publish as wp


class WordPressTests(unittest.TestCase):
    def setUp(self):
        self.client = wp.WordPressClient("https://news.example", "publisher", "test-only-secret")
        self.issue = wp.build_issue([{"title": "A <b>headline</b>", "source": "A & B",
                                     "url": "https://source.example/story?a=1&b=2",
                                     "summary": "Do not copy this feed text",
                                     "image_reference": "https://source.example/picture.jpg"}], "2026-10-17")
        self.me = {"id": 7, "capabilities": {"publish_posts": True, "edit_posts": True}}
        self.post = {"id": 42, "slug": self.issue["slug"], "status": "publish", "author": 7,
                     "title": {"raw": self.issue["title"]}, "content": {"raw": self.issue["content"]},
                     "link": "https://news.example/world-desk-daily-2026-10-17/"}

    def test_core_blocks_escape_and_omit_source_text_and_images(self):
        content = self.issue["content"]
        self.assertIn('class="wp-block-heading"', content)
        self.assertIn("A &amp; B", content)
        self.assertIn("a=1&amp;b=2", content)
        for prohibited in ["<b>", "Do not copy", "picture.jpg", "<script", "<img"]:
            self.assertNotIn(prohibited, content)

    def test_original_summary_and_availability_notice(self):
        issue = wp.build_issue([{"title": "One", "url": "https://source.example"}], "2026-10-17",
                               {"https://source.example": "An original summary."}, True)
        self.assertIn("An original summary.", issue["content"])
        self.assertIn("Some sources were unavailable", issue["content"])
        self.assertIn("generated with AI", issue["content"])

    def test_empty_or_unsafe_items_fail_before_network(self):
        for items in [[], [{"title": "Bad", "url": "javascript:alert(1)"}],
                      [{"title": "Bad", "url": "https://user:pass@example.com/"}]]:
            with self.subTest(items=items), self.assertRaises(RuntimeError):
                wp.build_issue(items, "2026-10-17")

    def test_deduplicates_links(self):
        item = {"title": "One", "url": "https://source.example"}
        self.assertIn("1 stories", wp.build_issue([item, item], "2026-10-17")["excerpt"])

    def test_rejects_unsafe_site_urls_and_missing_credentials(self):
        for url in ["", "http://example.com", "https://a:b@example.com", "https://example.com?a=b",
                    "https://example.com/#fragment", "https://example.com\n", "https://example.com:bad"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                wp.WordPressClient(url, "publisher", "secret")
        with self.assertRaises(ValueError):
            wp.WordPressClient("https://example.com", "", "secret")

    def test_redirects_never_forward_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "not forwarded"):
            wp.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/")

    def test_http_and_network_errors_do_not_echo_secrets(self):
        for failure in [urllib.error.HTTPError("https://secret.example", 401, "test-only-secret", {}, None),
                        urllib.error.URLError("test-only-secret")]:
            self.client._opener = Mock()
            self.client._opener.open.side_effect = failure
            with self.assertRaises(RuntimeError) as raised:
                self.client.request("users/me")
            self.assertNotIn("test-only-secret", str(raised.exception))

    def test_creates_and_reads_back_post(self):
        self.client.request = Mock(side_effect=[self.me, [], {"id": 42}, self.post])
        with tempfile.TemporaryDirectory() as folder:
            result = wp.publish_once(self.client, self.issue, "publish", Path(folder))
            state = json.loads(next(Path(folder).glob("*.json")).read_text())
            self.assertEqual(state["state"], "confirmed")
            self.assertFalse(list(Path(folder).glob("*.lock")))
        self.assertEqual(result["action"], "created")
        self.assertEqual(self.client.request.call_args_list[2].args[0], "posts")
        self.assertEqual(self.client.request.call_args_list[2].args[1]["status"], "publish")

    def test_existing_issue_is_preserved_with_no_write(self):
        edited = {**self.post, "content": {"raw": self.issue["content"] + "\nEditorial addition"}}
        self.client.request = Mock(side_effect=[self.me, [edited]])
        with tempfile.TemporaryDirectory() as folder:
            result = wp.publish_once(self.client, self.issue, "publish", Path(folder))
        self.assertEqual(result["action"], "already_exists")
        self.assertTrue(all(len(call.args) == 1 for call in self.client.request.call_args_list))

    def test_collision_or_status_change_does_not_overwrite(self):
        for post in [{**self.post, "author": 9}, {**self.post, "status": "draft"},
                     {**self.post, "content": {"raw": "Other article"}}]:
            self.client.request = Mock(side_effect=[self.me, [post]])
            with tempfile.TemporaryDirectory() as folder, self.assertRaises(RuntimeError):
                wp.publish_once(self.client, self.issue, "publish", Path(folder))
            self.assertEqual(self.client.request.call_count, 2)

    def test_uncertain_write_is_not_retried(self):
        self.client.request = Mock(side_effect=[self.me, [], RuntimeError("connection failed")])
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):
                wp.publish_once(self.client, self.issue, "publish", Path(folder))
            self.client.request = Mock(side_effect=[self.me, []])
            with self.assertRaisesRegex(RuntimeError, "previous write"):
                wp.publish_once(self.client, self.issue, "publish", Path(folder))
            self.assertEqual(self.client.request.call_count, 2)

    def test_uncertain_write_can_be_reconciled_by_reading_existing_post(self):
        self.client.request = Mock(side_effect=[self.me, [], RuntimeError("connection failed")])
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):
                wp.publish_once(self.client, self.issue, "publish", Path(folder))
            self.client.request = Mock(side_effect=[self.me, [self.post]])
            result = wp.publish_once(self.client, self.issue, "publish", Path(folder))
            self.assertEqual(result["action"], "already_exists")

    def test_readback_mismatch_stops_and_leaves_pending_state(self):
        altered = {**self.post, "content": {"raw": "Unexpected content"}}
        self.client.request = Mock(side_effect=[self.me, [], {"id": 42}, altered])
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(RuntimeError, "changed the saved"):
            wp.publish_once(self.client, self.issue, "publish", Path(folder))

    def test_permission_failure_prevents_writes(self):
        self.client.request = Mock(return_value={"id": 7, "capabilities": {"edit_posts": True}})
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(RuntimeError, "author permission"):
            wp.publish_once(self.client, self.issue, "publish", Path(folder))
        self.assertEqual(self.client.request.call_count, 1)

    def test_external_post_url_is_rejected(self):
        for url in ["http://news.example/post", "https://other.example/post", "https://user@news.example/post"]:
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                wp.validate_result(self.client, {**self.post, "link": url}, self.issue, "publish", 7)

    def test_draft_mode_does_not_publish(self):
        draft = {**self.post, "status": "draft"}
        self.client.request = Mock(side_effect=[self.me, [], {"id": 42}, draft])
        with tempfile.TemporaryDirectory() as folder:
            result = wp.publish_once(self.client, self.issue, "draft", Path(folder))
        self.assertEqual(result["status"], "draft")
        self.assertEqual(self.client.request.call_args_list[2].args[1]["status"], "draft")

    def test_cli_wordpress_flag_reaches_publisher(self):
        item = {"title": "Story", "url": "https://source.example", "source": "Source"}
        result = {"status": "publish", "link": self.post["link"], "action": "created"}
        with patch.object(sys, "argv", ["newsletter.py", "--wordpress", "publish", "--no-log"]), \
             patch.object(wp.WordPressClient, "from_environment", return_value=self.client), \
             patch.object(newsletter, "collect", return_value=([item], [])), \
             patch.object(newsletter, "collect_global_watch", return_value=([], [])), \
             patch.object(newsletter, "write_draft", return_value=(Path("draft.md"), Path("draft.html"))), \
             patch.object(wp, "publish_once", return_value=result) as publish, \
             patch.dict(wp.os.environ, {"NEWSLETTER_AI_PUBLIC_SUMMARIES": "false"}), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(newsletter.main(), 0)
        self.assertEqual(publish.call_args.args[0], self.client)
        self.assertEqual(publish.call_args.args[2], "publish")
        self.assertIn("Story", publish.call_args.args[1]["content"])

    def test_cli_missing_configuration_fails_before_collecting(self):
        with patch.object(sys, "argv", ["newsletter.py", "--wordpress", "publish", "--no-log"]), \
             patch.dict(wp.os.environ, {}, clear=True), \
             patch.object(newsletter, "collect") as collect, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(newsletter.main(), 1)
        collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
