# Architecture Plan — `drift-command`

The `goga drift` console command: declared-vs-code structural drift visibility, with the
object-returning refactor of the two view domains.

## Topic

- Short name: `drift-command` — the `goga drift` command
- Plan path: `.goga/history/2026/drift-command/arch.md`
- Authoritative inputs: `.goga/history/2026/drift-command/adr.md`, `prd.md`, `task.md`

## Implementation Order

| # | Cell | Action | Order rationale |
|---|------|--------|-----------------|
| 1 | `goga/schema` | modify | Leaf of the changed set — its Imports (goga/ast, goga/schema/hooks) already exist and do not change; the object-returning contract must exist before any consumer. |
| 2 | `goga/codegraph` | modify | Leaf of the changed set — its Imports (goga/codegraph/facts, goga/codegraph/analysis, goga/config) already exist and do not change. |
| 3 | `goga/drift` | create | Depends on `goga/schema`, `goga/schema/hooks`, `goga/codegraph`, `goga/codegraph/facts` — all settled in steps 1–2. |
| 4 | `goga/commands/schema` | modify | Depends on the refactored `goga/schema` contract (step 1). |
| 5 | `goga/commands/codegraph` | modify | Depends on the refactored `goga/codegraph` contract (step 2). |
| 6 | `goga/commands/drift` | create | Depends on `goga/drift` (step 3). |
| 7 | `goga/commands` | modify | Facade — depends on `goga/commands/drift` (step 6); registers the command last. |
| 8 | `goga` | modify | Root — imports the re-exported `drift` command from the facade (step 7) and registers it in the CLI group; last, after the facade. |

## Artifacts

### Cell 1 — `goga/schema` (MODIFY)

**CODEMANIFEST diff (section by section):**

- Header `Usages`: DELETE the inline practice `beautiful_json` (serialization leaves the cell).
- Header `Annotations`: REPLACE the line `The caller formats output through the `beautiful_json` practice.`
  with `The routine returns the assembled tree as `SchemaNode` objects — the caller owns the
  serialization of the returned tree.` All other lines unchanged.
- Header `Imports`: unchanged.
- Body — routine `schema`:
  - REPLACE signature `... -> json:str` with `... -> tree: list[SchemaNode]`.
  - REPLACE the param line `` `json`: JSON string representing the project schema `` with
    `` `tree`: the assembled schema tree — one `SchemaNode` per surviving cell; an empty tree is an empty list ``.
  - Algorithm step 6: `no JSON is returned` → `no tree is returned`; step 7: `Return the JSON
    string using the `beautiful_json` practice` → `Return the assembled `SchemaNode` tree`.
  - REPLACE the `Node format:` JSON block with the `Node content:` field list (below).
  - Requirements wording changes: `If the tree is empty: return "[]"` → `If the tree is empty:
    return an empty list`; `The tools key exists on a node iff...never an empty object at any of
    the three levels` → `A node's tools area is empty iff no tool wrote at least one fact on
    that cell`; `With no subscriptions — or no tool packages installed — the output is
    byte-identical to the six-field map: the tools key appears nowhere` → `With no
    subscriptions — or no tool packages installed — every tools area of the tree is empty`;
    `no partial JSON is returned` → `no partial tree is returned`; `an approved verdict leaves
    the output byte-identical` → `an approved verdict leaves the tree unchanged`.
- Body — routine `schema` annotation, tree wording throughout: `Generate the schema tree`
  (first line), `build the node tree` (step 2), and the validation-gate requirement block
  (`The delivered view of the gate carries…`, `an approved verdict leaves the tree unchanged`).
- Footer `Description`: update to the tree wording (below).

**CODEMANIFEST target state:**

```yaml
Imports:
  - Types:
      - AST
    From: goga/ast
  - Types:
      - SchemaHooks
      - CellFacts
      - DependencyFacts
      - SchemaNode
      - GateVerdict
    Usages:
      - checkpoints
    From: goga/schema/hooks

Usages:
  convention: .goga/usages/conventions.md
  documents: |
    Operate on the `AST` entity.
    - The caller loads the project via AST.load()
    - The caller accesses the document tree through the AST.tree property
    The caller must instantiate `AST` with the current CWD path (".").

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and
    testing in the project

  The caller uses the `documents` practice to load the project tree.
  The caller uses the `checkpoints` practice to deliver the
  cell-amendment checkpoint of the generation walk and place the
  contributed facts on the extended nodes.
  The caller uses the `checkpoints` practice to deliver the validation
  gate of the generation walk over the final assembled tree.
  The routine returns the assembled tree as `SchemaNode` objects — the
  caller owns the serialization of the returned tree.

---

"schema(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> tree: list[SchemaNode]":
  location: schema.py
  annotations: |
    Generate the schema tree of the project from the AST entity,
    extended by the tool contributions of the cell-amendment
    checkpoint.

    `cells`: cell paths to include in the output
    `max_depth`: maximum nesting depth of the cell tree
    `depends_on`: filter cells by their dependencies
    `tree`: the assembled schema tree — one `SchemaNode` per
             surviving cell; an empty tree is an empty list

    Use the `checkpoints` practice for the checkpoint delivery of the
    generation walk.

    Algorithm:
    1. Load the project document tree using the `documents` practice
    2. Recursively build the node tree with nested children nodes
    3. Apply filters in order: `cells`, `depends_on`, `max_depth`
    4. For every cell whose node survives the filters, in tree order:
       build the cell's authored facts and deliver them via the
       `SchemaHooks` entry — its amend_cell checkpoint; a `CellFacts`
       view over `DependencyFacts`, built from the loaded document tree
    5. Place the returned tools area on the node under the tools key
       iff the mapping is non-empty
    6. Build the read-only `SchemaNode` projection of the final tree —
       every surviving node with its committed tools overlay — and
       deliver the validation gate over `SchemaHooks`; a not-approved
       `GateVerdict` raises one merged error listing every violation
       (the tool, the hook, the reason) — no tree is returned
    7. Return the assembled `SchemaNode` tree

    Node content:
    - `SchemaNode.path` — the normalized cell path
    - `SchemaNode.description` — the footer description of the cell
      manifest
    - `SchemaNode.types` — the entity and routine names of the cell
      body
    - `SchemaNode.usages` — the usages file names of the cell
    - `SchemaNode.dependencies` — the cell's imports grouped per
      source path
    - `SchemaNode.children` — the nested child nodes
    - `SchemaNode.tools` — the committed tools overlay; empty when no
      tool contributed

    Requirements:
    - If `max_depth` is None: return the full tree without depth limits
    - If `depends_on` is an empty list: return the full tree without dependency filtering
    - If `depends_on` is non-empty: keep a cell only if its own dependencies or any descendant's dependencies contain at least one of the specified paths; cells without such a dependency are removed, while ancestor cells on the path to a kept descendant are preserved so the parent-child skeleton stays intact
    - If the tree is empty: return an empty list
    - If AST.errors is non-empty after loading: raise ValueError with the error count
    - Filters prune delivery exactly as they prune output — a cell is delivered iff its node appears in the output tree
    - The six content fields of every node are independent of the tools overlay
    - A node's tools area is empty iff no tool wrote at least one fact on that cell
    - With no subscriptions — or no tool packages installed — every tools area of the tree is empty
    - Delivery is cell-major and deterministic — cells in tree order, tools in enumeration order within each cell; repeated runs over the same project with the same installed tools produce identical trees
    - A hard failure of the checkpoint — a crashed hook or a structurally malformed contribution — and a register-facade import failure propagate out of the routine as errors naming the tool, the action, and the failing cell path (the package, for the import failure); no partial tree is returned
    - The delivered view carries authored facts only — never another tool's contributions, generated data, or the run's filter parameters
    - The validation gate fires exactly once over the final assembled tree — after the filters and the tools overlay; an approved verdict leaves the tree unchanged
    - The delivered view of the gate carries the final result, the tools overlay included — the recorded exception to the authored-facts-only rule
    - The gate is observe-and-veto — the tree is never modified by a validator

    Constraints:
    - Do not modify the CODEMANIFEST files or the filesystem — the contributions live in memory for the run

---

Author: Mikhail Trifonov
CreatedAt: 15/05/26

Description: |
  This manifest defines how the `schema` routine generates the CODEMANIFEST project schema tree.
```

