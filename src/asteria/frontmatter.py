"""
Interpretation of the standardized front matter block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape

from .errors import Diagnostics

KNOWN_FIELDS = {
    "title",
    "date",
    "author",
    "tags",
    "categories",
    "description",
    "slug",
    "variant",
    "toc",
    "navigation",
    "lang",
    "template",
    "featured",
    "cover",
    "menu_title",
    "nav_title",
}

FRONTMATTER_BLOCK_RE = re.compile(
    r'<div[^>]*class="ssg-frontmatter"[^>]*>(?P<inner>.*?)</div>',
    re.DOTALL,
)
META_TAG_RE = re.compile(
    r'<meta[^>]*data-key="(?P<key>[^"]*)"[^>]*content="(?P<value>[^"]*)"[^>]*>',
    re.DOTALL,
)


@dataclass
class Frontmatter:
    title: str | None = None
    date: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    description: str = ""
    slug: str | None = None
    variant: str | None = None     
    template: str | None = None
    toc: bool = True  
    navigation: bool = False  
    lang: str | None = None  
    featured: bool = False   
    cover: str | None = None    
    menu_title: str | None = None   
    nav_title: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default=None):
        return getattr(self, key, self.extra.get(key, default))


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in ("false", "no", "0", "off")


def extract_frontmatter(
    html: str, source: str, diagnostics: Diagnostics
) -> tuple[Frontmatter, str]:
    
    match = FRONTMATTER_BLOCK_RE.search(html)
    if not match:
        return Frontmatter(), html

    inner = match.group("inner")
    raw_fields: dict[str, str] = {}
    for meta_match in META_TAG_RE.finditer(inner):
        key = unescape(meta_match.group("key")).strip().lower()
        value = unescape(meta_match.group("value")).strip()
        if key in raw_fields:
            diagnostics.warning(f"Duplicate front matter field: '{key}'.", source=source)
        raw_fields[key] = value

    for key in raw_fields:
        if key not in KNOWN_FIELDS:
            diagnostics.warning(
                f"Unknown front matter field: '{key}' (preserved in extra).",
                source=source,
            )

    fm = Frontmatter(
        title=raw_fields.get("title"),
        date=raw_fields.get("date"),
        author=raw_fields.get("author"),
        tags=_split_list(raw_fields.get("tags", "")),
        categories=_split_list(raw_fields.get("categories", "")),
        description=raw_fields.get("description", ""),
        slug=raw_fields.get("slug"),
        variant=raw_fields.get("variant"),
        template=raw_fields.get("template") or None,
        toc=_parse_bool(raw_fields.get("toc"), default=True),
        navigation=_parse_bool(raw_fields.get("navigation"), default=False),
        lang=raw_fields.get("lang") or None,
        featured=_parse_bool(raw_fields.get("featured"), default=False),
        cover=raw_fields.get("cover") or None,
        menu_title=raw_fields.get("menu_title") or None,
        nav_title=raw_fields.get("nav_title") or None,
        extra={k: v for k, v in raw_fields.items() if k not in KNOWN_FIELDS},
    )

    html_without_block = html[: match.start()] + html[match.end() :]
    return fm, html_without_block.strip()