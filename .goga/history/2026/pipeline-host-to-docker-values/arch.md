# Architecture Plan — pipeline host→container values

Author: Goga
CreatedAt: 25/09/26
Topic branch: pipeline-host-to-docker-values
Decision source: `.goga/history/2026/pipeline-host-to-docker-values/adr.md`
Task source: `.goga/history/2026/pipeline-host-to-docker-values/task.md`

---

## Topic

- Short name: **pipeline-host-to-docker-values**
- Plan path: `.goga/history/2026/pipeline-host-to-docker-values/arch.md`

Unify the host→container context transfer for the goga pipeline launchers on the build model of
cmd-proxying — the workflow decision and skip names travel as in-container argv flags
(`-w/--workflow NAME`, `--no-workflow`, repeatable `-s/--skip NAME`) parsed by `pipeline_cli` and
passed to run coordination and the card as explicit parameters; the three `GOGA_*` env vars are
removed entirely (stale entries are inert). Simultaneously, automatic agent-credential
bind-mounts are removed completely (both launcher call sites, the `goga/agents/credentials`
cell, its facade re-export, and its practice); credential provisioning becomes user-owned via
`home.docker.run` (documented by the rewritten `docker-auth-mounts` user guide).

All cells are **MODIFY** or **DELETE** — nothing is created anew (minimal structural footprint;
existing responsibility zones absorb the change).

---

## Implementation Order

1. **`goga/agents` (MODIFY — facade shrink) + zone deletion** — the facade's export list is what
   the command cells consume; shrinking it first fixes the surface both launchers resolve
   against. The `goga/agents/credentials` cell and the `resolve-credential-mounts` practice are
   deleted in the same step (their remaining consumers are removed here and in steps 4–5).
2. **`goga/pipeline/compiler` (MODIFY — annotation-only)** — independent of every other change;
   its only import (`goga/pipeline/workflow`) is untouched.
3. **`goga/pipeline` (MODIFY — in-container contract)** — owns the new flag surface
   (`pipeline_cli`) and the explicit-parameter signatures (`run_pipeline`, `describe_pipeline`).
   Designed before the host launcher because the host argv addresses exactly this CLI surface and
   the host command cell imports this cell's usages.
4. **`goga/commands/build` (MODIFY — removal only)** — resolves against the shrunk `goga/agents`
   facade (step 1); no other dependency of its changes.
5. **`goga/commands/pipeline` (MODIFY — host launcher onto the argv channel)** — the root of the
   change-set: consumes step 1's facade and step 3's usages/CLI surface; lands last so both
   workstreams (channel unification + credential removal) arrive as one coherent shift in
   `run_pipeline_container`.
6. **Project-level documentation** — `.goga/usages/cooks/docker-auth-mounts.md` (rewrite) and
   `.goga/usages/cooks/afm.md` (fragment realignment) ship with the same change-set (they
   document the launcher contract and the user-owned channel; drift is never deferred).

Tests, per project convention, accompany each artifact (checklist below).

---

## Artifacts

### Cell 1 — `goga/agents` (MODIFY, facade shrink)

**CODEMANIFEST diff** — four edits; everything else unchanged:

1. Imports — remove the entry:

```yaml
  - Types:
      - resolve_credential_mounts
    From: goga/agents/credentials
```

   (the `goga/agents/wrapper` import entry stays verbatim).

2. Global Annotations — replace the facade paragraph. Remove:

```
  This cell is the facade of the agent-tooling area. It exposes two pure
  routines as the single stable import point for agent-related resolution:

  - `resolve_wrapper_path` — agent name → in-container *-as-claude.sh wrapper path
  - `resolve_credential_mounts` — host filesystem → list of (host_path,
    container_path) tuples for credential files to bind-mount read-only

  This cell has no own types — it is re-export only. The implementations
  live in subcells under this facade (goga/agents/wrapper,
  goga/agents/credentials).
```

   Add:

```
  This cell is the facade of the agent-tooling area. It exposes one pure
  routine as the single stable import point for agent-related resolution:

  - `resolve_wrapper_path` — agent name → in-container *-as-claude.sh wrapper path

  This cell has no own types — it is re-export only. The implementation
  lives in the subcell goga/agents/wrapper.
```

3. Body — delete the embedding `->resolve_credential_mounts: {}` (keep
   `->resolve_wrapper_path: {}`).

4. Footer Description — replace with:

```yaml
Description: |
  Agent tooling area. Provides the tool for working with AI agents —
  wrapper path resolution.
```

**.usages/ files**:
- DELETE `goga/agents/.usages/resolve-credential-mounts.md`.
- `resolve-wrapper-path.md` — unchanged.

**Deletion (same step)**: DELETE the cell directory `goga/agents/credentials/` (CODEMANIFEST +
`resolve.py` implementation + its tests).

---

### Cell 2 — `goga/pipeline/compiler` (MODIFY, annotation-only)

**CODEMANIFEST diff** — one edit in the `compile_flow` annotations, step 4.9 parenthetical.
Remove:

```
           (embedded extend-stages included; a stage removed by skip —
           workflow skip OR the CLI GOGA_SKIP_STAGES channel — never
           counts, so a run whose every participating stage was skipped
           emits no block)
```

Add:

```
           (embedded extend-stages included; a stage removed by skip —
           a workflow-file skip directive OR a CLI skip directive — never
           counts, so a run whose every participating stage was skipped
           emits no block)
```

**.usages/ files** — none changed.

---

### Cell 3 — `goga/pipeline` (MODIFY, in-container contract)

**CODEMANIFEST diff** — six edit groups.

1. Header `argparse` inline practice — replace the block. Remove:

```
  argparse: |
    Use the standard library argparse module for in-container CLI parsing.
    Two subcommands: list (with an optional --info flag) and run (a required
    name, an optional --info flag, optional workflow flags, --port required
    only without --info, and an optional --parallel N).
```

   Add:

```
  argparse: |
    Use the standard library argparse module for in-container CLI parsing.
    Two subcommands: list (with an optional --info flag) and run (a required
    name, an optional --info flag, the workflow flags -w/--workflow NAME and
    --no-workflow, a repeatable -s/--skip NAME — all three available with and
    without --info, --port required only without --info, and an optional
    --parallel N).
```

