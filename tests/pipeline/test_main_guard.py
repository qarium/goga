from __future__ import annotations

import runpy
import sys
import warnings
from unittest import mock

# ``goga.pipeline.__init__`` re-exports ``pipeline_cli`` from ``cli``, which can
# shadow the ``cli`` submodule name in attribute access on Python 3.10. Resolve
# the real module up front and patch its attribute directly (string-based
# ``mock.patch`` paths are unreliable here). Per
# [[feedback_mock_patch_module_shadowing]].
import goga.pipeline.cli as _cli_module
import pytest


class TestContract:
    """Contract-surface lock: the in-container guard is wired into __main__."""

    def test_pipeline_main_imports_ensure_in_docker(self) -> None:
        import goga.pipeline.__main__ as m

        assert hasattr(m, "ensure_in_docker")


class TestPipelineMainGuard:
    """Behavior coverage for both branches of the __main__ in-container guard."""

    def test_pipeline_main_delegates_to_cli_after_guard(self, monkeypatch) -> None:
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["prog", "list"])

        # Run runpy from a clean state so no pre-import RuntimeWarning is emitted
        # and the __main__ code is executed fresh.
        sys.modules.pop("goga.pipeline.__main__", None)

        with (
            mock.patch.object(_cli_module, "pipeline_cli", return_value=0) as mock_cli,
            pytest.raises(SystemExit) as exc_info,
        ):
            runpy.run_module("goga.pipeline", run_name="__main__")

        assert exc_info.value.code == 0
        assert mock_cli.call_args == mock.call(["list"])

    def test_pipeline_main_refuses_on_host(self, monkeypatch) -> None:
        monkeypatch.delenv("GOGA_DOCKER", raising=False)
        monkeypatch.setattr(sys, "argv", ["prog", "list"])

        def _fail_if_called(*_args: object, **_kwargs: object) -> int:
            raise AssertionError("pipeline_cli must not be called on the host")

        sys.modules.pop("goga.pipeline.__main__", None)

        with (
            mock.patch.object(_cli_module, "pipeline_cli", side_effect=_fail_if_called) as mock_cli,
            pytest.raises(SystemExit) as exc_info,
        ):
            runpy.run_module("goga.pipeline", run_name="__main__")

        assert exc_info.value.code == 1
        assert mock_cli.call_count == 0

    def test_pipeline_main_guard_does_not_define_pipeline_cli(self, monkeypatch) -> None:
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(sys, "argv", ["prog", "list"])

        import goga.pipeline.__main__ as m

        # pipeline_cli is imported from cli.py, not defined locally in __main__.
        assert m.pipeline_cli.__module__ == "goga.pipeline.cli"

        # Run runpy from a clean interpreter state (no pre-imported __main__) so
        # the thin-wrapper invariant holds: importing the package must not load
        # __main__ into sys.modules and trigger a runpy RuntimeWarning.
        sys.modules.pop("goga.pipeline.__main__", None)

        with (
            mock.patch.object(_cli_module, "pipeline_cli", return_value=0),
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
