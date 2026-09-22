# Project Configuration — goga/config

## Overview

The `goga.config` package provides unified access to project configuration through the `.goga/config.yml` file.

## Facade

Import all types directly from `goga.config`:

```python
from goga.config import (
    ProjectConfig,
    BuildConfig,
    ReviewConfig,
    AdditionalReviewConfig,
    PipelineConfig,
    CodemanifestConfig,
    DepConfig,
    LintConfig,
    TopicsConfig,
    load_project_config,
)
```

## Loading Configuration

### load_project_config() -> ProjectConfig

Parses `.goga/config.yml` from the current working directory (CWD).

**Usage**:

```python
from goga.config import load_project_config

config = load_project_config()
```

**Behavior**:
- `.goga/config.yml` is mandatory — raises `FileNotFoundError` if missing or empty
- Root YAML element must be a mapping — raises `ValueError` otherwise
- Required top-level field: `language`. All other top-level fields (`image`, `pipeline`, `build`, `commands`, `codemanifest`, `dockerfile`) are optional
- Optional sections `pipeline` and `build` may be absent — `config.pipeline` and `config.build` are then `None`. Consumers that need them (the `pipeline` and `build` commands) guard the `None` case and raise `ClickException` before any field access
- When `pipeline` is present: it must be a mapping; `pipeline.agent` is OPTIONAL — absent/null/empty/whitespace resolves to `None`, and `goga pipeline` raises `ClickException` when it needs an agent
- When `build` is present: it must be a mapping. The build section is
  two-part: the `build` root carries the tasks-pass settings (agent, env,
  max_iterations, session_timeout, idle_timeout, wait, prompts_dir,
  agents_dir, proxy, hosts); the optional `build.review` key carries the
  review-pass settings (skip, agent, env, roles, base_ref, strategy,
  finalize, additional, and the session knobs). `build.agent` is OPTIONAL —
  absent/null/empty/whitespace resolves to `None`, and `goga build` raises
  `ClickException` when it needs an agent. The loader extracts known fields
  only — unknown keys, including the retired `worktree`, `skip_finalize`,
  `codex_review` and the retired block names `task_executor` /
  `review_executor`, are silently ignored (not extracted, not stored).
  Values are exposed verbatim with no default merging — inheritance (review
  from root, additional.agent from review.agent) belongs to the consuming
  command
- Optional `build.review` follows structural-only validation: field types, a
  list-of-strings check for `roles`, a strings-mapping check for `env`, and
  scalar type checks for `base_ref` (string), `strategy`/`finalize`
  (strings), and `additional.patience`/`additional.max_iterations`
  (integers); an empty `roles` list and an empty `env` mapping pass through
  verbatim — the empty-to-full-set (roles), env-requires-agent (env), and
  strategy whitelist semantics belong to the consuming command
- A present-but-non-mapping `pipeline` or `build` value (e.g. `pipeline: 5`, `build: true`) raises `ValueError`, not `AttributeError`. An explicit YAML-null section (`pipeline:` with no value) is treated as absent — `None`, no error
- Raises `yaml.YAMLError` on invalid YAML syntax
- Optional `topics` follows structural-only validation: `topics.base_ref` and
  `topics.publish_commit` are strings when present — absent/YAML-null/empty/
  whitespace resolves to `None`; a present-but-non-mapping `topics` raises
  `ValueError`. Rev resolvability, template grammar, and the default template
  belong to the consuming command

`load_project_config` performs the authored load only — no hooks fire
inside it. A host-side command that offers the config amendment
checkpoint hands the loaded configuration to the zone entry
(`goga.config.hooks`) and consumes the effective configuration the
delivery returns.

**Error handling**:

```python
from goga.config import load_project_config

try:
    config = load_project_config()
except FileNotFoundError:
    # .goga/config.yml not found or empty
except KeyError as e:
    # Missing required field — `language`
    print(e)
except ValueError as e:
    # Invalid field value
    print(e)
except yaml.YAMLError as e:
    # YAML syntax error
    print(e)
```

## .goga/config.yml Schema

Minimal valid configuration (only `language` is required at the loader level):

```yaml
language: python
```

Minimal configuration for `goga pipeline` (the pipeline command requires the
`pipeline` section — absent section → ClickException):

```yaml
language: python
image: qarium/goga-python-3.12:latest
pipeline:
  agent: claude
```

Minimal configuration for `goga build` (the build command requires the `build`
section — absent section → ClickException):

