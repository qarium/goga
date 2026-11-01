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
`/home/goga/bin/codex-as-claude.sh`). In the goga integration the whole file is written
by the in-container run coordination before the afm launch: `client.command` carries the
wrapper resolved from the EFFECTIVE pipeline agent (the authored `pipeline.agent` as
amended by the in-container `amend_config` delivery); a bare agent name is never written.

`config.yaml` fields (YAML tags surfaced by the binary):

| Field           | Type   | Purpose                                                          |
|-----------------|--------|------------------------------------------------------------------|
| `client.command`| str    | Absolute in-container path of the `*-as-claude.sh` wrapper afm launches as the agent client (e.g. `/home/goga/bin/codex-as-claude.sh`) |
| `port`          | int    | Dashboard port (used when `afm run --port` is `0` or omitted)    |
| `idle_timeout`  | str    | Agent idle timeout (Go duration)                                 |
| `max_parallel`  | int    | Max parallel stages                                              |
| `prompts_dir`   | str    | Custom prompt directory. When set, afm reads the four agent prompts (`planning.md`, `implementation.md`, `review.md`, `summary.md`) from this directory instead of its built-in defaults. The goga in-container run coordination always writes `prompts_dir: /home/goga/pipeline/prompts` so afm uses the goga-managed prompt directory. |
| `proxy`         | map    | Outbound proxy settings. Surfaces at least `proxy.enabled: bool` — when `false`, afm does not use its own internal outbound proxy provider. The goga in-container run coordination always writes `proxy.enabled: false`: goga manages the outbound proxy through the container env-file (`HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`), so afm's own internal proxy provider must stay off to avoid the two layers colliding. |
| `server`        | str    | Server-side settings                                             |
| `open_browser`  | bool   | Whether afm opens the dashboard in a browser on start. The goga in-container run coordination always writes `open_browser: false`: the dashboard runs inside a container and is reached via the host-printed http://localhost:<port> URL, so an in-container browser launch has no effect. |
| `theme`         | str    | Dashboard theme name. The goga in-container run coordination always writes `theme: goga`. |

## Collaboration (afm v2.x)

afm offers a collaboration mechanism: helper agents attached to stages, run-level
team agents, delegation bounds, and a per-run helper task budget. Facts below are
recovered from the afm v2.x documentation (verified against the `v2.0.9` binary in
the image).

### Config layers and the kill-switch

Roles (profiles) live in `collaboration:` blocks of global `~/.afm/config.yaml` or
project `.afm/config.yaml`. Profiles with the same id in the project layer REPLACE
the global ones (union otherwise). `AFM_COLLABORATION=0` disables collaboration and
takes precedence over `collaboration.enabled` (default `true`); a flow CANNOT set
`collaboration.enabled`. When collaboration is disabled, declared helpers and unknown
profiles only produce warnings; `afm run`/`afm validate` proceed.

### `collaboration:` keys (config.yaml)

| Key | Type / values | Default | Notes |
|-----|---------------|---------|-------|
| `enabled` | bool | `true` | Overridden by `AFM_COLLABORATION=0`; flow cannot set it |
| `mode` | `team` \| `assistants` | `team` | Precedence flow > project > global; invalid values stop config loading |
| `max_depth` | int | `3` | `0` prevents helper creation; precedence flow > project > global; depth 1 = helper attached directly to a stage |
| `limits.max_tasks` | int | `20` | Lifetime budget counting every task of the run: helpers, run agents, and their children |
| `profiles` | map | — | Role definitions (below) |

A flow may override ONLY `max_depth` and `mode` (as a top-level `collaboration:`
block) — profiles and `limits` are config-layer-only.

### Profiles

Each profile requires its own `command` (it does NOT inherit `client.command`).
Keys: `title` (str), `command` (required), `instructions` (str), `delegate`
(bool, default `false`; `true` opts the role into child tasks, subject to depth and
`max_tasks`). On a native host only the Codex read-only adapter
(`codex-as-claude`) is accepted for helpers; inside a container any configured
command works.

### Stage helpers (flow-file `stages[].assistants`)

