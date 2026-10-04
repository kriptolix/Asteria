"""Style system (spec sections 6, 7 and 8).

Interprets styles.xml and the automatic styles in content.xml, resolving
each ODT style-name to a semantic representation that the renderer uses
to decide which HTML tag/class to generate.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from .ns import NS, q

# Default mapping (section 6) - the user may override/extend it.
DEFAULT_STYLE_MAP: dict[str, str | dict] = {
    "Title": "h1",
    "Subtitle": "h2",
    "Heading 1": "h2",
    "Heading 2": "h3",
    "Heading 3": "h4",
    "Heading 4": "h5",
    "Heading 5": "h6",
    "Heading 6": "h6",
    "Quotation": "blockquote",
    "Quotations": "blockquote",
    "Text Body": "p",
    "Preformatted Text": "pre",
    "Caption": {"tag": "figcaption"},
}


@dataclass
class ColumnInfo:
    count: int = 1
    gap: str | None = None  # CSS unit
    rule: str | None = None  # "1px solid #rrggbb"


@dataclass
class StyleInfo:
    name: str
    family: str  # "paragraph" | "text" | "table" | "table-cell" | "section" | "graphic"
    parent: str | None = None
    display_name: str | None = None
    text_align: str | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    superscript: bool = False
    subscript: bool = False
    break_before: bool = False
    break_after: bool = False
    columns: ColumnInfo | None = None
    # horizontal anchor position of a graphic/frame style (from
    # style:graphic-properties/@style:horizontal-pos), e.g. "left",
    # "center", "right", "from-left" - used to derive an alignment class
    # for images (see renderer._render_image).
    horizontal_pos: str | None = None
    # "fo:keep-with-next" of a paragraph style: True ("always"), False
    # ("auto", an explicit opt-out that overrides an inherited "always")
    # or None when this style level does not say anything about it.
    keep_with_next: bool | None = None
    # width of a table column (style:table-column-properties/
    # @style:column-width), already converted to centimeters.
    column_width_cm: float | None = None


CM_PER_UNIT = {"cm": 1.0, "mm": 0.1, "in": 2.54, "pt": 2.54 / 72, "px": 2.54 / 96}


def _to_css_length(value: str | None) -> str | None:
    """ODF already uses CSS-compatible units (cm, mm, in, pt, px) in
    most cases; we just pass the value through, validating the format."""
    if not value:
        return None
    return value


_LENGTH_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([a-z%]*)\s*$")


def length_to_cm(value: str | None) -> float | None:
    """Converts a CSS/ODF length such as '8.5cm' or '120px' into
    centimeters. Meant for classification and relative comparisons only.
    Returns None for empty, malformed or relative (%, em...) values."""
    if not value:
        return None
    match = _LENGTH_RE.match(value)
    if not match:
        return None
    number, unit = match.groups()
    factor = CM_PER_UNIT.get(unit or "cm")
    if factor is None:
        return None
    try:
        return float(number) * factor
    except ValueError:
        return None


_ODF_ESCAPE_RE = re.compile(r"_([0-9A-Fa-f]{2})_")


def decode_odf_style_name(name: str) -> str:
    """Decodes the reserved-character escaping used by
    LibreOffice/OpenOffice in style:name (e.g. 'Heading_20_1' -> 'Heading 1',
    'Normal_20__28_Web_29_' -> 'Normal (Web)'). style:name is an XML
    NCName and cannot contain certain characters (space, parentheses,
    etc.); those characters are encoded as '_XX_' (2-digit hex). When
    style:display-name is absent, this is the only way to get the
    "human" name of the style (used to match against style_map/
    DEFAULT_STYLE_MAP)."""
    return _ODF_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), name)


class StyleRegistry:
    """Consolidated registry of every named and automatic style found in
    styles.xml and content.xml."""

    def __init__(self) -> None:
        self._styles: dict[str, StyleInfo] = {}

    def add(self, info: StyleInfo) -> None:
        self._styles[info.name] = info

    def get(self, name: str | None) -> StyleInfo | None:
        if name is None:
            return None
        return self._styles.get(name)

    def resolve_columns(self, name: str | None) -> ColumnInfo | None:
        """Follows the parent-style-name chain until it finds column info."""
        seen = set()
        current = name
        while current and current not in seen:
            seen.add(current)
            info = self.get(current)
            if info is None:
                return None
            if info.columns is not None:
                return info.columns
            current = info.parent
        return None

    def resolve_horizontal_pos(self, name: str | None) -> str | None:
        """Follows the parent-style-name chain until it finds a graphic
        style's horizontal anchor position (used for image alignment)."""
        seen = set()
        current = name
        while current and current not in seen:
            seen.add(current)
            info = self.get(current)
            if info is None:
                return None
            if info.horizontal_pos is not None:
                return info.horizontal_pos
            current = info.parent
        return None

    def resolve_break_before(self, name: str | None) -> bool:
        """Follows the parent-style-name chain until it finds "break
        before" (the property is inherited when the paragraph's
        automatic style does not redefine it, which is the most common
        case)."""
        seen = set()
        current = name
        while current and current not in seen:
            seen.add(current)
            info = self.get(current)
            if info is None:
                return False
            if info.break_before:
                return True
            current = info.parent
        return False

    def resolve_keep_with_next(self, name: str | None) -> bool | None:
        """Follows the parent-style-name chain until it finds a style that
        explicitly sets "keep with next". The closest definition wins, so
        a child style with "auto" overrides an ancestor's "always".
        Returns None when nothing in the chain says anything about it."""
        seen = set()
        current = name
        while current and current not in seen:
            seen.add(current)
            info = self.get(current)
            if info is None:
                return None
            if info.keep_with_next is not None:
                return info.keep_with_next
            current = info.parent
        return None

    def resolve_text_align(self, name: str | None) -> str | None:
        """Follows the parent-style-name chain until it finds an explicit
        paragraph text alignment (raw ODF value: start, end, left, right,
        center, justify)."""
        seen = set()
        current = name
        while current and current not in seen:
            seen.add(current)
            info = self.get(current)
            if info is None:
                return None
            if info.text_align is not None:
                return info.text_align
            current = info.parent
        return None

    def display_name(self, name: str | None) -> str | None:
        if name is None:
            return None
        info = self.get(name)
        if info is None:
            return decode_odf_style_name(name)
        if info.display_name:
            return info.display_name
        return decode_odf_style_name(info.name)

    def resolve_style_candidates(self, name: str | None) -> list[str]:
        """Returns the ordered list of identifiers to try when resolving
        a style_name against style_map/DEFAULT_STYLE_MAP: the raw name
        and the "human" (decoded/display-name) name of every level in the
        parent-style-name chain, from most specific to most general.

        This is necessary because real-world documents almost always
        apply automatic styles generated by the editor (e.g. 'P1', 'P2')
        whose style:parent-style-name points to the actual named style
        (e.g. 'Heading_20_1' -> 'Heading 1') - the paragraph's own
        style_name is almost never literally 'Heading 1'."""
        candidates: list[str] = []
        seen_names = set()
        current = name
        while current and current not in seen_names:
            seen_names.add(current)
            candidates.append(current)
            display = self.display_name(current)
            if display and display != current:
                candidates.append(display)
            info = self.get(current)
            current = info.parent if info else None
        # remove duplicates while preserving order
        return list(dict.fromkeys(candidates))


