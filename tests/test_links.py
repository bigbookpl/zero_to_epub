"""Tests for internal article link rewriting."""

from datetime import datetime
from zoneinfo import ZoneInfo

from epub_links import build_internal_link_index
from html_cleaner import rewrite_internal_links
from models import Article
from scraper import chapter_file_for_slug

TZ = ZoneInfo("Europe/Warsaw")


def _article(slug: str, url: str | None = None) -> Article:
    return Article(
        title=slug,
        author="Autor",
        excerpt="Lead",
        prose_html="<p>x</p>",
        url=url or f"https://zero.pl/news/{slug}",
        slug=slug,
        published=datetime(2026, 6, 1, tzinfo=TZ),
        category="Kraj",
    )


def test_rewrite_to_chapter_relative_path():
    index = build_internal_link_index([_article("target-article")])
    html = '<p><a href="https://zero.pl/news/target-article">Link</a></p>'
    out = rewrite_internal_links(
        html, "chapters/source-article.xhtml", index
    )
    assert 'href="target-article.xhtml"' in out
    assert "https://zero.pl" not in out


def test_external_article_unchanged():
    index = build_internal_link_index([_article("in-book")])
    html = '<p><a href="https://zero.pl/news/not-in-book">Link</a></p>'
    out = rewrite_internal_links(html, "chapters/foo.xhtml", index)
    assert 'href="https://zero.pl/news/not-in-book"' in out


def test_fragment_preserved():
    index = build_internal_link_index([_article("target")])
    html = '<p><a href="https://zero.pl/news/target#section">Link</a></p>'
    out = rewrite_internal_links(html, "chapters/foo.xhtml", index)
    assert 'href="target.xhtml#section"' in out


def test_chapter_file_matches_slug():
    assert chapter_file_for_slug("foo-bar") == "chapters/foo-bar.xhtml"


def test_www_zero_pl_rewritten():
    index = build_internal_link_index([_article("target-article")])
    html = '<p><a href="https://www.zero.pl/news/target-article/">Link</a></p>'
    out = rewrite_internal_links(html, "chapters/foo.xhtml", index)
    assert 'href="target-article.xhtml"' in out


def test_relative_news_path_rewritten():
    index = build_internal_link_index([_article("target-article")])
    html = '<p><a href="/news/target-article">Link</a></p>'
    out = rewrite_internal_links(html, "chapters/foo.xhtml", index)
    assert 'href="target-article.xhtml"' in out
