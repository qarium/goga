# Design Document: `drift-command`

The `goga drift` command: declared-vs-code structural drift visibility, built on the
object-returning refactor of the two view domains. Authoritative inputs:
`adr.md`, `prd.md`, `task.md`, `arch.md` (this topic directory).

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/schema/CODEMANIFEST`: routine `schema` return changed `json: str` →
  `tree: list[SchemaNode]`; header practice `beautiful_json` deleted; the
  `Node format:` JSON block replaced by the `Node content:` field list over
  `SchemaNode` fields; tree wording throughout; footer Description updated.
  Serialization leaves the cell — the caller owns it.
- `goga/codegraph/CODEMANIFEST`: routines `codegraph` and `render_graph`
  return `tree: list[CodegraphNode]` instead of `json: str`; header practice
  `beautiful_json` deleted; object-tree wording throughout; footer
  Description updated.
- `goga/commands/schema/CODEMANIFEST`: imports `SchemaNode`, `DependencyFacts`
  from `goga/schema/hooks`; adds practice `beautiful_json`; the wrapper
  algorithm gains steps 3–4 — project the returned `SchemaNode` tree onto the
  output nodes and serialize via `beautiful_json`.
- `goga/commands/codegraph/CODEMANIFEST`: imports `CodegraphNode` from
  `goga/codegraph/facts`; adds practice `beautiful_json`; algorithm step 3
  serializes the returned object tree 1:1 via `beautiful_json`.
- `goga/commands/CODEMANIFEST` (facade): imports `drift` from
  `goga/commands/drift`; adds the embedding `->drift: {}`.
- `goga/CODEMANIFEST` (root): `drift` added to the `goga/commands` import
  block and to the `Commands:` list of `app()`.

### New Entities

- `DriftEntry(kind, cell, types)` — one flat entry of the drift report;
  `goga/drift/compare.py`.
- `compare_views(schema_tree, codegraph_tree)` — every structural discrepancy
  of the two complete views; `goga/drift/compare.py`.
- `scope_entries(entries, schema_tree, codegraph_tree)` — survival scoping of
  the computed entries over the filtered views; `goga/drift/compare.py`.
- `drift(cells, max_depth, depends_on)` — the scoped drift report routine;
  `goga/drift/drift.py`.
- `drift(cells, max_depth, depends_on)` (CLI) — the command wrapper with the
  three-outcome exit contract 0/1/2; `goga/commands/drift/drift.py`.

### Changed Entities

- `goga/schema` `schema` — returns the assembled `SchemaNode` tree (was: JSON
  string). The gate projection `_to_schema_node` result becomes the return
  value; the internal dict tree stays the working representation.
- `goga/codegraph` `codegraph` — returns `list[CodegraphNode]` (was: JSON
  string); orchestration unchanged.
- `goga/codegraph` `render_graph` — returns the filtered `CodegraphNode`
  forest (was: JSON string); the `asdict` + `json.dumps` tail is deleted.
- `goga/commands/schema` `schema` — takes over projection + serialization.
- `goga/commands/codegraph` `codegraph` — takes over serialization.
- `goga.commands` facade — re-exports `drift`; `goga.app` registers it.

### Deleted Entities

- None. The `beautiful_json` practice leaves the two domain manifests (it
  moves to the two command manifests); no contract entity is deleted.

### Usages and Annotations Changes

- `goga/schema`: header `Usages` − `beautiful_json` (inline); global
  Annotations replace the serialization line with the caller-owns-
  serialization clause.
- `goga/codegraph`: header `Usages` − `beautiful_json` (file); same
  annotation replacement.
- `goga/commands/schema`, `goga/commands/codegraph`,
  `goga/commands/drift`: header `Usages` + `beautiful_json`
  (`.goga/usages/cooks/beautiful_json.md`).
- `goga/drift`: new cell — imports usages `schema-usage` (from `goga/schema`)
  and `codegraph-usage` (from `goga/codegraph`).
- `.usages/` files: `goga/schema/.usages/schema-usage.md` and
  `goga/codegraph/.usages/codegraph-usage.md` rewritten to the object
  contract; `goga/drift/.usages/drift-usage.md`,
  `goga/commands/drift/.usages/drift.md` created;
  `goga/commands/.usages/cli-commands.md` updated to 18 commands.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Phase-3 validation found no defects: `goga lint` reports
  `cells: 89 errors: 0`; all four consistency dimensions hold against the
  live providers (`SchemaNode`/`DependencyFacts` in `goga/schema/hooks`,
  `CodegraphNode` in `goga/codegraph/facts` — field names and shapes match
  every annotation reference); no `::` mutations and no `->` embeddings
  outside `Imports` in the changed set; the import graph is acyclic and
  matches the arch-plan dependency map edge for edge (`goga schema
  --depends-on` per affected cell). The apply-stage lint fix (13 dotted
  references reformatted to the resolvable `` `Type`.field `` convention) is
  already in the working tree and validated.

## Entity Interaction and Data Flow

### Interaction Diagram

```
                     ┌───────────────────────── goga drift (CLI) ─────────────────────────┐
                     │  exit 0 []  │  exit 1 report  │  exit 2 stderr                     │
                     └───────────────────────────────┬────────────────────────────────────┘
                                                     │ drift_logic(cells, max_depth, depends_on)
                                                     ▼
                                              goga/drift::drift
                complete views (no filters)          │          filtered views (filters)
        ┌───────────────────────────────────────────┼───────────────────────────────────┐
        ▼                                           ▼                                   ▼
 goga/schema::schema                      goga/schema::schema            compare_views(complete)
 -> list[SchemaNode]                      -> list[SchemaNode]            + scope_entries(filtered)
        │                                           │                                   ▲
        │ hooks: amend_cell + validate_schema       │                                   │
        ▼                                           ▼                                   │
 goga/codegraph::codegraph                goga/codegraph::codegraph
 -> list[CodegraphNode]                   -> list[CodegraphNode]

 goga/commands/schema  ── schema_logic -> list[SchemaNode] ── project ── beautiful_json ── click.echo
 goga/commands/codegraph ── codegraph_logic -> list[CodegraphNode] ── asdict ── beautiful_json ── click.echo
 goga/commands/drift ── drift_logic -> list[DriftEntry] ── project ── beautiful_json ── click.echo
 goga/commands (facade) ── re-export drift;  goga.app ── add_command(drift)
