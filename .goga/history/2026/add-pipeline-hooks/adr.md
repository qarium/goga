# Pipeline hooks: workflow-overlay amendment with field-level authored-wins, pre-launch and any-exit notifications

The pipeline domain opens to installed `goga_tool_*` packages through three hooks-platform
actions: `pipeline/amend_workflow` (hard — the platform's first hard action), `pipeline/run_created`
(soft), and `pipeline/run_completed` (soft). Tools act **only on the workflow layer**, contributing
an overlay with authored-wins per slot; the pipeline-file itself is never modified. Decisions were
settled in a discovery interview on 18/09/26 and take precedence over the earlier PRD wording
(the PRD must be re-aligned — see Consequences).

## Decisions

1. **Boundary.** A tool influences the workflow layer only, with the full workflow-instruction
   vocabulary, declaratively, through the same compiler validation as authored instructions. The
   pipeline-file is not subject to modification; raw compiled-flow mutation is not opened.
2. **Overlay model — authored-wins per slot.** Authored means: workflow-file content plus the
   runner's explicit skips merged before the layer.
   - `prompt` — append: authored text first, tool texts concatenated in tool enumeration order;
     when no authored prompt exists, a tool text becomes the prompt.
   - `memory` — whole-block slot: an authored block is unbeatable; when absent, tools contribute
     whole blocks with later-tool-wins; no field-level merging (method-conditional fields make
     field merges structurally unsafe).
   - `stages` — per-field: authored fields win; a tool fills unset fields; a stage with no authored
     entry may be fully defined by a tool. `skip` is an ordinary field: an authored skip
     (workflow-file or merged runner skip) is unbeatable; an unset skip is tool-fillable — including
     removing a pipeline-file stage not protected by an authored skip.
   - `extend` — tools add new entries; a name already occupied by an authored stage wins and the
     tool entry is not applied; among tools, later wins.
3. **`amend_workflow` delivery.** Per-tool staged commit (the onboarding precedent, not topics'
   per-hook): buffered declarative contributions via methods of the delivered context; a tool's
   whole contribution commits only after every hook of that tool succeeds; a failure discards the
   tool's contribution and the hard error class stops the command before launch, naming the tool
   and the action.
4. **`amend_workflow` read surface.** Pipeline identity (name, description, project/user source);
   the workflow decision (explicitly disabled / explicit name / auto-match applied / silent miss,
   plus the resolved name when applicable); the **original authored workflow** — post decision,
   post runner-skip merge, pre-layer, read-only, identical for every tool (no staged-application
   visibility: tools are mutually blind); the current work identity. Identical modifications by
   several tools: the last in enumeration order wins.
5. **`run_created` — fires immediately before the runner launch** (after compilation and prompt
   materialization). Carries: pipeline identity; workflow decision; the final effective workflow
   (authored instructions plus committed tool contributions, read-only); the final composition
   (stages in execution order, as the card shows); provenance (tools whose contributions
   committed); the current work identity (topics-shaped: branch plus topic slug/year when hosted,
   branch-only form otherwise, no status delivered then); the work's history status at the moment
   (maximal present statuses of both axes, built-in and tool); the run's runtime dir. The runner's
   skips are not a separate fact (already reflected in the composition).
6. **`run_completed` — fires on every launch-attempt return**: zero, non-zero, and spawn failures
   (126/127) alike. Same facts as `run_created` with the status recomputed at the completion
   moment, plus the outcome: the actual exit code and the runtime dir path — the diagnostics
   surface for tools. Completion is a fact, not a success claim.
7. **Card equivalence and disable semantics.** The card composes through the same layer and shows
   provenance; no run events fire in card form; the flat list and overview involve no hooks at
   all. An explicit `--no-workflow` / `GOGA_WORKFLOW_DISABLED` disables the layer entirely. A
   silent auto-match miss keeps the layer active: tools contribute onto the empty authored
   workflow, as if an empty workflow-file existed.

## Considered Options

- **Stage-presence protection** (a tool can never remove an authored stage — the literal PRD
  R2.4/SC3 reading): rejected. Protection operates at the overlay-field level; the authored skip,
  not stage presence, is what wins. Predictability is preserved by observability (card +
  provenance), not by removal of power.
- **`run_finished` firing only on a zero exit** (PRD D1/R3.2): rejected. Completion ≠ success;
  firing on any exit with the code and runtime dir gives tools a diagnostics surface for failed
  runs.
- **`run_started` after a successful launch** (PRD R3.1): rejected. `run_created` fires pre-launch;
  the name deliberately claims no launch (`started`/`launched` were rejected for that reason).
- **Per-hook commit granularity** (the topics precedent): rejected in favor of per-tool (R2.6,
  onboarding precedent).
- **`extend_workflow` / `amend_composition` naming**: rejected. `amend_workflow` continues the
  `amend_*` family and names the real power — all four sections, not only `extend`.

## Consequences

- **The PRD must be re-aligned to this ADR** so the documents do not drift: the author-guarantee
  wording (R2.4, UX guarantee, SC3), the event names and timing (R3.1, R3.2, R3.5, D1, SC5), and
  the notification context list (runner skips removed, effective workflow and runtime dir added).
- `amend_workflow` is the platform's first hard action — "every action is soft" stops being an
  invariant; catalog records remain additive and published records stay untouched.
- Tool-author documentation follows the established pattern: a pipeline-domain
  `registering-hooks` usage plus filling the negative stub `docs/features/pipelines/hooks.md`
  (Address | Error class | Fires table, context members, failure semantics); the mkdocs nav slot
  already exists.
- With no tool packages installed, every pipeline form behaves exactly as before (zero impact).

## Unresolved (later stages)

- Exact context member names, signatures, and contribution-method contracts.
- The cell that owns the pipeline hooks zone (the `topics/hooks` precedent exists; cell
  boundaries are outside discovery scope).
- Provenance display format in card and run output.
- The actual PRD text edits listed above.

---

Author: trifonovmixail
CreatedAt: 18/09/26
Description: |
  Decision record of the discovery interview for opening the pipeline domain
  to tool package integrations: the workflow-overlay amendment model, the
  three actions with their error classes, the event timeline, and the PRD
  re-alignment directive.
