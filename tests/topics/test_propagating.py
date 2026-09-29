"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: propagating.py``:

- ``PropagationPlan(target, base_ref, strategy, message, year)`` — the
  resolved propagation the caller confirms
- ``resolve_propagation(identifier, base_ref, strategy,
  commit_message, year)`` — the read-only plan resolution
- ``execute_propagation(plan)`` — the checkout-free delivery

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched: the exchange
resolutions, the git-cell names (tip resolution, tree resolution, the
inventory, the containment oracle, the tree merge, the commit build,
the plant, the two pushes, the origin probe), the hooks facade, the
current branch, and the year resolution are patched at
``goga.topics.propagating``; the template engine runs for real under a
recording spy.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
import typing
from types import SimpleNamespace
from unittest import mock

import click
import pytest
from goga.topics import propagating
from goga.topics.exchange import ExchangeBase, ExchangeTarget
from goga.topics.git import BranchRef
from goga.topics.hooks import TopicIdentity
from goga.topics.propagating import PropagationPlan, execute_propagation, resolve_propagation

from tests.conftest import is_kw_only_dataclass

# The design test constants: the base, its effective tip, the tip a
# concurrent movement leaves, the local base tip (the rollback tip),
# the own tip, the reconciliation commit, the two merged trees, the
# two built deliveries, and the two peel answers.
BASE = "main"
REMOTE_BASE = "origin/main"
BASE_TIP = "bb2"
MOVED_TIP = "bb9"
LOCAL_TIP = "aa1"
OWN = "cc3"
RECON = "dd4"
TREE = "tree-oid-1"
TREE2 = "tree-oid-2"
DELIVERY = "ee5"
DELIVERY2 = "ee7"
BASE_TREE = "t0"
OWN_TREE = "t1"

TOPIC = "feat-x"

IDENTITY = TopicIdentity(slug=TOPIC, year="2026", branch=TOPIC)

DEFAULT_MESSAGE = "Propagate topic 'feat-x' into 'main'"

# The rejection stderr of a push whose remote moved concurrently — the
# one wording pair the retry cycle answers to.
REJECTED = "! [rejected] main -> main ({reason})"

# The base-resolution arguments every execution passes — the base
# spelling, the addressed branch, and its tip.
_RESOLUTION_ARGS = (BASE, TOPIC, OWN)


# --- Shared scenario helpers ---


def _rejected(reason: str) -> subprocess.CalledProcessError:
    """The concurrent-movement rejection of a delivery push, as git words it."""
    return subprocess.CalledProcessError(1, ["git", "push"], stderr=REJECTED.format(reason=reason))


