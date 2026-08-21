"""Tests for ``install_pipelines``: recreating ``~/.goga/pipelines/`` from the internal
goga source and from ``goga_tool_*`` packages. Tool pipelines are namespaced under
their tool (``<tool>:<name>.yml``); ``force_overwrite`` governs residual namespaced
conflicts."""

from __future__ import annotations

import importlib
import inspect
import shutil
from pathlib import Path
from unittest import mock

import pytest
from goga.connect import install_pipelines

_install_pipelines_mod = importlib.import_module("goga.connect.install_pipelines")


def _make_internal_pipelines(root: Path, files: dict[str, str]) -> Path:
    """Create a ``<root>/pipelines/`` directory with the given ``*.yml`` files."""
    pipelines = root / "pipelines"
    pipelines.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (pipelines / name).write_text(content)
    return pipelines


def _make_tool_spec(parent: Path, pkg_name: str, files: dict[str, str]) -> mock.MagicMock:
    """Create a ``goga_tool_*`` package layout and return a stub importlib spec."""
    pkg_dir = parent / pkg_name
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    if files:
        pipelines_dir = pkg_dir / "pipelines"
        pipelines_dir.mkdir()
        for name, content in files.items():
            (pipelines_dir / name).write_text(content)
    spec = mock.MagicMock()
    spec.origin = str(pkg_dir / "__init__.py")
    return spec


def _patch_discovery(
    monkeypatch,
    internal_pipelines_dir: Path,
    packages: dict[str, list[str]] | None = None,
    specs: dict[str, mock.MagicMock] | None = None,
) -> None:
    """Redirect internal-source resolution and package discovery at the module."""
    monkeypatch.setattr(_install_pipelines_mod, "_get_internal_pipelines_dir", lambda: internal_pipelines_dir)
    monkeypatch.setattr(
        _install_pipelines_mod.importlib.metadata,
        "packages_distributions",
        lambda: packages or {},
    )

    def find_spec(name: str):
        if specs and name in specs:
            return specs[name]
        return None

    monkeypatch.setattr(_install_pipelines_mod.importlib.util, "find_spec", find_spec)


class TestInstallPipelinesContract:
    def test_install_pipelines_importable_from_facade(self) -> None:
        """install_pipelines is importable from the goga.connect facade."""
        assert install_pipelines is not None

    def test_install_pipelines_signature_matches_contract(self) -> None:
        """install_pipelines exposes the (pipelines_dir, force_overwrite=False) signature."""
        signature = inspect.signature(install_pipelines)
        parameters = list(signature.parameters)

        assert parameters == ["pipelines_dir", "force_overwrite"]
        assert signature.parameters["force_overwrite"].default is False

    def test_install_pipelines_returns_int(self, tmp_path: Path, monkeypatch) -> None:
        """install_pipelines returns 0 on a clean no-op install."""
        pipelines_dir = tmp_path / "pipelines_target"
        _patch_discovery(monkeypatch, tmp_path / "does_not_exist")

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0


class TestGetInternalPipelinesDir:
    def test_returns_path_to_pipelines_under_assets(self) -> None:
        """_get_internal_pipelines_dir resolves to the relocated ``assets/pipelines`` dir.

        Regression guard against an accidental revert to the legacy ``flows/``
        location; mirrors ``TestGetSourceDir`` for the pipelines-specific resolver.
        """
        source = _install_pipelines_mod._get_internal_pipelines_dir()
        assert source.name == "pipelines"
        assert source.parent.name == "assets"
        # the relocated internal source is a real directory shipped with the package
        assert source.is_dir()


