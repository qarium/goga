"""Contract and logic tests for the entities declared in
``goga/history/statuses/CODEMANIFEST`` with ``location: scale.py``:

- ``Stage(name, filepath, before=None, after=None)`` — one scale entry, a
  named position anchored to the artifact that marks it
- ``StatusScale(stages)`` — the assembled partially ordered scale, the
  single source of scale order and maximal-status computation

Pure scale logic — no mocks and no filesystem: presence is decided by the
caller's ``paths`` input alone.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest
from goga.history.statuses import Stage, StatusScale


def _tool_extended_scale(builtin_scale: StatusScale) -> StatusScale:
    """Builtin axis plus two tool entries anchored after ``planned`` in package order."""
    return StatusScale(
        stages=[
            *builtin_scale.stages[:8],  # empty .. planned
            Stage(name="mkdocs.published", filepath="mkdocs/published.md", after="planned"),
            Stage(name="scriba.translated", filepath="scriba/translated.md", after="planned"),
            builtin_scale.stages[8],  # done
        ],
    )


# --- Contract tests ---


class TestScaleContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """``Stage`` and ``StatusScale`` live on the cell facade and its ``__all__``."""
        import goga.history.statuses as cell

        assert cell.Stage is Stage
        assert cell.StatusScale is StatusScale
        assert "Stage" in cell.__all__
        assert "StatusScale" in cell.__all__

    def test_stage_is_a_frozen_kw_only_dataclass(self) -> None:
        """``Stage(name, filepath, before=None, after=None)`` — frozen, keyword-only."""
        stage = Stage(name="defined", filepath="prd.md")

        assert stage.name == "defined"
        assert stage.filepath == "prd.md"
        assert stage.before is None
        assert stage.after is None

        with pytest.raises(TypeError):
            Stage("defined", "prd.md")  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            stage.name = "renamed"  # type: ignore[misc]

    def test_stage_carries_qualified_anchor_names(self) -> None:
        """``before``/``after`` hold the qualified names of the neighbouring entries."""
        stage = Stage(name="mkdocs.published", filepath="mkdocs/published.md", after="planned")

        assert stage.after == "planned"
        assert stage.before is None

    def test_status_scale_is_a_kw_only_dataclass_over_stages(self) -> None:
        """``StatusScale(stages=...)`` — keyword-only; ``stages`` is the scale content."""
        entries = [Stage(name="empty", filepath=""), Stage(name="defined", filepath="prd.md")]
        scale = StatusScale(stages=entries)

        assert isinstance(scale.stages, list)
        assert scale.stages == entries

        with pytest.raises(TypeError):
            StatusScale(entries)  # type: ignore[misc]

    def test_maximal_present_takes_paths_and_returns_status_names(self) -> None:
        """``maximal_present(paths: list[str]) -> list[str]``."""
        parameters = inspect.signature(StatusScale.maximal_present).parameters
        assert list(parameters) == ["self", "paths"]

        scale = StatusScale(stages=[Stage(name="empty", filepath="")])
        result = scale.maximal_present(["notes.txt"])

        assert isinstance(result, list)
        assert all(isinstance(name, str) for name in result)

    def test_resolve_status_returns_the_scale_entry(self) -> None:
        """``resolve_status(name: str) -> Stage`` — the entry carries its ``name``."""
        parameters = inspect.signature(StatusScale.resolve_status).parameters
        assert list(parameters) == ["self", "name"]

        scale = StatusScale(stages=[Stage(name="empty", filepath=""), Stage(name="done", filepath="completed/plan.md")])
        stage = scale.resolve_status("done")

        assert isinstance(stage, Stage)
        assert stage.name == "done"


# --- Logic tests — maximal_present ---


class TestMaximalPresent:
    def test_maximal_present_returns_deepest_artifact_status(self, builtin_scale: StatusScale) -> None:
        """The deepest present artifact of the axis wins; files outside the scale mark nothing."""
        paths = ["prd.md", "adr.md", "task.md", "notes.txt"]

        assert builtin_scale.maximal_present(paths) == ["backlog"]

    def test_maximal_present_done_outranks_flat_artifacts(self, builtin_scale: StatusScale) -> None:
        """The nested ``completed/plan.md`` outranks the flat ``plan.md``."""
        assert builtin_scale.maximal_present(["plan.md", "completed/plan.md"]) == ["done"]

    def test_maximal_present_empty_when_no_artifacts(self, builtin_scale: StatusScale) -> None:
        """No present artifact yields the single built-in name ``empty``."""
        assert builtin_scale.maximal_present([]) == ["empty"]
        assert builtin_scale.maximal_present(["notes.txt"]) == ["empty"]

    def test_maximal_present_title_only_is_new(self, builtin_scale: StatusScale) -> None:
        """The title artifact alone marks the built-in ``new`` entry."""
        assert builtin_scale.maximal_present(["title.txt"]) == ["new"]

    def test_maximal_present_title_with_prd_is_defined(self, builtin_scale: StatusScale) -> None:
        """``title.txt`` below ``prd.md`` — the maximal entry wins, ``new`` is not duplicated."""
        assert builtin_scale.maximal_present(["title.txt", "prd.md"]) == ["defined"]

    def test_maximal_present_empty_and_title_interplay(self, builtin_scale: StatusScale) -> None:
        """``empty`` against ``new``: no artifact and an off-scale artifact stay ``empty``."""
        assert builtin_scale.maximal_present([]) == ["empty"]
        assert builtin_scale.maximal_present(["notes.txt"]) == ["empty"]
        assert builtin_scale.maximal_present(["title.txt"]) == ["new"]

    def test_maximal_present_two_incomparable_tool_statuses(self, builtin_scale: StatusScale) -> None:
        """Two tool entries sharing an anchor are incomparable — both stay maximal."""
        scale = _tool_extended_scale(builtin_scale)
        paths = ["plan.md", "mkdocs/published.md", "scriba/translated.md"]

        assert scale.maximal_present(paths) == ["mkdocs.published", "scriba.translated"]

    def test_maximal_present_before_anchored_entry_stays_below_anchor(self, builtin_scale: StatusScale) -> None:
        """A ``before``-anchored tool entry is strictly below its anchor."""
        scale = StatusScale(
            stages=[
                *builtin_scale.stages[:8],  # empty .. planned
                Stage(name="tool.review", filepath="review.md", before="done"),
                builtin_scale.stages[8],  # done
            ],
        )

        # Both artifacts present — the anchor outranks the tool entry.
        assert scale.maximal_present(["review.md", "completed/plan.md"]) == ["done"]
        # The tool artifact alone — the tool entry is maximal, and so is the
        # axis entry it does not relate to.
        assert scale.maximal_present(["plan.md", "review.md"]) == ["planned", "tool.review"]

    def test_maximal_present_range_entry_between_its_anchors(self, builtin_scale: StatusScale) -> None:
        """A both-anchored range entry outranks its ``after`` and yields to its ``before``."""
        scale = StatusScale(
            stages=[
                *builtin_scale.stages[:8],  # empty .. planned
                Stage(name="tool.range", filepath="range.md", after="defined", before="done"),
                builtin_scale.stages[8],  # done
            ],
        )

        assert scale.maximal_present(["prd.md", "range.md"]) == ["tool.range"]
        assert scale.maximal_present(["range.md", "completed/plan.md"]) == ["done"]
        # The range entry and an unrelated axis entry are both maximal.
        assert scale.maximal_present(["plan.md", "range.md"]) == ["planned", "tool.range"]

    def test_maximal_present_after_chain_is_transitive(self, builtin_scale: StatusScale) -> None:
        """A chain of ``after`` anchors outranks transitively — the deepest wins."""
        scale = StatusScale(
            stages=[
                *builtin_scale.stages[:8],  # empty .. planned
                Stage(name="tool.first", filepath="first.md", after="planned"),
                Stage(name="tool.second", filepath="second.md", after="tool.first"),
                builtin_scale.stages[8],  # done
            ],
        )

        assert scale.maximal_present(["plan.md", "first.md"]) == ["tool.first"]
        assert scale.maximal_present(["first.md", "second.md"]) == ["tool.second"]

    def test_maximal_present_dedupes_repeated_paths(self, builtin_scale: StatusScale) -> None:
        """A repeated path marks its entry once."""
        assert builtin_scale.maximal_present(["plan.md", "plan.md"]) == ["planned"]


# --- Logic tests — resolve_status ---


class TestResolveStatus:
    def test_resolve_status_exact_qualified_name(self, builtin_scale: StatusScale) -> None:
        """The exact qualified name resolves — tool and built-in alike."""
        scale = _tool_extended_scale(builtin_scale)

        assert scale.resolve_status("mkdocs.published").name == "mkdocs.published"
        assert builtin_scale.resolve_status("done").name == "done"

    def test_resolve_status_unknown_name_raises(self, builtin_scale: StatusScale) -> None:
        """An unknown name raises a clean error carrying the entered name."""
        with pytest.raises(ValueError, match=r"unknown status name: 'mkdocs\.published'"):
            builtin_scale.resolve_status("mkdocs.published")
