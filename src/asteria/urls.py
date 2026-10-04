"""
Centralized URL generation.
"""

from __future__ import annotations

import re
import unicodedata

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Normalizes text into a slug safe for URLs or HTML IDs."""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = _SLUG_RE.sub("-", value).strip("-")

    return value or "document"


def build_url(pattern: str, **kwargs: str) -> str:
    """Applies a URL pattern, e.g., '/blog/{slug}/' -> '/blog/my-post/'."""
    url = pattern.format(**kwargs)
    if not url.startswith("/"):
        url = "/" + url
    if not url.endswith("/") and "." not in url.rsplit("/", 1)[-1]:
        url += "/"

    return url


def prefix_lang(url: str, lang: str, default_language: str) -> str:
    """Adds the language prefix ('/pt' in '/pt/blog/article/') for
        content that is not in the site's default language."""
    if not lang or lang == default_language:
        return url
    return f"/{lang}{url}"


def url_to_output_path(url: str) -> str:
    
    path = url.strip("/")
    if not path:
        return "index.html"
    if "." in path.rsplit("/", 1)[-1]:
        return path

    return f"{path}/index.html"


def url_to_output_dir(url: str) -> str:
    
    output_path = url_to_output_path(url)

    if output_path == "index.html":
        return ""

    return output_path.rsplit("/", 1)[0]
