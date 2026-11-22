"""The ``parse_dsl`` pure parser and the ``StructuralError`` exception."""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

import yaml

from .body_format import BodyFormat
from .phase_step import PhaseStep
from .phases_body import PhasesBody
from .pipeline_assistant import PipelineAssistant
from .pipeline_header import PipelineHeader
from .pipeline_roles import PipelineRoles
from .stage_step import StageStep
from .stages_body import StagesBody

logger = logging.getLogger(__name__)

# ``re.split(..., maxsplit=1)`` yields one element when the separator is absent
# and exactly two (header, body) when it is present.
_EXPECTED_SEGMENT_COUNT = 2

# A well-formed pipeline-file stream carries exactly two documents — the
# header and the body. The anchor-carrying stream parse below keys its
# document-count dispatch on this constant.
_EXPECTED_DOCUMENT_COUNT = 2

# Fixed keys of the header-level ``roles`` block (one per overridable role alias;
# each translates to its afm agent name / prompt-file stem via ``translate_role``).
# Used both for unknown-key rejection and for projecting the validated mapping
# onto the ``PipelineRoles`` fields. ``summary`` is intentionally absent — it is
# a separate, always-default channel, not an overridable role.
_ROLE_KEYS = ("planner", "executor", "reviewer")

# Phase-step keys carried as separate fields, not inside the verbatim body.
# ``depends_on`` is reserved — phases derive it from list position (compile_flow),
# so any authored value is dropped rather than leaked into the output. ``id`` is a
# reserved output key (the stage id derives from ``name``); an authored value would
# otherwise clobber the serializer's seeded ``id`` and break the position-derived
# depends_on chain, so it is dropped too. ``assistants`` is extracted into
# the step's typed field (step 4a) — the raw key never reaches the verbatim
# body.
_PHASE_STEP_KEYS = {"name", "title", "depends_on", "id", "assistants"}

# Stage-step keys carried as separate fields, not inside the verbatim body. ``name``
# and ``id`` are reserved output keys (the display label derives from ``title``,
# the id from the map key); authored values would otherwise clobber the serializer's
# seeded ``name``/``id``, so they are dropped. ``assistants`` is extracted into
# the step's typed field (step 4a) — the raw key never reaches the verbatim
# body.
_STAGE_STEP_KEYS = {"title", "depends_on", "name", "id", "assistants"}

# The stage-body ``assistants`` map's value-key vocabulary (step 4a) — one
# pipeline-file stage-declared helper per entry. The delivery keys ``agent``,
# ``env`` and ``delegate`` are NOT part of it: authoring one here is the
# unknown-key error carrying the delivery-keys clause.
_ASSISTANT_DECLARATION_KEYS = ("prompt", "skills", "when", "gate")

# The declaration's ``when`` domain — the same four-value engagement
# vocabulary the workflow surface authors (compile_flow's ``_WHEN_TRIGGER``
# translates it to the afm trigger).
_ASSISTANT_WHEN_VALUES = ("start", "checkpoints", "finish", "message")

# Assistant-name grammar and the one reserved name — the cross-surface rules
# (identical to the workflow cell's): ``[A-Za-z0-9._-]+`` and never the
# afm-reserved ``assistant``.
_ASSISTANT_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
_RESERVED_ASSISTANT_NAME = "assistant"


class StructuralError(ValueError):
    """Raised when a pipeline-file is structurally malformed (authored-time defect)."""


