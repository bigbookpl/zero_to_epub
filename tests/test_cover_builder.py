"""Tests for cover_builder."""

from datetime import datetime
from zoneinfo import ZoneInfo

from conftest import load_fixture
from cover_builder import adapt_logo_for_dark_background, build_cover_xhtml

TZ = ZoneInfo("Europe/Warsaw")


def test_adapt_logo_for_dark_background():
    svg = '<svg><text fill="black">Z</text></svg>'
    assert 'fill="white"' in adapt_logo_for_dark_background(svg)


def test_cover_plural_forms():
    dt = datetime(2026, 6, 4, tzinfo=TZ)
    html_one = build_cover_xhtml("<svg/>", dt, dt, dt, 1).decode()
    html_few = build_cover_xhtml("<svg/>", dt, dt, dt, 3).decode()
    html_many = build_cover_xhtml("<svg/>", dt, dt, dt, 5).decode()
    assert "1 artykuł" in html_one
    assert "3 artykuły" in html_few
    assert "5 artykułów" in html_many


def test_build_cover_bytes_mocked(patch_httpx_get):
    from cover_builder import build_cover_bytes

    logo = load_fixture("logo.svg")
    with patch_httpx_get({"logo": (200, logo, "image/svg+xml")}):
        import httpx

        with httpx.Client() as client:
            out = build_cover_bytes(
                client,
                datetime(2026, 6, 1, tzinfo=TZ),
                datetime(2026, 6, 4, tzinfo=TZ),
                datetime(2026, 6, 4, tzinfo=TZ),
                2,
            )
    assert b"Zero.pl" in out
    assert "artykuły".encode() in out
