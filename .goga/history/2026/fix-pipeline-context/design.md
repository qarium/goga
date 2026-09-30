# Design Document: `fix-pipeline-context`

<!-- Topic: fix-pipeline-context — split the run context from the host launch context (pipeline and build) -->

Stage: code-design (Designing architecture into code). Derived from the CODEMANIFEST
changes materialized by apply-architecture from `.goga/history/2026/fix-pipeline-context/arch.md`.
Branch: `fix-pipeline-context`; base: the working tree at `HEAD` (commit `6e74e1f`) —
the contracts below are already on disk, the implementation is not.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/docker/CODEMANIFEST`: +2 routines (`encode_extra_env`, `decode_extra_env`, both
  `location: extra_env.py`), global annotation zone extended with the engine-variable
  carriage responsibility, footer description updated.
- `goga/afm/CODEMANIFEST`: `run_flow` signature gains `env: dict[str, str] | None = None`;
  global annotations + routine annotations/algorithm/requirements/constraints extended for
  the env layer (secret-safe, subprocess-only).
- `goga/config/project/CODEMANIFEST`: property annotations of `PipelineConfig.agent` and
  `PipelineConfig.env` rewritten — the consumer is now the in-container `goga/pipeline`;
  `env` never travels through the docker launch env-file. Design-review fix: two
  Requirements bullets (`load_project_config`'s pipeline-block bullet and
  `PipelineConfig`'s agent bullet) also drop the retired host-guard sentence
  ("the pipeline command raises a clean ClickException when it needs an agent") —
  replaced with the in-container-consumer statement, aligning the Requirements
  blocks with the rewritten property annotations.
- `goga/pipeline/CODEMANIFEST`: Imports gain `decode_extra_env` + `extra-env-carriage`
  (goga/docker), `load_project_config` + `project-configuration` (goga/config),
  `ConfigHooks`/`ConfigOverlay` types-only (goga/config/hooks), `resolve_wrapper_path` +
  `resolve-wrapper-path` (goga/agents); local `Usages` gains `afm`; `run_pipeline`
  re-algorithmized to 21 steps (load-and-amend, afm configuration authorship, launch
  environment composition); new routine `write_afm_config` (`location: afm_config.py`);
  footer description updated.
- `goga/build/CODEMANIFEST`: Imports gain `ConfigHooks`/`ConfigOverlay` types-only
  (goga/config/hooks), `decode_extra_env` + `extra-env-carriage` (goga/docker); `build`
  re-algorithmized to 14 steps (agent guard moved before the `.ralphex/` rewrite, one
  payload decode feeding both pass layers); `main` gains the load-and-amend steps;
  `resolve_run_settings` step 4 reachability note updated.
- `goga/commands/pipeline/CODEMANIFEST`: Imports drop `resolve_wrapper_path` /
  `resolve-wrapper-path` / `agent-wrappers`, gain `encode_extra_env` +
  `extra-env-carriage` (goga/docker); `pipeline` command and `run_pipeline_container`
  re-specified — host owns launch mechanics only, tmpfile flow retired, env-file ladder
  reordered (CLI lines before engine lines, engine lines skip CLI-supplied keys,
  `GOGA_EXTRA_ENV` payload line), agent resolution and `pipeline.env` carriage removed;
  info-form constraints updated; footer description updated.
- `goga/commands/build/CODEMANIFEST`: Imports gain `encode_extra_env` +
  `extra-env-carriage` (goga/docker); host agent value guard removed (structural
  build-section guard stays), env-file ladder reordered with the payload line;
  `extra_env` parameter annotation updated.

### New Entities

- `encode_extra_env(entries: list[str]) -> value: str` — goga/docker, `extra_env.py` (file
  to create). Pure encoder of CLI environment entries into the single-line engine payload.
- `decode_extra_env(value: str) -> entries: dict[str, str]` — goga/docker, `extra_env.py`.
  Pure decoder of the engine payload back into the CLI environment mapping.
- `write_afm_config(agent: str | None) -> config_path: Path` — goga/pipeline,
  `afm_config.py` (file to create). Writes the whole in-container afm configuration file
  before the launch.
- Practice `extra-env-carriage` — `goga/docker/.usages/extra-env-carriage.md` (created by
  apply-architecture; the consumer wiring contract of the carriage).

### Changed Entities

- `run_flow` (goga/afm) — optional `env` layer applied on top of the inherited process
  environment for the afm subprocess only; never composed here, never logged.
- `run_pipeline` (goga/pipeline) — opens with the configuration load-and-amend; writes
  the afm configuration file via `write_afm_config` before the launch; composes the afm
  launch environment layer (effective `pipeline.env` + decoded CLI entries, engine keys
  dropped) and passes it as `run_flow`'s `env`.
- `main` (goga/build) — performs the load-and-amend at the entrypoint and hands the
  effective configuration to `build`.
- `build` (goga/build) — agent value guard runs before the first state write (the
  `.ralphex/` rewrite); decodes the CLI entries payload once; composes each pass env
  layer (effective task env layer + CLI entries, engine keys dropped).
- `resolve_run_settings` (goga/build) — step 4 reachability note: the no-review-agent
  error is reachable when neither the authored configuration nor an amendment supplies
  a review agent.
- `build` host command (goga/commands/build) — agent value guard removed; env-file
  ladder reordered with the `GOGA_EXTRA_ENV` payload line.
- `run_pipeline_container` (goga/commands/pipeline) — afm-config tmpfile retired; agent
  resolution removed; env-file ladder reordered with the payload line; `pipeline.env`
  no longer written into the env-file.

### Deleted Entities

- None at the contract level. Implementation-side deletions this design specifies:
  `_write_afm_config_tmpfile` and the wrapper resolution in
  `goga/commands/pipeline/run_pipeline_container.py`, the `agent-wrappers` practice
  declaration (already removed from the manifest), the tmpfile mount and its `finally`
  unlink, and the host agent guard in `goga/commands/build/build.py`.

### Usages and Annotations Changes

- `.goga/usages/cooks/afm.md` — config.yaml authorship moved to the in-container run
  coordination; "Environment carriage" section added (the ladder and the
  `GOGA_EXTRA_ENV` payload rule fixed at the practice level).
- `goga/docker/.usages/extra-env-carriage.md` — NEW: the carriage contract (host half,
  container half, engine-variable ladder, one-source rule).
- `goga/afm/.usages/run-flow.md` — `env` parameter documented; "Environment layer
  contract" section added.
- `goga/config/hooks/.usages/checkpoints.md` — "in-container loads stay authored-only"
  replaced by "One action, two moments" (both delivery moments, field ownership,
  applied-but-unconsumed semantics).
- `goga/config/.usages/registering-hooks.md` — `amend_config` fires at the load moment of
  every config-consuming surface, host commands and in-container entrypoints alike.
- `goga/pipeline/.usages/run-pipeline.md` — load-and-amend, afm configuration, and the
  two environment reads; threading chain extended with the `-e KEY=V` path.
- `goga/pipeline/.usages/registering-hooks.md` — `run_created` fires after the afm
  configuration write; config load/delivery failures fire nothing.
- `goga/build/.usages/build-usage.md` — load-and-amend preamble, "Environment ladder"
  and "Agent guard" sections; `main()` description updated.
- `goga/build/.usages/registering-hooks.md` — pre-launch failure list includes the agent
  value guard (effective agent).
- `goga/commands/build/.usages/build.md` — guard split documented; env-file layers and
  payload documented; `-e` semantics updated.
- `goga/commands/pipeline/.usages/pipeline-command.md` — "Environment carriage (run
  form)" section; Docker shapes without the tmpfile; threading chain extended.

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Phase 3 validation of the changed contracts found no defects:

  - `goga lint` → 83 cells, 0 errors (3 consecutive runs).
  - All `Imports` of the changed manifests resolve; every file referenced by an import
    exists (`goga/config/.usages/project-configuration.md`,
    `goga/agents/.usages/resolve-wrapper-path.md`,
    `goga/docker/.usages/extra-env-carriage.md`, `goga/afm/.usages/run-flow.md`,
    `goga/config/hooks/.usages/checkpoints.md`, `goga/pipeline/hooks/.usages/checkpoints.md`).
  - All backtick references in changed annotations resolve within their document context
    (checked per file; no stale `agent-wrappers` / `resolve-wrapper-path` references
    remain in `goga/commands/pipeline`; `checkpoints` in goga/build resolves to its own
    `goga/build/hooks` import; docker's `convention` key matches its `Usages`).
  - No new cross-imports: the new edges (`goga/pipeline → goga/config/hooks`,
    `goga/pipeline → goga/agents`, `goga/build → goga/config/hooks`) all point downward
    in the schema graph; no cycles (`goga/agents`, `goga/config/hooks` are importers of
    nothing that imports back).
  - `location` values of the new routines (`extra_env.py`, `afm_config.py`) are valid:
    same directory level, with extension, no traversal.

  Two documentation-level nuances (NOT contract defects — the normative rules live in
  the CODEMANIFESTs and are stated correctly there) are recorded for the implementer in
  "`.usages/` Update" below: the simplified host-half sketch in
  `extra-env-carriage.md`, and the engine-variable membership of `GOGA_EXTRA_ENV`.

---

## Entity Interaction and Data Flow

### Interaction Diagram

Pipeline domain (host owns launch mechanics, container owns run parameters):

```
HOST                                                      CONTAINER
════════════════════════════════════════════════════════════════════════════════

goga/commands/pipeline::pipeline (click)                  docker run --rm -p P:P
  │ load_home_config()                    ──env-file──►   python -m goga.pipeline run NAME
  │ load_project_config()   (authored)                    │ goga/pipeline::cli → run_pipeline
  │ ConfigHooks().amend_config()                          │  1  load_project_config()      (authored)
  │   └ summary_lines → stderr                            │  2  ConfigHooks().amend_config()
  │ guard: pipeline section (host-effective)              │     summary_lines → stderr
  │ read host-owned fields: image, dockerfile,            │     effective = overlay.config
  │   proxy, hosts                                        │  3–13 discovery → workflow → skip →
  ├─ run_pipeline_container(name, effective, …)           │     amend_workflow → compile →
  │   port, container_name, signal handlers               │     prompts (exactly 4 files)
  │   env-file ladder:                                    │  14 write_afm_config(effective
  │     home.env < git identity < CLI -e (raw)            │        .pipeline.agent)
  │       < engine lines (skip CLI keys):                 │        └ resolve_wrapper_path (goga/agents)
  │         AFM_DIR, AFM_DOCKER_FILE_ROOTS,               │  15–16 composition, statuses
  │         [HTTP(S)_PROXY, NO_PROXY]                     │  17 decode_extra_env(GOGA_EXTRA_ENV)
  │       < GOGA_EXTRA_ENV=encode_extra_env(-e)           │     layer = effective.pipeline.env
  │   mounts: /workspace, AFM_DIR state (rw)              │       ⊕ decoded entries ⊖ engine keys
  │   NO tmpfile, NO agent resolution                     │  18 emit_run_created
  └─ DockerRunner.run(...)                                │  19 run_flow(flow, port, parallel,
                                                            │        env=layer) → afm run …
                                                            │  20–21 emit_run_completed, exit code
```

Build domain:

```
HOST                                                      CONTAINER
════════════════════════════════════════════════════════════════════════════════

goga/commands/build::build (click)                        docker run --rm
  │ load_home_config()                    ──env-file──►   python -m goga.build PLAN …
  │ load_project_config() (authored)                      │ goga/build::__main__.main
  │ ConfigHooks().amend_config()                          │  0  ensure_in_docker()
  │   └ summary_lines → stderr                            │  1  argparse
  │ guard: build section (host-effective,                 │  2  load_project_config() (authored)
  │   structural) — agent guard REMOVED                   │  3  ConfigHooks().amend_config()
  │ read host-owned fields: image, dockerfile,            │  4  summary_lines → stderr
  │   proxy, hosts                                        │  5–6 cli_options; build(plan,
  ├─ env-file ladder:                                     │        overlay.config, cli_options)
  │     home.env < git identity < CLI -e (raw)            │  0–2  git pre-check, settings,
  │       < engine lines (skip CLI keys):                 │        review-config validation
  │         [HTTP(S)_PROXY, NO_PROXY]                     │  3    AGENT GUARD (effective agent,
  │       < GOGA_EXTRA_ENV=encode_extra_env(-e)           │        before any state write)
  │   mounts: /workspace, /workspace/.ralphex             │  4    sync_ralphex_defaults
  └─ DockerRunner.run(...)                                │  5    decode_extra_env(GOGA_EXTRA_ENV)
                                                          │  6–7  facts; validate_build gate
                                                          │  8    build_started
                                                          │  9    tasks pass: layer =
                                                          │        build.env ⊕ CLI ⊖ engine keys
                                                          │        → run_build_pass → run_ralphex
                                                          │ 10    review pass: layer =
                                                          │        build.review.env ⊕ same CLI
                                                          │ 11–14 relocation, statuses, completed
