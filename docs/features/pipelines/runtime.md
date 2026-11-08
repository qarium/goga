# Runtime

Every command that executes work — `goga pipeline` and `goga build` —
launches the **same project image** as an isolated Docker container. This
page documents the container contract shared by both: the image
requirement, the pre-launch version check, proxy and host networking, and
credentials.

The host side of goga is a thin launcher: it assembles one `docker run`
invocation, forwards the resolved configuration, and propagates the
container's exit code. Everything that interprets pipelines, drives
agents, and executes plans ships inside the image — the host needs only
Docker and the goga package itself.

## Direct in-container execution

The docker launches above are the **host substrate**. Inside the goga image
itself — where the image's build-time `ENV GOGA_DOCKER=1` marker is set —
every form of `goga pipeline` and `goga build` takes the **direct substrate**
instead: the same composed in-container command line and the same env
contract execute directly as a child process, with no `docker run` at all.
The marker is exact (`GOGA_DOCKER=1`); any other value or an unset variable
means the host substrate.

The composition is shared between the substrates — the same argv the docker
substrate hands to the image entrypoint, prefixed with the `python3` program
token, and the same env-file lines parsed into the child's env layer instead
of written to a file. Divergence between the two surfaces is a defect.

What the direct substrate skips (there is no docker launch to perform):
the Docker-CLI check, the [pre-launch version check](#pre-launch-version-check),
the `image` guard and image acquisition/refresh, and the env-file write. The
run form still allocates the port (it is part of the composed contract).

Host-only options — the ones that exist solely to configure the `docker run`
invocation — are rejected with a clean error naming the option, before any
other work; nothing is silently ignored:

| Command | Rejected in-container |
|---|---|
| `goga pipeline` | `-t/--topic`, `--todo`, `-u/--update`, `-e/--env`, `--add-host`, `--proxy` |
| `goga build` | `-e/--env`, `--add-host`, `--proxy`, `-u/--update` |

On the direct substrate `--clean` wipes the state directory the in-container
process actually uses — `/home/goga/pipeline` for `goga pipeline` (the
in-container `AFM_DIR`), `<cwd>/.ralphex` for `goga build` — before the run,
never after. Build's ralphex state does not persist across direct runs (no
host runtime mount exists on this path). `--dry-run` prints the direct
command line, never a `docker run` line.

The child's stdio is inherited (the same streamed output), SIGTERM/SIGINT are
forwarded to the child and the launcher exits with `128 + signum`, and the
child's exit code returns verbatim.

## The image

The top-level `image` field in `.goga/config.yml` selects the image both
commands launch. A [project Dockerfile](../../configuration/project.md)
may additionally be declared for `--update` to build the image from
source. When the field is unset, the command exits with an error naming
`image` before any container is started.

Prerequisite on the host — a working Docker daemon:

```bash
docker info
```

## Pre-launch version check

Before any launch, the goga version installed on the host and the goga
version inside the project image must agree at the **(major, minor)**
level. The image side is measured by one short-lived probe container
(roughly a second) that asks the image for its installed goga version —
captured silently, with no mounts, env-file, or credentials. The host
side is read from the installed distribution metadata. A patch-level
difference agrees; only a major or minor difference counts as a mismatch.

| Situation | Behavior |
|---|---|
| Host and image agree at (major, minor) | Launch proceeds, silently |
| Host and image differ at (major, minor) | Message on stderr, exit 1 — the container is not started |
| Image cannot answer the probe (no python3 or no goga inside the image) | Message on stderr, exit 1 — the container is not started |
| Host version undeterminable (goga not installed for this interpreter, or broken metadata) | Message on stderr, exit 1 — the container is not started |
| Image reports version `0.0.0` (a locally built image without a stamped version) | Warning on stderr, launch continues |

Every refusal message names the remedy. To skip the check entirely, set
`GOGA_SKIP_VERSION_CHECK=1` — both the probe and the comparison are
bypassed (zero extra containers, zero overhead), and the launch behaves
exactly as before the check existed:

```bash
GOGA_SKIP_VERSION_CHECK=1 goga pipeline deploy
```

## Proxy and hosts

