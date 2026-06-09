# Architecture Overview

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

Goga enforces 21 rules split into two scopes:

| Scope | Count | Applied by |
|---|---|---|
| Document-level | 18 | Visitor |
| Tree-level | 3 | Analyzer |

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
          | (18 doc rules) |   | (3 tree rules) |
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

- [AST Node Types](ast-nodes.md) -- the node hierarchy that makes up a document tree.
- [AST Factory](ast-factory.md) -- how YAML becomes an AST.
- [AST Visitor](ast-visitor.md) -- single-document validation.
- [AST Analyzer](ast-analyzer.md) -- tree-level validation.
- [Error Handling](ast-errors.md) -- the error hierarchy.
- [Validation Rules](validation-rules.md) -- full reference of all 21 rules.
- [Contract Extraction](contract-extraction.md) -- how source code is parsed.
