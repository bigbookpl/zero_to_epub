"""Tests for disk cache."""

from cache import Cache


def test_article_roundtrip(tmp_path):
    cache = Cache(root=tmp_path / "cache", enabled=True)
    cache.put_article("slug-a", "<html>ok</html>")
    assert cache.get_article("slug-a") == "<html>ok</html>"
    assert cache.get_article("missing") is None


def test_image_roundtrip(tmp_path):
    cache = Cache(root=tmp_path / "cache", enabled=True)
    data = b"\xff\xd8\xff"
    cache.put_image("https://cdn.zero.pl/img.jpg", data)
    assert cache.get_image("https://cdn.zero.pl/img.jpg") == data


def test_disabled_cache(tmp_path):
    cache = Cache(root=tmp_path / "cache", enabled=False)
    cache.put_article("x", "y")
    assert cache.get_article("x") is None


def test_clear(tmp_path):
    cache = Cache(root=tmp_path / "cache", enabled=True)
    cache.put_article("x", "y")
    cache.clear()
    assert cache.get_article("x") is None
