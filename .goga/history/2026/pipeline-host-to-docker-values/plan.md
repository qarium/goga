# Plan: `pipeline-host-to-docker-values`

Result of compiling `.goga/history/2026/pipeline-host-to-docker-values/design.md` (verified by the
design-review stage) into a ralphex-compatible execution plan. The CODEMANIFEST contracts are
**already materialized and staged in git** — this plan realigns the Python implementation with them.

## Purpose

Unify the host→container context transfer for the goga pipeline launchers on the build model of
cmd-proxying, and remove automatic agent-credential bind-mounts entirely. After implementation:

- The workflow decision (`-w WORKFLOW` / `--no-workflow`) and the skip names (repeatable
  `-s/--skip`) travel as **in-container argv flags** parsed by `pipeline_cli` and passed to
  `run_pipeline` / `describe_pipeline` as **explicit parameters** — never as `GOGA_*` environment
  variables. The three env vars (`GOGA_WORKFLOW_NAME`, `GOGA_WORKFLOW_DISABLED`,
  `GOGA_SKIP_STAGES`) are removed entirely; stale user-supplied values of those names travel
  verbatim in the env-file and stay **inert** (no warning, no error, no effect). `AFM_DIR` remains
  the only environment read of run coordination.
- The card form (`goga pipeline NAME --info`) forwards the skip names — the same flags produce the
  same composition in card and run forms.
- No launcher adds credential mounts. `goga build` and the pipeline run launcher mount exactly
  their engine mounts; credential provisioning is user-owned via `home.docker.run` / `-e`
  (documented by the already-rewritten `docker-auth-mounts` user guide).

Most important gaps between contract and code: the two command modules currently **fail at import**
(`build.py:16` and `run_pipeline_container.py:34` import the deleted `resolve_credential_mounts`,
which also blocks the full-suite collection); the in-container routines still read the `GOGA_*` env
channel; the run launcher still writes `GOGA_*` entries into the env-file; `-s` is missing from the
argparse run subparser, the card dispatch, and the card launcher argv.

Implementation strategy: per-cell realignment in dependency order — `goga/pipeline` first
(in-container surface the host argv addresses), then `goga/commands/build` (removal only), then
`goga/commands/pipeline` (the host launchers onto the argv channel), then the cross-cell
integration-test migration. Every coding task follows the TDD workflow (contract tests → code →
verification → logic tests → debugging → re-verification → lint).

## Context

### Contract Surface

All signatures below are the **already-materialized contract state** (read-only). The
implementation must match them exactly.

#### Cell `goga/pipeline` (in-container pipeline cell)

**Entity: `run_pipeline`**
- Type: `function` (Routine)
- Declared `location`: `run_pipeline.py`
- Facade obligation: importable from `goga.pipeline`
- Signature: `run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int, workflow: str | None = None, no_workflow: bool = False, skip: list[str] | None = None, parallel: int | None = None) -> exit_code: int`
- Semantic requirements from descriptions:
  - Step 6: resolve the workflow via `resolve_workflow` with the pipeline name and the
    `workflow` / `no_workflow` parameters — the CLI decision arrives as explicit arguments, never
    from the environment.
  - Step 7: apply the `skip` names via `apply_skip_stages` onto the resolved workflow
    (None/empty — no skip).
  - Read `AFM_DIR` directly from the process environment — **the only environment read**; the
    workflow decision and the skip names arrive as parameters.
  - `no_workflow` takes precedence over `workflow` (the host-side launcher rejects the combined
    use; the precedence is defensive — null the name before `resolve_workflow`).
  - The amendment facts derive from the **pre-merge** resolution (a skip-only document synthesized
    over a missing workflow is not a resolution); the delivery carries the **merged** workflow.
  - Steps 8–17 otherwise unchanged (facts, delivery, compile, prompts, run events).
- Imported dependencies: `resolve_workflow`, `apply_skip_stages`, `compile_flow`, `run_flow`,
  hooks zone types (all intra-cell or existing — unchanged).
- Annotation context: header `Usages` (`convention`, `argparse`, `cli_entrypoint`,
  `default_prompts`) + entity annotations (parameter docs for `workflow`/`no_workflow`/`skip`).

**Entity: `describe_pipeline`**
- Type: `function` (Routine)
- Declared `location`: `describe_pipeline.py`
- Facade obligation: importable from `goga.pipeline`
- Signature: `describe_pipeline(name: str, project_dir: Path, user_dir: Path, workflow: str | None, no_workflow: bool, skip: list[str] | None = None) -> card: PipelineCard`
- Semantic requirements from descriptions:
  - Step 3 (new): apply the `skip` names via `apply_skip_stages` onto the resolved workflow
    (None/empty — no skip) — the merge happens BEFORE the amendment delivery, exactly as a run
    does.
  - Step 4: the `WorkflowDecision` derives from `resolved` (**pre-merge**); the delivery (unless
    disabled) carries `workflow_doc` (**merged**); a disabled decision delivers nothing and the
    overlay is the passthrough `WorkflowOverlay` of the merged workflow. Deriving the decision
    from the merged document would misclassify a skip-only-synthesized document as a resolution.
  - Steps 5–8 (renumbered from 4–7): compile (temp dir) → `order_stages` → card build → temp
    cleanup — behavior unchanged.
  - The stage composition equals the composition a run of the same pipeline with the same workflow
    and skip flags would execute.
- Imported dependencies: `apply_skip_stages` (new intra-cell import), `resolve_workflow`,
  `compile_flow`, hooks zone types.

**Entity: `pipeline_cli`**
- Type: `function` (Routine)
- Declared `location`: `cli.py`
- Facade obligation: importable from `goga.pipeline`
- Signature: `pipeline_cli(argv: list[str]) -> exit_code: int` (unchanged)
- Semantic requirements from descriptions:
  - Run subparser: `name` positional; `--info/-i`; `--workflow/-w NAME` and `--no-workflow` and a
    repeatable `--skip/-s NAME` (**all three available with and without `--info`**); `--port`
    integer required only when `--info` is absent; `--parallel N` integer.
  - Dispatch run mode: `run_pipeline(name, project_dir, user_dir, port, workflow=…,
    no_workflow=…, skip=…, parallel=…)`.
  - Dispatch card mode: `describe_pipeline(name, project_dir, user_dir, workflow=…,
    no_workflow=…, skip=…)`.
  - No validation added: flag combinations are host-owned; unknown skip names are the compiler's
    structural error.
- Annotation context: the `argparse` inline practice names the repeatable `-s` and its dual-mode
  availability.

**Entity: `apply_skip_stages`**
- Type: `function` (Routine)
- Declared `location`: `apply_skip_stages.py`
- Facade obligation: importable from `goga.pipeline`
- Signature: unchanged — `apply_skip_stages(workflow: WorkflowDocument | None, skip_stages: list[str]) -> workflow: WorkflowDocument | None`
- Semantic requirements: logic **unchanged and already contract-conformant** (pure,
  non-mutating, empty-no-op, skip-wins, memory verbatim). Only its docstrings still attribute the
  names to the `GOGA_SKIP_STAGES` env channel → docstring alignment (module docstring +
  `skip_stages` arg description: "the repeatable `-s/--skip` flag names passed by run coordination
  and the card").

**Reference entity: `resolve_workflow`** — logic unchanged; docstring alignment only (module
docstring: the decision "arrives from CLI parameters" for both consumers; `workflow_name` arg doc:
"(parameters on both paths)").

#### Cell `goga/commands/pipeline` (host launcher cell)

**Entity: `pipeline` (click command)**
- Type: `function` (click command)
- Declared `location`: `pipeline.py`
- Facade obligation: importable from `goga.commands.pipeline`
- Signature: unchanged (click surface with `skip: tuple[str, ...]`)
- Semantic requirements from descriptions:
  - Step 4 card dispatch: `run_pipeline_info_container(..., workflow=workflow,
    no_workflow=no_workflow, skip=skip)` — **+ skip** (run-form dispatch unchanged).
  - The listing forms silently ignore `-s/--skip` (no dispatch of skip in the listing branch).
  - The run and card forms forward `skip` as parsed — one `-s` flag per name, no validation, no
    defaulting; the run form forwards `parallel` as parsed.
  - Option help texts must not reference the env-var channel: `--no-workflow` drops "(sets
    GOGA_WORKFLOW_DISABLED=1 in-container)" → e.g. "Disable workflow application entirely (run and
    card forms)"; `-s/--skip` drops "(run mode only …)" and "forwarded as GOGA_SKIP_STAGES" →
    "Exclude a stage from the compiled pipeline (run and card forms; repeatable)".
  - Steps 1–3 and 5 unchanged (config load + amendment, form validation 2.1→2.4 including `-w`
    existence and `-w`/`--no-workflow` exclusivity, topic procedure, exit-code propagation).

