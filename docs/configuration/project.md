# Project Configuration

goga reads project configuration from `.goga/config.yml` in the project root. This file is created by `goga init` and can be edited manually.

The page covers the **global** fields and the sections that belong to no single domain. Every domain-owned section (`build`, `pipeline`, `tools`, `usages`, `lint`, `topics`) is documented in full in its domain's **Configuration** page — see [Domain sections](#domain-sections).

## File location

```
.goga/config.yml
```

The config loader looks for this file relative to the current working directory.

For the machine-wide `~/.goga/config.yml`, see [Home Configuration](home.md). To read values back from the command line, see [`goga config`](cli.md).

## Example configuration

```yaml
language: python
image: qarium/goga-python-3.14:1.3
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
  # review_executor:              # optional review-phase control
  #   skip: false                 # true → tasks-only run (ralph-loop --tasks-only)
  #   agent: codex                # differing agent → two-pass run (tasks, then --review)
  #   roles: [quality, testing]   # reviewer composition; absent/[] → full default set
  #   env:                        # review-pass env layer (requires agent when non-empty)
  #     ANTHROPIC_MODEL: reviewer
  #   base_ref: origin/1.2.x      # review diff base — branch name or commit hash
  #   patience: 3                 # stop the external review after N unchanged rounds
  # proxy: http://corp:3123        # optional HTTP/HTTPS proxy URL for the build container
  # hosts:                         # optional docker run --add-host entries
  #   foo.local: 127.0.0.1

pipeline:
  agent: claude
  env:
    ANTHROPIC_API_KEY: sk-ant-...
  # proxy: http://corp:3123        # optional HTTP/HTTPS proxy URL for the pipeline container
  # hosts:                         # optional docker run --add-host entries
  #   foo.local: 127.0.0.1

codemanifest:
  usages:
    conventions: .goga/usages/conventions.md

  annotations: |
    Follow the project `conventions` for all code generation.

# tools: optional — declared tools are installed together by `goga install`
# tools:
#   viewer: latest        # → no specifier (pip selects newest)
#   afm: 1.0.x            # → ~=1.0.0
#   ralph-loop: 1.x       # → ~=1.0
#   go: 1.0.1             # → ==1.0.1

# usages: optional — git dependencies whose cell-level .usages/ are synced by `goga usages sync` and status-checked by `goga usages status`
# usages:
#   libs:
#     click:
#       git: https://github.com/pallets/click.git
#       ref: 8.1.7         # optional — branch, tag, or commit; omit for the default branch
#       root: docs         # optional — subpath inside the repo to walk .usages from; omit for the clone root

# lint: optional — directories ignored by `goga lint` (exact relative paths, no glob)
# lint:
#   ignore:
#     - .venv/
#     - build/dist

# topics: optional — topic creation base and publication template (`goga topics create`)
# topics:
#   base_ref: origin/main                     # base of the created topic branches
#   publish_commit: "goga: create topic {slug}"  # commit message template ({slug} optional)
```

## Fields reference

