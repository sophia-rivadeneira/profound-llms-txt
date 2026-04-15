from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

import httpx

from app.services.urls import normalize_url


async def fetch_sitemap_urls(
    base_url: str,
    client: httpx.AsyncClient,
    extra_sitemap_urls: list[str] | None = None,
) -> list[str]:
    candidates = [f"{base_url.rstrip('/')}/sitemap.xml"]
    if extra_sitemap_urls:
        candidates.extend(extra_sitemap_urls)

    seen: set[str] = set()
    result: list[str] = []

    for sitemap_url in candidates:
        urls = await _parse_sitemap(sitemap_url, client, seen)
        result.extend(urls)

    return result


async def _parse_sitemap(
    sitemap_url: str,
    client: httpx.AsyncClient,
    seen: set[str],
    depth: int = 0,
    max_depth: int = 3,
) -> list[str]:
    if sitemap_url in seen or depth > max_depth:
        return []
    seen.add(sitemap_url)

    try:
        resp = await client.get(sitemap_url, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return []
    except httpx.HTTPError:
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")
    if not soup.find():
        return []

    # Sitemap index — recurse into child sitemaps
    if soup.find("sitemapindex"):
        urls: list[str] = []
        for sitemap_tag in soup.find_all("sitemap"):
            loc = sitemap_tag.find("loc")
            if loc and loc.string:
                urls.extend(await _parse_sitemap(
                    loc.string.strip(), client, seen, depth=depth + 1, max_depth=max_depth
                ))
        return urls

    result: list[str] = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if not loc or not loc.string:
            continue
        raw = loc.string.strip()
        parsed = urlparse(raw)
        if not parsed.path or (parsed.path == "/" and parsed.fragment):
            continue
        result.append(normalize_url(raw))

    return result