**Entity: `run_pipeline_container`**
- Type: `function` (Routine)
- Declared `location`: `run_pipeline_container.py`
- Facade obligation: importable from `goga.commands.pipeline`
- Signature: unchanged — `(name, config, extra_env, proxy, hosts, clean, update, workflow, no_workflow, skip, parallel) -> exit_code: int`
- Semantic requirements from descriptions:
  - Step 9 — the workflow decision is a **log-only** decision: `no_workflow` → no log; explicit
    `workflow` → log that name; else the containment-guarded auto-match existence check → log the
    pipeline name exactly when `<cwd>/.goga/workflows/<name>.yml` exists, else no log. The
    decision produces **no env entries**.
  - Step 10 — print `Pipeline running with workflow "<name>"` exactly when the decision is not
    None (the only host-side stdout line besides docker output).
  - Step 11 — the env-file carries **environment layers only** (home.env, git identity,
    `config.pipeline.env`, `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, proxy). No `GOGA_*` key is ever
    written by the launcher.
  - Step 12 — argv: `["-m","goga.pipeline","run",name,"--port",str(port)]` then `["-w", workflow]`
    when explicit, else `["--no-workflow"]` when set, then one `["-s", n]` per skip name, then
    `["--parallel", str(parallel)]` when not None. Mounts: project, persistent afm state,
    afm-config tmpfile — **nothing else** (no credential loop).
  - Constraint: do not write or interpret any `GOGA_WORKFLOW_NAME` / `GOGA_WORKFLOW_DISABLED` /
    `GOGA_SKIP_STAGES` entry — user-supplied values of those names (via `-e` or home.env) may
    travel in the env-file verbatim and stay inert: no warning, no error.
  - Imports: `from ...agents import resolve_wrapper_path` only (`resolve_credential_mounts` gone).

**Entity: `run_pipeline_info_container`**
- Type: `function` (Routine)
- Declared `location`: `run_pipeline_info_container.py`
- Facade obligation: importable from `goga.commands.pipeline`
- Signature: `+(skip: tuple[str, ...])` in the DSL; the **Python** signature carries
  `skip: tuple[str, ...] = ()` (the DSL grammar rejects a default; the Python-level default `()`
  is the same implementation-detail precedent `run_pipeline_container` already uses) so the
  unchanged listing dispatch (which passes no skip) keeps working.
- Semantic requirements from descriptions:
  - `_compose_argv`: card → `["-m","goga.pipeline","run",name,"--info"]` + `-w`/`--no-workflow`
    + one `["-s", n]` per skip entry; listing forms deliberately do not represent skip.
  - The card argv carries the workflow decision and the skip names exactly as given.
  - The minimal shape holds for all three forms: no published port, no env-file, no afm-config
    tmpfile, no persistent afm state mount, no caller-side signal handler.

**Entity: `collect_file_roots`** (comment alignment only)
- Type: `function`; `location`: `file_roots.py`
- The engine-mount constraint now reads "afm state and the config overlay never become roots" —
  two comments in the module drop the "credentials" member ("afm state, config overlay,
  credentials" → "afm state, config overlay"). Logic unchanged.

#### Cell `goga/commands/build` (build launcher cell)

**Entity: `build`**
- Type: `function` (click command)
- Declared `location`: `build.py`
- Facade obligation: importable from `goga.commands.build`
- Signature: unchanged (`plan, proxy, add_host, update, clean, skip_review`)
- Semantic requirements from descriptions (removal only):
  - Mounts: `mounts = [f"{project_dir}:/workspace", f"{runtime_dir}:/workspace/.ralphex"]` — the
    credential loop, its import (`from ...agents import resolve_credential_mounts`, line 16), and
    the "Then each credential mount, read-only." comment tail are deleted.
  - Docstrings: remove credential-mount sentences from the module and routine docstrings.
  - Everything else (env-file, runtime dir, signal handling, argv, params, runner) unchanged.

#### Cell `goga/agents` (facade — already materialized, no code task)

The facade re-exports exactly `resolve_wrapper_path` (`goga/agents/__init__.py` already shrunk;
the `goga/agents/credentials` cell, its practice, and its tests are already deleted). The
implementation removes the two remaining consumer call sites and adds a facade guard test.

### Re-exports

- Name: `resolve_wrapper_path`
  - Source: `Imports` entry `goga/agents/wrapper` (cell `goga/agents`)
  - Facade obligation: must be importable from `goga.agents` — facade check:
    `python -c "from goga.agents import resolve_wrapper_path"`
  - The removed `->resolve_credential_mounts: {}` embedding is gone from the contract;
    `hasattr(goga.agents, "resolve_credential_mounts")` must be `False`.

### Usages Context

- `argparse` (inline, `goga/pipeline`): the in-container CLI surface — `list [--info]`; `run NAME
  [--info] [-w NAME | --no-workflow] [-s NAME]... [--port] [--parallel]`. The `-s` flag:
  `add_argument("--skip","-s", action="append", default=None)`. Relevant to Task 3.
- `cli_entrypoint` (inline, `goga/pipeline`): `__main__.py` stays a thin `pipeline_cli` delegate
  with the in-container docker guard — unchanged by this plan.
- `convention` / `conventions` (`.goga/usages/conventions.md`): docstring style, REPL/test
  organization — applied in every coding task.
- `click` (`.goga/usages/cooks/click.md`): command/option conventions — applied to the `pipeline`
  help-text edits (Task 7).
- `afm` (`.goga/usages/cooks/afm.md`): integration-pattern fragment already realigned (no
  credential mounts; user-guide pointer) — the `run_pipeline_container` docstring references stay
  valid; nothing to consume.
- Consumer docs (already replaced/edited at materialization — they are the specification the code
  must match; **no changes to them in this plan**):
  - `goga/pipeline/.usages/run-pipeline.md` — the explicit-parameter contract, the AFM_DIR-only
    env read, the threading chains.
  - `goga/pipeline/.usages/pipeline-cli.md` — dispatch signatures quoted
    (`run_pipeline(..., workflow=, no_workflow=, skip=, parallel=)`,
    `describe_pipeline(..., skip=)`).
  - `goga/pipeline/.usages/describe-pipeline.md` — `skip` parameter, merge semantics,
    anti-patterns ("pass the names; the merge is in-memory").
  - `goga/commands/pipeline/.usages/pipeline-command.md` — card-form skip forwarding, docker
    shapes (decision travels in the subcommand argv), threading chains.
  - `goga/commands/build/.usages/build.md` — user-owned mounting guidance.
- `docker-auth-mounts` (`.goga/usages/cooks/docker-auth-mounts.md`): now a **user guide**, not a
  launcher practice — no longer wired into any CODEMANIFEST `Usages`. Nothing for the
  implementation to consume. **Recorded to prevent re-wiring.**

### Imported Usages

- `resolve-wrapper-path` from `goga/agents` (imported by `goga/commands/pipeline` only) —
  unchanged; still applied at the wrapper-resolution step
  (`resolve_wrapper_path(config.pipeline.agent)`). After Task 4 the build cell has no
  `goga/agents` dependency.

### Local Usages

None. The design's `.usages/` Update section confirms: all five affected usage files are status
**current** (replaced/edited at materialization), `resolve-credential-mounts.md` is deleted, and
**no new `.usages/` files** are needed — no new functional domain appears (skip threading belongs
to the existing pipeline/cli/run domains already covered). This plan creates no usage files.

### External Dependencies

- `click` — the `pipeline` and `build` host commands (help texts, ClickException paths).
- `argparse` (stdlib) — the in-container CLI parser.
- PyYAML — config/workflow/DSL parsing (unchanged usage).
- pytest + `unittest.mock` / monkeypatch — test framework; mock-Docker fixtures; no real docker
  in tests.
- `ruff` — lint (`ruff check goga/`).
- `goga` CLI — `goga lint` (DSL validation over all cells).

## Facts

- The architecture plan (`.goga/history/2026/pipeline-host-to-docker-values/arch.md`) is already
  materialized into the CODEMANIFEST cells (apply-architecture stage, `goga lint` green over 81
  cells). The five changed manifests are staged in git — the design consumes them as the source of
  truth.
- `goga/agents/credentials/` (cell, implementation, tests), `goga/agents/.usages/
  resolve-credential-mounts.md`, `tests/agents/credentials/…`, and
  `tests/agents/test_facade_credentials.py` are already deleted.
- The two command modules currently fail at import: `goga/commands/build/build.py:16` and
  `goga/commands/pipeline/run_pipeline_container.py:34` import the deleted
  `resolve_credential_mounts`. This also blocks the full-suite collection today — the full
  `pytest tests/ -x` goes green only after Tasks 4 and 5 land (per-task validation commands are
  scoped accordingly).
- All in-repo call sites of `run_pipeline` / `describe_pipeline` pass at most the stable positional
  prefix plus keywords — the signature insertions (which move `parallel`'s position in
  `run_pipeline`) are safe as long as call sites keep using keywords.
- The type chain is coherent end to end: click `tuple[str, ...]` → argv `-s N` per name →
  argparse `action="append"` yields `list[str] | None` → `run_pipeline(skip: list[str] | None)` →
  `apply_skip_stages(skip or [])` takes `list[str]`.
- `run_pipeline_info_container.skip` carries no DSL default (`= ()` is rejected by the DSL
  signature grammar); the Python-level default `()` lives in the Python signature.
- Unknown skip names fail at `compile_flow`'s strict check (`StructuralError`) — the card now
  fails identically, which is the equivalence the contract wants. Host-side performs no skip-name
  validation or dedup anywhere.
- `apply_skip_stages` logic is already contract-conformant; only its docstrings are stale.
- Existing test fixtures: `tests/pipeline/conftest.py` (DSL stage/phase files, workflow files),
  `tests/commands/pipeline/` mock-Docker fixtures (`_mock_docker_internals`, env-file capture),
  `tests/commands/conftest.py` (click runner). Convention: docstring-first tests, asserts on exact
  argv lists / call kwargs; no real docker.
- `compile_flow`'s unknown-skip strict check and `resolve_workflow`'s rule set (incl. the
  containment guard) are unchanged by this plan.

### Entity Interaction and Data Flow (verified — transfer verbatim)

Interaction diagram:

```
 HOST                                    |  CONTAINER (docker run ... python3 -m goga.pipeline ...)
                                         |
 goga pipeline NAME [-w WF] [--no-workflow] [-s N]... [-p N]
   │                                    |
   ├─ pipeline (click)                  |
   │   validation: -w file exists,     |
   │   -w XOR --no-workflow             │
   │                                    |
   ├─ RUN FORM ────────────────────────►│  argv: -m goga.pipeline run NAME --port P
   │   run_pipeline_container           │        [-w WF] [--no-workflow] [-s N]... [--parallel N]
   │     workflow log decision          │   pipeline_cli (argparse)
   │     env-file (env layers ONLY)     │     ├─ run mode  → run_pipeline(workflow=, no_workflow=, skip=, parallel=)
   │     docker run (no cred mounts)    │     │               resolve_workflow ─ apply_skip_stages ─ hooks
   │                                    │     │               compile_flow ─ run_flow (afm)
   ├─ CARD FORM ───────────────────────►│     └─ --info    → describe_pipeline(workflow=, no_workflow=, skip=)
   │   run_pipeline_info_container      │                     resolve_workflow ─ apply_skip_stages ─ hooks
   │     argv: run NAME --info          │                     compile_flow (temp) ─ card
   │       [-w WF|--no-workflow]        │
   │       [-s N]...                    |
   │                                    |
 goga build PLAN (no credential mounts; user mounts via home.docker.run / -e)
```

**Run form (values on the argv channel):**

1. `pipeline` (click) validates form + `-w` existence + exclusivity, resolves proxy/hosts,
   dispatches `run_pipeline_container(name=..., workflow=..., no_workflow=..., skip=...,
   parallel=...)` — `skip` is the raw click tuple, forwarded as parsed (no validation, no dedup).
2. `run_pipeline_container` → `_run_named`: allocates the port, prepares the runtime dir,
   installs signal handlers, resolves the wrapper path, writes the afm-config tmpfile.
3. Step 9 — `_resolve_workflow_log_name(workflow, no_workflow, name)` decides ONLY the log line:
   `no_workflow` → None; explicit `workflow` → that name; else the containment-guarded auto-match
   existence check → the pipeline name or None.
4. Step 10 — print `Pipeline running with workflow "<name>"` when the decision is not None.
5. Step 11 — `_build_env_file` writes environment layers only (home.env, git identity,
   `config.pipeline.env`, `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, proxy). No `GOGA_*` key is ever
   written by the launcher; a user-supplied `GOGA_*` entry (via `-e`, `home.env`, or
   `config.pipeline.env`) travels verbatim and stays inert.
