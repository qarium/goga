---
status: accepted
---

# Open the build domain over a stable two-pass cycle with a verdict-collecting gate

The build domain joins the hooks platform with five additive catalog actions —
the hard `validate_build` gate plus the soft notifications `build_started`,
`pass_started`, `pass_completed`, `build_completed` — delivered by a per-domain
hooks zone fully symmetric with the open domains (pipeline, topics), and the run
model is restructured into a stable cycle (always a tasks pass then a review
pass as two separate ralphex invocations) so the moment set has a uniform
contract to describe. This ADR records the technical decisions of the discovery
interview (rounds q1–q8); the PRD at `prd.md` has been aligned to them.

## Decision

### Stable cycle and the two-part settings model

- Every non-skipped run is exactly two ralphex invocations: the tasks pass
  (`--tasks-only`, the root agent's wrapper, the root env as the tasks-pass env
  layer) then the review pass (`--review`, the review agent's wrapper, the
  review env layer, review-scoped knobs). The combined full pass is removed; a
  failed tasks pass never launches the review pass; the run's exit code is the
  last executed pass's; plan relocation happens only on success.
- The task env leaves the host-side container env-file and becomes the
  tasks-pass env layer — the review pass never receives it (secret-safe, never
  printed).
- Settings divide into two stage-bound parts with **no universal category**
  (supersedes the PRD line "universal build options apply to every pass"):
  the `build` section root carries the tasks-pass settings (`agent`, `env`,
  `max_iterations`, `session_timeout`, `idle_timeout`, `wait`); the
  `build.review` key carries the review-pass settings (`agent`, `env`,
  `roles`, `base_ref`, `strategy`, `finalize`, `additional`, plus the session
  knobs). Every unset review value inherits the root value; unset at both
  levels → omit. `additional.agent` inherits `review.agent`.
- Review strategy: `build.review.strategy` is `full` (internal agents +
  external review), `medium` (internal only — the default, reflecting goga's
  current effective behavior; goga explicitly disables external review), or
  `short` (external only — the review pass runs ralphex `-e` under the
  additional agent's wrapper). `skip` remains the tri-state all-or-nothing
  kill switch (CLI > config), orthogonal to strategy.
- External review block `build.review.additional`: `agent` (threads to
  ralphex's external-review surface — `external_review_tool` `codex|custom`,
  `custom_review_script`), `patience` (`--review-patience`, 0 = disabled),
  `max_iterations` (`--max-external-iterations`; 0 = ralphex auto:
  `max(3, max_iterations/5)`). No `enabled` key — strategy encodes on/off.
  Replaces the `codex_review` setting.
- `build.review.finalize` is a user-authored string prompt for the final
  review step (finalize is a ralphex review agent, `finalize.txt`). When set,
  goga materializes the ralphex files for the step and enables it
  (`finalize_enabled = true`) during the defaults sync; when unset the step
  stays at ralphex's default (off). Replaces `skip_finalize` (bool mirror);
  the `--skip-finalize` CLI flag is removed with no replacement (a prompt is
  config material).
- The worktree setting is removed outright from CLI and config. A stale
  `worktree` key in an existing config is not special-cased — the config
  loader extracts known fields only and ignores unknown keys (verified against
  the loader contract). The host-side two-pass × worktree guard is removed.
- `skip_manifest_check` stays a CLI-only pre-check toggle, outside both parts.
- CLI surface: no new flags. `--worktree` and `--skip-finalize` die;
  `--review-patience` remains and addresses `additional.patience`; the
  remaining existing flags address the part(s) where their knob lives.

### Hooks surface

- Five additive catalog records under domain `build`; no existing record
  changes. A per-domain hooks zone owned by the build domain consumes the
  `goga/hooks` facade; one `HookRegistry` per run is shared by all five
  checkpoints.
- The gate is a **staged per-tool walk over the facade primitives, run to
  completion**: every subscribed tool's validation hooks run (no early stop);
  each hook either approves silently or vetoes with a reason; a crashing hook
  counts as that tool's veto with the crash reason. All vetoes merge into one
  clean error listing every violation (tool, hook, reason); exit code 1; no
  pass launches; the plan is not relocated; no started/pass/completed events
  fire. The gate modifies nothing. This is a deliberate, domain-local
  deviation from the platform's hard-action semantics ("stop at the first
  failure") — verdict collection requires running every tool.
- The four notifications use the standard fire-and-forget platform emission
  (soft: a failing hook warns naming tool, action, reason).
- Contexts (semantic vocabulary; shapes are contract territory): a uniform
  envelope (`plan`, `work` — branch + topic when hosted, branch-only
  otherwise, `"unknown"` branch fallback — and `dry_run`) plus moment facts.
  The gate and `build_started` carry both resolved parts (env presence as
  names only). The pass contexts carry the stage, executor, pass option facts
  (including strategy/additional/finalize facts on the review pass), and the
  actual exit code. `build_completed` carries the final exit code, the
  executed stage sequence, the relocation outcome, and the work's **current**
  history statuses at the completion moment — recomputed after the relocation
  attempt (moved or not; branch-only form delivers an empty list). Contexts
  carry the full `finalize` prompt text when configured. All contexts are
  read-only; env values are never delivered anywhere.
- Facts resolve in the operation before delivery from the operation's own data
  and the history store; no git reads happen at a checkpoint moment.

## Considered options

- **Gate via plain `emit_hook_event` (hard)** — rejected: platform hard
  semantics stop at the first failure, violating full verdict collection.
- **Changing the platform hard class to collect-all** — rejected: touches the
  pipeline domain's contract; out of scope. The staged per-tool walk precedent
  (`per-tool-delivery`) already exists for domains that need per-tool
  outcomes.
- **Keeping a universal-options category** — rejected by the user: with
  always-two executors, every setting belongs to one of the two parts;
  inheritance preserves the set-once ergonomics.
- **`skip_finalize` as a bool (negative mirror or positive tri-state)** —
  rejected after learning finalize is a ralphex review agent (`finalize.txt`)
  that can carry a user prompt: the prompt form lets the author write the
  final review instructions, with goga preparing the files.
- **An `enabled` key inside `additional`** — rejected: redundant once
  `strategy` (full | medium | short) encodes external review on/off.
- **Nesting review under `review_executor` (keeping today's block names)** —
  rejected in favor of the flattened form (root = task settings, `review` =
  review settings): nesting makes the inheritance-from-root mechanism obvious
  to the configuring user.
- **Two ADRs** (cycle restructure vs domain opening) — rejected: one decision
  system; the moment set is defined over the stable cycle.

## Consequences

- Breaking changes shipped without compatibility paths in the major-version
  window (PRD C7): the combined full pass, the `task_executor` /
  `review_executor` block names, the `worktree` flag and key, the
  `--skip-finalize` flag, and the `codex_review` setting all disappear.
- The PRD's "universal build options apply to every pass" sentence and the
  out-of-scope line "review_executor keeps its shape" are superseded by this
  ADR; the PRD has been edited to match.
- The default strategy `medium` means goga explicitly disables external
  review unless `full`/`short` is configured — deliberate (reflects the
  current effective state), recorded here so it is not read as an accident.
- Open questions deferred to the architecture stage: cell boundaries and
  contract shapes for the hooks zone (context types, signatures, the gate
  walk's composition over the facade); the exact threading of
  `additional.agent` onto ralphex's external-review surface
  (`external_review_tool` / `custom_review_script`); the file form of the
  finalize materialization.
