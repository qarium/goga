"""Contract and logic tests for the entities declared in
``goga/config/hooks/CODEMANIFEST`` with ``location: overlay.py``:

- ``ToolAmendment(tool, amendments)`` — the committed contribution of one
  tool (pure data)
- ``AppliedAmendment(tool, path, intent)`` — one applied amendment, the
  winning contribution of one path (pure data, no value ever)
- ``ConfigOverlay(config, applied)`` — the effective configuration plus
  the applied records and their summary lines

``merge_config_amendments`` (same declared location) lands with its
algorithm in the next task of the plan. This suite covers the data layer
and the descriptor table — the hand-written configuration type tree the
merge resolves amendment paths against, cross-checked against the model
dataclasses so drift is detectable. Supported data only — no mocks, no
filesystem.
"""

from __future__ import annotations

import dataclasses
import importlib
import typing

import pytest
from goga.config.hooks.amendments import PathAmendment
from goga.config.hooks.overlay import (
    _CONFIG_TREE,
    AppliedAmendment,
    ConfigOverlay,
    ToolAmendment,
)
from goga.config.project import (
    AdditionalReviewConfig,
    BuildConfig,
    CodemanifestConfig,
    DepConfig,
    LintConfig,
    PipelineConfig,
    ProjectConfig,
    ReviewConfig,
    TopicsConfig,
)

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


# The nine configuration models of the type tree, by table key.
_MODELS: dict[str, type] = {
    "ProjectConfig": ProjectConfig,
    "BuildConfig": BuildConfig,
    "ReviewConfig": ReviewConfig,
    "AdditionalReviewConfig": AdditionalReviewConfig,
    "PipelineConfig": PipelineConfig,
    "CodemanifestConfig": CodemanifestConfig,
    "DepConfig": DepConfig,
    "LintConfig": LintConfig,
    "TopicsConfig": TopicsConfig,
}

# The node kind of every classified field, per model (the design's table).
_EXPECTED_KINDS: dict[str, dict[str, str]] = {
    "ProjectConfig": {
        "language": "scalar",
        "image": "scalar",
        "dockerfile": "scalar",
        "build": "section",
        "pipeline": "section",
        "commands": "free-form",
        "codemanifest": "section",
        "tools": "mapping",
        "usages": "mapping",
        "lint": "section",
        "topics": "section",
    },
    "BuildConfig": {
        "agent": "scalar",
        "env": "mapping",
        "max_iterations": "scalar",
        "session_timeout": "scalar",
        "idle_timeout": "scalar",
        "wait": "scalar",
        "prompts_dir": "scalar",
        "agents_dir": "scalar",
        "proxy": "scalar",
        "hosts": "mapping",
        "review": "section",
    },
    "ReviewConfig": {
        "skip": "scalar",
        "agent": "scalar",
        "env": "mapping",
        "roles": "list",
        "base_ref": "scalar",
        "strategy": "scalar",
        "finalize": "scalar",
        "additional": "section",
        "session_timeout": "scalar",
        "idle_timeout": "scalar",
        "wait": "scalar",
    },
    "AdditionalReviewConfig": {
        "agent": "scalar",
        "patience": "scalar",
        "max_iterations": "scalar",
    },
    "PipelineConfig": {
        "agent": "scalar",
        "env": "mapping",
        "proxy": "scalar",
        "hosts": "mapping",
    },
    "CodemanifestConfig": {
        "usages": "mapping",
        "annotations": "scalar",
    },
    "DepConfig": {
        "git": "scalar",
        "ref": "scalar",
        "root": "scalar",
    },
    "LintConfig": {
        "ignore": "list",
    },
    "TopicsConfig": {
        "base_ref": "scalar",
        "publish_commit": "scalar",
    },
}

