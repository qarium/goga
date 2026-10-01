# Open the build domain over a stable two-pass cycle with a verdict-collecting gate

Normative inputs: `adr.md` (accepted) and `prd.md` in this topic directory,
aligned with each other. Where any text differs, the ADR wins.

## Current State

- The build domain orchestrates code builds through the external ralphex
  binary (cell `goga/build`: pass composition, review-phase orchestration,
  vendored ralphex defaults sync, plan relocation). The run model is unstable
  for integration: whether tasks and review run as one combined pass or as two
  separate passes depends on incidental executor configuration (a differing
  review agent or a non-empty review env).
- Build settings live in the `task_executor` / `review_executor` blocks of the
  build config; executor settings are not bound to stages — the task env
  applies to the whole container, not to the tasks stage. A `worktree` run mode
  exists (CLI flag + config key + a host-side two-pass × worktree guard in
  `goga/commands/build`). External review is toggled by a `codex_review`
  setting; finalize by a `skip_finalize` flag/mirror.
- The hooks platform (facade `goga/hooks`: `HookRegistry`,
  `emit_hook_event`, `wrap_context`, `declared_actions`; per-tool delivery)
  already opens the pipeline, topics, onboarding, and statuses domains through
  per-domain hooks zones (`goga/pipeline/hooks`, `goga/topics/hooks`). The
  build domain is closed: an installed tool package can neither observe build
  moments, nor enforce build policy, nor connect build outcomes to the history
  status model or the work's artifacts.

## Description

Implement the accepted ADR as one task — restructure the run model into a
stable two-pass cycle and open the build domain to tool package integrations
over it:

1. **Stable cycle.** Every non-skipped run is exactly two ralphex invocations:
   the tasks pass (`--tasks-only`, the root agent's wrapper, the root env as
   the tasks-pass env layer) then the review pass (`--review`, the review
   agent's wrapper, the review env layer, review-scoped knobs). The combined
   full pass is removed. A failed tasks pass never launches the review pass;
   the run's exit code is the last executed pass's; plan relocation happens
   only on success. The task env never reaches the review pass (secret-safe,
   never printed).
2. **Two-part settings, no universal category.** The `build` config root
   carries the tasks-pass settings (`agent`, `env`, `max_iterations`,
   `session_timeout`, `idle_timeout`, `wait`); the `build.review` key carries
   the review-pass settings (`agent`, `env`, `roles`, `base_ref`, `strategy`,
   `finalize`, `additional`, plus the session knobs). Every unset review value
   inherits the root value; unset at both levels → omit; `additional.agent`
   inherits `review.agent`. Review strategy `full | medium | short` — default
   `medium` (internal only; external review explicitly disabled); `short` runs
   the review pass as ralphex `-e` under the additional agent's wrapper;
   `skip` remains the tri-state all-or-nothing kill switch (CLI > config).
   `build.review.additional` threads onto ralphex's external-review surface:
   `agent`, `patience` (`--review-patience`, 0 = disabled), `max_iterations`
   (`--max-external-iterations`; 0 = ralphex auto). `build.review.finalize` is
   a user-authored string prompt: when set, goga materializes the ralphex
   files for the finalize step and enables it (`finalize_enabled = true`)
   during the defaults sync; when unset the step stays at ralphex's default
   (off).
3. **Worktree retirement and breaking removals.** The `--worktree` flag, the
   `build.worktree` key, and the host-side two-pass × worktree guard are
   removed outright; a stale `worktree` key in an existing config is simply
   ignored (the loader extracts known fields only). `--skip-finalize` /
   `skip_finalize` and `codex_review` disappear with no replacement. Breaking
   changes, no compatibility paths (major-version window). This repository's
   own build section migrates to the new two-part form in the same change
   (the project dogfoods its build).
4. **Hooks surface.** Five additive catalog records under the `build` domain —
   the hard `validate_build` gate plus the soft notifications
   `build_started`, `pass_started`, `pass_completed`, `build_completed`; no
   existing record changes. A per-domain hooks zone fully symmetric with the
   open domains consumes the `goga/hooks` facade; one `HookRegistry` per run
   is shared by all five checkpoints. The gate is a staged per-tool walk run
   to completion: every subscribed tool's validation hooks run (no early
   stop); each approves silently or vetoes with a reason; a crashing hook
   counts as that tool's veto with the crash reason. All vetoes merge into
   one clean error listing every violation (tool, hook, reason); exit code 1;
   no pass launches; the plan is not relocated; no started/pass/completed
   events fire. The gate modifies nothing — a deliberate domain-local
   deviation from the platform's stop-at-first-failure hard semantics,
   following the `per-tool-delivery` precedent. The four notifications use
   the standard fire-and-forget soft emission (a failing hook warns naming
   tool, action, reason).
