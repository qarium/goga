# Design Document: `pipeline-host-to-docker-values`

The architecture plan (`.goga/history/2026/pipeline-host-to-docker-values/arch.md`) is already
materialized into the CODEMANIFEST cells (apply-architecture stage, `goga lint` green over 81
cells). This document is the **implementation design**: it specifies the exact code changes that
bring the Python implementation in line with the materialized contracts. Two coherent workstreams
land as one shift, per the plan's implementation order (steps 1–6): the **channel unification**
(workflow decision and skip names travel as in-container argv / explicit parameters, never as
`GOGA_*` environment variables) and the **credential-mount removal** (the launchers add no
credential mounts; mounting is user-served via home configuration).

---

## Contract Changes

All changes below are the **already-materialized** contract state (staged in git); the design
consumes them as the source of truth.

### Changed CODEMANIFEST Files

- `goga/agents/CODEMANIFEST`: facade shrink — the `goga/agents/credentials` import and the
  `->resolve_credential_mounts: {}` embedding removed; the facade re-exports exactly
  `resolve_wrapper_path`.
- `goga/pipeline/compiler/CODEMANIFEST`: annotation-only — the `compile_flow` participation
  bullet says "a workflow-file skip directive OR a CLI skip directive" (was: the
  `GOGA_SKIP_STAGES` channel).
- `goga/pipeline/CODEMANIFEST`: `run_pipeline` signature `+workflow/no_workflow/skip` with
  parameter-driven steps 6–7; `describe_pipeline` signature `+skip` with a new merge step 3 and
  renumbering 3–7→4–8; `apply_skip_stages` parameter doc re-pointed at the `-s/--skip` flag
  names; `pipeline_cli` parser and dispatch accept the repeatable `-s` in both run and card
  modes; the `argparse` practice and the global annotations re-describe the explicit-parameter
  channel.
- `goga/commands/build/CODEMANIFEST`: removal-only — credential-mount imports, the
  `docker-auth-mounts` practice, the step-14 credential clauses, and the credential
  Requirements/Constraints bullets are gone.
- `goga/commands/pipeline/CODEMANIFEST`: `run_pipeline_container` rewritten onto the argv
  channel (workflow log decision only in step 9; env-file carries environment layers only;
  step-12 argv `[-w WF] [--no-workflow] [-s N]... [--parallel N]`; GOGA_* inertness
  constraint); `run_pipeline_info_container` signature `+skip` with per-name card argv;
  `pipeline` card form forwards the skip names; `collect_file_roots` engine-mount list loses
  "credentials".

### New Entities

- None. The change-set is a pure realignment: no new contract entity is introduced.

### Changed Entities

- `pipeline` (goga/commands/pipeline) — card form forwards `skip`; option help texts lose the
  env-var wording.
- `run_pipeline_container` (goga/commands/pipeline) — workflow/skip travel as argv; env-file
  drops every GOGA_* entry; no credential mounts.
- `run_pipeline_info_container` (goga/commands/pipeline) — `+skip: tuple[str, ...]`; card argv
  carries one `-s NAME` per entry.
- `run_pipeline` (goga/pipeline) — `+workflow/no_workflow/skip` parameters replace the
  `GOGA_WORKFLOW_*` / `GOGA_SKIP_STAGES` env reads; `AFM_DIR` stays the only env read.
- `describe_pipeline` (goga/pipeline) — `+skip: list[str] | None = None`; applies the same
  in-memory skip merge a run applies.
- `pipeline_cli` (goga/pipeline) — repeatable `-s/--skip` on the run subcommand (both modes);
  dispatch threads the workflow decision and skip names to both `run_pipeline` and
  `describe_pipeline`.
- `apply_skip_stages` (goga/pipeline) — logic unchanged; the contract doc now attributes the
  names to the `-s/--skip` flag channel.
- `build` (goga/commands/build) — no contract signature change; the credential-mount behavior is
  removed from the algorithm and requirements.

### Deleted Entities

- `resolve_credential_mounts` (cell `goga/agents/credentials`) — the whole cell, its practice
  (`goga/agents/.usages/resolve-credential-mounts.md`), and its tests are already deleted
  (apply-architecture). The two remaining consumer call sites are removed by this design.

### Usages and Annotations Changes

- Replaced wholesale (already landed): `goga/pipeline/.usages/run-pipeline.md`,
  `pipeline-cli.md`, `describe-pipeline.md`; `goga/commands/pipeline/.usages/pipeline-command.md`.
- Edited (already landed): `goga/commands/build/.usages/build.md` (credential bullet →
  user-owned mounting guidance),
  `.goga/usages/cooks/afm.md` (integration-pattern fragment: no credential mounts, pointer to
  the user guide), `.goga/usages/cooks/docker-auth-mounts.md` (rewritten as the self-served
  mounting user guide).
