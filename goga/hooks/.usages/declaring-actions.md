# hooks — opening a domain action

How a goga domain maintainer opens an extension point for installed tool
packages. For domain maintainers inside goga.

## Declare the action

Add one record to the action catalog — the domain, the action name, and
the error class:

- `soft` — a failing hook is skipped with a log warning; the command
  continues.
- `hard` — the first failing hook stops the command with a clean error.

## Define the context contract

The action's context is your own object. Its members are the single
channel tools have into your domain — publish the surface you want tools
to call, and state in your contract what each member does and when the
event fires. When tools write through the context, give each receiving
tool its own view of it — the emission builds the view per tool.

## Emit at the checkpoint

```python
emit_hook_event(HookRegistry(), "<domain>", "<action>", context_for=build_view)
```

- The emission assembles the registry on first use — the single build of
  the run; there is no separate build step.
- `context_for` takes a tool identity and returns the object that tool's
  hooks receive — return the same instance to share, a scoped view to
  isolate.

## What the platform carries for you

Package enumeration, facade imports, the callback call, envelope
validation, delivery, injection, error classes, and diagnostics — your
domain declares the action and emits it; nothing else.