def _wire_propagation(  # noqa: PLR0913 — the scenario shape, keyword-only after the patcher
    monkeypatch: pytest.MonkeyPatch,
    *,
    target: ExchangeTarget,
    base: ExchangeBase,
    inventory: list[BranchRef],
    tips: dict[str, str] | None = None,
    trees: dict[str, str] | None = None,
    contains: set[tuple[str, str]] = frozenset(),
    current: str | None = TOPIC,
    bases: list[ExchangeBase] | None = None,
) -> SimpleNamespace:
    """Patch the propagation operation's import points with recording mocks.

    The revision resolution answers from ``tips`` — the target's own
    branch maps to the own tip, the overrides carry every rollback
    name; the tree resolution answers from ``trees``; the containment
    oracle answers from the ``contains`` ``(ancestor, descendant)``
    pairs; the tree merge answers ``TREE``, the commit build
    ``DELIVERY``, unless a test overrides the mock with a scripted
    sequence; the origin probe answers configured; ``bases`` scripts
    the re-resolution of the retry cycle (one entry per resolution).

    Args:
        monkeypatch: The patcher scoping the mocks to one test.
        target: The addressee the resolution answers.
        base: The base the first resolution answers.
        inventory: The branch inventory the operation reads.
        tips: The commit every resolvable name maps to.
        trees: The tree every resolvable revision maps to.
        contains: The containment pairs the oracle answers True for.
        current: The current branch name, or ``None`` for a detached
            HEAD.
        bases: The successive bases the resolution answers — the retry
            cycle's re-resolution is the second entry.

    Returns:
        The recording mocks: ``resolve_target``, ``resolve_base``,
        ``refs``, ``resolve``, ``tree``, ``containment``, ``merge``,
        ``build``, ``plant``, ``push``, ``push_write``, ``origin``,
        ``branch``, ``render``, and ``emit`` (the propagate
        notification).
    """
    commits = {target.branch: OWN, **(tips or {})}
    tree_answers = dict(trees or {})

    resolve_target = mock.Mock(return_value=target)
    resolve_base = mock.Mock(side_effect=list(bases)) if bases else mock.Mock(return_value=base)
    refs = mock.Mock(return_value=inventory)
    resolve = mock.Mock(side_effect=lambda name: commits[name])
    tree = mock.Mock(side_effect=lambda revision: tree_answers[revision])
    containment = mock.Mock(side_effect=lambda ancestor, descendant: (ancestor, descendant) in contains)
    merge = mock.Mock(return_value=TREE)
    build = mock.Mock(return_value=DELIVERY)
    plant = mock.Mock()
    push = mock.Mock()
    push_write = mock.Mock()
    origin = mock.Mock(return_value=True)
    branch = mock.Mock(return_value=current)
    render = mock.Mock(wraps=propagating.render_commit_template)
    hooks = mock.Mock()
    hooks_class = mock.Mock(return_value=hooks)

    monkeypatch.setattr(propagating, "resolve_exchange_target", resolve_target)
    monkeypatch.setattr(propagating, "resolve_exchange_base", resolve_base)
    monkeypatch.setattr(propagating, "list_branch_refs", refs)
    monkeypatch.setattr(propagating, "resolve_ref_commit", resolve)
    monkeypatch.setattr(propagating, "resolve_commit_tree", tree)
    monkeypatch.setattr(propagating, "is_ancestor", containment)
    monkeypatch.setattr(propagating, "merge_tree", merge)
    monkeypatch.setattr(propagating, "create_commit_from_tree", build)
    monkeypatch.setattr(propagating, "point_branch_at_commit", plant)
    monkeypatch.setattr(propagating, "push_branch", push)
    monkeypatch.setattr(propagating, "push_revision_to_branch", push_write)
    monkeypatch.setattr(propagating, "origin_configured", origin)
    monkeypatch.setattr(propagating, "resolve_current_branch_name", branch)
    monkeypatch.setattr(propagating, "render_commit_template", render)
    monkeypatch.setattr(propagating, "TopicHooks", hooks_class)
    monkeypatch.setattr(propagating, "current_year", mock.Mock(return_value="2026"))

    return SimpleNamespace(
        resolve_target=resolve_target,
        resolve_base=resolve_base,
        refs=refs,
        resolve=resolve,
        tree=tree,
        containment=containment,
        merge=merge,
        build=build,
        plant=plant,
        push=push,
        push_write=push_write,
        origin=origin,
        branch=branch,
        render=render,
        emit=hooks.emit_propagated,
    )


def _plan(
    target: ExchangeTarget,
    base_ref: str = BASE,
    strategy: str = "merge",
    message: str = "Deliver feat-x",
) -> PropagationPlan:
    """Build the confirmed plan of one execution scenario."""
    return PropagationPlan(target=target, base_ref=base_ref, strategy=strategy, message=message, year="2026")


# --- Contract tests ---


class TestPropagationContract:
    def test_entities_are_declared_in_the_module(self) -> None:
        """The entities live in ``goga.topics.propagating``."""
        import goga.topics.propagating as module

        assert module.PropagationPlan is PropagationPlan
        assert module.resolve_propagation is resolve_propagation
        assert module.execute_propagation is execute_propagation

    def test_propagation_plan_is_a_frozen_kw_only_dataclass_with_the_declared_fields(self) -> None:
        """The plan carries exactly the declared fields, frozen and keyword-only."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)

        assert is_kw_only_dataclass(PropagationPlan)
        assert PropagationPlan.__dataclass_params__.frozen
        assert [field.name for field in dataclasses.fields(PropagationPlan)] == [
            "target",
            "base_ref",
            "strategy",
            "message",
            "year",
        ]

        plan = PropagationPlan(target=target, base_ref=BASE, strategy="merge", message="m", year="2026")
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.strategy = "ff"  # type: ignore[misc]

    def test_declared_signatures(self) -> None:
        """The two entries take exactly the declared parameters with their defaults."""
        resolve_parameters = inspect.signature(resolve_propagation).parameters

        assert list(resolve_parameters) == ["identifier", "base_ref", "strategy", "commit_message", "year"]
        assert resolve_parameters["year"].default is None

        assert list(inspect.signature(execute_propagation).parameters) == ["plan"]

    def test_parameters_are_positional_or_keyword_with_contract_hints(self) -> None:
        """Every parameter is positional-or-keyword with the declared hints."""
        assert typing.get_type_hints(resolve_propagation) == {
            "identifier": str | None,
            "base_ref": str,
            "strategy": str | None,
            "commit_message": str | None,
            "year": str | None,
            "return": PropagationPlan,
        }
        assert typing.get_type_hints(execute_propagation) == {"plan": PropagationPlan, "return": str}

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
    @pytest.mark.parametrize("entry", ["resolve_propagation", "execute_propagation"])
    def test_public_entries_wrap_their_core_failures(
        self, monkeypatch: pytest.MonkeyPatch, entry: str, failure: Exception
    ) -> None:
        """The wrapped cores' five failure kinds surface as one clean error."""
        monkeypatch.setattr(propagating, f"_{entry}", mock.Mock(side_effect=failure))

        def call() -> None:
            if entry == "resolve_propagation":
                resolve_propagation(None, BASE, None, None)
            else:
                execute_propagation(mock.Mock())

        with pytest.raises(click.ClickException):
            call()


