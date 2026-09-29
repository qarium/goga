# Topics: Update from Base and Propagate into Base

## Problem

A developer working in goga's topic model manages each unit of work as one entity — a topic on its own branch. But while the base branch moves ahead, a long-lived topic silently falls behind, and the two operations that keep it healthy — refreshing it from its base, and delivering its finished work into the base — do not exist in the topic model: the developer performs them with raw git, managing delivery separately from topics. Divergence accumulates until the final merge becomes the most painful step of the whole cycle, and the split between git-level delivery and topic-level management forces thinking in two entities where the product promises one.

- **Who**: goga users working topics manually through the host-side CLI.
- **When**: a long-lived topic whose base has moved ahead; finished work that must land in the base (or another integration branch).
- **Blocked outcome**: refreshing a topic from its base and delivering its work into the base as native topic operations, without leaving the topic model for raw git.
- **Impact**: accumulated divergence and merge-time conflicts; delivery handled outside the topic entity; the board shows no signal of a topic falling behind.

## Users

**Primary user** — a goga developer, the single operator of the topic workflow, working manually through the host-side CLI in a git repository. Fluent in git, but choosing the topic model precisely to not manage branches, merges, and delivery as raw git objects.

- **Context**: works in a repo where the base branch (and peer integration branches) keep moving while topics live for days or weeks; uses `goga topics` board/create/switch daily; finished work must eventually land in the base.
- **Goals**: keep a long-lived topic current with its base; deliver finished topic work into the base (or another chosen branch) as a topic operation; think in one entity — the topic — from create to clear.
- **Expectations**: goga-style behaviour — clean errors with hints, confirmation before mutating steps, dirty-tree safety, bounded and reported network operations; no silent history rewrites of what goga does not own; visible outcome of every action.
- **Constraints**: terminal/CLI only; topic identity via the established identifier tiers; base resolution through the established ladder.

Secondary actors: none material — automation and pipelines are explicitly out of scope; remote peers are outside this change.

## Goals

- **G1 — Topic freshness**: the developer keeps a topic current with its base or a chosen branch as a native topic operation — divergence is resolved early and routinely, not accumulated until the final merge.
- **G2 — One-entity delivery**: delivering a topic's finished work into its base or a chosen branch is a native topic operation, without raw git; the topic remains the single entity from create to clear, and it stays alive after delivery (cleanup remains the separate `clear`).
- **G3 — Predictability and safety**: both operations fit the established goga contract — clean errors, confirmation for mutating steps, dirty-tree safety, bounded and reported network operations — bringing mid-lifecycle git power without surprises.
- **G4 — Divergence visibility**: the developer can see, on demand, that a topic has fallen behind its base — surfaced in the board's opt-in `--info` view.

## User Experience

### Entry points

- `goga topics board --info` shows a per-topic divergence marker against the resolved base (behind / current).
- `goga topics update [IDENTIFIER]` — refresh a topic from its base (the topic of the current branch when IDENTIFIER is omitted).
- `goga topics propagate [IDENTIFIER]` — deliver a topic's work into its base (same omission rule).

### Base as one logical branch

The base is addressed as **one logical branch**: a bare name and its `origin/` twin denote the same base. Both operations resolve it identically:

1. **Targeted fetch** of the branch first (eager, one network operation per invocation, bounded to the operation's own refs; each fetch is reported by one stdout line — `Fetching origin/<base>…` — before it runs).
2. **Effective tip** — the most advanced state available:
   - local branch and `origin/` twin both exist and one contains the other → the descendant is the effective tip (a local branch ahead of its remote contributes its commits; a remote ahead of the local contributes the fresh remote state);
   - they **diverged** (each carries commits the other lacks) → the operation reconciles the branch first with a checkout-free merge whose commit is written onto the **local** base branch (origin is never pushed by the reconciliation itself; the branch converges — afterwards the descendant rule applies); a reconciliation conflict is a clean error asking to reconcile the branch manually, with full rollback; in the idempotent case — the topic already contains the effective tip — nothing at all is mutated, the reconciliation included;
   - only one projection exists → its tip (a base that exists only on the remote is used through its remote-tracking ref).
3. A base that is a tag or a commit hash resolves to that commit; no fetch applies.

The base resolves from `--base-ref` > `topics.base_ref` in `.goga/config.yml`. There is no current-HEAD rung. No base at all is a clean error naming the flag and the configuration line. A base resolving to the topic's own branch is a clean error — the topic is its own base. Unconfigured `origin` is a clean error before any mutation.

### Update (base → topic)

- The user runs `goga topics update` on the current topic, or `goga topics update feat-x` for any identified topic. IDENTIFIER resolves through the switch tiers (exact branch name > exact topic slug > prefix); ambiguous on an interactive terminal → numbered prompt, headless → clean error. A bare invocation on a branch hosting no topic is a clean error. A topic whose hosting branch exists only as a remote-tracking ref is a rare edge answered by a clean error with a hint to `goga topics switch` first.
- The strategy comes from config only — `topics.update.strategy` (`merge` | `rebase` | `ff-else-merge` | `ff-else-rebase`, default `merge`):
  - `merge` — the base's commits land through a merge commit; the topic's history is never rewritten;
  - `rebase` — the topic's commits are replayed onto the effective tip;
  - `ff-else-*` — fast-forward when the topic has no own work, otherwise the named strategy.
- Updating the current topic happens in place — a dirty tree is a clean error before any mutation. Updating another topic never touches the working copy, index, or HEAD.
- No confirmation is asked.
- `--publish`/`-p` pushes the refreshed topic branch to `origin` after success: a plain push after `merge`; a protected force after `rebase` when the branch has an origin twin — an explicit lease against the topic's tip immediately before the rebase (the push succeeds only when the remote stands exactly on the rebased history; anything else is a clean refusal with git's reason). A failed publish push leaves the confirmed update in place and surfaces git's reason as a clean error.
- A topic already at the effective tip is an idempotent success with nothing mutated.
- Success feedback names the topic, base, strategy, and outcome; the `--help` text and the result line make the addressee visible (the current topic when IDENTIFIER is omitted, the identified one otherwise).

### Propagate (topic → base)

- Same identifier resolution and base ladder. One invocation delivers into exactly one target branch, and its push to `origin` is inherent — there is no `--publish` flag on propagate.
- The strategy comes from config only — `topics.propagate.strategy` (`merge` | `ff` | `squash`, default `merge`):
  - `merge` — a merge commit of the topic lands on the effective tip;
  - `ff` — fast-forward only; a non-fast-forwardable situation is a clean error;
  - `squash` — one squashed commit carries the topic's work.
- The operation is always checkout-free: the working copy, index, and HEAD are untouched; the user stays on their branch.
- Write path follows the resolved base — and every path ends on `origin`:
  - a **local branch** exists for the base → the result is written to that local branch **and pushed to `origin`** (the remote branch is created when absent), aligning the remote with the branch's whole history;
  - **no local branch exists** (the base is only `origin/<name>`) → write-through: the merge is built on the fresh remote-tracking tip and pushed to `origin` as an inherent part of the operation — naming the remote branch as the target is the explicit network consent;
  - an unconfigured `origin` is a clean error before any mutation;
  - a failed or rejected push on either path is a full rollback — nothing else was mutated.
- Exactly **one confirmation** before mutating, naming the target and the inherent push (e.g. `Propagate topic feat-x into origin/main? (push)`); `--yes`/`-y` skips it; a non-interactive terminal without `-y` is a clean error; a declined answer exits 0 with nothing done.
- Propagating into the currently checked-out branch is a clean error asking to switch away first.
- The topic stays alive after propagate: its branch and directory are untouched; cleanup remains the separate `clear`.
- A base that already carries the topic's **current state** is an idempotent success with a clear nothing-to-do message — "carried" means content, never mere presence of the topic directory.
- Success feedback names the topic, target base, strategy, and outcome.

### Conflicts and recovery

