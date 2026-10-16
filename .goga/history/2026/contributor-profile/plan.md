# Plan: `contributor-profile`

## Purpose

Implement the contributor-profile feature across nine cells: profile activation
(three channels: CLI `--profile` > `GOGA_PROFILE` > workflow `profile:` default),
project-then-home profile resolution, whole-file Jinja rendering of
workflow-files before parsing, the `GOGA_HOME_PROFILES` docker carriage, the
six-field workflow `build:` block layered onto build settings
(config < workflow `build:` < CLI), per-role and per-stage sh closure wrappers
delivering env layers (replacing the removed ralphex-launch env layer), and the
`-w/--workflow` / `-p/--profile` surfaces of both host commands.

After implementation the package provides: `goga pipeline [--profile P]` and
`goga build [-w W] [-p P]` activate profiles from project `.goga/profiles/` or
the personal `~/.goga/profiles/` bundle; workflow-files render as Jinja
templates with the profile content as context; per-stage `env:` and workflow
`build:` blocks reach the executing agents through generated wrapper scripts;
the ralphex launch carries no env layer.

Strategy: bottom-up by the dependency order fixed in the design —
workflow (leaf) → docker carriage → config/project → pipeline/hooks → build →
pipeline → commands/build → commands/pipeline → cross-cell integration tests →
final sweep. Every coding task follows the TDD workflow structured around the
REPL development cycle (see Mandatory Rules).

## Context

### Contract Surface

The contracts below are already materialized in the CODEMANIFEST files
(read-only for the implementation agent). Signatures are authoritative.

**Cell `goga/pipeline/workflow`** (leaf — no Imports; stdlib + PyYAML + jinja2 only)

- **`ProfileSource()`** — `profile_source.py` — str-backed Enum: `PROJECT = "project"`, `HOME = "home"`.
- **`ResolvedProfile(name: str, data: dict[str, Any], source: ProfileSource)`** — `resolved_profile.py` — frozen dataclass (`frozen=True, kw_only=True`); `.data` is the whole profile content (rendering context). No wrapper resolution, no rendering here.
- **`LoadedWorkflow(document: WorkflowDocument, profile: ResolvedProfile | None)`** — `loaded_workflow.py` — frozen dataclass (`frozen=True, kw_only=True`); no revalidation.
- **`WorkflowBuild(agent: str | None = None, env: dict[str, str] | None = None, review_agent: str | None = None, review_env: dict[str, str] | None = None, review_additional_agent: str | None = None, review_additional_env: dict[str, str] | None = None)`** — `workflow_build.py` — `@dataclass(kw_only=True)`; fixed field order; all default None; built only by `parse_workflow`; no merging here.
- **`load_home_profiles(home_dir: Path) -> profiles: dict[str, dict[str, Any]]`** — `load_home_profiles.py` — flat `*.yml` scan (non-recursive); missing dir → `{}`; invalid YAML / non-mapping root → one strict error naming the file path; deterministic (sorted); no env reads; no name-grammar validation (the REQUESTED name is validated at lookup).
- **`resolve_profile(name: str, project_dir: Path, home_profiles: dict[str, dict[str, Any]]) -> profile: ResolvedProfile`** — `resolve_profile.py` — grammar `^[A-Za-z0-9][A-Za-z0-9._-]*$`, `.`/`..` forbidden (path-traversal guard; violation → strict error naming the profile); `<project_dir>/<name>.yml` exists → parse (invalid YAML / non-mapping root → strict error naming profile and path; NO home fall-through) → source PROJECT; else `name in home_profiles` → source HOME; else strict error naming profile and BOTH locations. Project wins on the same name.
- **`render_workflow(text: str, profile_data: dict[str, Any], source_name: str = "") -> rendered: str`** — `render_workflow.py` — `Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, autoescape=False)` with standard `Undefined` (never `StrictUndefined`); `env.from_string(text).render(**profile_data)`; `TemplateSyntaxError` → one strict error carrying `source_name`, `exc.lineno`, `exc.message`; `UndefinedError` propagates unwrapped; template-free input renders to itself; no YAML parsing, no file/env reads.
- **`resolve_activation(cli_profile: str | None, env_profile: str | None, workflow_default: str | None) -> name: str | None`** — `resolve_activation.py` — first non-empty of (cli, env, default); whitespace-only = unset; all unset → None; pure.
- **`load_workflow(workflow_path: Path, cli_profile: str | None = None, env_profile: str | None = None, home_profiles: dict[str, dict[str, Any]] | None = None) -> loaded: LoadedWorkflow`** — `load_workflow.py` — the chain: `read_text()` (OSError propagates unchanged) → peek literal top-level `profile:` from RAW text (column-0 line-anchored; strip quotes/trailing comment; whitespace-only → None; value containing `{{`/`{%` → None) → `resolve_activation` → `resolve_profile(name, Path.cwd()/".goga"/"profiles", home_profiles or {})` when a name resolved → `render_workflow(text, profile.data if profile else {}, source_name=workflow_path.name)` (rendering ALWAYS runs) → `parse_workflow(rendered)` → `LoadedWorkflow(document, profile)`. No env reads; no path composition/existence guards (callers own them); no input mutation.
- **`parse_workflow(text: str) -> workflow: WorkflowDocument`** (CHANGED: path → rendered text) — `parse_workflow.py` — six top-level keys (`prompt, stages, extend, memory, profile, build`); unknown → `"unknown key in workflow: KEY; valid keys: prompt, stages, extend, memory, profile, build"`; `profile` non-str → `"non-str value in workflow.profile"`, empty/whitespace → None; `build` non-mapping → `"non-mapping build block in workflow"`. `_STAGE_KEYS` = `(agent, env, prompt, loop, skills, skip, approve, manual, notes, reflect, memory)`; stage `env`: non-dict → `"non-mapping env in workflow.stages.NAME"`, non-str value → `"non-str value in workflow.stages.NAME.env.KEY"`, empty map → None. `env` joins the forbidden extend keys → `"env is forbidden in workflow.extend.NAME"` (checked with the other forbidden keys, before positional/type validation). Build block strict keys: `agent, env, review.agent, review.env, review.additional.agent, review.additional.env` — any other key (incl. `proxy`, `hosts`) → `"unknown key in workflow.build.…: KEY; valid keys: agent, env, review.agent, review.env, review.additional.agent, review.additional.env"`; agent non-str → `"non-str value in workflow.build[.review[.additional]].agent"`; env non-mapping → `"non-mapping env in workflow.build[.review[.additional]]"`; non-str value → `"non-str value in ….env.KEY"`; result → `WorkflowBuild(agent, env, review_agent, review_env, review_additional_agent, review_additional_env)`. Empty rule: `prompt ∧ stages ∧ extend ∧ memory ∧ profile ∧ build` all absent → `"empty workflow — provide at least prompt, one stage, one extend entry, the memory block, or the build block"` (a `build:`-only workflow is valid; a `profile:`-only workflow is not). Do not read files or render here.
- **`WorkflowStage(agent=None, env: dict[str, str] | None = None, prompt=None, loop=None, skills=None, skip=False, approve=None, manual=None, notes=None, reflect=None, memory=None)`** (CHANGED) — `workflow_stage.py` — `env` at position 2 of the fixed field order.
- **`WorkflowDocument(prompt=None, stages=None, extend=None, memory=None, profile: str | None = None, build: WorkflowBuild | None = None)`** (CHANGED) — `workflow_document.py` — field order: prompt, stages, extend, memory, profile, build.

**Cell `goga/docker`** (carriage; mirror of `extra_env.py` for a nested mapping)

- **`encode_home_profiles(profiles: dict[str, dict[str, Any]]) -> value: str`** — `home_profiles.py` — `{}` → `""`; else `json.dumps(profiles, separators=(",", ":"), sort_keys=True)` → standard padded base64 → single-line str. Deterministic; pure; payload never printed/logged; no content validation (host loader owns strictness).
- **`decode_home_profiles(value: str) -> profiles: dict[str, dict[str, Any]]`** — `home_profiles.py` — `""` → `{}`; base64 decode (`validate=True`) → `json.loads`; failure / non-mapping root / a value that is not itself a mapping → `ValueError("GOGA_HOME_PROFILES: invalid payload")` — no payload content in the error. Pure; no env reads; no application of the mapping.

**Cell `goga/config/project`**

- **`AdditionalReviewConfig(agent, patience, max_iterations, env: dict[str, str])`** (CHANGED) — `config.py` — frozen dataclass gains the independent `env` layer: loader pattern = optional string mapping, default empty dict, non-string value → `ValueError`; values verbatim; never inherited from review env.
- **`resolve_run_settings(config: BuildConfig, cli_options: dict) -> settings: RunSettings`** (annotation change) — `run_settings.py` — the `config` parameter is the LAYERED effective build configuration (no layering logic here); step 5 passes the additional `env` verbatim (`_resolve_additional` construction site: `run_settings.py:191` — pass `env=block.env` or `{}`).

**Cell `goga/pipeline/hooks`**

- **`merge_workflow_overlay(base, contributions) -> overlay: WorkflowOverlay`** (CHANGED) — `overlay.py` — the stage merge is field-set-complete over the FULL declared field set of `WorkflowStage` **including `env`** (authored env unbeatable; an unset env takes the value of the later contributing tool that sets it) — never a named-subset copy; the rebuilt `WorkflowDocument` carries `profile`/`build` verbatim.

**Cell `goga/build`**

- **`resolve_build_workflow(workflow_cli: str | None, workflow_env: str | None, cli_profile: str | None = None, env_profile: str | None = None, home_profiles: dict[str, dict[str, Any]] | None = None) -> loaded: LoadedWorkflow | None`** — `resolve_build_workflow.py` — CLI beats env (empty strings = unset); neither → None (activation ignored entirely); compose `<cwd>/.goga/workflows/<name>.yml`; escape → strict `"invalid workflow name"`; missing file → strict error naming the workflow and the directory (explicit selection is strict, unlike the pipeline silent miss); then `load_workflow(...)`.
- **`merge_workflow_build(config: BuildConfig, build_block: WorkflowBuild) -> config: BuildConfig`** — `workflow_build.py` — pure overlay: agent fields `block.X or config.X` (None never overrides); env maps key-wise `{**config.env, **block.env}` (block wins per key) at root/review/additional; `config.review is None` + any review field set → construct NEW `ReviewConfig` (set fields only) + NEW `AdditionalReviewConfig` (env defaulting `{}`); every other field verbatim; returns a NEW `BuildConfig` with new nested models; inputs unmutated. The no-build-section guard (workflow `build:` block + `config.build is None`) lives in `build()` (decision D2) — one clean logged error, exit 1, no events.
- **`write_role_env_wrappers(settings: RunSettings, cli_entries: dict[str, str]) -> wrapper_paths: dict[str, Path]`** — `role_env_wrappers.py` — mkdir `/tmp/goga-build-env` (never under /workspace); per role (tasks, review, additional): agent = the role's settings agent (already inheritance-resolved; None → strict error naming the role BEFORE any pass launches); `resolve_wrapper_path(agent)`; layer = `{**role_env, **cli_entries}` minus the engine-key drop set (D1: existing five `AFM_DIR, AFM_DOCKER_FILE_ROOTS, HTTP_PROXY, HTTPS_PROXY, NO_PROXY` + `GOGA_PROFILE, GOGA_WORKFLOW, GOGA_HOME_PROFILES, GOGA_EXTRA_ENV`); every key validated as a legal environment variable name at generation (violation → strict error naming the role, BEFORE any script file is written); script = `#!/bin/sh` + `export KEY=<shlex.quote(value)>` per entry + `exec <wrapper> "$@"`; write `/tmp/goga-build-env/{tasks,review,additional}.sh`, `chmod 0o755`, idempotent overwrites; return the role→path mapping. Layers stay independent per role; env values never printed/logged.
- **`write_ralphex_config(settings, wrapper_path, additional_wrapper_path: str | None = None)`** (CHANGED) — `ralphex_config.py` — `claude_command = wrapper_path`; engaged external review under full/short sets `external_review_tool=custom`, `custom_review_script=additional_wrapper_path` (None → ralphex default); medium sets `codex_enabled=false`.
- **`run_build_pass(plan, settings, options, wrapper_path, dry_run)`** (CHANGED — `env` parameter REMOVED) — `build_pass.py` — write config with `wrapper_path`; delegate to `run_ralphex(plan, options, dry_run)` with NO env argument — the subprocess inherits the container environment.
- **`build(plan, config, cli_options)`** (CHANGED — 17-step algorithm) — `build.py` — step 1 decodes BOTH payloads (`decode_extra_env` + `decode_home_profiles`; reads `GOGA_WORKFLOW` and `GOGA_PROFILE` once each — exactly these four environment reads on the whole path); step 2 `resolve_build_workflow`; step 3 feedback line to stderr ONLY when a workflow is in effect AND a profile resolved: `Build running with workflow "<w>" and profile "<p>"`; step 4 layering `merge_workflow_build(config.build, document.build)` + the D2 guard; step 5 `resolve_run_settings` over the layered config; steps 12–13 generate wrappers via `write_role_env_wrappers` per pass, `write_ralphex_config` with the tasks (and additional) wrapper paths, launch via `run_build_pass` with the role wrapper path and NO env layer. DELETE the dead plumbing: `_compose_pass_env`, the `env` forwarding in `_launch_pass`, the `env` parameter chain of `run_build_pass`.
- **`main()`** (CHANGED) — `__main__.py` — argparse gains `-w/--workflow NAME` and `-p/--profile NAME` (forwarded into `cli_options`; `-p` is free here — build has no parallel option).

