# Drift

Report structural drift between declared contracts and actual code.

The drift domain compares the two independent views of the project — the declared contract view built from the CODEMANIFEST files ([Schema](../schema/index.md)) and the code-derived view parsed from the sources ([Codegraph](../codegraph/index.md)) — and prints the flat report of their structural discrepancies. Which tasks it solves:

- **See the drift** — `goga drift` reports every cell that exists in only one of the two views and every facade type name declared but missing from the code (or present in the code but undeclared), as one flat JSON report.
- **Trust the comparison** — discrepancies are computed on the complete views, always; the filters (`CELLS`, `--max-depth`, `--depends-on`) scope the report only — they select what is reported, never what is compared, so a filter asymmetry between the two views cannot fabricate an entry.
- **Gate on the outcome** — the exit code is the verdict: `0` the views agree, `1` discrepancies were found, `2` the comparison could not be performed; CI and review cycles branch on it without parsing the report.

Every discrepancy is one flat entry of four semantic kinds — the cell-level pair and the type-level pair:

| Kind | Level | Meaning |
|---|---|---|
| `schema_only` | cell | The cell is declared in a CODEMANIFEST but no analyzable code exists for it |
| `codegraph_only` | cell | The cell exists in the code but no CODEMANIFEST declares it |
| `schema_only` | types | The cell exists in both views; the listed type names are declared but missing from the code |
| `codegraph_only` | types | The cell exists in both views; the listed type names exist in the code but are undeclared |

A cell-level entry never coexists with type-level entries of the same cell — the branches are mutually exclusive. An empty report means the views agree. Where [Contract](../contract/index.md) compares declared signatures against implementations cell by cell, drift compares the two whole-project views structurally — cell presence and facade type names, name-level only; the two commands complement each other.

## In this directory

- [CLI](cli.md) — the full `goga drift` command reference
- [Configuration](configuration.md) — the domain reads no configuration section of its own; the underlying view domains consume `language` and `lint.ignore`
- [Hooks](hooks.md) — no hook actions of its own; declared-view checkpoint failures are execution failures
- [API](api.md) — the `goga.drift` facade
