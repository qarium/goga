"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: deletion.py``:

- ``DeleteTarget(topic, branch, remote, has_dir)`` — one identified
  deletion target
- ``resolve_delete_targets(identifiers, year)`` — the read-only resolution
- ``delete_topics(targets, year)`` — the confirmed removal

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched: the inventory,
the ref-tree reading, the current branch, and the removal primitives are
patched at ``goga.topics.deletion``. The disk tree is real on ``tmp_path``
via ``monkeypatch.chdir`` — ``collect_history_tree`` and (where the
scenario says so) ``remove_topic_dir`` run against it.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
import typing
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import click
import pytest
from goga.history import remove_topic_dir as _remove_topic_dir
from goga.topics import DeleteTarget, delete_topics, deletion, resolve_delete_targets
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


def _wire_removal(
    monkeypatch: pytest.MonkeyPatch,
    *,
    commit: str = "c123",
    remote_error: Exception | None = None,
    restore_error: Exception | None = None,
    dir_side_effect: Callable[..., bool] | None = None,
) -> SimpleNamespace:
    """Patch the removal's import points with recording mocks.

    Every removal primitive of ``deletion`` is replaced by a mock; the
    mocks share one parent so ``wired.order.mock_calls`` records the
    cross-primitive call order. ``dir_side_effect`` lets the directory
    removal run the real history-facade function against ``tmp_path``.

    Args:
        monkeypatch: The patcher scoping the mocks to one test.
        commit: The commit the capture mock resolves.
        remote_error: The failure the remote deletion raises, if any.
        restore_error: The failure the restore (branch re-plant) raises.
        dir_side_effect: The real behavior of the directory removal.

    Returns:
        The recording mocks: ``order`` (the shared parent), ``capture``,
        ``local``, ``remote``, ``restore``, and ``directory``.
    """
    order = mock.Mock()
    capture = mock.Mock(return_value=commit)
    local = mock.Mock()
    remote = mock.Mock(side_effect=remote_error)
    restore = mock.Mock(side_effect=restore_error)
    directory = mock.Mock(return_value=False, side_effect=dir_side_effect)
    for name, child in (
        ("capture", capture),
        ("local", local),
        ("remote", remote),
        ("restore", restore),
        ("directory", directory),
    ):
        order.attach_mock(child, name)
    monkeypatch.setattr(deletion, "resolve_ref_commit", capture)
    monkeypatch.setattr(deletion, "delete_local_branch", local)
    monkeypatch.setattr(deletion, "delete_remote_branch", remote)
    monkeypatch.setattr(deletion, "create_branch_at_commit", restore)
    monkeypatch.setattr(deletion, "remove_topic_dir", directory)
    return SimpleNamespace(
        order=order, capture=capture, local=local, remote=remote, restore=restore, directory=directory
    )


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

    def test_delete_topics_is_importable_from_the_cell_facade(self) -> None:
        """``delete_topics`` lives on the cell facade."""
        import goga.topics as cell

        assert cell.delete_topics is delete_topics
        assert "delete_topics" in cell.__all__

    def test_delete_topics_signature(self) -> None:
        """``delete_topics(targets, year=None) -> str``."""
        signature = inspect.signature(delete_topics)
        assert list(signature.parameters) == ["targets", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert typing.get_type_hints(delete_topics) == {
            "targets": list[DeleteTarget],
            "year": str | None,
            "return": str,
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

    def test_resolve_delete_targets_prefix_tier_matches_branch_and_slug(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A prefix identifier resolves through the third tier — one target.

        Both prefix arms agree here: the branch name starts with the raw
        identifier and the hosted slug starts with its normalization.
        """
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="feature-foo", remote=False)]
        trees = {"feature-foo": [".goga/history/2026/feature-foo/plan.md"]}
        _wire_resolution(monkeypatch, inventory, trees, "main")

        targets = resolve_delete_targets(["feat"], year="2026")

        assert targets == [
            DeleteTarget(topic="feature-foo", branch="feature-foo", remote=None, has_dir=False)
        ]

    def test_resolve_delete_targets_prefix_of_remote_short_name_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The prefix tier also reads a remote-tracking ref by its short name.

        The display name starts with ``origin/``, so only the short-name
        prefix arm can match a bare identifier prefix.
        """
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="origin/feature-foo", remote=True)]
        trees = {"origin/feature-foo": [".goga/history/2026/feature-foo/plan.md"]}
        _wire_resolution(monkeypatch, inventory, trees, "main")

        targets = resolve_delete_targets(["feature-fo"], year="2026")

        assert targets == [
            DeleteTarget(topic="feature-foo", branch=None, remote="feature-foo", has_dir=False)
        ]

    def test_resolve_delete_targets_non_ascii_identifier_matches_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-ASCII identifier normalizes to the empty slug — every slug
        starts with it, so the slug-prefix arms must stay disabled."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="feature-foo", remote=False)]
        trees = {"feature-foo": [".goga/history/2026/feature-foo/plan.md"]}
        _wire_resolution(monkeypatch, inventory, trees, "main")

        with pytest.raises(click.ClickException) as raised:
            resolve_delete_targets(["Тема"], year="2026")

        assert "Тема" in raised.value.message

    def test_resolve_delete_targets_non_origin_remote_is_not_the_twin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A tracking ref of another remote contributes no deletable twin.

        The deletion push of the git cell is origin-only, so a non-origin
        remote's short name must never reach ``remote`` — it would be
        pushed at origin (a wrong remote's branch deleted, or a phantom
        "remote ref does not exist" after the local branch is gone). The
        ref stays an eligible host — the topic is not merged work.
        """
        monkeypatch.chdir(tmp_path)
        _disk_topic(tmp_path, "2026", "feature-x")
        inventory = [BranchRef(name="upstream/feature-x", remote=True)]
        trees = {"upstream/feature-x": [".goga/history/2026/feature-x/plan.md"]}
        _wire_resolution(monkeypatch, inventory, trees, "main")

        targets = resolve_delete_targets(["feature-x"], year="2026")

        assert targets == [DeleteTarget(topic="feature-x", branch=None, remote=None, has_dir=True)]

    def test_resolve_delete_targets_prefers_the_origin_twin_among_remotes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With twins on several remotes, the origin twin is the deletable one."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="origin/feature-x", remote=True),
            BranchRef(name="upstream/feature-x", remote=True),
        ]
        trees = {
            "origin/feature-x": [".goga/history/2026/feature-x/plan.md"],
            "upstream/feature-x": [".goga/history/2026/feature-x/plan.md"],
        }
        _wire_resolution(monkeypatch, inventory, trees, "main")

        targets = resolve_delete_targets(["feature-x"], year="2026")

        assert targets == [
            DeleteTarget(topic="feature-x", branch=None, remote="feature-x", has_dir=False)
        ]

    def test_resolve_delete_targets_current_branch_guard_slug_arm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The guard also fires when the current branch's slug names the topic.

        A disk-only target carries ``branch=None``, so the branch-equality
        arm alone would let ``goga topics delete feature-foo`` remove the
        directory while the user sits on ``Feature_Foo``.
        """
        monkeypatch.chdir(tmp_path)
        _disk_topic(tmp_path, "2026", "feature-foo")
        _wire_resolution(monkeypatch, [], {}, "Feature_Foo")

        with pytest.raises(click.ClickException, match="switch"):
            resolve_delete_targets(["feature-foo"], year="2026")


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


# --- Logic tests: the confirmed removal ---


class TestDeleteTopics:
    def test_delete_topics_restores_local_on_remote_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed remote deletion restores the local branch at the captured commit."""
        monkeypatch.chdir(tmp_path)
        target = DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)
        wired = _wire_removal(
            monkeypatch,
            remote_error=subprocess.CalledProcessError(128, "git push", stderr=b"remote error"),
        )

        with pytest.raises(click.ClickException) as raised:
            delete_topics([target], year="2026")

        assert "remote error" in raised.value.message
        wired.restore.assert_called_once_with("feature-foo", "c123")
        wired.directory.assert_not_called()

    def test_delete_topics_full_success_removes_all_three(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The local branch, the origin twin, and the directory go — in that order."""
        monkeypatch.chdir(tmp_path)
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "feature-foo"
        topic_dir.mkdir(parents=True)
        target = DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)
        wired = _wire_removal(monkeypatch, dir_side_effect=_remove_topic_dir)

        line = delete_topics([target], year="2026")

        assert line == "Deleted 1 topic(s) of 2026: feature-foo"
        assert not topic_dir.exists()
        assert wired.order.mock_calls == [
            mock.call.capture("feature-foo"),
            mock.call.local("feature-foo"),
            mock.call.remote("feature-foo"),
            mock.call.directory("feature-foo", "2026"),
        ]

    def test_delete_topics_remote_only_target_no_restore(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A remote-only target has nothing to restore — the error propagates directly."""
        monkeypatch.chdir(tmp_path)
        target = DeleteTarget(topic="ghost", branch=None, remote="ghost", has_dir=False)
        wired = _wire_removal(
            monkeypatch,
            remote_error=subprocess.CalledProcessError(128, "git push", stderr=b"deny"),
        )

        with pytest.raises(click.ClickException) as raised:
            delete_topics([target], year="2026")

        assert "deny" in raised.value.message
        wired.restore.assert_not_called()

    def test_delete_topics_idempotent_directory_absence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An already-absent directory is a False, not an error — the topic still reports."""
        monkeypatch.chdir(tmp_path)
        target = DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)
        wired = _wire_removal(monkeypatch, dir_side_effect=_remove_topic_dir)

        line = delete_topics([target], year="2026")

        assert line == "Deleted 1 topic(s) of 2026: feature-foo"
        wired.directory.assert_called_once_with("feature-foo", "2026")

    def test_delete_topics_restore_failure_surfaces_original_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A broken rollback's failure is suppressed — the remote reason surfaces."""
        monkeypatch.chdir(tmp_path)
        target = DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)
        _wire_removal(
            monkeypatch,
            remote_error=subprocess.CalledProcessError(128, "git push", stderr=b"remote error"),
            restore_error=subprocess.CalledProcessError(1, "git update-ref", stderr=b"ref lock"),
        )

        with pytest.raises(click.ClickException) as raised:
            delete_topics([target], year="2026")

        assert "remote error" in raised.value.message
        assert "ref lock" not in raised.value.message

    def test_delete_topics_targets_before_a_failure_stay_removed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A multi-target deletion is not all-or-nothing across targets.

        The first target is fully removed before the second's remote
        deletion fails; the failing target restores its local branch at
        the captured commit and never reaches its directory.
        """
        monkeypatch.chdir(tmp_path)
        first = DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)
        second = DeleteTarget(topic="feature-bar", branch="feature-bar", remote="feature-bar", has_dir=True)
        wired = _wire_removal(monkeypatch)
        wired.remote.side_effect = [
            None,
            subprocess.CalledProcessError(128, "git push", stderr=b"deny second"),
        ]

        with pytest.raises(click.ClickException, match="deny second"):
            delete_topics([first, second], year="2026")

        assert wired.order.mock_calls == [
            mock.call.capture("feature-foo"),
            mock.call.local("feature-foo"),
            mock.call.remote("feature-foo"),
            mock.call.directory("feature-foo", "2026"),
            mock.call.capture("feature-bar"),
            mock.call.local("feature-bar"),
            mock.call.remote("feature-bar"),
            mock.call.restore("feature-bar", "c123"),
        ]
