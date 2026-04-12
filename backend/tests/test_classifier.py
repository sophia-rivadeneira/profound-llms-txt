from app.services.classifier import (
    classify_by_url,
    is_optional_section,
)


class TestClassifyByUrl:
    def test_docs_path_maps_to_documentation(self):
        assert classify_by_url("https://example.com/docs/intro") == "Documentation"

    def test_blog_path_maps_to_blog(self):
        assert classify_by_url("https://example.com/blog/2024/post") == "Blog"

    def test_api_path_maps_to_api_reference(self):
        assert classify_by_url("https://example.com/api/v1/users") == "API Reference"

    def test_changelog_path(self):
        assert classify_by_url("https://example.com/changelog") == "Changelog"

    def test_legal_variants(self):
        assert classify_by_url("https://example.com/privacy") == "Legal"
        assert classify_by_url("https://example.com/terms") == "Legal"

    def test_homepage_returns_none(self):
        assert classify_by_url("https://example.com/") is None

    def test_unknown_path_returns_none(self):
        assert classify_by_url("https://example.com/careers") is None

    def test_custom_rules_take_precedence(self):
        rules = {"learn": "Documentation"}
        assert classify_by_url("https://example.com/learn/intro", rules) == "Documentation"

    def test_custom_rules_override_defaults(self):
        rules = {"docs": "Knowledge Base"}
        assert classify_by_url("https://example.com/docs/x", rules) == "Knowledge Base"

    def test_first_segment_only(self):
        # only the first path segment is checked
        assert classify_by_url("https://example.com/products/docs/x") is None


class TestIsOptionalSection:
    def test_blog_is_optional(self):
        assert is_optional_section("Blog") is True

    def test_changelog_is_optional(self):
        assert is_optional_section("Changelog") is True

    def test_legal_is_optional(self):
        assert is_optional_section("Legal") is True

    def test_documentation_is_not_optional(self):
        assert is_optional_section("Documentation") is False

    def test_api_reference_is_not_optional(self):
        assert is_optional_section("API Reference") is False
