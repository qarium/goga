# Architecture Plan — Usages Domain Hooks (four soft run-level moments)

## Topic

Short name: **Usages domain hooks — sync/status run-level moments**.
Plan path: `.goga/history/2026/add-hooks-to-usages/arch.md` (printed by `goga history path -f arch.md`).

Source inputs: `task.md` (scope), `adr.md` (authoritative fact shapes and delivery semantics),
`prd.md` (full requirement set). The plan covers cell placement, wiring, and contract shapes —
the part the ADR deliberately left to this stage.

## Implementation Order

Ordered leaves → root; each step depends only on already-materialized cells.

1. **`goga/hooks/catalog`** (modify) — append the four soft records; no Imports changes; the
   platform is the leaf everything else rides on.
2. **`goga/usages/hooks`** (create) — the new zone; imports only `goga/hooks` (already
   present), so it can be materialized immediately after the catalog append.
3. **`goga/usages/sync`** (modify) — imports the zone (step 2); its existing imports
   (`goga/config`, `goga/config/hooks`) are unchanged.
4. **`goga/usages/status`** (modify) — imports the zone (step 2) and already imports
   `goga/usages/sync` (step 3, existing edge).
5. **`goga/commands/usages`** (modify, documentation wiring) — imports the
   `registering-hooks` practice from the `goga/usages` facade whose `.usages/` file is
   created in step 2; no behavioral change.
6. **Docs surface** — `docs/features/usages/hooks.md` (rewrite) and
   `docs/features/hooks/hooks.md` (extend); lands together with the records per the
   docs-consistency constraint.

`goga/usages` (facade CODEMANIFEST) is **unchanged**: a zone newly opened inside an existing
domain is wired directly to its consumer surfaces, and the facade is never extended into a
re-export layer for zone contracts.

## Artifacts

### 1. Cell `goga/hooks/catalog` — modify

CODEMANIFEST diff — append to the `Requirements:` block of `declared_actions()`, after the
schema record; nothing else in the file changes:

```yaml
    - The catalog carries the usages sync-start notification action —
      the record domain="usages", name="sync_started", error_class="soft":
      a failing hook of the action is skipped with a warning and the
      operation continues
    - The catalog carries the usages sync-completion notification action
      — the record domain="usages", name="sync_completed",
      error_class="soft": a failing hook of the action is skipped with a
      warning; the completion facts are already delivered
    - The catalog carries the usages status-start notification action —
      the record domain="usages", name="status_started", error_class="soft":
      a failing hook of the action is skipped with a warning and the
      operation continues
    - The catalog carries the usages status-completion notification action
      — the record domain="usages", name="status_completed",
      error_class="soft": a failing hook of the action is skipped with a
      warning; the completion facts are already delivered
```

.usages files: none.

### 2. Cell `goga/usages/hooks` — create

Files: `CODEMANIFEST`, `__init__.py` (facade, `__all__`), `facts.py`, `contexts.py`,
`events.py`, `.usages/checkpoints.md`.

**CODEMANIFEST (full):**

