from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands.install import hook as hook_module

_install_module = importlib.import_module("goga.commands.install.install")
_uninstall_module = importlib.import_module("goga.commands.install.uninstall")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


def _write_config(tmp_path: Path, body: str) -> Path:
    """Write ``.goga/config.yml`` under ``tmp_path`` and return its path."""
    config_dir = tmp_path / ".goga"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yml"
    config_file.write_text(body)
    return config_file


def _pkgs_from_argv(argv: list[str]) -> list[str]:
    """Slice the package identifiers out of a composed pip argv (between the
    ``install`` subcommand and the trailing ``-U``)."""
    return argv[argv.index("install") + 1 : -1]


class TestInstallCliIntegration:
    """End-to-end CLI tests for ``goga install``.

    Drive the root Click group via ``CliRunner`` so they exercise the full
    Cell 3 (``goga/cli.py``) -> Cell 1 (``goga/commands/install/install.py``)
    wiring: click group dispatch, option parsing (``--sudo`` / ``--version``),
    argv composition, and exit-code propagation through ``ctx.exit``. The pip
    boundary is mocked so no real ``subprocess.run`` happens.
    """

    def test_install_cli_help_lists_options(self) -> None:
        """``goga install --help`` exits 0 and lists both options and the NAME argument."""
        result = CliRunner().invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "--sudo" in result.output
        assert "--version" in result.output
        # Click uppercases the argument metavar (NAME) in the usage line and
        # emits an ``Arguments:`` section; either marker confirms the required
        # positional argument is declared.
        assert "NAME" in result.output.upper() or "Arguments" in result.output

    def test_install_cli_plain_dispatch(self) -> None:
        """``goga install foo`` composes the canonical argv and exits with pip's returncode."""
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv == [sys.executable, "-m", "pip", "install", "goga-tool-foo", "-U"]

    def test_install_cli_with_sudo_and_version(self) -> None:
        """``goga install foo --sudo --version 1.2.3`` prefixes sudo and grammar-resolves the version."""
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--sudo", "--version", "1.2.3"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]
        assert "goga-tool-foo==1.2.3" in argv

    def test_install_cli_propagates_pip_failure(self) -> None:
        """A non-zero pip returncode propagates through ``ctx.exit`` (no CalledProcessError)."""
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 1


class TestUninstallCliIntegration:
    """End-to-end CLI tests for ``goga uninstall``.

    Drive the root Click group via ``CliRunner`` so they exercise the full
    wiring: root group (``goga/cli.py``) -> commands facade
    (``goga/commands/__init__.py``) -> cell facade -> ``uninstall.py``
    command. The pip and re-sync boundaries are mocked so no real
    ``subprocess.run`` happens and no agent directory is touched.
    """

    def test_uninstall_cli_dispatch(self) -> None:
        """``goga uninstall foo --yes`` composes the canonical argv and exits 0."""
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--yes"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv == [sys.executable, "-m", "pip", "uninstall", "-y", "goga-tool-foo"]

    def test_uninstall_cli_help_lists_options(self) -> None:
        """``goga uninstall --help`` exits 0 and lists the options and the NAME argument."""
        result = CliRunner().invoke(app, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "--sudo" in result.output
        assert "-y" in result.output
        assert "--user" in result.output
        assert "NAME" in result.output.upper()

    def test_uninstall_cli_propagates_pip_failure(self) -> None:
        """A non-zero pip returncode propagates through ``ctx.exit``, skipping the re-sync."""
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result(1)),
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--yes"])
        assert result.exit_code == 1
        mock_resync.assert_not_called()


