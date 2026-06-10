# CLI Command: tool

## Purpose

CLI wrapper for running external tool commands. Parses click arguments and dynamically imports the tool package.

## Syntax

```
goga tool <name> [args...]
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | Yes | Tool package name (without `goga_tool_` prefix) |

## Tool package arguments

All remaining arguments are passed as-is to the tool package's `main(argv)` function.

## Exit code

- 0 — success
- 1 — error (package not found, main function missing)

## Examples

```bash
goga tool mytool arg1 --flag value
```

## Tool package requirements

The `goga_tool_<name>` package must provide a function:

```python
def main(argv: list[str]) -> None:
    """Entry point for the tool package."""
    ...
```
