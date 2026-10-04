"""odt2web - Python library to convert ODT documents into HTML/CSS."""

from __future__ import annotations

from .convert import check, convert, convert_bytes
from .extensibility import get_default_renderers, register_renderer, unregister_renderer
from .model import Document, Metadata
from .reader import InvalidOdtError, OdtPackage, read_odt_bytes, read_odt_file
from .result import Asset, ConversionResult, Warning, WarningLevel

__all__ = [
    "convert",
    "convert_bytes",
    "check",
    "ConversionResult",
    "Asset",
    "Metadata",
    "Warning",
    "WarningLevel",
    "InvalidOdtError",
    "register_renderer",
    "unregister_renderer",
]

__version__ = "0.1.0"
