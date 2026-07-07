# Project Configuration — goga/config

## Overview

The `goga.config` package provides unified access to project configuration through the `.goga/config.yml` file.

## Facade

Import all types directly from `goga.config`:

```python
from goga.config import (
    Config,
    BuildConfig,
    TaskExecutorConfig,
    PipelineConfig,
    CodemanifestConfig,
    load_config,
)
```

## Loading Configuration

### load_config() -> Config

Parses `.goga/config.yml` from the current working directory (CWD).

**Usage**:

```python
from goga.config import load_config

config = load_config()
```

**Behavior**:
- `.goga/config.yml` is mandatory — raises `FileNotFoundError` if missing or empty
- Root YAML element must be a mapping — raises `ValueError` otherwise
- Required sections: `language`, `image` (top-level), `pipeline`, `pipeline.agent`, `build`, `build.task_executor`, `build.task_executor.agent`
- Raises `yaml.YAMLError` on invalid YAML syntax

**Error handling**:

```python
from goga.config import load_config

try:
    config = load_config()
except FileNotFoundError:
    # .goga/config.yml not found or empty
except KeyError as e:
    # Missing required section
    print(e)
except ValueError as e:
    # Invalid field value
    print(e)
except yaml.YAMLError as e:
    # YAML syntax error
    print(e)
```

## .goga/config.yml Schema

Minimal valid configuration:

```yaml
language: python
image: qarium/goga-python-3.12:latest
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
```

Full configuration with all options:

```yaml
language: python
image: qarium/goga-python-3.12:latest
commands:
  test: pytest
pipeline:
  agent: claude
  env:
    ANTHROPIC_API_KEY: sk-xxx
  proxy: http://corp:3128        # HTTP/HTTPS proxy URL
  hosts:                         # docker run --add-host entries
    foo.local: 127.0.0.1
build:
  task_executor:
    agent: claude
    env:
      ANTHROPIC_API_KEY: sk-xxx
      MODEL: claude-sonnet-4-6
  proxy: http://corp:3128        # HTTP/HTTPS proxy URL
  hosts:                         # docker run --add-host entries
    foo.local: 127.0.0.1
  worktree: true
  skip_finalize: false
  session_timeout: "30m"
  idle_timeout: "1h"
  wait: "5m"
  max_iterations: 10
  review_patience: 3
  prompts_dir: /custom/prompts
  agents_dir: /custom/agents
  codex_review: true
codemanifest:
  usages:
    usage_name: path/to/file.md
  annotations: |
    Use the `usage_name` practice.
```

### Required Fields

| Field                       | Type    | Description                                                         |
|-----------------------------|---------|---------------------------------------------------------------------|
| `language`                  | str     | Project programming language                                        |
| `image`                     | str     | Top-level Docker image shared by build and pipeline                 |
| `pipeline`                  | mapping | Pipeline configuration block                                        |
| `pipeline.agent`            | str     | Agent name; resolved at runtime into the in-container `*-as-claude.sh` wrapper path and written to afm `client.command` |
| `build.task_executor`       | mapping | AI agent configuration block                                        |
| `build.task_executor.agent` | str     | Agent name; resolved at runtime into the in-container `*-as-claude.sh` wrapper path and written to ralphex `claude_command` |

#### Agent name semantics

Both `pipeline.agent` and `build.task_executor.agent` are agent names as
declared in the goga Docker image — any value matching the
`/home/goga/bin/<agent>-as-claude.sh` wrapper convention (e.g. `claude`,
`codex`, `opencode`). The config layer does no validation: resolution and
absence-of-wrapper errors are surfaced by the downstream tools (ralphex,
afm) that consume these fields.

### Optional Fields

