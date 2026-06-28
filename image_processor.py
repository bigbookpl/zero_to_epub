"""Resize and convert images for monochrome e-readers."""

from __future__ import annotations

import io

from PIL import Image

MAX_WIDTH = 600
JPEG_QUALITY = 65


def process_for_ereader(data: bytes) -> bytes:
    """Return grayscale JPEG bytes, max width MAX_WIDTH."""
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        w, h = img.size
        if w > MAX_WIDTH:
            ratio = MAX_WIDTH / w
            img = img.resize((MAX_WIDTH, int(h * ratio)), Image.Resampling.LANCZOS)
        gray = img.convert("L")
        out = io.BytesIO()
        gray.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue()
