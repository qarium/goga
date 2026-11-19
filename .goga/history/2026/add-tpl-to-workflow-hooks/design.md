# Design Document: `add-tpl-to-workflow-hooks`

## Contract Changes

Derived from the working-tree diff of the CODEMANIFEST layer (branch
`add-tpl-to-workflow-hooks` vs `HEAD`), which materialized the architecture
plan (`arch.md`) and the ADR (`adr.md`) of this topic. Baseline checks:
`goga lint` — 93 cells, 0 errors; `goga schema --depends-on` on the three
cells confirms every other dependent (the compiler and build/commands cells
over `goga/pipeline/workflow`) imports only model types and practices this
additive change does not touch — the affected set is exactly the three
modified cells.

### Changed CODEMANIFEST Files

- `goga/pipeline/workflow/CODEMANIFEST`
  - Header `Annotations`: new two-surfaces paragraph — the contributor-profile
    zone renders whole workflow-files before parsing AND the strings of
    committed workflow contributions (field-level render; strings only,
    structure/presence/non-string values preserved).
  - Body: new Routine `render_contribution(document, profile_data) -> rendered`
    (`location: render_contribution.py`, placed after `render_workflow`).
  - Footer `Description`: closing fragment "… and field-level rendering of
    committed workflow contributions."
- `goga/pipeline/hooks/CODEMANIFEST`
  - Header `Imports`: the `goga/pipeline/workflow` edge grows
    `ResolvedProfile` and `render_contribution` (additive).
  - Header `Annotations`: mutual-blindness sentence extended ("… and the same
    resolved profile fact …"); new profile-aware paragraph (render at commit,
    inside the walk, before the presence-based empty check; render failure is
    disciplinarily a hook failure; template-free byte-identity).
  - `WorkflowAmendment` gains `profile: ResolvedProfile | None = None`
    (parameter, requirement bullet, property).
  - `PipelineHooks.amend_workflow` gains the same trailing parameter; the
    algorithm is rewritten to seven steps (render-at-commit is step 4; the
    empty check runs on the rendered document, step 5; the rendered document
    is the committed document, step 6); new requirements/constraints.
  - Footer `Description`: closing sentence on the profile-aware amendment.
- `goga/pipeline/CODEMANIFEST`
  - Header `Imports`: `ResolvedProfile` appended to the
    `goga/pipeline/workflow` type list.
  - Header `Annotations`: profile-aware fragment on the amendment delivery
    (both forms deliver the identical fact and identical rendering).
  - `describe_pipeline` algorithm step 4 delivers "… with the merged workflow
    and the operation's resolved profile (the `LoadedWorkflow` profile of
    step 2 — None when no workflow resolved)"; new card/run-parity
    requirement bullet.
  - `run_pipeline` algorithm step 12 delivers "… with the authored workflow
    after the skip merge and the operation's resolved profile …"; new
    profile-carriage requirement bullet.

### New Entities

- `render_contribution(document: WorkflowDocument, profile_data: dict[str, Any]) -> rendered: WorkflowDocument`
  — Routine, `goga/pipeline/workflow`, `render_contribution.py`. Renders every
  template surface (string leaf + string mapping key, any depth, typed model
  fields and verbatim extend bodies alike) of one committed contribution with
  the fixed Jinja environment and exactly `profile_data` as context; pure, no
  I/O; strict errors (template cause + document dot-path; rendered-key
  collision).

### Changed Entities

- `WorkflowAmendment` — new read-only `profile` fact (operation data; None
  without activation; identical for every tool and in every delivery form).
- `PipelineHooks.amend_workflow` — new `profile` parameter; render-at-commit
  step inside the walk (a render failure is the hard amendment failure; the
  walk stops before the next tool; the empty check and the merge are
  unchanged and run on the rendered document).
- `describe_pipeline` / `run_pipeline` — wiring only: pass
  `resolved.profile if resolved is not None else None` into the delivery.
  Signatures unchanged.

### Deleted Entities

- None.

### Usages and Annotations Changes

- `.goga/usages/cooks/jinja2.md` (project-level cook, referenced by the
  workflow cell as `jinja2`): domain restated as the two rendering surfaces;
  new "Field-level render of a committed contribution" pattern (surface
  definition, example, failure vocabulary incl. collision); anti-patterns
  updated (no second environment/dialect/ambient context; document path
  replaces file line for contribution strings). Predates this design
  (updated during task formulation); verified consistent — one review-time
  wording fix applied (the amendment-failure bracket now says a render
  failure names the tool and the action, no hook).
- `goga/pipeline/hooks/.usages/checkpoints.md` (imported by `goga/pipeline`
  as `checkpoints`): `loaded.profile` fact bullet; `profile=loaded.profile`
  in the delivery example; four render-semantics bullets (same fact in both
  forms, render at commit before the unchanged checks, hard render failure,
  template-free byte-identity).
- `goga/pipeline/.usages/registering-hooks.md` (consumer doc of the pipeline
  cell; the `registering-hooks` practice imported by `goga/commands/pipeline`
  comes from `goga/hooks` and is untouched): amendment-view section rewritten
  (profile read + template-surface + template-error + legacy-note bullets)
  and a "Profile-aware contribution" integration scenario. Additive; the
  subscription mechanics it documents are unchanged — no contract change
  reaches `goga/commands/pipeline`.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Phase 3 validation found no defects:
  - syntax/DSL — `goga lint` clean (key casing, header→body→footer, location
    `render_contribution.py` flat with extension, optional parameter last in
    both changed signatures);
  - imports — no cross-imports (edge `hooks → workflow` already existed; the
    direction `workflow ← hooks ← pipeline` is preserved; no cycles);
  - practices — every connected practice is referenced (`jinja2` in the new
    routine annotation and the extended header; `per-tool-delivery`,
    `registering-hooks`, `checkpoints`, `convention` unchanged in role);
  - reference closure — every backtick reference in the changed annotations
    resolves inside its document (`render_contribution`, `profile`,
    `profile_data`, `document`, `rendered`, `LoadedWorkflow`,
    `ResolvedProfile`, `jinja2`, `convention`, `per-tool-delivery`).

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

