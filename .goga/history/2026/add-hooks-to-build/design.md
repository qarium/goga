# Design Document: `add-hooks-to-build`

Complete architectural specification for implementing the materialized
contracts (post-`apply-architecture` CODEMANIFEST state, plus the contract
fixes applied during this design stage) as Python code. The implementation
order and the per-file details below are fully elaborated; the implementing
agent executes them without further design decisions.

Normative inputs, in order: the CODEMANIFEST files listed under Contract
Changes (authoritative), `arch.md` (plan), `adr.md` (decisions), `task.md`
(success criteria SC1–SC10), and the practices listed under Usages Analysis.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/config/project/CODEMANIFEST` — the build section is restructured to
  the two-part form: `BuildConfig` reshaped (root tasks-pass fields +
  `review: ReviewConfig | None`), `TaskExecutorConfig` and
  `ReviewExecutorConfig` deleted, `ReviewConfig` and `AdditionalReviewConfig`
  added, `load_project_config` algorithm steps 6–7 rewritten; header
  Annotations carry the two-part stance.
- `goga/config/CODEMANIFEST` — facade embeddings updated mechanically:
  `TaskExecutorConfig`/`ReviewExecutorConfig` dropped, `ReviewConfig`/
  `AdditionalReviewConfig` embedded.
- `goga/ralphex/CODEMANIFEST` — `run_ralphex` option table updated: bool
  flags `tasks_only`/`review`/`external_only` (`-e`); scalars gain
  `max_external_iterations`; `worktree`/`skip_finalize` removed; the
  zero-valued external-flags rule added (`review_patience` 0 and
  `max_external_iterations` 0 ARE passed).
- `goga/hooks/catalog/CODEMANIFEST` — five additive `build` records
  (`validate_build` hard; `build_started`, `pass_started`, `pass_completed`,
  `build_completed` soft).
- `goga/build/hooks/CODEMANIFEST` — NEW cell: 13 types (7 facts, 5 contexts,
  1 checkpoint surface) + `.usages/checkpoints.md`.
- `goga/build/CODEMANIFEST` — new imports (`goga/build/hooks`, `goga/history`),
  `build()` rewritten to the 12-step checkpoint cycle, `main()` argparse
  surface updated, `resolve_run_settings`/`RunSettings`/`PassSettings`/
  `PassSettings::ReviewPassSettings`/`compose_pass_options` added,
  `resolve_review_options`/`ReviewOptions` deleted, `validate_review_config`/
  `sync_ralphex_defaults`/`write_ralphex_config`/`run_build_pass`/
  `move_completed_plan` re-signatured.
- `goga/commands/build/CODEMANIFEST` — flag surface without
  `--worktree`/`--skip-finalize`; the agent guard repointed to
  `config.build.agent`; the two-pass × worktree guard (step 2.3) deleted;
  the task env removed from the container env-file.
- `goga/onboarding/generator/CODEMANIFEST` — snapshot→YAML mapping repointed
  to the two-part build root (`build.agent`, `build.env`) — fixed during this
  design stage (user-approved).
- `goga/commands/config/CODEMANIFEST` — dot-notation examples repointed to
  live keys (`build.agent`, `build.review.strategy`) — fixed during this
  design stage (user-approved).

### New Entities

Zone `goga/build/hooks` (all `@dataclass(kw_only=True)`, non-frozen —
mutability is closed by the delivery proxy, following the
`goga/pipeline/hooks` precedent):

- `WorkIdentity(branch, slug=None, year=None)` — `facts.py`
- `BuildMoment(plan, work, dry_run)` — `facts.py`
- `StageFacts(stage, agent, env, max_iterations, session_timeout, idle_timeout, wait, roles, base_ref, strategy, finalize, additional)` — `facts.py`
- `AdditionalFacts(agent, patience, max_iterations)` — `facts.py`
- `RelocationOutcome(moved, destination)` — `facts.py`
- `Violation(tool, hook, reason)` — `facts.py`
- `GateVerdict(violations)` with `approved` property — `facts.py`
- `BuildValidation(moment, tasks, review, skip)` with `veto(reason)` — `contexts.py`
- `BuildStarted(moment, tasks, review, skip)` — `contexts.py`
- `PassStarted(moment, facts)` — `contexts.py`
- `PassCompleted(moment, facts, exit_code)` — `contexts.py`
- `BuildCompleted(moment, exit_code, stages, relocation, statuses)` — `contexts.py`
- `BuildHooks()` — `events.py`: `validate_build`, `emit_build_started`,
  `emit_pass_started`, `emit_pass_completed`, `emit_build_completed`

Cell `goga/build`:

- `resolve_run_settings(config: BuildConfig, cli_options: dict) -> RunSettings` — `run_settings.py` (new file)
- `RunSettings(skip, tasks, review)` — `run_settings.py` (frozen, kw_only)
- `PassSettings(agent, env, max_iterations, session_timeout, idle_timeout, wait)` — `run_settings.py` (frozen, kw_only)
- `PassSettings::ReviewPassSettings(roles, base_ref, strategy, finalize, additional)` — `run_settings.py` (frozen, kw_only)
- `compose_pass_options(settings, stage) -> options` — `pass_options.py` (new file)

Cell `goga/config/project`:

- `ReviewConfig(skip, agent, env, roles, base_ref, strategy, finalize, additional, session_timeout, idle_timeout, wait)` — `config.py` (frozen, kw_only)
- `AdditionalReviewConfig(agent, patience, max_iterations)` — `config.py` (frozen, kw_only)

### Changed Entities

- `BuildConfig(agent, env, max_iterations, session_timeout, idle_timeout, wait, prompts_dir, agents_dir, proxy, hosts, review)` — two-part form; `worktree`, `skip_finalize`, `codex_review`, `task_executor`, `review_executor` fields deleted.
- `load_project_config()` — build-block extraction rewritten (two-part, retired keys silently ignored).
- `build(plan, config, cli_options)` (goga/build) — 12-step checkpoint cycle.
- `main()` (goga/build `__main__.py`) — argparse surface: `--skip-review`/`--no-skip-review` pair, `--base-ref`, `--review-patience`, `--dry-run`, `--skip-manifest-check`, `--session-timeout`, `--idle-timeout`, `--wait`, `--max-iterations`; no `--worktree`/`--skip-finalize`.
- `validate_review_config(settings)` — re-signatured from `(config, review)` to `(settings: RunSettings)`; new checks (strategy whitelist, additional-agent wrapper).
- `sync_ralphex_defaults(config, settings)` — reads roles and the finalize prompt from `RunSettings`; materializes the finalize step file.
- `write_ralphex_config(settings, wrapper_path)` — external-review surface + `finalize_enabled`.
- `run_build_pass(plan, settings, options, wrapper_path, dry_run, env)` — carries `RunSettings` instead of `BuildConfig`.
- `move_completed_plan(plan, outcome, dry_run) -> RelocationOutcome` — returns the outcome facts.
- `run_ralphex` (goga/ralphex) — flag table per above.
- `build(...)` (goga/commands/build) — flag removals, guard repoint, env-file without the task env.
- `_build_config_document` (goga/onboarding/generator, code change only) — emits the two-part build root.

### Deleted Entities

- `TaskExecutorConfig`, `ReviewExecutorConfig` (goga/config/project) — replaced by the two-part `BuildConfig` + `ReviewConfig`.
- `resolve_review_options`, `ReviewOptions` (goga/build, file `review_options.py`) — superseded by `resolve_run_settings`/`RunSettings`; **delete the file**.
- CLI `--worktree` / `--skip-finalize` (host and in-container) and config keys `worktree`, `skip_finalize`, `codex_review`, `task_executor`, `review_executor` — breaking removals, no compatibility paths.

### Usages and Annotations Changes

- `goga/build` imports `checkpoints` (goga/build/hooks), `topic-paths` + `topic-statuses` (goga/history); header Annotations describe the checkpoint fact resolution (branch, hosting, statuses) and the always-two-pass stance.
- `goga/build/hooks` imports `declaring-actions`, `per-tool-delivery`, `registering-hooks` (goga/hooks) and declares the domain-local hard-delivery deviation in its header.
- `goga/commands/build` Annotations: flag surface paragraph rewritten (no worktree/skip-finalize; `--review-patience` addresses `build.review.additional.patience`; the task env is not written into the env-file).
- Project practice `.goga/usages/cooks/ralphex.md` (updated during grooming): always-two-pass wording, external-review surface, finalize step, `--base-ref` source key.
- Usage-file artifacts created/rewritten by `apply-architecture`: `goga/build/hooks/.usages/checkpoints.md`, `goga/build/.usages/registering-hooks.md`, rewritten `goga/build/.usages/build-usage.md`, rewritten build chapter of `goga/config/.usages/project-configuration.md`, updated `goga/commands/build/.usages/build.md`.
- `.goga/config.yml` — this repository's build section already migrated to the two-part form (dogfooding; landed by `apply-architecture`, verified `yaml.safe_load`-clean).

## Applied Fixes

### Fixed CODEMANIFEST Defects

All fixed during this design stage, user-approved (answer: fix all three + the
trace-discovered import gap):

- `goga/onboarding/generator/CODEMANIFEST`: `build.task_executor.agent → build.task_executor.agent` / `build.task_executor.env → build.task_executor.env` → `build.agent → build.agent` / `build.env → build.env` (reason: interface↔implementation drift — the generator would emit a silently-disabled build section under the new loader).
- `goga/commands/config/CODEMANIFEST`: examples `build.task_executor.agent build.worktree` → `build.agent build.review.strategy`, in both the `options` annotation and the output-format sample (reason: stale references to deleted keys).
- `goga/build/CODEMANIFEST`: `Imports → goga/history` gained `resolve_topic_dir`, and the annotations (global fact-resolution paragraph + `build()` step 4) now reference it (reason: interface↔interface gap — the topic-hosting decision of step 4 was unimplementable from the declared import surface; the `topic-paths` practice was imported without the type it documents).
- `goga/ralphex/.usages/run-ralphex.md`: removed `worktree` from the options example, replaced the conditional two-pass wording with the always-two-pass form, added `external_only` (`-e`) and `max_external_iterations` to the parameter contract, documented the zero-valued external-flags rule, and repointed the anti-pattern `TaskExecutorConfig` mention to `ReviewConfig` (reason: practice file lagged the updated CODEMANIFEST).

`goga lint` after all fixes: **79 cells, 0 errors**.

## Entity Interaction and Data Flow

### Interaction Diagram

```
goga/commands/build (host CLI, click)
  │  guards: config.build present, config.build.agent set
  │  env-file: home.env < git identity < CLI -e (+proxy)   [NO build env]
  │  docker run ... python -m goga.build <plan> <cli_flags>
  ▼
