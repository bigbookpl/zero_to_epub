"""Build EPUB from scraped articles."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

import httpx
from ebooklib import epub
from ebooklib.epub import Section

from cache import Cache
from cover_builder import build_cover_bytes
from epub_html import (
    CHAPTER_CSS,
    TITLE_PAGE_CSS,
    build_authors_index_page,
    chapter_bytes,
    write_epub,
)
from epub_links import build_internal_link_index
from html_cleaner import clean_prose_html, rewrite_internal_links
from image_processor import process_for_ereader
from models import Article, CleanedArticle, EpubMeta
from scraper import CATEGORY_ORDER, USER_AGENT, chapter_file_for_slug
from utils import escape_xml, format_date_pl

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def book_title(meta: EpubMeta) -> str:
    return (
        f"Zero.pl — {format_date_pl(meta.date_from)} – "
        f"{format_date_pl(meta.date_to)}"
    )


def _category_sort_key(category: str) -> tuple[int, str]:
    try:
        order = CATEGORY_ORDER.index(category)
    except ValueError:
        order = len(CATEGORY_ORDER)
    return (order, category)


def group_by_author(
    articles: list[Article],
) -> list[tuple[str, list[Article]]]:
    by_author: dict[str, list[Article]] = {}
    for article in articles:
        name = article.author.strip() or "Nieznany autor"
        by_author.setdefault(name, []).append(article)

    for group in by_author.values():
        group.sort(key=lambda a: a.published)

    return sorted(by_author.items(), key=lambda item: item[0].casefold())


def group_and_sort_articles(
    articles: list[Article],
) -> list[tuple[str, list[Article]]]:
    by_category: dict[str, list[Article]] = {}
    for article in articles:
        by_category.setdefault(article.category, []).append(article)

    for group in by_category.values():
        group.sort(key=lambda a: a.published)

    sorted_categories = sorted(by_category.keys(), key=_category_sort_key)
    return [(cat, by_category[cat]) for cat in sorted_categories]


def _get_image_bytes(
    client: httpx.Client,
    url: str,
    cache: Cache | None,
) -> bytes | None:
    if cache:
        cached = cache.get_image(url)
        if cached is not None:
            log.debug("cache hit: image %s", url[:60])
            return cached
    response = client.get(url)
    response.raise_for_status()
    data = response.content
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large ({len(data)} bytes): {url}")
    processed = process_for_ereader(data)
    if cache:
        cache.put_image(url, processed)
    return processed


def prepare_articles(articles: list[Article]) -> list[CleanedArticle]:
    cleaned: list[CleanedArticle] = []
    for article in articles:
        body_html, image_urls = clean_prose_html(article.prose_html)
        cleaned.append(
            CleanedArticle(
                title=article.title,
                author=article.author,
                excerpt=article.excerpt,
                body_html=body_html,
                url=article.url,
                slug=article.slug,
                published=article.published,
                category=article.category,
                image_urls=image_urls,
            )
        )
    return cleaned


def _embed_images(
    body_html: str,
    image_urls: list[str],
    slug: str,
    client: httpx.Client,
    book: epub.EpubBook,
    cache: Cache | None,
) -> str:
    result = body_html
    for idx, url in enumerate(image_urls):
        try:
            data = _get_image_bytes(client, url, cache)
            if not data:
                continue
        except Exception:
            continue
        epub_path = f"images/{slug}_{idx}.jpg"
        chapter_ref = f"../{epub_path}"
        item = epub.EpubImage()
        item.file_name = epub_path
        item.media_type = "image/jpeg"
        item.content = data
        book.add_item(item)
        result = result.replace(url, chapter_ref, 1)
    return result


def _build_chapter(
    article: CleanedArticle,
    body_html: str,
    book: epub.EpubBook,
) -> epub.EpubHtml:
    chapter = epub.EpubHtml(
        title=article.title,
        file_name=chapter_file_for_slug(article.slug),
        lang="pl",
    )
    chapter.content = chapter_bytes(
        title=escape_xml(article.title),
        author=article.author,
        excerpt=escape_xml(article.excerpt),
        body_html=body_html,
    )
    chapter.published = article.published
    book.add_item(chapter)
    return chapter


def build_epub(
    articles: list[Article],
    output_path: str,
    meta: EpubMeta,
    cache: Cache | None = None,
    *,
    book_identifier: str | None = None,
) -> None:
    grouped = group_and_sort_articles(articles)
    sorted_articles = [a for _, group in grouped for a in group]
    cleaned_list = prepare_articles(sorted_articles)
    cleaned_by_slug = {c.slug: c for c in cleaned_list}

    title = book_title(meta)
    period = (
        f"{format_date_pl(meta.date_from)} – {format_date_pl(meta.date_to)}"
    )

    book = epub.EpubBook()
    book.set_identifier(book_identifier or f"zero.pl-{uuid4()}")
    book.set_title(title)
    book.set_language("pl")
    book.add_author("Zero.pl")

    nav_css = epub.EpubItem(
        uid="nav_css",
        file_name="style/nav.css",
        media_type="text/css",
        content=CHAPTER_CSS.encode("utf-8"),
    )
    book.add_item(nav_css)

    toc: list = []
    spine_chapters: list[epub.EpubHtml] = []

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        cover_page = epub.EpubHtml(
            title="Okładka",
            file_name="cover.xhtml",
            lang="pl",
        )
        cover_page.content = build_cover_bytes(
            client,
            meta.date_from,
            meta.date_to,
            meta.generated_at,
            len(articles),
        )
        book.add_item(cover_page)

        title_page = epub.EpubHtml(
            title="Strona tytułowa",
            file_name="title.xhtml",
            lang="pl",
        )
        title_body = (
            f"<p>{escape_xml(period)}</p>"
            f"<p>{len(articles)} artykułów z zero.pl</p>"
            f"<p>Wygenerowano: {escape_xml(format_date_pl(meta.generated_at))}</p>"
        )
        title_page.content = chapter_bytes(
            title=escape_xml(title),
            author="",
            excerpt="",
            body_html=title_body,
            extra_head=f'<style type="text/css">{TITLE_PAGE_CSS}</style>',
            wrap_title=True,
            stylesheet=None,
        )
        book.add_item(title_page)

        chapter_by_slug: dict[str, epub.EpubHtml] = {}
        link_index = build_internal_link_index(sorted_articles)

        for category, group in grouped:
            category_chapters: list[epub.EpubHtml] = []
            for article in group:
                cleaned = cleaned_by_slug[article.slug]
                body_html = rewrite_internal_links(
                    cleaned.body_html,
                    chapter_file_for_slug(cleaned.slug),
                    link_index,
                )
                if cleaned.image_urls:
                    body_html = _embed_images(
                        body_html,
                        cleaned.image_urls,
                        cleaned.slug,
                        client,
                        book,
                        cache,
                    )
                chapter = _build_chapter(cleaned, body_html, book)
                chapter_by_slug[article.slug] = chapter
                category_chapters.append(chapter)
                spine_chapters.append(chapter)

            if category_chapters:
                toc.append((Section(category), category_chapters))

        author_groups = group_by_author(sorted_articles)

        authors_page = epub.EpubHtml(
            title="Indeks autorów",
            file_name="authors.xhtml",
            lang="pl",
        )
        authors_page.content = build_authors_index_page(
            author_groups, chapter_by_slug
        )
        book.add_item(authors_page)
        toc.append((Section("Indeks autorów"), [authors_page]))

    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", cover_page, title_page, *spine_chapters, authors_page]
    book.add_metadata(None, "meta", "", {"name": "cover", "content": "cover.xhtml"})

    write_epub(output_path, book)
