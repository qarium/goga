"""End-to-end integration tests for the review-scoped ``base_ref`` option.

These stitch together the cross-cell path introduced by the
``add-ref-for-review`` change:

    host                                container
    goga/commands/build (click value    goga/build/__main__ (argparse value
      option --base-ref)                  option --base-ref)
      -> cli_flags -> docker run args     -> cli_options["base_ref"]
                                              -> resolve_review_options step 6-7
    .goga/config.yml build.review_executor   (CLI > review_executor > omit)
      -> load_project_config (loader step 7)
        -> ReviewOptions.base_ref/.patience
          -> _review_scoped_options -> pass composition (review-carrying
            passes only) -> run_ralphex options keys base_ref /
            review_patience -> ralphex flags --base-ref / --review-patience

Three seams only hold end-to-end and are verified here: the value survives the
host->container handoff as the exact docker-run token pair and is parsed back
by the real in-container argparse wiring; an unset option forwards no token and
still lands as a present-but-None ``cli_options`` key (the tri-state that lets
the resolver defer to the config); and a config-declared review base reaches
the ralphex argv of the review pass only — never the tasks pass.

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

import yaml
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

_ROLES = ("quality", "implementation", "testing", "simplification", "documentation")

# Synthetic stand-ins for the vendored ralphex v1.6.1 review prompts. The real
# assets are a maintainers' artifact; tests never depend on it. These tests do
# not exercise role filtering (see test_skip_review_end_to_end.py), so only the
# counter fragments the rewrite touches are carried.
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


class TestBaseRefSurvivesHostToContainer:
    """The review diff base reaches cli_options["base_ref"] undistorted.

    The host click value option (``--base-ref``, default None) is forwarded as
    the exact token pair into the docker run args; the container argparse value
    option parses those same tokens back into one dest. Any lossy conversion on
    either side (the host resolving None against the config, or the token pair
    being dropped in ``_cli_flags_to_args``) would break the CLI >
    ``build.review_executor.*`` > omit precedence that lives in
    ``resolve_review_options``.
    """

    def test_base_ref_survives_host_to_container(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        runner = CliRunner()
        with (
            mock.patch.object(_build_cmd_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_cmd_mod, "_write_env_file", return_value=Path("/tmp/env")),
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

    def test_base_ref_unset_forwards_no_token(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        runner = CliRunner()
        with (
            mock.patch.object(_build_cmd_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_cmd_mod, "_write_env_file", return_value=Path("/tmp/env")),
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
        # None, so the resolver falls through to build.review_executor.base_ref.
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


class TestConfigBaseReachesRalphexFlag:
    """A config-declared review base reaches the ralphex argv of the review pass only.

    Loader (step 7) -> resolve_review_options (steps 6-7) -> pass composition
    (review-scoped fragment joined onto the review-carrying pass only) ->
    ``_build_command`` mapping the composed option keys to the ralphex flags.
    """

    def test_config_base_reach_ralphex_flag_on_review_pass(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(
            tmp_path,
            review_executor={"agent": "codex", "base_ref": "origin/1.2.x", "patience": 3},
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

        # The review-carrying pass alone carries the review-scoped flags: the
        # options keys base_ref / review_patience map onto the ralphex value
        # flags --base-ref / --review-patience. The full argv is pinned (not
        # just flag membership) so a flag/value transposition or a stray token
        # fails the test.
        second_cmd = _build_command("plan.md", mock_run.call_args_list[1].args[1])
        assert second_cmd == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
            "--review",
            "--review-patience",
            "3",
            "--base-ref",
            "origin/1.2.x",
        ]

        # The tasks pass carries the universal options only — a diff base on the
        # task pass would scope the wrong phase of the run.
        first_cmd = _build_command("plan.md", mock_run.call_args_list[0].args[1])
        assert first_cmd == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
            "--tasks-only",
        ]
