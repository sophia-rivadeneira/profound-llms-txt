import pytest
import httpx

from app.services.sitemap import fetch_sitemap_urls


SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page1</loc></url>
  <url><loc>https://example.com/page2</loc></url>
  <url><loc>https://example.com/page3/</loc></url>
</urlset>
"""

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>
"""

CHILD_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/child-page</loc></url>
</urlset>
"""


@pytest.mark.asyncio
async def test_parses_urlset(httpx_mock):
    httpx_mock.add_response(
        url="https://example.com/sitemap.xml",
        text=SITEMAP_XML,
    )
    async with httpx.AsyncClient() as client:
        urls = await fetch_sitemap_urls("https://example.com", client)
    assert "https://example.com/page1" in urls
    assert "https://example.com/page2" in urls
    assert "https://example.com/page3" in urls  # trailing slash stripped


@pytest.mark.asyncio
async def test_handles_sitemap_index(httpx_mock):
    httpx_mock.add_response(
        url="https://example.com/sitemap.xml",
        text=SITEMAP_INDEX,
    )
    httpx_mock.add_response(
        url="https://example.com/sitemap-pages.xml",
        text=CHILD_SITEMAP,
    )
    async with httpx.AsyncClient() as client:
        urls = await fetch_sitemap_urls("https://example.com", client)
    assert "https://example.com/child-page" in urls


@pytest.mark.asyncio
async def test_handles_missing_sitemap(httpx_mock):
    httpx_mock.add_response(
        url="https://example.com/sitemap.xml",
        status_code=404,
    )
    async with httpx.AsyncClient() as client:
        urls = await fetch_sitemap_urls("https://example.com", client)
    assert urls == []


@pytest.mark.asyncio
async def test_handles_invalid_xml(httpx_mock):
    httpx_mock.add_response(
        url="https://example.com/sitemap.xml",
        text="not xml at all",
    )
    async with httpx.AsyncClient() as client:
        urls = await fetch_sitemap_urls("https://example.com", client)
    assert urls == []