**Cell `goga/pipeline`**

- **`resolve_workflow(pipeline_name, workflow_name, no_workflow, cli_profile=None, env_profile=None, home_profiles=None) -> workflow: LoadedWorkflow | None`** (CHANGED) — `resolve_workflow.py` — returns `LoadedWorkflow | None`; `no_workflow` → None; basename fallback + containment guard + existence check unchanged (silent miss); existing file → `load_workflow(path, cli_profile, env_profile, home_profiles)`; errors propagate.
- **`apply_stage_env_wrappers(stages: list[FlowStage], workflow: WorkflowDocument | None, global_agent: str | None, flow_path: Path) -> stages: list[FlowStage]`** — `stage_env_wrappers.py` — selection: workflow entries with `env is not None` claim compiled stages by exact id, then `<name>-<digits>` loop suffix (exact claims beat suffix); no claims → return the input list WITHOUT reading/writing `flow_path` (byte-identity invariant); per selected stage: exec target = stage agent → `resolve_wrapper_path(agent)`, else `global_agent` → wrapper, else strict pre-run error naming the stage; one sh wrapper per selected stage under `/tmp/goga-stage-env/` (file name = stage id when `[A-Za-z0-9._-]+`, else sanitized + short digest) — `#!/bin/sh`, `export KEY=<shlex.quoted value>` VERBATIM (no engine-key dropping — per-stage layers above all global layers), `exec <target> "$@"`, `chmod 0o755`; text-level targeted patch of `flow_path` (D5 — never a YAML round-trip): replace each selected stage's `command:` value or insert `command: <wrapper>` at the canonical position (before the first present canonical key after command; else before `depends_on`; else at block end); every other byte untouched; return a NEW list — selected stages are NEW `FlowStage` objects with `fields["command"]` = the wrapper path, all others the SAME objects.
- **`run_pipeline(name, project_dir, user_dir, port, workflow=None, no_workflow=False, profile=None, skip=None, parallel=None)`** (CHANGED) — `run_pipeline.py` — step 8: `decode_home_profiles(os.environ.get("GOGA_HOME_PROFILES", ""))` (damaged bundle → one clean error, return 1, no events, afm never launches) + read `GOGA_PROFILE` once → `resolve_workflow(...)`; step 9 feedback line to stdout — `Pipeline running with workflow "<n>" and profile "<p>"` when a profile resolved, else `Pipeline running with workflow "<n>"`, nothing without a workflow (`<n>` = resolved workflow file stem); step 14 (new): `apply_stage_env_wrappers` over the compiled stages; step 19 (widened): launch layer = `pipeline.env` ⊕ decoded CLI entries, engine keys dropped — the engine set is now `{AFM_DIR, AFM_DOCKER_FILE_ROOTS, HTTP_PROXY, HTTPS_PROXY, NO_PROXY, GOGA_PROFILE, GOGA_WORKFLOW, GOGA_HOME_PROFILES, GOGA_EXTRA_ENV}` — plus `GOGA_PROFILE=<effective>` when a profile resolved. Exactly four environment reads total (AFM_DIR, GOGA_EXTRA_ENV, GOGA_PROFILE, GOGA_HOME_PROFILES).
- **`describe_pipeline(name, project_dir, user_dir, workflow, no_workflow, profile=None, skip=None)`** (CHANGED) — `describe_pipeline.py` — reads `GOGA_PROFILE` + decodes `GOGA_HOME_PROFILES` once, passes the channels into `resolve_workflow`; no feedback line; NEVER invokes `apply_stage_env_wrappers` (D3 — the card/run equivalence is structural).
- **`pipeline_cli(argv)`** (CHANGED) — `cli.py` — run subparser gains `--profile/-p NAME` (binds in both info and run modes); forwarded to `describe_pipeline`/`run_pipeline`.
- **`apply_skip_stages(workflow, skip_stages)`** (CHANGED) — `apply_skip_stages.py` — the rebuilt `WorkflowDocument` carries `memory`, `profile`, and `build` verbatim.

**Cell `goga/commands/build`**

- **`build(ctx, plan, …, workflow: str | None, profile: str | None, …)`** (CHANGED) — `build.py` — Click options `-w/--workflow NAME`, `-p/--profile NAME` (reject values starting with `-`; validate `-w` host-side for path containment + file existence under `<cwd>/.goga/workflows/` — a light early diagnostic, the file is never read); before ANY docker activity: `load_home_profiles(Path.home()/".goga"/"profiles")` — malformed home profile → one clean `ClickException` (no image refresh, no launch); env-file gains two engine lines after `GOGA_EXTRA_ENV` under the engine-skip rule (an explicit `-e` key keeps winning): `GOGA_PROFILE=<ambient>` only when non-empty, `GOGA_HOME_PROFILES=<encode_home_profiles(bundle)>` only when the bundle is non-empty; `GOGA_WORKFLOW` is NEVER written by this launcher; in-container argv gains `--workflow NAME` / `--profile NAME` only when set; no feedback line on the host.

**Cell `goga/commands/pipeline`**

- **`pipeline(ctx, …, profile: str | None, …)`** (CHANGED) — `pipeline.py` — `-p/--profile NAME` (the short alias MOVES from `--parallel`, which becomes long-only); profile value joins the leading-dash check; after argument-form checks and before dispatch: `load_home_profiles(~/.goga/profiles)` (strict, pre-docker); bundle handed to both launchers.
- **`run_pipeline_container(…, profile, …, home_profiles=None)`** (CHANGED) — `run_pipeline_container.py` — DELETE `_resolve_workflow_log_name` and its host-side print (the feedback line prints in-container); env-file gains three engine lines under the engine-skip rule: `GOGA_PROFILE` (ambient, non-empty only), `GOGA_HOME_PROFILES` (bundle non-empty only), `GOGA_WORKFLOW` = the effective workflow name of the run decision (never under `--no-workflow`; explicit `-w` or basename auto-match file existence with the same silent containment guard; no line when the auto-match file is absent); run argv: `run NAME --port P [-w W] [--no-workflow] [--profile P] [-s N]… [--parallel N]`.
- **`run_pipeline_info_container(…, profile, …, home_profiles=None)`** (CHANGED) — `run_pipeline_info_container.py` — env-file ONLY when there is cargo (non-empty ambient `GOGA_PROFILE` or non-empty bundle), carrying exactly the two profile lines (never `GOGA_WORKFLOW`); without cargo the launch keeps the minimal read-only shape; card argv gains `--profile P` when set.

**Cell `goga/ralphex`** — annotation-only change (already materialized): the `env` parameter of `run_ralphex` is no longer the carriage for build task env layers; the launcher contract (signature, flags, exit codes, secrecy) is UNCHANGED — no code change required (verify only; align the module docstring if it still claims env carriage for build passes).

**`pyproject.toml`** — `jinja2>=3.1` already present in `[project.dependencies]` (verify only).

### Re-exports (facade obligations)

- `goga/pipeline/workflow/__init__.py` — nine new names: `ProfileSource`, `ResolvedProfile`, `LoadedWorkflow`, `WorkflowBuild`, `load_home_profiles`, `resolve_profile`, `render_workflow`, `resolve_activation`, `load_workflow` (added to imports and `__all__`).
- `goga/docker/__init__.py` — `encode_home_profiles`, `decode_home_profiles`.
- `goga/build/__init__.py` — `resolve_build_workflow`, `merge_workflow_build`, `write_role_env_wrappers`.
- `goga/pipeline/__init__.py` — `apply_stage_env_wrappers`.

### Usages Context

- **`convention`** (`.goga/usages/conventions.md`, project-level) — MANDATORY; the full rule set is extracted into the **Mandatory Rules** section below and applies to every task. Covers: engineering principles, development constraints, imports, data models, logging, code formatting, docstrings (incl. CLI command docstrings), dependencies, testing (tools, structure, naming, types, mocks, boundary tests), validation commands.
- **`jinja2`** (`.goga/usages/cooks/jinja2.md`, project-level) — the rendering engine contract for `render_workflow` / `load_workflow`: fixed environment flags (`trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, autoescape=False`), standard `Undefined` (never `StrictUndefined`), missing-key semantics, strict `TemplateSyntaxError` surfacing with file+line, whole-file-before-parse stance, anti-patterns.

### Imported Usages

- **`load-workflow`** from `goga/pipeline/workflow` (`goga/pipeline/workflow/.usages/load-workflow.md`) — the loading-chain contract (read → peek → activation → resolve → render → parse). Consumers: `goga/pipeline` (`resolve_workflow`), `goga/build` (`resolve_build_workflow`).
- **`profiles`** from `goga/pipeline/workflow` (`goga/pipeline/workflow/.usages/profiles.md`) — profile files, name grammar, activation precedence, home-bundle collection, failure strictness. Consumers: `goga/pipeline`, `goga/build`, `goga/commands/build`, `goga/commands/pipeline`.
- **`home-profiles-carriage`** from `goga/docker` (`goga/docker/.usages/home-profiles-carriage.md`) — one derived value, engine-skip rule, write-when-non-empty, decode-once, secrecy. Consumers: `goga/build`, `goga/pipeline`, `goga/commands/build`, `goga/commands/pipeline`.
- **`extra-env-carriage`**, **`resolve-wrapper-path`**, **`afm`**, **`ralphex`**, **`agent-wrappers`**, **`docker-builder`**, **`docker-runner`**, **`click`** (existing) — unchanged roles; `resolve-wrapper-path` is additionally consumed by the two new wrapper generators.

### Local Usages

All seven new/updated `.usages/` files were materialized by the apply-architecture
stage and verified consistent by the design review — **no creation or edit tasks**;
the final task verifies they still match the implemented surfaces:

- `goga/pipeline/workflow/.usages/profiles.md` (new) — profile files, grammar, precedence.
- `goga/pipeline/workflow/.usages/load-workflow.md` (new) — the chain steps.
- `goga/pipeline/workflow/.usages/parse-workflow.md` (updated) — rendered-text stance, six keys, build block.
- `goga/docker/.usages/home-profiles-carriage.md` (new) — host/container halves of the carriage.
- `goga/build/.usages/workflow-layering.md` (new) — the six-field block, layering order, feedback line.
- `goga/build/.usages/build-usage.md` (updated) — per-role wrapper ladder, flags.
- `goga/pipeline/.usages/per-stage-env.md` (new) — authoring, delivery, byte-identity, loop copies.
- `goga/commands/build/.usages/build.md`, `goga/commands/pipeline/.usages/pipeline-command.md` (updated) — flag matrices, engine lines.