2. Global Annotations — replace two paragraphs. Remove:

```
  GOGA_SKIP_STAGES=<csv> carries the CLI skip names in run coordination:
  applied in-memory onto the resolved workflow before compilation. The CLI
  performs no stage-name validation — unknown names surface as the compiler's
  structural error.
```

   Add:

```
  The CLI skip names arrive as an explicit parameter of run coordination and
  the card: applied in-memory onto the resolved workflow before compilation.
  The CLI performs no stage-name validation — unknown names surface as the
  compiler's structural error.
```

   Remove:

```
  The card reads no run-only
  GOGA_SKIP_STAGES environment variable — the CLI skip channel is a run
  concern — while workflow-file skip directives apply through the shared
  compilation machine (they are part of the composition a run with the same
  workflow flags executes).
```

   Add:

```
  The card applies the CLI skip names through the same in-memory merge a run
  applies, and workflow-file skip directives arrive through the shared
  compilation machine — both are part of the composition a run with the same
  flags executes.
```

3. `pipeline_cli` annotations — four edits.

   Algorithm step 1, the run bullet — remove:

```
       - run: a required name positional; an optional --info/-i flag; optional
         --workflow/-w NAME and --no-workflow flags; a --port PORT integer
         required only when --info is absent; an optional --parallel N integer
```

   add:

```
       - run: a required name positional; an optional --info/-i flag; optional
         --workflow/-w NAME and --no-workflow flags and a repeatable
         --skip/-s NAME flag (all three available with and without --info);
         a --port PORT integer required only when --info is absent; an
         optional --parallel N integer
```

   Algorithm step 4, the two run dispatch bullets — remove:

```
       - run with --info — call `describe_pipeline` with the name and the
         parsed workflow flags; print the card: "name:" and "description:"
```

   (keep the rest of that bullet's template text) and:

```
       - run without --info — call `run_pipeline` with name, port, and
         parallel; return its exit code
```

   add:

```
       - run with --info — call `describe_pipeline` with the name, the parsed
         workflow flags, and the parsed skip names; print the card: "name:" and "description:"
```

   and:

```
       - run without --info — call `run_pipeline` with name, port, the parsed
         workflow flags, the parsed skip names, and parallel; return its exit
         code
```

   Requirements — remove:

```
    - The run subcommand accepts --info/-i, --workflow/-w NAME,
      --no-workflow, --parallel N
```

   add:

```
    - The run subcommand accepts --info/-i, --workflow/-w NAME,
      --no-workflow, the repeatable --skip/-s NAME, and --parallel N; the
      workflow and skip flags bind in both info and run modes
```

   Constraints — remove:

```
    - Do not validate workflow flag combinations — the host-side launcher
      owns that validation
```

   add:

```
    - Do not validate workflow flag combinations or skip stage names — the
      host-side launcher owns the flag-combination validation and the
      compiler owns the stage-name error
```

4. `run_pipeline` — signature and annotations.

   Signature — replace:

```yaml
"run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int, parallel: int | None = None) -> exit_code: int":
```

   with:

```yaml
"run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int, workflow: str | None = None, no_workflow: bool = False, skip: list[str] | None = None, parallel: int | None = None) -> exit_code: int":
```

   Description lead — remove:

```
    Resolve a pipeline name to an absolute file path via `list_pipelines`,
    resolve an optional workflow via `resolve_workflow` from the environment
    decision, deliver the workflow amendment through the pipeline hooks zone,
```

   add:

```
    Resolve a pipeline name to an absolute file path via `list_pipelines`,
    resolve an optional workflow via `resolve_workflow` from the CLI-provided
    decision, merge the CLI skip names via `apply_skip_stages`, deliver the
    workflow amendment through the pipeline hooks zone,
```

   Parameter docs — after the `port` doc and before the `parallel` doc, add:

```
    `workflow`: optional explicit workflow name (without the .yml extension) —
                the CLI decision from the -w flag; None with `no_workflow`
                unset resolves the basename auto-match
    `no_workflow`: when True, workflow application is disabled — the CLI
                   decision from the --no-workflow flag
    `skip`: stage names to skip — the CLI decision from the repeatable -s
            flags; None and an empty list both mean no skip
```

   Algorithm step 6 — remove:

```
    6. Read the workflow decision from the environment —
       GOGA_WORKFLOW_DISABLED="1" disables the workflow, otherwise
       GOGA_WORKFLOW_NAME names an explicit workflow — and resolve via
       `resolve_workflow` with the pipeline name
```

   add:

```
    6. Resolve the workflow via `resolve_workflow` with the pipeline name and
       the `workflow` / `no_workflow` parameters — the CLI decision arrives
       as explicit arguments, never from the environment
```

   Algorithm step 7 — remove:

```
    7. Read GOGA_SKIP_STAGES from the environment (unset/empty — no skip);
       when non-empty split into names and apply via `apply_skip_stages`
       onto the resolved workflow
```

   add:

```
    7. Apply the `skip` names via `apply_skip_stages` onto the resolved
       workflow (None/empty — no skip)
```

   Requirements — remove:

```
    - Read AFM_DIR, GOGA_WORKFLOW_DISABLED, GOGA_WORKFLOW_NAME, and
      GOGA_SKIP_STAGES directly from the process environment
    - GOGA_WORKFLOW_DISABLED="1" takes precedence over GOGA_WORKFLOW_NAME
```

   add:

```
    - Read AFM_DIR directly from the process environment — the only
      environment read; the workflow decision and the skip names arrive as
      parameters
    - `no_workflow` takes precedence over `workflow` (the host-side launcher
      rejects the combined use; the precedence is defensive)
```

5. `describe_pipeline` — signature and annotations.

   Signature — replace:

```yaml
"describe_pipeline(name: str, project_dir: Path, user_dir: Path, workflow: str | None, no_workflow: bool) -> card: PipelineCard":
```

   with:

```yaml
"describe_pipeline(name: str, project_dir: Path, user_dir: Path, workflow: str | None, no_workflow: bool, skip: list[str] | None = None) -> card: PipelineCard":
```

   Parameter docs — after the `no_workflow` doc, add:

```
    `skip`: stage names to skip — merged exactly as a run with the same flags
            merges them; None and an empty list both mean no skip
```

   Algorithm — insert a new step after step 2 (workflow resolution) and renumber the existing
   steps 3–7 to 4–8:

```
    3. Apply the `skip` names via `apply_skip_stages` onto the resolved
       workflow (None/empty — no skip)
```

   In the (renumbered) delivery step, replace "with the resolved workflow" with "with the merged
   workflow", and in its disabled branch replace "the overlay is the passthrough `WorkflowOverlay`
   of the resolved workflow" with "the overlay is the passthrough `WorkflowOverlay` of the merged
   workflow".

   Requirements — remove:

```
    - The stage composition equals the composition a run of the same pipeline
      with the same workflow flags would execute — the same amendment layer
      with the same precedence and the same compilation machine produce
      both
```

   add:

```
    - The stage composition equals the composition a run of the same pipeline
      with the same workflow and skip flags would execute — the same
      amendment layer with the same precedence and the same compilation
      machine produce both
```

   Remove:

```
    - The run-only GOGA_SKIP_STAGES environment variable is not read — the
      CLI skip channel is a run concern; workflow-file skip directives DO
      apply through the shared compilation machine (part of the composition
      a run with the same workflow flags executes)
```

   add:

```
    - The CLI skip names apply through the same in-memory merge a run applies
      and are reflected in the stage list; workflow-file skip directives
      apply through the shared compilation machine — both compose exactly
      as a run with the same flags
```

6. `apply_skip_stages` annotations — one parameter-doc edit. Remove:

```
    `skip_stages`: stage names to skip (from the comma-split GOGA_SKIP_STAGES
                   container env var); an empty list is a no-op
```

   add:

```
    `skip_stages`: stage names to skip (the repeatable -s/--skip flag names
                   passed by run coordination and the card); an empty list
                   is a no-op
```

**.usages/ files** — three files replaced wholesale (full content):

**File:** `goga/pipeline/.usages/run-pipeline.md`

```md
# run_pipeline — in-container run coordination

`run_pipeline` resolves a pipeline name to a file, resolves an optional workflow from the
CLI-provided decision, merges the CLI skip names, delivers the workflow amendment through the
pipeline hooks zone, compiles the pipeline-file to an afm flow-file via `compile_flow`,
materializes the four agent prompt files, emits the run-creation facts, launches afm via
`run_flow`, and emits the run-completion facts on its return.

## Signature

run_pipeline(name, project_dir, user_dir, port, workflow=None, no_workflow=False, skip=None,
parallel=None) -> exit_code

- `name: str` — pipeline name without extension
- `project_dir: Path` / `user_dir: Path` — absolute project / user pipeline directories
- `port: int` — dashboard port, allocated by the host-side launcher
- `workflow: str | None` — explicit workflow name without the `.yml` extension; None falls back
  to the basename auto-match
- `no_workflow: bool` — when True, workflow application is disabled
- `skip: list[str] | None` — stage names to skip; None and empty both mean no skip
- `parallel: int | None` — cap on concurrently executing stages; None means unbounded

## Workflow resolution

The workflow decision arrives as explicit parameters — the in-container CLI parses the
`-w WORKFLOW` / `--no-workflow` flags of the run subcommand. `no_workflow=True` disables
application; `workflow` names an explicit workflow; neither triggers the basename auto-match
(a workflow file named like the pipeline). Resolution follows the shared rule set — the same
rules the info card applies — so a run and a card with the same flags always agree on which
workflow applies. A missing auto-match file is a silent miss.

## Skip

`skip` (the repeatable `-s NAME` names of the run subcommand; None and empty both mean no skip)
is applied in-memory onto the resolved workflow before compilation via `apply_skip_stages`.
Skip applies to a workflow-less pipeline too. Unknown names surface as the compiler's structural
error.

## Workflow amendment

After the skip merge and before compilation, the workflow amendment is delivered through the
pipeline hooks zone (`PipelineHooks.amend_workflow`); `compile_flow` receives the effective
workflow the delivery returns. An explicit workflow disable turns the layer off — the merged
(skip-bearing) workflow composes and no amendment delivers; a silent auto-match miss keeps the
layer active onto the empty base. With no tool packages installed the overlay is the passthrough
— every run composes exactly what was passed. The amendment is a hard action: the first failing
tool stops the command with a clean error, and its whole contribution is discarded.

## Run events

`run_created` fires immediately before the runner launch — after compilation and prompt
materialization. `run_completed` fires on every launch-attempt return — zero, non-zero, and
spawn failures (126/127) alike — with the work statuses recomputed at the completion moment and
the actual exit code. Both notifications are soft: a failing hook warns and the run's exit code
is unaffected. A missing pipeline and a structural composition error fire no events — the
return happens before the checkpoints.

## Environment

The only environment read is `AFM_DIR` — the in-container afm state directory. Run options (the
workflow decision, the skip names, the parallel cap) never travel through the environment; they
arrive as parameters from the CLI.

## Threading chains (host → container)

    goga pipeline NAME -p N
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → pipeline_cli: parallel = N
          → run_pipeline(…, parallel=N)
            → run_flow(…, max_parallel=N)
              → afm run --port PORT --max-parallel N <flow>

    goga pipeline NAME -w hardening -s build -s test
      → docker run … -m goga.pipeline run NAME --port PORT -w hardening -s build -s test
        → pipeline_cli: workflow="hardening", skip=["build", "test"]
          → run_pipeline(…, workflow="hardening", skip=["build", "test"])

Absent flag ⇒ None ⇒ auto-match / no skip / unbounded.
```

**File:** `goga/pipeline/.usages/pipeline-cli.md`

```md
# pipeline_cli — in-container CLI for python -m goga.pipeline

`pipeline_cli` parses argv via argparse and dispatches to the flat listing (`list_pipelines`),
the overview (`describe_pipelines`), the card (`describe_pipeline`), or run coordination
(`run_pipeline`). Invoked by the host-side docker launcher through the runpy entrypoint in
`__main__.py`.

## Subcommands

### list

`list [--info]`

- Without `--info`: prints the flat list — one bullet line per pipeline: `* <name>` (with the
  " (project)" suffix for project source entries); no header line.
- With `--info`/`-i`: prints the overview — one bullet block per pipeline: the marker line
  `* <name>` (with the " (project)" suffix for project source entries) followed by `name:` and
  `description:` field lines indented by four spaces; `name:` carries the authored header name,
  `description:` the header description.
- An empty discovery prints nothing (flat list and overview alike); exit code 0.

### run

`run NAME [--info] [-w WORKFLOW | --no-workflow] [-s NAME]... [--port PORT] [--parallel N]`

- NAME (positional, required) — pipeline name without extension.
- `--info`/`-i` (flag) — print the card instead of running: `name:` and `description:` field
  lines, a blank line, a `---` separator, a blank line, then one bullet block per stage in
  execution order — the marker line `* <id>:` and a `title:` field line indented by four
  spaces. When the card provenance is non-empty, one blank line and one `tools:` field line
  follow the stage blocks — the contributing tools comma-separated in provenance order; an
  empty provenance adds nothing (byte-identical card).
- `-w WORKFLOW` / `--no-workflow` — the workflow decision, available in BOTH modes: a run and a
  card resolve it through the same shared rule set. `--no-workflow` disables application;
  `-w WORKFLOW` names an explicit workflow; neither flag triggers the basename auto-match.
- `-s NAME` (repeatable) — stage names to skip, available in BOTH modes: a run applies them to
  the execution, a card reflects them in the composition. Forwarding-only — unknown names
  surface as the compiler's structural error during composition.
- `--port PORT` (int) — dashboard port, allocated by the host launcher. Required only when
  `--info` is absent; ignored in info mode.
- `--parallel N` (int, optional) — max concurrently executing stages; run mode only.

Dispatch: run without `--info` → `run_pipeline(NAME, project_dir, user_dir, PORT,
workflow=<WF or None>, no_workflow=<bool>, skip=<names or None>, parallel=<N or None>)`; run
with `--info` → `describe_pipeline(NAME, project_dir, user_dir, workflow=<WF or None>,
no_workflow=<bool>, skip=<names or None>)`.

## Exit codes

0 success; 2 argparse error (including a missing `--port` without `--info`); non-zero operation
failure, rendered as a clean stderr message without a traceback.
```

**File:** `goga/pipeline/.usages/describe-pipeline.md`

```md
# describe_pipeline — pipeline card without running

`describe_pipeline` composes the card of a single pipeline: the authored name and description
from the DSL header, plus the stage list (id and title per stage) in execution order — the
composition a run of the same pipeline with the same workflow and skip flags would execute. The
card composes through the pipeline hooks zone — the same amendment layer with the same
precedence a run applies — and names the tools whose contributions committed into the
composition. No run events fire in card form. Nothing is launched and nothing is written into
the project or runtime directories.

## Usage

```python
from pathlib import Path
from goga.pipeline import describe_pipeline

card = describe_pipeline(
    name="deploy",
    project_dir=Path("/workspace/.goga/pipelines"),
    user_dir=Path("/home/goga/.goga/pipelines"),
    workflow="hardening",  # explicit workflow; None → basename auto-match
    no_workflow=False,
    skip=["build"],  # skip names; None → no skip
)
print(f"name: {card.name}")
print(f"description: {card.description}")
print()
print("---")
print()
for stage in card.stages:
    print(f"* {stage.id}:")
    print(f"    title: {stage.title}")
```

## Parameters

- `name: str` — pipeline name without extension
- `project_dir: Path` — project pipelines directory (absolute)
- `user_dir: Path` — user pipelines directory (absolute)
- `workflow: str | None` — explicit workflow name without the `.yml` extension; `None` with
  `no_workflow=False` resolves the basename auto-match (`<name>.yml` in `.goga/workflows/`); a
  missing file is a silent miss
- `no_workflow: bool` — when True, no workflow is applied and the raw DSL composition is
  reported (CLI skip names still compose)
- `skip: list[str] | None` — stage names to skip, merged exactly as a run with the same flags
  merges them; `None` and empty both mean no skip

Returns `PipelineCard`.

## The models

`PipelineCard` — `@dataclass(kw_only=True)`:

- `name: str` — pipeline name from the DSL header
- `description: str` — pipeline description from the DSL header
- `stages: list[CardStage]` — stage rows in execution order
- `provenance: list[str]` — the tools whose contributions committed into the composition, in
  enumeration order; empty when none contributed

`CardStage` — `@dataclass(kw_only=True)`:

- `id: str` — stage identifier
- `title: str` — stage display title

## Workflow and skip equivalence

`workflow` / `no_workflow` / `skip` follow one rule set shared with run coordination: disabled →
raw composition; explicit name → that workflow file; otherwise basename auto-match; a missing
file is a silent miss. The skip names merge onto the resolved workflow in-memory — the same
merge a run applies. The card composes through the pipeline hooks zone with the same precedence
a run applies — the same flags produce the same composition and the same provenance in both
forms, and the card names the contributing tools (`card.provenance`). The stage composition is
produced by the same compilation machine a run uses, so loop-expanded copies appear as separate
rows with their generated ids, and skipped stages disappear from the list exactly as they
disappear from a run. No run events fire in card form.

## Side effects

- Reads the pipeline-file and, when one resolves, the workflow-file.
- Writes one temporary flow-file in the system temporary directory (outside the project and
  runtime directories) and removes it before returning.

## Preconditions

- Both directories must be absolute.
- An unknown `name` raises a readable error naming the pipeline.
- A damaged pipeline-file or workflow-file raises a readable structural error.

## Anti-patterns

- Do not apply skip by rewriting the workflow-file — the merge is in-memory; pass the names.
- Do not treat the card as a launch — no afm invocation, no agents, no state changes.
```

Unchanged: `list-pipelines.md`, `describe-pipelines.md`, `registering-hooks.md`.

---

### Cell 4 — `goga/commands/build` (MODIFY, removal only)

**CODEMANIFEST diff** — four edit groups.

1. Imports — remove the entry:

```yaml
  - Types:
      - resolve_credential_mounts
    Usages:
      - resolve-credential-mounts
    From: goga/agents
```

2. Header Usages — remove the key `docker-auth-mounts: .goga/usages/cooks/docker-auth-mounts.md`.

3. Global Annotations — remove the two sentences:

```
  Use `resolve_credential_mounts` and the `resolve-credential-mounts`
  practice to obtain the list of credential files to bind-mount read-only into
  the container.
  Use the `docker-auth-mounts` practice for the read-only credential-mount rule
  applied when assembling the docker run command.
```

4. `build` annotations — removals only:
   - Apply block: remove "Apply the `resolve-credential-mounts` practice for the credential-mount
     consumer pattern." and "Apply the `docker-auth-mounts` practice for the read-only mount
     rule."
   - Algorithm step 14 params: in the `v=[...]` list remove ", and each credential mount
     read-only" (leaving `v=[CWD:/workspace, the resolved host runtime dir (step 11) read-write
     at /workspace/.ralphex]`); in the assembled-form prose remove the clause "; each
     credential mount from `resolve_credential_mounts` read-only" (the clause ends right
     before the closing parenthesis of the mounts enumeration, which stays).
   - Requirements: remove the bullet "Credential mounts come from
     `resolve_credential_mounts` — every returned tuple is an existing file, no re-check
     needed".
   - Constraints: remove the bullet "Do not filter credential mounts by the configured build
     agent — detection is agent-agnostic (see the `resolve-credential-mounts` practice)".

**.usages/ files** — `build.md`: replace the Requirements bullet (line 85). Remove:

```
- Credential mounts are detected automatically via `resolve_credential_mounts()` — there is no
  `--credential`/`--mount` flag. The routine scans the host filesystem for known AI-agent
  credential files (claude `~/.claude/.credentials.json`, codex `~/.codex/auth.json`, opencode
  `~/.local/share/opencode/auth.json`), is agent-agnostic (it is not filtered by the configured
  `build.agent`), and returns only files that exist. Every returned file is bind-mounted
  read-only into the container at the mirrored path under `/home/goga/`. When none exist, no
  credential mount is added — see the `resolve-credential-mounts` and `docker-auth-mounts`
  practices for details