class _PipelineFileLoader(yaml.SafeLoader):
    """SafeLoader that keeps the anchor registry across the stream's documents.

    A pipeline-file is one authoring unit split by the ``---`` separator line,
    so YAML links must cross the split: an anchor declared in the header
    segment (or in a hidden body key) stays resolvable in the body segment.
    The base loader resets the registry per document — the YAML spec scopes
    anchors to a document — so ``compose_document`` is overridden to keep it.
    Aliases still follow sequential order: an alias authored before its
    anchor fails as undefined, exactly as within one document.
    """

    def compose_document(self) -> Any:
        """Compose one document while preserving the shared anchor registry.

        Returns:
            The composed node graph of the next document in the stream.
        """
        # Drop the DOCUMENT-START/END events as the base loader does, but
        # deliberately skip the registry reset — the carriage of anchors
        # across the header/body separator lives exactly here.
        self.get_event()

        node = self.compose_node(None, None)

        self.get_event()

        return node


def _is_hidden_key(key: Any) -> bool:
    """Return whether ``key`` is a hidden declaration key (a ``str`` starting with ``.``).

    Args:
        key: The parsed body-level map key to classify.

    Returns:
        ``True`` when ``key`` is a ``str`` whose first character is a dot —
        the authoring idiom for YAML anchor declaration sites
        (``.defaults: &name``). By the time the body mapping reaches stage
        assembly, YAML resolution has already merged the anchored content
        into its use sites (aliases and ``<<:`` merge keys), so the key is
        not a stage name and must be dropped here.
    """
    return isinstance(key, str) and key.startswith(".")


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


def _parse_header(header_data: Any) -> PipelineHeader:
    """Validate the parsed header mapping into a ``PipelineHeader`` with string name/description.

    Args:
        header_data: The YAML-parsed header document (the first document of
            the stream) — any shape; a non-mapping fails the checks below.

    Returns:
        The parsed ``PipelineHeader`` (with ``roles`` set when the header
        carries a non-empty ``roles`` block).

    Raises:
        StructuralError: If the header is not a mapping, lacks string
            name/description, carries the legacy ``agents`` key (hard-rename
            error), carries a malformed ``roles`` block (non-mapping,
            unknown key, or non-str value), or carries a present
            ``repeatable`` value that is not strictly bool.
    """
    if not isinstance(header_data, dict):
        raise StructuralError("header missing name/description")

    name = header_data.get("name")
    description = header_data.get("description")

    if not (isinstance(name, str) and isinstance(description, str)):
        raise StructuralError("header missing name/description")

    # Hard-rename: the legacy ``agents`` header key is forbidden — the
    # authoring directive is now ``roles`` (3 overridable role aliases). A
    # user copying the old shape into the header is caught here rather than
    # silently dropped. Checked after name/description but before ``roles``
    # extraction so the rename error surfaces before any role-block error.
    if "agents" in header_data:
        raise StructuralError("agents key is forbidden in header; use roles")

    roles = _extract_roles(header_data.get("roles"))
    repeatable = _extract_repeatable(header_data)

    return PipelineHeader(name=name, description=description, roles=roles, repeatable=repeatable)


def _extract_roles(raw: Any) -> PipelineRoles | None:
    """Validate the optional ``roles`` block and build a ``PipelineRoles`` from it.

    Args:
        raw: The raw YAML-parsed value of the header's ``roles`` entry.

    Returns:
        ``None`` when the block is absent or empty, otherwise a
        ``PipelineRoles`` carrying the validated inline overrides; keys absent
        from the block stay ``None`` (verbatim pass-through, no merging with
        defaults).

    Raises:
        StructuralError: If ``raw`` is a non-mapping, has an unknown key, or
            has a non-str value.
    """
    if raw is None or raw == {}:
        return None

    if not isinstance(raw, dict):
        raise StructuralError("non-mapping roles block in header")

    for key, value in raw.items():
        if key not in _ROLE_KEYS:
            raise StructuralError(f"unknown role in header.roles: {key}; valid keys: planner, executor, reviewer")
        if not isinstance(value, str):
            raise StructuralError(f"non-str value in header.roles.{key}")

    return PipelineRoles(**{key: raw.get(key) for key in _ROLE_KEYS})


