#!/usr/bin/env python3
"""Scrape zero.pl articles and build an EPUB ebook."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from cache import Cache, DEFAULT_CACHE_DIR
from epub_builder import build_epub
from models import EpubMeta
from utils import format_date_pl
from scraper import scrape_for_days

DEFAULT_DAYS = 7


def default_output_path(date_from: datetime, date_to: datetime) -> str:
    start = date_from.strftime("%Y-%m-%d")
    end = date_to.strftime("%Y-%m-%d")
    return f"zero_{start}_{end}.epub"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pobierz artykuły z zero.pl z ostatnich N dni i utwórz EPUB."
    )
    parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Liczba dni wstecz (domyślnie: {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Ścieżka pliku EPUB (domyślnie: zero_YYYY-MM-DD_YYYY-MM-DD.epub)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Katalog cache (domyślnie: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Wyłącz cache — pobierz wszystko od zera",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Wyczyść cache przed uruchomieniem",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Więcej logów",
    )
    args = parser.parse_args()

    if args.days < 1:
        parser.error("--days musi być >= 1")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    if not args.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
    log = logging.getLogger(__name__)

    cache = Cache(root=args.cache_dir, enabled=not args.no_cache)
    if args.clear_cache:
        cache.clear()
        log.info("Cache wyczyszczony: %s", args.cache_dir)

    try:
        t0 = time.perf_counter()
        log.info("Pobieranie listy artykułów (ostatnie %d dni)...", args.days)
        result = scrape_for_days(days=args.days, cache=cache)
        refs_count = len(result.articles)

        log.info(
            "Zakres: %s – %s (%d artykułów)",
            format_date_pl(result.date_from),
            format_date_pl(result.date_to),
            refs_count,
        )

        for i, article in enumerate(result.articles, 1):
            if i <= 5 or i == refs_count:
                log.info("[%d/%d] %s", i, refs_count, article.title)
            elif i == 6:
                log.info("...")

        output = args.output or default_output_path(
            result.date_from, result.date_to
        )
        meta = EpubMeta(
            date_from=result.date_from,
            date_to=result.date_to,
            generated_at=result.generated_at,
        )

        log.info("Budowanie EPUB: %s", output)
        build_epub(result.articles, output, meta, cache=cache)
        elapsed = time.perf_counter() - t0
        log.info("Gotowe: %s (%.0f s)", output, elapsed)
        return 0

    except Exception as exc:
        log.error("Błąd: %s", exc)
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())
