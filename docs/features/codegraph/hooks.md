# Codegraph — Hooks

The codegraph domain exposes **no hook actions** — the run is a read-only parse-and-render pipeline with no extension points. Tool packages cannot amend or veto the graph; every checkpoint a schema consumer would deliver is absent because the graph is derived from the sources, not from authored facts.

The platform mechanism behind hook actions in general is covered in [Hooks](../hooks/index.md).
