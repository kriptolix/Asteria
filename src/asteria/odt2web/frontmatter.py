"""Recognizes a front matter block."""


from __future__ import annotations

from .model import LineBreak, Link, Paragraph, PageBreak, Section, Span, Text

DELIMITER = "---"


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


def _parse_kv_lines(lines: list[str]) -> dict[str, str] | None:

    data: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            # line outside the "key: value" pattern -> not valid front matter
            return None
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            return None
        data[key] = value
    return data or None


def extract_front_matter(section: Section) -> dict[str, str] | None:

    children = section.children

    start_idx = 0
    while start_idx < len(children):
        node = children[start_idx]
        if isinstance(node, PageBreak):
            # page breaks before the content (common when the document's
            # first paragraph has "break before" set in its style) are
            # just skipped during the search.
            start_idx += 1
            continue
        if not isinstance(node, Paragraph):
            # something other than a paragraph/page break (list, table,
            # image...) before any text: there is no front matter to
            # look for here.
            return None
        if _plain_text(node.children).strip() != "":
            break
        start_idx += 1
    else:
        return None  # all leading nodes were empty/page breaks

    if start_idx >= len(children):
        return None

    # --- Case 1: consecutive paragraphs, one per line -------------------
    first_text = _plain_text(children[start_idx].children).strip()
    if first_text == DELIMITER:
        end_idx = None
        for i in range(start_idx + 1, len(children)):
            node = children[i]
            if not isinstance(node, Paragraph):
                break
            if _plain_text(node.children).strip() == DELIMITER:
                end_idx = i
                break
        if end_idx is not None:
            lines = [
                _plain_text(node.children)
                for node in children[start_idx + 1:end_idx]
                if isinstance(node, Paragraph)
            ]
            data = _parse_kv_lines(lines)
            if data is not None:
                del children[start_idx:end_idx + 1]
                return data

    # --- Case 2: a single paragraph with manual line breaks -------------
    text_with_breaks = _plain_text(children[start_idx].children, line_break_as_newline=True)
    lines = text_with_breaks.split("\n")
    if len(lines) >= 3 and lines[0].strip() == DELIMITER:
        for j in range(1, len(lines)):
            if lines[j].strip() == DELIMITER:
                data = _parse_kv_lines(lines[1:j])
                if data is not None:
                    del children[start_idx]
                    return data
                break

    return None
