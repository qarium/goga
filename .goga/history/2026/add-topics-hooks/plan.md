# Plan: `add-topics-hooks`

Result of compiling the design document
`.goga/history/2026/add-topics-hooks/design.md` into ralphex execution
tasks. The CODEMANIFEST changes are already materialized in the working
tree — this plan implements the code against them.

---

## Purpose

Implement the seven platform hook actions of the topics lifecycle: five
post-fact notifications over the plain emission and two pre-fixation
amendments over a per-hook staged delivery, plus the home-path identity
and the no-read contexts.

After implementation:

- `goga/hooks/catalog` declares the seven topics records (all soft) —
  every checkpoint address resolves.
- The new cell `goga/topics/hooks` provides the eleven contract types
  (`TopicIdentity`, five contexts, two draft holders, two amendment
  views, `TopicHooks`) behind its facade, sharing one lazily-built
  `HookRegistry` per run.
- The six domain routines of `goga/topics` (`enter_topic_todo`,
  `create_topic`, `publish_topic`, `switch_topic`, `ensure_topic`,
  `delete_topics`) fire their checkpoints at the specified moments with
  facts from the operation's own data; public signatures, result lines,
  error surface, and mutation order are unchanged (one documented
  exception: the empty-template normalization on the delegated
  publication path).
- Docs describe the seven actions; all tests, lint, and the goga
  validations pass.

The most important gaps between contract and code: the zone directory
holds only `CODEMANIFEST` (no Python at all), the catalog constant
carries 3 of 10 records, `enter_topic_todo` lacks the `branch`
parameter, and no domain routine fires anything.

Strategy: bottom-up by cell — catalog data first (addresses must exist
before any checkpoint fires), then the zone (identity → contexts →
amendments → events → facade), then the domain wiring in the design's
routine order, then docs and the cross-cell validation. Every coding
task follows the TDD workflow.

## Context

### Contract Surface

All three `CODEMANIFEST` files are **read-only** for the implementation
agent. Where this plan and a manifest disagree, the manifest wins — fix
the code, never the contract.

#### Cell: `goga/hooks/catalog` (changed — data extension)

**Entity: `declared_actions() -> actions: list[Action]`**
- Type: function (Routine)
- Declared `location`: `catalog.py` (existing file
  `goga/hooks/catalog/catalog.py`)
- Facade obligation: importable from `goga/hooks` (already re-exported —
  no facade change in this plan)
- Behavioral change: the runtime constant `_DECLARED_ACTIONS` gains the
  seven topics records — `topic_created`, `topic_published`,
  `topic_switched`, `topic_todo_entered`, `topic_deleted`,
  `amend_creation`, `amend_todo_entry` (all `domain="topics"`,
  `error_class="soft"`). The routine itself (the `sorted()` by
  `(domain, name)`) is unchanged. Total: 10 records (3 existing + 7
  topics).
- Semantic requirements: deterministic and complete on every call;
  published records are never rewritten; the catalog is maintained data,
  not discovery (do not derive records from installed packages).
- `Action` (the frozen kw-only record dataclass) is unchanged.

#### Cell: `goga/topics/hooks` (created — all new code)

The directory currently holds only `CODEMANIFEST` and
`.usages/checkpoints.md`. Every entity below is new Python; the facade
`__init__.py` must expose exactly the eleven names through `__all__`
(alphabetical).

**Entity: `TopicIdentity(slug: str | None, year: str, branch: str | None)`**
- Type: class (Entity) — `@dataclass(frozen=True, kw_only=True)`
- Declared `location`: `identity.py`
- Facade obligation: importable from `goga/topics/hooks`
- Properties: `slug -> str | None` (normalized slug; None in the
  branch-only form), `home_path -> str | None`
  (`.goga/history/<year>/<slug>` posix string via `resolve_topic_dir`;
  None when slug is None; pure composition — nothing read or created),
  `branch -> str | None` (branch as entered; None only in the deletion
  context)
- Imported dependencies: `resolve_topic_dir` from `goga/history`
- Key requirement: pure composition — no repository reads, nothing
  created

**Entity: `TopicCreated(identity: TopicIdentity, checked_out: bool, published: bool, todo: str | None, commit_message: str | None, commit_hash: str | None)`**
- Type: class (Entity) — `@dataclass(frozen=True, kw_only=True)`
- Declared `location`: `contexts.py`
- Facade obligation: importable from `goga/topics/hooks`
- Properties: the six signature fields, plain data reads
- Key requirements: read-only facts of a completed creation;
  `commit_message`/`commit_hash` present exactly when the path builds a
  commit

**Entity: `TopicPublished(identity: TopicIdentity, commit_message: str, commit_hash: str, todo: str)`**
- Type: class (Entity) — `@dataclass(frozen=True, kw_only=True)`
- Declared `location`: `contexts.py`
- Properties: the four signature fields. Read-only facts of one
  successful publication push.

**Entity: `TopicSwitched(identity: TopicIdentity, outcome: str)`**
- Type: class (Entity) — `@dataclass(frozen=True, kw_only=True)`
- Declared `location`: `contexts.py`
- Properties: `identity`, `outcome`. The outcome is exactly one of
  `local-checkout`, `created-from-remote`, `already-on-branch` — fixed
  by construction of the emitting routine.

**Entity: `TopicTodoEntered(identity: TopicIdentity, text: str)`**
- Type: class (Entity) — `@dataclass(frozen=True, kw_only=True)`
- Declared `location`: `contexts.py`
- Properties: `identity`, `text` (the final written text — after every
  amendment). No prior text is carried.

**Entity: `TopicDeleted(identity: TopicIdentity, local_branch: str | None, origin_twin: str | None, directory_removed: bool)`**
- Type: class (Entity) — `@dataclass(frozen=True, kw_only=True)`
- Declared `location`: `contexts.py`
- Properties: the four signature fields. No deleted-commit hash is
  carried; the identity carries no branch fact.

**Entity: `CreationDraft(commit_message: str | None, todo: str | None)`**
- Type: class (Entity) — `@dataclass(kw_only=True)`, **mutable** (the
  `StatusRegistry` precedent)
- Declared `location`: `amendments.py`
- Properties: `commit_message -> str | None`, `todo -> str | None` (live
  fields)
- Key requirement: the content changes only through the delivery commit
  of the amendment checkpoint — never through a delivered view

**Entity: `TodoEntryDraft(text: str)`**
- Type: class (Entity) — `@dataclass(kw_only=True)`, **mutable**
- Declared `location`: `amendments.py`
- Property: `text -> str` (live field). Same single-mutation-point rule.

**Entity: `CreationAmendment(identity: TopicIdentity, checked_out: bool, published: bool, draft: CreationDraft)`**
- Type: class (Entity) — `@dataclass(kw_only=True)`, mutable view
- Declared `location`: `amendments.py`
- Properties: `identity`, `checked_out`, `published`, and the read-through
  `commit_message -> str | None`, `todo -> str | None` (they read the
  live holder — a later hook sees the committed amendments of the earlier
  hooks)
- Method: `amend(commit_message: str | None, todo: str | None)` — buffer
  one amendment replacing the full draft content; buffers into this
  hook's buffer alone; whole replacement (a field left out returns as
  None); never cancels/redirects/defers the operation
- Datamodel decision (from the design review): the holder is stored
  under the private field `_draft` (the walk in `events.py` is the sole
  constructor caller — the kw name is an internal wiring detail; the
  CODEMANIFEST signature documents the input semantically), plus a
  private `_buffered` field (`init=False, repr=False`, default `None`).
  The holder is never a public attribute of a delivered view.

**Entity: `TodoEntryAmendment(identity: TopicIdentity, draft: TodoEntryDraft)`**
- Type: class (Entity) — `@dataclass(kw_only=True)`, mutable view
- Declared `location`: `amendments.py`
- Properties: `identity`, and the read-through `text -> str`
- Method: `amend(text: str)` — buffer one amendment replacing the full
  text; same isolation rules

**Entity: `TopicHooks()`**
- Type: class (Entity) — cheap construction, no state
- Declared `location`: `events.py`
- Facade obligation: importable from `goga/topics/hooks`
- Methods:
  - `amend_creation(identity, checked_out, published, commit_message, todo) -> draft: CreationDraft` — the per-hook staged walk (full algorithm in Task 6)
  - `amend_todo_entry(identity, text) -> draft: TodoEntryDraft` — the same walk over the single text field
  - `emit_created(identity, checked_out, published, todo, commit_message, commit_hash)` — fire-and-forget
  - `emit_published(identity, commit_message, commit_hash, todo)` — fire-and-forget
  - `emit_switched(identity, outcome)` — fire-and-forget
  - `emit_todo_entered(identity, text)` — fire-and-forget
  - `emit_deleted(identity, local_branch, origin_twin, directory_removed)` — fire-and-forget
- Key requirements: no enumeration and no imports at construction; one
  `HookRegistry` per run carries every checkpoint (the transport — the
  module-level `_RUN_REGISTRY` with a lazy `_run_registry()` builder —
  is an implementation detail the design fixes as decision D1); every
  context and draft is built from caller values — no repository reads
- Imported dependencies: `HookRegistry`, `emit_hook_event`,
  `wrap_context`, `build_hook_arguments`, `declared_actions` from the
  `goga/hooks` facade; `resolve_topic_dir` from `goga/history`
  (identity.py only)

#### Cell: `goga/topics` (changed — checkpoint wiring in six routines)

All six keep their public signatures (one addition: `enter_topic_todo`
gains `branch: str | None = None`), result lines, error surface, and
mutation order. The emissions are additive wiring. The cell imports the
zone via the relative `from .hooks import ...`.

**Entity: `enter_topic_todo(topic, year=None, branch=None) -> written: bool`** — `creation.py`. The saved text passes through `amend_todo_entry` before the write; a completed entry emits `topic_todo_entered`; the write is the last mutation.

**Entity: `create_topic(branch_name, base_ref, todo=None, publish=False, commit_message=None, year=None, switch=False) -> result: str`** — `creation.py`. Step 6 delivers `amend_creation` immediately before the first mutation of the chosen path; the no-switch path captures the planted commit hash and emits `topic_created`; the switch path emits after its last mutation; the publication path delegates with the amended values.

**Entity: `publish_topic(branch_name, todo, base_ref, commit_message=None, year=None) -> result: str`** — `publishing.py`. Captures the publication commit hash; after the successful push emits `topic_created` then `topic_published`; a rolled-back publication fires nothing; a direct call publishes without `amend_creation`.

**Entity: `switch_topic(identifier, todo=False, year=None) -> result: str`** — `switching.py`. Emits `topic_switched` on every completed switch with the outcome kind; the todo entry receives the switched branch as the branch fact.

**Entity: `ensure_topic(identifier, todo=False, year=None) -> result: str`** — `ensuring.py`. The fast creation delivers the identity-only `amend_creation` immediately before its first mutation and emits `topic_created` after the creation completes; the todo entries pass the operation's branch fact.

**Entity: `delete_topics(targets, year=None) -> result: str`** — `deletion.py`. Emits `topic_deleted` after each target's full removal with the removal composition.

Unchanged entities of `goga/topics` (`BoardRecord`, `collect_topic_board`, `SwitchCandidate`, `resolve_switch_candidates`, `check_branch_occupancy`, `check_slug_occupancy`, `DeleteTarget`, `resolve_delete_targets`) are not touched.

### Re-exports

No DSL re-export blocks (`->Name: {}`) exist in any of the three
manifests. Facade obligations are language-level: the zone
`__init__.py` must list the eleven names in `__all__`; the `goga/hooks`
facade already re-exports `declared_actions`; the `goga/topics` facade
already re-exports the six routines (signature of `enter_topic_todo`
grows the parameter — no facade change).

### Usages Context

- **`convention`** (`.goga/usages/conventions.md` — connected by both
  changed cells and the zone): the project's mandatory Python rules —
  relative imports, kw-only dataclasses, Google docstrings mirroring the
  manifest annotations, logging, test structure, mock boundaries,
  validation commands. Relevant to every task.
