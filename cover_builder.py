"""Build XHTML cover page for Zero.pl EPUB."""

from __future__ import annotations

from datetime import datetime

import httpx

from scraper import LOGO_URL
from utils import escape_xml, format_date_pl


def fetch_logo_svg(client: httpx.Client) -> str:
    response = client.get(LOGO_URL)
    response.raise_for_status()
    return response.text


def adapt_logo_for_dark_background(svg: str) -> str:
    """White wordmark on black; keep red dot accent."""
    adapted = svg.replace('fill="black"', 'fill="white"')
    adapted = adapted.replace("fill='black'", "fill='white'")
    return adapted


def build_cover_xhtml(
    svg_inline: str,
    date_from: datetime,
    date_to: datetime,
    generated_at: datetime,
    article_count: int,
) -> bytes:
    period = f"{format_date_pl(date_from)} – {format_date_pl(date_to)}"
    generated = format_date_pl(generated_at)
    n = article_count
    if n == 1:
        count_label = "artykuł"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        count_label = "artykuły"
    else:
        count_label = "artykułów"

    html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="pl">
<head>
  <meta charset="utf-8"/>
  <title>Zero.pl</title>
</head>
<body>
  <div style="margin:0;padding:3em 1.5em;background-color:#000000;color:#ffffff;font-family:Georgia,serif;text-align:center;min-height:90vh;">
    <div style="width:55%;max-width:280px;margin:0 auto 2.5em;">
      {svg_inline}
    </div>
    <h1 style="font-size:1.4em;font-weight:normal;letter-spacing:0.05em;margin:0 0 1.2em;color:#ffffff;">Zero.pl</h1>
    <p style="font-size:1.15em;margin:0 0 0.8em;color:#ffffff;">{escape_xml(period)}</p>
    <p style="color:#999999;font-size:0.95em;line-height:1.6;margin:0;">
      Wygenerowano: {escape_xml(generated)}<br/>
      {article_count} {count_label}
    </p>
  </div>
</body>
</html>"""
    return html.encode("utf-8")


def build_cover_bytes(
    client: httpx.Client,
    date_from: datetime,
    date_to: datetime,
    generated_at: datetime,
    article_count: int,
) -> bytes:
    svg = fetch_logo_svg(client)
    svg_inline = adapt_logo_for_dark_background(svg)
    return build_cover_xhtml(
        svg_inline, date_from, date_to, generated_at, article_count
    )
