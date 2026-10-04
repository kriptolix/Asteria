"""Intermediate document model."""


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


# ---------------------------------------------------------------------------
# Inline nodes (text formatting)
# ---------------------------------------------------------------------------

@dataclass
class Text:
    """Plain text, with no additional formatting."""
    value: str


@dataclass
class Span:
    """A run of text with formatting or a named character style."""
    children: list["InlineNode"] = field(default_factory=list)
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    superscript: bool = False
    subscript: bool = False
    code: bool = False  # "Source Text" character style (inline code)
    style_name: Optional[str] = None  # original ODT style name, if any


@dataclass
class Link:
    href: str
    children: list["InlineNode"] = field(default_factory=list)


@dataclass
class LineBreak:
    pass


@dataclass
class NoteRef:
    """Inline reference to a footnote/endnote (numbered marker)."""
    note_id: str
    label: str  # number/symbol displayed, e.g. "1"


InlineNode = Union[Text, Span, Link, LineBreak, NoteRef]


# ---------------------------------------------------------------------------
# Block nodes
# ---------------------------------------------------------------------------

@dataclass
class Paragraph:
    children: list[InlineNode] = field(default_factory=list)
    style_name: Optional[str] = None
    # chain of candidate identifiers (raw name + decoded names from each
    # ancestor via parent-style-name) used to resolve against
    # style_map/DEFAULT_STYLE_MAP - see StyleRegistry.resolve_style_candidates
    style_candidates: list[str] = field(default_factory=list)
    # resolved semantic style (e.g. "Text Body", "Quotation")
    resolved_style: Optional[str] = None
    # the author asked (via the ODT style) for this paragraph to stay on
    # the same page/column as the next block; surfaced by the renderer as
    # a class so SSG-side CSS decides how to honor it.
    keep_with_next: bool = False


@dataclass
class Heading:
    level: int  # 1..6, already normalized
    children: list[InlineNode] = field(default_factory=list)
    style_name: Optional[str] = None
    style_candidates: list[str] = field(default_factory=list)
    # same meaning as Paragraph.keep_with_next; headings default to True
    # unless the ODT style explicitly opts out.
    keep_with_next: bool = False


@dataclass
class ListItem:
    children: list["BlockNode"] = field(default_factory=list)


@dataclass
class List:
    ordered: bool
    items: list[ListItem] = field(default_factory=list)
    style_name: Optional[str] = None


@dataclass
class TableCell:
    children: list["BlockNode"] = field(default_factory=list)
    colspan: int = 1
    rowspan: int = 1
    is_header: bool = False
    covered: bool = False  # cell covered by a preceding rowspan/colspan
    # explicit horizontal alignment authored in the cell's first paragraph
    # ("center" | "right"); None when left/start/justify or not set.
    align: Optional[str] = None


@dataclass
class TableRow:
    cells: list[TableCell] = field(default_factory=list)
    is_header: bool = False


@dataclass
class Table:
    rows: list[TableRow] = field(default_factory=list)
    style_name: Optional[str] = None
    caption: Optional[str] = None
    column_widths: list[Optional[float]] = field(default_factory=list)  # cm; None = unknown


@dataclass
class Image:
    src: str  # original path inside the ODT package (e.g. Pictures/foo.png)
    alt: Optional[str] = None
    caption: Optional[str] = None
    width: Optional[str] = None  # already in a CSS unit (e.g. "8.5cm")
    height: Optional[str] = None
    linked: bool = False  # True = referenced (external) image, not embedded
    # horizontal alignment as authored in the ODT frame's graphic style
    # ("left" | "center" | "right"), when it could be determined -
    # surfaced by the renderer as an "odt-image-align-*" class rather
    # than inline positioning, so SSG-side CSS controls the actual layout.
    align: Optional[str] = None


@dataclass
class PageBreak:
    pass


@dataclass
class Note:
    """A footnote/endnote, with its content, indexed by id."""
    note_id: str
    label: str
    children: list["BlockNode"] = field(default_factory=list)
    kind: str = "footnote"  # "footnote" | "endnote"


@dataclass
class CustomNode:
    """Extension node, handled by a registered renderer (section 17)."""
    name: str  # e.g. "custom:note"
    attributes: dict = field(default_factory=dict)
    children: list["BlockNode"] = field(default_factory=list)


@dataclass
class RawHtml:
    """Literal HTML block."""
    content: str


@dataclass
class CodeBlock:
    """Code block."""
    code: str
    language: Optional[str] = None
    css_class: Optional[str] = None


BlockNode = Union[
    Paragraph, Heading, List, Table, Image, PageBreak, CustomNode, RawHtml,
    CodeBlock,
]


# ---------------------------------------------------------------------------
# Section / document structure
# ---------------------------------------------------------------------------

@dataclass
class Section:
    children: list[BlockNode] = field(default_factory=list)
    columns: int = 1
    column_gap: Optional[str] = None  # CSS unit, e.g. "1.27cm"
    column_rule: Optional[str] = None  # e.g. "1px solid #000"
    style_name: Optional[str] = None
    name: Optional[str] = None


@dataclass
class Metadata:
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    created: Optional[str] = None
    modified: Optional[str] = None
    language: Optional[str] = None


@dataclass
class Document:
    sections: list[Section] = field(default_factory=list)
    notes: dict[str, Note] = field(default_factory=dict)
    metadata: Metadata = field(default_factory=Metadata)
    front_matter: Optional[dict] = None
    warnings: list[str] = field(default_factory=list)