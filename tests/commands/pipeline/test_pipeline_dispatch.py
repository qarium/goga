"""Contract and logic tests for the extended ``pipeline`` Click command surface.

These tests pin the click-command contract declared in
``goga/commands/pipeline/CODEMANIFEST`` for the extended entity
``pipeline(ctx, name, extra_env, proxy, add_host, clean, update)``:

- new ``--proxy``, ``--add-host`` (multiple), ``--clean``, ``--update/-u`` options
- new ``-b/--branch`` option (run form only): one Option with both forms
  binding the ``branch`` parameter; the guarded branch procedure runs after
  the step-2 validation and before any docker activity, prints exactly one
  stdout line, and never forwards the branch name into a launcher
- proxy resolution: ``--proxy`` wins over ``config.pipeline.proxy``
- hosts resolution: ``--add-host`` entries merge on top of
  ``config.pipeline.hosts`` (CLI overrides config on key conflict)
- dispatch semantics: discovery (``name is None``) forces ``clean=False``;
  run mode forwards ``clean``; both modes forward ``proxy``/``hosts``/``update``
- exit code propagated via ``ctx.exit``

The dispatch target ``run_pipeline_container`` is mocked so these tests stay
focused on the click surface and the host-side resolution logic, with no docker
dependency.
"""

from __future__ import annotations

import inspect
import sys
import typing
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.pipeline import pipeline
from goga.commands.pipeline.pipeline import pipeline as pipeline_cmd
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _make_config(
    *,
    pipeline_proxy: str | None = None,
    pipeline_hosts: dict[str, str] | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig, optionally with pipeline.proxy/hosts."""
    return ProjectConfig(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(
            agent="claude",
            proxy=pipeline_proxy,
            hosts=pipeline_hosts or {},
        ),
    )


# --- Contract tests ---


class TestPipelineDispatchContract:
    def test_pipeline_has_proxy_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "proxy" in param_names

    def test_pipeline_has_add_host_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "add_host" in param_names

    def test_pipeline_add_host_option_is_multiple(self) -> None:
        add_host_param = next(p for p in pipeline.params if p.name == "add_host")
        assert add_host_param.multiple is True

    def test_pipeline_has_clean_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "clean" in param_names

    def test_pipeline_clean_option_defaults_false(self) -> None:
        clean_param = next(p for p in pipeline.params if p.name == "clean")
        assert clean_param.is_flag is True
        assert clean_param.default is False

    def test_pipeline_has_update_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "update" in param_names

    def test_pipeline_update_option_defaults_false(self) -> None:
        update_param = next(p for p in pipeline.params if p.name == "update")
        assert update_param.is_flag is True
        assert update_param.default is False

    def test_pipeline_update_has_short_flag(self) -> None:
        update_param = next(p for p in pipeline.params if p.name == "update")
        assert "-u" in update_param.opts

    def test_help_lists_new_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(pipeline, ["--help"])
        assert result.exit_code == 0
        output = result.output
        assert "--proxy" in output
        assert "--add-host" in output
        assert "--clean" in output
        assert "--update" in output
        assert "-u" in output


class TestPipelineBranchOptionContract:
    def test_pipeline_branch_option_contract_both_forms_one_option(self) -> None:
        """-b/--branch is a single Option binding ``branch``; both forms reach the procedure.

        The Option carries both forms (``set(param.opts)`` is exactly the pair),
        defaults to None, and is a plain string option (click renders the
        declared ``type=str`` as its canonical STRING param type). The callback
        declares ``branch: str | None`` directly after ``info`` (contract
        order), and ``--branch x NAME`` / ``-b x NAME`` reach
        ``ensure_pipeline_branch`` with the same value.
        """
        branch_param = next(p for p in pipeline.params if p.name == "branch")
        assert set(branch_param.opts) == {"-b", "--branch"}
        assert branch_param.default is None
        assert branch_param.type is click.STRING

        parameters = list(inspect.signature(pipeline_cmd.callback).parameters)
        assert parameters.index("branch") == parameters.index("info") + 1
        hints = typing.get_type_hints(pipeline_cmd.callback)
        assert hints["branch"] == str | None

        config = _make_config()
        runner = CliRunner()
        for argv in (["--branch", "x", "my-pipeline"], ["-b", "x", "my-pipeline"]):
            with (
                mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
                mock.patch.object(_pipeline_module, "ensure_pipeline_branch", return_value="x") as mock_ensure,
                mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0),
            ):
                result = runner.invoke(pipeline, argv)

            assert result.exit_code == 0
            mock_ensure.assert_called_once_with("x")


# --- Logic tests (positive) ---


class TestPipelineDispatchLogic:
    def test_pipeline_dispatch_run_mode_with_clean(self) -> None:
        """Run mode forwards proxy/hosts/clean/update; exit code propagates via ctx.exit."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=42) as mock_run,
        ):
            result = runner.invoke(
                pipeline,
                [
                    "deploy",
                    "--proxy",
                    "http://corp:3128",
                    "--add-host",
                    "foo.local:127.0.0.1",
                    "--clean",
                ],
            )

        assert result.exit_code == 42
        mock_run.assert_called_once_with(
            name="deploy",
            config=config,
            extra_env=(),
            proxy="http://corp:3128",
            hosts={"foo.local": "127.0.0.1"},
            clean=True,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_proxy_none_falls_back_to_config(self) -> None:
        """When --proxy is absent, config.pipeline.proxy is forwarded."""
        config = _make_config(pipeline_proxy="http://from-config:3128")
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            name="deploy",
            config=config,
            extra_env=(),
            proxy="http://from-config:3128",
            hosts={},
            clean=False,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_update_flag_forwarded(self) -> None:
        """--update/-u is forwarded as update=True in both modes."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["deploy", "-u"])

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["update"] is True


# --- Logic tests (edge) ---


class TestPipelineDispatchEdge:
    def test_pipeline_dispatch_list_form_ignores_clean(self) -> None:
        """The flat-list form never carries run state — --clean is not forwarded.

        Under the five-form contract a bare ``--clean`` names no form (step 2.2
        exits 1), and the listing forms dispatch to
        ``run_pipeline_info_container`` whose signature has no ``clean`` slot at
        all — the runtime dir is never wiped outside the run form. The former
        discovery-mode ``clean forced to False`` behavior lives here now.
        """
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["--list", "--clean"])

        assert result.exit_code == 0
        mock_info.assert_called_once_with(
            name=None,
            info=False,
            config=config,
            hosts={},
            update=False,
            workflow=None,
            no_workflow=False,
        )

    def test_pipeline_add_host_merges_over_config(self) -> None:
        """--add-host entries merge on top of config.pipeline.hosts; CLI wins on conflict."""
        config = _make_config(pipeline_hosts={"a.local": "10.0.0.1"})
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                pipeline,
                [
                    "deploy",
                    "--add-host",
                    "a.local:192.168.1.1",
                    "--add-host",
                    "b.local:127.0.0.1",
                ],
            )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["hosts"] == {
            "a.local": "192.168.1.1",
            "b.local": "127.0.0.1",
        }

    @pytest.mark.parametrize("exit_code", [0, 1, 2, 42, 127, 130])
    def test_pipeline_propagates_exit_code(self, exit_code: int) -> None:
        """The container exit code is propagated via ctx.exit."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=exit_code),
        ):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == exit_code


