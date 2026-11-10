# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| `goga/config/.usages/project-configuration.md` | DIRECTLY AFFECTED — documents `lint.ignore` and its consumer scope, which the change widens |
| `goga/commands/lint/.usages/lint.md` | DIRECTLY AFFECTED — documents the ignore behavior as lint's own; now shared semantics |
| `goga/ast/.usages/loading.md` | INDIRECTLY AFFECTED — documents `AST(path, ignore)` delivery; verified |
| `goga/schema/hooks/.usages/checkpoints.md` | INDIRECTLY AFFECTED — walk/gate semantics over the (now filterable) tree; verified |
| `goga/config/hooks/.usages/checkpoints.md` | INDIRECTLY AFFECTED — the config amendment checkpoint the schema command newly delivers; verified |
| `goga/config/.usages/registering-hooks.md` | UNAFFECTED — mentions `lint.ignore` only as an example amendable config leaf; statement remains true |
| All other `.usages` files | UNAFFECTED — no references to the changed behavior |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| `goga/config/.usages/project-configuration.md` | Field table row `lint.ignore`: "excluded from AST traversal by `goga lint`" → "by the AST-consuming commands (`goga lint`, `goga schema`, `goga contract`, `goga tool`)"; `lint` accessor notes: paths "relative to the traversal root — the project-root cwd of the consuming command (`goga lint` chdirs to its path argument first)"; absence bullet: "excluded from traversal by the consuming commands" | The consumer set grew from one command to four; the old wording under-described the delivered behavior |
| `goga/commands/lint/.usages/lint.md` | Behavior list gains one bullet: the same `lint.ignore` list is honored by `goga schema`, `goga contract`, and the `ast` injection of `goga tool` | Consumers of the lint practice should learn the ignore list is project-wide AST semantics, not lint-private; file stays self-contained (references commands, not other practices) |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `goga/ast/.usages/loading.md` | Yes | The "Ignoring directories" section already frames `ignore` generically ("consumers use it to honor a configured ignore list") — no edit needed |
| `goga/schema/hooks/.usages/checkpoints.md` | Yes | "Deliver only the cells surviving your filters — filters prune delivery exactly as they prune output" already covers a tree filtered at load; no contradiction |
| `goga/config/hooks/.usages/checkpoints.md` | Yes | Describes the load-moment amendment delivery the schema command now performs (load authored config → amend → consume effective config → summary lines to stderr) — matches the new code path verbatim |

## Canonical Patterns Status

**Preserved.** No example signatures, recipe shapes, or code blocks changed semantics: the two edits are wording accuracy (consumer set) plus one additive bullet; the `lint.ignore` YAML examples, matching rules (exact paths, no glob, trailing slash insignificant), and swallow semantics stay byte-identical.

## Consistency Summary

**Consistent.** `goga lint` → `cells: 91, errors: 0`; `/tmp/goga-test-venv/bin/goga schema` → exit 0 with clean stderr. Every usage file that mentions the ignore behavior now describes the implemented four-consumer delivery; indirectly affected files verified without edits.
