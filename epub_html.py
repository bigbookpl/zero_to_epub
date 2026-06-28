"""XHTML templates and EPUB nav rendering."""

from __future__ import annotations

import posixpath
import re
import unicodedata
from datetime import datetime

from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubNav, EpubWriter

from models import Article
from utils import escape_xml, format_date_pl

XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
XHTML_ROOT = (
    f'<html xmlns="{XHTML_NS}" xmlns:epub="{EPUB_NS}" '
    f'lang="pl" xml:lang="pl">'
)

CHAPTER_CSS = """
body { font-family: Georgia, serif; line-height: 1.6; margin: 1em; }
h1 { font-size: 1.5em; margin-bottom: 0.5em; }
.author { color: #555; font-size: 0.95em; margin-bottom: 1em; }
.author a { color: #0066cc; text-decoration: none; }
.excerpt { font-style: italic; color: #333; margin-bottom: 1.5em; border-left: 3px solid #ccc; padding-left: 1em; }
.article-body p { margin: 0.8em 0; }
.article-body img { max-width: 100%; height: auto; }
.article-body ul, .article-body ol { margin: 0.8em 0; padding-left: 1.5em; }
.article-body blockquote { margin: 1em; padding-left: 1em; border-left: 3px solid #999; color: #444; }
.article-body a { color: #0066cc; }
.article-body figcaption { font-size: 0.85em; color: #666; }
"""

TITLE_PAGE_CSS = """
body { font-family: Georgia, serif; text-align: center; margin-top: 25%; }
h1 { font-size: 1.6em; }
p { color: #555; line-height: 1.6; }
"""

NAV_CSS = """
nav { font-family: Georgia, serif; }
nav#toc ol.categories { list-style: none; padding: 0; margin: 0; }
nav#toc li.category-item { margin: 0.8em 0; }
nav#toc span.category-label { font-weight: bold; display: block; margin-bottom: 0.25em; }
nav#toc ol.articles { list-style-type: disc; padding-left: 1.6em; margin: 0.2em 0 0.5em 0.4em; }
nav#toc ol.articles li { margin: 0.45em 0; display: list-item; }
nav#toc ol.articles a { display: block; line-height: 1.4; text-decoration: none; color: #0066cc; }
nav#toc em.date { font-style: italic; color: #666; font-size: 0.88em; }
nav#toc li.authors-index { margin-top: 1em; padding-top: 0.6em; border-top: 1px solid #ccc; }
"""

AUTHORS_INDEX_CSS = """
body { font-family: Georgia, serif; line-height: 1.5; margin: 1em; }
h1 { font-size: 1.4em; }
.author-group { margin: 1.2em 0; }
.author-group h2 { font-size: 1.1em; margin: 0 0 0.4em; }
.author-group ul { list-style-type: disc; padding-left: 1.5em; margin: 0.3em 0; }
.author-group li { margin: 0.4em 0; }
.author-group a { color: #0066cc; text-decoration: none; }
.author-group em.date { font-style: italic; color: #666; font-size: 0.88em; }
"""


def author_slug(author: str) -> str:
    """ASCII-only fragment id (Kindle / XML-safe)."""
    decomposed = unicodedata.normalize("NFKD", author)
    ascii_name = decomposed.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^\w\s\-]", "", ascii_name.lower())
    normalized = re.sub(r"[\s_]+", "-", normalized.strip())
    return f"author-{(normalized[:80] if normalized else 'nieznany')}"


def nav_href(nav_file_name: str, chapter_file_name: str) -> str:
    return posixpath.relpath(chapter_file_name, posixpath.dirname(nav_file_name))


def _article_link_html(chapter: EpubHtml, base_file: str) -> str:
    href = escape_xml(nav_href(base_file, chapter.file_name))
    title = escape_xml(chapter.title)
    published = getattr(chapter, "published", None)
    date_html = (
        f' <em class="date">{escape_xml(format_date_pl(published))}</em>'
        if published
        else ""
    )
    return f'<li><a href="{href}">{title}{date_html}</a></li>'


