# Architecture Plan — `codegraph`: prospective cell graph for existing code

## Topic

Short name: `codegraph`.
Plan path: `.goga/history/2026/codegraph/arch.md`.

Derive the prospective cell structure of the project's existing code (one of
python, golang, javascript, kotlin, swift per run) and print it as a JSON tree —
a full analogue of the `goga schema` output minus manifest-only fields.

## Implementation Order

Cells ordered leaves to root; each step names the reason for its position.

1. `goga/codegraph/facts` — **create**. No Imports (leaf): the shared data
   vocabulary every other new cell consumes.
2. `goga/codegraph/analysis` — **create**. Depends on `goga/codegraph/facts`
   (types + `records` practice).
3. `goga/codegraph` — **create**. Depends on `goga/codegraph/facts`,
   `goga/codegraph/analysis`, and the existing `goga/config` (as-is).
4. `goga/commands/codegraph` — **create**. Depends on `goga/codegraph`
   (`codegraph AS codegraph_logic` + `codegraph-usage` practice).
5. `goga/commands` — **modify**. Imports and re-exports the new command from
   `goga/commands/codegraph`; updates the `cli-commands` practice.
6. `goga` — **modify**. Registers `codegraph` in the root command group
   (`app()` command table in `cli.py` wiring).

Documentation pages are implementation-stage deliverables recorded in the task
file (`docs/features/codegraph/index.md`, `docs/features/codegraph/cli.md`,
rows in `docs/cli/index.md` and `docs/features/index.md`) — they are not
CODEMANIFEST/`.usages` artifacts of this plan.

## Artifacts

### Cell 1: `goga/codegraph/facts` [create]

#### CODEMANIFEST — `goga/codegraph/facts/CODEMANIFEST`

```yaml
Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell is the shared data vocabulary of the code analysis: every
  record carries facts extracted from the project sources. All model
  classes are immutable data classes per `convention` — frozen,
  keyword-only construction. The records carry data only, no behavior;
  the analysis stages own all logic.

---

"Declaration(path: Path, name: str, is_public: bool)":
  location: facts.py
  annotations: |
    One named code declaration found in a source file.

    `path`: file that defines the declaration, relative to the project root
    `name`: declaration name as written in the source
    `is_public`: public visibility under the language rules

    Requirements:
    - Immutable data class per `convention`
  properties:
    "path -> Path": |
      Defining file, relative to the project root.
    "name -> str": |
      Declaration name as written in the source.
    "is_public -> bool": |
      True when public under the language visibility rules.

"ImportRef(source: Path, specifier: str, names: list[str], is_relative: bool, is_wildcard: bool)":
  location: facts.py
  annotations: |
    One import statement or name usage collected from a source file.

    `source`: file that contains the import or usage
    `specifier`: raw module, package, or specifier string as written;
                 empty for pure name usages
    `names`: imported or used names; empty for wildcard imports
    `is_relative`: True for relative forms — Python relative imports,
                   JavaScript relative specifiers
    `is_wildcard`: True for star imports

    Requirements:
    - Immutable data class per `convention`
  properties:
    "source -> Path": |
      File that contains the import or usage.
    "specifier -> str": |
      Raw origin string as written in the source; empty for pure name usages.
    "names -> list[str]": |
      Imported or used names; empty for wildcard imports.
    "is_relative -> bool": |
      True when the import uses a relative form.
    "is_wildcard -> bool": |
      True when the import is a star import.

"FileFacts(path: Path, declarations: list[Declaration], imports: list[ImportRef], exports: list[str], module: str)":
  location: facts.py
  annotations: |
    Analysis result of one source file.

    `path`: file location relative to the project root
    `declarations`: named declarations found in the file
    `imports`: imports and name usages found in the file
    `exports`: explicit export list declared by the file; empty when
               the file declares none
    `module`: package or module declaration of the file; empty string
              when the language declares none

    Requirements:
    - Immutable data class per `convention`
  properties:
    "path -> Path": |
      Analyzed file, relative to the project root.
    "declarations -> list[Declaration]": |
      Named declarations of the file.
    "imports -> list[ImportRef]": |
      Imports and name usages of the file.
    "exports -> list[str]": |
      Explicit export list (Python __all__); empty when absent.
    "module -> str": |
      Package or module declaration (Kotlin package); empty when absent.

"Unit(path: Path, files: list[Path], facade: list[str], is_cell: bool)":
  location: facts.py
  annotations: |
    One language unit of the project — a candidate prospective cell.

    `path`: unit directory relative to the project root
    `files`: source files of the unit
    `facade`: public type names of the unit
    `is_cell`: True only when the facade is non-empty; a unit without a
               facade survives as a structural ancestor only

    Requirements:
    - Immutable data class per `convention`
    - `facade` is sorted and duplicate-free
  properties:
    "path -> Path": |
      Unit directory, relative to the project root.
    "files -> list[Path]": |
      Source files of the unit.
    "facade -> list[str]": |
      Sorted unique public type names of the unit.
    "is_cell -> bool": |
      True when the unit has a facade and is a prospective cell.

"CellLink(source: Path, target: Path, types: list[str])":
  location: facts.py
  annotations: |
    One resolved reference between two units.

    `source`: importing unit directory
    `target`: defining unit directory
    `types`: facade types of `target` imported by `source`

    Requirements:
    - Immutable data class per `convention`
    - `types` is sorted and duplicate-free
  properties:
    "source -> Path": |
      Importing unit directory.
    "target -> Path": |
      Defining unit directory.
    "types -> list[str]": |
      Sorted unique facade types carried by the link.

"CodegraphNode(cell: str, types: list[str], dependencies: dict[str, list[str]], children: list[CodegraphNode])":
  location: facts.py
  annotations: |
    One node of the output tree — the code-derived analogue of a
    schema node.

    `cell`: cell path relative to the project root
    `types`: facade type names of the cell
    `dependencies`: target cell path to the imported facade types
    `children`: nested child nodes

    Requirements:
    - Immutable data class per `convention`
    - Manifest-only fields never appear on a node
  properties:
    "cell -> str": |
      Cell path relative to the project root.
    "types -> list[str]": |
      Facade type names of the cell.
    "dependencies -> dict[str, list[str]]": |
      Target cell path to its imported facade types; no usages key.
    "children -> list[CodegraphNode]": |
      Nested child nodes.

---

Author: Goga
CreatedAt: 14/10/26
Description: |
  Shared data records of the code analysis.
```

