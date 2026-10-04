"""CSS generator (spec section 9).

Generates only the rules needed for the resources actually used in the
document (columns, tables, notes, etc.), as detected by
RenderContext.features during rendering.
"""
from __future__ import annotations

from .renderer import RenderContext

_RULES: dict[str, str] = {
    "blockquote": (
        "blockquote {\n"
        "  margin: 1rem 0;\n"
        "  padding-left: 1rem;\n"
        "  border-left: 3px solid #ccc;\n"
        "  font-style: italic;\n"
        "}\n"
    ),
    "pre": (
        "pre {\n"
        "  background: #f5f5f5;\n"
        "  padding: 1rem;\n"
        "  overflow-x: auto;\n"
        "  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;\n"
        "}\n"
    ),
    "code-block": (
        "pre code {\n"
        "  display: block;\n"
        "  font-family: inherit;\n"
        "  white-space: pre;\n"
        "  tab-size: 4;\n"
        "}\n"
    ),
    "inline-code": (
        "code {\n"
        "  background: #f0f0f0;\n"
        "  padding: 0.15em 0.4em;\n"
        "  border-radius: 3px;\n"
        "  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;\n"
        "  font-size: 0.9em;\n"
        "}\n"
        "pre code {\n"
        "  background: none;\n"
        "  padding: 0;\n"
        "  border-radius: 0;\n"
        "  font-size: inherit;\n"
        "}\n"
    ),
    "table": (
        "table {\n"
        "  border-collapse: collapse;\n"
        "  width: 100%;\n"
        "}\n"
        "th, td {\n"
        "  border: 1px solid #ccc;\n"
        "  padding: 0.5rem;\n"
        "  text-align: left;\n"
        "  vertical-align: top;\n"
        "}\n"
        "thead th {\n"
        "  background: #f0f0f0;\n"
        "}\n"
    ),
    "table-align": (
        ".odt-align-center {\n"
        "  text-align: center;\n"
        "}\n"
        ".odt-align-right {\n"
        "  text-align: right;\n"
        "}\n"
    ),
    "table-caption": (
        "caption {\n"
        "  caption-side: top;\n"
        "  text-align: left;\n"
        "  font-size: 0.9rem;\n"
        "  color: #555;\n"
        "  margin-bottom: 0.25rem;\n"
        "}\n"
    ),
    "keep-with-next": (
        ".odt-keep-with-next {\n"
        "  break-after: avoid;\n"
        "}\n"
    ),
    "figure": (
        "figure {\n"
        "  margin: 1rem 0;\n"
        "}\n"
        "figcaption {\n"
        "  font-size: 0.9rem;\n"
        "  color: #555;\n"
        "  margin-top: 0.25rem;\n"
        "}\n"
    ),
    "image": (
        "img {\n"
        "  max-width: 100%;\n"
        "  height: auto;\n"
        "}\n"
    ),
    "notes": (
        ".odt-notes {\n"
        "  margin-top: 2rem;\n"
        "  padding-top: 1rem;\n"
        "  border-top: 1px solid #ccc;\n"
        "  font-size: 0.9rem;\n"
        "}\n"
        ".odt-note-backref {\n"
        "  margin-left: 0.25rem;\n"
        "  text-decoration: none;\n"
        "}\n"
    ),
    "page-break": (
        ".odt-page-break {\n"
        "  border: 0;\n"
        "  margin: 2rem 0;\n"
        "}\n"
        "@media print {\n"
        "  .odt-page-break {\n"
        "    break-after: page;\n"
        "  }\n"
        "}\n"
    ),
    "raw-html": (
        "iframe {\n"
        "  max-width: 100%;\n"
        "  border: 0;\n"
        "}\n"
        ".odt-raw-html-disabled {\n"
        "  white-space: pre-wrap;\n"
        "  background: #fff3cd;\n"
        "  border: 1px solid #ffe69c;\n"
        "  padding: 0.75rem;\n"
        "  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;\n"
        "  font-size: 0.85rem;\n"
        "}\n"
    ),
    "list": (
        "ul, ol {\n"
        "  padding-left: 1.5rem;\n"
        "}\n"
        "li > ul, li > ol {\n"
        "  margin: 0.25rem 0;\n"
        "}\n"
    ),
}

# stable emission order, independent of insertion order in the set
_FEATURE_ORDER = [
    "image", "figure", "blockquote", "pre", "code-block", "inline-code",
    "list", "table", "table-align", "table-caption", "keep-with-next",
    "notes", "page-break", "raw-html",
]

# Flow rules for multi-column sections. Vertical spacing is expressed only
# as margin-bottom: a margin-top is not truncated at the very start of the
# container, so a column that starts with a heading would begin lower than
# the columns that start with plain text. Extra space before a heading is
# given to the preceding block instead.
_COLUMNS_FLOW = (
    ".odt-columns > * {\n"
    "  margin-block: 0 1rem;\n"
    "}\n"
    ".odt-columns > p {\n"
    "  orphans: 2;\n"
    "  widows: 2;\n"
    "}\n"
    ".odt-columns > :has(+ :is(h1, h2, h3, h4, h5, h6)) {\n"
    "  margin-block-end: 2rem;\n"
    "}\n"
)


def _columns_css(ctx: RenderContext) -> str:
    if not ctx.columns:
        return ""
    parts = [_COLUMNS_FLOW]
    for count in sorted(ctx.columns):
        gap, rule = ctx.columns[count]
        gap = gap or "2rem"
        decls = [f"  column-count: {count};", f"  column-gap: {gap};"]
        if rule:
            decls.append(f"  column-rule: {rule};")
        parts.append(f".odt-columns-{count} {{\n" + "\n".join(decls) + "\n}\n")
    return "".join(parts)


def generate_css(ctx: RenderContext) -> str:
    blocks: list[str] = []
    for feature in _FEATURE_ORDER:
        if feature in ctx.features and feature in _RULES:
            blocks.append(_RULES[feature])
    columns_css = _columns_css(ctx)
    if columns_css:
        blocks.append(columns_css)
    return "\n".join(block.rstrip("\n") for block in blocks) + ("\n" if blocks else "")