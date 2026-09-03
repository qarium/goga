"""Contract and logic tests for the routine declared in
``goga/history/CODEMANIFEST`` with ``location: prune.py``:

- ``prune_topics(year: str | None = None, dry_run: bool = False) -> removed: list[str]``

The orphan decision is the unit under test. The tree inventory is real
(``tmp_path`` + ``monkeypatch.chdir``); the git boundary is mocked at the
import site — ``goga.history.prune.list_branch_refs`` — except in the
filesystem-only test, which intercepts ``subprocess.run`` of the nested git
cell; the clock is the mandated ``naming.datetime`` point patched with a
fixed date. The facade exposure of the routine belongs to the facade task.
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from goga.history import naming, prune
from goga.history.git import BranchRef
from goga.history.naming import normalize_topic_slug
from goga.history.prune import prune_topics
from goga.topics.creation import check_branch_occupancy


class _FixedClock:
    """Stand-in for ``datetime`` answering a fixed naive date."""

    @staticmethod
    def now() -> datetime:
        return datetime(2026, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock


def _topic(root: Path, year: str, name: str, *artifacts: str) -> Path:
    """Create one topic directory of a year, with optional artifact files."""
    topic_dir = root / ".goga" / "history" / year / name
    topic_dir.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        path = topic_dir / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact, encoding="utf-8")
    return topic_dir


def _inventory(refs: list[BranchRef]) -> mock._patch[mock.Mock]:
    """Patch the git boundary of the prune module with a fixed inventory."""
    return mock.patch("goga.history.prune.list_branch_refs", return_value=refs)


def _inventory_run(heads: str, remotes: str) -> mock.Mock:
    """A ``subprocess.run`` stand-in answering the two ``for-each-ref`` calls."""
    answers = {"refs/heads": heads, "refs/remotes": remotes}

    def answering(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=answers[command[3]])

    return mock.Mock(side_effect=answering)


# --- Contract tests ---


class TestPruneContract:
    def test_routine_is_importable_from_module_and_callable(self) -> None:
        """``prune_topics`` is importable from ``goga.history.prune`` and callable."""
        assert callable(prune_topics)
        assert prune.prune_topics is prune_topics

    def test_prune_topics_signature(self) -> None:
        """``prune_topics(year: str | None = None, dry_run: bool = False) -> list[str]``."""
        signature = inspect.signature(prune_topics)
        assert list(signature.parameters) == ["year", "dry_run"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert signature.parameters["dry_run"].default is False
        hints = typing.get_type_hints(prune_topics)
        assert hints == {"year": str | None, "dry_run": bool, "return": list[str]}
        bound = inspect.signature(prune_topics).bind(year="2025", dry_run=True)
        assert bound.arguments == {"year": "2025", "dry_run": True}


# --- Logic tests ---


class TestPruneTopics:
    def test_prune_topics_deletes_orphans_keeps_hosted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Orphans go — a done orphan on equal terms; the hosted topic of the year stays."""
        monkeypatch.chdir(tmp_path)
        hosted = _topic(tmp_path, "2026", "feat-a", "prd.md")
        done = _topic(tmp_path, "2026", "done-c", "completed/plan.md")
        orphan = _topic(tmp_path, "2026", "orphan-b", "prd.md")
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="origin/feat/a", remote=True),
        ]
        with _inventory(inventory):
            removed = prune_topics("2026")
        assert removed == ["done-c", "orphan-b"]
        assert hosted.is_dir()
        assert not done.exists()
        assert not orphan.exists()

    def test_prune_remote_short_name_protects(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The short name of a remote-tracking ref protects without a local branch."""
        monkeypatch.chdir(tmp_path)
        topic_dir = _topic(tmp_path, "2026", "feat-a", "prd.md")
        with _inventory([BranchRef(name="origin/feat/a", remote=True)]):
            assert prune_topics("2026") == []
        assert topic_dir.is_dir()

    def test_prune_protection_is_year_independent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A branch protects same-named topics of every year — the default and an explicit year."""
        inventory = [BranchRef(name="feat/a", remote=False)]

        def build(root: Path) -> tuple[Path, Path]:
            return _topic(root, "2025", "feat-a", "prd.md"), _topic(root, "2026", "feat-a", "prd.md")

        current_year_root = tmp_path / "current"
        explicit_year_root = tmp_path / "explicit"
        old_current, new_current = build(current_year_root)
        old_explicit, new_explicit = build(explicit_year_root)
        with mock.patch.object(naming, "datetime", _FixedClock), _inventory(inventory):
            monkeypatch.chdir(current_year_root)
            assert prune_topics() == []
            monkeypatch.chdir(explicit_year_root)
            assert prune_topics("2025") == []
        assert old_current.is_dir()
        assert new_current.is_dir()
        assert old_explicit.is_dir()
        assert new_explicit.is_dir()

    def test_prune_dry_run_lists_what_real_run_deletes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The dry pass lists exactly what the real pass deletes — and deletes nothing itself."""
        dry_root = tmp_path / "dry"
        wet_root = tmp_path / "wet"

        def build(root: Path) -> tuple[Path, Path]:
            return _topic(root, "2026", "orphan-b", "prd.md"), _topic(root, "2026", "done-c", "completed/plan.md")

        dry_orphan, dry_done = build(dry_root)
        wet_orphan, wet_done = build(wet_root)
        with _inventory([]):
            monkeypatch.chdir(dry_root)
            assert prune_topics("2026", dry_run=True) == ["done-c", "orphan-b"]
            monkeypatch.chdir(wet_root)
            assert prune_topics("2026") == ["done-c", "orphan-b"]
        assert dry_orphan.is_dir()
        assert dry_done.is_dir()
        assert not wet_orphan.exists()
        assert not wet_done.exists()

    def test_prune_topics_returns_sorted_unique_slugs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The result is the sorted orphan slug set — no duplicates, dry or wet alike."""
        monkeypatch.chdir(tmp_path)
        _topic(tmp_path, "2026", "b-orphan", "prd.md")
        _topic(tmp_path, "2026", "a-orphan", "prd.md")
        with _inventory([]):
            assert prune_topics("2026", dry_run=True) == ["a-orphan", "b-orphan"]


class TestPruneTopicsOracle:
    def test_prune_oracle_matches_check_branch_occupancy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The orphan decision agrees with the creation occupancy oracle on exact branch names."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="origin/hot/b", remote=True),
            BranchRef(name="main", remote=False),
        ]
        for entered in ["feat/a", "hot/b", "main", "other"]:
            slug = normalize_topic_slug(entered)
            # (1) the occupancy oracle on the empty tree — only the git oracles answer
            with mock.patch("goga.topics.creation.list_branch_refs", return_value=inventory):
                occupied = check_branch_occupancy(entered, slug, "2026") is not None
            # (2) the topic directory of the slug comes to exist
            _topic(tmp_path, "2026", slug)
            # (3) the prune oracle measures the same names
            with _inventory(inventory):
                candidates = prune_topics("2026", dry_run=True)
            assert occupied == (slug not in candidates), entered


