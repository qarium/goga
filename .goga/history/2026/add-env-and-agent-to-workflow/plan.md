# Plan: `add-env-and-agent-to-workflow`

<!-- Topic: `add-env-and-agent-to-workflow` — two new top-level workflow-file
     keys, `agent` and `env`, that override the project configuration's own
     globals for the pipeline run (effective global agent feeding three
     consumers; launch env base merge) and for the build (the 4-layer
     `merge_workflow_build`). Source:
     `.goga/history/2026/add-env-and-agent-to-workflow/design.md`
     (design-review completed — 4 fixes applied, all approved; see its
     execution summary). This plan compiles the design into ralphex-executable
     tasks. -->

## Purpose

Implement the workflow-global run settings end-to-end against the already
applied CODEMANIFEST contracts: workflow-files gain two top-level keys —
`agent` (a single string naming the run's global agent) and `env` (a str→str
map of the run's global environment layer) — validated structurally at parse
time, carried verbatim through every document rebuild (overlay merge, skip
merge), resolved once per pipeline run as the effective global agent (feeding
exactly the per-stage wrapper fallback, the afm configuration write, and the
assistant fallback) and as the launch env base layer (key-wise merge with
`pipeline.env`, workflow wins per key), and layered onto the build
configuration as the middle layer of the 4-layer law
`config < workflow global < workflow build: < CLI`.

After implementation the project provides:

- `goga/pipeline/workflow` — `WorkflowDocument` gains the closing
  `agent: str | None = None` and `env: dict[str, str] | None = None` fields
  (canonical field order: 12 fields); `parse_workflow` extracts and validates
  both keys (`_validate_top_level_agent` mirror helper; `_validate_stage_env`
  reuse), the unknown-key enumeration grows to 12 keys, the empty-workflow
  rule counts both keys and its message grows, the final assembly returns
  them.
- `goga/pipeline/hooks` — `merge_workflow_overlay` final assembly carries
  `agent`/`env` of the base verbatim; the merge never reads a contribution's
  globals.
- `goga/pipeline` — `run_pipeline` resolves the effective global agent once
  per run (new step 14) and feeds the wrapper generation and the afm
  configuration write; the launch env base composes
  `pipeline.env ⊕ workflow global env`; `apply_skip_stages` carries the
  globals verbatim through the skip rebuild; `write_afm_config` /
  `apply_stage_env_wrappers` docstrings document the effective global agent
  (no code change).
- `goga/build` — `merge_workflow_build` replaced wholesale: the 4-parameter
  signature and the 4-layer algorithm (per-pass agent `block or global or
  config`; per-pass env `config ⊕ global ⊕ block`); `build` step 4 layers
  whenever a workflow document is present; `resolve_run_settings` docstring
  notes the layered input.

The most important gaps between contract and code: `WorkflowDocument` ends at
`gates` (10 fields); `_TOP_LEVEL_KEYS` is the 10-key tuple; the overlay and
skip rebuilds construct `WorkflowDocument` without `agent`/`env`; `run_pipeline`
feeds `config.pipeline.agent` directly to the two call sites and composes the
launch base from `pipeline.env` alone; `merge_workflow_build` takes two
parameters and knows only the block-only law; `build.py:407` requires
`loaded.document.build is not None`.

Strategy: leaves-first TDD in the design's mandated order — workflow (model →
parser) → hooks (overlay) → pipeline (skip rebuild → run resolution) → build
(merge rewrite → orchestration) → cross-entity integration proof. Every task
is gated by the Mandatory Rules below. CODEMANIFEST changes and all
`.usages/` docs are **already applied in the working tree** — this plan
touches code and tests only.

## Mandatory Rules

<!-- Extracted verbatim from the project convention `.goga/usages/conventions.md`
     (the `convention` practice, wired into every cell of this feature — for
     working with the codebase, organizing the REPL development cycle,
     debugging and testing, and the test infrastructure), the language rules
     (`goga-cell-python`), the ruff configuration (`pyproject.toml`), and the
     repo gates (`.github/workflows/lint.yml`, `.githooks/`). These rules are
     MANDATORY for every task in this plan. Where a task restates a rule, the
     restatement is a reminder, not a replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`; all code
  executes within a virtualenv — create it if missing.
- **Imports**: relative imports for ALL intra-package references inside
  `goga/` (`from .workflow_stage import WorkflowStage`, `from ..workflow import
  WorkflowDocument`); absolute imports only for stdlib and third-party
  (`yaml`, `logging`). Exception — tests: cross-directory references inside
  `tests/` use absolute imports rooted at the `tests` package.
- **Data models**: stdlib `dataclasses` only (NOT pydantic); model classes use
  `@dataclass(kw_only=True)` with fields in the declared contract order (the
  `workflow_document.py` precedent); `None` only for the explicit absence of
  a value — both new `WorkflowDocument` fields default to `None`.
- **Docstrings**: Google style, MANDATORY for every public function, method,
  and class. First line starts with a capital letter and ends with a period.
  Include `Args` when the function accepts parameters, `Returns` when it
  returns a value, `Raises` when it raises beyond built-in types. Dataclass
  models document every field in the `Args:` block (the CODEMANIFEST property
  annotations are the source text).
- **Code formatting**: inside function and method bodies, separate logical
  blocks by ONE blank line (initialization / conditions and loops / data
  preparation / processing / return).
- **Type hints**: mandatory everywhere (they drive facade signature
  extraction). Allowed shapes: `str`, `int`, `float`, `bool`, `list[T]`,
  `dict[str, T]`, `T | None`. Forbidden: `*args`, `**kwargs`, bare `dict`,
  bare `list`.
- **Naming**: PascalCase classes, snake_case functions/methods/properties/
  modules; private helpers one leading underscore (`_validate_top_level_agent`
  mirrors `_validate_top_level_profile`).
- **Facade**: each cell's `__init__.py` exposes the contract API through
  `__all__`; only identifiers in `__all__` constitute the facade. This
  feature adds NO new exports — every touched entity is already exported;
  `__all__` stays unchanged in all four cells.
- **Logging**: stdlib `logging` (`logger = logging.getLogger(__name__)`);
  structured records with contextual metadata, lowercase messages, stable
  event names. This feature adds NO new log points; the existing
  `logger.debug("pipeline run composed")` payload is unchanged. NEVER print
  or log env values — the constraint extends to the global env everywhere.
- **Error messages are contractual**: the five new structural messages
  ("non-str value in workflow.agent", "non-mapping env in workflow",
  "non-str key in workflow.env", "non-str value in workflow.env.KEY", the
  grown empty-workflow and unknown-key texts) are pinned by the CODEMANIFEST;
  tests pin them with `pytest.raises(..., match=...)` or exact equality.
- **Dependencies**: no new third-party dependencies — `pyyaml`, `jinja2` are
  already pinned in `pyproject.toml`.
- **No public API beyond the contract**: no new helpers on the public surface;
  `_validate_top_level_agent` is private to `parse_workflow.py`.

### Test Writing Rules (strictly per `conventions.md` — Testing)

- **Tools**: pytest (runner), ruff (lint + format of test code), pytest-cov
  (coverage). Test libraries live in `pyproject.toml`
  `[project.optional-dependencies]` under `test` (already pinned:
  `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0`).
- **Structure mirrors source directly**: `goga/pipeline/workflow/
  parse_workflow.py` → `tests/pipeline/workflow/test_parse_workflow_*.py`
  suites; `goga/pipeline/hooks/overlay.py` →
  `tests/pipeline/hooks/test_overlay.py`; `goga/pipeline/apply_skip_stages.py`
  → `tests/pipeline/test_apply_skip_stages.py`; `goga/pipeline/run_pipeline.py`
  → `tests/pipeline/test_run_pipeline.py`; `goga/build/workflow_build.py` →
  `tests/build/test_workflow_build_merge_*.py`; `goga/build/build.py` →
  `tests/build/test_build.py`. Every test directory already carries
  `__init__.py`.
- **Fixtures**: local fixtures in `tests/<package>/conftest.py`, shared
  fixtures in `tests/conftest.py`. Available shared infrastructure (reused,
  never duplicated): `is_kw_only_dataclass` (`tests/conftest.py:85`); the
  `config_path` fixture (`tests/pipeline/conftest.py:110`); the
  `_in_container_run_context` autouse fixture (`tests/pipeline/conftest.py:57`);
  the `_patch_seams` harness of `tests/pipeline/test_run_pipeline.py:1395`
  (the recording `write_afm_config` spy and mocked `run_flow` seams — reuse
  them for the run-level tests); the `load_workflow` chain fixtures of
  `tests/pipeline/workflow/conftest.py`.
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`;
  grouping `class Test<Component>:`; self-documenting test names; keep
  comments minimal.
- **Test types**: Unit — every public function/method/class, main scenario and
  typical data. Edge cases — empty inputs (`""`, `{}`, `[]`, `None`, absent
  keys), boundary values, invalid types, expected exceptions via
  `pytest.raises`. Integration — only for interaction between
  modules/packages (the chain and orchestration scenarios of Task 9).
- **Boundary tests**: the non-str `agent` value domain uses
  `@pytest.mark.parametrize` with a table covering every invalid form
  (`5`, `[claude]`, `{n: c}`, YAML null `agent:`).
- **Mocks**: pure logic — NO mocks (parser, merge routines are mock-free);
  file I/O — the `tmp_path` fixture exclusively; subprocesses/external
  boundaries — `mock.patch` at the import point (the run-pipeline seams).
  Mock only at external boundaries; keep business logic tests mock-free.
- **Golden values are grounded, never recalled**: every pinned golden in this
  plan (the exact structural messages, the 12-key enumeration, the
  field-order list) was verified by the design against the live sources; if
  an assertion disagrees with a live REPL run during implementation, the live
  run wins and the disagreement is reported — never silently "aligned".
- **Existing tests that pin the old surface are adapted in the same change**
  (the registry in Task 3 and Task 7): the exact-equality empty-workflow pins
  and the field-order pin are HARD-FAILING updates; the substring (`in`)
  valid-keys asserts keep passing (strengthening to the full 12-key fragment
  is recommended, not required).

