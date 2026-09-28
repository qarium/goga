# Design Document: `topic-update-and-propagate`

The architectural specification for implementing `goga topics update` and
`goga topics propagate` — the topic↔base exchange — against the materialized
CODEMANIFEST contracts. Every detail below is elaborated for implementation;
the implementation order belongs to the planning stage.

Language: Python (`goga config language` → python). All git access flows
through the `goga/topics/git` cell; every decision belongs to the domain
layers above it.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST` — two new Requirements bullets of
  `declared_actions`: the soft actions `topics/topic_updated` and
  `topics/topic_propagated`.
- `goga/config/project/CODEMANIFEST` — `TopicsConfig` rebuilt into the
  nested form (`base_ref` + `create`/`update`/`propagate` sections); three
  new models (`TopicsCreateConfig`, `TopicsUpdateConfig`,
  `TopicsPropagateConfig`); `load_project_config` — topics extraction moved
  to a dedicated nested step 9; Requirements/Constraints rewritten for the
  nested structural validation and the silently-retired `publish_commit`.
- `goga/config/CODEMANIFEST` — facade: +3 imported types, +3 embedding
  re-exports, the re-export phrase updated.
- `goga/config/hooks/CODEMANIFEST` — the configuration type-tree
  enumeration of `merge_config_amendments` extended with the three nested
  topics models; +3 imported types.
- `goga/topics/git/CODEMANIFEST` — the `git` practice text and the global
  annotations grow the checkout-free exchange zone; +13 routines
  (`exchange.py` ×7, `switch.py` ×3, `publish.py` ×3).
- `goga/topics/hooks/CODEMANIFEST` — counters five→seven moments,
  seven→nine actions; +2 contexts (`TopicUpdated`, `TopicPropagated`),
  +2 `TopicHooks` methods (`emit_updated`, `emit_propagated`); a
  notification-only paragraph.
- `goga/topics/CODEMANIFEST` — Imports +13 git types + the `exchanging`
  practice; the sanctioned network set rewritten; +10 types
  (`ExchangeBase`, `resolve_exchange_base`, `ExchangeTarget`,
  `resolve_exchange_target`, `render_commit_template`, `update_topic`,
  `PropagationPlan`, `resolve_propagation`, `execute_propagation`,
  `resolve_divergence`); 6 types modified (`BoardRecord`, `BoardEntry`,
  `collect_topic_board`, `aggregate_topic_board`, `create_topic`,
  `publish_topic`).
- `goga/commands/topics/CODEMANIFEST` — Imports +3 domain types + the
  `update`/`propagate` practices; +2 group methods (`update`, `propagate`);
  the `board` method grows the configuration-load first step; the three
  renderers grow the Base column / the `divergence` JSON key.

### New Entities

- `TopicsCreateConfig(commit: str | None)` — `goga/config/project`,
  `config.py`
- `TopicsUpdateConfig(strategy: str | None, commit: str | None)` —
  `goga/config/project`, `config.py`
- `TopicsPropagateConfig(strategy: str | None, commit: str | None)` —
  `goga/config/project`, `config.py`
- `require_git_version()` — `goga/topics/git`, `exchange.py`
- `is_ancestor(ancestor: str, descendant: str) -> contains: bool` —
  `goga/topics/git`, `exchange.py`
- `resolve_commit_tree(revision: str) -> tree: str` — `goga/topics/git`,
  `exchange.py`
- `merge_tree(ours: str, theirs: str, merge_base: str | None = None) ->
  tree: str | None` — `goga/topics/git`, `exchange.py`
- `create_commit_from_tree(tree: str, parents: list[str], message: str) ->
  commit: str` — `goga/topics/git`, `exchange.py`
- `replay_commits(onto: str, until: str) -> tip: str | None` —
  `goga/topics/git`, `exchange.py`
- `point_branch_at_commit(branch_name: str, commit: str)` —
  `goga/topics/git`, `exchange.py`
- `merge_into_current(revision: str, message: str)` — `goga/topics/git`,
  `switch.py`
- `rebase_current_onto(revision: str)` — `goga/topics/git`, `switch.py`
- `fast_forward_current_branch(revision: str)` — `goga/topics/git`,
  `switch.py`
- `fetch_branch(branch_name: str)` — `goga/topics/git`, `publish.py`
- `push_branch_with_lease(branch_name: str, expected_tip: str)` —
  `goga/topics/git`, `publish.py`
- `push_revision_to_branch(revision: str, branch_name: str)` —
  `goga/topics/git`, `publish.py`
- `TopicUpdated(...)` — `goga/topics/hooks`, `contexts.py`
- `TopicPropagated(...)` — `goga/topics/hooks`, `contexts.py`
- `TopicHooks.emit_updated(...)` — `goga/topics/hooks`, `events.py`
- `TopicHooks.emit_propagated(...)` — `goga/topics/hooks`, `events.py`
- `ExchangeBase(...)` — `goga/topics`, `exchange.py`
- `resolve_exchange_base(...)` — `goga/topics`, `exchange.py`
- `ExchangeTarget(...)` — `goga/topics`, `exchange.py`
- `resolve_exchange_target(...)` — `goga/topics`, `exchange.py`
- `render_commit_template(...)` — `goga/topics`, `exchange.py`
- `update_topic(...)` — `goga/topics`, `updating.py`
- `PropagationPlan(...)` — `goga/topics`, `propagating.py`
- `resolve_propagation(...)` — `goga/topics`, `propagating.py`
- `execute_propagation(...)` — `goga/topics`, `propagating.py`
- `resolve_divergence(...)` — `goga/topics`, `board.py`

### Changed Entities

- `TopicsConfig` — signature `(base_ref, create, update, propagate)`;
  the `publish_commit` field/property is **deleted** from the model; the
  three section properties replace it.
- `ProjectConfig.topics` — property annotation updated for the nested
  shape (the field type `TopicsConfig | None` is unchanged).
- `load_project_config` — step 8 no longer extracts topics; the new step 9
  performs the nested structural extraction; construct moves to step 10.
- `declared_actions` — carries the two new soft-action records.
- `merge_config_amendments` — the path-resolution type tree knows the
  three nested topics models.
- `BoardRecord`, `BoardEntry` — +`divergence: str | None = None` field
  and property.
- `collect_topic_board` — +`base_ref: str | None = None` parameter; step
  10 computes the marker per own-branched topic in the same pass.
- `aggregate_topic_board` — step 5 projects the winner's divergence marker
  into the entry.
- `create_topic`, `publish_topic` — the authored messages render through
  `render_commit_template`; the built-in default template becomes
  `Create topic '{slug}'` with the `{slug}` and `{base}` placeholders.
- `topics` (group) — the subcommand surface grows `update` and
  `propagate`; `board` gains the configuration-load first step.
- `render_topic_board` — six-column rule + the Base column under `info`.
- `render_topic_host_rows` — five-column rule + the Base column under
  `info`.
- `render_board_json` — every record carries the `divergence` key.

### Deleted Entities

- `TopicsConfig.publish_commit` (field + property) — retired by the nested
  topics section; stale authored values pass through the loader silently
  with no warning and no effect (the fresh-start 2.0 breaking-change
  precedent). No other contract entity is deleted.

### Usages and Annotations Changes

- `goga/topics/git` — the `git` practice (inline) grows the checkout-free
  exchange paragraph: merge-tree, commit-tree, plumbing replay, single-ref
  planting, lease push, targeted fetch, the real merge/rebase/ff of the
  current branch, the version gate; the global annotations add the
  exchange-zone paragraph; the new cell-level practice
  `.usages/exchanging.md` (imported by `goga/topics` as `exchanging`).
- `goga/topics` — the global annotations: the sanctioned network set is
  rewritten as the exact set (targeted reported fetches, the inherent
  propagate push, the update publish push, the existing publication and
  deletion pushes; nothing else fetches; the board never touches the
  network) and the exchange paragraph; Imports grow the `exchanging`
  usage.
- `goga/topics/hooks` — the counters (seven moments, nine actions, seven
  emissions) and the notification-only paragraph.
- `goga/commands/topics` — the input-resolution paragraph of the global
  annotations (base flag-beats-configuration with no current-HEAD rung;
  strategy and template verbatim; update asks no confirmation, propagate
  asks exactly one with the `--yes` escape); Imports grow the `update` and
  `propagate` practices.
- `.goga/usages`-level and cell-level practice files updated:
  `goga/config/.usages/project-configuration.md` (nested schema, migration
  note), `goga/topics/.usages/{topic-board,creating,publishing,update,propagate}.md`,
  `goga/topics/hooks/.usages/checkpoints.md`,
  `goga/topics/git/.usages/exchanging.md`,
  `goga/commands/topics/.usages/topics-command.md`.

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga/topics/CODEMANIFEST`, `execute_propagation`, Algorithm step 4:
  **before** — “a non-fast-forwardable situation is a clean error
  suggesting manual git, with nothing planted **and the rollback
  unnecessary**”; **after** — the phrase “and the rollback unnecessary” is
  removed (reason: internal inconsistency — step 8 of the same algorithm
  mandates a uniform full rollback that removes a reconciliation the
  resolution wrote, and the ff error is reachable precisely when a
  reconciliation was written: the reconciliation commit can never be
  contained in the own tip, else the already-carried check would have
  preempted it). The ff error now inherits the uniform step-8 rollback;
  when no reconciliation was written the restore is a harmless no-op ref
  update. Approved by the user (dialog q1, option A). `goga lint` re-run:
  81 cells, 0 errors.

### Fixed by the Design Review (design-review stage, 8 remarks, all approved)

- **R1 (CODEMANIFEST, Critical)** — the content-based nothing-to-do of
  `execute_propagation` needs a commit→tree resolution the git cell did
  not declare (the domain may not call git directly). Added the routine
  `resolve_commit_tree(revision: str) -> tree: str` to
  `goga/topics/git/CODEMANIFEST` (exchange.py; read-only; clean error on
  an unresolvable revision); `goga/topics` imports it and
  `execute_propagation` step 4 references it; the design trace,
  algorithm, counts (13 git routines, 28 facade exports), and tests
  updated; `exchanging.md` grows the content-identity block. `goga lint`:
  81 cells, 0 errors.
- **R2 (CODEMANIFEST, High)** — a reconciliation could move a
  checked-out base branch under the working copy (plumbing bypasses
  git's own current-branch protection; update had no guard while
  propagate did). `resolve_exchange_base` now refuses a branch-shaped
  base whose local branch is the current branch — a clean error asking
  to switch away first, before the fetch (Algorithm step 3 + a
  Requirement bullet); the design trace/algorithm/errors/edge-cases
  updated and `test_resolve_exchange_base_rejects_checked_out_base`
  added. `goga lint`: 81 cells, 0 errors.
- **R3 (Design, High)** — the checkout-free conflicts of `update_topic`
  were under-specified (a wrong "impossible in practice" claim; the
  algorithm block planted `None` on a rebase conflict; the `_restore_base`
  guard did not cover these conflicts — violating the contract's
  "every conflict … pre-operation state"). The trace, the algorithm
  branch, and the guard now handle `merge_tree`→None and
  `replay_commits`→None as clean errors + restore;
  `test_update_topic_checkout_free_conflict_rolls_back_reconciliation`
  added.
- **R4 (Test, Medium)** — `test_cli_propagate_confirmation_and_yes` was
  unrunnable as written (a CliRunner string input is not a TTY); it now
  uses the `_TtyStdin` fixture idiom of `test_topics.py` and gained the
  non-interactive-without-`--yes` branch (d).
- **R5 (Test, Medium)** — two internal contradictions fixed: the lease
  test no longer claims a second (non-existent) pre-flight
  `replay_commits` call on the checkout-free path;
  `test_resolve_propagation_rejects_current_branch_base` rewritten
  cleanly (drafting debris removed).
- **R6 (Test gaps, Medium)** — six additions: the two-commit replay
  chain; the in-place rebase path with the lease; the lease-rejection
  clean error (update stands, no retry); the propagate invalid-strategy
  error naming its key; the reconcile-conflict clean error; the
  `rebase_current_onto` argv test plus the note that the existing
  subcommand-surface enumerations grow to seven entries.
- **R7 (CODEMANIFEST, Low)** — `publish_topic`'s `commit_message`
  parameter annotation now names both `{slug}` and `{base}` through
  `render_commit_template`, matching its own Requirements. `goga lint`:
  81 cells, 0 errors.
- **R8 (Design, Low)** — the dangling `(D1)`/`(D15)` decision markers
  removed; the missing Setup/Trace elements completed for the affected
  negative/edge tests (the 6-element format now holds throughout).

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
CLI layer                         topics domain                    git plumbing
─────────────────────────────     ─────────────────────────────    ─────────────────────────────
goga/commands/topics/topics.py    goga/topics/exchange.py          goga/topics/git/exchange.py
  topics update  ──────────────►    update_topic (updating.py)  ───►  require_git_version
    │ flags → base/strategy/        │  resolve_exchange_target      is_ancestor
    │ template from TopicsConfig    │  resolve_exchange_base  ─────►  merge_tree / replay_commits
    │ (goga/config facade)          │  render_commit_template       create_commit_from_tree
    │ no confirmation               │  pre-flight + real mutation    point_branch_at_commit
    ▼                               │  publish push              ──►  merge_into_current /
  echo result line                  │  TopicHooks.emit_updated        rebase_current_onto /
                                    ▼                                 fast_forward_current_branch
goga/commands/topics/topics.py    goga/topics/propagating.py    ──► goga/topics/git/publish.py
  topics propagate ─────────────►    resolve_propagation            fetch_branch
    │ flags → base/strategy/         │  read-only plan              push_branch_with_lease
    │ template; one confirmation     │  (origin probe, current-      push_revision_to_branch
    ▼                                │   branch guard, message)      (existing: push_branch,
  execute_propagation ──────────►    │  build → plant → push         origin_configured, ...)
  echo result line                   │  retry cycle, uniform         │
                                    │  rollback                     ▼
goga/commands/topics/topics.py    goga/topics/board.py          git (subprocess)
  topics board ────────────────►    collect_topic_board            every invocation:
    │ config load → base_ref         │  resolve_divergence          check=True, captured output,
    ▼                                │    (is_ancestor only)        GIT_TERMINAL_PROMPT=0
  render_topic_board /              aggregate_topic_board
  render_topic_host_rows /          goga/topics/creation.py + publishing.py
  render_board_json                   render_commit_template({slug},{base})
                                    goga/topics/hooks: TopicHooks.emit_updated /
                                      emit_propagated → TopicUpdated / TopicPropagated →
                                      hooks platform (catalog: topics/topic_updated,
                                      topics/topic_propagated — soft)
