"""Contract and logic tests for the entity declared in
``goga/build/hooks/CODEMANIFEST`` with ``location: events.py``:

- ``BuildHooks()`` — the checkpoint surface delivering the hard validation
  gate and emitting the four soft notifications of the build cycle

The checkpoint surface runs for real over the platform boundary fixtures of
``tests/hooks/conftest.py`` (re-exported by the zone test package) — the
registry, the registrars, and the delivery execute the actual platform
code.
"""

from __future__ import annotations

import inspect

import pytest
from goga.build.hooks import (
    AdditionalFacts,
    BuildHooks,
    BuildMoment,
    RelocationOutcome,
    StageFacts,
    Violation,
    WorkIdentity,
)

_ZONE_ALL: list[str] = [
    "AdditionalFacts",
    "BuildCompleted",
    "BuildHooks",
    "BuildMoment",
    "BuildStarted",
    "BuildValidation",
    "GateVerdict",
    "PassCompleted",
    "PassStarted",
    "RelocationOutcome",
    "StageFacts",
    "Violation",
    "WorkIdentity",
]
"""The completed zone facade — exactly the thirteen contract names."""


def _tasks_facts(**overrides: object) -> StageFacts:
    """A tasks-part ``StageFacts`` — the review-only members None."""
    values: dict[str, object] = {
        "stage": "tasks",
        "agent": "claude",
        "env": ["A", "B"],
        "max_iterations": 9,
        "session_timeout": "30m",
        "idle_timeout": "5m",
        "wait": "1m",
        "roles": None,
        "base_ref": None,
        "strategy": None,
        "finalize": None,
        "additional": None,
    }
    values.update(overrides)

    return StageFacts(**values)  # type: ignore[arg-type]


def _review_facts(**overrides: object) -> StageFacts:
    """A review-part ``StageFacts`` — the review-only members populated."""
    values: dict[str, object] = {
        "stage": "review",
        "agent": "codex",
        "env": [],
        "max_iterations": None,
        "session_timeout": "30m",
        "idle_timeout": "5m",
        "wait": "1m",
        "roles": ["quality"],
        "base_ref": "main",
        "strategy": "medium",
        "finalize": None,
        "additional": AdditionalFacts(agent="codex", patience=None, max_iterations=None),
    }
    values.update(overrides)

    return StageFacts(**values)  # type: ignore[arg-type]


def _moment() -> BuildMoment:
    """The uniform envelope — a branch-only work identity."""
    return BuildMoment(
        plan="docs/plans/plan.md",
        work=WorkIdentity(branch="add-hooks-to-build"),
        dry_run=False,
    )


# --- Contract tests ---


class TestCheckpointContract:
    def test_zone_facade_exports_exactly_the_contract(self) -> None:
        """The facade IS the contract surface — the thirteen names, importable."""
        import goga.build.hooks as zone

        assert zone.BuildHooks is BuildHooks
        assert zone.__all__ == _ZONE_ALL  # alphabetical, complete

        for name in zone.__all__:
            assert getattr(zone, name, None) is not None, name

    def test_surface_carries_the_declared_method_signatures(self) -> None:
        """Every checkpoint takes exactly the declared parameters."""
        assert list(inspect.signature(BuildHooks.validate_build).parameters) == [
            "self",
            "moment",
            "tasks",
            "review",
            "skip",
        ]
        assert list(inspect.signature(BuildHooks.emit_build_started).parameters) == [
            "self",
            "moment",
            "tasks",
            "review",
            "skip",
        ]
        assert list(inspect.signature(BuildHooks.emit_pass_started).parameters) == [
            "self",
            "moment",
            "facts",
        ]
        assert list(inspect.signature(BuildHooks.emit_pass_completed).parameters) == [
            "self",
            "moment",
            "facts",
            "exit_code",
        ]
        assert list(inspect.signature(BuildHooks.emit_build_completed).parameters) == [
            "self",
            "moment",
            "exit_code",
            "stages",
            "relocation",
            "statuses",
        ]

    def test_validate_build_returns_the_gate_verdict(self) -> None:
        """The gate's return annotation is the collected verdict."""
        assert inspect.signature(BuildHooks.validate_build).return_annotation == "GateVerdict"

    def test_construction_enumerates_nothing(self, pin_package_environment) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        BuildHooks()

        assert boundary.call_count == 0


# --- Logic tests (real platform) ---