### Linter and Formatter Enforcement (all development stages and local commits)

The following gates are MANDATORY at the end of EVERY task and BEFORE EVERY
local commit, across all development stages. A failing gate is an actionable
defect, never acceptable noise. Local git hooks do NOT enforce formatting
(only the commit-msg / pre-push Co-Authored-By policy does) — the author runs
the formatter deliberately:

1. `ruff check goga/ tests/` — zero violations (the CI gate of
   `.github/workflows/lint.yml`; rule set per `pyproject.toml`: E, W, F, I,
   N, UP, B, SIM, PL, PLR, C4, DTZ, PT, ARG, RUF, PTH, C90; line length 120;
   target py310; mccabe max-complexity 10; the tests per-file-ignores apply).
2. `ruff format --check goga/ tests/` — zero reformattings; run
   `ruff format goga/ tests/` when it reports diffs.
3. `goga lint` — cell-level lint, **0 errors over 93 cells** (verified green
   on the pre-change tree during planning).
4. Focused tests green, then `pytest tests/ -x` green (the full battery — the
   existing suites stay green except the deliberate registry adaptations
   listed in the tasks).
5. Facade import checks green (see Validation Commands).
6. **Commit policy**: commit only with all gates green; commit messages MUST
   NOT contain `Co-Authored-By:` trailers (`.githooks/commit-msg` and
   `pre-push` reject them).
7. `CODEMANIFEST` files are READ-ONLY for the implementer — the contract
   changes are already applied in the working tree; if code does not match
   the contract, fix the code, never the contract.

### REPL Cycle Rules (continuous interactive evaluation, hot reloading, migration to source)

The `convention` practice is wired into every cell of this feature for
"Organizing the REPL development cycle". Every coding task in this plan
follows the same loop:

1. **Virtualenv first**: all code executes inside a virtualenv — create it if
   missing. No `.venv` exists in the workspace right now and the system
   interpreter (`/opt/goga/bin/python3`, Python 3.12.16) has no pytest/ruff —
   Task 1 bootstraps the environment (`python3 -m venv .venv` +
   `.venv/bin/pip install -e ".[test]"`) and verifies the baseline gates
   green BEFORE any change; every subsequent probe, test run, and lint run
   executes inside it (`.venv/bin/python`, `.venv/bin/pytest`,
   `.venv/bin/ruff`).
2. **Probe before writing**: verify each non-trivial behavior interactively
   against real inputs BEFORE the verified snippet is written into a source
   file or a golden is pinned into a test. The probes of this feature:
   construct `WorkflowDocument(agent="claude", env={"A": "1"})` and confirm
   the kw-only closing field order (Task 2); run live
   `parse_workflow("agent: 5\nprompt: hi\n")`-style calls and confirm the
   EXACT message texts before pinning them (Task 3); drive one live
   `merge_workflow_overlay` quadruple (base + a contribution with clashing
   globals) and confirm the base globals survive and the contribution's are
   discarded (Task 4); confirm the skip rebuild keeps the globals (Task 5);
   evaluate the launch-base dict comprehension `{**config.pipeline.env,
   **(workflow_env or {})}` and the effective-agent cascade against real
   values (Task 6); drive `merge_workflow_build` with the design's four
   scenarios and confirm the per-pass outcomes and input purity before
   writing the tests (Task 7); confirm the widened step-4 condition reaches
   the merge with `build=None` (Task 8).
3. **Hot feedback after every edit**: immediately re-run the focused test
   file and the facade import check in the same virtualenv; iterate in small
   steps. A long-lived REPL session re-imports edited modules
   (`importlib.reload` or a fresh `python -c`) — never trust stale module
   state as evidence; module-level tuples (`_TOP_LEVEL_KEYS`) and the
   dataclass field registry demand a fresh interpreter after every edit.
4. **Migrate verified code to source files**: REPL-verified snippets are
   migrated into the target `location` file with type hints, Google
   docstrings, relative imports, and convention formatting; REPL scratch
   never ships and is never referenced by source.
5. **Close the loop per task**: probe → implement (migrate) → focused tests
   → full battery → lint/format gates → commit (gates green).