```

### Data Flows

**Flow 1 — `goga topics update` (current topic, strategy `merge`,
`--publish`)**: CLI resolves `base_ref` (flag → `topics.base_ref` of the
effective `ConfigOverlay`), `strategy` (`topics.update.strategy`, verbatim,
possibly None), `template` (`topics.update.commit`, verbatim) → calls
`update_topic(identifier, base_ref, strategy, template, publish, year)` →
validates the strategy against the whitelist → `resolve_exchange_target`
(current branch → slug + branch) → `resolve_ref_commit(branch)` = own tip →
captures the base's local-branch tip as the rollback tip →
`resolve_exchange_base(base_ref, branch, own_tip)`: version gate, one
reported fetch, projections, containment, optional reconciliation commit →
`is_ancestor(base.tip, own_tip)` decides already-current → ff decision →
current topic: clean-tree probe, read-only pre-flight (`merge_tree` /
`replay_commits` discarded), then the real mutation (`merge_into_current` /
`rebase_current_onto` / `fast_forward_current_branch`) with the rendered
message → `origin_configured` probe → `push_branch` (merge/ff) or
`push_branch_with_lease(branch, pre-rebase own tip)` (rebase with twin) →
`TopicHooks.emit_updated(identity, base.name, base.tip, effective strategy,
outcome, published)` → one result line to stdout.

**Flow 2 — `goga topics propagate` (merge, local base)**: CLI resolves the
inputs like update (strategy/template from `topics.propagate.*`) →
`resolve_propagation`: strategy whitelist, `resolve_exchange_target`,
`origin_configured` guard, current-branch guard, message render → the CLI
asks exactly one confirmation (naming the topic, the target base, and the
inherent push; `--yes` skips; non-interactive without `--yes` is a clean
error; a decline exits 0) → `execute_propagation(plan)`: own tip, rollback
capture, `resolve_exchange_base`, reachability nothing-to-do check, delivery
build (`merge_tree(base.tip, own_tip)` → `create_commit_from_tree(tree,
[base.tip, own_tip], plan.message)`), content-based nothing-to-do check,
plant (`point_branch_at_commit(base.local_branch, delivery)`), push
(`push_branch(base.local_branch)`), one retry cycle on a concurrent-movement
rejection, uniform rollback on every failure →
`TopicHooks.emit_propagated(identity, base.name, strategy, outcome)` → one
result line.

**Flow 3 — `goga topics board` with a configured base**: CLI loads the
configuration the way `clear` does (`load_project_config` + the
`amend_config` checkpoint via `ConfigHooks`; a missing file counts as
unset), prints the amendment summary lines to stderr, extracts
`topics.base_ref` → `collect_topic_board(..., base_ref=base)` computes the
divergence marker of every own-branched topic in the same pass
(`resolve_divergence(own_tip, base_ref)` — local refs only, never a
failure) → `aggregate_topic_board` projects the winner's marker → the
renderers print the Base column (`--info`) or the `divergence` JSON key.

**Flow 4 — configuration load (nested topics)**: `.goga/config.yml` →
`load_project_config` step 9: absent/YAML-null `topics` → None; a
non-mapping → ValueError; `base_ref` and the three sub-mappings
structurally validated (absent/YAML-null → None section; present
non-mapping → ValueError; inside each, `strategy`/`commit` optional
strings, empty/whitespace → None); unknown keys — including the retired
`publish_commit` — silently ignored → `TopicsConfig` assembled into
`ProjectConfig` → the `goga/config` facade re-exports the three new models
→ the `goga/config/hooks` amendment tree accepts nested paths
(`topics.update.strategy`, `topics.create.commit`, …).

### Entity Dependencies

Implementation order (bottom-up; cross-imports between cells are
prohibited, and each layer only imports below itself):

1. `goga/hooks/catalog` (records) — no dependencies inside the change.
2. `goga/config/project` (models, then loader) → `goga/config` (facade
   re-exports) → `goga/config/hooks` (tree + factories).
3. `goga/topics/git` — `exchange.py` (new) + `switch.py`/`publish.py`
   additions + the facade `__init__.py`.
4. `goga/topics/hooks` — `contexts.py`, `events.py` (the new emissions
   resolve their error class through `declared_actions` — the catalog
   record must exist first), facade `__init__.py`.
5. `goga/topics` — `exchange.py`, `board.py` (divergence),
   `creation.py`/`publishing.py` (template engine), `updating.py`,
   `propagating.py`, facade `__init__.py`.
6. `goga/commands/topics` — `topics.py` (`board` step, `create` template
   rung, `update`, `propagate`), `render.py`.

---

## Code Stack Trace

Traces verified against the actual implementation files (module `_run_git`
helpers, the `switching.py` selection machinery, the `events.py` emission
idiom, the `overlay.py` tree, the `loader.py` parse style) and the git
plumbing API (git ≥ 2.38).

### Trace: `require_git_version`

1. **Input**: called by `resolve_exchange_base` step 1 — once per exchange.
2. **Step**: `git version` via the module `_run_git` (DEVNULL stdin,
   UTF-8/replace decode, `GIT_TERMINAL_PROMPT=0`) → stdout like
   `git version 2.43.0 (Apple Git-151)`.
3. **Step**: parse `version (\d+)\.(\d+)` from the first line →
   `(major, minor)` → checkpoint: parse failure of the regex is an
   infrastructure anomaly → treat as the gate failure (clean error naming
   the unparsed output) — **passed** (never a silent pass).
4. **Step**: `(major, minor) < (2, 38)` → raise
   `RuntimeError("goga needs git >= 2.38 for the topic exchange (found <present>)")`
   — a semantic gate failure, not a subprocess failure; the domain
   clean-error wrappers catch `RuntimeError` alongside the subprocess
   exceptions (see Cross-cutting) → checkpoint: the error names both the
   required and the present versions — **passed**.
5. **Output**: `None`; read-only, no repository state touched.

#### Checkpoint Summary
- version parse + floor compare: passed
- error channel (`RuntimeError` + domain wrapper catch): passed — matches
  the contract's “a clean error naming the required and present versions”

### Trace: `is_ancestor(ancestor, descendant)`

1. **Input**: `(ancestor, descendant)` — any resolvable revisions, from
   `resolve_exchange_base`, `update_topic`, `execute_propagation`,
   `resolve_divergence`.
2. **Step**: `git merge-base --is-ancestor <ancestor> <descendant>`
   **without** `check=True` → checkpoint: `merge-base --is-ancestor` exits
   0 = containment, 1 = no containment, >1 = failure (unresolvable rev) —
   the distinction is why this routine may not reuse the `check=True`
   helper verbatim — **passed**.
3. **Step**: returncode 0 → `True`; 1 → `False`; otherwise raise
   `subprocess.CalledProcessError` (raw — the domain wraps).
4. **Output**: plain `bool`; read-only, no network.

#### Checkpoint Summary
- exit-code trichotomy handling: passed
- raw propagation of real failures: passed (matches “peeled to its commit”
  — `--is-ancestor` resolves annotated tags itself)

### Trace: `resolve_commit_tree(revision)`

1. **Input**: any resolvable revision — the effective tip or the own tip
   of `execute_propagation`'s content-based nothing-to-do check.
2. **Step**: `git rev-parse --verify <revision>^{tree}` via the module
   `_run_git` → checkpoint: the `^{tree}` peel resolves a commit into
   the tree oid it carries — the content identity git itself compares —
   **passed**.
3. **Step**: an unresolvable revision → rc ≠ 0 → raw
   `CalledProcessError` (the domain surfaces it as a clean error); both
   callers pass freshly resolved commits, so the failure is unreachable
   in practice.
4. **Output**: the tree oid (`stdout.strip()`); read-only, no network.

#### Checkpoint Summary
- commit→tree peel (`^{tree}`): passed
- read-only guarantee: passed

### Trace: `merge_tree(ours, theirs, merge_base=None)`

1. **Input**: ours/theirs revision strings; optional explicit base (the
   cherry-pick steps of `replay_commits`; `resolve_exchange_base`
   reconciliation passes None).
2. **Step**: `git merge-tree --write-tree [--merge-base=<base>] <ours>
   <theirs>` → checkpoint: git ≥ 2.38 writes the merged tree oid as the
   first stdout line and exits 0 on a clean merge, exits 1 on conflict —
   **passed** (the version gate of the caller guarantees ≥ 2.38).
3. **Step**: rc 0 → `stdout.splitlines()[0].strip()` = the tree oid; rc 1 →
   `None` (the conflict signal, not an error); rc > 1 → raw
   `CalledProcessError`.
4. **Step**: nothing else is touched — checkpoint: `--write-tree` writes
   only new objects (dangling until planted), the working copy, the index,
   HEAD, and every ref stay untouched — **passed**; one git invocation per
   merge — **passed**.
5. **Output**: `str | None`.

#### Checkpoint Summary
- conflict-as-None vs infrastructure-error split: passed
- quarantine guarantee: passed

### Trace: `create_commit_from_tree(tree, parents, message)`

1. **Input**: a tree oid written by `merge_tree` (or a resolved tree), the
   ordered parent list (two for a merge/reconciliation, one for a squash),
   the final message (already rendered — placeholders belong to the
   caller).
2. **Step**: `git commit-tree <tree> [-p <p1>] [-p <p2> ...] -m <message>`
   with DEVNULL stdin → checkpoint: the DEVNULL stdin is load-bearing —
   `commit-tree -m ""` reads the operand from stdin otherwise and hangs
   (the exact pitfall documented in `publish.py`) — **passed**.
3. **Step**: author and committer come from the repository git identity; an
   unset identity or an unreadable tree → rc ≠ 0 → raw
   `CalledProcessError` (the domain surfaces it as a clean error).
4. **Step**: no ref is created, moved, or deleted — checkpoint: the commit
   dangles — **passed**.
5. **Output**: the new commit hash (`stdout.strip()`).

#### Checkpoint Summary
- parents order preserved (argv order): passed
- dangling guarantee: passed

### Trace: `replay_commits(onto, until)`

1. **Input**: `onto` — the new base (the effective tip); `until` — the
   replayed tip (the own tip).
2. **Step**: `git rev-list --reverse <until> ^<onto>` → the commits
   reachable from `until` and not from `onto`, oldest first → checkpoint:
   `--reverse` gives the oldest-first order the contract requires —
   **passed**; an empty list (nothing to replay) → return `onto` itself
   (the idempotent replay of a fully-carried line — the tip of an empty
   replay is the base) → checkpoint: contract says “the final replayed tip”
   — with zero commits the running result starts as `onto` — **passed**.
3. **Step**: per commit C with parent P (from `git rev-list --parents` or
   `git show -s --format=%P C`): `tree = merge_tree(ours=<running>,
   theirs=C, merge_base=P)` — the cherry-pick three-way with the explicit
   base → checkpoint: parent-of-C as the merge base is the standard
   cherry-pick semantics — **passed**; a merge commit (two parents) uses
   its first parent as the base.
4. **Step**: read C's author and message verbatim: `git show -s
   --format=%an%x1f%ae%x1f%aI%x1f%B C` (unit-separator framing survives
   names containing spaces; `%B` is the raw body) → build the new commit
   via `create_commit_from_tree`-style `git commit-tree <tree> -p
   <running> -m <message>` with `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`/
   `GIT_AUTHOR_DATE` exported for the single invocation → checkpoint:
   author + message preserved verbatim, committer = repository identity —
   **passed**.
5. **Step**: `tree is None` at any step → return `None` (the caller's
   conflict signal); commits are neither skipped, reordered, nor squashed.
6. **Output**: the final replayed tip `str | None`; read-only w.r.t. refs —
   every commit dangles until the caller plants.
7. **Step**: the in-place pre-flight of `update_topic` calls this same
   routine and discards the result → checkpoint: contract requirement
   “The pre-flight of an in-place rebase is this same call, discarded” —
   **passed** by construction.

#### Checkpoint Summary
- oldest-first enumeration: passed
- author/message preservation via `GIT_AUTHOR_*` env: passed
- conflict → None, never an error: passed

### Trace: `point_branch_at_commit(branch_name, commit)`

1. **Input**: the short name of an **existing** branch; the target commit.
2. **Step**: `git update-ref refs/heads/<branch_name> <commit>` → the
   single-ref planting mutation / the rollback restore primitive.
3. **Step**: full-ref form → checkpoint: a dash-leading short name cannot
   be parsed as an option (the documented concern of
   `create_branch_at_commit`) — **passed**; a git failure raises raw.
4. **Output**: `None`; exactly one ref update; the working copy, the index,
   and HEAD untouched (a checked-out branch's HEAD symref moves only via
   the ref itself — the caller owns the checked-out policy).
5. **Constraint check**: “Do not create the branch” — the routine must not
   be used as a creator; `update-ref` would create a missing ref, so the
   existence precondition is the caller's (every caller resolves the
   branch through the inventory or a captured tip first). Documented in
   the docstring; creation stays `create_branch_at_commit` (create-only
   semantics).

#### Checkpoint Summary
- single-mutation atomicity: passed
- existence precondition ownership: passed (documented)

### Trace: `merge_into_current(revision, message)`

1. **Input**: the effective tip; the rendered final message.
2. **Step**: `git merge --no-ff --no-edit -m <message> <revision>` →
   checkpoint: `--no-ff` guarantees a merge commit even when a
   fast-forward is possible (“A merge commit lands even when a
   fast-forward is possible”) — **passed**; `--no-edit` suppresses any
   editor/GitHub-style message prompt.
3. **Step**: failure (conflict included — the pre-flight makes it
   unreachable in practice) → raw `CalledProcessError` with git's reason.
4. **Output**: `None`; touches the working copy, the index, and HEAD — the
   sanctioned in-place path; no push.

#### Checkpoint Summary
- never-fast-forward guarantee: passed
- caller-owned cleanliness probe (not probed here): passed

### Trace: `rebase_current_onto(revision)`

1. **Input**: the effective tip as the new base.
2. **Step**: `git rebase <revision>` → git replays the current branch's
   commits preserving authors and messages; failure → raw
   `CalledProcessError` (git leaves its own rebase state — the caller's
   pre-flight makes conflicts unreachable; a mid-rebase infrastructure
   failure is git's domain).
3. **Output**: `None`; the working copy is rewritten; no pre-rebase tip
   capture here — the caller captured it for the lease push; no push.

#### Checkpoint Summary
- no tip capture (caller's duty): passed

### Trace: `fast_forward_current_branch(revision)`

1. **Input**: the effective tip to advance to.
2. **Step**: `git merge --ff-only <revision>` → checkpoint: a
   non-fast-forwardable situation is a git error (rc ≠ 0) surfaced raw →
   the domain's clean error; no fallback merge — **passed**.
3. **Output**: `None`; no commit authored; the working copy advances.

#### Checkpoint Summary
- ff-only strictness: passed

### Trace: `fetch_branch(branch_name)`

1. **Input**: the short branch name to refresh from origin.
2. **Step**: `git fetch origin +refs/heads/<b>:refs/remotes/origin/<b>`
   → checkpoint: the explicit forced refspec updates exactly one
   remote-tracking ref (the leading `+` survives a rewritten remote), in
   line with “exactly one branch, nothing else moves” — **passed**; the
   working copy, the index, and HEAD untouched — **passed**.
3. **Step**: rc ≠ 0 → inspect stderr: it contains
   `couldn't find remote ref` → the twin-absent case → **return normally**
   (the twin stays absent; the local projection stands alone); any other
   stderr → raw `CalledProcessError` (a clean error carrying the reason at
   the domain boundary) → checkpoint: the absent-branch matcher is the one
   git wordings pair (`couldn't find remote ref …`) across the supported
   floor (2.38) — **passed, documented**.
4. **Output**: `None`; silent — no printing (the reporting stdout line
   belongs to the calling module).

#### Checkpoint Summary
- twin-absent suppression vs real failure: passed
- silence guarantee: passed

### Trace: `push_branch_with_lease(branch_name, expected_tip)`

1. **Input**: the local branch short name; the tip the remote must stand
   on (captured by the caller immediately before the rewrite).
2. **Step**: `git push --no-follow-tags
   --force-with-lease=refs/heads/<b>:<expected_tip> origin
   refs/heads/<b>:refs/heads/<b>` → checkpoint: the full-ref lease form is
   unambiguous; a remote standing anywhere else refuses with git's
   “stale info” rejection → raw error → the domain's clean error, never an
   overwrite — **passed**; the full refspec can never start with a dash
   (mirrors `push_branch`'s documented rule).
3. **Step**: no fetch refreshes the lease; no retry — both belong to the
   caller.
4. **Output**: `None`; a network operation; the local branch stays.

#### Checkpoint Summary
- lease bound to the caller's expected value: passed

### Trace: `push_revision_to_branch(revision, branch_name)`

1. **Input**: the delivery commit; the remote branch short name (created
   when absent).
2. **Step**: `git push --no-follow-tags origin <revision>:refs/heads/<b>`
   → a plain push: no force, no lease; a non-fast-forward remote rejects →
   raw error → the domain's retry-or-fail policy.
3. **Output**: `None`; no local branch is created; the working copy
   untouched; exactly the named branch.

#### Checkpoint Summary
- write-through shape: passed

### Trace: `load_project_config` (the topics step)

1. **Input**: the parsed `.goga/config.yml` document (`data: dict`).
2. **Step** (step 9 of the contract): `raw = data.get("topics")` → None →
   `topics = None`; a non-mapping → `ValueError("'topics' must be a
   mapping in .goga/config.yml")`.
3. **Step**: `base_ref = _parse_topics_field(raw.get("base_ref"),
   "topics.base_ref")` — the existing helper (absent/YAML-null → None;
   non-string → ValueError naming the key; empty/whitespace → None via
   `.strip() or None`).
4. **Step**: per section in `("create", "update", "propagate")`:
   `section_raw = raw.get(name)` → None → section None; a non-mapping →
   `ValueError("'topics.<name>' must be a mapping in .goga/config.yml")`;
   inside, `commit` (create) or `strategy`/`commit` (update, propagate)
   run through `_parse_topics_field` with the dotted key names →
   checkpoint: unknown keys — including the retired `publish_commit` —
   are never read: no warning, no effect — **passed** (the
   `data.get`-only extraction style guarantees it).
5. **Step** (step 10): assemble `ProjectConfig(..., topics=TopicsConfig(
   base_ref=..., create=..., update=..., propagate=...))`.
6. **Output**: the loader returns the assembled `ProjectConfig`; the
   ValueError surfaces to the CLI as a clean error.

#### Checkpoint Summary
- nested structural validation: passed
- silent retirement of `publish_commit`: passed

### Trace: `TopicsConfig` / `TopicsCreateConfig` / `TopicsUpdateConfig` / `TopicsPropagateConfig`

1. **Input**: keyword-only constructor args from the loader (or the
   overlay factories).
2. **Step**: frozen kw_only dataclasses; every field typed
   `str | None` / `Topics*Config | None` **with `= None` defaults** →
   checkpoint: defaults simplify the overlay materialization factories and
   keep the loader call sites readable; the immutable-verbatim stance
   matches the contract Requirements — **passed**.
3. **Output**: value objects; no behavior, no validation (structural
   typing belongs to the loader, semantics to the consumer — the
   Constraints hold).

### Trace: `declared_actions` (the two records)

1. **Input**: none (module constant).
2. **Step**: add `Action(domain="topics", name="topic_propagated",
   error_class="soft")` and `Action(domain="topics", name="topic_updated",
   error_class="soft")` to `_DECLARED_ACTIONS` (the literal keeps its
   hand-ordered per-domain grouping; `declared_actions()` sorts on return —
   ordering is not a contract).
3. **Output**: the events cell's `_error_class(action)` now resolves both
   new addresses → checkpoint: an emission before the record exists would
   raise `ValueError(unknown hook action)` — implementation order puts the
   catalog first — **passed**.

### Trace: `TopicUpdated` / `TopicPropagated` / `TopicHooks.emit_updated` / `TopicHooks.emit_propagated`

1. **Input**: the operation's own facts (identity, base name, tip,
   strategy, outcome, published flag) — passed by `update_topic` /
   `execute_propagation`; no repository reads.
