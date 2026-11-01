# Assistants and Run Agents in goga Workflows

## Problem

goga users author multi-stage AI flows (pipeline-files plus workflow-files) and run them
through the external afm engine. afm already offers a collaboration mechanism — helper
agents attached to stages, run-level agents, delegation depth controls, and a per-run
task budget — but none of it is reachable from goga:

- the workflow-file (the single authoring surface for run customization) cannot declare
  helper agents, attach them to stages, or start run-level agents;
- the compiler cannot emit the corresponding flow-file parts;
- because goga rewrites the whole afm configuration on every launch, even manually
  configured global helper definitions are silently destroyed.

As a result, review/QA/audit interactions in goga-run flows stay entirely on the human,
runs cannot delegate work to helper agents, and the operator can neither bound
delegation (depth, number of tasks) nor obtain the assistants dashboard mode.

## Users

**Primary user — the workflow author / run operator** (the same goga user in two
moments). An engineer who authors workflow-files and pipeline-files in the project,
launches runs, and follows them in the afm dashboard. They want stages to receive
competent helper attention automatically instead of doing it manually, run-level agents
to be available throughout the run, and delegation to stay bounded and predictable.
They rely on goga to fail fast on authoring mistakes (the engine does not reject
unknown keys) and expect authored configuration to survive every launch.

**Secondary actors:**

- **Helper agents** (stage assistants and run agents) — non-human participants defined
  by the user's declarations: each needs its own agent, a clear instruction, an
  explicit delegation permission, and — for stage assistants — attachment parameters.
- **Stage agents** that may spawn one-shot advisory helpers at runtime — an existing
  engine capability; the authored depth and task budget bound what they can spawn.

## Goals

1. **Delegable runs** — a workflow author can give stages automatic helper attention:
   assistants attach to the stages that need review/QA/audit without dashboard clicks,
   and run-level agents are available throughout the run, so this work no longer
   depends solely on the human.
2. **One authoring surface, reliably delivered** — everything collaboration-related is
   authored in the goga workflow-file and takes effect on every launch: goga delivers
   it correctly into the engine's configuration and flow, nothing authored is silently
   wiped, and authoring mistakes surface through goga's own validation before launch.
3. **Bounded, controlled delegation** — the author decides how far delegation may go
   (depth, per-assistant permission to spawn child tasks) and how many helper tasks a
   run may consume in total.
4. **Assistants-mode operation** — the run presents the assistants experience in the
   dashboard (helpers living under their stages), not a fixed default the author
   cannot influence.

## User Experience

### Entry point

The workflow author edits a goga workflow-file (`.goga/workflows/*.yml`) — rendered
with contributor profiles exactly as today — and declares assistants, delegation
settings, and stage attachments. No new files, no new commands. The engine-internal
"profile" concept never appears to the user; all plumbing is created implicitly by goga.

### Authoring language

A top-level **`assistants:`** catalog — each entry is a named assistant that starts
with the run and stays reachable by name for the whole run:

```yaml
assistants:
  - name: reviewer
    agent: claude          # a goga agent name; goga resolves it implicitly
    delegate: true         # optional — permission to create child tasks
    skills:                # optional — the assistant's own skills
      - code-audit
    prompt: |              # required — the assistant's instruction
      Review the stage changes and report concrete findings.
```

A top-level **`delegation:`** block bounding the run's delegation:

```yaml
delegation:
  depth: 3        # optional — maximum delegation depth (0 forbids helpers)
  max_tasks: 50   # optional — whole-run helper task budget; default 50
```

Per-stage attachments **`stages.<name>.assistants:`** — three entry forms:

```yaml
stages:
  build:
    assistants:
      - reviewer            # 1) bare name — use the catalog assistant as-is
      - name: reviewer      # 2) reference with attachment overrides
        gate: true
        when: finish
      - name: security      # 3) full inline declaration, independent of the catalog
        agent: codex
        prompt: Audit the diff.
        when: checkpoints
```

- **`gate`** (bool; absent = advisory): the assistant's verdict must be `pass` before
  the stage may finish; a human may waive the gate with a recorded reason.
- **`when`** (`start` | `checkpoints` | `finish`; default `checkpoints`): when the
  assistant engages — once at execution start / re-runs at each stage checkpoint /
  engages at stage completion.
- References may override only `gate` and `when`; the agent, prompt, skills, and
  delegation permission come from the catalog entry.

### Primary scenario

1. The author declares a catalog (and optionally delegation bounds) and attaches
   assistants to stages in the workflow-file.
2. The author launches the run exactly as today.
3. goga validates the authoring; mistakes produce a clean error naming the workflow
   location, and the run does not start.
4. The run starts: every catalog assistant is present from run start, idle and
   reachable by name; when a stage enters execution, its assistants attach
   automatically — no dashboard clicks.
