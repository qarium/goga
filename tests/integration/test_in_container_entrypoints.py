"""Cross-cell integration tests for the in-container entrypoint flow (Task 7).

These stitch together the in-container entrypoint contract across three cells:

    goga/docker/env.py                (leaf — the guard routine ``ensure_in_docker``)
        -> goga/build/__main__.py     (consumer A — shape 1: routine entrypoint)
              ``ensure_in_docker()`` is step 0 of ``main()``; then argparse -> build()
        -> goga/pipeline/__main__.py  (consumer B — shape 2: runpy ``__main__`` guard)
              ``ensure_in_docker()`` is the first statement of the ``__main__`` block;
              then ``sys.exit(pipeline_cli(sys.argv[1:]))``

The tests invoke the real ``python -m goga.build`` / ``python -m goga.pipeline``
entrypoints via :mod:`runpy` (the same path the goga Docker image entrypoint uses)
and let the REAL :func:`ensure_in_docker` guard from :mod:`goga.docker` run — only
the leaf dispatch targets (``build``, ``load_config``, ``pipeline_cli``) are mocked,
to keep the test offline and fast. This verifies the seam that only holds when the
guard is wired into both entrypoints: the docker cell composes with the build and
pipeline cells, and both entrypoints refuse consistently via the SAME guard routine
when the ``GOGA_DOCKER`` marker is absent.

These tests do NOT repeat the per-cell unit coverage in ``tests/docker/``,
``tests/build/``, and ``tests/pipeline/``; they assert the cross-cell composition
end-to-end through the ``python -m <pkg>`` runpy path.

Module-shadowing caveat: ``goga.build.__init__`` re-exports ``build`` (the function),
which shadows the ``goga.build.build`` submodule in attribute access on Python 3.10,
so the real modules are resolved via :data:`sys.modules` and patched by attribute
(per ``[[feedback_mock_patch_module_shadowing]]``).
"""

from __future__ import annotations

import contextlib
import importlib
import runpy
import sys
import warnings
from unittest import mock

import pytest

# Resolve the real submodules via importlib: package ``__init__`` re-exports
# bind the function names (e.g. ``goga.build.build`` -> the ``build`` function),
# which shadow the submodule in attribute access on Python 3.10 — so the ``as``
# alias form ``import goga.build.build as x`` would bind ``x`` to the FUNCTION,
# not the module. ``importlib.import_module`` returns the real module object,
# which is then patched by attribute (per ``[[feedback_mock_patch_module_shadowing]]``).
_build_mod = importlib.import_module("goga.build.build")
_config_mod = importlib.import_module("goga.config")
_cli_mod = importlib.import_module("goga.pipeline.cli")


@contextlib.contextmanager
def _run_main_fresh(modname: str):
    """Re-execute ``<pkg>.__main__`` via runpy, then restore the original module.

    ``runpy.run_module`` re-executes the package's ``__main__`` submodule in a
    fresh namespace. After it returns, ``sys.modules`` no longer holds the
    original ``<pkg>.__main__`` module object. That is a problem for OTHER test
    modules that imported from it at collection time (e.g.
    ``from goga.build.__main__ import main`` in ``tests/build/test_main.py``):
    their function references keep ``__globals__`` bound to the *original*
    module dict, so a later ``mock.patch("<pkg>.__main__.<attr>")`` re-imports a
    fresh module and patches THAT, while the stale function still calls the real
    attribute. Popping up front (to force the fresh runpy execution) and
    restoring the original module object afterward keeps the cache coherent, so
    collection/execution order never changes test outcomes.
    """
    original = sys.modules.pop(modname, None)
    try:
        yield
    finally:
        if original is not None:
            sys.modules[modname] = original


