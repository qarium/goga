# [ARCHITECTURE_PLAN]

## Topic

Schema domain hooks zone (`add-hooks-to-schema`) — plan path:
`.goga/history/2026/add-hooks-to-schema/arch.md`

Opens the schema domain for tool extension over the existing hooks platform: one additive
hard-action record `schema` / `amend_cell`, a new zone cell `goga/schema/hooks` (per-cell
authored-facts read view, per-tool contribution model with key-wise merge, cell-major
checkpoint surface), integration of the checkpoint into the schema generation walk with the
`tools` wrapper key on extended nodes, clean hard-failure behavior on the CLI, and the
two-level tool-author documentation (domain `registering-hooks.md` + zone `checkpoints.md`).

## Implementation Order

1. **`goga/hooks/catalog`** (modify — data only) — first: has no Imports; every other change
   resolves the address against its catalog.
2. **`goga/schema/hooks`** (create) — second: depends only on `goga/hooks` (existing facade);
   must exist before `goga/schema` imports it.
3. **`goga/schema`** (modify) — third: depends on `goga/ast` (existing) and the new zone;
   the walk integrates the checkpoint.
4. **`goga/commands/schema`** (modify) — last: depends on `goga/schema` and (usage-only) the
   zone; converts the hard failures of the routine into clean command failures.

## Artifacts

### 1. Cell: goga/hooks/catalog — MODIFIED (data only)

**CODEMANIFEST diff** — one additive bullet appended to the `Requirements:` list of
`declared_actions`, after the config record bullet (domain-addition order):

```yaml
    - The catalog carries the schema cell-amendment action — the record
      domain="schema", name="amend_cell", error_class="hard": the first
      failing hook of the action — a crashed hook or a structurally
      malformed contribution — stops the command with a clean error
      naming the tool, the action, and the failing cell path
```

Nothing else changes: `Action`, the algorithm, the constraints, and the footer stay as
published (catalog additivity law — published records are never rewritten).

**.usages/ files** — none (the cell owns no `.usages/` directory).

### 2. Cell: goga/schema/hooks — CREATED

**CODEMANIFEST** (full):

