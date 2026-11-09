# Plan: `add-gates-to-workflow` — quality gates for workflow stages

<!-- `<topic>` — `add-gates-to-workflow` (`.goga/history/2026/add-gates-to-workflow/`) -->

## Purpose

Deliver stage-completion quality gates authored in the goga workflow vocabulary
and compiled one-directionally into the engine's stage `verify` field: a
top-level `gates:` settings block and a per-stage `gates:` check-step list in
the workflow-file, parsed strictly by the `workflow` cell, translated by the
`compiler` cell into `FlowVerify`/`FlowVerifyStep` and emitted through the
canonical `verify` slot of the flow-file, carried opaquely by the `hooks`
overlay merge and the `pipeline` skip rebuild. After implementation, a goga
author can gate any stage with shell check steps and AI-review steps plus a
bounded correction budget; a gate-free workflow compiles byte-identically to
its pre-feature output. The contracts are already materialized in the four
changed `CODEMANIFEST` files (read-only for the implementation); this plan
compiles them — with the design's verified traces — into ralphex tasks.

Implementation order (dependency direction, fixed): **workflow → compiler →
hooks → pipeline**, with documentation riders landing at the end.

## Context

### Contract Surface

**Entity: `WorkflowGates(patience, max_iterations, fresh_correction)`**
- Type: class (Entity, properties only)
- Declared `location`: `goga/pipeline/workflow/workflow_gates.py` (new file)
- Facade obligation: importable from `goga.pipeline.workflow`, listed in `__all__`
- Mutations: none
- Properties: `patience -> int | None`, `max_iterations -> int | None`,
  `fresh_correction -> bool | None` — all default `None` (authored keys only;
  an authored `0` is a value, not an omission)
- Semantic requirements: pure data model of the workflow quality-gate
  settings; no validation, no interpretation (parse-time validation lives in
  `parse_workflow`); fixed field order `patience, max_iterations,
  fresh_correction` (the emission order of the block keys)
- Imported dependencies: none (workflow cell is a leaf)
- Annotation context: `@dataclass(kw_only=True)` per the `convention`
  practice; Google-style docstring; module docstring mirrors
  `workflow_repeat.py`

**Entity: `WorkflowGateStep(name, script, agent, timeout, prompt)`**
- Type: class (Entity, properties only)
- Declared `location`: `goga/pipeline/workflow/workflow_gate_step.py` (new file)
- Facade obligation: importable from `goga.pipeline.workflow`, listed in `__all__`
- Mutations: none
- Properties: `name: str` (required, no default), `script: str | None = None`,
  `agent: str | None = None`, `timeout: str | None = None`,
  `prompt: str | None = None` — fixed field order `name, script, agent,
  timeout, prompt`
- Semantic requirements: data model of one authored check step; exactly one of
  `script`/`agent` is not `None` on every constructed instance
  (parser-enforced); `prompt` is `None` on every shell instance
  (parser-enforced — the applied fix "prompt-on-script-step binding")
- Imported dependencies: none
- Annotation context: `@dataclass(kw_only=True)` per `convention`

**Entity: `WorkflowStage` (changed)**
- Declared `location`: `goga/pipeline/workflow/workflow_stage.py` (existing)
- New trailing field `gates: list[WorkflowGateStep] | None = None` — fixed
  field order gains `gates` after `assistants`
- Facade obligation: unchanged (already exported)

**Entity: `WorkflowDocument` (changed)**
- Declared `location`: `goga/pipeline/workflow/workflow_document.py` (existing)
- New trailing field `gates: WorkflowGates | None = None` — fixed field order
  gains `gates` after `repeat`
- Facade obligation: unchanged

**Routine: `parse_workflow(input: str) -> document: WorkflowDocument` (changed)**
- Declared `location`: `goga/pipeline/workflow/parse_workflow.py` (existing)
- New structural validation surfaces: the top-level `gates:` settings block
  (keys/types/bounds; empty = absence), the per-stage `gates:` list (step
  forms), the extend-entry prohibition, the empty-workflow rule extension,
  model threading. Steps 4/5/6.1.2/6.1.15/6.10/6.11/7/8 of the contract.
- Raises: `WorkflowSyntaxError` with the exact one-line messages quoted in
  Task 3 (normative).

**Entity: `FlowVerifyStep(name, run, command, timeout, prompt)`**
- Type: class (Entity, properties only)
- Declared `location`: `goga/pipeline/compiler/flow_verify_step.py` (new file)
- Facade obligation: importable from `goga.pipeline.compiler`, listed in `__all__`
- Properties: `name: str` (required), `run: str | None = None`,
  `command: str | None = None`, `timeout: str | None = None`,
  `prompt: str | None = None` — fixed order (the emission order of the step
  keys). Exactly one of `run`/`command` not `None` mirrors the authored
  exclusivity.

**Entity: `FlowVerify(steps, max_failures, review_patience, fresh_correction)`**
- Type: class (Entity, properties only)
- Declared `location`: `goga/pipeline/compiler/flow_verify.py` (new file)
- Facade obligation: importable from `goga.pipeline.compiler`, listed in `__all__`
- Properties: `steps: list[FlowVerifyStep]` (required, no default),
  `max_failures: int | None = None`, `review_patience: int | None = None`,
  `fresh_correction: bool | None = None` — fixed order (the emission order of
  the block keys). An instance carrying no authored setting IS the list
  emission form.

**Routine: `compile_flow(...)` (changed)**
- Declared `location`: `goga/pipeline/compiler/compile_flow.py` (existing)
- Gains: the `_gates_emission` companion (numbering 4.11, called after
  `_collaboration_emission` 4.10), the step-5 gates assembly
  (`_canonical_fields` gains `verify_fields`; `_assemble_verify` assigns
  `source["verify"]` before the canonical loop), `_CANONICAL_KEY_ORDER` gains
  `"verify"` after `"assistants"`, `_effective_overrides` merged branch passes
  `gates=stg.gates` explicitly, `_reject_authoring_output_keys` gains the
  `gates`/`verify` prohibitions, the workflow-less path sets
  `verify_by_id = {}`.

**Routine: `serialize_flow(...)` (changed)**
- Declared `location`: `goga/pipeline/compiler/serialize_flow.py` (existing)
- Gains: `_verify_step_repr(step)` and `_verify_repr(gate)` helpers; the
  `_build_stage_repr` `verify` arm (before the generic `else`).

**Entity: `WorkflowAmendment.contribute` / `PipelineHooks.amend_workflow` (changed, hooks cell)**
- Declared `location`: `goga/pipeline/hooks/amendments.py`, `goga/pipeline/hooks/events.py`
- The document-description enumeration gains `gates`; the per-hook buffer
  duck-check tuple gains `"gates"`; the empty-document discard gains
  `and document.gates is None`; the docstring's step-5 enumeration gains
  "and no gates block".

**Routine: `merge_workflow_overlay(...)` (changed, hooks cell)**
- Declared `location`: `goga/pipeline/hooks/overlay.py`
- Gains: step 4d `_merge_gates(base, contributions)` (the `_merge_repeat`
  shape), step 5b `_STAGE_FIELDS` gains `"gates"` (last) with the automatic
  `None` default in `_STAGE_DEFAULTS`, step-8 carriage
  `gates=_merge_gates(...)` in the rebuilt `WorkflowDocument`.

**Routine: `apply_skip_stages(...)` (changed, pipeline cell)**
- Declared `location`: `goga/pipeline/apply_skip_stages.py`
- Step 3: the replacement `WorkflowStage(skip=True, assistants=…)` carries NO
  gates (the dataclass default `gates=None` provides this — documented in the
  docstring, no code change). Step 4: the rebuilt document gains
  `gates=workflow.gates if workflow is not None else None` (verbatim, same
  object).

### Re-exports

No new re-export blocks (`->Name: {}`) are added by this change. The compiler
imports `WorkflowGates`/`WorkflowGateStep` from `goga/pipeline/workflow` for
use in signatures — not embedding. Each new type's facade obligation belongs
to its own cell's contract (Task 1/Task 4 wire the `__all__` entries).

### Usages Context

- `convention` — `.goga/usages/conventions.md`: mandatory Python rules for
  all code and tests (dataclasses `kw_only=True`, relative intra-package
  imports, Google docstrings, test layout mirroring the source tree, boundary
  parametrized tests, ruff, virtualenv execution). Used by every task; the
  binding subset is extracted into **Mandatory Rules** below.
- `beautiful_yaml` — `.goga/usages/cooks/beautiful_yaml.md`: the `yaml.dump`
  parameter set used by `serialize_flow`; the verify emission rides the same
  dumper — plain scalars for settings, `_BlockLiteralScript` for multi-line
  step strings, no new representer.
- `afm` — `.goga/usages/cooks/afm.md`: the external engine's CLI/flow
  contract. GAP: no verify section exists yet — the verified fact base lands
  with the implementation (Task 10, the assistants-ADR precedent).

### Imported Usages

