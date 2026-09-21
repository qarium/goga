# Plan: `add-hooks-to-build`

Result of compiling the reviewed design document
(`.goga/history/2026/add-hooks-to-build/design.md`, post-review 1155 lines) into
ralphex-executable tasks. All traces, algorithms, and test scenarios below are
transferred verbatim from the design document — they are verified knowledge.

---

## Purpose

Implement the materialized contracts for the build domain hooks: the two-part
build configuration model (`build` root + `build.review`), the new hooks zone
`goga/build/hooks` (13 types: run-event facts, read-only contexts, the
verdict-collecting gate, and the `BuildHooks` checkpoint surface), the stable
always-two-pass build cycle with five checkpoints in `goga/build/build()`, the
ralphex launcher flag table with the external-review surface, the additive
`build` action catalog records, and the breaking removals
(`--worktree`/`--skip-finalize`, `TaskExecutorConfig`/`ReviewExecutorConfig`,
`review_options.py`) with no compatibility paths.

After implementation the package provides: a structural two-part loader,
`resolve_run_settings` with CLI > config > default > omit precedence and
root→review→additional inheritance, `compose_pass_options` per stage, the gate
before the first pass, four soft notifications around the cycle, finalize
materialization, plan relocation returning `RelocationOutcome`, and the host
launcher forwarding only live keys.

Overall strategy: leaf cells first, exactly the dependency order of the design
(`goga/config/project` → `goga/hooks/catalog` → `goga/ralphex` →
`goga/build/hooks` → `goga/build` → `goga/commands/build` →
`goga/onboarding/generator`), each task following the TDD workflow. The most
important gaps between contract and code are listed under Gap Analysis.

## Context

### Contract Surface

#### Cell `goga/config/project` (files `config.py`, `loader.py`)

**Entity: `ReviewConfig(skip, agent, env, roles, base_ref, strategy, finalize, additional, session_timeout, idle_timeout, wait)`**
- Type: class — frozen dataclass (`frozen=True, kw_only=True`)
- Declared `location`: `config.py`
- Facade obligation: importable from `goga.config` (embedding in `goga/config/CODEMANIFEST`)
- Properties: `skip -> bool | None`, `agent -> str | None`, `env -> dict[str, str]`,
  `roles -> list[str] | None`, `base_ref -> str | None`, `strategy -> str | None`,
  `finalize -> str | None`, `additional -> AdditionalReviewConfig | None`,
  `session_timeout/idle_timeout/wait -> str | None`
- Semantic requirements: every field verbatim; unset is None (empty dict for env);
  no normalization, no whitelist — structural typing only; "inherit from the root"
  semantics belong to the consumer
- Annotation context: two-part stance in the header annotations (loader extracts
  known fields only; retired keys silently ignored)

**Entity: `AdditionalReviewConfig(agent, patience, max_iterations)`**
- Type: class — frozen dataclass (`frozen=True, kw_only=True`)
- Declared `location`: `config.py`
- Facade obligation: importable from `goga.config`
- Properties: `agent -> str | None` (None = consumer inherits `review.agent`),
  `patience -> int | None` (0 = disabled), `max_iterations -> int | None`
  (0 = ralphex auto)
- Semantic requirements: values verbatim; 0 is a meaningful value, not an unset marker

**Entity: `BuildConfig(agent, env, max_iterations, session_timeout, idle_timeout, wait, prompts_dir, agents_dir, proxy, hosts, review)`** (changed)
- Type: class — frozen dataclass (`frozen=True, kw_only=True`)
- Declared `location`: `config.py`
- Facade obligation: importable from `goga.config`
- Properties: root tasks-pass fields + `review -> ReviewConfig | None`
- Semantic requirements: all fields may be None; `env`/`hosts` default empty dicts;
  values verbatim, no inheritance applied here
- Deleted: fields `worktree`, `skip_finalize`, `codex_review`, `task_executor`, `review_executor`

**Routine: `load_project_config()`** (changed, algorithm steps 6–7 rewritten)
- Declared `location`: `loader.py`
- Facade obligation: importable from `goga.config`
- Behavior: two-part extraction per the verbatim trace in Task 1

#### Cell `goga/config` (facade, file `__init__.py`)

Re-export embeddings updated mechanically: `TaskExecutorConfig`/
`ReviewExecutorConfig` dropped; `ReviewConfig`/`AdditionalReviewConfig` embedded
alongside the existing names (`ProjectConfig`, `load_project_config`,
`BuildConfig`, `PipelineConfig`, `CodemanifestConfig`, `DepConfig`, `LintConfig`,
`HomeConfig`, `DockerArgsConfig`, `load_home_config`, `resolve_project_name`,
`TopicsConfig`).

#### Cell `goga/hooks/catalog` (file `catalog.py`)

**Routine: `declared_actions() -> actions: list[Action]`** (changed, additive)
- Five new records: `Action(domain="build", name="validate_build", error_class="hard")`,
  `Action("build", "build_started", "soft")`, `Action("build", "pass_started", "soft")`,
  `Action("build", "pass_completed", "soft")`, `Action("build", "build_completed", "soft")`
- Existing records untouched; deterministic order (domain, then name)

#### Cell `goga/ralphex` (file `run_ralphex.py`)

**Routine: `run_ralphex(plan, options, dry_run, env=None) -> exit_code: int`** (changed)
- Bool flags `tasks_only` (`--tasks-only`), `review` (`--review`), `external_only` (`-e`)
- Scalar flags gain `review_patience` (`--review-patience`) and
  `max_external_iterations` (`--max-external-iterations`); `base_ref` (`--base-ref`) stays
- `worktree`/`skip_finalize` removed from the table
- Zero-valued external-flags rule: `review_patience` 0 and
  `max_external_iterations` 0 ARE passed; other scalar keys keep the historical
  `not in (None, "", 0)` drop rule

#### Cell `goga/build/hooks` (NEW — files `facts.py`, `contexts.py`, `events.py`, `__init__.py`)

All zone types are `@dataclass(kw_only=True)`, non-frozen — mutability is closed
by the delivery proxy (`wrap_context`), following the `goga/pipeline/hooks`
precedent.

**Facts (`facts.py`):**
- `WorkIdentity(branch, slug=None, year=None)` — hosting decision made in the
  constructing operation; branch-only form has `slug`/`year` None
- `BuildMoment(plan, work, dry_run)` — the uniform envelope of every context
- `StageFacts(stage, agent, env, max_iterations, session_timeout, idle_timeout, wait, roles, base_ref, strategy, finalize, additional)` —
  resolved facts of one stage; `env` carries NAMES only (values never appear);
  review-only members None on the tasks part; pure facts
- `AdditionalFacts(agent, patience, max_iterations)` — delivered mirror of the
  external-review block
- `RelocationOutcome(moved, destination)` — relocation attempt outcome
- `Violation(tool, hook, reason)` — one collected veto; reason never a raw traceback
- `GateVerdict(violations)` with `approved -> bool` property — data only

**Contexts (`contexts.py`):**
- `BuildValidation(moment, tasks, review, skip)` with `veto(reason)` — the gate's
  per-tool view; private `_veto: str | None = None` buffer; whole replacement; no
  cancellation/deflection
- `BuildStarted(moment, tasks, review, skip)` — read-only
- `PassStarted(moment, facts)` — read-only
- `PassCompleted(moment, facts, exit_code)` — completion is a fact, not a success claim
- `BuildCompleted(moment, exit_code, stages, relocation, statuses)` — read-only;
  the artifact → history-status integration builds from these facts alone

**Checkpoint surface (`events.py`):**
- `BuildHooks()` with `validate_build(moment, tasks, review, skip) -> GateVerdict`,
  `emit_build_started(moment, tasks, review, skip)`,
  `emit_pass_started(moment, facts)`,
  `emit_pass_completed(moment, facts, exit_code)`,
  `emit_build_completed(moment, exit_code, stages, relocation, statuses)`
- Cheap construction; one lazily-built `HookRegistry` per run shared by all five
  checkpoints; contexts built from caller values (no repository reads)

**Facade (`__init__.py`):** re-exports all 13 types with `__all__` (alphabetical),
module docstring naming the zone (mirror `goga/pipeline/hooks/__init__.py`).

#### Cell `goga/build` (files `run_settings.py` NEW, `pass_options.py` NEW, `review_config.py`, `ralphex_runtime.py`, `ralphex_config.py`, `build_pass.py`, `plan_relocation.py`, `build.py`, `__main__.py`; DELETE `review_options.py`)

- `resolve_run_settings(config: BuildConfig, cli_options: dict) -> RunSettings` —
  pure resolution (algorithm in Task 8)
- `RunSettings(skip, tasks, review)` — frozen, kw_only
- `PassSettings(agent, env, max_iterations, session_timeout, idle_timeout, wait)` —
  frozen, kw_only
- `PassSettings::ReviewPassSettings(roles, base_ref, strategy, finalize, additional)` —
  concretization of `PassSettings`; frozen, kw_only; inherited agent/session-knob
  fields plus review-only members; `additional` is non-optional
- `compose_pass_options(settings, stage) -> dict[str, str | int | bool]` — pure
- `validate_review_config(settings: RunSettings)` — re-signatured from
  `(config, review)`; fixed check order (algorithm in Task 10)
- `sync_ralphex_defaults(config: BuildConfig, settings: RunSettings)` — reads roles
  and finalize from `RunSettings`; materializes `.ralphex/agents/finalize.txt`
- `write_ralphex_config(settings: RunSettings, wrapper_path: str)` — external-review
  surface + `finalize_enabled` (algorithm in Task 12)
- `run_build_pass(plan, settings, options, wrapper_path, dry_run, env)` — carries
  `RunSettings` instead of `BuildConfig`
- `move_completed_plan(plan, outcome, dry_run) -> RelocationOutcome`
- `build(plan, config, cli_options) -> exit_code` — the 12-step checkpoint cycle
  (trace in Task 15)
- `main()` — argparse surface per the trace in Task 16
- Deleted: `resolve_review_options`, `ReviewOptions` (file `review_options.py` —
  delete the file)

#### Cell `goga/commands/build` (file `build.py`, changed)

- Flag surface without `--worktree`/`--skip-finalize`
- Step-2.2 guard repointed to `config.build.agent` with message
  `"build.agent is required in .goga/config.yml to run 'goga build'"`
- Step 2.3 (two-pass × worktree guard) deleted
- Step 7 env assembly: `{**home.env, **git_env, **cli_env}` — the task env
  (`config.build.env`) is NOT written into the env-file
- `--review-patience` help addresses `build.review.additional.patience`;
  `--base-ref` help addresses `build.review.base_ref`

#### Cell `goga/onboarding/generator` (file `generator.py`, code change only)

- `FileGenerator.generate_goga_config` snapshot→YAML build mapping (code
  change in the private `_build_config_document`/`_executor_block` helpers):
  `data["build"] = build_block` (agent, env at the two-part root) instead of
  `{"task_executor": build_block}`; `_executor_block` docstring reworded
  (build root / pipeline content)

#### Cell `goga/commands/config` (manifest-only, no code change)

- `goga/commands/config/CODEMANIFEST` — dot-notation examples repointed to
  live keys (`build.agent`, `build.review.strategy`); fixed and user-approved
  during the design stage — already materialized in the workspace (code and
  tests carry no stale references); no implementation task needed

### Re-exports

- `goga/config` facade: embeds `ReviewConfig` and `AdditionalReviewConfig` (new);
  `TaskExecutorConfig`/`ReviewExecutorConfig` removed. Facade obligation: every
  embedded name importable from `goga.config`.
- `goga/build/hooks` facade: re-exports its own 13 contract types through
  `__all__` — `AdditionalFacts`, `BuildCompleted`, `BuildHooks`, `BuildMoment`,
  `BuildStarted`, `BuildValidation`, `GateVerdict`, `PassCompleted`, `PassStarted`,
  `RelocationOutcome`, `StageFacts`, `Violation`, `WorkIdentity`.
- `goga/build` facade: unchanged (`build` only — the manifest declares no new
  embeddings; `RunSettings`/`PassSettings` are consumed via
  `goga.build.run_settings` module imports per the design test).

### Usages Context

- `conventions` / `convention` (`.goga/usages/conventions.md`) — mandatory Python
  rules: relative intra-package imports, `dataclasses(kw_only=True)`, Google
  docstrings (CLI callbacks verbatim-help, no Args/Returns/Raises), stdlib
  logging with `extra`, blank-line blocking, tests mirror source under `tests/`,
  validation commands (`pytest tests/ -x`, `ruff check`, facade `python -c`).
  Relevant to every task.
- `ralphex` (`.goga/usages/cooks/ralphex.md`, updated during grooming) — the
  external ralphex binary contract: config keys
  `claude_command`/`claude_args`/`codex_enabled`/`external_review_tool`/
  `custom_review_script`/`finalize_enabled`/`preserve_anthropic_api_key`/
  `move_plan_on_completion`, flags per the option table, `{{agent:X}}`
  composition filtering, `agents/finalize.txt` materialization. Relevant to
  Tasks 3, 9, 11, 12, 13.
- `agent-wrappers` (`.goga/usages/cooks/agent-as-claude-wrappers.md`) —
  `/home/goga/bin/<agent>-as-claude.sh` naming for wrappers referenced by
  absolute path. Relevant to Tasks 10, 12, 15.
