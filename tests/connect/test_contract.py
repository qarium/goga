from __future__ import annotations

import inspect
import typing

from goga.connect import connect


class TestInstallContract:
    def test_connect_importable_from_facade(self) -> None:
        assert callable(connect)

    def test_connect_has_correct_signature(self) -> None:
        sig = inspect.signature(connect)
        params = list(sig.parameters.keys())
        assert params == ["agent", "config", "force_overwrite"]

    def test_connect_agent_param_is_optional_str(self) -> None:
        hints = typing.get_type_hints(connect)
        # str | None
        assert hints["agent"] == str | None

    def test_connect_config_param_type(self) -> None:
        from goga.config import Config

        hints = typing.get_type_hints(connect)
        assert hints["config"] == Config | None

    def test_connect_returns_int(self) -> None:
        hints = typing.get_type_hints(connect)
        assert hints["return"] is int

    def test_connect_agent_default_none(self) -> None:
        sig = inspect.signature(connect)
        assert sig.parameters["agent"].default is None