# The scalar nodes carrying a non-str python type (every other scalar is str).
_EXPECTED_INT_OR_BOOL: dict[tuple[str, str], type] = {
    ("BuildConfig", "max_iterations"): int,
    ("AdditionalReviewConfig", "patience"): int,
    ("AdditionalReviewConfig", "max_iterations"): int,
    ("ReviewConfig", "skip"): bool,
}

# Every section node and the model it resolves to.
_EXPECTED_SECTIONS: dict[tuple[str, str], str] = {
    ("ProjectConfig", "build"): "BuildConfig",
    ("ProjectConfig", "pipeline"): "PipelineConfig",
    ("ProjectConfig", "codemanifest"): "CodemanifestConfig",
    ("ProjectConfig", "lint"): "LintConfig",
    ("ProjectConfig", "topics"): "TopicsConfig",
    ("BuildConfig", "review"): "ReviewConfig",
    ("ReviewConfig", "additional"): "AdditionalReviewConfig",
}


# --- Contract tests ---


class TestOverlayContract:
    def test_entities_are_importable_from_the_declared_module(self) -> None:
        """All three entities live on the module the CODEMANIFEST declares."""
        module = importlib.import_module("goga.config.hooks.overlay")

        assert module.ToolAmendment is ToolAmendment
        assert module.AppliedAmendment is AppliedAmendment
        assert module.ConfigOverlay is ConfigOverlay

    def test_entities_are_frozen_kw_only_dataclasses(self) -> None:
        """Pure frozen data — keyword-only construction, no field writes."""
        for cls in (ToolAmendment, AppliedAmendment, ConfigOverlay):
            assert dataclasses.is_dataclass(cls)
            assert is_kw_only_dataclass(cls)
            assert cls.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            ToolAmendment("harden", [])  # type: ignore[misc]

        with pytest.raises(TypeError):
            AppliedAmendment("harden", "build.agent", "set")  # type: ignore[misc]

        with pytest.raises(TypeError):
            ConfigOverlay(_authored(), [])  # type: ignore[misc]

        record = AppliedAmendment(tool="harden", path="build.agent", intent="set")

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.intent = "forced"  # type: ignore[misc]

    def test_entities_carry_exactly_the_declared_fields(self) -> None:
        """``tool, amendments`` / ``tool, path, intent`` / ``config, applied``."""
        assert [field.name for field in dataclasses.fields(ToolAmendment)] == ["tool", "amendments"]
        assert [field.name for field in dataclasses.fields(AppliedAmendment)] == ["tool", "path", "intent"]
        assert [field.name for field in dataclasses.fields(ConfigOverlay)] == ["config", "applied"]

    def test_config_and_applied_are_plain_attributes(self) -> None:
        """Declared fields, not properties — plain read access."""
        for name in ("config", "applied"):
            assert name in ConfigOverlay.__dataclass_fields__
            assert not isinstance(vars(ConfigOverlay).get(name), property)

    def test_summary_lines_is_a_property_returning_list_of_str(self) -> None:
        """A declared property whose return annotation is ``list[str]``."""
        attribute = vars(ConfigOverlay).get("summary_lines")

        assert isinstance(attribute, property)
        assert typing.get_type_hints(attribute.fget)["return"] == list[str]

    def test_applied_record_has_no_value_field(self) -> None:
        """No value channel exists — no configuration value can travel."""
        assert "value" not in AppliedAmendment.__dataclass_fields__
        assert not isinstance(vars(AppliedAmendment).get("value"), property)


# --- Logic tests: the summary lines ---


