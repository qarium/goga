"""The ``serialize_flow`` pure serializer — ``FlowDocument`` to canonical afm YAML.

``serialize_flow`` is the serialization half of the compiler cell: it takes a
fully-built ``FlowDocument`` (with ``FlowStage.fields`` already in canonical key
order — enforced by ``compile_flow``) and renders it into the canonical afm
flow-file format. It performs no file I/O and no reordering.

The one non-standard rule — flow-style for ``agents`` while ``skills`` and
``depends_on`` stay block-style — is isolated behind the ``_FlowAgents`` marker
list and its custom representer on ``_CanonicalDumper``. ``serialize_flow`` wraps
any ``agents`` list value in ``_FlowAgents`` before passing the document to
``yaml.dump``, so the rule never leaks into the rest of the pipeline.
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


class _CanonicalDumper(yaml.SafeDumper):
    """``SafeDumper`` subclass carrying the ``_FlowAgents`` flow-style representer."""
    pass


_CanonicalDumper.add_representer(_FlowAgents, _represent_flow_agents)


def _build_stage_repr(stage: FlowStage) -> dict[str, object]:
    """Build the per-stage dict in fixed order (id, name, canonical fields, depends_on).

    ``agents`` list values are wrapped in ``_FlowAgents`` so they serialize in
    flow-style. ``depends_on`` is emitted only when not ``None`` (distinguishing
    absent from explicit empty).

    Args:
        stage: One ``FlowStage`` of the document.

    Returns:
        The ordered mapping to feed to ``yaml.dump``.
    """
    stage_repr: dict[str, object] = {"id": stage.id, "name": stage.name}

    for key, value in stage.fields.items():
        if key == "agents" and isinstance(value, list):
            stage_repr[key] = _FlowAgents(value)
        else:
            stage_repr[key] = value

    if stage.depends_on is not None:
        stage_repr["depends_on"] = stage.depends_on

    return stage_repr


def serialize_flow(doc: FlowDocument) -> str:
    """Serialize a ``FlowDocument`` into canonical afm flow-file YAML.

    Top-level keys are emitted in fixed order (``name``, ``description``,
    ``stages``); each stage is emitted as ``id``, ``name``, then the stage's
    ``fields`` verbatim (preserving their canonical order), then ``depends_on``
    only when it is not ``None``. ``agents`` lists serialize in flow-style;
    ``skills`` and ``depends_on`` serialize in block-style. The output ends with
    exactly one trailing newline.

    The serializer does not reorder, validate, or otherwise transform the input —
    a document with out-of-order ``fields`` produces out-of-order output.

    Args:
        doc: The document to serialize. Each ``FlowStage.fields`` must already be
            in canonical key order and ``depends_on`` must be ``None`` or a list
            of strings.

    Returns:
        The canonical afm flow-file content as a string.
    """
    top: dict[str, object] = {
        "name": doc.name,
        "description": doc.description,
        "stages": [_build_stage_repr(stage) for stage in doc.stages],
    }

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