```yaml
Imports:
  - Types:
      - HookRegistry
      - wrap_context
      - build_hook_arguments
      - declared_actions
    Usages:
      - per-tool-delivery
      - registering-hooks
    From: goga/hooks

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of
    development and testing in the project

  This cell owns the hooks zone of the schema domain: the per-cell
  read view of the authored facts, the per-tool contribution model
  with its key-wise merge, and the checkpoint surface that delivers
  the cell amendment over the platform facade. One registry per run
  carries every checkpoint of a command — the checkpoints never
  multiply the package enumeration. Every context is built from the
  operation data the caller passes — no repository, git, or file
  reads happen here. The amendment action is hard: the first failing
  hook of the delivery walk — a crashed hook or a structurally
  malformed contribution — stops the command with a clean error
  naming the tool, the action, and the failing cell path, and the
  tool's whole contribution is discarded. Tools are mutually blind —
  every delivered view reads the authored cell facts only, never
  another tool's contribution; each tool's contributions commit as a
  unit, in enumeration order, per cell. The contributions live in
  memory for the current run — the authored CODEMANIFEST files are
  never modified. The zone does not import the schema domain — the
  read view is built from the facts the caller passes.
  Use the `per-tool-delivery` practice for the staged delivery loop of
  the amendment checkpoint — its loop skeleton, primitives, and
  tool-grouped commit apply as written.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind the checkpoint.
  Use relative imports.

---

"CellFacts(path: str, description: str, types: list[str], usages: list[str], dependencies: list[DependencyFacts], children: list[str])":
  location: facts.py
  annotations: |
    The authored facts of one cell — the per-cell read view delivered
    to a subscribed hook.

    `path`: the normalized cell path
    `description`: the footer description of the cell manifest
    `types`: the entity and routine names of the cell body
    `usages`: the usages file names of the cell
    `dependencies`: the cell's imports grouped per source path
    `children`: the authored children paths of the document tree

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the constructing operation passes resolved values;
      nothing is read here
    - Authored projection only — identical in every run regardless of
      filters; never another tool's contributions, generated data, or
      the run's filter parameters
  properties:
    "path -> str": |
      The normalized cell path.
    "description -> str": |
      The footer description of the cell manifest.
    "types -> list[str]": |
      The entity and routine names of the cell body.
    "usages -> list[str]": |
      The usages file names of the cell.
    "dependencies -> list[DependencyFacts]": |
      The cell's imports grouped per source path.
    "children -> list[str]": |
      The authored children paths of the document tree.

"DependencyFacts(path: str, types: list[str], usages: list[str])":
  location: facts.py
  annotations: |
    The imported facts of one dependency — the source path with its
    imported type names and usage names.

    `path`: the source path of the import
    `types`: the imported type names
    `usages`: the imported usage names

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the caller from the document's imports

"CellAmendment(cell: CellFacts)":
  location: amendments.py
  annotations: |
    The read-and-contribute view of one tool for one cell — the
    delivered facts of the amendment checkpoint and the buffer of
    this tool's contributions.

    `cell`: the authored facts of the cell being built — read-only and
             identical for every tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads deliver the authored facts — a tool never sees
      another tool's contribution
    - The buffered contributions belong to this tool alone
  properties:
    "cell -> CellFacts": |
      The authored facts of the cell; read-only for the receiving hook.
  methods:
    "contribute(facts: dict[str, object])": |
      Buffer one fact-mapping contribution of this tool.

      `facts`: the contribution mapping — fact names to
               JSON-representable values

      Requirements:
      - The call buffers into the buffer of this tool alone and
        changes nothing until the delivery commits it
      - The buffer merges key-wise — a later write replaces an
        earlier one on key conflict
      - An empty mapping contributes nothing

      Constraints:
      - Do not cancel, redirect, or defer the operation — a
        contribution extends the cell node's tools area only

"ToolContribution(tool: str, facts: dict[str, object])":
  location: overlay.py
  annotations: |
    The committed contribution of one tool for one cell — the pairing
    of the tool identity with its merged fact mapping.

    `tool`: the tool identity assigned by the platform
    `facts`: the committed contribution of the tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the checkpoint delivery alone

"merge_cell_contributions(contributions: list[ToolContribution]) -> tools: dict[str, dict[str, object]]":
  location: overlay.py
  annotations: |
    The deterministic tools-area composition — the `tools` mapping of
    one cell node from the committed contributions.

    `contributions`: the committed contributions in enumeration order
    `tools`: the tools area of the cell node — empty when nothing
              contributed

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Take the contributions in enumeration order
    2. Skip a contribution whose mapping is empty — a tool's key
       exists iff that tool wrote at least one fact
    3. Place each remaining mapping under its tool identity key
    4. Return the composed mapping — empty when every contribution
       was empty or none committed

    Requirements:
    - Deterministic — the same contributions give the same mapping
    - Pure — the inputs stay unmutated; the result is a new mapping
    - Structural validation is not here — it happened at the tool
      commit point of the delivery

    Constraints:
    - Do not read or write the filesystem
    - Do not mutate `contributions` or their maps

"SchemaHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the schema domain — the cell-amendment
    delivery over the platform facade.

    Apply the `convention` practice for the code style and
    intra-package imports.
    Use the `per-tool-delivery` practice for the staged delivery loop of
    the amendment checkpoint.
    Use the `registering-hooks` practice for the registration contract
    behind the checkpoint.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a command —
      the assembly runs once per run whatever the number of checkpoints
    - Every context is built from the values the caller passes — no
      repository, git, or file reads happen at the checkpoint
  methods:
    "amend_cell(cell: CellFacts) -> tools: dict[str, dict[str, object]]": |
      Deliver the cell-amendment checkpoint for one cell and return
      its tools area.

      `cell`: the authored facts of the cell being built — operation
               data handed over by the calling walk
      `tools`: the tools area of the cell node — empty when nothing
               contributed

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="schema", action="amend_cell"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `CellAmendment` view over the delivered
         facts — every tool reads the same authored `cell` — wrap it via
         `wrap_context`, project the call arguments via
         `build_hook_arguments` with the tool's own context, and call
         each hook of the tool
      3. A tool whose every hook returned without raising passes the
         structural check of its merged buffer — a payload not
         representable in the JSON map (a non-mapping payload,
         non-string keys, or non-serializable values at any nesting
         level) is the same hard failure as a crashed hook
      4. A passing tool commits as one `ToolContribution`; an empty
         merged buffer commits nothing
      5. A hard failure stops the delivery at the first failure in the
         walk — a clean error naming the tool, the action, and the
         failing cell path; the tool's contribution is discarded
      6. Compose the tools area of the committed contributions via
         `merge_cell_contributions` and return it

      Requirements:
      - The commit granularity is the tool — a tool's whole
        contribution commits only after every hook of the tool succeeds
        and the merged buffer is structurally representable
      - An address without subscriptions returns an empty mapping —
        the delivery is unobservable, the caller's output stays
        byte-identical
      - With no tool packages installed the checkpoint returns an
        empty mapping

      Constraints:
      - Do not apply any contribution outside the single composition
        after the walk
      - Do not skip a subscriber of the address
      - Do not read repositories, git, or the filesystem at the checkpoint
      - Do not print — the caller owns all output

---

Author: Goga
CreatedAt: 23/09/26
Description: |
  Owner of the schema domain hooks zone — the per-cell read view, the
  per-tool contribution merge, and the checkpoint surface over the
  hooks platform.
```

