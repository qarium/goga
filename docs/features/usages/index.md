# Usages

Sync cell-level usages from declared git dependencies — and check them for drift.

The usages domain keeps imported practices current. Which tasks it solves:

- **Declare dependencies** — the `usages:` section of `.goga/config.yml` maps `<group>` → `<dep>` → `{git, ref, root}`: the repositories whose cell-level `.usages/*.md` practices your project consumes.
- **Materialize** — `goga usages sync` clones each dependency's remote and copies its usage files into your project's `.goga/usages/<group>/<dep>/` tree — the practices your CODEMANIFEST files reference through `Usages` paths.
- **Detect drift** — `goga usages status` hashes the synchronized files against each dependency's current remote state and reports one status per dep — `new`, `up to date`, `out of date`, or `error` — without modifying anything. An `out of date` dep differs from the remote-rebuilt tree; the check does not distinguish an upstream move from a local edit.

Together with the `Imports` mechanism of the DSL (see [Cells — Usages](../../cell/usages.md)), this makes project know-how travel between repositories with the code.

## In this directory

- [CLI](cli.md) — the full `goga usages` command reference
- [Configuration](configuration.md) — the `usages:` section of `.goga/config.yml`
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.usages` package facade
