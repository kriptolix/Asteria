"""Incremental conversion cache.

The cache stores the result of the ODT→HTML conversion for
each document (the most expensive step in the pipeline—this is where odt2web
performs the actual parsing work) across runs, keyed by path, mtime,
and source file size. If an `.odt` file hasn't changed since the last build,
the conversion is skipped and the previous result is reused.

Anything that depends on multiple documents simultaneously—`[[id]]`
references, TOCs, `nav:`, taxonomies, blog pagination, sitemaps, feeds,
and template rendering—continues to run fully during **every**
build, even incremental ones. This prevents subtle bugs caused by
stale data.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .converter import ConversionResult, ExtractedImage, ODTConverter
from .errors import Diagnostics

CACHE_VERSION = 1
CACHE_FILENAME = ".asteria-cache.json"


def cache_path(project_root: Path) -> Path:
    return project_root / CACHE_FILENAME


def load_cache(project_root: Path) -> dict[str, Any]:
    path = cache_path(project_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def save_cache(project_root: Path, entries: dict[str, Any]) -> None:
    path = cache_path(project_root)
    try:
        path.write_text(
            json.dumps({"version": CACHE_VERSION, "entries": entries}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # The cache is just an optimization—failing to save it shouldn't break the build.


def clear_cache(project_root: Path) -> bool:
    path = cache_path(project_root)
    if path.exists():
        path.unlink()
        return True
    return False


def _fingerprint(path: Path) -> tuple[float, int]:
    stat = path.stat()
    return stat.st_mtime, stat.st_size


def _is_fresh(entry: dict[str, Any] | None, path: Path) -> bool:
    if entry is None:
        return False
    try:
        mtime, size = _fingerprint(path)
    except OSError:
        return False
    return entry.get("mtime") == mtime and entry.get("size") == size


def _result_to_entry(path: Path, result: ConversionResult) -> dict[str, Any]:
    mtime, size = _fingerprint(path)
    return {
        "mtime": mtime,
        "size": size,
        "html": result.html,
        "converter_name": result.converter_name,
        "images": [
            {
                "original_path": img.original_path,
                "output_name": img.output_name,
                "data_b64": base64.b64encode(img.data).decode("ascii"),
            }
            for img in result.images
        ],
    }


def _entry_to_result(entry: dict[str, Any]) -> ConversionResult:
    images = [
        ExtractedImage(
            original_path=img["original_path"],
            output_name=img["output_name"],
            data=base64.b64decode(img["data_b64"]),
        )
        for img in entry.get("images", [])
    ]
    return ConversionResult(
        html=entry["html"],
        images=images,
        converter_name=entry.get("converter_name", "cache"),
        # Front matter is always extracted from the HTML (see asteria.frontmatter),
        # so it does not need to be recalculated or cached separately.
        metadata=None,
    )


class CachingConverter(ODTConverter):
    """Wraps any `ODTConverter` with an incremental disk cache. 

    `entries` is mutated in-place—the object's creator is responsible for
    persisting it using `save_cache()` after the build (see `asteria.build`).
    """

    name = "cached"

    def __init__(self, inner: ODTConverter, entries: dict[str, Any]) -> None:
        self._inner = inner
        self._entries = entries
        self.hits = 0
        self.misses = 0

    def convert(self, odt_path: Path, diagnostics: Diagnostics) -> ConversionResult:
        key = str(odt_path.resolve())
        entry = self._entries.get(key)

        if _is_fresh(entry, odt_path):
            self.hits += 1
            return _entry_to_result(entry)

        self.misses += 1
        result = self._inner.convert(odt_path, diagnostics)
        self._entries[key] = _result_to_entry(odt_path, result)
        return result