**.usages/ file** — `goga/schema/hooks/.usages/checkpoints.md` (full):

````md
# schema — amending cells with tool facts

How the schema generation uses the hooks zone of the schema domain:
delivering the cell-amendment checkpoint at the generation moment and
placing the contributed facts on the extended nodes. For every entry
path that generates the project map — the schema routine and the CLI
command.

## The checkpoint surface

One `SchemaHooks` object serves the checkpoints of a run — the surface
shares one registry per run, so a command that reaches further
checkpoints enumerates the tool packages once.

```python
from goga.schema.hooks import SchemaHooks

hooks = SchemaHooks()
```

## Amend each cell in the walk

Build the authored facts of each cell, hand them to the zone entry,
and place the returned tools area on the node — the key exists iff the
mapping is non-empty. Deliver only the cells surviving your filters —
filters prune delivery exactly as they prune output.

```python
from goga.schema.hooks import CellFacts, DependencyFacts

for cell in walk_in_tree_order(tree):
    facts = CellFacts(
        path=cell.path,
        description=cell.description,
        types=cell.type_names,
        usages=cell.usage_names,
        dependencies=[
            DependencyFacts(path=d.path, types=d.types, usages=d.usages)
            for d in cell.dependencies
        ],
        children=cell.child_paths,
    )
    node = build_base_node(cell)          # the six base fields, unchanged
    tools = hooks.amend_cell(cell=facts)
    if tools:
        node["tools"] = tools             # never an empty object
```

- The delivered view is built from the values you pass — the
  checkpoint reads no repository, no git, no files; the facts are the
  authored facts of the cell only.
- Tools are mutually blind: every hook reads the same authored facts,
  never another tool's contribution; each tool's contribution commits
  as a unit, in enumeration order, per cell.
- The action is hard: the first failing hook — or a structurally
  malformed contribution (a non-mapping payload, non-string keys, or
  non-serializable values at any nesting level) — stops the command
  with a clean error naming the tool, the action, and the failing cell
  path. No partial map reaches stdout.
- A tool package whose facade fails to import stops the command the
  same way — the error names the package (raised as ImportError at
  the registry build); convert it to the same clean error, never a
  raw traceback.
- An address without subscriptions returns an empty mapping — place
  no `tools` key; with no tool packages installed the output is
  byte-identical to the map without the extension.
- The map and the CODEMANIFEST files are never modified — the
  contributions live in memory for the run; repeated runs with the
  same tools reproduce the output deterministically.
- stdout stays data-clean JSON; every warning and diagnostic goes to
  stderr.

## The output shape

Extended nodes carry one wrapper key: `tools -> {tool identity ->
{fact -> value}}`. The namespace key is the platform tool identity —
the canonical hyphen form of the package name without the
`goga_tool_` prefix; a tool never names itself. Base fields and
extensions stay structurally separated; empty objects never appear at
any of the three levels.
````

### 3. Cell: goga/schema — MODIFIED

**CODEMANIFEST diff:**

- ADD the second Imports entry (after the existing `goga/ast` entry):

```yaml
  - Types:
      - SchemaHooks
      - CellFacts
      - DependencyFacts
    Usages:
      - checkpoints
    From: goga/schema/hooks
```

- CHANGE the Usages key `conventions:` → `convention:` (base-config spelling); the
  `documents` and `beautiful_json` entries stay unchanged.
- REPLACE the `Annotations:` block with:

```yaml
Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and
    testing in the project

  The caller uses the `documents` practice to load the project tree.
  The caller formats output through the `beautiful_json` practice.
  The caller uses the `checkpoints` practice to deliver the
  cell-amendment checkpoint of the generation walk and place the
  contributed facts on the extended nodes.
```

- REPLACE the body type `"schema(cells: list[str], max_depth: int = None, depends_on: list[str] = []) -> json:str"` with:

