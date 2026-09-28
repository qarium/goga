"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: exchange.py``:

- ``ExchangeBase(name, tip, local_branch, reconciled)`` — one resolved
  logical branch base
- ``ExchangeTarget(topic, branch, current)`` — one addressed topic of
  an exchange
- ``render_commit_template(template, slug, base)`` — the commit-message
  template engine
- ``resolve_exchange_base(base_ref, own_branch, own_tip)`` — the shared
  base resolution of the exchange operations
- ``resolve_exchange_target(identifier, year)`` — the addressee
  resolution

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched: the inventory,
the revision resolution, the containment oracle, the tree merge, the
commit build, the plant, the fetch, the version gate, the current
branch, and the switch-candidate resolution are patched at
``goga.topics.exchange``; the fetch reporting line is captured through
``capsys``.
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
from goga.topics import exchange
from goga.topics.exchange import (
    ExchangeBase,
    ExchangeTarget,
    render_commit_template,
    resolve_exchange_base,
    resolve_exchange_target,
)
from goga.topics.git import BranchRef
from goga.topics.switching import SwitchCandidate

from tests.conftest import is_kw_only_dataclass

# The design test constants: the base pair, their tips, the own tip,
# the reconciliation commit, and the merged tree.
BASE = "main"
TWIN = "origin/main"
LOCAL_TIP = "aa1"
TWIN_TIP = "bb2"
OWN = "cc3"
RECON = "dd4"
TREE = "tree-oid-1"


# --- Shared scenario helpers ---


def _unresolvable(name: str) -> subprocess.CalledProcessError:
    """The git failure of a revision nothing resolves."""
    return subprocess.CalledProcessError(
        128, ["git", "rev-parse", "--verify", name], stderr=f"fatal: bad revision '{name}'"
    )


def _wire_base_resolution(
    monkeypatch: pytest.MonkeyPatch,
    *,
    inventory: list[BranchRef],
    tips: dict[str, str],
    contains: set[tuple[str, str]],
    current: str | None,
) -> SimpleNamespace:
    """Patch the base resolution's import points with recording mocks.

    The revision resolution answers from ``tips`` — a name missing
    there fails the way an absent ref fails in git, so the projection
    skip is exercised for real. The containment oracle answers from the
    ``contains`` ``(ancestor, descendant)`` pairs; the reconciliation
    merge answers ``TREE`` unless a test overrides the mock's return
    value.

    Args:
        monkeypatch: The patcher scoping the mocks to one test.
        inventory: The branch inventory the resolution reads.
        tips: The commit every resolvable name maps to.
        contains: The containment pairs the oracle answers True for.
        current: The current branch name, or ``None`` for a detached HEAD.

    Returns:
        The recording mocks: ``refs``, ``resolve``, ``contains``,
        ``merge``, ``build``, ``plant``, ``fetch``, and ``gate``.
    """

    def _resolve(name: str) -> str:
        if name not in tips:
            raise _unresolvable(name)
        return tips[name]

    refs = mock.Mock(return_value=inventory)
    resolve = mock.Mock(side_effect=_resolve)
    containment = mock.Mock(side_effect=lambda ancestor, descendant: (ancestor, descendant) in contains)
    merge = mock.Mock(return_value=TREE)
    build = mock.Mock(return_value=RECON)
    plant = mock.Mock()
    fetch = mock.Mock()
    gate = mock.Mock()

    monkeypatch.setattr(exchange, "list_branch_refs", refs)
    monkeypatch.setattr(exchange, "resolve_ref_commit", resolve)
    monkeypatch.setattr(exchange, "is_ancestor", containment)
    monkeypatch.setattr(exchange, "merge_tree", merge)
    monkeypatch.setattr(exchange, "create_commit_from_tree", build)
    monkeypatch.setattr(exchange, "point_branch_at_commit", plant)
    monkeypatch.setattr(exchange, "fetch_branch", fetch)
    monkeypatch.setattr(exchange, "require_git_version", gate)
    monkeypatch.setattr(exchange, "resolve_current_branch_name", mock.Mock(return_value=current))

    return SimpleNamespace(
        refs=refs,
        resolve=resolve,
        containment=containment,
        merge=merge,
        build=build,
        plant=plant,
        fetch=fetch,
        gate=gate,
    )


