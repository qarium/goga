# In-Container goga Runs, Tool-Assistant Overrides, and Environment-Driven Configuration

## Problem

goga pipelines and builds are executed inside the goga Docker image in CI, and
workflows consume assistants delivered by tool packages — but five gaps in the
current product prevent these users from completing their work:

1. **In-container commands.** Inside the goga Docker image (a CI job),
   `goga pipeline` and `goga build` still behave as host-side launchers: they
   require the docker CLI and attempt to launch a nested goga container, which
   fails. The only workaround is to know and invoke the internal entrypoints
   (`python -m goga.pipeline`, `python -m goga.build`) directly — the normal
   command surface does not exist inside the environment it creates.

2. **Tool-delivered assistants.** A tool package delivers a workflow assistant
   (its prompt, skills, and launch settings), but the project cannot configure
   the launch of that assistant. Today the user cannot change *anything*: an
   authored workflow entry with the same name fully displaces the tool's entry
   (and restating the tool's content is required to author one at all), while
   not authoring one leaves the tool's fixed agent and env in effect. The
   delivered assistant therefore cannot be adapted to the project's own agents
   and environment.

3. **Static configuration values.** Project configuration and tool
   configuration are purely literal: an environment-specific value (for
   example, which pipeline agent to use) must be hardcoded per checkout or
   rewritten by external tooling, so one committed configuration file cannot
   serve multiple environments such as CI and developer machines.

4. **Ungoverned stage addition.** The afm engine's dashboard allows adding
   stages to a running flow, but a goga-managed run's stage set is compiled
   from the pipeline file and workflow; a stage added through the dashboard
   escapes that compiled model and is unknown to goga's plumbing. The generated
   engine configuration does not disable this capability.

5. **Silent stage failure.** When a stage fails, the `goga pipeline` invocation
   does not end with an error exit status, so CI and other automation cannot
   detect the failure from the exit code and proceeds as if the run succeeded.

## Users

- **Developer / DevOps engineer running goga in CI (primary).** Runs
  `goga pipeline` and `goga build` inside the goga Docker image in a CI job.
  Needs the normal commands to work there, needs CI to fail when a pipeline
  fails, and needs environment-specific configuration without per-checkout
  file edits.
- **Workflow author (primary).** Authors `.goga/workflows/*.yml` in a project
  that consumes tool packages. Needs tool-delivered assistants to run with the
  project's own agent and env while the tool keeps delivering the content.
- **Tool package author (secondary).** Maintains a tool package that delivers
  workflow assistants. Needs deliveries to keep working in every consuming
  project and to remain meaningful under project customization.
- **Run operator (secondary).** Watches a goga-managed run in the afm
  dashboard. The run's stage set must stay what goga compiled; the dashboard
  must not offer out-of-model stage addition on goga-managed runs.

## Goals

1. **Uniform command surface.** Developers and DevOps engineers can run the
   product's pipeline and build commands with the same `goga pipeline` /
   `goga build` invocations on the host and inside the goga container — no
   knowledge of internal entrypoints, no nested container launch.
2. **Adaptable tool-delivered assistants.** A workflow author can configure the
   launch of an assistant delivered by a tool (its agent, env — any field),
   while the tool's delivered content keeps flowing to the project.
3. **Environment-driven configuration.** Project and tool configuration can
   take scalar values from the environment at load time, so one committed
   configuration file serves multiple environments.
4. **Governed run integrity.** Goga-managed runs express their compiled stage
   model to the engine, so out-of-model stage addition is unavailable on them.
5. **Trustworthy failure signaling.** A pipeline run in which a stage fails
   ends the `goga pipeline` invocation with an error status that automation
   can gate on.

## User Experience

### Running goga inside the container

- **Entry.** A CI job inside the goga Docker image invokes `goga pipeline`
  (any form: list, overview, card, run) or `goga build`.
- **Primary path.** The command recognizes that it is already inside the goga
  environment and performs the requested operation directly in the current
  environment — the same operation, with the same output, that the container
  launcher performs. No container launch is attempted; the docker CLI is not
  required.
- **Operation parameters** that belong to the operation itself (for the run
  form: `--workflow` / `--no-workflow`, `--profile`, `--skip`, `--parallel`,
  `--fail-on-error`) keep working on this path.
- **Failure path — host-only options.** An option whose effect belongs to
  container launching (`-t/--topic` with `--todo`, `--update`, `-e/--env`,
  `--add-host`, `--proxy`) passed on the in-container path produces an explicit
  error naming the option and stating it is available only on the host.
  Nothing is silently ignored.
- **Host unchanged.** On the host, both commands behave exactly as today
  (container launch, image acquisition, topic switching, profile carriage).

### Configuring a tool-delivered assistant

- **Entry.** A workflow author edits the project's workflow file; a tool
  delivers an assistant under a name the project uses.
- **Primary path.** The author writes an assistant entry under the same name.
  Every field the entry specifies overrides the tool's value; every field it
  omits is inherited from the tool's delivered entry. The assistant runs with
  the project's agent and env while its content keeps coming from the tool —
  tool updates to non-overridden fields remain effective on later runs.
- **Alternative.** An authored entry that names no tool-delivered assistant is
  a standalone declaration and keeps today's rules (its own content required).
- **Failure path.** An override-style entry (no content of its own) that names
  an assistant no tool delivers stops pipeline compilation with a readable
  error naming the assistant. Other authoring mistakes keep producing today's
  structural and compilation errors.

### Environment-driven configuration values

- **Entry.** A configuration author edits `.goga/config.yml` or a tool config,
  authoring a scalar value as an environment reference (`pipeline.agent`
  referencing an environment variable, for example).
- **Primary path.** At load, the value resolves from the referenced
  environment variable.
- **Failure path.** When the variable is unset, the value resolves to the
  empty string, and each field's existing empty-value semantics apply (an
  empty `pipeline.agent` behaves as absent, for example). Malformed use is a
  structural configuration error as today. Home configuration is unchanged.

