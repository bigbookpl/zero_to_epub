"""Tests for scraper (offline)."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import httpx
import pytest

from conftest import load_fixture
from models import ArticleRef
from scraper import (
    POSTS_API,
    article_slug_from_url,
    extract_article,
    fetch_articles,
    fetch_html,
    fetch_refs_for_days,
    ref_from_api_member,
    safe_chapter_slug,
)

TZ = ZoneInfo("Europe/Warsaw")


def test_article_slug_from_url():
    assert article_slug_from_url("https://zero.pl/news/foo-bar/") == "foo-bar"


def test_safe_chapter_slug():
    assert safe_chapter_slug("foo/bar!") == "foo_bar_"


def test_ref_from_api_member_ok():
    member = {
        "title": "Tytuł",
        "link": "https://zero.pl/news/x",
        "published": "2026-06-01T12:00:00+02:00",
        "category": {"title": "Kraj"},
        "author": {"firstname": "Jan", "lastname": "Kowalski"},
    }
    ref = ref_from_api_member(member)
    assert ref is not None
    assert ref.title == "Tytuł"
    assert ref.category == "Kraj"
    assert ref.author_hint == "Jan Kowalski"


def test_ref_from_api_member_missing_published():
    assert ref_from_api_member({"title": "X", "link": "https://zero.pl/news/x"}) is None


def test_extract_article_minimal():
    html = load_fixture("articles", "minimal-article.html")
    ref = ArticleRef(
        title="Test",
        url="https://zero.pl/news/minimal-article",
        published=datetime(2026, 6, 1, tzinfo=TZ),
        category="Kraj",
    )
    article = extract_article(html, ref.url, ref)
    assert article.title == "Testowy artykuł"
    assert article.author == "Jan Kowalski"
    assert article.excerpt == "To jest lead artykułu testowego."
    assert "div.prose" in article.prose_html or "prose" in article.prose_html


def test_extract_article_sample_fixture():
    html = load_fixture("articles", "sample-article.html")
    ref = ArticleRef(
        title="Placeholder",
        url="https://zero.pl/news/sample-article",
        published=datetime(2026, 6, 4, tzinfo=TZ),
        category="Sport",
    )
    article = extract_article(html, ref.url, ref)
    assert article.author
    assert article.excerpt
    assert len(article.title) > 10


@patch("scraper.time.sleep")
def test_fetch_refs_for_days_pagination_and_cutoff(mock_sleep):
    page1 = json.loads(load_fixture("api", "posts_page1.json"))
    page2 = json.loads(load_fixture("api", "posts_page2.json"))

    responses = {
        1: page1,
        2: page2,
    }

    def fake_get(url, **kwargs):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=responses.get(page, {"member": [], "totalItems": 0}))
        return resp

    client = MagicMock()
    client.get = fake_get

    with patch("scraper._cutoff_for_days") as cutoff:
        cutoff.return_value = datetime(2026, 6, 1, tzinfo=TZ)
        refs = fetch_refs_for_days(client, days=7)

    urls = [r.url for r in refs]
    assert urls.count("https://zero.pl/news/fresh-article") == 1
    assert "https://zero.pl/news/old-article" not in urls
    assert len(refs) == 1


@patch("scraper.time.sleep")
def test_fetch_refs_for_days_retries_after_timeout(mock_sleep):
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"member": [], "totalItems": 0})

    timeout = httpx.ReadTimeout(
        "The read operation timed out",
        request=httpx.Request("GET", POSTS_API),
    )
    client = MagicMock()
    client.get = MagicMock(side_effect=[timeout, response])

    refs = fetch_refs_for_days(client, days=7)

    assert refs == []
    assert client.get.call_count == 2
    mock_sleep.assert_called_once()


@patch("scraper.time.sleep")
def test_fetch_html_retries_after_timeout(mock_sleep):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.text = "<html>ok</html>"

    timeout = httpx.ReadTimeout(
        "The read operation timed out",
        request=httpx.Request("GET", "https://zero.pl/news/retry-article"),
    )
    client = MagicMock()
    client.get = MagicMock(side_effect=[timeout, response])

    html = fetch_html(client, "https://zero.pl/news/retry-article")

    assert html == "<html>ok</html>"
    assert client.get.call_count == 2
    mock_sleep.assert_called_once()


def test_fetch_articles_skips_request_errors():
    ref_timeout = ArticleRef(
        title="Timeout",
        url="https://zero.pl/news/timeout",
        published=datetime(2026, 6, 1, tzinfo=TZ),
        category="Kraj",
    )
    ref_ok = ArticleRef(
        title="OK",
        url="https://zero.pl/news/ok",
        published=datetime(2026, 6, 1, tzinfo=TZ),
        category="Kraj",
    )
    refs = [ref_timeout, ref_ok]

    timeout = httpx.ReadTimeout(
        "The read operation timed out",
        request=httpx.Request("GET", "https://zero.pl/news/timeout"),
    )
    article = MagicMock()

    with patch("scraper.fetch_html", side_effect=[timeout, "<html>ok</html>"]), patch(
        "scraper.extract_article", return_value=article
    ) as extract:
        articles = fetch_articles(MagicMock(), refs, delay=0.0)

    assert articles == [article]
    extract.assert_called_once_with("<html>ok</html>", ref_ok.url, ref_ok)
