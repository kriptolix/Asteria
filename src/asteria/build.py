"""
Build pipeline orchestration
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

from jinja2 import TemplateNotFound
from markupsafe import Markup

from .cache import CachingConverter, load_cache, save_cache
from .config import SiteConfig, load_config
from .converter import get_converter
from .discovery import discover_content
from .document import Document, Page, Post, TocEntry
from .errors import AsteriaError, Diagnostics
from .feed import render_atom, render_rss
from .i18n_strings import load_theme_i18n, translate
from .nav import NavEntry, build_nav
from .pagination import paginate
from .references import (
    build_registry,
    build_translation_registry,
    resolve_references_for_all,
    split_at_more_marker,
)
from .sitemap import SitemapEntry, render_sitemap
from .social import build_social_links
from .taxonomy import Term, collect_categories, collect_tags
from .templating import (
    SiteView,
    apply_asset_manifest,
    create_environment,
    make_site_view,
    render_template,
)
from .theme_config import load_theme_config
from .toc import inject_heading_ids_and_build_toc
from .urls import build_url, prefix_lang, url_to_output_dir, url_to_output_path
from .writer import (
    clean_output,
    copy_raw_pages,
    copy_static_assets,
    fingerprint_assets,
    list_generated_files,
    write_document_images,
    write_page,
    write_text_file,
)


@dataclass
class _LangSiteData:   

    menu: list[dict[str, str]]
    nav: list[NavEntry]
    categories: list[Term]
    tags: list[Term]
    featured_pages: list[Page]
    featured_posts: list[Post]
    pages: list[Page]
    posts: list[Post]
    tocs: dict[str, list[TocEntry]]


@dataclass
class BuildResult:
    diagnostics: Diagnostics
    pages: list[Page]
    posts: list[Post]
    output_dir: Path
    generated_files: list[str] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def success(self) -> bool:
        return not self.diagnostics.has_errors


def _assign_urls(config: SiteConfig, pages: list[Page], posts: list[Post]) -> None:
    patterns = config.url_patterns
    for page in pages:
        base_url = build_url(patterns["pages"], slug=page.slug)
        page.url = prefix_lang(base_url, page.lang, config.default_language)
    for post in posts:
        base_url = build_url(patterns["posts"], slug=post.slug)
        post.url = prefix_lang(base_url, post.lang, config.default_language)


def _link_translations(documents: list[Document]) -> None:
    """Preenche `doc.translations` com as demais versões (em outros
    idiomas) de cada documento, agrupadas por `translation_key`. Chame
    separadamente para `pages` e `posts` — uma página e um post nunca
    devem ser considerados tradução um do outro, mesmo que, por
    coincidência, compartilhem a mesma translation_key."""
    groups: dict[str, list[Document]] = {}
    for doc in documents:
        groups.setdefault(doc.translation_key, []).append(doc)

    for group in groups.values():
        for doc in group:
            doc.translations = {d.lang: d for d in group if d is not doc}


def _build_toc_for_all(documents: list[Document]) -> None:
    for doc in documents:
        html_with_ids, toc = inject_heading_ids_and_build_toc(doc.content_html)
        doc.content_html = html_with_ids
        doc.toc = toc


def _assign_prev_next(posts: list[Post]) -> None:
    """Chronological: from oldest to most recent, within each language
    (a post never points to a previous/next post in a different
    language)."""
    by_lang: dict[str, list[Post]] = {}
    for post in posts:
        by_lang.setdefault(post.lang, []).append(post)

    for group in by_lang.values():
        ordered = sorted(group, key=lambda p: p.sort_key())
        for i, post in enumerate(ordered):
            post.previous = ordered[i - 1] if i > 0 else None
            post.next = ordered[i + 1] if i < len(ordered) - 1 else None


def _resolve_page_reference(
    ref: str,
    pages_by_id: dict[str, Page],
    pages_by_translation_key: dict[str, dict[str, Page]],
    lang: str,
    default_language: str,
) -> Page | None:
    """Resolves a page reference string (as used by `menu: - page: ...`
    and `home_page:` in site.yaml) to a `Page`.
    """
    translations = pages_by_translation_key.get(ref)
    if translations:
        return (
            translations.get(lang)
            or translations.get(default_language)
            or next(iter(translations.values()))
        )
    return pages_by_id.get(ref)


def _build_menu(
    menu_config: list[dict],
    config: SiteConfig,
    pages_by_id: dict[str, Page],
    pages_by_translation_key: dict[str, dict[str, Page]],
    lang: str,
    diagnostics: Diagnostics,
    theme_strings: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Builds the menu for a single language.
    """
    # "blog" is the one reserved keyword that means "the blog index" in
    # `page:` (here) and `home_page:` (see run_build) — there's no
    # separate url_prefix-based alias anymore, since the blog's URL is
    # fully derived from `urls.posts` (see SiteConfig.blog_index_url).
    blog_keys = {"blog"}
    menu_items = []

    for entry in menu_config:
        page_id = entry.get("page")
        title_override = entry.get("title")

        if page_id in blog_keys:
            url = prefix_lang(config.blog_index_url, lang, config.default_language)
            # No page object to fall back to for a title here — see
            # theme_strings in the docstring above.
            title = title_override or translate(
                theme_strings, "blog_menu_label", lang, config.default_language,
                fallback="Blog",
            )
        else:
            # translation_key is checked FIRST, exact id second — see
            # _resolve_page_reference for the full rationale.
            page = _resolve_page_reference(
                page_id, pages_by_id, pages_by_translation_key,
                lang, config.default_language,
            )
            if page is None:
                diagnostics.warning(
                    f"menu: page '{page_id}' not found (checked both as an "
                    "exact page id and as a translation_key).",
                    # `menu:` now lives in site.yaml, not theme.yaml — see
                    # SiteConfig.menu_config.
                    source="site.yaml",
                )
                url = "#"
                # No resolved page to pull a title from — last-resort
                # fallback to the raw reference string, same as before
                # this fix.
                title = title_override or page_id
            else:
                url = page.url
                # title: (menu) > menu_title: (front matter) > title:
                # (front matter) — see the "A menu entry's label..."
                # paragraph in the docstring above. `page` was resolved
                # for this specific `lang`, so both `.menu_title` and
                # `.title` are already the right language's text.
                title = title_override or page.menu_title or page.title
        menu_items.append({"title": title, "url": url, "page_id": page_id})

    return menu_items


