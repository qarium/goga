"""Integration: the pipeline command driving the real topics domain.

Cross-package coverage (commands.pipeline + goga.topics + goga.history) moved
from tests/commands/pipeline/test_pipeline_dispatch.py per the integration-suite
placement rule. Only the domain's git boundary is canned; the deterministic
scale comes from the shared ``builtin_scale`` fixture of ``tests/conftest.py``
and the minimal ``ProjectConfig`` factory from the pipeline suite's conftest.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands.pipeline import pipeline
from goga.history import current_year
from goga.history.statuses import StatusScale
from goga.topics import board as topics_board
from goga.topics import creation as topics_creation
from goga.topics import ensuring as topics_ensuring
from goga.topics import switching as topics_switching
from goga.topics.git import BranchRef

from tests.commands.pipeline.conftest import make_config as _make_config

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


# --- Integration tests (the real topics-domain switch through the real command) ---


def _trees_reader(trees: dict[str, list[str]]):
    """A ``read_ref_tree_paths`` stand-in answering by ref display name."""

    def read(ref: str, prefix: str) -> list[str]:
        return [path for path in trees.get(ref, []) if path.startswith(prefix)]

    return read


def _wire_topic_domain(
    monkeypatch: pytest.MonkeyPatch,
    scale: StatusScale,
    inventory: list[BranchRef],
    trees: dict[str, list[str]],
    current: str | None,
) -> tuple[mock.Mock, mock.Mock, mock.Mock, mock.Mock]:
    """Wire the REAL ``ensure_topic`` to a canned git boundary.

    The resolution reads the scale, the ref inventory, the ref trees, and the
    current branch at their import points inside the topics domain (the same
    points the domain's own tests patch); the switch mutations are recording
    mocks. The fast creation of ``ensure_topic`` at zero candidates runs the
    REAL occupancy oracles — so the creation module's git boundary (the
    inventory, the current branch, and the branch-tree slug oracle) is wired
    the same way — and the REAL topic-directory creation; only its
    create-and-switch mutation is a recording mock at ``ensuring``'s import
    point. Only the topics facade stays real — exactly the wiring
    ``pipeline`` relies on through ``from ...topics import ensure_topic``.

    Returns:
        The cleanliness probe, the local checkout, the remote-tracking branch
        creation, and the create-and-switch mutation of the fast creation
        — all as recording mocks.
    """
    monkeypatch.setattr(topics_switching, "assemble_status_scale", lambda: scale)
    monkeypatch.setattr(topics_switching, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(topics_switching, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(topics_board, "read_ref_tree_paths", _trees_reader(trees))

    cleanliness = mock.Mock(return_value=True)
    checkout = mock.Mock()
    remote_creation = mock.Mock()
    monkeypatch.setattr(topics_switching, "is_working_tree_clean", cleanliness)
    monkeypatch.setattr(topics_switching, "checkout_local_branch", checkout)
    monkeypatch.setattr(topics_switching, "create_branch_from_remote_tracking", remote_creation)

    monkeypatch.setattr(topics_creation, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(topics_creation, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(topics_creation, "read_ref_tree_paths", _trees_reader(trees))
    create_and_switch = mock.Mock()
    monkeypatch.setattr(topics_ensuring, "create_and_switch_branch", create_and_switch)
    return cleanliness, checkout, remote_creation, create_and_switch


class TestPipelineTopicIntegration:
    """Cross-entity: the real ``ensure_topic`` from the topics domain through the real command.

    Only the domain's git boundary is canned, so these tests verify the wiring
    the unit tests mock away: the ``from ...topics import`` path, the run-form
    guard, the argument handed to the domain, and the ordering guarantee —
    step-2 validation, topic procedure, topic line, docker activity.
    """

    def test_pipeline_topic_flow_switches_and_launches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, builtin_scale: StatusScale
    ) -> None:
        """Flow happy path: the domain switches, its line prints, the launcher runs topic-free."""
        monkeypatch.chdir(tmp_path)
        year = current_year()
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="feat/a", remote=False),
        ]
        trees = {"feat/a": [f".goga/history/{year}/feat-a/plan.md"]}
        _cleanliness, checkout, _remote, _fresh = _wire_topic_domain(
            monkeypatch, builtin_scale, inventory, trees, "main"
        )

        config = _make_config()
        runner = CliRunner()

        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["-t", "feat/a", "my-pipeline"])

        assert result.exit_code == 0
        assert "Switched to branch feat/a" in result.stdout
        checkout.assert_called_once_with("feat/a")
        assert mock_run.call_count == 1
        assert mock_run.call_args.kwargs["name"] == "my-pipeline"
        # The topic identifier never crosses the docker boundary.
        assert "topic" not in mock_run.call_args.kwargs
        assert "feat/a" not in mock_run.call_args.kwargs.values()

    def test_pipeline_topic_idempotent_host_skips_git_mutations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, builtin_scale: StatusScale
    ) -> None:
        """Already on the host branch: the confirmation line prints and git is untouched."""
        monkeypatch.chdir(tmp_path)
        year = current_year()
        inventory = [BranchRef(name="feat/a", remote=False)]
        trees = {"feat/a": [f".goga/history/{year}/feat-a/plan.md"]}
        cleanliness, checkout, remote_creation, fresh_creation = _wire_topic_domain(
            monkeypatch, builtin_scale, inventory, trees, "feat/a"
        )

        config = _make_config()
        runner = CliRunner()

        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["-t", "feat/a", "my-pipeline"])

        assert result.exit_code == 0
        assert "Already on branch feat/a" in result.stdout
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        remote_creation.assert_not_called()
        fresh_creation.assert_not_called()
        assert mock_run.call_count == 1

    def test_pipeline_topic_unresolved_identifier_creates_and_launches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, builtin_scale: StatusScale
    ) -> None:
        """An identifier nothing hosts: fresh work is created — the branch as
        entered, the topic directory of the year — the creation line prints,
        and the launcher runs topic-free."""
        monkeypatch.chdir(tmp_path)
        year = current_year()
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": [f".goga/history/{year}/other/prd.md"]}
        _cleanliness, checkout, _remote, fresh_creation = _wire_topic_domain(
            monkeypatch, builtin_scale, inventory, trees, "main"
        )

        config = _make_config()
        runner = CliRunner()

        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["-t", "nope", "my-pipeline"])

        assert result.exit_code == 0
        assert f"Created branch nope and topic {year}/nope" in result.stdout
        fresh_creation.assert_called_once_with("nope")
        checkout.assert_not_called()
        assert (tmp_path / ".goga" / "history" / year / "nope").is_dir()
        assert mock_run.call_count == 1
        assert "topic" not in mock_run.call_args.kwargs
