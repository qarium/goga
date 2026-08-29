# topics — switching and continuation

How to move the repository onto existing work with the `goga.topics`
facade. For consumers that resume work: the topics switch command, the
pipeline run form.

`switch_topic` resolves the identifier, chooses among candidates, and
performs the switch. Resolution tries three tiers in order — exact branch
name, then exact topic slug (a local branch beats its remote twin), then
prefix matches on branch names and slugs — and takes the first non-empty
tier: an exact match excludes prefix candidates. A branch without a topic is
a valid target.

## Switching

```python
from goga.topics import switch_topic

result = switch_topic("history-com")   # prefix match, one candidate
print(result)                           # one line — the outcome
```

- Zero candidates -> a clean error with a hint to the board.
- Several candidates -> a numbered list with statuses and a number prompt;
  without interactive input the call fails with the list.
- Already on the hosting branch -> idempotent success, no mutation.
- A dirty working tree is a clean error — probed only when a mutation is
  needed.
- Mutations are local-only: checkout of a local branch, or creation of a
  local branch from a remote-tracking ref (no network).

## Resolving candidates without switching

```python
from goga.topics import resolve_switch_candidates

candidates = resolve_switch_candidates("release-1-3-0", year="2026")
for candidate in candidates:
    print(candidate.branch, candidate.topic, candidate.statuses)
```

- Read-only; build custom selection UIs on top of the same resolution
  order.
