# Project Configuration

goga reads project configuration from `.goga/config.yml` in the project root. This file is created by `goga init` and can be edited manually.

## File location

```
.goga/config.yml
```

The config loader looks for this file relative to the current working directory.

For the machine-wide `~/.goga/config.yml`, see [Home Configuration](home.md).

## Example configuration

```yaml
language: python
image: qarium/goga-python-3.14:1.2
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
```

## Fields reference

### Top-level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | `string` | Yes | Project language. One of: `python`, `golang`, `kotlin`, `swift`, `javascript` |
| `image` | `string` | No | Docker image used by `goga build` and `goga pipeline` (e.g. `qarium/goga-python-3.14:1.2`). Consumers raise an error when it is unset. |
| `dockerfile` | `string` | No | Path to a project Dockerfile. When set, `goga build --update` and `goga pipeline --update` build the image locally from this Dockerfile (fatal on build failure). When unset (default), `--update` pulls `image` from the registry instead (non-fatal warning on pull failure) |
| `build` | mapping | No | Build pipeline settings. Optional at the loader level; `goga build` raises a `ClickException` when the section is absent |
| `pipeline` | mapping | No | Pipeline (afm) execution settings. Optional at the loader level; `goga pipeline` raises a `ClickException` when the section is absent |
| `commands` | mapping | No | Reserved for future prompt customization. Defaults to `{}` |
| `codemanifest` | mapping | No | Global codemanifest configuration |
| `tools` | mapping | No | goga-tool version declarations consumed by `goga install` in bulk mode. Keys are tool names (without the `goga-tool-` prefix); values are version-form strings. Values are stored verbatim — the four-form grammar (`1.0.x`, `1.x`, `1.0.1`, `latest`) is validated by `goga install`, not the loader. Defaults to `None` (absent); an empty mapping is `{}`. YAML-null values (`viewer:`) are rejected |
| `usages` | mapping | No | Git dependencies whose cell-level `.usages/` files are synced into `.goga/usages/<group>/<dep>/` by [`goga usages sync`](../cli/usages.md) and checked for drift against the remote by [`goga usages status`](../cli/usages.md). Two-level mapping: `<group>` → `<dep>` → `{ git, ref, root }`. Defaults to `None` (absent), which makes `goga usages sync` a no-op (exit 0); an empty mapping is `{}`. `<group>` and `<dep>` keys are validated as filesystem path segments — empty, `.` / `..`, or any name containing `/` or `\` raise `ValueError` |
| `lint` | mapping | No | Optional linter section consumed by [`goga lint`](../cli/lint.md). Currently holds `ignore`, a list of directory relative paths to prune from lint traversal. Defaults to `None` (absent); an empty mapping is equivalent to no ignore list. Structural type errors (non-mapping `lint`, non-list `lint.ignore`, or a non-string element) raise `ValueError` |

### build

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_executor` | mapping | Yes | AI agent configuration |
| `worktree` | `bool` | No | Use isolated git worktree for builds |
| `skip_finalize` | `bool` | No | Skip the ralph-loop finalization step |
| `session_timeout` | `string` | No | Session timeout in Go duration format (e.g. `30m`, `1h`) |
| `idle_timeout` | `string` | No | Idle timeout in Go duration format |
| `wait` | `string` | No | Wait time on rate limit in Go duration format |
| `max_iterations` | `int` | No | Maximum task iterations |
| `review_patience` | `int` | No | Stop review after N unchanged rounds |
| `prompts_dir` | `string` | No | Path to custom ralph-loop prompts |
| `agents_dir` | `string` | No | Path to custom ralph-loop agents |
| `codex_review` | `bool` | No | Enable external codex review |
| `proxy` | `string` | No | HTTP/HTTPS proxy URL for the build container. When set, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` are written to the container env-file. Overridden by the `--proxy` CLI option |
| `hosts` | mapping | No | Host→IP mapping for `docker run --add-host`. Defaults to `{}`. Augmented by the repeatable `--add-host` CLI option (CLI wins on key conflict) |
| `review_executor` | mapping | No | Review-phase configuration. See [build.review_executor](#buildreview_executor) |

> The deprecated `build.image` field is rejected with a `ValueError`. Set the top-level `image` field instead.

### build.task_executor

| Field   | Type     | Required  | Description                                                                                                             |
|---------|----------|-----------|-------------------------------------------------------------------------------------------------------------------------|
| `agent` | `string` | No        | AI executor that runs the build inside the container. Optional at the loader level — absent/YAML-null/empty/whitespace resolves to `None`; `goga build` raises a `ClickException` when it is `None` (the build needs an agent to resolve the in-container wrapper). Resolved to `/home/goga/bin/<agent>-as-claude.sh` — no whitelist; any name whose wrapper file exists in the image works. Baseline wrappers: `claude`, `codex`, `cursor`, `opencode`, `qwen`. See [Agents](./agents.md) for the resolution mechanic, per-agent env variables, and how to add a custom agent. |
| `env`   | mapping  | No        | Environment variables passed to the agent. Keys and values must be strings. Defaults to `{}`                            |

### build.review_executor

Optional section controlling the review phase of `goga build`. When absent, the full cycle (tasks + review) runs in a single pass with the task executor's wrapper.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skip` | `bool` | No | Skip the review phase entirely — the run executes tasks only (ralph-loop `--tasks-only`). Absent/YAML-null means "not set" (the CLI flag decides); must be a real bool — a YAML `1` is rejected |
| `agent` | `string` | No | Review executor agent name (same resolution mechanic as `build.task_executor.agent`; its wrapper must exist in the image). When it differs from `task_executor.agent`, **or when a non-empty `env` is declared alongside it**, the build runs two passes: tasks with the task wrapper, then the review pass with the review wrapper. Combining either two-pass form with an active worktree (`--worktree` or `build.worktree: true`) is rejected with exit 1 on the host |
| `roles` | list of `string` | No | Reviewer composition for the review prompts: keeps only the `{{agent:X}}` lines of the selected roles and adapts the counters of the accompanying text. Whitelist: `quality`, `implementation`, `testing`, `simplification`, `documentation`. Absent or `[]` means the full default set (prompts stay byte-identical to the vendored defaults) |
| `env` | mapping of `string` | No | Review-pass environment layer (`{str: str}`). Keys overlay same-named container variables for the review-pass subprocess only — the tasks pass and the container env-file are unaffected, and the values never reach logs or dry-run output. Absent/YAML-null/`{}` all resolve to `{}` (unlike `build.task_executor.env`, where YAML-null is an error). A non-empty `env` induces a two-pass run like a differing agent does, and requires `agent` — a non-empty `env` without `agent` fails in-container validation when the review phase runs; a skipped run ignores the layer entirely |

