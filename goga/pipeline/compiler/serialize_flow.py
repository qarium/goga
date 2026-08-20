"""The ``serialize_flow`` pure serializer — ``FlowDocument`` to canonical afm YAML.

``serialize_flow`` is the serialization half of the compiler cell: it takes a
fully-built ``FlowDocument`` (with ``FlowStage.fields`` already in canonical key
order — enforced by ``compile_flow``) and renders it into the canonical afm
flow-file format. It performs no file I/O and no reordering.

The non-standard rules are isolated behind marker subclasses and their custom
representers on ``_CanonicalDumper``: flow-style for ``agents``
(``_FlowAgents``) while ``skills`` and ``depends_on`` stay block-style, and
block-literal scalar style for the top-level ``prompt`` (``_BlockLiteralPrompt``)
and for multi-line ``script_before``/``script``/``script_after`` stage fields
(``_BlockLiteralScript``). ``serialize_flow`` wraps any ``agents`` list value in
``_FlowAgents``, any non-``None`` top-level prompt in ``_BlockLiteralPrompt``, and
any multi-line ``script_*`` string value in ``_BlockLiteralScript`` before passing
the document to ``yaml.dump``, so the rules never leak into the rest of the
pipeline. The default ``beautiful_yaml`` parameters render a multi-line string
single-quoted, so the block-literal marker is mandatory for multi-line scripts;
single-line scripts and the boolean ``auto_approve``/``auto_run`` fields stay
plain scalars.
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
    flow-style. Multi-line ``script_before``/``script``/``script_after`` string
    values are wrapped in ``_BlockLiteralScript`` so they serialize in block-literal
    scalar style (the default parameters render a multi-line string single-quoted);
    single-line scripts and the boolean ``auto_approve``/``auto_run`` stay plain
    scalars. ``auto_run`` occupies the canonical field slot immediately after
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
        elif key in ("script_before", "script", "script_after") and isinstance(value, str) and "\n" in value:
            stage_repr[key] = _BlockLiteralScript(value)
        else:
            stage_repr[key] = value

    if stage.depends_on is not None:
        stage_repr["depends_on"] = stage.depends_on

    return stage_repr


def serialize_flow(doc: FlowDocument) -> str:
    """Serialize a ``FlowDocument`` into canonical afm flow-file YAML.

    Top-level keys are emitted in fixed order — ``prompt`` first when not
    ``None`` (block-literal scalar style), then ``root_dir`` when not
    ``None`` (plain scalar), then ``name``, ``description``, ``stages``.
    When ``doc.prompt is None`` the ``prompt`` key is omitted entirely;
    when ``doc.root_dir is None`` the ``root_dir`` key is omitted entirely.
    Each stage is emitted as ``id``, ``name``, then the stage's
    ``fields`` verbatim (preserving their canonical order), then ``depends_on``
    only when it is not ``None``. ``agents`` lists serialize in flow-style;
    ``skills`` and ``depends_on`` serialize in block-style. Multi-line
    ``script_before``/``script``/``script_after`` string values serialize in
    block-literal scalar style; single-line scripts and the boolean
    ``auto_approve``/``auto_run`` serialize as plain bool scalars (the canonical
    field order slots ``auto_run`` immediately after ``auto_approve``; a stage
    without a manual-effective trigger serializes without the ``auto_run`` key —
    byte-identical output for trigger-free pipelines — and ``auto_run``
    serializes only as ``auto_run: false``). The output ends with exactly one
    trailing newline.

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
