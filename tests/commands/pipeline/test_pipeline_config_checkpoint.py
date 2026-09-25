"""Config-amendment checkpoint tests for the ``pipeline`` command.

Pins the consumer-side delivery shape of the ``checkpoints`` practice: the
authored load and the ``ConfigHooks().amend_config`` checkpoint sit together
inside the command's existing load try, the summary lines print to stderr,
and every downstream read addresses the effective configuration — the
dispatch hands the launcher the overlay's config. The platform boundary
fixtures pin only the installed-packages mapping and the ``sys.modules``
entry of the fake ``goga_tool_*`` package; the delivery itself runs for
real.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
from goga.commands.pipeline.pipeline import pipeline

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command; resolve the real module via sys.modules (the
# sibling test_pipeline_command.py precedent).
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _write_config(tmp_path: Path) -> None:
    """Write a pipeline-capable ``.goga/config.yml`` under ``tmp_path``."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    (goga_dir / "config.yml").write_text(
        "language: python\n"
        "image: qarium/goga:latest\n"
        "build:\n"
        "  agent: claude\n"
        "pipeline:\n"
        "  agent: claude\n"
    )


def _register_hardener(hooks: object) -> None:
    """Subscribe one hook that buffers a pipeline env amendment."""

    def harden(context: object) -> None:
        context.set("pipeline.env.LOG_LEVEL", "DEBUG")  # type: ignore[attr-defined]

    hooks.subscribe("config", "amend_config", "hardening", harden)  # type: ignore[attr-defined]


class TestPipelineConfigCheckpoint:
    def test_pipeline_consumes_effective_config_and_prints_summary_to_stderr(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The dispatch hands the launcher the effective configuration.

        One run without tools (the baseline) and one with a forcing tool:
        the launcher receives the amended ``pipeline.env``, the summary line
        lands on stderr only, and stdout and exit code stay identical.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            baseline = runner.invoke(pipeline, ["deploy"])
            assert baseline.exit_code == 0
            baseline_config = mock_run.call_args.kwargs["config"]
            assert baseline_config.pipeline.env == {}

            pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})
            install_tool_package("goga_tool_hardener", register_hooks=_register_hardener)

            amended = runner.invoke(pipeline, ["deploy"])

        assert amended.exit_code == 0, amended.output
        effective_config = mock_run.call_args.kwargs["config"]
        assert effective_config is not baseline_config
        assert effective_config.pipeline.env == {"LOG_LEVEL": "DEBUG"}

        assert "- hardener set pipeline.env.LOG_LEVEL" in amended.stderr
        assert "- hardener set pipeline.env.LOG_LEVEL" not in amended.stdout
        assert amended.stdout == baseline.stdout
        assert amended.exit_code == baseline.exit_code

    def test_pipeline_hard_checkpoint_failure_is_clean_error(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the command: exit 1, clean message, no dispatch."""

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("config", "amend_config", "exploding", boom)  # type: ignore[attr-defined]

        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})
        install_tool_package("goga_tool_hardener", register_hooks=register)

        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 1
        assert "failed on config.amend_config" in result.output
        assert "Traceback" not in result.output
        mock_run.assert_not_called()
