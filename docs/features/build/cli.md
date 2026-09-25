# goga build

Execute a build plan inside an isolated Docker container.

## Synopsis

```bash
goga build PLAN [OPTIONS]
```

## Description

`goga build` launches the goga build pipeline for a given plan file. It prepares the environment, validates preconditions, and delegates execution to the build engine running inside a Docker container with the goga in-container process as the entry point.

The build pipeline performs these steps:

1. **Docker check** -- Verifies Docker is installed and accessible.
2. **Config loading** -- Reads `.goga/config.yml` for build settings. The optional machine-wide home config (`~/.goga/config.yml`) layers underneath: `home.env` is the base (lowest-priority) layer of the container env-file, `home.docker.run` is appended to every `docker run`, `home.docker.build` is forwarded to image builds. Git identity env (`GIT_AUTHOR_NAME/EMAIL`, `GIT_COMMITTER_NAME/EMAIL`) is layered in, tolerating absent git config.
3. **Uncommitted manifest check** -- Scans `git status` for uncommitted `CODEMANIFEST` files (can be skipped).
4. **Agent preconditions** -- Resolves the configured agent to its in-container wrapper (the wrappers ship inside the image). Requires a `build` section and a resolvable `build.agent` — a missing section or a `None` agent is rejected host-side with exit 1, before any container launch. The review agent's wrapper (`build.review.agent`) and, when the strategy engages the external review, the additional agent's wrapper are validated in-container before their pass.
5. **Defaults copy** -- Fully rewrites the engine's prompt and agent defaults from the configured `build.prompts_dir`/`build.agents_dir`, or from the defaults shipped with goga. When `build.review.roles` is set, the review prompts are filtered to the selected roles; when `build.review.finalize` is set, the finalize step's ralphex files are materialized from the prompt.
6. **Image refresh (optional)** -- When `--update`/`-u` is set, the image is refreshed: if a top-level `dockerfile` is declared in `.goga/config.yml`, `docker build` runs against it (build failure is fatal — exit 1); otherwise `docker pull` runs (a pull failure is logged as a warning and the build proceeds with the locally available image). By default no refresh happens and the local image is used as-is.
7. **First-run safety net** -- Runs unconditionally at launch entry: when the configured image is absent locally AND a project `dockerfile` is declared, the image is built once before launch (fatal on failure — the launch is skipped). This closes the corner case where a Dockerfile is declared but the image was never built and `--update` is not passed.
8. **Docker execution** -- Launches the build inside the configured Docker image, after the shared pre-launch host–image version check (see [Runtime — Pre-launch version check](../pipelines/runtime.md#pre-launch-version-check)). The launcher adds no credential mounts — provide the agent's credentials yourself (see [Runtime — Credentials](../pipelines/runtime.md#credentials)). Persistent build state is isolated from the project directory (see [Runtime state isolation](#runtime-state-isolation)). The pass structure: a run with review on is always two passes — a tasks pass (`--tasks-only`) on the `build.agent` wrapper, then a review pass (`--review`, or `--external-only` under `strategy: short`) on the review-stage agent's wrapper with the review env (`build.review.env`) overlaid for that subprocess only; a failed tasks pass skips the review; `--skip-review` (or `build.review.skip: true`) collapses the run to the tasks pass alone. Before the first pass, the `build/validate_build` hooks gate runs — a vetoed run stops with exit 1 and no pass (see [Hooks](hooks.md)).
9. **Plan relocation** -- After a successful final pass the plan file moves to `<plan_dir>/completed/<plan_name>` (atomic replace, idempotent by name). A failed run or a dry run leaves the plan in place so the build can resume.

## Arguments

| Argument | Description |
|---|---|
| `PLAN` | Path to the build plan file (required). |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | off | Print the assembled command without executing |
| `--skip-manifest-check` | flag | off | Skip check for uncommitted CODEMANIFEST files |
| `--skip-review` / `--no-skip-review` | bool pair (tri-state) | unset | Skip the review phase (`--skip-review` — a tasks-only run) or force the full cycle (`--no-skip-review`). Overrides `build.review.skip` in `.goga/config.yml`; when neither is given, the config decides |
| `--session-timeout` | string | config | Session timeout duration |
| `--idle-timeout` | string | config | Idle timeout duration |
| `--wait` | string | config | Wait time before starting |
| `--max-iterations` | int | config | Maximum number of build iterations (tasks pass) |
| `--review-patience` | int | config | External-review patience — addresses `build.review.additional.patience` in `.goga/config.yml`; forwarded to the container only when set |
| `--base-ref` | string | config | Review diff base (branch name or commit hash); overrides `build.review.base_ref`; reaches ralphex as `--base-ref` on the review pass only |
| `-e`, `--env` | string (repeatable) | -- | Additional environment variable (`KEY=VALUE`, repeatable) |
| `--proxy` | string | config | HTTP/HTTPS proxy URL; overrides `build.proxy`. Adds `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` to the container env-file |
| `--add-host` | string (repeatable) | -- | Add a `docker run --add-host HOST:IP` entry; merges on top of `build.hosts` (CLI wins on key conflict) |
| `-u`, `--update` | flag | off | Refresh the image before launch (build if a project Dockerfile is declared, else pull). Default skips the refresh |
| `-c`, `--clean` | flag | off | Wipe the build's persistent runtime directory on the host before launch (default preserves state across runs) |

Timeout and iteration options fall back to values in `.goga/config.yml` when not provided on the command line.

`--review-patience` and `--base-ref` are review-scoped: they resolve with precedence CLI > `build.review.*` in `.goga/config.yml` > omit, and they apply to the review pass only — a skipped run carries neither. The patience setting lives at `build.review.additional.patience` (the legacy `build.review_patience` and `build.review_executor.patience` keys are not parsed).

### Proxy and hosts

`--proxy` and `--add-host` (with `build.proxy` / `build.hosts` in
`.goga/config.yml`) follow the shared container contract — see
[Runtime — Proxy and hosts](../pipelines/runtime.md#proxy-and-hosts).

### Credentials

The launcher adds no credential mounts — mount the agent's credential file
yourself via a `docker.run` volume token in the home configuration, or pass
its API-key env var with `-e`; see
[Runtime — Credentials](../pipelines/runtime.md#credentials).

### Runtime state isolation

The build engine writes its persistent state to a `.ralphex/` directory it auto-detects in its working directory. Rather than letting that state accumulate inside your project directory, `goga build` bind-mounts a centralized host directory over `/workspace/.ralphex`, so the bytes physically land on the host under:

```
~/.goga/runtime/builds/<normalized_project>/<branch>/
```

`<normalized_project>` is the project's absolute path with leading slashes stripped and remaining slashes replaced by hyphens; `<branch>` is the current git branch (slashes replaced with hyphens), or `default` when git is unavailable, the directory is not a repository, or HEAD is detached.

The directory survives across runs of the same project on the same branch by default, so an interrupted build can be resumed. Pass `--clean` to wipe and recreate it before launch for a fresh run. The host path never reaches the container except as the `/workspace/.ralphex` mount source — the container sees only `/workspace/.ralphex`.

Note: concurrent builds of the same project on the same branch share one runtime directory; run them on different branches or use `--clean` if isolation is required.

### Pre-launch version check

Before the working container starts, `goga build` runs the shared host–image version check — the goga versions on the host and inside the image must agree at the **(major, minor)** level, or the launch is refused. The full behavior table and the `GOGA_SKIP_VERSION_CHECK=1` escape hatch live in
[Runtime — Pre-launch version check](../pipelines/runtime.md#pre-launch-version-check).

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

Wipe persistent build state before launching a fresh build:

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
  agent: claude
  env: {}
  proxy: http://corp:3128      # optional HTTP/HTTPS proxy URL for the build container
  hosts:                        # optional docker run --add-host entries
    foo.local: 127.0.0.1
```

Only `language` is required by the loader. `goga build` additionally requires a `build` section (it exits with a `ClickException` when `build` is absent), a non-`None` `build.agent` (optional at the loader level — absent/empty/whitespace resolves to `None`; the command raises a `ClickException` when it is `None`, since the build needs an agent to resolve the in-container wrapper), and the top-level `image` field must be set; otherwise the command exits with an error. The deprecated `build.image` field is rejected — use the top-level `image` field, and the retired keys (`worktree`, `skip_finalize`, `codex_review`, and the `task_executor` / `review_executor` block names) are silently ignored — see [Configuration](configuration.md). The optional top-level `dockerfile` field (when set) makes `--update` build the image locally from that Dockerfile instead of pulling it. The optional `build.proxy` and `build.hosts` fields are overridden/augmented by the `--proxy` and `--add-host` CLI options respectively.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Build completed successfully |
| `1` | Build failed (Docker not found, config error, precondition failure, invalid review configuration, a hook veto at the `build/validate_build` gate, an execution-engine error — a missing engine binary inside the image or a rejected launch surfaces as a clean one-line message with exit code 1 — a fatal `docker build` under `--update`, or the pre-launch version check refusing the launch: a host–image (major, minor) mismatch, an image that cannot answer the version probe, or an undeterminable host version — see [Runtime — Pre-launch version check](../pipelines/runtime.md#pre-launch-version-check)) |
