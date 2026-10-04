"""
ODT → HTML conversion layer.
"""

from __future__ import annotations

import re
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .errors import AsteriaError, Diagnostics
from .frontmatter import Frontmatter

ODT_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
}


@dataclass
class ExtractedImage:
    """An image embedded in the ODT that needs to be copied to the output."""

    original_path: str  
    data: bytes
    output_name: str  


@dataclass
class ConversionResult:
    """
    Standardized output from any ODT→HTML converter. 

    ``metadata``: when the converter itself recognizes and extracts the
    front matter block (as with odt2web, via ``result.metadata``), it is
    exposed here already normalized as ``Frontmatter``, and the SSG does not
    need to look for the ``div.ssg-frontmatter`` block in the HTML. When
    ``None`` (as with FallbackConverter), the SSG looks for the standardized
    block within the HTML.
    """

    html: str
    images: list[ExtractedImage] = field(default_factory=list)
    converter_name: str = "unknown"
    metadata: Frontmatter | None = None


class ODTConverter(ABC):
    
    name: str = "base"

    @abstractmethod
    def convert(self, odt_path: Path, diagnostics: Diagnostics) -> ConversionResult:
        
        raise NotImplementedError


class Odt2WebConverter(ODTConverter):
    """
    Adapter for ``odt2web``.
    """

    name = "odt2web"

    def __init__(self) -> None:
        try:
            from odt2web import convert  # type: ignore
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise ImportError(
                "The 'odt2web' library is not installed."
            ) from exc
        self._convert = convert

    def convert(self, odt_path: Path, diagnostics: Diagnostics) -> ConversionResult:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="asteria-odt2web-") as tmp:
            tmp_dir = Path(tmp)
            result = self._convert(
                str(odt_path),
                output_dir=str(tmp_dir),
                css=False,
                extract_images=True,
                document=False,
                allow_raw_html=True,
            )

            html = getattr(result, "html", "") or ""

            for warning in getattr(result, "warnings", None) or []:
                diagnostics.warning(_stringify(warning), source=str(odt_path))

            images, html = self._collect_assets_from_disk(tmp_dir, html)

            # Front matter is embedded in the HTML (div.ssg-frontmatter), not
            # in result.metadata — we leave metadata=None so that
            # discovery.py always uses extract_frontmatter(html) here as well.
            return ConversionResult(
                html=html,
                images=images,
                converter_name=self.name,
                metadata=None,
            )

    def _collect_assets_from_disk(
        self, tmp_dir: Path, html: str
    ) -> tuple[list[ExtractedImage], str]:
        
        assets_dir = tmp_dir / "assets"
        images: list[ExtractedImage] = []
        if not assets_dir.exists():
            return images, html

        for file_path in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
            rel_path = file_path.relative_to(tmp_dir).as_posix()  # "assets/foo.png"
            output_name = file_path.name
            images.append(
                ExtractedImage(
                    original_path=rel_path,
                    data=file_path.read_bytes(),
                    output_name=output_name,
                )
            )
            for needle in (rel_path, f"/{rel_path}", f"./{rel_path}"):
                if needle in html:
                    html = html.replace(needle, output_name)
                    break

        return images, html


def _stringify(warning: Any) -> str:
    message = getattr(warning, "message", None)
    return str(message) if message is not None else str(warning)


