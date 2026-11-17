# Design Document: `add-env-and-agent-to-workflow`

Workflow-level global `agent` and `env` — two new top-level workflow-file keys that
override the project configuration's own globals for both the pipeline run and the
build, per the accepted ADR (`adr.md`) and the applied architecture plan (`arch.md`).
This document specifies **what to implement and how**: every code change, its exact
shape, and the full test suite. The contracts (4 CODEMANIFESTs + 5 `.usages` docs)
are already materialized and validated (`goga lint`: 93 cells, 0 errors); the
implementation is still at the pre-change state.

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/pipeline/workflow/CODEMANIFEST` — grammar + model: `WorkflowDocument` gains
  `agent: str | None = None` and `env: dict[str, str] | None = None` (two properties,
  canonical field order closed by the two global run-settings fields);
  `parse_workflow` step 4 extracts and validates both keys (exact structural-error
  messages), step 5 unknown-key enumeration grows to 12 keys, step 7 empty-workflow
  rule counts both keys, step 8 returns them; header annotation paragraph and footer
  description extended.
- `goga/pipeline/hooks/CODEMANIFEST` — `merge_workflow_overlay` algorithm step 8,
  one requirement and one constraint: the global `agent`/`env` ride the rebuilt
  document verbatim from the base, joining `profile` and `build` in the
  verbatim-from-base set; the merge never reads a contribution's globals.
- `goga/pipeline/CODEMANIFEST` — `run_pipeline` gains step 14 (resolve the effective
  global agent once per run; former steps 14–23 renumbered 15–24); step 20 composes
  the launch env base as the key-wise merge `pipeline.env ⊕ workflow global env`;
  `write_afm_config` and `apply_stage_env_wrappers` parameter annotations now name
  the effective global agent; `apply_skip_stages` carries the globals verbatim
  through the skip rebuild; header annotation paragraph and footer description added.
- `goga/build/CODEMANIFEST` — `merge_workflow_build` replaced wholesale: new
  4-parameter signature (`build_block: WorkflowBuild | None`, defaulted
  `global_agent`, `global_env`) and the 4-layer algorithm
  (config < workflow global < workflow `build:` < CLI, cascade step documented);
  `build` step 4 layers whenever a workflow document is present (no `build:` block
  required); `resolve_run_settings` opening note updated; header Workflow-layering
  paragraph and footer description updated.

### New Entities

None — both new `WorkflowDocument` fields are primitives riding existing carriages;
no new Imports, locations, or cells.

### Changed Entities

- `WorkflowDocument` (workflow) — two new kw_only fields closing the canonical order:
  `agent`, `env`.
- `parse_workflow` (workflow) — extracts/validates the two keys; empty-workflow rule
  and messages extended.
- `merge_workflow_overlay` (hooks) — verbatim-from-base set extended with the two
  globals.
- `run_pipeline` (pipeline) — new step 14 (effective global agent); step 20 launch
  env base merge; the resolved value feeds `apply_stage_env_wrappers` and
  `write_afm_config`.
- `write_afm_config` (pipeline) — parameter semantics only: `agent` is now the
  effective global agent (assistant fallback follows it by construction).
- `apply_stage_env_wrappers` (pipeline) — parameter semantics only: `global_agent`
  is now the effective global agent.
- `apply_skip_stages` (pipeline) — the rebuild carries `agent`/`env` verbatim.
- `merge_workflow_build` (build) — new signature and 4-layer algorithm.
- `resolve_run_settings` (build) — docstring-level: consumes the layered value
  (globals + block), no code change.
- `build` (build) — step 4 layering condition: any workflow document present.

### Deleted Entities

None.

### Usages and Annotations Changes

- `goga/pipeline/workflow/.usages/parse-workflow.md` — new "The global run settings"
  section; 12-key top-level enumeration; empty-workflow rule text.
- `goga/pipeline/hooks/.usages/checkpoints.md` — overlay bullet: globals ride
  verbatim; tools can neither supply nor override them.
- `goga/pipeline/.usages/run-pipeline.md` — new "Workflow-global run settings"
  section; afm-configuration and env-ladder sections updated.
- `goga/pipeline/.usages/per-stage-env.md` — the global env layers reach every stage
  ambiently through the afm launch layer.
- `goga/build/.usages/workflow-layering.md` — 4-layer order section with the
  per-pass agent/env resolution laws.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga/build/CODEMANIFEST` (header annotation, Workflow-layering paragraph):
  before — "the global agent fills every pass-agent field that neither the build
  block nor the configuration fills" (reads as block > config > global, i.e. the
  configuration beats the global); after — "the global agent fills every pass-agent
  field the build block leaves unset — overriding the configuration field when one
  is set" (reason: annotation↔algorithm inconsistency — the same paragraph's layer
  order `config < workflow global < workflow build:`, `merge_workflow_build`
  Algorithm step 1, the ADR, task.md, and `.usages/workflow-layering.md` all state
  block > global > config; user-approved via the stage dialog). `goga lint` re-run
  green after the edit.

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

1. **Parse flow** — `load_workflow` renders the whole file (the two keys ride the
   rendering like every other byte; the profile peek still reads raw text, so a
   value materializing only through rendering activates nothing), `parse_workflow`
   validates structurally and builds `WorkflowDocument(agent=…, env=…)` (None when
   absent/empty; an empty env map builds `env=None`).
2. **Amendment flow** — `apply_skip_stages` rebuilds the document carrying the
   globals verbatim; `PipelineHooks.amend_workflow` → `merge_workflow_overlay`
   rebuilds again, still carrying the base's globals verbatim; contributions'
   globals are never read. The effective workflow of the run is
   `overlay.workflow` (the passthrough when the layer is off).
