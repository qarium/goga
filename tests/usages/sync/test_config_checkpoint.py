# tests/usages/sync/test_config_checkpoint.py — the config-amendment checkpoint of sync

from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.usages.sync import sync

# Resolve the inner ``sync.py`` submodule via importlib (the facade function
# shadows the submodule attribute in the package ``__dict__`` — the same
# pattern ``test_sync.py`` documents).
_sync_mod = importlib.import_module("goga.usages.sync.sync")

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


class TestSyncConfigCheckpoint:
    def test_sync_clones_from_the_effective_usages_section(
        self,
        tmp_path: Path,
        monkeypatch,
        capsys,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The checkpoint delivers; the clone receives the amended ref.

        The authored dep declares ``ref: main``; the fake tool forces
        ``usages.libs.click.ref`` to ``amended-ref`` — the clone call carries
        the effective ref, and the summary line lands on stderr while stdout
        stays untouched (sync itself prints nothing; rendering stays with the
        command).
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_pinref": ["goga-tool-pinref"]})
        install_tool_package("goga_tool_pinref", register_hooks=_register_pinref)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        with (
            mock.patch.object(_sync_mod, "clone_repository", return_value=fake_repo) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True)

        assert result == 0
        clone_mock.assert_called_once_with("https://x/click.git", "amended-ref")
        deploy_mock.assert_called_once_with(fake_repo, Path(".goga/usages/libs/click"), None)
        captured = capsys.readouterr()
        assert "- pinref forced usages.libs.click.ref" in captured.err
        assert captured.out == ""

    def test_sync_command_uniform_reach(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Baseline vs amended run: same stdout, same exit code, stderr summary.

        One run without tools (the baseline) and one with the amending tool:
        both clone/deploy the one dep (the only observable difference is the
        ref threaded into the clone), stdout stays identical and empty, and
        the exit code is unchanged.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        with (
            mock.patch.object(_sync_mod, "clone_repository", return_value=fake_repo) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages"),
        ):
            baseline = runner.invoke(app, ["usages", "sync", "--force"])
            baseline_ref = clone_mock.call_args[0][1]

            pin_package_environment({"goga_tool_pinref": ["goga-tool-pinref"]})
            install_tool_package("goga_tool_pinref", register_hooks=_register_pinref)

            amended = runner.invoke(app, ["usages", "sync", "--force"])
            amended_ref = clone_mock.call_args[0][1]

        assert baseline_ref == "main"
        assert amended_ref == "amended-ref"
        assert amended.exit_code == 0, amended.output
        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert "- pinref forced usages.libs.click.ref" in amended.stderr
        assert "- pinref forced usages.libs.click.ref" not in amended.stdout

    def test_sync_checkpoint_hard_failure_is_clean_error(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the command: exit 1, pinned message, no clone.

        The propagated checkpoint ``ValueError`` is converted by the
        ``goga usages`` wrapper into a clean ``ClickException``.
        """

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("config", "amend_config", "exploding", boom)  # type: ignore[attr-defined]

        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_pinref": ["goga-tool-pinref"]})
        install_tool_package("goga_tool_pinref", register_hooks=register)

        with mock.patch.object(_sync_mod, "clone_repository") as clone_mock:
            result = CliRunner().invoke(app, ["usages", "sync"])

        assert result.exit_code == 1
        assert "failed on config.amend_config" in result.output
        assert "Traceback" not in result.output
        clone_mock.assert_not_called()

    def test_sync_keeps_fail_loud_load_contract(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """A missing config.yml still propagates FileNotFoundError (fail-loud)."""
        monkeypatch.chdir(tmp_path)
        pin_package_environment({})

        with pytest.raises(FileNotFoundError):
            sync()
