<div align="center">

<img src="docs/assets/goga.svg" alt="goga" width="180" />

# Goga

A new semantic layer between specification and implementation based on the [**CODEMANIFEST**](https://github.com/qarium/codemanifest/blob/0.0.x/specs/en.md) specification — helping humans and AI agents reason about project structure at a higher level of abstraction.

A full-fledged **Specification-Driven Development (SDD)** framework: describe cell contracts with a structured YAML DSL, validate them, extract contracts from source code, and drive an end-to-end agent workflow — propose, brainstorm, design, plan, build, change, and acceptance — under the hood.

**Languages**

<img src="docs/assets/brands/python.svg" alt="Python" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/javascript.svg" alt="JavaScript" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/kotlin.svg" alt="Kotlin" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/swift.svg" alt="Swift" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/go.svg" alt="Go" width="40" height="40">

**Agents**

<img src="docs/assets/brands/claude.svg" alt="Claude" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/cursor.svg" alt="Cursor" width="40" height="40">

[Documentation](https://qarium.github.io/goga/) · [Getting Started](https://qarium.github.io/goga/getting-started/) · [Workflow](https://qarium.github.io/goga/workflow/)

</div>

---

## Install

```bash
pip install goga
```

Connect goga to your agent

```bash
goga connect <agent>
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
propose → brainstorm → apply → design → plan → goga build → change → acceptance
```

Reviews are optional at every stage. For smaller changes, use one of the shortcut paths described in the [Workflow](https://qarium.github.io/goga/workflow/) section.

**5. Visualize the result** — once `apply` has produced cells on disk, inspect the architecture:

```bash
goga schema | goga tool viewer
```

## What is CODEMANIFEST?

CODEMANIFEST is a YAML DSL that defines **cell contracts** — language-agnostic API specifications with types, routines, imports, usages, and annotations.

```yaml
"calculate_total(a: int, b: int) -> total:int":
  location: calculator.py
  annotations: |
    Calculates the sum of two operands.
    `a`: first operand
    `b`: second operand
```

## Features

- **Specification-Driven Development** — Contracts are the source of truth; the agent workflow produces architecture, code, and tests from them
- **CODEMANIFEST DSL** — Describe cell contracts with types, routines, imports, usages, and annotations
- **Agent workflow** — Built-in cycle: `propose → brainstorm → apply → design → plan → build → change → acceptance`, with review checkpoints and shortcut paths for smaller changes
- **Validation** — AST-based linter with 21 document-level and 3 tree-level rules
- **Language parsers** — Extract contracts from Python, Go, Kotlin, Swift, and JavaScript via tree-sitter
- **CLI toolkit** — init, lint, build, schema, connect, and contract extraction commands
- **Docker builds** — Execute build plans via ralphex in isolated containers

## Documentation

Full documentation is available at [qarium.github.io/goga](https://qarium.github.io/goga/).