"""Offline checks for the newsletter draft pipeline."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import newsletter


class NewsletterTests(unittest.TestCase):
    def test_clean_text_removes_markup_and_scripts(self):
        self.assertEqual(newsletter.clean_text("<p>Hello</p><script>bad()</script> world"), "Hello world")

    def test_parse_feed_keeps_only_http_links(self):
        xml = b"""<rss><channel><item><title>Story</title><link>https://example.com/story</link>
        <description><![CDATA[<b>Useful excerpt</b>]]></description></item>
        <item><title>Bad link</title><link>javascript:alert(1)</link></item></channel></rss>"""

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return xml

        with patch.object(newsletter.urllib.request, "urlopen", return_value=FakeResponse()):
            items = newsletter.parse_feed({"name": "Example", "url": "https://example.com/feed"})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["summary"], "Useful excerpt")

    def test_invalid_feed_scheme_is_rejected_before_network(self):
        with self.assertRaises(ValueError):
            newsletter.parse_feed({"name": "Local", "url": "http://localhost/feed"})

    def test_write_draft_replaces_existing_files_and_escapes_html(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(newsletter, "DRAFTS", Path(folder)):
                md_path, html_path = newsletter.write_draft("<script>alert(1)</script>")
            self.assertIn("<script>alert(1)</script>", md_path.read_text(encoding="utf-8"))
            self.assertIn("&lt;script&gt;", html_path.read_text(encoding="utf-8"))
            self.assertFalse(list(Path(folder).glob("*.tmp")))

    def test_public_issue_escapes_content_keeps_source_links_and_updates_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            issues = root / "issues"
            index = issues / "index.json"
            items = [{"title": "<b>headline</b>", "url": "https://example.com/story",
                      "source": "Example & Co", "summary": "A" * 300, "published": "today"},
                     {"title": "bad", "url": "javascript:alert(1)", "source": "Bad"}]
            with patch.object(newsletter, "PUBLIC_ISSUES", issues), \
                 patch.object(newsletter, "PUBLIC_INDEX", index):
                issue_path = newsletter.publish_issue(items, ["GDELT HTTP 429"])
            rendered = issue_path.read_text(encoding="utf-8")
            entries = json.loads(index.read_text(encoding="utf-8"))
            self.assertIn("headline", rendered)
            self.assertNotIn("<b>headline</b>", rendered)
            self.assertIn("https://example.com/story", rendered)
            self.assertNotIn("A" * 100, rendered)
            self.assertIn("Open the original report for the story details.", rendered)
            self.assertNotIn("javascript:alert(1)", rendered)
            self.assertIn("does not prove a story has not appeared in U.S. media", rendered)
            self.assertIn("Source availability notes", rendered)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["url"], f"/issues/{issue_path.name}")

    def test_public_issue_uses_original_summary_not_feed_excerpt(self):
        with tempfile.TemporaryDirectory() as folder:
            issues = Path(folder) / "issues"
            url = "https://example.com/report"
            item = {"title": "Headline", "url": url, "source": "Example",
                    "summary": "Do not publish this syndicated feed excerpt."}
            with patch.object(newsletter, "PUBLIC_ISSUES", issues), \
                 patch.object(newsletter, "PUBLIC_INDEX", issues / "index.json"):
                page = newsletter.publish_issue([item], [], {url: "An independently worded brief based on the source listing."})
            rendered = page.read_text(encoding="utf-8")
            self.assertIn("An independently worded brief", rendered)
            self.assertNotIn("Do not publish this syndicated feed excerpt", rendered)

    def test_ai_story_summary_requires_every_collected_item(self):
        articles = [{"title": "One", "url": "https://one.example", "source": "One"},
                    {"title": "Two", "url": "https://two.example", "source": "Two"}]
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                newsletter.generate_story_summaries(articles)

    def test_ai_story_summary_rejects_missing_story(self):
        response_body = json.dumps({"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps({"summaries": [{"id": 0, "summary": "First summary."}]})}
        ]}]}).encode()

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return response_body

        articles = [{"title": "One", "url": "https://one.example", "source": "One"},
                    {"title": "Two", "url": "https://two.example", "source": "Two"}]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
             patch.object(newsletter.urllib.request, "urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "exactly one summary per collected story"):
                newsletter.generate_story_summaries(articles)

    def test_ai_story_summary_maps_every_item_to_its_source_url(self):
        summaries = {"summaries": [
            {"id": 0, "summary": "An original brief for the first report."},
            {"id": 1, "summary": "A separate original brief for the second report."},
        ]}
        response_body = json.dumps({"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(summaries)}
        ]}]}).encode()

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return response_body

        articles = [{"title": "One", "url": "https://one.example", "source": "One"},
                    {"title": "Two", "url": "https://two.example", "source": "Two"}]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
             patch.object(newsletter.urllib.request, "urlopen", return_value=FakeResponse()):
            result = newsletter.generate_story_summaries(articles)
        self.assertEqual(result, {
            "https://one.example": "An original brief for the first report.",
            "https://two.example": "A separate original brief for the second report.",
        })

    def test_public_issue_keeps_existing_index_when_no_articles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            issues = root / "issues"
            issues.mkdir()
            index = issues / "index.json"
            index.write_text("[]\n", encoding="utf-8")
            with patch.object(newsletter, "PUBLIC_ISSUES", issues), \
                 patch.object(newsletter, "PUBLIC_INDEX", index), \
                 self.assertRaisesRegex(RuntimeError, "keeping the existing public issue"):
                newsletter.publish_issue([], ["all feeds failed"])
            self.assertEqual(index.read_text(encoding="utf-8"), "[]\n")

    def test_collect_reports_bad_config_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "sources.json"
            config.write_text(json.dumps({"feeds": "not-a-list"}), encoding="utf-8")
            with patch.object(newsletter, "SOURCES", config):
                with self.assertRaises(ValueError):
                    newsletter.collect()

    def test_gdelt_search_sanitizes_results_and_image_urls(self):
        payload = json.dumps({"articles": [
            {"title": "Example headline", "url": "https://news.example/story",
             "domain": "news.example", "sourcecountry": "France", "language": "French",
             "seendate": "20261017T100000Z", "socialimage": "javascript:alert(1)"},
            {"title": "Invalid URL", "url": "javascript:alert(1)"}
        ]}).encode()

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return payload

        with patch.object(newsletter.urllib.request, "urlopen", return_value=FakeResponse()):
            records = newsletter.gdelt_search("topic", "24h", 5)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_country"], "France")
        self.assertEqual(records[0]["image_reference"], "")

    def test_digest_does_not_claim_no_us_coverage(self):
        item = {"title": "Story", "url": "https://example.com/story", "source": "Example",
                "source_country": "Japan", "topic": "topic", "gdelt_seen": "today",
                "language": "Japanese", "us_topic_result_count": 0, "us_topic_examples": []}
        digest = newsletter.make_digest([item], [])
        self.assertIn("does not prove no U.S. outlet covered the story", digest)
        self.assertIn("not original publication time", digest)

    def test_gdelt_rate_limit_stops_remaining_searches(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "sources.json"
            config.write_text(json.dumps({"global_discovery": {
                "enabled": True, "topics": ["one", "two"]
            }}), encoding="utf-8")
            rate_limit = newsletter.urllib.error.HTTPError("https://api.gdeltproject.org", 429, "Too Many Requests", {}, None)
            with patch.object(newsletter, "SOURCES", config), \
                 patch.object(newsletter, "gdelt_search", side_effect=rate_limit) as search:
                articles, errors = newsletter.collect_global_watch()
        self.assertEqual(articles, [])
        self.assertEqual(search.call_count, 1)
        self.assertTrue(any("global discovery was skipped" in message for message in errors))

    def test_global_watch_uses_two_bounded_combined_queries(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "sources.json"
            config.write_text(json.dumps({"global_discovery": {
                "enabled": True, "topics": ["climate change", "technology"],
                "maxrecords_per_search": 40, "compare_us": True
            }}), encoding="utf-8")
            worldwide = [{"title": "Climate technology", "url": "https://example.com/a",
                          "source": "Example", "source_country": "Japan"}]
            with patch.object(newsletter, "SOURCES", config), \
                 patch.object(newsletter, "gdelt_search", side_effect=[worldwide, []]) as search:
                articles, errors = newsletter.collect_global_watch()
        self.assertEqual(search.call_count, 2)
        self.assertIn('"climate change" OR technology', search.call_args_list[0].args[0])
        self.assertIn("sourcecountry:unitedstates", search.call_args_list[1].args[0])
        self.assertEqual(search.call_args_list[0].args[2], 40)
        self.assertEqual(errors, [])
        self.assertFalse(articles[0]["us_exact_check_performed"])

    def test_rate_limit_retry_obeys_retry_after_once(self):
        payload = b'{"ok": true}'
        failure = newsletter.urllib.error.HTTPError(
            "https://example.com", 429, "Too Many Requests", {"Retry-After": "0"}, None)

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return payload

        request = newsletter.urllib.request.Request("https://example.com")
        with patch.object(newsletter.urllib.request, "urlopen", side_effect=[failure, FakeResponse()]) as urlopen, \
             patch.object(newsletter.time, "sleep") as sleep:
            result = newsletter.read_with_rate_limit_retry(request, 10)
        self.assertEqual(result, payload)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0)

    def test_spaces_archive_uploads_private_objects(self):
        uploads = []
        fake_client = types.SimpleNamespace(upload_file=lambda *args, **kwargs: uploads.append((args, kwargs)))
        fake_boto3 = types.SimpleNamespace(client=lambda *args, **kwargs: fake_client)
        fake_botocore = types.ModuleType("botocore")
        fake_config_mod = types.ModuleType("botocore.config")
        fake_config_mod.Config = lambda **kwargs: kwargs
        fake_botocore.config = fake_config_mod
        with tempfile.TemporaryDirectory() as folder:
            md = Path(folder) / "newsletter-2026-10-17.md"
            page = Path(folder) / "newsletter-2026-10-17.html"
            md.write_text("draft", encoding="utf-8")
            page.write_text("preview", encoding="utf-8")
            env = {"DO_SPACES_KEY": "test-key", "DO_SPACES_SECRET": "test-secret",
                   "DO_SPACES_BUCKET": "private-bucket", "DO_SPACES_REGION": "nyc3"}
            with patch.dict(os.environ, env, clear=False), \
                 patch.dict(sys.modules, {"boto3": fake_boto3, "botocore": fake_botocore,
                                          "botocore.config": fake_config_mod}):
                keys = newsletter.archive_draft_to_spaces((md, page))
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(uploads), 2)
        self.assertTrue(all(call[1]["ExtraArgs"]["ACL"] == "private" for call in uploads))

    def test_spaces_archive_requires_all_configuration_without_leaking_secrets(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DO_SPACES_KEY"):
                newsletter.archive_draft_to_spaces((Path("a.md"), Path("b.html")))


if __name__ == "__main__":
    unittest.main()
