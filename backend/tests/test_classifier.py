from types import SimpleNamespace

from app.services.classifier import (
    _is_locale_or_version,
    _label_segment,
    _normalize_segments,
    classify_pages,
    is_optional_section,
)


def _page(url: str) -> SimpleNamespace:
    return SimpleNamespace(url=url)


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


class TestIsLocaleOrVersion:
    def test_language_codes(self):
        assert _is_locale_or_version("en")
        assert _is_locale_or_version("ja")
        assert _is_locale_or_version("cn")
        assert _is_locale_or_version("EN")  # case-insensitive

    def test_locale_codes(self):
        assert _is_locale_or_version("en-us")
        assert _is_locale_or_version("pt-br")
        assert _is_locale_or_version("zh-CN")

    def test_v_prefix_versions(self):
        assert _is_locale_or_version("v1")
        assert _is_locale_or_version("v2.0")
        assert _is_locale_or_version("v3.21.0")

    def test_numeric_versions(self):
        assert _is_locale_or_version("1.0")
        assert _is_locale_or_version("2.9.x")
        assert _is_locale_or_version("3.21.0")

    def test_release_keywords(self):
        assert _is_locale_or_version("next")
        assert _is_locale_or_version("latest")
        assert _is_locale_or_version("stable")
        assert _is_locale_or_version("main")

    def test_normal_words_are_not_versions(self):
        assert not _is_locale_or_version("payments")
        assert not _is_locale_or_version("architecture")
        assert not _is_locale_or_version("camel-k")


class TestNormalizeSegments:
    def test_empty_path(self):
        assert _normalize_segments("/") == []
        assert _normalize_segments("") == []

    def test_basic_path(self):
        assert _normalize_segments("/docs/intro") == ["docs", "intro"]

    def test_strips_leading_locale(self):
        assert _normalize_segments("/en/docs/intro") == ["docs", "intro"]

    def test_strips_leading_version(self):
        assert _normalize_segments("/v2/api/users") == ["api", "users"]

    def test_strips_multiple_prefixes(self):
        # /en/v2/foo → strip both
        assert _normalize_segments("/en/v2/foo") == ["foo"]

    def test_does_not_strip_locale_in_middle(self):
        # Only leading locale segments are stripped.
        assert _normalize_segments("/docs/en/intro") == ["docs", "en", "intro"]

    def test_strips_trailing_index_html(self):
        # Only the literal "index.html" leaf is stripped — leading locale
        # stripping is independent and runs from the front.
        assert _normalize_segments("/camel-k/next/index.html") == ["camel-k", "next"]

    def test_strips_trailing_index_php(self):
        assert _normalize_segments("/products/index.php") == ["products"]

    def test_locale_then_index(self):
        assert _normalize_segments("/en/docs/index.html") == ["docs"]


class TestLabelSegment:
    def test_simple_word(self):
        assert _label_segment("architecture") == "Architecture"

    def test_hyphenated(self):
        assert _label_segment("payments-api") == "Payments Api"

    def test_underscored(self):
        assert _label_segment("use_cases") == "Use Cases"

    def test_camel_k(self):
        assert _label_segment("camel-k") == "Camel K"


class TestClassifyPages:
    def test_empty(self):
        assert classify_pages([]) == {}

    def test_homepage_is_general(self):
        result = classify_pages([_page("https://example.com/")])
        assert result["https://example.com/"] == ("General", False)

    def test_rule_match_takes_precedence(self):
        result = classify_pages([
            _page("https://example.com/docs/intro"),
            _page("https://example.com/blog/post-1"),
        ])
        assert result["https://example.com/docs/intro"] == ("Documentation", False)
        assert result["https://example.com/blog/post-1"] == ("Blog", True)

    def test_rule_match_after_locale_strip(self):
        # /en/docs/intro should still match the "docs" rule.
        result = classify_pages([_page("https://example.com/en/docs/intro")])
        assert result["https://example.com/en/docs/intro"] == ("Documentation", False)

    def test_clusters_unmatched_pages_by_first_segment(self):
        pages = [
            _page("https://example.com/wordpress/managed"),
            _page("https://example.com/wordpress/staging"),
            _page("https://example.com/wordpress/backups"),
            _page("https://example.com/cloud/computing"),
            _page("https://example.com/cloud/storage"),
        ]
        result = classify_pages(pages)
        assert result["https://example.com/wordpress/managed"] == ("Wordpress", False)
        assert result["https://example.com/cloud/computing"] == ("Cloud", False)

    def test_singleton_clusters_fall_back_to_general(self):
        pages = [
            _page("https://example.com/loneliness"),
            _page("https://example.com/wordpress/a"),
            _page("https://example.com/wordpress/b"),
        ]
        result = classify_pages(pages)
        assert result["https://example.com/loneliness"] == ("General", False)
        assert result["https://example.com/wordpress/a"] == ("Wordpress", False)

    def test_short_labels_fall_back_to_general(self):
        # Two-char segments like /lp/ are noise, even if there are many pages.
        pages = [
            _page("https://example.com/lp/a"),
            _page("https://example.com/lp/b"),
            _page("https://example.com/lp/c"),
        ]
        result = classify_pages(pages)
        assert result["https://example.com/lp/a"] == ("General", False)

    def test_index_html_stripped_before_clustering(self):
        # /camel-k/next/index.html should never produce an "Index.html" label;
        # the index.html leaf is stripped before clustering.
        pages = [
            _page("https://example.com/camel-k/next/index.html"),
            _page("https://example.com/camel-k/next/architecture/a"),
            _page("https://example.com/camel-k/next/architecture/b"),
        ]
        result = classify_pages(pages)
        sections = {section for section, _ in result.values()}
        assert "Index.html" not in sections

    def test_optional_flag_for_blog_cluster(self):
        # When the rule-based classifier matches "blog", the optional flag
        # is propagated.
        result = classify_pages([
            _page("https://example.com/blog/post-1"),
            _page("https://example.com/blog/post-2"),
        ])
        assert result["https://example.com/blog/post-1"] == ("Blog", True)

    def test_custom_rules_apply(self):
        rules = {"learn": "Documentation"}
        result = classify_pages(
            [_page("https://example.com/learn/intro")],
            custom_rules=rules,
        )
        assert result["https://example.com/learn/intro"] == ("Documentation", False)
