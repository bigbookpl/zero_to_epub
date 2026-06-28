"""Clean article prose HTML for EPUB."""

from __future__ import annotations

import posixpath
import re
from urllib.parse import urldefrag

from bs4 import BeautifulSoup, Comment, Tag

from utils import href_lookup_keys, normalize_url

AD_CLASS_PATTERN = re.compile(r"ad-slot", re.I)
REKLAMA_TEXT = re.compile(r"^\s*reklama\s*$", re.I)
SRCSET_ENTRY = re.compile(r"(https?://\S+?)\s+(\d+)w")


def _is_ad_node(tag: Tag) -> bool:
    if not isinstance(tag, Tag) or not tag.attrs:
        return tag.name == "iframe" if isinstance(tag, Tag) else False
    classes = " ".join(tag.get("class", []))
    if AD_CLASS_PATTERN.search(classes):
        return True
    if tag.name == "iframe":
        return True
    return False


def _unwrap_or_remove_embed(tag: Tag) -> None:
    """Replace oembed/twitter blocks with a link if possible."""
    link = tag.find("a", href=True)
    if link:
        href = link["href"]
        text = link.get_text(strip=True) or href
        tag.replace_with(BeautifulSoup(f'<p><a href="{href}">{text}</a></p>', "lxml"))
    else:
        tag.decompose()


def _best_image_src(img: Tag) -> str | None:
    src = img.get("src") or img.get("data-src")
    if src and not src.startswith("data:"):
        return normalize_url(src.strip())

    srcset = img.get("srcset", "")
    if srcset:
        best_url = None
        best_width = -1
        for match in SRCSET_ENTRY.finditer(srcset):
            url, width_str = match.group(1), match.group(2)
            width = int(width_str)
            if width > best_width:
                best_width = width
                best_url = url
        if best_url:
            return normalize_url(best_url)
    return None


def _strip_empty_paragraphs(soup: BeautifulSoup) -> None:
    for p in list(soup.find_all("p")):
        text = p.get_text(strip=True)
        if not text or REKLAMA_TEXT.match(text):
            p.decompose()


def _remove_vue_fragment_comments(root: Tag) -> None:
    for comment in root.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()


def _strip_vue_attrs(root: Tag) -> None:
    for tag in root.find_all(True):
        for attr in list(tag.attrs):
            if attr.startswith("data-v-"):
                del tag[attr]


def rewrite_internal_links(
    body_html: str,
    source_chapter_file: str,
    url_to_chapter: dict[str, str],
) -> str:
    if not body_html or not url_to_chapter:
        return body_html

    soup = BeautifulSoup(f'<div data-rewrite-root="">{body_html}</div>', "lxml")
    root = soup.find("div", attrs={"data-rewrite-root": ""})
    if not root:
        return body_html

    source_dir = posixpath.dirname(source_chapter_file) or "."

    for tag in root.find_all("a", href=True):
        href = tag["href"]
        if not href or href.startswith(("#", "mailto:", "tel:")):
            continue
        _base, fragment = urldefrag(href)
        for key in href_lookup_keys(href):
            target = url_to_chapter.get(key)
            if target:
                new_href = posixpath.relpath(target, source_dir)
                if fragment:
                    new_href = f"{new_href}#{fragment}"
                tag["href"] = new_href
                break

    return root.decode_contents()


def clean_prose_html(prose_html: str) -> tuple[str, list[str]]:
    """
    Return cleaned inner HTML and list of absolute image URLs in document order.
    """
    soup = BeautifulSoup(prose_html, "lxml")
    root = soup.find("div", class_="prose") or soup

    for tag in root.select("p.post-excerpt"):
        tag.decompose()

    for grid in root.select(".posts-grid"):
        grid.decompose()

    for tag in list(root.find_all(["script", "style", "noscript"])):
        tag.decompose()

    _remove_vue_fragment_comments(root)

    for tag in list(root.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        if _is_ad_node(tag):
            tag.decompose()
            continue
        classes = " ".join(tag.get("class", []) if tag.attrs else [])
        if "oembed" in classes or (tag.attrs and tag.get("data-oembed")):
            _unwrap_or_remove_embed(tag)

    _strip_vue_attrs(root)

    for tag in list(root.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        if tag.name == "a" and tag.get("href"):
            tag["href"] = normalize_url(tag["href"])
        elif tag.name == "img":
            src = _best_image_src(tag)
            if src:
                tag["src"] = src
            for attr in (
                "srcset",
                "data-src",
                "data-nuxt-img",
                "loading",
                "decoding",
                "fetchpriority",
                "sizes",
                "onerror",
                "height",
                "width",
                "class",
            ):
                if tag.has_attr(attr):
                    del tag[attr]

    for embed in root.select(".embed"):
        if not embed.get_text(strip=True) and not embed.find("img"):
            embed.decompose()

    _strip_empty_paragraphs(root)

    for tag in root.find_all(True):
        if tag.get("id"):
            del tag["id"]

    image_urls: list[str] = []
    for img in root.find_all("img"):
        src = img.get("src")
        if src and src not in image_urls:
            image_urls.append(src)

    inner = "".join(str(child) for child in root.children)
    return inner, image_urls
