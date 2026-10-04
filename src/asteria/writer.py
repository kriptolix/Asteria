"""Writing the final files and copying assets."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .config import SiteConfig
from .converter import ExtractedImage


FINGERPRINT_SUBDIRS: tuple[str, ...] = ("css", "js", "fonts", "images")

_HASH_LENGTH = 10


def write_page(output_dir: Path, relative_path: str, html: str) -> Path:
    target = output_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def write_text_file(output_dir: Path, relative_path: str, content: str) -> Path:
    target = output_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def copy_static_assets(config: SiteConfig) -> None:
    
    output_dir = config.output_dir

    if config.static_dir.exists():
        _copy_tree(config.static_dir, output_dir)

    theme_dir = config.theme_dir
    for sub in ("css", "js", "fonts", "images"):
        src = theme_dir / sub
        if src.exists():
            _copy_tree(src, output_dir / sub)


def _copy_tree(src: Path, dst: Path, exclude: set[str] | None = None) -> None:
    exclude = exclude or set()
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        if item.name in exclude:
            continue
        rel = item.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def write_document_images(
    output_dir: Path, images: list[ExtractedImage], subdir: str = ""
) -> None:
    
    target_dir = output_dir / subdir if subdir else output_dir
    for image in images:
        target = target_dir / image.output_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image.data)


def _content_hash(path: Path, length: int = _HASH_LENGTH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:length]


def _fingerprint_subdir(output_dir: Path, subdir: str, manifest: dict[str, str]) -> None:
    base = output_dir / subdir
    if not base.exists():
        return

    # Materialize the list before renaming, to avoid iterating over a
    # directory that is being modified.
    for file_path in sorted(p for p in base.rglob("*") if p.is_file()):
        digest = _content_hash(file_path)
        new_path = file_path.with_name(f"{file_path.stem}.{digest}{file_path.suffix}")
        file_path.replace(new_path)

        original_rel = "/" + file_path.relative_to(output_dir).as_posix()
        fingerprinted_rel = "/" + new_path.relative_to(output_dir).as_posix()
        manifest[original_rel] = fingerprinted_rel


def _rewrite_asset_references(
    output_dir: Path, subdirs: tuple[str, ...], manifest: dict[str, str]
) -> None:
    """Rewrites literal occurrences of an already-fingerprinted asset's
    original path with its fingerprinted path, inside every file under
    `subdirs` — e.g. a `url('/fonts/foo.woff2')` inside a .css file,
    where fingerprint_assets() has already renamed that font on disk to
    `/fonts/foo.a1b2c3.woff2`.

    This exists because `asset()` (the Jinja global templates use to
    resolve a fingerprinted path) only runs inside Jinja templates —
    CSS/JS files are copied to the output verbatim (copy_static_assets),
    so a font/image reference written inside one of them is never
    touched by `asset()` and would otherwise keep pointing at a filename
    that no longer exists once fingerprinting renames it.

    Only root-relative paths (starting with "/", exactly what `asset()`
    itself expects in templates) are recognized. A CSS/JS file
    referencing a font/image with a relative path instead
    (`../fonts/foo.woff2`, `./foo.woff2`) is NOT rewritten — resolving
    that correctly would require knowing the referencing file's own
    location on disk and doing real URL resolution, which is a lot of
    machinery for what `assets.fingerprint` otherwise keeps deliberately
    simple. Write font/image references in CSS/JS the same way templates
    do: an absolute, root-relative path.
    """
    if not manifest:
        return
    for subdir in subdirs:
        base = output_dir / subdir
        if not base.exists():
            continue
        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Not a text asset — e.g. a binary file that ended up in
                # css/ or js/ by mistake. Nothing to rewrite; skip it
                # rather than fail the whole build over it.
                continue
            new_text = text
            for original_rel, fingerprinted_rel in manifest.items():
                if original_rel in new_text:
                    new_text = new_text.replace(original_rel, fingerprinted_rel)
            if new_text != text:
                file_path.write_text(new_text, encoding="utf-8")


def fingerprint_assets(
    output_dir: Path, subdirs: tuple[str, ...] = FINGERPRINT_SUBDIRS
) -> dict[str, str]:
    """Renames every file under `subdirs` to embed a short content hash
    (e.g. `style.css` -> `style.a1b2c3.css`) and returns the
    original-path -> fingerprinted-path manifest that
    templating.apply_asset_manifest() uses to back the `asset()` global.

    Fonts and images are fingerprinted FIRST, before css/js — the
    opposite of `subdirs`' own declared order — specifically so that
    `_rewrite_asset_references` has their manifest entries ready in time
    to patch any `url(/fonts/...)`/`url(/images/...)` found inside a
    css/js file's own content. css/js are fingerprinted LAST, after that
    patching, so the hash embedded in their own final filename reflects
    the corrected content, not the stale, pre-patch one — otherwise the
    filename's hash wouldn't actually match what's being served under
    it, defeating the point of content-based fingerprinting.

    Any subdir passed in that isn't "fonts"/"images"/"css"/"js" is still
    fingerprinted (self-referencing content in it just won't be patched,
    same as css/js referencing each other — see _rewrite_asset_references
    — a rarer pattern this function doesn't attempt to handle).
    """
    manifest: dict[str, str] = {}

    binary_subdirs = tuple(s for s in subdirs if s in ("fonts", "images"))
    text_subdirs = tuple(s for s in subdirs if s in ("css", "js"))
    other_subdirs = tuple(s for s in subdirs if s not in binary_subdirs and s not in text_subdirs)

    for subdir in binary_subdirs:
        _fingerprint_subdir(output_dir, subdir, manifest)
    for subdir in other_subdirs:
        _fingerprint_subdir(output_dir, subdir, manifest)

    _rewrite_asset_references(output_dir, text_subdirs, manifest)

    for subdir in text_subdirs:
        _fingerprint_subdir(output_dir, subdir, manifest)

    return manifest


def clean_output(config: SiteConfig) -> None:
    if config.output_dir.exists():
        shutil.rmtree(config.output_dir)


def copy_raw_pages(output_dir: Path, raw_pages: list) -> None:
   
    for page in raw_pages:
        target_dir = output_dir / page.url.strip("/")
        _copy_tree(page.source_dir, target_dir, exclude={"raw.yaml"})


def list_generated_files(output_dir: Path) -> list[str]:
    
    if not output_dir.exists():
        return []

    files = []

    for path in output_dir.rglob("*"):
        if path.is_file():
            relative_path = path.relative_to(output_dir)
            files.append(str(relative_path))

    return sorted(files)