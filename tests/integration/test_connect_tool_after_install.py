from __future__ import annotations

import importlib
import inspect
import os
from pathlib import Path
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner
from goga.cli import app
from goga.connect import resync_registered_agents

# Real module handles — the cross-cell boundary is exercised for real. Only pip
# (``subprocess.run``) and the leaf ``connect`` symbol are mocked per-test.
_connect_module = importlib.import_module("goga.connect.connect")
_install_module = importlib.import_module("goga.commands.install.install")
_upgrade_module = importlib.import_module("goga.commands.upgrade.upgrade")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


def _write_registry(goga_home: Path, agents: dict[str, dict[str, bool]]) -> None:
    goga_home.mkdir(parents=True, exist_ok=True)
    (goga_home / "connect.yml").write_text(yaml.dump({"agents": agents}))


class TestFacadeWiringIntegration:
    """Cross-cell facade wiring — the routine is re-exported and consumed by all three cells.

    Pins the contract that ``resync_registered_agents`` lives in exactly one place
    (the ``goga.connect`` facade) and that install and upgrade reach it through that
    facade rather than a private copy, so behaviour cannot drift between callers.
    """

    def test_resync_registered_agents_importable_from_connect_facade(self) -> None:
        assert callable(resync_registered_agents)

    def test_resync_registered_agents_in_connect_all(self) -> None:
        facade = importlib.import_module("goga.connect")
        assert "resync_registered_agents" in facade.__all__

    def test_install_facade_surface_unchanged(self) -> None:
        facade = importlib.import_module("goga.commands.install")
        assert facade.__all__ == ["install"]

    def test_upgrade_facade_surface_unchanged(self) -> None:
        facade = importlib.import_module("goga.commands.upgrade")
        assert facade.__all__ == ["upgrade"]

    def test_install_and_upgrade_reference_same_routine(self) -> None:
        # Same object reached through the facade — not a private copy — so the
        # three cells share one activation entrypoint.
        assert _install_module.resync_registered_agents is resync_registered_agents
        assert _upgrade_module.resync_registered_agents is resync_registered_agents


class TestInstallToRoutineIntegration:
    """End-to-end install -> routine -> connect across the install/connect cell boundary.

    The install-module boundary is NOT mocked: the real ``resync_registered_agents``
    runs and invokes the real ``connect`` symbol of ``goga.connect.connect``. Only pip
    (``subprocess.run``) and the leaf ``connect`` are mocked, so the cross-cell wiring
    (import + invocation + per-agent ``force_overwrite`` forwarding + single-writer) is
    exercised for real.
    """

    def test_install_runs_real_routine_and_forwards_per_agent_force(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(goga_home, {"claude": {"force_overwrite": False}})
        before = (goga_home / "connect.yml").read_text()
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_connect_module, "connect", return_value=0) as mock_connect,
        ):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 0
        # The real routine ran (pip succeeded, no_connect is False) and forwarded the
        # agent's recorded force_overwrite — never a hardcoded value.
        mock_connect.assert_called_once_with(agents=["claude"], force_overwrite=False)
        # Single-writer invariant: install never writes connect.yml (byte-identical).
        assert (goga_home / "connect.yml").read_text() == before


class TestUpgradeToRoutineIntegration:
    """End-to-end upgrade -> routine -> connect across the upgrade/connect cell boundary.

    Same discipline as the install flow: the upgrade boundary is real, only pip and the
    leaf ``connect`` are mocked, so the delegated re-sync is exercised for real.
    """

    def test_upgrade_runs_real_routine_and_forwards_per_agent_force(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(goga_home, {"claude": {"force_overwrite": True}})
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_connect_module, "connect", return_value=0) as mock_connect,
        ):
            result = CliRunner().invoke(app, ["upgrade"])
        assert result.exit_code == 0
        # The real routine ran and forwarded the agent's recorded force_overwrite=True —
        # delegation through resync_registered_agents is confirmed end-to-end.
        mock_connect.assert_called_once_with(agents=["claude"], force_overwrite=True)


class TestHomeRedirectIntegration:
    """D1 end-to-end: ``$HOME`` redirected to the owning home during re-sync, restored after.

    Drives the real routine through an upgrade ``--user`` invocation: the target user's
    home differs from ``$HOME``, and the routine must temporarily point ``$HOME`` there so
    ``connect``'s ``Path.home()`` targets the owning installation, then restore ``$HOME``.
    """

    def test_upgrade_user_redirects_home_to_target_during_resync(self, tmp_path: Path) -> None:
        owner_home = tmp_path / "owner"
        goga_home = owner_home / ".goga"
        _write_registry(goga_home, {"claude": {"force_overwrite": False}})
        original_home = os.environ.get("HOME")

        seen: dict[str, object] = {}

        def fake_connect(agents: list[str], force_overwrite: bool = False) -> int:
            seen["home"] = Path.home()
            return 0

        pw = mock.MagicMock()
        pw.pw_dir = str(owner_home)
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module.pwd, "getpwnam", return_value=pw),
            mock.patch.object(_connect_module, "connect", new=fake_connect),
        ):
            result = CliRunner().invoke(app, ["upgrade", "--user", "alice"])
        assert result.exit_code == 0
        # The redirect was actually exercised: the owning home is not the current $HOME.
        assert owner_home != original_home
        # D1: ``$HOME`` pointed at the owning home while connect ran (Path.home() reads
        # $HOME), so the re-sync targets the target user's installation.
        assert seen["home"] == owner_home
        # ``$HOME`` restored to its pre-call value even on the happy path.
        assert os.environ.get("HOME") == original_home


class TestSingleWriterInvariant:
    """Single-writer invariant: only ``connect`` (via ``_write_connect_registry``) writes connect.yml.

    install, upgrade, and ``resync_registered_agents`` must never write the registry
    directly. Verified statically against each module's source — the behavioural
    ``connect.yml``-not-rewritten assertions live in the flow tests above.
    """

    def test_resync_routine_does_not_write_registry(self) -> None:
        source = inspect.getsource(resync_registered_agents)
        # The routine reads the registry but must never write it.
        assert "_write_connect_registry" not in source
        assert "write_text" not in source
        assert "write_bytes" not in source

    def test_install_does_not_write_registry_directly(self) -> None:
        source = inspect.getsource(_install_module)
        # install reaches the registry only through resync_registered_agents (read-only).
        assert "_write_connect_registry" not in source

    def test_upgrade_does_not_write_registry_directly(self) -> None:
        source = inspect.getsource(_upgrade_module)
        assert "_write_connect_registry" not in source

    def test_connect_is_the_single_writer_of_registry(self) -> None:
        source = inspect.getsource(_connect_module)
        # connect owns the only writer of connect.yml.
        assert "_write_connect_registry" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