| Field                       | Type    | Default                | Description                                             |
|-----------------------------|---------|------------------------|---------------------------------------------------------|
| `commands`                  | mapping | `{}`                   | Prompt customization hooks (reserved)                   |
| `pipeline.env`              | mapping | `{}`                   | Environment variables for pipeline runs (`{str: str}`)  |
| `pipeline.proxy`             | str     | None                   | HTTP/HTTPS proxy URL for the pipeline container                |
| `pipeline.hosts`             | mapping | `{}`                   | Host→IP mapping for `docker run --add-host` (pipeline)         |
| `build.task_executor.env`   | mapping | `{}`                   | Environment variables for builds (`{str: str}`)         |
| `build.proxy`                | str     | None                   | HTTP/HTTPS proxy URL for the build container                   |
| `build.hosts`                | mapping | `{}`                   | Host→IP mapping for `docker run --add-host` (build)            |
| `build.worktree`            | bool    | None                   | Run in an isolated git worktree                         |
| `build.skip_finalize`       | bool    | None                   | Skip the finalization step                              |
| `build.session_timeout`     | str     | None                   | Session timeout (Go duration format)                    |
| `build.idle_timeout`        | str     | None                   | Idle timeout (Go duration format)                       |
| `build.wait`                | str     | None                   | Rate-limit retry wait (Go duration format)              |
| `build.max_iterations`      | int     | None                   | Maximum task iteration count                            |
| `build.review_patience`     | int     | None                   | Review convergence threshold                            |
| `build.prompts_dir`         | str     | None                   | Custom prompt directory path                            |
| `build.agents_dir`          | str     | None                   | Custom agent directory path                             |
| `build.codex_review`        | bool    | None                   | Enable external codex review (mapped to ralphex `codex_enabled`) |
| `codemanifest`              | mapping | None                   | CODEMANIFEST usage and annotation config                |
| `codemanifest.usages`       | mapping | `{}`                   | Usage name-to-path mapping (`{str: str}`)               |
| `codemanifest.annotations`  | str     | None                   | Freeform annotations for the AI agent                   |

## Accessing Configuration Data

All objects are immutable frozen dataclasses (`frozen=True`). Fields expose read-only access.

```python
config = load_config()

# Top-level accessors
config.lang           # str — project language
config.image          # str | None — top-level Docker image (shared by build and pipeline)
config.build          # BuildConfig
config.pipeline       # PipelineConfig
config.commands       # dict — custom command hooks

# PipelineConfig fields
config.pipeline.agent   # str — afm client.command inside the container
config.pipeline.env     # dict — {str: str}
config.pipeline.proxy   # str | None — HTTP/HTTPS proxy URL for the pipeline container
config.pipeline.hosts   # dict[str, str] — docker run --add-host entries

# BuildConfig fields
config.build.task_executor   # TaskExecutorConfig
config.build.worktree        # bool | None
config.build.proxy           # str | None — HTTP/HTTPS proxy URL for the build container
config.build.hosts           # dict[str, str] — docker run --add-host entries

# TaskExecutorConfig fields
config.build.task_executor.agent  # str
config.build.task_executor.env    # dict — {str: str}

# CodemanifestConfig fields
config.codemanifest                    # CodemanifestConfig | None
config.codemanifest.usages             # dict — {str: str}
config.codemanifest.annotations        # str | None
```

## Immutability

All config objects are frozen — mutation attempts raise `FrozenInstanceError`:

```python
config = load_config()
config.lang = "go"  # raises dataclasses.FrozenInstanceError
```

To derive a modified copy, use `dataclasses.replace`:

```python
from dataclasses import replace
from goga.config import Config

new_config = replace(config, lang="go")
```

## Proxy and hosts semantics

`build.proxy` and `pipeline.proxy` are HTTP/HTTPS proxy URLs consumed by the
host-side docker launchers (`goga/commands/build`, `goga/commands/pipeline`).
When the resolved proxy (config or CLI `--proxy`) is non-empty, the launcher
writes three variables into the container env-file:

| Variable     | Value                                            |
|--------------|--------------------------------------------------|
| `HTTP_PROXY` | the resolved proxy URL                           |
| `HTTPS_PROXY`| the resolved proxy URL                           |
| `NO_PROXY`   | `localhost,127.0.0.1` (fixed; CLI cannot override)|

`NO_PROXY` is mandatory whenever a proxy is set — without it,
`--add-host foo.local:127.0.0.1` would route `foo.local` through the corporate
proxy and break. CLI `--add-host` entries are NOT auto-added to `NO_PROXY`
(non-standard topologies are a later extension).

`build.hosts` and `pipeline.hosts` are host→IP mappings translated to
`docker run --add-host HOST:IP` flags. CLI `--add-host` flags are merged on top
of the config value; on key conflict, CLI wins.