```yaml
"schema(cells: list[str], max_depth: int = None, depends_on: list[str] = []) -> json:str":
  location: schema.py
  annotations: |
    Generate a JSON schema of the project from the AST entity, extended
    by the tool contributions of the cell-amendment checkpoint.

    `cells`: cell paths to include in the output
    `max_depth`: maximum nesting depth of the cell tree
    `depends_on`: filter cells by their dependencies
    `json`: JSON string representing the project schema

    Use the `checkpoints` practice for the checkpoint delivery of the
    generation walk.

    Algorithm:
    1. Load the project document tree using the `documents` practice
    2. Recursively build a JSON tree with nested children nodes
    3. Apply filters in order: `cells`, `depends_on`, `max_depth`
    4. For every cell whose node survives the filters, in tree order:
       build the cell's authored facts and deliver them via the
       `SchemaHooks` entry — its amend_cell checkpoint; a `CellFacts`
       view over `DependencyFacts`, built from the loaded document tree
    5. Place the returned tools area on the node under the tools key
       iff the mapping is non-empty
    6. Return the JSON string using the `beautiful_json` practice

    Node format:
    {
      "cell": <path>,
      "description": <footer description>,
      "types": [<routine and entity names>],
      "usages": [<md files from .usages/>],
      "dependencies": {<path>: {"types": [...], "usages": [...]}},
      "children": [<children nodes>],
      "tools": {<tool identity>: {<fact>: <value>}}
    }

    The tools field is present on a node iff at least one tool wrote
    at least one fact on that cell.

    Requirements:
    - If `max_depth` is None: return the full tree without depth limits
    - If `depends_on` is an empty list: return the full tree without dependency filtering
    - If `depends_on` is non-empty: keep a cell only if its own dependencies or any descendant's dependencies contain at least one of the specified paths; cells without such a dependency are removed, while ancestor cells on the path to a kept descendant are preserved so the parent-child skeleton stays intact
    - If the tree is empty: return "[]"
    - If AST.errors is non-empty after loading: raise ValueError with the error count
    - Filters prune delivery exactly as they prune output — a cell is delivered iff its node appears in the output tree
    - The six base fields of every node are exactly what they would be without the extension
    - The tools key exists on a node iff at least one tool wrote at least one fact on that cell — never an empty object at any of the three levels
    - With no subscriptions — or no tool packages installed — the output is byte-identical to the six-field map: the tools key appears nowhere
    - Delivery is cell-major and deterministic — cells in tree order, tools in enumeration order within each cell; repeated runs over the same project with the same installed tools produce identical output
    - A hard failure of the checkpoint — a crashed hook or a structurally malformed contribution — and a register-facade import failure propagate out of the routine as errors naming the tool, the action, and the failing cell path (the package, for the import failure); no partial JSON is returned
    - The delivered view carries authored facts only — never another tool's contributions, generated data, or the run's filter parameters

    Constraints:
    - Do not modify the CODEMANIFEST files or the filesystem — the contributions live in memory for the run
```

- Footer: unchanged.

**.usages/ files:**

NEW — `goga/schema/.usages/registering-hooks.md` (full):

````md
# schema — registering hooks

How a `goga_tool_*` package subscribes its hooks to the schema domain
action. For tool package authors; no goga code changes are needed.

The domain opens one action — the cell amendment. It is a
read-and-contribute view over the authored facts of one cell,
delivered at the generation moment of the project map, while the walk
builds the node tree. It is a hard action.

## The events

| Address | Error class | Fires |
|---|---|---|
| `schema / amend_cell` | hard | At the generation moment of every entry path that builds the project map (`goga schema` and the schema routine). One delivery per cell whose node survives the filters — cells in tree order, tools in enumeration order within each cell. |

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("schema", "amend_cell", "coverage", cover_cell)
```

- `domain` — always `"schema"`; `action` — from the table; `name` —
  unique per tool per address; `hook` — the callable executed when the
  event fires.
- A hook receives values only for the parameters it declares by the
  fixed offered names: `context`, `self`.

## The amendment view

`amend_cell` delivers a `CellAmendment` view per tool, once per cell.
The reads: `cell` — the authored facts of the cell being built
(read-only; attribute assignment is blocked): `path`, `description`,
`types` (the entity and routine names), `usages` (the usages file
names), `dependencies` (each with `path`, `types`, `usages`), and
`children` (the authored children paths of the document tree). The
view never carries another tool's contributions, generated data, or
the run's filter parameters.

```python
def cover_cell(context):
    if is_interesting(context.cell.path):
        context.contribute({
            "coverage": measure_coverage(context.cell.path),
            "owner": owning_team(context.cell.types),
        })
