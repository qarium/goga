"""The ``serialize_flow`` pure serializer — ``FlowDocument`` to canonical afm YAML.

``serialize_flow`` is the serialization half of the compiler cell: it takes a
fully-built ``FlowDocument`` (with ``FlowStage.fields`` already in canonical key
order — enforced by ``compile_flow``) and renders it into the canonical afm
flow-file format. It performs no file I/O and no reordering. The top-level keys
are emitted in fixed order — ``prompt`` (when present), ``root_dir`` (when
supplied), ``name``, ``description``, ``memory`` (when memory participates),
``stages``; the memory block carries the fixed key order ``path``, ``mode``,
``memory_use``, ``max_rules``, ``commit`` with every present value a plain
scalar and a ``None`` field omitted entirely, while the stage memory keys
(``reflect`` mapping, ``memory_use`` bool) ride the regular ``fields``
emission — a block-style mapping and a plain bool scalar respectively.

The non-standard rules are isolated behind marker subclasses and their custom
representers on ``_CanonicalDumper``: flow-style for ``agents``
(``_FlowAgents``) while ``skills`` and ``depends_on`` stay block-style, and
block-literal scalar style for the top-level ``prompt`` (``_BlockLiteralPrompt``)
and for multi-line ``script_before``/``script``/``script_after``/``script_timeout``
stage fields and multi-line ``buttons`` values (``_BlockLiteralScript``).
``serialize_flow`` wraps any ``agents``
list value in ``_FlowAgents``, any non-``None`` top-level prompt in
``_BlockLiteralPrompt``, any multi-line ``script_*`` string value in
``_BlockLiteralScript``, and any multi-line ``buttons`` map value in
``_BlockLiteralScript`` before passing
the document to ``yaml.dump``, so the rules never leak into the rest of the
pipeline. The default ``beautiful_yaml`` parameters render a multi-line string
single-quoted, so the block-literal marker is mandatory for multi-line scripts
and multi-line button texts;
single-line scripts, single-line button values, and the boolean
``auto_approve``/``auto_run`` fields stay plain scalars.
"""

from __future__ import annotations

import logging

import yaml

from .flow_document import FlowDocument
from .flow_stage import FlowStage

logger = logging.getLogger(__name__)


class _FlowAgents(list):
    """Marker class — list that must serialize in flow-style."""

    pass


def _represent_flow_agents(dumper: yaml.Dumper, data: _FlowAgents) -> yaml.Node:
    """Force flow-style sequence output for an ``agents`` value."""
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


class _BlockLiteralPrompt(str):
    """Marker class — string that must serialize in block-literal scalar style."""

    pass


def _represent_block_literal_prompt(dumper: yaml.Dumper, data: _BlockLiteralPrompt) -> yaml.Node:
    """Force block-literal scalar output for the top-level ``prompt`` value."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


class _BlockLiteralScript(str):
    """Marker class — string that must serialize in block-literal scalar style."""

    pass


def _represent_block_literal_script(dumper: yaml.Dumper, data: _BlockLiteralScript) -> yaml.Node:
    """Force block-literal scalar output for a multi-line ``script_*`` value."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


class _CanonicalDumper(yaml.SafeDumper):
    """``SafeDumper`` subclass carrying the marker-class representers."""

    pass


_CanonicalDumper.add_representer(_FlowAgents, _represent_flow_agents)
_CanonicalDumper.add_representer(_BlockLiteralPrompt, _represent_block_literal_prompt)
_CanonicalDumper.add_representer(_BlockLiteralScript, _represent_block_literal_script)


def _build_stage_repr(stage: FlowStage) -> dict[str, object]:
    """Build the per-stage dict in fixed order (id, name, canonical fields, depends_on).

    ``agents`` list values are wrapped in ``_FlowAgents`` so they serialize in
    flow-style. Multi-line ``script_before``/``script``/``script_after``/
    ``script_timeout`` string values are wrapped in ``_BlockLiteralScript`` so
    they serialize in block-literal
    scalar style (the default parameters render a multi-line string single-quoted);
    single-line scripts and the boolean ``auto_approve``/``auto_run`` stay plain
    scalars. A ``buttons`` mapping is rebuilt entry by entry — single-line values
    stay plain scalars (quoted as needed), multi-line values are wrapped in
    ``_BlockLiteralScript`` — preserving the map's insertion order (never sorted);
    the mapping itself serializes as a regular block-style mapping.
    ``auto_run`` occupies the canonical field slot immediately after
    ``auto_approve`` and is present only when the stage's effective trigger is
    ``manual`` — the value is always ``False`` (``auto_run: false``; the
    serializer itself enforces neither rule, it emits ``fields`` verbatim).
    ``depends_on`` is emitted only when not ``None`` (distinguishing absent from
    explicit empty).

    Args:
        stage: One ``FlowStage`` of the document.

    Returns:
        The ordered mapping to feed to ``yaml.dump``.
    """
    stage_repr: dict[str, object] = {"id": stage.id, "name": stage.name}

    for key, value in stage.fields.items():
        if key == "agents" and isinstance(value, list):
            stage_repr[key] = _FlowAgents(value)
        elif (
            key in ("script_before", "script", "script_after", "script_timeout")
            and isinstance(value, str)
            and "\n" in value
        ):
            stage_repr[key] = _BlockLiteralScript(value)
        elif key == "buttons" and isinstance(value, dict):
            stage_repr[key] = {
                note: (_BlockLiteralScript(text) if isinstance(text, str) and "\n" in text else text)
                for note, text in value.items()
            }
        else:
            stage_repr[key] = value

    if stage.depends_on is not None:
        stage_repr["depends_on"] = stage.depends_on

    return stage_repr


