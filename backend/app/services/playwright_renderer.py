from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from playwright.async_api import Browser, async_playwright

from app.services.extract import PageMeta, extract_metadata


@asynccontextmanager
async def optional_browser(enabled: bool):
    if not enabled:
        yield None
        return

    pw = None
    browser = None

    async def get_browser() -> Browser:
        nonlocal pw, browser
        if browser is None:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True)
        return browser

    try:
        yield get_browser
    finally:
        if browser is not None:
            await browser.close()
        if pw is not None:
            await pw.stop()


async def fetch_rendered_html(
    url: str,
    browser: Browser,
    timeout_ms: int = 15000,
) -> str | None:
    try:
        page = await browser.new_page(user_agent="ProfoundLlmsTxtBot/0.1 (Playwright)")
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(800)
        await page.evaluate("window.scrollTo(0, 0)")
        content = await page.content()
        await page.close()
        return content
    except Exception:
        return None


async def re_fetch_with_playwright(
    url: str,
    get_browser: Callable[[], Awaitable[object]],
) -> PageMeta | None:
    browser = await get_browser()
    rendered = await fetch_rendered_html(url, browser)
    if not rendered:
        return None
    meta = extract_metadata(rendered, url)
    meta.url = url
    return meta