```

### Data Flows

1. **Drift report** — `drift()` calls `schema()` and `codegraph()` twice each
   (complete: `([], None, [])`; filtered: `(cells, max_depth, depends_on)`).
   The complete views feed `compare_views` (facts); the filtered views feed
   `scope_entries` (survival). The report flows to the CLI wrapper, which
   projects each `DriftEntry` to `{kind, cell[, types]}` and serializes.
2. **Schema CLI output** — `schema()` returns `list[SchemaNode]`; the wrapper
   projects each node to the seven output keys (`cell` from `path`,
   `dependencies` regrouped from `DependencyFacts` records, `tools` only when
   non-empty) and serializes via `beautiful_json`. Byte-identical to the
   pre-refactor domain serialization.
3. **Codegraph CLI output** — `codegraph()` returns `list[CodegraphNode]`;
   the wrapper maps records via `dataclasses.asdict` (fields map one-to-one
   to output keys) and serializes via `beautiful_json`. Byte-identical to the
   pre-refactor `render_graph` serialization.
4. **Registration** — `goga/commands/drift` re-exports the command; the
   facade `goga/commands` re-exports it in turn; `goga/cli.py` imports it
   from the facade and registers it in the `app()` group after `codegraph`.

### Entity Dependencies

Fixed, one-way (view domains → drift domain → wrapper → facade → root):

- `goga/drift` → `goga/schema` (`schema`), `goga/schema/hooks`
  (`SchemaNode`), `goga/codegraph` (`codegraph`), `goga/codegraph/facts`
  (`CodegraphNode`)
- `goga/commands/schema` → `goga/schema`, `goga/schema/hooks`
- `goga/commands/codegraph` → `goga/codegraph`, `goga/codegraph/facts`
- `goga/commands/drift` → `goga/drift`
- `goga/commands` → `goga/commands/drift`; `goga` → `goga/commands`

The two view producers stay mutually blind. Implementation order (leaves
first): `goga/schema` → `goga/codegraph` → `goga/drift` →
`goga/commands/schema` → `goga/commands/codegraph` → `goga/commands/drift` →
`goga/commands` → `goga` → tests/docs collateral.

## Code Stack Trace

### Trace: `goga.schema.schema` (changed)

#### Chain

1. **Input**: caller passes `cells: list[str]`, `max_depth: int | None`,
   `depends_on: list[str]` (the drift routine and the CLI wrapper are the two
   production callers).
2. `AST(".")` + `ast.load()`; `ast.errors` non-empty → `ValueError` with the
   error count → checkpoint: unchanged behavior, matches the manifest
   requirement.
3. `_filter_tree` (cells) → `_build_cell_tree` dict tree →
   `_filter_by_depends_on` → `_prune_depth` — the internal working
   representation stays the dict tree → checkpoint: filters and their order
   identical to the current implementation (byte-identity of CLI output
   depends on it).
4. Empty result → `return []` **before** any checkpoint delivery →
   checkpoint: preserves the current early return (`"[]"` was returned
   pre-checkpoint; `[]` now) — a vetoing tool never runs on an empty tree.
5. `hooks.amend_cell` per surviving cell in tree order; non-empty tools
   mappings placed on the dict nodes → checkpoint: delivery pruning equals
   output pruning; unchanged.
6. `nodes = [_to_schema_node(node) for node in result]` — the read-only
   `SchemaNode` projection → checkpoint: the projection already exists and is
   exactly the contract's `Node content` list (path, description, types,
   usages, dependencies as `DependencyFacts` records, children, tools).
7. `hooks.validate_schema(nodes)`; a not-approved `GateVerdict` → one merged
   `ValueError` → checkpoint: the gate now runs over the very list that is
   returned — observe-and-veto, the gate input and the return value are one
   object graph.
8. **Output**: `return nodes` — `list[SchemaNode]`; the `json.dumps` tail is
   deleted → checkpoint: type matches the signature `-> tree:
   list[SchemaNode]`; the wrapper owns serialization.

#### Checkpoint Summary

- Return type vs `SchemaNode` contract: passed (field-for-field).
- Gate-before-return ordering: passed (veto → no tree returned).
- Empty-tree early return preserved: passed.
- Serialization removal side effects: none in the domain (stdout is owned by
  the CLI wrapper).

### Trace: `goga.codegraph.codegraph` (changed)

#### Chain

1. **Input**: `cells`, `max_depth`, `depends_on`.
2. `load_project_config()` — absent `.goga/config.yml` →
   `FileNotFoundError(".goga/config.yml not found in project root")`;
   `config.language` outside the whitelist → `ValueError` naming the expected
   set; `config.lint` absent → no exclusions → checkpoint: producer failure
   modes unchanged (drift propagates them; the drift CLI maps them to exit
   2).
3. `discover_sources(language, ignore)` → files; `collect_facts` →
   `derive_units` → `resolve_links` (unparseable file → error naming the
   file) → checkpoint: unchanged.
4. `render_graph(units, links, cells, max_depth, depends_on)` now returns the
   filtered `list[CodegraphNode]` → checkpoint: the orchestrator's single
   `return render_graph(...)` line flows the new type through unchanged.
5. **Output**: `list[CodegraphNode]` — docstring/`-> str` annotations updated
   to the object contract.

#### Checkpoint Summary

- Pass-through return type: passed.
- Producer error surface unchanged: passed.

### Trace: `goga.codegraph.render_graph` (changed)

#### Chain

1. **Input**: `units: list[Unit]`, `links: list[CellLink]`, the three
   filters.
2. `_build_forest(units, links)` — cell units nested by path, non-cell units
   compressed into structural ancestors; `_filter_cells` →
   `_filter_by_depends_on` → `_prune_depth`, each rebuilding fresh frozen
   nodes → checkpoint: input records never mutated (constraints hold).
3. **Output**: `return roots` — the filtered `CodegraphNode` forest; the
   `if not roots: return "[]"` early exit, `asdict`, and `json.dumps` are
   deleted (an empty forest returns `[]` naturally) → checkpoint: the
   wrapper's `asdict` + `beautiful_json` reproduces the old serialization
   byte for byte.

#### Checkpoint Summary

- Empty-tree contract (`[]`): passed.
- Purity (`_with_children` rebuilds): passed.

### Trace: `goga.drift.DriftEntry` (new)

#### Chain

1. **Input**: constructed by `compare_views` with `kind`, `cell`, and either
   a sorted type list or `None`.
2. Frozen, keyword-only dataclass per the `convention` data-model rules;
   `__post_init__` copies the caller-owned `types` list (the family pattern
   of the facts records) → checkpoint: `types=None` is the recorded explicit
   absence (cell-level entry), satisfying the convention's `None` rule.
3. **Output**: immutable record consumed by `scope_entries` and serialized by
   the CLI wrapper.

#### Checkpoint Summary

- Convention compliance (frozen, kw_only, container copy): passed.

### Trace: `goga.drift.compare_views` (new)

#### Chain

1. **Input**: the two complete views — `schema_tree: list[SchemaNode]`,
   `codegraph_tree: list[CodegraphNode]`.
2. Index the declared view by a recursive walk: `{SchemaNode.path ->
   set(SchemaNode.types)}`, descending `children` → checkpoint: both fields
   exist on the live record (verified in `goga/schema/hooks/facts.py`).
3. Index the code-derived view the same way: `{CodegraphNode.cell ->
   set(CodegraphNode.types)}` → checkpoint: field exists (verified in
   `goga/codegraph/facts/facts.py`).
4. Cell-level entries: paths in `schema_index − codegraph_index` →
   `DriftEntry("schema_only", path, None)`; the reverse difference →
   `codegraph_only` → checkpoint: a cell-level entry carries no type list.
5. Type-level entries: for every shared path, `sorted(declared − code)` →
   one `schema_only` entry when non-empty; `sorted(code − declared)` → one
   `codegraph_only` entry when non-empty → checkpoint: set arithmetic makes
   the type lists sorted and duplicate-free by construction; a direction
   with no missing names emits nothing.
6. Sort by `(cell, kind)` → checkpoint: deterministic; `codegraph_only` < 
   `schema_only` lexicographically, both directions of one cell adjacent.
7. **Output**: `entries: list[DriftEntry]` — pure; the inputs are only read.

#### Checkpoint Summary

- No-double-reporting (cell-level never with type-level of the same cell):
  passed — mutually exclusive branches (path in exactly one view vs both).
- Both-directions-two-entries: passed.
- Purity: passed (frozen inputs; only derived lists built).

### Trace: `goga.drift.scope_entries` (new)

#### Chain

1. **Input**: `entries` (facts of the complete views), the two filtered
   views.
2. Collect surviving paths — the union of every `SchemaNode.path` walk of
   `schema_tree` and every `CodegraphNode.cell` walk of `codegraph_tree` →
   checkpoint: union semantics — survival in at least one view, never both
   required; this is the guard that makes the `depends_on` asymmetry
   (declared dependencies vs resolved imports) unable to fabricate entries.
3. Keep `entry` iff `entry.cell` is in the union; order preserved →
   checkpoint: survival is the only effect — no fabrication, alteration, or
   reordering.
4. **Output**: `report: list[DriftEntry]`.

#### Checkpoint Summary

- Union survival: passed.
- Order preservation: passed (list comprehension over the input order).

### Trace: `goga.drift.drift` (new)

#### Chain

1. **Input**: `cells`, `max_depth`, `depends_on` (defaults `[]`, `None`,
   `[]` — the CODEMANIFEST contract defaults, never mutated; `# noqa: B006`
   per the family precedent).