3. **Run flow** — after `compile_flow` (consumes neither key), `run_pipeline`
   resolves the effective global agent once (step 14) and feeds it to the wrapper
   generation and the afm configuration write; the launch env base composes
   `pipeline.env` with the workflow global env before the CLI entries layer above
   and the engine-key drop (step 20).
4. **Build flow** — `build` step 4 overlays the globals and the `build:` block onto
   `config.build` via the new `merge_workflow_build` signature whenever a workflow
   document is present; `resolve_run_settings` consumes the layered value; the
   agent-inheritance cascade runs from the layered root.

### Entity Dependencies

Implementation order (leaves → root, matching the import graph):

1. `goga/pipeline/workflow` (leaf) — model + parser.
2. `goga/pipeline/hooks` (imports workflow) — overlay verbatim carriage.
3. `goga/pipeline` (imports workflow + hooks) — skip rebuild, run resolution, doc
   alignments in `afm_config`/`stage_env_wrappers`.
4. `goga/build` (imports workflow) — `merge_workflow_build` rewrite + `build` step 4
   + `run_settings` docstring.

Untouched by contract (verified zero-diff in the apply stage, keep untouched):
`goga/pipeline/compiler`, `goga/agents/wrapper`, `goga/config`, `goga/commands/*`.

## Code Stack Trace

### Trace: `parse_workflow`

#### Chain

1. **Input**: rendered workflow-file text (from `load_workflow`; the file may carry
   top-level `agent:` and/or `env:`) → checkpoint: text is a str, rendering already
   applied — passed.
2. **Step**: `yaml.safe_load`; non-dict root → "workflow must be a mapping" →
   checkpoint: unchanged law — passed.
3. **Step**: `_extract_top_level(loaded)` iterates top-level keys. New branches:
   `agent` → `_validate_top_level_agent(value)` (new helper mirroring
   `_validate_top_level_profile`: non-str raises `WorkflowSyntaxError("non-str value
   in workflow.agent")`; empty/whitespace-only returns None; otherwise the str);
   `env` → `_validate_stage_env("workflow", value)` (existing helper, reused
   verbatim — its scope-interpolated messages are exactly the contracted ones:
   "non-mapping env in workflow", "non-str key in workflow.env",
   "non-str value in workflow.env.KEY"; an empty map returns None). Unknown key →
   message enumerates `_TOP_LEVEL_KEYS`, now the 12-key tuple → checkpoint: message
   text == CODEMANIFEST step 5 — passed (tuple join produces the exact list).
4. **Step**: block builders unchanged (`_build_build_block` etc. read their raw
   slots; the two new slots pass straight through) → checkpoint: no builder touches
   the new slots — passed.
5. **Step**: empty-workflow rule — condition grows `and agent is None and env is
   None`; message grows ", the agent key, or the env block" → checkpoint: an
   `agent:`-only or `env:`-only workflow is valid; a `profile:`-only workflow still
   raises — passed.
6. **Output**: `WorkflowDocument(…, gates=gates, agent=agent, env=env)` — the two
   fields close the canonical order; consumer types (`str | None`,
   `dict[str, str] | None`) match every downstream consumer signature → checkpoint:
   type flow — passed.

#### Checkpoint Summary

- Top-level extraction branch-per-key, messages exact: passed.
- Env law == `_validate_stage_env` output: passed (byte-identical messages; no new
  helper needed for env).
- Agent law == profile's scalar law with its own message: passed (new helper).
- Empty-workflow and unknown-key enumerations: passed.
- No wraparound defect found; the cell stays declarative (no resolution/merging).

### Trace: `merge_workflow_overlay` (hooks)

#### Chain

1. **Input**: `base: WorkflowDocument | None` (post-skip authored workflow),
   `contributions: list[ToolContribution]` → checkpoint: contributions may carry
   documents with `agent`/`env` set by a tool — data reaches the merge — passed.
2. **Step**: no contributions → passthrough `WorkflowOverlay(workflow=base)` — the
   base object already carries its globals; nothing to do → passed.
3. **Steps 2–7** (prompt/memory/stages/extend/assistants/delegation/repeat/gates
   merges): none of these helpers reads a document-level `agent`/`env` field; the
   stage field-set-complete merge operates on `WorkflowStage` fields, and the
   workflow-level merge helpers read only their own blocks → checkpoint: a
   tool-supplied global can never enter through any merge helper — passed by
   construction; the constraint "do not read the agent or env fields of any
   contribution document" requires no new code, only the final-assembly carriage.
4. **Step**: final assembly constructs a new `WorkflowDocument(...)` — the two new
   kwargs `agent=base.agent if base is not None else None`,
   `env=base.env if base is not None else None` must be added (the assembly is an
   explicit field list, not a copy) → checkpoint: without the edit the rebuild
   silently drops the globals (the exact regression the requirement names) — defect
   in implementation-to-be, fixed by the specified edit.
5. **Output**: the overlay document carries the base globals verbatim (same objects,
   never rebuilt) → passed.

#### Checkpoint Summary

- Verbatim carriage: passed (with the two-kwarg edit).
- Namespace/assistant/gates laws untouched: passed.

### Trace: `apply_skip_stages` (pipeline)

#### Chain

1. **Input**: resolved workflow document (carrying globals) + CLI skip names.
2. **Step**: empty skip → input returned unchanged (globals ride the same object) →
   passed.
