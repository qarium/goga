# Open the pipeline domain to tool package integrations (pipeline hooks)

## Current State

The hooks platform (`goga/hooks` facade over catalog / dispatch / registry / tools)
is domain-agnostic and production-ready, but the action catalog carries only the
statuses, onboarding, and topics domains — every record is soft. The pipeline
domain runs without any hooks: `goga/pipeline` coordinates discovery → workflow
resolution (`resolve_workflow`) → runner-skip merge (`apply_skip_stages`) →
compilation (`compile_flow`) → prompt materialization → launch (`run_flow`), and
the card (`describe_pipeline`) shares the same workflow-resolution rule set. An
installed `goga_tool_*` package has no way to observe pipeline moments or
contribute to pipeline operation: every pipeline integration today requires
changes inside goga itself. `docs/features/pipelines/hooks.md` is a negative
stub stating that the pipelines domain exposes no hook actions.

The decision record (ADR, 18/09/26 — same topic directory) settles the design:
three actions (`pipeline/amend_workflow` hard — the platform's first hard
action; `pipeline/run_created` soft; `pipeline/run_completed` soft), the
authored-wins-per-slot workflow overlay, per-tool staged commit, and the event
timeline. The PRD has been re-aligned to the ADR (this topic directory) — the
documents are consistent; the task implements them.

## Description

Open the pipeline domain to installed `goga_tool_*` packages through three
hooks-platform actions, implementing the ADR decisions:

1. **Action catalog** — three additive records in `goga/hooks/catalog`:
   `pipeline/amend_workflow` (hard — the first hard action in the platform),
   `pipeline/run_created` (soft), `pipeline/run_completed` (soft). Published
   records stay untouched. Diagnostics ride the platform: `goga hooks` shows
   pipeline subscriptions (catalog-driven, no command change), registration
   is never cached, and every warning and error of the delivery names the
   tool, the action, and the reason.
2. **Pipeline hooks zone** — a dedicated zone of the pipeline domain for the
   hooks surface (precedent: `goga/topics/hooks`): the fact models (pipeline
   identity with name, description, project/user source; the workflow decision
   with its resolved name; the read-only original authored workflow — post
   decision, post runner-skip merge, identical for every tool; the topics-shaped
   work identity with its branch-only degradation; the work's history status as
   maximal present statuses of both axes), the read-and-contribute context of
   `amend_workflow` with per-tool staged commit, the two notification contexts,
   and the checkpoint facade consumed by the pipeline flows. Exact cell boundary
   and member contracts are design-stage decisions.
3. **Workflow overlay layer** — authored-wins per slot, applied after the
   runner-skip merge and before compilation, in both the run form and the card
   form: `prompt` appends (authored first, tool texts in enumeration order);
   `memory` is a whole-block slot (authored unbeatable; otherwise
   later-tool-wins); `stages` is per-field (authored fields win, tools fill
   unset fields; `skip` is an ordinary field — authored skip unbeatable, unset
   skip tool-fillable, including removing an unprotected pipeline-file stage);
   `extend` adds entries (authored names win; among tools later wins). Tool
   contributions are declarative `WorkflowDocument`-shaped instructions passing
   the same compilation validation as authored ones. Provenance: the tools whose
   contributions committed.
4. **Run integration** — `run_pipeline`: deliver the amendment before
   compilation; emit `run_created` immediately before the runner launch (after
   compilation and prompt materialization) with the pipeline identity, the
   workflow decision, the final effective workflow, final composition,
   provenance, work identity, history status, and runtime dir; emit
   `run_completed` on every launch-attempt return — zero, non-zero, and spawn
   failures (126/127) — with the same facts recomputed at the completion
   moment plus the actual exit code and runtime dir path.
5. **Card integration** — `describe_pipeline` composes through the same layer
   with the same precedence (card/run equivalence for the same flags) and
   displays provenance; the flat list and overview forms involve no hooks; an
   explicit workflow disable disables the layer; a silent auto-match miss keeps
   it active. No run events fire in card form.
6. **Tool-author documentation** — fill the negative stub
   `docs/features/pipelines/hooks.md` (address | error class | fires table,
   context members, failure semantics) and add the pipeline-domain
   registering-hooks usage for tool package authors following the established
   pattern; keep mkdocs navigation and traceability in sync.
7. **Tests** — unit coverage per project conventions for every new public
   surface, the overlay merge semantics (per-slot precedence, enumeration
   order, per-tool commit/discard), the event timeline (pre-launch creation,
   any-exit completion with code and runtime dir), card/run equivalence, and
   the zero-impact guarantee.

