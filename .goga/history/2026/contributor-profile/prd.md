# Contributor Profiles

## Problem

Contributors to a goga-driven repository each hold their own LLM subscription and their own agent harness, but the process definitions they run — pipeline-files, workflow-files, and `.goga/config.yml` — are shared committed artifacts. The product provides no way to separate the shared process definition from the personal execution layer (agent, credentials, model, per-stage tuning).

A contributor whose subscription or harness differs from the one baked into the project configuration cannot run the shared process at all — on the pipeline path or on the build path — without editing committed files or forking workflows into per-contributor copies. Two gaps amplify this:

- environment variables exist only as one global layer, so per-stage environment needs (for example, the same agent with a different reasoning level on a particular stage) force contributors to hand-write personal wrapper scripts;
- workflow forking — the only current workaround — leaves the team with divergent per-contributor copies and no single configuration point where execution variance is expressed.

## Users

**Primary: contributor-executor.** A team member with a personal LLM subscription and harness agent who runs the shared processes (`goga pipeline`, `goga build`). Goal: execute the shared process with their own agent, credentials, and model without touching committed files. Performs one-time local profile setup and activates it per run (or once via environment).

**Process author (workflow maintainer).** Writes workflow-files and decides which stage consumes which data. Defines the profile data model through what the workflow templates read, and declares the workflow's default profile so that data is non-empty out of the box. Needs expressive workflow authoring with validation and understandable errors.

**CI / automation.** A silent executor of the same processes. Activates a profile non-interactively through the environment; secrets arrive from the environment; a missing profile is a strict failure, not a question to a human. Environment activation is also a human convenience: a developer sets their profile once in their shell and invokes commands without flags.

**Team / repository owner.** Owns the committed project-level profiles and the profile naming contract; is interested in personal credentials never leaking into the repository.

## Goals

Priority order (established with the user): G1 → G4 → G2 → G3.

**G1 — Personal execution layer.** A contributor with any LLM subscription or harness agent can run the repository's shared processes (pipelines and builds) as-is — with their own agent, credentials, and model — without editing committed files or maintaining workflow copies. Personal credentials stay local.

**G4 — Working default.** A fresh contributor or CI runs the process immediately, with no personal setup: the process author declares a recommended default profile, and the data is non-empty from the start.

**G2 — Single point of variability.** The team expresses execution variance of the process in one place — the shared workflow definition — instead of a set of diverging per-contributor workflow copies.

**G3 — Per-stage environment.** The process author gives each stage its own environment (model, reasoning, flags) through the process definition itself — no hand-written sh wrappers per contributor.

## User Experience

### Authoring a workflow with profiles

The process author writes a workflow-file that may contain Jinja template syntax anywhere in the file. The workflow declares its default profile with a top-level `profile:` key. Example workflow:

```yaml
profile: default

stages:
  worker:
    agent: {{ worker.agent }}
    env:
      {% for k, v in worker.env.items() %}
      {{ k }}: {{ v }}
      {% endfor %}
  review:
    agent: {{ review.agent }}
    prompt: "Review using {{ review.model }}."
```

The referenced variables (`worker`, `review`) are keys inside the active profile file. Through the template usage the author defines the data model that every profile of this workflow must fulfill. The team commits a project profile (`.goga/profiles/default.yml`) with recommended values so the workflow runs out of the box:

```yaml
worker:
  agent: claude
  env:
    ANTHROPIC_MODEL: sonnet
review:
  agent: claude
  model: sonnet
```

### One-time personal setup

