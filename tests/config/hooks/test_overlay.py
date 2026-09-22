"""Contract and logic tests for the entities declared in
``goga/config/hooks/CODEMANIFEST`` with ``location: overlay.py``:

- ``ToolAmendment(tool, amendments)`` — the committed contribution of one
  tool (pure data)
- ``AppliedAmendment(tool, path, intent)`` — one applied amendment, the
  winning contribution of one path (pure data, no value ever)
- ``ConfigOverlay(config, applied)`` — the effective configuration plus
  the applied records and their summary lines
- ``merge_config_amendments(base, contributions)`` — the deterministic,
  pure composition of the committed contributions over the authored base

The suite also covers the descriptor table — the hand-written
configuration type tree the merge resolves amendment paths against,
cross-checked against the model dataclasses so drift is detectable.
Supported data only — no mocks, no filesystem.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import re
import typing

import pytest
from goga.config.hooks.amendments import PathAmendment
from goga.config.hooks.overlay import (
    _CONFIG_TREE,
    AppliedAmendment,
    ConfigOverlay,
    ToolAmendment,
    merge_config_amendments,
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


def _authored(**overrides: object) -> ProjectConfig:
    """A minimal authored configuration — every optional branch absent.

    Args:
        overrides: authored fields to set over the minimal base (a
            present section, an authored ``""``/``False``, an authored
            usages tree, ...).
    """
    values: dict[str, object] = {
        "language": "python",
        "image": None,
        "dockerfile": None,
        "build": None,
        "pipeline": None,
    }
    values.update(overrides)
    return ProjectConfig(**values)  # type: ignore[arg-type]


def _amendment(path: str, intent: str, value: str | int | bool | list[str] | dict[str, str]) -> PathAmendment:
    """Build one buffered entry."""
    return PathAmendment(path=path, intent=intent, value=value)


def _contribution(tool: str, *amendments: PathAmendment) -> ToolAmendment:
    """Build one committed contribution — the tool and its buffer order."""
    return ToolAmendment(tool=tool, amendments=list(amendments))


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
        assert {field.name for field in dataclasses.fields(model)} == set(_CONFIG_TREE[name])

    @pytest.mark.parametrize("name", sorted(_EXPECTED_KINDS))
    def test_every_field_is_classified_with_the_declared_kind(self, name: str) -> None:
        """The node kind of every classified field matches the design's table."""
        recorded = {field: node.kind for field, node in _CONFIG_TREE[name].items()}

        assert recorded == _EXPECTED_KINDS[name]

    def test_scalar_nodes_carry_the_admitted_python_type(self) -> None:
        """``str`` everywhere except the pinned ``int`` / ``bool`` leaves."""
        for name, descriptor in _CONFIG_TREE.items():
            for field_name, node in descriptor.items():
                if node.kind != "scalar":
                    continue

                expected = _EXPECTED_INT_OR_BOOL.get((name, field_name), str)

                assert node.scalar_type is expected, (name, field_name)

    def test_section_nodes_carry_the_declared_section_model(self) -> None:
        """Every section node resolves to the model the design's table names."""
        sections = {
            (name, field_name): node.section_model
            for name, descriptor in _CONFIG_TREE.items()
            for field_name, node in descriptor.items()
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


# --- Contract tests: the merge routine ---


class TestMergeContract:
    def test_merge_is_importable_from_the_declared_module(self) -> None:
        """The routine lives on the module the CODEMANIFEST declares."""
        module = importlib.import_module("goga.config.hooks.overlay")

        assert module.merge_config_amendments is merge_config_amendments

    def test_merge_signature_matches_the_contract(self) -> None:
        """``(base, contributions) -> ConfigOverlay``, as declared."""
        parameters = list(inspect.signature(merge_config_amendments).parameters)

        assert parameters == ["base", "contributions"]

        hints = typing.get_type_hints(merge_config_amendments)

        assert hints["base"] is ProjectConfig
        assert hints["contributions"] == list[ToolAmendment]
        assert hints["return"] is ConfigOverlay

    def test_empty_contributions_is_the_passthrough(self) -> None:
        """No contributions — the passed object itself, zero rebuild."""
        base = _authored()
        overlay = merge_config_amendments(base, [])

        assert overlay.config is base
        assert overlay.applied == []
        assert overlay.summary_lines == []


# --- Logic tests: the merge algebra (the design's verified scenarios) ---


class TestMergeAlgebra:
    def test_set_applies_on_silent_path(self) -> None:
        """A silent authored branch takes the set; the base stays pure."""
        base = _authored()

        overlay = merge_config_amendments(base, [_contribution("harden", _amendment("build.agent", "set", "claude"))])

        assert overlay.config.build is not None
        assert overlay.config.build.agent == "claude"
        assert overlay.applied == [AppliedAmendment(tool="harden", path="build.agent", intent="set")]
        assert overlay.summary_lines == ["config amendments: 1 applied", "- harden set build.agent"]
        assert base.build is None

    def test_force_overwrites_authored_and_beats_set_cross_order(self) -> None:
        """Force wins over authored and over any set, in either order."""
        base = _authored(topics=TopicsConfig(base_ref="origin/dev", publish_commit=None))
        polite = _contribution("polite", _amendment("topics.base_ref", "set", "origin/main"))
        guard = _contribution("guard", _amendment("topics.base_ref", "force", "origin/stable"))

        for contributions in ([polite, guard], [guard, polite]):
            overlay = merge_config_amendments(base, contributions)

            assert overlay.config.topics is not None
            assert overlay.config.topics.base_ref == "origin/stable"
            assert [(r.tool, r.path, r.intent) for r in overlay.applied] == [
                ("guard", "topics.base_ref", "forced"),
            ]
            assert all("polite" not in line for line in overlay.summary_lines)

    def test_later_tool_wins_equal_intent(self) -> None:
        """Equal intent on one path — the later tool in enumeration wins."""
        early = _contribution("a", _amendment("pipeline.env.LOG_LEVEL", "set", "INFO"))
        late = _contribution("b", _amendment("pipeline.env.LOG_LEVEL", "set", "DEBUG"))

        overlay = merge_config_amendments(_authored(), [early, late])

        assert overlay.config.pipeline is not None
        assert overlay.config.pipeline.env == {"LOG_LEVEL": "DEBUG"}
        assert [(r.tool, r.path, r.intent) for r in overlay.applied] == [
            ("b", "pipeline.env.LOG_LEVEL", "set"),
        ]

    def test_unknown_path_is_structural_failure(self) -> None:
        """An unknown path fails naming the tool, before anything applies."""
        base = _authored()
        snapshot = dataclasses.astuple(base)
        good = _contribution("good", _amendment("build.agent", "set", "claude"))
        bad = _contribution("harden", _amendment("build.nonexistent", "set", "claude"))

        with pytest.raises(ValueError, match=r"tool harden: amendment at 'build\.nonexistent'"):
            merge_config_amendments(base, [good, bad])

        assert dataclasses.astuple(base) == snapshot

    def test_non_leaf_address_and_wrong_type_fail(self) -> None:
        """Non-leaf addresses and wrong-typed values — the pinned wordings."""
        cases = [
            (_amendment("build.env", "force", {"KEY": "v"}), "non-leaf"),
            (_amendment("build.max_iterations", "force", True), r"wrong type: expected int, got bool"),
            (_amendment("build.agent.deep", "force", "x"), "unknown path"),
            (_amendment("commands.run.cmd", "force", "x"), "unknown path"),
        ]

        for amendment, wording in cases:
            with pytest.raises(ValueError, match=wording):
                merge_config_amendments(_authored(), [_contribution("harden", amendment)])

    def test_path_structure_failures_are_pinned(self) -> None:
        """Every malformed path shape fails with its pinned wording."""
        cases = [
            (_amendment("build", "force", "x"), "addresses a non-leaf node: a whole section"),
            (_amendment("commands", "force", {"k": "v"}), "addresses a non-leaf node: the whole free-form mapping"),
            (_amendment("tools.viewer.deep", "force", "x"), "continues below the mapping entry 'tools.viewer'"),
            (_amendment("usages.docs", "force", "x"), "a usages branch without the group.dep.leaf descent"),
            (_amendment("usages.docs.scriba", "force", "x"), "a usages branch without the group.dep.leaf descent"),
            (_amendment("usages.docs.scriba.git.deep", "force", "x"), "continues below the leaf"),
            (_amendment("usages.docs.scriba.nothing", "force", "x"), "'nothing' is not a field of DepConfig"),
        ]

        for amendment, wording in cases:
            with pytest.raises(ValueError, match=wording):
                merge_config_amendments(_authored(), [_contribution("harden", amendment)])

    def test_non_string_path_fails_naming_the_tool(self) -> None:
        """A buffered non-string path fails at the merge, verbatim in the message."""
        entry = PathAmendment(path=("not", "a", "str"), intent="set", value="claude")

        with pytest.raises(ValueError, match="names an unknown path: the path is not a string") as excinfo:
            merge_config_amendments(_authored(), [_contribution("harden", entry)])

        assert "tool harden" in str(excinfo.value)

    def test_wrong_type_failures_per_node_kind(self) -> None:
        """The value guard holds at every leaf kind — list, scalar, entry, dep root."""
        cases = [
            (_amendment("lint.ignore", "force", "x/"), "a list of strings is required"),
            (_amendment("lint.ignore", "force", ["a/", 1]), "a list of strings is required"),
            (_amendment("build.agent", "force", 3), "expected str, got int"),
            (_amendment("build.review.skip", "force", "yes"), "expected bool, got str"),
            (_amendment("tools.viewer", "force", 3), "expected str, got int"),
            (_amendment("usages.docs.scriba.root", "force", 3), "usages dep 'root' must be a string"),
        ]

        for amendment, wording in cases:
            with pytest.raises(ValueError, match=wording):
                merge_config_amendments(_authored(), [_contribution("guard", amendment)])

    def test_unsafe_usages_group_and_dep_names_fail(self) -> None:
        """A traversal-shaped group/dep key never composes — the loader's own rule."""
        for path in (
            "usages./tmp/evil.dep.git",
            "usages..dep.git",
            "usages.docs..git",
            "usages.do/cs.scriba.git",
            "usages.docs.sc/riba.git",
            "usages.docs.scri\\ba.git",
        ):
            with pytest.raises(ValueError, match=re.escape("must be a plain name without '/' or '..'")):
                merge_config_amendments(
                    _authored(),
                    [_contribution("guard", _amendment(path, "force", "https://example/goga"))],
                )

    def test_dep_values_stored_stripped_and_root_normalized(self) -> None:
        """git/ref compose stripped; a safe root composes in its canonical form."""
        overlay = merge_config_amendments(
            _authored(),
            [
                _contribution(
                    "guard",
                    _amendment("usages.docs.scriba.git", "set", " https://example/goga "),
                    _amendment("usages.docs.scriba.ref", "set", " v2 "),
                    _amendment("usages.docs.scriba.root", "force", "docs\\cells"),
                ),
            ],
        )

        scriba = overlay.config.usages["docs"]["scriba"]

        assert scriba.git == "https://example/goga"
        assert scriba.ref == "v2"
        assert scriba.root == "docs/cells"

    def test_set_on_present_mapping_entry_drops_silently(self) -> None:
        """A set on a present authored mapping entry drops — no record, no line."""
        base = _authored(tools={"afm": "1.0.x"})

        overlay = merge_config_amendments(base, [_contribution("guard", _amendment("tools.afm", "set", "2.x"))])

        assert overlay.config.tools == {"afm": "1.0.x"}
        assert overlay.applied == []
        assert overlay.summary_lines == []

    def test_last_force_beats_earlier_force(self) -> None:
        """Two forcing tools on one path — the later in enumeration order wins."""
        early = _contribution("early", _amendment("build.agent", "force", "first"))
        late = _contribution("late", _amendment("build.agent", "force", "second"))

        overlay = merge_config_amendments(_authored(), [early, late])

        assert overlay.config.build is not None
        assert overlay.config.build.agent == "second"
        assert [(r.tool, r.path, r.intent) for r in overlay.applied] == [("late", "build.agent", "forced")]

    def test_materialized_dep_without_git_fails(self) -> None:
        """The final pass rejects a materialized dep missing its git."""
        base = _authored()

        with pytest.raises(ValueError, match=r"usages\.docs\.scriba") as excinfo:
            merge_config_amendments(base, [_contribution("harden", _amendment("usages.docs.scriba.ref", "set", "v2"))])

        assert "required git" in str(excinfo.value)
        assert base.usages is None

        git = _amendment("usages.docs.scriba.git", "set", "https://example/goga")
        ref = _amendment("usages.docs.scriba.ref", "set", "v2")

        for order in ([git, ref], [ref, git]):
            overlay = merge_config_amendments(_authored(), [_contribution("harden", *order)])

            scriba = overlay.config.usages["docs"]["scriba"]

            assert isinstance(scriba, DepConfig)
            assert scriba.git == "https://example/goga"
            assert scriba.ref == "v2"
            assert len(overlay.applied) == 2

    def test_depcfg_value_rules_match_the_loader(self) -> None:
        """Dep leaves carry the loader's own structural rules."""
        base = _authored(usages={"docs": {"scriba": DepConfig(git="https://example/goga")}})
        snapshot = dataclasses.astuple(base)

        for path, value in (
            ("usages.docs.scriba.git", ""),
            ("usages.docs.scriba.ref", ""),
            ("usages.docs.scriba.root", "../.."),
        ):
            with pytest.raises(ValueError, match=rf"tool guard: amendment at '{path}'"):
                merge_config_amendments(base, [_contribution("guard", _amendment(path, "force", value))])

        overlay = merge_config_amendments(
            base,
            [
                _contribution(
                    "guard",
                    _amendment("usages.docs.scriba.root", "force", ""),
                    _amendment("usages.docs.scriba.ref", "set", "v2"),
                ),
            ],
        )

        scriba = overlay.config.usages["docs"]["scriba"]

        assert scriba.root is None
        assert scriba.ref == "v2"
        assert scriba.git == "https://example/goga"
        assert {record.path for record in overlay.applied} == {"usages.docs.scriba.root", "usages.docs.scriba.ref"}
        assert dataclasses.astuple(base) == snapshot

    def test_purity_and_determinism(self) -> None:
        """Same inputs, same overlay; inputs never mutate; branches alias."""
        base = _authored(
            image="ghcr.io/example/app",
            build=BuildConfig(agent="codex", env={"A": "1"}),
            pipeline=PipelineConfig(agent="op"),
            codemanifest=CodemanifestConfig(annotations="@example"),
            topics=TopicsConfig(base_ref=None, publish_commit=None),
        )
        contributions = [
            _contribution(
                "harden",
                _amendment("build.env.LOG_LEVEL", "set", "DEBUG"),
                _amendment("lint.ignore", "set", ["x/"]),
            ),
            _contribution("guard", _amendment("topics.base_ref", "force", "origin/stable")),
        ]
        base_snapshot = dataclasses.astuple(base)
        buffers_snapshot = [list(contribution.amendments) for contribution in contributions]

        first = merge_config_amendments(base, contributions)
        second = merge_config_amendments(base, contributions)

        assert first.applied == second.applied
        assert first.config == second.config
        assert dataclasses.astuple(base) == base_snapshot
        assert [list(contribution.amendments) for contribution in contributions] == buffers_snapshot

        # An unmodified branch passes by reference; an applied list lands
        # as a fresh copy, never an alias of the contribution's list.
        assert first.config.codemanifest is base.codemanifest
        assert first.config.lint is not None
        assert first.config.lint.ignore == ["x/"]
        assert first.config.lint.ignore is not contributions[0].amendments[1].value

    def test_set_on_authored_empty_containers_applies(self) -> None:
        """Empty containers are silence markers; ``False``/``""`` are not."""
        base = _authored(
            image="",
            build=BuildConfig(env={}, review=ReviewConfig(skip=False)),
            lint=LintConfig(ignore=[]),
        )

        overlay = merge_config_amendments(
            base,
            [
                _contribution(
                    "harden",
                    _amendment("lint.ignore", "set", ["x/"]),
                    _amendment("build.env.KEY", "set", "v"),
                    _amendment("commands.report", "set", "on"),
                    _amendment("build.review.skip", "set", True),
                    _amendment("image", "set", "ghcr.io/example/other"),
                ),
            ],
        )

        assert overlay.config.lint is not None
        assert overlay.config.lint.ignore == ["x/"]
        assert overlay.config.build is not None
        assert overlay.config.build.env == {"KEY": "v"}
        assert overlay.config.commands == {"report": "on"}

        applied_paths = {record.path for record in overlay.applied}

        assert applied_paths == {"lint.ignore", "build.env.KEY", "commands.report"}
        assert overlay.config.build.review is not None
        assert overlay.config.build.review.skip is False
        assert overlay.config.image == ""
