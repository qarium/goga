"""Cross-cell integration tests: host forms ↔ in-container CLI consistency.

The unit tests of Tasks 1-12 pin each cell in isolation; these tests pin the
seams BETWEEN the cells — the property the whole ``pipeline-info`` feature
stands on:

- the argv a host form hands to ``docker run`` parses cleanly in the
  in-container parser ``pipeline_cli`` and means the same operation
  (host argv ``["-m", "goga.pipeline", "list", "--info"]`` ⇒ container
  ``pipeline_cli(["list", "--info"])``);
- the workflow decision survives the flag→argv→routine path identically for
  the card (CLI flags) and the run (env decision) — both reach
  ``compile_flow`` with the same parsed workflow, so what the card shows is
  structurally what the run executes (AC-3);
- a host form error (``--list deploy``, no name, ``-w``+``--no-workflow``,
  ghost workflow) never reaches docker — no builder, no update, no runner.

Docker is never required: the only external boundary mocked is
``DockerRunner.run`` (argv capture, exit 0) plus the builder/prelude
functions around it, per the module convention of patching real module
attributes — never ``sys.modules`` shadowing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands.pipeline.pipeline import pipeline
from goga.config import HomeConfig
from goga.pipeline import pipeline_cli, run_pipeline
from goga.pipeline.order_stages import order_stages

# The package __init__ files re-export the routine names, shadowing the
# submodule names in attribute access — resolve the real modules through
# sys.modules for mock.patch.object targets. Per
# [[feedback_mock_patch_module_shadowing]].
_rpic_mod = sys.modules["goga.commands.pipeline.run_pipeline_info_container"]
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]
_describe_pipeline_module = sys.modules["goga.pipeline.describe_pipeline"]
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# General Setup fixtures: a STAGES DSL file (build→test) and the hardening
# workflow (skip test + extend audit) — the same pair the design's Test Stack
# Trace uses across both cells.
_DEPLOY_YML = """\
name: Deploy
description: Deploy the service
---

build:
  title: Build
test:
  title: Test
  depends_on:
    - build