**The REPL never replaces the TDD gates**: contract tests are still written
FIRST (expected to fail) and logic tests AFTER the implementation — the REPL
shortens the debug loop between them (each task's STEP 2 embeds the probes).

## Context

### Entity Interaction and Data Flow (from the design, verbatim)

```
workflow-file (agent:, env:)
      │ load_workflow: read → peek profile (raw text) → render (jinja2, whole file)
      ▼
parse_workflow ──► WorkflowDocument(prompt, stages, …, gates, agent, env)
      │                          ▲                        ▲
      │                          │ agent/env verbatim     │ agent/env verbatim
      │                          │ (rebuilt document)     │ (rebuilt document)
      │                merge_workflow_overlay       apply_skip_stages
      │                (hooks; base-only globals)   (CLI -s skip merge)
      ▼                          │                        │
run_pipeline ◄── overlay.workflow ┴────────────────────────┘
      │ step 14: effective global agent =
      │     overlay.workflow.agent ?? config.pipeline.agent      (one value per run)
      ├──► apply_stage_env_wrappers(…, global_agent=effective)  (exec fallback tier)
      ├──► write_afm_config(agent=effective, flow, workflow)    (client command
      │                                                            + assistant fallback)
      │ step 20: launch env base = pipeline.env ⊕ overlay.workflow.env (key-wise,
      │          workflow wins per key); CLI entries above; engine keys dropped
      └──► run_flow(env=launch_layer)

build (build.py step 4, when a workflow document is present):
      loaded.document ──► merge_workflow_build(config.build,
                                               document.build | None,
                                               document.agent,
                                               document.env)
                              │ per pass (root/review/additional):
                              │   agent = block ?? global ?? config
                              │   env   = config ⊕ global ⊕ block   (key-wise)
                              ▼
                        resolve_run_settings(layered BuildConfig, cli_options)
                              │ cascade: review ?? layered root; additional ?? review
                              ▼
                        RunSettings → per-role closure wrappers → ralphex
```

Data flows (from the design, verbatim):

1. **Parse flow** — `load_workflow` renders the whole file (the two keys ride
   the rendering like every other byte; the profile peek still reads raw
   text, so a value materializing only through rendering activates nothing),
   `parse_workflow` validates structurally and builds
   `WorkflowDocument(agent=…, env=…)` (None when absent/empty; an empty env
   map builds `env=None`).
2. **Amendment flow** — `apply_skip_stages` rebuilds the document carrying
   the globals verbatim; `PipelineHooks.amend_workflow` →
   `merge_workflow_overlay` rebuilds again, still carrying the base's
   globals verbatim; contributions' globals are never read. The effective
   workflow of the run is `overlay.workflow` (the passthrough when the layer
   is off).
3. **Run flow** — after `compile_flow` (consumes neither key), `run_pipeline`
   resolves the effective global agent once (step 14) and feeds it to the
   wrapper generation and the afm configuration write; the launch env base
   composes `pipeline.env` with the workflow global env before the CLI
   entries layer above and the engine-key drop (step 20).
4. **Build flow** — `build` step 4 overlays the globals and the `build:`
   block onto `config.build` via the new `merge_workflow_build` signature
   whenever a workflow document is present; `resolve_run_settings` consumes
   the layered value; the agent-inheritance cascade runs from the layered
   root.

### Contract Surface

**Entity: `WorkflowDocument`** (cell `goga/pipeline/workflow` — CHANGED,
`location: workflow_document.py`)
- Type: data model (pure data; no validation, no resolution)
- Declared signature (CODEMANIFEST, exact):
  `WorkflowDocument(prompt: str | None = None, stages: dict[str, WorkflowStage] | None = None, extend: dict[str, WorkflowExtendStage] | None = None, memory: WorkflowMemory | None = None, profile: str | None = None, build: WorkflowBuild | None = None, assistants: dict[str, WorkflowAssistant] | None = None, delegation: WorkflowDelegation | None = None, repeat: WorkflowRepeat | None = None, gates: WorkflowGates | None = None, agent: str | None = None, env: dict[str, str] | None = None)`
- Facade obligation: importable from `goga.pipeline.workflow` (already in
  `__all__`; no facade change)
- New properties: `agent -> str | None` (the workflow-global agent name — the
  global run-settings layer every consumer resolves ahead of the
  configuration's pipeline agent; None when the key is absent or empty) and
  `env -> dict[str, str] | None` (the workflow-global environment layer;
  None when the key is absent — an empty map equals absence)
- Semantic requirements: the two fields close the canonical order —
  `prompt, stages, extend, memory, profile, build, assistants, delegation,
  repeat, gates, agent, env` (12 fields, fixed); the empty-workflow rule
  counts both keys as content (`profile` never counts); consumers treat the
  document as read-only (unchanged constraint)
- Implementation (design, verbatim):

  ```python
  agent: str | None = None
  env: dict[str, str] | None = None
  ```

  after `gates`, with `Args:`-docstring entries mirroring the CODEMANIFEST
  property annotations.

**Entity: `parse_workflow`** (cell `goga/pipeline/workflow` — CHANGED,
`location: parse_workflow.py`)
- Type: routine `parse_workflow(text: str) -> workflow: WorkflowDocument`
- Facade obligation: already exported; signature unchanged
- Changed behavior (CODEMANIFEST Algorithm steps 4, 5, 7, 8, verbatim):
  - step 4, two new extraction branches:
    `agent`: if present, must be a str; otherwise raise a structural error
    "non-str value in workflow.agent". An empty or whitespace-only value
    normalizes to None. `env`: if present, must be a dict of str→str; a
    non-dict value raises "non-mapping env in workflow"; a non-str key
    raises "non-str key in workflow.env"; a non-str value raises
    "non-str value in workflow.env.KEY". An empty map equals absence —
    build with env=None
  - step 5: unknown-key message enumerates the 12 valid keys
    (prompt, stages, extend, memory, profile, build, assistants,
    delegation, repeat, gates, agent, env)
  - step 7: the empty-workflow condition grows `agent is None` and
    `env is None`; the message grows ", the agent key, or the env block"
  - step 8: return the document with the two global keys (the authored
    agent, or None; the authored env map, or None)
- Algorithm (design, verbatim):

  ```
  1. In _extract_top_level's per-key loop, extend the dispatch:
     - key == "agent": agent = _validate_top_level_agent(value)
       → non-str: raise WorkflowSyntaxError("non-str value in workflow.agent")
       → empty/whitespace-only: agent = None
       → else: agent = value
     - key == "env": env = _validate_stage_env("workflow", value)
       → non-dict: "non-mapping env in workflow"
       → non-str key: "non-str key in workflow.env"
       → non-str value: "non-str value in workflow.env.KEY"
       → empty map: env = None
  2. _TOP_LEVEL_KEYS = (..., "repeat", "gates", "agent", "env")   # 12 keys, join
     feeds the unknown-key message verbatim
  3. Unpack the 12-tuple; empty-workflow condition += (agent is None) and
     (env is None); message += ", the agent key, or the env block"
  4. Return WorkflowDocument(..., gates=gates, agent=agent, env=env)
  ```

- Constraints: do not resolve agent to a wrapper path, merge env with any
  other layer, or apply either global anywhere here — the consumers own
  every resolution law; the cell stays declarative
- Errors: `WorkflowSyntaxError` with the exact messages above (contract-
  pinned text; `_validate_stage_env`'s scope-interpolated messages are
  byte-identical to the contract — no new env helper)
- Edge cases: `agent: ""` / `agent: "   "` → None (absence; the `profile`
  law); `env: {}` → None (the stage-env law, NOT the assistant
  explicit-clear law); `agent: 5`, `agent: [claude]`, `agent: {name: claude}`
  → structural error; YAML null `agent:` → structural error (an empty key is
  NOT absence — the `profile:` law); a `agent:`-only or `env:`-only workflow
  is valid; a `profile:`-only workflow still raises

**Entity: `merge_workflow_overlay`** (cell `goga/pipeline/hooks` — CHANGED,
`location: overlay.py`)
- Type: routine `merge_workflow_overlay(base: WorkflowDocument | None, contributions: list[ToolContribution]) -> overlay: WorkflowOverlay`
- Facade obligation: already exported; signature unchanged
- Changed behavior (CODEMANIFEST Algorithm step 8 + one requirement + one
  constraint, verbatim): "the final document assembly carries the profile,
  build, agent, and env fields of `base` verbatim (exactly as memory
  survives the rebuild)"; requirement — "the rebuilt `WorkflowDocument`
  preserves the global run settings: the agent and env fields of the base
  ride the rebuild verbatim — a rebuild that drops them would silently
  revert a tool-amended run to configuration-level globals; a tool-supplied
  global never reaches the final document (the merge reads the globals of
  the base only)"; constraint — "Do not read the agent or env fields of any
  contribution document — the globals are author-territory; only the base
  carries them into the overlay"
- Algorithm (design, verbatim):

  ```
  1. Final assembly (step 8) adds two kwargs:
     agent=base.agent if base is not None else None
     env=base.env if base is not None else None
     (same objects — verbatim, never rebuilt; exactly as profile/build/memory)
  2. No other change: no merge helper reads document-level globals; the
     constraint "never read a contribution's globals" holds by construction
  ```

- Edge case: empty base + contributions → workflow None (unchanged) or a
  contributed document (the contributions' globals are still not read — the
  workflow-level assembly reads only `base`)

**Entity: `run_pipeline`** (cell `goga/pipeline` — CHANGED,
`location: run_pipeline.py`)
- Type: routine; facade already exported; signature unchanged
- Changed behavior (CODEMANIFEST Algorithm steps 14 and 20, verbatim):
  - step 14 (NEW): "Resolve the effective global agent: the agent field of
    the overlay workflow document when it carries one, otherwise the
    effective configuration's pipeline.agent. The resolved value feeds the
    per-stage wrapper generation (its exec fallback), the afm configuration
    write (the client command and the assistant fallback), and nothing else"
  - step 20: "apply the decoded entries above the effective launch env base
    — the key-wise merge of the effective pipeline.env task env layer with
    the overlay workflow's global env (a workflow key overrides the
    same-named configuration key, untouched configuration keys survive)"
  - Requirements: "The effective global agent resolves once per run from the
    overlay workflow document's agent field, falling back to the effective
    pipeline.agent; it feeds exactly the three consumption points and
    nothing else; with the workflow layer off or no workflow resolved the
    effective pipeline.agent holds the role"; "The launch env base is the
    key-wise merge of pipeline.env with the workflow global env (workflow
    wins per key, config keys survive); CLI entries stay above;
    engine-variable keys still drop silently"
- Algorithm (design, verbatim):

  ```
  1. Step 14 (after compile_flow, before the wrapper applications):
     workflow_agent = overlay.workflow.agent if overlay.workflow is not None else None
     effective_agent = workflow_agent if workflow_agent is not None
                       else config.pipeline.agent
  2. Step 15 call: apply_stage_env_wrappers(..., global_agent=effective_agent, ...)
     Step 17 call: write_afm_config(effective_agent, flow_doc, overlay.workflow)
  3. Step 20:
     workflow_env = overlay.workflow.env if overlay.workflow is not None else None
     base = {**config.pipeline.env, **(workflow_env or {})}
     launch_layer = {k: v for k, v in {**base, **payload}.items()
                     if k not in _ENGINE_ENV_KEYS}
     (GOGA_PROFILE added afterwards from the resolved profile, as today)
  4. Renumber the step comments to the CODEMANIFEST's 1..24 and update the two
     inline comments that said "effective pipeline agent"
  ```

- Edge cases: `no_workflow` / silent miss / no file → `overlay.workflow` is
  None or its agent/env None → configuration values feed the same points
  (behavior byte-identical to today); a workflow env key colliding with the
  engine set (e.g. `GOGA_WORKFLOW`) drops silently with the same
  comprehension
- Constraints: no new environment reads (the four-read law is unchanged); no
  new error path (boundaries unchanged)

**Entity: `write_afm_config`** (cell `goga/pipeline` — CHANGED, semantics
only, `location: afm_config.py`)
- Signature unchanged: `write_afm_config(agent: str | None, flow: FlowDocument | None = None, workflow: WorkflowDocument | None = None) -> config_path: Path`
- Parameter semantics (CODEMANIFEST, verbatim): "`agent`: the effective
  global agent — the workflow global agent of the effective workflow when it
  carries one, otherwise the authored pipeline.agent as amended by the
  config delivery; None when neither resolves"
- Code change: NONE. The assistant fallback at `afm_config.py:187`
  (`target_agent = declaration.agent if declaration.agent is not None else
  agent`) already implements the new law. Docstring alignment only (the
  `agent` parameter description).

**Entity: `apply_stage_env_wrappers`** (cell `goga/pipeline` — CHANGED,
semantics only, `location: stage_env_wrappers.py`)
- Signature unchanged: `apply_stage_env_wrappers(stages: list[FlowStage], workflow: WorkflowDocument | None, global_agent: str | None, flow_path: Path) -> stages: list[FlowStage]`
- Parameter semantics (CODEMANIFEST, verbatim): "`global_agent`: the
  effective global agent — the workflow global agent of the effective
  workflow when it carries one, otherwise the effective pipeline agent"
- Code change: NONE. Docstring alignment only (`stage_env_wrappers.py:147`
  and the `apply_gate_env_wrappers` counterpart at `:495` — the "effective
  global pipeline agent" wording gains the workflow-global source).

**Entity: `apply_skip_stages`** (cell `goga/pipeline` — CHANGED,
`location: apply_skip_stages.py`)
- Signature unchanged: `apply_skip_stages(workflow: WorkflowDocument | None, skip_stages: list[str]) -> workflow: WorkflowDocument | None`
- Changed behavior (CODEMANIFEST Algorithm step 4, verbatim): the rebuild
  carries `agent = the agent field of workflow when workflow is not None
  else None; env = the env field of workflow when it is not None else None
  — carried verbatim`; requirements — "The global run settings (agent, env)
  of the input workflow survive the rebuild verbatim — a rebuild that drops
  them would silently revert a skip-driven run to configuration-level
  globals"; "When `workflow` is None and `skip_stages` is non-empty — the
  constructed `WorkflowDocument` carries agent None and env None"
- Algorithm (design, verbatim):

  ```
  1. Step 4 rebuild adds:
     agent=workflow.agent if workflow is not None else None
     env=workflow.env if workflow is not None else None
  2. Docstring enumeration of the synthesized-default document gains agent/env None
  ```

**Entity: `merge_workflow_build`** (cell `goga/build` — REPLACED WHOLESALE,
`location: workflow_build.py`)
- Declared signature (CODEMANIFEST, exact):
  `merge_workflow_build(config: BuildConfig, build_block: WorkflowBuild | None, global_agent: str | None = None, global_env: dict[str, str] | None = None) -> config: BuildConfig`
- Facade obligation: already exported; re-export unchanged
- Responsibility (CODEMANIFEST, verbatim): "Overlay the workflow layers onto
  the effective build configuration: the two global run settings as the
  middle layer and the six-field build block above them — producing a NEW
  BuildConfig where each pass agent resolves build-block > global >
  configuration, each pass env merges key-wise configuration < global <
  block, and absent values at every layer never override"
- Algorithm (design, verbatim):

  ```
  def merge_workflow_build(config, build_block, global_agent=None, global_env=None):
    1. pass_agent(block_value, config_value) =
          block_value or global_agent or config_value
       (truthiness cascade: an authored empty-string block agent falls through
       exactly as the block-only law (`block or config` today); the workflow
       global and every configuration agent field are normalized to
       None-or-non-empty by the parser/loader, so `or` equals presence for
       them and the parity requirement holds at this boundary too)
    2. Root:  agent = pass_agent(block?.agent, config.agent)
              env   = _merge_env(config.env, global_env, block?.env)
    3. Review: block fields via block or None; layered review agent/env likewise
       (config side from config.review when present)
    4. Additional: likewise over config.review.additional
    5. Construction triggers (well-formed layered configuration):
       - config.review is None AND any of {block.review_agent, block.review_env,
         block.review_additional_agent, block.review_additional_env, global_agent,
         global_env} is not None → new ReviewConfig(agent=layered review agent,
         env=layered review env (global ⊕ block review env; {} when both absent —
         but then only agent/global triggered), skip/roles/base_ref/strategy/
         finalize/session knobs None, max_iterations None,
         additional=_merge_additional(None, …))
       - additional is None AND any of {block.review_additional_agent,
         block.review_additional_env, global_agent, global_env} is not None →
         new AdditionalReviewConfig(agent=layered additional agent,
         env=_merge_env({}, global_env, block?.review_additional_env),
         patience=None, max_iterations=None)
    6. Every other BuildConfig field passes through verbatim (max_iterations,
       session_timeout, idle_timeout, wait, prompts_dir, agents_dir, proxy, hosts;
       review.skip/roles/base_ref/strategy/finalize/session knobs/max_iterations
       verbatim when review present)
    7. Return the new BuildConfig — inputs unmutated (frozen models: always new)
  ```

  `_merge_env(base, *overlays)` gains a variadic form (or is simply chained
  twice): later layers win per key; `None` overlays are skips.
- Requirements (CODEMANIFEST, verbatim): pure — new `BuildConfig` and new
  nested models, inputs unmutated; an absent value at any layer (None block
  field, None global, None config field) never overrides; `config` is always
  a non-None `BuildConfig` (the no-build-section guard lives in `build`
  step 4 before the call); the construction triggers when `config.review`
  is None and any review-sourced value would be set (a block review field,
  or a global reaching the review pass); with `global_agent` and
  `global_env` both None the layering matches the block-only overlay exactly
- Constraints: do not apply CLI values here (CLI applies at the settings
  resolution, preserving `config < workflow global < workflow build: < CLI`);
  do not resolve wrappers or validate agents; do not inherit configuration
  env between passes — the global env is the only cross-pass base
- Edge cases (design, verbatim):
  - `build_block=None` + globals → the globals still layer (root agent/env;
    review construction when a global reaches the review pass)
  - `build: {agent: ""}` (or `review.agent: ""`, `review.additional.agent:
    ""`) — the build-block agent fields are NOT empty-normalized at parse,
    so an authored empty string falls through to the global, else the
    configuration field, exactly as the block-only law does today
  - both globals None → field-identical to the block-only overlay (parity
    pinned by a test); with `build_block=None` too → field-identical copy of
    the input
  - config review agent set + global set (no block) → global WINS
    (block > global > config)
  - the global env is the ONLY cross-pass env base: config root env never
    reaches review/additional (secret-safety invariant preserved)

**Entity: `build`** (cell `goga/build` — CHANGED, `location: build.py`)
- Signature unchanged: `build(plan: str, config: ProjectConfig, cli_options: dict) -> exit_code: int`
- Changed behavior (CODEMANIFEST Algorithm step 4, verbatim): "Layer the
  build settings when a workflow is in effect: `merge_workflow_build` of the
  effective config.build with the document's build block (None when the
  document carries no block) and the document's global agent and env — the
  layered BuildConfig feeds every downstream step; the layering runs
  whenever the loaded document is present (the globals apply with no build
  block too)"
- Algorithm (design, verbatim):

  ```
  1. Guard (unchanged): config.build None → clean logged error, exit 1
  2. NEW condition: if loaded is not None:
       build_config = merge_workflow_build(
           build_config,
           loaded.document.build,      # None is legal now
           loaded.document.agent,
           loaded.document.env,
       )
     (replaces `if loaded is not None and loaded.document.build is not None:`)
  3. Comment updated: the layering runs whenever a document is present — the
     globals apply with no build block too
  ```

- Requirement (CODEMANIFEST, verbatim): "Workflow layering composes
  config < workflow global < workflow build: < CLI at the resolution point;
  an absent value at every layer never overrides; env maps merge key-wise"

**Entity: `resolve_run_settings`** (cell `goga/build` — docstring only,
`location: run_settings.py`)
- Signature unchanged. No algorithm change. Docstring alignment (CODEMANIFEST
  opening note, verbatim): "The `config` parameter is the LAYERED effective
  build configuration: when a workflow is in effect, the caller has already
  overlaid its global run settings and build block via
  `merge_workflow_build`; this routine consumes the layered value and
  applies no layering itself"

### Re-exports

None — no re-export blocks are added or changed by this feature. All touched
entities are already importable from their cell facades.

### Usages Context

- **`convention`** — `.goga/usages/conventions.md`: Python code rules
  (kw_only dataclasses, relative imports, Google docstrings, blank-line
  blocking), mirror-structured tests (`tests/<pkg>/test_<module>.py`), pytest
  naming `test_<what>_<scenario>`, the validation-command table. Wired into
  every changed cell; applied by the Mandatory Rules above and every task.
- **`jinja2`** — `.goga/usages/cooks/jinja2.md` (workflow cell): the
  whole-file rendering law (render before parse). The two keys ride the
  rendering like every other byte; the profile peek reads raw text, so a
  value materializing only through rendering activates nothing. No code
  change; one chain-level test pins a profile-rendered global env value
  reaching the document.
- **`afm`** — `.goga/usages/cooks/afm.md` (pipeline cell): the afm
  configuration-file contract (client command, static fields, collaboration
  section). Unchanged contract; only the `agent` parameter's source changes.
- **`ralphex`**, **`agent-wrappers`** — `.goga/usages/cooks/*` (build cell):
  unchanged consumption; the layered values flow through the existing
  `resolve_run_settings` → `write_role_env_wrappers` machinery.

### Imported Usages

- **`extra-env-carriage`** from `goga/docker` —
  `goga/docker/.usages/extra-env-carriage.md`: the env ladder's "task env
  layer (effective)" now composes as `pipeline.env ⊕ workflow global env` in
  the pipeline domain and as the layered pass env in the build domain; the
  practice's own example stays valid — no edit needed.
- **`resolve-wrapper-path`** from `goga/agents` —
  `goga/agents/.usages/resolve-wrapper-path.md`: unchanged; one more
  caller-side source for the agent name (`run_pipeline` step 14).
- **`parse-workflow`**, `load-workflow`, `profiles`, `assistants`, `memory`
  from `goga/pipeline/workflow`: read; `parse-workflow.md` already documents
  the new keys (updated by the apply stage, verified consistent).
- `per-tool-delivery`, `declaring-actions`, `registering-hooks` from
  `goga/hooks`; `checkpoints` from `goga/pipeline/hooks`;
  `compile-flow`/`collaboration-emission` from `goga/pipeline/compiler`;
  `project-configuration` from `goga/config`; `run-flow` from `goga/afm`;
  `topic-paths`/`topic-statuses` from `goga/history`;
  `ensure-in-docker`/`home-profiles-carriage` from `goga/docker` — all
  consumed exactly as before; no law of any of them changes.

### Local Usages

All five changed `.usages/` files are ALREADY UPDATED in the working tree by
the apply stage (verified against the final contracts during design review —
status: current). No creation or edit tasks; each cell task carries a
verification checkbox that the implementation keeps them truthful.

- `goga/pipeline/workflow/.usages/parse-workflow.md` — new "The global run
  settings" section; 12-key enumeration; empty-workflow rule text. Related:
  `parse_workflow`, `WorkflowDocument`. Verified in Task 3.
- `goga/pipeline/hooks/.usages/checkpoints.md` — overlay bullet: globals ride
  verbatim; tools can neither supply nor override them. Related:
  `merge_workflow_overlay`. Verified in Task 4.
- `goga/pipeline/.usages/run-pipeline.md` — "Workflow-global run settings"
  section; afm-configuration and env-ladder sections updated. Related:
  `run_pipeline`. Verified in Task 6.
- `goga/pipeline/.usages/per-stage-env.md` — the global env layers reach
  every stage ambiently through the afm launch layer. Verified in Task 6.
- `goga/build/.usages/workflow-layering.md` — 4-layer order section with the
  per-pass agent/env resolution laws (states block > global > config).
  Related: `merge_workflow_build`, `build`. Verified in Task 7.

No new `.usages/` files (no new functional domain); no CODEMANIFEST `Usages`
references point at a cell's own `.usages/` files (rule respected).

### External Dependencies

- `pyyaml` (pinned `>=6.0`) — `yaml.safe_load`; already used by
  `parse_workflow`.
- `jinja2` (pinned `>=3.1`) — whole-file rendering; unchanged code path.
- Test tooling: `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0` from
  `[project.optional-dependencies] test`.
- No new third-party dependencies.

## Facts

- The four changed CODEMANIFESTs and five `.usages/` docs are already
  materialized in the working tree (git status: modified); `goga lint` is
  green — 93 cells, 0 errors (re-verified during planning).
- `goga/pipeline/workflow/workflow_document.py` — `WorkflowDocument`
  currently ends at `gates: WorkflowGates | None = None` (10 fields:
  prompt, stages, extend, memory, profile, build, assistants, delegation,
  repeat, gates).
- `goga/pipeline/workflow/parse_workflow.py` — `_TOP_LEVEL_KEYS`
  (`parse_workflow.py:24`) is the 10-key tuple; the empty-workflow rule
  (lines ~262–278) counts nine content sources and its message ends "…
  the repeat block, or the gates block"; `_validate_top_level_profile`
  (line 427) is the scalar-law mirror pattern for the new agent helper;
  `_validate_stage_env` (line 1214) exists with scope-interpolated messages;
  the final `WorkflowDocument(...)` assembly (line 281) passes ten kwargs;
  `_extract_top_level` returns a 10-tuple unpacked at line ~238.
- `goga/pipeline/hooks/overlay.py` — the final assembly (line 619)
  constructs `WorkflowDocument(...)` with ten kwargs (profile/build carried
  via `base.X if base is not None else None`); no merge helper reads
  document-level globals.
- `goga/pipeline/run_pipeline.py` — current step comments run 1–2, 3–5, 6–7,
  8, 9, 10, 11, 12, 13, 14, 14b, 15, 16, 16a, 17, 18, 19, 20, 21, 22–23
  (old numbering); `apply_stage_env_wrappers(flow_doc.stages,
  overlay.workflow, config.pipeline.agent, flow_path)` at line 472;
  `write_afm_config(config.pipeline.agent, flow_doc, overlay.workflow)` at
  line 499; the launch base at line 552 is
  `{**config.pipeline.env, **payload}` filtered by `_ENGINE_ENV_KEYS`
  (line 58); `GOGA_PROFILE` added after (line 556).
- `goga/pipeline/apply_skip_stages.py` — the rebuild (line 96) passes ten
  kwargs; a None workflow synthesizes the document with the per-field
  `workflow.X if workflow is not None else None` pattern.
- `goga/pipeline/afm_config.py` — the assistant fallback at line 187 is
  `target_agent = declaration.agent if declaration.agent is not None else
  agent`; only the `agent` parameter docstring needs the new source text.
- `goga/pipeline/stage_env_wrappers.py` — `global_agent` docstrings at lines
  147 and 495 say "effective global pipeline agent"; the code path
  (lines 165–166) is source-agnostic.
- `goga/build/workflow_build.py` — `merge_workflow_build(config,
  build_block)` takes TWO parameters; `_merge_env(base, overlay)` is
  two-layer; `_merge_review`/`_merge_additional` implement the block-only
  law (`block or config`); the root assembly passes every other field
  through verbatim.
- `goga/build/build.py` — step 4 condition at lines 407–408:
  `if loaded is not None and loaded.document.build is not None:`.
- `goga/build/run_settings.py` — the `resolve_run_settings` docstring
  already names the layered input, but only for the `build:` overlay; it
  does not yet name the global run settings layer or
  `merge_workflow_build` (the CODEMANIFEST opening note wording).
- Test infrastructure: `tests/pipeline/workflow/` carries the parse suites
  (`test_parse_workflow_{contract,logic,memory,gates,assistants,repeat}.py`,
  `test_workflow_document_contract.py`); `tests/pipeline/hooks/test_overlay.py`;
  `tests/pipeline/test_apply_skip_stages.py`; `tests/pipeline/
  test_run_pipeline.py` with the `_patch_seams` harness at line 1395;
  `tests/build/test_workflow_build_merge_{contract,logic}.py`,
  `tests/build/test_build.py`. Every test dir has `__init__.py`.
- Existing exact pins that MUST be updated with the new texts (verified
  against the files): `test_workflow_document_contract.py` field-order list
  (line ~64); `test_parse_workflow_memory.py` exact empty-workflow equality
  (~378) and substring valid-keys (~235); `test_parse_workflow_logic.py`
  empty-workflow equality (~1353) and substring (~581);
  `test_parse_workflow_gates.py` substring (~297);
  `test_parse_workflow_contract.py` substring (~229);
  `test_parse_workflow_assistants.py` empty-workflow message (~82);
  `test_parse_workflow_repeat.py` empty-workflow message (~87);
  `tests/build/test_workflow_build_merge_contract.py` signature pin
  `["config", "build_block"]` (line 26).
- Environment: no `.venv` in the workspace; the system interpreter
  (`/opt/goga/bin/python3`, Python 3.12.16) has neither pytest nor ruff —
  the environment must be bootstrapped (Task 1).
- CI gates: `.github/workflows/lint.yml` runs `ruff check goga/ tests/` and
  `ruff format --check goga/ tests/`; `.github/workflows/tests.yml` runs the
  pytest battery. `.githooks/commit-msg` and `.githooks/pre-push` reject
  `Co-Authored-By:` trailers.
- Untouched by contract (verified zero-diff in the apply stage, keep
  untouched): `goga/pipeline/compiler`, `goga/agents/wrapper`, `goga/config`,
  `goga/commands/*`.

## Gap Analysis

- Missing model fields: `WorkflowDocument.agent` / `.env` (workflow cell).
- Missing parser support: the two `_extract_top_level` branches, the
  `_validate_top_level_agent` helper, the 12-key `_TOP_LEVEL_KEYS`, the
  empty-workflow condition/message extension, the two final-assembly kwargs.
- Missing verbatim carriage: `merge_workflow_overlay` final assembly and
  `apply_skip_stages` rebuild both construct the document WITHOUT the two
  globals — every rebuild silently drops them (the exact regression the
  contracts name).
- Missing run resolution: `run_pipeline` feeds `config.pipeline.agent`
  directly into `apply_stage_env_wrappers` (line 472) and `write_afm_config`
  (line 499) — no effective-agent resolution; the launch base (line 552)
  ignores `overlay.workflow.env`; the step comments carry the old numbering.
- Docstring drift: `write_afm_config.agent`, `apply_stage_env_wrappers.
  global_agent` (×2 sites), `resolve_run_settings` opening note — all
  describe the pre-change sources.
- Wholesale replacement gap: `merge_workflow_build` has the old 2-parameter
  signature and the block-only law (no global tier, no 3-layer env, no
  global-sourced construction triggers); `build.py:407` requires a build
  block to layer at all.
- Test coverage gaps: 27 new scenarios from the design's Test Stack Trace
  are uncovered; 10 existing pin sites need the new texts/signature (3
  hard-failing empty-workflow exact-equality pins — memory ~378, logic
  ~1353, assistants ~82 — plus the hard-failing field-order pin and the
  hard-failing signature pin as must-update sites; 1 match-pin that keeps
  passing; 4 recommended substring strengthenings).
- Facade/re-exports: no gaps — all entities already exported; `__all__`
  unchanged.
- Existing code that can be reused: `_validate_stage_env` (byte-identical
  messages), `_validate_top_level_profile` (mirror pattern), the
  `_patch_seams` harness, the `load_workflow` chain fixtures, the overlay
  fixtures of `tests/pipeline/hooks/test_overlay.py`, the build harness of
  `tests/build/`.
- No missing visibility in the workspace: all changed CODEMANIFESTs, source
  files, and test files are tracked.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed
> before starting the next (workflow → hooks → pipeline → build), matching
> the design's dependency order. Within each coding task, contract tests are
> written first (TDD workflow).

### Task 1: Bootstrap the virtualenv and verify the baseline gates (infrastructure)

This task creates the execution environment every subsequent task runs in
and proves the PRE-change tree is green, so any later failure is attributable
to the change under test. No contract entity is touched. The workspace has
no `.venv` and the system interpreter has no pytest/ruff (verified).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the virtualenv: `python3 -m venv .venv` (Python 3.12.16 system
  interpreter; 3.10+ required by the convention)
- [x] Install the project with the test extras:
  `.venv/bin/pip install -e ".[test]"` (pytest, pytest-cov, ruff)
- [x] Verify the baseline test battery:
  `.venv/bin/pytest tests/ -x` — green BEFORE any change (8298 passed, 8
  skipped)
- [x] Verify the baseline lint gates: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — zero findings
- [x] Verify the cell-level lint: `goga lint` — 93 cells, 0 errors
- [x] Verify the facade imports of every touched cell:
  `.venv/bin/python -c "from goga.pipeline.workflow import WorkflowDocument, parse_workflow; from goga.pipeline import run_pipeline, write_afm_config, apply_stage_env_wrappers, apply_skip_stages; from goga.pipeline.hooks import merge_workflow_overlay; from goga.build import merge_workflow_build, build, resolve_run_settings"`
- [x] Record the baseline results; a red baseline is reported, not silently
  absorbed (baseline green — recorded in
  /workspace/.ralphex/progress/progress-plan.txt)

### Task 2: `WorkflowDocument` — the two closing global fields (TDD)

This task implements the model half of the workflow-cell contract: two new
`kw_only` dataclass fields on `WorkflowDocument`
(`goga/pipeline/workflow/workflow_document.py`), closing the canonical field
order. The parser cannot carry the keys until the fields exist (Task 3
depends on this task). Facade unchanged — `WorkflowDocument` is already in
`__all__`.

**Usages relevant to this task:**
- `convention`: stdlib dataclasses, `@dataclass(kw_only=True)`, None for
  explicit absence, Google docstrings with every field in `Args:`, relative
  imports, mirror tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): in
  `tests/pipeline/workflow/test_workflow_document_contract.py` —
  `WorkflowDocument()` carries `agent is None` and `env is None` defaults;
  `WorkflowDocument(agent="claude", env={"A": "1"})` carries the authored
  values identity-equal; construction is kw_only
  (`is_kw_only_dataclass` from `tests/conftest.py:85`); and UPDATE the
  hard-failing field-order pin `test_workflow_document_field_order_fixed`
  (~line 64) to the 12-name list: `prompt, stages, extend, memory, profile,
  build, assistants, delegation, repeat, gates, agent, env`