Any conflict — during the base reconciliation, an update merge/rebase, or a propagate merge — is detected read-only **before any mutation** (the merge, and under rebase every replayed commit, is pre-flighted) and is a clean failure: full rollback to the pre-operation state, nothing mutated, exit 1, and a message suggesting manual git resolution. A propagate push rejected because the remote moved concurrently gets one retry cycle (fetch, rebuild, push) before the clean error — a failed or rejected push on either write path rolls back fully. The single sanctioned exception to failure atomicity is an update whose `--publish` push failed: the confirmed local refresh stands and git's reason surfaces as a clean, actionable error.

### Divergence visibility

`goga topics board --info` carries a simple per-topic marker against the resolved `topics.base_ref`: a dedicated **Base** column with **behind / current** (binary, no counts), in both table views, ordered topic, branch, hosts, todo, base, statuses. The board never fetches and never fails when the base is unconfigured or unresolvable — the marker renders as an empty cell. Both JSON views carry an additive `divergence` field (`behind` | `current` | `null`). The rule: the own-branch tip contains the effective base tip, computed from local refs without network, identically in `--remote` mode.

## Requirements

### Command surface

1. `goga topics update [IDENTIFIER]` — new subcommand of the `goga topics` group; the group `--year` scoping applies.
2. `goga topics propagate [IDENTIFIER]` — same group, same scoping.
3. IDENTIFIER omitted → the topic hosted by the current branch; a current branch hosting no topic is a clean error. The `--help` text and the result line state the addressee explicitly (the current topic when omitted, the identified one otherwise).
4. IDENTIFIER resolves through the switch tiers; several candidates on an interactive terminal → numbered prompt with statuses; headless → the numbered list itself is the clean error.

### Base resolution

5. Both commands resolve the base as `--base-ref` > `topics.base_ref`; no current-HEAD rung; no base at all → clean error naming the flag and the configuration line; a base resolving to the topic's own branch → clean error (the topic is its own base).
6. The base is one logical branch: bare name and `origin/` twin denote the same base; resolution is fetch-then-effective-tip as described in the User Experience (targeted reported fetch; descendant wins; divergence reconciles first; single projection stands alone; tag/hash bases resolve directly).
7. Propagate delivers into exactly one target branch per invocation.

### Update behaviour

8. Strategy from `topics.update.strategy` (`merge` | `rebase` | `ff-else-merge` | `ff-else-rebase`); default `merge`; config-only — no CLI override; an invalid value is a clean configuration error naming the key.
9. Updating the current topic works in place; a dirty tree is a clean error before any mutation. Updating another topic performs the whole operation without checkout — the working copy, index, and HEAD stay untouched.
10. No confirmation is asked for update.
11. `--publish`/`-p` pushes the refreshed topic branch to `origin` after success: a plain push after `merge`; a protected force after `rebase` when an origin twin exists — an explicit lease against the topic's pre-rebase tip, refused with git's reason when the remote stands anywhere else; a failed publish push leaves the confirmed update in place as a clean error; unconfigured `origin` is a clean error before any mutation.
12. An already-current topic is an idempotent success; nothing is mutated.
13. Success feedback names the topic, base, strategy, and outcome.

### Propagate behaviour

14. Strategy from `topics.propagate.strategy` (`merge` | `ff` | `squash`); default `merge`; config-only; an invalid value is a clean configuration error naming the key.
15. Always checkout-free: the working copy, index, and HEAD are never touched.
16. The push is inherent to every propagate — there is no `--publish` flag: a local-branch base receives the result on the local branch and is pushed to `origin` (created when absent), aligning the remote with the branch's whole history; a remote-only base is written through — built on the fresh remote-tracking tip and pushed as part of the operation. Unconfigured `origin` is a clean error before any mutation; a failed or rejected push on either path is a full rollback.
17. Exactly one confirmation naming the target and the inherent push; `--yes`/`-y` skips it; non-interactive without `-y` is a clean error; a declined answer exits 0 with nothing done.
18. Propagating into the currently checked-out branch is a clean error asking to switch away first.
19. The topic stays alive after propagate: its branch and directory are untouched; cleanup remains the separate `clear`.
20. Idempotency is content-based: a base already carrying the topic's current state is a nothing-to-do success; mere directory presence never suppresses delivery of newer work.
21. Success feedback names the topic, target base, strategy, and outcome.