"""

_HARDENING_YML = "stages:\n  test:\n    skip: true\nextend:\n  audit:\n    after: [test]\n    title: Audit\n"


def _write_project(tmp_path: Path, *, with_hardening: bool = True) -> Path:
    """Materialize a minimal project: config, pipeline-file, workflow-file.

    Args:
        tmp_path: Project root used as the working directory for the test.
        with_hardening: When ``True`` also write ``.goga/workflows/
            hardening.yml`` (skipped where its auto-match would be noise).

    Returns:
        The project-level pipelines directory.
    """
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    (goga_dir / "config.yml").write_text(
        "\n".join(
            [
                "language: python",
                "image: qarium/goga:latest",
                "build:",
                "  task_executor:",
                "    agent: claude",
                "pipeline:",
                "  agent: claude",
            ]
        )
        + "\n"
    )
    project_dir = goga_dir / "pipelines"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "deploy.yml").write_text(_DEPLOY_YML)
    if with_hardening:
        workflows_dir = goga_dir / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "hardening.yml").write_text(_HARDENING_YML)
    return project_dir


def _fail_test(name: str) -> mock.Mock:
    """Build a Mock that fails the test loudly if docker activity reaches it."""
    return mock.Mock(side_effect=AssertionError(f"docker activity reached {name} before form validation"))


def _spy_compile(target_module: Any, captured: dict[str, Any]) -> mock._patch:
    """Patch ``compile_flow`` on ``target_module`` with a pass-through spy.

    The spy records the ``workflow`` argument and the returned
    :class:`FlowDocument` into ``captured`` and delegates to the real
    compiler, so the observed values are the production ones.
    """
    real_compile = target_module.compile_flow

    def _spy(pipeline_path: Path, flow_path: Path, workflow: object = None, **kwargs: object):
        result = real_compile(pipeline_path, flow_path, workflow=workflow, **kwargs)
        captured["workflow"] = workflow
        captured["flow_doc"] = result[1]
        return result

    return mock.patch.object(target_module, "compile_flow", side_effect=_spy)


# --- Cross-entity: host argv ↔ container parser ---


class TestHostArgvIsContainerParseable:
    @pytest.mark.parametrize(
        ("host_argv", "expected_lines"),
        [
            (["--list"], ["* deploy (project)"]),
            (
                ["--list", "--info"],
                ["* deploy (project)", "    name: Deploy", "    description: Deploy the service"],
            ),
            (
                ["deploy", "--info"],
                [
                    "name: Deploy",
                    "description: Deploy the service",
                    "---",
                    "* build:",
                    "    title: Build",
                    "* test:",
                    "    title: Test",
                ],
            ),
        ],
        ids=["flat-list", "overview", "card"],
    )
    def test_each_info_form_argv_parses_and_means_the_same_operation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        host_argv: list[str],
        expected_lines: list[str],
    ) -> None:
        """The argv a host form passes to ``docker run`` runs cleanly in ``pipeline_cli``.

        The host form is invoked for real up to the docker boundary, where
        ``DockerRunner.run`` is mocked to capture its argv (exit 0). The
        captured argv minus the ``-m goga.pipeline`` prefix is then replayed
        through the REAL in-container parser on a project holding
        ``deploy.yml`` — the operation must print its output and exit 0,
        proving the two surfaces stay in lockstep.
        """
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        runner_cls = mock.MagicMock()
        runner_cls.return_value.run.return_value = 0
        with (
            mock.patch.object(_rpic_mod, "_check_docker", mock.Mock(return_value=True)),
            mock.patch.object(_rpic_mod, "DockerRunner", runner_cls),
            mock.patch.object(_rpic_mod, "docker_build_if_not_exist", mock.Mock()),
            mock.patch.object(_rpic_mod, "docker_update", mock.Mock()),
            mock.patch.object(_rpic_mod, "load_home_config", mock.Mock(return_value=HomeConfig())),
        ):
            result = CliRunner().invoke(pipeline, host_argv)

        assert result.exit_code == 0, result.output
        docker_argv = runner_cls.return_value.run.call_args.args[0]
        assert docker_argv[:2] == ["-m", "goga.pipeline"]

        # Container side: replay the captured argv through the real parser on
        # the same project (cwd/home patched per the in-container layout).
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        capsys.readouterr()
        exit_code = pipeline_cli(docker_argv[2:])
        out = capsys.readouterr().out

        assert exit_code == 0
        for line in expected_lines:
            assert line in out, f"expected {line!r} in container output:\n{out}"


# --- Cross-entity: workflow decision equivalence (card vs run) ---


class TestWorkflowDecisionEquivalence:
    def test_card_and_run_compose_the_same_stages(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The card (CLI flags) and the run (env decision) compile the same workflow.

        AC-3 in structural form: ``pipeline_cli(["run", "deploy", "--info",
        "-w", "hardening"])`` and ``run_pipeline`` under
        ``GOGA_WORKFLOW_NAME=hardening`` both reach ``compile_flow`` with the
        SAME parsed :class:`WorkflowDocument`, and the card's printed stage
        rows equal the run's compiled stage composition — what you see is
        what executes. The hardening workflow (skip ``test`` + extend
        ``audit``) makes the case nontrivial: the composition is
        ``build, audit``, not the raw ``build, test``.
        """
        project_dir = _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.delenv("GOGA_SKIP_STAGES", raising=False)
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "hardening")
        afm_dir = tmp_path / "afm"
        afm_dir.mkdir()
        monkeypatch.setenv("AFM_DIR", str(afm_dir))
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Card side — the CLI-flag decision path.
        card_captured: dict[str, Any] = {}
        with _spy_compile(_describe_pipeline_module, card_captured):
            card_exit = pipeline_cli(["run", "deploy", "--info", "-w", "hardening"])
        card_out = capsys.readouterr().out

        assert card_exit == 0
        assert card_captured["workflow"] is not None

        # Run side — the env decision path, with the real compiler and only
        # the external afm boundary mocked.
        run_captured: dict[str, Any] = {}
        with (
            _spy_compile(_run_pipeline_module, run_captured),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_exit = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert run_exit == 0
        assert run_captured["workflow"] is not None

        # The same parsed workflow reaches the compiler on both sides.
        assert card_captured["workflow"] == run_captured["workflow"]

        # And the printed card rows equal the run's compiled composition in
        # execution order (loop copies would appear as separate rows here).
        expected_rows = [
            line
            for stage in order_stages(run_captured["flow_doc"].stages)
            for line in (f"* {stage.id}:", f"    title: {stage.name}")
        ]
        card_rows = card_out.splitlines()[5:]
        assert card_rows == expected_rows
        # The workflow actually bent the composition away from the raw DSL —
        # otherwise both assertions above would hold trivially.
        assert card_rows == ["* build:", "    title: Build", "* audit:", "    title: Audit"]


# --- Edge case: host form errors precede any docker activity ---


class TestFormErrorsPrecedeDocker:
    @pytest.mark.parametrize(
        ("argv", "expected_message"),
        [
            (["--list", "deploy"], "--list and a pipeline name are mutually exclusive"),
            ([], 'Missing pipeline name. Use "goga pipeline --list"'),
            (["deploy", "-w", "hardening", "--no-workflow"], "--workflow and --no-workflow are mutually exclusive"),
            (["deploy", "--info", "-w", "ghost"], "workflow 'ghost' not found at"),
        ],
        ids=["list-plus-name", "no-form", "workflow-flags-clash", "ghost-workflow"],
    )
    def test_form_error_never_reaches_docker(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        argv: list[str],
        expected_message: str,
    ) -> None:
        """Every host form error exits 1 before any docker activity.

        The docker boundary of BOTH launchers is armed with fail-test mocks
        (builders, update, runner class). A form error must exit 1 with its
        exact message and trip none of them — no refresh, no first-run
        build, no container launch.
        """
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        # Fail-test arms on BOTH launchers' boundaries — a form error must
        # not trip any of them (the pipeline.py dispatch mocks are not needed:
        # validation runs before dispatch, so the real launchers are the
        # right thing to arm here).
        fail_runner = _fail_test("DockerRunner")
        fail_build = _fail_test("docker_build_if_not_exist")
        fail_update = _fail_test("docker_update")

        with (
            mock.patch.object(_rpic_mod, "_check_docker", mock.Mock(return_value=True)),
            mock.patch.object(_rpic_mod, "DockerRunner", _fail_test("info DockerRunner")),
            mock.patch.object(_rpic_mod, "docker_build_if_not_exist", _fail_test("info build")),
            mock.patch.object(_rpic_mod, "docker_update", _fail_test("info update")),
            mock.patch.object(_rpc_mod, "DockerRunner", fail_runner),
            mock.patch.object(_rpc_mod, "docker_build_if_not_exist", fail_build),
            mock.patch.object(_rpc_mod, "docker_update", fail_update),
        ):
            result = CliRunner().invoke(pipeline, argv)

        assert result.exit_code == 1
        assert expected_message in result.output
        fail_runner.assert_not_called()
        fail_build.assert_not_called()
        fail_update.assert_not_called()