```

Add:

```
- Credential files are NOT mounted automatically — the launcher adds no credential mounts. To
  give the in-container agents access to credentials, mount them yourself through the home
  configuration (`docker.run` volume tokens in ~/.goga/config.yml) or pass environment
  variables with `-e/--env` — see the `docker-auth-mounts` user guide for the host→container
  path table and the recommended read-only mounts
```

---

### Cell 5 — `goga/commands/pipeline` (MODIFY, host launcher onto the argv channel)

**CODEMANIFEST diff** — seven edit groups.

1. Imports — replace the `goga/agents` entry. Remove:

```yaml
  - Types:
      - resolve_wrapper_path
      - resolve_credential_mounts
    Usages:
      - resolve-wrapper-path
      - resolve-credential-mounts
    From: goga/agents
```

   Add:

```yaml
  - Types:
      - resolve_wrapper_path
    Usages:
      - resolve-wrapper-path
    From: goga/agents
```

2. Header Usages — remove the key
   `docker-auth-mounts: .goga/usages/cooks/docker-auth-mounts.md`.

3. Global Annotations — three edits:
   - Remove the guidance:

```
  Use `resolve_credential_mounts` and the `resolve-credential-mounts`
  practice to obtain the credential files bind-mounted read-only into the
  container; use the `docker-auth-mounts` practice for the read-only mount
  rule. Use `resolve_runtime_dir` and the `runtime-paths` practice to compute