2. `complete_schema = schema([], None, [])`;
   `complete_codegraph = codegraph([], None, [])` → checkpoint: comparison
   facts come from the complete views; the schema call delivers the hooks
   checkpoints to every cell of the complete run (each call builds its own
   `SchemaHooks` registry — one run per call, per the `checkpoints`
   practice).
3. `filtered_schema = schema(cells, max_depth, depends_on)`;
   `filtered_codegraph = codegraph(cells, max_depth, depends_on)` →
   checkpoint: the same filters apply to both views; a producer error here
   propagates unchanged (the comparison adds no failures of its own).
4. `entries = compare_views(complete_schema, complete_codegraph)`.
5. `report = scope_entries(entries, filtered_schema, filtered_codegraph)`.
6. **Output**: `report` — the scoped entries in the stable order; `[]` when
   the views agree.

#### Checkpoint Summary

- Complete-view comparison + filter scoping: passed (the deliberate four
  producer calls — the accepted cost of the precision contract; a diagnostic
  CLI, not a hot path).
- Error pass-through: passed (no try/except in the domain routine).

### Trace: `goga/commands/schema` CLI `schema` (changed)

#### Chain

1. **Input**: click surface unchanged — `CELLS` variadic argument,
   `--max-depth`, repeatable `--depends-on`; `ctx` for exits.
2. `schema_logic(list(cells), max_depth, list(depends_on))`; any `Exception`
   → `click.echo(str(e), err=True)` + `ctx.exit(1)` → checkpoint: unchanged
   failure contract.
3. **New step 3** — project the returned tree: `_project_node(node)` maps
   `SchemaNode.path → "cell"`, `description`, `types`, `usages`,
   `dependencies` → `{record.path: {"types": [...], "usages": [...]}}` over
   the `DependencyFacts` records, `children` recursively, and `"tools"` only
   when the overlay is non-empty → checkpoint: the projected key set and
   value shapes equal the pre-refactor serialized node exactly (the old
   `json.dumps` consumed precisely this dict structure); `sort_keys=True`
   makes key order irrelevant.
4. `click.echo(json.dumps(projected, indent=4, sort_keys=True,
   ensure_ascii=False))` (the `beautiful_json` practice) → checkpoint:
   byte-identity with the pre-refactor CLI output (C2), including `"[]"` for
   the empty tree.
5. **Output**: stdout JSON only; exit 0.

#### Checkpoint Summary

- Byte-identity mechanism: passed (projection rebuilds the exact legacy dict
  shape; the tools key is written iff non-empty — never `{}`).
- Exit codes: unchanged (0 success / 1 failure).

### Trace: `goga/commands/codegraph` CLI `codegraph` (changed)

#### Chain

1. **Input**: unchanged click surface.
2. `codegraph_logic(...)`; exception → stderr + `ctx.exit(1)` → checkpoint:
   unchanged.
3. **New step 3** — `document = [asdict(node) for node in tree]`
   (`dataclasses.asdict` recurses into children and the dependencies dict);
   `click.echo(json.dumps(document, indent=4, sort_keys=True,
   ensure_ascii=False))` → checkpoint: the transformation is the very one
   the old `render_graph` performed (`[asdict(root) for root in roots]`) —
   byte-identity by construction.
4. **Output**: stdout JSON only; exit 0.

#### Checkpoint Summary

- 1:1 field mapping (cell, types, dependencies, children): passed — the
  record fields are the output keys, no projection needed.

### Trace: `goga/commands/drift` CLI `drift` (new)

#### Chain

1. **Input**: `CELLS` variadic argument, `--max-depth`, repeatable
   `--depends-on` — the family surface, declared via the `click` practice.
2. `drift_logic(list(cells), max_depth, list(depends_on))`; any `Exception`
   — uninitialized project (`FileNotFoundError`), unsupported language or
   unparseable source (`ValueError`), manifest loading/validation failures
   (`ValueError`), hard checkpoint failures — → `click.echo(str(e), err=True)`
   + `ctx.exit(2)` → checkpoint: nothing on stdout, no raw traceback; exit 2
   is the deliberate, permanent family deviation (three-outcome contract).
3. Project each `DriftEntry`: `{"kind": ..., "cell": ...}` plus
   `"types": list(entry.types)` only when `entry.types is not None` →
   checkpoint: the `types` key's absence marks a cell-level entry — matches
   the documented report structure.
4. `click.echo(json.dumps(projected, indent=4, sort_keys=True,
   ensure_ascii=False))` (the `beautiful_json` practice).
5. `if report: ctx.exit(1)`; otherwise fall through → exit 0 → checkpoint:
   0 = completed + no discrepancies (an empty list is printed), 1 =
   completed + discrepancies (the full report is printed), 2 = could not
   perform. The command callback uses `ctx.exit(...)`, never `sys.exit`
   (click anti-pattern rule).
6. **Output**: stdout — the flat JSON array; the command docstring is the
   user-facing help documenting the report structure and the three
   statuses.

#### Checkpoint Summary

- Three-outcome exit contract: passed.
- Help-format obligation: passed (docstring mirrors the schema/codegraph
  helps; `\b` blocks for the report structure and the exit codes).

### Trace: `goga.commands` facade + `goga.app` (changed)

#### Chain

1. `goga/commands/__init__.py`: `from .drift import drift` (alphabetical
   position: after `contract`, before `history`) and `"drift"` in `__all__`
   → checkpoint: the import resolves against `goga/commands/drift/__init__.py`
   re-exporting `drift` from `drift.py`.
2. `goga/cli.py`: `drift` added to the `from .commands import (...)` block
   (alphabetical) and `app.add_command(drift)` after `add_command(codegraph)`
   → checkpoint: the registration order matches the `app()` `Commands:` list
   of the root manifest (schema, codegraph, drift, contract, …).
3. **Output**: `goga drift` reachable through the CLI group; the facade
   import line of `cli-commands.md` stays accurate (18 commands).

#### Checkpoint Summary

- Facade re-export chain (drift.py → subcell __init__ → facade → root):
  passed.

## Algorithm Design

### `goga/drift/compare.py` — module plan

**Responsibility**: the drift record vocabulary and the pure comparison
core. No I/O, no filters, no producers.

```python
"""Comparison core — the drift entries of the two complete views and their scoping.

The module owns the flat report record and the two pure steps over the view
trees: the name-level comparison of the complete views and the survival
scoping over the filtered views. No filters are applied here — the entries
are facts of the views passed in.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..codegraph.facts import CodegraphNode
from ..schema.hooks import SchemaNode

SCHEMA_ONLY = "schema_only"
CODEGRAPH_ONLY = "codegraph_only"


@dataclass(frozen=True, kw_only=True)
class DriftEntry:
    """One flat entry of the drift report.

    Args:
        kind: Direction of the discrepancy — ``schema_only`` or
            ``codegraph_only``.
        cell: Normalized cell path of the discrepancy subject.
        types: Sorted type names of the cell missing from the other view;
            ``None`` marks a cell-level discrepancy.
    """

    kind: str
    cell: str
    types: list[str] | None = None

    def __post_init__(self) -> None:
        """Copy the caller-owned type list into a fresh list."""
        if self.types is not None:
            object.__setattr__(self, "types", list(self.types))
```

The two kind literals are module-level constants (`SCHEMA_ONLY`,
`CODEGRAPH_ONLY`) — the literal values `"schema_only"` / `"codegraph_only"`
are the serialized contract and never change.

