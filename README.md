<div align="center">

<img src="docs/assets/goga.svg" alt="goga" width="180" />

# Goga

A new semantic layer between specification and implementation based on the [**CODEMANIFEST**](https://github.com/qarium/codemanifest/blob/0.0.x/specs/en.md) specification — helping humans and AI agents reason about project structure at a higher level of abstraction.

A full-fledged **Specification-Driven Development (SDD)** framework: describe cell contracts with a structured YAML DSL, validate them, extract contracts from source code, and drive an end-to-end agent workflow — propose, brainstorm, design, plan, build, change, and accept — under the hood.

**Languages**

<img src="docs/assets/brands/python.svg" alt="Python" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/javascript.svg" alt="JavaScript" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/kotlin.svg" alt="Kotlin" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/swift.svg" alt="Swift" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/go.svg" alt="Go" width="40" height="40">

**Agents**

<img src="docs/assets/brands/claude.svg" alt="Claude" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/cursor.svg" alt="Cursor" width="40" height="40">

[Documentation](https://qarium.github.io/goga/) · [Getting Started](https://qarium.github.io/goga/getting-started/) · [Workflow](https://qarium.github.io/goga/workflow/) · [Configuration](https://qarium.github.io/goga/configuration/)

</div>

---

## Install

```bash
pip install goga
```

`goga build` and `goga pipeline` launch a Docker container, so Docker must be installed and accessible on your host:

```bash
docker info
```

Connect goga to your agent

```bash
goga connect <agent>
```

To upgrade goga later and re-sync all connected agents, use:

```bash
goga upgrade
```

## Quick start

Start a new project from scratch and build your first feature end-to-end.

**1. Initialize the project** — the interactive wizard sets up `.goga/config.yml`, language conventions, and (optionally) a `Dockerfile`:

```bash
goga init
```

**2. Open your agent** — launch the agent you connected via `goga connect` (e.g., Claude Code) in the project directory. All `goga-<command>` skills are now available.

**3. Formulate the first feature** — describe what you want to create:

```text
/goga:propose <what you want to create>
```

The example above uses Claude Code style. For other agents, invoke the skill directly: `goga-propose`.

**4. Run the workflow** — each subsequent command takes the previous artifact as input and produces the next one:

```
propose → brainstorm → apply → design → plan → goga build → change → accept
```

Reviews are optional at every stage. For smaller changes, use one of the shortcut paths described in the [Workflow](https://qarium.github.io/goga/workflow/) section.

**5. Visualize the result** — once `apply` has produced cells on disk, inspect the architecture:

```bash
goga schema | goga tool viewer
```

## What is a cell?

A **cell** is a directory that encapsulates a distinct responsibility domain with a well-defined API boundary. Each cell contains a `CODEMANIFEST` file describing its contract and an optional `.usages/` directory with documentation for API consumers.

```
cell/
├── CODEMANIFEST       # YAML DSL describing the API contract
└── .usages/*.md       # Practices for working with the cell
```

The rule of thumb is **one responsibility zone — one cell**. A new cell is born when logic can be decoupled, owns distinct data models, must be reused, or can be stated in a single phrase without "and".

### Anatomy of a contract

A `CODEMANIFEST` consists of three sections separated by `---`:

- **Header** — `Imports` (types and usages from other cells), `Usages` (named practices), `Annotations` (global directives)
- **Body** — entities and routines that form the cell's public API
- **Footer** — `Author`, `CreatedAt`, `Description`

Cells expose three kinds of types:

- **Entity types** — objects with state and behavior (services, configurations, data models): properties + methods
- **Routine types** — single operations (transformers, factories, validators, parsers): no state
- **Embedded types** — re-exports of imported types: `->ExternalService`

Specialization is expressed with the `::` mutation syntax. The DSL stays language-agnostic — `BaseEntity::ExtendedEntity` may be realized through inheritance, composition, an adapter, or an interface implementation in the target language.

### Example

```yaml
Imports:
  - Types:
      - AnotherCellType
    From: path/to/another_cell

Usages:
  conventions: .goga/usages/conventions.md

Annotations: |
  Use `conventions` when writing code.

---

"ParseInput(input: string) -> data:List<byte>":
  location: parser.py
  annotations: |
    Parses raw input into a byte buffer.
  
    `input`: raw request payload

"HTTPServer(name: String)":
  location: server.py
  properties:
    "host -> String": |
      Bind address for incoming connections.
  methods:
    "handleRequest(req: Request) -> resp:Response": |
      Dispatches a single HTTP request.

      Algorithm:
      1. Parse input from `req` with `ParseInput`
      2. Filter result by some logic
      3. Save filtered result in `resp`
      4. Return `resp` object

---

Author: Goga
CreatedAt: 01/01/26
Description: |
  HTTP entry point cell.
```

## Features

- **Specification-Driven Development** — Contracts are the source of truth; the agent workflow produces architecture, code, and tests from them
- **CODEMANIFEST DSL** — Describe cell contracts with types, routines, imports, usages, and annotations
- **Agent workflow** — Built-in cycle: `propose → brainstorm → apply → design → plan → build → change → accept`, with review checkpoints and shortcut paths for smaller changes
- **Validation** — AST-based linter with 21 document-level and 3 tree-level rules
- **Language parsers** — Extract contracts from Python, Go, Kotlin, Swift, and JavaScript via tree-sitter
- **CLI toolkit** — init, lint, build, schema, connect, upgrade, contract extraction, and pipeline commands
- **Docker builds & pipelines** — Execute build plans via ralphex and run afm pipelines in isolated containers, with automatic forwarding of AI-agent credentials (claude/codex/opencode), optional HTTP proxy / `--add-host` support for corporate environments, and persistent pipeline state across runs

## Documentation

Full documentation is available at [qarium.github.io/goga](https://qarium.github.io/goga/).