# Lint

Validate CODEMANIFEST files in a project.

The lint domain is the structural gate of the DSL. Which tasks it solves:

- **Validate the manifest** — `goga lint` parses every `CODEMANIFEST` in the project tree and checks it against the rule set: 21 document-level rules (applied per document by the AST visitor) and 3 tree-level rules (applied across the import graph by the analyzer).
- **Report precisely** — every error carries the rule name, the message, the document path, and the offending YAML fragment; a closing summary counts cells and errors.
- **Scope the noise** — the `lint.ignore` list prunes directories (a vendored `.venv`, a build output) from traversal before validation.
- **Explain the failures** — the [error catalog](errors.md) describes what each rule checks and what a violation means.

What each rule *means* semantically — the DSL itself — is covered in [Cell](../../cell/index.md); how the rules are implemented (the visitor, the analyzer, the error hierarchy) in [Architecture](../../architecture/index.md).

## In this directory

- [CLI](cli.md) — the full `goga lint` command reference
- [Configuration](configuration.md) — the `lint:` section of `.goga/config.yml`
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.ast` package facade
- [Errors](errors.md) — the catalog of validation errors
