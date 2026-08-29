# topics — ensuring work: switch or create

How to bring the repository onto requested work in one call — switching
when it exists, creating it when nothing hosts it — with the `goga.topics`
facade. For consumers that resume *or* start work through a single
identifier.

`ensure_topic` resolves the identifier exactly like `switch_topic` —
exact branch name, then exact topic slug (a local branch beats its remote
twin), then prefixes, first non-empty tier wins — and falls back to
`create_topic` with the identifier as the branch name only when **zero
candidates** resolve. A resolvable identifier therefore never creates
anything.

## Ensuring work

```python
from goga.topics import ensure_topic

result = ensure_topic("prune-history-and-new-status")   # current year
result = ensure_topic("Feature/Foo_Bar", year="2025")
print(result)  # one line — the outcome
```

- Nothing hosts the identifier -> fresh work: the branch is created with
  the name as entered, the repository switches to it, and the topic
  directory of the year is created from its slug —
  `Created branch <name> and topic <year>/<slug>`.
- A hosted identifier -> the plain switch outcome: `Switched to branch
  <name>`, `Created branch <name> from <remote>/<name>`, or `Already on
  branch <name>` (idempotent, nothing touched).
- Several candidates -> the numbered list with statuses and a number
  prompt; without interactive input the call fails with the list —
  ambiguity never escapes into creation.
- An occupied name (an existing branch, a remote-tracking twin, or the
  topic directory of the year) or an empty slug triggers a re-ask on an
  interactive terminal, or a clean error with the reason and a hint
  otherwise.
- A switch that would mutate probes the working tree first — a dirty tree
  is a clean error. The creation fallback carries uncommitted changes
  onto the fresh branch instead.
- Mutations are local-only — no network, no fetch, no push.