```yaml
Imports:
  - Types:
      - HookRegistry
      - emit_hook_event
      - declared_actions
    Usages:
      - declaring-actions
      - registering-hooks
    From: goga/hooks

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the hooks zone of the usages domain: the fact
  vocabulary of the four run-level moments, the read-only contexts of
  the started and completed facts, and the checkpoint surface that
  emits the moments over the hooks platform. The zone is
  notification-only — a hook observes the facts and cannot alter,
  veto, or defer the operations. All four actions are soft: a failing
  hook warns naming the tool, the action, and the reason, and the
  delivery continues in enumeration order. One registry per run
  carries every moment of a command — the emissions never multiply
  the package enumeration. Every context is built from the values the
  caller passes — no configuration reads, no git access, and no file
  reads happen here. No fact carries a credential-bearing value:
  failure and crash messages use the same credential-free
  formulations the operations themselves log.
  Use the `declaring-actions` practice for the emission contract of
  the four moments.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind every moment.
  Use relative imports.

---

"UsagesMoment(operation: str, group: str | None, dep: str | None)":
  location: facts.py
  annotations: |
    The identity envelope of every usages moment — the operation kind
    with the filters the operation was asked to run.

    `operation`: the operation kind — exactly sync or status
    `group`: the applied group filter — None when no filter was applied
    `dep`: the applied dep filter — None when no filter was applied

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the values mirror the operation's own inputs;
      nothing is read or derived here
    - A dep filtered out by the filters is silently absent from every
      downstream fact — neither an error nor a skipped record
  properties:
    "operation -> str": |
      The operation kind — sync or status.
    "group -> str | None": |
      The applied group filter; None when no filter was applied.
    "dep -> str | None": |
      The applied dep filter; None when no filter was applied.

"SyncOutcome()":
  location: facts.py
  annotations: |
    Fixed value set of a matched dep's sync outcome.

    Members:
    - synced — the dep was cloned and deployed by the run
    - skipped — the dep's target already existed and force was not applied
    - failed — the dep's sync raised; the record carries the
      credential-free failure message

    Requirements:
    - Members map to the verdict strings used by the fact records

    Constraints:
    - Fixed value set (implement as enum.Enum)
  properties:
    "synced -> str": |
      "synced" — the dep was cloned and deployed by the run.
    "skipped -> str": |
      "skipped" — the target already existed and force was not applied.
    "failed -> str": |
      "failed" — the dep's sync raised; the record carries the
      credential-free failure message.

"SyncDepOutcome(group: str, dep: str, outcome: SyncOutcome, message: str | None = None)":
  location: facts.py
  annotations: |
    The sync outcome of one matched dep.

    `group`: the dep's group name
    `dep`: the dep name
    `outcome`: the dep's outcome — synced, skipped, or failed
    `message`: the credential-free failure message when the outcome is
                failed; None otherwise

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The message is set only when the outcome is failed and carries
      the same credential-free formulation the operation logs
    - One record per matched dep — filtered-out deps are absent
  properties:
    "group -> str": |
      The dep's group name.
    "dep -> str": |
      The dep name.
    "outcome -> SyncOutcome": |
      The dep's outcome — synced, skipped, or failed.
    "message -> str | None": |
      The credential-free failure message when failed; None otherwise.

"DriftVerdict()":
  location: facts.py
  annotations: |
    Fixed value set of a changed dep's drift verdict.

    Members:
    - new — the declared dep's target directory is absent
    - out of date — the local tree differs from the remote-rebuilt tree
    - error — the dep could not be checked

    Requirements:
    - Members map to the verdict strings used by the fact records

    Constraints:
    - Fixed value set (implement as enum.Enum)
  properties:
    "new -> str": |
      "new" — the declared dep's target directory is absent.
    "out_of_date -> str": |
      "out of date" — the local tree differs from the remote-rebuilt tree.
    "error -> str": |
      "error" — the dep could not be checked.

"ChangeVerdict()":
  location: facts.py
  annotations: |
    Fixed value set of one file's change between the expected
    (remote-rebuilt) and local trees.

    Members:
    - added — present only in the expected tree
    - modified — present in both trees, the content differs
    - removed — present only in the local tree

    Constraints:
    - Fixed value set (implement as enum.Enum)
  properties:
    "added -> str": |
      "added" — present only in the expected tree.
    "modified -> str": |
      "modified" — present in both trees, the content differs.
    "removed -> str": |
      "removed" — present only in the local tree.

"FileChange(path: str, change: ChangeVerdict)":
  location: facts.py
  annotations: |
    One file's change within a dep — the relative path of the changed
    file and its verdict.

    `path`: the file's relative posix path within the dep
    `change`: the file's change verdict — added, modified, or removed

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Files only — a directory node never appears as a record
  properties:
    "path -> str": |
      The file's relative posix path within the dep.
    "change -> ChangeVerdict": |
      The file's change verdict — added, modified, or removed.

"Completion()":
  location: facts.py
  annotations: |
    The terminal marker of a completed context — whether the
    operation finished or broke off.

    Members:
    - finished — the operation returned through its own paths; the
      facts are the final accounting, success or failure
    - crashed — the operation broke off unexpectedly; the facts are
      the best known at the break-off point and the run is an overall
      failure

    Constraints:
    - Fixed value set (implement as enum.Enum)
  properties:
    "finished -> str": |
      "finished" — the operation returned through its own paths.
    "crashed -> str": |
      "crashed" — the operation broke off unexpectedly.

"DepDrift(group: str, dep: str, verdict: DriftVerdict, changes: list[FileChange], message: str | None = None)":
  location: facts.py
  annotations: |
    One changed-set record of the status check — a matched dep whose
    verdict is not up to date.

    `group`: the dep's group name
    `dep`: the dep name
    `verdict`: the dep's verdict — new, out of date, or error
    `changes`: the per-file change list within the dep — populated
                for the out-of-date verdict, empty for new and error
    `message`: the credential-free error message when the verdict is
                error; None otherwise

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Directory nodes are absent — the change list carries files
      only; structure is derivable from the file paths
    - The message is set only when the verdict is error and carries
      the same credential-free formulation the operation logs
    - The changed set contains no up-to-date dep — an empty changed
      set reads as no drift among the matched deps
  properties:
    "group -> str": |
      The dep's group name.
    "dep -> str": |
      The dep name.
    "verdict -> DriftVerdict": |
      The dep's verdict — new, out of date, or error.
    "changes -> list[FileChange]": |
      The per-file change list within the dep; empty for the new and
      error verdicts.
    "message -> str | None": |
      The credential-free error message when error; None otherwise.

"SyncStarted(moment: UsagesMoment, force: bool)":
  location: contexts.py
  annotations: |
    The read-only context of the sync start — what the sync run was
    asked to do.

    `moment`: the identity envelope of the run
    `force`: the force flag as applied by the run

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a starting operation — a hook observes and
      cannot alter anything
  properties:
    "moment -> UsagesMoment": |
      The identity envelope of the run.
    "force -> bool": |
      The force flag as applied by the run.

"StatusStarted(moment: UsagesMoment)":
  location: contexts.py
  annotations: |
    The read-only context of the status start — what the status run
    was asked to do.

    `moment`: the identity envelope of the run

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a starting operation — a hook observes and
      cannot alter anything
  properties:
    "moment -> UsagesMoment": |
      The identity envelope of the run.

"SyncCompleted(moment: UsagesMoment, deps: list[SyncDepOutcome], success: bool, completion: Completion, reason: str | None = None)":
  location: contexts.py
  annotations: |
    The read-only context of the sync completion — the per-dep
    outcomes of the run, its overall success, and the terminal
    marker.

    `moment`: the identity envelope of the run
    `deps`: one `SyncDepOutcome` per matched dep, in iteration order;
             empty on a no-op run
    `success`: the run's overall success — True exactly when no
                matched dep failed
    `completion`: the terminal marker — finished or crashed
    `reason`: the credential-free crash reason when the marker is
               crashed; None otherwise

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a completed operation — a hook observes the
      outcome and cannot alter it
    - `success` is False whenever the marker is crashed — a crash is
      an overall failure
    - `reason` is present exactly when the marker is crashed; on a
      crash the outcome records are the best facts known at the
      break-off point
  properties:
    "moment -> UsagesMoment": |
      The identity envelope of the run.
    "deps -> list[SyncDepOutcome]": |
      One outcome record per matched dep, in iteration order; empty
      on a no-op run.
    "success -> bool": |
      The run's overall success; False whenever the marker is crashed.
    "completion -> Completion": |
      The terminal marker — finished or crashed.
    "reason -> str | None": |
      The credential-free crash reason; present exactly when the
      marker is crashed.

"StatusCompleted(moment: UsagesMoment, changed: list[DepDrift], success: bool, completion: Completion, reason: str | None = None)":
  location: contexts.py
  annotations: |
    The read-only context of the status completion — the changed-set
    records of the check, its overall outcome, and the terminal
    marker.

    `moment`: the identity envelope of the run
    `changed`: one `DepDrift` per matched dep whose verdict is not up
                to date — error deps included; empty when no matched
                dep drifted
    `success`: the check's overall outcome — True exactly when the
                changed set is empty
    `completion`: the terminal marker — finished or crashed
    `reason`: the credential-free crash reason when the marker is
               crashed; None otherwise

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a completed check
    - `success` is False whenever the marker is crashed
    - `reason` is present exactly when the marker is crashed
  properties:
    "moment -> UsagesMoment": |
      The identity envelope of the run.
    "changed -> list[DepDrift]": |
      One changed-set record per matched dep whose verdict is not up
      to date; empty when no matched dep drifted.
    "success -> bool": |
      The check's overall outcome — no drift exactly when the changed
      set is empty; False whenever the marker is crashed.
    "completion -> Completion": |
      The terminal marker — finished or crashed.
    "reason -> str | None": |
      The credential-free crash reason; present exactly when the
      marker is crashed.

"UsagesHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the usages domain — the four moment
    emissions over the hooks platform.

    Apply the `convention` practice for the code style and
    intra-package imports.
    Use the `declaring-actions` practice for the emission contract of
    every moment.
    Use the `registering-hooks` practice for the registration contract
    behind every moment.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every moment of a command —
      the assembly runs once per run whatever the number of moments
    - Every context is built from the values the caller passes — no
      configuration reads, no git access, and no file reads happen at
      a moment
  methods:
    "emit_sync_started(moment: UsagesMoment, force: bool)": |
      Emit the sync-start moment — what the sync run was asked to do.

      `moment`: the identity envelope of the run
      `force`: the force flag as applied by the run

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Resolve the address domain="usages", action="sync_started"
         against `declared_actions`
      2. Build the `SyncStarted` context from `moment` and `force`
      3. Emit the resolved address via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - A failing hook is skipped with a warning under the soft error
        class of the action — the operation is unaffected
    "emit_sync_completed(moment: UsagesMoment, deps: list[SyncDepOutcome], success: bool, completion: Completion, reason: str | None = None)": |
      Emit the sync-completion moment — the outcomes of a started
      sync run.

      `moment`: the identity envelope of the run
      `deps`: one `SyncDepOutcome` per matched dep, in iteration order
      `success`: the run's overall success
      `completion`: the terminal marker — finished or crashed
      `reason`: the credential-free crash reason; None unless crashed

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Resolve the address domain="usages", action="sync_completed"
         against `declared_actions`
      2. Build the `SyncCompleted` context from the values
      3. Emit the resolved address via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - The emission happens on every return path of a started run —
        finished and crashed alike; completion is a fact, not a
        success claim
    "emit_status_started(moment: UsagesMoment)": |
      Emit the status-start moment — what the status run was asked to
      do.

      `moment`: the identity envelope of the run

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Resolve the address domain="usages", action="status_started"
         against `declared_actions`
      2. Build the `StatusStarted` context from `moment`
      3. Emit the resolved address via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
    "emit_status_completed(moment: UsagesMoment, changed: list[DepDrift], success: bool, completion: Completion, reason: str | None = None)": |
      Emit the status-completion moment — the changed-set records of
      a started status run.

      `moment`: the identity envelope of the run
      `changed`: one `DepDrift` per changed matched dep
      `success`: the check's overall outcome
      `completion`: the terminal marker — finished or crashed
      `reason`: the credential-free crash reason; None unless crashed

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Resolve the address domain="usages", action="status_completed"
         against `declared_actions`
      2. Build the `StatusCompleted` context from the values
      3. Emit the resolved address via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - The emission happens on every return path of a started run —
        finished and crashed alike; completion is a fact, not a
        success claim

---

Author: Goga
CreatedAt: 25/09/26
Description: |
  Owner of the usages domain hooks zone — the run-level moment
  facts, the notification contexts, and the checkpoint surface over
  the hooks platform.
```

