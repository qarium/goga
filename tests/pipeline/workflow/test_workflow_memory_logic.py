"""Logic tests for the ``WorkflowMemory`` dataclass.

Covers construction behavior beyond the contract surface: the materialized
defaults (values, not omissions) and the verbatim round-trip of every authored
field. The defaults pin is load-bearing downstream — the consumer
default-constructs ``WorkflowMemory()`` when the workflow carries no block and
sources ``max_rules`` / ``commit`` (and the default method) from the field
defaults, so a silent shift of these values would change compiled output.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowMemory


class TestWorkflowMemoryLogic:
    """Logic tests — construction behavior of the ``WorkflowMemory`` dataclass."""

    def test_workflow_memory_defaults_are_materialized(self) -> None:
        """Constructing with no arguments yields the materialized authoring defaults.

        method "reflect", path None, max_rules 25, commit False, mode None —
        the values the emission case «no ``memory:`` block authored» sources.
        The pin prevents a silent drift of the defaults into compiled output.
        """
        config = WorkflowMemory()

        assert config.method == "reflect"
        assert config.path is None
        assert config.max_rules == 25
        assert config.commit is False
        assert config.mode is None

    def test_workflow_memory_stores_authored_values_verbatim(self) -> None:
        """Every field round-trips an authored block verbatim (no composition, no rewrite)."""
        config = WorkflowMemory(method="alignment", path="p", max_rules=9, commit=True, mode="r")

        assert config.method == "alignment"
        assert config.path == "p"
        assert config.max_rules == 9
        assert config.commit is True
        assert config.mode == "r"

    def test_equality_of_identical_constructions(self) -> None:
        """Two configurations with identical fields compare equal.

        The no-block default equals an explicitly authored ``memory: {}`` —
        both describe the same configuration, so the parser's materialized
        block and the consumer's default construction must compare equal.
        """
        assert WorkflowMemory() == WorkflowMemory(method="reflect", path=None, max_rules=25, commit=False, mode=None)
