from __future__ import annotations

from dataclasses import dataclass, field
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


def extract_metadata(html: str, page_url: str) -> PageMeta:
    soup = BeautifulSoup(html, "lxml")
    page = PageMeta(url=page_url)

    html_title = soup.find("title")
    if html_title and html_title.string:
        page.title = html_title.string.strip()

    open_graph_title = soup.find("meta", attrs={"property": "og:title"})
    if open_graph_title and not page.title:
        page.title = open_graph_title.get("content", "").strip() or None

    meta_description = soup.find("meta", attrs={"name": "description"})
    if meta_description:
        page.description = meta_description.get("content", "").strip() or None

    open_graph_description = soup.find("meta", attrs={"property": "og:description"})
    if open_graph_description and not page.description:
        page.description = open_graph_description.get("content", "").strip() or None

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