1. **Run form (pre-launch)** — `run_pipeline` steps 1–11 unchanged
   (config load+amend, discovery, `AFM_DIR`, `resolve_workflow` under the
   activation context, feedback line, `apply_skip_stages`, fact resolution).
   Step 12 now also passes the operation's resolved profile; the overlay's
   rendered tool strings then flow into `compile_flow` (step 13), the
   effective-global-agent read (step 14 — reads only `agent`, a rendered
   string), the env wrappers (steps 15 — rendered env maps/keys), the afm
   configuration write (step 17 — rendered collaboration strings), and the
   launch layer (step 20 — no workflow strings).
2. **Card form** — `describe_pipeline` steps 1–3 unchanged; step 4 passes
   the same resolved value; the card then compiles the overlay through the
   real machine into a temp dir (steps 5–8). No events fire; identical fact
   and identical rendering as the run form.
3. **Render-at-commit (inside the walk)** — per tool: hooks run against the
   view carrying the profile fact → on the tool's last hook returning, the
   buffered RAW document renders with `profile.data` (or `{}`) → the
   presence-based empty check reads the RENDERED document → non-empty
   commits as the rendered document. A render failure raises the hard
   amendment error; the walk stops before the next tool's hooks.

### Entity Dependencies

- `render_contribution` depends on nothing but the fixed Jinja environment
  (module-level, same construction as `render_workflow`) and the
  `dataclasses`/`typing` machinery — the workflow cell stays a leaf.
- `PipelineHooks.amend_workflow` imports `render_contribution` (and
  `ResolvedProfile` for the annotation) from `..workflow` — the existing
  edge, used additively.
- `merge_workflow_overlay` receives already-rendered documents; it is
  untouched.
- Initialization order is unchanged: `PipelineHooks()` stays cheap; the
  registry builds lazily at the first checkpoint.

## Code Stack Trace

### Trace: `run_pipeline` (step 12 wiring, run form)

#### Chain
1. **Input**: CLI `run` → `pipeline_cli` → `run_pipeline(...)`; `resolved`
   holds the `LoadedWorkflow` of step 8 (`resolve_workflow`), `workflow_doc`
   the skip-merged document of step 10, `identity/decision/work` the facts
   of step 11.
2. **Step**: `decision.kind != "disabled"` → `hooks.amend_workflow(...,
   workflow=workflow_doc, work=work, profile=resolved.profile if resolved
   is not None else None)` → checkpoint: value type `ResolvedProfile | None`
   matches the parameter; the profile comes from the LOADED workflow
   (`resolved`), not the skip-merged `workflow_doc` — `apply_skip_stages`
   never touches `.profile`, so both sources agree; `None` exactly when no
   workflow resolved (silent miss / containment escape / explicit-missing)
   → **passed**.