def _wire_target_resolution(
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[SwitchCandidate],
    current: str | None = "main",
) -> mock.Mock:
    """Patch the addressee resolution's import points.

    Args:
        monkeypatch: The patcher scoping the mocks to one test.
        candidates: The candidates the switch resolution answers.
        current: The current branch name, or ``None`` for a detached HEAD.

    Returns:
        The recording switch-candidate resolution mock.
    """
    resolution = mock.Mock(return_value=candidates)
    monkeypatch.setattr(exchange, "resolve_switch_candidates", resolution)
    monkeypatch.setattr(exchange, "resolve_current_branch_name", mock.Mock(return_value=current))
    return resolution


# --- Contract tests ---


class TestExchangeContract:
    def test_entities_are_declared_in_the_module(self) -> None:
        """The five entities live in ``goga.topics.exchange``."""
        import goga.topics.exchange as module

        assert module.ExchangeBase is ExchangeBase
        assert module.ExchangeTarget is ExchangeTarget
        assert module.render_commit_template is render_commit_template
        assert module.resolve_exchange_base is resolve_exchange_base
        assert module.resolve_exchange_target is resolve_exchange_target

    def test_declared_signatures(self) -> None:
        """The routines take exactly the declared parameters."""
        assert list(inspect.signature(resolve_exchange_base).parameters) == ["base_ref", "own_branch", "own_tip"]
        assert list(inspect.signature(resolve_exchange_target).parameters) == ["identifier", "year"]
        assert inspect.signature(resolve_exchange_target).parameters["year"].default is None
        assert list(inspect.signature(render_commit_template).parameters) == ["template", "slug", "base"]

    def test_parameters_are_positional_or_keyword_with_contract_hints(self) -> None:
        """Every parameter is positional-or-keyword with the declared hints."""
        hints = {
            resolve_exchange_base: {"base_ref": str, "own_branch": str, "own_tip": str, "return": ExchangeBase},
            resolve_exchange_target: {"identifier": str | None, "year": str | None, "return": ExchangeTarget},
            render_commit_template: {"template": str, "slug": str, "base": str, "return": str},
        }

        for routine, expected in hints.items():
            assert typing.get_type_hints(routine) == expected, routine

    def test_exchange_base_is_a_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the four declared fields."""
        assert dataclasses.is_dataclass(ExchangeBase)
        assert ExchangeBase.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(ExchangeBase)
        assert typing.get_type_hints(ExchangeBase) == {
            "name": str,
            "tip": str,
            "local_branch": str | None,
            "reconciled": bool,
        }

    def test_exchange_target_is_a_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the three declared fields."""
        assert dataclasses.is_dataclass(ExchangeTarget)
        assert ExchangeTarget.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(ExchangeTarget)
        assert typing.get_type_hints(ExchangeTarget) == {"topic": str, "branch": str, "current": bool}

    def test_the_fact_bags_are_immutable(self) -> None:
        """Assignment to a field of either fact bag fails."""
        base = ExchangeBase(name=BASE, tip=LOCAL_TIP, local_branch=BASE, reconciled=False)
        target = ExchangeTarget(topic="feat-x", branch="feat-x", current=False)

        with pytest.raises(dataclasses.FrozenInstanceError):
            base.tip = TWIN_TIP  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            target.current = True  # type: ignore[misc]


# --- Logic tests: the template engine ---


