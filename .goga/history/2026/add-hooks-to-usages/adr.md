# Open the usages domain to the hooks platform as four soft run-level moments

Tool-package authors could subscribe to every other command domain (pipeline, build,
topics, config, schema, onboarding, statuses) but had no address for the usages
lifecycle — `goga usages sync` and `goga usages status` ran as opaque operations. We
decided to add four soft actions to the catalog — `usages/sync_started`,
`usages/sync_completed`, `usages/status_started`, `usages/status_completed` — and to
deliver the moments from inside the domain operations themselves (the same layer that
already delivers the `config/amend_config` checkpoint), so the lifecycle wraps the
operation and the completion facts are exactly what the operation computes. The zone
is notification-only: no amendment, no veto — dependency-set amendment stays in the
config domain.

## Interview decisions

- **Facts are per-dep records, files-only for status.** Each record of the
  `status_completed` changed set carries the dep identity (group + dep name), its
  verdict (new / out of date / error), its credential-free error message when error,
  and its per-file change list (relative posix path within the dep + added / modified
  / removed). Directory nodes and unchanged entries are absent — the per-node
  aggregated diff the check computes is a rendering convenience (`--info`), not a
  fact; tools derive structure from file paths.
- **Both completed moments carry an overall outcome fact** (empty changed set ⇔
  success for status; overall success for sync mirroring it), plus, for `sync_completed`,
  the credential-free failure message of each failed dep (the same formulation the
  command logs). No deployed-file counts — sync stays outcome-level.
- **Completion fires on every return path after start, including an unexpected
  crash**, with the best facts known at the crash point (build-domain precedent:
  completion is a fact, not a success claim).
- **A terminal marker distinguishes finished from crashed.** Both completed contexts
  state whether the operation finished (success / failure) or broke off (crashed —
  facts are partial, overall failure, plus a credential-free crash reason). Without
  it, a subscriber cannot tell a final accounting from an aborted fragment.

## Terms

- **Matched dep** — a dep of the effective (post-amendment) `usages` section that
  passes the applied `group`/`dep` filters. Filtered-out deps are silently absent
  from facts — neither an error nor "skipped".
- **Changed set** — the matched deps whose verdict is not up to date (error deps
  included). Empty set means no drift among matched deps.
- **Operation vs run** — the operation is the domain work from effective-config
  resolution to result return; the run is the whole command process. The moments
  wrap the operation, not the workload: no-op runs fire both moments with empty
  fact sets, and an abort at the configuration boundary fires nothing.

## Considered options

- **Per-node diff tree as facts** (mirroring `--info`) — rejected: derivable from
  file paths, heavier facts, and the PRD's wording is drift-centric and per-file.
- **CLI-wrapper-owned delivery** — rejected: the wrappers would have to reconstruct
  facts only the operations compute (sync's per-dep outcomes are not in its return
  value), and the config-checkpoint precedent puts checkpoint delivery in the domain
  layer.
- **Silence on unexpected crash** (mirroring the config-boundary abort) — rejected:
  a subscriber would hear nothing about a run it saw start; partial facts plus a
  crash marker are strictly more informative.
- **No overall-outcome fact for status** (derivable from changed-set emptiness) —
  rejected: symmetry with `sync_completed` and it spares tool authors the inference
  rule.

## Consequences

- The registry stays one-per-run for free: the platform idiom (`build_once`) already
  guarantees the single assembly; the transport of the shared registry is an
  implementation detail (topics-zone precedent).
- Command output and exit codes are an unchanged contract under any subscription
  state; the platform's soft error class already isolates failing hooks.
- Docs: rewrite `docs/features/usages/hooks.md` (drop the "no hook actions"
  statement) and extend the domain-action enumeration in
  `docs/features/hooks/hooks.md`.
- Cell placement of the usages hooks zone, its wiring, and contract shapes are
  deliberately out of scope here — they belong to the architecture stage.