#### .usages file — `goga/codegraph/facts/.usages/records.md`

```md
# Facts Records — the data vocabulary of the code analysis

Domain: the immutable records produced and consumed by the codegraph analysis
pipeline. Target audience: implementers and consumers of the analysis stages —
every stage reads and writes exactly these records.

## Composition of the analysis flow

The records form one linear flow; each stage consumes the previous output:

    source files
      └─> FileFacts (path, declarations, imports, exports, module)
            ├─> Unit (path, files, facade, is_cell)
            └─> CellLink (source, target, types)
                  └─> CodegraphNode (cell, types, dependencies, children)

Declaration and ImportRef never travel alone — they are nested inside
FileFacts.

## Import

All records are importable from the cell facade:

```python
from goga.codegraph.facts import (
    CellLink,
    CodegraphNode,
    Declaration,
    FileFacts,
    ImportRef,
    Unit,
)
```

## Constructing file facts

One parsed source file contributes declarations and imports:

```python
from pathlib import Path

from goga.codegraph.facts import Declaration, FileFacts, ImportRef

render = Path("goga/codegraph/render.py")

facts = FileFacts(
    path=render,
    declarations=[
        Declaration(path=render, name="render_graph", is_public=True),
    ],
    imports=[
        ImportRef(
            source=render,
            specifier="goga.codegraph.facts",
            names=["CellLink", "CodegraphNode", "Unit"],
            is_relative=False,
            is_wildcard=False,
        ),
    ],
    exports=[],  # empty when the file declares no explicit export list
    module="",   # empty when the language declares no package/module
)
```

Preconditions:

- paths are relative to the project root
- `is_public` is decided by the language visibility rules before construction
- a wildcard import carries no `names`; a pure name usage (Swift) carries an
  empty `specifier`

## Deriving units

Group file facts into units; the facade comes from the language facade rules:

```python
from goga.codegraph.facts import Unit

unit = Unit(
    path=Path("goga/codegraph/facts"),
    files=[Path("goga/codegraph/facts/facts.py")],
    facade=["CellLink", "CodegraphNode", "Declaration", "FileFacts", "ImportRef", "Unit"],
    is_cell=True,
)
```

A unit with an empty facade is not a cell: construct it with `is_cell=False` —
it survives only as a structural ancestor of nested cells.

## Composing links and output nodes

Resolution yields one link per unit pair; the renderer folds links into node
dependencies:

```python
from goga.codegraph.facts import CellLink, CodegraphNode

