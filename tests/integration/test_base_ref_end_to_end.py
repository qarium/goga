"""End-to-end integration tests for the review-scoped ``base_ref`` option.

These stitch together the cross-cell path of the two-part build model
(``add-hooks-to-build``):

    host                                container
    goga/commands/build (click value    goga/build/__main__ (argparse value
      option --base-ref)                  option --base-ref)
      -> cli_flags -> docker run args     -> cli_options["base_ref"]
                                              -> resolve_run_settings step 6
    .goga/config.yml build.review.base_ref   (CLI > build.review.base_ref > omit)
      -> load_project_config (two-part loader)
        -> ReviewPassSettings.base_ref
          -> compose_pass_options("review") -> run_ralphex options key
            base_ref -> ralphex flag --base-ref

Three seams only hold end-to-end and are verified here: the value survives the
host->container handoff as the exact docker-run token pair and is parsed back
by the real in-container argparse wiring; an unset option forwards no token and
still lands as a present-but-None ``cli_options`` key (the tri-state that lets
the resolver defer to the config); and the resolved base reaches the ralphex
argv of the review pass only — never the tasks pass — under the full
CLI > ``build.review.base_ref`` > omit precedence.

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
from goga.ralphex.run_ralphex import _build_command

# goga.commands.build.build is shadowed by the function re-exported on the
# package __init__, so the real module is resolved via sys.modules and patched
# by attribute (per [[feedback_mock_patch_module_shadowing]]).
_build_cmd_mod = sys.modules["goga.commands.build.build"]


class TestBaseRefSurvivesHostToContainer:
    """The review diff base reaches cli_options["base_ref"] undistorted.

    The host click value option (``--base-ref``, default None) is forwarded as
    the exact token pair into the docker run args; the container argparse value
    option parses those same tokens back into one dest. Any lossy conversion on
    either side (the host resolving None against the config, or the token pair
    being dropped in ``_cli_flags_to_args``) would break the CLI >
    ``build.review.base_ref`` > omit precedence that lives in
    ``resolve_run_settings``.
    """

    def test_base_ref_survives_host_to_container(self, tmp_path: Path, monkeypatch, write_goga_config) -> None:
        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest")

        runner = CliRunner()

        with (
            mock.patch.object(_build_cmd_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_cmd_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(_build_cmd_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            runner.invoke(build_cmd, ["plan.md", "--base-ref", "origin/1.2.x"])

        # The exact tokens handed to docker run form the in-container argv; with
        # no other option set, --base-ref and its value are the whole tail.
        container_args = mock_runner.return_value.run.call_args.args[0]
        forwarded = container_args[container_args.index("plan.md") + 1 :]
        assert forwarded == ["--base-ref", "origin/1.2.x"]

        # The container parses those same tokens with its real argparse wiring;
        # only the dispatch target is mocked to capture cli_options.
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["goga.build", "plan.md", *forwarded])

        with (
            mock.patch("goga.build.__main__.build", return_value=0) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
        ):
            container_main()

        assert mock_build.call_args[0][2]["base_ref"] == "origin/1.2.x"

    def test_base_ref_unset_forwards_no_token(self, tmp_path: Path, monkeypatch, write_goga_config) -> None:
        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest")

        runner = CliRunner()

        with (
            mock.patch.object(_build_cmd_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_cmd_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(_build_cmd_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            runner.invoke(build_cmd, ["plan.md"])

        # An unset value option emits no token at all — the decision is left to
        # the container config, not baked in as an empty value.
        container_args = mock_runner.return_value.run.call_args.args[0]
        forwarded = container_args[container_args.index("plan.md") + 1 :]
        assert forwarded == []
        assert "--base-ref" not in container_args

        # The tri-state survives: the key is present in cli_options with value
        # None, so the resolver falls through to build.review.base_ref.
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["goga.build", "plan.md", *forwarded])

        with (
            mock.patch("goga.build.__main__.build", return_value=0) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
        ):
            container_main()

        cli_options = mock_build.call_args[0][2]
        assert "base_ref" in cli_options
        assert cli_options["base_ref"] is None


class _BaseRefCase(NamedTuple):
    """One precedence arm: the CLI base, the config base, and the resolved one."""

    cli_base_ref: str | None
    config_base_ref: str | None
    expected: str | None


class TestConfigBaseReachesRalphexFlag:
    """The resolved review base reaches the ralphex argv of the review pass only.

    Two-part loader -> ``resolve_run_settings`` step 6 (CLI >
    ``build.review.base_ref`` > omit) -> ``compose_pass_options("review")`` ->
    ``_build_command`` mapping the composed option keys to the ralphex flags.
    """

    @pytest.mark.parametrize(
        "case",
        [
            _BaseRefCase(cli_base_ref=None, config_base_ref="origin/1.2.x", expected="origin/1.2.x"),
            _BaseRefCase(cli_base_ref="cli/1.3.x", config_base_ref="origin/1.2.x", expected="cli/1.3.x"),
            _BaseRefCase(cli_base_ref="cli/1.3.x", config_base_ref=None, expected="cli/1.3.x"),
            _BaseRefCase(cli_base_ref=None, config_base_ref=None, expected=None),
        ],
    )
    def test_base_ref_precedence_on_review_pass(
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        mock_vendored_sources,
        case: _BaseRefCase,
    ) -> None:
        review: dict = {"agent": "codex", "additional": {"patience": 3}}

        if case.config_base_ref is not None:
            review["base_ref"] = case.config_base_ref

        monkeypatch.chdir(tmp_path)
        write_goga_config(image="goga:latest", review=review)
        Path("plan.md").write_text("# plan\n")
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        config = load_project_config()
        cli_options: dict = {"skip_manifest_check": True}

        if case.cli_base_ref is not None:
            cli_options["base_ref"] = case.cli_base_ref

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", config, cli_options)

        assert result == 0

        # The always-two-pass cycle: tasks-only first, review second.
        assert mock_run.call_count == 2
        first_options = mock_run.call_args_list[0].args[1]
        second_options = mock_run.call_args_list[1].args[1]
        assert first_options["tasks_only"] is True
        assert second_options["review"] is True

        # The review-carrying pass alone carries the review-scoped flags; the
        # full argv is pinned (not just flag membership) so a flag/value
        # transposition or a stray token fails the test.
        second_cmd = _build_command("plan.md", second_options)

        if case.expected is None:
            # Omit arm: neither source set the base — no --base-ref token.
            assert "base_ref" not in second_options
            assert second_cmd == [
                "ralphex",
                "plan.md",
                "--config-dir",
                ".ralphex/",
                "--review",
                "--review-patience",
                "3",
            ]
        else:
            assert second_cmd == [
                "ralphex",
                "plan.md",
                "--config-dir",
                ".ralphex/",
                "--review",
                "--review-patience",
                "3",
                "--base-ref",
                case.expected,
            ]

        # The tasks pass carries the universal options only — a diff base on the
        # task pass would scope the wrong phase of the run.
        first_cmd = _build_command("plan.md", first_options)
        assert first_cmd == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
            "--tasks-only",
        ]
