"""Contract and logic tests for the entities declared in
``goga/config/hooks/CODEMANIFEST`` with ``location: amendments.py``:

- ``ConfigAmendment(config)`` — the read-and-amend view of one tool: the
  authored project configuration plus the buffer of this tool's amendments
- ``PathAmendment(path, intent, value)`` — one buffered amendment (pure data)

Supported data only — no mocks, no filesystem: the view carries the
constructor fact verbatim and buffers the amendments of this tool alone.
Task 6 delivers the view through the platform proxy over the real registry.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import typing

import pytest
from goga.config.hooks.amendments import ConfigAmendment, PathAmendment
from goga.config.project import ProjectConfig
from goga.hooks import wrap_context

from tests.conftest import is_kw_only_dataclass


def _authored() -> ProjectConfig:
    """A minimal authored configuration — every optional branch absent."""
    return ProjectConfig(
        language="python",
        image=None,
        dockerfile=None,
        build=None,
        pipeline=None,
    )


@pytest.fixture
def authored() -> ProjectConfig:
    """The authored loaded project configuration — the shared read surface."""
    return _authored()


@pytest.fixture
def view(authored: ProjectConfig) -> ConfigAmendment:
    """The read-and-amend view of one tool."""
    return ConfigAmendment(config=authored)


# --- Contract tests ---


class TestAmendmentContract:
    def test_entities_are_importable_from_the_declared_module(self) -> None:
        """Both entities live on the module the CODEMANIFEST declares."""
        module = importlib.import_module("goga.config.hooks.amendments")

        assert module.ConfigAmendment is ConfigAmendment
        assert module.PathAmendment is PathAmendment

    def test_view_is_a_kw_only_dataclass(self) -> None:
        """Positional construction raises ``TypeError``."""
        assert dataclasses.is_dataclass(ConfigAmendment)
        assert is_kw_only_dataclass(ConfigAmendment)

        with pytest.raises(TypeError):
            ConfigAmendment(_authored())  # type: ignore[misc]

    def test_view_carries_exactly_the_declared_fields(self) -> None:
        """``config`` plus the private buffer — names, order, no view defaults."""
        assert [field.name for field in dataclasses.fields(ConfigAmendment)] == ["config", "_amendments"]

        config_field = ConfigAmendment.__dataclass_fields__["config"]

        assert config_field.default is dataclasses.MISSING
        assert config_field.default_factory is dataclasses.MISSING

    def test_config_is_a_plain_attribute(self) -> None:
        """``config`` is a declared field, not a property — plain read access."""
        assert "config" in ConfigAmendment.__dataclass_fields__
        assert not isinstance(vars(ConfigAmendment).get("config"), property)

        assert _authored().language == "python"

    def test_buffer_is_private_init_false_default_empty(self) -> None:
        """``_amendments`` — not constructor surface, not repr, starts empty."""
        buffer = ConfigAmendment.__dataclass_fields__["_amendments"]

        assert buffer.init is False
        assert buffer.repr is False
        assert buffer.default_factory is dict
        assert ConfigAmendment(config=_authored())._amendments == {}

    def test_set_and_force_carry_the_declared_signatures(self) -> None:
        """``set(path, value)`` / ``force(path, value)`` — two parameters, typed."""
        for name in ("set", "force"):
            method = getattr(ConfigAmendment, name)

            assert callable(method)
            assert list(inspect.signature(method).parameters) == ["self", "path", "value"]

            hints = typing.get_type_hints(method)

            assert hints["path"] is str
            assert typing.get_args(hints["value"]) == (str, int, bool, list[str])

    def test_entry_is_a_frozen_kw_only_dataclass(self) -> None:
        """``PathAmendment`` — pure frozen data, keyword-only construction."""
        assert dataclasses.is_dataclass(PathAmendment)
        assert is_kw_only_dataclass(PathAmendment)
        assert PathAmendment.__dataclass_params__.frozen

        entry = PathAmendment(path="build.agent", intent="set", value="claude")

        with pytest.raises(TypeError):
            PathAmendment("build.agent", "set", "claude")  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.value = "codex"  # type: ignore[misc]

    def test_entry_carries_exactly_the_declared_fields(self) -> None:
        """``path, intent, value`` — names, order, all required."""
        assert [field.name for field in dataclasses.fields(PathAmendment)] == ["path", "intent", "value"]

        defaults = [(field.name, field.default) for field in dataclasses.fields(PathAmendment)]

        assert defaults == [
            ("path", dataclasses.MISSING),
            ("intent", dataclasses.MISSING),
            ("value", dataclasses.MISSING),
        ]


# --- Logic tests: the buffer ---


class TestBufferSemantics:
    def test_set_stores_a_set_entry(self, view: ConfigAmendment) -> None:
        """``set`` buffers a ``set``-intent amendment of the exact value."""
        view.set("build.agent", "claude")

        assert list(view._amendments.values()) == [
            PathAmendment(path="build.agent", intent="set", value="claude"),
        ]

    def test_force_stores_a_force_entry(self, view: ConfigAmendment) -> None:
        """``force`` buffers a ``force``-intent amendment of the exact value."""
        view.force("build.agent", "claude")

        assert list(view._amendments.values()) == [
            PathAmendment(path="build.agent", intent="force", value="claude"),
        ]

    def test_value_vocabulary_round_trips_verbatim(self, view: ConfigAmendment) -> None:
        """Every vocabulary member buffers as the exact object passed."""
        values: list[str | int | bool | list[str]] = ["s", 3, True, ["a/", "b/"]]

        for index, value in enumerate(values):
            view.set(f"p{index}", value)

        assert [entry.value for entry in view._amendments.values()] == values

    def test_same_path_replacement_keeps_one_entry_at_first_position(
        self,
        view: ConfigAmendment,
    ) -> None:
        """A later same-path call replaces the earlier entry, first position kept."""
        view.set("p", 1)
        view.set("q", "v")
        view.force("p", 2)

        assert list(view._amendments) == ["p", "q"]
        assert view._amendments["p"] == PathAmendment(path="p", intent="force", value=2)
        assert view._amendments["q"] == PathAmendment(path="q", intent="set", value="v")

    def test_buffers_belong_to_this_view_alone(self, authored: ProjectConfig) -> None:
        """Two views over the same config never share buffer state."""
        first = ConfigAmendment(config=authored)
        second = ConfigAmendment(config=authored)

        first.set("build.agent", "claude")

        assert list(first._amendments) == ["build.agent"]
        assert second._amendments == {}

    def test_out_of_vocabulary_inputs_are_stored_verbatim(self, view: ConfigAmendment) -> None:
        """No validation lives here — a bad path/value fails later, in the merge."""
        value = {"deep": "mapping"}

        view.set(("not", "a", "str"), value)
        view.force("build.agent", value)

        assert view._amendments[("not", "a", "str")] == PathAmendment(
            path=("not", "a", "str"),
            intent="set",
            value=value,
        )
        assert view._amendments["build.agent"].value is value

    def test_set_changes_no_authored_fact(self, view: ConfigAmendment, authored: ProjectConfig) -> None:
        """The call buffers only — the authored object stays untouched."""
        view.set("build.agent", "claude")

        assert view.config is authored
        assert authored.build is None


class TestViewFacts:
    def test_constructor_fact_round_trips_verbatim(
        self,
        view: ConfigAmendment,
        authored: ProjectConfig,
    ) -> None:
        """The read delivers the authored object by reference."""
        assert view.config is authored

    def test_reads_deliver_the_authored_values(self, view: ConfigAmendment) -> None:
        """Attribute reads observe the authored configuration as loaded."""
        assert view.config.language == "python"
        assert view.config.build is None


# --- Logic tests: the delivery proxy interop ---


class TestDeliveryProxyInterop:
    def test_reads_and_method_calls_pass_through(
        self,
        view: ConfigAmendment,
        authored: ProjectConfig,
    ) -> None:
        """The proxy resolves reads and bound-method calls on the view."""
        proxy = wrap_context(view)

        assert proxy.config is authored
        assert proxy.config.language == "python"

        proxy.set("build.agent", "claude")
        proxy.force("topics.base_ref", "origin/main")

        assert view._amendments["build.agent"] == PathAmendment(
            path="build.agent",
            intent="set",
            value="claude",
        )
        assert view._amendments["topics.base_ref"].intent == "force"

    def test_attribute_assignment_on_the_proxy_is_blocked(
        self,
        view: ConfigAmendment,
        authored: ProjectConfig,
    ) -> None:
        """Writes raise a clean error — the view stays as it was."""
        proxy = wrap_context(view)

        with pytest.raises(
            AttributeError,
            match="the delivered context is read-only: attribute assignment is blocked",
        ):
            proxy.config = _authored()  # type: ignore[misc]

        with pytest.raises(
            AttributeError,
            match="the delivered context is read-only: attribute deletion is blocked",
        ):
            del proxy._amendments  # type: ignore[attr-defined]

        assert view.config is authored
        assert view._amendments == {}
