from __future__ import annotations

import inspect
import typing

from goga.install import install


class TestInstallContract:
    def test_install_importable_from_facade(self) -> None:
        assert callable(install)

    def test_install_has_correct_signature(self) -> None:
        sig = inspect.signature(install)
        params = list(sig.parameters.keys())
        assert params == ["agent", "config"]

    def test_install_agent_param_is_optional_str(self) -> None:
        hints = typing.get_type_hints(install)
        # str | None
        assert hints["agent"] == str | None

    def test_install_config_param_type(self) -> None:
        from goga.config import Config

        hints = typing.get_type_hints(install)
        assert hints["config"] == Config | None

    def test_install_returns_int(self) -> None:
        hints = typing.get_type_hints(install)
        assert hints["return"] is int

    def test_install_agent_default_none(self) -> None:
        sig = inspect.signature(install)
        assert sig.parameters["agent"].default is None
