# Topics: Update from Base and Propagate into Base

## Current State

The topics domain (`goga/topics`) covers the full manual lifecycle of a topic —
creation (with the todo acquisition ladder, quarantined no-switch publication,
and the switch path), ensure, switch, todo entry, deletion, clear, and the
board in two projections plus JSON. The two operations that keep a long-lived
topic healthy do not exist as topic operations:

- `goga/topics/git` provides read-only inspection, host-side branch mutations,
  quarantined commit construction through a temporary index, publication
  (push with upstream binding), and remote branch deletion. There is no
  checkout-free merge machinery (`merge-tree`), no replay, no targeted fetch,
  and no push with `--force-with-lease`.
- `goga/topics/hooks` exposes five notification contexts and two amendment
  drafts (seven checkpoints); the events `topic_updated` and
  `topic_propagated` do not exist, nor do their catalog entries.
- `TopicsConfig` in `goga/config/project` is the flat
  `(base_ref, publish_commit)` form; the nested `topics.<op>.<knob>` keys do
  not exist.
- `goga/commands/topics` carries board/create/switch/delete/clear; there are
  no `update`/`propagate` subcommands, and the board shows no divergence
  signal.
- The topics docs surface (`docs/features/topics/{index,cli,configuration,
  hooks,api}.md`) documents the current behavior only.

A developer refreshes a topic from its base and delivers work into the base
with raw git, outside the topic model; divergence is invisible until the final
merge.

## Description

Implement the topic↔base exchange as native topic operations, exactly per the
ADR (decisions D1–D11) and the aligned PRD of this topic:

1. **Checkout-free exchange on git plumbing** — merges built with
   `merge-tree --write-tree` plus `commit-tree` and planted by a single
   `update-ref`; the rebase of a non-current topic is a plumbing replay of its
   own commits with author and message preserved; descendant checks and
   targeted fetch through the same plumbing layer. Hard floor **git ≥ 2.38**;
   an older git fails with a clean error naming the version. Built objects
   stay dangling until the final ref update — atomicity by construction.
2. **Base as one logical branch** — resolution ladder `--base-ref` (an
   option of both commands) > `topics.base_ref` (no current-HEAD rung);
   targeted fetch of the base first
   (one reported stdout line before each fetch); effective tip = the
   descendant of the local/origin pair, or a reconciliation merge written onto
   the local base branch when they diverge (fixed message, never pushed, no
   reconciliation in the idempotent case), or the single projection's tip, or
   the commit a tag/hash resolves to. Self-base and missing base are clean
   errors.
3. **`goga topics update [IDENTIFIER]`** — strategies
   `merge | rebase | ff-else-merge | ff-else-rebase` from
   `topics.update.strategy` (config-only, default `merge`); `ff-else-*`
   fast-forwards when the topic has no own work and otherwise applies the
   named strategy; no confirmation is asked; the current topic
   updates in place (dirty tree is a clean pre-mutation error), any other
   topic fully checkout-free; every conflict pre-flighted read-only before any
   mutation; an already-current topic is an idempotent success mutating
   nothing; `--publish`/`-p` pushes the refreshed branch — a plain push after
   merge, a protected `--force-with-lease=<branch>:<pre-rebase-tip>` after
   rebase when the branch has an origin twin; a failed publish push leaves
   the confirmed update standing as the single atomicity exception.
4. **`goga topics propagate [IDENTIFIER]`** — strategies
   `merge | ff | squash` from `topics.propagate.strategy` (config-only,
   default `merge`) — `ff` fast-forwards only and a non-fast-forwardable
   situation is a clean error, `squash` carries the topic's work as one
   squashed commit; always checkout-free; the push is inherent: a local-base
   result is written to the local branch and pushed to origin (remote branch
   created when absent), a remote-only base is written through; exactly one
   confirmation naming the target and the push, with the `--yes` escape;
   content-based idempotency (nothing-to-do success); one retry cycle
   (fetch, rebuild, push) on a concurrently-moved remote; uniform full
   rollback on any failure; the topic stays alive after delivery.
5. **Lifecycle events** — notification-only soft actions `topic_updated` and
   `topic_propagated` through the topics hooks zone, with catalog entries;
   idempotent outcomes emit, a declined confirmation emits nothing.
6. **Nested configuration** — `topics.update.strategy`,
   `topics.propagate.strategy`, `topics.create.commit`,
   `topics.update.commit`, `topics.propagate.commit` (message templates with
   `{slug}` and `{base}` placeholders, unknown placeholders verbatim); the
   legacy `topics.publish_commit` key is removed in favor of
   `topics.create.commit` (migration note in the docs); `--commit/-c` stays
   the create-only CLI override — update and propagate expose no message
   override; invalid values are clean configuration errors naming the key.
7. **Commit messages** — git-merge style `<Verb> <object>` with quoted names,
   no `goga:` prefix; defaults `Create topic '{slug}'`,
   `Update topic '{slug}' from '{base}'`,
   `Propagate topic '{slug}' into '{base}'`; the reconciliation message
   `Reconcile base '<base>'` is fixed; rebase reuses original messages;
   fast-forward strategies author no commits.
