"""HTTP fetching and HTML parsing for zero.pl."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urljoin
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from cache import Cache
from models import Article, ArticleRef, ScrapeResult

log = logging.getLogger(__name__)

BASE_URL = "https://zero.pl"
LIST_URL = f"{BASE_URL}/najnowsze"
POSTS_API = f"{BASE_URL}/api/be/posts"
LOGO_URL = f"{BASE_URL}/images/logo.svg"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 0.5
API_PAGE_DELAY = 0.3
ARTICLE_FETCH_RETRIES = 3
ARTICLE_FETCH_RETRY_DELAY = 1.0
API_PARAMS = {
    "type": "post",
    "itemsPerPage": 18,
    "ignore_disabled_in_lists": "true",
    "cat": "-51",
}

CATEGORY_ORDER = [
    "Kraj",
    "Świat",
    "Sport",
    "Opinie",
    "Biznes",
    "Technologia",
    "Wojsko",
    "Zdrowie",
    "Kultura",
    "Nauka",
    "Moto",
]

TZ = ZoneInfo("Europe/Warsaw")


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30.0,
        follow_redirects=True,
    )


def _now() -> datetime:
    return datetime.now(TZ)


def _cutoff_for_days(days: int) -> datetime:
    today = _now().date()
    start = today - timedelta(days=days)
    return datetime(start.year, start.month, start.day, tzinfo=TZ)


def _parse_published(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _author_name(author: Any) -> str | None:
    if not author or not isinstance(author, dict):
        return None
    first = (author.get("firstname") or "").strip()
    last = (author.get("lastname") or "").strip()
    name = f"{first} {last}".strip()
    return name or None


def _category_from_member(member: dict[str, Any]) -> str:
    cat = member.get("category")
    if isinstance(cat, dict):
        title = (cat.get("title") or "").strip()
        if title:
            return title
    return "Inne"


def _category_from_card(card: Any) -> str:
    for item in card.select(".post__info__item"):
        text = item.get_text(strip=True)
        if text and text not in ("Dzisiaj", "Wczoraj") and "min" not in text.lower():
            if not any(c.isdigit() for c in text[:3]):
                return text
    return "Inne"


def ref_from_api_member(member: dict[str, Any]) -> ArticleRef | None:
    published_raw = member.get("published")
    if not published_raw:
        return None
    link = member.get("link") or urljoin(BASE_URL, member.get("path", ""))
    if not link:
        return None
    title = (member.get("title") or "").strip()
    if not title:
        return None
    return ArticleRef(
        title=title,
        url=link,
        published=_parse_published(published_raw),
        category=_category_from_member(member),
        author_hint=_author_name(member.get("author")),
    )


def fetch_refs_for_days(client: httpx.Client, days: int) -> list[ArticleRef]:
    cutoff = _cutoff_for_days(days)
    seen_urls: set[str] = set()
    refs: list[ArticleRef] = []
    page = 1

    while True:
        params = {**API_PARAMS, "page": page}
        for attempt in range(3):
            response = client.get(f"{POSTS_API}?{urlencode(params)}")
            if response.status_code < 500:
                break
            if attempt < 2:
                log.warning(
                    "API strona %d: HTTP %d, ponawiam (%d/3)...",
                    page,
                    response.status_code,
                    attempt + 2,
                )
                time.sleep(1.0 * (attempt + 1))
        response.raise_for_status()
        data = response.json()
        members = data.get("member") or []
        if not members:
            break

        stop = False
        for member in members:
            ref = ref_from_api_member(member)
            if not ref:
                continue
            if ref.published < cutoff:
                stop = True
                break
            if ref.url in seen_urls:
                continue
            seen_urls.add(ref.url)
            refs.append(ref)

        if stop:
            break

        total = data.get("totalItems", 0)
        if page * API_PARAMS["itemsPerPage"] >= total:
            break

        page += 1
        time.sleep(API_PAGE_DELAY)

    return refs


def article_slug_from_url(url: str) -> str:
    path = url.rstrip("/").split("/")[-1]
    return path or "article"


def safe_chapter_slug(slug: str) -> str:
    return re.sub(r"[^\w\-]", "_", slug)[:80]


def chapter_file_for_slug(slug: str) -> str:
    return f"chapters/{safe_chapter_slug(slug)}.xhtml"


def fetch_html(
    client: httpx.Client,
    url: str,
    cache: Cache | None = None,
) -> str:
    slug = article_slug_from_url(url)
    if cache:
        cached = cache.get_article(slug)
        if cached is not None:
            log.debug("cache hit: article %s", slug)
            return cached
    for attempt in range(ARTICLE_FETCH_RETRIES):
        try:
            response = client.get(url, headers={"Accept": "text/html"})
            break
        except httpx.RequestError as exc:
            if attempt < ARTICLE_FETCH_RETRIES - 1:
                log.warning(
                    "Błąd pobierania (%s), ponawiam (%d/%d): %s",
                    type(exc).__name__,
                    attempt + 2,
                    ARTICLE_FETCH_RETRIES,
                    url,
                )
                time.sleep(ARTICLE_FETCH_RETRY_DELAY * (attempt + 1))
                continue
            raise
    response.raise_for_status()
    html = response.text
    if cache:
        cache.put_article(slug, html)
    return html


def parse_list(html: str, limit: int | None = None) -> list[ArticleRef]:
    """Fallback: parse SSR list from /najnowsze when API is unavailable."""
    soup = BeautifulSoup(html, "lxml")
    articles: list[ArticleRef] = []
    cards = soup.select("article.post")
    if limit is not None:
        cards = cards[:limit]

    for card in cards:
        title_el = card.select_one("span.post__title")
        link_el = card.select_one('a[href^="/news/"]')
        if not title_el or not link_el:
            continue

        author_el = card.select_one(".post__author-name")
        author_hint = author_el.get_text(strip=True) if author_el else None
        if not author_hint:
            avatar = card.select_one(".post__author-avatars img")
            if avatar and avatar.get("alt"):
                author_hint = avatar["alt"].strip()

        articles.append(
            ArticleRef(
                title=title_el.get_text(strip=True),
                url=urljoin(BASE_URL, link_el["href"]),
                published=_now(),
                category=_category_from_card(card),
                author_hint=author_hint,
            )
        )

    return articles


def extract_article(html: str, url: str, ref: ArticleRef) -> Article:
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.find("h1")
    if not h1:
        raise ValueError(f"No h1 found on {url}")
    title = h1.get_text(strip=True)

    author_el = soup.select_one(".post__author-name")
    author = author_el.get_text(strip=True) if author_el else ""
    if not author:
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = meta_author["content"].strip()
    if not author:
        raise ValueError(f"No author found on {url}")

    prose = soup.select_one("div.prose")
    if not prose:
        raise ValueError(f"No div.prose found on {url}")

    excerpt_el = prose.select_one("p.post-excerpt")
    if excerpt_el:
        excerpt = excerpt_el.get_text(strip=True)
    else:
        og_desc = soup.find("meta", property="og:description")
        excerpt = og_desc["content"].strip() if og_desc and og_desc.get("content") else ""

    if not excerpt:
        raise ValueError(f"No excerpt found on {url}")

    return Article(
        title=title,
        author=author,
        excerpt=excerpt,
        prose_html=str(prose),
        url=url,
        slug=article_slug_from_url(url),
        published=ref.published,
        category=ref.category,
    )


def fetch_articles(
    client: httpx.Client,
    refs: list[ArticleRef],
    delay: float = REQUEST_DELAY,
    cache: Cache | None = None,
) -> list[Article]:
    articles: list[Article] = []
    for i, ref in enumerate(refs, 1):
        if i > 1:
            time.sleep(delay)
        try:
            html = fetch_html(client, ref.url, cache=cache)
            articles.append(extract_article(html, ref.url, ref))
        except httpx.RequestError:
            log.warning("Pominięto (błąd sieci): %s", ref.url)
            continue
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.warning("Pominięto (404): %s", ref.url)
                continue
            raise
    return articles


def scrape_for_days(days: int = 7, cache: Cache | None = None) -> ScrapeResult:
    generated_at = _now()
    with _client() as client:
        refs = fetch_refs_for_days(client, days)
        if not refs:
            raise ValueError(
                f"Brak artykułów z ostatnich {days} dni. Spróbuj większej wartości --days."
            )
        articles = fetch_articles(client, refs, cache=cache)
        published_dates = [r.published for r in refs]
        return ScrapeResult(
            articles=articles,
            date_from=min(published_dates),
            date_to=max(published_dates),
            generated_at=generated_at,
        )