link = CellLink(
    source=Path("goga/codegraph"),
    target=Path("goga/codegraph/facts"),
    types=["CellLink", "CodegraphNode", "FileFacts", "Unit"],
)

node = CodegraphNode(
    cell="goga/codegraph",
    types=["codegraph", "discover_sources", "render_graph"],
    dependencies={
        "goga/codegraph/facts": ["CellLink", "CodegraphNode", "FileFacts", "Unit"],
    },
    children=[],
)
```

Constraints relevant to the consumer:

- `facade` and link `types` are sorted and duplicate-free; `dependencies`
  values carry sorted type lists
- all records are immutable — build new records instead of mutating
- `CodegraphNode` never carries manifest-only fields (description, usages,
  tools) — they exist only in CODEMANIFEST
```

### Cell 2: `goga/codegraph/analysis` [create]

#### CODEMANIFEST — `goga/codegraph/analysis/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - Declaration
      - ImportRef
      - FileFacts
      - Unit
      - CellLink
    Usages:
      - records
    From: goga/codegraph/facts

Usages:
  convention: .goga/usages/conventions.md
  tree-sitter-python: .goga/usages/cooks/tree-sitter-python.md
  tree-sitter-go: .goga/usages/cooks/tree-sitter-go.md
  tree-sitter-js: .goga/usages/cooks/tree-sitter-js.md
  tree-sitter-kotlin: .goga/usages/cooks/tree-sitter-kotlin.md
  tree-sitter-swift: .goga/usages/cooks/tree-sitter-swift.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the per-language static analysis of source files:
  parse each file once, extract declarations and imports, derive the
  language units with their facades, and resolve every imported or
  used name to its exact defining unit. Parse a file with the
  tree-sitter grammar of its language — `tree-sitter-python`,
  `tree-sitter-go`, `tree-sitter-js`, `tree-sitter-kotlin`,
  `tree-sitter-swift`. Build every result record via the `records`
  practice.

---

"collect_facts(files: list[Path], language: str) -> facts: list[FileFacts]":
  location: collect.py
  annotations: |
    Parse every source file once and collect its declarations and
    imports into file facts.

    `files`: source files to analyze, relative to the project root
    `language`: the single configured language — python, golang,
                javascript, kotlin, swift
    `facts`: one FileFacts per input file, input order preserved

    Algorithm:
    1. For each file — read it once and parse it with the tree-sitter
       grammar of `language`
    2. Fail closed on unparseable input: a parse tree containing any
       ERROR or MISSING node raises an error naming the file
    3. Collect declarations with their public visibility per the
       language rules: python — top-level definitions, and for a
       package __init__.py all top-level bound names — definitions,
       imported names, assignment targets; golang — exported iff the
       name starts with an upper-case letter; javascript — exported
       declarations; kotlin — declarations with an explicit or
       implicit public modifier; swift — public and open declarations
    4. Collect imports per the language rules: python — plain and
       from-imports with relative dots and wildcards captured;
       golang — quoted import paths; javascript — ESM imports with
       relative specifiers marked; kotlin — fully qualified imports
       with wildcard support and the package declaration recorded as
       the module; swift — module imports without names plus used
       type names
    5. Record the explicit export list where the language has one —
       python __all__
    6. Build one FileFacts per file with `Declaration` and `ImportRef`
       via the `records` practice

    Requirements:
    - Each file is read and parsed exactly once — no re-parsing
    - A wildcard import records no names
    - The order of `facts` follows the order of `files`

    Constraints:
    - Do not resolve names to their origins here — resolution is a
      separate stage
    - Do not skip or recover unparseable files — always fail closed

