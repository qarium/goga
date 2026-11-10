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


class TestEncodeHomeProfilesStrictness:
    """The JSON-representability backstop of the encoder."""

    def test_encode_home_profiles_non_json_value_raises_value_error(self) -> None:
        """A bundle value JSON cannot represent (a YAML date) surfaces as one
        clean ValueError naming the engine variable — not a TypeError
        traceback escaping every ClickException boundary."""
        import datetime

        with pytest.raises(ValueError, match=r"GOGA_HOME_PROFILES: non-JSON-representable profile value"):
            encode_home_profiles({"mixa": {"deadline": datetime.date(2026, 1, 15)}})


class TestProfileCarriageLines:
    """Behavior coverage for the shared carriage composer."""

    def test_profile_carriage_lines_cargo_conditions(self) -> None:
        """Each line carries cargo: no ambient, no bundle, no workflow — an
        empty list; each present value appends exactly its line."""
        from goga.docker import profile_carriage_lines

        assert profile_carriage_lines("", None, None) == []
        assert profile_carriage_lines("mixa", None, None) == ["GOGA_PROFILE=mixa"]

        bundle = {"mixa": {"a": 1}}
        lines = profile_carriage_lines("mixa", bundle, "hard")

        assert lines[0] == "GOGA_PROFILE=mixa"
        assert lines[1] == f"GOGA_HOME_PROFILES={encode_home_profiles(bundle)}"
        assert lines[2] == "GOGA_WORKFLOW=hard"

    def test_profile_carriage_lines_skip_rule_and_workflow_gating(self) -> None:
        """A skipped key keeps the user's own line winning; the workflow line
        appears only when a name is given (the build and info launchers pass
        None and never carry it)."""
        from goga.docker import profile_carriage_lines

        bundle = {"mixa": {"a": 1}}
        skip = {"GOGA_PROFILE", "GOGA_HOME_PROFILES", "GOGA_WORKFLOW"}

        assert profile_carriage_lines("mixa", bundle, "hard", skip) == []
        assert profile_carriage_lines("mixa", bundle, None, {"GOGA_HOME_PROFILES"}) == ["GOGA_PROFILE=mixa"]


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
