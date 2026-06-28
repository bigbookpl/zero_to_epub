"""Tests for html_cleaner."""

from html_cleaner import clean_prose_html


def _prose(html: str) -> str:
    return f'<div class="prose">{html}</div>'


def test_removes_ad_slot_and_iframe():
    html = _prose(
        '<p>Text</p><div class="ad-slot-wrapper"><iframe src="x"></iframe></div><p>More</p>'
    )
    body, urls = clean_prose_html(html)
    assert "ad-slot" not in body
    assert "iframe" not in body
    assert "Text" in body and "More" in body
    assert urls == []


def test_strips_reklama_paragraph():
    body, _ = clean_prose_html(_prose("<p>Treść</p><p>Reklama</p>"))
    assert "Reklama" not in body
    assert "Treść" in body


def test_srcset_picks_largest_when_no_src():
    html = _prose(
        '<img srcset="https://cdn.zero.pl/small.jpg 400w, https://cdn.zero.pl/large.jpg 800w"/>'
    )
    body, urls = clean_prose_html(html)
    assert "large.jpg" in body
    assert urls == ["https://cdn.zero.pl/large.jpg"]


def test_src_prefers_src_over_srcset():
    html = _prose(
        '<img srcset="https://cdn.zero.pl/large.jpg 800w" src="https://cdn.zero.pl/fallback.jpg"/>'
    )
    body, urls = clean_prose_html(html)
    assert "fallback.jpg" in body
    assert urls == ["https://cdn.zero.pl/fallback.jpg"]


def test_minimal_fixture_clean():
    from conftest import load_fixture

    html = load_fixture("articles", "minimal-article.html")
    prose = html.split('<div class="prose">', 1)[1]
    prose = '<div class="prose">' + prose.rsplit("</div>", 1)[0] + "</div>"
    body, urls = clean_prose_html(prose)
    assert "ad-slot" not in body
    assert len(urls) == 1
    assert "test-800w.jpg" in urls[0] or "test.jpg" in urls[0]