class TestInContainerEntrypointFlow:
    """End-to-end cross-cell composition for the two in-container entrypoints."""

    def test_build_entrypoint_reaches_build_in_container(self, monkeypatch, capsys) -> None:
        """With GOGA_DOCKER=1, ``python -m goga.build plan.md`` reaches ``build()``.

        Composes the docker cell (real guard), the build cell (real ``__main__``
        argparse wiring), and the config cell (``load_config``). The guard passes;
        ``build()`` is invoked with the parsed plan and is the dispatch target.
        """
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["goga.build", "plan.md"])

        with (
            _run_main_fresh("goga.build.__main__"),
            mock.patch.object(_build_mod, "build", return_value=0) as mock_build,
            mock.patch.object(_config_mod, "load_config") as mock_config,
            pytest.raises(SystemExit) as exc_info,
        ):
            runpy.run_module("goga.build", run_name="__main__")

        # ``raise SystemExit(main())`` with main() == 0 -> SystemExit(0).
        assert exc_info.value.code == 0
        # The guard passed silently; no refusal message on stderr.
        assert capsys.readouterr().err == ""
        # build() was reached and received the parsed plan positional.
        assert mock_build.call_count == 1
        assert mock_build.call_args[0][0] == "plan.md"
        # load_config() was reached (config cell composed).
        assert mock_config.call_count == 1

    def test_pipeline_entrypoint_reaches_cli_in_container(self, monkeypatch, capsys) -> None:
        """With GOGA_DOCKER=1, ``python -m goga.pipeline list`` reaches ``pipeline_cli``.

        Composes the docker cell (real guard) and the pipeline cell (real
        ``__main__`` thin-wrapper delegation). The guard passes; ``pipeline_cli``
        receives ``sys.argv[1:]`` and is the dispatch target.
        """
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["goga.pipeline", "list"])

        with (
            _run_main_fresh("goga.pipeline.__main__"),
            mock.patch.object(_cli_mod, "pipeline_cli", return_value=0) as mock_cli,
            pytest.raises(SystemExit) as exc_info,
        ):
            runpy.run_module("goga.pipeline", run_name="__main__")

        # ``sys.exit(pipeline_cli(...))`` with pipeline_cli() == 0 -> SystemExit(0).
        assert exc_info.value.code == 0
        assert capsys.readouterr().err == ""
        # pipeline_cli was reached and received the sliced argv.
        assert mock_cli.call_count == 1
        assert mock_cli.call_args == mock.call(["list"])

    def test_both_entrypoints_refuse_on_host(self, monkeypatch, capsys) -> None:
        """With GOGA_DOCKER unset, both entrypoints refuse via the same guard.

        Both ``python -m goga.build plan.md`` and ``python -m goga.pipeline list``
        raise ``SystemExit(1)`` before any dispatch target (``build`` /
        ``load_config`` / ``pipeline_cli``) is called, and both emit the same
        refusal message — proving the two entrypoints refuse consistently through
        the shared ``ensure_in_docker`` routine from :mod:`goga.docker`.
        """
        monkeypatch.delenv("GOGA_DOCKER", raising=False)

        def _fail_if_called(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("dispatch target must not be called on the host")

        # --- build entrypoint refuses ---
        monkeypatch.setattr(sys, "argv", ["goga.build", "plan.md"])

        with (
            _run_main_fresh("goga.build.__main__"),
            mock.patch.object(_build_mod, "build", side_effect=_fail_if_called) as mock_build,
            mock.patch.object(_config_mod, "load_config", side_effect=_fail_if_called) as mock_config,
            pytest.raises(SystemExit) as build_exc,
        ):
            runpy.run_module("goga.build", run_name="__main__")

        assert build_exc.value.code == 1
        assert mock_build.call_count == 0
        assert mock_config.call_count == 0
        build_err = capsys.readouterr().err
        assert "goga Docker image" in build_err

        # --- pipeline entrypoint refuses ---
        monkeypatch.setattr(sys, "argv", ["goga.pipeline", "list"])

        with (
            _run_main_fresh("goga.pipeline.__main__"),
            mock.patch.object(_cli_mod, "pipeline_cli", side_effect=_fail_if_called) as mock_cli,
            pytest.raises(SystemExit) as pipeline_exc,
        ):
            runpy.run_module("goga.pipeline", run_name="__main__")

        assert pipeline_exc.value.code == 1
        assert mock_cli.call_count == 0
        pipeline_err = capsys.readouterr().err
        # Same guard routine -> same refusal message on both entrypoints.
        assert "goga Docker image" in pipeline_err
        assert build_err == pipeline_err


class TestRunpyThinWrapperInvariant:
    """The pipeline entrypoint stays a thin runpy wrapper (no RuntimeWarning)."""

    def test_pipeline_entrypoint_run_emits_no_pre_import_warning(self, monkeypatch) -> None:
        """Importing the package must not pre-load ``__main__`` into sys.modules.

        A runpy ``RuntimeWarning`` about ``__main__`` already being in
        ``sys.modules`` would indicate the thin-wrapper invariant was broken
        (e.g. ``pipeline_cli`` defined locally in ``__main__``). Cross-cell
        composition must preserve the invariant established in Task 4.
        """
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["goga.pipeline", "list"])

        with (
            _run_main_fresh("goga.pipeline.__main__"),
            mock.patch.object(_cli_mod, "pipeline_cli", return_value=0),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")

            with pytest.raises(SystemExit):
                runpy.run_module("goga.pipeline", run_name="__main__")

        pre_import_warnings = [
            w
            for w in caught
            if issubclass(w.category, RuntimeWarning)
            and "__main__" in str(w.message)
            and "sys.modules" in str(w.message)
        ]
        assert pre_import_warnings == []
