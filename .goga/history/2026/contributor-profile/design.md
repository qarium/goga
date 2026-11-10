# Design Document: `contributor-profile`

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/pipeline/workflow/CODEMANIFEST`: the cell gains the contributor-profile
  zone — 9 new types (`ProfileSource`, `ResolvedProfile`, `LoadedWorkflow`,
  `WorkflowBuild`, `load_home_profiles`, `resolve_profile`, `render_workflow`,
  `resolve_activation`, `load_workflow`); `parse_workflow` changes its signature
  from a path to rendered text and validates three new key families (per-stage
  `env`, top-level `profile`, top-level `build`); `WorkflowStage` gains `env`
  (field order: agent, env, prompt, …); `WorkflowDocument` gains `profile` and
  `build`; the `jinja2` practice joins the header Usages.
- `goga/docker/CODEMANIFEST`: the engine-variable carriage zone gains
  `encode_home_profiles` / `decode_home_profiles` (the `GOGA_HOME_PROFILES`
  single-line payload, mirroring the `GOGA_EXTRA_ENV` pattern for a nested
  mapping).
- `goga/config/project/CODEMANIFEST`: `AdditionalReviewConfig` gains the
  independent `env` layer (loader pattern: optional string mapping, default
  empty dict, non-string value → ValueError).
- `goga/build/CODEMANIFEST`: new Imports from `goga/pipeline/workflow`
  (`load_workflow`, `LoadedWorkflow`, `WorkflowBuild` + `load-workflow`,
  `profiles`) and `goga/docker` (`decode_home_profiles` +
  `home-profiles-carriage`); new routines `resolve_build_workflow`,
  `merge_workflow_build`, `write_role_env_wrappers`; `build` algorithm widened
  to 17 steps (decode → workflow resolution → feedback line → layering);
  `write_ralphex_config` gains `additional_wrapper_path`; `run_build_pass`
  drops the `env` parameter (task env travels through per-role closure
  wrappers; the ralphex subprocess inherits the container environment).
- `goga/pipeline/CODEMANIFEST`: new Imports (`decode_home_profiles`,
  `home-profiles-carriage`, `LoadedWorkflow`, `load-workflow`, `profiles`);
  `resolve_workflow` returns `LoadedWorkflow | None` and accepts the three
  activation channels; `describe_pipeline` and `run_pipeline` gain `profile`;
  new routine `apply_stage_env_wrappers`; `pipeline_cli` argparse gains
  `--profile/-p`; `apply_skip_stages` carries `profile`/`build` verbatim.
- `goga/pipeline/hooks/CODEMANIFEST`: the overlay merge is field-set-complete
  (per-stage `env` participates like every authored field) and the rebuilt
  document carries `profile`/`build` verbatim.
- `goga/ralphex/CODEMANIFEST`: annotations only — the `env` parameter of
  `run_ralphex` is no longer the carriage for build task env layers; the
  launcher contract (signature, flags, exit codes, secrecy) is unchanged.
- `goga/commands/build/CODEMANIFEST`: new Imports (`load_home_profiles` +
  `profiles` from workflow; `encode_home_profiles` +
  `home-profiles-carriage` from docker); the Click command gains
  `-w/--workflow` and `-p/--profile`; the home bundle loads before any docker
  activity; the env-file gains `GOGA_PROFILE` (ambient) and
  `GOGA_HOME_PROFILES` (encoded bundle) engine lines; `GOGA_WORKFLOW` is never
  written by this launcher.
- `goga/commands/pipeline/CODEMANIFEST`: same Imports; the `-p` short alias
  moves from `--parallel` (now long-only) to `--profile`; `pipeline`,
  `run_pipeline_container`, and `run_pipeline_info_container` gain the profile
  channel and the home bundle; the run launcher env-file gains three engine
  lines (`GOGA_PROFILE`, `GOGA_HOME_PROFILES`, `GOGA_WORKFLOW` of the run
  decision); the host workflow log line is removed (the feedback line prints
  in-container); the info launcher mounts an env-file only when there is
  profile cargo.
- `pyproject.toml`: `jinja2>=3.1` joins the dependencies.

### New Entities

- `ProfileSource` — `goga/pipeline/workflow/profile_source.py` — str-backed
  Enum (`PROJECT = "project"`, `HOME = "home"`).
- `ResolvedProfile` — `goga/pipeline/workflow/resolved_profile.py` — frozen
  dataclass (name, data, source).
- `LoadedWorkflow` — `goga/pipeline/workflow/loaded_workflow.py` — frozen
  dataclass (document, profile).
- `WorkflowBuild` — `goga/pipeline/workflow/workflow_build.py` — the six-field
  build-block model.
- `load_home_profiles` — `goga/pipeline/workflow/load_home_profiles.py`.
- `resolve_profile` — `goga/pipeline/workflow/resolve_profile.py`.
- `render_workflow` — `goga/pipeline/workflow/render_workflow.py`.
- `resolve_activation` — `goga/pipeline/workflow/resolve_activation.py`.
- `load_workflow` — `goga/pipeline/workflow/load_workflow.py`.
- `encode_home_profiles` / `decode_home_profiles` —
  `goga/docker/home_profiles.py`.
- `resolve_build_workflow` — `goga/build/resolve_build_workflow.py`.
- `merge_workflow_build` — `goga/build/workflow_build.py`.
- `write_role_env_wrappers` — `goga/build/role_env_wrappers.py`.
- `apply_stage_env_wrappers` — `goga/pipeline/stage_env_wrappers.py`.

### Changed Entities

- `parse_workflow` — signature `(workflow_path: Path)` → `(text: str)`; the
  caller owns reading and rendering; six top-level keys; `env` valid only
  under `stages.<name>`; strict six-field `build` block; empty-workflow rule
  extended (a `build:`-only workflow is valid; a `profile:`-only workflow is
  not).
- `WorkflowStage` — new `env: dict[str, str] | None` field (position 2 in the
  fixed order).
- `WorkflowDocument` — new `profile: str | None` and `build: WorkflowBuild |
  None` fields (order: prompt, stages, extend, memory, profile, build).
- `AdditionalReviewConfig` — new `env: dict[str, str]` (default empty).
- `build` — 17-step algorithm (decode once, resolve workflow, feedback line,
  layer settings, per-role wrapper launches without env layers).
- `resolve_run_settings` — the `config` parameter is documented as the LAYERED
  effective build configuration (no signature change).
- `write_ralphex_config` — new `additional_wrapper_path` parameter; the
  external-review surface points at the additional role wrapper.
- `run_build_pass` — the `env` parameter is removed.
- `resolve_workflow` — returns `LoadedWorkflow | None`; accepts
  `cli_profile`, `env_profile`, `home_profiles`.
- `describe_pipeline` / `run_pipeline` — new `profile` parameter; the run
  algorithm grows the feedback line, the wrapper patch step, and the
  `GOGA_PROFILE` export into the afm launch layer.
- `apply_skip_stages` — rebuilds with `profile`/`build` carried verbatim.
- `merge_workflow_overlay` — field-set-complete stage merge (including
  `env`); `profile`/`build` carried verbatim.
- `pipeline_cli` — `--profile/-p` in both run modes.
- `build` (command, `goga/commands/build`) — `-w/--workflow`, `-p/--profile`,
  home bundle, two env-file engine lines.
- `pipeline` (command, `goga/commands/pipeline`) — `-p/--profile` (short
  alias moved from `--parallel`), home bundle load before dispatch.
- `run_pipeline_container` — profile flag in argv, three env-file engine
  lines, no host workflow log line.
- `run_pipeline_info_container` — profile flag in card argv; env-file only
  with cargo.

### Deleted Entities

- None. `run_pipeline_container` steps 8–9 of the old algorithm (the host-side
  workflow-log decision and print) are removed behavior, not deleted types.

### Usages and Annotations Changes

- New project-level practice `.goga/usages/cooks/jinja2.md` — the rendering
  engine contract (fixed environment flags, missing-key semantics, strict
  syntax-error surfacing); connected as `jinja2` in the workflow cell header.
- New cell-level practices: `profiles.md` and `load-workflow.md`
  (goga/pipeline/workflow), `home-profiles-carriage.md` (goga/docker),
  `workflow-layering.md` (goga/build), `per-stage-env.md` (goga/pipeline) —
  each one functional domain, imported by every consumer cell through
  `Imports → Usages`.
- Updated cell-level practices: `build-usage.md`, `build.md` (commands/build),
  `pipeline-command.md` (commands/pipeline), `describe-pipeline.md`,
  `pipeline-cli.md`, `run-pipeline.md`, `parse-workflow.md` — extended with
  the profile/env-carriage surfaces; stale statements (env layers through the
  ralphex launch env, host workflow log line, `-p/--parallel`) replaced.
- Global annotations of every touched cell extended with the zone rules
  (layering order, wrapper mechanism, engine variables, feedback lines).

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None found during this design pass. `goga lint` reports 0 errors across 91
  cells; the four consistency dimensions (interface ↔ type, type ↔ mutation,
  interface ↔ interface, annotations ↔ entity) were traced against the actual
  implementation and practices (see the checkpoint summaries below). The
  `apply-architecture` stage had already resolved 14 annotation-link
  violations during materialization; this pass introduced no new edits — the
  CODEMANIFEST set is clean as-is.

### Fixed during the design-review pass

The review stage (code stack re-trace) found and fixed three contract
defects the design audit missed, all approved and applied:

- `goga/build/CODEMANIFEST` global Annotations — a stale sentence ("applied
  through the env layer of the ralphex launch only") contradicted the new
  per-role wrapper mechanism declared by the same manifest, `run_build_pass`,
  the ralphex cell, and `build-usage.md`; rewritten to the wrapper-only
  delivery with env-free ralphex launch (High).
- `goga/build/CODEMANIFEST` `resolve_run_settings` algorithm step 5 — the
  rebuilt `AdditionalReviewConfig` listed only agent/patience/max_iterations;
  the omitted `env` pass-through would silently drop the additional env
  layer (config and workflow block) at settings resolution; step 5 now
  carries the env verbatim clause (Medium).
- `goga/docker/CODEMANIFEST` `decode_home_profiles` algorithm step 3 — the
  garbled "non-string mapping values" phrasing (readable as requiring str
  values — the opposite of the intended every-value-is-a-mapping rule)
  reworded to "a value that is not itself a mapping" (Low).

Also reworded the "vanishes cleanly" claim of
`goga/pipeline/.usages/per-stage-env.md` (the clean vanish requires the
`{% if %}` guard to wrap the whole `env:` key), and extended the Test Stack
Trace with four scenarios: the malformed-project-profile strict error, the
illegal env-key rejection of `write_role_env_wrappers`, the card-level
profile application, and the `OSError` transparency of `load_workflow`.

## Entity Interaction and Data Flow

### Interaction Diagram

```
HOST                                                    CONTAINER
────                                                    ─────────
goga pipeline (click)                                   python -m goga.pipeline
  ├─ load_home_profiles(~/.goga/profiles)   strict       │
  │    └─ malformed → clean error, exit 1                ├─ pipeline_cli  (--profile/-p, run|list)
  ├─ encode_home_profiles(bundle)                        ├─ run_pipeline(profile=…)
  ├─ env-file:                                           │    ├─ decode_home_profiles(GOGA_HOME_PROFILES)
  │    GOGA_PROFILE=<ambient>          (non-empty)       │    ├─ read GOGA_PROFILE once
  │    GOGA_HOME_PROFILES=<payload>     (non-empty)      │    ├─ resolve_workflow(name, -w, --no-workflow,
  │    GOGA_WORKFLOW=<run decision>     (applied)  ──►   │    │        cli_profile, env_profile, bundle)
  └─ argv: run NAME --port P [--profile P]               │    │    └─ load_workflow(path, channels, bundle)
                                                         │    │         ├─ read text (OSError propagates)
