# Running AI-flow scenarios via afm

## Tool

**afm** is an external CLI tool (Go binary) that orchestrates multi-stage AI-flow scenarios.

Two artifacts matter for a host-side launcher that integrates with afm:

- the **base image** `akopichin/afm:latest` — ships `/usr/local/bin/afm` (used as the
  source in a downstream image build);
- the **integration image** — ships the `afm` binary on `PATH` (alongside agent CLIs
  such as `claude` and `codex`) so it can be selected as the afm client.

**IMPORTANT** — `afm` is an external tool. It is modified and developed in a separate
repository; an integrator only consumes its CLI contract.

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
- `--require-approval` — run in approval-required mode (each stage awaits explicit approval before executing)

### Key command — `list`

```
afm list
```

- Lists flows **only from `.afm/flows/`** relative to `--dir` (or CWD when `--dir` is unset).
- There is no flag to override the directory other than the global `--dir` / `AFM_DIR`.

## Configuration — `~/.afm/config.yaml`

afm reads its configuration from `~/.afm/config.yaml` (the `.afm/` directory inside the
invoking user's home). The single field that matters for integration is `client.command` —
the absolute in-container path of the `*-as-claude.sh` wrapper afm will drive (e.g.
`/home/goga/bin/codex-as-claude.sh`). The host-side launcher generates this file per
invocation with the resolved wrapper path; a bare agent name is never written.

`config.yaml` fields (YAML tags surfaced by the binary):

| Field           | Type   | Purpose                                                          |
|-----------------|--------|------------------------------------------------------------------|
| `client.command`| str    | Absolute in-container path of the `*-as-claude.sh` wrapper afm launches as the agent client (e.g. `/home/goga/bin/codex-as-claude.sh`) |
| `port`          | int    | Dashboard port (used when `afm run --port` is `0` or omitted)    |
| `idle_timeout`  | str    | Agent idle timeout (Go duration)                                 |
| `max_parallel`  | int    | Max parallel stages                                              |
| `prompts_dir`   | str    | Custom prompt directory. When set, afm reads the four agent prompts (`planning.md`, `implementation.md`, `review.md`, `summary.md`) from this directory instead of its built-in defaults. The goga host-side launcher always writes `prompts_dir: /home/goga/pipeline/prompts` so afm uses the goga-managed prompt directory. |
| `proxy`         | map    | Outbound proxy settings. Surfaces at least `proxy.enabled: bool` — when `false`, afm does not use its own internal outbound proxy provider. The goga host-side launcher always writes `proxy.enabled: false`: goga manages the outbound proxy through the container env-file (`HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`), so afm's own internal proxy provider must stay off to avoid the two layers colliding. |
| `server`        | str    | Server-side settings                                             |
| `open_browser`  | bool   | Whether afm opens the dashboard in a browser on start. The goga host-side launcher always writes `open_browser: false`: the dashboard runs inside a container and is reached via the host-printed http://localhost:<port> URL, so an in-container browser launch has no effect. |
| `theme`         | str    | Dashboard theme name. The goga host-side launcher always writes `theme: goga`. |

## Directory layout afm expects

```
~/.afm/
├── config.yaml                # optional; afm falls back to defaults when missing
└── flows/                     # flow *.yaml files discovered by `afm list`
```

## Per-stage command override (flow-file)

afm honors a per-stage `command:` field inside each stage of a flow-file. When a stage carries `command:`, afm uses that wrapper for the stage instead of the global `client.command` from `~/.afm/config.yaml`. The value follows the same convention as `client.command` — an absolute in-container path to a `*-as-claude.sh` wrapper (e.g. `/home/goga/bin/codex-as-claude.sh`).

The override is per-stage only; stages without `command:` keep using the global `client.command`. This lets a single flow route different stages to different agents (planning with claude, review with codex, etc.) without modifying the launcher-side config.yaml.

The goga host-side launcher still writes the global `client.command` tmpfile — it serves as the default for every stage that does not override. Per-stage overrides are authored by the goga workflow layer (not the launcher): they appear in the serialized flow-file as a stage field.

## Per-stage auto-approval, launch, and script directives (flow-file)

afm honors the following additional per-stage keys inside each stage of a flow-file:

| Key | Type | Purpose |
|-----|------|---------|
| `auto_approve` | bool | When true, afm auto-approves the stage plan (no manual `afm approve` step). Authored by the goga workflow layer from an `approve: auto` directive. |
| `auto_run` | bool | When false, the stage pauses and starts only manually (Continue in the dashboard); dependents wait. Authored by the goga pipeline compiler from a `trigger: manual` stage directive or a workflow `manual: true` instruction. Never emitted as true (omitempty contract — absence is the norm). |
| `script_before` | str | Shell script run before the stage's agent invocation. |
| `script` | str | Shell script run as the stage's action (mutually exclusive with the stage's `prompt`/`skills`). |
| `script_after` | str | Shell script run after the stage's agent invocation. |
| `script_timeout` | str | Timeout for the stage's script action (Go duration), applied via afm's script-timeout defaults. Authored by the goga pipeline compiler from a `timeout` stage directive; the value passes verbatim — a malformed duration surfaces at runtime. |
| `buttons` | map[str]str | Per-stage note buttons — a map of "button name → prompt text". Accepted by `afm validate` (single- and multi-line values); in the current binary the key is not yet interpreted (forward-compat) — it is neither rejected nor processed. Compiled by the goga workflow layer from a `notes` instruction (`workflow.stages.<name>.notes`). |
| `reflect` | map | Per-stage memory reflection — a map with a required `file` key (str) and an optional `mode` key (`r`/`w`/`rw`). afm treats `file` as a path INSIDE the flow's `memory.path`. Compiled by the goga workflow layer from a `reflect` instruction (`workflow.stages.<name>.reflect`, reflect method); goga materializes `mode: rw` when the authoring entry omits it. |
| `memory_use` | *bool | Per-stage participation in the flow's memory. An unset key INHERITS the global `memory.memory_use` (afm computes `UseFor(stage) = stage.memory_use ?? memory.memory_use`), so the goga pipeline compiler emits an explicit `memory_use: false` on every unmarked stage whenever the global `memory` block is emitted. Compiled from a workflow `memory: true` instruction (alignment method). |

