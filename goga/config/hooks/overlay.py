"""The data layer of the config amendment overlay — the merge, its
carriers, and the type tree.

Three pure-data entities make up the overlay layer of the zone:
``ToolAmendment`` (the committed contribution of one tool, its amendments
in buffer order), ``AppliedAmendment`` (one applied path — the tool, the
path, and ``set``/``forced``; never a value, so no configuration value
travels into any output), and ``ConfigOverlay`` (the effective
configuration of the run plus the applied records and the summary lines
composed from them). The module also carries the configuration type tree
— the hand-written descriptor the amendment merge resolves paths against,
mirroring the model dataclasses (the unit tests cross-check it against
``dataclasses.fields`` of every model so drift is detectable) — and
``merge_config_amendments`` itself: the deterministic, pure composition
of the committed contributions over the authored base into the effective
configuration of the run.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import PurePath
from typing import Any, NoReturn

from ..project import (
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


_CONFIG_TREE: dict[str, dict[str, _FieldNode]] = {
    "ProjectConfig": {
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
    "BuildConfig": {
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
    "ReviewConfig": {
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
        "max_iterations": _scalar(int),
    },
    "AdditionalReviewConfig": {
        "agent": _scalar(str),
        "patience": _scalar(int),
        "max_iterations": _scalar(int),
    },
    "PipelineConfig": {
        "agent": _scalar(str),
        "env": _mapping(),
        "proxy": _scalar(str),
        "hosts": _mapping(),
    },
    "CodemanifestConfig": {
        "usages": _mapping(),
        "annotations": _scalar(str),
    },
    "DepConfig": {
        "git": _scalar(str),
        "ref": _scalar(str),
        "root": _scalar(str),
    },
    "LintConfig": {
        "ignore": _list(),
    },
    "TopicsConfig": {
        "base_ref": _scalar(str),
        "publish_commit": _scalar(str),
    },
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
drift is detectable. Key shape stays the loader's own rule — a
``usages`` group/dep key must be a plain name (the merge checks the same
constraint the loader enforces, so no unsafe path segment composes).
"""


# The hop kinds of a resolved amendment path: a dataclass field holding
# a section instance, a dataclass field holding a mapping, an arbitrary
# key of a mapping, and the terminal assignment target.
_HOP_SECTION = "section"
_HOP_MAP = "map"
_HOP_KEY = "key"
_HOP_LEAF = "leaf"

# Where a leaf hop lands: an attribute of the holding section instance
# or an entry of the holding mapping.
_LAND_ATTRIBUTE = "attribute"
_LAND_ENTRY = "entry"

_ROOT_MODEL = "ProjectConfig"
"""The model every amendment path roots at."""

_DEP_MODEL = "DepConfig"
"""The section model under the two usages mapping levels."""

_USAGES_TAIL = 3
"""The segment count after the root ``usages`` field: the group key, the
dep key, and the dep leaf."""


@dataclass(frozen=True, kw_only=True)
class _Hop:
    """One resolved hop of an amendment path.

    Args:
        kind: ``section``, ``map``, ``key``, or ``leaf``.
        name: the field name or mapping key the hop addresses.
        model: the target model of a ``section`` hop.
        leaf: the node classification of a ``leaf`` hop.
        landing: a ``leaf`` hop's landing — ``attribute`` or ``entry``.
    """

    kind: str
    name: str
    model: str | None = None
    leaf: _FieldNode | None = None
    landing: str = ""


@dataclass(frozen=True, kw_only=True)
class _Plan:
    """One validated amendment staged for resolution.

    Args:
        contribution_index: the enumeration position of the contributing
            tool.
        buffer_index: the buffer position of the amendment.
        tool: the contributing tool's identity.
        path: the validated dotted leaf path.
        intent: the buffered intent — ``set`` or ``force``.
        hops: the resolved route against the type tree.
        stored: the storable value (a fresh copy for list values).
    """

    contribution_index: int
    buffer_index: int
    tool: str
    path: str
    intent: str
    hops: list[_Hop]
    stored: object


