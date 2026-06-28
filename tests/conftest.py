"""Shared pytest fixtures (offline only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(*parts: str) -> str:
    path = FIXTURES_DIR.joinpath(*parts)
    return path.read_text(encoding="utf-8")


def load_fixture_bytes(*parts: str) -> bytes:
    path = FIXTURES_DIR.joinpath(*parts)
    return path.read_bytes()


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def httpx_mock():
    """Patch httpx.Client.get to avoid network in EPUB/cover tests."""

    def _make_get(responses: dict[str, tuple[int, str | bytes, str]]):
        """Map URL prefix -> (status, body, content_type hint)."""

        def fake_get(self, url, **kwargs):
            for prefix, (status, body, _) in responses.items():
                if url.startswith(prefix) or prefix in url:
                    resp = MagicMock()
                    resp.status_code = status
                    resp.raise_for_status = MagicMock()
                    if status >= 400:
                        resp.raise_for_status.side_effect = Exception("HTTP error")
                    if isinstance(body, bytes):
                        resp.content = body
                        resp.text = body.decode("utf-8", errors="replace")
                    else:
                        resp.text = body
                        resp.content = body.encode("utf-8")
                    return resp
            resp = MagicMock()
            resp.status_code = 404
            resp.raise_for_status.side_effect = Exception(f"Unexpected URL: {url}")
            return resp

        return fake_get

    return _make_get


@pytest.fixture
def patch_httpx_get():
    """Context manager factory: patch_httpx_get(mapping)(client usage)."""

    def _patch(responses: dict[str, tuple[int, str | bytes, str]]):
        def fake_get(self, url, **kwargs):
            for prefix, (status, body, _) in responses.items():
                if url.startswith(prefix) or prefix in url:
                    resp = MagicMock()
                    resp.status_code = status
                    resp.raise_for_status = MagicMock()
                    if isinstance(body, bytes):
                        resp.content = body
                        resp.text = body.decode("utf-8", errors="replace")
                    else:
                        resp.text = body
                        resp.content = body.encode("utf-8")
                    return resp
            raise AssertionError(f"Unexpected URL: {url}")

        return patch("httpx.Client.get", fake_get)

    return _patch