- [x] **Code**: add the two fields after `gates` in
  `workflow_document.py`, in canonical order —
  `agent: str | None = None` and `env: dict[str, str] | None = None`
- [x] **Code**: extend the class `Args:` docstring with the two entries
  mirroring the CODEMANIFEST property annotations (agent: the
  workflow-global agent name — the global run-settings layer consumers
  resolve ahead of the configuration's pipeline agent; None when the key is
  absent or empty; env: the workflow-global environment layer; None when
  the key is absent — an empty map equals absence)
- [x] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/workflow/test_workflow_document_contract.py -v` — all pass
- [x] **Logic tests**: in
  `tests/pipeline/workflow/test_workflow_document_logic.py` — the authored
  values ride the document unchanged (identity: the same map object is
  carried, never rebuilt); defaults are None; the document with both None is
  constructible (the pre-change construction paths stay valid — every
  existing caller keeps working with zero changes)
- [x] **Debugging**: `.venv/bin/pytest tests/pipeline/workflow/ -x` — fix
  implementation code until all pass (do NOT fix test code)
- [x] **Contract re-verification**: facade import
  `from goga.pipeline.workflow import WorkflowDocument` green;
  `dataclasses.fields` order matches the contract; no other field moved
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — fix formatting if necessary
- [x] Verify `goga/pipeline/workflow/.usages/parse-workflow.md` stays
  truthful for the model surface (no edit expected — the fields are
  documented; report any drift)

### Task 3: `parse_workflow` — extraction, validation, and the grown rules (TDD)

This task implements the parser half of the workflow-cell contract
(`goga/pipeline/workflow/parse_workflow.py`): the two top-level extraction
branches, the new private `_validate_top_level_agent` helper (a mirror of
`_validate_top_level_profile`), the reuse of `_validate_stage_env("workflow",
value)` for the env map, the 12-key `_TOP_LEVEL_KEYS`, the extended
empty-workflow rule and message, and the two final-assembly kwargs. The cell
stays DECLARATIVE: no resolution, no merging, no launch.

Verified design facts to rely on: `_validate_stage_env`'s scope-interpolated
messages are byte-identical to the contract — reuse it verbatim, add NO new
env helper; block builders (`_build_build_block` etc.) do not touch the new
slots; a `profile:`-only workflow still raises (profile never counts).

**Usages relevant to this task:**
- `convention`: Google docstrings, parametrized boundary tables, exact
  message pins, pytest naming, mock-free pure-logic tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail): in
  `tests/pipeline/workflow/test_parse_workflow_contract.py` — the public
  signature `parse_workflow(text: str) -> WorkflowDocument` is unchanged;
  the returned document type carries `agent`/`env` (the Task 2 fields); an
  unknown top-level key raises the 12-key enumeration message (strengthen
  the existing substring assert at ~line 229 to the full fragment
  "valid keys: prompt, stages, extend, memory, profile, build, assistants,
  delegation, repeat, gates, agent, env" — recommended)
- [x] **Code**: add `_validate_top_level_agent(field_value: Any) ->
  str | None` mirroring `_validate_top_level_profile`
  (`parse_workflow.py:427`): non-str raises
  `WorkflowSyntaxError("non-str value in workflow.agent")`;
  empty/whitespace-only returns None; otherwise the str. Google docstring
  with Args/Returns/Raises
- [x] **Code**: extend `_extract_top_level`'s per-key dispatch and its
  return tuple with the two branches: `agent` →
  `_validate_top_level_agent(value)`; `env` →
  `_validate_stage_env("workflow", value)`; unpack the 12-tuple at the
  call site
- [x] **Code**: extend `_TOP_LEVEL_KEYS` (`parse_workflow.py:24`) with
  `"agent", "env"` (12 keys — the tuple join feeds the unknown-key message
  verbatim)
- [x] **Code**: grow the empty-workflow condition with
  `and agent is None and env is None` and the message with
  ", the agent key, or the env block"; pass `agent=agent, env=env` in the
  final `WorkflowDocument(...)` assembly (line ~281)
- [x] **Code**: extend the `parse_workflow` docstring's structural-error
  enumeration with the two new keys (the CODEMANIFEST step 4/5/7 wording)
- [x] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/workflow/test_parse_workflow_contract.py -v` — all pass
- [x] **Logic tests — positive** (new, in the mirror suites):
  - `test_agent_parses_into_document_field` — input
    `"stages:\n  build:\n    skip: true\nagent: claude\n"`:
    `document.agent == "claude"`, `document.env is None`,
    `document.stages["build"].skip is True`
  - `test_env_parses_into_document_field` — input
    `"prompt: hi\nenv:\n  GOGA_LOG_LEVEL: info\n  MODEL: '{{ m }}'\n"`:
    `document.env == {"GOGA_LOG_LEVEL": "info", "MODEL": "{{ m }}"}`,
    `document.agent is None` (parse does NOT render/interpret values)
  - `test_agent_alone_and_env_alone_are_valid_workflows` — `"agent:
    claude\n"` and `"env:\n  A: b\n"` both parse; the carried values assert
