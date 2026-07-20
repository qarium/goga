# tests/commands/install/test_resolve_version.py — contract and logic tests for resolve_version

import importlib
import inspect

import pytest
from goga.commands.install import resolve_version

# ---------------------------------------------------------------------------
# Contract tests — facade exposure and signature shape
# ---------------------------------------------------------------------------


class TestResolveVersionFacade:
    """Contract tests — verify resolve_version is exposed and shaped per CODEMANIFEST."""

    def test_resolve_version_importable_from_facade(self) -> None:
        assert resolve_version is not None
        assert callable(resolve_version)

    def test_resolve_version_in_facade_all(self) -> None:
        facade = importlib.import_module("goga.commands.install")
        assert facade.__all__ == ["install", "resolve_version"]

    def test_resolve_version_signature(self) -> None:
        sig = inspect.signature(resolve_version)
        params = sig.parameters
        assert list(params) == ["form"]
        assert params["form"].annotation is str | None or params["form"].annotation == "str | None"
        assert sig.return_annotation is str | None or sig.return_annotation == "str | None"


# ---------------------------------------------------------------------------
# Logic tests — positive (accepted grammar forms)
# ---------------------------------------------------------------------------


class TestResolveVersionLogicPositive:
    """Positive behavioral scenarios — the four accepted grammar forms."""

    def test_resolve_version_none_returns_none(self) -> None:
        assert resolve_version(None) is None

    def test_resolve_version_latest_returns_none(self) -> None:
        assert resolve_version("latest") is None

    def test_resolve_version_major_xrange(self) -> None:
        # "1.x" → major x-range → compatible-release pin on the major: ~=1.0
        assert resolve_version("1.x") == "~=1.0"

    def test_resolve_version_minor_xrange(self) -> None:
        # "1.0.x" → minor x-range → compatible-release pin on the minor: ~=1.0.0
        # The trailing .0 is required — ~=1.0 alone is a major-only bound.
        assert resolve_version("1.0.x") == "~=1.0.0"

    def test_resolve_version_concrete_three_segments(self) -> None:
        assert resolve_version("1.0.1") == "==1.0.1"

    def test_resolve_version_concrete_two_segments(self) -> None:
        # "1.0" is a valid concrete two-segment pin (regression: was rejected before).
        assert resolve_version("1.0") == "==1.0"

    def test_resolve_version_concrete_one_segment(self) -> None:
        assert resolve_version("1") == "==1"

    def test_resolve_version_concrete_high_versions(self) -> None:
        assert resolve_version("10.20.30") == "==10.20.30"

    @pytest.mark.parametrize(
        ("form", "expected"),
        [
            ("0", "==0"),
            ("0.0.x", "~=0.0.0"),
            ("0.x", "~=0.0"),
        ],
    )
    def test_resolve_version_zero_versions(self, form: str, expected: str) -> None:
        assert resolve_version(form) == expected

    def test_resolve_version_specifier_always_operator_prefixed(self) -> None:
        # Every non-None output is prefixed with the operator (== or ~=).
        outputs = [
            resolve_version("1.x"),
            resolve_version("1.0.x"),
            resolve_version("1"),
            resolve_version("1.0"),
            resolve_version("1.0.1"),
        ]
        for out in outputs:
            assert out is not None
            assert out.startswith("==") or out.startswith("~=")

    def test_resolve_version_performs_no_io(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pure transformer — resolution must not perform any file I/O. Spy on
        # ``open`` to assert it is never called across accepted, latest, and
        # rejected forms. (The prior "x == x" assertion passed for any
        # deterministic function, including one with side effects.)
        import builtins

        opened: list[tuple] = []
        real_open = builtins.open

        def spy(*args, **kwargs):
            opened.append(args)
            return real_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", spy)
        assert resolve_version("1.0.x") == "~=1.0.0"
        assert resolve_version("latest") is None
        with pytest.raises(ValueError, match="operator"):
            resolve_version("==1.0")
        assert opened == []


# ---------------------------------------------------------------------------
# Logic tests — negative (rejection paths)
# ---------------------------------------------------------------------------


class TestResolveVersionLogicNegative:
    """Negative behavioral scenarios — operator-prefixed and malformed forms raise."""

    @pytest.mark.parametrize("op", ["==", ">=", "<=", "~=", "!=", "<", ">", "==="])
    def test_resolve_version_all_operators_rejected(self, op: str) -> None:
        with pytest.raises(ValueError, match="operator"):
            resolve_version(f"{op}1.0")

    def test_resolve_version_operator_prefixed_raises(self) -> None:
        with pytest.raises(ValueError, match="operator"):
            resolve_version("==1.0")

    @pytest.mark.parametrize(
        "form",
        [
            "foo",
            "1.x.0",
            "1.0.x.y",
            "1.0.0a1",
            "1.0.0.post1",
            "1.0.0+local",
            "1.0.0.0",
            "1.x.x",
            "",
        ],
    )
    def test_resolve_version_malformed_raises(self, form: str) -> None:
        with pytest.raises(ValueError, match="malformed"):
            resolve_version(form)

    def test_resolve_version_empty_string_raises(self) -> None:
        # "" is not a valid form — not None, not "latest", not a grammar form.
        with pytest.raises(ValueError, match="malformed"):
            resolve_version("")

    def test_resolve_version_uppercase_latest_not_treated_as_marker(self) -> None:
        # Only the literal lowercase "latest" is the no-specifier marker.
        with pytest.raises(ValueError, match="malformed"):
            resolve_version("Latest")
