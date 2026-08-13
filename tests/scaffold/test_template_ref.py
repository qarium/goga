from __future__ import annotations

import inspect
from typing import get_type_hints


class TestContract:
    """Contract-level tests for parse_template_ref.

    The facade re-export (``from goga.scaffold import parse_template_ref``) is
    wired and verified in Task 5; these tests target the module path
    ``goga.scaffold.template_ref`` directly.
    """

    def test_parse_template_ref_importable_from_module(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        assert callable(parse_template_ref)

    def test_parse_template_ref_has_two_parameter_signature(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        signature = inspect.signature(parse_template_ref)
        params = list(signature.parameters)
        assert params == ["template_input", "ref_override"]

    def test_parse_template_ref_parameter_types(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        hints = get_type_hints(parse_template_ref)
        assert hints["template_input"] is str
        assert hints["ref_override"] == str | None

    def test_parse_template_ref_return_type(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        hints = get_type_hints(parse_template_ref)
        assert hints["return"] == tuple[str, str | None]

    def test_parse_template_ref_is_callable(self) -> None:
        # Imported lazily so the contract tests above fail clearly on import
        # before this one runs while the module is still absent.
        from goga.scaffold.template_ref import parse_template_ref

        result = parse_template_ref("https://example.com/tpl.git", None)
        assert isinstance(result, tuple)


class TestLogic:
    """Logic tests — verbatim scenarios from the design."""

    def test_parse_template_ref_returns_clean_url_and_fragment(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        result = parse_template_ref("https://example.com/tpl.git#v1.0", None)
        assert result == ("https://example.com/tpl.git", "v1.0")

    def test_parse_template_ref_ref_override_takes_precedence(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        result = parse_template_ref("https://example.com/tpl.git#v1.0", "main")
        assert result == ("https://example.com/tpl.git", "main")

    def test_parse_template_ref_no_fragment_no_override(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        result = parse_template_ref("https://example.com/tpl.git", None)
        assert result == ("https://example.com/tpl.git", None)

    def test_fragment_wins_when_override_absent(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        result = parse_template_ref("https://example.com/tpl.git#v1.0", None)
        assert result == ("https://example.com/tpl.git", "v1.0")

    def test_override_wins_when_no_fragment(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        result = parse_template_ref("https://example.com/tpl.git", "dev")
        assert result == ("https://example.com/tpl.git", "dev")

    def test_trailing_ref_only(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        # An empty fragment (trailing '#') normalizes to None — copier's
        # documented default (HEAD) — rather than the distinct value "".
        result = parse_template_ref("https://example.com/tpl.git#", None)
        assert result == ("https://example.com/tpl.git", None)

    def test_hash_in_path_segment_takes_last_as_fragment(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        result = parse_template_ref("https://example.com/a#b/tpl.git#v1.0", None)
        assert result == ("https://example.com/a#b/tpl.git", "v1.0")

    def test_empty_fragment_falls_through_to_none(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        # '' fragment + no override → None (not "").
        result = parse_template_ref("https://example.com/tpl.git#", None)
        assert result == ("https://example.com/tpl.git", None)

    def test_empty_override_falls_through_to_fragment(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        # '' override is treated as "not given" → the fragment wins.
        result = parse_template_ref("https://example.com/tpl.git#v1.0", "")
        assert result == ("https://example.com/tpl.git", "v1.0")

    def test_empty_override_and_no_fragment_yields_none(self) -> None:
        from goga.scaffold.template_ref import parse_template_ref

        # '' override + no fragment → None (not "").
        result = parse_template_ref("https://example.com/tpl.git", "")
        assert result == ("https://example.com/tpl.git", None)
