from __future__ import annotations

import inspect
import sys
from pathlib import Path
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


def _make_config() -> ProjectConfig:
    """Build a minimal ProjectConfig satisfying the new schema (top-level image, pipeline block)."""
    return ProjectConfig(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude"),
    )


class TestPipelineContract:
    def test_pipeline_importable_from_facade(self) -> None:
        """pipeline is importable from the goga.commands.pipeline facade."""
        assert pipeline is not None

    def test_pipeline_is_a_click_command(self) -> None:
        """pipeline is a single click.Command (NOT a group — no subcommands)."""
        assert isinstance(pipeline, click.Command)
        assert not isinstance(pipeline, click.Group)

    def test_pipeline_callback_takes_optional_name(self) -> None:
        """The pipeline command exposes an optional positional name argument (required=False)."""
        parameters = inspect.signature(pipeline_cmd.callback).parameters

        assert "name" in parameters
        # The Click-decorated command exposes name as optional (required=False).
        # Click's optional positional argument does not carry a Python default on
        # the callback (it is inspect.Parameter.empty); the relevant property is
        # that the registered argument is not required.
        name_param = next(p for p in pipeline.params if isinstance(p, click.Argument) and p.name == "name")
        assert name_param.required is False

    def test_pipeline_callback_takes_extra_env_option(self) -> None:
        """The pipeline command exposes a `-e/--env` Click option (multiple)."""
        env_option = next(
            (p for p in pipeline.params if isinstance(p, click.Option) and p.name == "extra_env"),
            None,
        )
        assert env_option is not None, "pipeline command must define an `extra_env` Click option"
        # Both short and long forms must be registered, matching `goga build`.
        assert "-e" in env_option.opts
        assert "--env" in env_option.opts
        # Click `multiple=True` always passes an empty tuple to the callback when
        # the flag is absent (independent of `default`), which preserves the
        # pre-option behavior of `goga pipeline`.
        assert env_option.multiple is True

    def test_pipeline_has_skip_option_with_short_alias(self) -> None:
        """The pipeline command exposes a repeatable `-s/--skip` Click option."""
        skip_param = next(
            (p for p in pipeline.params if isinstance(p, click.Option) and p.name == "skip"),
            None,
        )
        assert skip_param is not None, "pipeline command must define a `skip` Click option"
        # Both short and long forms must be registered.
        assert "-s" in skip_param.opts
        assert "--skip" in skip_param.opts
        # Repeatable: each `-s/--skip NAME` appends one stage name -> tuple.
        assert skip_param.multiple is True

    def test_pipeline_clean_option_has_short_alias(self) -> None:
        """The `--clean` option gains a short `-c` alias (still a flag)."""
        clean_param = next(
            (p for p in pipeline.params if isinstance(p, click.Option) and p.name == "clean"),
            None,
        )
        assert clean_param is not None
        assert "-c" in clean_param.opts
        assert "--clean" in clean_param.opts
        assert clean_param.is_flag is True

    def test_pipeline_workflow_option_has_short_alias(self) -> None:
        """The `--workflow` option gains a short `-w` alias (str, optional)."""
        workflow_param = next(
            (p for p in pipeline.params if isinstance(p, click.Option) and p.name == "workflow"),
            None,
        )
        assert workflow_param is not None
        assert "-w" in workflow_param.opts
        assert "--workflow" in workflow_param.opts

    def test_pipeline_callback_has_skip_parameter(self) -> None:
        """The decorated callback exposes a `skip` parameter."""
        parameters = inspect.signature(pipeline_cmd.callback).parameters
        assert "skip" in parameters