## Scope

**In scope:**
- The three pipeline domain actions on the hooks platform with their catalog
  records and error classes.
- The workflow amendment layer: delivery at composition time in the card and
  run forms; the delivered read surface; the full workflow-instruction
  vocabulary; authored-wins per-slot precedence; tool composition in
  enumeration order; per-tool staged commit; validation through the same
  compilation machine; provenance.
- The two run notifications with the pipeline identity, the workflow
  decision, the final effective workflow, final composition, provenance,
  work identity, history status, and runtime dir; `run_completed` fires on
  every launch-attempt return with the actual exit code.
- Card equivalence with provenance display; disable semantics; silent-miss
  behavior.
- Diagnostics: `goga hooks` covers pipeline subscriptions; registration never
  cached; every warning and error names the tool, the action, and the reason.
- Tool-author documentation (docs page, registering-hooks usage, mkdocs sync).
- Tests and the zero-impact guarantee.

**Out of scope:**
- Any consumer of the new surface: bundled, built-in, or reference
  `goga_tool_*` packages — including the artifacts → statuses integration
  (third-party territory).
- Stage-level events during afm execution and any change to afm itself
  (execution boundary).
- Raw compiled-flow mutation (rejected alternative).
- Host-side launcher moments and new host CLI flags (including a separate
  layer switch — `--no-workflow` covers disabling).
- Changes to workflow-file syntax or parser semantics (tools reuse the
  existing vocabulary; no new instruction kinds).
- Behavior of other hook domains (topics, statuses, onboarding).
- Reporting, analytics, or telemetry products built on the events.
- Onboarding-session integration for pipeline tools.

## Acceptance Criteria

- **AC1** A third-party `goga_tool_*` package, with no goga code change, can
  subscribe to all three pipeline actions; `goga hooks` shows its pipeline
  subscriptions.
- **AC2** With such a tool installed, its composition contribution is
  reflected identically in the card and in the executed run for the same
  flags, and the card names the contributing tool (provenance).
- **AC3** Authored intent survives tool participation per slot: workflow-file
  instructions and the runner's explicit skips are never overridden; an
  authored skip is unbeatable; an unset skip is tool-fillable — including
  removing a pipeline-file stage not protected by an authored skip (the
  authored skip, not stage presence, is the protection).
- **AC4** A failing amendment tool stops the launch before the runner with a
  clean error naming the tool and the action, and the tool's whole
  contribution is discarded; a failing notification hook warns naming tool,
  action, and reason, and the run's exit code is unaffected.
- **AC5** `run_created` fires immediately before the runner launch;
  `run_completed` fires on every launch-attempt return — zero, non-zero, and
  spawn failures alike — carrying the work identity, history status at the
  moment, actual exit code, and runtime dir path. A missing pipeline or a
  structural composition error fires nothing.
- **AC6** With no tool packages installed, every pipeline form behaves exactly
  as before — same output, same errors, same exit codes.
- **AC7** An explicit workflow disable composes the raw authored DSL (the
  layer is off); a silent auto-match miss keeps the layer active.
- **AC8** The tool-author documentation answers each integration scenario
  named in the problem — artifact → status integration on run completion, run
  reporting and automation, workflow personalization, on-the-fly composition
  add-ons — from moments, context members, and failure semantics alone.
- **AC9** Tool package edits apply from the next command without reinstall.

## Stack

- **Frameworks:** none new — Python 3.10+ on the existing codebase; stdlib
  `dataclasses` (kw_only=True), `enum`, `pathlib`, `logging` (structured, per
  project conventions); in-container argparse surface unchanged except card
  output gaining provenance.
- **Libraries:** PyYAML (existing, unchanged); pytest, ruff, pytest-cov
  (existing test toolchain per conventions).
- **Infrastructure:** the existing hooks platform (internal — registry,
  emission, per-tool staged delivery primitives, action catalog); mkdocs
  (existing documentation infrastructure).

Internal platform links consumed through Imports (all existing):
`goga/hooks` (facade: `HookRegistry`, `emit_hook_event`, `wrap_context`,
`build_hook_arguments`, `declared_actions`), `goga/pipeline/workflow`
(`WorkflowDocument` instruction models), `goga/history`
(`resolve_current_branch_name`, `resolve_topic_dir`), and
`goga/history/statuses` (`maximal_present`).

## External Dependencies

