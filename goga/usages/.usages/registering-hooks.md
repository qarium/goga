# usages — registering hooks

How a `goga_tool_*` package subscribes its hooks to the usages domain
actions. For tool package authors; no goga code changes are needed.

The domain opens four actions — all soft notifications around the two
usages operations. The moments wrap the operations: hooks observe
read-only facts and can never alter, veto, or defer the operations; the
commands' output and exit codes are the same whatever is subscribed.

## The events

| Address | Error class | Fires |
|---|---|---|
| `usages / sync_started` | soft | Once the effective configuration is resolved, before the first dep is processed — carrying the operation kind, the applied `group`/`dep` filters, and the force flag. |
| `usages / sync_completed` | soft | On every return of a started sync — carrying each matched dep's outcome (synced / skipped / failed with its credential-free message), the run's overall success, and the terminal marker. |
| `usages / status_started` | soft | Once the effective configuration is resolved, before the first dep is checked — carrying the operation kind and the applied `group`/`dep` filters. |
| `usages / status_completed` | soft | On every return of a started status check — carrying the changed-set records and the overall outcome, with the terminal marker. |

Both completed moments state whether the operation finished (success /
failure) or broke off (crashed — partial facts, overall failure, a
credential-free crash reason). A run aborting at the configuration boundary
fires no usages moment; no-op runs (absent/empty usages section, filters
matching no dep) fire both moments with the empty fact set.

## Subscribe

    def register_hooks(hooks):
        hooks.subscribe("usages", "sync_completed", "reporter", report_sync)
        hooks.subscribe("usages", "status_completed", "drift_watch", watch_drift)

- `domain` — always `"usages"`; `action` — from the table; `name` — unique
  per tool per address; `hook` — the callable executed when the moment
  fires.
- A hook receives values only for the parameters it declares by the fixed
  offered names: `context`, `self`.

## The views

- `sync_started` delivers `SyncStarted`: `moment` (operation kind,
  filters) and `force`.
- `sync_completed` delivers `SyncCompleted`: `moment`, `deps` — one record
  per matched dep (`group`, `dep`, `outcome` synced/skipped/failed,
  `message` when failed), `success`, `completion`, `reason` when crashed.
- `status_started` delivers `StatusStarted`: `moment`.
- `status_completed` delivers `StatusCompleted`: `moment`, `changed` — one
  record per non-up-to-date dep (`group`, `dep`, `verdict`
  new/out-of-date/error, `changes` — the per-file list of relative posix
  paths with added/modified/removed, `message` when error), `success`
  (empty changed set ⇔ no drift), `completion`, `reason` when crashed.

All views are read-only. Directory nodes never appear — tools derive
structure from file paths.

## Integration scenarios

- **Sync outcome recording** — subscribe to the two sync moments; read the
  per-dep outcomes and the overall success; keep state in your `self`
  context.
- **Drift surfacing** — subscribe to the two status moments; read the
  changed-set records and the per-file lists; report drift in your own
  channel.
- **Run accounting** — subscribe to all four; pair every started moment
  with its completed moment by the `moment` envelope; the terminal marker
  separates a finished accounting from a crashed fragment.
