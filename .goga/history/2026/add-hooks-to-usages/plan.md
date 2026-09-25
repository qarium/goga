# Plan: `add-hooks-to-usages`

Result of compiling `.goga/history/2026/add-hooks-to-usages/design.md` (design-review verified:
4 remarks fixed, 0 skipped) into ralphex execution tasks. All contract artifacts are already on
disk and lint-clean (`goga lint`: 82 cells, 0 errors) — this plan covers the **implementation**
those contracts require.

## Purpose

Open the usages domain to the hooks platform as four soft run-level moments. After
implementation:

- `goga/hooks/catalog` declares the four usages addresses (`sync_started`, `sync_completed`,
  `status_started`, `status_completed` — all `soft`), growing the catalog from 20 to 24 records.
- The new zone package `goga.usages.hooks` exists with thirteen contract entities: eight facts
  (`facts.py`), four read-only contexts (`contexts.py`), and the `UsagesHooks` checkpoint surface
  (`events.py`), re-exported through the package facade (`__init__.py`).
- `sync` and `status` own their run-level moments: the started moment fires once the effective
  configuration is resolved; the completed moment fires on every return path after the start —
  finished and crashed alike — with per-dep outcome facts (sync) and drift-projection facts
  (status).
- The commands, the CLI output, exit codes, and the best-effort error handling are byte-identical
  to today under any subscription state; with no tool packages installed the whole surface is inert.

The most important gaps between contract and code: the zone cell contains only `CODEMANIFEST`
and its practice file (no Python at all); the catalog lacks the four records; the two operations
contain no moment emission, no outcome/drift accumulation, and no crash wrapper.

Overall strategy: implement leaves-first in the design's dependency order — catalog records →
zone facts → contexts → events → zone facade → `sync` rework → `status` rework → cross-operation
integration tests. Each coding task follows the TDD workflow.

## Context

### Contract Surface

#### Changed entity — `declared_actions()` (`goga/hooks/catalog/CODEMANIFEST`)

- Type: function (unchanged signature — no API change, additive data growth)
- Declared `location`: `goga/hooks/catalog/catalog.py`
- Facade obligation: importable from `goga.hooks.catalog` (already satisfied — `__all__` =
  `["Action", "declared_actions"]`)
- Contract delta: four requirement bullets appended — records `domain="usages"`, `name` ∈
  {`sync_started`, `sync_completed`, `status_started`, `status_completed`}, `error_class="soft"`
- Semantic requirements: additive growth only; published records are never rewritten; the
  `(domain, name)` sort places the usages block last (build < config < onboarding < pipeline <
  schema < statuses < topics < usages); the total becomes 24; a fresh list per call
- Downstream consumers (`goga/hooks` facade re-export, `goga/commands/hooks` tree,
  registration-envelope validation) read the catalog dynamically — unaffected

#### New entities — zone `goga/usages/hooks/CODEMANIFEST` (13 types)

All frozen `kw_only` dataclasses or `enum.Enum` members, per `convention` and the manifest
annotations. The zone is notification-only: every context is built from the values the caller
passes — no configuration reads, no git access, no file reads; no fact carries a
credential-bearing value.