- `click` (`.goga/usages/cooks/click.md`) — host command surface. Relevant to
  Task 17.
- `yaml` (inline in `goga/config/project` and `goga/onboarding/generator`
  manifests) — `yaml.safe_load()` / `yaml.dump(default_flow_style=False)`.
  Relevant to Tasks 1, 18.

### Imported Usages

- `checkpoints` — from `goga/build/hooks`, source
  `goga/build/hooks/.usages/checkpoints.md` — how the build operation consumes
  the zone: one `BuildHooks` per run, facts resolved in the operation, gate
  before the first pass, emissions around the cycle. Relevant to Tasks 7, 15, 19.
- `topic-paths`, `topic-statuses` — from `goga/history`, source
  `goga/history/.usages/{topic-paths,topic-statuses}.md` — topic dir composition
  (slug grammar, year default) and status listing (`collect_topic_statuses`,
  `TopicRecord`). Relevant to Task 15.
- `resolve-wrapper-path` — from `goga/agents`, source
  `goga/agents/.usages/resolve-wrapper-path.md`. Relevant to Tasks 10, 12, 15.
- `run-ralphex` — from `goga/ralphex`, source
  `goga/ralphex/.usages/run-ralphex.md` (refreshed this stage: worktree removed,
  always-two-pass, external flags, zero rule). Relevant to Tasks 3, 13, 15.
- `ensure-in-docker` — from `goga/docker`. Relevant to Task 16.
- `build-usage` — from `goga/build`, source `goga/build/.usages/build-usage.md`
  (rewritten by apply-architecture: two-part settings, strategies, checkpoints,
  cli_options list). Relevant to Tasks 15, 16, 17.
- `project-configuration`, `home-configuration` — from `goga/config`. Relevant to
  Tasks 1, 17.
- `declaring-actions`, `per-tool-delivery`, `registering-hooks` — from
  `goga/hooks`, sources `goga/hooks/.usages/*.md` — the emission contract
  (`emit_hook_event` + `context_for`), the staged per-tool walk of the gate (with
  the recorded refinement: run to completion, collect vetoes, no contribution
  commit), and the hook signature (`context`/`self`) and failure handling behind
  every checkpoint. Relevant to Tasks 4–7.
- `docker-builder`, `docker-runner`, `docker-image-version`,
  `resolve-credential-mounts`, `runtime-paths`, `docker-auth-mounts` — from their
  cells, unchanged consumer contracts touched only via the Task 17 deltas.

### Local Usages

All usage-file artifacts were created/rewritten by `apply-architecture` or
updated during the design stage — they are current. No creation tasks needed;
each task that consumes them verifies currency by reading them.

- `goga/build/hooks/.usages/checkpoints.md` — consumer doc of the zone (status:
  current; consumed in Tasks 7, 15, 19)
- `goga/build/.usages/registering-hooks.md` — tool-author doc answering the three
  integration scenarios; its "missing agent returns before any checkpoint" claim
  is kept true by the Task 15 step-3.5 guard (status: current)
- `goga/build/.usages/build-usage.md` — rewritten to the two-pass + checkpoints
  contract (status: current)
- `goga/config/.usages/project-configuration.md` — build chapter rewritten to the
  two-part form incl. migration note (status: current)
- `goga/commands/build/.usages/build.md` — flag surface without the two removed
  flags; env layering note (status: current)
- `goga/ralphex/.usages/run-ralphex.md` — updated during the design stage
  (status: current)

### Entity Interaction and Data Flow (verbatim from the design)

Interaction diagram — the authoritative shape of the whole feature; Tasks 15,
17, and 19 implement and verify against it:

```
goga/commands/build (host CLI, click)
  │  guards: config.build present, config.build.agent set
  │  env-file: home.env < git identity < CLI -e (+proxy)   [NO build env]
  │  docker run ... python -m goga.build <plan> <cli_flags>
  ▼
goga/build  build()  ── in-container orchestrator ─────────────────────────────┐
  │ 0  git pre-check (uncommitted CODEMANIFEST → exit 1, no events)            │
  │ 1  resolve_run_settings(config.build, cli_options) → RunSettings           │
  │ 2  validate_review_config(settings)   ──► resolve_wrapper_path (goga/agents)│
  │ 3  sync_ralphex_defaults(config.build, settings)  [.ralphex/prompts|agents]│
  │ 4  facts: resolve_current_branch_name ── resolve_topic_dir ──► WorkIdentity│
  │           BuildMoment; StageFacts(tasks) + StageFacts(review)              │
  │ 5  BuildHooks.validate_build(...)  ──► GateVerdict                         │
  │        │ not approved → merged error, exit 1, nothing else fires           │
  │ 6  BuildHooks.emit_build_started(...)                                      │
  │ 7  tasks pass:  compose_pass_options(settings,"tasks")                     │
  │        emit_pass_started → run_build_pass → emit_pass_completed            │
  │ 8  review pass (tasks OK and not skip): compose_pass_options(,"review")    │
  │        wrapper = additional agent (short) else review agent                │
  │        emit_pass_started → run_build_pass → emit_pass_completed            │
  │ 9  move_completed_plan(...) ──► RelocationOutcome                          │
  │ 10 collect_topic_statuses(year) → statuses of work.slug                    │
  │ 11 BuildHooks.emit_build_completed(moment, exit_code, stages,              │
  │        relocation, statuses)                                               │
  └ 12 return exit code of the last executed pass                              │
                                                                               │
run_build_pass ──► write_ralphex_config(settings, wrapper) [.ralphex/config]   │
                 └► run_ralphex(plan, options, dry_run, env) (goga/ralphex)    │
                        └► subprocess: ralphex <plan> --config-dir .ralphex/   │
                                                                               │
goga/build/hooks  BuildHooks                                                   │
  ├ validate_build: staged per-tool walk over HookRegistry subscriptions       │
  │   (wrap_context + build_hook_arguments + registry.self_context),           │
  │   veto buffer per tool, Violation collection → GateVerdict                 │
  └ emit_*: emit_hook_event(registry, "build", <action>, context_for)          │
        all five addresses resolve via declared_actions() (goga/hooks/catalog) │
                                                                               │
goga/config  load_project_config → ProjectConfig(build=BuildConfig(            │
             review=ReviewConfig(additional=AdditionalReviewConfig)))          │
```

Data flows:

- **Flow A — configuration (once per run, in-container):**
  `load_project_config()` reads `.goga/config.yml` (the mounted `/workspace`)
  → structural two-part extraction → `BuildConfig` (root fields verbatim,
  `review: ReviewConfig | None`, `additional: AdditionalReviewConfig | None`)
  → `resolve_run_settings(config.build, cli_options)` applies CLI > config >
  default > omit and root→review→additional inheritance → frozen `RunSettings`.
- **Flow B — the gate (before any pass):**
  `build()` resolves `WorkIdentity` (git subprocess once, then
  `resolve_topic_dir` composition — no reads at the checkpoint) and both
  `StageFacts` (env presence as sorted names) → `BuildHooks.validate_build`
  walks the subscriptions of `build/validate_build` per tool → each tool gets a
  fresh `BuildValidation` view wrapped read-only → vetoes buffer per tool →
  `GateVerdict(violations)` returns to `build()` → not approved → one merged
  `logger.error` (tool, hook, reason per violation) → exit 1.
- **Flow C — a pass (twice per non-skipped run):**
  `compose_pass_options` (pure) → pass options dict →
  `run_build_pass(plan, settings, options, wrapper, dry_run, env)` →
  `write_ralphex_config` rewrites `.ralphex/config` (whole file, never merged)
  → `run_ralphex` maps options to flags and launches (or prints on dry-run) →
  exit code propagates unchanged → `emit_pass_completed` carries the actual
  code.
- **Flow D — completion (every return path of a started run):**
  `move_completed_plan` → `RelocationOutcome` → `collect_topic_statuses(year)`
  re-read AFTER the relocation attempt → statuses list (empty in the
  branch-only form) → `emit_build_completed(moment, exit_code, stages,
  relocation, statuses)` → soft emission; the exit code is already final.

Runtime initialization order inside one build run: config → settings →
validation → defaults sync → facts → `BuildHooks()` (cheap; the single
`HookRegistry` builds lazily on the first checkpoint and is shared by all
five) → passes → relocation → statuses → completion.

### External Dependencies

- The external `ralphex` binary — PATH-resolved, invoked only through
  `run_ralphex`; exit codes propagated; CLI flags per the `ralphex` practice table
- PyYAML (`yaml.safe_load` / `yaml.dump`) — stdlib-adjacent third-party, already
  in `pyproject.toml`
- click (host command), pytest + ruff + pytest-cov (test tooling), docker + git
  subprocesses (host launcher and manifest pre-check / branch resolution)
- The `goga/hooks` platform facade: `HookRegistry`, `wrap_context`,
  `build_hook_arguments`, `emit_hook_event`, `declared_actions` — stable, no
  changes in this plan

## Facts

- Python 3.10+; `pyproject.toml`; all commands run in the existing `.venv`
  virtualenv
- The workspace branch is `add-hooks-to-build`; `goga lint` after the design
  stage: **79 cells, 0 errors**; `goga schema` shows `goga/build/hooks` = 13
  types with a single dependency on `goga/hooks`
- `.goga/config.yml` of this repository is already migrated to the two-part form
  (dogfooding, landed by `apply-architecture`) — **do not touch it**
- The currently checked-in loader still enforces the retired model
  (`loader.py:598` raises `KeyError("build.task_executor is required in
  .goga/config.yml")`) — this is why any `goga` CLI subcommand that loads config
  currently fails against the migrated `.goga/config.yml` (e.g.
  `goga config language`); Task 1 closes this gap
