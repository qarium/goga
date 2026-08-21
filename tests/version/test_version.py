# tests/version/test_version.py — contract and logic tests for the goga/version cell

from __future__ import annotations

import importlib
import inspect

import pytest
from goga.version import resolve_relative_spec, resolve_version

# ---------------------------------------------------------------------------
# Contract tests — facade exposure and signature shape
# ---------------------------------------------------------------------------


class TestVersionFacade:
    """Contract tests — the goga.version facade exposes exactly the cell API."""

    def test_version_facade_all(self) -> None:
        facade = importlib.import_module("goga.version")
        assert facade.__all__ == ["resolve_relative_spec", "resolve_version"]
        for name in facade.__all__:
            assert callable(getattr(facade, name))


class TestResolveVersionFacade:
    """Contract tests — verify resolve_version is exposed and shaped per CODEMANIFEST."""

    def test_resolve_version_importable_from_facade(self) -> None:
        assert resolve_version is not None
        assert callable(resolve_version)

    def test_resolve_version_in_facade_all(self) -> None:
        facade = importlib.import_module("goga.version")
        assert "resolve_version" in facade.__all__
        assert callable(facade.resolve_version)

    def test_resolve_version_signature(self) -> None:
        sig = inspect.signature(resolve_version)
        params = sig.parameters
        assert list(params) == ["form"]
        assert params["form"].annotation is str | None or params["form"].annotation == "str | None"
        assert sig.return_annotation is str | None or sig.return_annotation == "str | None"


class TestResolveRelativeSpecFacade:
    """Contract tests — verify resolve_relative_spec is shaped per CODEMANIFEST."""

    def test_resolve_relative_spec_signature(self) -> None:
        sig = inspect.signature(resolve_relative_spec)
        params = sig.parameters
        assert list(params) == ["base_version", "patch", "minor"]
        assert params["patch"].default is False
        assert params["minor"].default is False
        assert sig.return_annotation is str or sig.return_annotation == "str"


# ---------------------------------------------------------------------------
# Logic tests — resolve_version, positive (accepted grammar forms)
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
# Logic tests — resolve_version, negative (rejection paths)
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

    @pytest.mark.parametrize(
        "form",
        [
            "١.x",  # Arabic-Indic digit — major x-range gate
            "١.٢.x",  # Arabic-Indic digits — minor x-range gate
            "1٢",  # mixed ASCII/Arabic-Indic — concrete gate
            "1²",  # superscript digit: isdigit() yet not even a Unicode decimal
        ],
    )
    def test_resolve_version_non_ascii_digits_raise(self, form: str) -> None:
        # str.isdigit accepts non-ASCII Unicode digits, but they are not PEP 440 —
        # the grammar recognises ASCII digits 0-9 only (shape check, not Unicode).
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


# ---------------------------------------------------------------------------
# Logic tests — resolve_relative_spec (relative version lines)
# ---------------------------------------------------------------------------


class TestResolveRelativeSpecLogic:
    """Behavioral scenarios — line synthesis from an installed version base."""

    def test_resolve_relative_spec_patch_from_full_version(self) -> None:
        # "1.2.3" + patch → regex yields major="1", minor_seg="2" (the ".3"
        # tail is not consumed) → form "1.2.x" → ~=1.2.0.
        assert resolve_relative_spec("1.2.3", patch=True) == "~=1.2.0"

    def test_resolve_relative_spec_minor_from_full_version(self) -> None:
        # minor never uses the minor segment: "1.2.3" → form "1.x" → ~=1.0.
        assert resolve_relative_spec("1.2.3", minor=True) == "~=1.0"

    @pytest.mark.parametrize("base", ["1.2.0rc1", "1.2.0.post1", "1.2.0+local", "1.2.1.dev0"])
    def test_resolve_relative_spec_rich_bases_truncated(self, base: str) -> None:
        # Rich bases are truncated, never rejected — all four reduce to the 1.2 line.
        assert resolve_relative_spec(base, patch=True) == "~=1.2.0"
        assert resolve_relative_spec(base, minor=True) == "~=1.0"

    def test_resolve_relative_spec_both_flags_raise(self) -> None:
        with pytest.raises(ValueError, match="exactly one of patch/minor"):
            resolve_relative_spec("1.2.3", patch=True, minor=True)

    def test_resolve_relative_spec_neither_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one of patch/minor"):
            resolve_relative_spec("1.2.3")

    def test_resolve_relative_spec_patch_without_minor_segment(self) -> None:
        # Loud fail — the routine does not invent a ".0" minor segment.
        with pytest.raises(ValueError, match="no minor segment"):
            resolve_relative_spec("1", patch=True)

    @pytest.mark.parametrize("base", ["", "abc", "v1.2", "١.٢"])
    def test_resolve_relative_spec_non_numeric_base(self, base: str) -> None:
        with pytest.raises(ValueError, match="cannot determine version line"):
            resolve_relative_spec(base, minor=True)

    def test_resolve_relative_spec_minor_allows_single_segment_base(self) -> None:
        # Line asymmetry: minor works from a major-only base, patch does not.
        assert resolve_relative_spec("1", minor=True) == "~=1.0"

    def test_resolve_relative_spec_output_always_compatible_release(self) -> None:
        outputs = [
            resolve_relative_spec("1.2.3", patch=True),
            resolve_relative_spec("1.2.3", minor=True),
            resolve_relative_spec("10.20.30", patch=True),
            resolve_relative_spec("10.20.30", minor=True),
            resolve_relative_spec("1", minor=True),
        ]
        for out in outputs:
            assert isinstance(out, str)  # never None — the synthesized form always resolves
            assert out.startswith("~=")
        assert resolve_relative_spec("10.20.30", patch=True) == "~=10.20.0"
        assert resolve_relative_spec("10.20.30", minor=True) == "~=10.0"

    def test_resolve_relative_spec_performs_no_io(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pure transformer — no file I/O across the successful resolve and
        # both ValueError paths (same spy pattern as resolve_version).
        import builtins

        opened: list[tuple] = []
        real_open = builtins.open

        def spy(*args, **kwargs):
            opened.append(args)
            return real_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", spy)
        assert resolve_relative_spec("1.2.3", patch=True) == "~=1.2.0"
        with pytest.raises(ValueError, match="exactly one"):
            resolve_relative_spec("1.2.3")
        with pytest.raises(ValueError, match="cannot determine"):
            resolve_relative_spec("abc", patch=True)
        assert opened == []
