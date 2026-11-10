# Pipeline Settings Calibration

Direct in-container execution, assistant partial overrides, environment-driven
configuration scalars, a governed stage set, and fail-on-error signaling for
`goga pipeline` / `goga build`. The task implements the five decisions of the
approved [adr.md](adr.md) against the product definition in [prd.md](prd.md).

## Current State

The project's pipeline/build launch and settings path operates as follows
(verified against the code):

- **Launch surface.** `goga pipeline` (cell `goga/commands/pipeline`) and
  `goga build` (cell `goga/commands/build`) are host-side launchers: they
  check the docker CLI, compose the in-container argv
  (`python3 -m goga.pipeline run NAME --port N …` / `python3 -m goga.build …`)
  and the env-file contract, and launch via `DockerRunner` (cell `goga/docker`).
  Inside the goga image — where the established in-image marker
  `GOGA_DOCKER=1` is set and the `ensure_in_docker` guard (cell `goga/docker`)
  enforces it for internal entrypoints — the normal commands still require
  the docker CLI and attempt a nested container launch, which fails. Only the
  internal entrypoints work there.
- **Assistant collisions.** `merge_workflow_overlay` (cell
  `goga/pipeline/hooks`) treats every authored assistant name as unbeatable:
  a tool contribution under the same name is fully displaced (the authored
  entry passes verbatim, the tool's content is lost), and tool inline
  declarations under an authored name are silently dropped. The workflow
  parser (cell `goga/pipeline/workflow`) rejects a catalog entry carrying
  neither `prompt` nor `skills`.
- **Configuration scalars.** `load_project_config` (cell
  `goga/config/project`) and `load_tool_config` (cell `goga/config/tool`) read
  their files with plain `yaml.safe_load` — values are purely literal; one
  committed file cannot serve multiple environments. The home-config loader
  (cell `goga/config/home`) stays on `safe_load` by explicit product decision.
- **Stage set governance.** `write_afm_config` (cell `goga/pipeline`) writes
  the client block, four static launcher fields (`theme`, `open_browser`,
  `proxy.enabled`, `prompts_dir`), the observer-hook registration, and the
  collaboration plumbing — but no `add_stage` field, so the afm engine's
  dashboard still offers out-of-model stage addition on goga-managed runs.
- **Failure signaling.** The run form has no `--fail-on-error` flag;
  `pipeline_cli` (cell `goga/pipeline`) and `run_flow` (cell `goga/afm`) never
  pass the engine's `--exit-on-fail` flag, so a failed stage does not end the
  `goga pipeline` invocation with an error exit status. The engine's exit code
  itself already propagates verbatim.

## Description

Implement the five settled decisions so that the normal commands work directly
inside the goga container, tool-delivered assistants become project-configurable
through partial overrides, configuration scalars resolve from the environment,
goga-managed runs disable engine-side stage addition, and a failing stage fails
the `goga pipeline` invocation:

1. **Direct in-container execution reuses the launcher's own composition.** The
   Click commands keep composing exactly today's in-container command line and
   env contract; when `GOGA_DOCKER=1` is present, that command is executed
   directly as a child process in the current environment instead of through
   `docker run` — the docker-CLI check is not performed, the port is still
   allocated and passed as today. The same subprocess is spawned (not the
   operation functions in-process): one execution substrate, identical
   behavior/output on both surfaces. Host-only options (`-t/--topic`, `--todo`,
   `--update`, `-e/--env`, `--add-host`, `--proxy`) fail with an explicit error
   naming the option; `--clean` keeps its meaning (wipes the in-container
   `AFM_DIR`); `--dry-run` on the direct path prints the command it would run.
2. **Same-name assistant entries become partial overrides instead of
   displacement.** The field-level merge lives in the existing workflow overlay
   merge: the winning delivered entry (the unchanged later-tool-wins rule among
   tools) is the base, and every field the authored entry specifies (`agent`,
   `env`, `delegate`, `prompt`, `skills`) replaces the base value while omitted
   fields keep flowing from the tool. Field presence decides — an explicitly
   authored empty `skills: []` / `env: {}` is an override; the workflow model
   preserves "explicitly empty" versus "not authored" (`None`), and downstream
   consumers key env effects on a non-empty effective map. The parser accepts
   entries with neither `prompt` nor `skills`; the content requirement moves to
   compilation, where an effective entry resolving no `prompt` and no `skills`
   — including an override naming an assistant no tool delivers — fails with a
   readable error naming the assistant and its authoring site through the
   existing structural-error channel. An assistant name stays owned by one
   authoring surface (catalog or one inline declaration); tool inline
   declarations under an authored name remain silently dropped.
3. **`!ENV NAME` is a registered YAML scalar constructor, not a preprocessing
   step.** The project-config and tool-config loaders resolve the tag through
   the yaml library's standard constructor mechanism at load time; the
   home-config loader stays on plain `yaml.safe_load`. The resolved value is
   always a string — no type coercion; an unset variable resolves to `""` and
   each field's existing validation and empty-value semantics apply. Malformed
   use is reported by the yaml library's own error machinery (constructor
   errors carry the file position).
