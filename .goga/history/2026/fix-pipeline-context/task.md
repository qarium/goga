# Split the run context from the host launch context (pipeline and build)

## Current State

Two domains launch work into the goga Docker image, and in both the project
configuration is out of reach of the image's tool packages at the moment it matters.

**Pipeline.** The host command (`goga/commands/pipeline`) loads the authored
configuration, delivers the `amend_config` checkpoint, and consumes the effective
configuration for the docker-level launch fields and the structural pipeline-section
guard. The host then bakes the run parameters into the launch: `pipeline.env` is
written into the container env-file, and `pipeline.agent` is resolved on the host into
a read-only afm-config tmpfile bind-mounted at `/home/goga/.afm/config.yaml`. The
in-container run coordination (`goga/pipeline::run_pipeline`) loads no configuration at
all — tool packages installed in the image never receive the `amend_config` delivery
and cannot influence the run's env or agent.

**Build.** The host command (`goga/commands/build`) delivers `amend_config` for its
fields; both guards — "build section is required" (structural) and "build.agent is
required" (value) — run on the host. The in-container entrypoint
(`python -m goga.build`) loads the authored configuration directly and delivers no
checkpoint (the documented rule "in-container loads stay authored-only" in
`goga/config/hooks/.usages/checkpoints.md`); no tool can influence `build.env` or
`build.agent`.

**Env ladder defect.** In the build domain the CLI `-e` entries travel in the env-file,
and the tasks-pass env layer (`build.env`) is applied in-container by `run_ralphex` on
top of the inherited process environment — the task env layer beats explicit CLI
input, the wrong precedence. In the pipeline domain `pipeline.env` sits in the env-file
below git identity, so the env afm runs with never reflects the effective (amended)
configuration.

## Description

Implement the accepted ADR (`.goga/history/2026/fix-pipeline-context/adr.md`): split
the context along the docker launch boundary — the host owns the launch mechanics, the
container owns the run parameters — and deliver `amend_config` at both load moments as
one action with one vocabulary.

- The in-container entrypoints perform load-and-amend: authored `load_project_config`
  → `amend_config` delivered to the image's tool packages → the effective
  configuration feeds everything downstream. Pipeline does it at the start of the run
  coordination, before workflow resolution and `amend_workflow`, in the run form only;
  build does it at its entrypoint.
