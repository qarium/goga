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

    require_git_version()   # older than 2.40 -> clean error naming versions

- Gate every exchange entry point; the check is cheap and read-only.

## Checking containment

    from goga.topics.git import is_ancestor

    contains = is_ancestor(base_tip, topic_tip)   # True: the topic carries the base

- Read-only, no network; both sides accept any resolvable revision.

## Comparing content identities

    from goga.topics.git import resolve_commit_tree

    base_tree = resolve_commit_tree(base_tip)
    delivery_tree = resolve_commit_tree(delivery)   # equal trees -> identical content

- The tree oid is git's own content identity — two commits with the same
  tree carry the same state whatever their histories; the caller owns
  the equality policy.

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

    fetch_branch("main")                                   # the single sanctioned fetch; False = absent on origin
    push_branch("main")                                    # plain, binds upstream, creates when absent
    push_branch_with_lease(topic_branch, pre_rebase_tip)   # the protected rewrite
    push_revision_to_branch(commit, "main")                # write-through, no local branch

- Report each fetch with one stdout line before it runs — the reporting
  belongs to the caller; the cell stays silent.
- A False return means origin carries no such branch — never read the
  remote-tracking ref as the twin after one: the ref is left untouched,
  so a stale value from an earlier fetch would speak for a remote that
  no longer has the branch.
- The lease binds to the tip captured immediately before the rewrite; a
  remote standing anywhere else refuses with git's reason.