```

     rejoining the surviving text as "Use `resolve_runtime_dir` and the `runtime-paths` practice
     to compute the host-side runtime directory."
   - In the launcher-shape paragraph replace "the run launcher (full shape — allocated port,
     env-file, afm-config tmpfile, persistent afm state, credential mounts, signal handling)"
     with "the run launcher (full shape — allocated port, env-file, afm-config tmpfile,
     persistent afm state, signal handling)".
   - Add the channel boundary rule right after the launcher-shape paragraph:

```
  Everything the in-container CLI consumes (run options) travels as command
  arguments after the image; everything the afm binary, agents, and tools
  consume travels through the env-file. The env-file carries environment
  layers only — run options never enter it.
```

4. `pipeline` annotations — three edits:
   - `skip` parameter doc — remove:

```
    `skip`: raw stage names from the repeatable -s/--skip option. Run form
            only; forwarded into the container env-file; names are validated
            in-container only.
```

     add:

```
    `skip`: raw stage names from the repeatable -s/--skip option. Run and card
            forms; forwarded into the in-container argv as one -s flag per
            name; names are validated in-container only.
```

   - Algorithm step 4, card branch — replace:

```
       - card — `run_pipeline_info_container` with the name, info=True, and
         the workflow flags
```

     with:

```
       - card — `run_pipeline_info_container` with the name, info=True, the
         workflow flags, and the skip names
```
   - Requirements — replace the bullet "The listing and info forms silently ignore -e/--env,
     --proxy, -c/--clean, -s/--skip, -p/--parallel, and --add-host — no side effects; --clean
     deletes nothing" with:

```
    - The listing forms silently ignore -e/--env, --proxy, -c/--clean,
      -s/--skip, -p/--parallel, and --add-host — no side effects; --clean
      deletes nothing
    - The card form forwards the skip names — the same flags produce the same
      composition in card and run forms
```

     and replace the bullet "The run form forwards `skip` and `parallel` as parsed — no
     validation, no defaulting" with:

```
    - The run and card forms forward `skip` as parsed — one -s flag per name,
      no validation, no defaulting; the run form forwards `parallel` as
      parsed
```

5. `run_pipeline_container` annotations — the channel rewrite:
   - Parameter docs — replace the `workflow`, `no_workflow`, and `skip` docs. Remove:

```
    `workflow`: optional workflow name forwarded into the container env-file
                as GOGA_WORKFLOW_NAME=<workflow>. When None AND
                `no_workflow` is False, the env-file carries neither
                workflow env var — the in-container run coordination attempts
                the basename auto-match fallback. The caller (the `pipeline`
                click command) has already validated file existence on the
                host when this is non-None.
    `no_workflow`: when True, write GOGA_WORKFLOW_DISABLED=1 into the
                   container env-file, forcing the in-container run
                   coordination to skip workflow resolution entirely.
                   Mutually exclusive with `workflow` (enforced by the
                   caller).
    `skip`: stage names (default empty). Joined comma-separated into the
            GOGA_SKIP_STAGES container env-file entry when non-empty.