```

- `contribute(facts)` buffers one mapping of facts for this cell —
  fact names to JSON-representable values; a later contribution of
  your tool on the same cell merges key-wise, a later write replacing
  an earlier one on key conflict.
- Your facts land on the cell node under your tool identity inside
  the `tools` wrapper area: `tools -> {<tool> -> {<fact>: <value>}}`.
  The identity is assigned by goga from the package name — a tool
  never names itself.

## The merge rules

- One JSON mapping per tool per cell; multiple hooks of your tool
  merge key-wise in registration order, later writes replacing
  earlier ones on key conflict.
- Tools never collide — each namespace lives under its own identity
  key; base fields and extensions stay structurally separated.
- Empty objects never appear: the `tools` key exists on a node iff at
  least one tool wrote at least one fact; your key exists iff you
  wrote at least one fact. An empty `contribute` contributes nothing.
- Tools are mutually blind — every hook reads the same authored
  facts; each tool's contribution commits as a unit, in enumeration
  order, per cell.

## Failure treatment

The action is hard. The first failing hook in the delivery walk stops
the command with a clean error naming the tool, the action, and the
failing cell path — no partial map is printed. A structurally
malformed contribution — a non-mapping payload, non-string keys, or
non-JSON-serializable values at any nesting level — fails the same
way; only JSON-representable facts are valid. A tool package whose
facade fails to import (raised as ImportError at the registry build)
stops the command the same way, the error naming the package — keep
the package facade import-clean.

## The run output

With no subscriptions — or no tool packages installed — `goga schema`
output is byte-identical to the map without the extension: no `tools`
key appears anywhere. The six base fields of every node are exactly
what they would be without the extension. The map and the CODEMANIFEST
files are never modified; repeated runs with the same tools reproduce
the output deterministically. stdout stays data-clean JSON — every
warning and diagnostic goes to stderr.

## Integration scenarios

- **Per-cell knowledge publication** — read `context.cell` (which
  types live here? which usages files? what does the cell import?)
  and publish your tool's facts about that cell.
- **Selective coverage** — contribute only on the cells your tool
  understands; silence is free — an absent key never appears.
- **Fact namespacing inside your area** — structure your facts as
  `{"<fact>": <value>}` freely; your identity key is the namespace,
  fact names are yours alone.
````

EXTEND — `goga/schema/.usages/schema-usage.md` (diff):

- Node Structure example gains the conditional field after `"children"`:

```json
  "tools": {"docs": {"score": 3}}
```

  with the note: present only when at least one installed tool
  contributed facts to this cell — never an empty object.
- Side Effects gains two bullets:

```md
- The routine delivers the cell-amendment checkpoint of the hooks
  platform — a hard action: a failing tool contribution stops the
  routine with an error naming the tool, the action, and the cell
  path; no partial JSON is returned
- With no subscribed tools the output is byte-identical to the map
  without the `tools` key — the routine still does not modify the
  file system
```

### 4. Cell: goga/commands/schema — MODIFIED

**CODEMANIFEST diff:**

- ADD the second Imports entry (after the existing `goga/schema` entry):

```yaml
  - Usages:
      - checkpoints
    From: goga/schema/hooks
```

- CHANGE the Usages key `conventions:` → `convention:`; the `click` entry stays.
- REPLACE the `Annotations:` block with (the verbatim base annotation under the
  `convention` key, the existing `click` and delegation lines kept, the
  `checkpoints` line appended):

```yaml
Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of
    development and testing in the project

  The developer must use the `click` practice to create CLI commands.
  The `schema` command delegates its business logic to `schema_logic`.
  The caller uses the `checkpoints` practice for the hard-failure handling of
  the schema generation — every failure of `schema_logic` surfaces as a clean
  command failure.