- `goga/pipeline/hooks` is the structural precedent for the zone: incremental
  facade building ("each entity task added its module's import and `__all__`
  entry"), zone-style module docstrings, non-frozen zone dataclasses with
  mutability closed by `wrap_context`
- `goga/hooks/__init__.py` exports `HookRegistry`, `ToolHooks`,
  `build_hook_arguments`, `declared_actions`, `emit_hook_event`,
  `enumerate_tool_packages`, `wrap_context`
- `HookRegistry.build_once` is idempotent — one registry per run is built lazily
  on the first checkpoint and shared by all five; a broken tool-package import
  surfaces from `build_once` as `ImportError` (the platform's single fatal case)
- `tests/conftest.py` provides the `is_kw_only_dataclass` helper;
  `tests/hooks/conftest.py` provides `pin_package_environment` and
  `install_tool_package` (the platform boundary fixtures)
- The gate's bound-method write channel: `wrap_context` blocks attribute writes
  on the proxy but `veto()` mutates the target's buffer through the bound method —
  the same mechanism as `WorkflowAmendment._contribution`
- `goga/build/review_options.py` and `tests/build/test_review_options.py` exist
  and are deleted by this plan; no compatibility shims anywhere (major-version
  window)
- Retired CLI/config surface (`--worktree`, `--skip-finalize`, `worktree`,
  `skip_finalize`, `codex_review`, `task_executor`, `review_executor`) must be
  absent from `goga/` after implementation — expected remaining hits are only
  retirement/migration documentation in manifests/usages and the loader's
  ignore-everything stance
- The env layers rule: `settings.tasks.env or None` / `settings.review.env or None`
  (an empty dict means pure inheritance, never an empty overlay);
  `StageFacts.env` is `sorted(env)` — names only, deterministic
- SC1–SC10 of `task.md` map to tests as annotated in the design (SC1 catalog/
  facade/`goga hooks`; SC2 two-pass; SC3 veto; SC4 notification failure/exit
  codes; SC5 completion facts + env names; SC6 dry-run; SC7 inert-no-tools; SC8
  absence; SC9 the `registering-hooks` doc; SC10 registration re-read)

## Gap Analysis

Comparing the contract with the current workspace state:

- **Missing contract entities**:
  - `goga/build/hooks/` contains only `CODEMANIFEST` + `.usages/` — no
    `facts.py`, `contexts.py`, `events.py`, `__init__.py`
  - `goga/build/run_settings.py`, `goga/build/pass_options.py` do not exist
  - `ReviewConfig`, `AdditionalReviewConfig` do not exist
  - `tests/build/hooks/` does not exist; `tests/build/test_run_settings.py`,
    `tests/build/test_pass_options.py` do not exist
- **Stale model (must be rewritten)**:
  - `goga/config/project/config.py:5,57,85–98` — `TaskExecutorConfig`,
    `ReviewExecutorConfig`, old `BuildConfig(task_executor=..., review_executor=...)`
  - `goga/config/project/loader.py:46,464,507,587–604` — `_parse_task_executor`,
    `_parse_review_scoped_fields`, `_parse_review_executor`, old `_parse_build`;
    line 598 raises the retired `KeyError`
  - `goga/config/__init__.py:11–12,26–27` re-exports the retired names
- **Stale launcher**: `goga/ralphex/run_ralphex.py:12–14` — `_BOOL_FLAGS`
  carries `worktree`/`skip_finalize`; no `external_only`/`-e` bool flag and no
  `max_external_iterations` scalar (`review_patience`/`base_ref` already exist
  in `_SCALAR_FLAGS`); no zero-valued external rule
- **Stale orchestrator**: `goga/build/build.py:61,101,128` — `_resolve_options`,
  `_review_scoped_options`, the old single/dual-pass `build()`; no checkpoints,
  no facts, no relocation outcome
- **Stale CLI**: `goga/build/__main__.py:22–23,38–39` — `--worktree`/
  `--skip-finalize` flags and their `cli_options` keys
- **Stale host command**: `goga/commands/build/build.py:118–120,215,265–266`
  (`--worktree`/`--skip-finalize` options and `_build_cli_args` branches),
  `:317–342` (guard on `config.build.task_executor.agent`; step 2.3 two-pass ×
  worktree guard), and the task env written into the env-file
- **Stale generator**: `goga/onboarding/generator/generator.py:59–60,159–163` —
  emits `{"task_executor": build_block}`
- **Missing catalog records**: `goga/hooks/catalog/catalog.py` has no `build`
  domain records
- **Test coverage gaps**: every suite listed in the design's Source File Registry
  and the "Affected tests outside the main registry" addendum is stale against
  the retired schema (`tests/build/test_review_options.py` to delete;
  `tests/build/test_build_resolved_wrapper.py`, `tests/build/test_shipped_ralphex_assets.py`,
  `tests/config/test_integration.py`, `tests/commands/conftest.py`,
  `tests/commands/test_build.py`, three `tests/integration/test_*` files, four
  `tests/commands/build/test_build_*_integration.py` to rewrite/update)
- **Existing code that can be reused**: the git pre-check helpers in
  `goga/build/build.py` (`_unquote_git_path`, `_parse_porcelain_path`,
  `_find_uncommitted_manifests`), the `sync_ralphex_defaults` rewrite/roles
  filtering logic, `move_completed_plan`'s `Path.replace` core, the
  `run_ralphex` PATH-check/subprocess/dry-run skeleton, the host launcher's
  steps 1–19 minus the three deltas, and the platform fixtures in
  `tests/hooks/conftest.py`
- **Missing visibility**: none — all cells are tracked in git on this branch

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before
> starting the next. Within each coding task, contract tests are written first
> (TDD workflow). Only ONE task is executed per ralphex iteration. The order
> below follows the design's Entity Dependencies (leaves first; no cycles).
>
> **Instructions for the implementation agent** (from the design's Additional
> Instructions): read the practices before coding — `conventions`, `ralphex`,
> `agent-wrappers`, `checkpoints`, `registering-hooks` (goga/build),
> `per-tool-delivery`, `declaring-actions` (goga/hooks), `topic-paths`,
> `topic-statuses` (goga/history), `run-ralphex` (goga/ralphex),
> `resolve-wrapper-path` (goga/agents), `build-usage`,
> `project-configuration`. Keep every file's module docstring in the zone style
> of `goga/pipeline/hooks` (which zone it is, which entities live here). Google
> docstrings everywhere; CLI callback docstrings verbatim-help (no
> Args/Returns/Raises); relative intra-package imports only;
> `from __future__ import annotations` at the top of every touched module.
> Match the established code idioms: the gate walk mirrors
> `PipelineHooks.amend_workflow` with the recorded deviation (collect, never
> stop); the emissions mirror `emit_run_created`; the merged veto error mirrors
> the existing `logger.error(..., extra={...})` style of `build.py`. No
> compatibility shims anywhere (major-version window). `.goga/config.yml` is
> already migrated — do not touch it.

### Task 1: Two-part build configuration model, loader, and facade re-exports (TDD coding)

Rewrites `goga/config/project` to the two-part build model and updates the
`goga/config` facade in the same task (the facade change is mechanical and must
land together with the model — deleting `TaskExecutorConfig` while the facade
still imports it would break every consumer). Covers contract entities
`BuildConfig` (reshaped), `ReviewConfig`, `AdditionalReviewConfig` (new),
`load_project_config` (steps 6–7 rewritten) in `goga/config/project/CODEMANIFEST`,
and the embedding list of `goga/config/CODEMANIFEST`. Locations:
`goga/config/project/config.py`, `goga/config/project/loader.py`,
`goga/config/__init__.py`.

Structural validation only — semantic validation (roles whitelist,
env-requires-agent, strategy whitelist, patience range) belongs to the consumer
(Task 10). The loader extracts known fields only; unknown keys (incl. stale
`worktree`, `task_executor`, `codex_review`) are silently ignored.

**Usages relevant to this task:**
- `convention` (`goga/config/project`): frozen kw_only dataclasses, stdlib
  dataclasses (NOT pydantic), relative imports, Google docstrings
- `yaml` (inline): `yaml.safe_load()` via PyYAML
- `project-configuration` (`goga/config/.usages/project-configuration.md`): the
  two-part build chapter incl. the migration note — verify the loader matches it

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace — implement exactly:

```
1. Input: .goga/config.yml at the project root (cwd), read + yaml.safe_load.
2. Step: top mapping guard (unchanged), lang/image/dockerfile, pipeline, then
   build block: absent → build=None; non-mapping → ValueError.
3. Step: root extraction — agent (empty/whitespace→None, non-str→ValueError),
   env (str mapping, default {}), max_iterations (int; bool→ValueError),
   session_timeout/idle_timeout/wait (agent pattern), prompts_dir/agents_dir
   (optional str), proxy (optional str), hosts (str mapping, default {});
   unknown keys (incl. stale worktree, task_executor, codex_review) silently
   ignored — verbatim extraction, no default merge.
4. Step: build.review sub-mapping: absent/null→None; non-mapping→ValueError;
   skip (bool|None), agent (pattern), env (pattern, default {}),
   roles (list[str]|None, empty passes verbatim), base_ref (agent pattern),
   strategy (empty/whitespace→None, non-str→ValueError, no whitelist),
   finalize (agent pattern — stored verbatim), additional (mapping: agent
   pattern, patience int with bool→ValueError, max_iterations same).
5. Output: ProjectConfig(build=BuildConfig(..., review=ReviewConfig(...,
   additional=AdditionalReviewConfig(...)))); codemanifest/lint/topics/tools/
   usages blocks extracted exactly as today.
```

Model rules: delete `TaskExecutorConfig`/`ReviewExecutorConfig`;
`BuildConfig` per the new signature (all fields kw_only, `env`/`hosts` default
empty dicts, everything else None-able); `ReviewConfig` and
`AdditionalReviewConfig` frozen kw_only. Loader: rewrite `_parse_build`;
delete `_parse_task_executor` (loader.py:46), `_parse_review_scoped_fields`
(loader.py:464), `_parse_review_executor` (loader.py:507); the
`KeyError("build.task_executor is required")` at loader.py:598 disappears
(`build.agent` is optional). Error messages use the new key names
(`build.agent must be a string…`, `build.review.strategy must be a string…`).
`goga/config/__init__.py`: add `ReviewConfig`, `AdditionalReviewConfig` to
imports and `__all__`; drop `TaskExecutorConfig`, `ReviewExecutorConfig`.

- [x] **Declaration**: Task 1 — two-part build configuration model, loader, and facade re-exports
- [x] **Contract tests**: in `tests/config/test_config.py` — `ReviewConfig` and `AdditionalReviewConfig` importable from `goga.config` and `goga.config.project`; both pass `is_kw_only_dataclass` (fixture from `tests/conftest.py`) and are frozen; `BuildConfig` exposes exactly the new field set (`review` present; `task_executor`/`worktree`/`review_executor` absent); in `tests/config/test_loader.py` — `load_project_config` still importable from `goga.config` (expected to fail at this stage)
- [x] **Code**: rewrite `goga/config/project/config.py` — delete `TaskExecutorConfig`/`ReviewExecutorConfig`, reshape `BuildConfig`, add `ReviewConfig`/`AdditionalReviewConfig` (frozen, kw_only, Google docstrings, `from __future__ import annotations`)
- [x] **Code**: rewrite `goga/config/project/loader.py` — `_parse_build` two-part extraction per the trace; delete the three retired parse helpers; new-key error messages; unknown keys ignored
- [x] **Code**: update `goga/config/__init__.py` — embed `ReviewConfig`/`AdditionalReviewConfig`, drop the retired names
- [x] **Interface verification**: `pytest tests/config/test_config.py tests/config/test_loader.py -x -q` — contract tests pass
- [x] **Logic tests**: in `tests/config/test_loader.py` — `test_load_project_config_parses_two_part_build` (setup: tmp `.goga/config.yml` with `language: python`, `build: {agent: claude, env: {A: "1"}, max_iterations: 7, session_timeout: 30m, review: {agent: codex, env: {B: "2"}, roles: [quality], base_ref: main, strategy: short, finalize: "do it", additional: {agent: cursor, patience: 2, max_iterations: 4}}}`; assert `config.build.agent == "claude"`, `config.build.env == {"A": "1"}`, `config.build.review.agent == "codex"`, `config.build.review.additional.patience == 2`, `not hasattr(config.build, "task_executor")`, `not hasattr(config.build, "worktree")`); `test_load_project_config_ignores_retired_keys` (config carrying `build: {worktree: true, skip_finalize: true, codex_review: false, task_executor: {agent: claude}, review_executor: {agent: codex}, agent: claude}` → no error; `config.build.agent == "claude"`; `config.build.review is None`); `test_load_project_config_rejects_malformed_review` (parametrize: `review: "x"`, `review: {skip: "yes"}`, `review: {roles: [1]}`, `review: {strategy: 5}`, `review: {additional: {patience: true}}`, `build: {max_iterations: true}`, `build: {agent: 7}` — each raises `ValueError` naming the key)
- [x] **Code**: rewrite `tests/config/test_integration.py` onto the two-part model (root fields plus `build.review`; drop or repoint the `worktree`/`skip_finalize`/`codex_review`/`task_executor`/`review_executor` assertions to the retired-key silence semantics already covered by the loader tests)
- [x] **Debugging**: `pytest tests/config/ -x -q` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade check `python -c "from goga.config import BuildConfig, ReviewConfig, AdditionalReviewConfig"` resolves; `python -c "from goga.config import TaskExecutorConfig"` raises `ImportError`
- [x] **Lint**: `ruff check goga/config tests/config` — fix formatting if necessary
- [x] **Completion**: mark all checkboxes of this task complete

### Task 2: Five build action catalog records (TDD coding)

Adds the five additive `build` records to the action catalog. Covers
`declared_actions()` in `goga/hooks/catalog/CODEMANIFEST` (location
`catalog.py`). The catalog is data only — maintained, not discovered; published
records are never rewritten; `declared_actions` sorts by domain then name.
Location: `goga/hooks/catalog/catalog.py`.

**Usages relevant to this task:**
- `convention`: docstring style, relative imports

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Append exactly (list order in the source is irrelevant — `declared_actions`
sorts by domain then name):

```
Action(domain="build", name="validate_build", error_class="hard"),
Action("build", "build_started", "soft"),
Action("build", "pass_started", "soft"),
Action("build", "pass_completed", "soft"),
Action("build", "build_completed", "soft")
```

Existing records (onboarding 2, pipeline 3, statuses 1, topics 7) stay
byte-identical.

- [x] **Declaration**: Task 2 — five build action catalog records
- [x] **Contract tests**: in `tests/hooks/catalog/test_catalog.py` — `declared_actions()` returns the five `(domain="build", name=…)` records with error classes hard/soft×4 (expected to fail at this stage)
- [x] **Code**: append the five records to the catalog list in `goga/hooks/catalog/catalog.py`
- [x] **Interface verification**: `pytest tests/hooks/catalog/test_catalog.py -x -q` — contract tests pass
- [x] **Logic tests**: `test_catalog_carries_the_five_build_records` — the five build records exist with error classes `validate_build` hard and the four notifications soft; pre-existing records byte-identical (compare against a frozen expected list); ordering deterministic (domain, then name)
- [x] **Debugging**: `pytest tests/hooks/ -x -q` — fix implementation code until all tests pass
- [x] **Contract re-verification**: `python -c "from goga.hooks import declared_actions; assert sum(1 for a in declared_actions() if a.domain == 'build') == 5"`
- [x] **Lint**: `ruff check goga/hooks tests/hooks` — fix formatting if necessary
- [x] **Completion**: mark all checkboxes of this task complete

### Task 3: Ralphex launcher flag table with external-review flags (TDD coding)

Updates the launcher's option→flag table. Covers `run_ralphex` in
`goga/ralphex/CODEMANIFEST` (location `run_ralphex.py`). This cell is a thin
launcher — no config generation, no option resolution, no wrapper resolution;
PATH check, subprocess, dry-run print, exit-code propagation stay as today.
Location: `goga/ralphex/run_ralphex.py`, tests `tests/ralphex/test_run_ralphex.py`.

**Usages relevant to this task:**
- `conventions`: docstrings, logging, test layout
- `ralphex` (`.goga/usages/cooks/ralphex.md`): the flag contract incl. the
  zero-valued external-flags rule
- `run-ralphex` (`goga/ralphex/.usages/run-ralphex.md`): refreshed this stage —
  worktree removed, always-two-pass wording, `external_only` (`-e`) and
  `max_external_iterations` documented, zero rule documented; the implementation
  must match it

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

New tables:

```
_BOOL_FLAGS = (("review", "--review"), ("tasks_only", "--tasks-only"), ("external_only", "-e"))
_SCALAR_FLAGS = (…, ("review_patience", "--review-patience"),
                 ("max_external_iterations", "--max-external-iterations"),
                 ("base_ref", "--base-ref"))
```

Scalar emission rule: `value is not None and value != ""` — with the
non-external keys additionally dropping 0 (`max_iterations`, `session_timeout`,
`idle_timeout`, `wait`, `base_ref`), i.e. keep the historical
`not in (None, "", 0)` for those and use the wider rule for exactly
`review_patience`/`max_external_iterations`. `worktree`/`skip_finalize` no
longer exist in the table.

- [x] **Declaration**: Task 3 — ralphex launcher flag table
- [x] **Contract tests**: in `tests/ralphex/test_run_ralphex.py` — bool mapping `review`→`--review`, `tasks_only`→`--tasks-only`, `external_only`→`-e` (True emits, False/absent omits); scalar mapping for the seven scalar keys; `worktree`/`skip_finalize` absent from any emitted command (expected to fail at this stage)
- [x] **Code**: replace `_BOOL_FLAGS` (run_ralphex.py:12–14) and extend `_SCALAR_FLAGS` (run_ralphex.py:18) per the tables above; implement the asymmetric zero rule
- [x] **Interface verification**: `pytest tests/ralphex/test_run_ralphex.py -x -q` — contract tests pass
- [x] **Logic tests**: `test_run_ralphex_external_flags_and_zero_rule` (patch `subprocess.call` recording argv; input `run_ralphex("p.md", {"external_only": True, "review_patience": 0, "max_external_iterations": 0, "max_iterations": 0, "base_ref": "main"}, False)`; assert
  `argv == ["ralphex", "p.md", "--config-dir", ".ralphex/", "-e", "--review-patience", "0", "--max-external-iterations", "0", "--base-ref", "main"]`
  and `--worktree`/`--skip-finalize` never appear for any input); `test_max_iterations_zero_dropped_by_launcher` (`run_ralphex("p.md", {"tasks_only": True, "max_iterations": 0}, dry_run=True)` capture stderr — printed command has no `--max-iterations`; contrast `review_patience: 0` prints `--review-patience 0`)
- [x] **Debugging**: `pytest tests/ralphex/ -x -q` — fix implementation code until all tests pass
- [x] **Contract re-verification**: dry-run still prints `shlex.join(cmd)` to stderr and never the env layer; PATH-missing → clean one-line stderr + exit 1
- [x] **Lint**: `ruff check goga/ralphex tests/ralphex` — fix formatting if necessary
- [x] **Completion**: mark all checkboxes of this task complete

### Task 4: Build hooks zone skeleton (infrastructure)

Creates the package structure of the new zone `goga/build/hooks` and its test
scaffolding. No contract entities land yet — this task creates the package
`__init__.py` with the zone-style module docstring (mirroring
`goga/pipeline/hooks/__init__.py`) and empty `__all__` (each later entity task
adds its module's import and `__all__` entry, the pipeline precedent), plus the
test package with the fixture re-export. Locations:
`goga/build/hooks/__init__.py`, `tests/build/hooks/__init__.py`,
`tests/build/hooks/conftest.py`.

**Usages relevant to this task:**
- `convention`: relative imports, package structure
- `registering-hooks`, `declaring-actions`, `per-tool-delivery` (imported from
  `goga/hooks/.usages/`): read before writing the zone docstring — the docstring
  names the zone's five moments and the hard gate with the domain-local
  never-stop deviation

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga/build/hooks/__init__.py` — module docstring naming the zone (the fact vocabulary, the gate, the checkpoint surface over the platform facade; the never-stop deviation), `from __future__ import annotations`, empty `__all__: list[str]`
- [x] Create `tests/build/hooks/__init__.py` (empty, per the each-test-directory-has-`__init__.py` rule)
- [x] Create `tests/build/hooks/conftest.py` re-exporting the platform boundary fixtures from `tests/hooks/conftest.py` (`pin_package_environment`, `install_tool_package`) — mirror `tests/pipeline/hooks/conftest.py`
- [x] Verify importability: `python -c "import goga.build.hooks"` (from the repo root, in `.venv`)
- [x] Lint: `ruff check goga/build tests/build` — fix formatting if necessary

### Task 5: Zone fact vocabulary — `facts.py` (TDD coding)

Implements the seven fact dataclasses. Covers `WorkIdentity`, `BuildMoment`,
`StageFacts`, `AdditionalFacts`, `RelocationOutcome`, `Violation`, `GateVerdict`
in `goga/build/hooks/CODEMANIFEST` (all `location: facts.py`). All are
`@dataclass(kw_only=True)`, NON-frozen — mutability is closed by the delivery
proxy (`wrap_context`), following the `goga/pipeline/hooks` precedent. Pure
facts: the constructing operation passes resolved values with inheritance
already applied; nothing is read or derived here. Locations:
`goga/build/hooks/facts.py`, `tests/build/hooks/test_facts.py`; extends the
facade.

**Usages relevant to this task:**
- `convention` (`goga/build/hooks`): kw_only dataclasses, relative imports,
  Google docstrings, blank-line blocking
- `registering-hooks` (from `goga/hooks`): the hook signature that consumes
  these facts — shapes the property docs

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Signatures (from the manifest, verbatim):

```
WorkIdentity(branch: str, slug: str | None = None, year: str | None = None)
BuildMoment(plan: str, work: WorkIdentity, dry_run: bool)
StageFacts(stage: str, agent: str | None, env: list[str], max_iterations: int | None,
           session_timeout: str | None, idle_timeout: str | None, wait: str | None,
           roles: list[str] | None, base_ref: str | None, strategy: str | None,
           finalize: str | None, additional: AdditionalFacts | None)
AdditionalFacts(agent: str | None, patience: int | None, max_iterations: int | None)
RelocationOutcome(moved: bool, destination: str | None)
Violation(tool: str, hook: str, reason: str)
GateVerdict(violations: list[Violation])          # property approved -> bool
```

- [ ] **Declaration**: Task 5 — zone fact vocabulary
- [ ] **Contract tests**: in `tests/build/hooks/test_facts.py` — each of the seven names importable from `goga.build.hooks`; each passes `is_kw_only_dataclass`; `GateVerdict.approved` exists as a property (expected to fail at this stage)
- [ ] **Code**: create `goga/build/hooks/facts.py` with the seven dataclasses (kw_only, non-frozen, zone-style module docstring, Google docstrings carrying the manifest property descriptions)
- [ ] **Code**: add the seven imports + `__all__` entries to `goga/build/hooks/__init__.py`
- [ ] **Interface verification**: `pytest tests/build/hooks/test_facts.py -x -q` — contract tests pass
- [ ] **Logic tests**: `GateVerdict([]).approved is True`; `GateVerdict([Violation("t", "h", "r")]).approved is False`; `WorkIdentity("feature-x")` branch-only form gives `slug is None and year is None`; `StageFacts` review-only members accept None on the tasks part; `AdditionalFacts` stores 0 verbatim (`patience=0` stays 0)
- [ ] **Debugging**: `pytest tests/build/hooks/ -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: the seven names importable from the facade `goga.build.hooks`
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 6: Zone read-only contexts — `contexts.py` (TDD coding)

Implements the five context dataclasses. Covers `BuildValidation` (with
`veto`), `BuildStarted`, `PassStarted`, `PassCompleted`, `BuildCompleted` in
`goga/build/hooks/CODEMANIFEST` (all `location: contexts.py`). Same dataclass
stance as Task 5 (kw_only, non-frozen). `BuildValidation` additionally carries
the private per-tool veto buffer `_veto: str | None = None` (not part of the
contract signature — an internal `init=False` field). Locations:
`goga/build/hooks/contexts.py`, `tests/build/hooks/test_contexts.py`; extends
the facade.

**Usages relevant to this task:**
- `convention`: data-model rules
- `registering-hooks` (from `goga/hooks`): the hook signature that receives
  `BuildValidation`

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

`veto(reason)` semantics (manifest, verbatim): the call buffers into the buffer
of this tool alone and changes nothing until the walk collects it; the
replacement is whole — a later call replaces the earlier reason; the view
records no hook identity (the walk attributes by observing the buffer change);
an empty or whitespace-only reason is stored as given. Constraints: no
cancellation, redirect, or deferral — a veto stops the run through the
collected verdict only.

- [ ] **Declaration**: Task 6 — zone read-only contexts
- [ ] **Contract tests**: in `tests/build/hooks/test_contexts.py` — the five names importable from `goga.build.hooks`; kw_only; `BuildValidation.veto` callable (expected to fail at this stage)
- [ ] **Code**: create `goga/build/hooks/contexts.py` — the five contexts + `veto()` writing `self._veto` (whole replacement) with the private `init=False` buffer field
- [ ] **Code**: add the five imports + `__all__` entries to the facade
- [ ] **Interface verification**: `pytest tests/build/hooks/test_contexts.py -x -q` — contract tests pass
- [ ] **Logic tests**: `veto("one")` then `veto("two")` → buffer holds exactly `"two"` (whole replacement); `veto("   ")` stores the whitespace verbatim; read-only fields (`moment`, `tasks`, `review`, `skip`, `facts`, `exit_code`, `stages`, `relocation`, `statuses`) carry the constructed values unchanged
- [ ] **Debugging**: `pytest tests/build/hooks/ -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: the twelve fact+context names importable from the facade
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 7: Checkpoint surface `BuildHooks` — `events.py` + facade completion (TDD coding)

Implements the gate and the four emissions — the hardest entity of the zone.
Covers `BuildHooks()` in `goga/build/hooks/CODEMANIFEST` (location
`events.py`): `validate_build`, `emit_build_started`, `emit_pass_started`,
`emit_pass_completed`, `emit_build_completed`. Finalizes the facade (13 names,
`__all__` alphabetical). The gate walk mirrors `PipelineHooks.amend_workflow`
(grouping, `wrap_context`, `build_hook_arguments`, `registry.self_context`)
with the recorded deviation: collect, never stop. The emissions mirror
`emit_run_created`. Locations: `goga/build/hooks/events.py`,
`goga/build/hooks/__init__.py`, `tests/build/hooks/test_events.py`.

**Usages relevant to this task:**
- `per-tool-delivery` (from `goga/hooks/.usages/per-tool-delivery.md`): the
  staged walk — loop skeleton, primitives, per-tool grouping — with the recorded
  refinement: run to completion, collect vetoes, no contribution commit
- `declaring-actions` (from `goga/hooks/.usages/declaring-actions.md`): the
  emission contract — `emit_hook_event(registry, domain, action, context_for)`
- `registering-hooks` (from `goga/hooks/.usages/registering-hooks.md`): the hook
  signature (`context`/`self`) and failure handling behind every checkpoint
- `checkpoints` (`goga/build/hooks/.usages/checkpoints.md`): the consumer-side
  integration order this surface serves

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace — the gate:

```
1. Input: moment: BuildMoment, tasks/review: StageFacts, skip: bool — values the
   operation already resolved.
2. Step: self._ensure_registry() — HookRegistry() + build_once() on first
   checkpoint; reused by every later checkpoint of the same BuildHooks instance.
3. Step: resolve domain="build", action="validate_build" against
   declared_actions() → unknown address → ValueError (defensive; the record
   exists by catalog — Task 2).
4. Step: group registry.subscriptions_for("build", "validate_build") per tool
   preserving enumeration order; per tool build a fresh
   BuildValidation(moment, tasks, review, skip) (private _veto buffer), wrap via
   wrap_context, call each hook with build_hook_arguments(hook, proxy,
   registry.self_context(tool)); snapshot view._veto before each call — a change
   after the call attributes the veto to that subscription's name (a later veto
   replaces the earlier attribution).
5. Step: a raising hook → record (tool, subscription.name, str(reason)) as the
   tool's single crash violation and STOP that tool's remaining hooks (exactly
   one Violation per tool); the walk continues with the next tool.
6. Step: a tool whose every hook returned and whose buffer is not None →
   Violation(tool, attributed_hook, buffered_reason); buffer None → silent
   approval.
7. Output: GateVerdict(violations) — approved is not violations; empty when the
   address has no subscriptions (inert with no tool packages).
```

Algorithm listing (gate):

```
1. registry = _ensure_registry()                  # once per run
2. record = find(declared_actions(), domain="build", name="validate_build")
   IF record is None: raise ValueError("unknown hook action: build.validate_build")
3. groups = {} ; for sub in registry.subscriptions_for("build","validate_build"):
       groups.setdefault(sub.tool, []).append(sub)
4. violations = []
5. FOR (tool, subs) in groups (enumeration order):
   a. view = BuildValidation(moment, tasks, review, skip)   # fresh buffer per tool
   b. attributed_hook, attributed_reason = None, None ; crash = None
   c. FOR sub in subs:
      - before = view._veto
      - TRY sub.hook(**build_hook_arguments(sub.hook,
                 wrap_context(view), registry.self_context(tool)))
        EXCEPT Exception as reason: crash = (sub.name, str(reason)) ; BREAK
      - IF view._veto != before:
            attributed_hook, attributed_reason = sub.name, view._veto
   d. IF crash:    violations.append(Violation(tool, crash[0], crash[1]))
      ELIF view._veto is not None:
                     violations.append(Violation(tool, attributed_hook, view._veto))
      ELSE: pass                                  # silent approval
6. RETURN GateVerdict(violations)                 # never stops between tools
```

Errors: unknown address → `ValueError` (defensive); a broken tool-package
import surfaces from `build_once` as `ImportError` (the platform's single fatal
case) — it escapes `build()` unhandled as documented (the pipeline precedent).
Edge cases: no subscriptions → empty verdict; empty/whitespace veto reason
stored and rendered verbatim; a later `veto()` replaces reason and attribution
whole; crash overrides the buffered veto.

Emissions — each builds its context and calls
`emit_hook_event(self._ensure_registry(), "build", <action>, context_for=lambda _tool: context)`
(the same instance for every tool — read-only contexts, no buffer); nothing
returns; a failing hook warns inside the platform (soft class); the run is
unaffected.

- [ ] **Declaration**: Task 7 — checkpoint surface BuildHooks
- [ ] **Contract tests**: in `tests/build/hooks/test_events.py` — `BuildHooks` importable from `goga.build.hooks`; the five methods exist with the declared signatures; construction performs no enumeration and no imports (expected to fail at this stage)
- [ ] **Code**: create `goga/build/hooks/events.py` — `BuildHooks` with `_ensure_registry()` (lazy, once per instance) and the five checkpoints per the algorithm above
- [ ] **Code**: finalize `goga/build/hooks/__init__.py` — all 13 types in `__all__`, alphabetical, zone docstring updated
- [ ] **Interface verification**: `pytest tests/build/hooks/test_events.py -x -q` — contract tests pass
- [ ] **Logic tests** (all in `tests/build/hooks/test_events.py`, using `pin_package_environment` + `install_tool_package`): `test_gate_collects_vetoes_without_early_stop` (two tools `goga_tool_a`/`goga_tool_b` subscribing `("build","validate_build","policy", hook)`; A vetoes `"no deploys on friday"`, B records `self.calls` and approves → `verdict.approved is False`; single violation naming tool+hook+reason; B's hook ran); `test_gate_attributes_veto_to_hook_and_replaces_whole` (one tool, hooks `first` vetoes "one", `second` vetoes "two" → exactly one `Violation` with `hook == "second"` and `reason == "two"`); `test_gate_crash_overrides_veto_and_walk_continues` (tool A: hook `broken` raises `RuntimeError("boom")` after hook `vetoer` buffered "blocked"; tool B approves → violations == `[Violation(A, "broken", "boom")]` only; B still ran; no exception escapes); `test_gate_empty_verdict_when_no_subscriptions` (`pin_package_environment({})` → `approved is True; violations == []`); `test_gate_veto_empty_reason_rendered_verbatim` (hook calls `context.veto("   ")` → `Violation.reason == "   "`; approved False); plus emission tests — each `emit_*` delegates to `emit_hook_event` with the right action name and the same context instance for every tool (one tool subscribing all four soft actions, recording `context` via `self`)
- [ ] **Debugging**: `pytest tests/build/hooks/ tests/hooks/ -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: facade check — `python -c "from goga.build.hooks import BuildHooks, BuildMoment, StageFacts, WorkIdentity, AdditionalFacts, RelocationOutcome, Violation, GateVerdict, BuildValidation, BuildStarted, PassStarted, PassCompleted, BuildCompleted"`; `goga schema` shows `goga/build/hooks` with exactly 13 types and a single dependency on `goga/hooks`
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting, apply decomposition if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 8: Run settings resolution — `run_settings.py` (TDD coding)

Implements the two-part settings resolver and its frozen value objects. Covers
`resolve_run_settings`, `RunSettings`, `PassSettings`,
`PassSettings::ReviewPassSettings` in `goga/build/CODEMANIFEST` (location
`run_settings.py` — new file). Pure — no I/O, no wrapper resolution, no
strategy validation. `ReviewPassSettings` is a concretization of `PassSettings`
(dataclass inheritance, frozen over frozen). Locations:
`goga/build/run_settings.py` (new), `tests/build/test_run_settings.py` (new).

**Usages relevant to this task:**
- `conventions`: frozen kw_only value objects, relative imports, test layout

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace (CLI precedence amendment from the design review is
included — the CLI layer was dead in the pre-review draft; steps 3–5 apply it):

```
1. Input: config: BuildConfig (review may be None), cli_options dict (keys
   skip_review, base_ref, review_patience, session_timeout, idle_timeout, wait,
   max_iterations — None when the flag was absent).
2. Step 0: config.review is None → every review field unset: skip=False, agent/
   session knobs inherit root, base_ref/roles/finalize None, additional =
   AdditionalReviewConfig(agent=<resolved review agent>, patience=None,
   max_iterations=None) — ReviewPassSettings.additional is non-optional, always
   constructed.
3. Step 1: skip = CLI skip_review when not None, else ReviewConfig.skip, else
   False (tri-state).
4. Step 2: strategy = ReviewConfig.strategy or "medium".
5. Step 3 (tasks): root agent/env verbatim; max_iterations and each session
   knob = the CLI value when given (not None), else the root value.
6. Step 4 (review): agent = review value when set else root; each of
   session_timeout/idle_timeout/wait = CLI value when given, else review value
   when set, else root; max_iterations NOT inherited (root-only); env = exactly
   review.env (never inherits); roles/base_ref/finalize verbatim.
7. Step 5 (additional): agent = additional.agent when set else resolved review
   agent; patience = CLI review_patience when given else the additional value
   verbatim; max_iterations verbatim (None when block absent).
8. Step 6: base_ref = CLI value when not None (strip; empty→None), else
   ReviewConfig.base_ref.
9. Output: frozen RunSettings(skip, tasks=PassSettings(...),
   review=ReviewPassSettings(roles, base_ref, strategy, finalize, additional,
   <inherited base fields>)).
```

Algorithm listing:

```
1. review = config.review ; absent → treat all review fields unset (step 0 semantics)
2. skip = cli.skip_review ?? review.skip ?? False
3. strategy = review.strategy or "medium"
4. knob(k) = cli.k if cli.k is not None else root.k   # max_iterations + session knobs
   tasks = PassSettings(agent=root.agent, env=root.env,
                        max_iterations=knob("max_iterations"),
                        session_timeout=knob("session_timeout"),
                        idle_timeout=knob("idle_timeout"), wait=knob("wait"))
5. review_agent = review.agent or root.agent
   review_knob(k) = cli.k if cli.k is not None else (review.k if set else root.k)
                                                          # session knobs only
   review_env = review.env                               # exactly; never root env
6. additional = AdditionalReviewConfig(
       agent=(review.additional.agent if review.additional else None) or review_agent,
       patience=(cli.review_patience if cli.review_patience is not None else
                 review.additional.patience if review.additional else None),
       max_iterations=review.additional.max_iterations if review.additional else None)
7. base_ref = strip(cli.base_ref) if cli.base_ref is not None else review.base_ref
8. RETURN RunSettings(skip, tasks,
       ReviewPassSettings(agent=review_agent, env=review_env, roles=review.roles,
           base_ref=base_ref, strategy=strategy, finalize=review.finalize,
           additional=additional, session_timeout=…, idle_timeout=…, wait=…))
```

- [ ] **Declaration**: Task 8 — run settings resolution
- [ ] **Contract tests**: in `tests/build/test_run_settings.py` — `resolve_run_settings`, `RunSettings`, `PassSettings`, `ReviewPassSettings` importable from `goga.build.run_settings`; the three dataclasses pass `is_kw_only_dataclass` and are frozen; `ReviewPassSettings` is a `PassSettings` subclass (expected to fail at this stage)
- [ ] **Code**: create `goga/build/run_settings.py` per the algorithm above (Google docstrings, `from __future__ import annotations`, relative imports)
- [ ] **Interface verification**: `pytest tests/build/test_run_settings.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_resolve_run_settings_full_inheritance` (setup: `BuildConfig(agent="claude", env={"A":"1"}, max_iterations=9, session_timeout="30m", idle_timeout="5m", wait="1m", review=ReviewConfig(skip=None, agent=None, env={}, roles=["quality"], base_ref="main", strategy=None, finalize=None, additional=AdditionalReviewConfig(agent=None, patience=3, max_iterations=None), session_timeout=None, idle_timeout=None, wait=None))`, `cli_options={}` → assert `settings.review.agent == "claude"`, `settings.review.strategy == "medium"`, `settings.review.additional.agent == "claude"`, `settings.review.additional.patience == 3`, `settings.review.env == {}`, `settings.review.base_ref == "main"`); `test_resolve_run_settings_cli_overrides_and_tri_state` (config with `review=ReviewConfig(skip=True, session_timeout="10m", …)`, `cli_options={"skip_review": False, "session_timeout": "99m"}` → `settings.skip is False`; `settings.review.session_timeout == "99m"`); `test_resolve_run_settings_review_absent` (`BuildConfig(agent="claude", env={}, max_iterations=5, …, review=None)`, `cli_options={}` → `settings.review.additional.agent == "claude"`, `settings.review.additional.patience is None`, `settings.review.roles is None`, `settings.skip is False`; repeat with `review=ReviewConfig(roles=[])` → `settings.review.roles == []` — the empty list travels verbatim, never coerced to None); `test_resolve_run_settings_base_ref_normalization` (`cli_options={"base_ref": "  release/1.3.0  "}`, config review `base_ref="main"` → `settings.review.base_ref == "release/1.3.0"`; repeat `cli_options={"base_ref": "   "}` → `base_ref == "main"` — empty CLI counts as unset)
- [ ] **Debugging**: `pytest tests/build/test_run_settings.py -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: `python -c "from goga.build.run_settings import RunSettings, PassSettings, ReviewPassSettings, resolve_run_settings"`; `from goga.config import BuildConfig, ReviewConfig, AdditionalReviewConfig` still resolves
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 9: Pass options composition — `pass_options.py` (TDD coding)

Implements the pure options composer. Covers `compose_pass_options` in
`goga/build/CODEMANIFEST` (location `pass_options.py` — new file). Keys of the
output must be a subset of the `run_ralphex` option table (Task 3). Locations:
`goga/build/pass_options.py` (new), `tests/build/test_pass_options.py` (new).

**Usages relevant to this task:**
- `conventions`: purity, test layout
- `ralphex`: the option-table key set the composition must respect

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace:

```
1. Input: settings: RunSettings, stage: str ("tasks" | "review").
2. Step (tasks): {"tasks_only": True} + each of session_timeout, idle_timeout,
   wait, max_iterations from settings.tasks when not None — no review-only
   keys, no agent (agent → wrapper), no env (env → layer).
3. Step (review): mode flag — {"external_only": True} when strategy == "short",
   else {"review": True}; plus session_timeout/idle_timeout/wait from the
   review part (inheritance already applied), base_ref when not None,
   review_patience from additional.patience when not None, 
   max_external_iterations from additional.max_iterations when not None —
   0-values kept for the two external flags.
4. Output: dict[str, str | int | bool] — unset knobs absent; exactly one
   pass-mode flag.
```

- [ ] **Declaration**: Task 9 — pass options composition
- [ ] **Contract tests**: in `tests/build/test_pass_options.py` — `compose_pass_options` importable from `goga.build.pass_options`; returns a plain dict (expected to fail at this stage)
- [ ] **Code**: create `goga/build/pass_options.py` per the trace above
- [ ] **Interface verification**: `pytest tests/build/test_pass_options.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_compose_pass_options_tasks` (settings with tasks knobs `session_timeout="30m"`, `max_iterations=9`, review part carrying `base_ref="main"`, `additional.patience=0` → `{"tasks_only": True, "session_timeout": "30m", "max_iterations": 9}` exactly; no `review`/`external_only`/`base_ref`/`review_patience`); `test_compose_pass_options_review_medium_and_short` (same settings, `strategy="medium"` → `options["review"] is True` and `"external_only" not in options`; `options["base_ref"] == "main"`; `options["review_patience"] == 0` — zero kept; `"max_external_iterations" in options` iff `additional.max_iterations is not None`; rebuild with `strategy="short"` → `options["external_only"] is True and "review" not in options`)
- [ ] **Debugging**: `pytest tests/build/test_pass_options.py -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: every emitted key maps 1:1 to a `run_ralphex` flag (cross-check against the Task 3 table)
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 10: Review config semantic validation — `review_config.py` re-signature (TDD coding)

Re-signatures the validator from `(config, review)` to `(settings: RunSettings)`
and adds the new checks. Covers `validate_review_config` in
`goga/build/CODEMANIFEST` (location `review_config.py`). Runs before any side
effect — before `.ralphex/` writes and before the first checkpoint. Locations:
`goga/build/review_config.py`, `tests/build/test_review_config.py`.

**Usages relevant to this task:**
- `conventions`: validation tier separation, test layout
- `resolve-wrapper-path` (from `goga/agents`): `resolve_wrapper_path(agent)`
- `agent-wrappers`: the wrapper naming the existence checks see

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace — fixed check order:

```
1. Input: settings: RunSettings.
2. Step 1: settings.skip → return (a skipped run validates nothing).
3. Step 2: each role of settings.review.roles against ROLE_WHITELIST
   (quality, implementation, testing, simplification, documentation) → first
   outsider raises ValueError naming it.
4. Step 3: settings.review.env non-empty and settings.review.agent is None →
   ValueError (env requires agent). Degenerate case: a None resolved agent at
   step 4 raises ValueError("no review agent resolved: set build.agent or
   build.review.agent") — resolve_wrapper_path(None) would produce a nonsense
   path; the clean error honors "the error message names the invalid value".
   (Unreachable through the host launcher — its step-2.2 guard requires
   build.agent — but reachable on direct in-container invocation.)
5. Step 4: wrapper = resolve_wrapper_path(settings.review.agent);
   not Path(wrapper).is_file() → ValueError naming agent and path.
6. Step 5: strategy engages the external review — "short" always; "full" when
   settings.review.additional.agent is set (always set after inheritance in
   practice) → resolve + existence-check the additional wrapper the same way.
7. Step 6: settings.review.strategy in {full, medium, short} else ValueError
   naming the value.
8. Output: None.
```

Constraint: do not validate the tasks agent wrapper here — only the
review/additional wrappers. Tests monkeypatch `resolve_wrapper_path` at its
import point (`goga.build.review_config.resolve_wrapper_path`) to a real
`tmp_path` file — the established pattern of `tests/build/test_review_config.py`.

- [ ] **Declaration**: Task 10 — review config semantic validation
- [ ] **Contract tests**: in `tests/build/test_review_config.py` — `validate_review_config(settings)` accepts exactly one positional argument of type `RunSettings` (expected to fail at this stage)
- [ ] **Code**: rewrite `goga/build/review_config.py` per the fixed order above (ROLE_WHITELIST constant; relative import of `resolve_wrapper_path` from `..agents`)
- [ ] **Interface verification**: `pytest tests/build/test_review_config.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_validate_review_config_accepts_clean_settings` (tmp wrapper file; monkeypatched `goga.build.review_config.resolve_wrapper_path` → `str(wrapper)`; `RunSettings(skip=False, review=ReviewPassSettings(agent="claude", env={"X":"1"}, roles=["quality"], strategy="medium", additional=AdditionalReviewConfig(agent="claude", patience=None, max_iterations=None), …)` → returns None, no exception); `test_validate_review_config_rejects_bad_fields` (clean baseline; wrapper monkeypatched to an existing tmp file; parametrize mutations: role `"auditor"`; review env non-empty + agent None; wrapper path to a missing file (`/home/goga/bin/ghost-as-claude.sh` via the patch); strategy `"fast"` → `pytest.raises(ValueError, match=…)` naming the role / the env-requires-agent problem / the agent+path / the strategy value; a `skip=True` variant of every mutation returns None); `test_validate_review_config_rejects_missing_additional_wrapper` (baseline `strategy="full"`, `additional.agent="codex"`; monkeypatch so the review agent resolves to an existing `tmp_path` file and the additional agent to a missing path → `pytest.raises(ValueError, match="ghost-as-claude.sh")` naming the additional agent and its path; a `skip=True` variant of the same settings returns None)
- [ ] **Debugging**: `pytest tests/build/test_review_config.py -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: check order observable via the negative tests (roles → env gate → review wrapper → additional wrapper → strategy)
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 11: Ralphex defaults sync with finalize materialization — `ralphex_runtime.py` (TDD coding)

Re-signatures the defaults sync to read roles and the finalize prompt from
`RunSettings` and materializes the finalize step file. Covers
`sync_ralphex_defaults` in `goga/build/CODEMANIFEST` (location
`ralphex_runtime.py`). The existing rewrite + roles-filtering logic is reused
unchanged; the delta is the signature and the new step 5. Locations:
`goga/build/ralphex_runtime.py`, `tests/build/test_ralphex_runtime.py`.

**Usages relevant to this task:**
- `conventions`: logging style, test layout
- `ralphex`: the finalize step is a ralphex review agent carrying the
  `finalize.txt` prompt; `{{agent:X}}` composition filtering

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace:

```
1. Input: config.build (custom prompts_dir/agents_dir), settings (roles,
   finalize).
2. Step: sources = custom dirs when set else vendored
   goga/assets/ralphex/{prompts,agents}; missing source → ValueError (as today).
3. Step: full rewrite of .ralphex/prompts/ and .ralphex/agents/ (clear + copy
   regular files).
4. Step: settings.review.roles non-empty list and vendored prompts → filter
   {{agent:X}} lines of review_first.txt/review_second.txt + counter rewrites
   (existing logic, unchanged); custom prompts_dir copied as-is.
5. Step (new): settings.review.finalize is not None → write the prompt string
   verbatim to .ralphex/agents/finalize.txt. Materialization applies regardless
   of a custom agents_dir — the file is goga's own step artifact, not part of
   the source tree. Unset → nothing written; the step stays at the ralphex
   default (off).
6. Output: the .ralphex/ prompts/agents tree on disk.
```

Checkpoint: byte-identity of the default composition (full role set / no roles)
— existing guard values kept; finalize materialization gated on the prompt
being set.

- [ ] **Declaration**: Task 11 — ralphex defaults sync with finalize
- [ ] **Contract tests**: in `tests/build/test_ralphex_runtime.py` — `sync_ralphex_defaults(config, settings)` two-argument signature over `(BuildConfig, RunSettings)` (expected to fail at this stage)
- [ ] **Code**: re-signature `goga/build/ralphex_runtime.py`; roles now read from `settings.review.roles`; add the finalize materialization step
- [ ] **Interface verification**: `pytest tests/build/test_ralphex_runtime.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_sync_ralphex_defaults_materializes_finalize` (tmp cwd; vendored sources exist — use the real vendored dirs, custom `prompts_dir`/`agents_dir` pointing at tmp copies when isolation is needed; `RunSettings` with `finalize="Final pass: merge the review."` → `(tmp_path / ".ralphex/agents/finalize.txt").read_text() == "Final pass: merge the review."`; unset-finalize variant → file absent); keep the existing roles-filtering tests green on the new signature (full default set → byte-identical prompts)
- [ ] **Debugging**: `pytest tests/build/test_ralphex_runtime.py -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: `.ralphex/config` untouched by this routine (owned by Task 12's routine)
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 12: Ralphex config generation with external surface — `ralphex_config.py` (TDD coding)

Re-signatures the config writer to `(settings, wrapper_path)` and derives the
external-review surface + finalize flag from the settings. Covers
`write_ralphex_config` in `goga/build/CODEMANIFEST` (location
`ralphex_config.py`). Whole-file rewrite — never merged. New import:
`resolve_wrapper_path` (from `..agents`) for the additional wrapper. Locations:
`goga/build/ralphex_config.py`, `tests/build/test_ralphex_config.py`.

**Usages relevant to this task:**
- `ralphex`: the `.ralphex/config` key layout incl.
  `codex_enabled`/`external_review_tool`/`custom_review_script`/`finalize_enabled`
- `resolve-wrapper-path` (from `goga/agents`), `agent-wrappers`: the additional
  wrapper path written as `custom_review_script`
- `conventions`: test layout

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace:

```
1. Input: settings: RunSettings, wrapper_path: str (the pass's executor wrapper).
2. Step: rewrite .ralphex/config whole with the fixed key block:
   claude_command = <wrapper_path>, claude_args = <fixed default>,
   preserve_anthropic_api_key = true, move_plan_on_completion = false.
3. Step: external surface (keys derived only from settings):
   strategy == "medium" → codex_enabled = false (explicitly disabled);
   full/short → codex_enabled stays unwritten (ralphex default enabled) and,
   when settings.review.additional.agent is not None → external_review_tool =
   custom and custom_review_script = resolve_wrapper_path(additional.agent);
   agent None (degenerate) → both stay unwritten (ralphex default codex).
4. Step: settings.review.finalize is not None → finalize_enabled = true; else
   unwritten (default false).
5. Output: .ralphex/config INI; called twice per two-pass run — same settings,
   only the wrapper differs.
```

INI lines joined with `\n` + trailing newline. Tasks-pass config carries the
review keys too — harmless: `--tasks-only` ignores every review-phase key
(practice note); keeps the routine a pure function of (settings, wrapper).

- [ ] **Declaration**: Task 12 — ralphex config generation with external surface
- [ ] **Contract tests**: in `tests/build/test_ralphex_config.py` — `write_ralphex_config(settings, wrapper_path)` signature (expected to fail at this stage)
- [ ] **Code**: rewrite `goga/build/ralphex_config.py` per the trace; add the `resolve_wrapper_path` import
- [ ] **Interface verification**: `pytest tests/build/test_ralphex_config.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_write_ralphex_config_strategies` (tmp cwd; three `RunSettings` variants — medium / full with additional agent "codex" / finalize set; wrapper path `"/home/goga/bin/claude-as-claude.sh"`; monkeypatch `goga.build.ralphex_config.resolve_wrapper_path` for the additional wrapper; assert
  `medium: "codex_enabled = false" in text; "external_review_tool" not in text`;
  `full+additional: "external_review_tool = custom" in text and f"custom_review_script = {additional_wrapper}" in text and "codex_enabled" not in text`;
  `finalize set: "finalize_enabled = true" in text; unset variant: not in text`;
  `always: "move_plan_on_completion = false", "preserve_anthropic_api_key = true", f"claude_command = {wrapper}"`)
- [ ] **Debugging**: `pytest tests/build/test_ralphex_config.py -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: key set matches the `ralphex` practice table exactly
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 13: Pass executor — `build_pass.py` re-signature (TDD coding)

Re-signatures the pass executor to carry `RunSettings`. Covers `run_build_pass`
in `goga/build/CODEMANIFEST` (location `build_pass.py`). Locations:
`goga/build/build_pass.py`, `tests/build/test_build_pass.py`.

**Usages relevant to this task:**
- `run-ralphex` (from `goga/ralphex`): the delegation contract
- `ralphex`: config written before launch
- `conventions`: test layout

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace:

```
1. Input: plan, settings, options, wrapper, dry_run, env (tasks: root env layer;
   review: review env layer; None/empty → pure inheritance).
2. Step: write_ralphex_config(settings, wrapper_path) → .ralphex/config of this
   pass.
3. Step: run_ralphex(plan, options, dry_run, env=env).
4. Output: the ralphex exit code, propagated unchanged.
```

Constraint: do not assemble or invoke the ralphex command directly — only
through `run_ralphex`. Secret safety: env values never in argv/logs/dry-run.

- [ ] **Declaration**: Task 13 — pass executor re-signature
- [ ] **Contract tests**: in `tests/build/test_build_pass.py` — `run_build_pass(plan, settings, options, wrapper_path, dry_run, env=None)` signature; delegates config write to `write_ralphex_config(settings, wrapper_path)` and launch to `run_ralphex(plan, options, dry_run, env=env)` (expected to fail at this stage)
- [ ] **Code**: rewrite `goga/build/build_pass.py` per the trace
- [ ] **Interface verification**: `pytest tests/build/test_build_pass.py -x -q` — contract tests pass
- [ ] **Logic tests**: positive — config file written before launch (order recorded via monkeypatched collaborators), exit code propagated unchanged (stub returns 7 → 7); negative — env layer forwarded verbatim to `run_ralphex` and never printed; edge — `env=None` passes pure inheritance
- [ ] **Debugging**: `pytest tests/build/test_build_pass.py -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: no direct subprocess call to ralphex in the module
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 14: Plan relocation outcome — `plan_relocation.py` (TDD coding)

Changes the relocation to return the outcome facts. Covers `move_completed_plan`
in `goga/build/CODEMANIFEST` (location `plan_relocation.py`). Locations:
`goga/build/plan_relocation.py`, `tests/build/test_plan_relocation.py`.

**Usages relevant to this task:**
- `conventions`: test layout, tmp_path file I/O

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm (manifest, verbatim): `not outcome or dry_run` →
`RelocationOutcome(moved=False, destination=None)`; else `Path.replace` into
`<plan_dir>/completed/<name>` (mkdir parents, exist_ok) →
`RelocationOutcome(moved=True, destination=str(dest))`. Constraint: do not
hard-code `docs/plans/` — the directory follows the plan file location.

- [ ] **Declaration**: Task 14 — plan relocation outcome
- [ ] **Contract tests**: in `tests/build/test_plan_relocation.py` — return type is `RelocationOutcome` (importable from `goga.build.hooks`) (expected to fail at this stage)
- [ ] **Code**: rewrite `goga/build/plan_relocation.py` per the algorithm
- [ ] **Interface verification**: `pytest tests/build/test_plan_relocation.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_move_completed_plan_returns_relocation_outcome` (setup `tmp_path/docs/plans/plan.md`; input `move_completed_plan(str(plan), outcome=True, dry_run=False)` → `relocation.moved is True`; `relocation.destination == str(tmp_path/"docs/plans/completed/plan.md")`; source gone; variants: `outcome=False` → `moved is False, destination is None`; `dry_run=True` → same not-moved outcome and file stays); `test_move_completed_plan_is_idempotent_by_name` (run the relocation twice on the same plan, recreating the source between calls → second call overwrites `completed/plan.md` without error)
- [ ] **Debugging**: `pytest tests/build/test_plan_relocation.py -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: directory follows the plan file location (test with a non-default plan dir)
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 15: The 12-step build cycle — `build.py` rewrite and retired-module deletion (TDD coding)

The central rewrite. Covers `build()` in `goga/build/CODEMANIFEST` (location
`build.py`): the 12-step checkpoint cycle. Deletes `resolve_review_options`/
`ReviewOptions` (file `goga/build/review_options.py`) and
`tests/build/test_review_options.py`, and the private helpers `_resolve_options`
/ `_review_scoped_options` (superseded by `resolve_run_settings` /
`compose_pass_options`). Adds the private helper `_completion_statuses(work) ->
list[str]`. The git pre-check helpers (`_unquote_git_path`,
`_parse_porcelain_path`, `_find_uncommitted_manifests`) stay. Locations:
`goga/build/build.py`, delete `goga/build/review_options.py`,
`tests/build/test_build.py`, delete `tests/build/test_review_options.py`,
rewrite `tests/build/test_build_resolved_wrapper.py`, update
`tests/build/test_shipped_ralphex_assets.py`.

**Usages relevant to this task:**
- `checkpoints` (from `goga/build/hooks/.usages/checkpoints.md`): the
  checkpoint integration order and fact resolution — read first
- `topic-paths`, `topic-statuses` (from `goga/history`): `resolve_current_branch_name() or "unknown"`;
  `resolve_topic_dir(branch)` (+`ValueError` guard, `.is_dir()`) → slug/year;
  `collect_topic_statuses(year=work.year)` filtered to `work.slug`
- `ralphex`, `agent-wrappers`, `resolve-wrapper-path`, `run-ralphex`: per their
  cells (wrapper resolution feeding the passes; delegation of the launch)
- `build-usage` (`goga/build/.usages/build-usage.md`): the in-container
  invocation contract — verify the implementation matches it
- `registering-hooks` (`goga/build/.usages/registering-hooks.md`): its "missing
  agent returns before any checkpoint" claim is kept true by the step-3.5 guard
- `conventions`: logging with `extra`, never a traceback

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace — the full cycle:

```
1. Input: plan path, ProjectConfig, cli_options.
2. Step 0: manifest pre-check (existing _find_uncommitted_manifests) — failure
   → return 1, no events (the moment never happened).
3. Steps 1–3: resolve_run_settings → validate_review_config (ValueError → log +
   return 1) → sync_ralphex_defaults (ValueError → log + return 1).
   config.build is guaranteed non-None by the host guard (step 2.2 of
   goga/commands/build); a build-less config invoked directly in-container is
   out of contract. STEP 3.5 GUARD: settings.tasks.agent is None →
   logger.error("no build agent resolved: set build.agent in .goga/config.yml")
   → return 1 — the degenerate skip-run case (validate_review_config returns
   early on skip, so the run would otherwise crash at step 7's
   resolve_wrapper_path(None) with a TypeError after emit_build_started fired);
   keeps the registering-hooks claim "missing agent returns before any
   checkpoint" true on the direct in-container path.
4. Step 4: branch = resolve_current_branch_name() or "unknown"; topic_dir =
   resolve_topic_dir(branch) guarded (ValueError → None, an unsluggable branch
   hosts no topic); hosted (topic_dir.is_dir()) →
   WorkIdentity(branch, slug=topic_dir.name, year=topic_dir.parent.name) else
   WorkIdentity(branch); moment = BuildMoment(plan, work, dry_run);
   tasks_facts/review_facts per StageFacts (env = sorted(env) — names only,
   deterministic) with the review-only members None on tasks and
   AdditionalFacts(agent, patience, max_iterations) on review — no git/process
   reads AFTER this step.
5. Step 5: hooks = BuildHooks(); verdict = hooks.validate_build(moment,
   tasks_facts, review_facts, settings.skip); not verdict.approved → one merged
   logger.error("build blocked by hook vetoes", extra={"violations":
   [f"{v.tool}/{v.hook}: {v.reason}" for v in verdict.violations]}) → return 1;
   no pass, no relocation, no further events.
6. Step 6: hooks.emit_build_started(moment, tasks_facts, review_facts,
   settings.skip).
7. Step 7: tasks pass — options = compose_pass_options(settings, "tasks");
   wrapper = resolve_wrapper_path(settings.tasks.agent);
   hooks.emit_pass_started(moment, tasks_facts); exit_code = run_build_pass(
   plan, settings, options, wrapper, dry_run, env=tasks_layer) where
   tasks_layer = settings.tasks.env or None; hooks.emit_pass_completed(moment,
   tasks_facts, exit_code); stages = ["tasks"].
8. Step 8: exit_code == 0 and not settings.skip → review pass — options =
   compose_pass_options(settings, "review"); wrapper =
   resolve_wrapper_path(settings.review.additional.agent if strategy == "short"
   else settings.review.agent); the same emit/launch/emit triple with
   review_facts and review_layer = settings.review.env or None;
   stages.append("review"). A failed tasks pass never reaches here.
9. Step 9: relocation = move_completed_plan(plan, outcome=(exit_code == 0),
   dry_run=dry_run).
10. Step 10: statuses — work.slug is None → []; else the matching
    collect_topic_statuses(year=work.year) record's statuses (absent topic →
    []) — re-read AFTER the relocation attempt.
11. Step 11: hooks.emit_build_completed(moment, exit_code, stages, relocation,
    statuses).
12. Output: return exit_code (the last executed pass's code).
```

Checkpoint summary (design): dry-run parity — identical steps; `run_ralphex`
prints and returns 0; relocation stays (dry_run guard); events carry
`moment.dry_run=True`. Pre-launch failures (0–3) and a blocked run (5) fire no
events. Exit code = last executed pass's code; relocation only on final-pass
success.

Test setup (General Setup of the design's Test Stack Trace, verbatim):
orchestration tests monkeypatch `goga.build.build.run_build_pass` (or
`goga.ralphex.run_ralphex.run_ralphex`) with a recording stub, run inside
`tmp_path` (`.ralphex/` writes land there), and monkeypatch
`resolve_current_branch_name`/`resolve_topic_dir`/`collect_topic_statuses` at
`goga.build.build`'s import point. Wrapper existence tests monkeypatch
`resolve_wrapper_path` at its import point.

- [ ] **Declaration**: Task 15 — the 12-step build cycle
- [ ] **Contract tests**: in `tests/build/test_build.py` — `build(plan, config, cli_options)` importable from `goga.build`; the cycle calls `resolve_run_settings`, `validate_review_config`, `sync_ralphex_defaults`, `compose_pass_options`, `run_build_pass`, `move_completed_plan`, and the five `BuildHooks` checkpoints in the traced order (expected to fail at this stage)
- [ ] **Code**: rewrite `goga/build/build.py` per the 12-step trace (steps 0–3.5 guard, 4–11, return); new `_completion_statuses(work)` helper; imports from `.run_settings`, `.pass_options`, `.review_config`, `.ralphex_runtime`, `.build_pass`, `.plan_relocation`, and the zone facade via `from .hooks import …` (relative intra-package, mirroring `goga/pipeline/run_pipeline.py`); `from ..history import resolve_current_branch_name, resolve_topic_dir, collect_topic_statuses`
- [ ] **Code**: delete `goga/build/review_options.py` and `tests/build/test_review_options.py`; remove `_resolve_options` and `_review_scoped_options` from `build.py`; no compatibility shims
- [ ] **Interface verification**: `pytest tests/build/test_build.py -x -q` — contract tests pass
- [ ] **Logic tests** (in `tests/build/test_build.py`): `test_build_runs_two_passes_with_bound_settings` (setup: tmp cwd with config; monkeypatch `goga.build.build.run_build_pass` recording `(options, wrapper, env)` returning 0; `resolve_current_branch_name` → `"add-hooks-to-build"`, `resolve_topic_dir` → raises ValueError (branch-only), `collect_topic_statuses` → `[]`; `cli_options` all None, `dry_run` False; no tool packages pinned → assert `run_build_pass` called exactly twice; first call `options["tasks_only"] is True` and `env == {"A":"1"}`; second call `options["review"] is True` and env is the review layer — never the root env; return 0; plan relocated); `test_build_skipped_review_single_tasks_pass` (same + `cli_options={"skip_review": True}` → exactly one `run_build_pass` call (`tasks_only`); return value = that pass's code); `test_build_failed_tasks_pass_skips_review` (`run_build_pass` first call returns 1 → one pass call only; `pass_completed` for tasks carries `exit_code == 1`; `BuildCompleted.stages == ["tasks"]`; relocation not moved; return 1); `test_build_vetoed_run_blocks_before_any_pass` (two-pass setup + one tool whose `validate_build` hook vetoes `"policy"`; `run_build_pass` recorder → return 1; `run_build_pass` never called; plan file in place; NO notification hook of the tool ran; exactly one `logger.error` record carrying the violation triple — caplog); `test_build_pre_launch_failures_fire_no_events` (tool subscribed to all five actions — recorder; parametrize: uncommitted CODEMANIFEST (patch `_find_uncommitted_manifests` → `["x/CODEMANIFEST"]`), invalid review config (patch `validate_review_config` → raise), unavailable defaults (patch `sync_ralphex_defaults` → raise), no build agent on a skip run (config with root agent None + `cli_options={"skip_review": True}` — the step-3.5 guard path) → return 1; zero hook invocations across all five actions in every variant); `test_unsluggable_branch_falls_back_to_branch_only` (`resolve_topic_dir` raises ValueError; `resolve_current_branch_name` → None → `WorkIdentity.branch == "unknown"`, `slug is None`; statuses `[]`; run proceeds normally); `test_build_statuses_recomputed_after_relocation` (topic-hosting branch: `resolve_current_branch_name → "add-hooks-to-build"`, `resolve_topic_dir → Path(".goga/history/2026/add-hooks-to-build")` (is_dir True); `collect_topic_statuses` stub returning `[TopicRecord("add-hooks-to-build", ["backlog", "designed"])]`; successful run → recorded `BuildCompleted.statuses == ["backlog", "designed"]`; `collect_topic_statuses` called with `year="2026"` AFTER `move_completed_plan` (order recorded); branch-only variant delivers `[]`); `test_stage_facts_carry_env_names_only` (settings with `tasks.env={"A":"1","B":"2"}` → orchestration facts: `StageFacts.env == ["A", "B"]` sorted names; walk `dataclasses.fields` of every context and assert no string member equals `"1"`/`"2"`)
- [ ] **Code**: rewrite `tests/build/test_build_resolved_wrapper.py` onto the two-part schema (`build.agent` at the root); delete the `codex_review → codex_enabled` case (the key is retired; the strategy-table test of Task 12 covers the new derivation); keep the uncommitted-manifests / ralphex-missing / custom-prompts-dir cases on the new fixtures
- [ ] **Code**: update `tests/build/test_shipped_ralphex_assets.py` — replace the `BuildConfig(task_executor=TaskExecutorConfig(...))` construction with the two-part `BuildConfig(agent=..., env={})`; the vendored asset assertions are unchanged
- [ ] **Debugging**: `pytest tests/build/ -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: facade `from goga.build import build` resolves; no compatibility shims (`grep -rn "review_options" goga/ tests/` empty); `--worktree`/`--skip-finalize`/`worktree`/`skip_finalize` absent from `goga/build/`
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting, apply decomposition if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 16: In-container CLI surface — `__main__.py` (TDD coding)

Updates the argparse surface. Covers `main()` in `goga/build/CODEMANIFEST`
(location `__main__.py`). `ensure_in_docker()` stays the very first statement;
both guard branches must be covered by tests (manifest requirement). Locations:
`goga/build/__main__.py`, `tests/build/test_main.py`,
`tests/build/test_contract.py`.

**Usages relevant to this task:**
- `ensure-in-docker` (from `goga/docker`): the guard contract at step 0
- `build-usage`: the cli_options list the container entrypoint accepts
- `conventions`: CLI docstring rules, test layout

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace:

```
ensure_in_docker() first → argparse (plan, --dry-run, --skip-manifest-check,
--skip-review/--no-skip-review → skip_review: bool | None, --base-ref,
--review-patience, --session-timeout, --idle-timeout, --wait, --max-iterations;
NO --worktree/--skip-finalize) → cli_options with exactly those keys
(dry_run, skip_manifest_check, skip_review, base_ref, review_patience,
session_timeout, idle_timeout, wait, max_iterations — worktree/skip_finalize
keys removed from the dict) → load_project_config() → build(...) → exit code.
→ checkpoint: cli_options keys match what resolve_run_settings reads.
```

Current stale lines: `goga/build/__main__.py:22–23` (`--worktree`,
`--skip-finalize` add_argument) and `:38–39` (their cli_options keys).

- [ ] **Declaration**: Task 16 — in-container CLI surface
- [ ] **Contract tests**: in `tests/build/test_main.py` — `main()` forwards exactly the nine cli_options keys; `--worktree`/`--skip-finalize` exit with argparse error (expected to fail at this stage)
- [ ] **Code**: update `goga/build/__main__.py` per the trace (remove the two flags and their dict keys)
- [ ] **Interface verification**: `pytest tests/build/test_main.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_main_argparse_surface_matches_contract` (monkeypatch `sys.argv` / `ensure_in_docker`; patch `goga.build.__main__.build`; input `["goga.build", "plan.md", "--skip-review", "--review-patience", "3"]`; repeat with `["goga.build", "plan.md", "--no-skip-review"]` → forwarded `cli_options["skip_review"] is True` / `cli_options["review_patience"] == 3`; the `--no-skip-review` variant forwards `cli_options["skip_review"] is False` (the tri-state False arm); parsing `--worktree` or `--skip-finalize` exits with SystemExit 2; guard `ensure_in_docker` called first — both branches covered per the manifest requirement)
- [ ] **Code**: update `tests/build/test_contract.py` to the new cell surface (facade `build`; module imports `goga.build.run_settings` / `goga.build.pass_options`; no retired names)
- [ ] **Debugging**: `pytest tests/build/ -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: cli_options keys match `resolve_run_settings`'s read set exactly
- [ ] **Lint**: `ruff check goga/build tests/build` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 17: Host launcher surface — `goga/commands/build` (TDD coding)

Applies the three host-command deltas and the flag removals. Covers `build(...)`
in `goga/commands/build/CODEMANIFEST` (location `build.py`): the existing
19-step algorithm with three deltas; `resolve_build_runtime_dir`,
`clean_build_runtime_dir`, `_cleanup_ralphex_in_project` unchanged. Locations:
`goga/commands/build/build.py`, `tests/commands/conftest.py`,
`tests/commands/test_build.py`, `tests/commands/build/test_build.py`, and the
four `tests/commands/build/test_build_*_integration.py` fixture updates.

**Usages relevant to this task:**
- `click` (`.goga/usages/cooks/click.md`): option declarations; command
  docstrings verbatim-help (no Args/Returns/Raises)
- `build-usage` (from `goga/build`): the in-container invocation contract
  (`-m goga.build <plan> <cli_flags>`)
- `project-configuration`, `home-configuration` (from `goga/config`): the
  two-part build schema and the env base-layering
- `docker-builder`, `docker-runner`, `docker-image-version`,
  `resolve-credential-mounts`, `runtime-paths`, `docker-auth-mounts`: unchanged
  consumer contracts — only the flag/env deltas touch them
- `conventions`: test layout, CliRunner pattern

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace (three deltas on the existing 19-step algorithm):

```
- step 2.2 guard message/key becomes: config.build.agent is None →
  ClickException("build.agent is required in .goga/config.yml to run
  'goga build'")
- step 2.3 (two-pass × worktree guard) DELETED
- step 7 env assembly becomes {**home.env, **git_env, **cli_env} — the task env
  (config.build.env) is NOT written to the env-file (it reaches the container
  only through the mounted .goga/config.yml and is applied in-container as the
  tasks-pass layer)
CLI flags: --worktree/--skip-finalize options and their forwarding removed
(_build_cli_args branches at build.py:118–120, the click option at :215, the
callback params at :265–266); --review-patience/--base-ref forwarding unchanged
(value-flag pattern); help text repointed to build.review.additional.patience /
build.review.base_ref.
→ checkpoint: host forwards, container resolves.
```

Also drop `config.build.env` from the comments that call the env-file
"task_executor secrets". Constraint from the manifest: no worktree handling
anywhere on the surface — no flag, no guard, no worktree-related rejection.

- [ ] **Declaration**: Task 17 — host launcher surface
- [ ] **Contract tests**: in `tests/commands/build/test_build.py` — `--worktree`/`--skip-finalize` are unknown options (exit 2 + message); the step-2.2 guard message names `build.agent` (expected to fail at this stage)
- [ ] **Code**: apply the three deltas + flag removals to `goga/commands/build/build.py` per the trace
- [ ] **Code**: update `tests/commands/conftest.py` shared config-writing helpers to the two-part schema (`build: {agent: …}`); drop the `worktree`/`skip_finalize`/`codex_review`/`review_executor` lines
- [ ] **Code**: update `tests/commands/test_build.py` — replace the `worktree`-option assertion with the removed-surface assertion (unknown option, exit 2); repoint the `task_executor` config fixture to `build.agent`
- [ ] **Interface verification**: `pytest tests/commands/ -x -q` — contract tests pass
- [ ] **Logic tests**: `test_host_command_surface_and_env_file` (click runner `CliRunner`; tmp config with two-part build; existing host fixtures; invoke `goga build plan.md` and with `--base-ref x --review-patience 2 --skip-review` → `--worktree`/`--skip-finalize` unknown options (exit 2 + message); guard message names `build.agent`; forwarded args contain `--base-ref x` / `--review-patience 2` / `--skip-review` only when set; the written env-file contains home/git/cli env keys and NOT the `build.env` values (secret boundary); docker args carry `-m goga.build <plan>`)
- [ ] **Code**: update the four integration files to the two-part schema and the env-file assertions (the task env is no longer written into the env-file): `tests/commands/build/test_build_home_integration.py`, `test_build_proxy_hosts_update.py`, `test_build_runtime_isolation_integration.py`, `test_build_credential_mount_integration.py`
- [ ] **Debugging**: `pytest tests/commands/ -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: `grep -rn -e "--worktree" -e "--skip-finalize" goga/commands/` empty; host does not resolve the tri-state or base-ref precedence (forwarding only)
- [ ] **Lint**: `ruff check goga/commands tests/commands` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 18: Onboarding two-part build emission — `goga/onboarding/generator` (TDD coding)

Repoints the generated config to the two-part build root. Covers the
`FileGenerator.generate_goga_config` snapshot→YAML build mapping in
`goga/onboarding/generator/CODEMANIFEST` (location `generator.py`; code change
in the private `_build_config_document`/`_executor_block` helpers). An existing
`.goga/config.yml` is never rewritten — that guarantee is untouched. Locations:
`goga/onboarding/generator/generator.py`, `tests/onboarding/generator/test_generator.py`.

**Usages relevant to this task:**
- `convention`: docstring style, relative imports
- `yaml` (inline): `yaml.dump(default_flow_style=False)`

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Verified design trace:

```
data["build"] = build_block (agent, env at the two-part root) instead of
{"task_executor": build_block}; _executor_block docstring reworded (build root /
pipeline content). → checkpoint: the generated file passes the new loader
(config.build.agent resolves).
```

Current stale lines: `generator.py:59–60` (`_executor_block` assembling a
`build.task_executor` dict) and `:159–163` (`data["build"] =
{"task_executor": build_block}`). This fixes the design-review defect: the
generator would otherwise emit a silently-disabled build section under the new
loader.

- [ ] **Declaration**: Task 18 — onboarding two-part build emission
- [ ] **Contract tests**: in `tests/onboarding/generator/test_generator.py` — the generated `build` block has `agent`/`env` at the root, no `task_executor` nesting (expected to fail at this stage)
- [ ] **Code**: update `goga/onboarding/generator/generator.py` per the trace (emission + `_executor_block` docstring reword)
- [ ] **Interface verification**: `pytest tests/onboarding/generator/test_generator.py -x -q` — contract tests pass
- [ ] **Logic tests**: `test_onboarding_generator_emits_two_part_build` (onboarding answers `build: {agent: "claude", env: {API_KEY: "secret"}}` — existing fixture pattern; input `generate_goga_config(answers)` → load the written file with `load_project_config` → `cfg["build"] == {"agent": "claude", "env": {"API_KEY": "secret"}}` (no `task_executor` nesting); `config.build.agent == "claude"` — the generated file actually drives a build)
- [ ] **Debugging**: `pytest tests/onboarding/ -x -q` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: round-trip — generated file passes `load_project_config` with the two-part extraction
- [ ] **Lint**: `ruff check goga/onboarding tests/onboarding` — fix formatting if necessary
- [ ] **Completion**: mark all checkboxes of this task complete

### Task 19: Integration tests for the build cycle and the end-to-end flows (integration tests)

Cross-entity and cross-package scenarios: the three rewritten end-to-end suites
plus the orchestration integration scenarios that exercise `goga/build` ×
`goga/build/hooks` × the fake tool packages together. Test setup follows the
design's General Setup verbatim (zone fixtures re-exported by
`tests/build/hooks/conftest.py`; orchestration monkeypatching at
`goga.build.build`'s import point; runs inside `tmp_path`).

**Usages relevant to this task:**
- `checkpoints` (from `goga/build/hooks/.usages/checkpoints.md`): the expected
  checkpoint sequence the end-to-end assertions verify against
- `build-usage`: the in-container invocation contract of the end-to-end flows
- `run-ralphex` (from `goga/ralphex`): flag expectations of the launcher-level
  assertions

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Rewrite `tests/integration/test_base_ref_end_to_end.py` onto the two-part config and the always-two-pass cycle (base_ref flows CLI > `build.review.base_ref` > omit)
- [ ] Rewrite `tests/integration/test_skip_review_end_to_end.py` onto the two-part config and the always-two-pass cycle (the skip form: exactly one tasks pass)
- [ ] Rewrite `tests/integration/test_resolved_wrapper_flow.py` onto the two-part config and the always-two-pass cycle (wrapper resolution per pass; the additional wrapper under short)
- [ ] Add to `tests/build/test_build.py` the orchestration integration scenarios: `test_notifications_carry_completion_facts` (one tool subscribing all four soft actions with hooks recording `context` via `self`; orchestration as in the two-pass test with the tasks pass returning 0 and the review pass returning 2 → recorded contexts expose `PassCompleted.exit_code == 2` for the review facts; `BuildCompleted.exit_code == 2`; `stages == ["tasks", "review"]`; a crashing notification hook — separate variant — warns and the return code stays 2); `test_build_dry_run_rehearses_event_structure` (two-pass setup with `dry_run=True`; `run_build_pass` NOT patched at the pass level — patch `goga.ralphex.run_ralphex.run_ralphex` to assert it is called with `dry_run=True` → both passes "ran" (launcher called twice, both dry); the plan file still at its original path; `BuildCompleted.relocation.moved is False`; recorded notification `moment.dry_run is True`); `test_registry_built_once_across_checkpoints` (one tool subscribing `validate_build` + `build_started` + `build_completed`; pin the enumeration boundary mock and count reads → the `packages_distributions` boundary read exactly once across a full `build(...)` run)
- [ ] Test edge case: second run sees an edited hook (SC10 — registration re-reads; assert a second `build(...)` run in the same process picks up a hook edit between runs)
- [ ] Run validation: `pytest tests/integration/ tests/build/ -x -q`, then the full suite `pytest tests/ -x`

---

## Validation Commands

All commands run in the `.venv` virtualenv from the repo root.

- `pytest tests/ -x`: Run all tests (the design's validation run; covers every
  suite listed in the Source File Registry and the affected-tests addendum)
- `ruff check goga/config goga/hooks goga/ralphex goga/build goga/commands goga/onboarding tests/config tests/hooks tests/ralphex tests/build tests/commands tests/onboarding tests/integration`: Lint check over every touched package
- `python -c "from goga.build.hooks import BuildHooks, BuildMoment, StageFacts, WorkIdentity, AdditionalFacts, RelocationOutcome, Violation, GateVerdict, BuildValidation, BuildStarted, PassStarted, PassCompleted, BuildCompleted"`: Zone facade accessibility (13 names)
- `python -c "from goga.config import BuildConfig, ReviewConfig, AdditionalReviewConfig"`: Config facade accessibility (and `python -c "from goga.config import TaskExecutorConfig"` must raise `ImportError`)
- `grep -rn -e "--worktree" -e "--skip-finalize" -e "worktree" -e "skip_finalize" -e "codex_review" -e "task_executor" -e "review_executor" goga/`: Absence check — expected hits are ONLY the retirement/migration documentation in manifests/usages and the loader's ignore-everything stance
- `goga lint`: Cell/manifest integrity (79 cells, 0 errors)
- `goga schema`: Dependency graph — `goga/build/hooks` shows exactly 13 types and a single dependency on `goga/hooks`
- Dogfooding acceptance (post-implementation, manual): a real `goga build` run on this repository executes the two passes over the migrated config; `goga hooks` lists build subscriptions of any installed tool

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (13 zone
      types across `facts.py`/`contexts.py`/`events.py`; `run_settings.py`,
      `pass_options.py` created; all re-signatured routines updated)
- [ ] Every contract entity is accessible from its facade
      (`goga.build.hooks` 13 names; `goga.config` embeddings; `goga.build.build`)
- [ ] Properties and methods match the declared API (kw_only dataclasses;
      frozen where the contract says frozen — `RunSettings`/`PassSettings`/
      `ReviewPassSettings` and the config model — non-frozen zone facts/contexts)
- [ ] Descriptions are reflected in behavior (checkpoint order, inheritance
      rules, zero-valued external flags, veto semantics, secret boundaries)
- [ ] Contract dependencies are met (imports from `goga/hooks`, `goga/history`,
      `goga/agents`, `goga/ralphex`, `goga/docker`, `goga/config` resolve as declared)
- [ ] Re-exports are accessible from the facade (`ReviewConfig`,
      `AdditionalReviewConfig` from `goga.config`; retired names gone)
- [ ] Every coding task followed the TDD workflow (contract tests → code →
      verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each
      coding task — 39 named scenarios (26 positive, 6 negative, 7 edge) plus
      the rewritten existing suites
- [ ] Integration tests exist where cross-entity scenarios require them
      (Task 19: three end-to-end rewrites + notifications/dry-run/registry-once
      orchestration scenarios)
- [ ] No package boundary was expanded (no new cells beyond the contract-declared
      `goga/build/hooks`; internal helpers only within existing cells)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only);
      `.goga/config.yml` was not touched (already migrated)
- [ ] All validation commands pass (`pytest tests/ -x`, ruff, facade checks,
      absence greps, `goga lint` 79 cells / 0 errors, `goga schema` 13 types)
- [ ] Every Usages entry is mentioned in at least one task (calibration table:
      `conventions`/`convention` all tasks; `ralphex` 3/9/11/12/13;
      `agent-wrappers` 10/12/15; `checkpoints` 7/15/19; `topic-paths`/
      `topic-statuses` 15; `resolve-wrapper-path` 10/12/15; `run-ralphex`
      3/13/15/19; `ensure-in-docker` 16; `build-usage` 15/16/17/19;
      `project-configuration` 1/17; `home-configuration` 17; `declaring-actions`/
      `per-tool-delivery`/`registering-hooks` 4–7; `click` 17; `yaml` 1/18;
      docker practices 17)
