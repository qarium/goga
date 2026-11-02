# tests/config/tool/test_loader.py — contract and logic tests for load_tool_config

from __future__ import annotations

import inspect
import typing
from pathlib import Path

import goga.config.tool as tool_module
import pytest
import yaml
from goga.config.tool import load_tool_config
from goga.config.tool import loader as tool_loader
from goga.config.yaml import parse_env_yaml

# --- Helpers ---


def _write_tool_file(root: Path, tool: str, filename: str, content: str) -> Path:
    """Write one tool config file under ``root/.goga/tools/<tool>/``."""
    tool_dir = root / ".goga" / "tools" / tool
    tool_dir.mkdir(parents=True, exist_ok=True)
    path = tool_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


# --- Contract tests ---


class TestLoadToolConfigContract:
    def test_importable_from_the_cell_facade(self) -> None:
        """load_tool_config is importable from goga.config.tool and in __all__."""
        assert callable(load_tool_config)
        assert tool_module.load_tool_config is load_tool_config
        assert "load_tool_config" in tool_module.__all__

    def test_declared_signature(self) -> None:
        """The declared signature (tool, filename, root=None) -> object | None."""
        parameters = inspect.signature(load_tool_config).parameters
        assert list(parameters) == ["tool", "filename", "root"]
        assert all(parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in parameters.values())
        assert parameters["root"].default is None
        assert typing.get_type_hints(load_tool_config) == {
            "tool": str,
            "filename": str,
            "root": Path | None,
            "return": object | None,
        }


class TestLoadToolConfigEnvParseContract:
    def test_tool_loader_parses_through_the_yaml_cell(self):
        """The loader's parse step routes through parse_env_yaml of goga/config/yaml."""
        assert tool_loader.parse_env_yaml is parse_env_yaml

    def test_tool_loader_carries_no_code_level_yaml_import(self):
        """The yaml module is no longer bound in the loader (docstrings keep the exception names)."""
        assert not hasattr(tool_loader, "yaml")

    def test_tool_loader_signature_unchanged(self):
        """load_tool_config still declares (tool, filename, root=None) -> object | None."""
        parameters = inspect.signature(load_tool_config).parameters
        assert list(parameters) == ["tool", "filename", "root"]
        assert parameters["root"].default is None


# --- Logic tests ---