2. **Step**: `emit_updated` builds `TopicUpdated(identity=..., base=...,
   effective_tip=..., strategy=..., outcome=..., published=...)` — a
   frozen kw_only dataclass mirroring `TopicSwitched`'s shape.
3. **Step**: `emit_hook_event(_run_registry(), "topics", "topic_updated",
   context_for=lambda _tool: context)` — the exact idiom of the existing
   five emissions: the shared run registry (`_run_registry()` — one
   `HookRegistry.build_once()` per run), the domain constant, the
   per-tool context view over the same instance.
4. **Step**: `_error_class("topic_updated")` resolves `soft` through the
   catalog → a failing hook warns and the delivery continues.
5. **Output**: fire-and-forget — nothing collected, nothing returned →
   checkpoint: matches the contract Requirements and the
   `declaring-actions` practice — **passed**. `emit_propagated` is the
   same trace over `TopicPropagated` (no pushed flag — the push is
   inherent).

#### Checkpoint Summary
- address/error-class pairing: passed
- context identity shared across the per-tool views: passed

### Trace: `render_commit_template(template, slug, base)`

1. **Input**: the template string, the topic slug, the base name as
   addressed.
2. **Step**: `template.replace("{slug}", slug).replace("{base}", base)` —
   pure text; unknown placeholders (`{whatever}`) never match and stay
   verbatim; no repository reads.
3. **Output**: the rendered message. Consumers: `create_topic` (the
   built-in path default), `publish_topic` (the create-section template),
   `update_topic` (the update-section template), `resolve_propagation`
   (the propagate-section template). → checkpoint: the single template
   engine of the domain's authored messages — `creation.py`'s and
   `publishing.py`'s current `.replace("{slug}", ...)` sites route through
   it — **passed**.

### Trace: `resolve_exchange_base(base_ref, own_branch, own_tip)`

1. **Input**: the base revision string (flag or configuration), the
   topic's own branch name, the own branch tip.
2. **Step**: `require_git_version()` — the gate fires here, once for
   every caller.
3. **Step**: `base_ref == own_branch` or `base_ref == f"origin/
   {own_branch}"` → clean error “the topic is its own base”.
4. **Step**: branch-shape detection over `list_branch_refs()` via the
   module helper `_base_branch_names(base_ref, refs)`: if `base_ref`
   starts with `origin/` → `(local := short(base_ref),
   twin := base_ref)`; else `(local := base_ref, twin :=
   f"origin/{base_ref}")`; branch-shaped iff the inventory carries
   `local` as a local ref or `twin` as a remote ref → checkpoint: the
   helper is shared by `update_topic`, `resolve_propagation`, and
   `execute_propagation` for their rollback-capture and current-branch
   guards — one detection rule everywhere — **passed**.
5. **Step** (the checked-out-base guard): branch-shaped and
   `local == resolve_current_branch_name()` → clean error asking to
   switch away first — before the fetch, before any write → checkpoint:
   a reconciliation must never move the checked-out branch under the
   working copy (`update-ref` bypasses git's own current-branch
   protection — the moved ref would leave HEAD pointing past the files
   on disk) — **passed**; a detached HEAD (`None`) passes the guard.
6. **Step** (non-branch-shaped): `tip = resolve_ref_commit(base_ref)`
   (a tag or a hash — read-only, no fetch; unresolvable → clean error
   carrying the git reason) → return `ExchangeBase(name=base_ref,
   tip=tip, local_branch=None, reconciled=False)`.
7. **Step** (branch-shaped): `click.echo(f"Fetching origin/{local}...")`
   then `fetch_branch(local)` → the twin stays absent on the
   absent-remote report; other failures are clean errors.
8. **Step**: projections — the local tip (`resolve_ref_commit(local)`
   when the local branch exists) and the twin tip
   (`resolve_ref_commit(twin)` when the twin exists), each as it stands
   **after** the fetch. One projection → it is the effective tip
   (`local_branch` = the local name or None).
9. **Step**: both — `is_ancestor(local, twin)` → twin is effective;
   `is_ancestor(twin, local)` → local is effective.
10. **Step**: diverged — `own_tip` contains **every** projection
    (`is_ancestor(local, own_tip) and is_ancestor(twin, own_tip)`) →
    effective tip = `own_tip`, nothing written, `reconciled=False` (the
    already-carried state) → checkpoint: the check precedes the
    reconciliation write — an up-to-date topic mutates nothing —
    **passed**.
11. **Step**: otherwise the reconciliation — `tree = merge_tree(local,
    twin)`; `None` → clean error “reconcile the branch manually”
    (nothing mutated); else `commit = create_commit_from_tree(tree,
    [local_tip, twin_tip], f"Reconcile base '{base_ref}'")` and
    `point_branch_at_commit(local, commit)` → effective tip = `commit`,
    `reconciled=True`. → checkpoint: exactly one fetch, reported before
    it runs, branch-shaped bases only — **passed**; the reconciliation
    lands only on the local base branch and is never pushed here —
    **passed**; atomicity — the tree and the commit dangle until the
    single `update-ref` — **passed**.
12. **Output**: `ExchangeBase(name=base_ref, tip, local_branch,`
    `reconciled)` — the caller applies its strategy to `tip`.

#### Checkpoint Summary
- self-base guard: passed
- checked-out-base guard (before the fetch): passed
- tag/hash path never fetches: passed
- descendant-of-pair / already-carried / reconciliation trichotomy: passed
- single-fetch + echo-before-run: passed

### Trace: `resolve_exchange_target(identifier, year=None)`

1. **Input**: the user identifier (or None for the current topic); the
   optional year.
2. **Step** (`identifier is None`): `current = resolve_current_branch_name()`
   → None (detached) → clean error “no current branch”; the candidates of
   `resolve_switch_candidates(current, year)` filtered to
   `branch == current` → none, or the survivor's `topic is None` → clean
   error naming the branch (it hosts no topic); the survivor gives
   `topic` and `branch` (a local name — the current branch is local by
   construction).
3. **Step** (identifier given): `resolve_switch_candidates(identifier,
   year)` → none → clean error with the board hint; several → the
   numbered list with statuses and `click.prompt("Select a branch by
   number", type=click.IntRange(1, len))` — the exact
   `_choose_candidate` idiom of `switching.py` (imported from
   `.switching`, one selection surface in the package) — or the failure
   with the list when stdin is not a terminal; the chosen candidate's
   `topic is None` → clean error (a branch without a topic is no
   addressee).
4. **Step**: the chosen candidate `remote=True` (its local twin was
   dropped by the tier collapse — a surviving remote candidate means
   remote-only) → clean error hinting `goga topics switch` first.
5. **Step**: `current = resolve_current_branch_name()`; return
   `ExchangeTarget(topic=..., branch=chosen.branch, current=(chosen.branch
   == current))`.
6. **Output**: the addressed target with the local branch name →
   checkpoint: read-only, nothing mutated — **passed**; the remote-only
   refusal fires here for both exchange operations — **passed**.

#### Checkpoint Summary
- reuse of the switch tiers and the numbered selection: passed
- remote-only refusal centralization: passed

### Trace: `update_topic(identifier, base_ref, strategy, commit_message, publish=False, year=None)`

1. **Input**: the CLI-resolved base (a flag beat the configuration), the
   verbatim strategy source and template (None = the built-in defaults),
   the publish flag, the scoped year.
2. **Step**: `effective_strategy = strategy if strategy in {"merge",
   "rebase", "ff-else-merge", "ff-else-rebase"} else ("merge" if strategy
   is None else error)` — an invalid non-None value → clean configuration
   error naming `topics.update.strategy`, before anything else.
3. **Step**: `target = resolve_exchange_target(identifier, year)`;
   `own_tip = resolve_ref_commit(target.branch)`; `identity =
   TopicIdentity(slug=target.topic, year=resolved_year,
   branch=target.branch)`.
4. **Step**: `refs = list_branch_refs()`; `(local, _twin) =
   _base_branch_names(base_ref, refs)`; when `local` exists in the
   inventory → `rollback_tip = resolve_ref_commit(local)` (captured
   **before** the resolution may write a reconciliation onto it);
   `base = resolve_exchange_base(base_ref, target.branch, own_tip)`.
5. **Step**: `is_ancestor(base.tip, own_tip)` → the already-current
   idempotent success: `TopicHooks().emit_updated(identity,
   base=base.name, effective_tip=base.tip, strategy=effective_strategy,
   outcome="already-current", published=False)`; return the result line;
   `publish` publishes nothing here.
6. **Step** (the ff decision): `strategy in {"ff-else-merge",
   "ff-else-rebase"} and is_ancestor(own_tip, base.tip)` → realized =
   `fast-forward`; else realized = `effective_strategy`.
7. **Step** (`target.current` — the in-place path): dirty tree
   (`not is_working_tree_clean()`) → clean error + the rollback guard
   (below); pre-flight — realized merge → `merge_tree(own_tip, base.tip)`
   (discarded), realized rebase → `replay_commits(base.tip, own_tip)`
   (discarded); `None` → clean error suggesting manual git + the rollback
   guard; then the real mutation: merge → `merge_into_current(base.tip,
   message)`; rebase → `rebase_current_onto(base.tip)`; fast-forward →
   `fast_forward_current_branch(base.tip)`.
8. **Step** (another topic — fully checkout-free): realized merge →
   `tree = merge_tree(own_tip, base.tip)` — `None` is the conflict
   signal, exactly as in the in-place pre-flight (the same computation
   over the same pair): a clean error suggesting manual git +
   `_restore_base`; a tree → `commit =
   create_commit_from_tree(tree, [own_tip, base.tip], message)`,
   `point_branch_at_commit(target.branch, commit)`; rebase → `tip =
   replay_commits(base.tip, own_tip)` — `None` → the same clean error
   and restore; a tip → `point_branch_at_commit(target.branch, tip)`;
   fast-forward → `point_branch_at_commit(target.branch, base.tip)` —
   no commit authored. → checkpoint: objects
   dangle until the single ref update — atomic by construction —
   **passed**; every conflict of the path is detected read-only before
   the single plant — **passed**.
9. **Step** (`publish`): `not origin_configured()` → clean error (the
   confirmed update stands); realized merge/fast-forward →
   `push_branch(target.branch)`; realized rebase → the addressee's origin
   twin exists in the inventory ? `push_branch_with_lease(target.branch,
   own_tip)` (the pre-rebase own tip — captured immediately before the
   rebase by construction of step 3) : `push_branch(target.branch)`; a
   failed push surfaces git's reason as a clean error — the update stands
   (the single atomicity exception; the reconciliation stands with it).
10. **Step**: `emit_updated(identity, base.name, base.tip,
    effective_strategy, outcome, published=publish)` with the outcome
    `merged` / `rebased` / `fast-forwarded`; return the single result
    line: `Updated topic {year}/{slug} from '{base}' via {strategy} ({outcome})`.
11. **The rollback guard** (a design elaboration of the contract's
    requirement): a helper `_restore_base(base, rollback_tip)` invoked on
    the dirty-tree error, the pre-flight conflict error, and every
    checkout-free build conflict (merge tree `None`, replay `None`) — when
    `base.reconciled and rollback_tip is not None` →
    `point_branch_at_commit(base.local_branch, rollback_tip)`; failures
    of the restore itself are suppressed so the original reason surfaces.
    → checkpoint: “a conflicted update leaves the repository at its
    pre-operation state” — **passed** on every conflict path of the
    operation.

#### Checkpoint Summary
- strategy whitelist before anything else: passed
- rollback-tip capture ordering (before the resolution): passed
- idempotent already-current (no publish): passed
- pre-flight before every in-place mutation: passed
- checkout-free build conflicts (merge tree None, replay None) → clean
  error + rollback guard: passed
- lease bound to the pre-rebase own tip with no extra fetch: passed
- publish atomicity exception: passed

### Trace: `resolve_propagation(identifier, base_ref, strategy, commit_message, year=None)`

1. **Input**: the CLI-resolved base; the verbatim strategy source and
   template.
2. **Step**: strategy whitelist `{"merge", "ff", "squash"}` — invalid →
   clean error naming `topics.propagate.strategy`.
3. **Step**: `target = resolve_exchange_target(identifier, year)`.
4. **Step**: `not origin_configured()` → clean error (the push is
   inherent, the remote must exist) — before any mutation.
5. **Step**: `(local, _twin) = _base_branch_names(base_ref,
   list_branch_refs())`; `local is not None and local ==
   resolve_current_branch_name()` → clean error asking to switch away
   first.
6. **Step**: `message = render_commit_template(commit_message if
   commit_message is not None else "Propagate topic '{slug}' into
   '{base}'", target.topic, base_ref)`.
7. **Step**: return `PropagationPlan(target=target, base_ref=base_ref,
   strategy=strategy, message=message, year=resolved_year)` → checkpoint:
   fully read-only — no fetch, no ref write, no working-copy touch; a
   declined confirmation performs nothing — **passed** (the ff
   fast-forwardability stays unverified here — it is authoritative only
   at execution against the effective tip).

### Trace: `execute_propagation(plan)`

1. **Input**: the confirmed plan (the strategy is validated and the
   message rendered).
2. **Step**: `own_tip = resolve_ref_commit(plan.target.branch)`; rollback
   capture exactly as in `update_topic` step 4 (when the base names a
   local branch, before the resolution may write onto it).
3. **Step**: `base = resolve_exchange_base(plan.base_ref,
   plan.target.branch, own_tip)`; `base.local_branch ==
   resolve_current_branch_name()` → clean error asking to switch away
   first.
4. **Step**: `is_ancestor(own_tip, base.tip)` → the reachability form of
   nothing-to-do: `emit_propagated(identity, base.name, plan.strategy,
   "nothing-to-do")`, return the line; a reconciliation the resolution
   wrote stands as sanctioned base bookkeeping.
5. **Step** (build): merge → `tree = merge_tree(base.tip, own_tip)`;
   squash → the same tree, single parent; ff → `is_ancestor(base.tip,
   own_tip)` must hold, else clean error suggesting manual git (the
   uniform rollback applies — Applied Fixes), delivery = `own_tip` (no
   commit authored); `tree is None` → conflict → clean error + rollback;
   merge → `delivery = create_commit_from_tree(tree, [base.tip,
   own_tip], plan.message)`; squash → `delivery =
   create_commit_from_tree(tree, [base.tip], plan.message)`.
6. **Step** (content-based nothing-to-do): `base_tree =
   resolve_commit_tree(base.tip)`; `delivery_tree` = the `merge_tree`
   result (merge/squash) or `resolve_commit_tree(own_tip)` (ff); equal →
   emit nothing-to-do, return the line — nothing planted, nothing pushed,
   the reconciliation stands.
7. **Step** (plant): `base.local_branch is not None` →
   `point_branch_at_commit(base.local_branch, delivery)`; a remote-only
   base plants nothing locally.
8. **Step** (push — inherent): the local path → `push_branch(
   base.local_branch)` (creates the remote branch when absent); the
   write-through → `push_revision_to_branch(delivery, short_name(
   plan.base_ref))` — `short_name` strips a leading `origin/` so the
   remote branch is named correctly.
9. **Step** (the retry cycle — once): a push failure whose stderr
   matches the concurrent-movement rejection signature (`rejected`,
   `non-fast-forward`, or `fetch first`) → echo
   `Fetching origin/{short}...`, `fetch_branch(short)`, re-resolve the
   effective tip by re-running the resolution tail (projections →
   containment → reconciliation over the refreshed pair), rebuild the
   delivery (steps 5–6, the nothing-to-do forms included), re-plant,
   re-push; a second rejection (or a first failure outside the
   signature) → rollback + clean error.
10. **Step** (the uniform rollback): on every failure (conflict,
    ff-impossible, a failed push, a failed retry) — `base.local_branch is
    not None and rollback_tip is not None` →
    `point_branch_at_commit(base.local_branch, rollback_tip)`, removing
    a reconciliation the resolution wrote (a no-op update-ref when
    nothing was written); restore failures are suppressed so the original
    reason surfaces; then the clean error.
11. **Step**: `emit_propagated(identity, base.name, plan.strategy,
    outcome)` — `merged` / `fast-forwarded` / `squashed`; return the
    single result line: `Propagated topic {year}/{slug} into '{base}' via {strategy} ({outcome})`.
12. → checkpoint: always checkout-free — the working copy, the index,
    and HEAD never touched — **passed**; the topic stays alive — its
    branch and directory untouched — **passed**; the retry runs exactly
    once — **passed**.

#### Checkpoint Summary
- both nothing-to-do forms (reachability + identical tree): passed
- plant/push split local vs write-through: passed
- retry-cycle bound: passed
- uniform rollback incl. the ff error (post-fix): passed

### Trace: `resolve_divergence(own_tip, base_ref=None)`

1. **Input**: the own-branch tip commit; the configured base revision
   string (None → None immediately).
2. **Step**: projections from local refs only — a branch-shaped base:
   the local tip and the twin tip, each via `resolve_ref_commit` inside
   `try/except subprocess.CalledProcessError` (an unresolvable side is
   skipped); a tag/hash base: `resolve_ref_commit(base_ref)` as the
   single projection; every side unresolvable → return None — never an
   error.