5. **Checkpoint contexts.** A uniform envelope (`plan`, `work` — branch +
   topic when hosted, branch-only otherwise, `"unknown"` branch fallback —
   and `dry_run`) plus moment facts. The gate and `build_started` carry both
   resolved parts (env presence as names only). The pass contexts carry the
   stage, executor, pass option facts (including strategy/additional/finalize
   facts on the review pass) and the actual exit code.
   `build_completed` carries the final exit code, the executed stage
   sequence, the relocation outcome, and the work's current history statuses
   at the completion moment — recomputed after the relocation attempt (moved
   or not; branch-only form delivers an empty list). Contexts carry the full
   `finalize` prompt text when configured. All contexts are read-only; env
   values are never delivered anywhere; facts resolve in the operation before
   delivery from the operation's own data and the history store — no git
   reads at a checkpoint moment.
6. **CLI.** No new flags. `--worktree` and `--skip-finalize` are removed;
   `--review-patience` addresses `build.review.additional.patience`;
   `skip_manifest_check` stays a CLI-only pre-check toggle outside both
   parts.
7. **Documentation.** Tool-author usage docs covering all five actions —
   address, firing moment, context members, failure semantics — so every
   build integration scenario is answerable from the docs.

## Scope

**In scope:**

- The five build-domain actions on the hooks platform with their additive
  catalog records: `validate_build` (verdict-collecting veto gate with a
  merged error) and the soft notifications `build_started`, `pass_started`,
  `pass_completed`, `build_completed`.
- The stable-cycle restructure: always two separate passes; the two-part
  flattened settings model with root inheritance; `strategy`
  full | medium | short; the `additional` external-review block; the
  `finalize` prompt; tri-state review skip; exit-code and plan-relocation
  semantics.
- The breaking-removals and CLI surface: the worktree retirement
  (flag, config key, host-side guard — no compatibility path), the
  `--skip-finalize` / `skip_finalize` and `codex_review` removals, and the
  `--review-patience` repointing to `build.review.additional.patience`
  (`skip_manifest_check` unchanged, CLI-only).
- The delivered checkpoint contexts: resolved run facts, bound stage
  composition, work identity (degraded branch-only form allowed), history
  statuses at completion, relocation outcome, `dry_run` — env presence
  instead of values.
- Edge semantics: pre-launch failures fire no events; dry-run fires events
  with the `dry_run` fact; a blocked run fires nothing after the gate.
- Diagnostics: `goga hooks` inspection of build subscriptions; never-cached
  registration; warnings/errors naming tool, action, reason.
- The hooks-layer zero-impact guarantee with no tool packages installed.
- Tool-author usage documentation of the five actions.
- Updating this repository's own `.goga/config.yml` build section to the new
  two-part form (the project dogfoods its build; the old block names become
  unknown keys and would silently disable the build section).

**Out of scope:**

- Any consumer of the new surface: bundled, built-in, or reference
  `goga_tool_*` packages — including the artifact → history-status
  integration (third-party territory).
- Config hooks — tool personalization or modification of build settings.
- Inside-pass or stage-level events during ralphex execution, and any change
  to ralphex itself (execution boundary).
- Host-side launcher moments as hook moments (secret env-file preparation,
  `.ralphex/` mount lifecycle, `--clean`) and any new host CLI flags.
