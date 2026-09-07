# Hooks — API

The facade of the domain package **`goga.hooks`** — the extension surface of the goga domains for installed tool packages. The facade declares no type of its own: it re-exports the declared action catalog, the run registry with its per-tool inspection view, and the emission of an action at a domain checkpoint. Importing the package imports no tool package and enumerates nothing.

The signatures below are the CODEMANIFEST contract of the platform cells.

## The facade

```python
from goga.hooks import HookRegistry, ToolHooks, declared_actions, emit_hook_event
```

| Name | Origin | Purpose |
|---|---|---|
| `declared_actions()` | `goga.hooks.catalog` | The declared action catalog |
| `HookRegistry()`, `ToolHooks` | `goga.hooks.registry` | The run registry and its per-tool view |
| `emit_hook_event(...)` | `goga.hooks.dispatch` | The emission of an action at a domain checkpoint |

## The action catalog

```python
declared_actions() -> list[Action]
Action(domain: str, name: str, error_class: str)
```

Every action declared by the domains — its address (`domain`, `name`) and its error class (`soft` or `hard`). A domain checkpoint consults the catalog to validate the address before emitting.

## The registry

```python
HookRegistry()
ToolHooks(tool: str, subscriptions: list[Subscription], rejections: list[RejectedRegistration])
ToolContext(tool: str)
```

`HookRegistry` is the one-registry-per-run state: one `ToolHooks` entry per tool with registrations, carrying its subscriptions and its refused registrations (with reasons). `ToolContext` is the isolated per-tool context delivered as `self` to the tool's hooks.

The registration envelope lives in the tools leaf cell:

```python
HookRegistrar(tool: str)
Subscription(tool: str, domain: str, action: str, name: str, hook: Callable)
RejectedRegistration(tool: str, domain: str, action: str, name: str, reason: str)
enumerate_tool_packages() -> list[ToolPackage]
ToolPackage(module_name: str)
call_register_hooks(package: ToolPackage, registrar: HookRegistrar) -> bool
```

`HookRegistrar` is the `hooks` object delivered to a package's `register_hooks` callback — `subscribe(domain, action, name, hook)` registers one hook; a wrong address, an empty name, or a repeated name on the same address is refused with a recorded reason. `enumerate_tool_packages` discovers the installed `goga_tool_*` packages deterministically (alphabetical order of top-level module name); `call_register_hooks` invokes a package's callback (`True` — the package declares one).

## The emission

```python
emit_hook_event(registry: HookRegistry, domain: str, action: str, context_for: Callable)
wrap_context(target: object) -> object
build_hook_arguments(hook: Callable, context: object, self_context: ToolContext) -> dict[str, object]
```

`emit_hook_event` delivers an action to every subscribed hook — assembling the registry on first use. The context mediation: `wrap_context` makes the delivered object read-only (attribute assignment blocked); `build_hook_arguments` passes a hook only the values it declares by the offered names (`context`, `self`).

## Example

```python
from goga.hooks import HookRegistry, declared_actions, emit_hook_event

registry = HookRegistry()

for action in declared_actions():
    print(action.domain, action.name, action.error_class)

# a domain checkpoint — the scale assembly of the history domain
emit_hook_event(registry, "statuses", "register_statuses", context_for=make_registry_surface)
```