8. **Divergence visibility** — a dedicated `Base` column (behind / current /
   empty) in `board --info` in both table views (default view order: topic,
   branch, hosts, todo, base, statuses; per-host view order: topic, branch,
   todo, base, statuses) and an additive JSON `divergence` field
   (`behind | current | null`) in both JSON views; the board never fetches
   and never fails on an unconfigured or unresolvable base.
9. **Documentation** — the new behavior shipped on the topics docs surface:
   `index.md`, `cli.md`, `configuration.md`, `hooks.md`, `api.md`.

## Scope

**In scope:**

- `goga topics update [IDENTIFIER]` — full behavior: switch-tier identifier
  resolution (current topic when omitted, explicit addressee in `--help` and
  the result line), logical-branch base resolution with targeted fetch and
  effective tip, strategy semantics, in-place vs checkout-free paths,
  pre-flight conflicts, idempotency, `--publish` with protected force.
- `goga topics propagate [IDENTIFIER]` — full behavior: strategy semantics,
  checkout-free execution, the single confirmation with `--yes`, the
  local-write and write-through paths with the inherent push, the retry
  cycle, uniform full rollback, content-based idempotency, topic stays
  alive.
- Base resolution machinery shared by both commands: targeted reported fetch,
  effective tip, reconciliation onto the local base branch, tag/hash bases,
  self-base and unconfigured-origin clean errors.
- Plumbing growth of the topics git access: merge-tree merges, commit-tree
  builds, single-ref planting, replay, descendant checks, targeted fetch,
  plain and lease-protected pushes, the git version floor.
- Nested `topics` configuration keys with clean validation, including the
  removal of `topics.publish_commit` and the template defaults.
- Lifecycle events `topic_updated` / `topic_propagated` with catalog entries
  and notification contexts through the topics hooks zone.
- The board `--info` `Base` column and the additive JSON `divergence` field.
- Edge semantics: self-base error, the bare invocation on a branch hosting
  no topic is a clean error, remote-only topic branch hinting
  `goga topics switch`, propagate into the checked-out branch refused,
  visible addressee of the bare invocation.
- Documentation of the new behavior on the topics docs surface (including
  the migration note for `topics.publish_commit`).
- Usage coverage: extension of the inline `git` practice of the topics git
  cell with the plumbing patterns, plus the cell-level usage files for the
  new operations (exact names and structure belong to the architecture
  stage).

**Out of scope:**

- Multi-target propagation in one invocation.
- Strategy CLI overrides — strategies are configuration-only.
- Network operations beyond the targeted reported fetch and the
  inherent/explicit pushes.
- Numeric divergence counts — the marker is binary.
- Automatic topic cleanup after propagate — `clear` stays separate.
- Pipeline/automation integration (afm, `goga pipeline`) of the new commands.
- Changes to existing subcommand semantics (`create`, `switch`, `delete`,
  `clear`) — the board `--info` marker is the only touch on an existing
  surface.
- Interactive conflict resolution inside goga — conflicts hand off to manual
  git.

## Acceptance Criteria

- SC1: on a topic whose base moved ahead, `goga topics update` brings the
  base's changes into the topic — including the case where the local base
  branch is ahead of its origin twin — and the board `--info` marker
  afterwards reads current.
- SC2: re-running update on an already-current topic succeeds idempotently
  with nothing mutated.
- SC3: `goga topics propagate` lands the topic's work in the target branch
  while the topic stays alive — its branch and directory remain, and `clear`
  afterwards recognizes it as merged; the inherent push aligns the remote
  with the branch's whole history.
- SC4: the full loop create → update (repeatedly) → propagate → clear
  completes without a single raw git command for the topic↔base exchange.
- SC5: a conflicted update or propagate leaves the repository exactly at its
  pre-operation state — no partial mutation, exit 1, actionable error
  suggesting manual git.
- SC6: the network is touched only by the targeted reported fetch of the
  operation's own refs and by pushes inherent to propagate or explicit on
  update's `--publish`; the board never touches the network.
- SC7: a rebased topic's `--publish` uses protected force — a remote moved
  by someone else is a clean refusal carrying git's reason, not an
  overwrite.
- SC8: board `--info` shows an accurate behind/current marker per topic
  against `topics.base_ref` and never fails when the base is unconfigured;
  both JSON views carry the `divergence` field.
- SC9: hooks consumers observe the update and propagate lifecycle events
  through the topics hooks zone.
- A repository with git older than 2.38 fails every exchange entry point
  with a clean error naming the required and present versions.
- `topics.publish_commit` in `.goga/config.yml` is no longer read; the docs
  carry the migration note to `topics.create.commit`.
- Validation: `pytest tests/ -x` passes; `ruff check` is clean; the docs
  build passes the project's documentation validation.

## Stack