### Governed stage set

- **Entry.** An operator opens the afm dashboard of a goga-managed run.
- **Behaviour.** Adding stages is unavailable; the run's stage set stays
  exactly what goga compiled.

### Failing the run on stage failure

- **Entry.** A user runs the run form of `goga pipeline` with the
  fail-on-error flag.
- **Primary path.** The run proceeds as today; when a stage fails, the run
  ends and the invocation exits with an error status — CI stops.
- **Without the flag**, exit behavior is unchanged. The failing stage remains
  visible in the dashboard and logs as today; the exit status is the new
  signal.

## Requirements

### R1. In-container command execution

- **R1.1.** `goga pipeline`, invoked inside the goga container environment,
  must perform the requested operation (list, overview, card, run) directly in
  the current environment, without requiring the docker CLI and without
  launching another container.
- **R1.2.** `goga build`, invoked inside the goga container environment, must
  perform the build directly under the same rule.
- **R1.3.** Detection of the in-container environment must use the product's
  established in-image marker — no new heuristics.
- **R1.4.** On the in-container path, a host-only option — `-t/--topic` (and
  `--todo`, which requires it), `--update`, `-e/--env`, `--add-host`,
  `--proxy` — must fail with an explicit error naming the option and stating
  it is host-only. This set is exhaustive; options not listed keep their
  meaning on this path.
- **R1.5.** Host-side behavior of both commands must remain unchanged.

### R2. Configuring tool-delivered assistants via the workflow file

- **R2.1.** An authored assistant entry in the workflow file — a top-level
  catalog entry or an inline stage declaration — whose name matches a
  tool-delivered assistant acts as a partial override: each field the entry
  specifies (any of `agent`, `env`, `delegate`, `prompt`, `skills`) overrides
  the tool's delivered value; each field it omits is inherited from the
  delivered entry. Field presence decides — an explicitly authored empty value
  (`skills: []`, `env: {}`) is an override, not an omission.
- **R2.2.** Non-overridden fields keep flowing from the tool: the tool's later
  changes to those fields remain effective on subsequent runs.
- **R2.3.** An override-style entry (no `prompt` and no `skills` of its own)
  that names an assistant no tool delivers is a pipeline compilation error
  with a readable message naming the assistant.
- **R2.4.** An entry that carries its own `prompt` or `skills` and names no
  tool-delivered assistant is a standalone declaration and keeps the existing
  standalone rules.
- **R2.5.** When several tools deliver the same name, the existing precedence
  rule (the later tool wins) applies first; the authored override then applies
  on top of the winning delivered entry.
- **R2.6.** The merged effective assistant must still produce a valid launch:
  when the effective entry resolves no agent at all, the existing pre-run
  error behavior applies.
- **R2.7.** Stage attachments keep their existing semantics (`when` required,
  optional `gate`, references and inline declarations).

### R3. Environment-variable scalars in configuration

- **R3.1.** In project configuration (`.goga/config.yml`) and tool
  configuration, any scalar value may be authored as an environment reference
  `!ENV NAME`; at load it resolves to the value of the environment variable
  `NAME`.
- **R3.2.** When the variable is unset, the value resolves to the empty
  string; each field's existing empty-value semantics then apply.
- **R3.3.** Home configuration (`~/.goga/config.yml`) does not gain the
  environment reference — its loader and behavior stay unchanged.
- **R3.4.** Malformed use — the reference in a non-scalar position (a mapping,
  a list, a key) or a malformed argument — is a structural configuration
  error, consistent with existing loader errors (readable, naming the
  location).

### R4. Disabling stage addition on goga-managed runs

- **R4.1.** The afm configuration goga generates for a managed run must
  disable the engine's stage-addition capability (`add_stage` with
  `enabled: false`).
- **R4.2.** The setting is static for goga-managed runs — not configurable
  through project configuration or the CLI, like the other fixed launcher
  fields.
- **R4.3.** The stage set presented to the engine stays exactly the compiled
  pipeline (pipeline file plus workflow contributions).