3. **Step**: `own_tip` contains every projection (`is_ancestor` for
   each) → `"current"`; otherwise `"behind"` → checkpoint: the rule
   matches the exchange's already-carried rule — the diverged base pair
   reads as behind (no reconciliation here) — **passed**.
4. **Output**: `"behind" | "current" | None`; no fetch, no mutation,
   never a failure.

### Trace: `collect_topic_board` (the divergence step)

1. **Input**: the existing collection inputs plus
   `base_ref: str | None = None`.
2. **Step**: the collection proceeds exactly as today through step 9;
   step 10 — for every own-branched topic (the primary-filter
   survivors): resolve the own-branch tip — the local branch's
   `resolve_ref_commit(name)` when the inventory carries it, else the
   twin's — and compute `resolve_divergence(own_tip, base_ref)` when
   `base_ref` is not None, else None → the marker is **topic-scoped**:
   every record of the topic carries the same `divergence` value (the
   field reads “the topic's own-branch divergence marker”; per-host audit
   rows of one topic then agree, and the aggregate projects the winner's)
   → checkpoint: the pass never fetches and never fails on an
   unconfigured or unresolvable base — `resolve_divergence` cannot raise
   on the base — **passed**.
3. **Step**: `base_ref` None → every marker None; the rest of the
   pipeline (filters, sort) is untouched.
4. **Output**: the records with the new field; existing callers that
   omit `base_ref` see None markers — an additive, back-compatible
   change.

### Trace: `aggregate_topic_board` (the projection)

1. **Input**: the records (each possibly carrying `divergence`).
2. **Step**: the winner selection is unchanged; step 5 additionally
   copies the winner's `divergence` into the entry → checkpoint: the
   winner is always an own-branch record, which carries the topic's
   marker — **passed**; no git access (the pure-projection requirement
   holds).
3. **Output**: entries with the projected marker.

### Trace: `create_topic` / `publish_topic` (the template engine switch)

1. **Input**: unchanged signatures; `commit_message` is the create-section
   template (the caller resolves `topics.create.commit`), None = the
   built-in default.
2. **Step**: every authored message site composes through
   `render_commit_template(template, slug, base_name)` with the default
   `Create topic '{slug}'`; `creation.py`'s no-switch path renders the
   built-in default with the operation's `base_ref` as the base; the
   existing `("...").replace("{slug}", ...)` sites are replaced by the
   shared call → checkpoint: the `{base}` placeholder becomes available
   everywhere; unknown placeholders stay verbatim — **passed**.
3. **Output**: unchanged result lines; the checkpoints receive the
   rendered message as before.

### Trace: `topics.board` (the configuration step)

1. **Input**: the board flags; the scoped year.
2. **Step** (new step 1): `section = _topics_section()` — the
   `clear`-style lazy load (`load_project_config` +
   `ConfigHooks().amend_config(config=...)`, the summary lines to stderr,
   FileNotFoundError → None); `base = section.base_ref if section is not
   None else None`; both `collect_topic_board` calls receive
   `base_ref=base` → checkpoint: no flag exists — the board reads the
   configuration only; a missing configuration file counts as unset —
   the divergence stays None and the board renders with empty Base
   cells, never an error — **passed**.
3. **Step**: the rest of the algorithm is unchanged (the json/info
   conflict check now precedes, per the renumbered steps).

### Trace: `topics.update` / `topics.propagate` (CLI)

1. **Input**: the IDENTIFIER positional (optional), `--base-ref`,
   `--publish/-p` (update) or `--yes/-y` (propagate), the group year.
2. **Step** (update): `section = _topics_section()` (lazily — only when
   `base_ref is None` or the template/strategy must come from the
   configuration; the three read together means one load); `base =
   base_ref or section.base_ref` → None → clean error naming the flag
   and the configuration line, before anything else; `strategy =
   section.update.strategy if section and section.update else None`
   (verbatim); `template = section.update.commit ...` (verbatim);
   delegate to `update_topic(identifier, base, strategy, template,
   publish, scope.year)`; echo the result line; exit 0/1 → checkpoint:
   no strategy validation at the CLI (the domain owns the whitelist and
   its error) — **passed**; no confirmation — **passed**; the --help
   text names the addressee rule (omitted IDENTIFIER addresses the
   current topic).
3. **Step** (propagate): the same base/strategy/template resolution over
   `topics.propagate.*`; `plan = resolve_propagation(identifier, base,
   strategy, template, scope.year)`; without `yes`: `not
   sys.stdin.isatty()` → clean error; else one
   `click.confirm(f"Propagate topic {plan.target.topic} into '{base}'
   (pushes to origin)?")` — declined → exit 0 with nothing done;
   `execute_propagation(plan)`; echo the line → checkpoint: exactly one
   confirmation naming the target and the inherent push — **passed**;
   the `-y` short form collides with the group `--year/-y` — the
   positions on the command line distinguish them (the same documented
   collision as `delete`/`clear`).
4. **Output**: exit codes per the contract (0 on success — a declined
   confirmation and a nothing-to-do delivery included; 1 on error).

### Trace: `render_topic_board` / `render_topic_host_rows` / `render_board_json`

1. **Input**: the entries/records with `divergence`; the measured width;
   the `info` flag.
2. **Step**: the column grid — without `info` unchanged (four-column /
   three-column rules); under `info` the new rules: the default view —
   topic, branch, hosts, todo, base each capped at one sixth of `width`
   minus the dividers, statuses the non-negative remainder, minimum 8
   per column; the audit view — topic, branch, todo, base each capped at
   one fifth, statuses the remainder, minimum 8.
3. **Step**: the header/row order — default: topic, branch, hosts, todo,
   base, statuses; audit: topic, branch, todo, base, statuses; the base
   header is the word `Base`; the cell carries the marker (`behind` /
   `current`) or empty when None; truncation/ellipsis, the current
   asterisk, the row dividers, and the narrow-terminal exception behave
   exactly as the existing columns.
4. **Step** (JSON): every entry shapes into the keys topic, branch,
   hosts, statuses, current, remote, todo, divergence; every record into
   the same without hosts; `divergence` is the string or null — always
   present, never omitted (an additive change to the stable record
   contract).
5. **Output**: the table/JSON on stdout; read-only over the input.

#### Checkpoint Summary
- width-rule arithmetic (sixth/fifth shares, min 8): passed
- divergence-key stability in JSON: passed

---

## Algorithm Design

The git-cell routines are one-invocation wrappers whose algorithms are
fixed by the traces above. This section elaborates the composite entities.

### `resolve_exchange_base`

**Responsibility**: resolve the base as one logical branch — the shared
machinery of update and propagate.

**Algorithm:**
```
1. require_git_version()
2. IF base_ref == own_branch OR base_ref == f"origin/{own_branch}":
   - raise clean error "the topic is its own base"
3. (local, twin) = _base_branch_names(base_ref, list_branch_refs())
   IF local not in inventory AND twin not in inventory:
   - tip = resolve_ref_commit(base_ref)        # tag/hash, no fetch
   - RETURN ExchangeBase(base_ref, tip, None, False)
   IF local == resolve_current_branch_name():
   - raise clean error "switch away first"     # the checked-out base
4. echo f"Fetching origin/{local}..."
   fetch_branch(local)                          # absent remote -> twin stays absent
5. projections = [resolve_ref_commit(x) for x in (local, twin) if x exists]
6. IF len(projections) == 1: effective = projections[0]
   ELIF is_ancestor(local_tip, twin_tip): effective = twin_tip
   ELIF is_ancestor(twin_tip, local_tip): effective = local_tip
   ELSE:                                        # the pair diverged
     IF is_ancestor(local_tip, own_tip) AND is_ancestor(twin_tip, own_tip):
     - effective = own_tip; written = False     # already carried, nothing written
     ELSE:
     - tree = merge_tree(local_tip, twin_tip)
     - IF tree is None: raise clean error "reconcile base '{base_ref}' manually"
     - commit = create_commit_from_tree(tree, [local_tip, twin_tip],
                                         f"Reconcile base '{base_ref}'")
     - point_branch_at_commit(local, commit)
     - effective = commit; written = True
7. RETURN ExchangeBase(base_ref, effective, local if local exists else None, written)
```

**Errors**: git-too-old (`RuntimeError` → clean); self-base; the base's
local branch being the current branch (switch away first); unresolvable
revision; fetch failure (other than twin-absent); reconciliation conflict.

**Edge cases**: remote-only base (`local` missing — projections = the twin
alone, `local_branch=None`); a tag/hash base never fetches; the base pair
converged by one side being the ancestor — no write; the own tip already
carrying both projections — no write at all.

### `resolve_exchange_target`

**Responsibility**: resolve the addressee — the current topic when the
identifier is omitted, the identified one otherwise; refuse remote-only.

**Algorithm:**
```
1. IF identifier is None:
   - current = resolve_current_branch_name(); None -> clean error
   - candidates = resolve_switch_candidates(current, year)
     keep branch == current; empty or topic is None -> clean error naming branch
2. ELSE:
   - candidates = resolve_switch_candidates(identifier, year)
   - none -> clean error with the board hint
   - several -> _choose_candidate(candidates)   # the switching.py numbered
                                                # prompt; clean error w/o a TTY
   - chosen.topic is None -> clean error (a branch without a topic)
3. chosen.remote -> clean error hinting `goga topics switch`
4. RETURN ExchangeTarget(chosen.topic, chosen.branch,
                         chosen.branch == resolve_current_branch_name())
```

**Errors**: no current branch; current branch hosting no topic; no
candidate; several without a terminal; remote-only own branch.

**Edge cases**: the current branch hosting a topic — no prompt, no
inventory ambiguity path; a local+twin pair — the tier collapse already
dropped the twin, so `remote=True` reliably means remote-only.

### `update_topic`

**Responsibility**: bring a topic up to its base under the configured
strategy; no confirmation; publish optional.

**Algorithm:**
```
1. IF strategy is None: effective = "merge"
   ELIF strategy in {merge, rebase, ff-else-merge, ff-else-rebase}: effective = strategy
   ELSE: raise clean config error naming topics.update.strategy
2. target = resolve_exchange_target(identifier, year)
   own_tip = resolve_ref_commit(target.branch)
3. (local, _) = _base_branch_names(base_ref, list_branch_refs())
   rollback_tip = resolve_ref_commit(local) IF local exists ELSE None
   base = resolve_exchange_base(base_ref, target.branch, own_tip)
4. IF is_ancestor(base.tip, own_tip):                          # already current
   - emit_updated(identity, base.name, base.tip, effective, "already-current", False)
   - RETURN result line                                       # publish publishes nothing
5. realized = ("fast-forward"
               IF effective in {ff-else-merge, ff-else-rebase}
               AND is_ancestor(own_tip, base.tip)
               ELSE effective)
6. message = render_commit_template(commit_message or "Update topic '{slug}' from '{base}'",
                                    target.topic, base.name)
7. IF target.current:                                         # the in-place path
   - not is_working_tree_clean() -> clean error + _restore_base
   - pre-flight: merge -> merge_tree(own_tip, base.tip)
                 rebase -> replay_commits(base.tip, own_tip)   # discarded
                 None -> clean error suggesting manual git + _restore_base
   - mutate: merge -> merge_into_current(base.tip, message)
             rebase -> rebase_current_onto(base.tip)
             ff     -> fast_forward_current_branch(base.tip)
   ELSE:                                                      # checkout-free
   - merge -> tree=merge_tree(own_tip, base.tip)
              None  -> clean error suggesting manual git + _restore_base
              commit=create_commit_from_tree(tree, [own_tip, base.tip], message)
              point_branch_at_commit(target.branch, commit)
   - rebase -> tip=replay_commits(base.tip, own_tip)
              None  -> clean error suggesting manual git + _restore_base
              point_branch_at_commit(target.branch, tip)
   - ff     -> point_branch_at_commit(target.branch, base.tip)
8. IF publish:
   - not origin_configured() -> clean error
   - merge/ff -> push_branch(target.branch)
   - rebase   -> twin exists ? push_branch_with_lease(target.branch, own_tip)
                             : push_branch(target.branch)
   - a failed push -> clean error carrying git's reason    # the update stands
9. outcome = {merge: "merged", rebase: "rebased", fast-forward: "fast-forwarded"}
   emit_updated(identity, base.name, base.tip, effective, outcome, publish)
   RETURN f"Updated topic {resolved_year}/{target.topic} from '{base.name}' via {effective} ({outcome})"
```

`_restore_base(base, rollback_tip)`: `if base.reconciled and rollback_tip
is not None: point_branch_at_commit(base.local_branch, rollback_tip)` with
suppressed restore failures.

**Errors**: invalid strategy (configuration); every resolution error; the
dirty tree; the pre-flight conflict; git failures (clean via the module
wrapper); the publish push failure (the update stands).

**Edge cases**: `ff-else-*` with no own work takes the fast-forward; the
rebase lease binds to the pre-rebase own tip with no extra fetch of the
topic twin; a topic without an origin twin publishes with a plain push
after a rebase; the current topic under `merge` when the base is strictly
behind — the real merge still lands (`--no-ff`).

### `resolve_propagation` / `execute_propagation`

**Responsibility**: the two halves of the delivery — a fully read-only
plan the caller confirms, then the checkout-free build-plant-push with one
retry and a uniform rollback.

**Algorithm (resolve):**
```
1. strategy in {merge, ff, squash} else clean config error (topics.propagate.strategy)
2. target = resolve_exchange_target(identifier, year)
3. not origin_configured() -> clean error
4. (local, _) = _base_branch_names(base_ref, list_branch_refs())
   local == resolve_current_branch_name() -> clean error "switch away first"
5. message = render_commit_template(
      commit_message or "Propagate topic '{slug}' into '{base}'", target.topic, base_ref)
6. RETURN PropagationPlan(target, base_ref, strategy, message, resolved_year)
```

**Algorithm (execute):**
```
1. own_tip = resolve_ref_commit(plan.target.branch)
   (local, _) = _base_branch_names(plan.base_ref, list_branch_refs())
   rollback_tip = resolve_ref_commit(local) IF local exists ELSE None
2. base = resolve_exchange_base(plan.base_ref, plan.target.branch, own_tip)
   base.local_branch == resolve_current_branch_name() -> clean error
3. IF is_ancestor(own_tip, base.tip):                          # reachability idempotency
   - emit_propagated(..., "nothing-to-do"); RETURN line        # reconciliation stands
4. base_tree = resolve_commit_tree(base.tip)
   merge/squash: tree = merge_tree(base.tip, own_tip); None -> conflict
                 merge   -> delivery = create_commit_from_tree(tree, [base.tip, own_tip], message)
                 squash  -> delivery = create_commit_from_tree(tree, [base.tip], message)
   ff: not is_ancestor(base.tip, own_tip) -> clean error suggesting manual git (+ rollback)
       delivery = own_tip; delivery_tree = resolve_commit_tree(own_tip)
   IF delivery_tree == base_tree:                              # content idempotency
   - emit_propagated(..., "nothing-to-do"); RETURN line        # nothing planted/pushed
5. plant: local path -> point_branch_at_commit(base.local_branch, delivery)
          remote-only -> nothing planted locally
6. push: local path -> push_branch(base.local_branch)
         write-through -> push_revision_to_branch(delivery, short_name(plan.base_ref))
7. ON push failure WITH the concurrent-movement stderr signature, ONCE:
   - echo f"Fetching origin/{short}..."; fetch_branch(short)
   - re-run the resolution tail (projections/containment/reconciliation)
   - rebuild delivery (step 4 logic, nothing-to-do included); re-plant; re-push
   - a second rejection -> rollback + clean error
8. ON any failure: rollback (point_branch_at_commit(base.local_branch, rollback_tip)
   when both are not None — removes a written reconciliation, a no-op otherwise),
   then the clean error
9. emit_propagated(identity, base.name, plan.strategy, outcome)   # merged|fast-forwarded|squashed
10. RETURN f"Propagated topic {year}/{slug} into '{base.name}' via {strategy} ({outcome})"
```

**Errors**: invalid strategy; no origin; the base is the current branch;
conflict; ff-impossible; a failed push; a failed retry.

**Edge cases**: both nothing-to-do forms emit and return exit-0 lines;
the write-through base (no local branch) plants nothing and pushes the
revision directly; the retry may itself land in nothing-to-do (the moved
remote already carries the topic); the topic's branch and directory are
never touched.

### `resolve_divergence`

**Responsibility**: the board's binary marker — read-only, local refs,
never a failure.

```
1. base_ref None -> None
2. projections: branch-shaped -> {local tip, twin tip} as they exist locally
                (each skipped on a resolution failure);
                tag/hash -> {resolve_ref_commit(base_ref)}
   projections empty -> None
3. RETURN "current" IF every projection satisfies is_ancestor(p, own_tip)
          ELSE "behind"
```

**Edge cases**: a diverged base pair reads as behind (no reconciliation
here — the marker converges only through an update); an unresolvable base
is None, never an error.

### The nested topics configuration

**`config.py`**: `TopicsCreateConfig(commit: str | None = None)`,
`TopicsUpdateConfig(strategy: str | None = None, commit: str | None =
None)`, `TopicsPropagateConfig` identical in shape; `TopicsConfig(
base_ref: str | None = None, create: TopicsCreateConfig | None = None,
update: TopicsUpdateConfig | None = None, propagate:
TopicsPropagateConfig | None = None)` — all `@dataclass(kw_only=True,
frozen=True)` with None defaults (the defaults keep the overlay
materialization factories trivial and match the `ReviewConfig` style; the
old required-field shape is gone with `publish_commit`).

**`loader.py` `_parse_topics`**: keep the existing helper
`_parse_topics_field` (already the right normalization); add a
`_parse_topics_section(raw, name, fields)` helper — absent/YAML-null →
None; a non-mapping → `ValueError("'topics.<name>' must be a mapping in
.goga/config.yml")`; inside, each named field through
`_parse_topics_field` with the dotted key (`topics.update.strategy`,
`topics.update.commit`, `topics.create.commit`,
`topics.propagate.strategy`, `topics.propagate.commit`); unknown keys
(including the retired `publish_commit`) are never read — silence by
construction, not by a skip-list.

**`overlay.py`**: `_CONFIG_TREE["TopicsConfig"]` becomes
`{"base_ref": _scalar(str), "create": _section("TopicsCreateConfig"),
"update": _section("TopicsUpdateConfig"), "propagate":
_section("TopicsPropagateConfig")}` plus the three per-model nodes
(`commit`/`strategy` scalars); `_SECTION_DEFAULTS` grows
`"TopicsCreateConfig": TopicsCreateConfig`, `"TopicsUpdateConfig":
TopicsUpdateConfig`, `"TopicsPropagateConfig": TopicsPropagateConfig`,
and the `TopicsConfig` lambda collapses to `TopicsConfig` (all-defaults
shape). The `dataclasses.fields` cross-check tests extend to the three
new models so tree drift stays detectable.

**`goga/config/__init__.py`**: import and `__all__`-export the three new
models beside `TopicsConfig` (the facade contract: +3 embedding
re-exports → 17 total).

### The hooks additions

`contexts.py`: two frozen kw_only dataclasses `TopicUpdated(identity,
base, effective_tip, strategy, outcome, published)` and
`TopicPropagated(identity, base, strategy, outcome)` in the file's
documented style; the module docstring's “five read-only fact bags”
becomes seven. `events.py`: `emit_updated` / `emit_propagated` in the
exact idiom of `emit_switched` (context build → `emit_hook_event(
_run_registry(), "topics", <action>, context_for=...)`); the class and
module docstrings' emission counts update five→seven. `__init__.py`:
export the two contexts. `catalog.py`: the two soft records (see the
trace).

### The CLI additions

`topics.py`: `update` — `@topics.command("update")`, `IDENTIFIER`
optional positional, `--base-ref`, `--publish/-p`; `propagate` —
`@topics.command("propagate")`, `IDENTIFIER` optional, `--base-ref`,
`--yes/-y`; both `@click.pass_obj` with the shared `_TopicsScope`, both
echo the domain line and `ctx.exit(0)`; the strategy/template resolution
reads `section.update` / `section.propagate` with the None-guard per
sub-section; the `create` template rung becomes `section.create.commit`
(and the `--commit` help text names `topics.create.commit`); the `board`
first step loads the configuration and passes `base_ref` (see the trace);
the group docstring's subcommand list and the module docstring grow the
two subcommands; the `--info` help text names the todo and base columns.

`render.py`: the two table renderers grow the Base column and the
sixth/fifth share rules; `render_board_json` adds the `divergence` key.

---

## Cross-cutting Concerns

- **Error handling**: the domain's clean-error boundary is unchanged —
  `subprocess.CalledProcessError` (stderr detail or `str(exc)`),
  `FileNotFoundError` (git missing), `OSError`, and the fatal
  `ImportError` of the hooks-registry assembly surface as
  `click.ClickException` at the public entry points
  (`update_topic`, `resolve_propagation`, `execute_propagation` wrap
  their `_`-prefixed cores exactly like `board.py`/`publishing.py`). The
  new gate error joins them: `require_git_version` raises `RuntimeError`,
  and the three new wrappers catch `RuntimeError` with it. The
  overlay raises its pinned `ValueError` format; the loader its
  `ValueError`s; both fold into the CLI's existing clean-error wrapper.
  The git cell itself stays raw-propagating — the wrap belongs to the
  domain. Rollback restores suppress their own failures so the original
  reason surfaces.
- **Logging**: none added — the topics domain logs nothing today; hooks
  failures warn through the platform's existing warning channel (the
  soft error class), and progress is user-facing stdout only (the single
  `Fetching origin/<base>...` line per fetch, echoed by the domain — the
  git cell stays silent).
