# History — Hooks

The history domain declares one hook action: the **status-scale registration** — the way an installed `goga_tool_*` package attaches its own statuses to the topic status scale, with no goga code changes.

## The action

| Address | Error class | Fires |
|---|---|---|
| `statuses` / `register_statuses` | **soft** — a failing hook is skipped with a stderr warning; the command continues | when a command first assembles the status scale (`goga history status`, `goga topics board`, …) |

A tool subscribes inside its `register_hooks` callback:

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "published", register_published)


def register_published(context):
    context.register("published", "mkdocs/published.md", after="planned")
```

The hook receives `context` — the registration surface scoped to the tool. Every registered name is stored **qualified** with the tool prefix (`<tool>.<name>`, e.g. `mkdocs.published`), so registrations from different tools never collide and a topic can carry several statuses at once. A hook may also declare `self` — the isolated per-tool context of the run.

## The registration surface

- `name` — the status name as the tool defines it; shown as `<tool>.<name>`.
- `filepath` — the artifact path relative to the topic directory; nested paths allowed.
- `before` / `after` — anchors: qualified names of statuses this one precedes or follows. At least one anchor is required; both given define a placement range.
- The built-in statuses are immutable — registration is add-only.
- Two tools may reference the same artifact path — both statuses apply independently.

A registration missing an anchor, carrying empty values, an unresolvable anchor, or an invalid range is skipped with a stderr warning naming the tool, the action, and the reason — it never aborts the command and never cancels other registrations.

The platform mechanism behind the action (enumeration, the registry, delivery, inspection with `goga hooks`) is the [Hooks](../hooks/index.md) domain; the tool-package side of authoring a `register_hooks` callback is covered in [Tools — Hooks](../tools/hooks.md).
