# Hooks

The extension platform connecting goga domains and tool packages.

The hooks domain is the mechanism behind every domain extension: a domain declares an **action** at a checkpoint of its run; an installed `goga_tool_*` package subscribes a hook to that action; when a command first reaches the checkpoint, goga enumerates the tool packages, calls each `register_hooks` callback, and delivers the action's context to the subscribed hooks. Which tasks it solves:

- **Domains expose extension points without knowing their consumers** — a domain declares an action address and the error class; the platform owns the enumeration, registration, and delivery.
- **Tool packages extend domains with no goga code changes** — a package registers its hooks at run time; registration is never cached, so package edits apply from the next run without reinstall.
- **Inspection** — `goga hooks` assembles the registry once and prints it as a tree: tool, domain, action — the fact of registration, including every refused registration with its reason.

The declared actions today: the status-scale registration of the [History](../history/hooks.md) domain. The authoring side — how a tool package writes its `register_hooks` callback — is the [registration contract](hooks.md).

## Model

- **Action** — an address `domain / name` plus an error class (**soft**: a failing hook is skipped with a warning; **hard**: the command stops at the first failure). The owner domain chooses the class when it declares the action.
- **Registry** — one per run, assembled lazily on first use at a checkpoint: packages in alphabetical order of top-level module name, subscriptions delivered in enumeration order. Commands that use no hooks never build the registry.
- **Tool identity** — assigned by goga from the package name (the `goga_tool_` prefix dropped, underscores as hyphens); a package never names itself, and identical hook names of different tools never collide.
- **Delivery** — a hook receives values only for the parameters it declares by the fixed offered names (`context`, `self`); the context is read-only (attribute assignment blocked), `self` is the tool's isolated per-run state.

## In this directory

- [CLI](cli.md) — the `goga hooks` command reference
- [Configuration](configuration.md) — the domain reads no configuration section
- [Hooks](hooks.md) — the registration contract for tool-package authors
- [API](api.md) — the `goga.hooks` package facade