goga/build  build()  ── in-container orchestrator ─────────────────────────────┐
  │ 0  git pre-check (uncommitted CODEMANIFEST → exit 1, no events)            │
  │ 1  resolve_run_settings(config.build, cli_options) → RunSettings           │
  │ 2  validate_review_config(settings)   ──► resolve_wrapper_path (goga/agents)
  │ 3  sync_ralphex_defaults(config.build, settings)  [.ralphex/prompts|agents]│
  │ 4  facts: resolve_current_branch_name ── resolve_topic_dir ──► WorkIdentity│
  │           BuildMoment; StageFacts(tasks) + StageFacts(review)              │
  │ 5  BuildHooks.validate_build(...)  ──► GateVerdict                         │
  │        │ not approved → merged error, exit 1, nothing else fires           │
  │ 6  BuildHooks.emit_build_started(...)                                      │
  │ 7  tasks pass:  compose_pass_options(settings,"tasks")                     │
  │        emit_pass_started → run_build_pass → emit_pass_completed            │
  │ 8  review pass (tasks OK and not skip): compose_pass_options(,"review")    │
  │        wrapper = additional agent (short) else review agent                │
  │        emit_pass_started → run_build_pass → emit_pass_completed            │
  │ 9  move_completed_plan(...) ──► RelocationOutcome                          │
  │ 10 collect_topic_statuses(year) → statuses of work.slug                    │
  │ 11 BuildHooks.emit_build_completed(moment, exit_code, stages,              │
  │        relocation, statuses)                                               │
  └ 12 return exit code of the last executed pass                              │
                                                                               │
run_build_pass ──► write_ralphex_config(settings, wrapper) [.ralphex/config]   │
                 └► run_ralphex(plan, options, dry_run, env) (goga/ralphex)    │
                        └► subprocess: ralphex <plan> --config-dir .ralphex/   │
                                                                               │
goga/build/hooks  BuildHooks                                                   │
  ├ validate_build: staged per-tool walk over HookRegistry subscriptions       │
  │   (wrap_context + build_hook_arguments + registry.self_context),           │
  │   veto buffer per tool, Violation collection → GateVerdict                 │
  └ emit_*: emit_hook_event(registry, "build", <action>, context_for)          │
        all five addresses resolve via declared_actions() (goga/hooks/catalog) │
                                                                               │
goga/config  load_project_config → ProjectConfig(build=BuildConfig(            │
             review=ReviewConfig(additional=AdditionalReviewConfig)))          │
