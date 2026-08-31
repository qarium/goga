"""Logic tests for the ``WorkflowReflect`` dataclass.

Covers construction behavior beyond the contract surface: the materialized
``mode`` default (a value, not an omission) and the verbatim round-trip of
authored values (the dataclass is not frozen, but supplied values must
round-trip unchanged).
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowReflect


class TestWorkflowReflectLogic:
    """Logic tests — construction behavior of the ``WorkflowReflect`` dataclass."""

    def test_workflow_reflect_mode_defaults_to_rw(self) -> None:
        """Omitting ``mode`` yields the materialized "rw" — not None.

        The contract materializes the default: «materialized to "rw" when the
        authoring entry omits it». A consumer reading the model must never
        distinguish an authored ``rw`` from an omitted mode, so the default
        pins a value rather than an absence.
        """
        reflect = WorkflowReflect(file="shared.md")

        assert reflect.file == "shared.md"
        assert reflect.mode == "rw"

    def test_workflow_reflect_stores_authored_values_verbatim(self) -> None:
        """Both fields round-trip authored values verbatim (no path or mode rewriting)."""
        reflect = WorkflowReflect(file="a.md", mode="r")

        assert (reflect.file, reflect.mode) == ("a.md", "r")

    def test_equality_of_identical_constructions(self) -> None:
        """Two instructions with identical fields compare equal.

        The omitted-mode and explicit-``rw`` constructions describe the same
        instruction and must compare equal — the materialized default is
        indistinguishable from the authored value.
        """
        assert WorkflowReflect(file="a.md") == WorkflowReflect(file="a.md", mode="rw")
        assert WorkflowReflect(file="a.md", mode="r") != WorkflowReflect(file="a.md")