**Entity: `UsagesMoment(operation, group, dep)`**
- Type: dataclass (facts) — identity envelope of every moment
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.usages.hooks`
- Properties: `operation -> str` (sync or status), `group -> str | None` (None when no filter),
  `dep -> str | None` (None when no filter)
- Semantic requirements: pure facts — the values mirror the operation's own inputs; a dep
  filtered out by the filters is silently absent from every downstream fact

**Entity: `SyncOutcome()`**
- Type: enum — fixed value set of a matched dep's sync outcome
- Declared `location`: `facts.py`
- Members: `synced="synced"`, `skipped="skipped"`, `failed="failed"` (display strings are
  contractual — tools string-match verdicts)

**Entity: `SyncDepOutcome(group, dep, outcome, message=None)`**
- Type: dataclass (facts) — one matched dep's sync outcome
- Declared `location`: `facts.py`
- Properties: `group -> str`, `dep -> str`, `outcome -> SyncOutcome`,
  `message -> str | None` (credential-free failure message when failed; None otherwise)
- Semantic requirements: the message is set only when the outcome is failed; one record per
  matched dep — filtered-out deps are absent

**Entity: `DriftVerdict()`**
- Type: enum — fixed value set of a changed dep's drift verdict
- Declared `location`: `facts.py`
- Members: `new="new"`, `out_of_date="out of date"`, `error="error"` (note the spaced display
  string, mirroring `UsageState.out_of_date = "out of date"`)

**Entity: `ChangeVerdict()`**
- Type: enum — fixed value set of one file's change
- Declared `location`: `facts.py`
- Members: `added="added"`, `modified="modified"`, `removed="removed"`

**Entity: `FileChange(path, change)`**
- Type: dataclass (facts) — one changed file within a dep
- Declared `location`: `facts.py`
- Properties: `path -> str` (relative posix path within the dep), `change -> ChangeVerdict`
- Semantic requirements: files only — a directory node never appears as a record

**Entity: `Completion()`**
- Type: enum — terminal marker of a completed context
- Declared `location`: `facts.py`
- Members: `finished="finished"`, `crashed="crashed"`

**Entity: `DepDrift(group, dep, verdict, changes, message=None)`**
- Type: dataclass (facts) — one changed-set record (a matched dep whose verdict is not up to date)
- Declared `location`: `facts.py`
- Properties: `group -> str`, `dep -> str`, `verdict -> DriftVerdict`,
  `changes -> list[FileChange]` (populated for out-of-date; empty for new and error),
  `message -> str | None` (credential-free error message when error; None otherwise)
- Semantic requirements: directory nodes absent from the change list; the changed set contains
  no up-to-date dep — an empty changed set reads as no drift among the matched deps

**Entity: `SyncStarted(moment, force)`**
- Type: dataclass (read-only context)
- Declared `location`: `contexts.py`
- Properties: `moment -> UsagesMoment`, `force -> bool`
- Semantic requirements: read-only facts of a starting operation — a hook observes and cannot
  alter anything

**Entity: `StatusStarted(moment)`**
- Type: dataclass (read-only context)
- Declared `location`: `contexts.py`
- Properties: `moment -> UsagesMoment`
- Semantic requirements: read-only facts of a starting operation

**Entity: `SyncCompleted(moment, deps, success, completion, reason=None)`**
- Type: dataclass (read-only context)
- Declared `location`: `contexts.py`
- Properties: `moment -> UsagesMoment`, `deps -> list[SyncDepOutcome]` (one per matched dep, in
  iteration order; empty on a no-op run), `success -> bool` (True exactly when no matched dep
  failed), `completion -> Completion`, `reason -> str | None`
- Semantic requirements: `success` is False whenever the marker is crashed; `reason` is present
  exactly when the marker is crashed; on a crash the outcome records are the best facts known at
  the break-off point

**Entity: `StatusCompleted(moment, changed, success, completion, reason=None)`**
- Type: dataclass (read-only context)
- Declared `location`: `contexts.py`
- Properties: `moment -> UsagesMoment`, `changed -> list[DepDrift]` (one per matched dep whose
  verdict is not up to date — error deps included), `success -> bool` (True exactly when the
  changed set is empty), `completion -> Completion`, `reason -> str | None`
- Semantic requirements: same crash invariants as `SyncCompleted`

**Entity: `UsagesHooks()`**
- Type: class — the checkpoint surface with four emit methods
- Declared `location`: `events.py`
- Facade obligation: importable from `goga.usages.hooks`
- Methods:
  - `emit_sync_started(moment: UsagesMoment, force: bool)` — fire-and-forget; resolves
    domain="usages", action="sync_started" against `declared_actions`, builds the `SyncStarted`
    context, emits via `emit_hook_event`; a failing hook is skipped with a warning (soft)
  - `emit_sync_completed(moment, deps, success, completion, reason=None)` — same shape over
    `SyncCompleted` at `usages/sync_completed`; completion is a fact, not a success claim
  - `emit_status_started(moment)` — same shape over `StatusStarted` at `usages/status_started`
  - `emit_status_completed(moment, changed, success, completion, reason=None)` — same shape over
    `StatusCompleted` at `usages/status_completed`
- Semantic requirements: cheap construction — no enumeration and no imports happen at
  construction; one `HookRegistry` per instance carries every moment (the assembly runs once per
  run whatever the number of moments); every context is built from the values the caller passes
- Imported dependencies: `HookRegistry`, `emit_hook_event` from the platform facade
  `goga/hooks` (Python import `from ...hooks import HookRegistry, emit_hook_event` — three dots:
  `goga.usages.hooks` → `goga` → `goga.hooks`). `declared_actions` is NOT imported in Python:
  the catalog resolution happens inside `emit_hook_event`; an unused import would fail ruff
- Annotation context (manifest → entity → method cascade): use `declaring-actions` for the
  emission contract, `registering-hooks` for the registration contract behind every moment,
  `convention` for code style and relative imports

#### Changed entities — the two operations

**Entity: `sync(force, group, dep) -> exit_code: int`** (`goga/usages/sync/CODEMANIFEST`)
- Declared `location`: `sync.py` — signature UNCHANGED
- Facade obligation: importable from `goga.usages.sync` and `goga.usages` (existing, keep green)
- Contract delta (annotation only): the algorithm gains the moment steps — compose
  `UsagesMoment`, emit sync-start after the effective configuration is resolved, record one
  `SyncDepOutcome` per matched dep (skipped on the existing-target path, synced on success,
  failed with the credential-free message on the per-dep error path), emit sync-completion on
  every return path (no-op, finished, crash), crash wrapper re-raising the original exception
- Imported dependencies (new import block): `UsagesHooks`, `UsagesMoment`, `SyncDepOutcome`,
  `SyncOutcome`, `Completion` + the `usages-moments` practice from `goga/usages/hooks`
  (Python: `from ..hooks import Completion, SyncDepOutcome, SyncOutcome, UsagesHooks,
  UsagesMoment` — two dots)
- Behavioral requirements that must NOT change: exit-code accumulation, best-effort per-dep
  isolation, the fail-loud config boundary (no moment fires on that abort), the clone/deploy
  try/except/finally structure, output

**Entity: `status(group, dep) -> report: UsageStatusReport`** (`goga/usages/status/CODEMANIFEST`)
- Declared `location`: `status.py` — signature UNCHANGED
- Facade obligation: importable from `goga.usages.status` and `goga.usages` (existing, keep green)
- Contract delta: same moment wiring as sync plus the `DepDrift` derivation — for every matched
  dep with a non-up-to-date state, derive one `DepDrift` (new → empty change list; error →
  message from `DepStatus.error`, empty change list; out of date → per-file `FileChange` list
  projected from the entry diff, files only, directory nodes dropped)
- Imported dependencies (new import block): `UsagesHooks`, `UsagesMoment`, `DepDrift`,
  `DriftVerdict`, `FileChange`, `ChangeVerdict`, `Completion` + `usages-moments` from
  `goga/usages/hooks`; `EntryKind` is already present in the existing `models` import — used as-is
- Behavioral requirements that must NOT change: the report shape, `UsageStatusReport.exit_code`
  semantics, the read-only nature, the INFO lifecycle log placement, `_check_dep`'s absorption
  of per-dep failures into error deps

### Re-exports

No DSL re-export blocks (`->Name: {}`) exist in any touched manifest. The facade obligations are
Python-level (per `goga-cell-python`): the zone package `__init__.py` must expose exactly the
thirteen contract names through `__all__`, every name importable from `goga.usages.hooks`.

### Usages Context

- `convention` (`.goga/usages/conventions.md`): mandatory Python rules — relative imports for all
  intra-package references; stdlib `dataclasses` with `kw_only=True` (frozen where the contract
  says facts); `logging` module loggers with `extra` metadata; Google-style docstrings
  (`Args`/`Returns`/`Raises`); one blank line between logical blocks inside function bodies;
  tests mirror the source tree, mocks only at external boundaries; validation commands
  (`pytest tests/ -x`, `ruff check`, facade `python -c "from package import Entity"`).
  Relevant to every task.
- `click` (`.goga/usages/cooks/click.md`): CLI construction and the stderr/stdout channel
  discipline. Relevant only in that the amendment summary lines keep printing to stderr
  (`click.echo(line, err=True)`) — unchanged code, no new output channel is added by the moments.
- `git` (inline, sync manifest): subprocess invocation contract for git (`check=True`,
  `capture_output=True`, `GIT_TERMINAL_PROMPT=0`); mock subprocess in tests. Relevant only in
  that `clone_repository` stays untouched — the zone reads no git.

### Imported Usages

- `checkpoints` from `goga/config/hooks` (sync, status) — path
  `goga/config/hooks/.usages/checkpoints.md`. The config-amendment delivery at the load moment:
  `ConfigHooks().amend_config(config=…)`, print `overlay.summary_lines` to stderr, consume
  `overlay.config`. Traced dependency of both operations' step 1 — already implemented in
  `sync.py` (`_effective_config`), to be mirrored in `status.py`.
- `usages-moments` from `goga/usages/hooks` (sync, status) — path
  `goga/usages/hooks/.usages/usages-moments.md` (already on disk). The moment-delivery practice:
  one `UsagesHooks` per run, resolve facts before delivery, emit around the operation, complete
  the crash path (`except Exception` → crashed emission → re-raise), no-op and abort semantics.
  The `_sync_work`/`_status_work` structure mirrors the practice's `run_sync_work` sketch.
- `declaring-actions` from `goga/hooks` (zone) — path `goga/hooks/.usages/declaring-actions.md`.
  The emission contract: declare the action in the catalog, own the context, emit via
  `emit_hook_event(HookRegistry(), domain, action, context_for=…)`; the platform carries
  enumeration, delivery, error classes, diagnostics.
- `registering-hooks` from `goga/hooks` (zone) — path `goga/hooks/.usages/registering-hooks.md`.
  The registration contract behind every moment: `register_hooks(hooks)` →
  `hooks.subscribe(domain, action, name, hook)`; the fixed offered parameter names (`context`,
  `self`); the failure ladder (soft skip / hard stop; broken import the only fatal case).
- `registering-hooks` from `goga/usages` (commands manifest) — path
  `goga/usages/.usages/registering-hooks.md` (already on disk). The consumer-facing practice for
  the four usages addresses (events table, views, integration scenarios). No code obligation —
  it is the reference the fake tool packages in the test tasks imitate (the subscribe sketch and
  the fixed offered names).
- `sync-usages`, `usages-status` from `goga/usages` (commands manifest) — unchanged references
  documenting the two operations' consumer contracts; the moments do not change them.

### Local Usages

Both `.usages/` files the design planned are already on disk (created by the apply stage,
verified current by the design and its review). **No creation or update tasks are needed.**

- `goga/usages/hooks/.usages/usages-moments.md` — functional category: how the sync and status
  operations consume the hooks zone (surface, fact resolution, emit-around, crash path, no-op and
  abort semantics). Status: current, additions needed: none. Related entities: `UsagesHooks`,
  `sync`, `status`. Creation task reference: none (on disk).
- `goga/usages/.usages/registering-hooks.md` — functional category: how a `goga_tool_*` package
  subscribes to the four usages addresses (events table, views, subscribe sketch). Status:
  current, additions needed: none. Related entities: the four catalog records. Creation task
  reference: none (on disk).

### External Dependencies

- The hooks platform itself (`goga/hooks`): `HookRegistry.build_once()` is idempotent
  (`goga/hooks/registry/state.py:54`); `wrap_context` closes attribute writes on the delivered
  proxy (`goga/hooks/dispatch/delivery.py:60`); `build_hook_arguments` injects only the declared
  `context`/`self` names (`delivery.py:94`); a raising hook under a soft record →
  `logger.warning` naming hook, tool, address, reason → the sequence continues
  (`goga/hooks/dispatch/emit.py:70-77` resolves the address against `declared_actions`).
- stdlib only for the zone facts: `dataclasses`, `enum`.
- pytest + `unittest.mock` for the test stack; ruff for lint; `goga` CLI for cell lint.
- No new third-party dependencies. No `pyproject.toml` changes.

### Entity Interaction and Data Flow (verbatim from the design)

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
        ├─────────────────────────────────────────────┐
        │ 3. the operation's own work                  ▼
        │    sync: clone/deploy per dep → SyncDepOutcome   emit_hook_event
        │    status: compute_dep_status → DepStatus            │ resolve record in
        │            → DepDrift projection                      │ declared_actions()
        │ 4. UsagesHooks.emit_<op>_completed                    ▼
        │    (finished — or crashed from the except arm)   for each subscription
        ▼                                                  in enumeration order:
 exit_code / UsageStatusReport                        wrap_context(view)
        │                                             build_hook_arguments
        ▼                                             hook(context=…, self=…)
 CLI rendering / exit code                            (soft: a failure warns and continues)
```

