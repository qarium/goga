"""The ``serialize_flow`` pure serializer — ``FlowDocument`` to canonical afm YAML."""

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
    """Force flow-style sequence output for an ``agents`` value.

    Args:
        dumper: The YAML dumper requesting the representation.
        data: The ``_FlowAgents`` list being represented.

    Returns:
        The sequence node rendered in flow-style.
    """
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


class _BlockLiteralPrompt(str):
    """Marker class — string that must serialize in block-literal scalar style."""

    pass


def _represent_block_literal_prompt(dumper: yaml.Dumper, data: _BlockLiteralPrompt) -> yaml.Node:
    """Force block-literal scalar output for the top-level ``prompt`` value.

    Args:
        dumper: The YAML dumper requesting the representation.
        data: The ``_BlockLiteralPrompt`` string being represented.

    Returns:
        The scalar node rendered in block-literal style.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


class _BlockLiteralScript(str):
    """Marker class — string that must serialize in block-literal scalar style."""

    pass


def _represent_block_literal_script(dumper: yaml.Dumper, data: _BlockLiteralScript) -> yaml.Node:
    """Force block-literal scalar output for a multi-line ``script_*`` value.

    Args:
        dumper: The YAML dumper requesting the representation.
        data: The ``_BlockLiteralScript`` string being represented.

    Returns:
        The scalar node rendered in block-literal style.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


class _CanonicalDumper(yaml.SafeDumper):
    """``SafeDumper`` subclass carrying the marker-class representers."""

    pass


_CanonicalDumper.add_representer(_FlowAgents, _represent_flow_agents)
_CanonicalDumper.add_representer(_BlockLiteralPrompt, _represent_block_literal_prompt)
_CanonicalDumper.add_representer(_BlockLiteralScript, _represent_block_literal_script)


def _build_stage_repr(stage: FlowStage) -> dict[str, object]:
    """Build the per-stage dict in fixed order (id, name, canonical fields, depends_on).

    Args:
        stage: One ``FlowStage`` of the document.

    Returns:
        The ordered mapping to feed to ``yaml.dump``: ``id``, ``name``,
        ``fields`` verbatim (``agents`` wrapped in ``_FlowAgents``; multi-line
        ``script_*`` strings and multi-line ``buttons`` values wrapped in
        ``_BlockLiteralScript``; the ``buttons`` map rebuilt preserving its
        insertion order), then ``depends_on`` only when not ``None``.
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

    Args:
        doc: The document to serialize. Each ``FlowStage.fields`` must already be
            in canonical key order and ``depends_on`` must be ``None`` or a list
            of strings. ``prompt`` and ``root_dir`` must be ``None`` or a ``str``.
            Nothing is reordered or validated — out-of-order fields yield
            out-of-order output.

    Returns:
        The canonical afm flow-file content as a string ending with exactly
        one trailing newline. Top-level keys in fixed order: ``prompt``
        (block-literal; omitted when ``None``), ``root_dir`` (omitted when
        ``None``), ``name``, ``description``, ``memory`` (omitted when ``None``;
        fixed key order with ``None`` fields dropped), ``stages`` — each stage
        ``id``, ``name``, ``fields`` verbatim, then ``depends_on`` only when
        not ``None``. ``agents`` serializes flow-style; multi-line
        ``script_*`` and ``buttons`` values serialize block-literal.
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