```

### Data Flows

**Flow A — configuration (once per run, in-container):**
`load_project_config()` reads `.goga/config.yml` (the mounted `/workspace`)
→ structural two-part extraction → `BuildConfig` (root fields verbatim,
`review: ReviewConfig | None`, `additional: AdditionalReviewConfig | None`)
→ `resolve_run_settings(config.build, cli_options)` applies CLI > config >
default > omit and root→review→additional inheritance → frozen `RunSettings`.

**Flow B — the gate (before any pass):**
`build()` resolves `WorkIdentity` (git subprocess once, then
`resolve_topic_dir` composition — no reads at the checkpoint) and both
`StageFacts` (env presence as sorted names) → `BuildHooks.validate_build`
walks the subscriptions of `build/validate_build` per tool → each tool gets a
fresh `BuildValidation` view wrapped read-only → vetoes buffer per tool →
`GateVerdict(violations)` returns to `build()` → not approved → one merged
`logger.error` (tool, hook, reason per violation) → exit 1.

**Flow C — a pass (twice per non-skipped run):**
`compose_pass_options` (pure) → pass options dict →
`run_build_pass(plan, settings, options, wrapper, dry_run, env)` →
`write_ralphex_config` rewrites `.ralphex/config` (whole file, never merged)
→ `run_ralphex` maps options to flags and launches (or prints on dry-run) →
exit code propagates unchanged → `emit_pass_completed` carries the actual
code.

**Flow D — completion (every return path of a started run):**
`move_completed_plan` → `RelocationOutcome` → `collect_topic_statuses(year)`
re-read AFTER the relocation attempt → statuses list (empty in the
branch-only form) → `emit_build_completed(moment, exit_code, stages,
relocation, statuses)` → soft emission; the exit code is already final.

### Entity Dependencies

Implementation order (leaves first — matches the dependency map; no cycles):

1. `goga/config/project` (`config.py` model, `loader.py`) → `goga/config` facade
2. `goga/hooks/catalog` (`catalog.py` — five records)
3. `goga/ralphex` (`run_ralphex.py` flag table)
4. `goga/build/hooks` (`facts.py` → `contexts.py` → `events.py` → `__init__.py`)
5. `goga/build`: `run_settings.py` → `pass_options.py` → `review_config.py` →
   `ralphex_runtime.py` → `ralphex_config.py` → `build_pass.py` →
   `plan_relocation.py` → `build.py` → `__main__.py`; delete `review_options.py`
6. `goga/commands/build` (`build.py` flag/guard/env changes)
7. `goga/onboarding/generator` (`_executor_block` docstring + two-part emission)

Runtime initialization order inside one build run: config → settings →
validation → defaults sync → facts → `BuildHooks()` (cheap; the single
`HookRegistry` builds lazily on the first checkpoint and is shared by all
five) → passes → relocation → statuses → completion.

## Code Stack Trace

### Trace: `load_project_config` (loader steps 6–7)

#### Chain
1. **Input**: `.goga/config.yml` at the project root (cwd), read + `yaml.safe_load`.
2. **Step**: top mapping guard (unchanged), `lang`/`image`/`dockerfile`, `pipeline`, then `build` block: absent → `build=None`; non-mapping → `ValueError` → checkpoint: matches step 6 (passed).
3. **Step**: root extraction — `agent` (empty/whitespace→None, non-str→ValueError), `env` (str mapping, default `{}`), `max_iterations` (int; bool→ValueError), `session_timeout`/`idle_timeout`/`wait` (agent pattern), `prompts_dir`/`agents_dir`/`proxy` (optional str), `hosts` (str mapping, default `{}`); unknown keys (incl. stale `worktree`, `task_executor`, `codex_review`) silently ignored → checkpoint: verbatim extraction, no default merge (passed).
4. **Step**: `build.review` sub-mapping: absent/null→None; non-mapping→ValueError; `skip` (bool|None), `agent` (pattern), `env` (pattern, default `{}`), `roles` (list[str]|None, empty passes verbatim), `base_ref` (agent pattern), `strategy` (empty/whitespace→None, non-str→ValueError, no whitelist), `finalize` (agent pattern — stored verbatim), `additional` (mapping: `agent` pattern, `patience` int with bool→ValueError, `max_iterations` same) → checkpoint: every field of `ReviewConfig`/`AdditionalReviewConfig` covered (passed).
5. **Output**: `ProjectConfig(build=BuildConfig(..., review=ReviewConfig(..., additional=AdditionalReviewConfig(...))))`; `codemanifest`/`lint`/`topics`/`tools`/`usages` blocks extracted exactly as today.

#### Checkpoint Summary
- Two-part shape ↔ `BuildConfig`/`ReviewConfig`/`AdditionalReviewConfig` signatures: passed.
- Retired-key silence (loader extracts known fields only): passed.
- Structural-only stance (strategy/finalize/roles semantics deferred to consumers): passed.

### Trace: `resolve_run_settings`

#### Chain
1. **Input**: `config: BuildConfig` (review may be None), `cli_options` dict (keys `skip_review`, `base_ref`, `review_patience`, `session_timeout`, `idle_timeout`, `wait`, `max_iterations` — None when the flag was absent).
2. **Step 0**: `config.review is None` → every review field unset: skip=False, agent/session knobs inherit root, `base_ref`/`roles`/`finalize` None, additional = `AdditionalReviewConfig(agent=<resolved review agent>, patience=None, max_iterations=None)` → checkpoint: `ReviewPassSettings.additional` is non-optional — always constructed (passed).
3. **Step 1**: skip = CLI `skip_review` when not None, else `ReviewConfig.skip`, else False → checkpoint: tri-state resolves (passed).
4. **Step 2**: strategy = `ReviewConfig.strategy` or `"medium"` → checkpoint: default per ADR (passed).
5. **Step 3**: tasks part — root `agent`/`env` verbatim; `max_iterations` and each session knob = the CLI value when given (not None), else the root value.
6. **Step 4**: review part — `agent`: review value when set else root; each of `session_timeout`/`idle_timeout`/`wait`: CLI value when given, else review value when set, else root; `max_iterations` NOT inherited (root-only); `env` = exactly `review.env` (never inherits); `roles`/`base_ref`/`finalize` verbatim → checkpoint: inheritance rules match `ReviewConfig` property docs with CLI precedence on top (passed).
7. **Step 5**: additional — `agent` = additional.agent when set else resolved review agent; `patience` = CLI `review_patience` when given else the additional value verbatim; `max_iterations` verbatim (None when block absent) → checkpoint: matches the ADR ("`additional.agent` inherits `review.agent`") (passed).
8. **Step 6**: base_ref = CLI value when not None (strip; empty→None), else `ReviewConfig.base_ref` → checkpoint: whitespace semantics identical to the retired `resolve_review_options` (passed).
9. **Output**: frozen `RunSettings(skip, tasks=PassSettings(...), review=ReviewPassSettings(roles, base_ref, strategy, finalize, additional, <inherited base fields>))`.

#### Checkpoint Summary
- CLI > config > default > omit for every knob: passed.
- Review env never inherits the root env (secret boundary): passed.
- Purity (no I/O, no wrapper resolution, no strategy validation): passed.

### Trace: `BuildHooks.validate_build` (the gate)

#### Chain
1. **Input**: `moment: BuildMoment`, `tasks/review: StageFacts`, `skip: bool` — values the operation already resolved.
2. **Step**: `self._ensure_registry()` — `HookRegistry()` + `build_once()` on first checkpoint; reused by every later checkpoint of the same `BuildHooks` instance → checkpoint: one registry per run (passed; `HookRegistry.build_once` is idempotent).
3. **Step**: resolve `domain="build", action="validate_build"` against `declared_actions()` → unknown address → `ValueError` (defensive; the record exists by catalog) → checkpoint: catalog record present after the additive change (passed).
4. **Step**: group `registry.subscriptions_for("build", "validate_build")` per tool preserving enumeration order; per tool build a fresh `BuildValidation(moment, tasks, review, skip)` (private `_veto: str | None = None` buffer), wrap via `wrap_context`, call each hook with `build_hook_arguments(hook, proxy, registry.self_context(tool))`; snapshot `view._veto` before each call — a change after the call attributes the veto to that subscription's name (a later veto replaces the earlier attribution) → checkpoint: proxy blocks writes but `veto()` mutates the target's buffer through the bound method — same mechanism as `WorkflowAmendment._contribution` (passed).
5. **Step**: a raising hook → record `(tool, subscription.name, str(reason))` as the tool's single crash violation and STOP that tool's remaining hooks (exactly one Violation per tool); the walk continues with the next tool → checkpoint: "a crash overrides the tool's buffered veto" and "the walk NEVER stops between tools" both satisfied (passed).
6. **Step**: a tool whose every hook returned and whose buffer is not None → `Violation(tool, attributed_hook, buffered_reason)`; buffer None → silent approval.
7. **Output**: `GateVerdict(violations)` — `approved` is `not violations`; empty when the address has no subscriptions (inert with no tool packages).

#### Checkpoint Summary
- Per-tool isolation of the veto buffer: passed (fresh view per tool).
- Exactly one Violation per tool (buffered veto XOR crash): passed.
- Verdict is data only — acting on it belongs to `build()`: passed.

### Trace: `BuildHooks.emit_*` (the four notifications)

#### Chain
1. **Input**: resolved facts from `build()` (same objects the gate saw, or pass facts / completion facts).
2. **Step**: construct the context (`BuildStarted`/`PassStarted`/`PassCompleted`/`BuildCompleted`) from the values.
3. **Step**: `emit_hook_event(self._ensure_registry(), "build", "<action>", context_for=lambda _tool: context)` — the same instance for every tool (read-only contexts, no buffer) → checkpoint: matches the `declaring-actions` pattern and the `PipelineHooks` precedent (passed).
4. **Output**: nothing returns; a failing hook warns inside the platform (soft class); the run is unaffected.

#### Checkpoint Summary
- Fire-and-forget on every return path (zero, non-zero, spawn-failure codes): passed — `build()` emits `pass_completed` immediately after each `run_build_pass` return and `build_completed` at the end of every started run.

### Trace: `compose_pass_options`

#### Chain
1. **Input**: `settings: RunSettings`, `stage: str` (`"tasks"` | `"review"`).
2. **Step (tasks)**: `{"tasks_only": True}` + each of `session_timeout`, `idle_timeout`, `wait`, `max_iterations` from `settings.tasks` when not None → checkpoint: no review-only keys, no agent (agent → wrapper), no env (env → layer) (passed).
3. **Step (review)**: mode flag — `{"external_only": True}` when `strategy == "short"`, else `{"review": True}`; plus `session_timeout`/`idle_timeout`/`wait` from the review part (inheritance already applied), `base_ref` when not None, `review_patience` from `additional.patience` when not None, `max_external_iterations` from `additional.max_iterations` when not None → checkpoint: keys ⊆ the `run_ralphex` table; 0-values kept for the two external flags (passed).
4. **Output**: `dict[str, str | int | bool]` — unset knobs absent; exactly one pass-mode flag.

#### Checkpoint Summary
- Mutual exclusivity of pass modes: passed (single flag per composition).
- Interface to `run_build_pass`/`run_ralphex`: passed (both consume the dict verbatim).

### Trace: `validate_review_config`

#### Chain
1. **Input**: `settings: RunSettings`.
2. **Step 1**: `settings.skip` → return (a skipped run validates nothing).
3. **Step 2**: each role of `settings.review.roles` against `ROLE_WHITELIST` (`quality`, `implementation`, `testing`, `simplification`, `documentation`) → first outsider raises `ValueError` naming it.
4. **Step 3**: `settings.review.env` non-empty and `settings.review.agent is None` → `ValueError` (env requires agent). Design decision for the degenerate case: a None resolved agent at step 4 raises `ValueError("no review agent resolved: set build.agent or build.review.agent")` — `resolve_wrapper_path(None)` would produce a nonsense path; the clean error honors "the error message names the invalid value". (Unreachable through the host launcher — its step-2.2 guard requires `build.agent` — but reachable on direct in-container invocation.)
5. **Step 4**: `wrapper = resolve_wrapper_path(settings.review.agent)`; `not Path(wrapper).is_file()` → `ValueError` naming agent and path.
6. **Step 5**: strategy engages the external review — `"short"` always; `"full"` when `settings.review.additional.agent` is set (always set after inheritance in practice) → resolve + existence-check the additional wrapper the same way.
7. **Step 6**: `settings.review.strategy` in `{full, medium, short}` else `ValueError` naming the value.
8. **Output**: None; runs before any side effect (before `.ralphex/` writes and before the first checkpoint).

#### Checkpoint Summary
- Check order fixed (roles → env gate → review wrapper → additional wrapper → strategy): passed.
- Constraint "do not validate the tasks agent wrapper here": passed (only the review/additional wrappers).

### Trace: `sync_ralphex_defaults`

#### Chain
1. **Input**: `config.build` (custom `prompts_dir`/`agents_dir`), `settings` (roles, finalize).
2. **Step**: sources = custom dirs when set else vendored `goga/assets/ralphex/{prompts,agents}`; missing source → `ValueError` (as today).
3. **Step**: full rewrite of `.ralphex/prompts/` and `.ralphex/agents/` (clear + copy regular files).
4. **Step**: `settings.review.roles` non-empty list and vendored prompts → filter `{{agent:X}}` lines of `review_first.txt`/`review_second.txt` + counter rewrites (existing logic, unchanged); custom prompts_dir copied as-is.
5. **Step (new)**: `settings.review.finalize is not None` → write the prompt string verbatim to `.ralphex/agents/finalize.txt` (the finalize step is a ralphex review agent carrying the `finalize.txt` prompt, per the `ralphex` practice). Materialization applies regardless of a custom `agents_dir` — the file is goga's own step artifact, not part of the source tree. Unset → nothing written; the step stays at the ralphex default (off).
6. **Output**: the `.ralphex/` prompts/agents tree on disk.

#### Checkpoint Summary
- Byte-identity of the default composition (full role set / no roles): passed (existing guard values kept).
- Finalize materialization gated on the prompt being set: passed.

### Trace: `write_ralphex_config`

#### Chain
1. **Input**: `settings: RunSettings`, `wrapper_path: str` (the pass's executor wrapper).
2. **Step**: rewrite `.ralphex/config` whole with the fixed key block:
   `claude_command = <wrapper_path>`, `claude_args = <fixed default>`,
   `preserve_anthropic_api_key = true`, `move_plan_on_completion = false`.
3. **Step**: external surface (keys derived only from `settings`):
   `strategy == "medium"` → `codex_enabled = false` (explicitly disabled);
   `full`/`short` → `codex_enabled` stays unwritten (ralphex default enabled)
   and, when `settings.review.additional.agent` is not None →
   `external_review_tool = custom` and
   `custom_review_script = resolve_wrapper_path(additional.agent)`;
   agent None (degenerate) → both stay unwritten (ralphex default codex).
4. **Step**: `settings.review.finalize is not None` → `finalize_enabled = true`; else unwritten (default false).
5. **Output**: `.ralphex/config` INI; called twice per two-pass run — same settings, only the wrapper differs.

#### Checkpoint Summary
- Key set ↔ the `ralphex` practice table: passed.
- `resolve_wrapper_path` import needed here (new import in `ralphex_config.py`): passed — the routine is on the `goga/agents` facade already imported by the cell.
- Tasks-pass config carries the review keys too — harmless: `--tasks-only` ignores every review-phase key (practice note); keeps the routine a pure function of (settings, wrapper).

### Trace: `run_build_pass` / `run_ralphex`

#### Chain
1. **Input**: plan, settings, options, wrapper, dry_run, env (tasks: root env layer; review: review env layer; None/empty → pure inheritance).
2. **Step**: `write_ralphex_config(settings, wrapper_path)` → `.ralphex/config` of this pass.
3. **Step**: `run_ralphex(plan, options, dry_run, env=env)` — bool mapping: `tasks_only`→`--tasks-only`, `review`→`--review`, `external_only`→`-e` (True emits, False/absent omits); scalar mapping: `session_timeout`, `idle_timeout`, `wait`, `max_iterations`, `review_patience`, `max_external_iterations`, `base_ref` → `--<flag> <value>`, omitted when None/"" — EXCEPT `review_patience`/`max_external_iterations`, where 0 IS emitted (`--review-patience 0`, `--max-external-iterations 0`); `worktree`/`skip_finalize` no longer exist in the table.
4. **Step**: dry_run prints `shlex.join(cmd)` to stderr (never the env layer) and returns 0; else PATH check → `subprocess.call(cmd[, env={**os.environ, **env}])`; missing binary / pre-exec rejection → clean one-line stderr message, exit 1.
5. **Output**: the ralphex exit code, propagated unchanged.

#### Checkpoint Summary
- Options keys from `compose_pass_options` all map 1:1: passed.
- Zero-valued external flags vs `value not in (None, "", 0)` drop rule: the launcher needs a per-key exception for exactly the two external flags (design-fixed).
- Secret safety (env never in argv/logs/dry-run): passed.

### Trace: `build()` (goga/build) — the full cycle

#### Chain
1. **Input**: plan path, `ProjectConfig`, cli_options.
2. **Step 0**: manifest pre-check (existing `_find_uncommitted_manifests`) — failure → `return 1`, no events (the moment never happened).
3. **Steps 1–3**: `resolve_run_settings` → `validate_review_config` (ValueError → log + `return 1`) → `sync_ralphex_defaults` (ValueError → log + `return 1`). `config.build` is guaranteed non-None by the host guard (step 2.2 of `goga/commands/build`); a build-less config invoked directly in-container is out of contract. **Step 3.5 guard**: `settings.tasks.agent is None` → `logger.error("no build agent resolved: set build.agent in .goga/config.yml")` → `return 1` — the degenerate skip-run case (`validate_review_config` returns early on skip, so the run would otherwise crash at step 7's `resolve_wrapper_path(None)` with a TypeError after `emit_build_started` fired); keeps the `registering-hooks` claim "missing agent returns before any checkpoint" true on the direct in-container path, mirroring the degenerate-case precedent of `validate_review_config` step 4.
4. **Step 4**: `branch = resolve_current_branch_name() or "unknown"`; `topic_dir = resolve_topic_dir(branch)` guarded (`ValueError` → None, an unsluggable branch hosts no topic); hosted (`topic_dir.is_dir()`) → `WorkIdentity(branch, slug=topic_dir.name, year=topic_dir.parent.name)` else `WorkIdentity(branch)`; `moment = BuildMoment(plan, work, dry_run)`; `tasks_facts`/`review_facts` per `StageFacts` (env = `sorted(env)` — names only, deterministic) with the review-only members None on tasks and `AdditionalFacts(agent, patience, max_iterations)` on review → checkpoint: no git/process reads AFTER this step (passed).
5. **Step 5**: `hooks = BuildHooks()`; `verdict = hooks.validate_build(moment, tasks_facts, review_facts, settings.skip)`; `not verdict.approved` → one merged `logger.error("build blocked by hook vetoes", extra={"violations": [f"{v.tool}/{v.hook}: {v.reason}" for v in verdict.violations]})` → `return 1`; no pass, no relocation, no further events.
6. **Step 6**: `hooks.emit_build_started(moment, tasks_facts, review_facts, settings.skip)`.
7. **Step 7**: tasks pass — `options = compose_pass_options(settings, "tasks")`; `wrapper = resolve_wrapper_path(settings.tasks.agent)`; `hooks.emit_pass_started(moment, tasks_facts)`; `exit_code = run_build_pass(plan, settings, options, wrapper, dry_run, env=tasks_layer)` where `tasks_layer = settings.tasks.env or None`; `hooks.emit_pass_completed(moment, tasks_facts, exit_code)`; `stages = ["tasks"]`.
8. **Step 8**: `exit_code == 0 and not settings.skip` → review pass — `options = compose_pass_options(settings, "review")`; `wrapper = resolve_wrapper_path(settings.review.additional.agent if strategy == "short" else settings.review.agent)`; the same emit/launch/emit triple with `review_facts` and `review_layer = settings.review.env or None`; `stages.append("review")`. A failed tasks pass never reaches here.
9. **Step 9**: `relocation = move_completed_plan(plan, outcome=(exit_code == 0), dry_run=dry_run)`.
10. **Step 10**: statuses — `work.slug is None` → `[]`; else `[r.statuses for r in collect_topic_statuses(year=work.year) if r.topic == work.slug][0]`-style lookup (absent topic → `[]`).
11. **Step 11**: `hooks.emit_build_completed(moment, exit_code, stages, relocation, statuses)`.
12. **Output**: `return exit_code` (the last executed pass's code).

#### Checkpoint Summary
- Dry-run parity: identical steps; `run_ralphex` prints and returns 0; relocation stays (dry_run guard); events carry `moment.dry_run=True` (passed).
- Pre-launch failures (0–3) and a blocked run (5) fire no events (passed).
- Exit code = last executed pass's code; relocation only on final-pass success (passed).

### Trace: `main()` (goga/build `__main__.py`)

`ensure_in_docker()` first → argparse (`plan`, `--dry-run`, `--skip-manifest-check`, `--skip-review`/`--no-skip-review` → `skip_review: bool | None`, `--base-ref`, `--review-patience`, `--session-timeout`, `--idle-timeout`, `--wait`, `--max-iterations`; **no** `--worktree`/`--skip-finalize`) → `cli_options` with exactly those keys (worktree/skip_finalize keys removed from the dict) → `load_project_config()` → `build(...)` → exit code. → checkpoint: cli_options keys match what `resolve_run_settings` reads (passed).

### Trace: `build(...)` (goga/commands/build, host)

Existing 19-step algorithm with three deltas: step 2.2 guard message/key becomes `config.build.agent is None → ClickException("build.agent is required in .goga/config.yml to run 'goga build'")`; step 2.3 (two-pass × worktree guard) deleted; step 7 env assembly becomes `{**home.env, **git_env, **cli_env}` — the task env (`config.build.env`) is NOT written to the env-file (it reaches the container only through the mounted `.goga/config.yml` and is applied in-container as the tasks-pass layer). CLI flags: `--worktree`/`--skip-finalize` options and their forwarding removed; `--review-patience`/`--base-ref` forwarding unchanged (value-flag pattern). → checkpoint: host forwards, container resolves (passed).

### Trace: `_build_config_document` (goga/onboarding/generator)

`data["build"] = build_block` (agent, env at the two-part root) instead of `{"task_executor": build_block}`; `_executor_block` docstring reworded (build root / pipeline content). → checkpoint: generated file passes the new loader (`config.build.agent` resolves) (passed).

## Algorithm Design

### `BuildHooks` (`goga/build/hooks/events.py`)

**Responsibility**: the checkpoint surface — the verdict-collecting gate and the four soft emissions over the `goga/hooks` facade; owns the single lazily-built run registry.

**Algorithm** (gate; the per-tool-delivery walk with the recorded refinement):
```
1. registry = _ensure_registry()                  # once per run
2. record = find(declared_actions(), domain="build", name="validate_build")
   IF record is None: raise ValueError("unknown hook action: build.validate_build")