class TestPipelineBranchRunForm:
    def test_pipeline_run_form_with_branch_prints_line_and_launches(self) -> None:
        """The run form runs the procedure, prints the branch line, launches without the name."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "ensure_pipeline_branch", return_value="feat/x") as mock_ensure,
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["-b", "feat/x", "my-pipeline"])

        assert result.exit_code == 0
        assert "Pipeline running on branch feat/x" in result.stdout
        mock_ensure.assert_called_once_with("feat/x")
        assert mock_run.call_count == 1
        assert mock_run.call_args.kwargs["name"] == "my-pipeline"
        # The branch name never crosses the docker boundary — no branch kwarg,
        # no value equal to it anywhere in the launcher call.
        assert "branch" not in mock_run.call_args.kwargs
        assert "feat/x" not in mock_run.call_args.kwargs.values()

    @pytest.mark.parametrize(
        "argv",
        [
            ["-b", "x", "--list"],
            ["-b", "x", "--list", "--info"],
            ["-b", "x", "my-pipeline", "--info"],
        ],
        ids=["flat-list", "overview", "card"],
    )
    def test_pipeline_list_and_info_forms_silently_skip_branch(self, argv: list[str]) -> None:
        """The flat list, overview, and card forms ignore -b — no procedure, no line."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "ensure_pipeline_branch") as mock_ensure,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0),
        ):
            result = runner.invoke(pipeline, argv)

        assert result.exit_code == 0
        mock_ensure.assert_not_called()
        assert "Pipeline running on branch" not in result.stdout

    def test_pipeline_missing_name_error_precedes_branch_procedure(self) -> None:
        """A step-2 form error exits 1 before any git action of the branch procedure."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "ensure_pipeline_branch") as mock_ensure,
            mock.patch.object(_pipeline_module, "run_pipeline_container") as mock_run,
        ):
            result = runner.invoke(pipeline, ["-b", "feat/x"])

        assert result.exit_code == 1
        assert "Missing pipeline name" in result.output
        mock_ensure.assert_not_called()
        mock_run.assert_not_called()


class TestPipelineCallbackSignature:
    def test_pipeline_callback_has_new_parameters(self) -> None:
        """The decorated callback exposes proxy/add_host/clean/update parameters."""
        parameters = pipeline_cmd.callback.__annotations__
        assert "proxy" in parameters
        assert "add_host" in parameters
        assert "clean" in parameters
        assert "update" in parameters