def serialize_flow(doc: FlowDocument) -> str:
    """Serialize a ``FlowDocument`` into canonical afm flow-file YAML.

    Top-level keys are emitted in fixed order — ``prompt`` first when not
    ``None`` (block-literal scalar style), then ``root_dir`` when not
    ``None`` (plain scalar), then ``name``, ``description``, ``memory`` (when
    present), ``stages``.
    When ``doc.prompt is None`` the ``prompt`` key is omitted entirely;
    when ``doc.root_dir is None`` the ``root_dir`` key is omitted entirely.
    When ``doc.memory is not None`` the memory block is emitted after
    ``description`` and before ``stages`` with the fixed key order ``path``,
    ``mode``, ``memory_use``, ``max_rules``, ``commit`` — every present value
    a plain scalar, a ``None`` field omitted entirely (no key in the output);
    when ``doc.memory is None`` the block is omitted entirely —
    byte-identical output for memory-free workflows.
    Each stage is emitted as ``id``, ``name``, then the stage's
    ``fields`` verbatim (preserving their canonical order), then ``depends_on``
    only when it is not ``None``. ``agents`` lists serialize in flow-style;
    ``skills``, ``depends_on``, and the ``buttons`` mapping serialize in
    block-style. Multi-line ``script_before``/``script``/``script_after``/
    ``script_timeout`` string values serialize in block-literal scalar style;
    single-line scripts and the boolean ``auto_approve``/``auto_run`` serialize
    as plain bool scalars (the canonical field order slots ``auto_run``
    immediately after ``auto_approve``; a stage
    without a manual-effective trigger serializes without the ``auto_run`` key —
    byte-identical output for trigger-free pipelines — and ``auto_run``
    serializes only as ``auto_run: false``). ``buttons`` values serialize as
    plain scalars when single-line (quoted as needed) and in block-literal
    scalar style when multi-line, preserving the map's insertion order; a stage
    without a ``buttons`` key serializes without it. The stage memory keys ride
    the same ``fields`` passthrough verbatim: ``reflect`` serializes as a
    block-style mapping of plain scalars (``file``, ``mode`` — the nested keys
    at the second indent level under ``stages``) and ``memory_use`` as a plain
    bool scalar. The output ends with exactly
    one trailing newline.

    The serializer does not reorder, validate, or otherwise transform the input —
    a document with out-of-order ``fields`` produces out-of-order output.

    Args:
        doc: The document to serialize. Each ``FlowStage.fields`` must already be
            in canonical key order and ``depends_on`` must be ``None`` or a list
            of strings. ``prompt`` and ``root_dir`` must be ``None`` or a ``str``.

    Returns:
        The canonical afm flow-file content as a string.
    """
    top: dict[str, object] = {}

    if doc.prompt is not None:
        top["prompt"] = _BlockLiteralPrompt(doc.prompt)
    if doc.root_dir is not None:
        top["root_dir"] = doc.root_dir

    top["name"] = doc.name
    top["description"] = doc.description

    if doc.memory is not None:
        top["memory"] = {
            key: value
            for key, value in (
                ("path", doc.memory.path),
                ("mode", doc.memory.mode),
                ("memory_use", doc.memory.memory_use),
                ("max_rules", doc.memory.max_rules),
                ("commit", doc.memory.commit),
            )
            if value is not None
        }

    top["stages"] = [_build_stage_repr(stage) for stage in doc.stages]

    text = yaml.dump(
        top,
        Dumper=_CanonicalDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        indent=2,
    )

    # Normalize to exactly one trailing newline.
    if not text.endswith("\n"):
        text += "\n"
    elif text.endswith("\n\n"):
        text = text.rstrip("\n") + "\n"

    return text
