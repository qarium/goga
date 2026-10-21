# Contributor Profiles: personal execution layer for shared processes

## Current State

Contributors to a goga-driven repository each hold their own LLM subscription and agent harness, but the process definitions they run — workflow-files, pipeline-files, `.goga/config.yml` — are shared committed artifacts. The product provides no way to separate the shared process definition from the personal execution layer:

- No profile system exists: no lookup of `.goga/profiles/<name>.yml` (project) or `~/.goga/profiles/<name>.yml` (home), no `--profile` CLI flag, no `GOGA_PROFILE` activation, and no carriage of home profiles into the container (the launcher moves personal data across the boundary only as derived values — the `GOGA_EXTRA_ENV` precedent in `goga/docker`).
- Workflow-files are parsed as plain YAML by `goga/pipeline/workflow` (`parse_workflow`); there is no rendering step before parsing, and jinja2 is not among the declared dependencies in `pyproject.toml`.
- The workflow grammar has no knowledge of a top-level `profile:` key, a per-stage `env` instruction, or a `build:` block.
- Per-stage environment does not exist: afm stage execution resolves through the agent wrapper on two levels — the `client.command` default written by `write_afm_config` (`goga/pipeline`) for stages without an override, and per-stage `command:` overrides composed by `goga/pipeline/compiler` (`compile_flow`) from the workflow stage `agent` as a direct wrapper path. Environment exists only as global layers (`pipeline.agent`, `pipeline.env`). Per-stage needs force contributors to hand-write personal wrapper scripts.
- The build path composes pass settings from `.goga/config.yml` only (`resolve_run_settings`, `compose_pass_options` in `goga/build`); `AdditionalReviewConfig` has no `env` field; task env layers ride the ralphex launch environment; command fields in `.ralphex/config` point at agent wrapper paths directly; a build invoked inside a pipeline runtime cannot inherit the active workflow (no `GOGA_WORKFLOW`).
- The pipeline launch line names the effective workflow but not the profile (`Pipeline running with workflow "<w>"`, `goga/commands/pipeline`); the build path prints no launch line; info/card forms do not activate a profile.

## Description

Implement contributor profiles as accepted in the ADR (`.goga/history/2026/contributor-profile/adr.md`) and specified by the PRD (`.goga/history/2026/contributor-profile/prd.md`). The ADR is authoritative for every design decision listed below; this task adds no new architecture.

A contributor activates a profile — a free-form YAML mapping committed at `.goga/profiles/<name>.yml` (project) or kept personal at `~/.goga/profiles/<name>.yml` (home, project wins on the same name). The active profile's whole content becomes the template context: workflow-files support Jinja template syntax across the whole file, rendered in-container before the standard parsing and structural validation (block tags vanish cleanly; rendering never bypasses validation). Activation precedence is `--profile` > `GOGA_PROFILE` > workflow `profile:` default; with no workflow in effect activation is ignored; templates without activation render with an empty context. Home profiles cross the host/container boundary as one launcher-encoded bundle variable `GOGA_HOME_PROFILES` (base64 compact JSON, the `GOGA_EXTRA_ENV` precedent); a malformed home profile fails strictly on the host before launch. Profile names are strictly validated against a path-component grammar; violations are strict pre-run failures.

The workflow grammar gains a per-stage `env` instruction (`stages.<name>.env` — literal and/or rendered values), delivered by generated per-stage sh closure wrappers that the afm stage `command:` points at (exec chain: stage agent wrapper, else the effective global wrapper, else strict pre-run failure; container-local temp directory). It also gains a top-level `build:` block with a strict six-field set (`agent`, `env`, `review.agent`, `review.env`, `review.additional.agent`, `review.additional.env`); anything else there — including `proxy` and `hosts` — is a structural error, because the host launcher must not read workflow files. Build settings layer `config < workflow build: < CLI`; env maps merge key-wise (workflow keys override same-named config keys, the rest of the config env survives). A new config field `build.review.additional.env` provides an independent env layer for the external reviewer. Every build pass executor (tasks, review, additional) runs through a generated per-role closure wrapper with the decoded CLI entries applied on top; task env layers leave the ralphex launch environment. `GOGA_WORKFLOW` is written only by the pipeline-run launcher and interpreted only by in-container `goga build` (workflow inheritance for builds inside a pipeline runtime); host builds select a workflow only via `-w`, and the CLI flag beats the env value.

Launch feedback extends the existing line design (`Pipeline running with workflow "<w>" and profile "<p>"` / `Build running with workflow "<w>" and profile "<p>"`; with no effective profile the output is unchanged). Info/card forms apply the profile through the same activation channels, with the launcher adding an env-file only when there is something to carry.

## Scope

**In scope:**