Precedence: the `--skip-review`/`--no-skip-review` CLI pair overrides `skip`; an explicit `--no-skip-review` forces the full cycle even when the config sets `skip: true`. Role names, the env-requires-agent rule, and the review wrapper are validated in-container before any pass runs — but only when the review phase will actually run (a skipped run never validates them).

### pipeline

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | `string` | No | AI agent that runs the pipeline stages inside the container. Optional at the loader level — absent/YAML-null/empty/whitespace resolves to `None`. When `None`, the agent may be supplied by a per-stage workflow override (see [Workflows](../pipelines/workflows.md)) or afm's own default, so `goga pipeline` does not require it. Same resolution mechanic and baseline set as `build.task_executor.agent` — see [Agents](./agents.md). |
| `env` | mapping | No | Environment variables passed into the pipeline container. Keys and values must be strings. Defaults to `{}` |
| `proxy` | `string` | No | HTTP/HTTPS proxy URL for the pipeline container. When set, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` are written to the container env-file. Overridden by the `--proxy` CLI option |
| `hosts` | mapping | No | Host→IP mapping for `docker run --add-host`. Defaults to `{}`. Augmented by the repeatable `--add-host` CLI option (CLI wins on key conflict) |

### codemanifest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `usages` | mapping | No | Named practices available in CODEMANIFEST files. Format: `{name: path/to/file.md}`. Defaults to `{}` |
| `annotations` | `string` | No | Free-text instructions for AI agents. Defaults to `None` |

### usages

Git dependencies whose cell-level `.usages/` files are synced into `.goga/usages/<group>/<dep>/` by [`goga usages sync`](../cli/usages.md) and checked for drift against the remote by [`goga usages status`](../cli/usages.md).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `usages.<group>` | mapping | Yes when `usages` present | Group bucket. The key becomes a top-level subdirectory of `.goga/usages/`. Validated as a path segment (no empty / `.` / `..` / `/` / `\`). |
| `usages.<group>.<dep>` | mapping | Yes when `<group>` present | Dependency entry. The key becomes a subdirectory under the group. Same path-segment validation. |
| `usages.<group>.<dep>.git` | `string` | Yes | Git URL of the source repository. Must be non-empty. |
| `usages.<group>.<dep>.ref` | `string` | No | Git ref — branch, tag, or commit. `None` (omitted) clones the default branch. |
| `usages.<group>.<dep>.root` | `string` | No | Subpath inside the clone to discover `.usages` folders from. Absent (or an empty string) → clone root. Must be relative; no `..` or absolute paths (leading `/` or UNC `//host/share`). |

