"""The data layer of the config amendment overlay — the merge's carriers
and type tree.

Three pure-data entities make up the overlay layer of the zone:
``ToolAmendment`` (the committed contribution of one tool, its amendments
in buffer order), ``AppliedAmendment`` (one applied path — the tool, the
path, and ``set``/``forced``; never a value, so no configuration value
travels into any output), and ``ConfigOverlay`` (the effective
configuration of the run plus the applied records and the summary lines
composed from them). The module also carries the configuration type tree
— the hand-written descriptor the amendment merge resolves paths against,
mirroring the model dataclasses (the unit tests cross-check it against
``dataclasses.fields`` of every model so drift is detectable).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..project import ProjectConfig
from .amendments import PathAmendment


@dataclass(frozen=True, kw_only=True)
class ToolAmendment:
    """The committed contribution of one tool at the amendment checkpoint.

    Args:
        tool: the tool identity assigned by the platform.
        amendments: the committed contributions of the tool, in buffer
            order.
    """

    tool: str
    amendments: list[PathAmendment]


@dataclass(frozen=True, kw_only=True)
class AppliedAmendment:
    """One applied amendment — the winning contribution of one path.

    Carries no value by construction: no configuration value travels
    into any output composed from these records.

    Args:
        tool: the tool identity whose amendment won the path.
        path: the applied dotted leaf path.
        intent: exactly ``set`` or ``forced``.
    """

    tool: str
    path: str
    intent: str


@dataclass(frozen=True, kw_only=True)
class ConfigOverlay:
    """The result of the amendment layer — the effective configuration
    and its applied amendments.

    Args:
        config: the effective (in-memory, per-run) configuration — every
            downstream consumer of the run observes it.
        applied: one record per applied path, in enumeration order.
    """

    config: ProjectConfig
    applied: list[AppliedAmendment]

    @property
    def summary_lines(self) -> list[str]:
        """The composed amendment summary.

        One header line plus one line per applied amendment (the tool,
        the path, ``set`` or ``forced``), in enumeration order; empty
        when nothing applied. No configuration value ever appears in a
        line — the records carry none.

        Returns:
            The summary lines, empty when nothing applied.
        """
        if not self.applied:
            return []

        header = f"config amendments: {len(self.applied)} applied"
        return [header, *(f"- {r.tool} {r.intent} {r.path}" for r in self.applied)]


# The node kinds of the configuration type tree.
_KIND_SCALAR = "scalar"
_KIND_LIST = "list"
_KIND_MAPPING = "mapping"
_KIND_SECTION = "section"
_KIND_FREE_FORM = "free-form"


@dataclass(frozen=True, kw_only=True)
class _FieldNode:
    """One classified field of the configuration type tree.

    Args:
        kind: the node kind — ``scalar``, ``list``, ``mapping``,
            ``section``, or ``free-form``.
        scalar_type: the python type a scalar leaf admits (``str``,
            ``int``, or ``bool``); ``None`` for every other kind.
        section_model: the model name a section node resolves to;
            ``None`` for every other kind.
    """

    kind: str
    scalar_type: type | None = None
    section_model: str | None = None


@dataclass(frozen=True, kw_only=True)
class _ModelNode:
    """One model of the configuration type tree.

    Args:
        fields: the model's fields, each classified into its node kind.
    """

    fields: dict[str, _FieldNode]


def _scalar(scalar_type: type) -> _FieldNode:
    """Build a scalar leaf node admitting ``scalar_type`` values."""
    return _FieldNode(kind=_KIND_SCALAR, scalar_type=scalar_type)


def _list() -> _FieldNode:
    """Build a wholesale list-valued leaf node (``list[str]``)."""
    return _FieldNode(kind=_KIND_LIST)


def _mapping() -> _FieldNode:
    """Build a string-valued mapping node (``<field>.<key>`` entries)."""
    return _FieldNode(kind=_KIND_MAPPING)


def _section(section_model: str) -> _FieldNode:
    """Build a section node resolving to the model named ``section_model``."""
    return _FieldNode(kind=_KIND_SECTION, section_model=section_model)


def _free_form() -> _FieldNode:
    """Build a free-form mapping node (any key, any value, no node check)."""
    return _FieldNode(kind=_KIND_FREE_FORM)


_CONFIG_TREE: dict[str, _ModelNode] = {
    "ProjectConfig": _ModelNode(
        fields={
            "language": _scalar(str),
            "image": _scalar(str),
            "dockerfile": _scalar(str),
            "build": _section("BuildConfig"),
            "pipeline": _section("PipelineConfig"),
            "commands": _free_form(),
            "codemanifest": _section("CodemanifestConfig"),
            "tools": _mapping(),
            "usages": _mapping(),
            "lint": _section("LintConfig"),
            "topics": _section("TopicsConfig"),
        },
    ),
    "BuildConfig": _ModelNode(
        fields={
            "agent": _scalar(str),
            "env": _mapping(),
            "max_iterations": _scalar(int),
            "session_timeout": _scalar(str),
            "idle_timeout": _scalar(str),
            "wait": _scalar(str),
            "prompts_dir": _scalar(str),
            "agents_dir": _scalar(str),
            "proxy": _scalar(str),
            "hosts": _mapping(),
            "review": _section("ReviewConfig"),
        },
    ),
    "ReviewConfig": _ModelNode(
        fields={
            "skip": _scalar(bool),
            "agent": _scalar(str),
            "env": _mapping(),
            "roles": _list(),
            "base_ref": _scalar(str),
            "strategy": _scalar(str),
            "finalize": _scalar(str),
            "additional": _section("AdditionalReviewConfig"),
            "session_timeout": _scalar(str),
            "idle_timeout": _scalar(str),
            "wait": _scalar(str),
        },
    ),
    "AdditionalReviewConfig": _ModelNode(
        fields={
            "agent": _scalar(str),
            "patience": _scalar(int),
            "max_iterations": _scalar(int),
        },
    ),
    "PipelineConfig": _ModelNode(
        fields={
            "agent": _scalar(str),
            "env": _mapping(),
            "proxy": _scalar(str),
            "hosts": _mapping(),
        },
    ),
    "CodemanifestConfig": _ModelNode(
        fields={
            "usages": _mapping(),
            "annotations": _scalar(str),
        },
    ),
    "DepConfig": _ModelNode(
        fields={
            "git": _scalar(str),
            "ref": _scalar(str),
            "root": _scalar(str),
        },
    ),
    "LintConfig": _ModelNode(
        fields={
            "ignore": _list(),
        },
    ),
    "TopicsConfig": _ModelNode(
        fields={
            "base_ref": _scalar(str),
            "publish_commit": _scalar(str),
        },
    ),
}
"""The configuration type tree — the field classification of every model.

A hand-written descriptor mirroring the configuration dataclasses of
``goga/config/project``: per model, per field, the node kind (scalar of
the admitted python type, list-valued leaf, string-valued mapping,
section of the named model, or the free-form ``commands`` mapping), with
arbitrary keys admitted under mapping-typed fields (``usages`` nesting
one mapping level deeper: group -> dep -> the ``DepConfig`` section).
The amendment merge resolves amendment paths against this tree; the unit
tests cross-check it against ``dataclasses.fields`` of every model so
drift is detectable.
"""