# --- Logic tests: the plan resolution ---


class TestResolvePropagation:
    def test_resolve_propagation_is_read_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The plan carries every decision and performs nothing — a declined confirmation is free."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
        )

        plan = resolve_propagation(TOPIC, BASE, None, None, year="2026")

        assert plan == PropagationPlan(
            target=target, base_ref=BASE, strategy="merge", message=DEFAULT_MESSAGE, year="2026"
        )
        wired.resolve_base.assert_not_called()
        wired.plant.assert_not_called()
        wired.push.assert_not_called()
        wired.push_write.assert_not_called()

    def test_resolve_propagation_invalid_strategy_is_config_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An off-whitelist strategy names the configuration key, before anything else."""
        wired = _wire_propagation(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[],
        )

        with pytest.raises(click.ClickException, match=r"topics\.propagate\.strategy") as excinfo:
            resolve_propagation(TOPIC, BASE, "merge-nono", None)

        assert "merge-nono" in str(excinfo.value)
        wired.resolve_target.assert_not_called()

    def test_resolve_propagation_without_origin_is_clean_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing origin remote fails the resolution — the push is inherent to the delivery."""
        wired = _wire_propagation(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
        )
        wired.origin.return_value = False

        with pytest.raises(click.ClickException, match="origin"):
            resolve_propagation(TOPIC, BASE, None, None)

        wired.render.assert_not_called()

    def test_resolve_propagation_rejects_tag_or_hash_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A base naming no branch — a tag or a hash — is no delivery target.

        The write-through of a local-less base belongs to a remote-only
        branch base alone; a tag or hash slipping through it would
        invent a remote branch named after the tag or the hash.
        """
        wired = _wire_propagation(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[],
        )

        with pytest.raises(click.ClickException, match="must be a branch") as excinfo:
            resolve_propagation(TOPIC, "v1.0", None, None)

        assert "v1.0" in str(excinfo.value)
        wired.resolve_base.assert_not_called()
        wired.render.assert_not_called()

    def test_resolve_propagation_accepts_remote_only_branch_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A base existing as the origin twin alone resolves — the write-through case."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name=f"origin/{BASE}", remote=True)],
        )

        plan = resolve_propagation(TOPIC, BASE, None, None, year="2026")

        assert plan == PropagationPlan(
            target=target, base_ref=BASE, strategy="merge", message=DEFAULT_MESSAGE, year="2026"
        )

    def test_resolve_propagation_rejects_current_branch_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A base checked out here asks to switch away first — no plan is built."""
        wired = _wire_propagation(
            monkeypatch,
            target=ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False),
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            current=BASE,
        )

        with pytest.raises(click.ClickException, match="switch away"):
            resolve_propagation(TOPIC, BASE, None, None)

        wired.render.assert_not_called()


# --- Logic tests: the delivery ---