5. Attached assistants work per their `when` and report verdicts; a `gate: true`
   assistant holds stage completion until its verdict passes (or a human waives).
6. Delegation stays inside the authored bounds: only `delegate: true` assistants spawn
   children, never beyond `depth`, within the whole-run `max_tasks` budget.
7. The dashboard presents the run in assistants mode: helpers under their stages,
   assistant conversations available, no team/board surfaces.

### Alternative scenarios

- Catalog-only workflow (no stage attachments): run agents present, stages unchanged.
- Stage-attachments-only workflow (no catalog): every attachment is a full inline
   declaration.
- Workflow without any collaboration authoring: runs as today, unchanged output
   except the always-present assistants mode key.
- Loop-expanded stages: every copy carries its assistants.
- Skipped stages: nothing attaches.
- New stages introduced by the workflow `extend` block may have assistants, authored
   in the stages block by the new stage's name (the established pattern).
- Run without a resolved workflow: no collaboration authoring applies.
- Collaboration disabled in the environment: declared helpers are skipped with
   warnings and the run proceeds.

### Failure behavior and recovery

- Invalid authoring (unknown assistant reference, missing `agent`/`prompt`, wrong
  types, invalid `when` value, duplicate names, attachment on a script-only or
  planning-only stage, unresolvable agent name) — a pre-launch goga error naming the
  workflow location; the user fixes the file and relaunches.
- Resuming a run reuses the existing run agents; stage retries never duplicate an
  attached assistant.

## Requirements

### Authoring

1. The workflow-file must accept a top-level `assistants:` catalog; each entry
   requires `name`, `agent`, and `prompt`, and may carry `delegate` (bool, default
   false) and `skills` (list).
2. The workflow-file must accept a top-level `delegation:` block with optional
   `depth` (integer ≥ 0) and `max_tasks` (integer ≥ 1; when the block is authored and
   the field omitted, it materializes as 50). When the block is absent, no bounds are
   authored and engine defaults apply.
3. The per-stage instruction `stages.<name>.assistants:` must accept a list where
   each entry is: a bare string referencing a catalog assistant; a map with `name`
   (reference) plus optional `gate`/`when` overrides; or a full inline map (`name`,
   `agent`, `prompt` required; `skills`, `delegate`, `gate`, `when` optional)
   independent of the catalog. A map entry that carries `agent` is a full inline
   declaration. References may override only `gate` and `when`.
4. `gate` (bool, absent = advisory): the assistant's verdict must be `pass` before the
   stage may finish; a human may waive the gate with a recorded reason.
5. `when` accepts exactly `start`, `checkpoints`, or `finish`; the default is
   `checkpoints`.
6. The new blocks must participate in contributor-profile rendering and activation
   exactly like existing workflow blocks.
7. The assistants dashboard mode is never authored; goga emits `mode: assistants`
   into every compiled flow.

### Delivery and run behaviour

8. Every catalog assistant must start with the run (before the first stage) and stay
   reachable by name for the whole run.
9. Stage assistants must attach automatically when the stage enters execution; every
   loop-expanded copy carries them; skipped stages attach nothing.
10. goga must resolve authored agent names to engine-usable commands implicitly and
    create all engine-internal plumbing for declared assistants invisibly — no
    user-facing profile concept, no duplicate authoring.
11. Delegation must stay bounded: only `delegate: true` assistants spawn children,
    never beyond the authored `depth`, and the run's total helper-task count never
    exceeds the authored `max_tasks`.
12. The dashboard must present the run in assistants mode: helpers under their
    stages, assistant conversations available, no team/board surfaces.
13. Helper status, verdicts, and findings must remain visible during the run; gate
    outcomes must be visible, with waive available to the human.
14. Resume must reuse existing run agents; stage retries must not duplicate attached
    assistants.

### Validation and failure

15. goga must reject invalid authoring before launch with a clean error naming the
    workflow location for: an unknown assistant reference; a missing required field;
    a wrong value type; an invalid `when` value; duplicate assistant names; the same
    assistant attached twice to one stage; an attachment on a non-execution
    (script-only or planning-only) stage; an unresolvable agent name.
16. A collaboration-free workflow must compile exactly as today, except the
    always-emitted mode key.
17. When collaboration is disabled in the environment, declared helpers are skipped
    with warnings and the run proceeds; goga must not fail the run for this.

## Constraints

**Engine contract (afm — an external dependency, developed separately)**

1. goga consumes afm's contract only; the solution must not rely on modifying afm.
2. Helper definitions exist only in the engine's configuration files, never in the
   flow-file — implicit plumbing must be delivered through the engine config goga
   already writes and fully owns on every launch.