3. groups = {} ; for sub in registry.subscriptions_for("build","validate_build"):
       groups.setdefault(sub.tool, []).append(sub)
4. violations = []
5. FOR (tool, subs) in groups (enumeration order):
   a. view = BuildValidation(moment, tasks, review, skip)   # fresh buffer per tool
   b. attributed_hook, attributed_reason = None, None ; crash = None
   c. FOR sub in subs:
      - before = view._veto
      - TRY sub.hook(**build_hook_arguments(sub.hook,
                 wrap_context(view), registry.self_context(tool)))
        EXCEPT Exception as reason: crash = (sub.name, str(reason)) ; BREAK
      - IF view._veto != before:
            attributed_hook, attributed_reason = sub.name, view._veto
   d. IF crash:    violations.append(Violation(tool, crash[0], crash[1]))
      ELIF view._veto is not None:
                     violations.append(Violation(tool, attributed_hook, view._veto))
      ELSE: pass                                  # silent approval
6. RETURN GateVerdict(violations)                 # never stops between tools
```

**Errors**: unknown address → `ValueError` (defensive); a broken tool-package import surfaces from `build_once` as `ImportError` (platform's single fatal case) — it escapes `build()` as an unhandled pre-pass failure after step 3 side effects but before events; acceptable per platform contract (single fatal case, clean message).

**Edge cases**: no subscriptions → empty verdict (approved); empty/whitespace veto reason stored and rendered verbatim; a later `veto()` replaces reason and attribution whole; crash overrides the buffered veto.

### `BuildValidation` (`contexts.py`)

`veto(reason)` sets `self._veto = reason` (whole replacement). Constraints: no cancellation/deflection — the veto acts only through the collected verdict.

### Emissions

Each builds its context and calls
`emit_hook_event(self._ensure_registry(), "build", <action>, context_for=lambda _tool: context)`.

### `resolve_run_settings` (`run_settings.py`)

```
1. review = config.review ; absent → treat all review fields unset (step 0 semantics)
2. skip = cli.skip_review ?? review.skip ?? False
3. strategy = review.strategy or "medium"
4. knob(k) = cli.k if cli.k is not None else root.k       # max_iterations + session knobs
   tasks = PassSettings(agent=root.agent, env=root.env,
                        max_iterations=knob("max_iterations"),
                        session_timeout=knob("session_timeout"),
                        idle_timeout=knob("idle_timeout"), wait=knob("wait"))
5. review_agent = review.agent or root.agent
   review_knob(k) = cli.k if cli.k is not None else (review.k if set else root.k)
                                                          # session knobs only
   review_env = review.env                               # exactly; never root env
6. additional = AdditionalReviewConfig(
       agent=(review.additional.agent if review.additional else None) or review_agent,
       patience=(cli.review_patience if cli.review_patience is not None else
                 review.additional.patience if review.additional else None),
       max_iterations=review.additional.max_iterations if review.additional else None)
7. base_ref = strip(cli.base_ref) if cli.base_ref is not None else review.base_ref
8. RETURN RunSettings(skip, tasks,
       ReviewPassSettings(agent=review_agent, env=review_env, roles=review.roles,
           base_ref=base_ref, strategy=strategy, finalize=review.finalize,
           additional=additional, session_timeout=…, idle_timeout=…, wait=…))
```
Pure; frozen value objects; no wrapper resolution; no strategy validation.

### `compose_pass_options` (`pass_options.py`)

```
tasks: {"tasks_only": True} ∪ {k: v for knobs of settings.tasks when v is not None}
review: mode = {"external_only": True} if strategy=="short" else {"review": True}
        ∪ {k: v for session_timeout/idle_timeout/wait of settings.review when not None}
        ∪ {"base_ref": v} when not None
        ∪ {"review_patience": additional.patience} when not None      # 0 kept
        ∪ {"max_external_iterations": additional.max_iterations} when not None  # 0 kept
