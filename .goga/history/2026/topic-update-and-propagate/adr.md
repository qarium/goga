# Topic↔Base Exchange: Plumbing Mechanics, Inherent Propagate Push, and the Nested Topics Config

The PRD defined `goga topics update` and `goga topics propagate` on the unified
logical-branch base model. This ADR records the technical decisions taken in the
discovery interview that the PRD does not fix — the checkout-free git mechanics,
the reconciliation and protection semantics, the reshaped propagate push model,
and the resulting `topics` configuration shape. Where a decision amends the
PRD, the PRD file is updated in the same change; the amendments are listed under
"PRD amendments" below.

## Decisions

### D1. Checkout-free exchange runs on git plumbing; the floor is git 2.38

Merges are built with `git merge-tree --write-tree` (a real 3-way merge that
never touches the working copy) plus `git commit-tree` and planted with a single
`update-ref`; the rebase of a non-current topic is a plumbing replay
(`rev-list` of the topic's own commits, one merge-tree cherry-pick step each,
author and message preserved). Every built object stays dangling until the final
ref update, so atomicity holds by construction — a failed or conflicted
operation has mutated nothing. This continues the quarantined-index precedent of
the topics git cell and creates nothing outside `.git`.

Considered and rejected: temporary linked worktrees (create directories, leave
conflict state behind that must be cleaned up) and temporary clones (network and
disk cost, violates the bounded-network constraint).

Consequence: goga requires git ≥ 2.38 and fails with a clean error naming the
version when it is older.

### D2. Conflicts are detected pre-flight, before any in-place mutation

The in-place update of the current topic computes its merge — and, under the
rebase strategy, every replayed commit — read-only via merge-tree first. A
conflict is a clean error while nothing is mutated; only a clean pre-flight
proceeds to the real `git merge` / `git rebase`. Run-and-`--abort` was rejected:
an abort can fail or lose state, and the interim conflicted state violates the
"nothing mutated" guarantee.

### D3. Base reconciliation persists onto the local base branch

When the local base branch and its origin twin diverge, the operation writes
the reconciliation merge commit onto the **local** base branch; origin is never
pushed by reconciliation itself. The branch converges: afterwards the local
branch contains the twin, so the descendant rule applies and no reconciliation
repeats. In the idempotent case — the topic already contains the effective tip —
nothing at all is mutated, including the reconciliation; the already-current
check precedes the reconciliation write. A virtual reconciliation (compute the
merge but never move the base branch) was rejected: it leaves the base
permanently diverged and accrues empty merge commits on every repeated update.

### D4. The propagate push is inherent; there is no `--publish` on propagate (PRD amendment)

Propagate has no local-only outcome. With a local base the result is written to
the branch **and pushed to origin** (creating `origin/<base>` when absent); a
remote-only base is write-through by definition. The single confirmation always
names the target and the push. Failure atomicity is uniform: a conflict, or a
failed/rejected push after the one retry cycle, rolls back everything — the
PRD's "confirmed local propagation stands" exception is removed. An unconfigured
origin is a clean error before any mutation. `update --publish` remains
unchanged: it pushes the refreshed topic branch and is meaningful in every case.

### D5. Protected force is an explicit lease against the pre-rebase tip

After a rebase, `update --publish` pushes with
`git push --force-with-lease=<branch>:<T>` where `T` is the topic's local tip
immediately before the rebase, and without any additional fetch of the topic
twin. The remote must stand exactly on the history that was rebased; anything
else — moved ahead or otherwise — is a clean refusal carrying git's reason and a
hint to reconcile manually. Leasing against the remote-tracking ref was
rejected: when the twin is ahead of the local branch (a colleague pushed), the
lease would succeed and overwrite their commits.

### D6. `update --publish` push failure leaves the update standing (the one atomicity exception)

The publish push of an update happens after the operation has succeeded; a
failed push surfaces git's reason as a clean error while the local refresh
remains. With D4 removing the propagate exception, this is the single sanctioned
deviation from all-or-nothing.

### D7. The `topics` config takes the nested `topics.<op>.<knob>` shape; commit messages become templates (PRD amendment)

