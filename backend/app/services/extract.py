from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import chain
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.services.urls import normalize_url, resolve_url


@dataclass
class PageMeta:
    url: str
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    h1: str | None = None
    links: list[str] = field(default_factory=list)


_MAX_HREFLESS_GUESSES_PER_PAGE = 10
_BOILERPLATE_RE = re.compile(r"^(?:©|\(c\)|copyright\b|\d{4}\b)", re.IGNORECASE)


def _title_text(soup: BeautifulSoup) -> str | None:
    tag = soup.find("title")
    if not tag or not tag.string:
        return None
    return tag.string.strip() or None


def _meta_content(soup: BeautifulSoup, **attrs: str) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    if not tag:
        return None
    content = tag.get("content", "").strip()
    return content or None


def _looks_like_boilerplate(text: str) -> bool:
    stripped = text.strip()
    if stripped.isdigit():
        return True
    return bool(_BOILERPLATE_RE.match(stripped))


def extract_metadata(html: str, page_url: str) -> PageMeta:
    soup = BeautifulSoup(html, "lxml")
    page = PageMeta(url=page_url)

    page.title = _title_text(soup) or _meta_content(soup, property="og:title")
    page.description = (
        _meta_content(soup, name="description")
        or _meta_content(soup, property="og:description")
    )

    canonical_link = soup.find("link", attrs={"rel": "canonical"})
    canonical_href = canonical_link.get("href") if canonical_link else None
    if canonical_href:
        resolved = resolve_url(canonical_href, page_url)
        if resolved:
            page.canonical_url = resolved

    h1_tag = soup.find("h1")
    if h1_tag:
        page.h1 = h1_tag.get_text(strip=True) or None

    collected_links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(page_url, anchor["href"])
        normalized = normalize_url(absolute)
        if normalized not in collected_links:
            collected_links.add(normalized)
            page.links.append(normalized)

    # Some sites render nav links as <a> with no href (onClick handlers only).
    # Derive candidate URLs from link text inside structural regions
    guesses = 0
    structural_anchors = chain.from_iterable(
        container.find_all("a")
        for container in soup.find_all(["nav", "footer", "header"])
    )
    for anchor in structural_anchors:
        if guesses >= _MAX_HREFLESS_GUESSES_PER_PAGE:
            break
        if anchor.get("href"):
            continue
        text = anchor.get_text(strip=True)
        if not text or len(text) > 40:
            continue
        if _looks_like_boilerplate(text):
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        if len(slug) < 3:
            continue
        candidate = normalize_url(urljoin(page_url, f"/{slug}"))
        if candidate not in collected_links:
            collected_links.add(candidate)
            page.links.append(candidate)
            guesses += 1

    return page


def looks_like_js_shell(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if body is None:
        return True

    body_text = body.get_text(separator=" ", strip=True)
    framework_root = body.find("div", id=lambda x: x in ("root", "__next", "app", "__nuxt"))

    if framework_root is not None and len(body_text) < 500:
        return True

    return len(body_text) == 0
