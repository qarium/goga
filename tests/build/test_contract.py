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

    def test_run_build_pass_signature_has_no_env_layer(self) -> None:
        """Contract: the pass launch carries no env parameter — the subprocess
        inherits the container environment; the additional wrapper path rides
        alongside the pass wrapper into the config write."""
        from goga.build.build_pass import run_build_pass

        sig = inspect.signature(run_build_pass)

        assert list(sig.parameters) == [
            "plan",
            "settings",
            "options",
            "wrapper_path",
            "dry_run",
            "additional_wrapper_path",
        ]
        assert sig.parameters["additional_wrapper_path"].default is None

    def test_write_ralphex_config_carries_additional_wrapper_path(self) -> None:
        """Contract: the config writer takes the additional wrapper path."""
        from goga.build.ralphex_config import write_ralphex_config

        sig = inspect.signature(write_ralphex_config)

        assert list(sig.parameters) == ["settings", "wrapper_path", "additional_wrapper_path"]
        assert sig.parameters["additional_wrapper_path"].default is None

    def test_resolve_run_settings_additional_env_flow(self) -> None:
        """Contract: the additional env layer flows verbatim into the resolved
        additional settings — empty when the block or its env is absent."""
        from goga.build.run_settings import resolve_run_settings
        from goga.config import AdditionalReviewConfig, BuildConfig, ReviewConfig

        config = BuildConfig(
            agent="claude",
            review=ReviewConfig(additional=AdditionalReviewConfig(env={"C": "3"})),
        )

        settings = resolve_run_settings(config, {})

        assert settings.review.additional.env == {"C": "3"}

        absent = resolve_run_settings(BuildConfig(agent="claude", review=None), {})

        assert absent.review.additional.env == {}
