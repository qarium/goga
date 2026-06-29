from __future__ import annotations

import importlib
import inspect
import typing
from pathlib import Path
from unittest import mock

import pytest
import requests.exceptions
import yaml
from goga.connect.connect import (
    AGENTS_WITH_COMMANDS,
    _cleanup_goga_skills,
    _create_agent_symlinks,
    _download_dsl_spec,
    _get_source_dir,
    _install_central,
    _install_tool_skills,
    _print_summary,
    _resolve_target_dir,
    _write_connect_registry,
    connect,
)

_install_mod = importlib.import_module("goga.connect.connect")


def _make_config(agent: str = "claude") -> list[str]:
    return [agent]


def _create_agent_resources(target: Path) -> Path:
    """Create a minimal goga/assets/ source tree (goga-* prefixed skills)."""
    source = target / "goga" / "assets"
    (source / "commands").mkdir(parents=True)
    (source / "commands" / "build.md").write_text("# build command")
    (source / "commands" / "install.md").write_text("# install command")
    (source / "skills" / "goga-cell").mkdir(parents=True)
    (source / "skills" / "goga-cell" / "SKILL.md").write_text("# cell skill")
    (source / "skills" / "goga-review").mkdir(parents=True)
    (source / "skills" / "goga-review" / "SKILL.md").write_text("# review skill")
    return source


def _mock_requests_response(content: bytes = b"# DSL spec") -> mock.MagicMock:
    mock_response = mock.MagicMock()
    mock_response.content = content
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.MagicMock()
    return mock_response


def _connect_ctx(tmp_path: Path, source: Path, home: Path, agents: list[str], **kwargs):
    """Run connect() with the standard mocks (source, home, requests)."""
    with (
        mock.patch.object(_install_mod, "_get_source_dir", return_value=source),
        mock.patch.object(_install_mod.Path, "home", return_value=home),
        mock.patch.object(_install_mod.requests, "get", return_value=_mock_requests_response()),
    ):
        return connect(agents=agents, **kwargs)


# --- Helper tests ---


class TestResolveTargetDir:
    def test_claude_maps_to_home_claude(self) -> None:
        result = _resolve_target_dir("claude")
        assert result == Path.home() / ".claude"

    def test_codex_maps_to_home_codex(self) -> None:
        result = _resolve_target_dir("codex")
        assert result == Path.home() / ".codex"

    def test_cursor_maps_to_home_cursor(self) -> None:
        result = _resolve_target_dir("cursor")
        assert result == Path.home() / ".cursor"

    def test_unsupported_agent_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported agent"):
            _resolve_target_dir("unknown_agent")


class TestGetSourceDir:
    def test_returns_path_to_assets_dir(self) -> None:
        source = _get_source_dir()
        assert source.name == "assets"
        assert "goga" in str(source)