**Data flows.**

- **Flow A — sync run with subscriptions.** `goga usages sync --force` → command reads
  group/dep from the click context → `sync(force, group, dep)` → `_effective_config()` (load +
  config amendment + summary lines to stderr) → `UsagesMoment("sync", group, dep)` →
  `UsagesHooks().emit_sync_started(moment, force)` → registry build → per-tool delivery of
  `SyncStarted` → `_sync_work` appends `SyncDepOutcome` records (skipped / synced / failed) →
  `emit_sync_completed(moment, outcomes, exit_code == 0, Completion.finished)` → per-tool
  delivery of `SyncCompleted` → exit code to the command.
- **Flow B — status run with subscriptions.** Same shape; `_status_work` collects `DepStatus`
  records and derives `DepDrift` records; the completion carries
  `StatusCompleted(changed, not changed, finished)`; the report returns to the command for
  rendering.
- **Flow C — crash.** Any `Exception` escaping the work helper after the start emission →
  `emit_<op>_completed(…, False, Completion.crashed, reason=str(reason))` → re-raise → the
  command wrapper converts as for any other failure (or the traceback escapes in programmatic
  use — identical to today's behavior).
- **Flow D — abort at the configuration boundary.** `load_project_config` or
  `ConfigHooks.amend_config` raises before any usages emission → no moment fires → the command
  wrapper converts to a clean `click.ClickException`.
- **Flow E — inert environment.** No `goga_tool_*` packages installed → the registry build
  enumerates nothing → every emission iterates zero subscriptions and returns → output, exit
  codes, and the report are byte-identical to the pre-zone behavior.

## Facts

- The zone cell `goga/usages/hooks/` exists with `CODEMANIFEST` (13 types) and
  `.usages/usages-moments.md` — and nothing else. `goga/usages/.usages/registering-hooks.md`
  exists. Both doc pages (`docs/features/usages/hooks.md`, `docs/features/hooks/hooks.md`) are
  already current.
- `goga lint`: 82 cells, 0 errors — the contract layer is consistent; no CODEMANIFEST edits are
  needed or allowed.
- `goga/hooks/catalog/catalog.py`: `_DECLARED_ACTIONS` currently holds 20 records; the four
  usages records are missing. `declared_actions()` returns `sorted(_DECLARED_ACTIONS,
  key=(domain, name))`.
- `goga/usages/sync/sync.py` already has the `_effective_config()` helper (load + amend +
  stderr lines) — the design's status extraction mirrors it verbatim.
- `goga/usages/status/status.py` has the config delivery inline in `status()` and the `_check_dep`
  helper whose `except Exception` absorbs any per-dep failure into an error `DepStatus`
  (`status.py:136`) — a raise of `compute_dep_status` can therefore never produce a crash; crash
  injection in tests must target `_check_dep` or `_derive_drift`.
- `UsageStatusReport.exit_code` is a computed property (`models.py:124`): 0 iff every dep is up
  to date — `success` ⇔ `exit_code == 0` ⇔ empty changed set coincide exactly.
- `EntryStatus`/`EntryChange`/`EntryKind` (re-exported by `status.py` from `models.py`) carry
  everything the `DepDrift` projection needs; `_diff_entries` sorts path-wise at
  `compare.py:166` — filtering a sorted list keeps it sorted.
- The platform facade `goga/hooks` exposes `HookRegistry` and `emit_hook_event`; importing it
  enumerates nothing.
- Test infrastructure on disk: `tests/hooks/conftest.py` provides `pin_package_environment`
  (pins `packages_distributions` — the single enumeration mock point) and `install_tool_package`
  (installs a fake `goga_tool_*` into `sys.modules` with a `register_hooks` callback);
  `tests/usages/conftest.py` re-exports both; `tests/pipeline/hooks/conftest.py` is the nested
  re-export precedent. `tests/conftest.py` additionally provides `make_repo`, `write_config`,
  `patch_clone`, `is_kw_only_dataclass`, and autouse cwd/home isolation.
- Mocking pattern (established): `_sync_mod = importlib.import_module("goga.usages.sync.sync")`
  then `mock.patch.object(_sync_mod, "clone_repository")` — the facade function shadows the
  submodule attribute, so dotted-path patching breaks on Python 3.10.
- The command wrappers already convert `ValueError`/`ImportError` to `click.ClickException`
  (`usages.py:88-95`, `usages.py:114-124`) — the registry-build `ImportError` at the first usages
  emission is covered; no command change is needed.
- `goga/usages/__init__.py` (facade), `goga/commands/usages/usages.py`, `clean.py` / `clone.py` /
  `deploy.py`, `compare.py` / `models.py` are unchanged by design.

## Gap Analysis

- Missing contract entities: all 13 zone types — `facts.py`, `contexts.py`, `events.py` do not
  exist.
- Missing facade exposure: `goga/usages/hooks/__init__.py` does not exist; nothing is importable
  from the zone package.
- Catalog gap: 20 records on disk vs the 24 the contracts declare (four `usages` records
  missing) — every zone emission would raise `ValueError` until this closes.
- Behavioral mismatches: `sync` emits no moments, records no `SyncDepOutcome`, has no crash
  wrapper, no `_sync_work` split; `status` emits no moments, derives no `DepDrift`, has no
  `_FILE_CHANGE` constant, no `_effective_config` helper, no `_status_work` split.
- Existing code that can be reused: `_effective_config` (sync — mirrored into status), the
  entire loop/filter structure of both operations (moved verbatim into the work helpers),
  `_check_dep`, `compute_dep_status`, the platform fixtures, the shared `tests/conftest.py`
  fixtures, the catalog pin test file.
- Test coverage gaps: no `tests/usages/hooks/` package; no `test_sync_moments.py`; no
  `test_status_moments.py`; catalog pins assert 20 records (stale the moment the records land).
- Missing visibility in workspace or git: the zone cell and the new practice file are untracked
  (new files) — normal for a feature branch; committing is outside this plan's scope.
- No `location` mismatches: every declared location is a file to create at exactly the
  contracted path (same directory level as its `CODEMANIFEST`).

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).

#### Package: `goga/hooks/catalog`

### Task 1: Grow the action catalog with the four usages records (TDD coding)