**`.usages/checkpoints.md` (full):**

```markdown
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
```

**Domain-level practice on the unchanged facade — `goga/usages/.usages/registering-hooks.md` (full; create):**

```markdown
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
```

### 3. Cell `goga/usages/sync` — modify

CODEMANIFEST diff.

**Header — add import block (after the existing `goga/config/hooks` block):**

```yaml
  - Types:
      - UsagesHooks
      - UsagesMoment
      - SyncDepOutcome
      - SyncOutcome
      - Completion
    Usages:
      - checkpoints AS usages-moments
    From: goga/usages/hooks
```

The `AS` alias resolves the name clash with the existing `checkpoints`
import from `goga/config/hooks`.

**Header — append to `Annotations:` (existing text unchanged):**

```yaml
  The operation owns its run-level moments delivered per the
  `usages-moments` practice: the started moment fires once the
  effective configuration is resolved, and the completed moment fires
  on every return path after the start — including an unexpected
  break-off. The moments are notification-only: they wrap the
  operation without participating in it.
```

**Body — replace the annotation of `sync` (signature unchanged):**

```yaml
"sync(force: bool = False, group: str | None = None, dep: str | None = None) -> exit_code: int":
  location: sync.py
  annotations: |
    Config-driven synchronization of cell-level usages from declared git dependencies
    into .goga/usages/<group>/<dep>/.

    `force`: True — clean .goga/usages/ (except cooks and root *.md) then re-sync all
             declared deps; False (default) — incremental, skip deps whose target dir exists.
    `group`: optional filter — limit the sync to one group name; None (default) → all groups.
    `dep`: optional filter — limit the sync to one dep name; None (default) → all deps. `dep`
           without `group` applies across every group.
    `exit_code`: 0 on success (incl. "nothing to sync"), 1 if any dep failed.

    Algorithm:
    1. Load configuration via `load_project_config` → `ProjectConfig`;
       deliver the config amendment checkpoint per the `checkpoints`
       practice via the `ConfigHooks` checkpoint surface —
       amend_config(config=...) — print the amendment summary lines of
       the `ConfigOverlay` to stderr per the `click` practice (nothing
       when empty), and read the usages declarations of the effective
       configuration. A load or checkpoint failure — ValueError covers
       the hard action, ImportError a broken tool package facade —
       propagates fail-loud at the boundary for the command's wrapper
       to convert; no usages moment fires on this abort
    2. Compose the `UsagesMoment` envelope — the operation kind sync
       with the applied `group`/`dep` filters — and emit the sync-start
       moment per the `usages-moments` practice through the
       `UsagesHooks` checkpoint surface; the started context carries
       the `force` flag and nothing is collected
    3. If ProjectConfig.usages is None → nothing to sync: emit the
       sync-completion moment with the empty outcome set, overall
       success, and the `Completion` marker finished; return 0
    4. usages_root = .goga/usages (relative to CWD)
    5. If `force` → `clean_usages_dir`(usages_root)
    6. For each group, dep, depcfg (`DepConfig`) in ProjectConfig.usages (insertion order),
       **applying the `group`/`dep` filters (a non-matching name is skipped, not an error —
       a filtered-out dep is absent from the outcomes)**:
       6.1. target = usages_root / group / dep
       6.2. If (not force) and target.exists() → record the dep's
            `SyncDepOutcome` with the `SyncOutcome` value skipped
       6.3. Else: repo = `clone_repository`(depcfg.git, depcfg.ref); try:
            `deploy_usages`(repo, target, depcfg.root); finally: remove the repo temp
            directory; on success record the dep's `SyncDepOutcome` with the
            `SyncOutcome` value synced
       6.4. On per-dep error → log ERROR, record the dep's `SyncDepOutcome` with
            the `SyncOutcome` value failed carrying the credential-free message, set
            overall failure, continue (best-effort)
    7. Emit the sync-completion moment — one `SyncDepOutcome` per matched dep, the run's
       overall success (False when any dep failed), and the `Completion` marker finished
    8. Return exit_code

    Requirements:
    - "synchronized" marker = existence of target dir; dep git/ref changes without force do NOT re-sync
    - Clone into a temp dir removed in a finally block
    - deploy receives the dep's optional root verbatim from `DepConfig` (None = walk from
      repo root); `sync` does not resolve or validate root — `deploy_usages` does, against
      the clone
    - A non-matching `group`/`dep` filter value is skipped, never treated as an error; only
      real sync errors on a matching dep set exit_code = 1.
    - The sync-completion moment fires on every return path after the start — the
      nothing-to-do return, the finished return, and the unexpected break-off alike; on a
      break-off the partial outcomes known at the break-off point travel with the overall
      failure, the `Completion` marker crashed, and a credential-free crash reason, and
      the original failure propagates unchanged after the emission
    - A matched dep — a dep of the effective configuration passing the applied filters —
      yields exactly one outcome record; a no-op run (absent usages section or filters
      matching no dep) fires both moments with the empty outcome set
    - The moments wrap the operation without participating in it — output, exit codes, and
      best-effort per-dep isolation are unchanged under any subscription state
    - Every failure fact and diagnostic is credential-free — the same formulation the
      operation logs

    Constraints:
    - Never touch .goga/usages/cooks or root *.md (`clean_usages_dir` owns that)
    - Do not re-sync an existing dep unless force
    - Sources are git only (no local-path mode)
    - Do not let the moments alter the operation — no amendment, no veto, no deferral;
      the zone is notification-only
```

