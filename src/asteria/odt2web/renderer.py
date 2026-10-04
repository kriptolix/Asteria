"""Produces semantic HTML."""


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .model import (
    CodeBlock, CustomNode, Document, Heading, Image, Link, LineBreak, List,
    NoteRef, PageBreak, Paragraph, RawHtml, Section, Span, Table, Text,
)
from .security import escape_attr, escape_text, sanitize_url
from .styles import length_to_cm, resolve_style_mapping
from .tables import analyze_table

CustomRenderer = Callable[[CustomNode, "RenderContext"], str]


@dataclass
class RenderContext:
    style_map: dict
    custom_renderers: dict[str, CustomRenderer] = field(default_factory=dict)
    features: set[str] = field(default_factory=set)
    columns: dict[int, tuple[str | None, str | None]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    allow_raw_html: bool = False


def _render_attrs(attrs: dict) -> str:
    if not attrs:
        return ""
    parts = []
    for key, value in attrs.items():
        parts.append(f'{key}="{escape_attr(str(value))}"')
    return " " + " ".join(parts)


def _merge_class(attrs: dict, *extra: str) -> dict:
    """Returns a copy of attrs with the extra classes appended to any
    class already coming from the style map."""
    merged = dict(attrs)
    classes = " ".join(filter(None, [merged.get("class"), *extra]))
    if classes:
        merged["class"] = classes
    return merged


# ---------------------------------------------------------------------------
# Inline
# ---------------------------------------------------------------------------

def render_inline(nodes: list, ctx: RenderContext) -> str:
    return "".join(_render_inline_node(node, ctx) for node in nodes)


def _slugify(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-") or "style"


def _render_inline_node(node, ctx: RenderContext) -> str:
    if isinstance(node, Text):
        return escape_text(node.value)

    if isinstance(node, Span):
        inner = render_inline(node.children, ctx)
        if node.bold:
            inner = f"<strong>{inner}</strong>"
        if node.italic:
            inner = f"<em>{inner}</em>"
        if node.underline:
            inner = f"<u>{inner}</u>"
        if node.strikethrough:
            inner = f"<s>{inner}</s>"
        if node.superscript:
            inner = f"<sup>{inner}</sup>"
        if node.subscript:
            inner = f"<sub>{inner}</sub>"
        if node.code:
            ctx.features.add("inline-code")
            inner = f"<code>{inner}</code>"
        elif not any([node.bold, node.italic, node.underline, node.strikethrough,
                      node.superscript, node.subscript]) and node.style_name:
            # character style with no recognized formatting: preserved as
            # a CSS class, to allow later customization by the user.
            cls = f"odt-char-{_slugify(node.style_name)}"
            inner = f'<span class="{cls}">{inner}</span>'
        return inner

    if isinstance(node, Link):
        inner = render_inline(node.children, ctx)
        href = sanitize_url(node.href)
        if href is None:
            ctx.warnings.append(f"Link with unsafe/invalid URL was removed: {node.href!r}")
            return inner
        return f'<a href="{href}">{inner}</a>'

    if isinstance(node, LineBreak):
        return "<br>"

    if isinstance(node, NoteRef):
        ctx.features.add("notes")
        note_id = escape_attr(node.note_id)
        label = escape_text(node.label)
        return (
            f'<sup id="fnref-{note_id}" class="odt-note-ref">'
            f'<a href="#{note_id}">{label}</a></sup>'
        )

    return ""


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

def render_block(node, ctx: RenderContext) -> str:
    if isinstance(node, Paragraph):
        return _render_paragraph(node, ctx)
    if isinstance(node, Heading):
        return _render_heading(node, ctx)
    if isinstance(node, List):
        return _render_list(node, ctx)
    if isinstance(node, Table):
        return _render_table(node, ctx)
    if isinstance(node, Image):
        return _render_image(node, ctx)
    if isinstance(node, PageBreak):
        return _render_page_break(node, ctx)
    if isinstance(node, CustomNode):
        return _render_custom(node, ctx)
    if isinstance(node, RawHtml):
        return _render_raw_html(node, ctx)
    if isinstance(node, CodeBlock):
        return _render_code_block(node, ctx)
    return ""


def _render_paragraph(node: Paragraph, ctx: RenderContext) -> str:
    mapping = resolve_style_mapping(node.style_candidates, ctx.style_map)
    tag, attrs = mapping if mapping is not None else ("p", {})
    if tag.startswith("custom:"):
        renderer = ctx.custom_renderers.get(tag)
        if renderer is not None:
            return renderer(node, ctx)
        ctx.warnings.append(
            f"Style '{node.style_name}' mapped to '{tag}', but no "
            "renderer was registered (see register_renderer); falling back to <p>"
        )
        tag, attrs = "p", {}
    if tag == "blockquote":
        ctx.features.add("blockquote")
    if tag == "pre":
        ctx.features.add("pre")
    if node.keep_with_next:
        # the author asked for this block to stay with the next one; we
        # only surface that as a class and let CSS decide how to honor it.
        ctx.features.add("keep-with-next")
        attrs = _merge_class(attrs, "odt-keep-with-next")
    inner = render_inline(node.children, ctx)
    return f"<{tag}{_render_attrs(attrs)}>{inner}</{tag}>\n"


def _render_heading(node: Heading, ctx: RenderContext) -> str:
    mapping = resolve_style_mapping(node.style_candidates, ctx.style_map)
    if mapping is not None:
        # an explicit mapping is honored even when it does not point to a
        # heading tag (section 7).
        tag, attrs = mapping
    else:
        tag, attrs = f"h{min(node.level + 1, 6)}", {}
    if node.keep_with_next:
        ctx.features.add("keep-with-next")
        attrs = _merge_class(attrs, "odt-keep-with-next")
    inner = render_inline(node.children, ctx)
    return f"<{tag}{_render_attrs(attrs)}>{inner}</{tag}>\n"


def _render_list(node: List, ctx: RenderContext) -> str:
    ctx.features.add("list")
    tag = "ol" if node.ordered else "ul"
    if node.ordered:
        ctx.features.add("ordered-list")
    items_html = []
    for item in node.items:
        inner = "".join(render_block(c, ctx) for c in item.children)
        items_html.append(f"<li>{inner}</li>\n")
    return f"<{tag}>\n{''.join(items_html)}</{tag}>\n"


def _render_table(node: Table, ctx: RenderContext) -> str:
    """Renders a table plus a few structural hints for the SSG (not the
    original look): simple/complex grid, size, header rows, relative
    column shares and explicit cell alignment."""
    ctx.features.add("table")
    hints = analyze_table(node)
    table_attrs = {
        "class": "odt-table " + ("odt-table-simple" if hints.simple else "odt-table-complex"),
        "data-cols": hints.cols,
        "data-rows": hints.rows,
    }
    if hints.header_rows:
        table_attrs["data-header-rows"] = hints.header_rows

    header_rows = [r for r in node.rows if r.is_header]
    body_rows = [r for r in node.rows if not r.is_header]

    def render_row(row) -> str:
        cells_html = []
        for cell in row.cells:
            if cell.covered:
                continue
            cell_tag = "th" if cell.is_header else "td"
            attrs = {}
            if cell.is_header:
                attrs["scope"] = "col"
            if cell.colspan > 1:
                attrs["colspan"] = cell.colspan
            if cell.rowspan > 1:
                attrs["rowspan"] = cell.rowspan
            if cell.align:
                ctx.features.add("table-align")
                attrs["class"] = f"odt-align-{cell.align}"
            inner = "".join(render_block(c, ctx) for c in cell.children)
            cells_html.append(f"<{cell_tag}{_render_attrs(attrs)}>{inner}</{cell_tag}>")
        return f"<tr>{''.join(cells_html)}</tr>\n"

    parts = [f"<table{_render_attrs(table_attrs)}>\n"]
    if node.caption:
        ctx.features.add("table-caption")
        parts.append(f"<caption>{escape_text(node.caption)}</caption>\n")
    if hints.col_shares:
        cols = "".join(f'<col data-share="{share}">' for share in hints.col_shares)
        parts.append(f"<colgroup>{cols}</colgroup>\n")
    if header_rows:
        parts.append("<thead>\n")
        parts.extend(render_row(r) for r in header_rows)
        parts.append("</thead>\n")
    parts.append("<tbody>\n")
    parts.extend(render_row(r) for r in body_rows)
    parts.append("</tbody>\n")
    parts.append("</table>\n")
    return "".join(parts)


# width (or, failing that, height) thresholds in cm used to bucket an
# image into a coarse size class - just enough for SSG-side CSS to tell
# "this was a small/medium/large image in the source document" apart,
# without hard-coding the document's original print dimensions.
_IMAGE_SIZE_THRESHOLDS_CM = (("small", 6.0), ("medium", 12.0))  # else "large"

def _image_size_class(node: Image) -> str | None:
    size_cm = length_to_cm(node.width) or length_to_cm(node.height)
    if size_cm is None:
        return None
    for label, threshold in _IMAGE_SIZE_THRESHOLDS_CM:
        if size_cm <= threshold:
            return f"odt-image-{label}"
    return "odt-image-large"


def _image_orientation_class(node: Image) -> str | None:
    width_cm = length_to_cm(node.width)
    height_cm = length_to_cm(node.height)
    if width_cm is None or height_cm is None:
        return None
    if abs(width_cm - height_cm) < 0.05:
        return "odt-image-square"
    return "odt-image-landscape" if width_cm > height_cm else "odt-image-portrait"


def _image_classes(node: Image) -> list[str]:
    classes = ["odt-image"]
    for cls in (_image_size_class(node), _image_orientation_class(node)):
        if cls:
            classes.append(cls)
    if node.align:
        classes.append(f"odt-image-align-{node.align}")
    return classes


def _render_image(node: Image, ctx: RenderContext) -> str:
    ctx.features.add("image")
    if node.linked:
        src = sanitize_url(node.src)
        if src is None:
            ctx.warnings.append(f"Referenced image with unsafe URL was removed: {node.src!r}")
            return ""
    else:
        src = escape_attr(node.src)

    # no inline width/height: the source dimensions are only reflected as
    # coarse classes (size, orientation, alignment), so the SSG's CSS
    # decides the real layout (an inline height would also fight the
    # generated "max-width: 100%; height: auto" rule on narrow screens).
    alt = escape_attr(node.alt or "")
    classes = _image_classes(node)

    if node.caption:
        # classes go on the <figure> (not the <img>), since alignment and
        # sizing are block-level concerns once there's a caption below it.
        ctx.features.add("figure")
        img_tag = f'<img src="{src}" alt="{alt}">'
        figure_class = escape_attr(" ".join(classes))
        return (
            f'<figure class="{figure_class}">{img_tag}'
            f"<figcaption>{escape_text(node.caption)}</figcaption></figure>\n"
        )

    img_class = escape_attr(" ".join(classes))
    return f'<img src="{src}" alt="{alt}" class="{img_class}">\n'


def _render_page_break(node: PageBreak, ctx: RenderContext) -> str:
    ctx.features.add("page-break")
    return '<hr class="odt-page-break">\n'


def _render_custom(node: CustomNode, ctx: RenderContext) -> str:
    renderer = ctx.custom_renderers.get(node.name)
    if renderer is None:
        ctx.warnings.append(f"No renderer registered for '{node.name}'; element ignored")
        return ""
    return renderer(node, ctx)


def _render_raw_html(node: RawHtml, ctx: RenderContext) -> str:
    """Emits a literal ':::html' block (see rawhtml.py). Only passes the
    content through unescaped if allow_raw_html is explicitly enabled
    (section 13 - the .odt is treated as untrusted input by default;
    this is an opt-in escape hatch)."""
    ctx.features.add("raw-html")
    if not ctx.allow_raw_html:
        ctx.warnings.append(
            "':::html' block found, but allow_raw_html=False; the "
            "content was escaped and shown as text instead of HTML"
        )
        return f"<pre class=\"odt-raw-html-disabled\">{escape_text(node.content)}</pre>\n"
    return node.content.strip() + "\n"


def _render_code_block(node: CodeBlock, ctx: RenderContext) -> str:
    """Renders a merged code block (see codeblocks.py) as
    <pre><code class="language-xxx">...</code></pre> - the format
    expected by syntax highlighters like highlight.js, Prism or Shiki.
    This library does not do the highlighting itself; it only delivers
    the markup."""
    ctx.features.add("pre")
    ctx.features.add("code-block")
    css_class = node.css_class
    if node.language:
        css_class = f"language-{node.language}"
    class_attr = f' class="{escape_attr(css_class)}"' if css_class else ""
    return f"<pre><code{class_attr}>{escape_text(node.code)}</code></pre>\n"


# ---------------------------------------------------------------------------
# Sections / notes / document
# ---------------------------------------------------------------------------

def render_section(section: Section, ctx: RenderContext) -> str:
    content = "".join(render_block(c, ctx) for c in section.children)
    if section.columns and section.columns > 1:
        ctx.features.add("columns")
        if section.columns not in ctx.columns:
            ctx.columns[section.columns] = (section.column_gap, section.column_rule)
        cls = f"odt-columns odt-columns-{section.columns}"
        return f'<section class="{cls}">\n{content}</section>\n'
    return content


def render_notes(document: Document, ctx: RenderContext) -> str:
    if not document.notes:
        return ""
    ctx.features.add("notes")
    items = []
    for note_id, note in document.notes.items():
        inner = "".join(render_block(c, ctx) for c in note.children) or "<p></p>\n"
        note_id_attr = escape_attr(note_id)
        items.append(
            f'<li id="{note_id_attr}">{inner}'
            f'<a href="#fnref-{note_id_attr}" class="odt-note-backref">&#8617;</a></li>\n'
        )
    return f'<section class="odt-notes">\n<ol>\n{"".join(items)}</ol>\n</section>\n'


def render_front_matter(front_matter: dict | None) -> str:
    """Renders the extracted front matter (see frontmatter.py) as:

        <div class="ssg-frontmatter" data-ssg="frontmatter">
          <meta data-key="title" content="...">
          ...
        </div>
    """
    if not front_matter:
        return ""
    lines = ['<div class="ssg-frontmatter" data-ssg="frontmatter">']
    for key, value in front_matter.items():
        lines.append(
            f'  <meta data-key="{escape_attr(key)}" content="{escape_attr(value)}">'
        )
    lines.append("</div>")
    return "\n".join(lines) + "\n"


def render_document(
    document: Document,
    *,
    style_map: dict | None = None,
    custom_renderers: dict[str, CustomRenderer] | None = None,
    allow_raw_html: bool = False,
) -> tuple[str, RenderContext]:
    """Renders the whole document (front matter + all sections + notes)
    and returns (body_html, context) - the context carries the
    `features` used, needed by the CSS generator (section 9)."""
    ctx = RenderContext(
        style_map=style_map or {}, custom_renderers=custom_renderers or {},
        allow_raw_html=allow_raw_html,
    )
    parts = [render_front_matter(getattr(document, "front_matter", None))]
    parts.extend(render_section(section, ctx) for section in document.sections)
    parts.append(render_notes(document, ctx))
    return "".join(parts), ctx


def wrap_full_document(body_html: str, css: str | None, metadata) -> str:
    """Wraps the fragment in a complete HTML document (section 12)."""
    lang = metadata.language or "pt"
    head_parts = ['<meta charset="utf-8">']
    if metadata.title:
        head_parts.append(f"<title>{escape_text(metadata.title)}</title>")
    if metadata.author:
        head_parts.append(f'<meta name="author" content="{escape_attr(metadata.author)}">')
    if metadata.description:
        head_parts.append(f'<meta name="description" content="{escape_attr(metadata.description)}">')
    if metadata.keywords:
        head_parts.append(
            f'<meta name="keywords" content="{escape_attr(", ".join(metadata.keywords))}">'
        )
    head_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    if css is not None:
        head_parts.append('<link rel="stylesheet" href="style.css">')

    head = "\n  ".join(head_parts)
    return (
        "<!doctype html>\n"
        f'<html lang="{escape_attr(lang)}">\n'
        "<head>\n"
        f"  {head}\n"
        "</head>\n"
        "<body>\n"
        f"{body_html}"
        "</body>\n"
        "</html>\n"
    )