# Architecture plan — Split the run context from the host launch context (pipeline and build)

## Topic

**Split the run context from the host launch context (pipeline and build)** — the in-container
load-and-amend, the afm `config.yaml` authorship move, the fixed env ladder with the CLI `-e`
dual carriage (`GOGA_EXTRA_ENV`), and the guard split.

Plan file: `.goga/history/2026/fix-pipeline-context/arch.md` (the path printed by
`goga history path -f arch.md`). Source task: `.goga/history/2026/fix-pipeline-context/task.md`;
accepted ADR: `.goga/history/2026/fix-pipeline-context/adr.md`.

The final content of every artifact below was assembled and verified against the DSL before this
plan was written: `goga lint` reports **83 cells, 0 errors** on the assembled state. Each
modified artifact is specified as a unified diff (`a/` = the current project file, `b/` = the
target state); the one new artifact is given in full. The plan contains only CODEMANIFEST and
`.usages/` artifacts — no implementation code.

## Implementation Order

Ordered leaves to root — each cell's imports must exist before the cell that references them:

1. **`goga/docker`** (modified) — boundary leaf (its only project dep is `goga/version`, untouched).
   The two carriage routines (`encode_extra_env`, `decode_extra_env`) land first: all four other
   cells import them. Its consumer practice `extra-env-carriage.md` lands with the cell.
2. **`goga/afm`** (modified) — leaf without project deps. The `run_flow` env parameter lands
   before the pipeline caller that passes the composed layer.
3. **`goga/config/hooks` + `goga/config` + `goga/config/project`** (documentation artifacts) —
   the two practice rewrites land before the cells whose contracts restate the
   one-action-two-moments rule; the `amend_config` CODEMANIFEST contracts are unchanged.
   The `goga/config/project` touch-up rewrites two `PipelineConfig` property annotations
   that still name the retired host-side flow (the tmpfile write, the env-file carriage
   of `pipeline.env`) — contract-neutral, same group.
4. **`goga/pipeline`** (modified) — depends on `goga/docker` (decode), `goga/afm` (run_flow env),
   `goga/agents` (wrapper path), `goga/config` (load), `goga/config/hooks` (types). Gains
   `write_afm_config` and the reworked `run_pipeline`; the `registering-hooks` practice
   gains the configuration load-or-delivery failure line and the afm-configuration-write
   ordering in the `run_created` row.
5. **`goga/build`** (modified) — depends on `goga/docker` (decode), `goga/config` (load),
   `goga/config/hooks` (types), `goga/agents` and `goga/ralphex` (existing, unchanged).
   `main` gains the load-and-amend; `build` gains the early agent guard and the pass env ladder.
6. **`goga/commands/pipeline`** (modified) — host root; depends on `goga/docker` (encode). Its
   runtime boundary to `goga/pipeline` is docker only (no Python imports either way).
7. **`goga/commands/build`** (modified) — host root; depends on `goga/docker` (encode). Its
   runtime boundary to `goga/build` is docker only.

## Artifacts

Every artifact below is a modification of an existing file unless marked **create**. Diffs are
unified (`--- a/<path>` current state, `+++ b/<path>` target state); apply them wholesale per
file. The target state of the whole set was lint-verified (0 errors) before this plan was issued.

### Cell: goga/docker — modified

#### CODEMANIFEST: `goga/docker/CODEMANIFEST`

````diff
--- a/goga/docker/CODEMANIFEST
+++ b/goga/docker/CODEMANIFEST
@@ -69,6 +69,16 @@
   for the check contract, the outcome matrix, and the escape environment
   variable.
 
+  The zone also owns the engine-variable carriage of the CLI environment
+  entries across the docker boundary: one routine turns the raw CLI entries
+  into the single-line payload of the dedicated engine variable, the other
+  turns the payload back into the mapping a domain launch applies above its
+  task env layer. Both routines are pure — the entry source belongs to the
+  calling launcher, the application belongs to the consuming domain launch.
+  The consumer wiring of both halves — the env-file ordering, the ladder,
+  the one-source rule — lives in the extra-env-carriage practice of this
+  cell's usages directory.
+
 ---
 
 "ensure_in_docker()":
@@ -105,6 +115,66 @@
     - Do NOT return an error value — the routine returns only in the in-container
       case; the host case terminates the process
 
+"encode_extra_env(entries: list[str]) -> value: str":
+  location: extra_env.py
+  annotations: |
+    Encode the CLI environment entries into the engine payload value carried
+    across the docker boundary in the container env-file.
+
+    `entries`: raw KEY=VALUE strings of the CLI environment option, verbatim
+    `value`: the single-line payload string for the dedicated engine variable
+
+    Apply `convention` for docstring style and intra-package imports.
+
+    Algorithm:
+    1. Split every entry at the first key-value separator; an entry without
+       a separator is skipped silently — no validation, no warning
+    2. Keep the later entry when a key repeats — the same last-wins rule the
+       env-file applies
+    3. Serialize the resolved mapping as compact JSON without whitespace
+    4. Encode as standard base64 with padding into a single line and return it
+
+    Requirements:
+    - Deterministic — identical entries produce the identical value
+    - The value decodes back into exactly the resolved mapping
+    - Pure — no filesystem access, no environment reads, no side effects
+
+    Constraints:
+    - Do not validate or reject entries — malformed input travels as it
+      arrived; the routine neither fails nor warns
+    - Do not read the environment — the caller owns the entry source
+
+"decode_extra_env(value: str) -> entries: dict[str, str]":
+  location: extra_env.py
+  annotations: |
+    Decode the engine payload value back into the CLI environment mapping a
+    domain launch applies above its task env layer.
+
+    `value`: the payload string of the dedicated engine variable; an absent
+             or empty variable arrives as an empty string
+    `entries`: the decoded CLI environment mapping; empty when the payload
+               carried nothing
+
+    Apply `convention` for docstring style and intra-package imports.
+
+    Algorithm:
+    1. An empty `value` resolves to an empty mapping — nothing to apply
+    2. Decode the base64 payload and parse the JSON mapping inside
+    3. A payload that fails decoding or parsing, or carries a non-string
+       value, raises one clean error naming the engine variable — no payload
+       content appears in the error
+
+    Requirements:
+    - Pure — the mapping is returned, nothing is applied anywhere
+    - The result equals the mapping `encode_extra_env` produced from the
+      same entries
+
+    Constraints:
+    - Do not read the environment — the caller owns the variable read
+    - Do not print or log the payload or any decoded value
+    - Do not apply the mapping to any environment — application belongs to
+      the consuming domain launch
+
 "DockerBuilder(image: str, dockerfile: str = 'Dockerfile', context: str = '.')":
   location: builder.py
   annotations: |
@@ -431,7 +501,9 @@
 Description: |
   Seed-cell with a declared responsibility zone — everything related to Docker in
   the project: in-container environment assertions, container launching, image
-  building, and reading the goga package version inside an image. The body holds
+  building, reading the goga package version inside an image, and the
+  engine-variable carriage of the CLI environment entries across the docker
+  boundary. The body holds
   the guard routine `ensure_in_docker`; the stateful `DockerBuilder` plus the
   `docker_pull`, `docker_update`, and `docker_build_if_not_exist` routines
   (image acquisition — `docker_update` refreshes under `--update`: build when a
````

#### practice (create): `goga/docker/.usages/extra-env-carriage.md` — **create**, full content

````markdown
# The CLI environment carriage across the docker boundary

How a domain threads the CLI environment entries (the repeatable `-e/--env`
option) across the docker launch boundary. For the host-side launchers that
write the container env-file (`goga/commands/pipeline`, `goga/commands/build`)
and the in-container domain launches that compose the target binary's
environment (`goga/pipeline`, `goga/build`).

## The carriage contract

The docker `--env-file` flattens every layer into one file, so the CLI entries
cannot be recognized on the container side once they land in it. The carriage
therefore travels twice, from one source:

- the env-file carries the raw `KEY=VALUE` lines verbatim — every reader of
  the inherited environment keeps seeing them;
- the dedicated engine variable `GOGA_EXTRA_ENV` carries the encoded form of
  the same entries — the value produced by `encode_extra_env` — so the
  container side can apply them as a distinguishable layer.

Both places compose from the same parsed CLI values on every launch; they
never diverge. Write the variable on every launch that writes the CLI lines.

## The environment ladder

The layers, lowest to highest, in both domains:

    home.env < git identity < task env layer (effective) < CLI -e < engine variables

Engine variables — `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`,
`HTTPS_PROXY`, `NO_PROXY` — are launch mechanics: nothing overrides them. In
the env-file they are written after the CLI lines; in the container the launch
composition drops a task-layer or CLI key that collides with one, silently —
the inherited launch value stands, with no warning.

## Host half — write the env-file and the payload

The launcher writes the env-file in ladder order and appends the payload line
built from the same entries:

```python
from goga.docker import encode_extra_env

env_file_lines = [
    *home_env_lines,          # home.env — the base layer
    *git_identity_lines,      # git identity
    *extra_env,               # the raw CLI entries, verbatim
    *engine_variable_lines,   # AFM_DIR, AFM_DOCKER_FILE_ROOTS, proxy — last
    f"GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}",
]
```

- The CLI lines and the payload come from the same tuple — never parse,
  filter, or re-format one of them independently of the other.
- The engine variables are written after the CLI lines so the env-file itself
  respects the ladder.

## Container half — decode and apply above the task env layer

The domain launch decodes the payload once and applies it above its effective
task env layer, for the target binary's launch only:

```python
import os
from goga.docker import decode_extra_env

payload = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))
merged = {**effective_task_env, **payload}      # CLI wins on key conflict
launch_layer = {k: v for k, v in merged.items() if k not in ENGINE_KEYS}
run_target(env=launch_layer)
```

- The task env layer is the domain's effective env mapping (for example
  `pipeline.env`); the payload wins on key conflict — explicit CLI input beats
  configuration and tool amendments.
- Keys colliding with the engine variables are dropped before the launch; the
  inherited launch values are never overridden.
- The layer applies to the target binary's subprocess only — the container's
  process environment stays untouched.
- The payload and the layer values are never printed or logged; a damaged
  payload fails as one clean error naming the variable — nothing partially
  applied, the target binary never launches.

````

### Cell: goga/afm — modified

#### CODEMANIFEST: `goga/afm/CODEMANIFEST`

````diff
--- a/goga/afm/CODEMANIFEST
+++ b/goga/afm/CODEMANIFEST
@@ -22,9 +22,14 @@
   The standard library subprocess and pathlib.Path modules are used for invoking
   the binary and receiving arguments.
 
+  The launcher inherits the process environment for the afm subprocess; an
+  optional env layer (dict of strings), supplied by the caller, is applied on
+  top of the inherited environment for that subprocess only. The layer is
+  never logged and never printed (secret-safe).
+
 ---
 
-"run_flow(flow_path: Path, port: int, max_parallel: int | None = None) -> exit_code: int":
+"run_flow(flow_path: Path, port: int, max_parallel: int | None = None, env: dict[str, str] | None = None) -> exit_code: int":
   location: run_flow.py
   annotations: |
     Launch the external `afm` binary to run the pipeline file at the given
@@ -40,21 +45,30 @@
                     When None — the "--max-parallel" flag is OMITTED and afm
                     applies its own default. Decided by
                     the caller; `run_flow` only passes it through.
+    `env`: optional environment layer applied on top of the inherited process
+           environment for the afm subprocess only — composed by the caller
+           (the run coordination) as the effective task env layer with the CLI
+           entries applied above it. None or an empty mapping means the
+           inherited environment unchanged. Never logged, never printed.
     `exit_code`: 0 on success, 127 when afm is missing from PATH, 126 when afm
                  is present but not executable (other OSError), otherwise afm's
                  own exit code
 
     Algorithm:
-    1. Receive `flow_path` (absolute), `port` (integer), and the optional
-       `max_parallel`
-    2. Invoke "afm run" via the `afm` practice with --port <port>, the absolute
-       `flow_path` as positional argument, and — when `max_parallel` is not None
-       — the --max-parallel <max_parallel> flag; resolve afm through PATH
-    3. On binary-not-found (FileNotFoundError, per the `afm` practice) — return
+    1. Receive `flow_path` (absolute), `port` (integer), the optional
+       `max_parallel`, and the optional `env` layer
+    2. Compose the afm subprocess environment: start from the inherited
+       process environment and apply the `env` layer on top for this
+       subprocess only — the caller's own process environment stays untouched
+    3. Invoke "afm run" via the `afm` practice with --port <port>, the absolute
+       `flow_path` as positional argument, — when `max_parallel` is not None —
+       the --max-parallel <max_parallel> flag, and the composed environment;
+       resolve afm through PATH
+    4. On binary-not-found (FileNotFoundError, per the `afm` practice) — return
        `exit_code` 127 with a clear message
-    4. On other OSError (present but not executable, permission denied, etc.) —
+    5. On other OSError (present but not executable, permission denied, etc.) —
        return `exit_code` 126 with a clear message
-    5. Return afm's exit code as `exit_code`
+    6. Return afm's exit code as `exit_code`
 
     Apply the `conventions` practice for error-handling style and docstring formatting.
 
@@ -65,6 +79,9 @@
     - Forward `max_parallel` via --max-parallel ONLY when it is not None — None
       means "do not limit" and MUST omit the flag (never substitute a default
       such as 0)
+    - Apply the `env` layer for the afm subprocess only — never write it into
+      the caller's process environment
+    - Never print or log any value of the `env` layer
     - Invoke afm through PATH — do not hard-code /srv/afm
     - Apply the `afm` practice's error-handling rules verbatim
     - Accept absolute paths only; do not resolve or construct paths internally
@@ -74,6 +91,8 @@
     - Do not allocate the port — the caller allocates it
     - Do not decide or default `max_parallel` — the caller decides; None ⇒ omit
       the flag, never infer a value
+    - Do not compose the layer — the caller owns the layer composition; this
+      routine only applies what it receives
     - Do not discover pipeline files — discovery is the caller's concern
     - Do not hard-code the afm binary path — rely on PATH inside the container
     - Do not modify or parse pipeline-file contents
````

#### practice: `goga/afm/.usages/run-flow.md`

````diff
--- a/goga/afm/.usages/run-flow.md
+++ b/goga/afm/.usages/run-flow.md
@@ -2,12 +2,13 @@
 
 `run_flow` is the goga-side entry point to the external `afm` binary. It invokes
 `afm run` with an absolute flow-file path and a dashboard port, optionally
