from dataclasses import dataclass, field
from typing import Any


@dataclass
class SiteConfig:
    title: str = "My Site"
    description: str = ""
    url: str = "http://localhost:8000"
    language: str = "en"
    home_page: str = "welcome"


@dataclass
class ContentConfig:
    pages: str = "content/pages"
    posts: str = "content/posts"


@dataclass
class OutputConfig:
    directory: str = "../result"


@dataclass
class StaticConfig:
    directory: str = "static"


@dataclass
class ThemeConfig:
    name: str = "minimal"
    directory: str = "themes"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class BlogConfig:
    posts_per_page: int = 10
    excerpt_enabled: bool = True
    excerpt_length: int = 280


@dataclass
class I18nConfig:
    languages: list[str] = field(default_factory=list)
    default_language: str = ""
    strings: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetsConfig:
    fingerprint: bool = True


@dataclass
class UrlsConfig:
    pages: str = "/pages/{slug}/"
    posts: str = "/blog/{slug}/"
    tags: str = "/tags/{slug}/"
    categories: str = "/categories/{slug}/"
    tags_index: str = "/tags/"
    categories_index: str = "/categories/"


@dataclass
class FeedsConfig:
    enabled: bool = True
    format: str = "rss"


@dataclass
class SearchConfig:
    enabled: bool = True


@dataclass
class SitemapConfig:
    enabled: bool = True


@dataclass
class RobotsConfig:
    enabled: bool = True

@dataclass
class Config:
    site: SiteConfig = field(default_factory=SiteConfig)
    content: ContentConfig = field(default_factory=ContentConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    static: StaticConfig = field(default_factory=StaticConfig)
    theme: ThemeConfig = field(default_factory=ThemeConfig)

    nav: list[Any] = field(default_factory=list)
    menu: list[Any] = field(default_factory=list)
    social: list[Any] = field(default_factory=list)

    blog: BlogConfig = field(default_factory=BlogConfig)
    i18n: I18nConfig = field(default_factory=I18nConfig)
    assets: AssetsConfig = field(default_factory=AssetsConfig)
    urls: UrlsConfig = field(default_factory=UrlsConfig)
    feeds: FeedsConfig = field(default_factory=FeedsConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    sitemap: SitemapConfig = field(default_factory=SitemapConfig)
    robots: RobotsConfig = field(default_factory=RobotsConfig)