**`.usages/` files:**

- `goga/schema/.usages/schema-usage.md` — MODIFY (target state):

```md
# Schema API — goga/schema

## Overview

The `goga.schema` module generates the schema tree of the CODEMANIFEST project
structure as a hierarchical tree of `SchemaNode` objects.

## Usage

```python
from goga.schema import schema

# Full project schema
tree = schema(cells=[], max_depth=None, depends_on=[])

# Filter by specific cells
tree = schema(cells=["goga/config", "goga/ast"], max_depth=None, depends_on=[])

# Limit nesting depth
tree = schema(cells=[], max_depth=2, depends_on=[])

# Filter by dependencies — keep only cells whose own dependencies or
# descendant subtree contains the specified path. Ancestor cells on the
# path to a kept descendant are preserved so the parent-child skeleton
# stays intact; cells with no matching dependency are pruned.
tree = schema(cells=[], max_depth=None, depends_on=["goga/ast"])
```

## Return Value

The `schema` routine returns a list of root `SchemaNode` objects — the
assembled schema tree. An empty tree returns `[]`.

Each node carries:

| Field | Description |
|-------|-------------|
| `path` | Normalized cell path |
| `description` | Footer description of the cell manifest |
| `types` | Entity and routine names of the cell body |
| `usages` | Usages file names of the cell |
| `dependencies` | Imports grouped per source path |
| `children` | Nested child nodes |
| `tools` | Committed tools overlay; empty when no tool contributed |

The caller owns the serialization of the returned tree. For the family
JSON output format, map each node to the keys `cell` (from `path`),
`description`, `types`, `usages`, `dependencies`, `children`, and
`tools`; group each node's `DependencyFacts` records into the
dependencies map — the record `path` as the key, the nested `types`
and `usages` lists as the value; the `tools` key is written only when
the overlay is non-empty — and serialize the whole tree with
`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.

## Side Effects

- The routine reads CODEMANIFEST files from the current working directory
- The routine does not modify the file system
- The routine delivers the cell-amendment checkpoint of the hooks
  platform — a hard action: a failing tool contribution stops the
  routine with an error naming the tool, the action, and the cell
  path; no partial tree is returned
- With no subscribed tools every node's tools area is empty — the
  routine still does not modify the file system

```

- `goga/schema/.usages/registering-hooks.md` — unchanged.

### Cell 2 — `goga/codegraph` (MODIFY)

**CODEMANIFEST diff (section by section):**

- Header `Usages`: DELETE the line `beautiful_json: .goga/usages/cooks/beautiful_json.md`.
- Header `Annotations`: REPLACE `...and the serialization via `beautiful_json`.` with `The
  caller owns the serialization of the returned tree.`; REPLACE `renders it as a JSON tree` with
  `assembles it as an object tree`.
- Body — routine `codegraph`: REPLACE signature return `json: str` with
  `tree: list[CodegraphNode]`; REPLACE the `` `json` `` param line with the `` `tree` `` param
  line; algorithm step 7 `Return the JSON document` → `Return the object tree`.
- Body — routine `render_graph`: REPLACE signature return `json: str` with
  `tree: list[CodegraphNode]`; REPLACE the `` `json` `` param line with the `` `tree` `` param
  line; algorithm step 4 `Serialize via `beautiful_json`; an empty tree renders as []` →
  `Return the assembled object tree`.
- Body — routine `discover_sources`: unchanged.
- Body — routine annotations, object-tree wording: `return it as an object tree` (first line of
  `codegraph`), `Assemble the hierarchical node tree of the code-derived view` (first line of
  `render_graph`), `Assemble the tree` (step 6), `produce identical trees` (determinism
  requirement).
- Footer `Description`: `...as a JSON tree.` → `...as an object tree.`

**CODEMANIFEST target state:**

```yaml
Imports:
  - Types:
      - Unit
      - CellLink
      - CodegraphNode
    Usages:
      - records
    From: goga/codegraph/facts
  - Types:
      - collect_facts
      - derive_units
      - resolve_links
    Usages:
      - stages
    From: goga/codegraph/analysis
  - Types:
      - load_project_config
      - ProjectConfig
      - LintConfig
    Usages:
      - project-configuration
    From: goga/config

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell derives the prospective cell graph of the project code and
  assembles it as an object tree. The analysis pipeline is consumed via
  the `stages` practice, the result records via `records`, the project
  configuration via `project-configuration`. The caller owns the
  serialization of the returned tree.