```yaml
language: python
image: qarium/goga-python-3.12:latest
build:
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
build:                       # two-part: the root is the tasks-pass settings
  agent: claude              # str | absent — tasks-pass executor agent
  env:                       # mapping | absent — tasks-pass env layer
    ANTHROPIC_API_KEY: sk-xxx
    MODEL: claude-sonnet-4-6
  max_iterations: 10         # int | absent — maximum task iterations
  session_timeout: "30m"     # str | absent — session timeout (Go duration)
  idle_timeout: "1h"         # str | absent — idle timeout (Go duration)
  wait: "5m"                 # str | absent — rate-limit retry wait
  prompts_dir: /custom/prompts
  agents_dir: /custom/agents
  proxy: http://corp:3128    # HTTP/HTTPS proxy URL
  hosts:                     # docker run --add-host entries
    foo.local: 127.0.0.1
  review:                    # optional review-pass settings
    skip: false              # bool | absent — tri-state source
    agent: codex             # str | absent — review executor (inherits build.agent)
    env:                     # mapping | absent — review env layer (never inherits the root env)
      ANTHROPIC_MODEL: reviewer-model
    roles:                   # list[str] | absent — reviewer composition
      - quality
      - testing
    base_ref: origin/1.2.x   # str | absent — review diff base (branch or hash)
    strategy: medium         # full | medium | short — review strategy (default medium)
    finalize: |              # str | absent — user-authored final review prompt
      Final review instructions here.
    session_timeout: "40m"   # review session knobs inherit the root when absent
    additional:              # optional external-review block
      agent: codex           # str | absent — external review agent (inherits review.agent)
      patience: 3            # int | absent — stop external review after N unchanged rounds
      max_iterations: 15     # int | absent — external review iteration cap (0 = ralphex auto)
codemanifest:
  usages:
    usage_name: path/to/file.md
  annotations: |
    Use the `usage_name` practice.
tools:
  viewer: latest        # → no specifier (pip selects newest)
  afm: 1.0.x            # → ~=1.0.0 (minor x-range, >=1.0.0,<1.1.0)
  ralphex: 1.x          # → ~=1.0   (major x-range, >=1.0.0,<2.0.0)
  go: 1.0.1             # → ==1.0.1 (concrete)
usages:                       # usages-sync section (optional)
  libs:                       # <group> — top-level dir under .goga/usages/
    click:                    # <dep> — subdir under the group
      git: https://github.com/pallets/click.git
      ref: main               # optional: branch/tag/commit (absent → default branch)
lint:                          # optional linter section
  ignore:                      # list of exact relative paths to exclude
    - .venv/                   # glob (**, *, ?) is NOT supported
    - build/dist
topics:                          # optional fast-creation section
  base_ref: origin/main          # str | absent — base of published topic branches
  publish_commit: "goga: create topic {slug}"  # str | absent — commit message template
```

#### Build section migration note

The build section is two-part. The retired keys `worktree`, `skip_finalize`,
`codex_review` and the retired block names `task_executor` / `review_executor`
are NOT extracted — the loader extracts known fields only and silently ignores
unknown keys. A config that still carries the old block names effectively loses
its build settings: `build.task_executor.agent` no longer populates
`build.agent`, so the section behaves as if unset and `goga build` fails with
`build.agent is required in .goga/config.yml to run 'goga build'`. Migrate by
moving `task_executor.agent`/`task_executor.env` to the `build` root and the
`review_executor` fields under `build.review`, as in the example above.

### Required Fields

| Field                       | Type    | Description                                                         |
|-----------------------------|---------|---------------------------------------------------------------------|
| `language`                  | str     | Project programming language                                        |

### Conditionally required fields

These fields are optional at the loader level but required by their consuming
command. When the consuming command is invoked on a config that lacks the
section, the command raises `ClickException` before any field access.

| Field                       | Required by           | Notes                                                                          |
|-----------------------------|-----------------------|--------------------------------------------------------------------------------|
| `pipeline`                  | `goga pipeline`       | Must be a mapping when present.                                                |
| `pipeline.agent`            | `goga pipeline`       | Optional at the loader level (absent/empty → `None`); required to actually run `goga pipeline`, which raises `ClickException` otherwise. Resolved into the in-container `*-as-claude.sh` wrapper path. |
| `build`                     | `goga build`          | Must be a mapping when present. Two-part: the root tasks-pass fields plus the optional `build.review` sub-mapping. |
| `build.agent`               | `goga build`          | Optional at the loader level (absent/empty → `None`); required to actually run `goga build`, which raises `ClickException` otherwise. Resolved into the in-container `*-as-claude.sh` wrapper path. |

