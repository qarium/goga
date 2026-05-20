from __future__ import annotations

import importlib
import urllib.error
from pathlib import Path
from unittest import mock

import pytest
from goga.config import BuildConfig, Config, TaskExecutor
from goga.install.install import (
    _cleanup_goga_skills,
    _download_dsl_spec,
    _get_source_dir,
    _install_commands,
    _install_skills,
    _print_summary,
    _resolve_target_dir,
    install,
)

_install_mod = importlib.import_module("goga.install.install")


def _make_config(agent: str = "claude") -> Config:
    task_executor = TaskExecutor(agent=agent, env={})
    build = BuildConfig(task_executor=task_executor)
    return Config(lang="python", build=build)


def _create_agent_resources(target: Path) -> Path:
    source = target / "goga" / "agent"
    (source / "commands").mkdir(parents=True)
    (source / "commands" / "build.md").write_text("# build command")
    (source / "commands" / "install.md").write_text("# install command")
    (source / "skills" / "goga-cell").mkdir(parents=True)
    (source / "skills" / "goga-cell" / "SKILL.md").write_text("# cell skill")
    (source / "skills" / "goga-cell" / "dsl.md").parent.mkdir(parents=True, exist_ok=True)
    (source / "skills" / "other-skill").mkdir(parents=True)
    (source / "skills" / "other-skill" / "SKILL.md").write_text("# other")
    return source


# --- Helper tests ---


class TestResolveTargetDir:
    def test_claude_maps_to_home_claude(self) -> None:
        result = _resolve_target_dir("claude")
        assert result == Path.home() / ".claude"

    def test_unsupported_agent_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported agent"):
            _resolve_target_dir("unknown_agent")


class TestGetSourceDir:
    def test_returns_path_to_agent_dir(self) -> None:
        source = _get_source_dir()
        assert source.name == "agent"
        assert "goga" in str(source)


