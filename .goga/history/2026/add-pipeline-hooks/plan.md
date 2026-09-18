# Plan: `add-pipeline-hooks`

<!-- Topic: add-pipeline-hooks — .goga/history/2026/add-pipeline-hooks/ -->

Result of compiling the reviewed design document (`.goga/history/2026/add-pipeline-hooks/design.md`,
post design-review with 9 approved fixes) into ralphex-executable tasks. This format is compatible
with ralphex execution.

---

## Purpose

Implement the pipeline domain hooks zone and wire both pipeline flows through it:

- **`goga/pipeline/hooks`** — the new zone cell (11 contract entities across five modules):
  the fact vocabulary of the run events (`identity.py`, `contexts.py`), the authored-wins
  workflow overlay (`overlay.py`), the read-and-contribute amendment view (`amendments.py`),
  and the checkpoint surface `PipelineHooks` (`events.py`) delivering the platform's first
  **hard** action `pipeline/amend_workflow` and the two soft notifications
  `pipeline/run_created` / `pipeline/run_completed` over the `goga/hooks` platform facade.
- **`goga/hooks/catalog`** — three additive `Action` records.
- **`goga/pipeline`** — `PipelineCard.provenance`, the card form (`describe_pipeline`) and the
  run form (`run_pipeline`, now 17 steps) composed through the amendment layer, and the CLI
  card `tools:` line plus clean rendering of the hard amendment error.

The dominant gap: none of this code exists — the zone directory holds only its `CODEMANIFEST`
(created and lint-clean at the apply stage), and the consumers are still at their pre-feature
11-step / 5-step shapes. The strategy is the design's dependency order: catalog records →
zone data models (`identity` → `contexts` → `overlay` → `amendments`) → `events.py` + facade →
`pipeline_card` → `describe_pipeline` → `run_pipeline` → `cli`, each task TDD
(contract tests first), each task verifiable in one session.

**With no tool packages installed the overlay is the passthrough — every form behaves exactly
as before** (byte-identical CLI output, unchanged exit codes). That guarantee is pinned by
tests, not assumed.

## Context

### Interaction Diagram

Transfer of the design's entity interaction and data flow diagram (verbatim):

```
                    goga/commands/pipeline (host CLI, docker boundary)
                                  │ docker run + env
                                  ▼
                    goga/pipeline (in-container zone)
        ┌──────────────────────────────────────────────────┐
        │ pipeline_cli ── run form ──▶ run_pipeline        │
        │      │ card form ──▶ describe_pipeline           │
        │      │                        │                  │
        │      ▼                        ▼                  │
        │  PipelineCard(+provenance)   (1) fact resolution │
        │        ▲                      │  parse_dsl       │
        │        │                      │  resolve_workflow + apply_skip_stages
        │        │                      │  resolve_current_branch_name /   ──▶ goga/history
        │        │                      │  resolve_topic_dir               (topic-paths,
        │        │                      │  (statuses: assemble_status_scale /  topic-statuses)
        │        │                      │   resolve_topic_status)          │
        │        │                      ▼                                  │
        │        │            goga/pipeline/hooks (the zone)               │
        │        │        PipelineHooks ── amend_workflow ──▶ WorkflowAmendment (per tool)
        │        │        │      │                    contribute()          │
        │        │        │      ▼                                          │
        │        │        │  merge_workflow_overlay ◀─ ToolContribution*    │
        │        │        │      │                                          │
        │        │        │      ▼ WorkflowOverlay                          │
        │        │        │  emit_run_created  ──▶ RunCreated ─┐            │
        │        │        │  emit_run_completed ─▶ RunCompleted ├─▶ goga/hooks
        │        └────────┤                                   │  (emit_hook_event,
        │  compile_flow(overlay.workflow) ◀───────────────────┘   wrap_context,
        │        │        ▲                                      build_hook_arguments,
        │        ▼        │                                      HookRegistry,
        │  order_stages ──┘ CompositionStage[]                   declared_actions)
        │        │                                                ▲
        │        ▼                                                │
        │  run_flow (goga/afm) ── exit_code ──▶ emit_run_completed│
        └──────────────────────────────────────────────────┘  goga/hooks/catalog
                                                              (+3 Action records)
```

### Contract Surface

**Cell `goga/pipeline/hooks`** (facade `goga/pipeline/hooks/__init__.py` exposes exactly these
11 names via `__all__`, alphabetical; Python rules: only `__all__` names constitute the facade):

**Entity: `PipelineIdentity(name: str, display_name: str = "", description: str, source: str)`**
- Type: class (dataclass, `kw_only=True`)
- Declared `location`: `identity.py`
- Facade obligation: importable from `goga.pipeline.hooks`
- Properties: `name -> str` (discovered stem, no `.yml` suffix), `display_name -> str`
  (authored header name, empty when header names none), `description -> str` (DSL header),
  `source -> str` (exactly `project` or `user`)
- Semantic requirements: pure facts — nothing is read here; `name` non-empty, no path
  separators, no `.yml` suffix; `source in ("project", "user")` guarded in `__post_init__`
  (repo convention, cf. `PipelineEntry`)
- Imported dependencies: none
- Annotation context: `convention` for data-model rules

**Entity: `WorkflowDecision(kind: str, workflow_name: str | None)`**
- Type: class (dataclass, `kw_only=True`)
- Declared `location`: `identity.py`
- Properties: `kind -> str` (exactly one of `disabled`, `explicit`, `auto-match`,
  `silent-miss`), `workflow_name -> str | None` (present for explicit and auto-match, None
  otherwise)
- Semantic requirements: mirrors the resolution the operation already made; `kind` literal
  guarded in `__post_init__`

**Entity: `WorkIdentity(branch: str, slug: str | None = None, year: str | None = None)`**
- Type: class (dataclass, `kw_only=True`)
- Declared `location`: `identity.py`
- Properties: `branch -> str`, `slug -> str | None` (normalized topic slug), `year -> str | None`
  (four digits)
- Semantic requirements: hosting decision happens in the constructing operation; the
  branch-only form (`slug`/`year` None) serves a branch hosting no topic

**Entity: `CompositionStage(id: str, title: str)`**
- Type: class (dataclass, `kw_only=True`)
- Declared `location`: `contexts.py`
- Properties: `id -> str`, `title -> str` — one row of the final composition as the card
  shows it

**Entity: `RunCreated(pipeline, decision, workflow, composition, provenance, work, statuses, runtime_dir)`**
- Type: class (dataclass, `kw_only=True`; read-only fact bundle)
- Declared `location`: `contexts.py`
- Properties: `pipeline -> PipelineIdentity`, `decision -> WorkflowDecision`,
  `workflow -> WorkflowDocument | None` (the effective workflow),
  `composition -> list[CompositionStage]`, `provenance -> list[str]`,
  `work -> WorkIdentity`, `statuses -> list[str]`, `runtime_dir -> str` (posix string)
- Semantic requirements: read-only facts of the composed moment — a hook observes and
  cannot alter
- Imported dependencies: `PipelineIdentity`/`WorkflowDecision`/`WorkIdentity` (local),
  `WorkflowDocument` from `goga/pipeline/workflow`

**Entity: `RunCompleted(... same eight ..., exit_code: int)`**
- Type: class (dataclass, `kw_only=True`); same fields as `RunCreated` plus `exit_code`
  (zero, non-zero, or a spawn failure 126/127) — facts recomputed at the completion moment
- Declared `location`: `contexts.py`

**Entity: `ToolContribution(tool: str, document: WorkflowDocument)`**
- Type: class (dataclass, `kw_only=True`)
- Declared `location`: `overlay.py`
- Properties: `tool -> str` (platform-assigned identity), `document -> WorkflowDocument`

**Entity: `WorkflowOverlay(workflow: WorkflowDocument | None, provenance: list[str])`**
- Type: class (dataclass, `kw_only=True`)
- Declared `location`: `overlay.py`
- Properties: `workflow -> WorkflowDocument | None` (None only in the passthrough case),
  `provenance -> list[str]` (committed tools, enumeration order)
- Semantic requirements: a None workflow with a non-empty provenance never occurs

**Routine: `merge_workflow_overlay(base: WorkflowDocument | None, contributions: list[ToolContribution]) -> overlay: WorkflowOverlay`**
- Type: function
- Declared `location`: `overlay.py`
- Semantic requirements (authored-wins merge — full algorithm in Task 5): pure (inputs never
  mutated, new instances); deterministic; prompt joins non-empty texts with a single blank
  line (authored first, then contributions in enumeration order); memory whole-block
  (authored unbeatable, else later tool wins); stage fields: authored-set never overwritten,
  unset fields take the later contributing tool's value; `skip=False` overrides nothing;
  extend: authored names win, among tools later entry wins; result stays declarative
  (compiles through the unchanged `compile_flow`)
- Constraints: no filesystem reads/writes; no mutation of `base`, the contributions, or
  their maps; no invented instructions

**Entity: `WorkflowAmendment(pipeline, decision, workflow, work)`**
- Type: class (dataclass, `kw_only=True`) — the read-and-contribute view of one tool
- Declared `location`: `amendments.py`
- Properties: `pipeline -> PipelineIdentity`, `decision -> WorkflowDecision`,
  `workflow -> WorkflowDocument | None` (the original authored workflow — post decision,
  post runner-skip merge, pre-layer; read-only and identical for every tool),
  `work -> WorkIdentity`
- Method: `contribute(document: WorkflowDocument)` — buffers one declarative contribution;
  whole replacement (a later call replaces the earlier buffered document); an empty document
  (no prompt, no stages, no extend, no memory) is discarded by the delivery with a warning;
  does not cancel, redirect, or defer the operation
- Internal (not contract surface): `_contribution: WorkflowDocument | None` — a private
  `field(init=False, default=None, repr=False)`, read only by the delivery (same package)
- Requirements: no staged-application state exists — a tool never sees another tool's
  contribution; the buffer belongs to this tool alone

**Entity: `PipelineHooks()`**
- Type: class
- Declared `location`: `events.py`
- Requirements: cheap construction (no enumeration, no imports at construction); one
  `HookRegistry` per run carries every checkpoint of a command (lazy `build_once`);
  every context built from caller-passed values — no repository reads at a checkpoint
- Methods:
  - `amend_workflow(pipeline, decision, workflow, work) -> overlay: WorkflowOverlay` — the
    hard amendment delivery (full algorithm in Task 7)
  - `emit_run_created(pipeline, decision, overlay, composition, work, statuses, runtime_dir)`
    — fire-and-forget soft emission; failing hook warns, launch proceeds
  - `emit_run_completed(pipeline, decision, overlay, composition, work, statuses, runtime_dir, exit_code)`
    — fires on every launch-attempt return path; the run's exit code is never affected
- Imported dependencies (platform facade, relative): `HookRegistry`, `wrap_context`,
  `build_hook_arguments`, `emit_hook_event`, `declared_actions` from `goga/hooks`;
  `WorkflowDocument` from `goga/pipeline/workflow`; local models from `.amendments`,
  `.contexts`, `.identity`, `.overlay`