#### Agent name semantics

Both `pipeline.agent` and `build.agent` are agent names as
declared in the goga Docker image — any value matching the
`/home/goga/bin/<agent>-as-claude.sh` wrapper convention (e.g. `claude`,
`codex`, `opencode`). The config layer does no validation: resolution and
absence-of-wrapper errors are surfaced by the downstream tools (ralphex,
afm) that consume these fields.

### Optional Fields

| Field                       | Type    | Default                | Description                                             |
|-----------------------------|---------|------------------------|---------------------------------------------------------|
| `image`                     | str     | None                   | Top-level Docker image shared by build and pipeline     |
| `dockerfile`                | str     | None                   | Top-level path to a project Dockerfile                  |
| `commands`                  | mapping | `{}`                   | Prompt customization hooks (reserved)                   |
| `pipeline`                  | mapping | None                   | Pipeline configuration block (conditionally required by `goga pipeline`)  |
| `pipeline.env`              | mapping | `{}`                   | Environment variables for pipeline runs (`{str: str}`)  |
| `pipeline.proxy`            | str     | None                   | HTTP/HTTPS proxy URL for the pipeline container         |
| `pipeline.hosts`            | mapping | `{}`                   | Host→IP mapping for `docker run --add-host` (pipeline)  |
| `build`                     | mapping | None                   | Build configuration block, two-part (conditionally required by `goga build`)  |
| `build.agent`               | str     | None                   | Tasks-pass executor agent name (resolved by the consumer) |
| `build.env`                 | mapping | `{}`                   | Tasks-pass environment variables for builds (`{str: str}`); never inherited by the review pass |
| `build.proxy`               | str     | None                   | HTTP/HTTPS proxy URL for the build container            |
| `build.hosts`               | mapping | `{}`                   | Host→IP mapping for `docker run --add-host` (build)     |
| `build.session_timeout`     | str     | None                   | Session timeout (Go duration format); the tasks-pass knob |
| `build.idle_timeout`        | str     | None                   | Idle timeout (Go duration format); the tasks-pass knob  |
| `build.wait`                | str     | None                   | Rate-limit retry wait (Go duration format); the tasks-pass knob |
| `build.max_iterations`      | int     | None                   | Maximum task iteration count (root-only, tasks pass)    |
| `build.prompts_dir`         | str     | None                   | Custom prompt directory path                            |
| `build.agents_dir`          | str     | None                   | Custom agent directory path                             |
| `build.review`              | mapping | None  | Review-pass settings block (structural validation only) |
| `build.review.skip`         | bool    | None  | Tri-state source for skipping the review pass |
| `build.review.agent`        | str     | None  | Review executor name (inherits `build.agent` when unset; resolved by the consumer) |
| `build.review.env`          | mapping | `{}`  | Review-pass env layer ({str: str}); empty when absent/YAML-null/`{}`; never inherits the root env; requires `agent` when non-empty (enforced by the consumer) |
| `build.review.roles`        | list    | None  | Reviewer composition; empty list passes verbatim (full default set is consumer semantics) |
| `build.review.base_ref`     | str     | None  | Review diff base — branch name or commit hash; overrides ralphex's default-branch detection for review diffs. Verbatim, no validation at the config layer |
| `build.review.strategy`     | str     | None  | Review strategy source — full, medium, or short (structural typing only; the whitelist and the default medium belong to the consumer) |
| `build.review.finalize`     | str     | None  | User-authored final review prompt, stored verbatim; None leaves the finalize step at the ralphex default (off) |
| `build.review.session_timeout` | str  | None  | Review session timeout; None inherits the root value |
| `build.review.idle_timeout`   | str  | None  | Review idle timeout; None inherits the root value |
| `build.review.wait`           | str  | None  | Review rate-limit wait; None inherits the root value |
| `build.review.additional`   | mapping | None  | External-review block (structural validation only) |
| `build.review.additional.agent` | str | None | External review agent name (inherits `build.review.agent` when unset) |
| `build.review.additional.patience` | int | None | Stop the external review after N consecutive unchanged rounds; 0 = disabled |
| `build.review.additional.max_iterations` | int | None | External review iteration cap; 0 = ralphex auto |
| `codemanifest`              | mapping | None                   | CODEMANIFEST usage and annotation config                |
| `codemanifest.usages`       | mapping | `{}`                   | Usage name-to-path mapping (`{str: str}`)               |
| `codemanifest.annotations`  | str     | None                   | Freeform annotations for the AI agent                   |
| `tools`                     | mapping | None                   | goga-tool version declarations (stored verbatim, no semantic validation) |
| `usages`                    | mapping | None                   | usages-sync section: `{group: {dep: {git, ref}}}` (None when absent) |
| `usages.<group>.<dep>.git`  | str     | —                      | git URL (required, non-empty) |
| `usages.<group>.<dep>.ref`  | str     | None                   | optional git ref (branch/tag/commit; absent → default branch) |
| `lint`        | mapping | None | Linter section (optional); when absent, config.lint is None |
| `lint.ignore` | list    | `[]` | List of exact relative paths excluded from AST traversal by `goga lint`. Glob is not supported |
| `topics`                    | mapping | None  | Fast-creation section (structural validation only) |
| `topics.base_ref`           | str     | None  | Base revision of published topic branches, verbatim |
| `topics.publish_commit`     | str     | None  | Commit message template; the {slug} placeholder is optional, verbatim |