- [x] **Logic tests — negative**:
  - `test_non_str_agent_raises_structural_error` — parametrized table
    `"agent: 5"`, `"agent: [claude]"`, `"agent: {n: c}"`, `"agent:"`
    (YAML null — an empty key is NOT absence; the `profile:` law), each
    with a `prompt:` present so only the agent branch fails;
    `pytest.raises(WorkflowSyntaxError, match="non-str value in
    workflow.agent")`
  - `test_non_mapping_env_raises` (`env: "x"` → "non-mapping env in
    workflow"), `test_non_str_env_key_raises` (`env: {1: a}` → "non-str
    key in workflow.env"), `test_non_str_env_value_raises` (`env: {A: 5}`
    → "non-str value in workflow.env.A") — each with a `prompt:` present
  - `test_unknown_top_level_key_message_lists_agent_and_env` —
    `"prompt: hi\nagents: x\n"` → exact message
    "unknown key in workflow: agents; valid keys: prompt, stages, extend,
    memory, profile, build, assistants, delegation, repeat, gates, agent,
    env"
  - `test_empty_workflow_message_names_agent_and_env` —
    `"profile: default\n"` → exact new message ending "… the gates block,
    the agent key, or the env block"
- [x] **Logic tests — edge cases**:
  - `test_blank_agent_normalizes_to_absence` —
    `"agent: '   '\nstages:\n  a:\n    skip: true\n"` →
    `document.agent is None`, valid document
  - `test_blank_agent_does_not_rescue_empty_workflow` —
    `"agent: '  '\n"` alone raises the empty-workflow error
  - `test_empty_env_map_equals_absence` —
    `"prompt: hi\nenv: {}\n"` → `document.env is None` (NOT `{}` — the
    downstream `is not None` checks rely on it)