@dataclass(frozen=True, kw_only=True)
class _Walk:
    """The resolution state of one amendment path.

    Args:
        tool: the contributing tool — every failure names it.
        path: the dotted path as buffered.
        segments: the path's dot-separated segments.
    """

    tool: str
    path: str
    segments: list[str]

    def fail(self, detail: str) -> NoReturn:
        """Raise this walk's structural failure, naming the tool.

        Args:
            detail: the malformedness classification.

        Raises:
            ValueError: Always — the pinned failure format.
        """
        _fail(self.tool, self.path, detail)

    def prefix(self, upto: int) -> str:
        """Join the first ``upto`` segments — the addressed node's name.

        Args:
            upto: the segment count to join.

        Returns:
            The dot-joined prefix.
        """
        return ".".join(self.segments[:upto])


_SECTION_DEFAULTS: dict[str, Callable[[], Any]] = {
    "BuildConfig": BuildConfig,
    "ReviewConfig": ReviewConfig,
    "AdditionalReviewConfig": AdditionalReviewConfig,
    "PipelineConfig": PipelineConfig,
    "CodemanifestConfig": CodemanifestConfig,
    "TopicsConfig": lambda: TopicsConfig(base_ref=None, publish_commit=None),
    "LintConfig": lambda: LintConfig(ignore=[]),
}
"""The materialization default instances — one factory per section model.

Every model is ``kw_only`` with defaults except the pinned exclusions:
``TopicsConfig`` and ``LintConfig`` carry required fields, so their
factories pass the unset shape explicitly. ``DepConfig`` is absent — a
dep materializes at its mapping key (``DepConfig(git=None, ...)``),
never as a section hop."""

_ABSENT = object()
"""The silence sentinel — an absent authored branch or key."""


def _fail(tool: str, path: object, detail: str) -> NoReturn:
    """Raise the structural failure of one amendment, naming the tool.

    Args:
        tool: the identity of the contributing tool.
        path: the malformed amendment path, verbatim — the buffer stores
            hook input as given, so the path may not even be a string.
        detail: the malformedness classification.

    Raises:
        ValueError: Always — the pinned failure format.
    """
    raise ValueError(f"tool {tool}: amendment at {path!r} {detail}")


def _checked_value(walk: _Walk, node: _FieldNode, value: object) -> object:
    """Type-check one amendment value against its leaf node.

    Args:
        walk: the resolution state (failure naming).
        node: the leaf's classification — a scalar of its admitted
            python type, a list-valued leaf, or a mapping entry (``str``).
        value: the buffered value.

    Returns:
        The storable value — a list-valued leaf returns a fresh list
        copy, never an alias of the contribution's list.

    Raises:
        ValueError: The value does not match the node.
    """
    if node.kind == _KIND_LIST:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            walk.fail("carries a value of the wrong type: a list of strings is required")
        return list(value)

    expected = str if node.kind == _KIND_MAPPING else node.scalar_type
    if expected is bool:
        admitted = isinstance(value, bool)
    elif expected is int:
        admitted = isinstance(value, int) and not isinstance(value, bool)
    else:
        admitted = isinstance(value, str)
    if not admitted:
        walk.fail(f"carries a value of the wrong type: expected {expected.__name__}, got {type(value).__name__}")
    return value


def _checked_dep_value(walk: _Walk, field: str, value: object) -> object:
    """Type-check one ``usages.<group>.<dep>`` leaf against the loader's rules.

    The dep leaves additionally carry the loader's own structural rules:
    ``git`` and ``ref`` must be non-empty strings (stored stripped, as
    the loader stores them), ``root`` a string that is a safe relative
    subpath. A blank ``root`` is NOT an error — it composes as ``None``,
    and a safe ``root`` composes in its canonical forward-slash form
    (the ``_parse_depcfg_root`` normalization mirrored; no filesystem is
    touched).

    Args:
        walk: the resolution state (failure naming).
        field: the dep leaf's field name — ``git``, ``ref``, or ``root``.
        value: the buffered value.

    Returns:
        The storable value — a blank ``root`` as ``None``.

    Raises:
        ValueError: The value breaks a dep structural rule.
    """
    if field in ("git", "ref"):
        if not isinstance(value, str) or not value.strip():
            walk.fail(f"carries a value of the wrong type: usages dep {field!r} must be a non-empty string")
        return value.strip()

    if not isinstance(value, str):
        walk.fail("carries a value of the wrong type: usages dep 'root' must be a string")
    normalized = value.strip().replace("\\", "/")
    if normalized.strip("/") == "":
        return None

    as_path = PurePath(normalized)
    if as_path.is_absolute() or as_path.anchor != "" or ".." in as_path.parts:
        walk.fail(
            "carries a value of the wrong type: usages dep 'root' must be "
            "a safe relative subpath (no '..', no absolute)",
        )
    return "/".join(segment for segment in normalized.split("/") if segment)