New keys: `topics.update.strategy` and `topics.propagate.strategy` (config-only,
no CLI override) plus `topics.create.commit`, `topics.update.commit`, and
`topics.propagate.commit` — commit-message templates with `{slug}` and `{base}`
placeholders; unknown placeholders stay verbatim. The legacy
`topics.publish_commit` key is **removed** (replaced by `topics.create.commit`;
the docs carry a migration note — the project has a fresh 2.0 breaking-change
precedent). `--commit/-c` stays the create-only CLI override; update and
propagate expose no message override.

All goga-authored commit messages follow the git-merge style — `<Verb>
<object>` with quoted names, no `goga:` prefix:

| Commit | Source | Default |
|---|---|---|
| Creation todo commit | `topics.create.commit` | `Create topic '{slug}'` |
| Base reconciliation | fixed, not configurable | `Reconcile base '<base>'` |
| Update merge | `topics.update.commit` | `Update topic '{slug}' from '{base}'` |
| Propagate merge and squash | `topics.propagate.commit` | `Propagate topic '{slug}' into '{base}'` |

One propagate template serves both merge and squash — the strategy changes the
commit's shape, not its message source. The reconciliation message stays fixed:
it is a bookkeeping commit, and binding it to an operation's template would give
one commit kind two different messages depending on the calling command.
Fast-forward strategies author no commits; rebase reuses the original messages.

### D8. Hooks: notification-only lifecycle events

Two soft actions in the topics zone, following the existing naming precedent:
`topic_updated` (identity; base name; effective tip; strategy; outcome —
merged / rebased / fast-forwarded / already-current; published flag) and
`topic_propagated` (identity; target base; strategy; outcome — merged /
fast-forwarded / squashed / nothing-to-do). No `pushed` flag — the push is
inherent (D4) and the flag would carry no information. Idempotent outcomes emit
their event (precedent: `topic_switched` with `already-on-branch`); a declined
confirmation emits nothing. An amendment checkpoint for the propagate commit
message was rejected: there is no user-editable pre-fixation content to expose.

### D9. The board marker is a dedicated `Base` column plus an additive JSON field

`board --info` gains a `Base` column in both table views — values `behind` /
`current`, an empty cell when the base is unconfigured or unresolvable, never a
failure, never a fetch; column order topic, branch, hosts, todo, base,
statuses. Both JSON views gain `"divergence": "behind" | "current" | null` — an
additive change to the stable record contract. The rule: the own-branch tip
contains the effective base tip, computed from local refs without network, and
applies identically in `--remote` mode.

### D10. Edge semantics and the visible addressee

A base resolving to the topic's own branch is a clean error ("the topic is its
own base") for both commands. A topic whose branch exists only as a
remote-tracking ref is a clean error hinting `goga topics switch`. Propagating
into the checked-out branch is a clean error asking to switch away first. The
bare `update` / `propagate` invocation addresses the current topic through the
switch tiers, and the addressee is made explicit in the `--help` text and in
the result line, which always names the topic and the base.

### D11. Every network operation is reported

Each targeted fetch prints one stdout line before it runs
(`Fetching origin/<base>…`); the retry cycle's second fetch is reported the
same way. The result line stays the single summary line of the operation.

## PRD amendments

Recorded here and applied to `prd.md` in the same change:

- The propagate push is inherent on every path; the `--publish` flag exists only
  on `update` (UX "Propagate", reqs 16, 17, 22–25; Constraints "Network is
  bounded", "Failure atomicity"; Scope; SC3, SC6).
- The failure-atomicity exception is now `update --publish`'s failed push, not a
  confirmed local propagation (req 24, Constraints).
- The `topics` section grows the three `topics.<op>.commit` template keys and
  loses `topics.publish_commit` (req 27, Constraints "Base and config"; the
  commit-message table above).
- Base resolution rejects a base equal to the topic's own branch (UX "Base as
  one logical branch", req 5).
- The board marker is the `Base` column plus the additive JSON `divergence`
  field (UX "Divergence visibility", req 26).
- Unconfigured origin is a clean error before mutation for propagate as well
  (UX "Propagate", req 16).

## Documentation surface

The behavior ships on the topics docs surface — `index.md`, `cli.md`,
`configuration.md`, `hooks.md`, and `api.md` (the facade API page; without it
the surface would be incomplete).