```

     add:

```
    `workflow`: optional workflow name forwarded into the in-container argv
                as -w <workflow>. When None AND `no_workflow` is False, the
                argv carries neither workflow flag — the in-container run
                coordination attempts the basename auto-match fallback. The
                caller (the `pipeline` click command) has already validated
                file existence on the host when this is non-None.
    `no_workflow`: when True, --no-workflow joins the in-container argv,
                   forcing the in-container run coordination to skip workflow
                   resolution entirely. Mutually exclusive with `workflow`
                   (enforced by the caller).
    `skip`: stage names (default empty). Each name appends one -s <name> to
            the in-container argv; names are forwarded as-is (no validation,
            no dedup).
```

   - Algorithm step 9 — remove the workflow env matrix:

```
    9. Compute the workflow env-file entries (host-side, BEFORE container
       launch):
       - When `no_workflow` is True:
         * workflow_env = {"GOGA_WORKFLOW_DISABLED": "1"}
         * workflow_log_name = None (no log emitted)
       - Else when `workflow` is not None (explicit --workflow, file already
         validated by the caller):
         * workflow_env = {"GOGA_WORKFLOW_NAME": workflow}
         * workflow_log_name = workflow
       - Else (auto-match fallback):
         * Compose auto_match_path as <cwd>/.goga/workflows/<name>.yml
         * When the auto-match file exists:
           - workflow_env = {} (in-container resolution handles the
             basename fallback)
           - workflow_log_name = name (the candidate)
         * Else:
           - workflow_env = {} (in-container resolution will silent-miss)
           - workflow_log_name = None (no log — file does not exist)
```

     add:

```
    9. Compute the workflow log decision (host-side, BEFORE container
       launch):
       - When `no_workflow` is True — no workflow log
       - Else when `workflow` is not None (explicit --workflow, file already
         validated by the caller) — log the given name
       - Else (auto-match fallback) — compose auto_match_path as
         <cwd>/.goga/workflows/<name>.yml; log the pipeline name exactly
         when that file exists; otherwise no log
```

   - Algorithm step 11 — remove the workflow and skip entry clauses. In the step text, delete
     the clause:

```
— then the workflow_env
entries (GOGA_WORKFLOW_NAME and/or GOGA_WORKFLOW_DISABLED per
step 9), the GOGA_SKIP_STAGES entry when `skip` is non-empty
(joined comma-separated via ",".join(skip); omitted when `skip` is
empty), and
```

     so the sentence reads "... the roots never diverge from the actual
     mounts of the launch — when `proxy` is not-None — HTTP_PROXY,
     HTTPS_PROXY, and NO_PROXY (fixed at localhost,127.0.0.1). ..." (the
     channel boundary rule itself lives once, in the global Annotations).

   - Algorithm step 12 — argv and mounts. In the args item remove:

```
        - args: -m goga.pipeline run <name> --port <port>
          [--parallel <parallel>] (--parallel <parallel> appended ONLY when
          not None; omitted when None)
```

     add:

```
        - args: -m goga.pipeline run <name> --port <port> [-w <workflow>]
          [--no-workflow] [-s <name>]... [--parallel <parallel>] — the
          workflow flags appended exactly as given (neither flag on
          auto-match), one -s per skip name, --parallel appended ONLY when
          not None; omitted when None
```

     In the params item remove ", and each credential mount read-only" (leaving the project,
     persistent afm state, and afm-config tmpfile mounts). In the assembled-form prose remove
     "each credential mount from `resolve_credential_mounts` read-only,".
   - Apply block — remove the two lines "Apply the `resolve-credential-mounts` practice for the
     credential-mount consumer pattern." and "Apply the `docker-auth-mounts` practice for the
     read-only mount rule."; replace the `run-pipeline` practice line. Remove:

```
    Apply the `run-pipeline` practice for the in-container prompt
    materialization contract that populates the prompts_dir directory, and
    for the workflow environment contract (GOGA_WORKFLOW_NAME /
    GOGA_WORKFLOW_DISABLED) that this launcher sets via the env-file in
    steps 9-11.
```

     add:

```
    Apply the `run-pipeline` practice for the in-container prompt
    materialization contract that populates the prompts_dir directory and
    for the explicit-parameter contract of the workflow decision and skip
    names the argv carries.
```

   - Requirements — remove:

```
    - Credential mounts come from `resolve_credential_mounts` — every returned
      tuple is an existing file, no re-check needed
```

     remove:

```
    - Workflow env-file entries follow the decision matrix in step 9:
      --no-workflow → GOGA_WORKFLOW_DISABLED=1; explicit --workflow X →
      GOGA_WORKFLOW_NAME=X; auto-match fallback → neither env var (the
      container resolves the basename). The decision is taken host-side so
      the workflow log is accurate
    - Write GOGA_SKIP_STAGES=<csv> into the container env-file when `skip`
      is non-empty
```

     add:

```
    - The run argv carries the workflow decision exactly as given: -w <name>,
      --no-workflow, or neither (in-container auto-match); the skip names
      append one -s <name> per entry — forwarded as parsed, no validation
```

     (The env-file content bullet, the workflow log-line bullet, and the --parallel bullet stay
     verbatim.)
   - Constraints — remove "Do not filter credential mounts by config.pipeline.agent — detection
     is agent-agnostic (see the `resolve-credential-mounts` practice)"; in the file-roots
     constraint replace:

```
      mounts (the persistent afm state, the config overlay, credentials)
      never become roots
```

     with:

```
      mounts (the persistent afm state, the config overlay)
      never become roots
```

     ; add:

```
    - Do not write or interpret any GOGA_WORKFLOW_NAME, GOGA_WORKFLOW_DISABLED,
      or GOGA_SKIP_STAGES entry — user-supplied values of those names (via -e
      or home.env) may travel in the env-file verbatim and stay inert: no
      warning, no error