6. Step 12 — argv assembly: `["-m","goga.pipeline","run",name,"--port",str(port)]` then
   `["-w", workflow]` when explicit, else `["--no-workflow"]` when set, then one `["-s", n]` per
   skip name, then `["--parallel", str(parallel)]` when not None. Mounts: project, persistent afm
   state, afm-config tmpfile — nothing else.
7. In-container: `pipeline_cli` parses (`-w`, `--no-workflow`, `-s` repeatable, `--port`,
   `--parallel`), dispatches `run_pipeline(name, project_dir, user_dir, port, workflow=...,
   no_workflow=..., skip=..., parallel=...)`.
8. `run_pipeline`: resolves the workflow via the shared rule set from the **parameters**, merges
   `skip or []` via `apply_skip_stages`, delivers the amendment with the merged workflow,
   compiles, materializes prompts, runs afm.

**Card form:** `pipeline` → `run_pipeline_info_container(name, info=True, ..., skip=skip)` → argv
`run NAME --info [-w WF | --no-workflow] [-s N]...` → `pipeline_cli` →
`describe_pipeline(..., skip=...)` → same merge and compilation machine as the run.

**Build form:** `build` assembles `mounts = [project:/workspace, runtime:/workspace/.ralphex`] —
the credential loop and its import are deleted.

### Entity Dependencies

- `goga/commands/pipeline` → `goga/agents` (`resolve_wrapper_path` only), → `goga/pipeline`
  (Usages-only; the runtime boundary is docker).
- `goga/commands/build` → no `goga/agents` dependency after Task 4 (the
  `resolve_credential_mounts` import is removed; the manifest carries no `goga/agents`
  Imports).
- `goga/pipeline` → `goga/pipeline/compiler`, `goga/pipeline/hooks`, `goga/pipeline/workflow`
  (unchanged by this design).
- Design/implementation order (dependency-driven): pipeline cell first (in-container surface),
  then the two command cells (they address that surface), then tests.

## Gap Analysis

Comparing the materialized contracts with the current code (verified code gaps from the design's
traces):

- Missing contract entities: none (pure realignment).
- `goga/pipeline/run_pipeline.py`: signature is `(name, project_dir, user_dir, port,
  parallel=None)` — lacks `workflow`/`no_workflow`/`skip`; steps 6–7 read
  `GOGA_WORKFLOW_DISABLED` / `GOGA_WORKFLOW_NAME` / `GOGA_SKIP_STAGES` from the environment;
  docstrings and the `WorkflowSyntaxError` Raises clause cite the env channel.
- `goga/pipeline/describe_pipeline.py`: `skip` parameter missing; no in-memory skip merge step;
  module docstring carries the `GOGA_SKIP_STAGES` paragraph.
- `goga/pipeline/cli.py`: `-s` not declared on the run subparser; `-w`/`--no-workflow` help texts
  wrongly say "(--info mode only)" and cite `GOGA_WORKFLOW_*`; `_run_execution` forwards only
  `parallel`; `_run_card` forwards no `skip`; module docstring dispatch note lacks skip.
- `goga/commands/pipeline/pipeline.py`: card dispatch (step 4) omits `skip`;
  `--no-workflow`/`-s` help texts reference the env-var channel.
- `goga/commands/pipeline/run_pipeline_container.py`: `_resolve_workflow_env` also produces
  `GOGA_WORKFLOW_NAME`/`GOGA_WORKFLOW_DISABLED` env entries (defect against step 9's log-only
  contract); `_build_env_file` also writes `GOGA_SKIP_STAGES=<csv>` and the workflow env entries;
  the mounts loop appends `resolve_credential_mounts()` entries (import already deleted →
  **ImportError at import**); argv assembly appends only `--parallel`; docstrings describe the env
  channel and credential mounts.
- `goga/commands/pipeline/run_pipeline_info_container.py`: signature lacks `skip`; `_compose_argv`
  card branch lacks the per-name `-s`.
- `goga/commands/pipeline/file_roots.py`: two comments still enumerate "credentials" among engine
  mounts.
- `goga/commands/build/build.py`: imports the deleted `resolve_credential_mounts` (line 16 →
  **ImportError at import**); the credential loop (lines ~422–425) and the comment tail; module
  docstring credential sentences.
- `goga/pipeline/apply_skip_stages.py`, `goga/pipeline/resolve_workflow.py`: docstrings still
  attribute names/decisions to the env channel.
- Test coverage gaps: ~10 existing test files encode the removed `GOGA_*` env channel premise
  (env-set setups, env-file entry assertions, one test asserting the old behavior verbatim,
  exact-kwargs dispatch asserts); two credential-mount integration test files must be deleted and
  two integration files monkeypatch the deleted symbol (they break at collection until migrated).

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).

> **Global implementation rules (from the design — apply to every task)**:
> - **`CODEMANIFEST` files are read-only.** If implementation does not match the contract, fix the
>   implementation — never fix the contract.
> - Do NOT re-add any `GOGA_WORKFLOW_NAME` / `GOGA_WORKFLOW_DISABLED` / `GOGA_SKIP_STAGES` read or
>   write anywhere in `goga/` or `tests/`. The only allowed mention in the whole change-set is the
>   inertness Constraint already present in `run_pipeline_container`'s manifest.
> - `run_pipeline`/`describe_pipeline` parameter insertion moves `parallel`'s position in the
>   signature; all in-repo call sites use keywords — keep it that way.
> - Keep `_resolve_workflow_log_name`'s containment guard: an auto-match name escaping
>   `.goga/workflows/` is a silent no-log miss, never a wider-filesystem resolve.
> - Help texts are contract surface: the click `--no-workflow`/`-s` helps and the argparse
>   `-w`/`--no-workflow`/`-s` helps must not reference the env-var channel or "--info mode only".
> - The `docker-auth-mounts` cook is a user guide now — never wire it back into a CODEMANIFEST
>   `Usages` header.
> - Pre-existing state: the full suite is red at collection (the two broken imports) until Tasks
>   4–5 land; use each task's scoped validation command.

### Task 1: `run_pipeline` explicit-parameter channel (goga/pipeline)

Make run coordination receive the workflow decision and the skip names as explicit parameters —
replacing the `GOGA_WORKFLOW_*` / `GOGA_SKIP_STAGES` environment reads — and align the docstrings
of `run_pipeline`, `apply_skip_stages`, and `resolve_workflow` with the parameter channel. After
this task `AFM_DIR` is the only environment read of run coordination.

