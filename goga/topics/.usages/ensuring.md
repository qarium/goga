# topics — ensuring work: switch or create

How to bring the repository onto requested work in one call — switching
when it exists, creating it when nothing hosts it — with the `goga.topics`
facade. For consumers that resume *or* start work through a single
identifier.

`ensure_topic` resolves the identifier exactly like `switch_topic` —
exact branch name, then exact topic slug (a local branch beats its remote
twin), then prefixes, first non-empty tier wins — and falls back to the fast
creation — the branch named as entered, off the current HEAD — only when **zero candidates**
resolve. A resolvable identifier therefore never creates
anything. With `todo=True` the todo entry runs after the switch or the creation.

## Ensuring work

```python
from goga.topics import ensure_topic

result = ensure_topic("prune-history-and-new-status")  # current year
result = ensure_topic("Feature/Foo_Bar", year="2025")
print(result)  # one line — the outcome
```

- Nothing hosts the identifier -> the fast creation from the current
  HEAD: the branch named as entered, the switch, the topic directory —
  and with `todo=True` the editor entry afterwards (an empty entry
  file; a cancelled entry leaves no todo.md). No publication ask
  exists here; the configuration base is never read.
- A hosted identifier -> the plain switch outcome; with `todo=True`
  the entry follows the switch: the todo.md of the **requested** topic —
  the resolution's hosted topic, so a topic merged into another branch
  is entered as itself (never a fresh directory of the hosting branch's
  name); a branch without a topic gets its topic directory created
  first, then the empty entry — the fast process is never interrupted
  (a branch name with no slug is a clean error).
- Several candidates -> the numbered list with statuses and a number
  prompt; without interactive input the call fails with the list —
  ambiguity never escapes into creation.
- An occupied name or an empty slug is a clean error with the reason
  and a hint to the board.
- `todo=True` without an interactive terminal is a clean error before
  any action.
- Mutations are local-only — no network, no fetch, no push.