- `gates` from `goga/pipeline/workflow` —
  Path: `goga/pipeline/workflow/.usages/gates.md` (exists, current, created
  by apply-architecture; carries the prompt-binding row). The authoring
  vocabulary of the consumed instructions; referenced by the compiler header
  Annotations and `compile_flow` Requirements/Constraints.
- `parse-workflow` from `goga/pipeline/workflow` — the parser surface
  overview (gates rows/sections present; current).
- `memory`, `assistants` from `goga/pipeline/workflow` — existing precedents
  (block carriage; attachment compilation) referenced by the same header.

### Local Usages

No `.usages/` creation or update tasks — the design-review verified all four
cell usage files current with the contracts:

- `goga/pipeline/workflow/.usages/gates.md` — status: current (new file,
  created by apply-architecture; single functional domain). Related entities:
  `WorkflowGates`, `WorkflowGateStep`, `parse_workflow`, `compile_flow`.
- `goga/pipeline/workflow/.usages/parse-workflow.md` — current.
- `goga/pipeline/compiler/.usages/compile-flow.md`, `serialize-flow.md` —
  current.
- `goga/pipeline/hooks` and `goga/pipeline` have no `.usages/` directories —
  nothing to update.

### External Dependencies

- afm engine verify contract (external, read-only):
  <https://akopichin.github.io/afm/verify/> — verified 2026-11-09; the full
  confirmed-facts table lives in the design's "Engine verify boundary" trace
  and is transferred into Task 10.
- PyYAML (existing dependency) — workflow parsing and flow serialization.
- pytest / pytest-cov / ruff — test/lint tooling from
  `[project.optional-dependencies] test`. **No new dependencies.**

### Entity Interaction and Data Flow (verbatim from the design)

```
workflow-file text (rendered)
        |
        v
parse_workflow (workflow cell ── leaf, no Imports)
        |  WorkflowDocument{ gates: WorkflowGates|None,
        |                     stages[name].gates: list[WorkflowGateStep]|None }
        v
compile_flow (compiler cell; imports WorkflowGates/WorkflowGateStep + `gates` usage)
        |  4.11 checks  : gates on script stage / planning-only stage -> StructuralError
        |                gates|verify keys in a stage body      -> StructuralError
        |  step 5 build : WorkflowGateStep -> FlowVerifyStep (script->run, agent->command,
        |                wrapper path, "1h" shell default)
        |                WorkflowGates  -> FlowVerify settings (authored keys only)
        |  FlowStage.fields["verify"] = FlowVerify  (canonical slot after "assistants")
        v
serialize_flow (compiler cell)
        |  list form (no authored setting) | container form (steps + settings)
        v
flow-file YAML  ──────────────> afm engine (verify contract — external, see Usages)
        ^
        | overlay path (hooks cell; WorkflowDocument only)
merge_workflow_overlay ── settings block authored-wins (4d), stage gates
        │                 authored-wins field (5b), carriage (8)
        v
amended WorkflowDocument ──> compile_flow
        ^
        | skip path (pipeline cell)
apply_skip_stages ── settings block carried verbatim; replacement stage
        │             carries NO gates (compiler removes the stage first)
        v
skip-merged WorkflowDocument ──> compile_flow
```

Key data-flow rules (verbatim from the design):

1. **Authoring → model**: `gates is not None` ⇔ at least one authored key (the
   parser normalizes emptiness to `None`) — every downstream "authored any
   key" decision reduces to an `is not None` check.
2. **Model → flow**: for every stage name of the working body (after skip
   removal and loop expansion) whose effective gates list is not `None`, one
   `FlowVerify` is built and mapped onto every produced id of that base name;
   the same object is shared across loop copies and deep-copied per stage at
   canonical assembly.
3. **Amendment overlay**: block/field whole, authored-wins, never rebuilt.
4. **Skip rebuild**: settings ride verbatim; the replacement carries no gates.

## Facts

- The four `CODEMANIFEST` files are already materialized on the branch
  (`workflow`, `compiler`, `hooks`, `pipeline`); `goga lint` passes (92 cells,
  0 errors). Both user-approved contract fixes (the 6.1.14 `gates`
  enumeration; the prompt-on-script-step binding) are in the working tree and
  verified by design-review.
- `WorkflowGateStep` sorts before `WorkflowGates` in ASCII (`__all__` order:
  after `WorkflowExtendStage`); `FlowVerify`/`FlowVerifyStep` go after
  `FlowTeamMember`, before `PhaseStep` in the compiler `__all__` and import
  list.
- `_WRAPPER_PATH_TEMPLATE = "/home/goga/bin/{agent}-as-claude.sh"` exists at
  `compile_flow.py:129` (the per-stage agent-override composition precedent).
- `_CANONICAL_KEY_ORDER` currently ends with `"assistants"`
  (`compile_flow.py:74`); the pin test
  `test_compile_flow.py::test_canonical_key_order_includes_approve_and_script_slots`
  asserts `[-7:]` — it must become `[-8:]` ending `["assistants", "verify"]`.
- `_canonical_fields` currently takes
  `(body, stage_name, notes, memory_fields, assistants_fields)`; the signature
  pin test asserts the exact parameter list — it must gain `verify_fields`
  (last, default `None`).
- `_collaboration_emission` is the third companion (called at
  `compile_flow.py:1786`); `_gates_emission` becomes the fourth, right after
  it, so attachment errors fire before gates errors.
- `_STAGE_FIELDS` in `overlay.py` ends with `"assistants"`; `_STAGE_DEFAULTS`
  is `dict.fromkeys(_STAGE_FIELDS)` so appending `"gates"` automatically
  yields the `None` default. The final overlay assembly constructs
  `WorkflowDocument(...)` field-by-field (currently ending `repeat=repeat`) —
  `gates=` must be added explicitly.
- `events.py` duck-check tuple is `("prompt", "stages", "extend", "memory",
  "assistants", "delegation", "repeat")` at `events.py:150`; the emptiness
  discard logs `"tool contributed an empty document; discarded"`.
- `apply_skip_stages.py` builds the replacement `WorkflowStage(...)` at line
  75 and the rebuilt `WorkflowDocument(...)` at line 86.
- No shipped pipeline or fixture authors `gates`/`verify` in a stage body, so
  the new prohibitions break nothing shipped.
- Environment baseline (verified this session): `python3 -m pytest tests/pipeline/workflow tests/pipeline/compiler tests/pipeline/hooks tests/pipeline/test_apply_skip_stages.py -q` → 1348 passed; `python3 -m ruff check goga/ tests/` → all checks passed; `python3 -m ruff format --check goga/ tests/` → 2 pre-existing unrelated files would be reformatted (`tests/commands/pipeline/test_pipeline.py`, `tests/pipeline/test_afm_config.py`) — leave them untouched; the format gate applies to files this plan touches.
- The project's git hooks (`.githooks/commit-msg`, `.githooks/pre-push`)
  reject `Co-Authored-By` trailers; `make install-hooks` wires them.
- `tests/integration/` exists at the tests root for multi-package scenarios
  (precedents: `test_repeat_skip_end_to_end.py`,
  `test_compile_flow_workflow_integration.py`).

## Gap Analysis

- Missing contract entities: `WorkflowGates`, `WorkflowGateStep`,
  `FlowVerifyStep`, `FlowVerify` — none exist yet (new files).
- Missing facade exposure: the four new names are absent from both facades'
  import lists and `__all__`.
- Model gaps: `WorkflowStage`/`WorkflowDocument` lack the `gates` field;
  `parse_workflow` rejects `gates` as an unknown key today (both top level and
  per stage).
- Compiler gaps: no `verify` emission, no canonical slot, no
  `_gates_emission`, no `gates`/`verify` body-key prohibitions (a raw
  `verify` key in a stage body currently passes through to the flow
  verbatim — the accidental passthrough this feature closes); the
  `_effective_overrides` merged branch drops the stages-block gates unless
  extended.
- Serializer gap: `_build_stage_repr` has no `verify` arm.
- Hooks gaps: `_merge_gates` absent; `_STAGE_FIELDS` lacks `gates`; the
  events emptiness enumeration would discard a gates-only contribution.
- Pipeline gap: `apply_skip_stages` drops the settings block on rebuild
  unless carried explicitly.
- Test coverage gaps: no `test_*_gates*`/`test_*verify*` files exist; the
  stage/document contract pins and the compile-flow signature/order pins do
  not yet include `gates`/`verify`.
- Documentation gaps: `docs/features/pipelines/workflows.md` has no gates
  section; `.goga/usages/cooks/afm.md` has no verify fact base.
- Existing code that can be reused: `_build_repeat` (the `_merge_gates` /
  `_build_gates` shape), `_assistant_repr` (the `_verify_step_repr` shape),
  `_collaboration_emission` (the companion shape), the
  `test_flow_repeat_contract.py` pattern (the four model-contract test files),
  the `test_serialize_flow_repeat_slot.py` pattern (the verify slot tests).
- Unrelated working-tree change (`goga/assets/afm/skin/goga.css`) — out of
  scope; leave it alone.

---

## Mandatory Rules

