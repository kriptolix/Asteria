"""
Interpretation of the standardized front matter block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape

from .errors import Diagnostics

KNOWN_FIELDS = {
    "title",
    "date",
    "author",
    "tags",
    "categories",
    "description",
    "slug",
    "variant",
    "toc",
    "navigation",
    "lang",
    "template",
    "featured",
    "cover",
    "menu_title",
    "nav_title",
}

FRONTMATTER_BLOCK_RE = re.compile(
    r'<div[^>]*class="ssg-frontmatter"[^>]*>(?P<inner>.*?)</div>',
    re.DOTALL,
)
META_TAG_RE = re.compile(
    r'<meta[^>]*data-key="(?P<key>[^"]*)"[^>]*content="(?P<value>[^"]*)"[^>]*>',
    re.DOTALL,
)


@dataclass
class Frontmatter:
    title: str | None = None
    date: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    description: str = ""
    slug: str | None = None
    variant: str | None = None  
    # Nome de um template do tema (ex: "wiki.html") a usar no lugar do
    # padrão baseado no tipo do documento (page.html / post.html). None
    # mantém o padrão — ver document.Document.template e
    # build._resolve_template_name.
    template: str | None = None
    toc: bool = True  
    navigation: bool = False  
    lang: str | None = None
    # Marca a página/post para aparecer em `site.featured_pages` /
    # `site.featured_posts` — ver document.Document.featured e
    # build._document_context / build.run_build.
    featured: bool = False
    # Caminho (absoluto, a partir da raiz do site) de uma imagem de capa
    # em static/, ex: "/covers/meu-post.jpg". Propositalmente NUNCA
    # extraída do corpo do .odt — ver document.Document.cover. None
    # quando não informado.
    cover: str | None = None
    # Rótulo alternativo a usar quando este documento é referenciado por
    # um `page:` do `menu:` (site.yaml) SEM `title:` explícito — permite
    # que o link do menu diga algo mais curto/diferente do título real
    # da página (ex: "Sobre" no menu vs. "Sobre a Empresa XYZ Corp" como
    # título), continuando traduzível por idioma (é front matter de cada
    # documento, não uma string fixa em site.yaml). Ver build._build_menu,
    # onde a ordem de prioridade é: title: do menu > menu_title: do
    # documento > title: do documento. None quando não informado — ver
    # document.Document.menu_title.
    menu_title: str | None = None
    # Alternate label to use when this document is referenced by a `nav:`
    # entry (site.yaml) WITHOUT an explicit override title. Mirrors
    # `menu_title` above, but for `nav:` instead of `menu:` — same
    # priority chain (nav entry's own title > nav_title: > title:) and
    # same rationale: living in front matter makes it translatable per
    # document, instead of a single fixed string hardcoded in site.yaml's
    # `nav:` (which can't vary per language). None when not informed —
    # see document.Document.nav_title and nav._resolve.
    nav_title: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default=None):
        return getattr(self, key, self.extra.get(key, default))


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in ("false", "no", "0", "off")


def extract_frontmatter(
    html: str, source: str, diagnostics: Diagnostics
) -> tuple[Frontmatter, str]:
    
    match = FRONTMATTER_BLOCK_RE.search(html)
    if not match:
        return Frontmatter(), html

    inner = match.group("inner")
    raw_fields: dict[str, str] = {}
    for meta_match in META_TAG_RE.finditer(inner):
        key = unescape(meta_match.group("key")).strip().lower()
        value = unescape(meta_match.group("value")).strip()
        if key in raw_fields:
            diagnostics.warning(f"Duplicate front matter field: '{key}'.", source=source)
        raw_fields[key] = value

    for key in raw_fields:
        if key not in KNOWN_FIELDS:
            diagnostics.warning(
                f"Unknown front matter field: '{key}' (preserved in extra).",
                source=source,
            )

    fm = Frontmatter(
        title=raw_fields.get("title"),
        date=raw_fields.get("date"),
        author=raw_fields.get("author"),
        tags=_split_list(raw_fields.get("tags", "")),
        categories=_split_list(raw_fields.get("categories", "")),
        description=raw_fields.get("description", ""),
        slug=raw_fields.get("slug"),
        variant=raw_fields.get("variant"),
        template=raw_fields.get("template") or None,
        toc=_parse_bool(raw_fields.get("toc"), default=True),
        navigation=_parse_bool(raw_fields.get("navigation"), default=False),
        lang=raw_fields.get("lang") or None,
        featured=_parse_bool(raw_fields.get("featured"), default=False),
        cover=raw_fields.get("cover") or None,
        menu_title=raw_fields.get("menu_title") or None,
        nav_title=raw_fields.get("nav_title") or None,
        extra={k: v for k, v in raw_fields.items() if k not in KNOWN_FIELDS},
    )

    html_without_block = html[: match.start()] + html[match.end() :]
    return fm, html_without_block.strip()