- **`click`** (`.goga/usages/cooks/click.md` — connected by
  `goga/topics`): the interactive moments of the domain — the numbered
  candidate selection, the publication ask, the non-interactive
  detection with its clean error. Relevant to the domain wiring tasks.
- **`editor-entry`** (imported from `goga/topics/editor`): the editor
  session patterns (`edit_text` — blank/unchanged save returns None).
  Relevant to the `enter_topic_todo` / `create_topic` tasks.
- **`topic-statuses`** (imported from `goga/history`): the status scale
  patterns — used only by the board, which this plan does not touch.
  Listed for completeness; no task applies it.

### Imported Usages

- **`declaring-actions`** from `goga/hooks` —
  `goga/hooks/.usages/declaring-actions.md`: the domain-maintainer side
  of opening an action — catalog record, context contract, emission at
  the checkpoint; the same context instance is returned to share per
  tool. Applied by the five `emit_*` methods (Task 6) and reflected in
  the catalog task (Task 1).
- **`per-tool-delivery`** from `goga/hooks` —
  `goga/hooks/.usages/per-tool-delivery.md`: the staged per-tool
  delivery loop skeleton — registry build once, subscriptions in
  enumeration order, wrap/project/call, commit only after success. The
  zone manifest declares one refinement: **the commit granularity is the
  single hook, not the tool** — a fresh view per subscription, the
  commit decided per subscription, so two hooks of one tool never share
  a buffer or a failure. Applied by `amend_creation` /
  `amend_todo_entry` (Task 6).
- **`registering-hooks`** from `goga/hooks` —
  `goga/hooks/.usages/registering-hooks.md`: the tool-author
  registration contract — the hook signature (`context`/`self` offered
  names) and the failure behavior behind every checkpoint. Applied by
  the amendment views (Task 5) and the walks (Task 6).
- **`topic-paths`** from `goga/history` —
  `goga/history/.usages/topic-paths.md`: the topic directory composition
  contract of `resolve_topic_dir`. Applied by `TopicIdentity.home_path`
  (Task 3); also the consumer patterns of the history facade used by the
  domain tasks.
- **`checkpoints`** from `goga/topics/hooks` —
  `goga/topics/hooks/.usages/checkpoints.md`: the consumer practice of
  the zone — one `TopicHooks` object per command, amend before
  fixation, emit after the moment, facts from the operation's own data.
  The binding practice for every checkpoint call site (Tasks 7–12).

### Local Usages

- `goga/topics/hooks/.usages/checkpoints.md` — functional category: the
  checkpoint surface for domain-flow consumers. Status: **already
  created** (with the manifest; the D8 advisory-amendment clause added
  during design review). Related entities: `TopicHooks`,
  `TopicIdentity`. No creation task needed — the file is current; Tasks
  7–12 apply it.
- `goga/topics/.usages/todo-entry.md` — one clause added (the written
  content is the final amended text). Status: **already updated** in the
  working tree. No task needed.
- `goga/topics/.usages/creating.md` — one clause added (todo.md content
  and commit message are the final amended values). Status: **already
  updated** in the working tree. No task needed.
- The design plans no other `.usages/` changes (optional one-line
  clauses for `switching`/`deleting`/`ensuring` are explicitly not
  required by the contract — do not add them).

### External Dependencies

- The hooks platform (`goga/hooks` facade: `HookRegistry`,
  `emit_hook_event`, `wrap_context`, `build_hook_arguments`,
  `declared_actions`) — consumed as-is, never modified.
- `goga/history` facade (`resolve_topic_dir`,
  `normalize_topic_dir`-family, `remove_topic_dir`, ...) — consumed
  as-is.
- The nested `goga/topics/git` and `goga/topics/editor` cells — consumed
  as-is.
- Tools: `pytest` (with `pytest-cov`), `ruff`, and the `goga` CLI
  (`goga lint`, `goga schema`, `goga hooks`). Python 3.10+;
  `T | None` union syntax is the project norm.

### Entity Interaction and Data Flow

Verbatim from the design document:

```
                          goga/commands (unchanged CLI + pipeline)
                                │  create_topic / switch_topic / ensure_topic /
                                │  publish_topic / delete_topics / enter_topic_todo
                                ▼
                       ┌───────────────────────┐
                       │      goga/topics      │  domain flows (six routines fire
                       │  creation / switching │  checkpoints at their moments)
                       │  publishing / ensuring│──── TopicHooks.amend_*  (pre-fixation)
                       │  deletion             │──── TopicHooks.emit_*   (post-moment)
                       └──────────┬────────────┘
                                  │ from .hooks (relative import)
                                  ▼
                       ┌──────────────────────────────┐
                       │      goga/topics/hooks      │  the hooks zone
                       │  identity.py   TopicIdentity│◀── resolve_topic_dir (goga/history)
                       │  contexts.py   5 contexts   │
                       │  amendments.py drafts+views │
                       │  events.py     TopicHooks + │
                       │                _RUN_REGISTRY│◀── HookRegistry, emit_hook_event,
                       └──────────┬───────────────────┘    wrap_context, build_hook_arguments,
                                  │                         declared_actions (goga/hooks facade)
                                  ▼
                       ┌──────────────────────────────┐
                       │       goga/hooks (platform) │  catalog.py (+7 records),
                       │  catalog / registry /        │  registry, dispatch — unchanged code
                       │  dispatch / tools            │
                       └──────────────────────────────┘
```

**Amendment flow (pre-fixation)** — e.g. `create_topic` step 6:

1. The domain routine composes `TopicIdentity(slug, year, branch)` from
   its own data (no repository reads) and calls
   `TopicHooks().amend_creation(identity, checked_out, published, draft_message, draft_todo)`.
2. `events.py` obtains the shared run registry (`_run_registry()` —
   built once per process run), resolves
   `Action("topics", "amend_creation", "soft")` against `declared_actions()`.
3. A `CreationDraft` holder is created with the draft values.
4. Per subscription of the address, in enumeration order: a fresh
   `CreationAmendment` view over the live holder is wrapped by
   `wrap_context`, projected by `build_hook_arguments` with the tool's
   `self_context`, and called.
5. A returned hook's buffer replaces the holder content (whole
   replacement); a raised hook or an empty/whitespace buffer field is a
   warning (`hook <name> of tool <tool> failed on topics.amend_creation:
   <reason>`) and the walk continues.
6. The holder returns to the domain, which reads the final
   `commit_message`/`todo` and fixes them into the artifacts (commit
   build / delegation / file write).

**Notification flow (post-moment)** — e.g. `publish_topic` step 9:

1. The routine composes `TopicIdentity` and the final facts (applied
   message, captured commit hash, final todo).
2. `TopicHooks().emit_created(...)` builds the frozen `TopicCreated`
   context and calls
   `emit_hook_event(_run_registry(), "topics", "topic_created", context_for)`.
3. `emit_hook_event` (platform, unchanged) builds the registry once,
   resolves the address, and delivers the **same context instance** to
   every subscribed hook through the per-tool delivery proxy; a failing
   hook of the soft action is a warning and the command continues.

**Catalog flow**: `declared_actions()` gains the seven records; the
`goga hooks` inspection command and the address resolution of every
checkpoint read the same list — no command change.

**Entity dependencies** (no cycles): `goga/hooks/catalog` imports
nothing; `goga/topics/hooks` imports `goga/hooks` (facade) and
`goga/history` — never its parent domain package; `goga/topics` imports
`goga/topics/hooks` via `from .hooks import ...` in `creation.py`,
`publishing.py`, `switching.py`, `ensuring.py`, `deletion.py`.

## Facts

- The three CODEMANIFEST files are already materialized in the working
  tree: `goga/hooks/catalog/CODEMANIFEST` (12 `declared_actions`
  requirement bullets — 7 topics records), `goga/topics/CODEMANIFEST`
  (imports the zone, six reworked routines), `goga/topics/hooks/CODEMANIFEST`
  (11 types). `goga lint`: 77 cells, 0 errors at design time.
- `goga/topics/hooks/.usages/checkpoints.md`,
  `goga/topics/.usages/todo-entry.md`, and
  `goga/topics/.usages/creating.md` already carry their planned content.
- `goga/hooks/catalog/catalog.py` currently carries 3 records in
  `_DECLARED_ACTIONS` (onboarding ×2, statuses ×1).
- `_plant_topic_branch` (publishing.py) already returns the built commit
  hash — the emissions reuse the existing return, no new git reads.
- `_apply_candidate` (switching.py) currently returns only the result
  line; `_short_name` lives in `goga/topics/board.py`.
- `enter_topic_todo` (public wrapper) + `_enter_topic_todo` (unwrapped
  mirror returning `bool`) exist in creation.py; the mirror's return
  becomes the final written text (`str | None`) — decision D6.
- `ensure_topic`'s `_create_fresh_work` currently calls the public
  `enter_topic_todo(identifier, year)`.
- The `goga/hooks` facade re-exports `HookRegistry`, `emit_hook_event`,
  `wrap_context`, `build_hook_arguments`, `declared_actions`;
  `resolve_topic_dir` is on the `goga/history` facade — all imports of
  the zone manifest resolve.
- `tests/hooks/conftest.py` provides the platform-environment fixture
  family (`pin_package_environment`, `install_tool_package`) — the zone
  and domain test conftests re-declare them locally per the design.
- `tests/topics/conftest.py` exists with the `builtin_scale` fixture;
  `tests/topics/test_{creation,publishing,switching,ensuring,deletion}.py`
  exist and mock `enter_topic_todo` (switching/ensuring) and the
  git/editor boundaries at the import point.
- `tests/hooks/catalog/test_catalog.py` exists (`TestCatalogContract`,
  `TestDeclaredActions`).
- `docs/features/topics/hooks.md` is a stub ("no hook actions today");
  the declared-actions lists live in `docs/features/hooks/index.md`,
  `docs/features/hooks/hooks.md`, `docs/features/tools/hooks.md`; the
  page exists in `mkdocs.yml` nav — no nav change.
- Design decisions D1–D8 (see Tasks) are contract-freedom decisions,
  fixed by the design review: D1 one registry per run; D2 switch branch
  fact; D3 effective commit message; D4 applied draft message; D5 nulled
  todo on a todo-requiring path; D6 private richer entry; D7 error class
  honored from the catalog; D8 advisory amendment on the ensure fast
  path.

## Gap Analysis

- **Missing contract entities**: all eleven `goga/topics/hooks` types —
  the directory has no Python files at all (`__init__.py`, `identity.py`,
  `contexts.py`, `amendments.py`, `events.py` all missing).
- **Missing facade exposure**: the eleven names are absent from any
  facade (`goga/topics/hooks` has no `__init__.py`).
- **Incorrect `location` placement**: none — all planned files match the
  manifest locations exactly (same directory level as `CODEMANIFEST`,
  `.py` extension).
- **API mismatches**: `enter_topic_todo` lacks `branch: str | None = None`.
- **Behavioral mismatches**: `_DECLARED_ACTIONS` carries 3 of 10
  records; no domain routine delivers an amendment or emits a
  notification; `_apply_candidate` returns no outcome kind; the todo
  entries pass no branch fact; `_publish_topic` does not capture/emit.
- **Existing code that can be reused**: `_plant_topic_branch` (hash
  return), `_enter_topic_todo` mirror (return-type change only),
  `_apply_candidate`'s three branches (outcome mapping added), the
  platform emission/delivery primitives (used as-is), the
  `tests/hooks/conftest.py` fixture family (pattern for the new
  conftests), the existing domain test suites (extended in place).
- **Test coverage gaps**: no `tests/topics/hooks/` directory; the domain
  tests assert no checkpoints; the catalog test does not pin the topics
  records; `tests/topics/conftest.py` lacks the platform fixtures and
  the registry reset.
- **Missing visibility in workspace or git**: `goga/topics/hooks/` and
  the `.goga/history/2026/add-topics-hooks/` directory are untracked;
  `goga/hooks/catalog/CODEMANIFEST`, `goga/topics/CODEMANIFEST`, and the
  two `.usages` files are modified — the materialized contract state is
  present and authoritative for this plan.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).