**Contract entity**: `run_pipeline` (location `run_pipeline.py`), signature
`run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int, workflow: str | None = None, no_workflow: bool = False, skip: list[str] | None = None, parallel: int | None = None) -> exit_code: int`.
Docstring-only alignment for `apply_skip_stages` (`apply_skip_stages.py`) and `resolve_workflow`
(`resolve_workflow.py`) — logic unchanged. Facade: all importable from `goga.pipeline`.

**Usages relevant to this task:**
- `convention`: docstring style (Google-style Args/Raises), error-handling style, intra-package
  imports.
- `run-pipeline` (consumer doc, already current): the explicit-parameter contract and the
  AFM_DIR-only env read this task implements — match it exactly.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm delta (from the design — verbatim):

```
1. Signature: def run_pipeline(name, project_dir, user_dir, port,
     workflow: str | None = None, no_workflow: bool = False,
     skip: list[str] | None = None, parallel: int | None = None) -> int
2. Step 6: workflow_name = None if no_workflow else workflow
           resolved = resolve_workflow(name, workflow_name, no_workflow)
3. Step 7: workflow = apply_skip_stages(resolved, skip or [])
   # the GOGA_SKIP_STAGES read + comma-split is deleted; AFM_DIR stays the only env read
4. Steps 8-17: UNCHANGED (facts from (no_workflow, workflow_name, resolved); delivery with
   the merged workflow; compile; prompts; run_flow; events)
5. Docstrings: routine docstring, Raises (WorkflowSyntaxError clause cites no_workflow, not
   GOGA_WORKFLOW_DISABLED), parameter docs for workflow/no_workflow/skip.
```

Verified trace checkpoints for this task: step 4's `workflow_name = None if no_workflow else
workflow` + `resolve_workflow(...)` keeps the double enforcement (input nulled + rule-set step 1);
`skip or []` normalizes `None`/`[]` to the no-op path and matches
`apply_skip_stages(skip_stages: list[str])`; `_resolve_amendment_facts(match, pipeline_path,
no_workflow, workflow_name, resolved)` stays unchanged — the decision derives from the PRE-merge
resolution. Docstring alignments for the two reference modules: `apply_skip_stages` — module
docstring and `skip_stages` arg: "the comma-split GOGA_SKIP_STAGES container env var" → "the
repeatable `-s/--skip` flag names passed by run coordination and the card"; `resolve_workflow` —
module docstring: "whose decision arrives from the container environment" → "whose decision
arrives from CLI parameters"; "(`run_pipeline` reads env; `describe_pipeline` reads CLI)" → "(both
`run_pipeline` and `describe_pipeline` receive their decision as parameters)"; `workflow_name` arg
doc: "(env on the run path, CLI flags on the card path)" → "(parameters on both paths)".

- [x] **Contract tests**: in `tests/pipeline/test_run_pipeline_contract.py` — assert the facade
      import (`from goga.pipeline import run_pipeline`) and the exact signature shape via
      `inspect.signature` (parameters `workflow: str | None = None`, `no_workflow: bool = False`,
      `skip: list[str] | None = None`, `parallel: int | None = None` after `port`); assert
      `apply_skip_stages` and `resolve_workflow` signatures unchanged (expected to fail at this
      stage — the parameters do not exist yet)
- [x] **Code**: rewrite the signature of `run_pipeline` in `goga/pipeline/run_pipeline.py` per the
      algorithm delta (insert `workflow`/`no_workflow`/`skip` before `parallel`)
- [x] **Code**: replace steps 6–7 — delete the three env reads
      (`GOGA_WORKFLOW_DISABLED`, `GOGA_WORKFLOW_NAME`, `GOGA_SKIP_STAGES` + comma-split); resolve
      via `workflow_name = None if no_workflow else workflow; resolved = resolve_workflow(name,
      workflow_name, no_workflow)`; merge via `workflow = apply_skip_stages(resolved, skip or [])`
- [x] **Code**: update the routine docstring, Raises clause (`WorkflowSyntaxError` cites
      `no_workflow`, not `GOGA_WORKFLOW_DISABLED`), and the Args docs for
      `workflow`/`no_workflow`/`skip`/`parallel`
- [x] **Code**: docstring-only alignment in `goga/pipeline/apply_skip_stages.py` (module docstring
      + `skip_stages` arg doc) and `goga/pipeline/resolve_workflow.py` (module docstring +
      `workflow_name` arg doc) — no logic changes
- [x] **Interface verification**: `pytest tests/pipeline/test_run_pipeline_contract.py -x` — all
      pass
- [x] **Logic tests**: migrate the env-driven suites onto parameters, preserving the scenario
      matrices, and add the new channel test:
      - `tests/pipeline/test_run_pipeline_workflow.py` — the 8 env-driven resolution tests
        (`GOGA_WORKFLOW_NAME` / `GOGA_WORKFLOW_DISABLED` setenv → assert `compile_flow` kwargs)
        rewrite onto explicit parameters (`workflow=` / `no_workflow=`), preserving the
        precedence/auto-match/containment scenario matrix
      - `tests/pipeline/test_run_pipeline.py` — the skip-stage class
        (`monkeypatch.setenv("GOGA_SKIP_STAGES", ...)`, ~lines 482–560) rewrites to `skip=[...]`
        parameter passing
      - `tests/pipeline/test_run_pipeline_hooks.py` — the decision-kind tests driven by setenv
        (~lines 312, 429, 433, 438–439) rewrite to parameters; the shared `_isolate`-style delenv
        helper may be dropped
      - migration of `tests/pipeline/test_run_pipeline_contract.py`: the two signature tests
        (`test_run_pipeline_signature_has_optional_parallel` ~line 61,
        `test_run_pipeline_signature_unchanged` ~line 105) assert the NEW parameter list
        (`workflow`/`no_workflow`/`skip` before `parallel`); the env-decision tests
        (`test_run_pipeline_delegates_workflow_resolution` ~line 116,
        `test_run_pipeline_disabled_env_nulls_the_explicit_name` ~line 134) rewrite from
        `setenv("GOGA_*")` to explicit parameters (`workflow=` / `no_workflow=`); the
        `TestRunPipelineWorkflowContract`/`TestRunPipelineDelegatesWorkflowResolution` class
        docstrings and the `test_run_pipeline_forwards_none_workflow_when_no_env` premise drop
        the env-channel wording; the harmless `delenv("GOGA_*")` calls in
        `TestRunPipelineProjectNameContract` may stay
      - new `test_run_pipeline_receives_workflow_from_parameters_not_env`: setup — `tests/pipeline`
        fixtures; `monkeypatch.setenv("GOGA_WORKFLOW_NAME","zzz")`,
        `setenv("GOGA_SKIP_STAGES","zzz")`, `AFM_DIR` to tmp; input —
        `run_pipeline("deploy", project_dir, user_dir, 50321, workflow="hardening")` (workflow
        file present); trace — `→ resolve_workflow("deploy","hardening",False) → parse
        hardening.yml → compile with it` — env values never read; assertions — the compiled flow
        (or the compile_flow mock kwargs) reflects `hardening`, not `zzz`; no stage named `zzz` is
        skipped. Sufficiency: AFM_DIR-only env read — the core of the channel unification
      - keep/verify `test_run_pipeline_afm_dir_unset_raises`: input — `run_pipeline(...)` with
        `monkeypatch.delenv("AFM_DIR")`; assertions — `RuntimeError("AFM_DIR not set")`.
        Sufficiency: AFM_DIR remains required and is the only env read
- [x] **Debugging**: `pytest tests/pipeline -x` — fix implementation code until all tests pass
      (do NOT fix test code to make a broken implementation pass)
- [x] **Contract re-verification**: facade import works; signature matches the manifest exactly;
      steps 8–17 behavior unchanged (facts from pre-merge resolution, delivery with merged
      workflow)
- [x] **Lint**: `ruff check goga/` — fix formatting if necessary

### Task 2: `describe_pipeline` skip merge (goga/pipeline)

Give the card the same in-memory skip merge a run applies: `+(skip: list[str] | None = None)`, a
new merge step between resolution and amendment delivery, decision derivation from the **pre-merge**
resolution, delivery carrying the **merged** document.

**Contract entity**: `describe_pipeline` (location `describe_pipeline.py`), signature
`describe_pipeline(name: str, project_dir: Path, user_dir: Path, workflow: str | None, no_workflow: bool, skip: list[str] | None = None) -> card: PipelineCard`.
New intra-cell import: `apply_skip_stages`. Facade: importable from `goga.pipeline`.

**Usages relevant to this task:**
- `describe-pipeline` (consumer doc, already current): `skip` parameter semantics — "merged
  exactly as a run with the same flags merges them; `None` and empty both mean no skip"; the
  anti-pattern "Do not apply skip by rewriting the workflow-file — the merge is in-memory; pass
  the names".
- `convention`: docstring style, intra-package imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm delta (from the design — verbatim):

```
1. Signature: +(skip: list[str] | None = None)
2. Step 2: resolved = resolve_workflow(name, workflow, no_workflow)
3. NEW Step 3: workflow_doc = apply_skip_stages(resolved, skip or [])
4. Step 4: decision derivation reads `resolved` (PRE-merge):
   - no_workflow            -> disabled
   - resolved is None       -> silent-miss          # a skip-only synthesized doc is NOT a resolution
   - workflow not in (None,"") -> explicit
   - else                   -> auto-match
   delivery (unless disabled) carries `workflow_doc` (MERGED); disabled -> passthrough
   WorkflowOverlay(workflow=workflow_doc, provenance=[])
