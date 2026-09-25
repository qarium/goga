# Opening the Build Domain to Tool Package Integrations

## Problem

Third-party tool package authors cannot integrate with the build domain —
the code-build execution domain of goga (plan orchestration through
ralphex: task and review passes, exit outcomes, plan relocation into
`completed/`). The product already offers a domain extension surface for
installed tool packages — the onboarding, statuses, topics, and pipeline
domains are open — but builds accept no tool participation: a tool can
neither observe build moments nor connect build outcomes to the history
status model or the work's artifacts.

Blocked demand exists today: reporting, automation, and external
notifications over build moments, and advancing the history status model
from build activity — plus policy enforcement over what may be built at
all.

Consequence: any integration between builds and a tool's logic requires
changes inside goga itself. The ecosystem cannot self-serve on the build
domain, the platform's extension promise stays asymmetric, and a tool
author facing an integration task around builds has no defined path —
every "how do I integrate with builds" scenario is currently unanswerable.

A second, structural problem compounds this: the run model itself is
unstable for integration purposes. Whether tasks and review run as one
combined pass or as two separate passes depends on incidental executor
configuration (a differing review agent or a non-empty review env), and
executor settings are not bound to stages (the task env applies to the
whole container, not to the tasks stage). There is no stable, predictable
cycle of build moments for a contract to describe.

## Users

### Primary: tool package author (integration developer)

A developer extending goga by writing an installed `goga_tool_*` package.
Python author; reads the goga usage docs; subscribes through the
package's `register_hooks` facade callback; already familiar with the
hooks platform from the topics, onboarding, statuses, and pipeline
domains.

- **Trying to:** solve an integration task around builds — report on or
  automate build moments (external notifications, CI, dashboards),
  connect build outcomes to the history status model and the work's
  artifacts (plan relocation, run facts), or enforce build policy by
  vetoing runs that violate it.
- **When:** while designing and iterating on the tool package; edits apply
  from the next command without reinstall.
- **What matters:** a complete, predictable contract — which build
  moments exist, what each moment delivers, what a hook may change and
  what it cannot, how hook failures are treated. No integration scenario
  around builds should be left without a documented answer.
- **Constraints:** runs inside the goga container at the trust level of
  the installation; cannot assume goga code changes; tool identity is
  assigned by goga.

### Secondary: build runner (project developer)

Uses goga in a project; runs `goga build <plan>`; installs tool packages
into the environment. Also the owner of the build configuration
(`.goga/config.yml` build section, CLI flags) — the closest thing build
has to an "author" role today.

- **Trying to:** get the build executed as expected, with installed tools
  adding value — and still understand what the tools did to the build.
- **What matters:** builds keep working with tools installed; behavior
  stays predictable; tool participation is observable and diagnosable; a
  failing tool degrades the way the declared error class promises; the
  hooks layer adds nothing observable when no tools are installed.

## Goals

Priority order: G1 → G2 → G3. When openness and predictability conflict,
integration power wins; G3 is preserved as the residual guarantee, not as
a veto.

- **G1 — Openness.** A tool package author can connect their logic to
  build operation — observe build moments and participate where the
  domain allows it — without changes inside goga, exactly as they
  already can in topics, onboarding, statuses, and pipeline.
- **G2 — Contract completeness.** The space of realistic integration
  scenarios around builds is covered definitively: reporting, automation,
  and external notifications over build moments; connecting build
  outcomes to the history status model and the work's artifacts; and
  policy enforcement over runs. A tool author understands from the
  contract how to solve their task — no scenario is left unanswered.
- **G3 — Trustworthy builds.** Opening the domain does not break the
  build experience: for the runner the build stays predictable, tool
  participation is observable and diagnosable, and tool failures degrade
  according to the declared semantics without corrupting builds.

## User Experience

### Established decisions