>
> Package order: `goga/hooks/catalog` (Task 1) → `goga/topics/hooks`
> (Tasks 2–6) → `goga/topics` (Tasks 7–12) → cross-cell docs and
> integration (Tasks 13–14). The catalog records must exist before any
> checkpoint fires (`emit_hook_event` raises `ValueError` on an unknown
> address).

### Task 1: Extend the action catalog with the seven topics records (TDD coding)

**Cell**: `goga/hooks/catalog`. **Entities**: `declared_actions` (data
extension only — the routine and `Action` are unchanged). **Locations**:
`goga/hooks/catalog/catalog.py`, `tests/hooks/catalog/test_catalog.py`
(extend the existing `TestDeclaredActions` class).

The catalog is the single address source — every checkpoint the zone
will emit resolves its address against `declared_actions()`; today
`_DECLARED_ACTIONS` (catalog.py:40-44) carries 3 records and the
implementation appends the seven. The list stays maintained data: append
the records; the routine's `sorted()` fixes the output order regardless
of insertion order.

**Usages relevant to this task:**
- `convention`: docstring style mirroring the manifest annotations,
  kw-only dataclass rules (untouched here), test structure — the test
  goes into the existing `TestDeclaredActions` class of
  `tests/hooks/catalog/test_catalog.py`.
- `declaring-actions` (`goga/hooks/.usages/declaring-actions.md`): the
  domain-maintainer side of opening an action — the catalog record is
  step one; read it for why the records must exist before any emission.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: extend `tests/hooks/catalog/test_catalog.py` — a test asserting the seven topics records exist with `error_class="soft"` and the total is 10 (scenario below; expected to fail at this stage)
- [x] **Code**: append seven `Action` records to `_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py` — all `domain="topics"`, `error_class="soft"`, names: `amend_creation`, `amend_todo_entry`, `topic_created`, `topic_deleted`, `topic_published`, `topic_switched`, `topic_todo_entered` (the list stays in `(domain, name)` sorted order; `declared_actions()` behavior is otherwise untouched)
- [x] **Interface verification**: `pytest tests/hooks/catalog/test_catalog.py -v` — all pass
- [x] **Logic tests**: the assertions below already cover the behavior (determinism, completeness, record shape); add none beyond them
- [x] **Debugging**: `pytest tests/hooks/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: the `Action` dataclass and the `declared_actions` signature/return are unchanged; `goga hooks` lists the topics domain with no command change
- [x] **Lint**: `ruff check goga/hooks/catalog` — fix formatting if necessary

Test scenario (from the design — `test_declared_actions_carries_the_seven_topics_records`):

```
Setup: none (pure data).
Input: declared_actions()
Trace:
declared_actions()
  -> sorted(_DECLARED_ACTIONS, key=(domain, name))
     returns: 10 records
Assertions:
topics = [a for a in declared_actions() if a.domain == "topics"]
[(a.name, a.error_class) for a in topics] == [
    ("amend_creation", "soft"),
    ("amend_todo_entry", "soft"),
    ("topic_created", "soft"),
    ("topic_deleted", "soft"),
    ("topic_published", "soft"),
    ("topic_switched", "soft"),
    ("topic_todo_entered", "soft"),
]
len(declared_actions()) == 10   # 3 existing + 7 topics
Sufficiency: the addresses must exist before any checkpoint fires; an
address the zone emits but the catalog misses is a runtime ValueError
in every flow — this pins the catalog against drift.
```

### Task 2: Zone package skeleton and test infrastructure (infrastructure)

**Cell**: `goga/topics/hooks`. **Entities**: none yet — this task creates
the package skeleton and the zone test infrastructure the entity tasks
build on. **Locations**: `goga/topics/hooks/__init__.py` (new),
`tests/topics/hooks/__init__.py` (new), `tests/topics/hooks/conftest.py`
(new).

Python needs `__init__.py` for the package to be importable; the entity
tasks (3–6) append their re-exports to it so the facade stays current at
every task boundary. The conftest re-declares the platform-environment
fixture family locally (the `tests/hooks/conftest.py` shape) plus the
`recording_hooks` helper — the run-registry reset joins in Task 6 (it
patches `goga.topics.hooks.events._RUN_REGISTRY`, which does not exist
until Task 6; declaring it earlier would break the suite at the Task 3–5
boundaries).

**Usages relevant to this task:**
- `convention`: relative imports, package structure, test-infrastructure
  rules (fixtures live in the local conftest; tests under
  `tests/topics/hooks/` mirror the package path).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga/topics/hooks/__init__.py` — the package docstring in the CODEMANIFEST Description voice (the hooks-zone owner description: importing the package imports no tool package and enumerates nothing) and an empty `__all__: list[str] = []` placeholder that Tasks 3–6 grow to the eleven names
- [x] Create `tests/topics/hooks/__init__.py` (empty, the tests package marker)
- [x] Create `tests/topics/hooks/conftest.py` with the two platform-environment fixtures re-declared locally (the `tests/hooks/conftest.py` shape): `pin_package_environment` — pins `goga.hooks.tools.packages.packages_distributions` to a fixed mapping (`{"goga_tool_one": ["pkg-one"], "goga_tool_two": ["pkg-two"]}`); `install_tool_package(module_name, register_hooks)` — mounts fake `goga_tool_*` modules in `sys.modules` (monkeypatch-undone)
- [x] Add to the same conftest the `recording_hooks` fixture — subscribes recording hooks (appending `(tool, hook_name, context)` tuples and captured facts to lists the tests assert) built on the two fixtures above
- [x] Verify the package imports: `python -c "import goga.topics.hooks"` and the suite still collects: `pytest tests/topics/hooks/ --collect-only -q` (no test files yet — collection must be clean)
- [x] Lint: `ruff check goga/topics/hooks tests/topics/hooks` — fix formatting if necessary

### Task 3: `TopicIdentity` — the identity vocabulary (TDD coding)

**Cell**: `goga/topics/hooks`. **Entities**: `TopicIdentity`
(`identity.py`). **Locations**: `goga/topics/hooks/identity.py` (new),
`goga/topics/hooks/__init__.py` (add the re-export),
`tests/topics/hooks/test_identity.py` (new).

**Usages relevant to this task:**
- `convention`: `@dataclass(frozen=True, kw_only=True)` data-model rules
  (the `Action`/`Stage` precedent), relative imports
  (`from ...history import resolve_topic_dir` inside the zone — three
  leading dots: `goga.topics.hooks` → package root → `goga.history`).
- `topic-paths` (`goga/history/.usages/topic-paths.md`): the topic
  directory composition contract behind `home_path` — the composition
  runs through `resolve_topic_dir`; `resolve_topic_dir` re-normalizes
  its input (idempotent for an already-normalized slug) and returns the
  `.goga/history/<year>/<slug>` path.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/topics/hooks/test_identity.py` — facade accessibility (`from goga.topics.hooks import TopicIdentity`), kw-only construction (`TopicIdentity(slug=..., year=..., branch=...)`; positional construction raises `TypeError`), frozen behavior (attribute assignment raises `FrozenInstanceError`), the three property types (expected to fail at this stage)
- [x] **Code**: create `goga/topics/hooks/identity.py` per the algorithm below — `@dataclass(frozen=True, kw_only=True)` with `slug: str | None`, `year: str`, `branch: str | None`, and the `home_path` property
- [x] **Code**: add `TopicIdentity` to `goga/topics/hooks/__init__.py` (relative import from `.identity`, append to `__all__` keeping alphabetical order)
- [x] **Interface verification**: `pytest tests/topics/hooks/test_identity.py -v` — all pass
- [x] **Logic tests**: the pure-composition scenario below (positive), the branch-only form `slug=None` → `home_path is None` (edge), the deletion form `branch=None` keeps `home_path` composed (edge)
- [x] **Debugging**: `pytest tests/topics/hooks/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade import works; property set is exactly `slug`/`home_path`/`branch` with the declared types; no repository reads, nothing created (pure composition)
- [x] **Lint**: `ruff check goga/topics/hooks tests/topics/hooks` — fix formatting if necessary

Algorithm (from the design):

```
1. @dataclass(frozen=True, kw_only=True) with fields slug: str | None,
   year: str, branch: str | None
2. home_path property:
   IF slug is None -> None
   ELSE -> resolve_topic_dir(slug, year).as_posix()

Errors: none — the empty-slug ValueError of resolve_topic_dir is
unreachable (slug non-None on the composing branch, and re-normalization
of a normalized slug is the identity).

Edge cases:
- Branch-only form (slug=None) -> home_path None.
- Deletion form (branch=None) -> the removal composition carries the
  branch names instead.
```

Test scenario (from the design — `test_topic_identity_home_path_composes_purely`):

```
Setup: none (pure composition; no filesystem).
Input: TopicIdentity(slug="add-topics-hooks", year="2026",
branch="add-topics-hooks").
Trace:
TopicIdentity(slug=..., year=..., branch=...)
  -> identity.home_path
     -> resolve_topic_dir("add-topics-hooks", "2026")
        -> normalize (idempotent) -> .goga/history/2026/add-topics-hooks
     -> .as_posix()
     returns: ".goga/history/2026/add-topics-hooks"
Assertions:
identity.home_path == ".goga/history/2026/add-topics-hooks"
identity.slug == "add-topics-hooks"; identity.branch == "add-topics-hooks"
Sufficiency: the home path is the canonical addressing fact every
notification carries; a regression here corrupts every tool's view of
the topic location.
```

### Task 4: The five notification contexts (TDD coding)

**Cell**: `goga/topics/hooks`. **Entities**: `TopicCreated`,
`TopicPublished`, `TopicSwitched`, `TopicTodoEntered`, `TopicDeleted`
(all `contexts.py`). **Locations**: `goga/topics/hooks/contexts.py`
(new), `goga/topics/hooks/__init__.py` (add five re-exports),
`tests/topics/hooks/test_contexts.py` (new).

The contexts are read-only fact bags: an `emit_*` method constructs one
from the values the caller passed; a hook observes and cannot alter
(frozen; assignment is also blocked on the delivery proxy). Plain
attribute reads suffice — no computed members, no method surface, no
write path.

**Usages relevant to this task:**
- `convention`: `@dataclass(frozen=True, kw_only=True)` rules, Google
  docstrings mirroring the manifest annotations, relative import of
  `TopicIdentity` from `.identity`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/topics/hooks/test_contexts.py` — per context: facade accessibility, kw-only construction, frozen behavior (assignment raises), the exact field set with declared types, `identity: TopicIdentity` carried through (expected to fail at this stage)
- [x] **Code**: create `goga/topics/hooks/contexts.py` per the algorithm below — five `@dataclass(frozen=True, kw_only=True)` classes with fields exactly as the signatures declare; plain data fields only
- [x] **Code**: add the five names to `goga/topics/hooks/__init__.py` (relative imports from `.contexts`, `__all__` stays alphabetical)
- [x] **Interface verification**: `pytest tests/topics/hooks/test_contexts.py -v` — all pass
- [x] **Logic tests**: field-passthrough reads per context (each constructor value reads back identically); `TopicSwitched.outcome` accepts and returns each of the three fixed kinds (`local-checkout`, `created-from-remote`, `already-on-branch`) — the kind is fixed by construction of the emitting routine, so the context itself just carries the string
- [x] **Debugging**: `pytest tests/topics/hooks/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade imports work; the five field lists are identical to the method parameters beyond `identity` of the matching `emit_*` signatures (interface↔type consistency); no method surface, no write path
- [x] **Lint**: `ruff check goga/topics/hooks tests/topics/hooks` — fix formatting if necessary

Algorithm (from the design):

```
1. Five @dataclass(frozen=True, kw_only=True) classes, fields exactly
   as the signatures declare:
   TopicCreated(identity, checked_out, published, todo, commit_message, commit_hash)
   TopicPublished(identity, commit_message, commit_hash, todo)
   TopicSwitched(identity, outcome)
   TopicTodoEntered(identity, text)
   TopicDeleted(identity, local_branch, origin_twin, directory_removed)
2. Plain data fields (attribute reads suffice; no computed members)

Errors: none.
Edge cases: TopicSwitched.outcome is one of the three fixed kinds by
construction of the emitting routine.
```

