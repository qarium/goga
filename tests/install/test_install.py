from __future__ import annotations

import importlib
import inspect
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
    _install_tool_skills,
    _print_summary,
    _resolve_target_dir,
    install,
)

_install_mod = importlib.import_module("goga.install.install")


def _make_config(agent: str = "claude") -> Config:
    task_executor = TaskExecutor(agent=agent, env={})
    build = BuildConfig(task_executor=task_executor, image="goga:latest")
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

        with (
            mock.patch.object(
                _install_mod.urllib.request,
                "urlopen",
                side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None),
            ),
            pytest.raises(OSError, match="HTTP 404"),
        ):
            _download_dsl_spec(tmp_path)

    def test_url_error_raises_os_error(self, tmp_path: Path) -> None:
        dsl_dir = tmp_path / "skills" / "goga-cell"
        dsl_dir.mkdir(parents=True)

        with (
            mock.patch.object(
                _install_mod.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ),
            pytest.raises(OSError, match="Failed to download DSL spec"),
        ):
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


# --- Contract tests for force_overwrite parameter ---


class TestInstallSignatureContract:
    def test_install_has_three_parameters(self) -> None:
        sig = inspect.signature(install)
        params = list(sig.parameters.keys())
        assert params == ["agent", "config", "force_overwrite"]

    def test_force_overwrite_default_is_false(self) -> None:
        sig = inspect.signature(install)
        param = sig.parameters["force_overwrite"]
        assert param.default is False

    def test_force_overwrite_is_bool_type(self) -> None:
        hints = inspect.get_annotations(install, eval_str=True)
        assert hints["force_overwrite"] is bool

    def test_install_accepts_force_overwrite_false(self, tmp_path: Path) -> None:
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
            result = install(agent="claude", config=config, force_overwrite=False)

        assert result == 0

    def test_install_accepts_force_overwrite_true(self, tmp_path: Path) -> None:
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
            result = install(agent="claude", config=config, force_overwrite=True)

        assert result == 0


# --- Contract tests for _install_tool_skills ---


class TestInstallToolSkillsContract:
    def test_install_tool_skills_exists(self) -> None:
        assert hasattr(_install_mod, "_install_tool_skills")

    def test_install_tool_skills_is_callable(self) -> None:
        assert callable(_install_mod._install_tool_skills)

    def test_install_tool_skills_has_two_params(self) -> None:
        sig = inspect.signature(_install_tool_skills)
        params = list(sig.parameters.keys())
        assert params == ["target", "force_overwrite"]

    def test_install_tool_skills_param_types(self) -> None:
        hints = inspect.get_annotations(_install_tool_skills, eval_str=True)
        assert hints["target"] is Path
        assert hints["force_overwrite"] is bool

    def test_install_tool_skills_return_type(self) -> None:
        hints = inspect.get_annotations(_install_tool_skills, eval_str=True)
        assert hints["return"] == list[str]


# --- Helpers for _install_tool_skills tests ---


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


# --- Logical tests for _install_tool_skills ---