- **D1 Stable cycle.** Tasks and review always run as separate passes;
  the combined full pass disappears. Every non-skipped run is: tasks
  pass → review pass. Settings divide into two stage-bound parts with no
  universal category: the `build` section root carries the tasks-pass
  settings (`agent`; `env` as the tasks-pass layer — the review pass
  does not receive it; `max_iterations`; the session knobs
  `session_timeout`, `idle_timeout`, `wait`), and the `build.review` key
  carries the review-pass settings (`agent` — inherited from the root
  agent when unset; `env` as the review-pass layer; `roles`; `base_ref`;
  `strategy`; `finalize`; `additional` — the external-review block:
  `agent` inheriting `review.agent`, `patience`, `max_iterations`; the
  session knobs inherit the root values when unset). The worktree
  setting is retired outright — removed from the CLI and the build
  config with no compatibility path (a major-version breaking change; a
  stale `worktree` key in an existing config is simply ignored — the
  loader reads known fields only) — so no run mode depends on it and the
  cycle is uniform.
- **D2 Moment set.** Five build-domain actions: the soft notifications
  `build_started`, `pass_started`, `pass_completed` (per stage pass:
  tasks/review), `build_completed` — and the hard validation gate
  `validate_build`.
- **D3 Validation gate.** `validate_build` fires after goga's own
  pre-checks, before the first pass, with the resolved run facts. Every
  subscribed tool's validation hooks run; each either approves silently
  or vetoes with a reason. Any veto stops the build before start with
  one clean merged error listing every violation (tool, hook, reason). A
  blocked build fires no started/pass events. The gate modifies nothing.
- **D4 Error classes.** The four notifications are soft: a failing hook
  warns naming tool, action, reason; the build is unaffected.
  `validate_build` is hard: vetoes stop the build (merged error).
- **D5 Edge semantics.** goga pre-launch failures (uncommitted
  manifests, invalid review config, unavailable defaults, missing build
  section or agent) fire no events — the moment never happened.
  Pass-failure semantics unchanged: a failed tasks pass skips the review
  pass; the run's exit code is the last executed pass's; plan relocation
  only on success.
- **D6 Dry-run.** Events fire with a `dry_run` fact (rehearsal); the
  gate runs too — a veto blocks the rehearsal consistently; nothing
  executes and the plan never relocates.
- **D7 Secrets.** Env layer values are never delivered — presence/names
  only, in every context.
- **D8 Config hooks deferred.** Amendment/personalization of build
  config by tools is a separate future topic — out of scope here.

### Tool package author

**Entry.** The build hooks usage document — a table of the domain's five
actions: the address (domain `build` + action name), when each fires,
what its context carries, what a hook may do.

**Primary flow.** In their `goga_tool_*` package they subscribe inside
`register_hooks`. They verify with `goga hooks` — their build
subscriptions appear in the inspection tree. Edits apply from the next
command; no reinstall.

**Building an integration.**

- *To observe builds:* subscribe to the notifications; read the plan
  identity, the stage facts (stage identity, executor, option facts),
  the actual exit codes, the relocation outcome, `dry_run`, and the work
  identity — external notifications, CI, dashboards.
- *To enforce policy:* subscribe to `validate_build`; inspect the
  resolved facts and veto with a reason when policy is violated — or
  silently log (the gate doubles as a pre-start notification for its
  subscribers).
- *To connect outcomes to statuses and artifacts:* `build_completed`
  carries the outcome, the relocation fact, the work identity, and that
  work's history status at the completion moment — the artifact →
  history-status integration builds here.

**Failure behavior.**

- A wrong address, an empty name, or a name collision on the same
  address: the registration is skipped with a warning naming the tool
  and the reason; the remaining registrations apply.
- A vetoing or crashing gate hook: the build stops before start with a
  clean error naming the tool, the hook, the action, and the reason —
  all vetoes merged into one message.
- A crashing notification hook: a warning naming the tool, the action,
  and the reason; the build's outcome is unaffected (soft).
- A broken package import: the single fatal case — a clean error naming
  the package.

### Build runner

Commands are unchanged (`goga build <plan>`; no new flags — the
restructure itself removes `--worktree` and `--skip-finalize`, and
`--review-patience` now addresses `review.additional.patience`). With
tools installed:

- **A policy tool may block a build before start:** one clean error
  lists every violation (tool, reason); fix or remove the cause and
  retry. Nothing heavy ever starts; the plan stays in place.
- **The stable cycle is visible:** a tasks pass then a review pass, each
  under its own executor and settings; a skipped review yields exactly
  one tasks pass.
