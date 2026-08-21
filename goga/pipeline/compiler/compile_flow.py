"""The ``compile_flow`` entry point — read a pipeline-file, compile, write a flow-file.

``compile_flow`` is the entry point of the compiler cell: it reads a goga DSL
pipeline-file (phases-list or stages-map), parses it via ``parse_dsl``, applies
the per-format ``depends_on`` rules (PHASES: position-derived; STAGES:
pass-through), reorders each step body into canonical key order via the internal
``_canonical_fields`` helper (translating the authoring-side ``roles`` field into
the output ``agents`` field via ``translate_role``, injecting the single default
``agents=["auto"]`` when the source body lacks a usable ``roles`` value,
translating the authoring-side ``communication`` field into the output
``interactive`` field, and hard-failing on the legacy ``agents`` and authoring
``interactive`` stage-body keys), builds a ``FlowDocument``,
serializes it via ``serialize_flow``, and writes the result to ``flow_path``. It
performs no environment-variable reads and no subprocess calls — the caller
supplies both paths explicitly.

The authoring-side stage-body field is ``roles``; the compiled afm output field is
``agents``. When a step body carries a usable ``roles`` value (a non-empty list),
each role is translated to its afm agent name via ``translate_role`` (the single
source of truth) and the result is placed under the output ``agents`` key. When a
step body has no ``roles`` key, has ``roles: null``, or has ``roles: []``,
``_canonical_fields`` injects a single default into the assembled
``FlowStage.fields``: ``agents=["auto"]``. A legacy ``agents`` key in a step body
is rejected with ``StructuralError("agents key is forbidden in stage body; use
roles")`` — the input-only ``roles`` key never reaches the output. Symmetrically,
the authoring-side stage-body field for interactivity is ``communication``; the
compiled afm output field is ``interactive``. A step body carrying
``communication`` is translated into the output ``interactive`` slot; an
authoring ``interactive`` key is rejected with ``StructuralError("interactive key
is forbidden in stage body; use communication")`` — the afm output key
``interactive`` is stable, so only ``communication`` is ever authored. Symmetrically,
the authoring-side stage-body field for the launch mode is ``trigger``; the compiled
afm output field is ``auto_run``. A step body carrying ``trigger: manual`` is
translated into the output ``auto_run: false`` slot (canonical position immediately
after ``auto_approve``); ``trigger: on_success`` (or no trigger) assembles NO
``auto_run`` key, and ``auto_run: true`` is never emitted. An authoring ``auto_run``
key is rejected with ``StructuralError("auto_run key is forbidden in stage body; use
trigger: manual")``; a ``trigger`` value outside ``on_success``/``manual`` is rejected
with ``StructuralError("trigger must be one of: on_success, manual")`` — the
authoring key is consumed by the translation, never passed through as an unknown
key.

Symmetrically, the authoring-side stage-body directive for the script timeout
is ``timeout``; the compiled afm output field is ``script_timeout``. A step
body carrying a string ``timeout`` (with ``script`` in the same body) is
translated into the output ``script_timeout`` slot (canonical position
immediately after ``script_after``); the value passes verbatim — the Go
duration grammar is NOT validated here (a malformed string like ``"3 min"``
reaches the flow-file as-is and fails in afm at runtime). A non-string value
(including ``timeout: null`` — presence gates, not truthiness, unlike
``trigger``) is rejected with ``StructuralError("timeout must be a string in
stage {name}")``; a ``timeout`` without ``script`` is rejected with
``StructuralError("timeout requires script in stage {name}")``
(``before_script``/``after_script`` do not open the directive —
``script_timeout`` scopes to the script action). The output key is present
only when the directive is authored (omitempty), so pipelines without
``timeout`` compile byte-identically. Directly authoring ``script_timeout`` is
not forbidden (the same stance as direct ``script_before``); when both are
authored, the translated ``timeout`` value wins. The directive applies to
pipeline-file stage bodies AND embedded extend-stage bodies, and every
loop-expanded copy (``NAME-i``) inherits the translated value verbatim. The
translation is local to ``FlowStage`` assembly — the ``PipelineDocument.body``
returned to consumers keeps the authored ``timeout`` untouched.
``auto`` is a
sentinel string emitted verbatim (goga does not interpret it; afm resolves the
agent). In a body carrying ``script``, the ``agents`` directive is NOT
assembled at all — afm rejects ``agents`` combined with ``script`` — so neither
the ``["auto"]`` default NOR a translated ``roles`` value reaches the output
(the ``roles`` elements are still validated). ``supervisor``/``supervisor_prompt`` are authored-only — never injected,
but they pass through the canonical slot when the source body carries them. The
translation/injection lives in ``FlowStage`` assembly only — the
``PipelineDocument.body`` returned to consumers stays a faithful mirror of the
source pipeline-file.

When the caller passes a non-``None`` ``workflow`` (a ``WorkflowDocument``), the
parsed body is reconstructed BEFORE the ``FlowStage`` assembly: per-stage
agent/prompt overrides are injected into the step bodies, looped stages are
expanded into N chained copies (``NAME-1``..``NAME-N``), and external
``depends_on`` references are rewritten to the LAST expanded id. The
reconstruction operates on a deep copy of the parsed steps — the
``PipelineDocument`` returned to the consumer always carries the ORIGINAL parsed
body, never the reconstructed one. Unknown ``workflow.stages`` names (names
absent from both the ORIGINAL body and every embedded extend-stage) AND dangling
``extend.<name>.before/.after`` refs (refs naming no step in the ORIGINAL body
nor an extend-stage) are both rejected with a ``StructuralError`` up front,
before the body is rebuilt — strict validation in both directions.

I/O exceptions and structural errors from ``parse_dsl`` propagate unchanged. An
empty body raises ``StructuralError("empty body")`` here — not in ``parse_dsl``,
which lets empty bodies through for ``compile_flow`` to reject.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from ..workflow import WorkflowDocument, WorkflowExtendStage, WorkflowStage
from .body_format import BodyFormat
from .flow_document import FlowDocument
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
_CANONICAL_KEY_ORDER = [
    "interactive",
    "auto_approve",
    "auto_run",
    "command",
    "prompt",
    "description",
    "agents",
    "supervisor",
    "supervisor_prompt",
    "skills",
    "script_before",
    "script",
    "script_after",
    "script_timeout",
]

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
    """Map an authoring-side ``role`` to its afm-side agent name / prompt-file stem.

    The single source of truth for the role ↔ ``{afm-agent-name, prompt-file-stem}``
    bijection. Maps the three known role aliases to their afm stems and passes every
    other value through verbatim. ``role`` values are NOT validated — the afm agent
    namespace is open, so already-afm names (``planning``/``implementation``/``review``),
    ``summary`` (a separate, non-role channel), ``auto`` (a compiler-side default
    sentinel, NOT injected here), and arbitrary agent names all return unchanged.

    Args:
        role: The authoring-side role value (an alias or an already-afm name).

    Returns:
        The afm-side agent name / prompt-file stem for a known alias, or ``role``
        unchanged for any other value.
    """
    return _ROLE_ALIASES.get(role, role)


def _has_usable_roles(body: dict[str, Any]) -> bool:
    """Return ``True`` when ``body`` carries a non-empty ``roles`` list.

    A missing ``roles`` key, an explicit ``None``, or an empty list all return
    ``False`` — these are the trigger conditions for default injection.

    Args:
        body: The step body dict produced by ``parse_dsl``.

    Returns:
        ``True`` when ``roles`` is a non-empty list; ``False`` otherwise.
    """
    roles = body.get("roles")
    return isinstance(roles, list) and len(roles) > 0


def _inject_defaults(body: dict[str, Any], suppress_agents: bool = False) -> dict[str, Any]:
    """Return a body dict with ``roles`` translated to ``agents`` (or the default injected).

    The input-only ``roles`` key is ALWAYS dropped from the output. When
    ``suppress_agents`` is ``True`` (the body carries a ``script`` key — afm
    rejects ``agents`` combined with ``script``), NO ``agents`` slot is
    assembled at all: neither the single ``["auto"]`` default NOR the
    translated ``roles`` value reaches the output. The ``roles`` list is still
    element-validated (a non-str element raises the same ``StructuralError``)
    so authoring defects surface identically. When ``body``
    carries a usable ``roles`` value (non-empty list), each role is translated to
    its afm agent name via ``translate_role`` (the single source of truth) and the
    result is placed under the output ``agents`` key. A non-str element raises
    ``StructuralError("non-str value in stage roles list: ...")`` (the body is
    parsed verbatim, so ``translate_role`` — which must not validate — is shielded
    from unhashable/non-str elements here). Otherwise the single default
    ``agents=["auto"]`` is injected. ``supervisor``/``supervisor_prompt`` are NOT
    injected — they are authored-only and flow through the canonical slot via
    ``_canonical_fields`` only when the source body already carries them. The
    input is never mutated; the returned dict is independent so the caller can
    deep-copy / reorder freely without touching the parsed body.

    Args:
        body: The step body dict produced by ``parse_dsl``.

    Returns:
        A new dict without the ``roles`` key, carrying either the translated
        ``agents`` list or the injected single ``["auto"]`` default — or no
        ``agents`` key at all when ``suppress_agents`` is ``True``.
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

    Three authoring keys are forbidden because each names an afm OUTPUT field
    whose authoring-side counterpart is a different key: ``agents`` (author the
    ``roles`` field — translated element-wise), ``interactive`` (author the
    ``communication`` field — renamed), and ``auto_run`` (author the ``trigger``
    field — ``trigger: manual`` assembles ``auto_run: false``). Checking them in
    one place, at the very start of ``_canonical_fields``, keeps every
    prohibition ahead of any translation, exactly as the contract orders it.

    Args:
        body: The step body dict produced by ``parse_dsl`` (or an embedded
            extend body).

    Raises:
        StructuralError: When ``body`` carries any of the three authoring keys,
            with the contract message naming the authoring-side field to use.
    """
    if "agents" in body:
        raise StructuralError("agents key is forbidden in stage body; use roles")

    if "interactive" in body:
        raise StructuralError("interactive key is forbidden in stage body; use communication")

    if "auto_run" in body:
        raise StructuralError("auto_run key is forbidden in stage body; use trigger: manual")


def _validate_trigger(body: dict[str, Any]) -> str | None:
    """Return the effective ``trigger`` of ``body``, validating the closed value set.

    Validation gates on the VALUE, not key presence: a ``trigger:`` with no
    value parses to ``None`` and is treated as ABSENT — symmetrically to
    ``roles: null``. Any non-``None`` value outside the closed set
    ``on_success``/``manual`` — including non-str values, which can never be
    members of a str tuple — raises.

    Args:
        body: The step body dict produced by ``parse_dsl`` (workflow path: a
            reconstructed deep copy, possibly already rewritten by the manual
            override pass).

    Returns:
        The effective trigger (``"on_success"``, ``"manual"``), or ``None``
        when the key is absent or carries a null value.

    Raises:
        StructuralError: When ``body`` carries a non-null ``trigger`` value
            outside ``on_success``/``manual``.
    """
    effective_trigger = body.get("trigger")

    if effective_trigger is not None and effective_trigger not in ("on_success", "manual"):
        raise StructuralError("trigger must be one of: on_success, manual")
    return effective_trigger


def _apply_timeout_directive(body: dict[str, Any], stage_name: str, timeout_value: Any) -> None:
    """Validate the captured ``timeout`` directive and assign ``script_timeout``.

    The directive was captured from the ORIGINAL body by the caller (the
    authoring key is consumed by the rebuild, so presence/value travel as
    arguments). Validation runs in the fixed contract order — non-string →
    requires-script → assign: a present non-string value (``timeout: null``
    counts as PRESENT, unlike ``trigger`` whose null counts as absent) raises;
    a ``timeout`` without ``script`` in the same (rebuilt) body raises —
    ``script_timeout`` scopes to the script action, so ``before_script``/
    ``after_script`` do not open the directive. Otherwise the value is
    assigned verbatim to the output ``script_timeout`` key — the Go duration
    grammar is NOT validated here (afm fails on a malformed string at
    runtime). The assignment overwrites a directly authored
    ``script_timeout`` (same output key — the translated value wins).

    Args:
        body: The REBUILT body dict (authoring keys already translated) —
            mutated in place by the assignment (the caller's fresh dict, never
            the caller's original parsed body).
        stage_name: The stage id (used in the structural error messages — for
            loop-expanded copies this is ``NAME-i``).
        timeout_value: The captured ``timeout`` value from the original body.

    Raises:
        StructuralError: When the value is not a string, or when the body
            carries no ``script`` key.
    """
    if not isinstance(timeout_value, str):
        raise StructuralError(f"timeout must be a string in stage {stage_name}")

    if "script" not in body:
        raise StructuralError(f"timeout requires script in stage {stage_name}")
    body["script_timeout"] = timeout_value


def _canonical_fields(body: dict[str, Any], stage_name: str) -> dict[str, Any]:
    """Reorder ``body`` into canonical key order, deep-copying each value.

    A legacy ``agents`` key in the step body is rejected up front with
    ``StructuralError("agents key is forbidden in stage body; use roles")`` — the
    authoring-side field is ``roles``; ``agents`` is the output-only afm field.
    Likewise, an authoring ``interactive`` key is rejected with
    ``StructuralError("interactive key is forbidden in stage body; use
    communication")`` — the authoring-side field is ``communication``; ``interactive``
    is the output-only afm field. Likewise, an authoring ``auto_run`` key is
    rejected with ``StructuralError("auto_run key is forbidden in stage body; use
    trigger: manual")`` — the authoring-side field for the launch mode is
    ``trigger``; ``auto_run`` is the output-only afm field.

    The ``trigger`` key (when present in a pipeline-file body, an embedded
    extend body, or a loop-expanded copy) is read and validated: any non-``None``
    value outside the closed set ``on_success``/``manual`` — including non-str
    values, which can never be members of the set — raises
    ``StructuralError("trigger must be one of: on_success, manual")``. Validation
    gates on the VALUE, not key presence: ``trigger:`` with no value parses to
    ``None`` and is treated as ABSENT (symmetrically to ``roles: null``). The key
    is consumed (excluded from the rebuilt dict, like ``_APPROVE_SENTINEL``), so
    the authoring key never reaches the output as an unknown key.

    The ``_APPROVE_SENTINEL`` key (if present — threaded by
    ``_apply_per_stage_overrides`` only on the workflow path) is read and
    consumed as the effective ``approve`` directive; it never reaches the output.
    The raw ``roles`` list is captured BEFORE translation so the ``auto_approve``
    effect matches the authored role (``planner``), not the translated stem
    (``planning``). The author script directives ``before_script``/``script``/
    ``after_script`` are translated to the output ``script_before``/``script``/
    ``script_after`` keys (consumed, not passed through as unknown keys). A body
    carrying ``script`` together with ``prompt`` and/or ``skills`` is rejected
    with ``StructuralError("script is mutually exclusive with prompt/skills in
    stage {stage_name}")``; ``before_script``/``after_script`` are compatible.

    The stage ``timeout`` directive is captured BEFORE the rebuild (from the
    ORIGINAL body) and validated/translated by the same pass as script
    exclusivity, in the fixed order: a present non-string value (including
    ``timeout: null`` — presence gates, not truthiness, unlike ``trigger``)
    raises ``StructuralError("timeout must be a string in stage
    {stage_name}")``; a ``timeout`` without ``script`` in the same body raises
    ``StructuralError("timeout requires script in stage {stage_name}")``
    (``before_script``/``after_script`` do not open the directive —
    ``script_timeout`` scopes to the script action); otherwise the value is
    assigned verbatim to the output ``script_timeout`` key — the Go duration
    grammar is NOT validated here (afm fails on a malformed string at runtime).
    The authoring ``timeout`` key is consumed, never passed through as an
    unknown key; the output key appears only when the directive is authored
    (omitempty). Directly authoring ``script_timeout`` is legal (unvalidated,
    the same stance as direct ``script_before``); when both are authored the
    translated ``timeout`` value wins.

    The authoring ``communication`` field is then translated into the output
    ``interactive`` slot — EXCEPT under an approve directive driving the
    communication effect (``auto``/``plan``) + ``communication: true``, where it
    is SUPPRESSED (omitted, not ``interactive: false``). ``communication: false``
    (or no communication-effect directive) renames to ``interactive: false`` as
    usual. The ``roles`` field is then translated to ``agents`` (or the single
    default ``agents=["auto"]`` injected) via ``_inject_defaults`` when the source
    body lacks a usable ``roles`` value — EXCEPT in a body carrying ``script``,
    where NO ``agents`` key is assembled at all (afm rejects the combination;
    both the default injection and the translated ``roles`` value are
    suppressed, while the ``roles`` elements are still validated). Under an
    approve directive driving the
    roles effect (``auto``/``dialog``) + ``planner`` in the raw ``roles``,
    ``auto_approve: true`` is emitted (canonical slot right after
    ``interactive``). A body whose effective ``trigger`` is ``manual`` assembles
    ``auto_run: false`` (canonical slot immediately after ``auto_approve``);
    ``trigger: on_success`` or no trigger assembles NO ``auto_run`` key —
    ``auto_run: true`` is never emitted. Known keys (``interactive``,
    ``auto_approve``, ``auto_run``, ``command``,
    ``prompt``, ``description``, ``agents``, ``supervisor``, ``supervisor_prompt``,
    ``skills``, ``script_before``, ``script``, ``script_after``,
    ``script_timeout``) are emitted in
    that fixed order; any remaining keys are appended alphabetically. The
    input-only ``roles`` key never reaches the output (dropped in
    ``_inject_defaults``); the input-only ``communication`` key never reaches the
    output either (renamed to ``interactive`` or suppressed). Each value is
    deep-copied so the returned dict shares no structure with the parsed body.

    This function NEVER mutates its ``body`` argument. The approve sentinel is
    read (``.get``) rather than popped, and every transformation rebuilds a
    fresh dict — so the caller's body is left untouched on every path. This
    matters on the non-workflow path, where ``body`` is the caller's shared dict
    (the same objects mirrored into ``PipelineDocument``): because nothing is
    mutated, ``PipelineDocument.body`` always reflects the authored source
    verbatim, whether or not a workflow is applied.

    Args:
        body: The step body dict produced by ``parse_dsl`` (workflow path: a
            reconstructed deep copy carrying the ``_APPROVE_SENTINEL``).
        stage_name: The stage id (used in the mutual-exclusion error message —
            for loop-expanded copies this is ``NAME-i``).

    Returns:
        A new dict in canonical key order with deep-copied values.

    Raises:
        StructuralError: If ``body`` carries the legacy ``agents`` key — the
            authoring-side field is ``roles``; ``agents`` is output-only. Or if
            ``body`` carries an authoring ``interactive`` key — the authoring-side
            field is ``communication``; ``interactive`` is output-only. Or if
            ``body`` carries an authoring ``auto_run`` key — the authoring-side
            field for the launch mode is ``trigger``; ``auto_run`` is
            output-only. Or if ``body`` carries a ``trigger`` value outside the
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

    Computed ONCE per reconstruction and threaded into ``_apply_per_stage_overrides``
    and ``_expand_loops`` so the per-field merge lives in exactly one place. The
    inline ``agent``/``loop``/``approve`` carried by ``workflow.extend`` seed the
    default override (an extend-stage with no matching stages-block still gets its
    inline agent/loop/approve applied); an explicit ``workflow.stages`` entry then
    overlays per-field and WINS whenever its field is not ``None`` (the inline
    value is the fallback only). ``prompt``/``skills`` have no inline equivalent,
    so a stages-block entry's own values always pass straight through, and a name
    with only an extend entry carries ``prompt``/``skills`` as ``None``. The
    manual-launch instruction is stages-block-only: the extend seed CANNOT carry
    ``manual`` (``parse_workflow`` rejects it in an extend-entry), so the merged
    branch passes ``manual=stg.manual`` EXPLICITLY — the ``WorkflowStage``
    constructor defaults it to ``None``, and an overlay that omitted it would
    silently drop the instruction.

    Args:
        workflow: The declarative workflow instructions.

    Returns:
        The effective per-stage override map keyed by stage name. Extend-seeded
        entries carry only ``agent``/``loop``/``approve`` (``manual`` stays
        ``None``); stages-block entries carry their full ``WorkflowStage``;
        merged entries combine them per-field, always carrying the stages-block
        ``manual``.
    """
    effective: dict[str, WorkflowStage] = {}

    for name, ext in workflow.extend.items():
        effective[name] = WorkflowStage(agent=ext.agent, loop=ext.loop, approve=ext.approve)

    for name, stg in workflow.stages.items():
        base = effective.get(name)
        if base is None:
            # Explicit stages-block with no inline fallback — use it verbatim.
            effective[name] = stg
            continue
        # Per-field overlay: stages-block wins whenever its field is not None.
        # ``manual`` is passed explicitly — the extend seed carries none, and the
        # constructor default (None) would silently drop the instruction.
        effective[name] = WorkflowStage(
            agent=stg.agent if stg.agent is not None else base.agent,
            prompt=stg.prompt,
            loop=stg.loop if stg.loop is not None else base.loop,
            skills=stg.skills,
            approve=stg.approve if stg.approve is not None else base.approve,
            manual=stg.manual,
        )

    return effective


def _merge_skills(
    pipeline_skills: list[str] | None,
    workflow_skills: list[str] | None,
) -> list[str] | None:
    """Merge pipeline-file and workflow-stage skills, deduplicating by value.

    Pipeline-file skills come first (their relative order is preserved), then the
    workflow-stage skills, with any value already seen dropped. Deduplication is
    deterministic (first-occurrence order). Both inputs empty (or ``None``) yields
    ``None`` — the absence marker the caller uses to leave the ``skills`` slot
    untouched, so an absent key stays absent.

    The pipeline-file body is parsed verbatim (``parse_dsl`` performs no field
    type validation by design), so ``pipeline_skills`` may carry any type in
    practice — e.g. an authored scalar ``skills: web-search``. A non-list value
    is treated as empty (the workflow override still applies) rather than
    crashing the merge; validating the pipeline-file ``skills`` type is a
    separate concern outside this cell. ``workflow_skills`` is always a
    ``list[str]`` or ``None`` — it is validated by ``parse_workflow``.

    Args:
        pipeline_skills: The stage's pipeline-file ``skills`` value, or ``None``.
        workflow_skills: The workflow-stage ``skills`` override (always a
            ``list[str]`` or ``None``), or ``None``.

    Returns:
        The merged deduplicated list, or ``None`` when both inputs are empty.
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

    For each ``(name, WorkflowStage)`` in ``effective``: the step with a matching
    name/id is found in ``steps`` (mutated in place); when no step matches the
    entry is silently skipped. A not-found can only be a stage removed at 4skip
    (4pre already rejected unknown ``workflow.stages`` names before this pass
    runs), so the skip is intentional and emits no warning. When found, a
    non-``None`` ``agent`` composes the
    in-container wrapper path into the step body's ``command`` slot, a
    non-``None`` ``prompt`` copies its text into the step body's ``description``
    slot, and a non-``None`` ``skills`` merges with the step body's existing
    ``skills`` via ``_merge_skills`` (pipeline-first dedup). The effective
    ``approve`` directive (one of ``auto``/``plan``/``dialog``, or ``None``) is
    always threaded into the step body under the ``_APPROVE_SENTINEL`` key — it
    survives ``copy.deepcopy`` in loop-expansion and is read/consumed in
    ``_canonical_fields`` to drive the two approve effects (interactive
    suppression and ``auto_approve`` emission, each on its own directive subset);
    writing ``None`` is harmless (``_canonical_fields`` treats a ``None`` sentinel
    as no directive). The effective tri-state ``manual`` instruction is then
    applied to the step body's ``trigger`` on this same working copy: ``True``
    forces ``trigger: manual`` over any authored value (an idempotent no-op on
    an already-manual stage); ``False`` cancels a manual state from EITHER body
    source (pipeline-file body OR embedded extend body) by rewriting
    ``trigger: manual`` to ``trigger: on_success``, and raises
    ``StructuralError("manual: false on non-manual stage <name>")`` when the
    body carries no manual state to cancel; ``None`` (no instruction) leaves
    the authored trigger unchanged. ``effective`` already folds the
    inline-extend default together with the explicit stages-block, so inline
    ``agent``/``loop``/``approve`` apply even without a stages-block, and an
    explicit stages-block wins per-field. Operates on the supplied (already
    deep-copied) working sequence so the ORIGINAL parsed body stays untouched.

    Args:
        steps: The working (deep-copied) step sequence to mutate in place.
        effective: The resolved per-stage override map (from
            ``_effective_overrides``), keyed by stage name.

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

    PHASES copies carry no ``depends_on`` (position derives it later); STAGES
    copies carry the original step's external ``depends_on`` on the FIRST copy
    (deep-copied so the rewrite pass can mutate it freely) and an internal chain
    reference to the previous copy (``NAME-(index-1)``) on every subsequent copy.
    The body is deep-copied so copies never alias one another or the base step.

    Args:
        step: The (override-applied) base step being expanded.
        new_id: The id for this copy (``NAME-<index>``).
        index: 1-based position within the expanded group.
        fmt: The body format — selects ``PhaseStep`` vs ``StageStep``.

    Returns:
        A new step instance for the expanded copy.
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

    For each step in source order: ``loop_count`` is the effective override's
    ``loop`` for the step's name when set, otherwise ``1``. ``effective`` already
    folds the inline-extend ``loop`` default together with the explicit
    stages-block ``loop`` (stages-block wins per-field), so an inline-extend loop
    expands even without a stages-block, and an explicit stages-loop wins. A
    ``loop_count`` of ``1`` appends the step unchanged and records the base-name →
    ``[base-name]``. A ``loop_count >= 2`` appends ``N`` copies ``NAME-1``..``NAME-N``
    (built via ``_make_expanded_copy``) and records the base-name →
    ``[NAME-1, ..., NAME-N]``.

    Args:
        steps: The override-applied working step sequence.
        fmt: The body format — selects the expanded step type.
        effective: The resolved per-stage override map (from
            ``_effective_overrides``), source of loop counts.

    Returns:
        The new ordered step list and the base-name → produced-ids map.
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

    For each ``StageStep`` with a non-``None`` ``depends_on``: a reference to a
    base-name whose loop count was ``>= 2`` is replaced with the LAST id from
    that base-name's expanded-ids list; a reference to a base-name with loop
    count ``1`` (whose single id equals the base-name) is kept as-is; an
    unmatched reference is kept as-is for afm to surface as a dangling ref.

    Args:
        steps: The loop-expanded STAGES sequence to rewrite in place.
        expanded_ids: The base-name → produced-ids map from ``_expand_loops``.
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

    ``title`` falls back to the extend-stage name when the body carries no
    ``title`` key (Design Decision 1: the display label is the stage name).
    ``body`` is the extend body minus the serializer-reserved identity keys
    (``title``, ``name``, ``id``), with every value deep-copied so the embedded
    step never aliases the workflow's declarative body. Dropping ``name``/``id``
    keeps the serializer's seeded identity intact — see
    ``_EXTEND_STEP_RESERVED_KEYS``.

    Args:
        name: The extend-stage name (map key in ``workflow.extend``).
        ext: The extend-stage declaration.

    Returns:
        The resolved display title and a deep-copied body without ``title``,
        ``name``, or ``id``.
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
    """STAGES branch — embed extend-stages by deriving ``depends_on`` (two passes).

    Pass 1 appends one ``StageStep`` per extend-entry in source order: the new
    stage's ``depends_on`` is a copy of its ``after`` refs (or ``None`` when no
    ``after``), so ``after``-refs land verbatim. Pass 2 applies ``before``: the
    new stage's name is appended to each ``before``-target's ``depends_on``,
    initialising the list to ``[]`` when it was ``None`` and appending
    idempotently (a name is never recorded twice). Every before/after ref is
    guaranteed to resolve — step 4a1 (``_strict_validate_extend_refs``) rejects
    any dangling ref with a ``StructuralError`` before this function runs, so no
    WARNING is emitted here. Cross-references between extend-stages resolve
    automatically — after pass 1 every extend step is already in ``steps``.

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

    Returns ``(idx, before_anchored)``. ``idx`` sits immediately after the LAST
    resolvable ``after``-target (preferred when both resolve consistently), or
    immediately before the FIRST resolvable ``before``-target, or at
    ``len_steps`` (append) when none resolve. ``before_anchored`` is ``True``
    only for a sole ``before`` (no ``after``); the caller offsets every other
    (after-anchored) insertion so siblings sharing a target stack in authored
    order. A WARNING is logged on the inconsistent and unresolvable fall-backs.

    Args:
        name: The extend-stage name (used in WARNING messages).
        after_positions: Sorted positions of resolvable ``after``-targets.
        before_positions: Sorted positions of resolvable ``before``-targets.
        len_steps: Current ``len(steps)`` — the append index when nothing
            resolves.

    Returns:
        The insertion index and whether the position is before-anchored.
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
    """PHASES branch — embed extend-stages by positional insertion.

    Each ``PhaseStep`` carries no ``depends_on`` (position derives it later in
    ``compile_flow``); this branch only places each extend-stage at the right
    list index. A deferred-resolution loop places, per iteration, the
    extend-stages whose ``before``/``after`` targets are either original steps
    or extend-stages already placed. The insertion index sits immediately after
    the LAST resolvable ``after``-target and/or immediately before the FIRST
    resolvable ``before``-target. Several stages anchored on the same resolvable
    target (or appended at the end) stack in authored order — same-index
    insertions are offset by how many siblings already landed there. When both
    are resolvable but inconsistent (the ``after``-target positioned after the
    ``before``-target) a ``WARNING`` is
    logged and the ``after`` index is used. Dangling targets (naming no known
    step) never reach this branch — step 4a0-pre
    (``_strict_validate_extend_refs``) rejects them with a ``StructuralError``
    first. A pass that places nothing
    indicates an unresolvable cycle between extend-stages — the remaining stages
    are appended at the end with a ``WARNING`` and the loop stops.

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

    Extend-stages are declarative new stages positioned relative to existing
    ones via ``before``/``after``. This step materialises them as real steps in
    ``steps`` so the generic downstream machine (4a overrides, 4b loop-expansion,
    4c external depends_on rewrite) processes them by the common rules. A no-op
    when ``workflow.extend`` is empty. The STAGES branch derives ``depends_on``
    from ``after``/``before`` (two passes); the PHASES branch inserts
    positionally (no ``depends_on`` — position derives it later).

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

    Builds the valid-name set as the union of every ORIGINAL step name in
    ``steps`` and every extend-stage name (``workflow.extend`` keys) — so a
    cross-reference to another extend-stage resolves. Any before/after ref
    absent from that set raises a ``StructuralError`` — replacing the former
    silent WARNING+skip / verbatim-pass-through. Runs BEFORE the 4a0 embed (and
    before any skip removal), so a before/after ref to a stage that also carries
    ``skip: true`` is NOT flagged here — it still exists in the ORIGINAL body at
    this point and is removed later at 4skip (referencing a skipped stage is not
    a dangling ref). The check is format-agnostic: ``step.name`` is the identity
    key for both ``StageStep`` and ``PhaseStep``. Validating before the embed
    keeps ``_embed_extend_stages`` a pure transform that can assume every ref
    resolves. Mirrors ``_strict_validate_stage_names`` (4pre) for
    ``workflow.stages`` names, extending strictness symmetrically to the
    extend-direction. Does NOT validate cycles, self-references, or duplicate
    refs — existence only; ordering/cycle concerns remain afm's responsibility.

    Args:
        steps: The working step sequence BEFORE the 4a0 embed (deep-copied
            ORIGINAL body only).
        workflow: The declarative workflow instructions (source of the extend
            names and their ``before``/``after`` refs).

    Raises:
        StructuralError: When a ``workflow.extend.<name>.before`` or ``.after``
            ref names no ORIGINAL step and no extend-stage.
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

    Builds the valid-name set from every step currently in ``steps`` — after the
    4a0 embed this is the union of the deep-copied ORIGINAL body and every
    extend-stage embedded at 4a0, so an extend-embedded name is a valid
    ``workflow.stages`` target.
    Any ``workflow.stages`` name absent from that set raises a
    ``StructuralError`` (replacing the former silent WARNING+skip). Runs on the
    FULL set BEFORE any skip removal, so a genuinely-existing stage that is also
    skipped is NOT flagged here — it is removed later at 4skip. The check is
    format-agnostic: ``step.name`` is the identity key for both ``StageStep``
    and ``PhaseStep``. Strictness over ``extend.<name>.before/.after`` refs is
    enforced separately by ``_strict_validate_extend_refs`` (step 4a0-pre),
    which runs before the 4a0 embed and before this pass.

    Args:
        steps: The working step sequence after 4a0 (deep-copied ORIGINAL +
            embedded extend-stages).
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

    Recurses over the skipped stage's ``depends_on``: a non-skipped reference is
    kept verbatim (the reconnection target — even a dangling one, which is afm's
    concern), while a skipped reference is resolved transitively. ``_seen``
    terminates a ``depends_on`` cycle among skipped stages — without it, a cycle
    would recurse forever; on cycle the recursion returns what it has so far. A
    skipped stage with no ``depends_on`` (or a missing step) resolves to ``[]`` so
    the caller writes an explicit empty ``depends_on: []``.

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
        the caller dedups preserving first-occurrence order).
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

    For each surviving (non-skipped) ``StageStep`` whose ``depends_on`` is not
    ``None``: rebuild the list so every reference to a skipped name ``S`` is
    replaced with ``_resolve_skip(S)`` (S's transitive non-skipped predecessors),
    while every other reference is kept verbatim. The rebuilt list is deduplicated
    preserving first-occurrence order; a fully-collapsed list is written as an
    explicit empty ``[]`` — distinct from ``None`` (which means "write no
    depends_on key"). Skipped steps themselves are left untouched here (the caller
    removes them). A resolved reference back to the step itself is dropped — a
    surviving step never legitimately depends on itself, and such a reference is
    reachable only from already-cyclic input (the skipped stage also depends on this
    survivor); cycle detection otherwise stays afm's concern.

    Args:
        steps: The working STAGES step sequence, mutated in place. Skipped steps
            are still present here — they are only read (as the source of
            ``depends_on``), never rewritten.
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

    Stages whose ``workflow.stages[name].skip`` is True are removed from the
    working body. STAGES reconnects: every reference to a removed stage ``S`` in a
    surviving step's ``depends_on`` is replaced with ``S``'s transitive
    non-skipped predecessors (via ``_resolve_skip``), deduplicated preserving
    first-occurrence order, and a fully-collapsed list is written as an explicit
    empty ``[]``. PHASES simply drops the skipped steps — ``depends_on``
    re-derives by list position downstream (automatic collapse, no explicit
    reconnection). The empty-body case (every stage skipped) is the caller's
    responsibility — this step leaves a possibly-empty ``steps`` for the guard.

    ``skip`` wins over ``agent``/``prompt``/``loop``/``skills`` overrides: this
    step runs BEFORE the 4a override pass, so a skipped stage's effective entry is
    a silent not-found there.

    Args:
        steps: The working step sequence after the 4a0 embed and 4pre validation,
            mutated in place.
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
) -> list[PhaseStep | StageStep]:
    """Apply the workflow reconstruction branch, returning a NEW step sequence.

    Deep-copies the parsed steps first so the ORIGINAL body (returned later via
    ``PipelineDocument``) is never mutated, then runs the CODEMANIFEST algorithm:
    (4a0-pre) strictly validate every ``workflow.extend.<name>.before/.after``
    ref against the full name set (a dangling ref is a ``StructuralError``);
    (4a0) embed ``workflow.extend`` stages; (4pre) strictly validate every
    ``workflow.stages`` name against the full name set (an unknown name is a
    ``StructuralError``); (4skip) remove skipped stages and transparently
    reconnect their dependents' ``depends_on``, then (guard) raise
    ``StructuralError("empty body")`` if nothing survives; resolve the effective
    per-stage override map ONCE (inline extend → stages overlay); (4a) per-stage
    overrides; (4b) loop-expansion with the expanded-ids map; (4c) external
    depends_on rewrite (STAGES only); the result (4d) is the reconstructed step
    list consumed for ``FlowStage`` assembly. The mandatory
    ``4a0-pre → 4a0 → 4pre → 4skip → empty-body guard → effective → 4a → 4b → 4c``
    ordering is load-bearing: extend-ref validation runs before the 4a0 embed
    (extend names come from ``workflow.extend`` keys, so cross-references between
    extend-stages resolve without embedding); extend-stages must be in ``steps``
    before strict validation (so an extend-embedded name is a valid
    ``workflow.stages`` target) and before the effective map is resolved (so
    their inline ``agent``/``loop`` seed the default override); skip removal runs
    before ``4a`` so a skipped stage's overrides are never applied ("skip wins");
    the empty-body guard runs once on the working copy, format-agnostic, before
    any assembly.

    Args:
        fmt: The body format — PHASES or STAGES.
        body: The ORIGINAL parsed body (never mutated here).
        workflow: The declarative workflow instructions.

    Returns:
        The reconstructed step sequence (PHASES or STAGES steps).

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

    return expanded


def compile_flow(
    pipeline_path: Path,
    flow_path: Path,
    workflow: WorkflowDocument | None = None,
    root_dir: str | None = None,
    project_name: str | None = None,
) -> tuple[PipelineDocument, FlowDocument]:
    """Compile a goga DSL pipeline-file into an afm flow-file and return both documents.

    Reads ``pipeline_path``, parses it with ``parse_dsl``, rejects an empty body
    with ``StructuralError("empty body")``, then builds a ``FlowDocument`` whose
    stages carry canonical-key-order ``fields`` and per-format ``depends_on``
    (position-derived for PHASES — the first step gets none, each subsequent step
    depends on its predecessor; pass-through for STAGES). The document is
    serialized via ``serialize_flow`` and written to ``flow_path`` (overwriting if
    it exists) as a side effect. I/O errors and structural errors from ``parse_dsl``
    propagate unchanged; ``compile_flow`` does not read ``AFM_DIR``.

    Each ``FlowStage.fields`` is assembled via ``_canonical_fields``, which
    translates the authoring-side ``roles`` field into the output ``agents`` field
    via ``translate_role`` (the single source of truth). A usable non-empty
    ``roles`` list is translated element-wise; a missing ``roles`` key, ``null``,
    or empty list injects the single default ``agents=["auto"]``. A legacy
    ``agents`` key in a step body is rejected with ``StructuralError`` — the
    authoring-side field is ``roles``. Likewise, a ``trigger`` value outside the
    closed set ``on_success``/``manual`` is rejected with ``StructuralError`` and
    an authoring ``auto_run`` key is rejected with ``StructuralError`` (the launch
    mode is authored as ``trigger: manual`` and translated into the output
    ``auto_run: false`` slot immediately after ``auto_approve`` — a body with
    ``trigger: on_success`` or no trigger assembles NO ``auto_run`` key).
    ``supervisor``/``supervisor_prompt`` are
    authored-only — never injected, but they pass through the canonical slot when
    the source body carries them. The translation/injection is local to
    ``FlowStage.fields`` — the ``PipelineDocument.body`` returned to consumers is
    never affected.

    When ``workflow`` is not ``None``, the parsed body is reconstructed
    (per-stage overrides, loop-expansion, external depends_on rewrite) on a deep
    copy BEFORE the ``FlowStage`` assembly; the top-level ``prompt`` of the
    workflow is emitted as the first key of the flow-file. When ``workflow`` is
    ``None`` no workflow is applied — the output carries no top-level prompt and
    no per-stage overrides.

    When ``root_dir`` is not ``None``, it is carried into the ``FlowDocument``
    and emitted by ``serialize_flow`` as the top-level ``root_dir`` key
    immediately after ``prompt`` (when present) and before ``name``. When
    ``root_dir`` is ``None`` the key is omitted entirely. The compiler performs
    no environment-variable reads — the caller (the ``run_pipeline`` routine in
    ``goga/pipeline``) computes the value from the in-container project root
    (``Path.cwd()`` resolves to ``/workspace`` inside the goga container).

    When ``project_name`` is not ``None``, the ``FlowDocument.description`` is
    prefixed ``f"[{project_name}] {header.description}"``; the
    ``PipelineDocument`` mirror keeps the unprefixed header description (the
    prefix is OUTPUT-only, like ``root_dir``). When ``project_name is None`` the
    description is unchanged (back-compat). The compiler performs no
    environment/subprocess reads to derive the name — the caller (the
    ``run_pipeline`` routine in ``goga/pipeline``) derives it in-container via
    ``resolve_project_name``.

    In addition to the flow-file, it builds a ``PipelineDocument`` aggregating the
    parsed ``header`` (including any inline ``roles`` overrides), ``format``, and
    the ORIGINAL ``body`` (never the reconstructed one) so consumers can obtain
    the parsed representation without re-invoking ``parse_dsl``. ``FlowDocument``
    never carries ``roles`` — the input-only ``roles`` field is translated away
    into the output ``agents`` field; ``FlowDocument`` is a goga-side artifact of
    the compiler, not part of the compiled afm flow-file.

    Args:
        pipeline_path: Absolute path to the input goga DSL pipeline-file. The file
            must be readable and contain a ``---`` separator line.
        flow_path: Absolute path to the output afm flow-file. The parent directory
            must already exist; it is not created here.
        workflow: Optional ``WorkflowDocument`` carrying declarative instructions
            for extending the pipeline (top-level prompt, per-stage
            agent/prompt/loop overrides). When ``None`` no workflow is applied.
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
        format, and the ORIGINAL body (always unprefixed); the ``FlowDocument``
        carries the name, the optionally project-name-prefixed description,
        optional top-level prompt, optional top-level ``root_dir``, and compiled
        stages (the input ``roles`` field translated to the output ``agents``
        field).

    Raises:
        StructuralError: On a structural defect in the DSL (propagated from
            ``parse_dsl``), on an empty body, on a legacy ``agents`` key in a
            stage body, on an authoring ``interactive``/``auto_run`` key in a
            stage body (the authoring-side fields are ``communication``/
            ``trigger``), or on a ``trigger`` value outside
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
    # sequence; the ORIGINAL `body` is preserved for PipelineDocument below.
    reconstructed = _reconstruct_body(fmt, body, workflow) if workflow is not None else list(body.steps)

    stages: list[FlowStage] = []

    if fmt is BodyFormat.PHASES:
        for i, step in enumerate(reconstructed):
            depends_on = [reconstructed[i - 1].name] if i > 0 else None
            fields = _canonical_fields(step.body, step.name)
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
            fields = _canonical_fields(step.body, step.name)
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
        stages=stages,
    )
    pipeline_doc = PipelineDocument(header=header, format=fmt, body=body)
    text_out = serialize_flow(doc)
    flow_path.write_text(text_out)

    return (pipeline_doc, doc)