def _resolve(tool: str, amendment: PathAmendment) -> tuple[list[_Hop], object]:
    """Resolve one amendment path into its hop route and storable value.

    Walks the segments against the configuration type tree: every
    intermediate must name a field of the model at hand, the path must
    end at a leaf, and the value must match the leaf's node — otherwise
    the amendment is structurally malformed and the failure names the
    tool and the malformedness.

    Args:
        tool: the contributing tool (failure naming).
        amendment: the buffered entry — stored verbatim by the buffer,
            so the path may not even be a string.

    Returns:
        The hop route and the storable value.

    Raises:
        ValueError: The path is unknown, addresses a non-leaf node, or
            the value is of the wrong type for the node.
    """
    path = amendment.path
    if not isinstance(path, str):
        _fail(tool, path, "names an unknown path: the path is not a string")

    walk = _Walk(tool=tool, path=path, segments=path.split("."))
    hops: list[_Hop] = []
    model_name = _ROOT_MODEL
    index = 0
    while True:
        segment = walk.segments[index]
        node = _CONFIG_TREE[model_name].get(segment)
        if node is None:
            walk.fail(f"names an unknown path: {segment!r} is not a field of {model_name}")

        if node.kind != _KIND_SECTION:
            if model_name == _ROOT_MODEL and segment == "usages":
                return _resolve_usages_leaf(walk, index, amendment.value, hops)
            if node.kind == _KIND_FREE_FORM:
                return _resolve_free_form_leaf(walk, index, node, amendment.value, hops)
            return _resolve_leaf(walk, index, node, amendment.value, hops)

        if index == len(walk.segments) - 1:
            walk.fail("addresses a non-leaf node: a whole section, not one of its leaves")
        hops.append(_Hop(kind=_HOP_SECTION, name=segment, model=node.section_model))
        model_name = node.section_model
        index += 1


def _resolve_leaf(
    walk: _Walk,
    index: int,
    node: _FieldNode,
    value: object,
    hops: list[_Hop],
) -> tuple[list[_Hop], object]:
    """Resolve the final field of a path — a leaf or a plain mapping.

    Args:
        walk: the resolution state (failure naming).
        index: the position of the final field's segment.
        node: the field's node classification.
        value: the buffered value.
        hops: the section hops walked so far.

    Returns:
        The hop route and the storable value.

    Raises:
        ValueError: The path addresses a non-leaf node or continues
            below a leaf.
    """
    remaining = len(walk.segments) - index - 1

    if node.kind in (_KIND_SCALAR, _KIND_LIST):
        if remaining:
            walk.fail(f"names an unknown path: it continues below the leaf {walk.prefix(index + 1)!r}")
        hops.append(_Hop(kind=_HOP_LEAF, name=walk.segments[index], leaf=node, landing=_LAND_ATTRIBUTE))
        return hops, _checked_value(walk, node, value)

    return _resolve_mapping_leaf(walk, index, node, value, hops)


def _resolve_free_form_leaf(
    walk: _Walk,
    index: int,
    node: _FieldNode,
    value: object,
    hops: list[_Hop],
) -> tuple[list[_Hop], object]:
    """Resolve one ``commands.<key>`` entry — the free-form leaf.

    Any key is admitted and any value accepted without a node check;
    a list value still lands as a fresh copy, never an alias.

    Args:
        walk: the resolution state (failure naming).
        index: the position of the ``commands`` segment.
        node: the free-form node classification.
        value: the buffered value.
        hops: the hops walked so far.

    Returns:
        The hop route and the storable value.

    Raises:
        ValueError: The path addresses the whole mapping or continues
            below an entry.
    """
    remaining = len(walk.segments) - index - 1
    if remaining == 0:
        walk.fail("addresses a non-leaf node: the whole free-form mapping, not one of its entries")
    if remaining > 1:
        walk.fail(f"names an unknown path: it continues below the free-form entry {walk.prefix(index + 2)!r}")

    hops.append(_Hop(kind=_HOP_MAP, name=walk.segments[index]))
    hops.append(_Hop(kind=_HOP_LEAF, name=walk.segments[-1], leaf=node, landing=_LAND_ENTRY))
    return hops, (list(value) if isinstance(value, list) else value)