Accepts a bare profile name, one object, or a mixed list (list order preserved).
Object keys: `profile` (required) plus optional `title`, `instruction`, `mode`
(`advisory` | `required`), `trigger` (`one_shot` | `checkpoints` | `on_completion`).
Omitted `mode`/`trigger` default to `advisory`/`one_shot`. Helpers attach when the
stage enters execution (after plan approval when planned). Valid on execution stages
(including `[auto]`), NOT on `script:` or planning-only stages; each profile may
appear only once per stage. An unknown profile stops `afm run` at preflight; a
profile unavailable at attach time is logged and skipped. afm does not interpret a
`skills` key on assistant entries yet (unknown keys pass silently); support is on
the engine roadmap. Helpers, verify agents, and delegated tasks do NOT inherit the
author's skills.

### Verdict gating

`advisory` — result does not block the stage. `required` — the verdict must be
`pass` before the stage finishes; `needs_changes` and `inconclusive` do not pass the
gate; a human may waive with a recorded reason. Helper output contract: one JSON
object with `schema_version: 1` and `kind: "result"` (verdict + summary) or
`kind: "delegate"` (child tasks, delegate roles only); invalid output after repair
attempts yields `protocol_error`.

### Dashboard triggers

`one_shot` — runs once. `checkpoints` — observes the stage agent's output and can
run again at each checkpoint. `on_completion` — may run early, gets a final turn
when the result is ready. A helper attached while its stage is `pending` stays in
`waiting_parent` (does not start; a required one in that state can block stage
completion).

### Team / run agents (flow-file top-level `team:`)

Members are added in order before any stage starts (order decides `@name` suffixes
like `@qa-2`). Keys: `id` (required; "names the declaration, not the agent"; used to
recognize members on resume; must match `[A-Za-z0-9._-]`), `profile` (required when
collaboration is enabled; unknown stops preflight), `title` (required; the `@name`
derives from it; `@assistant` is reserved), optional `instruction`, `skills` (one
name or a list), `skills_dir`. Resume reuses existing members by `id`; changed
members keep their saved version with a warning; removed members persist until the
run ends. Run agents are standing roles, idle between turns; an idle agent never
keeps the run open.

### Dashboard modes

`team` — Team/Board views, People panel, "Add run agent", human task posting.
`assistants` — hides those; helpers live under their stages; Attach helper,
Assistant, stage Feed conversations, Message/Revise remain; `team:` agents still
start and can message/board.

### goga's stance (decided in `.goga/history/2026/support-afm-assistants/adr.md`)

- goga authors collaboration in the workflow-file only and delivers: flow-file parts
  (`collaboration: {mode: assistants}` always, `max_depth` when authored, `team`
  list, stage `assistants` entries) plus global-config plumbing
  (`collaboration.profiles.goga-<name>` = `{title, command, delegate}` only, and
  `collaboration.limits.max_tasks` when `delegation:` is authored).
- The compiled flow-file is the single source of truth for the config write —
  profiles are materialized exactly for the ids the flow references.
- goga never reads or writes `collaboration.enabled` / `AFM_COLLABORATION`; an
  environment that disables collaboration gets engine warnings and skipped helpers.

## Lifecycle hooks (afm v1.2.17+)

afm ships a lifecycle-hooks mechanism: observer commands afm launches on every flow
and stage transition of a run. goga consumes this mechanism — its bridge hook is
registered by the in-container run coordination on every launch (see "goga's stance"
below).

### Declaration layers

Hooks are declared at four layers; the effective hook list is the union of all:

| Layer | Location |
|---|---|
| global | `~/.afm/config.yaml` |
| project | `.afm/config.yaml` (project root) |
| flow | the flow-file root |
| stage | inside a single stage |

- Global, project, and flow hooks receive events from all stages; a stage hook
  receives only its own stage's events (flow-level events are rejected in a stage
  hook at parse time).
- `id` is unique within a layer; a duplicate `id` in a more specific layer REPLACES
  the one above (precedence `global < project < flow < stage`). The same `id` in two
  different stages is a config error.

### Hook entry fields

