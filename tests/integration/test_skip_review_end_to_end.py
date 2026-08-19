"""End-to-end integration tests for the review-phase control flow.

These stitch together the cross-entity path introduced by the
``skip-review-on-build`` change:

    host                                container
    goga/commands/build (click pair)    goga/build/__main__ (argparse pair)
      -> cli_flags -> docker run args     -> cli_options["skip_review"]
                                              -> build() (Algorithm 0-9)
    .goga/config.yml build.review_executor
      -> load_project_config (loader step 6.5)
        -> resolve_review_options -> validate_review_config
          -> sync_ralphex_defaults (role filtering) -> run_build_pass xN
            -> .ralphex/config + ralphex flags -> move_completed_plan

Three seams only hold end-to-end and are verified here: the tri-state flag
survives the host->container handoff undistorted (click pair -> forwarded args
-> argparse pair -> cli_options); a real ``build.review_executor`` YAML section
flows through the loader into two ralphex passes with role-filtered prompts and
a codex ``claude_command``; the two-pass x worktree guard fires before the
env-file write and the DockerRunner launch.

Mocks live only on the external boundaries per the project conventions: the
DockerRunner (docker binary), ``run_ralphex`` (ralphex binary), the vendored
defaults constants (maintainers' artifact), ``resolve_wrapper_path`` inside the
validator (existence check), and the host's docker/git subprocess helpers.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner
from goga.build.__main__ import main as container_main
from goga.build.build import build
from goga.commands import build as build_cmd
from goga.config import load_project_config

# goga.commands.build.build is shadowed by the function re-exported on the
# package __init__, so the real module is resolved via sys.modules and patched
# by attribute (per [[feedback_mock_patch_module_shadowing]]).
_build_cmd_mod = sys.modules["goga.commands.build.build"]

_ROLES = ("quality", "implementation", "testing", "simplification", "documentation")

# Synthetic stand-ins for the vendored ralphex v1.6.1 review prompts, carrying
# the literal counter fragments the role filter adapts (see .goga/usages/cooks/
# ralphex.md § Review prompt composition). The real assets are a maintainers'
# artifact; tests never depend on it.
_REVIEW_FIRST_TEMPLATE = (
    "# first review prompt\n"
    "launches 5 parallel reviewer agents\n"
    "Launch ALL 5 Review Agents\n"
    "All 5 agent invocations\n" + "".join(f"{{{{agent:{role}}}}}\n" for role in _ROLES) + "until ALL 5 agents\n"
)

_REVIEW_SECOND_TEMPLATE = (
    "# second review prompt\n"
    "uses 2 agents\n"
    "Both agent invocations\n"
    "{{agent:quality}}\n"
    "{{agent:implementation}}\n"
    "until both complete\n"
    "until BOTH agents\n"
    "emit them both in one response\n"
)


def _write_goga_yml(tmp_path: Path, review_executor: dict | None = None) -> None:
    """Materialize a .goga/config.yml with the optional build.review_executor section."""
    build_section: dict = {"task_executor": {"agent": "claude"}}
    if review_executor is not None:
        build_section["review_executor"] = review_executor

    data = {
        "language": "python",
        "image": "goga:latest",
        "build": build_section,
        "pipeline": {"agent": "claude"},
    }
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    (goga_dir / "config.yml").write_text(yaml.dump(data))


@contextmanager
def _mock_vendored_sources(tmp_path: Path):
    """Point the vendored ralphex defaults at synthetic tmp sources (external boundary)."""
    from goga.build import ralphex_runtime

    prompts_dir = tmp_path / "vendored-prompts"
    agents_dir = tmp_path / "vendored-agents"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "task.txt").write_text("# task prompt\n")
    (prompts_dir / "codex.txt").write_text("# codex review prompt\n")
    (prompts_dir / "review_first.txt").write_text(_REVIEW_FIRST_TEMPLATE)
    (prompts_dir / "review_second.txt").write_text(_REVIEW_SECOND_TEMPLATE)
    for role in _ROLES:
        (agents_dir / f"{role}.txt").write_text(f"# {role} agent definition\n")

    with (
        mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", prompts_dir),
        mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", agents_dir),
    ):
        yield


class TestTriStateSurvivesHostToContainer:
    """The tri-state flag reaches cli_options["skip_review"] undistorted.

    The host click pair (``--skip-review/--no-skip-review``, default None) is
    forwarded verbatim into the docker run args; the container argparse pair
    parses those same tokens back into one dest. Any lossy conversion on either
    side (e.g. the host resolving None against the config, or the container
    defaulting to False) would break the CLI > ProjectConfig > omit precedence
    that lives in ``resolve_review_options``.
    """

    @pytest.mark.parametrize(
        ("host_flag", "expected"),
        [
            ("--skip-review", True),
            ("--no-skip-review", False),
            (None, None),
        ],
    )
    def test_tri_state_survives_host_to_container(
        self, tmp_path: Path, monkeypatch, host_flag: str | None, expected: bool | None
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        runner = CliRunner()
        with (
            mock.patch.object(_build_cmd_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_cmd_mod, "_write_env_file", return_value=Path("/tmp/env")),
            mock.patch.object(_build_cmd_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            cli_args = ["plan.md"]
            if host_flag is not None:
                cli_args.append(host_flag)
            runner.invoke(build_cmd, cli_args)

        # The exact tokens handed to docker run form the in-container argv.
        container_args = mock_runner.return_value.run.call_args.args[0]
        forwarded = container_args[container_args.index("plan.md") + 1 :]
        assert ("--skip-review" in forwarded) is (expected is True)
        assert ("--no-skip-review" in forwarded) is (expected is False)

        # The container parses those same tokens with its real argparse wiring;
        # only the dispatch target is mocked to capture cli_options.
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["goga.build", "plan.md", *forwarded])
        with (
            mock.patch("goga.build.__main__.build", return_value=0) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
        ):
            container_main()

        assert mock_build.call_args[0][2]["skip_review"] is expected


class TestConfigYamlFlowsToRalphex:
    """A real build.review_executor YAML section drives the full container flow.

    Loader (step 6.5) -> resolve_review_options -> validate_review_config ->
    sync_ralphex_defaults (role filtering) -> two run_build_pass calls (tasks,
    then review) -> the final .ralphex/config carrying the review wrapper.
    """

    def test_config_yaml_review_executor_flows_to_ralphex_flags(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(
            tmp_path,
            review_executor={"skip": False, "agent": "codex", "roles": ["quality"]},
        )
        Path("plan.md").write_text("# plan\n")
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        config = load_project_config()

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", config, {"skip_manifest_check": True})

        assert result == 0
        assert mock_run.call_count == 2
        first_options = mock_run.call_args_list[0].args[1]
        second_options = mock_run.call_args_list[1].args[1]
        assert first_options["tasks_only"] is True
        assert "review" not in first_options
        assert second_options["review"] is True
        assert "tasks_only" not in second_options

        # Roles filter the review prompts of BOTH phases to the selected role.
        review_first = (tmp_path / ".ralphex" / "prompts" / "review_first.txt").read_text()
        assert "{{agent:quality}}" in review_first
        assert "{{agent:implementation}}" not in review_first
        review_second = (tmp_path / ".ralphex" / "prompts" / "review_second.txt").read_text()
        assert "{{agent:quality}}" in review_second
        assert "{{agent:implementation}}" not in review_second
        assert "uses 1 agents" in review_second

        # The final pass config carries the review executor wrapper: the
        # validator only checks existence against the mocked resolve, while the
        # orchestrator's own resolve (real, string-only) produces the
        # conventional /home/goga/bin/ path that lands in the file.
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert "move_plan_on_completion = false" in config_text


class TestGuardFiresBeforeDockerAssembly:
    """The two-pass x worktree guard fires before any docker-side side effect."""

    def test_guard_fires_before_docker_assembly(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path, review_executor={"agent": "codex"})

        runner = CliRunner()
        with (
            mock.patch.object(_build_cmd_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_cmd_mod, "_write_env_file") as mock_env,
            mock.patch.object(_build_cmd_mod, "DockerRunner") as mock_runner,
        ):
            result = runner.invoke(build_cmd, ["plan.md", "--worktree"])

        assert result.exit_code == 1
        assert "review_executor" in result.output
        assert "worktree" in result.output
        mock_env.assert_not_called()
        mock_runner.return_value.run.assert_not_called()
        assert not mock_runner.called


class TestTwoPassFailureKeepsPlan:
    """A failed pass keeps the plan in place for a resumable re-run."""

    def test_two_pass_failure_keeps_plan_for_resume(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path, review_executor={"agent": "codex"})
        Path("plan.md").write_text("# plan\n")
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        config = load_project_config()

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", side_effect=[1]) as mock_run,
        ):
            result = build("plan.md", config, {"skip_manifest_check": True})

        assert result == 1
        assert mock_run.call_count == 1
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()