---

"codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> tree: list[CodegraphNode]":
  location: codegraph.py
  annotations: |
    Derive the prospective cell graph of the project code and return it
    as an object tree.

    `cells`: cell paths to include in the output
    `max_depth`: maximum nesting depth of the tree; None — no limit
    `depends_on`: keep only cells whose dependencies reach the given paths
    `tree`: the assembled tree of `CodegraphNode` records; an empty
            project yields an empty list

    Algorithm:
    1. Load the project configuration via `project-configuration` with
       `load_project_config` — an absent configuration is the
       uninitialized-project error; read the language of `ProjectConfig`
    2. Reject a language outside python, golang, javascript, kotlin,
       swift with a clear error
    3. Take the exclusion list from the lint section — an absent
       `LintConfig` means no exclusions
    4. Discover the source files with `discover_sources`
    5. Run the analysis stages in order via the `stages` practice —
       `collect_facts`, `derive_units`, `resolve_links`
    6. Assemble the tree with `render_graph`
    7. Return the object tree

    Requirements:
    - Deterministic and idempotent — identical code and configuration
      produce identical trees
    - Read-only — no file is created or modified

    Constraints:
    - Do not read environment variables
    - Do not execute project code

"discover_sources(language: str, ignore: list[str]) -> files: list[Path]":
  location: discovery.py
  annotations: |
    Walk the project tree and return the analyzable source files of
    the language.

    `language`: the single configured language
    `ignore`: exact relative paths excluded from the walk
    `files`: source files relative to the project root, in a
             deterministic walk order

    Algorithm:
    1. Walk the project tree from the root
    2. Skip the excluded relative paths — the same mechanics as lint
    3. Skip the idiomatic test files of the language entirely:
       test_*.py, *_test.go, *.test.js, *Test.kt, *Tests.swift
    4. Keep the files with the primary extension of the language:
       .py, .go, .js, .kt, .swift

    Requirements:
    - The exclusion mechanism is exactly the given list — no built-in
      exclusion lists, no command-specific settings

    Constraints:
    - Do not read file contents here — discovery works on paths only

"render_graph(units: list[Unit], links: list[CellLink], cells: list[str], max_depth: int | None, depends_on: list[str]) -> tree: list[CodegraphNode]":
  location: render.py
  annotations: |
    Assemble the hierarchical node tree of the code-derived view.

    `units`: all derived units
    `links`: all resolved links
    `cells`: cell paths to include in the output
    `max_depth`: maximum nesting depth; None — no limit
    `depends_on`: keep a cell only when its own or any descendant
                  dependencies contain at least one given path;
                  ancestors of kept cells stay so the parent-child
                  skeleton remains intact
    `tree`: the assembled tree of `CodegraphNode` records; an empty
            tree yields an empty list

    Algorithm:
    1. Nest the units by their paths mirroring the directory tree —
       only units that are cells carry output nodes; non-cell units
       survive only as structural ancestors of nested cells
    2. Aggregate the links into per-node dependencies — target cell
       path to the sorted unique imported types, no usages key; build
       the `CodegraphNode` records via the `records` practice
    3. Apply the filters in order: `cells`, `depends_on`, `max_depth`
       — the same behavior as the schema output
    4. Return the assembled object tree

    Requirements:
    - Node fields are exactly cell, types, dependencies, children —
      manifest-only fields never appear
    - Deterministic order of nodes, types, and dependency keys

    Constraints:
    - Do not modify the input records — build fresh nodes

---

Author: Goga
CreatedAt: 14/10/26

Description: |
  Prospective cell graph of the project code as an object tree.
```

**`.usages/` files:**

- `goga/codegraph/.usages/codegraph-usage.md` — MODIFY (target state):

```md
# Codegraph Usage — producing and consuming the prospective cell graph

Domain: how to run the codegraph analysis and consume its object tree.
Target audience: the CLI command that wraps this cell, the drift
comparison domain, and the later bootstrap stages that draft
CODEMANIFEST files from the graph.

## Import

The entry point is importable from the cell facade:

```python
from goga.codegraph import codegraph
```

## Running the analysis

No arguments are required — the command reads the configured language and the
lint exclusions from the project configuration:

```python
tree = codegraph()
```

All three schema-compatible filters are optional:

```python
filtered = codegraph(
    cells=["goga/codegraph"],  # only these cell paths
    max_depth=2,  # nesting limit
    depends_on=["goga/config"],  # keep only cells depending on these
)
```

## Output node format

The routine returns a list of root `CodegraphNode` records — the
code-derived tree. Each node carries exactly the code-derivable fields
(the schema node minus the manifest-only fields — no description,
usages, or tools; dependencies carry types only):

| Field | Description |
|-------|-------------|
| `cell` | Normalized path of the directory unit |
| `types` | Sorted facade type names of the unit |
| `dependencies` | Imported facade types grouped by normalized target cell path |
| `children` | Nested child nodes (recursive) |

A project with no analyzable sources yields `[]`.

The caller owns the serialization of the returned tree: the record
fields map one-to-one to the family JSON output keys, serialized with
`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.

## Guarantees for the consumer

- Deterministic: identical code and configuration produce identical trees
- Read-only: the project tree is unchanged after the run
- Purely descriptive: import cycles between prospective cells appear as links
  in both directions, with no verdicts or warnings
- Names resolving outside the project (standard library, third-party) never
  appear as links and never fail the run

## Failure behavior relevant to the caller

Each condition raises an error the caller surfaces as a clean command
failure:

- an uninitialized project — no .goga/config.yml
- a configured language outside python, golang, javascript, kotlin, swift
- an unparseable source file — the error names the file

```

### Cell 3 — `goga/drift` (CREATE)

**CODEMANIFEST (full):**