3. **Step**: non-empty skip rebuilds `WorkflowDocument(...)` — add
   `agent=workflow.agent if workflow is not None else None` and the `env` twin;
   a None workflow synthesizes the document with both None (kw_only defaults also
   cover it, but the explicit pattern matches the file's per-field style) →
   checkpoint: skip-driven runs keep workflow-level globals — passed (with the edit).
4. **Output**: new document, inputs unmutated → passed.

### Trace: `run_pipeline` (steps 13–20 region)

#### Chain

1. **Input**: `config = overlay.config` (effective; `config.pipeline` guaranteed
   non-None by the host-side launcher guard in `goga/commands/pipeline`), the
   `overlay.workflow` document, compiled `flow_doc`.
2. **Step 13**: `compile_flow` consumes neither global (verified: the compiler reads
   stage/extend/assistants/gates/repeat instructions only) → passed.
3. **Step 14 (new)**: resolve once —
   `workflow_agent = overlay.workflow.agent if overlay.workflow is not None else None`;
   `effective_agent = workflow_agent if workflow_agent is not None else
   config.pipeline.agent`. Layer off (`no_workflow`) or no workflow resolved →
   `overlay.workflow is None` or `.agent is None` → `config.pipeline.agent` holds
   the role → checkpoint: the three consumption points and nothing else — passed.
4. **Step 15**: `apply_stage_env_wrappers(flow_doc.stages, overlay.workflow,
   effective_agent, flow_path)` — the wrapper's own precedence (stage agent >
   extend-entry agent > global) is unchanged; only the global tier's value changes
   source → checkpoint: signature/type match — passed.
5. **Step 17**: `write_afm_config(effective_agent, flow_doc, overlay.workflow)` —
   the client command resolves `resolve_wrapper_path(effective_agent)` when not
   None; the assistant fallback inside `_resolve_profiles` is already
   `declaration.agent if declaration.agent is not None else agent` → checkpoint: an
   assistant without its own agent launches under the workflow global agent with
   zero changes inside `afm_config.py` — passed (docstring alignment only).
6. **Step 20**: launch env base —
   `workflow_env = overlay.workflow.env if overlay.workflow is not None else None`;
   `base = {**config.pipeline.env, **(workflow_env or {})}` (workflow wins per key,
   config keys survive); `launch_layer = {k: v for k, v in {**base, **payload}.items()
   if k not in _ENGINE_ENV_KEYS}`; `GOGA_PROFILE` added from the resolved profile
   only → checkpoint: CLI above base; engine keys (incl. a workflow-supplied
   `GOGA_PROFILE`/`GOGA_WORKFLOW`) drop silently; `extra-env-carriage` ladder
   preserved with the base as the effective task env layer — passed.
7. **Output**: `run_flow(..., env=launch_layer)`; process environment untouched →
   passed.

#### Checkpoint Summary

- Effective-agent resolution: single site, None-safe, three consumers — passed.
- Launch base merge: exact key-wise law, engine-set drop unchanged — passed.
- Card form (`describe_pipeline`): performs no global resolution (no
  `write_afm_config`/launch layer there) — verified, no change needed.

### Trace: `build` step 4 → `merge_workflow_build` → `resolve_run_settings`

#### Chain

1. **Input**: `loaded: LoadedWorkflow | None` (document may carry `build: None` but
   `agent`/`env` set), `config.build` guaranteed non-None by the step-4 guard.
2. **Step**: `if loaded is not None: build_config = merge_workflow_build(
   build_config, loaded.document.build, loaded.document.agent,
   loaded.document.env)` — condition widens from `loaded.document.build is not
   None` to `loaded is not None` → checkpoint: a globals-only workflow layers —
   passed.
3. **Step**: per-pass agent = block ?? global ?? config (root/review/additional
   independently); per-pass env = config ⊕ global ⊕ block key-wise → checkpoint:
   matches the (fixed) header annotation, Algorithm step 1/2, ADR, and
   `.usages/workflow-layering.md` — passed after the Phase-3 fix.
4. **Step**: nested-model construction triggers — when `config.review is None`:
   construct a new `ReviewConfig` if any review-sourced value would land on it (any
   of `block.review_agent`, `block.review_env`, `block.review_additional_agent`,
   `block.review_additional_env`, `global_agent`, `global_env` is set) — the global
   agent reaches the review/additional pass fields per Algorithm step 1, the global
   env reaches every pass env (env never inherits downstream, so the construction is
   the only way it reaches the review passes); when the additional part is None:
   construct a new `AdditionalReviewConfig` if any additional-sourced value would
   land on it (block additional fields, `global_agent`, `global_env`) → checkpoint:
   `resolve_run_settings` receives a well-formed layered configuration — passed.
5. **Step**: `resolve_run_settings(layered, cli_options)` — no code change: the
   cascade `review_agent = review.agent or config.agent` reads the layered root;
   env passes verbatim per pass; CLI knobs apply above → checkpoint: cascade runs
   from the effective post-override root — passed.
6. **Output**: `RunSettings` → `write_role_env_wrappers` composes the per-role
   closures over the layered pass env maps (CLI entries above them, engine keys
   dropped) → checkpoint: the global env reaches every executor ambiently through
   its pass layer — passed.

#### Checkpoint Summary

- 4-layer order and construction triggers: passed (post-fix).
- Block-only parity: with both globals None the layered result is field-identical
  to the block-only overlay — passed (design test pins it).
- Secret-safety invariants: the config root env still never reaches the review
  pass (the global env is the only cross-pass base) — passed.

## Algorithm Design

### `parse_workflow` — the two new extraction branches (workflow)

**Responsibility**: structural validation + model extraction of the two global keys;
no resolution, no merging, no launch.

**Algorithm:**
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