def _resolve_mapping_leaf(
    walk: _Walk,
    index: int,
    node: _FieldNode,
    value: object,
    hops: list[_Hop],
) -> tuple[list[_Hop], object]:
    """Resolve one plain mapping-valued field — the ``<field>.<key>`` entry.

    Args:
        walk: the resolution state (failure naming).
        index: the position of the mapping field's segment.
        node: the field's node classification.
        value: the buffered value.
        hops: the hops walked so far.

    Returns:
        The hop route and the storable value.

    Raises:
        ValueError: The path addresses a whole mapping or continues
            below an entry.
    """
    remaining = len(walk.segments) - index - 1
    if remaining == 0:
        walk.fail(f"addresses a non-leaf node: {walk.prefix(index + 1)!r} is a mapping, not a leaf")
    if remaining > 1:
        walk.fail(f"names an unknown path: it continues below the mapping entry {walk.prefix(index + 2)!r}")

    hops.append(_Hop(kind=_HOP_MAP, name=walk.segments[index]))
    hops.append(_Hop(kind=_HOP_LEAF, name=walk.segments[-1], leaf=node, landing=_LAND_ENTRY))
    return hops, _checked_value(walk, node, value)


def _checked_usages_segment(walk: _Walk, segment: str, kind: str) -> None:
    """Check one ``usages`` group/dep path segment against the loader's rule.

    The loader rejects unsafe dynamic keys at the config boundary because
    ``sync``/``status`` consume them verbatim as filesystem path segments
    (``.goga/usages/<group>/<dep>/``) — a name that is empty, a traversal
    segment (``.``/``..``), or carries a path separator could direct a
    deploy outside the target root. The merge admits the same key shape
    the loader does, so the effective configuration is one the authored
    load itself would have accepted.

    Args:
        walk: the resolution state (failure naming).
        segment: the group or dep segment as split off the dotted path.
        kind: ``group`` or ``dep`` — the segment's position.

    Raises:
        ValueError: The segment is not a plain name.
    """
    if segment == "" or segment in (".", "..") or "/" in segment or "\\" in segment:
        walk.fail(
            f"names an unsafe path: the usages {kind} {segment!r} must be "
            "a plain name without '/' or '..'",
        )


def _resolve_usages_leaf(
    walk: _Walk,
    index: int,
    value: object,
    hops: list[_Hop],
) -> tuple[list[_Hop], object]:
    """Resolve one ``usages.<group>.<dep>.<field>`` leaf — the nested map.

    The root ``usages`` nests one mapping level deeper than every other
    mapping (group -> dep -> the ``DepConfig`` section), so exactly three
    segments follow the field; the group/dep segments carry the loader's
    own key rules and the dep leaf the loader's own value rules.

    Args:
        walk: the resolution state (failure naming).
        index: the position of the ``usages`` segment.
        value: the buffered value.
        hops: the hops walked so far.

    Returns:
        The hop route and the storable value.

    Raises:
        ValueError: The path stops above a dep leaf, continues below
            one, names no ``DepConfig`` field, or addresses an unsafe
            group/dep name.
    """
    remaining = len(walk.segments) - index - 1
    if remaining < _USAGES_TAIL:
        walk.fail("addresses a non-leaf node: a usages branch without the group.dep.leaf descent")
    if remaining > _USAGES_TAIL:
        walk.fail(f"names an unknown path: it continues below the leaf {walk.prefix(index + _USAGES_TAIL + 1)!r}")

    _checked_usages_segment(walk, walk.segments[index + 1], "group")
    _checked_usages_segment(walk, walk.segments[index + 2], "dep")

    dep_field = walk.segments[index + _USAGES_TAIL]
    dep_node = _CONFIG_TREE[_DEP_MODEL].get(dep_field)
    if dep_node is None or dep_node.kind != _KIND_SCALAR:
        walk.fail(f"names an unknown path: {dep_field!r} is not a field of {_DEP_MODEL}")

    hops.append(_Hop(kind=_HOP_MAP, name=walk.segments[index]))
    hops.append(_Hop(kind=_HOP_KEY, name=walk.segments[index + 1]))
    hops.append(_Hop(kind=_HOP_KEY, name=walk.segments[index + 2]))
    hops.append(_Hop(kind=_HOP_LEAF, name=dep_field, leaf=dep_node, landing=_LAND_ATTRIBUTE))
    return hops, _checked_dep_value(walk, dep_field, value)


