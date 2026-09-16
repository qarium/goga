# Design Document: `add-topics-hooks`

Seven platform hook actions for the topics lifecycle: five post-fact
notifications over the plain emission, two pre-fixation amendments over a
per-hook staged delivery, home-path identity, no-read contexts. This
document specifies **what to implement and how** — the complete
architectural specification derived from the CODEMANIFEST changes
materialized by the architecture plan. No implementation code is written
at this stage.

Design target path: `.goga/history/2026/add-topics-hooks/design.md`
(this file).

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST`: the `Requirements` of
  `declared_actions` grew from 5 to 12 bullets — seven topics records
  appended (all `domain="topics"`, `error_class="soft"`): `topic_created`,
  `topic_published`, `topic_switched`, `topic_todo_entered`,
  `topic_deleted`, `amend_creation`, `amend_todo_entry`. Algorithm,
  Constraints, `Action`, header, and footer unchanged.
- `goga/topics/CODEMANIFEST`: new `Imports` block from `goga/topics/hooks`
  (`TopicIdentity`, `TopicHooks`, `CreationDraft`, `TodoEntryDraft` + the
  `checkpoints` practice); global annotations extended (the `checkpoints`
  practice paragraph and the hooks-zone sentences); annotations of six
  routines reworked — `enter_topic_todo` (signature gains
  `branch: str | None = None`), `create_topic`, `publish_topic`,
  `switch_topic`, `ensure_topic`, `delete_topics`; footer Description gains
  the lifecycle-events clause.
- `goga/topics/hooks/CODEMANIFEST`: CREATED — 11 types across
  `identity.py`, `contexts.py`, `amendments.py`, `events.py`, with
  `Imports` from `goga/hooks` (5 Types + 3 Usages) and `goga/history`
  (`resolve_topic_dir` + `topic-paths`).

### New Entities

Cell `goga/topics/hooks` (all new code — the directory currently holds
only `CODEMANIFEST`):

- `TopicIdentity(slug, year, branch)` — `identity.py` — the identity
  vocabulary of every topics event; `home_path` composed purely from
  `slug` + `year` through `resolve_topic_dir`.
- `TopicCreated(identity, checked_out, published, todo, commit_message, commit_hash)` — `contexts.py` — read-only creation facts.
- `TopicPublished(identity, commit_message, commit_hash, todo)` — `contexts.py` — read-only publication facts.
- `TopicSwitched(identity, outcome)` — `contexts.py` — read-only switch facts; `outcome` is exactly one of `local-checkout`, `created-from-remote`, `already-on-branch`.
- `TopicTodoEntered(identity, text)` — `contexts.py` — read-only todo-entry facts.
- `TopicDeleted(identity, local_branch, origin_twin, directory_removed)` — `contexts.py` — read-only deletion facts.
- `CreationDraft(commit_message, todo)` — `amendments.py` — the shared mutable holder of the creation amendment.
- `TodoEntryDraft(text)` — `amendments.py` — the shared mutable holder of the todo-entry amendment.
- `CreationAmendment(identity, checked_out, published, draft)` — `amendments.py` — the per-hook read view over the live holder, with `amend(commit_message, todo)` buffering a whole replacement.
- `TodoEntryAmendment(identity, draft)` — `amendments.py` — the per-hook read view over the live holder, with `amend(text)` buffering a whole replacement.
- `TopicHooks()` — `events.py` — the checkpoint surface: `amend_creation`, `amend_todo_entry`, `emit_created`, `emit_published`, `emit_switched`, `emit_todo_entered`, `emit_deleted`.

### Changed Entities

- `declared_actions` (`goga/hooks/catalog`, `catalog.py`) — the runtime
  constant `_DECLARED_ACTIONS` gains the seven topics records; the
  routine itself is unchanged.
- `enter_topic_todo` (`goga/topics`, `creation.py`) — signature gains
  `branch: str | None = None`; the saved text passes through
  `amend_todo_entry` before the write; a completed entry emits
  `topic_todo_entered`.
- `create_topic` (`goga/topics`, `creation.py`) — step 6 delivers
  `amend_creation` immediately before the first mutation of the chosen
  path; the no-switch path captures the planted commit hash and emits
  `topic_created`; the switch path emits `topic_created` after its last
  mutation; the publication path delegates with the amended values.
- `publish_topic` (`goga/topics`, `publishing.py`) — captures the
  publication commit hash; after the successful push emits
  `topic_created` then `topic_published`; a rolled-back publication fires
  nothing.
- `switch_topic` (`goga/topics`, `switching.py`) — emits `topic_switched`
  on every completed switch with the outcome kind; the todo entry receives
  the switched branch as the branch fact.
- `ensure_topic` (`goga/topics`, `ensuring.py`) — the fast creation
  delivers the identity-only `amend_creation` immediately before its
  first mutation and emits `topic_created` after the creation completes;
  the todo entries pass the operation's branch fact.
- `delete_topics` (`goga/topics`, `deletion.py`) — emits `topic_deleted`
  after each target's full removal with the removal composition.

### Deleted Entities

None.

### Usages and Annotations Changes

- `goga/topics/hooks/.usages/checkpoints.md` — CREATED (consumer
  practice: the checkpoint surface, amend-before-fixed,
  emit-after-moment).
- `goga/topics/.usages/todo-entry.md` — one clause added: the written
  content is the final amended text when a tool subscribes an amendment
  hook.
- `goga/topics/.usages/creating.md` — one clause added: the written
  todo.md content and the built commit message are the final amended
  values.
- Annotation-level: the `checkpoints` practice line added to the global
  annotations and to each of the six reworked routines (see the changed
  files above).

## Applied Fixes

### Fixed CODEMANIFEST Defects

None. The contract validation phase found no DSL defects:

- `goga lint`: 77 cells, 0 errors.
- Structure: header/body/footer with `---` separators, key casing,
  `location` values (same-level `.py` files), and signature types are
  valid per `goga-cell`.
- All `Imports` targets resolve: the five types exist on the
  `goga/hooks` facade (`goga/hooks/__init__.py` re-exports
  `HookRegistry`, `emit_hook_event`, `wrap_context`, `build_hook_arguments`,
  `declared_actions`); `resolve_topic_dir` exists on the `goga/history`
  facade; all imported usages exist (`goga/hooks/.usages/{declaring-actions,
  per-tool-delivery,registering-hooks}.md`, `goga/history/.usages/topic-paths.md`,
  `.goga/usages/conventions.md`).
- Entity/Routine selection and practice connection conform to
  `goga-cookbook`: every connected practice is referenced in at least one
  annotation; no unreferenced practice; no mutation (`::`) or embedding
  (`->`) is used, correctly.
- The four consistency dimensions (interface↔type, type↔mutation,
  interface↔interface, annotations↔entity) hold — verified against the
  actual platform surface (`goga/hooks/dispatch/emit.py`,
  `goga/hooks/registry/state.py`) and the onboarding per-tool-delivery
  precedent (`goga/onboarding/participation/participation.py`).

The items below are **design decisions inside the contract's explicit
freedom** (recorded here, not CODEMANIFEST defects). The most important:

1. **One registry per run** (D1): `TopicHooks` shares a module-level
   lazily-built `HookRegistry` in `events.py` — the CODEMANIFEST leaves
   "the transport of the shared `HookRegistry`" an implementation detail,
   and per-instance registries would multiply the package enumeration
   across the nested public calls (`ensure_topic` → `switch_topic` →
   `enter_topic_todo`; `create_topic` → `publish_topic`).
2. **Switch branch fact** (D2): the identity's `branch` for
   `topic_switched` is the branch the working copy is on after the
   switch — the candidate's display name for local candidates, its short
   name for a remote-tracking candidate — the same fact step 7 passes
   into `enter_topic_todo` ("the switched branch").
3. **Effective commit message** (D3): a hook may null the draft commit
   message (`amend(None, ...)`); on a commit-building path the built-in
   domain default then applies (the existing `_plant_topic_branch`
   fallback), and the emission reports the message that lands in git.
4. **Applied draft message** (D4): `amend_creation` receives the draft
   message with the `{slug}` placeholder already replaced — the tool sees
   and amends the actual text.
5. **Nulled todo on a todo-requiring path** (D5): the no-switch creation
   path re-raises its clean "needs a todo" error when the final amended
   todo is None (nothing has mutated yet — "a failed creation fires
   nothing" holds); the publication path's own guard covers its case.
6. **Private richer entry** (D6): `_enter_topic_todo` (the existing
   unwrapped mirror) returns the final written text (`str | None`) while
   the public `enter_topic_todo` keeps `-> written: bool` — `ensure_topic`
   needs the final todo for its `topic_created` emission.
7. **Error class honored from the catalog** (D7): the amendment walk
   resolves the address against `declared_actions()` and treats a raised
   hook failure per the record's error class exactly like
   `emit_hook_event` (all seven topics actions are soft today); the
   empty-amendment rejection always warns and continues — the CODEMANIFEST
   fixes that behavior unconditionally.
8. **Advisory amendment on the ensure fast path** (D8): the fast creation
   of `ensure_topic` delivers the identity-only creation amendment but
   deliberately does not read the returned holder — an amended todo does
   not land on this path. The todo resolves later through the entry's
   own `amend_todo_entry`, which owns the written text, and
   `commit_message` stays None (the path builds no commit). The
   `checkpoints` practice states this so a tool author is not surprised.

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

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

### Entity Dependencies

- `goga/hooks/catalog` — no imports (data only). Everything downstream
  resolves addresses against it.
- `goga/topics/hooks` — imports `goga/hooks` (facade) and
  `goga/history` (`resolve_topic_dir`). Imports neither its parent
  domain package nor any domain module — no cycle.
- `goga/topics` — imports `goga/topics/hooks` (the four types) in
  `creation.py`, `publishing.py`, `switching.py`, `ensuring.py`,
  `deletion.py` via the relative `from .hooks import ...`.
- Design order (implementation): `catalog.py` records →
  `goga/topics/hooks` (`identity.py` → `contexts.py` → `amendments.py`
  → `events.py` → `__init__.py`) → domain routine wiring → tests →
  docs.

## Code Stack Trace

### Trace: `declared_actions` (catalog extension)

#### Chain

1. **Input**: any checkpoint (`emit_hook_event`, the amendment walk) or
   the `goga hooks` command calls `declared_actions()`.
2. **Step**: the routine sorts `_DECLARED_ACTIONS` by
   `(domain, name)` → checkpoint: the seven appended records sort as
   `amend_creation`, `amend_todo_entry`, `topic_created`, `topic_deleted`,
   `topic_published`, `topic_switched`, `topic_todo_entered` after the
   onboarding and statuses groups — deterministic and complete ✓.
3. **Step**: address resolution in `emit.py:72-77`
   (`next(entry for entry in declared_actions() ...)`) finds
   `Action(domain="topics", name=..., error_class="soft")` for every
   address the zone emits → checkpoint: every emitted address resolves ✓
   (today `emit_hook_event` raises `ValueError` on an unknown address —
   the records must exist before any checkpoint fires, hence the
   implementation order).
4. **Output**: the 10-record list; `goga hooks` lists the topics domain
   with no command change ✓.

#### Checkpoint Summary

- Determinism and completeness: passed — maintained data, `sorted()`.
- Runtime gap: `_DECLARED_ACTIONS` (catalog.py:40-44) currently carries
  3 records — the implementation appends the seven (see Algorithm
  Design).

### Trace: `TopicIdentity` construction and `home_path`

#### Chain

1. **Input**: a domain routine builds
   `TopicIdentity(slug=..., year=..., branch=...)` — `slug` already
   normalized by the caller, `year` already resolved (four digits),
   `branch` the operation's branch fact.
2. **Step**: frozen kw-only dataclass stores the three fields →
   checkpoint: kw-only + frozen matches the `Action`/`Stage` data-model
   precedent and the conventions ✓.
3. **Step**: a hook (or the domain) reads `identity.home_path` →
   `None` when `slug is None` (branch-only form); otherwise
   `resolve_topic_dir(slug, year).as_posix()` → checkpoint:
   `resolve_topic_dir` re-normalizes its input — idempotent for an
   already-normalized slug ✓; the slug is non-None on this branch, so
   the empty-slug `ValueError` is unreachable ✓; nothing is read or
   created (pure composition) ✓; the result is the posix string
   `.goga/history/<year>/<slug>` the contract fixes ✓.
4. **Output**: the three attribute reads plus the composed
   `home_path`; attribute reads pass through the delivery proxy
   (`wrap_context` mediates plain attribute access) ✓.

#### Checkpoint Summary

- Type flow: `str | None` / `str` / `str | None` fields match every
  context constructor that carries `identity` — passed.
- No repository reads at composition — passed.

### Trace: the five notification contexts (`contexts.py`)

#### Chain

1. **Input**: an `emit_*` method constructs the context from the values
   the caller passed.
2. **Step**: frozen kw-only dataclass stores the facts → checkpoint:
   read-only — a hook observes and cannot alter (frozen; assignment also
   blocked on the delivery proxy) ✓.
3. **Step**: a hook reads `context.identity.home_path`,
   `context.commit_hash`, ... → plain attribute/property reads pass
   through the proxy ✓; `TopicSwitched.outcome` is exactly one of the
   three fixed kinds (the emitting routine constructs it from its
  outcome mapping — see `switch_topic`) ✓.
4. **Output**: observed facts only; no method surface, no write path.

#### Checkpoint Summary

- Interface↔type consistency with `emit_*` signatures — passed (field
  lists identical to the method parameters beyond `identity`).
- `TopicCreated.commit_message`/`commit_hash` "present exactly when the
  path builds a commit" — passed by construction on every emitting path
  (D3 keeps the message truthful).

### Trace: `CreationDraft` / `TodoEntryDraft` holders

#### Chain

1. **Input**: `amend_creation` creates `CreationDraft(commit_message=...,
   todo=...)` with the path's draft values.
2. **Step**: kw-only dataclass (mutable — the `StatusRegistry`
   precedent) stores the content; the properties `commit_message`/`todo`
   read the live fields → checkpoint: content changes only through the
   delivery commit (`_commit`, private-by-convention) — the delivered
   views expose no write path, and `wrap_context` blocks assignment on
   the proxy ✓.
3. **Step**: after each hook's buffer commits, later views read the
   updated fields ("a later hook sees the committed amendments of the
   earlier hooks") ✓.
4. **Output**: the domain reads `draft.commit_message` / `draft.todo` /
   `draft.text` after the walk — the final amended values.

#### Checkpoint Summary

- Read-passthrough of the views — passed (views hold the same holder
  instance).
- Single mutation point — passed (the `_commit` of the walk).

### Trace: `CreationAmendment.amend` / `TodoEntryAmendment.amend`

#### Chain

1. **Input**: a hook calls `context.amend(commit_message=..., todo=...)`
   (or `context.amend(text=...)`) on the delivered proxy.
2. **Step**: the method call passes through `wrap_context` and runs on
   the view; the view buffers the whole replacement into its private
   `_buffered` field (`tuple[str | None, str | None] | None` /
   `str | None`) → checkpoint: the holder is untouched ("changes nothing
   until the delivery commits it") ✓; a repeated `amend` overwrites the
   buffer (whole replacement, last wins) ✓.
3. **Step**: the hook returns; the walk inspects `_buffered` → commit /
   reject decision (next trace).
4. **Output**: no return value; the buffer rides on the view.

#### Checkpoint Summary

- Constraint "do not cancel, redirect, or defer the operation" — the
  view carries no such method — passed.
- Buffer isolation per hook — passed (a fresh view per subscription).

### Trace: `TopicHooks.amend_creation` — the per-hook walk

#### Chain

1. **Input**: the domain calls
   `TopicHooks().amend_creation(identity, checked_out, published, commit_message, todo)`.
2. **Step**: `_run_registry()` returns the shared run registry,
   building it on first use (`HookRegistry()` + `build_once()`) →
   checkpoint: one build per run whatever the number of checkpoints
   (D1); a broken package import surfaces here as the single fatal
   `ImportError` ✓.
3. **Step**: resolve the address against `declared_actions()` — an
   unknown address is a clean `ValueError` of the emitting side
   (mirroring `emit.py:72-77`); the record's `error_class` is read ✓.
4. **Step**: create the shared `CreationDraft` with the draft values.
5. **Step**: for each `subscription` of
   `registry.subscriptions_for("topics", "amend_creation")`, in
   enumeration order — **no grouping by tool** (the per-hook refinement
   of the `per-tool-delivery` practice):
   1. build a fresh `CreationAmendment(identity=..., checked_out=...,
      published=..., draft=holder)` **outside** the failure intercept
      (a crashing view builder is the emitting side's bug, never a hook
      failure — the `context_for` placement of `emit.py:83-85`);
   2. inside one intercept (`Exception` only, mirroring
      `emit.py:87-95`): `wrap_context(view)` →
      `build_hook_arguments(subscription.hook, proxy,
      registry.self_context(subscription.tool))` →
      `subscription.hook(**arguments)` → checkpoint: the hook receives
      values only for the declared offered names (`context`, `self`) ✓;
      the tool's `self` context is the same instance across every
      checkpoint of the run (shared registry) ✓.
6. **Step**: a hook that raised → its buffer is discarded; per the
   record's error class: soft — `logger.warning("hook %s of tool %s
   failed on topics.amend_creation: %s", name, tool, reason)` and the
   walk continues; hard — `ValueError` in the same shape as
   `emit.py:97-99` (dead branch today — all seven records are soft).
7. **Step**: a hook that returned → read `view._buffered`; `None` →
   nothing to commit, next subscription. Otherwise reject the whole
   buffer when a structurally present field is empty or whitespace-only
   (`(cm is not None and not cm.strip()) or (todo is not None and not
   todo.strip())`) → the same warning with the reason
   `"the buffered amendment is empty or whitespace-only"`, walk
   continues. Else `holder._commit((cm, todo))` — the whole replacement.
8. **Output**: the holder returns to the caller — the last committed
   buffer, or the original draft values when nothing committed. An
   address without subscriptions returns the original values — not an
   error ✓.

#### Checkpoint Summary

- Per-hook independence ("two hooks of one tool never share a buffer or
  a failure") — passed: a fresh view per subscription, commit decided
  per subscription.
- Delivery never filtered — passed ("do not skip a subscriber").
- No post-walk application — passed (the caller fixes the final draft
  itself).

### Trace: `TopicHooks.amend_todo_entry`

Identical chain with `TodoEntryDraft`/`TodoEntryAmendment`, address
`topics.amend_todo_entry`, single `text` field; the buffer rejection
covers `text is None or not text.strip()` (the contract types `text` as
`str`; a None buffer value is treated as the rejection case). Output:
the holder with the final text.

### Trace: `TopicHooks.emit_created` / `emit_published` / `emit_switched` / `emit_todo_entered` / `emit_deleted`

#### Chain

1. **Input**: a domain routine calls the emit method with the final
   facts.
2. **Step**: build the frozen context from the values.
3. **Step**: `emit_hook_event(_run_registry(), "topics", "<action>",
   context_for=lambda _tool: context)` — the **same instance** for every
   receiving tool, each through its own delivery proxy → checkpoint:
   matches the CODEMANIFEST ("the context view of every receiving tool
   reads the same instance through the delivery proxy") and the
   `declaring-actions` practice ("return the same instance to share") ✓;
   the platform performs the registry build, the address resolution, the
   per-tool views, the projection, and the soft-failure warning ✓.
4. **Output**: `None` — fire-and-forget; nothing collected ✓.

#### Checkpoint Summary

- Signature alignment with `emit_hook_event(registry, domain, action,
  context_for)` — passed.
- All five addresses exist in the catalog after the extension — passed.

### Trace: `enter_topic_todo` (changed)

#### Chain

1. **Input**: `enter_topic_todo(topic, year=None, branch=None)` — from
   the CLI-driven flows via `switch_topic`/`ensure_topic` or direct
   consumer call.
2. **Step**: `resolved_year = year or current_year()`; resolve the
   todo.md path via `resolve_topic_file`; read the initial text if the
   file exists (UTF-8, replacement decode) → unchanged ✓.
3. **Step**: `saved = edit_text(initial)` → `None` (cancelled) →
   return `False` — nothing delivered, nothing emitted ✓.
4. **Step**: identity =
   `TopicIdentity(slug=normalize_topic_slug(topic), year=resolved_year,
   branch=branch)` → checkpoint: pure inputs — "the identity needs no
   repository reads" ✓ (`normalize_topic_slug` already imported in
   `creation.py`).
5. **Step**: `draft = TopicHooks().amend_todo_entry(identity, saved)` —
   delivery after the save, before the write ✓.
6. **Step**: `_write_todo(topic, resolved_year, draft.text)` — the
   single-trailing-newline rule applies to the final amended text →
   the write is the last mutation ✓.
7. **Step**: `TopicHooks().emit_todo_entered(identity, draft.text)` —
   the final written text is the reported text ✓; returns `True`.
8. **Output**: `written: bool`; the file carries the amended text; the
   notification fired.

Internal (D6): the existing unwrapped mirror `_enter_topic_todo(topic,
year, branch)` returns the final written text (`str | None`); the public
wrapper returns `written is not None`.

#### Checkpoint Summary

- Cancelled entry: no delivery, no emission, file untouched — passed.
- Emission follows the write and mutates nothing — passed.
- Error boundary: the `OSError` wrapper unchanged (the checkpoint code
  performs no I/O).

### Trace: `create_topic` (changed)

#### Chain

1. **Input**: `create_topic(branch_name, base_ref, todo, publish,
   commit_message, year, switch)` — unchanged signature.
2. **Steps 1–5** (preflight, todo resolution, publish/no-switch todo
   guards, publication ask): unchanged → checkpoint: every decision
   precedes the first mutation ✓; a failing preflight fires nothing ✓.
3. **Step 6** (new — the amendment): `identity =
   TopicIdentity(slug, resolved_year, branch_name)`; the chosen path is
   now known (`publishing = _publication_asked(...)`); the draft facts:
   - `checked_out = switch and not publishing`, `published = publishing`
     (D12 — the path facts);
   - draft message: `publishing` → the applied template
     `(commit_message or _DEFAULT_COMMIT_MESSAGE).replace("{slug}", slug)`
     — the `or` predicate deliberately normalizes an empty template to
     the built-in default here, so the delegated publication lands the
     default; a direct `publish_topic` call keeps its own
     `is not None` predicate — behavior preserved there;
     no-switch → the applied built-in default; switch path → `None` (D4);
   - draft todo: `resolved_todo`.
   `draft = TopicHooks().amend_creation(identity, checked_out,
   published, draft_message, resolved_todo)`; then
   `final_todo = draft.todo`, `final_message = draft.commit_message`
   → checkpoint: delivered exactly once, immediately before the first
   mutation of the chosen path ✓; identity-only form valid (switch path
   without a todo) ✓.
4. **Step 7** (no-switch): if `final_todo is None` → the same clean
   "the local creation needs a todo" error (D5 — nothing has mutated);
   else `commit = _plant_topic_branch(branch_name, final_todo,
   base_commit, slug, resolved_year, final_message)` — the helper
   already returns the commit hash; `final_message` is None only when a
   hook nulled it → the helper's built-in default applies (D3); then
   `emit_created(identity, checked_out=False, published=False,
   todo=final_todo, commit_message=final_message or applied_default,
   commit_hash=commit)` → checkpoint: the reported message is the
   message that lands in git ✓.
5. **Step 8** (switch): `_enter_fresh_branch(branch_name, base_commit,
   final_todo, year, resolved_year)` unchanged except it writes
   `final_todo`; after it returns → `emit_created(identity,
   checked_out=True, published=False, todo=final_todo,
   commit_message=None, commit_hash=None)` — "the final todo when
   written, and no commit facts" ✓.
6. **Step 9** (publication): `publish_topic(branch_name, final_todo,
   base_ref, final_message, year)` — the amended todo and the amended
   message travel as the template (the helper's `.replace("{slug}", ...)`
   is a no-op on an applied/amended text without the placeholder);
   nothing fires here — the delegated routine fires its checkpoints
   after its push ✓.
7. **Output**: the unchanged single result line; emissions add no
   output.

#### Checkpoint Summary

- "topic_created fires exactly once per successful creation" — no-switch
  and switch paths emit here; the publication path's emission lives in
  the delegate — passed.
- Amendment before the first mutation, once — passed.
- Existing behavior (result lines, error surface, mutation order)
  unchanged — passed.

### Trace: `publish_topic` (changed)

#### Chain

1. **Input**: `publish_topic(branch_name, todo, base_ref,
   commit_message, year)` — unchanged signature (also the delegate of
   the publication path).
2. **Steps 1–5** (guards, occupancy, origin, base resolution):
   unchanged; nothing fires before the mutation chain ✓.
3. **Step 6**: compute `applied = (commit_message if commit_message
   is not None else _DEFAULT_COMMIT_MESSAGE).replace("{slug}", slug)`
   once; `commit = _plant_topic_branch(branch_name, todo, base_commit,
   slug, resolved_year, applied)` — captures the returned hash →
   checkpoint: "no new git reads for events (the plant hash from the
   existing return value)" ✓.
4. **Step 7–8**: plant + push; a failed push rolls the branch back and
   surfaces the clean error — **nothing fires** ✓.
5. **Step 9** (after the successful push):
   `identity = TopicIdentity(slug, resolved_year, branch_name)`;
   `emit_created(identity, checked_out=False, published=True, todo=todo,
   commit_message=applied, commit_hash=commit)`; then
   `emit_published(identity, commit_message=applied,
   commit_hash=commit, todo=todo)` → checkpoint: the order
   topic_created → topic_published ✓; "a direct call publishes without
   amend_creation" — no amendment here ✓.
6. **Output**: the unchanged result line.

#### Checkpoint Summary

- Both contexts carry the same final message/hash/todo — passed.
- Rollback fires nothing — passed.

### Trace: `switch_topic` (changed)

#### Chain

1. **Input**: `switch_topic(identifier, todo, year)` — unchanged
   signature.
2. **Steps 1–5** (terminal guard, resolution, prompt, no-topic guard,
   cleanliness probe, checkout/creation): unchanged; the no-topic guard
   fires before any mutation — nothing fires ✓.
3. **Step 5 reworked internally**: `_apply_candidate(chosen)` now
   returns `(line, outcome)` with `outcome` ∈ {`already-on-branch`,
   `local-checkout`, `created-from-remote`} — the three existing return
   branches map one-to-one onto the kinds; the lines are unchanged.
4. **Step 6** (new): `branch_fact = _short_name(chosen.branch) if
   chosen.remote else chosen.branch` (the post-switch local branch —
   D2); `identity = TopicIdentity(slug=chosen.topic, year=resolved_year,
   branch=branch_fact)` — `chosen.topic` may be None → the branch-only
   identity ✓; `TopicHooks().emit_switched(identity, outcome)` — every
   outcome included, the idempotent already-on-branch too ✓.
5. **Step 7**: with `todo` → `enter_topic_todo(chosen.topic, year,
   branch=branch_fact)` — "passing the switched branch as the branch
   fact" ✓ (the current call gains the kwarg).
6. **Output**: the unchanged single result line.

#### Checkpoint Summary

- "topic_switched fires on every completed switch" — the emission sits
  after `_apply_candidate` on every path — passed.
- Branch-only identity when the candidate hosts no topic — passed.
- Identity facts from the operation's own data (candidate's hosted slug,
  resolved year, branch name) — no git reads — passed.

