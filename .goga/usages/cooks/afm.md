# Running AI-flow scenarios via afm

## Tool

**afm** is an external CLI tool (Go binary) that orchestrates multi-stage AI-flow scenarios.

Two artifacts matter for `goga`:

- the **base image** `akopichin/afm:latest` — ships `/usr/local/bin/afm` (used as the source in `Dockerfile:12`);
- the **goga image** — ships the `afm` binary on `PATH` (alongside `claude` and `codex` CLIs) so it can be selected as the afm client.

**IMPORTANT** — `afm` is an external tool, distinct from `goga`. It is modified and developed in a separate repository; `goga` only integrates with its CLI contract.

## CLI contract (current)

`afm` runs as a top-level command with one global flag and a set of subcommands.

### Global flag

| Flag          | Env       | Default     | Purpose                                            |
|---------------|-----------|-------------|----------------------------------------------------|
| `--dir <path>`| `AFM_DIR` | current dir | Base directory for afm state (flows + run-state). NOTE: `~/.afm/config.yaml` is always read from the user's home, independent of `--dir`. |

### Commands

| Command           | Purpose                                                            |
|-------------------|--------------------------------------------------------------------|
| `afm init`        | Interactively create a flow file in `.afm/flows/`                  |
| `afm list`        | List flow files from `.afm/flows/` relative to `--dir` / CWD       |
| `afm run`         | Run a flow (or resume the latest run)                              |
| `afm check`       | Show status of the latest run                                      |
| `afm approve`     | Approve a stage plan (`awaiting_approval` → `ready`)               |
| `afm retry`       | Retry a failed stage (`failed` → `pending`)                        |
| `afm revise`      | Submit feedback to revise a stage plan                             |
| `afm install-skills` | Install AFM Claude skills into `~/.claude/skills/`              |

### Key command — `run`

```
afm run [flow.yaml] [flags]
```

- Accepts a **path to the flow file** as a positional argument (absolute or relative to CWD, not to `--dir`).
- If the path is omitted, afm resumes the most recent run.
- Flow files typically live under `.afm/flows/`, but `run` accepts an absolute path so a flow can be launched from anywhere.

Optional `run` flags:

- `--idle-timeout duration` — agent idle timeout
- `--max-parallel int` — maximum number of parallel stages (0 = no limit)
- `--port int` — dashboard port (0 = use the value from `config.yaml`)

### Key command — `list`

```
afm list
```

- Lists flows **only from `.afm/flows/`** relative to `--dir` (or CWD when `--dir` is unset).
- There is no flag to override the directory other than the global `--dir` / `AFM_DIR`.

## Configuration — `~/.afm/config.yaml`