def _authored_state(base: ProjectConfig, hops: list[_Hop]) -> object:
    """Walk the hops to the container holding the leaf.

    Args:
        base: the authored configuration.
        hops: the resolved route of an amendment.

    Returns:
        The holding section instance or mapping, or ``_ABSENT`` when any
        intermediate branch of the authored configuration is absent.
    """
    container: object = base
    for hop in hops[:-1]:
        container = container.get(hop.name) if hop.kind == _HOP_KEY else getattr(container, hop.name, None)
        if container is None:
            return _ABSENT
    return container


def _is_silent(base: ProjectConfig, hops: list[_Hop]) -> bool:
    """Report authored silence at the leaf — measured against ``base`` only.

    Silence is the loaded model's absence: a ``None`` scalar, a ``None``
    or empty list, an absent mapping entry (a ``None``/empty container
    carries no entries), or any absent intermediate branch. Authored
    emptiness that is not an absence marker — ``False``, ``""``, a
    present entry value — is authored, not silent.

    Args:
        base: the authored configuration.
        hops: the resolved route of an amendment.

    Returns:
        Whether the authored configuration is silent at the leaf.
    """
    container = _authored_state(base, hops)
    if container is _ABSENT:
        return True

    leaf = hops[-1]
    if leaf.landing == _LAND_ENTRY:
        return leaf.name not in container

    value = getattr(container, leaf.name)
    if leaf.leaf.kind == _KIND_LIST:
        return value is None or not value
    return value is None


def _materialize(next_hop: _Hop) -> object:
    """Build the absent node a key hop descends into.

    Args:
        next_hop: the hop after the absent key — a deeper key level
            materializes a fresh mapping, a dep leaf the unset
            ``DepConfig``.

    Returns:
        The materialized node.
    """
    if next_hop.kind == _HOP_KEY:
        return {}
    return DepConfig(git=None, ref=None, root=None)


def _write(container: object, hops: list[_Hop], index: int, stored: object) -> object:
    """Apply one winning amendment along its route, bottom-up.

    The walk never mutates its inputs: affected frozen sections are
    reconstructed with :func:`dataclasses.replace`, modified mappings
    are fresh dicts, missing intermediates materialize as the section
    default instances (or fresh mappings / the unset ``DepConfig``), and
    every branch off the route passes by reference.

    Args:
        container: the node at ``index`` — a section instance, or a
            mapping this walk already owns.
        hops: the resolved route of the amendment.
        index: the hop to apply now.
        stored: the storable value computed at validation.

    Returns:
        The rebuilt node — the new root when ``index`` is ``0``.
    """
    hop = hops[index]
    if index == len(hops) - 1:
        if hop.landing == _LAND_ATTRIBUTE:
            return replace(container, **{hop.name: stored})

        entries = dict(container)
        entries[hop.name] = stored
        return entries

    if hop.kind == _HOP_KEY:
        child = container.get(hop.name)
        if child is None:
            child = _materialize(hops[index + 1])
        elif isinstance(child, dict):
            child = dict(child)
        container[hop.name] = _write(child, hops, index + 1, stored)
        return container

    child = getattr(container, hop.name)
    if hop.kind == _HOP_SECTION:
        child = _SECTION_DEFAULTS[hop.model]() if child is None else child
    else:  # _HOP_MAP — descend through a private copy of the mapping.
        child = {} if child is None else dict(child)
    return replace(container, **{hop.name: _write(child, hops, index + 1, stored)})


def _postcheck_materialized_deps(base: ProjectConfig, effective: ProjectConfig, winners: list[_Plan]) -> None:
    """Reject a materialized dep without its required ``git`` — the final pass.

    Evaluated once over the finished composition, so the buffer order of
    the amendments never matters; the failure names the first applied
    amendment under the offending dep branch and its tool.

    Args:
        base: the authored configuration — the materialization baseline.
        effective: the finished composition.
        winners: the applied winners, in enumeration order.

    Raises:
        ValueError: A dep the composition materialized whose ``git`` is
            still ``None``.
    """
    authored = base.usages or {}
    for group, deps in (effective.usages or {}).items():
        for dep, dep_config in deps.items():
            if (group in authored and dep in authored[group]) or dep_config.git is not None:
                continue

            branch = f"usages.{group}.{dep}."
            first = next((plan for plan in winners if plan.path.startswith(branch)), None)
            if first is None:
                continue
            raise ValueError(
                f"tool {first.tool}: amendment at {first.path!r} materializes "
                f"usages.{group}.{dep} without its required git"
            )


