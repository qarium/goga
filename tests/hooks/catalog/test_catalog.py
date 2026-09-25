"""Contract and logic tests for the entities declared in
``goga/hooks/catalog/CODEMANIFEST`` with ``location: catalog.py``:

- ``Action(domain, name, error_class)`` — one catalog record, a named
  subscription address with its error class
- ``declared_actions()`` — the declared action catalog, the single source of
  known addresses

Supported data only — no mocks: the catalog is maintained data, not
discovery over installed packages.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest
from goga.hooks.catalog import Action, declared_actions

from tests.conftest import is_kw_only_dataclass

# --- Contract tests ---


class TestCatalogContract:
    def test_entities_are_importable_from_the_package_facade(self) -> None:
        """Both entities live on the cell package and its ``__all__`` is exact."""
        import goga.hooks.catalog as cell

        assert cell.Action is Action
        assert cell.declared_actions is declared_actions
        assert cell.__all__ == ["Action", "declared_actions"]

    def test_action_is_a_kw_only_frozen_dataclass(self) -> None:
        """``Action(domain=..., name=..., error_class=...)`` — keyword-only, frozen."""
        action = Action(domain="statuses", name="register_statuses", error_class="soft")

        assert action.domain == "statuses"
        assert action.name == "register_statuses"
        assert action.error_class == "soft"

        assert dataclasses.is_dataclass(Action)
        assert Action.__dataclass_params__.frozen
        assert is_kw_only_dataclass(Action)

        with pytest.raises(TypeError):
            Action("statuses", "register_statuses", "soft")  # type: ignore[misc]

    def test_action_assignment_raises_frozen_instance_error(self) -> None:
        """A published record is never rewritten."""
        action = Action(domain="statuses", name="register_statuses", error_class="soft")

        with pytest.raises(dataclasses.FrozenInstanceError):
            action.domain = "other"  # type: ignore[misc]

    def test_action_carries_exactly_the_three_declared_fields(self) -> None:
        """No computed properties, no extra state — the record is data only."""
        field_names = [field.name for field in dataclasses.fields(Action)]

        assert field_names == ["domain", "name", "error_class"]

    def test_declared_actions_signature(self) -> None:
        """``declared_actions() -> list[Action]`` — no parameters."""
        parameters = inspect.signature(declared_actions).parameters
        return_hint = typing.get_type_hints(declared_actions)["return"]

        assert list(parameters) == []
        assert return_hint == list[Action]

    def test_declared_actions_carries_the_five_build_records(self) -> None:
        """The build domain block — one hard gate, four soft notifications.

        ``build/validate_build`` (hard) is the verdict-collecting gate of the
        build cycle; ``build_started``, ``pass_started``, ``pass_completed``,
        and ``build_completed`` (soft) only notify. Every address the build
        zone emits must resolve here.
        """
        build = {
            action.name: action.error_class
            for action in declared_actions()
            if action.domain == "build"
        }

        assert build == {
            "validate_build": "hard",
            "build_started": "soft",
            "pass_started": "soft",
            "pass_completed": "soft",
            "build_completed": "soft",
        }

    def test_schema_amend_cell_record_present(self) -> None:
        """The schema cell-amendment action — the hard checkpoint of the schema domain.

        ``schema/amend_cell`` (hard) stops the generation at the first
        failing tool with a clean error naming the tool, the action, and the
        failing cell path; a structurally malformed contribution of the
        delivery is treated identically. The ``schema`` block orders between
        ``pipeline`` and ``statuses`` in the ``(domain, name)`` sort, the
        ordering stays stable with no duplicated record, and the
        pre-existing records are unchanged — the whole catalog is pinned
        against a frozen expected list of all other records.
        """
        records = declared_actions()

        assert Action(domain="schema", name="amend_cell", error_class="hard") in records

        pre_existing = [
            ("build", "build_completed", "soft"),
            ("build", "build_started", "soft"),
            ("build", "pass_completed", "soft"),
            ("build", "pass_started", "soft"),
            ("build", "validate_build", "hard"),
            ("config", "amend_config", "hard"),
            ("onboarding", "amend_config", "soft"),
            ("onboarding", "declare_session", "soft"),
            ("pipeline", "amend_workflow", "hard"),
            ("pipeline", "run_completed", "soft"),
            ("pipeline", "run_created", "soft"),
            ("statuses", "register_statuses", "soft"),
            ("topics", "amend_creation", "soft"),
            ("topics", "amend_todo_entry", "soft"),
            ("topics", "topic_created", "soft"),
            ("topics", "topic_deleted", "soft"),
            ("topics", "topic_published", "soft"),
            ("topics", "topic_switched", "soft"),
            ("topics", "topic_todo_entered", "soft"),
            ("usages", "status_completed", "soft"),
            ("usages", "status_started", "soft"),
            ("usages", "sync_completed", "soft"),
            ("usages", "sync_started", "soft"),
        ]

        triples = [(action.domain, action.name, action.error_class) for action in records]

        assert all(triple in triples for triple in pre_existing)
        assert len(triples) == len(pre_existing) + 1

        schema = [(action.name, action.error_class) for action in records if action.domain == "schema"]

        assert schema == [("amend_cell", "hard")]

        domains = [action.domain for action in records]

        assert domains.index("pipeline") < domains.index("schema") < domains.index("statuses")

        pairs = [(action.domain, action.name) for action in records]

        assert pairs == sorted(pairs)
        assert len(pairs) == len(set(pairs))
        assert len(records) == 24


# --- Logic tests ---


class TestDeclaredActions:
    def test_declared_actions_carries_the_statuses_action(self) -> None:
        """The seed record — the statuses registration action, soft failures."""
        records = {(action.domain, action.name): action for action in declared_actions()}

        assert ("statuses", "register_statuses") in records
        assert records[("statuses", "register_statuses")].error_class == "soft"

    def test_catalog_carries_onboarding_actions(self) -> None:
        """Both onboarding session actions are declared addresses, soft failures.

        The published statuses record stays untouched and the domain-then-name
        ordering holds with the new records in place.
        """
        records = declared_actions()
        triples = {(r.domain, r.name, r.error_class) for r in records}

        assert ("onboarding", "declare_session", "soft") in triples
        assert ("onboarding", "amend_config", "soft") in triples
        assert [(r.domain, r.name) for r in records] == sorted((r.domain, r.name) for r in records)
        assert ("statuses", "register_statuses") in {(r.domain, r.name) for r in records}

    def test_declared_actions_carries_the_seven_topics_records(self) -> None:
        """The seven topics lifecycle actions are declared addresses, soft failures.

        Five post-fact notifications and two pre-fixation amendments — every
        checkpoint the topics zone emits resolves its address here. An
        address the zone emits but the catalog misses is a runtime
        ValueError in every flow, so the record set is pinned against
        drift, together with the complete total: 1 config + 2 onboarding +
        5 build + 3 pipeline + 1 schema + 1 statuses + 7 topics + 4 usages.
        """
        topics = [action for action in declared_actions() if action.domain == "topics"]

        assert [(action.name, action.error_class) for action in topics] == [
            ("amend_creation", "soft"),
            ("amend_todo_entry", "soft"),
            ("topic_created", "soft"),
            ("topic_deleted", "soft"),
            ("topic_published", "soft"),
            ("topic_switched", "soft"),
            ("topic_todo_entered", "soft"),
        ]
        assert len(declared_actions()) == 24

    def test_declared_actions_carries_the_four_usages_records(self) -> None:
        """The four usages run-level moments are declared addresses, soft failures.

        ``sync_started`` and ``sync_completed`` bracket a usages sync run;
        ``status_started`` and ``status_completed`` bracket a status run. All
        four only notify — the operations' exit codes and output are
        independent of any subscription — and the ``usages`` block sorts
        last in the ``(domain, name)`` order.
        """
        usages = [(a.name, a.error_class) for a in declared_actions() if a.domain == "usages"]

        assert usages == [
            ("status_completed", "soft"),
            ("status_started", "soft"),
            ("sync_completed", "soft"),
            ("sync_started", "soft"),
        ]
        assert len(declared_actions()) == 24

        domains = [a.domain for a in declared_actions()]

        assert domains.index("topics") < domains.index("usages")  # the block sorts last

    def test_catalog_carries_the_three_pipeline_records(self) -> None:
        """The pipeline domain block — the platform's first hard action, two soft notifications.

        ``pipeline/amend_workflow`` (hard) stops a run on hook failure;
        ``pipeline/run_created`` and ``pipeline/run_completed`` (soft) only
        notify. The block orders between ``build`` and ``statuses`` in the
        ``(domain, name)`` sort, and the pre-build records are unchanged —
        the catalog grows to 24 records additively.
        """
        records = declared_actions()
        triples = {(r.domain, r.name, r.error_class) for r in records}

        assert ("pipeline", "amend_workflow", "hard") in triples
        assert ("pipeline", "run_completed", "soft") in triples
        assert ("pipeline", "run_created", "soft") in triples

        pipeline = [action.name for action in records if action.domain == "pipeline"]

        assert pipeline == ["amend_workflow", "run_completed", "run_created"]

        domains = [action.domain for action in records]

        assert domains.index("onboarding") < domains.index("pipeline") < domains.index("statuses")
        assert len(records) == 24

        pre_existing = [
            ("onboarding", "amend_config", "soft"),
            ("onboarding", "declare_session", "soft"),
            ("statuses", "register_statuses", "soft"),
            ("topics", "amend_creation", "soft"),
            ("topics", "amend_todo_entry", "soft"),
            ("topics", "topic_created", "soft"),
            ("topics", "topic_deleted", "soft"),
            ("topics", "topic_published", "soft"),
            ("topics", "topic_switched", "soft"),
            ("topics", "topic_todo_entered", "soft"),
        ]

        assert all(triple in triples for triple in pre_existing)

    def test_catalog_carries_the_five_build_records(self) -> None:
        """The build domain block — the gate plus the four cycle notifications.

        ``build/validate_build`` (hard) is the verdict-collecting gate that
        stops the build before any pass; the four soft notifications only
        observe the cycle. The pre-existing records are byte-identical —
        the whole catalog is pinned against a frozen expected list, and the
        ``build`` block orders first in the ``(domain, name)`` sort.
        """
        records = declared_actions()

        build = [action for action in records if action.domain == "build"]

        assert [(action.name, action.error_class) for action in build] == [
            ("build_completed", "soft"),
            ("build_started", "soft"),
            ("pass_completed", "soft"),
            ("pass_started", "soft"),
            ("validate_build", "hard"),
        ]

        expected = [
            ("build", "build_completed", "soft"),
            ("build", "build_started", "soft"),
            ("build", "pass_completed", "soft"),
            ("build", "pass_started", "soft"),
            ("build", "validate_build", "hard"),
            ("config", "amend_config", "hard"),
            ("onboarding", "amend_config", "soft"),
            ("onboarding", "declare_session", "soft"),
            ("pipeline", "amend_workflow", "hard"),
            ("pipeline", "run_completed", "soft"),
            ("pipeline", "run_created", "soft"),
            ("schema", "amend_cell", "hard"),
            ("statuses", "register_statuses", "soft"),
            ("topics", "amend_creation", "soft"),
            ("topics", "amend_todo_entry", "soft"),
            ("topics", "topic_created", "soft"),
            ("topics", "topic_deleted", "soft"),
            ("topics", "topic_published", "soft"),
            ("topics", "topic_switched", "soft"),
            ("topics", "topic_todo_entered", "soft"),
            ("usages", "status_completed", "soft"),
            ("usages", "status_started", "soft"),
            ("usages", "sync_completed", "soft"),
            ("usages", "sync_started", "soft"),
        ]

        assert [(a.domain, a.name, a.error_class) for a in records] == expected

        domains = [action.domain for action in records]

        assert domains.index("build") < domains.index("onboarding")
        assert [(a.domain, a.name) for a in records] == sorted(
            (a.domain, a.name) for a in records
        )

    def test_config_amend_config_record_present(self) -> None:
        """The config amendment action — the hard checkpoint of the config zone.

        ``config/amend_config`` (hard) stops the command at the first
        failing tool with a clean error naming the tool and the action; a
        structurally malformed contribution of the delivery is treated
        identically. The ``config`` block orders between ``build`` and
        ``onboarding`` in the ``(domain, name)`` sort, the ordering stays
        stable with no duplicated record, and the pre-existing records are
        unchanged — the whole catalog is pinned against a frozen expected
        list of all other records.
        """
        records = declared_actions()

        assert Action(domain="config", name="amend_config", error_class="hard") in records

        pre_existing = [
            ("build", "build_completed", "soft"),
            ("build", "build_started", "soft"),
            ("build", "pass_completed", "soft"),
            ("build", "pass_started", "soft"),
            ("build", "validate_build", "hard"),
            ("onboarding", "amend_config", "soft"),
            ("onboarding", "declare_session", "soft"),
            ("pipeline", "amend_workflow", "hard"),
            ("pipeline", "run_completed", "soft"),
            ("pipeline", "run_created", "soft"),
            ("schema", "amend_cell", "hard"),
            ("statuses", "register_statuses", "soft"),
            ("topics", "amend_creation", "soft"),
            ("topics", "amend_todo_entry", "soft"),
            ("topics", "topic_created", "soft"),
            ("topics", "topic_deleted", "soft"),
            ("topics", "topic_published", "soft"),
            ("topics", "topic_switched", "soft"),
            ("topics", "topic_todo_entered", "soft"),
            ("usages", "status_completed", "soft"),
            ("usages", "status_started", "soft"),
            ("usages", "sync_completed", "soft"),
            ("usages", "sync_started", "soft"),
        ]

        triples = [(action.domain, action.name, action.error_class) for action in records]

        assert all(triple in triples for triple in pre_existing)
        assert len(triples) == len(pre_existing) + 1

        config = [(action.name, action.error_class) for action in records if action.domain == "config"]

        assert config == [("amend_config", "hard")]

        domains = [action.domain for action in records]

        assert domains.index("build") < domains.index("config") < domains.index("onboarding")

        pairs = [(action.domain, action.name) for action in records]

        assert pairs == sorted(pairs)
        assert len(pairs) == len(set(pairs))
        assert len(records) == 24

    def test_declared_actions_is_deterministic_and_complete(self) -> None:
        """Same records in ``(domain, name)`` order on every call, unfiltered.

        A fresh list per call — mutating a returned list never reaches the
        catalog constant.
        """
        first = declared_actions()
        second = declared_actions()

        assert first == second
        assert first is not second
        assert [(a.domain, a.name) for a in first] == sorted((a.domain, a.name) for a in first)

        first.clear()

        assert declared_actions() == second
        assert first != second

    def test_declared_actions_records_are_well_formed(self) -> None:
        """Non-empty addresses, valid error classes, unique pairs."""
        records = declared_actions()
        pairs = [(action.domain, action.name) for action in records]

        assert all(action.domain for action in records)
        assert all(action.name for action in records)
        assert {action.error_class for action in records} <= {"soft", "hard"}
        assert len(pairs) == len(set(pairs))
