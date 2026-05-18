from __future__ import annotations

import inspect
import typing

from goga.sync import sync


class TestSyncContract:
    def test_sync_importable_from_facade(self) -> None:
        assert callable(sync)

    def test_sync_has_correct_signature(self) -> None:
        sig = inspect.signature(sync)
        params = list(sig.parameters.keys())
        assert params == ["source", "token", "branch"]

    def test_sync_source_param_is_str(self) -> None:
        hints = typing.get_type_hints(sync)
        assert hints["source"] is str

    def test_sync_token_param_default_none(self) -> None:
        sig = inspect.signature(sync)
        assert sig.parameters["token"].default is None

    def test_sync_branch_param_default_none(self) -> None:
        sig = inspect.signature(sync)
        assert sig.parameters["branch"].default is None

    def test_sync_returns_int(self) -> None:
        hints = typing.get_type_hints(sync)
        assert hints["return"] is int