class TestInstallPipelinesLogic:
    def test_install_pipelines_handles_missing_internal_source(self, tmp_path: Path, monkeypatch) -> None:
        """A missing internal source and no tool packages is a clean no-op success."""
        pipelines_dir = tmp_path / "pipelines_target"
        _patch_discovery(monkeypatch, tmp_path / "does_not_exist")

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert pipelines_dir.is_dir()

    def test_install_pipelines_recreates_dirty_directory(self, tmp_path: Path, monkeypatch) -> None:
        """A pre-existing stale pipeline is removed when the directory is recreated."""
        pipelines_dir = tmp_path / "pipelines_target"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "stale_pipeline.yml").write_text("stale")
        _patch_discovery(monkeypatch, tmp_path / "does_not_exist")

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert not (pipelines_dir / "stale_pipeline.yml").exists()

    def test_install_pipelines_tool_and_internal_same_name_coexist(self, tmp_path: Path, monkeypatch) -> None:
        """Namespacing lets a tool pipeline and an internal pipeline with the same
        base name coexist — no conflict, no skip."""
        pipelines_dir = tmp_path / "pipelines_target"
        internal_pipelines = _make_internal_pipelines(tmp_path / "internal", {"conflict.yml": "internal"})
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"conflict.yml": "tool"})
        _patch_discovery(
            monkeypatch,
            internal_pipelines,
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_pipelines(pipelines_dir, force_overwrite=False)

        assert exit_code == 0
        # Internal pipeline stays un-prefixed; tool pipeline is namespaced under its tool.
        assert (pipelines_dir / "conflict.yml").read_text() == "internal"
        assert (pipelines_dir / "X:conflict.yml").read_text() == "tool"

    def test_install_pipelines_namespaced_conflict_skipped_by_default(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A residual namespaced conflict (a destination ``<tool>:<name>.yml`` that
        already exists) is skipped with a warning unless ``force_overwrite`` is set.

        Here the internal source ships a colon-prefixed ``X:unique.yml`` so the
        tool ``goga_tool_X`` pipeline ``unique.yml`` lands on the same namespaced
        path — the only way a collision can still occur after tool namespacing.
        """
        pipelines_dir = tmp_path / "pipelines_target"
        internal_pipelines = _make_internal_pipelines(tmp_path / "internal", {"X:unique.yml": "internal"})
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"unique.yml": "tool"})
        _patch_discovery(
            monkeypatch,
            internal_pipelines,
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_pipelines(pipelines_dir, force_overwrite=False)

        assert exit_code == 0
        # Existing namespaced pipeline is preserved; the tool's file is skipped.
        assert (pipelines_dir / "X:unique.yml").read_text() == "internal"
        captured = capsys.readouterr()
        assert "X:unique.yml" in captured.err
        assert "already exists" in captured.err

    def test_install_pipelines_namespaced_conflict_overwritten_with_force(self, tmp_path: Path, monkeypatch) -> None:
        """With ``force_overwrite`` a residual namespaced conflict lets the tool
        pipeline overwrite the existing file."""
        pipelines_dir = tmp_path / "pipelines_target"
        internal_pipelines = _make_internal_pipelines(tmp_path / "internal", {"X:unique.yml": "internal"})
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"unique.yml": "tool"})
        _patch_discovery(
            monkeypatch,
            internal_pipelines,
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_pipelines(pipelines_dir, force_overwrite=True)

        assert exit_code == 0
        assert (pipelines_dir / "X:unique.yml").read_text() == "tool"

    def test_install_pipelines_copies_internal_pipelines(self, tmp_path: Path, monkeypatch) -> None:
        """Internal-source pipelines are copied into the recreated directory."""
        pipelines_dir = tmp_path / "pipelines_target"
        internal_pipelines = _make_internal_pipelines(
            tmp_path / "internal",
            {"deploy.yml": "internal deploy", "build.yml": "internal build"},
        )
        _patch_discovery(monkeypatch, internal_pipelines)

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert (pipelines_dir / "deploy.yml").read_text() == "internal deploy"
        assert (pipelines_dir / "build.yml").read_text() == "internal build"

    def test_install_pipelines_copies_tool_pipelines_namespaced(self, tmp_path: Path, monkeypatch) -> None:
        """A tool pipeline is copied namespaced as ``<tool>:<name>.yml``."""
        pipelines_dir = tmp_path / "pipelines_target"
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"unique.yml": "tool unique"})
        _patch_discovery(
            monkeypatch,
            tmp_path / "does_not_exist",
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert (pipelines_dir / "X:unique.yml").read_text() == "tool unique"
        # The un-prefixed name must NOT exist (the whole point of namespacing).
        assert not (pipelines_dir / "unique.yml").exists()

    def test_install_pipelines_namespaces_multisegment_tool_name(self, tmp_path: Path, monkeypatch) -> None:
        """A multi-segment tool name (``goga_tool_my_tool``) is normalized to hyphens in
        the ``my-tool:<name>.yml`` prefix, matching the canonical hyphenated tool/package
        name (``goga-tool-my-tool``)."""
        pipelines_dir = tmp_path / "pipelines_target"
        spec = _make_tool_spec(tmp_path, "goga_tool_my_tool", {"foo.yml": "tool foo"})
        _patch_discovery(
            monkeypatch,
            tmp_path / "does_not_exist",
            packages={"goga_tool_my_tool": ["goga-tool-my-tool"]},
            specs={"goga_tool_my_tool": spec},
        )

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert (pipelines_dir / "my-tool:foo.yml").read_text() == "tool foo"
        # The underscored prefix must NOT exist (normalization replaces _ with -).
        assert not (pipelines_dir / "my_tool:foo.yml").exists()

    def test_install_pipelines_two_tools_same_pipeline_name_no_collision(self, tmp_path: Path, monkeypatch) -> None:
        """Two tools shipping the same pipeline name install side by side under their
        own prefixes — the headline benefit of namespacing."""
        pipelines_dir = tmp_path / "pipelines_target"
        spec_a = _make_tool_spec(tmp_path, "goga_tool_a", {"deploy.yml": "from a"})
        spec_b = _make_tool_spec(tmp_path, "goga_tool_b", {"deploy.yml": "from b"})
        _patch_discovery(
            monkeypatch,
            tmp_path / "does_not_exist",
            packages={"goga_tool_a": ["goga_tool_a"], "goga_tool_b": ["goga_tool_b"]},
            specs={"goga_tool_a": spec_a, "goga_tool_b": spec_b},
        )

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert (pipelines_dir / "a:deploy.yml").read_text() == "from a"
        assert (pipelines_dir / "b:deploy.yml").read_text() == "from b"

    def test_install_pipelines_skips_package_without_pipelines_dir(self, tmp_path: Path, monkeypatch) -> None:
        """A goga_tool_* package without a pipelines/ directory is skipped silently."""
        pipelines_dir = tmp_path / "pipelines_target"
        spec = _make_tool_spec(tmp_path, "goga_tool_X", files={})
        _patch_discovery(
            monkeypatch,
            tmp_path / "does_not_exist",
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert list(pipelines_dir.glob("*.yml")) == []

    def test_install_pipelines_no_warning_when_namespacing_resolves_base_name(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A tool pipeline whose base name matches an internal pipeline is NOT a
        conflict after namespacing — no warning is emitted."""
        pipelines_dir = tmp_path / "pipelines_target"
        internal_pipelines = _make_internal_pipelines(tmp_path / "internal", {"conflict.yml": "internal"})
        spec = _make_tool_spec(tmp_path, "goga_tool_X", {"conflict.yml": "tool"})
        _patch_discovery(
            monkeypatch,
            internal_pipelines,
            packages={"goga_tool_X": ["goga_tool_X"]},
            specs={"goga_tool_X": spec},
        )

        install_pipelines(pipelines_dir, force_overwrite=False)

        captured = capsys.readouterr()
        assert "already exists" not in captured.err

    def test_install_pipelines_returns_nonzero_on_copy_error(self, tmp_path: Path, monkeypatch) -> None:
        """An OSError during copying makes install_pipelines return 1 with a message."""
        pipelines_dir = tmp_path / "pipelines_target"
        internal_pipelines = _make_internal_pipelines(tmp_path / "internal", {"deploy.yml": "deploy"})
        _patch_discovery(monkeypatch, internal_pipelines)

        def raise_oserror(*args, **kwargs):
            raise OSError("copy boom")

        monkeypatch.setattr(_install_pipelines_mod.shutil, "copy2", raise_oserror)

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 1

    def test_install_pipelines_returns_nonzero_on_shutil_error(self, tmp_path: Path, monkeypatch) -> None:
        """A shutil.Error during copying is caught and surfaces as exit 1.

        Guards the ``(OSError, shutil.Error)`` union: the ``shutil.Error`` arm
        must independently map to 1, not just ``OSError``.
        """
        pipelines_dir = tmp_path / "pipelines_target"
        internal_pipelines = _make_internal_pipelines(tmp_path / "internal", {"deploy.yml": "deploy"})
        _patch_discovery(monkeypatch, internal_pipelines)

        def raise_shutil_error(*args, **kwargs):
            raise shutil.Error("copy boom")

        monkeypatch.setattr(_install_pipelines_mod.shutil, "copy2", raise_shutil_error)

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 1

    def test_install_pipelines_returns_nonzero_on_rmtree_error(self, tmp_path: Path, monkeypatch) -> None:
        """An OSError during the initial rmtree (recreate) surfaces as exit 1.

        Guards that the destructive recreate stays inside the try/except: a
        permission error on rmtree must return 1 rather than raising.
        """
        pipelines_dir = tmp_path / "pipelines_target"
        _patch_discovery(monkeypatch, tmp_path / "does_not_exist")

        def raise_oserror(*args, **kwargs):
            raise OSError("rmtree boom")

        monkeypatch.setattr(_install_pipelines_mod.shutil, "rmtree", raise_oserror)

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 1

    def test_install_pipelines_copies_real_shipped_example_pipelines(self, tmp_path: Path, monkeypatch) -> None:
        """The shipped ``goga/assets/pipelines/*.yml`` examples are installed verbatim.

        Unlike the other cases the internal-source resolver is NOT patched, so
        this exercises the real packaged assets. A packaging break (an example
        fixture deleted or the package-data glob broken) fails this test. The
        shipped example is the goga DSL fixture ``development.yml``. Tool-package
        discovery is stubbed to an empty set to keep the test hermetic.
        """
        pipelines_dir = tmp_path / "pipelines"
        monkeypatch.setattr(
            _install_pipelines_mod.importlib.metadata,
            "packages_distributions",
            lambda: {},
        )

        exit_code = install_pipelines(pipelines_dir)

        assert exit_code == 0
        assert (pipelines_dir / "development.yml").is_file()
        # The installed content is byte-identical to the shipped asset (verbatim copy).
        internal_dir = _install_pipelines_mod._get_internal_pipelines_dir()
        assert (pipelines_dir / "development.yml").read_bytes() == (internal_dir / "development.yml").read_bytes()