- The host keeps its delivery, for its fields: the docker-level launch context (image,
  dockerfile, port, mounts, `--add-host`, proxy variables, env-file base layers,
  `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, container name, signal handling) and the
  structural section guards.
- The afm `config.yaml` is written fully in-container; the host stops generating and
  bind-mounting the afm-config tmpfile.
- The task env layer (the effective `pipeline.env` / `build.env` / `build.review.env`)
  is applied in-container between the inherited launch env and the CLI layer, for the
  target binary's launch only.
- The CLI `-e` entries travel twice with one source: they stay in the env-file AND
  travel as a distinguishable payload, so the in-container side applies them above the
  task env layer.
- Guards split by nature: value guards move in-container; structural guards stay
  host-side.
- Failure semantics stay hard and symmetric at both delivery moments.

## Scope

**In scope:**

1. Pipeline in-container run form: load-and-amend at the start of the run coordination
   (before workflow resolution and `amend_workflow`); the listing, overview, and card
   forms load nothing and deliver nothing (unchanged).
2. In-container afm `config.yaml` authorship: the whole file — `client.command`
   resolved from the effective `pipeline.agent` (written only when an agent resolves;
   omitted otherwise so per-stage workflow agents or afm's own defaults cover the
   absent global default), `theme: goga`, `open_browser: false`, `proxy.enabled:
   false`, `prompts_dir: /home/goga/pipeline/prompts` — is written by the in-container
   run coordination before launching afm; the host stops generating and mounting the
   afm-config tmpfile (the run launch shape loses the config-overlay mount).
3. Task env layer in the pipeline domain: `pipeline.env` leaves the host env-file; the
   effective mapping is applied in-container between the inherited launch env and the
   CLI layer, for the afm launch only.
4. CLI `-e` dual carriage, both domains: the entries stay in the env-file AND travel
   as a distinguishable payload (a dedicated engine variable, the
   `AFM_DOCKER_FILE_ROOTS` precedent) so the in-container side applies them above the
   task env layer; one source — the same parsed CLI values in both places.
5. Build in-container load-and-amend: `python -m goga.build` performs the authored
   load, delivers `amend_config`, and feeds the effective configuration to everything
   downstream (settings resolution, agent resolution, env layers).
6. Build guards: the "build.agent is required" value guard moves in-container (the
   effective agent may arrive as a container-side amendment); the "build section is
   required" structural guard stays host-side on the host-effective configuration;
   the pipeline section guard stays host-side likewise.
7. Build env ladder: the CLI `-e` payload is applied above `build.env` /
   `build.review.env` at the pass launch; git identity ends up below the task env
   layer (both domains).
8. One action, two moments: `amend_config` is not split by environment — the same
   path vocabulary and amendment semantics on the host and in the container; a
   contribution commits into the effective configuration of the moment that delivered
   it; contributions into the other side's fields stay applied but unconsumed,
   silently (visible through the summary lines, never a warning).
9. Failure semantics: hard and symmetric — the first failing tool at either delivery
   moment stops the command with a clean error naming the tool and the action; the
   target binary (afm / ralphex) never launches; the amendment summary lines print to
   stderr; configuration values never appear in any output.
10. Env ladder, both domains, fixed as: home.env < git identity < task env layer
    (effective) < CLI `-e` < engine variables (`AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`,
    `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`); engine variables are launch mechanics
    nothing overrides.

**Out of scope:**

- The concrete contract shapes, the payload variable name and encoding, and the cell
  boundaries of the new delivery — design-stage work; this task fixes the
  requirements (distinguishable carriage, one source, the ladder), not the shapes.
- Behavior of the listing, overview, and card forms (they load nothing, deliver
  nothing — unchanged).
- The home configuration load (stays authored-only, closed surface).
- The `afm` and `ralphex` binaries themselves (external repositories).
- The user-facing CLI surface: no new flags, no flag semantics changes.
- The loader `load_project_config` (stays authored-only and hooks-free; load-and-amend
  composes around it).

## Acceptance Criteria

- With a tool package installed in the image contributing to `pipeline.env` /
  `pipeline.agent` (container-side fields), a `goga pipeline NAME` run applies the
  contribution: the afm `config.yaml` carries the effective agent, and the afm launch
  env carries the effective task env layer.
- With a tool package contributing to docker-level fields (image, proxy, hosts) from
  inside the container, the contribution stays applied-but-unconsumed: the run
  proceeds with the host-resolved launch values, silently, no warning.
- A host-side tool contribution into `pipeline.env` / `pipeline.agent` becomes inert
  (the host no longer consumes those fields).
- `goga build PLAN -e KEY=VALUE` with `build.env` (or `build.review.env`) carrying
  KEY: the CLI value wins at the respective pass launch.
- `goga pipeline NAME -e KEY=VALUE` with `pipeline.env` carrying KEY: the CLI
  value wins at the afm launch (the task env layer applies in-container, the CLI
  payload above it).
- The env-file CLI entries and the distinguishable payload never diverge — both
  compose from the same parsed CLI values on every launch.
- A container-side amendment supplying `build.agent` on a config whose authored agent
  is unset passes the in-container agent guard and runs.
- A config with no `build` section still fails on the host with the structural guard,
  before any docker activity.
- The first failing tool at either delivery moment stops the command with a clean
  error naming the tool and the action; afm / ralphex never launch; no configuration
  value appears in any output (summary lines carry tool, path, set/forced only).
- The listing, overview, and card forms behave exactly as before (no config load, no
  delivery, no run events).
- The card still composes exactly as a run with the same workflow/skip flags (the
  shared compilation machine and the `amend_workflow` layer are untouched).

## Stack

- **Frameworks:** none — Python 3.10+ standard library only for the new logic
  (`dataclasses`, `argparse`, `subprocess`, `pathlib`)
- **Libraries:** the existing project stack — click (host commands, unchanged
  surface), the existing YAML loader; payload encoding via stdlib `json` + `base64`
  (the `AFM_DOCKER_FILE_ROOTS` precedent)
- **Infrastructure:** Docker — the existing `DockerRunner`; the run launch shape loses
  the config-overlay mount, everything else unchanged

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| afm | `.goga/usages/cooks/afm.md` | updated (at formulation) — `config.yaml` authorship moved in-container, the tmpfile flow retired, an "Environment carriage" section added |
| ralphex | `.goga/usages/cooks/ralphex.md` | existing — the `run_ralphex` contract is unchanged; the ladder is applied by the caller |
| click | `.goga/usages/cooks/click.md` | existing — no surface changes |
| agent wrappers | `.goga/usages/cooks/agent-as-claude-wrappers.md` | existing — the naming convention is unchanged; the resolution point moves in-container |

Synced usage files: none exist in the project (`.goga/usages/` holds only
`conventions.md` and `cooks/`).

## Risks and Constraints

- The ADR leaves one design question open: how the task env layer and the CLI payload
  reach the afm launch — `run_flow` inherits the process environment unchanged today.
  The design stage must fix the contract shapes, the payload encoding, and the cell
  boundaries before implementation.
- Dual carriage is one source: the env-file entries and the payload must never
  diverge — both compose from the same parsed CLI values.
- Removing the config-overlay mount changes the docker run shape of the pipeline run
  form; the persistent afm state mount, its cleanup contract, and the signal-handling
  invariant stay.
- Secrecy stays an output-side rule: in-container tool packages now receive the
  authored configuration with env values included — the same read-and-amend view host
  tools get; no value may appear in any output.
- Host-side tool amendments into `pipeline.env` / `pipeline.agent` become inert — a
  behavior change for existing tool packages; documented, never warned.
- The container writes into `~/.afm/` (`config.yaml`) — never into `/workspace` or
  `AFM_DIR` state paths beyond the established prompts contract.

## Scope Estimate

Single task. The mechanism is one shared denominator (the in-container load-and-amend,
the CLI payload carriage, the afm `config.yaml` move, the guard split); the pipeline
and build halves are not independently valuable — the host half without the container
half breaks the run. Decomposition was considered and rejected during formulation
(approved by the user).

## Existing Architecture

Affected cells and their roles in the change:

| Cell | Change |
|------|--------|
| `goga/pipeline` | the run coordination gains the in-container load-and-amend before workflow resolution; writes the afm `config.yaml`; applies the task env layer and the CLI payload around the afm launch (run form only) |
| `goga/commands/pipeline` | stops generating/mounting the afm-config tmpfile and resolving the agent on the host; stops writing `pipeline.env` into the env-file; adds the CLI `-e` payload carriage; keeps the host `amend_config` delivery, the structural pipeline-section guard, and all launch mechanics |
| `goga/build` | the entrypoint gains the in-container load-and-amend; the agent value guard moves here; the pass env layers apply the CLI payload above the task env layer |
| `goga/commands/build` | drops the host-side `build.agent` guard (keeps the structural build-section guard); adds the CLI `-e` payload carriage; keeps the host `amend_config` delivery and launch mechanics |
| `goga/config/hooks` | no contract change to the `amend_config` action itself (one action, one vocabulary); its cell usage is rewritten by the following stages — the "in-container loads stay authored-only" section retires |
| `goga/agents` | no contract change — `resolve_wrapper_path` gains the in-container pipeline consumer: the effective `pipeline.agent` resolves to the wrapper path inside the container for the afm `config.yaml` write (the host command stops resolving it) |
| `goga/afm`, `goga/ralphex` | the point where the composed launch environment is applied. `run_ralphex` keeps its existing `env` layer parameter — the caller composes the ladder (task env layer + CLI payload) through it, contract unchanged; whether `run_flow` gains a layer parameter or the pipeline caller composes is a design-stage decision |

Cell-level usages affected (rewritten by the following stages, listed here as
artifacts): `goga/config/hooks/.usages/checkpoints.md`,
`goga/commands/pipeline/.usages/pipeline-command.md`,
`goga/commands/build/.usages/build.md`, `goga/build/.usages/build-usage.md`,
`goga/pipeline/.usages/run-pipeline.md`, and the `registering-hooks` usages where they
describe delivery moments.

Integration requirements: the host and the container never share Python imports
across the docker boundary (`goga/commands/*` → `goga/pipeline`, `goga/build` is
docker-only); the new in-container delivery goes through the same hooks platform
primitives (the `ConfigHooks` checkpoint surface) as the host one.

## Notes

- Source ADR: `.goga/history/2026/fix-pipeline-context/adr.md` (accepted 2026-09-30).
- The project-level afm cook was updated to the target integration model during task
  formulation (user-approved): `config.yaml` authorship is in-container, the tmpfile
  flow is retired, an "Environment carriage" section fixes the env ladder rule.
- User-approved decisions at formulation: single task covering both domains; the stack
  as listed; the afm cook updated at this stage; cell-level usage files untouched by
  this stage.