def _extract_repeatable(header_data: dict[str, Any]) -> bool:
    """Validate the optional header-level ``repeatable`` flag.

    Args:
        header_data: The YAML-parsed header mapping (key presence separates
            an absent flag from an authored explicit ``null`` — ``dict.get``
            alone cannot).

    Returns:
        The strictly bool flag value, or ``False`` when the key is absent —
        an absent key equals an explicit ``false``. The flag is carried into
        ``PipelineHeader`` and never enters the compiled flow-file directly
        (the compiled repeat directive is derived from it).

    Raises:
        StructuralError: If the key is present and its value is not strictly
            bool — an explicit ``null``, an int (``1``), or a quoted string
            (``"yes"``) all fail the strict ``isinstance(value, bool)`` test
            (``1 == True`` in Python, but ``1`` is an ``int`` that is not a
            ``bool``).
    """
    if "repeatable" not in header_data:
        return False

    value = header_data["repeatable"]

    if not isinstance(value, bool):
        raise StructuralError("non-bool value in header.repeatable")

    return value


def _validate_assistant_declaration_name(stage: str, name: Any) -> None:
    """Validate a declaration name's grammar and reserved status (the step-4a name rules).

    Args:
        stage: The step's name (the stage name in the error message).
        name: The authored declaration name — the map key of the entry, which
            YAML may parse as a non-``str`` (an int key, for instance).

    Raises:
        StructuralError: If ``name`` is not a ``str`` or does not fullmatch
            ``[A-Za-z0-9._-]+`` (the message names the stage and the key), or
            equals the reserved ``"assistant"`` (the cross-surface text).
    """
    # The non-str guard comes first — a non-str key must die on the clean
    # structural message, never on a ``TypeError`` out of ``fullmatch``.
    if not isinstance(name, str) or not _ASSISTANT_NAME_PATTERN.fullmatch(name):
        raise StructuralError(f"invalid assistant name in stage {stage}.assistants.{name}: {name}")

    if name == _RESERVED_ASSISTANT_NAME:
        raise StructuralError("assistant name is reserved")


def _validate_assistant_declaration_field(stage: str, name: Any, key: str, value: Any) -> None:
    """Validate one declaration value key (the four-key loop of step 4a).

    Args:
        stage: The step's name (the stage name in every error message).
        name: The declaration's name (the map key of the entry).
        key: The authored value key.
        value: The authored value.

    Raises:
        StructuralError: If the value fails its key's type check or the key
            is unknown — the delivery keys carry the workflow-file clause.
    """
    if key == "prompt":
        if not isinstance(value, str):
            raise StructuralError(f"non-str value in stage {stage}.assistants.{name}.prompt")
    elif key == "skills":
        if not isinstance(value, list) or not all(isinstance(skill, str) for skill in value):
            raise StructuralError(f"non-list-of-str skills in stage {stage}.assistants.{name}")
    elif key == "when":
        if value not in _ASSISTANT_WHEN_VALUES:
            raise StructuralError(
                f"when must be one of: {', '.join(_ASSISTANT_WHEN_VALUES)} in stage {stage}.assistants.{name}"
            )
    elif key == "gate":
        if not isinstance(value, bool):
            raise StructuralError(f"non-bool value in stage {stage}.assistants.{name}.gate")
    else:
        raise StructuralError(
            f"unknown key in stage {stage}.assistants.{name}: {key}; "
            f"valid keys: {', '.join(_ASSISTANT_DECLARATION_KEYS)}; "
            "agent, env, delegate are workflow-file territory"
        )