- **Pass outcomes and warnings always name** the tool, the action, and
  the reason when tools are involved.
- **No tools installed:** the hooks layer is unobservable — no
  registration, no gate walk, no events, no output differences. (The
  stable-cycle restructure and the worktree removal themselves apply to
  every run — they are the deliberate product change, not a tool
  effect.)
- **Dry-run:** rehearses the same cycle — events carry the `dry_run`
  fact, the gate runs, nothing executes, the plan stays in place.

### States and feedback

- Errors and warnings always name the tool, the action, and the reason.
- Registration is never cached — tool edits apply on the next command.
- `goga hooks` shows the build subscriptions of the installed tools.

## Requirements

### Domain actions

- **R1.1** The build domain must open exactly five actions: the hard
  validation gate `validate_build` and the soft notifications
  `build_started`, `pass_started`, `pass_completed`, `build_completed`.
- **R1.2** Catalog records are added additively under the `build`
  domain; no existing action or domain record is altered.
- **R1.3** Subscriptions follow the platform envelope —
  `subscribe("build", action, name, hook)`; a wrong address, an empty
  name, or a name collision is skipped with a warning naming the tool
  and the reason; the remaining registrations apply.
- **R1.4** `goga hooks` must show the build subscriptions of installed
  tool packages.

### Stable cycle

- **R2.1** Tasks and review must always run as separate passes; the
  combined full pass is removed. Every non-skipped run is exactly: tasks
  pass, then review pass.