"derive_units(facts: list[FileFacts], language: str) -> units: list[Unit]":
  location: units.py
  annotations: |
    Derive the language units of the project with their facade types.

    `facts`: file facts of all analyzed files
    `language`: the single configured language
    `units`: one Unit per language unit, deterministic path order

    Algorithm:
    1. Group the files into units by the language unit rule: python —
       a directory containing __init__.py; golang — a directory
       containing .go files; javascript — a directory containing
       index.js; kotlin — a directory containing .kt files; swift — a
       directory containing .swift files — a unit owns exactly the
       source files of its own directory, nested directories form
       their own units, and files in directories that are not units
       belong to no unit (they are analyzed but never grouped)
    2. Mirror the directory nesting — nested units become children of
       the enclosing unit
    3. Derive each unit facade per the language facade rules: python —
       the __all__ entries of the unit __init__.py when declared,
       otherwise the non-underscore top-level names bound there;
       golang — the exported identifiers of the unit files;
       javascript — the exports of the unit index.js, named default
       exports included, anonymous excluded; kotlin — the public
       declarations; swift — the public and open declarations only
    4. Mark a unit with an empty facade as not a cell — it survives
       only as a structural ancestor
    5. Build the sorted duplicate-free facade and each Unit via the
       `records` practice

    Requirements:
    - The facade contains exactly the public surface the language
      cell rules define — no more, no fewer
    - Facade names are sorted and unique

    Constraints:
    - Do not read files here — work over the collected facts only
    - Do not invent units for directories without sources

"resolve_links(units: list[Unit], facts: list[FileFacts], language: str, root: Path) -> links: list[CellLink]":
  location: resolve.py
  annotations: |
    Resolve every imported or used name to its exact defining unit
    and derive the unit-to-unit links.

    `units`: all derived units
    `facts`: file facts of all analyzed files
    `language`: the single configured language
    `root`: absolute project root
    `links`: one CellLink per importing and defining unit pair

    Algorithm:
    1. Build the project-wide index over all units and facts first —
       unit path to language identity, facade name to defining unit;
       resolution runs second, never unit-locally
    2. Resolve each import to its origin per the language origin
       rules: python — absolute modules against the candidate roots
       <root> and <root>/src in priority order, relative modules
       against the importing file; golang — module mode by the module
       path from go.mod at the root, every import external without
       go.mod; javascript — relative specifiers only, Node-style file
       or directory resolution, bare specifiers external; kotlin —
       import paths against the package declarations of the analyzed
       files; swift — type usages by a type name unique within the
       project
    3. Expand wildcard imports to the names actually used in the
       importing file
    4. Keep only resolutions that land on a facade type of a unit
       cell inside the project
    5. Aggregate the kept resolutions into one link per unit pair
       with sorted unique types via the `records` practice

    Requirements:
    - Every linked type origin is exact — resolved by the language
      semantics, never by name coincidence
    - A name resolving outside the project, to a non-facade
      definition, or to the importing unit itself produces no link
      and no error
    - A link is produced only when the importing unit is a cell —
      imports of a unit with an empty facade produce no link and
      no error
    - Link types are sorted and unique

    Constraints:
    - Do not read environment variables — resolution is static and
      deterministic
    - Do not validate the graph — cycles and other rule violations
      pass through as they are

---

Author: Goga
CreatedAt: 14/10/26
Description: |
  Per-language static analysis of source files: facts, units, links.
```

#### .usages file — `goga/codegraph/analysis/.usages/stages.md`

```md
# Analysis Stages — consuming the three-stage pipeline

Domain: how the orchestrator consumes the codegraph analysis stages. Target
audience: the caller that runs the whole analysis — collect the file facts,
derive the units, resolve the links — over one configured language.

## Import

All stages are importable from the cell facade:

```python
from goga.codegraph.analysis import collect_facts, derive_units, resolve_links
```

## Stage order

The stages form one pipeline; each consumes the previous output. Never call a
later stage with partial input — every stage expects the complete project-wide
collection. `files` is the complete list of discovered source paths — discovery
belongs to the caller (the orchestrator cell), not to the analysis stages:

```python
from pathlib import Path

from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

root = Path.cwd()

facts = collect_facts(files, language="python")
units = derive_units(facts, language="python")
links = resolve_links(units, facts, language="python", root=root)
```

- `collect_facts` — parse each file exactly once; an unparseable file raises an
  error naming the file, and the caller surfaces it as a command failure
- `derive_units` — pure grouping over the collected facts; reads no files
- `resolve_links` — collect-then-resolve over the complete set; never
  unit-locally

## Failure behavior relevant to the caller

- The only failing stage is `collect_facts` — an unparseable file (a parse
  tree with an ERROR or MISSING node) aborts the run
- External names never fail resolution: they produce no link silently
- The returned records are immutable — pass them on as they are

## Constraints