-capping concurrency, and propagates the subprocess exit code. It performs no
-discovery, path resolution, or port allocation — those live in other cells.
+capping concurrency and applying an environment layer for the subprocess, and
+propagates the subprocess exit code. It performs no discovery, path resolution,
+or port allocation — those live in other cells.
 
 ## Signature
 
-run_flow(flow_path: Path, port: int, max_parallel: int | None = None) -> exit_code: int
+run_flow(flow_path: Path, port: int, max_parallel: int | None = None, env: dict[str, str] | None = None) -> exit_code: int
 
 ## Parameters
 
@@ -20,6 +21,12 @@
   (default), the `--max-parallel` flag is OMITTED and afm applies its own
   default. Decided by the caller; `run_flow` only forwards
   it.
+- `env` — optional environment layer applied on top of the inherited process
+  environment for the afm subprocess only. Composed by the caller (the
+  in-container run coordination): the effective task env layer (`pipeline.env`)
+  with the CLI `-e` entries applied above it. `None` and an empty mapping both
+  mean "inherited environment unchanged". Secret-safe: never logged, never
+  printed.
 
 ## Returns
 
@@ -33,6 +40,17 @@
 `run_flow`, where it becomes the omission of `--max-parallel` — afm then runs
 unbounded (its default). Never substitute a default value for None.
 
+## Environment layer contract
+
+The optional `env` layer is applied on top of the inherited process
+environment for the afm subprocess only — never to the caller's own
+environment. The caller (the in-container run coordination) composes the
+layer: the effective task env layer (`pipeline.env`) with the CLI `-e` entries
+applied above it, engine-variable keys dropped. `None` and an empty mapping
+both mean "inherited environment unchanged". The layer values are
+secret-safe: never logged, never printed, never included in any diagnostic
+output.
+
 ## Error handling
 
 `FileNotFoundError` ⇒ exit code 127 (afm missing from PATH); other `OSError` ⇒
@@ -44,4 +62,6 @@
 - Do not pass a flow name instead of an absolute path — afm treats the argument
   as a path.
 - Do not default `max_parallel` to 0 or any value — None means "omit the flag".
+- Do not compose the layer here — the caller owns the composition; `run_flow`
+  only applies what it receives.
 - Do not resolve paths or allocate ports here — those are the caller's jobs.
````

### Cell: goga/config/hooks (documentation-only) — modified (usage only)

#### practice: `goga/config/hooks/.usages/checkpoints.md`

````diff
--- a/goga/config/hooks/.usages/checkpoints.md
+++ b/goga/config/hooks/.usages/checkpoints.md
@@ -3,7 +3,8 @@
 How the config-consuming operations use the hooks zone of the config
 domain: delivering the amendment checkpoint at the project-configuration
 load moment and consuming the effective configuration. For every
-host-side command and config-driven module that loads .goga/config.yml.
+config-consuming surface — the host-side commands and the in-container
+entrypoints alike.
 
 ## The checkpoint surface
 
@@ -54,9 +55,25 @@
 - Values never appear in the summary — the lines carry the tool, the path,
   and set or forced only.
 
-## In-container loads stay authored-only
+## One action, two moments
 
-The in-container entry points (`python -m goga.build` and any in-container
-pipeline counterpart) load the authored configuration directly and
-deliver no checkpoint — in-container loading is the correct behavior for
-the build and pipeline domains.
+The checkpoint is not split by environment: the same action, the same path
+vocabulary, and the same amendment semantics deliver at every load moment —
+the host-side commands (goga/commands/pipeline, goga/commands/build) and the
+in-container entrypoints (the pipeline run coordination, the build
+entrypoint) alike.
+
+Each side consumes only the fields it owns:
+
+- the host consumes the docker-level launch fields — image, dockerfile,
+  proxy, hosts — and runs the structural section guards on its effective
+  configuration;
+- the container consumes the run-parameter fields — the task env layers and
+  the agent values — for everything downstream of its load.
+
+A contribution into the other side's fields stays applied but unconsumed —
+silently. No warning fires, no error is raised; the amendment summary lines
+are the only visibility. Both delivery moments share the hard failure
+semantics: the first failing tool stops the command with a clean error naming
+the tool and the action, and the target binary (afm / ralphex) never
+launches.
````

### Cell: goga/config (facade documentation) — modified (usage only)

#### practice: `goga/config/.usages/registering-hooks.md`

````diff
--- a/goga/config/.usages/registering-hooks.md
+++ b/goga/config/.usages/registering-hooks.md
@@ -12,7 +12,7 @@
 
 | Address | Error class | Fires |
 |---|---|---|
-| `config / amend_config` | hard | At the project-configuration load moment of every host-side command that loads `.goga/config.yml` (pipeline, lint, contract, install, config, build, topics, usages status, usages sync). In-container loads stay authored-only and fire nothing. |
+| `config / amend_config` | hard | At the project-configuration load moment of every config-consuming surface — the host-side commands that load `.goga/config.yml` (pipeline, lint, contract, install, config, build, topics, usages status, usages sync) and the in-container entrypoints (the pipeline run coordination, the build entrypoint). |
 
 A failing moment fires nothing: a missing or structurally invalid
 configuration file fails in the loader before the checkpoint.
````

### Cell: goga/config/project — modified (property annotations only)

#### CODEMANIFEST: `goga/config/project/CODEMANIFEST`

Contract-neutral touch-up: two `PipelineConfig` property annotations still describe the
retired host-side flow — the agent resolved by `goga/commands/pipeline` into the
afm-config tmpfile, and `pipeline.env` "passed to the container" through the launch.
After this plan both statements are false; the annotations move to the in-container
consumer and the in-container application point.

````diff
--- a/goga/config/project/CODEMANIFEST
+++ b/goga/config/project/CODEMANIFEST
@@ -418,13 +418,15 @@
       AI executor identifier — agent name as declared in the goga Docker image
       (e.g. "claude", "codex", "opencode", or any other name matching the
       /home/goga/bin/<agent>-as-claude.sh wrapper convention). Resolved at
-      runtime by the consumer (goga/commands/pipeline) into an absolute
-      wrapper path written into the afm-config tmpfile; this cell does no
-      resolution or validation of the value.
+      runtime by the in-container consumer (goga/pipeline) into an absolute
+      wrapper path written into the afm configuration file; this cell does
+      no resolution or validation of the value.
       Optional — None when the agent is not configured in .goga/config.yml.
     "env -> dict": |
       Environment variable dictionary ({str: str}).
-      Passed to the container at pipeline run time.
+      Applied in-container as the afm launch env layer, above the inherited
+      launch environment; it never travels through the docker launch
+      env-file.
       Optional — defaults to an empty dict.
     "proxy -> str | None": |
       Optional HTTP/HTTPS proxy URL for the pipeline container.
````

### Cell: goga/pipeline — modified

#### CODEMANIFEST: `goga/pipeline/CODEMANIFEST`

````diff
--- a/goga/pipeline/CODEMANIFEST
+++ b/goga/pipeline/CODEMANIFEST
@@ -17,8 +17,10 @@
     From: goga/afm
   - Types:
       - ensure_in_docker
+      - decode_extra_env
     Usages:
       - ensure-in-docker
+      - extra-env-carriage
     From: goga/docker
   - Types:
       - parse_workflow
@@ -30,8 +32,20 @@
     From: goga/pipeline/workflow
   - Types:
       - resolve_project_name
+      - load_project_config
+    Usages:
+      - project-configuration
     From: goga/config
   - Types:
+      - ConfigHooks
+      - ConfigOverlay
+    From: goga/config/hooks
+  - Types:
+      - resolve_wrapper_path
+    Usages:
+      - resolve-wrapper-path
+    From: goga/agents
+  - Types:
       - PipelineHooks
       - PipelineIdentity
       - WorkflowDecision
@@ -53,6 +67,7 @@
 
 Usages:
   convention: .goga/usages/conventions.md
+  afm: .goga/usages/cooks/afm.md
   argparse: |
     Use the standard library argparse module for in-container CLI parsing.
     Two subcommands: list (with an optional --info flag) and run (a required
@@ -151,6 +166,23 @@
   the work identity and the `topic-statuses` practice for the status facts
   of the run events.
 
+  The run coordination owns the in-container run parameters: the opening
+  load-and-amend of the project configuration (the effective configuration
+  feeds everything downstream), the afm configuration authorship, and the
+  launch environment composition around the afm launch. The config amendment
+  delivery of the load moment follows the one-action-two-moments rule — the
+  same action, vocabulary, and semantics as the host delivery; each side
+  consumes only the fields it owns. Use `project-configuration` for the
+  authored load, `afm` for the written
+  configuration-file contract, `resolve-wrapper-path` for the agent command
+  resolution, and `extra-env-carriage` for the CLI entries carriage of the
+  launch layer.
+
+  The listing, overview, and card forms load no configuration and deliver no
+  checkpoint — only the run form performs the load-and-amend. Docker-level
+  fields of the effective configuration (image, proxy, hosts) are
+  applied-but-unconsumed in-container — silently, summary lines only.
+
   The cell runs inside the goga Docker image when invoked through
   python -m goga.pipeline; the host-side launcher lives in
   goga/commands/pipeline (docker runtime boundary — no Python Imports).
@@ -546,19 +578,21 @@
 "run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int, workflow: str | None = None, no_workflow: bool = False, skip: list[str] | None = None, parallel: int | None = None) -> exit_code: int":
   location: run_pipeline.py
   annotations: |
-    Resolve a pipeline name to an absolute file path via `list_pipelines`,
-    resolve an optional workflow via `resolve_workflow` from the CLI-provided
-    decision, merge the CLI skip names via `apply_skip_stages`, deliver the
-    workflow amendment through the pipeline hooks zone,
-    compile the pipeline-file (extended by the effective workflow) into an
-    afm flow-file at runtime via `compile_flow`, materialize the four
-    agent prompt files (defaults plus inline overrides) into the runtime
-    prompts directory, emit the run-creation facts, launch afm through
-    `run_flow`, and emit the run-completion facts on its return. This is the
-    run coordination routine — it performs discovery, workflow resolution,
-    path resolution, fact resolution, amendment delivery, compilation, and
-    prompt materialization; the actual subprocess execution lives in
-    `run_flow`.
+    Load and amend the project configuration, resolve a pipeline name to an
+    absolute file path via `list_pipelines`, resolve an optional workflow via
+    `resolve_workflow` from the CLI-provided decision, merge the CLI skip
+    names via `apply_skip_stages`, deliver the workflow amendment through the
+    pipeline hooks zone, compile the pipeline-file (extended by the effective
+    workflow) into an afm flow-file at runtime via `compile_flow`, materialize
+    the four agent prompt files (defaults plus inline overrides) into the
+    runtime prompts directory, write the afm configuration file via
+    `write_afm_config`, emit the run-creation facts, launch afm through
+    `run_flow` with the composed launch environment layer, and emit the
+    run-completion facts on its return. This is the run coordination routine
+    — it performs the configuration load-and-amend, discovery, workflow
+    resolution, path resolution, fact resolution, amendment delivery,
+    compilation, prompt materialization, and afm configuration authorship;
+    the actual subprocess execution lives in `run_flow`.
 
     `name`: pipeline name without extension
     `project_dir`: project-level pipelines directory (same meaning as in `list_pipelines`)
@@ -578,91 +612,125 @@
                 the in-container CLI --parallel flag
     `exit_code`: 0 on success, non-zero on error (missing pipeline, missing
                  binary, afm failure, structural DSL error, workflow parse
-                 error, materialization error). 127 means afm is not on PATH
-                 inside the container.
+                 error, materialization error, configuration load or delivery
+                 failure). 127 means afm is not on PATH inside the container.
 
     Apply `convention` for error-handling style and docstring formatting.
+    Apply `project-configuration` for the authored configuration load.
+    Apply `checkpoints` for the workflow amendment delivery and the two
+    emissions of the pipeline hooks zone.
     Apply `parse-workflow` for the workflow-file contract consumed through
     `resolve_workflow`.
     Apply `compile-flow` for the compilation step contract and the documents
     tuple.
     Apply `default_prompts` for resolving the packaged default prompt files.
-    Apply `run-flow` for the subprocess launch contract.
-    Apply `checkpoints` for the amendment delivery and the two emissions of
-    the pipeline hooks zone.
+    Apply `afm` for the written afm configuration-file contract.
+    Apply `resolve-wrapper-path` for the agent command resolution inside
+    `write_afm_config`.
+    Apply `run-flow` for the subprocess launch contract and its environment
+    layer parameter.
+    Apply `extra-env-carriage` for the CLI entries carriage of the launch
+    layer.
     Apply `topic-paths` for the work identity resolution and
     `topic-statuses` for the status facts of the run events.
 
     Algorithm:
-    1. Discover pipelines via `list_pipelines` and find the entry whose name
+    1. Load the authored project configuration via `load_project_config` —
+       a load failure returns with a clean error before any work; no events
+       fire
+    2. Deliver the config amendment via the `ConfigHooks` checkpoint surface
+       with the authored configuration — the first failing tool stops the
+       run with a clean error naming the tool and the action (no events
+       fire, afm never launches); print the amendment summary lines of the
+       `ConfigOverlay` to stderr; every downstream step consumes the
+       effective configuration of the `ConfigOverlay`
+    3. Discover pipelines via `list_pipelines` and find the entry whose name
        matches
-    2. If no match — report that the pipeline is missing and return a
+    4. If no match — report that the pipeline is missing and return a
        non-zero exit code
-    3. Build the absolute pipeline path from the matching entry's source
+    5. Build the absolute pipeline path from the matching entry's source
        directory and the pipeline name
-    4. Resolve the in-container runtime directory from the AFM_DIR
+    6. Resolve the in-container runtime directory from the AFM_DIR
        environment variable; when unset raise a readable "AFM_DIR not set"
        error; resolve the value to an absolute path
-    5. Compose the output flow path inside that directory
-    6. Resolve the workflow via `resolve_workflow` with the pipeline name and
+    7. Compose the output flow path inside that directory
+    8. Resolve the workflow via `resolve_workflow` with the pipeline name and
        the `workflow` / `no_workflow` parameters — the CLI decision arrives
        as explicit arguments, never from the environment
