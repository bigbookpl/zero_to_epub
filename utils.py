"""Shared helpers for dates, XML escaping, and article URL keys."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

from scraper import TZ

BASE_URL = "https://zero.pl"
ZERO_HOSTS = frozenset({"zero.pl", "www.zero.pl"})


def normalize_url(url: str, base: str = BASE_URL) -> str:
    if not url or url.startswith(("data:", "javascript:", "#")):
        return url
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return "https:" + url
    return urljoin(base, url)


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_date_pl(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%d.%m.%Y")


def _dedupe_keys(keys: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def _collect_news_keys(
    path: str,
    *,
    full_url: str | None = None,
    slug: str | None = None,
) -> list[str]:
    path = (path or "").rstrip("/")
    if not path.startswith("/news/"):
        if slug:
            path = f"/news/{slug}"
        else:
            return []
    keys: list[str] = []
    if full_url:
        keys.extend([full_url, full_url.rstrip("/")])
    keys.append(path)
    keys.extend(
        [
            f"https://zero.pl{path}",
            f"https://zero.pl{path}/",
            f"https://www.zero.pl{path}",
            f"https://www.zero.pl{path}/",
        ]
    )
    return _dedupe_keys(keys)


def article_url_keys(url: str, slug: str) -> list[str]:
    """Keys used to match hrefs pointing at an article in this EPUB."""
    parsed = urlparse(url)
    path = (parsed.path or f"/news/{slug}").rstrip("/")
    return _collect_news_keys(path, full_url=url, slug=slug)


def href_lookup_keys(href: str, base_url: str = BASE_URL) -> list[str]:
    """Keys for matching <a href> in cleaned prose HTML."""
    normalized = normalize_url(href, base_url)
    base, _fragment = urldefrag(normalized)
    parsed = urlparse(base)
    if parsed.netloc and parsed.netloc not in ZERO_HOSTS:
        return []
    path = (parsed.path or "").rstrip("/")
    if not path.startswith("/news/"):
        return []
    full = base if parsed.scheme and parsed.netloc else None
    return _collect_news_keys(path, full_url=full)