### Top-level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | `string` | Yes | Project language. One of: `python`, `golang`, `kotlin`, `swift`, `javascript` |
| `image` | `string` | No | Docker image used by `goga build` and `goga pipeline` (e.g. `qarium/goga-python-3.14:1.3`). Consumers raise an error when it is unset. The deprecated `build.image` field is rejected — set this top-level field instead |
| `dockerfile` | `string` | No | Path to a project Dockerfile. When set, `goga build --update` and `goga pipeline --update` build the image locally from this Dockerfile (fatal on build failure). When unset (default), `--update` pulls `image` from the registry instead (non-fatal warning on pull failure) |
| `commands` | mapping | No | Reserved for future prompt customization. Defaults to `{}` |
| `codemanifest` | mapping | No | Global codemanifest configuration — see [codemanifest](#codemanifest) |
| `build` | mapping | No | Build pipeline settings — see [Build — Configuration](../features/build/configuration.md) |
| `pipeline` | mapping | No | Pipeline (afm) execution settings — see [Pipelines — Configuration](../features/pipelines/configuration.md) |
| `tools` | mapping | No | goga-tool version declarations for bulk install — see [Install — Configuration](../features/install/configuration.md) |
| `usages` | mapping | No | Git dependencies of cell-level usages — see [Usages — Configuration](../features/usages/configuration.md) |
| `lint` | mapping | No | Linter ignore list — see [Lint — Configuration](../features/lint/configuration.md) |
| `topics` | mapping | No | Topic creation base and publication template — see [Topics — Configuration](../features/topics/configuration.md) |

### Domain sections

Each domain-owned section is documented in full — every field, typing rule, and CLI precedence — in its domain's **Configuration** page:

| Section | Domain | Consumed by |
|---|---|---|
| `build` (incl. `task_executor`, `review_executor`) | [Build](../features/build/configuration.md) | `goga build` |
| `pipeline` | [Pipelines](../features/pipelines/configuration.md) | `goga pipeline` |
| `tools` | [Install](../features/install/configuration.md) | `goga install` (bulk mode) |
| `usages` | [Usages](../features/usages/configuration.md) | `goga usages sync` / `goga usages status` |
| `lint` | [Lint](../features/lint/configuration.md) | `goga lint` |
| `topics` | [Topics](../features/topics/configuration.md) | `goga topics create` |

### codemanifest

The `codemanifest` section is global — it belongs to no single domain. It feeds every CODEMANIFEST of the project (see [Cell](../cell/index.md)).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `usages` | mapping | No | Named practices available in CODEMANIFEST files. Format: `{name: path/to/file.md}`. Defaults to `{}` |
| `annotations` | `string` | No | Free-text instructions for AI agents. Defaults to `None` |

## Pre-built Docker images

goga provides prebuilt language images for build execution:

| Language | Images |
|----------|--------|
| Python | `qarium/goga-python-3.10:1.3` through `qarium/goga-python-3.14:1.3` |
| Go | `qarium/goga-golang-1.23:1.3` through `qarium/goga-golang-1.26:1.3` |
| JavaScript | `qarium/goga-node-22:1.3`, `qarium/goga-node-24:1.3` |
| Kotlin | `qarium/goga-kotlin-2.0:1.3` through `qarium/goga-kotlin-2.3:1.3` |
| Swift | `qarium/goga-swift-6.0:1.3` through `qarium/goga-swift-6.2:1.3` |

## Validation errors

The config loader raises specific exceptions for invalid configuration:

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | `.goga/config.yml` does not exist or is empty |
| `KeyError` | Missing required field (`language`, or `build.task_executor` when `build` is present) |
| `ValueError` | Invalid field value (wrong type, empty string, non-mapping where mapping expected), or the deprecated `build.image` field is present. `build.review_executor` adds: non-mapping section (`build.review_executor must be a mapping`), non-bool `skip` (a YAML `1` is rejected), non-string `agent`, `roles` that is not a list of strings, a non-mapping `env` (`build.review_executor.env must be a mapping in .goga/config.yml`), `env` with non-string keys/values (`build.review_executor.env must have string keys and values`), a non-string `base_ref` (`build.review_executor.base_ref must be a string in .goga/config.yml`), or a non-int `patience`, including a YAML boolean (`build.review_executor.patience must be an int in .goga/config.yml`). `topics` adds: a non-mapping section (`'topics' must be a mapping in .goga/config.yml`) or a non-string field (`topics.base_ref must be a string in .goga/config.yml`, `topics.publish_commit must be a string in .goga/config.yml`) |

## Implementation details

Configuration is loaded as immutable frozen dataclasses (`frozen=True`, `kw_only=True`). Once loaded, the `ProjectConfig` object cannot be modified. This ensures consistent behavior across the build pipeline.