class TestDownloadDslSpec:
    def test_downloads_and_writes(self, tmp_path: Path) -> None:
        dsl_dir = tmp_path / "skills" / "goga-cell"
        dsl_dir.mkdir(parents=True)

        with mock.patch.object(_install_mod.requests, "get", return_value=_mock_requests_response(b"dsl content")):
            _download_dsl_spec(tmp_path)

        assert (dsl_dir / "dsl.md").read_bytes() == b"dsl content"

    def test_http_error_raises_os_error(self, tmp_path: Path) -> None:
        dsl_dir = tmp_path / "skills" / "goga-cell"
        dsl_dir.mkdir(parents=True)

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_resp.reason = "Not Found"
        http_error = requests.exceptions.HTTPError(response=mock_resp)

        with (
            mock.patch.object(_install_mod.requests, "get", side_effect=http_error),
            pytest.raises(OSError, match="HTTP 404"),
        ):
            _download_dsl_spec(tmp_path)

    def test_url_error_raises_os_error(self, tmp_path: Path) -> None:
        dsl_dir = tmp_path / "skills" / "goga-cell"
        dsl_dir.mkdir(parents=True)

        with (
            mock.patch.object(
                _install_mod.requests,
                "get",
                side_effect=requests.exceptions.ConnectionError("connection refused"),
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

    def test_unlinks_stale_symlinks(self, tmp_path: Path) -> None:
        """Stale/broken goga-* symlinks are removed, not just real dirs."""
        skills = tmp_path / "skills"
        skills.mkdir(parents=True)
        (skills / "goga-old").symlink_to("/nonexistent/target")
        (skills / "goga-cell").mkdir()
        (skills / "user-skill").mkdir()

        removed = _cleanup_goga_skills(tmp_path)

        assert removed == 2
        assert not (skills / "goga-old").is_symlink()
        assert not (skills / "goga-cell").exists()
        assert (skills / "user-skill").exists()

    def test_unlinks_broken_symlink_only(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        skills.mkdir(parents=True)
        broken = skills / "goga-stale"
        broken.symlink_to("/nonexistent/path")

        removed = _cleanup_goga_skills(tmp_path)

        assert removed == 1
        assert not broken.is_symlink()


class TestPrintSummary:
    def test_prints_to_stderr(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _print_summary(["build", "install"], ["goga-cell"], tmp_path)
        captured = capsys.readouterr()
        assert "Installed goga commands" in captured.err
        assert "Installed 2 commands: build, install" in captured.err
        assert "Installed goga skills" in captured.err
        assert "Installed 1 skills: goga-cell" in captured.err

    def test_no_commands_output_when_empty(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _print_summary([], ["goga-cell"], tmp_path)
        captured = capsys.readouterr()
        assert "Installed goga commands" not in captured.err
        assert "Installed goga skills" in captured.err
        assert "Installed 1 skills: goga-cell" in captured.err


# --- Contract tests for connect() signature (byte-identical) ---


class TestConnectSignatureContract:
    def test_connect_has_two_parameters(self) -> None:
        sig = inspect.signature(connect)
        params = list(sig.parameters.keys())
        assert params == ["agents", "force_overwrite"]

    def test_force_overwrite_default_is_false(self) -> None:
        sig = inspect.signature(connect)
        param = sig.parameters["force_overwrite"]
        assert param.default is False

    def test_agents_default_is_empty(self) -> None:
        sig = inspect.signature(connect)
        param = sig.parameters["agents"]
        assert param.default is inspect.Parameter.empty

    def test_param_and_return_annotations(self) -> None:
        hints = typing.get_type_hints(connect)
        assert hints["agents"] == list[str]
        assert hints["force_overwrite"] is bool
        assert hints["return"] is int

    def test_force_overwrite_accepts_false_and_true(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()
        for value in (False, True):
            assert _connect_ctx(tmp_path, source, home, ["claude"], force_overwrite=value) == 0


# --- Contract tests for the centralized + symlink model ---


class TestConnectCentralInstall:
    def test_connect_creates_central_goga_home(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        assert _connect_ctx(tmp_path, source, home, ["claude"]) == 0

        goga_home = home / ".goga"
        assert (goga_home / "skills").is_dir()
        assert (goga_home / "commands").is_dir()
        # central entries are REAL directories, not symlinks
        assert (goga_home / "skills" / "goga-cell").is_dir()
        assert not (goga_home / "skills" / "goga-cell").is_symlink()

    def test_connect_creates_agent_symlinks_not_copies(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        assert _connect_ctx(tmp_path, source, home, ["claude"]) == 0

        claude = home / ".claude"
        skill_link = claude / "skills" / "goga-cell"
        assert skill_link.is_symlink()
        assert skill_link.resolve() == (home / ".goga" / "skills" / "goga-cell")

        cmd_link = claude / "commands" / "goga"
        assert cmd_link.is_symlink()
        assert cmd_link.resolve() == (home / ".goga" / "commands")

    def test_non_claude_agent_has_no_commands_symlink(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        assert _connect_ctx(tmp_path, source, home, ["codex"]) == 0

        codex = home / ".codex"
        assert (codex / "skills" / "goga-cell").is_symlink()
        assert not (codex / "commands").exists()

    def test_connect_writes_registry_atomically(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        assert _connect_ctx(tmp_path, source, home, ["claude"], force_overwrite=False) == 0

        registry = yaml.safe_load((home / ".goga" / "connect.yml").read_text())
        assert registry == {"agents": {"claude": {"force_overwrite": False}}}
        # no partial-write temp file lingers in ~/.goga/
        leftovers = [p.name for p in (home / ".goga").iterdir() if p.suffix == ".tmp"]
        assert leftovers == []


# --- Logic tests for connect() behavior ---


class TestConnectLogicPositive:
    def test_connect_single_agent_creates_symlinks_and_registry(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        result = _connect_ctx(tmp_path, source, home, ["claude"])

        assert result == 0
        claude = home / ".claude"
        assert (claude / "skills" / "goga-cell").is_symlink()
        assert (claude / "skills" / "goga-cell" / "SKILL.md").is_file()
        assert (claude / "skills" / "goga-review" / "SKILL.md").is_file()
        assert (claude / "commands" / "goga" / "build.md").is_file()
        assert (claude / "skills" / "goga-cell" / "dsl.md").read_bytes() == b"# DSL spec"

    def test_connect_preserves_other_agents_in_registry(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()
        goga_home = home / ".goga"
        goga_home.mkdir(parents=True)
        pre_registry = {
            "agents": {
                "claude": {"force_overwrite": False},
                "codex": {"force_overwrite": True},
            }
        }
        (goga_home / "connect.yml").write_text(yaml.dump(pre_registry))

        assert _connect_ctx(tmp_path, source, home, ["cursor"]) == 0

        registry = yaml.safe_load((goga_home / "connect.yml").read_text())
        assert set(registry["agents"].keys()) == {"claude", "codex", "cursor"}
        # unlisted agents preserved verbatim
        assert registry["agents"]["claude"] == {"force_overwrite": False}
        assert registry["agents"]["codex"] == {"force_overwrite": True}
        # newly-listed agent recorded with the call's force_overwrite
        assert registry["agents"]["cursor"] == {"force_overwrite": False}


class TestConnectLogicNegative:
    def test_connect_empty_agents_returns_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = connect(agents=[])
        assert result == 1
        captured = capsys.readouterr()
        assert "at least one agent" in captured.err

    def test_connect_unknown_agent_returns_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = connect(agents=["unknown_agent"])
        assert result == 1
        captured = capsys.readouterr()
        assert "unsupported agent" in captured.err

    def test_connect_source_missing_returns_error(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home.mkdir()
        with mock.patch.object(_install_mod, "_get_source_dir", return_value=tmp_path / "nonexistent"):
            result = connect(agents=["claude"])
        assert result == 1

    def test_connect_download_failure_returns_error(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()
        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=source),
            mock.patch.object(_install_mod.Path, "home", return_value=home),
            mock.patch.object(
                _install_mod.requests,
                "get",
                side_effect=requests.exceptions.ConnectionError("boom"),
            ),
        ):
            result = connect(agents=["claude"])
        assert result == 1


class TestConnectLogicEdge:
    def test_connect_purges_stale_symlinks_and_real_dirs(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        skills = home / ".claude" / "skills"
        skills.mkdir(parents=True)
        # stale real dir + broken symlink, both goga-*
        (skills / "goga-cell").mkdir()
        (skills / "goga-old-skill").symlink_to("/nonexistent")

        result = _connect_ctx(tmp_path, source, home, ["claude"])

        assert result == 0
        assert not (skills / "goga-old-skill").is_symlink()
        # fresh symlink created in place of the purged real dir
        assert (skills / "goga-cell").is_symlink()
        assert (skills / "goga-cell" / "SKILL.md").is_file()

    def test_connect_propagates_install_flows_failure(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()
        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=source),
            mock.patch.object(_install_mod.Path, "home", return_value=home),
            mock.patch.object(_install_mod.requests, "get", return_value=_mock_requests_response()),
            mock.patch.object(_install_mod, "install_flows", return_value=1),
        ):
            result = connect(agents=["claude"])
        assert result == 1

    def test_connect_symlink_oserror_continues_other_agents(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()
        real_symlink_to = Path.symlink_to

        def flaky_symlink_to(self, target, *args, **kwargs):
            if ".claude" in str(self):
                raise OSError("simulated privilege error")
            return real_symlink_to(self, target, *args, **kwargs)

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=source),
            mock.patch.object(_install_mod.Path, "home", return_value=home),
            mock.patch.object(_install_mod.requests, "get", return_value=_mock_requests_response()),
            mock.patch.object(Path, "symlink_to", flaky_symlink_to),
        ):
            result = connect(agents=["claude", "codex"])

        # OSError on claude is non-fatal: connect still returns 0 and codex is processed.
        assert result == 0
        assert (home / ".codex" / "skills" / "goga-cell").is_symlink()

    def test_connect_idempotent_double_run(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        assert _connect_ctx(tmp_path, source, home, ["claude"]) == 0
        assert _connect_ctx(tmp_path, source, home, ["claude"]) == 0

        skill_link = home / ".claude" / "skills" / "goga-cell"
        assert skill_link.is_symlink()
        assert skill_link.resolve() == (home / ".goga" / "skills" / "goga-cell")


# --- Contract tests for force_overwrite parameter ---


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


# --- New helper contract tests ---


class TestNewHelperContract:
    def test_install_central_exists(self) -> None:
        assert callable(_install_central)

    def test_create_agent_symlinks_exists(self) -> None:
        assert callable(_create_agent_symlinks)

    def test_write_connect_registry_exists(self) -> None:
        assert callable(_write_connect_registry)


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

    def test_skill_exists_no_overwrite(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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


class TestAgentsWithCommands:
    def test_claude_in_agents_with_commands(self) -> None:
        assert "claude" in AGENTS_WITH_COMMANDS

    def test_codex_not_in_agents_with_commands(self) -> None:
        assert "codex" not in AGENTS_WITH_COMMANDS

    def test_cursor_not_in_agents_with_commands(self) -> None:
        assert "cursor" not in AGENTS_WITH_COMMANDS