class TestLoadToolConfigLogic:
    def test_load_tool_config_returns_raw_mapping(self, tmp_path: Path) -> None:
        """A present config file returns the raw parsed mapping as-is."""
        _write_tool_file(tmp_path, "coverage", "config.yml", "threshold: 10\nname: cov\n")

        result = load_tool_config("coverage", "config.yml", root=tmp_path)

        assert result == {"threshold": 10, "name": "cov"}
        assert isinstance(result, dict)

    @pytest.mark.parametrize(
        ("filename", "content", "expected"),
        [
            ("list.yml", "- a\n- b\n", ["a", "b"]),
            ("str.yml", "just a name\n", "just a name"),
            ("empty.yml", "", None),
        ],
    )
    def test_load_tool_config_raw_value_kinds(
        self, tmp_path: Path, filename: str, content: str, expected: object
    ) -> None:
        """The raw parse passes every YAML value kind through as-is."""
        _write_tool_file(tmp_path, "coverage", filename, content)

        assert load_tool_config("coverage", filename, root=tmp_path) == expected

    def test_load_tool_config_absent_file_returns_none(self, tmp_path: Path) -> None:
        """An absent file is the normal state — None, never an error."""
        (tmp_path / ".goga").mkdir()

        result = load_tool_config("coverage", "config.yml", root=tmp_path)

        assert result is None

    @pytest.mark.parametrize(
        "filename",
        ["", ".", "..", "a/b", "a\\b", "config.yml/../../x"],
    )
    def test_load_tool_config_rejects_non_flat_names(self, tmp_path: Path, filename: str) -> None:
        """A non-flat name is a clean ValueError before any filesystem access."""
        missing_root = tmp_path / "nowhere"  # no .goga tree exists under it

        with pytest.raises(ValueError, match="flat segment") as exc_info:
            load_tool_config("coverage", filename, root=missing_root)

        # The contract message embeds the name through {!r}, so the escaped
        # repr form (e.g. 'a\\b') is what appears in the rendered message.
        assert repr(filename) in str(exc_info.value)

    def test_load_tool_config_rereads_no_cache(self, tmp_path: Path) -> None:
        """Every call re-reads — a rewritten file is seen on the next call."""
        path = _write_tool_file(tmp_path, "coverage", "config.yml", "k: 1\n")

        first = load_tool_config("coverage", "config.yml", root=tmp_path)
        path.write_text("k: 2\n", encoding="utf-8")
        second = load_tool_config("coverage", "config.yml", root=tmp_path)

        assert first == {"k": 1}
        assert second == {"k": 2}

    def test_load_tool_config_root_defaults_to_cwd(self, tmp_path: Path, monkeypatch) -> None:
        """An omitted root anchors at Path('.') exactly as load_project_config does."""
        _write_tool_file(tmp_path, "coverage", "config.yml", "threshold: 10\n")
        monkeypatch.chdir(tmp_path)

        result = load_tool_config("coverage", "config.yml")

        assert result == {"threshold": 10}

    def test_load_tool_config_tool_identity_never_validated(self, tmp_path: Path) -> None:
        """The tool name is a platform identity used verbatim in the path."""
        _write_tool_file(tmp_path, "scoped/coverage", "config.yml", "k: 1\n")

        result = load_tool_config("scoped/coverage", "config.yml", root=tmp_path)

        assert result == {"k": 1}

    def test_load_tool_config_malformed_yaml_propagates_raw(self, tmp_path: Path) -> None:
        """A present file that fails to parse propagates the raw ``yaml.YAMLError``.

        Interpreting is the consuming tool's job — the loader never folds a
        parse failure into ``None``, which would make a broken config
        indistinguishable from the normal absent state.
        """
        _write_tool_file(tmp_path, "coverage", "config.yml", "key: [unclosed\n")

        with pytest.raises(yaml.YAMLError):
            load_tool_config("coverage", "config.yml", root=tmp_path)

    def test_load_tool_config_unreadable_file_propagates_oserror_raw(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A present file that cannot be read propagates the raw ``OSError``.

        A permission failure must surface as itself — never swallowed into
        ``None`` (the absent-file answer) nor rewrapped. The read is broken
        through the ``Path.read_text`` seam so the scenario holds under any
        filesystem permission semantics, root included.
        """
        _write_tool_file(tmp_path, "coverage", "config.yml", "k: 1\n")

        def unreadable(self: Path, **kwargs: object) -> str:
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "read_text", unreadable)

        with pytest.raises(PermissionError, match="Permission denied"):
            load_tool_config("coverage", "config.yml", root=tmp_path)

    def test_load_tool_config_non_utf8_file_propagates_decoding_raw(self, tmp_path: Path) -> None:
        """A file outside UTF-8 propagates the raw ``UnicodeDecodeError``.

        The read is strict — never a silent fallback decode that would hand
        the tool mojibake as if it were the committed content.
        """
        tool_dir = tmp_path / ".goga" / "tools" / "coverage"
        tool_dir.mkdir(parents=True)
        (tool_dir / "config.yml").write_bytes(b"\xff\xfebroken: \xa0")

        with pytest.raises(UnicodeDecodeError):
            load_tool_config("coverage", "config.yml", root=tmp_path)


class TestLoadToolConfigEnvReferences:
    def test_load_tool_config_resolves_env_reference(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A !ENV NAME scalar resolves at load time into the raw passthrough value (SC6).

        A regression back to ``yaml.safe_load`` fails on the unknown tag; the
        resolved string must arrive in the raw passthrough value.
        """
        monkeypatch.setenv("RUFF_THRESHOLD", "85")
        _write_tool_file(tmp_path, "ruff", "settings.yml", "threshold: !ENV RUFF_THRESHOLD\n")

        result = load_tool_config("ruff", "settings.yml", root=tmp_path)

        assert result == {"threshold": "85"}
        assert isinstance(result["threshold"], str)

    def test_load_tool_config_unset_env_reference_resolves_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unset !ENV variable resolves to the empty string — no field semantics apply here."""
        monkeypatch.delenv("RUFF_THRESHOLD", raising=False)
        _write_tool_file(tmp_path, "ruff", "settings.yml", "threshold: !ENV RUFF_THRESHOLD\n")

        result = load_tool_config("ruff", "settings.yml", root=tmp_path)

        assert result == {"threshold": ""}
