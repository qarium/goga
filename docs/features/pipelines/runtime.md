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
`NO_PROXY=localhost,127.0.0.1` (fixed; cannot be overridden).

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
forms launch no env-file, so they produce no variable — the image's static
default applies there.

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
`ANTHROPIC_API_KEY=...`) or through the `pipeline.env` configuration; the
entry joins the container environment verbatim.

Recommendations: mount credential files read-only (`:ro`) — the container
must never modify host credentials — and mount only the credential file,
never the whole agent directory (a directory mount leaks host settings and
caches into the container). An absent credential file is not an error: the
in-container agent surfaces authentication failure through its own error
path. On macOS, web-login for the claude CLI stores the token in the
Keychain and auto-deletes `~/.claude/.credentials.json`; the Keychain cannot
be bind-mounted, so re-create the file manually with the OAuth token or use
`ANTHROPIC_API_KEY` instead.