### Failures and rollback

22. Any conflict during reconciliation, update, or propagate is detected read-only before any mutation (pre-flight) and is a clean failure: full rollback to the pre-operation state, nothing mutated, exit 1, message suggesting manual git resolution.
23. A propagate push rejected for concurrent remote movement gets one retry cycle (fetch, rebuild, push) on either write path; a second rejection is a clean error with a full rollback.
24. Failure atomicity holds uniformly for propagate — a failed or rejected push on either write path leaves the pre-operation state untouched. The single sanctioned exception is an update whose `--publish` push failed: the confirmed local refresh stands and the failure is a clean error with git's reason.
25. Every failure is a clean error naming the responsible option with an actionable hint, exit 1, and no partial mutations.

### Divergence visibility

26. `board --info` shows a per-topic binary divergence marker (behind / current) as a dedicated Base column in both table views against the resolved `topics.base_ref`; the board never fetches; an unconfigured or unresolvable base renders an empty marker cell and never fails the board; both JSON views carry an additive `divergence` field (`behind` | `current` | `null`).

### Configuration

27. New nested configuration keys `topics.update.strategy` and `topics.propagate.strategy` in `.goga/config.yml`, validated consistently with the existing `topics` section rules (non-string or invalid values are clean configuration errors naming the key).
28. Commit-message template keys in the same nested shape — `topics.create.commit`, `topics.update.commit`, `topics.propagate.commit` — with `{slug}` and `{base}` placeholders (unknown placeholders stay verbatim); the legacy `topics.publish_commit` key is removed in favour of `topics.create.commit` (the docs carry a migration note); `--commit/-c` stays the create-only CLI override; update and propagate expose no message override.

### Commit messages

29. Every goga-authored commit message follows the git-merge style — `<Verb> <object>` with quoted names, no `goga:` prefix — sourced from the `topics.<op>.commit` templates with the built-in defaults `Create topic '{slug}'` (creation), `Update topic '{slug}' from '{base}'` (update merge), and `Propagate topic '{slug}' into '{base}'` (propagate merge and squash — one template serves both). The base reconciliation commit message is fixed — `Reconcile base '<base>'` — and not configurable. Rebase reuses the original commit messages; fast-forward strategies author no commits.

### Lifecycle events

30. Topic update and topic propagation fire through the topics hooks zone so hook consumers observe the new lifecycle steps.

## Constraints

- **Network is bounded and reported**: the only network operations are the targeted fetch of the operation's own refs (each preceded by one reported stdout line), the push inherent to every propagate, and the explicit `--publish` pushes of update. Nothing else ever fetches; the board never touches the network.
- **Working-copy sanctity**: outside the established bounded mutations (the switch checkout, the in-place update of the current topic), the working copy, index, and HEAD are never touched; propagate is always checkout-free.
- **History ownership**: goga never rewrites history it does not own — the only rewrite is the configured `rebase` strategy on the topic's own branch, published with protection; a base branch only ever receives new commits (merge, fast-forward, squash, reconciliation) and its existing history is never rewritten; the reconciliation merge is an additive commit on the local base branch and is never itself pushed.
- **Base and config**: base resolution stays on the established ladder (`--base-ref` > `topics.base_ref`, no current-HEAD rung); the `topics` config section is the single home for the new nested keys — the strategy knobs and the `topics.<op>.commit` message templates; the legacy `topics.publish_commit` key is removed in favour of `topics.create.commit`.
- **Topic lifetime**: a topic exists exactly as long as its own branch exists; the merged-topic semantics stay owned by the existing model, shared by propagate's content-based idempotency and clear's detection.
- **Failure atomicity**: every operation is all-or-nothing — a failed or conflicted operation leaves the pre-operation state untouched; the single sanctioned exception is a confirmed update whose `--publish` push failed.
- **Exchange mechanics**: the topic↔base exchange runs on git plumbing — merges via the `merge-tree` write-tree form, commits via `commit-tree`, results planted by a single ref update; conflicts are detected read-only before any mutation, and the checkout-free paths are atomic by construction (built objects stay dangling until the final ref update). The `merge-tree` write-tree form requires **git 2.38**; an older git fails with a clean error naming the version.
- **CLI conventions**: the Click group `goga topics` with subcommands, exit codes 0/1, terminal-gated confirmations with a `--yes` escape, switch-tier identifier resolution, and a board that never fails on missing configuration are established conventions the new commands follow.
- **Hooks**: lifecycle events fire through the topics hooks zone; no parallel event mechanism is introduced.
- **Documentation surface**: goga ships its feature docs with the product — the topics documentation (cli, configuration, hooks, index, api) carries the new behavior in the same change.