### Task 5: Draft holders and amendment views (TDD coding)

**Cell**: `goga/topics/hooks`. **Entities**: `CreationDraft`,
`TodoEntryDraft`, `CreationAmendment`, `TodoEntryAmendment` (all
`amendments.py`). **Locations**: `goga/topics/hooks/amendments.py`
(new), `goga/topics/hooks/__init__.py` (add four re-exports),
`tests/topics/hooks/test_amendments.py` (new).

**Usages relevant to this task:**
- `convention`: kw-only dataclass rules; the holders are **mutable**
  dataclasses (the `StatusRegistry` precedent) while the views are
  mutable dataclasses with private fields.
- `registering-hooks` (`goga/hooks/.usages/registering-hooks.md`): the
  views are the delivered objects hooks receive — reads pass through the
  proxy, assignment is blocked on the proxy, `amend` is a plain method
  call. The hook signature (`context`/`self` offered names) and failure
  behavior behind every checkpoint are defined there.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/topics/hooks/test_amendments.py` — per type: facade accessibility, kw-only construction, the read-through properties (`view.commit_message`/`view.todo`/`view.text` read the live holder fields); `amend` returns `None` and raises nothing (expected to fail at this stage)
- [x] **Code**: create `goga/topics/hooks/amendments.py` per the algorithm below — the two mutable holders with the private `_commit`, and the two views storing the holder under the private field `_draft` with the private `_buffered` buffer (`init=False, repr=False`, default `None`)
- [x] **Code**: add the four names to `goga/topics/hooks/__init__.py` (relative imports from `.amendments`, `__all__` stays alphabetical)
- [x] **Interface verification**: `pytest tests/topics/hooks/test_amendments.py -v` — all pass
- [x] **Logic tests**: the two design scenarios below (`test_amend_views_block_no_write_path_to_the_holder`, `test_amend_called_twice_last_buffer_wins`) plus: a repeated `amend` overwrites the buffer (whole replacement, last wins — covered by the second scenario); `amend(None, None)` is a lawful whole replacement that buffers without holder contact
- [x] **Debugging**: `pytest tests/topics/hooks/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade imports work; the views expose no write path to the holder (`_draft` is private; `commit_message`/`todo`/`text` are read-through properties, not fields); no cancel/redirect/defer method exists; buffering never raises
- [x] **Lint**: `ruff check goga/topics/hooks tests/topics/hooks` — fix formatting if necessary

Algorithm (from the design — includes the review-fixed `_draft` rule):

```
CreationDraft / TodoEntryDraft:
1. @dataclass(kw_only=True) — mutable (the StatusRegistry precedent):
   CreationDraft(commit_message: str | None, todo: str | None)
   TodoEntryDraft(text: str)
2. _commit(values) — private; the single mutation point: replaces the
   whole content from the walk

CreationAmendment / TodoEntryAmendment:
1. @dataclass(kw_only=True) with the signature fields, the holder stored
   under the private field name `_draft` (the walk in events.py is the
   sole constructor caller: CreationAmendment(identity=...,
   checked_out=..., published=..., _draft=holder) — the kw name is an
   internal wiring detail; the CODEMANIFEST signature documents the
   input semantically), plus a private _buffered field (init=False,
   repr=False, default None)
2. commit_message / todo / text properties read through self._draft
   (the live holder) — the holder is never a public attribute of the
   view, so a delivered view exposes no write path to it: the proxy
   blocks assignment on the view, and reaching `_draft` deliberately
   is out-of-contract usage (the same cooperative trust the platform
   gives the `self` context)
3. amend(...) -> assigns self._buffered = the whole replacement
   (CreationAmendment: (commit_message, todo); TodoEntryAmendment: text);
   no holder contact

Errors: none — buffering never raises.
Edge cases:
- A hook calling amend twice -> the last buffer wins.
- amend(None, None) -> a lawful whole replacement to the identity-only
  form (commits; the path guards decide the consequences — D5).
```

Test scenarios (from the design):

`test_amend_views_block_no_write_path_to_the_holder`:
```
Setup: a holder and a view constructed directly; no platform.
Input: view.amend("m", "t"); then read holder.commit_message.
Trace: amend buffers on the view only; the holder fields stay at the
draft values.
Assertions:
holder.commit_message == <original>; holder.todo == <original>
view.commit_message reads the live holder (the draft values, not the buffer)
Sufficiency: "the content changes only through the delivery commit —
never through a delivered view" — the buffering isolation that makes
the discard-on-failure semantics possible.
```

`test_amend_called_twice_last_buffer_wins`:
```
Setup: enumeration pinned; one tool subscribing `fickle` whose hook
calls context.amend("first", "t-first") then
context.amend("second", "t-second"); registry reset.
Input: TopicHooks().amend_creation(identity, False, False, "orig",
"orig todo").
Trace:
walk: fickle buffers ("first", "t-first") then overwrites its buffer
     with ("second", "t-second"); the holder stays untouched during
     both calls
returns -> view._buffered == ("second", "t-second") -> committed whole
Assertions:
draft.commit_message == "second"; draft.todo == "t-second"
Sufficiency: pins the whole-replacement last-wins semantics of the
buffer — the sole guarantee that amend means "replace entirely", not
"extend"; prevents a drift to an accumulative or first-wins semantics
no other scenario distinguishes.
```

Note: the walk-dependent trace of the second scenario executes fully
only after Task 6; write the test now against the view/holder semantics
(hook double calls `view.amend` twice, then assert the buffer content
committed through a direct `_commit`), or defer the full-walk variant to
Task 6's `test_events.py` — in either case the last-wins assertion is
mandatory in this task.

### Task 6: `TopicHooks` and the run registry — the checkpoint surface (TDD coding)

**Cell**: `goga/topics/hooks`. **Entities**: `TopicHooks` (`events.py`),
the module-level `_RUN_REGISTRY` with the lazy `_run_registry()`
builder. **Locations**: `goga/topics/hooks/events.py` (new),
`goga/topics/hooks/__init__.py` (add the re-export — `__all__` reaches
its final eleven names), `tests/topics/hooks/conftest.py` (add the
autouse run-registry reset), `tests/topics/hooks/test_events.py` (new).

This is the core of the zone: the two amendment walks (per-hook staged
delivery over the public primitives) and the five plain emissions over
`emit_hook_event`. Decision D1 — one registry per run: the shared
module-level lazily-built `HookRegistry`, so nested public calls
(`ensure_topic` → `switch_topic` → `enter_topic_todo`;
`create_topic` → `publish_topic`) never multiply the package
enumeration.

**Usages relevant to this task:**
- `convention`: one module logger in `events.py`; `logger.warning` with
  `%s` placeholders (the `emit.py` style); relative imports
  (`from ...hooks import HookRegistry, emit_hook_event, wrap_context,
  build_hook_arguments, declared_actions`).
- `declaring-actions` (`goga/hooks/.usages/declaring-actions.md`): the
  emission contract — `emit_hook_event(registry, "topics", "<action>",
  context_for=lambda _tool: context)`; the same instance shared per
  tool; the emission assembles the registry on first use.
- `per-tool-delivery` (`goga/hooks/.usages/per-tool-delivery.md`): the
  staged delivery loop skeleton — build once, subscriptions in
  enumeration order, wrap/project/call, commit only after success, warn
  naming tool/action/reason, never filter delivery,
  `build_hook_arguments` as the single projection. **With the declared
  refinement: the commit granularity is the single hook, not the tool**
  — a fresh view per subscription, the commit decided per subscription
  (no grouping by tool).
- `registering-hooks` (`goga/hooks/.usages/registering-hooks.md`): the
  hook receives values only for the declared offered names (`context`,
  `self`); the tool's `self` context is the same instance across every
  checkpoint of the run (shared registry).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/topics/hooks/test_events.py` — facade accessibility of `TopicHooks`; cheap construction (scenario `test_topic_hooks_construction_enumerates_nothing` below); the seven method signatures callable as declared (expected to fail at this stage)
- [ ] **Code**: create `goga/topics/hooks/events.py` per the algorithm below — `_RUN_REGISTRY` module state, `_run_registry()`, `TopicHooks()` with `amend_creation`, `amend_todo_entry`, and the five `emit_*` methods
- [ ] **Code**: add `TopicHooks` to `goga/topics/hooks/__init__.py` — the final facade: `__all__` carries exactly the eleven names, alphabetically (`CreationAmendment`, `CreationDraft`, `TodoEntryAmendment`, `TodoEntryDraft`, `TopicCreated`, `TopicDeleted`, `TopicHooks`, `TopicIdentity`, `TopicPublished`, `TopicSwitched`, `TopicTodoEntered`)
- [ ] **Code**: add the autouse run-registry reset to `tests/topics/hooks/conftest.py` — `monkeypatch.setattr("goga.topics.hooks.events._RUN_REGISTRY", None)` — every test starts with an unbuilt registry, so no subscription leaks across tests and enumeration counts are per-test
- [ ] **Interface verification**: `pytest tests/topics/hooks/test_events.py -v` — all pass
- [ ] **Logic tests**: the eight design scenarios below — `test_amend_creation_walks_per_hook_and_commits_in_order`, `test_emit_created_shares_one_instance_and_returns_none`, `test_amend_creation_discards_buffer_of_raising_hook`, `test_amend_creation_rejects_empty_amendment_whole`, `test_amend_todo_entry_rejects_blank_text_buffer`, `test_run_registry_built_once_across_checkpoints`, `test_amend_creation_without_subscriptions_returns_original_values`, `test_amend_creation_identity_only_form_is_valid` — plus the construction scenario `test_topic_hooks_construction_enumerates_nothing` (below)
- [ ] **Debugging**: `pytest tests/topics/hooks/ -x` then `pytest tests/hooks/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the facade check passes — `python -c "from goga.topics.hooks import TopicHooks, TopicIdentity, CreationDraft, TodoEntryDraft, TopicCreated, TopicPublished, TopicSwitched, TopicTodoEntered, TopicDeleted, CreationAmendment, TodoEntryAmendment"`; no post-walk application of any amendment (the caller fixes the final draft itself); no subscriber of the address is skipped
- [ ] **Lint**: `ruff check goga/topics/hooks tests/topics/hooks` — fix formatting, apply decomposition if necessary

Algorithm (from the design):

```
_RUN_REGISTRY: HookRegistry | None = None   # module state, one per run

_run_registry():
1. IF _RUN_REGISTRY is None: create HookRegistry(), build_once(),
   store it
2. return _RUN_REGISTRY
   -> one enumeration per process run; every TopicHooks instance and
     every checkpoint shares it (D1)

TopicHooks():
1. No state — cheap construction; no enumeration, no imports at init

amend_creation(identity, checked_out, published, commit_message, todo):
1. registry = _run_registry()
2. record = resolve ("topics", "amend_creation") against declared_actions()
   -> None is a clean ValueError of the emitting side
3. holder = CreationDraft(commit_message=commit_message, todo=todo)
4. FOR subscription IN registry.subscriptions_for("topics", "amend_creation"):
     view = CreationAmendment(identity=..., checked_out=...,
                              published=..., _draft=holder)  # outside the intercept
     TRY:
       proxy = wrap_context(view)
       args = build_hook_arguments(subscription.hook, proxy,
                                   registry.self_context(subscription.tool))
       subscription.hook(**args)
     EXCEPT Exception AS reason:
       IF record.error_class == "hard": RAISE ValueError(
         "hook {name} of tool {tool} failed on topics.amend_creation: {reason}")
       WARN "hook {name} of tool {tool} failed on topics.amend_creation: {reason}"
       CONTINUE                                        # buffer discarded
     IF view._buffered is not None:
       IF a structurally present field is empty/whitespace-only:
         WARN ... ": the buffered amendment is empty or whitespace-only"
         CONTINUE                                      # whole buffer rejected
       holder._commit(view._buffered)                  # whole replacement
5. return holder

amend_todo_entry(identity, text):
  the same walk over TodoEntryDraft/TodoEntryAmendment, address
  topics.amend_todo_entry; the single-field rejection covers
  text is None or not text.strip()

emit_created / emit_published / emit_switched / emit_todo_entered / emit_deleted:
1. context = the frozen context from the values
2. emit_hook_event(_run_registry(), "topics", "<action>",
                   context_for=lambda _tool: context)
   -> the same instance per tool; the platform owns resolution, delivery,
     and the soft warning
```

