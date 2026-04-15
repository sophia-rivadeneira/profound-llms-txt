from app.models import PageData, Site
from app.services.generator import _build_markdown


def _make_site(title: str = "Example", domain: str = "example.com") -> Site:
    site = Site(url="https://example.com/", domain=domain, title=title)
    return site


def _make_page(
    url: str,
    title: str | None = None,
    description: str | None = None,
    section: str | None = None,
    is_optional: bool = False,
) -> PageData:
    return PageData(
        url=url,
        title=title,
        description=description,
        section=section,
        is_optional=is_optional,
    )


class TestBuildMarkdown:
    def test_includes_h1_from_site_title(self):
        site = _make_site(title="My Docs")
        content = _build_markdown(site, None, [])
        assert content.startswith("# My Docs")

    def test_falls_back_to_domain_when_no_title(self):
        site = _make_site(title=None)
        content = _build_markdown(site, None, [])
        assert content.startswith("# example.com")

    def test_includes_summary_as_blockquote(self):
        site = _make_site()
        content = _build_markdown(site, "A great site for developers.", [])
        assert "> A great site for developers." in content

    def test_omits_blockquote_when_no_summary(self):
        site = _make_site()
        content = _build_markdown(site, None, [])
        assert ">" not in content

    def test_groups_pages_by_section(self):
        site = _make_site()
        pages = [
            _make_page("https://example.com/docs/intro", "Intro", section="Documentation"),
            _make_page("https://example.com/docs/setup", "Setup", section="Documentation"),
            _make_page("https://example.com/api/users", "Users API", section="API Reference"),
        ]
        content = _build_markdown(site, None, pages)
        assert "## Documentation" in content
        assert "## API Reference" in content

    def test_formats_page_links(self):
        site = _make_site()
        pages = [
            _make_page(
                "https://example.com/docs/intro",
                "Intro",
                description="Getting started",
                section="Documentation",
            ),
        ]
        content = _build_markdown(site, None, pages)
        assert "- [Intro](https://example.com/docs/intro): Getting started" in content

    def test_falls_back_to_url_when_no_title(self):
        site = _make_site()
        pages = [
            _make_page("https://example.com/docs/x", section="Documentation"),
        ]
        content = _build_markdown(site, None, pages)
        assert "- [https://example.com/docs/x](https://example.com/docs/x)" in content

    def test_optional_pages_go_under_optional_heading(self):
        site = _make_site()
        pages = [
            _make_page("https://example.com/docs/intro", "Intro", section="Documentation"),
            _make_page(
                "https://example.com/blog/post",
                "Blog Post",
                section="Blog",
                is_optional=True,
            ),
        ]
        content = _build_markdown(site, None, pages)
        assert "## Optional" in content
        # Optional section should appear after main sections
        assert content.index("## Documentation") < content.index("## Optional")
        # Blog subsection under Optional
        assert "### Blog" in content

    def test_omits_optional_heading_when_no_optional_pages(self):
        site = _make_site()
        pages = [
            _make_page("https://example.com/docs/intro", "Intro", section="Documentation"),
        ]
        content = _build_markdown(site, None, pages)
        assert "## Optional" not in content

    def test_full_output_shape(self):
        site = _make_site(title="My Site")
        pages = [
            _make_page("https://example.com/docs/x", "Doc X", section="Documentation"),
            _make_page(
                "https://example.com/blog/y",
                "Blog Y",
                section="Blog",
                is_optional=True,
            ),
        ]
        content = _build_markdown(site, "A summary.", pages)
        lines = content.split("\n")
        assert lines[0] == "# My Site"
        assert "> A summary." in content
        assert "## Documentation" in content
        assert "## Optional" in content


