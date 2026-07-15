"""The ``compile_flow`` entry point — read a pipeline-file, compile, write a flow-file.

``compile_flow`` is the entry point of the compiler cell: it reads a goga DSL
pipeline-file (phases-list or stages-map), parses it via ``parse_dsl``, applies
the per-format ``depends_on`` rules (PHASES: position-derived; STAGES:
pass-through), reorders each step body into canonical key order via the internal
``_canonical_fields`` helper, builds a ``FlowDocument``, serializes it via
``serialize_flow``, and writes the result to ``flow_path``. It performs no
environment-variable reads and no subprocess calls — the caller supplies both
paths explicitly.

I/O exceptions and structural errors from ``parse_dsl`` propagate unchanged. An
empty body raises ``StructuralError("empty body")`` here — not in ``parse_dsl``,
which lets empty bodies through for ``compile_flow`` to reject.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from .body_format import BodyFormat
from .flow_document import FlowDocument
from .flow_stage import FlowStage
from .parse_dsl import StructuralError, parse_dsl
from .serialize_flow import serialize_flow

logger = logging.getLogger(__name__)

# Canonical key order for the output stage fields. ``serialize_flow`` emits
# ``FlowStage.fields`` verbatim, so canonical order must be established here.
_CANONICAL_KEY_ORDER = ["interactive", "prompt", "agents", "skills"]


def _canonical_fields(body: dict[str, Any]) -> dict[str, Any]:
    """Reorder ``body`` into canonical key order, deep-copying each value.

    Known keys (``interactive``, ``prompt``, ``agents``, ``skills``) are emitted
    first in that fixed order; any remaining keys are appended alphabetically.
    Each value is deep-copied so the returned dict shares no structure with the
    parsed body — isolating the compiler's output from caller mutation.

    Args:
        body: The step body dict produced by ``parse_dsl``.

    Returns:
        A new dict in canonical key order with deep-copied values.
    """
    ordered: dict[str, Any] = {}
    for key in _CANONICAL_KEY_ORDER:
        if key in body:
            ordered[key] = copy.deepcopy(body[key])
    extras = sorted(k for k in body if k not in _CANONICAL_KEY_ORDER)
    for key in extras:
        ordered[key] = copy.deepcopy(body[key])
    return ordered


def compile_flow(pipeline_path: Path, flow_path: Path) -> None:
    """Compile a goga DSL pipeline-file into an afm flow-file.

    Reads ``pipeline_path``, parses it with ``parse_dsl``, rejects an empty body
    with ``StructuralError("empty body")``, then builds a ``FlowDocument`` whose
    stages carry canonical-key-order ``fields`` and per-format ``depends_on``
    (position-derived for PHASES — the first step gets none, each subsequent step
    depends on its predecessor; pass-through for STAGES). The document is
    serialized via ``serialize_flow`` and written to ``flow_path`` (overwriting if
    it exists). I/O errors and structural errors from ``parse_dsl`` propagate
    unchanged; ``compile_flow`` does not read ``AFM_DIR``.

    Args:
        pipeline_path: Absolute path to the input goga DSL pipeline-file. The file
            must be readable and contain a ``---`` separator line.
        flow_path: Absolute path to the output afm flow-file. The parent directory
            must already exist; it is not created here.

    Raises:
        StructuralError: On a structural defect in the DSL (propagated from
            ``parse_dsl``) or on an empty body.
        FileNotFoundError: If ``pipeline_path`` does not exist or ``flow_path``'s
            parent is missing (propagated).
        PermissionError: If ``pipeline_path`` is unreadable (propagated).
    """
    logger.info("compile_flow: %s → %s", pipeline_path, flow_path)

    text = pipeline_path.read_text()
    header, fmt, body = parse_dsl(text)

    if len(body.steps) == 0:
        raise StructuralError("empty body")

    stages: list[FlowStage] = []
    if fmt is BodyFormat.PHASES:
        for i, step in enumerate(body.steps):
            depends_on = [body.steps[i - 1].name] if i > 0 else None
            fields = _canonical_fields(step.body)
            stages.append(
                FlowStage(
                    id=step.name,
                    name=step.description,
                    depends_on=depends_on,
                    fields=fields,
                ),
            )
    elif fmt is BodyFormat.STAGES:
        for step in body.steps:
            fields = _canonical_fields(step.body)
            stages.append(
                FlowStage(
                    id=step.name,
                    name=step.description,
                    depends_on=step.depends_on,
                    fields=fields,
                ),
            )

    doc = FlowDocument(name=header.name, description=header.description, stages=stages)
    text_out = serialize_flow(doc)
    flow_path.write_text(text_out)