- Removed: the `docker-auth-mounts` key from the `Usages` headers of `goga/commands/build` and
  `goga/commands/pipeline`; the `resolve-credential-mounts` imported practice from both.

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Phase 3 found no contract defect: `goga lint` passes (81 cells, 0 errors); the four
  consistency dimensions hold across the changed cells (the `tuple[str, ...]` → argv `-s` →
  argparse list → `list[str] | None` → `list[str]` chain is type-coherent end to end; the
  launcher argv in `run_pipeline_container` step 12 matches the `pipeline_cli` run-subcommand
  surface exactly; `no_workflow` precedence matches the `resolve_workflow` rule set; every
  annotation reference resolves). One lint-forced deviation from the plan text was already taken
  at materialization time and is accepted here: `run_pipeline_info_container.skip` carries no
  DSL default (`= ()` is rejected by the signature grammar); the Python-level default `()` is
  carried by the Python signature instead (`skip: tuple[str, ...] = ()` — the same
  implementation-detail precedent `run_pipeline_container` already uses), so the unchanged
  listing dispatch (which passes no `skip`) keeps working.

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
 HOST                                    |  CONTAINER (docker run ... python3 -m goga.pipeline ...)
                                         |
 goga pipeline NAME [-w WF] [--no-workflow] [-s N]... [-p N]
   │                                    |
   ├─ pipeline (click)                  |
   │   validation: -w file exists,     |
   │   -w XOR --no-workflow             |
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

### Data Flows

**Run form (values on the argv channel):**

1. `pipeline` (click) validates form + `-w` existence + exclusivity, resolves proxy/hosts,
   dispatches `run_pipeline_container(name=..., workflow=..., no_workflow=..., skip=...,
   parallel=...)` — `skip` is the raw click tuple, forwarded as parsed (no validation, no
   dedup).
2. `run_pipeline_container` → `_run_named`: allocates the port, prepares the runtime dir,
   installs signal handlers, resolves the wrapper path, writes the afm-config tmpfile.
3. Step 9 — `_resolve_workflow_log_name(workflow, no_workflow, name)` decides ONLY the log
   line: `no_workflow` → None; explicit `workflow` → that name; else the containment-guarded
   auto-match existence check → the pipeline name or None.
