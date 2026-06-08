# Configuration

goga reads project configuration from `.goga/config.yml` in the project root. This file is created by `goga init` and can be edited manually.

## File location

```
.goga/config.yml
```

The config loader looks for this file relative to the current working directory.

## Example configuration

```yaml
language: python
build:
  task_executor:
    agent: claude
    env:
      ANTHROPIC_API_KEY: sk-ant-...
  image: qarium/goga-python-3.14:1.0
  worktree: false
  skip_finalize: false
  session_timeout: 30m
  idle_timeout: 10m
  max_iterations: 10
codemanifest:
  usages:
    conventions: .goga/usages/conventions.md
  annotations: |
    Follow the project conventions for all code generation.
```

## Fields reference

### Top-level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | `string` | Yes | Project language. One of: `python`, `golang`, `kotlin`, `swift`, `javascript` |
| `build` | mapping | Yes | Build pipeline settings |
| `commands` | mapping | No | Reserved for future prompt customization. Defaults to `{}` |
| `codemanifest` | mapping | No | Global codemanifest configuration |

### build

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_executor` | mapping | Yes | AI agent configuration |
| `image` | `string` | No | Docker image for build execution (e.g. `qarium/goga-python-3.14:1.0`) |
| `worktree` | `bool` | No | Use isolated git worktree for builds |
| `skip_finalize` | `bool` | No | Skip the ralphex finalization step |
| `session_timeout` | `string` | No | Session timeout in Go duration format (e.g. `30m`, `1h`) |
| `idle_timeout` | `string` | No | Idle timeout in Go duration format |
| `wait` | `string` | No | Wait time on rate limit in Go duration format |
| `max_iterations` | `int` | No | Maximum task iterations |
| `review_patience` | `int` | No | Stop review after N unchanged rounds |
| `prompts_dir` | `string` | No | Path to custom ralphex prompts |
| `agents_dir` | `string` | No | Path to custom ralphex agents |
| `codex_review` | `bool` | No | Enable external codex review |

### build.task_executor

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | `string` | Yes | AI executor. Supported values: `claude`, `codex`, `copilot`, `gemini`, or `custom:/path/to/script` |
| `env` | mapping | No | Environment variables passed to the agent. Keys and values must be strings. Defaults to `{}` |

### codemanifest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `usages` | mapping | No | Named practices available in CODEMANIFEST files. Format: `{name: path/to/file.md}`. Defaults to `{}` |
| `annotations` | `string` | No | Free-text instructions for AI agents. Defaults to `None` |

## Prebuilt Docker images

goga provides prebuilt language images for build execution:

| Language | Images |
|----------|--------|
| Python | `qarium/goga-python-3.10:1.0` through `qarium/goga-python-3.14:1.0` |
| Go | `qarium/goga-golang-1.23.12:1.0` through `qarium/goga-golang-1.26.4:1.0` |
| JavaScript | `qarium/goga-node-22:1.0`, `qarium/goga-node-24:1.0` |
| Kotlin | `qarium/goga-kotlin-2.0.21:1.0` through `qarium/goga-kotlin-2.3.21:1.0` |
| Swift | `qarium/goga-swift-6.0.3:1.0` through `qarium/goga-swift-6.2.4:1.0` |

## Validation errors

The config loader raises specific exceptions for invalid configuration:

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | `.goga/config.yml` does not exist or is empty |
| `KeyError` | Missing required field (`language`, `build`, or `build.task_executor`) |
| `ValueError` | Invalid field value (wrong type, empty string, non-mapping where mapping expected) |

## Implementation details

Configuration is loaded as immutable frozen dataclasses (`frozen=True`, `kw_only=True`). Once loaded, the `Config` object cannot be modified. This ensures consistent behavior across the build pipeline.