```yaml
Imports:
  - Types:
      - schema
    Usages:
      - schema-usage
    From: goga/schema
  - Types:
      - SchemaNode
    From: goga/schema/hooks
  - Types:
      - codegraph
    Usages:
      - codegraph-usage
    From: goga/codegraph
  - Types:
      - CodegraphNode
    From: goga/codegraph/facts

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell compares the declared contract view with the code-derived
  view of the project and reports their structural discrepancies.
  The declared view is produced and consumed per the `schema-usage`
  practice, the code-derived view per the `codegraph-usage` practice.
  Discrepancies are facts of the complete views — the filters scope
  the report only. The caller owns the serialization of the returned
  report.

---

"DriftEntry(kind: str, cell: str, types: list[str] | None)":
  location: compare.py
  annotations: |
    One flat entry of the drift report.

    `kind`: the direction of the discrepancy — schema_only when the
            subject exists only in the declared view, codegraph_only
            when it exists only in the code-derived view
    `cell`: the normalized cell path of the discrepancy subject
    `types`: the sorted type names of the cell missing from the other
             view; None marks a cell-level discrepancy

    Apply the `convention` practice for the data-model rules.

    Requirements:
    - Immutable data class per `convention`
  properties:
    "kind -> str": |
      The direction of the discrepancy — schema_only or codegraph_only.
    "cell -> str": |
      The normalized cell path of the discrepancy subject.
    "types -> list[str] | None": |
      Sorted type names missing from the other view; None marks a
      cell-level discrepancy.

"compare_views(schema_tree: list[SchemaNode], codegraph_tree: list[CodegraphNode]) -> entries: list[DriftEntry]":
  location: compare.py
  annotations: |
    Compare the two complete views and produce every structural
    discrepancy entry.

    `schema_tree`: the complete declared view
    `codegraph_tree`: the complete code-derived view
    `entries`: every discrepancy of the two views, in the stable order

    Algorithm:
    1. Index each view — cell path to the cell's type names: the
       `SchemaNode.path` with `SchemaNode.types` on one side, the
       `CodegraphNode.cell` with `CodegraphNode.types` on the other
    2. Emit one cell-level entry for every cell path present in
       exactly one view — schema_only when only the declared view
       carries the path, codegraph_only otherwise — with no type list
    3. For every cell path present in both views, compare the two
       type-name sets: emit one schema_only entry carrying the sorted
       names declared but absent from the code, and one
       codegraph_only entry carrying the sorted names present in the
       code but undeclared — a direction with no missing names emits
       nothing
    4. Order the entries by cell path, then by kind

    Requirements:
    - Pure — no view is modified, no file is read or written
    - Identity is name-level — the normalized cell path and the type
      name; no signature or annotation semantics
    - A cell-level entry never coexists with type-level entries of
      the same cell
    - A cell with type drift in both directions yields two entries
    - An entry's type list is sorted and duplicate-free
    - Views that agree produce an empty list

    Constraints:
    - Do not apply filters here — the entries are facts of the views
      passed in

"scope_entries(entries: list[DriftEntry], schema_tree: list[SchemaNode], codegraph_tree: list[CodegraphNode]) -> report: list[DriftEntry]":
  location: compare.py
  annotations: |
    Scope the computed entries to the filtered views.

    `entries`: the computed discrepancies of the complete views
    `schema_tree`: the filtered declared view
    `codegraph_tree`: the filtered code-derived view
    `report`: the surviving entries, order preserved

    Algorithm:
    1. Collect the surviving cell paths — every `SchemaNode.path` of
       `schema_tree` and every `CodegraphNode.cell` of
       `codegraph_tree`
    2. Keep an entry iff its cell appears among the surviving paths

    Requirements:
    - An entry survives iff its cell survives the filters in at least
      one of the two filtered views — never both required
    - The output order is the input order
    - Pure — the inputs stay unmutated

    Constraints:
    - Do not fabricate, alter, or reorder entries — survival is the
      only effect

"drift(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> report: list[DriftEntry]":
  location: drift.py
  annotations: |
    Produce the drift report of the project — the structural
    discrepancies between the declared contracts and the actual code.

    `cells`: cell paths to scope the report
    `max_depth`: maximum nesting depth to scope the report; None —
                 no limit
    `depends_on`: scope the report to cells depending on the given
                  paths
    `report`: the scoped discrepancy entries in the stable order;
              an empty list when the views agree

    Algorithm:
    1. Produce the complete views — call `schema` and `codegraph`
       with no filters
    2. Produce the filtered views — call `schema` and `codegraph`
       with `cells`, `max_depth`, `depends_on`
    3. Compare the complete views with `compare_views`
    4. Scope the entries with `scope_entries` over the filtered views
    5. Return the scoped report

    Requirements:
    - The comparison always runs on the complete views; the filters
      scope the report only
    - The depends_on asymmetry — declared dependencies in the
      declared view, resolved imports in the code-derived view —
      never surfaces as fabricated cell-level entries
    - Deterministic and idempotent — identical project state,
      configuration, and filters produce identical reports
    - Read-only — no file is created or modified
    - Every error of a view producer propagates unchanged — the
      comparison adds no failures of its own

    Constraints:
    - Do not read manifests or sources — the views arrive fully
      assembled from `schema` and `codegraph`
    - Do not apply filters inside the comparison

---

Author: Goga
CreatedAt: 14/10/26

Description: |
  Structural drift between the declared contracts and the actual code.

```

**`.usages/` files:**

- `goga/drift/.usages/drift-usage.md` — CREATE:

```md
# Drift Usage — producing and consuming the contract-drift report

Domain: how to run the drift comparison and consume its report entries.
Target audience: the CLI command that wraps this cell and acceptance
review flows that check delivered functionality against declared
contracts.

## Import

The entry point is importable from the cell facade:

```python
from goga.drift import drift
```

## Running the comparison

No arguments are required — the comparison always covers the complete
declared and code-derived views of the current project:

```python
report = drift()
```

The three family filters are optional and scope the report only:

```python
report = drift(
    cells=["goga/config"],  # scope the report to these cell paths
    max_depth=2,  # nesting limit for the scope
    depends_on=["goga/ast"],  # scope to cells depending on these
)
```

## Report entries

The routine returns a list of `DriftEntry` records — one per
discrepancy, in the stable order (cell path, then kind):

| Field | Description |
|-------|-------------|
| `kind` | Direction — `schema_only` (exists only in the declared view) or `codegraph_only` (exists only in the code-derived view) |
| `cell` | Normalized cell path of the subject |
| `types` | Sorted type names missing from the other view; `None` marks a cell-level discrepancy |

Exactly four semantic kinds map onto direction × presence of `types`:
cell only declared, cell only in code, type only declared, type only
in code. A cell present in both views with type drift in both
directions yields two entries; a cell present in one view only yields
a single cell-level entry. An empty report means the views agree.

The caller owns the serialization of the report: each entry maps to
the keys `kind`, `cell`, and `types` — the `types` key is written
only for type-level entries — serialized with
`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.

