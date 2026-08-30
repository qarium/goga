"""Contract and logic tests for the entity declared in
``goga/history/statuses/CODEMANIFEST`` with ``location: registry.py``:

- ``StatusRegistry(builtin_stages, tool_prefix)`` — the controlled
  registration surface handed to a tool package, the only way a tool status
  enters the scale

Pure registration logic — no mocks and no filesystem: anchors are stored
verbatim and resolved at scale assembly, not here.
"""

from __future__ import annotations

import inspect

import pytest
from goga.history.statuses import Stage, StatusRegistry, StatusScale


def _registry(builtin_scale: StatusScale, tool_prefix: str = "mkdocs") -> StatusRegistry:
    """A registry over the deterministic built-in axis of the cell fixture."""
    return StatusRegistry(builtin_stages=builtin_scale.stages, tool_prefix=tool_prefix)


# --- Contract tests ---


class TestRegistryContract:
    def test_entity_is_importable_from_the_cell_facade(self) -> None:
        """``StatusRegistry`` lives on the cell facade and its ``__all__``."""
        import goga.history.statuses as cell

        assert cell.StatusRegistry is StatusRegistry
        assert "StatusRegistry" in cell.__all__

    def test_constructor_is_kw_only(self, builtin_scale: StatusScale) -> None:
        """``StatusRegistry(builtin_stages=..., tool_prefix=...)`` — keyword-only."""
        registry = StatusRegistry(builtin_stages=builtin_scale.stages, tool_prefix="mkdocs")

        assert registry.tool_prefix == "mkdocs"

        with pytest.raises(TypeError):
            StatusRegistry(builtin_scale.stages, "mkdocs")  # type: ignore[misc]

    def test_register_signature(self) -> None:
        """``register(name, filepath, before=None, after=None)``."""
        parameters = inspect.signature(StatusRegistry.register).parameters

        assert list(parameters) == ["self", "name", "filepath", "before", "after"]
        assert parameters["before"].default is None
        assert parameters["after"].default is None

    def test_stages_property_returns_the_built_in_axis_plus_entries(self, builtin_scale: StatusScale) -> None:
        """``stages -> list[Stage]`` — the built-in axis plus every accepted entry."""
        registry = _registry(builtin_scale)

        assert isinstance(registry.stages, list)
        assert all(isinstance(stage, Stage) for stage in registry.stages)
        assert registry.stages == builtin_scale.stages

    def test_registry_is_not_frozen(self, builtin_scale: StatusScale) -> None:
        """Registration is add-only state — the registry itself stays mutable."""
        assert not StatusRegistry.__dataclass_params__.frozen
        assert StatusRegistry.__dataclass_params__.kw_only


# --- Logic tests ---


class TestRegister:
    def test_register_qualifies_name_and_appends(self, builtin_scale: StatusScale) -> None:
        """``register`` stores the entry qualified and appends it after the axis."""
        registry = _registry(builtin_scale)
        before = len(registry.stages)

        registry.register("published", "mkdocs/published.md", after="planned")

        assert [s.name for s in registry.stages][-1] == "mkdocs.published"
        assert len(registry.stages) == before + 1
        # The built-in part is untouched — same nine names in the same order.
        assert [s.name for s in registry.stages[:9]] == [s.name for s in builtin_scale.stages]

    def test_register_stores_anchors_verbatim(self, builtin_scale: StatusScale) -> None:
        """Both anchors are carried as given — resolution is not done here."""
        registry = _registry(builtin_scale)

        registry.register("reviewed", "review/reviewed.md", before="done", after="scriba.translated")

        entry = registry.stages[-1]
        assert entry.filepath == "review/reviewed.md"
        assert entry.before == "done"
        assert entry.after == "scriba.translated"

    def test_register_missing_anchor_raises(self, builtin_scale: StatusScale) -> None:
        """A tool entry carries at least one anchor — otherwise a clean error."""
        registry = _registry(builtin_scale)

        with pytest.raises(ValueError, match="mkdocs"):
            registry.register("x", "x.md")

        assert registry.stages == builtin_scale.stages

    def test_register_duplicate_qualified_name_raises(self, builtin_scale: StatusScale) -> None:
        """The same qualified name cannot be registered twice in one registry."""
        registry = _registry(builtin_scale)
        registry.register("published", "mkdocs/published.md", after="planned")

        with pytest.raises(ValueError, match=r"mkdocs\.published"):
            registry.register("published", "mkdocs/published.md", after="planned")

        assert len(registry.stages) == 10

    @pytest.mark.parametrize(
        ("name", "filepath"),
        [("", "x.md"), ("x", "")],
        ids=["empty-name", "empty-filepath"],
    )
    def test_register_empty_name_or_filepath_raises(self, builtin_scale: StatusScale, name: str, filepath: str) -> None:
        """A non-empty name and a non-empty filepath are structural requirements."""
        registry = _registry(builtin_scale)

        with pytest.raises(ValueError, match=r"status entry"):
            registry.register(name, filepath, after="planned")

        assert registry.stages == builtin_scale.stages

    def test_stages_returns_a_copy(self, builtin_scale: StatusScale) -> None:
        """Mutating the issued list never reaches the registry content."""
        registry = _registry(builtin_scale)
        registry.register("published", "mkdocs/published.md", after="planned")

        issued = registry.stages
        issued.append(Stage(name="tamper", filepath="tamper.md", after="planned"))

        assert len(registry.stages) == 10
