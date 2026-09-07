# Architecture Overview

These pages document the **AST internals** — the validated tree goga builds from a project's CODEMANIFEST files. They are written for goga maintainers and contributors; for authoring cells, start at [Cells](../index.md) and the [CODEMANIFEST DSL](../codemanifest.md).

Goga validates cell contracts defined in CODEMANIFEST files through an AST-based pipeline. This page describes the main components and how data flows through the system.

## Components

### AST Pipeline

The core of goga is a three-stage pipeline that transforms CODEMANIFEST YAML files into validated document trees:

1. **Factory** -- parses YAML files and builds `DocumentRoot` trees of AST nodes.
2. **Visitor** -- validates individual documents against document-level rules.
3. **Analyzer** -- validates the entire tree against tree-level rules that require cross-document context.

### Contract Extraction

Language-specific parsers built on tree-sitter extract implemented contracts from source code. The system supports Python, Go, Kotlin, Swift, and JavaScript. Each parser produces a list of `EntityContract` and `RoutineContract` objects that describe what the code actually implements.

### Validation Rules

Goga enforces validation rules split into two scopes:

| Scope | Applied by |
|---|---|
| Document-level | Visitor |
| Tree-level | Analyzer |

Document-level rules validate a single CODEMANIFEST file in isolation. Tree-level rules validate relationships between multiple files, such as import resolution and cyclic dependency detection.

### CLI Layer

A Click-based command-line interface orchestrates the pipeline. Commands accept a project path, invoke the factory to build the tree, run visitor and analyzer passes, and report any errors.

## Pipeline Flow

```
                    CODEMANIFEST YAML files
                              |
                              v
                    +-------------------+
                    |     Factory       |
                    |  (YAML -> AST)    |
                    +-------------------+
                              |
                     DocumentRoot tree
                              |
                    +---------+---------+
                    |                   |
                    v                   v
          +----------------+   +----------------+
          |    Visitor     |   |   Analyzer     |
          | (doc rules) |   | (tree rules) |
          +----------------+   +----------------+
                    |                   |
                    v                   v
          DocumentRuleError    ASTRuleError
                    |                   |
                    +---------+---------+
                              |
                              v
                      CLI output / exit code


        Source code files (.py, .go, .kt, .swift, .js)
                              |
                              v
                    +-------------------+
                    | Contract          |
                    | Extraction        |
                    | (tree-sitter)     |
                    +-------------------+
                              |
                  EntityContract / RoutineContract
                              |
                              v
                    Compared against CODEMANIFEST
                    declarations for completeness
```

## Where to Next

- [AST Node Types](nodes.md) -- the node hierarchy that makes up a document tree.
- [AST Factory](factory.md) -- how YAML becomes an AST.
- [AST Visitor](visitor.md) -- single-document validation.
- [AST Analyzer](analyzer.md) -- tree-level validation.
- [Error Hierarchy](../../features/lint/error-hierarchy.md) -- the error classes validation raises.
- [Validation Rules](../../features/lint/validation-rules.md) -- the full rules reference.
- [Contract Extraction](contract-extraction.md) -- how source code is parsed.
