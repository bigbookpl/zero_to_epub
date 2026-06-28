# Zero.pl → EPUB

Aplikacja w Pythonie pobiera artykuły z [zero.pl](https://zero.pl) z **ostatnich N dni** (domyślnie 7), ekstrahuje treść i buduje plik **EPUB** z okładką i rozdziałami.

## Wymagania

- Python 3.10+

## Instalacja

```bash
cd zero_to_epub
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Uruchomienie

```bash
# Ostatnie 7 dni → np. zero_2026-05-28_2026-06-04.epub
python main.py

# Inny zakres
python main.py --days 14
python main.py -d 30 -o zero_miesiac.epub

python main.py -v   # logi szczegółowe
```

## Parametry CLI

| Flaga | Domyślnie | Opis |
|-------|-----------|------|
| `-d`, `--days` | `7` | Ile dni wstecz (od północy, strefa Europe/Warsaw) |
| `-o`, `--output` | `zero_{od}_{do}.epub` | Ścieżka pliku wyjściowego |
| `--cache-dir` | `.cache` | Katalog cache artykułów i obrazów |
| `--no-cache` | — | Wymuś pobieranie bez cache |
| `--clear-cache` | — | Usuń cache przed startem |
| `-v`, `--verbose` | — | Więcej logów (w tym trafienia cache) |

## Cache (development)

Przy ponownym uruchomieniu skrypt korzysta z:

- `.cache/articles/{slug}.html` — surowy HTML artykułu
- `.cache/images/{hash}.jpg` — przetworzone obrazy (skala szarości, JPEG)

```bash
python main.py -d 1              # pierwsze uruchomienie — pełne pobieranie
python main.py -d 1              # drugie — szybciej dzięki cache
python main.py -d 1 --clear-cache  # wymuś odświeżenie
```

## Obrazy pod Kindle

Zdjęcia są zmniejszane (max 600 px szerokości), konwertowane do **skali szarości JPEG** — mniejszy rozmiar EPUB i lepsza czytelność na czytnikach e-ink (np. Kindle Paperwhite).

## Spis treści

Rozdziały są pogrupowane wg kategorii (Kraj, Świat, Sport, …). W każdej kategorii artykuły są posortowane **od najstarszego do najnowszego**, z datą publikacji przy tytule. Artykuły w spisie mają wcięcie i punktory, żeby łatwiej je odróżnić na czytniku.

Na końcu książki jest **indeks autorów** (`authors.xhtml`): alfabetyczna lista autorów z linkami do ich artykułów. Nazwisko na początku rozdziału jest klikalne i prowadzi do tego indeksu.

## Co robi skrypt

1. Pobiera listę z API `zero.pl/api/be/posts` (paginacja jak na stronie „Najnowsze”).
2. Filtruje artykuły po dacie `published` z ostatnich N dni.
3. Dla każdego `/news/...` pobiera treść (`h1`, autor, excerpt, `div.prose`).
4. Czyści HTML (reklamy, related posts, komentarze Vue).
5. Linki do innych artykułów z tego samego zbioru zamienia na odnośniki wewnętrzne EPUB (zamiast URL zero.pl).
6. Osadza obrazy (optymalizowane pod e-ink) w EPUB.
7. Tworzy okładkę XHTML (logo zero.pl, zakres dat, data wygenerowania).
8. Zapisuje ebook ze spisem treści wg kategorii.

## GitHub Actions (automatyczne EPUB)

Workflow [`.github/workflows/generate-epub.yml`](.github/workflows/generate-epub.yml) generuje EPUB w chmurze i publikuje go jako **GitHub Release** (załącznik do wydania).

### Harmonogram

- **Co tydzień w sobotę o 6:00** (Europe/Warsaw, latem CEST) — artykuły z **ostatnich 7 dni**
- GitHub Actions używa UTC (`0 4 * * 6`); zimą (CET) uruchomienie nastąpi o **5:00** czasu warszawskiego

### Ręczne uruchomienie

1. Otwórz zakładkę **Actions** w repozytorium na GitHubie
2. Wybierz workflow **Generate EPUB** → **Run workflow**
3. Podaj liczbę dni wstecz (domyślnie `7`) i uruchom

### Pobieranie pliku

Wszystkie wygenerowane EPUB-y są w zakładce **[Releases](https://github.com/bigbookpl/zero_to_epub/releases)** — możesz pobrać najnowszy i poprzednie wydania (np. `zero_2026-06-21_2026-06-28.epub`).

- cotygodniowy build → tag `zero_YYYY-MM-DD_YYYY-MM-DD`
- ręczny build → tag z sufiksem `-run-<numer>` (żeby nie kolidował z istniejącym wydaniem)

### Lokalny cron (alternatywa)

```bash
# Co tydzień — sobota 6:00
0 6 * * 6 cd /ścieżka/zero_to_epub && .venv/bin/python main.py --days 7
```

## Testy

Testy są **wyłącznie offline** (fixture’y HTML/JSON, mock `httpx`) — bez zapytań do zero.pl.

```bash
pip install -r requirements-dev.txt
pytest
```

Po świadomej zmianie formatu HTML lub EPUB zaktualizuj snapshoty regresji:

```bash
pytest --force-regen
```

Fixture’y: `tests/fixtures/` (artykuły, odpowiedzi API, obraz testowy). Snapshoty: `tests/test_regression/*.yml`.

## Struktura

- `main.py` — CLI
- `models.py` — modele danych (`Article`, `EpubMeta`, …)
- `utils.py` — daty, XML, klucze URL artykułów
- `scraper.py` — API + pobieranie artykułów
- `html_cleaner.py` — czyszczenie treści
- `cover_builder.py` — okładka XHTML z logo SVG
- `epub_links.py` — indeks linków wewnętrznych EPUB
- `epub_html.py` — szablony XHTML (rozdziały, nawigacja)
- `epub_builder.py` — składanie i zapis EPUB
- `image_processor.py` — optymalizacja obrazów
- `cache.py` — cache dyskowy
- `tests/` — pytest (jednostkowe + regresja)

## Uwagi prawne

Ebook jest przeznaczony do **użytku osobistego**. Treści należą do Kanał Zero Sp. z o.o. — korzystaj zgodnie z regulaminem serwisu.