**Errors:**
- `WorkflowSyntaxError` with the five exact messages above (contract-pinned text).

**Edge cases:**
- `agent: ""` / `agent: "   "` → None (absence); such a workflow with no other
  content is EMPTY (raises) — activation-free scalar normalization, `profile` law.
- `env: {}` → None (absence, stage-env law — NOT the assistant explicit-clear law).
- `agent: 5`, `agent: [claude]`, `agent: {name: claude}` → structural error.
- YAML bool key `true:` as a key → unknown key (unchanged).

### `WorkflowDocument` (workflow)

**Responsibility**: carry the two globals as plain dataclass fields.

**Algorithm:**
```
1. Two new kw_only fields after gates, in canonical order:
   agent: str | None = None
   env: dict[str, str] | None = None
2. Args-docstring entries mirroring the CODEMANIFEST property annotations
```

**Edge cases:** None defaults; consumers treat the document as read-only
(unchanged constraint).

### `merge_workflow_overlay` (hooks)

**Algorithm:**
```
1. Final assembly (step 8) adds two kwargs:
   agent=base.agent if base is not None else None
   env=base.env if base is not None else None
   (same objects — verbatim, never rebuilt; exactly as profile/build/memory)
2. No other change: no merge helper reads document-level globals; the
   constraint "never read a contribution's globals" holds by construction
```

**Edge cases:** empty base + contributions → workflow None (unchanged) or a
contributed document (globals of the CONTRIBUTIONS are still not read — the
workflow-level assembly reads only `base`).

### `apply_skip_stages` (pipeline)

**Algorithm:**
```
1. Step 4 rebuild adds:
   agent=workflow.agent if workflow is not None else None
   env=workflow.env if workflow is not None else None
2. Docstring enumeration of the synthesized-default document gains agent/env None
```

### `run_pipeline` steps 14 and 20 (pipeline)

**Algorithm:**
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

**Errors:** unchanged boundaries (config load/delivery, damaged payload, compile
errors). No new error path.

**Edge cases:**
- `no_workflow` / silent miss / no file: `overlay.workflow` is None or agent/env
  None → configuration values feed the same points; behavior byte-identical to
  today.
- Workflow env carries an engine-variable key (e.g. `GOGA_WORKFLOW`) → dropped
  silently with the same comprehension (it only ever applies to the afm subprocess
  env parameter).

### `write_afm_config` / `apply_stage_env_wrappers` (pipeline)

**Algorithm:** logic unchanged — docstring/param-description alignment only (the
`agent`/`global_agent` parameters now document the effective global agent). The
assistant fallback line `target_agent = declaration.agent if
declaration.agent is not None else agent` already implements the new law.

### `merge_workflow_build` (build) — rewrite

**Responsibility**: pure 3-source per-pass layering onto an existing build section.

**Algorithm:**
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

`_merge_env(base, *overlays)` gains a variadic form (or is simply chained twice):
later layers win per key; `None` overlays are skips.

**Errors:** none raised here (the no-build-section guard lives in `build` step 4,
before the call — unchanged).

**Edge cases:**
- `build_block=None` + globals → the globals still layer (root agent/env; review
  construction when a global reaches the review pass).
- `build: {agent: ""}` (or `review.agent: ""`, `review.additional.agent: ""`) —
  the build-block agent fields are NOT empty-normalized at parse, so an
  authored empty string falls through to the global, else the configuration
  field, exactly as the block-only law does today (`block or config`).
- Both globals None → field-identical to the block-only overlay (parity pinned by
  a test); with `build_block=None` too → field-identical copy of the input.
- Config review agent set + global set (no block) → global WINS (block > global >
  config — the fixed header law).
- The global env is the ONLY cross-pass env base: config root env never reaches
  review/additional (secret-safety invariant preserved).

### `build` step 4 (build)

**Algorithm:**
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

### `resolve_run_settings` (build)

No algorithm change. Docstring alignment: "the workflow global run settings and
``build:`` overlay, when any, already applied by the caller".

## Cross-cutting Concerns

- **Error handling**: structural errors stay at parse time (`WorkflowSyntaxError`,
  five new exact messages); strict pre-run errors stay at the delivery points
  (illegal env keys at wrapper generation — existing POSIX check; unresolvable
  assistant agent — existing); clean-error boundaries of `run_pipeline`/`build`
  unchanged. No new exception types anywhere.
- **Validation**: parse-time structural only for the two keys (no agent-name
  validation — a missing wrapper surfaces at invocation, as `profile`/stage
  agents today); env key SHAPE validation deliberately not at parse (delivery
  points own it, per `parse-workflow.md`).
- **Logging**: nothing new logged; the constraint "do not print or log env values"
  extends to the global env by existing wording; `logger.debug("pipeline run
  composed")` payload unchanged.
- **Caching**: none.
- **Concurrency**: none (single-threaded coordination paths).

## Usages Analysis

### `convention` — `.goga/usages/conventions.md`
- **What it provides**: Python code rules — kw_only dataclasses, relative imports,
  Google docstrings, blank-line blocking, mirror-structured tests
  (`tests/<pkg>/test_<module>.py`), pytest naming `test_<what>_<scenario>`.
- **Where used**: every changed file and every new test.
- **Why chosen**: root practice of all four cells.
- **How exactly**: two new kw_only fields; `_validate_top_level_agent` Google
  docstring; tests in the existing mirror files; `pytest tests/ -x` green.