- One language per run — pass the same `language` to every stage
- Do not re-order the stages; resolution needs all units and all facts
- The result is deterministic for identical inputs
```

### Cell 3: `goga/codegraph` [create]

#### CODEMANIFEST — `goga/codegraph/CODEMANIFEST`

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
  beautiful_json: .goga/usages/cooks/beautiful_json.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell derives the prospective cell graph of the project code and
  renders it as a JSON tree. The analysis pipeline is consumed via
  the `stages` practice, the result records via `records`, the project
  configuration via `project-configuration`, and the serialization
  via `beautiful_json`.

---

"codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> json: str":
  location: codegraph.py
  annotations: |
    Derive the prospective cell graph of the project code and render
    it as a JSON tree.

    `cells`: cell paths to include in the output
    `max_depth`: maximum nesting depth of the tree; None — no limit
    `depends_on`: keep only cells whose dependencies reach the given paths
    `json`: JSON document of the tree; an empty project renders as []

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
    6. Render the tree with `render_graph`
    7. Return the JSON document

    Requirements:
    - Deterministic and idempotent — identical code and configuration
      produce byte-identical output
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

"render_graph(units: list[Unit], links: list[CellLink], cells: list[str], max_depth: int | None, depends_on: list[str]) -> json: str":
  location: render.py
  annotations: |
    Assemble the hierarchical node tree and render it as JSON.

    `units`: all derived units
    `links`: all resolved links
    `cells`: cell paths to include in the output
    `max_depth`: maximum nesting depth; None — no limit
    `depends_on`: keep a cell only when its own or any descendant
                  dependencies contain at least one given path;
                  ancestors of kept cells stay so the parent-child
                  skeleton remains intact
    `json`: the serialized tree; an empty tree renders as []

    Algorithm:
    1. Nest the units by their paths mirroring the directory tree —
       only units that are cells carry output nodes; non-cell units
       survive only as structural ancestors of nested cells
    2. Aggregate the links into per-node dependencies — target cell
       path to the sorted unique imported types, no usages key; build
       the `CodegraphNode` records via the `records` practice
    3. Apply the filters in order: `cells`, `depends_on`, `max_depth`
       — the same behavior as the schema output
    4. Serialize via `beautiful_json`; an empty tree renders as []

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
  Prospective cell graph of the project code as a JSON tree.
```

#### .usages file — `goga/codegraph/.usages/codegraph-usage.md`

```md
# Codegraph Usage — producing and consuming the prospective cell graph

Domain: how to run the codegraph analysis and consume its JSON output.
Target audience: the CLI command that wraps this cell and the later bootstrap
stages that draft CODEMANIFEST files from the graph.

## Import

The entry point is importable from the cell facade:

```python
from goga.codegraph import codegraph
```

## Running the analysis

No arguments are required — the command reads the configured language and the
lint exclusions from the project configuration:

```python
document = codegraph()
```

All three schema-compatible filters are optional:

```python
filtered = codegraph(
    cells=["goga/codegraph"],   # only these cell paths
    max_depth=2,                 # nesting limit
    depends_on=["goga/config"],  # keep only cells depending on these
)
```

## Output node format

Each node carries exactly the code-derivable fields — the schema node minus
the manifest-only fields (no description, usages, tools; dependencies carry
types only):

```json
[
    {
        "cell": "goga/codegraph",
        "children": [],
        "dependencies": {
            "goga/config": ["load_project_config"]
        },
        "types": ["codegraph", "discover_sources", "render_graph"]
    }
]
```

A project with no analyzable sources renders as `[]`.

## Guarantees for the consumer

- Deterministic: identical code and configuration produce byte-identical
  output
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

### Cell 4: `goga/commands/codegraph` [create]

#### CODEMANIFEST — `goga/commands/codegraph/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - codegraph AS codegraph_logic
    Usages:
      - codegraph-usage
    From: goga/codegraph

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

  The developer must use the `click` practice to create the CLI command.
  The `codegraph` command delegates its business logic to
  `codegraph_logic` and holds no domain knowledge of its own.
  The caller uses the `codegraph-usage` practice for the output and
  failure contract behind the command.

---

"codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])":
  location: codegraph.py
  annotations: |
    CLI wrapper for the codegraph command. Delegates business logic
    to `codegraph_logic`.

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
    3. Output the result via `click`.echo

    Requirements:
    - stdout carries the JSON document only — every diagnostic goes
      to stderr
    - Exit 0 only on a complete generation

---

Author: Goga
CreatedAt: 14/10/26
Description: |
  CLI wrapper that prints the prospective cell graph of existing code.
