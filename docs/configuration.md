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
image: qarium/goga-python-3.14:1.0
# dockerfile: .goga/Dockerfile     # optional — when set, `--update` builds from this Dockerfile instead of pulling

build:
  task_executor:
    agent: claude
    env:
      ANTHROPIC_API_KEY: sk-ant-...

  worktree: false
  skip_finalize: false
  session_timeout: 30m
  idle_timeout: 10m
  max_iterations: 10
  # proxy: http://corp:3128        # optional HTTP/HTTPS proxy URL for the build container
  # hosts:                         # optional docker run --add-host entries
  #   foo.local: 127.0.0.1

pipeline:
  agent: claude
  env:
    ANTHROPIC_API_KEY: sk-ant-...
  # proxy: http://corp:3128        # optional HTTP/HTTPS proxy URL for the pipeline container
  # hosts:                         # optional docker run --add-host entries
  #   foo.local: 127.0.0.1

codemanifest:
  usages:
    conventions: .goga/usages/conventions.md

  annotations: |
    Follow the project `conventions` for all code generation.
```

## Fields reference

### Top-level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | `string` | Yes | Project language. One of: `python`, `golang`, `kotlin`, `swift`, `javascript` |
| `image` | `string` | No | Docker image used by `goga build` and `goga pipeline` (e.g. `qarium/goga-python-3.14:1.0`). Consumers raise an error when it is unset. |
| `dockerfile` | `string` | No | Path to a project Dockerfile. When set, `goga build --update` and `goga pipeline --update` build the image locally from this Dockerfile (fatal on build failure). When unset (default), `--update` pulls `image` from the registry instead (non-fatal warning on pull failure) |
| `build` | mapping | No | Build pipeline settings. Optional at the loader level; `goga build` raises a `ClickException` when the section is absent |
| `pipeline` | mapping | No | Pipeline (afm) execution settings. Optional at the loader level; `goga pipeline` raises a `ClickException` when the section is absent |
| `commands` | mapping | No | Reserved for future prompt customization. Defaults to `{}` |
| `codemanifest` | mapping | No | Global codemanifest configuration |

### build

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_executor` | mapping | Yes | AI agent configuration |
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
| `proxy` | `string` | No | HTTP/HTTPS proxy URL for the build container. When set, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` are written to the container env-file. Overridden by the `--proxy` CLI option |
| `hosts` | mapping | No | Host→IP mapping for `docker run --add-host`. Defaults to `{}`. Augmented by the repeatable `--add-host` CLI option (CLI wins on key conflict) |

> The deprecated `build.image` field is rejected with a `ValueError`. Set the top-level `image` field instead.

### build.task_executor

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | `string` | Yes | AI executor. Supported values: `claude`, `codex`, `copilot`, `gemini`, or `custom:/path/to/script` |
| `env` | mapping | No | Environment variables passed to the agent. Keys and values must be strings. Defaults to `{}` |

### pipeline

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | `string` | Yes | afm client command agent for `goga pipeline` (e.g. `claude`, `codex`) |
| `env` | mapping | No | Environment variables passed into the pipeline container. Keys and values must be strings. Defaults to `{}` |
| `proxy` | `string` | No | HTTP/HTTPS proxy URL for the pipeline container. When set, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` are written to the container env-file. Overridden by the `--proxy` CLI option |
| `hosts` | mapping | No | Host→IP mapping for `docker run --add-host`. Defaults to `{}`. Augmented by the repeatable `--add-host` CLI option (CLI wins on key conflict) |

### codemanifest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `usages` | mapping | No | Named practices available in CODEMANIFEST files. Format: `{name: path/to/file.md}`. Defaults to `{}` |
| `annotations` | `string` | No | Free-text instructions for AI agents. Defaults to `None` |

## Pre-built Docker images

goga provides prebuilt language images for build execution:

| Language | Images |
|----------|--------|
| Python | `qarium/goga-python-3.10:1.0` through `qarium/goga-python-3.14:1.0` |
| Go | `qarium/goga-golang-1.23:1.0` through `qarium/goga-golang-1.26:1.0` |
| JavaScript | `qarium/goga-node-22:1.0`, `qarium/goga-node-24:1.0` |
| Kotlin | `qarium/goga-kotlin-2.0:1.0` through `qarium/goga-kotlin-2.3:1.0` |
| Swift | `qarium/goga-swift-6.0:1.0` through `qarium/goga-swift-6.2:1.0` |

## Validation errors

The config loader raises specific exceptions for invalid configuration:

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | `.goga/config.yml` does not exist or is empty |
| `KeyError` | Missing required field (`language`, or `build.task_executor` when `build` is present) |
| `ValueError` | Invalid field value (wrong type, empty string, non-mapping where mapping expected), or the deprecated `build.image` field is present |

## Implementation details

Configuration is loaded as immutable frozen dataclasses (`frozen=True`, `kw_only=True`). Once loaded, the `Config` object cannot be modified. This ensures consistent behavior across the build pipeline.