def _build_assistant_declaration(stage: str, name: Any, entry: Any) -> PipelineAssistant:
    """Validate one ``assistants`` entry and build its :class:`PipelineAssistant`.

    Args:
        stage: The step's name (the stage name in every error message).
        name: The declaration's name — the map key of the entry.
        entry: The raw parsed entry value.

    Returns:
        The validated declaration (``gate`` materializes the advisory
        ``False`` when not authored).

    Raises:
        StructuralError: If the entry is not a mapping, ``when`` is absent,
            a value fails its type check or the key is unknown, the name is
            invalid or reserved, or the entry resolves neither ``prompt``
            nor ``skills``.
    """
    if not isinstance(entry, dict):
        raise StructuralError(f"non-mapping assistant declaration in stage {stage}.assistants.{name}")

    # ``when`` presence is checked before the key loop — an empty entry
    # dies as when-required, never as an unknown key.
    if "when" not in entry:
        raise StructuralError(f"when is required in stage {stage}.assistants.{name}")

    for key, value in entry.items():
        _validate_assistant_declaration_field(stage, name, key, value)

    _validate_assistant_declaration_name(stage, name)

    prompt = entry.get("prompt")
    skills = entry.get("skills")

    if prompt is None and skills is None:
        raise StructuralError(f"assistant declaration {name} in stage {stage} resolves neither prompt nor skills")

    return PipelineAssistant(
        name=name,
        prompt=prompt,
        skills=skills,
        when=entry["when"],
        gate=entry.get("gate", False),
    )


def _extract_step_assistants(stage: str, item: dict[str, Any]) -> dict[str, PipelineAssistant] | None:
    """Validate a step item's ``assistants`` map and build the declaration models (step 4a).

    Args:
        stage: The step's name (the stage name in every error message).
        item: The raw parsed step item (a list element or a map value).

    Returns:
        The deep-copied map of validated :class:`PipelineAssistant`
        declarations keyed by assistant name, in authored order — ``None``
        when the item carries no ``assistants`` key or an empty map (an
        empty map equals absence).

    Raises:
        StructuralError: If the map is not a mapping or any entry fails the
            declaration validation (see :func:`_build_assistant_declaration`).
    """
    raw = item.get("assistants")

    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise StructuralError(f"non-mapping assistants in stage {stage}; author the map form keyed by assistant name")

    if not raw:
        return None

    built = {name: _build_assistant_declaration(stage, name, entry) for name, entry in raw.items()}

    return copy.deepcopy(built)