4. Step 10 — print `Pipeline running with workflow "<name>"` when the decision is not None.
5. Step 11 — `_build_env_file` writes environment layers only (home.env, git identity,
   `config.pipeline.env`, `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, proxy). No `GOGA_*` key is ever
   written by the launcher; a user-supplied `GOGA_*` entry (via `-e`, `home.env`, or
   `config.pipeline.env`) travels verbatim and stays inert.
6. Step 12 — argv assembly: `["-m","goga.pipeline","run",name,"--port",str(port)]` then
   `["-w", workflow]` when explicit, else `["--no-workflow"]` when set, then one
   `["-s", n]` per skip name, then `["--parallel", str(parallel)]` when not None. Mounts:
   project, persistent afm state, afm-config tmpfile — nothing else.
7. In-container: `pipeline_cli` parses (`-w`, `--no-workflow`, `-s` repeatable,
   `--port`, `--parallel`), dispatches `run_pipeline(name, project_dir, user_dir, port,
   workflow=..., no_workflow=..., skip=..., parallel=...)`.
8. `run_pipeline`: resolves the workflow via the shared rule set from the **parameters**,
   merges `skip or []` via `apply_skip_stages`, delivers the amendment with the merged
   workflow, compiles, materializes prompts, runs afm.

**Card form:** `pipeline` → `run_pipeline_info_container(name, info=True, ...,
skip=skip)` → argv `run NAME --info [-w WF | --no-workflow] [-s N]...` → `pipeline_cli` →
`describe_pipeline(..., skip=...)` → same merge and compilation machine as the run.

**Build form:** `build` assembles `mounts = [project:/workspace,
runtime:/workspace/.ralphex]` — the credential loop and its import are deleted.

### Entity Dependencies

- `goga/commands/pipeline` → `goga/agents` (`resolve_wrapper_path` only), → `goga/pipeline`
  (Usages-only; the runtime boundary is docker).
- `goga/commands/build` → `goga/agents` (`resolve_wrapper_path` only — the
  `resolve_credential_mounts` edge is gone).
- `goga/pipeline` → `goga/pipeline/compiler`, `goga/pipeline/hooks`, `goga/pipeline/workflow`
  (unchanged by this design).
- Design/implementation order (dependency-driven, mirrors the plan): pipeline cell first
  (in-container surface), then the two command cells (they address that surface), then tests.

---

## Code Stack Trace

All traces verified against the current source and the materialized contracts. Checkpoints mark
type/logic verification points.

### Trace: `pipeline` (click) — card dispatch

#### Chain
1. **Input**: `goga pipeline NAME --info -w hardening -s build -s test` (click parses;
   `skip=("build","test")`).
2. Steps 1–2 (unchanged): load config + amend; None-guard; form validation; `-w` existence
   validation (host-side, `Path.cwd()/.goga/workflows/hardening.yml`) → checkpoint: validation
   order matches the manifest (2.1→2.4, before any docker activity). **passed**
3. Step 4 card dispatch: `run_pipeline_info_container(name=name, info=True, config=config,
   hosts=info_hosts, update=update, workflow=workflow, no_workflow=no_workflow, skip=skip)`
   → checkpoint: signature `+skip: tuple[str, ...]` matches the contract. **passed — code gap:
   the current call omits `skip`**
4. **Output**: `ctx.exit(exit_code)`.

#### Checkpoint Summary
- Type flow click tuple → launcher tuple: **passed** (both `tuple[str, ...]`).
- Listing forms ignore `-s`: dispatch passes no skip for `--list` → **passed** (unchanged code —
  valid because the Python signature defaults `skip` to `()`).

### Trace: `run_pipeline_container` (run form)

#### Chain
1. **Input**: `(name, config, extra_env, proxy, hosts, clean, update, workflow, no_workflow,
   skip, parallel)` — signature already matches the contract. **passed**
2. `_check_docker`, `load_home_config`, image guard (unchanged).
3. `_run_named`: port allocation, runtime dir (+`--clean`), signal handlers, wrapper resolution,
   afm-config tmpfile (unchanged) → checkpoint: D7 window order preserved. **passed**
4. Step 9 — workflow decision: `_resolve_workflow_log_name(workflow, no_workflow, name)`
   returns only the log name → checkpoint: **code gap — the current `_resolve_workflow_env`
   also produces `GOGA_WORKFLOW_NAME`/`GOGA_WORKFLOW_DISABLED` env entries** (defect against
   step 9's log-only contract).
5. Step 10 — log line when not None → **passed** (existing behavior retained verbatim).
6. Step 11 — `_build_env_file(home_env, docker_run_tokens, extra_env, pipeline_env, proxy)`:
   env layers only → checkpoint: **code gap — the current call also writes
   `GOGA_SKIP_STAGES=<csv>` and the workflow env entries**.
7. Step 12 — mounts `[project:/workspace, runtime:/home/goga/pipeline,
   afm_config:/home/goga/.afm/config.yaml:ro]` → checkpoint: **code gap — the current loop
   appends `resolve_credential_mounts()` entries** (import already deleted → ImportError).
8. Step 12 — argv: `["-m","goga.pipeline","run",name,"--port",str(port)]` + workflow flags +
   per-name `-s` + `--parallel` → checkpoint: matches `pipeline_cli`'s run-subcommand surface
   (`-w`, `--no-workflow`, `-s` append, `--port`, `--parallel`). **code gap — the current
   assembly appends only `--parallel`**
9. Steps 13–14 (safety net, `--update`, `DockerRunner.run`) — unchanged.

#### Checkpoint Summary
- argv ↔ `pipeline_cli` surface alignment: **passed after the assembly fix** (flag names and
  repeatable `-s` match the argparse definitions).
- GOGA_* inertness: with the writes removed, user `GOGA_*` values in `extra_env`/`home.env`/
   `config.pipeline.env` flow into `_write_env_file` verbatim; nothing in-container reads them
   (`run_pipeline` reads only `AFM_DIR`) → inert with no warning. **passed by construction**

### Trace: `run_pipeline_info_container` (card form)

#### Chain
1. **Input**: `(name, info, config, hosts, update, workflow, no_workflow, skip)` → **code gap:
   the current signature lacks `skip`**.
2. `_compose_argv`: card → `["-m","goga.pipeline","run",name,"--info"]` + `-w`/`--no-workflow`
   + one `["-s", n]` per skip entry → checkpoint: order `[-w WF | --no-workflow] [-s N]...`
   matches the manifest step 3. **code gap — `-s` missing**.
3. Safety net / minimal shape / `DockerRunner.run` — unchanged → checkpoint: no port, no
   env-file, no engine mounts beyond the project. **passed**

### Trace: `pipeline_cli`

#### Chain
1. **Input**: e.g. `["run","deploy","--port","50321","-w","hardening","-s","build","-s","test",
   "--parallel","2"]`.
2. `_build_parser` — run subparser: `name` positional, `--info/-i`, `--workflow/-w`,
   `--no-workflow`, **`--skip/-s` (`action="append"`, `default=None`)**, `--port`, `--parallel`
   → checkpoint: argparse `append` yields `list[str] | None`, matching
   `skip: list[str] | None`. **code gap — `-s` not declared; `-w`/`--no-workflow` help texts
   wrongly say "--info mode only"**
3. Post-check `--port` required without `--info` (unchanged, exit 2 via `run_parser.error`).
4. Dispatch run mode: `run_pipeline(args.name, project_dir, user_dir, args.port,
   workflow=args.workflow, no_workflow=args.no_workflow, skip=args.skip,
   parallel=args.parallel)` → **code gap — the current call forwards only `parallel`**.
5. Dispatch card mode: `describe_pipeline(args.name, project_dir, user_dir,
   workflow=args.workflow, no_workflow=args.no_workflow, skip=args.skip)` → **code gap —
   `skip` not forwarded**.
6. **Output**: operation exit code; failures render as clean stderr (no traceback).

### Trace: `run_pipeline` (in-container run coordination)

#### Chain
1. **Input**: `(name, project_dir, user_dir, port, workflow=None, no_workflow=False,
   skip=None, parallel=None)` → **code gap — the current signature is
   `(name, project_dir, user_dir, port, parallel=None)`**.
2. Steps 1–3 `list_pipelines` → match → `pipeline_path` (unchanged; missing → stderr + 1).
3. Steps 4–5 `AFM_DIR` env read → **the only environment read** → checkpoint: contract
   "Read AFM_DIR directly from the process environment — the only environment read".
   **code gap — the current steps 6–7 also read `GOGA_WORKFLOW_DISABLED`,
   `GOGA_WORKFLOW_NAME`, `GOGA_SKIP_STAGES`**
4. Step 6: `workflow_name = None if no_workflow else workflow`;
   `resolved = resolve_workflow(name, workflow_name, no_workflow)` → checkpoint: double
   enforcement (input nulled + rule-set step 1) preserved; the shared rule set is the same one
   the card uses. **passed**
5. Step 7: `workflow = apply_skip_stages(resolved, skip or [])` → checkpoint: `skip or []`
   normalizes `None`/`[]` to the no-op path; type `list[str]` matches
   `apply_skip_stages(skip_stages: list[str])`. **passed**
6. Step 8 `_resolve_amendment_facts(match, pipeline_path, no_workflow, workflow_name,
   resolved)` — the decision derives from the PRE-merge resolution → checkpoint: "a skip-only
   document synthesized over a missing workflow is not a resolution". **passed** (facts
   helper unchanged; its inputs now come from parameters).
7. Steps 9–17: amendment delivery with the merged workflow, `compile_flow`, prompt
   materialization, `run_flow`, run events — unchanged.

### Trace: `describe_pipeline` (card composition)

#### Chain
1. **Input**: `(name, project_dir, user_dir, workflow, no_workflow, skip=None)` → **code gap —
   `skip` missing**.
2. Step 1 `list_pipelines` → match (missing → `RuntimeError`). **passed**
3. Step 2 `resolved = resolve_workflow(name, workflow, no_workflow)` → **passed**.
4. NEW Step 3 `workflow_doc = apply_skip_stages(resolved, skip or [])` → checkpoint: the merge
   happens BEFORE the amendment delivery, exactly as the run does. **code gap — no merge today**
5. Step 4 facts + delivery: the `WorkflowDecision` derives from **`resolved` (pre-merge)**, the
   delivery carries **`workflow_doc` (merged)**; a disabled decision delivers nothing and the
   passthrough overlay wraps `workflow_doc` → checkpoint: mirrors `run_pipeline` steps 8–9
   one-to-one. **design requirement — deriving the decision from the merged document would
   misclassify a skip-only-synthesized document as a resolution**
6. Steps 5–8 `compile_flow` (temp dir) → `order_stages` → card build → temp cleanup.
   **passed** (renumbered comments only)

### Trace: `build` (credential removal)

#### Chain
1. **Input**: unchanged (`plan, proxy, add_host, update, clean, skip_review`).
2. Env-file / runtime dir / signal handling — unchanged.
3. Mounts: `mounts = [f"{project_dir}:/workspace", f"{runtime_dir}:/workspace/.ralphex"]`
   → checkpoint: the contract's v-list and the "nothing under /workspace other than…" constraint
   hold with exactly these two entries. **code gap — the current loop appends credential
   mounts and imports the deleted `resolve_credential_mounts`**
4. argv / params / runner — unchanged.

### Trace: `apply_skip_stages` (reference)

Logic is unchanged and already contract-conformant (pure, non-mutating, empty-no-op, skip-wins,
memory verbatim). Only its docstrings still attribute the names to the `GOGA_SKIP_STAGES` env
channel → docstring alignment (module docstring + `skip_stages` arg description).

---

## Algorithm Design

### `pipeline` (click command)

**Responsibility**: five-form host entry; owns host-side validation and dispatch.

**Algorithm** (delta only):
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

**Errors**: unchanged (ClickException paths).

**Edge cases**: `-s` with `--list` — silently ignored (no dispatch of skip in the listing
branch). Unchanged.

### `run_pipeline_container`

**Responsibility**: full-shape run launcher; owns the workflow log decision, the env-file
(environment layers only), and the argv channel.

**Algorithm** (delta only):
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

**Errors**: unchanged (ClickException for docker/home/image failures; SystemExit on signals).

**Edge cases**:
- `skip=()` → no `-s` flags at all.
- `workflow` and `no_workflow` both set — impossible (caller rejects); the `elif` keeps the
  assembly total anyway (precedence: `-w`).
- User `GOGA_*` in `-e`/`home.env`/`config.pipeline.env` → written verbatim, never interpreted
  (inertness constraint).

### `run_pipeline_info_container`

**Responsibility**: minimal read-only launcher for the listing and card forms.

**Algorithm** (delta only):
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

**Edge cases**: `skip=()` → card argv carries no `-s`. Listing forms ignore `skip` entirely.

### `pipeline_cli`

**Responsibility**: in-container argparse surface and dispatch.

**Algorithm** (delta only):
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

**Edge cases**: `-s` absent → `args.skip is None` (argparse `append` default) → both routines
take their no-skip path.

### `run_pipeline`

**Responsibility**: in-container run coordination.

**Algorithm** (delta only):
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

**Errors**: unchanged set (RuntimeError AFM_DIR; WorkflowSyntaxError; StructuralError;
ValueError/ImportError from hooks; OSError/YAMLError).

**Edge cases**: `no_workflow=True` with `workflow="x"` — the launcher rejects the combination;
defensively `no_workflow` wins (name nulled before `resolve_workflow`).

### `describe_pipeline`

**Responsibility**: card composition through the same machine a run uses.

**Algorithm** (delta only):
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

**Edge cases**: `skip=None` and `skip=[]` produce byte-identical cards (`skip or []` no-op).
Unknown skip name → `StructuralError` from `compile_flow` (the same error a run raises).

### `build` (removal only)

```
1. Delete: from ...agents import resolve_credential_mounts   (line 16)
2. mounts = [f"{project_dir}:/workspace", f"{runtime_dir}:/workspace/.ralphex"]
   (delete the credential loop and the "Then each credential mount, read-only." comment tail)
3. Docstrings: remove credential-mount sentences from the module and routine docstrings.
```

### Docstring/comment-only alignments

- `goga/pipeline/apply_skip_stages.py` — module docstring and `skip_stages` arg: "the
  comma-split GOGA_SKIP_STAGES container env var" → "the repeatable `-s/--skip` flag names
  passed by run coordination and the card".
- `goga/pipeline/describe_pipeline.py` — module docstring paragraph (see above).
- `goga/commands/pipeline/file_roots.py` — two comments drop "credentials" from the
  engine-mount enumeration ("afm state, config overlay, credentials" → "afm state, config
  overlay"); the manifest constraint reads the same way.
- `goga/pipeline/cli.py` — module docstring dispatch note (mentions which routine receives
  what) updated to include skip; `pipeline_cli` docstring argv examples gain a `-s` example.
- `goga/pipeline/resolve_workflow.py` — module docstring: "whose decision arrives from the
  container environment" → "whose decision arrives from CLI parameters"; "(`run_pipeline`
  reads env; `describe_pipeline` reads CLI)" → "(both `run_pipeline` and `describe_pipeline`
  receive their decision as parameters)"; `workflow_name` arg doc: "(env on the run path,
  CLI flags on the card path)" → "(parameters on both paths)".

---

## Cross-cutting Concerns

- **Error handling**: unchanged strategies. Host: `click.ClickException` for docker/home/image
  failures. In-container: clean stderr messages, no traceback; `run_parser.error` (exit 2) for
  the conditional `--port`; `StructuralError` surfaces an unknown skip name during composition
  (run AND card — the card now fails identically, which is the equivalence the contract wants).
- **Logging**: the single host-side stdout line besides docker output —
  `Pipeline running with workflow "<name>"` — printed exactly when a workflow will apply
  (explicit `-w`, or an existing auto-match file). `--no-workflow` and a missing auto-match
  file print nothing. In-container `logger.debug` lines unchanged.
- **Validation**: host owns `-w` file existence and `-w`/`--no-workflow` exclusivity (steps
  2.3–2.4, every form); skip names are forwarded as parsed with no validation or dedup
  anywhere host-side; the in-container CLI validates nothing about workflow/skip; unknown skip
  names fail at `compile_flow`.
- **Caching**: none in scope.
- **Concurrency**: `--parallel` threading unchanged (host option → argv `--parallel` →
  `run_pipeline(parallel=)` → `run_flow(max_parallel=)` → `afm --max-parallel`).

---

## Usages Analysis

### `argparse` (inline, goga/pipeline)
- **What it provides**: the in-container CLI surface — `list [--info]`; `run NAME [--info]
  [-w NAME | --no-workflow] [-s NAME]... [--port] [--parallel]`.
- **Where used**: `pipeline_cli`.
- **Why chosen**: stdlib; the updated inline text now names the repeatable `-s` and its
  dual-mode availability.
- **How exactly**: `add_argument("--skip","-s", action="append", default=None)`.

### `cli_entrypoint` (inline, goga/pipeline)
- Unchanged: `__main__.py` stays a thin `pipeline_cli` delegate; no `runpy` warning.

### `run-pipeline` (goga/pipeline/.usages/, consumer doc)
- Describes the explicit-parameter contract, the AFM_DIR-only env read, and the threading
  chains — matches this design exactly. No change needed.

### `pipeline-cli` (goga/pipeline/.usages/, consumer doc)
- Dispatch signatures quoted (`run_pipeline(..., workflow=, no_workflow=, skip=, parallel=)`,
  `describe_pipeline(..., skip=)`) match the designed call sites. No change needed.

### `describe-pipeline` (goga/pipeline/.usages/, consumer doc)
- `skip` parameter, merge semantics, anti-patterns ("pass the names; the merge is in-memory")
  match. No change needed.

### `pipeline-command` (goga/commands/pipeline/.usages/, consumer doc)
- Card-form skip forwarding, docker shapes (decision travels in the subcommand argv), and the
  threading chains match. No change needed.

### `click` (.goga/usages/cooks/click.md)
- Applied as-is to the `pipeline` command edits (docstring conventions).

### `afm` (.goga/usages/cooks/afm.md)
- Integration-pattern fragment already realigned (no credential mounts; user-guide pointer).
  The `run_pipeline_container` docstring references stay valid.

### `docker-auth-mounts` (.goga/usages/cooks/docker-auth-mounts.md)
- Now a **user guide**, not a launcher practice: it is no longer wired into any CODEMANIFEST
  `Usages`. The launchers and the `build.md` usage point users at it. Nothing for this design
  to consume — recorded to prevent re-wiring.

### Imported Usages
- `resolve-wrapper-path` from `goga/agents` (both command cells) — unchanged; still applied at
  the wrapper-resolution step.

---

## `.usages/` Update

### Cell: `goga/pipeline`
- **`run-pipeline.md`**, **`pipeline-cli.md`**, **`describe-pipeline.md`** — Status: **current**
  (replaced wholesale at materialization; verified against this design's call sites). No
  additions or updates needed.
### Cell: `goga/commands/pipeline`
- **`pipeline-command.md`** — Status: **current** (card skip forwarding, argv shapes, threading
  chains verified). No change.
### Cell: `goga/commands/build`
- **`build.md`** — Status: **current** (credential bullet replaced by the user-owned mounting
  guidance; consistent with the mount-list change). No change.
### Cell: `goga/agents`
- **`.usages/resolve-credential-mounts.md`** — deleted at materialization; nothing to update.
- No new `.usages/` files: no new functional domain appears (skip threading belongs to the
  existing pipeline/cli/run domains already covered).

---

## Test Stack Trace

### General Setup

- Existing fixtures: `tests/pipeline/conftest.py` (DSL stage/phase files, workflow files),
  `tests/commands/pipeline/` mock-Docker fixtures (`_mock_docker_internals`,
  `_capture_env`-style env-file capture), `tests/commands/conftest.py` (click runner).
- Convention: docstring-first, asserts on exact argv lists / call kwargs; no real docker.

### Source File Registry

- Under test: `goga/pipeline/cli.py`, `run_pipeline.py`, `describe_pipeline.py`,
  `apply_skip_stages.py`; `goga/commands/pipeline/pipeline.py`, `run_pipeline_container.py`,
  `run_pipeline_info_container.py`; `goga/commands/build/build.py`.
- Deleted with the feature: `tests/commands/build/test_build_credential_mount_integration.py`,
  `tests/commands/pipeline/test_pipeline_credential_mount_integration.py`.

### Existing Test Migration

The unification breaks existing tests whose premise or exact assertions encode the removed
`GOGA_*` env channel. The implementation agent updates them in the same batch as the new
scenarios — none is left to discover through failures:

- `tests/pipeline/test_run_pipeline_workflow.py` — the 8 env-driven resolution tests
  (`GOGA_WORKFLOW_NAME` / `GOGA_WORKFLOW_DISABLED` setenv → assert `compile_flow` kwargs)
  rewrite onto explicit parameters (`workflow=` / `no_workflow=`), preserving the
  precedence/auto-match/containment scenario matrix.
- `tests/pipeline/test_run_pipeline.py` — the skip-stage class
  (`monkeypatch.setenv("GOGA_SKIP_STAGES", ...)`, ~lines 482–560) rewrites to `skip=[...]`
  parameter passing.
- `tests/pipeline/test_run_pipeline_hooks.py` — the decision-kind tests driven by setenv
  (~lines 312, 429, 433, 438–439) rewrite to parameters; the shared `_isolate`-style
  delenv helper stays harmless but may be dropped.
- `tests/pipeline/test_run_pipeline_contract.py` — the env-decision tests (~lines 100–143)
  rewrite to parameters.
- `tests/pipeline/test_pipeline_cli.py` — `test_pipeline_cli_run_ignores_workflow_flags`
  asserts the OLD env-channel behavior verbatim ("the decision travels via
  GOGA_WORKFLOW_* env vars") and is DELETED — its inverted successor is
  `test_pipeline_cli_run_threads_workflow_and_repeatable_skip`; the exact-kwargs
  `assert_called_once_with(..., parallel=None)` assertions (~lines 227, 248) gain the new
  `workflow=` / `no_workflow=` / `skip=` kwargs.
- `tests/integration/test_workflow_entity.py` — the assertions that the env-file carries
  `GOGA_WORKFLOW_NAME=feature-phases` (~lines 528, 583) invert to "no `GOGA_*` key is
  written; the argv carries `-w feature-phases`".
- `tests/integration/test_pipeline_info_integration.py` — the setenv premise
  (~lines 224–226) rewrites to parameter passing.
- `tests/commands/pipeline/test_run_pipeline_container_workflow.py` — the env-file
  `GOGA_*`-entry assertions (~lines 281–426) invert (no `GOGA_*` key ever written); the
  log-line tests fold into `test_workflow_log_line_matrix`; the auto-match containment
  tests (dotdot / absolute-prefix) survive the rewrite unchanged — the guard stays.
- `tests/commands/pipeline/test_pipeline_dispatch.py` — the exact-kwargs dispatch
  assertions gain `skip` (card: the parsed tuple; listing: unchanged, covered by the
  `skip=()` signature default).
- `tests/commands/pipeline/test_pipeline_workflow_flags.py` — the tests asserting the
  `--no-workflow` env-file write premise (~lines 156–175) rewrite to the argv/log
  surface; the host-side exclusivity and existence-validation tests survive unchanged.


---

### Positive Tests

#### `test_pipeline_cli_run_threads_workflow_and_repeatable_skip`

**Setup**: `tests/pipeline/conftest.py` stages DSL fixture + `hardening.yml` workflow;
`mock.patch("goga.pipeline.cli.run_pipeline")`.

**Input**: `pipeline_cli(["run","deploy","--port","50321","-w","hardening","-s","build","-s","test"])`

**Trace**:
```
pipeline_cli(argv)
  → _build_parser()                     # -s declared action="append"
  → parse_args → Namespace(skip=["build","test"], workflow="hardening", port=50321)
  → _run_execution(args, project_dir, user_dir)
    → run_pipeline("deploy", project_dir, user_dir, 50321,
        workflow="hardening", no_workflow=False, skip=["build","test"], parallel=None)
```

**Assertions**:
```
mock_run.assert_called_once()
kwargs["workflow"] == "hardening"; kwargs["skip"] == ["build","test"]
kwargs["no_workflow"] is False; kwargs["parallel"] is None
```

**Sufficiency**: pins the argv→parameter threading of the whole new channel at the CLI seam;
regresses any revert to env-var reads.

#### `test_pipeline_cli_card_threads_skip`

**Setup**: `mock.patch("goga.pipeline.cli.describe_pipeline")`.

**Input**: `pipeline_cli(["run","deploy","--info","-s","build"])`

**Trace**: `→ _run_card → describe_pipeline("deploy", project_dir, user_dir, workflow=None,
no_workflow=False, skip=["build"])`

**Assertions**: `kwargs["skip"] == ["build"]` (plus workflow None / no_workflow False).

**Sufficiency**: the card side of the dual-mode `-s` — the same flags produce the same
composition in card and run forms.

#### `test_run_argv_carries_workflow_flags_skip_and_parallel`

**Setup**: `tests/commands/pipeline` docker mocks; config with `image`, `pipeline.agent`.

**Input**: `run_pipeline_container(name="deploy", config=..., workflow="hardening",
no_workflow=False, skip=("build","test"), parallel=2, ...)` (docker internals mocked).

**Trace**:
```
run_pipeline_container → _run_named
  → _resolve_workflow_log_name("hardening", False, "deploy") → "hardening"   # log only
  → _build_env_file(...)                                                      # env layers only
  → args = ["-m","goga.pipeline","run","deploy","--port","<P>",
            "-w","hardening","-s","build","-s","test","--parallel","2"]
  → DockerRunner.run(args, ...) captured
```

**Assertions**:
```
captured_args == ["-m","goga.pipeline","run","deploy","--port",str(port),
                  "-w","hardening","-s","build","-s","test","--parallel","2"]
```

**Sufficiency**: the launcher argv assembly is the contract's step 12; exact-order assertion
prevents flag drift (e.g. `--parallel` jumping ahead of `-s`).

#### `test_env_file_carries_no_goga_entries`

**Setup**: same mocks; env-file content captured.

**Input**: run form with `workflow="hardening"`, `skip=("build",)`.

**Trace**: `→ _build_env_file → _write_env_file(env, extra_env)` — `env` keys inspected.

**Assertions**: no key in the file starts with `GOGA_`; `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`
present; the `Pipeline running with workflow "hardening"` line still printed once.

**Sufficiency**: the "env-file carries environment layers only" rule; catches a leftover
`GOGA_SKIP_STAGES`/`GOGA_WORKFLOW_*` write.

#### `test_stale_goga_env_values_are_inert`

**Setup**: docker mocks; `extra_env=("GOGA_WORKFLOW_NAME=zzz","GOGA_SKIP_STAGES=zzz")`.

**Input**: run form with NO workflow flags and empty skip.

**Trace**: `→ _write_env_file` writes the verbatim lines → argv carries no `-w`/`-s` →
`pipeline_cli` → `run_pipeline` reads only `AFM_DIR`.

**Assertions**: argv has no `-w`/`-s`; no warning/error raised; the verbatim lines are present
in the env-file (inert passengers).

**Sufficiency**: the manifest's inertness constraint — user-named GOGA_* values must not
change behavior.

#### `test_card_argv_carries_one_dash_s_per_skip`

**Setup**: `tests/commands/pipeline/test_run_pipeline_info_container.py` mocks.

**Input**: `run_pipeline_info_container(name="deploy", info=True, config=..., hosts={},
update=False, workflow=None, no_workflow=False, skip=("a","b"))`

**Trace**: `→ _compose_argv → ["-m","goga.pipeline","run","deploy","--info","-s","a","-s","b"]`

**Assertions**: exact argv equality.

**Sufficiency**: the card launcher's skip threading; one `-s` per entry, order preserved.

#### `test_card_form_command_forwards_skip_to_info_container`

**Setup**: `CliRunner`, mocked `run_pipeline_info_container`, project with
`.goga/workflows/hardening.yml` when needed.

**Input**: `["pipeline","deploy","--info","-s","build"]`

**Trace**: `→ pipeline click → card dispatch with skip=("build",)`

**Assertions**: call kwargs `skip == ("build",)`, `info is True`, `name == "deploy"`.

**Sufficiency**: the click seam — the card form honors `-s` (previously run-only).

#### `test_run_pipeline_receives_workflow_from_parameters_not_env`

**Setup**: `tests/pipeline` fixtures; `monkeypatch.setenv("GOGA_WORKFLOW_NAME","zzz")`,
`setenv("GOGA_SKIP_STAGES","zzz")`, `AFM_DIR` to tmp.

**Input**: `run_pipeline("deploy", project_dir, user_dir, 50321, workflow="hardening")`
(workflow file present).

**Trace**: `→ resolve_workflow("deploy","hardening",False) → parse hardening.yml → compile with
it` — env values never read.

**Assertions**: the compiled flow (or the compile_flow mock kwargs) reflects `hardening`, not
`zzz`; no stage named `zzz` is skipped.

**Sufficiency**: AFM_DIR-only env read — the core of the channel unification.

#### `test_describe_pipeline_applies_skip_names`

**Setup**: stages DSL with stages `s1,s2,s3`; no workflow file; `skip=["s2"]`.

**Input**: `describe_pipeline("deploy", project_dir, user_dir, None, False, skip=["s2"])`

**Trace**: `→ resolve_workflow → None → apply_skip_stages(None, ["s2"]) → synthesized doc →
compile_flow removes s2 + reconnects → order_stages`

**Assertions**: `[s.id for s in card.stages] == ["s1","s3"]`.

**Sufficiency**: card-side skip merge over a workflow-less pipeline ("skip applies to a
workflow-less pipeline too").

#### `test_card_and_run_skip_equivalence`

**Setup**: same fixtures; capture the composition both ways.

**Input**: `describe_pipeline(..., workflow="w", skip=["s2"])` vs the ordered stages of a
`run_pipeline` compile with the same flags (compile_flow output).

**Trace**: both compose through `resolve_workflow → apply_skip_stages → hooks → compile_flow`.

**Assertions**: identical stage id lists.

**Sufficiency**: "the same flags produce the same composition in card and run forms" — the
equivalence guarantee of the contract.

---

### Negative Tests

#### `test_describe_pipeline_unknown_skip_name_raises_structural_error`

**Setup**: stages DSL `s1,s2`; `skip=["nope"]`.

**Input**: `describe_pipeline("deploy", ..., skip=["nope"])`

**Trace**: `→ apply_skip_stages → compile_flow step 4pre strict check → StructuralError`.

**Assertions**: `pytest.raises(StructuralError)`; the message names the unknown stage; no temp
flow-file remains.

**Sufficiency**: name validation stays in the compiler — the card fails exactly as a run does.

#### `test_run_pipeline_afm_dir_unset_raises`

**Input**: `run_pipeline(...)` with `monkeypatch.delenv("AFM_DIR")`.

**Assertions**: `RuntimeError("AFM_DIR not set")`.

**Sufficiency**: AFM_DIR remains required and is the only env read.

#### `test_w_and_no_workflow_combination_rejected_host_side` (existing, keep)

**Input**: `["pipeline","deploy","-w","x","--no-workflow"]` → exit 1 clean message, no docker.
**Sufficiency**: host owns the exclusivity; unchanged behavior guard.

---

### Edge Case Tests

#### `test_skip_absent_yields_none_not_empty_list`

**Input**: `pipeline_cli(["run","deploy","--port","50321"])`.

**Assertions**: `kwargs["skip"] is None` (argparse append default) — None and [] both mean
no-skip downstream.

**Sufficiency**: pins the `list[str] | None` contract at the parse seam.

#### `test_skip_none_and_empty_cards_identical`

**Setup**: same pipeline; run `describe_pipeline` twice with `skip=None` and `skip=[]`.

**Assertions**: identical card contents (name, description, stage ids, provenance).

**Sufficiency**: the None/[] equivalence stated by both usages and the contract.

#### `test_card_skip_only_over_missing_workflow_is_silent_miss`

**Setup**: NO workflow file anywhere; `skip=["s2"]`.

**Input**: `describe_pipeline("deploy", ..., None, False, skip=["s2"])` with the delivery
mocked/spied.

**Trace**: `resolved=None → apply_skip_stages synthesizes a doc → decision derives from
`resolved` → kind="silent-miss"` (layer active onto the empty base), NOT auto-match/explicit.

**Assertions**: the delivery still runs (layer active) with a workflow that carries only the
skip; the decision kind is silent-miss.

**Sufficiency**: guards the pre-merge decision derivation — deriving from the merged document
would misclassify skip-only synthesis as a resolution (the run path documents this exact rule).

#### `test_no_credential_mounts_in_run_launcher`

**Setup**: docker mocks capture `params["v"]`.

**Input**: run form launch.

**Assertions**: `params["v"] == [f"{project}:/workspace", f"{runtime}:/home/goga/pipeline",
f"{afm_config}:/home/goga/.afm/config.yaml:ro"]` — exactly three engine mounts; no `:ro`
credential entries; no entry under `/home/goga/.claude`, `/home/goga/.codex`,
`/home/goga/.local`.

**Sufficiency**: the credential-removal contract; replaces the deleted
credential-integration tests.

#### `test_no_credential_mounts_in_build_launcher`

**Input**: `build("plan.md", ...)` with docker mocks.

**Assertions**: `params["v"] == [f"{project}:/workspace", f"{runtime}:/workspace/.ralphex"]`.

**Sufficiency**: same, for the build launcher.

#### `test_workflow_log_line_matrix` (rewrite of the existing workflow tests)

**Input** matrix: explicit `-w` → line names it; `--no-workflow` → no line; auto-match file
exists → line names the pipeline; auto-match absent → no line.

**Assertions**: exactly one stdout line in the positive cases; none in the others; the env-file
never carries a GOGA_* key in any case.

**Sufficiency**: the log decision is now purely host-side output — no env side effects.

#### `test_facade_import_surface`

**Input**: `python -c "from goga.agents import resolve_wrapper_path"` (subprocess) plus
`assert not hasattr(goga.agents, "resolve_credential_mounts")`.

**Sufficiency**: the shrunk facade — the checklist's facade check.

---

## Additional Instructions for the Implementation Agent

- Land the change-set in the plan's order: (1) `goga/pipeline` cell code, (2)
  `goga/commands/build`, (3) `goga/commands/pipeline`, (4) tests, (5) run
  `goga lint`, `ruff check goga/`, `pytest tests/ -x`. The two command modules currently fail
  at import (`build.py:16` imports the deleted `resolve_credential_mounts`, which also blocks
  the `goga` facade import chain) — fix both in the same batch.
- `run_pipeline`/`describe_pipeline` parameter insertion moves `parallel`'s position in the
  signature; all in-repo call sites use keywords — keep it that way.
- Do NOT re-add any `GOGA_WORKFLOW_NAME` / `GOGA_WORKFLOW_DISABLED` / `GOGA_SKIP_STAGES` read
  or write anywhere. The only allowed mention in the whole change-set is the inertness
  Constraint already present in `run_pipeline_container`'s manifest.
- Delete the two credential-mount integration test files; invert (do not merely delete) the
  credential assertions inside the runtime-isolation and launcher-tmpfile integration tests —
  they become the no-credential-mount guards.
- Keep `_resolve_workflow_log_name`'s containment guard: an auto-match name escaping
  `.goga/workflows/` is a silent no-log miss, never a wider-filesystem resolve.
- Help texts are contract surface: the click `--no-workflow`/`-s` helps and the argparse
  `-w`/`--no-workflow`/`-s` helps must not reference the env-var channel or "--info mode
  only".
- The `docker-auth-mounts` cook is a user guide now — never wire it back into a CODEMANIFEST
  `Usages` header.