Other members (`clean_usages_dir`, `clone_repository`, `deploy_usages`) and the Footer are
unchanged. .usages files: none.

### 4. Cell `goga/usages/status` — modify

CODEMANIFEST diff.

**Header — add import block (after the existing `goga/config/hooks` block):**

```yaml
  - Types:
      - UsagesHooks
      - UsagesMoment
      - DepDrift
      - DriftVerdict
      - FileChange
      - ChangeVerdict
      - Completion
    Usages:
      - checkpoints AS usages-moments
    From: goga/usages/hooks
```

**Header — append to `Annotations:` (existing text unchanged):**

```yaml
  The operation owns its run-level moments delivered per the
  `usages-moments` practice: the started moment fires once the
  effective configuration is resolved, and the completed moment fires
  on every return path after the start — including an unexpected
  break-off. The moments are notification-only: they wrap the check
  without participating in it.
```

**Body — replace the annotation of `status` (signature unchanged):**

```yaml
"status(group: str | None = None, dep: str | None = None) -> report: UsageStatusReport":
  location: status.py
  annotations: |
    Status check of already-synchronized cell-level usages against the current state of the
    remote git repository, for every declared dep.

    `group`: optional filter — limit the check to one group name; None (default) → all groups.
    `dep`: optional filter — limit the check to one dep name; None (default) → all deps.
      `dep` without `group` applies across every group.
    `report`: aggregate status result over all checked deps.

    Algorithm:
    1. Load configuration via `load_project_config` → `ProjectConfig`;
       deliver the config amendment checkpoint per the `checkpoints`
       practice via the `ConfigHooks` checkpoint surface —
       amend_config(config=...) — print the amendment summary lines of
       the `ConfigOverlay` to stderr (nothing when empty), and iterate
       the declared deps of the effective configuration. A load or
       checkpoint failure — ValueError covers the hard action,
       ImportError a broken tool package facade — propagates
       fail-loud at the boundary for the command's wrapper to convert;
       no usages moment fires on this abort
    2. Compose the `UsagesMoment` envelope — the operation kind status
       with the applied `group`/`dep` filters — and emit the
       status-start moment per the `usages-moments` practice through
       the `UsagesHooks` checkpoint surface; nothing is collected
    3. If the usages section of `ProjectConfig` is None or empty → emit
       the status-completion moment with the empty changed set, the
       no-drift outcome, and the `Completion` marker finished; return
       the empty `UsageStatusReport`
    4. For each group, dep, depcfg (`DepConfig`) declared in `ProjectConfig`, applying the
       `group`/`dep` filters (a non-matching name is skipped, not an error — a filtered-out
       dep is absent from the changed set):
       4.1. If the dep's target directory is absent → build a `DepStatus` with state new
            and derive the dep's `DepDrift` record with the `DriftVerdict` value new and
            the empty change list
       4.2. Otherwise → compute the dep's `DepStatus` via `compute_dep_status` and, when
            the state is out of date, derive the dep's `DepDrift` record with the
            `DriftVerdict` value out of date and the per-file change list of `FileChange`
            records projected from the entry diff — files only, directory nodes dropped,
            each file carrying its `ChangeVerdict`
       4.3. On a per-dep failure (clone/checkout/deploy) → log ERROR with a credential-free
            message, build a `DepStatus` with state error, derive the dep's `DepDrift`
            record with the `DriftVerdict` value error, that message, and the empty
            change list, and continue (best-effort)
    5. Assemble the collected `DepStatus` records into the `UsageStatusReport`
    6. Emit the status-completion moment — one `DepDrift` per matched dep whose verdict is
       not up to date, the overall outcome (no drift exactly when the changed set is
       empty), and the `Completion` marker finished
    7. Return the report

    Requirements:
    - Iteration is strictly over the declared deps (config-driven) — no orphan detection
    - Empty or absent usages section (None or {}) → empty report (exit 0)
    - A non-matching filter value is skipped, never treated as an error
    - The status-completion moment fires on every return path after the start — the
      empty-report return, the finished return, and the unexpected break-off alike; on a
      break-off the partial changed-set records known at the break-off point travel with
      the overall failure, the `Completion` marker crashed, and a credential-free crash
      reason, and the original failure propagates unchanged after the emission
    - The changed-set facts carry files only — the per-file change list is projected from
      the entry diff with the directory nodes dropped; a record with the new or error
      verdict carries the empty change list
    - The moments wrap the check without participating in it — output, exit codes, and the
      read-only nature are unchanged under any subscription state
    - Every error fact and diagnostic is credential-free — the same formulation the
      operation logs

    Constraints:
    - Read-only: never modify .goga/usages/, cooks/, or root *.md
    - git source only (no local-path mode)
    - Do not print the report — report rendering belongs to the command;
      the amendment summary lines of the `ConfigOverlay` print to stderr
      per the `click` practice
    - Log failures without exposing credentials embedded in git URLs
    - Do not let the moments alter the check — no amendment, no veto, no deferral; the
      zone is notification-only
```