3. **Step**: a render failure surfaces as `ValueError` from the walk → the
   CLI's generic strict pre-run branch prints `Error: pipeline '<name>'
   could not be prepared: …` and returns 1 before any compile/launch/event
   (existing `cli.py` handling; the `UndefinedError` branch there stays
   reserved for the whole-file render, which propagates unwrapped — the
   contribution render wraps its own cause) → **passed**.
4. **Output**: `overlay` feeds steps 13–24 unchanged; every tool-authored
   string inside it is rendered.

#### Checkpoint Summary
- Type flow `LoadedWorkflow.profile → amend_workflow.profile`: passed.
- No-workflow `None` carriage (silent-miss keeps the layer active on the
  empty base with an empty context): passed.

### Trace: `describe_pipeline` (step 4 wiring, card form)

#### Chain
1. **Input**: `describe_pipeline(...)` with `resolved` from step 2.
2. **Step**: `decision.kind != "disabled"` → `hooks.amend_workflow(...,
   profile=resolved.profile if resolved is not None else None)` → checkpoint:
   identical rule to the run form; the card applies the profile through the
   same channels (`profile` parameter, `GOGA_PROFILE`, decoded home bundle)
   → **passed**.
3. **Output**: `overlay` compiles into the temp flow-file; the card reports
   `overlay.provenance`. Card/run equivalence is structural and now also
   covers the rendered contributions (same resolved value, same render
   semantics, same merge).

#### Checkpoint Summary
- Run/card parity of the fact and the rendering: passed.

### Trace: `PipelineHooks.amend_workflow` (changed walk)

#### Chain
1. **Input**: caller facts incl. `profile`.
2. **Step**: `_ensure_registry()` → `declared_actions()` lookup —
   `Action(domain="pipeline", name="amend_workflow", error_class="hard")`
   exists in `goga/hooks/catalog/catalog.py` → **passed**.
3. **Step**: subscriptions grouped per tool in enumeration order (dict
   insertion order) → for each tool a FRESH `WorkflowAmendment(pipeline,
   decision, workflow, work, profile)` — the SAME `profile` object reaches
   every view (mutual blindness extended; `wrap_context` passes attribute
   reads, blocks assignment) → **passed**.
4. **Step**: each hook called via `build_hook_arguments`; the existing
   in-`try` buffer guard (out-of-contract buffer type fails the hook that
   wrote it) stays as-is → **passed**.
5. **Step (NEW)**: after the tool's hooks returned — buffer `None` → silent
   `continue`; otherwise `render_contribution(buffer, profile.data if
   profile is not None else {})`. Checkpoint: `profile.data` is
   `dict[str, Any]` — exactly `render_contribution`'s context type;
   `{}` preserves the empty-context parity → **passed**. A `ValueError`
   from the render is wrapped as the hard amendment failure (format below);
   the tool's contribution is discarded and the walk stops before the next
   tool (raise, not `continue`).
6. **Step**: the presence-based empty check reads the RENDERED document —
   the eight facts (`prompt`, `stages`, `extend`, `memory`, `assistants`,
   `delegation`, `repeat`, `gates`) unchanged; rendering preserves presence,
   so the check's meaning is untouched (a rendered `""` is a value → the
   document counts as non-empty; see edge case EC-3) → **passed**.
7. **Output**: `ToolContribution(tool, rendered_document)` per committing
   tool → `merge_workflow_overlay(workflow, contributions)` → overlay.
   Checkpoint: the merge consumes only rendered strings from here on; it
   never reads contribution `profile`/`build`/`agent`/`env` (globals are
   base-only), and those dead fields already rendered (or failed) — the
   "dead fields included" strictness lands pre-merge → **passed**.

#### Checkpoint Summary
- Interface alignment `amend_workflow → render_contribution →
  ToolContribution`: passed.
- Failure discipline (first failing tool stops the command; no later tool's
  hooks run): passed.

### Trace: `render_contribution` (new routine)

#### Chain
1. **Input**: `document` — a `WorkflowDocument`-shaped value authored by a
   tool (constructed in Python, not parsed from YAML: non-string map keys
   and arbitrary `body` payloads are possible); `profile_data` — the whole
   active profile content or `{}`.
2. **Step**: the walker dispatches on the RUNTIME type of every node
   (see Algorithm Design) — dataclass instances recurse over their declared
   fields in declaration order (`dataclasses.replace` rebuilds), mappings
   render string keys and recurse values, sequences recurse elements with
   index paths, `str` renders, everything else is carried unchanged.
   Checkpoint: field-set-complete — the walk reads
   `dataclasses.fields(value)`, so a future `WorkflowStage` field flows
   through with no change here; the extend `body` maps recurse freely
   (open-ended) → **passed**.
3. **Step**: each string renders with the module-fixed
   `Environment(trim_blocks=True, lstrip_blocks=True,
   keep_trailing_newline=True, autoescape=False)` — the SAME flag set
   `render_workflow` uses (one environment contract per the `jinja2`
   practice; no ambient variables — the context is exactly
   `**profile_data`) → **passed**.
4. **Step**: per-map collision detection on rendered result keys; per-string
   error wrapping with the document dot-path (grammar below) → **passed**.
5. **Output**: a NEW `WorkflowDocument` — every string surface rendered,
   every non-string value carried, field presence and mapping order
   preserved; the input and every nested container are unmutated.

#### Checkpoint Summary
- Purity / no-I/O: passed (pure Python transformations only).
- Presence preservation (empty-contribution check unaffected): passed.

### Trace: `merge_workflow_overlay` (unchanged, input compatibility)

The merge already treats contribution documents as opaque field bags: the
stage field loop, whole-block resolvers, catalog/stage assistant passes,
and the extend pass read rendered strings like any others. Rendered stage
names, extend names, `before`/`after` refs and assistant names render with
ONE context, so name references inside one contribution stay consistent
(`after: ["h{{ 'ard' }}"]` matches a contributed stage `h{{ 'ard' }}` after
both render). No merge change is required or allowed.

## Algorithm Design

### `render_contribution` (new, `goga/pipeline/workflow/render_contribution.py`)

**Responsibility**: the field-level rendering step of the amendment — one
committed document in, one rendered document out, under the fixed workflow
rendering semantics.

**Module layout** (mirrors `render_workflow.py`):

```python
from jinja2 import Environment  # the module reuses the same fixed flag set
_RENDER_ENVIRONMENT = Environment(
    trim_blocks=True, lstrip_blocks=True,
    keep_trailing_newline=True, autoescape=False,
)
```

Share the environment construction with `render_workflow` by repeating the
same four-flag literal in this module (the intra-package import rules and
one-environment contract forbid no sharing; two identical literals are the
existing precedent — the flags are the contract, not the object identity).
Do NOT import `render_workflow`'s private environment: keep both modules
self-contained like the rest of the cell.

**Algorithm** (the walker, private helpers):

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

**Document dot-path grammar** (the failure vocabulary):

- Segments join with `.`; the root is the `WorkflowDocument` field name
  (`prompt`, `stages`, `extend`, `memory`, `profile`, `build`,
  `assistants`, `delegation`, `repeat`, `gates`, `agent`, `env`).
- String mapping keys join with `.` using the SOURCE (pre-render) key —
  e.g. `stages.build.prompt`, `assistants.reviewer.agent`,
  `extend.scans.body.title`, `stages.build.env.API_KEY`.
- List elements append `[i]` — e.g. `stages.build.skills[0]`,
  `extend.scans.body.roles[2]`.
- The two gates shapes disambiguate positionally: the workflow-level
  settings block is the dot path under `gates` (`gates.patience` — note its
  model fields are int/bool, so in practice no string surface lives there),
  while a stage check-step list is `stages.<name>.gates[i].<field>` —
  e.g. `stages.review.gates[0].script`.
- Non-string mapping keys (possible only in tool-constructed documents and
  inside extend bodies) use the bracket form `[<repr>]`.
- A template error inside a string mapping KEY reports the bracket-repr
  form of its SOURCE key — `template error at stages['buil{{ "d" }}']: …`
— so the failing key is named; the collision error of the same map keeps
  the plain map dot-path (`rendered key collision in stages: …`).

**Errors**:
- Template error on any surface (values, keys, dead global fields, extend
  bodies — `TemplateSyntaxError`, `UndefinedError` on nested missing access,
  or any other exception raised by the render call of that surface) →
  `ValueError: template error at <dot-path>: <ErrorClass>: <message>`.
- Rendered-key collision inside one map → `ValueError: rendered key
  collision in <map dot-path>: keys <a!r> and <b!r> both render to <r!r>`.

**Edge Cases**:
- EC-1 `profile_data={}` (no activation): template syntax still processes;
  `{{ missing }}` renders `""`; `{% if missing %}` is falsy. Parity with
  the whole-file empty-context render.
- EC-2 A template-free document renders to an EQUAL document (Jinja renders
  plain text unchanged under these flags) — presence, order, and values
  identical.
- EC-3 A string rendering to `""` stays a present value (`prompt=""` is not
  `prompt=None`) — the presence-based empty-contribution check and the
  assistant declaration discriminator are unaffected; the prompt merge
  already drops empty texts.
- EC-4 Non-string scalars (`loop: 3`, `skip: False`, `gate: true`,
  delegation bounds) are carried unchanged — never template surfaces.
- EC-5 Keys that render to `""`: a map key rendering to the empty string is
  a legal result key (present, empty); it collides only with another source
  key that also renders to `""`.
- EC-6 Self-referential structures a tool might build: out of contract —
  the walker recurses and a cycle surfaces as `RecursionError`; not handled
  (parse-built documents are acyclic).
- EC-7 Subclassing: `dataclasses.replace` reconstructs via `type(value)`,
  so a tool subclass of a model keeps its class when every field is init
  (the contract models are).

### `WorkflowAmendment` (changed, `goga/pipeline/hooks/amendments.py`)

**Responsibility**: the per-tool read-and-contribute view; adds the
read-only `profile` fact.

**Algorithm**: add the field after `work`:

```python
from ..workflow import ResolvedProfile, WorkflowDocument

    profile: ResolvedProfile | None = None