```

### `validate_review_config` (`review_config.py`)

Fixed order: skip-return → role whitelist → env-requires-agent → review wrapper existence (None agent → clean `ValueError`) → additional wrapper existence (short always; full when additional.agent set) → strategy whitelist. Raises `ValueError` naming the invalid value; returns None.

### `sync_ralphex_defaults` (`ralphex_runtime.py`)

Existing rewrite + roles filtering, re-signatured to `(config: BuildConfig, settings: RunSettings)` (roles from `settings.review.roles`); new step: when `settings.review.finalize` is not None → write it verbatim to `.ralphex/agents/finalize.txt`.

### `write_ralphex_config` (`ralphex_config.py`)

Fixed block (`claude_command`, `claude_args`, `preserve_anthropic_api_key=true`, `move_plan_on_completion=false`) + `codex_enabled=false` under medium; under full/short: `external_review_tool=custom` + `custom_review_script=resolve_wrapper_path(additional.agent)` when additional.agent set; `finalize_enabled=true` when finalize set. Whole-file rewrite; INI lines joined with `\n` + trailing newline.

### `run_build_pass` (`build_pass.py`)

`write_ralphex_config(settings, wrapper_path)` → `return run_ralphex(plan, options, dry_run, env=env)`.

### `move_completed_plan` (`plan_relocation.py`)

`not outcome or dry_run` → `RelocationOutcome(moved=False, destination=None)`; else `Path.replace` into `<plan_dir>/completed/<name>` (mkdir parents, exist_ok) → `RelocationOutcome(moved=True, destination=str(dest))`.

### `build()` (`build.py`)

The 12-step cycle of the trace above, with the step-3.5 guard (tasks agent None → `logger.error("no build agent resolved: set build.agent in .goga/config.yml")` + `return 1`, before facts/gate/events — the degenerate skip-run case of a direct in-container invocation; unreachable through the host launcher's step-2.2 guard). Deletions: `_resolve_options`, `_review_scoped_options` (superseded by `resolve_run_settings`/`compose_pass_options`); the git pre-check helpers stay. New private helper `_completion_statuses(work) -> list[str]` (slug None → `[]`; else the matching `collect_topic_statuses(year=work.year)` record's statuses; absent → `[]`).

### `run_ralphex` (`goga/ralphex/run_ralphex.py`)

`_BOOL_FLAGS = (("review", "--review"), ("tasks_only", "--tasks-only"), ("external_only", "-e"))`;
`_SCALAR_FLAGS = (…, ("review_patience", "--review-patience"), ("max_external_iterations", "--max-external-iterations"), ("base_ref", "--base-ref"))`;
scalar emission rule: `value is not None and value != ""` — with the non-external keys additionally dropping 0 (`max_iterations`, `session_timeout`, `idle_timeout`, `wait`, `base_ref`), i.e. keep the historical `not in (None, "", 0)` for those and use the wider rule for exactly `review_patience`/`max_external_iterations`.

### `main()` (`__main__.py`)

argparse per the trace; `cli_options` keys: `dry_run`, `skip_manifest_check`, `skip_review`, `base_ref`, `review_patience`, `session_timeout`, `idle_timeout`, `wait`, `max_iterations` (worktree/skip_finalize removed).

### Host `build(...)` (`goga/commands/build/build.py`)

Remove the two click options + `_build_cli_args` worktree/skip_finalize branches; repoint the step-2.2 guard to `config.build.agent`; delete step 2.3; drop `config.build.env` from the env-file assembly (step 7) and from the comments that call the env-file "task_executor secrets"; `--review-patience`/`--base-ref` help text repointed to `build.review.additional.patience` / `build.review.base_ref`.

### Loader (`goga/config/project/loader.py`) and model (`config.py`)

Model: delete `TaskExecutorConfig`/`ReviewExecutorConfig`; `BuildConfig` per the new signature (all fields kw_only, `env`/`hosts` default empty dicts, everything else None-able); add `ReviewConfig`, `AdditionalReviewConfig` (frozen, kw_only). Loader: `_parse_build` extracts the root fields then the optional `review` sub-mapping (fields per the CODEMANIFEST step 7 patterns — `skip` bool|None, agent/env/base_ref/strategy/finalize emptiness patterns, `roles` list[str]|None with empty passing verbatim, `additional` mapping with int-typed `patience`/`max_iterations` rejecting YAML bools); error messages use the new key names (`build.agent must be a string…`, `build.review.strategy must be a string…`); unknown keys ignored. `_parse_task_executor`/`_parse_review_executor`/`_parse_review_scoped` deleted. `goga/config/__init__.py` re-exports `ReviewConfig`, `AdditionalReviewConfig`; drops the retired names.

### Catalog (`goga/hooks/catalog/catalog.py`)

Append five records (list order irrelevant — `declared_actions` sorts by domain then name):
`Action(domain="build", name="validate_build", error_class="hard")`,
`Action("build", "build_started", "soft")`, `Action("build", "pass_started", "soft")`,
`Action("build", "pass_completed", "soft")`, `Action("build", "build_completed", "soft")`. Existing records untouched.

### `goga/build/hooks/__init__.py`

Facade re-exporting all 13 types with `__all__` (alphabetical), module docstring naming the zone (mirror `goga/pipeline/hooks/__init__.py`).

## Cross-cutting Concerns

- **Error handling**: pre-launch failures (uncommitted manifests, invalid review config, unavailable defaults) and a vetoed gate return exit code 1 with a `logger.error` carrying structured `extra` — never a traceback; `ValueError` from validation is caught at the `build()` boundary. The single exception is the platform's fatal `ImportError` of a broken tool-package import, which escapes `build()` unhandled as documented in the `BuildHooks` errors section (the pipeline precedent — one clean message naming the package, still before any event). The gate's merged error lists every violation (tool, hook, reason). Soft hook failures warn inside the platform (tool, action, reason); the run is unaffected. `run_ralphex` launch rejections surface as one-line stderr + exit 1 and propagate as the pass's exit code (a completion fact).
- **Logging**: stdlib `logging`, `logger = logging.getLogger(__name__)`; lowercase stable event names; `extra={...}` metadata; **env values never appear in any log or print** — presence travels as sorted names in facts; the pass env layers are never logged and never printed on dry-run.
- **Validation**: three tiers — structural (loader, two-part extraction, retired keys ignored), semantic (`validate_review_config`: roles, env-requires-agent, wrapper existence ×2, strategy whitelist), and policy (the gate, tool-owned). All before the first side effect or event.
- **Caching**: none new. The `HookRegistry` builds once per run (lazily, on the first checkpoint) and is shared by all five checkpoints of the same `BuildHooks` instance; registration is never cached across runs. `.ralphex/` state persists on the host runtime mount (host-owned lifecycle).
- **Concurrency**: single-threaded in-container execution; no shared mutable state across processes. The only mutable checkpoint state is the per-tool veto buffer, scoped to one `validate_build` call.
- **Secret safety (C5)**: env values never delivered to any context, never written to the host env-file (the task env reaches the container only via the mounted config), never printed.

## Usages Analysis

### `conventions` / `convention`
- **What**: mandatory Python rules — relative imports, `dataclasses(kw_only=True)`, Google docstrings, logging style, blank-line blocking, test layout, validation commands.
- **Where used**: every touched file; every test file.
- **Why chosen**: project-wide mandate.
- **How exactly**: relative intra-package imports; frozen kw_only for `RunSettings`/`PassSettings`/`ReviewPassSettings` and the config model; plain kw_only for the zone facts/contexts; `logger = logging.getLogger(__name__)` with `extra`; tests mirror source under `tests/`.

### `ralphex` (project practice, updated during grooming)
- **What**: the external ralphex binary contract — CLI flags, config keys, review-agent composition, external-review surface, finalize step, vendorable defaults.
- **Where used**: `write_ralphex_config`, `sync_ralphex_defaults`, `compose_pass_options`, `run_ralphex` mapping.
- **Why chosen**: ralphex is the pass executor; goga observes only its own moments.
- **How exactly**: config keys `claude_command`/`claude_args`/`codex_enabled`/`external_review_tool`/`custom_review_script`/`finalize_enabled`/`preserve_anthropic_api_key`/`move_plan_on_completion`; flags per the option table; `{{agent:X}}` composition filtering; `agents/finalize.txt` materialization.

### `agent-wrappers`
- **What**: `/home/goga/bin/<agent>-as-claude.sh` naming for wrappers referenced by absolute path.
- **Where used**: wrapper resolution feeding `claude_command`.
- **Why chosen**: ralphex consumes the claude invocation shape.
- **How exactly**: `resolve_wrapper_path(agent)` (facade `goga.agents`), existence-checked only where the contract mandates (review + additional wrappers).

### `checkpoints` (goga/build/hooks/.usages — consumer doc of the zone)
- **What**: how the build operation consumes the zone — one `BuildHooks` per run, facts resolved in the operation, gate before the first pass, emissions around the cycle.
- **Where used**: `build()` steps 4–11.
- **Why chosen**: it IS the integration contract of this design.
- **How exactly**: per the trace (gate → started → per-pass started/completed → relocation → statuses → completed).

### `topic-paths` / `topic-statuses` (goga/history)
- **What**: topic dir composition (slug grammar, year default) and status listing (`collect_topic_statuses`, `TopicRecord`).
- **Where used**: work identity (hosting decision) and completion statuses.
- **Why chosen**: `goga/history` owns the tree; no new git surface.
- **How exactly**: `resolve_current_branch_name() or "unknown"`; `resolve_topic_dir(branch)` (+`ValueError` guard, `.is_dir()`) → slug/year; `collect_topic_statuses(year=work.year)` filtered to `work.slug`.

### `resolve-wrapper-path`, `run-ralphex`, `ensure-in-docker`, `ensure-in-docker`-adjacent host practices (`docker-*`, `click`, `home-configuration`, `project-configuration`, `build-usage`, `resolve-credential-mounts`, `runtime-paths`)
- **What**: unchanged consumer contracts of the surrounding cells.
- **Where used**: per their cells (host launcher, config facade, docker lifecycle).
- **Why chosen**: unchanged by this design (only the build-flag/env deltas of the host command touch them).
- **How exactly**: as documented in each file; `run-ralphex.md` was refreshed this stage (worktree removed, always-two-pass, external flags, zero rule).

### Imported by the zone (`goga/build/hooks` from `goga/hooks`)
- `declaring-actions` — `goga/hooks/.usages/declaring-actions.md` — the emission contract of the four notifications (`emit_hook_event` + `context_for`).
- `per-tool-delivery` — `goga/hooks/.usages/per-tool-delivery.md` — the staged per-tool walk of the gate (loop skeleton, primitives, per-tool grouping), with the recorded refinement: run to completion, collect vetoes, no contribution commit.
- `registering-hooks` — `goga/hooks/.usages/registering-hooks.md` — the hook signature (`context`/`self`) and failure handling behind every checkpoint.

## `.usages/` Update

### Cell: `goga/build`
- **`build-usage`** → `goga/build/.usages/build-usage.md` — Status: **current** (rewritten by apply-architecture; verified against the manifest: two-part settings, strategies, checkpoints, cli_options list). Additions/Updates: none.
- **`registering-hooks`** → `goga/build/.usages/registering-hooks.md` — Status: **current** (new file; answers the three integration scenarios). none.

### Cell: `goga/build/hooks`
- **`checkpoints`** → `goga/build/hooks/.usages/checkpoints.md` — Status: **current** (new file; consumer doc for the operation side). none.

### Cell: `goga/ralphex`
- **`run-ralphex`** → `goga/ralphex/.usages/run-ralphex.md` — Status: was **outdated** (worktree example, conditional two-pass wording, missing external flags) → **updated during this design stage**: worktree removed, always-two-pass composition, `external_only`/`max_external_iterations` + zero-valued rule documented, `TaskExecutorConfig` anti-pattern repointed.

### Cell: `goga/config`
- **`project-configuration`** → `goga/config/.usages/project-configuration.md` — Status: **current** (build chapter rewritten to the two-part form incl. migration note). none.

### Cell: `goga/commands/build`
- **`build`** → `goga/commands/build/.usages/build.md` — Status: **current** (flag surface without the two removed flags; env layering note). none.

### Cells without `.usages/` changes
`goga/hooks/catalog` (no `.usages/` directory), `goga/config/project` (no `.usages/`), `goga/onboarding/generator` (no `.usages/`), `goga/hooks` (provider practices unchanged). No new `.usages/` files are needed — every new domain (zone facts, gate, checkpoints, tool-author subscription) is already covered by the four files above.

## Test Stack Trace

### General Setup

- Zone tests reuse the platform boundary fixtures: `tests/hooks/conftest.py`
  (`pin_package_environment` — pins `packages_distributions`;
  `install_tool_package` — installs a fake `goga_tool_*` into `sys.modules`),
  re-exported by `tests/build/hooks/conftest.py` (mirror
  `tests/pipeline/hooks/conftest.py`).
- Wrapper existence tests monkeypatch `resolve_wrapper_path` at its import
  point (`goga.build.review_config.resolve_wrapper_path` /
  `goga.build.ralphex_config.resolve_wrapper_path`) to a real `tmp_path`
  file — the established pattern of `tests/build/test_review_config.py`.
- Orchestration tests monkeypatch `goga.build.build.run_build_pass` (or
  `goga.ralphex.run_ralphex.run_ralphex`) with a recording stub, run inside
  `tmp_path` (`.ralphex/` writes land there), and monkeypatch
  `resolve_current_branch_name`/`resolve_topic_dir`/`collect_topic_statuses`
  at `goga.build.build`'s import point.
- `tests/conftest.py` provides `is_kw_only_dataclass`.

### Source File Registry

Created: `goga/build/hooks/{__init__,facts,contexts,events}.py`,
`goga/build/{run_settings,pass_options}.py`,
`tests/build/hooks/{__init__,conftest,test_facts,test_contexts,test_events}.py`,
`tests/build/{test_run_settings,test_pass_options}.py`.
Rewritten: `goga/config/project/{config,loader}.py`, `goga/build/{build,__main__,review_config,ralphex_runtime,ralphex_config,build_pass,plan_relocation}.py`, `goga/ralphex/run_ralphex.py`, `goga/hooks/catalog/catalog.py`, `goga/commands/build/build.py`, `goga/onboarding/generator/generator.py`, `goga/config/__init__.py`.
Deleted: `goga/build/review_options.py`, `tests/build/test_review_options.py`.
Updated tests: `tests/build/{test_build,test_main,test_review_config,test_ralphex_config,test_ralphex_runtime,test_build_pass,test_plan_relocation,test_contract}.py`, `tests/config/{test_config,test_loader}.py`, `tests/ralphex/test_run_ralphex.py`, `tests/hooks/catalog/test_catalog.py`, `tests/commands/build/test_build.py`, `tests/onboarding/generator/test_generator.py`.

Affected tests outside the main registry — verified stale against the
retired schema during the design review; rewrite/update them as part of
the implementation (the validation run `pytest tests/ -x` covers them):

- `tests/build/test_build_resolved_wrapper.py` — rewrite the six tests
  onto the two-part schema (`build.agent` at the root); delete the
  `codex_review → codex_enabled` case (the key is retired; the strategy
  table test of `test_ralphex_config` covers the new derivation); keep the
  uncommitted-manifests / ralphex-missing / custom-prompts-dir cases on
  the new fixtures.
- `tests/build/test_shipped_ralphex_assets.py` — replace the
  `BuildConfig(task_executor=TaskExecutorConfig(...))` construction with
  the two-part `BuildConfig(agent=..., env={})`; the vendored asset
  assertions are unchanged.
- `tests/config/test_integration.py` — rewrite the build-section fixtures
  and assertions onto the two-part model (root fields plus
  `build.review`); drop or repoint the `worktree`/`skip_finalize`/
  `codex_review`/`task_executor`/`review_executor` assertions to the
  retired-key silence semantics already covered by the loader tests.
- `tests/commands/conftest.py` — update the shared config-writing helpers
  to the two-part schema (`build: {agent: ...}`); drop the
  `worktree`/`skip_finalize`/`codex_review`/`review_executor` lines.
- `tests/commands/test_build.py` — replace the `worktree`-option
  assertion with the removed-surface assertion (unknown option, exit 2);
  repoint the `task_executor` config fixture to `build.agent`.
- `tests/integration/test_base_ref_end_to_end.py`,
  `tests/integration/test_skip_review_end_to_end.py`,
  `tests/integration/test_resolved_wrapper_flow.py` — rewrite onto the
  two-part config and the always-two-pass cycle (the skip form: exactly
  one tasks pass).
- `tests/commands/build/test_build_home_integration.py`,
  `tests/commands/build/test_build_proxy_hosts_update.py`,
  `tests/commands/build/test_build_runtime_isolation_integration.py`,
  `tests/commands/build/test_build_credential_mount_integration.py` —
  update fixtures to the two-part schema and the env-file assertions (the
  task env is no longer written into the env-file).
- Incidental `task_executor` text in the fixtures of the pipeline /
  contract / usages-sync suites stays load-compatible (the loader
  silently ignores unknown keys) — no rewrite needed; confirmed by the
  full-suite run of the validation step.

---

### Positive Tests

#### `test_load_project_config_parses_two_part_build`

**Setup**: `tmp_path` with `.goga/config.yml`:
`language: python`, `build: {agent: claude, env: {A: "1"}, max_iterations: 7, session_timeout: 30m, review: {agent: codex, env: {B: "2"}, roles: [quality], base_ref: main, strategy: short, finalize: "do it", additional: {agent: cursor, patience: 2, max_iterations: 4}}}`; monkeypatch cwd.

**Input**: `load_project_config()`.

**Trace**:
```
load_project_config()
  → yaml.safe_load(doc)                    # mapping
  → _parse_build(build mapping)
    → root: agent="claude", env={"A":"1"}, max_iterations=7, session_timeout="30m"
    → review mapping → ReviewConfig(agent="codex", env={"B":"2"}, roles=["quality"],
      base_ref="main", strategy="short", finalize="do it",
      additional=AdditionalReviewConfig(agent="cursor", patience=2, max_iterations=4))
  → ProjectConfig(build=BuildConfig(..., review=...))