class FallbackConverter(ODTConverter):
    """
    Minimal converter, using only the Python standard library. 
    **For testing purposes only**
    """

    name = "fallback"

    FRONTMATTER_RE = re.compile(
        r"^\s*---\s*\n(?P<body>.*?)\n\s*---\s*\n?", re.DOTALL
    )

    def convert(self, odt_path: Path, diagnostics: Diagnostics) -> ConversionResult:
        with zipfile.ZipFile(odt_path) as zf:
            try:
                content_xml = zf.read("content.xml")
            except KeyError as exc:
                diagnostics.error(
                    f"Arquivo ODT inválido (sem content.xml): {exc}",
                    source=str(odt_path),
                )
                return ConversionResult(html="", converter_name=self.name)

            images = self._extract_images(zf, odt_path)

        try:
            root = ET.fromstring(content_xml)
        except ET.ParseError as exc:
            diagnostics.error(f"XML inválido no ODT: {exc}", source=str(odt_path))
            return ConversionResult(html="", converter_name=self.name)

        body = root.find(".//office:text", ODT_NS)
        if body is None:
            diagnostics.error(
                "Nenhum corpo de texto (office:text) encontrado.",
                source=str(odt_path),
            )
            return ConversionResult(html="", converter_name=self.name)

        blocks_html, plain_paragraphs = self._render_body(body, images)

        frontmatter_html, remaining_blocks = self._extract_frontmatter(
            blocks_html, plain_paragraphs, odt_path, diagnostics
        )

        html = frontmatter_html + "\n".join(remaining_blocks)
        return ConversionResult(html=html, images=images, converter_name=self.name)

    # -- imagens ------------------------------------------------------------
    def _extract_images(self, zf: zipfile.ZipFile, odt_path: Path) -> list[ExtractedImage]:
        images: list[ExtractedImage] = []
        for name in zf.namelist():
            if name.startswith("Pictures/") and not name.endswith("/"):
                data = zf.read(name)
                ext = Path(name).suffix or ".png"
                output_name = f"{Path(name).stem}{ext}"
                images.append(
                    ExtractedImage(original_path=name, data=data, output_name=output_name)
                )
        return images

    # -- corpo do documento ---------------------------------------------------
    def _render_body(
        self, body: ET.Element, images: list[ExtractedImage]
    ) -> tuple[list[str], list[str]]:
        blocks: list[str] = []
        plain_paragraphs: list[str] = []
        image_by_path = {img.original_path: img for img in images}

        for el in body:
            tag = el.tag.split("}")[-1]
            if tag == "h":
                level = el.attrib.get(
                    f"{{{ODT_NS['text']}}}outline-level", "1"
                )
                level = max(1, min(6, int(level)))
                text = self._text_content(el)
                blocks.append(f"<h{level}>{self._escape(text)}</h{level}>")
                plain_paragraphs.append("")
            elif tag == "p":
                inline = self._inline_html(el, image_by_path)
                text = self._text_content(el)
                plain_paragraphs.append(text)
                if text.strip() or "<img" in inline:
                    blocks.append(f"<p>{inline}</p>")
                else:
                    blocks.append("")
            elif tag == "list":
                blocks.append(self._render_list(el, image_by_path))
                plain_paragraphs.append("")
            elif tag == "table":
                blocks.append(self._render_table(el))
                plain_paragraphs.append("")
        return blocks, plain_paragraphs

    def _render_list(self, el: ET.Element, image_by_path: dict) -> str:
        items = []
        for item in el.findall("text:list-item", ODT_NS):
            parts = []
            for p in item.findall("text:p", ODT_NS):
                parts.append(self._inline_html(p, image_by_path))
            nested = item.findall("text:list", ODT_NS)
            for nested_list in nested:
                parts.append(self._render_list(nested_list, image_by_path))
            items.append(f"<li>{''.join(parts)}</li>")
        return f"<ul>{''.join(items)}</ul>"

    def _render_table(self, el: ET.Element) -> str:
        rows = []
        for row in el.findall("table:table-row", ODT_NS):
            cells = []
            for cell in row.findall("table:table-cell", ODT_NS):
                text = self._text_content(cell)
                cells.append(f"<td>{self._escape(text)}</td>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        return f"<table>{''.join(rows)}</table>"

    def _inline_html(self, el: ET.Element, image_by_path: dict) -> str:
        parts: list[str] = []
        if el.text:
            parts.append(self._escape(el.text))
        for child in el:
            tag = child.tag.split("}")[-1]
            if tag == "span":
                parts.append(self._inline_html(child, image_by_path))
            elif tag == "a":
                href = child.attrib.get(f"{{{ODT_NS['xlink']}}}href", "#")
                parts.append(f'<a href="{self._escape(href)}">{self._inline_html(child, image_by_path)}</a>')
            elif tag == "frame":
                img_el = child.find("draw:image", ODT_NS)
                if img_el is not None:
                    href = img_el.attrib.get(f"{{{ODT_NS['xlink']}}}href", "")
                    img = image_by_path.get(href)
                    # Caminho relativo: a imagem é gravada no mesmo
                    # diretório de saída do documento (ver writer.py), não
                    # em uma pasta /images/ compartilhada.
                    src = img.output_name if img else href
                    parts.append(f'<img src="{self._escape(src)}" alt="">')
            if child.tail:
                parts.append(self._escape(child.tail))
        return "".join(parts)

    def _text_content(self, el: ET.Element) -> str:
        return "".join(el.itertext())

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # -- front matter (spec 5.1 / 5.2) ---------------------------------------
    def _extract_frontmatter(
        self,
        blocks_html: list[str],
        plain_paragraphs: list[str],
        odt_path: Path,
        diagnostics: Diagnostics,
    ) -> tuple[str, list[str]]:
        """Reconhece o bloco `--- chave: valor ... ---` nos parágrafos
        iniciais do documento e o converte para o HTML padronizado da
        seção 5.2 da spec.
        """
        # Junta os parágrafos de texto simples iniciais para detectar o bloco.
        leading_text_parts = []
        consumed = 0
        for text in plain_paragraphs:
            stripped = text.strip()
            if stripped == "---" or ":" in stripped or stripped == "":
                leading_text_parts.append(text)
                consumed += 1
                if stripped == "---" and consumed > 1:
                    break
            else:
                break

        candidate = "\n".join(leading_text_parts)
        match = self.FRONTMATTER_RE.match(candidate + "\n")
        if not match:
            return "", blocks_html

        fields: dict[str, str] = {}
        for line in match.group("body").splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key:
                fields[key] = value

        if not fields:
            return "", blocks_html

        meta_tags = "\n".join(
            f'  <meta data-key="{self._escape(k)}" content="{self._escape(v)}">'
            for k, v in fields.items()
        )
        frontmatter_html = (
            f'<div class="ssg-frontmatter" data-ssg="frontmatter">\n{meta_tags}\n</div>\n'
        )

        remaining = blocks_html[consumed:]
        return frontmatter_html, remaining


def get_converter(preferred: str = "auto") -> ODTConverter:
    
    if preferred == "fallback":
        return FallbackConverter()

    try:
        return Odt2WebConverter()
    except ImportError as exc:
        raise AsteriaError(
            "The 'odt2web' library is not installed."            
        ) from exc
