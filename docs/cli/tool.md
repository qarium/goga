# goga tool

Invoke an external goga tool package by name.

## Synopsis

```bash
goga tool NAME [ARGS]...
```

## Description

`goga tool` provides dynamic invocation of externally installed tool packages. It auto-discovers Python packages with the `goga_tool_*` naming prefix, imports them, and delegates execution to their `main` function.

This mechanism allows extending goga with arbitrary tools without modifying the core codebase.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `NAME` | yes | The tool name (without the `goga_tool_` prefix). |
| `ARGS` | no | Arbitrary arguments passed through to the tool's `main` function. |

## How It Works

1. The tool name is mapped to a Python package: `goga_tool_<name>`.
2. The package is imported via `importlib.import_module`.
3. The package's `main(args: list[str])` function is called with any extra arguments.

## Examples

Run a tool named `mkdocs` (resolves to package `goga_tool_mkdocs`):

```bash
goga tool mkdocs
```

Run with extra arguments:

```bash
goga tool mkdocs --section api
```

## Creating a Tool Package

To create a custom tool package:

1. Create a Python package named `goga_tool_<name>`.
2. Define a `main(args: list[str])` function at the package level.
3. Install the package in the same environment as goga.

A minimal example:

```python
# goga_tool_hello/__init__.py
def main(args: list[str]) -> None:
    print(f"Hello! Args: {args}")
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Tool executed successfully |
| `1` | Tool package not found or has no `main` function |
