"""Contract and logic tests for the ``apply_skip_stages`` Routine.

The pipeline cell's CODEMANIFEST declares a pure Routine ``apply_skip_stages``
that merges CLI skip directives into a declarative
:class:`~goga.pipeline.workflow.WorkflowDocument` without mutating the input and
without validating stage names. The resulting document carries
:class:`~goga.pipeline.workflow.WorkflowStage`-s with ``skip=True`` so the
downstream :func:`~goga.pipeline.compiler.compile_flow` removes those stages and
reconnects their dependents' ``depends_on``.

Contract tests pin the facade surface (importability from ``goga.pipeline``,
the ``(workflow, skip_stages)`` signature, the ``WorkflowDocument | None``
return type). Logic tests cover the verbatim behavior from the design: empty
skip is a no-op (identity), skip always wins, the input is never mutated, names
are never validated, and a ``None`` workflow with non-empty skip constructs a
fresh skip-only document.
"""

from __future__ import annotations

import inspect

from goga.pipeline import apply_skip_stages
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowStage,
)


class TestApplySkipStagesContract:
    """Contract tests — the public API declared by the pipeline-cell CODEMANIFEST."""

    def test_apply_skip_stages_importable_from_facade(self) -> None:
        """apply_skip_stages must be importable from the goga.pipeline facade."""
        assert apply_skip_stages is not None

    def test_apply_skip_stages_signature(self) -> None:
        """apply_skip_stages exposes the (workflow, skip_stages) parameter list."""
        parameters = list(inspect.signature(apply_skip_stages).parameters)
        assert parameters == ["workflow", "skip_stages"]

    def test_apply_skip_stages_return_annotation(self) -> None:
        """apply_skip_stages declares a return type of WorkflowDocument | None."""
        annotation = inspect.signature(apply_skip_stages).return_annotation
        # With `from __future__ import annotations` the annotation is a string;
        # without it, it is the evaluated union. Accept either form.
        acceptable = {"WorkflowDocument | None", WorkflowDocument | None}
        assert annotation in acceptable


class TestApplySkipStagesLogic:
    """Logic tests — the verbatim behavior from the design Test Stack Trace."""

    def test_apply_skip_stages_empty_is_noop(self) -> None:
        """An empty skip_stages list returns the input unchanged (identity)."""
        workflow = WorkflowDocument(
            prompt="keep",
            stages={"build": WorkflowStage(agent="codex")},
        )

        result = apply_skip_stages(workflow, [])

        assert result is workflow
        # The input map was not touched.
        assert workflow.stages["build"].agent == "codex"

    def test_apply_skip_stages_none_empty_is_noop(self) -> None:
        """apply_skip_stages(None, []) returns None — empty skip is a no-op."""
        result = apply_skip_stages(None, [])

        assert result is None

    def test_apply_skip_stages_skip_wins_over_existing(self) -> None:
        """A skipped name fully replaces any pre-existing override (skip wins)."""
        workflow = WorkflowDocument(
            prompt="P",
            stages={"build": WorkflowStage(agent="codex", prompt="override")},
        )

        result = apply_skip_stages(workflow, ["build"])

        assert result is not workflow
        assert result.stages["build"].skip is True
        assert result.stages["build"].agent is None
        assert result.stages["build"].prompt is None

    def test_apply_skip_stages_none_nonempty_constructs_doc(self) -> None:
        """A None workflow with non-empty skip constructs a fresh skip-only doc."""
        result = apply_skip_stages(None, ["review"])

        assert result is not None
        assert result.prompt is None
        assert set(result.stages.keys()) == {"review"}
        assert result.stages["review"].skip is True
        assert result.extend == {}

    def test_apply_skip_stages_preserves_prompt_and_extend(self) -> None:
        """A non-None workflow preserves prompt, existing stages, and extend."""
        extend = {"extra": WorkflowExtendStage(after=["build"], body={"title": "Extra"})}
        workflow = WorkflowDocument(
            prompt="P",
            stages={"build": WorkflowStage(agent="codex")},
            extend=extend,
        )

        result = apply_skip_stages(workflow, ["test"])

        assert result.prompt == "P"
        # Existing stage preserved; new skip stage added.
        assert result.stages["build"].agent == "codex"
        assert result.stages["build"].skip is False
        assert result.stages["test"].skip is True
        # Extend map preserved.
        assert result.extend == extend

    def test_apply_skip_stages_does_not_mutate_input(self) -> None:
        """The input workflow and its maps are never mutated."""
        workflow = WorkflowDocument(
            prompt="keep",
            stages={"build": WorkflowStage(agent="codex")},
        )

        apply_skip_stages(workflow, ["build", "test"])

        # Input prompt untouched.
        assert workflow.prompt == "keep"
        # The existing stage's skip flag is unchanged.
        assert workflow.stages["build"].skip is False
        # A brand-new skip name was NOT injected into the input map.
        assert "test" not in workflow.stages
        assert set(workflow.stages.keys()) == {"build"}

    def test_apply_skip_stages_does_not_validate_names(self) -> None:
        """An unknown skip name is accepted — validation is the compiler's job."""
        workflow = WorkflowDocument(prompt="P", stages={"build": WorkflowStage(agent="codex")})

        # Must NOT raise — this Routine stays declarative.
        result = apply_skip_stages(workflow, ["totally_unknown"])

        assert result.stages["totally_unknown"].skip is True

    def test_apply_skip_stages_idempotent_duplicate_name(self) -> None:
        """A duplicate skip name produces a single entry (dict-key idempotency)."""
        workflow = WorkflowDocument(prompt="P", stages={})

        result = apply_skip_stages(workflow, ["build", "build"])

        assert set(result.stages.keys()) == {"build"}
        assert result.stages["build"].skip is True
