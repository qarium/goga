"""Contract and logic tests for the entity declared in
``goga/topics/CODEMANIFEST`` with ``location: updating.py``:

- ``update_topic(identifier, base_ref, strategy, commit_message,
  publish, year)`` — the update operation

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched: the exchange
resolutions, the git-cell names (tip resolution, inventory, the
containment oracle, the tree merge, the commit build, the plant, the
replay, the cleanliness probe, the in-place moves, the origin probe,
the two pushes), the hooks facade, and the year resolution are patched
at ``goga.topics.updating``.
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from types import SimpleNamespace
from unittest import mock

import click
import pytest
from goga.topics import updating
from goga.topics.exchange import ExchangeBase, ExchangeTarget
from goga.topics.git import BranchRef
from goga.topics.hooks import TopicIdentity
from goga.topics.updating import update_topic

# The design test constants: the base, its effective tip, the local
# base tip (the rollback tip), the own tip, the reconciliation commit,
# the merged tree, the built update commit, and the replayed tip.
BASE = "main"
BASE_TIP = "bb2"
LOCAL_TIP = "aa1"
OWN = "cc3"
RECON = "dd4"
TREE = "tree-oid-1"
NEW = "ee5"
REPLAYED = "ff6"

TOPIC = "feat-x"

IDENTITY = TopicIdentity(slug=TOPIC, year="2026", branch=TOPIC)

DEFAULT_MESSAGE = "Update topic 'feat-x' from 'main'"


# --- Shared scenario helpers ---


def _wire_update(  # noqa: PLR0913 — the scenario shape, keyword-only after the patcher
    monkeypatch: pytest.MonkeyPatch,
    *,
    target: ExchangeTarget,
    base: ExchangeBase,
    inventory: list[BranchRef],
    tips: dict[str, str] | None = None,
    contains: set[tuple[str, str]] = frozenset(),
    clean: bool = True,
) -> SimpleNamespace:
    """Patch the update operation's import points with recording mocks.

    The revision resolution answers from ``tips`` — the target's own
    branch maps to the own tip, the overrides carry every rollback
    name; the containment oracle answers from the ``contains``
    ``(ancestor, descendant)`` pairs; the tree merge answers ``TREE``,
    the replay ``REPLAYED``, and the commit build ``NEW`` unless a test
    overrides the mock's return value; the origin probe answers
    configured.

    Args:
        monkeypatch: The patcher scoping the mocks to one test.
        target: The addressee the resolution answers.
        base: The base the resolution answers.
        inventory: The branch inventory the operation reads.
        tips: The commit every resolvable name maps to.
        contains: The containment pairs the oracle answers True for.
        clean: The working-tree cleanliness the probe reports.

    Returns:
        The recording mocks: ``resolve_target``, ``resolve_base``,
        ``refs``, ``resolve``, ``containment``, ``merge``, ``build``,
        ``plant``, ``replay``, ``clean_probe``, ``in_place_merge``,
        ``in_place_rebase``, ``in_place_ff``, ``origin``, ``push``,
        ``lease``, and ``emit`` (the update notification).
    """
    commits = {target.branch: OWN, **(tips or {})}

    resolve_target = mock.Mock(return_value=target)
    resolve_base = mock.Mock(return_value=base)
    refs = mock.Mock(return_value=inventory)
    resolve = mock.Mock(side_effect=lambda name: commits[name])
    containment = mock.Mock(side_effect=lambda ancestor, descendant: (ancestor, descendant) in contains)
    merge = mock.Mock(return_value=TREE)
    build = mock.Mock(return_value=NEW)
    plant = mock.Mock()
    replay = mock.Mock(return_value=REPLAYED)
    clean_probe = mock.Mock(return_value=clean)
    in_place_merge = mock.Mock()
    in_place_rebase = mock.Mock()
    in_place_ff = mock.Mock()
    origin = mock.Mock(return_value=True)
    push = mock.Mock()
    lease = mock.Mock()
    hooks = mock.Mock()
    hooks_class = mock.Mock(return_value=hooks)

    monkeypatch.setattr(updating, "resolve_exchange_target", resolve_target)
    monkeypatch.setattr(updating, "resolve_exchange_base", resolve_base)
    monkeypatch.setattr(updating, "list_branch_refs", refs)
    monkeypatch.setattr(updating, "resolve_ref_commit", resolve)
    monkeypatch.setattr(updating, "is_ancestor", containment)
    monkeypatch.setattr(updating, "merge_tree", merge)
    monkeypatch.setattr(updating, "create_commit_from_tree", build)
    monkeypatch.setattr(updating, "point_branch_at_commit", plant)
    monkeypatch.setattr(updating, "replay_commits", replay)
    monkeypatch.setattr(updating, "is_working_tree_clean", clean_probe)
    monkeypatch.setattr(updating, "merge_into_current", in_place_merge)
    monkeypatch.setattr(updating, "rebase_current_onto", in_place_rebase)
    monkeypatch.setattr(updating, "fast_forward_current_branch", in_place_ff)
    monkeypatch.setattr(updating, "origin_configured", origin)
    monkeypatch.setattr(updating, "push_branch", push)
    monkeypatch.setattr(updating, "push_branch_with_lease", lease)
    monkeypatch.setattr(updating, "TopicHooks", hooks_class)
    monkeypatch.setattr(updating, "current_year", mock.Mock(return_value="2026"))

    return SimpleNamespace(
        resolve_target=resolve_target,
        resolve_base=resolve_base,
        refs=refs,
        resolve=resolve,
        containment=containment,
        merge=merge,
        build=build,
        plant=plant,
        replay=replay,
        clean_probe=clean_probe,
        in_place_merge=in_place_merge,
        in_place_rebase=in_place_rebase,
        in_place_ff=in_place_ff,
        origin=origin,
        push=push,
        lease=lease,
        emit=hooks.emit_updated,
    )


# --- Contract tests ---


class TestUpdateContract:
    def test_update_topic_is_declared_in_the_module(self) -> None:
        """The entity lives in ``goga.topics.updating``."""
        import goga.topics.updating as module

        assert module.update_topic is update_topic

    def test_declared_signature(self) -> None:
        """The routine takes exactly the declared parameters with their defaults."""
        parameters = inspect.signature(update_topic).parameters

        assert list(parameters) == ["identifier", "base_ref", "strategy", "commit_message", "publish", "year"]
        assert parameters["publish"].default is False
        assert parameters["year"].default is None

    def test_parameters_are_positional_or_keyword_with_contract_hints(self) -> None:
        """Every parameter is positional-or-keyword with the declared hints."""
        assert typing.get_type_hints(update_topic) == {
            "identifier": str | None,
            "base_ref": str,
            "strategy": str | None,
            "commit_message": str | None,
            "publish": bool,
            "year": str | None,
            "return": str,
        }

    @pytest.mark.parametrize(
        "failure",
        [
            subprocess.CalledProcessError(1, ["git"], stderr="fatal: boom"),
            FileNotFoundError("git"),
            OSError("spawn failed"),
            RuntimeError("the gate fired"),
            ImportError("the tool package is broken"),
        ],
    )
    def test_public_entry_wraps_its_core_failures(
        self, monkeypatch: pytest.MonkeyPatch, failure: Exception
    ) -> None:
        """The wrapped core's five failure kinds surface as one clean error."""
        monkeypatch.setattr(updating, "_update_topic", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException):
            update_topic(None, BASE, None, None)