afm reads its configuration from `~/.afm/config.yaml` (the `.afm/` directory
inside the invoking user's home). The single field `goga` cares about is
`client.command` — the absolute in-container path of the `*-as-claude.sh`
wrapper afm will drive (e.g. `/home/goga/bin/codex-as-claude.sh`). `goga`
generates this file per invocation with the resolved wrapper path; a bare
agent name is never written.

`config.yaml` fields (YAML tags surfaced by the binary):

| Field           | Type   | Purpose                                                          |
|-----------------|--------|------------------------------------------------------------------|
| `client.command`| str    | Absolute in-container path of the `*-as-claude.sh` wrapper afm launches as the agent client (e.g. `/home/goga/bin/codex-as-claude.sh`) |
| `port`          | int    | Dashboard port (used when `afm run --port` is `0` or omitted)    |
| `idle_timeout`  | str    | Agent idle timeout (Go duration)                                 |
| `max_parallel`  | int    | Max parallel stages                                              |
| `prompts_dir`   | str    | Custom prompt directory                                          |
| `proxy`         | str    | Outbound proxy settings                                          |
| `server`        | str    | Server-side settings                                             |
| `open_browser`  | bool   | Whether afm opens the dashboard in a browser on start            |

## Directory layout afm expects

```
~/.afm/
├── config.yaml                # optional; afm falls back to defaults when missing
└── flows/                     # flow *.yaml files discovered by `afm list`
```

## Integration with goga

`goga pipeline <name>` runs afm **inside the goga Docker image**, mirroring how
`goga build` launches ralphex. The host does:

1. Pick a free localhost port (bind a `socket` to `("", 0)`, read the assigned
   port, close it, and hand the same value to both `-p <port>:<port>` and
   `afm run --port <port>`).
2. Generate `~/.afm/config.yaml` content as a 0600 tempfile with
   `client.command: /home/goga/bin/<agent>-as-claude.sh` (an absolute
   in-container wrapper path matching the `*-as-claude.sh` convention) and
   mount it into the container at `/home/goga/.afm/config.yaml:ro` (the
   `goga` user's home inside the image). Unlink the tempfile in a `finally`
   block.
3. `docker run --rm -p <port>:<port> -v <project_dir>:/workspace
   -w /workspace -v <afm_config_tmpfile>:/home/goga/.afm/config.yaml:ro
   --env-file <env_file> [-v ~/.codex/auth.json:ro] <config.image>
   afm run --port <port> <flow_path>`
4. Forward `SIGTERM` / `SIGINT` to the container, kill it in `finally`, and
   propagate afm's exit code as `goga pipeline`'s exit code.

### Pipeline path resolution inside the container

- Project pipelines live under `<project_dir>/.goga/pipelines/` and reach the
  container through the `<project_dir>:/workspace` volume; the in-container
  path is `/workspace/.goga/pipelines/<name>.yml`.
- User pipelines live under `~/.goga/pipelines/` and are **not** under
  `/workspace`; they need either an additional `-v` mount or a deliberate
  decision to restrict the in-container launcher to project pipelines only.
  This decision belongs to the architecture phase.

### Handling container/subprocess errors

| Case                                                  | goga-side behavior                                  |
|-------------------------------------------------------|-----------------------------------------------------|
| `docker` CLI not found on the host                    | Emit a clear message, exit ≠ 0                      |
| afm exits with a non-zero code                        | Propagate the code as `goga pipeline`'s exit code   |
| `SIGTERM` / `SIGINT` received on the host             | Stop the container, run `docker kill` in `finally`  |
| `<name>.yml` not found by `list_pipelines`            | Emit a clear message, exit ≠ 0 (do not start afm)   |

## Anti-patterns

- Do not place the afm config or any afm-managed state inside `/workspace`.
  `/workspace` is the user's project directory; `~/.afm/` is afm's home. The
  generated `config.yaml` must mount to `/home/goga/.afm/config.yaml`.
- Do not pass a pipeline name as an identifier to `afm run` (e.g.
  `afm run my-pipeline`). afm interprets the argument as a path — pass the
  file path instead.
- Do not rely on `afm list` seeing pipelines in `~/.goga/pipelines/` — it
  reads `~/.afm/flows/` only. `goga pipeline` (discovery mode) reads the goga
  pipeline directories directly via `list_pipelines`, not through afm.
- Do not modify the external `afm` to accommodate the integration. It is
  developed independently; `goga` adapts to its CLI contract.

## Persistent state via AFM_DIR

afm's `config.yaml` (containing `client.command`) is always read from
`~/.afm/config.yaml` — it does NOT move when `AFM_DIR` / `--dir` is set.
The `AFM_DIR` / `--dir` flag controls only where afm writes its **state**
(flows, run-state, logs).

Inside the goga container, the host-side launcher (`goga/commands/pipeline`)
sets `AFM_DIR=/home/goga/pipeline` via the container env-file and bind-mounts
a host directory at that path read-write:

- Host path: `~/.goga/runtime/pipelines/<project-without-slash>/<git-branch>/<pipeline-name>/`
- Container path: `/home/goga/pipeline` (mounted read-write)
- Env-file: `AFM_DIR=/home/goga/pipeline`

`<project-without-slash>` is the absolute project path (result of
`Path.cwd().resolve()`) with the leading slash removed and every remaining
slash replaced by a hyphen — e.g. `/Users/wb/IdeaProjects/my/project` →
`Users-wb-IdeaProjects-my-project`.

`<git-branch>` is the current git branch (via `git rev-parse --abbrev-ref HEAD`),
or the literal `"default"` when git is unavailable, the directory is not a git
repository, or HEAD is detached.

State in this directory survives across runs of the same pipeline in the same
project on the same branch. Use `goga pipeline <name> --clean` to wipe the
directory before launch.

The `AFM_DIR` variable is provided exclusively by the host-side launcher
through the env-file. The `client.command` tmpfile is generated per invocation
and bind-mounted read-only at `/home/goga/.afm/config.yaml` — this path is
independent of `AFM_DIR` and supplies the `client.command` overlay; the
persistent directory mounted at `/home/goga/pipeline` supplies the rest of
afm state.

### Constraints

- Do not place afm state under `/workspace` — `/workspace` is the project
  directory; `/home/goga/pipeline` is afm's persistent state home inside the
  container.
- Do not delete the persistent directory in the host launcher's `finally` block
  — only the `client.command` tmpfile and env-file are deleted; state survives
  across runs.
- Do not set `AFM_DIR` via the Dockerfile — the host-side launcher owns the
  variable through the env-file so the path is deterministic per project,
  branch, and pipeline.
- Do NOT derive the `client.command` tmpfile mount target from `AFM_DIR` —
  `config.yaml` is always read from `~/.afm/config.yaml` (= `/home/goga/.afm/config.yaml`
  in the container), regardless of where `AFM_DIR` points.