`--proxy URL` (and `pipeline.proxy` / `build.proxy` in
`.goga/config.yml`) route the container's traffic through a corporate
proxy. When a proxy is resolved, three variables are written to the
container env-file: `HTTP_PROXY`, `HTTPS_PROXY`, and
`NO_PROXY=localhost,127.0.0.1` (fixed; there is no `--no-proxy`). A proxy
key the CLI supplied explicitly (`-e HTTP_PROXY=...`) is not written by the
launcher — the CLI line keeps winning under docker `--env-file`
last-write-wins.

`--add-host HOST:IP` (and `pipeline.hosts` / `build.hosts` in
`.goga/config.yml`) translate to `docker run --add-host HOST:IP`
flags; CLI entries merge on top of config with the CLI winning on key
conflict.

## File manager roots

The run form writes `AFM_DOCKER_FILE_ROOTS` into the container env-file on
**every** launch — the set of directories the file manager of the pipeline
web UI (served on the published port) lets you browse. The value is standard
base64 (with padding) of a compact UTF-8 JSON payload:

```json
{"version":1,"roots":[{"id":"project","label":"project","container_path":"/workspace","mount_read_only":false,"kind":"project"}]}
```

| Root | Source | Presence |
|---|---|---|
| `project` | the project directory mounted at `/workspace` | always — listed first, read-write |
| `extra` | a directory mount from a [home configuration](../../configuration/home.md) `docker.run` `-v`/`--volume` token | when the token's host part exists as a directory at launch time |

Extra roots are labeled with their full container path, appear in token order
after the project root, and a `:ro` mount is flagged read-only. Named volumes,
file mounts, missing host paths, and the persistent
pipeline state directory never become roots. The value is deterministic —
unchanged mounts produce the identical value on every launch.

An explicit `-e AFM_DOCKER_FILE_ROOTS=...` entry wins over the
launcher-composed value (docker `--env-file` last-write-wins). The list/info
forms write an env-file only when there is profile cargo (a non-empty
ambient `GOGA_PROFILE` or a non-empty personal bundle); when they do, the
variable is composed the same way, otherwise the image's static default
applies.

## Credentials

Nothing is mounted automatically. The launchers add no credential mounts
of their own — the container starts with the project, the runtime state,
and the engine mounts, and nothing else — so the credentials the in-container
agent uses are entirely yours to provide, in either of two channels:

**Volume tokens (file credentials).** Add `-v`/`--volume` tokens to the
`docker.run` list of the [home configuration](../../configuration/home.md)
(`~/.goga/config.yml`); they join every `docker run` goga launches, in both
the pipeline and build forms. Tokens pass to docker verbatim — `~` and
`$HOME` are **not** expanded, so spell the host part as an absolute path:

```yaml
docker:
  run:
    - "-v /home/<you>/.claude/.credentials.json:/home/goga/.claude/.credentials.json:ro"
    - "-v /home/<you>/.codex/auth.json:/home/goga/.codex/auth.json:ro"
```

Mount each credential file to the container path its CLI looks up natively —
the container layout mirrors the host layout under `/home/goga/`:

| agent | host file | container path |
|---|---|---|
| claude | `~/.claude/.credentials.json` | `/home/goga/.claude/.credentials.json` |
| codex | `~/.codex/auth.json` | `/home/goga/.codex/auth.json` |
| opencode | `~/.local/share/opencode/auth.json` | `/home/goga/.local/share/opencode/auth.json` |

**Environment variables (API keys).** When the agent's CLI accepts an API-key
variable, pass it with the launcher's `-e/--env KEY=VALUE` option (for example
`ANTHROPIC_API_KEY=...`) or through the `pipeline.env` configuration: a `-e`
entry joins the container environment verbatim and additionally applies above
the task env layer for the launched binary, while a `pipeline.env` entry
applies in-container around the `afm` launch only (`-e` wins on key conflict —
see [Home configuration — Env layering](../../configuration/home.md#env-layering)).

Recommendations: mount credential files read-only (`:ro`) — the container
must never modify host credentials — and mount only the credential file,
never the whole agent directory (a directory mount leaks host settings and
caches into the container). An absent credential file is not an error: the
in-container agent surfaces authentication failure through its own error
path. On macOS, web-login for the claude CLI stores the token in the
Keychain and auto-deletes `~/.claude/.credentials.json`; the Keychain cannot
be bind-mounted, so re-create the file manually with the OAuth token or use
`ANTHROPIC_API_KEY` instead.
