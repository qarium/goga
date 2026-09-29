# Topics: Update from Base and Propagate into Base — Architecture Plan

## Topic

**Short name:** topic-update-and-propagate
**Plan path:** `.goga/history/2026/topic-update-and-propagate/arch.md`

The topic↔base exchange as native topic operations — `goga topics update`
and `goga topics propagate` — on checkout-free git plumbing, with the
shared logical-branch base resolution, the nested `topics.<op>.<knob>`
configuration, the `topic_updated` / `topic_propagated` lifecycle events,
the board divergence marker, and the topics documentation surface.

All eight affected cells already exist — nothing is created anew. Every
change below is an extension of an existing responsibility zone (project
memory: minimal structural footprint).

## Implementation Order

Ordered leaves to root; each step imports only already-settled material.

1. **`goga/hooks/catalog`** — leaf (no Imports). Two additive soft records
   unlock the new event addresses before the hooks zone references them.
2. **`goga/config/project`** — leaf (no Imports). The nested
   `TopicsConfig` shape the CLI and the domain consume; the facade
   `goga/config` re-exports the same type name, so its re-export is
   unchanged (one phrase of its global annotations is refreshed).
3. **`goga/config/hooks`** — imports `goga/config/project` (step 2). The
   amendment type tree and the section defaults follow the reshaped
   `TopicsConfig` — without this step the overlay rejects the new nested
   paths and its `TopicsConfig` factory no longer constructs.
4. **`goga/topics/git`** — leaf (no Imports). The exchange plumbing the
   domain orchestrates: build, plant, replay, fetch, pushes, version gate.
5. **`goga/topics/hooks`** — imports `goga/hooks` and `goga/history`
   (both unchanged). The two notification contexts and emissions over the
   already-registered catalog addresses.
6. **`goga/topics`** — imports `goga/topics/git`, `goga/topics/hooks`,
   `goga/history`, `goga/topics/editor` (edges unchanged, new types on
   them). The base-resolution machinery, the two operations, the board
   divergence.
7. **`goga/commands/topics`** — imports `goga/topics`, `goga/config`,
   and `goga/config/hooks` (edges unchanged). The two subcommands, the
   board base pass-through, the renderers.
8. **Usage files and documentation** — land with their cells as one
   synchronized change-set (project memory: atomic convergent change-sets
   — contract manifests, practice documentation, and the five
   `docs/features/topics/` pages never describe superseded semantics).

## Artifacts

For every existing CODEMANIFEST the plan states a **diff** — fragments to
add, replace, or delete; everything not mentioned stays verbatim. New
`.usages/` files are given in full.

### Cell 1 — `goga/hooks/catalog` (modified)

**CODEMANIFEST diff.** Header and footer unchanged. Body: append two
Requirements bullets to `declared_actions` (existing bullets stay
verbatim):

```yaml
    - The catalog carries the topics update-notification action — the
      record domain="topics", name="topic_updated", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics propagate-notification action — the
      record domain="topics", name="topic_propagated", error_class="soft":
      a failing hook of the action is skipped with a warning and the
      command continues
```