```

6. `run_pipeline_info_container` — signature and annotations. Replace the signature:

```yaml
"run_pipeline_info_container(name: str | None, info: bool, config: ProjectConfig, hosts: dict[str, str], update: bool, workflow: str | None, no_workflow: bool) -> exit_code: int":
```

   with:

```yaml
"run_pipeline_info_container(name: str | None, info: bool, config: ProjectConfig, hosts: dict[str, str], update: bool, workflow: str | None, no_workflow: bool, skip: tuple[str, ...] = ()) -> exit_code: int":
```

   After the `no_workflow` parameter doc add:

```
    `skip`: stage names forwarded to the card form — one -s <name> appended
            to the card argv per entry
```

   Algorithm step 3, card line — replace:

```
       - card: -m goga.pipeline run NAME --info, plus -w WORKFLOW when
         `workflow` is provided or --no-workflow when `no_workflow` is set
```

   with:

```
       - card: -m goga.pipeline run NAME --info, plus -w WORKFLOW when
         `workflow` is provided or --no-workflow when `no_workflow` is set,
         plus one -s NAME per skip entry
```

   Requirements — replace the card-argv bullet:

```
    - The card argv carries the workflow decision exactly as given:
      explicit -w WORKFLOW, --no-workflow, or neither (in-container
      auto-match)
```

   with:

```
    - The card argv carries the workflow decision and the skip names exactly
      as given: explicit -w WORKFLOW, --no-workflow, or neither (in-container
      auto-match), and one -s NAME per skip entry
```

   Requirements — also replace the minimal-shape bullet (the credential member names the removed
   engine feature). Remove:

```
    - The minimal shape holds for all three forms: no published port, no
      env-file, no afm-config tmpfile, no persistent afm state mount, no
      credential mounts, no caller-side signal handler
```

   with:

```
    - The minimal shape holds for all three forms: no published port, no
      env-file, no afm-config tmpfile, no persistent afm state mount, no
      caller-side signal handler
```

7. `collect_file_roots` constraints — replace:

```
    - Do not include engine mounts — afm state, the config overlay, and
      credentials never become roots
```

   with:

```
    - Do not include engine mounts — afm state and the config overlay
      never become roots
```

**.usages/ files** — `pipeline-command.md`, five fragment edits (all other sections verbatim):

- Options table row — replace `| -s / --skip NAME | repeatable | exclude a stage; run only |`
  with `| -s / --skip NAME | repeatable | exclude a stage; run and card forms |`.
- "Flag behavior in the list/info forms" — replace the section body with:

```md
- Ignored in the listing forms (no-op, no side effects): `-e/--env`, `--proxy`, `-c/--clean`,
  `-p/--parallel`, `--add-host`, `-t/--topic`, `--todo`.
- `-u/--update`: works in `--list` without `--info`; no-op in both `--info` forms.
- `-w/--workflow`, `--no-workflow`, and `-s/--skip`: validated as usual (exclusivity and, for
  -w, file existence) and honored by the card form — the same flags produce the same
  composition in card and run forms.
- All errors go to stderr with a non-zero exit code; stdout stays clean for the listing,
  overview, and card output.
```

- "Docker shapes" — replace the section body with:

```md
- Run form: full shape — allocated port, env-file, afm-config tmpfile, persistent afm state
  mount, caller-side signal handler.
- List/info forms: minimal read-only shape — none of the above. The decision travels in the
  subcommand argv: `-m goga.pipeline list [--info]` or `-m goga.pipeline run NAME --info
  [-w WORKFLOW | --no-workflow] [-s NAME]...`.
```

- "Threading chains" — replace the section body with:

```md
    goga pipeline NAME            → run (full shape)
    goga pipeline NAME -t feat/x  → switch-or-create → run (full shape)
    goga pipeline --list          → minimal shape: list
    goga pipeline --list --info   → minimal shape: list --info
    goga pipeline NAME --info     → minimal shape: run NAME --info [-w WF | --no-workflow] [-s NAME]...

    goga pipeline NAME -p N
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → the in-container run launches afm bounded to N concurrent stages

    goga pipeline NAME -w hardening -s build -s test
      → docker run … -m goga.pipeline run NAME --port PORT -w hardening -s build -s test
        → the in-container run resolves the workflow and applies the skips

Absent ⇒ no flag ⇒ auto-match / no skip / unbounded.
```

- "File manager roots (run form)" — in the never-roots sentence remove the stale engine-credential
  member (user-mounted credential FILES are already covered by "File mounts"). Remove:

```md
File mounts, named volumes, missing host paths, credential files, the afm
config overlay, and the persistent afm state directory never become roots.
```

  Add:

```md
File mounts, named volumes, missing host paths, the afm config overlay, and
the persistent afm state directory never become roots.
```

---

### Project-level documentation

**File:** `.goga/usages/cooks/docker-auth-mounts.md` — REWRITTEN in full:

```md
# Docker Auth Mounts — Mounting Your Own Agent Credentials

## Domain

Self-served mounting of AI-agent credential files (claude, codex, opencode) into a container
that runs the agent CLIs. goga launchers add no credential mounts — you mount what you need,
where you need it.

Target audience: goga users who run pipelines or builds in the goga Docker container and want
the in-container agents to use the same credentials the host user already has.

## Primary channel — home.docker.run

Add volume tokens to the `docker.run` list of the home configuration (~/.goga/config.yml). The
tokens join every `docker run` goga launches; the accepted token shape and the layering rules
live in the `home-configuration` usage of the config cell. Example:

    docker:
      run:
        - "-v ~/.claude/.credentials.json:/home/goga/.claude/.credentials.json:ro"
        - "-v ~/.codex/auth.json:/home/goga/.codex/auth.json:ro"

## Path table

Mount each credential file to the container path its CLI looks up natively — the container
layout mirrors the host layout under /home/goga/:

| agent    | host_path                                  | container_path                             |
|----------|--------------------------------------------|--------------------------------------------|
| claude   | `~/.claude/.credentials.json`              | `/home/goga/.claude/.credentials.json`     |
| codex    | `~/.codex/auth.json`                       | `/home/goga/.codex/auth.json`              |
| opencode | `~/.local/share/opencode/auth.json`        | `/home/goga/.local/share/opencode/auth.json`|

## Alternative — environment variables

When a CLI accepts an API-key variable, pass it with the launcher's `-e/--env KEY=VALUE`
option (for example `ANTHROPIC_API_KEY=...`). The entry joins the container environment
verbatim.

## Recommendations