- **Validation**: strategy whitelists live in the domain
  (`update_topic`, `resolve_propagation`) and fire **before anything
  else**, naming the configuration key; the loader does structural
  typing only; the CLI passes values through verbatim (no validation at
  the CLI layer). Template grammar is never validated — unknown
  placeholders stay verbatim.
- **Caching**: none. Each operation reads the inventory fresh
  (`list_branch_refs` per routine that needs it — the resolution and its
  callers each enumerate once); the shared run `HookRegistry` remains
  the only process-level cache (one `build_once` per run).
- **Concurrency**: single-threaded CLI flows, unchanged. The
  force-with-lease push and the retry cycle are the designed answers to
  concurrent remote movement — no locking is introduced; the
  point-plant-ref atomicity (objects dangle until one ref update) keeps
  checkout-free paths safe against interruption.

---

## Usages Analysis

### `convention` (project-level, every changed cell)
- **What it provides**: the codebase rules — docstring style, the REPL
  cycle, the test infrastructure (mocking at the import point), relative
  imports.
- **Where used**: every new module of the five implementation cells.
- **Why chosen**: the standing project practice.
- **How exactly**: docstrings carry the Purpose/Algorithm/Requirements/
  Constraints/Raises structure of the neighboring routines; `from .x
  import y` intra-package; tests mock `subprocess.run` at the module
  import point.

### `click` (project-level cook, `goga/topics` + `goga/commands/topics`)
- **What it provides**: group/command/option/argument decorators, echo,
  `click.confirm`, `click.prompt` with `IntRange`, the clean error
  channel (`click.ClickException`), exit-code propagation.
- **Where used**: `resolve_exchange_target` (the numbered selection),
  `topics.update`, `topics.propagate` (the confirmation, the
  non-interactive detection), the renderers' echo.
- **Why chosen**: the interactive moments and the error surface of the
  CLI belong to the established practice.
- **How exactly**: the confirmation mirrors `delete`/`clear`
  (`sys.stdin.isatty()` guard → `click.confirm`; decline → `ctx.exit(0)`);
  the selection mirrors `switching.py`'s `_choose_candidate`.

### `git` (inline, `goga/topics/git`)
- **What it provides**: the invocation pattern (`subprocess.run`,
  `check=True`, captured output, `GIT_TERMINAL_PROMPT=0`, UTF-8 with
  replacement) — now extended with the checkout-free exchange patterns:
  `merge-tree --write-tree`, `commit-tree` over parents, the plumbing
  replay, the single-ref plant, `merge-base --is-ancestor`, the
  commit→tree peel, the lease
  push, the targeted fetch, the real merge/rebase/ff, the version gate.
- **Where used**: `exchange.py` (new), `switch.py`, `publish.py`.
- **Why chosen**: the cell's single git channel — no new library.
- **How exactly**: `exchange.py` carries its own `_run_git` mirroring
  `publish.py`'s (DEVNULL stdin, `input=` support for future needs,
  errors=replace); `switch.py`'s three additions reuse its existing
  `_run_git`; `publish.py`'s three reuse its own (full-ref refspecs,
  `--no-follow-tags`).

### `exchanging` (cell-level, `goga/topics/git/.usages/exchanging.md`)
- **What it provides**: the consumer patterns of the checkout-free
  exchange — gate, containment, tree identity, pre-flight + build +
  plant, replay, in-place moves, the network set.
- **Where used**: `goga/topics` — `resolve_exchange_base`,
  `update_topic`, `execute_propagation`, `resolve_divergence`.
- **Why chosen**: the bridge practice between the git cell and the
  domain (imported via `Imports.Usages` — a tracked, non-contractual
  link).
- **How exactly**: the traced call sequences follow its code blocks
  verbatim (plant last; the lease binds to the pre-replay tip; report
  each fetch with one stdout line before it runs).

### `refs-and-switching`, `publishing`, `deleting` (cell-level, `goga/topics/git`)
- **What it provides / How**: the inventory and revision-resolution
  patterns (`_base_branch_names` builds on the inventory reading), the
  quarantined commit + plant + push + rollback patterns reused by the
  exchange, and the symmetric removal patterns (unchanged by this
  topic). Used by `resolve_exchange_base`, `update_topic` (the publish
  push), `execute_propagation` (the pushes), `resolve_divergence`.

### `checkpoints` (cell-level, `goga/topics/hooks/.usages/checkpoints.md`)
- **What it provides**: the emission contract — fire-and-forget under
  the soft class, facts from the operation's own data; now the seven
  emissions with `topic_updated` / `topic_propagated` contexts.
- **Where used**: `emit_updated`, `emit_propagated`; the two operations'
  emission steps.
- **How exactly**: the contexts and the addresses exactly as the
  practice's table states (no pushed flag on the propagate context).

### `update`, `propagate` (cell-level, `goga/topics/.usages/{update,propagate}.md`)
- **What it provides**: the consumer contracts of the two operations —
  inputs, defaults, strategies, idempotency, atomicity, the inherent
  push.
- **Where used**: `goga/commands/topics` — the two subcommands.
- **How exactly**: the CLI maps flags to the documented inputs and adds
  exactly one confirmation on propagate (naming the target and the push)
  with the `--yes` escape.

### `project-configuration` (cell-level, `goga/config/.usages/project-configuration.md`)
- **What it provides**: the nested topics schema, the silent retirement
  of `publish_commit`, the migration note.
- **Where used**: the CLI's `_topics_section` consumers (`create`,
  `clear`, `board`, `update`, `propagate`).
- **How exactly**: read `topics.base_ref`, `topics.create.commit`,
  `topics.update.{strategy,commit}`, `topics.propagate.{strategy,commit}`
  with the per-sub-section None-guard.

### `beautiful_json` (project-level cook, `goga/commands/topics`)
- **What it provides**: the pretty-printed, sorted-keys JSON serialization.
- **Where used**: `render_board_json` — now with the `divergence` key.

### Imported usages traced
- `exchanging` from `goga/topics/git` — path
  `goga/topics/git/.usages/exchanging.md` (exists).
- `update` / `propagate` from `goga/topics` — paths
  `goga/topics/.usages/update.md`, `goga/topics/.usages/propagate.md`
  (exist).
- `checkpoints` from `goga/topics/hooks` — path
  `goga/topics/hooks/.usages/checkpoints.md` (exists, updated).
- `project-configuration` from `goga/config` — path
  `goga/config/.usages/project-configuration.md` (exists, updated).

---

## `.usages/` Update

Verified in this design pass — the files were created/updated by the
apply stage and re-checked against the CODEMANIFEST here; **no further
changes are required**:

### Cell: `goga/topics/git`
- **`exchanging.md`** — new file; covers the gate, containment,
  tree identity, pre-flight/build/plant, replay, in-place moves, the
  network set.
  Status: current (matches the 13 new signatures verbatim).

### Cell: `goga/topics`
- **`update.md`** — new file; the update contract. Status: current.
- **`propagate.md`** — new file; the propagation contract. Status:
  current (the uniform rollback including the ff error matches the
  fixed CODEMANIFEST).
- **`topic-board.md`** — updated with `base_ref` and the divergence
  marker. Status: current.
- **`creating.md` / `publishing.md`** — updated with the template
  engine and the new default. Status: current.
- **`registering-hooks.md`** — updated: nine soft actions, seven
  notifications, the two new context rows, the no-pushed-flag note.
  Status: current.

### Cell: `goga/topics/hooks`
- **`checkpoints.md`** — updated: seven emissions, the two new examples
  and context bullets. Status: current.

### Cell: `goga/commands/topics`
- **`topics-command.md`** — updated: the two new sections, the Base
  column, the `divergence` JSON key, the create template key. Status:
  current.

### Cell: `goga/config`
- **`project-configuration.md`** — updated: the nested schema, the
  field table, the migration note, the accessor block. Status: current.

**Rule applied**: no CODEMANIFEST `Usages` reference points at any own
`.usages/` file — they stay consumer documentation only.

---

## Test Stack Trace

### General Setup

- The git cell is tested by mocking `subprocess.run` **at the import
  point** (`mock.patch("goga.topics.git.exchange.subprocess.run", ...)`)
  per the `convention` practice — no git binary, no repository. The mock
  answers with `subprocess.CompletedProcess(args=["git"], returncode=0,
  stdout=..., stderr=...)`; a side-effect function inspects argv and
  answers per invocation, so multi-step chains (`rev-list` → per-commit
  reads → `commit-tree`) are scripted.
- The domain modules are tested by mocking the imported git-cell names
  at the domain module's import point (e.g.
  `mock.patch("goga.topics.updating.resolve_exchange_base")`) plus the
  hooks facade — the existing `tests/topics` style.
- `resolve_divergence` failure-tolerance tests mock
  `resolve_ref_commit` to raise `subprocess.CalledProcessError`.
- Loader tests feed inline YAML through `load_project_config` inside a
  `tmp_path` `.goga/config.yml` (the existing `tests/config` style).
- Constants used below: `BASE = "main"`, `TWIN = "origin/main"`,
  `LOCAL_TIP = "aa1"`, `TWIN_TIP = "bb2"`, `OWN = "cc3"`,
  `RECON = "dd4"`, `TREE = "tree-oid-1"`, slug `feat-x`, year `2026`.

### Source File Registry

- `goga/config/project/config.py`, `goga/config/project/loader.py`,
  `goga/config/__init__.py`, `goga/config/hooks/overlay.py`
- `goga/hooks/catalog/catalog.py`
- `goga/topics/git/exchange.py`, `goga/topics/git/switch.py`,
  `goga/topics/git/publish.py`, `goga/topics/git/__init__.py`
- `goga/topics/hooks/contexts.py`, `goga/topics/hooks/events.py`
- `goga/topics/exchange.py`, `goga/topics/updating.py`,
  `goga/topics/propagating.py`, `goga/topics/board.py`,
  `goga/topics/creation.py`, `goga/topics/publishing.py`,
  `goga/topics/__init__.py`
- `goga/commands/topics/topics.py`, `goga/commands/topics/render.py`
- Test homes: `tests/config/test_loader.py`,
  `tests/config/hooks/` (overlay), `tests/hooks/catalog/test_catalog.py`,
  `tests/topics/git/test_exchange.py`, `tests/topics/git/test_switch.py`,
  `tests/topics/git/test_publish.py`, `tests/topics/hooks/test_contexts.py`,
  `tests/topics/hooks/test_events.py`, `tests/topics/test_exchange.py`
  (new), `tests/topics/test_updating.py` (new),
  `tests/topics/test_propagating.py` (new), `tests/topics/test_board.py`,
  `tests/commands/topics/test_topics.py`, `tests/commands/topics/test_render.py`.

---

### Positive Tests

#### `test_require_git_version_passes_modern_git`

**Setup**: none (no repository needed — `git version` works anywhere).
**Input**: stdout `git version 2.43.0 (Apple Git-151)\n`.
**Trace**:
```
require_git_version()
  → _run_git(["git", "version"])           # returns stdout above
  → parse (2, 43)                          # >= (2, 38)
  → return None
```
**Assertions**: returns None; exactly one invocation; argv == `["git",
"version"]`.
**Sufficiency**: pins the gate's floor arithmetic and the read-only
single-invocation shape; prevents a silent no-op gate.

#### `test_require_git_version_rejects_old_git`

**Setup**: none.
**Input**: stdout `git version 2.35.1\n`.
**Trace**:
```
require_git_version()
  → parse (2, 35) < (2, 38)
  → raise RuntimeError("goga needs git >= 2.38 ... (found 2.35.1)")
```
**Assertions**: `pytest.raises(RuntimeError)` whose message contains both
`2.38` and `2.35.1`.
**Sufficiency**: the version floor is the exchange's hard dependency;
the error must name required and present versions for a actionable
clean error.

#### `test_is_ancestor_maps_exit_codes`

**Setup**: a run fake answering returncode 0 / 1 / 128 in three cases.
**Input**: `("aa1", "cc3")` under each returncode.
**Trace**:
```
is_ancestor("aa1", "cc3")
  → subprocess.run(["git", "merge-base", "--is-ancestor", "aa1", "cc3"], check=False)
  → rc 0 -> True ; rc 1 -> False ; rc 128 -> CalledProcessError
```
**Assertions**: True / False / raises respectively; `check=False` in the
call kwargs (never `check=True`).
**Sufficiency**: the rc-1-is-a-answer distinction is the routine's whole
point — `check=True` would turn every “no” into an infrastructure error
and break every caller's branching.

#### `test_resolve_commit_tree_peels_to_tree`

**Setup**: run fake answering stdout `"tree-oid-1\n"`.
**Input**: `("cc3",)`.
**Trace**:
```
resolve_commit_tree("cc3")
  → ["git", "rev-parse", "--verify", "cc3^{tree}"]
  → returns "tree-oid-1"
```
**Assertions**: the argv above (the `^{tree}` peel verbatim); exactly one
invocation; return `"tree-oid-1"`.
**Sufficiency**: the tree oid is the content identity of the
content-based nothing-to-do check — a missing peel (a bare
`rev-parse cc3`) would compare commits, not content, and break the
squash-already-landed idempotency.

