"""Package Reader (spec section 3.1).

Reads the .odt as a ZIP package (ODF format) and gives access to:
- content.xml
- styles.xml
- meta.xml
- settings.xml
- manifest.xml
- binary resources under Pictures/ and others

Does not depend on LibreOffice.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET


class InvalidOdtError(Exception):
    """Raised when the file is not a valid ODT package."""


@dataclass
class OdtPackage:
    content_xml: ET.Element | None
    styles_xml: ET.Element | None
    meta_xml: ET.Element | None
    settings_xml: ET.Element | None
    manifest_entries: dict[str, str]  # full-path -> media-type
    resources: dict[str, bytes]  # path inside the zip -> bytes (Pictures/, etc.)
    mimetype: str | None


def _parse_xml(data: bytes) -> ET.Element:
    # xml.etree does not expand external entities nor process DTDs by
    # default, which mitigates common XXE/billion-laughs attacks; we
    # still treat the content as untrusted (section 13).
    return ET.fromstring(data)


def read_odt_bytes(data: bytes) -> OdtPackage:
    """Reads an .odt package from in-memory bytes."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise InvalidOdtError("File is not a valid ZIP/ODT") from exc

    names = set(zf.namelist())

    mimetype = None
    if "mimetype" in names:
        mimetype = zf.read("mimetype").decode("ascii", errors="replace").strip()

    def read_optional_xml(name: str) -> ET.Element | None:
        if name not in names:
            return None
        try:
            return _parse_xml(zf.read(name))
        except ET.ParseError as exc:
            raise InvalidOdtError(f"Invalid XML in {name}: {exc}") from exc

    content_xml = read_optional_xml("content.xml")
    if content_xml is None:
        raise InvalidOdtError("content.xml missing - does not look like a valid .odt")

    styles_xml = read_optional_xml("styles.xml")
    meta_xml = read_optional_xml("meta.xml")
    settings_xml = read_optional_xml("settings.xml")

    manifest_entries: dict[str, str] = {}
    manifest_root = read_optional_xml("META-INF/manifest.xml")
    if manifest_root is not None:
        ns = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
        for entry in manifest_root.findall(f"{{{ns}}}file-entry"):
            full_path = entry.get(f"{{{ns}}}full-path")
            media_type = entry.get(f"{{{ns}}}media-type", "")
            if full_path:
                manifest_entries[full_path] = media_type

    resources: dict[str, bytes] = {}
    for name in names:
        if name.startswith("Pictures/") or name.startswith("media/") or name.startswith("Thumbnails/"):
            if not name.endswith("/"):
                resources[name] = zf.read(name)

    return OdtPackage(
        content_xml=content_xml,
        styles_xml=styles_xml,
        meta_xml=meta_xml,
        settings_xml=settings_xml,
        manifest_entries=manifest_entries,
        resources=resources,
        mimetype=mimetype,
    )


def read_odt_file(path: str) -> OdtPackage:
    """Reads an .odt package from a path on the file system."""
    with open(path, "rb") as fh:
        data = fh.read()
    return read_odt_bytes(data)
