from __future__ import annotations

from urllib.parse import urlparse

DEFAULT_PATH_RULES: dict[str, str] = {
    "docs": "Documentation",
    "documentation": "Documentation",
    "guide": "Guides",
    "guides": "Guides",
    "tutorial": "Tutorials",
    "tutorials": "Tutorials",
    "api": "API Reference",
    "api-reference": "API Reference",
    "reference": "API Reference",
    "blog": "Blog",
    "changelog": "Changelog",
    "releases": "Changelog",
    "legal": "Legal",
    "privacy": "Legal",
    "terms": "Legal",
    "about": "About",
    "pricing": "About",
    "support": "Support",
    "help": "Support",
    "faq": "Support",
}

OPTIONAL_SECTIONS = {"Blog", "Changelog", "Legal"}


def classify_by_url(url: str, custom_rules: dict[str, str] | None = None) -> str | None:
    path = urlparse(url).path.strip("/")
    if not path:
        return None
    segment = path.split("/")[0].lower()

    if custom_rules and segment in custom_rules:
        return custom_rules[segment]

    return DEFAULT_PATH_RULES.get(segment)


def is_optional_section(section: str) -> bool:
    return section in OPTIONAL_SECTIONS
