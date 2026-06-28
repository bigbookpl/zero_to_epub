"""Internal EPUB link index for zero.pl cross-references."""

from __future__ import annotations

from models import Article
from scraper import chapter_file_for_slug
from utils import article_url_keys


def build_internal_link_index(articles: list[Article]) -> dict[str, str]:
    index: dict[str, str] = {}
    for article in articles:
        chapter_file = chapter_file_for_slug(article.slug)
        for key in article_url_keys(article.url, article.slug):
            index[key] = chapter_file
    return index