def merge_config_amendments(base: ProjectConfig, contributions: list[ToolAmendment]) -> ConfigOverlay:
    """Compose the effective configuration from the authored base and the contributions.

    The deterministic amendment merge:

    1. VALIDATE — every amendment of every contribution, in buffer
       order, resolves against the configuration type tree: an unknown
       path, a non-leaf address, or a value of the wrong type at the
       node (the ``usages`` group/dep keys and the
       ``usages.<group>.<dep>`` leaves additionally carry the loader's
       own rules — plain group/dep names, non-empty ``git``/``ref``,
       path-safe ``root``) is a structural failure of the contributing
       tool, raised naming the tool; no amendment of the run applies.
    2. RESOLVE — authored silence measured against ``base`` only (a
       ``None`` scalar, a ``None``/empty list, an absent mapping entry,
       any absent intermediate branch); a ``set`` on a non-silent path
       is dropped silently; per remaining path the LAST ``force`` beats
       any ``set`` regardless of order, and among equal intent the later
       tool in enumeration order wins.
    3. COMPOSE — each winner, in enumeration order, applies to a
       working copy of ``base``: missing intermediates materialize (the
       section default instances, fresh mappings, the unset
       ``DepConfig``), list-valued leaves replace wholesale as fresh
       copies, mapping entries set individually, affected frozen
       instances reconstruct bottom-up, and a blank dep ``root``
       composes as ``None``. A final pass over the finished composition
       then rejects every materialized dep whose ``git`` is still
       missing — order-independent, evaluated once.
    4. COLLECT — one :class:`AppliedAmendment` per applied path, ordered
       by the winner's enumeration position.
    5. RETURN — the :class:`ConfigOverlay`.

    Empty ``contributions`` is the passthrough — the passed
    configuration object itself, empty ``applied``, empty summary lines.
    The merge is pure and deterministic: ``base``, the contributions,
    and their collections are never mutated, unmodified branches pass by
    reference, and the same inputs always give the same overlay. No
    filesystem access, no semantic validation of well-formed values.

    Args:
        base: the authored loaded configuration.
        contributions: the committed contributions, in enumeration
            order.

    Returns:
        The :class:`ConfigOverlay` — the effective configuration and
        its applied amendments.

    Raises:
        ValueError: A structurally malformed contribution (naming the
            tool and the malformedness) or a materialized dep without
            its required ``git`` — raised before anything applies.
    """
    # Step 1 — the passthrough: the passed object itself, zero rebuild.
    if not contributions:
        return ConfigOverlay(config=base, applied=[])

    # Step 2 — VALIDATE: every amendment of every contribution, buffer
    # order, before anything applies.
    plans: list[_Plan] = []
    for contribution_index, contribution in enumerate(contributions):
        for buffer_index, amendment in enumerate(contribution.amendments):
            hops, stored = _resolve(contribution.tool, amendment)
            plans.append(
                _Plan(
                    contribution_index=contribution_index,
                    buffer_index=buffer_index,
                    tool=contribution.tool,
                    path=amendment.path,
                    intent=amendment.intent,
                    hops=hops,
                    stored=stored,
                ),
            )

    # Step 3 — RESOLVE: silence against ``base`` only; a set on a
    # non-silent path drops silently; per path the last force beats any
    # set, else the last set (the later tool within equal intent).
    candidates: dict[str, list[_Plan]] = {}
    for plan in plans:
        if plan.intent == "force" or _is_silent(base, plan.hops):
            candidates.setdefault(plan.path, []).append(plan)

    winners = [
        ([plan for plan in per_path if plan.intent == "force"] or per_path)[-1]
        for per_path in candidates.values()
    ]
    winners.sort(key=lambda plan: (plan.contribution_index, plan.buffer_index))

    # Step 4 — COMPOSE: apply each winner in enumeration order, then the
    # final pass over the finished composition.
    effective: ProjectConfig = base
    for plan in winners:
        effective = _write(effective, plan.hops, 0, plan.stored)
    _postcheck_materialized_deps(base, effective, winners)

    # Steps 5-6 — COLLECT and RETURN: one record per applied path, in
    # enumeration order.
    return ConfigOverlay(
        config=effective,
        applied=[
            AppliedAmendment(tool=plan.tool, path=plan.path, intent="forced" if plan.intent == "force" else "set")
            for plan in winners
        ],
    )