def _extract_phase_step(item: Any) -> PhaseStep:
    """Build a ``PhaseStep`` from one element of a list body, deep-copying its fields.

    Args:
        item: One element of the parsed list body.

    Returns:
        The ``PhaseStep`` with name/title split out, the ``assistants`` map
        extracted into the typed field (step 4a), and a deep-copied body.

    Raises:
        StructuralError: If the item is not a mapping, lacks string
            name/title, or its ``assistants`` map fails step-4a validation.
    """
    if not isinstance(item, dict):
        raise StructuralError("phase item must be a mapping")

    name = item.get("name")
    title = item.get("title")

    if not (isinstance(name, str) and isinstance(title, str)):
        raise StructuralError("phase item missing name/title")

    assistants = _extract_step_assistants(name, item)
    body = _deep_copy_without(item, _PHASE_STEP_KEYS)

    return PhaseStep(name=name, title=title, body=body, assistants=assistants)


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
        The ``StageStep`` with title/depends_on split out, the ``assistants``
        map extracted into the typed field (step 4a), and a deep-copied body.

    Raises:
        StructuralError: If the key is not a string, the value is not a mapping,
            lacks a string title, has a malformed ``depends_on``, or its
            ``assistants`` map fails step-4a validation.
    """
    if not isinstance(name, str):
        raise StructuralError("stage name must be a string")

    if not isinstance(value, dict):
        raise StructuralError("stage value must be a mapping")

    title = value.get("title")

    if not isinstance(title, str):
        raise StructuralError("stage value missing title")

    depends_on = _extract_depends_on(value.get("depends_on"))
    assistants = _extract_step_assistants(name, value)
    body = _deep_copy_without(value, _STAGE_STEP_KEYS)

    return StageStep(name=name, title=title, depends_on=depends_on, body=body, assistants=assistants)


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

    YAML links carry across the ``---`` separator: the file is parsed as one
    stream whose anchor registry survives the document boundary, so an anchor
    declared in the header segment (or in a hidden body key) resolves in the
    body segment. Hidden declaration keys — top-level body keys starting with
    ``.`` — are anchor sites, not stages: their content is already merged by
    YAML resolution, and they are dropped before stage assembly.

    Args:
        text: Full pipeline-file text (must contain a ``---`` separator line —
            matched as a line of exactly three dashes, not a substring).

    Returns:
        A 3-tuple ``(header, fmt, body)`` where ``header`` is the parsed
        ``PipelineHeader``, ``fmt`` is the detected ``BodyFormat`` (PHASES for a
        list body, STAGES for a mapping body), and ``body`` is the parsed
        ``PhasesBody`` (PHASES) or ``StagesBody`` (STAGES). Step bodies are
        deep-copied so caller mutation cannot affect the source; a step's
        ``assistants`` map is extracted into its typed field (the verbatim body
        excludes the key); an empty body parses with zero steps
        (``compile_flow`` rejects it).

    Raises:
        StructuralError: If the separator is missing, the text is invalid YAML
            ("invalid YAML in pipeline-file"), the stream carries an extra
            separator line inside the body ("extra body separator"), the
            header lacks string name/description (an empty or comment-only
            header segment included), the header's ``repeatable`` flag is
            present and not strictly bool, the body is neither list nor
            mapping, a step is not a mapping or lacks required fields,
            ``depends_on`` is not ``None``/``list[str]``, or a step's
            ``assistants`` map fails the step-4a vocabulary (a non-mapping
            map or entry, a missing ``when``, a bad value type, an unknown
            key — the delivery keys carry the workflow-file clause —, an
            invalid or reserved name, or a declaration resolving neither
            ``prompt`` nor ``skills``).
    """
    # The split stays the structural pre-check: the separator line must be a
    # line of exactly three dashes ("missing body separator", the four-dash
    # rejection) — the body segment itself is not re-parsed from the split,
    # the stream parse below owns the content.
    header_text, _ = _split_segments(text)

    # One stream parse with anchor carriage: an anchor declared in the
    # header segment resolves in the body segment (and vice versa in
    # authored order). The low-level YAML error is replaced with a clean
    # structural message — the parser contract does not expose YAML
    # internals.
    try:
        documents = list(yaml.load_all(text, Loader=_PipelineFileLoader))
    except yaml.YAMLError:
        raise StructuralError("invalid YAML in pipeline-file") from None

    if len(documents) == _EXPECTED_DOCUMENT_COUNT and not header_text.strip():
        # A leading separator line: the header segment is empty, so the
        # stream's first document is body content — the header itself is
        # absent, the same empty-header error an empty header text produces.
        raise StructuralError("header missing name/description")

    if len(documents) != _EXPECTED_DOCUMENT_COUNT:
        # The separator pre-check has passed, so fewer than two documents
        # mean an empty or comment-only header segment (the single document
        # is the body); more than two mean an extra separator line inside
        # the body.
        message = (
            "header missing name/description" if len(documents) < _EXPECTED_DOCUMENT_COUNT else "extra body separator"
        )

        raise StructuralError(message)

    header = _parse_header(documents[0])

    parsed_body = documents[1]

    # An empty body document parses to None; normalize so an empty list body is
    # treated as PHASES with zero steps (compile_flow raises "empty body").
    if parsed_body is None:
        parsed_body = []

    # Hidden declaration keys (anchor sites such as ``.defaults: &name``) are
    # not stage names — YAML resolution has already merged their content, so
    # they are dropped before stage assembly.
    if isinstance(parsed_body, dict):
        parsed_body = {key: value for key, value in parsed_body.items() if not _is_hidden_key(key)}

    fmt, body = _build_body(parsed_body)

    return header, fmt, body
