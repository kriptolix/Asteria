"""Metadata extraction from meta.xml (spec section 11)."""
from __future__ import annotations

from xml.etree import ElementTree as ET

from .model import Metadata
from .ns import q


def parse_metadata(meta_xml: ET.Element | None, content_xml: ET.Element | None = None) -> Metadata:
    metadata = Metadata()
    if meta_xml is None:
        return metadata

    office_meta = meta_xml.find(q("office:meta"))
    if office_meta is None:
        return metadata

    def text_of(tag: str) -> str | None:
        el = office_meta.find(q(tag))
        if el is not None and el.text:
            return el.text.strip() or None
        return None

    metadata.title = text_of("dc:title")
    metadata.author = text_of("meta:initial-creator") or text_of("dc:creator")
    metadata.description = text_of("dc:description")
    metadata.subject = text_of("dc:subject")
    metadata.created = text_of("meta:creation-date")
    metadata.modified = text_of("dc:date")

    keywords: list[str] = []
    for kw_el in office_meta.findall(q("meta:keyword")):
        if kw_el.text and kw_el.text.strip():
            keywords.append(kw_el.text.strip())
    metadata.keywords = keywords

    if content_xml is not None:
        root_lang = content_xml.getroot().get("{http://www.w3.org/XML/1998/namespace}lang") \
            if hasattr(content_xml, "getroot") else content_xml.get(
                "{http://www.w3.org/XML/1998/namespace}lang"
            )
        metadata.language = root_lang

    return metadata
