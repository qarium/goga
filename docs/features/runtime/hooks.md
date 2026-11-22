# Runtime — Hooks

The runtime domain offers **no hook points** — no `goga_tool_*` package can subscribe to anything here.

The domain is a thin host-side observer: it resolves paths through the shared runtime formula and packages exactly one target per invocation. There is no lifecycle to extend and no decision to delegate. The platform mechanism itself (enumeration, registries, delivery, inspection with `goga hooks`) is covered in the [Hooks](../hooks/index.md) domain.