```

### Data Flows

**Flow A — the CLI environment carriage (one source, two carriers).**
The click `-e/--env` values (`extra_env: tuple[str, ...]`) feed exactly two artifacts
composed from the same parsed values: (1) the raw `KEY=VALUE` lines written verbatim
into the env-file; (2) `GOGA_EXTRA_ENV = encode_extra_env(list(extra_env))` appended as
the last env-file line. Docker's `--env-file` last-write-wins semantics give the
launcher-written payload line precedence over any CLI line of the same key. In-container,
`decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))` restores the mapping; the domain
applies it above its effective task env layer, drops the five engine keys, and passes the
result only through the `env` parameter of the target-binary launch (`run_flow` /
`run_ralphex`). The container's `os.environ` is never mutated.

**Flow B — the configuration (one action, two moments).**
`load_project_config()` reads `./.goga/config.yml` on each side (host CWD; in-container
`/workspace` — the project bind-mount). Each side then delivers
`ConfigHooks().amend_config(config=authored)`, prints `overlay.summary_lines` to stderr,
and consumes `overlay.config` (the effective configuration) for the fields it owns: the
host reads image/dockerfile/proxy/hosts and runs the structural section guards; the
container reads the run parameters (`pipeline.agent` → `write_afm_config`;
`pipeline.env` / `build.env` / `build.review.env` / `build.agent` → settings, guard, and
launch layers). A contribution into the other side's fields stays applied-but-unconsumed,
silently.

**Flow C — the afm configuration authorship.**
The container-side `write_afm_config(effective.pipeline.agent)` resolves the wrapper via
`resolve_wrapper_path` (goga/agents, pure string-building over the
`*-as-claude.sh` convention) and writes the whole `~/.afm/config.yaml`
(`/home/goga/.afm/config.yaml`, fixed, independent of `AFM_DIR`) programmatically:
`client.command` only when an agent resolved, plus the four static fields. The host no
longer generates or mounts any afm config.

**Flow D — the exit codes.**
Host click commands surface failures as `ClickException` (exit 1). In-container
`run_pipeline` returns 1 on config load/delivery failure, missing pipeline, or damaged
payload (all before any checkpoint — no events fire); otherwise it returns `run_flow`'s
code (0 / afm's code / 126 / 127). In-container `main` returns 1 on load/delivery
failure; otherwise `build`'s code (last executed pass, or 1 on pre-launch failures and a
vetoed gate).

### Entity Dependencies

New/changed dependency edges (all downward, verified via `goga schema`):

- `goga/pipeline → goga/docker` (+`decode_extra_env`, +practice `extra-env-carriage`)
- `goga/pipeline → goga/config` (+`load_project_config`, +practice `project-configuration`)
- `goga/pipeline → goga/config/hooks` (`ConfigHooks`, `ConfigOverlay` — types-only)
- `goga/pipeline → goga/agents` (+`resolve_wrapper_path`, +practice `resolve-wrapper-path`)
- `goga/build → goga/config/hooks` (`ConfigHooks`, `ConfigOverlay` — types-only)
- `goga/build → goga/docker` (+`decode_extra_env`, +practice `extra-env-carriage`)
- `goga/commands/pipeline → goga/docker` (+`encode_extra_env`, +practice `extra-env-carriage`)
- `goga/commands/build → goga/docker` (+`encode_extra_env`, +practice `extra-env-carriage`)
- REMOVED: `goga/commands/pipeline → goga/agents` (`resolve_wrapper_path`)

Design order (bottom-up, already satisfied by the materialized contracts):
`goga/docker` → `goga/afm` → `goga/config/hooks`/`goga/config`/`goga/agents` →
`goga/pipeline` / `goga/build` → `goga/commands/*`.

---

## Code Stack Trace

### Trace: `encode_extra_env` (goga/docker — new)

#### Chain
1. **Input**: called by the host launchers with the raw `-e/--env` click values, e.g.
   `["KEY=V", "TOKEN=a=b", "BROKEN", "KEY=W"]`.
2. **Step**: split every entry at the FIRST `=` (`str.partition("=")`); an entry without
   a separator (`"BROKEN"`) is skipped silently → no validation, no warning.
   → checkpoint: pass — the contract forbids validation; malformed input travels as it
   arrived.
3. **Step**: repeated keys resolve last-wins (`KEY` → `"W"`) — the same rule the
   env-file applies (docker last-write-wins).
   → checkpoint: pass — matches "Keep the later entry when a key repeats".
4. **Step**: serialize the resolved mapping as compact JSON
   (`json.dumps(mapping, separators=(",", ":"), sort_keys=True)`, UTF-8), then standard
   base64 WITH padding, single line (`base64.b64encode(...).decode("ascii")`).
   → checkpoint: pass — deterministic; decodes back to exactly the resolved mapping.
5. **Output**: `str` — the `GOGA_EXTRA_ENV` payload value. Pure: no filesystem access,
   no environment reads, no side effects, nothing printed.

#### Checkpoint Summary
- separator semantics (first `=`, values may contain `=`): passed
- silent skip of separator-less entries: passed
- last-wins: passed
- determinism (identical entries ⇒ identical value): passed
- purity: passed

### Trace: `decode_extra_env` (goga/docker — new)

#### Chain
1. **Input**: `os.environ.get("GOGA_EXTRA_ENV", "")` from the calling domain — an empty
   string when the variable is absent (older images, or a launch that wrote no CLI
   lines) or set to the empty-mapping payload.
2. **Step**: empty `value` → return `{}` immediately.
   → checkpoint: pass — "an absent or empty variable arrives as an empty string".
3. **Step**: `base64.b64decode(value, validate=True)` then `json.loads`. Any failure —
   non-alphabet characters, wrong padding, non-JSON, non-UTF-8 — raises one clean
   `ValueError` naming the engine variable: `"GOGA_EXTRA_ENV: invalid payload"`. The
   message carries NO payload content.
   → checkpoint: pass — `binascii.Error` and `json.JSONDecodeError` are both
   `ValueError` subclasses; a single except arm suffices.
4. **Step**: the parsed document must be a JSON object whose every key and value is a
   string; anything else raises the same clean `ValueError`.
   → checkpoint: pass — "or carries a non-string value, raises one clean error naming
   the engine variable".
5. **Output**: `dict[str, str]` — the CLI environment mapping (possibly `{}`). Pure:
   nothing applied anywhere, nothing printed or logged.

#### Checkpoint Summary
- empty-string fast path: passed
- damaged base64/JSON → one clean error, variable named, no content leaked: passed
- non-string value → same clean error: passed
- round-trip equality with `encode_extra_env`: passed (`decode(encode(x)) == resolved(x)`)
- purity (no environ read, no application, no print): passed

### Trace: `write_afm_config` (goga/pipeline — new)

#### Chain
1. **Input**: `run_pipeline` step 14 passes `config.pipeline.agent` of the EFFECTIVE
   configuration (`str | None`).
2. **Step**: when `agent is not None`, resolve the wrapper via
   `resolve_wrapper_path(agent)` (goga/agents — pure: `"/home/goga/bin/" + agent +
   "-as-claude.sh"`); when `None`, skip — no wrapper is resolved.
   → checkpoint: pass — the guard lives in the caller (`if agent is not None`); the
   routine never passes `None` into `resolve_wrapper_path` (its signature takes `str`).
3. **Step**: compose the content programmatically as a dict:
   `client: {command: <resolved wrapper>}` ONLY when an agent resolved (omitted
   otherwise — per-stage workflow agents or afm's own defaults cover the absent global
   default), plus the four static fields `theme: goga`, `open_browser: False`,
   `proxy: {enabled: False}`, `prompts_dir: /home/goga/pipeline/prompts`.
   → checkpoint: pass — the four fields are constants, never configurable; the value
   `"/home/goga/pipeline/prompts"` is a fixed literal (derived from the known
   `AFM_DIR=/home/goga/pipeline` constant of the afm integration), not an argument.
4. **Step**: serialize with `yaml.safe_dump` (programmatic — never a hand-escaped
   string), ensure the parent directory exists (idempotent `mkdir(parents=True,
   exist_ok=True)` — `~/.afm/` is not guaranteed to pre-exist; the old flow created it
   implicitly via the tmpfile mount), and write the whole file at the FIXED path
   `/home/goga/.afm/config.yaml`.
   → checkpoint: pass — the path is independent of `AFM_DIR` (afm always reads
   `~/.afm/config.yaml`); whole-file rewrite ⇒ a repeated invocation stays safe.
5. **Output**: the written `Path` (`/home/goga/.afm/config.yaml`). Nothing is printed.

#### Checkpoint Summary
- agent `None` ⇒ `client` block omitted (not `client.command: null`): passed
- bare agent name never written — always the resolved absolute wrapper path: passed
- fixed home path, independent of `AFM_DIR` and of the afm state directory: passed
- programmatic serialization (YAML nesting for `client`/`proxy` maps): passed
- prompts directory not created/managed here (run coordination materializes it): passed

### Trace: `run_flow` (goga/afm — changed)

#### Chain
1. **Input**: `run_pipeline` step 19 passes `(flow_path, port, max_parallel=parallel,
   env=launch_layer)` where `launch_layer` is the composed dict (possibly empty).
2. **Step**: assemble `cmd = ["afm", "run", "--port", str(port)]` (+ `--max-parallel`
   only when `max_parallel is not None`) + the absolute `flow_path` — unchanged.
3. **Step**: when `env` is truthy, launch with `subprocess.run(cmd, check=False,
   env={**os.environ, **env})`; when `env` is None/empty, launch with pure inheritance
   (no `env` kwarg).
   → checkpoint: pass — the exact pattern `goga/ralphex.run_ralphex` already
   implements; the layer applies to this subprocess only; the caller's `os.environ` is
   untouched; nothing from the layer reaches the argv, the logs, or any output.
4. **Step**: `FileNotFoundError` → stderr message + return 127; other `OSError` —
   or an environment layer rejected by the exec (`ValueError`, e.g. an illegal
   variable name in a config-authored `pipeline.env` key) → stderr message +
   return 126 — the unchanged classes plus the `ValueError` arm `run_ralphex`
   already carries. Error messages never include env values.
5. **Output**: afm's exit code, propagated unchanged.

#### Checkpoint Summary
- None/{} both mean pure inheritance: passed
- layer never applied to the caller's environment: passed
- secret-safety (no layer value printed/logged, including on the 126/127 paths): passed
- 126/127/None-omission semantics preserved for existing callers: passed

### Trace: `run_pipeline` (goga/pipeline — changed)

#### Chain
1. **Input**: the in-container CLI (`goga/pipeline/cli.py` run form, `--info` absent)
   calls `run_pipeline(name, project_dir, user_dir, port, workflow, no_workflow, skip,
   parallel)`. The container CWD is `/workspace` (the project bind-mount), so
   `load_project_config()` reads the project's `.goga/config.yml`.
2. **Step (1)**: `authored = load_project_config()`. On failure — `FileNotFoundError`,
   `OSError`, `KeyError`, `ValueError`, `yaml.YAMLError` (the loader's declared error
   modes) — print one clean error to stderr and `return 1` BEFORE any work; no events
   fire.
   → checkpoint: pass — the CODEMANIFEST requires "a load failure returns with a clean
   error before any work; no events fire"; the exception set mirrors the host command's
   handling.
3. **Step (2)**: `overlay = ConfigHooks().amend_config(config=authored)`. On failure —
   `ValueError` (a failing tool's hard action) or `ImportError` (a broken tool facade) —
   print one clean error naming the tool and the action, `return 1`; no events fire,
   afm never launches. Then print `overlay.summary_lines` to stderr (nothing when
   empty) and fix `config = overlay.config` — every downstream step consumes the
   effective configuration.
   → checkpoint: pass — one load, one delivery, one effective configuration
   (Constraint: no other load path).
4. **Steps (3–13)**: discovery (`list_pipelines` + match; missing → report + return 1,
   no events), `AFM_DIR` read + resolve (unset → `RuntimeError("AFM_DIR not set")`),
   flow path, `resolve_workflow`, `apply_skip_stages`, amendment facts, `amend_workflow`
   delivery, `compile_flow`, `_materialize_prompts` — all unchanged from the current
   implementation.
   → checkpoint: pass — the load-and-amend insertion changes none of the existing
   orderings; `run_created` still fires after compilation and prompt materialization.
5. **Step (14)**: `write_afm_config(config.pipeline.agent)` — the whole file at the
   fixed home path, BEFORE the launch. The pipeline section is guaranteed present: the
   host structural guard already rejected a section-less authored file, and amendments
   only set/force fields (they cannot remove a section).
   → checkpoint: pass — contract interaction verified: no in-container pipeline-section
   guard is specified, and none is needed under these invariants.
6. **Steps (15–16)**: composition (`order_stages`) and work statuses — unchanged.
7. **Step (17)**: `payload = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))`;
   a damaged payload (`ValueError`) → one clean error to stderr, `return 1` BEFORE the
   run-creation facts — no events fire, afm never launches. Then
   `launch_layer = {k: v for k, v in {**config.pipeline.env, **payload}.items() if k not
   in _ENGINE_ENV_KEYS}` — the CLI entries win on key conflict; engine-variable keys
   are dropped silently.
   → checkpoint: type flow verified — `config.pipeline.env: dict[str, str]`,
   `payload: dict[str, str]`, `launch_layer: dict[str, str]` feeds `run_flow`'s
   `env: dict[str, str] | None`. Empty layer (`{}`) is passed as-is (`run_flow` treats
   it as pure inheritance) — the inherited launch environment already carries the same
   CLI values via the env-file lines.
8. **Step (18)**: `emit_run_created` — now AFTER the afm configuration write and after
   the layer composition (a damaged payload returns before it).
9. **Step (19)**: `exit_code = run_flow(flow_path, port, max_parallel=parallel,
   env=launch_layer)`.
10. **Steps (20–21)**: statuses recomputed, `emit_run_completed` on every return path,
    `return exit_code` — unchanged.

#### Checkpoint Summary
- load failure → clean error, exit 1, no events: passed
- delivery failure → clean error naming tool+action, exit 1, no events, afm never
  launches: passed
- summary lines to stderr, nothing when empty, no values: passed
- effective agent reaches `write_afm_config` after prompts, before `run_created`: passed
- damaged payload → clean error before `run_created`: passed
- layer composition order (task env < CLI, engine keys dropped) and type flow: passed
- exactly two environment reads (`AFM_DIR`, `GOGA_EXTRA_ENV`): passed
- docker-level fields (image, proxy, hosts) of the effective config consumed nowhere
  in-container — applied-but-unconsumed, silently: passed
- every pre-existing return path (missing pipeline 1, structural errors, 126/127)
  preserved: passed

### Trace: `main` (goga/build/__main__.py — changed)

#### Chain
1. **Input**: `python -m goga.build PLAN [--flags]` inside the container; container CWD
   `/workspace`.
2. **Step (0)**: `ensure_in_docker()` — the very first statement (unchanged).
3. **Step (1)**: argparse — unchanged (`--skip-review`/`--no-skip-review` tri-state,
   `--base-ref`, `--dry-run`, `--skip-manifest-check`, `--session-timeout`,
   `--idle-timeout`, `--wait`, `--max-iterations`, `--review-patience`).
4. **Step (2)**: `authored = load_project_config()`; a load failure → one clean error
   to stderr, `return 1` — ralphex never launches.
5. **Step (3)**: `overlay = ConfigHooks().amend_config(config=authored)`; a failing
   tool (`ValueError`) or a broken facade (`ImportError`) → one clean error naming the
   tool and the action, `return 1` — ralphex never launches.
   → checkpoint: pass — mirrors the host command's exception wrapping; the entrypoint
   converts to a clean return, not a traceback.
6. **Step (4)**: print `overlay.summary_lines` to stderr (nothing when empty; no
   configuration value appears).
7. **Step (5)**: build `cli_options` from the parsed args — unchanged.
8. **Step (6)**: `return build(args.plan, overlay.config, cli_options)` — the effective
   configuration, never the authored one.
9. **Output**: the process exit code (0 success / 1 failure).

#### Checkpoint Summary
- exactly one load and one delivery: passed
- effective (not authored) configuration forwarded: passed
- both failure modes exit 1 before ralphex: passed
- summary lines carry tool/path/set-or-forced only: passed

### Trace: `build` (goga/build/build.py — changed)

#### Chain
1. **Input**: `main` passes `(plan, overlay.config, cli_options)`.
2. **Steps (0–2)**: uncommitted-CODEMANIFEST pre-check (skip via flag; failure → 1, no
   events), `resolve_run_settings` (inheritance + CLI precedence), and
   `validate_review_config` — unchanged.
3. **Step (3 — MOVED)**: the agent value guard: `if settings.tasks.agent is None:` →
   one clean error naming the missing agent requirement ("no build agent resolved" +
   the remedy hint), `return 1`, no events, NOTHING WRITTEN — the guard now runs BEFORE
   `sync_ralphex_defaults`, so a rejected run never starts the `.ralphex/` rewrite.
   → checkpoint: pass — "the agent value guard runs before the first state write"; an
   amendment supplying `build.agent` satisfies it because `settings` resolve from the
   effective configuration.
4. **Step (4)**: `sync_ralphex_defaults` — unchanged (now unconditionally after the
   guard).
5. **Step (5 — NEW)**: `cli_entries = decode_extra_env(os.environ.get(
   "GOGA_EXTRA_ENV", ""))`; a damaged payload → one clean error, `return 1`, no events,
   no pass launches, nothing partially applied.
6. **Steps (6–8)**: work identity, stage facts, `validate_build` gate (veto → merged
   error, exit 1), `build_started` — unchanged.
7. **Step (9 — CHANGED)**: tasks pass — `env_layer = _compose_pass_env(
   settings.tasks.env, cli_entries)` (task env ⊕ CLI entries, engine keys dropped;
   `None` when empty) → `run_build_pass(..., env=env_layer)` → `run_ralphex(env=...)`.
8. **Step (10 — CHANGED)**: review pass (when the tasks pass succeeded and review is
   not skipped) — the SAME `cli_entries` above `settings.review.env`, engine keys
   dropped. The task env still never reaches the review pass.
9. **Steps (11–14)**: relocation, statuses recompute, `build_completed`, exit code —
   unchanged.

#### Checkpoint Summary
- guard order (before the first state write): passed — the only ordering change inside
  the pre-launch sequence
- one decode feeding both passes: passed
- payload wins over the task env layer on key conflict, in both passes: passed
- engine keys never enter a composed layer: passed
- empty composed layer → pure inheritance (`None`): passed
- dry-run prints pass commands without env layers (secret-safe): passed
- every pre-launch failure (steps 0–5) fires no events: passed

### Trace: `build` host command (goga/commands/build/build.py — changed)

#### Chain
1. **Input**: `goga build PLAN [flags]` on the host; click supplies `extra_env:
   tuple[str, ...]` from the repeatable `-e/--env`.
2. **Steps (1–2)**: docker availability check, `load_home_config` — unchanged.
3. **Step (2)**: `load_project_config()` + `ConfigHooks().amend_config()` +
   summary-to-stderr + `config = overlay.config` — unchanged (already implemented).
4. **Step (2.1 — KEPT)**: structural guard — `config.build is None` →
   `ClickException("build section is required in .goga/config.yml to run 'goga build'")`
   on the host-effective configuration.
5. **Step (2.2 — REMOVED)**: the host agent value guard is deleted. A run whose
   authored agent is unset proceeds to the container, where the effective (possibly
   amended) agent is guarded.
6. **Steps (3–6)**: cli_flags, proxy resolution (CLI > `config.build.proxy`), hosts
   merge (CLI > `config.build.hosts`), image guard — unchanged.
7. **Step (7 — CHANGED)**: assemble the env-file in the ladder order:
   `{**home.env, **git_env}` lines → the raw `extra_env` lines verbatim → the engine
   lines (the proxy triple `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1`
   when a proxy resolved, each SKIPPED when the CLI explicitly supplied that key) →
   the payload line `GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}`. The task env
   (`build.env`) is NOT written into the env-file.
   → checkpoint: pass — the CLI lines and the payload compose from the same tuple
   (one source); the engine lines after the CLI lines; the skip rule preserves the
   documented `-e HTTP_PROXY=...`/`-e AFM_DOCKER_FILE_ROOTS=...` escape hatch under
   docker's last-write-wins.
8. **Steps (9–13)**: signal handlers BEFORE the env-file write, runtime dir + `--clean`,
   container name, docker-run inputs (mounts `/workspace` + `/workspace/.ralphex`,
   `--add-host`, `--env-file`), dry-run exit, first-run safety net, `--update` —
   unchanged (step numbers shift down by one; update in-code step references).
9. **Step (17–18)**: `DockerRunner(...).run(args, extra_args=home.docker.run,
   **params)`; `finally` unlinks the env-file, removes the project-dir `.ralphex/`
   mount point, restores the handlers — unchanged.

#### Checkpoint Summary
- guard split (structural host-side, value in-container): passed
- env-file ladder order + engine-line skip rule + payload line: passed
- payload and CLI lines from the same parsed values: passed
- task env stays out of the env-file: passed
- leak-prevention invariant (handlers before the secret file; unlink in finally):
  passed — the env-file remains the only secret artifact

### Trace: `run_pipeline_container` (goga/commands/pipeline — changed)

#### Chain
1. **Input**: the `pipeline` click command passes `(name, config=host-effective
   ProjectConfig, extra_env, proxy, hosts, clean, update, workflow, no_workflow, skip,
   parallel)` after its own load-and-amend and the missing-pipeline-section guard.
2. **Steps (1–4)**: docker check (caller), home config (caller), image guard, port
   allocation, container name — unchanged.
3. **Step (5 — CHANGED)**: `runtime_dir = resolve_pipeline_runtime_dir(name)`; mkdir;
   `--clean` wipe — moved strictly BEFORE the signal handlers and any temp file (no
   secret exists yet; unchanged behavior, renumbered step).
4. **Step (7 — CHANGED)**: install the SIGTERM/SIGINT handlers BEFORE creating the
   env-file — the leak-prevention invariant now covers exactly one secret artifact.
5. **Step (10 — CHANGED)**: `_build_env_file`: base dict `{**home.env, **git_env}` →
   raw `extra_env` lines verbatim → engine lines `AFM_DIR=/home/goga/pipeline`,
   `AFM_DOCKER_FILE_ROOTS=encode_file_roots(collect_file_roots(home.docker.run))`, the
   proxy triple when `proxy` is non-None — each engine line SKIPPED when the CLI
   explicitly supplied that key (the documented `-e AFM_DOCKER_FILE_ROOTS=...`
   escape hatch keeps winning) — → the payload line
   `GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}`. `config.pipeline.env` is NO
   LONGER written into the env-file; `config.pipeline.agent` is no longer read.
   → checkpoint: type flow — `encode_extra_env` receives the same tuple whose lines
   are written above; `config` is consumed for image/dockerfile only (proxy/hosts are
   resolved by the caller from host-owned fields).
6. **Step (11 — CHANGED)**: mounts = the project at `/workspace` + the persistent afm
   state dir read-write at `/home/goga/pipeline`. NO tmpfile mount (the whole
   `config.yaml` is authored in-container).
7. **Steps (12–14)**: `_compose_run_args` (unchanged), `docker_build_if_not_exist`,
   `--update` → `docker_update`, `DockerRunner(...).run(...)` — unchanged.
8. **Step (15 — CHANGED)**: `finally` deletes ONLY the env-file and restores the
   handlers; the persistent dir survives.
9. **Output**: the container's exit code.

#### Checkpoint Summary
- tmpfile flow fully retired (no write, no mount, no unlink): passed
- no agent resolution on the host; no `goga/agents` import remains: passed
- `pipeline.env` absent from the env-file; payload line present on every run launch:
  passed
- engine-line skip rule + ladder order: passed
- mounts reduced to project + afm state: passed
- signal/leak invariant over the single secret file: passed
- info forms untouched (minimal read-only shape already has no tmpfile/env-file):
  passed

### Trace: `PipelineConfig` property annotations (goga/config/project — changed)

#### Chain
1. **Input**: `.goga/config.yml` `pipeline:` section → `_parse_pipeline` → the frozen
   dataclass (`agent: str | None`, `env: dict`, `proxy`, `hosts`) — loader unchanged.
2. **Step**: only the dataclass DOCSTRINGS/annotation text change (implementation
   docstrings in `goga/config/project/config.py`): `agent` is "resolved at runtime by
   the in-container consumer (goga/pipeline) into an absolute wrapper path written
   into the afm configuration file; this cell does no resolution or validation";
   `env` is "applied in-container as the afm launch env layer, above the inherited
   launch environment; it never travels through the docker launch env-file".
   → checkpoint: pass — the current docstring ("`goga pipeline` raises a clean
   ClickException when it needs an agent") describes the retired host guard and must
   be replaced. Design-review fix: the same stale sentence also lived in the
   CODEMANIFEST Requirements of `load_project_config` and `PipelineConfig` — both
   bullets now state the in-container consumer instead (no host guard); `goga lint`
   re-verified at 83 cells / 0 errors.
3. **Output**: no behavioral change; the cell remains a leaf.

#### Checkpoint Summary
- contract text ↔ implementation docstring alignment: passed (one docstring update
  required, listed in the file registry)

---

## Algorithm Design

### `encode_extra_env`

**Responsibility**: turn the raw CLI environment entries into the single-line engine
payload value carried across the docker boundary.

**Algorithm:**
```
1. resolved = {} (insertion-ordered)
2. FOR each pair in entries:
     key, sep, value = pair.partition("=")
     IF sep == "": continue            # no separator — skipped silently
     resolved[key] = value             # later entry wins on repeat
3. payload = json.dumps(resolved, separators=(",", ":"), sort_keys=True)
4. RETURN base64.b64encode(payload.encode("utf-8")).decode("ascii")
```

**Errors:**
- none — malformed input travels as it arrived; the routine neither fails nor warns.

**Edge Cases:**
- `entries == []` → `base64("{}")` (the empty-mapping payload; decode returns `{}`).
- value containing `=` (`"KEY=A=B"` → `{"KEY": "A=B"}`) — split at the first separator.
- empty key (`"=V"` → `{"": "V"}`) — no validation, travels as-is.

### `decode_extra_env`

**Responsibility**: turn the engine payload value back into the CLI environment mapping
a domain launch applies above its task env layer.

**Algorithm:**
```
1. IF value == "": RETURN {}
2. TRY payload = json.loads(base64.b64decode(value, validate=True))
   EXCEPT (ValueError, binascii.Error): RAISE ValueError(f"{EXTRA_ENV_VARIABLE}: invalid payload")
     # binascii.Error IS a ValueError subclass; json.JSONDecodeError IS a ValueError
     # subclass — a single `except ValueError` arm covers both
3. IF not isinstance(payload, dict) OR any key/value is not a str:
     RAISE ValueError(f"{EXTRA_ENV_VARIABLE}: invalid payload")
4. RETURN dict(payload)
```

Module constant (private): `_EXTRA_ENV_VARIABLE = "GOGA_EXTRA_ENV"` — the name used in
the error message. Consumers read the environment with the literal per the
`extra-env-carriage` practice; only the two declared routines are exported.

**Errors:**
- `ValueError("GOGA_EXTRA_ENV: invalid payload")` → the consumer converts to its clean
  error path: `run_pipeline` returns 1 before `run_created`; `build` returns 1 before
  the gate — no events fire, the target binary never launches. No payload content ever
  appears in the error or any diagnostic.

**Edge Cases:**
- empty/absent variable → `{}` (nothing to apply).
- `validate=True` rejects non-alphabet characters and wrong padding rather than
  silently decoding garbage.
- round-trip: `decode_extra_env(encode_extra_env(x))` equals the resolved mapping of
  `x`.

### `write_afm_config`

**Responsibility**: write the whole afm configuration file in-container before the afm
launch — the agent client command plus the four static launcher-side fields.

**Algorithm:**
```
1. wrapper = resolve_wrapper_path(agent) IF agent is not None ELSE None
2. content = {
     "theme": "goga",
     "open_browser": False,
     "proxy": {"enabled": False},
     "prompts_dir": "/home/goga/pipeline/prompts",
   }
   IF wrapper is not None: content["client"] = {"command": wrapper}
   # insertion order fixes the serialized field order: client (when present),
   # theme, open_browser, proxy, prompts_dir — same order the retired tmpfile wrote
3. _AFM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)   # ~/.afm/ may not exist
4. _AFM_CONFIG_PATH.write_text(yaml.safe_dump(content, default_flow_style=False))
5. RETURN _AFM_CONFIG_PATH     # Path("/home/goga/.afm/config.yaml")
```

Module constants (private): `_AFM_CONFIG_PATH = Path("/home/goga/.afm/config.yaml")`,
`_PROMPTS_DIR = "/home/goga/pipeline/prompts"`.

**Errors:**
- `OSError` ( unwritable home) → propagates to `run_pipeline`'s caller as the run's
  failure (step 14 precedes `run_created`, so no events have fired — the structural
  error semantics of steps 3–13 apply unchanged).

**Edge Cases:**
- `agent is None` → the `client` block is omitted entirely (never a null command), so
  per-stage workflow agents or afm's own defaults cover the absent global default.
- repeated invocation → the whole file is rewritten; idempotent.
- the path never depends on `AFM_DIR` and never lands in the project directory or the
  afm state directory.

### `run_flow` (changed)

**Responsibility**: unchanged — thin subprocess-only wrapper for `afm run`; now also
applies the caller-composed env layer.

**Algorithm:**
```
1. cmd = ["afm", "run", "--port", str(port)]
2. IF max_parallel is not None: cmd += ["--max-parallel", str(max_parallel)]
3. cmd.append(str(flow_path))
4. TRY:
     IF env: result = subprocess.run(cmd, check=False, env={**os.environ, **env})
     ELSE:   result = subprocess.run(cmd, check=False)          # pure inheritance
     RETURN result.returncode
   EXCEPT FileNotFoundError: print clean message; RETURN 127
   EXCEPT (OSError, ValueError): print clean message; RETURN 126
     # the ValueError arm mirrors run_ralphex: an env-layer key that is not a
     # legal variable name (e.g. a config-authored pipeline.env key "A=B") is
     # rejected by the exec before the launch
```

**Errors:** 127/126 semantics unchanged (126 now also covers a rejected
environment layer — `ValueError`); no env value appears in any message.

**Edge Cases:** `env=None` and `env={}` are both pure inheritance — existing callers
are unaffected (backward compatible).

### `run_pipeline` (changed)

**Responsibility**: the in-container run coordination — now opening with the
configuration load-and-amend and owning the afm configuration authorship and the launch
environment composition.

**Algorithm (the 21 contract steps; deltas from the current implementation marked):**
```
 1. NEW  authored = load_project_config(); on (FileNotFoundError, OSError, KeyError,
        ValueError, yaml.YAMLError) → stderr line, RETURN 1 (no events)
 2. NEW  TRY overlay = ConfigHooks().amend_config(config=authored)
        EXCEPT (ValueError, ImportError) → stderr line, RETURN 1 (no events)
        print overlay.summary_lines to stderr; config = overlay.config
 3–13.  UNCHANGED: discovery (missing → RETURN 1), AFM_DIR read/resolve, flow path,
        resolve_workflow, apply_skip_stages, amendment facts, amend_workflow delivery,
        compile_flow, _materialize_prompts (exactly four files)
14. NEW  write_afm_config(config.pipeline.agent)
15–16.  UNCHANGED: composition via order_stages; work statuses
17. NEW  payload = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))
        on ValueError → stderr line, RETURN 1 (before run_created; no events)
        launch_layer = {k: v for k, v in {**config.pipeline.env, **payload}.items()
                        if k not in _ENGINE_ENV_KEYS}
18.      hooks.emit_run_created(...)            # now after steps 14 and 17
19. CHG  exit_code = run_flow(flow_path, port, max_parallel=parallel, env=launch_layer)
20–21.  UNCHANGED: statuses recompute, emit_run_completed, RETURN exit_code
```

New module constant (private, per the `extra-env-carriage` practice):
`_ENGINE_ENV_KEYS = frozenset({"AFM_DIR", "AFM_DOCKER_FILE_ROOTS", "HTTP_PROXY",
"HTTPS_PROXY", "NO_PROXY"})`. The same five keys, verbatim, in `goga/build/build.py`.

Import additions: `from ..config import load_project_config` (extend the existing
`from ..config import resolve_project_name`), `from ..config.hooks import ConfigHooks`,
`from ..docker import decode_extra_env`, `from .afm_config import write_afm_config`.
`yaml` is already imported? — NO: add `import yaml` (the load's error set includes
`yaml.YAMLError`).

**Errors:**
- config load failure → clean stderr error, exit 1, no events (before everything).
- delivery failure (`ValueError` names the tool and the action; `ImportError` names the
  broken facade) → clean stderr error, exit 1, no events.
- damaged payload → clean stderr error, exit 1, before `run_created`, afm never
  launches.
- all pre-existing error paths unchanged (missing pipeline 1; `AFM_DIR not set`;
  `WorkflowSyntaxError`/`StructuralError` propagation; 126/127 passthrough).

**Edge Cases:**
- empty payload (`GOGA_EXTRA_ENV` absent or empty-mapping) → layer is the effective
  `pipeline.env` minus engine keys alone.
- empty composed layer → passed as `{}` → `run_flow` inherits purely (the same CLI
  values already sit in the inherited environment via the env-file lines).
- docker-level fields (image, proxy, hosts) of the effective configuration are read
  nowhere — applied-but-unconsumed, silently, no warning.
- a `pipeline` section absent cannot reach this code (host structural guard) and
  amendments cannot remove it — no in-container section guard is added.

### `main` (goga/build/__main__.py — changed)

**Responsibility**: the in-container entrypoint — parse, load-and-amend, delegate.

**Algorithm:**
```
0. ensure_in_docker()                       # the very first statement
1. args = parser.parse_args()               # unchanged flag surface
2. TRY authored = load_project_config()
   EXCEPT (FileNotFoundError, OSError, KeyError, ValueError, yaml.YAMLError):
     stderr line; RETURN 1
3. TRY overlay = ConfigHooks().amend_config(config=authored)
   EXCEPT (ValueError, ImportError): stderr line; RETURN 1
4. print overlay.summary_lines to stderr
5. cli_options = {...}                      # unchanged
6. RETURN build(args.plan, overlay.config, cli_options)
```

Import additions: `from ..config.hooks import ConfigHooks`, `import yaml` (error set).

**Errors:** both failure modes are clean stderr errors with exit 1 — ralphex never
launches, `.ralphex/` is never touched.

**Edge Cases:** empty summary (no tool packages installed) → nothing printed, behavior
identical to the authored configuration.

### `build` (goga/build/build.py — changed)

**Responsibility**: the two-pass cycle — now guarding the agent on the effective
configuration before any state write and composing both pass env layers per the ladder.

**Algorithm deltas:**
```
in _prepare_run_settings (steps 1–4):
  a. settings = resolve_run_settings(config.build, cli_options)      # unchanged
  b. validate_review_config(settings) → failure: RETURN None         # unchanged
  c. MOVED  if settings.tasks.agent is None:
              logger.error("no build agent resolved",
                           extra={"remedy": "set build.agent in .goga/config.yml"})
              RETURN None          # BEFORE sync_ralphex_defaults — nothing is written
  d. sync_ralphex_defaults(config.build, settings) → failure: RETURN None  # unchanged

new helper (module-private):
  _ENGINE_ENV_KEYS = frozenset({"AFM_DIR", "AFM_DOCKER_FILE_ROOTS",
                                "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"})
  def _compose_pass_env(task_env: dict[str, str], cli_entries: dict[str, str]):
      merged = {k: v for k, v in {**task_env, **cli_entries}.items()
                if k not in _ENGINE_ENV_KEYS}
      return merged or None            # empty → pure inheritance

in build (step 5, after settings resolve, before the facts):
  TRY cli_entries = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))
  EXCEPT ValueError: logger.error(...); RETURN 1      # no events, no launches

in _launch_pass:
  env_layer = _compose_pass_env(settings.tasks.env if stage == "tasks"
                                else settings.review.env, cli_entries)
  → run_build_pass(..., env=env_layer)                # replaces _stage_env_layer
```

`_stage_env_layer` is deleted (subsumed by `_compose_pass_env`). `cli_entries` threads
from `build` into `_launch_pass` (a parameter — the helper stays pure; no module state).

**Errors:**
- damaged payload → clean error, exit 1, before the gate — no events fire, nothing
  partially applied.
- the agent guard error names the requirement and the remedy; an amendment supplying
  `build.agent` satisfies it (settings resolve from the effective configuration).

**Edge Cases:**
- identical `cli_entries` feed both passes (one decode per run).
- the task env never reaches the review pass (`settings.review.env` only) — the CLI
  entries DO reach both (they are explicit user input, already in the inherited env).
- dry-run: identical event structure, printed commands carry no env layers.

### `resolve_run_settings` (goga/build — changed, documentation-level)

**Responsibility**: unchanged pure settings resolution.

**Algorithm:** unchanged; the no-review-agent `ValueError` (raised inside
`validate_review_config`: `"no review agent resolved: set build.agent or
build.review.agent"`) keeps its message; only its docstring/reachability note is updated
— it is now reachable when neither the authored configuration nor an amendment supplies
a review agent (previously framed as "reachable only on direct in-container
invocation").

### `build` host command (goga/commands/build — changed)

**Responsibility**: the host-side launcher — launch mechanics only; the agent value
guard is gone.

**Algorithm deltas:**
```
REMOVED  step 2.2 (the host `config.build.agent is None` guard) — the effective agent
        may arrive as a container-side amendment; the guard lives in goga/build
KEPT    step 2.1 (the structural `config.build is None` guard, host-effective config)

CHANGED  env-file assembly (_write_env_file restructured):
  lines  = [f"{k}={v}" for k, v in {**home.env, **git_env}.items()]   # base layers
  lines += list(extra_env)                                            # raw CLI, verbatim
  cli_keys = {p.partition("=")[0] for p in extra_env if "=" in p}
  engine = {} (build domain: the proxy triple only, when resolved_proxy is not None)
  engine = {k: v for k, v in engine.items() if k not in cli_keys}     # escape hatch
  lines += [f"{k}={v}" for k, v in engine.items()]
  lines.append(f"GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}")
  → write 0600 tempfile
  NOTE: in-code step comments renumber (old 8–19 → new 7–18)
```

Import additions: `from ...docker import encode_extra_env` (extend the existing import).

**Errors:** unchanged ClickException surface (docker missing, malformed home/config,
build-less config, missing image, fatal image build).

**Edge Cases:**
- `-e HTTP_PROXY=...` — the CLI line stands, the launcher's proxy line is skipped.
- `-e GOGA_EXTRA_ENV=...` — the launcher's payload line (written last) wins under
  docker last-write-wins; no target binary reads `GOGA_EXTRA_ENV`, so the decoded
  entry is inert in the pass layer.
- no `-e` at all — the payload line still carries the empty-mapping value.

### `run_pipeline_container` (goga/commands/pipeline — changed)

**Responsibility**: the host-side run launcher — launch mechanics only; no afm config
authorship, no agent resolution, no run-parameter carriage.

**Algorithm deltas:**
```
REMOVED  `from ...agents import resolve_wrapper_path`
REMOVED  _write_afm_config_tmpfile (the whole helper), its invocation, the tmpfile
         mount entry, the `afm_config` variable, and its finally unlink
KEPT     _IN_CONTAINER_AFM_DIR (the AFM_DIR value and the file-roots mount target)

CHANGED  _build_env_file (drop the pipeline_env parameter):
  base   = {**home_env, **git_env}
  engine = {"AFM_DIR": _IN_CONTAINER_AFM_DIR,
            "AFM_DOCKER_FILE_ROOTS": encode_file_roots(collect_file_roots(tokens))}
  if proxy is not None: engine |= {HTTP_PROXY/HTTPS_PROXY: proxy,
                                   NO_PROXY: "localhost,127.0.0.1"}
  cli_keys = {p.partition("=")[0] for p in extra_env if "=" in p}
  engine   = {k: v for k, v in engine.items() if k not in cli_keys}
  lines = base lines → raw extra_env lines → engine lines →
          f"GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}"
  → write 0600 tempfile (_write_env_file restructured to the line-list form)

REORDERED the runtime-dir mkdir and the --clean wipe run BEFORE the signal handlers
         (no secret file exists yet) — behavior unchanged, matching the renumbered
         contract steps 5–6
CHANGED  mounts = [f"{project_dir}:/workspace", f"{runtime_dir}:{_IN_CONTAINER_AFM_DIR}"]
CHANGED  finally: unlink env_file only; restore both handlers
```

Import additions: `from ...docker import encode_extra_env` (extend the existing
import); remove the `resolve_wrapper_path` import.

**Errors:** unchanged ClickException surface; the leak-prevention invariant now covers
the env-file alone.

**Edge Cases:**
- `-e AFM_DOCKER_FILE_ROOTS=...` — the documented escape hatch keeps winning (the
  engine line is skipped).
- config consumed for `image`/`dockerfile` only; `pipeline.env`/`pipeline.agent` are
  read nowhere on the host.

---

## Cross-cutting Concerns

- **Error handling**: hard-and-symmetric amendment semantics at both delivery moments —
  the first failing tool stops the surface with one clean error naming the tool and the
  action; the target binary (afm / ralphex) never launches. Host surfaces wrap load +
  delivery failures into `ClickException`; in-container surfaces print one stderr line
  and return 1. A damaged `GOGA_EXTRA_ENV` payload is the same class of clean
  pre-launch failure. No events fire on any pre-checkpoint return path (load, delivery,
  missing pipeline, structural errors, damaged payload).
- **Logging**: summary lines of the config delivery go to stderr (host: click err
  channel; container: print to stderr). Env values, layer values, and payload contents
  are NEVER logged or printed — presence travels as names only; error messages carry no
  payload content. `run_pipeline` logs the composed-run debug fact without env data.
- **Validation**: entries validation is deliberately absent on the carriage
  (skip-silently on the encode side; one clean error on the decode side). The agent
  value guard validates the EFFECTIVE configuration in-container before the first
  state write. Structural section guards stay host-side on the host-effective
  configuration.
- **Caching**: none introduced. The afm configuration file is rewritten whole on every
  run (idempotent); the payload is decoded exactly once per process (`run_pipeline`
  step 17; `build` step 5) and threaded to every launch as data.
- **Concurrency**: unchanged — no new shared state; `ConfigHooks` is one per run; the
  pass layers are composed per pass from immutable inputs. Signal handling on the host
  is unchanged (handlers before the secret env-file write; runner handler nesting;
  unlink + handler restore in finally).
- **Secret safety** (cross-cutting invariant of this change): the env layer values, the
  task env, and the payload never appear in argv, logs, dry-run output, events, or
  error messages; the layer travels only through the `env` parameter of
  `run_flow`/`run_ralphex`; the container's `os.environ` is never mutated.

---

## Usages Analysis

### `convention` / `conventions` (`.goga/usages/conventions.md`)
- **What it provides**: development/testing conventions — docstring style, error-handling
  style, intra-package imports.
- **Where used**: every touched cell's global annotations and the new routines
  (`extra_env.py`, `afm_config.py`, changed `run_flow`, `run_pipeline`, `main`, `build`,
  both host launchers).
- **Why chosen**: project-wide code standard.
- **How exactly**: NumPy-style docstrings with Args/Returns/Raises; clean-error prints;
  relative intra-package imports; `from __future__ import annotations`.

### `afm` (`.goga/usages/cooks/afm.md` — changed by this topic)
- **What it provides**: the afm binary contract — CLI shape, PATH resolution, exit
  codes, the `~/.afm/config.yaml` field set, `AFM_DIR`, per-stage `command:` overrides,
  `AFM_DOCKER_FILE_ROOTS`, and now the environment-carriage ladder.
- **Where used**: `goga/afm::run_flow` (invocation + error codes), `goga/pipeline`
  (global annotations, `run_pipeline` steps 14/17, `write_afm_config` — the field set,
  the fixed home path, the per-stage override relationship), `goga/commands/pipeline`
  (env-file carriage, file-roots payload).
- **Why chosen**: the single external-binary integration contract.
- **How exactly**: `afm run --port <p> [--max-parallel <n>] <abs flow path>`; 127/126
  mapping; `config.yaml` fields `client.command` (absolute wrapper path only),
  `theme: goga`, `open_browser: false`, `proxy.enabled: false`,
  `prompts_dir: /home/goga/pipeline/prompts`.

### `checkpoints` (goga/config/hooks/.usages/checkpoints.md — changed)
- **What it provides**: the config checkpoint surface usage — `ConfigHooks().amend_config`,
  `ConfigOverlay.config`/`summary_lines`, the one-action-two-moments rule, field
  ownership, hard failure semantics.
- **Where used**: `run_pipeline` steps 1–2; `goga/build::main` steps 2–4; both host
  commands' step 2 (pre-existing).
- **Why chosen**: the delivery is the same action on both sides of the boundary.
- **How exactly**: authored load → `amend_config(config=...)` → summary lines to stderr
  → every downstream read addresses `overlay.config`; each side consumes only its own
  fields; applied-but-unconsumed contributions stay silent.

### `extra-env-carriage` (goga/docker/.usages/extra-env-carriage.md — NEW)
- **What it provides**: the carriage contract — one source (the parsed CLI values) two
  carriers (raw env-file lines + the `GOGA_EXTRA_ENV` payload); the ladder
  `home.env < git identity < task env layer < CLI -e < engine variables`; the engine-key
  drop set; the container-half application rules.
- **Where used**: `goga/docker` (the zone owning the carriage; both routines annotated),
  `goga/pipeline` (`run_pipeline` step 17), `goga/build` (steps 5/9/10),
  `goga/commands/pipeline` (step 10), `goga/commands/build` (step 7).
- **Why chosen**: the `--env-file` flattens layers; a distinguishable payload is the
  only way the container side can apply the CLI entries ABOVE the task env layer.
- **How exactly**: encode once on the host per launch; decode once in-container; compose
  `task_env ⊕ payload ⊖ ENGINE_KEYS`; pass only through the launch's `env` parameter.

### `project-configuration` (goga/config/.usages/project-configuration.md — now imported by goga/pipeline)
- **What it provides**: the authored load contract of `.goga/config.yml`.
- **Where used**: `run_pipeline` step 1 (NEW), `goga/build::main` step 2 (NEW); the host
  commands (pre-existing).
- **Why chosen**: one loader, one error-mode set, all four load moments identical.
- **How exactly**: `load_project_config()` from the CWD; the declared exception set
  becomes the clean-error boundary.

### `resolve-wrapper-path` (goga/agents/.usages/resolve-wrapper-path.md — now imported by goga/pipeline)
- **What it provides**: the in-container wrapper naming convention
  (`/home/goga/bin/<agent>-as-claude.sh`).
- **Where used**: `write_afm_config` step 1 (NEW); `goga/build` (pre-existing); NO
  LONGER used by `goga/commands/pipeline`.
- **Why chosen**: the agent command must be the absolute wrapper path, never a bare
  name.
- **How exactly**: `resolve_wrapper_path(agent)` — pure string building, no validation.

### `run-flow` (goga/afm/.usages/run-flow.md — changed)
- **What it provides**: the `run_flow` consumer contract incl. the new `env` layer
  parameter ("Environment layer contract" section).
- **Where used**: `run_pipeline` step 19.
- **Why chosen / how**: subprocess-only application of the caller-composed layer; None
  and empty both mean pure inheritance; never composed here, never logged.

### `checkpoints` (goga/pipeline/hooks) and `checkpoints` (goga/build/hooks)
- **What it provides**: the pipeline run-event moments and the build gate/moment
  ordering.
- **Where used**: `run_pipeline` (steps 11/18/20 — ordering shifted by the new steps);
  `build` (steps 7–13).
- **How exactly**: `run_created` now fires after the afm configuration write; the
  build gate after the agent guard and the defaults sync.

### Imported Usages (cross-cell traceability)
- `extra-env-carriage` from `goga/docker` — imported by `goga/pipeline`, `goga/build`,
  `goga/commands/pipeline`, `goga/commands/build` (all four referenced in annotations).
  Path: `goga/docker/.usages/extra-env-carriage.md`.
- `project-configuration` from `goga/config` — imported by `goga/pipeline` (NEW);
  already imported by both command cells. Path: `goga/config/.usages/project-configuration.md`.
- `resolve-wrapper-path` from `goga/agents` — imported by `goga/pipeline` (NEW) and
  `goga/build`; REMOVED from `goga/commands/pipeline`. Path:
  `goga/agents/.usages/resolve-wrapper-path.md`.
- `run-flow` from `goga/afm` — imported by `goga/pipeline`. Path:
  `goga/afm/.usages/run-flow.md`.
- `checkpoints` from `goga/config/hooks` — imported by both command cells (the host
  delivery); the in-container consumers (`goga/pipeline`, `goga/build`) import the
  types only and carry the delivery semantics through their own annotations.

---

## `.usages/` Update

All cell-level `.usages/` files of the affected cells were already updated by the
apply-architecture stage. This design's audit against the (new) CODEMANIFESTs finds
them **current** — no edits required by the implementer. Two optional clarifications
are recorded for a future documentation pass (NOT blockers; the normative rules are
correct in the CODEMANIFESTs and in the named consumer practices):

### Cell: `goga/docker`
- **`extra-env-carriage.md`** → current. The host-half sketch's
  `*engine_variable_lines` comment does not spell out the skip rule ("skip a key the
  CLI explicitly supplied" — the escape-hatch rule that `commands/pipeline`
  CODEMANIFEST step 10 and `pipeline-command.md` state). Optional clarification: add
  the skip clause to the sketch comment.
- Same file: `GOGA_EXTRA_ENV` is named "the dedicated engine variable" in the carriage
  section but is not a member of the five-key drop set of the ladder section. That is
  correct behavior (no target binary reads it; the payload line already wins by
  last-write-wins) — optional clarification: one sentence noting the asymmetry.

### Cell: `goga/pipeline`
- **`run-pipeline.md`**, **`registering-hooks.md`** → current (load-and-amend, afm
  configuration, two environment reads, `run_created` after the config write, the
  config-failure no-events rule all present and contract-matching). Optional
  clarification: `registering-hooks.md`'s "a failing moment fires nothing" list could
  also name the damaged-payload return (the CODEMANIFEST requires it fires before
  `run_created`).

### Cell: `goga/afm`
- **`run-flow.md`** → current (`env` parameter, environment layer contract,
  composition-not-here constraint).

### Cell: `goga/config/hooks` / `goga/config`
- **`checkpoints.md`**, **`registering-hooks.md`** → current (one action, two moments;
  the in-container entrypoints in the firing table). Propagation note: the other
  `checkpoints` consumers (`goga/commands/*`, `goga/usages/status`, `goga/usages/sync`)
  import the same practice — its content change is backward-compatible (the delivery
  surface they already implement is unchanged).

### Cell: `goga/build`
- **`build-usage.md`**, **`registering-hooks.md`** → current (load-and-amend preamble,
  environment ladder, agent guard sections; the gate description now lists the guard
  among the pre-checks).

### Cell: `goga/commands/build`
- **`build.md`** → current (guard split documented; `-e` dual carriage; env-file
  layers).

### Cell: `goga/commands/pipeline`
- **`pipeline-command.md`** → current (environment carriage section; docker shapes
  without the tmpfile; the `-e` threading chain).

### Cell: `goga/config/project`
- No `.usages/` directory — nothing to update.

---

## Test Stack Trace

### General Setup

- pytest, existing per-cell suites; `monkeypatch` for environment and CWD; `tmp_path`
  for filesystem effects; `capsys` for stdout/stderr.
- Existing helpers worth reuse: the `tests/pipeline/conftest.py` pipeline-tree fixtures
  and the `PipelineHooks`/`BuildHooks` fakes used by `test_run_pipeline_hooks.py` /
  `test_build.py`; the env-file readers in `tests/commands/build/test_build.py` and
  `tests/commands/pipeline/test_run_pipeline_container.py`.
- The `_ENGINE_ENV_KEYS` set is asserted through behavior (a key colliding with an
  engine variable is absent from the layer), not by importing the private constant.
- `GOGA_EXTRA_ENV` is always driven via `monkeypatch.setenv/delenv` — never mutated
  globally.

### Source File Registry

Create: `goga/docker/extra_env.py`, `goga/pipeline/afm_config.py`,
`tests/docker/test_extra_env.py`, `tests/pipeline/test_afm_config.py`.

Modify: `goga/docker/__init__.py` (+`encode_extra_env`, `decode_extra_env` exports and
`__all__`), `goga/afm/run_flow.py`, `goga/pipeline/__init__.py` (+`write_afm_config`
export), `goga/pipeline/run_pipeline.py`, `goga/build/__main__.py`,
`goga/build/build.py`, `goga/build/run_settings.py` (docstring only),
`goga/build/review_config.py` (docstring only), `goga/commands/build/build.py`,
`goga/commands/pipeline/run_pipeline_container.py`,
`goga/commands/pipeline/pipeline.py` (agent-optionality comment; no behavioral read of
`pipeline.agent`/`pipeline.env`), `goga/config/project/config.py` (docstrings),
plus the test files below.

Delete: `tests/commands/pipeline/test_run_pipeline_container_afm_config.py`,
`tests/commands/pipeline/test_run_pipeline_container_resolved_wrapper.py` (the retired
host tmpfile/wrapper flows).

Extend: `tests/afm/test_run_flow.py`, `tests/pipeline/test_run_pipeline.py`,
`tests/pipeline/test_run_pipeline_contract.py`, `tests/build/test_main.py`,
`tests/build/test_build.py`, `tests/commands/build/test_build.py`,
`tests/commands/build/test_build_config_checkpoint.py`,
`tests/commands/pipeline/test_run_pipeline_container.py`.

---

### Positive Tests

#### `test_encode_extra_env_roundtrip_resolves_last_wins` (tests/docker/test_extra_env.py)

**Setup**: no fixtures — pure function.

**Input**: `entries = ["KEY=V", "TOKEN=a=b", "KEY=W"]`

**Trace**:
```
encode_extra_env(["KEY=V", "TOKEN=a=b", "KEY=W"])
  → partition each at first "="        # KEY→V (overwritten), TOKEN→a=b, KEY→W
  → resolved = {"KEY": "W", "TOKEN": "a=b"}
  → json.dumps(..., separators=(",",":"), sort_keys=True)
  → base64 standard with padding
decode_extra_env(value)
  → b64decode(validate=True) → json.loads → dict
```

**Assertions**:
```
value is a single line (no "\n"), non-empty, only base64 alphabet chars
decode_extra_env(value) == {"KEY": "W", "TOKEN": "a=b"}
```

**Sufficiency**: locks the carriage core — first-separator split, values containing
`=`, last-wins, and the exact round-trip the two domains depend on.

#### `test_encode_extra_env_deterministic` (tests/docker/test_extra_env.py)

**Setup**: none.

**Input**: `encode_extra_env(["A=1", "B=2"])` called twice; also
`encode_extra_env(["B=2", "A=1"])`.

**Trace**: two independent serializations of the same resolved mapping.

**Assertions**:
```
encode_extra_env(["A=1", "B=2"]) == encode_extra_env(["A=1", "B=2"])
encode_extra_env(["A=1", "B=2"]) == encode_extra_env(["B=2", "A=1"])  # sort_keys
```

**Sufficiency**: the "identical entries produce the identical value" requirement —
repeated launches with unchanged CLI values produce byte-identical env-files.

#### `test_write_afm_config_with_agent_writes_resolved_wrapper_and_static_fields` (tests/pipeline/test_afm_config.py)

**Setup**: monkeypatch the module path constant `_AFM_CONFIG_PATH` to
`tmp_path / ".afm" / "config.yaml"` (the fixed-path constant is patched, not the
filesystem root).

**Input**: `write_afm_config("codex")`

**Trace**:
```
write_afm_config("codex")
  → resolve_wrapper_path("codex") → "/home/goga/bin/codex-as-claude.sh"
  → content = {client:{command:wrapper}, theme:"goga", open_browser:False,
               proxy:{enabled:False}, prompts_dir:"/home/goga/pipeline/prompts"}
  → mkdir parents → yaml.safe_dump → write_text
```

**Assertions**:
```
returned Path == the patched path
yaml.safe_load(path.read_text()) == {"client": {"command": "/home/goga/bin/codex-as-claude.sh"},
                                     "theme": "goga", "open_browser": False,
                                     "proxy": {"enabled": False},
                                     "prompts_dir": "/home/goga/pipeline/prompts"}
"codex" != any bare-name client command — the command value contains "/home/goga/bin/"
```

**Sufficiency**: the afm field-set contract — the exact five fields, the wrapper (never
a bare name), the nested YAML maps.

#### `test_write_afm_config_without_agent_omits_client_block` (tests/pipeline/test_afm_config.py)

**Setup**: same path patch.

**Input**: `write_afm_config(None)`

**Trace**: no wrapper resolution; content lacks the `client` key; file written.

**Assertions**:
```
data = yaml.safe_load(path.read_text())
"client" not in data
set(data) == {"theme", "open_browser", "proxy", "prompts_dir"}
```

**Sufficiency**: the omitted-`client` rule — per-stage workflow agents or afm defaults
cover the absent global default; a null command must never be written.

#### `test_write_afm_config_rewrites_whole_file_idempotently` (tests/pipeline/test_afm_config.py)

**Setup**: path patch; pre-write garbage into the target file
(`path.parent.mkdir(); path.write_text("stale: true\n")`).

**Input**: `write_afm_config("claude")` twice.

**Trace**: whole-file rewrite over the stale content; second write identical.

**Assertions**:
```
first == second == the five-field document; "stale" not in data after each write
```

**Sufficiency**: "the whole file is rewritten on every run — a repeated invocation
stays safe" (state left by an older run never leaks into afm).

#### `test_run_flow_env_layer_applied_to_subprocess_only` (tests/afm/test_run_flow.py)

**Setup**: monkeypatch `subprocess.run` to capture the `env` kwarg and return
`returncode=0`; monkeypatch `os.environ` copy sentinel `SENTINEL="inherited"`.

**Input**: `run_flow(Path("/f.yml"), 8080, env={"KEY": "V"})`

**Trace**:
```
run_flow(..., env={"KEY": "V"})
  → cmd = ["afm","run","--port","8080","/f.yml"]
  → subprocess.run(cmd, check=False, env={**os.environ, **{"KEY":"V"}})
  → os.environ unchanged (assert "KEY" not in os.environ afterwards)
```

**Assertions**:
```
captured env["KEY"] == "V" and env["SENTINEL"] == "inherited"   # layer on top of inherited
"KEY" not in os.environ                                          # caller untouched
cmd == ["afm", "run", "--port", "8080", "/f.yml"]
result == 0
```

**Sufficiency**: the layer applies to the afm subprocess only, on top of the inherited
environment — the core of the in-container env composition.

#### `test_run_flow_none_and_empty_env_are_pure_inheritance` (tests/afm/test_run_flow.py)

**Setup**: capture `subprocess.run` kwargs.

**Input**: `run_flow(Path("/f.yml"), 8080)` then `run_flow(Path("/f.yml"), 8080,
env={})`.

**Trace**: both calls take the no-`env` branch.

**Assertions**:
```
both calls: "env" not in captured kwargs
```

**Sufficiency**: backward compatibility — None and empty mean "inherited unchanged",
so every existing caller and the empty-layer case behave identically.

#### `test_run_pipeline_loads_and_amends_before_any_work` (tests/pipeline/test_run_pipeline.py)

**Setup**: existing run fixture (project pipelines tree with pipeline `deploy`);
monkeypatch `goga.pipeline.run_pipeline.load_project_config` to return an authored
`ProjectConfig` with `pipeline=PipelineConfig(agent="codex", env={"T": "1"})`;
monkeypatch `ConfigHooks.amend_config` to record the call and return a real
`ConfigOverlay` (effective config with `pipeline.agent="opencode"`) whose
`summary_lines == ["config amendments: 1 applied", "- tool set pipeline.agent"]`;
monkeypatch `write_afm_config` and `run_flow` (return 0) to record calls; spy on
`hooks.emit_run_created` via the PipelineHooks fake.

**Input**: `run_pipeline("deploy", project_dir, user_dir, port=9000)`

**Trace**:
```
run_pipeline(...)
  → load_project_config()                    # recorded first
  → ConfigHooks().amend_config(config=authored)   # recorded second, keyword `config=`
  → summary lines printed to stderr
  → discovery/compile/prompts (fixture)
  → write_afm_config("opencode")             # the EFFECTIVE agent
  → emit_run_created(...)
  → run_flow(..., env={"T": "1"})            # effective pipeline.env as the layer
```

**Assertions**:
```
call order: load → amend → write_afm_config → emit_run_created → run_flow
write_afm_config called once with "opencode"
capsys.err contains "config amendments: 1 applied" and "- tool set pipeline.agent"
run_flow kwargs: env == {"T": "1"}, max_parallel is None
return == 0
```

**Sufficiency**: the load-and-amend opens the coordination, the effective agent and
env feed the afm configuration and the launch layer, and the summary reaches stderr —
the headline behavior of the topic for the pipeline domain.

#### `test_run_pipeline_launch_layer_cli_entries_above_task_env_engine_keys_dropped` (tests/pipeline/test_run_pipeline.py)

**Setup**: as above with effective `pipeline.env = {"T": "cfg", "HTTP_PROXY":
"cfg-proxy"}`; `monkeypatch.setenv("GOGA_EXTRA_ENV",
encode_extra_env(["T=cli", "AFM_DIR=x"]))`.

**Input**: `run_pipeline("deploy", ...)` with `run_flow` recorded.

**Trace**:
```
decode_extra_env(payload) → {"T": "cli", "AFM_DIR": "x"}
merged = {"T": "cli", "HTTP_PROXY": "cfg-proxy", "AFM_DIR": "x"}
layer  = merged − {AFM_DIR, HTTP_PROXY, ...} → {"T": "cli"}
run_flow(..., env={"T": "cli"})
```

**Assertions**:
```
run_flow kwargs env == {"T": "cli"}          # CLI wins over config; engine keys absent
os.environ["AFM_DIR"] unchanged by the call  # no process mutation
```

**Sufficiency**: the precedence fix of the whole topic — explicit CLI input beats the
(amended) task env layer, and launch mechanics never get overridden.

#### `test_main_loads_amends_and_forwards_effective_config` (tests/build/test_main.py)

**Setup**: monkeypatch `ensure_in_docker` (no-op), `sys.argv` to
`["goga.build", "plan.md"]`; monkeypatch `load_project_config` (authored, agent None),
`ConfigHooks.amend_config` (effective agent "codex", summary lines), and
`goga.build.__main__.build` to record and return 7.

**Input**: `main()`

**Trace**:
```
main()
  → ensure_in_docker() → argparse → load_project_config()
  → amend_config(config=authored) → summary to stderr
  → build("plan.md", overlay.config, cli_options) → 7
```

**Assertions**:
```
build called exactly once; its config argument IS overlay.config (identity)
build kwargs cli_options["dry_run"] is False, skip_review is None
capsys.err contains the summary line
return == 7
```

**Sufficiency**: the entrypoint hands the orchestration the effective configuration —
never the authored one — and the exit code propagates.

#### `test_build_guard_satisfied_by_amendment_and_runs_both_pass_layers` (tests/build/test_build.py)

**Setup**: the existing `build` test scaffolding; effective config with
`build.agent="codex"`, `build.env={"T":"cfg"}`, `build.review.env={"R":"1"}`;
`monkeypatch.setenv("GOGA_EXTRA_ENV", encode_extra_env(["T=cli"]))`; record
`run_build_pass` (return 0) and `sync_ralphex_defaults`.

**Input**: `build("plan.md", effective_config, {"dry_run": False})`

**Trace**:
```
build(...)
  → settings (tasks.agent="codex") → review-config validation
  → AGENT GUARD passes (effective agent non-None) → sync_ralphex_defaults
  → decode {"T":"cli"} → gate (approved) → build_started
  → tasks pass: run_build_pass(env={"T":"cli"})          # cfg overridden by CLI
  → review pass: run_build_pass(env={"R":"1","T":"cli"}) # same CLI entries above review env
```

**Assertions**:
```
sync_ralphex_defaults called BEFORE the first run_build_pass
run_build_pass calls: [env={"T":"cli"}, env={"R":"1","T":"cli"}]
return == 0
```

**Sufficiency**: one decode feeds both passes; the payload wins over each pass's task
env layer; the guard reads the effective configuration.

#### `test_host_build_no_agent_guard_launches_container_with_payload` (tests/commands/build/test_build.py)

**Setup**: the existing click `CliRunner` scaffolding with docker/config/home fakes
(authored config WITHOUT `build.agent`); record `DockerRunner.run`,
`docker_build_if_not_exist` (no-op), and the env-file content via a fake
`tempfile.mkstemp`/real temp read.

**Input**: `goga build plan.md -e KEY=V -e HTTP_PROXY=user-proxy` (agent unset — the
amendment will supply it in-container).

**Trace**:
```
build command
  → load + amend (no agent field touched) → build-section guard passes
  → NO agent guard (removed)
  → env-file: home.env lines, git lines, "KEY=V", "HTTP_PROXY=user-proxy",
    GOGA_EXTRA_ENV=<payload>            # no engine proxy line — CLI supplied the key
  → DockerRunner.run(["-m","goga.build","plan.md", ...], env_file=...)
```

**Assertions**:
```
result.exit_code == 0 (launch reached; container returns 0)
env-file lines contain "KEY=V" and "HTTP_PROXY=user-proxy"
exactly one HTTP_PROXY line                      # the launcher's own was skipped
decode_extra_env(GOGA_EXTRA_ENV line value) == {"KEY":"V","HTTP_PROXY":"user-proxy"}
"build.agent is required" not in result.output
```

**Sufficiency**: the guard split — an agent-less host config launches; the CLI values
and the payload compose from one source; the engine-line skip rule preserves the
user's explicit proxy.

#### `test_run_pipeline_container_env_file_ladder_and_payload_no_pipeline_env` (tests/commands/pipeline/test_run_pipeline_container.py)

**Setup**: the existing container-launcher scaffolding (docker fakes, home config with
`env={"H":"1"}` and a `-v /data:/data` run token); effective config with
`pipeline.env={"T":"cfg"}`, `pipeline.agent="codex"`; `extra_env=("T=cli",)`;
`proxy="http://p:1"`; capture the env-file.

**Input**: `run_pipeline_container("deploy", config=effective, extra_env=("T=cli",),
proxy="http://p:1")` (docker fakes return 0).

**Trace**:
```
launcher
  → port, runtime dir (mkdir), handlers
  → env-file: "H=1", git lines?, "T=cli", "AFM_DIR=...", "AFM_DOCKER_FILE_ROOTS=...",
    "HTTP_PROXY=http://p:1", "HTTPS_PROXY=http://p:1", "NO_PROXY=localhost,127.0.0.1",
    "GOGA_EXTRA_ENV=<payload of T=cli>"
  → mounts: [project:/workspace, runtime:/home/goga/pipeline]   # no tmpfile mount
  → DockerRunner.run(...)
```

**Assertions**:
```
lines.index("T=cli") < lines.index("AFM_DIR=...")            # CLI before engine
"T=cfg" not in env-file text                                 # pipeline.env never enters
decode_extra_env(payload value) == {"T": "cli"}
no line mounts "<tmpfile>:/home/goga/.afm/config.yaml" among params["v"]
params["v"] == [f"{project}:/workspace", f"{runtime}:/home/goga/pipeline"]
finally: the env-file path is unlinked
```

**Sufficiency**: the host half of the pipeline carriage — ladder order, one-source
payload, task-env exclusion, tmpfile retirement, single secret artifact.

---

### Negative Tests

#### `test_encode_extra_env_silently_skips_separatorless_entries` (tests/docker/test_extra_env.py)

**Setup**: none.

**Input**: `encode_extra_env(["BROKEN", "=V", "KEY=V"])`

**Trace**: `"BROKEN"` has no `=` → skipped; `"=V"` → key `""`; `"KEY=V"` kept.

**Assertions**:
```
decode_extra_env(value) == {"": "V", "KEY": "V"}
no warning/error raised (no pytest.warns)
```

**Sufficiency**: "do not validate or reject entries" — malformed input travels as it
arrived, silently (the encoder never becomes a CLI validator).

#### `test_decode_extra_env_damaged_payload_raises_clean_error_naming_variable` (tests/docker/test_extra_env.py)

**Setup**: none.

**Input**: `["!!!not-base64!!!", "aGVsbG8=", base64 of "[1,2]"]` (valid b64, non-JSON
object), and base64 of `{"K": 1}` (non-string value).

**Trace**: each fails validation at step 2 or 3 → one `ValueError`.

**Assertions**:
```
with pytest.raises(ValueError, match=r"GOGA_EXTRA_ENV: invalid payload"): each call
str(excinfo.value) contains no base64 fragment of the input   # no content leaked
```

**Sufficiency**: the damaged-payload contract — one clean error naming the engine
variable, no payload content in the error, for every damage class (b64, JSON shape,
value type).

#### `test_run_pipeline_config_load_failure_clean_error_no_events` (tests/pipeline/test_run_pipeline.py)

**Setup**: run fixture; `load_project_config` raises
`FileNotFoundError(".goga/config.yml not found in project root")`; PipelineHooks fake
records every emit; `run_flow` recorded.

**Input**: `run_pipeline("deploy", ...)`

**Trace**: step 1 raises → stderr line → return 1 before discovery.

**Assertions**:
```
return == 1
capsys.err contains ".goga/config.yml not found"
emit_run_created == 0 and emit_run_completed == 0     # no events
run_flow not called; write_afm_config not called      # afm never launches
no traceback in output (clean error path)
```

**Sufficiency**: the load-failure firing rule — before any work, no events, clean
message.

#### `test_run_pipeline_config_delivery_failure_clean_error_no_events` (tests/pipeline/test_run_pipeline.py)

**Setup**: as above; `amend_config` raises
`ValueError("toolA/hookX: amend_config failed")`.

**Input**: `run_pipeline("deploy", ...)`

**Trace**: step 2 raises → stderr line naming tool+action → return 1.

**Assertions**:
```
return == 1; capsys.err contains "toolA" and "amend_config"
no events; run_flow/write_afm_config uncalled
```

**Sufficiency**: the hard, symmetric delivery semantics inside the container.

#### `test_run_pipeline_damaged_payload_clean_error_before_run_created` (tests/pipeline/test_run_pipeline.py)

**Setup**: healthy config fixture (load+amend passthrough);
`monkeypatch.setenv("GOGA_EXTRA_ENV", "###garbage###")`; events recorded.

**Input**: `run_pipeline("deploy", ...)`

**Trace**: steps 3–16 run (prompts written), step 17 decode raises → stderr →
return 1 BEFORE step 18.

**Assertions**:
```
return == 1; capsys.err contains "GOGA_EXTRA_ENV"
emit_run_created == 0; run_flow not called
```

**Sufficiency**: the payload damage surfaces after the compile work but before the
run facts — "no events fire, afm never launches".

#### `test_main_config_failure_exit_1_ralphex_never_launches` (tests/build/test_main.py)

**Setup**: argv fixture; `load_project_config` raises `ValueError("bad mapping")`;
`build` recorded.

**Input**: `main()`

**Assertions**:
```
return == 1; capsys.err contains "bad mapping"; build not called
```

**Sufficiency**: the entrypoint's clean-error boundary — ralphex never starts on a
failed load.

#### `test_main_delivery_failure_exit_1_names_tool` (tests/build/test_main.py)

**Setup**: `amend_config` raises `ValueError("toolB: hook failed on amend_config")`.

**Input**: `main()`

**Assertions**:
```
return == 1; capsys.err contains "toolB"; build not called
```

**Sufficiency**: identical hard semantics at the build load moment.

#### `test_build_agent_guard_rejects_before_any_state_write` (tests/build/test_build.py)

**Setup**: effective config with `build.agent=None`; record
`sync_ralphex_defaults`, `BuildHooks` emissions, `run_build_pass`.

**Input**: `build("plan.md", effective_config, {"skip_review": True})` — the
degenerate skip-run the guard exists for: `validate_review_config` returns
early on a skipped review, so with an unskipped review and no review agent the
step-2 validator ("no review agent resolved") would fire first and the guard
would be unreachable.

**Trace**: settings resolve with `tasks.agent=None` → `validate_review_config`
returns early (skipped review) → guard fires at step 3 BEFORE
`sync_ralphex_defaults` → return 1.

**Assertions**:
```
return == 1
sync_ralphex_defaults not called          # .ralphex/ rewrite never starts
emit_build_started == 0; run_build_pass not called
capsys/stderr or log names the agent requirement ("no build agent resolved")
"no review agent resolved" not in output  # the guard fired, not the validator
```

**Sufficiency**: the moved guard — "the .ralphex/ rewrite never starts on a run the
guard rejects" (the ordering change of this topic). The unskipped no-agent-anywhere
scenario is already locked by the existing `validate_review_config` tests (the
"no review agent resolved" error); this test isolates the tasks-agent guard alone.

#### `test_build_damaged_payload_clean_error_no_events_no_launch` (tests/build/test_build.py)

**Setup**: healthy effective config; `monkeypatch.setenv("GOGA_EXTRA_ENV", "zzz")`
(invalid b64); events recorded.

**Input**: `build("plan.md", effective_config, {})`

**Assertions**:
```
return == 1; no gate/build_started/pass events; run_build_pass not called
```

**Sufficiency**: the decode failure is a pre-launch failure — nothing partially
applied.

#### `test_write_afm_config_unwritable_home_raises_oserror` (tests/pipeline/test_afm_config.py)

**Setup**: patch `_AFM_CONFIG_PATH` to `tmp_path / ".afm" / "config.yaml"`; create
the parent and make it read-only (`path.parent.mkdir(parents=True);
path.parent.chmod(0o500)`); restore `0o700` on teardown; skip under root
(`os.getuid() == 0` — chmod does not restrict root, the write would succeed).

**Input**: `write_afm_config("codex")`

**Trace**:
```
write_afm_config("codex")
  → resolve_wrapper_path("codex") → content composed (in memory)
  → mkdir(parents=True, exist_ok=True) succeeds (already present)
  → write_text(...) → PermissionError (an OSError subclass) propagates
```

**Assertions**:
```
pytest.raises(OSError)
the config file does not exist afterwards      # no partial write
nothing printed                                # no partial content on any stream
```

**Sufficiency**: the declared error semantics of the routine — a clean
propagation to `run_pipeline`'s caller (step 14 precedes `run_created`, no
events fired) with no partial write and no content echo.

---

### Edge Case Tests

#### `test_decode_extra_env_empty_value_returns_empty_mapping` (tests/docker/test_extra_env.py)

**Setup**: none.

**Input**: `decode_extra_env("")`

**Assertions**: `result == {}` and no exception.

**Sufficiency**: the absent-variable case (older images / no `-e`) resolves to "nothing
to apply" — never an error.

#### `test_run_flow_illegal_env_key_returns_126` (tests/afm/test_run_flow.py)

**Setup**: monkeypatch `subprocess.run` to raise
`ValueError("illegal environment variable name")` (the exec-side rejection of an
env-layer key containing `=`).

**Input**: `run_flow(Path("/f.yml"), 8080, env={"A=B": "v"})` — the shape a
config-authored `pipeline.env` key could produce (payload keys can never contain
`=`, but the YAML mapping can).

**Trace**:
```
run_flow(..., env={"A=B": "v"})
  → subprocess.run(cmd, env={**os.environ, **{"A=B": "v"}}) raises ValueError
  → the (OSError, ValueError) arm prints one clean message
  → RETURN 126                       # the run_ralphex-parity arm
```

**Assertions**:
```
return == 126
capsys.err contains one clean "Error:" line; no traceback
"A=B" and "v" not in the message          # no layer content leaked
```

**Sufficiency**: the boundary the parity arm exists for — an illegal layer key
surfacing as a clean 126 instead of escaping to the CLI's generic ValueError
handler with the misleading "was not amended" message.

#### `test_run_pipeline_empty_payload_layer_is_effect_task_env_alone` (tests/pipeline/test_run_pipeline.py)

**Setup**: effective `pipeline.env={"T":"1"}`;
`monkeypatch.delenv("GOGA_EXTRA_ENV", raising=False)`.

**Input**: `run_pipeline("deploy", ...)`

**Assertions**: `run_flow` kwargs `env == {"T": "1"}`.

**Sufficiency**: absent `-e` ⇒ the task env layer alone (the documented
"empty-mapping payload ⇒ the task env layer alone" chain).

#### `test_run_pipeline_empty_composed_layer_pure_inheritance` (tests/pipeline/test_run_pipeline.py)

**Setup**: effective `pipeline.env={}`; payload absent; `run_flow` recorded.

**Input**: `run_pipeline("deploy", ...)`

**Assertions**: `run_flow` kwargs `env == {}` and afm still launches (return 0) —
`{}` is pure inheritance inside `run_flow`.

**Sufficiency**: a config with no task env and no CLI entries runs exactly as before
the change (backward compatibility).

#### `test_run_pipeline_docker_level_fields_unconsumed_silently` (tests/pipeline/test_run_pipeline.py)

**Setup**: effective config carrying `image="img"`, `pipeline.proxy="http://x"`,
`pipeline.hosts={"h":"1"}` (set by the amendment fixture); spies assert no docker
module is touched.

**Input**: `run_pipeline("deploy", ...)`

**Assertions**:
```
return == 0; no warning in stderr beyond the summary lines; no attribute read of
config.image/dockerfile by the run coordination (the docker cell is never imported
by run_pipeline beyond decode_extra_env)
```

**Sufficiency**: applied-but-unconsumed — the in-container side neither consumes nor
warns about the host's fields.

#### `test_run_pipeline_container_escape_hatch_cli_engine_key_wins` (tests/commands/pipeline/test_run_pipeline_container.py)

**Setup**: container scaffolding; `extra_env=("AFM_DOCKER_FILE_ROOTS=dXNlcg==",)`.

**Input**: run launch; capture the env-file.

**Assertions**:
```
the env-file contains the CLI line verbatim and NO second launcher-written
AFM_DOCKER_FILE_ROOTS line (exactly one occurrence)
```

**Sufficiency**: the documented `-e AFM_DOCKER_FILE_ROOTS=...` escape hatch survives
the ladder reorder (engine lines skip CLI-supplied keys).

#### `test_run_pipeline_container_payload_line_present_with_no_cli_entries` (tests/commands/pipeline/test_run_pipeline_container.py)

**Setup**: the existing container-launcher scaffolding (docker/config/home fakes);
`extra_env=()`; capture the env-file via the existing env-file reader of the suite.

**Input**: `run_pipeline_container("deploy", config=effective, extra_env=())`
(docker fakes return 0).

**Trace**:
```
launcher
  → env-file: base lines (home.env + git identity), ZERO CLI lines,
    engine lines (AFM_DIR, AFM_DOCKER_FILE_ROOTS), then the LAST line
    GOGA_EXTRA_ENV=e30=            # encode_extra_env([]) → {} → base64("{}")
  → container launched
```

**Assertions**:
```
payload_lines = [l for l in lines if l.startswith("GOGA_EXTRA_ENV=")]
len(payload_lines) == 1                       # written on EVERY launch
decode_extra_env(payload_lines[0].split("=", 1)[1]) == {}
no non-engine KEY=VALUE line present          # extra_env was empty
runner called exactly once                    # the launch proceeded
```

**Sufficiency**: locks the "on every launch" one-source rule — a regression that
skips the payload line when no `-e` is given breaks the carriage silently
(the container-side read resolves the absent variable to `{}` and nothing
fails), so only this boundary test holds the invariant.

#### `test_run_pipeline_container_no_tmpfile_and_agent_not_resolved` (tests/commands/pipeline/test_run_pipeline_container.py)

**Setup**: container scaffolding; the runner params are recorded and the launcher
module object is captured for the import assertion below. Do NOT assert on
`sys.modules` — it is process-global and order-dependent (other suites import
`goga.agents` long before this test); the `dir()` check on the launcher module is
the order-independent form.

**Input**: a run launch with `pipeline.agent="codex"` configured.

**Assertions**:
```
params["v"] has exactly 2 mounts (project + afm state)
no file matching "goga-afm-config-*" exists during/after the run
"resolve_wrapper_path" not in dir(run_pipeline_container_module)   # no agents import
```

**Sufficiency**: the retired host authorship — the container is the only writer of
`config.yaml`.

#### `test_build_host_structural_guard_still_fires` (tests/commands/build/test_build.py)

**Setup**: effective config with `build=None` (section absent).

**Input**: `goga build plan.md`

**Assertions**:
```
ClickException "build section is required in .goga/config.yml to run 'goga build'"
exit_code == 1; DockerRunner.run not called
```

**Sufficiency**: the structural guard stays host-side on the host-effective
configuration — the guard SPLIT, not the guard removal.

#### `test_build_dry_run_prints_commands_without_env_layers` (tests/build/test_build.py)

**Setup**: the existing build scaffolding; effective config with
`build.env={"T": "cfg"}` (agent satisfied); 
`monkeypatch.setenv("GOGA_EXTRA_ENV", encode_extra_env(["T=cli"]))`;
`cli_options={"dry_run": True, "skip_manifest_check": True}`; capture stderr
(`run_ralphex` prints the pass commands there) and record `run_build_pass`
and the `BuildHooks` emissions.

**Input**: `build("plan.md", effective_config, cli_options)`

**Trace**:
```
build(...)
  → guard → sync → decode {"T":"cli"} → gate (approved) → build_started
  → tasks pass: run_build_pass(env={"T":"cli"}) → run_ralphex(dry_run=True)
      prints shlex.join(cmd) to stderr, returns 0
  → review pass: run_build_pass(env={"R":…,"T":"cli"}) → printed the same way
  → relocation skipped (dry_run) → build_completed
```

**Assertions**:
```
"T=cli" not in captured stderr; "cfg" not in captured stderr
"GOGA_EXTRA_ENV" not in captured stderr
event structure identical to a non-dry run: build_started 1, pass_started 2,
pass_completed 2, build_completed 1
run_build_pass received env={"T":"cli"} (tasks) — the layer travels as data
```

**Sufficiency**: the dry-run secret-safety checkpoint of the new layer
composition — the CLI entries and the task env reach the passes as `env`
parameters only; a regression that prints a composed layer would leak tokens
into CI logs.

---

## Additional Instructions for the Implementation Agent

- Write the code bottom-up: `goga/docker/extra_env.py` (+ exports) → `goga/afm/run_flow.py`
  → `goga/pipeline/afm_config.py` (+ export) → `goga/pipeline/run_pipeline.py` →
  `goga/build/__main__.py` + `goga/build/build.py` → the two host launchers. Each layer's
  tests land with the layer.
- `run_flow`'s env application must mirror `goga/ralphex/run_ralphex.py` exactly
  (`env={**os.environ, **env}` when truthy, no `env` kwarg otherwise) — read that file
  first.
- The engine-key drop set is a private constant in EACH consumer
  (`run_pipeline.py`, `build.py`): `frozenset({"AFM_DIR", "AFM_DOCKER_FILE_ROOTS",
  "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"})` — verbatim from the `extra-env-carriage`
  practice. Do not export an undeclared constant from `goga.docker`; only
  `encode_extra_env` and `decode_extra_env` join `__all__`.
- Consumers read the payload with the literal `os.environ.get("GOGA_EXTRA_ENV", "")`
  per the practice; the name constant inside `extra_env.py` stays private (it exists
  for the error message).
- `GOGA_EXTRA_ENV` needs no drop-set membership: no target binary reads it, and the
  launcher-written payload line (last line of the env-file) already wins over any CLI
  line of the same key under docker's last-write-wins.
- Both host `_write_env_file` helpers converge on the same line-list form: base dict
  lines → raw CLI lines → engine lines (minus CLI-supplied keys) → the payload line.
  Keep the 0600 mode and the private tempfile prefix of each existing helper.
- Renumber the in-code step comments to the new contract numbering (commands/build
  steps 7–18; commands/pipeline steps 5–16) — the CODEMANIFEST is the reference.
- Delete `tests/commands/pipeline/test_run_pipeline_container_afm_config.py` and
  `..._resolved_wrapper.py` with the code they locked; port any still-relevant
  assertions (fixed mount target absence, wrapper-omission semantics) into the new
  in-container `test_afm_config.py` suite.
- Update the stale docstrings: `goga/config/project/config.py` (`PipelineConfig.agent`
  still describes the retired host ClickException guard) and the `resolve_run_settings`
  / `validate_review_config` reachability notes.
- Never print, log, or assert with real secret values; tests use synthetic markers
  (`KEY=V`, `TOKEN=a=b`).
- After implementation: `goga lint` must stay at 0 errors, the full pytest suite must
  pass, and `git diff` must show no changes under `.usages/` or `CODEMANIFEST` (the
  contracts are frozen by this design; any contract-level need discovered during
  implementation goes back through review, not an in-flight manifest edit).
