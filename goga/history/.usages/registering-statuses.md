# history — registering topic statuses

How a `goga_tool_*` package attaches its own statuses to the topic status
scale. For tool package authors; no goga code changes are needed.

Subscribe a hook to the status action of the statuses domain inside your
`register_hooks` callback:

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "published", register_published)


def register_published(context):
    context.register("published", "mkdocs/published.md", after="planned")
```

The hook receives `context` — the registration surface scoped to your
tool. Every name you register is stored qualified with your tool prefix,
so registrations from different tools never collide and a topic can carry
several statuses at once. A hook may also declare `self` — the isolated
context of your tool; one instance links all its hook invocations of a
run, freely mutable, invisible to the domains.

## Rules and failure behavior

- The built-in statuses are immutable — registration is add-only.
- `name` — the status name as your tool defines it; shown as
  `<tool>.<name>`.
- `filepath` — the artifact path relative to the topic directory; nested
  paths allowed.
- `before` / `after` — anchors: qualified names of statuses this one
  precedes or follows; at least one anchor is required, both given define
  a placement range.
- A registration missing an anchor, carrying empty values, an
  unresolvable anchor, or an invalid range is skipped with a log
  warning; it never aborts the command and never cancels other
  registrations.
- Two tools may reference the same artifact path — both statuses apply
  independently.