`declared_actions()` in `goga/hooks/catalog/catalog.py` is the single source of known
subscription addresses. The catalog CODEMANIFEST has appended four requirement bullets: records
`domain="usages"`, `name` ∈ {`sync_started`, `sync_completed`, `status_started`,
`status_completed`}, `error_class="soft"`. No signature change — additive data growth. The zone
cell (later tasks) emits these addresses; `emit_hook_event` resolves every emission against this
catalog, so an address the zone emits but the catalog misses is a runtime `ValueError` in every
usages flow. The catalog must grow FIRST — the design's implementation order step 1.

**Usages relevant to this task:**
- `convention`: Google docstrings, logging discipline, test naming (`test_<what>_<scenario>`),
  maintained-data tests are mock-free.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/hooks/catalog/test_catalog.py` update the existing pinning
  tests to the grown catalog — `test_schema_amend_cell_record_present`,
  `test_config_amend_config_record_present`,
  `test_declared_actions_carries_the_seven_topics_records`,
  `test_catalog_carries_the_three_pipeline_records`: `len(records) == 20` → `== 24` (and the two
  `len(pre_existing) + 1` assertions — the schema and config tests — gain the four usages triples
  in their `pre_existing` lists so the arithmetic stays honest); in
  `test_declared_actions_carries_the_seven_topics_records` also refresh the docstring's domain
  enumeration — it fixes the complete total as "1 config + 2 onboarding + 5 build + 3 pipeline +
  1 schema + 1 statuses + 7 topics" (= 20); the enumeration gains "+ 4 usages" (total 24) so the
  prose matches the updated assertion;
  `test_catalog_carries_the_five_build_records`: the frozen expected list gains the four
  `("usages", …, "soft")` triples at the end. Add the new test
  `test_declared_actions_carries_the_four_usages_records` to `TestDeclaredActions`:

  ```python
  usages = [(a.name, a.error_class) for a in declared_actions() if a.domain == "usages"]
  assert usages == [("status_completed", "soft"), ("status_started", "soft"),
                    ("sync_completed", "soft"), ("sync_started", "soft")]
  assert len(declared_actions()) == 24
  domains = [a.domain for a in declared_actions()]
  assert domains.index("topics") < domains.index("usages")   # the block sorts last
  ```

  (expected to fail at this stage — 20 ≠ 24)
- [ ] **Code**: append to `_DECLARED_ACTIONS` (after the schema record) in
  `goga/hooks/catalog/catalog.py`:

  ```python
  Action(domain="usages", name="sync_started", error_class="soft"),
  Action(domain="usages", name="sync_completed", error_class="soft"),
  Action(domain="usages", name="status_started", error_class="soft"),
  Action(domain="usages", name="status_completed", error_class="soft"),
  ```

  → the sort in `declared_actions()` places the block last; no other edit. No new imports.
- [ ] **Interface verification**: run `pytest tests/hooks/catalog/test_catalog.py -v` — all must
  pass (24 records, deterministic `(domain, name)` order, no duplicates, published records
  untouched)
- [ ] **Logic tests**: covered by the pin set — the catalog is maintained data with no
  behavioral logic; `test_declared_actions_is_deterministic_and_complete` and
  `test_declared_actions_records_are_well_formed` already pin the invariants and must stay green
- [ ] **Debugging**: run `pytest tests/hooks/ -q` — fix implementation code until all tests pass
  (do NOT fix test code)
- [ ] **Contract re-verification**: signature unchanged (`declared_actions() -> list[Action]`,
  no parameters); facade `goga.hooks.catalog` unchanged (`__all__ == ["Action",
  "declared_actions"]`); the four records present with `error_class="soft"`; total 24
- [ ] **Lint**: `ruff check goga/hooks/catalog/` — fix formatting if necessary

#### Package: `goga/usages/hooks` (new zone)

### Task 2: Zone test package scaffolding (infrastructure)

Create the `tests/usages/hooks/` package so the three zone test files (Tasks 3–5) and the facade
test (Task 6) have their convention-mandated home with the platform boundary fixtures in scope.
The `tests/pipeline/hooks/conftest.py` file is the exact precedent — a nested re-export of the
two fixtures `tests/usages/conftest.py` already re-exports.

**Usages relevant to this task:**
- `convention`: each test directory MUST contain an `__init__.py`; local fixtures live in
  `tests/<package>/conftest.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/usages/hooks/__init__.py` (empty package marker)
- [ ] Create `tests/usages/hooks/conftest.py` with the re-export chain (verbatim shape of
  `tests/pipeline/hooks/conftest.py`):

  ```python
  from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401
  ```

  with the same module docstring pattern (shared fixtures of the usages hooks zone tests — the
  platform boundary)
- [ ] Verify collection: `pytest tests/usages/ --collect-only -q` — the existing usages suites
  still collect and the new package imports cleanly (exit 0)
- [ ] Lint: `ruff check tests/usages/hooks/` — fix formatting if necessary

### Task 3: The eight fact entities — `facts.py` (TDD coding)

The zone's fact vocabulary: pure data, no behavior, no I/O. Module `goga/usages/hooks/facts.py`
(stdlib-only leaf — dataclasses + enum). Every entity is declared in
`goga/usages/hooks/CODEMANIFEST` with `location: facts.py`; the construction rules below are the
design's verified decisions. Note: until Task 6 creates `__init__.py`, `goga.usages.hooks`
behaves as a namespace package — import the modules directly
(`from goga.usages.hooks.facts import …`); the facade pin lands in Task 6.

**Usages relevant to this task:**
- `convention`: frozen `kw_only=True` dataclasses from the stdlib `dataclasses` module; enums as
  `enum.Enum`; `None` only for fields that represent the explicit absence of a value; relative
  imports; Google docstrings; tests mirror the source tree (`tests/usages/hooks/test_facts.py`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/usages/hooks/test_facts.py` with the facts half of the
  design's pin scenario `test_facts_are_frozen_kw_only_dataclasses_and_enums_are_pinned`
  (expected to fail at this stage — module missing):

  ```python
  moment = UsagesMoment(operation="sync", group=None, dep=None)
  assert moment.operation == "sync" and moment.group is None and moment.dep is None
  for cls in (UsagesMoment, SyncDepOutcome, FileChange, DepDrift):
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

  Use the `is_kw_only_dataclass` helper from `tests/conftest.py` for the kw_only arm (the
  catalog tests show the pattern). Sufficiency: the display strings are contractual (tools
  string-match verdicts); frozen kw_only is the `convention` data-model rule; the field sets pin
  the wire shape against accidental growth.
- [ ] **Code**: create `goga/usages/hooks/facts.py` with a module docstring documenting the file
  as the facts cell of the zone (the established per-module header pattern), then the eight
  entities with mandatory type hints and Google docstrings (property descriptions from the
  CODEMANIFEST are the doc content). Construction rules (verbatim from the design):

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

  Member values are the display strings the CODEMANIFEST properties declare (`out_of_date =
  "out of date"` mirrors `UsageState.out_of_date = "out of date"`). `message` defaults to `None`
  — the explicit absence of a failure fact. A `list` field on a frozen dataclass is
  shallow-immutable only — accepted (the `DepStatus.entries` precedent); the delivered views are
  write-protected by the platform proxy anyway.
- [ ] **Interface verification**: run `pytest tests/usages/hooks/test_facts.py -v` — all must
  pass
- [ ] **Logic tests**: the pin set IS the logic coverage for data-only entities (positive:
  construction and member values; negative: positional construction refusal, frozen assignment);
  no further behavioral logic exists — facts only
- [ ] **Debugging**: run `pytest tests/usages/hooks/ -q` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: every `facts.py` entity importable from
  `goga.usages.hooks.facts`; field sets and enum members exactly as pinned; no methods, no I/O,
  no config/git/file reads
- [ ] **Lint**: `ruff check goga/usages/hooks/ tests/usages/hooks/` — fix formatting if necessary

### Task 4: The four context entities — `contexts.py` (TDD coding)

The read-only views a subscribed hook receives: facts only, no methods. Module
`goga/usages/hooks/contexts.py`, importing `.facts` (relative). The invariants (`success` is
False whenever crashed, `reason` present exactly when crashed) are guaranteed by the emitting
operations, not enforced here — facts, not police (the zone contract's "pure facts" rule).

**Usages relevant to this task:**
- `convention`: frozen `kw_only` dataclasses; relative imports
  (`from .facts import Completion, DepDrift, SyncDepOutcome, SyncOutcome, UsagesMoment`);
  Google docstrings; tests in `tests/usages/hooks/test_contexts.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/usages/hooks/test_contexts.py` with the contexts half of
  the pin scenario (expected to fail at this stage):

  ```python
  for cls in (SyncStarted, StatusStarted, SyncCompleted, StatusCompleted):
      assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen
      with pytest.raises(TypeError): cls("x")            # positional construction refuses
  assert [f.name for f in dataclasses.fields(SyncStarted)] == ["moment", "force"]
  assert [f.name for f in dataclasses.fields(StatusStarted)] == ["moment"]
  assert [f.name for f in dataclasses.fields(SyncCompleted)] == ["moment", "deps", "success", "completion", "reason"]
  assert [f.name for f in dataclasses.fields(StatusCompleted)] == ["moment", "changed", "success", "completion", "reason"]
  assert SyncCompleted(moment=m, deps=[], success=True,
                       completion=Completion.finished).reason is None   # the None default
  ```

- [ ] **Code**: create `goga/usages/hooks/contexts.py` with the module docstring and the four
  frozen kw_only dataclasses (verbatim from the design):

  ```
  SyncStarted(moment: UsagesMoment, force: bool)
  StatusStarted(moment: UsagesMoment)
  SyncCompleted(moment: UsagesMoment, deps: list[SyncDepOutcome], success: bool,
                completion: Completion, reason: str|None = None)
  StatusCompleted(moment: UsagesMoment, changed: list[DepDrift], success: bool,
                  completion: Completion, reason: str|None = None)
  ```

  All four frozen kw_only dataclasses; `reason` defaults to `None`. Mandatory type hints;
  docstrings carry the CODEMANIFEST property descriptions.
- [ ] **Interface verification**: run `pytest tests/usages/hooks/test_contexts.py -v` — all must
  pass
- [ ] **Logic tests**: the pin set (positive construction + defaults; negative positional
  refusal) — the contexts carry no behavior by contract
- [ ] **Debugging**: run `pytest tests/usages/hooks/ -q` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the four contexts importable from
  `goga.usages.hooks.contexts`; read-only facts — no methods, no I/O
- [ ] **Lint**: `ruff check goga/usages/hooks/ tests/usages/hooks/` — fix formatting if necessary

### Task 5: The checkpoint surface `UsagesHooks` — `events.py` (TDD coding)

The four moment emissions over the platform facade. Module `goga/usages/hooks/events.py`.
Imports: `from ...hooks import HookRegistry, emit_hook_event` (three dots to the platform
facade) plus `.contexts` and `.facts`. Do NOT import `declared_actions` — the catalog resolution
named by the contract's algorithm step happens inside `emit_hook_event`; an unused import would
fail ruff.

**Usages relevant to this task:**
- `declaring-actions` (from `goga/hooks`): declare the action in the catalog (done in Task 1),
  own the context, emit via `emit_hook_event(HookRegistry(), domain, action, context_for=…)`;
  the platform carries enumeration, delivery, error classes, diagnostics.
- `registering-hooks` (from `goga/hooks`): the registration contract behind every moment —
  `register_hooks(hooks)` → `hooks.subscribe(domain, action, name, hook)`; the fixed offered
  parameter names (`context`, `self`); the failure ladder.
- `convention`: relative imports, Google docstrings with `Args`/`Raises`, tests in
  `tests/usages/hooks/test_events.py` with mocks only at the platform boundary fixtures.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/usages/hooks/test_events.py` pinning the surface shape
  (expected to fail at this stage): `UsagesHooks` is a class with exactly the four public emit
  methods, signatures matching the CODEMANIFEST —
  `emit_sync_started(moment: UsagesMoment, force: bool)`,
  `emit_sync_completed(moment: UsagesMoment, deps: list[SyncDepOutcome], success: bool,
  completion: Completion, reason: str | None = None)`,
  `emit_status_started(moment: UsagesMoment)`,
  `emit_status_completed(moment: UsagesMoment, changed: list[DepDrift], success: bool,
  completion: Completion, reason: str | None = None)` — none returns a value
