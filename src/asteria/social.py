"""
Social media links in the footer.   
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass
class SocialLink:
    platform: str
    url: str
    label: str    

def build_social_links(social_config: list[dict[str, Any]]) -> list[SocialLink]:

    links: list[SocialLink] = []

    for entry in social_config:
        platform = str(entry.get("platform", "")).strip().lower()
        url = entry.get("url")
        label = entry.get("label")

        if not platform or not url or not label:
            continue               

        links.append(
            SocialLink(platform=platform, url=str(url), label=label)
        )

    return links