def _parse_column_props(section_props: ET.Element) -> ColumnInfo | None:
    columns_el = section_props.find(q("style:columns"))
    if columns_el is None:
        return None
    count_raw = columns_el.get(q("fo:column-count"))
    try:
        count = int(count_raw) if count_raw else 1
    except ValueError:
        count = 1
    gap = _to_css_length(columns_el.get(q("fo:column-gap")))

    rule = None
    sep_el = columns_el.find(q("style:column-sep"))
    if sep_el is not None:
        width = _to_css_length(sep_el.get(q("style:width"))) or "1px"
        color = sep_el.get(q("style:color")) or "#000000"
        style = sep_el.get(q("style:style")) or "solid"
        rule = f"{width} {style} {color}"

    return ColumnInfo(count=count, gap=gap, rule=rule)


def _parse_style_element(style_el: ET.Element, family_override: str | None = None) -> StyleInfo | None:
    name = style_el.get(q("style:name"))
    if not name:
        return None
    family = family_override or style_el.get(q("style:family")) or "paragraph"
    parent = style_el.get(q("style:parent-style-name"))
    display_name = style_el.get(q("style:display-name"))

    info = StyleInfo(name=name, family=family, parent=parent, display_name=display_name)

    para_props = style_el.find(q("style:paragraph-properties"))
    if para_props is not None:
        info.text_align = para_props.get(q("fo:text-align"))
        columns = _parse_column_props(para_props)
        if columns is not None:
            info.columns = columns
        if para_props.get(q("fo:break-before")) == "page":
            info.break_before = True
        if para_props.get(q("fo:break-after")) == "page":
            info.break_after = True
        keep_with_next = para_props.get(q("fo:keep-with-next"))
        if keep_with_next == "always":
            info.keep_with_next = True
        elif keep_with_next == "auto":
            info.keep_with_next = False

    text_props = style_el.find(q("style:text-properties"))
    if text_props is not None:
        weight = text_props.get(q("fo:font-weight"))
        if weight and weight != "normal":
            info.bold = True
        posture = text_props.get(q("fo:font-style"))
        if posture and posture != "normal":
            info.italic = True
        underline_style = text_props.get(q("style:text-underline-style"))
        if underline_style and underline_style != "none":
            info.underline = True
        strike_style = text_props.get(q("style:text-line-through-style"))
        if strike_style and strike_style != "none":
            info.strikethrough = True
        position = text_props.get(q("style:text-position"))
        if position:
            first = position.split(" ")[0]
            if first == "super":
                info.superscript = True
            elif first == "sub":
                info.subscript = True

    # section-properties (used by style:style family="section" and by
    # page-layout-properties for page-level columns)
    section_props = style_el.find(q("style:section-properties"))
    if section_props is not None:
        columns = _parse_column_props(section_props)
        if columns is not None:
            info.columns = columns

    # graphic-properties (used by style:style family="graphic", applied
    # to draw:frame elements - carries the anchor/alignment of images).
    graphic_props = style_el.find(q("style:graphic-properties"))
    if graphic_props is not None:
        hpos = graphic_props.get(q("style:horizontal-pos"))
        if hpos:
            info.horizontal_pos = hpos

    # table-column-properties (used by style:style family="table-column",
    # applied to table:table-column elements).
    column_props = style_el.find(q("style:table-column-properties"))
    if column_props is not None:
        info.column_width_cm = length_to_cm(column_props.get(q("style:column-width")))

    return info


