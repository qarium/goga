# hooks — delivering per tool with staged control

How a goga domain delivers an action to its subscribed hooks per tool, when
the plain emission is not enough — the domain must know each tool's outcome
(staged contributions, compensating rollback). For domain maintainers inside
goga.

## When to use

Use `emit_hook_event` when the domain only hands the context over — the
emission is fire-and-forget and collects nothing after the event. Use this
pattern when a tool's contribution is committed only after its hooks succeed;
per-hook outcomes are out of reach through the emission, so the domain drives
the delivery loop itself over the public primitives.

## The public primitives

    from goga.hooks import HookRegistry, wrap_context, build_hook_arguments

- `HookRegistry()` — the run registry; `build_once()` assembles it once per
  run.
- `registry.subscriptions_for(domain, action)` — the address's
  subscriptions, in enumeration order.
- `registry.self_context(tool)` — the isolated context of one tool.
- `wrap_context(view)` — the delivery view of your context: reads and calls
  pass through, attribute assignment is blocked.
- `build_hook_arguments(hook, proxy, self_context)` — the keyword arguments
  for the call; only names the hook declared receive values.

## The pattern

```python
registry = HookRegistry()
registry.build_once()

groups: dict[str, list] = {}
for sub in registry.subscriptions_for("<domain>", "<action>"):
    groups.setdefault(sub.tool, []).append(sub)

for tool, subs in groups.items():
    proxy = wrap_context(build_the_context_for(tool))   # your per-tool view
    try:
        for sub in subs:
            sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))
    except Exception as reason:
        logger.warning("tool skipped", extra={"tool": tool, "action": "<action>", "reason": reason})
        discard(tool)          # the tool's whole contribution
        continue
    commit(tool)               # only after every hook of the tool succeeded
```

## Rules the pattern keeps

- Deliver to every subscriber of the address — never filter delivery by
  invitation or any other criterion; a tool's eligibility lives in its
  context (a marker the hook checks), not in delivery.
- Treat a failure per the action's error class recorded in the catalog —
  soft: warn naming the tool, the action, and the reason, then continue with
  the next tool. The single fatal case (a broken package import) surfaces at
  `build_once`.
- One registry per run — build it once and share it across your checkpoints.
- Do not deliver a hook any value it did not declare —
  `build_hook_arguments` is the single projection.
