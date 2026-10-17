"""Opt-in WordPress REST publishing. No account, site, theme, or ad settings are changed."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import html
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlsplit

MAX_RESPONSE = 2_000_000


def text(value: object, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value)))).strip()[:limit]


def paragraph(value: str) -> str:
    return f"<!-- wp:paragraph -->\n<p>{html.escape(value)}</p>\n<!-- /wp:paragraph -->"


def build_issue(articles: list[dict], stamp: str, summaries: dict | None = None,
                degraded: bool = False) -> dict:
    dt.date.fromisoformat(stamp)
    marker = f"World Desk automated briefing — {stamp}"
    blocks = [paragraph(marker), paragraph(
        "A quick guide to the day's reporting, with links so you can explore the stories that interest you. "
        "This briefing is assembled automatically and is not independently fact-checked.")]
    if degraded:
        blocks.append(paragraph("Some sources were unavailable for this edition, so coverage is limited."))
    count, seen = 0, set()
    for item in articles[:50]:
        title = text(item.get("title", ""), 300)
        url = str(item.get("url", "")).strip()
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password
        except ValueError:
            valid = False
        if not title or not valid or url in seen or any(ord(c) < 32 for c in url):
            continue
        seen.add(url)
        count += 1
        blocks.append(f'<!-- wp:heading -->\n<h2 class="wp-block-heading">{html.escape(title)}</h2>\n<!-- /wp:heading -->')
        blocks.append(paragraph("Source: " + text(item.get("source", "Original publisher"), 100)))
        # Only separately generated, original summaries can enter the public post.
        # Never reuse the feed excerpt, article body, or image reference.
        summary = text((summaries or {}).get(url, ""))
        if summary:
            blocks.append(paragraph(summary))
        blocks.append('<!-- wp:paragraph -->\n<p><a href="' + html.escape(url, quote=True)
                      + '" rel="noopener noreferrer">Read the original reporting</a></p>\n<!-- /wp:paragraph -->')
    if not count:
        raise RuntimeError("No valid stories; no WordPress post will be created.")
    if summaries:
        blocks.append(paragraph("Summaries were generated with AI from limited source metadata; check the linked reporting for full context."))
    return {"slug": f"world-desk-daily-{stamp}", "title": f"World Desk Daily Brief — {stamp}",
            "content": "\n\n".join(blocks), "excerpt": f"Explore {count} stories in today's source-linked briefing.",
            "comment_status": "closed", "ping_status": "closed"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("WordPress redirected the request. Configure its final HTTPS URL; credentials were not forwarded.")


class WordPressClient:
    def __init__(self, site: str, username: str, password: str):
        try:
            parsed = urlsplit(site)
            valid = (parsed.scheme == "https" and parsed.hostname and not parsed.username
                     and not parsed.password and not parsed.query and not parsed.fragment
                     and not any(ord(c) < 33 for c in site))
            parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("WORDPRESS_SITE_URL must be the exact HTTPS site URL, without credentials, query, or fragment.")
        if not username or not password or ":" in username or any(c in username + password for c in "\r\n"):
            raise ValueError("WordPress needs a username and application password supplied as runtime secrets.")
        self.site = site.rstrip("/")
        self._auth = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self._opener = urllib.request.build_opener(NoRedirect())

    @classmethod
    def from_environment(cls):
        return cls(os.environ.get("WORDPRESS_SITE_URL", ""),
                   os.environ.get("WORDPRESS_USERNAME", ""),
                   os.environ.get("WORDPRESS_APPLICATION_PASSWORD", ""))

    def request(self, endpoint: str, body: dict | None = None):
        request = urllib.request.Request(self.site + "/wp-json/wp/v2/" + endpoint,
            data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
            headers={"Authorization": self._auth, "Content-Type": "application/json",
                     "Accept": "application/json", "User-Agent": "WorldDeskPublisher/1.0"})
        try:
            with self._opener.open(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise RuntimeError(f"WordPress API returned HTTP {code}. Check site access and author permissions.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("WordPress connection failed. No automatic write retry was attempted.") from None
        if len(raw) > MAX_RESPONSE:
            raise RuntimeError("WordPress response exceeded the size limit.")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise RuntimeError("WordPress returned an invalid JSON response.") from None


def write_state(path: Path, state: dict) -> None:
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".wp-state-", delete=False) as handle:
            name = handle.name
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def publish_once(client: WordPressClient, issue: dict, status: str, state_dir: Path) -> dict:
    """Create once per site/date. Existing posts are preserved, including manual edits.

    A durable pending marker blocks repeat creates after an ambiguous failure.
    Use one publisher/state directory per site; this is not a distributed lock.
    """
    if status not in {"draft", "publish"}:
        raise ValueError("WordPress status must be draft or publish.")
    slug = issue.get("slug", "")
    if not re.fullmatch(r"world-desk-daily-\d{4}-\d{2}-\d{2}", slug):
        raise ValueError("Unexpected newsletter issue slug.")
    state_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((client.site + "/" + slug).encode()).hexdigest()
    state_path, lock_path = state_dir / (key + ".json"), state_dir / (key + ".lock")
    try:
        lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError("Another publisher is running or left a stale lock; inspect the run before retrying.") from None
    try:
        os.close(lock)
        me = client.request("users/me?_fields=id,capabilities&context=edit")
        if not isinstance(me, dict) or type(me.get("id")) is not int or me["id"] <= 0:
            raise RuntimeError("WordPress did not confirm the publisher identity.")
        needed = "publish_posts" if status == "publish" else "edit_posts"
        capabilities = me.get("capabilities")
        if not isinstance(capabilities, dict) or capabilities.get(needed) is not True:
            raise RuntimeError("The WordPress account lacks the required author permission.")
        query = urlencode({"slug": slug, "status": "any", "context": "edit", "per_page": 2,
                           "_fields": "id,slug,status,link,author,title,content"})
        matches = client.request("posts?" + query)
        if not isinstance(matches, list) or len(matches) > 1:
            raise RuntimeError("WordPress issue lookup was ambiguous; nothing was written.")
        previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
        if matches:
            found = matches[0]
            marker = paragraph("World Desk automated briefing — " + slug.removeprefix("world-desk-daily-"))
            if (not isinstance(found, dict) or found.get("slug") != slug or found.get("author") != me["id"]
                    or raw_field(found, "title") != issue["title"]
                    or marker not in raw_field(found, "content")):
                raise RuntimeError("A different post uses this issue slug; it was not changed.")
            if found.get("status") != status:
                raise RuntimeError("This issue already exists with a different status. Review it in WordPress; it was not changed.")
            result = validate_result(client, found, issue, status, me["id"])
            write_state(state_path, {**result, "state": "confirmed"})
            return {**result, "action": "already_exists"}
        if previous is not None:
            raise RuntimeError("A previous write is recorded but its post was not found. Inspect WordPress before clearing this issue's state; no duplicate was created.")
        write_state(state_path, {"state": "pending", "slug": slug})
        result = client.request("posts", {**issue, "status": status, "author": me["id"]})
        if not isinstance(result, dict) or type(result.get("id")) is not int or result["id"] <= 0:
            raise RuntimeError("WordPress did not confirm a post ID. The pending marker was retained.")
        verified = client.request(f"posts/{result['id']}?context=edit&_fields=id,slug,status,link,author,title,content")
        result = validate_result(client, verified, issue, status, me["id"])
        if raw_field(verified, "content") != issue["content"]:
            raise RuntimeError("WordPress changed the saved block content. Review the post before retrying.")
        write_state(state_path, {**result, "state": "confirmed"})
        return {**result, "action": "created"}
    finally:
        lock_path.unlink(missing_ok=True)


def raw_field(post: dict, key: str) -> str:
    value = post.get(key)
    raw = value.get("raw") if isinstance(value, dict) else None
    return raw if isinstance(raw, str) else ""


def validate_result(client: WordPressClient, result: dict, issue: dict, status: str, author: int) -> dict:
    if (not isinstance(result, dict) or type(result.get("id")) is not int or result["id"] <= 0
            or result.get("slug") != issue["slug"] or result.get("status") != status
            or result.get("author") != author or raw_field(result, "title") != issue["title"]):
        raise RuntimeError("WordPress saved unexpected post details. Inspect the issue before retrying.")
    link = result.get("link", "")
    try:
        parsed = urlsplit(link)
        base = urlsplit(client.site)
        safe = (parsed.scheme == "https" and parsed.netloc == base.netloc and not parsed.username
                and (not base.path or parsed.path.startswith(base.path.rstrip("/") + "/")))
    except (ValueError, TypeError):
        safe = False
    if not safe:
        raise RuntimeError("WordPress returned an unexpected post URL.")
    return {"id": result["id"], "slug": result["slug"], "status": status, "link": link}