goga build (click)                                       │    │         ├─ peek literal `profile:` (RAW text)
  ├─ load_home_profiles(~/.goga/profiles)                │    │         ├─ resolve_activation(cli>env>default)
  ├─ encode_home_profiles(bundle)                        │    │         ├─ resolve_profile(project>home)
  ├─ env-file:                                           │    │         ├─ render_workflow(jinja2, whole file)
  │    GOGA_PROFILE=<ambient>                            │    │         └─ parse_workflow(rendered text)
  │    GOGA_HOME_PROFILES=<payload>                      │    │    ├─ feedback line (stdout)
  │    (never GOGA_WORKFLOW)                             │    │    ├─ apply_skip_stages → hooks overlay
  └─ argv: --workflow NAME / --profile NAME              │    │    ├─ compile_flow → flow.yml
                                                         │    │    ├─ apply_stage_env_wrappers (patch flow.yml)
                                                         │    │    ├─ write_afm_config / prompts
                                                         │    │    └─ run_flow(env = pipeline.env ⊕ CLI
                                                         │    │                  ⊕ GOGA_PROFILE=effective)
                                                         │    │         └─ afm stage execs wrapper →
                                                         │    │              exec agent wrapper
                                                         │    └─ (a stage may invoke `goga build`)
                                                         │         python -m goga.build (-w/-p)
                                                         │           ├─ decode_home_profiles
                                                         │           ├─ read GOGA_WORKFLOW / GOGA_PROFILE
                                                         │           ├─ resolve_build_workflow (CLI>env)
                                                         │           ├─ merge_workflow_build (config<build:)
                                                         │           ├─ resolve_run_settings (layered)
                                                         │           ├─ write_role_env_wrappers
                                                         │           │    (/tmp/goga-build-env/{tasks,review,
                                                         │           │     additional}.sh)
                                                         │           └─ run_build_pass → write_ralphex_config
                                                         │                (claude_command = role wrapper)
                                                         │                → run_ralphex (NO env layer —
                                                         │                   inherits container env)
