from __future__ import annotations

import inspect
import typing

import pytest
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

    def test_move_completed_plan_returns_none(self) -> None:
        hints = typing.get_type_hints(move_completed_plan)
        assert hints["return"] is type(None)


class TestMoveCompletedPlanLogic:
    def test_move_completed_plan_moves_to_completed(self, tmp_path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "x.md"
        plan.write_text("P")

        move_completed_plan(str(plan), True, False)

        assert not plan.exists()
        assert (plans_dir / "completed" / "x.md").read_text() == "P"

    @pytest.mark.parametrize(("outcome", "dry_run"), [(False, False), (True, True)])
    def test_move_completed_plan_noop_on_failure_and_dry_run(self, tmp_path, outcome, dry_run) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "x.md"
        plan.write_text("P")

        move_completed_plan(str(plan), outcome, dry_run)

        assert plan.read_text() == "P"
        assert not (plans_dir / "completed").exists()

    def test_move_completed_plan_same_name_overwrites(self, tmp_path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        completed_dir = plans_dir / "completed"
        completed_dir.mkdir(parents=True)
        (completed_dir / "x.md").write_text("OLD")
        plan = plans_dir / "x.md"
        plan.write_text("NEW")

        move_completed_plan(str(plan), True, False)

        assert not plan.exists()
        assert (completed_dir / "x.md").read_text() == "NEW"

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

        move_completed_plan(str(plan), True, False)

        assert (other_dir / "completed" / "feature.md").read_text() == "P"
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
