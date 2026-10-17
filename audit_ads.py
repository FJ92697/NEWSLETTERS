"""Read-only website configuration audit. This cannot prove ad delivery or payment."""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])


def fetch(base, path):
    request = urllib.request.Request(base + path, headers={"User-Agent": "WorldDeskConfigurationAudit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if urllib.parse.urlsplit(response.url).netloc != urllib.parse.urlsplit(base).netloc:
                return 0, ""
            return response.status, response.read(2_000_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def audit(base):
    parts = urllib.parse.urlsplit(base)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/"):
        raise ValueError("Use an HTTPS origin without credentials, query, or path.")
    base = base.rstrip("/")
    paths = ["/", "/adsense-config.js", "/adsense.js", "/about.html", "/privacy.html", "/ads.txt", "/issues/index.json"]
    responses = {path: fetch(base, path) for path in paths}
    index_status, index_text = responses["/issues/index.json"]
    if index_status == 200:
        try:
            entries = json.loads(index_text)
            if isinstance(entries, list) and entries and isinstance(entries[0], dict):
                latest = entries[0].get("url", "")
                if isinstance(latest, str) and re.fullmatch(r"/issues/issue-\d{4}-\d{2}-\d{2}\.html", latest):
                    responses[latest] = fetch(base, latest)
        except (ValueError, TypeError):
            pass
    match = re.search(r'WORLD_DESK_ADSENSE_CLIENT\s*=\s*"(ca-pub-\d{16})"', responses["/adsense-config.js"][1])
    client = match.group(1) if match else None
    enabled = bool(re.search(r"WORLD_DESK_ADSENSE_ENABLED\s*=\s*true\s*;", responses["/adsense-config.js"][1]))
    pages = {}
    for path, (status, content) in responses.items():
        if path != "/" and not path.startswith("/issues/issue-"):
            continue
        page = Page(); page.feed(content)
        pages[path] = {"http_status": status,
                       "ad_scripts_once": page.scripts.count("/adsense-config.js") == 1 and page.scripts.count("/adsense.js") == 1,
                       "publisher_links": all(link in page.links for link in ("/about.html", "/privacy.html"))}
    seller = client.removeprefix("ca-") if client else None
    authorized = False
    for line in responses["/ads.txt"][1].splitlines():
        fields = [field.strip().lower() for field in line.split("#", 1)[0].split(",")]
        if seller and len(fields) >= 3 and fields[:3] == ["google.com", seller, "direct"]:
            authorized = True
    return {"site": base, "http_statuses": {path: status for path, (status, _) in responses.items()},
            "pages": pages, "publisher_id_configured": bool(client), "ad_loading_enabled": enabled,
            "matching_google_ads_txt": authorized, "ad_delivery_verified": False, "payouts_verified": False,
            "limitations": ["An HTTP/configuration check does not prove account approval, rendered ads, impressions, earnings, or payment.",
                            "Complete provider dashboard review and privacy/consent setup before activation."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://161-35-103-204.sslip.io")
    args = parser.parse_args()
    try:
        result = audit(args.url)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    # Nonzero means activation still needs attention, never proof of income.
    ready = result["publisher_id_configured"] and result["ad_loading_enabled"] and result["matching_google_ads_txt"]
    ready = ready and len(result["pages"]) >= 2 and all(p["http_status"] == 200 and p["ad_scripts_once"] and p["publisher_links"] for p in result["pages"].values())
    ready = ready and all(result["http_statuses"].get(p) == 200 for p in ("/about.html", "/privacy.html", "/adsense-config.js", "/adsense.js"))
    sys.exit(0 if ready else 2)