4. **`add_stage: {enabled: false}` is a static field of the generated afm
   config.** `write_afm_config` writes it unconditionally next to the four
   existing static launcher fields — product-owned and non-configurable; the
   stage set presented to the engine stays exactly the compiled pipeline.
5. **`--fail-on-error` maps onto the engine's native `afm run --exit-on-fail`
   flag.** The run-form flag is carried inside the composed in-container argv,
   threaded through the in-container CLI to the engine launch, and added as an
   explicit argv flag (visible in the process listing) rather than the
   `AFM_EXIT_ON_FAIL` environment variable. No new exit machinery is
   introduced — the engine's exit code already propagates verbatim.

## Scope

**In scope:**

- In-container direct execution of `goga pipeline` (list, overview, card, run)
  and `goga build` gated on `GOGA_DOCKER=1`, with explicit errors for
  host-only options, `--clean` semantics, and `--dry-run` on the direct path.
- Partial override of tool-delivered assistants from workflow entries (catalog
  and inline): field-level merge with inheritance of unspecified fields,
  parser relaxation for override-style entries, and the compile-time content
  check with a readable error for unknown override names.
- The `!ENV NAME` scalar tag in project configuration and tool configuration
  via the yaml constructor mechanism, with empty-string resolution for unset
  variables and library-native error handling.
- Static `add_stage: {enabled: false}` in the generated afm configuration.
- The `--fail-on-error` run-form flag with error exit on stage failure,
  carried through host and in-container paths as the engine's `--exit-on-fail`
  argv flag.
- User-facing documentation of the changed and added surfaces in the product's
  usage documents.

**Out of scope:**

- `!ENV` support in home configuration.
- Making the stage-addition setting configurable (project or CLI).
- Changes to the host-side docker launch flow or image acquisition.
- Changes to the afm engine itself; only its existing flags and configuration
  are consumed.
- A second configuration channel for assistant settings (project-config
  section or similar) — the workflow file is the channel.
- Changes to the tool delivery protocol (hooks platform, commit/discard, hard
  and soft action classes).
- Extending `--fail-on-error` to other commands (`goga build` keeps its own
  exit semantics).
- Migration tooling for existing workflows; dedicated coordination for runs
  spawned from inside stages; goga-side dashboard or GUI changes.

## Acceptance Criteria

- **SC1.** Inside the goga container environment with no docker CLI available,
  `goga pipeline <name>` (run form) executes the pipeline directly and
  completes; the list, overview, and card forms work through the same direct
  path; `goga build` builds directly.
- **SC2.** On the in-container path, each host-only option (`-t/--topic`,
  `--todo`, `--update`, `-e/--env`, `--add-host`, `--proxy`) fails with an
  error naming the option; nothing is silently ignored.
- **SC3.** On the host, both commands behave exactly as before the change.
- **SC4.** With a tool delivering assistant `X` (content plus a default agent)
  and a workflow entry for `X` specifying `agent` (and/or `env`), the run
  starts `X` with the authored agent/env while `X`'s content comes from the
  tool; an entry specifying `prompt` replaces the tool's prompt, and
  unspecified fields still flow from the tool.
