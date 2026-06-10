# Project Configuration — goga/config

## Overview

The `goga.config` package provides unified access to project configuration through the `.goga/config.yml` file.

## Facade

Import all types directly from `goga.config`:

```python
from goga.config import Config, BuildConfig, TaskExecutor, CodemanifestConfig, load_config
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
- Required sections: `language`, `build`, `build.task_executor`, `build.task_executor.agent`
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
```

## .goga/config.yml Schema

Minimal valid configuration:

```yaml
language: python
build:
  task_executor:
    agent: claude
```

Full configuration with all options:

```yaml
language: python
commands:
  test: pytest
build:
  task_executor:
    agent: claude
    env:
      ANTHROPIC_API_KEY: sk-xxx
      MODEL: claude-sonnet-4-6
  image: qarium/goga:latest
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
| `build.task_executor`       | mapping | AI agent configuration block                                        |
| `build.task_executor.agent` | str     | AI executor identifier: `claude`, `codex`, `copilot`, `gemini`, `custom:/path` |

### Optional Fields

| Field                      | Type    | Default                | Description                                  |
|----------------------------|---------|------------------------|----------------------------------------------|
| `commands`                 | mapping | `{}`                   | Prompt customization hooks (reserved)        |
| `build.task_executor.env`  | mapping | `{}`                   | Environment variables (`{str: str}`)         |
| `build.image`              | str     | None                   | Docker image for build execution             |
| `build.worktree`           | bool    | None                   | Run in an isolated git worktree              |
| `build.skip_finalize`      | bool    | None                   | Skip the finalization step                   |
| `build.session_timeout`    | str     | None                   | Session timeout (Go duration format)         |
| `build.idle_timeout`       | str     | None                   | Idle timeout (Go duration format)            |
| `build.wait`               | str     | None                   | Rate-limit retry wait (Go duration format)   |
| `build.max_iterations`     | int     | None                   | Maximum task iteration count                 |
| `build.review_patience`    | int     | None                   | Review convergence threshold                 |
| `build.prompts_dir`        | str     | None                   | Custom prompt directory path                 |
| `build.agents_dir`         | str     | None                   | Custom agent directory path                  |
| `build.codex_review`       | bool    | None                   | Enable external codex review                 |
| `codemanifest`             | mapping | None                   | CODEMANIFEST usage and annotation config     |
| `codemanifest.usages`      | mapping | `{}`                   | Usage name-to-path mapping (`{str: str}`)    |
| `codemanifest.annotations` | str     | None                   | Freeform annotations for the AI agent        |

## Accessing Configuration Data

All objects are immutable frozen dataclasses (`frozen=True`). Fields expose read-only access.

```python
config = load_config()

# Top-level accessors
config.lang           # str — project language
config.build          # BuildConfig
config.commands       # dict — custom command hooks

# BuildConfig fields
config.build.task_executor   # TaskExecutor
config.build.image           # str | None — build Docker image
config.build.worktree        # bool | None

# TaskExecutor fields
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
