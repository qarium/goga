from __future__ import annotations

import inspect
import typing

import pytest
from goga.build.hooks import RelocationOutcome
from goga.build.plan_relocation import move_completed_plan


class TestMoveCompletedPlanContract:
    def test_move_completed_plan_importable_from_module(self) -> None:
        assert callable(move_completed_plan)

    def test_move_completed_plan_has_correct_signature(self) -> None:
        sig = inspect.signature(move_completed_plan)
        params = list(sig.parameters.keys())
        assert params == ["plan", "outcome", "dry_run"]

    def test_move_completed_plan_plan_param_is_str(self) -> None:
        hints = typing.get_type_hints(move_completed_plan)
        assert hints["plan"] is str

    def test_move_completed_plan_outcome_param_is_bool(self) -> None:
        hints = typing.get_type_hints(move_completed_plan)
        assert hints["outcome"] is bool

    def test_move_completed_plan_dry_run_param_is_bool(self) -> None:
        hints = typing.get_type_hints(move_completed_plan)
        assert hints["dry_run"] is bool

    def test_move_completed_plan_returns_relocation_outcome(self) -> None:
        hints = typing.get_type_hints(move_completed_plan)
        assert hints["return"] is RelocationOutcome

    def test_relocation_outcome_importable_from_zone_facade(self) -> None:
        import goga.build.hooks as zone

        assert zone.RelocationOutcome is RelocationOutcome


class TestMoveCompletedPlanLogic:
    def test_move_completed_plan_moves_to_completed(self, tmp_path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "x.md"
        plan.write_text("P")

        move_completed_plan(str(plan), True, False)

        assert not plan.exists()
        assert (plans_dir / "completed" / "x.md").read_text() == "P"

    def test_move_completed_plan_returns_relocation_outcome(self, tmp_path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "plan.md"
        plan.write_text("P")

        relocation = move_completed_plan(str(plan), outcome=True, dry_run=False)

        assert relocation.moved is True
        assert relocation.destination == str(tmp_path / "docs" / "plans" / "completed" / "plan.md")
        assert not plan.exists()

        failed = move_completed_plan(str(plan), outcome=False, dry_run=False)
        assert failed.moved is False
        assert failed.destination is None

        plan.write_text("P")
        rehearsal = move_completed_plan(str(plan), outcome=True, dry_run=True)
        assert rehearsal.moved is False
        assert rehearsal.destination is None
        assert plan.read_text() == "P"

    def test_move_completed_plan_is_idempotent_by_name(self, tmp_path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "plan.md"

        plan.write_text("first")
        first = move_completed_plan(str(plan), outcome=True, dry_run=False)
        assert first.moved is True

        plan.write_text("second")
        second = move_completed_plan(str(plan), outcome=True, dry_run=False)

        assert second.moved is True
        assert second.destination == first.destination
        assert (plans_dir / "completed" / "plan.md").read_text() == "second"
        assert not plan.exists()

    @pytest.mark.parametrize(("outcome", "dry_run"), [(False, False), (True, True)])
    def test_move_completed_plan_noop_on_failure_and_dry_run(self, tmp_path, outcome, dry_run) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "x.md"
        plan.write_text("P")

        relocation = move_completed_plan(str(plan), outcome, dry_run)

        assert relocation.moved is False
        assert relocation.destination is None
        assert plan.read_text() == "P"
        assert not (plans_dir / "completed").exists()

    def test_move_completed_plan_relative_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "x.md").write_text("P")

        move_completed_plan("docs/plans/x.md", True, False)

        assert (tmp_path / "docs" / "plans" / "completed" / "x.md").is_file()

    def test_move_completed_plan_dir_follows_plan_location(self, tmp_path) -> None:
        """The completed/ directory is not hardcoded to docs/plans — it sits next to the plan."""
        other_dir = tmp_path / "sprints" / "q3"
        other_dir.mkdir(parents=True)
        plan = other_dir / "feature.md"
        plan.write_text("P")

        relocation = move_completed_plan(str(plan), True, False)

        assert (other_dir / "completed" / "feature.md").read_text() == "P"
        assert relocation.destination == str(other_dir / "completed" / "feature.md")
        assert not (tmp_path / "docs").exists()

    def test_move_completed_plan_creates_nested_completed_dir(self, tmp_path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "x.md"
        plan.write_text("P")

        move_completed_plan(str(plan), True, False)

        assert (plans_dir / "completed").is_dir()

    def test_move_completed_plan_missing_plan_raises(self, tmp_path) -> None:
        """A vanished plan surfaces its OSError to the caller — no silent no-op."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError):
            move_completed_plan(str(plans_dir / "gone.md"), True, False)

    def test_move_completed_plan_read_only_parent_raises(self, tmp_path) -> None:
        """A completed/ that cannot be created propagates the OSError."""
        import os

        if os.geteuid() == 0:  # pragma: no cover - skip when chmod is not enforced
            pytest.skip("permission bits are not enforced for root")
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "x.md"
        plan.write_text("P")
        plans_dir.chmod(0o500)
        try:
            with pytest.raises(PermissionError, match="completed"):
                move_completed_plan(str(plan), True, False)
        finally:
            plans_dir.chmod(0o700)