- [x] **Registry updates** (existing pins, same commit):
  - HARD-FAILING (exact equality, must be updated or they fail):
    `tests/pipeline/workflow/test_parse_workflow_memory.py` ~378
    (`test_parse_workflow_empty_workflow_message_mentions_memory_block`),
    `test_parse_workflow_logic.py` ~1353, and
    `test_parse_workflow_assistants.py` ~82 — all three empty-workflow
    exact-equality pins gain ", the agent key, or the env block"
  - `test_parse_workflow_repeat.py` ~87 — a match-pin
    (`match=re.escape(...)` of the old full message; `re.search` keeps the
    old text a prefix-substring of the new) that KEEPS PASSING; update it
    to the new full message to keep the pin tight (recommended)
  - RECOMMENDED (substring, keep passing either way): strengthen the
    valid-keys asserts of `test_parse_workflow_gates.py` ~297,
    `test_parse_workflow_memory.py` ~235, `test_parse_workflow_logic.py`
    ~581, `test_parse_workflow_contract.py` ~229 to the full 12-key
    fragment
- [x] **Debugging**: `.venv/bin/pytest tests/pipeline/workflow/ -x` — fix
  implementation code until all pass (do NOT fix test code)
- [x] **Contract re-verification**: the cell stays declarative (no wrapper
  resolution, no env merging, no launch anywhere); the five exact message
  texts match the CODEMANIFEST byte-for-byte; `from
  goga.pipeline.workflow import parse_workflow, WorkflowSyntaxError` green
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — fix formatting if
  necessary
- [x] Verify `goga/pipeline/workflow/.usages/parse-workflow.md` matches the
  implemented law (12-key list, the global-run-settings section, the
  empty-workflow rule text); report drift, do not silently rewrite

### Task 4: `merge_workflow_overlay` — verbatim globals carriage (TDD)

This task implements the hooks-cell contract change
(`goga/pipeline/hooks/overlay.py`): the final document assembly (step 8,
line ~619) gains the two kwargs carrying the BASE's globals verbatim. No
merge helper reads document-level globals — the "never read a
contribution's globals" constraint holds by construction; the only edit is
the final-assembly carriage.

**Usages relevant to this task:**
- `convention`: docstring style, relative imports, mock-free pure-logic
  tests with dataclass literals.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail): in
  `tests/pipeline/hooks/test_overlay.py` — `merge_workflow_overlay`
  signature unchanged; the rebuilt document is a `WorkflowDocument`
  carrying the base globals
- [x] **Code**: in the final assembly, add the two kwargs after `gates`:
  `agent=base.agent if base is not None else None` and
  `env=base.env if base is not None else None` (same objects — verbatim,
  never rebuilt; exactly as profile/build/memory)
- [x] **Code**: extend the `merge_workflow_overlay` docstring's verbatim-set
  note with the two globals (the CODEMANIFEST step 8 wording)
- [x] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/hooks/test_overlay.py -v` — all pass
- [x] **Logic tests**:
  - `test_overlay_preserves_global_run_settings_verbatim` — base =
    `WorkflowDocument(prompt="p", agent="claude", env={"A": "1"})`; one
    contribution whose document sets `agent="tool-agent"`,
    `env={"B": "2"}` and a stage field; after the merge:
    `overlay.workflow.agent == "claude"`,
    `overlay.workflow.env == {"A": "1"}` (the contribution's globals are
    discarded), and the contribution's stage field DID merge (the merge
    otherwise works)
  - edge: empty base + contributions → the contributed document's globals
    are still not read (the workflow-level assembly reads only `base`)
- [x] **Debugging**: `.venv/bin/pytest tests/pipeline/hooks/ -x` — fix
  implementation code until all pass
- [x] **Contract re-verification**: no merge helper reads a contribution's
  `agent`/`env`; purity holds (inputs unmutated, new document);
  `from goga.pipeline.hooks import merge_workflow_overlay` green
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/`
- [x] Verify `goga/pipeline/hooks/.usages/checkpoints.md` stays truthful
  (the verbatim-globals bullet); report drift

### Task 5: `apply_skip_stages` — skip rebuild carriage (TDD)

This task implements the pipeline-cell skip contract
(`goga/pipeline/apply_skip_stages.py`): the step-4 rebuild (line ~96)
carries the globals verbatim; the None-workflow synthesis carries both None;
the docstring enumeration grows the two fields.

