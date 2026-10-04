"""
Content discovery.

Scans `content/pages` and `content/posts`, converts each `.odt` file, extracts
front matter, and assembles `Page`/`Post` objects. It also identifies "raw"
HTML pages (see `asteria/raw.py`) and validates that all identifiers
(file/folder names without extensions) are unique across the entire site.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import SiteConfig
from .converter import ODTConverter
from .document import Document, Page, Post
from .errors import Diagnostics
from .frontmatter import extract_frontmatter
from .highlight import highlight_code_blocks, load_languages
from .raw import RawPage, load_raw_page


def _walk_pages(
    directory: Path, diagnostics: Diagnostics
) -> tuple[list[Path], list[Path]]:
    
    odt_paths: list[Path] = []
    raw_dirs: list[Path] = []
    _walk_pages_rec(directory, odt_paths, raw_dirs, diagnostics)
    return odt_paths, raw_dirs


def _walk_pages_rec(
    directory: Path,
    odt_paths: list[Path],
    raw_dirs: list[Path],
    diagnostics: Diagnostics,
) -> None:
    
    if not directory.exists():
        return
    for entry in sorted(directory.iterdir()):
        if entry.is_file() and entry.suffix == ".odt":
            odt_paths.append(entry)
        elif entry.is_dir():
            if any(entry.rglob("*.odt")):
                # Organizational folder: contains (at some level) .odt files —
                # recurses normally, without affecting page IDs/URLs.
                _walk_pages_rec(entry, odt_paths, raw_dirs, diagnostics)
            elif (entry / "index.html").exists():
                raw_dirs.append(entry)
            else:
                diagnostics.warning(
                    f"Folder in content/pages/ without .odt or index.html, ignored: '{entry.name}'.",
                    source=str(entry),
                )


def _walk_posts(
    directory: Path, diagnostics: Diagnostics
) -> tuple[list[Path], list[Path]]:
    
    odt_paths: list[Path] = []
    raw_dirs: list[Path] = []
    if not directory.exists():
        return odt_paths, raw_dirs

    for entry in sorted(directory.iterdir()):
        if entry.is_file() and entry.suffix == ".odt":
            odt_paths.append(entry)
        elif entry.is_dir():
            if (entry / "index.html").exists():
                raw_dirs.append(entry)
            else:
                diagnostics.warning(
                    f"Folder in content/posts/ without index.html, ignored: '{entry.name}' "
                    "(content/posts/ is not recursive for .odt).",
                    source=str(entry),
                )

    return odt_paths, raw_dirs


def _detect_lang(stem: str, languages: list[str], default_language: str) -> tuple[str, str]:
    """Detecta um idioma explícito no nome do arquivo.

    Convenção: "meu-post.pt.odt" -> idioma "pt" (desde que "pt" esteja
    entre os idiomas configurados em `i18n.languages`/`site.language`);
    "meu-post.odt" -> idioma padrão do site. Retorna
    (translation_key, lang), onde translation_key é o nome do arquivo
    sem o sufixo de idioma — usado para agrupar as traduções de um
    mesmo post entre si.
    """
    if "." in stem:
        base, _, suffix = stem.rpartition(".")
        if base and suffix in languages:
            return base, suffix
    return stem, default_language


def _load_document(
    path: Path,
    kind: str,
    converter: ODTConverter,
    diagnostics: Diagnostics,
    code_languages: dict[str, dict[str, Any]],
    lang: str = "",
    translation_key: str = "",
) -> Document:
    
    doc_id = path.stem
    if not doc_id or not doc_id.replace("-", "").replace("_", "").isalnum():
        diagnostics.warning(
            f"Unusual document identifier derived from the filename: '{doc_id}'.",
            source=str(path),
        )

    result = converter.convert(path, diagnostics)

    if result.metadata is not None:        
        fm = result.metadata
        content_html = result.html
    else:        
        fm, content_html = extract_frontmatter(
            result.html, source=str(path), diagnostics=diagnostics
        )
        if not fm.title:
            diagnostics.warning(
                "Document without a 'title' in the front matter; using the filename.",
                source=str(path),
            )

    # Highlight básico de blocos <pre><code class="language-x"> (ver
    # asteria.highlight). Roda sempre, mesmo em documentos que vieram do
    # cache de conversão (cache.py só evita repetir a conversão ODT→HTML
    # em si — tudo que é pós-processamento de HTML, como isto e o front
    # matter acima, continua rodando em todo build, igual já acontecia
    # antes desta mudança).
    content_html = highlight_code_blocks(content_html, code_languages)

    # O campo `lang:` do front matter, quando presente, tem prioridade
    # sobre o idioma detectado a partir do nome do arquivo.
    final_lang = fm.lang or lang

    cls = Page if kind == "page" else Post
    return cls(
        id=doc_id,
        kind=kind,
        source_path=path,
        frontmatter=fm,
        content_html=content_html,
        raw_content_html=content_html,
        images=result.images,
        lang=final_lang,
        translation_key=translation_key or doc_id,
    )


def discover_content(
    config: SiteConfig, converter: ODTConverter, diagnostics: Diagnostics
) -> tuple[list[Page], list[Post], list[RawPage]]:
    pages: list[Page] = []
    posts: list[Post] = []
    raw_pages: list[RawPage] = []

    # Definições de linguagem para o highlight (bundled + eventual
    # source/highlight.yaml do projeto) — carregadas uma vez por build,
    # não por documento.
    code_languages = load_languages(config.root)

    page_odts, page_raw_dirs = _walk_pages(config.pages_dir, diagnostics)
    for path in page_odts:
        # Páginas seguem a mesma convenção dos posts: "sobre.odt" -> idioma
        # padrão; "sobre.pt.odt" -> idioma "pt" (se configurado). O campo
        # `lang:` no front matter tem prioridade sobre o nome do arquivo.
        translation_key, detected_lang = _detect_lang(
            path.stem, config.languages, config.default_language
        )
        pages.append(
            _load_document(
                path, "page", converter, diagnostics, code_languages,
                lang=detected_lang, translation_key=translation_key,
            )
        )  # type: ignore[arg-type]
    for raw_dir in page_raw_dirs:
        raw_pages.append(
            load_raw_page(raw_dir, config.url_patterns["pages"], diagnostics)
        )

    post_odts, post_raw_dirs = _walk_posts(config.posts_dir, diagnostics)
    for path in post_odts:
        translation_key, detected_lang = _detect_lang(
            path.stem, config.languages, config.default_language
        )
        posts.append(
            _load_document(
                path, "post", converter, diagnostics, code_languages,
                lang=detected_lang, translation_key=translation_key,
            )
        )  # type: ignore[arg-type]
    for raw_dir in post_raw_dirs:
        raw_pages.append(
            load_raw_page(raw_dir, config.url_patterns["posts"], diagnostics)
        )

    _validate_unique_ids(pages, posts, raw_pages, diagnostics)
    _validate_languages([*pages, *posts], config, diagnostics)
    return pages, posts, raw_pages


def _validate_languages(
    documents: list[Document], config: SiteConfig, diagnostics: Diagnostics
) -> None:
    known = set(config.languages)
    for doc in documents:
        if doc.lang not in known:
            diagnostics.warning(
                f"{doc.kind.capitalize()} language '{doc.lang}' is not listed in "
                "i18n.languages (or site.language); it will still be "
                "built, but won't get a language prefix and won't be "
                "grouped with the site's other languages.",
                source=str(doc.source_path),
            )


def _validate_unique_ids(
    pages: list[Page],
    posts: list[Post],
    raw_pages: list[RawPage],
    diagnostics: Diagnostics,
) -> None:
    seen: dict[str, str] = {}  # id -> source path (str) already seen
    for item in [*pages, *posts, *raw_pages]:
        source = str(getattr(item, "source_path", None) or getattr(item, "source_dir", ""))
        if item.id in seen:
            diagnostics.error(
                f"Duplicate ID '{item.id}': used by '{seen[item.id]}' and '{source}'.",
                source=source,
            )
        else:
            seen[item.id] = source