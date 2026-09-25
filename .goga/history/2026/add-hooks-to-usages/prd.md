# Usages Domain Hooks Events

Open the usages domain lifecycle — the start and completion of `goga usages sync`
and `goga usages status` — to the hooks platform, so installed tool packages can
observe and react to usages synchronization and drift.

## Problem

Tool-package authors (developers of installed `goga_tool_*` packages) cannot
observe the usages lifecycle. When a project consumes cell-level usages from
git dependencies, `goga usages sync` and `goga usages status` run as opaque
operations: the hooks platform — the extension surface every other command
domain already opens (pipeline, build, topics, config, schema, onboarding,
statuses) — offers no subscription moment at their start or completion.

An installed tool therefore cannot record sync outcomes, surface
drift-detection results in its own channel, or trigger follow-up automation
around imported practices; integrations that need this awareness stay blind.
The only usages-adjacent checkpoint today is `config/amend_config` at
configuration load, which amends the declared dependency set but says nothing
about the operations' execution.

## Users

**Primary — tool-package author.** A developer writing a
`goga_tool_<tool>` package that integrates an external tool (reporter, docs
generator, automation bot) with goga's domains by subscribing hooks to domain
actions. Goal: react to the usages lifecycle — record sync outcomes, surface
drift results in their own channel, trigger follow-up automation. Today they
can subscribe to seven other domains; for usages they have no address to
subscribe to. What matters: a stable, documented set of moments with read-only
facts, delivered in the platform's established shape (fixed offered parameter
names, per-tool isolated context, deterministic order).

**Secondary — goga project developer (end user).** Runs `goga usages sync` /
`goga usages status` on a project consuming usages from git dependencies, with
tool packages installed. Goal: imported practices stay current without the
operation changing character. Expectations: the commands' behaviour, output,
and exit codes remain the contract; subscribed tools never break the
operations — a failing hook is a warning, not a failure.

## Goals

1. **Make the usages lifecycle observable to installed tools.** A
   tool-package author can subscribe to the start and completion of both
   usages operations — sync and status — and receive the run's facts at those
   moments in the same shape the platform's other domains already offer. This
   removes the blindness that today forces integrations around imported
   practices to stay out-of-band.
2. **Make the usages domain a uniform citizen of the hooks platform.**
   Subscribing, delivery, error treatment, registry inspection, and
   documentation for the new usages moments behave exactly like the existing
   domains — no special cases in the tool-author experience; the domain simply
   joins the catalog the platform already exposes.
3. **Preserve the operations' character for end users.** Adding observability
   changes nothing about how `goga usages sync` and `goga usages status` run
   for the project developer: same output, same exit codes, same failure
   semantics — subscribed tools observe the operations but can never break or
   slow their meaning.

## User Experience

**Entry point (tool-package author).** The author opens the hooks
documentation or inspects the registry with `goga hooks` to discover
subscription addresses. Where the usages domain today shows no actions of its
own, they now find four addresses — the start and completion moments of both
usages operations — listed and documented uniformly with the other domains.

**Primary scenario (subscribe and react).**

1. In their `goga_tool_<tool>` package the author registers hooks for the new
   addresses with `hooks.subscribe("usages", "sync_started", …)` (and
   likewise `sync_completed`, `status_started`, `status_completed`).
   Registration validates against the catalog: a wrong address is refused
   with a stderr warning naming the tool, action, and reason — the
   registration is skipped, the rest apply.
2. The registrations appear under the tool's line in the `goga hooks` tree;
   nothing is cached — package edits apply from the next run.