- Profile files and resolution: `~/.goga/profiles/` + `.goga/profiles/`, project-wins, `.yml` only, free-form mapping, whole content as template context; strict profile-name validation (path-traversal guard); files-only management.
- Home carriage: `GOGA_HOME_PROFILES` encoded bundle written by the host launcher, decoded in-container; strict host-side failure on a malformed home profile.
- Whole-file Jinja rendering of workflow-files before parsing, with `trim_blocks`, `lstrip_blocks`, `keep_trailing_newline`, and the standard `Undefined`.
- Workflow grammar: top-level `profile:` default; per-stage `stages.<name>.env` (valid only there, not in extend-entries); top-level `build:` block with the strict six-field set.
- Activation: `--profile` on pipeline and build commands, `GOGA_PROFILE` carriage into every launched container, precedence CLI > env > workflow default; explicit `-e GOGA_PROFILE=...` beats the ambient host environment.
- `GOGA_WORKFLOW`: launcher-written alongside `GOGA_PROFILE` and the home bundle, interpreted only by in-container `goga build`; `-w` / `--workflow` on host builds; CLI flag beats the env value; reserved inert names untouched.
- Per-stage env delivery via generated per-stage closure wrappers pointed at by the afm stage `command:`; container-local temp directory; per-stage values layer above all global env layers.
- Build path: `build.review.additional.env` config field; key-wise env merge; settings layering `config < workflow build: < CLI`; uniform per-role closure wrappers for all pass executors (per-role, not per-agent); wrappers regenerated when each pass's `.ralphex/config` is written, in `/tmp/goga-build-env/`; task env layers removed from the ralphex launch env; inert additional layer under the `medium` strategy; `claude_command` as the additional wrapper under `short`.
- Launch feedback lines for pipeline and build; profile activation in info/card forms (env-file added only when there is something to carry).
- Strict pre-run failures with actionable messages (profile name and both lookup locations; malformed profile name and path; Jinja syntax location; post-render structural errors unchanged).
- jinja2 declared as a third-party dependency in `pyproject.toml` with a minimum version.

**Out of scope:**

- CLI subcommands for profile management (list, show, create, validate).
- Templating of pipeline-files (`.goga/pipelines/*.yml`), `.goga/config.yml`, or profile files themselves.
- Extending the info card or describe output with profile analytics (activation only, per the card invariant).
- Secret management beyond file placement (vaults, encryption, rotation).
- New agents or new wrapper scripts shipped by goga; profiles only select among the wrappers the container image ships.
- Interactive fallbacks for missing profiles.
- A template context beyond the single active profile (multi-profile or cross-profile references).
- Modifying the external runners (afm, ralphex) themselves.
- Changes to the reserved inert names `GOGA_WORKFLOW_NAME`, `GOGA_WORKFLOW_DISABLED`, `GOGA_SKIP_STAGES`.

## Acceptance Criteria

- Personal execution (G1): a contributor whose subscription and harness differ from the project default runs a templated workflow — and a build — end-to-end with their personal profile activated, their agent/env values reaching the executing stages, without modifying any committed file.
- Working default (G4): a fresh contributor or CI, with no personal profile, runs a workflow declaring `profile: default` successfully against the committed project profile — no local setup.
- Single point of variance (G2): one committed workflow serves contributors with different subscriptions; only the locally activated profile differs between runs, and the runs exhibit the corresponding distinct behaviour.
- Per-stage environment (G3): a workflow assigns different agents/env to different stages via profile data and `stages.<name>.env`, and the stages execute with those values — with no contributor-written wrapper scripts.
- Strict failures: a run referencing a missing profile (activated or workflow default), a malformed profile file, a Jinja syntax error, or an invalid profile name fails before any stage executes, with actionable messages naming the profile and both lookup locations (or the error location), identically for interactive and CI invocations.
- Backward compatibility: profile-free projects and workflows compile and run identically — byte-identical flow output on the pipeline path (wrappers generated only for stages declaring `env`); on the build path identical effective env delivery and identical results, while `.ralphex/config` command fields point at generated per-role wrappers instead of agent wrapper paths directly.
- Environment propagation: `GOGA_PROFILE` set on the host is available inside the launched container; a build invoked inside a pipeline runtime inherits the pipeline's workflow and profile through `GOGA_WORKFLOW` without additional options.
- Launch feedback: a launch with an effective profile shows the brief line naming the workflow and profile; with no effective profile the output is unchanged.

## Stack

- **Frameworks:** none (Python console application; click CLI framework)
- **Libraries:** click>=8.0 (existing), pyyaml>=6.0 (existing), jinja2>=3.1 (**new** — whole-file workflow rendering)
- **Infrastructure:** none. External execution boundaries (unchanged, not modified): Docker launcher, afm >= 0.4.15 (per-stage `command:` carriage), ralphex (build orchestration, `.ralphex/config` command fields, `custom_review_script`)

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| jinja2 | `.goga/usages/cooks/jinja2.md` | created |
| click | `.goga/usages/cooks/click.md` | existing |
| afm | `.goga/usages/cooks/afm.md` | existing |
| ralphex | `.goga/usages/cooks/ralphex.md` | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task. No synced dependency groups are declared in this project (`goga usages sync` / `goga usages status` report none).

## Risks and Constraints

