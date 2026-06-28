"""Disk cache for article HTML and processed images."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

DEFAULT_CACHE_DIR = Path(".cache")


class Cache:
    def __init__(self, root: Path | str = DEFAULT_CACHE_DIR, enabled: bool = True):
        self.root = Path(root)
        self.enabled = enabled
        self.articles_dir = self.root / "articles"
        self.images_dir = self.root / "images"

    def ensure_dirs(self) -> None:
        if self.enabled:
            self.articles_dir.mkdir(parents=True, exist_ok=True)
            self.images_dir.mkdir(parents=True, exist_ok=True)

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)

    def get_article(self, slug: str) -> str | None:
        if not self.enabled:
            return None
        path = self.articles_dir / f"{slug}.html"
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return None

    def put_article(self, slug: str, html: str) -> None:
        if not self.enabled:
            return
        self.ensure_dirs()
        path = self.articles_dir / f"{slug}.html"
        path.write_text(html, encoding="utf-8")

    def _image_key(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def get_image(self, url: str) -> bytes | None:
        if not self.enabled:
            return None
        path = self.images_dir / f"{self._image_key(url)}.jpg"
        if path.is_file():
            return path.read_bytes()
        return None

    def put_image(self, url: str, data: bytes) -> None:
        if not self.enabled:
            return
        self.ensure_dirs()
        path = self.images_dir / f"{self._image_key(url)}.jpg"
        path.write_bytes(data)