```

#### .usages files

None — the consumer documentation lives in the provider practice
`codegraph-usage` (same pattern as `goga/commands/schema`).

### Cell 5: `goga/commands` [modify]

#### CODEMANIFEST — `goga/commands/CODEMANIFEST` (diff)

Add to `Imports` (new block):

```yaml
  - Types:
      - codegraph
    From: goga/commands/codegraph
```

Add to Body (new embedding, alongside the existing ones):

```yaml
->codegraph: {}
```

Everything else unchanged.

#### .usages file — `goga/commands/.usages/cli-commands.md` (diff)

1. First paragraph: "re-exports 16 CLI commands" → "re-exports 17 CLI commands".
2. Facade `Import` block: add `codegraph` to the shared import list (after
   `schema`).
3. "Each command is available from its subcell": add
   `from goga.commands.codegraph import codegraph`.
4. Registration block: add `app.add_command(codegraph)` after
   `app.add_command(schema)`.
5. Command list table: add row
   `| codegraph | goga/commands/codegraph/ | Prospective cell graph from existing code |`.

### Cell 6: `goga` [modify]

#### CODEMANIFEST — `goga/CODEMANIFEST` (diff)

1. In the `Imports` block `From: goga/commands`, add `codegraph` to the
   `Types` list (after `schema`).
2. In the `app()` annotation, add `- codegraph` to the Commands list (after
   `schema`).

Everything else unchanged. The code wiring follows the `cli-commands`
practice: facade import line and `app.add_command(codegraph)` in `cli.py`.

## Dependency Map

```
goga/config (existing, as-is)
    │ load_project_config, ProjectConfig, LintConfig + project-configuration
    ▼
goga/codegraph/facts [create]
    │ Unit, CellLink, CodegraphNode + records
    ▼
goga/codegraph/analysis [create]
    │ collect_facts, derive_units, resolve_links + stages
    ▼
goga/codegraph [create]
    │ codegraph AS codegraph_logic + codegraph-usage
    ▼
goga/commands/codegraph [create]
    │ codegraph
    ▼
goga/commands [modify: Imports + ->codegraph: {} + cli-commands]
    │ (existing nesting)
    ▼
goga (cli.py) [modify: app() command table]
```

No cross-imports; no cycles.

## Verification Checklist

After implementing each artifact, verify:

- `goga/codegraph/facts`
  - `goga lint` clean for the cell; records importable via
    `python -c "from goga.codegraph.facts import Unit, CellLink, CodegraphNode"`
    (facade `__all__` per the language rules)
  - all records frozen and keyword-only; empty defaults for collections
- `goga/codegraph/analysis`
  - `goga lint` clean; facade exposes the three stages
  - unit tests per `convention`: per-language declaration/import extraction,
    ERROR/MISSING failure naming the file, facade rules (including python
    `__all__` and fallback, swift public/open only), origin rules (python
    `<root>`/`<root>/src`, go module mode, js relative-only, kotlin package,
    swift unique name), wildcard expansion, external names silent
- `goga/codegraph`
  - `goga lint` clean; `python -c "from goga.codegraph import codegraph"`
  - determinism: two runs over unchanged code/config produce byte-identical
    output; empty project renders `[]`
  - filter parity with the `schema` command output behavior
    (cells / depends_on / max_depth semantics, ancestor skeleton)
  - read-only: project tree unchanged after a run
- `goga/commands/codegraph`
  - `goga lint` clean; command registered; CliRunner tests: success echoes
    JSON with exit 0; each failure mode (uninitialized project, unsupported
    language, unparseable file) exits 1 with stderr message and empty stdout
- `goga/commands` (modify)
  - `goga lint` clean; `cli-commands` practice updated (17 commands);
    embedding compiles
- `goga` (modify)
  - `goga --help` lists `codegraph`; `goga codegraph --help` renders the
    command docstring per the CLI docstring conventions
  - `goga lint` and `goga schema` still work unchanged
- **Documentation (implementation-stage deliverables)**
  - `docs/features/codegraph/index.md` describes the domain — deriving the
    prospective cell graph of the existing code, the per-language unit and
    facade rules, and the boundaries (descriptive, no validation)
  - `docs/features/codegraph/cli.md` is the full command reference —
    synopsis, the three filters (cell paths, max depth, depends-on),
    behavior, exit codes, and the failure modes
  - the command table in `docs/cli/index.md` gains the `goga codegraph` row
  - the domains table in `docs/features/index.md` gains the Codegraph row