### `jinja2` — `.goga/usages/cooks/jinja2.md` (workflow cell)
- **What it provides**: whole-file rendering law (render before parse).
- **Where used**: unchanged `render_workflow`; the two keys ride it by construction.
- **Why chosen**: the globals must render like the rest of the file (ADR).
- **How exactly**: no code change; one chain-level test pins a profile-rendered
  global env value reaching the document.

### `afm` — `.goga/usages/cooks/afm.md` (pipeline cell)
- **What it provides**: afm configuration-file contract (client command, static
  fields, collaboration section).
- **Where used**: `write_afm_config` — only the `agent` parameter's source changes.
- **Why chosen / how**: unchanged contract; the client command resolves the same
  wrapper path from a possibly-different agent name.

### `ralphex`, `agent-wrappers` — `.goga/usages/cooks/*` (build cell)
- Unchanged consumption; the layered values flow through the existing
  `resolve_run_settings` → `write_role_env_wrappers` machinery.

### Imported Usages
- `extra-env-carriage` from `goga/docker` — path `goga/docker/.usages/extra-env-carriage.md`.
  The ladder's "task env layer (effective)" now composes as
  `pipeline.env ⊕ workflow global env` in the pipeline domain and as the layered
  pass env in the build domain; the practice's own example ("for example
  `pipeline.env`") stays valid — no edit needed (verified during trace).
- `resolve-wrapper-path` from `goga/agents` — unchanged; one more caller-side
  source for the agent name.
- `parse-workflow`, `load-workflow`, `profiles`, `assistants`, `memory` from
  `goga/pipeline/workflow` — read; `parse-workflow.md` already documents the new
  keys (updated by the apply stage, verified consistent).
- `per-tool-delivery`, `declaring-actions`, `registering-hooks` from `goga/hooks`,
  `checkpoints` from `goga/pipeline/hooks`, `compile-flow`/`collaboration-emission`
  from `goga/pipeline/compiler`, `project-configuration` from `goga/config`,
  `run-flow` from `goga/afm`, `topic-paths`/`topic-statuses` from `goga/history`,
  `ensure-in-docker`/`home-profiles-carriage` from `goga/docker` — all consumed
  exactly as before; no law of any of them changes.

## `.usages/` Update

### Cell: `goga/pipeline/workflow`
- **`parse-workflow.md`** → status: current (12-key list, global-run-settings
  section, empty-workflow rule — verified against the final contracts).

### Cell: `goga/pipeline/hooks`
- **`checkpoints.md`** → status: current (verbatim-globals bullet verified).

### Cell: `goga/pipeline`
- **`run-pipeline.md`** → status: current (Workflow-global run settings section,
  afm-config and env-ladder wording verified).
- **`per-stage-env.md`** → status: current (ambient global env paragraph verified).

### Cell: `goga/build`
- **`workflow-layering.md`** → status: current (4-layer order; states block >
  global > config, which the Phase-3 CODEMANIFEST fix now matches).

No new `.usages/` files (no new functional domain); no CODEMANIFEST `Usages`
references point at own `.usages/` files (rule respected).

## Test Stack Trace

### General Setup

- Conventions: mirror structure, pytest, `tmp_path` for file I/O, seams via
  `monkeypatch` where subprocesses/files are involved (the existing
  `tests/pipeline/conftest.py` seam helpers for `run_pipeline`).
- Parse-level tests: plain string inputs, no fixtures.
- Merge-level tests: plain dataclass literals.
- Run-level tests: the existing `_patch_seams` harness of
  `tests/pipeline/test_run_pipeline.py` (mocked `run_flow`, `compile_flow`,
  `write_afm_config` seams where the existing tests already do).

### Source File Registry

- `goga/pipeline/workflow/workflow_document.py`, `parse_workflow.py`
- `goga/pipeline/hooks/overlay.py`
- `goga/pipeline/run_pipeline.py`, `apply_skip_stages.py`, `afm_config.py`,
  `stage_env_wrappers.py` (docstrings)
- `goga/build/workflow_build.py`, `build.py`, `run_settings.py` (docstring)

---

### Positive Tests

#### `test_agent_parses_into_document_field`

**Setup**: none (pure parser).
**Input**: `"stages:\n  build:\n    skip: true\nagent: claude\n"` to `parse_workflow`.
**Trace**:
```
parse_workflow(text)
  → yaml.safe_load                     # dict with stages, agent
  → _extract_top_level                 # agent branch → _validate_top_level_agent("claude")
    returns: "claude"
  → _build_stages / empty-workflow rule  # stages non-empty → passes
  → WorkflowDocument(..., agent="claude", env=None)
  → assert document.agent == "claude" and document.env is None
```
**Assertions**: `document.agent == "claude"`; `document.env is None`; the other
fields parse as before (`document.stages["build"].skip is True`).
**Sufficiency**: pins the carriage of the new scalar key end to end — the core
regression this feature exists for.

#### `test_env_parses_into_document_field`

**Setup**: none.
**Input**: `"prompt: hi\nenv:\n  GOGA_LOG_LEVEL: info\n  MODEL: '{{ m }}'\n"` (a
literal rendered-looking value — parse accepts any str).
**Trace**: `parse_workflow → _extract_top_level → _validate_stage_env("workflow", …)`
returns the map → document carries it.
**Assertions**: `document.env == {"GOGA_LOG_LEVEL": "info", "MODEL": "{{ m }}"}`;
`document.agent is None`.
**Sufficiency**: pins the map carriage and proves parse does NOT render/interpret
values.

#### `test_agent_alone_and_env_alone_are_valid_workflows`

