# run_pipeline — in-container run coordination

`run_pipeline` loads and amends the project configuration, resolves a pipeline name to a file, resolves an optional
workflow from the CLI-provided decision under the profile activation context, merges the CLI skip names, delivers the
workflow amendment through the
pipeline hooks zone, compiles the pipeline-file to an afm flow-file via `compile_flow`, applies the per-stage env
wrappers as a targeted post-compile patch of the written flow-file, materializes the four agent
prompt files, writes the afm configuration file, emits the run-creation facts, launches afm via `run_flow` with the
composed launch layer, and emits the run-completion facts on its return.

## Signature

run_pipeline(name, project_dir, user_dir, port, workflow=None, no_workflow=False, profile=None,
skip=None, parallel=None) -> exit_code

- `name: str` — pipeline name without extension
- `project_dir: Path` / `user_dir: Path` — absolute project / user pipeline directories
- `port: int` — dashboard port, allocated by the host-side launcher
- `workflow: str | None` — explicit workflow name without the `.yml` extension; None falls back
  to the basename auto-match
- `no_workflow: bool` — when True, workflow application is disabled
- `profile: str | None` — the CLI activation channel value (-p/--profile); composes with the
  `GOGA_PROFILE` value and the workflow `profile:` default per the shared activation precedence
  (`--profile` > `GOGA_PROFILE` > workflow default)
- `skip: list[str] | None` — stage names to skip; None and empty both mean no skip
- `parallel: int | None` — cap on concurrently executing stages; None means unbounded

## Configuration: load-and-amend

The run coordination opens with the configuration load-and-amend: the authored `load_project_config`, then the
`amend_config` delivery to the tool packages installed in the image, then the amendment summary lines to stderr.
Everything downstream consumes the effective configuration — the afm configuration write reads the effective
`pipeline.agent`, the launch layer reads the effective `pipeline.env`. The first failing tool stops the run with a
clean error naming the tool and the action: afm never launches and no run events fire. Docker-level fields (image,
proxy, hosts) of the effective configuration are applied-but-unconsumed here — silently.

## afm configuration

Before the launch the coordination writes the whole afm configuration file via `write_afm_config`: the client command
resolved from the effective `pipeline.agent` — written only when an agent resolves, so per-stage workflow agents or
afm's own defaults cover the absent global default — plus the four static fields (theme, open_browser, proxy.enabled,
prompts_dir) at the fixed in-container home path (`/home/goga/.afm/config.yaml`, independent of `AFM_DIR`).

The write also registers goga's own observer hook in the global layer of the file: `id: goga`,
`command: python3 -m goga.pipeline hook`, `events: all`, `inherit_env: true`, and the afm
default timeout and retries — always on, no user action or configuration involved. afm spawns
the command once per lifecycle event; it bridges the run interior onto the hooks platform as
the fifteen soft mid-run `pipeline` actions, while the run boundaries stay with the run
coordination's `run_created` / `run_completed` checkpoints. Consequence: manual global-layer
hooks do not survive a goga launch — goga fully authors the global layer.

## Workflow resolution and profile activation

The workflow decision arrives as explicit parameters — the in-container CLI parses the
`-w WORKFLOW` / `--no-workflow` / `-p PROFILE` flags of the run subcommand. `no_workflow=True`
disables application; `workflow` names an explicit workflow; neither triggers the basename
auto-match (a workflow file named like the pipeline). Resolution follows the shared rule set —
the same rules the info card applies — so a run and a card with the same flags always agree on
which workflow applies. A missing auto-match file is a silent miss.

The resolved workflow loads under the profile activation context: the run coordination decodes
the `GOGA_HOME_PROFILES` bundle (`decode_home_profiles` from goga/docker — a damaged payload is
one clean pre-run error, no events), reads `GOGA_PROFILE` once, and passes all three channels
(CLI flag, env value, home bundle) into the shared loading chain. The workflow-file is rendered
with the active profile before parsing; `run_pipeline` receives the document AND the active
profile (`LoadedWorkflow`). With no workflow resolved, activation is ignored entirely — nothing
loads, no line prints.

## Launch feedback line

The run coordination prints ONE stdout line when a workflow resolved:

- `Pipeline running with workflow "<name>" and profile "<profile>"` — when an effective
  profile resolved (any activation channel, including the workflow `profile:` default),
- `Pipeline running with workflow "<name>"` — profile-free,
- nothing — without a workflow.

The line prints in-container (the coordination knows the effective profile and its source);
the host launcher prints no workflow line.

## Per-stage env wrappers

