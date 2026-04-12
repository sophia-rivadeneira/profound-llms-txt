from __future__ import annotations

import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from playwright.async_api import Browser, async_playwright
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CrawlJob, PageData, Site
from app.services.extract import PageMeta, extract_metadata, looks_like_js_shell
from app.services.sitemap import fetch_sitemap_urls
from app.services.robots import RobotsChecker
from app.services.urls import (
    USER_AGENT,
    is_same_domain,
    normalize_url,
)


@dataclass
class CrawlConfig:
    max_pages: int = 200
    max_depth: int = 5
    max_duration_seconds: int = 120
    concurrency: int = 5
    delay_seconds: float = 0.1
    use_playwright_fallback: bool = True


@dataclass
class _QueueItem:
    url: str
    depth: int


@dataclass
class CrawlResult:
    pages_found: int = 0
    error_message: str | None = None
    pages: list[PageMeta] = field(default_factory=list)


async def run_crawl(
    site: Site,
    crawl_job: CrawlJob,
    session: AsyncSession,
    config: CrawlConfig | None = None,
) -> None:
    config = config or CrawlConfig()
    now = datetime.now(timezone.utc)

    crawl_job.status = "running"
    crawl_job.started_at = now
    await session.commit()

    try:
        result = await _crawl(site.url, config)

        crawl_job.status = "completed"
        crawl_job.pages_found = result.pages_found
        crawl_job.completed_at = datetime.now(timezone.utc)
        if result.error_message:
            crawl_job.error_message = result.error_message

        for meta in result.pages:
            page = PageData(
                crawl_job_id=crawl_job.id,
                url=meta.url,
                canonical_url=meta.canonical_url,
                title=meta.title,
                description=meta.description,
                crawled_at=datetime.now(timezone.utc),
            )
            session.add(page)

        base_normalized = normalize_url(site.url)
        homepage_meta = next(
            (p for p in result.pages if normalize_url(p.url) == base_normalized),
            result.pages[0] if result.pages else None,
        )
        if homepage_meta:
            if homepage_meta.title and not site.title:
                site.title = homepage_meta.title
            if homepage_meta.description and not site.description:
                site.description = homepage_meta.description

        await session.commit()

    except Exception as exc:
        await session.rollback()
        crawl_job.status = "failed"
        crawl_job.error_message = str(exc)[:500]
        crawl_job.completed_at = datetime.now(timezone.utc)
        await session.commit()


async def _crawl(base_url: str, config: CrawlConfig) -> CrawlResult:
    robots = RobotsChecker()
    visited: set[str] = set()
    result = CrawlResult()
    start_time = time.monotonic()
    semaphore = asyncio.Semaphore(config.concurrency)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=15,
    ) as client:
        base_normalized = normalize_url(base_url)
        await robots.can_fetch(base_normalized, client)

        sitemap_urls_from_robots = robots.get_sitemaps(base_normalized)
        sitemap_urls = await fetch_sitemap_urls(
            base_url, client, extra_sitemap_urls=sitemap_urls_from_robots
        )

        queue: deque[_QueueItem] = deque()

        if sitemap_urls:
            for u in sitemap_urls:
                if u not in visited and is_same_domain(u, base_url):
                    queue.append(_QueueItem(url=u, depth=0))
                    visited.add(u)

        if base_normalized not in visited:
            queue.append(_QueueItem(url=base_normalized, depth=0))
            visited.add(base_normalized)

        async with _optional_browser(config.use_playwright_fallback) as browser:
            while queue:
                if result.pages_found >= config.max_pages:
                    break
                elapsed = time.monotonic() - start_time
                if elapsed >= config.max_duration_seconds:
                    result.error_message = "Crawl timed out"
                    break

                batch_size = min(
                    config.concurrency, len(queue), config.max_pages - result.pages_found
                )
                batch = [queue.popleft() for _ in range(batch_size)]

                tasks = [
                    _fetch_page(item, client, robots, semaphore, config, base_url, browser)
                    for item in batch
                ]
                pages = await asyncio.gather(*tasks)

                for item, meta in zip(batch, pages):
                    if meta is None:
                        continue
                    result.pages.append(meta)
                    result.pages_found += 1

                    if result.pages_found >= config.max_pages:
                        break

                    for link in meta.links:
                        if link in visited:
                            continue
                        if not is_same_domain(link, base_url):
                            continue
                        new_depth = item.depth + 1
                        if new_depth > config.max_depth:
                            continue
                        visited.add(link)
                        queue.append(_QueueItem(url=link, depth=new_depth))

                if config.delay_seconds > 0 and queue:
                    await asyncio.sleep(config.delay_seconds)

    return result


@asynccontextmanager
async def _optional_browser(enabled: bool):
    if not enabled:
        yield None
        return
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        await browser.close()
        await pw.stop()


async def _fetch_page(
    item: _QueueItem,
    client: httpx.AsyncClient,
    robots: RobotsChecker,
    semaphore: asyncio.Semaphore,
    config: CrawlConfig,
    base_url: str,
    browser: Browser | None = None,
) -> PageMeta | None:
    async with semaphore:
        if not await robots.can_fetch(item.url, client):
            return None

        try:
            resp = await client.get(item.url, timeout=15)
        except httpx.HTTPError:
            return None

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None

        html = resp.text
        final_url = normalize_url(str(resp.url))
        meta = extract_metadata(html, final_url)
        meta.url = final_url

        if config.use_playwright_fallback and looks_like_js_shell(html) and browser:
            rendered = await _fetch_rendered_html(final_url, browser)
            if rendered:
                meta = extract_metadata(rendered, final_url)
                meta.url = final_url

        return meta


async def _fetch_rendered_html(url: str, browser: Browser, timeout_ms: int = 15000) -> str | None:
    try:
        page = await browser.new_page(user_agent="ProfoundLlmsTxtBot/0.1 (Playwright)")
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        content = await page.content()
        await page.close()
        return content
    except Exception:
        return None
