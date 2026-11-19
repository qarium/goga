# Plan: `add-tpl-to-workflow-hooks`

Result of compiling `.goga/history/2026/add-tpl-to-workflow-hooks/design.md` (verified by the
design-review stage — all 6 remarks fixed) into a ralphex-compatible execution plan. The three
CODEMANIFEST contracts and the three usage files are **already materialized in the working tree** —
this plan realigns the Python implementation with them. The contracts, the usage files, and every
"unchanged" module named by the design are read-only for the implementation agent.

## Purpose

Make the pipeline amendment layer profile-aware: every tool's `WorkflowAmendment` view carries the
operation's already-resolved active contributor profile as a read-only fact, and every string
surface (string leaf + string mapping key, any depth, typed model fields and verbatim extend bodies
alike) of a tool's committed contribution renders as a Jinja template with that profile's content
at the commit moment — inside the walk, before the presence-based empty-contribution check, before
the authored-wins merge. After implementation:

- `render_contribution(document, profile_data)` exists in the workflow cell (leaf, pure, no I/O),
  renders under the same fixed four-flag Jinja environment as `render_workflow`, and fails strict:
  template errors carry the error class, message, and document dot-path; rendered-key collisions
  inside one map name the map, both source keys, and the colliding result.
- `PipelineHooks.amend_workflow` gains the trailing `profile: ResolvedProfile | None = None`
  parameter; a render failure is disciplinarily a hook failure — the first failing tool stops the
  command pre-run, later tools' hooks never run, the tool's whole contribution is discarded.
- `run_pipeline` / `describe_pipeline` pass `resolved.profile if resolved is not None else None`
  into the delivery — signatures unchanged, wiring only; the run and card forms deliver the
  identical fact and produce the identical rendering.

Most important gaps between contract and code: `render_contribution` does not exist (module and
facade export missing); `WorkflowAmendment` has no `profile` field; `amend_workflow` takes no
`profile` parameter and commits the raw buffered document unrendered; the two delivery sites pass
four arguments today.

Implementation strategy: per-cell realignment in the design's fixed order — `workflow` (the leaf
routine) → `hooks` (the view fact, then the changed walk) → `pipeline` (the wiring + integration
tests). Every coding task follows the TDD workflow (contract tests → code → verification → logic
tests → debugging → re-verification → lint) and the Mandatory Rules below.

## Context

### Contract Surface

All signatures below are the **already-materialized contract state** (read-only). The
implementation must match them exactly.

#### Cell `goga/pipeline/workflow` (leaf — the workflow-file parser and contributor-profile zone)

**Entity: `render_contribution`** — NEW
- Type: `function` (Routine)
- Declared `location`: `render_contribution.py`
- Facade obligation: importable from `goga.pipeline.workflow`, listed in `__all__`
- Signature: `render_contribution(document: WorkflowDocument, profile_data: dict[str, Any]) -> rendered: WorkflowDocument`
- Semantic requirements from the manifest annotations (the behavioral contract):
  - Walk `document` type-driven at any depth, over the typed model fields and the verbatim
    extend-entry bodies alike: render every string leaf and every string mapping key individually;
    carry every non-string scalar unchanged. The walk is **field-set-complete** over the document
    model (a new model field flows through with no change here) and **no field is exempt** — the
    never-merging global fields (`profile`, `build`, `agent`, `env`) render like every other
    surface.
  - Render each surface with the fixed environment per `jinja2` and **exactly `profile_data`** as
    the context — no ambient variables (tool, pipeline, workflow name) exist in the context.
  - While rendering the keys of one map — detect a rendered-key collision: two distinct source
    keys rendering to the same result key raise one strict error naming the map (its dot-path),
    the source keys, and the colliding result.
  - On a template error in any surface — dead fields included — raise one strict error carrying
    the template cause: the error class, the message, and the document path — the dot-path built
    from the **source (pre-render) keys**, with list elements indexed and the two gates shapes
    disambiguated positionally (the workflow-level gates settings block path versus a stage
    check-step list path).
  - Return a NEW `WorkflowDocument` — every surface rendered, every non-string value carried
    unchanged, field presence unchanged (a rendered empty string is a value, not an absence).
  - Requirements: pure (no mutation of `document` or its maps; the result is a new document); no
    I/O (no files, no environment reads, no subprocess); a template-free document renders to an
    equal document; without an active profile the render runs against an empty context (template
    syntax still processes, missing keys render empty); rendering never changes field presence.
  - Constraints: do not parse/validate/restructure; do not merge/apply/interpret; do not resolve
    profiles or read the environment; do not build a second template environment, dialect, or
    ambient context.
- Imported dependencies: none (the cell has no Imports; only `dataclasses`, `typing.Any`, and
  `jinja2.Environment`).