**Usages relevant to this task:**
- `convention`: docstring style, mock-free pure-logic tests, dataclass
  literals.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail): in
  `tests/pipeline/test_apply_skip_stages.py` — signature unchanged; the
  rebuild result type carries `agent`/`env`
- [ ] **Code**: add to the rebuild
  `agent=workflow.agent if workflow is not None else None` and
  `env=workflow.env if workflow is not None else None` (the explicit
  per-field pattern matches the file's style; the kw_only defaults also
  cover the None case)
- [ ] **Code**: extend the docstring's synthesized-default enumeration and
  the rebuild note with the two globals (the CODEMANIFEST step 4 wording:
  carried verbatim — a rebuild that drops them would silently revert a
  skip-driven run to configuration-level globals)
- [ ] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/test_apply_skip_stages.py -v` — all pass
- [ ] **Logic tests**:
  - `test_skip_rebuild_preserves_global_run_settings` —
    `WorkflowDocument(prompt="p", stages={"a": …}, agent="claude",
    env={"A": "1"})` + `apply_skip_stages(workflow, ["a"])` →
    result `.agent == "claude"`, `.env == {"A": "1"}`,
    `.stages["a"].skip is True`
  - `test_skip_synthesis_with_none_workflow_carries_agent_env_none` —
    `apply_skip_stages(None, ["a"])` → `.agent is None`, `.env is None`,
    `.stages["a"].skip`
  - edge: empty skip list returns the input object unchanged (the
    pre-existing law, still green)
- [ ] **Debugging**: `.venv/bin/pytest tests/pipeline/test_apply_skip_stages.py
  tests/pipeline/test_card_run_skip_equivalence.py -x` — fix implementation
  until all pass
- [ ] **Contract re-verification**: inputs unmutated; the routine stays
  declarative (no stage deletion, no depends_on rewrite);
  `from goga.pipeline import apply_skip_stages` green
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/`

### Task 6: `run_pipeline` — effective global agent and launch env base (TDD)

This task implements the run-coordination contract
(`goga/pipeline/run_pipeline.py`): the NEW step 14 resolves the effective
global agent once per run; the wrapper call (line ~472) and the afm config
call (line ~499) consume it; step 20's launch env base (line ~552) composes
`pipeline.env ⊕ workflow global env` under the unchanged CLI-above and
engine-key-drop laws; the step comments are renumbered to the CODEMANIFEST's
1..24; the two consumer docstrings (`afm_config.py` agent parameter;
`stage_env_wrappers.py` global_agent parameter, both sites) document the new
source. `write_afm_config` and `apply_stage_env_wrappers` take NO code
change — the assistant fallback at `afm_config.py:187` already implements
the law.

**Usages relevant to this task:**
- `convention`: docstring style; run-level tests reuse the `_patch_seams`
  harness of `tests/pipeline/test_run_pipeline.py:1395` (mocked
  `write_afm_config` spy, mocked `run_flow`, `monkeypatch.setenv` for
  `GOGA_EXTRA_ENV`); no new mocks beyond the existing seams.
- `afm` (project usage): the afm configuration-file contract consumed by
  `write_afm_config` — unchanged contract; only the `agent` parameter's
  source changes (the client command resolves the same wrapper path from a
  possibly-different agent name; the assistant fallback follows it by
  construction).
- `extra-env-carriage` (imported): the "task env layer (effective)" of the
  ladder is now the key-wise merge `pipeline.env ⊕ workflow global env`;
  CLI entries stay above; engine keys drop silently.
- `resolve-wrapper-path` (imported): unchanged — one more caller-side source
  for the agent name.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail): in
  `tests/pipeline/test_run_pipeline_contract.py` — `run_pipeline` signature
  unchanged; the source-level threading pins (any pin of
  `config.pipeline.agent` reaching the seams stays valid — the fallback is
  unchanged; add the workflow-global call form rather than rewriting
  existing pins)
- [ ] **Code — step 14** (after `compile_flow`, before the wrapper
  applications): `workflow_agent = overlay.workflow.agent if
  overlay.workflow is not None else None`; `effective_agent =
  workflow_agent if workflow_agent is not None else config.pipeline.agent`
  (single site; None-safe; exactly three consumers)
- [ ] **Code — consumers**: the wrapper call becomes
  `apply_stage_env_wrappers(flow_doc.stages, overlay.workflow,
  effective_agent, flow_path)`; the config call becomes
  `write_afm_config(effective_agent, flow_doc, overlay.workflow)`
- [ ] **Code — step 20**: `workflow_env = overlay.workflow.env if
  overlay.workflow is not None else None`;
  `base = {**config.pipeline.env, **(workflow_env or {})}`;
  the launch layer comprehension composes `{**base, **payload}` under the
  unchanged `_ENGINE_ENV_KEYS` filter; `GOGA_PROFILE` still added afterwards
  from the resolved profile
- [ ] **Code — renumbering**: renumber the step comments to the
  CODEMANIFEST's 1..24 (current 14/14b → 15 wrappers; 15 → 16 prompts;
  16/16a → 17 afm home + skin; 17 → 18 composition; 18 → 19 statuses;
  19 → 20 launch layer; 20 → 21 run-creation facts; 21 → 22 launch;
  22–23 → 23 completion; return → 24) and update the two inline comments
  that said "effective pipeline agent"
- [ ] **Code — docstring alignment** (no behavior): `afm_config.py` `agent`
  parameter description → the effective global agent (workflow global when
  the effective workflow carries one, otherwise the authored pipeline.agent
  as amended; None when neither resolves); `stage_env_wrappers.py:147` and
  `:495` `global_agent` descriptions → the effective global agent (workflow
  global, else the effective pipeline agent)
- [ ] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/test_run_pipeline_contract.py
  tests/pipeline/test_afm_config.py
  tests/pipeline/test_stage_env_wrappers_contract.py -v` — all pass
- [ ] **Logic tests** (in `tests/pipeline/test_run_pipeline.py`, via
  `_patch_seams`):
  - `test_run_pipeline_workflow_global_agent_feeds_all_three_consumers` —
    config `pipeline=PipelineConfig(agent="codex", env={})`; workflow file
    with `agent: claude` and one env-free stage; the `write_afm_config`
    seam received `agent == "claude"`; the wrapper generation received the
    same value; `"codex"` appears nowhere; optional variant: an assistant
    without its own agent launches under `claude` (the fallback inside the
    config write)
  - `test_run_pipeline_launch_env_base_merges_workflow_env_keywise` —
    `pipeline.env={"A": "1", "B": "1"}`; workflow `env: {B: "2", C: "3"}`;
    `GOGA_EXTRA_ENV` unset; the `run_flow` seam env ==
    `{"A": "1", "B": "2", "C": "3"}` (workflow wins per key, config keys
    survive)
  - `test_run_pipeline_cli_entries_stay_above_and_engine_keys_drop` —
    workflow `env: {B: "w", GOGA_WORKFLOW: "evil"}`;
    `GOGA_EXTRA_ENV` encoding `{B: "cli"}`; the `run_flow` env has
    `B == "cli"` and NO `GOGA_WORKFLOW` key from the workflow (a workflow
    cannot escalate into engine carriage variables)
  - `test_run_pipeline_without_workflow_global_falls_back_to_pipeline_agent`
    — workflow WITHOUT `agent:`; `pipeline.agent="codex"`; the seams
    receive `"codex"` — behavior identical to today
- [ ] **Debugging**: `.venv/bin/pytest tests/pipeline/ -x` — fix
  implementation code until all pass
- [ ] **Contract re-verification**: the environment reads stay exactly four
  (AFM_DIR, the CLI entries payload, GOGA_PROFILE, GOGA_HOME_PROFILES); the
  effective agent feeds exactly the three consumption points and nothing
  else; no new error path; `from goga.pipeline import run_pipeline` green
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/`
- [ ] Verify `goga/pipeline/.usages/run-pipeline.md` and
  `goga/pipeline/.usages/per-stage-env.md` stay truthful against the
  implemented law; report drift

### Task 7: `merge_workflow_build` — the 4-layer rewrite (TDD)

This task replaces `goga/build/workflow_build.py`'s merge wholesale: the
4-parameter signature, the truthiness cascade `block or global or config`
per pass agent, the 3-layer key-wise env (`_merge_env(base, *overlays)`),
the construction triggers extended with the global sources, and the
unchanged verbatim pass-through of every other field. The routine stays
pure (frozen models — inputs unmutated, always a new result).

**Usages relevant to this task:**
- `convention`: Google docstrings, relative imports, mock-free pure-logic
  tests with dataclass literals; exact signature pins in the contract
  suite.
- `workflow-layering` (local usage, already updated): the 4-layer order and
  the per-pass resolution laws — block > global > config at every pass; the
  global env is the only cross-pass base.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail): in
  `tests/build/test_workflow_build_merge_contract.py` — UPDATE the signature
  pin (~line 26) to the 4-parameter form
  `["config", "build_block", "global_agent", "global_env"]` with
  `config`/`build_block` required (empty defaults) and
  `global_agent`/`global_env` defaulted; annotations
  `BuildConfig` / `WorkflowBuild | None` / `str | None` /
  `dict[str, str] | None`; return `BuildConfig`
- [ ] **Code**: rewrite `merge_workflow_build` per the design algorithm
  (see Context — the verbatim algorithm block): `pass_agent(block_value,
  config_value) = block_value or global_agent or config_value`; root agent
  and env; review and additional layers; the construction triggers
  (`config.review is None` AND any of the six review-sourced values set →
  new `ReviewConfig`; `additional is None` AND any of the four
  additional-sourced values set → new `AdditionalReviewConfig`); every
  other field verbatim
- [ ] **Code**: extend `_merge_env` to the variadic form
  (`_merge_env(base, *overlays)` — later layers win per key, None overlays
  are skips) and thread the global env through `_merge_review` /
  `_merge_additional`
- [ ] **Code**: Google docstrings for the new signature and helpers (the
  CODEMANIFEST parameter descriptions are the source text; document the
  truthiness cascade and the empty-string block-agent fall-through)
- [ ] **Interface verification**: `.venv/bin/pytest
  tests/build/test_workflow_build_merge_contract.py -v` — all pass