- [ ] **Code**: implement `goga/usages/hooks/events.py` per the design's algorithm (verbatim):

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

  `context_for=lambda _tool: context` — the same instance is shared by every receiving tool:
  the facts are frozen and the delivery proxy closes writes, so sharing is safe and matches the
  pipeline-zone precedent. Verified platform behavior this relies on: `build_once` is idempotent
  (`state.py:54`); `wrap_context` closes writes (`delivery.py:60`); `build_hook_arguments`
  injects only the declared `context`/`self` names (`delivery.py:94`); a raising hook under a
  soft record warns and the sequence continues (`emit.py`).
- [ ] **Interface verification**: run `pytest tests/usages/hooks/test_events.py -v` — the
  contract-shape tests must pass
- [ ] **Logic tests**: add the design's three behavioral scenarios to
  `tests/usages/hooks/test_events.py` (verbatim specs):

  **`test_construction_enumerates_nothing_and_one_registry_serves_all_four_moments`** — Setup:
  `pin_package_environment({"goga_tool_rec": ["goga-tool-rec"]})` returning the boundary mock;
  `install_tool_package("goga_tool_rec", register_hooks=_register)` where `_register` subscribes
  one no-op hook to each of the four addresses and counts `register_hooks` invocations via a
  closure counter. Input: `hooks = UsagesHooks()`; then `hooks.emit_sync_started(m, False)`,
  `hooks.emit_sync_completed(m, [], True, Completion.finished)`, `hooks.emit_status_started(m)`,
  `hooks.emit_status_completed(m, [], True, Completion.finished)` with
  `m = UsagesMoment(operation="sync", group=None, dep=None)`. Assertions:

  ```python
  assert boundary.call_count == 0          # after construction alone
  … emit all four …
  assert boundary.call_count == 1
  assert register_hooks_calls == 1         # the callback ran exactly once
  ```

  Sufficiency: pins the zone's headline property — the emissions never multiply the package
  enumeration — and the cheap-construction requirement.

  **`test_emit_delivers_the_readonly_context_by_fixed_names`** — Setup: a fake tool subscribing
  `def record(context): captured.append(context)` to `usages/sync_started` and
  `def record_self(self, context): …` to `usages/sync_completed`; boundary pinned. Input:
  `emit_sync_started(m, force=True)`; `emit_sync_completed(m, [outcome], False,
  Completion.crashed, reason="boom")` where `outcome = SyncDepOutcome(group="libs", dep="click",
  outcome=SyncOutcome.failed, message="failed to sync usages for libs/click")`. Assertions:

  ```python
  assert captured[0].moment is m and captured[0].force is True
  assert captured[1].deps == [outcome] and captured[1].success is False
  assert captured[1].completion is Completion.crashed and captured[1].reason == "boom"
  with pytest.raises(AttributeError):
      captured[0].force = False        # the delivered view is read-only
  ```

  **`test_a_hook_receives_nothing_it_did_not_declare`** — Setup: a fake tool subscribing
  `def only_self(self): seen.append("called")` to `usages/status_started`. Input:
  `emit_status_started(m)`. Assertions: `seen == ["called"]` (no `TypeError` — the call injects
  only `self`). Sufficiency: the fixed offered-names injection is platform-guaranteed; the zone
  must not have broken it by its context shape.
