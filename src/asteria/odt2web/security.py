"""Security-related functions."""


from __future__ import annotations

import html as _html
import re
from urllib.parse import urlparse

ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel", ""}

# schemes that are explicitly dangerous or that allow escaping the
# browser sandbox / the output directory.
_DANGEROUS_SCHEMES = {"javascript", "file", "vbscript", "data"}


def escape_text(value: str) -> str:
    """Escapes text for safe use in HTML content."""
    return _html.escape(value, quote=False)


def escape_attr(value: str) -> str:
    """Escapes text for safe use inside an HTML attribute (double quotes)."""
    return _html.escape(value, quote=True)


def sanitize_url(url: str, *, allow_relative: bool = True) -> str | None:
    """Sanitizes a URL coming from the ODT document.

    Returns None if the URL is considered dangerous (in that case the
    caller should omit the link/attribute instead of generating it).
    """
    if url is None:
        return None
    url = url.strip()
    if not url:
        return None

    # normalize internal whitespace used to obfuscate schemes,
    # e.g. "java\tscript:alert(1)"
    stripped = re.sub(r"[\s\x00-\x1f]+", "", url)
    parsed = urlparse(stripped)
    scheme = parsed.scheme.lower()

    if scheme in _DANGEROUS_SCHEMES:
        return None

    if scheme and scheme not in ALLOWED_URL_SCHEMES:
        # unknown schemes (ftp:, custom:, etc.) are rejected by default -
        # the allowlist can be extended in the future.
        return None

    if not scheme and not allow_relative:
        return None

    return escape_attr(url)


def is_safe_relative_path(path: str) -> bool:
    """Checks that a relative asset path does not escape the output
    directory (protects against path traversal via file names in the ODT)."""
    if not path:
        return False
    if path.startswith("/") or path.startswith("\\"):
        return False
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    depth = 0
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                return False
        else:
            depth += 1
    return True
