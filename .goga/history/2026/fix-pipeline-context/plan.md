# Plan: `fix-pipeline-context`

<!-- Topic: fix-pipeline-context — split the run context from the host launch context (pipeline and build) -->

Compiled from the reviewed design document `.goga/history/2026/fix-pipeline-context/design.md`
(including all 6 design-review fixes). The contracts (CODEMANIFEST files and `.usages/`
practices) are already materialized on disk by apply-architecture; this plan implements them.
Branch: `fix-pipeline-context`; base: the working tree at `HEAD` (commit `6e74e1f`).

---

## Purpose

Split the run context from the host launch context in both container domains (pipeline and
build). After implementation:

- The CLI environment entries (`-e KEY=VALUE`) travel across the docker boundary through
  **two carriers composed from one source**: the raw `KEY=VALUE` env-file lines and the
  `GOGA_EXTRA_ENV=encode_extra_env(...)` payload line (last line of the env-file). In-container,
  each domain decodes the payload once and applies it **above** its effective task env layer,
  dropping the five engine-variable keys — so explicit CLI input beats the (amended) task env
  layer, and launch mechanics can never be overridden.
- The project configuration is loaded **and amended in-container** (`run_pipeline` and
  `goga/build::main` now open with the load-and-amend), so amendments supplied by tool
  packages reach the run parameters they own (`pipeline.agent`, `pipeline.env`,
  `build.agent`, `build.env`, `build.review.env`).
- The afm configuration file (`~/.afm/config.yaml`) is authored **in-container** by
  `write_afm_config`; the host no longer generates or mounts it (tmpfile flow retired).
- The build agent value guard moves **before the first state write** (the `.ralphex/`
  rewrite) and reads the effective configuration; the host keeps only the structural
  build-section guard.

Strategy: bottom-up implementation in dependency order — `goga/docker` (the carriage) →
`goga/afm` (the env layer) → `goga/pipeline` → `goga/build` → the two host launchers —
with each layer's tests landing in the same task as the layer (TDD workflow).

---

## Context

### Interaction Diagram (verbatim from the design)

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

### Data Flows (verbatim from the design)

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

### Entity Dependencies (new/changed edges, all downward, verified via `goga schema`)

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

### Contract Surface

**Entity: `encode_extra_env`** (goga/docker — NEW)
- Type: function (Routine)
- Declared `location`: `goga/docker/extra_env.py` (file to create)
- Facade obligation: must be importable from `goga.docker` (added to `__all__` in
  `goga/docker/__init__.py`)
- Signature: `encode_extra_env(entries: list[str]) -> value: str`
- Semantic requirements: pure encoder of the raw CLI environment entries into the
  single-line engine payload; split each entry at the FIRST `=`; separator-less entries
  skipped silently (no validation, no warning); repeated keys resolve last-wins;
  compact sorted JSON then standard base64 with padding, single line; deterministic;
  decodes back to exactly the resolved mapping; pure (no filesystem, no env reads, no
  side effects)
- Imported dependencies: none (stdlib `json`, `base64` only)
- Annotation context: `convention` for docstring style and intra-package imports

**Entity: `decode_extra_env`** (goga/docker — NEW)
- Type: function (Routine)
- Declared `location`: `goga/docker/extra_env.py`
- Facade obligation: must be importable from `goga.docker` (added to `__all__`)
- Signature: `decode_extra_env(value: str) -> entries: dict[str, str]`
- Semantic requirements: pure decoder of the payload back into the CLI environment
  mapping; empty `value` → `{}` immediately; `base64.b64decode(value, validate=True)` +
  `json.loads`; ANY failure (non-alphabet, wrong padding, non-JSON, non-UTF-8, non-dict,
  non-string key/value) raises ONE clean `ValueError` naming the engine variable
  (`"GOGA_EXTRA_ENV: invalid payload"`), never leaking payload content; result equals
  the mapping `encode_extra_env` produced from the same entries; pure — nothing applied,
  printed, or logged
- Module constant (private): `_EXTRA_ENV_VARIABLE = "GOGA_EXTRA_ENV"` — used in the error
  message; only the two routines join `__all__`
- Imported dependencies: none (stdlib `base64`, `json`, `binascii`)

**Entity: `run_flow`** (goga/afm — CHANGED)
- Type: function (Routine)
- Declared `location`: `goga/afm/run_flow.py` (existing file)
- Facade obligation: already importable from `goga.afm` — unchanged
- New signature: `run_flow(flow_path: Path, port: int, max_parallel: int | None = None, env: dict[str, str] | None = None) -> exit_code: int`
- Semantic requirements: when `env` is truthy launch with
  `subprocess.run(cmd, check=False, env={**os.environ, **env})`; when None/empty launch
  with pure inheritance (no `env` kwarg); the layer applies to this subprocess only; the
  caller's `os.environ` is untouched; nothing from the layer reaches argv, logs, or
  output; `FileNotFoundError` → 127; other `OSError` OR `ValueError` (an environment
  layer rejected by the exec — e.g. an illegal variable name in a config-authored
  `pipeline.env` key) → 126; afm's exit code propagated unchanged
- Imported dependencies: none new (stdlib `os` added)

**Entity: `write_afm_config`** (goga/pipeline — NEW)
- Type: function (Routine)
- Declared `location`: `goga/pipeline/afm_config.py` (file to create)
- Facade obligation: must be importable from `goga.pipeline` (added to `__all__` in
  `goga/pipeline/__init__.py`)
- Signature: `write_afm_config(agent: str | None) -> config_path: Path`
- Semantic requirements: resolve the wrapper via `resolve_wrapper_path(agent)` ONLY when
  `agent is not None`; compose content programmatically as a dict — `client:
  {command: <resolved wrapper>}` only when an agent resolved (omitted otherwise), plus
  the four static fields `theme: goga`, `open_browser: False`, `proxy: {enabled: False}`,
  `prompts_dir: /home/goga/pipeline/prompts`; serialize with `yaml.safe_dump`; ensure the
  parent directory exists (`mkdir(parents=True, exist_ok=True)`); write the whole file at
  the FIXED path `/home/goga/.afm/config.yaml`; return the written `Path`; nothing
  printed; `OSError` propagates (unwritable home); idempotent whole-file rewrite
- Module constants (private): `_AFM_CONFIG_PATH = Path("/home/goga/.afm/config.yaml")`,
  `_PROMPTS_DIR = "/home/goga/pipeline/prompts"`
- Imported dependencies: `resolve_wrapper_path` from `goga/agents` (via `..agents`)
- Annotation context: `convention`, `afm` (field set, fixed home path), `resolve-wrapper-path`

**Entity: `run_pipeline`** (goga/pipeline — CHANGED)
- Type: function (Routine)
- Declared `location`: `goga/pipeline/run_pipeline.py` (existing file)
- Facade obligation: already importable from `goga.pipeline` — unchanged
- Signature: UNCHANGED — `run_pipeline(name, project_dir, user_dir, port, workflow=None, no_workflow=False, skip=None, parallel=None) -> exit_code: int`
- Semantic requirements: the re-algorithmized 21 contract steps (verbatim in Task 4) —
  opens with the configuration load-and-amend; writes the afm configuration file via
  `write_afm_config` at step 14; composes the launch env layer at step 17 (effective
  `pipeline.env` ⊕ decoded CLI entries ⊖ engine keys); passes it as `run_flow`'s `env`;
  exactly two environment reads (`AFM_DIR`, `GOGA_EXTRA_ENV`); no events fire on any
  pre-checkpoint return path
- New module constant (private): `_ENGINE_ENV_KEYS = frozenset({"AFM_DIR",
  "AFM_DOCKER_FILE_ROOTS", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"})`