class TestInstallEndToEndPaths:
    """End-to-end paths exercising cross-entity wiring (install -> resolve_version
    -> load_project_config -> subprocess.run) plus regressions the bulk/empty rewrite
    introduces: optional ``name``, no ``~/.goga`` writes, and empty-path isolation
    from ``--sudo``. The pip boundary is mocked so no real install runs and the
    real home dir (redirected to ``tmp_path/.pytest_home`` by the autouse
    ``_isolate_home`` fixture) is observable for side-effect assertions.
    """

    def test_install_no_name_runs_bulk_or_empty_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: ``goga install`` without NAME no longer parse-errors.

        Previously ``name`` was a required argument, so ``["install"]`` exited 2
        with Click's "Missing argument" usage error. With ``name`` optional the
        empty path runs instead: a config without ``tools:`` prints
        ``Nothing to install`` and exits 0 without invoking pip.
        """
        _write_config(tmp_path, "language: python\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        # Exit 0 (empty path), not 2 (Click usage error).
        assert result.exit_code == 0
        assert result.output.strip() == "Nothing to install"
        mock_run.assert_not_called()

    def test_install_single_path_empty_name_propagates_to_pip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``goga install ""`` drives the SINGLE path with ``pkg = "goga-tool-"``.

        An empty string is not ``None``, so Click dispatches it as a name: the
        version resolves to ``None`` (no specifier) and pip is handed the bare
        ``goga-tool-`` identifier. pip's non-zero returncode propagates as-is.
        """
        # An empty string must be passed verbatim through the shell-free CliRunner.
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)) as mock_run:
            result = CliRunner().invoke(app, ["install", ""])
        assert result.exit_code == 1
        assert mock_run.call_count == 1
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["goga-tool-"]

    def test_install_no_resync_does_not_touch_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Single-path install writes nothing under ``~/.goga``.

        The install command installs a tool via pip; it never runs the
        connect/resync step that materializes ``~/.goga``. ``_isolate_home``
        redirects HOME to ``tmp_path/.pytest_home``, so the absence of a
        ``.goga`` directory there proves no home writes occurred.
        """
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()):
            CliRunner().invoke(app, ["install", "foo"])
        assert not (tmp_path / ".pytest_home" / ".goga").exists()

    def test_install_does_not_read_connect_yml_in_bulk_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bulk-path install does not create ``~/.goga/connect.yml``.

        Resolving ``cfg.tools`` and invoking pip must not trigger the connect
        step that writes ``connect.yml``. After a bulk install no such file
        exists under the isolated home.
        """
        _write_config(tmp_path, "language: python\ntools:\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()):
            CliRunner().invoke(app, ["install"])
        assert not (tmp_path / ".pytest_home" / ".goga" / "connect.yml").exists()

    def test_install_bulk_path_full_cross_entity_argv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cross-entity: a real ``.goga/config.yml`` drives load_project_config ->
        resolve_version -> one ``subprocess.run`` with composed argv.

        Three tools, three grammar forms (minor x-range, latest, concrete),
        resolved in YAML insertion order into a single pip invocation.
        """
        _write_config(
            tmp_path,
            "language: python\ntools:\n  afm: 1.0.x\n  viewer: latest\n  go: 1.2.3\n",
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        argv = mock_run.call_args[0][0]
        assert argv[:3] == [sys.executable, "-m", "pip"]
        assert argv[3] == "install"
        assert argv[-1] == "-U"
        assert _pkgs_from_argv(argv) == ["goga-tool-afm~=1.0.0", "goga-tool-viewer", "goga-tool-go==1.2.3"]

    def test_install_empty_path_with_sudo_still_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Edge: empty path + ``--sudo`` stays empty — sudo never materializes.

        With no ``tools:`` the empty branch fires before argv composition, so
        ``--sudo`` is never consulted and pip is never invoked.
        """
        _write_config(tmp_path, "language: python\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "--sudo"])
        assert result.exit_code == 0
        assert result.output.strip() == "Nothing to install"
        mock_run.assert_not_called()


class TestInstallHookFlowIntegration:
    """Cross-entity: the real hook routines through the real ``install`` command.

    Only the process boundary is mocked (pip subprocess, the dynamic
    ``goga_tool_<tool>`` facade import, the agent re-sync), so these tests
    verify the wiring the unit tests mock away: the ``from .hook import`` path
    inside ``install.py``, the per-path hook-target lists, the
    pip -> hooks -> re-sync order, and the failure containment of the design's
    Flows B (single mode, sudo) and C (bulk hook failure).

    The hook-fake construction rule applies: every fake facade is a
    ``types.SimpleNamespace`` carrying a REAL recorder function declaring its
    parameters — a bare MagicMock has no declared ``user`` parameter and the
    signature projection would bare-call it.
    """

    def test_install_hook_flow_b_sudo_user_reaches_hook_in_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Flow B: pip -> hook -> re-sync, the hook seeing the REAL person.

        sudo ran and recorded the caller in ``SUDO_USER`` — the hook must
        receive ``alice``, the actual person, not the root account the
        installer may run under.
        """
        monkeypatch.setenv("SUDO_USER", "alice")
        order: list[str] = []
        recorder: list[dict[str, str | None]] = []

        def _viewer_install(user: str | None = None) -> None:
            order.append("hook")
            recorder.append({"user": user})

        def _pip(_argv: list[str], **_kwargs: object) -> mock.MagicMock:
            order.append("pip")
            return _pip_result()

        def _resync(_home: Path) -> int:
            order.append("resync")
            return 0

        def _import(name: str) -> types.SimpleNamespace:
            if name == "goga_tool_viewer":
                return types.SimpleNamespace(install=_viewer_install)
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        with (
            mock.patch.object(_install_module.subprocess, "run", side_effect=_pip) as mock_run,
            mock.patch.object(hook_module.importlib, "import_module", side_effect=_import),
            mock.patch.object(_install_module, "resync_registered_agents", side_effect=_resync) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "viewer"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        mock_resync.assert_called_once()
        # The initiating user is the real person behind the sudo-ed install.
        assert recorder == [{"user": "alice"}]
        assert order == ["pip", "hook", "resync"]

    def test_install_hook_flow_c_bulk_failure_stops_at_first_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Flow C: bulk stops at the first failing hook — no re-sync, no rollback.

        The viewer hook raises; the wrapped RuntimeError carries the tool name
        and hook message out as a user-facing error (exit 1). afm's hook never
        runs, the pip package stays, and the agent re-sync is never reached.
        """
        _write_config(tmp_path, "language: python\ntools:\n  viewer: latest\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SUDO_USER", raising=False)
        calls: list[str] = []

        def _viewer_install(user: str | None = None) -> None:
            calls.append("viewer")
            raise ValueError("boom")

        def _afm_install(user: str | None = None) -> None:
            calls.append("afm")

        def _import(name: str) -> types.SimpleNamespace:
            if name == "goga_tool_viewer":
                return types.SimpleNamespace(install=_viewer_install)
            if name == "goga_tool_afm":
                return types.SimpleNamespace(install=_afm_install)
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(hook_module.getpass, "getuser", return_value="bob"),
            mock.patch.object(hook_module.importlib, "import_module", side_effect=_import),
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install"])

        assert result.exit_code == 1
        assert "install hook for tool 'viewer' failed: boom" in result.output
        # No rollback — exactly one pip install, no uninstall anywhere — and
        # bulk stops at the FIRST failing hook: afm's hook never runs.
        assert mock_run.call_count == 1
        assert calls == ["viewer"]
        mock_resync.assert_not_called()

    def test_install_local_suffix_hook_end_to_end(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Edge: ``--local <path>:<tool>`` — suffix stripped from pip, names the hook.

        The pip argv carries the bare path, the hook target is the suffixed
        tool name, the hook receives the OS user (no ``SUDO_USER``), and the
        activation still runs — the suffix governs only the hook, never the
        re-sync.
        """
        monkeypatch.delenv("SUDO_USER", raising=False)
        recorder: list[dict[str, str | None]] = []

        def _mytool_install(user: str | None = None) -> None:
            recorder.append({"user": user})

        def _import(name: str) -> types.SimpleNamespace:
            if name == "goga_tool_mytool":
                return types.SimpleNamespace(install=_mytool_install)
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(hook_module.getpass, "getuser", return_value="bob"),
            mock.patch.object(hook_module.importlib, "import_module", side_effect=_import),
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./my-tool:mytool"])

        assert result.exit_code == 0
        # The suffix is stripped from the pip target...
        assert mock_run.call_count == 1
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["./my-tool"]
        # ...and names the hook target, which receives the OS user.
        assert recorder == [{"user": "bob"}]
        mock_resync.assert_called_once()