3. A project developer runs `goga usages sync` or `goga usages status` as
   always. At the operation's start the started moment fires: every
   subscribed hook receives a read-only context of the operation about to run
   (what was asked — filters, force — and the operation's identity),
   delivered through the platform's fixed parameter rules and the tool's own
   isolated context.
4. At completion the completed moment fires with the facts of the finished
   operation: for sync — what each dep did (synced, skipped as already
   present, or failed) and the run's overall success; for status — the
   changed deps of the drift check: each dep whose verdict is not up to date
   (new / out of date / error) with its per-file change list (added /
   modified / removed usage files) and the same credential-free failure
   messages the command renders. An empty changed set reads as "no drift
   among the matched deps".
5. The tool acts on the facts in its own domain (report, audit, notify). The
   command's own output and exit code are exactly what they were without any
   hook subscribed.

**Alternative scenarios.**

- No subscribers: the moments fire to nobody; the commands behave
  byte-for-byte as today.
- Partial sync failure: completed still fires, carrying which deps failed
  alongside the synced and skipped ones; the exit code keeps its meaning.
- Nothing to do (empty/absent `usages` section, or filters matching no dep):
  the operation still runs its course and both moments fire with the empty
  fact set — the lifecycle wraps the operation, not the workload.
- Repeating the command re-fires the moments; nothing persists between runs.

**Failure scenarios.**

- A hook raises at delivery: it is skipped with the standard stderr warning
  naming the tool, the action, and the reason; the operation continues
  unaffected (soft class) and the completed moment still fires for the
  remaining tools.
- The operation aborts before it properly starts (config load error or hard
  config-checkpoint failure): neither usages moment fires — the existing
  clean error path is unchanged.
- A broken tool package import remains the one fatal case, reported as the
  platform already does.

**Feedback and closure.** The four addresses are documented on the usages
hooks page with their contexts and soft error class, mirroring the other
domains' pages; the registry tree and registration diagnostics name them
exactly like existing actions. The project developer sees nothing new unless
a hook fails — then one standard warning line, and the run's outcome
untouched.

## Requirements

### Catalog and subscription

- **R1.** The hooks action catalog must expose four new addresses under the
  `usages` domain: `sync_started`, `sync_completed`, `status_started`,
  `status_completed` — all four with the soft error class. The extension is
  additive: every existing record stays unchanged.
- **R2.** A tool package must be able to register hooks on each of the four
  addresses through the existing subscription contract, with the existing
  validation behaviour: a wrong address, an empty hook name, or a repeated
  name per tool per address is refused with a warning naming the tool,
  action, and reason; the rest of the registrations apply.

### Moment behaviour

- **R3. Started moments.** When a `goga usages sync` or
  `goga usages status` run reaches the start of its operation (after the
  effective configuration is resolved), the corresponding started action
  fires. Each subscribed hook receives a read-only context stating what was
  asked: the operation kind, the applied `group`/`dep` filters, and — for
  sync — the force flag. Fire-and-forget; nothing is collected.
- **R4. Sync completion facts.** When the sync operation finishes,
  `sync_completed` fires with the run's facts: for every matched dependency
  its outcome — synced, skipped (already present, non-force), or failed —
  and the run's overall success. No credential-bearing value (e.g. git URLs
  with embedded tokens) may appear in any fact.
- **R5. Status completion facts.** When the status check finishes,
  `status_completed` fires with the drift-centric report: every matched
  dependency whose verdict is not up to date — its verdict (new / out of
  date / error), its credential-free error message when error, and its
  per-file change list (added / modified / removed usage files) as the check
  computed it. Up-to-date dependencies are absent from the facts; the empty
  changed set reports no drift. Read-only facts of a completed check.
- **R6. No-op runs.** Both moments of an operation fire even when there is
  nothing to do (absent/empty `usages` section, or filters matching no
  dependency), carrying the empty fact set — the lifecycle wraps the
  operation, not the workload.

### Failure and error semantics

- **R7. Abort semantics.** If the run aborts at the configuration boundary
  (config load error or hard config-checkpoint failure), no usages moment
  fires; the existing clean-error behaviour is unchanged.
- **R8. Soft delivery.** A failing hook on any of the four actions is
  skipped with the standard stderr warning naming the hook, the tool, the
  action, and the reason. The operation's output, exit code, and the
  delivery to the remaining tools are unaffected; one tool's failure never
  hides a moment from another tool.

### Continuity and discovery

- **R9. Unchanged command behaviour.** With no subscriber on an address —
  including when no tool packages are installed at all — `goga usages sync`
  and `goga usages status` behave exactly as today: same rendered output,
  same exit codes, same timing character.
- **R10. Discovery and documentation.** The four addresses appear in the
  registry inspection surface under the usages domain, uniform with existing
  domains, and the usages hooks documentation documents the four actions,
  their contexts' facts, and their soft class — replacing today's "no hook
  actions" statement.
- **R11. Registry economics.** The hook registry is assembled once per
  command run regardless of how many of the four moments fire — no repeated
  tool-package enumeration per moment.

## Constraints

- **C1. Catalog additivity.** The action catalog is append-only in product
  terms: published records are never rewritten or removed. The four usages
  records are added; every existing record stays byte-identical in meaning.