Extracted from the project convention (`.goga/usages/conventions.md` — the
`convention` practice referenced by every CODEMANIFEST) and the Python
language rules (`goga-cell-python`): **binding on every task in this plan**.
Where a contract annotation is more specific, the contract wins; where it is
silent, these rules decide.

### R1 — Coding style (strictly per the convention)

- Python **3.10+ only**; all tool configuration via `pyproject.toml`; no new
  third-party dependencies (anything new would require a minimum version in
  `pyproject.toml` — this plan adds none).
- **Execute all code and tests inside a virtualenv** — create it if missing
  (`python3 -m venv .venv && .venv/bin/pip install -e '.[test]'`); the
  current environment already provides one.
- **Relative imports for all intra-package references**
  (`from .workflow_gates import WorkflowGates`); absolute imports only for
  stdlib and third-party. Exception — inside `tests/`, cross-directory
  references use absolute imports rooted at the `tests` package
  (`from tests.conftest import is_kw_only_dataclass`).
- **Data models via the stdlib `dataclasses` module with `kw_only=True`**;
  `None` only for the explicit absence of a value; fixed declaration field
  order exactly as the contract states (the emission order).
- **Type hints mandatory**; signatures use `str`, `int`, `float`, `bool`,
  `list[T]`, `dict[str, T]`, `T | None` — no `*args`/`**kwargs`, no
  unparametrized `dict`/`list` (contract signatures govern; internal helpers
  follow the same idiom).
- **Naming**: PascalCase classes; snake_case functions, methods, properties
  (`goga-cell-python`).
- **Google-style docstrings mandatory** on all public functions, methods, and
  classes: first line capitalized and ending with a period; `Args` when the
  function accepts parameters; `Returns` when it returns a value; `Raises`
  when it raises beyond built-in types. CLI command callbacks are the only
  exception (omit `Args`/`Returns`/`Raises`; keep the summary line; use
  `\f` to hide developer notes) — no CLI surface changes in this plan.
- **Blank-line discipline** inside function/method bodies: one blank line
  between logical blocks (initialization vs conditions/loops; data
  preparation vs processing; processing vs return).
- **Logging**: none added anywhere in this feature (the design pins this —
  the gates path emits no logs; if a log were ever needed, `logging` with
  structured `extra` metadata and lowercase messages).

### R2 — Test writing (strictly per the convention)

- **pytest** runs tests; **ruff** lints/formats test code; test libraries
  come only from `[project.optional-dependencies] test`.
- **Tests mirror the source structure directly**:
  `goga/pipeline/workflow/workflow_gates.py` →
  `tests/pipeline/workflow/test_workflow_gates.py`. Each test directory has
  an `__init__.py`. Local fixtures in `tests/<package>/conftest.py`, shared
  fixtures in `tests/conftest.py`. Multi-package integration tests go to
  `tests/integration/` (`test_<scenario>.py`).
- **Naming**: files `test_<module>.py`; functions
  `test_<what>_<scenario>` (e.g. `test_complexity_with_empty_input`);
  grouping `class Test<Component>:`; self-documenting names, minimal
  comments.
- **Coverage**: unit tests for every public function/method/class — main
  scenario and typical data; edge cases for empty inputs (`None`, `""`,
  `[]`, `{}`), boundary values (`0`, negative, very large), invalid types,
  and expected exceptions via `pytest.raises`; integration tests only for
  interaction between modules/packages (never as a substitute for unit
  tests).
- **Boundary tests** for thresholds/ranges use `@pytest.mark.parametrize`
  with a table of values including each boundary (the `>= 0` bounds and the
  full structural-error table in Task 3 are exactly this shape).
- **Mocks**: pure logic — no mocks (this whole feature is pure); file I/O —
  only the `tmp_path` fixture (`compile_flow` pipeline-in/flow-out); mock at
  external boundaries only. Nothing here needs `mock.patch`.
- **Strict errors**: every parser/compiler rejection is pinned with
  `with pytest.raises(WorkflowSyntaxError, match=re.escape(msg))` (or
  `StructuralError`) using the exact one-line message texts — the messages
  are normative.
- **REST/CLI testing** (not applicable here): call the handler function
  directly via Python call.

### R3 — Linters and formatters at every stage and every local commit

- **ruff is the project's linter AND formatter**, configured in
  `pyproject.toml` (`target-version = "py310"`, `line-length = 120`, the
  full rule selection `E W F I N UP B SIM PL PLR C4 DTZ PT ARG RUF PTH C90`
  with `max-complexity = 10`, per-file ignores for `tests/**`, and
  `[tool.ruff.format]` double quotes / LF / magic trailing comma).
- **Every development stage**: each coding task below ends with its Lint
  step and no task is complete until BOTH pass:
  - `python3 -m ruff check goga/ tests/` — zero errors;
  - `python3 -m ruff format --check <files touched by this task>` — clean
    (fix with `python3 -m ruff format <files>`; never reformat the two
    pre-existing unrelated offenders listed in Facts).
- **Every local commit**: before any `git commit` made during execution, the
  committing task's full gate must be green in that working tree —
  `ruff check`, the scoped `ruff format --check`, and the task's test
  command. Never commit with a red gate; never `--no-verify` past it.
- **Commit messages carry no `Co-Authored-By` trailers** — the project's
  `commit-msg`/`pre-push` hooks reject them (project policy: no co-authorship
  trailers in git history). Run `make install-hooks` once before the first
  commit if hooks are not wired.
- McCabe `max-complexity = 10` is a decomposition signal: if `ruff check`
  flags complexity, decompose into internal helpers (allowed within the
  cell) rather than suppressing.

### R4 — REPL development cycle (continuous evaluation, hot reload, migration to source)

The workflow of every coding task is structured around a REPL loop, per the
CODEMANIFEST header Annotations of all four cells (the `convention` practice
is used for "Organizing the REPL development cycle"); the concrete protocol
is elaborated here:

- **Work inside the virtualenv REPL** — every interactive evaluation runs as
  `python3 -i` (or `python3 - <<…` scratch invocations) against the installed
  working tree, never against a stale interpreter or an ad-hoc script outside
  the repo.
- **Continuous interactive evaluation** — while implementing each unit, keep
  a live REPL session exercising the real artifacts: feed workflow-file
  snippets to `parse_workflow`, inspect the built
  `WorkflowGates`/`WorkflowGateStep` models, drive `compile_flow` on
  `tmp_path` pipeline fixtures and read the emitted flow text. Evaluate
  behavior by observing real outputs (model fields, YAML text, raised error
  messages) — not by reading code.
- **Hot reloading** — after every source edit, reload the touched module in
  the session (`importlib.reload(goga.pipeline.workflow.parse_workflow)` and
  every dependent re-import) or restart the REPL entry, so evaluation always
  executes the current code; never reason from pre-edit state. For
  `compile_flow`/`serialize_flow` chains, prefer fresh subprocess runs
  (`python3 -c …`) when reload ordering across modules gets fragile.
- **Code migration to source files** — the REPL is scratch: every snippet
  that works (a validator arm, an emission branch, a serializer helper) is
  migrated into its target module with convention-compliant naming, type
  hints, and docstrings before the step counts as done. No behavior may live
  only in a REPL session; the deliverable is the module plus its tests.
- **REPL findings become tests** — whenever REPL exploration confirms a
  behavior (an exact error line, an emission shape, an indentation level of
  the dumper), pin it immediately as a formal test in the task's test file;
  the formal suite — not the REPL — is the completion authority.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow). Order: `goga/pipeline/workflow` → `goga/pipeline/compiler` → `goga/pipeline/hooks` → `goga/pipeline` → riders → full sweep.

### Task 1: Workflow gates data models — `WorkflowGates` + `WorkflowGateStep` (TDD coding)

Create the two new workflow-cell data models (pure data, no validation, no
interpretation) and export them from the facade. Covers contract entities
`WorkflowGates` (`workflow_gates.py`) and `WorkflowGateStep`
(`workflow_gate_step.py`) in `goga/pipeline/workflow`.

**Usages relevant to this task:**
- `convention`: `@dataclass(kw_only=True)` models, Google docstrings, module
  docstrings mirroring `workflow_repeat.py`, relative imports
  (`from .workflow_gates import WorkflowGates`), snake_case/PascalCase naming.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: declare Task 1 (workflow gates data models) being executed
