# Open the usages domain to the hooks platform as four soft run-level moments

## Current State

- The hooks platform (`goga/hooks` — catalog, dispatch, registry, tools) exposes subscription
  addresses for seven command domains: pipeline, build, topics, config, schema, onboarding,
  statuses. The usages domain has no address — `goga usages sync` and `goga usages status`
  run as opaque operations for tool-package authors.
- The usages domain lives in the `goga/usages` cell with two subcells: `goga/usages/sync`
  (routine `sync` plus the deployment primitives `clone_repository`, `deploy_usages`,
  `clean_usages_dir`) and `goga/usages/status` (routine `status` with the fact types
  `DepStatus`, `EntryChange`, `EntryKind`, `EntryStatus`, `UsageState`, `UsageStatusReport`
  and the helpers `compute_dep_status`, `hash_tree`). Both operations already resolve the
  effective configuration through `goga/config/hooks` (the `config/amend_config`
  checkpoint) — the layer that owns moment delivery per the ADR.
- CLI wrappers live in `goga/commands/usages` (depends on the `goga/usages` facade); their
  rendered output and exit codes are a consumed contract.
- Documentation: `docs/features/usages/hooks.md` states the domain exposes no hook actions;
  `docs/features/hooks/hooks.md` enumerates the per-domain action catalog.
- The decision record `.goga/history/2026/add-hooks-to-usages/adr.md` settles the fact
  shapes and delivery semantics this task implements; the PRD
  `.goga/history/2026/add-hooks-to-usages/prd.md` holds the full requirement set.

## Description

Add four soft actions to the hooks catalog under the `usages` domain — `sync_started`,
`sync_completed`, `status_started`, `status_completed` — and deliver the moments from
inside the domain operations themselves, so the lifecycle wraps the operation: the started
moment fires once the effective configuration is resolved, and the completed moment fires
on every return path after start, including an unexpected crash. The zone is
notification-only: hooks observe and cannot alter, veto, or defer the operations.

Facts, as settled in the ADR:

- **Started contexts.** The operation kind, the applied `group`/`dep` filters, and — for
  sync — the force flag. Fire-and-forget; nothing is collected.
- **`sync_completed`.** For every matched dep its outcome (synced / skipped as already
  present non-force / failed) with the credential-free failure message of each failed dep
  (the same formulation the command logs), plus the run's overall success. Outcome-level
  only — no deployed-file counts.
- **`status_completed`.** One record per changed-set entry: the dep identity (group + dep
  name), its verdict (new / out of date / error), its credential-free error message when
  error, and its per-file change list (relative posix path within the dep + added /
  modified / removed). Directory nodes and unchanged entries are absent — the per-node
  aggregated diff the check renders under `--info` is a rendering convenience, not a fact.
  Plus the overall outcome: an empty changed set reads as no drift among the matched deps.
- **Terminal marker.** Both completed contexts state whether the operation finished
  (success / failure) or broke off (crashed — facts are partial, overall failure, plus a
  credential-free crash reason). Without the marker a subscriber cannot tell a final
  accounting from an aborted fragment.
- **Terms.** A matched dep is a dep of the effective (post-amendment) `usages` section that
  passes the applied filters; filtered-out deps are silently absent from facts. The moments
  wrap the operation, not the workload: no-op runs (absent/empty `usages` section, or
  filters matching no dep) fire both moments with the empty fact set, and an abort at the
  configuration boundary fires nothing.

## Scope

**In scope:**

- The four new catalog actions under the `usages` domain, all soft error class, added
  additively (every existing record stays unchanged in meaning).
- Moment delivery around the `sync` and `status` operations with the facts above, riding
  the existing platform contract: registration contract, fixed offered parameter names,
  per-tool isolated contexts, deterministic enumeration order, never-cached registration.
- Registry economics: the registry is assembled once per command run regardless of how
  many of the four moments fire (the platform `build_once` idiom).
- Visibility of the four addresses in the existing registry inspection surface
  (`goga hooks`), uniform with existing domains.
- Documentation updates: rewrite `docs/features/usages/hooks.md` (drop the "no hook
  actions" statement; document the four actions, their contexts' facts, and their soft
  class) and extend the per-domain action enumeration in
  `docs/features/hooks/hooks.md`.
- Credential-free formulation of every new fact and diagnostic.
- Tests covering: subscription and validation behaviour on the new addresses; started and
  completed fact delivery; completion on every return path including the crash path with
  the terminal marker; no-op runs; abort semantics at the configuration boundary; soft
  isolation of a failing hook; zero-subscriber neutrality; credential safety.

**Out of scope:**

- Cell placement of the usages hooks zone, its wiring, and contract shapes — owned by the
  architecture stage (brainstorm) of the pipeline.
- Any amendment or veto checkpoint in the usages domain — dependency-set amendment stays
  in the config domain (C5).
- Per-dep granularity events — the moments are run-level.
- Any change to the sync/status operations' observable behaviour: best-effort per-dep
  isolation, rendering, exit codes, read-only nature stay as-is (adding moment delivery
  inside them is in scope; it wraps the operations without participating in them).
- New CLI commands or flags — the discovery surface already exists and only inherits the
  new addresses.
- Changes to other domains' actions or to the platform core semantics beyond the additive
  catalog records.
- A first-party example/consumer tool package; analytics on hook usage; new tutorials or
  tooling beyond the existing documentation surface.
- Code examples in this document (stage constraint).

## Acceptance Criteria

- **Subscription and discovery.** A tool package registering hooks on all four `usages`
  addresses has every registration accepted and visible in the `goga hooks` tree under the
  usages domain; a registration against a wrong address is refused with the standard
  warning while the remaining registrations apply.
