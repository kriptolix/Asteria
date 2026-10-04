"""Recognizes a block delimited by markers."""


from __future__ import annotations

from .model import LineBreak, Link, Paragraph, RawHtml, Span, Text

START_MARKER = ":::html"
END_MARKER = ":::"

# common typographic substitutions that LibreOffice's autocorrect applies
# while typing (straight quotes -> curly quotes, etc.) which would break
# HTML such as tag attributes (href="...") if not reverted inside a block
# explicitly marked as code/HTML.
_TYPOGRAPHY_FIXUPS = {
    "\u201c": '"', "\u201d": '"',  # curly double quotes -> straight
    "\u2018": "'", "\u2019": "'",  # curly single quotes -> straight
    "\u00a0": " ",  # non-breaking space -> regular space
    "\u2026": "...",  # ellipsis -> three dots
}


def _normalize_typography(text: str) -> str:
    for src, dst in _TYPOGRAPHY_FIXUPS.items():
        text = text.replace(src, dst)
    return text


def _plain_text(nodes: list, *, line_break_as_newline: bool = False) -> str:
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.value)
        elif isinstance(node, (Span, Link)):
            parts.append(_plain_text(node.children, line_break_as_newline=line_break_as_newline))
        elif isinstance(node, LineBreak):
            parts.append("\n" if line_break_as_newline else " ")
    return "".join(parts)


def extract_raw_html_blocks(children: list) -> list:
    """Walks a list of BlockNode, replacing blocks delimited by
    ':::html' / ':::' with a single RawHtml node. Does not mutate the
    original list; returns a new list."""
    result: list = []
    i = 0
    n = len(children)

    while i < n:
        node = children[i]

        if isinstance(node, Paragraph):
            text = _plain_text(node.children).strip()

            # --- Case 1: consecutive paragraphs -------------------------
            if text == START_MARKER:
                end_idx = None
                for j in range(i + 1, n):
                    sibling = children[j]
                    if not isinstance(sibling, Paragraph):
                        break
                    if _plain_text(sibling.children).strip() == END_MARKER:
                        end_idx = j
                        break
                if end_idx is not None:
                    lines = [
                        _plain_text(c.children)
                        for c in children[i + 1:end_idx]
                        if isinstance(c, Paragraph)
                    ]
                    content = _normalize_typography("\n".join(lines))
                    result.append(RawHtml(content=content))
                    i = end_idx + 1
                    continue

            # --- Case 2: a single paragraph with manual line breaks -----
            text_with_breaks = _plain_text(node.children, line_break_as_newline=True)
            lines = text_with_breaks.split("\n")
            if len(lines) >= 3 and lines[0].strip() == START_MARKER:
                for j in range(1, len(lines)):
                    if lines[j].strip() == END_MARKER:
                        content = _normalize_typography("\n".join(lines[1:j]))
                        result.append(RawHtml(content=content))
                        break
                else:
                    result.append(node)
                i += 1
                continue

        result.append(node)
        i += 1

    return result