### `DriftEntry`

**Responsibility**: the immutable report record (Entity with properties
only).

**Algorithm:** construction only — `__post_init__` copies the `types` list.

**Errors:** none (a pure record).

**Edge Cases:**
- `types is None` → cell-level entry; serialized without a `types` key.
- Duplicate names in `types` → impossible by construction (set-derived).

### `compare_views`

**Responsibility**: every structural discrepancy of the two complete views.

**Algorithm:**
```
1. build schema_index: walk schema_tree recursively (node + children)
   → {SchemaNode.path: set(SchemaNode.types)}
2. build codegraph_index: walk codegraph_tree recursively
   → {CodegraphNode.cell: set(CodegraphNode.types)}
3. FOR path IN schema_index.keys() - codegraph_index.keys():
   - append DriftEntry(kind=SCHEMA_ONLY, cell=path, types=None)
4. FOR path IN codegraph_index.keys() - schema_index.keys():
   - append DriftEntry(kind=CODEGRAPH_ONLY, cell=path, types=None)
5. FOR path IN schema_index.keys() & codegraph_index.keys():
   - declared_only = sorted(schema_index[path] - codegraph_index[path])
   - code_only = sorted(codegraph_index[path] - schema_index[path])
   - IF declared_only: append DriftEntry(SCHEMA_ONLY, path, declared_only)
   - IF code_only: append DriftEntry(CODEGRAPH_ONLY, path, code_only)
6. entries.sort(key=(cell, kind))
   → return entries
```

**Errors:** none — pure.

**Edge Cases:**
- Both views empty → `[]`.
- Agreement on every cell → `[]`.
- A cell with drift in both directions → exactly two entries (steps 5 both
  branches).
- Deep nesting → the recursive walks flatten the full tree, not just roots.

### `scope_entries`

**Responsibility**: survival scoping of the computed entries.

**Algorithm:**
```
1. surviving = {every SchemaNode.path of schema_tree (recursive walk)}
   | {every CodegraphNode.cell of codegraph_tree (recursive walk)}
2. return [entry for entry in entries if entry.cell in surviving]
```

**Errors:** none — pure.

**Edge Cases:**
- Empty filtered views (both) → every entry dropped → `[]`.
- Entry cell surviving in exactly one view → kept (union).
- `entries=[]` → `[]` regardless of the views.

### `goga/drift/drift.py`

**Responsibility**: the entry routine — produce the scoped report.

**Algorithm:**
```
1. complete_schema = schema([], None, [])
   complete_codegraph = codegraph([], None, [])
2. filtered_schema = schema(cells, max_depth, depends_on)
   filtered_codegraph = codegraph(cells, max_depth, depends_on)
3. entries = compare_views(complete_schema, complete_codegraph)
4. report = scope_entries(entries, filtered_schema, filtered_codegraph)
   → return report
```

**Errors:** every producer error propagates unchanged — no interception, no
wrapping, no added failures.

**Edge Cases:**
- Healthy project → `[]`.
- Filters excluding all drifted cells → `[]` (facts computed, nothing
  survives).
- A producer failing on the *filtered* call after the complete call
  succeeded → propagates (exit 2 at the CLI).

### `goga/schema/schema.py` — refactor

**Responsibility**: unchanged generation; the return contract becomes the
`SchemaNode` tree.

**Algorithm** (delta only):
```
6. nodes = [_to_schema_node(node) for node in result]   # built once
7. verdict = hooks.validate_schema(nodes)
   IF not verdict.approved → raise merged ValueError
8. return nodes                                          # was: json.dumps(result)
```
Step 4's early return becomes `if not result: return []`. The `json` import
and the `-> str` annotation leave; the docstring documents
`list[SchemaNode]` and the caller-owns-serialization rule.

**Errors:** unchanged (`ValueError` AST/gate/checkpoint, `ImportError`
register facade).

**Edge Cases:** unchanged (empty tree pre-checkpoint; filters prune delivery
exactly as output).

### `goga/codegraph/render.py` — refactor

**Algorithm** (delta only): delete the empty-forest early exit and the
`asdict`/`json.dumps` tail; `return roots`. The `json`/`asdict` imports
leave; the module docstring drops the serialization sentence.

### `goga/commands/schema/schema.py` — refactor

**Algorithm** (delta only): add the module-level private projector and
serialize its output:

```python
def _project_node(node: SchemaNode) -> dict:
    """Project one read-only schema node onto the family JSON output shape."""
    projected = {
        "cell": node.path,
        "description": node.description,
        "types": list(node.types),
        "usages": list(node.usages),
        "dependencies": {
            dep.path: {"types": list(dep.types), "usages": list(dep.usages)}
            for dep in node.dependencies
        },
        "children": [_project_node(child) for child in node.children],
    }

    if node.tools:
        projected["tools"] = node.tools

    return projected
```

Callback tail: `click.echo(json.dumps([_project_node(n) for n in result],
indent=4, sort_keys=True, ensure_ascii=False))`. The help docstring is
unchanged (the documented JSON structure is exactly what the projection
emits).

### `goga/commands/codegraph/codegraph.py` — refactor

**Algorithm** (delta only): callback tail becomes
`click.echo(json.dumps([asdict(n) for n in result], indent=4, sort_keys=True,
ensure_ascii=False))` with `from dataclasses import asdict`. Help docstring
unchanged.

### `goga/commands/drift/drift.py`

**Responsibility**: the CLI wrapper — surface, three exits, serialization.

**Algorithm:**
```
1. report = drift_logic(list(cells), max_depth, list(depends_on))
2. ON Exception e:
   - click.echo(str(e), err=True); ctx.exit(2)
3. projected = [_project_entry(entry) for entry in report]
   click.echo(json.dumps(projected, indent=4, sort_keys=True,
   ensure_ascii=False))
4. IF report: ctx.exit(1)   ELSE: return (exit 0)
```

```python
def _project_entry(entry: DriftEntry) -> dict:
    """Project one drift entry onto the family JSON output shape."""
    projected = {"kind": entry.kind, "cell": entry.cell}

    if entry.types is not None:
        projected["types"] = list(entry.types)

    return projected
```

Command docstring (user-facing help, family style — no Args/Returns/Raises
sections, `\b` blocks for structure):

```python
"""Report contract drift between declared manifests and actual code.

Compares the declared contract view (goga schema) with the code-derived
view (goga codegraph) and prints the flat JSON report of their
structural discrepancies to stdout. Discrepancies are computed on the
complete views; the filters scope the report only.

Every diagnostic goes to stderr; stdout carries the JSON report only.

\b
JSON report entries (sorted by cell path then kind):
  kind   - "schema_only" or "codegraph_only"
  cell   - normalized path of the discrepancy subject
  types  - sorted type names missing from the other view; present
           only on type-level entries — its absence marks a
           cell-level discrepancy

\b
Exit codes:
  0 - comparison completed, no discrepancies
  1 - comparison completed, discrepancies found
  2 - comparison could not be performed
"""
```

**Errors:** every `drift_logic` failure → one clean stderr line, exit 2.

**Edge Cases:**
- Empty report → prints `[]`, exit 0.
- Report with entries → prints the full report, exit 1.
- Repeated runs → byte-identical stdout (deterministic producers, stable
  order, sorted keys).

### Facade and root registration

`goga/drift/__init__.py`:

```python
"""Facade of the drift cell — the structural drift report between the declared and code-derived views."""

from .compare import DriftEntry, compare_views, scope_entries
from .drift import drift

__all__ = [
    "DriftEntry",
    "compare_views",
    "drift",
    "scope_entries",
]
```

`goga/commands/drift/__init__.py`:

```python
from .drift import drift

__all__ = ["drift"]
```