```
- REPLACE the body type `"schema(cells: list[str], max_depth: int = None, depends_on: list[str] = [])"` with:

```yaml
"schema(cells: list[str], max_depth: int = None, depends_on: list[str] = [])":
  location: schema.py
  annotations: |
    CLI wrapper for the schema command. Delegates business logic to `schema_logic`.

    `cells` (list[str]): cell paths to filter the schema output
    `max_depth` (int, optional): maximum nesting depth of the dependency tree
    `depends_on` (list[str]): filter cells by dependency relationship

    Use the `checkpoints` practice for the failure handling of the
    generation checkpoint.

    Algorithm:
    1. Invoke `schema_logic`(`cells`, `max_depth`, `depends_on`)
    2. On any error from `schema_logic` — AST parse errors, a hard failure
       of the cell-amendment checkpoint (a crashed hook or a structurally
       malformed contribution; the error names the tool, the action, and
       the failing cell path), or a register-facade import failure (the
       error names the package) — write the error message to stderr and
       exit 1; nothing is printed to stdout and no raw traceback is shown
    3. Output the result via `click`.echo

    Requirements:
    - stdout carries the machine-consumed JSON only — every warning and
      diagnostic goes to stderr
    - Exit 0 only on a complete generation
```

- Footer: unchanged.

**.usages/ file** — EXTEND `goga/commands/schema/.usages/schema.md` (diff):

- Purpose gains one sentence: "Extended cells may carry a `tools` area
  contributed by installed tool packages."
- Exit code section becomes:

```md
- 0 — success
- 1 — AST parsing errors found
- 1 — hard failure of the cell-amendment checkpoint: a failing or
  structurally malformed tool contribution (the message names the tool,
  the action, and the cell path) or a tool package import failure (the
  message names the package); nothing is printed to stdout
```

## Dependency Map

```
goga/hooks/catalog ──(declared_actions)──> goga/hooks (facade, unchanged re-export)
                                              │
                    (HookRegistry, wrap_context, build_hook_arguments, declared_actions;
                     usages per-tool-delivery, registering-hooks)
                                              │
                                              v
                                   goga/schema/hooks  [CREATED zone]
                                              ^
                    (SchemaHooks, CellFacts, DependencyFacts; usage checkpoints)
                                              │
goga/ast ──(AST)──────────────────────────────> goga/schema  [MODIFIED walk]
                                                │        ^
                        (schema AS schema_logic)│        │ (usage checkpoints)
                                                v        │
                                   goga/commands/schema  [MODIFIED CLI]
```

Acyclic. The zone imports only `goga/hooks` (cross-import prohibition vs `goga/schema`
holds — the config-zone pattern).

## Verification Checklist

After implementing each artifact:

1. **`goga/hooks/catalog`**
   - `goga lint` passes (80+1 cells, 0 errors)
   - The catalog inspection (`goga hooks`) lists `schema / amend_cell` with error class
     `hard` alongside the other domains' actions
   - `declared_actions` output unchanged for every previously published record (additivity)
2. **`goga/schema/hooks`**
   - `goga lint` passes on the new cell; every imported usage resolves
     (`goga/hooks/.usages/per-tool-delivery.md`, `goga/hooks/.usages/registering-hooks.md`)
   - Facade check: `python -c "from goga.schema.hooks import SchemaHooks, CellFacts, DependencyFacts, CellAmendment, ToolContribution, merge_cell_contributions"`
   - Unit tests per `convention` in `tests/schema/hooks/` (mirror of `goga/schema/hooks/`):
     buffer key-wise merge with later-wins; `merge_cell_contributions` no-empty composition
     and determinism; `amend_cell` passthrough (empty mapping) with no subscriptions;
     structural-check hard failure naming tool + action + cell path at the tool commit point
3. **`goga/schema`**
   - `goga lint` passes; the new Imports edge renders in `goga schema --depends-on goga/schema/hooks`
   - Byte-identity: with no tool packages installed (or none subscribed), `goga schema`
     output is byte-identical to the pre-change output; no `tools` key anywhere
   - Filters: delivery happens exactly on the cells present in the output (parametrized
     boundary tests over `cells` / `max_depth` / `depends_on`)
   - Six base fields of extended nodes identical to the no-extension run
4. **`goga/commands/schema`**
   - `goga lint` passes; CLI tested by direct handler call per `convention`
   - Failure conversion: checkpoint hard error and register-facade ImportError → message on
     stderr naming tool/action/cell path (or package), exit 1, stdout empty, no raw traceback
5. **Usages files**
   - File names match their reference keys (`checkpoints`, `registering-hooks`);
     `goga schema` lists them in the cells' `usages` fields
   - Self-contained (no cross-references to other practices); examples use the contract
     type names (`SchemaHooks`, `CellFacts`, `CellAmendment`)
6. **Integration (acceptance)**
   - A scratch `goga_tool_*` package subscribed to `schema / amend_cell` integrates without
     goga code changes; its facts appear under its identity key inside `tools` on the cells
     it extended; repeated runs reproduce identical output