## Guarantees for the consumer

- Deterministic: identical project state, configuration, and filters
  produce an identical report
- Read-only: the project tree is unchanged after the run
- Complete-view semantics: discrepancies are computed on the complete
  views; the filters scope the report only — a cell is reported when
  it survives the filters in at least one of the two filtered views,
  and the `depends_on` asymmetry never fabricates cell-level entries

## Failure behavior relevant to the caller

Every failure of a view producer propagates unchanged — the caller
surfaces it as a clean command failure:

- an uninitialized project — no .goga/config.yml
- a configured language outside python, golang, javascript, kotlin, swift
- an unparseable source file — the error names the file
- manifest loading and validation failures of the declared view
- hard failures of the schema hooks checkpoints

```

### Cell 4 — `goga/commands/schema` (MODIFY)

**CODEMANIFEST diff:**

- Header `Imports`: in the `goga/schema/hooks` block ADD `Types: [SchemaNode, DependencyFacts]`
  (keep the `checkpoints` usage import).
- Header `Usages`: ADD `beautiful_json: .goga/usages/cooks/beautiful_json.md`.
- Header `Annotations`: ADD `and serializes the returned object tree via the `beautiful_json`
  practice` to the delegation sentence.
- Body: algorithm extended with steps 3–4 (node projection + serialization) per the target state.
- Body: the routine annotation first line gains `and serializes the returned object tree`; the
  param doc lines drop the parenthesized types (untyped family style).
- Footer: unchanged.

**CODEMANIFEST target state:**

```yaml
Imports:
  - Types:
      - schema AS schema_logic
    Usages:
      - registering-hooks
    From: goga/schema
  - Types:
      - SchemaNode
      - DependencyFacts
    Usages:
      - checkpoints
    From: goga/schema/hooks

Usages:
  click: .goga/usages/cooks/click.md
  convention: .goga/usages/conventions.md
  beautiful_json: .goga/usages/cooks/beautiful_json.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of
    development and testing in the project

  The developer must use the `click` practice to create CLI commands.
  The `schema` command delegates its business logic to `schema_logic`
  and serializes the returned object tree via the `beautiful_json`
  practice.
  The caller uses the `checkpoints` practice for the hard-failure handling of
  the schema generation — every failure of `schema_logic` surfaces as a clean
  command failure.
  The caller uses the `registering-hooks` practice for the tool-package
  hook subscription surface of the schema domain actions behind the
  checkpoints of the generation.

---

"schema(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])":
  location: schema.py
  annotations: |
    CLI wrapper for the schema command. Delegates business logic to
    `schema_logic` and serializes the returned object tree.

    `cells`: cell paths to filter the schema output
    `max_depth`: maximum nesting depth of the dependency tree
    `depends_on`: filter cells by dependency relationship

    Use the `checkpoints` practice for the failure handling of the
    generation checkpoint.

    Algorithm:
    1. Invoke `schema_logic`(`cells`, `max_depth`, `depends_on`)
    2. On any error from `schema_logic` — AST parse errors, a hard failure
       of the cell-amendment checkpoint (a crashed hook or a structurally
       malformed contribution; the error names the tool, the action, and
       the failing cell path), a vetoed validation gate of the final tree
       (the merged error lists every violation — the tool, the hook, the
       reason), or a register-facade import failure (the error names the
       package) — write the error message to stderr and exit 1; nothing is
       printed to stdout and no raw traceback is shown
    3. Project the returned `SchemaNode` tree onto the output nodes — the
       keys cell (from the node path), description, types, usages,
       dependencies, children, and tools; group each node's
       `DependencyFacts` records into the dependencies map — the record
       path as the key, the nested types and usages lists as the value;
       the tools key is written only when the overlay is non-empty
    4. Serialize the projected tree via the `beautiful_json` practice and
       output it via `click`.echo

    Requirements:
    - stdout carries the machine-consumed JSON only — every warning and
      diagnostic goes to stderr
    - Exit 0 only on a complete generation

---

Author: Goga
CreatedAt: 20/05/26

Description: |
  CLI wrapper command that generates a JSON schema representation of the project structure

```

**`.usages/` files:** unchanged (`goga/commands/schema/.usages/schema.md`).

### Cell 5 — `goga/commands/codegraph` (MODIFY)

**CODEMANIFEST diff:**

- Header `Imports`: ADD block `Types: [CodegraphNode] From: goga/codegraph/facts`.
- Header `Usages`: ADD `beautiful_json: .goga/usages/cooks/beautiful_json.md`.
- Header `Annotations`: ADD the serialization clause to the delegation sentence.
- Body: algorithm step 3 owns the 1:1 serialization per the target state.
- Header `Annotations`: the clause `and holds no domain knowledge of its own` is replaced with
  `and serializes the returned object tree via the `beautiful_json` practice`; the routine
  annotation first line gains `and serializes the returned object tree`.
- Footer: unchanged.

**CODEMANIFEST target state:**

```yaml
Imports:
  - Types:
      - codegraph AS codegraph_logic
    Usages:
      - codegraph-usage
    From: goga/codegraph
  - Types:
      - CodegraphNode
    From: goga/codegraph/facts

Usages:
  convention: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  beautiful_json: .goga/usages/cooks/beautiful_json.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  The developer must use the `click` practice to create the CLI command.
  The `codegraph` command delegates its business logic to
  `codegraph_logic` and serializes the returned object tree via the
  `beautiful_json` practice.
  The caller uses the `codegraph-usage` practice for the output and
  failure contract behind the command.

---

"codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])":
  location: codegraph.py
  annotations: |
    CLI wrapper for the codegraph command. Delegates business logic
    to `codegraph_logic` and serializes the returned object tree.

    `cells`: cell paths to filter the output
    `max_depth`: maximum nesting depth of the tree
    `depends_on`: filter cells by dependency relationship

    Use the `click` practice to declare the command surface — the
    CELLS variadic argument and the --max-depth and repeatable
    --depends-on options, identical to the schema command.

    Algorithm:
    1. Invoke `codegraph_logic`(`cells`, `max_depth`, `depends_on`)
    2. On any error — an uninitialized project, an unsupported
       configured language, an unparseable source file — write the
       error message to stderr and exit 1; nothing is printed to
       stdout and no raw traceback is shown
    3. Serialize the returned `CodegraphNode` tree via the
       `beautiful_json` practice — the record fields map one-to-one
       to the output node keys — and output it via `click`.echo

    Requirements:
    - stdout carries the JSON document only — every diagnostic goes
      to stderr
    - Exit 0 only on a complete generation
    - The command help documents the JSON structure per root cell —
      the fields cell, types, dependencies, children — mirroring the
      schema command help so agents can read the output

---

Author: Goga
CreatedAt: 14/10/26

Description: |
  CLI wrapper that prints the prospective cell graph of existing code.

```

**`.usages/` files:** unchanged (`goga/commands/codegraph/.usages/codegraph.md`).

### Cell 6 — `goga/commands/drift` (CREATE)

**CODEMANIFEST (full):**

```yaml
Imports:
  - Types:
      - drift AS drift_logic
      - DriftEntry
    Usages:
      - drift-usage
    From: goga/drift

Usages:
  convention: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  beautiful_json: .goga/usages/cooks/beautiful_json.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  The developer must use the `click` practice to create the CLI command.
  The `drift` command delegates its business logic to `drift_logic`
  and serializes the returned report via the `beautiful_json` practice.
  The caller uses the `drift-usage` practice for the report and failure
  contract behind the command.

---

"drift(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])":
  location: drift.py
  annotations: |
    CLI wrapper for the drift command. Delegates business logic to
    `drift_logic` and prints the flat JSON report.

    `cells`: cell paths to scope the report
    `max_depth`: maximum nesting depth to scope the report
    `depends_on`: scope the report to cells depending on the given paths

    Use the `click` practice to declare the command surface — the
    CELLS variadic argument and the --max-depth and repeatable
    --depends-on options, identical to the schema and codegraph
    commands.

    Algorithm:
    1. Invoke `drift_logic`(`cells`, `max_depth`, `depends_on`)
    2. On any error from `drift_logic` — an uninitialized project, an
       unsupported configured language, an unparseable source file,
       manifest loading and validation failures, hard failures of the
       schema hooks checkpoints — write the error message to stderr and
       exit 2; nothing is printed to stdout and no raw traceback is
       shown
    3. Serialize the returned `DriftEntry` report via the
       `beautiful_json` practice — each entry maps to the keys kind and
       cell plus types for type-level entries only — and output it via
       `click`.echo
    4. Exit 0 when the report is empty, 1 when it carries entries

    Requirements:
    - stdout carries the JSON report only — every diagnostic goes to
      stderr
    - Exit 0 — comparison completed, no discrepancies; an empty JSON
      list is printed
    - Exit 1 — comparison completed, discrepancies found; the full
      report is printed
    - Exit 2 — the comparison could not be performed; the exit-2
      deviation from the family exit-1 failure convention is
      deliberate and permanent — the three-outcome contract reserves
      exit 1 for discrepancies found
    - The command help documents the arguments, the options, the JSON
      report structure, and the completion statuses — mirroring the
      schema and codegraph command helps so agents can read the output

---

Author: Goga
CreatedAt: 14/10/26

Description: |
  CLI wrapper that prints the contract drift between schema and codegraph.

```

**`.usages/` files:**

- `goga/commands/drift/.usages/drift.md` — CREATE:

```md
# CLI Command: drift

## Purpose

CLI wrapper for the drift command. Delegates business logic to `goga/drift`. Compares the declared contract view (`goga schema`) with the code-derived view (`goga codegraph`) and prints the flat JSON report of their structural discrepancies to stdout. Discrepancies are computed on the complete views; the filters scope the report only.

## Syntax

```
goga drift [cells...] [--max-depth N] [--depends-on PATH]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `cells` | list[str] | Paths to cells for scoping the report (optional; a cell is reported when it survives the filters in at least one of the two filtered views) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--max-depth` | int | None | Nesting depth limit for the report scope |
| `--depends-on` | list[str] | None | Scope the report by dependency (repeatable) |

## Exit code

- 0 — comparison completed, no discrepancies (an empty JSON list is printed)
- 1 — comparison completed, discrepancies found (the full report is printed)
- 2 — the comparison could not be performed: an uninitialized project (no `.goga/config.yml`); a configured language outside python, golang, javascript, kotlin, swift; an unparseable source file (the message names the file); manifest loading and validation failures; hard failures of the schema hooks checkpoints — nothing is printed to stdout

## Output

A flat JSON array of report entries, sorted by cell path then kind:

| Field | Description |
|-------|-------------|
| `kind` | Direction — `schema_only` (exists only in the declared view) or `codegraph_only` (exists only in the code-derived view) |
| `cell` | Normalized cell path of the subject |
| `types` | Sorted type names of the cell missing from the other view; present only on type-level entries — its absence marks a cell-level discrepancy |

Healthy projects render as `[]`.

## Examples

```bash
goga drift
goga drift goga/config goga/ast --max-depth 2
goga drift --depends-on goga/ast
```

