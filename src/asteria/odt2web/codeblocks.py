"""Code blocks (section 5 'structure' / section 7 'custom styles').

Treats code blocks as a special case of a paragraph whose style is
mapped (via style_map, sections 6/7) to the "pre" tag - by default, the
LibreOffice native "Preformatted Text" style. Unlike a regular
paragraph:

- several consecutive paragraphs with the same "pre" style are merged
  into a single <pre><code>...</code></pre> block (one line per
  paragraph), instead of becoming several separate <pre> blocks;
- the content is extracted as literal text (inline formatting such as
  bold/italic is ignored) - applying <strong>/<em> inside a code block
  would break copy-paste and most syntax highlighters;
- the language can be indicated in two ways: (a) the style_map's CSS
  class, if it follows the "language-xxx" convention (e.g. dedicated
  per-language ODT styles, like "Code Python" -> {"tag": "pre",
  "class": "language-python"}); or (b) a Markdown-style marker on the
  first line of the block (```python), removed from the final content -
  useful for people who don't want to create an ODT style per language.

The generated HTML (<pre><code class="language-xxx">) follows the
convention adopted by client-side syntax-highlighting libraries
(highlight.js, Prism) and by SSGs' server-side highlighters (e.g. Chroma
in Hugo, Shiki/PrismJS in Eleventy/11ty plugins) - the library does not
do the highlighting itself, it only delivers the markup those tools
expect.
"""
from __future__ import annotations

from .model import CodeBlock, LineBreak, Link, Paragraph, Section, Span, Text
from .styles import resolve_style_mapping


def _literal_text(nodes: list) -> str:
    """Extracts the literal text of a paragraph, ignoring inline
    formatting (bold/italic/links) but preserving manual line breaks as
    '\\n' - used to avoid corrupting code."""
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.value)
        elif isinstance(node, (Span, Link)):
            parts.append(_literal_text(node.children))
        elif isinstance(node, LineBreak):
            parts.append("\n")
    return "".join(parts)


def _strip_language_fence(lines: list[str]) -> tuple[str | None, list[str]]:
    """If the first line is a Markdown-style marker ('```python'),
    removes it and returns the indicated language."""
    if lines and lines[0].strip().startswith("```"):
        lang = lines[0].strip()[3:].strip()
        return (lang or None), lines[1:]
    return None, lines


def _language_from_css_class(css_class: str | None) -> str | None:
    if css_class and css_class.startswith("language-"):
        return css_class[len("language-"):]
    return None


def _merge_children(children: list, style_map: dict) -> list:
    result: list = []
    i = 0
    n = len(children)

    while i < n:
        node = children[i]

        if isinstance(node, Paragraph):
            mapping = resolve_style_mapping(node.style_candidates, style_map)
            tag, attrs = mapping if mapping is not None else ("p", {})
            if tag == "pre":
                css_class = attrs.get("class")
                j = i
                paragraph_lines: list[str] = []
                while j < n and isinstance(children[j], Paragraph):
                    m2 = resolve_style_mapping(children[j].style_candidates, style_map)
                    t2, a2 = m2 if m2 is not None else ("p", {})
                    if t2 != "pre" or a2.get("class") != css_class:
                        break
                    paragraph_lines.append(_literal_text(children[j].children))
                    j += 1

                # each paragraph may contain multiple internal lines
                # (manual line breaks); flatten everything into a list of
                # lines before looking for the language marker.
                lines: list[str] = []
                for para_text in paragraph_lines:
                    lines.extend(para_text.split("\n"))

                fence_lang, lines = _strip_language_fence(lines)
                language = fence_lang or _language_from_css_class(css_class)

                result.append(CodeBlock(
                    code="\n".join(lines), language=language, css_class=css_class,
                ))
                i = j
                continue

        result.append(node)
        i += 1

    return result


def merge_code_blocks(sections: list[Section], style_map: dict) -> None:
    """Applies the merging to all sections of the document, in place."""
    for section in sections:
        section.children = _merge_children(section.children, style_map)