class TestSummaryLines:
    def test_nothing_applied_summarizes_to_nothing(self) -> None:
        """Empty ``applied`` — the caller prints nothing."""
        overlay = ConfigOverlay(config=_authored(), applied=[])

        assert overlay.summary_lines == []

    def test_summary_lines_compose_header_plus_one_line_per_applied(self) -> None:
        """The pinned format — header, then one line per applied record."""
        overlay = ConfigOverlay(
            config=_authored(),
            applied=[
                AppliedAmendment(tool="harden", path="build.agent", intent="set"),
                AppliedAmendment(tool="guard", path="topics.base_ref", intent="forced"),
            ],
        )

        assert overlay.summary_lines == [
            "config amendments: 2 applied",
            "- harden set build.agent",
            "- guard forced topics.base_ref",
        ]

    def test_no_configuration_value_appears_in_any_line(self) -> None:
        """The records carry no value, so no value can leak into a line."""
        overlay = ConfigOverlay(
            config=_authored(),
            applied=[
                AppliedAmendment(tool="harden", path="build.agent", intent="forced"),
                AppliedAmendment(tool="polite", path="lint.ignore", intent="set"),
            ],
        )

        joined = "\n".join(overlay.summary_lines)

        assert "claude" not in joined
        assert "codex" not in joined
        assert "x/" not in joined


# --- Logic tests: the descriptor table ---


class TestDescriptorTable:
    def test_table_covers_exactly_the_nine_models(self) -> None:
        """The tree records a descriptor for each model, and nothing else."""
        assert set(_CONFIG_TREE) == set(_MODELS)

    @pytest.mark.parametrize(("name", "model"), sorted(_MODELS.items()))
    def test_descriptor_table_matches_model_fields(self, name: str, model: type) -> None:
        """The recorded field-name set equals the dataclass's, both directions."""
        assert {field.name for field in dataclasses.fields(model)} == set(_CONFIG_TREE[name].fields)

    @pytest.mark.parametrize("name", sorted(_EXPECTED_KINDS))
    def test_every_field_is_classified_with_the_declared_kind(self, name: str) -> None:
        """The node kind of every classified field matches the design's table."""
        recorded = {field: node.kind for field, node in _CONFIG_TREE[name].fields.items()}

        assert recorded == _EXPECTED_KINDS[name]

    def test_scalar_nodes_carry_the_admitted_python_type(self) -> None:
        """``str`` everywhere except the pinned ``int`` / ``bool`` leaves."""
        for name, descriptor in _CONFIG_TREE.items():
            for field_name, node in descriptor.fields.items():
                if node.kind != "scalar":
                    continue

                expected = _EXPECTED_INT_OR_BOOL.get((name, field_name), str)

                assert node.scalar_type is expected, (name, field_name)

    def test_section_nodes_carry_the_declared_section_model(self) -> None:
        """Every section node resolves to the model the design's table names."""
        sections = {
            (name, field_name): node.section_model
            for name, descriptor in _CONFIG_TREE.items()
            for field_name, node in descriptor.fields.items()
            if node.kind == "section"
        }

        assert sections == _EXPECTED_SECTIONS
        assert all(model in _CONFIG_TREE for model in sections.values())


# --- Logic tests: pure-data round trips ---


class TestPureData:
    def test_contribution_carries_the_amendments_in_buffer_order(self) -> None:
        """The committed contribution pairs the tool with its buffer order."""
        entries = [
            PathAmendment(path="build.agent", intent="set", value="claude"),
            PathAmendment(path="lint.ignore", intent="force", value=["a/"]),
        ]
        contribution = ToolAmendment(tool="harden", amendments=entries)

        assert contribution.tool == "harden"
        assert contribution.amendments == entries
        assert contribution.amendments is entries

    def test_overlay_carries_the_effective_configuration_verbatim(self) -> None:
        """``config`` and ``applied`` round-trip the constructor facts."""
        authored = _authored()
        applied = [AppliedAmendment(tool="harden", path="build.agent", intent="set")]
        overlay = ConfigOverlay(config=authored, applied=applied)

        assert overlay.config is authored
        assert overlay.applied is applied

    def test_applied_record_accepts_no_value_kwarg(self) -> None:
        """The no-value-leak guarantee holds by construction."""
        with pytest.raises(TypeError):
            AppliedAmendment(tool="harden", path="build.agent", intent="set", value="claude")