`goga/commands/__init__.py`: `from .drift import drift` (after
`from .contract import contract`), `"drift"` in `__all__` (same position).
`goga/cli.py`: `drift` in the facade import block (alphabetical),
`app.add_command(drift)` directly after `app.add_command(codegraph)`.

## Cross-cutting Concerns

- **Error handling**: the domain layers propagate (`schema` raises
  `ValueError`/`ImportError`; `codegraph` raises `FileNotFoundError`/
  `ValueError`; `drift` adds nothing). The command layer is the single
  translation point: `str(e)` → stderr → `ctx.exit(1)` (schema, codegraph)
  or `ctx.exit(2)` (drift). No wrapping, no traceback, stdout stays clean.
- **Logging**: no logging is added anywhere — the family is silent on
  stdout-data paths and speaks only through stderr diagnostics; the
  `convention` logging rules therefore do not change any behavior here.
- **Validation**: no new input validation — the click surface validates
  types (`--max-depth` is `int`); the producers own every semantic
  validation (language whitelist, manifest parseability, checkpoint
  contracts).
- **Caching**: none. Each `drift()` run performs two `schema()` and two
  `codegraph()` calls by design; the schema AST re-parse cost is the
  accepted price of the complete-view precision contract. No cross-run
  state exists (read-only, stateless).
- **Concurrency**: no shared mutable state; frozen records; the routines are
  safe under concurrent invocation (each call builds its own `SchemaHooks`
  registry per the `checkpoints` practice).
- **Determinism**: producers are deterministic; `compare_views` sorts by
  `(cell, kind)`; serialization uses `sort_keys=True` — identical project
  state and filters produce byte-identical reports.

## Usages Analysis

### `convention` (`.goga/usages/conventions.md`)
- **What it provides**: mandatory Python rules — relative imports,
  frozen/kw_only dataclasses, Google docstrings, CLI docstring exceptions,
  formatting, test structure.
- **Where used**: every touched module; `DriftEntry` (data-model rules);
  all test files.
- **Why chosen**: project-wide base practice.
- **How exactly**: relative imports for intra-package references
  (`from ..schema import schema` inside `goga/drift`); command docstrings
  without Args/Returns/Raises; tests mirror the source layout
  (`tests/drift/test_compare.py`, `tests/commands/drift/test_drift.py`).

### `click` (`.goga/usages/cooks/click.md`)
- **What it provides**: the CLI framework patterns — decorators, variadic
  arguments, repeatable options, `ctx.exit`, echo conventions.
- **Where used**: `goga/commands/drift/drift.py` (new); unchanged in the two
  sibling wrappers.
- **Why chosen**: the family framework (task Stack).
- **How exactly**: `@click.argument("cells", nargs=-1)`,
  `@click.option("--max-depth", type=int, default=None)`,
  `@click.option("--depends-on", multiple=True, ...)`, `@click.pass_context`,
  exits via `ctx.exit(code)` (never `sys.exit`), diagnostics via
  `click.echo(..., err=True)`.

