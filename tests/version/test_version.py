# tests/version/test_version.py — contract and logic tests for the goga/version cell

from __future__ import annotations

import importlib
import inspect
from importlib.metadata import PackageNotFoundError
from unittest import mock

import pytest
from goga.version import (
    compare_versions,
    ensure_version_match,
    host_goga_version,
    resolve_relative_spec,
    resolve_version,
    version_check_enabled,
)

# ---------------------------------------------------------------------------
# Contract tests — facade exposure and signature shape
# ---------------------------------------------------------------------------


class TestVersionFacade:
    """Contract tests — the goga.version facade exposes exactly the cell API."""

    def test_version_facade_all(self) -> None:
        facade = importlib.import_module("goga.version")
        assert facade.__all__ == [
            "compare_versions",
            "ensure_version_match",
            "host_goga_version",
            "resolve_relative_spec",
            "resolve_version",
            "version_check_enabled",
        ]
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


class TestCompareVersionsFacade:
    """Contract tests — verify compare_versions is exposed and shaped per CODEMANIFEST."""

    def test_compare_versions_importable_from_facade(self) -> None:
        assert compare_versions is not None
        assert callable(compare_versions)

    def test_compare_versions_in_facade_all(self) -> None:
        facade = importlib.import_module("goga.version")
        assert "compare_versions" in facade.__all__
        assert callable(facade.compare_versions)

    def test_compare_versions_signature(self) -> None:
        sig = inspect.signature(compare_versions)
        params = sig.parameters
        assert list(params) == ["host_version", "image_version"]
        assert sig.return_annotation is bool or sig.return_annotation == "bool"


class TestHostGogaVersionFacade:
    """Contract tests — verify host_goga_version is exposed and shaped per CODEMANIFEST."""

    def test_host_goga_version_importable_from_facade(self) -> None:
        assert host_goga_version is not None
        assert callable(host_goga_version)

    def test_host_goga_version_in_facade_all(self) -> None:
        facade = importlib.import_module("goga.version")
        assert "host_goga_version" in facade.__all__
        assert callable(facade.host_goga_version)

    def test_host_goga_version_signature(self) -> None:
        sig = inspect.signature(host_goga_version)
        assert list(sig.parameters) == []
        assert sig.return_annotation is str or sig.return_annotation == "str"


class TestVersionCheckEnabledFacade:
    """Contract tests — verify version_check_enabled is exposed and shaped per CODEMANIFEST."""

    def test_version_check_enabled_importable_from_facade(self) -> None:
        assert version_check_enabled is not None
        assert callable(version_check_enabled)

    def test_version_check_enabled_in_facade_all(self) -> None:
        facade = importlib.import_module("goga.version")
        assert "version_check_enabled" in facade.__all__
        assert callable(facade.version_check_enabled)

    def test_version_check_enabled_signature(self) -> None:
        sig = inspect.signature(version_check_enabled)
        assert list(sig.parameters) == []
        assert sig.return_annotation is bool or sig.return_annotation == "bool"


class TestEnsureVersionMatchFacade:
    """Contract tests — verify ensure_version_match is exposed and shaped per CODEMANIFEST."""

    def test_ensure_version_match_importable_from_facade(self) -> None:
        assert ensure_version_match is not None
        assert callable(ensure_version_match)

    def test_ensure_version_match_in_facade_all(self) -> None:
        facade = importlib.import_module("goga.version")
        assert "ensure_version_match" in facade.__all__
        assert callable(facade.ensure_version_match)

    def test_ensure_version_match_signature(self) -> None:
        sig = inspect.signature(ensure_version_match)
        params = sig.parameters
        assert list(params) == ["image_version"]
        assert params["image_version"].annotation is str | None or params["image_version"].annotation == "str | None"
        assert sig.return_annotation is None or sig.return_annotation == "None"


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


# ---------------------------------------------------------------------------
# Logic tests — compare_versions ((major, minor) comparator)
# ---------------------------------------------------------------------------


class TestCompareVersionsLogic:
    """Behavioral scenarios — (major, minor) comparison with tail reduction."""

    def test_compare_versions_agreeing_major_minor(self) -> None:
        # A patch difference is invisible at the (major, minor) granularity —
        # the core of the check's tolerance.
        assert compare_versions("1.2.0", "1.2.1") is True

    @pytest.mark.parametrize(
        ("host_version", "image_version", "expected"),
        [
            # Rich tails reduce silently to the same (major, minor) line.
            ("1.2.1.dev3", "1.2.0", True),
            ("1.2.0rc1", "1.2.0.post1", True),
            ("1.2.0+local", "1.2.0", True),
            # A missing minor segment counts as 0: "1" ≡ "1.0".
            ("1", "1.0", True),
            # Patch-only difference on two-segment forms.
            ("1.2", "1.2.9", True),
            # Minor and major differences refuse.
            ("1.3.0", "1.2.4", False),
            ("2.0.0", "1.9.1", False),
        ],
    )
    def test_compare_versions_parametrized_reduction(
        self, host_version: str, image_version: str, expected: bool
    ) -> None:
        assert compare_versions(host_version, image_version) is expected

    @pytest.mark.parametrize("bad_version", ["abc", "", "١.٢"])
    def test_compare_versions_rejects_non_numeric_prefix(self, bad_version: str) -> None:
        # No leading numeric major segment — re.ASCII also rejects Unicode
        # decimal digits, which are not PEP 440.
        with pytest.raises(ValueError, match="cannot determine version line"):
            compare_versions(bad_version, "1.2")


