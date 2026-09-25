# Usages — Hooks

The usages domain exposes **four hook actions** for tool packages — all soft notifications wrapping the two usages operations. The moments are notification-only: hooks observe read-only facts and can never alter, veto, or defer the operations; the commands' output and exit codes are the same whatever is subscribed.

A tool subscribes through its `register_hooks` callable — no goga code changes are needed (see the [registration contract](../hooks/hooks.md)):

```python
def register_hooks(hooks):
    hooks.subscribe("usages", "sync_completed", "reporter", report_sync)
    hooks.subscribe("usages", "status_completed", "drift_watch", watch_drift)
```

## The events

| Address | Error class | Fires |
|---|---|---|
| `usages / sync_started` | soft | Once the effective configuration is resolved, before the first dep is processed — carrying the operation kind, the applied `group`/`dep` filters, and the force flag |
| `usages / sync_completed` | soft | On every return of a started sync — carrying each matched dep's outcome, the run's overall success, and the terminal marker |
| `usages / status_started` | soft | Once the effective configuration is resolved, before the first dep is checked — carrying the operation kind and the applied `group`/`dep` filters |
| `usages / status_completed` | soft | On every return of a started status check — carrying the changed-set records and the overall outcome, with the terminal marker |

Both completed moments state whether the operation finished or broke off: the terminal marker is `finished` when the operation returned through its own paths (the facts are the final accounting, success or failure) and `crashed` when it broke off unexpectedly (the facts are the best known at the break-off point, the run is an overall failure, and a credential-free crash reason travels along). Completion is a fact, not a success claim.

A run aborting at the configuration boundary — a config load error or a hard config-checkpoint failure — fires no usages moment. No-op runs (absent or empty usages section, filters matching no dep) fire both moments with the empty fact set: the moments wrap the operation, not the workload. With no tool packages installed the whole surface is inert — both commands behave as if the zone did not exist.

## The views

All four deliver read-only facts; a failing hook warns naming your tool, the action, and the reason — the operation is never affected.

- `sync_started` — `SyncStarted`: `moment` (the operation kind with the applied `group`/`dep` filters, exactly as the operation received them) and `force`.
- `sync_completed` — `SyncCompleted`: `moment`, `deps` — one `SyncDepOutcome` per matched dep, in iteration order (`group`, `dep`, `outcome` synced / skipped / failed, `message` when failed), `success` (true exactly when no matched dep failed), `completion`, `reason` when crashed.
- `status_started` — `StatusStarted`: `moment`.
- `status_completed` — `StatusCompleted`: `moment`, `changed` — one `DepDrift` per matched dep whose verdict is not up to date, error deps included (`group`, `dep`, `verdict` new / out of date / error, `changes` — the per-file list of relative posix paths with added / modified / removed, `message` when error), `success` (no drift exactly when the changed set is empty), `completion`, `reason` when crashed.

A matched dep is a dep of the effective (post-amendment) usages section that passes the applied filters; filtered-out deps are silently absent from every fact. Directory nodes never appear in the change lists — tools derive structure from the file paths. No fact carries a credential-bearing value: failure and crash messages use the same credential-free formulations the operations themselves log.

## Integration scenarios

- **Sync outcome recording** — subscribe to the two sync moments; read the per-dep outcomes and the overall success; keep state in your `self` context.
- **Drift surfacing** — subscribe to the two status moments; read the changed-set records and the per-file lists; report drift in your own channel.
- **Run accounting** — subscribe to all four; pair every started moment with its completed moment by the `moment` envelope; the terminal marker separates a finished accounting from a crashed fragment.

The sync itself is driven purely by the configuration declarations (see [Configuration](configuration.md)). Both `usages sync` and `usages status` deliver the config amendment checkpoint at their configuration load — the declared deps iterate the effective `usages` section (see [Configuration — Hooks](../../configuration/hooks.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
