from __future__ import annotations

import inspect

import goga.docker


class TestContract:
    """Contract-surface lock: facade accessibility and API shape."""

    def test_encode_home_profiles_importable_from_facade(self) -> None:
        from goga.docker import encode_home_profiles

        assert callable(encode_home_profiles)

    def test_encode_home_profiles_in_facade_all(self) -> None:
        assert "encode_home_profiles" in goga.docker.__all__

    def test_encode_home_profiles_signature_matches_contract(self) -> None:
        from goga.docker import encode_home_profiles

        signature = inspect.signature(encode_home_profiles)

        assert list(signature.parameters) == ["profiles"]
        assert signature.parameters["profiles"].default is inspect.Parameter.empty
        assert signature.return_annotation == "str"

    def test_decode_home_profiles_importable_from_facade(self) -> None:
        from goga.docker import decode_home_profiles

        assert callable(decode_home_profiles)

    def test_decode_home_profiles_in_facade_all(self) -> None:
        assert "decode_home_profiles" in goga.docker.__all__

    def test_decode_home_profiles_signature_matches_contract(self) -> None:
        from goga.docker import decode_home_profiles

        signature = inspect.signature(decode_home_profiles)

        assert list(signature.parameters) == ["value"]
        assert signature.parameters["value"].default is inspect.Parameter.empty
        assert signature.return_annotation == "dict[str, dict[str, Any]]"
