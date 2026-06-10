<div align="center">

# goga

A CLI and Agent tools for working with the **CODEMANIFEST** specification.

Describe cell contracts with a structured YAML DSL, validate them, extract contracts from source code, and integrate with AI agents for automated development.

[Documentation](https://qarium.github.io/goga/) · [Getting Started](https://qarium.github.io/goga/getting-started/) · [CLI Reference](https://qarium.github.io/goga/cli/)

</div>

---

## Install

```bash
pip install goga
```

## Quick start

```bash
goga init          # Initialize a project
goga lint .        # Validate CODEMANIFEST files
goga connect <agent>  # Install skills into an AI agent
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

- **CODEMANIFEST DSL** — Describe cell contracts with types, routines, imports, usages, and annotations
- **Validation** — AST-based linter with 21 document-level and 3 tree-level rules
- **Language parsers** — Extract contracts from Python, Go, Kotlin, Swift, and JavaScript via tree-sitter
- **CLI toolkit** — init, lint, build, schema, connect, and contract extraction commands
- **AI agent skills** — Architecture, design, planning, review, acceptance, and change management workflows
- **Docker builds** — Execute build plans via ralphex in isolated containers

## Documentation

Full documentation is available at [qarium.github.io/goga](https://qarium.github.io/goga/).