- Annotation context: header `Usages` (`convention`, `jinja2`) + the entity annotations ("Use
  `jinja2` for the rendering engine contract … Apply `convention` for docstring style").

**Reference entities (unchanged, consumed as imports):** `WorkflowDocument` (12 fixed-order
fields — the walk's root), `WorkflowStage`, `WorkflowExtendStage` (open-ended `body: dict[str, Any]`
— the recursion must not enumerate fields of body), `ResolvedProfile` / `LoadedWorkflow` /
`render_workflow` (the environment-flag precedent), `ProfileSource`. `render_workflow` itself is
final — do not touch it; the new module repeats the same four-flag `Environment(...)` literal
(two identical literals are the existing precedent; the flags are the contract, not object
identity; do NOT import `render_workflow`'s private environment).

#### Cell `goga/pipeline/hooks` (the hooks zone of the pipeline domain)

**Entity: `WorkflowAmendment`** — CHANGED
- Type: `class` (Entity, `@dataclass(kw_only=True)`)
- Declared `location`: `amendments.py`
- Facade obligation: importable from `goga.pipeline.hooks` (facade unchanged — fifteen names)
- Signature: `WorkflowAmendment(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, work: WorkIdentity, profile: ResolvedProfile | None = None)`
- Change: one new read-only field after `work` — `profile: ResolvedProfile | None = None`; the
  docstring gains the `profile:` arg line (the operation's already-resolved active contributor
  profile — name, whole content, source — or None without activation / no workflow); runtime
  import `from ..workflow import ResolvedProfile` (matches the file's existing runtime import of
  `WorkflowDocument`). No behavior: the field is a delivered fact; `contribute` and the buffer are
  untouched.
- Semantic requirements: the `profile` fact is operation data passed in by the caller — no reads,
  no re-resolution at the checkpoint; read-only and identical for every tool and in every delivery
  form; reads absent (None) without activation, including the no-workflow silent-miss case.
- Imported dependencies: `ResolvedProfile` (new, from `goga/pipeline/workflow` via the existing
  Imports edge — additive).

**Entity: `PipelineHooks.amend_workflow`** — CHANGED
- Type: `class` method of `PipelineHooks()` (`events.py`)
- Declared `location`: `events.py`
- Facade obligation: `PipelineHooks` importable from `goga.pipeline.hooks` (facade unchanged)
- Signature: `amend_workflow(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, work: WorkIdentity, profile: ResolvedProfile | None = None) -> overlay: WorkflowOverlay`
  (the trailing parameter is optional — backward compatible).
- Semantic requirements (the rewritten seven-step algorithm; steps 1–3 are structurally unchanged,
  the view now also receives `profile=profile`):
  1. Resolve the address `domain="pipeline", action="amend_workflow"` against `declared_actions`.
  2. Walk the subscriptions per tool in enumeration order: build the tool's `WorkflowAmendment`
     view over the delivered facts — every tool reads the same original `workflow` and the **same
     `profile` fact (same object)** — wrap via `wrap_context`, project the call arguments via
     `build_hook_arguments`, call each hook. The existing in-`try` buffer guard (out-of-contract
     buffer type fails the hook that wrote it) stays as-is.
  3. A raising hook is a hard failure (unchanged).
  4. **NEW** — per tool, after every hook returned: buffer `None` → silent `continue`; otherwise
     `context = profile.data if profile is not None else {}`, then
     `rendered = render_contribution(document, context)`; a `ValueError` from the render is the
     same hard failure as a raising hook —
     `ValueError(f"contribution of tool {tool} failed on pipeline.amend_workflow: {reason}")`;
     the tool's whole contribution is discarded and the walk stops before the next tool is called.
  5. The empty-contribution check runs on the **rendered** document and stays presence-based and
     unchanged (the eight facts); empty → warning + continue.
  6. A non-empty rendered document commits as one `ToolContribution` — **the rendered document is
     the committed document**.
  7. `merge_workflow_overlay(workflow, contributions)` — unchanged.
- Requirements: commit granularity is the tool (render + commit only after every hook of the tool
  succeeds); the render runs inside the walk at each tool's commit — never as a pass after the
  walk; the profile fact never varies per tool; an address without subscriptions returns the
  passthrough overlay; a contribution without template syntax composes byte-identically with or
  without an active profile.
- Constraints: do not apply any contribution outside the single merge; do not skip a subscriber;
  no repository/filesystem reads at the checkpoint; do not resolve the profile here.
- Imports: `render_contribution` from `..workflow` at **runtime** (it is called); `ResolvedProfile`
  joins the existing `TYPE_CHECKING` block (annotation-only).
- Reference entities (unchanged, final): `merge_workflow_overlay` / `ToolContribution` /
  `WorkflowOverlay` (`overlay.py`), the `emit_*` members, the contexts.

#### Cell `goga/pipeline` (the pipeline domain)

**Entity: `run_pipeline`** — CHANGED (wiring only)
- Type: `function` (Routine); `location`: `run_pipeline.py`; facade: `goga.pipeline`
- Signature: **unchanged** — `run_pipeline(name, project_dir, user_dir, port, workflow=None, no_workflow=False, profile=None, skip=None, parallel=None, fail_on_error=False) -> exit_code: int`
- Change: algorithm step 12 only — the delivery now passes the operation's resolved profile:
  `hooks.amend_workflow(..., workflow=workflow_doc, work=work, profile=resolved.profile if resolved is not None else None)`.
  `resolved` is the `LoadedWorkflow | None` the routine already holds from its `resolve_workflow`
  step (step 8). The profile comes from the LOADED workflow, not the skip-merged `workflow_doc` —
  `apply_skip_stages` never touches `.profile`, so both sources agree. The disabled branch, the
  docstring Raises notes, and everything after the delivery are unchanged.

**Entity: `describe_pipeline`** — CHANGED (wiring only)
- Type: `function` (Routine); `location`: `describe_pipeline.py`; facade: `goga.pipeline`
- Signature: **unchanged** — `describe_pipeline(name, project_dir, user_dir, workflow, no_workflow, profile=None, skip=None) -> card: PipelineCard`
- Change: algorithm step 4 only — the same one expression at the delivery site. New requirement
  bullet (card/run parity): the card delivers the amendment with the resolved profile exactly as
  the run form does — the same fact on every tool's view and the same rendering of contributed
  strings; the card's merged composition equals what a run with the same flags executes.

### Re-exports

None. No `->Name: {}` block changes. The workflow facade gains one direct export of its own new
entity (`render_contribution`); the hooks facade (fifteen names, pinned by `ZONE_ALL` in
`tests/pipeline/hooks/conftest.py`) gains nothing — `render_contribution` is internal to the
amendment zone's use.

### Usages Context

- `convention` (`.goga/usages/conventions.md`): the mandatory ruleset for every touched module and
  test file — code style, dataclass discipline, docstring style, test layout and rules, lint and
  validation commands, and the organization of the REPL development cycle. Extracted in full into
  the **Mandatory Rules** section below and applied in every task.
- `jinja2` (`.goga/usages/cooks/jinja2.md`): the two rendering surfaces (whole-file before
  parsing; field-level of a committed contribution), the fixed environment flags, the context rule
  (exactly the single active profile; empty without activation; no ambient variables), the
  missing-key semantics, the strict failure vocabulary (file+line for authored files; document
  dot-path for contribution strings; the collision failure), and the anti-patterns (no second
  environment/dialect/ambient context). Applied in Task 1 (and referenced by Tasks 3–4 through
  `render_contribution`).

### Imported Usages

- `per-tool-delivery` from `goga/hooks` (`goga/hooks/.usages/per-tool-delivery.md`) — the walk's
  loop skeleton and the commit-after-success rule; `render_contribution` slots into the commit
  moment between the hook loop and the empty check. Applied in Task 3.
- `registering-hooks` from `goga/hooks` (`goga/hooks/.usages/registering-hooks.md`) — the hook
  signature receiving the view; the new `profile` attribute is read through the same wrapped
  context. Applied in Tasks 2–3.
- `declaring-actions` from `goga/hooks` (`goga/hooks/.usages/declaring-actions.md`) — unchanged
  role (the notification and bridged emissions); context only, no task action.
- `checkpoints` from `goga/pipeline/hooks` (`goga/pipeline/hooks/.usages/checkpoints.md`) — the
  delivery documentation the pipeline cell codes against: the `loaded.profile` fact bullet, the
  `profile=loaded.profile` delivery example, and the four render-semantics bullets (same fact in
  both forms, render at commit before the unchanged checks, hard render failure, template-free
  byte-identity). The code of Task 4 matches it exactly; the file itself is **final**.

### Local Usages

None. The design's `.usages/` Update section confirms: `goga/pipeline/hooks/.usages/checkpoints.md`
and `goga/pipeline/.usages/registering-hooks.md` are status **current** (updated at
materialization; verified against the design) — additions needed: none. No `.usages/` directory is
planned for `goga/pipeline/workflow` (the rendering practice is project-level; consumer docs live
with the hooks pair). This plan creates and modifies **no** usage files.

### External Dependencies

- `jinja2>=3.1` — the rendering engine (already in `pyproject.toml`; no new dependency).
- `pytest>=8.0` + `unittest.mock` / `monkeypatch` + the existing platform-boundary fixtures — the
  test framework; no new test dependency.
- `ruff>=0.15.0` — lint and format (already in the `test` extra).
- `goga` CLI — `goga lint` (DSL validation over all cells; must stay 93 cells / 0 errors).

## Mandatory Rules (extracted from `convention` — apply in every task, every stage, every commit)

The rules below are compiled for this change from the `convention` practice
(`.goga/usages/conventions.md` — style, data models, docstrings, logging, test layout, mocks,
validation commands), the Python contract rules (mandatory type hints and their allowed forms,
naming), and the repository's own policy (the ruff configuration, the `.githooks` commit
policy) — the CODEMANIFEST annotations attribute the REPL-cycle organization to `convention`;
R4 spells that attribution out concretely. They are **mandatory** — the convention's own
precedence applies: contract first, facade obligations second, these conventions next, language
idioms last. Violations are task failures, not style nits.

### R1. Coding style

- **Runtime**: Python 3.10+ only; all configuration through `pyproject.toml`; **all** code and
  tests execute inside the project virtualenv (`.venv` — create it if missing); never the system
  interpreter.
- **Imports**: relative imports for ALL intra-package references
  (`from ..workflow import ResolvedProfile, WorkflowDocument`, `from .render_contribution import
  render_contribution`); absolute imports only for stdlib and third-party (`dataclasses`,
  `typing`, `jinja2`). Exception — tests: inside `tests/`, cross-directory references use absolute
  imports rooted at the `tests` package (`from tests.pipeline.hooks.conftest import ...`,
  `from tests.hooks.conftest import install_tool_package`).
- **Data models**: stdlib `dataclasses` only (NOT pydantic); every model class
  `@dataclass(kw_only=True)`; `None` only for the explicit absence of a value. The changed
  `profile: ResolvedProfile | None = None` follows exactly this rule.
- **Type hints**: mandatory on every public surface; allowed forms `str`, `int`, `bool`,
  `list[T]`, `dict[str, T]`, `T | None`; forbidden: `*args`/`**kwargs`, bare `dict`, bare `list`.
- **Naming**: PascalCase classes; snake_case functions, methods, and properties.
- **Function-body formatting**: logical blocks inside function/method bodies are separated by one
  blank line — initialization vs conditionals/loops, data preparation vs processing, processing vs
  the return.
- **Docstrings**: Google style, mandatory for all public functions, methods, and classes. First
  line capitalized and ending with a period; `Args` when parameters exist, `Returns` when a value
  returns, `Raises` for exceptions beyond built-in behavior. Module docstrings in the cell's
  one-line form (e.g. "The ``render_contribution`` routine — field-level Jinja rendering of
  committed workflow contributions."). Keep comments laconic and professional — one point per
  comment.
- **Logging**: stdlib `logging` with module-level `logger = logging.getLogger(__name__)`;
  lowercase, structured, operationally worded messages. This change adds **no** log lines: the
  existing empty-contribution WARNING fires unchanged; renders and profile facts log nothing
  (facts are delivered, not logged).
- **Dependencies**: any third-party library must live in `pyproject.toml` with a minimum version.
  This change adds none.

### R2. Test writing

- **Framework and layout**: pytest; tests mirror the source structure directly —
  `goga/pipeline/workflow/render_contribution.py` → `tests/pipeline/workflow/test_render_contribution.py`.
  Every test directory carries `__init__.py`; local fixtures in `tests/<package>/conftest.py`,
  shared fixtures in `tests/conftest.py`. No new directories are needed — all four target files
  exist.
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`; grouping
  `class Test<Component>:`. Self-documenting names; minimal comments.
- **Order (TDD)**: contract tests FIRST in every coding task (facade importability, `__all__`
  membership, signature shape via `inspect.signature`, annotations via `get_type_hints`) — they
  fail before implementation and that failure is expected; logic tests AFTER the implementation
  (positive, negative, edge — empty inputs, boundary values such as `0` and `False`, invalid
  types, expected exceptions).
- **Assertions**: expected exceptions via `pytest.raises(ValueError, match=<regex>)` — regex
  prefix matching for the long Jinja messages (never exact equality on a message that continues
  beyond the pinned prefix).
- **Mocks**: pure logic is tested **without mocks** — `render_contribution` tests are mock-free;
  the hooks-zone tests run against the real platform boundary fixtures
  (`pin_package_environment` / `install_tool_package`); file I/O uses `tmp_path` exclusively;
  subprocesses are mocked at the call, external dependencies at the import point. Mock only at
  external boundaries — business-logic tests stay mock-free.
- **CLI/routine testing**: call the handler function directly via Python (`run_pipeline(...)`,
  `describe_pipeline(...)`) — never a subprocess.
- **Traceability**: every test names the contract entity and scenario it verifies; the mapping
  entity → location → tests is auditable per task.

### R3. Lint and format enforcement (all development stages and local commits)

- **Lint gate**: `ruff check goga/` and `ruff check tests/` (the project linter, configured in
  `pyproject.toml` — line length 120, target py310, the full rule selection with the tests
  per-file ignores). The gate runs at: STEP 7 (Lint) of every coding task, the completion of every
  task, and **before every local commit**. A commit with lint findings is forbidden — fix the
  findings or do not commit.
- **Format gate**: `ruff format` per the `[tool.ruff.format]` config (double quotes, space indent,
  LF line endings, magic trailing comma honored). Run it over **every Python file the task
  touched** and include the result in the same commit. Do NOT run a repository-wide
  `ruff format`: two pre-existing files are not format-clean and are out of scope —
  `goga/pipeline/hooks/.usages/checkpoints.md` (a usage file, final and read-only for this
  change) and `tests/commands/pipeline/test_pipeline_command.py` (untouched by this plan).
- **Test gate before commit**: the task's scoped test command and `pytest tests/ -x` green;
  `goga lint` green (93 cells, 0 errors — proves the CODEMANIFESTs stayed untouched).
- **Commits**: conventional, per-task commits; the repo's `.githooks` policy (no co-authorship
  trailers) applies — `make install-hooks` if the hooks path is not yet set.

### R4. REPL development cycle (continuous interactive evaluation → hot reloading → migration to source files)

Every coding task works as a REPL-driven loop, per the `convention` practice's REPL-cycle role:

1. **Evaluate interactively before coding.** Probe every behavior you do not know exactly in an
   active Python session inside the venv (`.venv/bin/python`), against the real dependencies:
   the four-flag `Environment` rendering of a candidate surface; `dataclasses.replace` on a
   subclassed model; the exact `type(exc).__name__` and `str(exc)` of a Jinja
   `TemplateSyntaxError`/`UndefinedError`; the composed error-message strings; dict iteration
   order under collision. A behavior whose live shape is unknown is not yet implementable.
2. **Keep the loop continuous.** After each edit of a module, re-import in a fresh interpreter
   (`python -c` probe or a new REPL) and re-run the focused probes — the changed modules are pure
   and import-time-cheap, so the evaluation loop is seconds, not minutes. In a long-lived session
   use `importlib.reload` for a just-edited module; when state goes stale, **restart the
   interpreter** — never work around stale imports.
3. **Migrate verified code to source files.** The REPL is scratch space only: every verified
   expression, message format, and edge-case result migrates into the module at its declared
   `location` (implementation) or into the task's test files (as assertions). Nothing verified in
   a session may live only there.
4. **Probes inform tests, never replace them.** Every task still ends with the pytest and lint
   commands of the Validation Commands section; a REPL observation that a test must capture goes
   into the test, not into memory.

## Facts

- The branch is `add-tpl-to-workflow-hooks`; the three CODEMANIFESTs and the three usage files
  (`.goga/usages/cooks/jinja2.md`, `goga/pipeline/hooks/.usages/checkpoints.md`,
  `goga/pipeline/.usages/registering-hooks.md`) are already materialized in the working tree
  (staged diff vs HEAD); `goga lint` — **93 cells, 0 errors**. They are the read-only source of
  truth.
- The design passed the design-review stage: 6 remarks fixed (Medium 1, Low 4, Test Gap 1),
  including the tuple-branch test and the bracket-repr key error path.
- Baseline state (verified): `pytest tests/pipeline/workflow tests/pipeline/hooks -q` → 818
  passed; `pytest tests/pipeline -q` → 2025 passed; `ruff check goga/` clean; venv Python
  3.12.16, ruff 0.17.5, pytest 9.2.0.
- `render_contribution` exists nowhere — `from goga.pipeline.workflow import render_contribution`
  fails today. It is the only missing entity.
- `WorkflowAmendment` (`goga/pipeline/hooks/amendments.py`) carries exactly four init fields
  (`pipeline`, `decision`, `workflow`, `work`) plus the private `_contribution` buffer
  (`init=False, repr=False`); pinned by `TestAmendmentContract::test_view_carries_exactly_the_declared_fields`
  (`tests/pipeline/hooks/test_amendments.py:83`).
- `PipelineHooks.amend_workflow` (`goga/pipeline/hooks/events.py:64`) takes exactly
  `(self, pipeline, decision, workflow, work)`; pinned by
  `TestCheckpointContract::test_surface_carries_the_declared_method_signatures`
  (`tests/pipeline/hooks/test_events.py:504`).
- The delivery sites pass four keyword arguments today: `goga/pipeline/run_pipeline.py:446` and
  `goga/pipeline/describe_pipeline.py:161`.
- The walk in `events.py` already has the exact slot the render fills: buffer `None` →
  `continue` (line 169); the presence-based empty check (lines 174–183); the commit
  (line 190); `merge_workflow_overlay` (line 192). Steps 1–3 (registry, declared-actions lookup,
  per-tool grouping, view construction, in-try buffer guard) are unchanged.
- `render_workflow.py` is the module-layout mirror: one-line module docstring,
  `from __future__ import annotations`, the module-fixed four-flag `_RENDER_ENVIRONMENT`
  (`trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, autoescape=False`),
  a Google-style docstring, one `try/except` wrap. Its `UndefinedError` propagates **unwrapped**
  (whole-file precedent) — the contribution render wraps **every** failure (the design fixes this
  difference deliberately).
- The workflow facade `__all__` is alphabetized; `render_contribution` sorts between
  `parse_workflow` and `render_workflow`. The hooks facade is the fifteen-name `ZONE_ALL` —
  unchanged.
- The hooks-zone test scaffolding exists and is reused: `tests/pipeline/hooks/conftest.py`
  (`pin_package_environment` / `install_tool_package` re-exports, `field_defaults`, `ZONE_ALL`,
  the four fact fixtures); `tests/pipeline/workflow/conftest.py` (`project_root`, `home_bundle`,
  `render_env`); the wiring suites `tests/pipeline/test_run_pipeline_hooks.py` and
  `tests/pipeline/test_describe_pipeline.py` carry the AFM_DIR-pinning environment scaffolding.
- `ResolvedProfile` and `ProfileSource` are already exported from `goga.pipeline.workflow` —
  the hooks-cell import edge needs no facade change.
- ruff format debt: exactly two files (see R3) — both outside this change; no action.
- No new dependencies, no new cells, no `.usages/` changes.

### Entity Interaction and Data Flow (from the design — verified, transfer verbatim)

```
                        in-container operation data
  ┌────────────────────────────────────────────────────────────────┐
  │ run_pipeline (run form)      describe_pipeline (card form)     │
  │   resolved = resolve_workflow(...)   ← LoadedWorkflow           │
  │   resolved.profile : ResolvedProfile | None                    │
  │        │  profile=resolved.profile (None when resolved is None)│
  │        ▼                                                       │
  │  PipelineHooks.amend_workflow(pipeline, decision, workflow,    │
  │                                work, profile)                  │
  │        │ per tool (enumeration order)                          │
  │        ├─ WorkflowAmendment(..., profile)  ← same object/tool  │
  │        │    └─ hook(context)  → contribute(raw document)       │
  │        ├─ render_contribution(raw, profile.data if       NEW   │
  │        │          profile is not None else {})                 │
  │        │    └─ rendered : WorkflowDocument (strict errors)     │
  │        ├─ empty check on RENDERED document (presence-based)    │
  │        └─ ToolContribution(tool, rendered)                     │
  │        ▼                                                       │
  │  merge_workflow_overlay(workflow, contributions)  — UNCHANGED  │
  │        └─ WorkflowOverlay → compile_flow → afm launch / card   │
  └────────────────────────────────────────────────────────────────┘
  workflow cell (leaf): render_contribution imports nothing from the
  other two cells; jinja2 Environment fixed once, shared flag set with
  render_workflow.
```

**Data flows**:

1. **Run form (pre-launch)** — `run_pipeline` steps 1–11 unchanged (config load+amend,
   discovery, `AFM_DIR`, `resolve_workflow` under the activation context, feedback line,
   `apply_skip_stages`, fact resolution). Step 12 now also passes the operation's resolved
   profile; the overlay's rendered tool strings then flow into `compile_flow` (step 13), the
   effective-global-agent read (step 14 — reads only `agent`, a rendered string), the env
   wrappers (steps 15 — rendered env maps/keys), the afm configuration write (step 17 —
   rendered collaboration strings), and the launch layer (step 20 — no workflow strings).
2. **Card form** — `describe_pipeline` steps 1–3 unchanged; step 4 passes the same resolved
   value; the card then compiles the overlay through the real machine into a temp dir (steps
   5–8). No events fire; identical fact and identical rendering as the run form.
3. **Render-at-commit (inside the walk)** — per tool: hooks run against the view carrying the
   profile fact → on the tool's last hook returning, the buffered RAW document renders with
   `profile.data` (or `{}`) → the presence-based empty check reads the RENDERED document →
   non-empty commits as the rendered document. A render failure raises the hard amendment
   error; the walk stops before the next tool's hooks.

**Entity dependencies**: `render_contribution` depends on nothing but the fixed Jinja
environment (module-level, same construction as `render_workflow`) and the
`dataclasses`/`typing` machinery — the workflow cell stays a leaf. `PipelineHooks.amend_workflow`
imports `render_contribution` (and `ResolvedProfile` for the annotation) from `..workflow` — the
existing edge, used additively. `merge_workflow_overlay` receives already-rendered documents; it
is untouched. Initialization order is unchanged: `PipelineHooks()` stays cheap; the registry
builds lazily at the first checkpoint.

## Gap Analysis

- **Missing contract entities**: `render_contribution` (Routine, `render_contribution.py`) — no
  module, no facade export, no tests.
- **Missing facade exposure**: `"render_contribution"` absent from
  `goga/pipeline/workflow/__init__.py` (`__all__` and the import block).
- **API mismatches**:
  - `WorkflowAmendment` lacks `profile: ResolvedProfile | None = None` (and its docstring line);
  - `PipelineHooks.amend_workflow` lacks the trailing `profile` parameter (and the runtime import
    of `render_contribution` / the `TYPE_CHECKING` import of `ResolvedProfile` / the docstring
    update);
  - the delivery sites lack the `profile=` argument.
- **Behavioral mismatches**: the walk commits the raw buffered document — no field-level render,
  no rendered-key collision detection, no template-cause error surfacing, no hard-stop on a
  render failure; the empty-contribution check reads the raw document; views carry no profile
  fact; `run_pipeline`/`describe_pipeline` do not thread the loaded profile into the delivery.
- **Existing code reused as-is**: steps 1–3 of the walk (registry, grouping, view construction,
  `wrap_context`, `build_hook_arguments`, in-try buffer guard), the empty-check code, the merge,
  `render_workflow` (flag-set precedent), the Jinja environment construction pattern, all conftest
  fixtures and wiring scaffolding.
- **Test coverage gaps**: no `tests/pipeline/workflow/test_render_contribution.py`; the
  hooks-zone suites lack the seven profile/render delivery scenarios and the two contract-suite
  extensions (`profile` field/parameter lists); the wiring suites lack the three profile-delivery
  scenarios (run-form delivery, no-workflow None, card/run parity).
- **Usage files**: current and final — no gaps, no tasks.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next,
> in the design's fixed order `workflow → hooks → pipeline` (each cell consumes only what the
> earlier ones provide; the dependency direction never reverses). Within each coding task,
> contract tests are written first (TDD workflow).

> **Global implementation rules (apply to every task)**:
> - **`CODEMANIFEST` files are read-only.** If implementation does not match the contract, fix the
>   implementation — never fix the contract. `goga lint` must stay 93 cells / 0 errors.
> - **The three usage files are final** (`.goga/usages/cooks/jinja2.md`,
>   `goga/pipeline/hooks/.usages/checkpoints.md`, `goga/pipeline/.usages/registering-hooks.md`) —
>   do not touch them; the code is made to match them.
> - **Do not touch** `merge_workflow_overlay` / `overlay.py`, `render_workflow.py`, the `emit_*`
>   members, `goga/pipeline/cli.py`, the action catalog (`goga/hooks/catalog/`), or
>   `wrap_context`/`build_hook_arguments` — final as they stand.
> - **Message formats are contract surface** — copy them verbatim from this plan (which carries
>   them verbatim from the design): the render-failure tail keeps the established
>   `… failed on pipeline.amend_workflow: <reason>` shape so the CLI's generic strict pre-run
>   branch and the existing regex-based tests keep matching.
> - The **Mandatory Rules** (R1 style, R2 tests, R3 lint/format + commit gates, R4 REPL cycle)
>   apply to every task and every commit — R3's gates are part of every task's completion.
> - The Python signature of `amend_workflow` gains `profile: ResolvedProfile | None = None` as the
>   LAST parameter (after `work`); all call sites keep using keywords.

### Task 1: `render_contribution` — the field-level render routine (goga/pipeline/workflow)

Create the new Routine `render_contribution` in `goga/pipeline/workflow/render_contribution.py`
and export it from the cell facade. One committed `WorkflowDocument` in, one rendered document
out, under the fixed workflow rendering semantics — the field-level rendering step the pipeline
amendment applies at a tool's commit moment. The routine is pure, does no I/O, and fails strict
with the document dot-path vocabulary.

**Contract entity**: `render_contribution` (location `render_contribution.py`), signature
`render_contribution(document: WorkflowDocument, profile_data: dict[str, Any]) -> rendered: WorkflowDocument`.
Facade: importable from `goga.pipeline.workflow`, listed in `__all__`.

**Usages relevant to this task:**
- `jinja2`: the fixed environment flags (the module repeats the same four-flag `Environment(...)`
  literal `render_workflow` uses — one environment contract; do NOT import `render_workflow`'s
  private object), the context rule (exactly `profile_data`, no ambient variables), missing-key
  semantics (standard `Undefined` — falsy in guards, empty interpolation), the strict failure
  vocabulary (document dot-path for contribution strings; the collision failure), the
  anti-patterns (no second environment/dialect/ambient context; document path replaces file line
  for contribution strings).
- `convention`: style (R1), test rules (R2), lint/format gates (R3), REPL cycle (R4).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Module layout and the walker (from the design — verbatim; `render_workflow.py` is the structural
mirror):

```python
"""The ``render_contribution`` routine — field-level Jinja rendering of committed workflow contributions."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Any

from jinja2 import Environment

_RENDER_ENVIRONMENT = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    autoescape=False,
)
```

(no imports beyond `dataclasses`, `typing.Any`, and `jinja2.Environment`)

```
render_contribution(document, profile_data):
1. result = _walk(document, profile_data, path="")
2. return result                                  # a new WorkflowDocument

_walk(value, ctx, path):
   IF isinstance(value, str):
       RETURN _render_surface(value, ctx, path)
   IF dataclasses.is_dataclass(value) and not isinstance(value, type):
       fields = dataclasses.fields(value)          # declaration order
       rendered = {f.name: _walk(getattr(value, f.name), ctx,
                                 _child(path, f.name))
                   for f in fields}
       RETURN dataclasses.replace(value, **rendered)
   IF isinstance(value, dict):
       RETURN _walk_map(value, ctx, path)
   IF isinstance(value, (list, tuple)):
       RETURN type(value)(_walk(item, ctx, f"{path}[{i}]")
                          for i, item in enumerate(value))
   RETURN value                                    # None/bool/int/float/enum/…

_walk_map(mapping, ctx, path):
   out = {}                                        # insertion order preserved
   owner: dict[str, str] = {}                      # result key -> first source
   for key, item in mapping.items():               # source order
       IF isinstance(key, str):
           key_path = f"{path}[{key!r}]" if path else key   # bracket-repr of
           result_key = _render_surface(key, ctx, key_path)  # the SOURCE key
           IF result_key in owner:
               RAISE ValueError(
                   f"rendered key collision in {path}: keys "
                   f"{owner[result_key]!r} and {key!r} both render "
                   f"to {result_key!r}")
           owner[result_key] = key
           child = _child(path, key)               # SOURCE key in the path
       ELSE:
           result_key = key                        # carried, never rendered,
           child = f"{path}[{key!r}]"              # never collision-checked
       out[result_key] = _walk(item, ctx, child)
   RETURN out

_render_surface(text, ctx, path):
   TRY: RETURN _RENDER_ENVIRONMENT.from_string(text).render(**ctx)
   EXCEPT Exception as exc:                        # TemplateSyntaxError,
       RAISE ValueError(                           # UndefinedError, any render
           f"template error at {path}: "           # failure of THIS surface
           f"{type(exc).__name__}: {exc}") from None

_child(path, key):  RETURN key if path == "" else f"{path}.{key}"
```

Document dot-path grammar (the failure vocabulary — implement and test exactly):

- Segments join with `.`; the root is the `WorkflowDocument` field name (`prompt`, `stages`,
  `extend`, `memory`, `profile`, `build`, `assistants`, `delegation`, `repeat`, `gates`, `agent`,
  `env`).
- String mapping keys join with `.` using the SOURCE (pre-render) key — `stages.build.prompt`,
  `assistants.reviewer.agent`, `extend.scans.body.title`, `stages.build.env.API_KEY`.
- List elements append `[i]` — `stages.build.skills[0]`, `extend.scans.body.roles[2]`; nested
  containers compose (`…roles[1][0]`).
- The two gates shapes disambiguate positionally: the workflow-level settings block is the dot
  path under `gates` (`gates.patience`), while a stage check-step list is
  `stages.<name>.gates[i].<field>` — e.g. `stages.review.gates[0].script`.
- Non-string mapping keys use the bracket form `[<repr>]`.
- A template error inside a string mapping KEY reports the bracket-repr form of its SOURCE key —
  `template error at stages['buil{{ "d" }}']: …` — so the failing key is named; the collision
  error of the same map keeps the plain map dot-path (`rendered key collision in stages: …`).

Errors: template error on any surface (values, keys, dead global fields, extend bodies) →
`ValueError: template error at <dot-path>: <ErrorClass>: <message>`; rendered-key collision →
`ValueError: rendered key collision in <map dot-path>: keys <a!r> and <b!r> both render to <r!r>`.

REPL-cycle checkpoints for this task (R4): before pinning code and test expectations, probe live —
(a) `Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
autoescape=False).from_string("Model: {{ model")` → capture the exact `TemplateSyntaxError`
message (it continues `…, expected 'end of print statement'.` — the tests match a regex PREFIX);
(b) `dataclasses.replace` on a `WorkflowStage` subclass → the type survives; (c) the collision
message with `!r` of both source keys; (d) a tuple rebuilt via `type(value)(…)` stays a tuple.
Migrate every verified string into the implementation/messages and the assertions.

- [x] **Contract tests**: create `tests/pipeline/workflow/test_render_contribution.py` —
      `TestRenderContributionContract` (module docstring in the zone's established form):
      facade identity + `__all__` membership
      (`import goga.pipeline.workflow as facade; facade.render_contribution is render_contribution`;
      `"render_contribution" in facade.__all__`); signature via `inspect.signature` — parameters
      exactly `["document", "profile_data"]`, no defaults; annotations via `get_type_hints` —
      `document: WorkflowDocument`, `profile_data: dict[str, Any]`, `return: WorkflowDocument`
      (expected to fail at this stage — the module does not exist)
- [x] **Code**: create `goga/pipeline/workflow/render_contribution.py` per the module layout and
      the walker above — public `render_contribution` + private `_walk`, `_walk_map`,
      `_render_surface`, `_child`; Google-style docstring (Args/Returns/Raises naming both error
      shapes); blank-line block separation per R1
- [x] **Code**: export from the facade — in `goga/pipeline/workflow/__init__.py` add
      `from .render_contribution import render_contribution` (alphabetical position after
      `from .profile_source import ProfileSource`, before `from .render_workflow import
      render_workflow`) and `"render_contribution"` in `__all__` between `"parse_workflow"` and
      `"render_workflow"`
- [x] **Interface verification**: `pytest tests/pipeline/workflow/test_render_contribution.py -x`
      — the contract class passes
- [x] **Logic tests** (mock-free, per R2) — add the 13 scenarios from the design:
      - `test_template_free_document_renders_to_an_equal_document` — the depth-covering document
        (`prompt="plain"`, a stage with prompt/skills/env, an extend stage with body
        title/roles, `memory`, `agent="codex"`, `env={"A": "1"}`) under
        `profile_data={"model": "sonnet"}`; assert `rendered == document`,
        `list(rendered.stages) == ["build"]`, `document.prompt == "plain"` (input unmutated)
      - `test_renders_values_and_keys_at_any_depth` — with
        `{"suffix": "ci", "model": "sonnet"}`: stage key `build-{{ suffix }}`, stage prompt,
        `notes` key `run-{{ suffix }}`, gate step name `check-{{ suffix }}` and script, extend
        body title/nested deep, assistants key `rev-{{ suffix }}` + entry prompt,
        `build.env` key `K_{{ suffix }}` and value, `agent="agent-{{ suffix }}"`; assert every
        rendered value/key (`stages` keys `["build-ci"]`, `build.env == {"K_ci": "sonnet"}`, …)
      - `test_empty_context_renders_missing_keys_empty` (EC-1) —
        `WorkflowDocument(prompt="a{{ missing }}b")` with `{}` → `rendered.prompt == "ab"`
      - `test_non_string_scalars_carried_unchanged` (EC-4) — `loop=3`, `skip=True`,
        `manual=False`, `memory=None`, `delegation(depth=2, max_tasks=50)`,
        `repeat(max_cycles=0, keep_runs=None)`, `gates(patience=1)` under `{"x": "y"}`; assert
        identity of every non-string field (`repeat.max_cycles == 0` — a zero is a value,
        `keep_runs is None`)
      - `test_syntax_error_raises_with_class_message_and_dot_path` —
        `WorkflowStage(prompt="Model: {{ model")`; assert `pytest.raises(ValueError,
        match=r"template error at stages\.build\.prompt: TemplateSyntaxError: unexpected end of
        template")` — regex prefix, escaped dots (the full Jinja message continues beyond the
        prefix)
      - `test_nested_undefined_access_raises_with_dot_path` —
        `WorkflowStage(prompt="{{ worker.model }}")` with `{}`; assert match
        `r"template error at stages.build.prompt: UndefinedError"`
      - `test_error_in_a_dead_global_field_is_strict` —
        `WorkflowDocument(profile="{{ broken", stages={"b": WorkflowStage(prompt="ok")})`;
        assert match `r"template error at profile:"`; the valid stage does not rescue
      - `test_rendered_key_collision_names_map_sources_and_result` —
        `stages={"build": …, 'buil{{ "d" }}': …}` with `{}`; assert match
        `r"rendered key collision in stages: keys 'build' and 'buil\{\{ \"d\" \}\}' both render to 'build'"`
      - `test_error_path_indexes_lists_and_disambiguates_gates` —
        `stages={"review": WorkflowStage(gates=[WorkflowGateStep(name="check", script="{{ oops")])}`
        → path `stages.review.gates[0].script`; an extend body `roles: ["fine", "{{ oops"]` →
        path `extend.<name>.body.roles[1]`
      - `test_rendered_empty_string_stays_present` (EC-3) —
        `WorkflowDocument(prompt="{{ gone }}")` with `{}` → `rendered.prompt == ""` and
        `is not None`
      - `test_purity_the_input_tree_is_never_mutated` — the depth-covering document, snapshot
        `copy.deepcopy(document)` before the call; assert `document == snapshot` after,
        `rendered.stages is not document.stages` (and nested maps equal but not identical)
      - `test_walk_reconstructs_dataclasses_with_type_preserved` (EC-7) — `type(rendered) is
        WorkflowDocument`, every nested model keeps its type (`WorkflowStage`,
        `WorkflowGateStep`, `WorkflowExtendStage`, `WorkflowAssistant`, `WorkflowBuild`)
      - `test_tuple_containers_recurse_and_rebuild_as_tuples` —
        `extend={"scan": WorkflowExtendStage(before=("build",), body={"roles": ("a{{ x }}",
        ("deep-{{ x }}",))})}` with `{"x": "ci"}`; assert
        `before == ("build",)` and `isinstance(..., tuple)`,
        `body["roles"] == ("aci", ("deep-ci",))`
- [x] **Debugging**: `pytest tests/pipeline/workflow -x` — fix implementation code until all tests
      pass (do NOT fix test code to make a broken implementation pass)
- [x] **Contract re-verification**: facade import works
      (`python -c "from goga.pipeline.workflow import render_contribution"`); signature matches
      the manifest exactly; purity/no-I/O constraints hold (no file/env/subprocess reads in the
      module); `goga lint` still 0 errors
- [x] **Lint**: `ruff check goga/ tests/pipeline/workflow/` — fix findings; `ruff format` the
      touched files (`render_contribution.py`, `__init__.py`,
      `tests/pipeline/workflow/test_render_contribution.py`)

### Task 2: `WorkflowAmendment.profile` — the read-only profile fact (goga/pipeline/hooks)

Add the read-only `profile` fact to the amendment view: one dataclass field, one import, one
docstring line — no behavior. This is the per-tool read-and-contribute view's extension with the
operation's already-resolved active contributor profile; the fact is identical for every tool and
in every delivery form, and reads absent (None) without activation (including the no-workflow
silent-miss case).

**Contract entity**: `WorkflowAmendment` (location `amendments.py`), signature
`WorkflowAmendment(pipeline, decision, workflow, work, profile: ResolvedProfile | None = None)`.
Facade: the fifteen-name `goga.pipeline.hooks` facade is unchanged (`ZONE_ALL` stays).

**Usages relevant to this task:**
- `convention`: dataclass discipline (`kw_only=True`, `None` only for explicit absence — R1),
  relative imports, docstring style; test rules R2 (extend the existing contract suite); gates R3;
  REPL cycle R4 (probe the field order/default live before pinning).
- `registering-hooks` (imported, from `goga/hooks`): the hook signature receives this view — the
  new `profile` attribute will be read through the same wrapped context (context for the
  construction tests; no file changes).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Change (from the design — verbatim):

```python
from ..workflow import ResolvedProfile, WorkflowDocument

    profile: ResolvedProfile | None = None
```

The field lands after `work`; the runtime import of `ResolvedProfile` matches the file's existing
runtime import of `WorkflowDocument`; the docstring gains the `profile:` arg line (the operation's
already-resolved active contributor profile — the profile that rendered the authored
workflow-file: its name, its whole content, and its source — or None when no profile is active).
`contribute` and the buffer are untouched.

- [ ] **Contract tests**: extend `tests/pipeline/hooks/test_amendments.py`
      `TestAmendmentContract::test_view_carries_exactly_the_declared_fields` — the
      `field_defaults(WorkflowAmendment)` assertion gains `("profile", None)` after
      `("work", MISSING)` AND the `dataclasses.fields` order assertion gains `"profile"` after
      `"work"`; update the test docstring to name the one field with a default; extend the module
      docstring's entity summary with `profile` (expected to fail at this stage)
- [ ] **Code**: add the `profile` field, the runtime import, and the docstring arg line in
      `goga/pipeline/hooks/amendments.py` per the change above
- [ ] **Interface verification**: `pytest tests/pipeline/hooks/test_amendments.py -x` — all pass
- [ ] **Logic tests**: extend the suite with a construction test — default construction leaves
      `profile is None`; explicit construction with
      `ResolvedProfile(name="mixa", data={"model": "sonnet"}, source=ProfileSource.PROJECT)`
      round-trips the fact verbatim; `contribute` still buffers unchanged beside the fact
- [ ] **Debugging**: `pytest tests/pipeline/hooks -x` — fix implementation code until all tests
      pass
- [ ] **Contract re-verification**: the view carries exactly the five declared fields in order;
      the facade is unchanged (`ZONE_ALL`); `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/hooks/` — fix findings; `ruff format` the touched
      files

### Task 3: `PipelineHooks.amend_workflow` — render at commit, inside the walk (goga/pipeline/hooks)

Rewrite the amendment walk to be profile-aware: the signature gains the trailing `profile`
parameter, the same `profile` object reaches every tool's view, and each tool's buffered document
renders field-level at its commit moment — a render failure is the same hard failure as a raising
hook; the empty-contribution check then reads the rendered document; the rendered document is the
committed document. The merge and everything around it is unchanged.

**Contract entity**: `PipelineHooks.amend_workflow` (location `events.py`), signature
`amend_workflow(pipeline, decision, workflow, work, profile: ResolvedProfile | None = None) -> overlay: WorkflowOverlay`.
Facade: unchanged.

**Usages relevant to this task:**
- `per-tool-delivery` (imported, from `goga/hooks`): the walk's loop skeleton and the
  commit-after-success rule — `render_contribution` slots into the commit moment between the hook
  loop and the empty check; apply its loop primitives as written.
- `registering-hooks` (imported, from `goga/hooks`): the failure handling behind the checkpoint —
  the hard-channel message format the render failure reuses.
- `declaring-actions` (imported, from `goga/hooks`): unchanged role — the notification and
  bridged emissions this task must NOT disturb (`emit_*` members and the action catalog stay
  untouched; only the hard `amend_workflow` action changes).
- `convention`: style R1, tests R2, gates R3, REPL cycle R4 (probe the composed failure message
  and the `profile.data`/`{}` context selection live).
- `jinja2` (transitively, through `render_contribution`): the render semantics the walk now
  invokes — no direct Jinja use in `events.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm delta (from the design — verbatim; only the marked steps change):

```
1–3. unchanged: registry build, declared-actions lookup, per-tool grouping, view
     construction — the view now receives profile=profile (NEW: same object into
     every tool's view), wrap_context, per-hook call with the existing in-try
     buffer guard (out-of-contract buffer types still fail the hook that wrote
     them)
4.   per tool, after every hook returned:
       IF amendment._contribution is None: continue        # never contributed
       context = profile.data if profile is not None else {}     # NEW
       TRY:   rendered = render_contribution(document, context)  # NEW
       EXCEPT ValueError as reason:                              # NEW
           RAISE ValueError(f"contribution of tool {tool} failed "
                            f"on pipeline.amend_workflow: {reason}")
           # hard stop: the walk ends here — no later tool's hooks run,
           # the tool's whole contribution is discarded
5.   presence-based empty check — UNCHANGED code, now reading `rendered`
     (the eight facts); empty → warning + continue
6.   contributions.append(ToolContribution(tool=tool, document=rendered))
7.   merge_workflow_overlay(workflow, contributions) — unchanged
```

Imports: `render_contribution` from `..workflow` at runtime (it is called), `ResolvedProfile`
joins the `TYPE_CHECKING` block. The docstring's Algorithm/Args/Raises sections update to the
contract text (the render-failure note names the tool and the action and carries the template
cause — the same `pipeline.amend_workflow: <reason>` tail as the existing hook-failure format).

Verified trace checkpoints (from the design): `profile.data` is `dict[str, Any]` — exactly
`render_contribution`'s context type; `{}` preserves the empty-context parity; rendering preserves
presence, so the eight-fact check's meaning is untouched (a rendered `""` is a value → the document
counts as non-empty); the merge consumes only rendered strings from here on (contribution
`profile`/`build`/`agent`/`env` are base-only globals the merge never reads — the "dead fields
included" strictness lands pre-merge).

- [ ] **Contract tests**: extend `tests/pipeline/hooks/test_events.py`
      `TestCheckpointContract::test_surface_carries_the_declared_method_signatures` — the
      `amend_workflow` parameter list gains `"profile"` after `"work"`
      (`["self", "pipeline", "decision", "workflow", "work", "profile"]`) (expected to fail at
      this stage)
- [ ] **Code**: add the `profile: ResolvedProfile | None = None` parameter (last, after `work`)
      to `amend_workflow`; add the `TYPE_CHECKING` import of `ResolvedProfile` and the runtime
      import of `render_contribution` from `..workflow`; pass `profile=profile` into every tool's
      `WorkflowAmendment` view construction
- [ ] **Code**: implement steps 4–6 of the algorithm delta at the existing walk slot
      (`events.py:169–190`): buffer `None` → `continue`; context selection
      (`profile.data if profile is not None else {}`); the try/render/except wrap raising
      `ValueError(f"contribution of tool {tool} failed on pipeline.amend_workflow: {reason}")`;
      the empty check reading `rendered`; the commit carrying `document=rendered`
- [ ] **Code**: update the routine docstring (Algorithm steps 4–6, the `profile` arg line, the
      Raises note covering the render-failure channel)
- [ ] **Interface verification**: `pytest tests/pipeline/hooks/test_events.py -x` — all pass
- [ ] **Logic tests** (extend `TestAmendWorkflowDelivery`; real platform fixtures, no mocks beyond
      the existing boundary) — the seven scenarios from the design:
      - `test_view_carries_the_same_profile_fact_for_every_tool` — two
        `install_tool_package` tools recording `id(context.profile)` and `context.profile.name`;
        `profile = ResolvedProfile(name="mixa", data={"model": "sonnet"},
        source=ProfileSource.PROJECT)`; authored base `WorkflowDocument(prompt="authored")`;
        assert both ids equal `id(profile)`, both names `"mixa"`, `overlay.provenance == [both
        tools]`
      - `test_profile_defaults_to_none_and_delivery_is_unchanged` — one contributing tool
        capturing `context.profile`; call WITHOUT `profile`; assert captured `is None` and the
        overlay equals the pre-change composition (prompt concat, provenance)
      - `test_contribution_renders_at_commit_with_profile_content` — tool contributes
        `WorkflowDocument(stages={"build": WorkflowStage(prompt="Model: {{ model }}")})` with
        `data={"model": "sonnet"}`; assert
        `overlay.workflow.stages["build"].prompt == "Model: sonnet"` and provenance includes the
        tool
      - `test_render_failure_is_a_hard_stop_and_later_tools_never_run` — tool A contributes
        `WorkflowDocument(prompt="{{ oops")` (syntax error); tool B appends to a `witnesses` list;
        `profile=None` (empty context does not rescue a syntax error); assert
        `pytest.raises(ValueError, match=r"pipeline\.amend_workflow: template error at prompt:
        TemplateSyntaxError")`, the message names tool A (`contribution of tool demo failed on`),
        and `witnesses == []`
      - `test_empty_check_runs_on_the_rendered_document` — tool contributes
        `WorkflowDocument(profile="{{ 'x' }}")` (the only field that never counts as content);
        assert one warning (`tool contributed an empty document; discarded`), empty provenance,
        no error
      - `test_rendered_empty_contribution_still_commits_by_presence` — tool contributes
        `WorkflowDocument(prompt="{{ missing }}")`; `profile=None`; authored base
        `prompt="authored"`; assert provenance includes the tool while
        `overlay.workflow.prompt == "authored"` (the merge drops empty texts)
      - `test_template_free_composition_is_identical_with_and_without_profile` — one plain-string
        contribution delivered twice (`profile=None` and `profile=ResolvedProfile(...,
        data={"model": "sonnet"})`); assert the two `overlay.workflow` documents are `==`
- [ ] **Debugging**: `pytest tests/pipeline/hooks -x` — fix implementation code until all tests
      pass
- [ ] **Contract re-verification**: facade unchanged (`ZONE_ALL`); the hard/soft discipline holds
      (only the amendment action is hard; the `emit_*` members untouched);
      `merge_workflow_overlay` untouched; `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/hooks/` — fix findings; `ruff format` the touched
      files

### Task 4: Profile wiring and card/run parity — `run_pipeline` / `describe_pipeline` (goga/pipeline)

Thread the operation's resolved profile into the two amendment deliveries and prove the run/card
parity end to end. Signatures unchanged — one expression per delivery site; the wiring tests are
the cross-entity integration scenarios of this change (run form → hooks walk → render → merge;
card form with the same fact and the same rendering).

**Contract entities**: `run_pipeline` (location `run_pipeline.py`, step 12) and `describe_pipeline`
(location `describe_pipeline.py`, step 4) — wiring only; facades unchanged.

**Usages relevant to this task:**
- `checkpoints` (imported, from `goga/pipeline/hooks`): the delivery documentation the pipeline
  cell codes against — `profile=loaded.profile` in the delivery example and the four
  render-semantics bullets; match it exactly (the file is final).
- `convention`: style R1 (docstrings untouched — Raises notes unchanged per the design), tests R2
  (call the handlers directly; reuse the existing scaffolding; `tmp_path`-pinned project trees),
  gates R3, REPL cycle R4 (probe the `resolved.profile if resolved is not None else None`
  selection against both branches live before writing the wiring).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Wiring (from the design — verbatim; one expression at each delivery site):

```python
overlay = hooks.amend_workflow(
    pipeline=identity, decision=decision, workflow=workflow_doc, work=work,
    profile=resolved.profile if resolved is not None else None,   # NEW
)
```

(`resolved` is the `LoadedWorkflow | None` both routines already hold from their
`resolve_workflow` step.) The disabled branches, the docstrings, and everything after the delivery
are unchanged. Error boundary (verified by the design's code-stack trace): a render failure
surfaces as `ValueError` from the walk → the CLI's generic strict pre-run branch prints
`Error: pipeline '<name>' could not be prepared: contribution of tool <tool> failed on
pipeline.amend_workflow: template error at <path>: <Class>: <message>` and returns 1 before any
compile/launch/event — the CLI module itself is untouched.

- [ ] **Contract tests**: no contract-suite change in
      `tests/pipeline/test_pipeline_contract.py`,
      `tests/pipeline/test_run_pipeline_hooks.py::TestRunPipelineHooksWiringContract`, or
      `tests/pipeline/test_describe_pipeline.py::TestDescribePipelineContract` — the two public
      signatures are UNCHANGED, and no existing test pins the `amend_workflow` call shape
      (verified: the wiring subscriptions run through the real `PipelineHooks`; the run-form
      stubs accept `**kwargs`). Run the existing signature/facade assertions of these suites
      unedited and green; the delivery-shape change is pinned by the logic tests below
      (expected to fail at this stage)
- [ ] **Code**: add the `profile=resolved.profile if resolved is not None else None` argument at
      the delivery site of `goga/pipeline/run_pipeline.py` (step 12, line ~446)
- [ ] **Code**: add the same argument at the delivery site of
      `goga/pipeline/describe_pipeline.py` (step 4, line ~161)
- [ ] **Interface verification**: `pytest tests/pipeline/test_pipeline_contract.py
      tests/pipeline/test_describe_pipeline.py -x` — the unchanged signatures still pass
- [ ] **Logic tests / integration scenarios** (extend the existing suites; call the handlers
      directly per R2; reuse the AFM_DIR-pinning, project-pipelines/workflows/profiles
      scaffolding; stub `run_flow`) — the three scenarios from the design:
      - `test_run_form_delivers_loaded_profile_and_renders_contributions` — project fixture with
        pipeline `deploy.yml`, auto-matched workflow `deploy.yml` (no `profile:` key), project
        profile `.goga/profiles/mixa.yml` (`worker: {agent: codex, model: sonnet}`); installed
        tool capturing `context.profile` and contributing
        `WorkflowDocument(stages={"build": WorkflowStage(prompt="Use {{ worker.model }}")})`;
        `AFM_DIR` pinned; `run_pipeline(..., profile="mixa")`; assert captured
        `context.profile.name == "mixa"`, `.source == "project"`, and the compiled/overlay
        workflow carries `Use sonnet`
      - `test_run_form_delivers_none_when_no_workflow_resolved` — the same project without a
        workflow file (silent miss), tool capturing `context.profile`; assert captured
        `profile is None` and a contributed `"{{ x }}"` renders empty (empty context) — the
        delivery still runs onto the empty base
      - `test_card_form_delivers_the_same_fact_and_renders_identically` — the same project and
        tool; `describe_pipeline(..., profile="mixa")`; assert the card-form captured
        `context.profile` equals (`==` and `.name`) the run form's, the rendered contribution
        strings are identical, and the card provenance equals the run provenance
- [ ] **Debugging**: `pytest tests/pipeline -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: both signatures unchanged; the disabled branches deliver
      nothing (passthrough overlay); card/run parity holds; no CLI/catalog/event changes;
      `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/` — fix findings; `ruff format` the touched files

---

## Validation Commands

All commands run in the project virtualenv (`.venv`); Python 3.10+ compatibility required.

- `pytest tests/pipeline/workflow -x`: the workflow-cell suite (Task 1 scope)
- `pytest tests/pipeline/hooks -x`: the hooks-zone suites (Tasks 2–3 scope)
- `pytest tests/pipeline -x`: the wiring and integration scope (Task 4 scope)
- `pytest tests/ -x`: Run all tests (the convention's command; green at every task end and before
  every local commit)
- `ruff check goga/`: Lint check (the convention's lint command — after every coding task and
  before every local commit)
- `ruff check tests/`: Test-code lint (the convention makes ruff the test linter/formatter)
- `ruff format <touched files>`: Formatter per `[tool.ruff.format]` over every file the task
  touched (never repository-wide in this change — see R3)
- `goga lint`: DSL validation over all cells — the contracts are read-only and must stay green
  (93 cells, 0 errors)
- `python -c "from goga.pipeline.workflow import render_contribution"`: Facade accessibility —
  the new routine's facade obligation

---

## Completion Criteria

- [ ] Every changed contract entity is implemented in its declared `location`:
      `render_contribution.py` (new), `amendments.py`, `events.py`, `run_pipeline.py`,
      `describe_pipeline.py` — and matches the materialized signatures exactly (the `profile`
      parameter last with default `None`)
- [ ] `render_contribution` is importable from `goga.pipeline.workflow` and listed in `__all__`
      (alphabetical position before `render_workflow`); the hooks facade is unchanged
      (`ZONE_ALL`, fifteen names)
- [ ] The walk renders at the commit moment inside the walk: every tool's view carries the SAME
      profile object; a render failure is the hard amendment failure (the first failing tool stops
      the walk — no later tool's hooks run, the contribution discarded); the empty check reads the
      rendered document and stays presence-based; the rendered document is the committed document;
      `merge_workflow_overlay` is untouched
- [ ] The run and card forms deliver the identical fact and the identical rendering
      (`resolved.profile if resolved is not None else None` at both sites); the disabled branches
      are unchanged
- [ ] The error vocabulary holds: `template error at <dot-path>: <Class>: <message>` (source
      keys, indexed lists, positionally disambiguated gates, bracket-repr key paths) and
      `rendered key collision in <map>: keys <a!r> and <b!r> both render to <r!r>`; the walk's
      failure tail keeps the `… failed on pipeline.amend_workflow: <reason>` shape
- [ ] All 23 design test scenarios are implemented (13 render-contribution + 7 hooks-delivery +
      3 wiring) and the two existing contract suites are EXTENDED in the same change sets as the
      signatures they pin (`test_amendments.py` field list + construction, `test_events.py`
      parameter list)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic
      tests → debugging → re-verification → lint)
- [ ] The Mandatory Rules were observed in every task and every commit: R1 style (relative
      imports, `kw_only` discipline, Google docstrings, blank-line block separation), R2 test
      rules (mirror layout, `test_<what>_<scenario>` naming, mock-free pure-logic tests, direct
      handler calls, `pytest.raises(match=...)` regex prefixes), R3 lint/format gates (`ruff
      check goga/ tests/` + `ruff format` on touched files before every local commit; no commit
      behind red tests or lint findings), R4 REPL cycle (live-probed behavior, fresh-interpreter
      re-evaluation, all verified code migrated into source files and tests)
- [ ] No package boundary was expanded; no new cells; no `.usages/` files created or modified;
      the final modules (`overlay.py`, `render_workflow.py`, the `emit_*` members, `cli.py`, the
      action catalog) and the three usage files are untouched
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check goga/` and `tests/`,
      `goga lint` 93/0, the facade check)