- Mount credential files read-only (`:ro`) — the container must never modify host credentials.
- Mount only the credential file, never the whole agent directory — a directory mount leaks
  host settings and caches into the container.
- An absent credential file is not an error: the in-container agent surfaces authentication
  failure through its own error path.

## Platform caveat — macOS Keychain for claude

On macOS, web-login for the claude CLI stores the token in the macOS Keychain and
auto-deletes `~/.claude/.credentials.json`. The Keychain cannot be bind-mounted. Re-create
`~/.claude/.credentials.json` manually with the OAuth token before launching goga, or pass
`ANTHROPIC_API_KEY` via `-e/--env` instead.
```

**File:** `.goga/usages/cooks/afm.md` — one fragment replaced. Remove:

```md
3. `docker run --rm -p <port>:<port> -v <project_dir>:/workspace
   -w /workspace -v <afm_config_tmpfile>:/home/goga/.afm/config.yaml:ro
   --env-file <env_file> [-v <host_cred_path>:<container_cred_path>:ro ...] <image>
   afm run --port <port> <flow_path>`

   Credential files are bind-mounted read-only — one `-v` per credential file
   detected on the host. Detection is agent-agnostic (`resolve_credential_mounts()`:
   claude, codex, opencode) rather than a single hardcoded agent mount, so every
   present credential is mirrored into the container at its native lookup path
   under `/home/goga/`. See the `resolve-credential-mounts` and
   `docker-auth-mounts` practices.
```

Add:

```md
3. `docker run --rm -p <port>:<port> -v <project_dir>:/workspace
   -w /workspace -v <afm_config_tmpfile>:/home/goga/.afm/config.yaml:ro
   --env-file <env_file> <image> afm run --port <port> <flow_path>`

   The launcher adds no credential mounts. A user who wants credentials inside the container
   mounts them through the home configuration (`docker.run` volume tokens) or passes
   environment variables — see the `docker-auth-mounts` user guide.
```

---

## Dependency Map

Post-change import graph (changed edges marked):

```
goga/agents/wrapper ──(resolve_wrapper_path)──────────────> goga/agents            [unchanged]
goga/agents ──(resolve_wrapper_path, resolve-wrapper-path)─> goga/commands/pipeline [shrunk]
goga/agents ──(resolve_wrapper_path, resolve-wrapper-path)─> goga/build             [unchanged — the
                                                             surviving export covers every remaining
                                                             consumer need]
goga/commands/build ⇥ goga/agents                          [EDGE REMOVED]
goga/agents ⇥ goga/agents/credentials                      [EDGE REMOVED — target deleted]

goga/topics ──(ensure_topic, ensuring)────────────────────> goga/commands/pipeline  [unchanged]
goga/config, goga/config/hooks, goga/runtime, goga/docker ──> goga/commands/pipeline [unchanged]
goga/commands/pipeline ──(pipeline, pipeline-command)──────> goga/commands          [unchanged — the
                                                             click signature and the practice
                                                             filename stay stable]
goga/build, goga/config, goga/config/hooks, goga/docker, goga/runtime ──> goga/commands/build [unchanged]

goga/pipeline ──(Usages only: list-pipelines, describe-pipelines, pipeline-cli,
                 run-pipeline, describe-pipeline)──> goga/commands/pipeline  [docker runtime
                 boundary — no Types; run options now travel the post-image argv]
goga/pipeline ──> goga/pipeline/compiler, goga/pipeline/hooks, goga/pipeline/workflow,
                  goga/afm, goga/docker, goga/config, goga/history              [unchanged]
goga/pipeline/compiler ──> goga/pipeline/workflow            [unchanged]
```

All edges point strictly downward; no cycles (removals plus one intra-cell edge:
`describe_pipeline` → `apply_skip_stages` inside `goga/pipeline`).

## Verification Checklist

After each artifact (fix-in-place: defects are repaired in the artifact and the full suite is
re-run to green before approval):

- [ ] `goga lint` passes over all five touched manifests (`goga/agents`,
      `goga/pipeline/compiler`, `goga/pipeline`, `goga/commands/build`,
      `goga/commands/pipeline`) — DSL syntax, reference resolution, usage wiring.
- [ ] No `GOGA_WORKFLOW_NAME` / `GOGA_WORKFLOW_DISABLED` / `GOGA_SKIP_STAGES` mentions remain in
      the realigned usage files (`run-pipeline.md`, `pipeline-cli.md`,
      `describe-pipeline.md`, `pipeline-command.md`, `build.md`, `afm.md`,
      `docker-auth-mounts.md`) — the only allowed occurrence in the whole change-set is the
      inertness Constraint of `run_pipeline_container`.
- [ ] No `resolve_credential_mounts` / `resolve-credential-mounts` / `docker-auth-mounts`
      references remain in `goga/agents`, `goga/commands/build`, `goga/commands/pipeline`
      manifests or their usages; `goga/agents/credentials/` and
      `goga/agents/.usages/resolve-credential-mounts.md` no longer exist.
- [ ] `resolve_wrapper_path` still importable from `goga.agents` (facade check:
      `python -c "from goga.agents import resolve_wrapper_path"`).
- [ ] In-container argv threading: `pipeline_cli` parses `-w`, `--no-workflow`, repeatable `-s`
      in both run and card modes; `run_pipeline`/`describe_pipeline` receive the decision and
      skip as parameters; `AFM_DIR` is the only env read of run coordination (tests:
      `tests/pipeline/`, CLI dispatch and card/run equivalence — same flags, same composition).
- [ ] Launcher argv assembly: run form composes `-m goga.pipeline run NAME --port P [-w WF]
      [--no-workflow] [-s N]... [--parallel N]`; card form appends one `-s NAME` per entry;
      env-file carries environment layers only; stale `GOGA_*` values passed via `-e`/home.env
      are inert (no warning, no error, no effect).
- [ ] Host validation unchanged: missing `-w` file and `-w`+`--no-workflow` rejected host-side;
      unknown skip names fail in-container as the compiler's structural error.
- [ ] Workflow log line printed exactly when the workflow applies (explicit or existing
      auto-match file).
- [ ] No credential mounts in any launcher command; build/pipeline docker-run mount lists carry
      no credential entries.
- [ ] `pytest tests/ -x` green and `ruff check goga/` clean after implementation.
