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

# tools: optional — declared tools are installed together by `goga install`
# tools:
#   viewer: latest        # → no specifier (pip selects newest)
#   afm: 1.0.x            # → ~=1.0.0
#   ralphex: 1.x          # → ~=1.0
#   go: 1.0.1             # → ==1.0.1

# usages: optional — git dependencies whose cell-level .usages/ are synced by `goga usages sync` and status-checked by `goga usages status`
# usages:
#   libs:
#     click:
#       git: https://github.com/pallets/click.git
#       ref: 8.1.7         # optional — branch, tag, or commit; omit for the default branch
#       root: docs         # optional — subpath inside the repo to walk .usages from; omit for the clone root
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
| `tools` | mapping | No | goga-tool version declarations consumed by `goga install` in bulk mode. Keys are tool names (without the `goga-tool-` prefix); values are version-form strings. Values are stored verbatim — the four-form grammar (`1.0.x`, `1.x`, `1.0.1`, `latest`) is validated by `goga install`, not the loader. Defaults to `None` (absent); an empty mapping is `{}`. YAML-null values (`viewer:`) are rejected |
| `usages` | mapping | No | Git dependencies whose cell-level `.usages/` files are synced into `.goga/usages/<group>/<dep>/` by [`goga usages sync`](../cli/usages.md) and checked for drift against the remote by [`goga usages status`](../cli/usages.md). Two-level mapping: `<group>` → `<dep>` → `{ git, ref, root }`. Defaults to `None` (absent), which makes `goga usages sync` a no-op (exit 0); an empty mapping is `{}`. `<group>` and `<dep>` keys are validated as filesystem path segments — empty, `.` / `..`, or any name containing `/` or `\` raise `ValueError` |

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

| Field   | Type     | Required  | Description                                                                                                             |
|---------|----------|-----------|-------------------------------------------------------------------------------------------------------------------------|
| `agent` | `string` | Yes       | AI executor that runs the build inside the container. Resolved to `/home/goga/bin/<agent>-as-claude.sh` — no whitelist; any name whose wrapper file exists in the image works. Baseline wrappers: `claude`, `codex`, `cursor`, `opencode`. See [Agents](./agents.md) for the resolution mechanic, per-agent env variables, and how to add a custom agent. |
| `env`   | mapping  | No        | Environment variables passed to the agent. Keys and values must be strings. Defaults to `{}`                            |

### pipeline

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | `string` | Yes | AI agent that runs the pipeline stages inside the container. Same resolution mechanic and baseline set as `build.task_executor.agent` — see [Agents](./agents.md). |
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

## Pre-built Docker images

goga provides prebuilt language images for build execution:

| Language | Images |
|----------|--------|
| Python | `qarium/goga-python-3.10:1.1` through `qarium/goga-python-3.14:1.1` |
| Go | `qarium/goga-golang-1.23:1.1` through `qarium/goga-golang-1.26:1.1` |
| JavaScript | `qarium/goga-node-22:1.1`, `qarium/goga-node-24:1.1` |
| Kotlin | `qarium/goga-kotlin-2.0:1.1` through `qarium/goga-kotlin-2.3:1.1` |
| Swift | `qarium/goga-swift-6.0:1.1` through `qarium/goga-swift-6.2:1.1` |

## Validation errors

The config loader raises specific exceptions for invalid configuration:

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | `.goga/config.yml` does not exist or is empty |
| `KeyError` | Missing required field (`language`, or `build.task_executor` when `build` is present) |
| `ValueError` | Invalid field value (wrong type, empty string, non-mapping where mapping expected), or the deprecated `build.image` field is present |

## Implementation details

Configuration is loaded as immutable frozen dataclasses (`frozen=True`, `kw_only=True`). Once loaded, the `ProjectConfig` object cannot be modified. This ensures consistent behavior across the build pipeline.

## Home configuration

In addition to the per-project `.goga/config.yml`, goga reads an optional
machine-wide configuration from `~/.goga/config.yml`. This file is entirely
optional — when it is absent (the normal state), an empty home config is used
and nothing changes. A malformed file surfaces as a clean error and exits
non-zero; a missing file is never an error.

```yaml
# ~/.goga/config.yml — optional, machine-wide
env:
  HTTP_PROXY: http://corp:3128     # applied as the lowest-priority env base layer
docker:
  run: ["--network=host"]          # appended to every `docker run` (build + pipeline)
  build: ["--squash"]              # appended to image builds only (`goga build`/`--update`)
```

| Field | Type | Description |
|-------|------|-------------|
| `env` | mapping | Environment variables applied as the **lowest-priority base layer** in the container env-file. Project config and CLI `-e`/`extra_env` override these on key conflict. Applied to `docker run` containers (`goga build` and `goga pipeline <name>`); not applied to `docker build` |
| `docker.run` | list of strings | Tokens appended to every `docker run` invocation in both `goga build` and `goga pipeline` |
| `docker.build` | list of strings | Tokens appended to image builds only — forwarded by both `goga build` and `goga pipeline` (`docker_build_if_not_exist` / `docker_update`, build branch only; ignored on image pull) |

The env layering formula is `{**home.env, **project_env, **cli_env}` — `home.env`
is the base, project config wins over it, and CLI extra env wins last. Unknown
keys are ignored.
