import unittest
from unittest.mock import patch

import audit_ads


class AdAuditTests(unittest.TestCase):
    def test_rejects_credentials_and_non_https_origins(self):
        for url in ("http://example.com", "https://user:secret@example.com", "https://example.com/path"):
            with self.assertRaises(ValueError):
                audit_ads.audit(url)

    def test_missing_config_does_not_claim_delivery_or_payment(self):
        with patch.object(audit_ads, "fetch", return_value=(404, "")):
            result = audit_ads.audit("https://example.com")
        self.assertFalse(result["publisher_id_configured"])
        self.assertFalse(result["ad_loading_enabled"])
        self.assertFalse(result["ad_delivery_verified"])
        self.assertFalse(result["payouts_verified"])

    def test_configured_site_still_needs_dashboard_and_browser_evidence(self):
        page = '<script src="/adsense-config.js"></script><script src="/adsense.js"></script><a href="/about.html">About</a><a href="/privacy.html">Privacy</a>'
        contents = {
            "/": page,
            "/adsense-config.js": 'window.WORLD_DESK_ADSENSE_CLIENT = "ca-pub-1234567890123456"; window.WORLD_DESK_ADSENSE_ENABLED = true;',
            "/ads.txt": 'google.com, pub-1234567890123456, DIRECT, example-certification-id',
            "/issues/index.json": '[{"url":"/issues/issue-2026-10-17.html"}]',
            "/issues/issue-2026-10-17.html": page,
        }
        with patch.object(audit_ads, "fetch", side_effect=lambda base, path: (200, contents.get(path, ""))):
            result = audit_ads.audit("https://example.com")
        self.assertTrue(result["publisher_id_configured"])
        self.assertTrue(result["matching_google_ads_txt"])
        self.assertTrue(all(row["ad_scripts_once"] for row in result["pages"].values()))
        self.assertFalse(result["ad_delivery_verified"])
        self.assertFalse(result["payouts_verified"])

    def test_remote_issue_link_is_not_followed(self):
        with patch.object(audit_ads, "fetch", return_value=(200, '[{"url":"https://untrusted.example/issue.html"}]')) as mocked:
            audit_ads.audit("https://example.com")
        self.assertEqual(mocked.call_count, 7)
