# usages — delivering the usages checkpoints

How the sync and status operations consume the hooks zone of the usages
domain: emitting the started moment once the effective configuration is
resolved and the completed moment on every return path — including an
unexpected crash. For the usages domain operations.

## The checkpoint surface

One `UsagesHooks` object serves every moment of a run — the surface shares
one registry per run, so a run that reaches several moments enumerates the
tool packages once.

    from goga.usages.hooks import UsagesHooks

    hooks = UsagesHooks()

## Resolve the facts in the operation

Every context is built from the values the caller passes — the moments read
no configuration and touch no git. Resolve before the delivery:

- `UsagesMoment` — the operation kind (sync or status) with the applied
  `group`/`dep` filters, exactly as the operation received them.
- Sync-start facts — the force flag.
- Sync-completion facts — one `SyncDepOutcome` per matched dep (synced /
  skipped / failed, with the credential-free failure message of each failed
  dep) and the run's overall success.
- Status-completion facts — one `DepDrift` per matched dep whose verdict is
  not up to date (identity, verdict, credential-free error message when
  error, per-file change list) and the overall outcome.

A matched dep is a dep of the effective (post-amendment) usages section
that passes the applied filters; filtered-out deps are silently absent from
every fact.

## Emit around the operation

    hooks.emit_sync_started(moment, force)
    outcomes, success = run_sync_work(...)      # the operation's own work
    hooks.emit_sync_completed(moment, outcomes, success, Completion.finished)

- The started moment fires once the effective configuration is resolved —
  after the config amendment checkpoint, before the first dep is processed.
- The completed moment fires on every return path after the start:
  success, per-dep failure, and nothing-to-do alike.

## Complete the crash path

    try:
        outcomes, success = run_sync_work(...)  # partial facts stay collected
    except Exception as reason:
        hooks.emit_sync_completed(moment, outcomes, False, Completion.crashed,
                                  reason=str(reason))
        raise

- The crash completion carries the best facts known at the break-off point,
  the overall failure, the crashed marker, and a credential-free crash
  reason.
- The re-raise preserves the operation's own failure behaviour — the moment
  wraps the operation and never masks it.

## No-op runs and abort semantics

- An absent or empty usages section, or filters matching no dep, still fire
  both moments with the empty fact set — the moments wrap the operation,
  not the workload.
- A run aborting at the configuration boundary (config load error or a
  hard config-checkpoint failure) fires no usages moment.
- With no tool packages installed the whole surface is inert — both
  commands behave as if the zone did not exist.
