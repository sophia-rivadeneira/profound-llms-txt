from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

import tldextract

USER_AGENT = "ProfoundLlmsTxtBot/0.1"


def normalize_url(url: str) -> str:
    """Normalize URL format: lowercase scheme/host, strip trailing slash and query/fragment."""
    parsed = urlparse(url)
    if not parsed.netloc:
        return url
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def normalize_to_origin(url: str) -> str:
    """Strip path/query/fragment — returns just scheme + host. Used for seed URL normalization."""
    parsed = urlparse(url)
    if not parsed.netloc:
        return url
    return normalize_url(f"{parsed.scheme}://{parsed.netloc}/")


def domain_to_slug(domain: str) -> str:
    """Convert a domain to a clean URL slug. www.tryprofound.com → tryprofound"""
    r = tldextract.extract(domain)
    subdomain = re.sub(r"^www$", "", r.subdomain)  # strip bare www, keep others
    parts = [p for p in [subdomain, r.domain] if p]
    slug = "-".join(parts)
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _canonical_host(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def is_same_domain(url: str, base_url: str) -> bool:
    return _canonical_host(extract_domain(url)) == _canonical_host(extract_domain(base_url))


def resolve_url(href: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return normalize_url(absolute)