- [x] **Contract tests**: create `tests/pipeline/workflow/test_workflow_gates_contract.py` and `tests/pipeline/workflow/test_workflow_gate_step_contract.py` (the `test_flow_repeat_contract.py` pattern): facade importability + `__all__` membership (`WorkflowGateStep` sorts before `WorkflowGates`, after `WorkflowExtendStage`), `is_kw_only_dataclass` (from `tests.conftest`), fixed field order via `dataclasses.fields` (`WorkflowGates`: patience, max_iterations, fresh_correction; `WorkflowGateStep`: name, script, agent, timeout, prompt), defaults all `None` except the required `name`, authored-zero preservation (`WorkflowGates(patience=0, max_iterations=0)` keeps `0` — a value, not an omission) — expected to fail at this stage
- [x] **Code**: create `goga/pipeline/workflow/workflow_gates.py` — `@dataclass(kw_only=True)` `WorkflowGates` with `patience: int | None = None`, `max_iterations: int | None = None`, `fresh_correction: bool | None = None` (fixed order); module + Google docstrings mirroring `workflow_repeat.py`
- [x] **Code**: create `goga/pipeline/workflow/workflow_gate_step.py` — `@dataclass(kw_only=True)` `WorkflowGateStep` with `name: str` (required, no default), `script: str | None = None`, `agent: str | None = None`, `timeout: str | None = None`, `prompt: str | None = None` (fixed order)
- [x] **Code**: export both from `goga/pipeline/workflow/__init__.py` — relative imports in module order and `__all__` entries `WorkflowGateStep`, `WorkflowGates` after `WorkflowExtendStage`
- [x] **REPL checkpoint**: in the virtualenv REPL, construct `WorkflowGates(patience=1)`, `WorkflowGateStep(name="t", script="pytest -q")` and an authored-zero instance; observe the fields — then reload (`importlib.reload`) after any edit
- [x] **Interface verification**: `python3 -m pytest tests/pipeline/workflow/test_workflow_gates_contract.py tests/pipeline/workflow/test_workflow_gate_step_contract.py -v` — all pass
- [x] **Logic tests**: defaults carry no authored key; exactly-one-of `script`/`agent` is a parse-time guarantee (assert the dataclass accepts what the parser will thread — the model itself performs no exclusivity check); `name` has no default (`pytest.raises(TypeError)` on missing)
- [x] **Debugging**: `python3 -m pytest tests/pipeline/workflow -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade `__all__` and importability match the CODEMANIFEST obligation; field names/order/types match the declared properties
- [x] **Lint**: `python3 -m ruff check goga/pipeline/workflow/ tests/pipeline/workflow/` and `python3 -m ruff format --check goga/pipeline/workflow/workflow_gates.py goga/pipeline/workflow/workflow_gate_step.py goga/pipeline/workflow/__init__.py tests/pipeline/workflow/test_workflow_gates_contract.py tests/pipeline/workflow/test_workflow_gate_step_contract.py` — fix formatting if necessary
- [x] **Completion**: mark checkboxes complete

### Task 2: Thread `gates` through `WorkflowStage` and `WorkflowDocument` (TDD coding)

Add the trailing `gates` field to the two existing workflow-cell models.
Covers changed entities `WorkflowStage` (`workflow_stage.py`) and
`WorkflowDocument` (`workflow_document.py`).

**Usages relevant to this task:**
- `convention`: `kw_only=True` dataclass fields with `None` default for
  explicit absence; field order pins belong in the contract tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: declare Task 2 (model threading) being executed
- [x] **Contract tests**: extend `tests/pipeline/workflow/test_workflow_stage_contract.py` — the `dataclasses.fields` order pin gains `gates` last (after `assistants`), default `None`; extend `tests/pipeline/workflow/test_workflow_document_contract.py` — the order pin gains `gates` last (after `repeat`), default `None` — expected to fail at this stage
- [x] **Code**: `goga/pipeline/workflow/workflow_stage.py` — trailing field `gates: list[WorkflowGateStep] | None = None` after `assistants` (relative import of the type per convention); docstring gains the field description
- [x] **Code**: `goga/pipeline/workflow/workflow_document.py` — trailing field `gates: WorkflowGates | None = None` after `repeat`; docstring gains the field description
- [x] **REPL checkpoint**: in the REPL, build `WorkflowStage(prompt="x", gates=[WorkflowGateStep(name="g", script="echo ok")])` and `WorkflowDocument(gates=WorkflowGates(max_iterations=1))`; observe `[f.name for f in fields(...)]` ending in `gates`
- [x] **Interface verification**: `python3 -m pytest tests/pipeline/workflow/test_workflow_stage_contract.py tests/pipeline/workflow/test_workflow_document_contract.py -v` — all pass
- [x] **Logic tests**: default construction leaves `gates is None` on both models (existing callers unchanged)
- [x] **Debugging**: `python3 -m pytest tests/pipeline/workflow -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: both models keep their declared API; every existing construction site stays valid without edits (additive law)
- [x] **Lint**: `python3 -m ruff check goga/ tests/` + `python3 -m ruff format --check` on the touched files — fix formatting if necessary
- [x] **Completion**: mark checkboxes complete

### Task 3: `parse_workflow` gates validation surface (TDD coding)

Implement the parser side: the top-level settings block, the per-stage
check-step list, the extend prohibition, and the empty-workflow rule. Covers
the `parse_workflow` contract steps 4/5/6.1.2/6.1.15/6.10/6.11/7/8 in
`goga/pipeline/workflow/parse_workflow.py`.

**Usages relevant to this task:**
- `convention`: parametrized boundary tables, `pytest.raises` with exact
  messages, pure-function tests without mocks, REPL evaluation of parser
  output before pinning tests.
- `parse-workflow` (imported from `goga/pipeline/workflow/.usages/parse-workflow.md`):
  the parser-surface overview this task must stay consistent with — the
  top-level key list and per-stage table already carry the gates rows; the
  implemented surface (keys, errors, emptiness rules) must match what it
  documents.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: declare Task 3 (parser gates surface) being executed
- [x] **Contract tests**: create `tests/pipeline/workflow/test_parse_workflow_gates.py` with the positive tests below (they fail at this stage — `gates` is an unknown key today)

Context — `_build_gates` algorithm (per contract 6.10; mirrors `_build_repeat`; verbatim from the design):

```
1. IF gates_raw is None: RETURN None
2. FOR key, value in gates_raw.items():        # authored order, first defect raises
     patience / max_iterations:
       bool or non-int  -> raise "non-int value in workflow.gates.KEY"
       < 0              -> raise "KEY must be >= 0 in workflow.gates"
     fresh_correction:
       non-bool         -> raise "non-bool value in
                                  workflow.gates.fresh_correction"
     other key          -> raise "unknown key in workflow.gates: KEY; valid
                                  keys: patience, max_iterations,
                                  fresh_correction"
3. IF gates_raw is empty: RETURN None          # empty block equals absence
4. RETURN WorkflowGates(patience=…, max_iterations=…, fresh_correction=…)
   # authored keys only — absent keys stay None
```

Context — `_build_stage_gates` algorithm (per contract 6.1.15; check order is normative; verbatim from the design):

```
1. IF value is not a list:
     raise "non-list gates in workflow.stages.NAME"
2. IF value is empty: RETURN None            # empty list equals absence
3. FOR i, step in enumerate(value):
   a. IF step is not a dict:
        raise "non-mapping gate step in workflow.stages.NAME.gates[i]"
   b. IF any key outside {name, script, agent, timeout, prompt}:
        raise "unknown key in workflow.stages.NAME.gates[i]: KEY;
              valid keys: name, script, agent, timeout, prompt"
   c. IF "name" not in step:
        raise "gates step without name in workflow.stages.NAME.gates[i]"
      IF step["name"] is not a str:
        raise "non-str value in workflow.stages.NAME.gates[i].name"
   d. IF ("script" in step) == ("agent" in step):        # both or neither
        raise "gates step must carry exactly one of script/agent in
               workflow.stages.NAME.gates[i]"
   e. IF step["script"] is not a non-empty str:
        raise "script must be a non-empty string in
               workflow.stages.NAME.gates[i]"            # agent counterpart
   f. IF "timeout" in step and not a str:
        raise "non-str value in workflow.stages.NAME.gates[i].timeout"
      IF "prompt" in step and not a str:
        raise "non-str value in workflow.stages.NAME.gates[i].prompt"
   g. IF "prompt" in step and "script" in step:
        raise "prompt is forbidden on a script gate step in
               workflow.stages.NAME.gates[i]"            # Applied Fixes
4. RETURN [WorkflowGateStep(...) for each step]          # authored order
```