### External Dependencies

- `jinja2>=3.1` (already in `pyproject.toml`) — rendering engine; the `jinja2` practice is the contract.
- `pyyaml>=6.0` — profile/workflow parsing (existing).
- `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0` — test/lint toolchain (`[project.optional-dependencies].test`).

### Entity Interaction and Data Flow (verified — transfer from the design)

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

Data flows: (1) home bundle host→container (`load_home_profiles` → `encode_home_profiles` → env-file `GOGA_HOME_PROFILES` → `decode_home_profiles` → `load_workflow(home_profiles=…)`); (2) activation `--profile` > `GOGA_PROFILE` > workflow `profile:` default (raw-text peek) folded by `resolve_activation`; (3) profile → `ResolvedProfile.data` = whole Jinja context → `render_workflow` → `parse_workflow`; (4) `WorkflowBuild` → `merge_workflow_build` → layered `BuildConfig` → `resolve_run_settings` → `write_role_env_wrappers` → `write_ralphex_config` wrapper pointers; (5) `WorkflowStage.env` → (compilation ignores it) → `apply_stage_env_wrappers` → sh closures in `/tmp/goga-stage-env/` → targeted `command:` patch; (6) `run_pipeline` exports `GOGA_PROFILE=<effective>` into the afm launch layer — nested `goga build` inherits it; the workflow travels via ambient `GOGA_WORKFLOW`.

Initialization order (bottom-up): workflow → docker carriage → config/project → ralphex (no code) → pipeline/hooks → build → pipeline → commands/build → commands/pipeline → facades (already ordered into the task sequence).

## Facts