class TestInstallToolSkills:
    def test_discovers_and_installs_tool_skill(self, tmp_path: Path) -> None:
        pkg_dir = _create_tool_package(tmp_path, "goga_tool_debug")
        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        with (
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
            result = _install_tool_skills(target, False)

        assert "goga-tool-debug" in result
        assert (target / "skills" / "goga-tool-debug" / "SKILL.md").exists()

    def test_installs_multiple_tool_packages(self, tmp_path: Path) -> None:
        pkg1 = _create_tool_package(tmp_path, "goga_tool_debug")
        pkg2 = _create_tool_package(tmp_path, "goga_tool_analyze")
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

        assert "goga-tool-debug" in result
        assert "goga-tool-analyze" in result

    def test_force_overwrite_replaces_existing(self, tmp_path: Path) -> None:
        pkg_dir = _create_tool_package(tmp_path, "goga_tool_debug")
        target = tmp_path / "target"
        existing = target / "skills" / "goga-tool-debug"
        existing.mkdir(parents=True)
        (existing / "old.txt").write_text("old")

        with (
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
            result = _install_tool_skills(target, True)

        assert "goga-tool-debug" in result
        assert not (existing / "old.txt").exists()
        assert (existing / "SKILL.md").exists()

    def test_multiple_skills_in_one_package(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "goga_tool_debug"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("")
        skills_dir = pkg_dir / "skills"
        skills_dir.mkdir()

        (skills_dir / "debug").mkdir()
        (skills_dir / "debug" / "SKILL.md").write_text("# debug")
        (skills_dir / "analyze").mkdir()
        (skills_dir / "analyze" / "SKILL.md").write_text("# analyze")
        (skills_dir / "helpers.md").write_text("helpers")

        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        with (
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
            result = _install_tool_skills(target, False)

        assert sorted(result) == ["goga-tool-analyze", "goga-tool-debug"]
        assert (target / "skills" / "goga-tool-debug" / "SKILL.md").exists()
        assert (target / "skills" / "goga-tool-analyze" / "SKILL.md").exists()
        assert not (target / "skills" / "helpers.md").exists()

    def test_package_no_entry_point(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pkg_dir = _create_tool_package(
            tmp_path, "goga_tool_debug", has_entry_point=False
        )
        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        with (
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
            result = _install_tool_skills(target, False)

        assert result == []
        captured = capsys.readouterr()
        assert "missing skills/debug/SKILL.md" in captured.err

    def test_skill_exists_no_overwrite(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pkg_dir = _create_tool_package(tmp_path, "goga_tool_debug")
        target = tmp_path / "target"
        existing = target / "skills" / "goga-tool-debug"
        existing.mkdir(parents=True)
        (existing / "old.txt").write_text("old")

        with (
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
            result = _install_tool_skills(target, False)

        assert result == []
        assert (existing / "old.txt").exists()
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_no_tool_packages(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        with mock.patch.object(
            _install_mod.importlib.metadata,
            "packages_distributions",
            return_value={"requests": ["requests"]},
        ):
            result = _install_tool_skills(target, False)

        assert result == []

    def test_find_spec_returns_none(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        with (
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_debug": ["goga-tool-debug"]},
            ),
            mock.patch.object(
                _install_mod.importlib.util, "find_spec", return_value=None
            ),
        ):
            result = _install_tool_skills(target, False)

        assert result == []

    def test_preserves_core_skills(self, tmp_path: Path) -> None:
        pkg_dir = _create_tool_package(tmp_path, "goga_tool_debug")
        target = tmp_path / "target"
        (target / "skills" / "goga-cell").mkdir(parents=True)
        (target / "skills" / "goga-cell" / "SKILL.md").write_text("# cell")

        with (
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
            result = _install_tool_skills(target, False)

        assert "goga-tool-debug" in result
        assert (target / "skills" / "goga-cell" / "SKILL.md").exists()

    def test_cleanup_removes_old_tool_skills(self, tmp_path: Path) -> None:
        config = _make_config()
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "agent"
        mock_home = tmp_path / "home"
        (mock_home / ".claude" / "skills" / "goga-tool-obsolete").mkdir(parents=True)
        (mock_home / ".claude" / "skills" / "goga-tool-obsolete" / "SKILL.md").write_text("# old")

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
            result = install(agent="claude", config=config)

        assert result == 0
        assert not (mock_home / ".claude" / "skills" / "goga-tool-obsolete").exists()
        assert (mock_home / ".claude" / "skills" / "goga-tool-debug").is_dir()

    def test_two_packages_same_skill_name(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pkg1 = tmp_path / "goga_tool_debug"
        pkg1.mkdir(parents=True)
        (pkg1 / "__init__.py").write_text("")
        (pkg1 / "skills" / "debug").mkdir(parents=True)
        (pkg1 / "skills" / "debug" / "SKILL.md").write_text("# debug v1")

        pkg2 = tmp_path / "goga_tool_analyze"
        pkg2.mkdir(parents=True)
        (pkg2 / "__init__.py").write_text("")
        (pkg2 / "skills" / "analyze").mkdir(parents=True)
        (pkg2 / "skills" / "analyze" / "SKILL.md").write_text("# analyze v1")
        (pkg2 / "skills" / "debug").mkdir(parents=True)
        (pkg2 / "skills" / "debug" / "SKILL.md").write_text("# debug v2")

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

        assert "goga-tool-debug" in result
        assert "goga-tool-analyze" in result
        content = (target / "skills" / "goga-tool-debug" / "SKILL.md").read_text()
        assert "v2" in content
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_empty_packages_distributions(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        with mock.patch.object(
            _install_mod.importlib.metadata,
            "packages_distributions",
            return_value={},
        ):
            result = _install_tool_skills(target, False)

        assert result == []

    def test_find_spec_origin_is_none(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        (target / "skills").mkdir(parents=True)

        spec = mock.MagicMock()
        spec.origin = None

        with (
            mock.patch.object(
                _install_mod.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_debug": ["goga-tool-debug"]},
            ),
            mock.patch.object(
                _install_mod.importlib.util, "find_spec", return_value=spec
            ),
        ):
            result = _install_tool_skills(target, False)

        assert result == []