# goga

**goga -- contract-first development toolkit**

A CLI tool for working with the CODEMANIFEST specification -- assembly, extension, and plan-building workflow.

[goga](https://github.com/qarium/goga) provides a DSL for describing cell contracts, validates them against structural rules, extracts contracts from source code in multiple languages, and integrates with AI agents for automated development.

## Features

- **CODEMANIFEST DSL** -- Describe cell contracts with types, routines, imports, usages, and annotations in a structured YAML format
- **21 validation rules** -- AST-based linter checks your CODEMANIFEST files for structural correctness, import consistency, usage validity, mutation rules, and more
- **5 language parsers** -- Extract contracts from Python, Go, Kotlin, Swift, and JavaScript source code via tree-sitter
- **CLI toolkit** -- Commands for project initialization, linting, building, schema generation, synchronization, and contract extraction
- **AI agent skills** -- Built-in Claude skills for design, planning, review, and change management workflows
- **Docker-based builds** -- Execute build plans via ralphex in isolated containers

## Quick install

```bash
pip install goga
```

Or run without installing:

```bash
uvx goga
```

## Next steps

- [Getting Started](getting-started.md) -- Initialize your first goga project
- [Configuration](configuration.md) -- Configure `.goga/config.yml`
- [Examples](examples.md) -- CODEMANIFEST examples for all DSL features
- [CLI Reference](cli-reference.md) -- Full command reference