- All nine touched CODEMANIFEST files are already materialized (git-modified working tree); `goga lint` reports 0 errors across 91 cells; `jinja2>=3.1` is already in `pyproject.toml`.
- `run_flow` (goga/afm) and `run_ralphex` (goga/ralphex) apply `env` as an overlay (`{**os.environ, **env}`); with no layer the subprocess inherits the environment — the inheritance claims rest on this (verified in source).
- `_WRAPPER_PATH_TEMPLATE` (`compile_flow.py:112`) is byte-identical to `resolve_wrapper_path` output; `_expand_loops` yields `NAME-1..NAME-N` (count 1 → base id).
- Current `_ENGINE_ENV_KEYS` (5 keys) exists in `run_pipeline.py`; the current `run_build_pass` carries a dead `env` parameter; `_compose_pass_env`/`_launch_pass` env plumbing and `_resolve_workflow_log_name` exist and must be deleted.
- `_STAGE_KEYS`/`_STAGE_FIELDS`/`WorkflowStage`/`WorkflowDocument`/`AdditionalReviewConfig` all lack the new fields today; `-p` currently sits on `--parallel` in the pipeline command.
- Tests mirror source under `tests/` with the established `test_<module>_contract.py` / `test_<module>_logic.py` pair convention; `tests/pipeline/workflow/`, `tests/docker/`, `tests/build/`, `tests/pipeline/`, `tests/pipeline/hooks/`, `tests/commands/build/`, `tests/commands/pipeline/`, `tests/integration/` all exist with `__init__.py`.
- Click command tests in this project run in-process via `click.testing.CliRunner` (the project's realization of "call the handler directly via Python call").
- Local commit policy: `.githooks/commit-msg` + `pre-push` reject any `Co-Authored-By` trailer (`make install-hooks` activates `core.hooksPath .githooks`).

## Gap Analysis

- **Missing contract entities**: 14 new modules (`profile_source.py`, `resolved_profile.py`, `loaded_workflow.py`, `workflow_build.py`, `load_home_profiles.py`, `resolve_profile.py`, `render_workflow.py`, `resolve_activation.py`, `load_workflow.py` in workflow; `home_profiles.py` in docker; `resolve_build_workflow.py`, `workflow_build.py`, `role_env_wrappers.py` in build; `stage_env_wrappers.py` in pipeline).
- **Missing facade exposure**: 9 workflow names, 2 docker names, 3 build names, 1 pipeline name (see Re-exports).
- **API mismatches to close**: `parse_workflow` path→text; `WorkflowStage`/`WorkflowDocument`/`AdditionalReviewConfig` new fields; `resolve_workflow` return/channels; `describe_pipeline`/`run_pipeline`/`pipeline_cli` `profile`; `write_ralphex_config` `additional_wrapper_path`; `run_build_pass` drops `env`; `build` command `-w/-p`; `pipeline` command `-p` migration; both container launchers gain `home_profiles`/`profile`.
- **Behavioral mismatches**: build 17-step orchestration (decode → resolve → feedback → layering → wrappers); launch-layer engine set widened to 9 keys; host workflow log line removed; dead env plumbing deleted.
- **Reusable code**: `extra_env.py` is the pattern for `home_profiles.py`; `resolve_wrapper_path` for wrapper targets; the existing contract/logic test pairs and conftest fixtures extend directly.
- **Test coverage gaps**: 47 named behavior scenarios from the design (18 positive / 16 negative / 13 edge, incl. the 4 review-added ones) plus per-task contract tests — none exist today.
- **Workspace visibility**: all locations are inside existing packages; no new cells; no `location` violations (every file at the CODEMANIFEST level).

---

## Mandatory Rules

Extracted from the project convention (`.goga/usages/conventions.md`, the
`convention` practice connected by every touched CODEMANIFEST). These rules are
**mandatory for every task**; precedence: contract first, package boundary and
facade obligations second, these conventions next, language idioms last.

### M1 — Coding style (strictly per `convention`)

1. Python 3.10+ only. All configuration through `pyproject.toml`. All code
   executes inside a virtualenv — create it if missing (`python -m venv .venv`;
   `pip install -e ".[test]"`).
2. Imports: **relative** for ALL intra-package references inside `goga`
   (`from .models import User`); **absolute** only for stdlib and third-party.
   Exception — tests: cross-directory references use absolute imports rooted at
   the `tests` package (`from tests.conftest import helper`).
3. Data models: stdlib `dataclasses` for all new models; `kw_only=True`
   mandatory; empty defaults for fields — `None` only for explicit absence;
   `frozen=True` where the contract demands immutability (`ResolvedProfile`,
   `LoadedWorkflow`, `AdditionalReviewConfig`).
4. Logging: stdlib `logging` (`logger = logging.getLogger(__name__)`);
   structured output with contextual metadata (`extra={...}`); lowercase concise
   messages, stable event names; levels per the convention semantics
   (DEBUG diagnostics / INFO lifecycle / WARNING recoverable / ERROR failed
   operation / CRITICAL operator intervention). **Never** log secrets,
   credentials, env values, payloads, or profile contents — facts and logs
   carry NAMES only.
5. Formatting: inside function/method bodies, logical blocks are separated by
   one blank line (initialization / conditions+loops / data preparation /
   processing / return).
6. Docstrings: Google style, mandatory for all public functions, methods, and
   classes; first line starts with a capital letter and ends with a period;
   `Args` / `Returns` / `Raises` sections as applicable. Click command callback
   docstrings are user-facing `--help` text: NO `Args`/`Returns`/`Raises`; keep
   the concise summary line; use the `\f` marker to hide developer notes.
7. Dependencies: every third-party library in `pyproject.toml` with a minimum
   version (test libraries under `[project.optional-dependencies].test`).
8. Engineering principles: readable explicit code, predictable straightforward
   control flow, stable abstractions, operational stability.

### M2 — Test writing (strictly per `convention`)

1. Tools: pytest (runner), ruff (lint + format of test code), pytest-cov
   (coverage). Tests run inside the venv.
2. Structure mirrors source directly: `goga/<pkg>/<module>.py` →
   `tests/<pkg>/test_<module>.py`; every test directory has `__init__.py`;
   local fixtures in `tests/<pkg>/conftest.py`, shared fixtures in
   `tests/conftest.py`; cross-package scenarios in
   `tests/integration/test_<scenario>.py`. The project's
   `test_<module>_contract.py` / `test_<module>_logic.py` pair convention
   extends to the new modules; changed modules gain additions to their
   existing test files.
3. Naming: files `test_<module>.py`; functions `test_<what>_<scenario>`
   (e.g. `test_complexity_with_empty_input`); grouping `class Test<Component>`;
   self-documenting names, minimal comments.
4. Types: unit tests for every public function/method/class (main scenario +
   typical data); edge cases for empty inputs (`None`, `""`, `[]`, `{}`),
   boundary values (`0`, negative, very large), invalid types, and expected
   exceptions via `pytest.raises`; integration tests only for cross-module /
   cross-package interaction. Contract tests (facade accessibility, API shape,
   signatures) are written FIRST and fail initially; logic tests after
   implementation. Integration tests do not replace contract/logic tests.
5. CLI commands are tested by invoking the handler in-process (the project
   pattern: `click.testing.CliRunner`); REST/handler-style entry points by
   direct Python call.
6. Boundary tests for thresholds/ranges/state transitions use
   `@pytest.mark.parametrize` with a table including each boundary.
7. Mocks only at external boundaries: pure logic without mocks; file I/O
   exclusively through the `tmp_path` fixture; subprocesses via `mock.patch`
   of the subprocess call; external dependencies via `mock.patch` at the
   import point.
8. Skip integration tests whose external dependencies are unavailable via
   `pytest.mark.skipif`.

### M3 — Linters and formatters across all development stages and local commits

1. `ruff check` (pyproject config: target `py310`, line-length 120, rule sets
   E/W/F/I/B/C4/SIM/PT/ARG/RUF/PTH/C90 max-complexity 10) must report **zero
   errors** at every development stage: after contract tests, after
   implementation, after logic tests, and before every local commit.
2. `ruff format` (double quotes, space indent, LF) is the formatter:
   `ruff format --check` must be clean (or `ruff format` applied) before every
   local commit. Lint/format cover BOTH `goga/` and `tests/` (tests carry the
   per-file ignores of pyproject).
3. Local commit gate: commit only after the scoped `pytest` run, `ruff check`,
   and `ruff format --check` all pass. Commit messages MUST NOT contain
   `Co-Authored-By` trailers (project policy enforced by `.githooks/commit-msg`
   and `.githooks/pre-push`; activate once with `make install-hooks`).
4. Cell-level gates after facade edits: `goga lint` (0 errors) and
   `goga schema` (import graph stays acyclic; workflow stays a leaf).

### M4 — REPL development cycle (workflow structuring)

Every coding task's implementation step (STEP 2) runs as a REPL cycle — the
convention practice "Organizing the REPL development cycle" applied to this
plan:

1. **Continuous interactive evaluation**: open an interactive Python session
   in the project venv (`python -i` or an equivalent) before writing final
   code; load the module under development plus the facade import
   (`from goga.pipeline.workflow import ...`) so the facade obligation is
   exercised continuously. Evaluate each new/changed entity against the
   contract immediately — signature, return types, behavior, exact error
   messages — as it is written, not after.
2. **Hot reloading**: after every edit, reload in the live session
   (`importlib.reload(module)`, or re-exec of the loader snippet) and
   re-evaluate; never restart from scratch to observe a change.
3. **Code migration to source files**: the REPL is the scratchpad; the
   declared `location` file is the deliverable. Once a snippet behaves
   correctly interactively, migrate it verbatim into the source file (no
   retyping drift), then re-verify in the REPL by importing through the
   package facade. Scratch files live under `/tmp/goga-repl/` — NEVER inside
   the repository, never committed.
4. REPL observations feed STEP 4: behaviors verified interactively (exact
   error strings, rendered shapes) become logic-test assertions.

---

## Tasks

> **Package ordering rule**: tasks execute in order; all coding tasks of a
> package complete before the next package starts (bottom-up dependency order:
> workflow → docker → config/project → pipeline/hooks → build → pipeline →
> commands/build → commands/pipeline → integration → final sweep).
>
> **Every coding task** follows the TDD workflow (STEP 0–8 below) structured
> around the REPL cycle (M4) with the convention linters (M3) enforced at every
> stage and at the local commit gate. **`CODEMANIFEST` files are read-only** —
> if implementation does not match the contract, fix the implementation.

### Task 1: Workflow-cell test workspace and toolchain (infrastructure)

Prepare the test infrastructure for the workflow package and verify the
toolchain. No production code yet. Creates the shared fixtures the design's
General Setup prescribes and the REPL scratch convention (`/tmp/goga-repl/`).

**Usages relevant to this task:**
- `convention`: venv execution, test structure (`tests/<pkg>/conftest.py`), fixture placement, `__init__.py` per test directory.

- [x] Ensure the virtualenv exists and is current: `python -m venv .venv` (if missing) and `pip install -e ".[test]"`; verify `python -c "import jinja2; print(jinja2.__version__)"` reports >= 3.1 inside the venv
- [x] Create `tests/pipeline/workflow/conftest.py` with the shared fixtures: `project_root(tmp_path, monkeypatch)` — chdir into a fake project carrying `.goga/profiles/` and `.goga/workflows/`; `home_bundle` — a sample `dict[str, dict[str, Any]]` (`{"mixa": {"worker": {"agent": "codex", "model": "sonnet"}}}}`); `render_env` — the fixed jinja2 `Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, autoescape=False)` per the `jinja2` practice
- [x] Verify fixture wiring: `pytest tests/pipeline/workflow/ -v` collects and passes the existing tests
- [x] Lint: `ruff check tests/pipeline/workflow/` and `ruff format --check tests/pipeline/workflow/` — zero errors
- [x] Local commit gate (M3): scoped pytest + ruff pass; `git add` the conftest; commit without `Co-Authored-By` trailers

### Task 2: Workflow data models (TDD coding)

Create the four profile/build data models in `goga/pipeline/workflow`:
`ProfileSource` (`profile_source.py`), `ResolvedProfile` (`resolved_profile.py`),
`LoadedWorkflow` (`loaded_workflow.py`), `WorkflowBuild` (`workflow_build.py`),
and export them from the cell facade. All models follow M1.3: stdlib
dataclasses, `kw_only=True`, frozen where the contract demands
(`ResolvedProfile`, `LoadedWorkflow` frozen; `WorkflowBuild` plain `kw_only`
with fixed field order agent, env, review_agent, review_env,
review_additional_agent, review_additional_env — all defaulting None).

**Usages relevant to this task:**
- `convention`: dataclass rules (`kw_only=True`, frozen models, empty defaults / None-for-absence), Google docstrings, relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (workflow data models) and restate: entities, locations, facade additions
- [x] **STEP 1 — CONTRACT TESTS**: write `tests/pipeline/workflow/test_profile_source_contract.py`, `test_resolved_profile_contract.py`, `test_loaded_workflow_contract.py`, `test_workflow_build_contract.py` — facade importability (`from goga.pipeline.workflow import ProfileSource, ResolvedProfile, LoadedWorkflow, WorkflowBuild`), constructor signatures (kw_only enforced), field names/order/defaults, `ProfileSource.PROJECT == "project"` / `ProfileSource.HOME == "home"`, frozen immutability (`pytest.raises(FrozenInstanceError)`) — expected to FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: in a venv REPL session, build each model, evaluate construction/frozenness/enum values interactively, hot-reload after each edit, migrate the verified code verbatim into `profile_source.py`, `resolved_profile.py`, `loaded_workflow.py`, `workflow_build.py`; add the four names to `goga/pipeline/workflow/__init__.py` imports and `__all__` (alphabetical)
- [x] **STEP 3 — INTERFACE VERIFICATION**: `pytest tests/pipeline/workflow/test_profile_source_contract.py tests/pipeline/workflow/test_resolved_profile_contract.py tests/pipeline/workflow/test_loaded_workflow_contract.py tests/pipeline/workflow/test_workflow_build_contract.py -v` — all pass
- [x] **STEP 4 — LOGIC TESTS**: add `test_*_logic.py` counterparts — defaults (all six `WorkflowBuild` fields None; a constructed model with every field None), `ResolvedProfile.data` carries an arbitrary mapping verbatim, `LoadedWorkflow.profile` accepts None and a `ResolvedProfile`, str-serialization of `ProfileSource` values
- [x] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/workflow/ -x` — fix implementation (not tests) until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: `python -c "from goga.pipeline.workflow import ProfileSource, ResolvedProfile, LoadedWorkflow, WorkflowBuild; print('facade ok')"`; confirm no CODEMANIFEST was touched (`git diff --stat` shows only code/tests)
- [x] **STEP 7 — LINT**: `ruff check goga/pipeline/workflow/ tests/pipeline/workflow/` + `ruff format --check goga/pipeline/workflow/ tests/pipeline/workflow/` — fix formatting, decompose if complexity exceeds limits
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; commit per the M3 gate (no `Co-Authored-By` trailers)
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 3: Activation, profile resolution, home bundle (TDD coding)

Implement the three resolution routines of `goga/pipeline/workflow`:
`resolve_activation` (`resolve_activation.py`), `resolve_profile`
(`resolve_profile.py`), `load_home_profiles` (`load_home_profiles.py`); export
all three from the facade. Algorithms (verbatim from the contracts):

`resolve_activation`: return the first non-empty of (cli_profile, env_profile,
workflow_default); whitespace-only = unset; all unset → None; pure.

`resolve_profile`: (1) grammar `^[A-Za-z0-9][A-Za-z0-9._-]*$` with `.`/`..`
forbidden — violation raises one strict error naming the profile; (2)
`<project_dir>/<name>.yml` exists → parse; invalid YAML or non-mapping root →
strict error naming the profile and the path (NO home fall-through) →
`ResolvedProfile(source=PROJECT)`; (3) else `name in home_profiles` →
`ResolvedProfile(source=HOME)` (no re-validation of bundle entries); (4) else
strict error naming the profile and BOTH lookup locations. No env reads, no
rendering.

`load_home_profiles`: (1) not `home_dir.is_dir()` → `{}`; (2) for each path in
`sorted(home_dir.glob("*.yml"))` (non-recursive): parse; invalid YAML or
non-mapping root → strict error naming the file path; `bundle[path.stem] =
data`; (3) return the bundle. No env reads; no name-grammar validation.

**Usages relevant to this task:**
- `profiles` (cell-local practice, already materialized): name grammar, project-wins precedence, strictness rules — read `goga/pipeline/workflow/.usages/profiles.md` before implementing.
- `convention`: `tmp_path` for all file trees, monkeypatch for cwd, `pytest.raises` negatives, error-message assertions in tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (activation/resolution/home bundle) and restate the three algorithms above
- [x] **STEP 1 — CONTRACT TESTS**: `tests/pipeline/workflow/test_resolve_activation_contract.py`, `test_resolve_profile_contract.py`, `test_load_home_profiles_contract.py` — facade importability, exact signatures — expected to FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-verify each routine against the grammar regex, the project-wins ordering, and the strict error wordings; exercise with `tmp_path` trees from the session; hot-reload per edit; migrate verified code into the three `location` files; add the three names to the facade
- [x] **STEP 3 — INTERFACE VERIFICATION**: run the three contract test files — all pass
- [x] **STEP 4 — LOGIC TESTS** (scenario names from the design; full traces in the design's Test Stack Trace): `test_resolve_activation_whitespace_and_precedence` (edge: `" ", "env", "default"` → `"env"`; `None, "", "  "` → None; `"cli", "env", "default"` → `"cli"`); `test_resolve_profile_project_wins_over_home` (positive); `test_resolve_profile_rejects_traversal_names` (negative: `../secrets`, `..`, `a/b`, `.hidden`); `test_resolve_profile_missing_everywhere_names_both_locations` (negative: message contains the name, the project dir, and the home wording); `test_resolve_profile_malformed_project_file_strict_names_profile_and_path` (negative: `- a` root and `: : :` YAML; the home bundle is never consulted); `test_load_home_profiles_collects_bundle_and_missing_dir_is_empty` (positive: flat `*.yml` only — nested subdir and `notes.txt` ignored; missing dir → `{}`); `test_load_home_profiles_malformed_file_strict_names_path` (negative: invalid YAML and non-mapping root each raise naming the path)
- [x] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/workflow/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade import of the three names; constraints hold (no `os.environ` reads in the three modules — assert via source inspection or mock)
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/pipeline/workflow/` and `tests/pipeline/workflow/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 4: Jinja rendering engine (TDD coding)

Implement `render_workflow` (`goga/pipeline/workflow/render_workflow.py`) and
export it. The engine contract comes verbatim from the `jinja2` practice:
`Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
autoescape=False)` with the standard `Undefined` (NEVER `StrictUndefined`);
`env.from_string(text).render(**profile_data)`; `TemplateSyntaxError` → one
strict error carrying `source_name`, `exc.lineno`, `exc.message`;
`UndefinedError` (nested access on a missing key) propagates unwrapped;
template-free input renders to itself; no YAML parsing, no file/env reads.

**Usages relevant to this task:**
- `jinja2` (`.goga/usages/cooks/jinja2.md`): read it FIRST — fixed flags, missing-key semantics, strict syntax surfacing, whole-file-before-parse stance, anti-patterns.
- `convention`: mock-free pure-logic tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (render_workflow) and restate the fixed flag set and error contract
- [x] **STEP 1 — CONTRACT TESTS**: `tests/pipeline/workflow/test_render_workflow_contract.py` — facade importability, signature `(text, profile_data, source_name="")` — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: in the REPL, render template-free text (identity), a `{{ var }}` interpolation, the `{% for k, v in worker.env.items() %}` iteration pattern from the practice; observe the trimmed output and the syntax-error exception fields interactively; hot-reload per edit; migrate into `render_workflow.py`; add the facade name
- [x] **STEP 3 — INTERFACE VERIFICATION**: run the contract tests — all pass
- [x] **STEP 4 — LOGIC TESTS**: `test_render_workflow_env_iteration_produces_valid_yaml` (positive: the iteration pattern with context `{"worker": {"env": {"A": "1", "B": "2"}}}` renders to text whose `yaml.safe_load` round-trips the env map exactly — the trim/lstrip flags are load-bearing); `test_render_workflow_syntax_error_names_file_and_line` (negative: `{% if %}` unclosed with `source_name="broken.yml"` — message contains the name, the line, the cause); identity render of template-free input; missing top-level key renders falsy/empty (standard `Undefined`); nested access on a missing key raises `UndefinedError` unwrapped
- [x] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/workflow/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade import; `autoescape=False` and standard `Undefined` asserted in the module (not `StrictUndefined`)
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over cell and tests
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 5: Parser delta and document models (TDD coding)

Change `parse_workflow` (`parse_workflow.py`) from `(workflow_path: Path)` to
`(text: str)`, extend `WorkflowStage` (`workflow_stage.py`) with `env` at
position 2 of the fixed order, and `WorkflowDocument` (`workflow_document.py`)
with `profile` and `build` (order: prompt, stages, extend, memory, profile,
build). The grammar delta (verbatim):

```
3. top-level: accept prompt|stages|extend|memory|profile|build
   - profile: non-str → "non-str value in workflow.profile"; empty/whitespace → None
   - build: non-mapping → "non-mapping build block in workflow"
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
   - any other key (incl. proxy, hosts) → unknown-key error with the valid-keys list
   - agent non-str → "non-str value in workflow.build[.review[.additional]].agent"
   - env non-mapping → "non-mapping env in …"; non-str value → "non-str value in ….env.KEY"
   - build WorkflowBuild(agent, env, review_agent, review_env,
     review_additional_agent, review_additional_env)
7. empty rule: prompt∧stages∧extend∧memory∧profile∧build all absent
   → "empty workflow — provide at least prompt, one stage, one extend
   entry, the memory block, or the build block"
