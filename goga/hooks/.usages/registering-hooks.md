# hooks — registering domain hooks

How a `goga_tool_*` package subscribes its hooks to the actions of goga
domains. For tool package authors; no goga code changes are needed.

A package may define three facade callbacks, separated by nature: `main`
(the CLI call of the tool), `install` (the post-install lifecycle hook),
and `register_hooks` (the domain extension registration described here).

## The callback

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "my_status", register_my_status)
```

- `domain` — the semantic owner of the action; with the action name it is
  the address of the subscription.
- `action` — the action name within the domain.
- `name` — the hook name, unique per tool per address.
- `hook` — the callable executed when the action fires.

The tool identity is assigned by goga from the package name — a package
never names itself, and identical hook names of different tools never
collide.

## The hook signature

A hook receives values only for the parameters it declares by the fixed
offered names:

```python
def register_my_status(self, context):
    context.register("published", "mkdocs/published.md", after="planned")
```

- `self` — the isolated context of your tool; one instance links all its
  hook invocations of a run; freely mutable by your tool.
- `context` — the delivered object of the action; read attributes and
  call methods freely, attribute assignment is blocked.

The declaration order does not matter; names you did not declare receive
nothing.

## When hooks run

goga calls `register_hooks` when a command first reaches a hook
checkpoint of the run — or when you inspect the registry with
`goga hooks`. Commands that use no hooks never call it. Registration is
never cached — package edits apply from the next run, without reinstall.

## Failure behavior

- A wrong address, an empty name, or a repeated name on the same address —
  a stderr warning naming your tool, the action, and the reason; the
  registration is skipped, the rest apply.
- A crashing callback — a warning; the registrations made before the
  crash survive.
- A failing hook — a warning, the hook is skipped, the sequence continues
  (soft action); or a command error stopping at the first failure (hard
  action). The action's error class is fixed by the domain in the action
  catalog.
- A broken package import is the only fatal case: a clean error naming
  the package.