5. Steps 5-8: renumber comments 4->5 .. 7->8; behavior unchanged
6. Import apply_skip_stages; module docstring: replace the GOGA_SKIP_STAGES paragraph with the
   CLI-skip merge paragraph; skip param doc.
```

Verified trace checkpoints: the merge happens BEFORE the amendment delivery, exactly as the run
does; the `WorkflowDecision` derives from `resolved` (pre-merge) while the delivery carries
`workflow_doc` (merged) — mirroring `run_pipeline` steps 8–9 one-to-one; the disabled branch is
the passthrough `WorkflowOverlay` of the merged workflow.

- [x] **Contract tests**: in `tests/pipeline/test_describe_pipeline.py` — assert the facade import
      and the signature gains `skip: list[str] | None = None` after `no_workflow` (expected to
      fail at this stage)
- [x] **Code**: add the `skip` parameter to `goga/pipeline/describe_pipeline.py`; import
      `apply_skip_stages`
- [x] **Code**: insert the merge step (`workflow_doc = apply_skip_stages(resolved, skip or [])`)
      after resolution; derive the decision from `resolved` (pre-merge) per the matrix above;
      deliver with `workflow_doc` (merged); the disabled passthrough wraps `workflow_doc`;
      renumber the step comments 4→5 … 7→8
- [x] **Code**: module docstring — replace the `GOGA_SKIP_STAGES` paragraph with the CLI-skip
      merge paragraph; add the `skip` param doc
- [x] **Interface verification**: `pytest tests/pipeline/test_describe_pipeline.py -x` — all pass
- [x] **Logic tests** (new scenarios in `tests/pipeline/test_describe_pipeline.py`):
      - `test_describe_pipeline_applies_skip_names`: setup — stages DSL with stages `s1,s2,s3`; no
        workflow file; `skip=["s2"]`; input — `describe_pipeline("deploy", project_dir, user_dir,
        None, False, skip=["s2"])`; trace — `→ resolve_workflow → None → apply_skip_stages(None,
        ["s2"]) → synthesized doc → compile_flow removes s2 + reconnects → order_stages`;
        assertions — `[s.id for s in card.stages] == ["s1","s3"]`. Sufficiency: card-side skip
        merge over a workflow-less pipeline ("skip applies to a workflow-less pipeline too")
      - `test_skip_none_and_empty_cards_identical`: run `describe_pipeline` twice with
        `skip=None` and `skip=[]`; assertions — identical card contents (name, description, stage
        ids, provenance). Sufficiency: the None/[] equivalence stated by both usages and the
        contract
      - `test_describe_pipeline_unknown_skip_name_raises_structural_error`: setup — stages DSL
        `s1,s2`; `skip=["nope"]`; input — `describe_pipeline("deploy", ..., skip=["nope"])`; trace
        — `→ apply_skip_stages → compile_flow step 4pre strict check → StructuralError`;
        assertions — `pytest.raises(StructuralError)`; the message names the unknown stage; no
        temp flow-file remains. Sufficiency: name validation stays in the compiler — the card
        fails exactly as a run does
      - `test_card_skip_only_over_missing_workflow_is_silent_miss`: setup — NO workflow file
        anywhere; `skip=["s2"]`; input — `describe_pipeline("deploy", ..., None, False,
        skip=["s2"])` with the delivery mocked/spied; trace — `resolved=None →
        apply_skip_stages synthesizes a doc → decision derives from `resolved` →
        kind="silent-miss"` (layer active onto the empty base), NOT auto-match/explicit;
        assertions — the delivery still runs (layer active) with a workflow that carries only the
        skip; the decision kind is silent-miss. Sufficiency: guards the pre-merge decision
        derivation — deriving from the merged document would misclassify skip-only synthesis as a
        resolution (the run path documents this exact rule)
- [x] **Debugging**: `pytest tests/pipeline/test_describe_pipeline.py tests/pipeline -x` — fix
      implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: signature matches the manifest; the card is still read-only
      (no afm launch, no run events, temp flow-file removed); the decision/delivery split matches
      `run_pipeline` steps 8–9 one-to-one
- [x] **Lint**: `ruff check goga/` — fix formatting if necessary

### Task 3: `pipeline_cli` dual-mode `-s` and workflow threading (goga/pipeline)

Declare the repeatable `-s/--skip` on the argparse run subcommand (both modes), fix the stale
`-w`/`--no-workflow` help texts, and thread the workflow decision and skip names into both
dispatch calls.

**Contract entity**: `pipeline_cli` (location `cli.py`); signature unchanged
(`pipeline_cli(argv: list[str]) -> exit_code: int`). Facade: importable from `goga.pipeline`.

**Usages relevant to this task:**
- `argparse` (inline): `add_argument("--skip","-s", action="append", default=None)`; the run
  surface is `run NAME [--info] [-w NAME | --no-workflow] [-s NAME]... [--port] [--parallel]`.
- `pipeline-cli` (consumer doc, already current): dispatch signatures quoted —
  `run_pipeline(NAME, project_dir, user_dir, PORT, workflow=<WF or None>, no_workflow=<bool>,
  skip=<names or None>, parallel=<N or None>)`; `describe_pipeline(NAME, project_dir, user_dir,
  workflow=<WF or None>, no_workflow=<bool>, skip=<names or None>)`.
- `cli_entrypoint` (inline): unchanged by this task — `__main__.py` stays a thin `pipeline_cli`
  delegate with the in-container docker guard; `pipeline_cli` remains a pure parse-and-dispatch
  routine defined in the cli module. Do not move logic into `__main__`.
- `convention`: docstring style, intra-package imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm delta (from the design — verbatim):

```
1. _build_parser — run subparser additions/fixes:
   - add: run_parser.add_argument("--skip","-s", action="append", default=None,
           help="exclude a stage from the composition (run and card; repeatable)")
   - fix: --workflow help — drop "(--info mode only; a run picks its workflow up from the
           GOGA_WORKFLOW_* env vars)" -> "apply this workflow (run and card modes)"
   - fix: --no-workflow help — drop "(--info mode only)" -> "disable workflow application
           (run and card modes)"
2. _run_execution: return run_pipeline(args.name, project_dir, user_dir, args.port,
     workflow=args.workflow, no_workflow=args.no_workflow, skip=args.skip,
     parallel=args.parallel)
3. _run_card: card = describe_pipeline(args.name, project_dir, user_dir,
     workflow=args.workflow, no_workflow=args.no_workflow, skip=args.skip)
4. No validation added: flag combinations are host-owned; unknown skip names are the
   compiler's structural error.
```

Verified trace checkpoint: argparse `append` yields `list[str] | None`, matching
`skip: list[str] | None`. Post-check `--port` required without `--info` (unchanged, exit 2 via
`run_parser.error`).

- [x] **Contract tests**: in `tests/pipeline/test_pipeline_cli.py` — assert the run subparser
      declares `--skip`/`-s` with `action="append"` and `default=None`; assert `-w`,
      `--no-workflow`, `-s` bind in both info and run modes (expected to fail at this stage)
- [x] **Code**: add the `--skip`/`-s` argument to the run subparser in `goga/pipeline/cli.py`
      (`_build_parser`) with the help text above
- [x] **Code**: fix the `--workflow`/`--no-workflow` help texts (drop "(--info mode only)" and the
      `GOGA_WORKFLOW_*` wording) per the algorithm delta
- [x] **Code**: `_run_execution` — forward `workflow=args.workflow, no_workflow=args.no_workflow,
      skip=args.skip` to `run_pipeline`; `_run_card` — forward the same three to
      `describe_pipeline`
- [x] **Code**: update the module docstring dispatch note and the `pipeline_cli` docstring argv
      examples (include a `-s` example)
- [x] **Interface verification**: `pytest tests/pipeline/test_pipeline_cli.py -x` — all pass
- [x] **Logic tests** (in `tests/pipeline/test_pipeline_cli.py`):
      - `test_pipeline_cli_run_threads_workflow_and_repeatable_skip`: setup — `tests/pipeline/
        conftest.py` stages DSL fixture + `hardening.yml` workflow;
        `mock.patch("goga.pipeline.cli.run_pipeline")`; input —
        `pipeline_cli(["run","deploy","--port","50321","-w","hardening","-s","build","-s","test"])`;
        trace — `pipeline_cli(argv) → _build_parser() → parse_args → Namespace(skip=["build",
        "test"], workflow="hardening", port=50321) → _run_execution(args, project_dir, user_dir)
        → run_pipeline("deploy", project_dir, user_dir, 50321, workflow="hardening",
        no_workflow=False, skip=["build","test"], parallel=None)`; assertions —
        `mock_run.assert_called_once()`; `kwargs["workflow"] == "hardening"`;
        `kwargs["skip"] == ["build","test"]`; `kwargs["no_workflow"] is False`;
        `kwargs["parallel"] is None`. Sufficiency: pins the argv→parameter threading of the whole
        new channel at the CLI seam; regresses any revert to env-var reads
      - `test_pipeline_cli_card_threads_skip`: setup — `mock.patch(
        "goga.pipeline.cli.describe_pipeline")`; input —
        `pipeline_cli(["run","deploy","--info","-s","build"])`; trace — `→ _run_card →
        describe_pipeline("deploy", project_dir, user_dir, workflow=None, no_workflow=False,
        skip=["build"])`; assertions — `kwargs["skip"] == ["build"]` (plus workflow None /
        no_workflow False). Sufficiency: the card side of the dual-mode `-s`
      - `test_skip_absent_yields_none_not_empty_list`: input —
        `pipeline_cli(["run","deploy","--port","50321"])`; assertions — `kwargs["skip"] is None`
        (argparse append default) — None and [] both mean no-skip downstream. Sufficiency: pins
        the `list[str] | None` contract at the parse seam
      - migration: DELETE `test_pipeline_cli_run_ignores_workflow_flags` (currently at
        `tests/pipeline/test_pipeline_cli.py:250` — it asserts the OLD env-channel behavior
        verbatim); its inverted successor is
        `test_pipeline_cli_run_threads_workflow_and_repeatable_skip`; the exact-kwargs
        `assert_called_once_with(..., parallel=None)` assertions (~lines 227 and 248 — the third
        occurrence, ~line 271, lives inside the deleted test and goes with it) gain the new
        `workflow=` / `no_workflow=` / `skip=` kwargs
- [x] **Debugging**: `pytest tests/pipeline -x` — fix implementation code until all tests pass
      (do NOT fix test code)
- [x] **Contract re-verification**: parser surface matches the `argparse` practice (repeatable
      `-s` in both modes); dispatch kwargs match the `pipeline-cli` usage doc verbatim; `--port`
      post-check unchanged (exit 2 without `--info`)
- [x] **Lint**: `ruff check goga/` — fix formatting if necessary

### Task 4: `build` credential-mount removal (goga/commands/build)

Remove the automatic credential bind-mounts from the build launcher: delete the broken import,
the credential loop, and the credential docstring sentences. The docker-run mount list becomes
exactly two entries.

**Contract entity**: `build` (location `build.py`); signature unchanged
(`plan, proxy, add_host, update, clean, skip_review`). Facade: importable from
`goga.commands.build`. Removal-only — no other behavior changes.

**Usages relevant to this task:**
- `conventions`: docstring style, intra-package imports.
- `build` (consumer doc `goga/commands/build/.usages/build.md`, already current): "Credential
  files are NOT mounted automatically — the launcher adds no credential mounts." — this is the
  behavior to implement.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm (from the design — verbatim):

```
1. Delete: from ...agents import resolve_credential_mounts   (line 16)
2. mounts = [f"{project_dir}:/workspace", f"{runtime_dir}:/workspace/.ralphex"]
   (delete the credential loop and the "Then each credential mount, read-only." comment tail)