```

The caller owns reading and rendering — no file reads in the parser. This
task lands BEFORE the loading chain (Task 6) so the chain can call
`parse_workflow(rendered)`. Because the signature changes, adapt the current
callers in the same task so the battery stays green: `goga/pipeline/
resolve_workflow.py:62` gets the interim mechanical adaptation
`parse_workflow(workflow_path.read_text())` (the final load-chain form
replaces it in Task 16), and the existing path-based test call sites
(`tests/pipeline/workflow/test_parse_workflow_*.py`,
`tests/pipeline/compiler/test_compile_flow_*.py`,
`tests/pipeline/test_describe_pipeline.py`,
`tests/integration/test_compile_flow_memory_integration.py`,
`tests/integration/test_compile_flow_workflow_integration.py`,
`tests/integration/test_workflow_entity.py`, and any other path passers)
switch to passing text. All `WorkflowDocument` construction sites are
keyword-based after M1.3 `kw_only` (verify `apply_skip_stages`, `overlay.py`,
tests).

**Usages relevant to this task:**
- `parse-workflow` (cell-local practice, updated): the rendered-text stance and grammar — read before implementing.
- `convention`: kw_only dataclasses; parametrized boundary tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (parser delta + models) and restate the grammar delta above
- [x] **STEP 1 — CONTRACT TESTS**: extend `tests/pipeline/workflow/test_parse_workflow_contract.py`, `test_workflow_stage_contract.py`, `test_workflow_document_contract.py` — new signature `(text: str)`, `WorkflowStage.env` field and order, `WorkflowDocument.profile`/`.build` fields and order — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive the parser over the design's input texts (build block alone, `profile: 42`, `env: [1,2]` under a stage, `env` in extend, `build: {}` alone, empty `{}`); observe exact error strings interactively and pin them; hot-reload per edit; migrate into the three `location` files; apply the interim `resolve_workflow.py` adaptation and the test call-site updates
- [x] **STEP 3 — INTERFACE VERIFICATION**: the three contract test files pass
- [x] **STEP 4 — LOGIC TESTS** (design scenarios): `test_parse_workflow_accepts_build_block_alone` (positive: all six `WorkflowBuild` fields populated; `document.profile is None`; no raise); `test_parse_workflow_rejects_env_in_extend_entry` (negative: message `env is forbidden in workflow.extend.extra`); `test_parse_workflow_rejects_proxy_in_build_block` (negative: unknown-key message with the valid-keys list); `test_parse_workflow_rejects_non_str_profile` (negative: `profile: 42`); `test_parse_workflow_rejects_bad_stage_env_shapes` (negative: `env: [1, 2]` and `env: {A: 1}` under a stage — both exact messages); `test_parse_workflow_empty_and_profile_only_workflows` (edge: `{}` and `profile: mixa` alone raise the empty-workflow error; `build: {}` alone is valid with all six fields None); `test_parse_workflow_stage_env_empty_map_equals_absence` (edge: `env: {}` → None)
- [x] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/workflow/ tests/pipeline/ tests/integration/ -x` — fix implementation until green (the adapted callers included)
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: `parse_workflow` stays exported and importable (pipeline annotations and tests reference it); no file I/O in the module; `goga lint` + `goga schema` still clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over cell and tests
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 6: The loading chain (TDD coding)

Implement `load_workflow` (`goga/pipeline/workflow/load_workflow.py`) and
export it. The chain (verbatim):

```
1. text = workflow_path.read_text()                → OSError propagates
2. default = peek_literal_profile(text)            → str | None
   - line-anchored scan: ^profile:\s*(value)$ at column 0
   - strip quotes / trailing comment; whitespace-only → None
   - value containing "{{" or "{%" → None (not a literal default)
3. name = resolve_activation(cli_profile, env_profile, default)
4. IF name is None: profile = None
   ELSE: profile = resolve_profile(name, Path.cwd()/".goga"/"profiles",
                                   home_profiles or {})
5. rendered = render_workflow(text, profile.data if profile else {},
                              source_name=workflow_path.name)
6. document = parse_workflow(rendered)
7. RETURN LoadedWorkflow(document, profile)
```

Rendering ALWAYS runs (empty context without activation); the peek works on
RAW text (a rendered-only default never activates); no env reads; no
path/existence guards (callers own them); inputs never mutated. The parser
already accepts rendered text (Task 5 landed first).

**Usages relevant to this task:**
- `load-workflow` (cell-local practice, materialized): the chain semantics — read `goga/pipeline/workflow/.usages/load-workflow.md` first.
- `jinja2`: through `render_workflow`.
- `convention`: `tmp_path` + monkeypatch.chdir fixtures from Task 1.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (load_workflow) and restate the 7-step chain
- [x] **STEP 1 — CONTRACT TESTS**: `tests/pipeline/workflow/test_load_workflow_contract.py` — facade importability, signature — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive the chain over a real tmp workflow file — peek variants (literal, quoted, trailing comment, whitespace, `{{ }}` templated), activation fold, project-profile render, plain-file identity; hot-reload per edit; migrate into `load_workflow.py`; add the facade name
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS** (design scenarios): `test_load_workflow_renders_with_active_project_profile` (positive: project profile `mixa.yml` = `worker: {agent: codex, model: sonnet}`; workflow `stages: {build: {agent: '{{ worker.agent }}', env: {MODEL: '{{ worker.model }}'}}}`; env channel `"mixa"`; assert `loaded.profile.name == "mixa"`, `source is PROJECT`, `stages["build"].agent == "codex"`, `env == {"MODEL": "sonnet"}`); `test_load_workflow_plain_file_renders_to_itself` (positive: `loaded.profile is None`; document equals the direct parse); `test_load_workflow_templated_default_does_not_participate` (edge: `profile: '{{ worker.profile }}'` → peek None → empty-context render; `loaded.profile is None`; no raise); `test_load_workflow_oserror_propagates_unchanged` (edge: missing path raises `FileNotFoundError`, NOT wrapped)
- [x] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/workflow/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade import; exactly zero `os.environ` reads in the module; no existence guard inside the chain
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over cell and tests
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 7: Workflow-cell integration tests (integration tests)

Cross-entity scenarios of the loading chain inside
`goga/pipeline/workflow` — the full render→parse pipeline over real files,
exercising the facade as a consumer would.

**Usages relevant to this task:**
- `convention`: integration tests verify cross-entity interaction; they do not replace the contract/logic pairs (M2.4).
- `jinja2`: the iteration and guard patterns from the practice.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If a test does not match the contract, fix the test — never the contract.**

- [x] Create `tests/pipeline/workflow/test_loading_chain_integration.py`
- [x] Scenario — profile-driven whole-file render: project profile + workflow using `{{ worker.agent }}` interpolation AND the `{% for %}` env-iteration pattern; `load_workflow` through the facade returns a document whose stage agent and env map carry the rendered values (pins data flows 2+3 end-to-end)
- [x] Scenario — activation through every channel: CLI channel, env channel, and the workflow literal default each activate the same profile; a quoted/commented default activates; channels beat the default
- [x] Scenario — template-free file equals the pre-feature parse: `LoadedWorkflow.document` equals the direct `parse_workflow(text)` result (identity invariant across the whole chain)
- [x] Run validation: `pytest tests/pipeline/workflow/ -v`; `ruff check` + `ruff format --check` over the test files; M3 commit gate

### Task 8: Home-profiles carriage (TDD coding)

Implement `encode_home_profiles` / `decode_home_profiles` in
`goga/docker/home_profiles.py` and export both from `goga/docker/__init__.py`.
Mirror `extra_env.py` for a nested mapping. Algorithms (verbatim):

```
encode: {} → ""
        json.dumps(profiles, separators=(",", ":"), sort_keys=True)
        → base64 (standard, padded) → str
decode: "" → {}
        base64 decode (validate=True) → json.loads
        failure / non-mapping root / a value that is not itself a mapping
        (inner maps may hold any YAML scalars — only the name keys and the
        nesting shape are checked) → ValueError("GOGA_HOME_PROFILES: invalid payload")
```

Deterministic; pure; the payload never appears in errors or logs; no env
reads; no application of the mapping.

**Usages relevant to this task:**
- `home-profiles-carriage` (cell-local practice, materialized): read `goga/docker/.usages/home-profiles-carriage.md` first — one derived value, write-when-non-empty, decode-once, secrecy.
- `convention`: pure-function tests without mocks; exact-message assertions.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (carriage encode/decode) and restate both algorithms
- [x] **STEP 1 — CONTRACT TESTS**: `tests/docker/test_home_profiles_contract.py` — facade importability (`from goga.docker import encode_home_profiles, decode_home_profiles`), signatures — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-verify roundtrip identity, determinism across calls, and every damaged-payload class (not-base64, base64-of-non-JSON, JSON list root, `{"a": "b"}` non-mapping value); hot-reload per edit; migrate into `home_profiles.py`; add the two facade names
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS** (design scenarios): `test_encode_home_profiles_empty_bundle_and_roundtrip` (edge/positive: `{}` → `""`; `decode(encode(b)) == b`; deterministic across calls; `decode_home_profiles("")` → `{}`); `test_decode_home_profiles_damaged_payload_clean_error` (negative: each damaged class raises `ValueError` containing `GOGA_HOME_PROFILES` and no payload content)
- [x] **STEP 5 — DEBUGGING**: `pytest tests/docker/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade import; purity (no FS/env access); `goga lint` + `goga schema` clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/docker/` and `tests/docker/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 9: Additional env layer of the external reviewer (TDD coding)

Extend `AdditionalReviewConfig` in `goga/config/project/config.py` with the
independent `env: dict[str, str]` layer (default empty dict; values verbatim;
never inherited from review env) and the loader pattern: optional string
mapping, default `{}`, non-string value → `ValueError`. Frozen dataclass
(`frozen=True, kw_only=True`) per the contract.

**Usages relevant to this task:**
- `convention`: frozen kw_only dataclasses; loader error style; parametrized invalid-type tests.
- `project-configuration` (existing cell practice): the loader pattern family.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (AdditionalReviewConfig.env) and restate the loader pattern
- [x] **STEP 1 — CONTRACT TESTS**: extend `tests/config/project/` tests — field presence on the facade type, kw_only construction with `env`, default `{}` — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-verify construction defaults, frozenness, and the loader behavior for present/absent/non-string values; hot-reload per edit; migrate into `config.py` (model + loader branch)
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS**: loader accepts a string mapping verbatim; absent key → `{}`; a non-string value (`env: "x"`, `env: [1]`) raises `ValueError`; the built config round-trips the values; the review-env independence is structural (no inheritance code path)
- [x] **STEP 5 — DEBUGGING**: `pytest tests/config/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade import `from goga.config import AdditionalReviewConfig`; `goga lint` + `goga schema` clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/config/` and `tests/config/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 10: Field-set-complete overlay merge (TDD coding)

Update `merge_workflow_overlay` in `goga/pipeline/hooks/overlay.py`: the
per-stage field merge covers the FULL declared field set of `WorkflowStage`
**including `env`** — an authored env is unbeatable exactly like every other
authored stage field; an unset env takes the value of the later contributing
tool that sets it. Never a named-subset copy (e.g. `_STAGE_FIELDS` gains
`env`; the merge iterates the field set). The rebuilt `WorkflowDocument`
carries `profile` and `build` verbatim.

**Usages relevant to this task:**
- `convention`: pure in-memory merge tests without mocks.
- `checkpoints` (existing hooks practice): contribution shape.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (overlay merge completeness) and restate the field-set-complete rule
- [x] **STEP 1 — CONTRACT TESTS**: extend `tests/pipeline/hooks/test_overlay.py` (the existing combined contract-and-logic file of the module) — the merged document carries `env`, `profile`, `build` — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive the authored-env-unbeatable and tool-fills-unset-slot cases (`{"A": "1"}` authored vs `{"A": "2", "B": "3"}` tool → merged `{"A": "1", "B": "3"}`); hot-reload per edit; migrate into `overlay.py`
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS**: authored env wins per key; unset env filled by the later tool; no authored entry → stage fully defined by tools; `profile`/`build` of the base survive the rebuild verbatim (the same `build` object); extend/prompt behavior unchanged
- [x] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/hooks/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: `goga lint` + `goga schema` clean; no new Imports (hooks cell stays workflow-only)
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/pipeline/hooks/` and `tests/pipeline/hooks/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 11: Build-side workflow selection and layering (TDD coding)

