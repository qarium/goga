from __future__ import annotations

import base64
import inspect
import json
import string

import pytest
from goga.docker import decode_extra_env, encode_extra_env


class TestContract:
    """Contract-surface lock: facade accessibility and API shape."""

    def test_encode_extra_env_importable_from_facade(self) -> None:
        assert callable(encode_extra_env)

    def test_encode_extra_env_in_facade_all(self) -> None:
        import goga.docker

        assert "encode_extra_env" in goga.docker.__all__

    def test_encode_extra_env_signature_matches_contract(self) -> None:
        signature = inspect.signature(encode_extra_env)

        assert list(signature.parameters) == ["entries"]
        assert signature.parameters["entries"].default is inspect.Parameter.empty
        assert signature.return_annotation == "str"

    def test_decode_extra_env_importable_from_facade(self) -> None:
        assert callable(decode_extra_env)

    def test_decode_extra_env_in_facade_all(self) -> None:
        import goga.docker

        assert "decode_extra_env" in goga.docker.__all__

    def test_decode_extra_env_signature_matches_contract(self) -> None:
        signature = inspect.signature(decode_extra_env)

        assert list(signature.parameters) == ["value"]
        assert signature.parameters["value"].default is inspect.Parameter.empty
        assert signature.return_annotation == "dict[str, str]"


class TestEncodeExtraEnv:
    """Behavior coverage for the payload encoder."""

    def test_encode_extra_env_roundtrip_resolves_last_wins(self) -> None:
        entries = ["KEY=V", "TOKEN=a=b", "KEY=W"]

        value = encode_extra_env(entries)

        assert "\n" not in value
        assert value != ""
        assert set(value) <= set(string.ascii_letters + string.digits + "+/=")
        assert decode_extra_env(value) == {"KEY": "W", "TOKEN": "a=b"}

    def test_encode_extra_env_deterministic(self) -> None:
        assert encode_extra_env(["A=1", "B=2"]) == encode_extra_env(["A=1", "B=2"])
        assert encode_extra_env(["A=1", "B=2"]) == encode_extra_env(["B=2", "A=1"])

    def test_encode_extra_env_silently_skips_separatorless_entries(self) -> None:
        entries = ["BROKEN", "=V", "KEY=V"]

        value = encode_extra_env(entries)

        assert decode_extra_env(value) == {"": "V", "KEY": "V"}


class TestDecodeExtraEnv:
    """Behavior coverage for the payload decoder."""

    @pytest.mark.parametrize(
        "payload",
        [
            "!!!not-base64!!!",
            "aGVsbG8=",
            base64.b64encode(json.dumps([1, 2]).encode("utf-8")).decode("ascii"),
            base64.b64encode(json.dumps({"K": 1}).encode("utf-8")).decode("ascii"),
        ],
    )
    def test_decode_extra_env_damaged_payload_raises_clean_error_naming_variable(self, payload: str) -> None:
        with pytest.raises(ValueError, match=r"GOGA_EXTRA_ENV: invalid payload") as exc_info:
            decode_extra_env(payload)

        assert payload not in str(exc_info.value)

    def test_decode_extra_env_empty_value_returns_empty_mapping(self) -> None:
        assert decode_extra_env("") == {}