## Accessing Configuration Data

All objects are immutable frozen dataclasses (`frozen=True`). Fields expose read-only access.

```python
config = load_project_config()

# Top-level accessors
config.language  # str — project language
config.image  # str | None — top-level Docker image (shared by build and pipeline)
config.build  # BuildConfig | None — None when the `build` section is absent
config.pipeline  # PipelineConfig | None — None when the `pipeline` section is absent
config.commands  # dict — custom command hooks
config.dockerfile  # str | None — path to a project Dockerfile
config.usages  # dict[str, dict[str, DepConfig]] | None — usages-sync declarations (None when absent)

# Section accessors require a None-guard in the consuming command. The loader
# does not enforce presence of `pipeline` or `build`; the consuming command is
# responsible for raising a user-facing error (ClickException) before any field
# access:

if config.pipeline is None:
    raise ClickException("pipeline section is required in .goga/config.yml ...")
# now safe to read config.pipeline.agent / env / proxy / hosts

if config.build is None:
    raise ClickException("build section is required in .goga/config.yml ...")
# now safe to read config.build.agent / env / review / proxy / hosts / ...

# PipelineConfig fields (after the None-guard)
config.pipeline.agent  # str | None — afm client.command inside the container; None when not configured
config.pipeline.env  # dict — {str: str}
config.pipeline.proxy  # str | None — HTTP/HTTPS proxy URL for the pipeline container
config.pipeline.hosts  # dict[str, str] — docker run --add-host entries

# BuildConfig fields (after the None-guard) — the root is the tasks-pass part
config.build.agent  # str | None — tasks-pass executor agent, None when not configured
config.build.env  # dict[str, str] — tasks-pass env layer, empty when absent
config.build.max_iterations  # int | None — tasks-pass iteration cap
config.build.session_timeout  # str | None — tasks-pass session knob
config.build.idle_timeout  # str | None — tasks-pass session knob
config.build.wait  # str | None — tasks-pass session knob
config.build.prompts_dir  # str | None — custom ralphex prompt directory
config.build.agents_dir  # str | None — custom ralphex agent directory
config.build.proxy  # str | None — HTTP/HTTPS proxy URL for the build container
config.build.hosts  # dict[str, str] — docker run --add-host entries

# ReviewConfig fields — None when the build.review key is absent
config.build.review  # ReviewConfig | None
config.build.review.skip  # bool | None — tri-state skip source
config.build.review.agent  # str | None — review executor name (inherits the root agent when unset)
config.build.review.env  # dict[str, str] — review env layer, empty when absent; never inherits the root env
config.build.review.roles  # list[str] | None — verbatim; [] means the full default set to the consumer
config.build.review.base_ref  # str | None — review diff base, verbatim
config.build.review.strategy  # str | None — full | medium | short source
config.build.review.finalize  # str | None — final review prompt, verbatim
config.build.review.session_timeout  # str | None — inherits the root when None
config.build.review.idle_timeout  # str | None — inherits the root when None
config.build.review.wait  # str | None — inherits the root when None
config.build.review.additional  # AdditionalReviewConfig | None

# AdditionalReviewConfig fields — None when the additional block is absent
config.build.review.additional.agent  # str | None — external review agent (inherits review.agent)
config.build.review.additional.patience  # int | None — external-review stop threshold
config.build.review.additional.max_iterations  # int | None — external review iteration cap

# CodemanifestConfig fields — None when the `codemanifest` section is absent
config.codemanifest  # CodemanifestConfig | None
config.codemanifest.usages  # dict — {str: str}
config.codemanifest.annotations  # str | None

# TopicsConfig fields — None when the `topics` section is absent
config.topics  # TopicsConfig | None
config.topics.base_ref  # str | None — base revision, verbatim
config.topics.publish_commit  # str | None — commit message template, verbatim
```