**Setup**: none.
**Input**: `"agent: claude\n"` and `"env:\n  A: b\n"` (two calls).
**Trace**: empty-workflow condition — `agent` (resp. `env`) non-None short-circuits
the emptiness check → document built.
**Assertions**: both parse without raising; `document.agent == "claude"` /
`document.env == {"A": "b"}`.
**Sufficiency**: pins the content rule — the acceptance criterion "a workflow
consisting of `agent` alone is valid"; prevents a future regression to treating
the globals as activation-like non-content (`profile`).

#### `test_workflow_global_env_renders_from_profile_data`

**Setup**: a workflow text with `env: {MODEL: "{{ agent_cfg.model }}"}` and a
profile dict `{"agent_cfg": {"model": "opus"}}` (existing `load_workflow` chain
fixtures in `tests/pipeline/workflow/conftest.py`).
**Input**: `load_workflow(path, cli_profile=…)` with the written file.
**Trace**: `load_workflow → peek (raw text) → render_workflow(jinja2) → parse_workflow`
— the rendered text carries `MODEL: opus` → document.env carries it.
**Assertions**: `loaded.document.env == {"MODEL": "opus"}`.
**Sufficiency**: pins the ride-the-rendering law (globals compose with contributor
profiles) without any rendering-code change.

#### `test_overlay_preserves_global_run_settings_verbatim`

**Setup**: `base = WorkflowDocument(prompt="p", agent="claude", env={"A": "1"})`;
one contribution whose document sets `agent="tool-agent"`, `env={"B": "2"}` and a
stage field.
**Input**: `merge_workflow_overlay(base, [contribution])`.
**Trace**: merge helpers never read document globals → final assembly carries
`agent=base.agent`, `env=base.env` → the contribution's globals are discarded.
**Assertions**: `overlay.workflow.agent == "claude"`;
`overlay.workflow.env == {"A": "1"}`; the contribution's stage field DID merge
(merge otherwise works).
**Sufficiency**: pins the author-territory law — a tool can neither supply nor
override globals (ADR rejection of tool-contributable globals).

#### `test_skip_rebuild_preserves_global_run_settings`

**Setup**: `workflow = WorkflowDocument(prompt="p", stages={"a": …}, agent="claude",
env={"A": "1"})`.
**Input**: `apply_skip_stages(workflow, ["a"])`.
**Trace**: rebuild carries `agent`/`env` from the input verbatim.
**Assertions**: result `.agent == "claude"`, `.env == {"A": "1"}`,
`.stages["a"].skip is True`.
**Sufficiency**: pins "a rebuild that drops them would silently revert a
skip-driven run to configuration-level globals".

#### `test_run_pipeline_workflow_global_agent_feeds_all_three_consumers`

**Setup**: `_patch_seams` harness; config `pipeline=PipelineConfig(agent="codex",
env={})`; workflow file with `agent: claude` and one stage without env; seams
record `write_afm_config` args and the `run_flow` env; an assistant in the catalog
without its own agent (optional variant).
**Input**: `run_pipeline(name, …, workflow="w")`.
**Trace**: resolve → skip merge → overlay → compile → step 14:
`effective_agent = "claude"` (workflow carries one) →
`apply_stage_env_wrappers(…, "claude", …)` and `write_afm_config("claude", …)`;
assistant fallback inside the config write resolves `claude`.
**Assertions**: the `write_afm_config` seam received `agent == "claude"`; the
written config's client command resolves the `claude` wrapper (or the seam arg is
asserted where the file write is mocked); `pipeline.agent` "codex" appears nowhere.
**Sufficiency**: pins the single-value-three-consumers law and the override of the
configuration agent.

#### `test_run_pipeline_launch_env_base_merges_workflow_env_keywise`

**Setup**: seams; `pipeline=PipelineConfig(agent=None, env={"A": "1", "B": "1"})`;
workflow with `env: {B: "2", C: "3"}`; `GOGA_EXTRA_ENV` unset.
**Input**: `run_pipeline(…)`.
**Trace**: step 20 — base `{"A": "1", "B": "2", "C": "3"}` → no payload → engine
filter (none collide) → `run_flow(env=…)` receives the base.
**Assertions**: the `run_flow` seam env == `{"A": "1", "B": "2", "C": "3"}`.
**Sufficiency**: pins the key-wise merge law (workflow wins per key, config keys
survive) — the acceptance criterion for the launch env.

#### `test_run_pipeline_cli_entries_stay_above_and_engine_keys_drop`

**Setup**: as above but workflow `env: {B: "w", GOGA_WORKFLOW: "evil"}` and
`GOGA_EXTRA_ENV` encoding `{B: "cli"}`.
**Input**: `run_pipeline(…)`.
**Trace**: base `{B: "w", GOGA_WORKFLOW: "evil"}` → payload above → engine-set
filter drops `GOGA_WORKFLOW` silently.
**Assertions**: `run_flow` env has `B == "cli"` and NO `GOGA_WORKFLOW` key from the
workflow (the inherited launch value stands; no `GOGA_PROFILE` unless a profile
resolved).
**Sufficiency**: pins the ladder above the new layer — a workflow cannot escalate
into engine carriage variables.

#### `test_merge_workflow_build_four_layer_agent_precedence`

**Setup**: `config = BuildConfig(agent="cfg-root", env={},
review=ReviewConfig(agent="cfg-rev", env={}, additional=AdditionalReviewConfig(
agent="cfg-add", env={})))`; `block = WorkflowBuild(review_agent="blk-rev")`;
globals `("g-global", None)`.
**Input**: `merge_workflow_build(config, block, "g-global", None)`.
**Trace**: root = block.agent(None) → global("g-global"); review =
blk-rev (block wins); additional = block(None) → global("g-global") → wait —
additional = block?.review_additional_agent (None) → global → "g-global".
**Assertions**: root agent `"g-global"`; review agent `"blk-rev"`; additional
agent `"g-global"` (per-pass independence: block > global > config at every pass).
**Sufficiency**: pins the per-pass resolution — especially that the global
OVERRIDES a set config field (the law the Phase-3 fix disambiguated).