- Behavior of the other hook domains (topics, statuses, onboarding,
  pipeline).
- Reporting, analytics, or telemetry products built on the events.
- Migration aids or deprecation shims for the removed or reshaped settings —
  the `worktree` flag and key, the `--skip-finalize` flag and `skip_finalize`
  key, the `codex_review` key, and the `task_executor` / `review_executor`
  block names (explicitly rejected — breaking changes).

## Acceptance Criteria

Verbatim from the PRD's success criteria:

- **SC1** A third-party `goga_tool_*` package, with no goga code change, can
  subscribe to all five build actions; `goga hooks` shows its build
  subscriptions.
- **SC2** Every non-skipped run executes exactly a tasks pass then a review
  pass with the bound per-stage settings — including the formerly combined
  case of identical executors with no env; a skipped review yields exactly
  one tasks pass.
- **SC3** With a policy tool subscribed, a vetoed run stops before any pass
  with one merged error listing every violation (tool, hook, reason); exit
  code 1; nothing executes; the plan stays in place; no
  started/pass/completed events fire; a non-vetoing gate subscriber is still
  invoked.
- **SC4** A crashing notification hook warns naming tool, action, and reason —
  the run's exit code and outcome are unaffected; `pass_completed` and
  `build_completed` fire on zero, non-zero, and spawn-failure returns alike,
  carrying the actual exit code.
- **SC5** `build_completed` carries the relocation outcome, `dry_run`, the
  work identity, and that work's history status at the moment — the artifact
  → history-status integration is buildable by a third-party tool from
  documented facts alone; no context ever carries env values.
- **SC6** A dry-run rehearses the identical event structure with the
  `dry_run` fact; the gate runs; nothing executes; the plan is not
  relocated.
- **SC7** With no tool packages installed, the hooks layer is unobservable —
  same output, errors, and exit codes as before the change (modulo the
  deliberate stable-cycle and worktree changes).
- **SC8** The worktree flag and config setting no longer exist anywhere on
  the build surface; the run model contains no worktree mode.
- **SC9** The tool-author documentation answers each integration scenario
  named in the problem — reporting, automation, and external notifications
  over build moments; connecting outcomes to statuses and artifacts; and
  policy enforcement via the gate — from moments, context members, and
  failure semantics alone.
- **SC10** Tool package edits apply from the next command without reinstall.

Validation commands (project conventions): `pytest tests/ -x`, `ruff check`
over the touched packages, facade checks for the new zone, and absence
checks for the removed surface — `--worktree`, `--skip-finalize`, the
`worktree` / `skip_finalize` / `codex_review` config keys, and the
`task_executor` / `review_executor` block names — across the CLI and the
config loader.

## Stack

- **Frameworks:** none new — Python 3.10+ stdlib only (project language:
  python)
- **Libraries:** stdlib `dataclasses` (`kw_only=True`) for the restructured
  settings model; `click` for the existing `goga build` CLI edits; stdlib
  `logging` for structured, secret-safe diagnostics; PyYAML (existing) for
  the restructured loader's yaml.safe_load parsing
- **Infrastructure:** goga Docker container execution (existing
  `DockerRunner`); the external ralphex binary as the pass executor —
  unchanged, observed only at goga's own moments

## External Dependencies

| Component | Usage file                        | Status   |
|-----------|-----------------------------------|----------|
| ralphex   | `.goga/usages/cooks/ralphex.md`   | updated  |
| click     | `.goga/usages/cooks/click.md`     | existing |
| PyYAML    | inline `yaml` practice of `goga/config/project` | existing |

`ralphex.md` was updated during grooming (approved): the external review
surface (`external_review_tool` codex|custom, `custom_review_script`,
`--max-external-iterations` with the 0 = auto rule), the finalize step
(`finalize.txt` + `finalize_enabled` materialization), the always-two-pass
wording, and the `--base-ref` source key repointed to `build.review.base_ref`.

## Risks and Constraints

