"""Contract tests for the ``pipeline`` Click command surface.

These tests pin the click-command contract declared in
``goga/commands/pipeline/CODEMANIFEST`` for the entity
``pipeline(ctx, name, extra_env)``:

- a single ``click.Command`` (not a group)
- an optional positional ``name`` argument (``None`` -> discovery, provided -> run)
- a repeatable ``-e/--env`` option bound to ``extra_env``
- dispatch to ``run_pipeline_container(name, config, extra_env)`` via keyword args
- propagation of the container exit code through the click context
- schema errors surfaced as ``click.ClickException``

The dispatch target ``run_pipeline_container`` is mocked so these tests stay
focused on the click surface (argument parsing, dispatch wiring, exit-code
propagation) and do not depend on docker.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner

# Importing the module populates sys.modules; the import is also how the
# contract obligation ``from goga.commands.pipeline.pipeline import pipeline``
# is exercised. ``pipeline`` is the click command (re-exported identically by
# the package __init__, which would otherwise shadow the submodule name).
from goga.commands.pipeline.pipeline import pipeline

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules, mirroring the
# sibling test_pipeline.py module.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _write_config(tmp_path: Path, *, with_pipeline: bool = True) -> None:
    """Materialize a ``.goga/config.yml`` under ``tmp_path``.

    Args:
        tmp_path: Project root used as the working directory for the test.
        with_pipeline: When ``False`` the ``pipeline:`` block is omitted,
            producing a schema error (``pipeline`` section required) that the
            command surfaces as a ``click.ClickException``.
    """
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "language: python",
        "image: qarium/goga:latest",
        "build:",
        "  task_executor:",
        "    agent: claude",
    ]
    if with_pipeline:
        lines += [
            "pipeline:",
            "  agent: claude",
        ]
    (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")


# --- Contract obligation ---


class TestPipelineCommandContract:
    def test_pipeline_is_importable_and_is_click_command(self) -> None:
        """``from goga.commands.pipeline.pipeline import pipeline`` succeeds; it is a click.Command."""
        from goga.commands.pipeline.pipeline import pipeline as imported

        assert imported is not None
        assert isinstance(imported, click.Command)
        # A single command, not a group — no ls/run subcommands (per the `click` practice).
        assert not isinstance(imported, click.Group)

    def test_pipeline_command_discovery_calls_container_with_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No positional ``name`` dispatches ``run_pipeline_container(name=None)``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, [])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["name"] is None

    def test_pipeline_command_collects_extra_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The repeatable ``-e/--env`` option is collected and forwarded as ``extra_env``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(
                pipeline,
                ["deploy", "-e", "FOO=bar", "--env", "BAZ=qux"],
            )

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["extra_env"] == ("FOO=bar", "BAZ=qux")
        assert mock_run.call_args.kwargs["name"] == "deploy"

    def test_pipeline_raises_on_schema_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A config schema missing the ``pipeline`` block surfaces as a ClickException."""
        _write_config(tmp_path, with_pipeline=False)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # standalone_mode=False propagates the ClickException as result.exception
        # instead of Click converting it to SystemExit during CLI handling.
        result = runner.invoke(pipeline, ["deploy"], standalone_mode=False)

        assert result.exit_code != 0
        assert isinstance(result.exception, click.ClickException)
        assert "pipeline" in str(result.exception).lower()


# --- Logic tests ---


class TestPipelineCommandLogic:
    def test_pipeline_command_run_mode_passes_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A provided ``name`` is forwarded to ``run_pipeline_container(name=<name>)``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["name"] == "deploy"

    def test_pipeline_command_propagates_exit_code(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The container exit code is propagated via ``ctx.exit``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=42):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 42