def _render_category_toc(items: tuple, nav_file_name: str) -> str:
    parts = ['<ol class="categories">']
    for item in items:
        if isinstance(item, (tuple, list)):
            section, children = item[0], item[1]
            label = escape_xml(section.title)
            parts.append(
                f'<li class="category-item"><span class="category-label">{label}</span>'
            )
            parts.append('<ol class="articles">')
            for child in children:
                if isinstance(child, EpubHtml):
                    parts.append(_article_link_html(child, nav_file_name))
            parts.append("</ol></li>")
    parts.append("</ol>")
    return "".join(parts)


def build_authors_index_page(
    author_groups: list[tuple[str, list[Article]]],
    chapter_by_slug: dict[str, epub.EpubHtml],
) -> bytes:
    sections: list[str] = []
    for author, group in author_groups:
        slug = author_slug(author)
        name = escape_xml(author)
        links = []
        for article in group:
            chapter = chapter_by_slug.get(article.slug)
            if not chapter:
                continue
            href = escape_xml(nav_href("authors.xhtml", chapter.file_name))
            title = escape_xml(article.title)
            date_html = (
                f' <em class="date">{escape_xml(format_date_pl(article.published))}</em>'
            )
            links.append(f'<li><a href="{href}">{title}{date_html}</a></li>')
        sections.append(
            f'<div class="author-group" id="{slug}">'
            f"<h2>{name}</h2>"
            f'<ul>{"".join(links)}</ul>'
            f"</div>"
        )

    html = f"""<!DOCTYPE html>
{XHTML_ROOT}
<head>
  <meta charset="utf-8"/>
  <title>Indeks autorów</title>
  <style type="text/css">{AUTHORS_INDEX_CSS}</style>
</head>
<body>
  <h1>Indeks autorów</h1>
  {"".join(sections)}
</body>
</html>"""
    return html.encode("utf-8")


def build_nav_content(nav_item: EpubNav, book: epub.EpubBook) -> bytes:
    heading = escape_xml(nav_item.title or book.title)
    toc_body = _render_category_toc(book.toc, nav_item.file_name)
    html = f"""<!DOCTYPE html>
{XHTML_ROOT}
<head>
  <meta charset="utf-8"/>
  <title>{heading}</title>
  <style type="text/css">{NAV_CSS}</style>
</head>
<body>
  <nav epub:type="toc" id="toc" role="doc-toc">
    <h2>{heading}</h2>
    {toc_body}
  </nav>
</body>
</html>"""
    return html.encode("utf-8")


class ZeroEpubWriter(EpubWriter):
    """EPUB writer with TOC entries showing publication dates in italics."""

    def _get_nav(self, item: EpubNav) -> bytes:
        return build_nav_content(item, self.book)


def write_epub(path: str, book: epub.EpubBook) -> None:
    writer = ZeroEpubWriter(path, book, {})
    writer.process()
    writer.write()


def author_paragraph(author: str) -> str:
    if not author:
        return ""
    slug = author_slug(author)
    name = escape_xml(author)
    return (
        f'<p class="author"><a href="../authors.xhtml#{slug}">{name}</a></p>'
    )


def chapter_bytes(
    title: str,
    author: str,
    excerpt: str,
    body_html: str,
    extra_head: str = "",
    wrap_title: bool = False,
    stylesheet: str | None = "../style/nav.css",
    author_linked: bool = True,
) -> bytes:
    if wrap_title:
        body_parts = [f"<h1>{title}</h1>", body_html]
    else:
        author_block = author_paragraph(author) if author_linked else (
            f'<p class="author">{author}</p>' if author else ""
        )
        body_parts = [
            f"<h1>{title}</h1>",
            author_block,
            f'<p class="excerpt">{excerpt}</p>' if excerpt else "",
            f'<div class="article-body">{body_html}</div>',
        ]
    body = "\n  ".join(p for p in body_parts if p)
    css_link = (
        f'  <link rel="stylesheet" type="text/css" href="{stylesheet}"/>\n'
        if stylesheet
        else ""
    )
    html = f"""<!DOCTYPE html>
{XHTML_ROOT}
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
{css_link}{extra_head}
</head>
<body>
  {body}
</body>
</html>"""
    return html.encode("utf-8")
