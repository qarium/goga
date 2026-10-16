"""Logic tests for the ``load_home_profiles`` routine.

Covers behavior beyond the contract surface: the flat ``*.yml`` collection,
the missing-directory empty bundle, determinism, and the strict
malformed-file failure naming the path.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from goga.pipeline.workflow import load_home_profiles


class TestLoadHomeProfilesLogic:
    """Logic tests — bundle collection and strictness of ``load_home_profiles``."""

    def test_load_home_profiles_collects_bundle_and_missing_dir_is_empty(self, tmp_path: Path) -> None:
        """Positive: flat ``*.yml`` files collect by stem; nested dirs and non-yml are invisible.

        A nested ``deep.yml`` and a ``notes.txt`` are ignored; a missing
        directory resolves to an empty mapping.
        """
        home = tmp_path / "profiles"
        home.mkdir()
        (home / "mixa.yml").write_text("worker:\n  agent: codex\n")
        (home / "zeta.yml").write_text("a: 1\n")
        (home / "notes.txt").write_text("not a profile")
        (home / "nested").mkdir()
        (home / "nested" / "deep.yml").write_text("b: 2\n")

        assert load_home_profiles(home) == {
            "mixa": {"worker": {"agent": "codex"}},
            "zeta": {"a": 1},
        }
        assert load_home_profiles(tmp_path / "absent") == {}

    def test_load_home_profiles_non_json_value_is_strict_failure(self, tmp_path: Path) -> None:
        """An unquoted YAML date parses to a datetime value no JSON payload can
        carry — the loader rejects it with one clean error naming the file,
        before any docker activity (never a json TypeError traceback at the
        encoder mid-launch)."""
        home = tmp_path / "profiles"
        home.mkdir()
        (home / "mixa.yml").write_text("deadline: 2026-01-15\n")

        with pytest.raises(ValueError, match=re.escape("home profile carries a non-JSON value")) as exc_info:
            load_home_profiles(home)

        assert "mixa.yml" in str(exc_info.value)

    def test_load_home_profiles_deterministic_across_calls(self, tmp_path: Path) -> None:
        """Unchanged directory contents produce the identical mapping on every call."""
        home = tmp_path / "profiles"
        home.mkdir()
        (home / "zeta.yml").write_text("a: 1\n")
        (home / "alpha.yml").write_text("b: 2\n")

        first = load_home_profiles(home)
        second = load_home_profiles(home)

        assert first == second
        assert list(first) == ["alpha", "zeta"]

    def test_load_home_profiles_empty_directory_is_empty_bundle(self, tmp_path: Path) -> None:
        """An existing but empty directory resolves to the empty bundle."""
        home = tmp_path / "profiles"
        home.mkdir()

        assert load_home_profiles(home) == {}

    def test_load_home_profiles_yaml_extension_only(self, tmp_path: Path) -> None:
        """Only the ``*.yml`` extension collects — a ``.yaml`` sibling stays invisible."""
        home = tmp_path / "profiles"
        home.mkdir()
        (home / "mixa.yaml").write_text("a: 1\n")

        assert load_home_profiles(home) == {}

    def test_load_home_profiles_malformed_file_strict_names_path(self, tmp_path: Path) -> None:
        """Negative: invalid YAML and a non-mapping root each raise naming the file path."""
        home = tmp_path / "profiles"
        home.mkdir()
        broken = home / "broken.yml"
        broken.write_text(": : :\n")

        with pytest.raises(ValueError, match=f"invalid YAML in home profile: {re.escape(str(broken))}"):
            load_home_profiles(home)

        broken.write_text("- a\n")

        with pytest.raises(ValueError, match=f"home profile must be a mapping: {re.escape(str(broken))}"):
            load_home_profiles(home)

    def test_load_home_profiles_module_reads_no_environment(self) -> None:
        """The module is pure — its source never touches ``os.environ`` or ``getenv``."""
        import inspect

        source = Path(inspect.getsourcefile(load_home_profiles)).read_text()  # type: ignore[arg-type]

        assert "os.environ" not in source
        assert "getenv" not in source