def build_style_registry(styles_root: ET.Element | None, content_root: ET.Element | None) -> StyleRegistry:
    registry = StyleRegistry()

    def scan(root: ET.Element | None):
        if root is None:
            return
        # office:styles (named styles), office:automatic-styles
        for container_tag in ("office:styles", "office:automatic-styles", "office:master-styles"):
            container = root.find(q(container_tag))
            if container is None:
                continue
            for style_el in container.findall(q("style:style")):
                info = _parse_style_element(style_el)
                if info:
                    registry.add(info)
            # page-layout can also carry columns (rarely used as a
            # fallback when the section does not define its own)
            for layout_el in container.findall(q("style:page-layout")):
                info = _parse_style_element(layout_el, family_override="page-layout")
                if info:
                    registry.add(info)

    scan(styles_root)
    scan(content_root)

    return registry


def build_list_style_registry(styles_root: ET.Element | None, content_root: ET.Element | None) -> dict[str, bool]:
    """Maps list-style name -> True (ordered) / False (unordered),
    looking at the first defined level (spec section 5 'lists')."""
    result: dict[str, bool] = {}

    def scan(root: ET.Element | None):
        if root is None:
            return
        for container_tag in ("office:styles", "office:automatic-styles"):
            container = root.find(q(container_tag))
            if container is None:
                continue
            for list_style_el in container.findall(q("text:list-style")):
                name = list_style_el.get(q("style:name"))
                if not name:
                    continue
                ordered = list_style_el.find(q("text:list-level-style-number")) is not None
                result[name] = ordered

    scan(styles_root)
    scan(content_root)
    return result


def _mapping_to_tag_attrs(mapping) -> tuple[str, dict]:
    if isinstance(mapping, str):
        return mapping, {}
    tag = mapping.get("tag", "p")
    attrs = {}
    if "class" in mapping:
        attrs["class"] = mapping["class"]
    return tag, attrs


def resolve_style_mapping(candidates: list[str], style_map: dict) -> tuple[str, dict] | None:
    """Resolves the list of candidate identifiers (see
    StyleRegistry.resolve_style_candidates) against the user's style_map
    (section 7) and then against the default (section 6).

    Returns None if no candidate matches anything (the caller decides
    the fallback - regular paragraphs fall back to <p>, headings fall
    back to h(N) based on outline-level).

    The user's style_map has full priority over the default, but both
    are tried against the whole inheritance chain before giving up. A
    second, case-insensitive pass covers capitalization variations
    between LibreOffice versions/locales (e.g. 'Text Body' vs 'Text body').
    """
    if not candidates:
        return None

    for name in candidates:
        if name in style_map:
            return _mapping_to_tag_attrs(style_map[name])
    for name in candidates:
        if name in DEFAULT_STYLE_MAP:
            return _mapping_to_tag_attrs(DEFAULT_STYLE_MAP[name])

    lower_style_map = {k.lower(): v for k, v in style_map.items()}
    for name in candidates:
        if name.lower() in lower_style_map:
            return _mapping_to_tag_attrs(lower_style_map[name.lower()])
    lower_default = {k.lower(): v for k, v in DEFAULT_STYLE_MAP.items()}
    for name in candidates:
        if name.lower() in lower_default:
            return _mapping_to_tag_attrs(lower_default[name.lower()])

    return None