"""Integration-style EPUB build tests (offline, mocked HTTP)."""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx

from conftest import load_fixture, load_fixture_bytes
from epub_builder import build_epub
from models import Article, EpubMeta

TZ = ZoneInfo("Europe/Warsaw")
LOGO = load_fixture("logo.svg")
IMAGE = load_fixture_bytes("images", "sample.png")


def _articles() -> list[Article]:
    prose = '<div class="prose"><p class="post-excerpt">Lead A</p><p>Body A</p></div>'
    prose_b = '<div class="prose"><p class="post-excerpt">Lead B</p><p>Body B</p></div>'
    return [
        Article(
            title="Artykuł A",
            author="Anna Nowak",
            excerpt="Lead A",
            prose_html=prose,
            url="https://zero.pl/news/article-a",
            slug="article-a",
            published=datetime(2026, 6, 1, tzinfo=TZ),
            category="Kraj",
        ),
        Article(
            title="Artykuł B",
            author="Piotr Zieliński",
            excerpt="Lead B",
            prose_html=prose_b,
            url="https://zero.pl/news/article-b",
            slug="article-b",
            published=datetime(2026, 6, 2, tzinfo=TZ),
            category="Świat",
        ),
    ]


def _mock_get(self, url, **kwargs):
    from unittest.mock import MagicMock

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if "logo.svg" in url:
        resp.text = LOGO
        resp.content = LOGO.encode()
    elif "cdn.zero.pl" in url or url.endswith(".jpg") or url.endswith(".png"):
        resp.content = IMAGE
        resp.text = ""
    else:
        raise AssertionError(f"Unexpected URL: {url}")
    return resp


def test_build_epub_structure(tmp_path):
    meta = EpubMeta(
        date_from=datetime(2026, 6, 1, tzinfo=TZ),
        date_to=datetime(2026, 6, 2, tzinfo=TZ),
        generated_at=datetime(2026, 6, 4, tzinfo=TZ),
    )
    out = tmp_path / "test.epub"
    with patch.object(httpx.Client, "get", _mock_get):
        build_epub(
            _articles(),
            str(out),
            meta,
            book_identifier="zero.pl-test-fixed-id",
        )

    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        chapters = [n for n in names if n.startswith("EPUB/chapters/") or n.startswith("chapters/")]
        assert any("article-a" in n for n in chapters)
        assert any("article-b" in n for n in chapters)