```

### Cell 7 — `goga/commands` (MODIFY — facade)

**CODEMANIFEST diff:**

- Header `Imports`: ADD block after the codegraph block:
  `Types: [drift] From: goga/commands/drift`.
- Body: ADD embedding `->drift: {}` after `->codegraph: {}`.
- All other sections unchanged.

**CODEMANIFEST target state:**

```yaml
Imports:
  - Types:
      - lint
    From: goga/commands/lint
  - Types:
      - build
    From: goga/commands/build
  - Types:
      - connect
    From: goga/commands/connect
  - Types:
      - schema
    From: goga/commands/schema
  - Types:
      - codegraph
    From: goga/commands/codegraph
  - Types:
      - drift
    From: goga/commands/drift
  - Types:
      - contract
    From: goga/commands/contract
  - Types:
      - config
    From: goga/commands/config
  - Types:
      - usages
    From: goga/commands/usages
  - Types:
      - tool
    From: goga/commands/tool
  - Types:
      - init
    From: goga/commands/init
  - Types:
      - pipeline
    Usages:
      - pipeline-command
    From: goga/commands/pipeline
  - Types:
      - upgrade
    From: goga/commands/upgrade
  - Types:
      - install
      - uninstall
    Usages:
      - uninstall-usage
      - install AS install-usage
    From: goga/commands/install
  - Types:
      - history
    Usages:
      - history-command
    From: goga/commands/history
  - Types:
      - topics
    Usages:
      - topics-command
    From: goga/commands/topics
  - Types:
      - hooks
    Usages:
      - hooks-command
    From: goga/commands/hooks

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  Use the `uninstall-usage` practice for consumer scenarios of the removal
  command: confirmation behavior, flags, exit codes, and the post-removal
  re-sync.

  Use the `pipeline-command` practice for consumer scenarios of the
  pipeline command: the five forms, the topic switch flow of -t/--topic
  with --todo, and the flag behavior per form.
  Use the `install-usage` practice for consumer scenarios of the install
  command: the four modes, the post-install hooks, and the exit codes.

  Use the `history-command` practice for consumer scenarios of the history
  command group: the five subcommands, their options and filters, the path
  and ensure behaviors, and the exit codes.

  Use the `topics-command` practice for consumer scenarios of the topics
  command group: the board table with its filters, the creation flow,
  the switching flow, the deletion and clear flows, and the exit codes.

  Use the `hooks-command` practice for consumer scenarios of the hooks
  command: the registry tree, the tool slice, and the exit codes.

---

->lint: {}
->build: {}
->connect: {}
->schema: {}
->codegraph: {}
->drift: {}
->contract: {}
->config: {}
->usages: {}
->tool: {}
->init: {}
->pipeline: {}
->upgrade: {}
->install: {}
->uninstall: {}
->history: {}
->topics: {}
->hooks: {}

---

Author: Goga
CreatedAt: 20/05/26

Description: |
  Facade of the goga console application commands. Re-exports all CLI commands from subcells.
```

**`.usages/` files:**

- `goga/commands/.usages/cli-commands.md` — MODIFY (target state — 18 commands, drift added to
  both import lists, the registration snippet, and the command table):

```md
# CLI Commands — goga/commands facade

The `goga.commands` package is a facade that re-exports 18 CLI commands. Each command is a `click.Command` registered in a click group. Each subcell is an independent Python package (`goga/commands/<name>/`) with implementation in `<name>.py` and re-export through `__init__.py`.

## Import

All commands are available from the facade in a single line:

```python
from goga.commands import (
    lint,
    build,
    connect,
    schema,
    codegraph,
    drift,
    contract,
    config,
    usages,
    tool,
    init,
    pipeline,
    upgrade,
    install,
    uninstall,
    history,
    hooks,
    topics,
)
```

Each command is available from its subcell (via `__init__.py` re-export):

```python
from goga.commands.lint import lint
from goga.commands.build import build
from goga.commands.connect import connect
from goga.commands.schema import schema
from goga.commands.codegraph import codegraph
from goga.commands.drift import drift
from goga.commands.contract import contract
from goga.commands.config import config
from goga.commands.usages import usages
from goga.commands.tool import tool
from goga.commands.init import init
from goga.commands.pipeline import pipeline
from goga.commands.upgrade import upgrade
from goga.commands.install import install
from goga.commands.install import uninstall
from goga.commands.history import history
from goga.commands.hooks import hooks
from goga.commands.topics import topics
```

## Registration in click group

```python
import click

from goga.commands import (
    lint,
    build,
    connect,
    schema,
    codegraph,
    drift,
    contract,
    config,
    usages,
    tool,
    init,
    pipeline,
    upgrade,
    install,
    uninstall,
    history,
    hooks,
    topics,
)


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(lint)
app.add_command(build)
app.add_command(connect)
app.add_command(schema)
app.add_command(codegraph)
app.add_command(drift)
app.add_command(contract)
app.add_command(config)
app.add_command(usages)
app.add_command(tool)
app.add_command(init)
app.add_command(pipeline)
app.add_command(upgrade)
app.add_command(install)
app.add_command(uninstall)
app.add_command(history)
app.add_command(hooks)
app.add_command(topics)
```

## Testing with CliRunner

```python
from click.testing import CliRunner
from goga.commands.lint import lint


def test_example():
    runner = CliRunner()
    result = runner.invoke(lint, ["."])
    assert result.exit_code in (0, 1)
```

## Command list

| Command     | Subcell                   | Purpose                              |
|-------------|---------------------------|--------------------------------------|
| `lint`      | `goga/commands/lint/`     | CODEMANIFEST file validation         |
| `build`     | `goga/commands/build/`    | Build via ralphex                    |
| `connect`   | `goga/commands/connect/`  | Connect goga skills                  |
| `schema`    | `goga/commands/schema/`   | Project JSON schema                  |
| `codegraph` | `goga/commands/codegraph/` | Prospective cell graph from existing code |
| `drift`     | `goga/commands/drift/`    | Contract drift between schema and codegraph |
| `contract`  | `goga/commands/contract/` | Compare contract with implementation |
| `config`    | `goga/commands/config/`   | Output configuration values          |
| `usages`    | `goga/commands/usages/`   | Synchronize cell-level usages        |
| `tool`      | `goga/commands/tool/`     | Run tool commands                    |
| `init`      | `goga/commands/init/`     | Initialize goga project              |
| `pipeline`  | `goga/commands/pipeline/` | Run a goga pipeline (or list them)   |
| `upgrade`   | `goga/commands/upgrade/`  | Upgrade goga and re-sync agents      |
| `install`   | `goga/commands/install/`  | Install a goga_tool_* package        |
| `uninstall` | `goga/commands/install/`  | Remove a goga_tool_* package         |
| `history`   | `goga/commands/history/`  | Work with the .goga/history/ tree    |
| `hooks`     | `goga/commands/hooks/`    | Inspect registered tool hooks        |
| `topics`    | `goga/commands/topics/`   | Topic board, creation, and switching |