- **SC5.** An override-style entry naming an assistant no tool delivers stops
  compilation with a readable error naming the assistant; workflows without
  tool-name collisions compile to the same result as before the change.
- **SC6.** Project configuration with `pipeline.agent: !ENV PIPELINE_AGENT`
  and `PIPELINE_AGENT` set uses the referenced agent; with the variable unset,
  the configuration loads and the field behaves as its established absent/empty
  semantics; tool configuration resolves the reference the same way; home
  configuration behavior is unchanged.
- **SC7.** The afm configuration generated for a goga-managed run carries the
  disabled stage-addition setting, and the run's dashboard does not accept
  stage addition.
- **SC8.** `goga pipeline <name> --fail-on-error` exits non-zero when a stage
  fails, exits successfully when no stage fails, and the same pipeline without
  the flag exits as before the change.
- All tests pass (`pytest tests/ -x`) and lint is clean (`ruff check goga/`),
  per the project conventions.

## Stack

- **Frameworks:** none beyond the existing CLI framework — click (host-side
  commands and the new run-form flag).
- **Libraries:** PyYAML (the `!ENV` scalar-tag constructor mechanism in the
  project and tool config loaders); Python 3.10+ stdlib (`subprocess` for the
  direct child execution and the engine launch, `socket` for port allocation,
  `argparse` for the in-container CLI, `dataclasses` kw_only for the assistant
  model's explicit-empty vs `None` discipline, `os.environ` for tag
  resolution).
- **Infrastructure:** the external `afm` engine binary v2.0.9 as shipped in
  the goga image (consumed read-only: `afm run --exit-on-fail`, config field
  `add_stage.enabled`); the goga Docker image (marker `GOGA_DOCKER=1`); pytest
  and ruff for tests and lint per the project conventions.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| afm engine (v2.0.9) | `.goga/usages/cooks/afm.md` | updated (this topic: the `--exit-on-fail` run flag and the `add_stage` config field) |
| PyYAML constructor mechanism | `.goga/usages/cooks/yaml_env_constructor.md` | created (this topic) |
| click | `.goga/usages/cooks/click.md` | existing |
| project conventions | `.goga/usages/conventions.md` | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- **C1. Host behavior is preserved.** The host-side launch flow of both
  commands (image acquisition, port allocation, topic switching, profile and
  file-root carriage) must not change; the in-container path is an addition.
- **C2. Established in-image marker.** In-container detection uses only
  `GOGA_DOCKER=1` — no new heuristics.
- **C3. Home configuration untouched.** The `!ENV` tag is not added to home
  configuration (explicit product decision).
- **C4. One authoring model.** Assistant overrides extend the established
  workflow authoring model (name-keyed entries, attachment parameters,
  readable structural and compilation errors); no parallel authoring syntax.
- **C5. Engine as shipped.** Only shipped afm capabilities are consumed; no
  engine changes.
- **C6. Generated engine configuration is governed.** The afm configuration
  goga writes is product-owned; `add_stage` joins the static launcher fields
  and is not project-configurable.
- **C7. Tool delivery contract intact.** Only the merge outcome for same-name
  assistants changes; delivery mechanics, commit/discard, and failure
  semantics stay.
- **C8. Non-colliding authoring unchanged.** Workflows and configurations not
  using the new capabilities keep working unchanged, no migration. Same-name
  collision semantics intentionally change from full displacement to partial
  override — workflows that restated a tool's content under the same name keep
  compiling but now also inherit unspecified fields from the tool (documented,
  accepted).
- **Model discipline.** The workflow model must preserve "explicitly empty"
  versus "not authored" (`None`) for `env` and `skills`; downstream consumers
  key env effects on a non-empty effective map — regression here silently
  changes override semantics.
- **One substrate.** The direct path spawns the same composed subprocess as
  the container path; divergence between the two surfaces is a defect.

## Scope Estimate

