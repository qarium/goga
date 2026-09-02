"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: deletion.py``:

- ``DeleteTarget(topic, branch, remote, has_dir)`` — one identified
  deletion target
- ``resolve_delete_targets(identifiers, year)`` — the read-only resolution

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched: the inventory,
the ref-tree reading, and the current branch are patched at
``goga.topics.deletion``. The disk tree is real on ``tmp_path`` via
``monkeypatch.chdir`` — ``collect_history_tree`` runs against it.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
import typing
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.topics import DeleteTarget, deletion, resolve_delete_targets
from goga.topics.git import BranchRef

# --- Shared scenario helpers ---


def _trees_reader(trees: dict[str, list[str]]) -> Callable[..., list[str]]:
    """A ``read_ref_tree_paths`` stand-in answering by ref display name."""

    def read(ref: str, prefix: str) -> list[str]:
        assert prefix == ".goga/history/2026/", "the resolution reads under the year prefix only"
        return [path for path in trees.get(ref, []) if path.startswith(prefix)]

    return read


def _wire_resolution(
    monkeypatch: pytest.MonkeyPatch,
    inventory: list[BranchRef],
    trees: dict[str, list[str]],
    current: str | None,
) -> None:
    """Patch the resolution's import points: git inventory, trees, branch."""
    monkeypatch.setattr(deletion, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(deletion, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(deletion, "read_ref_tree_paths", _trees_reader(trees))


def _disk_topic(cwd: Path, year: str, slug: str) -> None:
    """Create the on-disk topic directory of the year."""
    (cwd / ".goga" / "history" / year / slug).mkdir(parents=True, exist_ok=True)


def _twin_inventory() -> list[BranchRef]:
    """The design-scenario inventory: a local branch and its remote twin."""
    return [
        BranchRef(name="feature-foo", remote=False),
        BranchRef(name="origin/feature-foo", remote=True),
    ]


def _twin_trees() -> dict[str, list[str]]:
    """The design-scenario ref trees: one topic on both refs."""
    return {
        "feature-foo": [".goga/history/2026/feature-foo/plan.md"],
        "origin/feature-foo": [".goga/history/2026/feature-foo/plan.md"],
    }


# --- Contract tests ---


class TestDeletionContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """``DeleteTarget`` and the resolver live on the cell facade."""
        import goga.topics as cell

        assert cell.DeleteTarget is DeleteTarget
        assert cell.resolve_delete_targets is resolve_delete_targets
        for name in ("DeleteTarget", "resolve_delete_targets"):
            assert name in cell.__all__

    def test_delete_target_is_a_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the four declared fields."""
        assert dataclasses.is_dataclass(DeleteTarget)
        assert DeleteTarget.__dataclass_params__.frozen is True
        assert DeleteTarget.__dataclass_params__.kw_only is True
        assert typing.get_type_hints(DeleteTarget) == {
            "topic": str,
            "branch": str | None,
            "remote": str | None,
            "has_dir": bool,
        }
        target = DeleteTarget(topic="x", branch=None, remote=None, has_dir=True)
        assert target.topic == "x"
        assert target.branch is None
        assert target.remote is None
        assert target.has_dir is True
        with pytest.raises(dataclasses.FrozenInstanceError):
            target.topic = "other"  # type: ignore[misc]
        with pytest.raises(TypeError):
            DeleteTarget("x", None, None, True)  # type: ignore[misc]

    def test_resolve_delete_targets_signature(self) -> None:
        """``resolve_delete_targets(identifiers, year=None) -> list[...]``."""
        signature = inspect.signature(resolve_delete_targets)
        assert list(signature.parameters) == ["identifiers", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert typing.get_type_hints(resolve_delete_targets) == {
            "identifiers": list[str],
            "year": str | None,
            "return": list[DeleteTarget],
        }


# --- Logic tests: the resolution tiers ---


class TestResolveDeleteTargets:
    def test_resolve_delete_targets_exact_slug_with_unhosted_disk_topic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A disk topic no branch hosts is a target — directory only."""
        monkeypatch.chdir(tmp_path)
        _disk_topic(tmp_path, "2026", "orphan-topic")
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="origin/other", remote=True),
        ]
        _wire_resolution(monkeypatch, inventory, {"main": []}, "main")

        targets = resolve_delete_targets(["orphan-topic"], year="2026")

        assert targets == [DeleteTarget(topic="orphan-topic", branch=None, remote=None, has_dir=True)]

    def test_resolve_delete_targets_collapses_local_and_origin_twin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The branch name and its twin name identify one target with both refs."""
        monkeypatch.chdir(tmp_path)
        _disk_topic(tmp_path, "2026", "feature-foo")
        _wire_resolution(monkeypatch, _twin_inventory(), _twin_trees(), "main")

        targets = resolve_delete_targets(["feature-foo", "origin/feature-foo"], year="2026")

        assert targets == [
            DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)
        ]

    def test_resolve_delete_targets_twin_collapse_order_independent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both identifier orders return the identical single target (fix D8)."""
        monkeypatch.chdir(tmp_path)
        _disk_topic(tmp_path, "2026", "feature-foo")
        _wire_resolution(monkeypatch, _twin_inventory(), _twin_trees(), "main")

        twin_first = resolve_delete_targets(["origin/feature-foo", "feature-foo"], year="2026")
        local_first = resolve_delete_targets(["feature-foo", "origin/feature-foo"], year="2026")

        expected = [
            DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)
        ]
        assert twin_first == expected
        assert local_first == expected

    def test_resolve_delete_targets_ambiguous_error_all_or_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Several topics in the winning tier cancel the whole call."""
        monkeypatch.chdir(tmp_path)
        _disk_topic(tmp_path, "2026", "orphan-topic")
        inventory = [BranchRef(name="feature-foo", remote=False)]
        trees = {
            "feature-foo": [
                ".goga/history/2026/feature-foo/plan.md",
                ".goga/history/2026/feature-foobar/plan.md",
            ]
        }
        _wire_resolution(monkeypatch, inventory, trees, "main")

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["feature-foo", "orphan-topic"], year="2026")

        assert "feature-foo" in raised.value.message
        assert "feature-foobar" in raised.value.message

    def test_resolve_delete_targets_current_branch_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A target hosted by the current branch is a clean error — switch away."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="feature-foo", remote=False)]
        trees = {"feature-foo": [".goga/history/2026/feature-foo/plan.md"]}
        _wire_resolution(monkeypatch, inventory, trees, "feature-foo")

        with pytest.raises(click.ClickException, match="switch"):
            resolve_delete_targets(["feature-foo"], year="2026")

    def test_resolve_delete_targets_merged_topic_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A topic hosted only by integration refs is merged work, not a target (fix D3)."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="origin/main", remote=True),
        ]
        trees = {
            "main": [".goga/history/2026/feature-x/plan.md"],
            "origin/main": [".goga/history/2026/feature-x/plan.md"],
        }
        _wire_resolution(monkeypatch, inventory, trees, "other")

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["feature-x"], year="2026")

        assert "feature-x" in raised.value.message
        assert "main" in raised.value.message

    def test_resolve_delete_targets_integration_branch_named_directly_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The merged-work guard applies through the exact-branch tier too (fix D3)."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": [".goga/history/2026/cleanup/plan.md"]}
        _wire_resolution(monkeypatch, inventory, trees, "other")

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["main"], year="2026")

        assert "main" in raised.value.message
        assert "cleanup" in raised.value.message

    def test_resolve_delete_targets_branch_without_topic_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare branch hosting nothing resolves to no topic — deletion deletes topics."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="gh-pages", remote=False)]
        _wire_resolution(monkeypatch, inventory, {}, "main")

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["gh-pages"], year="2026")

        assert "gh-pages" in raised.value.message

    def test_resolve_delete_targets_no_match_names_identifier(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An identifier nothing matches is a clean error naming it."""
        monkeypatch.chdir(tmp_path)
        _wire_resolution(monkeypatch, [], {}, "main")

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["nope"], year="2026")

        assert "nope" in raised.value.message


# --- Infrastructure boundary ---


class TestDeletionInfrastructureBoundary:
    def test_git_failure_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A git infrastructure failure with stderr becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        failure = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "for-each-ref"], stderr="fatal: not a git repository"
        )
        monkeypatch.setattr(deletion, "list_branch_refs", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["feature-foo"], year="2026")

        assert "fatal: not a git repository" in raised.value.message

    def test_missing_git_binary_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing git binary during the resolution is a clean error."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(deletion, "list_branch_refs", mock.Mock(side_effect=FileNotFoundError("git")))

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["feature-foo"], year="2026")

        assert "git is not available" in raised.value.message
