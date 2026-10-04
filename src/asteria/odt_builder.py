"""
Generator for minimal, valid `.odt` files. Legacy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

_MIMETYPE = b"application/vnd.oasis.opendocument.text"

_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>
"""

_CONTENT_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 office:version="1.2">
 <office:body>
  <office:text>
"""
_CONTENT_FOOTER = "  </office:text>\n </office:body>\n</office:document-content>\n"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class OdtDocument:
    """Monta o corpo de um `.odt` bloco a bloco, incluindo o front matter."""

    frontmatter: dict[str, str] = field(default_factory=dict)
    _blocks: list[str] = field(default_factory=list)

    def heading(self, text: str, level: int = 1) -> "OdtDocument":
        self._blocks.append(f'   <text:h text:outline-level="{level}">{_escape(text)}</text:h>\n')
        return self

    def paragraph(self, text: str = "") -> "OdtDocument":
        self._blocks.append(f"   <text:p>{_escape(text)}</text:p>\n")
        return self

    def list_items(self, items: list[str]) -> "OdtDocument":
        parts = ["   <text:list>\n"]
        for item in items:
            parts.append(f"    <text:list-item><text:p>{_escape(item)}</text:p></text:list-item>\n")
        parts.append("   </text:list>\n")
        self._blocks.append("".join(parts))
        return self

    def _frontmatter_block(self) -> str:
        if not self.frontmatter:
            return ""
        lines = ["---"] + [f"{k}: {v}" for k, v in self.frontmatter.items()] + ["---"]
        return "".join(f"   <text:p>{_escape(line)}</text:p>\n" for line in lines)

    def build(self) -> str:
        return self._frontmatter_block() + "".join(self._blocks)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = self.build()
        with ZipFile(path, "w", ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", _MIMETYPE, compress_type=ZIP_STORED)
            zf.writestr("META-INF/manifest.xml", _MANIFEST)
            zf.writestr("content.xml", _CONTENT_HEADER + body + _CONTENT_FOOTER)
        return path