### R5. Fail-on-error for the pipeline run

- **R5.1.** The run form of `goga pipeline` must accept a `--fail-on-error`
  flag.
- **R5.2.** With the flag, when a stage fails, the run ends and the
  `goga pipeline` invocation exits with an error (non-zero) status.
- **R5.3.** Without the flag, exit behavior stays as today; with the flag and
  no failing stage, the invocation exits successfully.
- **R5.4.** The flag is a run-form parameter, available through the
  in-container path like the other run parameters; the list, overview, and
  card forms are unaffected.

## Constraints

- **C1. Host behavior is preserved.** The host-side launch flow of both
  commands (image acquisition, port allocation, topic switching, profile and
  file-root carriage) is established behavior and must not change; the
  in-container path is an addition.
- **C2. Established in-image marker.** In-container detection uses the
  product's existing in-image environment marker.
- **C3. Home configuration untouched.** The environment reference is not added
  to home configuration (explicit product decision).
- **C4. One authoring model.** Assistant overrides extend the established
  workflow authoring model (name-keyed entries, attachment parameters,
  readable structural and compilation errors); no parallel authoring syntax
  or second configuration channel is introduced.
- **C5. Engine as shipped.** goga rides the external afm engine; the solution
  must work with the engine's existing capabilities (its exit-on-fail run
  option and its add-stage configuration) — no engine changes.
- **C6. Generated engine configuration is governed.** The afm configuration
  goga writes is product-owned; its fixed launcher fields are not
  project-configurable, and the stage-addition setting joins that static set.
- **C7. Tool delivery contract intact.** Tools deliver workflow amendments
  through the established delivery mechanism with its existing commit/discard
  and failure semantics; only the merge outcome for same-name assistants
  changes.
- **C8. Non-colliding authoring unchanged.** Workflows and configurations
  that do not use the new capabilities keep working unchanged, with no
  migration. Same-name collision semantics intentionally change from full
  displacement to partial override (explicit product decision).

## Scope

### In Scope

- In-container direct execution of `goga pipeline` (list, overview, card,
  run) and `goga build`, with explicit errors for host-only options.
- Partial override of tool-delivered assistants from workflow entries
  (catalog and inline), with inheritance of unspecified fields and a
  compilation error for unknown override names.
- The `!ENV NAME` scalar in project configuration and tool configuration,
  with empty-string resolution for unset variables.
- Static `add_stage: enabled: false` in the generated afm configuration.
- The `--fail-on-error` run-form flag with error exit on stage failure,
  carried through host and in-container paths.
- User-facing documentation of the changed and added authoring and CLI
  surfaces (the product's usage documents).

### Out of Scope

- `!ENV` support in home configuration.
- Making the stage-addition setting configurable (project or CLI).
- Changes to the host-side docker launch flow or image acquisition.
- Changes to the afm engine itself; only its existing flags and configuration
  are consumed.
- A second configuration channel for assistant settings (project-config
  section or similar) — the workflow file is the channel.
- Changes to the tool delivery protocol (hooks platform, commit/discard,
  hard/soft action classes).
- Extending `--fail-on-error` to other commands (`goga build` keeps its own
  exit semantics).
- Migration tooling for existing workflows; dedicated coordination for runs
  spawned from inside stages; goga-side dashboard or GUI changes.

## Success Criteria

- **SC1.** Inside the goga container environment with no docker CLI
  available, `goga pipeline <name>` (run form) executes the pipeline
  directly and completes; the list, overview, and card forms work through the
  same direct path; `goga build` builds directly.
- **SC2.** On the in-container path, each host-only option (`-t/--topic`,
  `--todo`, `--update`, `-e/--env`, `--add-host`, `--proxy`) fails with an
  error naming the option; nothing is silently ignored.
- **SC3.** On the host, both commands behave exactly as before the change.
- **SC4.** With a tool delivering assistant `X` (content plus a default
  agent) and a workflow entry for `X` specifying `agent` (and/or `env`), the
  run starts `X` with the authored agent/env while `X`'s content comes from
  the tool; an entry specifying `prompt` replaces the tool's prompt, and
  unspecified fields still flow from the tool.
- **SC5.** An override-style entry naming an assistant no tool delivers stops
  compilation with a readable error naming the assistant; workflows without
  tool-name collisions compile to the same result as before the change.
- **SC6.** Project configuration with `pipeline.agent: !ENV PIPELINE_AGENT`
  and `PIPELINE_AGENT` set uses the referenced agent; with the variable
  unset, the configuration loads and the field behaves as its established
  absent/empty semantics; tool configuration resolves the reference the same
  way; home configuration behavior is unchanged.
- **SC7.** The afm configuration generated for a goga-managed run carries the
  disabled stage-addition setting, and the run's dashboard does not accept
  stage addition.
- **SC8.** `goga pipeline <name> --fail-on-error` exits non-zero when a stage
  fails, exits successfully when no stage fails, and the same pipeline
  without the flag exits as before the change.
