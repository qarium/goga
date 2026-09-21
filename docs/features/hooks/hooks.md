# Hooks — The registration contract

How a `goga_tool_*` package subscribes its hooks to domain actions — the tool-author side of the platform.

A tool **may** expose a `register_hooks(hooks)` callable in its facade package — the registration of domain hooks. goga calls it when a command first reaches a hook checkpoint of the run, or when you inspect the registry with [`goga hooks`](cli.md); commands that use no hooks never call it. Registration is never cached — package edits apply from the next run, without reinstall.

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "published", register_published)


def register_published(context):
    context.register("published", "mkdocs/published.md", after="planned")
```

`hooks.subscribe(domain, action, name, hook)` registers one hook:

- `domain` + `action` — the action address: the semantic owner domain and the action name within it (`"statuses"` / `"register_statuses"` is the topic-status action — see [History — Hooks](../history/hooks.md); `"onboarding"` / `"declare_session"` and `"onboarding"` / `"amend_config"` are the onboarding-session actions a tool is invited into via `goga init -t <tool>` — see [Init — Hooks](../init/hooks.md); the seven `"topics"` addresses — `amend_creation`, `amend_todo_entry`, `topic_created`, `topic_published`, `topic_switched`, `topic_todo_entered`, `topic_deleted`, all soft — are the topic-lifecycle checkpoints: two amendments before the content is fixed and five notifications after their moments, see [Topics — Hooks](../topics/hooks.md); the three `"pipeline"` addresses — `amend_workflow` (**hard**), `run_created`, `run_completed` (soft) — are the pipeline checkpoints: the workflow amendment before compilation in both the run and the card form, and the two notifications around a run's launch, see [Pipelines — Hooks](../pipelines/hooks.md); the five `"build"` addresses — `validate_build` (**hard**, with verdict collection), `build_started`, `pass_started`, `pass_completed`, `build_completed` (soft) — are the build checkpoints: the validation gate over the resolved run facts before the first pass and the four run notifications, see [Build — Hooks](../build/hooks.md)).
- `name` — the hook name, unique per tool per address; registrations appear in the [`goga hooks`](cli.md) tree under their tool line.
- `hook` — the callable executed when the action fires.

The tool identity is assigned by goga from the package name — a package never names itself, and identical hook names of different tools never collide. Enumeration is deterministic: packages in alphabetical order of top-level module name, subscriptions delivered in enumeration order.

## The hook signature

A hook receives values only for the parameters it declares by the fixed offered names — `context` and `self`:

- `context` — the delivered object of the action. Read attributes and call methods freely; attribute assignment is blocked. What the object carries is fixed by the owner domain's contract — for `register_statuses` it is the status registration surface (`register(name, filepath, before=..., after=...)`, names stored qualified `<tool>.<name>`; see [History — Hooks](../history/hooks.md) for the scale rules). For the onboarding actions it is the declaration or contribution surface described in [Init — Hooks](../init/hooks.md).
- `self` — the isolated context of your tool. One instance links all its hook invocations of a run; freely mutable by your tool, invisible to the domains.

The declaration order does not matter; names you did not declare receive nothing.

## Error classes and diagnostics

Each action in the catalog fixes how a failing hook is treated. The topic-status, the onboarding, the topics, the two pipeline notification, and the four build notification actions are **soft**: a failing hook is skipped with a stderr warning naming the tool, the action, and the reason, and the command continues. A **hard** action stops the command — `pipeline/amend_workflow` stops at the first failing hook with a clean error (see [Pipelines — Hooks](../pipelines/hooks.md)), while `build/validate_build` lets every subscribed tool's hooks run to completion and merges their vetoes into one error that stops the build before any pass (see [Build — Hooks](../build/hooks.md)); the class is chosen by the owner domain when it declares the action.

At registration: a wrong address, an empty name, or a repeated name on the same address is refused with a stderr warning naming the tool, the action, and the reason — the registration is skipped, the rest apply. A crashing callback is a warning; the registrations made before the crash survive. A broken package import is the only fatal case: a clean error naming the package.

> **Migration note.** The old `register_topic_statuses(statuses)` callback is gone. After a goga update, a package still carrying it loses its statuses **without any diagnostic** — they silently disappear from the scale. Moving to `register_hooks` is the package author's responsibility. Qualified names of packages with underscores in their name change too: the qualifier is the canonical hyphen identity, so `goga_tool_hello_world` now registers `hello-world.published` where it used to register `hello_world.published` — existing `goga history status -s <tool>.<name>` filters must use the hyphen form.