A contributor creates a personal profile file at `~/.goga/profiles/<name>.yml` with the same shape (the model the workflow's templates read) but their own values — their agent, their credentials, their model. Profile management is files-only: no CLI subcommands exist for creating, listing, or inspecting profiles. Personal credentials live only in home profiles; committed project profiles carry no personal secrets.

Profile lookup: `.goga/profiles/<name>.yml` (project, committed) and `~/.goga/profiles/<name>.yml` (home, personal). On the same name, the project profile wins.

### Activating and running

The active profile is selected by, from weakest to strongest: the workflow's `profile:` key (default), the `GOGA_PROFILE` environment variable, and the `--profile` CLI option. A stronger source replaces the weaker one.

With an effective profile, the run prints one brief line at launch naming the profile and its source (project or home). Nothing else changes in the visible output.

The contributor runs the shared workflow with their personal values substituted at the templated positions; non-templated parts keep the team configuration. Workflows that use no templates behave exactly as before (configuration-driven).

The `GOGA_PROFILE` variable set on the host reaches the launched container and remains set inside it, so nested invocations pick up the same profile.

### Build path

`goga build` accepts a `--workflow` / `-w` option selecting the workflow whose settings drive the build; workflow-provided build settings override the corresponding `.goga/config.yml` build fields, the config remaining the base. A build invoked inside a pipeline runtime (already inside a container launched with a workflow and a profile) inherits that workflow and profile through the environment, without re-specifying options.

### Failures

All profile-related failures occur before any stage executes; nothing partial runs; the strictness is identical for humans and CI (no interactive fallback):

- an activated profile or a workflow `profile:` default that exists neither in the project nor in home — strict fail with an actionable message naming the profile and both lookup locations;
- a malformed profile file (invalid YAML or non-mapping) — strict fail naming the profile and path;
- a Jinja syntax error in the workflow — strict fail locating the error;
- a rendered workflow that fails the standard structural validation — the existing structural errors apply unchanged.

A missing key inside the profile is not an error: standard Jinja semantics apply (`{% if %}` on missing data evaluates falsy, `| default(...)` works).

## Requirements

### Profiles

1. Profile files are read from `~/.goga/profiles/<name>.yml` (home, personal) and `.goga/profiles/<name>.yml` (project, committed). On the same profile name, the project file wins.
2. A profile file is a free-form YAML mapping. There are no conventional or reserved keys: the data model of a profile is defined solely by what the workflow's templates read.
3. Profile management is files-only. The product provides no CLI subcommands for profile lifecycle operations.

### Workflow templating

4. Workflow-files support Jinja template syntax across the whole file: any string value (agent, env, prompt, title, …) may reference profile data.
5. The template context is the entire content of the active profile: every top-level key of the profile file is a template variable.
6. Template evaluation follows standard Jinja semantics. A missing key is not an error; a missing profile file, a malformed profile file, and a Jinja syntax error are strict pre-run failures.
7. After rendering, the rendered workflow passes the standard structural validation; the existing grammar and error rules apply unchanged.
8. Pipeline-files (`.goga/pipelines/*.yml`), `.goga/config.yml`, and profile files themselves are not templated.

### Activation

9. The workflow may declare a top-level `profile: <name>` — the default active profile for runs of that workflow.
10. Activation channels: the `--profile` CLI option and the `GOGA_PROFILE` environment variable. Precedence: `--profile` > `GOGA_PROFILE` > workflow `profile:`. 
11. The active profile influences a run only through template rendering. Workflow parts without templates and fully legacy workflows keep the configuration-driven behaviour (`pipeline.agent`, `pipeline.env`, build config fields).
12. There is no built-in fallback profile: a workflow's `profile: default` refers to an ordinary profile the team commits at `.goga/profiles/default.yml`.
13. `GOGA_PROFILE`, when set on the host, propagates into every launched container and remains available to in-container invocations.

### Per-stage environment

14. The workflow grammar gains a per-stage `env` instruction (`stages.<name>.env`): a map of environment variables for that stage, literal and/or rendered from profile data.
15. A stage carrying `env` executes with those variables applied above the global environment layers; per-stage values take precedence over globally provided values for that stage. No contributor-side wrapper scripts are required to achieve this.

### Feedback

16. A launch with an effective profile prints a brief line naming the profile and its source (project or home). No other reporting surface (info card, describe output) is extended.

### Build

17. `goga build` honors profile activation through the same channels and precedence as pipelines.
18. `goga build` accepts a `--workflow` / `-w` option; build settings provided by the selected workflow override the corresponding `.goga/config.yml` build fields; the config remains the base.
19. A build invoked inside a pipeline runtime inherits the active workflow and profile from the environment without additional CLI options.

### Compatibility and strictness

20. Runs and compilations that use no profile features behave identically to the current product: the pipeline path is byte-identical (stage wrappers are generated only for stages that declare `env`); the build path is behaviour-identical — agents receive the same effective environment and builds produce the same results, while the command fields in `.ralphex/config` point at generated per-role wrappers instead of agent wrapper paths directly.
21. All profile and template failures happen before any stage executes and are reported with actionable messages (profile name, lookup locations, or error location).

## Constraints

- **Backward compatibility.** Projects, workflows, and configurations that use no profile features must compile and run exactly as today — byte-identical flow output on the pipeline path; on the build path, identical effective agent environments and identical results (generated wrapper command paths are an internal mechanism change and may differ).
- **Secret boundary.** The product must not require personal credentials in committed artifacts; home profiles (`~/.goga/`) are the personal store.
- **Declarative discipline.** Templating is a rendering step before parsing; the workflow grammar remains strictly structurally validated after rendering. Rendering must not bypass validation.
- **Template grammar.** The workflow template grammar is Jinja — a product decision, not an engineering choice.
- **External execution model.** The per-stage execution carriage is the downstream runner's per-stage command (afm ≥ 0.4.15); the runner has no native per-stage env. Per-stage env delivery (including any generated wrapper scripts) must work through this boundary without modifying the external tool.
- **Agent set.** Profiles only select among the agent wrappers the container image ships; no new agents or wrappers are introduced by this change.
- **Uniform strictness.** Humans and CI receive identical failure behaviour; no interactive recovery paths exist for missing profiles.

## Scope

### In Scope

- Profile files and resolution: `~/.goga/profiles/` + `.goga/profiles/`, project-wins, free-form mapping, whole content as template context.
- Whole-file Jinja templating of workflow-files with standard Jinja semantics.
- The workflow top-level `profile:` default key.
- Profile activation via `--profile` (pipeline and build commands) and `GOGA_PROFILE`, with precedence CLI > env > workflow default.
- Propagation of `GOGA_PROFILE` into launched containers.
- The per-stage `env` workflow instruction, composable with profile data.
- Strict pre-run failures (missing profile, malformed profile, Jinja syntax, post-render validation) with actionable messages.
- The brief launch feedback line (profile name + source).
- Build: profile activation, `--workflow` / `-w`, workflow settings over config, in-container inheritance of workflow and profile.
- Backward-compatible behaviour for profile-free runs.

### Out of Scope

- CLI subcommands for profile management (list, show, create, validate).
- Templating of pipeline-files, `.goga/config.yml`, or profile files.
- Extending the info card or describe output with profile analytics.
- Secret management beyond file placement (vaults, encryption, rotation).
- New agents or new wrapper scripts shipped by goga.
- Interactive fallbacks for missing profiles.
- A template context beyond the single active profile (multi-profile or cross-profile references).
- Modifying the external runner (afm) itself.

## Success Criteria

1. **Personal execution (G1).** A contributor whose subscription and harness differ from the project default runs a templated workflow — and a build — end-to-end with their personal profile activated, and their agent/env values reach the executing stages, without modifying any committed file.
2. **Working default (G4).** A fresh contributor or CI, with no personal profile, runs a workflow declaring `profile: default` successfully against the committed project profile — no local setup required.
3. **Single point of variance (G2).** One committed workflow serves contributors with different subscriptions: only the locally activated profile differs between their runs, and the runs exhibit the corresponding distinct behaviour.
4. **Per-stage environment (G3).** A workflow assigns different agents/env to different stages (for example, the same agent with different reasoning levels) via profile data and `stages.<name>.env`, and the stages execute with those values — with no contributor-written wrapper scripts.
5. **Strict failures.** A run referencing a missing profile (activated or workflow default) fails before any stage executes, with a message naming the profile and both lookup locations, identically for interactive and CI invocations.
6. **Backward compatibility.** Profile-free projects and workflows compile and run identically to the previous behaviour: byte-identical on the pipeline path; on the build path, identical effective env delivery and identical results.
7. **Environment propagation.** `GOGA_PROFILE` set on the host is available inside the launched container; a build invoked inside a pipeline runtime inherits the pipeline's workflow and profile without additional options.
8. **Launch feedback.** A launch with an effective profile shows a brief line naming the profile and its source (project/home).