```

**Assertions**:
```
config.build.agent == "claude"; config.build.env == {"A": "1"}
config.build.review.agent == "codex"; config.build.review.additional.patience == 2
not hasattr(config.build, "task_executor"); not hasattr(config.build, "worktree")
```

**Sufficiency**: pins the two-part loader shape every downstream resolution depends on; prevents regression to the executor-block model.

#### `test_resolve_run_settings_full_inheritance`

**Setup**: `BuildConfig(agent="claude", env={"A":"1"}, max_iterations=9, session_timeout="30m", idle_timeout="5m", wait="1m", review=ReviewConfig(skip=None, agent=None, env={}, roles=["quality"], base_ref="main", strategy=None, finalize=None, additional=AdditionalReviewConfig(agent=None, patience=3, max_iterations=None), session_timeout=None, idle_timeout=None, wait=None))`; `cli_options={}` (all None).

**Input**: `resolve_run_settings(config, cli_options)`.

**Trace**:
```
resolve_run_settings(config, {})
  → skip=False; strategy="medium" (default)
  → tasks=PassSettings(agent="claude", env={"A":"1"}, max_iterations=9, "30m","5m","1m")
  → review.agent="claude" (inherited); knobs "30m"/"5m"/"1m" (inherited)
  → additional.agent="claude" (inherits review agent), patience=3
  → base_ref="main"
  → RunSettings(skip=False, ...)
```

**Assertions**: `settings.review.agent == "claude"`; `settings.review.strategy == "medium"`; `settings.review.additional.agent == "claude"`; `settings.review.additional.patience == 3`; `settings.review.env == {}`; `settings.review.base_ref == "main"`.

**Sufficiency**: the inheritance spine (root→review→additional) is the core of the two-part model; SC2's "bound per-stage settings".

#### `test_resolve_run_settings_cli_overrides_and_tri_state`

**Setup**: config with `review=ReviewConfig(skip=True, session_timeout="10m", ...)`; `cli_options={"skip_review": False, "session_timeout": "99m"}`.

**Input**: `resolve_run_settings(config, cli_options)`.

**Trace**: skip: CLI False (not None) wins over config True → False; `session_timeout`: CLI "99m" wins.

**Assertions**: `settings.skip is False`; `settings.review.session_timeout == "99m"`.

**Sufficiency**: precedence CLI > config and the tri-state kill switch (task item 2/`skip`).

#### `test_resolve_run_settings_review_absent`

**Setup**: `BuildConfig(agent="claude", env={}, max_iterations=5, ..., review=None)`; `cli_options={}`.

**Input**: `resolve_run_settings(config, {})`.

**Trace**: step 0 — every review field unset; skip False; strategy medium; additional constructed with `agent="claude"`, patience/max_iterations None.

**Assertions**: `settings.review.additional.agent == "claude"`; `settings.review.additional.patience is None`; `settings.review.roles is None`; `settings.skip is False`. Repeat with `review=ReviewConfig(roles=[])` → `settings.review.roles == []` (the empty list travels verbatim, never coerced to None).

**Sufficiency**: the non-optional `additional` member must resolve even with no `build.review` key (a `ReviewPassSettings` construction crash would break every plain config).

#### `test_resolve_run_settings_base_ref_normalization`

**Setup**: `cli_options={"base_ref": "  release/1.3.0  "}`; config review `base_ref="main"`.

**Input**: `resolve_run_settings(...)` → **Assertions**: `settings.review.base_ref == "release/1.3.0"`. Repeat with `cli_options={"base_ref": "   "}` → `base_ref == "main"` (empty CLI counts as unset).

**Sufficiency**: whitespace semantics preserved from the retired resolver; prevents padded/empty CLI values silently overriding config.

#### `test_compose_pass_options_tasks`

**Setup**: `RunSettings` with tasks knobs (`session_timeout="30m"`, `max_iterations=9`) and review part carrying `base_ref="main"`, `additional.patience=0`.

**Input**: `compose_pass_options(settings, "tasks")`.

**Trace**: `{"tasks_only": True, "session_timeout": "30m", "max_iterations": 9}`.

**Assertions**: exactly those keys; no `review`/`external_only`/`base_ref`/`review_patience`.

**Sufficiency**: "Review-only options never appear on the tasks pass".

#### `test_compose_pass_options_review_medium_and_short`

**Setup**: same settings, `strategy="medium"`.

**Input**: `compose_pass_options(settings, "review")`.

**Assertions**: `options["review"] is True` and `"external_only" not in options`; `options["base_ref"] == "main"`; `options["review_patience"] == 0` (zero kept); `"max_external_iterations" in options` iff `additional.max_iterations is not None`.

**Trace (short)**: rebuild with `strategy="short"` → **Assertion**: `options["external_only"] is True and "review" not in options`.

**Sufficiency**: mutually exclusive pass modes and the short-strategy `-e` binding (SC2 / task item 2).

#### `test_validate_review_config_accepts_clean_settings`

**Setup**: `tmp_path` wrapper file; monkeypatch `goga.build.review_config.resolve_wrapper_path` → `str(wrapper)`; `RunSettings(skip=False, review=ReviewPassSettings(agent="claude", env={"X":"1"}, roles=["quality"], strategy="medium", additional=AdditionalReviewConfig(agent="claude", patience=None, max_iterations=None), ...))`.

**Input**: `validate_review_config(settings)`.

**Trace**: roles pass → env non-empty but agent set → wrapper resolves + exists → medium does not engage the additional check → strategy whitelisted → returns None.

**Assertions**: returns None; no exception.

**Sufficiency**: the happy path must not raise — the fixed check order is observable via the negative tests below.

#### `test_write_ralphex_config_strategies`

**Setup**: tmp cwd; three `RunSettings` variants (medium / full with additional agent "codex" / finalize set), wrapper path `"/home/goga/bin/claude-as-claude.sh"`; monkeypatch `goga.build.ralphex_config.resolve_wrapper_path` for the additional wrapper.

**Input**: `write_ralphex_config(settings, wrapper)` per variant.

**Trace**: file `.ralphex/config` rewritten whole per call.

**Assertions**:
```
medium:  "codex_enabled = false" in text; "external_review_tool" not in text
full+additional: "external_review_tool = custom" in text
         and f"custom_review_script = {additional_wrapper}" in text
         and "codex_enabled" not in text