- **Frameworks:** Click (existing `goga topics` command group).
- **Libraries:** Python 3.10+ stdlib only for new code — `subprocess`,
  `dataclasses` (`kw_only=True`); PyYAML through the existing config loader.
  No new third-party dependencies; `pyproject.toml` dependencies unchanged.
- **Infrastructure:** the host git binary (≥ 2.38) invoked via
  `subprocess.run` (`check=True`, `capture_output=True`,
  `GIT_TERMINAL_PROMPT=0`) — `merge-tree --write-tree`, `commit-tree`,
  `update-ref`, `rev-list`, `merge-base`, targeted `fetch`, plain and
  `--force-with-lease` pushes; a local origin remote in tests.
- **Testing:** pytest + pytest-cov, ruff; subprocess mocked per the
  `convention` practice; plumbing and exchange scenarios exercised against
  real temporary git repositories under `tmp_path`.
- **Docs:** MkDocs pages under `docs/features/topics/`.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| git ≥ 2.38 (plumbing exchange) | inline `git` practice of `goga/topics/git/CODEMANIFEST` + cell-level `.usages/` of the topics cells | updated (scheduled; decision q3 — variant A) |
| Click | `.goga/usages/cooks/click.md` | existing |
| PyYAML | inline `yaml` practice of `goga/config/project` | existing |
| beautiful_json | `.goga/usages/cooks/beautiful_json.md` | existing |

No `.goga/usages/cooks/` files are created or updated by this task: the git
knowledge stays whole inside the topics git cell per the project precedent,
and no synced dependency usages are involved.

## Risks and Constraints

- **git version floor** — `merge-tree --write-tree` requires git ≥ 2.38;
  every exchange entry point must gate on it with a clean error naming the
  version (D1).
- **Atomicity discipline** — checkout-free paths are atomic by construction
  (objects dangle until the single `update-ref`); the in-place update of the
  current topic relies on pre-flight conflict detection (D2) — any
  run-and-abort pattern is rejected.
- **Exactly two sanctioned network operations** — the targeted fetch of the
  operation's own refs (each reported by one stdout line before it runs) and
  the pushes (inherent on propagate, explicit `--publish` on update);
  nothing else ever fetches; the board never touches the network (D11).
- **Single atomicity exception** — a failed `update --publish` push leaves
  the confirmed refresh standing; every other failure rolls back fully (D4,
  D6).
- **Protected force semantics** — the lease binds to the topic's local tip
  immediately before the rebase, with no extra fetch of the topic twin;
  anything else on the remote is a clean refusal (D5).
- **Reconciliation placement** — onto the local base branch only, never
  pushed by the reconciliation itself, skipped entirely in the idempotent
  case (D3).
- **Breaking config change** — `topics.publish_commit` is removed; the 2.0
  fresh-start precedent applies and the docs carry the migration note (D7).
- **Board stability** — the `Base` column and the JSON `divergence` field
  are additive; an unresolvable base renders an empty cell, never a failure
  (D9).
- **History ownership** — the only rewrite is the configured rebase of the
  topic's own branch, published with protection; base branches only ever
  receive new commits.

## Scope Estimate

Single task — no decomposition (decision q4). The update and propagate
operations share the base-resolution machinery, the plumbing layer, the
nested configuration, the hooks zone, and the docs surface; splitting them
would create subtasks without independent user value. Cell-level
distribution and execution planning belong to the subsequent architecture
and planning stages. No additional topics were created.

## Existing Architecture

Affected cells and their integration requirements (contract design belongs
to the architecture stage):

- `goga/topics/git` — grows the plumbing exchange: checkout-free merges,
  commit builds, single-ref planting, replay, descendant checks, targeted
  fetch, plain and lease-protected pushes, the version gate. Stays
  environment access — every decision belongs to the callers.
- `goga/topics` — grows the update and propagate operations, the shared
  logical-branch base resolution with reconciliation, and the board
  divergence computation (local refs only, no network).
- `goga/topics/hooks` — grows the `topic_updated` / `topic_propagated`
  notification contexts and their emission checkpoints; notification-only,
  no new amendments.
- `goga/hooks/catalog` — grows the two soft action records.
- `goga/config/project` (re-exported through `goga/config`) — `TopicsConfig`
  takes the nested `topics.<op>.<knob>` shape with structural validation;
  `publish_commit` is removed.
- `goga/commands/topics` — grows the `update` / `propagate` subcommands and
  the board `Base` column / JSON `divergence` field.
- Docs surface `docs/features/topics/` — five pages updated in the same
  change.

## Notes

- Input artifacts: `adr.md` (D1–D11) and the aligned `prd.md` of this topic;
  this task adds no decisions beyond them.
- Formulation, stack, usage coverage (variant A — inline cell practice plus
  cell-level usages, no cooks files), and the single-task estimate were
  confirmed with the user in the specify dialog (q1–q4).
- Per stage constraints, the task intentionally contains no code examples
  and prescribes no architecture — type contracts, cell file layout, and
  CODEMANIFEST wording belong to the following prototype stage.
