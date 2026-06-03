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
        assert params == ["agents", "force_overwrite"]

    def test_connect_agents_param_is_list_str(self) -> None:
        hints = typing.get_type_hints(connect)
        assert hints["agents"] == list[str]

    def test_connect_returns_int(self) -> None:
        hints = typing.get_type_hints(connect)
        assert hints["return"] is int

    def test_connect_agents_default_is_none(self) -> None:
        sig = inspect.signature(connect)
        assert sig.parameters["agents"].default is inspect.Parameter.empty

    def test_connect_force_overwrite_default_is_false(self) -> None:
        sig = inspect.signature(connect)
        assert sig.parameters["force_overwrite"].default is False
