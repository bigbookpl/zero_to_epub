"""Regression snapshots for HTML cleaning and EPUB output."""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx
import pytest

from conftest import load_fixture, load_fixture_bytes
from epub_builder import build_epub
from epub_html import chapter_bytes
from epub_links import build_internal_link_index
from html_cleaner import clean_prose_html, rewrite_internal_links
from models import Article, EpubMeta

TZ = ZoneInfo("Europe/Warsaw")


@pytest.fixture
def minimal_prose_fragment():
    html = load_fixture("articles", "minimal-article.html")
    inner = html.split('<div class="prose">', 1)[1]
    return '<div class="prose">' + inner.rsplit("</div>", 1)[0] + "</div>"


def test_clean_prose_html_regression(minimal_prose_fragment, data_regression):
    body, image_urls = clean_prose_html(minimal_prose_fragment)
    data_regression.check({"body_html": body, "image_urls": image_urls})


def test_rewrite_links_roundtrip_regression(minimal_prose_fragment, data_regression):
    body, _ = clean_prose_html(minimal_prose_fragment)
    articles = [
        Article(
            title="Inny",
            author="A",
            excerpt="L",
            prose_html="<p>x</p>",
            url="https://zero.pl/news/other-article",
            slug="other-article",
            published=datetime(2026, 6, 1, tzinfo=TZ),
            category="Kraj",
        ),
        Article(
            title="Self",
            author="B",
            excerpt="L",
            prose_html="<p>x</p>",
            url="https://zero.pl/news/minimal-article",
            slug="minimal-article",
            published=datetime(2026, 6, 2, tzinfo=TZ),
            category="Kraj",
        ),
    ]
    index = build_internal_link_index(articles)
    out = rewrite_internal_links(
        body, "chapters/minimal-article.xhtml", index
    )
    data_regression.check({"body_html": out})


def test_chapter_xhtml_regression(data_regression):
    raw = chapter_bytes(
        title="Test &amp; tytuł",
        author="Jan Kowalski",
        excerpt="Lead \"cytat\"",
        body_html="<p>Treść</p>",
    ).decode("utf-8")
    data_regression.check({"xhtml": raw})


LOGO = load_fixture("logo.svg")
IMAGE = load_fixture_bytes("images", "sample.png")


def _mock_get(self, url, **kwargs):
    from unittest.mock import MagicMock

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if "logo.svg" in url:
        resp.text = LOGO
        resp.content = LOGO.encode()
    else:
        resp.content = IMAGE
        resp.text = ""
    return resp


def test_minimal_epub_regression(tmp_path, data_regression):
    meta = EpubMeta(
        date_from=datetime(2026, 6, 1, tzinfo=TZ),
        date_to=datetime(2026, 6, 2, tzinfo=TZ),
        generated_at=datetime(2026, 6, 4, tzinfo=TZ),
    )
    article = Article(
        title="Regresja",
        author="Autor Test",
        excerpt="Lead regresji",
        prose_html='<div class="prose"><p class="post-excerpt">Lead regresji</p><p>Stała treść.</p></div>',
        url="https://zero.pl/news/regression-article",
        slug="regression-article",
        published=datetime(2026, 6, 1, tzinfo=TZ),
        category="Kraj",
    )
    out = tmp_path / "regression.epub"
    with patch.object(httpx.Client, "get", _mock_get):
        build_epub(
            [article],
            str(out),
            meta,
            book_identifier="zero.pl-regression-test",
        )

    with zipfile.ZipFile(out) as zf:
        names = sorted(zf.namelist())
    data_regression.check({"zip_entries": names})
