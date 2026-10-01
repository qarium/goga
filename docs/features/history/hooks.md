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

The hook receives `context` — a `StatusRegistry` view scoped to the tool. Every registered name is stored **qualified** with the tool prefix (`<tool>.<name>`, e.g. `mkdocs.published`), so registrations from different tools never collide and a topic can carry several statuses at once. A hook may also declare `self` — the isolated per-tool context of the run.

## The contexts

### `register_statuses` — `StatusRegistry` (soft)

One view per tool identity — a hook registers through it and nothing else.

| Read | Type | Meaning |
|---|---|---|
| `builtin_stages` | `list[Stage]` | the nine built-in stages of the axis |
| `tool_prefix` | `str` | your tool's identity prefix — the qualifier applied to every name registered through this view |
| `stages` | `list[Stage]` (property) | the built-in axis plus your accepted entries — a fresh copy each read |

| Method | Effect |
|---|---|
| `register(name, filepath, before=..., after=...)` | stores the name qualified as `<tool>.<name>`; raises on an empty name, an empty filepath, a missing anchor, or a duplicate qualified name; an unresolvable anchor or an invalid range surfaces at assembly as a warning plus skip. |

The read-and-contribute surface of the statuses axis — read-only, attribute assignment blocked. The built-in statuses are immutable — registration is add-only. Two tools may reference the same artifact path — both statuses apply independently.

A structural rejection — empty values, a missing anchor, a duplicate — raises out of `register` inside your hook and the delivery warns on stderr naming the tool, the action, and the reason. An assembly rejection — an anchor that resolves against no entry of the assembled axis, a range the axis cannot fit — is skipped at assembly with a `skipping status registration` warning whose record carries the entry name and the reason as structured fields. A rejection never aborts the command and never cancels the other registrations.

## Integration scenarios

- **Artifact → history-status mapping** — register a status keyed by your artifact's file (`register("<name>", "<artifact>.md", before=..., after=...)`), anchored onto the axis around the stage the artifact belongs to; `goga topics board` then places your artifact on the scale.
- **CI / dashboard consumption** — read `stages` in your hook to mirror the axis — the built-in nine plus your own accepted entries — into your own reporting, and key your pipeline checks on the qualified names.

## The fact records

The record the context reads:

| Record | Fields |
|---|---|
| `Stage` | `name` (`str` — bare for the built-in entries, `<tool>.<name>` for tool entries), `filepath` (`str` — the artifact path relative to the topic directory, nested paths allowed), `before` / `after` (`str | None` anchors — qualified names; both given define a placement range) |

The platform mechanism behind the action (enumeration, the registry, delivery, inspection with `goga hooks`) is the [Hooks](../hooks/index.md) domain; the registration contract for tool authors in [Hooks — The registration contract](../hooks/hooks.md); the tool-package side of authoring a `register_hooks` callback is covered in [Tools — Hooks](../tools/hooks.md).
