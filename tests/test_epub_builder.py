"""Tests for epub_builder grouping and titles."""

from datetime import datetime
from zoneinfo import ZoneInfo

from epub_builder import book_title, group_and_sort_articles, group_by_author
from epub_html import author_slug
from models import Article, EpubMeta

TZ = ZoneInfo("Europe/Warsaw")


def _article(**kwargs) -> Article:
    defaults = dict(
        title="T",
        author="Autor",
        excerpt="Lead",
        prose_html='<div class="prose"><p>x</p></div>',
        url="https://zero.pl/news/x",
        slug="x",
        published=datetime(2026, 6, 1, tzinfo=TZ),
        category="Inne",
    )
    defaults.update(kwargs)
    return Article(**defaults)


def test_group_and_sort_articles_category_order():
    articles = [
        _article(category="Sport", published=datetime(2026, 6, 2, tzinfo=TZ), slug="s2"),
        _article(category="Kraj", published=datetime(2026, 6, 1, tzinfo=TZ), slug="k1"),
        _article(category="Kraj", published=datetime(2026, 6, 3, tzinfo=TZ), slug="k3"),
    ]
    grouped = group_and_sort_articles(articles)
    assert [g[0] for g in grouped] == ["Kraj", "Sport"]
    kraj_slugs = [a.slug for a in grouped[0][1]]
    assert kraj_slugs == ["k1", "k3"]


def test_group_by_author_alphabetical():
    articles = [
        _article(author="Żurek", slug="z"),
        _article(author="Adam", slug="a"),
    ]
    groups = group_by_author(articles)
    assert [name for name, _ in groups] == ["Adam", "Żurek"]


def test_author_slug_polish_chars():
    assert author_slug("Łukasz Wiśniewski") == "author-ukasz-wisniewski"


def test_book_title():
    meta = EpubMeta(
        date_from=datetime(2026, 5, 28, tzinfo=TZ),
        date_to=datetime(2026, 6, 4, tzinfo=TZ),
        generated_at=datetime(2026, 6, 4, tzinfo=TZ),
    )
    assert book_title(meta) == "Zero.pl — 28.05.2026 – 04.06.2026"
