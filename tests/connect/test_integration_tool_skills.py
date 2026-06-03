"""Integration tests for install-tool-packages: end-to-end scenarios covering
core + tool skills coexistence, cleanup, name conflicts, and CLI behavior."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.connect.connect import _install_tool_skills, connect

_install_mod = importlib.import_module("goga.connect.connect")


def _make_agents(agent: str = "claude") -> list[str]:
    return [agent]


def _create_agent_resources(target: Path) -> Path:
    source = target / "goga" / "agent"
    (source / "commands").mkdir(parents=True)
    (source / "commands" / "build.md").write_text("# build command")
    (source / "commands" / "install.md").write_text("# install command")
    (source / "skills" / "goga-cell").mkdir(parents=True)
    (source / "skills" / "goga-cell" / "SKILL.md").write_text("# cell skill")
    (source / "skills" / "other-skill").mkdir(parents=True)
    (source / "skills" / "other-skill" / "SKILL.md").write_text("# other")
    return source


def _create_tool_package(
    parent: Path,
    pkg_name: str,
    extra_skills: list[str] | None = None,
    has_entry_point: bool = True,
) -> Path:
    pkg_dir = parent / pkg_name
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    tool_name = pkg_name.removeprefix("goga_tool_")
    skills_dir = pkg_dir / "skills"
    skills_dir.mkdir()
    if has_entry_point:
        entry = skills_dir / tool_name
        entry.mkdir()
        (entry / "SKILL.md").write_text(f"# {tool_name}")
    for name in extra_skills or []:
        sdir = skills_dir / name
        sdir.mkdir()
        (sdir / "SKILL.md").write_text(f"# {name}")
    return pkg_dir


def _make_find_spec_side_effect(spec_map: dict[str, Path]):
    def find_spec(name: str):
        if name in spec_map:
            spec = mock.MagicMock()
            spec.origin = str(spec_map[name] / "__init__.py")
            return spec
        return None

    return find_spec


def _mock_urlopen_response(content: bytes = b"dsl content") -> mock.MagicMock:
    mock_response = mock.MagicMock()
    mock_response.read.return_value = content
    mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
    mock_response.__exit__ = mock.MagicMock(return_value=False)
    return mock_response


class TestFullInstallCycleWithToolPackages:
    """Test: full install cycle — core skills + tool skills installed correctly,
    _print_summary outputs total count."""

    def test_core_and_tool_skills_both_installed(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        mock_home.mkdir()

        pkg_dir = _create_tool_package(tmp_path / "pkgs", "goga_tool_debug")

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_debug": ["goga-tool-debug"]},
            ),
            mock.patch.object(
                _install_mod.importlib.util,
                "find_spec",
                side_effect=_make_find_spec_side_effect({"goga_tool_debug": pkg_dir}),
            ),
        ):
            result = connect(agents=["claude"])

        assert result == 0
        target = mock_home / ".claude"
        # Core skills installed
        assert (target / "skills" / "goga-cell" / "SKILL.md").is_file()
        assert (target / "skills" / "other-skill" / "SKILL.md").is_file()
        # Tool skills installed
        assert (target / "skills" / "goga-tool-debug" / "SKILL.md").is_file()

    def test_print_summary_includes_tool_skills_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        mock_home.mkdir()

        pkg_dir = _create_tool_package(tmp_path / "pkgs", "goga_tool_debug")

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_debug": ["goga-tool-debug"]},
            ),
            mock.patch.object(
                _install_mod.importlib.util,
                "find_spec",
                side_effect=_make_find_spec_side_effect({"goga_tool_debug": pkg_dir}),
            ),
        ):
            result = connect(agents=["claude"])

        assert result == 0
        captured = capsys.readouterr()
        # 2 core skills (goga-cell, other-skill) + 1 tool skill = 3 total
        assert "Installed 3 skills" in captured.err
        assert "goga-cell" in captured.err
        assert "goga-tool-debug" in captured.err


class TestCleanupObsoleteToolSkills:
    """Test: cleanup removes obsolete goga-tool-* during reinstall,
    but preserves goga-tool-* from current packages."""

    def test_cleanup_removes_obsolete_but_keeps_current(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        mock_home.mkdir()

        # Pre-existing obsolete tool skill
        (mock_home / ".claude" / "skills" / "goga-tool-obsolete").mkdir(parents=True)
        (mock_home / ".claude" / "skills" / "goga-tool-obsolete" / "SKILL.md").write_text("# obsolete")

        # Current tool package provides debug skill
        pkg_dir = _create_tool_package(tmp_path / "pkgs", "goga_tool_debug")

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_debug": ["goga-tool-debug"]},
            ),
            mock.patch.object(
                _install_mod.importlib.util,
                "find_spec",
                side_effect=_make_find_spec_side_effect({"goga_tool_debug": pkg_dir}),
            ),
        ):
            result = connect(agents=["claude"])

        assert result == 0
        skills_dir = mock_home / ".claude" / "skills"
        # Obsolete removed by cleanup (runs before tool skill install)
        assert not (skills_dir / "goga-tool-obsolete").exists()
        # Current tool skill installed
        assert (skills_dir / "goga-tool-debug" / "SKILL.md").is_file()
        # Core skills still present
        assert (skills_dir / "goga-cell" / "SKILL.md").is_file()


class TestTwoPackagesSameSkillName:
    """Test: two packages with same skill name — first wins, stderr has warning."""

    def test_first_package_wins_on_name_conflict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Package 1: goga_tool_debug with skill "debug"
        pkg1 = tmp_path / "goga_tool_debug"
        pkg1.mkdir(parents=True)
        (pkg1 / "__init__.py").write_text("")
        (pkg1 / "skills" / "debug").mkdir(parents=True)
        (pkg1 / "skills" / "debug" / "SKILL.md").write_text("# debug from pkg1")

        # Package 2: goga_tool_analyze with skill "analyze" AND "debug"
        pkg2 = tmp_path / "goga_tool_analyze"
        pkg2.mkdir(parents=True)
        (pkg2 / "__init__.py").write_text("")
        (pkg2 / "skills" / "analyze").mkdir(parents=True)
        (pkg2 / "skills" / "analyze" / "SKILL.md").write_text("# analyze from pkg2")
        (pkg2 / "skills" / "debug").mkdir(parents=True)
        (pkg2 / "skills" / "debug" / "SKILL.md").write_text("# debug from pkg2")

        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        with (
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={
                    "goga_tool_debug": ["goga-tool-debug"],
                    "goga_tool_analyze": ["goga-tool-analyze"],
                },
            ),
            mock.patch.object(
                _install_mod.importlib.util,
                "find_spec",
                side_effect=_make_find_spec_side_effect(
                    {"goga_tool_debug": pkg1, "goga_tool_analyze": pkg2}
                ),
            ),
        ):
            result = _install_tool_skills(target, False)

        # Both packages' unique skills are installed
        assert "goga-tool-debug" in result
        assert "goga-tool-analyze" in result
        # Alphabetically first package (goga_tool_analyze) installs first,
        # so its content wins for the conflicting skill name
        content = (target / "skills" / "goga-tool-debug" / "SKILL.md").read_text()
        assert "pkg2" in content
        # Warning about the conflict
        captured = capsys.readouterr()
        assert "already exists" in captured.err


class TestCLIForceOverwriteEndToEnd:
    """Test: CLI end-to-end — two packages with conflicting skill name.
    With --force-overwrite, the second package overwrites the first."""

    def test_cli_force_overwrite_replaces_tool_skills(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").write_text(
            "language: python\nbuild:\n  task_executor:\n    agent: claude\n"
        )
        monkeypatch.chdir(tmp_path)

        # Package 1: provides "debug" skill
        pkg1 = _create_tool_package(tmp_path / "pkgs", "goga_tool_debug")

        # Package 2: provides "analyze" and "debug" skills (conflict on "debug")
        pkg2 = tmp_path / "pkgs" / "goga_tool_analyze"
        pkg2.mkdir(parents=True)
        (pkg2 / "__init__.py").write_text("")
        (pkg2 / "skills" / "analyze").mkdir(parents=True)
        (pkg2 / "skills" / "analyze" / "SKILL.md").write_text("# analyze")
        (pkg2 / "skills" / "debug").mkdir(parents=True)
        (pkg2 / "skills" / "debug" / "SKILL.md").write_text("# debug from pkg2")

        skills_dir = tmp_path / "home" / ".claude" / "skills"

        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path / "home"),
            mock.patch("urllib.request.urlopen", return_value=_mock_urlopen_response()),
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={
                    "goga_tool_debug": ["goga-tool-debug"],
                    "goga_tool_analyze": ["goga-tool-analyze"],
                },
            ),
            mock.patch.object(
                _install_mod.importlib.util,
                "find_spec",
                side_effect=_make_find_spec_side_effect(
                    {"goga_tool_debug": pkg1, "goga_tool_analyze": pkg2}
                ),
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude", "--force-overwrite"])

        assert result.exit_code == 0
        # With force_overwrite: alphabetically first (goga_tool_analyze/pkg2) installs
        # goga-tool-debug first, then goga_tool_debug (pkg1) overwrites it
        content = (skills_dir / "goga-tool-debug" / "SKILL.md").read_text()
        assert content == "# debug"


class TestCLIWithoutForceOverwrite:
    """Test: CLI without --force-overwrite — when two packages provide the
    same skill name, the second package's skill is NOT installed."""

    def test_cli_no_force_preserves_existing_tool_skills(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").write_text(
            "language: python\nbuild:\n  task_executor:\n    agent: claude\n"
        )
        monkeypatch.chdir(tmp_path)

        # Package 1: provides "debug" skill
        pkg1 = _create_tool_package(tmp_path / "pkgs", "goga_tool_debug")

        # Package 2: provides "analyze" and "debug" skills (conflict on "debug")
        pkg2 = tmp_path / "pkgs" / "goga_tool_analyze"
        pkg2.mkdir(parents=True)
        (pkg2 / "__init__.py").write_text("")
        (pkg2 / "skills" / "analyze").mkdir(parents=True)
        (pkg2 / "skills" / "analyze" / "SKILL.md").write_text("# analyze")
        (pkg2 / "skills" / "debug").mkdir(parents=True)
        (pkg2 / "skills" / "debug" / "SKILL.md").write_text("# debug from pkg2")

        skills_dir = tmp_path / "home" / ".claude" / "skills"

        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path / "home"),
            mock.patch("urllib.request.urlopen", return_value=_mock_urlopen_response()),
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={
                    "goga_tool_debug": ["goga-tool-debug"],
                    "goga_tool_analyze": ["goga-tool-analyze"],
                },
            ),
            mock.patch.object(
                _install_mod.importlib.util,
                "find_spec",
                side_effect=_make_find_spec_side_effect(
                    {"goga_tool_debug": pkg1, "goga_tool_analyze": pkg2}
                ),
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])

        assert result.exit_code == 0
        # Alphabetically first (goga_tool_analyze/pkg2) installs goga-tool-debug first,
        # then goga_tool_debug (pkg1) is skipped (already exists, no force)
        content = (skills_dir / "goga-tool-debug" / "SKILL.md").read_text()
        assert "pkg2" in content
        # Both unique skills installed
        assert (skills_dir / "goga-tool-analyze" / "SKILL.md").is_file()
