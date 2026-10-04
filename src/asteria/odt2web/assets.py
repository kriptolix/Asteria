"""Asset extraction."""


from __future__ import annotations

import posixpath

from .model import Document, Image
from .reader import OdtPackage
from .result import Asset
from .security import is_safe_relative_path

_MEDIA_TYPE_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _guess_media_type(path: str) -> str | None:
    ext = posixpath.splitext(path)[1].lower()
    return _MEDIA_TYPE_BY_EXT.get(ext)


def extract_assets(document: Document, package: OdtPackage, assets_dir: str = "assets") -> list[Asset]:

    assets: list[Asset] = []
    seen: dict[str, str] = {}  # original_path -> output_path (avoids duplicates)
    counter = 1

    def visit_images(nodes):
        nonlocal counter
        for node in nodes:
            if isinstance(node, Image) and not node.linked:
                original = node.src
                if not original or not is_safe_relative_path(original):
                    continue
                if original not in package.resources:
                    continue  # missing/invalid resource
                if original in seen:
                    node.src = seen[original]
                    continue
                ext = posixpath.splitext(original)[1] or ".bin"
                output_name = f"image-{counter:03d}{ext}"
                counter += 1
                output_path = posixpath.join(assets_dir, output_name)
                data = package.resources[original]
                assets.append(
                    Asset(
                        original_path=original,
                        output_path=output_path,
                        data=data,
                        media_type=_guess_media_type(original),
                    )
                )
                seen[original] = output_path
                node.src = output_path
            children = getattr(node, "children", None)
            if children:
                visit_images(children)
            items = getattr(node, "items", None)
            if items:
                for item in items:
                    visit_images(item.children)
            rows = getattr(node, "rows", None)
            if rows:
                for row in rows:
                    for cell in row.cells:
                        visit_images(cell.children)

    for section in document.sections:
        visit_images(section.children)
    for note in document.notes.values():
        visit_images(note.children)

    return assets
