# CLI Command: tool

## Purpose

CLI wrapper for running external tool commands. Parses click arguments, dynamically imports the tool package, and invokes its entry point. The entry point may optionally receive the project AST.

## Syntax

```
goga tool <name> [args...]
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | Yes | Tool package name (without `goga_tool_` prefix) |

## Tool package arguments

All remaining arguments are captured and forwarded to the tool package's entry point.

## Exit code

- 0 — success
- 1 — error (package not found, entry point missing, manifest load failure)

## Examples

```bash
goga tool mytool arg1 --flag value
```

## Tool package requirements

The `goga_tool_<name>` package must provide an entry point named `main`:

```python
def main(argv: list[str]) -> None:
    """Entry point for the tool package."""
    ...
```

## Optional injections

The entry point may declare optional parameters to receive values the dispatcher can supply. The dispatcher inspects the entry point's signature and supplies an injection only when the entry point declares a matching parameter name. Parameters are forwarded as keyword arguments.

Currently the dispatcher offers:

| Parameter | Type | Value | Built lazily |
|-----------|------|-------|--------------|
| `ast` | `goga.ast.AST` | The project AST, loaded from the current project root | Yes — only when `main` declares `ast` |

Declaring `ast` receives the project AST:

```python
from goga.ast import AST


def main(argv: list[str], *, ast: AST) -> None:
    # argv: forwarded CLI arguments
    # ast: the project AST, already loaded
    for doc in ast.tree:
        ...
    if ast.errors:
        # validation errors are passed through unfiltered
        ...
```

Not declaring `ast` keeps the entry point identical to the minimal contract, and the AST is never built:

```python
def main(argv: list[str]) -> None: ...
```

## Opt-in rules

- Opt-in is by parameter name. A parameter with a different name is ignored and triggers no AST construction.
- Any keyword-capable parameter (positional-or-keyword or keyword-only) named `ast` receives the injection. Positional-only parameters are not supplied.
- The AST is loaded from the current project root. There is no CLI flag to override the path or scope.
- Validation errors (`ast.errors`) are passed through unchanged. The dispatcher does not block execution and does not filter errors — the tool decides how to react to an invalid manifest tree.

## Extensibility

Adding a future optional injection is a dispatcher-side change: a new parameter name is registered in the offered set together with the way its value is built. Tool packages opt in by declaring the matching parameter name.