-    7. Apply the `skip` names via `apply_skip_stages` onto the resolved
+    9. Apply the `skip` names via `apply_skip_stages` onto the resolved
        workflow (None/empty — no skip)
-    8. Resolve the amendment facts from the operation's own data: the
-       `PipelineIdentity` (discovered name; authored header name and
-       description read via `parse_dsl` from the pipeline-file text; entry
-       source), the `WorkflowDecision` (disabled /
-       explicit / auto-match / silent-miss with the resolved name), and the
-       `WorkIdentity` (current branch via `resolve_current_branch_name`,
-       the literal "unknown" when it resolves None; the hosting topic slug
-       and year via `resolve_topic_dir` when its
-       directory exists, the branch-only form otherwise)
-    9. Unless the decision is disabled, deliver the amendment via the
-       `PipelineHooks` checkpoint surface with the authored workflow after
-       the skip merge — receiving the overlay result; a disabled decision
-       delivers nothing (the layer is off) and the overlay is the
-       passthrough `WorkflowOverlay` of the merged workflow
-    10. Resolve the in-container project name via `resolve_project_name`
+    10. Resolve the amendment facts from the operation's own data: the
+        `PipelineIdentity` (discovered name; authored header name and
+        description read via `parse_dsl` from the pipeline-file text; entry
+        source), the `WorkflowDecision` (disabled /
+        explicit / auto-match / silent-miss with the resolved name), and the
+        `WorkIdentity` (current branch via `resolve_current_branch_name`,
+        the literal "unknown" when it resolves None; the hosting topic slug
+        and year via `resolve_topic_dir` when its
+        directory exists, the branch-only form otherwise)
+    11. Unless the decision is disabled, deliver the amendment via the
+        `PipelineHooks` checkpoint surface with the authored workflow after
+        the skip merge — receiving the overlay result; a disabled decision
+        delivers nothing (the layer is off) and the overlay is the
+        passthrough `WorkflowOverlay` of the merged workflow
+    12. Resolve the in-container project name via `resolve_project_name`
         (None when the git origin remote is unavailable). Compile via
         `compile_flow` with the overlay workflow (the resolved workflow when
         the layer is off), the in-container project root (Path.cwd()) as
         root_dir, and the project name; receive the documents tuple;
         structural errors propagate unchanged
-    11. Materialize agent prompts atomically (validate-all, then wipe, then
+    13. Materialize agent prompts atomically (validate-all, then wipe, then
         write): resolve the default prompts directory per `default_prompts`;
         for each overridable role (planner, executor, reviewer) require an
         inline override from the documents tuple or an existing default file
         (stem via `translate_role`); require the summary default; then reset
         <AFM_DIR>/prompts/ and write exactly four files — overrides where
         present, defaults otherwise, summary always from the default
-    12. Order the compiled stages via `order_stages` and build one
+    14. Write the afm configuration file via `write_afm_config` with the
+        effective pipeline agent — the whole file at the fixed in-container
+        home path, before the launch
+    15. Order the compiled stages via `order_stages` and build one
         `CompositionStage` per ordered stage — id from the `FlowStage` id,
         title from the `FlowStage` name
-    13. Resolve the work statuses — the maximal present statuses of the
+    16. Resolve the work statuses — the maximal present statuses of the
         hosting topic via `assemble_status_scale` and `resolve_topic_status`;
         an empty list in the branch-only form
-    14. Emit the run-creation facts via the checkpoint surface immediately
+    17. Compose the afm launch environment layer per `extra-env-carriage`:
+        decode the CLI entries payload via `decode_extra_env` from the
+        dedicated engine variable; apply the decoded entries above the
+        effective pipeline.env task env layer; drop the entries whose keys
+        are engine variables — silently. A damaged payload is one clean
+        error here — no events fire, afm never launches
+    18. Emit the run-creation facts via the checkpoint surface immediately
         before the launch: the identity, the decision, the overlay, the
         composition, the work identity, the statuses, and the runtime dir as
         a posix string
-    15. Launch afm via `run_flow` with the compiled flow-file path, `port`,
-        and max_parallel=`parallel`
-    16. On every return of `run_flow` — zero, non-zero, and spawn failures
+    19. Launch afm via `run_flow` with the compiled flow-file path, `port`,
+        max_parallel=`parallel`, and the composed layer as its env parameter
+        — the process environment of the container stays untouched
+    20. On every return of `run_flow` — zero, non-zero, and spawn failures
         alike — recompute the work statuses at the completion moment and
         emit the run-completion facts with the actual exit code
-    17. Return the exit code returned by `run_flow`
+    21. Return the exit code returned by `run_flow`
 
     Requirements:
+    - The environment reads are exactly two: AFM_DIR and the CLI entries
+      payload engine variable — the workflow decision and the skip names
+      arrive as parameters
     - Always pass the absolute pipeline path to `compile_flow` — never the
       bare name
     - Always pass the absolute compiled flow path to `run_flow` — never the
       bare name or the DSL path
     - Always forward `port` to `run_flow`; forward `parallel` (None
       propagates — no --max-parallel flag)
-    - Read AFM_DIR directly from the process environment — the only
-      environment read; the workflow decision and the skip names arrive as
-      parameters
+    - A configuration load failure and a configuration delivery failure fire
+      no events — the return happens before the pipeline checkpoints; afm
+      never launches on a delivery failure
+    - The amendment summary lines of the config delivery print to stderr
+      (nothing when empty)
+    - Docker-level fields of the effective configuration (image, proxy,
+      hosts) are consumed nowhere in-container — applied-but-unconsumed,
+      silently, no warning
     - `no_workflow` takes precedence over `workflow` (the host-side launcher
       rejects the combined use; the precedence is defensive)
     - Workflow resolution and parsing go through `resolve_workflow` — one
@@ -681,15 +749,23 @@
     - The "run_created" action fires immediately before the runner launch;
       the "run_completed" action fires on every launch-attempt return path
       — no exit path skips the completion emission
-    - A missing pipeline and a structural composition error fire no events
-      — the return happens before the checkpoints
+    - A missing pipeline, a structural composition error, and a
+      configuration load or delivery failure fire no events — the return
+      happens before the checkpoints
+    - A damaged CLI entries payload is one clean error before the
+      run-creation facts — no events fire, afm never launches
     - The runtime dir fact is the resolved AFM_DIR path as a posix string
     - With no tool packages installed the overlay is the passthrough — the
       compiled workflow, the prompts, and the output behave exactly as with
       the amendment layer absent
-    - <AFM_DIR>/prompts/ contains exactly four files after step 11 succeeds;
+    - <AFM_DIR>/prompts/ contains exactly four files after step 13 succeeds;
       validation precedes any wipe or write — atomicity guarantees no
       partial state on disk
+    - The afm configuration file is written exactly once per run, before
+      the launch, via `write_afm_config`
+    - The launch layer applies to the afm subprocess only, through the env
+      parameter of `run_flow` — engine-variable keys never enter the layer,
+      and the container's process environment is never mutated
     - Inline prompt overrides come exclusively from the documents tuple
       header roles; the override is a full file replacement — no merge, no
       concatenation
@@ -703,6 +779,9 @@
       the inline prompt overrides as-is
 
     Constraints:
+    - Do not load the configuration outside `load_project_config` followed
+      by the checkpoint delivery — one load, one delivery, one effective
+      configuration
     - Do not invoke afm directly outside `run_flow`
     - Do not invoke the compiler outside `compile_flow`
     - Do not invoke the workflow parser outside `parse_workflow`
@@ -716,11 +795,67 @@
     - Do not skip the completion emission on any launch-attempt return path
     - Do not write prompts inside the project directory or /workspace —
       always <AFM_DIR>/prompts/
+    - Do not write the afm configuration anywhere but the fixed in-container
+      home path — never in the project directory, never in the afm state
+      directory
     - Do not write inline prompt overrides into the compiled flow-file
     - Do not delete skipped stages or rewrite depends_on — `compile_flow`
       does both
     - Do not write or generate a workflow-file for skip — the merge is
       in-memory only
+    - Do not mutate the process environment — composed layers travel only
+      through the env parameter of `run_flow`
+    - Do not print configuration values — summary lines carry the tool, the
+      path, set or forced only
+
+"write_afm_config(agent: str | None) -> config_path: Path":
+  location: afm_config.py
+  annotations: |
+    Write the whole afm configuration file in-container before the afm
+    launch: the agent client command resolved from the effective pipeline
+    agent, plus the four static launcher-side fields.
+
+    `agent`: the effective pipeline agent — the authored pipeline.agent as
+             amended by the config delivery; None when no agent resolves
+    `config_path`: the fixed in-container path of the written file
+
+    Apply `convention` for docstring style and intra-package imports.
+    Apply `afm` for the configuration-file contract — the field set, the
+    fixed home path, and the per-stage override relationship.
+    Apply `resolve-wrapper-path` when resolving the agent command.
+
+    Algorithm:
+    1. Resolve the absolute wrapper path via `resolve_wrapper_path` — only
+       when `agent` is not None
+    2. Compose the content: the client command carrying the resolved
+       absolute wrapper path (never a bare agent name) — written only when
+       an agent resolved, omitted otherwise so per-stage workflow agents or
+       the binary's own defaults cover the absent global default; plus the
+       four static fields — the dashboard theme, the disabled browser
+       launch, the disabled internal proxy provider, and the in-container
+       prompts directory
+    3. Write the whole file to the fixed in-container home configuration
+       path — the path is independent of the afm state directory variable
+    4. Return the written path
+
+    Requirements:
+    - The whole file is rewritten on every run — a repeated invocation
+      stays safe
+    - The four static fields are constants — never configurable through
+      the project configuration or the CLI
+    - The content is serialized programmatically — never hand-escaped as a
+      string
+    - The file lands only at the fixed home configuration path — never in
+      the project directory, never in the afm state directory
+
+    Constraints:
+    - Do not write a bare agent name as the client command — always the
+      resolved absolute wrapper path
+    - Do not derive the prompts directory value from an argument or a
+      configuration field — the value is fixed
+    - Do not create or manage the prompts directory — the run coordination
+      materializes it
+    - Do not print any part of the written content
 
 "apply_skip_stages(workflow: WorkflowDocument | None, skip_stages: list[str]) -> workflow: WorkflowDocument | None":
   location: apply_skip_stages.py
@@ -883,5 +1018,7 @@
 Description: |
   Cell that owns the pipeline workflow: discovery of *.yml pipeline files
   across the project and user pipeline directories, the pipeline-file entity
-  model, the informational surface (overview and card), run coordination,
+  model, the informational surface (overview and card), run coordination
+  with the in-container run parameters — the configuration load-and-amend,
+  the afm configuration authorship, and the launch environment composition —
   and the in-container CLI entrypoint pipeline_cli.
````

#### practice: `goga/pipeline/.usages/run-pipeline.md`

````diff
--- a/goga/pipeline/.usages/run-pipeline.md
+++ b/goga/pipeline/.usages/run-pipeline.md
@@ -1,10 +1,10 @@
 # run_pipeline — in-container run coordination
 
-`run_pipeline` resolves a pipeline name to a file, resolves an optional workflow from the
-CLI-provided decision, merges the CLI skip names, delivers the workflow amendment through the
-pipeline hooks zone, compiles the pipeline-file to an afm flow-file via `compile_flow`,
-materializes the four agent prompt files, emits the run-creation facts, launches afm via
-`run_flow`, and emits the run-completion facts on its return.
+`run_pipeline` loads and amends the project configuration, resolves a pipeline name to a file, resolves an optional
+workflow from the CLI-provided decision, merges the CLI skip names, delivers the workflow amendment through the
+pipeline hooks zone, compiles the pipeline-file to an afm flow-file via `compile_flow`, materializes the four agent
+prompt files, writes the afm configuration file, emits the run-creation facts, launches afm via `run_flow` with the
+composed launch layer, and emits the run-completion facts on its return.
 
 ## Signature
 
@@ -20,6 +20,22 @@
 - `skip: list[str] | None` — stage names to skip; None and empty both mean no skip
 - `parallel: int | None` — cap on concurrently executing stages; None means unbounded
 
+## Configuration: load-and-amend
+
+The run coordination opens with the configuration load-and-amend: the authored `load_project_config`, then the
+`amend_config` delivery to the tool packages installed in the image, then the amendment summary lines to stderr.
+Everything downstream consumes the effective configuration — the afm configuration write reads the effective
+`pipeline.agent`, the launch layer reads the effective `pipeline.env`. The first failing tool stops the run with a
+clean error naming the tool and the action: afm never launches and no run events fire. Docker-level fields (image,
+proxy, hosts) of the effective configuration are applied-but-unconsumed here — silently.
+
+## afm configuration
+
+Before the launch the coordination writes the whole afm configuration file via `write_afm_config`: the client command
+resolved from the effective `pipeline.agent` — written only when an agent resolves, so per-stage workflow agents or
+afm's own defaults cover the absent global default — plus the four static fields (theme, open_browser, proxy.enabled,
+prompts_dir) at the fixed in-container home path (`/home/goga/.afm/config.yaml`, independent of `AFM_DIR`).
+
 ## Workflow resolution
 
 The workflow decision arrives as explicit parameters — the in-container CLI parses the
@@ -48,18 +64,23 @@
 
 ## Run events
 
-`run_created` fires immediately before the runner launch — after compilation and prompt
-materialization. `run_completed` fires on every launch-attempt return — zero, non-zero, and
-spawn failures (126/127) alike — with the work statuses recomputed at the completion moment and
-the actual exit code. Both notifications are soft: a failing hook warns and the run's exit code
-is unaffected. A missing pipeline and a structural composition error fire no events — the
-return happens before the checkpoints.
+`run_created` fires immediately before the runner launch — after compilation, prompt
+materialization, and the afm configuration write. `run_completed` fires on every launch-attempt
+return — zero, non-zero, and spawn failures (126/127) alike — with the work statuses recomputed
+at the completion moment and the actual exit code. Both notifications are soft: a failing hook
+warns and the run's exit code is unaffected. A missing pipeline, a structural composition error,
+and a configuration load or delivery failure fire no events — the return happens before the
+checkpoints.
 
 ## Environment
 