**Cell `goga/hooks/catalog`** (additive change):

**Routine: `declared_actions()`** (existing, `location: catalog.py`)
- Requirements gain three records: `pipeline/amend_workflow` (**hard** — the platform's
  first), `pipeline/run_completed` (soft), `pipeline/run_created` (soft). `Action` and the
  ten published records are untouched; the catalog grows to 13 records.

**Cell `goga/pipeline`** (changed entities):

**Entity: `PipelineCard(name, description, stages, provenance: list[str] = [])`**
- Declared `location`: `pipeline_card.py` — gains `provenance` implemented as
  `field(default_factory=list)` (the DSL `[]` default is a representation; the factory is
  applied at construction — two cards never share the list); constructions without it
  remain valid

**Routine: `describe_pipeline(name, project_dir, user_dir, workflow, no_workflow) -> card: PipelineCard`**
- Declared `location`: `describe_pipeline.py` — algorithm extended to 7 steps (Task 9):
  fact resolution via one early `parse_dsl` read, delivery unless disabled, compilation with
  the overlay workflow, `provenance=overlay.provenance` on the card; no events, no statuses,
  no launch; `GOGA_SKIP_STAGES` never read

**Routine: `run_pipeline(name, project_dir, user_dir, port, parallel=None) -> exit_code: int`**
- Declared `location`: `run_pipeline.py` — algorithm extended to 17 steps (Task 10): fact
  resolution, amendment delivery between the skip merge and compilation, composition build,
  status resolution, emissions around the launch

**Routine: `pipeline_cli(argv: list[str]) -> exit_code: int`**
- Declared `location`: `cli.py` — the card template gains the conditional `tools:` line;
  both failure paths (`_run_card`, `_run_execution`) render the hard amendment error
  (`ValueError`) and the registry build's fatal `ImportError` cleanly (no traceback)

### Re-exports

None — no `->Name: {}` blocks exist in any of the three manifests.

### Usages Context

- **`convention`** (`.goga/usages/conventions.md`, both changed manifests): kw_only
  dataclasses, relative intra-package imports, Google-style docstrings, `logging.getLogger(__name__)`,
  blank-line block separation, test placement `tests/<pkg>/test_<module>.py`, test naming
  `test_<what>_<scenario>`, venv execution. Applied in every task.
- **`argparse`** (inline, `goga/pipeline` manifest): stdlib argparse, `list`/`run`
  subcommands, flag surface — unchanged by this feature; the CLI task touches only the card
  template and the catch tuples.
- **`cli_entrypoint`** (inline): `__main__.py` stays a thin runpy wrapper — NOT touched by
  this plan.
- **`default_prompts`** (inline): the four packaged prompt files and the atomic
  validate-all → wipe → write materialization — run step 11, unchanged; the new steps
  bracket it without touching it.

### Imported Usages

- **`per-tool-delivery`** from `goga/hooks` (`goga/hooks/.usages/per-tool-delivery.md`):
  the staged delivery loop of `amend_workflow` — loop skeleton, public primitives
  (`HookRegistry`, `subscriptions_for`, `self_context`, `wrap_context`, `build_hook_arguments`),
  tool-grouped commit. Applied as written; the soft-discard leg is replaced by the hard
  raise (the action's catalog error class drives it — the practice itself defers to the
  catalog: "Treat a failure per the action's error class"). → Task 7.
- **`declaring-actions`** from `goga/hooks` (`goga/hooks/.usages/declaring-actions.md`):
  the emission contract of the two notifications — `emit_hook_event(registry, domain,
  action, context_for=...)` with a shared-instance `context_for`. → Task 7.
- **`registering-hooks`** from `goga/hooks` (`goga/hooks/.usages/registering-hooks.md`):
  the hook signature (`self`/`context` injection, fixed offered names) and failure behavior
  behind every checkpoint. → Tasks 6, 7 (and the test setups of Tasks 9-11).
- **`checkpoints`** from `goga/pipeline/hooks` (`goga/pipeline/hooks/.usages/checkpoints.md`):
  the checkpoint surface consumption patterns — fact resolution in the operation,
  amend-before-compile, emit-around-launch, the card form. → Tasks 9, 10.
- **`topic-paths`** from `goga/history` (`goga/history/.usages/topic-paths.md`): the branch
  read and topic-dir resolution behind `WorkIdentity`; slug/year derive from the returned
  directory (`topic_dir.name`, `topic_dir.parent.name`). → Tasks 9, 10.
- **`topic-statuses`** from `goga/history` (`goga/history/.usages/topic-statuses.md`): the
  status facts of the run events (`assemble_status_scale` + `resolve_topic_status`, single
  assembly, nested artifacts honored). → Task 10.
- Compiler/afm/docker/workflow imports (`compile-flow`, `parse-dsl`, `serialize-flow`,
  `memory-emission`, `run-flow`, `ensure-in-docker`, `parse-workflow`, `memory`): unchanged
  consumption, context only.

### Local Usages

None planned. Per the design's `.usages/` Update (verified against the workspace):

- `goga/pipeline/hooks/.usages/checkpoints.md` — exists, current; additions needed: none.
- `goga/pipeline/.usages/registering-hooks.md` — exists, current; additions needed: none.
- `goga/pipeline/.usages/{describe-pipeline,run-pipeline,pipeline-cli}.md` — exist, synced
  to the new surface; updates needed: none.

No usage-file creation or update tasks. (`docs/features/pipelines/hooks.md` + mkdocs
traceability are deferred to documentation task items, not the code cells — per the design.)

### External Dependencies

- stdlib: `dataclasses`, `logging`, `tempfile`, `pathlib`, `sys` — no new third-party code.
- `pyyaml` (`yaml.YAMLError` channels — existing).
- Test tools: `pytest` (>= 8.0), `pytest-cov`, `ruff` (>= 0.15) — all in the project venv.
- The `afm` binary is reached only through `run_flow` and is mocked in every test that
  would launch; the platform enumeration boundary
  (`goga.hooks.tools.packages.packages_distributions`) is pinned by fixtures, never by
  installing real tool packages.

## Facts

- Contracts are materialized and lint-clean: `goga lint` → 78 cells, 0 errors. The three
  CODEMANIFESTs (`goga/pipeline/hooks` created; `goga/pipeline`, `goga/hooks/catalog`
  changed) are **read-only** for the implementation agent.
- `goga/pipeline/hooks/` currently contains ONLY `CODEMANIFEST` + `.usages/checkpoints.md`.
  All five modules and the facade are missing.
- Catalog today: 10 records in `_DECLARED_ACTIONS` (`goga/hooks/catalog/catalog.py:40-51`),
  sorted by `(domain, name)` — onboarding(2), statuses(1), topics(7). Adding the pipeline
  block places it between `onboarding` and `statuses`.
- `run_pipeline` is currently an 11-step routine (discovery → AFM_DIR → workflow → skip →
  compile → prompts → `run_flow`); `describe_pipeline` is a 5-step routine. The contracts
  now specify 17 and 7 steps respectively.
- `PipelineCard` (`goga/pipeline/pipeline_card.py`) has exactly `name`, `description`,
  `stages` — no `provenance`.
- `cli.py` `_run_card`/`_run_execution` catch
  `(StructuralError, WorkflowSyntaxError, RuntimeError, yaml.YAMLError, OSError, UnicodeDecodeError)`
  — no `ValueError`, no `ImportError`. Platform precedent for the pair:
  `history.py:114` catches `(ValueError, ImportError)`.
- Platform message format (`goga/hooks/dispatch/emit.py:96-99`, hard leg):
  `f"hook {subscription.name} of tool {subscription.tool} failed on {domain}.{action}: {exc}"`
  raised `from exc`. The zone copies this shape verbatim.
- Delivery proxy (`goga/hooks/dispatch/delivery.py:54-61`): reads and calls pass through
  `__getattr__`, attribute assignment/deletion raise `AttributeError` — `contribute()` is
  reachable through the proxy (a method call), and it is the ONLY write channel.
- Registry API: `HookRegistry.build_once()` (`state.py:54`),
  `subscriptions_for(domain, action)` (`state.py:110`, enumeration order),
  `self_context(tool)` (`state.py:127`). Single-build guarantee per instance.
- Per-tool loop precedent: `goga/onboarding/participation/participation.py:130-139` —
  the zone's loop skeleton with the failure leg replaced by the hard raise.
- `apply_skip_stages(None, skips)` constructs a skip-only document;
  `apply_skip_stages(x, [])` returns `x` unchanged (`apply_skip_stages.py:73-75, 78-82`).
- `resolve_topic_dir` raises `ValueError` when the input normalizes to an empty slug
  (`goga/history/paths.py:60-61`); `resolve_current_branch_name() -> str | None`;
  `assemble_status_scale() -> StatusScale` (`statuses/assembly.py:38`);
  `resolve_topic_status(topic_dir: Path, scale: StatusScale) -> list[str]`
  (`goga/history/status.py:35`); `current_year()` on the `goga.history` facade.
- Workflow models (`goga/pipeline/workflow/`): `WorkflowDocument(prompt, stages, extend,
  memory)` with `field(default_factory=dict)` maps; `WorkflowStage` fields in fixed order
  `agent, prompt, loop, skills, skip=False, approve, manual, notes, reflect, memory` —
  `manual` is three-state (`None`/`True`/`False`), `skip=False` is the default and means
  "not skipped"; `WorkflowExtendStage(before, after, agent, loop, approve, body)`;
  `WorkflowMemory(method, path, max_rules, commit, mode)`.
- `parse_dsl(text)` returns `(header, _, _)` with `header.name` / `header.description` —
  the established fact-resolution read (`describe_pipelines.py:63`).
- Test infrastructure: `tests/pipeline/conftest.py` provides `isolated_cwd`; the platform
  boundary fixtures `pin_package_environment` / `install_tool_package` live in
  `tests/hooks/conftest.py` (cross-package import precedent: `tests/test_cli.py:20`); the
  `afm_dir` fixture is local to `tests/pipeline/test_run_pipeline.py:35` (mirror it in the
  new hooks test file); `mock.patch.object(_run_pipeline_module, ...)` with
  `sys.modules["goga.pipeline.run_pipeline"]` is the established mock pattern
  (`goga.pipeline.run_pipeline` is shadowed in the package `__init__` — string patch paths
  through the facade fail on Python 3.10).
