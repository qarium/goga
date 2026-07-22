"""Contract and logic tests for the ``translate_role`` routine.

``translate_role`` is the single source of truth for the bijection between an
authoring-side role and its afm-side agent name / prompt-file stem. It maps the
three known role aliases (``planner``/``executor``/``reviewer``) to their afm
stems (``planning``/``implementation``/``review``) and passes every other value
through verbatim — the afm agent namespace is open, so already-afm names,
``summary``, ``auto``, and arbitrary names need no validation.
"""

from __future__ import annotations

import inspect
import typing

import pytest
from goga.pipeline.compiler import translate_role


class TestTranslateRoleContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_translate_role_importable_from_facade(self) -> None:
        """translate_role must be importable from the compiler facade."""
        assert translate_role is not None
        assert callable(translate_role)

    def test_translate_role_signature_single_str_returns_str(self) -> None:
        """Signature is ``translate_role(role: str) -> str`` — one positional str param, returns str."""
        sig = inspect.signature(translate_role)
        params = list(sig.parameters.values())

        assert len(params) == 1
        role_param = params[0]
        assert role_param.name == "role"
        # ``compile_flow.py`` uses ``from __future__ import annotations`` (PEP 563), so
        # raw annotations are deferred strings — resolve them via ``get_type_hints`` to
        # assert the real types.
        hints = typing.get_type_hints(translate_role)
        assert hints["role"] is str
        assert hints["return"] is str
        assert role_param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)

    def test_translate_role_returns_str_for_known_alias(self) -> None:
        """Calling with a known alias returns a ``str`` value (purity / no side effects)."""
        result = translate_role("planner")

        assert isinstance(result, str)
        assert result == "planning"

    def test_translate_role_is_pure_no_side_effects(self) -> None:
        """Repeated calls with the same input yield identical results (pure function)."""
        first = translate_role("reviewer")
        second = translate_role("reviewer")

        assert first == second == "review"


class TestTranslateRoleLogic:
    """Behavior tests — bijection of the three aliases + verbatim passthrough."""

    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            # The three known aliases — bijection to afm stems.
            ("planner", "planning"),
            ("executor", "implementation"),
            ("reviewer", "review"),
        ],
    )
    def test_translate_role_maps_known_aliases(self, role: str, expected: str) -> None:
        """Known role aliases map to their canonical afm agent names / prompt-file stems."""
        assert translate_role(role) == expected

    @pytest.mark.parametrize(
        "value",
        [
            # summary — separate channel, NOT a role; passes through unchanged.
            "summary",
            # auto — compiler-side default sentinel, NOT injected here.
            "auto",
            # already-afm names — not aliases, so verbatim.
            "planning",
            "implementation",
            "review",
            # arbitrary afm-agent-names — open namespace.
            "custom-agent",
            "researcher",
            "",
        ],
    )
    def test_translate_role_passes_non_aliases_verbatim(self, value: str) -> None:
        """Any value that is not one of the three aliases returns unchanged (no validation)."""
        assert translate_role(value) == value

    def test_translate_role_maps_known_aliases_and_passes_others(self) -> None:
        """Bijection of exactly the three aliases; everything else verbatim (open namespace)."""
        assert translate_role("planner") == "planning"
        assert translate_role("executor") == "implementation"
        assert translate_role("reviewer") == "review"
        assert translate_role("summary") == "summary"
        assert translate_role("auto") == "auto"
        assert translate_role("planning") == "planning"
        assert translate_role("custom-agent") == "custom-agent"

    def test_translate_role_auto_not_injected_here(self) -> None:
        """``auto`` is a compiler-side default, not a DSL role value — it is NOT injected here."""
        # ``auto`` is not an alias, so it returns verbatim (the only place ``auto`` is
        # materialised is ``_DEFAULT_AGENTS`` injection in ``compile_flow``).
        assert translate_role("auto") == "auto"