- **C1 Execution boundary** — pass execution belongs to ralphex; goga observes
  only its own moments; no inside-pass events; ralphex is not changed.
- **C2 Runtime boundary** — hooks delivery runs inside the goga Docker
  container; host-side launcher moments are not hook moments.
- **C3 Platform delivery** — no filtering by eligibility; installation trust
  level; one registry per run; fixed offered parameter names; per-tool
  isolated contexts; a broken package import is the only fatal case.
- **C4 Catalog additivity** — published records are never rewritten.
- **C5 Secret safety** — env values never delivered, never printed; names
  only.
- **C6 Veto-only hard surface** — tools cannot modify build settings in this
  scope.
- **C7 Major-version window** — breaking changes without compatibility paths.
- **C8 Hooks-layer zero impact** — with no tools installed, no observable
  difference.
- **C9 No git reads at checkpoints** — facts come from the operation's own
  data and the history store.
- **C10 Documentation surface** — every action's moment, context members, and
  failure semantics documented for tool authors.
- Deferred to the architecture stage (recorded in the ADR): cell boundaries
  and contract shapes for the hooks zone (context types, signatures, the gate
  walk's composition over the facade); the exact threading of
  `additional.agent` onto ralphex's external-review surface; the file form of
  the finalize materialization.

## Scope Estimate

Single task — no subtask breakdown (approved). Large but coherent: four
modified cells plus one new per-domain hooks zone (by precedent, the
pipeline and topics zones carry ~11 types each) plus usage documentation.
Decomposition into cells and execution plans belongs to the architecture
stage.

## Existing Architecture

Link connections examined against the cell schema:

- `goga/config/project` (re-exported through the `goga/config` facade):
  `BuildConfig`, `TaskExecutorConfig`, `ReviewExecutorConfig`,
  `load_project_config` — restructured into the two-part model; consumed by
  `goga/build` (types) and `goga/commands/build` (loaders). The
  `goga/config` facade's re-export list follows the reshaped type names
  mechanically (its `TaskExecutorConfig` / `ReviewExecutorConfig` embeddings
  update or drop out with the two-part model) — a consumer that tracks the
  restructuring, not a design owner.
- `goga/build` — the run model: pass composition, exit semantics, ralphex
  defaults sync, plan relocation; integrates the new checkpoints. Imports
  today from `goga/agents` (wrapper resolution), `goga/config`, `goga/docker`
  (ensure-in-docker), `goga/ralphex` (`run_ralphex`).
- `goga/commands/build` — the host-side CLI wrapper: flag removals,
  `--review-patience` repointing, removal of the two-pass × worktree guard.
- `goga/hooks/catalog` — `Action` / `declared_actions`: five additive `build`
  domain records; the catalog is consumed by the facade, the tools/dispatch
  sub-cells, and `goga/history/statuses` — additivity keeps those consumers
  untouched.
- New per-domain hooks zone (placement follows the `goga/pipeline/hooks` /
  `goga/topics/hooks` precedent) — consumes the `goga/hooks` facade
  (`HookRegistry`, `build_hook_arguments`, `declared_actions`,
  `emit_hook_event`, `wrap_context`) with the `declaring-actions`,
  `per-tool-delivery`, `registering-hooks` practices; work identity and
  completion statuses come from `goga/history`
  (`resolve_current_branch_name`, `collect_topic_statuses`) without new git
  surface.
- `goga/ralphex` — the thin launcher `run_ralphex` consumes the resolved
  per-pass options; option resolution stays in `goga/build`.

## Notes

- No code examples in this task (stage constraint); no architecture is fixed
  here — cell boundaries and contract shapes are the architecture stage's
  territory.
- The gate's verdict-collecting walk is a domain-local deviation from the
  platform's hard semantics; the platform cells are not touched.
- The default strategy `medium` explicitly disables external review —
  deliberate (reflects goga's current effective behavior), per the ADR.
- Grooming decisions (all user-approved): formulation and boundaries as
  above; the stack (existing components only, no new usage files); the
  `ralphex.md` update (five edits, applied); a single task with no
  breakdown.