class TestPruneTopicsNegatives:
    def test_prune_topics_absent_year_returns_empty_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An absent year yields no topics — nothing is deleted, nothing is touched."""
        monkeypatch.chdir(tmp_path)
        kept = _topic(tmp_path, "2026", "feat-a", "prd.md")
        with (
            _inventory([BranchRef(name="feat/a", remote=False)]),
            mock.patch("goga.history.prune.remove_topic_dir") as remover,
        ):
            assert prune_topics("1999") == []
        remover.assert_not_called()
        assert kept.is_dir()

    def test_prune_topics_queries_inventory_even_for_empty_year(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A year without topics still reads the branch inventory — no short-circuit."""
        monkeypatch.chdir(tmp_path)
        with _inventory([]) as inventory:
            assert prune_topics("1999") == []

        inventory.assert_called_once_with()

    def test_prune_topics_propagates_inventory_git_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A git failure of the ref listing propagates to the caller."""
        monkeypatch.chdir(tmp_path)
        failure = subprocess.CalledProcessError(returncode=128, cmd=["git", "for-each-ref"])
        with (
            mock.patch("goga.history.prune.list_branch_refs", side_effect=failure),
            pytest.raises(subprocess.CalledProcessError),
        ):
            prune_topics("2026")

    def test_prune_topics_never_mutates_git(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The only git invocations of the flow are the read-only ref listings — wet and dry alike."""
        monkeypatch.chdir(tmp_path)
        orphan = _topic(tmp_path, "2026", "orphan-b", "prd.md")
        done = _topic(tmp_path, "2026", "done-c", "completed/plan.md")
        runner = _inventory_run(heads="main\n", remotes="")
        with mock.patch("goga.history.git.refs.subprocess.run", runner):
            assert prune_topics("2026", dry_run=True) == ["done-c", "orphan-b"]
            assert orphan.is_dir()
            assert done.is_dir()
            assert prune_topics("2026") == ["done-c", "orphan-b"]
        assert not orphan.exists()
        assert not done.exists()
        assert runner.call_count == 4  # two ref listings per pass, one dry and one wet
        for call in runner.call_args_list:
            command = call.args[0]
            assert command[:2] == ["git", "for-each-ref"]
            assert not {"branch", "push", "update-ref", "checkout", "rm"} & set(command)