-The only environment read is `AFM_DIR` — the in-container afm state directory. Run options (the
-workflow decision, the skip names, the parallel cap) never travel through the environment; they
-arrive as parameters from the CLI.
+The environment reads are exactly two: `AFM_DIR` (the in-container afm state directory) and the
+CLI entries payload variable `GOGA_EXTRA_ENV`. The afm launch environment composes as the ladder
+requires: the container's process environment stays untouched, and the composed layer — the
+effective task env layer (`pipeline.env`) with the decoded CLI entries applied above it,
+engine-variable keys dropped — passes to `run_flow` as its `env` parameter, applying to the afm
+subprocess only. Run options (the workflow decision, the skip names, the parallel cap) never
+travel through the environment; they arrive as parameters from the CLI.
 
 ## Threading chains (host → container)
 
@@ -70,9 +91,17 @@
             → run_flow(…, max_parallel=N)
               → afm run --port PORT --max-parallel N <flow>
 
+    goga pipeline NAME -e KEY=V
+      → docker run … -m goga.pipeline run NAME --port PORT
+        (env-file: home.env, git identity, KEY=V, engine variables, GOGA_EXTRA_ENV)
+        → pipeline_cli → run_pipeline
+          → run_flow(…, env={**effective pipeline.env, "KEY": "V"})
+            → afm runs with KEY=V overriding the pipeline.env value
+
     goga pipeline NAME -w hardening -s build -s test
       → docker run … -m goga.pipeline run NAME --port PORT -w hardening -s build -s test
         → pipeline_cli: workflow="hardening", skip=["build", "test"]
           → run_pipeline(…, workflow="hardening", skip=["build", "test"])
 
-Absent flag ⇒ None ⇒ auto-match / no skip / unbounded.
+Absent flag ⇒ None ⇒ auto-match / no skip / unbounded. Absent `-e` ⇒ empty payload ⇒ the task
+env layer alone.
````

#### practice: `goga/pipeline/.usages/registering-hooks.md`

The tool-author-facing events practice follows the run form's new failure surface: the
configuration load-or-delivery failure joins the no-event returns, and the `run_created`
row names the afm configuration write in its ordering.

````diff
--- a/goga/pipeline/.usages/registering-hooks.md
+++ b/goga/pipeline/.usages/registering-hooks.md
@@ -14,11 +14,12 @@
 | Address | Error class | Fires |
 |---|---|---|
 | `pipeline / amend_workflow` | hard | After the workflow resolution and the runner-skip merge, before compilation — in the run form and in the card form alike. |
-| `pipeline / run_created` | soft | Immediately before the runner launch — after compilation and prompt materialization. |
+| `pipeline / run_created` | soft | Immediately before the runner launch — after compilation, prompt materialization, and the afm configuration write. |
 | `pipeline / run_completed` | soft | On every launch-attempt return — zero, non-zero, and spawn failures (126/127) alike. |
 
-A failing moment fires nothing: a missing pipeline and a structural
-composition error return before any checkpoint.
+A failing moment fires nothing: a missing pipeline, a structural
+composition error, and a configuration load or delivery failure return
+before any checkpoint.
 
 ## Subscribe
 
````

### Cell: goga/build — modified

#### CODEMANIFEST: `goga/build/CODEMANIFEST`

````diff
--- a/goga/build/CODEMANIFEST
+++ b/goga/build/CODEMANIFEST
@@ -7,14 +7,20 @@
       - load_project_config
     From: goga/config
   - Types:
+      - ConfigHooks
+      - ConfigOverlay
+    From: goga/config/hooks
+  - Types:
       - resolve_wrapper_path
     Usages:
       - resolve-wrapper-path
     From: goga/agents
   - Types:
       - ensure_in_docker
+      - decode_extra_env
     Usages:
       - ensure-in-docker
+      - extra-env-carriage
     From: goga/docker
   - Types:
       - run_ralphex
@@ -70,6 +76,20 @@
   checkpoint moments, never at them. Env values are never delivered to any
   context and never printed — presence travels as names only.
 