### Trace: `ensure_topic` (changed)

#### Chain

1. **Input**: `ensure_topic(identifier, todo, year)` — unchanged
   signature (also the pipeline's entry:
   `commands/pipeline/pipeline.py:239`).
2. **Step 1–2** (terminal guard, candidate resolution): unchanged.
3. **Step 3 — the fast creation** (`_create_fresh_work`): slug guard and
   the occupancy oracles first (clean errors, nothing fires); then
   `identity = TopicIdentity(slug, resolved_year, identifier)` (the
   branch name as entered — the identifier becomes the branch) and
   `TopicHooks().amend_creation(identity, checked_out=True,
   published=False, commit_message=None, todo=None)` — the identity-only
   form, delivered immediately before `create_and_switch_branch` (the
   first mutation) ✓; the returned holder is deliberately not read —
   on this path the creation amendment observes only: an amended todo
   does not land here (the todo resolves later through the entry's own
   `amend_todo_entry`, which owns the written text), and
   `commit_message` is None because the path builds no commit (D8);
   `create_and_switch_branch(identifier)` →
   `ensure_topic_dir(identifier, year)` → with `todo`:
   `final_todo = _enter_topic_todo(identifier, year, branch=identifier)`
   (the private mirror, D6 — "passing the branch name as the branch
   fact"); after the creation completes →
   `emit_created(identity, checked_out=True, published=False,
   todo=final_todo, commit_message=None, commit_hash=None)` — "the final
   todo when the entry resolved one, and no commit facts" ✓.
4. **Step 4 — the switch path**: `switch_topic(identifier, todo=False,
   year)` — the switch notification fires inside it ✓; then with `todo`
   `_enter_switched_todo(candidates, year)` reworked: `current =
   resolve_current_branch_name()`; a hosted topic exists →
   `enter_topic_todo(topic, year, branch=current)`; a hosting branch
   without a topic → `ensure_topic_dir(current, year)` then
   `enter_topic_todo(current, year, branch=current)` (the derived
   identity — the topic input is the branch name, which normalizes to
   the slug) — "no creation checkpoint fires for the directory
   creation" ✓ (no `amend_creation`/`emit_created` on this branch).
5. **Output**: the unchanged single result line.

#### Checkpoint Summary

- "The fast creation delivers the creation amendment exactly once,
  immediately before its first mutation" — passed.
- "`ensure --todo` on a topic-less branch fires `amend_todo_entry` +
  `topic_todo_entered` with derived identity and no `topic_created`" —
  passed (the entry fires its own pair; the directory creation fires
  nothing).
- One registry across `ensure → switch → entry` (D1) — the enumeration
  runs once.

### Trace: `delete_topics` (changed)

#### Chain

1. **Input**: `delete_topics(targets, year)` — unchanged signature;
   targets resolved and confirmed by the caller.
2. **Steps 1–4** (per target: capture commit, delete local, delete
   origin twin with restore-on-failure, remove the directory):
   unchanged — a failure mid-target restores and raises before the
   emission → "a target whose removal fails midway fires nothing" ✓.
3. **Step 5** (new, inside the per-target loop after the directory
   removal): `directory_removed = remove_topic_dir(...) if target.has_dir
   else False` (the actual return — D-d7); `identity =
   TopicIdentity(slug=target.topic, year=resolved_year, branch=None)`;
   `TopicHooks().emit_deleted(identity, local_branch=target.branch,
   origin_twin=target.remote, directory_removed=directory_removed)` →
   checkpoint: fires after the target's **complete** removal ✓; targets
   fully removed before a later failure already fired theirs (the
   emission precedes the next target's processing) ✓; no commit hash
   carried (the captured rollback commit stays local) ✓.
4. **Output**: the unchanged single result line.

#### Checkpoint Summary

- Per-target timing — passed.
- The restore path (failure) emits nothing for the failing target —
  passed.

## Algorithm Design

### `goga/hooks/catalog/catalog.py` — `_DECLARED_ACTIONS` extension

**Responsibility**: the maintained data every address resolution reads.

**Algorithm:**
```
1. Append seven records to _DECLARED_ACTIONS (topics domain, soft class):
   amend_creation, amend_todo_entry, topic_created, topic_deleted,
   topic_published, topic_switched, topic_todo_entered
   → the list stays in (domain, name) sorted order; declared_actions()
     behavior is otherwise untouched
```

**Errors:** none (data).

**Edge Cases:** none — the routine's `sorted()` already fixes the output
order regardless of insertion order.

### `goga/topics/hooks/identity.py` — `TopicIdentity`

**Responsibility**: the identity vocabulary of every topics event.

**Algorithm:**
```
1. @dataclass(frozen=True, kw_only=True) with fields slug: str | None,
   year: str, branch: str | None
2. home_path property:
   IF slug is None -> None
   ELSE -> resolve_topic_dir(slug, year).as_posix()
```

**Errors:** none — the empty-slug `ValueError` of `resolve_topic_dir`
is unreachable (`slug` non-None on the composing branch, and
re-normalization of a normalized slug is the identity).

**Edge Cases:**
- Branch-only form (`slug=None`) → `home_path` None.
- Deletion form (`branch=None`) → the removal composition carries the
  branch names instead.

### `goga/topics/hooks/contexts.py` — the five contexts

**Responsibility**: read-only facts of one completed operation each.

**Algorithm:**
```
1. Five @dataclass(frozen=True, kw_only=True) classes, fields exactly
   as the signatures declare:
   TopicCreated(identity, checked_out, published, todo, commit_message, commit_hash)
   TopicPublished(identity, commit_message, commit_hash, todo)
   TopicSwitched(identity, outcome)
   TopicTodoEntered(identity, text)
   TopicDeleted(identity, local_branch, origin_twin, directory_removed)
2. Plain data fields (attribute reads suffice; no computed members)
```

**Errors:** none.

**Edge Cases:** `TopicSwitched.outcome` is one of the three fixed
kinds by construction of the emitting routine.

### `goga/topics/hooks/amendments.py` — holders and views

**Responsibility**: the shared draft holders and the per-hook views.

**Algorithm:**
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
```

**Errors:** none — buffering never raises.

**Edge Cases:**
- A hook calling `amend` twice → the last buffer wins.
- `amend(None, None)` → a lawful whole replacement to the identity-only
  form (commits; the path guards decide the consequences — D5).

### `goga/topics/hooks/events.py` — `TopicHooks` and the run registry

**Responsibility**: the checkpoint surface over the platform facade.

**Algorithm:**
```
_RUN_REGISTRY: HookRegistry | None = None   # module state, one per run

_run_registry():
1. IF _RUN_REGISTRY is None: create HookRegistry(), build_once(),
   store it
2. return _RUN_REGISTRY
   → one enumeration per process run; every TopicHooks instance and
     every checkpoint shares it (D1)

TopicHooks():
1. No state — cheap construction; no enumeration, no imports at init

amend_creation(identity, checked_out, published, commit_message, todo):
1. registry = _run_registry()
2. record = resolve ("topics", "amend_creation") against declared_actions()
   -> None is a clean ValueError of the emitting side
3. holder = CreationDraft(commit_message=commit_message, todo=todo)
4. FOR subscription IN registry.subscriptions_for("topics", "amend_creation"):
     view = CreationAmendment(identity=..., checked_out=..., published=...,
                              _draft=holder)         # outside the intercept
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
   → the same instance per tool; the platform owns resolution, delivery,
     and the soft warning
```

**Errors:**
- `ValueError` (unknown address) → the emitting side's bug; never a hook
  outcome.
- `ValueError` (hard-class raised hook) → dead branch today; identical
  shape to `emit_hook_event`.
- `ImportError` from `build_once` (a broken tool package import) → the
  single fatal case, surfacing from the platform unchanged.

**Edge Cases:**
- An address without subscriptions → the walk returns the original
  draft; the emission delivers nothing.
- Two hooks of one tool → independent views, buffers, and failures.

### `goga/topics/hooks/__init__.py` — the facade

**Algorithm:**
```
1. Re-export the eleven types from their modules (relative imports):
   TopicIdentity, TopicCreated, TopicPublished, TopicSwitched,
   TopicTodoEntered, TopicDeleted, CreationDraft, TodoEntryDraft,
   CreationAmendment, TodoEntryAmendment, TopicHooks
2. __all__ carries exactly the eleven names, alphabetically
3. Package docstring: the hooks-zone owner description (the CODEMANIFEST
   Description voice); importing the package imports no tool package
   and enumerates nothing
```

### `goga/topics/creation.py` — `enter_topic_todo`, `create_topic`

**Algorithm** — per the Code Stack Trace sections above; the concrete
wiring:

```
enter_topic_todo(topic, year=None, branch=None):
1-3. unchanged (path resolve, prefill read, editor session);
     cancelled -> False (nothing delivered or emitted)
4. identity = TopicIdentity(slug=normalize_topic_slug(topic),
                            year=resolved_year, branch=branch)
5. draft = TopicHooks().amend_todo_entry(identity, saved)
6. _write_todo(topic, resolved_year, draft.text) -> the final text
7. TopicHooks().emit_todo_entered(identity, draft.text); return True

_create_topic — insert between the ask and the path branches:
  publishing = _publication_asked(publish, resolved_todo)
  identity = TopicIdentity(slug, resolved_year, branch_name)
  draft = TopicHooks().amend_creation(identity,
           checked_out=switch and not publishing,
           published=publishing,
           commit_message=<applied message of the path, None on switch>,
           todo=resolved_todo)
  # the applied message uses the `or` predicate: an empty template
  # normalizes to the built-in default before the delegation
  final_todo = draft.todo; final_message = draft.commit_message
no-switch branch:
  IF final_todo is None -> the "needs a todo" clean error (D5)
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

**Errors:** the existing `click.ClickException` boundary is unchanged;
the checkpoint code adds no I/O. A hook failure is a log warning inside
the walk, never an exception to the flow.

**Edge Cases:** see D3/D4/D5 above; a failed preflight/ask fires
nothing.

### `goga/topics/publishing.py` — `publish_topic`

**Algorithm:**
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
```

**Errors:** unchanged; the rollback path fires nothing.

**Edge Cases:** a direct CLI call publishes without `amend_creation`
(the creation amendment belongs to the creating orchestration).

### `goga/topics/switching.py` — `switch_topic`

**Algorithm:**
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
```

**Errors:** unchanged.

**Edge Cases:** the idempotent already-on-branch outcome still emits;
the `todo` no-topic guard fires before any mutation and emits nothing.

### `goga/topics/ensuring.py` — `ensure_topic`

**Algorithm:**
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
```

**Errors:** unchanged; note the OSError boundary comment covers only
the directory creation and the write — the checkpoints add no I/O.

**Edge Cases:** the directory creation of a topic-less branch fires no
creation checkpoint; the todo entry alone fires its two.

### `goga/topics/deletion.py` — `delete_topics`

**Algorithm:**
```
_delete_topics — inside the per-target loop, after the directory removal:
  directory_removed = (remove_topic_dir(target.topic, resolved_year)
                       if target.has_dir else False)
  identity = TopicIdentity(slug=target.topic, year=resolved_year, branch=None)
  TopicHooks().emit_deleted(identity, local_branch=target.branch,
                            origin_twin=target.remote,
                            directory_removed=directory_removed)
```

**Errors:** unchanged; the restore-on-failure path raises before the
emission.

**Edge Cases:** a remote-only target (`branch=None`) still fires with
its twin name; a directory-less target reports
`directory_removed=False`.

## Cross-cutting Concerns

- **Error handling**: two layers, strictly separated. (1) The domain
  flows keep their `click.ClickException` clean-error boundary — every
  preflight conflict, failed publication, and failed remote deletion is
  one clean error, and a flow that errors before its moment fires
  nothing. (2) The hook layer never breaks an operation: the seven
  topics actions are soft — a raised hook discards its buffer, an
  empty/whitespace buffer is rejected whole, both are warnings, and the
  walk/delivery continues in enumeration order. The single fatal case is
  a broken tool package import surfacing from `build_once` (platform
  behavior, unchanged).
- **Logging**: `logging` per the conventions; one module logger in
  `events.py`. Warnings use the platform's exact shape —
  `hook <name> of tool <tool> failed on topics.<action>: <reason>` —
  naming the hook, the tool, the action, and the reason (the rejection
  reason string: `the buffered amendment is empty or whitespace-only`).
  No INFO/DEBUG additions in the zone (the platform's emit path already
  owns the diagnostics surface).
- **Validation**: the catalog is the single address source — the walk
  and `emit_hook_event` both resolve against `declared_actions()`; an
  unknown address is the emitting side's `ValueError`. Buffer
  validation at commit time only (empty/whitespace structural fields
  reject the whole buffer); no validation of hook-authored content
  beyond that (a tool may lawfully transform any field, including
  nulling it — the path guards own the consequences).
- **Caching**: exactly one `HookRegistry` per process run (D1) — the
  module-level lazily-built `_RUN_REGISTRY` in `events.py`, shared by
  every checkpoint and every `TopicHooks` instance; `build_once` on the
  same object is idempotent, so nested public calls
  (`ensure → switch → entry`, `create → publish`) never multiply the
  package enumeration. Nothing else is cached; no state survives a
  process exit. Tests reset the registry through a fixture (see Test
  Stack Trace).
- **Concurrency**: none introduced — the flows are single-threaded CLI
  paths; the registry and contexts follow the platform's existing
  (non-thread-safe, run-scoped) model.

## Usages Analysis

### `convention` (both changed cells)
- **What it provides**: the project's mandatory Python rules — relative
  imports, kw-only dataclasses, logging, docstring style, test
  structure, mock boundaries, validation commands.
- **Where used**: every module of the zone and every touched domain
  module (global annotations + type annotations).
- **Why chosen**: the project-wide baseline.
- **How exactly**: relative intra-package imports (`from ...hooks
  import ...` inside the zone, `from .hooks import ...` in the domain
  modules); `@dataclass(kw_only=True)` for all eleven types; Google
  docstrings mirroring the manifest annotations; tests under
  `tests/topics/hooks/` with `__init__.py` and a local `conftest.py`.

### `declaring-actions` (imported from `goga/hooks`)
- **What it provides**: the domain-maintainer side of opening an action:
  catalog record, context contract, emission at the checkpoint.
- **Where used**: `TopicHooks` type annotation and the five `emit_*`
  methods.
- **Why chosen**: the five notifications are plain emissions.
- **How exactly**: `emit_hook_event(registry, "topics", "<action>",
  context_for=lambda _tool: context)` — the same instance shared per
  tool; the emission assembles the registry on first use.

### `per-tool-delivery` (imported from `goga/hooks`)
- **What it provides**: the staged per-tool delivery loop skeleton over
  the public primitives — registry build once, subscriptions in
  enumeration order, wrap/project/call, commit only after success.
- **Where used**: `TopicHooks` type annotation; `amend_creation`;
  `amend_todo_entry`.
- **Why chosen**: the amendments need per-hook outcomes (the buffer
  commit), which the plain emission cannot collect.
- **How exactly**: with the declared refinement — the commit granularity
  is the **single hook**, not the tool: a fresh view per subscription,
  the commit decided per subscription, so two hooks of one tool never
  share a buffer or a failure. The practice's tool-grouped loop is
  otherwise followed (build once, warn naming tool/action/reason,
  never filter delivery, `build_hook_arguments` as the single
  projection).

### `registering-hooks` (imported from `goga/hooks`)
- **What it provides**: the tool-author registration contract — the
  hook signature (`context`/`self` offered names) and the failure
  behavior behind every checkpoint.
- **Where used**: `TopicHooks` type annotation; `CreationAmendment`;
  `TodoEntryAmendment`.
- **Why chosen**: the views are the delivered objects hooks receive;
  their read/`amend` surface must match the delivered-context rules
  (reads pass through the proxy, assignment blocked, `amend` is a plain
  method call).

### `topic-paths` (imported from `goga/history`)
- **What it provides**: the topic directory composition contract of
  `resolve_topic_dir`.
- **Where used**: `TopicIdentity` (the `home_path` composition).
- **Why chosen**: the home path must be the canonical
  `.goga/history/<year>/<slug>` posix form the history facade owns.
- **How exactly**: `resolve_topic_dir(slug, year).as_posix()` — pure,
  nothing created.

### `checkpoints` (imported from `goga/topics/hooks` into `goga/topics`)
- **What it provides**: the consumer practice of the zone — one
  `TopicHooks` object per command, amend before fixation, emit after
  the moment, facts from the operation's own data.
- **Where used**: the global annotations and the six reworked routines
  of `goga/topics`.
- **Why chosen**: the binding practice for every checkpoint call site.
- **How exactly**: as the Code Stack Traces specify — identity
  construction from operation data, amendment immediately before the
  first mutation of the path, emission after the moment fully succeeds.

### Imported usages — traceable dependency summary

- `declaring-actions`, `per-tool-delivery`, `registering-hooks` from
  `goga/hooks` — paths `goga/hooks/.usages/*.md` — the emission and
  delivery contracts the zone composes (read and applied above).
- `topic-paths` from `goga/history` — path
  `goga/history/.usages/topic-paths.md` — the path-composition contract
  behind `home_path`.
- `checkpoints` from `goga/topics/hooks` — path
  `goga/topics/hooks/.usages/checkpoints.md` — the consumer practice
  for the domain flows (this cell's own `.usages/`, consumed by
  `goga/topics`).

## `.usages/` Update

### Cell: `goga/topics/hooks`

#### Existing Files — Consistency
- **`checkpoints`** → `goga/topics/hooks/.usages/checkpoints.md`
  - Status: current — created with the manifest; every referenced name
    (`TopicHooks`, `TopicIdentity`, `amend_creation`, `amend_todo_entry`,
    `emit_*`, `CreationDraft` accessors) matches the CODEMANIFEST
    signatures; the examples compile against the designed API (kw-only
    constructor arguments as shown).
  - Additions needed: none.
  - Updates needed: none — one clarification may accompany the
    implementation if desired: the run registry is shared per process
    run (D1), which the file already states as "one registry per run".

#### New Files
- None — the zone is one functional domain (the checkpoint surface);
  a single practice file covers it.

### Cell: `goga/topics`

#### Existing Files — Consistency
- **`todo-entry`** → `goga/topics/.usages/todo-entry.md`
  - Status: current — the added clause (the written content is the
    final amended text) matches the designed `enter_topic_todo`.
  - Additions needed: none.
  - Updates needed: none.
- **`creating`** → `goga/topics/.usages/creating.md`
  - Status: current — the added clause (todo.md content and commit
    message are the final amended values) matches the designed
    `create_topic`/`publish_topic`.
  - Additions needed: none.
  - Updates needed: none.
- Remaining files (`deleting`, `switching`, `ensuring`, `board` if
  present): no content changes required — the hooks are log-level
  facts, not consumer-visible behavior of those flows. Optional
  one-line clauses mirroring the two above may be added at
  implementation time for `switching`/`deleting`/`ensuring` if the
  documentation stage judges them useful; not required by the contract.

#### New Files
- None — no new functional domain of the consumer surface opens (the
  hooks zone documents itself in its own cell).

## Test Stack Trace

### General Setup

Two fixture families, following the established boundaries:

1. **The platform environment** (the `tests/hooks/conftest.py` shape,
   re-declared locally in `tests/topics/hooks/conftest.py` and
   `tests/topics/conftest.py`):
   - `pin_package_environment` — pins
     `goga.hooks.tools.packages.packages_distributions` to a fixed
     mapping (`{"goga_tool_one": ["pkg-one"], "goga_tool_two": ["pkg-two"]}`);
   - `install_tool_package(module_name, register_hooks)` — mounts fake
     `goga_tool_*` modules in `sys.modules` (monkeypatch-undone);
   - `recording_hooks` — subscribes recording hooks (appending
     `(tool, hook_name, context)` and captured facts to lists the test
     asserts).
2. **The run-registry reset** (autouse in both conftest files):
   `monkeypatch.setattr("goga.topics.hooks.events._RUN_REGISTRY", None)`
   — every test starts with an unbuilt registry, so no subscription
   leaks across tests and enumeration counts are per-test.
3. **The git/editor boundaries** (existing `tests/topics` fixtures):
   mocked at the import point per module (`monkeypatch.setattr(creation,
   "list_branch_refs", ...)`, the recording parent mock for the git
   mutations, `edit_text` stubbed on the creation module).

Mock policy: the platform (registry, dispatch, wrap, projection) and
the whole hooks zone run **for real**; only the package environment,
the git/editor boundaries, and the run-registry reset are pinned — the
`convention` and `statuses` precedents combined.

### Source File Registry

- `goga/hooks/catalog/catalog.py` — the seven records
- `goga/topics/hooks/__init__.py` — the facade (11 re-exports)
- `goga/topics/hooks/identity.py` — `TopicIdentity`
- `goga/topics/hooks/contexts.py` — the five contexts
- `goga/topics/hooks/amendments.py` — holders and views
- `goga/topics/hooks/events.py` — `TopicHooks`, `_run_registry`
- `goga/topics/creation.py`, `publishing.py`, `switching.py`,
  `ensuring.py`, `deletion.py` — the checkpoint wiring
- Tests: `tests/hooks/catalog/test_catalog.py` (extended);
  `tests/topics/hooks/{__init__,conftest,test_identity,test_contexts,
  test_amendments,test_events}.py` (new); `tests/topics/test_{creation,
  publishing,switching,ensuring,deletion}.py` (extended).

---

### Positive Tests

#### `test_declared_actions_carries_the_seven_topics_records`

**Setup**: none (pure data).

**Input**: `declared_actions()`.

**Trace**:
```
declared_actions()
  -> sorted(_DECLARED_ACTIONS, key=(domain, name))
     returns: 10 records
```

**Assertions**:
```
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
```

**Sufficiency**: the addresses must exist before any checkpoint fires;
an address the zone emits but the catalog misses is a runtime
`ValueError` in every flow — this pins the catalog against drift.

---

#### `test_topic_identity_home_path_composes_purely`

**Setup**: none (pure composition; no filesystem).

**Input**: `TopicIdentity(slug="add-topics-hooks", year="2026",
branch="add-topics-hooks")`.

**Trace**:
```
TopicIdentity(slug=..., year=..., branch=...)
  -> identity.home_path
     -> resolve_topic_dir("add-topics-hooks", "2026")
        -> normalize (idempotent) -> .goga/history/2026/add-topics-hooks
     -> .as_posix()
     returns: ".goga/history/2026/add-topics-hooks"
```

**Assertions**:
```
identity.home_path == ".goga/history/2026/add-topics-hooks"
identity.slug == "add-topics-hooks"; identity.branch == "add-topics-hooks"
```

**Sufficiency**: the home path is the canonical addressing fact every
notification carries; a regression here corrupts every tool's view of
the topic location.

---

#### `test_amend_creation_walks_per_hook_and_commits_in_order`

**Setup**: enumeration pinned to two tools; two packages installed —
`goga_tool_one` subscribing `first` and `second` to
`topics.amend_creation`, `goga_tool_two` subscribing `tail`;
run-registry reset applied.

**Input**:
```
hooks = TopicHooks()
draft = hooks.amend_creation(
    identity, checked_out=False, published=False,
    commit_message="goga: create topic add-topics-hooks", todo="first todo")
```
Hooks: `first` calls `context.amend("m1", "t1")`; `second` records
`context.todo` (live read) and calls `context.amend("m2", "t2")`; `tail`
records `context.todo`.

**Trace**:
```
amend_creation(...)
  -> _run_registry(): build_once() enumerates both packages once
  -> holder = CreationDraft("goga: create topic add-topics-hooks", "first todo")
  -> sub one/first: view over holder; hook buffers ("m1", "t1")
     returns -> holder._commit(("m1","t1"))  [non-empty]
  -> sub one/second: view reads context.todo == "t1" (committed amendment of the earlier hook)
     hook buffers ("m2","t2") -> holder._commit(("m2","t2"))
  -> sub two/tail: view reads context.todo == "t2"
  returns holder
```

**Assertions**:
```
draft.commit_message == "m2"; draft.todo == "t2"          # last committed buffer
second saw context.todo == "t1"; tail saw context.todo == "t2"
enumeration boundary called exactly once
```

**Sufficiency**: pins the per-hook commit granularity (two hooks of one
tool, independent buffers, ordered visibility) — the core refinement
the zone adds over the tool-grouped practice.

---

#### `test_emit_created_shares_one_instance_and_returns_none`

**Setup**: enumeration pinned; two packages each subscribing one hook
to `topics.topic_created`.

**Input**: `result = TopicHooks().emit_created(identity, checked_out=False,
published=False, todo="t", commit_message="m", commit_hash="abc123")`.

**Trace**:
```
emit_created(...)
  -> TopicCreated(...) built once
  -> emit_hook_event(_run_registry(), "topics", "topic_created",
                     context_for=lambda _tool: context)
     -> both hooks called with the delivered proxy
```

**Assertions**:
```
result is None
the two deliveries observe the identical underlying context —
  each through its own fresh proxy (type is not TopicCreated), the
  shared instance pinned one attribute deep:
  recorded[0].identity is recorded[1].identity
each hook read: checked_out False, published False, todo "t",
  commit_message "m", commit_hash "abc123", identity.home_path as composed
```

**Sufficiency**: the context-instance sharing and the fire-and-forget
contract of every notification — prevents per-tool copies (stale facts)
and accidental return-channel collection.

---

#### `test_enter_topic_todo_writes_amended_text_and_emits_final`

**Setup**: `tmp_path` as cwd; topic directory
`.goga/history/2026/feature-foo/` created; `edit_text` stubbed to return
`"saved text"`; enumeration pinned; one package subscribing an
`amend_todo_entry` hook (`context.amend("amended text")`) and a
`topic_todo_entered` recorder; registry reset.

**Input**: `enter_topic_todo("feature-foo", year="2026",
branch="feature-foo")`.

**Trace**:
```
enter_topic_todo(...)
  -> resolve_topic_file -> path (file absent -> initial None)
  -> edit_text(None) -> "saved text"
  -> identity = TopicIdentity("feature-foo", "2026", "feature-foo")
  -> amend_todo_entry(identity, "saved text") -> holder.text "amended text"
  -> _write_todo: todo.md == "amended text\n" (UTF-8, single newline)
  -> emit_todo_entered(identity, "amended text")
  returns True
```

**Assertions**:
```
result is True
(todo.md).read_text() == "amended text\n"
recorded topic_todo_entered context.text == "amended text"
recorded context.identity.branch == "feature-foo"
```

**Sufficiency**: the pre-fixation/post-moment pair of the entry — the
file carries the amended text and the notification reports the same
final value (the `.usages/todo-entry.md` clause made executable).

---

#### `test_create_topic_no_switch_emits_created_with_commit_hash`

**Setup**: git boundary mocked at the import point (empty inventory,
current branch `main`, occupancy free, base resolved, plant wired to a
recording mock returning `"deadbeef"`); `sys.stdin` pinned to an
interactive terminal (`isatty` → True, the tests/topics precedent) so
the editor-todo resolution runs; `edit_text` → `"the todo"`;
enumeration pinned with a `topic_created` recorder; registry reset.

**Input**: `create_topic("Feature/Foo_Bar", "HEAD", todo=None, year="2026")`
(interactive terminal pinned; the editor stubbed).

**Trace**:
```
_create_topic -> preflight free; resolved_todo "the todo"; ask False (publish False)
-> amend_creation(identity(slug "feature-foo-bar", 2026, "Feature/Foo_Bar"),
   checked_out False, published False, commit_message "goga: create topic feature-foo-bar",
   todo "the todo") -> unamended (no subscriber)
-> _plant_topic_branch(... final values ...) returns "deadbeef"
-> emit_created(identity, False, False, "the todo", <applied default>, "deadbeef")
returns "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
```

**Assertions**:
```
result line unchanged
recorded context.commit_hash == "deadbeef"
recorded context.commit_message == "goga: create topic feature-foo-bar"
recorded context.todo == "the todo"; checked_out False; published False
plant mock called once (mutation order unchanged)
```

**Sufficiency**: the no-switch path's checkpoint wiring — the hash comes
from the existing plant return (no new git read) and the identity facts
come from the operation's own data.

---

#### `test_publish_topic_emits_created_then_published_after_push`

**Setup**: git boundary mocked (occupancy free, origin configured, base
resolved, plant → `"cafe123"`, push succeeding); enumeration pinned with
recorders for both actions; registry reset.

**Input**: `publish_topic("Feature/Foo_Bar", "the todo", "HEAD",
year="2026")`.

**Trace**:
```
_publish_topic -> guards pass
-> applied = "goga: create topic feature-foo-bar"
-> commit = _plant_topic_branch(..., applied) -> "cafe123"
-> push_branch OK
-> emit_created(identity, False, True, "the todo", applied, "cafe123")
-> emit_published(identity, applied, "cafe123", "the todo")
returns the unchanged line
```

**Assertions**:
```
emission order == ["topic_created", "topic_published"]
both contexts carry commit_hash "cafe123", commit_message applied, todo "the todo"
created.checked_out False; created.published True
```

**Sufficiency**: the publication pair fires only after the push, in the
fixed order, with the identical final facts — the contract's central
ordering guarantee.

---

#### `test_switch_topic_emits_switched_for_every_outcome` (parametrized)

**Setup**: three inventory scenarios — (a) already on `feature-foo`;
(b) local branch `feature-foo` not current; (c) remote-tracking
`origin/feature-foo` only; tree-clean probe True; a `topic_switched`
recorder; registry reset.

**Input**: `switch_topic("feature-foo", year="2026")` per scenario
(candidate hosts topic `feature-foo` in (a)/(b); a fourth parametrization
uses a topic-less branch).

**Trace** (scenario c):
```
_switch_topic -> chosen = origin/feature-foo (remote, topic feature-foo)
-> create_branch_from_remote_tracking(...)   # line unchanged
-> branch_fact = "feature-foo" (short name)
-> emit_switched(TopicIdentity("feature-foo", "2026", "feature-foo"),
                 "created-from-remote")
returns "Created branch feature-foo from origin/feature-foo"
```

**Assertions**:
```
(a) outcome "already-on-branch"; (b) "local-checkout"; (c) "created-from-remote"
topic-less branch: identity.slug is None; identity.home_path is None;
  identity.branch == the branch name
all lines unchanged
```

**Sufficiency**: every completed switch fires exactly once, the
idempotent outcome included, and the branch-only degradation works —
the marginal corner of the switch contract.

---

#### `test_ensure_fast_creation_amends_identity_only_and_emits_after_entry`

**Setup**: empty inventory (zero candidates), tree-clean True;
`create_and_switch_branch` recorded; `sys.stdin` pinned to an
interactive terminal (`isatty` → True, the tests/topics precedent);
`edit_text` → `"fresh todo"`;
enumeration pinned with `amend_creation`/`topic_created`/
`amend_todo_entry`/`topic_todo_entered` recorders; registry reset.

**Input**: `ensure_topic("New_Work", todo=True, year="2026")`.

**Trace**:
```
_ensure_topic -> zero candidates -> _create_fresh_work
-> slug "new-work", oracles free
-> amend_creation(TopicIdentity("new-work","2026","New_Work"),
   checked_out True, published False, commit_message None, todo None)
-> create_and_switch_branch("New_Work"); ensure_topic_dir
-> _enter_topic_todo("New_Work", "2026", branch="New_Work") -> "fresh todo"
-> emit_created(identity, True, False, "fresh todo", None, None)
```

**Assertions**:
```
amend_creation recorded once, before create_and_switch_branch (call order)
its context.commit_message is None and context.todo is None (identity-only)
topic_created context.todo == "fresh todo"; commit_hash None; checked_out True
topic_todo_entered fired with identity.branch "New_Work"
result line unchanged
```

**Sufficiency**: the fast-creation corner — identity-only amendment
before the first mutation, notification after the entry with the final
todo, all from one registry build.

---

#### `test_delete_topics_emits_per_target_after_full_removal`

**Setup**: two targets
(`DeleteTarget("one", branch="one", remote="one", has_dir=True)`,
`DeleteTarget("two", branch=None, remote=None, has_dir=False)`); git
boundary recorded (`resolve_ref_commit` → hash, deletions succeeding,
`remove_topic_dir` real over `tmp_path` with `.goga/history/2026/one/`
created); a `topic_deleted` recorder; registry reset.

**Input**: `delete_topics(targets, year="2026")`.

**Trace**:
```
_delete_topics
-> target one: capture commit, delete local, delete remote, remove dir -> True
   -> emit_deleted(identity(slug "one", 2026, branch None),
                   local_branch "one", origin_twin "one", directory_removed True)
-> target two: no branch, no twin, no dir -> emit_deleted(identity,
   local_branch None, origin_twin None, directory_removed False)
returns the unchanged line
```

**Assertions**:
```
two emissions, in target order
first: local_branch "one", origin_twin "one", directory_removed True
second: all-absent composition, directory_removed False
both identities: branch is None; home_path ".goga/history/2026/<slug>"
```

**Sufficiency**: the per-target timing and the removal-composition
mapping — including the directory-less and remote-only target shapes.

---

### Negative Tests

#### `test_amend_creation_discards_buffer_of_raising_hook`

**Setup**: enumeration pinned; `goga_tool_one` subscribes `boom`
(calls `context.amend("m", "t")` then `raise RuntimeError("kaputt")`);
`goga_tool_two` subscribes `tail` (`context.amend("late", "late-t")`);
registry reset; `caplog` at WARNING.

**Input**: `TopicHooks().amend_creation(identity, False, False, "orig",
"orig todo")`.

**Trace**:
```
walk: boom raises after buffering -> buffer discarded, warning emitted
walk: tail returns -> buffer committed
returns holder
```

**Assertions**:
```
draft.commit_message == "late"; draft.todo == "late-t"   # boom's buffer gone
any("hook boom of tool one failed on topics.amend_creation: kaputt"
    in r.message for r in caplog.records)
the walk reached tail (its buffer landed)
```

**Sufficiency**: a failing hook never breaks the operation and never
leaks its buffer — the soft-action core guarantee.

---

#### `test_amend_creation_rejects_empty_amendment_whole`

**Setup**: one tool subscribing `blank` →
`context.amend("   ", "fine text")`; registry reset; `caplog`.

**Input**: `TopicHooks().amend_creation(identity, False, False, "orig",
"orig todo")`.

**Trace**:
```
walk: blank returns; buffer ("   ", "fine text")
-> commit_message structurally present and whitespace-only
-> whole buffer rejected with the empty-amendment warning
returns holder with the original values
```

**Assertions**:
```
draft.commit_message == "orig"; draft.todo == "orig todo"
"failed on topics.amend_creation: the buffered amendment is empty or whitespace-only"
  in caplog.text
```

**Sufficiency**: the whole-replacement rejection — a whitespace field
must not partially land (the message survives while the todo changes).

---

#### `test_amend_todo_entry_rejects_blank_text_buffer`

**Setup**: enumeration pinned; one tool subscribing `blank` →
`context.amend("   ")` (whitespace buffer); registry reset; `caplog`
at WARNING.

**Input**: `TopicHooks().amend_todo_entry(identity, "saved text")`.

**Trace**:
```
walk: blank returns; buffer "   "
-> text buffer blank (whitespace-only)
-> whole buffer rejected with the empty-amendment warning
returns holder with the saved text
```

**Assertions**:
```
draft.text == "saved text"
"failed on topics.amend_todo_entry: the buffered amendment is empty or whitespace-only"
  in caplog.text
```

**Sufficiency**: pins the single predicate that distinguishes the
todo-entry walk from the creation walk (`text is None or
not text.strip()` — a None buffer is rejected here, lawful on the
creation side) — a regression that unifies the two walks without
changing the contract is caught, and the write path is guaranteed a
non-blank text by rejection rather than by luck.

---

#### `test_publish_topic_rollback_fires_nothing`

**Setup**: git boundary mocked with `push_branch` raising
`CalledProcessError` (rollback recorded); both action recorders
installed; registry reset.

**Input**: `publish_topic("Feature/Foo_Bar", "the todo", "HEAD",
year="2026")`.

**Trace**:
```
plant OK -> push raises -> delete_local_branch (rollback) -> ClickException
```

**Assertions**:
```
pytest.raises(click.ClickException)
recorded emissions == []          # nothing fired on the failure
delete_local_branch called once   # the rollback still runs
```

**Sufficiency**: a rolled-back publication must leave no event trail —
tools would otherwise record a publication that does not exist.

---

#### `test_create_topic_failed_preflight_fires_nothing`

**Setup**: occupancy conflict wired (`check_branch_occupancy` → a
reason); recorders for all seven actions; registry reset.

**Input**: `create_topic("Feature/Foo_Bar", "HEAD", todo="x",
year="2026")`.

**Trace**:
```
preflight conflict -> ClickException before any input-driven step
```

**Assertions**:
```
pytest.raises(click.ClickException)
recorded emissions and amendments == []
```

**Sufficiency**: "a failed creation fires nothing" — the amendment
delivers only immediately before the first mutation, never before the
decisions.

---

#### `test_enter_topic_todo_cancelled_entry_delivers_and_emits_nothing`

**Setup**: topic directory present; `edit_text` → `None` (cancelled);
recorders installed; registry reset.

**Input**: `enter_topic_todo("feature-foo", year="2026")`.

**Trace**:
```
edit_text -> None -> return False before any delivery
```

**Assertions**:
```
result is False
todo.md absent; recorded checkpoints == []
```

**Sufficiency**: a cancelled entry is a non-event — the amendment
moment never arrives.

---

#### `test_enter_topic_todo_failed_write_emits_nothing`

**Setup**: `tmp_path` as cwd; topic directory created; `edit_text`
stubbed to return `"saved"`; `_write_todo` on the creation module
monkeypatched to raise `OSError`; a `topic_todo_entered` recorder
installed; registry reset.

**Input**: `enter_topic_todo("feature-foo", year="2026")`.

**Trace**:
```
enter_topic_todo -> save "saved"
-> amend_todo_entry delivered (holder.text "saved" — no subscriber)
-> _write_todo raises OSError
-> the wrapper converts it to ClickException; emit_todo_entered
   is never reached
```

**Assertions**:
```
pytest.raises(click.ClickException)
recorded topic_todo_entered == []
```

**Sufficiency**: pins the write-then-emit order on the failure path —
the only point where the order guarantees the event carries a written
fact; catches an emit-before-write or emit-in-finally regression.

---

#### `test_switch_todo_onto_topicless_branch_fires_nothing`

**Setup**: one candidate `bare-branch` (topic None) with interactive
terminal; recorders installed; registry reset.

**Input**: `switch_topic("bare-branch", todo=True, year="2026")`.

**Trace**:
```
chosen.topic is None and todo -> clean error before any mutation
```

**Assertions**:
```
pytest.raises(click.ClickException, match="hosts no topic")
recorded checkpoints == []
```

**Sufficiency**: the pre-mutation guard must also suppress the switch
notification — the only switch path that fires nothing.

---

### Edge Case Tests

#### `test_run_registry_built_once_across_checkpoints`

**Setup**: enumeration boundary mock (call-counting); one tool
subscribing to `amend_creation`, `topic_created`, `topic_todo_entered`,
`amend_todo_entry`; registry reset.

**Input**:
```
hooks = TopicHooks()
hooks.amend_creation(identity, False, False, None, None)   # identity-only form
hooks.emit_created(identity, False, False, None, None, None)
hooks.amend_todo_entry(identity, "t")
hooks.emit_todo_entered(identity, "t")
TopicHooks().emit_switched(identity, "local-checkout")     # a second instance
```

**Trace**:
```
every checkpoint -> _run_registry() -> the single built object
```

**Assertions**:
```
boundary.call_count == 1
all checkpoints delivered to the subscriber
```

**Sufficiency**: D1 — "the checkpoints never multiply the package
enumeration", including across separate `TopicHooks` instances and
nested flows.

---

#### `test_topic_hooks_construction_enumerates_nothing`

**Setup**: enumeration boundary mock installed; registry reset.

**Input**: `TopicHooks()` (no checkpoint calls).

**Trace**:
```
__init__ stores nothing, touches nothing
```

**Assertions**:
```
boundary.call_count == 0; _RUN_REGISTRY stays None
```

**Sufficiency**: "cheap construction — no enumeration and no imports
happen at construction" — keeps import-time and construction-time
behavior identical for every consumer.

---

#### `test_amend_creation_without_subscriptions_returns_original_values`

**Setup**: enumeration pinned to a tool subscribing nothing; registry
reset.

**Input**: `amend_creation(identity, False, False, "m", None)`.

**Trace**:
```
walk over zero subscriptions -> holder untouched
```

**Assertions**:
```
draft.commit_message == "m"; draft.todo is None   # no error
```

**Sufficiency**: the no-subscriber case is the everyday case — the
amendment is a transparent no-op the flows can always call.

---

#### `test_amend_creation_identity_only_form_is_valid`

**Setup**: one tool subscribing a recorder (no amend call); registry
reset.

**Input**: `amend_creation(identity, True, False, None, None)`.

**Trace**:
```
holder created with (None, None); hook observes, buffers nothing
```

**Assertions**:
```
draft.commit_message is None; draft.todo is None
recorded view read: checked_out True, published False,
  commit_message None, todo None
```

**Sufficiency**: the identity-only form is the norm on the ensure fast
path — a hook must be able to observe it without acting.

---

#### `test_create_topic_switch_path_amended_null_todo_degrades_gracefully`

**Setup**: switch=True, todo resolved, inventory free; a tool whose
`amend_creation` hook calls `context.amend(None, None)` (nulls the
todo); recorders; registry reset.

**Input**: `create_topic("Feature/Foo_Bar", "HEAD", todo="the todo",
switch=True, year="2026")`.

**Trace**:
```
amendment commits (None, None) -> final_todo None
switch path: branch planted+checked out, dir ensured, no todo write
-> emit_created(identity, True, False, None, None, None)
```

**Assertions**:
```
topic_created fired once with todo None
todo.md absent (nothing written)
result line unchanged
```

**Sufficiency**: the switch path's todo is optional — a nulled amended
todo degrades gracefully and the notification reports the truth.

---

#### `test_ensure_todo_on_topicless_branch_fires_only_the_entry_pair`

**Setup**: one candidate `bare-branch` (topic None), tree-clean,
current branch becomes `bare-branch` after the switch; `edit_text` →
`"fresh"`; recorders for all seven actions; registry reset.

**Input**: `ensure_topic("bare-branch", todo=True, year="2026")`.

**Trace**:
```
switch_topic -> emit_switched(branch-only identity)      # the switch's own event
-> _enter_switched_todo: no hosted topic -> ensure_topic_dir(current)
-> _enter_topic_todo(current, year, branch=current)
   -> amend_todo_entry(derived identity) -> emit_todo_entered
no amend_creation / topic_created anywhere
```

**Assertions**:
```
fired actions == ["topic_switched", "topic_todo_entered"]
topic_todo_entered identity.slug == "bare-branch" (derived) and
  identity.branch == "bare-branch"
topic_created not recorded
```

**Sufficiency**: the marginal corner of the ensure contract — the
directory creation of a topic-less branch fires no creation
checkpoint; the entry alone fires its two.

---

#### `test_amend_views_block_no_write_path_to_the_holder`

**Setup**: a holder and a view constructed directly; no platform.

**Input**: `view.amend("m", "t")`; then read `holder.commit_message`.

**Trace**:
```
amend buffers on the view only; the holder fields stay at the draft values
```

**Assertions**:
```
holder.commit_message == <original>; holder.todo == <original>
view.commit_message reads the live holder (the draft values, not the buffer)
```

**Sufficiency**: "the content changes only through the delivery commit —
never through a delivered view" — the buffering isolation that makes
the discard-on-failure semantics possible.

---

#### `test_amend_called_twice_last_buffer_wins`

**Setup**: enumeration pinned; one tool subscribing `fickle` whose hook
calls `context.amend("first", "t-first")` then
`context.amend("second", "t-second")`; registry reset.

**Input**: `TopicHooks().amend_creation(identity, False, False, "orig",
"orig todo")`.

**Trace**:
```
walk: fickle buffers ("first", "t-first") then overwrites its buffer
     with ("second", "t-second"); the holder stays untouched during
     both calls
returns -> view._buffered == ("second", "t-second") -> committed whole
```

**Assertions**:
```
draft.commit_message == "second"; draft.todo == "t-second"
```

**Sufficiency**: pins the whole-replacement last-wins semantics of the
buffer — the sole guarantee that `amend` means "replace entirely", not
"extend"; prevents a drift to an accumulative or first-wins semantics
no other scenario distinguishes.

---

## Additional Instructions for the Implementation Agent

- Implement in the order: `catalog.py` records → `goga/topics/hooks`
  (`identity.py` → `contexts.py` → `amendments.py` → `events.py` →
  `__init__.py`) → domain wiring (`creation.py`, `publishing.py`,
  `switching.py`, `ensuring.py`, `deletion.py`) → tests → docs. The
  catalog records must exist before any checkpoint runs.
- All eleven zone types are `@dataclass(kw_only=True)`; the identity and
  the five contexts are additionally `frozen=True`; the two holders and
  the two views are mutable (`StatusRegistry` precedent; the views store
  the holder under the private field `_draft` and carry the private
  `_buffered` field with `init=False, repr=False` — the holder is never
  a public attribute of a delivered view).
- Use relative imports everywhere intra-package: `from ...hooks
  import ...` inside the zone; `from .hooks import TopicHooks,
  TopicIdentity` in the domain modules. No new module-level import
  cycles are created (the zone imports neither the parent domain nor
  any domain module).
- The run registry is the module-level `_RUN_REGISTRY` of `events.py`
  with the lazy `_run_registry()` builder (D1). Never hold a registry on
  a `TopicHooks` instance and never call `HookRegistry()` inside a
  domain routine — the checkpoints own the sharing.
- The warning text is fixed: `hook <name> of tool <tool> failed on
  topics.<action>: <reason>` with the rejection reason
  `the buffered amendment is empty or whitespace-only`. Use
  `logger.warning` with `%s` placeholders (the `emit.py` style), one
  module logger in `events.py`.
- Do not change: any public signature, any result line, any error
  message, the mutation order of any flow, the `goga/commands/**` code,
  the platform cells (`goga/hooks/{dispatch,registry,tools}`). The
  emissions are additive wiring inside the six routines. One documented
  exception: an empty commit-message template on the delegated
  publication path normalizes to the built-in default at the amendment
  draft (the `or` predicate); a direct `publish_topic` call keeps its
  `is not None` predicate unchanged.
- The existing mocks of `enter_topic_todo` in `tests/topics/test_switching.py`
  and `test_ensuring.py` record calls — extend their assertions for the
  new `branch=` keyword (and update the signature-contract test in
  `test_creation.py` for the `branch` parameter).
- Docs synchronization (per the plan's checklist): replace the stub
  `docs/features/topics/hooks.md` with the seven-action reference (the
  checkpoint moments, the context surfaces, the amendment contract);
  add the topics domain to the declared-actions lists in
  `docs/features/hooks/index.md`, `docs/features/hooks/hooks.md`, and
  `docs/features/tools/hooks.md`. No `mkdocs.yml` nav change (the page
  exists).
- Validation: `pytest tests/ -x` green; `ruff check` over the touched
  sources green; `goga lint` stays at 0 errors; the facade check
  `python -c "from goga.topics.hooks import TopicHooks, TopicIdentity,
  CreationDraft, TodoEntryDraft, TopicCreated, TopicPublished,
  TopicSwitched, TopicTodoEntered, TopicDeleted, CreationAmendment,
  TodoEntryAmendment"` passes; `goga hooks` lists the seven topics
  actions with no command change; `goga schema goga/topics` shows the
  new subcell (already materialized).