finalize set: "finalize_enabled = true" in text; unset variant: not in text
always: "move_plan_on_completion = false", "preserve_anthropic_api_key = true",
        f"claude_command = {wrapper}"
```

**Sufficiency**: the external surface and finalize wiring of the review pass — SC-level behavior of the strategy triple.

#### `test_sync_ralphex_defaults_materializes_finalize`

**Setup**: tmp cwd; vendored sources exist (use the real vendored dirs, custom `prompts_dir`/`agents_dir` pointing at tmp copies when isolation is needed); `RunSettings` with `finalize="Final pass: merge the review."`.

**Input**: `sync_ralphex_defaults(config, settings)`.

**Trace**: full rewrite of prompts/agents → finalize step: `.ralphex/agents/finalize.txt` written with the prompt verbatim.

**Assertions**: `(tmp_path / ".ralphex/agents/finalize.txt").read_text() == "Final pass: merge the review."`; unset-finalize variant → file absent.

**Sufficiency**: the finalize materialization (task item 2; ADR finalize decision).

#### `test_move_completed_plan_returns_relocation_outcome`

**Setup**: `tmp_path/docs/plans/plan.md` exists.

**Input**: `move_completed_plan(str(plan), outcome=True, dry_run=False)`.

**Trace**: not-moved guard passes → `completed/` created → `Path.replace` → outcome built.

**Assertions**: `relocation.moved is True`; `relocation.destination == str(tmp_path/"docs/plans/completed/plan.md")`; source gone. Variants: `outcome=False` → `moved is False, destination is None`; `dry_run=True` → same not-moved outcome and file stays.

**Sufficiency**: `BuildCompleted.relocation` facts (SC5) depend on the outcome object.

#### `test_build_runs_two_passes_with_bound_settings`

**Setup**: tmp cwd with config; monkeypatch `goga.build.build.run_build_pass` recording `(options, wrapper, env)` and returning 0; monkeypatch `resolve_current_branch_name` → `"add-hooks-to-build"`, `resolve_topic_dir` → raises ValueError (branch-only), `collect_topic_statuses` → `[]`; `cli_options={... all None, dry_run False}`; no tool packages pinned (inert hooks).

**Input**: `build("plan.md", config, cli_options)`.

**Trace**:
```
build(...)
  → resolve_run_settings → validate (patched wrappers) → sync (tmp .ralphex)
  → work = WorkIdentity("add-hooks-to-build")        # unsluggable → branch-only
  → gate: no subscriptions → approved
  → emit_build_started (inert)
  → pass 1: options {"tasks_only": True,...}, wrapper claude-as-claude.sh, env={"A":"1"}
  → pass 2 (exit 0, not skip): options {"review": True,...}, wrapper review/additional, env=review env
  → move_completed_plan(outcome=True) → relocation.moved True
  → statuses [] (branch-only) → emit_build_completed → return 0
```

**Assertions**: `run_build_pass` called exactly twice; first call `options["tasks_only"] is True` and `env == {"A":"1"}`; second call `options["review"] is True` and env is the review layer (never the root env); return 0; plan relocated.

**Sufficiency**: SC2 — the stable cycle including the formerly combined case; secret boundary (root env never on the review pass).

#### `test_build_skipped_review_single_tasks_pass`

**Setup**: as above with `cli_options={"skip_review": True}`.

**Assertions**: exactly one `run_build_pass` call (`tasks_only`); return value = that pass's code; no review-pass call.

**Sufficiency**: SC2 second sentence ("a skipped review yields exactly one tasks pass").

#### `test_gate_collects_vetoes_without_early_stop`

**Setup**: `pin_package_environment({"goga_tool_a": ["goga_tool_a"], "goga_tool_b": ["goga_tool_b"]})`; install both with `register_hooks` subscribing `("build","validate_build","policy", hook)`; hook A vetoes `"no deploys on friday"`, hook B records `self.calls` and approves; facts built directly.

**Input**: `hooks = BuildHooks(); verdict = hooks.validate_build(moment, tasks, review, skip=False)`.

**Trace**: registry builds once → groups {A, B} → A's view buffers the veto → B still invoked → verdict `[Violation(tool="goga_tool_a", hook="policy", reason="no deploys on friday")]`.

**Assertions**: `verdict.approved is False`; single violation naming tool+hook+reason; B's hook ran (recorded flag True).

**Sufficiency**: SC3 — verdict collection requires every tool's outcome; a non-vetoing subscriber is still invoked.

#### `test_gate_attributes_veto_to_hook_and_replaces_whole`

**Setup**: one tool, two hooks `first` (vetoes "one") and `second` (vetoes "two") on the same address.

**Input**: `validate_build(...)`.

**Assertions**: exactly one `Violation`; `violation.hook == "second"`; `violation.reason == "two"` (later veto replaces reason AND attribution).

**Sufficiency**: the whole-replacement attribution rule from the zone contract.

#### `test_gate_crash_overrides_veto_and_walk_continues`

**Setup**: tool A: hook `broken` raises `RuntimeError("boom")` after a hook `vetoer` buffered "blocked"; tool B approves.

**Input**: `validate_build(...)`.

**Assertions**: violations == `[Violation(A, "broken", "boom")]` only — crash reason replaces the buffered veto, exactly one violation for A, B still ran, no exception escapes.

**Sufficiency**: "a crashing hook counts as its tool's veto with the crash reason — never a raw traceback" + no early stop.

#### `test_gate_empty_verdict_when_no_subscriptions`

**Setup**: `pin_package_environment({})`.

**Input**: `validate_build(...)` → **Assertions**: `verdict.approved is True; verdict.violations == []`.

**Sufficiency**: SC7/SC8-adjacent — the hooks layer is inert with no tool packages.

#### `test_notifications_carry_completion_facts`

**Setup**: one tool subscribing all four soft actions with hooks recording `context` (via `self`); orchestration as in the two-pass test with the tasks pass returning 0 and the review pass returning 2.

**Input**: `build(...)`.

**Trace**: started → pass_started(tasks) → pass_completed(tasks, 0) → pass_started(review) → pass_completed(review, 2) → relocation (not moved — failure) → build_completed(exit_code=2, stages=["tasks","review"], relocation.moved=False, statuses=[]).

**Assertions**: recorded contexts expose `PassCompleted.exit_code == 2` for the review facts; `BuildCompleted.exit_code == 2`; `stages == ["tasks", "review"]`; a crashing notification hook (separate variant) warns and the return code stays 2.

**Sufficiency**: SC4 — completion fires on non-zero codes with the actual exit code; SC5 facts on `build_completed`.

#### `test_build_dry_run_rehearses_event_structure`

**Setup**: two-pass setup with `dry_run=True`; `run_build_pass` NOT patched at the pass level — patch `goga.ralphex.run_ralphex.run_ralphex` to assert it is called with `dry_run=True` (it prints and returns 0).

**Input**: `build(...)` with `cli_options={"dry_run": True}`.

**Assertions**: both passes "ran" (launcher called twice, both dry); the plan file still at its original path (relocation not moved); `BuildCompleted.relocation.moved is False`; recorded notification `moment.dry_run is True`.

**Sufficiency**: SC6 — identical event structure, gate runs, nothing executes, plan not relocated.

#### `test_registry_built_once_across_checkpoints`

**Setup**: one tool subscribing `validate_build` + `build_started` + `build_completed`; pin the enumeration boundary mock and count reads.

**Input**: full `build(...)` run.

**Assertions**: the `packages_distributions` boundary was read exactly once (one registry build shared by all reached checkpoints).

**Sufficiency**: "one HookRegistry per run carries every checkpoint" (performance + enumeration-once invariant).

#### `test_catalog_carries_the_five_build_records`

**Setup/Input**: `declared_actions()`.

**Assertions**: the five `(domain="build", name∈{validate_build, build_started, pass_started, pass_completed, build_completed})` records exist with error classes hard/soft×4; pre-existing records byte-identical (compare against a frozen expected list); ordering deterministic (domain, then name).

**Sufficiency**: C4 catalog additivity — no existing record changes; SC1 addressing.

#### `test_zone_facade_exports_thirteen_types`

**Input**: `python -c`-style import in test: `from goga.build.hooks import BuildHooks, BuildMoment, StageFacts, WorkIdentity, AdditionalFacts, RelocationOutcome, Violation, GateVerdict, BuildValidation, BuildStarted, PassStarted, PassCompleted, BuildCompleted`.

**Assertions**: all resolve; `RunSettings`/`PassSettings` importable from `goga.build.run_settings`; facade `from goga.config import BuildConfig, ReviewConfig, AdditionalReviewConfig` resolves and retired names are gone (`ImportError` on `TaskExecutorConfig`).

**Sufficiency**: the arch-plan facade check, executable.

#### `test_main_argparse_surface_matches_contract`

**Setup**: monkeypatch `sys.argv` / `ensure_in_docker`; patch `goga.build.__main__.build`.

**Input**: `main()` with `["goga.build", "plan.md", "--skip-review", "--review-patience", "3"]`; repeat with `["goga.build", "plan.md", "--no-skip-review"]`.

**Assertions**: forwarded `cli_options["skip_review"] is True` and `cli_options["review_patience"] == 3`; the `--no-skip-review` variant forwards `cli_options["skip_review"] is False` (the tri-state False arm of the argparse pair); parsing `--worktree` or `--skip-finalize` exits with argparse error (SystemExit 2); guard `ensure_in_docker` called first (both branches covered per the manifest requirement).

**Sufficiency**: the in-container CLI surface; SC8 (flags removed end to end).

#### `test_host_command_surface_and_env_file`

**Setup**: click runner (`CliRunner`); tmp config with two-part build; existing host fixtures.

**Input**: invoke `goga build plan.md` (and with `--base-ref x --review-patience 2 --skip-review`).

**Assertions**: `--worktree`/`--skip-finalize` are unknown options (exit 2 + message); guard message names `build.agent`; forwarded args contain `--base-ref x` / `--review-patience 2` / `--skip-review` only when set; the written env-file contains home/git/cli env keys and NOT the `build.env` values (secret boundary); docker args carry `-m goga.build <plan>`.

**Sufficiency**: SC8 host side + the env-file layering change; guard repoint.

#### `test_onboarding_generator_emits_two_part_build`

**Setup**: onboarding answers `build: {agent: "claude", env: {API_KEY: "secret"}}` (existing fixture pattern).

**Input**: `generate_goga_config(answers)` → load the written file with `load_project_config`.

**Assertions**: `cfg["build"] == {"agent": "claude", "env": {"API_KEY": "secret"}}` (no `task_executor` nesting); `config.build.agent == "claude"` (the generated file actually drives a build).

**Sufficiency**: the fixed defect — fresh onboarding must produce a working build section.

#### `test_run_ralphex_external_flags_and_zero_rule`

**Setup**: patch `subprocess.call` (via the existing launcher test pattern) recording argv; `dry_run=False`.

**Input**: `run_ralphex("p.md", {"external_only": True, "review_patience": 0, "max_external_iterations": 0, "max_iterations": 0, "base_ref": "main"}, False)`.

**Trace**: `_build_command` → bool loop emits `-e`; scalar loop: `review_patience 0` and `max_external_iterations 0` emitted; `max_iterations` 0 dropped; `base_ref main` emitted.

**Assertions**:
```
argv == ["ralphex", "p.md", "--config-dir", ".ralphex/", "-e",
         "--review-patience", "0", "--max-external-iterations", "0",
         "--base-ref", "main"]