```yaml
topics:
  base_ref: origin/main
  publish_commit: "goga: create topic {slug}"
```

The default template and the `{slug}` substitution belong to the consuming
command (the create command).

### `tools` accessor — no-validation contract

`config.tools` exposes the raw mapping from `.goga/config.yml`. The loader
performs only structural validation (keys and values must be strings); semantic
validation of the four-form version grammar is owned by the consumer that
interprets these declarations.

```python
config = load_project_config()

# config.tools is dict[str, str] | None
# - None when the `tools` section is absent or YAML-null
# - {} when the section is present but empty
# - {"viewer": "latest", "afm": "1.0.x", ...} when populated

if config.tools is None:
    # tools section absent — consumer treats as "nothing to install"
    ...
else:
    for name, form in config.tools.items():
        # `name` is the tool identifier (without goga-tool- prefix)
        # `form` is a string in the four-form grammar: 1.0.x, 1.x, 1.0.1, latest
        # Malformed values (operator-prefixed `==1.0`, malformed `1.x.0`) pass
        # through load_project_config verbatim — the consumer surfaces them as ValueError
        # at its own resolution step
        ...
```

**Do NOT validate `tools` values at the config layer.** The loader is a leaf —
it must not own version-grammar concerns. Semantic validation belongs to the
consumer that interprets these declarations; the loader only enforces that keys
and values are strings.

**YAML-null values are rejected by the loader as a structural type error:**

```yaml
tools:
  viewer:              # YAML null — loader raises ValueError
```

To declare "no specifier" for a tool, write `latest` explicitly:

```yaml
tools:
  viewer: latest       # valid — resolves to "no specifier"
```

### `usages` accessor

`config.usages` exposes the optional usages-sync declarations from the
`usages` section of `.goga/config.yml`. Structure: `{group: {dep: DepConfig}}`,
or `None` when the section is absent (an empty section yields `{}`).

```python
config.usages  # dict[str, dict[str, DepConfig]] | None
config.usages["libs"]["click"].git  # str — git URL (required, non-empty)
config.usages["libs"]["click"].ref  # str | None — optional git ref

# When the `usages` section is absent, config.usages is None — `goga usages sync`
# is a no-op (exit 0).
```

```yaml
usages:
  libs:
    click:
      git: https://github.com/pallets/click.git
      ref: main
```

CLI dot-notation renders a single dep's `DepConfig` via `beautiful_yaml`:

```bash
goga config usages.libs.click   # → DepConfig(git=..., ref=...)
```

### `lint` accessor

`config.lint` exposes the optional linter section.

```python
config.lint  # LintConfig | None — None when the `lint` section is absent
config.lint.ignore  # list[str] — exact relative paths; empty when ignore is absent/empty
```

```yaml
lint:
  ignore:
    - .venv/
    - build/dist
```

- `ignore` entries are exact paths relative to the `goga lint` invocation cwd
  (after `os.chdir(path)` — relative to the traversal root). Matching is strict:
  trailing slash is insignificant (`.venv/` == `.venv`); glob patterns
  (`**`, `*`, `?`) are NOT supported and are not applied.
- The loader performs only structural validation (list of strings); path
  semantics (glob/normalization/existence) are the consumer's responsibility.
- Absence of the `lint` section ⇒ `config.lint is None` ⇒ no directories are
  excluded from validation.

## Immutability

All config objects are frozen — mutation attempts raise `FrozenInstanceError`:

```python
config = load_project_config()
config.language = "go"  # raises dataclasses.FrozenInstanceError
```

To derive a modified copy, use `dataclasses.replace`:

```python
from dataclasses import replace
from goga.config import ProjectConfig

new_config = replace(config, language="go")
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