```

Runtime import of `ResolvedProfile` (matches the file's existing runtime
import of `WorkflowDocument`); the docstring gains the `profile:` arg line.
No behavior: the field is a delivered fact; `contribute` and the buffer are
untouched.

### `PipelineHooks.amend_workflow` (changed, `goga/pipeline/hooks/events.py`)

**Responsibility**: the hard amendment delivery — now profile-aware.

**Algorithm** (the walk; only the marked steps change):

```
1–3. unchanged: registry build, declared-actions lookup, per-tool grouping,
     view construction — the view now receives profile=profile (NEW: same
     object into every tool's view), wrap_context, per-hook call with the
     existing in-try buffer guard (out-of-contract buffer types still fail
     the hook that wrote them)
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

- `render_contribution` is imported from `..workflow` (runtime import — it
  is called) alongside the existing `TYPE_CHECKING` `WorkflowDocument`.
- The signature gains `profile: ResolvedProfile | None = None` as the last
  parameter (backward compatible; `ResolvedProfile` joins the
  `TYPE_CHECKING` import block).
- The docstring algorithm/args/raises sections are updated to the contract
  text; the render-failure message names the tool and the action and
  carries the template cause — same `pipeline.amend_workflow: <reason>`
  tail as the existing hook-failure format, so the CLI's generic strict
  pre-run branch reports it unchanged.

### Wiring: `run_pipeline` / `describe_pipeline`

**Algorithm**: one expression at each delivery site —

```python
overlay = hooks.amend_workflow(
    pipeline=identity, decision=decision, workflow=workflow_doc, work=work,
    profile=resolved.profile if resolved is not None else None,   # NEW
)
```

(`resolved` is the `LoadedWorkflow | None` both routines already hold from
their `resolve_workflow` step.) The disabled branches, the docstrings'
Raises notes, and everything after the delivery are unchanged.

### Facade exports

- `goga/pipeline/workflow/__init__.py`: import
  `from .render_contribution import render_contribution` and add
  `"render_contribution"` to `__all__` (alphabetical position before
  `"render_workflow"` — the list is alphabetized; `render_contribution`
  sorts before `render_workflow`).
- `goga/pipeline/hooks/__init__.py`: unchanged (the fifteen-name facade
  gains nothing; `render_contribution` is internal to the zone).

**Errors** (zone-wide summary):
- `render_contribution` strict errors → the walk's hard amendment failure →
  `run_pipeline`/`describe_pipeline` propagate → CLI prints
  `Error: pipeline '<name>' could not be prepared: contribution of tool
  <tool> failed on pipeline.amend_workflow: template error at
  <path>: <Class>: <message>` (the run form's prefix; the card form prints
  the plain `Error: <message>` shape); exit 1; no events fire; afm never
  launches.
- Everything else (soft notifications, `emit_*` members) is untouched.

## Cross-cutting Concerns

- **Error handling**: unchanged strategy — the amendment action is hard
  (`error_class="hard"` in the catalog), the notifications stay soft. The
  new render failure reuses the hard channel and the existing CLI boundary.
  No new exception types: `ValueError` everywhere (the cell precedent —
  `WorkflowSyntaxError` is a `ValueError` subclass for parse-side needs;
  the render errors stay plain `ValueError` because no consumer dispatches
  on the type).
- **Logging**: unchanged — the empty-contribution warning
  (`tool contributed an empty document; discarded`, extra tool/action)
  still fires once per discarded tool; renders and profile facts log
  nothing (facts are delivered, not logged; the launch feedback line of
  step 9 already reports the active profile name).
- **Validation**: NO new post-render validation exists (ADR decision 5).
  Rendered strings flow to the checks that already exist: env-key legality
  at wrapper generation (`stage_env_wrappers` / `gate_env_wrappers`
  strict pre-run errors), assistant agent resolution and env-key legality
  at the afm configuration write, stage-name resolution and the full
  structural validation at `compile_flow`.
- **Caching**: none — the render is per-commit, single-shot, and pure.
- **Concurrency**: single-threaded as today; no shared mutable state is
  introduced (the fixed Jinja `Environment` is thread-safe for rendering,
  as `render_workflow` already relies on).

## Usages Analysis

### `jinja2` (project-level cook, `.goga/usages/cooks/jinja2.md`)
- **What it provides**: the two rendering surfaces, the fixed environment
  flags, the context rule (exactly the single active profile; empty without
  activation; no ambient variables), missing-key semantics, the strict
  failure vocabulary (file+line for authored files; document dot-path for
  contribution strings; the collision failure), anti-patterns (no second
  environment/dialect/ambient context; the one sanctioned render of a
  parsed document).
- **Where used**: `render_contribution` (environment + context + error
  surfacing), the workflow-cell header, `render_workflow` (unchanged).
- **Why chosen**: the ADR fixes one environment and one context rule for
  both surfaces; the cook is the single source for them.
- **How exactly**: `_RENDER_ENVIRONMENT.from_string(surface).render(**profile_data)`
  per surface; `TemplateSyntaxError`/`UndefinedError`/any render exception
  wrapped with class, message, dot-path.

### `convention` (`.goga/usages/conventions.md`)
- **What it provides**: code style, dataclass discipline (kw_only), REPL
  cycle, test layout (`tests/…` mirrors the package), docstring style.
- **Where used**: every touched module and every new test file.
- **How exactly**: `@dataclass(kw_only=True)` models; module docstrings in
  the cell's one-line form; tests under `tests/pipeline/workflow/` and
  `tests/pipeline/hooks/` mirroring the source structure.

### Imported Usages
- `per-tool-delivery` from `goga/hooks` — the walk's loop skeleton and the
  commit-after-success rule; `render_contribution` slots into the commit
  moment between the hook loop and the empty check.
  Path: `goga/hooks/.usages/per-tool-delivery.md`.
- `registering-hooks` from `goga/hooks` — the hook signature receiving the
  view (the new `profile` attribute is read through the same wrapped
  context). Path: `goga/hooks/.usages/registering-hooks.md`.
- `declaring-actions` from `goga/hooks` — unchanged role (the notification
  and bridged emissions). Path: `goga/hooks/.usages/declaring-actions.md`.
- `checkpoints` from `goga/pipeline/hooks` — the delivery documentation the
  pipeline cell codes against; updated with the profile fact and the
  render semantics. Path: `goga/pipeline/hooks/.usages/checkpoints.md`.

## `.usages/` Update

### Cell: `goga/pipeline/workflow`
No `.usages/` directory exists — none required (the rendering practice is
project-level; consumer docs live with the hooks pair).

### Cell: `goga/pipeline/hooks`
- **`checkpoints.md`** → `goga/pipeline/hooks/.usages/checkpoints.md`
  - Status: current (updated by the architecture-apply stage; verified
    against this design — the `loaded.profile` fact, the `profile=`
    delivery example, and the four render bullets match the traced
    behavior, including the empty-context and first-failure semantics).
  - Additions/Updates needed: none.

### Cell: `goga/pipeline`
- **`registering-hooks.md`** → `goga/pipeline/.usages/registering-hooks.md`
  - Status: current (updated by the architecture-apply stage; the
    amendment-view section — profile read, every-string-is-a-surface,
    template-error, collision, legacy note — and the "Profile-aware
    contribution" scenario match this design).
  - Additions/Updates needed: none.
- Other files (`describe-pipeline.md`, `run-pipeline.md`, …) describe the
  callers' CLI surfaces, which do not change — out of scope.

## Test Stack Trace

### General Setup

- `tests/pipeline/workflow/conftest.py` fixtures: `project_root` (chdir'd
  fake project), `home_bundle` (`{"mixa": {"worker": {"agent": "codex",
  "model": "sonnet"}}}`), `render_env` (the four-flag Environment — reuse
  for expectation building).
- `tests/pipeline/hooks/conftest.py`: `pin_package_environment` /
  `install_tool_package` (the platform boundary), `_facts()`-style
  amendment facts, `field_defaults` introspector, `ZONE_ALL` facade list.
- Wiring tests reuse the existing `tests/pipeline/test_run_pipeline_hooks.py`
  / `test_describe_pipeline.py` environment scaffolding (AFM_DIR pinning,
  project pipelines/workflows/profiles directories).

### Source File Registry

- `goga/pipeline/workflow/render_contribution.py` (new) + `__init__.py`
  export — `tests/pipeline/workflow/test_render_contribution.py` (new).
- `goga/pipeline/hooks/amendments.py`, `events.py` —
  `tests/pipeline/hooks/test_amendments.py`, `test_events.py` (extend).
- `goga/pipeline/run_pipeline.py`, `describe_pipeline.py` —
  `tests/pipeline/test_run_pipeline_hooks.py`, `test_describe_pipeline.py`
  (extend).

---

### Positive Tests

#### `test_template_free_document_renders_to_an_equal_document`

**Setup**: `document = WorkflowDocument(prompt="plain",
stages={"build": WorkflowStage(prompt="p", skills=["s"], env={"K": "v"})},
extend={"scan": WorkflowExtendStage(before=["build"], body={"title": "t",
"roles": ["r1", "r2"]})}, memory=WorkflowMemory(path="mem.md"),
agent="codex", env={"A": "1"})`; `profile_data = {"model": "sonnet"}` (a
non-empty context proves plain strings never interpolate).

**Input**: `render_contribution(document, profile_data)`

**Trace**:
```
render_contribution(document, {"model": "sonnet"})
  → _walk(document)            # dataclass → fields in order
    → _render_surface("plain") # no template syntax → "plain"
    → _walk_map(stages)        # key "build" renders to "build"
      → _walk(WorkflowStage)   # prompt/skills/env walked
    → _walk_map(extend["scan"].body)  # nested strings walked
  → rendered document
```

**Assertions**:
```
rendered == document                     # dataclass equality end to end
list(rendered.stages) == ["build"]       # order preserved
document.prompt == "plain"               # input unmutated (purity, cf. EC-2)
```

**Sufficiency**: pins the backward-compatibility guarantee — template-free
contributions compose byte-identically with or without a profile.

#### `test_renders_values_and_keys_at_any_depth`

**Setup**: `profile_data = {"suffix": "ci", "model": "sonnet"}`;
`document` with `stages={"build-{{ suffix }}": WorkflowStage(prompt="Model:
{{ model }}", notes={"run-{{ suffix }}": "note {{ model }}"},
gates=[WorkflowGateStep(name="check-{{ suffix }}", script="echo {{
model }}")])}`, `extend={"scan": WorkflowExtendStage(before=["build-ci"],
body={"title": "Scan {{ model }}", "nested": {"deep": "{{ model }}"}})}`,
`assistants={"rev-{{ suffix }}": WorkflowAssistant(name="rev-{{ suffix }}",
prompt="Review {{ model }}")}`, `build=WorkflowBuild(env={"K_{{ suffix }}":
"{{ model }}"})`, `agent="agent-{{ suffix }}"`.

**Input**: `render_contribution(document, profile_data)`

**Trace**: walker reaches every string — values and keys, model fields and
extend bodies, gates step fields, build env keys.

**Assertions**:
```
rendered.stages keys == ["build-ci"]
stage.prompt == "Model: sonnet"
stage.notes == {"run-ci": "note sonnet"}
stage.gates[0].name == "check-ci"; .script == "echo sonnet"
rendered.extend["scan"].body["title"] == "Scan sonnet"
rendered.extend["scan"].body["nested"]["deep"] == "sonnet"
rendered.assistants keys == ["rev-ci"]; entry.prompt == "Review sonnet"
rendered.build.env == {"K_ci": "sonnet"}
rendered.agent == "agent-ci"            # a never-merging global still renders
```

**Sufficiency**: the type-driven field-set-complete law — every surface
class (typed fields, extend bodies, keys, list elements) renders; prevents
a future "enumerated field list" regression.

#### `test_empty_context_renders_missing_keys_empty` (EC-1)

**Setup**: `document = WorkflowDocument(prompt="a{{ missing }}b")`.

**Input**: `render_contribution(document, {})`

**Trace**: `_render_surface` renders with `**{}` — standard `Undefined` →
empty interpolation.

**Assertions**: `rendered.prompt == "ab"`.

**Sufficiency**: parity with the whole-file empty-context render; the
no-activation delivery must not raise on plain missing keys.

#### `test_non_string_scalars_carried_unchanged` (EC-4)

**Setup**: `document` with `stages={"b": WorkflowStage(loop=3, skip=True,
manual=False, memory=None)}`, `delegation=WorkflowDelegation(depth=2,
max_tasks=50)`, `repeat=WorkflowRepeat(max_cycles=0, keep_runs=None)`,
`gates=WorkflowGates(patience=1)`; context `{"x": "y"}`.

**Assertions**: every non-string field `is` the source value (`loop == 3`,
`skip is True`, `manual is False`, `repeat.max_cycles == 0` — a zero is a
value, `keep_runs is None`).

**Sufficiency**: non-string scalars are never template surfaces; presence
discipline (`manual=False` vs None) survives the render.

---

### Negative Tests

#### `test_syntax_error_raises_with_class_message_and_dot_path`

**Setup**: `document = WorkflowDocument(stages={"build":
WorkflowStage(prompt="Model: {{ model")})` (unclosed expression);
`profile_data = {"model": "sonnet"}`.

**Input**: `pytest.raises(ValueError, match=...)` around
`render_contribution(document, profile_data)`.

**Trace**: `_render_surface` → jinja raises `TemplateSyntaxError` →
wrapped.

**Assertions**:
```
match == r"template error at stages\.build\.prompt: "
        r"TemplateSyntaxError: unexpected end of template"
```
(regex match via `pytest.raises(match=...)`, NOT an exact equality — the
full Jinja message continues `…unexpected end of template, expected 'end
of print statement'.`; the pattern is a stable prefix of it).

**Sufficiency**: the strict-failure vocabulary — error class, message, and
document path — is the actionable pre-run error the ADR demands.

#### `test_nested_undefined_access_raises_with_dot_path`

**Setup**: `document = WorkflowDocument(stages={"build":
WorkflowStage(prompt="{{ worker.model }}")}); `profile_data={}`.

**Assertions**: `ValueError` matching
`r"template error at stages.build.prompt: UndefinedError"`.

**Sufficiency**: standard-Jinja nested-missing semantics stay strict and
located (unlike the whole-file render, which lets `UndefinedError`
propagate unwrapped — the contribution render must carry the path).

#### `test_error_in_a_dead_global_field_is_strict`

**Setup**: `document = WorkflowDocument(profile="{{ broken",
stages={"b": WorkflowStage(prompt="ok")}); any context.

**Assertions**: `ValueError` matching `r"template error at profile:"`; the
valid stage does not rescue the run.

**Sufficiency**: ADR decision 4 — dead fields included; a broken template
fails the run regardless of where the string sits.

#### `test_rendered_key_collision_names_map_sources_and_result`

**Setup**: `profile_data = {}`; `document = WorkflowDocument(stages={
"build": WorkflowStage(prompt="a"),
'buil{{ "d" }}': WorkflowStage(prompt="b"),
})` — the second source key `'buil{{ "d" }}'` renders to `build`, and the
plain key `"build"` renders to itself: both produce the result key `build`.

**Input**: `pytest.raises(ValueError, match=...)` around
`render_contribution(document, {})`.

**Assertions**: `ValueError` matching
`r"rendered key collision in stages: keys 'build' and 'buil\{\{ \"d\" \}\}' both render to 'build'"`.

**Sufficiency**: ADR rejects later-wins — silently losing a whole stage
override must be impossible; the map, both SOURCE keys, and the result are
named.

#### `test_error_path_indexes_lists_and_disambiguates_gates`

**Setup**: `document = WorkflowDocument(stages={"review":
WorkflowStage(gates=[WorkflowGateStep(name="check", script="{{ oops")])})
` and a contribution whose extend body carries `roles: ["fine", "{{ oops"]`.

**Assertions**: paths `stages.review.gates[0].script` and
`extend.<name>.body.roles[1]` appear in the respective messages (bracket
indices; the stage check-step list path never collapses into the settings
block form).

**Sufficiency**: the dot-path grammar — indexed lists, positionally
disambiguated gates shapes.

---

### Edge Case Tests

#### `test_rendered_empty_string_stays_present` (EC-3)

**Setup**: `document = WorkflowDocument(prompt="{{ gone }}"); `profile_data={}`.

**Assertions**: `rendered.prompt == ""` and `rendered.prompt is not None`.

**Sufficiency**: presence preservation — the downstream empty-contribution
check and the assistant declaration discriminator keep their meaning.

#### `test_purity_the_input_tree_is_never_mutated`

**Setup**: build the depth-covering document of the depth test; snapshot
`copy.deepcopy(document)` before the call.

**Assertions**: `document == snapshot` after the call; nested maps (`body`,
`env`, `notes`) are equal AND the returned containers are not the input
objects (`rendered.stages is not document.stages`).

**Sufficiency**: the routine's purity requirement — a tool's buffer must
survive its commit render intact (e.g. for a repeated delivery).

#### `test_walk_reconstructs_dataclasses_with_type_preserved` (EC-7)

**Assertions**: `type(rendered) is WorkflowDocument`,
`type(rendered.stages["…"]) is WorkflowStage` for every nested model.

**Sufficiency**: `dataclasses.replace`-based rebuild keeps the model types
the merge and the compiler switch on.

#### `test_tuple_containers_recurse_and_rebuild_as_tuples`

**Setup**: `document = WorkflowDocument(extend={"scan":
WorkflowExtendStage(before=("build",), body={"roles": ("a{{ x }}",
("deep-{{ x }}",))})})`; `profile_data = {"x": "ci"}` (tool-constructed
documents may carry tuples — the models type `list[str]`, but nothing
coerces a Python value, and the buffer guard only checks the eight facts).

**Input**: `render_contribution(document, profile_data)`.

**Trace**: `_walk(extend)` → map key `"scan"` → `WorkflowExtendStage`
— field `before` is a tuple → `type(value)` is `tuple` → elements render
(`"build"` → `"build"`); field `body` is a map → key `"roles"` → the
tuple value → `[0]` `"a{{ x }}"` renders `"aci"`, `[1]` is a nested
tuple → `[1][0]` `"deep-{{ x }}"` renders `"deep-ci"`; an error inside
would report `extend.scan.body.roles[1][0]`.

**Assertions**:
```
rendered.extend["scan"].before == ("build",)
isinstance(rendered.extend["scan"].before, tuple)
rendered.extend["scan"].body["roles"] == ("aci", ("deep-ci",))
```

**Sufficiency**: pins the `(list, tuple)` reconstruction branch
(`type(value)(…)` — the riskiest line of the container arm), nested
tuples, and the `[i][j]` path composition; prevents a regression where a
tuple silently becomes a list or its elements stop rendering.

---

### Hooks-zone tests (`tests/pipeline/hooks/`)

#### `test_view_carries_the_same_profile_fact_for_every_tool` (positive)

**Setup**: `pin_package_environment` + two `install_tool_package` tools
recording `id(context.profile)` and `context.profile.name` in their `self`
contexts; `profile = ResolvedProfile(name="mixa",
data={"model": "sonnet"}, source=ProfileSource.PROJECT)`; authored
`WorkflowDocument(prompt="authored")`.

**Input**: `PipelineHooks().amend_workflow(..., profile=profile)`.

**Trace**: one view per tool, each built with the same `profile` object.

**Assertions**: both recorded ids equal `id(profile)`; both names
`"mixa"`; `overlay.provenance == [both tools]` (delivery otherwise
unchanged).

**Sufficiency**: mutual blindness extended to the fact — identical,
read-only, per-tool views.

#### `test_profile_defaults_to_none_and_delivery_is_unchanged` (positive)

**Setup**: one contributing tool capturing `context.profile`; call
`amend_workflow(...)` WITHOUT `profile`.

**Assertions**: captured value `is None`; the overlay equals the
pre-change composition (prompt concat, provenance).

**Sufficiency**: backward compatibility of the surface (default None) —
existing callers and tests keep working.

#### `test_contribution_renders_at_commit_with_profile_content` (positive)

**Setup**: tool contributes `WorkflowDocument(stages={"build":
WorkflowStage(prompt="Model: {{ model }}")}); `profile` as above
(`data={"model": "sonnet"}`).

**Assertions**: `overlay.workflow.stages["build"].prompt ==
"Model: sonnet"`; provenance includes the tool.

**Sufficiency**: the feature's core behavior — the committed document is
the RENDERED document.

#### `test_render_failure_is_a_hard_stop_and_later_tools_never_run` (negative)

**Setup**: tool A contributes `WorkflowDocument(prompt="{{ oops")` (syntax
error); tool B appends to a `witnesses` list; `profile=None` (empty context
does not rescue a syntax error).

**Assertions**: `pytest.raises(ValueError, match=r"pipeline\.amend_workflow:
template error at prompt: TemplateSyntaxError")`; the message names tool A
(`contribution of tool demo failed on`); `witnesses == []`.

**Sufficiency**: ADR decision 2 — render failure is disciplinarily a hook
failure; the first failing tool stops the walk.

#### `test_empty_check_runs_on_the_rendered_document` (edge)

**Setup**: tool contributes `WorkflowDocument(profile="{{ 'x' }}")` — the
only field never counts as content.

**Assertions**: one warning (`tool contributed an empty document;
discarded`), empty provenance, no error (the render itself succeeded).

**Sufficiency**: the check stays presence-based and unchanged, running
AFTER the render.

#### `test_rendered_empty_contribution_still_commits_by_presence` (edge, EC-3)

**Setup**: tool contributes `WorkflowDocument(prompt="{{ missing }}")`;
`profile=None`; authored base `prompt="authored"`.

**Assertions**: provenance includes the tool (the rendered `""` is a
present field → non-empty contribution) while
`overlay.workflow.prompt == "authored"` (the merge drops empty texts).

**Sufficiency**: pins the exact presence/emptiness boundary between the
check and the merge — the subtlest interaction of this change.

#### `test_template_free_composition_is_identical_with_and_without_profile` (edge)

**Setup**: one plain-string contribution; two deliveries — `profile=None`
and `profile=ResolvedProfile(..., data={"model": "sonnet"})`.

**Assertions**: the two `overlay.workflow` documents are `==`.

**Sufficiency**: the byte-identity requirement end to end through the walk.

#### Contract updates (existing tests to EXTEND, not new files)

- `test_amendments.py`: in `test_view_carries_exactly_the_declared_fields`,
  the `field_defaults(WorkflowAmendment)` assertion gains
  `("profile", None)` after `("work", MISSING)` AND the
  `dataclasses.fields` order assertion gains `"profile"` after `"work"`;
  a construction test asserts the default and the explicit pass-through.
- `test_events.py` `test_surface_carries_the_declared_method_signatures`:
  `amend_workflow` parameters gain `"profile"` after `"work"`.

---

### Wiring tests (`tests/pipeline/`)

#### `test_run_form_delivers_loaded_profile_and_renders_contributions`

**Setup**: `project_root`-shaped fixture — pipeline `deploy.yml`, workflow
`deploy.yml` (auto-match) with `profile:` absent, project profile
`.goga/profiles/mixa.yml` (`worker: {agent: codex, model: sonnet}`);
installed tool capturing `context.profile` and contributing
`WorkflowDocument(stages={"build": WorkflowStage(prompt="Use {{ worker.model }}")})`; `AFM_DIR` pinned; `run_pipeline(..., profile="mixa")` (or
monkeypatched `GOGA_PROFILE`), stubbed `run_flow`.

**Trace**: `resolve_workflow → load_workflow` renders the authored file
with the resolved profile → `LoadedWorkflow.profile` is the mixa
`ResolvedProfile` → step 12 passes it → every tool's view reads it → the
contribution renders `Use sonnet`.

**Assertions**: captured `context.profile.name == "mixa"`,
`.source == "project"`; the compiled/overlay workflow carries
`Use sonnet` (via the captured overlay or the stubbed launch inputs).

**Sufficiency**: the run-form wiring — one resolved value feeds the views
and the rendering.

#### `test_run_form_delivers_none_when_no_workflow_resolved`

**Setup**: same project without a workflow file (silent miss), tool
capturing `context.profile`.

**Assertions**: captured `profile is None`; a contributed
`"{{ x }}"` renders empty (empty context) — delivery still runs onto the
empty base.

**Sufficiency**: the no-workflow None carriage of the contract.

#### `test_card_form_delivers_the_same_fact_and_renders_identically`

**Setup**: the same project as the run-form test; call
`describe_pipeline(..., profile="mixa")` with the same contributing tool;
compose the run form's overlay prompt separately.

**Assertions**: the card-form captured `context.profile` equals
(`==` and `.name`) the run form's; the rendered contribution strings are
identical; the card provenance equals the run provenance.

**Sufficiency**: card/run parity — the same fact and the same rendering in
both forms (the new card requirement bullet).

## Additional Instructions for the Implementation Agent

- Implement in the fixed order `workflow → hooks → pipeline` (each cell
  consumes only what the earlier ones provide); the dependency direction
  never reverses.
- `render_contribution.py` gets a module docstring in the cell's one-line
  form ("The ``render_contribution`` routine — …"), Google-style docstring
  sections per `convention`, and no imports beyond `dataclasses`,
  `typing.Any`, and `jinja2.Environment`.
- Do not touch `merge_workflow_overlay`, `render_workflow`, the `emit_*`
  members, the CLI, the action catalog, or the two usage files — they are
  final as they stand.
- Keep the amendment-failure message tails in the established
  `… failed on pipeline.amend_workflow: <reason>` shape so the CLI's
  generic ValueError branch and the existing regex-based tests keep
  matching.
- Update the two contract tests (`test_amendments.py` field list,
  `test_events.py` signature list) in the same change set as the
  signatures they pin.
- After implementation run: `goga lint` (must stay 0 errors), the three
  test packages (`tests/pipeline/workflow`, `tests/pipeline/hooks`, the
  wiring suites), and `ruff`/project lint per `convention`.