# ---------------------------------------------------------------------------
# Logic tests — version_check_enabled (gate predicate)
# ---------------------------------------------------------------------------


class TestVersionCheckEnabledLogic:
    """Behavioral scenarios — exact-"1" escape, every other value enables."""

    @pytest.mark.parametrize("value", ["", "0", " 1", "true", "2"])
    def test_version_check_enabled_true_matrix(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        # The test's own monkeypatch runs after the autouse _skip_version_check
        # fixture and overrides its GOGA_SKIP_VERSION_CHECK=1. Only the exact
        # string "1" disables — no stripping, no case folding.
        monkeypatch.setenv("GOGA_SKIP_VERSION_CHECK", value)
        assert version_check_enabled() is True

    def test_version_check_enabled_exact_one_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOGA_SKIP_VERSION_CHECK", "1")
        assert version_check_enabled() is False

    def test_version_check_enabled_unset_returns_true_despite_autouse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # unset is the most common mode (no escape at all) — still enabled.
        monkeypatch.delenv("GOGA_SKIP_VERSION_CHECK")
        assert version_check_enabled() is True


# ---------------------------------------------------------------------------
# Logic tests — host_goga_version (single reading point)
# ---------------------------------------------------------------------------


class TestHostGogaVersionLogic:
    """Behavioral scenarios — metadata read, silent success, propagated failure."""

    def test_host_goga_version_returns_installed_version(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Metadata substitution on the stdlib module attribute — the single
        # reading point must return the distribution version verbatim.
        monkeypatch.setattr("goga.version.version.importlib.metadata.version", lambda _name: "1.2.3")
        assert host_goga_version() == "1.2.3"
        captured = capsys.readouterr()
        assert captured.out == ""  # never prints — translation belongs to callers
        assert captured.err == ""

    def test_host_goga_version_propagates_metadata_failure(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        failing = mock.Mock(side_effect=PackageNotFoundError("goga"))
        monkeypatch.setattr("goga.version.version.importlib.metadata.version", failing)
        with pytest.raises(PackageNotFoundError):
            host_goga_version()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


# ---------------------------------------------------------------------------
# Logic tests — ensure_version_match (outcome matrix)
# ---------------------------------------------------------------------------


class TestEnsureVersionMatchLogic:
    """Behavioral scenarios — the five outcomes of the consistency check.

    The host-version seam is the intramodule call point
    ``goga.version.version.host_goga_version`` (step 1 of the algorithm calls
    it as a module global); stderr is captured with ``capsys``.
    """

    def test_ensure_version_match_agreeing_path_is_silent(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("goga.version.version.host_goga_version", lambda: "1.2.0")
        assert ensure_version_match("1.2.1") is None  # patch difference agrees
        captured = capsys.readouterr()
        assert captured.out == ""  # nothing is printed on the agreeing path
        assert captured.err == ""

    def test_ensure_version_match_zero_placeholder_warns_and_continues(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("goga.version.version.host_goga_version", lambda: "1.2.0")
        ensure_version_match("0.0.0")  # warning, not a refusal — no exception
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "0.0.0" in captured.err
        assert "GOGA_SKIP_VERSION_CHECK" not in captured.err  # continuation, not refusal

    def test_ensure_version_match_refuses_on_mismatch(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("goga.version.version.host_goga_version", lambda: "1.2.4")
        with pytest.raises(SystemExit) as excinfo:
            ensure_version_match("1.3.0")
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "1.2.4" in captured.err  # both versions named in the message
        assert "1.3.0" in captured.err
        assert "GOGA_SKIP_VERSION_CHECK" in captured.err  # remediation names the escape
        assert "Traceback" not in captured.err  # clean refusal, no traceback

    def test_ensure_version_match_refuses_on_probe_failure(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("goga.version.version.host_goga_version", lambda: "1.2.4")
        with pytest.raises(SystemExit) as excinfo:
            ensure_version_match(None)
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "GOGA_SKIP_VERSION_CHECK" in captured.err
        assert "Traceback" not in captured.err

    def test_ensure_version_match_refuses_on_undeterminable_host(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        failing = mock.Mock(side_effect=PackageNotFoundError("goga"))
        monkeypatch.setattr("goga.version.version.host_goga_version", failing)
        with pytest.raises(SystemExit) as excinfo:
            ensure_version_match("1.2.0")
        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "cannot determine" in captured.err
        assert "Traceback" not in captured.err

    def test_ensure_version_match_refuses_on_none_host(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Broken dist-info: version() returned nothing — same refusal as a
        # missing distribution, and the comparison is never reached (without
        # the guard, _RELEASE_PREFIX_RE.match(None) would raise TypeError).
        comparator = mock.Mock()
        monkeypatch.setattr("goga.version.version.host_goga_version", lambda: None)
        monkeypatch.setattr("goga.version.version.compare_versions", comparator)
        with pytest.raises(SystemExit) as excinfo:
            ensure_version_match("1.2.0")
        assert excinfo.value.code == 1
        comparator.assert_not_called()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "cannot determine" in captured.err
        assert "Traceback" not in captured.err

    def test_version_facade_exports_new_routines(self) -> None:
        # All four check-surface names are importable from the facade.
        facade = importlib.import_module("goga.version")
        for name in ("compare_versions", "host_goga_version", "version_check_enabled", "ensure_version_match"):
            assert callable(getattr(facade, name))
        assert {"compare_versions", "host_goga_version", "version_check_enabled", "ensure_version_match"} <= set(
            facade.__all__
        )
