"""Tests for image_processor."""

import io

from PIL import Image

from conftest import load_fixture_bytes
from image_processor import MAX_WIDTH, process_for_ereader


def test_process_resizes_wide_image():
    img = Image.new("RGB", (1200, 600), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out = process_for_ereader(buf.getvalue())
    result = Image.open(io.BytesIO(out))
    assert result.format == "JPEG"
    assert result.mode == "L"
    assert result.size[0] <= MAX_WIDTH


def test_process_fixture_png():
    data = load_fixture_bytes("images", "sample.png")
    out = process_for_ereader(data)
    assert len(out) < len(data)
    assert out[:2] == b"\xff\xd8"
