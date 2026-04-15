from __future__ import annotations

from contextlib import asynccontextmanager

from playwright.async_api import Browser, async_playwright


@asynccontextmanager
async def optional_browser(enabled: bool):
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


async def fetch_rendered_html(
    url: str,
    browser: Browser,
    timeout_ms: int = 15000,
) -> str | None:
    try:
        page = await browser.new_page(user_agent="ProfoundLlmsTxtBot/0.1 (Playwright)")
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        # Scroll to bottom to trigger lazy-loaded nav/footer links, then back to top.
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(800)
        await page.evaluate("window.scrollTo(0, 0)")
        content = await page.content()
        await page.close()
        return content
    except Exception:
        return None
