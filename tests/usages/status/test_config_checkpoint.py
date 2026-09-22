# tests/usages/status/test_config_checkpoint.py — the config-amendment checkpoint of status

from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
from goga.cli import app
from goga.usages.status import DepStatus, UsageState, status

# Resolve the inner ``status.py`` submodule via importlib (the facade function
# shadows the submodule attribute in the package ``__dict__`` — the same
# pattern ``test_status.py`` documents).
_status_mod = importlib.import_module("goga.usages.status.status")

_USAGES_BLOCK = "usages:\n  libs:\n    click:\n      git: https://x/click.git\n      ref: main\n"


def _write_config(tmp_path: Path) -> None:
    """Write a one-dep ``.goga/config.yml`` under ``tmp_path``."""
    config_dir = tmp_path / ".goga"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(f"language: python\n{_USAGES_BLOCK}")


def _register_pinref(hooks: object) -> None:
    """Subscribe one hook that forces the click dep's ref to a pinned value."""

    def pin(context: object) -> None:
        context.force("usages.libs.click.ref", "amended-ref")  # type: ignore[attr-defined]

    hooks.subscribe("config", "amend_config", "pinning", pin)  # type: ignore[attr-defined]


def _up_to_date(group_name: str, dep_name: str, depcfg, target) -> DepStatus:
    """A stand-in compute result so the target-existing path completes."""
    return DepStatus(group=group_name, dep=dep_name, state=UsageState.up_to_date, entries=[])


class TestStatusConfigCheckpoint:
    def test_status_iterates_the_effective_usages_section(
        self,
        tmp_path: Path,
        monkeypatch,
        capsys,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The checkpoint delivers; compute receives the amended depcfg.

        The authored dep declares ``ref: main``; the fake tool forces
        ``usages.libs.click.ref`` to ``amended-ref`` — the dep handed to
        ``compute_dep_status`` carries the effective ref, and the summary line
        lands on stderr while stdout stays the data-clean surface.
        """
        _write_config(tmp_path)
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_pinref": ["goga-tool-pinref"]})
        install_tool_package("goga_tool_pinref", register_hooks=_register_pinref)

        with mock.patch.object(_status_mod, "compute_dep_status", side_effect=_up_to_date) as compute_mock:
            report = status()

        assert report.exit_code == 0
        compute_mock.assert_called_once()
        amended_depcfg = compute_mock.call_args[0][2]
        assert amended_depcfg.git == "https://x/click.git"
        assert amended_depcfg.ref == "amended-ref"
        captured = capsys.readouterr()
        assert "- pinref forced usages.libs.click.ref" in captured.err
        assert captured.out == ""

    def test_status_command_uniform_reach(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Baseline vs amended run: same stdout, same exit code, stderr summary.

        One run without tools (the baseline) and one with the amending tool:
        the report renders identically (the dep is up to date either way), the
        summary line appears on stderr only, and the exit code is unchanged.
        """
        _write_config(tmp_path)
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        with mock.patch.object(_status_mod, "compute_dep_status", side_effect=_up_to_date) as compute_mock:
            baseline = runner.invoke(app, ["usages", "status"])
            baseline_ref = compute_mock.call_args[0][2].ref

            pin_package_environment({"goga_tool_pinref": ["goga-tool-pinref"]})
            install_tool_package("goga_tool_pinref", register_hooks=_register_pinref)

            amended = runner.invoke(app, ["usages", "status"])
            amended_ref = compute_mock.call_args[0][2].ref

        assert baseline_ref == "main"
        assert amended_ref == "amended-ref"
        assert amended.exit_code == 0, amended.output
        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert "- pinref forced usages.libs.click.ref" in amended.stderr
        assert "- pinref forced usages.libs.click.ref" not in amended.stdout

    def test_status_checkpoint_hard_failure_is_clean_error(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the command: exit 1, pinned message, no compute."""

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("config", "amend_config", "exploding", boom)  # type: ignore[attr-defined]

        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_pinref": ["goga-tool-pinref"]})
        install_tool_package("goga_tool_pinref", register_hooks=register)

        with mock.patch.object(_status_mod, "compute_dep_status") as compute_mock:
            result = CliRunner().invoke(app, ["usages", "status"])

        assert result.exit_code == 1
        assert "failed on config.amend_config" in result.output
        assert "Traceback" not in result.output
        compute_mock.assert_not_called()