class TestValidationGate:
    def test_gate_collects_vetoes_without_early_stop(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One vetoing tool never stops the walk — the approving tool still runs."""
        boundary = pin_package_environment({"goga_tool_a": ["a-dist"], "goga_tool_b": ["b-dist"]})

        def register_a(hooks: object) -> None:
            def policy(self: object, context: object) -> None:
                context.veto("no deploys on friday")

            hooks.subscribe("build", "validate_build", "policy", policy)  # type: ignore[attr-defined]

        def register_b(hooks: object) -> None:
            def observer(self: object, context: object) -> None:
                self.calls = getattr(self, "calls", 0) + 1

            hooks.subscribe("build", "validate_build", "observer", observer)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_a", register_hooks=register_a)
        install_tool_package("goga_tool_b", register_hooks=register_b)

        surface = BuildHooks()
        verdict = surface.validate_build(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        assert verdict.approved is False
        assert len(verdict.violations) == 1

        violation = verdict.violations[0]
        assert (violation.tool, violation.hook, violation.reason) == ("a", "policy", "no deploys on friday")

        # The walk ran to completion: B's hook ran although A had vetoed.
        assert surface._registry.self_context("b").calls == 1
        assert boundary.call_count == 1

    def test_gate_collects_both_violations_of_two_vetoing_tools(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Every vetoing tool contributes its violation — collected, never overwritten."""
        pin_package_environment({"goga_tool_a": ["a-dist"], "goga_tool_b": ["b-dist"]})

        def register_a(hooks: object) -> None:
            def policy(self: object, context: object) -> None:
                context.veto("policy")

            hooks.subscribe("build", "validate_build", "policy", policy)  # type: ignore[attr-defined]

        def register_b(hooks: object) -> None:
            def guard(self: object, context: object) -> None:
                context.veto("guard")

            hooks.subscribe("build", "validate_build", "guard", guard)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_a", register_hooks=register_a)
        install_tool_package("goga_tool_b", register_hooks=register_b)

        verdict = BuildHooks().validate_build(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        assert verdict.approved is False
        assert verdict.violations == [
            Violation(tool="a", hook="policy", reason="policy"),
            Violation(tool="b", hook="guard", reason="guard"),
        ]

    def test_gate_delivers_read_only_view(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The gate wraps the view — attribute writes are blocked, the facts survive."""
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def writer(self: object, context: object) -> None:
                try:
                    context.skip = True  # type: ignore[misc]
                    self.blocked = False
                except AttributeError as error:
                    self.blocked = True
                    self.error = str(error)

            def observer(self: object, context: object) -> None:
                self.observed_skip = context.skip

            hooks.subscribe("build", "validate_build", "writer", writer)  # type: ignore[attr-defined]
            hooks.subscribe("build", "validate_build", "observer", observer)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        surface = BuildHooks()
        verdict = surface.validate_build(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        self_context = surface._registry.self_context("demo")

        # The write never reached the view — the delivery proxy blocked it.
        assert self_context.blocked is True
        assert "read-only" in self_context.error

        # A later hook of the same tool read the untouched facts.
        assert self_context.observed_skip is False

        # No veto, no crash — the tool approves silently.
        assert verdict.approved is True
        assert verdict.violations == []

    def test_gate_attributes_veto_to_hook_and_replaces_whole(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two vetoing hooks of one tool — the later veto wins whole, once."""
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def first(self: object, context: object) -> None:
                context.veto("one")

            def second(self: object, context: object) -> None:
                context.veto("two")

            hooks.subscribe("build", "validate_build", "first", first)  # type: ignore[attr-defined]
            hooks.subscribe("build", "validate_build", "second", second)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        verdict = BuildHooks().validate_build(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        assert verdict.violations == [Violation(tool="demo", hook="second", reason="two")]

    def test_gate_crash_overrides_veto_and_walk_continues(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A crash is the tool's single violation; the walk continues, nothing escapes."""
        pin_package_environment({"goga_tool_a": ["a-dist"], "goga_tool_b": ["b-dist"]})

        def register_a(hooks: object) -> None:
            def vetoer(self: object, context: object) -> None:
                context.veto("blocked")

            def broken(self: object, context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("build", "validate_build", "vetoer", vetoer)  # type: ignore[attr-defined]
            hooks.subscribe("build", "validate_build", "broken", broken)  # type: ignore[attr-defined]

        def register_b(hooks: object) -> None:
            def observer(self: object, context: object) -> None:
                self.calls = getattr(self, "calls", 0) + 1

            hooks.subscribe("build", "validate_build", "observer", observer)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_a", register_hooks=register_a)
        install_tool_package("goga_tool_b", register_hooks=register_b)

        surface = BuildHooks()
        verdict = surface.validate_build(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        assert verdict.violations == [Violation(tool="a", hook="broken", reason="boom")]
        assert verdict.approved is False

        # The walk continued past the crashing tool — B ran and approved.
        assert surface._registry.self_context("b").calls == 1

    def test_gate_empty_verdict_when_no_subscriptions(self, pin_package_environment) -> None:
        """No tool packages installed — the gate is inert and approves."""
        pin_package_environment({})

        verdict = BuildHooks().validate_build(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        assert verdict.approved is True
        assert verdict.violations == []

    def test_gate_veto_empty_reason_rendered_verbatim(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A whitespace-only reason is stored and delivered as given."""
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def policy(self: object, context: object) -> None:
                context.veto("   ")

            hooks.subscribe("build", "validate_build", "policy", policy)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        verdict = BuildHooks().validate_build(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        assert verdict.approved is False
        assert verdict.violations[0].reason == "   "


class TestNotificationEmissions:
    def test_each_emission_addresses_its_action_with_one_shared_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Each emit_* delegates with its action name; one context instance for every tool."""
        from goga.build.hooks import events as events_module

        boundary = pin_package_environment(
            {"goga_tool_demo": ["demo-dist"], "goga_tool_second": ["second-dist"]}
        )

        def register_all(hooks: object) -> None:
            def make(action: str):
                def hook(self: object, context: object) -> None:
                    setattr(self, action, context)

                return hook

            for action in ("build_started", "pass_started", "pass_completed", "build_completed"):
                hooks.subscribe("build", action, action, make(action))  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_all)
        install_tool_package("goga_tool_second", register_hooks=register_all)

        # A delegating spy over the platform emission — the real delivery
        # still runs; the spy only records the delegated addresses and
        # their context builders.
        real_emit = events_module.emit_hook_event
        delegated: list[tuple[str, str, object]] = []

        def spy(registry: object, domain: str, action: str, context_for: object) -> None:
            delegated.append((domain, action, context_for))
            real_emit(registry, domain, action, context_for)  # type: ignore[arg-type]

        monkeypatch.setattr(events_module, "emit_hook_event", spy)

        moment = _moment()
        tasks = _tasks_facts()
        review = _review_facts()
        relocation = RelocationOutcome(moved=True, destination="docs/plans/completed/plan.md")
        surface = BuildHooks()

        # Nothing returns — fire-and-forget on every checkpoint.
        assert surface.emit_build_started(moment=moment, tasks=tasks, review=review, skip=False) is None
        assert surface.emit_pass_started(moment=moment, facts=tasks) is None
        assert surface.emit_pass_completed(moment=moment, facts=review, exit_code=2) is None
        assert (
            surface.emit_build_completed(
                moment=moment,
                exit_code=2,
                stages=["tasks", "review"],
                relocation=relocation,
                statuses=["backlog", "designed"],
            )
            is None
        )

        # Each emit_* delegated to emit_hook_event on the build domain
        # with exactly its own action name.
        assert [(domain, action) for domain, action, _ in delegated] == [
            ("build", "build_started"),
            ("build", "pass_started"),
            ("build", "pass_completed"),
            ("build", "build_completed"),
        ]

        # One context instance for every tool of each emission — the
        # read-only notification contexts carry no per-tool buffer.
        for _, _, context_for in delegated:
            builder = context_for  # type: ignore[operator]
            assert builder("demo") is builder("second")

        # The delivered views carried the caller's facts — and the
        # distinguishing members pin each action's context: a wrong
        # address would leave another action's shape in the slot.
        demo = surface._registry.self_context("demo")
        second = surface._registry.self_context("second")

        assert demo.build_started.tasks is tasks
        assert demo.build_started.review is review
        assert demo.build_started.skip is False
        assert second.build_started.tasks is tasks

        assert demo.pass_started.facts is tasks
        assert second.pass_started.facts is tasks

        assert demo.pass_completed.facts is review
        assert demo.pass_completed.exit_code == 2
        assert second.pass_completed.exit_code == 2

        assert demo.build_completed.exit_code == 2
        assert demo.build_completed.stages == ["tasks", "review"]
        assert demo.build_completed.relocation is relocation
        assert demo.build_completed.statuses == ["backlog", "designed"]
        assert second.build_completed.stages == ["tasks", "review"]

        # One registry build carried every checkpoint of the surface.
        assert boundary.call_count == 1

    def test_gate_and_emissions_share_the_run_registry(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The gate and every emission of one surface share one registry build."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def policy(self: object, context: object) -> None:
                return None

            def started(self: object, context: object) -> None:
                return None

            def completed(self: object, context: object) -> None:
                return None

            hooks.subscribe("build", "validate_build", "policy", policy)  # type: ignore[attr-defined]
            hooks.subscribe("build", "build_started", "started", started)  # type: ignore[attr-defined]
            hooks.subscribe("build", "build_completed", "completed", completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        moment = _moment()
        tasks = _tasks_facts()
        review = _review_facts()
        surface = BuildHooks()

        verdict = surface.validate_build(moment=moment, tasks=tasks, review=review, skip=False)
        surface.emit_build_started(moment=moment, tasks=tasks, review=review, skip=False)
        surface.emit_build_completed(
            moment=moment,
            exit_code=0,
            stages=["tasks"],
            relocation=RelocationOutcome(moved=False, destination=None),
            statuses=[],
        )

        assert verdict.approved is True
        assert boundary.call_count == 1
