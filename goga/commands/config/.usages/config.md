# CLI Command: config

## Purpose

Output option values from the project configuration .goga/config.yml. Supports navigation across all fields via dot notation.

## Syntax

```
goga config <option>...
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `options` | list[str] | Paths to options in dot notation (e.g. build.task_executor.agent) |

## Output format

```
# language
python

# build.task_executor.agent
claude

# build.worktree
True
```

- Each option starts with a `# <path>` header
- Between options — empty line
- Primitives are output as-is
- Complex types are output in YAML format

## Exit code

- 0 — success
- 1 — error (option not found, configuration error)

## Examples

```bash
goga config language
goga config language build.task_executor.agent build.worktree
```