3. Docstrings: remove credential-mount sentences from the module and routine docstrings.
```

Verified trace checkpoint: with exactly these two entries, the contract's v-list
(`v=[CWD:/workspace, the resolved host runtime dir read-write at /workspace/.ralphex]`) and the
"nothing under /workspace other than…" constraint hold.

- [x] **Contract tests**: keep the existing facade/signature/option-surface tests in
      `tests/commands/build/test_build.py` green (the surface is unchanged);
      `from goga.commands.build import build` must import cleanly again (currently ImportError —
      expected to fail at this stage via the new logic test below)
- [x] **Code**: delete the `resolve_credential_mounts` import (line 16), the credential loop
      (~lines 422–425), and the "Then each credential mount, read-only." comment tail in
      `goga/commands/build/build.py`
- [x] **Code**: remove the credential-mount sentences from the module and routine docstrings
- [x] **Code**: delete `tests/commands/build/test_build_credential_mount_integration.py` (tests
      the removed feature)
- [x] **Interface verification**: `pytest tests/commands/build -x` — all pass
- [x] **Logic tests**: add `test_no_credential_mounts_in_build_launcher` to
      `tests/commands/build/test_build.py` (extend the existing `mock.patch.object(_build_mod,
      "DockerRunner")` pattern): input — `build("plan.md", ...)` with docker mocks; assertions —
      `params["v"] == [f"{project}:/workspace", f"{runtime}:/workspace/.ralphex"]` (exactly two
      mounts). Sufficiency: the credential-removal contract for the build launcher; replaces the
      deleted credential-integration tests
- [x] **Debugging**: `pytest tests/commands/build -x` — fix implementation code until all tests
      pass (do NOT fix test code). Note: `tests/integration/test_runtime_isolation.py` still
      monkeypatches the deleted symbol — it is migrated in Task 8 and stays red until then
- [x] **Contract re-verification**: the mount list carries exactly the two entries; every other
      step of the `build` algorithm (env-file, runtime dir, signals, argv, params, runner,
      finally-cleanup) is untouched
- [x] **Lint**: `ruff check goga/` — fix formatting if necessary

### Task 5: `run_pipeline_container` argv channel + credential removal (goga/commands/pipeline)

Rewrite the run launcher onto the argv channel: the workflow decision becomes log-only
(`_resolve_workflow_env` → `_resolve_workflow_log_name`), the env-file carries environment layers
only, the argv assembly carries the workflow flags + one `-s` per skip name + `--parallel`, and
the credential mounts (and their broken import) are removed.

**Contract entity**: `run_pipeline_container` (location `run_pipeline_container.py`); signature
unchanged. Comment alignment in `file_roots.py` (`collect_file_roots` engine-mount enumeration
drops "credentials"). Facade: importable from `goga.commands.pipeline`.

**Usages relevant to this task:**
- `run-pipeline` (imported usage, already current): "Apply … for the explicit-parameter contract
  of the workflow decision and skip names the argv carries."
- `afm`: the file-manager roots payload and the afm-config tmpfile contract — unchanged by this
  task.
- `resolve-wrapper-path` (imported from `goga/agents`): still applied at the wrapper-resolution
  step (step 5).
- `convention`: docstring style, intra-package imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm delta (from the design — verbatim):

```
1. Replace _resolve_workflow_env with _resolve_workflow_log_name(workflow, no_workflow, name)
   -> str | None:
   - no_workflow is True            -> None                     (no log)
   - workflow is not None           -> workflow                 (explicit; file validated by caller)
   - else auto-match: compose <cwd>/.goga/workflows/<name>.yml; keep the containment guard
     (a name escaping the workflows dir -> None, never a wider-filesystem resolve);
     exists -> name; absent -> None
2. _run_named steps:
   a. port, runtime dir (+clean), signal handlers, wrapper, afm-config tmpfile (unchanged)
   b. step 9:  workflow_log_name = _resolve_workflow_log_name(workflow, no_workflow, name)
   c. step 10: if workflow_log_name is not None:
                 click.echo(f'Pipeline running with workflow "{workflow_log_name}"')
   d. step 11: env_file = _build_env_file(home_env=home.env,
                  docker_run_tokens=home.docker.run, extra_env=extra_env,
                  pipeline_env=config.pipeline.env, proxy=proxy)
              # NO workflow/no_workflow/name/skip parameters remain on _build_env_file
   e. step 12: mounts = [f"{project_dir}:/workspace",
                 f"{runtime_dir}:{_IN_CONTAINER_AFM_DIR}",
                 f"{afm_config}:/home/goga/.afm/config.yaml:ro"]        # no credential loop
   f. step 12: args = ["-m","goga.pipeline","run",name,"--port",str(port)]
               if workflow is not None:  args += ["-w", workflow]
               elif no_workflow:         args += ["--no-workflow"]
               for n in skip:            args += ["-s", n]
               if parallel is not None:  args += ["--parallel", str(parallel)]
   g. safety net / docker_update / DockerRunner.run (unchanged)
3. Imports: from ...agents import resolve_wrapper_path        # resolve_credential_mounts gone
4. Docstrings: module, _build_env_file, _run_named, run_pipeline_container — drop the workflow
   env-var/GOGA_SKIP_STAGES sentences; describe the argv channel and the log-only decision;
   drop the credential-mount sentences.