**.usages/** — none (data cell; stays without practices).

### Cell 2 — `goga/config/project` (modified) + `goga/config` facade

**CODEMANIFEST diff (`goga/config/project/CODEMANIFEST`).**

Header unchanged (`convention`, `yaml`). Global annotations unchanged.

Replace the type `TopicsConfig` with:

```yaml
"TopicsConfig(base_ref: str | None, create: TopicsCreateConfig | None, update: TopicsUpdateConfig | None, propagate: TopicsPropagateConfig | None)":
  location: config.py
  annotations: |
    The topics section of .goga/config.yml — the shared base of the
    topic exchange and the per-operation knobs and message templates.

    `base_ref`: any revision string the topic exchange resolves from —
                verbatim, None when unset
    `create`: the topics.create section, or None when absent
    `update`: the topics.update section, or None when absent
    `propagate`: the topics.propagate section, or None when absent

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `convention`
    - Fields are stored verbatim — the empty-to-None normalization
      belongs to `load_project_config`; the strategy whitelists, the
      template grammar, and the defaults belong to the consumer

    Constraints:
    - Do not resolve the revision string, validate strategy values, or
      validate template grammar at this level — structural typing
      belongs to `load_project_config`, semantics to the consumer
    - The retired publish_commit key does not exist in the model
  properties:
    "base_ref -> str | None": |
      The base revision of the topic exchange, verbatim from
      .goga/config.yml. None when the field is absent, YAML-null, or
      empty/whitespace-only (normalized by `load_project_config`).
    "create -> TopicsCreateConfig | None": |
      The topics.create section, or None when absent.
    "update -> TopicsUpdateConfig | None": |
      The topics.update section, or None when absent.
    "propagate -> TopicsPropagateConfig | None": |
      The topics.propagate section, or None when absent.
```

Add three new types:

```yaml
"TopicsCreateConfig(commit: str | None)":
  location: config.py
  annotations: |
    The topics.create section of .goga/config.yml — the commit message
    template of the creation todo commit.

    `commit`: the message template, verbatim — None when unset

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `convention`
    - Stored verbatim; the {slug}/{base} grammar and the default
      template belong to the consumer

    Constraints:
    - Do not validate the template grammar at this level
  properties:
    "commit -> str | None": |
      The commit message template of the creation, verbatim. None when
      the field is absent, YAML-null, or empty/whitespace-only.

"TopicsUpdateConfig(strategy: str | None, commit: str | None)":
  location: config.py
  annotations: |
    The topics.update section of .goga/config.yml — the update strategy
    and the commit message template.

    `strategy`: the strategy name, verbatim — None when unset (the
                consumer applies the default)
    `commit`: the message template, verbatim — None when unset

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `convention`
    - Stored verbatim; the whitelist and the defaults belong to the
      consumer

    Constraints:
    - Do not validate the strategy value or the template grammar at
      this level — an invalid value surfaces as a clean configuration
      error from the consumer, naming the key
  properties:
    "strategy -> str | None": |
      The update strategy source, verbatim. None when the field is
      absent, YAML-null, or empty/whitespace-only.
    "commit -> str | None": |
      The update commit message template, verbatim. None when unset.

"TopicsPropagateConfig(strategy: str | None, commit: str | None)":
  location: config.py
  annotations: |
    The topics.propagate section of .goga/config.yml — the propagation
    strategy and the commit message template.

    `strategy`: the strategy name, verbatim — None when unset (the
                consumer applies the default)
    `commit`: the message template, verbatim — None when unset

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `convention`
    - Stored verbatim; the whitelist and the defaults belong to the
      consumer

    Constraints:
    - Do not validate the strategy value or the template grammar at
      this level — an invalid value surfaces as a clean configuration
      error from the consumer, naming the key
  properties:
    "strategy -> str | None": |
      The propagate strategy source, verbatim. None when the field is
      absent, YAML-null, or empty/whitespace-only.
    "commit -> str | None": |
      The propagate commit message template, verbatim. None when unset.
```

`load_project_config` diff:

- Algorithm step 8 loses the topics mention — "Extract the codemanifest,
  lint, commands, tools, and usages blocks exactly as today (unchanged)".
- New algorithm step:

```yaml
    9. Extract the topics block: absent/YAML-null → topics None;
       present but not a mapping → ValueError. `base_ref` — an optional
       string (absent/YAML-null/empty/whitespace → None; non-string →
       ValueError). The create, update, and propagate sub-mappings:
       absent/YAML-null → None; present but not a mapping → ValueError;
       inside each, strategy and commit are optional strings with the
       same pattern. Unknown keys are silently ignored — the loader
       extracts known fields only; the retired publish_commit key is
       not extracted and has no effect
```

- Requirements bullet on `topics` replaced: topics is optional (None when
  absent/YAML-null; present-but-non-mapping → ValueError); `base_ref` and
  the three sub-sections are structural string checks — the strategy
  whitelists, the template grammar, and the defaults belong to the
  consuming domain.
- Constraints bullet replaced: Do NOT validate strategy values or template
  semantics at the loader level; Do NOT treat a stale
  `topics.publish_commit` value as an error — it passes through verbatim
  with no warning and no effect.
- `ProjectConfig` — the `topics` property description becomes: "The topics
  configuration of .goga/config.yml — the shared base and the operation
  sections. Instance of `TopicsConfig`, or None when the topics section is
  absent."

**`goga/config/CODEMANIFEST` diff.** One phrase of the global
annotations: "the topics fast-creation section" → "the topics section".
The `->TopicsConfig: {}` re-export is unchanged. The `goga/config/project`
import block gains the three new section types `TopicsCreateConfig`,
`TopicsUpdateConfig`, `TopicsPropagateConfig`, and the body gains their
embedding re-exports — the facade keeps embedding all project
configuration types:

```yaml
->TopicsCreateConfig: {}
->TopicsUpdateConfig: {}
->TopicsPropagateConfig: {}
```

**.usages/** — update `goga/config/.usages/project-configuration.md`
(facade-level file):

- Full-configuration example, topics section:

```yaml
topics:
  base_ref: origin/main                 # str | absent — base of the topic exchange
  create:
    commit: "Create topic '{slug}'"     # str | absent — creation todo-commit template
  update:
    strategy: merge                     # merge | rebase | ff-else-merge | ff-else-rebase
    commit: "Update topic '{slug}' from '{base}'"
  propagate:
    strategy: merge                     # merge | ff | squash
    commit: "Propagate topic '{slug}' into '{base}'"
```

- Loading Configuration behavior bullet: replace the topics bullet —
  the nested structural shape (the optional create, update, and
  propagate mapping sections with optional string strategy/commit
  keys; the retired `topics.publish_commit` silently ignored, no
  warning, no effect).
- Optional Fields table: replace the `topics` / `topics.base_ref` /
  `topics.publish_commit` rows with `topics`, `topics.base_ref`,
  `topics.create.commit`, `topics.update.strategy`,
  `topics.update.commit`, `topics.propagate.strategy`,
  `topics.propagate.commit` (all structural-only, verbatim).
- Accessors section: `config.topics.update.strategy`,
  `config.topics.propagate.commit`, … with the None-guard on each
  sub-section; behavior notes — whitelists and defaults belong to the
  consuming domain; the accessor yaml snippet is replaced by the
  nested example — the old `publish_commit` snippet disappears, so
  after the sweep only the migration note names the retired key.
- New "topics migration note" subsection: `topics.publish_commit` is no
  longer read — migrate to `topics.create.commit`; the `goga:` prefix is
  gone from the built-in defaults; stale values of the old key pass
  through silently (fresh-start 2.0 breaking-change precedent).

### Cell 3 — `goga/config/hooks` (modified)

**CODEMANIFEST diff (`goga/config/hooks/CODEMANIFEST`).**

`merge_config_amendments` — Algorithm step 1 names the section models of
the configuration type tree; the enumeration gains the three nested
topics section models: `BuildConfig`, `ReviewConfig`,
`AdditionalReviewConfig`, `PipelineConfig`, `CodemanifestConfig`,
`DepConfig`, `LintConfig`, `TopicsConfig`, `TopicsCreateConfig`,
`TopicsUpdateConfig`, `TopicsPropagateConfig`. The leaf
`topics.publish_commit` disappears together with the retired field — a
contribution still addressing it is the same unknown-path structural
failure of the contributing tool as today.

**Implementation diff (`goga/config/hooks/overlay.py`).** The hand-written
type tree and the section-default factories mirror the configuration
dataclasses and follow the reshaped model (the cross-check tests against
`dataclasses.fields` enforce the parity):

- the `TopicsConfig` node gains the three section leaves
  `create`/`update`/`propagate` (each a section of its own model) and
  loses the `publish_commit` scalar leaf;
- the new section models classify `commit` and `strategy` as scalar
  string leaves;
- the section-default factories gain the three new models
  (`TopicsCreateConfig`, `TopicsUpdateConfig`, `TopicsPropagateConfig`
  with their unset shapes) and the `TopicsConfig` factory passes
  `base_ref=None, create=None, update=None, propagate=None`.

**.usages/** — none (the cell keeps its `checkpoints` practice only).

### Cell 4 — `goga/topics/git` (modified)

**CODEMANIFEST diff (`goga/topics/git/CODEMANIFEST`).**

Header — the inline `git` practice gains this paragraph:

```yaml
    The checkout-free exchange (git >= 2.38): real three-way merges written
    as trees (merge-tree --write-tree, an explicit merge base for cherry-pick
    steps), commits built over ready trees (commit-tree), a plumbing replay
    of a commit range (rev-list of the range, one merge-tree step each,
    author and message preserved), a branch moved to a commit by a single
    update-ref, descendant checks (merge-base), the targeted fetch of one
    branch into its remote-tracking ref, a lease-protected push
    (--force-with-lease=<branch>:<tip>), and a plain push of a revision to a
    remote branch (creating it when absent). The in-place path of the
    current topic uses the real merge (never fast-forwarding, -m), the real
    rebase, and the fast-forward-only merge. Every built object stays
    dangling until the caller plants it with one ref update — atomicity by
    construction; the version gate fails on git older than 2.38.
```

Global annotations — append:

```yaml
  The exchange plumbing extends the zone: checkout-free three-way merges
  written as trees, commits over ready trees, the plumbing replay of a
  commit range with authors and messages preserved, the single-ref
  planting that keeps every exchange atomic by construction, descendant
  checks, and the git version gate (>= 2.38, a clean error naming the
  required and present versions). The bounded host-side mutations grow
  the real merge, rebase, and fast-forward of the current branch. The
  network set grows the targeted fetch of exactly one branch, the
  lease-protected push, and the revision push — beside the existing
  publication and deletion pushes. The cell stays silent: the reporting
  line of a fetch belongs to the calling module. It remains environment
  access — every decision (when to fetch, what a conflict means, when
  to roll back) belongs to the caller.
```

Body — add twelve routines (existing types stay verbatim):

```yaml
"require_git_version()":
  location: exchange.py
  annotations: |
    Gate the exchange machinery on the git version floor.

    Apply the `git` practice for the invocation pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git for its version
    2. Older than 2.38 -> a clean error naming the required and the
       present versions

    Requirements:
    - Read-only and cheap — no repository state is touched

    Constraints:
    - Do not scatter the gate over entry points — the shared base
      resolution of the domain invokes it once for every exchange

"is_ancestor(ancestor: str, descendant: str) -> contains: bool":
  location: exchange.py
  annotations: |
    Decide commit containment — whether one revision carries another.

    `ancestor`: the revision expected to be reachable
    `descendant`: the revision expected to carry it
    `contains`: True when `ancestor` is reachable from `descendant`

    Apply the `git` practice for the invocation pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git whether `ancestor` is an ancestor of `descendant`
    2. Report the answer as a plain boolean

    Requirements:
    - Read-only — no network, no mutation
    - Both sides accept any resolvable revision, peeled to its commit

    Constraints:
    - Do not decide what containment means for the caller — the policy
      belongs to the caller

"merge_tree(ours: str, theirs: str, merge_base: str | None = None) -> tree: str | None":
  location: exchange.py
  annotations: |
    Build the three-way merge of two revisions as a written tree —
    without the working copy.

    `ours`: one side of the merge
    `theirs`: the other side
    `merge_base`: the explicit merge base of a cherry-pick step; None —
                  git computes the merge base of the pair
    `tree`: the written tree of the merge, or None when the merge
            conflicts

    Apply the `git` practice for the merge-tree pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to write the merged tree of the pair — with the
       explicit base when given
    2. A conflicting merge yields None — a signal, not an error
    3. Return the written tree

    Requirements:
    - The working copy, the index, HEAD, and every ref stay untouched —
      only new objects appear, dangling until planted
    - One git invocation per merge

    Constraints:
    - Do not commit — the tree is the caller's input
    - Do not treat a conflict as an error — the caller owns the policy

"create_commit_from_tree(tree: str, parents: list[str], message: str) -> commit: str":
  location: exchange.py
  annotations: |
    Build one commit over a ready tree with its parents and the final
    message.

    `tree`: the tree oid the commit carries
    `parents`: the parent commits in order — two for a merge or a
               reconciliation, one for a squash
    `message`: the final commit message — placeholders belong to the
               caller
    `commit`: the hash of the built commit

    Apply the `git` practice for the commit-tree pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to create the commit with `message` over `tree` and
       `parents`, authored by the repository git identity
    2. Return the new commit hash; every git failure — an unreadable
       tree, an unset identity — surfaces as a clean error

    Requirements:
    - The commit stays dangling — no ref is created, moved, or deleted
    - The working copy, the index, and HEAD stay untouched

    Constraints:
    - Do not plant branches — planting belongs to the caller

"replay_commits(onto: str, until: str) -> tip: str | None":
  location: exchange.py
  annotations: |
    Replay the commits of one line onto a new base — the plumbing
    rebase of a branch, without the working copy.

    `onto`: the new base the commits replay onto
    `until`: the tip whose commits replay — the commits reachable from
             it and not from `onto`, oldest first
    `tip`: the final replayed tip, or None when a step conflicts

    Apply the `git` practice for the replay pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. List the commits reachable from `until` but not from `onto`,
       oldest first
    2. Merge each onto the running result with its parent as the
       explicit merge base, preserving the commit's author and message;
       the committer is the repository identity
    3. A conflicting step yields None
    4. Return the final tip

    Requirements:
    - Read-only w.r.t. refs — the result dangles until the caller
      plants it
    - The author and the message of every replayed commit are preserved
      verbatim
    - The pre-flight of an in-place rebase is this same call, discarded

    Constraints:
    - Do not move branches
    - Do not skip, reorder, or squash commits

"point_branch_at_commit(branch_name: str, commit: str)":
  location: exchange.py
  annotations: |
    Move a branch to a commit through a single ref update — the
    planting mutation of an exchange and the restore primitive of a
    rollback.

    `branch_name`: the short name of the existing branch
    `commit`: the commit the branch moves to

    Apply the `git` practice for the single-ref planting pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to update the branch ref to `commit`
    2. A git failure surfaces as a clean error

    Requirements:
    - Exactly one ref update — the single mutation that plants a built
      exchange result or restores a captured rollback tip
    - The working copy, the index, and HEAD stay untouched

    Constraints:
    - Do not create the branch — creation is `create_branch_at_commit`
    - Do not guard the current branch — the caller owns the checked-out
      policy

"merge_into_current(revision: str, message: str)":
  location: switch.py
  annotations: |
    Merge a revision into the current branch as a real merge commit —
    never fast-forwarding.

    `revision`: the revision to merge
    `message`: the final commit message

    Apply the `git` practice for the invocation pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to merge `revision` into the current branch with
       `message`, fast-forwarding disabled
    2. A failure surfaces as a clean error carrying the git reason

    Requirements:
    - The mutation touches the working copy, the index, and HEAD — the
      sanctioned in-place path of the current topic
    - A merge commit lands even when a fast-forward is possible

    Constraints:
    - Do not probe cleanliness — the caller does, before the call
    - Do not push

"rebase_current_onto(revision: str)":
  location: switch.py
  annotations: |
    Rebase the current branch onto a revision.

    `revision`: the new base of the current branch

    Apply the `git` practice for the invocation pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to rebase the current branch onto `revision`
    2. A failure surfaces as a clean error carrying the git reason

    Requirements:
    - The mutation touches the working copy — the sanctioned in-place
      path of the current topic
    - Git preserves the replayed commits' authors and messages

    Constraints:
    - Do not capture the pre-rebase tip — the caller does, for a
      protected push
    - Do not push

"fast_forward_current_branch(revision: str)":
  location: switch.py
  annotations: |
    Advance the current branch to a revision without a merge commit.

    `revision`: the revision to advance to

    Apply the `git` practice for the invocation pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git for the fast-forward-only merge of `revision`
    2. A non-fast-forwardable situation is a clean error

    Requirements:
    - The mutation touches the working copy; no commit is authored

    Constraints:
    - Do not fall back to a merge

"fetch_branch(branch_name: str)":
  location: publish.py
  annotations: |
    Refresh exactly one branch from origin into its remote-tracking
    ref — the targeted fetch of the exchange.

    `branch_name`: the short name of the branch to fetch

    Apply the `git` practice for the invocation pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to fetch exactly `branch_name` from origin into its
       remote-tracking ref
    2. A fetch reporting the remote branch absent reads as twin-absent
       — not an error; any other failure surfaces as a clean error
       carrying the reason

    Requirements:
    - A network operation — exactly one branch, nothing else moves
    - The working copy, the index, and HEAD stay untouched

    Constraints:
    - Do not print — the reporting line belongs to the calling module
    - Do not fetch anything beyond the named branch

"push_branch_with_lease(branch_name: str, expected_tip: str)":
  location: publish.py
  annotations: |
    Publish a rewritten branch under protection — an explicit lease
    against the expected tip.

    `branch_name`: the short name of the local branch
    `expected_tip`: the tip the remote must stand on — captured by the
                    caller immediately before the rewrite

    Apply the `git` practice for the lease pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to push the branch with a force-with-lease bound to
       `expected_tip`
    2. A remote standing anywhere else refuses — a clean error
       carrying the git reason, never an overwrite

    Requirements:
    - A network operation; the local branch stays in the repository

    Constraints:
    - Do not fetch to refresh the lease — the caller owns the expected
      value
    - Do not retry — the caller owns the failure policy

"push_revision_to_branch(revision: str, branch_name: str)":
  location: publish.py
  annotations: |
    Deliver a revision to a remote branch without a local branch — the
    write-through push.

    `revision`: the commit to deliver
    `branch_name`: the short name of the remote branch — created when
                   absent

    Apply the `git` practice for the invocation pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git to push `revision` to the remote branch, creating it
       when absent
    2. A failure surfaces as a clean error carrying the reason

    Requirements:
    - A plain push — no force, no lease; a network operation
    - No local branch is created; the working copy stays untouched

    Constraints:
    - Do not push other branches or tags — exactly the named branch
    - Do not retry — the caller owns the failure policy
```

**.usages/** — new file `goga/topics/git/.usages/exchanging.md`:

```md
# topics/git — the checkout-free exchange

How to refresh a topic from its base and deliver work into a base branch
with the `goga.topics.git` facade, without touching the working copy. For
consumers that orchestrate the topic↔base exchange: the topics domain,
higher-level orchestration.

The exchange is environment access: the cell builds trees, commits, and
moved refs — every policy decision (when to fetch, what a conflict means,
when to roll back) belongs to the caller. Objects built here stay dangling
until the caller plants them with a single ref update — atomicity by
construction.

## Gating on the git version

    from goga.topics.git import require_git_version

    require_git_version()   # older than 2.38 -> clean error naming versions

- Gate every exchange entry point; the check is cheap and read-only.

## Checking containment

    from goga.topics.git import is_ancestor

    contains = is_ancestor(base_tip, topic_tip)   # True: the topic carries the base

- Read-only, no network; both sides accept any resolvable revision.

## Pre-flighting and building a merge

    from goga.topics.git import create_commit_from_tree, merge_tree, point_branch_at_commit

    tree = merge_tree(topic_tip, base_tip)        # None -> conflicts, nothing mutated
    if tree is None:
        ...   # the caller raises its clean conflict error
    commit = create_commit_from_tree(tree, [topic_tip, base_tip], message)
    point_branch_at_commit(topic_branch, commit)  # the single planting mutation

- `merge_tree` never touches the working copy, the index, or HEAD; a
  conflict is the None signal, not an error.
- One parent list serves every shape: two parents for a merge or a base
  reconciliation, one for a squash.
- Plant last — everything before `point_branch_at_commit` mutated
  nothing.

## Replaying a topic (plumbing rebase)

    from goga.topics.git import replay_commits

    new_tip = replay_commits(base_tip, topic_tip)   # None -> a step conflicts
    if new_tip is not None:
        point_branch_at_commit(topic_branch, new_tip)

- Authors and messages of the replayed commits are preserved; capture the
  pre-replay tip beforehand when a protected push will follow.
- Read-only w.r.t. refs — the pre-flight of an in-place rebase is the
  same call, discarded.

## Moving the current branch in place

    from goga.topics.git import fast_forward_current_branch, merge_into_current, rebase_current_onto

    merge_into_current(base_tip, message)   # a real merge commit, never ff
    rebase_current_onto(base_tip)           # a real rebase
    fast_forward_current_branch(base_tip)   # ff-only, a clean error otherwise

- These touch the working copy — probe cleanliness first, and run them
  only after a read-only pre-flight; they never replace it.

## Refreshing and delivering over the network

    from goga.topics.git import fetch_branch, push_branch, push_branch_with_lease, push_revision_to_branch

    fetch_branch("main")                                   # the single sanctioned fetch
    push_branch("main")                                    # plain, binds upstream, creates when absent
    push_branch_with_lease(topic_branch, pre_rebase_tip)   # the protected rewrite
    push_revision_to_branch(commit, "main")                # write-through, no local branch

- Report each fetch with one stdout line before it runs — the reporting
  belongs to the caller; the cell stays silent.
- The lease binds to the tip captured immediately before the rewrite; a
  remote standing anywhere else refuses with git's reason.
```

### Cell 5 — `goga/topics/hooks` (modified)

**CODEMANIFEST diff (`goga/topics/hooks/CODEMANIFEST`).**

Header unchanged. Global annotations: the zone sentence counts change —
"the read-only notification contexts of the five moments" → "of the seven
moments"; "the seven topics actions are soft" → "the nine topics actions
are soft"; append:

```yaml
  The update and propagate moments are notification-only soft events —
  no new amendments exist. An idempotent outcome emits its event; a
  declined confirmation emits nothing. The propagate context carries no
  pushed flag — the push is inherent and the flag would carry no
  information.
```

Body — add two contexts and two methods:

```yaml
"TopicUpdated(identity: TopicIdentity, base: str, effective_tip: str, strategy: str, outcome: str, published: bool)":
  location: contexts.py
  annotations: |
    The read-only context of the update notification — the final facts
    of one completed update.

    `identity`: the identity of the updated topic
    `base`: the base name as addressed by the operation
    `effective_tip`: the effective tip commit the topic was brought to
    `strategy`: the validated strategy name as configured — merge,
                rebase, ff-else-merge, or ff-else-rebase; the realized
                kind is the `outcome`
    `outcome`: the outcome kind — exactly one of merged, rebased,
               fast-forwarded, already-current
    `published`: True when the update published the refreshed branch

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a completed operation — a hook observes the
      outcome and cannot alter it
    - The idempotent already-current outcome emits like any other
  properties:
    "identity -> TopicIdentity": |
      The identity of the updated topic.
    "base -> str": |
      The base name as addressed by the operation.
    "effective_tip -> str": |
      The effective tip commit the topic was brought to.
    "strategy -> str": |
      The validated strategy name as configured — merge, rebase,
      ff-else-merge, or ff-else-rebase; the realized kind is the
      `outcome`.
    "outcome -> str": |
      The outcome kind — merged, rebased, fast-forwarded, or
      already-current.
    "published -> bool": |
      True when the update published the refreshed branch.

"TopicPropagated(identity: TopicIdentity, base: str, strategy: str, outcome: str)":
  location: contexts.py
  annotations: |
    The read-only context of the propagate notification — the final
    facts of one completed delivery.

    `identity`: the identity of the propagated topic
    `base`: the target base name as addressed by the operation
    `strategy`: the applied strategy — merge, ff, or squash
    `outcome`: the outcome kind — exactly one of merged,
               fast-forwarded, squashed, nothing-to-do

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a completed operation
    - No pushed flag — the push is inherent to every propagate
    - The idempotent nothing-to-do outcome emits like any other
  properties:
    "identity -> TopicIdentity": |
      The identity of the propagated topic.
    "base -> str": |
      The target base name as addressed by the operation.
    "strategy -> str": |
      The applied strategy.
    "outcome -> str": |
      The outcome kind — merged, fast-forwarded, squashed, or
      nothing-to-do.
```

`TopicHooks` — the type annotation counts "the five notification
emissions" → "the seven notification emissions"; add two methods:

```yaml
    "emit_updated(identity: TopicIdentity, base: str, effective_tip: str, strategy: str, outcome: str, published: bool)":
      Emit the update notification — the facts of one completed
      update.

      `identity`: the identity of the updated topic
      `base`: the base name as addressed
      `effective_tip`: the effective tip commit
      `strategy`: the validated strategy name as configured
      `outcome`: merged, rebased, fast-forwarded, or already-current
      `published`: True when the update published the refreshed branch

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicUpdated` context from the values
      2. Emit the address domain="topics", action="topic_updated"
         via `emit_hook_event` — the context view of every receiving
         tool reads the same instance through the delivery proxy

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - A failing hook is skipped with a warning under the soft error
        class of the action

    "emit_propagated(identity: TopicIdentity, base: str, strategy: str, outcome: str)":
      Emit the propagate notification — the facts of one completed
      delivery.

      `identity`: the identity of the propagated topic
      `base`: the target base name as addressed
      `strategy`: the applied strategy
      `outcome`: merged, fast-forwarded, squashed, or nothing-to-do

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicPropagated` context from the values
      2. Emit the address domain="topics", action="topic_propagated"
         via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - A failing hook is skipped with a warning under the soft error
        class of the action
```

**.usages/** — update `goga/topics/hooks/.usages/checkpoints.md`: the
emission section counts five → seven notifications; add the two emission
examples and bullets:

```md
hooks.emit_updated(identity, base="main", effective_tip=tip, strategy="merge", outcome="merged", published=True)
hooks.emit_propagated(identity, base="main", strategy="squash", outcome="squashed")
```

- `topic_updated` — `TopicUpdated`: `identity`, `base`, `effective_tip`,
  `strategy` (merge / rebase / ff-else-merge / ff-else-rebase — the
  configured name; the realized kind is the outcome), `outcome` (merged /
  rebased / fast-forwarded / already-current), `published`. The
  idempotent already-current outcome emits like any other.
- `topic_propagated` — `TopicPropagated`: `identity`, `base`,
  `strategy`, `outcome` (merged / fast-forwarded / squashed /
  nothing-to-do). No pushed flag — the push is inherent; nothing-to-do
  emits.
- Both fire-and-forget under the soft error class; a declined propagate
  confirmation emits nothing.

### Cell 6 — `goga/topics` (modified)

**CODEMANIFEST diff (`goga/topics/CODEMANIFEST`).**

Header — the `goga/topics/git` import block gains the types
`require_git_version`, `is_ancestor`, `merge_tree`,
`create_commit_from_tree`, `replay_commits`, `point_branch_at_commit`,
`merge_into_current`, `rebase_current_onto`, `fast_forward_current_branch`,
`fetch_branch`, `push_branch_with_lease`, `push_revision_to_branch` and
the usage `exchanging`.

Global annotations — replace the superseded network sentence ("Mutations
are local-only except the two pushes — publication and deletion; no fetch
ever happens.") with:

```yaml
  The sanctioned network set is exact: the targeted fetch of the
  operation's own refs (each reported by one stdout line before it
  runs), the push inherent to every propagate, the explicit update
  publish push (plain or lease-protected), and the existing publication
  and deletion pushes; nothing else ever fetches, and the board never
  touches the network.
```

and append the exchange paragraph:

```yaml
  The domain grows the topic↔base exchange: the update and propagate
  operations, the shared logical-branch base resolution — one targeted
  reported fetch, the descendant-of-pair effective tip, the
  reconciliation merge written onto the local base branch and never
  pushed — and the board divergence marker computed from local refs
  without network.
```

Body — add ten types:

```yaml
"ExchangeBase(name: str, tip: str, local_branch: str | None, reconciled: bool)":
  location: exchange.py
  annotations: |
    One resolved logical branch base — the shared resolution result of
    the exchange operations.

    `name`: the base as addressed — the revision string the operation
            resolved from
    `tip`: the effective tip commit of the logical branch
    `local_branch`: the local branch of the base, or None when the base
                    is remote-only or a tag/hash
    `reconciled`: True when the resolution wrote a reconciliation merge
                  onto the local base branch

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "name -> str": |
      The base as addressed by the operation.
    "tip -> str": |
      The effective tip commit of the logical branch — the descendant
      of the local/origin pair, the reconciliation commit of a diverged
      pair, the single projection's tip, or the commit a tag or hash
      resolves to.
    "local_branch -> str | None": |
      The local branch of the base, or None when remote-only or
      tag/hash.
    "reconciled -> bool": |
      True when the resolution wrote a reconciliation merge onto the
      local base branch.

"resolve_exchange_base(base_ref: str, own_branch: str, own_tip: str) -> base: ExchangeBase":
  location: exchange.py
  annotations: |
    Resolve the base as one logical branch — the shared machinery of
    the update and propagate operations.

    `base_ref`: the base revision string as resolved by the caller
    `own_branch`: the topic's own branch name — the self-base oracle
    `own_tip`: the topic's own branch tip — the idempotency oracle
    `base`: the resolved `ExchangeBase`

    Apply the `exchanging` practice for the fetch, containment, and
    reconciliation patterns.
    Apply the `refs-and-switching` practice for the inventory and
    revision-resolution patterns.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. `require_git_version` — the exchange gate fires here, once for
       every caller
    2. A `base_ref` naming the `own_branch` — bare or origin-twin form
       — is a clean error: the topic is its own base
    3. A local branch `base_ref` or its origin twin exists -> the
       branch-shaped base; otherwise resolve `base_ref` as a revision —
       a tag or a hash — read-only with no fetch; an unresolvable base
       is a clean error carrying the git reason
    4. The branch-shaped base: echo one stdout line
       Fetching origin/<base>... then `fetch_branch`; a fetch reporting
       the remote branch absent leaves the twin absent — the local
       projection stands alone; any other fetch failure is a clean
       error
    5. The projections: the local tip and the twin tip as they exist
       after the fetch; one projection alone -> it is the effective tip
    6. Both projections: one containing the other via `is_ancestor` ->
       the descendant is the effective tip
    7. The projections diverged: `own_tip` containing every projection
       -> the effective tip is `own_tip` itself and nothing is written
       — the already-carried state; otherwise the reconciliation —
       `merge_tree` of the pair, a conflict is a clean error asking to
       reconcile the branch manually with nothing mutated, a tree is
       committed via `create_commit_from_tree` with the fixed message
       Reconcile base '<name>' and planted onto the local base branch
       via `point_branch_at_commit` — the reconciliation commit is the
       effective tip

    Requirements:
    - Exactly one fetch per resolution, reported before it runs —
      branch-shaped bases only; a tag or hash base never fetches
    - The already-carried check precedes the reconciliation write — an
      up-to-date topic mutates nothing at all
    - The reconciliation lands only on the local base branch and is
      never pushed by the resolution itself
    - Atomicity: the reconciliation is the only mutation — built
      objects dangle until the single ref update

    Constraints:
    - Do not decide the strategy — the caller applies it to `tip`
    - Do not resolve a base for a topic without its own branch — the
      caller resolves the addressee first

"ExchangeTarget(topic: str, branch: str, current: bool)":
  location: exchange.py
  annotations: |
    One addressed topic of an exchange operation.

    `topic`: the topic slug
    `branch`: the own branch name — local form; a remote-only own
              branch is refused by the resolution
    `current`: True when the own branch hosts the current working
               branch

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "topic -> str": |
      The topic slug of the addressed topic.
    "branch -> str": |
      The own branch name of the addressed topic.
    "current -> bool": |
      True when the own branch hosts the current working branch.

"resolve_exchange_target(identifier: str | None, year: str | None = None) -> target: ExchangeTarget":
  location: exchange.py
  annotations: |
    Resolve the addressee of an exchange operation — the current topic
    when the identifier is omitted, the identified one otherwise.

    `identifier`: the user input — a branch name, a topic slug, or
                  their prefix; None addresses the current topic
    `year`: optional year as four digits; None means the current year
    `target`: the addressed `ExchangeTarget`

    Apply the `click` practice for the numbered candidate selection
    and the non-interactive detection.
    Apply the `topic-paths` practice for the slug and current-branch
    patterns.
    Apply the `refs-and-switching` practice for the inventory pattern.

    Algorithm:
    1. `identifier` None -> the current branch via
       `resolve_current_branch_name`; a branch hosting no topic is a
       clean error naming the branch; the hosted topic of the branch
       is the addressee
    2. Otherwise resolve the switch tiers via
       `resolve_switch_candidates`; none -> a clean error with a hint
       to the board; several -> the numbered list with statuses and
       the number prompt, or the failure with the list without
       interactive input
    3. The chosen candidate whose own branch exists only as a
       remote-tracking ref is a clean error hinting `goga topics
       switch` first
    4. Mark the current branch and return the target with the local
       branch name

    Requirements:
    - Read-only — nothing is mutated before the operation itself
    - The remote-only refusal fires here for both exchange operations

    Constraints:
    - Do not switch — the operations work without checkout

"render_commit_template(template: str, slug: str, base: str) -> message: str":
  location: exchange.py
  annotations: |
    Render a commit message from a template — the single template
    engine of the domain's authored messages.

    `template`: the message template
    `slug`: the topic slug
    `base`: the base name as addressed
    `message`: the rendered message

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Replace {slug} with `slug` and {base} with `base`
    2. Unknown placeholders stay verbatim
    3. Return the message — no other transformation

    Requirements:
    - Pure text transformation — no repository reads

"update_topic(identifier: str | None, base_ref: str, strategy: str | None, commit_message: str | None, publish: bool = False, year: str | None = None) -> result: str":
  location: updating.py
  annotations: |
    Bring a topic up to its base — the update operation of the domain.

    `identifier`: the addressee input; None addresses the current
                  topic
    `base_ref`: the base revision string as resolved by the caller
    `strategy`: the strategy name from topics.update.strategy — None
                applies the built-in default merge; an invalid value is
                a clean configuration error naming the key
    `commit_message`: the message template from topics.update.commit —
                      None applies the built-in default
                      Update topic '{slug}' from '{base}'
    `publish`: True pushes the refreshed branch after success
    `year`: optional year as four digits; None means the current year
    `result`: one line describing the outcome — the addressee, the
              base, the strategy, and the outcome

    Apply the `exchanging` practice for the build, plant, and push
    patterns.
    Apply the `refs-and-switching` practice for the tip-resolution
    pattern.
    Apply the `publishing` practice for the publication push pattern.
    Apply the `checkpoints` practice for the update notification.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Validate `strategy` against merge, rebase, ff-else-merge,
       ff-else-rebase — an invalid value is a clean configuration
       error naming topics.update.strategy, before anything else
    2. Resolve the addressee via `resolve_exchange_target`
    3. Resolve the own tip via `resolve_ref_commit`
    4. When `base_ref` names a local branch, capture its current tip as
       the rollback tip — before the resolution may write a
       reconciliation onto it; resolve the base via
       `resolve_exchange_base` — the version gate, the reported fetch,
       the effective tip, a possible reconciliation
    5. `is_ancestor` reporting the effective tip contained in the own
       tip -> the already-current idempotent success: emit topic_updated
       over `TopicHooks` — the identity via `TopicIdentity`, the base
       name, the effective tip, the configured strategy name, the
       outcome already-current, published False — and return the line;
       `publish` publishes nothing in this case
    6. The ff decision: an ff-else-* strategy with the effective tip
       containing the own tip — the topic has no own work — takes the
       fast-forward; otherwise the named base strategy applies
    7. The current topic: probe `is_working_tree_clean` — a dirty tree
       is a clean error before any mutation; pre-flight read-only —
       merge via `merge_tree` of the own tip with the effective tip,
       rebase via `replay_commits` of the own line onto the effective
       tip — a conflict is a clean error suggesting manual git with
       nothing mutated and the base's local branch restored to the
       captured pre-resolution tip when the resolution wrote a
       reconciliation; then the real mutation: `merge_into_current` with the
       effective tip and the rendered `render_commit_template` message
       — the template or the built-in default
       Update topic '{slug}' from '{base}',
       or `rebase_current_onto` with the effective tip, or
       `fast_forward_current_branch` with the effective tip
    8. Another topic — fully checkout-free: merge -> `merge_tree` -> a
       tree becomes a two-parent commit of the own tip and the
       effective tip via `create_commit_from_tree` with the rendered
       message, planted via `point_branch_at_commit` on the addressee's
       branch; rebase -> `replay_commits` onto the effective tip ->
       `point_branch_at_commit` on the addressee's branch;
       fast-forward -> `point_branch_at_commit` of the addressee's
       branch at the effective tip — no commit authored
    9. `publish`: `origin_configured` reads False -> a clean error;
       merge or fast-forward -> `push_branch` of the addressee's
       branch; rebase -> an origin twin exists ?
       `push_branch_with_lease` with the addressee's branch and the
       pre-rebase own tip : `push_branch` of the addressee's branch; a
       failed publish push leaves the confirmed update standing and
       surfaces git's reason as a clean error — the single atomicity
       exception
    10. Emit topic_updated over `TopicHooks` — the identity, the base
        name, the effective tip, the configured strategy name, the
        outcome merged, rebased, or fast-forwarded, the published
        flag — and return the single result line

    Requirements:
    - No confirmation is asked
    - Every conflict is detected read-only before any topic mutation —
      a conflicted update leaves the repository at its pre-operation
      state: a reconciliation the resolution wrote is rolled back to
      the captured pre-resolution tip of the base's local branch via
      `point_branch_at_commit`
    - The in-place path never runs without its pre-flight; the
      checkout-free paths are atomic by construction — objects dangle
      until the single ref update
    - The rebase lease binds to the own tip immediately before the
      rebase, with no extra fetch of the topic twin
    - The result is exactly one line and names the addressee

    Constraints:
    - Do not rewrite history beyond the topic's own branch under the
      configured rebase
    - Do not push without `publish`

"PropagationPlan(target: ExchangeTarget, base_ref: str, strategy: str, message: str, year: str)":
  location: propagating.py
  annotations: |
    The resolved propagation — the self-contained plan the caller
    confirms and executes.

    `target`: the addressed `ExchangeTarget`
    `base_ref`: the base revision string as resolved by the caller
    `strategy`: the validated strategy — merge, ff, or squash
    `message`: the rendered commit message
    `year`: the resolved year of the operation

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "target -> ExchangeTarget": |
      The addressed topic of the delivery.
    "base_ref -> str": |
      The base revision string the delivery targets.
    "strategy -> str": |
      The validated delivery strategy.
    "message -> str": |
      The rendered commit message of the delivery commit.
    "year -> str": |
      The resolved year of the operation.

"resolve_propagation(identifier: str | None, base_ref: str, strategy: str | None, commit_message: str | None, year: str | None = None) -> plan: PropagationPlan":
  location: propagating.py
  annotations: |
    Resolve the delivery read-only — every decision before the
    confirmation and before any mutation, the network included.

    `identifier`: the addressee input; None addresses the current
                  topic
    `base_ref`: the base revision string as resolved by the caller
    `strategy`: the strategy name from topics.propagate.strategy —
                None applies the built-in default merge; an invalid
                value is a clean configuration error naming the key
    `commit_message`: the message template from
                      topics.propagate.commit — None applies the
                      built-in default
    `year`: optional year as four digits; None means the current year
    `plan`: the resolved `PropagationPlan`

    Apply the `topic-paths` practice for the slug and current-branch
    patterns.
    Apply the `refs-and-switching` practice for the inventory pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Validate `strategy` against merge, ff, squash — an invalid
       value is a clean configuration error naming
       topics.propagate.strategy
    2. Resolve the addressee via `resolve_exchange_target`
    3. `origin_configured` reads False -> a clean error before any
       mutation — the push is inherent, the remote must exist
    4. The local branch named `base_ref` being the current branch —
       read via `resolve_current_branch_name` — is a clean error
       asking to switch away first
    5. Render `message` via `render_commit_template` — the template or
       the built-in default Propagate topic '{slug}' into '{base}'
    6. Return the plan

    Requirements:
    - Fully read-only — no fetch, no ref write, no working-copy touch:
       a declined confirmation performs nothing at all
    - The ff fast-forwardability is verified authoritatively at
       execution against the effective tip

    Constraints:
    - Do not confirm — the confirmation belongs to the caller

"execute_propagation(plan: PropagationPlan) -> result: str":
  location: propagating.py
  annotations: |
    Execute the confirmed delivery — build, plant, push, with one
    retry cycle and a uniform full rollback.

    `plan`: the resolved plan — the caller has confirmed it
    `result`: one line describing the outcome — the topic, the target
              base, the strategy, and the outcome

    Apply the `exchanging` practice for the build, plant, fetch, and
    push patterns.
    Apply the `refs-and-switching` practice for the tip-resolution
    pattern.
    Apply the `checkpoints` practice for the propagate notification.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Resolve the own tip via `resolve_ref_commit`; when the base
       names a local branch, capture its current tip as the rollback
       tip — before the resolution may write a reconciliation onto it
    2. Resolve the base via `resolve_exchange_base` — the version gate,
       the reported fetch, the effective tip, a possible
       reconciliation; the base's local branch being the current branch
       is a clean error asking to switch away first
    3. `is_ancestor` reporting the own tip contained in the effective
       tip -> the nothing-to-do idempotent success: emit
       topic_propagated — the identity via `TopicIdentity`, the base
       name, the strategy, the outcome nothing-to-do — and return the
       line; a reconciliation written by the resolution stands as
       sanctioned base bookkeeping
    4. Build the delivery: merge -> `merge_tree` of the effective tip
       with the own tip -> a two-parent commit via
       `create_commit_from_tree` with the plan's message; squash ->
       the same tree over the single parent — the effective tip — one
       squashed commit; ff -> the effective tip must be contained in
       the own tip via `is_ancestor` — a non-fast-forwardable
       situation is a clean error suggesting manual git, with nothing
       planted and the rollback unnecessary; otherwise the delivery is
       the own tip, no commit authored; a conflict is a clean error
       suggesting manual git.
       The delivery tree equal to the effective tip's tree — the base
       already carries the topic's state by content — is the
       second, content-based form of the nothing-to-do idempotent
       success: a reconciliation the resolution wrote stands as
       sanctioned base bookkeeping, the event emits with the outcome
       nothing-to-do, and nothing is planted or pushed
    5. Plant: the base's local branch exists ->
       `point_branch_at_commit` of the base's local branch at the
       delivery commit; a remote-only base plants nothing locally —
       the write-through
    6. Push — inherent: the local path pushes via `push_branch` of the
       base's local branch, creating the remote branch when absent;
       the write-through pushes via `push_revision_to_branch` with the
       delivery commit and the base name
    7. A push rejected for concurrent remote movement gets one retry
       cycle — the reported `fetch_branch`, the re-resolved effective
       tip, the rebuilt delivery, the re-plant, the re-push; a second
       rejection is a clean error
    8. Every failure rolls back fully — the base's local branch
       returns to the captured pre-resolution tip via
       `point_branch_at_commit`, removing a reconciliation the
       resolution wrote
    9. Emit topic_propagated — the identity, the base name, the
       strategy, the outcome merged, fast-forwarded, or squashed
    10. Return the single result line

    Requirements:
    - Always checkout-free — the working copy, the index, and HEAD are
      never touched
    - Idempotency is content-based — both the commit-reachability form
      (step 3) and the identical-delivery-tree form (step 4) are the
      nothing-to-do success and emit like any other
    - The topic stays alive — its branch and directory are untouched
    - Failure atomicity is uniform — a conflict or a failed push
      leaves the pre-operation state
    - The retry cycle runs exactly once

    Constraints:
    - Do not re-resolve the addressee — the plan carries it
    - Do not clean the topic up — clear stays separate

"resolve_divergence(own_tip: str, base_ref: str | None) -> marker: str | None":
  location: board.py
  annotations: |
    Compute the board's binary divergence marker — read-only, from
    local refs, without network.

    `own_tip`: the own-branch tip commit of the topic
    `base_ref`: the configured base revision string; None renders no
                marker
    `marker`: behind, current, or None when the base is unconfigured
              or unresolvable

    Apply the `refs-and-switching` practice for the inventory and
    revision-resolution patterns.
    Apply the `exchanging` practice for the containment pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. `base_ref` None -> None
    2. The available projections of the base — the local branch tip
       and the twin tip, each as it exists locally, no fetch; a
       tag or hash base resolves to its commit; an unresolvable base
       -> None — never an error
    3. `own_tip` containing every projection via `is_ancestor` ->
       current; otherwise behind

    Requirements:
    - Read-only — no fetch, no mutation, never a failure
    - The rule matches the exchange's already-carried rule — current
      means the topic carries every projection the base offers

    Constraints:
    - Do not reconcile — divergence of the base pair reads as behind
      until an update converges it
```

Body — modify six types:

- `BoardRecord` — add the optional constructor field
  `divergence: str | None = None` and the property
  `"divergence -> str | None"`: the topic's own-branch divergence marker
  (behind / current), None when unconfigured or unresolvable.
- `BoardEntry` — the same optional field and property, projected from
  the winning own-branch record.
- `collect_topic_board` — add the parameter
  `base_ref: str | None = None`; extend the Algorithm with: the
  divergence marker of every own-branched topic is computed in this
  single collection pass via `resolve_divergence` from its own-branch
  tip; Requirements: the collection never fetches and never fails on an
  unconfigured or unresolvable base — the marker stays None.
- `aggregate_topic_board` — Requirements bullet: the divergence of the
  winning own-branch record projects into the entry; Algorithm step 5
  gains the divergence marker among the winner's projected facts.
- `create_topic` — Requirements: the built-in default message template
  is `Create topic '{slug}'`; template rendering runs through
  `render_commit_template` with the {slug} and {base} placeholders,
  unknown placeholders verbatim.
- `publish_topic` — the same template semantics (the template source is
  the create-section key resolved by the caller).

**.usages/** — two new files, four updates.

New `goga/topics/.usages/update.md`:

```md
# topics — updating a topic from its base

How to refresh a topic with its base's changes through the `goga.topics`
facade. For consumers that keep long-lived topics current: the topics
command group, higher-level orchestration.

`update_topic` resolves the addressee (the current topic when the
identifier is omitted), resolves the base as one logical branch, and
applies the configured strategy. The strategy and the commit-message
template come from `topics.update.strategy` and `topics.update.commit`
(the caller passes them; the built-in defaults live here — the message
default is `Update topic '{slug}' from '{base}'`). No confirmation is
asked.

## Updating

    from goga.topics import update_topic

    result = update_topic(None, "main")                        # the current topic, default strategy
    result = update_topic("feat-x", "main", strategy="rebase", publish=True)
    print(result)  # one line: the topic, the base, the strategy, the outcome

- The base is one logical branch: a bare name and its origin twin denote
  the same base; the targeted fetch is reported by one stdout line
  before it runs; the effective tip is the descendant of the pair, a
  reconciliation merge written onto the local base branch when they
  diverge (fixed message, never pushed, skipped when the topic already
  carries every projection), the single projection's tip, or the commit
  a tag or hash resolves to.
- The current topic updates in place: a dirty tree is a clean error
  before any mutation, and the real merge/rebase/fast-forward runs only
  after a read-only pre-flight of the same computation.
- Any other topic updates fully checkout-free: the merge (or replay) is
  built on git plumbing and planted by a single ref update — a failure
  leaves the repository exactly as it was.
- A topic already at the effective tip is an idempotent success:
  nothing is mutated, the reconciliation included; `publish` publishes
  nothing in that case.
- Strategies: `merge` (a merge commit, never rewriting the topic),
  `rebase` (the topic's commits replayed, author and message
  preserved), `ff-else-merge` / `ff-else-rebase` (fast-forward when the
  topic has no own work, otherwise the named strategy). An invalid
  value is a clean configuration error naming the key.
- `publish=True` pushes the refreshed branch after success: a plain
  push after a merge, a protected force-with-lease against the
  pre-rebase tip after a rebase when the branch has an origin twin. A
  failed publish push leaves the confirmed update standing — the single
  atomicity exception.
- Every conflict is detected read-only before any mutation and is a
  clean error suggesting manual git.
- The result line always names the addressee, the base, the strategy,
  and the outcome.
```

New `goga/topics/.usages/propagate.md`:

```md
# topics — propagating a topic into its base

How to deliver a topic's finished work into its base branch through the
`goga.topics` facade. For consumers that land finished work: the topics
command group, higher-level orchestration.

`resolve_propagation` resolves everything read-only (the addressee, the
strategy from `topics.propagate.strategy`, the message from
`topics.propagate.commit`); `execute_propagation` performs the
confirmed delivery. The push is inherent — there is no publish flag:
a local base receives the result on the local branch and is pushed to
origin (the remote branch is created when absent); a remote-only base
is written through.

## Propagating

    from goga.topics import execute_propagation, resolve_propagation

    plan = resolve_propagation("feat-x", "main")
    ...  # the caller confirms: the target and the inherent push
    result = execute_propagation(plan)
    print(result)  # one line: the topic, the target base, the strategy, the outcome

- The operation is always checkout-free: the working copy, the index,
  and HEAD are untouched; propagating into the currently checked-out
  branch is a clean error asking to switch away first.
- Strategies: `merge` (a merge commit on the effective tip), `ff`
  (fast-forward only; a non-fast-forwardable situation is a clean
  error), `squash` (one squashed commit carries the topic's work). An
  invalid value is a clean configuration error naming the key.
- A base that already carries the topic's current state is an
  idempotent nothing-to-do success — carried means content, never the
  mere presence of the topic directory.
- A push rejected because the remote moved concurrently gets one retry
  cycle (fetch, rebuild, push); a second rejection is a clean error.
- Failure atomicity is uniform: a conflict or a failed push rolls
  everything back to the pre-operation state.
- The topic stays alive after the delivery: its branch and directory
  are untouched; cleanup remains the separate clear.
- A declined confirmation performs nothing — resolve, confirm, and
  execute are separate steps.
```

Updates:

- `goga/topics/.usages/topic-board.md` — `collect_topic_board` gains
  `base_ref`; records and entries carry `divergence` (behind / current /
  None); the marker is computed from local refs without network and
  never fails on an unconfigured or unresolvable base; the JSON
  projection carries the `divergence` key.
- `goga/topics/.usages/creating.md` — the template key is
  `topics.create.commit`; the built-in default is
  `Create topic '{slug}'`; the placeholders are {slug} and {base}.
- `goga/topics/.usages/publishing.md` — the same template semantics;
  the `goga:` prefix phrasing removed.
- `goga/topics/.usages/registering-hooks.md` — the events table gains
  `topics / topic_updated` (after a completed update — the idempotent
  already-current outcome included) and `topics / topic_propagated`
  (after a completed delivery — nothing-to-do included); the context
  descriptions (`TopicUpdated`, `TopicPropagated`); the no-pushed-flag
  note; the intro counts change — the domain opens nine soft actions,
  seven of them notifications.

### Cell 7 — `goga/commands/topics` (modified)

**CODEMANIFEST diff (`goga/commands/topics/CODEMANIFEST`).**

Header — the `goga/topics` import block gains the types `update_topic`,
`resolve_propagation`, `execute_propagation` and the usages `update`,
`propagate`.

Global annotations — append:

```yaml
  The update and propagate subcommands resolve their inputs at this
  layer: the base — a flag beats the topics section of the effective
  configuration, with no current-HEAD rung; the strategy and the
  message template pass through verbatim from the nested topics keys —
  the whitelists and the defaults live in the domain; update asks no
  confirmation, propagate asks exactly one — naming the target and the
  inherent push — with the --yes escape.
```

Body — the `topics` group gains two subcommand surfaces (the existing
Subcommand surfaces list gains: update — an optional IDENTIFIER
positional, a --base-ref option, a --publish/-p flag; propagate — an
optional IDENTIFIER positional, a --base-ref option, a --yes/-y flag)
and two methods:

```yaml
    "update(identifier: str | None = None, base_ref: str | None = None, publish: bool = False) -> exit_code: int":
      Subcommand goga topics update: bring a topic up to its base —
      the current topic when IDENTIFIER is omitted, the identified one
      otherwise; --publish/-p pushes the refreshed branch after
      success.

      `identifier`: IDENTIFIER positional — a branch name, a topic
                    slug, or their prefix; omitted addresses the
                    current topic
      `base_ref`: the --base-ref value — the base of the update
      `publish`: the --publish/-p flag — push the refreshed branch
      `exit_code`: 0 on success (an already-current topic included), 1
                   on error

      Apply the `update` practice for the update contract of the
      domain.
      Apply the `project-configuration` practice for the topics
      section schema.
      Apply the `checkpoints` practice for the config amendment
      checkpoint at the configuration load moment.
      Apply the `click` practice for the options, echo, and exit-code
      propagation.

      Algorithm:
      1. Resolve the base — `base_ref`, otherwise topics.base_ref of
         the effective configuration of the `ConfigOverlay` (loaded
         via `load_project_config`; the configuration load delivers
         the config amendment checkpoint per the `checkpoints`
         practice); no base at all -> clean error naming the flag and
         the configuration line, before anything else
      2. Resolve the strategy source — topics.update.strategy of the
         effective configuration, verbatim; None stays None (the
         built-in default lives in the domain)
      3. Resolve the message template — topics.update.commit,
         verbatim
      4. Delegate to `update_topic` with the identifier, the base, the
         strategy source, the template, `publish`, and the scoped year
      5. Echo the single result line
      6. Propagate the exit code

      Requirements:
      - The configuration is read only for values no flag provided; a
         missing configuration file counts as an unset value
      - The amendment summary lines of the `ConfigOverlay` print to
         stderr (nothing when empty)
      - The --help text names the addressee rule explicitly

      Constraints:
      - Do not validate the strategy here — the domain owns the
        whitelist and its configuration error
      - Do not ask a confirmation

    "propagate(identifier: str | None = None, base_ref: str | None = None, yes: bool = False) -> exit_code: int":
      Subcommand goga topics propagate: deliver a topic's finished
      work into its base — the push to origin is inherent, there is no
      publish flag; exactly one confirmation names the target and the
      push.

      `identifier`: IDENTIFIER positional — omitted addresses the
                    current topic
      `base_ref`: the --base-ref value — the target base
      `yes`: the --yes/-y flag — skip the confirmation
      `exit_code`: 0 on success (a nothing-to-do delivery and a
                   declined confirmation included), 1 on error

      Apply the `propagate` practice for the propagation contract of
      the domain.
      Apply the `project-configuration` practice for the topics
      section schema.
      Apply the `checkpoints` practice for the config amendment
      checkpoint at the configuration load moment.
      Apply the `click` practice for the confirmation, echo, and
      exit-code propagation.

      Algorithm:
      1. Resolve the base and the sources exactly as the update
         subcommand — `base_ref`, otherwise topics.base_ref; the
         strategy from topics.propagate.strategy and the template from
         topics.propagate.commit, verbatim
      2. Resolve the plan via `resolve_propagation` with the
         identifier, the base, the strategy source, the template, and
         the scoped year
      3. Without `yes`: no interactive terminal -> clean error;
         otherwise ask one confirmation naming the topic, the target
         base, and the push; a declined answer exits 0 with nothing
         done
      4. Delegate to `execute_propagation` with the plan
      5. Echo the single result line
      6. Propagate the exit code

      Requirements:
      - The -y short form collides with the group --year; the
        positions on the command line distinguish them
      - One confirmation — naming the target and the inherent push

      Constraints:
      - Do not compute the delivery here — the resolution and the
        execution belong to the domain
```

The `board` method — the Algorithm gains a first step before the
views: load the configuration the way `clear` does (`load_project_config`;
the configuration load delivers the config amendment checkpoint per the
`checkpoints` practice; the amendment summary lines print to stderr,
nothing when empty) and pass the resolved `topics.base_ref` of the
effective configuration into `collect_topic_board` (no flag exists;
the board reads the configuration only); the view and render steps
stay verbatim. Requirements addition: a missing configuration file
counts as an unset value — the divergence stays None and the board
renders with empty Base cells, never an error.

Renderer diffs (`render.py`):

- `render_topic_board` — under `info` the table gains the Base column:
  the header sentence, the `info` parameter annotation ("adds the todo
  and base columns and switches to the six-column width rule"), the
  Algorithm column-order sentence (topic, branch, hosts, todo, base,
  statuses under `info`), and the info-width Requirements bullet are
  replaced — the five-column rule becomes the six-column rule: topic,
  branch, hosts, todo, and base get an equal share (each capped at one
  sixth of `width` minus the dividers), statuses receives the
  non-negative remainder, every column keeps a minimum of 8 before
  truncation; the marker is behind or current, an empty cell when the
  divergence is None; the column header is the word Base beside the
  words Hosts and Todo.
- `render_topic_host_rows` — the same replacement shape: the header
  sentence (under `info` the todo and base columns sit between branch
  and statuses), the `info` parameter annotation (the five-column
  rule), the Algorithm column order (topic, branch, todo, base,
  statuses under `info`), and the four-column info-width bullet becomes
  the five-column rule — topic, branch, todo, and base get an equal
  share (each capped at one fifth of `width` minus the dividers),
  statuses the remainder, minimum 8; the column header is the word
  Base.
- `render_board_json` — Requirements addition: every record carries the
  `divergence` key — behind, current, or null when unresolved; always
  present, never omitted — an additive change to the stable record
  contract.

**.usages/** — update `goga/commands/topics/.usages/topics-command.md`:

- Intro enumeration gains update and propagate.
- Boarding section: column order under `--info` becomes topic, branch,
  hosts, todo, base, statuses; the marker — behind / current against
  `topics.base_ref`, an empty cell when unconfigured or unresolvable;
  the board never fetches and never fails on the base.
- Per-host section: order topic, branch, todo, base, statuses.
- JSON section: records carry `divergence` (behind | current | null) in
  both views.
- Creating/publishing section: `--commit/-c (topics.create.commit,
  default "Create topic '{slug}'")`; the {base} placeholder noted.
- New sections:

```md
## Updating a topic from its base

    goga topics update
    goga topics update feat-x
    goga topics update feat-x --base-ref origin/main
    goga topics update -p

Refreshes the topic from its base — the current topic when the
identifier is omitted, the identified one otherwise (the switch tiers;
several candidates offer the numbered list). The base comes from
--base-ref or topics.base_ref; no base at all is a clean error naming
the flag and the configuration line. The strategy comes from
topics.update.strategy (merge | rebase | ff-else-merge |
ff-else-rebase, default merge) and the message template from
topics.update.commit — no CLI overrides. No confirmation is asked.
--publish/-p pushes the refreshed branch after success (a plain push
after a merge, a protected force after a rebase). The targeted fetch of
the base is reported by one stdout line before it runs. Exit 0/1.

## Propagating a topic into its base

    goga topics propagate feat-x
    goga topics propagate --yes
    goga topics propagate feat-x --base-ref release/2.0.0

Delivers the topic's work into its base and pushes — the push is
inherent, there is no --publish flag. The strategy comes from
topics.propagate.strategy (merge | ff | squash, default merge), the
message from topics.propagate.commit. Exactly one confirmation names
the topic, the target, and the push; --yes/-y skips it (a
non-terminal without it is a clean error; a declined answer exits 0
with nothing done). The topic stays alive after the delivery — cleanup
remains the separate clear. Exit 0/1.
```

## Dependency Map

No new edges — new types travel the existing edges, same direction:

```
goga/hooks/catalog        (leaf, M)
goga/config/project       (leaf, M) ──► goga/config (facade, M — one phrase)
goga/config/hooks         (M) ── imports ──► goga/config/project (the amendment
                                               type tree and section defaults
                                               follow the reshaped TopicsConfig)
goga/topics/git           (leaf, M)
goga/topics/hooks         (M) ── imports ──► goga/hooks (E), goga/history (E)
goga/topics               (M) ── imports ──► goga/topics/git (12 new + existing types,
                                               exchanging usage), goga/topics/hooks
                                               (TopicIdentity, TopicHooks — E),
                                               goga/history (E), goga/topics/editor (E)
goga/commands/topics      (M) ── imports ──► goga/topics (3 new + existing types,
                                               update + propagate usages),
                                               goga/config (TopicsConfig, load_project_config),
                                               goga/config/hooks (E)
```

Acyclic; implementation order above is a topological order.

## Verification Checklist

After each cell lands, and again after the whole change-set:

- **DSL / manifests** — `goga lint` exits 0 (every connected practice
  referenced in at least one annotation; no annotation references an
  entity outside its CODEMANIFEST context; casing, `location`
  restrictions, and signature rules hold; new body fragments sit in the
  same manifest style as their cell).
- **Config sweep** — a repository-wide search for `publish_commit`
  finds no reader: only the migration note in
  `docs/features/topics/configuration.md` and
  `goga/config/.usages/project-configuration.md` mention the name
  (project memory: deletion triggers a repository-wide sweep; stale
  values pass through silently, no warning).
- **Facades** — `python -c "from goga.topics.git import merge_tree,
  replay_commits, fetch_branch, push_branch_with_lease"`; `python -c
  "from goga.topics import update_topic, resolve_propagation,
  execute_propagation, resolve_divergence"`; `python -c "from
  goga.config import TopicsConfig"` all succeed; `python -c "from
  goga.config import TopicsCreateConfig, TopicsUpdateConfig,
  TopicsPropagateConfig"` succeeds.
- **Config amendment overlay** — a tool contribution amending
  `topics.update.strategy` applies through `merge_config_amendments` and
  appears in the overlay summary; the retired `topics.publish_commit`
  path is the same unknown-path structural failure as before; the
  overlay cross-check tests against `dataclasses.fields` stay green.
- **Hooks** — the two new addresses resolve through `declared_actions`;
  a failing subscriber warns and never breaks the command (soft class).
- **Behavior gates** — `pytest tests/ -x` green and `ruff check` clean;
  the suite covers: the effective-tip ladder (descendant / single
  projection / tag/hash), the reconciliation (written, skipped when
  already carried, never pushed), the four update strategies on both
  the current and another topic, pre-flight conflict atomicity, the
  publish plain/lease split with the failed-push exception, the three
  propagate strategies on both write paths, the retry cycle and the
  uniform rollback, content-based nothing-to-do, the board marker and
  the additive JSON field (null when unresolved), the git version gate,
  and the nested config validation (clean errors naming the keys).
- **Docs** — the MkDocs build passes; the five
  `docs/features/topics/` pages describe the new behavior and carry the
  migration note. The global configuration page
  `docs/configuration/project.md` lands in the same change-set: its
  commented `topics` example switches to the nested shape (base_ref
  plus create/update/propagate with strategy/commit) and its
  loader-error table row names the nested keys (`topics.update.strategy
  must be a string…` and the same pattern for every topics leaf) — the
  name `publish_commit` survives there nowhere, keeping the sweep
  assertion above true (the migration note and the facade usage file
  only).

The docs pages and the test suite are tracked by the task (`task.md`
Scope); this plan carries the CODEMANIFEST and `.usages/` artifacts —
the change-set lands them together.