+  The entrypoint owns the in-container load-and-amend of the project
+  configuration: the authored load, the config amendment delivery to the tool
+  packages installed in the image, and the handover of the effective
+  configuration to the orchestration. The delivery follows the
+  one-action-two-moments rule — the same action, vocabulary, and semantics
+  as the host delivery; each side consumes only the fields it owns.
+
+  The orchestration enforces the agent value requirement on the effective
+  configuration before the first state write, so a container-side amendment
+  supplying build.agent satisfies it. The pass env layers compose per
+  `extra-env-carriage`: the effective task env layer of the pass with the CLI
+  entries payload applied above it, engine-variable keys dropped — applied
+  through the env layer of the ralphex launch only.
+
   Use the `conventions` practice for development and testing.
   Use the `ralphex` practice for the ralphex config-generation contract (the
   .ralphex/config key layout, the external-review surface, the finalize step
@@ -110,42 +130,53 @@
        with root inheritance, the tri-state skip, the strategy default medium
     2. Validate the review configuration via `validate_review_config` when
        the review pass will run; a validation failure fires no events
-    3. Rewrite .ralphex/prompts/ and .ralphex/agents/ from the vendored
+    3. Guard the tasks agent on the effective configuration: when the
+       resolved tasks agent of the settings is None — one clean error naming
+       the missing agent requirement, exit code 1, no events fire, nothing
+       is written; a container-side amendment supplying build.agent
+       satisfies the guard
+    4. Rewrite .ralphex/prompts/ and .ralphex/agents/ from the vendored
        defaults via `sync_ralphex_defaults` — roles filtering, finalize
-       materialization when the prompt is set; then reject the run when the
-       resolved tasks agent is None (a pre-launch failure — no events fire,
-       exit code 1)
-    4. Resolve the checkpoint facts from this operation's own data: the
+       materialization when the prompt is set
+    5. Decode the CLI entries payload once via `decode_extra_env` from the
+       dedicated engine variable (per `extra-env-carriage`); a damaged
+       payload is one clean error — nothing partially applied, no pass
+       launches
+    6. Resolve the checkpoint facts from this operation's own data: the
        `WorkIdentity` (branch via `resolve_current_branch_name` with the
        "unknown" fallback, slug/year via `resolve_topic_dir` when the branch
        hosts a topic), the `BuildMoment` (plan, work, dry_run), and both
        `StageFacts` (env as names)
-    5. Run the validation gate via `BuildHooks` (its validate_build
+    7. Run the validation gate via `BuildHooks` (its validate_build
        checkpoint); when the
        returned `GateVerdict` is not approved: print one merged error listing
        every violation (tool, hook, reason) to sys.stderr and return exit
        code 1 — no pass launches, the plan is not relocated, no further
        events fire
-    6. Emit build_started with the same facts the gate saw
-    7. Tasks pass: compose the options via `compose_pass_options` (stage
+    8. Emit build_started with the same facts the gate saw
+    9. Tasks pass: compose the options via `compose_pass_options` (stage
        tasks), resolve the root agent wrapper per the `resolve-wrapper-path`
-       practice, emit pass_started, launch via `run_build_pass` with the
-       root env as the env layer, emit pass_completed with the actual exit
-       code
-    8. When the tasks pass succeeded and review is not skipped: review pass
-       under the review agent's wrapper (the additional agent's wrapper under
-       the short strategy), the review env as the env layer, the
-       strategy-bound options; pass_started / launch / pass_completed
-       around it. A failed tasks pass never launches the review pass
-    9. Relocate the plan via `move_completed_plan` with outcome = success of
-       the final pass (dry-run and failure leave the plan in place); take the
-       returned `RelocationOutcome`
-    10. Recompute the work's history statuses via `collect_topic_statuses`
+       practice, compose the tasks env layer — the effective build.env task
+       env layer with the decoded CLI entries applied above it,
+       engine-variable keys dropped (per `extra-env-carriage`) — emit
+       pass_started, launch via `run_build_pass` with the composed layer as
+       the env layer, emit pass_completed with the actual exit code
+    10. When the tasks pass succeeded and review is not skipped: review pass
+        under the review agent's wrapper (the additional agent's wrapper under
+        the short strategy), the review env layer — the effective
+        build.review.env task env layer with the same decoded CLI entries
+        applied above it, engine-variable keys dropped — and the
+        strategy-bound options; pass_started / launch / pass_completed
+        around it. A failed tasks pass never launches the review pass
+    11. Relocate the plan via `move_completed_plan` with outcome = success of
+        the final pass (dry-run and failure leave the plan in place); take the
+        returned `RelocationOutcome`
+    12. Recompute the work's history statuses via `collect_topic_statuses`
         AFTER the relocation attempt (moved or not; branch-only form — an
         empty list)
-    11. Emit build_completed with the final exit code, the executed stage
+    13. Emit build_completed with the final exit code, the executed stage
         sequence, the relocation outcome, and the recomputed statuses
-    12. Return the exit code of the last executed pass
+    14. Return the exit code of the last executed pass
 
     Apply `conventions` for docstring style and intra-package imports.
     Apply `ralphex` for the config-generation contract.
@@ -159,6 +190,14 @@
     Requirements:
     - `ralphex` is launched only through `run_ralphex` — never via a direct
       subprocess call
+    - The agent value guard runs before the first state write — the
+      .ralphex/ rewrite never starts on a run the guard rejects
+    - The guard reads the effective configuration — an amendment supplying
+      build.agent satisfies it
+    - The CLI entries payload decodes once per run and feeds both pass
+      compositions; the payload wins over the task env layer on key conflict
+    - Engine-variable keys never enter a composed layer — dropped silently,
+      the inherited launch values stand
     - Every non-skipped run is exactly two passes; a skipped review yields
       exactly one tasks pass
     - The run's exit code is the last executed pass's; plan relocation
@@ -166,15 +205,19 @@
     - The task env never reaches the review pass (secret-safe, never printed)
     - On dry-run: fire the identical event structure with the dry_run fact,
       print the commands of both passes without env layers, relocate nothing
-    - Pre-launch failures (steps 0-3) fire no events — the moment never
+    - Pre-launch failures (steps 0-5) fire no events — the moment never
       happened
-    - A blocked run (step 5) fires nothing after the gate
+    - A blocked run (step 7) fires nothing after the gate
     - Warnings and errors of the checkpoints name the tool, the action, and
       the reason (delivered by the zone per its practices)
 
     Constraints:
     - Do not assemble the ralphex command or invoke ralphex directly —
       delegate to `run_ralphex`
+    - Do not read the environment for the payload anywhere but the single
+      decode step
+    - Do not apply any layer to the process environment — layers travel only
+      through the env parameter of the ralphex launch
     - Do not read git at a checkpoint moment — the facts resolve before
       delivery
     - Do not deliver or print env values — names only, in every fact
@@ -188,6 +231,9 @@
 
     `exit_code`: process exit code (0 = success, 1 = failure)
 
+    Apply the `ensure-in-docker` practice for the container guard.
+    Apply `conventions` for docstring style and intra-package imports.
+
     Algorithm:
     0. Call `ensure_in_docker` as the very first statement (per the
        `ensure-in-docker` practice)
@@ -197,15 +243,25 @@
        --skip-manifest-check, --session-timeout, --idle-timeout, --wait,
        --max-iterations, and --review-patience (addressing
        build.review.additional.patience)
-    2. Load project configuration via `load_project_config`
-    3. Build cli_options from the parsed argparse results
-    4. Invoke `build`(plan, `ProjectConfig`, cli_options)
-    5. Return the resulting `exit_code`
+    2. Load the authored project configuration via `load_project_config` —
+       a load failure is one clean error, exit 1; ralphex never launches
+    3. Deliver the config amendment via the `ConfigHooks` checkpoint surface
+       with the authored configuration — the first failing tool, or a tool
+       package whose facade fails to import, converts to one clean error
+       naming the tool and the action, exit 1; ralphex never launches
+    4. Print the amendment summary lines to stderr (nothing when empty)
+    5. Build cli_options from the parsed argparse results
+    6. Invoke `build`(plan, the effective configuration of the
+       `ConfigOverlay`, cli_options)
+    7. Return the resulting `exit_code`
 
     Requirements:
     - The guard at step 0 MUST be covered by tests for both branches
-
-    Apply the `ensure-in-docker` practice at step 0.
+    - Exactly one configuration load and exactly one delivery — the
+      orchestration receives the effective configuration, never the authored
+      one
+    - No configuration value appears in any output — the summary lines carry
+      the tool, the path, set or forced only
 
 "resolve_run_settings(config: BuildConfig, cli_options: dict) -> settings: RunSettings":
   location: run_settings.py
@@ -393,8 +449,8 @@
     3. When the review part carries a non-empty env and no review agent —
        raise ValueError naming the problem (env requires agent)
     4. When the resolved review agent is None — raise ValueError naming the
-       problem (no review agent). Reachable only on direct in-container
-       invocation — the host launcher requires build.agent up front
+       problem (no review agent). Reachable when neither the authored
+       configuration nor an amendment supplies a review agent
     5. Resolve the review-agent wrapper via `resolve_wrapper_path` and
        require the wrapper file to exist; absence raises ValueError naming
        the agent
````

#### practice: `goga/build/.usages/build-usage.md`

````diff
--- a/goga/build/.usages/build-usage.md
+++ b/goga/build/.usages/build-usage.md
@@ -2,11 +2,15 @@
 
 ## Overview
 
-The `goga.build` module orchestrates the stable two-pass build cycle through
-ralphex — settings resolution with root inheritance, the five hooks checkpoints,
-ralphex config generation with the external-review surface, vendored
-defaults sync with finalize materialization, and delegation of the launch to
-`run_ralphex` (goga/ralphex).
+The `goga.build` module opens with the configuration load-and-amend — the
+authored `load_project_config`, the `amend_config` delivery to the tool
+packages installed in the image, and the effective configuration feeding
+everything downstream (settings resolution, agent resolution, env layers) —
+then orchestrates the stable two-pass build cycle through ralphex — settings
+resolution with root inheritance, the five hooks checkpoints, ralphex config
+generation with the external-review surface, vendored defaults sync with
+finalize materialization, and delegation of the launch to `run_ralphex`
+(goga/ralphex).
 
 Every non-skipped run is exactly two ralphex invocations: a tasks pass
 (`--tasks-only`) then a review pass (`--review`, or `-e` under the short
@@ -23,13 +27,16 @@
 
 ```python
 from goga.config import load_project_config
+from goga.config.hooks import ConfigHooks
 from goga.build import build
 
-config = load_project_config()
+config = load_project_config()           # authored load — hooks-free
+overlay = ConfigHooks().amend_config(config=config)
+print_summary_to_stderr(overlay.summary_lines)
 
 exit_code = build(
     plan="docs/plans/my-plan.md",
-    config=config,
+    config=overlay.config,               # the effective configuration
     cli_options={
         "dry_run": False,
         "skip_manifest_check": False,
@@ -47,7 +54,9 @@
 ## Parameters
 
 - `plan` — path to the plan file (markdown)
-- `config` — ProjectConfig object loaded via `load_project_config`
+- `config` — the effective ProjectConfig: the authored load via
+  `load_project_config` followed by the `amend_config` delivery (the entry
+  point performs the composition; direct callers do the same)
 - `cli_options` — options dictionary (`dry_run`, `skip_manifest_check`,
   `skip_review`, `base_ref`, `review_patience`, `session_timeout`,
   `idle_timeout`, `wait`, `max_iterations`); each knob is None when the CLI
@@ -111,9 +120,11 @@
 
 The cycle delivers five hooks checkpoints:
 
-1. `validate_build` (hard gate) — after goga's pre-checks, before the first
-   pass; every subscribed tool's hooks run to completion, vetoes merge into
-   one error (tool, hook, reason), exit 1, nothing launches
+1. `validate_build` (hard gate) — after goga's pre-checks (manifest check,
+   settings resolution, review-config validation, the agent value guard,
+   ralphex defaults sync), before the first pass; every subscribed tool's
+   hooks run to completion, vetoes merge into one error (tool, hook, reason),
+   exit 1, nothing launches
 2. `build_started` (soft) — immediately after the gate passes
 3. `pass_started` (soft) — before each pass launch
 4. `pass_completed` (soft) — on every pass return, with the actual exit code
@@ -125,12 +136,33 @@
 invalid review config, unavailable defaults) and a blocked (vetoed) run fire
 no events.
 
+## Environment ladder
+
+Each pass launches with the ladder applied in-container: the inherited launch
+environment (home.env, git identity, the CLI `-e` lines, the engine variables)
+stays untouched, and the pass env layer — the effective task env layer of the
+pass (`build.env` for the tasks pass, `build.review.env` for the review pass)
+with the decoded CLI `-e` entries applied above it, engine-variable keys
+(`AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`)
+dropped — passes to `run_ralphex` as its env layer, applying to that pass's
+subprocess only. The task env layer never reaches the review pass; the CLI
+entries payload reaches both passes (the same values already sit in the
+inherited environment). Nothing is printed.
+
+## Agent guard
+
+The tasks agent is required: when the resolved tasks agent of the effective
+configuration is None, the run stops with one clean error before any state
+write — `.ralphex/` is never touched, no events fire. A container-side
+amendment supplying `build.agent` satisfies the guard.
+
 ## Review-pass environment
 
 `build.review.env` (mapping of strings) overrides same-named variables for the
 review pass subprocess only; every other container variable passes through
 unchanged. The tasks pass receives `build.env` as its env layer the same way.
-Neither layer is printed on dry-run (secret-safe).
+The CLI `-e` entries apply above each pass's task env layer per the
+environment ladder above. Neither layer is printed on dry-run (secret-safe).
 
 ## Plan relocation
 
@@ -175,4 +207,6 @@
 `main()` calls `ensure_in_docker()` first, then argparse handles parsing
 (`--skip-review`/`--no-skip-review`, `--base-ref`, `--dry-run`,
 `--skip-manifest-check`, `--session-timeout`, `--idle-timeout`, `--wait`,
-`--max-iterations`, `--review-patience`) and calls `build()`.
+`--max-iterations`, `--review-patience`), then loads and amends the
+configuration (authored load → `amend_config` delivery → summary lines to
+stderr) and calls `build()` with the effective configuration.
````

#### practice: `goga/build/.usages/registering-hooks.md`

````diff
--- a/goga/build/.usages/registering-hooks.md
+++ b/goga/build/.usages/registering-hooks.md
@@ -13,15 +13,15 @@
 
 | Address | Error class | Fires |
 |---|---|---|
-| `build / validate_build` | hard | After goga's own pre-checks (manifest check, settings resolution, review-config validation, ralphex defaults sync) and before the first pass launch — including dry-run runs. |
+| `build / validate_build` | hard | After goga's own pre-checks (manifest check, settings resolution, review-config validation, the agent value guard, ralphex defaults sync) and before the first pass launch — including dry-run runs. |
 | `build / build_started` | soft | Immediately after the gate passes, before the first pass launch. |
 | `build / pass_started` | soft | Before each pass launch — tasks and review. |
 | `build / pass_completed` | soft | On every pass return — zero, non-zero, and spawn-failure codes alike, carrying the actual exit code. |
 | `build / build_completed` | soft | On every return of a started build — after the relocation attempt and the status recompute. |
 
 A failing moment fires nothing: goga pre-launch failures (uncommitted
-manifests, invalid review config, unavailable defaults, missing build section
-or agent) return before any checkpoint. A blocked (vetoed) run fires nothing
+manifests, invalid review config, unavailable defaults, a missing build
+section, a missing effective agent) return before any checkpoint. A blocked (vetoed) run fires nothing
 after the gate.
 
 ## Subscribe
````

### Cell: goga/commands/pipeline — modified

#### CODEMANIFEST: `goga/commands/pipeline/CODEMANIFEST`

````diff
--- a/goga/commands/pipeline/CODEMANIFEST
+++ b/goga/commands/pipeline/CODEMANIFEST
@@ -20,11 +20,6 @@
       - checkpoints
     From: goga/config/hooks
   - Types:
-      - resolve_wrapper_path
-    Usages:
-      - resolve-wrapper-path
-    From: goga/agents
-  - Types:
       - resolve_runtime_dir
     Usages:
       - runtime-paths
@@ -41,17 +36,18 @@
       - docker_update
       - docker_build_if_not_exist
       - DockerRunner
+      - encode_extra_env
     Usages:
       - docker-builder
       - docker-runner
       - docker-image-version
+      - extra-env-carriage
     From: goga/docker
 
 Usages:
   convention: .goga/usages/conventions.md
   click: .goga/usages/cooks/click.md
   afm: .goga/usages/cooks/afm.md
-  agent-wrappers: .goga/usages/cooks/agent-as-claude-wrappers.md
   git: |
     External git binary invoked via subprocess.run (check=True,
     capture_output=True). Set GIT_TERMINAL_PROMPT=0 in the env to suppress
@@ -79,9 +75,6 @@
   Use the `afm` practice for the in-container binary contract (CLI shape,
   PATH-resolved invocation, exit codes).
 
-  Use the `agent-wrappers` practice for the in-container wrapper naming
-  convention referenced when generating the afm client.command config.
-
   Use the `pipeline-cli` practice for the in-container subcommand surface
   (the listing and run subcommands with the info modifiers), the
   `list-pipelines` and `describe-pipelines` practices for the listing and
@@ -97,9 +90,21 @@
   command and invokes python -m goga.pipeline inside the goga Docker image.
   The runtime boundary to goga/pipeline is docker, not Python Imports; the
   host never reads pipeline files directly. Two launch shapes exist: the run
-  launcher (full shape — allocated port, env-file, afm-config tmpfile,
-  persistent afm state, signal handling) and the info
-  launcher (minimal read-only shape — none of those).
+  launcher (full shape — allocated port, env-file, persistent afm state,
+  signal handling) and the info launcher (minimal read-only shape — none of
+  those). The host owns the launch mechanics only: image, dockerfile, port,
+  mounts, hosts, proxy variables, env-file base layers, engine variables,
+  container name, signal handling, and the structural section guards. Run
+  parameters — the task env layer and the agent — resolve in-container.
+
+  The run form carries the CLI environment entries twice from one source
+  (per `extra-env-carriage`): the raw KEY=VALUE lines travel in the env-file,
+  and the same entries travel encoded as the dedicated engine payload
+  variable. The configuration task env layer stays out of the env-file — the
+  in-container run coordination applies it around the afm launch. Use
+  `checkpoints` for the host config amendment delivery: the host delivery
+  serves the host-owned launch fields, and amendments into run-parameter
+  fields stay applied-but-unconsumed — silently.
 
   Everything the in-container CLI consumes (run options) travels as command
   arguments after the image; everything the afm binary, agents, and tools
@@ -238,9 +243,13 @@
        `checkpoints` practice via the `ConfigHooks` checkpoint surface —
        amend_config(config=...) — and treat the effective configuration
        of the `ConfigOverlay` as
-       the run's configuration — the missing-pipeline-section guard and
-       every downstream read address the effective configuration; a
-       missing pipeline section is a clean error. A load or checkpoint
+       the launch's configuration: the missing-pipeline-section guard and
+       every downstream read of host-owned launch fields (image,
+       dockerfile, proxy, hosts) address the effective configuration; a
+       missing pipeline section is a clean error. Amendments into
+       run-parameter fields (pipeline.env, pipeline.agent) stay
+       applied-but-unconsumed — the host consumes them nowhere, silently,
+       no warning. A load or checkpoint
        failure — ValueError covers the hard action, ImportError a
        broken tool package facade — wraps into the same user-facing
        ClickException, never a raw traceback. The home configuration
@@ -379,18 +388,22 @@
   annotations: |
     Host-side docker launcher for the run form. Launches the goga Docker
     container to run "python -m goga.pipeline run" and returns the
-    container's exit code.
+    container's exit code. The host owns the launch mechanics only — the
+    run parameters (the task env layer, the agent) resolve in-container.
 
     `name`: pipeline name without extension
-    `config`: loaded project configuration (provides image, pipeline.agent,
-              pipeline.env)
+    `config`: the host-effective project configuration, consumed for the
+              host-owned launch fields only (image, dockerfile, proxy,
+              hosts); the run-parameter fields (pipeline.env,
+              pipeline.agent) are consumed nowhere on the host
     `extra_env`: raw KEY=VALUE strings (default empty) forwarded into the
-                 container env-file. When the default empty tuple is passed,
-                 no extra environment variables are forwarded.
+                 container env-file verbatim AND encoded into the CLI
+                 entries payload variable — one source, the same parsed
+                 values in both places (per `extra-env-carriage`)
     `proxy`: resolved HTTP/HTTPS proxy URL (CLI overrides config in the
              caller). When non-None, the launcher writes HTTP_PROXY,
              HTTPS_PROXY, and NO_PROXY=localhost,127.0.0.1 into the
-             container env-file.
+             container env-file as engine variables.
     `hosts`: resolved host→IP dict (CLI entries merged on top of
              config.pipeline.hosts by the caller; CLI wins on host-key
              conflict; default None — no extra hosts). Each entry becomes
@@ -436,47 +449,17 @@
     2. Verify config.image is set; raise ClickException when None
     3. Allocate a free localhost TCP port for the dashboard
     4. Generate a unique container_name
-    5. Resolve the agent wrapper path via `resolve_wrapper_path` (per the
-       `resolve-wrapper-path` practice) using config.pipeline.agent, ONLY
-       when config.pipeline.agent is not None; otherwise the wrapper path is
-       None. Do not validate the agent value — absence of the wrapper file
-       is surfaced by afm itself. pipeline.agent is OPTIONAL: when it is
-       None the agent is expected to come from the workflow (per-stage
-       command overrides) or from afm's own defaults, so None is carried
-       through, not rejected.
-    6. Install a SIGTERM/SIGINT handler (raises SystemExit with code 128 +
-       signum) BEFORE creating any temp file — the leak-prevention invariant
-       (a signal during tmpfile/env-file setup or the `docker_update` build
-       must unwind to the finally block and unlink the secret files). The
-       runner's handler later nests under this one. Then create a private
-       afm-config tmpfile carrying the launcher-side fields: client.command
-       set to the resolved wrapper path (written ONLY when the wrapper path
-       is not None — i.e. when config.pipeline.agent is configured; omitted
-       otherwise so per-stage workflow agents or afm's own defaults cover
-       the absent global default), theme: goga (dashboard theme),
-       open_browser: false (the dashboard is reached via the host-printed
-       http://localhost:<port> URL; afm must not attempt to open a browser
-       inside the container), proxy.enabled: false (afm's own internal
-       outbound proxy provider is disabled; goga manages the outbound proxy
-       through the container env-file via HTTP_PROXY / HTTPS_PROXY /
-       NO_PROXY), and prompts_dir: /home/goga/pipeline/prompts (the
-       in-container prompts directory, derived from the known
-       AFM_DIR=/home/goga/pipeline value — NOT from an additional argument
-       or config field; the directory is populated by the in-container run
-       coordination from the four goga-packaged defaults plus any inline
-       overrides from the pipeline-file header — see the `run-pipeline` and
-       `afm` practices). The tmpfile is a read-only overlay over the
-       persistent afm state directory mounted in step 11
-    7. Resolve the persistent afm state host directory via
-       `resolve_pipeline_runtime_dir` and ensure it exists (idempotent).
-       Executed BEFORE the step-6 signal handler and temp files — no secret
-       file exists yet at this point, and the directory must be on disk
-       under every exit path
-    8. When `clean` is True: wipe the resolved directory via
-       `clean_pipeline_runtime_dir` before launch (also before the step-6
-       handler and temp files — the wipe is strictly pre-launch, never in
-       finally)
-    9. Compute the workflow log decision (host-side, BEFORE container
+    5. Resolve the persistent afm state host directory via
+       `resolve_pipeline_runtime_dir` and ensure it exists (idempotent)
+    6. When `clean` is True: wipe the resolved directory via
+       `clean_pipeline_runtime_dir` before launch (strictly pre-launch,
+       never in finally)
+    7. Install a SIGTERM/SIGINT handler (raises SystemExit with code 128 +
+       signum) BEFORE creating the env-file — the leak-prevention invariant
+       (a signal during the env-file setup or the `docker_update` build must
+       unwind to the finally block and unlink the secret file). The runner's
+       handler later nests under this one
+    8. Compute the workflow log decision (host-side, BEFORE container
        launch):
        - When `no_workflow` is True — no workflow log
        - Else when `workflow` is not None (explicit --workflow, file already
@@ -487,23 +470,30 @@
          prefix — is a silent no-log, mirroring the in-container
          containment guard); log the pipeline name exactly when that file
          exists; otherwise no log
-    10. When workflow_log_name is not None: print
+    9. When workflow_log_name is not None: print
         "Pipeline running with workflow WORKFLOW_LOG_NAME" to stdout.
         This cell surfaces only this workflow log line — it does NOT print
         any dashboard URL line.
-    11. Create a private env-file layering home.env as the BASE
-        (lowest-priority) layer, then config.pipeline.env, git identity, the
-        `extra_env` KEY=VALUE strings (forwarded as-is, no validation),
-        AFM_DIR set to the in-container persistent state path,
+    10. Create a private env-file layering, in order: home.env as the BASE
+        (lowest-priority) layer, then git identity, then the raw `extra_env`
+        KEY=VALUE strings (forwarded as-is, no validation), then the engine
+        variables — AFM_DIR set to the in-container persistent state path,
         AFM_DOCKER_FILE_ROOTS set to the encoded file-manager roots of the
-        launch — composed via `collect_file_roots` from the home.docker.run
+        launch (composed via `collect_file_roots` from the home.docker.run
         tokens and encoded via `encode_file_roots`; the roots never diverge
-        from the actual mounts of the launch — when `proxy` is non-None — HTTP_PROXY, HTTPS_PROXY,
-        and NO_PROXY (fixed at localhost,127.0.0.1). Project config and CLI
-        override home.env on key conflict; an explicit `extra_env`
-        AFM_DOCKER_FILE_ROOTS entry overrides the launcher value (the
-        `extra_env` lines follow every launcher layer in the file).
-    12. Assemble the docker-run inputs to hand to `DockerRunner`:
+        from the actual mounts of the launch), and, when `proxy` is
+        non-None, HTTP_PROXY, HTTPS_PROXY, and NO_PROXY (fixed at
+        localhost,127.0.0.1) — then the CLI entries payload line:
+        GOGA_EXTRA_ENV set to the value of `encode_extra_env` over the same
+        `extra_env` strings (one source, per `extra-env-carriage` — the
+        payload and the env-file lines compose from the same parsed values
+        on every launch). The configuration task env layer (pipeline.env)
+        never enters the env-file. The engine layer is written after the CLI
+        lines and skips a key the CLI explicitly supplied — an explicit user
+        entry for an engine variable (the documented
+        -e AFM_DOCKER_FILE_ROOTS=... escape hatch of the `afm` practice)
+        keeps winning over the launcher-produced value
+    11. Assemble the docker-run inputs to hand to `DockerRunner`:
         - args: -m goga.pipeline run <name> --port <port> [-w <workflow>]
           [--no-workflow] [-s <name>]... [--parallel <parallel>] — the
           workflow flags appended exactly as given (neither flag on
@@ -511,10 +501,8 @@
           not None; omitted when None
         - params: name=<container_name>, rm=True, entrypoint=python3,
           workdir=/workspace, p=<port>:<port>, v=[project:/workspace (set as
-          container working dir), the persistent afm state host dir (step 7)
-          read-write at the in-container persistent state path, the afm-config
-          tmpfile (step 6) read-only at the in-container afm config path as a
-          client.command overlay],
+          container working dir), the persistent afm state host dir (step 5)
+          read-write at the in-container persistent state path],
           add_host=<each resolved HOST:IP>, env_file=<env-file path>
         - extra_args: home.docker.run — raw docker tokens passed as a
           SEPARATE keyword to DockerRunner.run (NOT part of params; appended
@@ -524,12 +512,9 @@
         - The assembled form: --rm, --name, -p <port>:<port>, the project
           bind-mount as /workspace (container working directory), the
           persistent afm state host dir read-write at the in-container
-          persistent state path (survives across runs), the afm-config
-          tmpfile read-only at the in-container afm config path (independent
-          of AFM_DIR; see the `afm` practice — the persistent dir supplies
-          the rest of afm state), --add-host per host, --env-file,
-          --entrypoint python3, image, args
-    13. Call `docker_build_if_not_exist` with config.image, config.dockerfile,
+          persistent state path (survives across runs), --add-host per host,
+          --env-file, --entrypoint python3, image, args
+    12. Call `docker_build_if_not_exist` with config.image, config.dockerfile,
         and extra_args=home.docker.build — the first-run safety net. No-op
         when the image already exists or when no Dockerfile is set. When the
         image is absent and a Dockerfile is declared: build it (fatal on
@@ -537,49 +522,41 @@
         home.docker.build tokens reach the build branch verbatim (extra_args
         — appended after the translated params flags, before -f); ignored on
         no-op branches. Runs inside the try so the leak-prevention invariant
-        covers this window: the secret tmpfile/env-file are already written
-        (steps 6, 11), and a fatal build unwinds to the finally which unlinks
-        them.
-    14. When `update` is True: call `docker_update` with config.image,
+        covers this window: the secret env-file is already written (step 10),
+        and a fatal build unwinds to the finally which unlinks it
+    13. When `update` is True: call `docker_update` with config.image,
         config.dockerfile, and extra_args=home.docker.build — build when a
         project Dockerfile is declared (fatal), else pull (warning,
         non-fatal). home.docker.build tokens are forwarded in the build
         branch only (ignored on the pull branch). When `update` is False:
-        skip the refresh.
-    15. Launch the container via
+        skip the refresh
+    14. Launch the container via
         DockerRunner(config.image).run(args, extra_args=home.docker.run,
         **params): (extra_args is a SEPARATE keyword; params is unpacked via
         **) the runner installs its own SIGTERM/SIGINT handler (exit 128 +
-        signum), which nests under the caller handler installed in step 6
+        signum), which nests under the caller handler installed in step 7
         (saves and restores it), runs docker run, streams stdout/stderr, and
         returns the exit code. The runner finally performs the guaranteed
         docker kill and restores to the caller handler
-    16. In finally: delete the afm-config tmpfile and delete the env-file,
-        and restore the caller-installed SIGTERM/SIGINT handler to the
-        original. Do NOT delete the persistent afm state host directory — it
-        survives across runs. The docker kill and the runner's
-        signal-handler restore happen inside the runner finally (which runs
-        before this finally); the runner's restore returns to the caller
-        handler, then this finally restores the original
-    17. Return the container exit code
-
-    Apply the `agent-wrappers` practice for the wrapper path semantics
-    referenced in step 5.
-    Apply the `resolve-wrapper-path` practice when calling
-    `resolve_wrapper_path` in step 5.
+    15. In finally: delete the env-file and restore the caller-installed
+        SIGTERM/SIGINT handler to the original. Do NOT delete the persistent
+        afm state host directory — it survives across runs. The docker kill
+        and the runner's signal-handler restore happen inside the runner
+        finally (which runs before this finally)
+    16. Return the container exit code
+
     Apply the `docker-builder` practice for the --update build-vs-pull
     refresh and the first-run safety net.
     Apply the `docker-runner` practice for the docker run launch and
     lifecycle.
-    Apply the `afm` practice for the in-container afm config.yaml contract,
-    including the prompts_dir field written in step 6.
     Apply the `afm` practice for the file-manager roots payload delivered
-    through AFM_DOCKER_FILE_ROOTS in step 11 — the schema, the encoding,
+    through AFM_DOCKER_FILE_ROOTS in step 10 — the schema, the encoding,
     and the roots scope live there.
-    Apply the `run-pipeline` practice for the in-container prompt
-    materialization contract that populates the prompts_dir directory and
-    for the explicit-parameter contract of the workflow decision and skip
-    names the argv carries.
+    Apply the `extra-env-carriage` practice for the CLI entries payload
+    line of step 10 and the ladder order of the env-file layers.
+    Apply the `run-pipeline` practice for the in-container contract the
+    argv addresses — the load-and-amend, the afm configuration authorship,
+    and the launch layer the container side composes.
     Apply the `home-configuration` practice for loading the optional
     machine-wide home config (home.env as the lowest-priority env layer;
     home.docker.run appended to the docker run; home.docker.build forwarded
@@ -588,51 +565,38 @@
     Requirements:
     - Use the same port value in -p <port>:<port> and in --port <port>
       (single source — the port allocated in step 3)
-    - afm-config tmpfile is owner-only (private). It carries the
-      launcher-side fields: client.command: <resolved wrapper path> (the
-      value MUST be the absolute path returned by `resolve_wrapper_path`,
-      never a bare agent name; the client: block is written ONLY when
-      config.pipeline.agent is configured — when it is None the block is
-      omitted, so per-stage workflow agents or afm's own defaults cover the
-      absent global default), theme: goga, open_browser: false,
-      proxy.enabled: false, and prompts_dir: /home/goga/pipeline/prompts.
-      theme, open_browser, proxy.enabled, and prompts_dir are static
-      launcher-side constants — they are NOT configurable via the goga
-      ProjectConfig or CLI
-    - env-file content: home.env (base) + config.pipeline.env + git identity
-      + `extra_env` KEY=VALUE strings (forwarded as-is, no validation) +
-      AFM_DIR=/home/goga/pipeline + AFM_DOCKER_FILE_ROOTS=<encoded roots> +
-      (when proxy is non-None) HTTP_PROXY/HTTPS_PROXY/NO_PROXY
+    - env-file content: home.env (base) + git identity + the raw CLI -e
+      strings + AFM_DIR + AFM_DOCKER_FILE_ROOTS + (when proxy) the proxy
+      triple + GOGA_EXTRA_ENV — the engine variables follow the CLI lines;
+      the configuration task env layer never enters
+    - The payload line and the CLI lines compose from the same parsed values
+      on every launch — they never diverge
     - AFM_DOCKER_FILE_ROOTS is written into the env-file on every run
       launch: the value comes from `collect_file_roots` and
       `encode_file_roots` over the home.docker.run tokens; repeated
       launches with unchanged mounts produce the identical value; an
       explicit user -e AFM_DOCKER_FILE_ROOTS=... entry wins
-    - home.env is the lowest-priority env layer; project config
-      (config.pipeline.env) and CLI extra_env override home.env on key
-      conflict. home.docker.run tokens are appended to the docker run
-      (passed as extra_args to `DockerRunner`). home.docker.build tokens are
-      forwarded to image build (passed as extra_args to
-      `docker_build_if_not_exist` / `docker_update`; build branch only).
-      An absent home file yields an empty `HomeConfig` — no effect
-    - Persistent afm state directory mount is read-write; the tmpfile
-      client.command overlay is read-only
-    - The client.command tmpfile mount target is FIXED at
-      /home/goga/.afm/config.yaml and does NOT depend on AFM_DIR — afm
-      always reads config.yaml from ~/.afm/config.yaml. AFM_DIR controls
-      only afm state (flows, run-state), not config.yaml discovery
+    - home.env is the lowest-priority env layer; the CLI -e lines override
+      home.env on key conflict. home.docker.run tokens are appended to the
+      docker run (passed as extra_args to `DockerRunner`). home.docker.build
+      tokens are forwarded to image build (passed as extra_args to
+      `docker_build_if_not_exist` / `docker_update`; build branch only). An
+      absent home file yields an empty `HomeConfig` — no effect
+    - Persistent afm state directory mount is read-write; no afm config
+      overlay exists on any launch — the afm config.yaml is written
+      in-container by the run coordination
+    - AFM_DIR=/home/goga/pipeline is provided via the env-file
     - First-run safety net runs UNCONDITIONALLY at launch entry via
       `docker_build_if_not_exist`: when config.image is absent locally AND
       config.dockerfile is declared, build it (fatal on failure — surfaces
       as ClickException, exit 1, launch skipped); no-op when the image is
       present or no Dockerfile is declared
-    - AFM_DIR=/home/goga/pipeline is provided via the env-file
     - SIGTERM/SIGINT during the run must result in exit code 128 + signum
       (130 for SIGINT, 143 for SIGTERM); the caller installs its
-      SIGTERM/SIGINT handler BEFORE writing the secret tmpfile/env-file, and
-      the runner's handler nests under it (leak prevention — a signal in the
+      SIGTERM/SIGINT handler BEFORE writing the secret env-file, and the
+      runner's handler nests under it (leak prevention — a signal in the
       setup window, including the `docker_update` build, must unwind to the
-      finally block and unlink the secret files)
+      finally block and unlink the secret file)
     - Propagate afm's non-zero exit code as the container's exit code
     - The run argv carries the workflow decision exactly as given: -w <name>,
       --no-workflow, or neither (in-container auto-match); the skip names
@@ -640,7 +604,7 @@
     - The "Pipeline running with workflow NAME" log line is printed ONLY
       when a workflow will actually be applied: explicit --workflow X (file
       already validated by the caller) OR basename auto-match file exists on
-      the host (existence check at step 9). When --no-workflow is set OR the
+      the host (existence check at step 8). When --no-workflow is set OR the
       auto-match file does not exist, NO workflow log is printed
     - Append --parallel <parallel> to the in-container run argv ONLY when
       `parallel` is not None (absent ⇒ no flag ⇒ afm unbounded); the Docker
@@ -655,10 +619,10 @@
       build, not a rebuild of an existing image)
     - Do NOT apply home.env to docker build — home.env is a docker run
       container-env layer only (no --build-arg)
-    - Do NOT let home.env override project config or CLI env — home.env is
-      the lowest-priority (base) layer
-    - Delete only the tmpfile and env-file in finally — the persistent afm
-      state host directory survives across runs
+    - Do NOT let home.env override the CLI env — home.env is the
+      lowest-priority (base) layer
+    - Delete only the env-file in finally — the persistent afm state host
+      directory survives across runs
     - --clean wipes the persistent afm state host directory BEFORE launch;
       the directory survives across runs (no wipe in finally under any exit
       path)
@@ -667,24 +631,19 @@
     - Do not auto-add --add-host entries to NO_PROXY
     - Do not mount anything under /workspace other than the project
       directory — in-container afm state belongs in /home/goga/.afm/
-      (config.yaml) and /home/goga/pipeline (state)
+      (config.yaml, written by the container) and /home/goga/pipeline (state)
     - Do not compose file-manager roots from any mount other than the
       project mount and the home.docker.run directory mounts — engine
-      mounts (the persistent afm state, the config overlay)
-      never become roots
-    - Do not write the afm config into the project directory — use a tmpfile
-      and a read-only mount
+      mounts (the persistent afm state) never become roots
+    - Do not resolve the agent or write any afm configuration — the afm
+      config.yaml is authored in-container by the run coordination
+    - Do not write the configuration task env layer (pipeline.env) into the
+      env-file — it applies in-container around the afm launch
+    - Do not encode the CLI entries from any source other than the same
+      parsed values written into the env-file
     - Do not invoke the in-container entrypoint other than via "docker run
       python -m goga.pipeline"
     - Do not import any Type from goga/pipeline — runtime boundary only
-    - Do not validate config.pipeline.agent against a hardcoded whitelist —
-      absence of the wrapper is surfaced by afm
-    - Do not write a bare agent name into client.command — always write the
-      resolved absolute wrapper path
-    - Do not derive prompts_dir from an additional CLI option, config field,
-      or runtime argument — the value is fixed at
-      /home/goga/pipeline/prompts and follows from the known
-      AFM_DIR=/home/goga/pipeline constant
     - Do not surface any dashboard URL line on stdout — this cell prints
       only the workflow log line (when applicable) and forwards the docker
       output stream
@@ -754,7 +713,7 @@
 
     Requirements:
     - The minimal shape holds for all three forms: no published port, no
-      env-file, no afm-config tmpfile, no persistent afm state mount, no
+      env-file, no persistent afm state mount, no
       caller-side signal handler
     - The card argv carries the workflow decision and the skip names exactly
       as given: explicit -w WORKFLOW, --no-workflow, or neither (in-container
@@ -763,11 +722,10 @@
       directories and launch no agents
 
     Constraints:
-    - Do not publish a port, mount a tmpfile or env-file, or mount the
-      persistent afm state — the info path is read-only
+    - Do not publish a port, mount an env-file, or mount the persistent afm
+      state — the info path is read-only
     - Do not refresh the image in the overview and card forms
-    - Do not write any file on the host — no tmpfile, no env-file, no
-      cleanup
+    - Do not write any file on the host — no env-file, no cleanup
     - Do not import any Type from goga/pipeline — the runtime boundary is
       docker only
 
@@ -931,8 +889,8 @@
     - Do not re-split or re-quote `tokens` — consume the already-tokenized
       list
     - Do not fail on unrecognized or malformed tokens — skip them
-    - Do not include engine mounts — afm state and the config overlay
-      never become roots
+    - Do not include engine mounts — the afm state mount never becomes a
+      root
 
 "encode_file_roots(roots: list[FileRoot]) -> value: str":
   location: file_roots.py
@@ -970,8 +928,10 @@
   Host-side CLI wrapper cell for the single pipeline command. Every form —
   the flat list, the overview, the card, and the run — launches the goga
   Docker container and invokes the in-container pipeline entrypoint inside
-  it; the run form can first bring the repository onto the requested work
-  (the -t/--topic switch-or-create) on the host and describes the afm
-  dashboard file-manager roots to the container env-file. The runtime
-  boundary to the in-container pipeline is docker — this cell has no Python
-  Type Imports from it.
+  it. The host owns the launch mechanics only: the run form can first bring
+  the repository onto the requested work (the -t/--topic switch-or-create)
+  on the host, describes the afm dashboard file-manager roots and the CLI
+  entries payload to the container env-file, and leaves the run parameters —
+  the task env layer and the agent — to the in-container coordination. The
+  runtime boundary to the in-container pipeline is docker — this cell has no
+  Python Type Imports from it.
````

#### practice: `goga/commands/pipeline/.usages/pipeline-command.md`

````diff
--- a/goga/commands/pipeline/.usages/pipeline-command.md
+++ b/goga/commands/pipeline/.usages/pipeline-command.md
@@ -76,12 +76,27 @@
 
 ## Docker shapes
 
-- Run form: full shape — allocated port, env-file, afm-config tmpfile, persistent afm state
-  mount, caller-side signal handler.
+- Run form: full shape — allocated port, env-file, persistent afm state
+  mount, caller-side signal handler. No afm-config overlay exists: the whole
+  `config.yaml` is written in-container by the run coordination, after its
+  load-and-amend of the effective configuration.
 - List/info forms: minimal read-only shape — none of the above. The decision travels in the
   subcommand argv: `-m goga.pipeline list [--info]` or `-m goga.pipeline run NAME --info
   [-w WORKFLOW | --no-workflow] [-s NAME]...`.
 
+## Environment carriage (run form)
+
+The env-file carries the launch base layers in ladder order: home.env, git
+identity, the raw CLI `-e` lines, then the engine variables (`AFM_DIR`,
+`AFM_DOCKER_FILE_ROOTS`, the proxy triple) — skipping a key the CLI
+explicitly supplied (the documented `-e AFM_DOCKER_FILE_ROOTS=...` escape
+hatch keeps winning) — then the `GOGA_EXTRA_ENV` payload: the same CLI
+entries encoded per the carriage contract of goga/docker, so the
+in-container run applies them above the task env layer at the afm launch.
+The task env layer (`pipeline.env`) and the agent (`pipeline.agent`) never
+travel through the host: they resolve in-container from the effective
+configuration the in-container load-and-amend produces.
+
 ## File manager roots (run form)
 
 The afm dashboard file manager shows the directories the user may browse.
@@ -94,7 +109,7 @@
 | project | the mounted project at `/workspace` | always — listed first, read-write |
 | extra | a directory mount from a `home.docker.run` `-v`/`--volume` token | when the token's host part exists as a directory |
 
-File mounts, named volumes, missing host paths, the afm config overlay, and
+File mounts, named volumes, missing host paths, and
 the persistent afm state directory never become roots.
 
 Exposing an extra directory — add a volume token to ~/.goga/config.yml:
@@ -141,4 +156,11 @@
       → docker run … -m goga.pipeline run NAME --port PORT -w hardening -s build -s test
         → the in-container run resolves the workflow and applies the skips
 
-Absent ⇒ no flag ⇒ auto-match / no skip / unbounded.
+    goga pipeline NAME -e KEY=V
+      → docker run … -m goga.pipeline run NAME --port PORT
+        (env-file: home.env, git identity, KEY=V, engine vars, GOGA_EXTRA_ENV)
+        → the in-container run applies the effective pipeline.env with KEY=V
+          above it at the afm launch
+
+Absent ⇒ no flag ⇒ auto-match / no skip / unbounded. Absent `-e` ⇒ no payload
+line value beyond the empty-mapping payload ⇒ the task env layer alone.
````

### Cell: goga/commands/build — modified

#### CODEMANIFEST: `goga/commands/build/CODEMANIFEST`

````diff
--- a/goga/commands/build/CODEMANIFEST
+++ b/goga/commands/build/CODEMANIFEST
@@ -29,10 +29,12 @@
       - docker_update
       - docker_build_if_not_exist
       - DockerRunner
+      - encode_extra_env
     Usages:
       - docker-builder
       - docker-runner
       - docker-image-version
+      - extra-env-carriage
     From: goga/docker
 
 Usages:
@@ -41,11 +43,12 @@
 
 Annotations: |
   The `conventions` practice is used for:
-  - working with the codebase
-  - organizing the REPL development cycle
-  - debugging and testing
-  - organizing test infrastructure
-  - understanding general development and testing principles/rules in the project
+  - Working with the codebase
+  - Organizing the REPL development cycle
+  - Debugging and testing
+  - Organizing the test infrastructure
+  - Understanding the general principles and rules of development and
+    testing in the project
   Use the `click` practice to create the command.
 
   Use the `checkpoints` practice for the config amendment checkpoint at
@@ -94,6 +97,17 @@
   in-container; the env-file carries the base layers (home.env, git
   identity, CLI -e, proxy).
 
+  Guards split by nature: the structural build-section guard stays
+  host-side on the host-effective configuration — a build-less config fails
+  before any docker activity; the agent value guard lives in the
+  in-container build domain, where an amendment can supply the agent.
+
+  The CLI environment entries travel twice from one source (per
+  `extra-env-carriage`): the raw KEY=VALUE lines in the env-file, and the
+  same entries encoded as the dedicated engine payload variable, so the
+  in-container build applies them above its task env layers at the pass
+  launches. The task env (build.env) stays out of the env-file.
+
   The command runs goga.build inside a Docker container.
 
   This command is the host-side launcher for `run_build`: it
@@ -145,7 +159,10 @@
               build.review.base_ref; forwarding only, precedence resolves
               in-container
     `extra_env`: raw KEY=VALUE strings from the repeatable -e/--env click
-              option, forwarded into the container env-file
+              option, forwarded into the container env-file verbatim AND
+              encoded into the CLI entries payload variable — one source,
+              the same parsed values in both places (per
+              `extra-env-carriage`)
     `proxy`: optional HTTP/HTTPS proxy URL from the --proxy click option.
              When None, falls back to config.build.proxy. The resolved value
              (CLI wins over config) drives HTTP_PROXY/HTTPS_PROXY/NO_PROXY in
@@ -202,30 +219,31 @@
     Load the home configuration via `load_home_config` (per the
     `home-configuration` practice) — an empty `HomeConfig` when the home file
     is absent (no-op). home.env is the lowest-priority env layer (step 7);
-    home.docker.run is appended to every docker run (step 14/18);
-    home.docker.build is forwarded to image build (steps 16/17, build branch).
+    home.docker.run is appended to every docker run (step 13/17);
+    home.docker.build is forwarded to image build (steps 15/16, build branch).
     1. Verify docker availability; raise ClickException when missing
     2. Load configuration via `load_project_config` (practice `project-configuration`) — get `ProjectConfig`;
        deliver the config amendment checkpoint per the `checkpoints`
        practice right after the authored load via the `ConfigHooks`
        checkpoint surface — amend_config(config=...) — the config.build
-       is None guard and every downstream field access address the
-       effective configuration of the `ConfigOverlay`. A load or
+       is None guard and every downstream access to host-owned launch
+       fields address the effective configuration of the `ConfigOverlay`.
+       Amendments into run-parameter fields (build.env, build.agent) stay
+       applied-but-unconsumed — the host consumes them nowhere, silently,
+       no warning. A load or
        checkpoint failure — ValueError covers the hard action,
        ImportError a broken tool package facade — wraps into the
        same user-facing ClickException, never a raw traceback. The home
        configuration load stays authored-only
     2.1. When config.build is None → raise ClickException(
         "build section is required in .goga/config.yml to run 'goga build'").
-        Host-side guard — runs BEFORE any config.build access and BEFORE the
-        docker command is assembled, so the in-container goga.build never
-        starts on a build-less config (no docker run).
-    2.2. When config.build.agent is None → raise ClickException(
-        "build.agent is required in .goga/config.yml to run 'goga build'").
-        The agent is optional at the loader level (None when absent/empty), but the
-        build command resolves it into the in-container wrapper path and cannot run
-        without it. Host-side guard — runs BEFORE any agent access to avoid a
-        downstream TypeError.
+        Host-side structural guard — runs BEFORE any config.build access and
+        BEFORE the docker command is assembled, on the host-effective
+        configuration, so the in-container goga.build never starts on a
+        build-less config (no docker run). The agent value guard lives
+        in-container: the effective agent may arrive as a container-side
+        amendment, so a host check on the authored value would reject a run
+        an amendment could have satisfied
     3. Collect cli_flags from click parameters; forward the review pair:
        skip_review True → --skip-review; False → --no-skip-review; None →
        neither flag (the tri-state survives to the container); forward
@@ -241,35 +259,40 @@
     6. Read git identity and assemble it as git env vars; tolerate absent git
        config and continue without error
     7. Assemble the container env layering home.env as the BASE (lowest-priority)
-       layer, then git identity env, and CLI extra env (home.env < git
-       identity < CLI extra env on key conflict — CLI overrides home.env);
+       layer, then git identity env, then the raw CLI extra env KEY=VALUE
+       strings (forwarded as-is, no validation — CLI overrides home.env on
+       key conflict), then the engine variables — when the resolved proxy is
+       non-None: HTTP_PROXY, HTTPS_PROXY, and
+       NO_PROXY (fixed at localhost,127.0.0.1) to the container env,
+       skipping a key the CLI explicitly supplied — then the CLI entries
+       payload line: GOGA_EXTRA_ENV set to the value of `encode_extra_env`
+       over the same parsed CLI strings (one source, per
+       `extra-env-carriage`);
        the task env (build.env) is NOT written into the env-file — it is
-       forwarded for the tasks-pass env layer in-container
-    8. When the resolved proxy is non-None: add HTTP_PROXY, HTTPS_PROXY, and
-       NO_PROXY (fixed at localhost,127.0.0.1) to the container env
-    9. Verify ProjectConfig.image is set; raise ClickException when None
-    10. Install a SIGTERM/SIGINT handler (raises SystemExit with code 128 + signum)
+       applied in-container at the pass launches
+    8. Verify ProjectConfig.image is set; raise ClickException when None
+    9. Install a SIGTERM/SIGINT handler (raises SystemExit with code 128 + signum)
         BEFORE writing the secret env-file — the leak-prevention invariant (a
         signal in the window between the env-file write and the `DockerRunner`
         launch, which includes the `docker_update` build, must unwind to the
         finally block and unlink the secret file). The runner's handler later
         nests under this one. Then write the assembled env to a private env-file
         for the container
-    11. Resolve the host runtime directory via `resolve_build_runtime_dir`:
+    10. Resolve the host runtime directory via `resolve_build_runtime_dir`:
         - call `resolve_runtime_dir`("builds") (the routine composes
           ~/.goga/runtime/builds/<normalized_project>/<branch>/ from cwd + git
           branch)
         - ensure the directory exists (idempotent mkdir with parents)
-    12. When `clean` is True: wipe and recreate the host runtime directory via
+    11. When `clean` is True: wipe and recreate the host runtime directory via
         `clean_build_runtime_dir` BEFORE docker run. When `clean` is False: keep
         the existing directory as-is (ralphex progress files survive across runs)
-    13. Generate a unique container_name
-    14. Assemble the docker-run inputs to hand to `DockerRunner`:
+    12. Generate a unique container_name
+    13. Assemble the docker-run inputs to hand to `DockerRunner`:
         - args: the post-image command — -m goga.build <plan> + cli_flags
         - params: the docker-run options, translated to flags by the
           shared rule in `docker-runner` — name=<container_name>, rm=True,
           entrypoint=python3, workdir=/workspace, v=[CWD:/workspace, the resolved
-          host runtime dir (step 11) read-write at /workspace/.ralphex], add_host=<each resolved HOST:IP>,
+          host runtime dir (step 10) read-write at /workspace/.ralphex], add_host=<each resolved HOST:IP>,
           env_file=<env-file path>
         - extra_args: home.docker.run — raw docker tokens passed as a SEPARATE
           keyword argument to DockerRunner.run (NOT part of params: they are
@@ -282,28 +305,28 @@
           /workspace/.ralphex as a nested bind-mount, so ralphex auto-detects
           .ralphex/ in cwd and the bytes land in the host runtime dir, never in
           the project dir), --add-host, --env-file, image, args
-    15. On dry_run: print the assembled command and exit 0 without launching
-    16. Call `docker_build_if_not_exist` with config.image, config.dockerfile,
+    14. On dry_run: print the assembled command and exit 0 without launching
+    15. Call `docker_build_if_not_exist` with config.image, config.dockerfile,
         and extra_args=home.docker.build — the first-run safety net, runs
         UNCONDITIONALLY at launch entry. No-op when the image already exists or
         when no Dockerfile is set (extra_args forwarded in the build branch only).
         When the image is absent and a Dockerfile is declared: build it (fatal on failure
         — surfaces as a ClickException, exit 1, launch
         skipped). Runs inside the try so the leak-prevention invariant covers
-        this window: the secret env-file is already written (step 10), and a
+        this window: the secret env-file is already written (step 9), and a
         fatal build unwinds to the finally which unlinks it
-    17. When `update` is True: call `docker_update` with config.image,
+    16. When `update` is True: call `docker_update` with config.image,
         config.dockerfile, and extra_args=home.docker.build — build when a
         project Dockerfile is declared (fatal on failure; the build branch
         forwards extra_args), else pull (warning, non-fatal; extra_args ignored).
         When `update` is False: skip the refresh.
-    18. Launch the container via `DockerRunner`(config.image).run(args, extra_args=home.docker.run, **params):
+    17. Launch the container via `DockerRunner`(config.image).run(args, extra_args=home.docker.run, **params):
         extra_args is a SEPARATE keyword (NOT inside params, which is
         unpacked via **); the runner installs its own SIGTERM/SIGINT handler (exit 128 + signum),
-        which nests under the caller handler installed in step 10 (saves and
+        which nests under the caller handler installed in step 9 (saves and
         restores it), runs docker run, streams stdout/stderr, and returns the
         exit code
-    19. In finally: delete the env-file and remove ``.ralphex/`` from the project
+    18. In finally: delete the env-file and remove ``.ralphex/`` from the project
         directory via `_cleanup_ralphex_in_project` to enforce the contract
         invariant that no ``.ralphex/`` appears in the project directory under any
         exit path, and restore the caller-installed SIGTERM/SIGINT handler to the
@@ -380,6 +403,10 @@
     - Do NOT let home.env override CLI env — home.env is the
       lowest-priority (base) layer; CLI extra env wins on key conflict
       (build.env is not part of the env-file at all)
+    - Do not guard the agent value on the host — the effective agent may
+      arrive as a container-side amendment; the guard lives in-container
+    - Do not encode the CLI entries from any source other than the same
+      parsed values written into the env-file
     - Do not write --add-host for hosts absent in both config and CLI
     - Do not validate the "HOST:IP" format of --add-host entries beyond a
       single-colon split — Docker itself reports malformed entries
@@ -420,7 +447,7 @@
     Requirements:
     - Return value is an absolute path
     - Pure with respect to the filesystem — does not create the directory
-      (creation is the caller's responsibility in `build` Algorithm step 11)
+      (creation is the caller's responsibility in `build` Algorithm step 10)
 
     Constraints:
     - Do not create the directory here — the caller handles creation
````

#### practice: `goga/commands/build/.usages/build.md`

````diff
--- a/goga/commands/build/.usages/build.md
+++ b/goga/commands/build/.usages/build.md
@@ -34,7 +34,7 @@
 | `--review-patience` | int | from config | External-review stop threshold; addresses `build.review.additional.patience` in `.goga/config.yml`; forwarded to the container only when set |
 | `--base-ref` | str | from config | Review diff base (branch name or commit hash). Addresses `build.review.base_ref` in `.goga/config.yml`; forwarded to the container only when set. Reaches ralphex as `--base-ref` on the review pass only |
 | `--skip-review` / `--no-skip-review` | bool pair | tri-state | Skip the review phase (`--skip-review`) or force the full cycle (`--no-skip-review`). Overrides `build.review.skip` in `.goga/config.yml`; when neither flag is given, the config decides |
-| `-e` / `--env` | str (multiple) | — | Pass environment variables to the container (KEY=VALUE) |
+| `-e` / `--env` | str (multiple) | — | Pass environment variables to the container (KEY=VALUE). The entries travel in the env-file AND as the `GOGA_EXTRA_ENV` payload (one source), so the in-container build applies them above the task env layers at the pass launches |
 | `--proxy` | str | from config | HTTP/HTTPS proxy URL; overrides `build.proxy` in `.goga/config.yml`. When set, adds HTTP_PROXY/HTTPS_PROXY/NO_PROXY to the container env-file |
 | `--add-host` | str (multiple) | — | Add a `docker run --add-host HOST:IP` entry. Merges on top of `build.hosts` from config; CLI wins on host-key conflict |
 | `-c` / `--clean` | flag | false | Wipe the persistent ralph-loop runtime directory under `~/.goga/runtime/builds/<normalized_project>/<branch>/` before launching the container. Default is no wipe — ralph-loop state (progress files, config, prompts, agents) survives across runs of the same project on the same branch, useful for resuming interrupted builds |
@@ -77,11 +77,11 @@
 ## Requirements
 
 - Docker must be installed and available in PATH
-- `.goga/config.yml` must contain a `build` section. The loader makes the section optional (`config.build` is `None` when absent), but `goga build` cannot run without it — the command raises `ClickException("build section is required in .goga/config.yml to run 'goga build'")` before any field access and before the container is launched. The `build.agent` field itself is optional at the loader level (absent/empty → `None`), but `goga build` needs an agent to resolve the in-container wrapper — when it is `None` the command raises `ClickException("build.agent is required in .goga/config.yml to run 'goga build'")` before launch
+- `.goga/config.yml` must contain a `build` section. The loader makes the section optional (`config.build` is `None` when absent), but `goga build` cannot run without it — the command raises `ClickException("build section is required in .goga/config.yml to run 'goga build'")` before any field access and before the container is launched, on the host-effective configuration. The agent value (`build.agent`) is guarded in-container after the configuration amendment: a run whose authored agent is unset but a container-side tool amendment supplies one proceeds; a run with no effective agent fails inside the container before anything is written
 - `.goga/config.yml` must have the top-level `image` field set — otherwise the command exits with error `image in .goga/config.yml is not set`
 - By default the image is NOT refreshed — the local image is used as-is. Use `--update`/`-u` to refresh it before launch: build when a project Dockerfile is declared (fatal on failure), else pull (warning on failure, non-fatal — the build continues with the locally available image)
 - First-run safety net: when `dockerfile` is declared in `.goga/config.yml` and the image is absent locally, the command builds it ONCE before launch even WITHOUT `--update` (so the first run after declaring a project Dockerfile does not need `--update`). `--update` forces a RE-build of an already-present image; the safety net is a no-op once the image exists
-- Git config (user.name, user.email) is automatically passed to the container as GIT_AUTHOR_NAME/EMAIL, GIT_COMMITTER_NAME/EMAIL. If git config is absent, the build continues without error. The container env-file carries the base layers only (home.env, git identity, CLI `-e`, proxy) — the task env (`build.env`) is NOT written into the env-file; it reaches the container solely as the in-container tasks-pass env layer
+- Git config (user.name, user.email) is automatically passed to the container as GIT_AUTHOR_NAME/EMAIL, GIT_COMMITTER_NAME/EMAIL. If git config is absent, the build continues without error. The container env-file carries the base layers only (home.env, git identity, the CLI `-e` lines, the proxy engine variables, the `GOGA_EXTRA_ENV` payload) — the task env (`build.env`) is NOT written into the env-file; it reaches the container solely as the in-container tasks-pass env layer, with the CLI `-e` entries applied above it at each pass launch
 - Credential files are NOT mounted automatically — the launcher adds no credential mounts. To
   give the in-container agents access to credentials, mount them yourself through the home
   configuration (`docker.run` volume tokens in ~/.goga/config.yml) or pass environment
@@ -126,9 +126,11 @@
 
 - **env (env-file base layer):** `home.env` is the BASE (lowest-priority) layer
   of the container env-file. CLI (`-e/--env`) overrides it on key conflict —
-  `home.env < git identity < CLI extra env`. The env-file carries the base
-  layers only; the task env (`build.env`) is forwarded for the tasks-pass
-  env layer in-container, not written into the env-file.
+  `home.env < git identity < CLI extra env < engine variables`; the CLI
+  entries additionally travel as the `GOGA_EXTRA_ENV` payload — same values,
+  one source (the carriage contract of goga/docker). The env-file carries
+  the base layers only; the task env (`build.env`) is applied for the
+  pass-launch layers in-container, not written into the env-file.
 - **docker.run:** `home.docker.run` tokens are appended verbatim to the
   `docker run` (the runner's `extra_args` channel).
 - **docker.build:** `home.docker.build` tokens are forwarded verbatim to image
````



## Dependency Map

```
                     ┌─────────────────────────────────────────────────┐
                     │  leaves                                        │
                     ├─────────────────────────────────────────────────┤
                     │ goga/version ← goga/docker (existing)          │
                     │ goga/docker   + encode_extra_env/decode_extra_env │
                     │ goga/afm      + run_flow(env=…)                 │
                     │ goga/ralphex  (unchanged; env param exists)     │
                     │ goga/agents   (unchanged; new consumer below)   │
                     │ goga/config, goga/config/project (unchanged)    │
                     │ goga/config/hooks (CODEMANIFEST unchanged;      │
                     │   usage rewritten to one-action-two-moments)    │
                     └─────────────────────────────────────────────────┘
                                           │
       ┌───────────────────────────────────┼─────────────────────────────┐
       ▼                                   ▼                             ▼
┌───────────────────────┐  ┌──────────────────────────┐  ┌─────────────────────────┐
│ goga/pipeline         │  │ goga/build               │  │ host commands           │
│ run_pipeline (mod)    │  │ main (mod)               │  │                         │
│ write_afm_config(new) │  │ build (mod)              │  │                         │
│ ← goga/config  +types │  │ ← goga/config  +types    │  │                         │
│ ← goga/config/hooks   │  │ ← goga/config/hooks      │  │                         │
│   (types-only) NEW    │  │   (types-only) NEW       │  │                         │
│ ← goga/agents     NEW │  │ ← goga/docker +decode    │  │                         │
│ ← goga/docker +decode │  │ ← goga/agents (existing) │  │                         │
│ ← goga/afm (env arg)  │  │ ← goga/ralphex(existing) │  │                         │
└──────────┬────────────┘  └──────────┬───────────────┘  └──────────┬──────────────┘
           │ run_flow(env=…)                 │ run_build_pass → run_ralphex(env=…)
           │                       ═══ docker runtime boundary (no Python imports) ═══
           ▼                                  ▼                       ▼
┌────────────────────────────┐  ┌───────────────────────────────────────────────┐
│ goga/commands/pipeline     │  │ goga/commands/build                           │
│ pipeline (mod)             │  │ build (mod)                                   │
│ run_pipeline_container(mod)│  │ ← goga/docker +encode_extra_env (existing edge)│
│ ← goga/docker +encode      │  │ − host agent value guard (moved in-container)  │
│ − goga/agents import gone  │  │                                                │
└────────────────────────────┘  └───────────────────────────────────────────────┘
```

New Python-import edges (3): `goga/pipeline → goga/config/hooks` (types-only), `goga/pipeline →
goga/agents`, `goga/build → goga/config/hooks` (types-only). Removed (1):
`goga/commands/pipeline → goga/agents`. All edges point strictly downward — no cycles
(`goga lint` confirms). The host↔container pairs exchange data only through the docker launch
(argv, env-file, `GOGA_EXTRA_ENV` payload) — the fixed direction law holds.

The docker carriage contract shared by all four consumers:

```
GOGA_EXTRA_ENV = base64( compact JSON of the parsed CLI -e entries )
env-file order: home.env → git identity → raw CLI -e lines → engine variables
                (AFM_DIR, AFM_DOCKER_FILE_ROOTS, proxy triple; a key the CLI
                explicitly supplied is skipped) → GOGA_EXTRA_ENV line
in-container:   decode once → apply above the effective task env layer, for the
                target binary's launch only → engine keys never overridden
```

## Verification Checklist

Check after materializing the artifacts, in this order:

1. **`goga lint`** over the whole project — must report 0 errors (the pre-issued target state
   was verified at 83 cells / 0 errors; any error means the materialized state diverged).
2. **`goga schema goga/docker goga/afm goga/pipeline goga/build goga/commands/pipeline
   goga/commands/build`** — the new types appear (`encode_extra_env`, `decode_extra_env`,
   `write_afm_config`), `run_flow` carries the `env` parameter, `goga/pipeline` and `goga/build`
   depend on `goga/config/hooks`, `goga/commands/pipeline` no longer depends on `goga/agents`.
3. **`goga/docker/.usages/extra-env-carriage.md`** exists and is connected through `Imports` by
   all four consumers (`goga/pipeline`, `goga/build`, `goga/commands/pipeline`,
   `goga/commands/build`), each referencing it in at least one annotation.
4. **Practices**: `goga/config/hooks/.usages/checkpoints.md` contains the "One action, two
   moments" section and no "In-container loads stay authored-only" text; the events row of
   `goga/config/.usages/registering-hooks.md` names the in-container entrypoints;
   `goga/pipeline/.usages/registering-hooks.md` names the configuration load-or-delivery
   failure among the no-event returns and the afm configuration write in the `run_created`
   row.
5. **Annotation rules**: no annotation references "from Imports" phrasing; no annotation
   references prior functionality (current-state contracts only); every connected practice is
   referenced; footer descriptions stay responsibility-zone level without detail; no
   annotation names the retired tmpfile/config-overlay mechanism (check the
   `goga/config/project` property annotations, `collect_file_roots`,
   `run_pipeline_info_container`).
6. **Contract spot checks** (read the manifests, not code): `run_pipeline` opens with
   load-and-amend before workflow resolution; `write_afm_config` writes the whole file at the
   fixed home path with `client.command` only when an agent resolves; `run_flow` treats
   `env=None` as the inherited environment; `build` guards the tasks agent before the first
   state write; both command manifests keep their structural guards and carry the payload line
   with the one-source rule; `run_pipeline_container` mounts no config overlay and writes no
   `pipeline.env` layer.
7. **Acceptance criteria**: all 11 criteria of the task file are covered by the contracts as
   mapped in the assembly report (11/11).
