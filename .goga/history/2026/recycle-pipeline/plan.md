# Plan: `recycle-pipeline`

<!-- Topic: `recycle-pipeline` — the two authoring-surface changes approved in
     `adr.md` (normative) and designed in `design.md` (design-review completed,
     7 fixes applied): the repeating run cycle (pipeline header `repeatable`
     flag + workflow `repeat` block → compiled `repeat` directive) and the
     map-form assistants authoring (name-keyed catalog / stage attachment maps,
     hard transition from the list form). Source:
     `.goga/history/2026/recycle-pipeline/design.md`. This plan compiles the
     design into ralphex-executable tasks. CODEMANIFEST contracts are ALREADY
     applied in the working tree (`goga lint`: 91 cells, 0 errors) — read-only
     for every task below. -->

## Purpose

Implement the `recycle-pipeline` feature end-to-end against the applied
CODEMANIFEST contracts: workflow-files gain an optional top-level `repeat`
block (`{max_cycles, keep_runs}`, authored values only, map form strictly);
pipeline-files gain a header `repeatable` capability flag; the compiler gains
one rule with no exceptions — a repeatable pipeline ALWAYS compiles a `repeat`
key (authored keys from a workflow block, else the scalar `repeat: true`),
emitted between `description` and `memory`; a workflow `repeat` block on a
non-repeatable pipeline is a compile-time structural error. In the same
change, assistants authoring switches from list-of-mappings to name-keyed maps
on both surfaces (catalog and stage attachments), `when` becomes required on
every stage attachment, and the hard transition rejects the old list form with
rename errors naming the map form. The compiled flow-file output for
assistants is unchanged (the engine's list-form contracts stay as-is), and
non-repeatable pipelines compile byte-identically.

After implementation the project provides:

- `goga/pipeline/workflow` — new model `WorkflowRepeat`
  (`workflow_repeat.py`); `WorkflowDocument.repeat` (last field);
  `WorkflowStage.assistants` re-typed `list[WorkflowAssistant] | None` →
  `dict[str, WorkflowAssistant] | None` (name-keyed, authored order);
  `WorkflowAssistant` name/when docstring rewording for the map form;
  `parse_workflow` steps 4 (nine top-level keys incl. `repeat`; the
  assistants branches re-worded to the map form), 6.5 (catalog map grammar),
  6.7 (attachment map grammar with required `when`), 6.9 (`_build_repeat`),
  7 (empty-workflow rule counts `repeat`); the dead list-form helpers deleted;
  facade `__all__` 18 → 19.
- `goga/pipeline/compiler` — new model `FlowRepeat` (`flow_repeat.py`);
  `PipelineHeader.repeatable` (after `roles`); `FlowDocument.repeat` (between
  `description` and `memory`); `parse_dsl` header `repeatable` extraction
  (strictly bool); `compile_flow` step 4.0 (`_check_repeat_correspondence`)
  and step 6 (`_repeat_emission`) plus the `.values()` map walks of
  `_assistant_namespace` / `_assistants_by_id`; `serialize_flow` repeat
  emission (scalar / block / omitted); facade `__all__` 19 → 20.
- `goga/pipeline/hooks` — `merge_workflow_overlay` step 4c (`_merge_repeat`,
  whole-block authored-wins) and the map-form `_merge_stage_assistants`
  append-with-dedup; the rebuild carries `repeat`; the `PipelineHooks`
  delivery counts `repeat` in the intercept fact walk and in the emptiness
  rule; `amend_workflow` docstring gains "and no repeat".
- `goga/pipeline` — `apply_skip_stages` carries `repeat` verbatim and the
  pre-skip entry's assistants **map** on the skip replacement;
  `write_afm_config._assistant_namespace` walks `.values()`.

The most important gaps between contract and code: neither repeat surface
exists (header carries 3 fields; `_TOP_LEVEL_KEYS` is the 8-key tuple;
`_extract_top_level` returns an 8-tuple; the empty-workflow rule counts seven
content blocks); the compiler has no `FlowRepeat`, no cross-check, no emission
arm, and the serializer emits the old 8-key top level; the overlay has no
repeat arm and drops unknown fields on rebuild; assistants are list-validated
(`_validate_top_level_list`, `_build_catalog_entry`,
`_build_attachment_*`, materialized `when` default) and consumed by list
iteration in six sites across compiler / hooks / pipeline; the hard
transition breaks the verified set of 8 existing test files authoring the
list form or constructing `WorkflowStage(assistants=[...])` (see Facts).

Strategy: two feature slices in the design's leaf→root cell order — the
repeat cycle first (Tasks 1–4, one task per cell, each self-consistent and
suite-green), then the map-form hard transition as ONE atomic cross-cell task
(Task 5: the model re-type breaks every consumer at once, so the transition
cannot land half-way without a red suite at a commit boundary), then the
integration proof (Task 6). Every task is gated by the Mandatory Rules below.
CODEMANIFEST changes and all `.usages/` files are already applied and stay
read-only — this plan touches code and tests only.

## Mandatory Rules

<!-- Extracted from the project convention `.goga/usages/conventions.md` (the
     `convention` practice wired into every cell of this feature — for working
     with the codebase, organizing the REPL development cycle, debugging and
     testing, and the test infrastructure), the language rules
     (`goga-cell-python`), the ruff configuration (`pyproject.toml`), and the
     repo gates (`.github/workflows/lint.yml`, `.github/workflows/tests.yml`,
     `.githooks/`). These rules are MANDATORY for every task in this plan.
     Where a task restates a rule, the restatement is a reminder, not a
     replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`.
- **Imports**: relative imports for ALL intra-package references inside
  `goga/` (`from .workflow_repeat import WorkflowRepeat`, `from ..workflow
  import WorkflowDocument`); absolute imports only for stdlib and
  third-party. New model files mirror the existing cell idiom:
  `from __future__ import annotations` at the top. Exception — tests:
  cross-directory references inside `tests/` use absolute imports rooted at
  the `tests` package.
- **Data models**: stdlib `dataclasses` only (never pydantic); model classes
  use `@dataclass(kw_only=True)` with fields in the declared contract order.
  `None` means the explicit absence of a value ONLY — the repeat models carry
  authored values and materialize NO defaults (`WorkflowRepeat()` /
  `FlowRepeat()` with both fields `None` IS the scalar form; an authored `0`
  is a value, never normalized away).
- **Docstrings**: Google style, MANDATORY for every public function, method,
  and class. First line starts with a capital letter and ends with a period.
  Include `Args` when the function accepts parameters, `Returns` when it
  returns a value, `Raises` when it raises beyond built-in types. Dataclass
  models document every field in the `Args:` block (the
  `workflow_delegation.py` precedent — the CODEMANIFEST field descriptions
  are the source text). Click command callbacks are the documented exception
  (no `Args`/`Returns`/`Raises`) — no CLI callback is touched by this plan.
- **Code formatting**: inside function and method bodies, separate logical
  blocks by ONE blank line (initialization / conditions and loops / data
  preparation / processing / return).
- **Type hints**: mandatory everywhere. Allowed shapes: `str`, `int`, `float`,
  `bool`, `list[T]`, `dict[str, T]`, `T | None`. Forbidden: `*args`,
  `**kwargs`, bare `dict`, bare `list`.
- **Naming**: PascalCase classes, snake_case functions/methods/properties/
  modules; private helpers one leading underscore.
- **Facade**: each cell's `__init__.py` exposes the contract API through
  `__all__`, kept ALPHABETICAL. `WorkflowRepeat` slots between
  `WorkflowReflect` and `WorkflowStage`; `FlowRepeat` between `FlowMemory`
  and `FlowStage`.
- **Logging**: stdlib `logging` only (`logger = logging.getLogger(__name__)`);
  lowercase messages, stable event names, contextual `extra=` metadata. This
  feature adds NO log points (the one existing inline-declaration skills
  WARNING is unchanged) — do not add any.
- **Dependencies**: nothing new is added to `pyproject.toml` (PyYAML is the
  only external dependency touched, already declared).
- **Error handling**: `WorkflowSyntaxError` (a `ValueError` subclass) for
  workflow authoring, `StructuralError` (a `ValueError` subclass) for
  pipeline parsing/compilation; raised, never returned; NO wrapping, NO
  recovery. Every message string below is contract — copy verbatim.

### Test Writing (strictly per `conventions.md`)

- **pytest**; tests mirror the source structure directly:
  `goga/pipeline/workflow/x.py` → `tests/pipeline/workflow/test_x.py`.
  Every test directory carries `__init__.py`. Local fixtures live in
  `tests/<package>/conftest.py` (the existing per-directory pattern is
  sufficient — no new shared fixtures).
- **Naming**: files `test_<module>[_<kind>].py`; functions
  `test_<what>_<scenario>` (e.g. `test_parse_repeat_block_carries_authored_keys`);
  grouping `class Test<Component>:` where the file groups by entity.
- **Coverage**: unit tests for every public function/method/class — main
  scenario plus typical data; edge cases for empty inputs (`None`, `""`,
  `[]`, `{}`), boundary values (`0`, negative), invalid types, and expected
  exceptions via `pytest.raises(..., match=...)`. Boundary tables (the
  negative repeat values, the non-bool `repeatable` values) use
  `@pytest.mark.parametrize` with every boundary in the table.
- **Mocks**: NO mocks for pure logic — `parse_workflow` / `parse_dsl` /
  `serialize_flow` are pure (text in, model/text out); `compile_flow` uses
  `tmp_path` exclusively for `pipeline_path` / `flow_path`; overlay tests
  build `WorkflowDocument` / `ToolContribution` values directly.
- **Integration tests** covering multiple packages go to `tests/integration/`
  (`test_<scenario>.py`).
- **Self-documenting test names, minimal comments**; no `pytest.mark.skipif`
  needed (no external dependencies).
- Test libraries stay in `[project.optional-dependencies].test` (already
  declared: `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0`).

### Linters and Formatters — every development stage, every local commit

- **ruff is the project linter AND formatter**, configured in `pyproject.toml`
  (`target-version = "py310"`, `line-length = 120`, the full `select` rule
  set incl. `I`, `N`, `PT`, `RUF`, `PTH`, `C90`; `[tool.ruff.format]`
  double-quote / LF). The CI gates (`.github/workflows/lint.yml`) run exactly:
  - `.venv/bin/ruff check goga/ tests/`
  - `.venv/bin/ruff format --check goga/ tests/` (run
    `.venv/bin/ruff format goga/ tests/` to fix)
- **No task is complete and NO local commit is made while any gate is red.**
  ralphex runs validation after each task and commits only after it passes —
  every task below ends with the full gate battery green: `pytest tests/ -x`,
  `ruff check`, `ruff format --check` (plus `goga lint`, bare, from the
  repository root — per-path invocation yields false usage-filepath errors).
- **All code executes inside the project virtualenv** (`.venv`, created in
  Task 1 if missing — `python3 -m venv .venv && .venv/bin/pip install -e
  '.[test]'`); the venv is the only environment in which pytest / ruff / the
  REPL run. Python 3.10+ compatibility is enforced by CI
  (`.github/workflows/tests.yml` runs 3.10–3.14).
- **Git policy** (`.githooks/`): no `Co-Authored-By:` trailers in commit
  messages.

### REPL Development Cycle — continuous evaluation, hot reload, migration to source

The `convention` practice is bound by every cell's annotations to
"Organizing the REPL development cycle". Every coding task works through an
interactive evaluate → edit → re-evaluate loop in the project virtualenv:

- **Continuous interactive evaluation**: exercise the REAL modules with
  concrete inputs — `python -c` / `python -i` (or `.venv/bin/python`) feeding
  an authored workflow text through `parse_workflow`, calling `compile_flow`
  over `tmp_path` files, constructing the new models — and inspect the real
  outputs and the real exception messages. Never reason about behavior you
  have not observed.
- **Hot reloading**: after each edit, re-evaluate in a FRESH process (or
  `importlib.reload`) — never trust stale interpreter state; the loop
  continues until the observed strings and shapes match the contract exactly
  (the error messages in this plan are frozen — evaluate them, do not
  re-derive them).
- **Code migrates to source files**: whatever expression or scenario was
  verified in the REPL is then migrated into the module (implementation) or
  the test file (scenario). The REPL is scratch; the source files and the
  test suite are the deliverable. Nothing verified only interactively stays
  out of the suite, and nothing enters the suite that was not evaluated.
- **The REPL never replaces the TDD gates**: contract tests are still written
  first (expected to fail), logic tests still follow the implementation; the
  REPL shortens the debug loop between them (each task's STEP 2 embeds the
  probe).

## Context

### Contract Surface

**Cell `goga/pipeline/workflow`** (manifest
`goga/pipeline/workflow/CODEMANIFEST`):

- **Entity: `WorkflowRepeat`** (NEW)
  - Type: class (pure data model); `location: workflow_repeat.py` (new file)
  - Facade obligation: importable from `goga.pipeline.workflow`
  - Signature: `WorkflowRepeat(max_cycles: int | None = None, keep_runs: int | None = None)`
  - Requirements: `@dataclass(kw_only=True)`; both fields default `None`;
    authored values only — an authored zero is a value, not an omission, and
    stays distinguishable from `None`; field order fixed `max_cycles,
    keep_runs`
  - Constraints: no validation, no interpretation here — `parse_workflow`
    validates; the consumer and the engine interpret
- **Entity: `WorkflowDocument`** (changed)
  - `location: workflow_document.py`
  - New field `repeat: WorkflowRepeat | None = None` — LAST field (after
    `delegation`); "a workflow consisting of the block alone is valid"; an
    empty authored block equals absence (parser normalizes to `None`)
  - The empty-workflow rule counts the block: empty only when prompt None AND
    stages empty AND extend empty AND memory None AND build None AND
    assistants empty AND delegation None AND repeat None (`profile` never
    counts)
- **Entity: `WorkflowStage`** (changed)
  - `location: workflow_stage.py`
  - `assistants` re-typed `dict[str, WorkflowAssistant] | None` — a map keyed
    by assistant name, in authored order; `None` when not specified (an empty
    map equals absence — normalized by `parse_workflow`); field stays LAST in
    the fixed field order
- **Entity: `WorkflowAssistant`** (changed — wording only)
  - `location: workflow_assistant.py`; the model shape is unchanged
  - `name` is now the map key on BOTH authoring surfaces; `when` is authored
    on every stage attachment (a missing `when` is a structural error; the
    model default `when="checkpoints"` serves only construction paths that
    carry no attachment authoring)
- **Routine: `parse_workflow(text: str) -> workflow: WorkflowDocument`** (changed)
  - `location: parse_workflow.py`
  - Step 4: nine top-level keys — `repeat` present must be a dict, else
    `"non-mapping repeat block in workflow"`; `assistants` present must be a
    dict, else `"non-mapping assistants block in workflow; author the map
    form keyed by assistant name"`; unknown-key message lists all nine keys
  - Step 6.5 catalog / 6.7 attachments: the map grammars (Task 5 detail)
  - Step 6.9 `_build_repeat`: the repeat block grammar (Task 1 detail)
  - Step 7: the eight-term emptiness conjunction with the new enumeration
  - Step 8: returns the document with `repeat`
- **Unchanged in this cell**: `WorkflowReflect`, `WorkflowExtendStage`,
  `WorkflowMemory`, `WorkflowDelegation`, `WorkflowBuild`,
  `WorkflowSyntaxError`, the profile zone (`ProfileSource`,
  `ResolvedProfile`, `LoadedWorkflow`, `load_home_profiles`,
  `resolve_profile`, `render_workflow`, `resolve_activation`,
  `load_workflow`) — no edits beyond what is listed above.

**Cell `goga/pipeline/compiler`** (manifest
`goga/pipeline/compiler/CODEMANIFEST`):

- Imports gain `WorkflowRepeat` from `goga/pipeline/workflow` (the single
  import delta).
- **Entity: `FlowRepeat`** (NEW)
  - Type: class (pure data model); `location: flow_repeat.py` (new file)
  - Facade obligation: importable from `goga.pipeline.compiler`
  - Signature: `FlowRepeat(max_cycles: int | None = None, keep_runs: int | None = None)`
  - A directive carrying no authored key IS the scalar form; this cell
    materializes no values; field order fixed `max_cycles, keep_runs`
- **Entity: `PipelineHeader`** (changed)
  - `location: pipeline_header.py`; new field `repeatable: bool = False`
    after `roles`; declares the capability, never enters the flow-file
    directly (only the derived `FlowRepeat` does)
- **Entity: `FlowDocument`** (changed)
  - `location: flow_document.py`; new field `repeat: FlowRepeat | None =
    None` between `description` and `memory` (the canonical emission order);
    `None` omits the key entirely (byte-identical output for non-repeatable
    pipelines)
- **Routine: `parse_dsl(text)`** (changed)
  - `location: parse_dsl.py`; after the `roles` extraction: `repeatable`
    present-and-not-strictly-bool → `StructuralError("non-bool value in
    header.repeatable")` (explicit `null` is "present and non-bool" — same
    error; `repeatable: 1` fails the strict `isinstance(v, bool)` test);
    absent → `False`; the 4-field header flows 1:1 into `PipelineDocument`
- **Routine: `compile_flow(...)`** (changed)
  - `location: compile_flow.py`
  - Step 4.0 `_check_repeat_correspondence(header, workflow)` — called
    immediately after the empty-body guard, BEFORE the `workflow is not
    None` reconstruction branch (error precedence: the cross-check fires
    before any extend-ref / stage-name / skip error): `if workflow is not
    None and workflow.repeat is not None and not header.repeatable: raise
    StructuralError("workflow repeat block requires a repeatable pipeline;
    author repeatable: true in the pipeline header")`
  - Step 6 `_repeat_emission(header, workflow) -> FlowRepeat | None`:
    `not header.repeatable` → `None`; workflow block present →
    `FlowRepeat(max_cycles=..., keep_runs=...)` (authored keys only — no
    default materialization; `max_cycles: 0` compiles as 0); else (no block /
    `workflow=None` / workflow-free) → `FlowRepeat()` (the scalar form). The
    `FlowDocument` construction gains `repeat=` between `description` and
    `memory`
  - Steps 4.1–4.10 unchanged except the assistants map consumption
    (`.values()` walks — Task 5)
  - `PipelineDocument` mirror untouched — the repeat directive is
    output-side only
- **Routine: `serialize_flow(doc)`** (changed)
  - `location: serialize_flow.py`; after `top["description"] = ...` and
    before the `memory` block: `doc.repeat is None` → nothing;
    both fields `None` → `top["repeat"] = True` (plain scalar `repeat:
    true`); otherwise → `top["repeat"] = {"max_cycles": ..., "keep_runs":
    ...}` (present keys only, fixed insertion order; block-style mapping of
    plain scalars: `repeat:\n  max_cycles: 3\n  keep_runs: 5`). No new
    `_CanonicalDumper` representer — plain `bool` / `dict` of `int`s hit the
    SafeDumper defaults exactly as the memory block does
- **Unchanged in this cell**: `BodyFormat`, `PipelineRoles`,
  `PipelineDocument`, `PhaseStep`, `StageStep`, `PhasesBody`, `StagesBody`,
  `FlowStage`, `FlowMemory`, `FlowCollaboration`, `FlowTeamMember`,
  `FlowAssistant`, `StructuralError`, `translate_role`.

**Cell `goga/pipeline/hooks`** (manifest `goga/pipeline/hooks/CODEMANIFEST`):

- **Routine: `merge_workflow_overlay(base, contributions)`** (changed)
  - `location: overlay.py`
  - Step 4c `_merge_repeat` (NEW, the exact shape of `_merge_delegation`):
    authored block wins; with none, the later contributing tool's block wins;
    no field-level merging. The rebuilt `WorkflowDocument` gains
    `repeat=_merge_repeat(base, contributions)` — the ninth field rides the
    rebuild (verbatim, whole)
  - Step 5a `_merge_stage_assistants`: the map append-with-dedup (Task 5
    detail)
  - Requirements: pure (inputs never mutated); the rebuilt document preserves
    the effective repeat verbatim — a rebuild that drops it would silently
    recompile an authored cycle bound as the scalar default on tool-amended
    runs
- **Method: `WorkflowAmendment.contribute` / `PipelineHooks.amend_workflow`** (changed — delivery)
  - `location: events.py`; the intercept fact walk tuple gains `"repeat"`
    (`"prompt", "stages", "extend", "memory", "assistants", "delegation",
    "repeat"`); the emptiness discard gains `and document.repeat is None` —
    a `repeat`-only contribution is NOT empty, it commits and merges; the
    `amend_workflow` docstring (and its Algorithm step-5 text) gains "and no
    repeat"

**Cell `goga/pipeline`** (manifest `goga/pipeline/CODEMANIFEST`):

- **Routine: `apply_skip_stages(workflow, skip_stages)`** (changed)
  - `location: apply_skip_stages.py`
  - Step 3: the skip replacement CARRIES the pre-skip entry's assistants MAP
    (`assistants=(existing.assistants if existing is not None else None)` —
    the code already forwards the field verbatim; only its type and the
    docstring wording change)
  - Step 4: the rebuild gains `repeat=workflow.repeat if workflow is not
    None else None` — carried verbatim (same object, opaque); a dropped
    field would silently recompile an authored `repeat: {max_cycles: N}` as
    the scalar `true` on every `--skip` run
- **Routine: `write_afm_config(agent, flow, workflow)`** (changed — mechanical)
  - `location: afm_config.py`; `_assistant_namespace` walks
    `(stage.assistants or {}).values()` (was `or []`); no behavior change
    (the contract wording was already map-agnostic); everything else
    untouched

### Re-exports

None — no `->Name: {}` blocks in any of the four manifests. The two new
types are surfaced through their own cell facades (`WorkflowRepeat` in the
workflow `__all__`, `FlowRepeat` in the compiler `__all__`).

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — the mandatory project rules
  (style, tests, validation commands, the REPL cycle). Bound by every cell.
  Relevance: every task; the Mandatory Rules section above is its extraction.
- `beautiful_yaml` (`.goga/usages/cooks/beautiful_yaml.md`) — the
  `yaml.dump` parameters the `_CanonicalDumper` extends (`sort_keys=False`,
  `default_flow_style=False`, `allow_unicode=True`, `indent=2`). Relevance:
  Task 2 (serializer repeat emission needs no new representer — the plain
  dict/bool ride these defaults).
- `afm` (`.goga/usages/cooks/afm.md`) — the engine contract: the flow-file
  `repeat` directive forms (scalar ⇔ unlimited cycles + `keep_runs: 2`
  engine defaults; block ⇔ authored bounds), the strict block parse, cycle
  semantics (`flow_repeated`, stop-on-failed-cycle, `keep_runs` pruning), the
  team-member/stage-assistant key sets, mode/trigger vocabularies. The
  `repeat` section is read-only for implementation. Relevance: Tasks 2, 5
  (engine vocabulary imported verbatim; goga never duplicates cycle
  semantics).
- `jinja2` (`.goga/usages/cooks/jinja2.md`) — whole-file workflow rendering
  before parsing. Relevance: confirmed NO interaction (repeat/assistants ride
  the rendered text like every other block) — no task edits rendering.

### Imported Usages

- `parse-workflow`, `memory`, `assistants` from `goga/pipeline/workflow`
  (consumed by the compiler; paths
  `goga/pipeline/workflow/.usages/{parse-workflow,memory,assistants}.md`):
  `assistants` documents the map-form catalog/attachments grammar the
  compiler consumes (Task 5); `parse-workflow` documents the repeat block
  grammar and the empty-workflow rule (Tasks 1, 5); `memory` scopes the
  memory consumption (unchanged).
- `compile-flow`, `serialize-flow`, `parse-dsl`,
  `collaboration-emission`, `memory-emission` from `goga/pipeline/compiler`
  (consumed by `goga/pipeline`): the consumer-side cells' bridge to the
  compiler practices — all current (updated by apply-architecture; the
  always-written trigger wording, the repeat sections, the name-keyed map
  merge-slot bullet verified by the design).
- `checkpoints` from `goga/pipeline/hooks` (consumed by `goga/pipeline`):
  the merge-slot bullet — the repeat block is whole; stage assistant maps
  append with name deduplication (Task 5).
- `declaring-actions`, `per-tool-delivery`, `registering-hooks` from
  `goga/hooks` (consumed by the hooks cell): the delivery loop the Task 3
  emptiness change rides; unchanged behavior.

### Local Usages

None planned. All cell `.usages/` files were rewritten/updated by the
apply-architecture stage and the design confirms consistency ("no further
`.usages/` edits"): workflow (`assistants.md`, `parse-workflow.md`),
compiler (`parse-dsl.md`, `compile-flow.md`, `serialize-flow.md`,
`collaboration-emission.md`), hooks (`checkpoints.md`).
`goga/pipeline` has no `.usages/` directory. **No task below creates or
edits a usage file.**

### External Dependencies

- PyYAML (`yaml.safe_load` / `yaml.dump` + the `_CanonicalDumper`) — already
  declared in `pyproject.toml`. YAML 1.1 semantics matter for the tests:
  an unquoted `yes` parses as bool `True`; duplicate mapping keys collapse
  at load (the map-form duplicate convention).
- Python stdlib only otherwise (`dataclasses`, `re`, `logging`,
  `pathlib`).
- Tools: pytest / ruff via `.[test]`; ralphex executes this plan; `goga`
  CLI for `goga lint`.

### Entity Interaction and Data Flow (from the design, verbatim)

```
                          workflow-file                pipeline-file
                               │                            │
                               ▼                            ▼
                       parse_workflow                parse_dsl
                               │                            │
              WorkflowDocument │                    PipelineHeader
              ├ assistants: dict[str, WorkflowAssistant]   ├ repeatable: bool
              ├ delegation ────┘                            └────────┬─────────┐
              └ repeat: WorkflowRepeat | None                        │         │
                               │                                    │         │
        ┌──────────────────────┼──────────────────────────┐         │         │
        │ (tool amendments)    │ (CLI -s/--skip)          │         │         │
        ▼                      ▼                          ▼         ▼         ▼
  PipelineHooks.amend    apply_skip_stages            compile_flow(pipeline, flow, workflow, …)
  ├ emptiness counts …   ├ skip replacement carries    ├ 4.0 cross-check: workflow.repeat × header.repeatable
  │  repeat (events.py)  │  the pre-skip assistants map├ 4.1–4.10 reconstruction (assistants maps consumed)
  └ merge_workflow_…     └ repeat carried verbatim     ├ step 5 FlowStage assembly (assistants slot)
       ├ 4c repeat: authored-wins, whole              ├ step 6: repeat = _repeat_emission(header, workflow)
       └ 5a stage maps append with dedup               │         → FlowRepeat | None
                               │                       └ FlowDocument(prompt, root_dir, name, description,
                               │                            repeat, memory, collaboration, team, stages)
                               ▼                                     │
                        WorkflowOverlay                              ▼
                         (effective doc)                      serialize_flow
                                                             ├ repeat None → key omitted (byte-identical)
                                                             ├ no authored key → `repeat: true`
                                                             └ authored keys → block map, order fixed
                                                                   │
                                                                   ▼
                                                        afm run (single invocation; engine owns cycles)
```

Data flows:

1. **Repeat authoring → compiled directive.** `repeat: {max_cycles: 3}` in
   the workflow-file → `parse_workflow` step 6.9 →
   `WorkflowRepeat(max_cycles=3, keep_runs=None)` on `WorkflowDocument` →
   survives `apply_skip_stages` (verbatim) and `merge_workflow_overlay`
   (whole-block, authored-wins) → `compile_flow` step 4.0 (cross-check
   passes: `header.repeatable` is True) → step 6 →
   `FlowRepeat(max_cycles=3, keep_runs=None)` → `serialize_flow` emits
   `repeat:\n  max_cycles: 3` between `description` and `memory`.
2. **Repeatable default.** `repeatable: true` header, workflow without a
   block (or `workflow=None`, or `--no-workflow`) →
   `WorkflowDocument.repeat is None` → `compile_flow` step 6 builds
   `FlowRepeat()` (no authored key) → `serialize_flow` writes the scalar
   `repeat: true`.
3. **Cross-check failure.** non-repeatable header + workflow `repeat` block
   → `compile_flow` step 4.0 raises `StructuralError("workflow repeat block
   requires a repeatable pipeline; author repeatable: true in the pipeline
   header")` before any reconstruction.
4. **Map-form assistants → engine list.** catalog + attachments as
   name-keyed maps → `WorkflowAssistant` per entry (name = map key) →
   `_effective_overrides` carries the stage map verbatim →
   `_assistant_namespace` (catalog ∪ inline declarations) →
   `_assistants_by_id` resolves references and builds the engine-facing
   `FlowAssistant` list in authored key order → `_canonical_fields`
   assembles the `assistants` slot → `serialize_flow` writes the list of
   mappings — **output shape unchanged** versus the old list-form authoring.
5. **Tool contribution of repeat.** A tool's `WorkflowDocument` carrying
   only `repeat` → `PipelineHooks` delivery: not empty (counts) →
   `merge_workflow_overlay` step 4c: applies only when the authored base has
   no block; later tools win among contributions.

## Facts

- The CODEMANIFEST set is applied and clean: `goga lint` → 91 cells, 0
  errors (bare invocation from the repo root).
- `WorkflowDocument.assistants` is ALREADY `dict[str, WorkflowAssistant]`
  (the catalog was always name-keyed); only the authoring grammar and the
  STAGE attachment container change in Task 5.
- `_extract_top_level` (parse_workflow.py) currently returns an 8-tuple and
  `_TOP_LEVEL_KEYS` lists 8 keys; the `assistants` branch calls
  `_validate_top_level_list("non-list assistants block in workflow", ...)`
  — the only caller of that helper.
- `_ASSISTANT_CATALOG_KEYS` currently includes `"name"` (6 keys);
  `_ATTACHMENT_DECLARATION_KEYS` derives from it; `_validate_catalog_field`
  carries an explicit `if key == "name"` acceptance branch that must be
  DELETED (dropping the constant alone would leave the branch silently
  accepting an inner `name`).
- `_validate_delegation_bound(key, minimum, field_value)` is the exact
  pattern `_validate_repeat_bound` twins (bool-guard, int-guard, minimum);
  `_merge_delegation` (overlay.py) is the exact shape `_merge_repeat` twins.
- The `PipelineHooks` intercept fact walk tuple is `("prompt", "stages",
  "extend", "memory", "assistants", "delegation")`; the emptiness
  conjunction has six terms; both gain `repeat` (Task 3).
- The serializer emits the top level as `top["prompt"]`, `top["root_dir"]`,
  `top["name"]`, `top["description"]`, then memory — the repeat arm inserts
  between `description` and the memory block; `_CanonicalDumper` +
  `yaml.dump(sort_keys=False, default_flow_style=False, indent=2)` needs no
  new representer for a plain bool or a dict of ints.
- The workflow facade `__all__` has 18 names; the compiler facade has 19.
- Six shipped pipeline assets exist (`goga/assets/pipelines/{bugfix,
  refinement, patch, development, sync, review}.yml`) — none gains
  `repeatable: true` (ADR decision 8).
- `.goga/workflows/refinement.yml` stays in the list form — its rejected
  parse is the known accepted consequence; conversion is a separate task.
- Neither pytest nor ruff is installed in the plan environment — Task 1
  bootstraps `.venv` (`pip install -e '.[test]'`).
- The hard transition breaks the VERIFIED set of 8 existing test files
  authoring list-form assistants YAML or constructing
  `WorkflowStage(assistants=[...])` (repo-verified against the actual test
  sources; extend the set only if the suite reveals a further file):
  `tests/pipeline/workflow/test_parse_workflow_assistants.py` (25 tests /
  47+ list-form fixtures), `tests/pipeline/workflow/
  test_workflow_stage_contract.py`, `tests/pipeline/hooks/
  test_overlay_assistants.py`, `tests/pipeline/compiler/
  test_compile_flow_collaboration.py`, `tests/pipeline/compiler/
  test_serialize_flow_collaboration.py`, `tests/pipeline/
  test_apply_skip_stages.py`, `tests/pipeline/test_afm_config_collaboration.py`,
  `tests/pipeline/test_stage_env_wrappers_logic.py`. Files referencing only
  `FlowCollaboration(mode="assistants")` or already authoring map-form
  catalogs (e.g. `test_data_models.py`, `test_flow_document_contract.py`,
  `test_flow_assistant_contract.py`, `test_run_pipeline.py`) need NO
  migration — do not touch them.

## Gap Analysis

- Missing contract entities: `WorkflowRepeat` (`workflow_repeat.py`),
  `FlowRepeat` (`flow_repeat.py`) — neither file exists; neither facade
  exports it.
- Missing facade exposure: the two names above; also the compiler's
  `WorkflowRepeat` import (annotations reference it).
- Missing fields: `WorkflowDocument.repeat`, `PipelineHeader.repeatable`,
  `FlowDocument.repeat`.
- Behavioral gaps: `parse_workflow` steps 4/6.5/6.7/6.9/7 (repeat + map
  grammars + the nine-key/empty-rule wording); `parse_dsl` repeatable
  extraction; `compile_flow` 4.0 + step-6 emission + `.values()` walks;
  `serialize_flow` repeat arm; `merge_workflow_overlay` 4c + map 5a +
  rebuild carry; `events.py` fact walk + emptiness + docstring;
  `apply_skip_stages` repeat carry (+ map wording);
  `afm_config._assistant_namespace` map walk.
- Dead code to delete (Task 5): `_validate_top_level_list`,
  `_build_catalog_entry`, `_build_attachment_entry`,
  `_required_attachment_name`, `_build_attachment_reference`,
  `_build_attachment_declaration`, the `_validate_catalog_field` `name`
  branch, `_ASSISTANT_CATALOG_KEYS`'s `"name"`.
- Stale docstrings to reword (map wording; source = the CODEMANIFEST
  annotations): the workflow models, `_effective_overrides`,
  `_merge_stage_assistants`, `apply_skip_stages`, the `afm_config` namespace
  walk, plus `amend_workflow` (events.py) gains "and no repeat".
- Existing code that can be reused: `_validate_top_level_mapping`,
  `_validate_when`, `_validate_attachment_field`, `_is_assistant_declaration`,
  the delegation validators/merge (the twins), the canonical serializer
  skeleton, `_expand_loops`/`_effective_overrides` machinery.
- Test coverage gaps: every design scenario in Tasks 1–6 is new; the
  verified set of 8 files needs the mechanical map-form migration (Task 5).
- No visibility/workspace issues: all four cells are tracked; the plan adds
  two files under existing packages.

---

## Tasks

> **Package ordering rule**: tasks run in the design's leaf→root cell order —
> workflow → compiler → hooks → pipeline — with the cross-cell map-form
> transition (Task 5) landing atomically after the four cell slices, and the
> integration proof last. Within each coding task, contract tests are written
> first (TDD workflow). Only ONE task is executed per ralphex iteration.

### Task 1: Workflow cell — the `repeat` block: `WorkflowRepeat` model, document field, `parse_workflow` steps 4/6.9/7, facade (TDD coding; bootstraps the environment)

<Context: the cell `goga/pipeline/workflow` (dir `goga/pipeline/workflow/`)
gains the run-cycle tuning block. New file `workflow_repeat.py` with the
`WorkflowRepeat` dataclass (contract above); `workflow_document.py` gains the
`repeat` field (LAST, after `delegation`) with its docstring entry;
`parse_workflow.py` changes: `_TOP_LEVEL_KEYS` gains `"repeat"` (9 keys —
the unknown-key message derives from the tuple); `_extract_top_level` gains
the `repeat` branch (`_validate_top_level_mapping("non-mapping repeat block
in workflow", value)` — a scalar `true`/`false`/`5`, a list, or a string
fails exactly there) and returns a 9-tuple with `repeat_raw` appended
(`dict[str, Any] | None`); the docstring "eight top-level blocks" → "nine".
New private `_build_repeat(repeat_raw)` — the structural twin of
`_build_delegation`:

```
1. repeat_raw is None → return None (no block)
2. FOR (key, value) IN repeat_raw.items():
   - key == "max_cycles" → max_cycles = _validate_repeat_bound("max_cycles", value)
   - key == "keep_runs"  → keep_runs  = _validate_repeat_bound("keep_runs", value)
   - ELSE → raise WorkflowSyntaxError(
       f"unknown key in workflow.repeat: {key}; valid keys: max_cycles, keep_runs")
3. empty dict (no keys survived) → return None (empty block equals absence)
4. RETURN WorkflowRepeat(max_cycles=…, keep_runs=…)
```

New private `_validate_repeat_bound(key, field_value)` — the twin of
`_validate_delegation_bound` with `minimum=0` and the `workflow.repeat`
scope:

```
1. isinstance(field_value, bool) or not isinstance(field_value, int)
   → raise f"non-int value in workflow.repeat.{key}"
2. field_value < 0 → raise f"{key} must be >= 0 in workflow.repeat"
3. RETURN field_value
```

The empty-workflow rule (step 7) gains `and repeat is None` and the message
enumeration becomes "...the delegation block, or the repeat block" (full
message below); the `WorkflowDocument` construction (step 8) passes
`repeat=repeat` as the ninth field. The facade `__init__.py` gains
`from .workflow_repeat import WorkflowRepeat` (between `workflow_reflect`
and `workflow_stage`) and `"WorkflowRepeat"` in `__all__` (alphabetical,
between `WorkflowReflect` and `WorkflowStage`; 18 → 19 names). This task
also BOOTSTRAPS the environment: create `.venv` if missing and install
`'.[test]'`. Test home: new `tests/pipeline/workflow/test_parse_workflow_repeat.py`
+ `tests/pipeline/workflow/test_workflow_repeat_contract.py`; extend
`tests/pipeline/workflow/test_parse_workflow_contract.py` /
`test_parse_workflow_logic.py` where the top-level/empty-rule messages are
pinned. THREE further files pin what this task changes and MUST be updated
in this task (repo-verified breakage — without them the suite stays red):
`tests/pipeline/workflow/test_workflow_document_contract.py` (the
exhaustive `WorkflowDocument` field-order pin gains `repeat` last; add the
`WorkflowDocument().repeat is None` default check),
`tests/pipeline/workflow/test_parse_workflow_memory.py` (the pinned
empty-workflow message gains "the delegation block, or the repeat block"),
and `tests/pipeline/workflow/test_parse_workflow_assistants.py` (ONLY its
two message pins — the 8-key valid-keys list becomes the 9-key list and
the exact empty-workflow string gains the repeat tail; the file's full
map-form rewrite stays in Task 5).>

**Usages relevant to this task:**
- `convention`: dataclass rules (`kw_only=True`, stdlib only), Google
  docstrings, validator message shapes, test layout/naming, the REPL cycle,
  the lint gates, the venv bootstrap.
- `parse-workflow` (the cell's own practice): the repeat-block grammar, the
  top-level key list with `repeat`, the empty-workflow rule, the scalar
  anti-pattern (`repeat: true` rejected at parse).
- `jinja2`: confirmed NO interaction — rendering happens before parsing;
  `repeat` rides the rendered text like every other block and the rendered
  text passes the standard structural validation unchanged. Verify in the
  REPL probe that a template-authored `repeat` block survives the render
  step; do not touch `render_workflow`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION + bootstrap)**: declare this task; create the
      virtualenv if missing — `python3 -m venv .venv && .venv/bin/pip
      install -e '.[test]'` — and confirm the baseline:
      `.venv/bin/pytest tests/pipeline/workflow/ -x` green on the clean tree
- [ ] **STEP 1 (Contract tests)**: in
      `tests/pipeline/workflow/test_workflow_repeat_contract.py`:
      `WorkflowRepeat()` has both fields `None`;
      `WorkflowRepeat(max_cycles=0).max_cycles == 0` (zero is a value);
      `list(dataclasses.fields(WorkflowRepeat))` — the field names equal
      `["max_cycles", "keep_runs"]` and `WorkflowRepeat.__dataclass_params__.kw_only`
      is True; `from goga.pipeline.workflow import WorkflowRepeat` imports
      cleanly. In `tests/pipeline/workflow/test_parse_workflow_repeat.py`:
      a workflow of `"repeat:\n  max_cycles: 2\n"` ALONE parses (no
      `WorkflowSyntaxError`); a `repeat` top-level key on an otherwise-empty
      workflow is ACCEPTED (the block counts as content). Expected to fail —
      correct
- [ ] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      `.venv/bin/python -c` feeding `"repeat:\n  max_cycles: 3\n  keep_runs:
      5\nprompt: x\n"` through `parse_workflow` (observe the current
      unknown-key error `unknown key in workflow: repeat; valid keys:
      prompt, stages, ...`), then re-evaluate after each edit (fresh
      process) until the observed messages equal the frozen strings below.
      Implement per the Contract Surface: create `workflow_repeat.py`
      (`from __future__ import annotations`, `@dataclass(kw_only=True)`,
      Google docstring documenting both fields and the authored-values-only
      rule); add the `repeat` field + docstring to `workflow_document.py`;
      in `parse_workflow.py`: extend `_TOP_LEVEL_KEYS`, the `_extract_top_level`
      branch + 9-tuple + docstring, write `_build_repeat` and
      `_validate_repeat_bound` (the bool-trap guard is MANDATORY:
      `isinstance(v, bool) or not isinstance(v, int)` — a `bool` is an
      `int` subclass), extend the empty-workflow conjunction and message,
      pass `repeat=repeat` at the document construction; update the facade
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/workflow/ -v` — all pass
- [ ] **STEP 4 (Logic tests)**: in `test_parse_workflow_repeat.py` (design,
      verbatim): `test_parse_repeat_block_carries_authored_keys` — input
      `"repeat:\n  max_cycles: 3\n  keep_runs: 5\n"` plus a `prompt:`;
      assert `doc.repeat is not None`, `doc.repeat.max_cycles == 3`,
      `doc.repeat.keep_runs == 5`.
      `test_parse_repeat_block_single_key_and_zero_values` — three texts
      (`max_cycles: 0`; `keep_runs: 0`; `max_cycles: 1`); assert the
      zero-vs-None distinction per the design.
      `test_parse_repeat_only_workflow_is_valid` — `"repeat:\n  max_cycles:
      2\n"` alone; assert no raise, `doc.prompt is None`, `not doc.stages`,
      `doc.repeat.max_cycles == 2`. NEGATIVE (parametrized tables, exact
      `match=`): `test_parse_repeat_non_mapping_block` —
      `repeat: true`, `repeat: false`, `repeat: 5`, `repeat: [1, 2]`,
      `repeat: soon` (each with a `prompt: x`) → `non-mapping repeat block
      in workflow`. `test_parse_repeat_unknown_key` — `{"max_cycles": 1,
      "cycles": 3}` → `unknown key in workflow.repeat: cycles; valid keys:
      max_cycles, keep_runs`.
      `test_parse_repeat_non_int_and_negative_values` —
      `{"max_cycles": true}`, `{"keep_runs": "3"}`, `{"max_cycles": 1.5}`
      → `non-int value in workflow.repeat.max_cycles` (resp. `keep_runs`);
      `{"max_cycles": -1}`, `{"keep_runs": -2}` → `max_cycles must be >= 0
      in workflow.repeat` (resp. `keep_runs`). EDGE:
      `test_parse_repeat_empty_block_equals_absence` — `"repeat: {}\nprompt:
      x\n"` → `doc.repeat is None` (and the workflow is valid via `prompt`).
      `test_parse_empty_workflow_still_rejects_profile_only` —
      `"profile: dev\n"` → `pytest.raises(WorkflowSyntaxError,
      match=re.escape("empty workflow — provide at least prompt, one stage,
      one extend entry, the memory block, the build block, the assistants
      block, the delegation block, or the repeat block"))`
- [ ] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix
      implementation code until all tests pass (do NOT fix test code
      to mask behavior; updating stale message/field-order expectations
      invalidated by this task's contract change — the files listed in
      the task's Test home — IS part of the task)
- [ ] **STEP 6 (Contract re-verification)**: facade import
      `.venv/bin/python -c "from goga.pipeline.workflow import
      WorkflowRepeat"`; `WorkflowDocument()` default `repeat is None`; the
      unknown-top-key message now lists the nine keys
- [ ] **STEP 7 (Lint)**: `.venv/bin/ruff check goga/ tests/` and
      `.venv/bin/ruff format --check goga/ tests/` — fix formatting if
      necessary; `goga lint` (bare, from the repo root) — 0 errors
- [ ] **STEP 8 (COMPLETION)**: mark the checkboxes; submit for review

### Task 2: Compiler cell — `repeatable` flag + `FlowRepeat` + `parse_dsl` extraction + `compile_flow` 4.0/6 + `serialize_flow` emission (TDD coding)

<Context: the cell `goga/pipeline/compiler` (dir `goga/pipeline/compiler/`)
gains the repeatable capability and the compiled directive. New file
`flow_repeat.py` with the `FlowRepeat` dataclass (contract above; "a
directive carrying no authored key IS the scalar form"); `pipeline_header.py`
gains `repeatable: bool = False` after `roles` (+ docstring: strictly bool,
False when absent, never enters the flow-file directly);
`flow_document.py` gains `repeat: FlowRepeat | None = None` between
`description` and `memory` (+ docstring: emission position, scalar form,
byte-identity). `parse_dsl.py` `_parse_header`: after the `roles`
extraction (the flag check comes LAST, after roles) extract `repeatable` —
present-and-not-strictly-bool (including explicit `null` and `1`) →
`StructuralError("non-bool value in header.repeatable")`; absent → False;
build `PipelineHeader(name, description, roles, repeatable)`.
`compile_flow.py`: new private `_check_repeat_correspondence(header,
workflow)` —

```
1. workflow is None or workflow.repeat is None or header.repeatable
   → return (no error)
2. ELSE raise StructuralError("workflow repeat block requires a
   repeatable pipeline; author repeatable: true in the pipeline header")
```

called immediately after the empty-body guard (step 3), BEFORE the
`workflow is not None` reconstruction branch (the cross-check error
precedeses every reconstruction error — embed refs, stage names, skip
guards); new private `_repeat_emission(header, workflow) -> FlowRepeat |
None` —

```
1. not header.repeatable → None
2. workflow is not None and workflow.repeat is not None →
   FlowRepeat(max_cycles=workflow.repeat.max_cycles,
              keep_runs=workflow.repeat.keep_runs)   # authored keys only
3. ELSE → FlowRepeat()                                # the scalar form
```

called at the `FlowDocument` construction: `repeat=` between `description=`
and `memory=`. `serialize_flow.py`: between `top["description"] =
doc.description` and the memory block — `doc.repeat is None` → nothing
(byte-identical); both fields `None` → `top["repeat"] = True` (serializes
`repeat: true`); otherwise a plain insertion-ordered dict of the present
keys (`max_cycles` first, `keep_runs` second) → block-style mapping of
plain scalars. NO new `_CanonicalDumper` representer. Facade:
`from .flow_repeat import FlowRepeat` (between `flow_memory` and
`flow_stage`), `"FlowRepeat"` in `__all__` between `FlowMemory` and
`FlowStage` (19 → 20 names). The compiler also imports `WorkflowRepeat`
from the workflow package where its annotations reference it (the import
delta of the manifest). `PipelineDocument` mirror untouched — repeat is
output-side only. Test home: extend `tests/pipeline/compiler/test_parse_dsl.py`
+ `test_pipeline_header.py`; new `tests/pipeline/compiler/test_flow_repeat_contract.py`,
`test_compile_flow_repeat.py`, `test_serialize_flow_repeat_slot.py`.>

**Usages relevant to this task:**
- `convention`: dataclass rules, docstrings, test layout, REPL cycle, lint
  gates.
- `afm`: the engine's repeat directive forms — scalar `repeat: true` ⇔
  unlimited cycles + `keep_runs: 2` engine defaults; the block form ⇔
  authored bounds; goga never materializes those defaults and never
  duplicates cycle semantics (the run stays a single engine invocation).
- `beautiful_yaml`: the dump parameters the `_CanonicalDumper` extends —
  the plain `bool` / dict-of-ints emission rides them with no representer.
- `parse-workflow` (imported): the `WorkflowDocument` contract of the
  workflow parameter (the `repeat` field consumed at 4.0 and step 6).
- `parse-dsl` / `compile-flow` / `serialize-flow` (the cell's practices):
  the header flag section, the repeat compilation table, the emission style
  rule and key-presence note between `description` and `memory`.
- `memory` (imported from the workflow cell): the memory consumption is
  UNCHANGED by this task — the repeat insertion at the `FlowDocument`
  construction and in the serializer must not disturb the memory arm;
  the memory suites stay green untouched.
- `memory-emission` (imported, compiler's own practice carried by the root
  cell): same guard — the memory block keeps its position between `repeat`
  and `collaboration` and its existing byte-for-byte output.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task; confirm Task 1 gates green
- [ ] **STEP 1 (Contract tests)**: `tests/pipeline/compiler/
      test_flow_repeat_contract.py`: `FlowRepeat()` both fields None;
      `dataclasses.fields` names == `["max_cycles", "keep_runs"]`;
      `kw_only` True; `from goga.pipeline.compiler import FlowRepeat`
      imports. `test_pipeline_header.py`: `PipelineHeader(name, description)`
      has `repeatable is False`; the field order ends `..., roles,
      repeatable`. `test_parse_dsl.py`: a header with `repeatable: true`
      parses to `header.repeatable is True`. `test_compile_flow_repeat.py`:
      compiling a repeatable pipeline yields `doc.repeat is not None`.
      Expected to fail — correct
- [ ] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      compile (over `tmp_path` files) a `repeatable: true` pipeline with a
      `repeat: {max_cycles: 3}` workflow and read the emitted flow text;
      verify in the SAME probe that a non-repeatable compile contains no
      `repeat` substring; re-evaluate after each edit. Implement per the
      Contract Surface: `flow_repeat.py`; the two model fields; the
      `parse_dsl` extraction (strict `isinstance(v, bool)` — Python
      `1 == True` but is not a `bool`); `_check_repeat_correspondence` +
      `_repeat_emission` in `compile_flow.py` with the exact placement (4.0
      before the reconstruction branch; `repeat=` between `description` and
      `memory` at the `FlowDocument` construction); the serializer arm; the
      facade + the `WorkflowRepeat` import
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/compiler/ -v` — all pass
- [ ] **STEP 4 (Logic tests)**: `test_parse_dsl_repeatable_flag` — three
      headers (explicit true; flag absent; explicit false) →
      `header.repeatable is True / is False / is False`.
      `test_parse_dsl_repeatable_non_bool` — parametrized:
      `repeatable: 1`, `repeatable: "yes"` (a QUOTED string; a bare `yes`
      parses as bool True under PyYAML's YAML 1.1 — do not use it), and
      `repeatable: null` → `pytest.raises(StructuralError,
      match=re.escape("non-bool value in header.repeatable"))`.
      `test_compile_flow_repeatable_with_block_emits_authored_keys` —
      tmp_path pipeline with `repeatable: true` + one stage; workflow
      `repeat: {max_cycles: 3, keep_runs: 5}` via `parse_workflow`;
      assert `doc.repeat.max_cycles == 3 and doc.repeat.keep_runs == 5`;
      the flow text contains `"repeat:\n  max_cycles: 3\n  keep_runs:
      5\n"`; `text.index("description:") < text.index("repeat:") <
      text.index("memory:")`.
      `test_compile_flow_repeatable_without_block_emits_scalar` — TWO
      variants: a repeatable pipeline with a workflow WITHOUT a repeat
      block, and `workflow=None` (the `--no-workflow` CLI path reaches the
      same variant: the caller passes `workflow=None`); assert
      `doc.repeat is not None`, both fields `None`, and
      `"\nrepeat: true\n" in flow_path.read_text()` for BOTH variants.
      `test_compile_flow_non_repeatable_output_byte_identical` — a
      non-repeatable pipeline without a workflow repeat block; assert
      `doc.repeat is None` and `"repeat" not in flow_path.read_text()`.
      NEGATIVE: `test_compile_flow_cross_check_error` — a NON-repeatable
      pipeline + a workflow with `repeat: {max_cycles: 2}` →
      `pytest.raises(StructuralError, match=re.escape("workflow repeat
      block requires a repeatable pipeline; author repeatable: true in the
      pipeline header"))` — and the error fires BEFORE reconstruction (the
      workflow would also fail a stage-name check later; the cross-check
      message is the one raised). EDGE (serializer, in
      `test_serialize_flow_repeat_slot.py`):
      `test_serialize_flow_repeat_scalar_and_block_forms` — build
      `FlowDocument` values directly: `FlowRepeat()` → `"\nrepeat: true\n"`
      in text; `FlowRepeat(max_cycles=3)` → `"repeat:\n  max_cycles: 3\n"`
      in text and `"keep_runs" not in text` (present keys only);
      `repeat=None` → `"repeat" not in text`; plus the model-contract
      assertions from STEP 1 stay
- [ ] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix
      implementation code until all tests pass (do NOT fix test code
      to mask behavior; updating stale message/field-order expectations
      invalidated by this task's contract change — the files listed in
      the task's Test home — IS part of the task)
- [ ] **STEP 6 (Contract re-verification)**: facade import
      `.venv/bin/python -c "from goga.pipeline.compiler import
      FlowRepeat"`; a non-repeatable compile is byte-identical (no repeat
      key anywhere); `PipelineDocument` keeps the original body and the
      unprefixed description — the repeat directive is output-side only
- [ ] **STEP 7 (Lint)**: `.venv/bin/ruff check goga/ tests/` and
      `.venv/bin/ruff format --check goga/ tests/`; `goga lint` — 0 errors
- [ ] **STEP 8 (COMPLETION)**: mark the checkboxes; submit for review

### Task 3: Hooks cell — overlay `repeat` merge (4c), rebuild carry, delivery emptiness counts `repeat` (TDD coding)

<Context: the cell `goga/pipeline/hooks` (dir `goga/pipeline/hooks/`)
carries the repeat block through the amendment layer. `overlay.py`: new
private `_merge_repeat(base, contributions) -> WorkflowRepeat | None` — the
exact shape of `_merge_delegation` (the twin, one cell over):

```
1. repeat = base.repeat if base is not None else None
2. IF repeat is None:
     FOR contribution IN contributions:
       IF contribution.document.repeat is not None:
         repeat = contribution.document.repeat      # later tool wins, whole
3. RETURN repeat
```

wired as merge step 4c (after 4b delegation) and threaded into the rebuilt
`WorkflowDocument(..., delegation=…, repeat=_merge_repeat(base,
contributions))` — the ninth field rides the rebuild verbatim, whole (no
field-level merging). `events.py` (`PipelineHooks.amend_workflow`
delivery): the intercept fact walk tuple gains `"repeat"` LAST — `for fact
in ("prompt", "stages", "extend", "memory", "assistants", "delegation",
"repeat")` (a `getattr` failure on an out-of-contract object still fails
the hook under the same hard error); the emptiness discard gains `and
document.repeat is None` — a `repeat`-only contribution is NOT empty, it
commits and merges; the `amend_workflow` docstring's emptiness enumeration
(and its Algorithm step-5 text) gains "and no repeat" (source: the
`PipelineHooks` contract wording). Nothing else in the cell changes — the
catalog merge is untouched; the stage-map merge is Task 5. Test home: new
`tests/pipeline/hooks/test_overlay_repeat.py`; extend
`tests/pipeline/hooks/test_events.py`.>

**Usages relevant to this task:**
- `convention`: docstring style, relative imports, test layout, REPL cycle,
  lint gates.
- `per-tool-delivery` / `registering-hooks` / `declaring-actions`
  (imported from `goga/hooks`): the staged delivery loop the emptiness
  rule lives in — unchanged behavior, one new fact.
- `checkpoints` (the cell's own practice): the merge-slot bullet — the
  repeat block is whole; authored-wins; later tool fills.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task; confirm Task 2 gates green
- [ ] **STEP 1 (Contract tests)**: `tests/pipeline/hooks/test_overlay_repeat.py`:
      `merge_workflow_overlay(base_with_repeat, [])` returns the authored
      block; `merge_workflow_overlay(None, [contrib_with_repeat])` returns
      the contributed block; a rebuilt document with an authored `repeat`
      and tool contributions preserves the authored block. In
      `test_events.py`: a registered tool contributing
      `WorkflowDocument(repeat=WorkflowRepeat(max_cycles=4))` with
      `workflow=None` yields `overlay.workflow is not None`. Expected to
      fail — correct
- [ ] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      build `WorkflowDocument(repeat=WorkflowRepeat(max_cycles=2))` and two
      `ToolContribution` values; call `merge_workflow_overlay` and inspect
      `overlay.workflow.repeat`; then exercise `amend_workflow` with a
      repeat-only contributing tool (registry per the existing hooks
      conftest) and observe the warning NOT firing; re-evaluate after each
      edit. Implement per the Contract Surface: `_merge_repeat`, the 4c
      wiring, the rebuild `repeat=` argument, the events fact walk + the
      emptiness term + the docstring rewording
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/hooks/ -v` — all pass
- [ ] **STEP 4 (Logic tests)**: `test_overlay_authored_repeat_wins_and_
      contribution_fills` (design, verbatim) — scenario 1: base
      `WorkflowDocument(repeat=WorkflowRepeat(max_cycles=2))`,
      contributions: tool A `repeat=WorkflowRepeat(keep_runs=9)`, tool B
      `repeat=WorkflowRepeat(max_cycles=7)`; scenario 2: the same with
      `base.repeat = None`. Assert `overlay.workflow.repeat.max_cycles ==
      2` and `overlay.workflow.repeat.keep_runs is None` (scenario 1 —
      authored wins, contribution NOT merged in: whole-block);
      `overlay.workflow.repeat.max_cycles == 7` (scenario 2 — later tool
      wins). `test_events_repeat_only_contribution_is_not_empty` — a hook
      tool whose contribution is `WorkflowDocument(repeat=
      WorkflowRepeat(max_cycles=4))`; call `hooks.amend_workflow(pipeline=
      ..., decision=..., workflow=None, work=...)` with the tool
      registered; assert `overlay.workflow is not None` and
      `overlay.workflow.repeat.max_cycles == 4` (a dropped `repeat` term
      would discard the contribution with a warning and yield
      `workflow=None`)
- [ ] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix
      implementation code until all tests pass (do NOT fix test code
      to mask behavior; updating stale message/field-order expectations
      invalidated by this task's contract change — the files listed in
      the task's Test home — IS part of the task)
- [ ] **STEP 6 (Contract re-verification)**: purity — the inputs stay
      unmutated (new dicts/documents built); the merged result passes the
      same compilation validation an authored workflow passes; workflow
      `None` only for a `None` base with no committed contribution
- [ ] **STEP 7 (Lint)**: `.venv/bin/ruff check goga/ tests/` and
      `.venv/bin/ruff format --check goga/ tests/`; `goga lint` — 0 errors
- [ ] **STEP 8 (COMPLETION)**: mark the checkboxes; submit for review

### Task 4: Pipeline root — `apply_skip_stages` carries `repeat` verbatim (TDD coding)

<Context: the cell `goga/pipeline` (dir `goga/pipeline/`, manifest
`goga/pipeline/CODEMANIFEST`). `apply_skip_stages.py` step 4: the rebuilt
`WorkflowDocument` gains `repeat=workflow.repeat if workflow is not None
else None` — carried verbatim (the SAME object, opaque; the memory
configuration precedent — never interpreted, validated, or rebuilt here).
A dropped field would silently recompile an authored `repeat: {max_cycles:
N}` as the scalar `true` on every `--skip` run. The docstring Requirements
gains the repeat bullet (source: the contract's survival requirement —
"the repeat block of the input workflow survive the rebuild verbatim — a
rebuild that drops them would ... recompile an authored cycle bound as the
scalar default for skip-driven runs"). Step 3's assistants carry and the
map wording are Task 5 (they need the dict model); the docstring "list" →
"map" rewording rides Task 5 as well. Test home: extend
`tests/pipeline/test_apply_skip_stages.py`.>

**Usages relevant to this task:**
- `convention`: docstring style, test layout, REPL cycle, lint gates.
- `parse-workflow` (imported from the workflow cell): the `repeat` field of
  the document being rebuilt.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task; confirm Task 3 gates green
- [ ] **STEP 1 (Contract tests)**: in `tests/pipeline/test_apply_skip_stages.py`:
      `apply_skip_stages(WorkflowDocument(repeat=WorkflowRepeat(
      max_cycles=3)), ["build"])` returns a document whose `repeat` is the
      SAME object; an empty `skip_stages` returns the input unchanged
      (existing). Expected to fail — correct
- [ ] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      construct the document, apply a skip, and assert `out.repeat is
      doc.repeat` interactively before writing the test; re-evaluate after
      each edit. Implement per the Contract Surface: the `repeat=`
      construction argument + the docstring bullet
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/test_apply_skip_stages.py -v` — all pass
- [ ] **STEP 4 (Logic tests)**: `test_apply_skip_stages_carries_repeat`
      (the repeat half of the design's skip-carry scenario; the map half
      lands in Task 5) — `WorkflowDocument(stages={"build":
      WorkflowStage()}, repeat=WorkflowRepeat(max_cycles=3))`; apply
      `["build"]`; assert `out.repeat is doc.repeat` (verbatim, same
      object), `out.stages["build"].skip is True`; also
      `apply_skip_stages(None, ["build"])` still constructs the skip-only
      document with `repeat is None`; empty `skip_stages` is the input
      unchanged
- [ ] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix
      implementation code until all tests pass (do NOT fix test code
      to mask behavior; updating stale message/field-order expectations
      invalidated by this task's contract change — the files listed in
      the task's Test home — IS part of the task)
- [ ] **STEP 6 (Contract re-verification)**: the input workflow and its
      maps are NOT mutated; all nine fields survive the rebuild (prompt,
      stages, extend, memory, profile, build, assistants, delegation — and
      now repeat)
- [ ] **STEP 7 (Lint)**: `.venv/bin/ruff check goga/ tests/` and
      `.venv/bin/ruff format --check goga/ tests/`; `goga lint` — 0 errors
- [ ] **STEP 8 (COMPLETION)**: mark the checkboxes; submit for review

### Task 5: Map-form assistants — the hard transition across all four cells + the mechanical test migration (TDD coding)

<Context: THE atomic authoring-surface switch (ADR decisions 5–7: hard, not
dual-accepting; the compiled output is unchanged). It lands as ONE task
because the `WorkflowStage.assistants` re-type breaks every consumer at
once — a half-landed transition would leave a red suite at a commit
boundary. Work cell by cell in the design's order (workflow → compiler →
hooks → pipeline), keeping the REPL loop running file-by-file; the full
battery gates the commit.

**Workflow cell — models**: `workflow_stage.py`: `assistants:
dict[str, WorkflowAssistant] | None = None` (name-keyed, authored order;
empty map equals absence); docstring rewording per the contract.
`workflow_assistant.py`: docstring rewording — `name` is the map key of the
entry on BOTH authoring surfaces (matches `[A-Za-z0-9._-]`, "assistant"
rejected, unique across the catalog and every inline declaration);
`when` is authored on every stage attachment (the model default
`when="checkpoints"` serves only construction paths that carry no
attachment authoring). `workflow_document.py` docstring: the assistants
catalog is "an insertion-ordered map ... keyed by name (the authored order
is the delivery order of the run agents)" — already accurate; touch only
if the wording names lists.

**Workflow cell — parser** (`parse_workflow.py`):
`_extract_top_level` `assistants` branch: `_validate_top_level_list(...)`
is REPLACED with `_validate_top_level_mapping("non-mapping assistants
block in workflow; author the map form keyed by assistant name", value)`;
`assistants_raw` re-typed `dict[str, Any] | None`. `_ASSISTANT_CATALOG_KEYS`
drops `"name"` → `("prompt", "skills", "agent", "delegate", "env")` — the
unknown-key message and `_ATTACHMENT_DECLARATION_KEYS` derive from it
automatically; the explicit `if key == "name"` acceptance branch in
`_validate_catalog_field` is DELETED (with the branch gone, an inner
`name` key reaches the else-branch and raises the unknown-key error —
dropping the constant alone would leave the branch silently accepting it).
`_validate_assistant_name` gains the non-`str` guard:

```
if not isinstance(name, str) or not _ASSISTANT_NAME_PATTERN.fullmatch(name):
    raise WorkflowSyntaxError(f"invalid assistant name: {name}")
```

(a YAML key may parse as int/float/bool — `123:` must raise the message,
not a `TypeError` from `re.fullmatch`). `_build_assistant_catalog`
REWRITTEN over the map:

```
1. assistants_raw is None → return {}
2. FOR (key, entry_value) IN assistants_raw.items():
   - not isinstance(entry_value, dict) → raise
     f"non-mapping assistant entry in workflow.assistants.{key}"
   - name = key (a non-str key fails the name grammar — see above)
   - fields = {k: _validate_catalog_field(scope, k, v) for k, v in
     entry_value.items()}   # scope = f"workflow.assistants.{name}"
   - at-least-one: fields["prompt"] is None and fields["skills"] is None
     → raise f"assistant {name} requires at least one of prompt or skills"
     # presence, NOT truthiness — skills: [] satisfies
   - _validate_assistant_name(name)
   - catalog[name] = WorkflowAssistant(name=name, prompt=…, skills=…,
     agent=…, delegate=fields.get("delegate", False), env=…)
3. RETURN catalog   # insertion order = authored order
```

An in-catalog duplicate cannot occur (a dict key is unique; duplicate YAML
keys collapse at `safe_load` — the `stages`/`env` map convention); the
document-wide namespace check below stays the cross-surface guard.
`_build_stage_assistants` REWRITTEN (contract 6.7):

```
1. not isinstance(value, dict) → raise
   f"non-mapping assistants in workflow.stages.{stage}; author the map
   form keyed by assistant name"     # kills the list AND bare-string forms
2. empty dict → return None
3. FOR (key, entry_value) IN value.items():
   - not isinstance(entry_value, dict) → raise
     f"non-mapping assistant attachment in workflow.stages.{stage}.{key}"
   - name = key; scope = f"workflow.stages.{stage}.assistants.{name}"
   - "when" not in entry_value → raise f"when is required in {scope}"
     # runs for BOTH forms, before discrimination — an empty {} dies here
   - gate = entry_value.get("gate", False); non-bool → f"non-bool value in
     {scope}.gate"; when = _validate_when(scope, entry_value["when"])
   - IF set(entry_value) <= {"gate", "when"}:      # reference
       _validate_assistant_name(name)
       attachments[name] = WorkflowAssistant(name=name, gate=gate, when=when)
   - ELSE:                                          # full inline declaration
       fields = {k: _validate_attachment_field(scope, k, v) for k, v in
                 entry_value.items()}
       at-least-one (same message as the catalog, on `name`)
       _validate_assistant_name(name)
       attachments[name] = WorkflowAssistant(name=name, prompt=…, skills=…,
         agent=…, delegate=…, env=…, gate=gate, when=when)
4. RETURN attachments   # None when empty
```

The model default `when="checkpoints"` is never consulted for authored
attachments — `when` is always in the constructor call. The unknown
attachment key error lists the seven-key valid set `prompt, skills, agent,
delegate, env, gate, when`. `_validate_assistant_namespace`: iterates
`(stage.assistants or {}).values()` (was: list elements); a declaration
name repeated across the catalog and any inline declaration raises
`"duplicate assistant name: NAME"`; references never count. DELETIONS
(verify each has no remaining callers): `_build_catalog_entry`,
`_build_attachment_entry`, `_required_attachment_name`,
`_build_attachment_reference`, `_build_attachment_declaration`,
`_validate_top_level_list`.

**Compiler cell** (`compile_flow.py`): `_effective_overrides` carries the
stage assistants MAP verbatim (the field forwarding is unchanged — only the
container type and the docstring wording change); `_assistant_namespace`:
`for entry in (stage.assistants or {}).values():` (was `or []`);
`_assistants_by_id`: `for entry in attachments.values():` (was: list
iteration); the duplicate-in-one-stage guard (check 2, the `seen` set) is
RETAINED as a defensive check per the contract ("a programmatic
contribution" — an authored map cannot repeat a key and the overlay merge
deduplicates, so the guard is unreachable through authored paths; it costs
O(n) and keeps the contract's four checks in one place); `if not
attachments:` keeps working (`None`/`{}` both falsy); loop-expanded copies
share one entry list (uniform across copies). Docstrings reworded
("list" → map wording; source = the CODEMANIFEST annotations).

**Hooks cell** (`overlay.py`): `_authored_namespace`: `for entry in
(stage.assistants or {}).values()`; `_merge_catalog` unchanged (already
map-keyed by name); `_merge_stage_assistants` REWRITTEN as the map
append-with-dedup:

```
1. result = dict(authored_map) if authored_map is not None else {}
2. present_on_stage = set(result)
3. FOR contribution, FOR (name, entry) IN tool_stage.assistants.items():
     - name in present_on_stage → skip (silent drop)
     - declaration AND name in namespace → skip (silent drop)
     - result[name] = entry; present_on_stage.add(name)
     - declaration → namespace.add(name)
4. RETURN result or None
```

(the namespace invariant — each name at most once across catalog + every
inline declaration — is preserved by construction). Docstring rewording.

**Pipeline root**: `apply_skip_stages.py` step 3 replacement keeps
`assistants=(existing.assistants if existing is not None else None)` — the
field is now a map, forwarded verbatim, no rebuild (the compiler removes
the skipped stage before the attachment walk, but the document-wide
namespace reads every stage entry, so inline declarations stay resolvable
for other stages' references — the same carry an authored `skip: true`
keeps); docstring "list" → "map" wording. `afm_config.py`
`_assistant_namespace`: `for entry in (stage.assistants or {}).values())`
(was `or []`) — no behavior change; docstring wording.

**Test migration (mechanical, the verified set of 8 files)**: every test
authoring list-form assistants YAML or constructing
`WorkflowStage(assistants=[...])` is rewritten to the map form (and the
dict model). The repo-verified affected set: `tests/pipeline/workflow/
test_parse_workflow_assistants.py` (25 tests / 47+ list-form fixtures;
full rewrite), `tests/pipeline/workflow/test_workflow_stage_contract.py`,
`tests/pipeline/hooks/test_overlay_assistants.py`,
`tests/pipeline/compiler/test_compile_flow_collaboration.py`,
`tests/pipeline/compiler/test_serialize_flow_collaboration.py`,
`tests/pipeline/test_apply_skip_stages.py`,
`tests/pipeline/test_afm_config_collaboration.py`,
`tests/pipeline/test_stage_env_wrappers_logic.py`. Extend the set only if
the suite reveals a further file; files referencing only
`FlowCollaboration(mode="assistants")` or already authoring map-form
catalogs (`test_data_models.py`, `test_flow_document_contract.py`,
`test_flow_assistant_contract.py`, `test_run_pipeline.py`) need NO
migration — leave them untouched. The recipe:
`- name: X` entries become map keys (`X:` at the entry indentation); a
bare-string attachment `reviewer` becomes `reviewer: {when: <the value the
old default materialized — make it explicit>`; expected
`WorkflowAssistant` LISTS become name-keyed dicts; every stage attachment
fixture gains its `when:`; assertion messages change only where the new
rename errors apply. `.goga/workflows/refinement.yml` is NOT converted —
its list-form parse rejection is the known accepted consequence (its
conversion is a separate task). Test home: rewrite
`tests/pipeline/workflow/test_parse_workflow_assistants.py`; new scenarios
per the design below; migrate the rest in place.>

**Usages relevant to this task:**
- `convention`: the full rule set (style, tests, REPL cycle, lint gates).
- `assistants` (imported from the workflow cell, and the cell's own
  practice): the map-form catalog/attachments grammar, the required
  `when`, the complete structural-error table, no list-form examples.
- `parse-workflow` (imported): the map grammar and the empty-workflow rule
  interplay.
- `collaboration-emission` (imported from the compiler): the name-keyed
  map source with authored key order; the always-written trigger with no
  compiler-side engagement default.
- `compile-flow` / `serialize-flow` (imported): the engine-facing list
  output contract — unchanged.
- `checkpoints` (imported from hooks): stage assistant maps append with
  name deduplication.
- `afm`: the engine's strict `stages[].assistants` parse and the
  team-member key set (unchanged outputs).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task; confirm Task 4 gates
      green; re-read the ADR decisions 5–7 (hard transition; required
      `when`; unconverted `refinement.yml`)
- [ ] **STEP 1 (Contract tests)**: in the rewritten
      `tests/pipeline/workflow/test_parse_workflow_assistants.py`: the
      map-form catalog parses into `doc.assistants` keyed by name; a stage
      attachment map parses into `doc.stages[name].assistants` keyed by
      name; `WorkflowStage(assistants={"x": ...})` constructs (the dict
      model); `from goga.pipeline.workflow import WorkflowAssistant`
      unchanged. Expected to fail — correct
- [ ] **STEP 2 (REPL probe + implementation, cell by cell)**: probe in the
      venv REPL with the design's canonical map-form YAML (below) — parse
      it, then compile it and diff the stage `assistants` list against the
      old list-form output (they must be EQUAL — the engine-facing
      contract is untouched); re-evaluate after each edit (fresh process).
      Implement per the Contract Surface above, in order: workflow models
      → workflow parser (+ deletions) → compiler walks → hooks overlay →
      pipeline root; keep every frozen message verbatim
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/workflow/ tests/pipeline/compiler/
      tests/pipeline/hooks/ -v` — the migrated suites pass
- [ ] **STEP 4 (Logic tests)**: in the rewritten assistants suites (design,
      verbatim): `test_parse_assistant_catalog_map_form` — input the
      canonical YAML:

      ```yaml
      assistants:
        reviewer:
          agent: claude
          delegate: true
          skills: [code-audit]
          prompt: |
            Review the stage changes.
      stages:
        build:
          assistants:
            reviewer:
              when: finish
      ```

      assert `doc.assistants["reviewer"].name == "reviewer"`,
      `.delegate is True`, `.gate is False` (materialized default),
      `doc.stages["build"].assistants["reviewer"].when == "finish"`,
      `.prompt is None` (the reference carries none).
      `test_parse_attachment_full_inline_declaration` — a stage attachment
      `{agent: codex, prompt: Audit the diff., gate: true, when:
      checkpoints}`; assert the built `WorkflowAssistant` fields.
      `test_parse_list_form_catalog_rejected_naming_map_form` — the old
      list form `"assistants:\n- name: reviewer\n  prompt: X\nprompt:
      x\n"` → `pytest.raises(WorkflowSyntaxError, match=re.escape(
      "non-mapping assistants block in workflow; author the map form
      keyed by assistant name"))`.
      `test_parse_attachment_list_and_string_forms_rejected` —
      `assistants: [reviewer]` and `assistants: reviewer` on a stage →
      the `non-mapping assistants in workflow.stages.build; author the
      map form keyed by assistant name` message.
      `test_parse_attachment_missing_when` — an attachment value
      `{gate: true}` → `when is required in
      workflow.stages.build.assistants.reviewer`.
      `test_parse_catalog_inner_name_gate_when_unknown` — catalog entries
      carrying `name:`, `gate:`, or `when:` keys → `unknown key in
      workflow.assistants.reviewer: (name|gate|when); valid keys: prompt,
      skills, agent, delegate, env`.
      `test_parse_duplicate_assistant_name_across_surfaces` — a catalog
      `reviewer` plus an inline declaration `reviewer` on a stage (or the
      same name declared inline on two stages) → `duplicate assistant
      name: reviewer`.
      EDGE: `test_parse_attachment_reference_with_when_only` —
      `{when: start}` → a reference with `gate is False`, `when ==
      "start"`, `prompt is None`.
      `test_parse_attachment_empty_map_equals_absence` —
      `assistants: {}` on a stage → `doc.stages["build"].assistants is
      None`.
      `test_parse_empty_assistants_catalog_equals_absence` —
      `"assistants: {}\nprompt: x\n"` → `doc.assistants == {}` and valid
      via prompt; `"assistants: {}\n"` alone → the `empty workflow` error
      (the map-form twin of the old `assistants: []` behavior).
      `test_parse_assistant_name_grammar_and_reserved` — catalog keys
      `"good.name-1_X"` (parses), `"bad name!"`, `"assistant"`
      (reserved), `123` (the non-str guard) → the respective messages.
      Compiler: `test_compile_flow_map_form_output_equals_list_form_output`
      — one pipeline; two workflow texts authoring the same collaboration:
      the new map form and a pre-change equivalent list form (kept as a
      LITERAL string in the test, not parsed by the new parser); the
      expected flow text is computed once from the map-form compile;
      assert for BOTH the reference form and the declaration form that
      the stage `fields["assistants"]` equals the expected
      `FlowAssistant` list (explicit `trigger` on every entry:
      one_shot/checkpoints/on_completion) and the `team` block equals the
      expected `FlowTeamMember` list. Pipeline root:
      `test_apply_skip_stages_carries_repeat_and_assistants_map` (the map
      half) — `WorkflowDocument(stages={"build": WorkflowStage(assistants=
      {"security": WorkflowAssistant(name="security", prompt="Audit.",
      when="start")})}, repeat=WorkflowRepeat(max_cycles=3))`; apply
      `["build"]`; assert `out.repeat is doc.repeat`,
      `out.stages["build"].skip is True`,
      `out.stages["build"].assistants["security"].prompt == "Audit."`
      (the namespace stays resolvable). `test_afm_config_namespace_walks_
      map_attachments` — an effective workflow with a stage assistants map
      + a `FlowDocument` referencing the same names; `write_afm_config(
      agent=None, flow=flow, workflow=workflow)` into a tmp home; assert
      the generated profiles cover the map's declaration names
- [ ] **STEP 5 (Migration + debugging)**: migrate the affected test files
      (the verified set of 8 listed above; extend only if the suite
      reveals more) per the recipe (file-by-file; run each migrated file
      immediately — `.venv/bin/pytest tests/pipeline/<dir>/test_<file>.py
      -v`); then `.venv/bin/pytest tests/ -x` — fix implementation code
      until all tests pass (do NOT fix test code to mask behavior)
- [ ] **STEP 6 (Contract re-verification)**: the compiled engine-facing
      output is UNCHANGED (the STEP 2 probe + the equals test); the
      six-site `.values()` consumption verified (compiler ×2, hooks ×2,
      pipeline root ×2); the deleted helpers have no dangling references
      (`.venv/bin/ruff check goga/` catches them)
- [ ] **STEP 7 (Lint)**: `.venv/bin/ruff check goga/ tests/` and
      `.venv/bin/ruff format --check goga/ tests/`; `goga lint` — 0 errors
- [ ] **STEP 8 (COMPLETION)**: mark the checkboxes; submit for review

### Task 6: Integration — the skip-path end-to-end repeat proof + the byte-identity golden check (integration tests)

<Context: the cross-cell scenarios the unit layer cannot pin alone.
(1) The composed rebuilds: `resolve → load_workflow → apply_skip_stages →
compile_flow` with an authored repeat and a CLI skip — two rebuilds
(`apply_skip_stages` and the overlay decision path) compose without losing
the block. If the full `run_pipeline` coordination is too heavy for the
unit layer, drive the direct chain (the design allows both). Test home:
new `tests/integration/test_repeat_skip_end_to_end.py` (the
`tests/integration/` placement is the convention's rule for cross-package
scenarios; the `test_skip_review_end_to_end.py` precedent).
(2) The byte-identity spot check (design, Additional Instructions):
compile the six shipped assets (`goga/assets/pipelines/*.yml`) plus the
project pipelines BEFORE the change (a `git worktree` at the base commit,
or a golden copy captured via `git stash`) and AFTER; diff the flow
outputs — they must be byte-identical (none of them is repeatable; the
serializer's `None` arm omits the key). The existing
`tests/pipeline/compiler/test_shipped_pipelines_compile.py` already pins
the shipped-asset outputs — confirm it stays green (it is the permanent
guard); the pre/post diff is this task's one-off verification (record the
result in the task notes; no permanent golden fixtures are added).>

**Usages relevant to this task:**
- `convention`: integration-test placement (`tests/integration/`), tmp_path
  for all files, no mocks for the pure chain.
- `afm`: the flow-file contract the outputs are diffed against.
- `parse-workflow` / `compile-flow` (imported practices): the chain being
  composed.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] Create `tests/integration/test_repeat_skip_end_to_end.py` with the
      project-dir fixture pattern (a `repeatable: true` pipeline, a
      workflow with `repeat: {max_cycles: 2}`, tmp dirs)
- [ ] `test_run_pipeline_skip_path_compiles_authored_repeat` (design,
      verbatim): drive the chain with `skip=["review"]` (or the direct
      `load_workflow → apply_skip_stages → compile_flow` chain); assert
      the flow-file carries `max_cycles: 2` AND omits the skipped stage
- [ ] Byte-identity: capture the pre-change compiled outputs of the six
      shipped assets + the project pipelines (base-commit worktree or git
      stash), recompile on this branch, `diff` — byte-identical; record
      the result; confirm `tests/pipeline/compiler/
      test_shipped_pipelines_compile.py` is green
- [ ] Run validation: `.venv/bin/pytest tests/integration/ -v` then the
      full battery `.venv/bin/pytest tests/ -x`
- [ ] Final gates: `.venv/bin/ruff check goga/ tests/`, `.venv/bin/ruff
      format --check goga/ tests/`, `goga lint` (bare, from the repo
      root), and the facade checks — all green before the local commit

---

## Validation Commands

(All inside the virtualenv created in Task 1 — `.venv/bin/...`)

- `.venv/bin/pytest tests/ -x`: Run all tests (the full battery; the
  per-task gate and the pre-commit gate)
- `.venv/bin/pytest tests/pipeline/workflow/ tests/pipeline/compiler/
  tests/pipeline/hooks/ tests/pipeline/test_apply_skip_stages.py
  tests/pipeline/test_afm_config_collaboration.py tests/integration/ -v`:
  The focused suites of this feature
- `.venv/bin/ruff check goga/ tests/`: Lint check (the CI gate of
  `.github/workflows/lint.yml`)
- `.venv/bin/ruff format --check goga/ tests/`: Format check (run
  `.venv/bin/ruff format goga/ tests/` to fix — the second CI gate)
- `goga lint`: Cell-level lint — 91 cells, 0 errors (run BARE from the
  repository root; per-path invocation yields false usage-filepath errors)
- `.venv/bin/python -c "from goga.pipeline.workflow import
  WorkflowRepeat"`: Workflow facade (19 names, `WorkflowRepeat` between
  `WorkflowReflect` and `WorkflowStage`)
- `.venv/bin/python -c "from goga.pipeline.compiler import FlowRepeat"`:
  Compiler facade (20 names, `FlowRepeat` between `FlowMemory` and
  `FlowStage`)

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
  (`workflow_repeat.py`, `flow_repeat.py`; the extended
  `workflow_document.py`, `workflow_stage.py`, `workflow_assistant.py`,
  `parse_workflow.py`, `pipeline_header.py`, `flow_document.py`,
  `parse_dsl.py`, `compile_flow.py`, `serialize_flow.py`, `overlay.py`,
  `events.py`, `apply_skip_stages.py`, `afm_config.py`)
- [ ] Every contract entity is accessible from its facade (workflow 19,
  compiler 20)
- [ ] Properties and methods match the declared API (dataclass field sets
  and orders exact — `max_cycles, keep_runs` twice; the nine-field
  `WorkflowDocument`; the four-field `PipelineHeader`; the `FlowDocument`
  order `prompt, root_dir, name, description, repeat, memory,
  collaboration, team, stages`)
- [ ] Descriptions are reflected in behavior (authored-values-only carry
  with the zero-vs-None distinction; the always-emit rule; the 4.0
  cross-check precedence; the emission position and the three serializer
  arms; byte-identity for non-repeatable pipelines; the map grammars with
  required `when` and the rename errors; the whole-block overlay merge;
  the emptiness counts `repeat`; the verbatim skip carry; the
  `.values()` consumption)
- [ ] Contract dependencies are met (workflow → compiler → hooks →
  pipeline order; imported usages applied where their annotations bind
  them)
- [ ] Re-exports are accessible from the facade (none declared — the two
  new types are surfaced through their own facades)
- [ ] Every coding task followed the TDD workflow (contract tests → REPL
  probe + code → verification → logic tests → debugging →
  re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior
  within each coding task — all 34 design test scenarios implemented
  (the model-contract and facade scenarios split across Tasks 1–2; the
  skip-carry scenario split across Tasks 4–5) plus the integration
  scenario and the byte-identity check
- [ ] Integration tests exist where cross-entity scenarios require them
  (the skip-path end-to-end repeat proof; the shipped-assets golden diff)
- [ ] No package boundary was expanded (no new cells; private helpers
  only; the deleted list-form helpers leave no trace)
- [ ] `CODEMANIFEST` files were not modified; no `.usages/` file was
  created or edited (contract and practices are read-only)
- [ ] All validation commands pass (battery, ruff check + format,
  `goga lint`, facade imports)
- [ ] Every Usages entry is mentioned in at least one task (`convention`,
  `beautiful_yaml`, `afm`, `jinja2`, `parse-workflow`, `memory`,
  `assistants`, `collaboration-emission`, `memory-emission`,
  `compile-flow`, `serialize-flow`, `parse-dsl`, `checkpoints`,
  `per-tool-delivery`, `declaring-actions`, `registering-hooks`)
- [ ] The ADR's out-of-scope guardrails held: `.goga/workflows/
  refinement.yml` NOT converted; no shipped asset gained `repeatable:
  true`; no repeat surfacing in `goga pipeline card` /
  `describe_pipeline`; `run_pipeline` stays a single `afm run` invocation
  (no goga-side cycle logic — no counting, no stop conditions, no
  pruning)
- [ ] The Mandatory Rules were enforced at every task boundary and every
  local commit (style, tests, linters/formatters, REPL cycle; no
  `Co-Authored-By:` trailers)