Walk details fixed by the design trace (verified against the platform):

- The fresh `CreationAmendment` view is built **outside** the failure
  intercept — a crashing view builder is the emitting side's bug, never
  a hook failure (the `context_for` placement of `emit.py:83-85`).
- The intercept catches `Exception` only, mirroring `emit.py:87-95`.
- The hard-class branch raises `ValueError` in the same shape as
  `emit.py:97-99` — dead today (all seven records are soft).
- The buffer rejection predicate (creation):
  `(cm is not None and not cm.strip()) or (todo is not None and not todo.strip())`
  — reject the **whole** buffer when either structurally present field is
  empty or whitespace-only, with the reason string
  `the buffered amendment is empty or whitespace-only`.
- The todo-entry rejection covers `text is None or not text.strip()`
  (the contract types `text` as `str`; a None buffer value is treated as
  the rejection case — this single predicate distinguishes the two
  walks).
- The warning text is fixed: `hook <name> of tool <tool> failed on
  topics.<action>: <reason>` — `logger.warning` with `%s` placeholders,
  one module logger in `events.py`. No INFO/DEBUG additions (the
  platform's emit path owns the diagnostics surface).
- An address without subscriptions returns the original draft values —
  not an error.
- Errors: `ValueError` (unknown address) is the emitting side's bug;
  `ImportError` from `build_once` (a broken tool package import) is the
  single fatal case, surfacing from the platform unchanged.

Test scenarios (from the design):

`test_amend_creation_walks_per_hook_and_commits_in_order` (positive):
```
Setup: enumeration pinned to two tools; two packages installed —
goga_tool_one subscribing `first` and `second` to
topics.amend_creation, goga_tool_two subscribing `tail`;
run-registry reset applied.
Input:
hooks = TopicHooks()
draft = hooks.amend_creation(
    identity, checked_out=False, published=False,
    commit_message="goga: create topic add-topics-hooks", todo="first todo")
Hooks: `first` calls context.amend("m1", "t1"); `second` records
context.todo (live read) and calls context.amend("m2", "t2"); `tail`
records context.todo.
Trace:
amend_creation(...)
  -> _run_registry(): build_once() enumerates both packages once
  -> holder = CreationDraft("goga: create topic add-topics-hooks", "first todo")
  -> sub one/first: view over holder; hook buffers ("m1", "t1")
     returns -> holder._commit(("m1","t1"))  [non-empty]
  -> sub one/second: view reads context.todo == "t1" (committed amendment of the earlier hook)
     hook buffers ("m2","t2") -> holder._commit(("m2","t2"))
  -> sub two/tail: view reads context.todo == "t2"
returns holder
Assertions:
draft.commit_message == "m2"; draft.todo == "t2"          # last committed buffer
second saw context.todo == "t1"; tail saw context.todo == "t2"
enumeration boundary called exactly once
Sufficiency: pins the per-hook commit granularity (two hooks of one
tool, independent buffers, ordered visibility) — the core refinement
the zone adds over the tool-grouped practice.
```

`test_emit_created_shares_one_instance_and_returns_none` (positive):
```
Setup: enumeration pinned; two packages each subscribing one hook
to topics.topic_created.
Input: result = TopicHooks().emit_created(identity, checked_out=False,
published=False, todo="t", commit_message="m", commit_hash="abc123").
Trace:
emit_created(...)
  -> TopicCreated(...) built once
  -> emit_hook_event(_run_registry(), "topics", "topic_created",
                     context_for=lambda _tool: context)
     -> both hooks called with the delivered proxy
Assertions:
result is None
the two deliveries observe the identical underlying context —
  each through its own fresh proxy (type is not TopicCreated), the
  shared instance pinned one attribute deep:
  recorded[0].identity is recorded[1].identity
each hook read: checked_out False, published False, todo "t",
  commit_message "m", commit_hash "abc123", identity.home_path as composed
Sufficiency: the context-instance sharing and the fire-and-forget
contract of every notification — prevents per-tool copies (stale facts)
and accidental return-channel collection.
```

`test_amend_creation_discards_buffer_of_raising_hook` (negative):
```
Setup: enumeration pinned; goga_tool_one subscribes `boom`
(calls context.amend("m", "t") then raise RuntimeError("kaputt"));
goga_tool_two subscribes `tail` (context.amend("late", "late-t"));
registry reset; caplog at WARNING.
Input: TopicHooks().amend_creation(identity, False, False, "orig",
"orig todo").
Trace:
walk: boom raises after buffering -> buffer discarded, warning emitted
walk: tail returns -> buffer committed
returns holder
Assertions:
draft.commit_message == "late"; draft.todo == "late-t"   # boom's buffer gone
any("hook boom of tool one failed on topics.amend_creation: kaputt"
    in r.message for r in caplog.records)
the walk reached tail (its buffer landed)
Sufficiency: a failing hook never breaks the operation and never
leaks its buffer — the soft-action core guarantee.
```

`test_amend_creation_rejects_empty_amendment_whole` (negative):
```
Setup: one tool subscribing `blank` ->
context.amend("   ", "fine text"); registry reset; caplog.
Input: TopicHooks().amend_creation(identity, False, False, "orig",
"orig todo").
Trace:
walk: blank returns; buffer ("   ", "fine text")
-> commit_message structurally present and whitespace-only
-> whole buffer rejected with the empty-amendment warning
returns holder with the original values
Assertions:
draft.commit_message == "orig"; draft.todo == "orig todo"
"failed on topics.amend_creation: the buffered amendment is empty or whitespace-only"
  in caplog.text
Sufficiency: the whole-replacement rejection — a whitespace field
must not partially land (the message survives while the todo changes).
```

`test_amend_todo_entry_rejects_blank_text_buffer` (negative):
```
Setup: enumeration pinned; one tool subscribing `blank` ->
context.amend("   ") (whitespace buffer); registry reset; caplog
at WARNING.
Input: TopicHooks().amend_todo_entry(identity, "saved text").
Trace:
walk: blank returns; buffer "   "
-> text buffer blank (whitespace-only)
-> whole buffer rejected with the empty-amendment warning
returns holder with the saved text
Assertions:
draft.text == "saved text"
"failed on topics.amend_todo_entry: the buffered amendment is empty or whitespace-only"
  in caplog.text
Sufficiency: pins the single predicate that distinguishes the
todo-entry walk from the creation walk (text is None or
not text.strip() — a None buffer is rejected here, lawful on the
creation side) — a regression that unifies the two walks without
changing the contract is caught, and the write path is guaranteed a
non-blank text by rejection rather than by luck.
```

`test_run_registry_built_once_across_checkpoints` (edge):
```
Setup: enumeration boundary mock (call-counting); one tool
subscribing to amend_creation, topic_created, topic_todo_entered,
amend_todo_entry; registry reset.
Input:
hooks = TopicHooks()
hooks.amend_creation(identity, False, False, None, None)   # identity-only form
hooks.emit_created(identity, False, False, None, None, None)
hooks.amend_todo_entry(identity, "t")
hooks.emit_todo_entered(identity, "t")
TopicHooks().emit_switched(identity, "local-checkout")     # a second instance
Trace:
every checkpoint -> _run_registry() -> the single built object
Assertions:
boundary.call_count == 1
all checkpoints delivered to the subscriber
Sufficiency: D1 — "the checkpoints never multiply the package
enumeration", including across separate TopicHooks instances and
nested flows.
```

`test_amend_creation_without_subscriptions_returns_original_values` (edge):
```
Setup: enumeration pinned to a tool subscribing nothing; registry
reset.
Input: amend_creation(identity, False, False, "m", None).
Trace: walk over zero subscriptions -> holder untouched.
Assertions:
draft.commit_message == "m"; draft.todo is None   # no error
Sufficiency: the no-subscriber case is the everyday case — the
amendment is a transparent no-op the flows can always call.
```

`test_amend_creation_identity_only_form_is_valid` (edge):
```
Setup: one tool subscribing a recorder (no amend call); registry
reset.
Input: amend_creation(identity, True, False, None, None).
Trace: holder created with (None, None); hook observes, buffers nothing.
Assertions:
draft.commit_message is None; draft.todo is None
recorded view read: checked_out True, published False,
  commit_message None, todo None
Sufficiency: the identity-only form is the norm on the ensure fast
path — a hook must be able to observe it without acting.
```

`test_topic_hooks_construction_enumerates_nothing` (edge):
```
Setup: enumeration boundary mock installed; registry reset.
Input: TopicHooks() (no checkpoint calls).
Trace: __init__ stores nothing, touches nothing.
Assertions:
boundary.call_count == 0; _RUN_REGISTRY stays None
Sufficiency: "cheap construction — no enumeration and no imports
happen at construction" — keeps import-time and construction-time
behavior identical for every consumer.
```

### Task 7: `enter_topic_todo` — the todo-entry checkpoint pair (TDD coding)

**Cell**: `goga/topics`. **Entities**: `enter_topic_todo` (signature
gains `branch: str | None = None`) and the private mirror
`_enter_topic_todo` (its return becomes the final written text — D6).
**Locations**: `goga/topics/creation.py` (modify),
`tests/topics/conftest.py` (extend — the platform fixtures and the
registry reset for the domain tests), `tests/topics/test_creation.py`
(extend).

This is the first domain task: extend `tests/topics/conftest.py` with
the platform-environment fixture family (`pin_package_environment`,
`install_tool_package`, `recording_hooks` — the same local shape as
`tests/topics/hooks/conftest.py`) and the autouse registry reset
(`monkeypatch.setattr("goga.topics.hooks.events._RUN_REGISTRY", None)`);
the zone is complete by now, so the reset is safe for every test under
`tests/topics/`. The child conftest of `tests/topics/hooks/` shadows the
parent for its own directory — no double application.

**Usages relevant to this task:**
- `convention`: relative imports (`from .hooks import TopicHooks,
  TopicIdentity` in creation.py), test structure, mock boundaries —
  `edit_text` stubbed on the creation module, the git/editor boundaries
  mocked at the import point per module.
- `editor-entry` (`goga/topics/editor/.usages/editor-entry.md`): the
  editor session pattern — `edit_text(initial)` returns the saved text
  or `None` on cancellation (blank/unchanged save → None).
- `topic-paths` (`goga/history/.usages/topic-paths.md`): the todo-file
  path pattern (`resolve_topic_file`).
- `checkpoints` (`goga/topics/hooks/.usages/checkpoints.md`): the
  binding practice — identity construction from operation data
  (`TopicIdentity(slug=normalize_topic_slug(topic), year=resolved_year,
  branch=branch)` — no repository reads), amendment delivery after the
  save and before the write, notification emission after the write.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: update the signature-contract test of `tests/topics/test_creation.py` for the `branch` parameter (`inspect.signature` shape: `enter_topic_todo(topic: str, year: str | None = None, branch: str | None = None) -> bool`); add facade re-export check (`from goga.topics import enter_topic_todo` — unchanged, still importable) (expected to fail at this stage)
- [ ] **Code**: rework `enter_topic_todo` / `_enter_topic_todo` in `goga/topics/creation.py` per the algorithm below — the `branch` parameter, the amendment delivery, the emission, and the D6 return-type change of the mirror (`str | None`; the public wrapper returns `written is not None`)
- [ ] **Interface verification**: `pytest tests/topics/test_creation.py -v` — all pass (existing tests included)
- [ ] **Logic tests**: the three design scenarios below — `test_enter_topic_todo_writes_amended_text_and_emits_final` (positive), `test_enter_topic_todo_cancelled_entry_delivers_and_emits_nothing` (negative), `test_enter_topic_todo_failed_write_emits_nothing` (negative)
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all tests pass; the existing switching/ensuring tests that mock `enter_topic_todo` keep passing unchanged (their assertions gain the `branch=` keyword only in Tasks 10–11)
- [ ] **Contract re-verification**: cancelled entry → no delivery, no emission, file untouched; emission follows the write and mutates nothing; the `OSError` wrapper boundary unchanged (the checkpoint code performs no I/O); the write is the last mutation
- [ ] **Lint**: `ruff check goga/topics` — fix formatting if necessary

Algorithm (from the design):

```
enter_topic_todo(topic, year=None, branch=None):
1-3. unchanged (path resolve, prefill read, editor session);
     cancelled -> False (nothing delivered or emitted)
4. identity = TopicIdentity(slug=normalize_topic_slug(topic),
                            year=resolved_year, branch=branch)
5. draft = TopicHooks().amend_todo_entry(identity, saved)
   # the returned TodoEntryDraft holder — draft.text is the final text
6. _write_todo(topic, resolved_year, draft.text) -> the final text
   (the single-trailing-newline rule applies to the final amended text;
   the write is the last mutation)
7. TopicHooks().emit_todo_entered(identity, draft.text); return True

Internal (D6): the existing unwrapped mirror _enter_topic_todo(topic,
year, branch) returns the final written text (str | None); the public
wrapper returns written is not None.
```

Test scenarios (from the design):

`test_enter_topic_todo_writes_amended_text_and_emits_final`:
```
Setup: tmp_path as cwd; topic directory
.goga/history/2026/feature-foo/ created; edit_text stubbed to return
"saved text"; enumeration pinned; one package subscribing an
amend_todo_entry hook (context.amend("amended text")) and a
topic_todo_entered recorder; registry reset.
Input: enter_topic_todo("feature-foo", year="2026",
branch="feature-foo").
Trace:
enter_topic_todo(...)
  -> resolve_topic_file -> path (file absent -> initial None)
  -> edit_text(None) -> "saved text"
  -> identity = TopicIdentity("feature-foo", "2026", "feature-foo")
  -> amend_todo_entry(identity, "saved text") -> holder.text "amended text"
  -> _write_todo: todo.md == "amended text\n" (UTF-8, single newline)
  -> emit_todo_entered(identity, "amended text")
returns True
Assertions:
result is True
(todo.md).read_text() == "amended text\n"
recorded topic_todo_entered context.text == "amended text"
recorded context.identity.branch == "feature-foo"
Sufficiency: the pre-fixation/post-moment pair of the entry — the
file carries the amended text and the notification reports the same
final value (the .usages/todo-entry.md clause made executable).
```

`test_enter_topic_todo_cancelled_entry_delivers_and_emits_nothing`:
```
Setup: topic directory present; edit_text -> None (cancelled);
recorders installed; registry reset.
Input: enter_topic_todo("feature-foo", year="2026").
Trace: edit_text -> None -> return False before any delivery.
Assertions:
result is False
todo.md absent; recorded checkpoints == []
Sufficiency: a cancelled entry is a non-event — the amendment
moment never arrives.
```

`test_enter_topic_todo_failed_write_emits_nothing`:
```
Setup: tmp_path as cwd; topic directory created; edit_text
stubbed to return "saved"; _write_todo on the creation module
monkeypatched to raise OSError; a topic_todo_entered recorder
installed; registry reset.
Input: enter_topic_todo("feature-foo", year="2026").
Trace:
enter_topic_todo -> save "saved"
-> amend_todo_entry delivered (holder.text "saved" — no subscriber)
-> _write_todo raises OSError
-> the wrapper converts it to ClickException; emit_todo_entered
   is never reached
Assertions:
pytest.raises(click.ClickException)
recorded topic_todo_entered == []
Sufficiency: pins the write-then-emit order on the failure path —
the only point where the order guarantees the event carries a written
fact; catches an emit-before-write or emit-in-finally regression.
```

### Task 8: `create_topic` — the creation amendment and notification (TDD coding)

**Cell**: `goga/topics`. **Entities**: `create_topic` (checkpoint wiring
inside `_create_topic`). **Locations**: `goga/topics/creation.py`
(modify), `tests/topics/test_creation.py` (extend).

Steps 1–5 (preflight, todo resolution, guards, publication ask) are
unchanged — every decision precedes the first mutation; a failing
preflight fires nothing. The amendment inserts between the ask and the
path branches; the emissions close the no-switch and switch paths; the
publication path delegates with the amended values and fires nothing
here.

**Usages relevant to this task:**
- `convention`: relative imports, mock boundaries (`sys.stdin` pinned to
  an interactive terminal via the tests/topics precedent — `isatty` →
  True — wherever the editor-todo resolution must run).
- `click` (`.goga/usages/cooks/click.md`): the publication ask and the
  non-interactive detection — unchanged behavior, pinned by the test
  setups.
- `editor-entry`: the editor session of the todo resolution (`edit_text`
  stub).
- `topic-paths`: the slug, existence, directory-creation, and todo-file
  path patterns.
- `refs-and-switching` (`goga/topics/git/.usages/refs-and-switching.md`):
  the checkout pattern of the switch path — `_enter_fresh_branch` and
  its create-then-checkout sequence are unchanged; the wiring only adds
  the emission after the path completes.
- `publishing` (`goga/topics/git/.usages/publishing.md`): the
  quarantined plant of the no-switch path — `_plant_topic_branch`
  already returns the commit hash.
- `checkpoints`: the creation amendment immediately before the first
  mutation of the chosen path; `topic_created` after the last mutation
  of the path.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: the public signature, result lines, and error surface are unchanged — assert via the existing contract tests of `tests/topics/test_creation.py` (they must keep passing unmodified; expected failure at this stage comes only from the new wiring assertions below)
- [ ] **Code**: rework `_create_topic` in `goga/topics/creation.py` per the algorithm below — the amendment step between the ask and the path branches, the no-switch hash capture and emission, the switch-path emission, the publication delegation with the final values
- [ ] **Interface verification**: `pytest tests/topics/test_creation.py -v` — all pass
- [ ] **Logic tests**: the three design scenarios below — `test_create_topic_no_switch_emits_created_with_commit_hash` (positive), `test_create_topic_failed_preflight_fires_nothing` (negative), `test_create_topic_switch_path_amended_null_todo_degrades_gracefully` (edge)
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: `topic_created` fires exactly once per successful creation (no-switch and switch paths emit here; the publication path's emission lives in the delegate); the amendment delivers exactly once, immediately before the first mutation; existing behavior (result lines, error surface, mutation order) unchanged
- [ ] **Lint**: `ruff check goga/topics` — fix formatting if necessary

Algorithm (from the design — includes decisions D3, D4, D5, D12):

```
_create_topic — insert between the ask and the path branches:
  publishing = _publication_asked(publish, resolved_todo)
  identity = TopicIdentity(slug, resolved_year, branch_name)
  draft = TopicHooks().amend_creation(identity,
           checked_out=switch and not publishing,
           published=publishing,
           commit_message=<applied message of the path, None on switch>,
           todo=resolved_todo)
  # the returned CreationDraft holder — its amended values replace the
  # todo and the commit message carried into the mutation steps
  # the applied message uses the `or` predicate: an empty template
  # normalizes to the built-in default before the delegation
  final_todo = draft.todo; final_message = draft.commit_message
no-switch branch:
  IF final_todo is None -> the "needs a todo" clean error (D5 —
    nothing has mutated yet; "a failed creation fires nothing" holds)
  commit = _plant_topic_branch(branch_name, final_todo, base_commit,
                               slug, resolved_year, final_message)
  TopicHooks().emit_created(identity, checked_out=False, published=False,
                            todo=final_todo,
                            commit_message=final_message or <applied default>,
                            commit_hash=commit)
switch branch: _enter_fresh_branch(..., final_todo, ...) then
  TopicHooks().emit_created(identity, checked_out=True, published=False,
                            todo=final_todo, commit_message=None,
                            commit_hash=None)
publication branch: publish_topic(branch_name, final_todo, base_ref,
                                  final_message, year)
```

Draft-message composition (from the design trace, step 6):
`publishing` → the applied template
`(commit_message or _DEFAULT_COMMIT_MESSAGE).replace("{slug}", slug)`
— the `or` predicate deliberately normalizes an empty template to the
built-in default here, so the delegated publication lands the default
(a direct `publish_topic` call keeps its own `is not None` predicate —
behavior preserved there; this is the one documented exception);
no-switch → the applied built-in default; switch path → `None` (D4 —
the tool sees and amends the actual text, with the `{slug}` placeholder
already replaced).

D3 (effective commit message): a hook may null the draft commit message
(`amend(None, ...)`); on a commit-building path the built-in domain
default then applies (the existing `_plant_topic_branch` fallback), and
the emission reports the message that lands in git
(`final_message or <applied default>`).

Test scenarios (from the design):

`test_create_topic_no_switch_emits_created_with_commit_hash`:
```
Setup: git boundary mocked at the import point (empty inventory,
current branch main, occupancy free, base resolved, plant wired to a
recording mock returning "deadbeef"); sys.stdin pinned to an
interactive terminal (isatty -> True, the tests/topics precedent) so
the editor-todo resolution runs; edit_text -> "the todo";
enumeration pinned with a topic_created recorder; registry reset.
Input: create_topic("Feature/Foo_Bar", "HEAD", todo=None, year="2026")
(interactive terminal pinned; the editor stubbed).
Trace:
_create_topic -> preflight free; resolved_todo "the todo"; ask False (publish False)
-> amend_creation(identity(slug "feature-foo-bar", 2026, "Feature/Foo_Bar"),
   checked_out False, published False, commit_message "goga: create topic feature-foo-bar",
   todo "the todo") -> unamended (no subscriber)
-> _plant_topic_branch(... final values ...) returns "deadbeef"
-> emit_created(identity, False, False, "the todo", <applied default>, "deadbeef")
returns "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
Assertions:
result line unchanged
recorded context.commit_hash == "deadbeef"
recorded context.commit_message == "goga: create topic feature-foo-bar"
recorded context.todo == "the todo"; checked_out False; published False
plant mock called once (mutation order unchanged)
Sufficiency: the no-switch path's checkpoint wiring — the hash comes
from the existing plant return (no new git read) and the identity facts
come from the operation's own data.
```

`test_create_topic_failed_preflight_fires_nothing` (negative):
```
Setup: occupancy conflict wired (check_branch_occupancy -> a
reason); recorders for all seven actions; registry reset.
Input: create_topic("Feature/Foo_Bar", "HEAD", todo="x",
year="2026").
Trace: preflight conflict -> ClickException before any input-driven step.
Assertions:
pytest.raises(click.ClickException)
recorded emissions and amendments == []
Sufficiency: "a failed creation fires nothing" — the amendment
delivers only immediately before the first mutation, never before the
decisions.
```

`test_create_topic_switch_path_amended_null_todo_degrades_gracefully` (edge):
```
Setup: switch=True, todo resolved, inventory free; a tool whose
amend_creation hook calls context.amend(None, None) (nulls the
todo); recorders; registry reset.
Input: create_topic("Feature/Foo_Bar", "HEAD", todo="the todo",
switch=True, year="2026").
Trace:
amendment commits (None, None) -> final_todo None
switch path: branch planted+checked out, dir ensured, no todo write
-> emit_created(identity, True, False, None, None, None)
Assertions:
topic_created fired once with todo None
todo.md absent (nothing written)
result line unchanged
Sufficiency: the switch path's todo is optional — a nulled amended
todo degrades gracefully and the notification reports the truth.
```

### Task 9: `publish_topic` — the publication pair (TDD coding)

**Cell**: `goga/topics`. **Entities**: `publish_topic` (checkpoint
wiring inside `_publish_topic`). **Locations**:
`goga/topics/publishing.py` (modify), `tests/topics/test_publishing.py`
(extend).

The routine is also the delegate of the creation's publication path.
Guards unchanged; nothing fires before the mutation chain. The plant
call is replaced by the applied-message computation plus hash capture;
a failed push rolls the branch back and surfaces the clean error —
nothing fires. After the successful push: `topic_created` then
`topic_published`.

**Usages relevant to this task:**
- `convention`: relative imports (`from .hooks import TopicHooks,
  TopicIdentity`), mock boundaries (git boundary mocked at the import
  point).
- `topic-paths`: the slug, current-branch, and todo-file path patterns.
- `publishing` (`goga/topics/git/.usages/publishing.md`): the
  quarantined commit building, branch planting, publication, and
  rollback patterns.
- `checkpoints`: the publication notifications fire only after the push
  succeeds, in the fixed order, with the identical final facts.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: the public signature and result line are unchanged — the existing contract tests of `tests/topics/test_publishing.py` keep passing unmodified; add the facade re-export check if absent (expected to fail at this stage only for the new wiring)
- [ ] **Code**: rework `_publish_topic` in `goga/topics/publishing.py` per the algorithm below — the applied message computed once, the plant hash captured, the two emissions after the successful push
- [ ] **Interface verification**: `pytest tests/topics/test_publishing.py -v` — all pass
- [ ] **Logic tests**: the two design scenarios below — `test_publish_topic_emits_created_then_published_after_push` (positive), `test_publish_topic_rollback_fires_nothing` (negative)
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: both contexts carry the same final message/hash/todo; rollback fires nothing; a direct call publishes without `amend_creation` (the creation amendment belongs to the creating orchestration)
- [ ] **Lint**: `ruff check goga/topics` — fix formatting if necessary

Algorithm (from the design):

```
_publish_topic — replace the plant call:
  applied = (commit_message if commit_message is not None
             else _DEFAULT_COMMIT_MESSAGE).replace("{slug}", slug)
  commit = _plant_topic_branch(branch_name, todo, base_commit, slug,
                               resolved_year, applied)
  push; on failure the existing rollback — nothing fires
after the successful push:
  identity = TopicIdentity(slug, resolved_year, branch_name)
  TopicHooks().emit_created(identity, checked_out=False, published=True,
                            todo=todo, commit_message=applied,
                            commit_hash=commit)
  TopicHooks().emit_published(identity, commit_message=applied,
                              commit_hash=commit, todo=todo)

Edge case: a direct CLI call publishes without amend_creation (the
creation amendment belongs to the creating orchestration).
```

Note: `_plant_topic_branch` keeps its internal
`message.replace("{slug}", slug)` — on an already-applied text without
the placeholder it is a no-op.

Test scenarios (from the design):

`test_publish_topic_emits_created_then_published_after_push`:
```
Setup: git boundary mocked (occupancy free, origin configured, base
resolved, plant -> "cafe123", push succeeding); enumeration pinned with
recorders for both actions; registry reset.
Input: publish_topic("Feature/Foo_Bar", "the todo", "HEAD",
year="2026").
Trace:
_publish_topic -> guards pass
-> applied = "goga: create topic feature-foo-bar"
-> commit = _plant_topic_branch(..., applied) -> "cafe123"
-> push_branch OK
-> emit_created(identity, False, True, "the todo", applied, "cafe123")
-> emit_published(identity, applied, "cafe123", "the todo")
returns the unchanged line
Assertions:
emission order == ["topic_created", "topic_published"]
both contexts carry commit_hash "cafe123", commit_message applied, todo "the todo"
created.checked_out False; created.published True
Sufficiency: the publication pair fires only after the push, in the
fixed order, with the identical final facts — the contract's central
ordering guarantee.
```

`test_publish_topic_rollback_fires_nothing` (negative):
```
Setup: git boundary mocked with push_branch raising
CalledProcessError (rollback recorded); both action recorders
installed; registry reset.
Input: publish_topic("Feature/Foo_Bar", "the todo", "HEAD",
year="2026").
Trace: plant OK -> push raises -> delete_local_branch (rollback) -> ClickException
Assertions:
pytest.raises(click.ClickException)
recorded emissions == []          # nothing fired on the failure
delete_local_branch called once   # the rollback still runs
Sufficiency: a rolled-back publication must leave no event trail —
tools would otherwise record a publication that does not exist.
```

### Task 10: `switch_topic` — the switch notification (TDD coding)

**Cell**: `goga/topics`. **Entities**: `switch_topic` (checkpoint wiring
inside `_switch_topic` and the outcome mapping of `_apply_candidate`).
**Locations**: `goga/topics/switching.py` (modify),
`tests/topics/test_switching.py` (extend — including the existing
`enter_topic_todo` mock assertions for the new `branch=` keyword).

`_apply_candidate` returns `(line, outcome)` — the three existing
return branches map one-to-one onto the kinds; the lines are unchanged.
The emission sits after `_apply_candidate` on every path — the
idempotent already-on-branch included. The branch fact (D2): the
identity's `branch` for `topic_switched` is the branch the working copy
is on after the switch — the candidate's display name for local
candidates, its short name for a remote-tracking candidate — the same
fact step 7 passes into `enter_topic_todo`.

**Usages relevant to this task:**
- `convention`: relative imports (`from .hooks import TopicHooks,
  TopicIdentity`), mock boundaries.
- `click`: the numbered selection prompt and the non-interactive
  detection — unchanged; pinned by the test setups (interactive terminal
  pinned for the todo flows).
- `refs-and-switching` (`goga/topics/git/.usages/refs-and-switching.md`):
  the checkout and remote-tracking branch patterns.
- `checkpoints`: the switch notification after the completed switch,
  every outcome included; the identity degrades to branch-only when the
  chosen candidate hosts no topic.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: the public signature and result lines are unchanged — the existing contract tests of `tests/topics/test_switching.py` keep passing; extend the existing `enter_topic_todo` mock assertions for the new `branch=` keyword (expected to fail at this stage)
- [ ] **Code**: rework `_apply_candidate` to return `(line, outcome)` with the three-kind mapping, and `_switch_topic` per the algorithm below — the branch fact, the identity, the emission, the branch kwarg of the entry
- [ ] **Interface verification**: `pytest tests/topics/test_switching.py -v` — all pass
- [ ] **Logic tests**: the two design scenarios below — `test_switch_topic_emits_switched_for_every_outcome` (positive, parametrized over the three inventory scenarios plus the topic-less branch), `test_switch_todo_onto_topicless_branch_fires_nothing` (negative)
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: `topic_switched` fires on every completed switch; branch-only identity when the candidate hosts no topic; identity facts from the operation's own data (candidate's hosted slug, resolved year, branch name — no git reads); the `todo` no-topic guard fires before any mutation and emits nothing
- [ ] **Lint**: `ruff check goga/topics` — fix formatting if necessary

Algorithm (from the design):

```
_apply_candidate(chosen) -> (line, outcome):
  already-on-branch  -> ("Already on branch X", "already-on-branch")
  local checkout     -> ("Switched to branch X", "local-checkout")
  remote creation    -> ("Created branch <short> from X", "created-from-remote")
  (the lines unchanged; the outcome mapping added)

_switch_topic — after the mutation, before the todo entry:
  branch_fact = _short_name(chosen.branch) if chosen.remote else chosen.branch
  identity = TopicIdentity(slug=chosen.topic, year=resolved_year,
                           branch=branch_fact)
  TopicHooks().emit_switched(identity, outcome)
  IF todo: enter_topic_todo(chosen.topic, year, branch=branch_fact)

Edge cases: the idempotent already-on-branch outcome still emits; the
todo no-topic guard fires before any mutation and emits nothing.
```

Test scenarios (from the design):

`test_switch_topic_emits_switched_for_every_outcome` (parametrized):
```
Setup: three inventory scenarios — (a) already on feature-foo;
(b) local branch feature-foo not current; (c) remote-tracking
origin/feature-foo only; tree-clean probe True; a topic_switched
recorder; registry reset.
Input: switch_topic("feature-foo", year="2026") per scenario
(candidate hosts topic feature-foo in (a)/(b); a fourth parametrization
uses a topic-less branch).
Trace (scenario c):
_switch_topic -> chosen = origin/feature-foo (remote, topic feature-foo)
-> create_branch_from_remote_tracking(...)   # line unchanged
-> branch_fact = "feature-foo" (short name)
-> emit_switched(TopicIdentity("feature-foo", "2026", "feature-foo"),
                 "created-from-remote")
returns "Created branch feature-foo from origin/feature-foo"
Assertions:
(a) outcome "already-on-branch"; (b) "local-checkout"; (c) "created-from-remote"
topic-less branch: identity.slug is None; identity.home_path is None;
  identity.branch == the branch name
all lines unchanged
Sufficiency: every completed switch fires exactly once, the idempotent
outcome included, and the branch-only degradation works — the marginal
corner of the switch contract.
```

`test_switch_todo_onto_topicless_branch_fires_nothing` (negative):
```
Setup: one candidate bare-branch (topic None) with interactive
terminal; recorders installed; registry reset.
Input: switch_topic("bare-branch", todo=True, year="2026").
Trace: chosen.topic is None and todo -> clean error before any mutation.
Assertions:
pytest.raises(click.ClickException, match="hosts no topic")
recorded checkpoints == []
Sufficiency: the pre-mutation guard must also suppress the switch
notification — the only switch path that fires nothing.
```

### Task 11: `ensure_topic` — the fast-creation checkpoints and the branch facts (TDD coding)

**Cell**: `goga/topics`. **Entities**: `ensure_topic` (checkpoint wiring
inside `_create_fresh_work` and `_enter_switched_todo`).
**Locations**: `goga/topics/ensuring.py` (modify),
`tests/topics/test_ensuring.py` (extend — including the existing
`enter_topic_todo` mock assertions for the new `branch=` keyword).

The fast creation delivers the identity-only creation amendment
immediately before `create_and_switch_branch` (the first mutation) and
deliberately does not read the returned holder — D8: an amended todo
does not land on this path (the todo resolves later through the entry's
own `amend_todo_entry`, which owns the written text), and
`commit_message` stays None (the path builds no commit). The todo entry
uses the private mirror `_enter_topic_todo` (D6) so the final todo
feeds the `topic_created` emission.

**Usages relevant to this task:**
- `convention`: relative imports (`from .creation import
  _enter_topic_todo` — the private mirror, internal to the cell;
  `from .hooks import TopicHooks, TopicIdentity`), mock boundaries
  (`sys.stdin` isatty pin for the editor-todo path).
- `click`: the interactive moments inherited from the switch
  orchestration.
- `topic-paths`: the slug and topic-directory patterns of the creation.
- `refs-and-switching`: the checkout and create-and-switch patterns.
- `checkpoints`: the creation amendment and the creation notification of
  the fast creation — the file's advisory-amendment clause documents D8
  for tool authors.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: the public signature and result line are unchanged — the existing contract tests of `tests/topics/test_ensuring.py` keep passing; extend the existing `enter_topic_todo` mock assertions for the new `branch=` keyword (expected to fail at this stage)
- [ ] **Code**: rework `_create_fresh_work` and `_enter_switched_todo` in `goga/topics/ensuring.py` per the algorithm below
- [ ] **Interface verification**: `pytest tests/topics/test_ensuring.py -v` — all pass
- [ ] **Logic tests**: the two design scenarios below — `test_ensure_fast_creation_amends_identity_only_and_emits_after_entry` (positive), `test_ensure_todo_on_topicless_branch_fires_only_the_entry_pair` (edge)
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the fast creation delivers the creation amendment exactly once, immediately before its first mutation, and emits `topic_created` after the creation completes (the identity-only amendment form is the norm on this path); directory creation under the todo flag of a topic-less branch fires no creation checkpoint — the todo entry alone fires its two; the todo entries pass the operation's branch fact; one registry across `ensure → switch → entry` (D1)
- [ ] **Lint**: `ruff check goga/topics` — fix formatting if necessary

Algorithm (from the design):

```
_create_fresh_work — after the oracles, before create_and_switch_branch:
  identity = TopicIdentity(slug, resolved_year, identifier)
  TopicHooks().amend_creation(identity, checked_out=True, published=False,
                              commit_message=None, todo=None)
  # the returned holder stays unread — the creation amendment observes
  # only on this path (D8): the todo-entry amendment owns the written
  # text, and the path builds no commit
  create_and_switch_branch(identifier); ensure_topic_dir(identifier, year)
  final_todo = _enter_topic_todo(identifier, year, branch=identifier) IF todo
  TopicHooks().emit_created(identity, checked_out=True, published=False,
                            todo=final_todo, commit_message=None,
                            commit_hash=None)

_enter_switched_todo — the entry calls gain the branch fact:
  hosted topic     -> enter_topic_todo(topic, year, branch=current)
  fresh directory  -> ensure_topic_dir(current, year);
                       enter_topic_todo(current, year, branch=current)

Edge cases: the directory creation of a topic-less branch fires no
creation checkpoint; the todo entry alone fires its two.
```

Test scenarios (from the design):

`test_ensure_fast_creation_amends_identity_only_and_emits_after_entry`:
```
Setup: empty inventory (zero candidates), tree-clean True;
create_and_switch_branch recorded; sys.stdin pinned to an
interactive terminal (isatty -> True, the tests/topics precedent);
edit_text -> "fresh todo";
enumeration pinned with amend_creation/topic_created/
amend_todo_entry/topic_todo_entered recorders; registry reset.
Input: ensure_topic("New_Work", todo=True, year="2026").
Trace:
_ensure_topic -> zero candidates -> _create_fresh_work
-> slug "new-work", oracles free
-> amend_creation(TopicIdentity("new-work","2026","New_Work"),
   checked_out True, published False, commit_message None, todo None)
-> create_and_switch_branch("New_Work"); ensure_topic_dir
-> _enter_topic_todo("New_Work", "2026", branch="New_Work") -> "fresh todo"
-> emit_created(identity, True, False, "fresh todo", None, None)
Assertions:
amend_creation recorded once, before create_and_switch_branch (call order)
its context.commit_message is None and context.todo is None (identity-only)
topic_created context.todo == "fresh todo"; commit_hash None; checked_out True
topic_todo_entered fired with identity.branch "New_Work"
result line unchanged
Sufficiency: the fast-creation corner — identity-only amendment
before the first mutation, notification after the entry with the final
todo, all from one registry build.
```

`test_ensure_todo_on_topicless_branch_fires_only_the_entry_pair` (edge):
```
Setup: one candidate bare-branch (topic None), tree-clean,
current branch becomes bare-branch after the switch; edit_text ->
"fresh"; recorders for all seven actions; registry reset.
Input: ensure_topic("bare-branch", todo=True, year="2026").
Trace:
switch_topic -> emit_switched(branch-only identity)      # the switch's own event
-> _enter_switched_todo: no hosted topic -> ensure_topic_dir(current)
-> _enter_topic_todo(current, year, branch=current)
   -> amend_todo_entry(derived identity) -> emit_todo_entered
no amend_creation / topic_created anywhere
Assertions:
fired actions == ["topic_switched", "topic_todo_entered"]
topic_todo_entered identity.slug == "bare-branch" (derived) and
  identity.branch == "bare-branch"
topic_created not recorded
Sufficiency: the marginal corner of the ensure contract — the
directory creation of a topic-less branch fires no creation
checkpoint; the entry alone fires its two.
```

### Task 12: `delete_topics` — the per-target deletion notification (TDD coding)

**Cell**: `goga/topics`. **Entities**: `delete_topics` (checkpoint
wiring inside `_delete_topics`). **Locations**:
`goga/topics/deletion.py` (modify), `tests/topics/test_deletion.py`
(extend).

The removal steps are unchanged — a failure mid-target restores and
raises before the emission. The new step fires inside the per-target
loop after the directory removal.

**Usages relevant to this task:**
- `convention`: relative imports (`from .hooks import TopicHooks,
  TopicIdentity`), mock boundaries (`remove_topic_dir` real over
  `tmp_path`; deletions recorded).
- `deleting` (`goga/topics/git/.usages/deleting.md`): the symmetric
  local-and-origin removal and the restore-on-failure patterns.
- `checkpoints`: the deletion notification after the target's full
  removal, with the removal composition; no branch fact on the identity;
  no deleted-commit hash carried.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: the public signature and result line are unchanged — the existing contract tests of `tests/topics/test_deletion.py` keep passing (expected to fail at this stage only for the new wiring)
- [ ] **Code**: extend the per-target loop of `_delete_topics` in `goga/topics/deletion.py` per the algorithm below
- [ ] **Interface verification**: `pytest tests/topics/test_deletion.py -v` — all pass
- [ ] **Logic tests**: the design scenario below — `test_delete_topics_emits_per_target_after_full_removal` (positive; covers the directory-less and remote-only target shapes as edge cases)
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: a target fires after its complete removal; targets fully removed before a later failure already fired theirs; a target whose removal fails midway fires nothing (the restore path raises before the emission); no commit hash carried
- [ ] **Lint**: `ruff check goga/topics` — fix formatting if necessary

Algorithm (from the design):

```
_delete_topics — inside the per-target loop, after the directory removal:
  directory_removed = (remove_topic_dir(target.topic, resolved_year)
                       if target.has_dir else False)
  identity = TopicIdentity(slug=target.topic, year=resolved_year, branch=None)
  TopicHooks().emit_deleted(identity, local_branch=target.branch,
                            origin_twin=target.remote,
                            directory_removed=directory_removed)

Edge cases: a remote-only target (branch=None) still fires with its
twin name; a directory-less target reports directory_removed=False.
```

Test scenario (from the design):

`test_delete_topics_emits_per_target_after_full_removal`:
```
Setup: two targets
(DeleteTarget("one", branch="one", remote="one", has_dir=True),
DeleteTarget("two", branch=None, remote=None, has_dir=False)); git
boundary recorded (resolve_ref_commit -> hash, deletions succeeding,
remove_topic_dir real over tmp_path with .goga/history/2026/one/
created); a topic_deleted recorder; registry reset.
Input: delete_topics(targets, year="2026").
Trace:
_delete_topics
-> target one: capture commit, delete local, delete remote, remove dir -> True
   -> emit_deleted(identity(slug "one", 2026, branch None),
                   local_branch "one", origin_twin "one", directory_removed True)
-> target two: no branch, no twin, no dir -> emit_deleted(identity,
   local_branch None, origin_twin None, directory_removed False)
returns the unchanged line
Assertions:
two emissions, in target order
first: local_branch "one", origin_twin "one", directory_removed True
second: all-absent composition, directory_removed False
both identities: branch is None; home_path ".goga/history/2026/<slug>"
Sufficiency: the per-target timing and the removal-composition
mapping — including the directory-less and remote-only target shapes.
```

### Task 13: Documentation synchronization (infrastructure)

**Scope**: the seven-action reference for tool authors and the
declared-actions lists. **Locations**: `docs/features/topics/hooks.md`
(replace the stub), `docs/features/hooks/index.md`,
`docs/features/hooks/hooks.md`, `docs/features/tools/hooks.md` (extend
the declared-actions lists). No `mkdocs.yml` nav change (the page
exists).

The current `docs/features/topics/hooks.md` states the topics domain
exposes no hook actions — after this plan it exposes seven. The three
declared-actions lists enumerate the catalog per domain; the topics
domain joins them.

**Usages relevant to this task:**
- `checkpoints` (`goga/topics/hooks/.usages/checkpoints.md`): the
  authoritative consumer description of the surface — the reference page
  restates it for tool authors (the checkpoint moments, the context
  surfaces, the amendment contract).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Replace the stub `docs/features/topics/hooks.md` with the seven-action reference: the checkpoint moments (amend before fixation, emit after the moment), the context surfaces (the five notification contexts and the two amendment views with their fields), and the amendment contract (whole replacement, empty/whitespace rejection, soft failure, the advisory-amendment note of the ensure fast path)
- [ ] Add the topics domain (the seven actions with their error class) to the declared-actions lists in `docs/features/hooks/index.md`, `docs/features/hooks/hooks.md`, and `docs/features/tools/hooks.md`
- [ ] Verify: `mkdocs build` stays green (or the project's docs validation command), and every documented action name matches `declared_actions()` exactly
- [ ] No `mkdocs.yml` change — the page exists in the nav

### Task 14: Cross-cell integration validation (integration tests)

**Scope**: the whole feature across the three cells — zone, domain
wiring, catalog, docs. All named scenarios already landed in Tasks 1–12;
this task verifies the assembled whole against the contract-level
guarantees and the goga tooling.

**Usages relevant to this task:**
- `convention`: the validation commands table — all commands run in a
  virtualenv; Python 3.10+ compatibility.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Run the full suite: `pytest tests/ -x` — green (all 26 named scenarios plus the existing tests; the platform, the zone, and the domain tests run together — proving no registry/subscription leak and no import cycle)
- [ ] Facade check: `python -c "from goga.topics.hooks import TopicHooks, TopicIdentity, CreationDraft, TodoEntryDraft, TopicCreated, TopicPublished, TopicSwitched, TopicTodoEntered, TopicDeleted, CreationAmendment, TodoEntryAmendment"` — passes
- [ ] Catalog surface: `goga hooks` lists the seven topics actions (all soft) with no command change
- [ ] Manifest validation: `goga lint` — 0 errors (stays at the design-time baseline); `goga schema goga/topics` resolves the `goga/topics/hooks` subcell and shows `goga/topics` importing it
- [ ] Behavior preservation sweep: the result lines, error messages, and mutation order of the six routines are unchanged — re-run the pre-existing domain tests untouched by the checkpoint additions and confirm no assertion was weakened to accommodate the wiring

---

## Validation Commands

- `pytest tests/ -x`: Run all tests
- `pytest tests/hooks/catalog/test_catalog.py -v`: Catalog contract and records
- `pytest tests/topics/hooks/ -v`: Zone tests (identity, contexts, amendments, events)
- `pytest tests/topics/ -v`: Domain tests (creation, publishing, switching, ensuring, deletion)
- `ruff check goga/hooks/catalog goga/topics`: Lint the touched sources
- `python -c "from goga.topics.hooks import TopicHooks, TopicIdentity, CreationDraft, TodoEntryDraft, TopicCreated, TopicPublished, TopicSwitched, TopicTodoEntered, TopicDeleted, CreationAmendment, TodoEntryAmendment"`: Facade accessibility of the eleven zone names
- `goga hooks`: The seven topics actions are listed (no command change)
- `goga lint`: Manifest validation stays at 0 errors
- `goga schema goga/topics`: The `goga/topics/hooks` subcell resolves and `goga/topics` imports it

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`identity.py`, `contexts.py`, `amendments.py`, `events.py`, `__init__.py` of the zone; the six domain routines in their existing files)
- [ ] Every contract entity is accessible from the facade (the eleven zone names in `__all__`; the six routines from `goga.topics`)
- [ ] Properties and methods match the declared API (kw-only constructors; frozen identity/contexts; mutable holders/views with the private `_draft`/`_buffered` fields)
- [ ] Descriptions are reflected in behavior (the walks' commit/rejection rules, the emissions' same-instance delivery, the domain checkpoint moments per the traces)
- [ ] Contract dependencies are met (the five platform names and `resolve_topic_dir` import through the declared facades; no new import cycle)
- [ ] Re-exports are accessible from the facade (no DSL re-export blocks exist; the language-level facade obligations hold)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task (all 26 named scenarios plus per-task contract tests)
- [ ] Integration tests exist where cross-entity scenarios require them (Task 14; the cross-flow scenarios landed in Tasks 6, 10, 11)
- [ ] No package boundary was expanded (no new cells, no changes to `goga/commands/**` or the platform cells `goga/hooks/{dispatch,registry,tools}`)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (`convention` — all tasks; `declaring-actions`, `per-tool-delivery`, `registering-hooks` — Tasks 1, 5, 6; `topic-paths` — Tasks 3, 7, 8, 9, 11; `checkpoints` — Tasks 7–13; `click` — Tasks 8, 10, 11; `editor-entry` — Tasks 7, 8; `refs-and-switching` — Tasks 8, 10, 11; `publishing` — Tasks 8, 9; `deleting` — Task 12; `topic-statuses` — untouched by this plan, noted in Usages Context)
