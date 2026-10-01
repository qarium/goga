"""End-to-end integration tests for the review-phase control flow.

These stitch together the cross-entity path of the two-part build model
(``add-hooks-to-build``):

    host                                container
    goga/commands/build (click pair)    goga/build/__main__ (argparse pair)
      -> cli_flags -> docker run args     -> cli_options["skip_review"]
                                              -> build() (Algorithm 0-11)
    .goga/config.yml build.review
      -> load_project_config (two-part loader)
        -> resolve_run_settings (tri-state skip: CLI > build.review.skip
          > False) -> validate_review_config
          -> sync_ralphex_defaults (role filtering) -> run_build_pass xN
            -> .ralphex/config + ralphex flags -> move_completed_plan

Three seams only hold end-to-end and are verified here: the tri-state flag
survives the host->container handoff undistorted (click pair -> forwarded args
-> argparse pair -> cli_options); a real ``build.review`` YAML section flows
through the loader into two ralphex passes with role-filtered prompts and a
codex ``claude_command``; and the skip form yields exactly one tasks pass.
(The ``build.agent`` value guard is covered by the ``goga/build`` unit suite —
it moved in-container, before the first ``.ralphex/`` state write.)

Mocks live only on the external boundaries per the project conventions: the
DockerRunner (docker binary), ``run_ralphex`` (ralphex binary), the vendored
defaults constants (maintainers' artifact), ``resolve_wrapper_path`` inside the
validator (existence check), and the host's docker/git subprocess helpers.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.build.__main__ import main as container_main
from goga.build.build import build
from goga.commands import build as build_cmd
from goga.config import load_project_config

# goga.commands.build.build is shadowed by the function re-exported on the
# package __init__, so the real module is resolved via sys.modules and patched
# by attribute (per [[feedback_mock_patch_module_shadowing]]).
_build_cmd_mod = sys.modules["goga.commands.build.build"]


class TestTriStateSurvivesHostToContainer:
    """The tri-state flag reaches cli_options["skip_review"] undistorted.

    The host click pair (``--skip-review/--no-skip-review``, default None) is
    forwarded verbatim into the docker run args; the container argparse pair
    parses those same tokens back into one dest. Any lossy conversion on either
    side (e.g. the host resolving None against the config, or the container
    defaulting to False) would break the CLI > ``build.review.skip`` > False
    precedence that lives in ``resolve_run_settings``.
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
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        host_flag: str | None,
        expected: bool | None,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest")

        runner = CliRunner()
        with (
            mock.patch.object(_build_cmd_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_cmd_mod, "_write_env_file", return_value=tmp_path / "env"),
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
    """A real build.review YAML section drives the full container flow.

    Two-part loader -> resolve_run_settings -> validate_review_config ->
    sync_ralphex_defaults (role filtering) -> two run_build_pass calls (tasks,
    then review) -> the final .ralphex/config carrying the review wrapper.
    """

    def test_config_yaml_review_flows_to_ralphex_flags(
        self, tmp_path: Path, monkeypatch, write_goga_config, mock_vendored_sources
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest", review={"skip": False, "agent": "codex", "roles": ["quality"]})
        Path("plan.md").write_text("# plan\n")
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        config = load_project_config()

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", config, {"skip_manifest_check": True})

        assert result == 0

        # The always-two-pass cycle of a non-skipped run.
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


class _SkipCase(NamedTuple):
    """One skip arm: the review section and the CLI options that carry the skip."""

    review_section: dict | None
    cli_options: dict


class TestSkipFormSingleTasksPass:
    """The skip form of the always-two-pass cycle: exactly one tasks pass.

    Both skip sources land in the same shape: the config-declared
    ``build.review.skip`` and the CLI tri-state override.
    """

    @pytest.mark.parametrize(
        "case",
        [
            _SkipCase(review_section={"skip": True}, cli_options={"skip_manifest_check": True}),
            _SkipCase(
                review_section={"skip": True, "agent": "codex"},
                cli_options={"skip_manifest_check": True},
            ),
            _SkipCase(
                review_section={"agent": "codex"},
                cli_options={"skip_manifest_check": True, "skip_review": True},
            ),
            _SkipCase(review_section=None, cli_options={"skip_manifest_check": True, "skip_review": True}),
        ],
    )
    def test_skip_yields_exactly_one_tasks_pass(
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        mock_vendored_sources,
        case: _SkipCase,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest", review=case.review_section)
        Path("plan.md").write_text("# plan\n")

        config = load_project_config()

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", config, case.cli_options)

        assert result == 0

        # Exactly one pass — tasks-only; the review pass never launches.
        assert mock_run.call_count == 1
        options = mock_run.call_args.args[1]
        assert options["tasks_only"] is True
        assert "review" not in options

        # The single successful pass relocates the plan.
        assert not (tmp_path / "plan.md").exists()
        assert (tmp_path / "completed" / "plan.md").read_text() == "# plan\n"


class TestTwoPassFailureKeepsPlan:
    """A failed pass keeps the plan in place for a resumable re-run."""

    def test_two_pass_failure_keeps_plan_for_resume(
        self, tmp_path: Path, monkeypatch, write_goga_config, mock_vendored_sources
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest", review={"agent": "codex"})
        Path("plan.md").write_text("# plan\n")
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        config = load_project_config()

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", side_effect=[1]) as mock_run,
        ):
            result = build("plan.md", config, {"skip_manifest_check": True})

        assert result == 1
        assert mock_run.call_count == 1
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

    def test_review_pass_failure_keeps_plan_for_resume(
        self, tmp_path: Path, monkeypatch, write_goga_config, mock_vendored_sources
    ) -> None:
        """A failed review pass after a successful tasks pass keeps the plan in place."""
        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest", review={"agent": "codex"})
        Path("plan.md").write_text("# plan\n")
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        config = load_project_config()

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", side_effect=[0, 1]) as mock_run,
        ):
            result = build("plan.md", config, {"skip_manifest_check": True})

        assert result == 1
        assert mock_run.call_count == 2
        review_options = mock_run.call_args_list[1].args[1]
        assert review_options["review"] is True
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()
