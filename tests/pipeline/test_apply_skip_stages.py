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
    WorkflowAssistant,
    WorkflowBuild,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowMemory,
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

    def test_apply_skip_stages_carries_memory_verbatim(self) -> None:
        """The rebuild carries the input's memory configuration verbatim.

        The SAME ``WorkflowMemory`` object (not a rebuild) rides into the
        returned document — a rebuild that dropped it would silently disable
        memory participation for skip-driven runs.
        """
        memory = WorkflowMemory(max_rules=7)
        workflow = WorkflowDocument(
            memory=memory,
            stages={"build": WorkflowStage(agent="codex")},
        )

        result = apply_skip_stages(workflow, ["review"])

        assert result.memory is memory

    def test_apply_skip_stages_none_input_memory_stays_none(self) -> None:
        """A rebuild over a None workflow carries memory=None."""
        result = apply_skip_stages(None, ["x"])

        assert result is not None
        assert result.memory is None

    def test_apply_skip_stages_and_overlay_preserve_profile_and_build(self) -> None:
        """The rebuild carries ``profile`` and the SAME ``build`` object verbatim.

        ``memory`` preservation landed earlier; ``profile`` (activation) and
        ``build`` (build instructions) must survive the rebuild the same way —
        a rebuild that dropped them would change activation or lose build
        instructions for skip-driven runs. Skip still wins per name; a None
        workflow with non-empty skip builds the skip-only document (profile
        None, build None).
        """
        build = WorkflowBuild(agent="codex", env={"A": "1"})
        workflow = WorkflowDocument(
            stages={"build": WorkflowStage(agent="claude"), "test": WorkflowStage()},
            profile="mixa",
            build=build,
        )

        result = apply_skip_stages(workflow, ["build"])

        assert result is not None
        assert result.profile == "mixa"
        assert result.build is build
        # Skip still wins per name — the replacement carries skip=True.
        assert result.stages["build"].skip is True
        # The skip-only document over a None workflow carries no profile/build.
        skip_only = apply_skip_stages(None, ["review"])

        assert skip_only is not None
        assert skip_only.profile is None
        assert skip_only.build is None

    def test_apply_skip_stages_carries_collaboration_verbatim(self) -> None:
        """The rebuild carries the assistants catalog and the delegation block verbatim.

        The SAME catalog dict and delegation object (not rebuilds) ride into
        the returned document, and a surviving stage keeps its attachment
        list — the memory/profile/build carry precedent extended to the
        collaboration fields. A skipped stage's replacement entry carries
        ``assistants=None`` (the constructor default): the compiler removes
        the stage before any attachment resolution, so its attachments are
        unreachable by design. A None workflow with non-empty skip
        synthesizes the default empty catalog and no delegation block.
        """
        catalog = {"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")}
        delegation = WorkflowDelegation(depth=2, max_tasks=7)
        attachments = [WorkflowAssistant(name="reviewer", gate=True, when="finish")]
        workflow = WorkflowDocument(
            assistants=catalog,
            delegation=delegation,
            stages={"build": WorkflowStage(), "verify": WorkflowStage(assistants=attachments)},
        )

        result = apply_skip_stages(workflow, ["build"])

        assert result is not None
        assert result.assistants is catalog
        assert result.delegation is delegation
        # The surviving stage keeps its attachment list (the same object).
        assert result.stages["verify"].assistants is attachments
        # The skipped stage's wholesale replacement carries the constructor
        # default — its attachments never reach the compiler.
        assert result.stages["build"].skip is True
        assert result.stages["build"].assistants is None
        # The skip-only document over a None workflow starts collaboration-free.
        skip_only = apply_skip_stages(None, ["build"])

        assert skip_only is not None
        assert skip_only.assistants == {}
        assert skip_only.delegation is None


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
        assert result.stages["build"].loop is None
        assert result.stages["build"].skills is None
        # The wholesale replacement drops the memory instructions too — the
        # WorkflowStage(skip=True) constructor defaults (a skipped stage never
        # participates; the compiler removes it before any memory assembly).
        assert result.stages["build"].reflect is None
        assert result.stages["build"].memory is None

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

    def test_apply_skip_stages_does_not_mutate_memory(self) -> None:
        """The input's memory configuration and stages map survive the rebuild."""
        workflow = WorkflowDocument(
            memory=WorkflowMemory(max_rules=7),
            stages={"build": WorkflowStage(agent="codex")},
        )

        result = apply_skip_stages(workflow, ["review"])

        # The rebuild carries the memory verbatim; the input keeps its own.
        assert result.memory == WorkflowMemory(max_rules=7)
        assert workflow.memory == WorkflowMemory(max_rules=7)
        # The input stages map is unchanged.
        assert set(workflow.stages.keys()) == {"build"}
        assert workflow.stages["build"].agent == "codex"
        assert workflow.stages["build"].skip is False

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

    def test_skip_replaces_notes_entry(self) -> None:
        """A skipped name's replacement stage carries notes=None (model default)."""
        workflow = WorkflowDocument(
            stages={
                "a": WorkflowStage(notes={"x": "1"}),
                "b": WorkflowStage(notes={"y": "2"}),
            },
        )

        result = apply_skip_stages(workflow, ["a"])

        # The wholesale replacement carries skip=True and the notes model
        # default (None) — dropped notes are unreachable by design (the
        # compiler removes the stage before any notes application).
        assert result.stages["a"].notes is None
        assert result.stages["a"].skip is True
        # The input document is unchanged.
        assert workflow.stages["a"].notes == {"x": "1"}
        assert workflow.stages["a"].skip is False

    def test_apply_skip_stages_preserves_notes_of_other_stages(self) -> None:
        """Surviving stages keep their notes through the shallow stages copy."""
        workflow = WorkflowDocument(
            stages={
                "a": WorkflowStage(notes={"x": "1"}),
                "b": WorkflowStage(notes={"y": "2"}),
            },
        )

        result = apply_skip_stages(workflow, ["a"])

        assert result.stages["b"].notes == {"y": "2"}
