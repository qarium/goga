"""Tests for ``install_flows``: recreating ``~/.goga/flows/`` from the internal
goga source and from ``goga_tool_*`` packages, with the
``force_overwrite`` conflict policy."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from unittest import mock

import pytest
from goga.connect import install_flows

_install_flows_mod = importlib.import_module("goga.connect.install_flows")


def _make_internal_flows(root: Path, files: dict[str, str]) -> Path:
    """Create a ``<root>/flows/`` directory with the given ``*.yml`` files."""
    flows = root / "flows"
    flows.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (flows / name).write_text(content)
    return flows


def _make_tool_spec(parent: Path, pkg_name: str, files: dict[str, str]) -> mock.MagicMock:
    """Create a ``goga_tool_*`` package layout and return a stub importlib spec."""
    pkg_dir = parent / pkg_name
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    if files:
        flows_dir = pkg_dir / "flows"
        flows_dir.mkdir()
        for name, content in files.items():
            (flows_dir / name).write_text(content)
    spec = mock.MagicMock()
    spec.origin = str(pkg_dir / "__init__.py")
    return spec


def _patch_discovery(
    monkeypatch,
    internal_flows_dir: Path,
    packages: dict[str, list[str]] | None = None,
    specs: dict[str, mock.MagicMock] | None = None,
) -> None:
    """Redirect internal-source resolution and package discovery at the module."""
    monkeypatch.setattr(
        _install_flows_mod, "_get_internal_flows_dir", lambda: internal_flows_dir
    )
    monkeypatch.setattr(
        _install_flows_mod.importlib.metadata,
        "packages_distributions",
        lambda: packages or {},
    )

    def find_spec(name: str):
        if specs and name in specs:
            return specs[name]
        return None

    monkeypatch.setattr(_install_flows_mod.importlib.util, "find_spec", find_spec)


class TestInstallFlowsContract:
    def test_install_flows_importable_from_facade(self) -> None:
        """install_flows is importable from the goga.connect facade."""
        assert install_flows is not None

    def test_install_flows_signature_matches_contract(self) -> None:
        """install_flows exposes the (flows_dir, force_overwrite=False) signature."""
        signature = inspect.signature(install_flows)
        parameters = list(signature.parameters)

        assert parameters == ["flows_dir", "force_overwrite"]
        assert signature.parameters["force_overwrite"].default is False

    def test_install_flows_returns_int(self, tmp_path: Path, monkeypatch) -> None:
        """install_flows returns an int exit code."""
        flows_dir = tmp_path / "flows_target"
        _patch_discovery(monkeypatch, tmp_path / "does_not_exist")

        exit_code = install_flows(flows_dir)

        assert isinstance(exit_code, int)


class TestInstallFlowsLogic:
    def test_install_flows_handles_missing_internal_source(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A missing internal source and no tool packages is a clean no-op success."""
        flows_dir = tmp_path / "flows_target"
        _patch_discovery(monkeypatch, tmp_path / "does_not_exist")

        exit_code = install_flows(flows_dir)

        assert exit_code == 0
        assert flows_dir.is_dir()

    def test_install_flows_recreates_dirty_directory(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A pre-existing stale flow is removed when the directory is recreated."""
        flows_dir = tmp_path / "flows_target"
        flows_dir.mkdir(parents=True)
        (flows_dir / "stale_flow.yml").write_text("stale")
        _patch_discovery(monkeypatch, tmp_path / "does_not_exist")

        exit_code = install_flows(flows_dir)

        assert exit_code == 0
        assert not (flows_dir / "stale_flow.yml").exists()

    def test_install_flows_internal_wins_on_conflict_by_default(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """By default the internal-source flow wins on a name conflict."""
        flows_dir = tmp_path / "flows_target"
        internal_flows = _make_internal_flows(
            tmp_path / "internal", {"conflict.yml": "internal"}
        )
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"conflict.yml": "tool"})
        _patch_discovery(
            monkeypatch,
            internal_flows,
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_flows(flows_dir, force_overwrite=False)

        assert exit_code == 0
        assert (flows_dir / "conflict.yml").read_text() == "internal"

    def test_install_flows_tools_overwrite_on_conflict_with_force(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """With force_overwrite the tool flow wins on a name conflict."""
        flows_dir = tmp_path / "flows_target"
        internal_flows = _make_internal_flows(
            tmp_path / "internal", {"conflict.yml": "internal"}
        )
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"conflict.yml": "tool"})
        _patch_discovery(
            monkeypatch,
            internal_flows,
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_flows(flows_dir, force_overwrite=True)

        assert exit_code == 0
        assert (flows_dir / "conflict.yml").read_text() == "tool"

    def test_install_flows_copies_internal_flows(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Internal-source flows are copied into the recreated directory."""
        flows_dir = tmp_path / "flows_target"
        internal_flows = _make_internal_flows(
            tmp_path / "internal",
            {"deploy.yml": "internal deploy", "build.yml": "internal build"},
        )
        _patch_discovery(monkeypatch, internal_flows)

        exit_code = install_flows(flows_dir)

        assert exit_code == 0
        assert (flows_dir / "deploy.yml").read_text() == "internal deploy"
        assert (flows_dir / "build.yml").read_text() == "internal build"

    def test_install_flows_copies_tool_flows_when_no_conflict(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A tool flow with a unique name is copied without a warning."""
        flows_dir = tmp_path / "flows_target"
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"unique.yml": "tool unique"})
        _patch_discovery(
            monkeypatch,
            tmp_path / "does_not_exist",
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_flows(flows_dir)

        assert exit_code == 0
        assert (flows_dir / "unique.yml").read_text() == "tool unique"

    def test_install_flows_skips_package_without_flows_dir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A goga_tool_* package without a flows/ directory is skipped silently."""
        flows_dir = tmp_path / "flows_target"
        spec = _make_tool_spec(tmp_path, "goga_tool_X", files={})
        _patch_discovery(
            monkeypatch,
            tmp_path / "does_not_exist",
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_flows(flows_dir)

        assert exit_code == 0
        assert list(flows_dir.glob("*.yml")) == []

    def test_install_flows_warns_on_skipped_conflict(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A skipped conflict logs a warning to stderr."""
        flows_dir = tmp_path / "flows_target"
        internal_flows = _make_internal_flows(
            tmp_path / "internal", {"conflict.yml": "internal"}
        )
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"conflict.yml": "tool"})
        _patch_discovery(
            monkeypatch,
            internal_flows,
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        install_flows(flows_dir, force_overwrite=False)

        captured = capsys.readouterr()
        assert "conflict.yml" in captured.err
        assert "already exists" in captured.err

    def test_install_flows_returns_nonzero_on_copy_error(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """An OSError during copying makes install_flows return 1 with a message."""
        flows_dir = tmp_path / "flows_target"
        internal_flows = _make_internal_flows(
            tmp_path / "internal", {"deploy.yml": "deploy"}
        )
        _patch_discovery(monkeypatch, internal_flows)

        def raise_oserror(*args, **kwargs):
            raise OSError("copy boom")

        monkeypatch.setattr(_install_flows_mod.shutil, "copy2", raise_oserror)

        exit_code = install_flows(flows_dir)

        assert exit_code == 1
