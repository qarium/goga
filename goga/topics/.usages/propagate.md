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
