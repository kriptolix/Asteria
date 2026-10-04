"""Public types returned by the API (spec section 2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .model import Metadata


class WarningLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Warning:
    message: str
    level: WarningLevel = WarningLevel.WARNING
    source: str | None = None  # e.g. "parser", "renderer", "assets"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.level.value}] {self.message}"


@dataclass
class Asset:
    """A resource extracted from the ODT package (usually an image)."""
    original_path: str  # path inside the .odt, e.g. Pictures/10000000...png
    output_path: str  # relative path referenced by the HTML
    data: bytes = field(repr=False, default=b"")
    media_type: str | None = None
    written_to: str | None = None  # absolute path on disk, if written


@dataclass
class ConversionResult:
    html: str
    css: str | None
    assets: list[Asset] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
    front_matter: dict | None = None
    warnings: list[Warning] = field(default_factory=list)

    def write(self, output_dir: str, html_filename: str = "index.html",
              css_filename: str = "style.css") -> None:
        """Writes html/css/assets to output_dir. Used internally by the
        high-level API when output_dir is given, but can also be called
        manually."""
        import os

        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, html_filename)
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(self.html)

        if self.css is not None:
            css_path = os.path.join(output_dir, css_filename)
            with open(css_path, "w", encoding="utf-8") as fh:
                fh.write(self.css)

        for asset in self.assets:
            asset_path = os.path.join(output_dir, asset.output_path)
            os.makedirs(os.path.dirname(asset_path), exist_ok=True)
            with open(asset_path, "wb") as fh:
                fh.write(asset.data)
            asset.written_to = asset_path
