"""Tests for utils module."""

from datetime import datetime
from zoneinfo import ZoneInfo

from utils import article_url_keys, escape_xml, format_date_pl, href_lookup_keys

TZ = ZoneInfo("Europe/Warsaw")


def test_escape_xml():
    assert escape_xml('a & b <c> "d"') == "a &amp; b &lt;c&gt; &quot;d&quot;"


def test_format_date_pl():
    dt = datetime(2026, 6, 4, 15, 30, tzinfo=TZ)
    assert format_date_pl(dt) == "04.06.2026"


def test_article_url_keys_trailing_slash():
    keys = article_url_keys("https://zero.pl/news/foo/", "foo")
    assert "https://zero.pl/news/foo" in keys
    assert "https://www.zero.pl/news/foo/" in keys


def test_href_lookup_keys_relative_path():
    keys = href_lookup_keys("/news/target-article")
    assert "https://zero.pl/news/target-article" in keys


def test_href_lookup_keys_external_empty():
    assert href_lookup_keys("https://example.com/news/foo") == []
