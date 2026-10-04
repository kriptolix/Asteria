"""
Document model exposed to templates.
`Document` is the common base between `Page` and `Post`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from markupsafe import Markup

from .converter import ExtractedImage
from .frontmatter import Frontmatter
from .urls import slugify


@dataclass
class TocEntry:
    id: str
    title: str
    level: int
    children: list["TocEntry"] = field(default_factory=list)


@dataclass
class Document:    

    id: str  # filename without extension — unique identifier
    kind: str  # "page" or "post"
    source_path: Path
    frontmatter: Frontmatter
    content_html: str  # Final HTML final
    raw_content_html: str  # HTML before resolve refs

    slug: str = ""
    url: str = ""
    toc: list[TocEntry] = field(default_factory=list)
    images: list[ExtractedImage] = field(default_factory=list)

    previous: "Document | None" = None
    next: "Document | None" = None
    manual_excerpt: str | None = None
    excerpt_length: int = 280
    excerpt_enabled: bool = True

    # -- i18n -----------------------------------------------------------
    lang: str = ""    
    translation_key: str = ""    
    translations: dict[str, "Document"] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.translation_key:
            self.translation_key = self.id
        if not self.slug:            
            self.slug = self.frontmatter.slug or slugify(self.translation_key)

    
    @property
    def title(self) -> str:
        return self.frontmatter.title or self.id

    @property
    def date(self) -> str | None:
        return self.frontmatter.date

    @property
    def author(self) -> str | None:
        return self.frontmatter.author

    @property
    def tags(self) -> list[str]:
        return self.frontmatter.tags

    @property
    def categories(self) -> list[str]:
        return self.frontmatter.categories

    @property
    def description(self) -> str:
        return self.frontmatter.description

    @property
    def variant(self) -> str | None:
        """CSS variant to use for this document (e.g., 'dark'), or
        None to use the site's default variant."""
        return self.frontmatter.variant

    @property
    def featured(self) -> bool:
        """`featured: true` no front matter — usado por build.run_build
        para popular `site.featured_pages` / `site.featured_posts`."""
        return self.frontmatter.featured

    @property
    def cover(self) -> str | None:
        """Caminho da imagem de capa (`cover:` no front matter), ex:
        "/covers/meu-post.jpg" — um asset em static/, não uma imagem
        extraída do corpo do .odt (essas continuam só em `content`). None
        quando o documento não define capa. Aceita o valor sem a barra
        inicial no front matter (ex: `cover: covers/foo.jpg`) e
        normaliza aqui, mesmo critério usado pelo `asset()` do tema
        (ver templating.apply_asset_manifest)."""
        value = self.frontmatter.cover
        if not value:
            return None
        return value if value.startswith("/") else f"/{value}"

    @property
    def menu_title(self) -> str | None:
        """`menu_title:` no front matter — rótulo alternativo a usar no
        menu quando o próprio título do documento não é o texto ideal
        pro link (ex: título longo demais). Raw passthrough (None quando
        não informado) — quem decide a prioridade final entre isso,
        `title:` do menu, e `.title` do documento é build._build_menu."""
        return self.frontmatter.menu_title

    @property
    def nav_title(self) -> str | None:
        """`nav_title:` front matter field — alternate label to use in
        `nav:` (site.yaml) when this document's own title isn't the
        ideal link text. Same role as `menu_title`, but for `nav:`
        instead of `menu:` — see nav._resolve, where the priority order
        is: this nav entry's own explicit title > this document's
        `nav_title:` > this document's `title:`."""
        return self.frontmatter.nav_title

    @property
    def template(self) -> str | None:
        """Nome do arquivo de template do tema (ex: 'wiki.html') a usar
        na renderização deste documento, vindo de `template:` no front
        matter. None mantém o padrão de acordo com a localização do
        documento (page.html para páginas, post.html para posts) — ver
        build._resolve_template_name."""
        return self.frontmatter.template

    @property
    def toc_enabled(self) -> bool:
        """Automatic table of contents (TOC) for this page. Do not confuse it with the `toc` 
        field (the already constructed tree of headings) of this same class."""
        return self.frontmatter.toc

    @property
    def navigation_enabled(self) -> bool:
        """Navigation sidebar (`nav:` from site.yaml) on this page."""
        return self.frontmatter.navigation

    @property
    def content(self) -> str:
        return self.content_html

    @property
    def excerpt(self) -> str:
        if not self.excerpt_enabled:
            # Desligado: description se houver, senão apenas o título.
            return self.frontmatter.description or self.title

        # Ligado: se houver marcação [[more]] explícita, respeita o autor.
        if self.manual_excerpt is not None:
            # manual_excerpt is a genuine HTML fragment — a prefix of
            # content_html, already through the trusted conversion
            # pipeline (see references.split_at_more_marker) — not plain
            # text like the auto-generated branch below. Wrapped in
            # Markup so `{{ post.excerpt }}` renders it as HTML directly;
            # without this, Jinja's autoescaping (on by default — see
            # templating.create_environment) would show the tags
            # (`<p>`, etc.) as literal visible text instead of an actual
            # paragraph.
            return Markup(self.manual_excerpt)

        # Sem marcação: sempre gera o excerpt padrão, mesmo que haja description.
        import re
        text = re.sub(r"<[^>]+>", " ", self.content_html)
        text = re.sub(r"\s+", " ", text).strip()
        length = self.excerpt_length
        return (text[:length] + "…") if len(text) > length else text

    @property
    def word_count(self) -> int:
        """Approximate word count of the rendered content, HTML tags
        stripped. Whitespace-based, so it's a rough count for CJK-style
        scripts without spaces between words — good enough for
        `reading_time` below, not meant for precise stats."""
        import re
        text = re.sub(r"<[^>]+>", " ", self.content_html)
        return len(text.split())

    @property
    def reading_time(self) -> int:
        """Estimated reading time in whole minutes, rounded up, assuming
        ~200 words per minute (the same rough figure Hugo's `.ReadingTime`
        defaults to). Always at least 1, even for very short documents."""
        words_per_minute = 200
        return max(1, -(-self.word_count // words_per_minute))

    def sort_key(self):
        return self.frontmatter.date or ""


@dataclass
class Page(Document):
    def __post_init__(self) -> None:
        self.kind = "page"
        super().__post_init__()


@dataclass
class Post(Document):
    def __post_init__(self) -> None:
        self.kind = "post"
        super().__post_init__()