#### `test_merge_tree_clean_and_conflict`

**Setup**: run fake answering rc 0 stdout `"tree-oid-1\n\n"` and rc 1.
**Input**: `("cc3", "aa1")` twice, then `("cc3", "aa1", "bb2")` (explicit
base).
**Trace**:
```
merge_tree("cc3", "aa1")
  → ["git", "merge-tree", "--write-tree", "cc3", "aa1"]  # rc 0
  → returns "tree-oid-1"
merge_tree (rc 1) → returns None
merge_tree("cc3", "aa1", "bb2")
  → argv contains "--merge-base=bb2"                      # rc 0
  → returns "tree-oid-1"
```
**Assertions**: the three returns; the first stdout line only; exactly
one invocation per call.
**Sufficiency**: conflict-as-None is the contract's signal channel; the
`--merge-base` flag's spelling and placement drive every replay step.

#### `test_create_commit_from_tree_argv_order`

**Setup**: run fake answering stdout `"ee5\n"`.
**Input**: `("tree-oid-1", ["cc3", "aa1"], "Update topic 'feat-x'")`.
**Trace**:
```
create_commit_from_tree(tree, parents, message)
  → ["git", "commit-tree", "tree-oid-1", "-p", "cc3", "-p", "aa1", "-m", "Update topic 'feat-x'"]
  → stdin is DEVNULL (run called with no input)
  → returns "ee5"
```
**Assertions**: argv as above; `stdin=subprocess.DEVNULL` in the run
kwargs; return `"ee5"`.
**Sufficiency**: parent order is the merge's history record; the DEVNULL
stdin guards the documented `commit-tree -m` hang.

#### `test_replay_commits_preserves_author_and_message`

**Setup**: run fake scripted per argv: `rev-list --reverse cc3 ^aa1` →
`"c1 c0\n"` (with `--parents`: `"c1 c0\n"`), `show -s --format=... c1`
→ `"Ann<a1f>ann@x.io<a1f>2026-01-02T03:04:05+00:00<a1f>Do the thing\n"`,
`merge-tree` (base `c0`) → tree, `commit-tree` → `"f1\n"`.
**Input**: `("aa1", "cc3")`.
**Trace**:
```
replay_commits("aa1", "cc3")
  → rev-list --reverse cc3 ^aa1            → [c1]
  → read c1 author+message (%an,%ae,%aI,%B via %x1f framing)
  → merge_tree(ours=aa1, theirs=c1, merge_base=c0) → tree
  → commit-tree tree -p aa1 -m "Do the thing"
      env: GIT_AUTHOR_NAME="Ann", GIT_AUTHOR_EMAIL="ann@x.io",
           GIT_AUTHOR_DATE="2026-01-02T03:04:05+00:00"
  → returns "f1"
```
**Assertions**: return `"f1"`; the `commit-tree` invocation's env
carries the three `GIT_AUTHOR_*` values verbatim; the message argument
is `"Do the thing"`; `rev-list` argv ends with `["cc3", "^aa1"]` and
includes `--reverse`.
**Sufficiency**: author/message preservation is a contract Requirement —
a plumbing rebase that reauthors commits silently rewrites history.

#### `test_replay_commits_two_commit_chain_chains_running_result`

**Setup**: run fake scripted per argv — `rev-list --reverse cc3 ^aa1`
→ `"c1 c0\nc2 c1\n"` (oldest first); the per-commit author/message
reads; the two `merge-tree` calls answer `tree1` / `tree2`; the two
`commit-tree` calls answer `"f1\n"` / `"f2\n"`.
**Input**: `("aa1", "cc3")`.
**Trace**:
```
replay_commits("aa1", "cc3")
  → rev-list → [c1 (parent c0), c2 (parent c1)]
  → c1: merge_tree(ours=aa1, theirs=c1, merge_base=c0) → tree1
       commit-tree tree1 -p aa1 → f1
  → c2: merge_tree(ours=f1, theirs=c2, merge_base=c1) → tree2
       commit-tree tree2 -p f1 → f2
```
**Assertions**: return `"f2"`; the second `merge-tree` invocation
received `ours=f1` and `--merge-base=c1` — the running result and each
step's own parent, never `aa1`/`c0` again.
**Sufficiency**: a one-commit replay cannot distinguish a chained
replay from a lone cherry-pick; an accumulation bug (replaying every
step onto the fixed base) would silently flatten the topic's history.

#### `test_replay_commits_conflict_returns_none`

**Setup**: the scripted `merge-tree` answers rc 1.
**Input**: `("aa1", "cc3")`.
**Trace**: rev-list yields one commit → `merge_tree` → None → return
None; **no** `commit-tree` invocation.
**Assertions**: returns None; no commit-tree in the recorded argv.
**Sufficiency**: the None signal (not an error) drives the callers'
conflict branches; an exception here would bypass their read-only
pre-flight design.

#### `test_point_branch_at_commit_single_ref_update`

**Setup**: run fake answering rc 0.
**Input**: `("main", "ee5")`.
**Trace**: `["git", "update-ref", "refs/heads/main", "ee5"]` → None.
**Assertions**: the argv above; exactly one invocation.
**Sufficiency**: the single-ref planting is the atomicity primitive of
every exchange — extra invocations would break the “single mutation”
invariant.

#### `test_merge_into_current_never_fast_forwards`

**Setup**: run fake answering rc 0.
**Input**: `("aa1", "Update topic 'feat-x'")`.
**Trace**:
```
merge_into_current("aa1", msg)
  → ["git", "merge", "--no-ff", "--no-edit", "-m", msg, "aa1"]
```
**Assertions**: argv contains both `--no-ff` and `--no-edit` before the
revision.
**Sufficiency**: a missing `--no-ff` silently turns configured merges
into fast-forwards and changes the outcome kind reported to hooks.

#### `test_rebase_current_onto_uses_rebase`

**Setup**: run fake answering rc 0.
**Input**: `("aa1",)`.
**Trace**: `["git", "rebase", "aa1"]` → None.
**Assertions**: the argv exactly; no other flags (no `--onto` forms, no
autostash); exactly one invocation.
**Sufficiency**: the in-place rebase must be the plain `git rebase` —
extra flags would change the working-copy semantics the pre-flight
validated.

#### `test_fast_forward_current_branch_uses_ff_only`

**Setup**: run fake answering rc 0.
**Input**: `("aa1",)`.
**Trace**: `["git", "merge", "--ff-only", "aa1"]`.
**Assertions**: the argv exactly; no other flags.
**Sufficiency**: the no-fallback constraint — a plain merge here would
author commits the contract forbids.

#### `test_fetch_branch_updates_single_tracking_ref`

**Setup**: run fake answering rc 0.
**Input**: `("main",)`.
**Trace**: `["git", "fetch", "origin", "+refs/heads/main:refs/remotes/origin/main"]`.
**Assertions**: the argv above; nothing printed (no echo in the cell).
**Sufficiency**: the forced single-branch refspec is the “exactly one
branch” guarantee; a bare `git fetch origin main` could widen under
configuration.

#### `test_fetch_branch_absent_remote_is_silence`

**Setup**: run fake raising `CalledProcessError(1, cmd)` with stderr
`"fatal: couldn't find remote ref refs/heads/main\n"`.
**Input**: `("main",)`.
**Trace**: the fetch fails → stderr matched → return None (no raise).
**Assertions**: returns None; no exception.
**Sufficiency**: the twin-absent case is the remote-only-base enabling
path — raising here would break every brand-new remote base.

#### `test_fetch_branch_other_failure_raises`

**Setup**: stderr `"fatal: unable to access 'origin': network\n"`.
**Input**: `("main",)`.
**Trace**: the fetch fails → no match → the CalledProcessError
propagates raw.
**Assertions**: `pytest.raises(subprocess.CalledProcessError)`.
**Sufficiency**: a network outage must not read as twin-absent — that
would silently resolve bases to stale local projections.

#### `test_push_branch_with_lease_binds_expected_tip`

**Setup**: run fake answering rc 0.
**Input**: `("feat-x", "cc3")`.
**Trace**:
```
push_branch_with_lease("feat-x", "cc3")
  → ["git", "push", "--no-follow-tags",
     "--force-with-lease=refs/heads/feat-x:cc3", "origin",
     "refs/heads/feat-x:refs/heads/feat-x"]
```
**Assertions**: the argv above (full-ref lease and full refspec).
**Sufficiency**: the lease value is the rebase's safety net — a short
form or a stale lease would let the push overwrite concurrent remote
work.

#### `test_push_revision_to_branch_writes_through`

**Input**: `("ee5", "main")`.
**Trace**: `["git", "push", "--no-follow-tags", "origin",
"ee5:refs/heads/main"]`.
**Assertions**: the argv; no `-u`, no force flags.
**Sufficiency**: the write-through must never bind upstream or force —
it creates-or-updates exactly one remote branch.

#### `test_loader_parses_nested_topics_section`

**Setup**: `tmp_path` `.goga/config.yml`:
```yaml
language: python
topics:
  base_ref: origin/main
  create:
    commit: "Create topic '{slug}'"
  update:
    strategy: rebase
    commit: "Update topic '{slug}' from '{base}'"
  propagate:
    strategy: squash
    commit: "Propagate topic '{slug}' into '{base}'"
```
**Input**: `load_project_config()`.
**Trace**:
```
load_project_config()
  → _parse_topics(data) → raw mapping
  → base_ref "origin/main"; create/update/propagate sub-mappings parsed
  → ProjectConfig(topics=TopicsConfig(base_ref="origin/main",
      create=TopicsCreateConfig(commit="Create topic '{slug}'"),
      update=TopicsUpdateConfig(strategy="rebase", commit=...),
      propagate=TopicsPropagateConfig(strategy="squash", commit=...)))
```
**Assertions**: `config.topics.base_ref == "origin/main"`;
`config.topics.create.commit == "Create topic '{slug}'"`;
`config.topics.update.strategy == "rebase"`;
`config.topics.propagate.strategy == "squash"`; every model `frozen` and
`kw_only` (dataclass import checks).
**Sufficiency**: the nested shape is the configuration contract of both
new commands; a flat mis-parse would silently strand every knob at None.

#### `test_loader_retires_publish_commit_silently`

**Setup**: yaml with `topics: {base_ref: main, publish_commit: "old"}`
plus valid nested sections.
**Input**: `load_project_config()`.
**Trace**: `_parse_topics` reads only `base_ref` and the three
sub-mappings — `publish_commit` is never `get`-ed.
**Assertions**: no warning (capsys empty); `config.topics` has no
`publish_commit` attribute (`pytest.raises(AttributeError)`).
**Sufficiency**: the retirement is contractual (no warning, no effect);
an accidental deprecation warning would spam every legacy repository.

#### `test_render_commit_template_placeholders`

**Input**: `("Do {what} for {slug} from {base}", "feat-x", "main")`.
**Trace**: `.replace("{slug}", "feat-x").replace("{base}", "main")`.
**Assertions**: result == `"Do {what} for feat-x from main"`.
**Sufficiency**: unknown placeholders verbatim is the single-engine rule;
a `str.format` implementation would raise on `{what}`.

#### `test_resolve_exchange_base_reconciliation_flow`

**Setup**: mocked at `goga.topics.exchange`: `list_branch_refs` →
`[BranchRef("main", False), BranchRef("origin/main", True)]`;
`resolve_ref_commit` → `{"main": LOCAL_TIP, "origin/main": TWIN_TIP}`;
`is_ancestor` → False everywhere; `merge_tree` → `TREE`;
`create_commit_from_tree` → `RECON`; `point_branch_at_commit`,
`fetch_branch`, `require_git_version` → no-ops; echo captured.
**Input**: `resolve_exchange_base("main", "feat-x", OWN)`.
**Trace**:
```
require_git_version()                    # gate fired once
_base_branch_names → ("main", "origin/main")   # branch-shaped
echo "Fetching origin/main..." ; fetch_branch("main")
projections LOCAL_TIP, TWIN_TIP ; no containment either way
own carries neither projection          # not already-carried
merge_tree(LOCAL_TIP, TWIN_TIP) → TREE  # no conflict
create_commit_from_tree(TREE, [LOCAL_TIP, TWIN_TIP], "Reconcile base 'main'")
point_branch_at_commit("main", RECON)
→ ExchangeBase("main", RECON, "main", True)
```
**Assertions**: the returned `ExchangeBase` tuple as above; the
reconciliation message exactly `Reconcile base 'main'`; the echo line
`Fetching origin/main...` printed before `fetch_branch` was called
(order via a `mock.Mock` attached helper or call order list); exactly
one `fetch_branch` call.
**Sufficiency**: the reconciliation is the exchange's one sanctioned
write onto a foreign branch — wrong message, wrong parents, or a second
fetch all break the audit trail and the fetch contract.

#### `test_resolve_exchange_base_already_carried_writes_nothing`

**Setup**: as above but `is_ancestor(LOCAL_TIP, OWN)` and
`is_ancestor(TWIN_TIP, OWN)` → True.
**Input**: `resolve_exchange_base("main", "feat-x", OWN)`.
**Trace**: diverged pair → own carries both → effective tip = OWN, no
`merge_tree`, no `point_branch_at_commit`.
**Assertions**: `base.tip == OWN`, `base.reconciled is False`;
`merge_tree` not called; `point_branch_at_commit` not called.
**Sufficiency**: the already-carried check preceding the write is a
contract Requirement — an up-to-date topic must mutate nothing at all.

#### `test_resolve_exchange_base_tag_base_never_fetches`

**Setup**: `list_branch_refs` → `[]`; `resolve_ref_commit("v2.0")` →
`"tagcommit"`.
**Input**: `resolve_exchange_base("v2.0", "feat-x", OWN)`.
**Trace**: not branch-shaped → resolve → return
`ExchangeBase("v2.0", "tagcommit", None, False)`.
**Assertions**: `fetch_branch` not called; no echo.
**Sufficiency**: the no-fetch guarantee of tag/hash bases — an extra
network hop would violate the sanctioned network set.

#### `test_resolve_exchange_base_rejects_self_base`

**Input**: `resolve_exchange_base("feat-x", "feat-x", OWN)` and
`resolve_exchange_base("origin/feat-x", "feat-x", OWN)`.
**Assertions**: both raise `click.ClickException` naming the topic as
its own base; `list_branch_refs` never consulted for the pair (the
guard precedes).
**Sufficiency**: a self-base update would reconcile a branch with its
own twin — nonsense that must fail before any fetch.

#### `test_resolve_exchange_base_rejects_checked_out_base`

**Setup**: mocked at `goga.topics.exchange`: `list_branch_refs` →
`[BranchRef("main", False), BranchRef("origin/main", True)]`;
`resolve_current_branch_name` → `"main"`; `fetch_branch`,
`merge_tree`, `point_branch_at_commit` captured.
**Input**: `resolve_exchange_base("main", "feat-x", OWN)` (and the
`"origin/main"` form).
**Trace**: branch-shaped, local `main` == current → clean error asking
to switch away first — before the fetch.
**Assertions**: `click.ClickException` mentioning switching away;
`fetch_branch` not called; `merge_tree` and `point_branch_at_commit`
not called; a detached HEAD (`resolve_current_branch_name` → None)
passes to the fetch.
**Sufficiency**: the reconciliation writes onto the local base branch
via plumbing that bypasses git's own current-branch protection —
without the guard, a checkout-free update while sitting on the base
leaves HEAD pointing past the files on disk (a phantom-dirty working
copy).

#### `test_update_topic_checkout_free_merge_plants_two_parent_commit`

**Setup**: mocked at `goga.topics.updating`: target
`ExchangeTarget("feat-x", "feat-x", False)`; `resolve_ref_commit` →
OWN; inventory without a local `main` but with `origin/main`;
`resolve_exchange_base` → `ExchangeBase("main", BASE_TIP, None, False)`;
`is_ancestor(BASE_TIP, OWN)` → False (not already current), and for the
ff decision False; `merge_tree(OWN, BASE_TIP)` → TREE;
`create_commit_from_tree` → NEW; hooks captured.
**Input**: `update_topic(None, "main", None, None, publish=False,
year="2026")`.
**Trace**:
```
strategy None → effective "merge"                    # whitelist first
target → feat-x/feat-x, own tip OWN
rollback capture: no local main → rollback_tip None
base resolved (mocked)
not already-current ; realized "merge"
message = render of default → "Update topic 'feat-x' from 'main'"
not current → checkout-free: merge_tree(OWN, BASE_TIP) → TREE
create_commit_from_tree(TREE, [OWN, BASE_TIP], message) → NEW
point_branch_at_commit("feat-x", NEW)
publish False → no push
emit_updated(identity, "main", BASE_TIP, "merge", "merged", False)
return "Updated topic 2026/feat-x from 'main' via merge (merged)"
```
**Assertions**: the parent order `[OWN, BASE_TIP]`; the message; the
planted branch; the emitted facts; the result line exactly; `push_branch`
not called.
**Sufficiency**: the checkout-free merge is the default path of the
whole feature — parents, message, plant, and emission facts in one
regression net.