When `usages` is absent, `config.usages` is `None` and `goga usages sync` exits `0` without invoking git. A present-but-non-mapping value raises `ValueError`.

### lint

Optional section consumed by [`goga lint`](../cli/lint.md) to prune directories from validation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lint.ignore` | list of strings | No | Directory relative paths to skip during lint traversal, stored verbatim. A directory matches when its exact normalized relative path equals an entry; glob patterns are not interpreted and a trailing separator is insignificant. Defaults to `[]` when `lint` is present but `ignore` is absent |

When `lint` is absent, `config.lint` is `None` and `goga lint` lints every directory. A present-but-non-mapping `lint`, a non-list `lint.ignore`, or a non-string element raises `ValueError`. The `lint` command derives `ignore` **tolerantly** — any loader error falls back to no filtering rather than failing the lint run.

## Pre-built Docker images

goga provides prebuilt language images for build execution:

| Language | Images |
|----------|--------|
| Python | `qarium/goga-python-3.10:1.2` through `qarium/goga-python-3.14:1.2` |
| Go | `qarium/goga-golang-1.23:1.2` through `qarium/goga-golang-1.26:1.2` |
| JavaScript | `qarium/goga-node-22:1.2`, `qarium/goga-node-24:1.2` |
| Kotlin | `qarium/goga-kotlin-2.0:1.2` through `qarium/goga-kotlin-2.3:1.2` |
| Swift | `qarium/goga-swift-6.0:1.2` through `qarium/goga-swift-6.2:1.2` |

## Validation errors

The config loader raises specific exceptions for invalid configuration:

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | `.goga/config.yml` does not exist or is empty |
| `KeyError` | Missing required field (`language`, or `build.task_executor` when `build` is present) |
| `ValueError` | Invalid field value (wrong type, empty string, non-mapping where mapping expected), or the deprecated `build.image` field is present. `build.review_executor` adds: non-mapping section (`build.review_executor must be a mapping`), non-bool `skip` (a YAML `1` is rejected), non-string `agent`, `roles` that is not a list of strings, a non-mapping `env` (`build.review_executor.env must be a mapping in .goga/config.yml`), or `env` with non-string keys/values (`build.review_executor.env must have string keys and values`) |

## Implementation details

Configuration is loaded as immutable frozen dataclasses (`frozen=True`, `kw_only=True`). Once loaded, the `ProjectConfig` object cannot be modified. This ensures consistent behavior across the build pipeline.
