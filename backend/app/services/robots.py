from __future__ import annotations
import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import httpx
from app.services.urls import USER_AGENT


class RobotsChecker:
    def __init__(self) -> None:
        self._parsers: dict[str, RobotFileParser] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def can_fetch(self, url: str, client: httpx.AsyncClient) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        async with self._global_lock:
            if origin not in self._locks:
                self._locks[origin] = asyncio.Lock()
            lock = self._locks[origin]

        async with lock:
            if origin not in self._parsers:
                parser = RobotFileParser()
                robots_url = f"{origin}/robots.txt"
                try:
                    resp = await client.get(robots_url, follow_redirects=True, timeout=10)
                    if resp.status_code == 200:
                        parser.parse(resp.text.splitlines())
                    else:
                        parser.allow_all = True
                except httpx.HTTPError:
                    parser.allow_all = True
                self._parsers[origin] = parser

        return self._parsers[origin].can_fetch(USER_AGENT, url)

    def get_sitemaps(self, base_url: str) -> list[str]:
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._parsers.get(origin)
        if parser is None:
            return []
        return list(parser.site_maps() or [])