- Import-cycle safety (verified by the design's trace): importing `goga.pipeline.hooks`
  first executes `goga/pipeline/__init__.py` (partial), which imports `.run_pipeline` →
  `.hooks` → `..workflow`; `goga.pipeline.workflow` and `goga.hooks` never import back into
  `goga.pipeline` submodules loaded by its `__init__` — the same shape as the existing
  `.compiler → ..workflow` edge. The zone MUST use relative imports only.
- Boundary note (recorded, not changed): `assemble_status_scale` (history) builds its own
  registry internally — a run that resolves statuses enumerates tool packages a second
  time through the history cell. Pre-existing platform behavior, outside these contracts.

## Gap Analysis

- **Missing contract entities**: all 11 zone entities (five modules + facade); the zone
  facade `__init__.py` does not exist.
- **Missing facade exposure**: `goga.pipeline.hooks.__all__` with the 11 names.
- **Incorrect `location` placement**: none — no zone code exists to misplace; consumer
  files already sit at their declared locations.
- **API mismatches**: `PipelineCard` lacks `provenance`; `run_pipeline`/`describe_pipeline`
  lack the amendment/emission steps; `pipeline_cli` lacks the `tools:` line and the
  `ValueError`/`ImportError` catches; the catalog lacks the three pipeline records.
- **Behavioral mismatches**: same as above — with the contracts materialized, code and
  contract diverge on exactly the changed surface.
- **Existing code that can be reused**: everything else — `resolve_workflow`,
  `apply_skip_stages`, `compile_flow`, `order_stages`, `list_pipelines`, the platform
  facade, the history facade, the prompt materialization block (run step 11). The zone is
  purely additive around them.
- **Test coverage gaps**: `tests/pipeline/hooks/` does not exist;
  `tests/pipeline/test_run_pipeline_hooks.py` does not exist; the catalog, card,
  describe, and CLI test files predate the feature (their existing tests must stay green —
  they pin the byte-identical no-tools behavior).
- **Missing visibility in workspace or git**: the zone `CODEMANIFEST` +
  `.usages/checkpoints.md`, `registering-hooks.md`, and the three synced pipeline usages
  are untracked/modified in git — expected; committing is outside this plan.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow). Package order: `goga/hooks/catalog` → `goga/pipeline/hooks` → `goga/pipeline` → integration verification.

### Task 1: Catalog records for the three pipeline actions (TDD coding)