def _site_view_for_lang(
    site_view: SiteView,
    lang_site_data: dict[str, _LangSiteData],
    lang: str,
    default_language: str,
) -> SiteView:
    
    data = lang_site_data.get(lang) or lang_site_data.get(default_language)
    if data is None:
        return site_view
    
    updates = {f.name: getattr(data, f.name) for f in fields(_LangSiteData)}
    if all(getattr(site_view, name) is value for name, value in updates.items()):
        return site_view
    return replace(site_view, **updates)


def _breadcrumbs_for_page(config: SiteConfig, page: Page) -> list[dict[str, str]]:
    crumbs = [{"title": config.title, "url": "/"}]
    
    if page.translation_key != config.home_page:
        crumbs.append({"title": page.title, "url": page.url})
    return crumbs


def _ui_label(
    theme_strings: dict[str, dict[str, str]],
    config: SiteConfig,
    key: str,
    lang: str,
    fallback: str,
) -> str:
    """Translates a built-in UI label (breadcrumb/taxonomy names)"""
    return translate(
        theme_strings, key, lang or config.default_language,
        config.default_language, fallback=fallback,
    )


def _breadcrumbs_for_post(
    config: SiteConfig, post: Post, theme_strings: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    blog_url = prefix_lang(config.blog_index_url, post.lang, config.default_language)
    blog_label = _ui_label(theme_strings, config, "blog_menu_label", post.lang, "Blog")
    return [
        {"title": config.title, "url": "/"},
        {"title": blog_label, "url": blog_url},
        {"title": post.title, "url": post.url},
    ]


def _document_context(
    config: SiteConfig,
    site_view: SiteView,
    theme_ns: dict,
    doc: Document,
    breadcrumbs: list[dict[str, str]],
) -> dict:
    return {
        "site": site_view,
        "theme": theme_ns,
        "page": doc,
        "post": doc,
        "content": Markup(doc.content_html),
        "breadcrumbs": breadcrumbs,
        "theme_css": doc.variant or theme_ns["default_variant"],
        "canonical_path": doc.url,
        "og_type": "article" if doc.kind == "post" else "website",
        "show_toc": theme_ns["sidebar_toc"] and doc.toc_enabled,
        "show_navigation": bool(site_view.nav) and doc.navigation_enabled,
        "lang": doc.lang or config.default_language,
    }


def _resolve_template_name(
    env, doc: Document, default_name: str, diagnostics: Diagnostics
) -> str:
    """Resolve o template do tema a usar para este documento."""
    name = doc.template or default_name
    if name == default_name:
        return name
    try:
        env.get_template(name)
    except TemplateNotFound:
        diagnostics.error(
            f"template: '{name}' not found in the theme; using the default template "
            f"('{default_name}').",
            source=str(doc.source_path),
        )
        return default_name
    return name


def _feed_filename(config: SiteConfig) -> str:
    return "rss.xml" if config.data["feeds"].get("format", "rss") == "rss" else "atom.xml"


def _search_index_filename(lang: str, default_language: str) -> str:    
    return "search-index.json" if lang == default_language else f"{lang}-search-index.json"


def _write_search_index(
    config: SiteConfig,
    documents: list[Document],
    lang: str,
) -> None:
    
    entries = [
        {
            "title": doc.title,
            "url": doc.url,
            "date": doc.date,
            "excerpt": doc.excerpt,
        }
        for doc in documents
    ]
    write_text_file(
        config.output_dir,
        _search_index_filename(lang, config.default_language),
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
    )


def _finalize_html(html: str, live_reload_script: str | None) -> str:
    """Injects the live reload script """

    if not live_reload_script:
        return html
    marker = "</body>"
    if marker in html:
        return html.replace(marker, live_reload_script + marker, 1)
    return html + live_reload_script


def run_build(
    project_root: Path,
    config_filename: str = "site.yaml",
    converter_name: str = "auto",
    dry_run: bool = False,
    live_reload_script: str | None = None,
) -> BuildResult:
    
    diagnostics = Diagnostics()
    config_path = project_root / "source" /config_filename
    config = load_config(config_path)

    if not config.theme_dir.exists():
        raise AsteriaError(
            f"Theme '{config.theme_name}' not founded in {config.theme_dir}."
        )

    raw_converter = get_converter(converter_name)
    if raw_converter.name == "fallback":
        diagnostics.warning(
            "Using the FallbackConverter (restricted to tests)"            
        )

    cache_entries = load_cache(project_root)
    converter = CachingConverter(raw_converter, cache_entries)

    pages, posts, raw_pages = discover_content(config, converter, diagnostics)

    if diagnostics.has_errors:
        return BuildResult(diagnostics, pages, posts, config.output_dir)

    _link_translations(pages)
    _link_translations(posts)
    _assign_urls(config, pages, posts)
    resolve_references_for_all(
        [*pages, *posts], diagnostics, extra_targets=raw_pages,
        default_language=config.default_language,
    )

    if diagnostics.has_errors:
        return BuildResult(diagnostics, pages, posts, config.output_dir)

    _build_toc_for_all([*pages, *posts])
    _assign_prev_next(posts)

    pages_by_id = {p.id: p for p in pages}
    pages_by_translation_key: dict[str, dict[str, Page]] = {}
    for page in pages:
        pages_by_translation_key.setdefault(page.translation_key, {})[page.lang] = page
    
    theme_config_raw = load_theme_config(config.theme_dir, config.theme_params)
    
    if config.home_page != "blog":
        menu_page_refs = {entry.get("page") for entry in config.menu_config}
        if config.home_page not in menu_page_refs:
            diagnostics.warning(
                f"home_page: '{config.home_page}' is not referenced by any "
                "menu item (menu: - page: ...) in site.yaml. This may be "
                "intentional (e.g. the home page is reached via a logo or "
                "site title instead of a menu entry) — if it isn't, add a "
                "matching 'page:' entry to menu: to keep them in sync.",
                source="site.yaml",
            )
    
    theme_strings = load_theme_i18n(config.theme_dir, config.i18n_string_overrides)

    menus_by_lang: dict[str, list[dict[str, str]]] = {
        lang: _build_menu(
            config.menu_config, config, pages_by_id,
            pages_by_translation_key, lang, diagnostics, theme_strings,
        )
        for lang in config.languages
    }
    feed_url = f"/{_feed_filename(config)}" if config.feeds_enabled else None
    nav_registry = build_registry([*pages, *posts, *raw_pages])
    # Raw pages are excluded here (same as menus/[[references]]): they have
    # no lang/translation_key, so they're only reachable by their exact id.
    nav_translation_registry = build_translation_registry([*pages, *posts])
    navs_by_lang: dict[str, list[NavEntry]] = {
        lang: build_nav(
            config.nav_config, nav_registry, diagnostics,
            translation_registry=nav_translation_registry,
            lang=lang, default_language=config.default_language,
        )
        for lang in config.languages
    }
    social_links = build_social_links(config.social_config)
   
    lang_site_data: dict[str, _LangSiteData] = {}
    for lang in config.languages:
        lang_pages_all = [p for p in pages if p.lang == lang]
        lang_posts_all = [p for p in posts if p.lang == lang]
        lang_posts_sorted = sorted(lang_posts_all, key=lambda p: p.sort_key(), reverse=True)

        lang_categories = collect_categories(lang_posts_all, config)
        lang_tags = collect_tags(lang_posts_all, config)
        if lang != config.default_language:
            for term in [*lang_categories, *lang_tags]:
                term.url = prefix_lang(term.url, lang, config.default_language)

        lang_site_data[lang] = _LangSiteData(
            menu=menus_by_lang[lang],
            nav=navs_by_lang[lang],
            categories=lang_categories,
            tags=lang_tags,
            featured_pages=[p for p in lang_pages_all if p.featured],
            featured_posts=[p for p in lang_posts_all if p.featured],
            pages=lang_pages_all,
            posts=lang_posts_sorted,
           
            tocs={
                doc.url: doc.toc
                for doc in [*lang_pages_all, *lang_posts_all]
                if doc.toc_enabled and doc.toc
            },
        )

    theme_ns: dict = dict(theme_config_raw)
   
    theme_ns.setdefault("sidebar_toc", True)
    theme_ns.setdefault("default_variant", "light")
 
    default_lang_data = lang_site_data.get(config.default_language)
    site_view = make_site_view(
        config,
        feed_url=feed_url,
        menu=default_lang_data.menu if default_lang_data else [],
        nav=default_lang_data.nav if default_lang_data else [],
        social=social_links,
        categories=default_lang_data.categories if default_lang_data else [],
        tags=default_lang_data.tags if default_lang_data else [],
        featured_pages=default_lang_data.featured_pages if default_lang_data else [],
        featured_posts=default_lang_data.featured_posts if default_lang_data else [],
        pages=default_lang_data.pages if default_lang_data else [],
        posts=default_lang_data.posts if default_lang_data else [],
        tocs=default_lang_data.tocs if default_lang_data else {},
    )

    env = create_environment(config)

    # Excerpt [[more]]
   
    for post in posts:
        post.excerpt_length = config.excerpt_length
        post.excerpt_enabled = config.excerpt_enabled
        post.content_html, manual_excerpt = split_at_more_marker(post.content_html)
        post.manual_excerpt = manual_excerpt

    _build_toc_for_all([*pages, *posts])

    if not dry_run:
        clean_output(config)
   
    if not dry_run:
        copy_static_assets(config)
        asset_manifest = (
            fingerprint_assets(config.output_dir) if config.fingerprint_assets_enabled else {}
        )
        if asset_manifest:
            write_text_file(
                config.output_dir,
                "asset-manifest.json",
                json.dumps(asset_manifest, indent=2, sort_keys=True) + "\n",
            )
        apply_asset_manifest(env, asset_manifest)

    home_candidates: dict[str, str] = {}
    home_candidate_images: dict[str, list] = {}
    # Preenchido no laço por idioma abaixo, apenas quando `home_page:` no
    # site.yaml é 'blog': página 1 do índice do blog de cada idioma.
    blog_home_html: dict[str, str] = {}
    sitemap_entries: list[SitemapEntry] = []

    # -- pages --------------------------------------------------------------
    for page in pages:
        page_site_view = _site_view_for_lang(
            site_view, lang_site_data, page.lang, config.default_language,
        )
        context = _document_context(
            config, page_site_view, theme_ns, page, _breadcrumbs_for_page(config, page)
        )
        template_name = _resolve_template_name(env, page, "layouts/page.html", diagnostics)
        html = _finalize_html(render_template(env, template_name, context), live_reload_script)
        if not dry_run:
            write_page(config.output_dir, url_to_output_path(page.url), html)
            write_document_images(
                config.output_dir, page.images, subdir=url_to_output_dir(page.url)
            )
        home_candidates[page.id] = html
        home_candidate_images[page.id] = page.images
        sitemap_entries.append(SitemapEntry(path=page.url))

    # -- posts ------------------------------------------------------------
    for post in posts:
        post_site_view = _site_view_for_lang(
            site_view, lang_site_data, post.lang, config.default_language,
        )
        context = _document_context(
            config, post_site_view, theme_ns, post,
            _breadcrumbs_for_post(config, post, theme_strings),
        )
        template_name = _resolve_template_name(env, post, "layouts/post.html", diagnostics)
        html = _finalize_html(render_template(env, template_name, context), live_reload_script)
        if not dry_run:
            write_page(config.output_dir, url_to_output_path(post.url), html)
            write_document_images(
                config.output_dir, post.images, subdir=url_to_output_dir(post.url)
            )
        sitemap_entries.append(SitemapEntry(path=post.url, lastmod=post.date))
    
    for lang in config.languages:
        is_default_lang = lang == config.default_language
        lang_data = lang_site_data[lang]
        lang_site_view = _site_view_for_lang(
            site_view, lang_site_data, lang, config.default_language,
        )
      
        lang_posts_desc = lang_data.posts

        blog_index_url = prefix_lang(config.blog_index_url, lang, config.default_language)
        blog_label = _ui_label(theme_strings, config, "blog_menu_label", lang, "Blog")
        blog_pages = paginate(lang_posts_desc, config.posts_per_page, blog_index_url)
        for blog_page in blog_pages:
            html = _finalize_html(
                render_template(
                    env,
                    "layouts/blog.html",
                    {
                        "site": lang_site_view,
                        "theme": theme_ns,
                        "posts": blog_page.items,
                        "pagination": blog_page,
                        "theme_css": theme_ns["default_variant"],
                        "canonical_path": blog_page.url,
                        "og_type": "website",
                        "show_navigation": False,
                        "lang": lang,
                        "breadcrumbs": [
                            {"title": config.title, "url": "/"},
                            {"title": blog_label, "url": blog_index_url},
                        ],
                    },
                ),
                live_reload_script,
            )
            if not dry_run:
                write_page(config.output_dir, url_to_output_path(blog_page.url), html)
            sitemap_entries.append(SitemapEntry(path=blog_page.url))
            if blog_page.number == 1:
                blog_home_html[lang] = html

        tags_index_url = prefix_lang(
            config.data["urls"]["tags_index"], lang, config.default_language
        )
        categories_index_url = prefix_lang(
            config.data["urls"]["categories_index"], lang, config.default_language
        )
        
        lang_tags = lang_data.tags
        lang_categories = lang_data.categories

        sitemap_entries += _write_taxonomy(
            config, env, lang_site_view, theme_ns, lang_tags,
            kind_label=_ui_label(theme_strings, config, "tags_label", lang, "Tags"),
            index_url=tags_index_url,
            dry_run=dry_run, live_reload_script=live_reload_script,
        )
        sitemap_entries += _write_taxonomy(
            config, env, lang_site_view, theme_ns, lang_categories,
            kind_label=_ui_label(
                theme_strings, config, "categories_label", lang, "Categories"
            ),
            index_url=categories_index_url,
            dry_run=dry_run, live_reload_script=live_reload_script,
        )

        if config.feeds_enabled and not dry_run:
            feed_format = config.data["feeds"].get("format", "rss")
            feed_xml = (
                render_rss(config, lang_posts_desc)
                if feed_format == "rss"
                else render_atom(config, lang_posts_desc)
            )
            
            feed_filename = (
                _feed_filename(config) if is_default_lang else f"{lang}-{_feed_filename(config)}"
            )
            write_text_file(config.output_dir, feed_filename, feed_xml)

        if config.search_enabled and not dry_run:
            _write_search_index(config, [*lang_data.pages, *lang_posts_desc], lang)

    
    is_blog_home = config.home_page == "blog"
    
    home_pages_by_lang: dict[str, Page] = {}
    if not is_blog_home:
      
        home_page_default = _resolve_page_reference(
            config.home_page, pages_by_id, pages_by_translation_key,
            lang=config.default_language, default_language=config.default_language,
        )
        if home_page_default is not None:
            home_pages_by_lang[home_page_default.lang] = home_page_default
            home_pages_by_lang.update(home_page_default.translations)

    for lang in config.languages:
        is_default_lang = lang == config.default_language
        root_path = "/" if is_default_lang else f"/{lang}/"

        if is_blog_home:
            home_html = blog_home_html.get(lang)
            extra_images: list = []
        else:
            home_page_for_lang = home_pages_by_lang.get(lang)
            home_html = home_candidates.get(home_page_for_lang.id) if home_page_for_lang else None
            extra_images = (
                home_candidate_images.get(home_page_for_lang.id, []) if home_page_for_lang else []
            )

        if home_html is None:
            
            if is_default_lang and (pages or posts):
                diagnostics.warning(
                    f"Home page '{config.home_page}' not found among the "
                    "generated pages or indexes (use a page ID, or 'blog' "
                    "to use the blog index); no root index.html was generated.",
                )
            continue

        if not dry_run:
            write_page(config.output_dir, url_to_output_path(root_path), home_html)
            
            if extra_images:
                write_document_images(
                    config.output_dir, extra_images, subdir=url_to_output_dir(root_path)
                )
        sitemap_entries.append(SitemapEntry(path=root_path))

    # -- page 404 --------------------------------------------------------------
    not_found_html = _finalize_html(
        render_template(
            env,
            "layouts/404.html",
            {
                "site": site_view,
                "theme": theme_ns,
                "theme_css": theme_ns["default_variant"],
                "canonical_path": "/404.html",
                "og_type": "website",
                "show_navigation": False,
                "breadcrumbs": [],
            },
        ),
        live_reload_script,
    )
    if not dry_run:
        write_page(config.output_dir, "404.html", not_found_html)

    if not dry_run:
        copy_raw_pages(config.output_dir, raw_pages)
    sitemap_entries += [SitemapEntry(path=p.url) for p in raw_pages]

    # -- sitemap.xml ---------------------------------------------------
    if config.sitemap_enabled and not dry_run:
        sitemap_xml = render_sitemap(sitemap_entries, config.url)
        write_text_file(config.output_dir, "sitemap.xml", sitemap_xml)

    # -- robots.txt  ------------------------------------------------------
    if config.robots_enabled and not dry_run:
        robots_lines = ["User-agent: *", "Allow: /"]
        if config.sitemap_enabled:
            robots_lines += ["", f"Sitemap: {config.url}/sitemap.xml"]
        write_text_file(config.output_dir, "robots.txt", "\n".join(robots_lines) + "\n")

    # -- incremental cache ----------------------------------------------
    if not dry_run:
        save_cache(project_root, cache_entries)

    generated_files = [] if dry_run else list_generated_files(config.output_dir)
    return BuildResult(
        diagnostics, pages, posts, config.output_dir, generated_files,
        cache_hits=converter.hits, cache_misses=converter.misses,
    )


def _write_taxonomy(
    config: SiteConfig,
    env,
    site_view,
    theme_ns: dict,
    terms: list[Term],
    kind_label: str,
    index_url: str,
    dry_run: bool = False,
    live_reload_script: str | None = None,
) -> list[SitemapEntry]:
    entries = [SitemapEntry(path=index_url)]

    index_html = _finalize_html(
        render_template(
            env,
            "layouts/taxonomy_index.html",
            {
                "site": site_view,
                "theme": theme_ns,
                "terms": terms,
                "kind_label": kind_label,
                "theme_css": theme_ns["default_variant"],
                "canonical_path": index_url,
                "og_type": "website",
                "show_navigation": False,
                "breadcrumbs": [
                    {"title": config.title, "url": "/"},
                    {"title": kind_label, "url": index_url},
                ],
            },
        ),
        live_reload_script,
    )
    if not dry_run:
        write_page(config.output_dir, url_to_output_path(index_url), index_html)

    for term in terms:
        term_html = _finalize_html(
            render_template(
                env,
                "layouts/taxonomy_term.html",
                {
                    "site": site_view,
                    "theme": theme_ns,
                    "term": term,
                    "posts": term.posts,
                    "kind_label": kind_label,
                    "theme_css": theme_ns["default_variant"],
                    "canonical_path": term.url,
                    "og_type": "website",
                    "show_navigation": False,
                    "breadcrumbs": [
                        {"title": config.title, "url": "/"},
                        {"title": kind_label, "url": index_url},
                        {"title": term.name, "url": term.url},
                    ],
                },
            ),
            live_reload_script,
        )
        if not dry_run:
            write_page(config.output_dir, url_to_output_path(term.url), term_html)
        entries.append(SitemapEntry(path=term.url))

    return entries