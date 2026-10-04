"""Jinja2 template rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from .config import SiteConfig
from .dates import format_date
from .i18n_strings import load_theme_i18n, translate
from .nav import NavEntry
from .urls import prefix_lang, slugify


@dataclass
class SiteView:
    """`site` object exposed to the templates."""

    title: str
    description: str
    url: str
    language: str
    blog_index_url: str
    feed_url: str | None = None
    # -- i18n -------------------------------------------------------------
    languages: list[str] = field(default_factory=list)
    default_language: str = ""    
    blog_index_urls: dict[str, str] = field(default_factory=dict)
   
    menu: list[dict[str, str]] = field(default_factory=list)
    nav: list[NavEntry] = field(default_factory=list)
    social: list[Any] = field(default_factory=list)    
    
    categories: list[Any] = field(default_factory=list)
    tags: list[Any] = field(default_factory=list)
   
    featured_pages: list[Any] = field(default_factory=list)
    featured_posts: list[Any] = field(default_factory=list)
 
    pages: list[Any] = field(default_factory=list)
    posts: list[Any] = field(default_factory=list)
 
    tocs: dict[str, Any] = field(default_factory=dict)


def make_site_view(
    config: SiteConfig,
    feed_url: str | None = None,
    menu: list[dict[str, str]] | None = None,
    nav: list[NavEntry] | None = None,
    social: list[Any] | None = None,
    categories: list[Any] | None = None,
    tags: list[Any] | None = None,
    featured_pages: list[Any] | None = None,
    featured_posts: list[Any] | None = None,
    pages: list[Any] | None = None,
    posts: list[Any] | None = None,
    tocs: dict[str, Any] | None = None,
) -> SiteView:
    return SiteView(
        title=config.title,
        description=config.description,
        url=config.url,
        language=config.language,
        blog_index_url=config.blog_index_url,
        feed_url=feed_url,
        languages=config.languages,
        default_language=config.default_language,
        blog_index_urls={
            lang: prefix_lang(config.blog_index_url, lang, config.default_language)
            for lang in config.languages
        },
        menu=menu or [],
        nav=nav or [],
        social=social or [],
        categories=categories or [],
        tags=tags or [],
        featured_pages=featured_pages or [],
        featured_posts=featured_posts or [],
        pages=pages or [],
        posts=posts or [],
        tocs=tocs or {},
    )


def create_environment(config: SiteConfig) -> Environment:
    theme_dir = config.theme_dir
    env = Environment(
        loader=FileSystemLoader(str(theme_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        # Content HTML is trustworthy only when it comes from the pipeline itself
        #, the auto-escaping above protects any other variable.
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # `content` (and other document fields that are already trusted HTML from
    # the pipeline) must be inserted without extra escaping: templates use
    # `{{ post.content }}` directly, so we mark it as safe here via a
    # dedicated filter instead of using a global autoescape=False.
    env.filters["safe_content"] = lambda value: Markup(value)
    env.filters["slug"] = slugify
    env.filters["format_date"] = format_date
    env.globals["nav_branch_active"] = _nav_branch_contains
    env.globals["menu_item_active"] = _menu_item_active
    # `t(key, lang, **kwargs)` — UI string translations owned by the
    # theme's own i18n.yaml (plus any site.yaml `i18n.strings`
    # override), loaded once here since they don't change per-document
    # the way `site`/`theme` context values do. See i18n_strings.py.
    theme_strings = load_theme_i18n(theme_dir, config.i18n_string_overrides)
    env.globals["t"] = lambda key, lang="", **kwargs: translate(
        theme_strings, key, lang or config.default_language,
        config.default_language, **kwargs,
    )
    # Fallback identity: until `apply_asset_manifest` runs (after static
    # assets are copied and fingerprinted), `asset('/css/style.css')` just
    # returns the path unchanged. Templates can call it unconditionally.
    env.globals["asset"] = lambda path: path
    return env


def apply_asset_manifest(env: Environment, manifest: dict[str, str]) -> None:
    """Connects the template `asset()` filter/global to
      the asset fingerprint manifest ({"/css/style.css": "/css/style.a1b2c3.css", ...}).   
    """

    def _asset(path: str) -> str:
        lookup = path if path.startswith("/") else f"/{path}"
        return manifest.get(lookup, path)

    env.globals["asset"] = _asset


def _nav_branch_contains(entry: Any, path: str) -> bool:
    
    if entry.url == path:
        return True

    for child in entry.children:
        if _nav_branch_contains(child, path):
            return True

    return False


def _menu_item_active(item: dict, path: str) -> bool:
    """Equivalente de `_nav_branch_contains` para `site.menu`: os itens
    ali são dicts planos (`{title, url, page_id}`, ver
    build._build_menu), sem filhos/aninhamento, então não precisa de
    recursão — só compara a URL diretamente. Usado pelo global
    `menu_item_active(item, path)` para marcar o item corrente (ex:
    `class="active"`) num template."""
    return item.get("url") == path


def render_template(env: Environment, template_name: str, context: dict[str, Any]) -> str:
    template = env.get_template(template_name)
    return template.render(**context)