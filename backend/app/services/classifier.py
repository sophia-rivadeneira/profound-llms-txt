from __future__ import annotations

import re
from collections import Counter
from typing import Iterable
from urllib.parse import urlparse

# Maps first URL path segment → section name
DEFAULT_PATH_RULES: dict[str, str] = {
    # Documentation
    "docs": "Documentation",
    "documentation": "Documentation",
    "doc": "Documentation",
    "developer": "Documentation",
    "developers": "Documentation",
    "dev": "Documentation",
    # Guides & Tutorials
    "guide": "Guides",
    "guides": "Guides",
    "tutorial": "Guides",
    "tutorials": "Guides",
    "learn": "Guides",
    "learning": "Guides",
    "academy": "Guides",
    "course": "Guides",
    "courses": "Guides",
    "training": "Guides",
    "webinar": "Guides",
    "webinars": "Guides",
    "workshop": "Guides",
    "workshops": "Guides",
    "getting-started": "Guides",
    # API Reference
    "api": "API Reference",
    "api-reference": "API Reference",
    "reference": "API Reference",
    "sdk": "API Reference",
    "integrations": "API Reference",
    "integration": "API Reference",
    "openapi": "API Reference",
    # Product
    "platform": "Product",
    "product": "Product",
    "products": "Product",
    "features": "Product",
    "feature": "Product",
    "enterprise": "Product",
    "pro": "Product",
    "plans": "Product",
    # Use Cases
    "solutions": "Use Cases",
    "solution": "Use Cases",
    "use-cases": "Use Cases",
    "use-case": "Use Cases",
    "customers": "Use Cases",
    "customer": "Use Cases",
    "case-studies": "Use Cases",
    "case-study": "Use Cases",
    "industries": "Use Cases",
    "industry": "Use Cases",
    "for": "Use Cases",
    # Pricing
    "pricing": "Pricing",
    "plans-and-pricing": "Pricing",
    # Blog / News
    "blog": "Blog",
    "news": "Blog",
    "press": "Blog",
    "articles": "Blog",
    "posts": "Blog",
    "insights": "Blog",
    "stories": "Blog",
    "resources": "Blog",
    "podcast": "Blog",
    "videos": "Blog",
    "events": "Blog",
    "community": "Blog",
    # Changelog
    "changelog": "Changelog",
    "releases": "Changelog",
    "release-notes": "Changelog",
    "updates": "Changelog",
    "whats-new": "Changelog",
    # Legal
    "legal": "Legal",
    "privacy": "Legal",
    "terms": "Legal",
    "security": "Legal",
    "compliance": "Legal",
    "gdpr": "Legal",
    "cookies": "Legal",
    "trust": "Legal",
    # About
    "about": "About",
    "company": "About",
    "team": "About",
    "careers": "About",
    "jobs": "About",
    "mission": "About",
    "story": "About",
    "contact": "About",
    "partners": "About",
    "partner": "About",
    "investors": "About",
    # Support
    "support": "Support",
    "help": "Support",
    "faq": "Support",
    "faqs": "Support",
    "kb": "Support",
    "knowledge-base": "Support",
    "status": "Support",
}

# Sections that are supplementary — listed under ## Optional in llms.txt
OPTIONAL_SECTIONS = {"Blog", "Changelog", "Legal"}

# Display order for sections in the llms.txt output and the frontend pages
# list. Non-optional sections come first in this order, optional sections
# follow in the same order. Sections not in this list sort to the end.
SECTION_ORDER: list[str] = [
    "General",
    "Product",
    "Documentation",
    "Guides",
    "API Reference",
    "Use Cases",
    "Pricing",
    "About",
    "Support",
    "Blog",
    "Changelog",
    "Legal",
]


def is_optional_section(section: str) -> bool:
    return section in OPTIONAL_SECTIONS


# Common ISO-639-1 language codes seen as URL prefixes on docs sites.
# Not exhaustive; rare languages will simply not be stripped.
_LANG_CODES: frozenset[str] = frozenset({
    "en", "fr", "de", "es", "it", "pt", "ja", "ko", "zh", "cn", "tw", "ru",
    "ar", "hi", "nl", "sv", "no", "fi", "da", "pl", "cs", "tr", "vi", "th",
    "id", "fa", "he", "el", "uk", "ro", "hu",
})

_LOCALE_RE = re.compile(r"^[a-z]{2}-[a-z]{2}$", re.IGNORECASE)
_VERSION_RE = re.compile(r"^v\d+(\.\d+)*$", re.IGNORECASE)
# Numeric versions like "2.9.x", "1.0", "3.21.0" — no leading "v".
_NUMERIC_VERSION_RE = re.compile(r"^\d+(\.\d+|\.x)+$", re.IGNORECASE)
_RELEASE_KEYWORDS: frozenset[str] = frozenset({
    "next", "latest", "stable", "main", "master", "current",
})


def _is_locale_or_version(segment: str) -> bool:
    seg_low = segment.lower()
    if seg_low in _LANG_CODES:
        return True
    if seg_low in _RELEASE_KEYWORDS:
        return True
    if _LOCALE_RE.match(segment):
        return True
    if _VERSION_RE.match(segment):
        return True
    if _NUMERIC_VERSION_RE.match(segment):
        return True
    return False


_INDEX_FILE_RE = re.compile(r"^index\.(html?|php|md|aspx?)$", re.IGNORECASE)


def _normalize_segments(path: str) -> list[str]:
    segments = [s for s in path.split("/") if s]
    if segments and _INDEX_FILE_RE.match(segments[-1]):
        segments = segments[:-1]
    while segments and _is_locale_or_version(segments[0]):
        segments = segments[1:]
    return segments


def _label_segment(segment: str) -> str:
    words = re.split(r"[-_\s]+", segment)
    return " ".join(
        word[0].upper() + word[1:].lower() for word in words if word
    )


def classify_pages(
    pages: Iterable,
    custom_rules: dict[str, str] | None = None,
) -> dict[str, tuple[str, bool]]:
    classifications: dict[str, tuple[str, bool]] = {}
    unmatched: list[tuple[str, str]] = []  # (url, first_segment)

    for page in pages:
        url = page.url
        path = urlparse(url).path
        segments = _normalize_segments(path)
        if not segments:
            classifications[url] = ("General", False)
            continue

        first = segments[0].lower()
        rule_match: str | None = None
        if custom_rules and first in custom_rules:
            rule_match = custom_rules[first]
        elif first in DEFAULT_PATH_RULES:
            rule_match = DEFAULT_PATH_RULES[first]

        if rule_match:
            classifications[url] = (rule_match, is_optional_section(rule_match))
        else:
            unmatched.append((url, first))

    cluster_sizes = Counter(key for _, key in unmatched)
    for url, key in unmatched:
        if cluster_sizes[key] < 2 or len(key) < 3:
            classifications[url] = ("General", False)
        else:
            label = _label_segment(key)
            classifications[url] = (label, is_optional_section(label))

    return classifications