- [ ] **Logic tests** (in `tests/build/test_workflow_build_merge_logic.py`):
  - `test_merge_workflow_build_four_layer_agent_precedence` — config
    root/review/additional agents set; block `review_agent="blk-rev"`;
    globals `("g-global", None)` → root agent `"g-global"` (global
    OVERRIDES a set config field), review agent `"blk-rev"` (block wins),
    additional agent `"g-global"` (per-pass independence)
  - `test_merge_workflow_build_env_layering_config_global_block` — config
    env `{"R": "cfg", "S": "cfg"}`, review env `{"X": "cfg"}`;
    `global_env={"S": "glob", "T": "glob"}`; block
    `env={"R": "blk"}`, `review_env={"X": "blk"}` → root
    `{"R": "blk", "S": "glob", "T": "glob"}`; review `{"X": "blk",
    "S": "glob", "T": "glob"}`; additional `{"S": "glob", "T": "glob"}`;
    inputs unmutated
  - `test_merge_workflow_build_globals_with_none_block` —
    `build_block=None`, `global_agent="g"`, `global_env={"E": "2"}`,
    `config.review=None` → root agent "g", root env `{"A": "1", "E": "2"}`;
    review constructed with agent "g", env `{"E": "2"}`; additional
    constructed with env `{"E": "2"}`; the INPUT's `config.review` still
    None (purity)
  - `test_merge_workflow_build_globals_none_matches_block_only_overlay` —
    call with `(config, block, None, None)`; every field equals the
    block-only expectation (root agent `block.agent or config.agent`;
    two-layer env; review/additional construction only from block fields)
  - `test_merge_workflow_build_never_mutates_inputs` — frozen config
    models, deep field snapshot before, all layers set; inputs
    field-identical after; the result is a new object
  - edge: `build: {agent: ""}` — an authored empty-string block agent
    falls through to the global, else the config (the non-normalized
    boundary; the `block or config` parity)
- [ ] **Debugging**: `.venv/bin/pytest tests/build/ -x` — fix
  implementation code until all pass
- [ ] **Contract re-verification**: pure (new `BuildConfig`, new nested
  models, inputs unmutated); absent values never override; no CLI values
  applied here; no wrapper resolution; the global env is the only
  cross-pass base; `from goga.build import merge_workflow_build` green
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/`
- [ ] Verify `goga/build/.usages/workflow-layering.md` stays truthful (the
  4-layer order; block > global > config); report drift

### Task 8: `build` step 4 and `resolve_run_settings` note (TDD)

This task implements the orchestration half of the build-cell contract
(`goga/build/build.py`): the step-4 layering condition widens from
`loaded is not None and loaded.document.build is not None` (lines 407–408)
to `loaded is not None` — the globals apply with no build block too;
`goga/build/run_settings.py` gains the docstring-level note (no code
change).

**Usages relevant to this task:**
- `convention`: docstring style; the build harness of `tests/build/`
  (existing fixtures, mocked pass launches).
- `ralphex`, `agent-wrappers` (project usages): unchanged consumption — the
  layered values flow through the existing machinery.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail): in `tests/build/test_build.py`
  — `build` signature unchanged; the step-4 call form: with a workflow
  document present, `merge_workflow_build` is called with four arguments
  (the document's build block — None legal — its agent, its env)
- [ ] **Code**: replace the condition with `if loaded is not None:` and the
  call with `build_config = merge_workflow_build(build_config,
  loaded.document.build, loaded.document.agent, loaded.document.env)`;
  update the surrounding comment (the layering runs whenever a document is
  present — the globals apply with no build block too)
- [ ] **Code**: `run_settings.py` — extend the `resolve_run_settings`
  docstring opening note: "The `config` parameter is the LAYERED effective
  build configuration: when a workflow is in effect, the caller has already
  overlaid its global run settings and build block via
  `merge_workflow_build`; this routine consumes the layered value and
  applies no layering itself" (no algorithm change)
- [ ] **Interface verification**: `.venv/bin/pytest tests/build/test_build.py
  tests/build/test_run_settings.py -v` — all pass
- [ ] **Logic tests**:
  - `test_build_layers_globals_without_build_block` — config with a build
    section, `review=None`; workflow file `agent: g\nenv: {E: "2"}\n` (no
    `build:` block); `build(plan, config, cli_options)` with the pass
    launches mocked → the resolved settings/wrapper composition carries
    `agent="g"` and env layer `{"E": "2"}`; the exit path proceeds as with
    a normal run
  - regression: a workflow with a `build:` block still layers exactly as
    before (the block path through the new signature)
  - regression: no workflow in effect → no layering call at all (the
    `loaded is None` branch unchanged)
- [ ] **Debugging**: `.venv/bin/pytest tests/build/ -x` — fix
  implementation code until all pass
- [ ] **Contract re-verification**: the no-build-section guard is unchanged
  and still fires before any layering; the guard reads the layered
  effective configuration; `from goga.build import build,
  resolve_run_settings` green
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/`

### Task 9: Integration tests — cross-entity and chain scenarios

This task covers the scenarios that span modules and cells: the
load-render-parse chain (the globals ride the profile rendering), the build
cascade (the layered root feeding `resolve_run_settings`), and one composed
pipeline-run scenario (workflow globals surviving skip + overlay into the
run seams). These verify the FEATURE end to end, not any single entity.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

**Usages relevant to this task:**
- `jinja2` (project usage): the whole-file rendering law — the two keys
  ride the rendering like every other byte; the profile peek reads raw
  text.
- `convention`: integration tests only for interaction between
  modules/packages; `tmp_path` for the file I/O; the existing chain
  fixtures and seams.

- [ ] Create/extend `tests/pipeline/workflow/test_loading_chain_integration.py`:
  `test_workflow_global_env_renders_from_profile_data` — a workflow text
  with `env: {MODEL: "{{ agent_cfg.model }}"}` and a profile dict
  `{"agent_cfg": {"model": "opus"}}` (the existing `load_workflow` chain
  fixtures of `tests/pipeline/workflow/conftest.py`); `load_workflow(path,
  cli_profile=…)` → `loaded.document.env == {"MODEL": "opus"}` (the
  ride-the-rendering law; no rendering-code change)
- [ ] Create/extend the build cross-entity test (in
  `tests/build/test_workflow_build_merge_logic.py` or
  `tests/build/test_run_settings.py`):
  `test_build_cascade_runs_from_layered_root` — config
  `BuildConfig(agent="cfg-root", review=ReviewConfig(agent=None))`;
  workflow global `agent: g`, no block; `merge_workflow_build` then
  `resolve_run_settings(layered, {})` → `settings.review.agent == "g"` and
  `settings.tasks.agent == "g"` (the cascade runs from the effective,
  post-override root)
- [ ] Create the composed run scenario (in
  `tests/pipeline/test_run_pipeline.py`): one workflow file carrying BOTH
  globals and one skippable stage; `run_pipeline(…, skip=[…])` under the
  seams → the skip rebuild AND the overlay both preserved the globals, the
  seams received the workflow agent, and the `run_flow` env carries the
  merged base (the full parse → skip → overlay → resolve chain)
- [ ] Run the full battery: `.venv/bin/pytest tests/ -x` — green
- [ ] Run the facade battery (Validation Commands) — green

---

## Validation Commands

All commands run in the virtualenv (Task 1); `goga lint` runs on the host
interpreter:

- `.venv/bin/pytest tests/ -x`: Run all tests (the full battery)
- `.venv/bin/pytest tests/pipeline/workflow/ -x`: The workflow cell suites
- `.venv/bin/pytest tests/pipeline/hooks/ tests/pipeline/ -x`: The hooks and
  pipeline suites
- `.venv/bin/pytest tests/build/ -x`: The build suites
- `.venv/bin/ruff check goga/ tests/`: Lint — zero violations (the CI gate)
- `.venv/bin/ruff format --check goga/ tests/`: Format — zero reformattings
  (the CI gate)
- `goga lint`: Cell-level lint — 0 errors over 93 cells
- `.venv/bin/python -c "from goga.pipeline.workflow import WorkflowDocument, parse_workflow, WorkflowSyntaxError"`:
  Workflow facade check
- `.venv/bin/python -c "from goga.pipeline.hooks import merge_workflow_overlay"`:
  Hooks facade check
- `.venv/bin/python -c "from goga.pipeline import run_pipeline, write_afm_config, apply_stage_env_wrappers, apply_skip_stages"`:
  Pipeline facade check
- `.venv/bin/python -c "from goga.build import merge_workflow_build, build, resolve_run_settings"`:
  Build facade check

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is accessible from the facade (no `__all__`
      changes were needed — verified none were made)
- [ ] Properties and methods match the declared API (the two model fields;
      the 4-parameter merge signature; unchanged signatures everywhere else)
- [ ] Descriptions are reflected in behavior (the exact five messages, the
      12-key enumeration, the grown empty-workflow message, the verbatim
      carriage, the effective-agent three consumers, the key-wise env laws,
      the 4-layer build order)
- [ ] Contract dependencies are met (workflow → hooks → pipeline → build in
      dependency order)
- [ ] Re-exports are accessible from the facade (none added — verified)
- [ ] Every coding task followed the TDD workflow (contract tests → code →
      verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within
      each coding task
- [ ] Integration tests exist where cross-entity scenarios require them
      (Task 9)
- [ ] No package boundary was expanded (no new cells, no new Imports, no
      facade growth)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (full battery, ruff check, ruff format
      --check, goga lint 93/0, facade imports)
- [ ] The Mandatory Rules were enforced at every task end and before every
      local commit (style, tests, lint/format gates, REPL cycle)
- [ ] `goga/pipeline/compiler`, `goga/agents/wrapper`, `goga/config`, and
      every `goga/commands/*` remain untouched (the contract-drift
      guarantee survives)
- [ ] No commit message carries a `Co-Authored-By:` trailer
- [ ] The deferred follow-up (de-stamping `.goga/profiles/default.yml`) was
      NOT done in this feature