- Imported dependencies (new): `load_project_config` (extend the existing
  `from ..config import resolve_project_name`), `ConfigHooks` (`from ..config.hooks`),
  `decode_extra_env` (`from ..docker`), `write_afm_config` (`from .afm_config`), and
  `import yaml` (the load's error set includes `yaml.YAMLError`)

**Entity: `main`** (goga/build — CHANGED)
- Type: function (Routine)
- Declared `location`: `goga/build/__main__.py` (existing file)
- Facade obligation: module entrypoint — unchanged shape
- Signature: `main() -> exit_code: int` — unchanged
- Semantic requirements: `ensure_in_docker()` first; argparse unchanged; then
  load-and-amend (steps 2–4): load failure → clean stderr error, return 1, ralphex never
  launches; delivery failure (`ValueError`/`ImportError`) → clean error naming the tool
  and the action, return 1; print `overlay.summary_lines` to stderr (nothing when empty;
  no configuration value appears); `return build(args.plan, overlay.config, cli_options)`
  — the EFFECTIVE configuration, never the authored one
- Imported dependencies (new): `ConfigHooks` (`from ..config.hooks`), `import yaml`
  (error set); `load_project_config` already imported

**Entity: `build`** (goga/build — CHANGED)
- Type: function (Routine)
- Declared `location`: `goga/build/build.py` (existing file)
- Facade obligation: importable from `goga.build` (via `from .build import build`) — unchanged
- Signature: `build(plan: str, config: ProjectConfig, cli_options: dict) -> exit_code: int` — unchanged
- Semantic requirements: agent value guard runs at step 3 BEFORE `sync_ralphex_defaults`
  (before any state write) on the EFFECTIVE settings; one payload decode (step 5) feeds
  both passes; `_compose_pass_env(task_env, cli_entries)` = task env ⊕ CLI entries ⊖
  engine keys, `None` when empty; the task env never reaches the review pass; damaged
  payload → clean error, exit 1, no events, no launches
- Internal deletions: `_stage_env_layer` (subsumed by `_compose_pass_env`); `cli_entries`
  threads from `build` into `_launch_pass` as a parameter (the helper stays pure; no
  module state)
- Imported dependencies (new): `decode_extra_env` (`from ..docker`); `resolve_wrapper_path` already imported

**Entity: `resolve_run_settings` / `validate_review_config`** (goga/build — CHANGED, documentation-level)
- Locations: `goga/build/run_settings.py`, `goga/build/review_config.py`
- Behavior unchanged; only the reachability note/docstring updates: the no-review-agent
  error is reachable when neither the authored configuration nor an amendment supplies a
  review agent (previously framed as "reachable only on direct in-container invocation")

**Entity: `build` host command** (goga/commands/build — CHANGED)
- Type: Click command callback
- Declared `location`: `goga/commands/build/build.py` (existing file)
- Facade obligation: part of the click CLI surface — unchanged shape
- Semantic requirements: the host agent value guard (step 2.2) is DELETED; the
  structural build-section guard (step 2.1) stays on the host-effective configuration;
  env-file ladder reordered: base lines (`{**home.env, **git_env}`) → raw `extra_env`
  lines verbatim → engine lines (the proxy triple only, each SKIPPED when the CLI
  explicitly supplied that key) → the payload line
  `GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}`; the task env (`build.env`) is NOT
  written into the env-file; in-code step comments renumber (old 8–19 → new 7–18)
- Imported dependencies (new): `encode_extra_env` (extend the existing
  `from ...docker import ...`)

**Entity: `run_pipeline_container`** (goga/commands/pipeline — CHANGED)
- Type: function (Routine)
- Declared `location`: `goga/commands/pipeline/run_pipeline_container.py` (existing file)
- Facade obligation: consumed by the `pipeline` command — unchanged shape
- Signature: `run_pipeline_container(name, config, extra_env, proxy, hosts, clean, update, workflow, no_workflow, skip, parallel) -> exit_code: int` — unchanged
- Semantic requirements: tmpfile flow fully retired (no write, no mount, no unlink); NO
  agent resolution (the `goga/agents` import is removed); `_build_env_file` drops the
  `pipeline_env` parameter and restructures to the line-list form: base lines → raw CLI
  lines → engine lines (`AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, the proxy triple — each
  skipped when the CLI supplied that key) → the payload line; `config.pipeline.env` and
  `config.pipeline.agent` are read NOWHERE on the host; mounts reduced to
  `[f"{project_dir}:/workspace", f"{runtime_dir}:{_IN_CONTAINER_AFM_DIR}"]`; runtime-dir
  mkdir + `--clean` wipe move BEFORE the signal handlers; `finally` unlinks ONLY the
  env-file and restores both handlers; in-code step comments renumber (steps 5–16)
- Internal deletions: `_write_afm_config_tmpfile` (whole helper), its invocation, the
  tmpfile mount entry, the `afm_config` variable, its `finally` unlink,
  `from ...agents import resolve_wrapper_path`
- Kept: `_IN_CONTAINER_AFM_DIR` (the AFM_DIR value and the file-roots mount target)
- Imported dependencies (new): `encode_extra_env` (extend the existing
  `from ...docker import ...`)

**Entity: `pipeline` command** (goga/commands/pipeline — comment-level)
- Location: `goga/commands/pipeline/pipeline.py`
- No behavioral change beyond what `run_pipeline_container`'s changes imply; the
  agent-optionality comment block stays accurate (no behavioral read of
  `pipeline.agent`/`pipeline.env` remains anywhere in the host cell)

**Entity: `PipelineConfig`** (goga/config/project — CHANGED, documentation-level)
- Location: `goga/config/project/config.py`
- Behavior unchanged; only dataclass docstrings change: `agent` is "resolved at runtime
  by the in-container consumer (goga/pipeline) into an absolute wrapper path written
  into the afm configuration file; this cell does no resolution or validation"; `env` is
  "applied in-container as the afm launch env layer, above the inherited launch
  environment; it never travels through the docker launch env-file". The current
  docstring still describes the retired host guard ("`goga pipeline` raises a clean
  ClickException when it needs an agent") and must be replaced.

### Re-exports

None. The changed CODEMANIFESTs declare no `->Name: {}` embedding blocks. The only
facade obligations are the `__all__` additions in `goga/docker/__init__.py`
(`encode_extra_env`, `decode_extra_env`) and `goga/pipeline/__init__.py`
(`write_afm_config`).

### Usages Context

- **`convention` / `conventions`** (`.goga/usages/conventions.md`) — the project-wide
  code standard: Google-style docstrings, relative intra-package imports, logging rules,
  pytest/ruff test rules. Used by every touched cell's global annotations. Its mandatory
  rules are extracted into the "Mandatory Rules" section below and are binding for every
  task.
- **`afm`** (`.goga/usages/cooks/afm.md`, already updated by this topic) — the afm
  binary contract: CLI shape (`afm run --port <p> [--max-parallel <n>] <abs flow path>`),
  PATH resolution, exit codes, the `~/.afm/config.yaml` field set (`client.command` —
  absolute wrapper path only, `theme: goga`, `open_browser: false`, `proxy.enabled:
  false`, `prompts_dir: /home/goga/pipeline/prompts`), `AFM_DIR`, per-stage `command:`
  overrides, `AFM_DOCKER_FILE_ROOTS`, and the environment-carriage ladder. Relevant to
  Tasks 2, 3, 4.
- **`checkpoints`** (goga/config/hooks/.usages/checkpoints.md, already updated) — the
  config checkpoint surface usage: `ConfigHooks().amend_config`,
  `ConfigOverlay.config`/`summary_lines`, the one-action-two-moments rule, field
  ownership, hard failure semantics. Relevant to Tasks 4, 5 (and the pre-existing host
  delivery in Tasks 7, 8).
- **`extra-env-carriage`** (goga/docker/.usages/extra-env-carriage.md, NEW — created by
  apply-architecture) — the carriage contract: one source (the parsed CLI values), two
  carriers (raw env-file lines + the `GOGA_EXTRA_ENV` payload); the ladder
  `home.env < git identity < task env layer < CLI -e < engine variables`; the engine-key
  drop set; the container-half application rules. Relevant to Tasks 1, 4, 6, 7, 8.
- **`project-configuration`** (goga/config/.usages/project-configuration.md) — the
  authored load contract of `.goga/config.yml`: one loader, one error-mode set, all four
  load moments identical. Relevant to Tasks 4, 5.
- **`resolve-wrapper-path`** (goga/agents/.usages/resolve-wrapper-path.md) — the
  in-container wrapper naming convention (`/home/goga/bin/<agent>-as-claude.sh`);
  `resolve_wrapper_path(agent)` is pure string building, no validation. Relevant to
  Task 3 (NEW consumer); NO LONGER used by `goga/commands/pipeline` (Task 8).
- **`run-flow`** (goga/afm/.usages/run-flow.md, already updated) — the `run_flow`
  consumer contract incl. the new `env` layer parameter ("Environment layer contract"
  section). Relevant to Task 4 (step 19).
- **`checkpoints`** (goga/pipeline/hooks and goga/build/hooks) — the pipeline run-event
  moments (`run_created` now fires after the afm configuration write) and the build
  gate/moment ordering (the gate after the agent guard and the defaults sync). Relevant
  to Tasks 4, 6.

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
  delivery); the in-container consumers (`goga/pipeline`, `goga/build`) import the types
  only and carry the delivery semantics through their own annotations.

### Local Usages

None to create or modify. The design's audit found every cell-level `.usages/` file of
the affected cells already current (they were updated by the apply-architecture stage).
Two OPTIONAL clarifications were recorded for a future documentation pass — they are NOT
blockers and MUST NOT be applied by the implementation agent (the `.usages/` tree is
frozen by this plan): the skip-rule comment in the host-half sketch of
`extra-env-carriage.md`, and the `GOGA_EXTRA_ENV` drop-set asymmetry note.

### External Dependencies

- **afm** — the external binary launched by `run_flow` (CLI shape and exit codes per the
  `afm` practice). Not invoked by tests (subprocess is mocked).
- **ralphex** — the external binary launched by `run_ralphex` (untouched; the parity
  reference for `run_flow`'s env application).
- **docker** — external CLI used by `DockerRunner`/`DockerBuilder`; `--env-file`
  last-write-wins semantics underpin the carriage contract. Not invoked by tests.
- **PyYAML** (`yaml.safe_dump`/`yaml.safe_load`, `yaml.YAMLError`) — serialization for
  `write_afm_config` and the load error set. Already a project dependency.
- **pytest / pytest-cov / ruff** — test and lint toolchain (`[project.optional-dependencies].test`).
- **click** — host command surface (`ClickException`, `CliRunner` in tests). Already a dependency.

## Facts

- The contracts are already materialized: `goga lint` reported 83 cells / 0 errors, all
  imports resolve, all backtick references resolve, no cross-import cycles, and the new
  `location`s (`extra_env.py`, `afm_config.py`) are valid.
- `goga/ralphex/run_ralphex.py` already implements the exact env-application pattern
  `run_flow` must mirror (`env={**os.environ, **env}` when truthy, no `env` kwarg
  otherwise, plus the `(OSError, ValueError)` arm).
- `goga/build/__main__.py` already imports and calls `load_project_config()` — but
  without error handling and without the amend delivery.
- `goga/build/build.py` currently has `_prepare_run_settings` (line ~66), `_stage_env_layer`
  (line ~205, to be deleted), `_launch_pass` (line ~212); the agent guard currently sits
  in the host command (`goga/commands/build/build.py` step 2.2, line ~331–336).
- `goga/commands/pipeline/run_pipeline_container.py` currently contains
  `_write_afm_config_tmpfile` (line ~162, prefix `goga-afm-config-`), the
  `resolve_wrapper_path` import (line ~44), and `_build_env_file` with a `pipeline_env`
  parameter (line ~348) that merges `config.pipeline.env` into the env-file.
- `tests/docker/` exists (with `__init__.py`) but has no `test_extra_env.py`;
  `tests/pipeline/` has `conftest.py` (pipeline-tree fixtures: `isolated_cwd`, `afm_dir`,
  `write_pipeline`, `patch_defaults`) but no `test_afm_config.py`.
- `tests/afm/test_run_flow.py` already carries the contract-test pattern to follow
  (`test_run_flow_importable_from_facade`, `test_run_flow_signature_matches_contract`).
- `binascii.Error` and `json.JSONDecodeError` are both `ValueError` subclasses — a
  single `except ValueError` arm covers the whole decode failure set.
- Docker's `--env-file` applies last-write-wins; the launcher-written payload line is
  the last line, so it beats any CLI line of the same key.
- `GOGA_EXTRA_ENV` needs no drop-set membership: no target binary reads it, and the
  launcher-written payload line already wins under last-write-wins.
- The working tree carries the uncommitted contract changes from apply-architecture
  (7 CODEMANIFESTs + `.usages/` files + `.goga/usages/cooks/afm.md`); the implementation
  must not touch them further.

## Gap Analysis

- Missing contract entities: `goga/docker/extra_env.py` (both routines),
  `goga/pipeline/afm_config.py` (`write_afm_config`) — files do not exist.
- Missing facade exposure: `encode_extra_env`/`decode_extra_env` absent from
  `goga/docker/__init__.py` (`__all__` lacks them); `write_afm_config` absent from
  `goga/pipeline/__init__.py`.
- API mismatches: `run_flow` lacks the `env` parameter; `run_pipeline` lacks the
  load-and-amend, the afm-config write, and the layer composition; `build::main` lacks
  the amend and the clean-error boundary; `build::build` guards the agent in the wrong
  place (host, after-load) and composes pass layers without the CLI entries.
- Behavioral mismatches: the host pipeline launcher writes `pipeline.env` into the
  env-file and resolves the agent (both retired); the host build launcher guards
  `build.agent` (retired); the tmpfile afm-config flow exists (retired); engine lines
  precede CLI lines in the env-file (reordered).
- Existing code to reuse: `_write_env_file` in both host launchers (keep the 0600 mode
  and the private tempfile prefix of each), `run_ralphex`'s env pattern (the parity
  reference), the `PipelineHooks`/`BuildHooks` test fakes, the env-file readers in both
  command test suites, `tests/pipeline/conftest.py` fixtures.
- Test coverage gaps: no tests exist for the carriage, the afm-config authorship, the
  load-and-amend in-container, the guard move, or the ladder order.
- Legacy tests locking the retired behavior (verified against the working tree —
  they are deleted or reworked by Tasks 7–8, never satisfied by reverting the
  implementation):
  - DELETE whole files: `tests/commands/pipeline/test_run_pipeline_container_afm_config.py`,
    `tests/commands/pipeline/test_run_pipeline_container_resolved_wrapper.py`,
    `tests/integration/test_launcher_tmpfile_integration.py` (mounts the tmpfile,
    asserts 3 mounts, monkeypatches `_write_afm_config_tmpfile`).
  - `tests/commands/test_build.py` — the `TestBuildAgentGuard` class
    (`test_build_command_raises_click_exception_when_agent_absent`) locks the host
    step-2.2 guard Task 7 deletes; the `TestBuildSectionGuard` class stays (structural
    guard kept).
  - `tests/commands/pipeline/test_run_pipeline_container.py` — existing scenarios to
    rework: `test_pipeline_env_file_combines_pipeline_env_and_git` and
    `test_pipeline_env_overrides_git_on_conflict` (pipeline.env in the env-file —
    premise retired); `test_pipeline_env_file_default_extra_env_is_empty` (exact
    content `FOO=1\n` — the payload line is now written on every launch);
    `test_pipeline_env_file_appends_extra_env_lines` and
    `test_pipeline_run_forwards_extra_env_to_write_env_file` (`_write_env_file`
    restructured to the line-list form); `test_extra_env_file_roots_override_wins`
    (semantics inverted — the launcher engine line is now SKIPPED when the CLI
    supplied the key); `test_home_and_pipeline_env_keys_do_not_override_composed_roots`
    (pipeline.env premise); the three-mounts test (~lines 770–800 → exactly 2 mounts).
  - `tests/integration/test_resolved_wrapper_flow.py` — the "pipeline consumer:
    afm-config tmpfile client.command" section (~lines 210–313) reads the tmpfile
    content; the build-side sections stay.
  - `tests/integration/test_docker_update_launch_integration.py` — the D7 leak tests
    monkeypatch the deleted `_write_afm_config_tmpfile` (lines ~328/341, ~392/405);
    rework to the env-file as the single secret artifact.
  - `tests/integration/test_runtime_isolation.py` —
    `test_run_mounts_exactly_three_engine_mounts_even_with_credentials_present`
    (3 → exactly 2 engine mounts).
  - `tests/integration/test_pipeline_home_integration.py` —
    `test_run_mode_layers_home_env_as_base` asserts pipeline.env inside the env-file
    (retired); the `_write_env_file` capture wrappers follow the old signature.
- Stale docstrings: `goga/config/project/config.py` (`PipelineConfig.agent` describes
  the retired host guard), `goga/build/run_settings.py` /
  `goga/build/review_config.py` reachability notes.

---

## Mandatory Rules

Extracted from the project conventions (`.goga/usages/conventions.md`), the Python
language contract rules (`goga-cell-python`), and the general contract-oriented
conventions. These rules are **mandatory** for every task in this plan; the contract
(CODEMANIFEST annotations) takes precedence only where it is explicitly stricter.

### Coding Style (mandatory)

1. **Python 3.10+ only.** All code (source and tests) must be compatible with Python
   3.10 and above. Execute everything inside a virtualenv — create it if missing.
2. **`from __future__ import annotations`** at the top of every touched module (already
   the idiom in every file this plan modifies; keep it in the new files
   `extra_env.py` and `afm_config.py`).
3. **Relative imports for all intra-package references**
   (`from ..config import load_project_config`, `from .afm_config import write_afm_config`);
   absolute imports only for stdlib and third-party (`import yaml`, `import base64`).
   Exception — tests: inside `tests/`, cross-directory references use absolute imports
   rooted at the `tests` package (`from tests.commands.conftest import ...`).
4. **Type hints are mandatory** on every public function/method; they drive contract
   signature extraction. Allowed shapes: `str`, `int`, `float`, `bool`, `list[T]`,
   `dict[str, T]`, `T | None`. No bare `dict`/`list`, no `*args`/`**kwargs`.
5. **Google-style docstrings** for every public function, method, and class: first line
   required, starts with a capital letter, ends with a period; `Args:` section when the
   function accepts parameters; `Returns:` when it returns a value; `Raises:` when it
   raises beyond built-ins. Update the docstring of every function whose behavior this
   plan changes (`run_flow`, `run_pipeline`, `main`, `build`, the host launchers).
6. **Click command callback docstrings are user-facing help**: omit `Args`/`Returns`/
   `Raises`, keep the concise summary line, use `\f` to hide developer-facing notes.
   (Relevant where the host command docstrings mention the guard.) All OTHER public
   functions in command modules keep the full Google style.
7. **Dataclasses**: any new data model uses the stdlib `dataclasses` module with
   `kw_only=True`; empty defaults for fields; `None` only for explicit absence. (No new
   data models are planned; apply to any helper dataclass if one is introduced.)
8. **Logging** via stdlib `logging` with `logger = logging.getLogger(__name__)`;
   lowercase structured messages with contextual `extra={...}` metadata (e.g. the agent
   guard's `extra={"remedy": ...}`); ERROR for operations that cannot complete. Clean
   CLI errors print one line to stderr (`print(..., file=sys.stderr)`).
9. **Secret safety (cross-cutting invariant of this change)**: env layer values, task
   env values, and payload contents NEVER appear in argv, logs, dry-run output, events,
   or error messages — presence travels as names only; error messages carry no payload
   content; layers travel only through the `env` parameter of `run_flow`/`run_ralphex`;
   the container's `os.environ` is never mutated.
10. **Formatting**: one blank line between logical blocks inside function bodies
    (initialization vs conditions/loops; data preparation vs processing; processing vs
    return). Ruff line-length 120, target py310 — `ruff check` must pass.
11. **Naming**: PascalCase for classes; snake_case for functions, methods, properties,
    and module constants (`_ENGINE_ENV_KEYS`, `_EXTRA_ENV_VARIABLE`, `_AFM_CONFIG_PATH`).
    Private module constants stay private (leading `_`); only contract entities join
    `__all__`.
12. **Location discipline**: implement each entity exactly at its declared `location`;
    the file must sit at the same directory level as the cell's CODEMANIFEST.

### Test Writing Rules (mandatory)

1. **pytest**; tests mirror the source structure directly:
   `goga/<cell>/<file>.py` → `tests/<cell>/test_<file>.py`. Every test directory has an
   `__init__.py`. Local fixtures go in `tests/<pkg>/conftest.py`, shared ones in
   `tests/conftest.py`.
2. **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>` (e.g.
   `test_run_flow_illegal_env_key_returns_126`); grouping `class Test<Component>:` where
   a file covers one component.
3. **TDD within each coding task (ralphex protocol)**: STEP 1 writes **contract tests**
   first — facade importability, API shape, method signatures (follow the existing
   pattern of `test_run_flow_importable_from_facade` /
   `test_run_flow_signature_matches_contract` using `inspect.signature`) — they are
   expected to FAIL before implementation. STEP 4 writes **logic tests** after the
   implementation: positive, negative, and edge scenarios per the design's Test Stack
   Trace (transferred verbatim into the tasks below). STEP 5 runs everything and fixes
   the implementation (never the tests) until green.
4. **Mocks only at external boundaries.** Pure logic (the encode/decode round-trip) is
   tested without mocks. File I/O → `tmp_path` exclusively. Subprocesses →
   `mock.patch` the subprocess call. Environment/CWD → `monkeypatch`. External
   dependencies → `mock.patch` at the import point.
5. **`GOGA_EXTRA_ENV` is always driven via `monkeypatch.setenv/delenv`** — never mutated
   globally. The `_ENGINE_ENV_KEYS` set is asserted through behavior (a key colliding
   with an engine variable is absent from the layer), NOT by importing the private
   constant.
6. **Never print, log, or assert with real secret values** — tests use synthetic markers
   (`KEY=V`, `TOKEN=a=b`) only.
7. **Boundary behavior** (the decode failure classes, the empty-payload cases) uses
   `pytest.raises` / parametrized tables including each boundary.
8. **Reuse the existing scaffolding**: `tests/pipeline/conftest.py` (pipeline-tree
   fixtures), the `PipelineHooks`/`BuildHooks` fakes from `test_run_pipeline_hooks.py` /
   `test_build.py`, and the env-file readers in `tests/commands/build/test_build.py` and
   `tests/commands/pipeline/test_run_pipeline_container.py`.
9. **Order-independence**: never assert on `sys.modules` (process-global,
   order-dependent); use the module-object `dir()` form instead (see Task 8).
10. **Test classification**: contract tests (facade/API shape) and logic tests
    (behavior) are mandatory inside each coding task; integration tests do not replace
    them. This plan adds no new cross-package integration files — the docker boundary
    makes the carriage cross-entity behavior observable only through the per-cell
    boundary tests the design specifies.

### Contract and Boundary Discipline (mandatory)

1. **`CODEMANIFEST` files are read-only.** If the implementation does not match the
   contract, fix the implementation — never the contract. Any contract-level need
   discovered during implementation goes back through review, not an in-flight manifest
   edit.
2. **The `.usages/` tree is frozen by this plan** — the files are current per the
   design's audit; do not apply the two optional clarifications.
3. **No new cells, no boundary expansion** — internal helpers stay inside the touched
   cells; the engine-key drop set is a private constant in EACH consumer
   (`run_pipeline.py`, `build.py`), verbatim; do not export an undeclared constant from
   `goga.docker` (only `encode_extra_env` and `decode_extra_env` join `__all__`).
4. **Consumers read the payload with the literal**
   `os.environ.get("GOGA_EXTRA_ENV", "")` per the `extra-env-carriage` practice; the
   name constant inside `extra_env.py` stays private (it exists for the error message).
5. **Facade obligations**: every entity must be importable from its package root via
   `__all__`.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting
> the next. Within each coding task, contract tests are written first (TDD workflow).
> Package order (bottom-up): `goga/docker` → `goga/afm` → `goga/pipeline` → `goga/build`
> → `goga/commands/build` → `goga/commands/pipeline` → `goga/config/project` → final
> verification.

### Task 1: `encode_extra_env` + `decode_extra_env` — the CLI env carriage routines (goga/docker)

Create `goga/docker/extra_env.py` with the two pure carriage routines declared in
`goga/docker/CODEMANIFEST` (`location: extra_env.py`) and expose both from the
`goga.docker` facade. The cell structure and facade already exist — this task only adds
the module and the `__all__` entries. Both routines are pure: the entry source belongs
to the calling launcher, the application belongs to the consuming domain launch.

**Usages relevant to this task:**
- `convention`: Google-style docstrings, relative imports, `from __future__ import annotations`.
- `extra-env-carriage` (`goga/docker/.usages/extra-env-carriage.md`): the carriage
  contract context — one source, two carriers; the routines implement only the payload
  half (encode on the host per launch, decode once in-container).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare Task 1 — targets `goga/docker/extra_env.py` (new), `goga/docker/__init__.py` (facade), `tests/docker/test_extra_env.py` (new)
- [x] **STEP 1 (CONTRACT TESTS)**: create `tests/docker/test_extra_env.py` with contract tests (expected to FAIL now): `encode_extra_env` and `decode_extra_env` importable from the `goga.docker` facade; signatures match the contract via `inspect.signature` — `encode_extra_env(entries: list[str]) -> str`, `decode_extra_env(value: str) -> dict[str, str]`
- [x] **STEP 2 (IMPLEMENTATION)**: create `goga/docker/extra_env.py` implementing (verbatim from the design's Algorithm Design):

```
encode_extra_env(entries: list[str]) -> value: str
1. resolved = {} (insertion-ordered)
2. FOR each pair in entries:
     key, sep, value = pair.partition("=")
     IF sep == "": continue            # no separator — skipped silently
     resolved[key] = value             # later entry wins on repeat
3. payload = json.dumps(resolved, separators=(",", ":"), sort_keys=True)
4. RETURN base64.b64encode(payload.encode("utf-8")).decode("ascii")

decode_extra_env(value: str) -> entries: dict[str, str]
1. IF value == "": RETURN {}
2. TRY payload = json.loads(base64.b64decode(value, validate=True))
   EXCEPT (ValueError, binascii.Error): RAISE ValueError(f"{_EXTRA_ENV_VARIABLE}: invalid payload")
     # binascii.Error IS a ValueError subclass; json.JSONDecodeError IS a ValueError
     # subclass — a single `except ValueError` arm covers both
3. IF not isinstance(payload, dict) OR any key/value is not a str:
     RAISE ValueError(f"{_EXTRA_ENV_VARIABLE}: invalid payload")
4. RETURN dict(payload)
```

  with the private module constant `_EXTRA_ENV_VARIABLE = "GOGA_EXTRA_ENV"` (used only
  in the error message; consumers read the environment with the literal), Google-style
  docstrings (Args/Returns/Raises on `decode_extra_env`), type hints, purity (no
  filesystem access, no environment reads, no prints), and NO entry validation on the
  encode side (malformed input travels as it arrived)
- [x] **STEP 2 (IMPLEMENTATION)**: extend `goga/docker/__init__.py` — import both routines from `.extra_env` and add `"decode_extra_env"`, `"encode_extra_env"` to `__all__` (alphabetical order, matching the existing list style); only these two names join the facade
- [x] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/docker/test_extra_env.py -v` — the contract tests must pass; plus facade check `python -c "from goga.docker import encode_extra_env, decode_extra_env"`
- [x] **STEP 4 (LOGIC TESTS)**: add to `tests/docker/test_extra_env.py` the logic tests below (verbatim scenarios from the design's Test Stack Trace; pure functions — no mocks, no fixtures):
  - [x] `test_encode_extra_env_roundtrip_resolves_last_wins` — input `["KEY=V", "TOKEN=a=b", "KEY=W"]`; assert the value is a single line (no `"\n"`), non-empty, only base64-alphabet chars, and `decode_extra_env(value) == {"KEY": "W", "TOKEN": "a=b"}` (first-separator split, values containing `=`, last-wins, exact round-trip)
  - [x] `test_encode_extra_env_deterministic` — `encode_extra_env(["A=1", "B=2"]) == encode_extra_env(["A=1", "B=2"])` and `== encode_extra_env(["B=2", "A=1"])` (sort_keys ⇒ order-independent)
  - [x] `test_encode_extra_env_silently_skips_separatorless_entries` — input `["BROKEN", "=V", "KEY=V"]`; assert `decode_extra_env(value) == {"": "V", "KEY": "V"}` and no warning/error raised (no `pytest.warns`)
  - [x] `test_decode_extra_env_damaged_payload_raises_clean_error_naming_variable` — for `["!!!not-base64!!!", "aGVsbG8=", base64 of "[1,2]", base64 of '{"K": 1}']` each raises `pytest.raises(ValueError, match=r"GOGA_EXTRA_ENV: invalid payload")`; assert `str(excinfo.value)` contains no base64 fragment of the input (no content leaked)
  - [x] `test_decode_extra_env_empty_value_returns_empty_mapping` — `decode_extra_env("") == {}`, no exception
- [x] **STEP 5 (DEBUGGING)**: run `pytest tests/docker/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify all contract obligations — both routines importable from `goga.docker`, signatures match, purity constraints hold (no env reads/prints in the module), only the two names added to `__all__`
- [x] **STEP 7 (LINT)**: `ruff check goga/docker/ tests/docker/` — fix formatting if necessary
- [x] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 1 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 2: `run_flow` env layer (goga/afm)

Change `goga/afm/run_flow.py` (declared `location: run_flow.py`) so the routine accepts
the caller-composed env layer: `run_flow(flow_path, port, max_parallel=None,
env: dict[str, str] | None = None) -> int`. The layer is applied to the afm subprocess
ONLY, on top of the inherited process environment; it is never composed here and never
logged. Before implementing, READ `goga/ralphex/run_ralphex.py` — the env application
must mirror it exactly.

**Usages relevant to this task:**
- `convention`: docstring style, imports.
- `afm` (`.goga/usages/cooks/afm.md`): the afm invocation shape and the 127/126 exit-code mapping.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare Task 2 — targets `goga/afm/run_flow.py`, `tests/afm/test_run_flow.py` (extend)
- [ ] **STEP 1 (CONTRACT TESTS)**: extend `tests/afm/test_run_flow.py` contract tests (expected to FAIL now): `run_flow` still importable from `goga.afm`; `inspect.signature` includes `env: dict[str, str] | None = None` after `max_parallel` (update the existing `test_run_flow_signature_matches_contract`)
- [ ] **STEP 2 (IMPLEMENTATION)**: apply to `run_flow` (verbatim from the design):

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

  Add `import os`; keep the docstring updated (`env` arg documented: subprocess-only
  application, None/{} both pure inheritance, secret-safe); error messages never
  include env values
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/afm/test_run_flow.py -v` — contract tests pass
- [ ] **STEP 4 (LOGIC TESTS)**: extend `tests/afm/test_run_flow.py` with (verbatim scenarios; monkeypatch `subprocess.run` to capture the `env` kwarg and return `returncode=0`):
  - [ ] `test_run_flow_env_layer_applied_to_subprocess_only` — monkeypatch a sentinel `SENTINEL="inherited"` into `os.environ`; call `run_flow(Path("/f.yml"), 8080, env={"KEY": "V"})`; assert captured `env["KEY"] == "V"` and `env["SENTINEL"] == "inherited"` (layer on top of inherited), `"KEY" not in os.environ` afterwards (caller untouched), `cmd == ["afm", "run", "--port", "8080", "/f.yml"]`, result `== 0`
  - [ ] `test_run_flow_none_and_empty_env_are_pure_inheritance` — `run_flow(Path("/f.yml"), 8080)` then `run_flow(Path("/f.yml"), 8080, env={})`; assert `"env" not in captured kwargs` for both calls
  - [ ] `test_run_flow_illegal_env_key_returns_126` — monkeypatch `subprocess.run` to raise `ValueError("illegal environment variable name")`; input `run_flow(Path("/f.yml"), 8080, env={"A=B": "v"})` (the shape a config-authored `pipeline.env` key could produce); assert return `== 126`, capsys.err contains one clean `Error:` line with no traceback, and neither `"A=B"` nor `"v"` appears in the message (no layer content leaked)
- [ ] **STEP 5 (DEBUGGING)**: run `pytest tests/afm/ -x` — fix implementation until green (do NOT fix tests)
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify facade importability from `goga.afm`, the full signature (existing callers unaffected — backward compatible), 127/126 semantics, secret-safety on all error paths
- [ ] **STEP 7 (LINT)**: `ruff check goga/afm/ tests/afm/`
- [ ] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 2 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 3: `write_afm_config` — in-container afm configuration authorship (goga/pipeline)

Create `goga/pipeline/afm_config.py` with the new routine declared in
`goga/pipeline/CODEMANIFEST` (`location: afm_config.py`) and expose it from the
`goga.pipeline` facade. The routine writes the WHOLE afm configuration file before the
launch: the agent client command (only when an agent resolved) plus the four static
launcher-side fields, at the FIXED home path.

**Usages relevant to this task:**
- `convention`: docstring style, relative imports.
- `afm` (`.goga/usages/cooks/afm.md`): the configuration-file contract — the exact field set, the fixed home path, the per-stage override relationship.
- `resolve-wrapper-path` (`goga/agents/.usages/resolve-wrapper-path.md`): `resolve_wrapper_path(agent)` — pure string building (`/home/goga/bin/<agent>-as-claude.sh`), no validation; never pass `None` into it (the guard lives in this routine).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare Task 3 — targets `goga/pipeline/afm_config.py` (new), `goga/pipeline/__init__.py` (facade), `tests/pipeline/test_afm_config.py` (new)
- [ ] **STEP 1 (CONTRACT TESTS)**: create `tests/pipeline/test_afm_config.py` with contract tests (expected to FAIL now): `write_afm_config` importable from the `goga.pipeline` facade; signature `write_afm_config(agent: str | None) -> Path`
- [ ] **STEP 2 (IMPLEMENTATION)**: create `goga/pipeline/afm_config.py` implementing (verbatim from the design; private constants `_AFM_CONFIG_PATH = Path("/home/goga/.afm/config.yaml")` and `_PROMPTS_DIR = "/home/goga/pipeline/prompts"`):

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

  Import `resolve_wrapper_path` via `from ..agents import resolve_wrapper_path`; the
  path is independent of `AFM_DIR`; the whole-file rewrite makes repeated invocation
  idempotent; `OSError` propagates (declared error semantics — step 14 of `run_pipeline`
  precedes `run_created`, so no events have fired); nothing is printed
- [ ] **STEP 2 (IMPLEMENTATION)**: extend `goga/pipeline/__init__.py` — `from .afm_config import write_afm_config` and add `"write_afm_config"` to `__all__`
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/pipeline/test_afm_config.py -v`; facade check `python -c "from goga.pipeline import write_afm_config"`
- [ ] **STEP 4 (LOGIC TESTS)**: add the logic tests (verbatim scenarios; monkeypatch the module constant `_AFM_CONFIG_PATH` to `tmp_path / ".afm" / "config.yaml"` — the fixed-path constant is patched, not the filesystem root):
  - [ ] `test_write_afm_config_with_agent_writes_resolved_wrapper_and_static_fields` — `write_afm_config("codex")`; assert the returned Path equals the patched path; `yaml.safe_load(path.read_text()) == {"client": {"command": "/home/goga/bin/codex-as-claude.sh"}, "theme": "goga", "open_browser": False, "proxy": {"enabled": False}, "prompts_dir": "/home/goga/pipeline/prompts"}`; the command value contains `"/home/goga/bin/"` (never a bare name)
  - [ ] `test_write_afm_config_without_agent_omits_client_block` — `write_afm_config(None)`; assert `"client" not in data` and `set(data) == {"theme", "open_browser", "proxy", "prompts_dir"}` (a null command must never be written; this also ports the wrapper-omission semantics of the deleted host tmpfile tests)
  - [ ] `test_write_afm_config_rewrites_whole_file_idempotently` — pre-write garbage (`path.parent.mkdir(); path.write_text("stale: true\n")`); call `write_afm_config("claude")` twice; assert both writes produce the identical five-field document and `"stale" not in data` after each
  - [ ] `test_write_afm_config_unwritable_home_raises_oserror` — patch the path, create the parent, `path.parent.chmod(0o500)`, restore `0o700` on teardown, skip under root (`os.getuid() == 0`); assert `pytest.raises(OSError)`, the config file does not exist afterwards (no partial write), nothing printed (no partial content on any stream)
- [ ] **STEP 5 (DEBUGGING)**: run `pytest tests/pipeline/test_afm_config.py -x` — fix implementation until green
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify facade importability, the signature, the four-constants rule (never configurable), programmatic serialization (YAML nesting for `client`/`proxy`), the fixed home path, and the "do not create or manage the prompts directory" constraint
- [ ] **STEP 7 (LINT)**: `ruff check goga/pipeline/ tests/pipeline/`
- [ ] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 3 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 4: `run_pipeline` — load-and-amend, afm config write, launch layer (goga/pipeline)

Re-algorithmize `goga/pipeline/run_pipeline.py` (declared `location: run_pipeline.py`)
to the 21 contract steps. The signature is UNCHANGED. Three insertions and one changed
call; steps 3–13 and 15–16, 20–21 stay byte-identical in behavior to the current
implementation (discovery, `AFM_DIR` read/resolve, flow path, workflow resolution, skip
merge, amendment facts, `amend_workflow` delivery, `compile_flow`, `_materialize_prompts`,
composition, statuses, completion emission).

**Usages relevant to this task:**
- `convention`: error-handling style, docstring formatting.
- `project-configuration` (`goga/config/.usages/project-configuration.md`): the authored load — `load_project_config()` from the CWD; its declared exception set becomes the clean-error boundary.
- `checkpoints` (goga/config/hooks/.usages/checkpoints.md): `ConfigHooks().amend_config`, `ConfigOverlay.config`/`summary_lines`, hard failure semantics, one load + one delivery.
- `extra-env-carriage` (`goga/docker/.usages/extra-env-carriage.md`): step 17 — decode once, apply above the task env layer, drop engine keys.
- `afm` / `resolve-wrapper-path`: consumed through `write_afm_config` (Task 3).
- `run-flow` (`goga/afm/.usages/run-flow.md`): the subprocess launch contract and its env layer parameter.
- `checkpoints` (goga/pipeline/hooks): `run_created` now fires AFTER the afm configuration write and the layer composition.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare Task 4 — targets `goga/pipeline/run_pipeline.py`, `tests/pipeline/test_run_pipeline.py` (extend), `tests/pipeline/test_run_pipeline_contract.py` (extend)
- [ ] **STEP 1 (CONTRACT TESTS)**: extend `tests/pipeline/test_run_pipeline_contract.py` (expected to FAIL now): `run_pipeline` still importable from the facade with the unchanged signature; the module exposes the load-and-amend surface (`load_project_config`, `ConfigHooks` referenced) — contract-level checks only, behavior is locked by the logic tests below
- [ ] **STEP 2 (IMPLEMENTATION)**: apply the algorithm deltas to `run_pipeline.py` (verbatim from the design — the 21 contract steps, deltas marked):

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

- [ ] **STEP 2 (IMPLEMENTATION)**: add the private module constant `_ENGINE_ENV_KEYS = frozenset({"AFM_DIR", "AFM_DOCKER_FILE_ROOTS", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"})` (verbatim; the same five keys also go into `goga/build/build.py` in Task 6 — a private constant in EACH consumer, never exported)
- [ ] **STEP 2 (IMPLEMENTATION)**: extend the imports: `from ..config import load_project_config` (extend the existing `from ..config import resolve_project_name`), `from ..config.hooks import ConfigHooks`, `from ..docker import decode_extra_env` (a new import statement — the module currently imports nothing from `goga.docker`), `from .afm_config import write_afm_config`, and `import yaml` (the load's error set includes `yaml.YAMLError`)
- [ ] **STEP 2 (IMPLEMENTATION)**: keep every constraint — one load + one delivery; the empty layer `{}` passes as-is (`run_flow` treats it as pure inheritance); docker-level fields (image, proxy, hosts) of the effective config consumed nowhere in-container; the pipeline section is guaranteed present (host structural guard + set/force-only amendments) so NO in-container section guard is added; the process environment is never mutated
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/pipeline/test_run_pipeline_contract.py -v`
- [ ] **STEP 4 (LOGIC TESTS)**: extend `tests/pipeline/test_run_pipeline.py` (verbatim scenarios; reuse the `tests/pipeline/conftest.py` pipeline-tree fixtures and the `PipelineHooks` fake; monkeypatch `goga.pipeline.run_pipeline.load_project_config`, `ConfigHooks.amend_config`, `write_afm_config`, and `run_flow` to record calls; drive `GOGA_EXTRA_ENV` only via `monkeypatch.setenv/delenv`):
  - [ ] `test_run_pipeline_loads_and_amends_before_any_work` — authored config with `pipeline=PipelineConfig(agent="codex", env={"T": "1"})`; `amend_config` returns a real `ConfigOverlay` (effective `pipeline.agent="opencode"`, `summary_lines == ["config amendments: 1 applied", "- tool set pipeline.agent"]`); input `run_pipeline("deploy", project_dir, user_dir, port=9000)`; assert call order load → amend → write_afm_config → emit_run_created → run_flow; `write_afm_config` called once with `"opencode"` (the EFFECTIVE agent); capsys.err contains both summary lines; `run_flow` kwargs `env == {"T": "1"}`, `max_parallel is None`; return `== 0`
  - [ ] `test_run_pipeline_launch_layer_cli_entries_above_task_env_engine_keys_dropped` — effective `pipeline.env = {"T": "cfg", "HTTP_PROXY": "cfg-proxy"}`; `monkeypatch.setenv("GOGA_EXTRA_ENV", encode_extra_env(["T=cli", "AFM_DIR=x"]))`; assert `run_flow` kwargs `env == {"T": "cli"}` (CLI wins over config; engine keys absent) and `os.environ["AFM_DIR"]` unchanged by the call (no process mutation)
  - [ ] `test_run_pipeline_config_load_failure_clean_error_no_events` — `load_project_config` raises `FileNotFoundError(".goga/config.yml not found in project root")`; assert return `== 1`, capsys.err contains `".goga/config.yml not found"`, `emit_run_created == 0` and `emit_run_completed == 0`, `run_flow` and `write_afm_config` not called, no traceback in output
  - [ ] `test_run_pipeline_config_delivery_failure_clean_error_no_events` — `amend_config` raises `ValueError("toolA/hookX: amend_config failed")`; assert return `== 1`, capsys.err contains `"toolA"` and `"amend_config"`, no events, `run_flow`/`write_afm_config` uncalled
  - [ ] `test_run_pipeline_damaged_payload_clean_error_before_run_created` — healthy passthrough config; `monkeypatch.setenv("GOGA_EXTRA_ENV", "###garbage###")`; assert return `== 1`, capsys.err contains `"GOGA_EXTRA_ENV"`, `emit_run_created == 0`, `run_flow` not called (steps 3–16 ran — prompts written — but the return precedes step 18)
  - [ ] `test_run_pipeline_empty_payload_layer_is_effect_task_env_alone` — effective `pipeline.env={"T":"1"}`; `monkeypatch.delenv("GOGA_EXTRA_ENV", raising=False)`; assert `run_flow` kwargs `env == {"T": "1"}`
  - [ ] `test_run_pipeline_empty_composed_layer_pure_inheritance` — effective `pipeline.env={}`; payload absent; assert `run_flow` kwargs `env == {}` and afm still launches (return 0)
  - [ ] `test_run_pipeline_docker_level_fields_unconsumed_silently` — effective config carrying `image="img"`, `pipeline.proxy="http://x"`, `pipeline.hosts={"h":"1"}`; assert return `== 0`, no warning in stderr beyond the summary lines, no docker module touched by the run coordination beyond `decode_extra_env`
- [ ] **STEP 5 (DEBUGGING)**: run `pytest tests/pipeline/ -x` — fix implementation until green (do NOT fix tests)
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify all 21 steps against the CODEMANIFEST algorithm; exactly two environment reads (`AFM_DIR`, `GOGA_EXTRA_ENV`); every pre-existing return path preserved (missing pipeline 1, `AFM_DIR not set`, structural error propagation, 126/127 passthrough); `run_created` after steps 14 and 17; no events on any pre-checkpoint return
- [ ] **STEP 7 (LINT)**: `ruff check goga/pipeline/ tests/pipeline/`
- [ ] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 4 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 5: `main` — in-container load-and-amend entrypoint (goga/build)

Change `goga/build/__main__.py` (declared `location: __main__.py`) so the entrypoint
performs the load-and-amend and hands `build` the EFFECTIVE configuration. The current
file already calls `load_project_config()` unguarded; add the clean-error boundary and
the amend delivery.

**Usages relevant to this task:**
- `convention`: docstring style, relative imports.
- `project-configuration`: the authored load and its exception set.
- `checkpoints` (goga/config/hooks): `amend_config` delivery, summary lines, hard failure semantics.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare Task 5 — targets `goga/build/__main__.py`, `tests/build/test_main.py` (extend)
- [ ] **STEP 1 (CONTRACT TESTS)**: extend `tests/build/test_main.py` with contract checks (expected to FAIL now): `main` references the amend surface (`ConfigHooks`) and forwards the overlay config (assertable via the recorded `build` call — see logic tests)
- [ ] **STEP 2 (IMPLEMENTATION)**: apply to `main()` (verbatim from the design):

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
  Both failure modes are clean stderr errors with exit 1 — ralphex never launches,
  `.ralphex/` is never touched; empty summary → nothing printed
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/build/test_main.py -v`
- [ ] **STEP 4 (LOGIC TESTS)**: extend `tests/build/test_main.py` (verbatim scenarios; monkeypatch `ensure_in_docker` no-op, `sys.argv` to `["goga.build", "plan.md"]`, `load_project_config`, `ConfigHooks.amend_config`, and `goga.build.__main__.build`):
  - [ ] `test_main_loads_amends_and_forwards_effective_config` — authored agent None, effective agent `"codex"` with summary lines, `build` recorded returning 7; assert `build` called exactly once, its config argument IS `overlay.config` (identity), `cli_options["dry_run"] is False` and `skip_review is None`, capsys.err contains the summary line, return `== 7`
  - [ ] `test_main_config_failure_exit_1_ralphex_never_launches` — `load_project_config` raises `ValueError("bad mapping")`; assert return `== 1`, capsys.err contains `"bad mapping"`, `build` not called
  - [ ] `test_main_delivery_failure_exit_1_names_tool` — `amend_config` raises `ValueError("toolB: hook failed on amend_config")`; assert return `== 1`, capsys.err contains `"toolB"`, `build` not called
- [ ] **STEP 5 (DEBUGGING)**: run `pytest tests/build/test_main.py -x` — fix implementation until green
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify exactly one load and one delivery, effective (not authored) configuration forwarded, both failure modes exit 1 before ralphex, summary lines carry tool/path/set-or-forced only
- [ ] **STEP 7 (LINT)**: `ruff check goga/build/ tests/build/`
- [ ] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 5 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 6: `build` — guard move, one decode, both pass layers (goga/build)

Change `goga/build/build.py` (declared `location: build.py`): move the agent value
guard BEFORE the first state write, decode the CLI entries payload once, and compose
each pass env layer (effective task env ⊕ CLI entries, engine keys dropped). Also
update the two documentation-level reachability notes (`run_settings.py`,
`review_config.py`). `_stage_env_layer` is deleted, subsumed by `_compose_pass_env`.

**Usages relevant to this task:**
- `convention`: docstring style, logging (`logger.error(..., extra={"remedy": ...})` for the guard).
- `extra-env-carriage`: step 5 decode once; `_compose_pass_env` = `task_env ⊕ cli_entries ⊖ ENGINE_KEYS`.
- `resolve-wrapper-path`: pre-existing (the pass wrapper resolution is unchanged).
- `checkpoints` (goga/build/hooks): the gate after the agent guard and the defaults sync; no events on any pre-launch failure (steps 0–5).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare Task 6 — targets `goga/build/build.py`, `goga/build/run_settings.py` (docstring), `goga/build/review_config.py` (docstring), `tests/build/test_build.py` (extend)
- [ ] **STEP 1 (CONTRACT TESTS)**: extend `tests/build/test_build.py` contract checks (expected to FAIL now): `build` composes pass layers through the new surface — assertable via the recorded `run_build_pass` `env` kwargs (see logic tests); `_stage_env_layer` no longer exists in the module (`" _stage_env_layer" not in dir(module)` / grep)
- [ ] **STEP 2 (IMPLEMENTATION)**: apply the deltas (verbatim from the design):

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

  `cli_entries` threads from `build` into `_launch_pass` as a parameter (the helper
  stays pure; no module state). Delete `_stage_env_layer`. Add `from ..docker import
  decode_extra_env`. The task env still never reaches the review pass; the CLI entries
  DO reach both (explicit user input, already in the inherited env); dry-run prints pass
  commands without env layers
- [ ] **STEP 2 (IMPLEMENTATION)**: update the reachability docstrings: `goga/build/run_settings.py` (`resolve_run_settings`) and `goga/build/review_config.py` (`validate_review_config` — the `"no review agent resolved: set build.agent or build.review.agent"` message stays) — the no-review-agent error is reachable when neither the authored configuration nor an amendment supplies a review agent
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/build/test_build.py -v`
- [ ] **STEP 4 (LOGIC TESTS)**: extend `tests/build/test_build.py` (verbatim scenarios; reuse the existing `build` scaffolding and `BuildHooks` fake; drive `GOGA_EXTRA_ENV` via `monkeypatch`):
  - [ ] `test_build_guard_satisfied_by_amendment_and_runs_both_pass_layers` — effective config `build.agent="codex"`, `build.env={"T":"cfg"}`, `build.review.env={"R":"1"}`; `monkeypatch.setenv("GOGA_EXTRA_ENV", encode_extra_env(["T=cli"]))`; record `run_build_pass` (return 0) and `sync_ralphex_defaults`; input `build("plan.md", effective_config, {"dry_run": False})`; assert `sync_ralphex_defaults` called BEFORE the first `run_build_pass`; `run_build_pass` calls `[env={"T":"cli"}, env={"R":"1","T":"cli"}]`; return `== 0`
  - [ ] `test_build_agent_guard_rejects_before_any_state_write` — effective `build.agent=None`; input `build("plan.md", effective_config, {"skip_review": True})` (the degenerate skip-run the guard exists for — with review unskipped and no review agent, the step-2 validator would fire first and the guard would be unreachable); assert return `== 1`, `sync_ralphex_defaults` not called (the `.ralphex/` rewrite never starts), `emit_build_started == 0`, `run_build_pass` not called, the output names the agent requirement (`"no build agent resolved"`), and `"no review agent resolved" not in output` (the guard fired, not the validator)
  - [ ] `test_build_damaged_payload_clean_error_no_events_no_launch` — healthy effective config; `monkeypatch.setenv("GOGA_EXTRA_ENV", "zzz")` (invalid b64); input `build("plan.md", effective_config, {})`; assert return `== 1`, no gate/build_started/pass events, `run_build_pass` not called (nothing partially applied)
  - [ ] `test_build_dry_run_prints_commands_without_env_layers` — effective `build.env={"T": "cfg"}` (agent satisfied); `monkeypatch.setenv("GOGA_EXTRA_ENV", encode_extra_env(["T=cli"]))`; `cli_options={"dry_run": True, "skip_manifest_check": True}`; capture stderr (`run_ralphex` prints the pass commands there) and record `run_build_pass` and the `BuildHooks` emissions; assert `"T=cli" not in captured stderr`, `"cfg" not in captured stderr`, `"GOGA_EXTRA_ENV" not in captured stderr`; event structure identical to a non-dry run (`build_started` 1, `pass_started` 2, `pass_completed` 2, `build_completed` 1); `run_build_pass` received `env={"T":"cli"}` (tasks) — the layer travels as data
- [ ] **STEP 5 (DEBUGGING)**: run `pytest tests/build/ -x` — fix implementation until green
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify the guard order (before the first state write — the only ordering change inside the pre-launch sequence), one decode feeding both passes, payload wins over each pass's task env on key conflict, engine keys never enter a composed layer, empty composed layer → `None` (pure inheritance), every pre-launch failure (steps 0–5) fires no events
- [ ] **STEP 7 (LINT)**: `ruff check goga/build/ tests/build/`
- [ ] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 6 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 7: host `build` command — guard removal + env-file ladder (goga/commands/build)

Change `goga/commands/build/build.py` (declared `location: build.py`): delete the host
agent value guard (step 2.2), keep the structural build-section guard (step 2.1), and
restructure `_write_env_file` to the ladder line-list form with the `GOGA_EXTRA_ENV`
payload line. Renumber the in-code step comments (old 8–19 → new 7–18) — the
CODEMANIFEST is the reference.

**Usages relevant to this task:**
- `convention`: docstring style, relative imports.
- `extra-env-carriage`: one source (the same parsed `-e` tuple feeds the raw lines and the payload), two carriers; the engine-line skip rule preserves the documented `-e HTTP_PROXY=...` escape hatch under docker's last-write-wins.
- `checkpoints` (goga/config/hooks): the pre-existing host load-and-amend (step 2) is unchanged.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare Task 7 — targets `goga/commands/build/build.py`, `tests/commands/build/test_build.py` (extend), `tests/commands/build/test_build_config_checkpoint.py` (extend), `tests/commands/test_build.py` (legacy guard tests)
- [ ] **STEP 1 (CONTRACT TESTS)**: extend `tests/commands/build/test_build.py` contract checks (expected to FAIL now): the module no longer contains the host agent guard (`"build.agent is required" not in module source / behavior — see logic tests); `encode_extra_env` is referenced by the launcher module
- [ ] **STEP 2 (IMPLEMENTATION)**: apply the deltas (verbatim from the design):

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

  Import addition: `from ...docker import encode_extra_env` (extend the existing
  import). Keep the 0600 mode and the private tempfile prefix of the existing helper.
  The task env (`build.env`) is NOT written into the env-file. The signal handlers stay
  BEFORE the env-file write; the `finally` unlink and handler restore stay unchanged
- [ ] **STEP 2 (IMPLEMENTATION)**: delete the `TestBuildAgentGuard` class from
  `tests/commands/test_build.py` (`test_build_command_raises_click_exception_when_agent_absent`
  locks the removed step-2.2 host guard; the value guard is in-container now) — keep
  `TestBuildSectionGuard` untouched (the structural guard stays host-side); the
  `TestWriteEnvFile` direct-call tests survive the restructure (containment assertions
  only — the payload line is additive)
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/commands/build/ -v`
- [ ] **STEP 4 (LOGIC TESTS)**: extend `tests/commands/build/test_build.py` (verbatim scenarios; reuse the existing `CliRunner` scaffolding with docker/config/home fakes and the env-file reader of the suite):
  - [ ] `test_host_build_no_agent_guard_launches_container_with_payload` — authored config WITHOUT `build.agent`; input `goga build plan.md -e KEY=V -e HTTP_PROXY=user-proxy`; assert `result.exit_code == 0` (launch reached; container returns 0); env-file lines contain `"KEY=V"` and `"HTTP_PROXY=user-proxy"`; exactly ONE `HTTP_PROXY` line (the launcher's own was skipped); `decode_extra_env(GOGA_EXTRA_ENV line value) == {"KEY":"V","HTTP_PROXY":"user-proxy"}`; `"build.agent is required" not in result.output`
  - [ ] `test_build_host_structural_guard_still_fires` — effective config with `build=None` (section absent); input `goga build plan.md`; assert `ClickException "build section is required in .goga/config.yml to run 'goga build'"`, `exit_code == 1`, `DockerRunner.run` not called
- [ ] **STEP 4 (LOGIC TESTS)**: extend `tests/commands/build/test_build_config_checkpoint.py` so the checkpoint suite reflects the guard split: the host-effective configuration still flows through load → amend → summary → structural guard (no agent guard between them), and an amendment setting `build.agent` on the host does not stop the launch (the value guard is in-container)
- [ ] **STEP 5 (DEBUGGING)**: run `pytest tests/commands/build/ -x` — fix implementation until green
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify the guard split (structural host-side, value in-container), the ladder order + engine-line skip rule + payload line, the payload and CLI lines composed from the same tuple, the task env stays out of the env-file, and the leak-prevention invariant (handlers before the secret file; unlink in finally — the env-file remains the only secret artifact)
- [ ] **STEP 7 (LINT)**: `ruff check goga/commands/build/ tests/commands/build/`
- [ ] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 7 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 8: `run_pipeline_container` — tmpfile retirement + ladder reorder (goga/commands/pipeline)

Change `goga/commands/pipeline/run_pipeline_container.py` (declared `location:
run_pipeline_container.py`): retire the whole afm-config tmpfile flow, remove host
agent resolution, drop `pipeline_env` from the env-file, reorder the ladder with the
payload line, and reduce the mounts. Delete the two retired test files with the code
they locked. Renumber the in-code step comments (steps 5–16) — the CODEMANIFEST is the
reference. Also confirm the `pipeline.py` agent-optionality comment stays accurate (no
behavioral read of `pipeline.agent`/`pipeline.env` remains anywhere in the host cell).

**Usages relevant to this task:**
- `convention`: docstring style, relative imports.
- `extra-env-carriage`: the host half — ladder order, one-source payload, engine-line skip rule (the documented `-e AFM_DOCKER_FILE_ROOTS=...` escape hatch keeps winning), task-env exclusion from the env-file.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare Task 8 — targets `goga/commands/pipeline/run_pipeline_container.py`, `goga/commands/pipeline/pipeline.py` (comment), `tests/commands/pipeline/test_run_pipeline_container.py` (extend + legacy rework), `tests/commands/pipeline/test_run_pipeline_container_afm_config.py` (DELETE), `tests/commands/pipeline/test_run_pipeline_container_resolved_wrapper.py` (DELETE), `tests/integration/test_launcher_tmpfile_integration.py` (DELETE), `tests/integration/test_resolved_wrapper_flow.py` (pipeline-consumer section rework), `tests/integration/test_docker_update_launch_integration.py` (D7 leak-test rework), `tests/integration/test_runtime_isolation.py` (mount-count rework), `tests/integration/test_pipeline_home_integration.py` (base-layer test rework)
- [ ] **STEP 1 (CONTRACT TESTS)**: extend `tests/commands/pipeline/test_run_pipeline_container.py` contract checks (expected to FAIL now): the launcher module no longer references `resolve_wrapper_path` (`"resolve_wrapper_path" not in dir(module)` — the order-independent form; do NOT assert on `sys.modules`) and no longer defines `_write_afm_config_tmpfile`
- [ ] **STEP 2 (IMPLEMENTATION)**: apply the deltas (verbatim from the design):

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

  Import changes: `from ...docker import encode_extra_env` (extend the existing
  import); remove the `resolve_wrapper_path` import. Keep the 0600 mode and the private
  tempfile prefix (`goga-pipeline-env-`) of the existing helper. `config` is consumed
  for `image`/`dockerfile` only; `pipeline.env`/`pipeline.agent` are read nowhere on
  the host
- [ ] **STEP 2 (IMPLEMENTATION)**: delete `tests/commands/pipeline/test_run_pipeline_container_afm_config.py` and `tests/commands/pipeline/test_run_pipeline_container_resolved_wrapper.py` — the wrapper-omission semantics are already ported into `tests/pipeline/test_afm_config.py` (Task 3); the fixed-mount-target absence is asserted by the new scenario below
- [ ] **STEP 2 (IMPLEMENTATION)**: delete `tests/integration/test_launcher_tmpfile_integration.py` (both classes lock the retired tmpfile flow — the tmpfile mount, the 3-mount count, the `_write_afm_config_tmpfile` monkeypatch); its still-relevant leak-prevention intent (env-file unlinked in `finally`, persistent dir survives) is already asserted by the suite's own cleanup tests and the new scenarios below
- [ ] **STEP 2 (IMPLEMENTATION)**: rework the legacy scenarios that lock the retired behavior (per the Gap Analysis inventory — delete the scenario when its premise is gone, rewrite it against the new contract otherwise; never weaken an assertion to mask a contract violation):
  - `tests/commands/pipeline/test_run_pipeline_container.py`: delete
    `test_pipeline_env_file_combines_pipeline_env_and_git` and
    `test_pipeline_env_overrides_git_on_conflict` (pipeline.env never enters the
    env-file); rewrite `test_pipeline_env_file_appends_extra_env_lines`,
    `test_pipeline_env_file_default_extra_env_is_empty`, and
    `test_pipeline_run_forwards_extra_env_to_write_env_file` for the line-list
    `_write_env_file` form (the `GOGA_EXTRA_ENV` payload line is written on every
    launch); rewrite `test_extra_env_file_roots_override_wins` for the inverted
    semantics (the launcher engine line is skipped — exactly one occurrence, the CLI
    one); rewrite `test_home_and_pipeline_env_keys_do_not_override_composed_roots`
    without the pipeline.env premise; rewrite the three-mounts test to exactly 2
    engine mounts (project + afm state)
  - `tests/integration/test_resolved_wrapper_flow.py`: drop the "pipeline consumer:
    afm-config tmpfile client.command" section (the host no longer resolves or writes
    the agent command; the in-container authorship is covered by
    `tests/pipeline/test_afm_config.py`); keep the build-side sections
  - `tests/integration/test_docker_update_launch_integration.py`: rework the D7
    leak tests off the deleted `_write_afm_config_tmpfile` monkeypatch — the env-file
    is the single secret artifact
  - `tests/integration/test_runtime_isolation.py`: rewrite
    `test_run_mounts_exactly_three_engine_mounts_even_with_credentials_present` to
    exactly 2 engine mounts
  - `tests/integration/test_pipeline_home_integration.py`: rewrite
    `test_run_mode_layers_home_env_as_base` (home.env stays the base layer;
    pipeline.env no longer merges into the env-file) and update the `_write_env_file`
    capture wrappers to the restructured signature
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: run `pytest tests/commands/pipeline/ -v`
- [ ] **STEP 4 (LOGIC TESTS)**: extend `tests/commands/pipeline/test_run_pipeline_container.py` (verbatim scenarios; reuse the existing container-launcher scaffolding — docker/config/home fakes and the env-file reader of the suite):
  - [ ] `test_run_pipeline_container_env_file_ladder_and_payload_no_pipeline_env` — home config `env={"H":"1"}` with a `-v /data:/data` run token; effective config `pipeline.env={"T":"cfg"}`, `pipeline.agent="codex"`; `extra_env=("T=cli",)`, `proxy="http://p:1"`; input `run_pipeline_container("deploy", config=effective, extra_env=("T=cli",), proxy="http://p:1")`; assert `lines.index("T=cli") < lines.index("AFM_DIR=...")` (CLI before engine), `"T=cfg" not in` env-file text (`pipeline.env` never enters), `decode_extra_env(payload value) == {"T": "cli"}`, no tmpfile mount among `params["v"]`, `params["v"] == [f"{project}:/workspace", f"{runtime}:/home/goga/pipeline"]`, and the env-file path is unlinked in `finally`
  - [ ] `test_run_pipeline_container_escape_hatch_cli_engine_key_wins` — `extra_env=("AFM_DOCKER_FILE_ROOTS=dXNlcg==",)`; assert the env-file contains the CLI line verbatim and NO second launcher-written `AFM_DOCKER_FILE_ROOTS` line (exactly one occurrence)
  - [ ] `test_run_pipeline_container_payload_line_present_with_no_cli_entries` — `extra_env=()`; assert exactly one `GOGA_EXTRA_ENV=` line (written on EVERY launch), `decode_extra_env(payload_lines[0].split("=", 1)[1]) == {}`, no non-engine `KEY=VALUE` line present (extra_env was empty), runner called exactly once — locks the "on every launch" one-source rule (a regression that skips the payload line when no `-e` is given breaks the carriage silently)
  - [ ] `test_run_pipeline_container_no_tmpfile_and_agent_not_resolved` — a run launch with `pipeline.agent="codex"` configured; assert `params["v"]` has exactly 2 mounts (project + afm state), no file matching `goga-afm-config-*` exists during/after the run, and `"resolve_wrapper_path" not in dir(run_pipeline_container_module)` (no agents import)
- [ ] **STEP 5 (DEBUGGING)**: run `pytest tests/commands/pipeline/ tests/integration/ -x` — fix implementation until green (the ONLY tests touched are the legacy deletions/reworks inventoried in STEP 2 — a test locking retired behavior is removed or rewritten against the new contract, never satisfied by reverting the implementation)
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: verify the tmpfile flow fully retired (no write, no mount, no unlink), no agent resolution on the host, `pipeline.env` absent from the env-file, the payload line present on every run launch, the engine-line skip rule + ladder order, mounts reduced to project + afm state, the signal/leak invariant over the single secret file, and the info forms untouched
- [ ] **STEP 7 (LINT)**: `ruff check goga/commands/pipeline/ tests/commands/pipeline/`
- [ ] **STEP 8 (COMPLETION)**: mark all checkboxes of Task 8 complete
- **→ REVIEW → APPROVAL → NEXT TASK**

### Task 9: `PipelineConfig` docstring alignment (goga/config/project — documentation-level)

Align the implementation docstrings of `goga/config/project/config.py` with the
rewritten property annotations of `goga/config/project/CODEMANIFEST`. No behavioral
change — the loader and the frozen dataclass are untouched; only the stale docstrings
describing the retired host guard are replaced. This is an infrastructure-style
documentation task: code → verification → lint (no TDD cycle — there is no behavior to
test; the existing cell suite must stay green).

**Usages relevant to this task:**
- `convention`: docstring style.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract.**

- [ ] Update the `PipelineConfig.agent` docstring in `goga/config/project/config.py` to: resolved at runtime by the in-container consumer (goga/pipeline) into an absolute wrapper path written into the afm configuration file; this cell does no resolution or validation
- [ ] Update the `PipelineConfig.env` docstring to: applied in-container as the afm launch env layer, above the inherited launch environment; it never travels through the docker launch env-file
- [ ] Remove every remaining occurrence of the retired host-guard sentence ("`goga pipeline` raises a clean ClickException when it needs an agent") from the file
- [ ] Update the `BuildConfig` class docstring (the `agent` field sentence, currently "the consuming ``goga build`` command raises a clean ClickException when it actually needs an agent") to the guard-split reality: the value is guarded by the in-container consumer (`goga/build`) on the effective configuration before the first state write; this cell performs no resolution, validation, or guarding
- [ ] Verify no behavior changed: run `pytest tests/config/ -x` — the existing suite for the cell must pass untouched
- [ ] Lint: `ruff check goga/config/` — fix formatting if necessary

### Task 10: Integration verification — full suite, lint, contract freeze

Final cross-entity verification of the whole topic. Every coding task above is complete
and green; this task verifies the assembled result end-to-end and the contract freeze.
It creates no new product code.

**Usages relevant to this task:**
- `convention`: validation commands (all inside a virtualenv).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only. Fix the implementation, never the contract. Any contract-level need discovered during implementation goes back through review.**

- [ ] Record the contract-freeze baseline BEFORE Task 1 if not already recorded: `git status --porcelain -- '**/CODEMANIFEST' '*/.usages/*' '.goga/usages/*' > /tmp/contract-freeze-baseline.txt` (the pre-existing uncommitted apply-architecture changes are expected in it)
- [ ] Run the full test suite: `pytest tests/ -x` — all tests pass (including the extended suites of Tasks 1–8 and the untouched suites)
- [ ] Run the facade checks: `python -c "from goga.docker import encode_extra_env, decode_extra_env"` and `python -c "from goga.pipeline import write_afm_config"` and `python -c "from goga.afm import run_flow; from goga.pipeline import run_pipeline"`
- [ ] Run the contract lint: `goga lint` — must report 0 errors (83 cells)
- [ ] Run the code lint: `ruff check goga/ tests/` — no findings
- [ ] Verify the contract freeze: `git status --porcelain -- '**/CODEMANIFEST' '*/.usages/*' '.goga/usages/*'` — the output is IDENTICAL to `/tmp/contract-freeze-baseline.txt` (the implementation added no changes under `CODEMANIFEST` or any `.usages/` tree; any contract-level need discovered during implementation goes back through review)
- [ ] Verify the deletions: `test_run_pipeline_container_afm_config.py`, `test_run_pipeline_container_resolved_wrapper.py`, and `tests/integration/test_launcher_tmpfile_integration.py` no longer exist; `goga/docker/extra_env.py` and `goga/pipeline/afm_config.py` exist
- [ ] Confirm the whole-suite secret-safety spot check: no test asserts with real secret values (synthetic markers only)

---

## Validation Commands

All commands run inside the project virtualenv (create it if missing). Python 3.10+ required.

- `pytest tests/ -x`: Run all tests (the full suite — final gate)
- `pytest tests/<cell>/test_<file>.py -v` → e.g. `pytest tests/docker/test_extra_env.py -v`: Run one task's suite (per-task STEP 3/5)
- `ruff check goga/ tests/`: Lint check (line-length 120, target py310)
- `python -c "from goga.docker import encode_extra_env, decode_extra_env"`: Facade check — docker carriage routines
- `python -c "from goga.pipeline import write_afm_config, run_pipeline"`: Facade check — pipeline surface
- `python -c "from goga.afm import run_flow"`: Facade check — afm surface
- `goga lint`: Contract lint — must stay at 0 errors (83 cells)
- `git status --porcelain -- '**/CODEMANIFEST' '*/.usages/*' '.goga/usages/*'`: Contract freeze check — output must be identical before Task 1 and after Task 10

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`goga/docker/extra_env.py`, `goga/pipeline/afm_config.py`, and the six modified files)
- [ ] Every contract entity is accessible from the facade (`encode_extra_env`, `decode_extra_env` from `goga.docker`; `write_afm_config` from `goga.pipeline`)
- [ ] Properties and methods match the declared API (`run_flow`'s `env` parameter; all other signatures unchanged)
- [ ] Descriptions are reflected in behavior (the 21-step `run_pipeline`, the 14-step `build`, the ladder, the guard split, the exit codes)
- [ ] Contract dependencies are met (the eight new/changed import edges; the removed `goga/commands/pipeline → goga/agents` edge)
- [ ] Re-exports are accessible from the facade (none declared — no `->` blocks)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task (all 33 design test scenarios land)
- [ ] Integration tests exist where cross-entity scenarios require them (the docker-boundary carriage is locked by the per-cell boundary tests; the final integration verification task runs the assembled suite)
- [ ] No package boundary was expanded (no new cells; private constants stay private in each consumer)
- [ ] `CODEMANIFEST` files and `.usages/` files were not modified (contract freeze check identical)
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check`, `goga lint` 0 errors, all facade checks)
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `afm`, `checkpoints` ×3 zones, `extra-env-carriage`, `project-configuration`, `resolve-wrapper-path`, `run-flow`)