After `compile_flow` writes the flow-file, `apply_stage_env_wrappers` generates one sh closure
wrapper per env-declaring stage (see `per-stage-env`) and patches exactly those stages'
`command:` fields in the ALREADY WRITTEN flow-file — every other byte stays untouched. A
workflow declaring no stage env is neither read nor rewritten: the flow output stays
byte-identical to the compiler's direct composition.

## Skip

`skip` (the repeatable `-s NAME` names of the run subcommand; None and empty both mean no skip)
is applied in-memory onto the resolved workflow before compilation via `apply_skip_stages`.
Skip applies to a workflow-less pipeline too. Unknown names surface as the compiler's structural
error.

## Workflow amendment

After the skip merge and before compilation, the workflow amendment is delivered through the
pipeline hooks zone (`PipelineHooks.amend_workflow`); `compile_flow` receives the effective
workflow the delivery returns. An explicit workflow disable turns the layer off — the merged
(skip-bearing) workflow composes and no amendment delivers; a silent auto-match miss keeps the
layer active onto the empty base. With no tool packages installed the overlay is the passthrough
— every run composes exactly what was passed. The amendment is a hard action: the first failing
tool stops the command with a clean error, and its whole contribution is discarded.

## Run events

`run_created` fires immediately before the runner launch — after compilation, prompt
materialization, and the afm configuration write. `run_completed` fires on every launch-attempt
return — zero, non-zero, and spawn failures (126/127) alike — with the work statuses recomputed
at the completion moment and the actual exit code. Both notifications are soft: a failing hook
warns and the run's exit code is unaffected. A missing pipeline, a structural composition error,
and a configuration load or delivery failure fire no events — the return happens before the
checkpoints.

## Environment

The environment reads are exactly four: `AFM_DIR` (the in-container afm state directory), the
CLI entries payload variable `GOGA_EXTRA_ENV`, `GOGA_PROFILE`, and `GOGA_HOME_PROFILES`
(decoded once; a damaged bundle is one clean pre-run error, no events). The afm launch
environment composes as the ladder
requires: the container's process environment stays untouched, and the composed layer — the
effective task env layer (`pipeline.env`) with the decoded CLI entries applied above it, plus
`GOGA_PROFILE=<effective profile name>` when a profile resolved — passes to `run_flow` as its
`env` parameter, applying to the afm
subprocess only. The `GOGA_PROFILE` export makes the effective profile inheritable: pipeline
stages and any build invoked inside the runtime pick the same profile up through its env
channel with no additional options (the workflow travels via `GOGA_WORKFLOW` of the launch
environment). Keys of `pipeline.env` and the CLI entries colliding with the engine set —
`GOGA_PROFILE`, `GOGA_WORKFLOW`, `GOGA_HOME_PROFILES`, `GOGA_EXTRA_ENV`, `AFM_DIR`,
`AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` — are dropped silently
from the layer; the inherited launch values stand. Run options (the workflow decision, the
profile flag, the skip names, the parallel cap) never travel through the environment; they
arrive as parameters from the CLI.

## Threading chains (host → container)

    goga pipeline NAME --parallel N
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → pipeline_cli: parallel = N
          → run_pipeline(…, parallel=N)
            → run_flow(…, max_parallel=N)
              → afm run --port PORT --max-parallel N <flow>

    goga pipeline NAME -e KEY=V
      → docker run … -m goga.pipeline run NAME --port PORT
        (env-file: home.env, git identity, KEY=V, engine variables, GOGA_EXTRA_ENV)
        → pipeline_cli → run_pipeline
          → run_flow(…, env={**effective pipeline.env, "KEY": "V"})
            → afm runs with KEY=V overriding the pipeline.env value

    goga pipeline NAME -w hardening -s build -s test
      → docker run … -m goga.pipeline run NAME --port PORT -w hardening -s build -s test
        → pipeline_cli: workflow="hardening", skip=["build", "test"]
          → run_pipeline(…, workflow="hardening", skip=["build", "test"])

    goga pipeline NAME -p mixa
      → docker run … -m goga.pipeline run NAME --port PORT --profile mixa
        (env-file: …, GOGA_PROFILE=<ambient>, GOGA_HOME_PROFILES=<encoded bundle>)
        → pipeline_cli: profile="mixa"
          → run_pipeline(…, profile="mixa") — the workflow renders with the profile;
            the afm launch layer carries GOGA_PROFILE=mixa

Absent flag ⇒ None ⇒ auto-match / no skip / no profile / unbounded. Absent `-e` ⇒ empty
payload ⇒ the task env layer alone.
