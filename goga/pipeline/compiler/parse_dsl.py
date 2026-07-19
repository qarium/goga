"""The ``parse_dsl`` pure parser and the ``StructuralError`` exception.

``parse_dsl`` is the parsing half of the compiler cell: it takes the full text of
a goga DSL pipeline-file, splits it into a header segment and a body segment on a
literal three-dash line, structurally validates both, and returns a typed
3-tuple ``(PipelineHeader, BodyFormat, PhasesBody | StagesBody)``. It performs no
file I/O, no validation of step-field contents, and no ``depends_on`` rule
application (position-derived ``depends_on`` is ``compile_flow``'s job).

A pipeline-file without a ``---`` separator is, by design, a structural error —
already-afm-format files are rejected rather than silently re-parsed.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

import yaml

from .body_format import BodyFormat
from .phase_step import PhaseStep
from .phases_body import PhasesBody
from .pipeline_agents import PipelineAgents
from .pipeline_header import PipelineHeader
from .stage_step import StageStep
from .stages_body import StagesBody

logger = logging.getLogger(__name__)

# ``re.split(..., maxsplit=1)`` yields one element when the separator is absent
# and exactly two (header, body) when it is present.
_EXPECTED_SEGMENT_COUNT = 2

# Fixed keys of the header-level ``agents`` block (one per afm agent prompt file).
# Used both for unknown-key rejection and for projecting the validated mapping
# onto the ``PipelineAgents`` fields.
_AGENT_KEYS = ("planning", "implementation", "review", "summary")

# Phase-step keys carried as separate fields, not inside the verbatim body.
# ``depends_on`` is reserved — phases derive it from list position (compile_flow),
# so any authored value is dropped rather than leaked into the output. ``id`` is a
# reserved output key (the stage id derives from ``name``); an authored value would
# otherwise clobber the serializer's seeded ``id`` and break the position-derived
# depends_on chain, so it is dropped too.
_PHASE_STEP_KEYS = {"name", "title", "depends_on", "id"}

# Stage-step keys carried as separate fields, not inside the verbatim body. ``name``
# and ``id`` are reserved output keys (the display label derives from ``title``,
# the id from the map key); authored values would otherwise clobber the serializer's
# seeded ``name``/``id``, so they are dropped.
_STAGE_STEP_KEYS = {"title", "depends_on", "name", "id"}


class StructuralError(ValueError):
    """Raised when a pipeline-file is structurally malformed.

    A structural error is an authored-time defect in the DSL: a missing
    ``---`` separator, a header without a string name/description, a body
    that is neither a list nor a mapping, a step missing required fields, or
    a ``depends_on`` that is not ``None``/``list[str]``. Reference resolution
    (dangling ids, cycles, duplicates) is afm's responsibility, not ours.
    """


def _split_segments(text: str) -> tuple[str, str]:
    """Split ``text`` into (header_text, body_text) on the literal ``---`` line.

    Args:
        text: Full pipeline-file text.

    Returns:
        The header and body segments.

    Raises:
        StructuralError: If no ``---`` separator line is present.
    """
    # Match exactly three dashes; the optional ``\r`` keeps CRLF (Windows) line
    # endings working — under ``re.MULTILINE`` ``$`` sits before ``\n``, so a
    # ``---\r\n`` line otherwise reads as ``---\r`` and fails to match.
    parts = re.split(r"^---\r?$", text, maxsplit=1, flags=re.MULTILINE)

    if len(parts) < _EXPECTED_SEGMENT_COUNT:
        raise StructuralError("missing body separator")

    return parts[0], parts[1]


def _parse_header(header_text: str) -> PipelineHeader:
    """Parse the header segment into a ``PipelineHeader`` with string name/description.

    Args:
        header_text: The header segment text (before the ``---`` line).

    Returns:
        The parsed ``PipelineHeader`` (with ``agents`` set when the header
        carries a non-empty ``agents`` block).

    Raises:
        StructuralError: If the header is not a mapping, lacks string
            name/description, or carries a malformed ``agents`` block
            (non-mapping, unknown key, or non-str value).
    """
    header_data = yaml.safe_load(header_text)

    if not isinstance(header_data, dict):
        raise StructuralError("header missing name/description")

    name = header_data.get("name")
    description = header_data.get("description")

    if not (isinstance(name, str) and isinstance(description, str)):
        raise StructuralError("header missing name/description")

    agents = _extract_agents(header_data.get("agents"))

    return PipelineHeader(name=name, description=description, agents=agents)


def _extract_agents(raw: Any) -> PipelineAgents | None:
    """Validate the optional ``agents`` block and build a ``PipelineAgents`` from it.

    An absent block (``raw is None``) and an empty mapping (``raw == {}``) are
    treated identically — both yield ``None`` (no overrides). A non-mapping
    value, an unknown key, or a non-str value are structural errors. The four
    fixed keys are projected onto the ``PipelineAgents`` fields; keys absent
    from the block stay ``None``. No merging with defaults and no content
    validation happens here (verbatim pass-through).

    Args:
        raw: The raw YAML-parsed value of the header's ``agents`` entry.

    Returns:
        ``None`` when the block is absent or empty, otherwise a
        ``PipelineAgents`` carrying the validated inline overrides.

    Raises:
        StructuralError: If ``raw`` is a non-mapping, has an unknown key, or
            has a non-str value.
    """
    if raw is None or raw == {}:
        return None

    if not isinstance(raw, dict):
        raise StructuralError("non-mapping agents block in header")

    for key, value in raw.items():
        if key not in _AGENT_KEYS:
            raise StructuralError(
                f"unknown agent in header.agents: {key}; valid keys: planning, implementation, review, summary"
            )
        if not isinstance(value, str):
            raise StructuralError(f"non-str value in header.agents.{key}")

    return PipelineAgents(**{key: raw.get(key) for key in _AGENT_KEYS})


def _extract_phase_step(item: Any) -> PhaseStep:
    """Build a ``PhaseStep`` from one element of a list body, deep-copying its fields.

    Args:
        item: One element of the parsed list body.

    Returns:
        The ``PhaseStep`` with name/title split out and a deep-copied body.

    Raises:
        StructuralError: If the item is not a mapping or lacks string
            name/title.
    """
    if not isinstance(item, dict):
        raise StructuralError("phase item must be a mapping")

    name = item.get("name")
    title = item.get("title")

    if not (isinstance(name, str) and isinstance(title, str)):
        raise StructuralError("phase item missing name/title")

    body = _deep_copy_without(item, _PHASE_STEP_KEYS)

    return PhaseStep(name=name, title=title, body=body)


def _extract_depends_on(depends_on: Any) -> list[str] | None:
    """Validate and return a stage's ``depends_on`` (``None``, or ``list[str]``).

    Args:
        depends_on: The raw parsed ``depends_on`` value.

    Returns:
        The validated ``depends_on`` (``None`` when absent, the list otherwise).

    Raises:
        StructuralError: If ``depends_on`` is present but not a list of strings.
    """
    if depends_on is not None and not isinstance(depends_on, list):
        raise StructuralError("stage depends_on must be a list")

    if isinstance(depends_on, list) and not all(isinstance(x, str) for x in depends_on):
        raise StructuralError("stage depends_on must contain only strings")

    return depends_on


def _extract_stage_step(name: Any, value: Any) -> StageStep:
    """Build a ``StageStep`` from one entry of a mapping body, deep-copying its fields.

    Args:
        name: The map key (becomes the step id).
        value: The map value for this step.

    Returns:
        The ``StageStep`` with title/depends_on split out and a deep-copied body.

    Raises:
        StructuralError: If the key is not a string, the value is not a mapping,
            lacks a string title, or has a malformed ``depends_on``.
    """
    if not isinstance(name, str):
        raise StructuralError("stage name must be a string")

    if not isinstance(value, dict):
        raise StructuralError("stage value must be a mapping")

    title = value.get("title")

    if not isinstance(title, str):
        raise StructuralError("stage value missing title")

    depends_on = _extract_depends_on(value.get("depends_on"))
    body = _deep_copy_without(value, _STAGE_STEP_KEYS)

    return StageStep(name=name, title=title, depends_on=depends_on, body=body)


def _deep_copy_without(mapping: dict[str, Any], excluded: set[str]) -> dict[str, Any]:
    """Deep-copy ``mapping`` omitting ``excluded`` keys so caller mutation cannot reach the source.

    Args:
        mapping: The source mapping.
        excluded: Keys to drop (carried as separate fields, not body content).

    Returns:
        A deep-copied dict of every key not in ``excluded``.
    """
    return {key: copy.deepcopy(value) for key, value in mapping.items() if key not in excluded}


def _build_body(parsed_body: Any) -> tuple[BodyFormat, PhasesBody | StagesBody]:
    """Detect the body format and build the typed body, deep-copying every step.

    Args:
        parsed_body: The YAML-parsed body (a list, a mapping, or None/scalar).

    Returns:
        A 2-tuple ``(fmt, body)`` — PHASES/PhasesBody for a list, STAGES/StagesBody
        for a mapping.

    Raises:
        StructuralError: If the body is neither a list nor a mapping.
    """
    if isinstance(parsed_body, list):
        steps = [_extract_phase_step(item) for item in parsed_body]

        return BodyFormat.PHASES, PhasesBody(steps=steps)

    if isinstance(parsed_body, dict):
        steps = [_extract_stage_step(name, value) for name, value in parsed_body.items()]

        return BodyFormat.STAGES, StagesBody(steps=steps)

    raise StructuralError("unsupported body format")


def parse_dsl(text: str) -> tuple[PipelineHeader, BodyFormat, PhasesBody | StagesBody]:
    """Structurally parse a pipeline-file into a header, a body format, and a typed body.

    The three-dash separator is matched as a line of exactly three dashes (per
    YAML document-separator convention), not as a substring. The header segment
    must be a mapping with string ``name`` and ``description``. The body segment
    is a YAML list (PHASES) or mapping (STAGES); anything else is rejected. Step
    bodies are deep-copied so subsequent caller mutation cannot affect the
    source. Empty bodies are NOT an error here — ``compile_flow`` checks that.

    Args:
        text: Full pipeline-file text (must contain a ``---`` separator line).

    Returns:
        A 3-tuple ``(header, fmt, body)`` where ``header`` is the parsed
        ``PipelineHeader``, ``fmt`` is the detected ``BodyFormat`` (PHASES for a
        list body, STAGES for a mapping body), and ``body`` is the parsed
        ``PhasesBody`` (PHASES) or ``StagesBody`` (STAGES).

    Raises:
        StructuralError: If the separator is missing, the header lacks string
            name/description, the body is neither list nor mapping, a step is
            not a mapping or lacks required fields, or ``depends_on`` is not
            ``None``/``list[str]``.
    """
    header_text, body_text = _split_segments(text)

    header = _parse_header(header_text)

    parsed_body = yaml.safe_load(body_text)

    # An empty body segment parses to None; normalize so an empty list body is
    # treated as PHASES with zero steps (compile_flow raises "empty body").
    if parsed_body is None:
        parsed_body = []

    fmt, body = _build_body(parsed_body)

    return header, fmt, body
