from __future__ import annotations

import inspect
import typing

from goga.build import build


class TestBuildContract:
    def test_build_importable_from_facade(self) -> None:
        assert callable(build)

    def test_build_has_correct_signature(self) -> None:
        sig = inspect.signature(build)
        params = list(sig.parameters.keys())
        assert params == ["plan", "config", "cli_options"]

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
