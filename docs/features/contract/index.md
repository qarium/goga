# Contract

Compare CODEMANIFEST declarations with the source code implementation.

The contract domain is the drift detector between the DSL and the code. Which tasks it solves:

- **Verify a cell** — `goga contract <cell>` parses the cell's `CODEMANIFEST` and extracts the implementation surface from its source files: every declared entity and routine is matched against the actual classes and functions.
- **Per language** — extraction is language-aware (`--lang python | golang | kotlin | swift | javascript`, defaulting to the project's `language`); the per-language rules are covered in [Languages](../../languages/index.md).
- **Report the drift** — each declared type that the implementation does not match (missing, signature mismatch, misplaced) is reported; the report is what acceptance and review cycles act on.

Together with [Lint](../lint/index.md) — which validates the DSL itself — this closes the loop: the manifest is structurally valid *and* faithfully implemented.

## In this directory

- [CLI](cli.md) — the full `goga contract` command reference
- [Configuration](configuration.md) — the domain reads the global `language` field
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.contract` package facade