- [ ] **Debugging**: run `pytest tests/usages/hooks/ -q` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: fire-and-forget (all four methods return `None`); cheap
  construction (no enumeration, no imports at construction); one registry per instance; every
  context built only from the caller's values — no config/git/file reads; a failing hook never
  surfaces to the caller (soft class warns inside `emit_hook_event`)
- [ ] **Lint**: `ruff check goga/usages/hooks/ tests/usages/hooks/` — fix formatting, apply
  decomposition if necessary

### Task 6: The zone facade — `__init__.py` (infrastructure)

The consumer entry point of the zone: a pure re-export assembling the thirteen contract names.
Importing the package enumerates nothing. After this task `goga.usages.hooks` becomes a regular
package (until now a namespace package) and every contract name is importable from it — the
`usages-moments.md` practice imports `UsagesHooks` from this facade.

**Usages relevant to this task:**
- `convention`: relative imports; facade exactness (`goga-cell-python`: `__init__.py` must
  expose the full contract API through `__all__` — only identifiers in `__all__` constitute the
  facade).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `goga/usages/hooks/__init__.py` with the module docstring and (verbatim from the
  design):

  ```python
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

- [ ] Create `tests/usages/hooks/test_facade.py` with the design's facade pin
  `test_zone_facade_exposes_the_thirteen_contract_names`:

  ```python
  import goga.usages.hooks as zone

  assert zone.__all__ == ["ChangeVerdict", "Completion", "DepDrift", "DriftVerdict",
                          "FileChange", "StatusCompleted", "StatusStarted", "SyncCompleted",
                          "SyncDepOutcome", "SyncOutcome", "SyncStarted", "UsagesHooks",
                          "UsagesMoment"]
  assert zone.UsagesHooks is not None and callable(zone.UsagesHooks)
  ```

  (each contract name resolves on the zone object — assert one name per name listed)
- [ ] Verify facade accessibility: `python -c "from goga.usages.hooks import UsagesHooks,
  UsagesMoment, SyncDepOutcome, DepDrift, Completion"` — exit 0
- [ ] Run the zone suites: `pytest tests/usages/hooks/ -v` — all pass
- [ ] Lint: `ruff check goga/usages/hooks/ tests/usages/hooks/` — fix formatting if necessary

#### Package: `goga/usages/sync`

### Task 7: The sync operation owns its moments — rework `sync.py` (TDD coding)

`goga/usages/sync/sync.py`: `sync` keeps its signature and gains the emission scaffold; the
per-dep work moves into a private `_sync_work` helper that mutates a caller-owned outcomes
accumulator (so partial facts survive a crash); a single `except Exception` wrapper around the
helper emits the crashed completion and re-raises. The CODEMANIFEST's renumbered algorithm
(steps 1–8 with outcome recording) is the contract; the design's algorithm below is the verified
implementation. The existing sync suites must stay green — the loop structure moves verbatim.

**Usages relevant to this task:**
- `usages-moments` (from `goga/usages/hooks`, path `goga/usages/hooks/.usages/usages-moments.md`):
  one `UsagesHooks` per run, resolve facts before delivery, emit around the operation, complete
  the crash path (`except Exception` → crashed emission → `raise`), no-op and abort semantics —
  the `_sync_work` split mirrors the practice's `run_sync_work` sketch verbatim in shape.
- `checkpoints` (from `goga/config/hooks`): the step-1 config-amendment delivery — unchanged
  (`_effective_config` stays as is).
- `registering-hooks` (from `goga/usages`, consumer practice): the events table and subscribe
  sketch the capturing fake tool in the tests imitates.
- `sync-usages` (from `goga/usages`): the documented consumer contract — unchanged by the
  moments.