Other members (`compute_dep_status`, `hash_tree`, the report fact types) and the Footer are
unchanged. .usages files: none.

### 5. Cell `goga/commands/usages` — modify (documentation wiring)

CODEMANIFEST diff.

**Header — the first import block from `goga/usages` gains the practice:**

```yaml
  - Types:
      - sync AS sync_logic
    Usages:
      - sync-usages
      - registering-hooks
    From: goga/usages
```

**Header — append to `Annotations:` (existing text unchanged):**

```yaml
  Use the `registering-hooks` practice for the run-level moments the
  operations behind this command group emit and the tool-package
  hooks subscribed to them.
```

Body and Footer unchanged — the wrappers do not deliver moments; rendered output and exit
codes are an unchanged contract. .usages files: none.

### 6. Docs surface (not cells; lands with the records)

- `docs/features/usages/hooks.md` — rewrite: drop the "no hook actions" statement; document
  the four actions, their contexts' facts, firing moments, terminal marker semantics, and
  the soft class; mirror the domain-level `registering-hooks` practice.
- `docs/features/hooks/hooks.md` — extend the per-domain action enumeration in the
  `domain` + `action` bullet with the four `usages` addresses (soft) and a pointer to the
  usages hooks page.

## Dependency Map

```
goga/hooks ──(Types: HookRegistry, emit_hook_event, declared_actions;
              Usages: declaring-actions, registering-hooks)──► goga/usages/hooks

goga/usages/hooks ──(Types: UsagesHooks, UsagesMoment, SyncDepOutcome,
                     SyncOutcome, Completion; Usages: checkpoints AS
                     usages-moments)──► goga/usages/sync

goga/usages/hooks ──(Types: UsagesHooks, UsagesMoment, DepDrift,
                     DriftVerdict, FileChange, ChangeVerdict, Completion;
                     Usages: checkpoints AS usages-moments)──► goga/usages/status

goga/usages/sync ──(existing: clone_repository, deploy_usages)──► goga/usages/status

goga/usages ──(Usages: registering-hooks)──► goga/commands/usages   [practice only]

goga/usages (facade CODEMANIFEST) — unchanged; carries only the new
goga/usages/.usages/registering-hooks.md documentation artifact.
```