No new external components — the task builds entirely on the existing hooks
platform and stack; existing cooks and cell usages cover everything consumed.

| Component | Usage file | Status |
|-----------|------------|--------|
| (none) | — | no creation or update required |

## Risks and Constraints

- `amend_workflow` is the platform's **first hard action**: the dispatch and
  error paths must stop the command cleanly (naming the tool and the action)
  while catalog additivity and all published records stay untouched.
- The per-slot overlay merge is the most intricate logic (per-field
  authored-wins, skip as an ordinary field, whole-block memory, prompt append
  ordering, later-tool-wins) — it must be exactly the ADR semantics and is the
  priority target of unit tests.
- Card/run equivalence (R4.1, R8.2) — both forms must go through the same
  layer with the same precedence; two divergent code paths are the main drift
  risk.
- `run_completed` must fire on every return path, including spawn failures
  (126/127) — error-path coverage is mandatory in tests.
- Zero-impact guarantee: with no tool packages installed, output, errors, and
  exit codes of every pipeline form are byte-identical to today.
- No git reads at a checkpoint: every delivered fact is built from the
  operation's own data (branch/topic resolution happens in the operation, not
  inside hook delivery).
- Tools are mutually blind: the `amend_workflow` read surface delivers the
  original authored workflow to every tool — no staged-application state.
- Execution/runtime boundaries (C1–C3): stage execution belongs to afm; the
  layer runs in-container; contributions stay declarative through the same
  compilation validation.
- Provenance display format is not fixed by the ADR — a design-stage decision
  recorded as open.

## Scope Estimate

Single task, medium-large scale. The parts are tightly coupled — the overlay
layer is consumed by both the card and the run, the events carry the layer's
output, and the documentation describes the same contract — so decomposition
would not yield independently valuable deliverables. Internal decomposition
(catalog records, hooks zone, layer, run/card integration, docs, tests) is a
design/plan-stage concern.

## Existing Architecture

Affected cells and their link connections:

- `goga/hooks/catalog` — three additive records (`pipeline/amend_workflow`
  hard; `pipeline/run_created`, `pipeline/run_completed` soft). Data-only
  change; no cell's contract changes.
- **Pipeline hooks zone** (new; precedent `goga/topics/hooks`) — owns the
  fact models, the `amend_workflow` read-and-contribute context with per-tool
  staged commit (onboarding precedent, per `per-tool-delivery`), the two
  notification contexts, and the checkpoint facade. Links: imports from
  `goga/hooks` (platform facade), `goga/pipeline/workflow` (instruction
  models), `goga/history` (branch and topic-dir resolution),
  `goga/history/statuses` (status computation). The exact boundary and member
  contracts are design-stage decisions (ADR unresolved item).
- `goga/pipeline` — `run_pipeline` gains the amendment delivery between the
  skip merge and `compile_flow`, `run_created` immediately before `run_flow`,
  and `run_completed` on its return (every exit code); `describe_pipeline`
  composes through the same layer and reports provenance in the card output.
  Imports the pipeline hooks zone facade.
- `goga/pipeline/workflow`, `goga/pipeline/compiler` — contracts unchanged;
  the layer reuses the declarative vocabulary and the same validation
  machine.
- `docs/features/pipelines/hooks.md` (fill the stub), the tool-author
  registering-hooks usage of the pipeline domain, `mkdocs.yml` navigation —
  the nav slot already exists.

Cross-import rule respected: the hooks zone imports from the platform and the
sibling leaf cells only (never from `goga/pipeline` itself — the parent
imports the zone, not the reverse).

## Notes

- Decision source: the ADR in this topic directory. Where the earlier PRD
  wording differed (stage-presence protection, `run_started`/`run_finished`
  timing, notification context), the ADR wins — and the PRD has already been
  re-aligned to the ADR during task formulation (established-decision,
  guarantee, R1–R3, scope, and success-criteria sections updated), so the
  document history is consistent before this task's release.
- No code examples are included in this task (stage constraint). Exact context
  member names, signatures, contribution-method contracts, the hooks-zone cell
  boundary, and the provenance display format remain design-stage decisions.
- No new external dependencies; `.goga/usages/cooks/` is untouched. The
  practices consumed live at cell level: `declaring-actions`,
  `per-tool-delivery`, `registering-hooks` (`goga/hooks/.usages`), the
  `goga/topics/hooks` precedent, and project conventions
  (`.goga/usages/conventions.md`).

---

Author: trifonovmixail
CreatedAt: 18/09/26
