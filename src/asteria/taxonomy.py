"""Taxonomies: tags and categories."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import SiteConfig
from .document import Post
from .urls import build_url, slugify


@dataclass
class Term:
    name: str  # display name (first spelling found)
    slug: str
    url: str
    posts: list[Post] = field(default_factory=list)


def _collect(posts: list[Post], attr: str, pattern: str) -> list[Term]:

    terms: dict[str, Term] = {}

    for post in posts:
        for raw_name in getattr(post, attr):
            slug = slugify(raw_name)
            if slug not in terms:
                terms[slug] = Term(
                    name=raw_name, slug=slug, url=build_url(pattern, slug=slug)
                )
            terms[slug].posts.append(post)

    
    for term in terms.values():
        term.posts.sort(key=lambda p: p.sort_key(), reverse=True)

    return sorted(terms.values(), key=lambda t: t.name.lower())


def collect_tags(posts: list[Post], config: SiteConfig) -> list[Term]:
    return _collect(posts, "tags", config.url_patterns["tags"])


def collect_categories(posts: list[Post], config: SiteConfig) -> list[Term]:
    return _collect(posts, "categories", config.url_patterns["categories"])