class TestInstallCommands:
    def test_copies_commands_to_target(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        (source / "commands").mkdir(parents=True)
        (source / "commands" / "build.md").write_text("# build")
        (source / "commands" / "install.md").write_text("# install")

        target = tmp_path / "target"
        target.mkdir()

        result = _install_commands(source, target)
        assert result == ["build", "install"]
        assert (target / "commands" / "goga" / "build.md").exists()
        assert (target / "commands" / "goga" / "install.md").exists()

    def test_replaces_existing_commands(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        (source / "commands").mkdir(parents=True)
        (source / "commands" / "new.md").write_text("# new")

        target = tmp_path / "target"
        (target / "commands" / "goga" / "old.md").parent.mkdir(parents=True)
        (target / "commands" / "goga" / "old.md").write_text("# old")

        _install_commands(source, target)
        assert not (target / "commands" / "goga" / "old.md").exists()
        assert (target / "commands" / "goga" / "new.md").exists()


class TestInstallSkills:
    def test_copies_skill_dirs(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        (source / "skills" / "goga-cell").mkdir(parents=True)
        (source / "skills" / "goga-cell" / "SKILL.md").write_text("# cell")

        target = tmp_path / "target"
        target.mkdir()

        result = _install_skills(source, target)
        assert result == ["goga-cell"]
        assert (target / "skills" / "goga-cell" / "SKILL.md").exists()

    def test_skips_files_in_skills_dir(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        (source / "skills").mkdir(parents=True)
        (source / "skills" / "readme.txt").write_text("readme")

        target = tmp_path / "target"
        target.mkdir()

        result = _install_skills(source, target)
        assert result == []


class TestDownloadDslSpec:
    def test_downloads_and_writes(self, tmp_path: Path) -> None:
        dsl_dir = tmp_path / "skills" / "goga-cell"
        dsl_dir.mkdir(parents=True)

        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"dsl content"
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch.object(_install_mod.urllib.request, "urlopen", return_value=mock_response):
            _download_dsl_spec(tmp_path)

        assert (dsl_dir / "dsl.md").read_bytes() == b"dsl content"

    def test_http_error_raises_os_error(self, tmp_path: Path) -> None:
        dsl_dir = tmp_path / "skills" / "goga-cell"
        dsl_dir.mkdir(parents=True)

        with mock.patch.object(
            _install_mod.urllib.request,
            "urlopen",
            side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None),
        ), pytest.raises(OSError, match="HTTP 404"):
            _download_dsl_spec(tmp_path)

    def test_url_error_raises_os_error(self, tmp_path: Path) -> None:
        dsl_dir = tmp_path / "skills" / "goga-cell"
        dsl_dir.mkdir(parents=True)

        with mock.patch.object(
            _install_mod.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ), pytest.raises(OSError, match="Failed to download DSL spec"):
            _download_dsl_spec(tmp_path)


class TestCleanupGogaSkills:
    def test_removes_goga_prefixed_dirs(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        (skills / "goga-cell").mkdir(parents=True)
        (skills / "goga-review").mkdir(parents=True)
        (skills / "other-skill").mkdir(parents=True)

        removed = _cleanup_goga_skills(tmp_path)
        assert removed == 2
        assert not (skills / "goga-cell").exists()
        assert not (skills / "goga-review").exists()
        assert (skills / "other-skill").exists()

    def test_returns_zero_when_no_skills_dir(self, tmp_path: Path) -> None:
        removed = _cleanup_goga_skills(tmp_path)
        assert removed == 0

    def test_returns_zero_when_no_goga_skills(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        (skills / "other").mkdir(parents=True)
        removed = _cleanup_goga_skills(tmp_path)
        assert removed == 0


class TestPrintSummary:
    def test_prints_to_stderr(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _print_summary(["build", "install"], ["goga-cell"], tmp_path)
        captured = capsys.readouterr()
        assert "Installed goga commands" in captured.err
        assert "Installed 2 commands: build, install" in captured.err
        assert "Installed goga skills" in captured.err
        assert "Installed 1 skills: goga-cell" in captured.err


# --- Main function tests ---


class TestInstall:
    def test_default_agent_from_config(self, tmp_path: Path) -> None:
        config = _make_config(agent="claude")
        mock_source = tmp_path / "source"
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"

        mock_home = tmp_path / "home"
        mock_home.mkdir()

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result = install(agent=None, config=config)

        assert result == 0
        target = mock_home / ".claude"
        assert (target / "commands" / "goga").is_dir()
        assert (target / "skills" / "goga-cell").is_dir()

    def test_explicit_claude_agent(self, tmp_path: Path) -> None:
        config = _make_config(agent="other")
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"

        mock_home = tmp_path / "home"
        mock_home.mkdir()

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result = install(agent="claude", config=config)

        assert result == 0

    def test_unsupported_agent_returns_1(self) -> None:
        config = _make_config(agent="unknown")
        result = install(agent="unknown", config=config)
        assert result == 1

    def test_source_missing_returns_1(self, tmp_path: Path) -> None:
        config = _make_config()
        mock_source = tmp_path / "nonexistent"

        with mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source):
            result = install(agent="claude", config=config)

        assert result == 1

    def test_download_failure_returns_1(self, tmp_path: Path) -> None:
        config = _make_config()
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        mock_home.mkdir()

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec", side_effect=OSError("download failed")),
        ):
            result = install(agent="claude", config=config)

        assert result == 1

    def test_full_install_cycle(self, tmp_path: Path) -> None:
        config = _make_config()
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        mock_home.mkdir()

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result = install(agent="claude", config=config)

        assert result == 0
        target = mock_home / ".claude"
        assert (target / "commands" / "goga" / "build.md").exists()
        assert (target / "commands" / "goga" / "install.md").exists()
        assert (target / "skills" / "goga-cell").is_dir()
        assert (target / "skills" / "other-skill").is_dir()

    def test_idempotent_double_install(self, tmp_path: Path) -> None:
        config = _make_config()
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        mock_home.mkdir()

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result1 = install(agent="claude", config=config)
            result2 = install(agent="claude", config=config)

        assert result1 == 0
        assert result2 == 0

    def test_preserves_other_skills(self, tmp_path: Path) -> None:
        config = _make_config()
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        (mock_home / ".claude" / "skills" / "user-skill").mkdir(parents=True)
        (mock_home / ".claude" / "skills" / "user-skill" / "SKILL.md").write_text("# user")

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result = install(agent="claude", config=config)

        assert result == 0
        assert (mock_home / ".claude" / "skills" / "user-skill" / "SKILL.md").exists()

    def test_cleanup_removes_old_goga_skills(self, tmp_path: Path) -> None:
        config = _make_config()
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        (mock_home / ".claude" / "skills" / "goga-obsolete").mkdir(parents=True)
        (mock_home / ".claude" / "skills" / "goga-obsolete" / "SKILL.md").write_text("# old")

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result = install(agent="claude", config=config)

        assert result == 0
        assert not (mock_home / ".claude" / "skills" / "goga-obsolete").exists()

    def test_error_output_to_stderr(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        result = install(agent="unknown", config=config)
        assert result == 1
        captured = capsys.readouterr()
        assert "unsupported agent" in captured.err

    def test_replaces_old_commands(self, tmp_path: Path) -> None:
        config = _make_config()
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        (mock_home / ".claude" / "commands" / "goga" / "old.md").parent.mkdir(parents=True)
        (mock_home / ".claude" / "commands" / "goga" / "old.md").write_text("# old")

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result = install(agent="claude", config=config)

        assert result == 0
        assert not (mock_home / ".claude" / "commands" / "goga" / "old.md").exists()
        assert (mock_home / ".claude" / "commands" / "goga" / "build.md").exists()

    def test_empty_skills_dir_in_source(self, tmp_path: Path) -> None:
        config = _make_config()
        source = tmp_path / "goga" / "agent"
        (source / "commands").mkdir(parents=True)
        (source / "commands" / "build.md").write_text("# build")
        (source / "skills").mkdir(parents=True)

        mock_home = tmp_path / "home2"
        mock_home.mkdir()

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=source),
            mock.patch.object(_install_mod.Path, "home", return_value=mock_home),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            result = install(agent="claude", config=config)

        assert result == 0