## Scope

### In Scope

- `goga topics update [IDENTIFIER]` — full behaviour: identifier resolution, logical-branch base resolution with targeted fetch and effective tip, `topics.update.strategy` semantics, in-place vs checkout-free paths, idempotency, `--publish` with protected force after rebase.
- `goga topics propagate [IDENTIFIER]` — full behaviour: `topics.propagate.strategy` semantics, checkout-free execution, one confirmation with `--yes` escape, the local-write and write-through paths with their inherent push and uniform full rollback, content-based idempotency, topic stays alive.
- Conflict behaviour for both: read-only pre-flight detection, clean failure, full rollback, manual-git handoff, the push retry cycle, the update `--publish` push-failure exception.
- Nested configuration keys `topics.update.strategy` and `topics.propagate.strategy` with clean validation, plus the `topics.create.commit`, `topics.update.commit`, `topics.propagate.commit` message templates replacing `topics.publish_commit`.
- The board `--info` divergence marker (behind / current) and the additive JSON `divergence` field.
- Lifecycle events for update and propagate through the topics hooks zone.
- Documentation of the new behavior on the topics docs surface.

### Out of Scope

- Multi-target propagation in one invocation — one invocation targets one branch; several targets are several invocations.
- Strategy CLI overrides — strategies are configuration-only.
- Network operations beyond the bounded targeted fetch and the explicit/inherent pushes described above.
- Numeric divergence counts — the marker is binary.
- Automatic topic cleanup after propagate — `clear` stays the separate cleanup step.
- Pipeline/automation integration (afm, `goga pipeline`) of the new commands — manual CLI workflow only.
- Changes to existing subcommand semantics (`create`, `switch`, `delete`, `clear`) — the board `--info` marker is the only touch on an existing surface.
- Interactive conflict resolution inside goga — conflicts hand off to manual git.

## Success Criteria

1. **SC1 (G1)**: on a topic whose base moved ahead, `goga topics update` brings the base's changes into the topic — including the case where the local base branch is ahead of its origin twin — and the board `--info` marker afterwards reads current.
2. **SC2 (G1)**: re-running update on an already-current topic succeeds idempotently with nothing mutated.
3. **SC3 (G2)**: `goga topics propagate` lands the topic's work in the target branch while the topic stays alive — its branch and directory remain, and `clear` afterwards recognizes it as merged; the inherent push aligns the remote with the branch's whole history.
4. **SC4 (G2)**: the full loop create → update (repeatedly) → propagate → clear completes without a single raw git command for the topic↔base exchange.
5. **SC5 (G3)**: a conflicted update or propagate leaves the repository exactly at its pre-operation state — no partial mutation, exit 1, actionable error.
6. **SC6 (G3)**: the network is touched only by the targeted reported fetch of the operation's own refs and by pushes inherent to propagate or explicit on update's `--publish`; the board never touches the network.
7. **SC7 (G3)**: a rebased topic's `--publish` uses protected force — a remote moved by someone else is a clean refusal, not an overwrite.
8. **SC8 (G4)**: board `--info` shows an accurate behind/current marker per topic against `topics.base_ref` and never fails when the base is unconfigured.
9. **SC9**: hooks consumers observe the update and propagate lifecycle events through the topics hooks zone.