#### `test_update_topic_already_current_is_idempotent`

**Setup**: as above with `is_ancestor(BASE_TIP, OWN)` → True; publish
True.
**Trace**: already-current → emit
`(outcome="already-current", published=False)` → return the line; no
mutation, no push.
**Assertions**: no `merge_tree`/`point_branch_at_commit`/`push_branch`;
the emitted `published` is False despite the flag; exit path returns a
line naming `already-current`.
**Sufficiency**: the idempotency contract — `publish` publishes nothing
in this case, and hooks still observe the moment.

#### `test_update_topic_invalid_strategy_is_config_error`

**Input**: `update_topic(None, "main", "squash", None)`.
**Trace**: whitelist check fails first → `click.ClickException` naming
`topics.update.strategy`; the target is never resolved.
**Assertions**: the exception message contains `topics.update.strategy`
and `squash`; `resolve_exchange_target` not called.
**Sufficiency**: the whitelist ordering (before anything else) and the
key naming are contract-fixed; a late failure would leave fetches and
reconciliations behind.

#### `test_update_topic_rebase_publish_uses_lease_against_pre_rebase_tip`

**Setup**: target not current; `resolve_exchange_base` →
`ExchangeBase("main", BASE_TIP, None, False)`; inventory carries
`origin/feat-x`; `replay_commits(BASE_TIP, OWN)` → REPLAYED;
`push_branch_with_lease` captured.
**Input**: `update_topic("feat-x", "main", "rebase", None, publish=True)`.
**Trace**: the checkout-free rebase — `replay_commits(BASE_TIP, OWN)`
is the build itself (this path runs no separate pre-flight; the build
is read-only until the plant) → REPLAYED → `point_branch_at_commit(
"feat-x", REPLAYED)` → twin exists → `push_branch_with_lease("feat-x",
OWN)`.
**Assertions**: the lease tip is exactly `OWN` (the pre-rebase own tip,
not REPLAYED); `push_branch` not called; `replay_commits` called
exactly once; the emitted outcome
`"rebased"`, strategy `"rebase"`, published True.
**Sufficiency**: binding the lease to the post-rebase tip would defeat
the protection entirely — this is the safety core of the rebase path.

#### `test_update_topic_preflight_conflict_rolls_back_reconciliation`

**Setup**: `resolve_exchange_base` → `ExchangeBase("main", RECON, "main",
True)`; local `main` in inventory → `rollback_tip = LOCAL_TIP`;
`merge_tree(OWN, RECON)` → None; `point_branch_at_commit` captured.
**Input**: `update_topic("feat-x", "main", "merge", None)`.
**Trace**: pre-flight conflict → clean error suggesting manual git →
`_restore_base` → `point_branch_at_commit("main", LOCAL_TIP)`.
**Assertions**: `click.ClickException` raised; the restore call
`(“main”, LOCAL_TIP)` happened after the failed pre-flight.
**Sufficiency**: the pre-operation-state guarantee — without the
restore, a failed update leaves a moved base branch behind (the exact
defect class the CODEMANIFEST Requirement names).

#### `test_update_topic_checkout_free_conflict_rolls_back_reconciliation`

**Setup**: mocked at `goga.topics.updating`: target
`ExchangeTarget("feat-x", "feat-x", False)` (another topic — the
checkout-free path); `resolve_ref_commit` → OWN; `resolve_exchange_base`
→ `ExchangeBase("main", RECON, "main", True)` with local `main` in the
inventory → `rollback_tip = LOCAL_TIP`; `is_ancestor(BASE_TIP, OWN)` →
False; `merge_tree(OWN, RECON)` → None (the build conflict);
`point_branch_at_commit` captured.
**Input**: `update_topic("feat-x", "main", "merge", None)`.
**Trace**: not current → the checkout-free build → `merge_tree` → None
→ clean error suggesting manual git → `_restore_base` →
`point_branch_at_commit("main", LOCAL_TIP)`; nothing planted on
`feat-x`.
**Assertions**: `click.ClickException` raised; `point_branch_at_commit`
called with `("main", LOCAL_TIP)` and never with `("feat-x", …)`;
`create_commit_from_tree` not called; no emission of a merged outcome.
**Sufficiency**: the contract Requirement names **every** conflict — the
checkout-free merge of another topic is the default path of the whole
feature; without the explicit None branch the design would plant `None`
(raw git error) and leave the written reconciliation behind.

#### `test_resolve_propagation_is_read_only`

**Setup**: target mocked; inventory with local `main`; current branch
`feat-x`.
**Input**: `resolve_propagation("feat-x", "main", None, None,
year="2026")`.
**Trace**: strategy None → `"merge"`; origin configured True; base not
current; message rendered from the default.
**Assertions**: `PropagationPlan(target, "main", "merge", "Propagate
topic 'feat-x' into 'main'", "2026")`; `resolve_exchange_base` /
`fetch_branch` / any write not called.
**Sufficiency**: a declined confirmation must have performed nothing —
the read-only plan is the whole confirmation safety.

#### `test_execute_propagation_merge_builds_plants_pushes`

**Setup**: own tip OWN; `resolve_exchange_base` → `ExchangeBase("main",
BASE_TIP, "main", False)`; rollback_tip LOCAL_TIP;
`is_ancestor(OWN, BASE_TIP)` → False; `merge_tree(BASE_TIP, OWN)` →
TREE; `resolve_commit_tree` → base tree `"t0"`, delivery tree `"t1"`
(differ); `create_commit_from_tree` → DELIVERY; `push_branch` ok.
**Input**: `execute_propagation(plan)` (strategy merge, message M).
**Trace**:
```
own tip ; rollback capture
base resolved ; base.local_branch "main" != current "feat-x"
not nothing-to-do (reachability False)
merge_tree(BASE_TIP, OWN) → TREE ; create_commit_from_tree(TREE, [BASE_TIP, OWN], M)
delivery tree "t1" != base tree "t0"   # not content-idempotent
point_branch_at_commit("main", DELIVERY)
push_branch("main")
emit_propagated(identity, "main", "merge", "merged")
return "Propagated topic 2026/feat-x into 'main' via merge (merged)"
```
**Assertions**: the parent order `[BASE_TIP, OWN]`; the plant; one
`push_branch("main")`; no `push_revision_to_branch`; the emitted facts;
the line.
**Sufficiency**: the default delivery path end-to-end — build, plant,
push, notify — with the propagate-side parent order (base first).

#### `test_execute_propagation_reachability_nothing_to_do`

**Setup**: `is_ancestor(OWN, BASE_TIP)` → True; `resolve_exchange_base`
reconciled=True with local branch `main`, rollback captured.
**Input**: `execute_propagation(plan)`.
**Trace**: nothing-to-do → emit `(outcome="nothing-to-do")` → return;
the reconciliation **stands** (no restore).
**Assertions**: no `merge_tree`, no plant, no push;
`point_branch_at_commit` not called with the rollback tip; the emitted
outcome and strategy; the result line names `nothing-to-do`.
**Sufficiency**: the idempotent success must emit like any other and
keep the sanctioned base bookkeeping — a rollback here would undo a
legitimate convergence.

#### `test_execute_propagation_content_nothing_to_do`

**Setup**: reachability False; `merge_tree(BASE_TIP, OWN)` → TREE;
`resolve_commit_tree` → `"t0"` for both the base tip and the delivery.
**Input**: `execute_propagation(plan)` (merge).
**Trace**: the delivery tree equals the base tree → emit nothing-to-do
→ return; nothing planted, nothing pushed.
**Assertions**: no `create_commit_from_tree`, no plant, no push; the
emitted outcome `nothing-to-do`.
**Sufficiency**: “carried means content, never the mere presence of the
topic directory” — the second idempotency form is the propagate-specific
contract a plain reachability check misses (e.g. a squash already
landed with a different commit).

#### `test_execute_propagation_squash_single_parent`

**Setup**: merge tree ok; trees differ.
**Input**: plan strategy `squash`.
**Trace**: `create_commit_from_tree(TREE, [BASE_TIP], M)` → plant →
push → emit `("squash", "squashed")`.
**Assertions**: exactly one `-p` parent (BASE_TIP); the outcome line.
**Sufficiency**: a two-parent squash would inject the topic's whole
history into the base — the opposite of squashing.

#### `test_execute_propagation_ff_delivers_own_tip_without_commit`

**Setup**: `is_ancestor(BASE_TIP, OWN)` → True (fast-forwardable),
reachability `is_ancestor(OWN, BASE_TIP)` → False.
**Input**: plan strategy `ff`.
**Trace**: delivery = OWN (no `create_commit_from_tree`) → plant
`("main", OWN)` → push → emit `("ff", "fast-forwarded")`.
**Assertions**: no commit-tree invocation; the plant target is OWN.
**Sufficiency**: ff must not author a commit — the base simply advances
to the topic tip.

#### `test_execute_propagation_ff_impossible_rolls_back`

**Setup**: both containments False; base reconciled with rollback
captured.
**Input**: plan strategy `ff`.
**Trace**: ff guard fails → clean error suggesting manual git → uniform
rollback `point_branch_at_commit("main", LOCAL_TIP)`.
**Assertions**: `click.ClickException`; the restore happened; nothing
pushed.
**Sufficiency**: regression of the fixed CODEMANIFEST defect — the ff
error joins the uniform rollback (the reconciliation must not survive a
failed delivery).

#### `test_execute_propagation_retry_cycle_recovers_once`

**Setup**: `push_branch` fails first with
`CalledProcessError(1, cmd)` stderr `! [rejected] main -> main
(non-fast-forward)`; the retry fetch + re-resolution yields a moved
`BASE_TIP2` (already containing the first delivery); second push
succeeds.
**Input**: plan strategy merge.
**Trace**: build/plant/push → rejected (signature matched) → echo
`Fetching origin/main...` → `fetch_branch("main")` → resolution tail
re-runs → the rebuilt delivery is nothing-to-do or a fresh commit →
re-plant → re-push ok → emit.
**Assertions**: `fetch_branch` called exactly once during retry; the
echo line printed; exactly two `push_branch` calls; no restore with the
rollback tip on success; the result line returned.
**Sufficiency**: the exactly-once retry is the contract's answer to
racing teammates — an unbounded retry or a missing rebuild would either
loop or push a stale delivery.

#### `test_execute_propagation_second_rejection_fails_with_rollback`

**Setup**: both pushes rejected with the signature; reconciliation was
written.
**Input**: plan strategy merge.
**Trace**: retry → rejected again → rollback → clean error.
**Assertions**: `click.ClickException` carrying git's reason;
`point_branch_at_commit("main", LOCAL_TIP)` (the pre-resolution tip)
called after the second failure; exactly two pushes.
**Sufficiency**: the uniform failure atomicity — a failed delivery must
leave the pre-operation state, reconciliation included.

#### `test_execute_propagation_write_through_remote_only_base`

**Setup**: `resolve_exchange_base` → `ExchangeBase("origin/main",
BASE_TIP, None, False)`; no local `main` → no rollback tip.
**Input**: plan with base_ref `"origin/main"`.
**Trace**: plant skipped → `push_revision_to_branch(DELIVERY, "main")`
(the `origin/` prefix stripped).
**Assertions**: `point_branch_at_commit` not called;
`push_revision_to_branch` called with `"main"`; no rollback attempted.
**Sufficiency**: the write-through is the only path that must not plant
locally — a plant here would create an unmanaged local branch; the
short-name strip drives the remote branch name.

#### `test_resolve_divergence_marker_matrix`

**Setup**: mocked `resolve_ref_commit` and `is_ancestor`.
**Input**: four cases — base None; unresolvable base; both projections
contained; one projection not contained.
**Trace**: None → None; empty projections → None; all contained →
`"current"`; else `"behind"`.
**Assertions**: the four returns; no exception in any case (the
unresolvable resolution raises `CalledProcessError` internally and is
swallowed).
**Sufficiency**: the board's marker rule and its never-fail guarantee —
a raising marker would break the whole board render on one odd ref.

#### `test_collect_topic_board_sets_topic_scoped_divergence`

**Setup**: the existing board fixture (two branches hosting `feat-x`,
one merged host) extended: base_ref `"main"`; `resolve_divergence`
mocked per tip.
**Input**: `collect_topic_board(year="2026", base_ref="main")`.
**Trace**: the pass computes the marker once per own-branched topic and
sets it on every record of the topic.
**Assertions**: every record of `feat-x` carries the same marker;
`aggregate_topic_board` projects the winner's marker into the entry;
calling without `base_ref` yields all-None markers.
**Sufficiency**: the additive board contract — one marker per topic,
projected deterministically, and None-safe without a configured base.

#### `test_render_topic_board_info_six_columns_with_base`