#### `test_merge_workflow_build_env_layering_config_global_block`

**Setup**: config env `{"R": "cfg", "S": "cfg"}`, review env `{"X": "cfg"}`,
additional env `{}`; `global_env={"S": "glob", "T": "glob"}`; block
`env={"R": "blk"}`, `review_env={"X": "blk"}`.
**Input**: `merge_workflow_build(config, block, None, global_env)`.
**Trace**: root env = cfg ⊕ glob ⊕ blk → `{"R": "blk", "S": "glob", "T": "glob"}`;
review env → `{"X": "blk", "S": "glob", "T": "glob"}`; additional env →
`{"S": "glob", "T": "glob"}`.
**Assertions**: the three maps above; inputs unmutated.
**Sufficiency**: pins the key-wise 3-layer env law per pass — including the global
env as the only cross-pass base.

#### `test_merge_workflow_build_globals_with_none_block`

**Setup**: `config = BuildConfig(agent="cfg-root", env={"A": "1"}, review=None)`;
`build_block=None`, `global_agent="g"`, `global_env={"E": "2"}`.
**Input**: `merge_workflow_build(config, None, "g", {"E": "2"})`.
**Trace**: root agent "g", root env `{"A": "1", "E": "2"}`; review constructed
(globals reach it): agent "g", env `{"E": "2"}`, additional constructed with env
`{"E": "2"}`.
**Assertions**: as traced; `config.review` of the INPUT still None (purity).
**Sufficiency**: pins "the layering applies whenever a workflow is in effect — a
document without a build: block still carries its globals".

#### `test_merge_workflow_build_globals_none_matches_block_only_overlay`

**Setup**: any config + block; call twice — once with the new signature
`(config, block, None, None)`, once comparing against the expected field values of
the historical block-only law.
**Input**: `merge_workflow_build(config, block)`.
**Trace**: pass-through of unset layers → identical field values.
**Assertions**: every field equals the block-only expectation (root agent
block.agent or config.agent; env two-layer; review/additional construction only
from block fields).
**Sufficiency**: pins the backward-compatibility parity requirement.

#### `test_build_layers_globals_without_build_block`

**Setup**: `tests/build` harness; config with build section, `review=None`;
workflow file `agent: g\nenv: {E: "2"}\n` (no `build:` block); CLI options minimal.
**Input**: `build(plan, config, cli_options)` with the pass launches mocked.
**Trace**: step 2 resolves the workflow → step 4 (new condition) merges with
`build=None` → `resolve_run_settings` over the layered config → tasks agent "g".
**Assertions**: the resolved settings/mocked wrapper composition carries
`agent="g"` and env layer `{"E": "2"}`; exit path proceeds as with a normal run.
**Sufficiency**: pins the widened step-4 condition at the orchestration level.

#### `test_build_cascade_runs_from_layered_root`

**Setup**: config `BuildConfig(agent="cfg-root", review=ReviewConfig(agent=None))`;
workflow global `agent: g`, no block.
**Input**: `merge_workflow_build` then `resolve_run_settings(layered, {})`.
**Trace**: layered root agent "g", layered review agent None → cascade: review
agent = layered root "g".
**Assertions**: `settings.review.agent == "g"`; `settings.tasks.agent == "g"`.
**Sufficiency**: pins "the agent-inheritance cascade keeps working — from the
effective, post-override root" (ADR).

---

### Negative Tests

#### `test_non_str_agent_raises_structural_error`

**Setup**: none.
**Input**: parametrized `"agent: 5"`, `"agent: [claude]"`, `"agent: {n: c}"`,
`"agent:"` (YAML null — an empty key is NOT absence; an authored `""`
normalizes to None, a missing value is a structural error; the same law as
`profile:`), each with a `prompt:` present so only the agent branch fails.
**Trace**: `_validate_top_level_agent` → non-str → raise.
**Assertions**: `pytest.raises(WorkflowSyntaxError, match="non-str value in
workflow.agent")` for every case.
**Sufficiency**: pins the scalar structural law (acceptance criterion).

#### `test_non_mapping_env_raises` / `test_non_str_env_key_raises` / `test_non_str_env_value_raises`

**Setup**: none.
**Input**: `env: "x"`; `env: {1: a}`; `env: {A: 5}` (each with a `prompt:` present).
**Trace**: `_validate_stage_env("workflow", …)` raises the scope-interpolated
message.
**Assertions**: exact matches `"non-mapping env in workflow"`,
`"non-str key in workflow.env"`, `"non-str value in workflow.env.A"`.
**Sufficiency**: pins the three map-law messages verbatim (the contract pins the
exact strings — including the `KEY` interpolation).

#### `test_unknown_top_level_key_message_lists_agent_and_env`

**Setup**: none.
**Input**: `"prompt: hi\nagents: x\n"` (a plausible typo).
**Trace**: unknown-key branch joins the 12-key tuple.
**Assertions**: message == `"unknown key in workflow: agents; valid keys: prompt,
stages, extend, memory, profile, build, assistants, delegation, repeat, gates,
agent, env"`.
**Sufficiency**: the enumeration is user-facing grammar documentation; existing
substring pins stay green — strengthening them to the full 12-key fragment is
recommended (see registry).

#### `test_empty_workflow_message_names_agent_and_env`