- **C2. Platform delivery contract.** The new moments must ride the existing
  hooks platform — its registration contract, fixed offered parameter names
  (`context`, `self`), per-tool isolated contexts, deterministic enumeration
  order, and never-cached registration. No parallel or special-case delivery
  mechanism for the usages domain.
- **C3. Credential safety.** The usages domain's established discipline binds
  every new fact and diagnostic: git URLs may embed credentials, so no
  context, warning, or error message may expose a credential-bearing value.
  Facts use the same credential-free formulations as the commands' own logs
  and rendered messages.
- **C4. Command contract stability.** The rendered output and exit codes of
  `goga usages sync` and `goga usages status` are a consumed contract;
  scripts depend on them. The solution must not alter them under any
  subscription state.
- **C5. Notification-only zone.** The four usages actions are soft
  notifications: hooks observe and cannot alter, veto, or defer the
  operations. Amendment of the dependency set already belongs to the
  `config` domain's checkpoint — the usages zone must not grow an
  overlapping amendment moment.
- **C6. Operation semantics preserved.** Sync's best-effort per-dep
  isolation (one dep's failure never aborts the rest) and status's read-only
  nature are unchanged; the moments wrap the operations without
  participating in them.

## Scope

### In Scope

- The four new catalog actions under the usages domain — `sync_started`,
  `sync_completed`, `status_started`, `status_completed` — soft class, added
  additively.
- The usages checkpoint surface: firing the started/completed moments around
  `goga usages sync` and `goga usages status` runs with the read-only facts
  of R3–R6 (operation kind, filters, force flag; per-dep sync outcomes;
  drift-centric status facts — changed deps with their per-file changes),
  delivered through the existing platform contract.
- Subscription, validation, and warning behaviour for the new addresses,
  uniform with existing domains.
- Visibility of the four addresses in the existing registry inspection
  surface (`goga hooks`).
- Documentation updates: the usages hooks page (replacing today's "no hook
  actions" statement) and the platform registration docs that enumerate
  per-domain actions — so the catalog's documented face stays consistent.
- Credential-free formulation of every new fact and diagnostic.

### Out of Scope

- Any amendment or veto checkpoint in the usages domain — dependency-set
  amendment remains the config domain's moment (C5).
- Per-dep granularity events — the moments are run-level.
- Any change to the sync/status operations themselves: best-effort per-dep
  semantics, rendering, exit codes, read-only nature stay as-is.
- New CLI commands or flags — the discovery surface (`goga hooks`) already
  exists and only inherits the new addresses.
- Changes to other domains' actions or to the platform core semantics beyond
  the additive catalog records.
- A first-party example/consumer tool package; analytics on hook usage; new
  tutorials or tooling beyond the existing documentation surface.

## Success Criteria

- **SC1 — Subscription and discovery.** A tool package registering hooks on
  all four `usages` addresses has every registration accepted and visible in
  the `goga hooks` tree under the usages domain; a registration against a
  wrong address is refused with the standard warning while the remaining
  registrations apply.
- **SC2 — Moments deliver the facts.** In a `goga usages sync` run with a
  subscribed probe tool, its hooks receive the started context (operation
  kind, filters, force flag) and, at completion, each matched dep's outcome
  (synced / skipped / failed) plus the run's overall success; in a
  `goga usages status` run, they receive the started context and the
  drift-centric facts — each non-up-to-date dep's verdict, its per-file
  change list, and its credential-free error message when error.
- **SC3 — No-op runs.** With an absent `usages` section or filters matching
  no dep, both moments of the operation still fire, carrying the empty fact
  set.
- **SC4 — Abort semantics.** A run aborting at the configuration boundary
  fires no usages moment.
- **SC5 — Soft isolation.** A hook raising on any of the four actions yields
  exactly one standard warning naming the hook, tool, action, and reason;
  the operation still completes with unchanged output and exit code, and the
  remaining tools still receive the moment.
- **SC6 — Zero-subscriber neutrality.** With no subscribers — including with
  no tool packages installed at all — both commands behave byte-for-byte as
  before the change: same output, same exit codes.
- **SC7 — Credential safety.** No context fact or diagnostic exposed to
  hooks carries a credential-bearing value, including when a dep fails to
  clone from a URL with an embedded token.
- **SC8 — Documented face.** The usages hooks page documents the four
  actions with their facts and soft class (no longer stating the domain
  exposes no actions); the registration documentation's action enumeration
  includes the usages addresses.
- **SC9 — Catalog additivity.** Every pre-existing action record and its
  delivery behaviour is unchanged.