- `git` (inline): `clone_repository` untouched; the moments add no git access.
- `click` (cook): the amendment summary lines stay on stderr — no new output channel.
- `convention`: relative imports, docstring standard, mocking at the import point.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/usages/sync/test_sync_moments.py`. Contract-first pins
  (expected to fail at this stage): `sync` signature unchanged
  (`sync(force: bool = False, group: str | None = None, dep: str | None = None) -> int`),
  still importable from `goga.usages.sync` and the `goga.usages` facade. Setup pattern per the
  design's General Setup: `_sync_mod = importlib.import_module("goga.usages.sync.sync")`;
  `mock.patch.object(_sync_mod, "clone_repository")` (the established pattern — the facade
  function shadows the submodule attribute); config via a `_write_config`-style helper writing a
  `.goga/config.yml` under `tmp_path` + `monkeypatch.chdir(tmp_path)` (or the shared
  `write_config` fixture from `tests/conftest.py`); capture channel = a fake tool package whose
  `register_hooks` subscribes closures appending the delivered `context` objects to a plain list
  owned by the test.
- [ ] **Code**: add the import
  `from ..hooks import Completion, SyncDepOutcome, SyncOutcome, UsagesHooks, UsagesMoment`
  (two dots) and restructure per the design's algorithm (verbatim):

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

  Binding decisions (fixed by the design — do not deviate):
  - The failed-outcome message is exactly
    `f"failed to sync usages for {group_name}/{dep_name}"` — the sentence shape of the sibling
    `DepStatus.error`, credential-free by construction (group/dep names only, no exception text,
    no URL). The existing `logger.error` call (with its credential-avoidance comment) stays
    unchanged.
  - The crash reason is `str(reason)` of the single `except Exception` wrapper — never
    `BaseException` (`KeyboardInterrupt` is not caught; no completion emission, matching the
    platform's own catch-`Exception` policy).
  - Exactly one finished-emission site and one crashed-emission site; the two finished returns
    (no-op, normal) cannot double-emit (single emission site after the helper).
  The docstring of `sync` gains the moment paragraphs (start after the effective configuration;
  completion on every return path; notification-only). `_sync_work` gets its own docstring
  noting the `outcomes` accumulator contract (partial facts survive a crash). The helper split
  is also the complexity-budget move — the orchestrator stays within the lint budget the way
  `_effective_config` already documents.
- [ ] **Interface verification**: run `pytest tests/usages/sync/test_sync.py
  tests/usages/sync/test_config_checkpoint.py -v` (existing suites) plus the signature pins in
  the new file — all must pass
- [ ] **Logic tests**: add the design's sync scenarios to `tests/usages/sync/test_sync_moments.py`
  (verbatim specs):

  **`test_sync_emits_both_moments_with_per_dep_outcomes`** — Setup: `tmp_path` cwd with a
  `.goga/config.yml` declaring `libs/click` (clone ok), `libs/common` (clone raises),
  `libs/skipped` (target dir pre-created); a fake tool capturing all `usages/*` contexts;
  `mock.patch.object(_sync_mod, "clone_repository")` with `side_effect` returning a tmp repo
  containing `.usages/conventions.md` for `click`/`skipped` and raising
  `RuntimeError("git failed https://user:tok@x/common.git")` for `common`. Input:
  `sync(force=False, group="libs", dep=None)`. Assertions:

  ```python
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

  **`test_sync_no_op_run_fires_both_moments_with_empty_outcomes`** — Setup: config with no
  `usages` section; capturing fake tool installed. Input: `sync()`. Assertions:

  ```python
  assert sync() == 0
  assert len(started) == 1 and len(completed) == 1
  assert completed[0].deps == [] and completed[0].success is True
  assert completed[0].completion is Completion.finished
  ```

  **`test_failing_hook_warns_and_the_operation_is_unaffected`** (negative) — Setup: a fake tool
  subscribing a raising hook (`def boom(context): raise RuntimeError("kaput")`) to
  `usages/sync_started` and a recording hook to `usages/sync_completed`; a one-dep config;
  `clone_repository` mocked ok; `caplog` at WARNING. Input: `sync()`. Assertions:

  ```python
  assert result == 0
  assert any("usages.sync_started" in r.message and "kaput" in r.message for r in caplog.records)
  assert len(completed) == 1            # the run reached its completion
  ```

  **`test_config_boundary_abort_fires_no_usages_moment`** (negative) — Setup: `tmp_path` cwd
  with NO `.goga/config.yml`; capturing fake tool installed. Input: `sync()` (expect
  `FileNotFoundError`). Assertions:

  ```python
  with pytest.raises(FileNotFoundError): sync()
  assert captured == []
  ```

  **`test_sync_crash_path_emits_the_crashed_completion_and_reraises`** (edge) — Setup: one-dep
  config; capturing tool; `mock.patch.object(_sync_mod, "clean_usages_dir",
  side_effect=RuntimeError("boom"))` (crash injection at `clean_usages_dir` — called outside the
  absorbing per-dep try). Input: `sync(force=True)`. Assertions:

  ```python
  with pytest.raises(RuntimeError, match="boom"): sync(force=True)
  assert completed[0].completion is Completion.crashed
  assert completed[0].success is False and completed[0].reason == "boom"
  assert completed[0].deps == []
  ```

  **`test_filtered_deps_are_absent_from_every_fact`** (edge) — Setup: the multi-group config
  (`libs.click`, `libs.common`, `apps.common`); capturing tool; `clone_repository` mocked ok.
  Input: `sync(dep="common")`. Assertions:

  ```python
  outcomes = [(o.group, o.dep) for o in completed[0].deps]
  assert outcomes == [("apps", "common"), ("libs", "common")]   # click absent, insertion order
  assert started[0].moment.dep == "common"                       # the envelope mirrors the filters
  ```
- [ ] **Debugging**: run `pytest tests/usages/sync/ -q` — fix implementation code until all
  tests pass, old and new (do NOT fix test code)
- [ ] **Contract re-verification**: the CODEMANIFEST algorithm steps 1–8 all realized — start
  after the effective configuration (step 2), the no-op return emits the completion with the
  empty outcome set (step 3), one `SyncDepOutcome` per matched dep (steps 6.2–6.4), completion
  on every return path (step 7), exit-code semantics unchanged (step 8); the moments alter
  nothing — output, exit codes, and best-effort per-dep isolation are unchanged under any
  subscription state
- [ ] **Lint**: `ruff check goga/usages/sync/ tests/usages/sync/` — fix formatting, apply
  decomposition if necessary

#### Package: `goga/usages/status`

### Task 8: The status operation owns its moments and the drift projection — rework `status.py` (TDD coding)

`goga/usages/status/status.py`: extract `_effective_config` (the exact body `sync.py` already
has), split the work into `_status_work` (mutating a caller-owned `changed` accumulator), add
the `_derive_drift` projection with the module constant `_FILE_CHANGE`, and wrap the helper in
the crash path. Signature unchanged; the report shape unchanged; the INFO lifecycle logs keep
their exact current placement (inside the work helper, around the loop, after the empty-section
check). The existing status suites must stay green.

**Usages relevant to this task:**
- `usages-moments` (from `goga/usages/hooks`): same delivery practice as sync — one
  `UsagesHooks` per run, emit around the check, complete the crash path.
- `checkpoints` (from `goga/config/hooks`): the step-1 config-amendment delivery — the body
  moves verbatim from the current inline code into `_effective_config`.
- `registering-hooks` (from `goga/usages`, consumer practice): the events table the capturing
  fake tool imitates.
- `usages-status` (from `goga/usages`): the documented consumer contract — unchanged by the
  moments.
- `click` (cook): amendment summary lines stay on stderr; the report is still not printed here.
- `convention`: relative imports, frozen dataclass facts, mocking at the import point.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/usages/status/test_status_moments.py`. Contract-first
  pins (expected to fail at this stage): `status` signature unchanged
  (`status(group: str | None = None, dep: str | None = None) -> UsageStatusReport`), still
  importable from `goga.usages.status` and the `goga.usages` facade. Setup pattern:
  `_status_mod = importlib.import_module("goga.usages.status.status")`;
  `mock.patch.object(_status_mod, "compute_dep_status")`; capturing fake tool as in Task 7.
- [ ] **Code**: add the import
  `from ..hooks import (ChangeVerdict, Completion, DepDrift, DriftVerdict, FileChange,
  UsagesHooks, UsagesMoment)` (`EntryKind` is already present in the existing `models` import —
  re-exported today; the projection filter uses it as-is) and restructure per the design's
  algorithm (verbatim):

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

  Verified projection properties (from the design's checkpoint): directory nodes dropped
  (`kind is dir` filtered), unchanged files dropped (not a key of `_FILE_CHANGE`), path-sorted
  order preserved (filtering a sorted list keeps it sorted — `_diff_entries` sorts at
  `compare.py:166`), and an out-of-date dep always yields ≥ 1 file change (differing hash maps
  imply at least one non-unchanged file). The error arm reuses the exact credential-free
  `DepStatus.error` (`"failed to check usages status for {group}/{dep}"`). The in-document
  models (`DepStatus` et al.) stay defined in `models.py` and re-exported — untouched; `__all__`
  of `status.py` unchanged. The crash reason is `str(reason)`; never `BaseException`. Exactly
  one finished-emission site and one crashed-emission site.
- [ ] **Interface verification**: run `pytest tests/usages/status/test_status.py
  tests/usages/status/test_config_checkpoint.py -v` (existing suites) plus the signature pins in
  the new file — all must pass
- [ ] **Logic tests**: add the design's status scenarios to
  `tests/usages/status/test_status_moments.py` (verbatim specs):

  **`test_status_emits_the_changed_set_with_the_file_projection`** — Setup: `tmp_path` cwd with
  a config declaring `libs/click`; the local target `.goga/usages/libs/click/` populated;
  `mock.patch.object(_status_mod, "compute_dep_status")` returning
  `DepStatus(group="libs", dep="click", state=UsageState.out_of_date, entries=[
  EntryStatus(path="b.md", kind=EntryKind.file, change=EntryChange.unchanged),
  EntryStatus(path="c.md", kind=EntryKind.file, change=EntryChange.removed),
  EntryStatus(path="docs", kind=EntryKind.dir, change=EntryChange.modified),
  EntryStatus(path="docs/a.md", kind=EntryKind.file, change=EntryChange.added)])`; capturing
  fake tool. Input: `status(group="libs")`. Assertions:

  ```python
  started[0].moment.operation == "status"
  completed[0].changed == [DepDrift(group="libs", dep="click", verdict=DriftVerdict.out_of_date,
                                    changes=[FileChange(path="c.md", change=ChangeVerdict.removed),
                                             FileChange(path="docs/a.md", change=ChangeVerdict.added)])]
  assert completed[0].success is False
  assert report.deps[0].state is UsageState.out_of_date     # the report is unchanged in shape
  ```

  Sufficiency: the projection is the riskiest new logic — files only, directories dropped,
  unchanged dropped, verdict mapping, sorted order preserved — pinned with one exhaustive
  expected value.

  **`test_status_up_to_date_run_has_an_empty_changed_set_and_success`** — Setup: as above but
  `compute_dep_status` returns state `up_to_date` (entries populated with unchanged files).
  Input: `status()`. Assertions: `completed[0].changed == []` and `completed[0].success is True`
  and `report.exit_code == 0`.

  **`test_status_new_dep_lands_in_the_changed_set_with_the_empty_change_list`** — Setup:
  `tmp_path` cwd with a config declaring `libs/click`; the local target
  `.goga/usages/libs/click/` absent (never synchronized); capturing fake tool installed. NO
  git-boundary mock — `_check_dep` returns the `new` state before `compute_dep_status` is ever
  reached. Input: `status()`. Assertions:

  ```python
  assert completed[0].changed == [DepDrift(group="libs", dep="click",
                                           verdict=DriftVerdict.new, changes=[])]
  assert completed[0].changed[0].message is None
  assert completed[0].success is False
  assert report.deps[0].state is UsageState.new and report.exit_code == 1
  assert completed[0].completion is Completion.finished
  ```

  **`test_status_error_dep_lands_in_the_changed_set_with_its_message`** (negative) — Setup:
  one-dep config; `compute_dep_status` mocked to raise; capturing tool. Input: `status()`.
  Assertions:

  ```python
  assert completed[0].changed[0].verdict is DriftVerdict.error
  assert completed[0].changed[0].changes == []
  assert completed[0].changed[0].message == "failed to check usages status for libs/click"
  assert completed[0].completion is Completion.finished      # best-effort, not a crash
  assert result.exit_code == 1
  ```

  **`test_status_crash_path_carries_the_partial_changed_set`** (edge) — Setup: two-dep config
  (`libs/click`, `libs/common`); capturing tool;
  `mock.patch.object(_status_mod, "_check_dep", side_effect=[out_of_date_depstatus,
  RuntimeError("boom")])` where `out_of_date_depstatus` is a real `DepStatus` (`libs/click`,
  `out_of_date`, one modified-file entry) — the crash must be injected OUTSIDE `_check_dep`'s
  own absorption: a raise of `compute_dep_status` is absorbed by `_check_dep`'s `except
  Exception` into an error dep (the best-effort path, never a crash), so the injection point is
  `_check_dep` (or `_derive_drift`), never `compute_dep_status`. Input: `status()`. Assertions:

  ```python
  with pytest.raises(RuntimeError, match="boom"): status()
  assert completed[0].completion is Completion.crashed and completed[0].reason == "boom"
  assert completed[0].success is False
  assert completed[0].changed == [DepDrift(group="libs", dep="click",
                                          verdict=DriftVerdict.out_of_date, changes=[…])]
  ```

  (Variant with dep#1 up to date asserts `changed == []` — the empty partial set.)
- [ ] **Debugging**: run `pytest tests/usages/status/ -q` — fix implementation code until all
  tests pass, old and new (do NOT fix test code)
- [ ] **Contract re-verification**: the CODEMANIFEST algorithm steps 1–7 all realized — start
  after the effective configuration, the None-or-empty return through the same single
  finished-emission site, one `DepDrift` per non-up-to-date matched dep (steps 4.1–4.3), the
  report assembled verbatim (step 5), `success` ⇔ empty changed set ⇔ `report.exit_code == 0`
  (verified against `UsageStatusReport.exit_code` in `models.py:124`); read-only — no new writes
  anywhere in the flow
- [ ] **Lint**: `ruff check goga/usages/status/ tests/usages/status/` — fix formatting, apply
  decomposition if necessary

#### Package: usages domain — cross-operation

### Task 9: Integration tests — cross-operation moment scenarios (integration tests)

Cross-entity scenarios spanning both reworked operations and the zone: the inert-environment
guarantee and the None-vs-`{}` boundary. These extend the existing usages cross-entity
integration file `tests/usages/test_integration.py` (the established home for multi-operation
usages tests; its `TestSyncIntegration` class shows the fixture usage — `make_repo`,
`write_config`, `patch_clone` from `tests/conftest.py`). The boundary fixtures come from the
`tests/usages/conftest.py` re-export.

**Usages relevant to this task:**
- `usages-moments` (from `goga/usages/hooks`): the no-op and inert-environment semantics these
  scenarios pin.
- `registering-hooks` (from `goga/usages`): the consumer practice whose inert/no-subscription
  behavior is verified here.
- `convention`: integration tests for module interaction; mocks only at the boundaries shown.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create the new test class (e.g. `TestMomentsIntegration`) in
  `tests/usages/test_integration.py`
- [ ] Test cross-operation interaction: `test_no_tool_packages_keep_the_surface_inert` — Setup:
  `pin_package_environment({})`; one-dep config; `clone_repository` mocked ok. Input: `sync()`;
  `status()` (with `compute_dep_status` mocked up-to-date). Assertions:

  ```python
  assert sync() == 0 and (Path(".goga/usages/libs/click")).exists()
  assert status().exit_code == 0
  # no moment code path raised, no extra output: capsys stdout unchanged vs. the classic shape
  ```

  Sufficiency: "with no tool packages installed the whole surface is inert — both commands
  behave as if the zone did not exist".
- [ ] Test edge case: `test_empty_usages_section_fires_both_moments_and_force_still_cleans` —
  Setup: `tmp_path` cwd with a config whose `usages` section is present but empty (`usages: {}`);
  a stale directory `.goga/usages/libs/stale/` pre-created; capturing fake tool installed;
  `clean_usages_dir` NOT mocked. Input: `sync(force=True)`, then `status()`. Assertions
  (captured contexts filtered by `moment.operation`, as in the neighboring tests):

  ```python
  assert sync(force=True) == 0
  assert not Path(".goga/usages/libs/stale").exists()    # the clean ran — {} ≠ None
  assert sync_completed.deps == [] and sync_completed.success is True
  assert status().exit_code == 0
  assert status_completed.changed == [] and status_completed.success is True
  ```

  Sufficiency: pins the None-vs-{} distinction the design's edge-case analysis relies on — only
  `None` short-circuits before the force clean; an empty section still cleans, and in both cases
  both moments fire with the empty fact set (the status contract's "None or empty" wording).
- [ ] Run validation: `pytest tests/usages/ -q` — the whole usages tree passes (moments,
  integration, and the pre-existing suites)

---

## Validation Commands

- `pytest tests/hooks/catalog/ tests/usages/ -v`: Run the touched suites (catalog pins, zone,
  sync, status, integration)
- `pytest tests/ -x`: Run all tests (full suite green — existing suites stay green)
- `ruff check goga/ tests/`: Lint check (source and tests)
- `goga lint`: Cell/contract lint — must remain 82 cells, 0 errors
- `python -c "from goga.usages.hooks import UsagesHooks, UsagesMoment, SyncDepOutcome, DepDrift, Completion"`: Facade check — the zone facade exposes the contract names

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`facts.py`,
  `contexts.py`, `events.py` for the zone; `catalog.py`, `sync.py`, `status.py` changed in place)
- [ ] Every contract entity is accessible from the facade (`goga.usages.hooks.__all__` exposes
  exactly the thirteen names; `goga.hooks.catalog` and the two operation facades unchanged)
- [ ] Properties and methods match the declared API (field sets, enum members, the four emit
  signatures)
- [ ] Descriptions are reflected in behavior (moment semantics, credential-free messages,
  crash-path guarantees, the files-only projection)
- [ ] Contract dependencies are met (the zone imports only `goga/hooks`; the operations import
  only `goga/usages/hooks` — no cross-imports)
- [ ] The Python facade obligation is satisfied (all thirteen names importable from
  `goga.usages.hooks`)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification →
  logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them (Task 9)
- [ ] No package boundary was expanded (no new cells beyond the contracted zone; no changes to
  `goga/usages/__init__.py`, `goga/commands/usages/usages.py`, `clean.py`/`clone.py`/
  `deploy.py`, `compare.py`/`models.py`, docs, or practice files)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `click`, `git`,
  `checkpoints`, `usages-moments`, `declaring-actions`, `registering-hooks` ×2, `sync-usages`,
  `usages-status`)
