"""Pagination: `/blog/`, `/blog/page/2/`, `/blog/page/3/` ..."""

from __future__ import annotations

from dataclasses import dataclass

from .document import Post


@dataclass
class Page:
    
    items: list[Post]
    number: int  # 1-indexed
    total_pages: int
    url: str
    prev_url: str | None
    next_url: str | None


def paginate(
    posts: list[Post], per_page: int, base_url: str
) -> list[Page]:
    
    if per_page < 1:
        per_page = len(posts) or 1

    total_pages = max(1, -(-len(posts) // per_page)) if posts else 1
    pages: list[Page] = []

    for number in range(1, total_pages + 1):
        start = (number - 1) * per_page
        items = posts[start : start + per_page]
        url = base_url if number == 1 else f"{base_url}page/{number}/"
        pages.append(Page(items=items, number=number, total_pages=total_pages, url=url, prev_url=None, next_url=None))

    for i, page in enumerate(pages):
        page.prev_url = pages[i - 1].url if i > 0 else None
        page.next_url = pages[i + 1].url if i < len(pages) - 1 else None

    return pages
