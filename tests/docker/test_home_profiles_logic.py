from __future__ import annotations

import base64
import json
import string

import pytest
from goga.docker import decode_home_profiles, encode_home_profiles


class TestEncodeHomeProfiles:
    """Behavior coverage for the bundle encoder."""

    def test_encode_home_profiles_empty_bundle_and_roundtrip(self) -> None:
        bundle = {
            "mixa": {"worker": {"agent": "codex", "model": "sonnet"}},
            "zeta": {"flag": True, "count": 2, "none": None},
        }

        value = encode_home_profiles(bundle)

        assert encode_home_profiles({}) == ""
        assert decode_home_profiles("") == {}
        assert value != ""
        assert "\n" not in value
        assert set(value) <= set(string.ascii_letters + string.digits + "+/=")
        assert decode_home_profiles(value) == bundle
        assert encode_home_profiles(bundle) == encode_home_profiles(bundle)
        assert encode_home_profiles(bundle) == encode_home_profiles(dict(reversed(list(bundle.items()))))

    def test_encode_home_profiles_inner_scalars_carried_verbatim(self) -> None:
        bundle = {"a": {"s": "x", "n": None, "f": 1.5, "t": True}}

        assert decode_home_profiles(encode_home_profiles(bundle)) == bundle


class TestDecodeHomeProfiles:
    """Behavior coverage for the bundle decoder."""

    @pytest.mark.parametrize(
        "payload",
        [
            "!!!not-base64!!!",
            base64.b64encode(b"not json").decode("ascii"),
            base64.b64encode(json.dumps([1, 2]).encode("utf-8")).decode("ascii"),
            base64.b64encode(json.dumps({"a": "b"}).encode("utf-8")).decode("ascii"),
            base64.b64encode(json.dumps({"a": [1]}).encode("utf-8")).decode("ascii"),
        ],
    )
    def test_decode_home_profiles_damaged_payload_clean_error(self, payload: str) -> None:
        with pytest.raises(ValueError, match=r"GOGA_HOME_PROFILES: invalid payload") as exc_info:
            decode_home_profiles(payload)

        assert payload not in str(exc_info.value)