class TestRenderCommitTemplate:
    def test_render_commit_template_placeholders(self) -> None:
        """Both placeholders substitute; unknown ones stay verbatim."""
        rendered = render_commit_template("Do {what} for {slug} from {base}", "feat-x", BASE)

        assert rendered == "Do {what} for feat-x from main"

    def test_render_commit_template_is_pure_text(self) -> None:
        """No repository read happens — the engine is a text transformation."""
        with mock.patch("subprocess.run", side_effect=AssertionError("no repository reads")):
            assert render_commit_template("{slug} + {base}", "feat-x", BASE) == "feat-x + main"
            assert render_commit_template("no placeholders", "feat-x", BASE) == "no placeholders"


# --- Logic tests: the base resolution ---


class TestResolveExchangeBase:
    def test_resolve_exchange_base_reconciliation_flow(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A diverged pair reconciles onto the local base branch after one reported fetch."""
        wired = _wire_base_resolution(
            monkeypatch,
            inventory=[BranchRef(name=BASE, remote=False), BranchRef(name=TWIN, remote=True)],
            tips={BASE: LOCAL_TIP, TWIN: TWIN_TIP},
            contains=set(),
            current="feat-x",
        )
        echoed_before_fetch: dict[str, str] = {}

        def _fetch_runs(name: str) -> None:
            echoed_before_fetch[name] = capsys.readouterr().out

        wired.fetch.side_effect = _fetch_runs

        base = resolve_exchange_base(BASE, "feat-x", OWN)

        assert base == ExchangeBase(name=BASE, tip=RECON, local_branch=BASE, reconciled=True)
        assert wired.build.call_args == mock.call(TREE, [LOCAL_TIP, TWIN_TIP], "Reconcile base 'main'")
        assert wired.plant.call_args == mock.call(BASE, RECON)
        assert wired.fetch.call_count == 1
        assert wired.gate.call_count == 1
        assert echoed_before_fetch[BASE] == "Fetching origin/main...\n"

    def test_resolve_exchange_base_already_carried_writes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A topic carrying both projections is the effective tip — nothing is written."""
        wired = _wire_base_resolution(
            monkeypatch,
            inventory=[BranchRef(name=BASE, remote=False), BranchRef(name=TWIN, remote=True)],
            tips={BASE: LOCAL_TIP, TWIN: TWIN_TIP},
            contains={(LOCAL_TIP, OWN), (TWIN_TIP, OWN)},
            current="feat-x",
        )

        base = resolve_exchange_base(BASE, "feat-x", OWN)

        assert base.tip == OWN
        assert base.reconciled is False
        wired.merge.assert_not_called()
        wired.plant.assert_not_called()

    def test_resolve_exchange_base_tag_base_never_fetches(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A base nothing branches around resolves read-only — no fetch, no echo."""
        wired = _wire_base_resolution(
            monkeypatch,
            inventory=[],
            tips={"v2.0": "tagcommit"},
            contains=set(),
            current="feat-x",
        )

        base = resolve_exchange_base("v2.0", "feat-x", OWN)

        assert base == ExchangeBase(name="v2.0", tip="tagcommit", local_branch=None, reconciled=False)
        wired.fetch.assert_not_called()
        assert capsys.readouterr().out == ""

    def test_resolve_exchange_base_rejects_self_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A base naming the topic's own branch — bare or twin form — is a clean error."""
        wired = _wire_base_resolution(monkeypatch, inventory=[], tips={}, contains=set(), current="feat-x")

        with pytest.raises(click.ClickException, match="its own base"):
            resolve_exchange_base("feat-x", "feat-x", OWN)
        with pytest.raises(click.ClickException, match="its own base"):
            resolve_exchange_base("origin/feat-x", "feat-x", OWN)

        wired.refs.assert_not_called()

    def test_resolve_exchange_base_rejects_checked_out_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The local base being the current branch is refused before the fetch."""
        inventory = [BranchRef(name=BASE, remote=False), BranchRef(name=TWIN, remote=True)]
        tips = {BASE: LOCAL_TIP, TWIN: TWIN_TIP}
        wired = _wire_base_resolution(monkeypatch, inventory=inventory, tips=tips, contains=set(), current=BASE)

        with pytest.raises(click.ClickException, match="switch"):
            resolve_exchange_base(BASE, "feat-x", OWN)

        wired.fetch.assert_not_called()
        wired.merge.assert_not_called()
        wired.plant.assert_not_called()

        # A detached HEAD passes the guard — the fetch runs.
        detached = _wire_base_resolution(
            monkeypatch, inventory=inventory, tips=tips, contains={(LOCAL_TIP, TWIN_TIP)}, current=None
        )
        base = resolve_exchange_base(BASE, "feat-x", OWN)

        detached.fetch.assert_called_once_with(BASE)
        assert base.tip == TWIN_TIP

    def test_resolve_exchange_base_reconcile_conflict_is_clean_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A conflicting reconciliation surfaces as a clean error, nothing mutated."""
        wired = _wire_base_resolution(
            monkeypatch,
            inventory=[BranchRef(name=BASE, remote=False), BranchRef(name=TWIN, remote=True)],
            tips={BASE: LOCAL_TIP, TWIN: TWIN_TIP},
            contains=set(),
            current="feat-x",
        )
        wired.merge.return_value = None

        with pytest.raises(click.ClickException, match="manual"):
            resolve_exchange_base(BASE, "feat-x", OWN)

        wired.build.assert_not_called()
        wired.plant.assert_not_called()

    def test_resolve_exchange_base_remote_only_base_single_projection(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A base carried only by its origin twin projects once — no local branch."""
        wired = _wire_base_resolution(
            monkeypatch,
            inventory=[BranchRef(name=TWIN, remote=True)],
            tips={TWIN: TWIN_TIP},
            contains=set(),
            current="feat-x",
        )

        base = resolve_exchange_base(TWIN, "feat-x", OWN)

        assert base == ExchangeBase(name=TWIN, tip=TWIN_TIP, local_branch=None, reconciled=False)
        assert wired.fetch.call_args == mock.call(BASE)
        assert "Fetching origin/main...\n" in capsys.readouterr().out

    def test_resolve_exchange_base_descendant_of_pair(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One projection containing the other decides without a merge."""
        wired = _wire_base_resolution(
            monkeypatch,
            inventory=[BranchRef(name=BASE, remote=False), BranchRef(name=TWIN, remote=True)],
            tips={BASE: LOCAL_TIP, TWIN: TWIN_TIP},
            contains={(LOCAL_TIP, TWIN_TIP)},
            current="feat-x",
        )

        base = resolve_exchange_base(BASE, "feat-x", OWN)

        assert base.tip == TWIN_TIP
        assert base.reconciled is False
        wired.merge.assert_not_called()


# --- Logic tests: the addressee resolution ---


class TestResolveExchangeTarget:
    def test_resolve_exchange_target_addresses_the_requested_topic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A local candidate becomes the target, marked when it is the current branch."""
        candidate = SwitchCandidate(branch="feat-x", topic="feat-x", statuses=[], current=False, remote=False)
        _wire_target_resolution(monkeypatch, [candidate], current=BASE)

        assert resolve_exchange_target("feat-x", year="2026") == ExchangeTarget(
            topic="feat-x", branch="feat-x", current=False
        )

        _wire_target_resolution(monkeypatch, [candidate], current="feat-x")
        assert resolve_exchange_target("feat-x", year="2026") == ExchangeTarget(
            topic="feat-x", branch="feat-x", current=True
        )

    def test_resolve_exchange_target_refuses_remote_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A candidate surviving only as a remote-tracking ref hints the switch first."""
        candidate = SwitchCandidate(branch="origin/feat-x", topic="feat-x", statuses=[], current=False, remote=True)
        _wire_target_resolution(monkeypatch, [candidate])

        with pytest.raises(click.ClickException, match="goga topics switch"):
            resolve_exchange_target("feat-x", year="2026")

    def test_resolve_exchange_target_no_candidate_hints_board(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An identifier nothing hosts names the board in the error."""
        _wire_target_resolution(monkeypatch, [])

        with pytest.raises(click.ClickException, match="goga topics board"):
            resolve_exchange_target("nope", year="2026")
