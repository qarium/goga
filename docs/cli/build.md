# goga build

Execute a build plan via a ralph-loop inside a Docker container.

## Synopsis

```bash
goga build PLAN [OPTIONS]
```

## Description

`goga build` launches the goga build pipeline for a given plan file. It prepares the environment, validates preconditions, and delegates execution to a ralph-loop running inside a Docker container with the goga in-container process as the entry point.

The build pipeline performs these steps:

1. **Docker check** -- Verifies Docker is installed and accessible.
2. **Config loading** -- Reads `.goga/config.yml` for build settings.
3. **Uncommitted manifest check** -- Scans `git status` for uncommitted `CODEMANIFEST` files (can be skipped).
4. **Agent preconditions** -- Resolves the agent wrapper path into `.ralphex/config` (e.g., `claude_command = /home/goga/bin/claude-as-claude.sh`; the wrappers ship inside the image). A review executor with a set `agent` that differs from the task executor, or that declares a non-empty `env`, combined with an active worktree (`--worktree` or `build.worktree: true`) is rejected host-side with exit 1, before any container launch — the ralph-loop review mode cannot follow a worktree branch. The guard is config-level and skip-independent: `--skip-review` does not bypass it.
5. **Defaults copy** -- Fully rewrites `.ralphex/prompts/` and `.ralphex/agents/` from the configured `build.prompts_dir`/`build.agents_dir`, or from the vendored ralph-loop defaults shipped with goga (`goga/assets/ralphex/`). When `build.review_executor.roles` is set, the review prompts are filtered to the selected roles.
6. **Image refresh (optional)** -- When `--update`/`-u` is set, the image is refreshed: if a top-level `dockerfile` is declared in `.goga/config.yml`, `docker build` runs against it (build failure is fatal — exit 1); otherwise `docker pull` runs (a pull failure is logged as a warning and the build proceeds with the locally available image). By default no refresh happens and the local image is used as-is.
7. **Docker execution** -- Launches the ralph-loop command inside the configured Docker image, after a pre-launch host–image version check (see [Pre-launch version check](#pre-launch-version-check)). Credential files for claude, codex, and opencode are detected on the host and bind-mounted read-only into the container automatically (no flag).

## Arguments

| Argument | Description |
|---|---|
| `PLAN` | Path to the build plan file (required). |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | off | Print the assembled command without executing |
| `--worktree` | flag | off | Enable ralph-loop worktree mode |
| `--skip-finalize` | flag | off | Skip finalization step |
| `--skip-manifest-check` | flag | off | Skip check for uncommitted CODEMANIFEST files |
| `--skip-review` / `--no-skip-review` | bool pair (tri-state) | unset | Skip the review phase (`--skip-review`, the ralph-loop `--tasks-only`) or force the full cycle (`--no-skip-review`). Overrides `build.review_executor.skip` in `.goga/config.yml`; when neither is given, the config decides |
| `--session-timeout` | string | config | Session timeout duration |
| `--idle-timeout` | string | config | Idle timeout duration |
| `--wait` | string | config | Wait time before starting |
| `--max-iterations` | int | config | Maximum number of build iterations |
| `--review-patience` | int | config | Review patience count |
| `--base-ref` | string | config | Review diff base (branch name or commit hash); overrides `build.review_executor.base_ref` |
| `-e`, `--env` | string (repeatable) | -- | Additional environment variable (`KEY=VALUE`, repeatable) |
| `--proxy` | string | config | HTTP/HTTPS proxy URL; overrides `build.proxy`. Adds `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` to the container env-file |
| `--add-host` | string (repeatable) | -- | Add a `docker run --add-host HOST:IP` entry; merges on top of `build.hosts` (CLI wins on key conflict) |
| `--update`, `-u` | flag | off | Refresh the image before launch (build if a project Dockerfile is declared, else pull). Default skips the refresh |
| `-c`, `--clean` | flag | off | Wipe the persistent ralph-loop runtime host directory before launch (default preserves state across runs) |

Timeout and iteration options fall back to values in `.goga/config.yml` when not provided on the command line.

`--review-patience` and `--base-ref` are review-scoped: they resolve with precedence CLI > `build.review_executor.*` in `.goga/config.yml` > omit, and they apply to review-carrying passes only — the single full-cycle pass, or the review pass of a two-pass run; a tasks-only run carries neither. The legacy `build.review_patience` key is not parsed (the setting moved to `build.review_executor.patience`).

### Proxy and hosts

`--proxy URL` (and `build.proxy` in `.goga/config.yml`) route the container's traffic through a corporate proxy. When a proxy is resolved, three variables are written to the container env-file:

| Variable | Value |
|---|---|
| `HTTP_PROXY` | the resolved proxy URL |
| `HTTPS_PROXY` | the resolved proxy URL |
| `NO_PROXY` | `localhost,127.0.0.1` (fixed; cannot be overridden) |

`--add-host HOST:IP` (and `build.hosts` in `.goga/config.yml`) translate to `docker run --add-host HOST:IP` flags. CLI entries are merged on top of config; on host-key conflict, the CLI entry wins. Format is split on the first colon only — Docker reports malformed entries itself.

### Credential mounts

Credential files for the supported AI agents are detected on the host and bind-mounted read-only into the container automatically (no flag): claude (`~/.claude/.credentials.json`), codex (`~/.codex/auth.json`), and opencode (`~/.local/share/opencode/auth.json`). Detection is agent-agnostic — it is not filtered by the configured `task_executor.agent` — and only files that exist are mounted. When none exist, no credential mount is added.

### Ralphex runtime isolation

The ralph-loop writes its persistent state to a `.ralphex/` directory it auto-detects in its working directory. Rather than letting that state accumulate inside your project directory, `goga build` bind-mounts a centralized host directory over `/workspace/.ralphex`, so the bytes physically land on the host under:

```
~/.goga/runtime/builds/<normalized_project>/<branch>/
```

`<normalized_project>` is the project's absolute path with leading slashes stripped and remaining slashes replaced by hyphens; `<branch>` is the current git branch (slashes replaced with hyphens), or `default` when git is unavailable, the directory is not a repository, or HEAD is detached.

The directory survives across runs of the same project on the same branch by default, so an interrupted build can be resumed. Pass `--clean` to wipe and recreate it before launch for a fresh run. The host path never reaches the container except as the `/workspace/.ralphex` mount source — the container sees only `/workspace/.ralphex`.

Note: concurrent builds of the same project on the same branch share one runtime directory; run them on different branches or use `--clean` if isolation is required.

### Pre-launch version check

Before the working container starts, `goga build` checks that the goga version installed on the host and the goga version inside the project image agree at the **(major, minor)** level. The image side is measured by one short-lived probe container (roughly a second): `docker run --rm --entrypoint python3 <image> -c "from importlib.metadata import version; print(version('goga'))"` — captured silently, with no mounts, env-file, or credentials. The host side is read from the installed distribution metadata. A patch-level difference agrees; only a major or minor difference counts as a mismatch.

| Situation | Behavior |
|---|---|
| Host and image agree at (major, minor) | Launch proceeds, silently |
| Host and image differ at (major, minor) | Message on stderr, exit 1 — the working container is not started |
| Image cannot answer the probe (no python3 or no goga inside the image) | Message on stderr, exit 1 — the working container is not started |
| Host version undeterminable (goga not installed for this interpreter, or broken metadata) | Message on stderr, exit 1 — the working container is not started |
| Image reports version `0.0.0` (a locally built image without a stamped version) | Warning on stderr, launch continues |

Every refusal message names the remedy. To skip the check entirely, set `GOGA_SKIP_VERSION_CHECK=1` — both the probe and the comparison are bypassed (zero extra containers, zero overhead), and the launch behaves exactly as before the check existed:

```bash
GOGA_SKIP_VERSION_CHECK=1 goga build plan.md
```

## Examples

Run a build plan:

```bash
goga build plan.md
```

Dry run to see the command without executing:

```bash
goga build plan.md --dry-run
```

Run with custom timeouts and an extra environment variable:

```bash
goga build plan.md --session-timeout 1h --max-iterations 50 -e ANTHROPIC_API_KEY=sk-xxx
```

Skip the uncommitted CODEMANIFEST check:

```bash
goga build plan.md --skip-manifest-check
```

Skip the review phase (run tasks only):

```bash
goga build plan.md --skip-review
```

Review against a specific branch or commit instead of the detected default:

```bash
goga build plan.md --base-ref origin/1.2.x
```

Pull the latest image, then build (default skips the pull):

```bash
goga build plan.md --update
```

Route container traffic through a corporate proxy and add a local host entry:

```bash
goga build plan.md --proxy http://corp:3128 --add-host foo.local:127.0.0.1
```

Wipe persistent ralph-loop state before launching a fresh build:

```bash
goga build plan.md --clean
```

## Configuration

Build settings are loaded from `.goga/config.yml`. Example configuration:

```yaml
language: python
image: qarium/goga-python-3.12:1.3
# dockerfile: .goga/Dockerfile   # optional — when set, `--update` builds the image from this Dockerfile instead of pulling
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
    env: {}
  proxy: http://corp:3128      # optional HTTP/HTTPS proxy URL for the build container
  hosts:                        # optional docker run --add-host entries
    foo.local: 127.0.0.1
```

Only `language` is required by the loader. `goga build` additionally requires a `build` section (it exits with a `ClickException` when `build` is absent), a non-`None` `build.task_executor.agent` (optional at the loader level — absent/empty/whitespace resolves to `None`; the command raises a `ClickException` when it is `None`, since the build needs an agent to resolve the in-container wrapper), and the top-level `image` field must be set; otherwise the command exits with an error. The deprecated `build.image` field is rejected — use the top-level `image` field. The optional top-level `dockerfile` field (when set) makes `--update` build the image locally from that Dockerfile instead of pulling it. The optional `build.proxy` and `build.hosts` fields are overridden/augmented by the `--proxy` and `--add-host` CLI options respectively.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Build completed successfully |
| `1` | Build failed (Docker not found, config error, precondition failure, invalid review configuration, two-pass review combined with worktree, a ralph-loop error — a missing `ralphex` binary or a rejected launch surfaces as a clean one-line message with exit code 1 — a fatal `docker build` under `--update`, or the pre-launch version check refusing the launch: a host–image (major, minor) mismatch, an image that cannot answer the version probe, or an undeterminable host version — see [Pre-launch version check](#pre-launch-version-check)) |