Implement `resolve_build_workflow` (`goga/build/resolve_build_workflow.py`)
and `merge_workflow_build` (`goga/build/workflow_build.py`); export both from
`goga/build/__init__.py`. Algorithms (verbatim):

`resolve_build_workflow`: (1) `workflow_cli` beats `workflow_env`; empty
strings count as unset; (2) neither → None (activation ignored entirely);
(3) `root = (Path.cwd()/".goga"/"workflows").resolve()`; escape → strict
`"invalid workflow name"`; missing file → strict error naming the workflow and
the directory; (4) `load_workflow(path, cli_profile, env_profile,
home_profiles)`.

`merge_workflow_build`: agent fields `block.X or config.X` per role (None
never overrides); env maps key-wise `{**config.env, **block.env}` (and the
review/additional counterparts); `config.review is None` + any review field
set → NEW `ReviewConfig` (set fields only) + NEW `AdditionalReviewConfig`
(`env` defaulting `{}`); every other field verbatim; NEW `BuildConfig` with
new nested models; inputs unmutated. The D2 guard (workflow `build:` block +
`config.build is None` → clean error, exit 1, no events) lives in `build()`
(Task 14) — `merge_workflow_build` always receives non-None.

**Usages relevant to this task:**
- `load-workflow` + `profiles` (imported from workflow cell): chain semantics and activation rules.
- `workflow-layering` (cell-local practice, materialized): the layering order and key-wise merge — read `goga/build/.usages/workflow-layering.md` first.
- `convention`: pure-function tests; tmp_path trees; monkeypatch.chdir.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (build workflow selection + layering) and restate both algorithms
- [x] **STEP 1 — CONTRACT TESTS**: `tests/build/test_resolve_build_workflow_contract.py`, `tests/build/test_workflow_build_merge_contract.py` — facade importability, signatures — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive CLI-vs-env folds, empty-string-unset, containment escape, key-wise merges, and the review-None construction; hot-reload per edit; migrate into the two `location` files; add the two facade names
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS** (design scenarios): `test_resolve_build_workflow_env_fallback_and_empty_strings` (edge: no CLI → env loads; CLI `"custom"` wins; CLI `""` → env; both empty → None) plus the strict negatives (escape → `"invalid workflow name"`; missing file names workflow and directory); `test_merge_workflow_build_keywise_env_and_agents` (positive: `merged.env == {"A": "1", "B": "over"}`, `review.env == {"C": "3", "D": "4"}`, agents preserved, additional verbatim, input config unmutated); `test_merge_workflow_build_constructs_review_when_none` (positive: new `ReviewConfig` + `AdditionalReviewConfig(agent="gemini", env={})`, other fields None/defaults)
- [x] **STEP 5 — DEBUGGING**: `pytest tests/build/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade imports; no env reads in either module; purity of the merge; `goga lint` + `goga schema` clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/build/` and `tests/build/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 12: Per-role env wrappers (TDD coding)

Implement `write_role_env_wrappers`
(`goga/build/role_env_wrappers.py`); export it. Algorithm (verbatim, D1/D7/D8):

```
1. base = Path("/tmp/goga-build-env"); base.mkdir(parents=True, exist_ok=True)
2. roles = {"tasks": settings.tasks.agent,
           "review": settings.review.agent,
           "additional": settings.review.additional.agent}
   FOR role, agent IN roles:
     IF agent is None: RAISE strict error naming the role
     wrapper = resolve_wrapper_path(agent)
     layer = {**role_env, **cli_entries} minus ENGINE_KEYS   # D1: five existing
                                                             # + GOGA_PROFILE,
                                                             # GOGA_WORKFLOW,
                                                             # GOGA_HOME_PROFILES,
                                                             # GOGA_EXTRA_ENV
     FOR key IN layer: IF not legal_env_name(key): RAISE strict error naming role
                       # raised BEFORE any script file is written (D8)
     script = "#!/bin/sh\n" + "".join(f"export {k}={shlex.quote(v)}\n")
              + f'exec {wrapper} "$@"\n'
     path = base / f"{role}.sh"; write; chmod 0o755
3. RETURN {"tasks": …, "review": …, "additional": …}
```

The wrapper base path must be patchable in tests (module constant); CLI wins
per key over the role env; engine keys dropped silently; layers independent
per role; env values never printed/logged; nothing under /workspace.

**Usages relevant to this task:**
- `resolve-wrapper-path` (imported from agents/wrapper): the exec-target resolution.
- `agent-wrappers` (existing): wrapper semantics.
- `convention`: `tmp_path`/monkeypatch for the temp dir; content assertions on generated files.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (role wrappers) and restate the algorithm and the D1 drop set
- [x] **STEP 1 — CONTRACT TESTS**: `tests/build/test_role_env_wrappers_contract.py` — facade importability, signature — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-generate the three closures with a patched base dir; inspect file contents, permissions, and the drop/override behavior interactively; hot-reload per edit; migrate into `role_env_wrappers.py`; add the facade name
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS** (design scenarios): `test_write_role_env_wrappers_generates_independent_closures` (positive: keys `{tasks, review, additional}`; tasks.sh contains `export T=CLI` and NOT the role value; review/additional export only their own layer; none contains `GOGA_PROFILE`; all files carry the exec bit; each ends with `exec <wrapper> "$@"`); `test_write_role_env_wrappers_rejects_illegal_env_key` (negative: tasks env `{"BAD=KEY": "1"}` → strict error naming `tasks`; NO wrapper file exists in the base directory — validation precedes any write); missing role agent → strict error naming the role before any pass launches
- [x] **STEP 5 — DEBUGGING**: `pytest tests/build/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade import; nothing written under `/workspace` (assert the base constant); no print/log of env values; `goga lint` + `goga schema` clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/build/` and `tests/build/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 13: Pass config, pass launch, settings pass-through (TDD coding)

Three changed entities of `goga/build`:

1. `write_ralphex_config` (`ralphex_config.py`) — new parameter
   `additional_wrapper_path: str | None = None`; `claude_command =
   wrapper_path`; engaged external review (full/short, additional wrapper
   given) sets `external_review_tool=custom` and `custom_review_script=
   additional_wrapper_path`; None → ralphex default; medium →
   `codex_enabled=false` (unchanged).
2. `run_build_pass` (`build_pass.py`) — the `env` parameter is REMOVED;
   delegate to `run_ralphex(plan, options, dry_run)` with no env layer — the
   subprocess inherits the container environment.
3. `resolve_run_settings` (`run_settings.py`) — no signature change; the
   annotation now documents `config` as the LAYERED value; `_resolve_additional`
   (construction site `run_settings.py:191`) passes the additional `env`
   verbatim (`env=block.env` or `{}`) — the design-review Medium fix.

Also verify (no code change expected): `goga/ralphex/run_ralphex.py` — the
launcher contract is unchanged; align its module docstring only if it still
claims env carriage for build passes.

**Usages relevant to this task:**
- `ralphex` (existing practice): the config-generation contract.
- `convention`: signature-change tests; mock.patch at the boundary.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (config/launch/settings) and restate the three deltas
- [x] **STEP 1 — CONTRACT TESTS**: extend `tests/build/test_contract.py` / `test_build_pass.py` — new `write_ralphex_config` signature, `run_build_pass` signature WITHOUT `env`, `RunSettings` additional env flow — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-verify the written `.ralphex/config` content for the three strategies with/without the additional wrapper; the `run_ralphex` call shape without env; the layered additional settings; hot-reload per edit; migrate into the three files
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS** (design scenario): `test_run_build_pass_launches_without_env_layer` (positive: `run_ralphex` monkeypatched — the recorded call has no `env` argument / `env is None`; `claude_command` in the written config is the wrapper path); plus: additional env flows into the resolved additional settings verbatim (empty when absent); engaged external review under full/short sets `custom_review_script` to the additional wrapper; medium keeps `codex_enabled=false`
- [x] **STEP 5 — DEBUGGING**: `pytest tests/build/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: facade still exports `build`; `run_ralphex` signature untouched; `goga lint` + `goga schema` clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/build/` and `tests/build/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 14: Build orchestration rework (TDD coding)

Rework `build` (`goga/build/build.py`) to the 17-step algorithm and
`main()` (`goga/build/__main__.py`) to the widened argparse; delete the dead
env plumbing. The delta against today:

- Step 1 decodes BOTH payloads (`decode_extra_env` AND
  `decode_home_profiles`) and reads `GOGA_WORKFLOW` + `GOGA_PROFILE` once
  each — exactly four environment reads on the whole path; a damaged
  payload/bundle is one clean error, nothing partially applied, no events, no
  pass launches.
- Step 2 `resolve_build_workflow(cli_options.workflow, GOGA_WORKFLOW,
  cli_options.profile, GOGA_PROFILE, bundle)`.
- Step 3 feedback line to stderr ONLY when a workflow is in effect AND the
  loaded profile is not None: `Build running with workflow "<w>" and profile
  "<p>"` — every other run prints no line (the build/pipeline asymmetry is
  contractual).
- Step 4 the D2 guard: workflow in effect + document carries a `build` block
  + `config.build is None` → one clean logged error naming the
  build-section requirement, exit 1, no events; otherwise
  `merge_workflow_build(config.build, document.build)` and the layered value
  feeds every downstream step (including the step-7 agent guard).
- Steps 12–13: per pass — `compose_pass_options`, `write_role_env_wrappers(
  settings, cli_entries)`, `write_ralphex_config(settings, str(tasks_wrapper),
  str(additional_wrapper))`, `run_build_pass(plan, settings, options,
  wrapper_path, dry_run)` — NO env layer anywhere.
- DELETE `_compose_pass_env` and the `env` forwarding in `_launch_pass`.
- `main()` argparse gains `-w/--workflow NAME` and `-p/--profile NAME`
  (forwarded into `cli_options`; `-p` is free — build has no parallel
  option).

**Usages relevant to this task:**
- `build-usage` (cell-local, updated): the wrapper ladder and flag surfaces.
- `workflow-layering`, `home-profiles-carriage`, `extra-env-carriage`, `ralphex`, `checkpoints`, `topic-paths`, `topic-statuses`: per-step contracts.
- `convention`: structured logging (names only); CLI docstring rules for argparse help texts.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (build orchestration) and restate the delta above
- [x] **STEP 1 — CONTRACT TESTS**: extend `tests/build/test_build.py` / `test_main.py` — `cli_options` carries `workflow`/`profile`; the argparse surface; the two-pass launch shape — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive the orchestration with mocked hooks/run_ralphex over: damaged bundle, workflow+profile, workflow-only, no workflow, build-block-without-config-section; observe exit codes, stderr lines, event counts interactively; hot-reload per edit; migrate into `build.py` / `__main__.py`
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS** (design scenarios): `test_build_damaged_bundle_one_clean_error_before_events` (negative: `GOGA_HOME_PROFILES="###"` → exit 1, no events, no pass launches, message names the variable); `test_build_workflow_build_block_without_config_build_section` (negative: `config.build=None` + loaded build block → exit 1 clean error naming the requirement, no AttributeError traceback, no events); `test_build_no_workflow_ignores_activation_entirely` (edge: `GOGA_PROFILE` set + valid bundle + no `-w`/`GOGA_WORKFLOW` → no profile loads, no feedback line, pre-feature behavior); `test_build_feedback_line_only_with_effective_profile` (edge: workflow without profile → NO line; with → `Build running with workflow "hard" and profile "mixa"` on stderr); argparse binds `-w`/`-p` into `cli_options`
- [x] **STEP 5 — DEBUGGING**: `pytest tests/build/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: the dead plumbing is gone (`_compose_pass_env` absent; no env kwarg on any pass launch); exactly four env reads (source inspection); `goga lint` + `goga schema` clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/build/` and `tests/build/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 15: Per-stage env wrappers (TDD coding)

