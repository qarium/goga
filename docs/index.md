# goga

A CLI and Agent tools for working with the CODEMANIFEST specification -- assembly, extension, and plan-building workflow.

[goga](https://github.com/qarium/goga) provides a DSL for describing cell contracts, validates them against structural rules, extracts contracts from source code in multiple languages, and integrates with AI agents for automated development.

## Features

- **CODEMANIFEST** -- Describe cell contracts with types, routines, imports, usages, and annotations in a structured YAML format
- **Validation rules** -- AST-based linter checks your CODEMANIFEST files for structural correctness, import consistency, usage validity, mutation rules, and more
- **Language parsers** -- Extract contracts from Python, Go, Kotlin, Swift, and JavaScript source code via tree-sitter
- **CLI toolkit** -- Commands for project initialization, linting, building, schema generation, synchronization and contract extraction
- **AI agent skills** -- Built-in agent skills for architecture, design, planning, review, acceptance and change management workflows
- **Docker-based builds** -- Execute build plans via ralphex in isolated containers

## Quick install

```bash
pip install goga
```

## Next steps

- [Getting Started](getting-started.md) -- Initialize your first goga project
- [Workflow](workflow/index.md) -- The agent-driven feature development cycle
- [Configuration](configuration.md) -- Configure `.goga/config.yml`
- [Cell](cell/index.md) -- Cell structure, usages, and CODEMANIFEST DSL reference
- [CLI Reference](cli/index.md) -- Full command reference
