"""Logic tests of ``write_role_env_wrappers`` — closure generation rules and strictness."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from goga.build import role_env_wrappers as wrappers_module
from goga.build import write_role_env_wrappers
from goga.build.run_settings import PassSettings, ReviewPassSettings, RunSettings
from goga.config import AdditionalReviewConfig

ENGINE_KEYS = (
    "AFM_DIR",
    "AFM_DOCKER_FILE_ROOTS",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "GOGA_PROFILE",
    "GOGA_WORKFLOW",
    "GOGA_HOME_PROFILES",
    "GOGA_EXTRA_ENV",
)


def _make_settings(
    *,
    agents: dict[str, str | None] | None = None,
    envs: dict[str, dict[str, str]] | None = None,
) -> RunSettings:
    """Baseline run plan with per-role agents and env layers the scenario tunes.

    Args:
        agents: Per-role agent overrides keyed by role name; a role absent
            from the mapping keeps its baseline agent.
        envs: Per-role env layers keyed by role name; a role absent from the
            mapping gets an empty layer.

    Returns:
        The assembled run plan.
    """
    resolved_agents = {"tasks": "claude", "review": "codex", "additional": "gemini"} | (agents or {})
    resolved_envs = envs or {}

    return RunSettings(
        skip=False,
        tasks=PassSettings(agent=resolved_agents["tasks"], env=resolved_envs.get("tasks", {})),
        review=ReviewPassSettings(
            agent=resolved_agents["review"],
            env=resolved_envs.get("review", {}),
            strategy="medium",
            additional=AdditionalReviewConfig(
                agent=resolved_agents["additional"],
                patience=None,
                max_iterations=None,
                env=resolved_envs.get("additional", {}),
            ),
        ),
    )


class TestWriteRoleEnvWrappers:
    def test_generates_independent_closures(self, wrapper_base: Path) -> None:
        settings = _make_settings(envs={"tasks": {"T": "role"}, "review": {"R": "1"}, "additional": {"A": "x"}})

        paths = write_role_env_wrappers(settings, {"T": "CLI", "GOGA_PROFILE": "evil"})

        assert set(paths) == {"tasks", "review", "additional"}

        tasks_text = paths["tasks"].read_text()
        assert tasks_text.startswith("#!/bin/sh\n")
        assert "export T=CLI" in tasks_text
        assert "role" not in tasks_text
        assert tasks_text.endswith('exec /home/goga/bin/claude-as-claude.sh "$@"\n')

        review_text = paths["review"].read_text()
        assert "export R=1" in review_text
        assert "role" not in review_text
        assert review_text.endswith('exec /home/goga/bin/codex-as-claude.sh "$@"\n')

        additional_text = paths["additional"].read_text()
        assert "export A=x" in additional_text
        assert "R=1" not in additional_text
        assert "role" not in additional_text
        assert additional_text.endswith('exec /home/goga/bin/gemini-as-claude.sh "$@"\n')

        for path in paths.values():
            assert path.stat().st_mode & 0o111
            assert "GOGA_PROFILE" not in path.read_text()

    def test_cli_entries_apply_to_every_role_with_quoted_values(self, wrapper_base: Path) -> None:
        settings = _make_settings(envs={"tasks": {"T": "role"}, "review": {"R": "1"}, "additional": {"A": "x"}})

        paths = write_role_env_wrappers(settings, {"T": "CLI", "K": "a b"})

        for path in paths.values():
            text = path.read_text()

            assert "export T=CLI" in text
            assert "export K='a b'" in text

    @pytest.mark.parametrize("engine_key", ENGINE_KEYS)
    def test_engine_keys_dropped_silently_from_every_source(self, wrapper_base: Path, engine_key: str) -> None:
        settings = _make_settings(
            envs={"tasks": {engine_key: "tasks"}, "review": {engine_key: "review"}, "additional": {engine_key: "add"}},
        )

        paths = write_role_env_wrappers(settings, {engine_key: "cli"})

        for path in paths.values():
            assert engine_key not in path.read_text()

    def test_rejects_illegal_env_key_writing_nothing(self, wrapper_base: Path) -> None:
        settings = _make_settings(envs={"tasks": {"BAD=KEY": "1"}})

        with pytest.raises(ValueError, match="invalid environment variable name in the tasks role layer") as excinfo:
            write_role_env_wrappers(settings, {})

        assert "BAD=KEY" in str(excinfo.value)
        assert not list(wrapper_base.glob("*.sh"))

    def test_illegal_key_in_later_role_still_writes_nothing(self, wrapper_base: Path) -> None:
        """Validation of every role's layer precedes the first write — the
        additional role's violation leaves no tasks or review wrapper behind."""
        settings = _make_settings(envs={"tasks": {"T": "1"}, "additional": {"9BAD": "1"}})

        with pytest.raises(ValueError, match="invalid environment variable name in the additional role layer"):
            write_role_env_wrappers(settings, {})

        assert not list(wrapper_base.glob("*.sh"))

    @pytest.mark.parametrize(
        ("role", "agent"),
        [
            ("tasks", None),
            ("review", None),
            ("additional", None),
        ],
    )
    def test_missing_agent_names_role_writing_nothing(self, wrapper_base: Path, role: str, agent: None) -> None:
        settings = _make_settings(agents={role: agent})

        with pytest.raises(ValueError, match=f"no agent resolved for the {role} role"):
            write_role_env_wrappers(settings, {})

        assert not list(wrapper_base.glob("*.sh"))

    def test_idempotent_overwrites(self, wrapper_base: Path) -> None:
        settings = _make_settings(envs={"tasks": {"T": "1"}, "review": {"R": "2"}, "additional": {"A": "3"}})

        first = write_role_env_wrappers(settings, {})
        first_texts = {role: path.read_text() for role, path in first.items()}

        second = write_role_env_wrappers(settings, {})

        assert second == first
        assert {role: path.read_text() for role, path in second.items()} == first_texts
        assert len(list(wrapper_base.glob("*.sh"))) == 3

    def test_returns_paths_inside_the_base(self, wrapper_base: Path) -> None:
        paths = write_role_env_wrappers(_make_settings(), {})

        assert paths["tasks"] == wrapper_base / "tasks.sh"
        assert paths["review"] == wrapper_base / "review.sh"
        assert paths["additional"] == wrapper_base / "additional.sh"

    def test_run_directory_is_pid_keyed_under_the_base(self, wrapper_base: Path) -> None:
        """Each build process owns its own run directory — concurrent builds
        in one container never share or clobber each other's closures."""
        import os

        write_role_env_wrappers(_make_settings(), {})

        assert wrapper_base == wrappers_module._WRAPPER_BASE / f"run-{os.getpid()}"

    def test_closures_and_run_directory_owner_only(self, wrapper_base: Path) -> None:
        """The env layers never sit in a world-readable file: the run
        directory and every closure carry owner-only permissions (0o700)."""
        import stat

        paths = write_role_env_wrappers(_make_settings(envs={"tasks": {"SECRET": "tok"}}), {})

        run_mode = stat.S_IMODE(wrapper_base.stat().st_mode)
        assert run_mode == 0o700

        for path in paths.values():
            assert stat.S_IMODE(path.stat().st_mode) == 0o700
            # Owner-only still means executable by the owner — ralphex execs it.
            assert path.stat().st_mode & 0o100

    def test_env_values_never_printed(self, wrapper_base: Path, capsys) -> None:
        settings = _make_settings(envs={"tasks": {"SECRET_TOKEN": "sekret-value"}})

        write_role_env_wrappers(settings, {})

        captured = capsys.readouterr()

        assert captured.out == ""
        assert captured.err == ""

    def test_module_reads_no_environment_and_writes_nowhere_under_workspace(self) -> None:
        source = inspect.getsource(wrappers_module)

        assert "os.environ" not in source
        assert not str(wrappers_module._WRAPPER_BASE).startswith("/workspace")
