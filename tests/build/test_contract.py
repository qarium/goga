from __future__ import annotations

import inspect
import sys
import typing

from goga.build import build


class TestBuildContract:
    def test_build_importable_from_facade(self) -> None:
        assert callable(build)

    def test_build_has_correct_signature(self) -> None:
        sig = inspect.signature(build)
        params = list(sig.parameters.keys())
        assert params == ["plan", "config", "cli_options"]

    def test_absorbed_private_helpers_removed_from_module(self) -> None:
        """The private config/defaults helpers are gone — their contracts were
        absorbed by the public routines (write_ralphex_config, sync_ralphex_defaults).

        sys.modules is used because goga/build/__init__.py shadows the `build`
        attribute with the function of the same name.
        """
        build_module = sys.modules["goga.build.build"]
        assert not hasattr(build_module, "_write_ralphex_config")
        assert not hasattr(build_module, "_copy_defaults")
        assert not hasattr(build_module, "DEFAULTS_PACKAGE_DIR")
        assert not hasattr(build_module, "_DEFAULT_CLAUDE_ARGS")

    def test_build_plan_param_is_str(self) -> None:
        hints = typing.get_type_hints(build)
        assert hints["plan"] is str

    def test_build_config_param_type(self) -> None:
        from goga.config import ProjectConfig

        hints = typing.get_type_hints(build)
        assert hints["config"] is ProjectConfig

    def test_build_cli_options_param_is_dict(self) -> None:
        hints = typing.get_type_hints(build)
        assert hints["cli_options"] is dict

    def test_build_returns_int(self) -> None:
        hints = typing.get_type_hints(build)
        assert hints["return"] is int

    def test_run_settings_module_surface(self) -> None:
        """Contract: the settings resolver lives at goga.build.run_settings."""
        from goga.build import run_settings

        assert callable(run_settings.resolve_run_settings)
        assert hasattr(run_settings, "RunSettings")
        assert hasattr(run_settings, "PassSettings")
        assert hasattr(run_settings, "ReviewPassSettings")

    def test_pass_options_module_surface(self) -> None:
        """Contract: the options composer lives at goga.build.pass_options."""
        from goga.build import pass_options

        assert callable(pass_options.compose_pass_options)

    def test_retired_review_options_module_deleted(self) -> None:
        """Contract: goga.build.review_options is gone — no compatibility shims."""
        import importlib.util

        assert importlib.util.find_spec("goga.build.review_options") is None

    def test_retired_cli_keys_absent_from_main(self) -> None:
        """Contract: the in-container surface carries no worktree/skip_finalize keys."""
        import goga.build.__main__ as build_main

        source = inspect.getsource(build_main)
        assert "worktree" not in source
        assert "skip_finalize" not in source
