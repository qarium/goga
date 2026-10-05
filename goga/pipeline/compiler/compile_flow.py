"""The ``compile_flow`` entry point — read a pipeline-file, compile, write a flow-file."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..workflow import WorkflowDocument, WorkflowExtendStage, WorkflowMemory, WorkflowStage
from .body_format import BodyFormat
from .flow_document import FlowDocument
from .flow_memory import FlowMemory
from .flow_stage import FlowStage
from .parse_dsl import StructuralError, parse_dsl
from .phase_step import PhaseStep
from .phases_body import PhasesBody
from .pipeline_document import PipelineDocument
from .serialize_flow import serialize_flow
from .stage_step import StageStep
from .stages_body import StagesBody

logger = logging.getLogger(__name__)

# Canonical key order for the output stage fields. ``serialize_flow`` emits
# ``FlowStage.fields`` verbatim, so canonical order must be established here.
# ``command`` and ``description`` are populated by per-stage workflow overrides
# (workflow branch); when absent they are simply skipped by the loop below.
# ``supervisor`` and ``supervisor_prompt`` sit between ``agents`` and ``skills``
# so the supervisor block reads as a continuation of the agents block.
# ``auto_approve`` (bool) sits right after ``interactive`` and is present only
# when an approve directive driving the roles effect (``auto``/``dialog``) +
# planner-in-roles fired (workflow-driven). ``auto_run`` (bool) sits right after
# ``auto_approve`` and is present ONLY when the stage's effective trigger is
# ``manual`` (the value is always ``False`` — ``auto_run: true`` is never
# assembled; afm pauses such a stage until a manual launch). The author
# script directives (``before_script``/``script``/``after_script``) are translated
# to ``script_before``/``script``/``script_after`` and slotted after ``skills``;
# they appear only when authored, so flow-files without them compile byte-identically.
# ``script_timeout`` (str) sits immediately after ``script_after`` — the
# translated form of the authoring ``timeout`` directive — and is likewise
# present only when authored (or directly authored under its output name).
# ``buttons`` (map of str→str) sits immediately after ``description`` — the
# compiled form of the workflow ``notes`` instruction (the map verbatim, one
# deep copy per ``FlowStage``); present only when the workflow supplied a
# non-empty notes instruction for the stage, so pipelines without notes
# compile byte-identically.
# ``reflect`` (map of file + mode) and ``memory_use`` (bool) close the list —
# the compiled form of the workflow memory instructions. ``reflect`` is present
# only when the memory block is emitted and the stage's reflect instruction is
# effective (the authored file verbatim, the materialized mode), uniform across
# every loop-expanded copy. ``memory_use`` is present only when the block is
# emitted under the alignment method — ``True`` on a participating stage, an
# explicit ``False`` on every non-participating one. A stage of a memory-free
# workflow carries neither key, so pipelines without memory participation
# compile byte-identically.
_CANONICAL_KEY_ORDER = [
    "interactive",
    "auto_approve",
    "auto_run",
    "command",
    "prompt",
    "description",
    "buttons",
    "agents",
    "supervisor",
    "supervisor_prompt",
    "skills",
    "script_before",
    "script",
    "script_after",
    "script_timeout",
    "reflect",
    "memory_use",
]

# The fixed project-memory root of the emitted memory block. The authored
# ``memory.path`` suffix is joined onto this root (``.goga/memory/<suffix>``);
# a ``None`` suffix emits the bare root. The root is fixed here — the workflow
# cell carries the authored suffix only, and this cell composes the final path
# (the single composition site).
_MEMORY_ROOT = ".goga/memory"

# Sentinel key threaded by ``_apply_per_stage_overrides`` into a reconstructed
# step body to carry the effective ``approve`` directive through loop-expansion
# (it survives ``copy.deepcopy`` in ``_expand_loops``/``_make_expanded_copy``)
# into ``_canonical_fields``, where it is READ (not popped) and consumed to drive
# the two approve effects (interactive suppression + ``auto_approve`` emission,
# each on its own directive subset — see ``_APPROVE_SUPPRESS_INTERACTIVE`` /
# ``_APPROVE_EMIT_AUTO_APPROVE``). The sentinel is output-only plumbing — it is
# EXCLUDED from the
# fresh dict ``_canonical_fields`` builds, so it NEVER reaches
# ``FlowStage.fields``. ``_canonical_fields`` never mutates its ``body`` argument
# (it reads the sentinel and rebuilds a new dict), so on the non-workflow path —
# where ``body`` is the caller's shared dict — nothing is mutated either.
_APPROVE_SENTINEL = "_approve_directive"

# The two INDEPENDENT ``approve`` effects each fire on their own trigger and on
# their own subset of the accepted directives (``auto``/``plan``/``dialog``).
# ``auto`` fires BOTH; ``plan`` fires only interactive suppression (the
# communication effect) and ``dialog`` fires only ``auto_approve`` (the roles
# effect). ``None`` (no directive) fires neither. The accepted value set is
# owned by ``goga/pipeline/workflow/parse_workflow.py`` (``_APPROVE_DIRECTIVES``);
# these two tuples select which directives drive each effect here.
_APPROVE_SUPPRESS_INTERACTIVE: tuple[str, ...] = ("auto", "plan")
_APPROVE_EMIT_AUTO_APPROVE: tuple[str, ...] = ("auto", "dialog")

# In-container wrapper path template consumed by afm >= 0.4.15 as the per-stage
# ``command:`` override. Composed directly from the ``WorkflowStage`` agent name
# — the cell does NOT call any host-side wrapper resolver.
_WRAPPER_PATH_TEMPLATE = "/home/goga/bin/{agent}-as-claude.sh"

# Loop count at and above which a stage is expanded into multiple copies.
# ``>= _LOOP_EXPANSION_THRESHOLD`` triggers expansion (and an external
# depends_on rewrite to the LAST expanded id); a count of ``1`` is a no-op.
_LOOP_EXPANSION_THRESHOLD = 2

# Default value injected into ``FlowStage.fields`` when the source step body
# carries no usable ``roles`` value. A missing ``roles`` key, an explicit
# ``None``, OR an empty list all trigger injection — authored non-empty ``roles``
# always wins (each value translated to its afm agent name via ``translate_role``).
# ``auto`` is a sentinel string emitted verbatim; goga does NOT interpret it (afm
# resolves the agent). Authored ``supervisor``/``supervisor_prompt`` are NOT
# injected — they are authored-only and pass through the canonical slot when the
# source body carries them.
_DEFAULT_AGENTS: tuple[str, ...] = ("auto",)

# Single source of truth for the bijection between an authoring-side role and its
# afm-side agent name / prompt-file stem. The three known role aliases
# (``planner``/``executor``/``reviewer``) map to their afm stems
# (``planning``/``implementation``/``review``); every other value is passed
# through verbatim by ``translate_role`` — the afm agent namespace is open, so
# already-afm names, ``summary``, ``auto``, and arbitrary names need no
# translation and no validation. Declared exactly once here; consumers
# (``compile_flow`` stage translation, ``run_pipeline`` prompt materialization)
# import ``translate_role`` rather than re-declaring this mapping.
_ROLE_ALIASES: dict[str, str] = {
    "planner": "planning",
    "executor": "implementation",
    "reviewer": "review",
}


def translate_role(role: str) -> str:
    """Map an authoring-side ``role`` to its afm-side agent name / prompt-file stem — the single translation site.

    Args:
        role: The authoring-side role value (an alias or an already-afm name).

    Returns:
        The afm-side agent name / prompt-file stem for a known alias, or
        ``role`` unchanged for any other value — values are NOT validated (the
        afm agent namespace is open; already-afm names, ``summary``, ``auto``,
        and arbitrary names all return unchanged).
    """
    return _ROLE_ALIASES.get(role, role)


def _has_usable_roles(body: dict[str, Any]) -> bool:
    """Return ``True`` when ``body`` carries a non-empty ``roles`` list.

    Args:
        body: The step body dict produced by ``parse_dsl``.

    Returns:
        ``True`` when ``roles`` is a non-empty list; ``False`` for a missing
        key, an explicit ``None``, or an empty list — the default-injection
        triggers.
    """
    roles = body.get("roles")
    return isinstance(roles, list) and len(roles) > 0


def _inject_defaults(body: dict[str, Any], suppress_agents: bool = False) -> dict[str, Any]:
    """Return a body dict with ``roles`` translated to ``agents`` (or the default injected).

    Args:
        body: The step body dict produced by ``parse_dsl``.
        suppress_agents: When ``True``, assemble no ``agents`` key at all —
            neither the single ``["auto"]`` default nor the translated
            ``roles`` value (a body carrying ``script``; afm rejects the
            combination).

    Returns:
        A new dict without the ``roles`` key (always dropped), carrying either
        the translated ``agents`` list or the injected single ``["auto"]``
        default — or no ``agents`` key at all when ``suppress_agents`` is
        ``True``; no ``supervisor``/``supervisor_prompt`` key is added. The
        input is never mutated.

    Raises:
        StructuralError: When a ``roles`` element is not a ``str`` (the body is
            parsed verbatim, so the unvalidated list may carry any type).
    """
    out = {key: value for key, value in body.items() if key != "roles"}

    if _has_usable_roles(body):
        # The pipeline-file body is parsed verbatim (``parse_dsl`` performs no
        # field-content validation by design), so an authored ``roles`` list may
        # carry unhashable (dict/list) or non-str elements. ``translate_role`` is
        # contractually required NOT to validate (open afm namespace): an unhashable
        # element would raise a raw ``TypeError`` from its dict lookup, and a hashable
        # non-str (e.g. an int) would pollute the ``list[str]`` output unchanged.
        # Reject non-str elements here with a clean ``StructuralError`` instead —
        # mirroring the header ``roles`` validation in ``parse_dsl._extract_roles``.
        # The validation runs under ``suppress_agents`` too, so authoring defects
        # surface identically whether or not the value is emitted.
        for role in body["roles"]:
            if not isinstance(role, str):
                raise StructuralError(f"non-str value in stage roles list: {role!r}")

        if not suppress_agents:
            out["agents"] = [translate_role(role) for role in body["roles"]]
    elif not suppress_agents:
        out["agents"] = list(_DEFAULT_AGENTS)

    return out


def _reject_authoring_output_keys(body: dict[str, Any]) -> None:
    """Reject authoring-side stage-body keys that duplicate output-only afm fields.

    Args:
        body: The step body dict produced by ``parse_dsl`` (or an embedded
            extend body).

    Raises:
        StructuralError: When ``body`` carries any output-only key — ``agents``
            (author ``roles``), ``interactive`` (author ``communication``),
            ``auto_run`` (author ``trigger``), ``buttons`` (author the workflow
            ``notes`` instruction), ``reflect``/``memory_use`` (author the
            workflow memory instructions) — with the message naming the
            authoring-side field.
    """
    if "agents" in body:
        raise StructuralError("agents key is forbidden in stage body; use roles")

    if "interactive" in body:
        raise StructuralError("interactive key is forbidden in stage body; use communication")

    if "auto_run" in body:
        raise StructuralError("auto_run key is forbidden in stage body; use trigger: manual")

    if "buttons" in body:
        raise StructuralError("buttons key is forbidden in stage body; use notes in workflow.stages")

    if "reflect" in body:
        raise StructuralError("reflect key is forbidden in stage body; use reflect in workflow.stages")

    if "memory_use" in body:
        raise StructuralError("memory_use key is forbidden in stage body; use memory in workflow.stages")


def _validate_trigger(body: dict[str, Any]) -> str | None:
    """Return the effective ``trigger`` of ``body``, validating the closed value set.

    Args:
        body: The step body dict produced by ``parse_dsl`` (workflow path: a
            reconstructed deep copy, possibly already rewritten by the manual
            override pass).

    Returns:
        The effective trigger (``"on_success"``, ``"manual"``), or ``None``
        when the key is absent or carries a null value — validation gates on
        the VALUE, not key presence.

    Raises:
        StructuralError: When ``body`` carries a non-null ``trigger`` value
            outside ``on_success``/``manual`` (non-str values included).
    """
    effective_trigger = body.get("trigger")

    if effective_trigger is not None and effective_trigger not in ("on_success", "manual"):
        raise StructuralError("trigger must be one of: on_success, manual")
    return effective_trigger


def _apply_timeout_directive(body: dict[str, Any], stage_name: str, timeout_value: Any) -> None:
    """Validate the captured ``timeout`` directive and assign it verbatim to ``script_timeout``.

    Args:
        body: The REBUILT body dict (authoring keys already translated) —
            mutated in place by the assignment; the value overwrites a
            directly authored ``script_timeout`` (the translated value wins).
        stage_name: The stage id (used in the structural error messages — for
            loop-expanded copies this is ``NAME-i``).
        timeout_value: The captured ``timeout`` value from the original body;
            presence gates, so ``timeout: null`` counts as PRESENT (unlike
            ``trigger``). Passes verbatim — the Go duration grammar is NOT
            validated here (afm fails on a malformed string at runtime).

    Raises:
        StructuralError: When the value is not a string, or when the body
            carries no ``script`` key (``before_script``/``after_script`` do
            not open the directive).
    """
    if not isinstance(timeout_value, str):
        raise StructuralError(f"timeout must be a string in stage {stage_name}")

    if "script" not in body:
        raise StructuralError(f"timeout requires script in stage {stage_name}")
    body["script_timeout"] = timeout_value


def _assemble_buttons(source: dict[str, Any], notes: dict[str, str] | None) -> None:
    """Deep-copy the effective workflow notes into the output ``buttons`` field.

    Args:
        source: The REBUILT body dict (authoring keys already translated) —
            mutated in place by the assignment (the caller's fresh dict, never
            the caller's original parsed body).
        notes: The effective workflow notes instruction for the stage, or
            ``None`` when the workflow carries none. Deep-copied verbatim into
            ``buttons`` so ``FlowStage.fields`` never aliases
            ``WorkflowStage.notes``; ``None`` assembles no key at all.
    """
    if notes is not None:
        source["buttons"] = copy.deepcopy(notes)


def _assemble_memory_keys(source: dict[str, Any], memory_fields: dict[str, Any] | None) -> None:
    """Assign the stage's computed memory keys into the output fields dict.

    Args:
        source: The REBUILT body dict (authoring keys already translated) —
            mutated in place by the assignment (the caller's fresh dict, never
            the caller's original parsed body).
        memory_fields: The computed memory keys for this stage (a
            ``{"reflect": {...}}`` or ``{"memory_use": bool}`` map from
            ``_memory_emission``), or ``None``/empty when the stage carries
            none; the values are fresh per call, so a plain assignment needs
            no deep copy. ``None`` or empty assembles no key at all.
    """
    if memory_fields:
        source.update(memory_fields)


def _canonical_fields(
    body: dict[str, Any],
    stage_name: str,
    notes: dict[str, str] | None = None,
    memory_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reorder ``body`` into canonical key order, deep-copying each value; never mutates ``body``.

    Args:
        body: The step body dict produced by ``parse_dsl`` (workflow path: a
            reconstructed deep copy carrying the ``_APPROVE_SENTINEL``).
            Authoring keys are translated or consumed — ``roles`` → ``agents``
            (or the single ``["auto"]`` default), ``communication`` →
            ``interactive``, ``trigger: manual`` → ``auto_run: false``,
            ``timeout`` → ``script_timeout``, ``before_script``/``script``/
            ``after_script`` → ``script_before``/``script``/``script_after`` —
            and never reach the output as unknown keys; the sentinel is read
            (not popped) and dropped. In a body carrying ``script`` no
            ``agents`` key is assembled at all (afm rejects the combination).
        stage_name: The stage id (used in the mutual-exclusion error message —
            for loop-expanded copies this is ``NAME-i``).
        notes: The effective workflow notes instruction for this stage (a map
            of note name → prompt text, already resolved by base name so
            loop-expanded copies share it), or ``None`` when the workflow
            carries none. Read-only input — deep-copied into the assembled
            ``buttons`` field, never threaded into ``body``.
        memory_fields: The computed memory keys for this stage (a
            ``{"reflect": {"file": ..., "mode": ...}}`` map under the reflect
            method, or a ``{"memory_use": bool}`` map under alignment, already
            resolved by final id so loop-expanded copies share them), or
            ``None``/empty when the stage carries none. Read-only input —
            assigned into the assembled fields by ``_assemble_memory_keys``,
            never threaded into ``body``.

    Returns:
        A new dict in canonical key order with deep-copied values — known keys
        in ``_CANONICAL_KEY_ORDER`` order, remaining keys appended
        alphabetically. ``auto_approve`` is emitted only under a roles-effect
        approve directive (``auto``/``dialog``) with ``planner`` in the raw
        roles; ``auto_run`` (always ``False``) only for an effective
        ``trigger: manual``; ``buttons``/memory keys only from their function
        arguments.

    Raises:
        StructuralError: If ``body`` carries the legacy ``agents`` key — the
            authoring-side field is ``roles``; ``agents`` is output-only. Or if
            ``body`` carries an authoring ``interactive`` key — the authoring-side
            field is ``communication``; ``interactive`` is output-only. Or if
            ``body`` carries an authoring ``auto_run`` key — the authoring-side
            field for the launch mode is ``trigger``; ``auto_run`` is
            output-only. Or if ``body`` carries an authoring ``buttons`` key —
            buttons are authored ONLY through the workflow ``notes``
            instruction; ``buttons`` is output-only. Or if ``body`` carries an
            authoring ``reflect``/``memory_use`` key — the memory stage keys are
            authored ONLY through the workflow memory instructions;
            both are output-only. Or if ``body`` carries a
            ``trigger`` value outside the
            closed set ``on_success``/``manual`` (a ``None`` value counts as
            absent). Or if
            ``body`` carries ``script`` together with ``prompt`` and/or ``skills``
            — they are mutually exclusive. Or if ``body`` carries a present
            non-string ``timeout`` value, or a ``timeout`` without ``script``
            in the same body (``script_timeout`` scopes to the script action).
    """
    _reject_authoring_output_keys(body)

    # Read the approve sentinel (output-only plumbing) WITHOUT mutating ``body``
    # — reading (not popping) keeps this function non-mutating on every path.
    # The sentinel is threaded in by ``_apply_per_stage_overrides`` on the
    # workflow path (where ``body`` is a deep copy); it is dropped from the fresh
    # dict built below so it never reaches the output. Absent ⇒ ``None`` (the
    # non-workflow path carries no sentinel).
    effective_approve = body.get(_APPROVE_SENTINEL)

    # Read and validate the stage trigger directive WITHOUT mutating ``body``
    # (see ``_validate_trigger`` — a null value counts as absent).
    effective_trigger = _validate_trigger(body)

    # Capture the raw roles list BEFORE translation — the auto_approve effect
    # matches the authored role "planner", not its translated stem "planning".
    raw_roles = body.get("roles")

    # Capture the timeout directive BEFORE the rebuild — the authoring key is
    # consumed by its translation below, so its presence/value must be read
    # from the ORIGINAL body. Presence gates (``has_timeout``), not truthiness:
    # ``timeout: null`` is a PRESENT non-string and raises (unlike ``trigger``,
    # whose null counts as absent), and ``timeout: ""`` is a valid present string.
    has_timeout = "timeout" in body
    timeout_value = body.get("timeout")

    # Translate the authoring script directives into their output keys (the
    # authoring keys are consumed, never passed through as unknown keys) and drop
    # the approve sentinel and the authoring ``trigger``/``timeout`` keys — all
    # consumed by their translations, so none ever reaches the output. A fresh
    # dict is built rather than mutating ``body`` in place.
    body = {
        ("script_before" if key == "before_script" else "script_after" if key == "after_script" else key): value
        for key, value in body.items()
        if key not in (_APPROVE_SENTINEL, "trigger", "timeout")
    }

    # ``script`` is mutually exclusive with ``prompt`` and ``skills``;
    # ``before_script``/``after_script`` are compatible (checked against the
    # translated ``script`` key, so it fires whether ``script`` was authored
    # directly or — it cannot be — derived).
    if "script" in body and ("prompt" in body or "skills" in body):
        raise StructuralError(f"script is mutually exclusive with prompt/skills in stage {stage_name}")

    # The stage timeout directive — validated and translated by the same pass
    # as script exclusivity (non-string → requires-script → assign; see
    # ``_apply_timeout_directive``). ``script_timeout`` scopes to the script
    # action: only ``script`` opens the directive. The value passes verbatim
    # (the Go duration grammar belongs to afm at runtime) and the assignment
    # overwrites a directly authored ``script_timeout`` (translated wins).
    if has_timeout:
        _apply_timeout_directive(body, stage_name, timeout_value)

    if "communication" in body:
        # Translate the authoring ``communication`` key into the output
        # ``interactive`` slot BEFORE ``_inject_defaults`` / reordering, so the
        # canonical slot is ``interactive`` (afm-stable). Under an approve
        # directive that drives the communication effect (``auto``/``plan``) +
        # ``communication: true`` the key is SUPPRESSED (omitted) instead —
        # suppress means omission, NOT ``interactive: false``. A fresh dict is
        # built rather than mutating ``body`` in place.
        suppress = effective_approve in _APPROVE_SUPPRESS_INTERACTIVE and body["communication"] is True
        if suppress:
            body = {key: value for key, value in body.items() if key != "communication"}
        else:
            body = {("interactive" if key == "communication" else key): value for key, value in body.items()}

    # A body carrying ``script`` assembles NO ``agents`` key — afm rejects the
    # combination. The suppression covers BOTH the default ``["auto"]``
    # injection AND the translated ``roles`` value (authored ``roles`` with
    # ``script`` is legal; the agents slot is simply not emitted).
    source = _inject_defaults(body, suppress_agents="script" in body)

    # Workflow notes instruction → the output ``buttons`` field (single
    # authoring source). The notes map arrives as a function argument — never
    # threaded through the body (the authoring-buttons prohibition above would
    # trip on a body ``buttons`` key) — and is deep-copied into the assembled
    # fields by ``_assemble_buttons`` (see its docstring for the no-aliasing
    # rationale). The ``notes`` argument itself is read-only input; this
    # function stays non-mutating.
    _assemble_buttons(source, notes)

    # Computed stage memory keys (step 4.9). The memory value travels as a
    # function argument — never threaded through the body (the authoring
    # prohibition above would trip on a body ``reflect``/``memory_use`` key) —
    # and is assigned by ``_assemble_memory_keys`` BEFORE the canonical-order
    # loop so both keys land in their canonical slots after ``script_timeout``.
    _assemble_memory_keys(source, memory_fields)

    # An approve directive that drives the roles effect (``auto``/``dialog``) +
    # ``planner`` in the raw roles ⇒ emit ``auto_approve: true`` (canonical slot
    # right after ``interactive``). The two approve effects are independent:
    # each fires on its own trigger and its own directive subset.
    has_planner = isinstance(raw_roles, list) and "planner" in raw_roles
    if effective_approve in _APPROVE_EMIT_AUTO_APPROVE and has_planner:
        source["auto_approve"] = True

    # A body whose effective trigger is ``manual`` assembles ``auto_run: false``
    # — the canonical loop slots it immediately after ``auto_approve``. A body
    # with ``trigger: on_success`` (or no trigger) assembles NO ``auto_run`` key;
    # ``auto_run: true`` is never emitted on any path.
    if effective_trigger == "manual":
        source["auto_run"] = False

    ordered: dict[str, Any] = {}
    for key in _CANONICAL_KEY_ORDER:
        if key in source:
            ordered[key] = copy.deepcopy(source[key])
    extras = sorted(k for k in source if k not in _CANONICAL_KEY_ORDER)
    for key in extras:
        ordered[key] = copy.deepcopy(source[key])
    return ordered


def _effective_overrides(workflow: WorkflowDocument) -> dict[str, WorkflowStage]:
    """Resolve the per-stage effective override map (inline extend → stages overlay).

    Args:
        workflow: The declarative workflow instructions.

    Returns:
        The effective per-stage override map keyed by stage name. Extend-seeded
        entries carry only ``agent``/``loop``/``approve`` (``manual``,
        ``notes``, ``reflect``, and ``memory`` stay ``None``); stages-block
        entries carry their full ``WorkflowStage``; merged entries combine them
        per-field (a stages-block value wins whenever its field is not
        ``None``), always carrying the stages-block ``manual``, ``notes``,
        ``reflect``, and ``memory``.
    """
    effective: dict[str, WorkflowStage] = {}

    for name, ext in workflow.extend.items():
        # Extend-seeded default: only the inline fields an extend-entry can
        # carry. ``manual``/``notes``/``reflect``/``memory`` stay ``None`` (the
        # constructor defaults) — all four are stages-block-only
        # (``parse_workflow`` rejects them in an extend-entry).
        effective[name] = WorkflowStage(agent=ext.agent, loop=ext.loop, approve=ext.approve)

    for name, stg in workflow.stages.items():
        base = effective.get(name)
        if base is None:
            # Explicit stages-block with no inline fallback — use it verbatim.
            effective[name] = stg
            continue
        # Per-field overlay: stages-block wins whenever its field is not None.
        # ``manual``, ``notes``, ``reflect``, and ``memory`` are passed
        # explicitly — the extend seed carries none of them, and the
        # constructor default (None) would silently drop the instruction.
        effective[name] = WorkflowStage(
            agent=stg.agent if stg.agent is not None else base.agent,
            prompt=stg.prompt,
            loop=stg.loop if stg.loop is not None else base.loop,
            skills=stg.skills,
            approve=stg.approve if stg.approve is not None else base.approve,
            manual=stg.manual,
            notes=stg.notes,
            reflect=stg.reflect,
            memory=stg.memory,
        )

    return effective


def _effective_notes_by_id(
    effective: dict[str, WorkflowStage],
    expanded_ids: dict[str, list[str]],
) -> dict[str, dict[str, str] | None]:
    """Resolve the effective notes for every FINAL step id (base name → copies).

    Args:
        effective: The resolved per-stage override map (from
            ``_effective_overrides``), keyed by stage name.
        expanded_ids: The base-name → produced-ids map from ``_expand_loops``
            (every final id appears in exactly one produced-ids list).

    Returns:
        The final-id → effective-notes map — each base name's effective notes
        copied onto every id it produced, so loop-expanded copies stay uniform.
        A name absent from ``effective`` (or carrying ``notes=None``) maps to
        ``None`` — no buttons key.
    """
    notes_by_id: dict[str, dict[str, str] | None] = {}

    for base_name, produced_ids in expanded_ids.items():
        stage = effective.get(base_name)
        notes = stage.notes if stage is not None else None

        for produced_id in produced_ids:
            notes_by_id[produced_id] = notes

    return notes_by_id


@dataclass(kw_only=True)
class _MemoryEmission:
    """The step-4.9 result — the memory block plus the per-stage memory keys.

    Args:
        block: The compiled memory block, or ``None`` when memory does not
            participate (the block is emitted if and only if participation
            exists).
        keys_by_id: The final-id → memory-keys map consumed per step by
            ``_canonical_fields`` — ``{"reflect": {"file": ..., "mode": ...}}``
            on participating ids under the reflect method,
            ``{"memory_use": bool}`` on every id under alignment.
    """

    block: FlowMemory | None
    keys_by_id: dict[str, dict[str, Any]]


def _memory_emission(
    workflow: WorkflowDocument | None,
    effective: dict[str, WorkflowStage],
    expanded_ids: dict[str, list[str]],
) -> _MemoryEmission:
    """Step 4.9 — compute the memory block and the per-stage memory keys.

    Args:
        workflow: The declarative workflow instructions, or ``None`` when no
            workflow is applied (no block, no keys — byte-identical output).
            The effective memory configuration is the workflow's ``memory``
            block, else a default-constructed ``WorkflowMemory()`` whose
            field defaults are the materialized authoring defaults.
        effective: The resolved per-stage override map (from
            ``_effective_overrides``), keyed by stage name. Read-only input.
        expanded_ids: The base-name → produced-ids map from ``_expand_loops``
            over the working body (every final id appears in exactly one
            produced-ids list). Read-only input.

    Returns:
        The ``_MemoryEmission`` — the block (or ``None``) and the final-id →
        memory-keys map. The block is emitted if and only if at least one
        stage participates (a ``reflect`` instruction under the reflect
        method, a true ``memory`` instruction under alignment, counted over
        the working body); otherwise the emission is a silent no-op. The
        block composes ``_MEMORY_ROOT`` with the authored suffix (``mode``
        fixed ``"r"`` under reflect, the materialized authored value under
        alignment; ``memory_use`` always ``False``). Keys: reflect —
        ``{"reflect": {file, mode}}`` on participating ids; alignment —
        ``{"memory_use": bool}`` on every id (an explicit ``False`` on
        non-participants). The goga-side method selector never reaches any
        output.
    """
    if workflow is None:
        return _MemoryEmission(block=None, keys_by_id={})

    config = workflow.memory if workflow.memory is not None else WorkflowMemory()
    method = config.method

    participating_ids: set[str] = set()

    for base_name, produced_ids in expanded_ids.items():
        stage = effective.get(base_name)
        instr_reflect = stage.reflect if stage is not None else None
        instr_memory = (stage.memory is True) if stage is not None else False
        participates = (instr_reflect is not None) if method == "reflect" else instr_memory

        if participates:
            participating_ids.update(produced_ids)

    if not participating_ids:
        return _MemoryEmission(block=None, keys_by_id={})

    path = _MEMORY_ROOT if config.path is None else f"{_MEMORY_ROOT}/{config.path}"
    block = FlowMemory(
        path=path,
        mode=("r" if method == "reflect" else config.mode),
        memory_use=False,
        max_rules=config.max_rules,
        commit=config.commit,
    )

    keys_by_id: dict[str, dict[str, Any]] = {}

    for base_name, produced_ids in expanded_ids.items():
        for produced_id in produced_ids:
            if method == "alignment":
                keys_by_id[produced_id] = {"memory_use": produced_id in participating_ids}
            elif produced_id in participating_ids:
                reflect = effective[base_name].reflect
                keys_by_id[produced_id] = {"reflect": {"file": reflect.file, "mode": reflect.mode}}

    return _MemoryEmission(block=block, keys_by_id=keys_by_id)


def _merge_skills(
    pipeline_skills: list[str] | None,
    workflow_skills: list[str] | None,
) -> list[str] | None:
    """Merge pipeline-file and workflow-stage skills, deduplicating by value.

    Args:
        pipeline_skills: The stage's pipeline-file ``skills`` value, or
            ``None``; a non-list value (the verbatim-parsed body may carry any
            type) is treated as empty.
        workflow_skills: The workflow-stage ``skills`` override (always a
            ``list[str]`` or ``None``), or ``None``.

    Returns:
        The merged deduplicated list — pipeline-file skills first (source
        order), then workflow skills, first occurrence kept — or ``None``
        when both inputs are empty (the absence marker that keeps an absent
        ``skills`` key absent).
    """
    pipeline_list = pipeline_skills if isinstance(pipeline_skills, list) else []
    merged: list[str] = []
    seen: set[str] = set()

    for skill in pipeline_list + (workflow_skills or []):
        # Only ``str`` skills are kept; a verbatim pipeline-file ``skills`` list may
        # otherwise carry unhashable (dict/list) or non-str elements, which would
        # raise ``TypeError`` on ``skill not in seen`` or pollute the ``list[str]``
        # result. ``workflow_skills`` is always ``list[str]`` (validated upstream).
        if isinstance(skill, str) and skill not in seen:
            seen.add(skill)
            merged.append(skill)

    return merged if merged else None


def _apply_per_stage_overrides(
    steps: list[PhaseStep | StageStep],
    effective: dict[str, WorkflowStage],
) -> None:
    """Inject per-stage agent/prompt/skills/approve overrides into the matching step bodies.

    Args:
        steps: The working (deep-copied) step sequence to mutate in place.
        effective: The resolved per-stage override map (from
            ``_effective_overrides``), keyed by stage name; a not-found name
            is a silent skip (a stage removed at 4skip — 4pre already
            rejected unknown names). The ``approve`` directive is threaded
            under ``_APPROVE_SENTINEL`` (read and dropped in
            ``_canonical_fields``; a ``None`` sentinel means no directive),
            and the tri-state ``manual`` rewrites the working ``trigger`` —
            ``True`` forces manual, ``False`` cancels it, ``None`` leaves it.

    Raises:
        StructuralError: When a ``manual: false`` entry targets a stage whose
            working body carries no ``trigger: manual`` (nothing to cancel).
    """
    steps_by_name = {step.name: step for step in steps}

    for name, stage in effective.items():
        step = steps_by_name.get(name)
        if step is None:
            # A not-found can only be a stage removed at 4skip (4pre already
            # rejected unknown ``workflow.stages`` names before this pass) — a
            # silent, intentional skip. No warning.
            continue
        if stage.agent is not None:
            step.body["command"] = _WRAPPER_PATH_TEMPLATE.format(agent=stage.agent)
        if stage.prompt is not None:
            step.body["description"] = stage.prompt

        if stage.skills is not None:
            merged = _merge_skills(step.body.get("skills"), stage.skills)
            if merged is not None:
                step.body["skills"] = merged

        # Thread the effective approve directive into the step body under the
        # sentinel key. Writing ``None`` is harmless and keeps the contract
        # simple (the sentinel always reflects the resolved directive). It never
        # reaches the output — read and dropped in ``_canonical_fields``.
        step.body[_APPROVE_SENTINEL] = stage.approve

        # Tri-state manual-launch instruction (4a manual). The rewrite targets
        # this WORKING body copy only — the original parsed body and the
        # ``PipelineDocument`` mirror stay untouched. ``True`` forces the manual
        # state over any authored trigger (idempotent on an already-manual
        # stage); ``False`` cancels a manual state from either body source
        # (pipeline-file OR extend body) or is an error when there is nothing to
        # cancel; ``None`` (no instruction) leaves the authored trigger alone.
        if stage.manual is True:
            step.body["trigger"] = "manual"
        elif stage.manual is False:
            if step.body.get("trigger") == "manual":
                step.body["trigger"] = "on_success"
            else:
                raise StructuralError(f"manual: false on non-manual stage {name}")


def _make_expanded_copy(
    step: PhaseStep | StageStep,
    new_id: str,
    index: int,
    fmt: BodyFormat,
) -> PhaseStep | StageStep:
    """Build one loop-expanded copy of ``step`` carrying the id ``new_id``.

    Args:
        step: The (override-applied) base step being expanded.
        new_id: The id for this copy (``NAME-<index>``).
        index: 1-based position within the expanded group.
        fmt: The body format — selects ``PhaseStep`` vs ``StageStep``.

    Returns:
        A new step instance for the expanded copy (body deep-copied, so copies
        never alias one another or the base step). PHASES copies carry no
        ``depends_on`` (position derives it later); STAGES copies carry the
        original external ``depends_on`` on the first copy and a chain
        reference to the previous copy (``NAME-(index-1)``) on every
        subsequent copy.

    Raises:
        TypeError: When a STAGES expansion receives a non-``StageStep`` (an
            internal invariant breach, not a recoverable state).
    """
    body = copy.deepcopy(step.body)

    if fmt is BodyFormat.PHASES:
        return PhaseStep(name=new_id, title=step.title, body=body)

    # STAGES: first copy inherits the original external depends_on (rewritten in
    # 5c); later copies chain to the previous copy by id.
    if index == 1:
        # A real guard, not an ``assert``: the type must hold in optimized runs
        # (``python -O``) too — a non-StageStep here is an internal invariant
        # breach, not a recoverable state.
        if not isinstance(step, StageStep):
            raise TypeError(f"expected StageStep in STAGES expansion, got {type(step).__name__}")
        depends_on = copy.deepcopy(step.depends_on)
    else:
        depends_on = [f"{step.name}-{index - 1}"]

    return StageStep(name=new_id, title=step.title, depends_on=depends_on, body=body)


def _expand_loops(
    steps: list[PhaseStep | StageStep],
    fmt: BodyFormat,
    effective: dict[str, WorkflowStage],
) -> tuple[list[PhaseStep | StageStep], dict[str, list[str]]]:
    """Expand looped stages into N chained copies, preserving source order.

    Args:
        steps: The override-applied working step sequence.
        fmt: The body format — selects the expanded step type.
        effective: The resolved per-stage override map (from
            ``_effective_overrides``), source of loop counts (an unset
            override means a count of ``1``).

    Returns:
        The new ordered step list and the base-name → produced-ids map. A step
        with a count of ``1`` passes through unchanged and maps to
        ``[base-name]``; a count ``>= 2`` expands into ``NAME-1``..``NAME-N``
        copies (built via ``_make_expanded_copy``) mapping to those ids.
    """
    expanded: list[PhaseStep | StageStep] = []
    expanded_ids: dict[str, list[str]] = {}

    for step in steps:
        loop_count = 1
        eff = effective.get(step.name)

        if eff is not None and eff.loop is not None:
            loop_count = eff.loop
        if loop_count < _LOOP_EXPANSION_THRESHOLD:
            expanded.append(step)
            expanded_ids[step.name] = [step.name]
            continue

        ids = [f"{step.name}-{i}" for i in range(1, loop_count + 1)]

        for index, new_id in enumerate(ids, start=1):
            expanded.append(_make_expanded_copy(step, new_id, index, fmt))

        expanded_ids[step.name] = ids

    return expanded, expanded_ids


def _rewrite_external_depends_on(
    steps: list[StageStep],
    expanded_ids: dict[str, list[str]],
) -> None:
    """Rewrite external depends_on refs to the LAST expanded id (STAGES only).

    Args:
        steps: The loop-expanded STAGES sequence to rewrite in place.
        expanded_ids: The base-name → produced-ids map from ``_expand_loops``;
            a ref to a base with multiple produced ids is replaced with its
            LAST id, every other ref is kept as-is (unmatched refs surface in
            afm as dangling).
    """
    for step in steps:
        if step.depends_on is None:
            continue

        rewritten: list[str] = []

        for ref in step.depends_on:
            produced = expanded_ids.get(ref)

            if produced is not None and len(produced) >= _LOOP_EXPANSION_THRESHOLD:
                rewritten.append(produced[-1])
            else:
                rewritten.append(ref)

        step.depends_on = rewritten


# Extend-step keys carried as a separate field or dropped, never inside the
# verbatim body handed to ``FlowStage.fields``. ``title`` becomes the step's
# display label (falling back to the extend name); ``name`` and ``id`` are
# serializer-reserved identity keys — the id derives from the extend map key and
# the display name from the resolved title. An authored ``name``/``id`` would
# otherwise survive into ``FlowStage.fields`` and clobber the serializer's seeded
# ``name``/``id`` (``_build_stage_repr`` sets them first, then iterates fields),
# silently corrupting the flow-file. Mirrors ``parse_dsl._STAGE_STEP_KEYS`` /
# ``_PHASE_STEP_KEYS`` for original stages.
_EXTEND_STEP_RESERVED_KEYS = frozenset({"title", "name", "id"})


def _extend_step_title_and_body(
    name: str,
    ext: WorkflowExtendStage,
) -> tuple[str, dict[str, Any]]:
    """Return the ``(title, body)`` for one extend-stage step.

    Args:
        name: The extend-stage name (map key in ``workflow.extend``).
        ext: The extend-stage declaration.

    Returns:
        The resolved display title (falling back to the extend-stage name) and
        a deep-copied body without the serializer-reserved identity keys
        ``title``/``name``/``id`` (see ``_EXTEND_STEP_RESERVED_KEYS``) — so
        the embedded step never aliases the workflow's declarative body and
        the serializer's seeded identity stays intact.
    """
    title = ext.body.get("title", name)
    body_for_step = {
        key: copy.deepcopy(value) for key, value in ext.body.items() if key not in _EXTEND_STEP_RESERVED_KEYS
    }
    return title, body_for_step


def _embed_extend_stages_stages(
    steps: list[StageStep],
    workflow: WorkflowDocument,
) -> None:
    """STAGES branch — embed extend-stages by deriving ``depends_on`` from ``after``/``before`` refs.

    Args:
        steps: The working (deep-copied) STAGES step sequence, mutated in place.
        workflow: The declarative workflow instructions (source of extend-entries).
    """
    for name, ext in workflow.extend.items():
        title, body_for_step = _extend_step_title_and_body(name, ext)
        depends_on = list(ext.after) if ext.after is not None else None
        steps.append(
            StageStep(name=name, title=title, depends_on=depends_on, body=body_for_step),
        )

    by_name = {step.name: step for step in steps}

    for name, ext in workflow.extend.items():
        for bname in ext.before or []:
            # 4a0-pre (``_strict_validate_extend_refs``) guarantees every
            # before-ref resolves to a step in ``by_name`` — a missing key here
            # would be an internal invariant breach, not a recoverable state.
            target = by_name[bname]

            if target.depends_on is None:
                target.depends_on = []
            if name not in target.depends_on:
                target.depends_on.append(name)


def _resolve_phases_insert_index(
    name: str,
    after_positions: list[int],
    before_positions: list[int],
    len_steps: int,
) -> tuple[int, bool]:
    """Resolve the PHASES insertion index for one extend-stage.

    Args:
        name: The extend-stage name (used in WARNING messages).
        after_positions: Sorted positions of resolvable ``after``-targets.
        before_positions: Sorted positions of resolvable ``before``-targets.
        len_steps: Current ``len(steps)`` — the append index when nothing
            resolves.

    Returns:
        The insertion index and whether the position is before-anchored.
        ``idx`` sits immediately after the LAST resolvable ``after``-target
        (preferred when both resolve consistently), or immediately before the
        FIRST resolvable ``before``-target, or at ``len_steps`` (append) when
        none resolve; ``before_anchored`` is ``True`` only for a sole
        ``before`` (no ``after``). A WARNING is logged on the inconsistent and
        unresolvable fall-backs.
    """
    after_index = (max(after_positions) + 1) if after_positions else None
    before_index = min(before_positions) if before_positions else None

    if after_index is not None and before_index is not None:
        if after_index > before_index:
            logger.warning(
                "compile_flow: extend after/before inconsistent; using after",
                extra={"extend_stage": name},
            )
        return after_index, False
    if after_index is not None:
        return after_index, False
    if before_index is not None:
        return before_index, True

    logger.warning(
        "compile_flow: extend has no resolvable position; appending at end",
        extra={"extend_stage": name},
    )
    return len_steps, False


def _embed_extend_stages_phases(
    steps: list[PhaseStep],
    workflow: WorkflowDocument,
    known_names: set[str],
) -> None:
    """PHASES branch — embed extend-stages by positional insertion (siblings sharing an anchor stack in authored order).

    Args:
        steps: The working (deep-copied) PHASES step sequence, mutated in place.
        workflow: The declarative workflow instructions (source of extend-entries).
        known_names: Union of original step names and extend-stage names; targets
            outside this set are treated as dangling.
    """
    pending: list[tuple[str, WorkflowExtendStage]] = list(workflow.extend.items())

    while pending:
        placed_names = {step.name for step in steps}
        next_pending: list[tuple[str, WorkflowExtendStage]] = []
        progress = False
        # Two after-anchored stages sharing a target both compute the same
        # ``after_index`` (the target's index never moves, even as siblings
        # insert after it), so the second ``steps.insert(idx, ...)`` would shift
        # the first sibling right and reverse authored order. Offset each
        # after-anchored insertion by how many already landed at that index this
        # iteration so they stack in author order. ``before``-anchored insertions
        # are exempt — their target shifts forward on each insert, advancing the
        # index naturally (see ``test_compile_flow_phases_extend_same_anchor_preserves_author_order``).
        after_inserts_at_index: dict[int, int] = {}

        for name, ext in pending:
            after_targets = ext.after or []
            before_targets = ext.before or []
            # Defer when any target is an extend-stage that is not yet placed.
            if any(t in known_names and t not in placed_names for t in after_targets + before_targets):
                next_pending.append((name, ext))
                continue
            after_positions = [
                i for i, step in enumerate(steps) if step.name in after_targets and step.name in known_names
            ]
            before_positions = [
                i for i, step in enumerate(steps) if step.name in before_targets and step.name in known_names
            ]
            idx, before_anchored = _resolve_phases_insert_index(name, after_positions, before_positions, len(steps))
            if not before_anchored:
                # Offset by prior same-iteration insertions at this computed
                # index (keyed by the pre-offset index) before recording this one.
                offset = after_inserts_at_index.get(idx, 0)
                after_inserts_at_index[idx] = offset + 1
                idx += offset
            title, body_for_step = _extend_step_title_and_body(name, ext)
            steps.insert(idx, PhaseStep(name=name, title=title, body=body_for_step))
            progress = True

        pending = next_pending

        if not progress:
            for name, ext in pending:
                logger.warning(
                    "compile_flow: extend unresolved cycle; appending at end",
                    extra={"extend_stage": name},
                )
                title, body_for_step = _extend_step_title_and_body(name, ext)
                steps.append(PhaseStep(name=name, title=title, body=body_for_step))
            break


def _embed_extend_stages(
    steps: list[PhaseStep | StageStep],
    workflow: WorkflowDocument,
    fmt: BodyFormat,
) -> None:
    """Step 4a0 — embed ``workflow.extend`` stages into the working step sequence.

    Args:
        steps: The working (deep-copied) step sequence, mutated in place. Called
            after the deep-copy in ``_reconstruct_body`` and before the 4a
            override pass — so extend-stages receive overrides, loops, and
            external-ref rewrites too.
        workflow: The declarative workflow instructions (source of extend-entries).
        fmt: The body format — selects the STAGES vs PHASES embedding branch.
    """
    if not workflow.extend:
        return

    known_names = {step.name for step in steps} | set(workflow.extend)

    if fmt is BodyFormat.STAGES:
        _embed_extend_stages_stages(steps, workflow)
    else:
        _embed_extend_stages_phases(steps, workflow, known_names)


def _strict_validate_extend_refs(
    steps: list[PhaseStep | StageStep],
    workflow: WorkflowDocument,
) -> None:
    """Step 4a0-pre — strictly validate every ``workflow.extend.<name>.before/.after`` ref.

    Args:
        steps: The working step sequence BEFORE the 4a0 embed (deep-copied
            ORIGINAL body only); a ref to a stage later removed at 4skip is
            NOT flagged here (it still exists in the original body).
        workflow: The declarative workflow instructions (source of the extend
            names and their ``before``/``after`` refs).

    Raises:
        StructuralError: When a ``workflow.extend.<name>.before`` or ``.after``
            ref names no ORIGINAL step and no extend-stage. Existence only —
            cycles, self-references, and duplicate refs remain afm's
            responsibility.
    """
    valid_names = {step.name for step in steps} | set(workflow.extend)
    for name, ext in workflow.extend.items():
        for ref in ext.before or []:
            if ref not in valid_names:
                raise StructuralError(f"unknown stage name in workflow.extend.{name}.before: {ref}")
        for ref in ext.after or []:
            if ref not in valid_names:
                raise StructuralError(f"unknown stage name in workflow.extend.{name}.after: {ref}")


def _strict_validate_stage_names(
    steps: list[PhaseStep | StageStep],
    workflow: WorkflowDocument,
) -> None:
    """Step 4pre — strictly validate every ``workflow.stages`` name against the body.

    Args:
        steps: The working step sequence after 4a0 (deep-copied ORIGINAL +
            embedded extend-stages); a genuinely-existing stage that is also
            skipped is NOT flagged here (removed later at 4skip).
        workflow: The declarative workflow instructions (source of the
            ``workflow.stages`` names to validate).

    Raises:
        StructuralError: When a ``workflow.stages`` name matches no step name in
            ``steps``.
    """
    valid_names = {step.name for step in steps}
    for name in workflow.stages:
        if name not in valid_names:
            raise StructuralError(f"unknown stage name in workflow.stages: {name}")


def _resolve_skip(
    name: str,
    steps_by_name: dict[str, StageStep],
    skipped_names: set[str],
    _seen: set[str] | None = None,
) -> list[str]:
    """Resolve a skipped stage name to its transitive non-skipped predecessors.

    Args:
        name: The skipped stage name to resolve.
        steps_by_name: Name → step index over the working STAGES sequence
            (includes skipped steps, used as the source of ``depends_on``).
        skipped_names: The set of skipped names to recurse through.
        _seen: The visited set for cycle termination, threaded across the
            recursion. Callers omit it; it defaults to a fresh set on the first
            frame.

    Returns:
        The list of non-skipped predecessors in source order (NOT deduplicated —
        the caller dedups preserving first-occurrence order; a skipped stage
        with no ``depends_on`` or a missing step resolves to ``[]``).
    """
    if _seen is None:
        _seen = set()

    if name in _seen:
        return []
    _seen.add(name)

    step = steps_by_name.get(name)
    if step is None:
        return []

    result: list[str] = []
    for ref in step.depends_on or []:
        if ref in skipped_names:
            result.extend(_resolve_skip(ref, steps_by_name, skipped_names, _seen))
        else:
            result.append(ref)
    return result


def _reconnect_stages_depends_on(
    steps: list[StageStep],
    steps_by_name: dict[str, StageStep],
    skipped_names: set[str],
) -> None:
    """STAGES sub-trace of 4skip — reconnect dependents of skipped stages.

    Args:
        steps: The working STAGES step sequence, mutated in place; a
            fully-collapsed ``depends_on`` is written as an explicit ``[]``.
            Skipped steps are still present here — they are only read (as the
            source of ``depends_on``), never rewritten.
        steps_by_name: Name → step index over ``steps`` (includes skipped steps).
        skipped_names: The set of names to remove and reconnect around.
    """
    for step in steps:
        if step.name in skipped_names or step.depends_on is None:
            continue

        rewritten: list[str] = []
        seen: set[str] = set()
        for ref in step.depends_on:
            resolved = _resolve_skip(ref, steps_by_name, skipped_names) if ref in skipped_names else [ref]
            for resolved_ref in resolved:
                if resolved_ref != step.name and resolved_ref not in seen:
                    seen.add(resolved_ref)
                    rewritten.append(resolved_ref)
        step.depends_on = rewritten


def _remove_skipped_stages(
    steps: list[PhaseStep | StageStep],
    workflow: WorkflowDocument,
    fmt: BodyFormat,
) -> None:
    """Step 4skip — remove skipped stages and transparently reconnect dependents.

    Args:
        steps: The working step sequence after the 4a0 embed and 4pre validation,
            mutated in place. Runs BEFORE the 4a override pass, so skip wins
            over every override; the empty-body case (every stage skipped) is
            the caller's guard.
        workflow: The declarative workflow instructions (source of skip flags).
        fmt: The body format — selects the STAGES reconnect branch vs the PHASES
            positional drop.
    """
    skipped_names = {name for name, stage in workflow.stages.items() if stage.skip}
    if not skipped_names:
        return

    if fmt is BodyFormat.STAGES:
        steps_by_name = {step.name: step for step in steps}
        _reconnect_stages_depends_on(steps, steps_by_name, skipped_names)

    steps[:] = [step for step in steps if step.name not in skipped_names]


def _reconstruct_body(
    fmt: BodyFormat,
    body: PhasesBody | StagesBody,
    workflow: WorkflowDocument,
) -> tuple[list[PhaseStep | StageStep], dict[str, dict[str, str] | None], _MemoryEmission]:
    """Apply the workflow reconstruction branch, returning a NEW step sequence.

    Args:
        fmt: The body format — PHASES or STAGES.
        body: The ORIGINAL parsed body (never mutated here — the sequence is
            deep-copied first).
        workflow: The declarative workflow instructions.

    Returns:
        The reconstructed step sequence (PHASES or STAGES steps), the
        final-id → effective-notes map, and the ``_MemoryEmission`` (the
        compiled memory block plus the final-id → memory-keys map). Both maps
        travel as separate values — never threaded into the step bodies — and
        are consumed per step by ``_canonical_fields`` (loop-expanded copies
        resolve through their base name, keeping the keys uniform across
        copies).

    Raises:
        StructuralError: When a ``workflow.extend.<name>.before/.after`` ref
            matches no step name (4a1), when a ``workflow.stages`` name matches
            no step name (4pre), or when every step is skipped (post-4skip
            empty-body guard).
    """
    steps: list[PhaseStep | StageStep] = [copy.deepcopy(step) for step in body.steps]
    _strict_validate_extend_refs(steps, workflow)
    _embed_extend_stages(steps, workflow, fmt)
    _strict_validate_stage_names(steps, workflow)
    _remove_skipped_stages(steps, workflow, fmt)
    if not steps:
        raise StructuralError("empty body")
    effective = _effective_overrides(workflow)
    _apply_per_stage_overrides(steps, effective)
    expanded, expanded_ids = _expand_loops(steps, fmt, effective)

    if fmt is BodyFormat.STAGES:
        _rewrite_external_depends_on(expanded, expanded_ids)

    return (
        expanded,
        _effective_notes_by_id(effective, expanded_ids),
        _memory_emission(workflow, effective, expanded_ids),
    )


def compile_flow(
    pipeline_path: Path,
    flow_path: Path,
    workflow: WorkflowDocument | None = None,
    root_dir: str | None = None,
    project_name: str | None = None,
) -> tuple[PipelineDocument, FlowDocument]:
    """Compile a goga DSL pipeline-file into an afm flow-file, write it to ``flow_path``, and return both documents.

    Args:
        pipeline_path: Absolute path to the input goga DSL pipeline-file. The file
            must be readable and contain a ``---`` separator line.
        flow_path: Absolute path to the output afm flow-file. The parent directory
            must already exist; it is not created here.
        workflow: Optional ``WorkflowDocument`` carrying declarative instructions
            for extending the pipeline (top-level prompt, per-stage
            agent/prompt/loop overrides). When ``None`` no workflow is applied;
            otherwise the parsed body is reconstructed on a deep copy before
            the ``FlowStage`` assembly.
        root_dir: Optional top-level afm ``root_dir`` directive emitted after
            ``prompt`` (when present) and before ``name``. When ``None`` the key
            is omitted entirely (back-compat). The caller computes the value
            (typically the in-container project root via ``Path.cwd()``); the
            compiler itself performs no environment-variable reads.
        project_name: Optional project name that prefixes the output
            ``FlowDocument.description`` as ``f"[{project_name}] {header.description}"``
            when not ``None``. The ``PipelineDocument`` mirror keeps the
            unprefixed header description (OUTPUT-only, like ``root_dir``). When
            ``None`` the description is unchanged (back-compat). The caller
            derives the value in-container via ``resolve_project_name``; the
            compiler performs no environment/subprocess reads.

    Returns:
        A ``(PipelineDocument, FlowDocument)`` documents tuple. The
        ``PipelineDocument`` carries the parsed header (with ``header.roles``),
        format, and the ORIGINAL body (always unprefixed, never the
        reconstructed one); the ``FlowDocument`` carries the name, the
        optionally project-name-prefixed description, optional top-level
        prompt, optional top-level ``root_dir``, the optional compiled
        ``memory`` block (``None`` when memory does not participate; emitted
        between ``description`` and ``stages``), and compiled stages (the
        input ``roles`` field translated to the output ``agents`` field;
        ``depends_on`` position-derived for PHASES, pass-through for STAGES).

    Raises:
        StructuralError: On a structural defect in the DSL (propagated from
            ``parse_dsl``), on an empty body, on a legacy ``agents`` key in a
            stage body, on an authoring ``interactive``/``auto_run`` key in a
            stage body (the authoring-side fields are ``communication``/
            ``trigger``), on an authoring ``reflect``/``memory_use`` key in a
            stage body (the memory stage keys are authored through the workflow
            memory instructions), or on a ``trigger`` value outside
            ``on_success``/``manual``.
        FileNotFoundError: If ``pipeline_path`` does not exist or ``flow_path``'s
            parent is missing (propagated).
        PermissionError: If ``pipeline_path`` is unreadable (propagated).
    """
    logger.info("compile_flow: %s → %s", pipeline_path, flow_path)

    text = pipeline_path.read_text()
    header, fmt, body = parse_dsl(text)

    if len(body.steps) == 0:
        raise StructuralError("empty body")

    # The step sequence consumed for FlowStage assembly. When a workflow is
    # applied, this is a reconstructed (deep-copied + overridden + expanded)
    # sequence plus the two companion maps: the per-final-id effective-notes
    # map (the source of each stage's ``buttons`` field) and the memory
    # emission of step 4.9 (the compiled memory block plus the per-final-id
    # memory keys — both resolved by base name / final id so loop-expanded
    # copies share them); the ORIGINAL `body` is preserved for
    # PipelineDocument below. Workflow-less compiles carry an empty notes map
    # and an empty emission, so every lookup below is ``None``/falsy and no
    # ``buttons``/``reflect``/``memory_use`` key is assembled.
    if workflow is not None:
        reconstructed, notes_by_id, memory_emission = _reconstruct_body(fmt, body, workflow)
    else:
        reconstructed, notes_by_id = list(body.steps), {}
        memory_emission = _MemoryEmission(block=None, keys_by_id={})

    stages: list[FlowStage] = []

    if fmt is BodyFormat.PHASES:
        for i, step in enumerate(reconstructed):
            depends_on = [reconstructed[i - 1].name] if i > 0 else None
            fields = _canonical_fields(
                step.body,
                step.name,
                notes=notes_by_id.get(step.name),
                memory_fields=memory_emission.keys_by_id.get(step.name),
            )
            stages.append(
                FlowStage(
                    id=step.name,
                    name=step.title,
                    depends_on=depends_on,
                    fields=fields,
                ),
            )
    elif fmt is BodyFormat.STAGES:
        for step in reconstructed:
            fields = _canonical_fields(
                step.body,
                step.name,
                notes=notes_by_id.get(step.name),
                memory_fields=memory_emission.keys_by_id.get(step.name),
            )
            stages.append(
                FlowStage(
                    id=step.name,
                    name=step.title,
                    depends_on=step.depends_on,
                    fields=fields,
                ),
            )

    flow_prompt = workflow.prompt if workflow is not None else None

    # The project-name prefix is OUTPUT-only: when ``project_name`` is not ``None``,
    # ``FlowDocument.description`` carries ``[{project_name}] {header.description}``
    # while the ``PipelineDocument`` mirror below keeps the unprefixed header
    # description (the same OUTPUT-only posture as ``root_dir``). When
    # ``project_name is None`` the description is unchanged (back-compat). The
    # compiler performs no environment/subprocess reads to derive the name — the
    # caller supplies it.
    description = f"[{project_name}] {header.description}" if project_name is not None else header.description

    doc = FlowDocument(
        prompt=flow_prompt,
        root_dir=root_dir,
        name=header.name,
        description=description,
        memory=memory_emission.block,
        stages=stages,
    )
    pipeline_doc = PipelineDocument(header=header, format=fmt, body=body)
    text_out = serialize_flow(doc)
    flow_path.write_text(text_out)

    return (pipeline_doc, doc)
