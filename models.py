"""Data models for scraping and EPUB building."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ArticleRef:
    title: str
    url: str
    published: datetime
    category: str
    author_hint: str | None = None


@dataclass
class Article:
    title: str
    author: str
    excerpt: str
    prose_html: str
    url: str
    slug: str
    published: datetime
    category: str


@dataclass
class ScrapeResult:
    articles: list[Article]
    date_from: datetime
    date_to: datetime
    generated_at: datetime


@dataclass
class EpubMeta:
    date_from: datetime
    date_to: datetime
    generated_at: datetime


@dataclass
class CleanedArticle:
    title: str
    author: str
    excerpt: str
    body_html: str
    url: str
    slug: str
    published: datetime
    category: str
    image_urls: list[str]