```
and `--worktree`/`--skip-finalize` never appear for any input.

**Sufficiency**: the launcher flag contract incl. the zero-valued external rule (0 = disabled / ralphex auto are meaningful).

### Negative Tests

#### `test_load_project_config_ignores_retired_keys`

**Setup**: config carrying `build: {worktree: true, skip_finalize: true, codex_review: false, task_executor: {agent: claude}, review_executor: {agent: codex}, agent: claude}`.

**Input**: `load_project_config()`.

**Assertions**: no error; `config.build.agent == "claude"`; `config.build.review is None` (the old blocks are unknown keys — silently ignored, not parsed).

**Sufficiency**: SC8 — retired keys vanish without compatibility paths; the "stale config silently disables review, not build" semantics.

#### `test_load_project_config_rejects_malformed_review`

**Setup/Input**: parametrize: `review: "x"` (non-mapping), `review: {skip: "yes"}`, `review: {roles: [1]}`, `review: {strategy: 5}`, `review: {additional: {patience: true}}`, `build: {max_iterations: true}`, `build: {agent: 7}`.

**Assertions**: each raises `ValueError` naming the key (`build.review.skip must be a bool…` etc.).

**Sufficiency**: structural typing of the new block (manifest step 7 patterns, incl. YAML-bool-as-int rejection).

#### `test_validate_review_config_rejects_bad_fields`

**Setup**: clean baseline settings; wrapper monkeypatched to an existing tmp file; parametrize mutations: role `"auditor"`; review env non-empty + agent None; wrapper path to a missing file (`/home/goga/bin/ghost-as-claude.sh` via the patch); strategy `"fast"`.

**Input**: `validate_review_config(mutated)`.

**Assertions**: `pytest.raises(ValueError, match=...)` naming the role / the env-requires-agent problem / the agent+path / the strategy value; a `skip=True` variant of every mutation returns None (skipped runs validate nothing).

**Sufficiency**: the semantic tier incl. the skip short-circuit; the fixed check order.

#### `test_validate_review_config_rejects_missing_additional_wrapper`

**Setup**: clean baseline settings with `strategy="full"` and `additional.agent="codex"`; monkeypatch `goga.build.review_config.resolve_wrapper_path` so the review agent resolves to an existing `tmp_path` file and the additional agent to a missing path (`/home/goga/bin/ghost-as-claude.sh`).

**Input**: `validate_review_config(settings)`.

**Trace**: roles pass → env gate pass → review wrapper resolves + exists → strategy full engages the external review (additional.agent set) → the additional wrapper resolves to the missing path → `not Path(wrapper).is_file()` → raise.

**Assertions**: `pytest.raises(ValueError, match="ghost-as-claude.sh")` naming the additional agent and its path; a `skip=True` variant of the same settings returns None (skipped runs validate nothing).

**Sufficiency**: the step-5 branch of the fixed check order (the additional-wrapper existence under full/short) has no other negative coverage — without this test the external-surface validation never has a failing exercise.

#### `test_build_vetoed_run_blocks_before_any_pass`

**Setup**: two-pass orchestration setup + one tool whose `validate_build` hook vetoes `"policy"`; `run_build_pass` patched with a recorder.

**Input**: `build(...)`.

**Assertions**: return 1; `run_build_pass` never called; the plan file still in place; NO notification hook of the tool ran (recorded `build_started`/`pass_*`/`build_completed` absent); exactly one `logger.error` record carrying the violation triple (caplog).

**Sufficiency**: SC3 end-to-end — one merged error, exit 1, nothing executes, no post-gate events.

#### `test_build_pre_launch_failures_fire_no_events`

**Setup**: tool subscribed to all five actions (recorder); parametrize: uncommitted CODEMANIFEST in tmp git-less setup (patch `_find_uncommitted_manifests` → `["x/CODEMANIFEST"]`), invalid review config (patch `validate_review_config` → raise), unavailable defaults (patch `sync_ralphex_defaults` → raise), no build agent on a skip run (config with root agent None + `cli_options={"skip_review": True}` — the step-3.5 guard path; `validate_review_config` returns early on skip, so the guard is the only pre-event check that fires).

**Input**: `build(...)` per variant.

**Assertions**: return 1; zero hook invocations across all five actions in every variant.

**Sufficiency**: "a failing moment fires nothing" (registering-hooks doc; task edge semantics).

### Edge Case Tests

#### `test_stage_facts_carry_env_names_only`

**Setup/Input**: settings with `tasks.env={"A":"1","B":"2"}` → orchestration facts (or direct construction helper under test).

**Assertions**: `StageFacts.env == ["A", "B"]` (sorted names); no fact object exposes any env value (walk `dataclasses.fields` of every context and assert no string member equals `"1"`/`"2"`).

**Sufficiency**: C5/SC5 — "no context ever carries env values".

#### `test_build_statuses_recomputed_after_relocation`

**Setup**: topic-hosting branch: `resolve_current_branch_name → "add-hooks-to-build"`, `resolve_topic_dir → Path(".goga/history/2026/add-hooks-to-build")` (is_dir True); `collect_topic_statuses` stub returning `[TopicRecord("add-hooks-to-build", ["backlog", "designed"])]`; successful run.

**Input**: `build(...)`.

**Assertions**: the recorded `BuildCompleted.statuses == ["backlog", "designed"]`; `collect_topic_statuses` called with `year="2026"` AFTER `move_completed_plan` (order recorded); branch-only variant delivers `[]`.

**Sufficiency**: SC5 — artifact → history-status integration buildable from documented facts; the recompute-after-relocation ordering.

#### `test_build_failed_tasks_pass_skips_review`

**Setup**: `run_build_pass` first call returns 1.

**Input**: `build(...)`.

**Assertions**: one pass call only; `pass_completed` for tasks carries `exit_code == 1`; `BuildCompleted.stages == ["tasks"]`; relocation not moved; return 1.

**Sufficiency**: "a failed tasks pass never launches the review pass" + completion facts on failure.

#### `test_gate_veto_empty_reason_rendered_verbatim`

**Setup**: tool hook calls `context.veto("   ")`.

**Input**: `validate_build(...)` → **Assertions**: `Violation.reason == "   "`; approved False.

**Sufficiency**: the stored-as-given rule for empty reasons.

#### `test_max_iterations_zero_dropped_by_launcher`

**Setup/Input**: `run_ralphex("p.md", {"tasks_only": True, "max_iterations": 0}, dry_run=True)` (capture stderr).

**Assertions**: printed command has no `--max-iterations`; contrast `review_patience: 0` prints `--review-patience 0`.

**Sufficiency**: the asymmetric zero rule (only the two external flags carry meaningful zeros).

#### `test_unsluggable_branch_falls_back_to_branch_only`

**Setup**: `resolve_topic_dir` raises `ValueError`; `resolve_current_branch_name → None`.

**Input**: `build(...)` → **Assertions**: `WorkIdentity.branch == "unknown"`, `slug is None`; statuses `[]`; run proceeds normally (hosting failure is not a run failure).

**Sufficiency**: the degraded branch-only form is allowed (task item 5).

#### `test_move_completed_plan_is_idempotent_by_name`

**Setup**: run the relocation twice on the same plan (recreate the source between calls).

**Assertions**: second call overwrites `completed/plan.md` without error.

**Sufficiency**: the documented idempotency (existing behavior preserved through the re-signature).

---

## Additional Instructions for the Implementation Agent

- Read the practices before coding: `conventions`, `ralphex`, `agent-wrappers`, `checkpoints`, `registering-hooks` (goga/build), `per-tool-delivery`, `declaring-actions` (goga/hooks), `topic-paths`, `topic-statuses` (goga/history), `run-ralphex` (goga/ralphex), `resolve-wrapper-path` (goga/agents), `build-usage`, `project-configuration`.
- Implement in the dependency order of Entity Dependencies; keep every file's module docstring in the zone style of `goga/pipeline/hooks` (which zone it is, which entities live here).
- Google docstrings everywhere; CLI callback docstrings verbatim-help (no Args/Returns/Raises); relative intra-package imports only; `from __future__ import annotations` at the top of every touched module.
- Match the established code idioms: the gate walk mirrors `PipelineHooks.amend_workflow` (grouping, `wrap_context`, `build_hook_arguments`, `registry.self_context`) with the recorded deviation (collect, never stop); the emissions mirror `emit_run_created`; the merged veto error mirrors the existing `logger.error(..., extra={...})` style of `build.py`.
- Delete `goga/build/review_options.py` and `tests/build/test_review_options.py`; no compatibility shims anywhere (major-version window, C7).
- `.goga/config.yml` is already migrated — do not touch it.
- The env layers: `settings.tasks.env or None` / `settings.review.env or None` (an empty dict means pure inheritance, never an empty overlay).
- `StageFacts.env` is `sorted(env)` — names only, deterministic.
- Validation after implementation: `pytest tests/ -x`; `ruff check` over every touched package; facade checks (`from goga.build.hooks import ...` 13 names; `from goga.config import BuildConfig, ReviewConfig, AdditionalReviewConfig`); absence greps for `--worktree`, `--skip-finalize`, `worktree`, `skip_finalize`, `codex_review`, `task_executor`, `review_executor` across `goga/` (expected hits: only the retirement/migration documentation in manifests/usages, and the loader's ignore-everything stance); `goga lint` (79 cells, 0 errors); `goga schema` shows
`goga/build/hooks` with exactly 13 types and a single dependency on `goga/hooks`.
- Dogfooding acceptance: a real `goga build` run on this repository executes the two passes over the migrated config; `goga hooks` lists build subscriptions of any installed tool.
- SC1–SC10 map to tests as annotated in the Test Stack Trace (SC1 catalog/facade/`goga hooks`; SC2 two-pass; SC3 veto; SC4 notification failure/exit codes; SC5 completion facts + env names; SC6 dry-run; SC7 inert-no-tools; SC8 absence; SC9 the `registering-hooks` doc answers the three scenarios; SC10 no-caching is platform behavior — assert registration re-reads by a second run seeing an edited hook).
