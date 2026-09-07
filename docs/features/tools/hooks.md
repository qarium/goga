# Tools — Hooks

The tools domain is the **consumer side** of the hooks platform: a tool package declares the callbacks, the domains fire the actions.

A tool package may expose two lifecycle callables in its facade, next to the required `main(argv)`:

| Callable | Called by | Purpose |
|---|---|---|
| `register_hooks(hooks)` | a domain checkpoint, or `goga hooks` | Subscribe hooks to domain actions — `hooks.subscribe(domain, action, name, hook)`; registration is never cached, package edits apply from the next run |
| `install(user: str \| None = None)` | `goga install`, after a successful pip | The post-install lifecycle hook (see [Install — CLI, post-install hooks](../install/cli.md#post-install-hooks)) |

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "published", register_published)
```

The full registration contract — the hook signature (`context` / `self`), the error classes, the diagnostics — is the [Hooks domain](../hooks/hooks.md); the declared actions are listed per domain (today: [History — Hooks](../history/hooks.md)). The `main` entry point and its optional AST injection are covered in [CLI](cli.md#optional-injections).