Single task — no decomposition. The five decisions form one cohesive
calibration of the same run path; D1 (direct execution) and D5
(`--fail-on-error`) share the launch-composition files and cannot be cleanly
separated; every other piece is small. Decided with the product owner in the
specify interview.

## Existing Architecture

Affected cells and their role in the task (facts, per the schema):

- `goga/commands/pipeline` — host-side pipeline launcher: the Click command's
  option surface (gains `--fail-on-error` on the run form; host-only options
  gain the direct-path rejection), `run_pipeline_container` /
  `run_pipeline_info_container` (the direct-execution branch reuses their
  composed argv/env), `_compose_run_args` (carries the new flag).
- `goga/commands/build` — host-side build launcher; gains the same direct
  execution branch for `GOGA_DOCKER=1` (its host-only options fail likewise).
- `goga/docker` — provides the in-image marker guard (`ensure_in_docker`,
  `GOGA_DOCKER=1`) and the env-carriage codecs (`encode_extra_env`,
  `decode_extra_env`); imported by both command cells and by `goga/pipeline`.
- `goga/pipeline` — the in-container coordination: `pipeline_cli` (argparse
  surface gains the flag), `run_pipeline` (threads the flag to the engine
  launch), `write_afm_config` (gains the fifth static field `add_stage`).
- `goga/pipeline/hooks` — `merge_workflow_overlay` and the catalog/stage merge
  helpers implement the field-level override (the authored namespace stops
  being unbeatable; the delivered entry becomes the merge base).
- `goga/pipeline/workflow` — `parse_workflow` relaxes the prompt-or-skills
  requirement for override-style entries; `WorkflowAssistant` carries the
  explicit-empty vs `None` discipline the merge relies on.
- `goga/pipeline/compiler` — `compile_flow` performs the moved content check:
  an effective assistant entry resolving no `prompt` and no `skills` fails
  through the existing `StructuralError` channel, naming the assistant and its
  authoring site.
- `goga/afm` — `run_flow` composes the `afm run` launch and gains the
  `--exit-on-fail` argv flag; exit-code propagation is unchanged.
- `goga/config/project` — `load_project_config` loads through the
  `!ENV`-aware yaml loader (home config explicitly excluded).
- `goga/config/tool` — `load_tool_config` loads through the `!ENV`-aware yaml
  loader.

Cell link connections that the task rides (per the schema dependency graph):
`goga/commands/pipeline` → `goga/docker`, `goga/config`, `goga/pipeline`
(usages only), `goga/pipeline/workflow`, `goga/runtime`, `goga/topics`;
`goga/commands/build` → `goga/build`, `goga/docker`, `goga/config`,
`goga/pipeline/workflow`, `goga/runtime`; `goga/pipeline` → `goga/afm`
(`run_flow`), `goga/config` (`load_project_config`), `goga/docker`
(`decode_extra_env`, `ensure_in_docker`), `goga/pipeline/compiler`,
`goga/pipeline/hooks`, `goga/pipeline/workflow`; `goga/pipeline/compiler` →
`goga/pipeline/workflow`; `goga/pipeline/hooks` → `goga/pipeline/workflow`.
No new cell is created and no import edge changes direction; the task modifies
behavior inside existing cells.

## Notes

- Source documents: the approved [adr.md](adr.md) (five decisions, settled
  2026-11-02) and [prd.md](prd.md) (R1–R5, C1–C8, SC1–SC8). Where this task
  document and the ADR differ in wording, the ADR's decision text governs.
- The afm usage doc (`.goga/usages/cooks/afm.md`) was updated with the two
  engine facts (`--exit-on-fail`, `add_stage`) and the yaml constructor usage
  (`.goga/usages/cooks/yaml_env_constructor.md`) was created during the
  specify stage of this topic.
- The engine facts were verified against the shipped afm v2.0.9 binary
  (`--exit-on-fail` in `afm run --help`; `add_stage` with a nested `enabled`
  yaml field in the binary).
- No code examples and no new architecture are prescribed here — the
  implementing stages apply the cell contracts and the ADR decisions.