class TestPipelineLogic:
    def test_pipeline_delegates_to_run_pipeline_container_discovery(self) -> None:
        """pipeline (no name) delegates to run_pipeline_container with (None, config, ())."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(pipeline, [])

        assert result.exit_code == 0
        mock_rpc.assert_called_once_with(
            name=None,
            config=config,
            extra_env=(),
            proxy=None,
            hosts={},
            clean=False,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_delegates_to_run_pipeline_container_run(self) -> None:
        """pipeline <name> delegates to run_pipeline_container with (name, config, ())."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        mock_rpc.assert_called_once_with(
            name="deploy",
            config=config,
            extra_env=(),
            proxy=None,
            hosts={},
            clean=False,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_passes_extra_env_to_run_pipeline_container(self) -> None:
        """`-e KEY=VALUE` (repeatable) is forwarded as a tuple to run_pipeline_container."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(
                pipeline,
                ["deploy", "-e", "ANTHROPIC_API_KEY=sk-xxx", "-e", "MODEL=claude-sonnet-4-6"],
            )

        assert result.exit_code == 0
        mock_rpc.assert_called_once_with(
            name="deploy",
            config=config,
            extra_env=("ANTHROPIC_API_KEY=sk-xxx", "MODEL=claude-sonnet-4-6"),
            proxy=None,
            hosts={},
            clean=False,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_accepts_long_env_option(self) -> None:
        """The `--env KEY=VALUE` long form is accepted identically to `-e`."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(pipeline, ["deploy", "--env", "FOO=bar"])

        assert result.exit_code == 0
        mock_rpc.assert_called_once_with(
            name="deploy",
            config=config,
            extra_env=("FOO=bar",),
            proxy=None,
            hosts={},
            clean=False,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_accepts_skip_and_clean_short_aliases(self) -> None:
        """`-s/--skip` (repeatable) + `-c` short clean alias are forwarded as kwargs."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(
                pipeline,
                ["deploy", "--skip", "build", "-s", "test", "-c"],
            )

        assert result.exit_code == 0
        assert mock_rpc.call_args.kwargs["skip"] == ("build", "test")
        assert mock_rpc.call_args.kwargs["clean"] is True

    def test_pipeline_click_parallel_option_threads_through(self) -> None:
        """`-p N` and `--parallel N` both forward parallel=<N> to run_pipeline_container."""
        config = _make_config()
        runner = CliRunner()
        for argv in (["deploy", "-p", "4"], ["deploy", "--parallel", "4"]):
            with (
                mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
                mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
            ):
                result = runner.invoke(pipeline, argv)

            assert result.exit_code == 0, f"failed for {argv}: {result.output}"
            assert mock_rpc.call_args.kwargs["parallel"] == 4

    def test_pipeline_click_parallel_defaults_none(self) -> None:
        """`goga pipeline NAME` without `-p` forwards parallel=None (unbounded)."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        assert mock_rpc.call_args.kwargs["parallel"] is None

    def test_pipeline_discovery_forces_empty_skip(self) -> None:
        """In discovery mode (no name) --skip is a no-op: skip forced to ()."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(pipeline, ["--skip", "build"])

        assert result.exit_code == 0
        # Discovery (name is None) ignores --skip, mirroring the clean=False forcing.
        assert mock_rpc.call_args.kwargs["name"] is None
        assert mock_rpc.call_args.kwargs["skip"] == ()

    def test_pipeline_clean_short_alias_equivalent(self) -> None:
        """`-c` and `--clean` produce the same clean=True dispatch value."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            runner.invoke(pipeline, ["deploy", "--clean"])
            kwargs_long = mock_rpc.call_args.kwargs["clean"]
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            runner.invoke(pipeline, ["deploy", "-c"])
            kwargs_short_c = mock_rpc.call_args.kwargs["clean"]

        assert kwargs_long is True
        assert kwargs_long == kwargs_short_c

    def test_pipeline_workflow_short_alias_equivalent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """`-w` and `--workflow` produce the same workflow=<name> dispatch value."""
        config = _make_config()
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "custom.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            runner.invoke(pipeline, ["deploy", "--workflow", "custom"])
            kwargs_long = mock_rpc.call_args.kwargs["workflow"]
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            runner.invoke(pipeline, ["deploy", "-w", "custom"])
            kwargs_short_w = mock_rpc.call_args.kwargs["workflow"]

        assert kwargs_long == "custom"
        assert kwargs_long == kwargs_short_w

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

    def test_pipeline_raises_clickexception_when_config_load_fails(self) -> None:
        """A config load failure surfaces as a non-zero exit code via ClickException."""
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", side_effect=FileNotFoundError("no config")),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_rpc,
        ):
            result = runner.invoke(pipeline, [])

        assert result.exit_code != 0
        assert "no config" in result.output
        # The container was never launched — config load failed first.
        mock_rpc.assert_not_called()


class TestPipelineBoundary:
    def test_pipeline_module_has_no_type_imports_from_goga_pipeline(self) -> None:
        """pipeline.py must NOT import any Type from goga/pipeline (docker runtime boundary)."""
        assert _pipeline_module.__file__ is not None
        source = Path(_pipeline_module.__file__).read_text()
        assert "from ...pipeline import" not in source
        assert "from goga.pipeline import" not in source
        # The only goga imports are config + intra-cell run_pipeline_container.
        assert "from ...config import load_project_config" in source
        assert "from .run_pipeline_container import run_pipeline_container" in source