- [x] **Contract tests (positive, from the design's test stack trace)**:
  - `test_gates_settings_block_alone_is_valid` — input `"gates:\n  patience: 1\n"`; assert `doc.gates.patience == 1`, `doc.gates.max_iterations is None`, `doc.gates.fresh_correction is None`, and `doc.prompt is None and doc.stages == {}` (a gates-only workflow is valid content)
  - `test_stage_gates_steps_built_in_authored_order` — input: stage `implement` with two steps (`name: Unit tests, script: pytest -q, timeout: 30m` and `name: Code review, agent: codex, prompt: Review the diff for correctness.`); assert 2 steps in authored order with verbatim `script`/`timeout`/`agent`/`prompt`
  - `test_empty_settings_block_and_empty_list_equal_absence` — input `"gates: {}\nstages:\n  a:\n    gates: []\n    prompt: x\n"`; assert `doc.gates is None` and `doc.stages["a"].gates is None`
  - `test_authored_zero_is_a_value` — input `"gates: {patience: 0, max_iterations: 0}\n"`; assert both `== 0` and `is not None`
- [x] **Code**: `_extract_top_level` becomes a 10-tuple — new dispatch arm `elif key == "gates": gates_raw = _validate_top_level_mapping("non-mapping gates block in workflow", value)`; `_TOP_LEVEL_KEYS` gains `"gates"` appended last (the unknown-key message enumerates `…, delegation, repeat, gates`)
- [x] **Code**: implement `_build_gates(gates_raw)` per the algorithm above; empty block → `None`; else `WorkflowGates` from authored keys only
- [x] **Code**: `_validate_stage_field` gains the arm `elif key == "gates": return _build_stage_gates(name, field_value)`; `_STAGE_KEYS` gains `"gates"` (unknown-key message `…, memory, assistants, gates` per 6.1.2)
- [x] **Code**: implement `_build_stage_gates(name, value)` per the algorithm above — non-list / empty→None / per-step checks in the normative order (key set → name → exclusivity → non-empty → types → prompt binding) → `WorkflowGateStep` list in authored order
- [x] **Code**: `_build_stage` construction gains `gates=fields.get("gates")` (contract 6.1.14 enumerates it); `WorkflowDocument(..., repeat=repeat, gates=gates)`; `_reject_forbidden_extend_keys` tuple gains `"gates"` → message `"gates is forbidden in workflow.extend.NAME"` (contract 6.11)
- [x] **Code**: empty-workflow rule condition gains `and gates is None`; message ends `…, the repeat block, or the gates block`; new constants `_GATES_KEYS = ("patience", "max_iterations", "fresh_correction")` and `_GATE_STEP_KEYS = ("name", "script", "agent", "timeout", "prompt")` (message sources, mirroring `_REPEAT_KEYS`); `parse_workflow` docstring `Raises` extended with the gates cases
- [x] **REPL checkpoint**: in the REPL, run `parse_workflow` on each positive input and on 2–3 malformed inputs; observe the model and the exact error lines; hot-reload `parse_workflow` after each edit before re-evaluating; pin every observed error line into the parametrized table
- [x] **Interface verification**: `python3 -m pytest tests/pipeline/workflow/test_parse_workflow_gates.py -v` — positive tests pass
- [x] **Logic tests (negative, parametrized table — verbatim from the design; `with pytest.raises(WorkflowSyntaxError, match=re.escape(msg))`)**:
  ```
  "gates: 5"                                  → "non-mapping gates block in workflow"
  "gates: {patiance: 1}"                      → "unknown key in workflow.gates: patiance; valid keys: patience, max_iterations, fresh_correction"
  "gates: {patience: true}"                   → "non-int value in workflow.gates.patience"
  "gates: {max_iterations: -1}"               → "max_iterations must be >= 0 in workflow.gates"
  "gates: {fresh_correction: 1}"              → "non-bool value in workflow.gates.fresh_correction"
  "stages: {a: {gates: {name: x}}}"           → "non-list gates in workflow.stages.a"
  "stages: {a: {gates: [pytest]}}"            → "non-mapping gate step in workflow.stages.a.gates[0]"
  "stages: {a: {gates: [{script: x}]}}"       → "gates step without name in workflow.stages.a.gates[0]"
  "stages: {a: {gates: [{name: 1, script: x}]}}" → "non-str value in workflow.stages.a.gates[0].name"
  "stages: {a: {gates: [{name: x}]}}"         → "gates step must carry exactly one of script/agent in workflow.stages.a.gates[0]"
  "stages: {a: {gates: [{name: x, script: y, agent: z}]}}" → "gates step must carry exactly one of script/agent in workflow.stages.a.gates[0]"
  "stages: {a: {gates: [{name: x, script: \"\"}]}}" → "script must be a non-empty string in workflow.stages.a.gates[0]"
  "stages: {a: {gates: [{name: x, script: y, timeout: 5}]}}" → "non-str value in workflow.stages.a.gates[0].timeout"
  "stages: {a: {gates: [{name: x, script: y, prompt: z}]}}" → "prompt is forbidden on a script gate step in workflow.stages.a.gates[0]"
  "stages: {a: {gates: [{name: x, agent: y, extra: 1}]}}" → "unknown key in workflow.stages.a.gates[0]: extra; valid keys: name, script, agent, timeout, prompt"
  "extend: {n: {after: [a], gates: [...]}}"   → "gates is forbidden in workflow.extend.n"
  ```
  (rows are workflow YAML texts; the `agent` counterparts — `agent must be a non-empty string…`, `non-str … .prompt` on an agent step — join the same table)
- [x] **Debugging**: `python3 -m pytest tests/pipeline/workflow -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: unknown top-level/stage keys still reject with the extended enumerations; existing parse behavior for gate-free workflows unchanged (the full workflow suite passes)
- [x] **Lint**: `python3 -m ruff check goga/ tests/` + `python3 -m ruff format --check` on the touched files — fix formatting if necessary
- [x] **Completion**: mark checkboxes complete

### Task 4: Compiler verify emission models — `FlowVerifyStep` + `FlowVerify` (TDD coding)

Create the two compiler-cell emission models and export them from the
facade. Covers `FlowVerifyStep` (`flow_verify_step.py`) and `FlowVerify`
(`flow_verify.py`) in `goga/pipeline/compiler`.

**Usages relevant to this task:**
- `convention`: `kw_only=True` dataclasses, Google docstrings (module
  docstrings mirroring `flow_repeat.py`), relative imports, contract-test
  pattern.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: declare Task 4 (compiler verify models) being executed
- [x] **Contract tests**: create `tests/pipeline/compiler/test_flow_verify_step_contract.py` and `tests/pipeline/compiler/test_flow_verify_contract.py` (the `test_flow_repeat_contract.py` pattern): facade importability + `__all__` membership, `is_kw_only_dataclass`, fixed field order (`FlowVerifyStep`: name, run, command, timeout, prompt; `FlowVerify`: steps, max_failures, review_patience, fresh_correction), defaults `None` with `steps` required (`pytest.raises(TypeError)` on missing), authored-zero preservation — expected to fail at this stage
- [x] **Code**: create `goga/pipeline/compiler/flow_verify_step.py` — `@dataclass(kw_only=True)` `FlowVerifyStep`: `name: str` (required), `run: str | None = None`, `command: str | None = None`, `timeout: str | None = None`, `prompt: str | None = None` (fixed order — the emission order of the step keys)
- [x] **Code**: create `goga/pipeline/compiler/flow_verify.py` — `@dataclass(kw_only=True)` `FlowVerify`: `steps: list[FlowVerifyStep]` (required, no default), `max_failures: int | None = None`, `review_patience: int | None = None`, `fresh_correction: bool | None = None` (fixed order — the emission order of the block keys); docstring notes that an instance carrying no authored setting IS the list emission form
- [x] **Code**: export both from `goga/pipeline/compiler/__init__.py` — relative imports and `__all__` entries `FlowVerify`, `FlowVerifyStep` after `FlowTeamMember`, before `PhaseStep`
- [x] **REPL checkpoint**: in the REPL, construct `FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")])` and a settings-carrying instance; observe the fields
- [x] **Interface verification**: `python3 -m pytest tests/pipeline/compiler/test_flow_verify_step_contract.py tests/pipeline/compiler/test_flow_verify_contract.py -v` — all pass
- [x] **Logic tests**: defaults carry no authored setting; `steps` has no default; authored `0` on `max_failures`/`review_patience` stays `0`
- [x] **Debugging**: `python3 -m pytest tests/pipeline/compiler -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade `__all__` matches the CODEMANIFEST obligation; field names/order/types match the declared properties
- [x] **Lint**: `python3 -m ruff check goga/ tests/` + `python3 -m ruff format --check` on the touched files — fix formatting if necessary
- [x] **Completion**: mark checkboxes complete

### Task 5: `serialize_flow` verify emission (TDD coding)

Implement the serializer side: the `verify` arm and the two helpers. Covers
the `serialize_flow` contract changes in
`goga/pipeline/compiler/serialize_flow.py`. Runs BEFORE the compile task:
`compile_flow` writes its output through `serialize_flow`, and the compile
task's positive tests assert on the serialized flow text — the `verify` arm
must already exist for them to pass (a raw `FlowVerify` reaching the repr
dict is a YAML RepresenterError); this task's tests construct `FlowDocument`
directly and depend only on the Task-4 models.

**Usages relevant to this task:**
- `beautiful_yaml`: the existing `_CanonicalDumper` parameter set — plain
  scalars for settings, `_BlockLiteralScript` iff a `str` contains `"\n"` (the
  script-family pattern); no new representer.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: declare Task 5 (serialize_flow verify emission) being executed
- [x] **Contract tests**: create `tests/pipeline/compiler/test_serialize_flow_verify_slot.py` (the `test_serialize_flow_repeat_slot.py` pattern — direct `FlowDocument` construction). Expected to fail at this stage.
- [x] **Code**: `_verify_step_repr(step)` (mirrors `_assistant_repr`): ordered mapping `name` → `run` xor `command` (whichever is not `None`) → `timeout` (when not `None`) → `prompt` (when not `None`); each of `run`/`command`/`timeout`/`prompt` wrapped in `_BlockLiteralScript` iff it is a `str` containing `"\n"`
- [x] **Code**: `_verify_repr(gate)`: no authored setting (`max_failures is None and review_patience is None and fresh_correction is None`) → the steps list (the engine list form); else the ordered container `{"steps": [...]}` then present settings only, fixed order `max_failures`, `review_patience`, `fresh_correction` (plain scalars; step fields NEVER at the container top level — engine parse error)
- [x] **Code**: `_build_stage_repr` gains the arm before the generic `else`: `elif key == "verify" and isinstance(value, FlowVerify): stage_repr[key] = _verify_repr(value)`; import `FlowVerify`/`FlowVerifyStep` (relative); docstring updated
- [x] **REPL checkpoint**: in the REPL, serialize the two test documents; observe the exact indentation (list form: dashes under `verify:` at 2 spaces, fields at 4; container form: `steps:` at 4, dashes at 4, step fields at 6) and the block-literal `|` prompt; pin the observed substrings
- [x] **Interface verification**: `python3 -m pytest tests/pipeline/compiler/test_serialize_flow_verify_slot.py -v` — all pass
- [x] **Logic tests (from the design's test stack trace)**:
  - `test_verify_list_form_is_the_steps_list` — `FlowStage(fields={"prompt": "Do", "verify": FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")])})`; assertions: `"verify:\n" in text`, no `steps:` in the verify block (list, not container), `"- name: t\n" in text`
  - `test_verify_container_form_fixed_order_and_multiline_prompt` — `FlowVerify(steps=[FlowVerifyStep(name="r", command="/x/y.sh", prompt="line1\nline2")], max_failures=3, review_patience=1)`; assertions: `"verify:\n    steps:\n" in text`, `"    max_failures: 3\n" in text`, `"    review_patience: 1\n" in text`, `text.index("steps:") < text.index("max_failures:") < text.index("review_patience:")`, `"      prompt: |\n" in text` (REPL note: with the plan's no-trailing-newline prompt the dumper writes the strip-chomping `|-`; the `|` assertion is pinned with a trailing-newline prompt and `|-` with the plan's exact data — both observed forms covered)
- [x] **Debugging**: `python3 -m pytest tests/pipeline/compiler -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: a stage without a gate never enters the arm — no `verify` key in the output, byte-identical text; the existing serializer suite stays green
- [x] **Lint**: `python3 -m ruff check goga/ tests/` + `python3 -m ruff format --check` on the touched files — fix formatting if necessary
- [x] **Completion**: mark checkboxes complete

### Task 6: `compile_flow` gates emission — `_gates_emission`, canonical slot, prohibitions (TDD coding)

Implement the compiler's gates translation: the fourth emission companion,
the effective-override merge fix, the `verify` canonical slot, and the
`gates`/`verify` authoring-key prohibitions. Covers the `compile_flow`
contract changes in `goga/pipeline/compiler/compile_flow.py`.

**Usages relevant to this task:**
- `gates` (imported from `goga/pipeline/workflow/.usages/gates.md`): the
  authoring vocabulary consumed — per-stage check steps and the settings
  block, translated per the `_gates_emission` algorithm below (script → run,
  agent → command via the wrapper path, patience → review_patience,
  max_iterations → max_failures, fresh_correction unchanged).
- `memory`, `assistants` (imported from `goga/pipeline/workflow/.usages/`):
  the existing precedents this task mirrors — the block-carriage shape
  (`memory`) and the attachment-emission companion shape (`assistants`:
  `_collaboration_emission`, `_assemble_assistants`, the per-stage
  shared-list-then-deep-copy discipline).
- `afm`: the emitted verify contract (fact base lands in Task 10; the
  verified shapes are embedded in this task's assertions).
- `convention`: `tmp_path` for the pipeline-in/flow-out fixtures; exact
  substring assertions on serialized text.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: declare Task 6 (compile_flow gates emission) being executed
- [x] **Contract tests**: create `tests/pipeline/compiler/test_compile_flow_gates.py` (fixtures: STAGES-format pipeline text constants — the `test_compile_flow_memory.py` pattern — plus `parse_workflow(text)` workflow docs); extend `tests/pipeline/compiler/test_compile_flow.py` pins (below). Expected to fail at this stage.

Context — `_gates_emission` algorithm (verbatim from the design):

```
1. gates_settings = workflow.gates                # WorkflowGates | None
2. bodies = {step.name: step.body for step in expanded}
3. verify_by_id = {}
4. FOR base_name, produced_ids in expanded_ids.items():
     stage  = effective.get(base_name)
     gates  = stage.gates if stage is not None else None
     IF gates is None: CONTINUE
     body = bodies[produced_ids[0]]               # the original; copies share shape
     IF "script" in body:
       raise "gates are forbidden on a script stage in
              workflow.stages.{base_name}"
     IF _translate_body_agents(body) == ["planning"]:
       raise "gates are forbidden on a planning-only stage in
              workflow.stages.{base_name}"
     steps = []
     FOR gs in gates:                             # authored order
       IF gs.script is not None:
         steps.append(FlowVerifyStep(
           name=gs.name, run=gs.script,
           timeout=(gs.timeout if gs.timeout is not None else "1h"),
           prompt=gs.prompt))                     # None by the parse guarantee
       ELSE:
         steps.append(FlowVerifyStep(
           name=gs.name,
           command=_WRAPPER_PATH_TEMPLATE.format(agent=gs.agent),
           timeout=gs.timeout, prompt=gs.prompt)) # no AI default
     IF gates_settings is not None:               # ⇔ authored any key
       verify = FlowVerify(steps=steps,
         max_failures=gates_settings.max_iterations,
         review_patience=gates_settings.patience,
         fresh_correction=gates_settings.fresh_correction)
     ELSE:
       verify = FlowVerify(steps=steps)           # list form
     FOR pid in produced_ids: verify_by_id[pid] = verify
5. RETURN verify_by_id
```

- [x] **Code**: implement `_gates_emission(workflow, effective, expanded, expanded_ids) -> dict[str, FlowVerify]` per the algorithm; call it as the fourth companion immediately after `_collaboration_emission` (attachment errors fire before gates errors); `workflow.gates is None` cannot reach here with gated stages — the settings source is `workflow.gates`
- [x] **Code**: `_effective_overrides` merged branch (extend + stages-block entry for the same name) gains `gates=stg.gates` in the explicit per-field pass — omitting it silently drops the gate; extend-seeded entries keep the constructor default `None` (gates is stages-block-only); docstring updated
- [x] **Code**: `_canonical_fields` signature gains `verify_fields: FlowVerify | None = None` (last parameter); new `_assemble_verify(source, verify_fields)` assigns `source["verify"]` when not `None` — BEFORE the canonical loop (the `_assemble_assistants` pattern); `_CANONICAL_KEY_ORDER` gains `"verify"` after `"assistants"` (comment block extended with the verify sentence); both PHASES and STAGES branches pass `verify_fields=verify_by_id.get(step.name)`; workflow-less path sets `verify_by_id = {}` (the `_MemoryEmission` default mirror); docstrings (Args/Raises/Returns) extended
- [x] **Code**: `_reject_authoring_output_keys` gains the prohibitions (same pass as `buttons`/`reflect`/`memory_use`/`assistants`, running from `_canonical_fields` on every produced copy — pipeline-file stage OR embedded extend-stage body): `"gates" in body` → `StructuralError("gates key is forbidden in stage body; use gates in workflow.stages")`; `"verify" in body` → `StructuralError("verify key is forbidden in stage body; use gates in workflow.stages")`
- [x] **REPL checkpoint**: in the REPL (fresh `python3 -c`/`python3 -i` runs per edit — the compile chain spans modules), compile the Task-6 positive fixtures on `tmp_path`; observe the emitted flow text (slot position, `1h` default, container vs list form) before pinning the substring assertions; confirm a gate-free workflow still compiles to identical text
- [x] **Interface verification**: `python3 -m pytest tests/pipeline/compiler/test_compile_flow_gates.py -v` — positive tests pass
- [x] **Logic tests (positive — from the design's test stack trace)**:
  - `test_gated_stage_compiles_verify_with_steps_and_materialized_timeout` — one prompt stage `build`, gate step `name: compile, script: make all`, no settings block; assertions (exact substrings; the canonical dumper aligns block-sequence dashes with the parent key, stage fields at 2 spaces): `"verify:\n" in text`, `"  - name: compile\n" in text`, `"    run: make all\n" in text`, `"    timeout: 1h\n" in text`, `text.index("verify:") > text.index("prompt:")`, `"max_failures" not in text`
  - `test_ai_step_command_composed_from_agent_wrapper_path` — gate step `name: Check, agent: codex, prompt: "Be strict.", timeout: 15m`; assertions: `"- name: Check\n" in text`, `"command: /home/goga/bin/codex-as-claude.sh\n" in text`, `"timeout: 15m\n" in text`, `"prompt: 'Be strict.'\n" in text or "prompt: Be strict.\n" in text` (per dumper quoting); no default timeout materialized
  - `test_settings_block_authors_container_form_on_every_gated_stage` — two gated stages `a`, `b`; settings `gates: {max_iterations: 2, fresh_correction: true}`; assertions: `text.count("steps:\n") == 2`, `"max_failures: 2\n" in text`, `"fresh_correction: true\n" in text`, `"review_patience" not in text`
  - `test_loop_expanded_copies_carry_the_same_gate` — stage `check` with `loop: 2` and a gate step; assertions: `text.count("verify:\n") == 2`, `"- id: check-1\n" in text and "- id: check-2\n" in text`
- [x] **Logic tests (negative)**:
  - `test_gates_on_script_stage_rejected` — pipeline stage `s` with `script: make check`, workflow `stages: {s: {gates: [{name: g, script: pytest}]}}`; `pytest.raises(StructuralError, match="gates are forbidden on a script stage in workflow.stages.s")`
  - `test_gates_on_planning_only_stage_rejected` — stage with `roles: [planner]` gated → `match="gates are forbidden on a planning-only stage in workflow.stages.p"`; plus a twin with `roles: [planning]` (already-afm name) proving the `_translate_body_agents` comparison
  - `test_gates_and_verify_keys_forbidden_in_stage_body` (parametrized) — stage bodies carrying `gates: []` / `verify: "make test"` (also one embedded in an extend-entry body); `match="gates key is forbidden in stage body; use gates in workflow.stages"` and `match="verify key is forbidden in stage body; use gates in workflow.stages"`
  - `test_settings_block_alone_compiles_inert` — plain ungated pipeline + workflow `gates: {patience: 2}` only; `"verify" not in flow_text`
- [x] **Logic tests (edge)**:
  - `test_gate_free_workflow_compiles_byte_identically` — any pipeline + a workflow without gates; `flow_text == EXPECTED_UNCHANGED` (full-string golden, verbatim from the pre-feature output — capture it in the REPL before implementing)
  - `test_malformed_timeout_passes_verbatim` — gated shell step with `timeout: "30x"`; `"timeout: 30x" in flow_text` (no goga error — value grammar is engine-owned)
  - `test_extend_plus_stages_entry_keeps_gate` — pipeline stage `x`; workflow `extend: {x: {after: [a], agent: codex}}` AND `stages: {x: {gates: [step]}}`; `"verify:" in flow_text` and the composed `command` from the inline extend agent also present
- [x] **Contract-test extensions**: `tests/pipeline/compiler/test_compile_flow.py` — `test_canonical_fields_signature_has_stage_name` asserts the parameter list `["body", "stage_name", "notes", "memory_fields", "assistants_fields", "verify_fields"]` with `verify_fields` default `None`; `test_canonical_key_order_includes_approve_and_script_slots` pin becomes `[-8:]` ending `["reflect", "memory_use", "assistants", "verify"]` (verify after assistants)
- [x] **Debugging**: `python3 -m pytest tests/pipeline/compiler -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: byte-identical gate-free output (golden test green); `PipelineDocument` and the pipeline-file untouched; error precedence preserved (extend refs → stage names → attachments 4.10 → gates 4.11 → body-key prohibitions)
- [x] **Lint**: `python3 -m ruff check goga/ tests/` + `python3 -m ruff format --check` on the touched files — fix formatting, apply decomposition if necessary
- [x] **Completion**: mark checkboxes complete

### Task 7: Hooks — overlay merge and amendment emptiness for gates (TDD coding)

Carry gates through the hooks cell: the settings-block merge, the per-stage
field merge, and the emptiness enumeration. Covers the
`merge_workflow_overlay` changes in `goga/pipeline/hooks/overlay.py` and the
`WorkflowAmendment.contribute`/`PipelineHooks.amend_workflow` changes in
`amendments.py`/`events.py`.

**Usages relevant to this task:**
- `convention`: pure-model tests without mocks; `caplog` for the warning
  absence assertion (the `test_repeat_only_contribution_is_not_empty` shape).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: declare Task 7 (hooks gates carriage) being executed
- [ ] **Contract tests**: create `tests/pipeline/hooks/test_overlay_gates.py`; extend `tests/pipeline/hooks/test_events.py`. Expected to fail at this stage.
- [ ] **Code**: `_merge_gates(base, contributions)` — line-for-line the `_merge_repeat` shape: the authored block when present (unbeatable), else the later contributing tool's block; no field-level merging
- [ ] **Code**: `_STAGE_FIELDS` gains `"gates"` (last, declaration order) — `_STAGE_DEFAULTS` (`dict.fromkeys(_STAGE_FIELDS)`) automatically gains the `None` default; `_merge_stage`'s authored-wins field loop carries `gates` like `agent`/`prompt`/`notes` (an authored check-step list is never overwritten; `_is_set`: not-`None` = set); no `assistants`-style carve-out — the merge unit is the field
- [ ] **Code**: the rebuilt `WorkflowDocument(..., repeat=repeat, gates=_merge_gates(base, contributions))` — `profile`/`build` verbatim as before; docstring gains the 4d/5b/8 arms
- [ ] **Code**: `events.py` — the per-hook buffer duck-check tuple gains `"gates"` (`("prompt", "stages", "extend", "memory", "assistants", "delegation", "repeat", "gates")`); the empty-document discard gains `and document.gates is None`; the docstring's step-5 enumeration gains "and no gates block"; `amendments.py` `contribute` docstring enumeration gains `gates` ("prompt, stages, extend, memory, assistants, delegation, repeat, gates")
- [ ] **REPL checkpoint**: in the REPL, run `merge_workflow_overlay` on the test models (authored base vs gates-only contribution) and `amend_workflow` with a gates-only buffered contribution; observe the rebuilt document and that no discard warning fires
- [ ] **Interface verification**: `python3 -m pytest tests/pipeline/hooks/test_overlay_gates.py -v` — all pass
- [ ] **Logic tests (from the design's test stack trace)**:
  - `test_overlay_gates.py::test_authored_settings_block_unbeatable_and_stage_gates_fill` — `base = WorkflowDocument(gates=WorkflowGates(patience=1), stages={"a": WorkflowStage(gates=[step])})`; one contribution with `gates=WorkflowGates(max_iterations=9)` and `stages={"b": WorkflowStage(gates=[other_step])}`; assertions: `overlay.workflow.gates.patience == 1`, `overlay.workflow.gates.max_iterations is None` (no field-level merge), `overlay.workflow.stages["a"].gates == [step]`, `overlay.workflow.stages["b"].gates == [other_step]`
  - `test_overlay_gates.py::test_gates_only_contribution_rides_the_merge` — `merge_workflow_overlay(None, [ToolContribution(tool="t", document=WorkflowDocument(gates=WorkflowGates(max_iterations=1)))])`; assertions: `overlay.workflow is not None`, `overlay.workflow.gates.max_iterations == 1`
  - `test_events.py::test_gates_only_contribution_is_not_empty` — a registered tool hook buffers `WorkflowAmendment.contribute(WorkflowDocument(gates=WorkflowGates(max_iterations=1)))`; `amend_workflow(...)` with `workflow=None`; assertions: `overlay.workflow is not None`, `overlay.workflow.gates.max_iterations == 1`, and `not [r for r in caplog.records if r.message == "tool contributed an empty document; discarded"]`
- [ ] **Debugging**: `python3 -m pytest tests/pipeline/hooks -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: a gates-only tool contribution commits as a `ToolContribution` and merges; inputs never mutated; gates values carried whole (never interpreted, validated, or rebuilt); no new imports (`WorkflowDocument` only)
- [ ] **Lint**: `python3 -m ruff check goga/ tests/` + `python3 -m ruff format --check` on the touched files — fix formatting if necessary
- [ ] **Completion**: mark checkboxes complete

### Task 8: Pipeline — `apply_skip_stages` gates carriage (TDD coding)

Carry the settings block through the skip-driven rebuild. Covers the
`apply_skip_stages` contract changes in `goga/pipeline/apply_skip_stages.py`.

**Usages relevant to this task:**
- `convention`: pure-model tests; docstring bullet updates ride the code
  change.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: declare Task 8 (skip rebuild carriage) being executed
- [ ] **Contract tests**: extend `tests/pipeline/test_apply_skip_stages.py` (the `test_apply_skip_stages_carries_repeat_verbatim` shape). Expected to fail at this stage.
- [ ] **Code**: the rebuilt `WorkflowDocument(...)` gains `gates=workflow.gates if workflow is not None else None` — carried verbatim (same object, opaque); the replacement `WorkflowStage(skip=True, assistants=…)` needs NO code change (the dataclass default `gates=None` provides "replacement carries no gates") — document it in the docstring (the compiler removes the skipped stage before the gates walk)
- [ ] **REPL checkpoint**: in the REPL, run `apply_skip_stages` on the test model; observe `merged.gates is workflow.gates` (same object) and `merged.stages["gone"].gates is None`
- [ ] **Interface verification**: `python3 -m pytest tests/pipeline/test_apply_skip_stages.py -v` — all pass
- [ ] **Logic tests (from the design's test stack trace)**:
  - `test_settings_block_survives_skip_rebuild` — `workflow = WorkflowDocument(gates=WorkflowGates(max_iterations=4), stages={"a": WorkflowStage(prompt="x"), "gone": WorkflowStage(skip=True, gates=[step])})`; `skip_stages=["gone"]`; assertions: `merged.gates is workflow.gates` (same object, verbatim), `merged.stages["gone"].gates is None` (replacement carries no gates)
  - `None` workflow with non-empty skips constructs with `gates=None` (the existing none-input shape extended)
- [ ] **Debugging**: `python3 -m pytest tests/pipeline/test_apply_skip_stages.py tests/pipeline -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: skip-driven runs keep retry tuning for remaining gated stages; the skipped stage's checks drop silently downstream; no mutation of inputs
- [ ] **Lint**: `python3 -m ruff check goga/ tests/` + `python3 -m ruff format --check` on the touched files — fix formatting if necessary
- [ ] **Completion**: mark checkboxes complete

### Task 9: Integration tests for the gates lifecycle (integration tests)

Cross-cell end-to-end scenarios stitching the four packages: the amendment
overlay chain and the skip chain, each continuing into `compile_flow` (the
design's data flows 3 and 4 — "an amended run compiles with gates", "a
skip-merged run keeps the settings block for its remaining gated stages").

**Usages relevant to this task:**
- `convention`: integration tests live in `tests/integration/`
  (`test_<scenario>.py`, precedent `test_repeat_skip_end_to_end.py`); pure
  chain — no mocks; `tmp_path` for the pipeline-file fixtures.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create test file `tests/integration/test_gates_end_to_end.py`
- [ ] Test cross-entity interaction — amended run compiles with gates: a gates-only tool contribution → `PipelineHooks.amend_workflow` → `merge_workflow_overlay` → `compile_flow` on a `tmp_path` STAGES pipeline whose stage is gated by the contribution's stage entry; assert the emitted flow carries the `verify` block with the contributed settings (container form when the settings block authored a key)
- [ ] Test cross-entity interaction — skip-driven run: `WorkflowDocument` with a settings block, one gated stage and one `skip` stage → `apply_skip_stages` → `compile_flow`; assert the remaining gated stage carries `verify` with the settings, the skipped stage is absent from the flow and carries no gate, and no error fires
- [ ] Test edge case — loop copies through the full chain: a gated `loop: 2` stage parsed, skip-merged (nothing skipped), amended with an authored settings block, then compiled; assert both expanded ids carry the same `verify` (the design's uniformity invariant)
- [ ] Run validation: `python3 -m pytest tests/integration/test_gates_end_to_end.py -v` — all pass
- [ ] Lint: `python3 -m ruff check tests/` + `python3 -m ruff format --check tests/integration/test_gates_end_to_end.py`

### Task 10: Documentation riders — user-facing gates section and afm fact base (infrastructure)

Land the task.md item-7 riders: the user-facing documentation section and
the engine verify fact base (the assistants-ADR precedent).

**Usages relevant to this task:**
- `afm` (`.goga/usages/cooks/afm.md`): gains the verify fact base — synced
  usage files are managed by `goga usages sync`; edit the cook file the same
  way the assistants fact base was added (the `support-afm-assistants`
  precedent), NOT by hand-editing a synced copy elsewhere.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Add the "Quality gates (`gates`)" section to `docs/features/pipelines/workflows.md` (after the "Run cycles (`repeat`)" section, matching the document's existing section style): the authoring vocabulary (settings block keys, per-stage check steps, `script` xor `agent`, required `name`), the engine-vocabulary mapping table (`patience → review_patience`, `max_iterations → max_failures`, `fresh_correction` unchanged), the `1h` shell-step timeout default (AI steps materialize no default), the combination/exclusion rules (gates forbidden in extend-entries, in stage bodies, on script and planning-only stages; empty equals absence; the settings block alone is inert), and a worked example
- [ ] Verify the worked example compiles as documented: run its exact workflow text through `parse_workflow` + `compile_flow` in the REPL (virtualenv) and compare the emitted `verify` block against the documented snippet — the acceptance criterion pins this
- [ ] Add the engine verify fact base to `.goga/usages/cooks/afm.md` (a "verify" section alongside the existing assistants material), transferring the verified facts from the design's "Engine verify boundary" trace: both engine authoring forms (list and container); step fields `name`/`run`/`command`/`prompt`/`timeout` with `run`/`command` mutually exclusive and exactly one required, `prompt` AI-step-only, `timeout` valid on both kinds; the container form = `steps` + `max_failures`/`review_patience`/`fresh_correction` with step fields at the container top level a parse error; `command` resolved via the same mechanism as `stage.command`; gates forbidden on script and planning-only stages; `name` ≥ 1 non-space character (empty/space-only = parse error); `max_failures ≥ review_patience` interplay with the `min(max_failures, 15)` ceiling (engine-owned); in-order fail-fast steps, full-list re-runs after a correction, strict JSON verdicts (`pass`/`needs_changes`/`inconclusive`), human waiver; older engines reject a gated flow at load (downgrade not silent)
- [ ] Verify consistency: `goga lint` passes (the compiler CODEMANIFEST references the `afm` usage — the fact base must cover what the annotations cite)
- [ ] Lint: `python3 -m ruff check goga/ tests/` (docs changes touch no Python; this confirms no drift)

### Task 11: Full validation sweep (infrastructure)

Final verification across the whole repository — the plan-level Validation
Commands, run as one gate before completion and before any final local
commit.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Run the full suite: `python3 -m pytest tests/ -x` — all pass
- [ ] Lint the project: `python3 -m ruff check goga/ tests/` — zero errors
- [ ] Format-check the touched files: `python3 -m ruff format --check` over every file created or modified by Tasks 1–9 — clean
- [ ] Facade check: `python3 -c "from goga.pipeline.workflow import WorkflowGateStep, WorkflowGates; from goga.pipeline.compiler import FlowVerify, FlowVerifyStep"`
- [ ] Byte-identical guard: `python3 -m pytest tests/pipeline/compiler/test_compile_flow_gates.py::test_gate_free_workflow_compiles_byte_identically -v` — green
- [ ] `goga lint` — passes
- [ ] Confirm `CODEMANIFEST` files untouched (`git diff --stat` shows no CODEMANIFEST path) and the unrelated `goga/assets/afm/skin/goga.css` working-tree change is left alone

---

## Validation Commands

- `python3 -m venv .venv && .venv/bin/pip install -e '.[test]'` (only if no virtualenv exists; the current environment already provides one): prepare the execution environment per the convention
- `python3 -m pytest tests/pipeline/<cell> -x`: run one cell's suite after its tasks (workflow, compiler, hooks, then `tests/pipeline/test_apply_skip_stages.py`)
- `python3 -m pytest tests/integration/test_gates_end_to_end.py -v`: gates lifecycle end-to-end
- `python3 -m pytest tests/ -x`: run all tests
- `python3 -m ruff check goga/ tests/`: lint check (zero errors)
- `python3 -m ruff format --check <touched files>`: formatter check on everything this plan touches
- `python3 -c "from goga.pipeline.workflow import WorkflowGateStep, WorkflowGates; from goga.pipeline.compiler import FlowVerify, FlowVerifyStep"`: facade accessibility
- `goga lint`: CODEMANIFEST/usages consistency

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`workflow_gates.py`, `workflow_gate_step.py`, `flow_verify.py`, `flow_verify_step.py`; changed: `parse_workflow.py`, `workflow_stage.py`, `workflow_document.py`, `compile_flow.py`, `serialize_flow.py`, `overlay.py`, `events.py`, `amendments.py`, `apply_skip_stages.py`)
- [ ] Every contract entity is accessible from the facade (`WorkflowGateStep`, `WorkflowGates` from `goga.pipeline.workflow`; `FlowVerify`, `FlowVerifyStep` from `goga.pipeline.compiler`)
- [ ] Properties and methods match the declared API (field names, order, types, defaults)
- [ ] Descriptions are reflected in behavior (validation surfaces, emission forms, merge semantics, carriage)
- [ ] Contract dependencies are met (compiler imports the two types + the `gates` usage from workflow; no cycles; workflow stays a leaf)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Every coding task ran its REPL checkpoint (interactive evaluation with hot reload; verified snippets migrated to source files)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task; integration tests exist for the cross-package lifecycle chains
- [ ] A gate-free workflow compiles byte-identically (full-string golden comparison green)
- [ ] No package boundary was expanded; no new dependencies
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] The Mandatory Rules (R1–R4) were applied in every task; ruff check and the scoped ruff format check were green at every stage and before every local commit; commit messages carry no co-authorship trailers
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `beautiful_yaml`, `afm`, `gates`, `parse-workflow`, `memory`, `assistants`)
