import pytest


class TestSlugValidation:
    @pytest.fixture
    def pattern(self):
        from main import SLUG_PATTERN

        return SLUG_PATTERN

    @pytest.mark.parametrize("slug", ["underskoterskor-inom-vard", "elektriker", "a-1-b"])
    def test_valid_slugs(self, pattern, slug):
        assert pattern.match(slug)

    @pytest.mark.parametrize("slug", ["../etc/passwd", "slug/path", "slug@host", "Uppercase", ""])
    def test_rejects_dangerous_slugs(self, pattern, slug):
        assert not pattern.match(slug)


class TestHtmlToText:
    @pytest.fixture
    def convert(self):
        from main import _html_to_text

        return _html_to_text

    def test_strips_script_and_style_but_keeps_content(self, convert):
        html = "<style>.x{color:red}</style><script>alert(1)</script><p>Hello</p>"
        result = convert(html)
        assert "Hello" in result
        assert "alert" not in result
        assert "color:red" not in result
