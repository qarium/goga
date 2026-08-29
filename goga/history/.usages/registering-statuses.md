# history — registering topic statuses

How a `goga_tool_*` package attaches its own statuses to the topic status
scale. For tool package authors; no goga code changes are needed.

goga calls `register_topic_statuses(statuses)` in your package at every
command start that computes a topic status. The `statuses` object is a
controlled registration surface scoped to your package: every name you
register is stored qualified with your tool prefix, so registrations from
different tools never collide and a topic can carry several statuses at
once.

## The callback

```python
# inside the goga_tool_<tool> package
def register_topic_statuses(statuses):
    statuses.register("published", "mkdocs/published.md", after="planned")
```

- `name` — the status name as your tool defines it; shown as
  `<tool>.<name>`.
- `filepath` — the artifact path relative to the topic directory; nested
  paths are allowed.
- `before` / `after` — anchors: qualified names of statuses this one
  precedes or follows, controlling where it sits in the scale. At least one
  anchor is required; both given define a placement range.

## Rules and failure behavior

- The built-in statuses are immutable — registration is add-only.
- A registration missing an anchor, carrying empty values, an unresolvable
  anchor, or an invalid range is skipped with a stderr warning; it never
  aborts the command and never cancels other registrations.
- Two tools may reference the same artifact path — both statuses apply
  independently.
- A package import failure is the only fatal case: a clean error naming the
  package.
