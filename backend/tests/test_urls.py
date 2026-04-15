from app.services.urls import extract_domain, is_same_domain, normalize_url, resolve_url


class TestNormalizeUrl:
    def test_strips_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/about/") == "https://example.com/about"

    def test_preserves_root_slash(self):
        assert normalize_url("https://example.com") == "https://example.com/"

    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTPS://Example.COM/Page") == "https://example.com/Page"

    def test_strips_query_string(self):
        assert normalize_url("https://example.com/page?ref=1") == "https://example.com/page"


class TestExtractDomain:
    def test_basic(self):
        assert extract_domain("https://example.com/path") == "example.com"

    def test_with_port(self):
        assert extract_domain("https://example.com:8080/path") == "example.com:8080"

    def test_subdomain(self):
        assert extract_domain("https://docs.example.com") == "docs.example.com"


class TestIsSameDomain:
    def test_same(self):
        assert is_same_domain("https://example.com/about", "https://example.com/")

    def test_subdomain_rejected(self):
        assert not is_same_domain("https://docs.example.com/page", "https://example.com/")

    def test_www_normalized(self):
        assert is_same_domain("https://example.com/page", "https://www.example.com/")
        assert is_same_domain("https://www.example.com/page", "https://example.com/")

    def test_different_domain(self):
        assert not is_same_domain("https://other.com/page", "https://example.com/")


class TestResolveUrl:
    def test_relative(self):
        result = resolve_url("/about", "https://example.com/page")
        assert result == "https://example.com/about"

    def test_absolute(self):
        result = resolve_url("https://example.com/contact", "https://example.com/page")
        assert result == "https://example.com/contact"

    def test_rejects_non_http(self):
        result = resolve_url("mailto:hi@example.com", "https://example.com/page")
        assert result is None

    def test_rejects_javascript(self):
        result = resolve_url("javascript:void(0)", "https://example.com/page")
        assert result is None