The `goga/hooks/catalog` cell declares `declared_actions()` — the single source of known
subscription addresses. This task appends the three pipeline-domain records to
`_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py`: `pipeline/amend_workflow` (hard —
the platform's first hard action), `pipeline/run_completed` (soft), `pipeline/run_created`
(soft). Purely additive: `Action` and the ten published records are untouched. The catalog
grows to 13 records; `declared_actions()` sorts by `(domain, name)`, so the pipeline block
orders `amend_workflow`, `run_completed`, `run_created` between `onboarding` and `statuses`.
No behavior beyond the data. The address resolution of every later checkpoint depends on
these records existing, hence the task comes first.

**Usages relevant to this task:**
- `convention`: docstring style, no new imports needed (dataclass `Action` already imported).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: extend `tests/hooks/catalog/test_catalog.py` (the file already
  exists with `TestCatalogContract` / logic classes) with the design scenario:

  ```
  test_catalog_carries_the_three_pipeline_records

  Setup: none (pure catalog read).
  Input: declared_actions()
  Trace: _DECLARED_ACTIONS (13 records) → sorted by (domain, name)
  Assertions:
  [("pipeline", "amend_workflow", "hard"),
   ("pipeline", "run_completed", "soft"),
   ("pipeline", "run_created", "soft")] all present;
  pipeline block ordered between onboarding and statuses
  ```

  Also assert the total record count is 13 and that the ten pre-existing records are
  unchanged (regression pin). Expected to fail at this stage — the records do not exist.
- [x] **Code**: append to `_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py`:

  ```python
  Action(domain="pipeline", name="amend_workflow", error_class="hard"),
  Action(domain="pipeline", name="run_created", error_class="soft"),
  Action(domain="pipeline", name="run_completed", error_class="soft"),
  ```

  (list order is irrelevant — `declared_actions()` sorts — but keep the file's existing
  grouping style.)
- [x] **Interface verification**: `python -m pytest tests/hooks/catalog/test_catalog.py -q`
  — all pass, including the pre-existing tests.
- [x] **Logic tests**: covered by the scenario above (presence, error classes, ordering,
  count); add nothing speculative.
- [x] **Debugging**: `python -m pytest tests/hooks/catalog -q` — fix implementation code
  until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: `declared_actions()` still returns every record,
  complete and unfiltered, deterministic; `Action` untouched; the module docstring still
  matches.
- [x] **Lint**: `python -m ruff check goga/hooks/catalog tests/hooks/catalog && python -m ruff format --check goga/hooks/catalog tests/hooks/catalog` — fix formatting if necessary.

### Task 2: Zone package skeleton and test scaffolding (infrastructure)

Create the `goga/pipeline/hooks` Python package (the cell directory exists with its
`CODEMANIFEST` and `.usages/checkpoints.md`; only the Python package is missing) and the
mirrored test package `tests/pipeline/hooks/`. The facade `__init__.py` starts as a
documented placeholder and grows incrementally — each later module task adds its names, and
Task 7 completes it to exactly the 11 contract names (the precedent: the workflow cell's
facade was "Built incrementally: each entity task adds its module's import and `__all__`
entry"). The test `conftest.py` re-exports the platform boundary fixtures exactly as the
design's General Setup specifies.

**Usages relevant to this task:**
- `convention`: test placement (`tests/pipeline/hooks/test_<module>.py`), every test
  directory carries `__init__.py`, relative imports inside the package.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga/pipeline/hooks/__init__.py` — package docstring naming the zone (the
  hooks zone of the pipeline domain) and an empty `__all__: list[str] = []` for now; no
  imports yet (the modules do not exist). Relative imports only, once they appear.
- [x] Create `tests/pipeline/hooks/__init__.py` (empty) and `tests/pipeline/hooks/conftest.py`:

  ```python
  from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401
  ```

  (cross-package import precedent: `tests/test_cli.py:20`; the fixtures pin the two
  platform boundary points — `packages_distributions` and the `sys.modules` entry of a
  `goga_tool_*` package — so the platform code under test runs for real).
- [x] Verify collection: `python -m pytest tests/pipeline/hooks --collect-only -q` — the
  package collects cleanly (zero tests is expected at this stage).
- [x] Verify package importability: `python -c "import goga.pipeline.hooks"` — no error
  (the partially-initialized-parent edge is safe: `goga/pipeline/__init__.py` does not
  import the zone yet).
- [x] Lint: `python -m ruff check goga/pipeline/hooks tests/pipeline/hooks && python -m ruff format --check goga/pipeline/hooks tests/pipeline/hooks` — fix formatting if necessary.
  (Formatting fix applied to the pre-existing `.usages/checkpoints.md` code blocks —
  ruff 0.16 formats embedded Python in Markdown; rewrap only, no content change.)

### Task 3: Zone identity models — `identity.py` (TDD coding)

Implement the three identity entities of the zone in `goga/pipeline/hooks/identity.py`:
`PipelineIdentity(name: str, display_name: str = "", description: str, source: str)`,
`WorkflowDecision(kind: str, workflow_name: str | None)`, and
`WorkIdentity(branch: str, slug: str | None = None, year: str | None = None)` — the
identity vocabulary of every pipeline event. All three are `@dataclass(kw_only=True)` per
`convention`, snake_case fields, type-hinted (mandatory), docstrings in the repo style
(Args sections mirroring the CODEMANIFEST annotations). No behavior: pure fact carriers.
Two contract invariants get runtime guards via `__post_init__` (repo convention, cf.
`PipelineEntry`): `PipelineIdentity` — `source in ("project", "user")` (and the `name`
rules: non-empty, no path separators, no `.yml` suffix); `WorkflowDecision` — `kind in
("disabled", "explicit", "auto-match", "silent-miss")`. Add the three names to the facade.

**Usages relevant to this task:**
- `convention`: kw_only dataclasses, Google-style docstrings, relative imports
  (`from __future__ import annotations`; `str | None` fields follow the existing
  `WorkflowStage` precedent under the future-annotations import).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/pipeline/hooks/test_identity.py`:
  - importability from the facade after this task: `from goga.pipeline.hooks import
    PipelineIdentity, WorkflowDecision, WorkIdentity` (fails now — expected);
  - each model is a `kw_only` dataclass (positional construction raises `TypeError`;
    cf. `is_kw_only_dataclass` helper from `tests/conftest.py` used by the catalog tests);
  - declared field names, order, and defaults exactly per the signatures —
    `PipelineIdentity`: `name, display_name="", description, source`;
    `WorkflowDecision`: `kind, workflow_name`;
    `WorkIdentity`: `branch, slug=None, year=None`.
- [x] **Code**: create `goga/pipeline/hooks/identity.py` with the three dataclasses and
  the `__post_init__` guards (`ValueError` on a bad `source` literal, a bad `kind`
  literal, and invalid `name` input — non-empty, no `/`/`\\`, no `.yml` suffix).
- [x] **Code**: add the three names to `goga/pipeline/hooks/__init__.py` imports and
  `__all__` (keep `__all__` alphabetical).
- [x] **Interface verification**: `python -m pytest tests/pipeline/hooks/test_identity.py -q`
  — all pass.
- [x] **Logic tests** (same file):
  - `PipelineIdentity(source="elsewhere")` raises `ValueError`; `source="project"` and
    `source="user"` construct;
  - `PipelineIdentity(name="dir/x")` / `name="x.yml"` / `name=""` raise `ValueError`;
    `display_name` defaults to `""`;
  - `WorkflowDecision(kind="bogus")` raises; all four literal kinds construct;
    `workflow_name=None` accepted;
  - `WorkIdentity(branch="b")` alone constructs the branch-only form
    (`slug is None`, `year is None`).
- [x] **Debugging**: `python -m pytest tests/pipeline/hooks -q` — fix implementation code
  until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: fields/properties match the declared API; pure facts —
  no repository reads anywhere in the module; facade exposes the three names.
- [x] **Lint**: `python -m ruff check goga/pipeline/hooks tests/pipeline/hooks && python -m ruff format --check goga/pipeline/hooks tests/pipeline/hooks` — fix formatting, apply decomposition if necessary.

### Task 4: Zone run-event contexts — `contexts.py` (TDD coding)

Implement `goga/pipeline/hooks/contexts.py`: `CompositionStage(id: str, title: str)` (one
row of the final composition as the card shows it), `RunCreated(pipeline, decision,
workflow, composition, provenance, work, statuses, runtime_dir)`, and `RunCompleted` (the
same eight fields plus `exit_code: int` — the facts recomputed at the completion moment,
including the spawn-failure codes 126/127). All `@dataclass(kw_only=True)`, all fields
required (no defaults — the signatures carry none), read-only fact bundles: a hook observes
and cannot alter. `WorkflowDocument` imports from `..workflow`; the local identity types
from `.identity`. The contract tests for these models live in
`tests/pipeline/hooks/test_events.py` (per the design's Source File Registry — the file is
created here and extended by Task 7, which owns the emission behavior).

**Usages relevant to this task:**
- `convention`: kw_only dataclasses, docstrings, relative imports
  (`from ..workflow import WorkflowDocument` for type hints).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/pipeline/hooks/test_events.py` (data-model
  contract block; Task 7 appends the delivery/emission classes):
  - the three names importable from `goga.pipeline.hooks` (fails now — expected);
  - `kw_only` enforced (positional construction raises `TypeError`);
  - field names and order exactly per the signatures:
    `CompositionStage(id, title)`; `RunCreated(pipeline, decision, workflow, composition,
    provenance, work, statuses, runtime_dir)`; `RunCompleted` = the same eight plus
    `exit_code` last.
- [x] **Code**: create `goga/pipeline/hooks/contexts.py` with the three dataclasses
  (docstrings mirroring the CODEMANIFEST property annotations).
- [x] **Code**: add `CompositionStage`, `RunCreated`, `RunCompleted` to the facade
  `__init__.py` and `__all__` (alphabetical).
- [x] **Interface verification**: `python -m pytest tests/pipeline/hooks/test_events.py -q`
  — all pass.
- [x] **Logic tests**: construction carries every field verbatim (build a
  `RunCreated`/`RunCompleted` from identity/decision/workflow fixtures and assert each
  attribute round-trips; `RunCompleted.exit_code` accepts 0, 3, and 127); dataclass
  equality of two identically-built contexts holds.
- [x] **Debugging**: `python -m pytest tests/pipeline/hooks -q` — fix implementation code
  until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: read-only facts — no methods, no behavior, no defaults
  beyond the declared signatures; facade exposes the names.
- [x] **Lint**: `python -m ruff check goga/pipeline/hooks tests/pipeline/hooks && python -m ruff format --check goga/pipeline/hooks tests/pipeline/hooks` — fix formatting, apply decomposition if necessary.

### Task 5: The authored-wins overlay — `overlay.py` (TDD coding)

Implement `goga/pipeline/hooks/overlay.py`: the data models `ToolContribution(tool: str,
document: WorkflowDocument)` and `WorkflowOverlay(workflow: WorkflowDocument | None,
provenance: list[str])`, and the Routine `merge_workflow_overlay(base: WorkflowDocument |
None, contributions: list[ToolContribution]) -> WorkflowOverlay` — compose the effective
workflow from the authored base and the committed contributions, authored intent winning
per slot. This is the semantic heart of the feature.

The verified algorithm (transfer from the design — implement exactly this):

```
1. IF contributions empty: RETURN WorkflowOverlay(workflow=base, provenance=[])
   — the passed workflow object itself, zero rebuild (the no-tool-packages guarantee)
2. prompt  = "\n\n".join(non-empty texts: authored first, then contributions in order) or None
3. memory  = authored block when present — unbeatable; otherwise the LATER contributing
             tool's block; no field-level merging
4. stages  = per name (authored names first, then fresh names):
             authored-set fields never overwritten;
             unset fields take the later contributing tool's value;
             no authored entry → fully tool-defined WorkflowStage
5. extend  = authored entries kept; a contribution entry under an authored name dropped;
             among tools the later entry wins per name
6. provenance = [c.tool for c in contributions]
7. RETURN WorkflowOverlay(WorkflowDocument(prompt, stages, extend, memory), provenance)
```

Field "is set" semantics (the authored-wins table):

| Field | SET when | Note |
|---|---|---|
| `agent`, `prompt`, `loop`, `skills`, `approve`, `notes`, `reflect`, `memory` | value is not `None` | `None` = unset |
| `manual` | value is not `None` | three-state: `True` (force) and `False` (explicit cancel) are BOTH set; absence = unset |
| `skip` | value is `True` | `skip=False` overrides nothing — only a positive skip is authored intent |

Stage merge (per name — `FIELDS` is the `WorkflowStage` field set, `DEFAULT[f]` is
`None` / `skip=False`):

```
authored = base.stages.get(name) if base else None
values   = {f: getattr(authored, f) for f in FIELDS} if authored
         else {f: DEFAULT[f] for f in FIELDS}          # None / skip=False
authored_set = {f: SET(f, values[f]) for f in FIELDS}
for c in contributions:                                 # enumeration order
    cs = c.document.stages.get(name)
    if cs is None: continue
    for f in FIELDS:
        if SET(f, getattr(cs, f)) and not authored_set[f]:
            values[f] = getattr(cs, f)                  # later tool wins
merged_stages[name] = WorkflowStage(**values)
```

Constraints: pure — new `WorkflowStage`/`WorkflowDocument` instances (field values by
reference, the repo's shallow-copy convention as in `apply_skip_stages.py:78`; nothing
mutated); no filesystem; deterministic; the result stays declarative (it compiles through
the unchanged `compile_flow`). No errors raised — invalid shapes cannot occur (committed
contributions are non-empty by construction; structural validation of the merged result
belongs to `compile_flow`, e.g. a contribution naming an unknown stage surfaces as its
`StructuralError`). `WorkflowOverlay` requirement: a None workflow with a non-empty
provenance never occurs — `workflow` is `None` only when `base` is `None` and no
contribution committed (unreachable past the empty short-circuit).

**Usages relevant to this task:**
- `convention`: kw_only dataclasses for the two models, Google-style docstring for the
  Routine, relative imports (`from ..workflow import WorkflowDocument, WorkflowStage`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/pipeline/hooks/test_overlay.py`:
  - `ToolContribution`, `WorkflowOverlay`, `merge_workflow_overlay` importable from
    `goga.pipeline.hooks` (fails now — expected);
  - both models `kw_only` with the declared fields;
  - `merge_workflow_overlay` signature: parameters `base`, `contributions`, return
    `WorkflowOverlay` (inspect.signature).
- [x] **Code**: create `goga/pipeline/hooks/overlay.py` — the two dataclasses and the
  merge implementing the algorithm above exactly (blank-line-joined prompt, whole-block
  memory, per-field stage merge with the SET table, authored-names-win extend,
  enumeration-order provenance, empty short-circuit returning the passed object).
- [x] **Code**: add `ToolContribution`, `WorkflowOverlay`, `merge_workflow_overlay` to the
  facade `__init__.py` and `__all__` (alphabetical).
- [x] **Interface verification**: `python -m pytest tests/pipeline/hooks/test_overlay.py -q`
  — contract tests pass.
- [x] **Logic tests** (same file — the design's scenarios, verbatim):

  ```
  test_merge_prompt_concatenates_authored_first_then_tools
  Setup: base = WorkflowDocument(prompt="authored"); contributions:
    [ToolContribution("t1", WorkflowDocument(prompt="one")),
     ToolContribution("t2", WorkflowDocument(prompt="two"))].
  Input: merge_workflow_overlay(base, contributions)
  Trace:
    texts = ["authored", "one", "two"]        # empties dropped
    prompt = "authored\n\none\n\ntwo"          # single blank line joins
    WorkflowOverlay(provenance=["t1", "t2"])
  Assertions:
    overlay.workflow.prompt == "authored\n\none\n\ntwo"
    overlay.provenance == ["t1", "t2"]
  ```

  ```
  test_merge_stage_fields_fill_only_unset_later_tool_wins
  Setup: base.stages = {"build": WorkflowStage(agent="author-agent", loop=2)};
    t1 contributes WorkflowStage(agent="t1-agent", skills=["s1"]);
    t2 contributes WorkflowStage(agent="t2-agent", loop=5).
  Input: merge_workflow_overlay(base, [tc(t1), tc(t2)])
  Trace:
    stage "build": authored agent set → blocks both tools
      authored loop=2 set → blocks t2
      skills unset → t1 sets ["s1"] (t2 sets none)
    → WorkflowStage(agent="author-agent", loop=2, skills=["s1"])
  Assertions:
    overlay.workflow.stages["build"].agent == "author-agent"
    overlay.workflow.stages["build"].loop == 2
    overlay.workflow.stages["build"].skills == ["s1"]
    base.stages["build"].skills is None            # purity — input untouched
  ```

  ```
  test_merge_skip_false_overrides_nothing_authored_skip_unbeatable
  Setup: base.stages = {"build": WorkflowStage(skip=True)};
    t1 contributes WorkflowStage(skip=False); fresh name "deploy":
    authored has no entry, t1 contributes WorkflowStage(skip=True).
  Input: merge_workflow_overlay(base, [tc(t1)])
  Trace:
    "build": authored skip=True SET → t1's False blocked
    "deploy": no authored entry → t1's skip=True fills
  Assertions:
    overlay.workflow.stages["build"].skip is True
    overlay.workflow.stages["deploy"].skip is True
  ```

  ```
  test_merge_memory_authored_block_unbeatable_and_later_tool_wins
  Setup: case A — base.memory = WorkflowMemory(max_rules=5), t1
    contributes WorkflowMemory(max_rules=99); case B — base.memory=None,
    t1 and t2 both contribute blocks (max_rules=7 / max_rules=9).
  Input: both merges.
  Trace:
    A: authored block present → kept whole (max_rules=5)
    B: no authored block → later tool t2 wins (max_rules=9)
  Assertions:
    A: overlay.workflow.memory.max_rules == 5
    B: overlay.workflow.memory.max_rules == 9
  ```

  ```
  test_merge_extend_authored_names_win_and_later_tool_wins
  Setup: base = WorkflowDocument(extend={"audit": WorkflowExtendStage(
    after=["build"], body={"title": "Audit"})});
    t1 contributes extend={"audit": WorkflowExtendStage(before=["build"],
    body={"title": "X"}), "notify": WorkflowExtendStage(after=["deploy"],
    body={"title": "N1"})};
    t2 contributes extend={"notify": WorkflowExtendStage(after=["audit"],
    body={"title": "N2"})}.
  Input: merge_workflow_overlay(base, [tc(t1), tc(t2)])
  Trace:
    "audit": under an authored name → t1's entry dropped, the authored
      after=["build"] entry kept
    "notify": fresh name → t1 sets it, t2 replaces (later tool wins)
  Assertions:
    overlay.workflow.extend["audit"].after == ["build"]
    overlay.workflow.extend["notify"].after == ["audit"]
    len(overlay.workflow.extend) == 2
    base.extend["audit"].after == ["build"]        # purity — input untouched
  ```

  ```
  test_merge_empty_base_tools_build_the_document
  Setup: base None; t1 contributes WorkflowDocument(prompt="one",
    stages={"build": WorkflowStage(agent="a")}); t2 contributes
    WorkflowDocument(prompt="two").
  Input: merge_workflow_overlay(None, [tc(t1), tc(t2)])
  Trace:
    contributions non-empty → no passthrough short-circuit
    no authored layer → texts ["one", "two"] → prompt "one\n\ntwo"
    stage "build": no authored entry → fully tool-defined (agent="a")
    provenance ["t1", "t2"]; the document exists (every contribution non-empty)
  Assertions:
    overlay.workflow is not None
    overlay.workflow.prompt == "one\n\ntwo"
    overlay.workflow.stages["build"].agent == "a"
    overlay.provenance == ["t1", "t2"]
  ```

  ```
  test_merge_passthrough_short_circuit_returns_base_object
  Setup: base = WorkflowDocument(prompt="x").
  Input: merge_workflow_overlay(base, []) and merge_workflow_overlay(None, []).
  Trace: contributions empty → WorkflowOverlay(workflow=base, provenance=[])
  Assertions:
    overlay.workflow is base            # the passed object itself
    overlay.provenance == []
    merge(None, []).workflow is None
  ```

- [x] **Debugging**: `python -m pytest tests/pipeline/hooks -q` — fix implementation code
  until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: purity (no input mutated anywhere — the assertions
  pin it), determinism, declarative result shape (`WorkflowDocument` with `stages` as
  `dict[str, WorkflowStage]`, `extend` as `dict[str, WorkflowExtendStage]`); facade
  exposes the three names.
- [x] **Lint**: `python -m ruff check goga/pipeline/hooks tests/pipeline/hooks && python -m ruff format --check goga/pipeline/hooks tests/pipeline/hooks` — fix formatting, apply decomposition if necessary.

### Task 6: The amendment view — `amendments.py` (TDD coding)

Implement `goga/pipeline/hooks/amendments.py`: `WorkflowAmendment(pipeline:
PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, work:
WorkIdentity)` — the read-and-contribute view of one tool. `@dataclass(kw_only=True)`,
four read-only fact fields (the original authored workflow — post decision, post
runner-skip merge, pre-layer — identical for every tool), plus the method:

```
contribute(document):
1. self._contribution = document   # whole replacement; no validation here
                                   # (the delivery checks emptiness post-hoc)
```

`_contribution: WorkflowDocument | None` is a private `field(init=False, default=None,
repr=False)` — not contract surface; read only by the delivery (same package). Errors:
none raised; a bad document surfaces at the consumer (`compile_flow`) or as the
empty-contribution warning. Edge cases: repeat calls replace; the buffer is per-tool (per
view).

**Usages relevant to this task:**
- `registering-hooks` (`goga/hooks/.usages/registering-hooks.md`): the hook signature that
  receives this view — `context` (this object, delivered through the read-only proxy:
  read attributes and call methods freely, attribute assignment blocked) and `self` (the
  tool's isolated context). `contribute` is reachable through the proxy and is the ONLY
  write channel.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/pipeline/hooks/test_amendments.py`:
  - `WorkflowAmendment` importable from `goga.pipeline.hooks` (fails now — expected);
  - `kw_only`, fields exactly `pipeline, decision, workflow, work`;
  - `contribute` is a public method with signature `(document)`;
  - `_contribution` is `init=False`, default `None`, excluded from `repr`.
- [x] **Code**: create `goga/pipeline/hooks/amendments.py` (imports:
  `from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity`;
  `from ..workflow import WorkflowDocument`).
- [x] **Code**: add `WorkflowAmendment` to the facade `__init__.py` and `__all__`.
- [x] **Interface verification**: `python -m pytest tests/pipeline/hooks/test_amendments.py -q`
  — all pass.
- [x] **Logic tests**: `contribute(WorkflowDocument(prompt="a"))` sets the buffer;
  a second `contribute(WorkflowDocument(prompt="b"))` replaces it whole
  (`_contribution.prompt == "b"`); a fresh view starts with `_contribution is None`;
  `contribute` returns `None`.
- [x] **Debugging**: `python -m pytest tests/pipeline/hooks -q` — fix implementation code
  until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: no staged-application state (the four fields are the
  constructor facts, unchanged by `contribute`); the buffer belongs to this view alone.
- [x] **Lint**: `python -m ruff check goga/pipeline/hooks tests/pipeline/hooks && python -m ruff format --check goga/pipeline/hooks tests/pipeline/hooks` — fix formatting, apply decomposition if necessary.

### Task 7: The checkpoint surface — `events.py` + facade completion (TDD coding)

Implement `goga/pipeline/hooks/events.py`: `PipelineHooks` — the checkpoint surface of the
pipeline domain. Construction is cheap (`self._registry: HookRegistry | None = None`; no
enumeration, no imports, no repository reads). One lazily-built `HookRegistry` per
instance carries every checkpoint:

```
_ensure_registry():
1. IF self._registry is None:
   - registry = HookRegistry(); registry.build_once(); self._registry = registry
2. RETURN self._registry                       # ImportError propagates (single fatal case)

amend_workflow(pipeline, decision, workflow, work):
1. record = the declared_actions() entry (domain="pipeline", action="amend_workflow")
   → absent: raise ValueError("unknown hook action: pipeline.amend_workflow")
2. groups = subscriptions_for("pipeline", "amend_workflow") grouped per tool
   (enumeration order)
3. IF groups empty: RETURN merge_workflow_overlay(workflow, [])   # passthrough
4. FOR tool, subs in groups.items():
   a. amendment = WorkflowAmendment(pipeline=pipeline, decision=decision,
                                    workflow=workflow, work=work)  # fresh view, fresh buffer
   b. proxy = wrap_context(amendment)
   c. FOR sub in subs:
      - sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))
      - ON Exception AS reason:
        raise ValueError(f"hook {sub.name} of tool {tool} failed on "
                         f"pipeline.amend_workflow: {reason}") from reason
        # hard: stop at the first failure; the tool's buffer dies with its view
   d. IF amendment._contribution is None: continue        # never contributed — silent
   e. IF empty(amendment._contribution):                  # prompt None ∧ stages {} ∧ extend {} ∧ memory None
      - logger.warning("tool %s contributed an empty document to "
                       "pipeline.amend_workflow: discarded", tool)
      - continue
   f. contributions.append(ToolContribution(tool=tool, document=amendment._contribution))
5. RETURN merge_workflow_overlay(workflow, contributions)
```

The hard-failure message copies the platform's format (`emit.py:96-99`) verbatim shape:
hook name, tool, address, reason. `BaseException` (e.g. `KeyboardInterrupt`) is not
intercepted (platform convention: intercept `Exception` only). The emissions:

```
emit_run_created(pipeline, decision, overlay, composition, work, statuses, runtime_dir):
1. context = RunCreated(pipeline=..., decision=..., workflow=overlay.workflow,
   composition=..., provenance=overlay.provenance, work=..., statuses=...,
   runtime_dir=...) — one shared instance
2. emit_hook_event(self._ensure_registry(), "pipeline", "run_created",
   context_for=lambda _tool: context)
   → None — fire-and-forget; soft failures warn inside the platform

emit_run_completed(..., exit_code):
1. context = RunCompleted(... the same facts ..., exit_code=exit_code)
2. emit_hook_event(self._ensure_registry(), "pipeline", "run_completed",
   context_for=lambda _tool: context)
```

Errors: `ValueError` (hard hook failure) and `ImportError` (broken tool package, from
`build_once`) propagate — both rendered by `pipeline_cli` as clean stderr messages
(Task 11). Edge cases: no tool packages installed → registry builds empty → passthrough
(byte-identical runs); a tool subscribed but silent → no commit, no warning. This task also
completes the facade to exactly the 11 contract names.

**Usages relevant to this task:**
- `per-tool-delivery` (`goga/hooks/.usages/per-tool-delivery.md`): the staged delivery
  loop — applied as written; the soft-discard leg is replaced by the hard raise (the
  action's catalog error class drives it — the practice defers to the catalog).
- `declaring-actions` (`goga/hooks/.usages/declaring-actions.md`): the emission contract —
  `emit_hook_event(registry, domain, action, context_for=...)`; returning the same
  instance shares the read-only context.
- `registering-hooks` (`goga/hooks/.usages/registering-hooks.md`): registration and
  failure behavior behind every checkpoint.
- Platform import surface (relative): `from ...hooks import HookRegistry,
  build_hook_arguments, emit_hook_event, wrap_context, declared_actions` (three dots:
  `goga.pipeline.hooks` → `goga`); local models via `from .amendments import ...` etc.
  The zone never imports `..workflow` in `events.py` beyond type hints (contexts carry it).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: extend `tests/pipeline/hooks/test_events.py`:
  - `PipelineHooks` importable from the facade; methods `amend_workflow`,
    `emit_run_created`, `emit_run_completed` exist with the declared signatures
    (`inspect.signature`, `self` excluded);
  - construction performs no enumeration (a `pin_package_environment({"goga_tool_demo":
    ["demo-dist"]})` boundary with `call_count == 0` right after `PipelineHooks()`);
  - facade completion:

    ```
    test_zone_facade_exports_exactly_the_contract
    Setup: import goga.pipeline.hooks.
    Input: sorted(goga.pipeline.hooks.__all__)
    Assertions:
    __all__ == ["CompositionStage", "PipelineHooks", "PipelineIdentity",
                "RunCompleted", "RunCreated", "ToolContribution",
                "WorkIdentity", "WorkflowAmendment", "WorkflowDecision",
                "WorkflowOverlay", "merge_workflow_overlay"]
    each name importable from the package root
    ```

- [x] **Code**: create `goga/pipeline/hooks/events.py` implementing the algorithms above
  (`logger = logging.getLogger(__name__)`; `mock`-free; relative imports only).
- [x] **Code**: complete the facade `__init__.py` to the 11 names.
- [x] **Interface verification**: `python -m pytest tests/pipeline/hooks/test_events.py -q`
  — all pass.
- [x] **Logic tests** (same file; tool-package simulation via
  `pin_package_environment({"goga_tool_demo": ["demo-dist"]})` +
  `install_tool_package("goga_tool_demo", register_hooks=...)` — the platform code under
  test runs for real; design scenarios verbatim):

  ```
  test_amend_workflow_commits_per_tool_and_merges
  Setup: pinned environment with two tool packages. The first subscribes
  ("pipeline", "amend_workflow", "hardening", hook) where hook(context) reads
  context.pipeline.name, context.decision.kind, context.workflow (recording
  id(context.workflow) into its self context) and calls
  context.contribute(WorkflowDocument(prompt="harden")). The second
  (goga_tool_second) subscribes the same address with a hook that records
  id(context.workflow) and context.workflow.prompt into its own self AFTER
  contributing WorkflowDocument(prompt="second").
  Input: PipelineHooks().amend_workflow(pipeline=PipelineIdentity(
  name="deploy", description="d", source="project"), decision=...,
  workflow=WorkflowDocument(prompt="authored"), work=WorkIdentity(branch="b"))
  Trace:
    registry.build_once()                     # real enumeration, one build
    subscriptions_for("pipeline", "amend_workflow") → 2 subscriptions, 2 tools
    per tool: WorkflowAmendment(view over the SAME workflow) → wrap_context
      → build_hook_arguments → hook(context=proxy)   # only "context" declared
      → contribute(...) sets the tool's own buffer
    both non-empty → ToolContribution per tool
    merge → overlay
  Assertions:
    overlay.workflow.prompt == "authored\n\nharden\n\nsecond"
    overlay.provenance == [tool_id_of("goga_tool_demo"), tool_id_of("goga_tool_second")]
    first_seen_id == second_seen_id            # the same original workflow object
    second_seen_prompt == "authored"           # the first tool's contribution invisible
  ```

  ```
  test_amend_workflow_registry_built_once_across_checkpoints
  Setup: pinned environment (boundary mock returned by pin_package_environment);
  a tool subscribing both amend_workflow and run_completed.
  Input: one PipelineHooks instance: amend_workflow(...) then emit_run_completed(...).
  Trace: amend → _ensure_registry (build #1); emit_run_completed → _ensure_registry
  (no rebuild)
  Assertions: boundary.call_count == 1   # packages_distributions read exactly once
  ```

  ```
  test_amend_workflow_hard_failure_stops_command_and_discards
  Setup: pinned env; tool subscribes amend_workflow with hook(context) raising
  RuntimeError("boom") after calling context.contribute(WorkflowDocument(prompt="x"));
  a second tool subscribes the same address with a working hook.
  Input: PipelineHooks().amend_workflow(...) (facts as above).
  Trace: tool #1 hook raises → ValueError("hook ... of tool ... failed on
  pipeline.amend_workflow: boom") → walk stops — tool #2 never called
  Assertions:
    pytest.raises(ValueError, match="pipeline.amend_workflow: boom")
    merge never ran → no overlay returned; tool #2's hook not called
  ```

  ```
  test_empty_contribution_discarded_with_warning_silent_tool_ok
  Setup: pinned env with two tools: one contributes WorkflowDocument() (all defaults),
  one subscribes but never calls contribute.
  Input: amend_workflow(...) with base=WorkflowDocument(prompt="a").
  Trace: tool #1: buffer set, empty → warning, discard; tool #2: buffer None → silent;
  merge with [] → passthrough
  Assertions:
    overlay.workflow.prompt == "a"; overlay.provenance == []
    caplog has exactly one discard warning (names tool #1)
  ```

- [x] **Debugging**: `python -m pytest tests/pipeline/hooks -q` — fix implementation code
  until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: commit granularity is the tool; an address without
  subscriptions returns the passthrough overlay (the passed workflow, empty provenance);
  no repository/filesystem reads at any checkpoint; one registry per instance across
  amendment + emissions; the facade is exactly the 11 names.
- [x] **Lint**: `python -m ruff check goga/pipeline/hooks tests/pipeline/hooks && python -m ruff format --check goga/pipeline/hooks tests/pipeline/hooks` — fix formatting, apply decomposition if necessary.

### Task 8: `PipelineCard.provenance` (TDD coding)

Add the `provenance` field to `PipelineCard` in `goga/pipeline/pipeline_card.py`:
`provenance: list[str] = field(default_factory=list)` (import `field` from
`dataclasses`), a docstring line for it (the tools whose contributions committed into the
composition, in enumeration order; empty when none contributed). Existing constructions
compile unchanged (the default); two cards never share the list (factory per instance).
`CardStage` is untouched.

**Usages relevant to this task:**
- `convention`: dataclass field style; the DSL signature default `[]` is a representation —
  the actual default factory is applied at construction (the `WorkflowDocument` map-fields
  precedent).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: extend `tests/pipeline/test_pipeline_card.py`:
  - the `PipelineCard` field set is now exactly `name, description, stages, provenance`;
  - construction without `provenance` remains valid (existing tests already pin this —
    they must stay green unchanged: the regression proof of the additive default).
- [x] **Code**: add the field + docstring line to `goga/pipeline/pipeline_card.py`.
- [x] **Interface verification**: `python -m pytest tests/pipeline/test_pipeline_card.py -q`
  — all pass.
- [x] **Logic tests** (design scenario, verbatim):

  ```
  test_pipeline_card_provenance_default_factory_isolated
  Setup: two PipelineCard(name="a", description="d", stages=[]) constructions
  (no provenance).
  Input: mutate card_a.provenance.append("x").
  Trace: default_factory=list per construction → independent lists
  Assertions: card_b.provenance == []
  ```

- [x] **Debugging**: `python -m pytest tests/pipeline/test_pipeline_card.py -q` — fix
  implementation code until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: `PipelineCard` remains a `kw_only` dataclass; the
  field order ends with `provenance`; the facade `goga.pipeline.PipelineCard` unchanged.
- [x] **Lint**: `python -m ruff check goga/pipeline/pipeline_card.py tests/pipeline/test_pipeline_card.py && python -m ruff format --check goga/pipeline/pipeline_card.py tests/pipeline/test_pipeline_card.py` — fix formatting if necessary.

### Task 9: The card form through the amendment layer — `describe_pipeline.py` (TDD coding)

Rewire `goga/pipeline/describe_pipeline.py` to the 7-step contract. Current state: 5 steps
(locate → resolve → compile → order → card). The change inserts the amendment layer:

1. Discover entries via `list_pipelines` and locate the matching name; on no match report
   the missing pipeline with a readable error (unchanged).
2. Resolve the workflow via `resolve_workflow` with the pipeline name and the workflow
   flags (unchanged; CLI flags — no `GOGA_SKIP_STAGES` read, ever).
3. Resolve the amendment facts (the `PipelineIdentity` — the authored header name and
   description read via `parse_dsl` from the pipeline-file text; the `WorkflowDecision`;
   and the `WorkIdentity` — the current branch via `resolve_current_branch_name`, the
   literal `"unknown"` when it resolves None; the hosting topic slug and year via
   `resolve_topic_dir` when its directory exists, the branch-only form otherwise) and,
   unless the decision is disabled, deliver the amendment via the `PipelineHooks`
   checkpoint surface with the resolved workflow — receiving the overlay result; a
   disabled decision delivers nothing and the overlay is the passthrough `WorkflowOverlay`
   of the resolved workflow.
4. Compile the pipeline-file via `compile_flow` into a temporary flow-file located in a
   system temporary directory with the overlay workflow, and receive the documents tuple.
5. Order the compiled stages via `order_stages` (unchanged).
6. Build the card: name and description from the parsed pipeline document header (the
   documents tuple — NOT a re-parse); one `CardStage` per ordered stage; the card
   provenance from the overlay.
7. Discard the temporary flow-file and return the card.

Fact-resolution details (identical to the run form): `header, _, _ =
parse_dsl(pipeline_path.read_text())`;
`PipelineIdentity(name=match.name, display_name=header.name,
description=header.description, source=match.source.value)`; the kind-derivation
matrix — `no_workflow` → ("disabled", None); explicit name given (`workflow_name
not in (None, "")`) and a document resolved → ("explicit", workflow_name); no
explicit name and a document resolved → ("auto-match", name); document None
(explicit-missing / auto-miss / containment escape) → ("silent-miss", None);
`branch = resolve_current_branch_name() or "unknown"`;
`try: topic_dir = resolve_topic_dir(branch)` / `except ValueError: topic_dir = None`;
`topic_dir.is_dir()` → `WorkIdentity(branch=branch, slug=topic_dir.name,
year=topic_dir.parent.name)` else `WorkIdentity(branch=branch)`.

Constraints: no afm launch, no run events, no writes into project/runtime directories; do
not re-parse the pipeline-file for the card fields — the single early `parse_dsl` read of
step 3 serves the amendment facts only. **No events, no statuses, no launch.**

**Usages relevant to this task:**
- `checkpoints` (`goga/pipeline/hooks/.usages/checkpoints.md`): the card form section —
  compose through the same amendment with the same precedence, report
  `overlay.provenance`, no run events.
- `topic-paths` (`goga/history/.usages/topic-paths.md`): the branch read and topic-dir
  resolution behind the work identity; slug/year from the returned directory.
- `convention`: docstring style, relative imports (`from .hooks import PipelineHooks,
PipelineIdentity, ...`; `from ..history import resolve_current_branch_name,
resolve_topic_dir`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: extend `tests/pipeline/test_describe_pipeline.py` — the
  signature is unchanged (existing tests pin it); add the new-surface pin: the returned
  card carries `provenance == []` on the no-tools path (deterministic via
  `pin_package_environment({})` — the registry builds empty, the overlay is the
  passthrough).
- [x] **Code**: rewire `goga/pipeline/describe_pipeline.py` to the 7 steps above
    (hooks instance scoped to the call; `logger.debug` may add provenance/composition —
    additive, debug level).
- [x] **Interface verification**: `python -m pytest tests/pipeline/test_describe_pipeline.py -q`
  — all pass, including the pre-existing tests (they pin the no-tools composition and
  must stay green).
- [x] **Logic tests** (design scenarios, verbatim):

  ```
  test_describe_pipeline_reports_provenance_through_same_layer
  Setup: pinned env with a tool contributing prompt="tool-text" via amend_workflow;
  a workflow file in .goga/workflows/deploy.yml with prompt: "authored".
  Input: describe_pipeline("deploy", project_dir, user_dir, workflow=None,
  no_workflow=False) — real compile_flow into the temp dir (no mocks beyond the
  tool env).
  Trace:
    resolve_workflow → auto-match → WorkflowDocument(prompt="authored")
    facts → amend → overlay(prompt="authored\n\ntool-text", ["<tool>"])
    compile_flow(overlay.workflow) → temp flow-file → discarded
    PipelineCard(provenance=["<tool>"])
  Assertions:
    card.provenance == ["<tool-id>"]
    card.name == <authored header name>
  ```

  ```
  test_describe_pipeline_disabled_reports_raw_composition
  Setup: a workflow file .goga/workflows/deploy.yml exists (prompt: "authored");
  pinned env with a tool whose amend_workflow hook would fail loudly if called;
  isolated_cwd.
  Input: describe_pipeline("deploy", project_dir, user_dir, workflow=None,
  no_workflow=True) — real compile_flow into the temp dir.
  Trace:
    step 2: resolve_workflow(..., no_workflow=True) → None
      → decision ("disabled", None)
    step 3: disabled → no delivery, overlay is the passthrough
    (workflow=None, provenance=[])
    step 4: compile the raw authored DSL → card without the tool layer
  Assertions:
    amend hook not called
    card.provenance == []
    card.stages == <raw composition — same as a no-workflow-file compile>
    no exception
  ```

  (Both scenarios live in `tests/pipeline/test_describe_pipeline.py` as
  `TestDescribePipelineAmendmentLayer`, running the real platform over the
  `tests/hooks/conftest.py` boundary fixtures re-exported by
  `tests/pipeline/conftest.py`; the disabled scenario's workflow adds a skip
  directive so "raw composition" is falsifiable.)
- [x] **Debugging**: `python -m pytest tests/pipeline/test_describe_pipeline.py tests/pipeline -q`
  — fix implementation code until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: the stage composition equals the composition a run of
  the same pipeline with the same workflow flags would execute; the silent auto-match miss
  keeps the layer active onto the empty base; `GOGA_SKIP_STAGES` never read; the temp
  flow-file lives outside the project and runtime directories and is removed.
- [x] **Lint**: `python -m ruff check goga/pipeline/describe_pipeline.py tests/pipeline/test_describe_pipeline.py && python -m ruff format --check goga/pipeline/describe_pipeline.py tests/pipeline/test_describe_pipeline.py` — fix formatting, apply decomposition if necessary.

### Task 10: The run form through the amendment layer — `run_pipeline.py` (TDD coding)

Rewire `goga/pipeline/run_pipeline.py` to the 17-step contract. The existing 11 steps
renumber with four insertions — new step 8 (facts), new step 9 (delivery), new steps 12-14
(composition, statuses, creation emission), step 16 (completion emission):

1. `list_pipelines` → `PipelineEntry` match → absolute `pipeline_path`; missing → stderr
   message, `return 1` (no events).
2. `AFM_DIR` env → `afm_dir` (unset → `RuntimeError("AFM_DIR not set")`);
   `runtime_dir = afm_dir.as_posix()`.
3. `GOGA_WORKFLOW_DISABLED` / `GOGA_WORKFLOW_NAME` env → decision inputs →
   `resolve_workflow(name, workflow_name, no_workflow)` → `WorkflowDocument | None`.
4. `GOGA_SKIP_STAGES` split → `apply_skip_stages(workflow, skips)` → merged `workflow`
   (None-safe; empty split → unchanged).
5. Facts: `pipeline_path.read_text()` → `parse_dsl(text)[0]` → header (`name`,
   `description`) → `PipelineIdentity`; kind-derivation (below) → `WorkflowDecision`;
   `branch = resolve_current_branch_name() or "unknown"` → guarded `resolve_topic_dir(branch)`
   → `WorkIdentity`.
6. `hooks = PipelineHooks()` (one instance for the whole run).
   `decision.kind != "disabled"` → `overlay = hooks.amend_workflow(pipeline=...,
   decision=..., workflow=..., work=...)`; else `overlay = WorkflowOverlay(workflow=
   merged_workflow, provenance=[])` (no delivery, no registry build from the amendment
   side — the first registry build happens at the creation emission).
7. `resolve_project_name()` → `compile_flow(pipeline_path, flow_path,
   workflow=overlay.workflow, root_dir=str(Path.cwd().resolve()), project_name=...)` →
   `(pipeline_doc, flow_doc)`; structural errors propagate (no events).
8. Prompt materialization (unchanged steps: validate-all → wipe → write four files into
   `<AFM_DIR>/prompts/`).
9. `order_stages(flow_doc.stages)` → `composition = [CompositionStage(id=s.id,
   title=s.name) for s in ordered]`.
10. Statuses (hosting form only): `scale = assemble_status_scale()`, `statuses =
    resolve_topic_status(topic_dir, scale)`; branch-only → `statuses = []` (no scale
    assembly).
11. `hooks.emit_run_created(pipeline=identity, decision=decision, overlay=overlay,
    composition=composition, work=work, statuses=statuses, runtime_dir=runtime_dir)`.
12. `exit_code = run_flow(flow_path, port, max_parallel=parallel)` (spawn failures are
    return codes 126/127 — returns, not raises).
13. Hosting form: `statuses = resolve_topic_status(topic_dir, scale)` recomputed (one
    scale, two reads); branch-only stays `[]`.
    `hooks.emit_run_completed(..., exit_code=exit_code)`; `return exit_code`.

Kind-derivation matrix (the operation recomputes what `resolve_workflow` does not
report):

```
no_workflow                                   → ("disabled", None)
explicit name given (workflow_name not in (None, ""))
  and a document resolved                      → ("explicit", workflow_name)
no explicit name and a document resolved       → ("auto-match", name)
document None (explicit-missing / auto-miss /
containment escape)                            → ("silent-miss", None)
```

Work-identity edge handling: detached HEAD / missing git / non-repo → `"unknown"` branch,
branch-only work; a fully non-ASCII branch (empty slug) → `resolve_topic_dir` raises
`ValueError` → guarded `topic_dir = None` → branch-only form. Errors: unchanged channels
plus the hard `ValueError` from the amendment (before any compile/write/launch) and the
`ImportError` from the registry build. An exception escaping `run_flow` has no exit code
to report and propagates without a completion emission (boundary, documented).

**Usages relevant to this task:**
- `checkpoints` (`goga/pipeline/hooks/.usages/checkpoints.md`): fact resolution in the
  operation, amend-before-compile, emit-around-launch (creation after prompts
  materialize, completion on every return path), statuses recompute at the completion
  moment.
- `topic-paths` (`goga/history/.usages/topic-paths.md`): branch read, topic-dir
  resolution, slug/year from the returned directory.
- `topic-statuses` (`goga/history/.usages/topic-statuses.md`): one `assemble_status_scale()`
  per run, two `resolve_topic_status` reads, nested artifacts honored (`completed/plan.md`
  outranks `todo.md`).
- `compile-flow`, `parse-dsl`, `default_prompts`, `run-flow`, `convention`: unchanged
  consumption; the documents tuple is read-only after construction.

**Testing rules for this task** (design General Setup, binding): the new operation-level
test file is `tests/pipeline/test_run_pipeline_hooks.py` (mirror a local `afm_dir`
fixture from `tests/pipeline/test_run_pipeline.py:35`); mock at module boundaries only —
`mock.patch.object(_run_pipeline_module, "compile_flow"/"run_flow")` with
`_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]` (the module is shadowed
in the package `__init__`; string patch paths fail on Python 3.10); the git branch read is
mocked (`resolve_current_branch_name` on the same module) since tmp dirs are not repos;
history trees are real `.goga/history/<year>/<slug>/` structures under `tmp_path` +
`monkeypatch.chdir(tmp_path)` (`isolated_cwd`); the tree is built under `current_year()`
(or with `current_year` mocked to a fixed value) — never a hardcoded year literal, and
assertions derive the expected year the same way, so the suite survives a year boundary;
the platform env is pinned (`pin_package_environment` + `install_tool_package`) so the
registry, delivery, and emissions run for real.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/pipeline/test_run_pipeline_hooks.py` — the
  signature is unchanged (existing `tests/pipeline/test_run_pipeline.py` contract tests
  pin it; they must stay green); pin the new import wiring: the module now imports
  `PipelineHooks` & co. from `.hooks` and the four history names from `..history`
  (attribute presence on the module).
- [x] **Code**: rewire `goga/pipeline/run_pipeline.py` to the 17 steps (insert the fact
  resolution after the skip merge, the delivery before `resolve_project_name`/compile,
  the composition/statuses/creation before `run_flow`, the recomputed-statuses completion
  after it; update the docstring's step numbering and the Raises section with the hard
  `ValueError`/`ImportError` channels).
- [x] **Interface verification**: `python -m pytest tests/pipeline/test_run_pipeline_hooks.py tests/pipeline/test_run_pipeline.py tests/pipeline/test_run_pipeline_workflow.py -q`
  — all pass (the pre-existing suites are the no-tools regression proof).
- [x] **Logic tests** (design scenarios, verbatim):

  ```
  test_run_pipeline_full_event_sequence_around_launch
  Setup: afm_dir fixture (AFM_DIR → tmp); a minimal real pipeline file in project_dir;
  workflow absent (silent-miss); pinned env with a tool subscribing run_created and
  run_completed, recording received facts into its self context; compile_flow and
  run_flow mocked (run_flow → 3); resolve_current_branch_name mocked → "feature-demo";
  tmp .goga/history/<current_year()>/feature-demo/ with todo.md.
  Input: run_pipeline("deploy", project_dir, user_dir, port=50321)
  Trace:
    facts: identity (parse_dsl header), decision ("silent-miss", None),
      work ("feature-demo", "feature-demo", current_year())
    amend (silent-miss keeps the layer active) → passthrough (no subs on
      amend_workflow for this tool) → overlay.workflow None
    compile_flow(workflow=None ...)           # mocked documents tuple
    order_stages → composition [CompositionStage("build", "Build")]
    statuses ["todo"]                          # real scale + topic dir
    emit_run_created (records: composition ids, runtime_dir posix)
    run_flow → 3
    statuses recomputed → emit_run_completed (exit_code=3)
    return 3
  Assertions:
    result == 3
    created_facts["pipeline"].name == "deploy"
    created_facts["decision"].kind == "silent-miss"
    created_facts["composition"] == [CompositionStage(id="build", title="Build")]
    created_facts["statuses"] == ["todo"]
    created_facts["runtime_dir"] == afm_dir.as_posix()
    completed_facts["exit_code"] == 3
    order: created recorded before run_flow called, completed after
  ```

  ```
  test_spawn_failure_still_emits_completion_with_code
  Setup: as the positive run test (pinned env, event-recording tool keeping facts in
  its self context); compile_flow mocked; run_flow mocked → 127 (the afm binary
  missing from PATH).
  Input: run_pipeline("deploy", project_dir, user_dir, port=50321)
  Trace:
    facts → amend → compile (mocked) → prompts materialize
    emit_run_created
    run_flow → 127                    # a return code, not an exception
    statuses recomputed → emit_run_completed(exit_code=127)
    return 127
  Assertions:
    result == 127
    completed_facts["exit_code"] == 127
    completed recorded after created; no exception raised
  ```

  ```
  test_missing_pipeline_and_structural_error_fire_no_events
  Setup: event-recording tool installed; case A — unknown pipeline name; case B — a
  malformed workflow file (valid name resolution path).
  Input: run_pipeline("nope", ...); run_pipeline("deploy", ...) with the malformed
  workflow.
  Trace:
    A: return 1 at discovery — checkpoints unreached
    B: WorkflowSyntaxError propagates from resolve_workflow (step 6) — before the
       delivery
  Assertions:
    A: result == 1; zero events recorded
    B: pytest.raises(WorkflowSyntaxError); zero events recorded
  ```

  ```
  test_work_identity_unknown_branch_and_empty_slug_guard
  Setup: resolve_current_branch_name mocked → None; then → "Ветка" (fully non-ASCII —
  every character drops, slug empty).
  Input: run_pipeline fact resolution (observed via the recorded work of
  emit_run_created).
  Trace:
    None → branch "unknown" → resolve_topic_dir("unknown") missing → branch-only
    "Ветка" → normalize_topic_slug("Ветка") == "" → resolve_topic_dir raises
      ValueError → guarded → branch-only
    (a partial-ASCII name such as "Бranched" slugs to "ranched" — it covers the
     missing-directory leg, not the guard)
  Assertions:
    work.branch == "unknown" / work.slug is None / work.year is None   (case A)
    work.branch == "Ветка" / slug is None / year is None               (case B)
    no exception; events still fired
  ```

  ```
  test_workflow_decision_kind_derivation_matrix
  Setup: four env configurations (disabled; explicit+exists; explicit+missing; no-name
  auto-match hit and miss).
  Input: run_pipeline fact resolution (observed via recorded facts).
  Trace:
    disabled → ("disabled", None)
    explicit+exists → ("explicit", "ci")
    explicit+missing → ("silent-miss", None)
    auto-match hit → ("auto-match", "deploy"); miss → ("silent-miss", None)
  Assertions: each recorded decision matches the table exactly.
  ```

  ```
  test_disabled_decision_skips_delivery_compiles_raw_and_still_emits
  Setup: env GOGA_WORKFLOW_DISABLED=1; event-recording tool with an amendment hook
  that would fail loudly if called; run_flow → 0; GOGA_SKIP_STAGES unset.
  Input: run_pipeline("deploy", ...).
  Trace:
    decision ("disabled", None) → no amend call
    overlay = WorkflowOverlay(workflow=None, provenance=[])
    compile_flow(workflow=None)
    emit_run_created(decision.kind == "disabled", overlay.provenance == [])
    emit_run_completed(exit_code=0)
  Assertions:
    amend hook not called
    created_facts["decision"].kind == "disabled"
    created_facts["provenance"] == []
    result == 0
  ```

  ```
  test_statuses_recomputed_at_completion_and_branch_only_stays_empty
  Setup: hosting form — todo.md present, a completed/plan.md written by a fake "run"
  (the run_flow mock writes it); branch-only — no topic dir.
  Input: both runs with an event-recording tool.
  Trace:
    hosting: created statuses ["todo"] → completed statuses ["done"]
             (completed/plan.md outranks todo — maximal-present recomputed at the
              completion moment)
    branch-only: [] at both moments; assemble_status_scale never called
                 (assert via the enumeration boundary)
  Assertions:
    created_facts["statuses"] == ["todo"]
    completed_facts["statuses"] == ["done"]
    branch-only: both == [] and boundary call_count == 1  # only the pipeline registry build
  ```

  ```
  test_emit_soft_failure_warns_and_never_affects_exit_code
  Setup: pinned env; tool's run_completed hook raises; run_flow mocked → 0.
  Input: full run_pipeline flow.
  Trace: emit_run_completed → emit_hook_event intercepts → logger.warning; run
  continues → return 0
  Assertions:
    result == 0
    caplog contains a warning naming the tool, "run_completed", "boom"
  ```

- [x] **Debugging**: `python -m pytest tests/pipeline -q` — fix implementation code until
  all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: every requirement of the 17-step contract — absolute
  paths to `compile_flow`/`run_flow`; `port`/`parallel` forwarding unchanged; env reads
  exactly `AFM_DIR`, `GOGA_WORKFLOW_DISABLED`, `GOGA_WORKFLOW_NAME`, `GOGA_SKIP_STAGES`;
  DISABLED precedence; skip merge before delivery; delivery before compile; creation
  after prompt materialization and before launch; completion on every return path; the
  runtime dir fact as posix string; with no tool packages the passthrough — output
  exactly as before.
- [x] **Lint**: `python -m ruff check goga/pipeline/run_pipeline.py tests/pipeline/test_run_pipeline_hooks.py && python -m ruff format --check goga/pipeline/run_pipeline.py tests/pipeline/test_run_pipeline_hooks.py` — fix formatting, apply decomposition if necessary.

### Task 11: CLI card `tools:` line and clean hard-error rendering — `cli.py` (TDD coding)

Two additive edits in `goga/pipeline/cli.py`. (1) The card form `_run_card`: after the
stage loop —

```python
if card.provenance:
    print()
    print(f"tools: {', '.join(card.provenance)}")
```

Uniform rule: the tools block is one blank line + one field line whenever provenance is
non-empty (with zero stages it follows the separator's blank line — deterministic, and the
empty-provenance output stays byte-identical in every form). (2) Failure rendering: add
`ValueError` and `ImportError` to the caught tuples of `_run_card` and `_run_execution`
(the hard amendment stops both forms; the registry build's fatal `ImportError` stops every
form — platform precedent `history.py:114` catches `(ValueError, ImportError)`; contract
step 5: "Render an operation failure as a clean readable message to stderr (no
traceback)"). The parser, dispatch, `__main__` delegation, and the docker guard are
untouched.

**Usages relevant to this task:**
- `argparse`: the parser surface is unchanged — this task touches only the card template
  and the catch tuples.
- `cli_entrypoint`: `__main__.py` stays a thin wrapper — not touched.
- `convention`: docstring style; relative imports unchanged.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: extend `tests/pipeline/test_pipeline_cli.py` — the card template
  requirement: "when the card provenance is non-empty, one blank line and one `tools:`
  field line follow the stage blocks — the contributing tools comma-separated in
  provenance order; an empty provenance adds nothing — the output stays byte-identical to
  the provenance-free card" (fails now — expected).
- [x] **Code**: add the `tools:` block to `_run_card`; add `ValueError` and `ImportError`
  to the `_run_card` and `_run_execution` caught tuples.
- [x] **Interface verification**: `python -m pytest tests/pipeline/test_pipeline_cli.py -q`
  — all pass, including every pre-existing template test (byte-identity regression).
- [x] **Logic tests** (design scenarios, verbatim):

  ```
  test_cli_card_renders_tools_line_and_stays_byte_identical_without_it
  Setup: two PipelineCards — one with provenance=["t1", "t2"], one default; capsys.
  Input: render both through the card path (factor the rendering via the _run_card
  flow with a stubbed describe_pipeline).
  Trace:
    card with provenance → stage blocks, blank, "tools: t1, t2"
    card without → stage blocks only
  Assertions:
    out_with.endswith("\ntools: t1, t2\n")
    out_without does not contain "tools:"
    out_without == <exact pre-feature expected bytes>   # byte-identical
  ```

  ```
  test_run_pipeline_hard_amendment_renders_clean_error_no_launch
  Setup: as the positive run test, but the tool's amend_workflow hook raises; run_flow
  mocked with a call recorder.
  Input: pipeline_cli argv ["deploy", "--port", "50321"] (or run_pipeline directly +
  the CLI wrapper for the message).
  Trace:
    run → step 9 amend → ValueError → propagates
    run_flow.assert_not_called(); prompts dir untouched; no events emitted
  Assertions:
    capsys err contains "pipeline.amend_workflow" and "boom"; no traceback
    exit code != 0
  ```

- [x] **Debugging**: `python -m pytest tests/pipeline/test_pipeline_cli.py tests/pipeline -q`
  — fix implementation code until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: every template requirement (flat list, overview,
  card, tools line); no traceback for any operation failure; `--port`/`--parallel`
  behavior untouched.
- [x] **Lint**: `python -m ruff check goga/pipeline/cli.py tests/pipeline/test_pipeline_cli.py && python -m ruff format --check goga/pipeline/cli.py tests/pipeline/test_pipeline_cli.py` — fix formatting if necessary.

### Task 12: Integration verification of the wired flows (integration tests)

Final cross-entity gate. The feature's cross-entity behavior is covered by the scenario
suites of Tasks 7-11 (zone delivery over the real platform, run/card flows through the
zone, history facts, CLI rendering — with only module-boundary mocks, per the design's
General Setup). This task verifies the composed whole and guards the read-only surfaces.

**Usages relevant to this task:**
- `convention`: full-suite execution in the venv; test classification (contract/logic/
  integration all present).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Run the full suite: `python -m pytest` — 5686 passed, 9 failed. All 9 failures
  (docker runner/integration, onboarding integration, `python -m` subprocess entrypoint,
  `--version` enumeration pin) reproduce identically on the pre-feature base commit
  `751c2b9` in a scratch worktree — sandbox environment limitations (docker binary absent,
  exit 127; subprocess env loses `yaml`; no installed package metadata for the version
  gate), pre-existing and not feature defects (environment-verification items, not
  automatable here). The targeted plan suites: 147 passed.
- [x] Verify the zone facade: `python -c "import goga.pipeline.hooks as h; assert sorted(h.__all__) == ['CompositionStage', 'PipelineHooks', 'PipelineIdentity', 'RunCompleted', 'RunCreated', 'ToolContribution', 'WorkIdentity', 'WorkflowAmendment', 'WorkflowDecision', 'WorkflowOverlay', 'merge_workflow_overlay']"`
  — passes; the facade IS the contract surface (11 names).
- [x] Verify the cell graph: `goga lint` — 78 cells, 0 errors (contracts and cells stay
  consistent).
- [x] Verify the untouched surfaces: `git status` clean; zero diff on
  `goga/pipeline/workflow`, the `goga/hooks` platform modules (dispatch/registry/tools),
  and the compiler; the three `CODEMANIFEST`s (plus the packaged
  `goga/assets/pipelines/development.yml` prompt asset) were touched only by the
  apply-stage commit `d76b44e` — no implementation task modified a manifest.
- [x] Lint the whole: `python -m ruff check goga tests` — all checks passed;
  `python -m ruff format --check goga tests` — 15 files flagged, all pre-existing on the
  base commit under the same ruff 0.16.8 (Markdown `.usages` embedded-Python drift plus
  onboarding/topics/commands test files); none on this feature's surface, and every file
  this feature added or touched is format-clean (757 formatted on branch vs 742 on base).

---

## Validation Commands

- `python -m pytest tests/hooks/catalog tests/pipeline/hooks tests/pipeline/test_run_pipeline_hooks.py tests/pipeline/test_describe_pipeline.py tests/pipeline/test_pipeline_card.py tests/pipeline/test_pipeline_cli.py -q`: Targeted run of every suite this plan touches (run in the project venv)
- `python -m pytest`: Run all tests (testpaths `tests/`; the full pre-feature suites are the no-tools regression proof)
- `python -m ruff check goga tests && python -m ruff format --check goga tests`: Lint check over the changed surface and the whole
- `goga lint`: Cell contract lint — 78 cells, 0 errors
- `python -c "import goga.pipeline.hooks as h; assert sorted(h.__all__) == ['CompositionStage', 'PipelineHooks', 'PipelineIdentity', 'RunCompleted', 'RunCreated', 'ToolContribution', 'WorkIdentity', 'WorkflowAmendment', 'WorkflowDecision', 'WorkflowOverlay', 'merge_workflow_overlay']"`: Verify that all facade entities are importable

---

## Completion Criteria

- [x] Every contract entity is implemented in the correct `location` (11 zone entities across `identity.py`, `contexts.py`, `overlay.py`, `amendments.py`, `events.py`; catalog records in `catalog.py`; consumer edits in `pipeline_card.py`, `describe_pipeline.py`, `run_pipeline.py`, `cli.py`)
- [x] Every contract entity is accessible from the facade (`goga.pipeline.hooks.__all__` — exactly the 11 names)
- [x] Properties and methods match the declared API (signatures, defaults, `kw_only`)
- [x] Descriptions are reflected in behavior (authored-wins merge, hard/soft error classes, mutually-blind tools, one registry per run, emissions around the launch, kind-derivation matrix)
- [x] Contract dependencies are met (platform facade imports, `WorkflowDocument` from `..workflow`, history facade imports in the operations)
- [x] Re-exports are accessible from the facade (none declared — vacuously true)
- [x] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [x] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [x] Integration tests exist where cross-entity scenarios require them (Tasks 7-11 scenario suites over the real platform + Task 12 composed verification)
- [x] No package boundary was expanded (no new cells beyond the contract-created zone; `goga/pipeline/workflow`, `goga/hooks` platform modules, and the compiler untouched)
- [x] `CODEMANIFEST` files were not modified (contract is read-only)
- [x] All validation commands pass (targeted suites 147 passed; `goga lint` 78/0; facade check OK; `ruff check` clean — the full-suite and format-check exceptions are the pre-existing base-commit environment items documented in Task 12)
- [x] Every Usages entry is mentioned in at least one task (`convention` — all tasks; `per-tool-delivery`, `declaring-actions`, `registering-hooks` — Tasks 6-7; `checkpoints` — Tasks 9-10; `topic-paths` — Tasks 9-10; `topic-statuses` — Task 10; `argparse`/`cli_entrypoint` — Task 11; `default_prompts`/`compile-flow`/`parse-dsl`/`run-flow` — Tasks 9-10)
