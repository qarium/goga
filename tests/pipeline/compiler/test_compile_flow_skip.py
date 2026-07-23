"""Contract tests for the Task 4 skip-removal pass (``compile_flow``).

Pins the facade shape the 4skip feature depends on: ``compile_flow`` and
``BodyFormat`` are both importable from the compiler-cell facade. The skip
removal + reconnection helpers themselves (``_remove_skipped_stages``,
``_resolve_skip``) are private implementation details — not on the facade —
and are exercised directly via import in ``test_compile_flow_workflow.py``.
"""

from __future__ import annotations

from goga.pipeline.compiler import BodyFormat, compile_flow


class TestCompileFlowSkipContract:
    """Facade shape for the Task 4 skip-removal feature."""

    def test_compile_flow_importable_from_facade(self) -> None:
        """``compile_flow`` is importable from the compiler-cell facade."""
        assert compile_flow is not None

    def test_body_format_importable_from_facade(self) -> None:
        """``BodyFormat`` is importable from the compiler-cell facade.

        The 4skip pass dispatches on ``BodyFormat`` (STAGES reconnects
        ``depends_on``; PHASES drops positionally), so the enum must be on the
        facade.
        """
        assert BodyFormat is not None
        assert {BodyFormat.STAGES, BodyFormat.PHASES} == {BodyFormat.STAGES, BodyFormat.PHASES}
