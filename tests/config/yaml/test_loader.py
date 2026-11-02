# tests/config/yaml/test_loader.py — contract and logic tests for parse_env_yaml

from __future__ import annotations

import inspect
import typing

import pytest
import yaml
import yaml.constructor
from goga.config.yaml import parse_env_yaml

# --- Contract tests ---


class TestParseEnvYamlContract:
    def test_importable_from_the_cell_facade(self) -> None:
        """parse_env_yaml is importable from goga.config.yaml and alone in __all__."""
        import goga.config.yaml as yaml_cell

        assert callable(parse_env_yaml)
        assert yaml_cell.parse_env_yaml is parse_env_yaml
        assert yaml_cell.__all__ == ["parse_env_yaml"]

    def test_declared_signature(self) -> None:
        """The declared signature (text: str) -> object."""
        parameters = inspect.signature(parse_env_yaml).parameters

        assert list(parameters) == ["text"]
        assert all(parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in parameters.values())
        assert parameters["text"].default is inspect.Parameter.empty
        assert typing.get_type_hints(parse_env_yaml) == {
            "text": str,
            "return": object,
        }


# --- Logic tests ---


class TestParseEnvYamlLogic:
    def test_parse_env_yaml_resolves_env_reference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A tagged scalar resolves from the environment into a plain string."""
        monkeypatch.setenv("PIPELINE_AGENT", "claude")

        result = parse_env_yaml("pipeline:\n  agent: !ENV PIPELINE_AGENT\n")

        assert result == {"pipeline": {"agent": "claude"}}
        assert isinstance(result["pipeline"]["agent"], str)

    def test_parse_env_yaml_unset_variable_resolves_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unset referenced variable resolves to "" — never None, never an error."""
        monkeypatch.delenv("GOGA_YAML_TEST_MISSING", raising=False)

        result = parse_env_yaml("a: !ENV GOGA_YAML_TEST_MISSING\n")

        assert result == {"a": ""}

    def test_parse_env_yaml_value_specials_verbatim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A resolved value containing separators and newlines arrives verbatim — no re-parsing."""
        monkeypatch.setenv("GOGA_YAML_TEST_VALUE", "x=y:z\nline2")

        result = parse_env_yaml("a: !ENV GOGA_YAML_TEST_VALUE\n")

        assert result == {"a": "x=y:z\nline2"}

    def test_parse_env_yaml_scalar_tag_in_mapping_key_position(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A tagged scalar in a mapping-KEY position resolves normally (no position special-case)."""
        monkeypatch.setenv("GOGA_YAML_TEST_KEY", "key1")

        result = parse_env_yaml("!ENV GOGA_YAML_TEST_KEY: value\n")

        assert result == {"key1": "value"}

    @pytest.mark.parametrize(
        ("text", "expected"),
        [("", None), ("just a scalar\n", "just a scalar"), ("- a\n- b\n", ["a", "b"])],
        ids=["empty-text-none", "scalar-document", "list-document"],
    )
    def test_parse_env_yaml_returns_parsed_value_as_is(self, text: str, expected: object) -> None:
        """The parsed value is returned as-is — no models, no normalization."""
        assert parse_env_yaml(text) == expected

    def test_parse_env_yaml_empty_argument_is_constructor_error(self) -> None:
        """A !ENV tag without an argument raises ConstructorError naming the position."""
        with pytest.raises(yaml.constructor.ConstructorError) as excinfo:
            parse_env_yaml("a: !ENV\n")

        assert "!ENV" in str(excinfo.value) or "line" in str(excinfo.value)

    @pytest.mark.parametrize(
        "text",
        ["a: !ENV [x, y]\n", "a: !ENV {k: v}\n"],
        ids=["tagged-sequence", "tagged-mapping"],
    )
    def test_parse_env_yaml_non_scalar_is_constructor_error(self, text: str) -> None:
        """A !ENV tag on a sequence/mapping node raises ConstructorError, not a raw TypeError."""
        with pytest.raises(yaml.constructor.ConstructorError) as excinfo:
            parse_env_yaml(text)

        assert "line" in str(excinfo.value)

    def test_parse_env_yaml_does_not_leak_tag_into_safe_load(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After an env-aware parse, plain safe_load still rejects the tag (subclass scoping)."""
        monkeypatch.setenv("GOGA_YAML_TEST_LEAK", "resolved")

        assert parse_env_yaml("a: !ENV GOGA_YAML_TEST_LEAK") == {"a": "resolved"}

        with pytest.raises(yaml.YAMLError, match="!ENV"):
            yaml.safe_load("a: !ENV GOGA_YAML_TEST_LEAK")

    def test_parse_env_yaml_error_caught_by_yaml_error_handler(self) -> None:
        """The constructor error is a yaml.YAMLError — the consumers' handlers keep working."""
        with pytest.raises(yaml.YAMLError):
            parse_env_yaml("a: !ENV\n")
