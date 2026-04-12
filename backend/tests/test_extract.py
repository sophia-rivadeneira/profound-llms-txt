from app.services.extract import extract_metadata, looks_like_js_shell


FULL_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <meta name="description" content="A test description">
    <meta property="og:title" content="OG Title">
    <meta property="og:description" content="OG Description">
    <link rel="canonical" href="https://example.com/canonical">
</head>
<body>
    <h1>Main Heading</h1>
    <a href="/about">About</a>
    <a href="https://example.com/contact">Contact</a>
    <a href="https://other.com/ext">External</a>
</body>
</html>
"""


class TestExtractMetadata:
    def test_title(self):
        meta = extract_metadata(FULL_PAGE, "https://example.com/page")
        assert meta.title == "Test Page"

    def test_description(self):
        meta = extract_metadata(FULL_PAGE, "https://example.com/page")
        assert meta.description == "A test description"

    def test_canonical(self):
        meta = extract_metadata(FULL_PAGE, "https://example.com/page")
        assert meta.canonical_url == "https://example.com/canonical"

    def test_h1(self):
        meta = extract_metadata(FULL_PAGE, "https://example.com/page")
        assert meta.h1 == "Main Heading"

    def test_links_extracted(self):
        meta = extract_metadata(FULL_PAGE, "https://example.com/page")
        assert "https://example.com/about" in meta.links
        assert "https://example.com/contact" in meta.links
        assert "https://other.com/ext" in meta.links

    def test_og_fallback_when_no_title(self):
        html = '<html><head><meta property="og:title" content="Fallback"></head><body></body></html>'
        meta = extract_metadata(html, "https://example.com/page")
        assert meta.title == "Fallback"

    def test_og_desc_fallback(self):
        html = '<html><head><meta property="og:description" content="OG Desc"></head><body></body></html>'
        meta = extract_metadata(html, "https://example.com/page")
        assert meta.description == "OG Desc"

    def test_deduplicates_links(self):
        html = '<html><body><a href="/a">A</a><a href="/a">A again</a></body></html>'
        meta = extract_metadata(html, "https://example.com/page")
        a_links = [l for l in meta.links if l.endswith("/a")]
        assert len(a_links) == 1


class TestLooksLikeJsShell:
    def test_empty_body(self):
        assert looks_like_js_shell("<html><body></body></html>")

    def test_react_root(self):
        html = '<html><body><div id="root"></div></body></html>'
        assert looks_like_js_shell(html)

    def test_next_root(self):
        html = '<html><body><div id="__next"></div></body></html>'
        assert looks_like_js_shell(html)

    def test_full_content_not_shell(self):
        assert not looks_like_js_shell(FULL_PAGE)

    def test_no_body(self):
        assert looks_like_js_shell("<html></html>")
