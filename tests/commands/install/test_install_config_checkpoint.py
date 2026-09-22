"""Config-amendment checkpoint tests for the ``install`` command's bulk path.

Pins the consumer-side delivery shape of the ``checkpoints`` practice on the
bulk path only (the single and local paths carry no load, so no checkpoint):
the delivery joins the bulk load try, the summary lines print to stderr, and
the installed set derives from the effective ``tools`` mapping. The platform
boundary fixtures pin only the installed-packages mapping and the
``sys.modules`` entry of the fake ``goga_tool_*`` package.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
from goga.cli import app

_install_module = importlib.import_module("goga.commands.install.install")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


def _write_config(tmp_path: Path) -> None:
    """Write a bulk-install ``.goga/config.yml`` under ``tmp_path``."""
    config_dir = tmp_path / ".goga"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text("language: python\ntools:\n  afm: 1.0.x\n")


def _register_hardener(hooks: object) -> None:
    """Subscribe one hook that buffers a tools-mapping amendment."""

    def harden(context: object) -> None:
        context.set("tools.viewer", "1.x")  # type: ignore[attr-defined]

    hooks.subscribe("config", "amend_config", "hardening", harden)  # type: ignore[attr-defined]


class TestInstallConfigCheckpoint:
    def test_install_bulk_consumes_effective_tools_and_prints_summary_to_stderr(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The bulk pip call installs the effective tools mapping.

        One run without tools (the baseline) and one with an amending tool:
        the pip argv gains the amended tool, the summary line lands on stderr
        only, and stdout and exit code stay identical.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            baseline = runner.invoke(app, ["install"])
            assert baseline.exit_code == 0
            baseline_argv = mock_run.call_args[0][0]

            pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})
            install_tool_package("goga_tool_hardener", register_hooks=_register_hardener)

            amended = runner.invoke(app, ["install"])

        assert amended.exit_code == 0, amended.output
        amended_argv = mock_run.call_args[0][0]
        assert "goga-tool-viewer~=1.0" in amended_argv
        assert amended_argv.count("install") == baseline_argv.count("install")
        assert amended_argv[: amended_argv.index("install") + 1] == baseline_argv[: baseline_argv.index("install") + 1]

        assert "- hardener set tools.viewer" in amended.stderr
        assert "- hardener set tools.viewer" not in amended.stdout
        assert amended.stdout == baseline.stdout
        assert amended.exit_code == baseline.exit_code

    def test_install_bulk_hard_checkpoint_failure_is_clean_error(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the bulk path: exit 1, clean message, no pip."""

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("config", "amend_config", "exploding", boom)  # type: ignore[attr-defined]

        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})
        install_tool_package("goga_tool_hardener", register_hooks=register)

        runner = CliRunner()
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = runner.invoke(app, ["install"])

        assert result.exit_code == 1
        assert "failed on config.amend_config" in result.output
        assert "Traceback" not in result.output
        mock_run.assert_not_called()

    def test_install_single_path_has_no_checkpoint(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """The single path installs without any config load or checkpoint."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        boundary = pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})

        runner = CliRunner()
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
            mock.patch.object(_install_module, "run_install_hooks"),
        ):
            result = runner.invoke(app, ["install", "afm"])

        assert result.exit_code == 0
        assert boundary.call_count == 0  # no registry assembly without a load
        argv = mock_run.call_args[0][0]
        assert "goga-tool-afm" in argv

    def test_install_local_path_has_no_checkpoint(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """The local path installs without any config load or checkpoint either."""
        _write_config(tmp_path)
        (tmp_path / "my-tool").mkdir()
        monkeypatch.chdir(tmp_path)
        boundary = pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})

        runner = CliRunner()
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
            mock.patch.object(_install_module, "run_install_hooks"),
        ):
            result = runner.invoke(app, ["install", "--local", "my-tool"])

        assert result.exit_code == 0, result.output
        assert boundary.call_count == 0  # no registry assembly without a load
        argv = mock_run.call_args[0][0]
        assert "my-tool" in argv
