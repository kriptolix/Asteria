"""
Automatic document summary.
"""

from __future__ import annotations

import re

from .document import TocEntry
from .urls import slugify

_HEADING_RE = re.compile(r"<(h[1-6])([^>]*)>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_ID_ATTR_RE = re.compile(r'\sid="[^"]*"', re.IGNORECASE)


def inject_heading_ids_and_build_toc(html: str) -> tuple[str, list[TocEntry]]:
    
    used_slugs: dict[str, int] = {}
    flat: list[tuple[int, str, str]] = []

    def _replace(match: re.Match) -> str:
        tag = match.group(1).lower()
        attrs = match.group(2) or ""
        inner = match.group(3)
        level = int(tag[1])

        title_text = _TAG_RE.sub("", inner).strip()
        base_slug = slugify(title_text) if title_text else f"secao-{len(flat) + 1}"

        count = used_slugs.get(base_slug, 0)
        slug = base_slug if count == 0 else f"{base_slug}-{count + 1}"
        used_slugs[base_slug] = count + 1

        flat.append((level, slug, title_text))

        cleaned_attrs = _ID_ATTR_RE.sub("", attrs)
        return f'<{tag}{cleaned_attrs} id="{slug}">{inner}</{tag}>'

    new_html = _HEADING_RE.sub(_replace, html)
    tree = _build_tree(flat)
    return new_html, tree


def _build_tree(flat: list[tuple[int, str, str]]) -> list[TocEntry]:

    root: list[TocEntry] = []
    stack: list[tuple[int, TocEntry]] = []

    for level, slug, title in flat:
        entry = TocEntry(id=slug, title=title, level=level)
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1].children.append(entry)
        else:
            root.append(entry)
        stack.append((level, entry))

    return root