**Setup**: entries `[BoardEntry(topic="feat-x", branch="feat-x",
hosts=["feat-x", "main"], statuses=["[todo]"], current=True, remote=
False, todo="Fix retries", divergence="behind")]`.
**Input**: `render_topic_board(entries, width=120, info=True)`.
**Trace**: six-column rule (topic/branch/hosts/todo/base each ≤
(120−18)//6, statuses the remainder, min 8) → header `Topic | Branch |
Hosts | Todo | Base | Statuses` → the row shows `behind` in Base.
**Assertions**: the header words in order; the cell `behind`; a None
divergence renders an empty cell (second entry); the table never
exceeds the width above the narrow threshold.
**Sufficiency**: the sixth share and the Base column are the visible
board change — an off-by-one in the share math silently starves
statuses.

#### `test_render_board_json_carries_divergence_key`

**Input**: `render_board_json([entry_with_divergence,
entry_without])`.
**Trace**: each entry shapes into the eight keys.
**Assertions**: every JSON object has `divergence` (`"behind"` /
`null`); the key set is exactly {topic, branch, hosts, statuses,
current, remote, todo, divergence}; records shape without `hosts`.
**Sufficiency**: the always-present key is the additive JSON contract —
omitting it on null breaks every machine consumer.

#### `test_cli_update_resolves_configuration_inputs`

**Setup**: CliRunner; `load_project_config` + `ConfigHooks` mocked to an
overlay whose effective topics is `TopicsConfig(base_ref="origin/main",
update=TopicsUpdateConfig(strategy="rebase", commit="U {slug}"))`;
`update_topic` mocked.
**Input**: `["topics", "update"]`.
**Trace**: base None → configuration read → `origin/main`; strategy
`"rebase"` verbatim; template `"U {slug}"` verbatim; delegation
`update_topic(None, "origin/main", "rebase", "U {slug}", False, None)`.
**Assertions**: the delegation kwargs; the amendment summary lines went
to stderr; exit 0; `update_topic`'s line echoed to stdout.
**Sufficiency**: the flag-beats-configuration ladder and the verbatim
pass-through are the CLI's entire job; validating here instead would
duplicate the domain error.

#### `test_cli_propagate_confirmation_and_yes`

**Setup**: CliRunner; `resolve_propagation` mocked to a plan
(`target.topic="feat-x"`, `base_ref="main"`); `execute_propagation`
mocked returning a line. The confirm gate needs a terminal: the
`_TtyStdin` fixture of `tests/commands/topics/test_topics.py` (a
`TextIOWrapper` whose `isatty()` reads True) feeds the runner, exactly
as the `delete`/`clear` confirm tests do — a plain string `input=` is
not a TTY and would hit the non-interactive clean error instead.
**Input**: (a) `["topics", "propagate"]` with `input=_TtyStdin("y\n")`;
(b) `["topics", "propagate", "--yes"]` (no TTY needed); (c)
`input=_TtyStdin("n\n")`; (d) a plain non-TTY stdin without `--yes`.
**Trace**: (a) one confirm naming `feat-x`, `main`, and the push →
execute; (b) no prompt → execute; (c) declined → exit 0, nothing
executed; (d) `isatty()` False → the clean non-interactive error before
any prompt.
**Assertions**: (a) output contains `feat-x` and `main` and a push
mention; `execute_propagation` called once; (b) called once without any
prompt text; (c) `execute_propagation` not called, exit_code 0; (d)
`execute_propagation` not called, exit_code 1, the error names the
interactive-terminal requirement and `--yes`.
**Sufficiency**: exactly one confirmation with the `--yes` escape and
the decline-exits-0 contract — the safety interlock of an inherently
pushing command; (d) pins the non-interactive guard the contract
requires alongside the escape.

#### `test_cli_board_passes_configured_base`

**Setup**: `_topics_section` mocked to `TopicsConfig(base_ref="main")`;
`collect_topic_board`/`aggregate_topic_board` mocked.
**Input**: `["topics", "board", "--info"]`.
**Assertions**: `collect_topic_board` received `base_ref="main"` in
both views; with the configuration absent (None) the parameter is None
and the command still exits 0.
**Sufficiency**: the board reads the configuration only — a missing
file must degrade to empty Base cells, never an error.

#### `test_emit_updated_and_emit_propagated_addresses`

**Setup**: the existing `tests/topics/hooks` registry fixtures.
**Input**: `TopicHooks().emit_updated(identity, base="main",
effective_tip="cc3", strategy="merge", outcome="merged",
published=True)`; `emit_propagated(identity, base="main",
strategy="ff", outcome="fast-forwarded")`.
**Trace**: context built → `emit_hook_event(registry, "topics",
"topic_updated"/"topic_propagated", ...)` under the soft class.
**Assertions**: the receiving tool saw a `TopicUpdated` /
`TopicPropagated` instance with the exact fields; a raising hook is
warned-and-skipped (the fixture's failing-hook case) and the call
returns None.
**Sufficiency**: the two new addresses and their soft treatment are the
hooks-platform contract; the contexts are frozen (immutability checked
in the contexts test).

---

### Negative Tests

#### `test_loader_rejects_non_mapping_topics_section`

**Setup**: yaml `topics: 5`.
**Input**: `load_project_config()`.
**Trace**: `_parse_topics` sees a non-dict → `ValueError("'topics' must
be a mapping in .goga/config.yml")`.
**Assertions**: `pytest.raises(ValueError)` with that message.
**Sufficiency**: the structural error class is the loader's whole
validation vocabulary — an `AttributeError` here would pierce the CLI
clean-error wrapper.

#### `test_loader_rejects_non_mapping_update_section`

**Setup**: yaml `topics: {update: 5}`.
**Input**: `load_project_config()`.
**Trace**: `_parse_topics_section(5, "update", ...)` sees a non-dict →
`ValueError("'topics.update' must be a mapping in .goga/config.yml")`.
**Assertions**: `ValueError` naming `topics.update`.
**Sufficiency**: per-section structural errors must name the dotted key
so the user can fix the exact line.

#### `test_loader_rejects_non_string_strategy`

**Setup**: yaml `topics: {update: {strategy: 3}}`.
**Input**: `load_project_config()`.
**Trace**: `_parse_topics_field(3, "topics.update.strategy")` sees a
non-string → `ValueError("topics.update.strategy must be a string in
.goga/config.yml")`.
**Assertions**: `ValueError` naming `topics.update.strategy`.
**Sufficiency**: the shared `_parse_topics_field` contract (non-string
→ ValueError naming the key) must hold on every nested leaf.

#### `test_catalog_declares_both_new_actions`

**Input**: `declared_actions()`.
**Assertions**: contains `Action("topics", "topic_updated", "soft")`
and `Action("topics", "topic_propagated", "soft")`; the topics domain
now counts nine actions.
**Sufficiency**: an emission whose address is missing from the catalog
raises `ValueError(unknown hook action)` at runtime — the record is the
compile-time half of the contract.

#### `test_resolve_exchange_target_refuses_remote_only`

**Setup**: `resolve_switch_candidates` → `[SwitchCandidate("origin/
feat-x", "feat-x", [], False, True)]`.
**Input**: `resolve_exchange_target("feat-x")`.
**Assertions**: `click.ClickException` whose message mentions
`goga topics switch`.
**Sufficiency**: update/propagate move the own branch — impossible
without a local branch; the refusal must be one shared error, not two
divergent ones.

#### `test_resolve_exchange_target_no_candidate_hints_board`

**Setup**: candidates → `[]`.
**Input**: `resolve_exchange_target("nope")`.
**Assertions**: the error message contains the board hint.
**Sufficiency**: the shared UX contract with switch — the user is told
where to look.

#### `test_resolve_propagation_invalid_strategy_is_config_error`

**Setup**: none — the whitelist fires first.
**Input**: `resolve_propagation("feat-x", "main", "merge-nono", None)`.
**Trace**: step 1 — the whitelist {merge, ff, squash} rejects the
value → clean configuration error naming `topics.propagate.strategy`;
the addressee is never resolved.
**Assertions**: `click.ClickException` whose message contains
`topics.propagate.strategy` and `merge-nono`; `resolve_exchange_target`
not called.
**Sufficiency**: the configuration-key naming is contractual (the user
must know which line to fix); the update-side test does not cover the
propagate key.

#### `test_resolve_propagation_without_origin_is_clean_error`

**Setup**: `origin_configured` → False.
**Input**: `resolve_propagation("feat-x", "main", None, None)`.
**Assertions**: `click.ClickException` mentioning origin; nothing
resolved further.
**Sufficiency**: the push is inherent — discovering a missing origin
after a mutation would violate the read-only plan.

#### `test_resolve_propagation_rejects_current_branch_base`

**Setup**: the addressed topic resolved on branch `feat-x` (not the
current branch); the inventory carries a local `main`;
`resolve_current_branch_name` → `"main"`; `origin_configured` → True.
**Input**: `resolve_propagation("feat-x", "main", None, None)`.
**Trace**: the step-4 guard — the local branch named `base_ref`
(`main`) is the current branch → clean error asking to switch away
first; the message render and the plan construction never run.
**Assertions**: `click.ClickException` asking to switch away first;
`render_commit_template` not called; no `PropagationPlan` built.
**Sufficiency**: propagating into the checked-out branch would need
in-place mutations the checkout-free contract forbids.

#### `test_execute_propagation_current_branch_base_guard`

**Setup**: `base.local_branch == "feat-x"` == current branch.
**Input**: `execute_propagation(plan)`.
**Trace**: step 2 — the resolved base's local branch equals the current
branch → clean error asking to switch away first; no build, no plant.
**Assertions**: clean error before any build.
**Sufficiency**: the execution-side twin of the resolve guard — the
plan may be executed later, when the user has switched.

#### `test_update_topic_publish_without_origin_is_clean_error`

**Setup**: `origin_configured` → False; the update itself succeeded
(mocked plant ok).
**Input**: `update_topic(..., publish=True)`.
**Assertions**: `click.ClickException`; the planted update stands (the
plant call remains in the recorded calls).
**Sufficiency**: the atomicity exception is deliberate — the error must
not roll the confirmed update back.

---

### Edge Case Tests

#### `test_update_topic_ff_else_with_no_own_work_fast_forwards`

**Setup**: strategy `"ff-else-merge"`; `is_ancestor(OWN, BASE_TIP)` →
True.
**Input**: the update of a non-current topic.
**Trace**: realized fast-forward → `point_branch_at_commit("feat-x",
BASE_TIP)` — no commit authored, no merge-tree.
**Assertions**: no `create_commit_from_tree`; the plant target is
BASE_TIP; the emitted strategy is `"ff-else-merge"` with outcome
`"fast-forwarded"`.
**Sufficiency**: the ff-else semantics — the emitted strategy stays the
configured name while the outcome records the realized kind; the
hooks-visible pair is the contract.

#### `test_update_topic_current_topic_dirty_tree_clean_error`

**Setup**: target current; `is_working_tree_clean` → False; base
reconciled with rollback captured.
**Input**: the update.
**Assertions**: clean error before any mutation call; the
reconciliation restored.
**Sufficiency**: the in-place path's precondition — a dirty tree must
stop the operation with the pre-operation state intact.

#### `test_update_topic_current_topic_merge_is_in_place`

**Setup**: target current; clean tree; strategy merge.
**Input**: the update.
**Trace**: pre-flight `merge_tree(OWN, BASE_TIP)` discarded →
`merge_into_current(BASE_TIP, message)` — the real mutation.
**Assertions**: `merge_tree` called exactly once (the pre-flight) and
`merge_into_current` once; no `point_branch_at_commit` on the topic
branch.
**Sufficiency**: the current topic must not take the checkout-free path
(the branch is checked out — moving its ref without the working copy
would desync HEAD).

#### `test_resolve_exchange_base_reconcile_conflict_is_clean_error`

**Setup**: the diverged pair — `list_branch_refs` →
`[BranchRef("main", False), BranchRef("origin/main", True)]`;
projections LOCAL_TIP / TWIN_TIP; no containment either way;
`is_ancestor(LOCAL_TIP, OWN)` and `is_ancestor(TWIN_TIP, OWN)` →
False (not already carried); `merge_tree(LOCAL_TIP, TWIN_TIP)` → None;
`create_commit_from_tree`, `point_branch_at_commit` captured.
**Input**: `resolve_exchange_base("main", "feat-x", OWN)`.
**Trace**: diverged → not carried → `merge_tree` → None → clean error
asking to reconcile the branch manually; nothing written.
**Assertions**: `click.ClickException` mentioning the manual
reconciliation; `create_commit_from_tree` not called;
`point_branch_at_commit` not called.
**Sufficiency**: the reconciliation is the exchange's only sanctioned
write onto a foreign branch — its conflict must surface as a clean
error before any write (the atomicity Requirement), never as a raw
plumbing failure or a half-written state.

#### `test_update_topic_current_topic_rebase_is_in_place_with_lease`

**Setup**: target `ExchangeTarget("feat-x", "feat-x", True)` (the
current topic); `is_working_tree_clean` → True; strategy rebase,
publish=True; the inventory carries `origin/feat-x`;
`replay_commits(BASE_TIP, OWN)` → REPLAYED (the pre-flight);
`rebase_current_onto` and `push_branch_with_lease` captured;
`point_branch_at_commit` captured.
**Input**: `update_topic(None, "main", "rebase", None, publish=True)`.
**Trace**: clean tree → the in-place pre-flight `replay_commits`
(discarded) → the real mutation `rebase_current_onto(BASE_TIP)` → the
twin exists → `push_branch_with_lease("feat-x", OWN)`.
**Assertions**: `replay_commits` called exactly once (the pre-flight —
the real mutation is git's own rebase, not a second plumbing replay);
`rebase_current_onto` called once with BASE_TIP; `point_branch_at_commit`
never called on `feat-x` (the in-place rebase moves HEAD itself); the
lease tip is exactly OWN; the emitted outcome `"rebased"`, published
True.
**Sufficiency**: the only path whose mutation is a real `git rebase`
rather than plumbing — a path mix-up (planting the branch ref without
the working copy) would desync HEAD from the files on disk.

#### `test_update_topic_lease_rejection_is_clean_error_update_stands`

**Setup**: as above, but `push_branch_with_lease` raises
`CalledProcessError(1, cmd)` with stderr `\"! [rejected] feat-x ->
feat-x (stale info)\"`.
**Input**: the same update.
**Trace**: the rebase completes → the lease push refuses (the remote
moved) → git's reason surfaces as a clean error; no retry — the retry
cycle belongs to propagate alone; the confirmed update stands.
**Assertions**: `click.ClickException` carrying `stale info`;
`push_branch_with_lease` called exactly once; `_restore_base` not
invoked (the atomicity exception — the update itself succeeded);
`rebase_current_onto` remains in the recorded calls.
**Sufficiency**: the lease is the rebase path's whole safety net —
\"never an overwrite\"; a retry here would defeat the protection the
lease exists to provide, and a rollback would discard confirmed work.

#### `test_resolve_exchange_base_remote_only_base_single_projection`

**Setup**: inventory `[BranchRef("origin/main", True)]` only.
**Input**: `resolve_exchange_base("origin/main", "feat-x", OWN)`.
**Trace**: branch-shaped, local missing → fetch → single projection
TWIN_TIP → effective TWIN_TIP, `local_branch=None`.
**Assertions**: the tuple `("origin/main", TWIN_TIP, None, False)`; the
fetch echo printed for the short name `main`.
**Sufficiency**: the remote-only base is the write-through enabler; a
None local_branch here drives the plant-skip in execute.

#### `test_resolve_exchange_base_descendant_of_pair`

**Setup**: `is_ancestor(LOCAL_TIP, TWIN_TIP)` → True.
**Input**: the resolution.
**Assertions**: effective tip TWIN_TIP, `reconciled=False`, no
`merge_tree`.
**Sufficiency**: the common converged case must not write anything —
the containment shortcut is what keeps the exchange cheap.

#### `test_replay_commits_empty_range_returns_onto`

**Setup**: `rev-list` → empty.
**Input**: `replay_commits("aa1", "aa1")` (a fully-carried line).
**Assertions**: returns `"aa1"`; no commit-tree calls.
**Sufficiency**: the degenerate replay feeds the rebase pre-flight of an
already-carried topic — a None here would read as a conflict.

#### `test_loader_empty_and_whitespace_strings_resolve_none`

**Setup**: yaml `topics: {base_ref: "", update: {strategy: "  "}}`.
**Input**: `load_project_config()`.
**Assertions**: `base_ref is None`; `update.strategy is None`; the
update section itself is a `TopicsUpdateConfig` (present section, unset
leaves).
**Sufficiency**: the empty-to-None normalization belongs to the loader
(the value objects store verbatim) — a whitespace strategy reaching the
domain would fail the whitelist with a confusing key error.

#### `test_overlay_accepts_nested_topics_amendment_paths`

**Setup**: an authored config without a topics section; a tool
amendment contributing `topics.update.strategy = "rebase"`.
**Input**: `merge_config_amendments(base, [contribution])`.
**Trace**: the path resolves through `ProjectConfig.topics` →
`_section("TopicsConfig")` → `update` → `_section("TopicsUpdateConfig")`
→ `strategy` scalar; missing sections materialize via the factories.
**Assertions**: the overlay's effective config carries
`topics.update.strategy == "rebase"`; the summary line names the path.
**Sufficiency**: the tree and factories are the amendment gate — a
missing tree node rejects every nested topics amendment (the exact gap
this topic closes); the `dataclasses.fields` cross-check tests extend
to the three new models.

#### `test_facade_reexports_nested_topics_models`

**Input**: `from goga.config import TopicsCreateConfig,
TopicsUpdateConfig, TopicsPropagateConfig`.
**Assertions**: the three names import; each is in `goga.config.__all__`
beside `TopicsConfig`; the cell facade count is 17.
**Sufficiency**: the facade is the single import entry point — consumers
must not reach into `goga.config.project`.

#### `test_topics_git_facade_exports_exchange_surface`

**Input**: `from goga.topics.git import require_git_version, is_ancestor,
resolve_commit_tree, merge_tree, create_commit_from_tree, replay_commits,
point_branch_at_commit, merge_into_current, rebase_current_onto,
fast_forward_current_branch, fetch_branch, push_branch_with_lease,
push_revision_to_branch`.
**Assertions**: all thirteen import and appear in `__all__` (28 exported
names total).
**Sufficiency**: the domain imports the exchange surface from the
package root — a missing export breaks the facade contract the
CODEMANIFEST declares.

#### `test_topics_facade_exports_operations`

**Input**: `from goga.topics import update_topic, resolve_propagation,
execute_propagation` (and `__all__` inspection).
**Assertions**: present in `__all__` beside the existing surface.
**Sufficiency**: the CLI's import path — the facade-only rule.

#### `test_publish_topic_renders_create_section_template`

**Setup**: `create_commit_from_tree`-equivalent mocked; template
`"Create {slug} from {base}"`.
**Input**: `publish_topic("feat-x", "Fix retries.", "main", "Create
{slug} from {base}", "2026")`.
**Assertions**: the commit message is `Create feat-x from main` (both
placeholders, `{base}` included).
**Sufficiency**: the `{base}` placeholder is new — the old single-
placeholder replace would leave it literal.

#### `test_cli_create_template_comes_from_create_section`

**Setup**: the effective topics `TopicsConfig(create=
TopicsCreateConfig(commit="C {slug}"))`.
**Input**: `["topics", "create", "feat-x", "--publish", "--todo",
"Fix."]`.
**Assertions**: `create_topic` received the template `"C {slug}"` (not
the retired `publish_commit`, not the default).
**Sufficiency**: the create rung's key changed — reading the old key
would strand every configured template at the default.

#### `test_cli_update_help_names_addressee_rule`

**Input**: `["topics", "update", "--help"]`.
**Assertions**: the help text states that an omitted IDENTIFIER
addresses the current topic.
**Sufficiency**: a contract Requirement of the subcommand surface;
--help is the only place the rule is visible to users.

---

## Additional Instructions for the Implementation Agent

- Implement bottom-up in the dependency order of this document
  (catalog → config/project → config facade → config/hooks → topics/git
  → topics/hooks → topics exchange/board/creation/publishing → updating
  → propagating → commands). Run `goga lint` after any CODEMANIFEST
  touch (none should be needed — the contracts are final) and
  `pytest`/`ruff` per the `convention` practice after each layer.
- Do not add validation to the CLI layer or the loader beyond this
  design: strategy whitelists live in `update_topic` /
  `resolve_propagation`; template grammar is never validated.
- The result-line and echo formats are fixed here: `Updated topic
  {year}/{slug} from '{base}' via {strategy} ({outcome})`,
  `Propagated topic {year}/{slug} into '{base}' via {strategy}
  ({outcome})`, `Fetching origin/{branch}...`, `Reconcile base
  '{name}'`, and the three built-in templates
  `Create topic '{slug}'`, `Update topic '{slug}' from '{base}'`,
  `Propagate topic '{slug}' into '{base}'` — implement them as module
  constants, single-sourced.
- `is_ancestor` must run without `check=True` (the rc-1 answer); every
  other new git invocation keeps `check=True` per the practice.
- Update the module docstrings whose counts changed (contexts.py/events.py
  five→seven; the git facade's inventory sentence; the topics facade's
  mutation sentence — the network set grew).
- The retired `publish_commit` readers in `goga/commands/topics/topics.py`
  (`section.publish_commit`) and any residual references in tests/docs
  are removed in this implementation — sweep for `publish_commit`
  outside the loader's silence and the plan/design documents.
- Extend the overlay `dataclasses.fields` cross-check tests to the
  three new models so tree drift stays detectable.
- The existing surface-enumeration tests of `tests/commands/topics/
  test_topics.py` (the sorted subcommand list, the per-subcommand
  parametrizations — the five-name lists around the group surface
  tests) grow `update` and `propagate` to seven entries; every mock of
  a topics-domain name moves to the `goga.topics` import point.