3. A flow cannot enable or disable collaboration; when the environment disables it,
   declared helpers are skipped with warnings — goga must not force-enable or fail.
4. Stage assistants are valid only on execution stages — never on script-only or
   planning-only stages; the same assistant cannot be attached twice to one stage.
5. An assistant unknown to the engine stops the run at preflight — all implicit
   plumbing must be in place before launch, on every launch.
6. Dashboard-mode resolution is flow > project config > global config > default (team
   view); the flow-file is the only layer goga authors, hence the mode is emitted
   there.
7. Resume reuses existing run agents and stage retries never duplicate attachments —
   these engine guarantees must be preserved.
8. Verdict gating, depth, and the task budget are enforced by the engine; goga only
   authors the bounds.
9. The project-layer engine config (`.afm/config.yaml`) is user territory goga never
   touches; same-named entries there take precedence over goga-delivered ones.

**Existing product behaviour to preserve**

10. The workflow-file grammar stays strictly validated by goga: every new key is
    structurally checked — the engine does not reject unknown keys, so silent typos
    must never pass.
11. Backward compatibility: collaboration-free workflows compile exactly as today,
    with one deliberate exception — the always-emitted `mode: assistants` key.
12. The workflow-file remains the single authoring surface: no new files or commands
    for the base experience.
13. Users author goga agent names; wrapper paths and engine commands are never
    user-authored.
14. Per-stage instructions for extend-stages follow the established pattern: authored
    in the stages block by the new stage's name, forbidden inside extend-entries.
15. The DSL vocabulary `trigger` (`on_success` | `manual`) keeps its stage-launch
    meaning — assistant engagement uses `when`.

**Confirmed product decisions**

16. No user-facing "profile" concept — all engine plumbing is implicit.
17. Fixed defaults: `when: checkpoints`; `gate` absent = advisory; `max_tasks: 50`
    when delegation is authored; `mode: assistants` always emitted.

## Scope

### In Scope

- Workflow-file authoring: the `assistants:` catalog, the `delegation:` block, and
  the per-stage `assistants:` instruction (all three entry forms), with full
  goga-side structural validation and clean pre-launch errors.
- Compilation and delivery: run agents from catalog entries, stage assistant
  attachments, delegation bounds, and the always-emitted `mode: assistants` in the
  compiled flow; implicit engine plumbing delivered through the engine config goga
  authors at every launch.
- The resulting run experience: automatic attachment, gate verdicts with human waive,
  bounded delegation, assistants-mode dashboard presentation, resume/retry behavior
  preserved.
- Backward compatibility of collaboration-free workflows.
- Update of user-facing workflow authoring documentation for the new blocks.

### Out of Scope

- Authoring collaboration in the pipeline-file DSL (stage bodies or header) — the
  workflow-file is the single authoring surface for this change.
- Any user-facing profile concept or profile-management commands.
- Any dashboard mode other than assistants (team view, Board, human task posting,
  "Add run agent").
- Modifying or extending the afm engine itself.
- New CLI commands or flags for collaboration management.
- Mid-run helper orchestration initiated from goga (attach/detach during a live run).
- Runtime one-shot helper spawning by stage agents — an existing engine capability,
  unchanged by this work.
- Adjacent flow-level engine settings unrelated to collaboration (`side_agent`,
  `max_parallel`, `worktrees`, `repeat`).

## Success Criteria

1. **Auto-attachment** — in a run whose workflow attaches an assistant to a stage,
   the helper appears and engages when the stage enters execution, with no dashboard
   interaction; loop-expanded copies each get their helpers; skipped stages attach
   none.
2. **Run agents present** — every catalog assistant is available from run start and
   reachable by name for the whole run; on resume, existing ones are reused rather
   than duplicated.
3. **Gate works** — a stage whose gate assistant yields `needs_changes` or
   `inconclusive` does not complete; a `pass` verdict (or a human waive with reason)
   lets it complete.
4. **Delegation bounded** — child tasks never appear below non-delegating assistants;
   delegation never exceeds the authored depth; the run's total helper-task count
   never exceeds the authored budget (50 when default).
5. **Authoring survives launches** — the same workflow authoring takes effect on
   every consecutive launch of the same pipeline; goga's config rewrite destroys
   nothing.
6. **Validation upfront** — an invalid workflow (unknown assistant reference, bad
   `when` value, missing `agent`/`prompt`, attachment on a script-only stage,
   duplicate names) fails with a goga error naming the workflow location, before the
   engine launches.
7. **Assistants mode everywhere** — every compiled flow carries the assistants mode;
   the dashboard presents helpers under their stages and never the team view by
   default.
8. **Backward compatible** — a collaboration-free workflow compiles byte-identically
   to today except the added mode key, and existing pipelines run unchanged.