**Setup**: none.
**Input**: `"profile: default\n"`.
**Trace**: all content keys None/empty (profile never counts) → raise.
**Assertions**: exact new message ending "… the gates block, the agent key, or the
env block".
**Sufficiency**: pins the shifted emptiness error text; guards the profile-is-not-
content law against drift while the message grows.

---

### Edge Case Tests

#### `test_blank_agent_normalizes_to_absence`

**Input**: `"agent: '   '\nstages:\n  a:\n    skip: true\n"`.
**Trace**: whitespace-only → None; stages present → valid document.
**Assertions**: `document.agent is None`.
**Sufficiency**: pins the profile-pattern normalization.

#### `test_blank_agent_does_not_rescue_empty_workflow`

**Input**: `"agent: '  '\n"` alone.
**Assertions**: raises the empty-workflow error (absence is not content).
**Sufficiency**: prevents an "empty-after-normalization" hole.

#### `test_empty_env_map_equals_absence`

**Input**: `"prompt: hi\nenv: {}\n"`.
**Assertions**: `document.env is None` (NOT `{}` — the wrapper/merge `is not None`
checks rely on it).
**Sufficiency**: pins the stage-env-pattern empty law and the deliberate
divergence from the assistant explicit-clear pattern.

#### `test_skip_synthesis_with_none_workflow_carries_agent_env_none`

**Input**: `apply_skip_stages(None, ["a"])`.
**Assertions**: result `.agent is None`, `.env is None`, `.stages["a"].skip`.
**Sufficiency**: pins the synthesized-document contract for workflow-less skips.

#### `test_run_pipeline_without_workflow_global_falls_back_to_pipeline_agent`

**Setup**: workflow WITHOUT `agent:`; `pipeline.agent="codex"`.
**Assertions**: the `write_afm_config`/wrapper seams receive `"codex"` — behavior
identical to today.
**Sufficiency**: pins the no-regression fallback (acceptance: "with it absent,
`pipeline.agent` applies exactly as today").

#### `test_merge_workflow_build_never_mutates_inputs`

**Setup**: frozen config models; deep field snapshot before.
**Input**: any merge with all layers set.
**Assertions**: inputs field-identical after the call; result is a new object.
**Sufficiency**: the purity requirement (frozen models make mutation attempts
crash — the test pins the new-object result and input equality).

#### Existing exact-message assertions to UPDATE (registry)

- `tests/pipeline/workflow/test_parse_workflow_gates.py` (~line 297),
  `test_parse_workflow_memory.py` (~235), `test_parse_workflow_logic.py` (~581),
  `test_parse_workflow_contract.py` (~229): valid-keys enumerations are
  substring (`in`) asserts that keep passing — strengthen each to the new
  full 12-key fragment (recommended, not required for green).
- `tests/pipeline/workflow/test_parse_workflow_assistants.py` (~82) and
  `test_parse_workflow_repeat.py` (~87): empty-workflow message gains
  ", the agent key, or the env block".
- `tests/pipeline/workflow/test_parse_workflow_memory.py` (~378,
  `test_parse_workflow_empty_workflow_message_mentions_memory_block`) and
  `test_parse_workflow_logic.py` (~1353, the `{}` / profile-only / build-only
  test): the SAME empty-workflow message, pinned by EXACT equality
  (`str(exc_info.value) == ...`) — both gain
  ", the agent key, or the env block" or the asserts fail.
- `tests/pipeline/workflow/test_workflow_document_contract.py` (~64,
  `test_workflow_document_field_order_fixed`): the expected field-order list
  gains the two closing names — `prompt, stages, extend, memory, profile,
  build, assistants, delegation, repeat, gates, agent, env` (12 fields).
- `tests/build/test_workflow_build_merge_contract.py`: signature pin updated to
  the 4-parameter form (`["config", "build_block", "global_agent",
  "global_env"]` with the two defaulted).
- `tests/pipeline/test_run_pipeline.py`: any pin of `config.pipeline.agent`
  reaching the seams stays valid (fallback unchanged); add the workflow-global
  variants above rather than rewriting existing ones.

## Additional Instructions for the Implementation Agent

- Implement in dependency order: workflow → hooks → pipeline → build; run
  `goga lint` (must stay 93 cells, 0 errors) and `pytest tests/ -x` after each cell.
- Reuse `_validate_stage_env("workflow", value)` for the top-level env — its
  messages are already byte-identical to the contract; add only
  `_validate_top_level_agent` (mirror of `_validate_top_level_profile`).
- Do NOT touch `goga/pipeline/compiler`, `goga/agents/wrapper`, `goga/config`, or
  any `goga/commands/*` — the contract-drift guarantee of the apply stage must
  survive; the public facades (`run_pipeline`, `build`, `WorkflowDocument`
  construction with keyword defaults) stay backward compatible.
- Renumber the step comments in `run_pipeline.py` to the CODEMANIFEST's 1..24
  (the inline comments currently carry the old numbering).
- Align docstrings only where semantics changed: `write_afm_config.agent`,
  `apply_stage_env_wrappers.global_agent`, `resolve_run_settings` opening note,
  `merge_workflow_overlay`/`apply_skip_stages` verbatim-set notes; no behavior
  hides behind a docstring change.
- Never log or print env values; engine-variable keys drop silently everywhere.
- De-stamping `.goga/profiles/default.yml` (~20 repeated stage stamps) is an
  explicitly deferred follow-up — do not do it in this task; it doubles as the
  end-to-end validation scenario afterwards.
- The empty-map-equals-absence law (global env) and the authored-empty-clears law
  (assistant env) coexist deliberately — do not "unify" them.
