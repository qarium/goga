# Schema

Generate a JSON schema tree from project CODEMANIFEST files.

The schema domain exposes the contract layer to schema consumers. Which tasks it solves:

- **Export the contract** — `goga schema` walks the project cells and emits a JSON tree of the declared types: every entity and routine with its signature, location, annotations, methods, and properties.
- **Scope the export** — positional cells limit the output to the named cells; `--max-depth N` bounds the import expansion; `--depends-on CELL` keeps only the cells connected to the given one.
- **Feed tooling** — the JSON output is the machine-readable projection of the CODEMANIFEST layer: viewers, generators, and external validators consume it instead of re-parsing the DSL.

## In this directory

- [CLI](cli.md) — the full `goga schema` command reference
- [Configuration](configuration.md) — the domain reads no configuration section
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.schema` package facade
