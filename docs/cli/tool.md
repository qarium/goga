# goga tool

Invoke an external goga tool package by name.

## Synopsis

```bash
goga tool NAME [ARGS]...
```

## Description

`goga tool` provides dynamic invocation of externally installed tool packages. It auto-discovers Python packages with the `goga_tool_*` naming prefix, imports them, and delegates execution to their `main` function.

This mechanism allows extending goga with arbitrary tools without modifying the core codebase.

The entry point may optionally receive the project AST. The dispatcher inspects the entry point's signature and supplies an injection only when the entry point declares a matching parameter name; the value is built lazily.

## Arguments

| Argument | Required | Description                                                       |
|----------|----------|-------------------------------------------------------------------|
| `NAME`   | yes      | The tool name (without the `goga_tool_` prefix).                  |
| `ARGS`   | no       | Arbitrary arguments passed through to the tool's `main` function. |

## How It Works

1. The tool name is mapped to a Python package: `goga_tool_<name>`.
2. The package is imported via `importlib.import_module`.
3. The package's `main` function is retrieved.
4. The optional injections are computed by projecting the entry point's signature against the injections the dispatcher can supply (`build_injections`).
5. The `main` function is called with the extra arguments and the projected injections forwarded as keyword arguments.

## Examples

Run a tool named `mkdocs` (resolves to package `goga_tool_mkdocs`):

```bash
goga tool mkdocs
```

Run with extra arguments:

```bash
goga tool hello --help
```

## Creating a Tool Package

To create a custom tool package:

1. Create a Python package named `goga_tool_<name>`.
2. Define a `main(argv: list[str])` function at the package level.
3. Install the package in the same environment as goga.

A minimal entry point takes the forwarded arguments:

```python
# goga_tool_hello/__init__.py
def main(argv: list[str]) -> None:
    print(f"Hello! Args: {argv}")
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
- The AST is loaded from the current project root (`AST(".")`). There is no CLI flag to override the path or scope.
- Validation errors (`ast.errors`) are passed through unchanged. The dispatcher does not block execution and does not filter errors — the tool decides how to react to an invalid manifest tree.

## Exit Codes

| Code | Meaning                                          |
|------|--------------------------------------------------|
| `0`  | Tool executed successfully                       |
| `1`  | Tool package not found or has no `main` function |