Implement `apply_stage_env_wrappers`
(`goga/pipeline/stage_env_wrappers.py`); export it from
`goga/pipeline/__init__.py`. Algorithm (verbatim, D5/D6/D7):

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
     chmod 0o755        # file name: stage id when [A-Za-z0-9._-]+, else sanitized+digest
3. text = flow_path.read_text()
   FOR stage_id IN claims:
     patch the stage block: replace the command line value, or insert
     `command: <wrapper>` at the canonical position (before the first
     present canonical key after command; else before depends_on; else at
     block end)      # text-level targeted patch — NEVER a YAML round-trip (D5)
   flow_path.write_text(patched)                            # other bytes intact
4. RETURN [new FlowStage with fields["command"]=wrapper if claimed
          else the SAME input object]
```

Per-stage env exports values VERBATIM — no engine-key dropping (per-stage
layers sit above all global layers by contract).

**Usages relevant to this task:**
- `per-stage-env` (cell-local practice, materialized): authoring, delivery mechanism, byte-identity, loop copies — read `goga/pipeline/.usages/per-stage-env.md` first.
- `resolve-wrapper-path` (imported): exec-target resolution.
- `compile-flow` (existing): the serialized flow-file shape (`- id:` anchors, canonical key order, `_WRAPPER_PATH_TEMPLATE`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 — DECLARATION**: declare this task (per-stage wrappers) and restate the algorithm
- [x] **STEP 1 — CONTRACT TESTS**: `tests/pipeline/test_stage_env_wrappers_contract.py` — facade importability (`from goga.pipeline import apply_stage_env_wrappers`), signature — FAIL now
- [x] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: compile a real flow in the REPL (or handcraft the serialized form), apply the routine, and inspect: the patched bytes vs the original (only command lines), the wrapper contents, the insertion position; hot-reload per edit; migrate into `stage_env_wrappers.py`; add the facade name
- [x] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [x] **STEP 4 — LOGIC TESTS** (design scenarios): `test_apply_stage_env_wrappers_patches_only_command_fields` (positive: `result[build].fields["command"] == str(wrapper)`; `result[test] is stages[test]` — SAME object; the patched text differs from the original ONLY on build's command line; the wrapper contains `export E=1`); `test_apply_stage_env_wrappers_env_free_run_is_byte_identical` (positive: no claims → the returned list IS the input list; file mtime and content unchanged; no `/tmp/goga-stage-env` created); `test_apply_stage_env_wrappers_loop_copies_each_get_wrapper` (positive: `loop: 3` → ids `worker-1..3`, three distinct wrapper files each exporting `N=9`, three command fields patched); `test_apply_stage_env_wrappers_strict_error_without_any_agent` (negative: env stage, no stage agent, `global_agent=None` → strict error naming the stage; no wrapper written; flow-file untouched); `test_apply_stage_env_wrappers_inserts_command_when_absent` (edge: env without agent + `global_agent="claude"` → a `command:` line appears at the canonical position; every pre-existing line unchanged; the returned stage carries `command`)
- [x] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/ -x` — fix implementation until green
- [x] **STEP 6 — CONTRACT RE-VERIFICATION**: input list/objects never mutated; no YAML round-trip (text-level patch); facade import; `goga lint` + `goga schema` clean
- [x] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/pipeline/` and `tests/pipeline/`
- [x] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 16: Pipeline workflow resolution and skip rebuild (TDD coding)

Change `resolve_workflow` (`goga/pipeline/resolve_workflow.py`) to return
`LoadedWorkflow | None` and accept the three activation channels
(`cli_profile`, `env_profile`, `home_profiles`; `no_workflow` → None; the
basename fallback, containment guard, and silent miss stay; an existing file
loads through `load_workflow` and errors propagate). Change
`apply_skip_stages` (`goga/pipeline/apply_skip_stages.py`) so the rebuilt
`WorkflowDocument` carries `memory`, `profile`, and `build` verbatim (the
skip merge itself is unchanged).

**Usages relevant to this task:**
- `load-workflow` + `profiles` (imported from workflow cell): the chain and activation rules.
- `convention`: pure in-memory tests; tmp_path trees.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 — DECLARATION**: declare this task (resolve_workflow + apply_skip_stages) and restate both deltas
- [ ] **STEP 1 — CONTRACT TESTS**: extend `tests/pipeline/test_resolve_workflow.py` (the existing combined contract-and-logic file of the module) and `test_apply_skip_stages.py` — new signature/return type; the rebuilt document fields — FAIL now
- [ ] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive: silent miss vs explicit load errors vs `no_workflow`; the profile channels flowing into the chain; the skip rebuild preserving profile/build; hot-reload per edit; migrate into the two files
- [ ] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [ ] **STEP 4 — LOGIC TESTS**: resolve returns `LoadedWorkflow` with `.document` and `.profile`; `no_workflow` short-circuits before any load; the containment escape and missing file stay silent; a structural workflow error propagates. `test_apply_skip_stages_and_overlay_preserve_profile_and_build` (edge, the apply_skip half — the overlay half landed in Task 10): `apply_skip_stages(doc, ["build"])` returns a document with `profile == "mixa"` and the SAME `build` object; skip still wins per name; None workflow + non-empty skip builds the skip-only document (profile None, build None)
- [ ] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/ -x` — fix implementation until green
- [ ] **STEP 6 — CONTRACT RE-VERIFICATION**: facade exports unchanged names; `goga lint` + `goga schema` clean
- [ ] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/pipeline/` and `tests/pipeline/`
- [ ] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 17: Run coordination, card, and CLI (TDD coding)

Three changed entities of `goga/pipeline`:

1. `run_pipeline` (`run_pipeline.py`) — step 8: decode the bundle + read
   `GOGA_PROFILE` once → `resolve_workflow` (damaged bundle → clean error,
   return 1, no events, afm never launches); step 9: the stdout feedback line
   (`Pipeline running with workflow "<n>" and profile "<p>"` / without the
   profile part / no line without a workflow; `<n>` = resolved file stem);
   step 14 (new): `apply_stage_env_wrappers` over the compiled stages;
   step 19 (widened): engine drop set = the five existing +
   `GOGA_PROFILE, GOGA_WORKFLOW, GOGA_HOME_PROFILES, GOGA_EXTRA_ENV`, plus
   `GOGA_PROFILE=<effective>` exported when a profile resolved. Exactly four
   environment reads total.
2. `describe_pipeline` (`describe_pipeline.py`) — read `GOGA_PROFILE` +
   decode `GOGA_HOME_PROFILES` once; pass the channels into
   `resolve_workflow`; merge skips over `resolved.document`; no feedback
   line; NEVER `apply_stage_env_wrappers` (D3).
3. `pipeline_cli` (`cli.py`) — `--profile/-p NAME` on the run subparser,
   binding in both info and run modes, forwarded verbatim.

**Usages relevant to this task:**
- `run-pipeline`, `describe-pipeline`, `pipeline-cli` (cell-local practices, updated): the activation context, feedback line, wrapper patch, four env reads, engine-set drops, `-p` flag.
- `per-stage-env`, `extra-env-carriage`, `run-flow`, `afm`: per-step contracts.
- `convention`: monkeypatch for env vars; captured stdout/stderr assertions.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 — DECLARATION**: declare this task (run/card/cli) and restate the three deltas
- [ ] **STEP 1 — CONTRACT TESTS**: extend `tests/pipeline/test_run_pipeline_contract.py`, `test_describe_pipeline.py`, `test_pipeline_cli.py` — `profile` parameters, the CLI flag — FAIL now
- [ ] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive the launch-layer composition (monkeypatched `run_flow` capturing `env`), the feedback variants, and the CLI binding in both modes; hot-reload per edit; migrate into the three files
- [ ] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [ ] **STEP 4 — LOGIC TESTS** (design scenarios): `test_run_pipeline_launch_layer_exports_effective_profile` (positive: bundle + `GOGA_WORKFLOW="hard"` + workflow default `profile: mixa` + `pipeline.env` carrying `{"GOGA_PROFILE": "evil", "OTHER": "1"}` + `GOGA_EXTRA_ENV` `{"K": "v"}` → captured layer `{"OTHER": "1", "K": "v", "GOGA_PROFILE": "mixa"}`; stdout contains `Pipeline running with workflow "hard" and profile "mixa"`); `test_run_pipeline_damaged_bundle_no_events_no_launch` (negative: `GOGA_HOME_PROFILES="###"` → return 1, clean stderr, no emit_* calls, no `run_flow` call); `test_pipeline_cli_parses_profile_flag_both_modes` (positive: `-p mixa` and `--profile mixa` bind in info and run modes, forwarded verbatim); `test_describe_pipeline_applies_profile_channels` (edge: `{% if worker.hardening %}` extend guard — with `profile="mixa"` the card carries `harden`, without it not; no exception either path; no wrapper generation)
- [ ] **STEP 5 — DEBUGGING**: `pytest tests/pipeline/ -x` — fix implementation until green
- [ ] **STEP 6 — CONTRACT RE-VERIFICATION**: exactly four env reads in `run_pipeline` (source inspection); the card never generates wrappers; `goga lint` + `goga schema` clean
- [ ] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/pipeline/` and `tests/pipeline/`
- [ ] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 18: Build command host launcher (TDD coding)

Extend the Click command `build` (`goga/commands/build/build.py`): options
`-w/--workflow NAME` and `-p/--profile NAME` (reject values starting with
`-`; validate `-w` host-side for path containment + file existence under
`<cwd>/.goga/workflows/` — light early diagnostic, the file is never read);
`load_home_profiles(Path.home()/".goga"/"profiles")` BEFORE any docker
activity (malformed → one clean `ClickException`, no image refresh, no
launch); two env-file engine lines after `GOGA_EXTRA_ENV` under the
engine-skip rule (an explicit `-e` key keeps winning): `GOGA_PROFILE=
<ambient>` only when non-empty, `GOGA_HOME_PROFILES=<encoded bundle>` only
when the bundle is non-empty; `GOGA_WORKFLOW` NEVER written; argv forwarding
of both long flags only when set; no host feedback line.