No cycles: the zone imports only `goga/hooks`; it deliberately defines its own verdict
value sets instead of importing `UsageState`/`EntryChange` from `goga/usages/status`
(which would create a prohibited cross-import with the zone's consumers).

## Verification Checklist

After implementing each artifact:

1. **`goga/hooks/catalog`** — `goga lint` clean; `declared_actions()` returns the four new
   records (domain `usages`, soft) ordered by domain then name; every pre-existing record
   byte-identical in meaning; `goga hooks` tree shows the usages domain with four actions.
2. **`goga/usages/hooks`** — `goga lint` clean; facade import check
   `python -c "from goga.usages.hooks import UsagesHooks"`; construction performs no
   enumeration and no imports; ruff clean on the new package.
3. **`goga/usages/sync`** — `goga lint` clean; started moment fires after config
   resolution; completion fires on nothing-to-do, finished, and crash paths (crash carries
   partial outcomes, overall failure, crashed marker, credential-free reason, then
   re-raises); zero-subscriber run byte-identical to prior behavior (output + exit code);
   registry assembled once per run; `ruff check goga/usages/sync/`.
4. **`goga/usages/status`** — `goga lint` clean; changed-set records carry files only
   (directory nodes dropped); new/error records carry empty change lists; overall outcome
   ⇔ empty changed set; crash path as above; read-only nature intact; zero-subscriber
   byte-identity; `ruff check goga/usages/status/`.
5. **`goga/commands/usages`** — `goga lint` clean; `registering-hooks` import resolves;
   no behavioral change to either command.
6. **Docs** — `docs/features/usages/hooks.md` contains no "no hook actions" statement and
   matches the catalog exactly; `docs/features/hooks/hooks.md` enumerates the four usages
   addresses; both land in the same change-set as the records.
7. **Test suite gates** — `pytest tests/ -x` green, covering: subscription and validation
   on the four addresses; started/completed fact delivery; completion on every return path
   including the crash path with the terminal marker; no-op runs; abort semantics at the
   configuration boundary; soft isolation of a failing hook; zero-subscriber neutrality;
   credential safety (token-bearing git URL never reaches a fact or diagnostic); registry
   economics.
