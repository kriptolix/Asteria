"""
"Raw" HTML pages
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import Diagnostics
from .urls import build_url, slugify


@dataclass
class RawPage:
    id: str
    source_dir: Path
    title: str = ""
    slug: str = ""
    url: str = ""

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = slugify(self.id)
        if not self.title:
            self.title = self.id


def load_raw_page(
    source_dir: Path, url_pattern: str, diagnostics: Diagnostics
) -> RawPage:
    
    meta: dict = {}
    meta_path = source_dir / "raw.yaml"
    if meta_path.exists():
        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            diagnostics.warning(
                f"raw.yaml invalid, ignored: {exc}", source=str(meta_path)
            )
            meta = {}

    page = RawPage(
        id=source_dir.name,
        source_dir=source_dir,
        title=str(meta.get("title", "")) or source_dir.name,
    )
    page.url = build_url(url_pattern, slug=page.slug)
    return page