| Field | Type | Default | Purpose |
|---|---|---|---|
| `id` | str | — | Hook identity used in logs and diagnostics |
| `events` | `all` or list | — | Subscribed event names; `skip_events` subtracts from it; an unknown event name is a config error |
| `command` | str | — | Static command string; event values are never interpolated into it |
| `env` | map | — | Key = variable name the hook sees; value must be `file:PATH` (read and trimmed) or `env:NAME` (resolved from project `.afm/secrets.env` > global `~/.afm/secrets.env` > process env); plain literals are rejected; references resolve once before the flow starts; a missing variable, missing file, or empty value fails fast as a config error |
| `timeout` | duration | `30s` | Per-invocation timeout |
| `retries` | int | `0` | Retry count (0 = single attempt) |
| `inherit_env` | bool | `false` | `false` = minimal env (`PATH`, `HOME`, locale, temp dir, proxy/cert settings, plus the `AFM_*` variables and the resolved `env`); `true` adds the full afm process environment |

### Event catalog

- Flow: `flow_started`, `flow_resumed`, `flow_finished`, `flow_failed`,
  `flow_interrupted`
- Stage: `stage_planning_started`, `stage_plan_ready`, `stage_approved`,
  `stage_revision_started`, `stage_execution_started`, `stage_question_asked`,
  `stage_question_answered`, `stage_retry_scheduled`, `stage_retry_started`,
  `stage_paused`, `stage_resumed`, `stage_finished`, `stage_failed`
- Scripts (script stages and `script_before`/`script_after`):
  `stage_script_started`, `stage_script_finished`, `stage_script_failed`,
  `stage_script_before_started`, `stage_script_before_finished`,
  `stage_script_before_failed`, `stage_script_after_started`,
  `stage_script_after_finished`, `stage_script_after_failed`

`events: all` covers the public lifecycle catalog only — internal high-frequency
events (`agent_action`, `script_output`, event-loop wakeups) are not delivered.

### JSON payload (stdin)

Each invocation receives the full event as JSON on stdin:

| Field | Meaning |
|---|---|
| `schema_version` | `1` |
| `event_id` | Stable event identity (e.g. `<run-id>:transition:<n>:<event>`) — the recommended idempotency key |
| `event` | Event name |
| `occurred_at` | ISO-8601 UTC timestamp |
| `flow` | `{ name, run_id, resumed, run_dir, root_dir }` |
| `stage` | `{ id, name, from, to, phase }` — `from`/`to` are stage statuses; the block is absent for flow-level events |
| `reason` | Free-text cause, present when afm provides one |

### `AFM_*` environment

`AFM_HOOK_EVENT`, `AFM_HOOK_EVENT_ID`, `AFM_FLOW_NAME`, `AFM_RUN_ID`,
`AFM_RUN_DIR`, `AFM_ROOT_DIR`, `AFM_STAGE_ID`, `AFM_STAGE_NAME`, `AFM_STAGE_FROM`,
`AFM_STAGE_TO`. Stage variables are empty for flow-level events. `AFM_RUN_DIR` /
`AFM_ROOT_DIR` are absolute paths when set.

### Execution model

- The command runs via `sh -c` with CWD set to the flow's `root_dir`.
- Invocations of a single hook run sequentially (one consumer, in order); different
  hooks run in parallel.
- On clean flow exit afm waits a bounded time for the hook queue to drain; the
  terminal `flow_finished` / `flow_failed` event is emitted before that flush.

### Failure semantics and delivery guarantees

- Hooks are observers: a hook error never changes the FSM, a stage result, or the
  flow outcome.
- On ultimate failure (after timeout/retries) the error is written to the per-hook
  log — `.afm/runs/<run-id>/hooks/<hook-id>.log` — and a warning appears on the
  dashboard; the flow continues.
- Delivery is live best-effort: events not delivered before a crash are not replayed
  after restart (durable at-least-once redelivery is a planned afm-side feature).

### goga's stance

- The in-container run coordination writes the whole `~/.afm/config.yaml` on every
  launch — including goga's own hook entry in the global layer: `id: goga`,
  `command: python3 -m goga.pipeline hook`, `events: all`, `inherit_env: true`,
  afm-default timeout and retries. Always on; no user action or configuration
  involved.
- Consequence: manual global-layer hooks do not survive a goga launch — goga fully
  authors the global layer.