```

Edge cases (from the design — verbatim): `skip=()` → no `-s` flags at all; `workflow` and
`no_workflow` both set — impossible (caller rejects); the `elif` keeps the assembly total anyway
(precedence: `-w`); user `GOGA_*` in `-e`/`home.env`/`config.pipeline.env` → written verbatim,
never interpreted (inertness constraint). GOGA_* inertness holds by construction: with the writes
removed, user `GOGA_*` values flow into `_write_env_file` verbatim; nothing in-container reads
them (`run_pipeline` reads only `AFM_DIR`).

Also in this task: `goga/commands/pipeline/file_roots.py` — two comments drop "credentials" from
the engine-mount enumeration (module docstring "afm state, config overlay, credentials" → "afm
state, config overlay"; same in the `collect_file_roots` docstring) — matching the manifest
constraint. Logic unchanged.

- [x] **Contract tests**: in `tests/commands/pipeline/test_run_pipeline_container_contract.py` —
      the existing facade/signature tests stay green (signature unchanged);
      `from goga.commands.pipeline import run_pipeline_container` must import cleanly again
      (currently ImportError — the new logic tests fail at this stage)
- [x] **Code**: replace `_resolve_workflow_env` with `_resolve_workflow_log_name(workflow,
      no_workflow, name) -> str | None` per the algorithm delta (keep the containment guard
      verbatim)
- [x] **Code**: shrink `_build_env_file` to environment layers only — remove the
      `workflow`/`no_workflow`/`name`/`skip` parameters, the workflow-env update, and the
      `GOGA_SKIP_STAGES` write; move the log-line emission to `_run_named` step 10 (after the
      step-9 decision)
- [x] **Code**: argv assembly per step 12f (exact order: `--port`, then `-w`/`--no-workflow`,
      then one `-s` per name, then `--parallel`)
- [x] **Code**: mounts — exactly the three engine mounts; delete the credential loop and fix the
      import to `from ...agents import resolve_wrapper_path`
- [x] **Code**: docstrings (module, `_build_env_file`, `_run_named`, `run_pipeline_container`) per
      algorithm delta item 4; comment alignment in `file_roots.py`
- [x] **Code**: delete `tests/commands/pipeline/test_pipeline_credential_mount_integration.py`
      (tests the removed feature)
- [x] **Interface verification**: `pytest tests/commands/pipeline/test_run_pipeline_container.py
      tests/commands/pipeline/test_run_pipeline_container_contract.py -x` — all pass
- [x] **Logic tests** (mock-Docker fixtures; assert on exact argv lists / env-file keys):
      - `test_run_argv_carries_workflow_flags_skip_and_parallel` (in
        `tests/commands/pipeline/test_run_pipeline_container.py`): setup — docker mocks; config
        with `image`, `pipeline.agent`; input — `run_pipeline_container(name="deploy", config=…,
        workflow="hardening", no_workflow=False, skip=("build","test"), parallel=2, …)`; trace —
        `→ _run_named → _resolve_workflow_log_name("hardening", False, "deploy") → "hardening"`
        (log only) `→ _build_env_file(…)` (env layers only) `→ args = ["-m","goga.pipeline",
        "run","deploy","--port","<P>","-w","hardening","-s","build","-s","test","--parallel","2"]
        → DockerRunner.run(args, …) captured`; assertions — exact argv equality (order included —
        prevents flag drift such as `--parallel` jumping ahead of `-s`). Sufficiency: the launcher
        argv assembly is the contract's step 12
      - `test_env_file_carries_no_goga_entries` (in
        `tests/commands/pipeline/test_run_pipeline_container_workflow.py`): setup — same mocks;
        env-file content captured; input — run form with `workflow="hardening"`, `skip=("build",)`;
        trace — `→ _build_env_file → _write_env_file(env, extra_env)` — keys inspected; assertions
        — no key in the file starts with `GOGA_`; `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS` present; the
        `Pipeline running with workflow "hardening"` line still printed once. Sufficiency: the
        "env-file carries environment layers only" rule; catches a leftover
        `GOGA_SKIP_STAGES`/`GOGA_WORKFLOW_*` write
      - `test_stale_goga_env_values_are_inert` (same file): setup — docker mocks;
        `extra_env=("GOGA_WORKFLOW_NAME=zzz","GOGA_SKIP_STAGES=zzz")`; input — run form with NO
        workflow flags and empty skip; assertions — argv has no `-w`/`-s`; no warning/error
        raised; the verbatim lines are present in the env-file (inert passengers). Sufficiency:
        the manifest's inertness constraint
      - `test_no_credential_mounts_in_run_launcher` (in
        `tests/commands/pipeline/test_run_pipeline_container.py`): setup — docker mocks capture
        `params["v"]`; input — run form launch; assertions — `params["v"]` is exactly
        `[f"{project}:/workspace", f"{runtime}:/home/goga/pipeline",
        f"{afm_config}:/home/goga/.afm/config.yaml:ro"]` — exactly three engine mounts; no `:ro`
        credential entries; no entry under `/home/goga/.claude`, `/home/goga/.codex`,
        `/home/goga/.local`. Sufficiency: the credential-removal contract; replaces the deleted
        credential-integration tests
      - `test_workflow_log_line_matrix` (rewrite of the existing workflow tests in
        `test_run_pipeline_container_workflow.py`): input matrix — explicit `-w` → line names it;
        `--no-workflow` → no line; auto-match file exists → line names the pipeline; auto-match
        absent → no line; assertions — exactly one stdout line in the positive cases; none in the
        others; the env-file never carries a `GOGA_*` key in any case. Sufficiency: the log
        decision is now purely host-side output — no env side effects
      - migration of `tests/commands/pipeline/test_run_pipeline_container_workflow.py`: the
        env-file `GOGA_*`-entry assertions (~lines 281–426) invert (no `GOGA_*` key ever
        written); the log-line tests fold into `test_workflow_log_line_matrix`; the auto-match
        containment tests (dotdot / absolute-prefix) survive the rewrite unchanged — the guard
        stays
- [x] **Debugging**: `pytest tests/commands/pipeline -x --ignore=
      tests/commands/pipeline/test_integration_launcher_tmpfile.py` — fix implementation code
      until all tests pass (do NOT fix test code). The ignored file still monkeypatches the
      deleted symbol — it is migrated in Task 8
- [x] **Contract re-verification**: signature unchanged; steps 1–8 and 13–16 unchanged (D7
      signal-handler window order preserved); argv ↔ `pipeline_cli` run-subcommand surface
      alignment (flag names and repeatable `-s` match the argparse definitions from Task 3)
- [x] **Lint**: `ruff check goga/` — fix formatting if necessary

### Task 6: `run_pipeline_info_container` card-form skip (goga/commands/pipeline)

Add the `skip` parameter to the card launcher and compose one `-s NAME` per entry into the card
argv. The listing forms ignore `skip` entirely.

**Contract entity**: `run_pipeline_info_container` (location `run_pipeline_info_container.py`);
DSL signature `+(skip: tuple[str, ...])`, **Python** signature `skip: tuple[str, ... = ()` after
`no_workflow` — the Python-level default carries the empty tuple (the DSL signature has no
default — grammar-rejected); the listing dispatch, which passes no skip, relies on this default.
Facade: importable from `goga.commands.pipeline`.

**Usages relevant to this task:**
- `pipeline-cli` (imported usage): the in-container subcommand surface the argv addresses —
  `run NAME --info [-w WORKFLOW | --no-workflow] [-s NAME]...`.
- `convention`: docstring style, intra-package imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm delta (from the design — verbatim):

```
1. Signature: +(skip: tuple[str, ...] = ()) after no_workflow — the Python-level default
   carries the empty tuple (the DSL signature has no default — grammar-rejected); the
   listing dispatch, which passes no skip, relies on this default
2. _compose_argv(name, info, workflow, no_workflow, skip):
   - name is None -> list/overview argv (unchanged; skip deliberately not represented)
   - card: argv = ["-m","goga.pipeline","run",name,"--info"]
           if workflow is not None: argv += ["-w", workflow]
           elif no_workflow:        argv += ["--no-workflow"]
           for n in skip:           argv += ["-s", n]
3. Docstrings: card-form description mentions the per-name -s; skip param doc.
```

Edge cases: `skip=()` → card argv carries no `-s`. Listing forms ignore `skip` entirely.

- [x] **Contract tests**: in `tests/commands/pipeline/test_run_pipeline_info_container.py` —
      assert the signature gains `skip: tuple[str, ...] = ()` after `no_workflow` (expected to
      fail at this stage); the listing-form argv shapes stay unchanged
- [x] **Code**: add `skip: tuple[str, ...] = ()` to `run_pipeline_info_container` and thread it
      into `_compose_argv(name, info, workflow, no_workflow, skip)`
- [x] **Code**: card branch appends one `["-s", n]` per skip entry after the workflow flags;
      docstrings per the algorithm delta
- [x] **Interface verification**: `pytest tests/commands/pipeline/test_run_pipeline_info_container.py
      -x` — all pass
- [x] **Logic tests** (in `tests/commands/pipeline/test_run_pipeline_info_container.py`):
      - `test_card_argv_carries_one_dash_s_per_skip`: setup — the module's mocks; input —
        `run_pipeline_info_container(name="deploy", info=True, config=…, hosts={}, update=False,
        workflow=None, no_workflow=False, skip=("a","b"))`; trace — `→ _compose_argv →
        ["-m","goga.pipeline","run","deploy","--info","-s","a","-s","b"]`; assertions — exact
        argv equality. Sufficiency: the card launcher's skip threading; one `-s` per entry, order
        preserved
      - edge: `skip=()` → card argv carries no `-s`; listing argv unchanged (no skip
        representation)
- [x] **Debugging**: `pytest tests/commands/pipeline/test_run_pipeline_info_container.py -x` —
      fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: the minimal shape holds for all three forms (no port, no
      env-file, no engine mounts beyond the project); the card argv carries the workflow decision
      and the skip names exactly as given
- [x] **Lint**: `ruff check goga/` — fix formatting if necessary

### Task 7: `pipeline` click card dispatch + help texts (goga/commands/pipeline)

Forward the skip names in the card dispatch and clean the option help texts of the env-var
wording. The card form honors `-s` (previously run-only).

**Contract entity**: `pipeline` (location `pipeline.py`); click signature unchanged. Facade:
importable from `goga.commands.pipeline`.

**Usages relevant to this task:**
- `click` (cook): option help conventions; exit-code propagation via the click context.
- `pipeline-command` (consumer doc, already current): "card-form skip forwarding … the same
  flags produce the same composition in card and run forms".
- `convention`: CLI command docstring rule (the `--help` text is rendered verbatim by Click).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm delta (from the design — verbatim):

```
1. Steps 1–3 — UNCHANGED (config load + amendment, pipeline-section guard, form validation
   2.1→2.4 including the -w existence check and -w/--no-workflow exclusivity, topic procedure)
2. Step 4 dispatch:
   - card form: run_pipeline_info_container(..., workflow=workflow,
     no_workflow=no_workflow, skip=skip)          # + skip
   - run form:  run_pipeline_container(..., workflow=workflow, no_workflow=no_workflow,
     skip=skip, parallel=parallel)                  # unchanged
3. Option help texts (contract-alignment, no behavior):
   - --no-workflow: drop "(sets GOGA_WORKFLOW_DISABLED=1 in-container)" → describe the
     forwarded flag (e.g. "Disable workflow application entirely (run and card forms)")
   - -s/--skip: drop "(run mode only …)" and "forwarded as GOGA_SKIP_STAGES" →
     "Exclude a stage from the compiled pipeline (run and card forms; repeatable)"
```

Edge cases: `-s` with `--list` — silently ignored (no dispatch of skip in the listing branch).
Unchanged. Errors: unchanged (ClickException paths). The listing dispatch stays unchanged — it
passes no `skip` and relies on the `skip=()` signature default from Task 6.

- [x] **Contract tests**: the existing facade/option-surface tests in
      `tests/commands/pipeline/test_pipeline.py` and `test_pipeline_contract.py` stay green
      (surface unchanged); a new failing-first dispatch assertion (below) pins the card kwargs
- [x] **Code**: card dispatch in `goga/commands/pipeline/pipeline.py` gains `skip=skip`;
      run-form dispatch unchanged
- [x] **Code**: fix the `--no-workflow` and `-s/--skip` option help texts per the algorithm
      delta
- [x] **Interface verification**: `pytest tests/commands/pipeline/test_pipeline_dispatch.py -x` —
      all pass
- [x] **Logic tests**:
      - `test_card_form_command_forwards_skip_to_info_container` (in
        `tests/commands/pipeline/test_pipeline_dispatch.py`): setup — CliRunner, mocked
        `run_pipeline_info_container`, project with `.goga/workflows/hardening.yml` when needed;
        input — `["pipeline","deploy","--info","-s","build"]`; trace — `→ pipeline click → card
        dispatch with skip=("build",)`; assertions — call kwargs `skip == ("build",)`,
        `info is True`, `name == "deploy"`. Sufficiency: the click seam — the card form honors
        `-s` (previously run-only)
      - keep/verify `test_w_and_no_workflow_combination_rejected_host_side` (existing): input —
        `["pipeline","deploy","-w","x","--no-workflow"]` → exit 1 clean message, no docker.
        Sufficiency: host owns the exclusivity; unchanged behavior guard
      - migration of `tests/commands/pipeline/test_pipeline_dispatch.py`: the exact-kwargs
        dispatch assertions gain `skip` (card: the parsed tuple; listing: unchanged, covered by
        the `skip=()` signature default)
      - migration of `tests/commands/pipeline/test_pipeline_workflow_flags.py`: the tests
        asserting the `--no-workflow` env-file write premise (~lines 156–175) rewrite to the
        argv/log surface; the host-side exclusivity and existence-validation tests survive
        unchanged
- [x] **Debugging**: `pytest tests/commands/pipeline/test_pipeline.py
      tests/commands/pipeline/test_pipeline_dispatch.py
      tests/commands/pipeline/test_pipeline_workflow_flags.py -x` — fix implementation code until
      all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: steps 1–3 and 5 untouched (validation order 2.1→2.4 before
      any docker activity; topic procedure; exit-code propagation); listing forms still ignore
      `-s`/`-e`/`--proxy`/`-c`/`-p`/`--add-host`
- [x] **Lint**: `ruff check goga/` — fix formatting if necessary

### Task 8: Integration tests + cross-cell test migration

Make the whole suite green: migrate the four integration test files that encode the removed
env-channel premise or monkeypatch the deleted credential symbol, add the card/run skip
equivalence test and the facade guard, and run the full validation battery.

**Cross-entity scenarios**: card↔run skip equivalence (describe_pipeline vs run_pipeline through
the same `resolve_workflow → apply_skip_stages → hooks → compile_flow` machine); host→container
argv threading end-to-end (env-file vs argv channel); no credential mounts across both launchers;
the shrunk `goga/agents` facade.

**Usages relevant to this task:**
- `convention`: test infrastructure organization; docstring-first tests; mock-Docker fixtures.
- `describe-pipeline` / `run-pipeline` (consumer docs): the equivalence guarantee ("the same
  flags produce the same composition").

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/pipeline/test_card_run_skip_equivalence.py` with
      `test_card_and_run_skip_equivalence`: setup — `tests/pipeline` fixtures; capture the
      composition both ways; input — `describe_pipeline(..., workflow="w", skip=["s2"])` vs the
      ordered stages of a `run_pipeline` compile with the same flags (`compile_flow` output);
      trace — both compose through `resolve_workflow → apply_skip_stages → hooks →
      compile_flow`; assertions — identical stage id lists. Sufficiency: "the same flags produce
      the same composition in card and run forms" — the equivalence guarantee of the contract
- [ ] Migrate `tests/integration/test_workflow_entity.py`: the assertions that the env-file
      carries `GOGA_WORKFLOW_NAME=feature-phases` (~lines 528, 583) invert to "no `GOGA_*` key is
      written; the argv carries `-w feature-phases`"
- [ ] Migrate `tests/integration/test_pipeline_info_integration.py`: the setenv premise (~lines
      224–226: `delenv`/`setenv("GOGA_WORKFLOW_NAME","hardening")`) rewrites to parameter passing
      (`workflow="hardening"`)
- [ ] Migrate `tests/integration/test_runtime_isolation.py`: drop the
      `monkeypatch.setattr(_build_mod, "resolve_credential_mounts", …)` /
      `monkeypatch.setattr(_rpc_mod, "resolve_credential_mounts", …)` patches (~lines 86–88) and
      INVERT (do not merely delete) the credential assertions — they become the no-credential-
      mount guards (exactly-two build mounts / exactly-three pipeline engine mounts)
- [ ] Migrate `tests/commands/pipeline/test_integration_launcher_tmpfile.py`: same inversion —
      drop the `resolve_credential_mounts` monkeypatch (~lines 80–81); assert the tmpfile mount
      set contains no credential entries
- [ ] Add the facade guard `test_facade_import_surface` (extend `tests/agents/test_facade.py`):
      `python -c "from goga.agents import resolve_wrapper_path"` (subprocess) plus
      `assert not hasattr(goga.agents, "resolve_credential_mounts")`. Sufficiency: the shrunk
      facade — the checklist's facade check
- [ ] Run the full validation battery (see Validation Commands): `pytest tests/ -x`,
      `ruff check goga/`, `goga lint`, the facade check, and the two no-residue greps — all must
      pass / come back empty
- [ ] Verify no residue: no `GOGA_WORKFLOW_NAME`/`GOGA_WORKFLOW_DISABLED`/`GOGA_SKIP_STAGES`
      mention remains in `goga/` or `tests/`; no `resolve_credential_mounts` /
      `resolve-credential-mounts` reference remains in `goga/` or `tests/`

---

## Validation Commands

- `pytest tests/ -x`: Run all tests (green only after Task 8; per-task scoped commands are listed
  inside each task)
- `ruff check goga/`: Lint check (after every coding task and at the end)
- `goga lint`: DSL validation over all cells — the contracts are read-only and must stay green
  (81 cells, 0 errors)
- `python -c "from goga.agents import resolve_wrapper_path"`: Facade accessibility — the shrunk
  `goga/agents` facade
- `grep -rn "GOGA_WORKFLOW_NAME\|GOGA_WORKFLOW_DISABLED\|GOGA_SKIP_STAGES" goga/ tests/ || true`:
  No-residue check — must return nothing (the only allowed mention in the change-set is the
  inertness Constraint inside `run_pipeline_container`'s CODEMANIFEST, which this grep does not
  traverse)
- `grep -rn "resolve_credential_mounts\|resolve-credential-mounts" goga/ tests/ || true`:
  No-residue check — must return nothing

---

## Completion Criteria

- [ ] Every changed contract entity is implemented in its declared `location` and matches the
      materialized signature exactly (`run_pipeline`, `describe_pipeline`, `pipeline_cli`,
      `apply_skip_stages`, `pipeline`, `run_pipeline_container`, `run_pipeline_info_container`,
      `build`)
- [ ] Every entity is accessible from its facade (`goga.pipeline`, `goga.commands.pipeline`,
      `goga.commands.build`, `goga.agents`)
- [ ] The workflow decision and skip names travel as argv/parameters end to end (click tuple →
      launcher argv → argparse → explicit parameters → `apply_skip_stages`); `AFM_DIR` is the
      only environment read of run coordination
- [ ] No `GOGA_*` env entry is written or read anywhere; stale user-supplied values are inert
- [ ] The card form forwards skip names and produces the same composition as a run with the same
      flags (equivalence test)
- [ ] No launcher adds credential mounts; the two credential integration test files are deleted
      and the runtime-isolation / launcher-tmpfile assertions are inverted into guards
- [ ] The workflow log line prints exactly when a workflow will apply (explicit or existing
      auto-match file)
- [ ] Help texts (click `--no-workflow`/`-s`; argparse `-w`/`--no-workflow`/`-s`) carry no
      env-var or "--info mode only" wording
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic
      tests → debugging → re-verification → lint)
- [ ] All ~20 design test scenarios are implemented and the migrated scenario matrices
      (workflow precedence/auto-match/containment; skip classes) are preserved
- [ ] The existing test migration is complete — none of the enumerated files still encodes the
      env-channel premise
- [ ] No package boundary was expanded; no new cells; no `.usages/` files created or modified
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check goga/`, `goga lint`, facade
      check, both no-residue greps)
