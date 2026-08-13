from __future__ import annotations

import inspect

import pytest

# Gate the whole module on copier being installed — it may be absent in some
# environments, and these tests exist only to lock goga's call contract against
# the *real* copier API surface (the unit tests in test_scaffold.py mock copier
# and therefore cannot detect a kwargs mismatch against the real signatures).
copier = pytest.importorskip("copier")


class TestCopierCallContract:
    """Lock goga's copier call shape against the real copier API.

    goga calls copier with specific keyword-only kwargs (``answers_file``,
    ``vcs_ref``, ``overwrite``, ``defaults``) and, for ``run_update``, with NO
    ``src_path``. The unit tests mock copier, so a kwargs mismatch against the
    real API — exactly the gap that let the missing ``overwrite=True`` defect
    slip through — is invisible there. These tests inspect the real signatures
    (no network, no git) to lock the contract.
    """

    def test_copier_run_copy_accepts_goga_kwargs(self) -> None:
        params = inspect.signature(copier.run_copy).parameters

        # goga's call shape is valid: ``run_copy(src_path, dst_path, data, ...)``
        # plus the four keyword-only kwargs goga relies on.
        assert "src_path" in params, "run_copy must accept src_path (goga passes the clean URL)"
        assert "data" in params
        for name in ("answers_file", "vcs_ref", "defaults", "overwrite"):
            assert name in params, f"run_copy must accept {name}"

        # goga passes answers_file, vcs_ref, defaults, overwrite as keyword-only.
        # Guard against them ever being positional (a real-API mismatch would
        # silently bind a positional value to the wrong parameter).
        for name in ("answers_file", "vcs_ref", "defaults", "overwrite"):
            assert params[name].kind == inspect.Parameter.KEYWORD_ONLY, (
                f"run_copy {name} must be keyword-only"
            )

    def test_copier_run_update_has_no_src_path_and_accepts_goga_kwargs(self) -> None:
        params = inspect.signature(copier.run_update).parameters

        # run_update takes NO src_path — the template + answers come from the
        # recorded state file. Regression guard for the no-src_path constraint.
        assert "src_path" not in params, "run_update must not take src_path"

        for name in ("answers_file", "vcs_ref", "defaults", "overwrite"):
            assert name in params, f"run_update must accept {name}"
            assert params[name].kind == inspect.Parameter.KEYWORD_ONLY, (
                f"run_update {name} must be keyword-only"
            )

        # overwrite=True is REQUIRED on run_update (copier raises
        # UserMessageError("Enable overwrite to update a subproject.") without
        # it); defaults=True is mandatory for the no-interactive mechanism.
        assert params["overwrite"].default is False
        assert params["defaults"].default is False

    def test_copier_is_importable_at_runtime(self) -> None:
        # Documents that the Task 1 dependency change (copier>=9.0 in main
        # dependencies) makes copier importable at runtime for goga/scaffold.
        import copier as copier_module  # intentional import check

        assert hasattr(copier_module, "__version__")
        assert hasattr(copier_module, "run_copy")
        assert hasattr(copier_module, "run_update")
