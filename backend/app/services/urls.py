from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

USER_AGENT = "ProfoundLlmsTxtBot/0.1"


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.netloc:
        return url
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def is_same_domain(url: str, base_url: str) -> bool:
    url_domain = extract_domain(url)
    base_domain = extract_domain(base_url)
    return url_domain == base_domain or url_domain.endswith(f".{base_domain}")


def resolve_url(href: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return normalize_url(absolute)