class TestPruneTopicsEdges:
    def test_prune_topics_empty_tree_returns_empty_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing history root is an empty result — not an error, and nothing is created."""
        monkeypatch.chdir(tmp_path)
        with _inventory([]):
            assert prune_topics() == []
        assert not (tmp_path / ".goga").exists()

    def test_prune_topics_only_resolved_year_touched(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An explicit year scopes the cleanup — other years stay untouched."""
        monkeypatch.chdir(tmp_path)
        old = _topic(tmp_path, "2025", "orphan-old", "prd.md")
        new = _topic(tmp_path, "2026", "orphan-new", "prd.md")
        with mock.patch.object(naming, "datetime", _FixedClock), _inventory([]):
            assert prune_topics("2025") == ["orphan-old"]
        assert not old.exists()
        assert (tmp_path / ".goga" / "history" / "2025").is_dir()  # the emptied year directory stays
        assert new.is_dir()

    def test_prune_topics_empty_string_year_means_current_year(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty-string year is "not set" — the current year alone supplies the candidates."""
        monkeypatch.chdir(tmp_path)
        old = _topic(tmp_path, "2025", "orphan-old", "prd.md")
        new = _topic(tmp_path, "2026", "orphan-new", "prd.md")
        with mock.patch.object(naming, "datetime", _FixedClock), _inventory([]):
            assert prune_topics("", dry_run=True) == ["orphan-new"]
        assert old.is_dir()
        assert new.is_dir()

    def test_prune_topics_normalizes_tree_names_for_protection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A manual unnormalized directory is protected through its normalized slug."""
        monkeypatch.chdir(tmp_path)
        manual = _topic(tmp_path, "2026", "Feature_Foo", "prd.md")
        twin = _topic(tmp_path, "2026", "feature-foo", "prd.md")
        with _inventory([BranchRef(name="feature/foo", remote=False)]):
            assert prune_topics("2026") == []
        assert manual.is_dir()
        assert twin.is_dir()

    def test_prune_topics_unnormalized_orphan_dir_stays(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A manual unnormalized orphan is listed but unreachable for deletion — wet and dry agree."""
        dry_root = tmp_path / "dry"
        wet_root = tmp_path / "wet"
        dry_manual = _topic(dry_root, "2026", "Feature_Foo", "prd.md")
        wet_manual = _topic(wet_root, "2026", "Feature_Foo", "prd.md")
        with _inventory([]):
            monkeypatch.chdir(dry_root)
            assert prune_topics("2026", dry_run=True) == ["feature-foo"]
            monkeypatch.chdir(wet_root)
            assert prune_topics("2026") == ["feature-foo"]
        assert dry_manual.is_dir()
        assert wet_manual.is_dir()