- **Backward compatibility (amended clause).** Runs and compilations that use no profile features must behave identically to the current product: the pipeline path is byte-identical (stage wrappers are generated only for stages that declare `env`); the build path is behaviour-identical — agents receive the same effective environment and builds produce the same results, while command fields in `.ralphex/config` point at generated per-role wrappers.
- **Secret boundary.** Personal credentials must never be required in committed artifacts; home profiles (`~/.goga/`) are the personal store; host home directories are never mounted (derived-value carriage only).
- **Declarative discipline.** Rendering is a step before parsing; the workflow grammar remains strictly structurally validated after rendering; rendering must not bypass validation.
- **Template grammar.** Jinja is a product decision, not an engineering choice; standard Jinja semantics for missing keys (falsy/empty, `|default(...)` works).
- **External execution model.** Per-stage env delivery works through the afm per-stage `command:` boundary (executable path convention, afm >= 0.4.15) without modifying afm; build-pass env works through ralphex command fields and `custom_review_script` without modifying ralphex.
- **Host/workflow isolation.** Workflow files are read, rendered, and parsed in-container only; the host launcher must not read workflow files (hence the strict six-field `build:` set and the encoded home bundle).
- **Agent set.** Profiles only select among the agent wrappers the container image ships.
- **Uniform strictness.** Humans and CI receive identical failure behaviour; no interactive recovery paths.
- **Contract relaxation.** `GOGA_WORKFLOW` deliberately relaxes the "run options never travel through the environment" rule; the relaxation is narrow (launcher-written, in-container-consumed) and must be documented in the affected contracts.
- **Wrapper ephemerality.** Wrappers live in container-local temp directories (secret ephemerality, no collision between concurrent builds sharing the runtime dir, regenerated per pass so interrupted-build resume is unaffected); never under `/workspace` (dashboard-browsable).

## Scope Estimate

Single task — no decomposition (user decision during formulation). Scale: nine affected cells, three workflow-grammar extensions, two wrapper-generation mechanisms (afm stage commands / ralphex pass commands), one new third-party dependency. Internal breakdown into implementation tasks happens at the plan stage.

## Existing Architecture

Affected cells (integration boundaries; design decisions per ADR):

| Cell | Boundary-level change |
|------|----------------------|
| `goga/pipeline/workflow` | Grammar gains `profile:`, `stages.<name>.env`, and the `build:` block; whole-file Jinja rendering runs before `parse_workflow` |
| `goga/pipeline` | Generates per-stage closure wrappers for stages declaring `env` and rewrites the compiled flow's stage `command:` to point at them (post-compile rewrite — the compiler's direct composition for env-free stages is untouched, keeping flow output byte-identical); `resolve_workflow` / `run_pipeline` handle activation; describe/card forms apply the profile; launch feedback line |
| `goga/commands/pipeline` | Launcher: `--profile` flag, `GOGA_PROFILE` carriage, `GOGA_HOME_PROFILES` encoding, `GOGA_WORKFLOW` writing, conditional env-file for info forms |
| `goga/commands/build` | Launcher: `--profile` and `-w/--workflow` flags, build feedback line |
| `goga/docker` | Encoding/decoding of the `GOGA_HOME_PROFILES` bundle (alongside the `extra-env-carriage` precedent) |
| `goga/build` | Settings layering `config < workflow build: < CLI`; per-role wrapper regeneration in `write_ralphex_config`; `GOGA_WORKFLOW` interpretation in-container with workflow loading via `goga/pipeline/workflow` (new dependency edge — the build path consumes the workflow grammar, rendering, and profile resolution alongside the pipeline path); task env layers leave the ralphex launch env |
| `goga/config/project` | New config field `build.review.additional.env` (`AdditionalReviewConfig`) |
| `goga/agents` | `resolve_wrapper_path` consumed in the wrapper exec chains (consumer only, contract unchanged) |
| `goga/ralphex` | Thin launcher unchanged in contract; launch env no longer carries task env layers |

Import graph around the change: `commands/pipeline` and `commands/build` depend on `docker`, `config`, `runtime`; `pipeline` depends on `pipeline/compiler`, `pipeline/workflow`, `pipeline/hooks`, `afm`, `agents`, `docker`, `config`; `build` depends on `config`, `docker`, `ralphex`, `agents`, `build/hooks`. The change adds one new edge — `build` → `pipeline/workflow` (in-container workflow loading for the build path; acyclic: `pipeline/workflow` has no dependencies). Cross-import cycles must not be introduced (DSL restriction).

## Notes

- Input artifacts: ADR `.goga/history/2026/contributor-profile/adr.md` (authoritative decisions) and PRD `.goga/history/2026/contributor-profile/prd.md` (requirements, aligned backward-compatibility clause).
- This task document intentionally contains no code examples and no new architecture — both are fixed by the ADR and the existing cell structure.
- Minimum jinja2 version `jinja2>=3.1` approved during formulation.
- New usage file `.goga/usages/cooks/jinja2.md` created together with this task (English, per project convention).
