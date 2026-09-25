# Design Document: `add-hooks-to-usages`

<!-- Topic: open the usages domain to the hooks platform as four soft run-level moments -->

## Contract Changes

The architecture plan (`.goga/history/2026/add-hooks-to-usages/arch.md`) was materialized into
contract artifacts by the apply stage. This design specifies the implementation those contracts
require. All contract changes below are already on disk and lint-clean (`goga lint`: 82 cells,
0 errors); no CODEMANIFEST edits were needed by this design pass.

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST`: four requirement bullets appended to `declared_actions()`
  — the records `domain="usages"`, `name` ∈ {`sync_started`, `sync_completed`, `status_started`,
  `status_completed`}, `error_class="soft"`. No signature change.
- `goga/usages/hooks/CODEMANIFEST` (**new zone cell**): 13 types — 8 facts (`facts.py`),
  4 read-only contexts (`contexts.py`), the `UsagesHooks` checkpoint surface (`events.py`);
  imports types and practices from `goga/hooks` only.
- `goga/usages/sync/CODEMANIFEST`: new import block (5 types + `usages-moments` practice from
  `goga/usages/hooks`); the `sync` annotation gains the moments paragraphs, renumbered
  algorithm with outcome recording, new requirements and constraints. Signature unchanged.
- `goga/usages/status/CODEMANIFEST`: new import block (7 types + `usages-moments` practice);
  the `status` annotation gains the same wiring plus the `DepDrift` derivation steps.
  Signature unchanged.
- `goga/commands/usages/CODEMANIFEST`: `registering-hooks` practice added to the
  `goga/usages` import block; one annotation paragraph added. No signature change.

### New Entities

All in `goga/usages/hooks` (new Python package `goga.usages.hooks`):

- `UsagesMoment(operation, group, dep)` — identity envelope of every moment; `facts.py`.
- `SyncOutcome()` — enum: synced / skipped / failed; `facts.py`.
- `SyncDepOutcome(group, dep, outcome, message=None)` — one matched dep's sync outcome; `facts.py`.
- `DriftVerdict()` — enum: new / out of date / error; `facts.py`.
- `ChangeVerdict()` — enum: added / modified / removed; `facts.py`.
- `FileChange(path, change)` — one changed file within a dep; `facts.py`.
- `Completion()` — enum: finished / crashed; `facts.py`.
- `DepDrift(group, dep, verdict, changes, message=None)` — one changed-set record; `facts.py`.
- `SyncStarted(moment, force)` — read-only sync-start context; `contexts.py`.
- `StatusStarted(moment)` — read-only status-start context; `contexts.py`.
- `SyncCompleted(moment, deps, success, completion, reason=None)` — read-only sync-completion
  context; `contexts.py`.
- `StatusCompleted(moment, changed, success, completion, reason=None)` — read-only
  status-completion context; `contexts.py`.
- `UsagesHooks()` — the checkpoint surface with four emit methods; `events.py`.

### Changed Entities

- `declared_actions()` (`goga/hooks/catalog/catalog.py`) — the catalog constant grows by the
  four usages records; the routine's behavior is otherwise unchanged.
- `sync` (`goga/usages/sync/sync.py`) — composes `UsagesMoment`, emits start/completion on
  every return path, records one `SyncDepOutcome` per matched dep, wraps the work in a crash
  path.
- `status` (`goga/usages/status/status.py`) — composes `UsagesMoment`, emits start/completion
  on every return path, derives one `DepDrift` per non-up-to-date matched dep, wraps the work
  in a crash path.

### Deleted Entities

None.

### Usages and Annotations Changes

- `goga/usages/hooks` header imports the practices `declaring-actions` and `registering-hooks`
  from `goga/hooks`; its `Annotations:` block binds them to the zone's emission and
  registration contracts.
- `goga/usages/sync` and `goga/usages/status` import the practice `usages-moments` from
  `goga/usages/hooks` and reference it in the global `Annotations:` and the operation
  annotation.
- `goga/commands/usages` imports the practice `registering-hooks` from `goga/usages`
  (resolving to `goga/usages/.usages/registering-hooks.md`) and references it in the global
  `Annotations:`.
- New consumer practices on disk (created by the apply stage, verified consistent by this
  design): `goga/usages/hooks/.usages/usages-moments.md`,
  `goga/usages/.usages/registering-hooks.md`.
- Docs (already updated by the apply stage): `docs/features/usages/hooks.md` rewritten;
  `docs/features/hooks/hooks.md` extended with the four usages addresses.

## Applied Fixes

### Fixed CODEMANIFEST Defects

None. The four-dimension consistency audit (interface↔type, type↔mutation, interface↔interface,
annotations↔entity) over all five touched manifests found no defects:

- Every `Imports` target exists (types and practices resolve on disk; `goga lint` clean).
- No cross-imports: the zone imports only `goga/hooks`; `goga/hooks` does not import the zone.
- Every connected practice is referenced in at least one annotation of its manifest.
- Type flow across cells verified end-to-end: `UsagesMoment` → the four contexts →
  `UsagesHooks.emit_*` signatures → the `sync`/`status` algorithm steps → the catalog records
  (`domain="usages"`, four names, soft).
- Projection feasibility verified: `DepStatus.entries: list[EntryStatus]` carries everything
  `DepDrift.changes: list[FileChange]` needs (per-file verdicts exist as `EntryChange`
  added/modified/removed; directory nodes and unchanged files are droppable).

Two implementation-level details the contracts deliberately leave open are fixed by this
design (see Algorithm Design): the exact credential-free failure message of a failed
`SyncDepOutcome`, and the exact structure of the crash wrapper.

## Entity Interaction and Data Flow

### Interaction Diagram

```
 goga usages sync / goga usages status            (commands/usages — unchanged code)
        │  delegates; converts ValueError/ImportError → click.ClickException
        ▼
 sync.sync / status.status                        (usages/sync, usages/status)
        │ 1. load_project_config → ConfigHooks.amend_config ──► HookRegistry build #1
        │    (config zone's own registry; abort here fires NO usages moment)
        │ 2. UsagesMoment(operation="sync"|"status", group, dep)
        ▼
 UsagesHooks.emit_<op>_started                    (usages/hooks/events.py)
        │ _ensure_registry ──► HookRegistry build #2 (once per UsagesHooks instance)
        │ emit_hook_event(registry, "usages", "<op>_started", context_for)
        ├─────────────────────────────────────────────────────┐
        │ 3. the operation's own work                          ▼
        │    sync: clone/deploy per dep → SyncDepOutcome   emit_hook_event
        │    status: compute_dep_status → DepStatus            │ resolve record in
        │            → DepDrift projection                      │ declared_actions()
        │ 4. UsagesHooks.emit_<op>_completed                    ▼
        │    (finished — or crashed from the except arm)   for each subscription
        ▼                                                  in enumeration order:
 exit_code / UsageStatusReport                        wrap_context(view)
        │                                             build_hook_arguments
        ▼                                             hook(context=…, self=…)
 CLI rendering / exit code                        (soft: a failure warns and continues)
```

### Data Flows

**Flow A — sync run with subscriptions.**
`goga usages sync --force` → command reads group/dep from the click context →
`sync(force, group, dep)` → `_effective_config()` (load + config amendment + summary lines to
stderr) → `UsagesMoment("sync", group, dep)` → `UsagesHooks().emit_sync_started(moment, force)`
→ registry build → per-tool delivery of `SyncStarted` → `_sync_work` appends
`SyncDepOutcome` records (skipped / synced / failed) → `emit_sync_completed(moment, outcomes,
exit_code == 0, Completion.finished)` → per-tool delivery of `SyncCompleted` → exit code to
the command.

**Flow B — status run with subscriptions.** Same shape; `_status_work` collects
`DepStatus` records and derives `DepDrift` records; the completion carries
`StatusCompleted(changed, not changed, finished)`; the report returns to the command for
rendering.

**Flow C — crash.** Any `Exception` escaping the work helper after the start emission →
`emit_<op>_completed(…, False, Completion.crashed, reason=str(reason))` → re-raise → the
command wrapper converts as for any other failure (or the traceback escapes in programmatic
use — identical to today's behavior).

**Flow D — abort at the configuration boundary.** `load_project_config` or
`ConfigHooks.amend_config` raises before any usages emission → no moment fires → the command
wrapper converts to a clean `click.ClickException`.

**Flow E — inert environment.** No `goga_tool_*` packages installed → the registry build
enumerates nothing → every emission iterates zero subscriptions and returns → output, exit
codes, and the report are byte-identical to the pre-zone behavior.

### Entity Dependencies

Implementation order (leaves first):

1. `goga/hooks/catalog/catalog.py` — append the four records (no new imports).
2. `goga/usages/hooks/facts.py` — stdlib-only leaf (dataclasses + enum).
3. `goga/usages/hooks/contexts.py` — imports `.facts`.
4. `goga/usages/hooks/events.py` — imports `...hooks` (platform facade), `.contexts`, `.facts`.
5. `goga/usages/hooks/__init__.py` — the zone facade over the three modules.
6. `goga/usages/sync/sync.py` — imports `..hooks` (five names).
7. `goga/usages/status/status.py` — imports `..hooks` (seven names) + the private
   `_derive_drift` projection.
8. Tests (see Test Stack Trace).

Unchanged by design: `goga/usages/__init__.py` (facade), `goga/commands/usages/usages.py`,
`clean.py` / `clone.py` / `deploy.py`, `compare.py` / `models.py`, all docs.

## Code Stack Trace

### Trace: `UsagesHooks.emit_sync_started` (representative for all four emit methods)

#### Chain
1. **Input**: `moment: UsagesMoment` (operation="sync", the applied `group`/`dep` filters),
   `force: bool` — both passed by `sync` from its own inputs.
2. `self._ensure_registry()` → first call: `HookRegistry()` + `build_once()` — enumerates
   `goga_tool_*` packages once, runs their `register_hooks` callbacks; later calls return the
   cached registry → checkpoint: one build per `UsagesHooks` instance; the operations create
   one instance per run → the enumeration never multiplies with the number of moments.
   Verified against `goga/hooks/registry/state.py:54` (idempotent `build_once`).
3. Resolve `domain="usages"`, `action="sync_started"` against `declared_actions()` — realized
   inside `emit_hook_event` (`goga/hooks/dispatch/emit.py:70-77`): an unknown address is a clean
   `ValueError` of the emitting side → checkpoint: the catalog record must exist — the
   catalog gap is closed by this design's first implementation step.
4. Build `SyncStarted(moment=moment, force=force)` — frozen facts, built only from the
   caller's values → checkpoint: no config/git/file reads here (zone requirement).
5. `emit_hook_event(registry, "usages", "sync_started", context_for=lambda _tool: context)`:
   iterates `registry.subscriptions_for("usages", "sync_started")` in enumeration order; one
   `wrap_context` proxy per subscription over the shared context instance; attribute writes on
   the proxy raise (`delivery.py:60`); `build_hook_arguments` injects only the declared
   `context`/`self` names (`delivery.py:94`); a raising hook → record `error_class == "soft"`
   → `logger.warning` naming hook, tool, address, reason → the sequence continues.
6. **Output**: `None` — fire-and-forget; nothing is collected.

#### Checkpoint Summary
- Registry-per-run: passed (`build_once` idempotence verified in source).
- Address resolvability: passed once the four catalog records land (implementation step 1).
- Read-only delivery: passed (`wrap_context` closes writes; the models are frozen anyway).
- Soft failure semantics: passed (the record's `error_class` drives `emit.py`'s branch).

### Trace: `sync(force, group, dep)`

#### Chain
1. **Input**: `force=False, group=None, dep=None` (the command reads them from the click
   group context).
2. `_effective_config()` — `load_project_config()` → authored `ProjectConfig`;
   `ConfigHooks().amend_config(config=config)` → `ConfigOverlay`; summary lines to stderr;
   returns `overlay.config` → checkpoint: a `ValueError` (hard config action) or `ImportError`
   (broken tool facade) propagates before any usages emission — "no usages moment fires on
   this abort" holds structurally because the moment composition comes after this call.
3. `moment = UsagesMoment(operation="sync", group=group, dep=dep)`; `hooks = UsagesHooks()`;
   `hooks.emit_sync_started(moment, force)` → checkpoint: start fires "once the effective
   configuration is resolved" — after the amendment, before the `None` check.
4. `outcomes: list[SyncDepOutcome] = []`; `try: exit_code = _sync_work(config, force, group,
   dep, outcomes)`:
   - `config.usages is None` → `return 0` from the helper → checkpoint: the no-op run still
     emitted the start moment and will emit the completion moment with the empty outcome set.
   - `usages_root = Path(".goga/usages")`; `if force: clean_usages_dir(usages_root)`.
   - Loop over `config.usages.items()` in insertion order with the `group`/`dep` filters:
     a non-matching name `continue`s (no outcome record — "a filtered-out dep is absent from
     the outcomes") → checkpoint: matches the existing loop structure verbatim.
   - `(not force) and target.exists()` → append `SyncDepOutcome(group, dep, skipped)`.
   - else `clone_repository(depcfg.git, depcfg.ref)` + `deploy_usages(repo, target,
     depcfg.root)` under the existing try/except/finally (repo cleanup in `finally`):
     - `except Exception` → `logger.error("usages sync failed for %s/%s", …)` (unchanged,
       credential-free), append `SyncDepOutcome(group, dep, failed,
       message=f"failed to sync usages for {group_name}/{dep_name}")`, `exit_code = 1`,
       `continue` → checkpoint: the message carries no exception text — a
       `CalledProcessError` embeds the git URL, possibly with credentials; the formulation
       mirrors `DepStatus.error` in `status.py:145`.
     - no exception → append `SyncDepOutcome(group, dep, synced)`.
   - `return exit_code`.
5. After the helper: `hooks.emit_sync_completed(moment, outcomes, exit_code == 0,
   Completion.finished)`; `return exit_code`.
6. `except Exception as reason:` (around the helper call only) →
   `hooks.emit_sync_completed(moment, outcomes, False, Completion.crashed,
   reason=str(reason))`; `raise` → checkpoint: the partial outcomes list survives because the
   helper mutates the caller-owned accumulator; the original exception propagates unchanged.

#### Checkpoint Summary
- Type flow `UsagesMoment`→`SyncStarted`/`SyncCompleted`: passed.
- "Completion fires on every return path after the start": passed — three returns (no-op,
  finished, crash) each reach exactly one completion emission; the two finished returns
  cannot double-emit (single emission site after the helper).
- Exit-code semantics unchanged: passed (`exit_code` accumulation untouched).
- Credential-free failure facts: passed (log formulation unchanged; the new message adds no
  exception text; crash reason is `str(reason)` of a non-per-dep exception — per-dep git
  failures never reach the crash arm, they are absorbed best-effort at step 4).

### Trace: `status(group, dep)`

#### Chain
1. **Input**: `group=None, dep=None` (from the click group context).
2. `_effective_config()` — extracted to mirror `sync.py` (same five-line body: load, deliver
   `amend_config`, print summary lines to stderr, return the effective config) → same abort
   semantics as sync: no moment on this boundary.
3. `moment = UsagesMoment(operation="status", group=group, dep=dep)`;
   `hooks.emit_status_started(moment)` — nothing is collected.
4. `changed: list[DepDrift] = []`; `try: report = _status_work(config, group, dep, changed)`:
   - `not config.usages` (None or `{}`) → `return UsageStatusReport(deps=[])` → checkpoint:
     the empty-section case returns through the same single finished-emission site.
   - `logger.info("usages status started", …)` (unchanged placement: after the empty check).
   - Loop over declared deps with the filters (unchanged structure):
     `dep_status = _check_dep(group_name, dep_name, depcfg)` (unchanged helper) →
     `collected.append(dep_status)` → `drift = _derive_drift(dep_status)` →
     `if drift is not None: changed.append(drift)`.
   - `logger.info("usages status completed", …)` (unchanged).
   - `return UsageStatusReport(deps=collected)`.
5. After the helper: `hooks.emit_status_completed(moment, changed, not changed,
   Completion.finished)`; `return report` → checkpoint: `success` ⇔ the changed set is empty
   ⇔ every matched dep is up to date ⇔ `report.exit_code == 0` (verified against
   `UsageStatusReport.exit_code` in `models.py:124` — the three formulations coincide).
6. `except Exception as reason:` → `emit_status_completed(moment, changed, False,
   Completion.crashed, reason=str(reason))`; `raise`.

**`_derive_drift(dep_status) -> DepDrift | None`** (new private helper, `status.py`):
- `state is up_to_date` → `None` — no record ("the changed set contains no up-to-date dep").
- `state is new` → `DepDrift(group, dep, DriftVerdict.new, changes=[])`.
- `state is error` → `DepDrift(group, dep, DriftVerdict.error, changes=[],
  message=dep_status.error)` — reuses the exact credential-free `DepStatus.error`
  (`"failed to check usages status for {group}/{dep}"`).
- `state is out of date` → `DepDrift(group, dep, DriftVerdict.out_of_date, changes=[
  FileChange(path=e.path, change=_FILE_CHANGE[e.change]) for e in dep_status.entries
  if e.kind is EntryKind.file and e.change in _FILE_CHANGE])` with the module constant
  `_FILE_CHANGE = {EntryChange.added: ChangeVerdict.added, EntryChange.modified:
  ChangeVerdict.modified, EntryChange.removed: ChangeVerdict.removed}` → checkpoint:
  directory nodes dropped (`kind is dir` filtered), unchanged files dropped (not a key of
  `_FILE_CHANGE`), path-sorted order preserved (filtering a sorted list keeps it sorted —
  `_diff_entries` sorts at `compare.py:166`), and an out-of-date dep always yields ≥ 1 file
  change (differing hash maps imply at least one non-unchanged file) — "populated for the
  out-of-date verdict" holds.

#### Checkpoint Summary
- Type flow `DepStatus`/`EntryStatus` → `DepDrift`/`FileChange`: passed (projection verified
  member-by-member).
- Report/moment agreement: passed (`success` ≡ `exit_code == 0` ≡ empty changed set).
- Read-only nature: passed (no new writes anywhere in the flow).

### Trace: `declared_actions()`

#### Chain
1. **Input**: none.
2. `_DECLARED_ACTIONS` gains four records appended after the schema record:
   `("usages", "sync_started", "soft")`, `("usages", "sync_completed", "soft")`,
   `("usages", "status_started", "soft")`, `("usages", "status_completed", "soft")`.
3. `sorted(key=(domain, name))` → the usages block lands last (build < config < onboarding <
   pipeline < schema < statuses < topics < usages) → checkpoint: deterministic and complete.
4. **Output**: 24 records (was 20), a fresh list per call.

#### Checkpoint Summary
- Additive growth, no rewrite of published records: passed.
- Downstream consumers (`goga/hooks` facade re-export, `goga/commands/hooks` tree,
  registration-envelope validation): unaffected — they read the catalog dynamically.

### Trace: the `goga usages sync` / `goga usages status` commands

#### Chain
1. **Input**: CLI flags (`--force`, `--info`, group-level `--group`/`--dep`).
2. The wrappers call `sync_logic` / `status_logic` inside
   `except (FileNotFoundError, KeyError, ValueError, ImportError, yaml.YAMLError)` →
   `click.ClickException` → checkpoint: the new failure surface (registry `ImportError` at the
   first usages emission — a broken tool package facade) is already covered by the existing
   `ImportError` arm; no command change needed.
3. Rendering and `ctx.exit` unchanged → **Output**: identical CLI behavior under any
   subscription state.

#### Checkpoint Summary
- No-change conclusion: passed for both commands (`usages.py:88-95`, `usages.py:114-124`).

## Algorithm Design

### `goga/hooks/catalog` — `declared_actions`

**Responsibility**: the single source of known subscription addresses; grows additively.

**Algorithm:**
```
1. Append to _DECLARED_ACTIONS (after the schema record):
   Action(domain="usages", name="sync_started",   error_class="soft")
   Action(domain="usages", name="sync_completed", error_class="soft")
   Action(domain="usages", name="status_started",   error_class="soft")
   Action(domain="usages", name="status_completed", error_class="soft")
   → the sort in declared_actions() places the block last; no other edit
```

**Errors:** none (maintained data).

**Edge Cases:** none — the pair set stays unique; the count becomes 24.

### `goga/usages/hooks/facts.py` — the eight fact entities

**Responsibility**: the zone's fact vocabulary — pure data, no behavior, no I/O.

**Algorithm (construction rules):**
```
UsagesMoment            frozen kw_only dataclass: operation: str, group: str|None, dep: str|None
SyncOutcome             enum.Enum: synced="synced", skipped="skipped", failed="failed"
SyncDepOutcome          frozen kw_only dataclass: group: str, dep: str,
                         outcome: SyncOutcome, message: str|None = None
DriftVerdict            enum.Enum: new="new", out_of_date="out of date", error="error"
ChangeVerdict           enum.Enum: added="added", modified="modified", removed="removed"
FileChange              frozen kw_only dataclass: path: str, change: ChangeVerdict
Completion              enum.Enum: finished="finished", crashed="crashed"
DepDrift                frozen kw_only dataclass: group: str, dep: str,
                         verdict: DriftVerdict, changes: list[FileChange],
                         message: str|None = None
```

- Member values are the display strings the CODEMANIFEST properties declare
  (`out_of_date = "out of date"` mirrors `UsageState.out_of_date = "out of date"`).
- `message` defaults to `None` — the explicit absence of a failure fact.
- Module docstring documents the file as the facts cell of the zone (the established
  per-module header pattern).

**Errors:** none — data only.

**Edge Cases:** a `list` field on a frozen dataclass is shallow-immutable only — accepted
(the `DepStatus.entries` precedent); the delivered views are write-protected by the platform
proxy anyway.

### `goga/usages/hooks/contexts.py` — the four context entities

**Responsibility**: the read-only views a subscribed hook receives; facts only, no methods.

**Algorithm (construction rules):**
```
SyncStarted(moment: UsagesMoment, force: bool)
StatusStarted(moment: UsagesMoment)
SyncCompleted(moment: UsagesMoment, deps: list[SyncDepOutcome], success: bool,
              completion: Completion, reason: str|None = None)
StatusCompleted(moment: UsagesMoment, changed: list[DepDrift], success: bool,
                completion: Completion, reason: str|None = None)
```
All four frozen kw_only dataclasses; `reason` defaults to `None`.

**Errors:** none.

**Edge Cases:** none — the invariants (`success is False whenever crashed`, `reason` present
exactly when crashed) are guaranteed by the emitting operations, not enforced here (facts, not
police — the zone contract's "pure facts" rule).

### `goga/usages/hooks/events.py` — `UsagesHooks`

**Responsibility**: the checkpoint surface — the four moment emissions over the platform
facade.

**Algorithm:**
```
class UsagesHooks:
  __init__:
    self._registry = None                       # cheap: no enumeration, no imports
  _ensure_registry() -> HookRegistry:
    IF self._registry is None:
      registry = HookRegistry(); registry.build_once(); self._registry = registry
    RETURN self._registry                       # one build per instance (per run)
  emit_sync_started(moment, force):
    context = SyncStarted(moment=moment, force=force)
    emit_hook_event(self._ensure_registry(), "usages", "sync_started",
                    context_for=lambda _tool: context)
  emit_sync_completed(moment, deps, success, completion, reason=None):
    context = SyncCompleted(moment=moment, deps=deps, success=success,
                            completion=completion, reason=reason)
    emit_hook_event(self._ensure_registry(), "usages", "sync_completed",
                    context_for=lambda _tool: context)
  emit_status_started(moment):
    context = StatusStarted(moment=moment)
    emit_hook_event(self._ensure_registry(), "usages", "status_started",
                    context_for=lambda _tool: context)
  emit_status_completed(moment, changed, success, completion, reason=None):
    context = StatusCompleted(moment=moment, changed=changed, success=success,
                              completion=completion, reason=reason)
    emit_hook_event(self._ensure_registry(), "usages", "status_completed",
                    context_for=lambda _tool: context)
```

- Imports: `from ...hooks import HookRegistry, emit_hook_event` (the platform facade —
  three dots: `goga.usages.hooks` → `goga` → `goga.hooks`). `declared_actions` is not
  imported in Python: the catalog resolution named by the contract's algorithm step happens
  inside `emit_hook_event` (the `declaring-actions` practice's "declare and emit" split); an
  unused import would fail ruff.
- `context_for=lambda _tool: context` — the same instance is shared by every receiving tool:
  the facts are frozen and the delivery proxy closes writes, so sharing is safe and matches
  the pipeline-zone precedent.

**Errors:**
- `ImportError` (broken tool package facade) at the first emission → propagates to the
  operation → the command wrapper converts it to a clean `click.ClickException`; no usages
  moment has fired (the start was never delivered).
- `ValueError` (unknown address) — unreachable by contract once the four records land; it
  names the address and stays a clean emitting-side error if it ever fires.

**Edge Cases:**
- Zero subscriptions (or zero tool packages) → the loop body never runs → the method returns
  `None`; the surface is inert.
- A raising hook → the soft class warns inside `emit_hook_event` and continues — never
  surfaces to the operation.

### `goga/usages/hooks/__init__.py` — the zone facade

**Responsibility**: the consumer entry point of the zone.

**Algorithm:**
```
from .contexts import StatusCompleted, StatusStarted, SyncCompleted, SyncStarted
from .events import UsagesHooks
from .facts import (ChangeVerdict, Completion, DepDrift, DriftVerdict, FileChange,
                    SyncDepOutcome, SyncOutcome, UsagesMoment)

__all__ = [  # exactly the thirteen contract names, alphabetical
  "ChangeVerdict", "Completion", "DepDrift", "DriftVerdict", "FileChange",
  "StatusCompleted", "StatusStarted", "SyncCompleted", "SyncDepOutcome",
  "SyncOutcome", "SyncStarted", "UsagesHooks", "UsagesMoment",
]
```

**Edge Cases:** none — a pure re-export; importing the package enumerates nothing.

### `goga/usages/sync/sync.py` — the changed `sync`

**Responsibility**: config-driven synchronization; now also the owner of its run-level
moments.

**Algorithm:**
```
sync(force=False, group=None, dep=None) -> int:
  1. config = _effective_config()               # unchanged: load + amend_config + stderr lines
                                                # abort here → no usages moment
  2. moment = UsagesMoment(operation="sync", group=group, dep=dep)
     hooks = UsagesHooks()
     hooks.emit_sync_started(moment, force)     # started context carries force; collects nothing
  3. outcomes = []
     TRY:
       exit_code = _sync_work(config, force, group, dep, outcomes)
     EXCEPT Exception as reason:
       hooks.emit_sync_completed(moment, outcomes, False, Completion.crashed,
                                 reason=str(reason))
       RAISE                                    # the operation's own failure is never masked
  4. hooks.emit_sync_completed(moment, outcomes, exit_code == 0, Completion.finished)
  5. RETURN exit_code

_sync_work(config, force, group, dep, outcomes) -> int:   # private; mutates `outcomes`
  1. IF config.usages is None: RETURN 0                  # nothing to sync
  2. usages_root = Path(".goga/usages")
  3. IF force: clean_usages_dir(usages_root)
  4. exit_code = 0
     FOR group_name, deps IN config.usages.items():               # insertion order
       IF group is not None AND group_name != group: CONTINUE
       FOR dep_name, depcfg IN deps.items():
         IF dep is not None AND dep_name != dep: CONTINUE
         target = usages_root / group_name / dep_name
         IF (not force) AND target.exists():
           outcomes.append(SyncDepOutcome(group=group_name, dep=dep_name,
                                          outcome=SyncOutcome.skipped))
           CONTINUE
         repo = None
         TRY:
           repo = clone_repository(depcfg.git, depcfg.ref)
           deploy_usages(repo, target, depcfg.root)
         EXCEPT Exception:
           logger.error("usages sync failed for %s/%s", group_name, dep_name,
                        extra={"group": group_name, "dep": dep_name})
           outcomes.append(SyncDepOutcome(group=group_name, dep=dep_name,
                                          outcome=SyncOutcome.failed,
                                          message=f"failed to sync usages for {group_name}/{dep_name}"))
           exit_code = 1
           CONTINUE
         FINALLY:
           IF repo is not None: shutil.rmtree(repo, ignore_errors=True)
         outcomes.append(SyncDepOutcome(group=group_name, dep=dep_name,
                                        outcome=SyncOutcome.synced))
  5. RETURN exit_code
```

- Imports added to `sync.py`: `from ..hooks import Completion, SyncDepOutcome, SyncOutcome,
  UsagesHooks, UsagesMoment` (two dots: `goga.usages.sync` → `goga.usages` → `.hooks`).
- **Fixed decision — the failure message**: `f"failed to sync usages for {group}/{dep}"`.
  Rationale: the exact sentence shape of the operation's sibling
  (`DepStatus.error = f"failed to check usages status for {group}/{dep}"`), credential-free by
  construction (group/dep names only, no exception text, no URL), and it satisfies the
  annotation's "the same credential-free formulation the operation logs" reading.
- The helper split (`_sync_work`) is also the complexity-budget move: `sync` gains the
  emission scaffold, and the orchestrator stays within the lint budget the way
  `_effective_config` already documents.
- The docstring of `sync` gains the moment paragraphs (start after the effective
  configuration; completion on every return path; notification-only). `_sync_work` gets its
  own docstring noting the `outcomes` accumulator contract (partial facts survive a crash).

**Errors:**
- Config boundary (`FileNotFoundError`, `KeyError`, `ValueError`, `ImportError`,
  `yaml.YAMLError`) → unchanged propagation; no moment fired.
- Registry build `ImportError` at the start emission → propagates; no moment fired (the start
  was never delivered).
- Per-dep failure → best-effort isolation unchanged + a `failed` outcome record.
- Crash (`Exception` anywhere in `_sync_work` after the start) → crashed completion with the
  partial outcomes, then the original exception re-raised unchanged.
- `BaseException` (`KeyboardInterrupt`) → not caught (the platform's own catch-`Exception`
  policy, `emit.py`); no completion emission — matches the approved
  `usages-moments.md` sketch.

**Edge Cases:**
- `usages: {}` (present but empty) → the helper's loop runs zero iterations; with `force` the
  clean still runs (unchanged legacy semantics — only `None` short-circuits before the clean);
  both moments fire with the empty outcome set and `success=True`.
- Filters matching no dep → same empty-outcome outcome set.
- An existing target under `force=False` → a `skipped` record (previously silent — the sync
  output is unchanged; the fact is new only in the moment).

### `goga/usages/status/status.py` — the changed `status`

**Responsibility**: config-driven drift check; now also the owner of its run-level moments.

**Algorithm:**
```
status(group=None, dep=None) -> UsageStatusReport:
  1. config = _effective_config()               # NEW private helper — the exact body sync.py
                                                # already has (load + amend_config + stderr
                                                # lines); abort here → no usages moment
  2. moment = UsagesMoment(operation="status", group=group, dep=dep)
     hooks = UsagesHooks()
     hooks.emit_status_started(moment)          # nothing is collected
  3. changed = []
     TRY:
       report = _status_work(config, group, dep, changed)
     EXCEPT Exception as reason:
       hooks.emit_status_completed(moment, changed, False, Completion.crashed,
                                   reason=str(reason))
       RAISE
  4. hooks.emit_status_completed(moment, changed, not changed, Completion.finished)
  5. RETURN report

_status_work(config, group, dep, changed) -> UsageStatusReport:  # private; mutates `changed`
  1. IF not config.usages: RETURN UsageStatusReport(deps=[])     # None or {}
  2. logger.info("usages status started", extra={"group": group, "dep": dep})
  3. collected = []
     FOR group_name, deps IN config.usages.items():
       IF group is not None AND group_name != group: CONTINUE
       FOR dep_name, depcfg IN deps.items():
         IF dep is not None AND dep_name != dep: CONTINUE
         dep_status = _check_dep(group_name, dep_name, depcfg)   # unchanged helper
         collected.append(dep_status)
         drift = _derive_drift(dep_status)
         IF drift is not None: changed.append(drift)
  4. logger.info("usages status completed", extra={"deps": len(collected)})
  5. RETURN UsageStatusReport(deps=collected)

_derive_drift(dep_status) -> DepDrift | None:                    # NEW private projection
  IF dep_status.state is UsageState.up_to_date: RETURN None
  IF dep_status.state is UsageState.new:
    RETURN DepDrift(group=…, dep=…, verdict=DriftVerdict.new, changes=[])
  IF dep_status.state is UsageState.error:
    RETURN DepDrift(group=…, dep=…, verdict=DriftVerdict.error, changes=[],
                    message=dep_status.error)
  # out of date — project the per-file changes from the entry diff
  RETURN DepDrift(group=…, dep=…, verdict=DriftVerdict.out_of_date,
                  changes=[FileChange(path=e.path, change=_FILE_CHANGE[e.change])
                           for e IN dep_status.entries
                           IF e.kind is EntryKind.file AND e.change IN _FILE_CHANGE])

_FILE_CHANGE = {EntryChange.added: ChangeVerdict.added,
                EntryChange.modified: ChangeVerdict.modified,
                EntryChange.removed: ChangeVerdict.removed}      # module constant
```

- Imports added to `status.py`: `from ..hooks import (ChangeVerdict, Completion, DepDrift,
  DriftVerdict, FileChange, UsagesHooks, UsagesMoment)`; `EntryKind` is already present in
  the existing `models` import (re-exported today — the projection filter uses it as-is).
- The INFO lifecycle logs keep their exact current placement and payloads (moved verbatim
  into the helper).
- The in-document models (`DepStatus` et al.) stay defined in `models.py` and re-exported —
  untouched.

**Errors:** identical taxonomy to `sync` (config boundary; registry `ImportError`; per-dep
failures absorbed by `_check_dep` into `error` states; crash → crashed completion +
re-raise).

**Edge Cases:**
- `usages: {}` and `usages:` absent → both produce the empty report; both fire the two
  moments with the empty changed set (the contract's step 3 wording "None or empty").
- A dep with entries but no non-unchanged file cannot be out of date (hash maps would be
  equal) — the populated-changes invariant holds by construction.
- Mixed verdicts inside one dep → directory aggregation is irrelevant to the projection
  (directories are dropped); file verdicts pass through verbatim.

## Cross-cutting Concerns

- **Error handling**: the four actions are soft — the platform warns (hook, tool, address,
  reason) and continues; the operations' own error handling is untouched (best-effort per-dep
  isolation, fail-loud config boundary, crash re-raise after the crashed emission). The
  command wrappers already convert `ValueError`/`ImportError` to `click.ClickException`.
- **Logging**: unchanged operation logs (`ERROR` per failed dep — credential-free; `INFO`
  status lifecycle); the platform's `WARNING` for failing/registration-rejected hooks;
  nothing new prints — the zone never prints (stderr summary lines remain the config
  checkpoint's own channel).
- **Validation**: registration envelopes are validated by the platform against the catalog
  (wrong address → warning + skip); emissions resolve their address against
  `declared_actions` (defensive `ValueError` — unreachable once the records land). The zone
  itself validates nothing — facts only.
- **Caching**: one `HookRegistry` per `UsagesHooks` instance, built lazily on the first
  emission (`build_once` idempotent); nothing cached across runs. Note the established
  platform shape: a command run that delivers the config amendment and the usages moments
  builds two registries (one per zone surface) — the per-zone-surface registry is the
  platform's documented unit (each zone's "one registry per run" claim scopes to its own
  surface).
- **Concurrency**: single-threaded CLI flows; all delivered facts are frozen dataclasses;
  no shared mutable state beyond the per-run registry (whose own threading posture is the
  platform's, unchanged).

## Usages Analysis

### `convention`
- **What it provides**: mandatory Python rules — relative imports, kw_only dataclasses,
  logging style/format, docstring standard, test structure/mocking policy, validation
  commands.
- **Where used**: every touched manifest's global annotations; every new/changed module.
- **Why chosen**: the project-wide baseline.
- **How exactly**: relative imports in all three zone modules and both operations; frozen
  kw_only dataclasses for the twelve models; `logging` module loggers with `extra`
  metadata; Google-style docstrings; tests mirroring the source tree with mocks only at the
  external boundaries.

### `git` (sync, inline)
- **What it provides**: subprocess invocation contract for git (`check=True`,
  `capture_output=True`, `GIT_TERMINAL_PROMPT=0`); mock subprocess in tests.
- **Where used**: `clone_repository` (unchanged); the moments add no git access.
- **Why chosen / how**: unchanged — the zone reads no git (a headline contract property).

### `click` (sync, status, commands — cook file)
- **What it provides**: CLI construction rules and the stderr/stdout channel discipline.
- **Where used**: the amendment summary lines (`click.echo(err=True)`) — unchanged; the
  command wrappers — unchanged.
- **How exactly**: nothing new; the moments add no output channel.

### Imported Usages

- `checkpoints` from `goga/config/hooks` (sync, status) — Path
  `goga/config/hooks/.usages/checkpoints.md`. The config-amendment delivery at the load
  moment: `ConfigHooks().amend_config(config=…)`, print `overlay.summary_lines` to stderr,
  consume `overlay.config`. Traced dependency — both operations' step 1.
- `usages-moments` from `goga/usages/hooks` (sync, status) — Path
  `goga/usages/hooks/.usages/usages-moments.md`. The moment-delivery practice the operations
  follow: one `UsagesHooks` per run, resolve facts before delivery, emit around the
  operation, complete the crash path (`except Exception` → crashed emission → re-raise),
  no-op and abort semantics. The implemented structure (`_sync_work`/`_status_work` sketches)
  mirrors the practice's `run_sync_work` sketch verbatim in shape.
- `declaring-actions` from `goga/hooks` (zone) — Path `goga/hooks/.usages/declaring-actions.md`.
  The emission contract: declare the action in the catalog, own the context, emit via
  `emit_hook_event(HookRegistry(), domain, action, context_for=…)`; the platform carries
  enumeration, delivery, error classes, diagnostics.
- `registering-hooks` from `goga/hooks` (zone) — Path `goga/hooks/.usages/registering-hooks.md`.
  The registration contract behind every moment: `register_hooks(hooks)` →
  `hooks.subscribe(domain, action, name, hook)`; the fixed offered parameter names
  (`context`, `self`); the failure ladder (soft skip / hard stop; broken import the only
  fatal case).
- `registering-hooks` from `goga/usages` (commands) — Path
  `goga/usages/.usages/registering-hooks.md`. The consumer-facing practice for the four
  usages addresses (events table, views, integration scenarios) — documentation for the
  command group's annotation; no code obligation.
- `sync-usages`, `usages-status` from `goga/usages` (commands) — unchanged references.

## `.usages/` Update

### Cell: `goga/usages/hooks`

#### New Files
- **hooks zone practices** → `goga/usages/hooks/.usages/usages-moments.md` (created by the
  apply stage).
  - Status: **current** — verified against this design: the surface sketch
    (`UsagesHooks()`), the resolve-before-delivery fact list, the emit-around-the-operation
    shape, the crash-path sketch (`except Exception` → crashed emission → `raise`), and the
    no-op/abort semantics all match the contract and this design's algorithms.
  - Additions needed: none.

### Cell: `goga/usages`

#### New Files
- **tool-author practices** → `goga/usages/.usages/registering-hooks.md` (created by the
  apply stage).
  - Status: **current** — the events table matches the four catalog records; the views match
    the context fields (including `reason`-when-crashed and the files-only change lists);
    the subscribe sketch matches the registrar API.
  - Additions needed: none.

#### Existing Files — Consistency
- **`sync-usages`** → `goga/usages/.usages/sync-usages.md` — Status: current. The moments do
  not change the documented contract (config shape, on-disk result, modes, filters, exit
  codes); the hooks surface is a separate functional domain with its own file. No updates.
- **`usages-status`** → `goga/usages/.usages/usages-status.md` — Status: current, same
  reasoning (status determination, result shape, exit codes unchanged). No updates.

### Cell: `goga/hooks`

`declaring-actions.md`, `registering-hooks.md`, `per-tool-delivery.md` — generic platform
practices; the usages additions do not alter them. No updates.

## Test Stack Trace

### General Setup

- Platform boundary fixtures (existing, reused): `tests/hooks/conftest.py` provides
  `pin_package_environment` (pins `packages_distributions` — the single enumeration mock
  point) and `install_tool_package` (installs a fake `goga_tool_*` into `sys.modules` with a
  `register_hooks` callback). `tests/usages/conftest.py` already re-exports both; the new
  `tests/usages/hooks/conftest.py` re-exports them again (the `tests/pipeline/hooks`
  precedent).
- Config fixtures (existing, reused): `_write_config`-style helpers writing a
  `.goga/config.yml` under `tmp_path` + `monkeypatch.chdir(tmp_path)`.
- Mocking per `convention`: mock at the import point — `_sync_mod =
  importlib.import_module("goga.usages.sync.sync")` then `mock.patch.object(_sync_mod,
  "clone_repository")` (the established pattern; the facade function shadows the submodule
  attribute); `_status_mod = importlib.import_module("goga.usages.status.status")` then
  `mock.patch.object(_status_mod, "compute_dep_status")`. Crash injection:
  `_sync_mod.clean_usages_dir` for sync (called outside the absorbing per-dep try);
  `_status_mod._check_dep` (or `_derive_drift`) for status — a raise of
  `compute_dep_status` is absorbed by `_check_dep`'s `except Exception` into an error
  dep, so it can never produce a crash.
- Capture channel for delivered moments: a fake tool package whose `register_hooks`
  subscribes closures that append the delivered `context` objects (and optionally `self`)
  to a plain list owned by the test.

### Source File Registry

- `goga/hooks/catalog/catalog.py` — 4 new records (tests: `tests/hooks/catalog/test_catalog.py`
  updated + one new test).
- `goga/usages/hooks/{__init__,facts,contexts,events}.py` — new zone (tests:
  `tests/usages/hooks/test_{facts,contexts,events}.py`, new).
- `goga/usages/sync/sync.py` — changed (tests: `tests/usages/sync/test_sync_moments.py`,
  new; existing sync suites must stay green).
- `goga/usages/status/status.py` — changed (tests: `tests/usages/status/test_status_moments.py`,
  new; existing status suites must stay green).
- Unchanged but exercised: `goga/commands/usages/usages.py`, `goga/usages/status/compare.py`,
  `goga/usages/status/models.py`.

---

### Positive Tests

#### `test_declared_actions_carries_the_four_usages_records`

**Setup**: none (maintained data).

**Input**: `declared_actions()`.

**Trace**:
```
declared_actions()
  → sorted(_DECLARED_ACTIONS, key=(domain, name))   # 24 records
  → filter domain == "usages"
```

**Assertions**:
```
usages = [(a.name, a.error_class) for a in declared_actions() if a.domain == "usages"]
assert usages == [("status_completed", "soft"), ("status_started", "soft"),
                  ("sync_completed", "soft"), ("sync_started", "soft")]
assert len(declared_actions()) == 24
domains = [a.domain for a in declared_actions()]
assert domains.index("topics") < domains.index("usages")   # the block sorts last
```

**Sufficiency**: an address the zone emits but the catalog misses is a runtime `ValueError`
in every usages flow — the record set is pinned against drift, together with the new total.

#### `test_zone_facade_exposes_the_thirteen_contract_names`

**Setup**: none.

**Input**: `import goga.usages.hooks as zone`.

**Trace**:
```
zone.Completion / zone.UsagesHooks / …   # each contract name resolves
zone.__all__                              # the exact thirteen names
```

**Assertions**:
```
assert zone.__all__ == ["ChangeVerdict", "Completion", "DepDrift", "DriftVerdict",
                        "FileChange", "StatusCompleted", "StatusStarted", "SyncCompleted",
                        "SyncDepOutcome", "SyncOutcome", "SyncStarted", "UsagesHooks",
                        "UsagesMoment"]
assert zone.UsagesHooks is not None and callable(zone.UsagesHooks)
```

**Sufficiency**: the facade is the consumer contract surface (the `usages-moments.md`
practice imports `UsagesHooks` from it); drift between modules and `__all__` breaks consumers
silently.

#### `test_facts_are_frozen_kw_only_dataclasses_and_enums_are_pinned`

**Setup**: none.

**Input**: the zone model classes.

**Trace**:
```
UsagesMoment(operation="sync", group=None, dep=None)   # keyword-only construction
SyncOutcome.synced.value …                              # member value strings
dataclasses.fields(SyncDepOutcome)                      # exact field sets
```

**Assertions**:
```
moment = UsagesMoment(operation="sync", group=None, dep=None)
assert moment.operation == "sync" and moment.group is None and moment.dep is None
for cls in (UsagesMoment, SyncDepOutcome, FileChange, DepDrift,
            SyncStarted, StatusStarted, SyncCompleted, StatusCompleted):
    assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen
    with pytest.raises(TypeError): cls("x")            # positional construction refuses
assert [f.name for f in dataclasses.fields(SyncDepOutcome)] == ["group", "dep", "outcome", "message"]
assert [f.name for f in dataclasses.fields(DepDrift)] == ["group", "dep", "verdict", "changes", "message"]
assert SyncDepOutcome(group="libs", dep="click",
                      outcome=SyncOutcome.failed).message is None      # the None default
assert [m.value for m in SyncOutcome] == ["synced", "skipped", "failed"]
assert [m.value for m in DriftVerdict] == ["new", "out of date", "error"]
assert [m.value for m in ChangeVerdict] == ["added", "modified", "removed"]
assert [m.value for m in Completion] == ["finished", "crashed"]
```

**Sufficiency**: the display strings are contractual (tools string-match verdicts); frozen
kw_only is the `convention` data-model rule; the field sets pin the wire shape against
accidental growth.

#### `test_construction_enumerates_nothing_and_one_registry_serves_all_four_moments`

**Setup**: `pin_package_environment({"goga_tool_rec": ["goga-tool-rec"]})` returning the
boundary mock; `install_tool_package("goga_tool_rec", register_hooks=_register)` where
`_register` subscribes one no-op hook to each of the four addresses and counts
`register_hooks` invocations via a closure counter.

**Input**: `hooks = UsagesHooks()`; then `hooks.emit_sync_started(m, False)`,
`hooks.emit_sync_completed(m, [], True, Completion.finished)`,
`hooks.emit_status_started(m)`, `hooks.emit_status_completed(m, [], True,
Completion.finished)` with `m = UsagesMoment(operation="sync", group=None, dep=None)`.

**Trace**:
```
UsagesHooks()                    → boundary not read (construction is cheap)
emit_sync_started(...)           → build_once → packages_distributions() read #1
emit_sync_completed(...)         → cached registry, no read
emit_status_started(...)         → cached registry, no read
emit_status_completed(...)       → cached registry, no read
```

**Assertions**:
```
assert boundary.call_count == 0          # after construction alone
… emit all four …
assert boundary.call_count == 1
assert register_hooks_calls == 1         # the callback ran exactly once
```

**Sufficiency**: pins the zone's headline property — the emissions never multiply the
package enumeration — and the cheap-construction requirement.

#### `test_emit_delivers_the_readonly_context_by_fixed_names`

**Setup**: a fake tool subscribing `def record(context): captured.append(context)` to
`usages/sync_started` and `def record_self(self, context): …` to `usages/sync_completed`;
boundary pinned.

**Input**: `emit_sync_started(m, force=True)`; `emit_sync_completed(m, [outcome], False,
Completion.crashed, reason="boom")` where `outcome = SyncDepOutcome(group="libs",
dep="click", outcome=SyncOutcome.failed, message="failed to sync usages for libs/click")`.

**Trace**:
```
emit_sync_started → SyncStarted(moment=m, force=True) → wrap_context →
  build_hook_arguments(record) → {"context": proxy} → record(context=proxy)
emit_sync_completed → SyncCompleted(...) → record_self(context=proxy, self=tool_context)
```

**Assertions**:
```
assert captured[0].moment is m and captured[0].force is True
assert captured[1].deps == [outcome] and captured[1].success is False
assert captured[1].completion is Completion.crashed and captured[1].reason == "boom"
with pytest.raises(AttributeError):
    captured[0].force = False        # the delivered view is read-only
```

**Sufficiency**: the delivered facts are the tool's only channel — the exact field delivery
and the write-block are the contract's core guarantees.

#### `test_sync_emits_both_moments_with_per_dep_outcomes`

**Setup**: `tmp_path` cwd with a `.goga/config.yml` declaring `libs/click` (clone ok),
`libs/common` (clone raises), `libs/skipped` (target dir pre-created); a fake tool capturing
all `usages/*` contexts; `mock.patch.object(_sync_mod, "clone_repository")` with
`side_effect` returning a tmp repo containing `.usages/conventions.md` for `click`/`skipped`
and raising `RuntimeError("git failed https://user:tok@x/common.git")` for `common`.

**Input**: `sync(force=False, group="libs", dep=None)`.

**Trace**:
```
sync → _effective_config (no subscriptions on config domain) →
emit_sync_started(UsagesMoment("sync", "libs", None), False) →
_sync_work: click → synced; common → failed (message "failed to sync usages for libs/common");
            skipped → skipped →
emit_sync_completed(outcomes, success=False, finished) → return 1
```

**Assertions**:
```
assert sync_result == 1
started = [c for c in captured if type(c).__name__ == "SyncStarted"]
completed = [c for c in captured if type(c).__name__ == "SyncCompleted"]
assert len(started) == 1 and started[0].moment.operation == "sync"
assert started[0].moment.group == "libs" and started[0].force is False
assert len(completed) == 1
assert [(o.group, o.dep, o.outcome) for o in completed[0].deps] == [
    ("libs", "click", SyncOutcome.synced),
    ("libs", "common", SyncOutcome.failed),
    ("libs", "skipped", SyncOutcome.skipped)]
assert completed[0].deps[1].message == "failed to sync usages for libs/common"
assert "tok" not in completed[0].deps[1].message        # credential-free by construction
assert completed[0].success is False and completed[0].completion is Completion.finished
```

**Sufficiency**: one record per matched dep (synced/skipped/failed with message), overall
success, the finished marker, and the credential-free message — the sync-completion contract
in one observable place.

#### `test_sync_no_op_run_fires_both_moments_with_empty_outcomes`

**Setup**: config with no `usages` section; capturing fake tool installed.

**Input**: `sync()`.

**Trace**:
```
sync → _effective_config → emit_sync_started → config.usages is None →
_sync_work returns 0 → emit_sync_completed([], True, finished) → return 0
```

**Assertions**:
```
assert sync() == 0
assert len(started) == 1 and len(completed) == 1
assert completed[0].deps == [] and completed[0].success is True
assert completed[0].completion is Completion.finished
```

**Sufficiency**: "a no-op run fires both moments with the empty fact set" — the wrap-the-
operation-not-the-workload rule.

#### `test_status_emits_the_changed_set_with_the_file_projection`

**Setup**: `tmp_path` cwd with a config declaring `libs/click`; the local target
`.goga/usages/libs/click/` populated; `mock.patch.object(_status_mod, "compute_dep_status")`
returning `DepStatus(group="libs", dep="click", state=UsageState.out_of_date, entries=[
EntryStatus(path="b.md", kind=EntryKind.file, change=EntryChange.unchanged),
EntryStatus(path="c.md", kind=EntryKind.file, change=EntryChange.removed),
EntryStatus(path="docs", kind=EntryKind.dir, change=EntryChange.modified),
EntryStatus(path="docs/a.md", kind=EntryKind.file, change=EntryChange.added)])`;
capturing fake tool.

**Input**: `status(group="libs")`.

**Trace**:
```
status → emit_status_started(UsagesMoment("status", "libs", None)) →
_status_work: _check_dep → DepStatus(out_of_date) → _derive_drift →
  FileChange("c.md", removed), FileChange("docs/a.md", added) →
emit_status_completed(changed, success=False, finished) → report
```

**Assertions**:
```
started[0].moment.operation == "status"
completed[0].changed == [DepDrift(group="libs", dep="click", verdict=DriftVerdict.out_of_date,
                                  changes=[FileChange(path="c.md", change=ChangeVerdict.removed),
                                           FileChange(path="docs/a.md", change=ChangeVerdict.added)])]
assert completed[0].success is False
assert report.deps[0].state is UsageState.out_of_date     # the report is unchanged in shape
```

**Sufficiency**: the projection is the riskiest new logic — files only, directories dropped,
unchanged dropped, verdict mapping, sorted order preserved — pinned with one exhaustive
expected value.

#### `test_status_up_to_date_run_has_an_empty_changed_set_and_success`

**Setup**: as above but `compute_dep_status` returns state `up_to_date` (entries populated
with unchanged files).

**Input**: `status()`.

**Assertions**: `completed[0].changed == []` and `completed[0].success is True` and
`report.exit_code == 0`.

**Sufficiency**: "an empty changed set reads as no drift" and the success ≡ exit-code-0
agreement.

#### `test_status_new_dep_lands_in_the_changed_set_with_the_empty_change_list`

**Setup**: `tmp_path` cwd with a config declaring `libs/click`; the local target
`.goga/usages/libs/click/` absent (never synchronized); capturing fake tool installed.
No git-boundary mock — `_check_dep` returns the `new` state before `compute_dep_status`
is ever reached.

**Input**: `status()`.

**Trace**:
```
status → _effective_config → emit_status_started(UsagesMoment("status", None, None)) →
_status_work: _check_dep → target absent → DepStatus(new, entries=[]) →
_derive_drift → DepDrift(new, changes=[]) → changed=[drift] →
emit_status_completed(changed=[drift], success=False, finished) → report
```

**Assertions**:
```
assert completed[0].changed == [DepDrift(group="libs", dep="click",
                                         verdict=DriftVerdict.new, changes=[])]
assert completed[0].changed[0].message is None
assert completed[0].success is False
assert report.deps[0].state is UsageState.new and report.exit_code == 1
assert completed[0].completion is Completion.finished
```

**Sufficiency**: the only unpinned branch of the `_derive_drift` projection — a
never-synchronized dep must read as drift (success False, exit 1) with the empty change
list and no message.

---

### Negative Tests

#### `test_failing_hook_warns_and_the_operation_is_unaffected`

**Setup**: a fake tool subscribing a raising hook (`def boom(context): raise
RuntimeError("kaput")`) to `usages/sync_started` and a recording hook to
`usages/sync_completed`; a one-dep config; `clone_repository` mocked ok; `caplog` at
WARNING.

**Input**: `sync()`.

**Trace**:
```
emit_sync_started → hook raises → soft class → logger.warning("hook boom of tool … failed
on usages.sync_started: kaput") → sequence continues → sync proceeds → completion delivered
to the recording hook
```

**Assertions**:
```
assert result == 0
assert any("usages.sync_started" in r.message and "kaput" in r.message for r in caplog.records)
assert len(completed) == 1            # the run reached its completion
```

**Sufficiency**: the soft error class is the zone's safety property — a broken tool never
breaks the operation.

#### `test_config_boundary_abort_fires_no_usages_moment`

**Setup**: `tmp_path` cwd with NO `.goga/config.yml`; capturing fake tool installed.

**Input**: `sync()` (expect `FileNotFoundError`).

**Trace**:
```
sync → _effective_config → load_project_config raises FileNotFoundError → propagates
(no UsagesMoment composed, no emission)
```

**Assertions**:
```
with pytest.raises(FileNotFoundError): sync()
assert captured == []
```

**Sufficiency**: the abort-semantics boundary — a run aborting at the configuration boundary
fires no usages moment.

#### `test_status_error_dep_lands_in_the_changed_set_with_its_message`

**Setup**: one-dep config; `compute_dep_status` mocked to raise; capturing tool.

**Input**: `status()`.

**Trace**:
```
_status_work → _check_dep catches → DepStatus(error, error="failed to check usages status
for libs/click") → _derive_drift → DepDrift(error, message=same) →
emit_status_completed(changed=[drift], success=False, finished)
```

**Assertions**:
```
assert completed[0].changed[0].verdict is DriftVerdict.error
assert completed[0].changed[0].changes == []
assert completed[0].changed[0].message == "failed to check usages status for libs/click"
assert completed[0].completion is Completion.finished      # best-effort, not a crash
assert result.exit_code == 1
```

**Sufficiency**: error deps are part of the changed set with the empty change list — the
status-completion contract's error arm.

#### `test_a_hook_receives_nothing_it_did_not_declare`

**Setup**: a fake tool subscribing `def only_self(self): seen.append("called")` to
`usages/status_started`.

**Input**: `emit_status_started(m)`.

**Assertions**: `seen == ["called"]` (no `TypeError` — the call injects only `self`).

**Sufficiency**: the fixed offered-names injection is platform-guaranteed; the zone must not
have broken it by its context shape.

---

### Edge Case Tests

#### `test_sync_crash_path_emits_the_crashed_completion_and_reraises`

**Setup**: one-dep config; capturing tool; `mock.patch.object(_sync_mod, "clean_usages_dir",
side_effect=RuntimeError("boom"))`.

**Input**: `sync(force=True)`.

**Trace**:
```
emit_sync_started → _sync_work → clean_usages_dir raises RuntimeError →
except: emit_sync_completed([], False, Completion.crashed, reason="boom") → raise
```

**Assertions**:
```
with pytest.raises(RuntimeError, match="boom"): sync(force=True)
assert completed[0].completion is Completion.crashed
assert completed[0].success is False and completed[0].reason == "boom"
assert completed[0].deps == []
```

**Sufficiency**: the crash path is the contract's strongest guarantee — completion as a
fact, the original failure preserved, partial facts delivered.

#### `test_status_crash_path_carries_the_partial_changed_set`

**Setup**: two-dep config (`libs/click`, `libs/common`); capturing tool;
`mock.patch.object(_status_mod, "_check_dep", side_effect=[out_of_date_depstatus,
RuntimeError("boom")])` where `out_of_date_depstatus` is a real `DepStatus`
(`libs/click`, `out_of_date`, one modified-file entry) — the crash must be injected
outside `_check_dep`, whose `except Exception` absorbs any raise of `compute_dep_status`
into an error dep (the best-effort path, never a crash).

**Input**: `status()`.

**Trace**:
```
emit_status_started → dep#1: _check_dep returns out_of_date → _derive_drift (real) →
changed=[drift1] → dep#2: _check_dep raises RuntimeError → escapes _status_work →
except: emit_status_completed(changed=[drift1], False, crashed, "boom") → raise
```

**Assertions**:
```
with pytest.raises(RuntimeError, match="boom"): status()
assert completed[0].completion is Completion.crashed and completed[0].reason == "boom"
assert completed[0].success is False
assert completed[0].changed == [DepDrift(group="libs", dep="click",
                                        verdict=DriftVerdict.out_of_date, changes=[…])]
```

(Variant with dep#1 up to date asserts `changed == []` — the empty partial set.)

**Sufficiency**: "the partial changed-set records known at the break-off point travel with
the overall failure" — the raise must escape the work helper, so the injection point is
`_check_dep` (or `_derive_drift`), never `compute_dep_status` (absorbed best-effort).

#### `test_filtered_deps_are_absent_from_every_fact`

**Setup**: the multi-group config (`libs.click`, `libs.common`, `apps.common`); capturing
tool; `clone_repository` mocked ok.

**Input**: `sync(dep="common")`.

**Assertions**:
```
outcomes = [(o.group, o.dep) for o in completed[0].deps]
assert outcomes == [("apps", "common"), ("libs", "common")]   # click absent, insertion order
assert started[0].moment.dep == "common"                       # the envelope mirrors the filters
```

**Sufficiency**: "a filtered-out dep is silently absent from every fact" and the envelope
mirrors the operation's own inputs.

#### `test_no_tool_packages_keep_the_surface_inert`

**Setup**: `pin_package_environment({})`; one-dep config; `clone_repository` mocked ok.

**Input**: `sync()`; `status()` (with `compute_dep_status` mocked up-to-date).

**Assertions**:
```
assert sync() == 0 and (Path(".goga/usages/libs/click")).exists()
assert status().exit_code == 0
# no moment code path raised, no extra output: capsys stdout unchanged vs. the classic shape
```

**Sufficiency**: "with no tool packages installed the whole surface is inert — both commands
behave as if the zone did not exist".

#### `test_empty_usages_section_fires_both_moments_and_force_still_cleans`

**Setup**: `tmp_path` cwd with a config whose `usages` section is present but empty
(`usages: {}`); a stale directory `.goga/usages/libs/stale/` pre-created; capturing fake
tool installed; `clean_usages_dir` NOT mocked.

**Input**: `sync(force=True)`, then `status()`.

**Trace**:
```
sync: _effective_config → emit_sync_started → config.usages is {} (not None) →
force → clean_usages_dir removes the stale dir → loop runs zero iterations →
emit_sync_completed([], True, finished) → 0
status: emit_status_started → not config.usages → {} → empty report →
emit_status_completed([], True, finished) → exit_code 0
```

**Assertions** (captured contexts filtered by `moment.operation`, as in the neighboring
tests):
```
assert sync(force=True) == 0
assert not Path(".goga/usages/libs/stale").exists()    # the clean ran — {} ≠ None
assert sync_completed.deps == [] and sync_completed.success is True
assert status().exit_code == 0
assert status_completed.changed == [] and status_completed.success is True
```

**Sufficiency**: pins the None-vs-{} distinction the design's edge-case analysis relies
on — only `None` short-circuits before the force clean; an empty section still cleans,
and in both cases both moments fire with the empty fact set (the status contract's
"None or empty" wording).

#### Catalog pin updates (`tests/hooks/catalog/test_catalog.py`)

**Setup/Changes**: the existing pinning tests are updated to the grown catalog —
`test_schema_amend_cell_record_present`, `test_config_amend_config_record_present`,
`test_declared_actions_carries_the_seven_topics_records`,
`test_catalog_carries_the_three_pipeline_records`: `len(records) == 20` → `== 24` (and the
two `len(pre_existing) + 1` assertions gain the four usages triples in their `pre_existing`
lists so the arithmetic stays honest); `test_catalog_carries_the_five_build_records`: the
frozen expected list gains the four `("usages", …, "soft")` triples at the end; the new
`test_declared_actions_carries_the_four_usages_records` above joins the class.

**Sufficiency**: the catalog is the source of address truth; stale pins would either mask a
lost record or block an additive one.

## Additional Instructions for the Implementation Agent

- Follow `goga-cell-python` (facade `__all__` exactness, mandatory type hints, no `*args`/
  `**kwargs`) and `.goga/usages/conventions.md` (relative imports, frozen kw_only
  dataclasses, Google docstrings with `Args`/`Returns`/`Raises`, logging with `extra`).
- Import shapes: the zone uses `from ...hooks import HookRegistry, emit_hook_event`
  (three dots to the platform facade); the operations use `from ..hooks import …` (two
  dots). Do not import `declared_actions` in `events.py` — the platform emission resolves
  the catalog record; an unused import fails ruff.
- Do not touch: `goga/usages/__init__.py` (facade unchanged by plan), `goga/commands/usages/
  usages.py`, `clean.py`/`clone.py`/`deploy.py`, `compare.py`/`models.py`, both doc pages
  (already current), and every practice file listed in `.usages/` Update (all verified
  current).
- The two design-fixed values are binding: the failed-outcome message
  `f"failed to sync usages for {group_name}/{dep_name}"`, and the crash reason
  `str(reason)` of the single `except Exception` wrapper (never `BaseException`).
- The private helpers `_sync_work` / `_status_work` (accumulators passed in) and
  `_derive_drift` + `_FILE_CHANGE` are the designed structure — they keep the emission
  scaffold flat (exactly one finished-emission site and one crashed-emission site per
  operation) and the orchestrators within the lint complexity budget.
- Keep the status INFO lifecycle logs at their exact current positions (inside the work
  helper, around the loop, after the empty-section check).
- Test placement per convention: new `tests/usages/hooks/` package (with `__init__.py` and a
  `conftest.py` re-exporting the two platform fixtures), new `tests/usages/sync/
  test_sync_moments.py`, new `tests/usages/status/test_status_moments.py`; update
  `tests/hooks/catalog/test_catalog.py` pins. Mock only at the boundaries shown (the
  import-point mocks for `clone_repository`/`compute_dep_status`/`clean_usages_dir` and the
  two platform fixtures); the platform delivery runs for real.
- Validation before done: `goga lint` (0 errors), `ruff check goga/`, the full pytest suite
  green, and the facade check `python -c "from goga.usages.hooks import UsagesHooks,
  UsagesMoment, SyncDepOutcome, DepDrift, Completion"`.
