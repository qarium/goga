# Home Configuration

In addition to the per-project `.goga/config.yml` (see [Project Configuration](project.md)), goga reads an optional
machine-wide configuration from `~/.goga/config.yml`. This file is entirely
optional — when it is absent (the normal state), an empty home config is used
and nothing changes. A malformed file surfaces as a clean error and exits
non-zero; a missing file is never an error.

```yaml
# ~/.goga/config.yml — optional, machine-wide
env:
  HTTP_PROXY: http://corp:3128     # applied as the lowest-priority env base layer
docker:
  run:                            # appended to every `docker run` (build + pipeline)
    - "--network=host"
    - "-v /Users/me/.ssh:/home/goga/.ssh:ro"   # shell-like: flag + value split into two tokens
  build: ["--squash"]              # appended to image builds only (`goga build`/`--update`)
```

Each `docker.run` / `docker.build` entry is parsed as a **shell fragment**:
`-v /host:/container` becomes two argv tokens (`-v` and the volume spec), so you
can write them the same way you would on the command line. The `--flag=value`
form and already-split single tokens are unchanged. Quote a value that contains
whitespace (e.g. `-v "/host with space:/c"`); `$VAR` and `~` are not expanded. A
malformed entry (an unterminated quote) fails to load with a clean error.

| Field | Type | Description |
|-------|------|-------------|
| `env` | mapping | Environment variables applied as the **lowest-priority base layer** in the container env-file. Git identity, the CLI `-e`/`extra_env` entries, and the engine variables override these on key conflict. Applied to `docker run` containers (`goga build` and `goga pipeline <name>`); not applied to `docker build` |
| `docker.run` | list of strings | Shell fragments appended to every `docker run` invocation in both `goga build` and `goga pipeline`. Each entry is shell-tokenized (e.g. `-v /host:/container` → `-v` + volume spec) |
| `docker.build` | list of strings | Shell fragments appended to image builds only — forwarded by both `goga build` and `goga pipeline` (`docker_build_if_not_exist` / `docker_update`, build branch only; ignored on image pull). Each entry is shell-tokenized like `docker.run` |

## `docker.run` volume mounts and the dashboard file manager

In the run form of `goga pipeline <name>`, every `docker.run` directory-mount
entry additionally becomes a browsable root of the pipeline web UI's file
manager (delivered to the container as `AFM_DOCKER_FILE_ROOTS` — see
[Runtime](../features/pipelines/runtime.md)):

```yaml
docker:
  run:
    - "-v /home/me/data:/home/goga/data"     # browsable in the file manager
    - "-v /home/me/refs:/home/goga/refs:ro"  # read-only root
```

The host part must exist as a directory at launch time; `~` and `$VAR` are not
expanded (a literal `~` path yields no root). Roots appear in token order
after the project root; an explicit `-e AFM_DOCKER_FILE_ROOTS=...` overrides
the composed set.

## Env layering

Two ladders apply, one on each side of the docker boundary.

**The container env-file ladder** (written by the host launcher of `goga build`
and the run form of `goga pipeline`, lowest to highest): `home.env` < git
identity (`GIT_AUTHOR_*` / `GIT_COMMITTER_*` of the current user) < the raw
`-e KEY=VALUE` CLI lines < the engine variables (`AFM_DIR`,
`AFM_DOCKER_FILE_ROOTS`, and the `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` proxy
triple when a proxy is resolved — an engine line is skipped when the CLI
supplied that key, so `-e HTTP_PROXY=...` overrides the launcher's) < the
`GOGA_EXTRA_ENV` payload line (the encoded copy of the `-e` entries; the last
line, so docker `--env-file` last-write-wins gives it precedence). The payload
is a single line — docker's env-file parser rejects lines longer than 64 KB,
so the aggregate size of a launch's `-e` entries is bounded by that limit.

**The in-container task env layer** (never part of the env-file): the
domain's configuration env applies in-container around the launched binary
only — `pipeline.env` around the `afm` launch, `build.env` / `build.review.env`
around each ralphex pass — with the decoded CLI `-e` entries applied **above**
it (explicit CLI input wins over config and tool amendments on key conflict)
and the five engine keys (`AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`,
`HTTPS_PROXY`, `NO_PROXY`) dropped silently: launch mechanics are never
overridden. Git identity therefore sits below the task env layer (their keys
practically never collide). Unknown top-level keys of `~/.goga/config.yml`
are ignored.