### `beautiful_json` (`.goga/usages/cooks/beautiful_json.md`)
- **What it provides**: the family serialization —
  `json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.
- **Where used**: the three command wrappers (schema projection, codegraph
  `asdict` mapping, drift entry projection).
- **Why chosen**: byte-identity (C2) for the two refactored commands; family
  style for the new report.
- **How exactly**: exactly the call above, once per command, over the fully
  projected list.

### `documents` (inline, `goga/schema`)
- **What it provides**: AST loading contract (`AST(".")`, `.load()`,
  `.tree`, `.errors`).
- **Where used**: `schema()` step 1 (unchanged).
- **Why chosen / how**: unchanged by this task.

### Imported Usages

- `schema-usage` from `goga/schema` — how to call `schema()` and consume
  `list[SchemaNode]` (tree walk, field semantics, caller-owned
  serialization). Path: `goga/schema/.usages/schema-usage.md`. Consumed by
  `goga/drift` (`drift()` steps 1–2) and referenced in its global
  annotations.
- `codegraph-usage` from `goga/codegraph` — how to call `codegraph()` and
  consume `list[CodegraphNode]`. Path:
  `goga/codegraph/.usages/codegraph-usage.md`. Same consumer.
- `checkpoints` from `goga/schema/hooks` — the amend/gate delivery contract
  the schema routine fulfills internally. Path:
  `goga/schema/hooks/.usages/checkpoints.md`. Consumed by `goga/schema`
  (implementation) and `goga/commands/schema` (failure handling context).
- `registering-hooks` from `goga/schema` — tool-package subscription
  surface; context for the command's stderr behavior. Path:
  `goga/schema/.usages/registering-hooks.md`.
- `records` from `goga/codegraph/facts` — the record vocabulary
  (`CodegraphNode` construction rules) used by `render_graph`. Path:
  `goga/codegraph/facts/.usages/records.md`.
- `stages` from `goga/codegraph/analysis` — the three-stage pipeline order
  used by the orchestrator. Path:
  `goga/codegraph/analysis/.usages/stages.md`.
- `project-configuration` from `goga/config` — `load_project_config`
  semantics (language, lint exclusions). Path:
  `goga/config/.usages/project-configuration.md`.
- `drift-usage` from `goga/drift` — the report and failure contract behind
  the command. Path: `goga/drift/.usages/drift-usage.md`. Consumed by
  `goga/commands/drift`.
- `cli-commands` from `goga/commands` — the registration reference (18
  commands, import lines, add_command wiring, command table). Path:
  `goga/commands/.usages/cli-commands.md`. Consumed by `goga/cli.py`.

All connected practices are referenced in at least one annotation of their
manifests (verified: `goga lint` enforces reference resolution — 0 errors).

## `.usages/` Update

### Cell: `goga/schema`

- **`schema-usage.md`** → Status: **current** (rewritten by the apply stage
  to the object contract — return `list[SchemaNode]`, the field table, the
  caller-owned family serialization recipe). No further changes needed.
- **`registering-hooks.md`** → Status: current, untouched (tool-package
  subscription surface unchanged).

### Cell: `goga/codegraph`

- **`codegraph-usage.md`** → Status: **current** (object-tree contract, the
  field table, the one-to-one serialization note, drift named as a
  consumer). No further changes needed.

### Cell: `goga/drift` (new)

- **`drift-usage.md`** → Created: domain statement, import line, filter
  semantics, entry table with the four semantic kinds, serialization
  recipe, guarantees, failure behavior. Self-contained (no cross-practice
  references). No changes needed.

### Cell: `goga/commands/drift` (new)

- **`drift.md`** → Created: syntax, argument/option tables, the three exit
  codes, output field table, examples. No changes needed.

### Cell: `goga/commands`

- **`cli-commands.md`** → Status: **current** (18 commands; `drift` in all
  four lists). No changes needed.

### Cells: `goga/commands/schema`, `goga/commands/codegraph`

- **`schema.md`**, **`codegraph.md`** → Status: current, intentionally
  unchanged — they document CLI-level behavior (surface, output structure,
  exit codes), which is byte-identical before and after the refactor.

## Test Stack Trace

### General Setup

- Shared fixtures: `cwd` (tests/conftest.py) for CWD pinning;
  `pin_package_environment` / `empty_package_environment` for isolating the
  schema hooks registry — every module testing `schema()` (including the new
  `tests/drift/*`) uses the autouse `_empty_package_environment` pattern of
  `tests/schema/test_schema.py`.
- Planted projects live in `tmp_path`; `.goga/config.yml` carries
  `language: python`; helpers `_write_codemanifest` (tests/schema/conftest)
  are reused or mirrored locally in `tests/drift/conftest.py`.
- Python-cell fixtures put the public functions directly in `__init__.py`
  (the facade of a unit is derived from `__init__.py` — `__all__` or public
  declarations). **Never place a cross-unit import in `__init__.py`**: an
  imported name becomes a public binding and leaks into the unit's facade,
  producing an unintended `codegraph_only` type entry (verified by dry-run
  against the live producers). Cross-unit imports that must resolve as
  links go in a sibling module (e.g. `mix/impl.py`) — the link still
  resolves (link resolution is unit-wide) while the facade stays clean.
- All fixture expectations below were validated by dry-running the current
  `schema()`/`codegraph()` producers over the exact planted layouts and
  simulating `compare_views`/`scope_entries` — the printed views and
  reports match the asserted values entry for entry.

### Source File Registry

New: `goga/drift/{__init__,compare,drift}.py`,
`goga/commands/drift/{__init__,drift}.py`. Modified:
`goga/schema/schema.py`, `goga/codegraph/{codegraph,render}.py`,
`goga/commands/schema/schema.py`, `goga/commands/codegraph/codegraph.py`,
`goga/commands/__init__.py`, `goga/cli.py`. Tests:
`tests/drift/{__init__,conftest,test_compare,test_drift}.py`,
`tests/commands/drift/{__init__,test_drift}.py`; adapted:
`tests/schema/test_schema.py`, `tests/codegraph/{test_codegraph,test_render}.py`;
adapted (string-pinned suites — every remaining test that pins the
JSON-string domain return): `tests/schema/test_contract.py`,
`tests/commands/schema/test_schema.py`,
`tests/integration/test_schema_walk_gate_integration.py`; extended:
`tests/commands/test_commands_facade.py`, `tests/test_cli.py`.
Docs: `docs/features/drift/{index,cli,configuration,hooks,api}.md`,
`docs/features/index.md`, `docs/cli/index.md`.

---

### Positive Tests

#### `test_compare_views_reports_all_four_discrepancy_kinds`

**Setup**: none (records constructed inline — pure function).

**Input**:
```python
schema_tree = [SchemaNode(path="lib", description="", types=["thing"], usages=[],
                          dependencies=[], children=[], tools={}),
               SchemaNode(path="mix", description="", types=["run", "stale"], usages=[],
                          dependencies=[], children=[], tools={}),
               SchemaNode(path="ghost", description="", types=["phantom"], usages=[],
                          dependencies=[], children=[], tools={})]
codegraph_tree = [CodegraphNode(cell="lib", types=["thing"], dependencies={}, children=[]),
                  CodegraphNode(cell="mix", types=["run", "helper2"], dependencies={}, children=[]),
                  CodegraphNode(cell="extra", types=["helper"], dependencies={}, children=[])]
```

**Trace**:
```
compare_views(schema_tree, codegraph_tree)
  → _index_schema walk           # {lib: {thing}, mix: {run, stale}, ghost: {phantom}}
  → _index_codegraph walk        # {lib: {thing}, mix: {run, helper2}, extra: {helper}}
  → cell-level diff              # ghost schema_only; extra codegraph_only
  → type-level diff on mix       # declared−code = {stale}; code−declared = {helper2}
  → sort by (cell, kind)
  returns: [extra/cg, ghost/sc, mix/cg(helper2), mix/sc(stale)]
```

**Assertions**:
```python
entries = compare_views(schema_tree, codegraph_tree)
assert [(e.kind, e.cell, e.types) for e in entries] == [
    ("codegraph_only", "extra", None),
    ("schema_only", "ghost", None),
    ("codegraph_only", "mix", ["helper2"]),
    ("schema_only", "mix", ["stale"]),
]
```

**Sufficiency**: pins the four semantic kinds, the grouped encoding, the
`(cell, kind)` order, and sorted type lists in one regression net — the core
PRD R4 contract.

#### `test_compare_views_agreeing_views_yield_empty_list`

**Setup/Input**: two single-cell views over the same path `pkg` with
identical type sets `{run}` (records as above).

**Trace**: indexes equal → both differences empty → `[]`.

**Assertions**: `assert compare_views(s, c) == []`

**Sufficiency**: the healthy-path contract — prevents the report from
inventing entries when nothing differs.

#### `test_scope_entries_keeps_entry_surviving_in_one_view_only`

**Setup**: entry for cell `mix`; filtered schema view without `mix`;
filtered codegraph view with `mix`.

**Input**:
```python
entries = [DriftEntry(kind="schema_only", cell="mix", types=["stale"])]
schema_tree = []                                  # mix pruned by declared-dep asymmetry
codegraph_tree = [CodegraphNode(cell="mix", types=["run"], dependencies={}, children=[])]
```

**Trace**: surviving = `{mix}` (union) → the entry survives.

**Assertions**: `assert scope_entries(entries, [], codegraph_tree) == entries`

**Sufficiency**: the union-survival rule — the `depends_on` asymmetry guard;
a both-views-required implementation would drop the entry.

#### `test_drift_reports_planted_discrepancies_all_four_kinds`

**Setup** (`tmp_path` + `_cwd`, autouse empty package environment):
```
.goga/config.yml   → "language: python"
lib/__init__.py    → "def thing() -> None: ..."
lib/CODEMANIFEST   → declares routine thing
mix/__init__.py    → "def run() -> None: ..." + "def helper2() -> None: ..."
mix/CODEMANIFEST   → declares routines run, stale
extra/__init__.py  → "def helper() -> None: ..."
ghost/CODEMANIFEST → declares routine phantom        # no .py files
```

**Input**: `drift([], None, [])`

**Trace**:
```
drift()
  → schema([], None, [])      # {lib:{thing}, mix:{run,stale}, ghost:{phantom}}
  → codegraph([], None, [])   # {lib:{thing}, mix:{run,helper2}, extra:{helper}}
  → compare_views             # 4 entries (mix both directions)
  → scope_entries (no filters — all cells survive)
  returns: 4 entries
```

**Assertions**:
```python
report = drift([], None, [])
assert [(e.kind, e.cell, e.types) for e in report] == [
    ("codegraph_only", "extra", None),
    ("schema_only", "ghost", None),
    ("codegraph_only", "mix", ["helper2"]),
    ("schema_only", "mix", ["stale"]),
]
```

**Sufficiency**: the integration acceptance — the PRD's "nothing extra,
nothing missing" over a real filesystem with real producers.

#### `test_drift_cli_discrepancies_exit_1_and_print_full_report`

**Setup**: the four-kinds project above; `CliRunner`.

**Input**: `runner.invoke(app, ["drift"])`

**Trace**:
```
drift callback → drift_logic([], None, []) → 4 entries
  → _project_entry ×4 → json.dumps(..., indent=4, sort_keys=True) → click.echo
  → report non-empty → ctx.exit(1)
```

**Assertions**:
```python
assert result.exit_code == 1
data = json.loads(result.output)
assert data == [
    {"cell": "extra", "kind": "codegraph_only"},
    {"cell": "ghost", "kind": "schema_only"},
    {"cell": "mix", "kind": "codegraph_only", "types": ["helper2"]},
    {"cell": "mix", "kind": "schema_only", "types": ["stale"]},
]
assert result.output.endswith("\n")  # single echo line
```

**Sufficiency**: the three-outcome contract's discrepancy branch — exit 1
reserved for found discrepancies, full report on stdout, `types` key only on
type-level entries.

#### `test_drift_cli_agreement_exit_0_prints_empty_list`

**Setup**: healthy project — `.goga/config.yml`; `pkg/__init__.py` with
`def run() -> None: ...`; `pkg/CODEMANIFEST` declaring routine `run`.

**Input**: `runner.invoke(app, ["drift"])`

**Trace**: views agree → report `[]` → echo `"[]"` → exit 0.

**Assertions**: `assert result.exit_code == 0` and
`assert json.loads(result.output) == []`.

**Sufficiency**: the healthy-path exit code — 0 must mean completed-with-no-
discrepancies, not merely success.

#### `test_schema_domain_returns_schema_node_tree` (adapted suite)

**Setup**: existing walk-project fixtures of `tests/schema/conftest.py`.

**Input**: `schema([], None, [])`

**Trace**: generation as today; the gate projection becomes the return.

**Assertions**: `result` is `list[SchemaNode]`; the root `result[0].path`,
`.types`, `.children[0]...` match the previous JSON expectations
(`json.loads` call sites become direct attribute checks);
`schema([...], 0, [])` (max-depth 0 empty case) returns `[]` where the old
suite pinned `"[]"`.

**Sufficiency**: adapts the domain suite to the object contract with
expectations preserved (C2 regression net at the domain level).

#### `test_schema_returns_schema_node_list` (adapted `tests/schema/test_contract.py`)

**Setup**: none (signature introspection).

**Input**: `typing.get_type_hints(schema)`.

**Trace**: the contract test inspects the facade signature; only the
return-annotation check changes with the refactor.

**Assertions**: `hints["return"]` is `list[SchemaNode]` (was `str`; the
test renames from `test_schema_returns_str`); the parameter checks
(`cells`, `max_depth`, `depends_on` and their types) stay unchanged.

**Sufficiency**: the facade contract test must pin the new return type —
left unadapted it fails on the `str` assertion and blocks the gate.

#### String-pinned suite adaptations (`tests/commands/schema/test_schema.py`, `tests/integration/test_schema_walk_gate_integration.py`)

Every remaining caller of the domain routines that consumed the JSON
string adapts with its expectation preserved:

- Routine-vs-CLI equivalence (`tests/commands/schema/test_schema.py`):
  `routine_output = schema_logic([], None, [])` becomes the object tree;
  the equivalence assertion becomes
  `json.loads(cli_result.output) == [_project_node(n) for n in routine_output]`
  using the wrapper's projector — the tested fact (routine and CLI
  produce the same extended tree) is unchanged.
- Determinism over routine outputs (same file): `set(routine_outputs)`
  over a list of frozen records is unhashable — compare object trees
  directly: `routine_outputs[0] == routine_outputs[1] == routine_outputs[2]`
  (frozen-dataclass equality), keeping the CLI-side `set(cli_outputs)`
  string check as is.
- Gate integration (`tests/integration/test_schema_walk_gate_integration.py`):
  the `json.loads(result)` sites become direct `SchemaNode` attribute
  checks (`result[0].tools == {"docs": {"score": 3}}`,
  `result[0].children[0].tools == ...`, and a seven-field check over
  `dataclasses.fields(result[0])` replacing the key-set assertion); the
  `result == GATE_GOLDEN` string-golden comparison serializes the object
  tree through the wrapper projection + `beautiful_json` and compares
  against the same golden — byte-for-byte expectation preserved.
- CLI-level suites that pin only `json.loads(result.output)` of the
  command stdout (`tests/integration/test_codegraph_cli_integration.py`,
  `tests/integration/test_integration_split.py`) need no changes — the
  CLI output is byte-identical by construction (C2).

#### `test_schema_cli_output_byte_identical_golden` (new, capture before refactor)

**Setup**: golden stdout strings captured from the current CLI **before**
the refactor (full run + each filter form: cells, `--max-depth`,
`--depends-on`, empty tree) over the walk-project fixture.

**Input**: `runner.invoke(app, ["schema", ...])` per form.

**Trace**: wrapper → `schema_logic` → projection → serialization → echo.

**Assertions**: `assert result.output == GOLDEN_FULL` etc. for every form.

**Sufficiency**: carries the C2 byte-identical guarantee at CLI level — the
single most important regression net of the refactor.

#### `test_codegraph_cli_output_byte_identical_golden`

Identical construction for `codegraph` (full run + filter forms; the
`"[]"` empty-project case included).

#### `test_facade_reexports_drift` / `test_drift_command_registered`

**Setup**: none (imports).

**Input**: `from goga.commands import drift as facade_drift`;
`app.commands`.

**Trace**: subcell `__init__` re-export → facade `__all__` → root group
registration.

**Assertions**: `facade_drift is goga.commands.drift.drift`;
`"drift" in commands.__all__`; `isinstance(drift, click.Command)`;
`"drift" in app.commands`.

**Sufficiency**: the registration chain — a broken link anywhere leaves the
command unreachable.

---

### Negative Tests

#### `test_drift_cli_uninitialized_project_exit_2_clean_stderr`

**Setup**: `tmp_path` with the four-kinds project **minus**
`.goga/config.yml`; `_cwd(tmp_path)`.

**Input**: `runner.invoke(app, ["drift"])`

**Trace**:
```
drift callback → drift_logic
  → schema([], None, [])       # succeeds — manifests parse
  → codegraph([], None, [])    # load_project_config raises
    FileNotFoundError(".goga/config.yml not found in project root")
  → propagates unchanged → callback except: echo(str(e), err=True); ctx.exit(2)
```

**Assertions**:
```python
assert result.exit_code == 2
assert result.stdout == ""                     # stdout carries nothing (click>=8.2: output merges stderr)
assert ".goga/config.yml" in (result.stderr or "")  # the clean reason
```

**Sufficiency**: the exit-2 branch — execution failure must print nothing to
stdout and state the reason on stderr; also pins the deliberate deviation
from the family's exit-1 failure convention.

#### `test_drift_propagates_ast_parse_error`

**Setup**: `.goga/config.yml` + one invalid-YAML `CODEMANIFEST`.

**Input**: `drift([], None, [])` (direct call).

**Trace**: `schema()` → `AST.load()` records errors → `ValueError("AST
parsing failed with 1 error(s)")` propagates through `drift`.

**Assertions**: `with pytest.raises(ValueError, match="AST parsing failed
with 1 error")`.

**Sufficiency**: producer errors pass through the comparison unchanged — no
swallowing, no wrapping.

#### `test_drift_propagates_unsupported_language_error`

**Setup**: `.goga/config.yml` with `language: rust`.

**Input**: `drift([], None, [])`.

**Trace**: `codegraph()` → `ValueError("unsupported language: 'rust'; ...")`
propagates.

**Assertions**: `pytest.raises(ValueError, match="unsupported language")`.

**Sufficiency**: C3 — an unsupported language is an execution failure, never
an empty report.

#### `test_drift_cli_ast_error_exit_2`

The CLI face of the AST case: `runner.invoke(app, ["drift"])` → exit 2,
`result.stdout == ""` (click ≥ 8.2: `result.output` merges stderr — assert
the dedicated `result.stdout` stream), stderr naming the parse failure.

---

### Edge Case Tests

#### `test_compare_views_empty_views_yield_empty_list`

**Input**: `compare_views([], [])` → **Assertions**: `== []`.
**Sufficiency**: empty-project boundary (both producers legitimately return
empty trees).

#### `test_compare_views_collects_nested_children`

**Setup**: schema tree `a → a/b` with type drift only on `a/b`;
codegraph tree with the same two paths (codegraph nesting via structural
compression verified in the planted-project test).

**Input**: the two two-level trees.

**Trace**: recursive index walks reach `a/b` → the entry targets `a/b`, not
`a`.

**Assertions**: exactly one entry, `cell == "a/b"`, kinds/types as planted.
**Sufficiency**: root-only indexing would silently miss every nested cell.

#### `test_compare_views_pure_inputs_unmutated`

**Input**: deep-copied views; run; compare against the copies.
**Assertions**: trees equal the copies.
**Sufficiency**: the purity requirement (frozen records still hold mutable
lists — the walk must only read).

#### `test_compare_views_cell_level_never_coexists_with_type_level`

**Input**: `ghost` present only in the schema view with types `["phantom"]`.
**Assertions**: exactly one entry for `ghost`, `types is None`.
**Sufficiency**: the no-double-reporting rule — a cell-level subject never
also emits type-level entries.

#### `test_scope_entries_preserves_input_order`

**Input**: entries deliberately out of sorted order (constructed directly);
a surviving set covering all.
**Assertions**: output order equals the constructed input order.
**Sufficiency**: `scope_entries` must not re-sort — ordering belongs to
`compare_views` alone.

#### `test_scope_entries_empty_filtered_views_drop_everything`

**Input**: non-empty `entries`; `scope_entries(entries, [], [])`.
**Assertions**: `== []`.
**Sufficiency**: the boundary of maximal filtering.

#### `test_drift_cells_filter_scopes_report_only`

**Setup**: the four-kinds project.

**Input**: `drift(["ghost"], None, [])`

**Trace**: complete views still compared (4 entries computed); filtered
schema view keeps `ghost`; filtered codegraph view is empty; union
`{ghost}` → only the ghost entry survives.

**Assertions**: exactly `[("schema_only", "ghost", None)]`.
**Sufficiency**: scope-gating — filters select what is reported, never what
is compared.

#### `test_drift_depends_on_asymmetry_never_fabricates_entries`

**Setup**: healthy-plus project — `lib` (declared `thing`, code exports
`thing`), `mix` (declared `run`; `mix/__init__.py` defines `run` only;
`mix/impl.py` does `from lib import thing` — the import lives in a sibling
module so it never leaks into the facade, and the link mix→lib still
resolves); **no** cell declares a manifest dependency on `lib`. Dry-run
confirmation: schema view `{lib: {thing}, mix: {run}}`, codegraph view the
same; `schema(["lib"])` filters to `[]`, `codegraph(["lib"])` keeps `mix`.

**Input**: `drift([], None, ["lib"])`

**Trace**:
```
complete views agree             # entries = []
schema(["lib"])   → no declared dep on lib anywhere → []
codegraph(["lib"]) → mix imports lib → mix survives
direct filtered-tree comparison would fabricate "mix schema_only"
scope_entries([], ...) → []     # facts come from the complete views
```

**Assertions**: `report == []`.
**Sufficiency**: the PRD precision contract's sharpest edge — the pass-
through variant this design replaces would fail it.

#### `test_drift_max_depth_scopes_report`

**Setup**: `a` (declared + code, agrees); `a/b` nested in both views with
`schema_only ["stale"]` drift (`a/b/CODEMANIFEST` declares `run, stale`;
`a/b/__init__.py` defines `run`; `a/__init__.py` defines its declared name —
both views nest `a/b` under `a`).

**Input**: full run → one `a/b` entry; `drift([], 0, [])`.

**Trace**: `max_depth=0` keeps only roots → both filtered views lose `a/b`
→ the entry dies.

**Assertions**: `drift([], None, [])` has the `a/b` entry;
`drift([], 0, []) == []`.
**Sufficiency**: the depth filter's scope-gating parity across both views.

#### `test_drift_deterministic_and_read_only`

**Setup**: four-kinds project.

**Input**: two consecutive `drift([], None, [])` runs; a pre-run snapshot of
the tree (paths + contents).

**Assertions**: the two reports equal; the tree snapshot equals the
post-run snapshot.
**Sufficiency**: C5/R10 — determinism and read-only as observable behavior.

#### `test_drift_cli_repeated_runs_byte_identical`

**Input**: two `runner.invoke(app, ["drift"])`.
**Assertions**: `result1.output == result2.output`; both exit 1.
**Sufficiency**: the CLI-level determinism guarantee.

#### `test_drift_cli_help_documents_surface_report_and_statuses`

**Input**: `runner.invoke(app, ["drift", "--help"])`.

**Assertions**:
```python
result = runner.invoke(app, ["drift", "--help"])
assert result.exit_code == 0
assert "CELLS" in result.output          # the argument surface
assert "--max-depth" in result.output    # the option surface
assert "--depends-on" in result.output
assert "kind" in result.output and "cell" in result.output and "types" in result.output
assert "schema_only" in result.output and "codegraph_only" in result.output
assert "0" in result.output and "1" in result.output and "2" in result.output
```

**Sufficiency**: pins the CODEMANIFEST help obligation in full — the
surface (a typo in an option name breaks every filter invocation through
the CLI while the domain-level filter tests still pass), the report
structure, and the three exit-code lines; mirrors the codegraph help
test exactly (family convention; agents read the help to parse the
output).

#### `test_drift_entry_is_frozen_kw_only_record`

**Input**: `DriftEntry(kind="schema_only", cell="x", types=["a"])`.
**Assertions**: positional construction raises `TypeError`; attribute
assignment raises `FrozenInstanceError`; `types` list copied (mutating the
source list does not change the entry).
**Sufficiency**: the `convention` data-model rules on the new record.

#### `test_render_graph_returns_unserialized_object_tree` (adapted)

**Input**: existing render fixtures.
**Trace**: forest → filters → `roots` returned directly.
**Assertions**: elements are `CodegraphNode`; the empty case `== []` (was
`== "[]"`); filter parity assertions unchanged.
**Sufficiency**: pins the refactored return contract of `render_graph`.

## Additional Instructions for the Implementation Agent

- Implement in the arch-plan order (leaves → root): schema domain →
  codegraph domain → drift domain → the three command wrappers (schema,
  codegraph, drift) → facade → root CLI. Tests and docs follow each step.
- **Capture the golden CLI outputs before touching the domains** — run the
  current `goga schema` / `goga codegraph` over the fixed walk/codegraph
  fixtures and embed the stdout strings; those goldens are the C2 net and
  must pass untouched after the refactor.
- Keep the domain internals (dict tree in `schema.py`, the
  `_to_schema_node` projection, the `render.py` filter helpers) — only the
  return tails change. Do not rewrite working filter logic.
- Preserve the empty-tree early return in `schema()` **before** checkpoint
  delivery (`return []`), and delete (not keep) the `"[]"` string exits in
  both domains.
- The mutable defaults `cells=[], depends_on=[]` in `drift()` carry
  `# noqa: B006` with the family comment (the CODEMANIFEST contract default;
  never mutated) — mirror `codegraph()`.
- Exits: `ctx.exit(2)` / `ctx.exit(1)` in the drift callback — never
  `sys.exit`, never `click.ClickException` (the family catches `Exception`
  broadly and echoes `str(e)` to stderr; keep that pattern).
- Module docstrings and Google-style docstrings on every public function;
  the three command docstrings are user-facing help (no Args/Returns/
  Raises; `\b` blocks; summary line in the command listing).
- `goga/drift` imports producers relatively (`from ..schema import schema`,
  `from ..codegraph import codegraph`); `goga/commands/drift` imports
  `from ...drift import DriftEntry, drift as drift_logic`.
- Documentation collateral (family page model): create
  `docs/features/drift/` — `index.md` (the two-view comparison model, four
  kinds, scope-gating), `cli.md` (normative synopsis/options/exit codes/
  output), `configuration.md` (reads no section of its own — the language
  and `lint.ignore` of the consumed domains), `hooks.md` (no hook actions of
  its own; declared-view hooks failures are execution failures), `api.md`
  (the facade signatures: `drift`, `compare_views`, `scope_entries`,
  `DriftEntry`). Add the Drift row to `docs/features/index.md` (between
  Codegraph and Contract) and the `goga drift` row to `docs/cli/index.md`.
- Validation gates after each step: `goga lint` (0 errors), facade checks
  (`python -c "from goga.drift import drift"`, `python -c "from
  goga.commands import drift"`), `pytest tests/ -x`, `ruff check` on the
  touched modules. Never weaken a golden to make a gate pass — a golden
  mismatch is a defect in the refactor.
- Do not "align" the drift exit-2 deviation later; it is permanent (ADR).