```

### Data Flows

1. **Home bundle (host → container)**: `load_home_profiles(Path.home()/
   ".goga/profiles")` → `dict[str, dict[str, Any]]` → `encode_home_profiles`
   → base64(compact JSON) single line → env-file `GOGA_HOME_PROFILES` →
   (docker boundary) → `decode_home_profiles` → the same mapping →
   `load_workflow(home_profiles=…)` → `resolve_profile` home lookup.
2. **Activation (three channels → one name)**: `--profile` (argv, forwarded
   in-container) > `GOGA_PROFILE` (env-file, ambient host value, or the afm
   launch layer export for nested runs) > workflow `profile:` default (raw
   text peek). `resolve_activation` folds them into one name or None.
3. **Profile → rendered workflow**: `resolve_profile` → `ResolvedProfile`
   → `.data` is the whole Jinja context → `render_workflow` renders the whole
   file → `parse_workflow(rendered)` → `WorkflowDocument`.
4. **Workflow build block → build settings**: `parse_workflow` →
   `WorkflowBuild` → `merge_workflow_build(config.build, block)` → layered
   `BuildConfig` → `resolve_run_settings` → `RunSettings` →
   `write_role_env_wrappers` exports per-role env layers →
   `write_ralphex_config` points `claude_command`/`custom_review_script` at
   the wrappers.
5. **Per-stage env → executing agent**: `WorkflowStage.env` → (compilation
   ignores it) → `apply_stage_env_wrappers` matches compiled `FlowStage`s by
   workflow stage name (+ loop suffix) → sh closure wrappers in
   `/tmp/goga-stage-env/` → targeted `command:` patch of the written
   flow-file → afm execs the wrapper → wrapper exports env, execs the agent
   wrapper.
6. **Effective profile → nested builds**: `run_pipeline` adds
   `GOGA_PROFILE=<effective>` to the afm launch layer (an overlay over the
   inherited container env); a `goga build` inside the runtime reads it
   through its env channel; the workflow travels via the ambient
   `GOGA_WORKFLOW` written by the run launcher.

### Entity Dependencies

- `goga/pipeline/workflow` stays a leaf (no Imports). Everything below
  depends on it; it depends on nothing but the stdlib, yaml, and jinja2.
- `goga/docker` (carriage) → `goga/version` (unchanged).
- `goga/config/project` — leaf (unchanged).
- `goga/pipeline/hooks` → `goga/pipeline/workflow` (`WorkflowDocument`).
- `goga/build` → `goga/pipeline/workflow` (load chain), `goga/docker`
  (decoders), `goga/config`, `goga/agents`, `goga/ralphex` (unchanged set).
- `goga/pipeline` → `goga/pipeline/workflow`, `goga/docker`, `goga/agents`
  (new), `goga/pipeline/compiler`, `goga/pipeline/hooks`, `goga/afm`.
- Both command cells → `goga/pipeline/workflow` (host half of the bundle) +
  `goga/docker` (encoders). No cell imports from a command cell; no cycles.
- Initialization order for the implementation stage (bottom-up): workflow →
  docker carriage → config/project → ralphex annotations (no code) →
  pipeline/hooks → build → pipeline → commands/build → commands/pipeline,
  then `pyproject.toml` (already materialized) and the facades
  (`goga/pipeline/workflow/__init__.py`, `goga/docker/__init__.py`,
  `goga/build/__init__.py`, `goga/pipeline/__init__.py` export lists).

## Code Stack Trace

Verified against the actual sources: `goga/pipeline/workflow/parse_workflow.py`,
`workflow_stage.py`, `workflow_document.py`; `goga/pipeline/resolve_workflow.py`,
`run_pipeline.py`, `cli.py`, `describe_pipeline.py`, `apply_skip_stages.py`;
`goga/pipeline/hooks/overlay.py`; `goga/pipeline/compiler/compile_flow.py`
(`_WRAPPER_PATH_TEMPLATE = "/home/goga/bin/{agent}-as-claude.sh"`,
`_expand_loops` → `NAME-1..NAME-N`), `serialize_flow.py`;
`goga/agents/wrapper/resolve.py` (`resolve_wrapper_path` produces exactly the
compiler's template — string concatenation); `goga/docker/extra_env.py`;
`goga/build/build.py`, `run_settings.py`, `ralphex_config.py`,
`build_pass.py`; `goga/commands/build/build.py`;
`goga/commands/pipeline/run_pipeline_container.py`,
`run_pipeline_info_container.py`; `goga/config/project/config.py`;
`goga/afm/run_flow.py` and `goga/ralphex/run_ralphex.py` (both apply `env`
as an **overlay** — `{**os.environ, **env}` — the fact the inheritance claims
rest on).

### Trace: `load_workflow` (the loading chain)

#### Chain
1. **Input**: `workflow_path: Path` (absolute, existence-guarded by the
   caller), `cli_profile`, `env_profile` (channel values, never read from the
   environment here), `home_profiles` (decoded bundle or None → treated as
   empty).
2. `workflow_path.read_text()` → raw text. OSError propagates unchanged
   (callers guard existence: `resolve_workflow` checks `.exists()`;
   `resolve_build_workflow` checks existence at step 3) → checkpoint: file
   I/O limited to the received path; **passed**.
3. Peek: scan the RAW text lines for a top-level literal `profile:` key
   (line starts at column 0 with `profile:`, value on the same line). Strip
   surrounding quotes and trailing comments; whitespace-only → None; a value
   carrying Jinja markers (`{{`/`{%`) is NOT a literal default → None
   (rendered-only defaults do not participate in activation) → checkpoint:
   matches the `load-workflow` practice and the arch checklist ("peek finds
   only literal `profile:` lines"); **passed**.
4. `resolve_activation(cli_profile, env_profile, peeked)` → name or None →
   checkpoint: three sources, strongest first, empty/whitespace = unset;
   **passed**.
5. When a name resolved: `resolve_profile(name, Path.cwd()/".goga"/"profiles",
   home_profiles or {})` → `ResolvedProfile` (strict errors: grammar,
   malformed project file, missing everywhere). Otherwise profile = None →
   checkpoint: project-wins ordering; the project directory derives from cwd
   (in-container `/workspace/.goga/profiles`); **passed**.
6. `render_workflow(text, profile.data if profile else {}, source_name=
   workflow_path.name)` → rendered text (a template-free file renders to
   itself; rendering ALWAYS runs, empty context without activation) →
   checkpoint: the fixed jinja2 environment per the `jinja2` practice;
   **passed**.
7. `parse_workflow(rendered)` → `WorkflowDocument` (structural validation
   unchanged; a rendered defect is the standard structural error) →
   checkpoint: rendering never bypasses validation; **passed**.
8. **Output**: `LoadedWorkflow(document=…, profile=…)` — consumers read
   `.document` (amendment/compilation) and `.profile` (feedback line, build
   layering trigger).

#### Checkpoint Summary
- read/peek/activation order and strictness: passed (matches contracts and
  practices).
- render-before-parse with unchanged grammar: passed.
- No environment reads inside the chain: passed (channels are parameters).

### Trace: `parse_workflow` (rendered text → document)

#### Chain
1. **Input**: `text: str` — the rendered workflow-file text. The caller owns
   reading and rendering (constraint: "Do not read files or render here").
2. `yaml.safe_load(text)`; `yaml.YAMLError` → `WorkflowSyntaxError("invalid
   YAML in workflow-file")`; non-dict root → `"workflow must be a mapping"`
   → checkpoint: unchanged behavior, message set identical to today;
   **passed**.
3. Top-level extraction over six keys (`prompt`, `stages`, `extend`,
   `memory`, `profile`, `build`): unknown key → `"unknown key in workflow:
   KEY; valid keys: prompt, stages, extend, memory, profile, build"`;
   `profile` non-str → `"non-str value in workflow.profile"`; empty/
   whitespace-only `profile` → None; `build` non-mapping → `"non-mapping
   build block in workflow"` → checkpoint: `_TOP_LEVEL_KEYS` tuple and
   `_extract_top_level` gain two branches; **passed**.
4. Stage building: `_STAGE_KEYS` becomes `(agent, env, prompt, loop, skills,
   skip, approve, manual, notes, reflect, memory)`; new validator for `env`:
   non-dict → `"non-mapping env in workflow.stages.NAME"`; non-str value →
   `"non-str value in workflow.stages.NAME.env.KEY"`; empty map → None
   (absence) → checkpoint: symmetric with the existing `notes` empty-map
   rule; **passed**.
5. Extend building: `env` joins the forbidden extend keys
   (`"env is forbidden in workflow.extend.NAME"`, checked with the other
   forbidden keys before positional/type validation) → checkpoint: the
   environment of a new stage is authored in the stages block under the new
   stage's name — same rationale as `notes`; **passed**.
6. Build block (`_build_build`): strict key set `agent`, `env`, `review`,
   (`review.agent`, `review.env`, `review.additional`,
   `review.additional.agent`, `review.additional.env`); any other key —
   including `proxy` and `hosts` — is `"unknown key in workflow.build.…:
   KEY; valid keys: agent, env, review.agent, review.env,
   review.additional.agent, review.additional.env"`; agent values must be
   str; env maps follow the string-map pattern (non-mapping →
   `"non-mapping env in workflow.build[.review[.additional]]"`, non-str
   value → `"non-str value in …env.KEY"`); result → `WorkflowBuild` with
   flat fields (`review_agent`, `review_env`, `review_additional_agent`,
   `review_additional_env`) → checkpoint: the host launcher never reads
   workflow files — proxy/hosts are consumed host-side, hence structural
   errors here; **passed**.
7. Empty rule: `prompt is None and not stages and not extend and memory is
   None and profile is None and build is None` → `"empty workflow — provide
   at least prompt, one stage, one extend entry, the memory block, or the
   build block"` → checkpoint: `build:`-only valid; `profile:`-only invalid
   (activation is not content — `profile` is not counted as content in the
   rule); **passed**.
8. **Output**: `WorkflowDocument(prompt, stages, extend, memory, profile,
   build)` — construction sites updated everywhere (`apply_skip_stages`,
   `overlay.py`, tests).

#### Checkpoint Summary
- New keys and error messages: passed (message shapes follow the existing
  conventions).
- `env` staging (stages-only, empty=absence): passed.
- Model field order vs dataclass declaration: passed (`WorkflowStage` field
  order agent, env, prompt, …; `WorkflowDocument` …, memory, profile, build).

### Trace: `resolve_profile`

#### Chain
1. **Input**: `name`, `project_dir` (typically `<cwd>/.goga/profiles/`),
   `home_profiles` mapping.
2. Grammar check `^[A-Za-z0-9][A-Za-z0-9._-]*$`, `.`/`..` forbidden; a
   violation raises one strict error naming the profile (path-traversal
   guard — the name becomes a filesystem component) → checkpoint: the same
   grammar documented in `profiles.md`; **passed**.
3. `<project_dir>/<name>.yml` exists → parse; invalid YAML or non-mapping
   root → strict error naming the profile and the path; → `ResolvedProfile(
   source=ProfileSource.PROJECT)`.
4. Else `name in home_profiles` → `ResolvedProfile(source=
   ProfileSource.HOME)` (bundle entries were strict-validated on the host;
   no re-validation).
5. Else strict error naming the profile and BOTH lookup locations.
6. **Output**: `ResolvedProfile` — `.data` is the rendering context.

#### Checkpoint Summary
- project-wins-on-same-name: passed (step 3 precedes step 4).
- No environment reads, no rendering here: passed.

### Trace: `render_workflow`

#### Chain
1. **Input**: `text`, `profile_data` (the whole profile mapping or `{}`),
   `source_name` (carried into error messages).
2. Build `jinja2.Environment(trim_blocks=True, lstrip_blocks=True,
   keep_trailing_newline=True, autoescape=False)` — the standard `Undefined`
   (per the `jinja2` practice; never `StrictUndefined`) → checkpoint: the
   fixed flag set is an ADR decision; **passed**.
3. `env.from_string(text).render(**profile_data)`; `TemplateSyntaxError` →
   one strict error carrying `source_name`, `exc.lineno`, `exc.message`.
   `UndefinedError` (nested access on a missing key) propagates as the
   natural Jinja failure — standard semantics, not wrapped.
4. **Output**: the rendered text (identity for template-free input).

#### Checkpoint Summary
- Engine flags / missing-key semantics / strict syntax surfacing: passed
  (matches `.goga/usages/cooks/jinja2.md` verbatim).

### Trace: `resolve_workflow` (pipeline side)

#### Chain
1. **Input**: `pipeline_name`, `workflow_name`, `no_workflow`, and the three
   activation channels.
2. `no_workflow` → None (activation ignored entirely — nothing loads).
3. Basename fallback (`workflow_name or pipeline_name`), compose
   `<cwd>/.goga/workflows/<name>.yml`, containment guard (escape → silent
   miss), existence check (missing → silent miss) — unchanged.
4. Existing file → `load_workflow(path, cli_profile, env_profile,
   home_profiles)` → `LoadedWorkflow`; structural/render errors propagate
   with their readable messages.
5. **Output**: `LoadedWorkflow | None`. Consumers: `run_pipeline` /
   `describe_pipeline` pass `.document` into `apply_skip_stages` and read
   `.profile` (run only).

#### Checkpoint Summary
- Silent-miss vs strict asymmetry with the build path: passed and
  deliberate — pipeline names may arrive from auto-match; an explicit build
  selection (`-w`/`GOGA_WORKFLOW`) is strict.

### Trace: `run_pipeline` (activation + wrappers + launch layer)

#### Chain
1. Steps 1–7 unchanged (config load-and-amend, discovery, paths, AFM_DIR).
2. Step 8: `decode_home_profiles(os.environ.get("GOGA_HOME_PROFILES", ""))`
   — a damaged bundle is one clean error here (return 1, no events, afm
   never launches); read `os.environ.get("GOGA_PROFILE")` once; both feed
   `resolve_workflow(name, workflow_name, no_workflow, profile, goga_profile,
   bundle)` → `LoadedWorkflow | None`.
3. Step 9: feedback line to stdout — `Pipeline running with workflow "<n>"
   and profile "<p>"` when `loaded.profile is not None`, else
   `Pipeline running with workflow "<n>"`, nothing without a workflow.
   `<n>` is the resolved workflow file stem (the explicit name, or the
   auto-match basename = pipeline name).
4. Steps 10–13 unchanged in mechanics, but `apply_skip_stages(resolved.
   document if resolved else None, skip)` and the amendment facts read the
   pre-merge resolution (`resolved`) — the decision matrix is unchanged.
5. Step 14 (new): `stages = apply_stage_env_wrappers(flow_doc.stages,
   overlay.workflow, config.pipeline.agent, flow_path)` — a no-op that
   touches no file when no stage declares env.
6. Steps 15–18 as before (prompts, afm config, composition — build
   `CompositionStage` rows from the wrapper-returned list; ids are
   identical, order preserved), statuses.
7. Step 19 (widened): launch layer = `pipeline.env` ⊕ decoded CLI entries,
   engine keys dropped — the engine set is now
   `{AFM_DIR, AFM_DOCKER_FILE_ROOTS, HTTP_PROXY, HTTPS_PROXY, NO_PROXY,
   GOGA_PROFILE, GOGA_WORKFLOW, GOGA_HOME_PROFILES, GOGA_EXTRA_ENV}` — plus
   `GOGA_PROFILE=<effective profile name>` when `loaded.profile` resolved.
   `run_flow` applies the layer OVER the inherited environment, so the
   ambient `GOGA_WORKFLOW`/`GOGA_HOME_PROFILES` of the env-file survive and
   every stage (and any nested `goga build`) inherits the effective profile.
8. Steps 20–23 unchanged (run, recompute statuses, completion facts, exit
   code).

#### Checkpoint Summary
- Four environment reads exactly (AFM_DIR, GOGA_EXTRA_ENV, GOGA_PROFILE,
  GOGA_HOME_PROFILES): passed.
- `run_flow` overlay semantics verified in source (`env` applied over the
  inherited environment): the GOGA_PROFILE export and ambient GOGA_WORKFLOW
  inheritance claims hold; **passed**.
- Composition equivalence card ↔ run: passed (wrappers alter only `command`
  fields, which the card does not report).

### Trace: `apply_stage_env_wrappers`

#### Chain
1. **Input**: the compiled `FlowStage` list, the overlay workflow document
   (or None), `global_agent` (the effective pipeline agent or None),
   `flow_path` (the file `compile_flow` wrote).
2. Selection: for each workflow stage entry with `env is not None`, claim
   every compiled stage whose `id` equals the entry name (exact match,
   highest priority) or matches `<name>-<digits>` (loop-expansion suffix —
   `FlowStage.id` is `NAME` or `NAME-i` per `_expand_loops`). No claimed
   stages → return the input list WITHOUT reading `flow_path` (byte-
   identical invariant).
3. Exec target per selected stage: workflow entry `agent` →
   `resolve_wrapper_path(agent)`; else `global_agent` →
   `resolve_wrapper_path(global_agent)`; else one strict pre-run error
   naming the stage. (`resolve_wrapper_path` output is byte-identical to the
   compiler's `_WRAPPER_PATH_TEMPLATE` — verified.)
4. Wrapper generation: one sh file per selected stage under
   `/tmp/goga-stage-env/` — `#!/bin/sh`, `export KEY=<shlex.quoted value>`
   per env entry (values verbatim — the contract imposes no engine-key
   dropping on per-stage env; it layers above all global layers), then
   `exec <resolved wrapper path> "$@"`; `chmod 0o755`. File name: the stage
   id when it matches `[A-Za-z0-9._-]+`, else a sanitized form plus a short
   digest (deterministic, idempotent overwrites per run).
5. Patch `flow_path` (text-level targeted patch — see Algorithm Design):
   replace the `command:` value of each selected stage's block, or insert a
   `command:` line at the canonical position when the stage has none (an
   env-declaring stage without an agent override compiles with no command
   field); every other byte of the file stays untouched.
6. **Output**: a new list — selected stages are NEW `FlowStage` objects with
   `fields["command"]` = the absolute wrapper path; every other stage is the
   SAME input object.

#### Checkpoint Summary
- Loop-copy multiplication: passed (every `NAME-i` copy gets its own wrapper
  with the same values).
- env-free byte-identity: passed (no read, no write when nothing is
  selected).
- Insertion case (env without agent): passed — design decision D5 documents
  the canonical insertion position.

### Trace: `resolve_build_workflow` (build side)

#### Chain
1. **Input**: `workflow_cli` (-w flag), `workflow_env` (GOGA_WORKFLOW value
   read once by `build()`), the two profile channels, the decoded bundle.
2. `workflow_cli` beats `workflow_env`; empty strings are unset; neither →
   None (no workflow in effect — activation ignored entirely, nothing loads,
   no feedback line).
3. Compose `<cwd>/.goga/workflows/<name>.yml`; a name whose resolved path
   escapes the workflows directory → one strict `"invalid workflow name"`
   error (an EXPLICIT selection is strict here, unlike the pipeline
   auto-match silent miss); a missing file → one strict error naming the
   workflow and the directory.
4. `load_workflow(path, cli_profile, env_profile, home_profiles)` →
   `LoadedWorkflow`; errors propagate.
5. **Output**: `LoadedWorkflow | None`.

#### Checkpoint Summary
- CLI > env on both axes (workflow and profile): passed.
- Strictness contrast with the pipeline path: deliberate, documented.

### Trace: `merge_workflow_build`

#### Chain
1. **Input**: the effective `BuildConfig` (non-None — see D2), the
   `WorkflowBuild` block.
2. Agents: `block.agent or config.agent` (root, review, additional — each
   independently; None never overrides).
3. Env maps key-wise: `{**config.env, **block.env}` (and the review /
   additional counterparts) — the block wins per key, the rest of the config
   env survives (override-one-variable use case).
4. `config.review is None` and the block sets any review field → construct a
   NEW `ReviewConfig` (set fields only, everything else default) and a NEW
   `AdditionalReviewConfig` when additional fields are set (its `env`
   defaulting to `{}`) so `resolve_run_settings` receives a well-formed
   layered configuration.
5. Every other `BuildConfig`/nested field passes through verbatim (session
   knobs, caps, skip, roles, base_ref, strategy, finalize, patience,
   prompts_dir, agents_dir, proxy, hosts).
6. **Output**: a NEW `BuildConfig` (new nested models; inputs unmutated —
   pure).

#### Checkpoint Summary
- `resolve_run_settings` consumes the layered value with no layering logic
  of its own: passed (its annotation now says exactly this).
- `AdditionalReviewConfig.env` flows: `_resolve_additional` must pass
  `env=block.env` (or `{}`) — construction site traced in
  `run_settings.py:191`; **passed** (implementation note recorded).

### Trace: `write_role_env_wrappers` + the two-pass launch

#### Chain
1. **Input**: `RunSettings`, decoded CLI entries.
2. `mkdir -p /tmp/goga-build-env` (container-local; never under /workspace).
3. Per role in (tasks, review, additional): role agent = tasks agent /
   review agent / additional agent (already inheritance-resolved by
   `resolve_run_settings` — the additional agent carries the inherited
   review agent when unset); None → one strict error naming the role BEFORE
   any pass launches.
4. Closure content: `export` the role's env layer with `cli_entries` applied
   ON TOP (CLI wins per key), engine-variable keys dropped silently — the
   drop set is the build engine set ∪ the GOGA_ engine set (decision D1);
   then `exec <resolved wrapper> "$@"`. Keys are validated as legal
   environment variable names at generation (a broken key would produce a
   broken script) — one strict error naming the role.
5. Write `/tmp/goga-build-env/{tasks,review,additional}.sh`, `chmod 0o755`;
   idempotent overwrites; regenerated at each pass's config write.
6. **Output**: `{"tasks": Path, "review": Path, "additional": Path}`.
7. Pass launch (`build` steps 12–13): `write_ralphex_config(settings,
   str(tasks_wrapper), str(additional_wrapper))` → `claude_command` = the
   role wrapper; under full/short with an engaged external review,
   `custom_review_script` = the additional wrapper. `run_build_pass(plan,
   settings, options, wrapper_path, dry_run)` → `run_ralphex(plan, options,
   dry_run)` — NO env argument; the ralphex subprocess inherits the container
   environment (`run_ralphex` env overlay semantics verified — with no layer
   it calls `subprocess.call` without `env`). Under medium the additional
   wrapper stays inert (`codex_enabled = false`).

#### Checkpoint Summary
- Layer independence (task env never reaches the review pass; additional
  never inherits review env): passed — each wrapper exports only its own
  role's layer.
- Old `env` layer path fully removed: `run_build_pass` signature drops it;
  `_compose_pass_env`/`_launch_pass` env plumbing in `build.py` is deleted;
  **passed**.

### Trace: host launchers (commands/build, commands/pipeline)

#### Chain — `goga build`
1. Click options `-w/--workflow NAME`, `-p/--profile NAME` (both `str |
   None`). Reject values starting with `-` (argv parsability). Validate the
   `-w` name host-side: path containment under `<cwd>/.goga/workflows/` +
   file existence (a light early diagnostic; the file is never read).
2. Before any docker activity: `home_profiles = load_home_profiles(
   Path.home()/".goga"/"profiles")` — a malformed home profile is one clean
   `ClickException` (no image refresh, no launch).
3. Env-file ladder unchanged through the CLI entries payload
   (`GOGA_EXTRA_ENV`), then two engine lines under the engine-skip rule (an
   explicit `-e` key keeps winning): `GOGA_PROFILE=<ambient host value>`
   only when non-empty; `GOGA_HOME_PROFILES=encode_home_profiles(bundle)`
   only when the bundle is non-empty. `GOGA_WORKFLOW` is NEVER written by
   this launcher.
4. In-container argv gains `--workflow NAME` / `--profile NAME` only when
   set. This launcher prints no feedback line (the build line prints
   in-container, to stderr).

#### Chain — `goga pipeline`
1. `-p/--profile NAME` (the short alias moves from `--parallel`, which
   becomes long-only); the profile value passes the leading-dash check
   together with `workflow`/`name`/`skip`.
2. After the argument-form checks and before dispatch:
   `load_home_profiles(~/.goga/profiles)` — strict, pre-docker; the bundle
   is handed to both launchers.
3. Run launcher env-file: after `GOGA_EXTRA_ENV`, three engine lines under
   the engine-skip rule — `GOGA_PROFILE` (ambient, non-empty only),
   `GOGA_HOME_PROFILES` (bundle non-empty only), `GOGA_WORKFLOW` = the
   effective workflow name of the run decision (never under `--no-workflow`;
   explicit `-w` (already validated) or the basename auto-match file
   existence — the same silent containment guard; no line when the
   auto-match file is absent). The host prints NO workflow line.
4. Run argv: `run NAME --port P [-w W] [--no-workflow] [--profile P] [-s N]…
   [--parallel N]`.
5. Info launcher: env-file ONLY when there is cargo (non-empty ambient
   `GOGA_PROFILE` or non-empty bundle), carrying exactly the two profile
   lines (never `GOGA_WORKFLOW`); without cargo the launch keeps the minimal
   read-only shape (no port, no env-file, no persistent mount). Card argv
   gains `--profile P` when set.

#### Checkpoint Summary
- Engine-skip rule reuse (`cli_keys` filter verified in both launcher
  sources): passed.
- `-p` namespace migration (--parallel long-only; the Docker `-p port:host`
  token is a separate namespace — documented in `pipeline-command.md`):
  passed.

## Algorithm Design

### `load_workflow`

**Responsibility**: the single loading chain turning a workflow-file path
into a `LoadedWorkflow` under an activation context.

**Algorithm**:
```
1. text = workflow_path.read_text()                → OSError propagates
2. default = peek_literal_profile(text)            → str | None
   - line-anchored scan: ^profile:\s*(value)$ at column 0
   - strip quotes / trailing comment; whitespace-only → None
   - value containing "{{" or "{%" → None (not a literal default)
3. name = resolve_activation(cli_profile, env_profile, default)
4. IF name is None: profile = None
   ELSE: profile = resolve_profile(name, Path.cwd()/".goga/profiles",
                                   home_profiles or {})
5. rendered = render_workflow(text, profile.data if profile else {},
                              source_name=workflow_path.name)
6. document = parse_workflow(rendered)
7. RETURN LoadedWorkflow(document, profile)
```

**Errors**:
- `OSError` → propagated unchanged (callers guard existence).
- `WorkflowSyntaxError` (strict, pre-run) → grammar/profile defects surface
  with their messages; the CLI renders them as clean stderr lines.
- Profile resolution errors (grammar / malformed / missing) → strict,
  pre-run, actionable (profile, path, or both locations).
- `TemplateSyntaxError` wrapper → names the file and the line.

**Edge Cases**:
- Template-free file, no activation → renders to itself; document equals
  today's path-based parse.
- Workflow default + no channels → the default activates (weakest source).
- Empty/whitespace channel values → unset.
- `home_profiles=None` → treated as `{}`.

### `parse_workflow` (delta)

**Responsibility**: pure structural parser over rendered text.

**Algorithm** (new/changed steps only):
```
3. top-level: accept prompt|stages|extend|memory|profile|build
   - profile: non-str → error; empty/whitespace → None
   - build: non-mapping → error
6.1.2 stage keys: agent, env, prompt, loop, skills, skip, approve,
      manual, notes, reflect, memory
6.1.4 env: non-dict → "non-mapping env in workflow.stages.NAME";
      non-str value → "non-str value in workflow.stages.NAME.env.KEY";
      empty map → env=None
6.2.8 extend: env key → "env is forbidden in workflow.extend.NAME"
      (checked with the other forbidden keys, before before/after types)
6.4 build block:
   - strict keys: agent, env, review.agent, review.env,
     review.additional.agent, review.additional.env
   - any other key (incl. proxy, hosts) → unknown-key error
   - agent non-str → "non-str value in workflow.build[.review[.additional]].agent"
   - env non-mapping → "non-mapping env in …"; non-str value →
     "non-str value in ….env.KEY"
   - build WorkflowBuild(agent, env, review_agent, review_env,
     review_additional_agent, review_additional_env)
7. empty rule: prompt∧stages∧extend∧memory∧profile∧build all absent
   → "empty workflow — provide at least prompt, one stage, one extend
   entry, the memory block, or the build block"
```

**Errors**: `WorkflowSyntaxError` with the exact messages above.

**Edge Cases**:
- `build:`-only workflow → valid.
- `profile: "  "` → None; then the empty rule applies if nothing else
  is present.
- `env: {}` → absence (None).
- `profile: 42` → non-str structural error.

### `resolve_activation`

**Responsibility**: fold three activation sources into one effective name.

**Algorithm**:
```
1. FOR value IN (cli_profile, env_profile, workflow_default):
     IF value is not None AND value.strip() != "": RETURN value
2. RETURN None
```

**Errors**: none (pure).

**Edge Cases**: whitespace-only counts as unset; first non-empty wins
(strongest first).

### `resolve_profile`

**Responsibility**: validate a name and resolve it project-first.

**Algorithm**:
```
1. IF not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name in (".", ".."):
     RAISE strict error naming the profile
2. path = project_dir / f"{name}.yml"
   IF path.exists():
     data = yaml.safe_load(path.read_text())   → invalid YAML / non-mapping
                                               → strict error naming profile+path
     RETURN ResolvedProfile(name, data, ProfileSource.PROJECT)
3. IF name in home_profiles:
     RETURN ResolvedProfile(name, home_profiles[name], ProfileSource.HOME)
4. RAISE strict error naming the profile and BOTH locations
```

**Edge Cases**: a home bundle key failing the grammar is inert (the REQUESTED
name is validated, not the bundle); the project file wins on the same name.

### `render_workflow`

**Responsibility**: whole-file Jinja render before parsing.

**Algorithm**:
```
1. env = Environment(trim_blocks=True, lstrip_blocks=True,
                     keep_trailing_newline=True, autoescape=False)
2. TRY rendered = env.from_string(text).render(**profile_data)
   EXCEPT TemplateSyntaxError AS exc:
     RAISE strict error f"{source_name}: template syntax error at line
     {exc.lineno}: {exc.message}"
3. RETURN rendered
```

**Edge Cases**: template-free input → identity; missing keys → falsy/empty
(standard `Undefined`); nested access on a missing key → `UndefinedError`
propagates (standard semantics, unwrapped).

### `load_home_profiles`

**Responsibility**: strict whole-bundle read of the home profiles directory
(host side, before any docker activity).

**Algorithm**:
```
1. IF not home_dir.is_dir(): RETURN {}
2. FOR path IN sorted(home_dir.glob("*.yml")):        # non-recursive, flat
     data = yaml.safe_load(path.read_text())
     invalid YAML or non-mapping root → strict error naming the file path
     bundle[path.stem] = data
3. RETURN bundle
```

**Edge Cases**: missing directory → `{}` (a personal-machine default); only
flat `*.yml` collected (subdirectories ignored); deterministic
(sorted iteration).

### `encode_home_profiles` / `decode_home_profiles`

**Responsibility**: the `GOGA_HOME_PROFILES` carriage across the docker
boundary (mirror of `extra_env.py` for a nested mapping).

**Algorithm**:
```
encode: {} → ""
        json.dumps(profiles, separators=(",", ":"), sort_keys=True)
        → base64 (standard, padded) → str
decode: "" → {}
        base64 decode (validate=True) → json.loads
        failure / non-mapping root / non-str mapping VALUES (inner maps may
        hold any YAML scalars — only the name keys and the nesting shape are
        checked) → ValueError("GOGA_HOME_PROFILES: invalid payload")
```

**Edge Cases**: empty bundle → empty string → no env-file line; roundtrip
identity; payload content never appears in errors or logs.

### `resolve_build_workflow`

**Responsibility**: select and load the workflow driving a build (CLI > env;
none → None).

**Algorithm**:
```
1. name = workflow_cli if non-empty else workflow_env if non-empty
2. IF name is None: RETURN None
3. root = (Path.cwd()/".goga"/"workflows").resolve()
   path = root / f"{name}.yml"
   IF path.resolve() escapes root: RAISE "invalid workflow name" strict error
   IF not path.exists(): RAISE strict error naming the workflow and the dir
4. RETURN load_workflow(path, cli_profile, env_profile, home_profiles)
```

**Edge Cases**: `workflow_cli=""` counts as unset (env wins); no workflow →
activation ignored entirely.

### `merge_workflow_build`

**Responsibility**: overlay the six-field block onto the effective build
configuration (config < workflow `build:` < CLI).

**Algorithm**:
```
1. review = config.review
   block_sets_review = any of (review_agent, review_env,
                               review_additional_agent,
                               review_additional_env) is not None
   IF review is None AND block_sets_review:
     review = ReviewConfig() defaults, then fill the set str/env fields
     (AdditionalReviewConfig(env=…) when additional fields are set)
2. RETURN BuildConfig(
     agent = block.agent or config.agent,
     env   = {**config.env, **(block.env or {})},
     …every other root field verbatim…,
     review = ReviewConfig(
         agent = block.review_agent or (review.agent if review else None),
         env   = {**(review.env if review else {}), **(block.review_env or {})},
         …verbatim…,
         additional = AdditionalReviewConfig(
             agent = block.review_additional_agent
                     or (additional.agent if additional else None),
             patience/max_iterations verbatim,
             env = {**(additional.env if additional else {}),
                    **(block.review_additional_env or {})})))
```

**Errors**: none raised for content; the None-build-section guard is the
caller's (D2).

**Edge Cases**: absent block fields never override; key-wise merge preserves
config survivors; `config.review is None` + review fields → well-formed new
`ReviewConfig`; purity — every nested model is new.

### `write_role_env_wrappers`

**Responsibility**: generate the per-role closure wrappers every build pass
executor runs through.

**Algorithm**:
```
1. base = Path("/tmp/goga-build-env"); base.mkdir(parents=True, exist_ok=True)
2. roles = {"tasks": settings.tasks.agent,
           "review": settings.review.agent,
           "additional": settings.review.additional.agent}
   FOR role, agent IN roles:
     IF agent is None: RAISE strict error naming the role
     wrapper = resolve_wrapper_path(agent)
     layer = {**role_env, **cli_entries} minus ENGINE_KEYS   # D1
     FOR key IN layer: IF not legal_env_name(key): RAISE strict error naming role
     script = "#!/bin/sh\n" + "".join(f"export {k}={shlex.quote(v)}\n")
              + f'exec {wrapper} "$@"\n'
     path = base / f"{role}.sh"; write; chmod 0o755
3. RETURN {"tasks": …, "review": …, "additional": …}
```

**Edge Cases**: idempotent overwrite per pass; dry-run still generates (the
config points at the wrapper; only the launch is skipped); the additional
wrapper exists under every strategy but stays inert under medium
(`codex_enabled = false`).

### `apply_stage_env_wrappers`

**Responsibility**: deliver per-stage env through generated sh closures and
a targeted post-compile patch of the written flow-file.

**Algorithm**:
```
1. IF workflow is None: RETURN stages                       # untouched
   claims = {}
   FOR wname, wstage IN workflow.stages.items() WHERE wstage.env is not None:
     FOR stage IN stages:
       IF stage.id == wname: claims[stage.id] = (wstage, exact=True)
     FOR stage IN stages:                                   # loop copies
       IF re.fullmatch(rf"{re.escape(wname)}-\d+", stage.id)
          AND stage.id not claimed exact:
         claims[stage.id] = (wstage, suffix=True)
   IF no claims: RETURN stages                              # flow_path untouched
2. base = Path("/tmp/goga-stage-env"); mkdir
   FOR stage_id, (wstage, _) IN claims:
     target = resolve_wrapper_path(wstage.agent) if wstage.agent
              else resolve_wrapper_path(global_agent) if global_agent
              ELSE RAISE strict error naming the stage
     write wrapper: export each env value (verbatim), exec target "$@"
     chmod 0o755
3. text = flow_path.read_text()
   FOR stage_id IN claims:
     patch the stage block: replace the command line value, or insert
     `command: <wrapper>` at the canonical position (before the first
     present canonical key after command; else before depends_on; else at
     block end)
   flow_path.write_text(patched)                            # other bytes intact
4. RETURN [new FlowStage with fields["command"]=wrapper if claimed
          else the SAME input object]
```

**Errors**: missing exec target (no stage agent, no global agent) → strict
pre-run error naming the stage; no events fire (the run coordination raises
before `run_flow`).

**Edge Cases**: exact-match entry beats suffix-match on id collisions;
wrapper file naming sanitization with digest fallback; loop copies each get
their own wrapper with identical values; per-stage values are exported
verbatim (no engine-key drop — they layer above all global layers by
contract).

### `run_pipeline` (delta), `describe_pipeline` (delta), `pipeline_cli` (delta)

- `run_pipeline`: insert feedback print (step 9), wrapper application
  (step 14), the launch-layer engine-set widening and the `GOGA_PROFILE`
  export (step 19); everything else byte-for-byte the existing flow.
- `describe_pipeline`: read `GOGA_PROFILE` + decode `GOGA_HOME_PROFILES`
  once, pass the channels into `resolve_workflow`, merge skips over
  `resolved.document`; no feedback line; no wrapper generation (the card
  reports id/title only — equivalence is structural).
- `pipeline_cli`: `--profile/-p` on the run subparser (binds in both info
  and run modes); forwarded to `describe_pipeline`/`run_pipeline`.

### Host launchers (delta)

- `goga/commands/build/build.py`: two click options; leading-dash rejection;
  `-w` containment+existence validation; `load_home_profiles` before docker;
  two engine lines after `GOGA_EXTRA_ENV` under the engine-skip rule; argv
  forwarding.
- `goga/commands/pipeline/pipeline.py`: `-p/--profile` (short alias moved),
  `--parallel` long-only; bundle load after argument checks before dispatch;
  bundle + profile handed to both launchers.
- `run_pipeline_container.py`: drop `_resolve_workflow_log_name` and its
  print; add the three engine lines (the `GOGA_WORKFLOW` decision recomputed
  silently with the same containment guard); `--profile` in argv.
- `run_pipeline_info_container.py`: `--profile` in the card argv; env-file
  only with cargo (`GOGA_PROFILE` ambient non-empty or bundle non-empty),
  carrying exactly the two profile lines.

## Cross-cutting Concerns

- **Error handling**: every new failure is strict, pre-run, and actionable —
  malformed home profiles fail on the HOST before any docker activity; a
  damaged `GOGA_HOME_PROFILES` payload is one clean error in-container
  before any event fires (no partial application); profile grammar/lookup
  failures name the profile (and path / both locations); Jinja syntax errors
  name the file and line; the strict/ silent-miss split is deliberate
  (explicit build selections strict; pipeline auto-match silent). The build
  feedback line prints only for workflow+profile runs; the pipeline line for
  any resolved workflow.
- **Validation**: `parse_workflow` owns the workflow grammar (six top-level
  keys, stages-only `env`, strict build block); `resolve_profile` owns the
  name grammar (path-traversal guard); `write_role_env_wrappers` validates
  env-key legality before writing scripts; rendering never bypasses
  validation.
- **Logging / secrecy**: env values, wrapper contents, payloads, and profile
  contents are never printed or logged (engine-carriage secrecy is
  unchanged); facts and logs carry NAMES only; dry-runs print command lines
  only.
- **Caching**: none introduced. Wrappers are regenerated per pass / per run
  (idempotent overwrites in container-local temp dirs — never under
  `/workspace`); the home bundle is loaded once per host invocation and
  decoded once per container run.
- **Concurrency**: no shared mutable state; all new routines are pure or
  write to per-run temp paths. Loop-expanded wrappers are distinct files per
  stage id, so parallel afm stages never race on one wrapper.

## Usages Analysis

### `jinja2` (project-level, `.goga/usages/cooks/jinja2.md`)
- **What it provides**: the rendering engine contract — fixed environment
  flags (`trim_blocks`, `lstrip_blocks`, `keep_trailing_newline`,
  `autoescape=False`, standard `Undefined`), missing-key semantics, strict
  `TemplateSyntaxError` surfacing with location, whole-file-before-parse
  stance, anti-patterns.
- **Where used**: `render_workflow`, `load_workflow` (global cell
  annotations + both routines' annotations).
- **Why chosen**: an external library contract that must not be duplicated;
  file form (project-level cooks/ convention for library practices).
- **How exactly**: `Environment(...)` → `from_string(text).render(**profile)`.

### `convention` / `conventions` (project-level)
- Unchanged role for every touched cell: code style, docstrings, dataclass
  rules (`kw_only=True`, frozen models), test infrastructure.

### Imported Usages
- `load-workflow` from `goga/pipeline/workflow` — the loading-chain contract
  (read → peek → activation → resolve → render → parse). Consumers:
  `goga/pipeline` (`resolve_workflow`), `goga/build`
  (`resolve_build_workflow`). Path: `goga/pipeline/workflow/.usages/
  load-workflow.md`.
- `profiles` from `goga/pipeline/workflow` — profile files, name grammar,
  activation precedence, home-bundle collection, failure strictness.
  Consumers: `goga/pipeline`, `goga/build`, `goga/commands/build`,
  `goga/commands/pipeline` (the host bundle loaders). Path:
  `goga/pipeline/workflow/.usages/profiles.md`.
- `home-profiles-carriage` from `goga/docker` — the carriage contract (one
  derived value, engine-skip rule, write-when-non-empty, decode-once,
  secrecy). Consumers: `goga/build`, `goga/pipeline`,
  `goga/commands/build`, `goga/commands/pipeline`. Path:
  `goga/docker/.usages/home-profiles-carriage.md`.
- `extra-env-carriage`, `resolve-wrapper-path`, `afm`, `ralphex`,
  `agent-wrappers`, `docker-builder`, `docker-runner`, `click` (existing)
  — unchanged roles; `resolve-wrapper-path` is now consumed by the two new
  wrapper generators in addition to its existing consumers.

Every connected practice is referenced in at least one annotation (verified
per cell during the audit).

## `.usages/` Update

All seven new/updated files were materialized by the `apply-architecture`
stage; this design pass verified their consistency against the CODEMANIFESTs
(status below). No further edits are required.

### Cell: `goga/pipeline/workflow`
- **`profiles.md`** (new) — current; covers profile files, grammar,
  precedence, `load_home_profiles`, strictness; matches
  `resolve_activation`/`resolve_profile`/`load_home_profiles` signatures.
- **`load-workflow.md`** (new) — current; the chain steps mirror
  `load_workflow`'s algorithm; failure modes match the contracts.
- **`parse-workflow.md`** (updated) — current; rendered-text stance, six
  top-level keys, the build block, stages-only `env`, empty-workflow rule.

### Cell: `goga/docker`
- **`home-profiles-carriage.md`** (new) — current; host half
  (`load_home_profiles` + `encode_home_profiles`, write-when-non-empty,
  engine-skip) and container half (`decode_home_profiles`, decode once)
  match the contracts.

### Cell: `goga/build`
- **`workflow-layering.md`** (new) — current; the six-field block, layering
  order, key-wise merge, selection channels, feedback line.
- **`build-usage.md`** (updated) — current; per-role wrapper ladder,
  workflow/profile flags, side effects, `main()` argparse surface.

### Cell: `goga/pipeline`
- **`per-stage-env.md`** (new) — current; authoring, delivery mechanism,
  byte-identity, loop copies, profile combination.
- **`run-pipeline.md`**, **`describe-pipeline.md`**, **`pipeline-cli.md`**
  (updated) — current; activation context, feedback line, wrapper patch,
  four env reads, engine-set drops, `-p` flag.

### Cell: `goga/commands/build`
- **`build.md`** (updated) — current; `-w`/`-p` rows, profile-carriage
  table, GOGA_WORKFLOW exclusion.

### Cell: `goga/commands/pipeline`
- **`pipeline-command.md`** (updated) — current; flag matrix, three engine
  lines, in-container workflow line, cargo-only info env-file, `-p` vs
  docker `-p`.

No cell points its own CODEMANIFEST `Usages` at its `.usages/` directory
(verified) — the files are consumer documentation only.

## Test Stack Trace

### General Setup

- pytest fixtures per `tests/<package>/conftest.py`; tmp_path for all file
  trees; monkeypatch for environment variables and cwd; the existing
  contract/logic test-pair convention (`test_<module>_contract.py`,
  `test_<module>_logic.py`) extends to the new modules.
- Shared new fixtures (suggested `tests/pipeline/workflow/conftest.py`):
  `project_root(tmp_path, monkeypatch)` — chdir into a fake project with
  `.goga/profiles/`, `.goga/workflows/`; `home_bundle` — a sample
  `dict[str, dict[str, Any]]`; `render_env` — the fixed jinja2 Environment
  per the practice.
- jinja2 must be installed in the test venv (`pip install jinja2>=3.1` —
  already in `pyproject.toml`).

### Source File Registry

- `goga/pipeline/workflow/`: `parse_workflow.py`, `workflow_stage.py`,
  `workflow_document.py`, `workflow_build.py`, `profile_source.py`,
  `resolved_profile.py`, `loaded_workflow.py`, `load_home_profiles.py`,
  `resolve_profile.py`, `render_workflow.py`, `resolve_activation.py`,
  `load_workflow.py`, `__init__.py` (facade).
- `goga/docker/home_profiles.py`, `__init__.py`.
- `goga/config/project/config.py` (+ loader).
- `goga/build/`: `resolve_build_workflow.py`, `workflow_build.py`,
  `role_env_wrappers.py`, `build.py`, `run_settings.py`,
  `ralphex_config.py`, `build_pass.py`, `__main__.py`, `__init__.py`.
- `goga/pipeline/`: `resolve_workflow.py`, `stage_env_wrappers.py`,
  `run_pipeline.py`, `describe_pipeline.py`, `cli.py`,
  `apply_skip_stages.py`, `__init__.py`.
- `goga/pipeline/hooks/overlay.py`.
- `goga/commands/build/build.py`; `goga/commands/pipeline/pipeline.py`,
  `run_pipeline_container.py`, `run_pipeline_info_container.py`.

---

### Positive Tests

#### `test_load_workflow_renders_with_active_project_profile`

**Setup**: project root with `.goga/profiles/mixa.yml` =
`worker: {agent: codex, model: sonnet}`; workflow
`.goga/workflows/hard.yml` = `stages: {build: {agent: '{{ worker.agent }}',
env: {MODEL: '{{ worker.model }}'}}}`; the workflow has no `profile:`
default; activation arrives through the env channel.

**Input**: `load_workflow(root/".goga/workflows/hard.yml", cli_profile=None,
env_profile="mixa", home_profiles={})`.

**Trace**:
```
load_workflow(path, None, "mixa", {})
  → read_text()                          # raw template text
  → peek: no literal `profile:` line → None
  → resolve_activation(None, "mixa", None) → "mixa"
  → resolve_profile("mixa", <cwd>/.goga/profiles, {})
      → project file exists → yaml parse → mapping
      → ResolvedProfile("mixa", {"worker": …}, ProfileSource.PROJECT)
  → render_workflow(text, {"worker": …}, "hard.yml")
      → jinja render → stages.build.agent == "codex", env.MODEL == "sonnet"
  → parse_workflow(rendered)
      → WorkflowStage(agent="codex", env={"MODEL": "sonnet"})
  → LoadedWorkflow(document, profile)
```

**Assertions**:
```
loaded.profile.name == "mixa"
loaded.profile.source is ProfileSource.PROJECT
loaded.document.stages["build"].agent == "codex"
loaded.document.stages["build"].env == {"MODEL": "sonnet"}
```

**Sufficiency**: pins the whole chain — activation via the env channel,
project-first resolution, context = whole profile, render-before-parse, env
map flowing into the model. Prevents regressions where rendering is skipped
or the context is flattened.

#### `test_load_workflow_plain_file_renders_to_itself`

**Setup**: workflow without any Jinja syntax (`prompt: hi` +
one stage `{agent: claude}`); no profile anywhere; channels None.

**Input**: `load_workflow(path, None, None, None)`.

**Trace**:
```
load_workflow → peek None → activation None → profile None
  → render_workflow(text, {}, "plain.yml") → text unchanged
  → parse_workflow(text) → document
  → LoadedWorkflow(document, None)
```

**Assertions**: `loaded.profile is None`; document equals
`parse_workflow(text)` directly.

**Sufficiency**: the identity-render invariant — a template-free file
behaves exactly as today's path-based parse; guards the "rendering ALWAYS
runs" rule from breaking plain workflows.

#### `test_resolve_profile_project_wins_over_home`

**Setup**: `.goga/profiles/mixa.yml` = `{a: 1}`; home bundle
`{"mixa": {"a": 2}}`.

**Input**: `resolve_profile("mixa", root/".goga/profiles", home_bundle)`.

**Trace**:
```
resolve_profile → grammar OK → project file exists
  → ResolvedProfile(source=PROJECT, data={"a": 1})
```

**Assertions**: `source is ProfileSource.PROJECT`; `data == {"a": 1}`.

**Sufficiency**: the shadowing rule — a committed project profile beats the
personal home copy of the same name.

#### `test_load_home_profiles_collects_bundle_and_missing_dir_is_empty`

**Setup**: `tmp/home/profiles/` with `a.yml` (`{x: 1}`), `b.yml`
(`{y: {z: 2}}`), a nested subdirectory with an ignored `c.yml`, and a
`notes.txt` (ignored); a second empty path with no directory.

**Input**: `load_home_profiles(tmp/"home/profiles")`;
`load_home_profiles(tmp/"missing")`.

**Trace**:
```
load_home_profiles → sorted glob("*.yml") → parse each (mapping roots)
  → {"a": {"x": 1}, "b": {"y": {"z": 2}}}
load_home_profiles(missing) → not is_dir → {}
```

**Assertions**: bundle equals the two-entry mapping (no `c`, no `notes`);
missing dir → `{}`.

**Sufficiency**: the flat-collection contract and the missing-directory
default (a fresh machine must not fail).

#### `test_render_workflow_env_iteration_produces_valid_yaml`

**Setup**: template text using the mapping-iteration pattern from the
`jinja2` practice:
`stages:\n  worker:\n    env:\n{% for k, v in worker.env.items() %}      {{ k }}: {{ v }}\n{% endfor %}`
with context `{"worker": {"env": {"A": "1", "B": "2"}}}`.

**Input**: `render_workflow(text, context, "wf.yml")`.

**Trace**:
```
render_workflow → Environment(trim_blocks, lstrip_blocks, …)
  → render → "stages:\n  worker:\n    env:\n      A: 1\n      B: 2\n"
  → yaml.safe_load(rendered) parses; map == {"A": "1", "B": "2"}
```

**Assertions**: rendered parses as YAML; the env map round-trips exactly.

**Sufficiency**: the trim/lstrip flag set is load-bearing — with wrong flags
the block tags leave blank lines that break YAML. Prevents an "innocent"
environment change.

#### `test_parse_workflow_accepts_build_block_alone`

**Setup** (input text):
```yaml
build:
  agent: claude
  env: {X: "1"}
  review:
    agent: codex
    env: {Y: "2"}
    additional:
      agent: gemini
      env: {Z: "3"}
```

**Input**: `parse_workflow(text)`.

**Trace**:
```
parse_workflow → top-level keys {build} OK → build block validated
  → WorkflowBuild(agent="claude", env={"X": "1"}, review_agent="codex",
                  review_env={"Y": "2"}, review_additional_agent="gemini",
                  review_additional_env={"Z": "3"})
  → empty rule: build is not None → valid
```

**Assertions**: all six fields; `document.profile is None`; no raise.

**Sufficiency**: the build-block-only workflow is a first-class form; guards
the empty-rule extension and the field flattening.

#### `test_merge_workflow_build_keywise_env_and_agents`

**Setup**: `BuildConfig(agent="claude", env={"A": "1", "B": "2"}, review=
ReviewConfig(agent="codex", env={"C": "3"}, additional=
AdditionalReviewConfig(agent="gpt", env={}, patience=2, max_iterations=4)))`;
block = `WorkflowBuild(env={"B": "over"}, review_agent=None,
review_env={"D": "4"})`.

**Input**: `merge_workflow_build(config, block)`.

**Trace**:
```
merge → root agent "claude" (block.agent None) → env {"A": "1", "B": "over"}
  → review agent "codex" (block review_agent None) → review env {"C": "3", "D": "4"}
  → additional verbatim (agent "gpt", patience 2, max_iterations 4)
  → NEW BuildConfig; inputs unmutated
```

**Assertions**:
```
merged.env == {"A": "1", "B": "over"}
merged.review.env == {"C": "3", "D": "4"}
merged.agent == "claude"; merged.review.additional.patience == 2
config.env == {"A": "1", "B": "2"}          # input unmutated
```

**Sufficiency**: the override-one-variable use case — absent fields never
override, key-wise merge keeps config survivors, purity.

#### `test_merge_workflow_build_constructs_review_when_none`

**Setup**: `BuildConfig(agent="claude", env={}, review=None)`; block sets
`review_env={"R": "1"}` and `review_additional_agent="gemini"`.

**Input**: `merge_workflow_build(config, block)`.

**Trace**:
```
review is None + review fields set → new ReviewConfig(env={"R": "1"},
  agent=None, …defaults) + new AdditionalReviewConfig(agent="gemini", env={})
```

**Assertions**: `merged.review is not None`;
`merged.review.env == {"R": "1"}`;
`merged.review.additional.agent == "gemini"`; other review fields None/
defaults.

**Sufficiency**: `resolve_run_settings` requires a well-formed two-part
configuration — a None review part would crash downstream.

#### `test_write_role_env_wrappers_generates_independent_closures`

**Setup**: `RunSettings` with tasks agent "claude" env `{"T": "1"}`, review
agent "codex" env `{"R": "2"}` (additional inheriting "codex",
env `{"A": "3"}`); `cli_entries = {"T": "CLI", "GOGA_PROFILE": "x"}`;
tmp dir patched in place of `/tmp/goga-build-env` (monkeypatch the module
constant or the base path).

**Input**: `write_role_env_wrappers(settings, cli_entries)`.

**Trace**:
```
mkdir base → per role: resolve_wrapper_path(agent) →
  layer = {**role_env, **cli_entries} − ENGINE_KEYS  # CLI wins per key,
                                                     # GOGA_PROFILE dropped
  → tasks.sh exports T=CLI; review.sh exports R=2; additional.sh exports A=3
  → each ends with exec <wrapper> "$@"
```

**Assertions**:
```
paths.keys() == {"tasks", "review", "additional"}
tasks.sh content contains "export T=CLI" and NOT "T=\"1\""
review.sh contains "export R=2" and NOT "T="
additional.sh contains "export A=3" and NOT "R="
none contains GOGA_PROFILE
all files have the exec bit
```

**Sufficiency**: the three independence rules — CLI above task env, engine
keys dropped, layers isolated per role — and the exec delegation.

#### `test_run_build_pass_launches_without_env_layer`

**Setup**: `run_ralphex` monkeypatched (record call); minimal settings.

**Input**: `run_build_pass("plan.md", settings, {"--tasks-only": True},
"/tmp/w.sh", False)`.

**Trace**:
```
run_build_pass → write_ralphex_config(settings, "/tmp/w.sh")  # mocked FS ok
  → run_ralphex(plan, options, dry_run)      # NO env kwarg
```

**Assertions**: the recorded call has no `env` argument (or `env is None`);
`claude_command` in the written config is the wrapper path.

**Sufficiency**: the launch-layer removal — task env now rides the wrapper;
a regression here would resurrect the double-application path.

#### `test_apply_stage_env_wrappers_patches_only_command_fields`

**Setup**: compile a real flow (or handcraft) with stages `build` (workflow
env `{"E": "1"}`, agent `claude`) and `test` (no env, agent `claude`); write
the serialized flow-file to tmp; note its bytes.

**Input**: `apply_stage_env_wrappers(stages, workflow, None, flow_path)`.

**Trace**:
```
claims = {build} → target = resolve_wrapper_path("claude")
  → /tmp/goga-stage-env/build.sh written (exports E=1, exec target)
  → flow text patched: build's command line value replaced
  → test's block byte-identical; every other line unchanged
```

**Assertions**:
```
result[build].fields["command"] == str(wrapper)
result[test] is stages[test]                    # SAME object
patched_text.splitlines() differs from original ONLY on build's command line
wrapper script contains "export E=1"
```

**Sufficiency**: the targeted-patch invariant — the flow output stays
byte-identical except the command fields of env-declaring stages.

#### `test_apply_stage_env_wrappers_env_free_run_is_byte_identical`

**Setup**: a compiled flow-file whose workflow declares no stage env.

**Input**: `apply_stage_env_wrappers(stages, workflow, "claude", flow_path)`.

**Trace**: no claims → the routine returns the input list without touching
`flow_path`.

**Assertions**: returned list IS the input list (same objects); file mtime
and content unchanged; no `/tmp/goga-stage-env` created.

**Sufficiency**: the env-free regression net — existing workflows must
produce identical flow output after the feature lands.

#### `test_apply_stage_env_wrappers_loop_copies_each_get_wrapper`

**Setup**: workflow stage `worker` with `loop: 3`, `env: {"N": "9"}`;
compiled ids `worker-1..3`.

**Input**: `apply_stage_env_wrappers(stages, workflow, "claude", flow_path)`.

**Trace**: three claims (suffix match); three distinct wrapper files each
exporting `N=9`; three command fields patched.

**Assertions**: three wrapper files exist; each copy's command points at
its own wrapper; each wrapper exports the same values.

**Sufficiency**: loop multiplication — every expanded copy carries the env.

#### `test_run_pipeline_launch_layer_exports_effective_profile`

**Setup**: monkeypatch env: `AFM_DIR`, `GOGA_HOME_PROFILES` = encoded
bundle with profile "mixa", `GOGA_EXTRA_ENV` = payload `{"K": "v"}`,
`GOGA_WORKFLOW="hard"`; project pipeline + workflow `hard.yml` with
`profile: mixa` default and `pipeline.env` containing
`{"GOGA_PROFILE": "evil", "OTHER": "1"}` in config; `run_flow` monkeypatched
to capture `env`.

**Input**: `run_pipeline("deploy", project_dir, user_dir, 5000)`.

**Trace**:
```
decode bundle → resolve_workflow → load_workflow (default "mixa" activates)
  → feedback line printed to stdout
  → launch layer = pipeline.env ⊕ CLI entries − ENGINE_KEYS
      {"OTHER": "1", "K": "v", "GOGA_PROFILE": "mixa"}   # "evil" dropped,
                                                          # effective added
  → run_flow(env=layer)
```

**Assertions**:
```
captured_env["GOGA_PROFILE"] == "mixa"
captured_env["OTHER"] == "1"
stdout contains 'Pipeline running with workflow "hard" and profile "mixa"'
```

**Sufficiency**: the nested-inheritance keystone — the effective profile
(any channel, here the workflow default) is exported, collisions dropped,
and the ambient GOGA_WORKFLOW survives via the overlay semantics.

#### `test_pipeline_cli_parses_profile_flag_both_modes`

**Setup**: `describe_pipeline` / `run_pipeline` monkeypatched (record args).

**Input**: `pipeline_cli(["run", "deploy", "--info", "-p", "mixa"])` and
`pipeline_cli(["run", "deploy", "--port", "5000", "--profile", "mixa"])`.

**Trace**: argparse binds `profile="mixa"` in both modes; forwarded
verbatim.

**Assertions**: both recorders received `profile="mixa"`.

**Sufficiency**: the flag must bind in info and run modes (the card mirrors
the run).

#### `test_build_command_writes_profile_envfile_lines`

**Setup**: home `~/.goga/profiles/mixa.yml` (via HOME monkeypatch);
`GOGA_PROFILE="ambient"` in the host env; docker/runner machinery mocked;
project config with image + build section.

**Input**: click runner invokes `goga build plan.md -w hard -p mixa -e K=V`.

**Trace**:
```
load_home_profiles → bundle non-empty
  → env-file lines: …, K=V, GOGA_EXTRA_ENV=…, GOGA_PROFILE=ambient,
    GOGA_HOME_PROFILES=<payload>        # engine-skip: K=V only if key collides
  → argv: … --workflow hard --profile mixa
  → NO GOGA_WORKFLOW line
```

**Assertions**: env-file content contains the two lines in order after the
payload; argv contains both long flags; `GOGA_WORKFLOW` not in the file;
docker run called once.

**Sufficiency**: the host half of the carriage and the flag forwarding;
GOGA_WORKFLOW exclusion (the pipeline-run launcher owns it).

#### `test_run_pipeline_container_envfile_workflow_decision_matrix`

**Setup**: project with workflows `deploy.yml`; runner mocked; env-file
captured.

**Input** (three cases): (a) `workflow="deploy"`; (b) no workflow flag,
auto-match file exists; (c) `no_workflow=True`.

**Trace**: the `GOGA_WORKFLOW` line is written exactly when a workflow will
be applied — (a) explicit name, (b) "deploy" (basename auto-match exists),
(c) no line; the argv carries `-w`/neither accordingly.

**Assertions**: per case — line present with the right value or absent;
stdout contains NO "Pipeline running with workflow" line (host prints
none).

**Sufficiency**: the decision mirror and the removal of the host-side log
line.

#### `test_info_container_envfile_only_with_cargo`

**Setup**: runner mocked; two cases — ambient `GOGA_PROFILE=""` +
empty bundle; ambient `"mixa"` + empty bundle.

**Input**: `run_pipeline_info_container(None, True, config, {}, False,
None, None, (), home_profiles)` / variant with `profile="mixa"`.

**Trace**: without cargo → docker params carry no env-file; with cargo →
an env-file with exactly `GOGA_PROFILE=mixa` (bundle empty → no
GOGA_HOME_PROFILES line, never GOGA_WORKFLOW).

**Assertions**: params contain/omit `env_file`; when present, the file
content is exactly the cargo lines.

**Sufficiency**: the minimal read-only shape default and the cargo
exception.

---

### Negative Tests

#### `test_parse_workflow_rejects_env_in_extend_entry`

**Setup/Input**: text with `extend: {extra: {after: [build], env: {A: "1"}}}`.

**Trace**: `_reject_forbidden_extend_keys` raises before positional checks.

**Assertions**: `WorkflowSyntaxError` with message
`env is forbidden in workflow.extend.extra`.

**Sufficiency**: `env` is stages-only by design — an extend-entry env would
bypass the stage authoring model.

#### `test_parse_workflow_rejects_proxy_in_build_block`

**Setup/Input**: build block carrying `proxy: http://x`.

**Assertions**: message matches
`unknown key in workflow.build: proxy; valid keys: agent, env, review.agent,
review.env, review.additional.agent, review.additional.env`.

**Sufficiency**: the host launcher must not be forced to read workflow
files — the strict key set is the enforcement point.

#### `test_parse_workflow_rejects_non_str_profile`

**Setup/Input**: `profile: 42`.

**Assertions**: `non-str value in workflow.profile`.

**Sufficiency**: the default is a name; numbers/mappings are authoring
errors, not silently ignored.

#### `test_parse_workflow_rejects_bad_stage_env_shapes`

**Setup/Input**: `env: [1, 2]` (non-mapping) and `env: {A: 1}` (non-str
value) under a stage.

**Assertions**: `non-mapping env in workflow.stages.build` /
`non-str value in workflow.stages.build.env.A`.

**Sufficiency**: the string-map pattern for per-stage env.

#### `test_resolve_profile_rejects_traversal_names`

**Setup/Input**: `resolve_profile("../secrets", …)`, `resolve_profile("..",
…)`, `resolve_profile("a/b", …)`, and `resolve_profile(".hidden", …)` (the
grammar requires an alphanumeric first character, so dot-prefixed names
fail too).

**Assertions**: each raises the strict grammar error naming the profile.

**Sufficiency**: the name becomes a filesystem component — the grammar is
the path-traversal guard.

#### `test_resolve_profile_missing_everywhere_names_both_locations`

**Setup**: no project profile, empty bundle.

**Input**: `resolve_profile("ghost", project_dir, {})`.

**Assertions**: the error message contains `"ghost"`, the project dir, and
the home location wording.

**Sufficiency**: actionable miss — the user must learn where goga looked.

#### `test_resolve_profile_malformed_project_file_strict_names_profile_and_path`

**Setup**: project `.goga/profiles/bad.yml` = `- a` (non-mapping root); a
second single-file setup with `: : :` (invalid YAML); home bundle empty.

**Input**: `resolve_profile("bad", root/".goga/profiles", {})`.

**Trace**:
```
resolve_profile → grammar OK → project file exists
  → yaml parse fails / root is not a mapping
  → strict error naming the profile and the path
  → NO home fallback (the project file wins even when malformed — strict,
    never a silent fall-through)
```

**Assertions**: raises the strict error; the message contains `"bad"` and
the file path; the home bundle is never consulted.

**Sufficiency**: pins the declared failure mode of `resolve_profile` step
2 — a malformed project profile must surface as a strict error, not
silently fall through to the home bundle.

#### `test_render_workflow_syntax_error_names_file_and_line`

**Setup/Input**: text with `{% if %}` (unclosed block) and
`source_name="broken.yml"`.

**Assertions**: the raised error message contains `broken.yml`, the line
number, and the underlying message.

**Sufficiency**: a swallowed or location-less Jinja error would strand the
author.

#### `test_load_home_profiles_malformed_file_strict_names_path`

**Setup**: home dir with `bad.yml` = `: : :` (invalid YAML) and `list.yml`
= `- a` (non-mapping root).

**Assertions**: each single-file setup raises naming the offending path.

**Sufficiency**: a malformed personal profile must fail on the host before
any container launches — never half-way through a run.

#### `test_decode_home_profiles_damaged_payload_clean_error`

**Setup/Input**: `"not-base64!!!"`, valid base64 of non-JSON, of a list, of
`{"a": "b"}` (values must be mappings).

**Assertions**: each raises `ValueError` containing `GOGA_HOME_PROFILES`
and no payload content.

**Sufficiency**: the carriage decode contract — one clean error, no leaks.

#### `test_run_pipeline_damaged_bundle_no_events_no_launch`

**Setup**: `GOGA_HOME_PROFILES="###"`; `run_flow` and the hooks emit
functions monkeypatched with counters.

**Input**: `run_pipeline("deploy", …)`.

**Assertions**: returns 1; a clean stderr message; no emit_* calls; no
`run_flow` call.

**Sufficiency**: the pre-run strictness boundary — nothing partial
executes.

#### `test_build_damaged_bundle_one_clean_error_before_events`

**Setup**: in-container `build()` with env `GOGA_HOME_PROFILES="###"`;
hooks and `run_ralphex` mocked with counters.

**Assertions**: exit 1; no events; no pass launches; message names the
variable.

**Sufficiency**: symmetric boundary on the build path.

#### `test_build_workflow_build_block_without_config_build_section`

**Setup**: config with `build=None`; a loaded workflow carrying a `build`
block (direct in-container invocation).

**Input**: `build("plan.md", config, {"workflow": "hard"})` with
GOGA_WORKFLOW unset — reaching the layering step.

**Assertions**: exit 1 with a clean error naming the build-section
requirement (no AttributeError traceback, no events).

**Sufficiency**: the contract's "instead of the raw attribute failure"
guarantee (decision D2).

#### `test_build_command_rejects_leading_dash_values`

**Setup/Input**: `-w "-x"`, `-p "-x"` via the click runner.

**Assertions**: clean error (exit 1), no docker invocation.

**Sufficiency**: argv parsability — click would swallow a flag-looking
token.

#### `test_apply_stage_env_wrappers_strict_error_without_any_agent`

**Setup**: workflow stage `build` with env, no agent; `global_agent=None`.

**Assertions**: strict error naming the stage; no wrapper written; flow-file
untouched.

**Sufficiency**: a wrapper with no exec target would produce a stage that
fails at run time — the failure must be pre-run.

#### `test_write_role_env_wrappers_rejects_illegal_env_key`

**Setup**: `RunSettings` with all three role agents set (tasks agent
"claude", review "codex", additional inheriting); tasks env layer
`{"BAD=KEY": "1"}`; the wrapper base dir patched to a tmp path.

**Input**: `write_role_env_wrappers(settings, {})`.

**Trace**:
```
write_role_env_wrappers → mkdir base → role loop reaches tasks
  → key-legality check on "BAD=KEY" fails ("=" is illegal in an env name)
  → strict error naming the role — raised BEFORE any script file is written
```

**Assertions**: raises the strict error naming `tasks`; no wrapper file
exists in the base directory.

**Sufficiency**: D8 declares key-legality validation at generation — an
unvalidated key would produce a broken script failing only at exec time,
far from the cause (a regression here resurrects the runtime failure).

---

### Edge Case Tests

#### `test_parse_workflow_empty_and_profile_only_workflows`

**Setup/Input**: (a) empty text `{}` … a mapping with nothing; (b)
`profile: mixa` alone; (c) `build: {}` alone.

**Assertions**: (a) and (b) raise the empty-workflow error naming all
options; (c) is valid — an empty `build: {}` block yields `WorkflowBuild()`
with all six fields None, which satisfies "a workflow consisting of the
build block alone is valid".

**Sufficiency**: the empty-rule boundary — activation is not content; a
build-only workflow is.

#### `test_resolve_activation_whitespace_and_precedence`

**Setup/Input**:
`resolve_activation(" ", "env", "default")` → `"env"`;
`resolve_activation(None, "", "  ")` → `None`;
`resolve_activation("cli", "env", "default")` → `"cli"`.

**Assertions**: exact returns per the strongest-first rule with
whitespace-as-unset.

**Sufficiency**: the precedence fold is the single activation arbiter used
by every consumer.

#### `test_load_workflow_templated_default_does_not_participate`

**Setup**: workflow `profile: '{{ worker.profile }}'` plus body using
`{{ worker.agent }}`; project profile `worker` data
`{profile: mixa, agent: codex}`; channels None.

**Input**: `load_workflow(path, None, None, {})`.

**Trace**: the peek sees `{{ worker.profile }}` — Jinja markers → not a
literal default → None → no activation → empty-context render (the body's
`{{ worker.agent }}` renders empty) → parsed document; profile is None.

**Assertions**: `loaded.profile is None`; no strict error.

**Sufficiency**: the raw-text peek rule — defaults must be literal; a
rendered-only default never activates (and never crashes the grammar
check).

#### `test_apply_skip_stages_and_overlay_preserve_profile_and_build`

**Setup**: `WorkflowDocument(prompt="p", stages={}, extend={},
memory=None, profile="mixa", build=WorkflowBuild(env={"X": "1"}))`.

**Input**: `apply_skip_stages(doc, ["build"])`; then
`merge_workflow_overlay(merged, [ToolContribution(tool="t",
document=WorkflowDocument(stages={"new": WorkflowStage(agent="a")}))])`.

**Assertions**: both results carry `profile == "mixa"` and the SAME build
object; the overlay stage merge honors an authored `env` (authored env
unbeatable; a tool env fills an unset slot — add a stage `s` authored env
`{"A": "1"}`, tool env `{"A": "2", "B": "3"}` → merged env `{"A": "1",
"B": "3"}`).

**Sufficiency**: the full-model survival rule — a rebuild that drops
profile/build would silently change activation or lose build instructions;
the field-set-complete merge must include `env`.

#### `test_parse_workflow_stage_env_empty_map_equals_absence`

**Setup/Input**: stage with `env: {}`.

**Assertions**: `stages["s"].env is None`.

**Sufficiency**: symmetric with `notes`; an empty map must not claim the
stage into wrapper generation.

#### `test_encode_home_profiles_empty_bundle_and_roundtrip`

**Setup/Input**: `encode_home_profiles({})` → `""`; a nested bundle →
decode(encode(b)) == b; encode deterministic across calls.

**Assertions**: exact values; `decode_home_profiles("")` → `{}`.

**Sufficiency**: the carriage write-when-non-empty rule depends on the
empty↔"" equivalence.

#### `test_build_no_workflow_ignores_activation_entirely`

**Setup**: env `GOGA_PROFILE="mixa"` + valid bundle; no `-w`, no
GOGA_WORKFLOW.

**Input**: `build("plan.md", config, {})` (launch mocked).

**Assertions**: no profile loads (no strict error even though the name
would resolve), no feedback line, behavior identical to the pre-feature
build.

**Sufficiency**: "with no workflow in effect, activation is ignored
entirely" — the isolation rule.

#### `test_build_feedback_line_only_with_effective_profile`

**Setup**: workflow in effect without a profile (case A) and with (case B);
stderr captured.

**Assertions**: case A prints NO line (unlike the pipeline, which prints
the workflow-only form); case B prints
`Build running with workflow "hard" and profile "mixa"`.

**Sufficiency**: the build/pipeline feedback asymmetry is contractual.

#### `test_apply_stage_env_wrappers_inserts_command_when_absent`

**Setup**: workflow stage with env but NO agent; `global_agent="claude"`;
compiled stage has no `command` field.

**Input**: `apply_stage_env_wrappers(...)`.

**Assertions**: the patched block contains a `command:` line at the
canonical position (before the first present canonical key after command /
before `depends_on`); every pre-existing line is unchanged; the returned
stage's fields contain `command`.

**Sufficiency**: the insertion case of the patch — replacing-only would
silently skip agentless env stages.

#### `test_resolve_build_workflow_env_fallback_and_empty_strings`

**Setup**: env `GOGA_WORKFLOW="hard"`; cases: no CLI (→ "hard" loads);
CLI `"custom"` (→ custom wins); CLI `""` (→ env used); both empty (→ None).

**Assertions**: per case — the loaded document's identity or None.

**Sufficiency**: the CLI>env fold with empty-as-unset on the workflow axis.

#### `test_nested_build_inherits_workflow_and_profile` (integration,
`tests/integration/`)

**Setup**: launch layer captured by a mocked `run_flow` inside
`run_pipeline` (profile "mixa", workflow "hard" ambient via env-file
semantics: monkeypatch os.environ GOGA_WORKFLOW="hard" +
GOGA_PROFILE absent); then run `resolve_build_workflow(None, "hard",
None, "mixa", bundle)` with the same fixture data.

**Trace**: the launch layer carries `GOGA_PROFILE=mixa`; the ambient env
carries `GOGA_WORKFLOW=hard`; the build-side resolution picks both up with
no additional options.

**Assertions**: `resolve_build_workflow(...)` returns a `LoadedWorkflow`
whose profile is "mixa"; the workflow file is "hard".

**Sufficiency**: the headline scenario — a build invoked inside the
pipeline runtime inherits workflow AND profile through the environment
channels alone.

#### `test_describe_pipeline_applies_profile_channels`

**Setup**: pipeline `deploy` with stage `build`; workflow `deploy.yml`
guarding an extend entry with `{% if worker.hardening %}` (the entry adds
stage `harden` after `build`); project profile `mixa.yml` =
`{worker: {hardening: true}}`; `GOGA_PROFILE`/`GOGA_HOME_PROFILES` cleared
from the environment.

**Input**: `describe_pipeline("deploy", project_dir, user_dir, None,
False, profile="mixa")` and the same call with `profile=None`.

**Trace**:
```
with profile="mixa": resolve_workflow → load_workflow(cli="mixa")
  → resolve_profile("mixa", project dir, {}) → project file
  → render (guard TRUE) → document carries extend "harden"
  → compile → card stages [build, harden]
with profile=None: channels empty, workflow has no literal default
  → render with empty context (guard FALSE) → no extend → [build]
```

**Assertions**: with the profile, `"harden"` is in
`[s.id for s in card.stages]`; without it, it is not; no exception on
either path.

**Sufficiency**: the CODEMANIFEST requirement "the card keeps reflecting
what a run with the same flags would apply" — a card that ignored the
activation channels would silently diverge from the runtime composition.

#### `test_load_workflow_oserror_propagates_unchanged`

**Setup**: no file at the path (existence guards belong to the callers).

**Input**: `load_workflow(root/".goga/workflows/ghost.yml", None, None,
None)`.

**Trace**: `read_text()` raises `FileNotFoundError` before the peek, the
activation fold, or any rendering.

**Assertions**: raises `OSError` (a `FileNotFoundError`) — NOT wrapped in
`WorkflowSyntaxError` or any other goga error.

**Sufficiency**: the contract says callers guard existence and OSError
propagates unchanged; wrapping it would break the error discrimination
the silent-miss guards of `resolve_workflow`/`resolve_build_workflow`
rely on.

---

## Additional Instructions for the Implementation Agent

- **Design decisions fixed by this document** (all within the contract
  text; no CODEMANIFEST change needed):
  - **D1 — engine-key drop set** for `write_role_env_wrappers` (and the
    widened `_ENGINE_ENV_KEYS` of `run_pipeline`): the existing five
    (`AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`, `HTTPS_PROXY`,
    `NO_PROXY`) plus the four GOGA engine variables (`GOGA_PROFILE`,
    `GOGA_WORKFLOW`, `GOGA_HOME_PROFILES`, `GOGA_EXTRA_ENV`). Per-stage env
    (`apply_stage_env_wrappers`) exports values VERBATIM — no dropping; it
    layers above all global layers by contract.
  - **D2 — the no-build-section guard** lives in `build()` at the layering
    step: a workflow in effect whose document carries a `build` block and
    `config.build is None` → one clean logged error naming the requirement,
    exit 1, no events (the host launcher already guards host-side; this
    covers direct in-container invocations). `merge_workflow_build` itself
    always receives a non-None `BuildConfig`.
  - **D3 — the card does not generate wrappers**: `describe_pipeline` never
    invokes `apply_stage_env_wrappers`; the card/run equivalence is
    structural (wrappers alter only `command` fields, which the card does
    not report).
  - **D4 — the raw-text peek**: line-anchored scan for a column-0
    `profile:` key; strip quotes and trailing comments; whitespace-only →
    None; a value containing `{{`/`{%` is not a literal default → None.
  - **D5 — the flow-file patch is a text-level targeted patch** (never a
    YAML round-trip — the canonical serializer's marker styles would not
    survive, breaking byte-identity): locate each selected stage's block by
    its `- id:` anchor, replace the existing `command:` value or insert the
    line at the canonical position; every other byte untouched.
  - **D6 — loop-copy matching**: exact id match first, then
    `<name>-<digits>` suffix; exact claims beat suffix claims.
  - **D7 — wrapper locations**: `/tmp/goga-build-env/{tasks,review,
    additional}.sh` (build) and `/tmp/goga-stage-env/<stage-id>.sh`
    (pipeline; sanitize the id, append a short digest when it deviates from
    `[A-Za-z0-9._-]+`). Both container-local, `chmod 0o755`, idempotent
    overwrites.
  - **D8 — wrapper script shape**: `#!/bin/sh`, one `export KEY=<shlex
    .quote(value)>` per entry, then `exec <resolved wrapper> "$@"`; validate
    key legality at generation (strict error naming the role/stage).
  - **D9 — feedback names**: the workflow name printed is the resolved
    file stem (explicit `-w` name, or the auto-match basename = pipeline
    name); pipeline → stdout, build → stderr.
- Facade updates are part of the work: `goga/pipeline/workflow/__init__.py`
  exports the nine new names; `goga/docker/__init__.py` exports
  `encode_home_profiles`/`decode_home_profiles`; `goga/build/__init__.py`
  and `goga/pipeline/__init__.py` gain `resolve_build_workflow`,
  `merge_workflow_build`, `write_role_env_wrappers`,
  `apply_stage_env_wrappers` (per the facade-import checklist of the
  architecture plan).
- `apply_skip_stages`, `hooks/overlay.py` (`_STAGE_FIELDS` gains `env`;
  the rebuilt `WorkflowDocument` carries `profile`/`build`), and
  `run_settings.py::_resolve_additional` (passes `env`) are mandatory
  touch-points even though their signatures barely move.
- Delete the now-dead env plumbing in `goga/build/build.py`
  (`_compose_pass_env`, the `env` forwarding in `_launch_pass`) and the
  host-side `_resolve_workflow_log_name` machinery in
  `run_pipeline_container.py`.
- Keep `parse_workflow` exported and importable — the pipeline cell's
  annotations still reference it, and tests use it directly.
- Test placement follows the project map: `tests/pipeline/workflow/`,
  `tests/docker/`, `tests/config/project/`, `tests/build/`,
  `tests/pipeline/`, `tests/pipeline/hooks/`, `tests/commands/build/`,
  `tests/commands/pipeline/`, `tests/integration/` — contract/logic pairs
  for new modules, additions to the existing files for changed ones.
- Run `goga lint` and `goga schema` after the facade edits (both were clean
  at design time: 0 errors / 91 cells) and the full pytest battery in a
  venv with `jinja2>=3.1` installed.