- **R2.2** Stage binding of settings, two parts with no universal
  category: the tasks pass runs under the `build` root settings —
  `agent`, `env` as the tasks-pass layer which the review pass does not
  receive, `max_iterations`, and the session knobs. The review pass runs
  under `build.review`: `agent` — inherited from the root `agent` when
  unset; `env` as the review-pass layer; `roles`; `base_ref`; `strategy`
  (`full` — internal agents plus external review; `medium` — internal
  only, the default, with external review explicitly disabled; `short` —
  external only, the review pass running ralphex `-e` under the
  additional agent's wrapper); `finalize` (the user-authored final
  review prompt — when set, goga materializes the ralphex files for the
  step and enables it; unset leaves the step at ralphex's default, off);
  `additional` (external review: `agent` — inherited from
  `review.agent` when unset; `patience`; `max_iterations`); and the
  session knobs, each inherited from the root when unset.
- **R2.3** Review skip (tri-state CLI > config) yields exactly one tasks
  pass and an absent review stage.
- **R2.4** Exit semantics: a failed tasks pass never launches the review
  pass; the run's exit code is the last executed pass's code; plan
  relocation happens only on success of the final pass.
- **R2.5** The worktree setting is removed from the CLI and the build
  config with no compatibility path (a major-version breaking change);
  no run mode depends on it; the host-side two-pass × worktree guard is
  removed with it.

### Validation gate

- **R3.1** `validate_build` must fire after goga's own pre-checks
  (manifest check, review-config validation, ralphex defaults sync) and
  before the first pass launch — including dry-run runs.
- **R3.2** The gate context must carry the resolved run facts: the plan
  identity, the bound stage composition — both resolved parts (tasks:
  executor, env presence; review: executor with inheritance, env
  presence, roles, base_ref, strategy, the additional facts — agent,
  patience, max_iterations — and the finalize fact with its full prompt
  text when configured), the skip state, `dry_run`, and the current work
  identity (branch + topic when resolvable, branch-only otherwise). Env
  values are never delivered.
- **R3.3** Every subscribed tool's validation hooks must run — no early
  stop between tools; each approves silently or vetoes with a reason;
  any veto stops the build before start with one clean merged error
  listing every violation (tool, hook, reason); exit code 1; no passes
  run; the plan is not relocated; no `build_started`, pass, or
  `build_completed` events fire for a blocked run.
- **R3.4** A crashing gate hook counts as that tool's veto with the
  crash reason named — never a raw traceback.
- **R3.5** The gate modifies nothing: no contribution, no mutation of
  any delivered fact.

### Run notifications

- **R4.1** `build_started` must fire immediately after the gate passes
  and before the first pass launch, carrying the same resolved facts as
  the gate context.
- **R5.1** `pass_started` must fire before each pass launch,
  identifying the stage (tasks/review), the pass executor, the pass
  option facts, and `dry_run`.
- **R5.2** `pass_completed` must fire on every pass return — zero,
  non-zero, and spawn-failure codes alike — carrying the pass facts plus
  the actual exit code. Completion is a fact, not a success claim.
- **R5.3** A failed tasks pass fires its own `pass_completed`; no review
  pass events follow.
- **R6.1** `build_completed` must fire on every return of a started
  build — zero, non-zero, and spawn-failure codes alike — carrying the
  final exit code, the executed stage sequence, the relocation outcome
  (moved or not, and the destination when moved), `dry_run`, the work
  identity, and that work's history status at the completion moment.
- **R6.2** On dry-run, `build_completed` fires with the `dry_run` fact
  and a not-relocated outcome.

### Edge semantics

- **R7.1** Pre-launch failures (uncommitted manifests, invalid review
  config, unavailable ralphex defaults, missing build section or agent)
  fire no events — the moment never happened.
- **R7.2** Env layer values must never be delivered in any context —
  presence/names only, matching the secret-safe dry-run behavior.
- **R7.3** Facts delivered at a checkpoint come from the operation's own
  data and the history store — no git reads happen at a checkpoint
  moment.

### Zero impact and diagnostics

- **R8.1** With no tool packages installed, the hooks layer is inert:
  no registration, no gate walk, no events, no output differences. (The
  stable-cycle restructure and worktree removal are deliberate product
  changes and apply to every run.)
- **R8.2** Registration is never cached — package edits apply from the
  next command without reinstall.
- **R8.3** Every warning and error of the domain must name the tool, the
  action, and the reason.
- **R8.4** A broken tool-package import surfaces as the single clean
  fatal error naming the package.

### Documentation

- **R9.1** Tool-author usage docs must cover all five build actions —
  address, firing moment, context members, failure semantics — so every
  build integration scenario is answerable from the docs.

## Constraints

- **C1 Execution boundary.** Pass execution belongs to the external
  ralphex binary; goga observes only its own moments — settings
  resolution and stage binding, pass launch, pass return code, plan
  relocation. No inside-pass or stage-internal events exist, and ralphex
  itself is not changed.
- **C2 Runtime boundary.** Build hooks delivery runs inside the goga
  Docker container; tool packages must be installed in that environment.
  The host-side launcher moments (secret env-file preparation,
  `.ralphex/` mount lifecycle, `--clean`) are not hook moments.
- **C3 Platform delivery.** Hooks-platform rules hold for the build
  domain: delivery is never filtered by tool eligibility; tools run at
  the trust level of their installation (no isolation, no sandbox); one
  registry per run; hooks receive values only for parameters declared by
  the fixed offered names; per-tool isolated self contexts; a broken
  package import is the only fatal case.
- **C4 Catalog additivity.** The action catalog is extended additively;
  published records are never rewritten — the build actions must not
  alter any existing action or domain record.
- **C5 Secret safety.** Env layer values are never delivered to hooks
  and never printed — presence/names only, identical to the established
  dry-run secret-safety behavior.
- **C6 Veto-only hard surface.** In this scope a tool cannot modify
  build settings: the only hard action is the validation veto. Settings
  personalization by tools (config hooks) is a separate future topic.
- **C7 Major-version window.** The stable-cycle restructure, the
  two-part flattened settings model, and the worktree removal are
  breaking changes shipped without compatibility paths; they are
  accepted for the major version this PRD targets.
- **C8 Hooks-layer zero impact.** With no tool packages installed, the
  hooks layer must add no observable difference — no registration, no
  gate walk, no events, no output changes.
- **C9 No git reads at checkpoints.** Facts delivered at a checkpoint
  come from the operation's own data and the history store; no git reads
  happen at a checkpoint moment.
- **C10 Documentation surface.** The contract reaches tool authors
  through the repo's usage documentation: every build action's moment,
  context members, and failure semantics must be documented.

## Scope

### In Scope

- The five build-domain actions on the hooks platform with their
  additive catalog records: `validate_build` (hard — verdict-collecting
  veto gate with a merged error) and the soft notifications
  `build_started`, `pass_started`, `pass_completed`, `build_completed`.
- The stable-cycle restructure: tasks and review always run as separate
  passes; the combined full pass is removed; the two-part flattened
  settings model (the `build` root as the tasks-pass settings; the
  `build.review` key as the review-pass settings with root inheritance,
  `strategy` full | medium | short, the `additional` external-review
  block, and the `finalize` prompt); tri-state review skip; exit-code
  and plan-relocation semantics.
- The worktree retirement: removal of the `--worktree` flag, the
  `build.worktree` config setting, and the host-side two-pass × worktree
  guard — no compatibility path (major version).
- The delivered checkpoint contexts: resolved run facts, bound stage
  composition, work identity (degraded branch-only form allowed),
  history status at completion, relocation outcome, `dry_run` — with env
  presence instead of values.
- Edge semantics: pre-launch failures fire no events; dry-run fires
  events with the `dry_run` fact; a blocked run fires nothing after the
  gate.
- Diagnostics: `goga hooks` inspection of build subscriptions;
  never-cached registration; warnings/errors naming tool, action,
  reason.
- The hooks-layer zero-impact guarantee with no tool packages installed.
- Tool-author usage documentation of the five actions (moments, context
  members, failure semantics).

### Out of Scope

- Any consumer of the new surface: bundled, built-in, or reference
  `goga_tool_*` packages — including the artifact → history-status
  integration (third-party territory).
- Config hooks — tool personalization or modification of build settings
  (a separate future topic by decision).
- Inside-pass or stage-level events during ralphex execution, and any
  change to ralphex itself (execution boundary).
- Host-side launcher moments as hook moments (secret env-file
  preparation, `.ralphex/` mount lifecycle, `--clean`) and any new host
  CLI flags.
- Behavior of the other hook domains (topics, statuses, onboarding,
  pipeline).
- Reporting, analytics, or telemetry products built on the events.
- Migration aids or deprecation shims for the removed or reshaped
  settings — the `worktree` flag and key, the `--skip-finalize` flag and
  `skip_finalize` key, the `codex_review` key, and the `task_executor` /
  `review_executor` block names (explicitly rejected — breaking
  changes).

## Success Criteria

- **SC1** A third-party `goga_tool_*` package, with no goga code change,
  can subscribe to all five build actions; `goga hooks` shows its build
  subscriptions.
- **SC2** Every non-skipped run executes exactly a tasks pass then a
  review pass with the bound per-stage settings — including the formerly
  combined case of identical executors with no env; a skipped review
  yields exactly one tasks pass.
- **SC3** With a policy tool subscribed, a vetoed run stops before any
  pass with one merged error listing every violation (tool, hook,
  reason); exit code 1; nothing executes; the plan stays in place; no
  started/pass/completed events fire for the blocked run; a
  non-vetoing gate subscriber is still invoked.
- **SC4** A crashing notification hook warns naming tool, action, and
  reason — the run's exit code and outcome are unaffected;
  `pass_completed` and `build_completed` fire on zero, non-zero, and
  spawn-failure returns alike, carrying the actual exit code.
- **SC5** `build_completed` carries the relocation outcome, `dry_run`,
  the work identity, and that work's history status at the moment — the
  artifact → history-status integration is buildable by a third-party
  tool from documented facts alone; no context ever carries env values.
- **SC6** A dry-run rehearses the identical event structure with the
  `dry_run` fact; the gate runs; nothing executes; the plan is not
  relocated.
- **SC7** With no tool packages installed, the hooks layer is
  unobservable — same output, errors, and exit codes as before the
  change (modulo the deliberate stable-cycle and worktree changes).
- **SC8** The worktree flag and config setting no longer exist anywhere
  on the build surface; the run model contains no worktree mode.
- **SC9** The tool-author documentation answers each integration
  scenario named in the problem — reporting, automation, and external
  notifications over build moments; connecting outcomes to statuses and
  artifacts; and policy enforcement via the gate — from moments, context
  members, and failure semantics alone.
- **SC10** Tool package edits apply from the next command without
  reinstall.
