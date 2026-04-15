from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import CrawlJob, PageData, Site
from app.services.extract import PageMeta, extract_metadata, looks_like_js_shell
from app.services.generator import generate_llms_txt
from app.services.playwright_renderer import Browser, fetch_rendered_html, optional_browser
from app.services.sitemap import fetch_sitemap_urls
from app.services.robots import RobotsChecker
from app.services.urls import USER_AGENT, is_same_domain, normalize_url


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


async def run_crawl_in_background(site_id: int, crawl_job_id: int) -> None:
    """Open a fresh session and run a crawl for the given job. Used by
    FastAPI `BackgroundTasks` — the original request's session is already
    closed by the time this fires, so we can't share it."""
    async with AsyncSessionLocal() as session:
        site = await session.get(Site, site_id)
        crawl_job = await session.get(CrawlJob, crawl_job_id)
        if site and crawl_job:
            await run_crawl(site, crawl_job, session)


async def _persist_progress(
    crawl_job: CrawlJob,
    session: AsyncSession,
    pages_found: int,
) -> None:
    crawl_job.pages_found = pages_found
    await session.commit()


def _apply_homepage_meta(site: Site, pages: list[PageMeta]) -> None:
    if not pages:
        return
    base_normalized = normalize_url(site.url)
    homepage_meta = next(
        (p for p in pages if normalize_url(p.url) == base_normalized),
        pages[0],
    )
    if homepage_meta.title and not site.title:
        site.title = homepage_meta.title
    if homepage_meta.description and not site.description:
        site.description = homepage_meta.description


async def run_crawl(
    site: Site,
    crawl_job: CrawlJob,
    session: AsyncSession,
    config: CrawlConfig | None = None,
) -> None:
    config = config or CrawlConfig()

    crawl_job.status = "running"
    crawl_job.started_at = datetime.now(timezone.utc)
    await session.commit()

    try:
        result = await asyncio.wait_for(
            _crawl(
                site.url,
                config,
                progress_callback=partial(_persist_progress, crawl_job, session),
            ),
            timeout=config.max_duration_seconds,
        )

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

        _apply_homepage_meta(site, result.pages)

        await session.commit()

        await generate_llms_txt(site, crawl_job, session)

    except Exception as exc:
        await session.rollback()
        crawl_job.status = "failed"
        if isinstance(exc, asyncio.TimeoutError):
            crawl_job.error_message = (
                f"Crawl exceeded maximum duration ({config.max_duration_seconds}s). "
                "The site may have an unusually large sitemap or slow response times."
            )
        else:
            crawl_job.error_message = str(exc)[:500]
        crawl_job.completed_at = datetime.now(timezone.utc)
        await session.commit()


async def _crawl(
    base_url: str,
    config: CrawlConfig,
    progress_callback: Callable[[int], Awaitable[None]] | None = None,
) -> CrawlResult:
    robots = RobotsChecker()
    visited: set[str] = set()
    final_urls_seen: set[str] = set()
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

        async with optional_browser(config.use_playwright_fallback) as browser:
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
                    if meta.url in final_urls_seen:
                        continue
                    final_urls_seen.add(meta.url)
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

                if progress_callback is not None:
                    await progress_callback(result.pages_found)

                if config.delay_seconds > 0 and queue:
                    await asyncio.sleep(config.delay_seconds)

    return result


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

        if resp.status_code >= 400:
            return None

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None

        html = resp.text
        final_url = normalize_url(str(resp.url))
        meta = extract_metadata(html, final_url)
        meta.url = final_url

        if config.use_playwright_fallback and looks_like_js_shell(html) and browser:
            rendered = await fetch_rendered_html(final_url, browser)
            if rendered:
                meta = extract_metadata(rendered, final_url)
                meta.url = final_url

        return meta