- **Moments deliver the facts.** In a `goga usages sync` run with a subscribed probe tool,
  its hooks receive the started context (operation kind, filters, force flag) and, at
  completion, each matched dep's outcome with failure messages, the run's overall
  success, and the finished terminal marker (success / failure). In a `goga usages
  status` run, they receive the started context and the changed-set records — each
  non-up-to-date dep's identity, verdict, per-file change list, and credential-free
  error message when error — plus the overall outcome and the finished terminal marker
  (success / failure).
- **Crash completion.** When the operation breaks off unexpectedly, the completed moment
  still fires with the best facts known at the crash point, the overall failure, the
  crashed terminal marker, and a credential-free crash reason.
- **No-op runs.** With an absent `usages` section or filters matching no dep, both moments
  of the operation still fire, carrying the empty fact set.
- **Abort semantics.** A run aborting at the configuration boundary (config load error or
  hard config-checkpoint failure) fires no usages moment.
- **Soft isolation.** A hook raising on any of the four actions yields exactly one
  standard warning naming the hook, the tool, the action, and the reason; the operation
  still completes with unchanged output and exit code, and the remaining tools still
  receive the moment.
- **Zero-subscriber neutrality.** With no subscribers — including with no tool packages
  installed at all — both commands behave byte-for-byte as before the change.
- **Credential safety.** No context fact or diagnostic exposed to hooks carries a
  credential-bearing value, including when a dep fails to clone from a URL with an
  embedded token.
- **Registry economics.** The hook registry is assembled exactly once per command run
  regardless of how many of the four moments fire.
- **Documented face.** The usages hooks page documents the four actions with their facts
  and soft class; the registration documentation's action enumeration includes the usages
  addresses.
- **Catalog additivity.** Every pre-existing action record and its delivery behaviour is
  unchanged.

## Stack

- **Frameworks:** Click (existing CLI framework — no new command surface)
- **Libraries:** Python stdlib only for new logic — `dataclasses` (`kw_only=True`) for
  fact/context records, `logging` (structured, credential-free messages)
- **Infrastructure:** none — the hooks platform is in-process; the registry is assembled
  once per run

## External Dependencies

| Component                            | Usage file                            | Status                       |
|--------------------------------------|---------------------------------------|------------------------------|
| click                                | `.goga/usages/cooks/click.md`         | existing (no new patterns)   |
| pytest / ruff / pytest-cov           | `conventions.md`                      | existing                     |

No new external dependencies; no usage files to create or update.

## Risks and Constraints

- **C1 — Catalog additivity.** The action catalog is append-only in product terms; the
  four records are added, every existing record stays identical in meaning.
- **C2 — Platform delivery contract.** The moments must ride the existing platform — no
  parallel or special-case delivery mechanism for the usages domain.
- **C3 — Credential safety.** Git URLs may embed credentials; no context, warning, or
  error message may expose a credential-bearing value — facts use the same
  credential-free formulations as the commands' own logs and rendered messages.
- **C4 — Command contract stability.** The rendered output and exit codes of both commands
  must not change under any subscription state.
- **C5 — Notification-only zone.** No amendment, no veto, no deferral; the usages zone
  must not grow an overlapping amendment moment.
- **C6 — Operation semantics preserved.** Sync's best-effort per-dep isolation and
  status's read-only nature are unchanged; the moments wrap the operations without
  participating in them.
- **Crash-path discipline.** Crash completion must not mask the original failure: the
  crash reason travels as a fact, and the command's own error behaviour is untouched.
- **Docs consistency.** The documented face must match the catalog exactly — page rewrite
  and enumeration update land together with the records.

## Scope Estimate

Single task — no decomposition. The feature is one cohesive domain change (four additive
catalog records + moment delivery inside the two usages domain operations + two docs
pages); splitting it would sever natural dependencies (the docs describe the catalog, the
delivery relies on the records). Architecture, cell placement, wiring, and contract shapes
proceed to the architecture stage (brainstorm) of the pipeline rather than becoming
subtasks.

## Existing Architecture

- `goga/hooks` — the platform facade: `declared_actions` (catalog data, append-only;
  owned by the `goga/hooks/catalog` subcell — the append point of the four records),
  `emit_hook_event`, `build_hook_arguments`, `wrap_context`, `HookRegistry` (assembled
  once per run via the `build_once` idiom), `enumerate_tool_packages`.
- `goga/config/hooks` — the config-checkpoint precedent (`ConfigHooks`, `ConfigOverlay`);
  both usages operations already resolve the effective configuration through it, and the
  moments fire only after that resolution.
- `goga/build/hooks`, `goga/topics/hooks` — reference zones for the delivery idiom
  (declaring actions, per-tool delivery, completion on every return path; transport of the
  shared registry as an implementation detail).
- `goga/usages` — the domain facade with the `sync` and `status` subcells; the domain
  operations own the moments and compute the facts.
- `goga/commands/usages` — the CLI wrappers; per the ADR they are not the delivery owner.
- Docs surface: `docs/features/usages/hooks.md`, `docs/features/hooks/hooks.md`.

Integration requirements: the four catalog records are additive; the moments ride the
existing platform contract; new cross-cell connections (the exact wiring of the usages
hooks zone) are designed by the architecture stage, respecting the DSL's prohibition of
cross-imports between cells.

## Notes

- Input artifacts: the PRD (`.goga/history/2026/add-hooks-to-usages/prd.md`) and the ADR
  (`.goga/history/2026/add-hooks-to-usages/adr.md`); the ADR is authoritative where the two
  overlap (it post-dates and refines the PRD's fact wording).
- The ADR deliberately leaves cell placement, wiring, and contract shapes out of scope;
  this task must not pre-commit them.
- Formulation interview: current state and scope boundaries confirmed; stack confirmed
  with no new external dependencies; single-task estimate confirmed.