```

### Cell 8 — `goga` (MODIFY — root CLI group)

**CODEMANIFEST diff:**

- Header `Imports`: in the `goga/commands` block ADD the type `drift` (after `codegraph`; keep the
  `cli-commands` usage import — its practice file is updated by step 7).
- Body — entity `app()`: in the `Commands:` list ADD `- `drift`` (after `- `codegraph``).
- All other sections unchanged.

**CODEMANIFEST target state:**

```yaml
Imports:
  - Types:
      - lint
      - build
      - connect
      - schema
      - codegraph
      - drift
      - contract
      - config
      - usages
      - tool
      - init
      - pipeline
      - upgrade
      - install
      - uninstall
      - history
      - hooks
      - topics
    Usages:
      - cli-commands
    From: goga/commands
  - Types:
      - AST
    From: goga/ast
  - Types:
      - host_goga_version
    Usages:
      - version-check
    From: goga/version

Usages:
  convention: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  Use the `click` practice for the root group, the command registration, and
  the --version flag (an eager flag with a callback that prints and exits).
  Use the `version-check` practice for the host-version reading contract
  behind the flag. Wire the application in __main__.py to enable invocation
  via python -m.

---

->AST: {}

app():
  location: cli.py
  annotations: |
    Root command group of the goga CLI.

    Use the `click` practice to create the root command group.

    The group carries the --version / -v flag: an eager option handled
    before subcommand dispatch, so it never conflicts with subcommands or
    their options. When the flag is set, print the host goga version
    obtained via `host_goga_version` to stdout and exit with code 0. When
    the host version cannot be determined, catch the metadata failure and
    surface a clean user-facing error (stderr, no traceback, non-zero
    exit). The flag takes no part in the host–image version check.

    Use the `cli-commands` practice for the command registration reference:
    the facade import line, the add_command wiring, and the full command
    table.

    Commands:
    - `lint`
    - `build`
    - `connect`
    - `schema`
    - `codegraph`
    - `drift`
    - `contract`
    - `config`
    - `usages`
    - `tool`
    - `init`
    - `pipeline`
    - `upgrade`
    - `install`
    - `uninstall`
    - `history`
    - `hooks`
    - `topics`

---

Author: Goga
CreatedAt: 13/04/26

Description: |
  This manifest describes the assembly of the goga main application interface.
```

**`.usages/` files:** unchanged — the root consumes the `cli-commands` practice of `goga/commands`,
whose target state (18 commands) is delivered by step 7.

## Dependency Map

```
goga/schema/hooks ──(SchemaNode)────> goga/schema ──(schema, schema-usage)────┐
goga/codegraph/facts ──(Codegraph─> goga/codegraph ──(codegraph,             │
  Node, Unit, CellLink)                codegraph-usage)──┐                    │
                                                        ├──> goga/drift ─────┤
goga/schema/hooks ──(SchemaNode)─────────────────────────┤   (DriftEntry,     │
goga/codegraph/facts ──(CodegraphNode)───────────────────┘    compare_views,  │
                                                               scope_entries,  │
                                                               drift)          │
goga/schema ──(schema, registering-hooks)──> goga/commands/schema              │
goga/codegraph ──(codegraph, codegraph-usage)──> goga/commands/codegraph       │
goga/drift ──(drift AS drift_logic, DriftEntry, drift-usage)──> goga/commands/drift
goga/commands/drift ──(drift)──> goga/commands (facade, ->drift: {})
goga/commands ──(drift, cli-commands)──> goga (root CLI group — app() registers the commands)
```

Direction is fixed and one-way: view domains → drift domain → wrapper → facade → root CLI
group. The two view
producers stay mutually blind; no edge creates a cycle.

## Verification Checklist

After implementing each artifact, run the checks in order; a failing check is an actionable
defect, never acceptable noise:

1. **DSL validity (every CODEMANIFEST, after each edit):** `goga lint` reports 0 errors for the
   touched cells; YAML parses with the three-section structure; casing of all keys exact;
   every connected practice referenced in at least one annotation; annotation references resolve
   within the document context.
2. **`goga/schema` refactor (C2):** golden CLI-level tests assert `goga schema` output is
   byte-identical before and after (full run and each filter form); existing domain tests that
   pin the JSON-string return are adapted to the object contract with expectations preserved;
   `python -c "from goga.schema import schema"` still resolves the facade.
3. **`goga/codegraph` refactor (C2):** same golden byte-identity for `goga codegraph`; domain
   tests adapted to `list[CodegraphNode]`; `render_graph` returns the filtered tree unserialized.
4. **`goga/drift`:** unit tests per `convention` — `compare_views` (all four kinds, grouped
   sorted types, no-double-reporting, both-directions-two-entries, stable order, empty on
   agreement), `scope_entries` (survival in at least one view, order preservation, pure),
   `drift` (complete-view comparison, filter scoping, depends_on asymmetry never fabricates
   entries, determinism, read-only, producer errors propagate); integration test with planted
   discrepancies of all four kinds.
5. **`goga/commands/drift`:** CLI tests invoking the handler directly — exits 0 with `[]` on
   agreement; exits 1 with the full report on discrepancies; exits 2 with a clean stderr message
   and empty stdout on an uninitialized project; help documents arguments, options, the report
   structure, and the three statuses; repeated runs byte-identical; project tree unchanged.
6. **Facade:** `goga drift` reachable through the CLI; `goga.commands` facade imports the
   command; `cli-commands.md` table matches the registered commands.
7. **Usage files:** every referenced usage file exists at its path; drift usage files are
   self-contained (no cross-references to other practices); names in examples match the
   CODEMANIFEST signatures.
8. **Documentation (collateral obligations, family layout):** `docs/features/drift/` — index.md,
   cli.md, api.md, configuration.md, hooks.md — created in the convention of
   `docs/features/schema/` and `docs/features/codegraph/`; the CLI help text and the docs agree
   on the report structure and the exit codes.
9. **Gates:** `pytest tests/ -x` green; `ruff check` clean on the touched code; coverage of the
   new public functions per `convention`.
