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
