"""sitemap.xml generation."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass
class SitemapEntry:
    path: str  # ex: "/blog/artigo/"
    lastmod: str | None = None  # "YYYY-MM-DD", if available


def render_sitemap(entries: list[SitemapEntry], site_url: str) -> str:
    site_url = site_url.rstrip("/")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for entry in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(site_url + entry.path)}</loc>")
        if entry.lastmod:
            lines.append(f"    <lastmod>{escape(entry.lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