class TestExecutePropagation:
    def test_execute_propagation_merge_builds_plants_pushes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A merge delivery is one two-parent commit, one plant, one push."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={BASE_TIP: BASE_TREE},
        )

        result = execute_propagation(_plan(target))

        assert wired.merge.call_args == mock.call(BASE_TIP, OWN)
        assert wired.build.call_args == mock.call(TREE, [BASE_TIP, OWN], "Deliver feat-x")
        assert wired.plant.call_args == mock.call(BASE, DELIVERY)
        assert wired.push.call_args == mock.call(BASE)
        wired.push_write.assert_not_called()
        assert wired.emit.call_args == mock.call(IDENTITY, base=BASE, strategy="merge", outcome="merged")
        assert result == "Propagated topic 2026/feat-x into 'main' via merge (merged)"

    def test_execute_propagation_reachability_nothing_to_do(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A topic the base already carries delivers nothing — and the reconciliation stands."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            contains={(OWN, BASE_TIP)},
        )

        result = execute_propagation(_plan(target))

        wired.merge.assert_not_called()
        wired.push.assert_not_called()
        assert wired.plant.call_args_list == []
        assert wired.emit.call_args == mock.call(IDENTITY, base=BASE, strategy="merge", outcome="nothing-to-do")
        assert "nothing-to-do" in result

    def test_execute_propagation_content_nothing_to_do(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A delivery tree equal to the base tree lands nothing — content idempotency."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={BASE_TIP: BASE_TREE},
        )
        wired.merge.return_value = BASE_TREE  # the merged tree IS the base tree

        result = execute_propagation(_plan(target))

        wired.build.assert_not_called()
        wired.plant.assert_not_called()
        wired.push.assert_not_called()
        assert wired.emit.call_args == mock.call(IDENTITY, base=BASE, strategy="merge", outcome="nothing-to-do")
        assert "nothing-to-do" in result

    def test_execute_propagation_squash_single_parent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A squash delivery is one commit over the single base parent."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={BASE_TIP: BASE_TREE},
        )

        result = execute_propagation(_plan(target, strategy="squash"))

        assert wired.build.call_args == mock.call(TREE, [BASE_TIP], "Deliver feat-x")
        assert wired.plant.call_args == mock.call(BASE, DELIVERY)
        assert wired.emit.call_args == mock.call(IDENTITY, base=BASE, strategy="squash", outcome="squashed")
        assert result == "Propagated topic 2026/feat-x into 'main' via squash (squashed)"

    def test_execute_propagation_ff_delivers_own_tip_without_commit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An ff delivery plants the own tip — no commit is authored."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={BASE_TIP: BASE_TREE, OWN: OWN_TREE},
            contains={(BASE_TIP, OWN)},
        )

        result = execute_propagation(_plan(target, strategy="ff"))

        wired.build.assert_not_called()
        assert wired.plant.call_args == mock.call(BASE, OWN)
        assert wired.emit.call_args == mock.call(IDENTITY, base=BASE, strategy="ff", outcome="fast-forwarded")
        assert result == "Propagated topic 2026/feat-x into 'main' via ff (fast-forwarded)"

    def test_execute_propagation_ff_impossible_rolls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-fast-forwardable ff is a clean error suggesting manual git — and rolls back."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={RECON: BASE_TREE},
        )

        with pytest.raises(click.ClickException, match="manual"):
            execute_propagation(_plan(target, strategy="ff"))

        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]
        wired.build.assert_not_called()
        wired.push.assert_not_called()
        wired.emit.assert_not_called()

    def test_execute_propagation_retry_cycle_recovers_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A concurrent-movement rejection rolls the plant back, re-resolves, and redelivers."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={BASE_TIP: BASE_TREE, MOVED_TIP: BASE_TREE},
            bases=[
                ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=BASE, reconciled=False),
                ExchangeBase(name=BASE, tip=MOVED_TIP, local_branch=BASE, reconciled=False),
            ],
        )
        wired.merge.side_effect = [TREE, TREE2]
        wired.build.side_effect = [DELIVERY, DELIVERY2]
        wired.push.side_effect = [_rejected("non-fast-forward"), None]
        order = mock.Mock()
        order.attach_mock(wired.resolve_base, "resolve_base")
        order.attach_mock(wired.plant, "plant")

        result = execute_propagation(_plan(target))

        assert wired.resolve_base.call_count == 2
        assert wired.push.call_count == 2
        # The failed attempt's plant is rolled back between the two
        # deliveries — and before the re-resolution, so the retry never
        # reads its own planted delivery as an already-carried topic.
        assert wired.plant.call_args_list == [
            mock.call(BASE, DELIVERY),
            mock.call(BASE, LOCAL_TIP),
            mock.call(BASE, DELIVERY2),
        ]
        resolutions = [
            index
            for index, recorded in enumerate(order.mock_calls)
            if recorded == mock.call.resolve_base(*_RESOLUTION_ARGS)
        ]
        assert order.mock_calls.index(mock.call.plant(BASE, LOCAL_TIP)) < resolutions[1]
        assert result == "Propagated topic 2026/feat-x into 'main' via merge (merged)"

    def test_execute_propagation_second_rejection_fails_with_rollback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second rejection is one clean error carrying git's reason — after the rollback."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={RECON: BASE_TREE, MOVED_TIP: BASE_TREE},
            bases=[
                ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
                ExchangeBase(name=BASE, tip=MOVED_TIP, local_branch=BASE, reconciled=True),
            ],
        )
        wired.merge.side_effect = [TREE, TREE2]
        wired.build.side_effect = [DELIVERY, DELIVERY2]
        wired.push.side_effect = [_rejected("fetch first"), _rejected("non-fast-forward")]

        with pytest.raises(click.ClickException, match=r"twice.*non-fast-forward") as excinfo:
            execute_propagation(_plan(target))

        assert "'feat-x'" in str(excinfo.value)
        assert wired.push.call_count == 2
        # The retry's pre-resolution restore and the terminal rollback
        # both point the base at the captured pre-resolution tip.
        assert wired.plant.call_args_list == [
            mock.call(BASE, DELIVERY),
            mock.call(BASE, LOCAL_TIP),
            mock.call(BASE, DELIVERY2),
            mock.call(BASE, LOCAL_TIP),
        ]

    def test_execute_propagation_write_through_remote_only_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A remote-only base plants nothing locally and pushes the delivery through."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=REMOTE_BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name=REMOTE_BASE, remote=True)],
            trees={BASE_TIP: BASE_TREE},
        )

        result = execute_propagation(_plan(target, base_ref=REMOTE_BASE))

        wired.plant.assert_not_called()
        assert wired.push_write.call_args == mock.call(DELIVERY, BASE)
        wired.push.assert_not_called()
        assert wired.emit.call_args == mock.call(IDENTITY, base=REMOTE_BASE, strategy="merge", outcome="merged")
        assert result == "Propagated topic 2026/feat-x into 'origin/main' via merge (merged)"

    def test_execute_propagation_write_through_names_slash_free_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A slash-free base spelling addresses its remote branch verbatim — never an empty refspec."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name=REMOTE_BASE, remote=True)],
            trees={BASE_TIP: BASE_TREE},
        )

        result = execute_propagation(_plan(target, base_ref=BASE))

        assert wired.push_write.call_args == mock.call(DELIVERY, BASE)
        assert result == "Propagated topic 2026/feat-x into 'main' via merge (merged)"

    def test_execute_propagation_merge_conflict_rolls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A conflicting delivery build is a clean error suggesting manual git — nothing planted or pushed."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            trees={RECON: BASE_TREE},
        )
        wired.merge.return_value = None

        with pytest.raises(click.ClickException, match="conflicts"):
            execute_propagation(_plan(target))

        assert wired.plant.call_args_list == [mock.call(BASE, LOCAL_TIP)]
        wired.build.assert_not_called()
        wired.push.assert_not_called()
        wired.emit.assert_not_called()

    def test_execute_propagation_remote_only_failure_plants_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed write-through push surfaces git's reason and plants nothing on any local branch."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=False)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=REMOTE_BASE, tip=BASE_TIP, local_branch=None, reconciled=False),
            inventory=[BranchRef(name=REMOTE_BASE, remote=True)],
            trees={BASE_TIP: BASE_TREE},
        )
        wired.push_write.side_effect = subprocess.CalledProcessError(
            128, ["git", "push"], stderr="fatal: remote error"
        )

        with pytest.raises(click.ClickException, match="remote error"):
            execute_propagation(_plan(target, base_ref=REMOTE_BASE))

        wired.plant.assert_not_called()
        wired.emit.assert_not_called()

    def test_execute_propagation_current_branch_base_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A base resolved onto the current branch is a clean error before any build."""
        target = ExchangeTarget(topic=TOPIC, branch=TOPIC, current=True)
        wired = _wire_propagation(
            monkeypatch,
            target=target,
            base=ExchangeBase(name=BASE, tip=BASE_TIP, local_branch=TOPIC, reconciled=False),
            inventory=[BranchRef(name=BASE, remote=False)],
            tips={BASE: LOCAL_TIP},
            current=TOPIC,
        )

        with pytest.raises(click.ClickException, match="switch away"):
            execute_propagation(_plan(target))

        wired.merge.assert_not_called()
        wired.build.assert_not_called()
        wired.plant.assert_not_called()
        wired.push.assert_not_called()