These keys are optional per stage; stages that do not carry them behave as before (backward compatible). goga authors `auto_approve` from its `approve: auto` workflow directive, translates its authoring `before_script`/`script`/`after_script` stage-body keys into `script_before`/`script`/`script_after`, compiles its authoring `timeout` stage directive into `script_timeout` (verbatim), and authors `auto_run: false` from a `trigger: manual` stage directive or a workflow `manual: true` instruction (never `true`; the key's absence is the norm). goga compiles its workflow `notes` instruction (map str→str) into the per-stage `buttons` field; the interpretation of the buttons belongs to afm (a separate repository) — goga only serializes the field.

## Memory mechanism (flow-file, afm v0.5.60+)

afm supports a persistent-memory mechanism authored through the flow-file: a global
`memory` block plus two per-stage keys (`reflect`, `memory_use`).

### Global `memory` block

A top-level flow-file key placed after `description` and before `stages`, with the key
order `path`, `mode`, `memory_use`, `max_rules`, `commit`:

| Key | Type | Purpose |
|-----|------|---------|
| `path` | str | Memory directory (e.g. `.goga/memory`); a stage's `reflect.file` resolves inside it |
| `mode` | str (`r`/`w`/`rw`) | Project-memory access mode |
| `memory_use` | bool | Global participation default inherited by stages that carry no `memory_use` of their own |
| `max_rules` | int (>= 1) | Maximum number of memory rules |
| `commit` | bool | Whether memory changes are committed |

### Semantics (recovered from the afm binary)

- `UseFor(stage) = stage.memory_use ?? memory.memory_use` — a stage key that is not set
  inherits the global value.
- `CanReadProject` / `CanWriteProject` check EXACT equality of `mode` against
  `r`/`w`/`rw`: an empty `mode` means neither read nor write (NOT `rw`).
- `reflect.file` is treated as a path INSIDE `memory.path`.
- The afm-side default of `max_rules` is not locatable in the binary.
- afm does NOT reject unknown keys — a typo in a key name passes silently, which is why
  goga performs the full authoring validation on its own side.

### goga authoring stance

goga authors memory in the workflow-file (the `memory:` block plus the `reflect`/`memory`
stage instructions) and compiles it into the flow-file; the runtime interpretation belongs
to afm. The global block is emitted if and only if at least one stage participates in
memory; defaults are materialized (`max_rules: 25`, `commit: false`, `mode: r` for the
reflect method, the authored `mode` value (`rw` by default) for the alignment method, and
the global `memory_use: false` under both methods — participation is per-stage opt-in);
`path` is the fixed prefix `.goga/memory` plus an optional authored
suffix; the goga-side `method` key (reflect | alignment) is never written to the
flow-file.

## Integration pattern — running afm in a container

A host-side launcher runs afm **inside a container image** that ships the `afm` binary.
The host does:

1. Pick a free localhost port (bind a `socket` to `("", 0)`, read the assigned port,
   close it, and hand the same value to both `-p <port>:<port>` and
   `afm run --port <port>`).
2. Generate `~/.afm/config.yaml` content as a 0600 tempfile with
   `client.command: /home/goga/bin/<agent>-as-claude.sh` (an absolute in-container
   wrapper path matching the `*-as-claude.sh` convention), plus four static
   launcher-side constants — `theme: goga` (dashboard theme),
   `open_browser: false` (the dashboard is reached via the host-printed
   http://localhost:<port> URL; afm must not attempt to open a browser inside
   the container), `proxy.enabled: false` (afm's own internal outbound proxy
   provider is disabled — goga manages the outbound proxy through the container
   env-file `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`, the two layers must never
   collide), and `prompts_dir: /home/goga/pipeline/prompts` (the in-container
   prompts directory — afm reads four prompt files from this directory,
   `planning.md`, `implementation.md`, `review.md`, `summary.md`, instead of
   its built-in defaults; goga writes this field unconditionally so afm uses
   the goga-managed prompt directory regardless of whether the pipeline-file
   customizes any prompt). Mount the tempfile into the container at
   `/home/goga/.afm/config.yaml:ro` (the in-container user's home).
   Unlink the tempfile in a `finally` block.
3. `docker run --rm -p <port>:<port> -v <project_dir>:/workspace
   -w /workspace -v <afm_config_tmpfile>:/home/goga/.afm/config.yaml:ro
   --env-file <env_file> [-v <host_cred_path>:<container_cred_path>:ro ...] <image>
   afm run --port <port> <flow_path>`

   Credential files are bind-mounted read-only — one `-v` per credential file
   detected on the host. Detection is agent-agnostic (`resolve_credential_mounts()`:
   claude, codex, opencode) rather than a single hardcoded agent mount, so every
   present credential is mirrored into the container at its native lookup path
   under `/home/goga/`. See the `resolve-credential-mounts` and
   `docker-auth-mounts` practices.
4. Forward `SIGTERM` / `SIGINT` to the container, kill it in `finally`, and propagate
   afm's exit code as the launcher's exit code.

### Flow file resolution

- afm reads flow files from `.afm/flows/` relative to `--dir` / `AFM_DIR` (or CWD).
- Because `afm run` accepts an absolute path, the host-side launcher resolves the flow
  file on the host and passes its absolute in-container path to `afm run`.
- Where flows are discovered on the host — a project-level flows directory versus a
  user-level flows directory — is a launcher-side decision; afm itself only knows about
  `.afm/flows/` relative to `--dir`.

### Handling container/subprocess errors

| Case                                                  | Launcher-side behavior                                  |
|-------------------------------------------------------|---------------------------------------------------------|
| `docker` CLI not found on the host                    | Emit a clear message, exit ≠ 0                          |
| afm exits with a non-zero code                        | Propagate the code as the launcher's exit code          |
| `SIGTERM` / `SIGINT` received on the host             | Stop the container, run `docker kill` in `finally`      |
| Flow file not found by the launcher                   | Emit a clear message, exit ≠ 0 (do not start afm)       |

## Anti-patterns

- Do not place the afm config or any afm-managed state inside `/workspace`.
  `/workspace` is the user's project directory; `~/.afm/` is afm's home. The generated
  `config.yaml` must mount to `/home/goga/.afm/config.yaml`.
- Do not pass a flow name as an identifier to `afm run` (e.g. `afm run my-flow`). afm
  interprets the argument as a path — pass the file path instead.
- Do not rely on `afm list` seeing flows outside `.afm/flows/` — it reads
  `~/.afm/flows/` (relative to `--dir`) only. A launcher that needs to enumerate flows
  from elsewhere must read those directories directly, not through afm.
- Do not modify the external `afm` to accommodate the integration. It is developed
  independently; the integrator adapts to its CLI contract.

## Persistent state via AFM_DIR

afm's `config.yaml` (containing `client.command`) is always read from
`~/.afm/config.yaml` — it does NOT move when `AFM_DIR` / `--dir` is set. The
`AFM_DIR` / `--dir` flag controls only where afm writes its **state** (flows, run-state,
logs).

Inside the container, the host-side launcher sets `AFM_DIR=/home/goga/pipeline` via the
container env-file and bind-mounts a host directory at that path read-write:

- Container path: `/home/goga/pipeline` (mounted read-write)
- Env-file: `AFM_DIR=/home/goga/pipeline`
- Host path: a deterministic, per-project, per-branch, per-flow directory under the
  launcher's host runtime state directory, with the shape
  `<runtime>/pipelines/<project>/<branch>/<flow>`.

`<project>` is the absolute project path (result of `Path.cwd().resolve()`) with the
leading slash removed and every remaining slash replaced by a hyphen — e.g.
`/Users/wb/IdeaProjects/my/project` → `Users-wb-IdeaProjects-my-project`.

`<branch>` is the current git branch (via `git rev-parse --abbrev-ref HEAD`), or the
literal `"default"` when git is unavailable, the directory is not a git repository, or
HEAD is detached.

State in this directory survives across runs of the same flow in the same project on the
same branch. Use the launcher's `--clean` flag to wipe the directory before launch.

The `AFM_DIR` variable is provided exclusively by the host-side launcher through the
env-file. The `client.command` tmpfile is generated per invocation and bind-mounted
read-only at `/home/goga/.afm/config.yaml` — this path is independent of `AFM_DIR` and
supplies the `client.command` overlay; the persistent directory mounted at
`/home/goga/pipeline` supplies the rest of afm state.

### Constraints

- Do not place afm state under `/workspace` — `/workspace` is the project directory;
  `/home/goga/pipeline` is afm's persistent state home inside the container.
- Do not delete the persistent directory in the host launcher's `finally` block — only
  the `client.command` tmpfile and env-file are deleted; state survives across runs.
- Do not set `AFM_DIR` via the image build (Dockerfile) — the host-side launcher owns
  the variable through the env-file so the path is deterministic per project, branch,
  and flow.
- Do NOT derive the `client.command` tmpfile mount target from `AFM_DIR` — `config.yaml`
  is always read from `~/.afm/config.yaml` (= `/home/goga/.afm/config.yaml` in the
  container), regardless of where `AFM_DIR` points.