- `inherit_env: true` is deliberate: the hook process — and the goga subscriber
  hooks running inside it — inherits the afm process environment, including the
  launch env layers (env-file layers, the `pipeline.env` task layer, CLI `-e`
  entries). This carriage is accepted by design and documented; the bridge declares
  no `env` map of its own.
- Overridable id: a more specific layer (project, flow, stage) can replace goga's
  hook by id — afm's designed control point, documented as such.

### The future place for user-authored hooks

- Today user-authored hooks belong in the project layer — `.afm/config.yaml` in the
  project root — which goga never touches and afm unions natively.
- The flow-file layers are the future authoring surface for the goga pipeline
  compiler. Context-formation considerations: a user-authored hook receives the raw
  afm payload vocabulary; a future authoring task decides how much of goga's bridged
  context formation (pipeline identity, goga-idiomatic names) is offered to user
  hooks — extending the mechanism instead of reworking it.

#### Constraints

- Do not declare goga's bridge hook anywhere but the global layer goga authors.
- Do not rely on manual hooks surviving in `~/.afm/config.yaml` — the file is fully
  rewritten on every goga launch.
- Do not treat a hook failure as a run failure — observer semantics hold end-to-end
  on the goga side as well.

## Directory layout afm expects

```
~/.afm/
├── config.yaml                # optional; afm falls back to defaults when missing
└── flows/                     # flow *.yaml files discovered by `afm list`
```

## Per-stage command override (flow-file)

afm honors a per-stage `command:` field inside each stage of a flow-file. When a stage carries `command:`, afm uses that wrapper for the stage instead of the global `client.command` from `~/.afm/config.yaml`. The value follows the same convention as `client.command` — an absolute in-container path to a `*-as-claude.sh` wrapper (e.g. `/home/goga/bin/codex-as-claude.sh`).

The override is per-stage only; stages without `command:` keep using the global `client.command`. This lets a single flow route different stages to different agents (planning with claude, review with codex, etc.) without modifying the launcher-side config.yaml.

The goga in-container run coordination writes the global `client.command` into `~/.afm/config.yaml` — it serves as the default for every stage that does not override. Per-stage overrides are authored by the goga workflow layer: they appear in the serialized flow-file as a stage field.

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
The launch context splits along the docker boundary: the host owns the launch mechanics,
the container owns the run parameters.

The host does:

1. Pick a free localhost port (bind a `socket` to `("", 0)`, read the assigned port,
   close it, and hand the same value to both `-p <port>:<port>` and
   `afm run --port <port>`).
2. Mount NO afm config overlay — the host generates and mounts no `config.yaml`
   at all; the whole file is written in-container (step 3). The env-file carries
   the launch base layers only (see "Environment carriage" below).
3. `docker run --rm -p <port>:<port> -v <project_dir>:/workspace
   -w /workspace --env-file <env_file> <image> <in-container entrypoint>`

   The entrypoint (the in-container run coordination) performs the load-and-amend of
   the project configuration, writes the whole `~/.afm/config.yaml` before launching
   afm, and then invokes `afm run --port <port> <flow_path>`. The written file
   carries `client.command: /home/goga/bin/<agent>-as-claude.sh` (an absolute
   in-container wrapper path matching the `*-as-claude.sh` convention, resolved from
   the EFFECTIVE pipeline agent; written only when an agent resolves — omitted
   otherwise so per-stage workflow agents or afm's own defaults cover the absent
   global default), plus four static constants — `theme: goga` (dashboard theme),
   `open_browser: false` (the dashboard is reached via the host-printed
   http://localhost:<port> URL; afm must not attempt to open a browser inside
   the container), `proxy.enabled: false` (afm's own internal outbound proxy
   provider is disabled — goga manages the outbound proxy through the container
   env-file `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`, the two layers must never
   collide), and `prompts_dir: /home/goga/pipeline/prompts` (the in-container
   prompts directory — afm reads four prompt files from this directory,
   `planning.md`, `implementation.md`, `review.md`, `summary.md`, instead of
   its built-in defaults; written unconditionally so afm uses the goga-managed
   prompt directory regardless of whether the pipeline-file customizes any
   prompt).

   The launcher adds no credential mounts. A user who wants credentials inside the container
   mounts them through the home configuration (`docker.run` volume tokens) or passes
   environment variables — see the `docker-auth-mounts` user guide.