# --- Logic tests: the update operation ---


class TestUpdateTopic:
    def test_update_topic_checkout_free_merge_plants_two_parent_commit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Another topic merges checkout-free: one two-parent commit, one plant."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name="origin/main", remote=True)],
        )

        result = update_topic(None, BASE, None, None, publish=False, year="2026")

        assert wired.build.call_args == mock.call(TREE, [OWN, BASE_TIP], DEFAULT_MESSAGE)
        assert wired.plant.call_args == mock.call(TOPIC, NEW)
        assert wired.emit.call_args == mock.call(
            IDENTITY, base=BASE, effective_tip=BASE_TIP, strategy="merge", outcome="merged", published=False
        )
        assert result == "Updated topic 2026/feat-x from 'main' via merge (merged)"
        wired.push.assert_not_called()

    def test_update_topic_already_current_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A topic carrying its base mutates nothing and publishes nothing."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[],
            contains={(BASE_TIP, OWN)},
        )

        result = update_topic(TOPIC, BASE, None, None, publish=True, year="2026")

        wired.merge.assert_not_called()
        wired.plant.assert_not_called()
        wired.push.assert_not_called()
        assert wired.emit.call_args == mock.call(
            IDENTITY, base=BASE, effective_tip=BASE_TIP, strategy="merge", outcome="already-current", published=False
        )
        assert "already-current" in result

    def test_update_topic_invalid_strategy_is_config_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An off-whitelist strategy names the configuration key, before anything else."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[],
        )

        with pytest.raises(click.ClickException, match=r"topics\.update\.strategy") as excinfo:
            update_topic(None, BASE, "squash", None)

        assert "squash" in str(excinfo.value)
        wired.resolve_target.assert_not_called()

    def test_update_topic_rebase_publish_uses_lease_against_pre_rebase_tip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A checkout-free rebase publishes under a lease bound to the pre-rebase own tip."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name="origin/main", remote=True), BranchRef(name="origin/feat-x", remote=True)],
        )

        result = update_topic(TOPIC, BASE, "rebase", None, publish=True)

        assert wired.replay.call_count == 1
        assert wired.replay.call_args == mock.call(BASE_TIP, OWN)
        assert wired.plant.call_args == mock.call(TOPIC, REPLAYED)
        assert wired.lease.call_args == mock.call(TOPIC, OWN)
        wired.push.assert_not_called()
        assert wired.emit.call_args == mock.call(
            IDENTITY, base=BASE, effective_tip=BASE_TIP, strategy="rebase", outcome="rebased", published=True
        )
        assert result == "Updated topic 2026/feat-x from 'main' via rebase (rebased)"

    def test_update_topic_preflight_conflict_rolls_back_reconciliation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A conflicting pre-flight of the current topic restores the captured base tip after it."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
        )
        wired.merge.return_value = None
        order = mock.Mock()
        order.attach_mock(wired.merge, "merge")
        order.attach_mock(wired.plant, "plant")

        with pytest.raises(click.ClickException, match="manual"):
            update_topic(None, BASE, None, None, year="2026")

        assert wired.plant.call_args == mock.call(BASE, LOCAL_TIP)
        assert order.mock_calls.index(mock.call.merge(OWN, RECON)) < order.mock_calls.index(
            mock.call.plant(BASE, LOCAL_TIP)
        )
        wired.build.assert_not_called()
        wired.in_place_merge.assert_not_called()
        wired.emit.assert_not_called()

    def test_update_topic_checkout_free_conflict_rolls_back_reconciliation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A checkout-free build conflict restores the base and never plants the topic."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
        )
        wired.merge.return_value = None

        with pytest.raises(click.ClickException, match="manual"):
            update_topic(TOPIC, BASE, None, None, year="2026")

        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]
        wired.build.assert_not_called()
        wired.emit.assert_not_called()

    def test_update_topic_publish_without_origin_is_clean_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A publish without an origin fails cleanly — the confirmed update stands."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[],
        )
        wired.origin.return_value = False

        with pytest.raises(click.ClickException, match="origin"):
            update_topic(None, BASE, None, None, publish=True, year="2026")

        assert wired.plant.call_args == mock.call(TOPIC, NEW)
        wired.push.assert_not_called()
        wired.emit.assert_not_called()

    def test_update_topic_ff_else_with_no_own_work_fast_forwards(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An ff-else strategy with no own work plants the base tip — no commit authored."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[],
            contains={(OWN, BASE_TIP)},
        )

        result = update_topic(None, BASE, "ff-else-merge", None, year="2026")

        wired.build.assert_not_called()
        assert wired.plant.call_args == mock.call(TOPIC, BASE_TIP)
        assert wired.emit.call_args == mock.call(
            IDENTITY,
            base=BASE,
            effective_tip=BASE_TIP,
            strategy="ff-else-merge",
            outcome="fast-forwarded",
            published=False,
        )
        assert result == "Updated topic 2026/feat-x from 'main' via ff-else-merge (fast-forwarded)"

    def test_update_topic_current_topic_dirty_tree_clean_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A dirty tree of the current topic fails before any mutation, reconciliation restored."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            clean=False,
        )

        with pytest.raises(click.ClickException, match="clean"):
            update_topic(None, BASE, None, None, year="2026")

        wired.merge.assert_not_called()
        wired.in_place_merge.assert_not_called()
        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]

    def test_update_topic_current_topic_merge_is_in_place(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The current topic merges in place — one discarded pre-flight, one real merge."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
        )

        result = update_topic(None, BASE, None, None, year="2026")

        assert wired.merge.call_count == 1
        assert wired.merge.call_args == mock.call(OWN, BASE_TIP)
        assert wired.in_place_merge.call_args == mock.call(BASE_TIP, DEFAULT_MESSAGE)
        wired.plant.assert_not_called()
        assert wired.emit.call_args == mock.call(
            IDENTITY, base=BASE, effective_tip=BASE_TIP, strategy="merge", outcome="merged", published=False
        )
        assert result == "Updated topic 2026/feat-x from 'main' via merge (merged)"

    def test_update_topic_current_topic_rebase_is_in_place_with_lease(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The current topic rebases in place — one discarded pre-flight, one real rebase."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False), BranchRef(name="origin/feat-x", remote=True)],
            tips={BASE: LOCAL_TIP},
        )

        result = update_topic(None, BASE, "rebase", None, publish=True, year="2026")

        assert wired.replay.call_count == 1
        assert wired.replay.call_args == mock.call(BASE_TIP, OWN)
        assert wired.in_place_rebase.call_args == mock.call(BASE_TIP)
        wired.plant.assert_not_called()
        assert wired.lease.call_args == mock.call(TOPIC, OWN)
        wired.push.assert_not_called()
        assert wired.emit.call_args == mock.call(
            IDENTITY, base=BASE, effective_tip=BASE_TIP, strategy="rebase", outcome="rebased", published=True
        )
        assert result == "Updated topic 2026/feat-x from 'main' via rebase (rebased)"

    def test_update_topic_lease_rejection_is_clean_error_update_stands(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rejected lease push is one clean error — no retry, the update stands."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False), BranchRef(name="origin/feat-x", remote=True)],
            tips={BASE: LOCAL_TIP},
        )
        wired.lease.side_effect = subprocess.CalledProcessError(
            1, ["git", "push"], stderr="! [rejected] feat-x -> feat-x (stale info)"
        )

        with pytest.raises(click.ClickException, match="stale info"):
            update_topic(None, BASE, "rebase", None, publish=True, year="2026")

        assert wired.lease.call_count == 1
        wired.in_place_rebase.assert_called_once_with(BASE_TIP)
        wired.plant.assert_not_called()

    def test_update_topic_preflight_infrastructure_failure_rolls_back_reconciliation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A raised git failure of the in-place pre-flight restores the base — no raw leftover."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
        )
        wired.merge.side_effect = subprocess.CalledProcessError(
            129, ["git", "merge-tree"], stderr="error: unknown option `merge-base=aa1'"
        )

        with pytest.raises(click.ClickException, match="git failed"):
            update_topic(None, BASE, None, None, year="2026")

        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]
        wired.in_place_merge.assert_not_called()
        wired.emit.assert_not_called()

    def test_update_topic_checkout_free_build_failure_rolls_back_reconciliation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A raised git failure of the checkout-free build restores the base before surfacing."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
        )
        wired.build.side_effect = subprocess.CalledProcessError(
            128, ["git", "commit-tree"], stderr="fatal: unable to read tree"
        )

        with pytest.raises(click.ClickException, match="git failed"):
            update_topic(TOPIC, BASE, None, None, year="2026")

        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]
        wired.emit.assert_not_called()

    def test_update_topic_in_place_rebase_conflict_rolls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A conflicting rebase pre-flight of the current topic restores the base and hints manually."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
        )
        wired.replay.return_value = None

        with pytest.raises(click.ClickException, match="manual"):
            update_topic(None, BASE, "rebase", None, year="2026")

        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]
        wired.in_place_rebase.assert_not_called()
        wired.emit.assert_not_called()

    def test_update_topic_checkout_free_rebase_conflict_rolls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A conflicting checkout-free replay restores the base and never plants the topic."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
        )
        wired.replay.return_value = None

        with pytest.raises(click.ClickException, match="manual"):
            update_topic(TOPIC, BASE, "rebase", None, year="2026")

        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]
        wired.emit.assert_not_called()

    def test_update_topic_current_topic_fast_forward_is_in_place_ff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An ff-else strategy with no own work fast-forwards the current branch in place."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            contains={(OWN, BASE_TIP)},
        )

        result = update_topic(None, BASE, "ff-else-merge", None, year="2026")

        assert wired.in_place_ff.call_args == mock.call(BASE_TIP)
        wired.in_place_merge.assert_not_called()
        wired.in_place_rebase.assert_not_called()
        wired.merge.assert_not_called()
        assert result == "Updated topic 2026/feat-x from 'main' via ff-else-merge (fast-forwarded)"

    def test_update_topic_merge_publish_pushes_plain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A merge publish pushes plainly — the lease path belongs to the rebase alone."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name="origin/main", remote=True), BranchRef(name="origin/feat-x", remote=True)],
        )

        result = update_topic(None, BASE, None, None, publish=True, year="2026")

        assert wired.push.call_args == mock.call(TOPIC)
        wired.lease.assert_not_called()
        assert result == "Updated topic 2026/feat-x from 'main' via merge (merged)"

    def test_update_topic_rebase_publish_without_twin_pushes_plain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A rebase publish whose branch has no origin twin pushes plainly — nothing to lease against."""
        wired = _wire_update(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name="origin/main", remote=True)],
        )

        result = update_topic(TOPIC, BASE, "rebase", None, publish=True, year="2026")

        assert wired.push.call_args == mock.call(TOPIC)
        wired.lease.assert_not_called()
        assert result == "Updated topic 2026/feat-x from 'main' via rebase (rebased)"