**Usages relevant to this task:**
- `build` (cell-local usage, updated): flag rows, profile-carriage table, GOGA_WORKFLOW exclusion.
- `profiles` + `home-profiles-carriage` (imported): the host half of the bundle.
- `click` (existing): the Click option/exception conventions; CLI docstring rules (M1.6).
- `docker-builder` / `docker-runner` (imported, unchanged roles): the docker acquisition and launch mechanics stay untouched by this task — the runner is mocked in tests per `convention`; the new env-file lines and argv tokens ride the unchanged launch shape.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 — DECLARATION**: declare this task (build command) and restate the delta
- [ ] **STEP 1 — CONTRACT TESTS**: extend `tests/commands/build/test_build.py` — the two options exist with the right short/long forms and types — FAIL now
- [ ] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive via `CliRunner` (in-process, M2.5): home-bundle loading under a patched HOME, the env-file line composition, the engine-skip interplay with `-e`, the `-w` validation branches; hot-reload per edit; migrate into `build.py`
- [ ] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [ ] **STEP 4 — LOGIC TESTS** (design scenarios): `test_build_command_writes_profile_envfile_lines` (positive: home profile via patched HOME + `GOGA_PROFILE="ambient"` + `-e K=V` → env-file carries `K=V`, `GOGA_EXTRA_ENV=…`, `GOGA_PROFILE=ambient`, `GOGA_HOME_PROFILES=<payload>` in order; argv carries `--workflow hard --profile mixa`; `GOGA_WORKFLOW` not in the file; docker run called once); `test_build_command_rejects_leading_dash_values` (negative: `-w "-x"` / `-p "-x"` → clean error, exit 1, no docker invocation); malformed home profile → clean `ClickException` before any docker activity; `-w` pointing at a missing/escaping file → clean host-side diagnostic
- [ ] **STEP 5 — DEBUGGING**: `pytest tests/commands/build/ -x` — fix implementation until green
- [ ] **STEP 6 — CONTRACT RE-VERIFICATION**: the workflow file is never read host-side; `GOGA_WORKFLOW` never written; `goga lint` + `goga schema` clean
- [ ] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/commands/build/` and `tests/commands/build/`
- [ ] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 19: Pipeline command host launcher (TDD coding)

Extend the Click command `pipeline` (`goga/commands/pipeline/pipeline.py`):
`-p/--profile NAME` (the short alias MOVES from `--parallel`, which becomes
long-only; the Docker `-p port:host` token is a separate namespace); the
profile value joins the leading-dash check; after the argument-form checks
and before dispatch: `load_home_profiles(Path.home()/".goga"/"profiles")`
(strict, pre-docker); the bundle is handed to both launchers.

**Usages relevant to this task:**
- `pipeline-command` (cell-local usage, updated): the flag matrix, `-p` vs docker `-p`.
- `profiles` + `home-profiles-carriage` (imported): the host bundle half.
- `click` (existing): option conventions; CLI docstring rules.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 — DECLARATION**: declare this task (pipeline command) and restate the delta
- [ ] **STEP 1 — CONTRACT TESTS**: extend `tests/commands/pipeline/test_pipeline_command.py` / `test_pipeline_contract.py` — the option matrix (`-p` = profile; `--parallel` long-only) — FAIL now
- [ ] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive via `CliRunner`: the flag matrix, the pre-docker bundle load ordering (malformed bundle → clean error, no docker call), the bundle reaching both launchers; hot-reload per edit; migrate into `pipeline.py`
- [ ] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [ ] **STEP 4 — LOGIC TESTS**: `-p mixa` binds profile; `--parallel 4` still binds parallel; `-p 5000` is NOT consumed by profile (docker port namespace unaffected); malformed home profile → clean error before dispatch; both launchers receive the bundle
- [ ] **STEP 5 — DEBUGGING**: `pytest tests/commands/pipeline/ -x` — fix implementation until green
- [ ] **STEP 6 — CONTRACT RE-VERIFICATION**: `--parallel` reachable only in long form; `goga lint` + `goga schema` clean
- [ ] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/commands/pipeline/` and `tests/commands/pipeline/`
- [ ] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 20: Container launchers (TDD coding)

Change the two host launchers of `goga/commands/pipeline`:

1. `run_pipeline_container` (`run_pipeline_container.py`) — DELETE
   `_resolve_workflow_log_name` and its host-side workflow log print (the
   feedback line prints in-container); three env-file engine lines under the
   engine-skip rule: `GOGA_PROFILE` (ambient, non-empty only),
   `GOGA_HOME_PROFILES` (bundle non-empty only), `GOGA_WORKFLOW` = the
   effective workflow name of the run decision (never under `--no-workflow`;
   explicit `-w` (already validated) or the basename auto-match file
   existence — the same silent containment guard; no line when the auto-match
   file is absent); `--profile P` in the run argv.
2. `run_pipeline_info_container` (`run_pipeline_info_container.py`) —
   env-file ONLY when there is cargo (non-empty ambient `GOGA_PROFILE` or
   non-empty bundle), carrying exactly the two profile lines (never
   `GOGA_WORKFLOW`); without cargo the launch keeps the minimal read-only
   shape; card argv gains `--profile P` when set.

**Usages relevant to this task:**
- `pipeline-command` (updated): three engine lines, in-container workflow line, cargo-only info env-file.
- `home-profiles-carriage` (imported): write-when-non-empty, engine-skip.
- `docker-builder` / `docker-runner` (imported, unchanged roles): the docker acquisition and launch mechanics stay untouched by this task — the runner is mocked in tests per `convention`; the new env-file lines and argv tokens ride the unchanged launch shape.
- `convention`: mocked runner; env-file content assertions; monkeypatch for env/HOME.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 — DECLARATION**: declare this task (container launchers) and restate both deltas
- [ ] **STEP 1 — CONTRACT TESTS**: extend `tests/commands/pipeline/test_run_pipeline_container_contract.py` / `test_run_pipeline_info_container.py` — the `profile`/`home_profiles` parameters, argv shapes — FAIL now
- [ ] **STEP 2 — IMPLEMENTATION (REPL cycle, M4)**: REPL-drive the three-case workflow decision and the cargo cases with a mocked runner; inspect env-file contents and argv; hot-reload per edit; migrate into the two files
- [ ] **STEP 3 — INTERFACE VERIFICATION**: contract tests pass
- [ ] **STEP 4 — LOGIC TESTS** (design scenarios): `test_run_pipeline_container_envfile_workflow_decision_matrix` (positive: (a) explicit `workflow="deploy"` → line `GOGA_WORKFLOW=deploy` + `-w deploy` in argv; (b) no flag + auto-match file exists → line with the basename, no `-w`; (c) `no_workflow=True` → no line; stdout contains NO `Pipeline running with workflow` host line); `test_info_container_envfile_only_with_cargo` (positive: no cargo → no env-file in docker params; ambient `GOGA_PROFILE="mixa"` + empty bundle → env-file with exactly `GOGA_PROFILE=mixa`, never `GOGA_WORKFLOW`; card argv carries `--profile mixa` when set)
- [ ] **STEP 5 — DEBUGGING**: `pytest tests/commands/pipeline/ -x` — fix implementation until green
- [ ] **STEP 6 — CONTRACT RE-VERIFICATION**: `_resolve_workflow_log_name` gone; engine-skip rule honored (explicit `-e` wins); `goga lint` + `goga schema` clean
- [ ] **STEP 7 — LINT**: `ruff check` + `ruff format --check` over `goga/commands/pipeline/` and `tests/commands/pipeline/`
- [ ] **STEP 8 — COMPLETION + LOCAL COMMIT**: mark checkboxes; M3 commit gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 21: Cross-cell integration tests (integration tests)

End-to-end scenarios spanning cells, in `tests/integration/` — the headline
inheritance scenario and the cross-cell regression nets.

**Usages relevant to this task:**
- `convention`: `tests/integration/test_<scenario>.py`; mocked externals at the boundaries only (`run_flow`, `run_ralphex`, docker runner); `tmp_path` trees.
- `load-workflow`, `home-profiles-carriage`, `per-stage-env`, `workflow-layering` (imported practices): the composed semantics under test.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If a test does not match the contract, fix the test — never the contract.**

- [ ] Create `tests/integration/test_nested_build_inherits_workflow_and_profile.py`: `test_nested_build_inherits_workflow_and_profile` — capture the launch layer of `run_pipeline` via a mocked `run_flow` (profile "mixa", ambient `GOGA_WORKFLOW="hard"`, `GOGA_PROFILE` absent); then `resolve_build_workflow(None, "hard", None, "mixa", bundle)` with the same fixture data returns a `LoadedWorkflow` whose profile is "mixa" and whose workflow file is "hard" — the build side picks both channels up through the environment alone
- [ ] Add `tests/integration/test_card_run_profile_equivalence.py`: with the same flags the card and the run compose the same stage set (profile channels included; an env-declaring stage appears in the card as it composes in the run — D3)
- [ ] Add `tests/integration/test_env_free_regression.py`: a workflow without any per-stage env and a config without workflow build blocks produce byte-identical flow output vs the no-workflow path (the env-free regression net across compile + wrappers)
- [ ] Run validation: `pytest tests/integration/ -v`; `ruff check` + `ruff format --check` over the new files; M3 commit gate

### Task 22: Final sweep — facades, schema, full battery (infrastructure)

Verify the whole feature: facades, contract-level gates, the full test
battery, and the usage-file consistency check. No production code changes
expected — fix code (never contracts) where a check fails.

**Usages relevant to this task:**
- `convention`: the Validation Commands table (pytest / ruff / facade check).
- All imported usages of the touched cells: verify the materialized `.usages/` files still describe the implemented surfaces (Local Usages list above).

- [ ] Facade checks: `python -c "from goga.pipeline.workflow import ProfileSource, ResolvedProfile, LoadedWorkflow, WorkflowBuild, load_home_profiles, resolve_profile, render_workflow, resolve_activation, load_workflow"`, `python -c "from goga.docker import encode_home_profiles, decode_home_profiles"`, `python -c "from goga.build import resolve_build_workflow, merge_workflow_build, write_role_env_wrappers"`, `python -c "from goga.pipeline import apply_stage_env_wrappers"`
- [ ] Contract gates: `goga lint` (0 errors) and `goga schema` (workflow stays a leaf; no cycles)
- [ ] Full battery: `pytest tests/ -x` inside the venv — all green
- [ ] Lint/format over everything: `ruff check goga/ tests/` + `ruff format --check goga/ tests/` — zero findings
- [ ] Verify no CODEMANIFEST or `.usages/` file was modified by the implementation (`git status`); verify the materialized usage files match the implemented surfaces (spot-check `profiles.md`, `load-workflow.md`, `home-profiles-carriage.md`, `per-stage-env.md`, `workflow-layering.md` against the landed code)
- [ ] Final local commit per the M3 gate; the working tree is clean

---

## Validation Commands

All commands run in the project virtualenv (create if missing; Python 3.10+).

- `pytest tests/ -x`: Run all tests (the full battery)
- `pytest tests/<pkg>/test_<module>.py -v`: Run a specific test file (task-scoped verification)
- `ruff check goga/ tests/`: Lint check (zero errors required at every stage)
- `ruff format --check goga/ tests/`: Formatter check (or apply `ruff format`) before every local commit
- `python -c "from goga.pipeline.workflow import ProfileSource, ResolvedProfile, LoadedWorkflow, WorkflowBuild, load_home_profiles, resolve_profile, render_workflow, resolve_activation, load_workflow"`: Workflow facade accessibility
- `python -c "from goga.docker import encode_home_profiles, decode_home_profiles"`: Docker facade accessibility
- `python -c "from goga.build import resolve_build_workflow, merge_workflow_build, write_role_env_wrappers"`: Build facade accessibility
- `python -c "from goga.pipeline import apply_stage_env_wrappers"`: Pipeline facade accessibility
- `goga lint`: CODEMANIFEST consistency (0 errors across 91 cells)
- `goga schema`: Import graph (acyclic; workflow stays a leaf)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is accessible from its cell facade (`__all__`)
- [ ] Properties and methods match the declared API (signatures verbatim)
- [ ] Descriptions are reflected in behavior (algorithms, error messages, invariants)
- [ ] Contract dependencies are met (Imports resolve; workflow stays a leaf)
- [ ] Re-exports are accessible from the facades (M1 import rules hold)
- [ ] Every coding task followed the TDD workflow (STEP 0–8: contract tests → REPL-cycle implementation → verification → logic tests → debugging → re-verification → lint → commit)
- [ ] The REPL development cycle (M4) structured every implementation step: continuous interactive evaluation, hot reloading, verbatim migration to source files
- [ ] The convention linters/formatters (M3) passed at every stage and at every local commit; no commit carries a `Co-Authored-By` trailer
- [ ] The coding style (M1) and test rules (M2) extracted from `convention` were followed in every task
- [ ] All 47 design test scenarios plus the per-task contract tests and the Task 7/21 integration tests exist and pass
- [ ] No package boundary was expanded; no new cells were created
- [ ] `CODEMANIFEST` files and `.usages/` files were not modified by the implementation (contract is read-only)
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check`, `ruff format --check`, `goga lint`, `goga schema`, facade checks)
- [ ] Every Usages entry is exercised by at least one task (`convention`, `jinja2`, `load-workflow`, `profiles`, `home-profiles-carriage`, `per-stage-env`, `workflow-layering`, `resolve-wrapper-path`, plus the existing set)