4. Forward `SIGTERM` / `SIGINT` to the container, kill it in `finally`, and propagate
   afm's exit code as the launcher's exit code.

### Environment carriage

The container env-file carries the launch base layers only: `home.env`, git identity,
the CLI `-e` entries, and the engine variables (`AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`,
`HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`). The task env layer (the domain's effective env
mapping, e.g. `pipeline.env`) is NOT written into the env-file — it is applied
in-container, around the target binary's launch only, above the inherited launch env
and below the CLI layer.

Because docker `--env-file` flattens layers, the CLI `-e` entries additionally travel
as a distinguishable payload variable (the `AFM_DOCKER_FILE_ROOTS` precedent — a
dedicated engine variable carrying a structured payload) so the in-container side can
apply them ABOVE the task env layer; the same values stay in the env-file — one source,
same values in both places. The payload travels as the dedicated engine variable
`GOGA_EXTRA_ENV` (standard base64 of a compact JSON mapping) — the carriage contract of
the goga/docker cell; the rule fixed here is the ladder: explicit CLI input wins
over config and tool amendments, and engine variables are launch mechanics nothing
overrides.

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
  `/workspace` is the user's project directory; `~/.afm/` is afm's home. The
  in-container coordination writes `config.yaml` to `/home/goga/.afm/config.yaml`;
  the host launcher mounts no config overlay.
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
env-file. The `~/.afm/config.yaml` file (with `client.command`) is written in-container
by the run coordination at `/home/goga/.afm/config.yaml` — this path is independent of
`AFM_DIR`; the persistent directory mounted at `/home/goga/pipeline` supplies the rest
of afm state.

### Constraints

- Do not place afm state under `/workspace` — `/workspace` is the project directory;
  `/home/goga/pipeline` is afm's persistent state home inside the container.
- Do not delete the persistent directory in the host launcher's `finally` block — only
  the env-file is deleted; state survives across runs.
- Do not set `AFM_DIR` via the image build (Dockerfile) — the host-side launcher owns
  the variable through the env-file so the path is deterministic per project, branch,
  and flow.
- Do NOT relocate `config.yaml` — it is always read from `~/.afm/config.yaml`
  (= `/home/goga/.afm/config.yaml` in the container), regardless of where `AFM_DIR`
  points; the in-container write targets exactly this path.

## File manager roots via AFM_DOCKER_FILE_ROOTS

afm's dashboard file manager displays the directories the user may browse. The set is
delivered through the `AFM_DOCKER_FILE_ROOTS` environment variable — a standard base64
string (with padding) of a compact UTF-8 JSON object:

    {"version":1,"roots":[{"id":"...","label":"...","container_path":"...","mount_read_only":false,"kind":"project"}]}

- `version` — always `1`
- `id` — a stable identifier, unique within the list (`"project"` for the project root)
- `label` — display name: `"project"` for the project root; the full `container_path`
  for extra roots
- `container_path` — the in-container mount target
- `mount_read_only` — whether the mount is read-only
- `kind` — `"project"` (the project root) or `"extra"` (a directory mount resolved
  from `home.docker.run` `-v` tokens)

The producer is the host-side run launcher: it writes the variable into the run
env-file from the ACTUAL mounts of the launch, so the payload and the `-v` mounts never
diverge. The Dockerfile carries only a static image default; the run env-file overrides
it on every launch, and an explicit user `-e AFM_DOCKER_FILE_ROOTS=...` wins over both
(env-file last-write-wins semantics).

Scope of roots: every mounted volumes-directory except afm state — the project root
`/workspace` plus extra directories from `home.docker.run` `-v` tokens whose host part
exists as a directory. Named volumes, file mounts, credentials, and the persistent afm
state directory are not user file roots and never appear.

### Constraints

- The info forms (list/overview/card) receive no `AFM_DOCKER_FILE_ROOTS` — no dashboard
  is started there; the image default stays in effect by design.
- Do not add new goga config surface for extra roots — `home.docker.run` is the single
  source.
- goga is the producer of the contract; how afm parses and renders the variable is
  afm's own concern (external binary, separate repository).
