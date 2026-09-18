# Opening the Pipeline Domain to Tool Package Integrations

## Problem

Third-party tool package authors cannot integrate with the pipeline domain —
the core execution domain of goga (discovery, composition with workflows,
compilation, launch, completion). The product already offers a domain
extension surface for installed tool packages — the topics, onboarding, and
statuses domains are open — but pipelines accepts no tool participation:
a tool can neither observe pipeline moments nor contribute its logic to
pipeline operation.

Blocked demand exists today: a tool cannot connect a pipeline run to the
history status model through the artifacts the run produces. Statuses can be
registered by tools, but nothing can advance them from pipeline activity.
The ambition beyond that is larger: tools should be able to personalize
workflow application per project and per user, and to build composition
add-ons on the fly.

Consequence: any integration between pipelines and a tool's logic requires
changes inside goga itself. The ecosystem cannot self-serve on the core
domain, the platform's extension promise is asymmetric, and a tool author
facing an integration task around pipelines has no defined path — every
"how do I integrate with pipelines" scenario is currently unanswerable.

## Users

### Primary: tool package author (integration developer)

A developer extending goga by writing an installed `goga_tool_*` package.
Python author; reads the goga usage docs; subscribes through the package's
`register_hooks` facade callback; already familiar with the hooks platform
from topics, onboarding, and statuses.

- **Trying to:** solve an integration task around pipelines — connect run
  artifacts to the history status model, observe pipeline moments for
  reporting or automation, personalize workflow application, or build
  composition add-ons for their users.
- **When:** while designing and iterating on the tool package; edits apply
  from the next run without reinstall.
- **What matters:** a complete, predictable contract — which pipeline
  moments exist, what each moment delivers, what a hook may change and what
  it cannot, how hook failures are treated, and how tool logic composes with
  project-authored workflow-files. No integration scenario should be left
  without a documented answer.
- **Constraints:** runs inside the goga container at the trust level of the
  installation; cannot assume goga code changes; tool identity is assigned
  by goga.

### Secondary: pipeline runner (project developer)

Uses goga in a project; runs `goga pipeline NAME`; installs tool packages
into the environment.

- **Trying to:** get the pipeline executed as expected, with installed tools
  adding value (statuses advancing, integrations firing) — and still
  understand what the tools did to the run.
- **What matters:** runs keep working with tools installed — authored
  behavior stays predictable, tool participation is observable and
  diagnosable, and a failing tool degrades the way the declared error class
  promises.

### Secondary: pipeline/workflow author (project member)

Authors pipeline-files and workflow-files in the project; often the same
person as the runner, a distinct role when composition is authored by one
member and run by others.

- **Trying to:** author the pipeline composition declaratively and have it
  mean the same thing on every machine, including machines with tools
  installed.
- **What matters:** predictability and precedence — whether and how tool
  participation changes the authored composition must be defined, not
  accidental.

## Goals

Priority order: G1 → G2 → G3. When openness and predictability conflict,
integration power wins; G3 is preserved as the residual guarantee, not as a
veto.

- **G1 — Openness.** A tool package author can connect their logic to
  pipeline operation — observe run moments and participate where the domain
  allows it — without changes inside goga, exactly as they already can in
  topics, onboarding, and statuses.
- **G2 — Contract completeness.** The space of realistic integration
  scenarios is covered definitively: artifacts → history status model,
  reporting and automation over pipeline moments, workflow
  personalization, and on-the-fly composition add-ons. A tool author
  understands from the contract how to solve their task — no scenario is
  left unanswered.
- **G3 — Trustworthy runs.** Opening the domain does not break the pipeline
  experience: for the author and runner the pipeline stays predictable,
  tool participation is observable and diagnosable, and tool failures
  degrade according to the declared semantics without corrupting runs.

## User Experience

### Established decisions

- **D1 Moment set.** One amendment point — the workflow layer delivered
  before compilation — plus two notifications: `run_created` (immediately
  before the runner launch, after compilation and prompt materialization)
  and `run_completed` (on every launch-attempt return: zero, non-zero, and
  spawn failures 126/127 alike, carrying the actual exit code and the
  runtime dir path). Completion is a fact, not a success claim.
- **D2 Layer power and precedence.** Tools contribute with the full
  workflow-instruction vocabulary; precedence is authored-wins per slot:
  `prompt` appends (authored text first, tool texts in tool enumeration
  order); `memory` is a whole-block slot (an authored block is unbeatable;
  when absent, tools contribute whole blocks with later-tool-wins); the
  `stages` block is per-field (authored fields win, a tool fills unset
  fields; `skip` is an ordinary field — an authored skip is unbeatable, an
  unset skip is tool-fillable, including removing a pipeline-file stage not
  protected by an authored skip); `extend` adds new entries (a name
  already occupied by an authored stage wins; among tools, later wins).
- **D3 Error classes.** The workflow amendment is hard: a failing tool
  stops the launch before the runner starts, with a clean error naming the
  tool and the action. Notifications are soft: a failing hook warns and
  the run is unaffected.
- **D4 Card equivalence and provenance.** The card composes through the
  same layer — it shows the tool-extended composition and names the
  contributing tools.
- **D5 Disable semantics.** An explicit workflow disable (`--no-workflow` /
  `GOGA_WORKFLOW_DISABLED`) disables the tools layer too — the raw authored
  DSL composition composes. A silent auto-match miss keeps the tools layer
  active.

### Tool package author

**Entry.** The author opens the pipeline hooks usage document — a table of
the domain's actions: the address (domain `pipeline` + action name), when
each fires, what its context carries, and what a hook may change.

**Primary flow.** In their `goga_tool_*` package they subscribe inside
`register_hooks`. They verify with `goga hooks` — their pipeline
subscriptions appear in the inspection tree. Edits apply from the next
command; no reinstall.

**Building an integration.**

- *To amend the workflow:* subscribe to the amendment action; receive the
  resolved composition facts — pipeline identity (name, description,
  project/user source), the workflow decision (explicitly disabled /
  explicit name / auto-match applied / silent miss, plus the resolved name
  when applicable), the original authored workflow (post decision, post
  runner-skip merge, pre-layer, read-only, identical for every tool), and
  the current work identity — and contribute workflow-shaped instructions
  with the full vocabulary: new stages, per-stage overrides, memory
  directives, stage skips.
- *To react to runs:* subscribe to the created/completed notifications;
  read the final effective workflow, the final composition facts,
  provenance, the current work identity, that work's history status at the
  moment, and the run's runtime dir; the completion event adds the actual
  exit code. The artifact → status integration builds here.

**Failure behavior.**

- A wrong address, an empty name, or a name collision on the same address:
  the registration is skipped with a warning naming the tool and the
  reason; the remaining registrations apply.
- A crashing amendment hook: the command stops before the runner launches,
  with a clean error naming the tool and the action (hard).
- A structurally invalid contribution (the hook returns, the contribution
  fails validation): the compiler's clean structural error surfaces before
  any launch.
- A crashing notification hook: a warning naming the tool, the action, and
  the reason; the run's outcome is unaffected (soft).
- A broken package import: the single fatal case — a clean error naming
  the package.

### Pipeline runner

Commands are unchanged. With tools installed:

- The card shows the composition that would really execute, extended by
  tools, with the contributors named (provenance). The run start names the
  contributing tools the same way.
- **No tools installed:** nothing changes — no registration, no layer, no
  output differences.
- **A tool fails while extending:** the launch stops before the runner with
  a clean error naming the tool; nothing heavy ever starts; retry after
  fixing or removing the tool.
- **A tool fails in a notification:** a warning in the log; the run's
  outcome and exit code are unaffected.
- **Explicit `--no-workflow`:** the raw authored DSL composition — the
  tools layer is off too.
- **Missing pipeline / structural DSL error:** today's clean errors; no
  events fire (the moment never happened — the command stops before any
  launch attempt).
- **The runner exits non-zero (or fails to spawn, 126/127):** the run
  reports failure as today; the completion event fires with the actual
  exit code and the runtime dir path — the diagnostics surface for tools.

### Pipeline/workflow author

**Guarantee.** Authored intent wins per slot: pipeline-file content,
workflow-file instructions, and the runner's explicit stage skips are
never overridden by tool contributions. The authored skip — not stage
presence — is what wins: a pipeline-file stage not protected by an
authored skip may be removed by a tool filling the unset skip field.
Machines without tools compose identically to machines with tools for
everything the author defined.

**Observability.** The card's provenance shows which tools extended the
composition; `goga hooks` shows what is installed and subscribed.

### States and feedback

- The card and run output remain the single source of composition truth;
  provenance names the contributing tools.
- Warnings and errors always name the tool, the action, and the reason.
- Registration is never cached — tool edits apply on the next command.
- Run notifications fire only in the run form; the card involves the
  amendment layer but never fires run events; the flat list and overview
  involve no hooks at all.

## Requirements

### Domain actions

- **R1.1** The pipeline domain must open exactly three actions on the hooks
  platform: the workflow amendment `amend_workflow` and the two run
  notifications `run_created` and `run_completed`.
- **R1.2** The amendment action must be declared hard: the first failing
  tool stops the command with a clean error before any launch, naming the
  tool and the action. The two notifications must be declared soft: a
  failing hook warns and the run is unaffected.
- **R1.3** Subscriptions follow the platform envelope —
  `subscribe("pipeline", action, name, hook)`; a wrong address, an empty
  name, or a name collision is skipped with a warning naming the tool and
  the reason; the remaining registrations apply.

### Workflow amendment

- **R2.1** The amendment layer must be delivered at composition time —
  after the workflow decision resolves and the runner's explicit skips
  merge, before compilation — in both the card form and the run form.
- **R2.2** The delivered context must carry: the pipeline identity (name,
  description, project/user source), the workflow decision (explicitly
  disabled / explicit name / auto-match applied / silent miss, plus the
  resolved name when applicable), the original authored workflow — post
  decision, post runner-skip merge, pre-layer, read-only, identical for
  every tool (no staged-application visibility: tools are mutually blind)
  — and the current work identity. The runner's skips are not a separate
  fact: they are already merged into the authored workflow.
- **R2.3** A hook may contribute instructions from the full
  workflow-instruction vocabulary: new stages, per-stage overrides, memory
  directives, and stage skips.
- **R2.4** Authored-wins per slot: pipeline-file content, workflow-file
  instructions, and the runner's explicit skips must never be overridden by
  a tool; a tool instruction applies only where no authored instruction
  exists. `skip` is an ordinary field: an authored skip (workflow-file or
  merged runner skip) is unbeatable; an unset skip is tool-fillable —
  including removing a pipeline-file stage not protected by an authored
  skip.
- **R2.5** Tools contribute in enumeration order; within the un-authored
  space a later tool's instruction overwrites an earlier tool's
  instruction for the same slot; identical modifications by several tools —
  the last in enumeration order wins; `prompt` appends (authored text
  first, tool texts concatenated in enumeration order).
- **R2.6** A tool's whole contribution must commit only after every hook of
  that tool for the action succeeds; a failing tool's contribution is
  discarded and the hard error class stops the command naming the tool and
  the action.
- **R2.7** A structurally invalid contribution must surface as the
  compiler's clean structural error before any launch — tool contributions
  pass through the same validation as authored ones.
- **R2.8** The composed output must name the tools whose contributions
  committed (provenance), in the card and at the run start.

### Run notifications

- **R3.1** `run_created` must fire immediately before the runner launch —
  after compilation and prompt materialization — carrying the pipeline
  identity, the workflow decision, the final effective workflow (authored
  instructions plus committed tool contributions, read-only), the final
  composition facts (stage list in execution order), provenance, the
  current work identity, that work's history status at the start moment,
  and the run's runtime dir. The runner's skips are not a separate fact
  (already reflected in the composition).
- **R3.2** `run_completed` must fire on every launch-attempt return —
  zero, non-zero, and spawn failures (126/127) alike — carrying the same
  facts as `run_created` with the status recomputed at the completion
  moment, plus the outcome: the actual exit code and the runtime dir path.
  Completion is a fact, not a success claim.
- **R3.3** When the current branch hosts no topic, the work identity
  degrades to its branch-only form and no history status is delivered; the
  tool decides whether to act.
- **R3.4** A failing notification hook must warn naming the tool, the
  action, and the reason; the run's own outcome and exit code are
  unaffected.
- **R3.5** No event may fire for a moment that never happened: a missing
  pipeline, a workflow parse error, or a structural composition error stops
  the command before any launch attempt — `run_created` never fires. A
  launch attempt that returns — including a spawn failure (126/127) — is a
  real completion moment: `run_completed` fires with the actual exit code.

### Card equivalence

- **R4.1** The card must compose through the same amendment layer with the
  same precedence: what the card shows with given flags is exactly what a
  run with the same flags executes.
- **R4.2** The card must display the provenance of the composition — which
  tools contributed.
- **R4.3** The flat list and overview forms must not involve hooks: no
  composition, no registration, no layer.

### Disable semantics

- **R5.1** An explicit workflow disable (`--no-workflow` /
  `GOGA_WORKFLOW_DISABLED`) must disable the amendment layer entirely —
  the raw authored DSL composition composes.
- **R5.2** A silent auto-match miss must keep the amendment layer active:
  tools contribute onto the empty authored workflow.

### Diagnostics and iteration

- **R6.1** `goga hooks` must show the pipeline subscriptions of the
  installed tool packages.
- **R6.2** Registration is never cached: package edits apply from the next
  command without reinstall.
- **R6.3** A broken tool-package import must surface as a clean fatal error
  naming the package — the only fatal case of the platform.
- **R6.4** Every warning and error of the domain must name the tool, the
  action, and the reason.

### Zero impact

- **R7.1** With no tool packages installed, every pipeline form must behave
  exactly as before: same output, same errors, same exit codes, no
  registration activity.

### Consistency

- **R8.1** Facts delivered to hooks must be built from the operation's own
  data — no git reads at a checkpoint.
- **R8.2** For the same flags, card facts and run facts must agree —
  workflow decision, skips, provenance.

## Constraints

- **C1 Execution boundary.** Stage execution belongs to the external afm
  binary; goga observes only its own moments (composition, launch, exit
  code). The product cannot open stage-level events — the extension
  surface is bounded by goga-owned moments.
- **C2 Runtime boundary.** Pipeline composition and hook delivery run
  inside the goga Docker container; tool packages must be installed in that
  environment. The host-side launcher only translates input; no host-side
  pipeline moments exist.
- **C3 Declarative extension.** Tool contributions are workflow-shaped
  declarative instructions that pass through the same compilation
  validation as authored ones; the product does not open raw
  compiled-flow mutation.
- **C4 Catalog additivity.** The action catalog is extended additively;
  published records are never rewritten — the pipeline actions must not
  alter any existing action or domain record.
- **C5 Platform delivery.** Platform delivery rules hold: delivery is never
  filtered by tool eligibility; tools run at the trust level of their
  installation (no isolation, no sandbox); one registry per run; hooks
  receive values only for parameters declared by the fixed offered names;
  per-tool isolated self contexts; a broken package import is the only
  fatal case.
- **C6 Authored intent.** Authored intent is inviolable: pipeline-file
  content, workflow-file instructions, and the runner's explicit skips are
  never overridden by tool contributions.
- **C7 Backward compatibility.** With no tool packages installed, every
  existing pipeline form must behave exactly as before — output, errors,
  and exit codes included; commands that reach no checkpoint never call
  `register_hooks`.
- **C8 No git reads at checkpoints.** Facts delivered at a checkpoint are
  built from the operation's own data; no git reads at a checkpoint.
- **C9 Documentation surface.** The contract reaches tool authors through
  the repo's usage documentation: every action's moments, context members,
  and failure semantics must be documented for tool package authors — the
  integration task must be answerable from the docs.

## Scope

### In Scope

- The three pipeline domain actions on the hooks platform: the workflow
  amendment `amend_workflow` (hard — the platform's first hard action) and
  the `run_created`/`run_completed` notifications (soft), with their
  catalog records.
- The workflow amendment layer: delivery at composition time in the card
  and run forms, the delivered facts (pipeline identity, workflow
  decision, the original authored workflow post runner-skip merge, current
  work identity), the full workflow-instruction vocabulary, authored-wins
  per-slot precedence, tool composition in enumeration order, per-tool
  staged commit, validation through the same compilation machine.
- The two run notifications with the final effective workflow, final
  composition facts, provenance, the current work identity, its history
  status at the event moment, and the runtime dir; `run_completed` fires
  on every launch-attempt return with the actual exit code.
- Card equivalence: the card composes through the layer and displays
  provenance; the run start names contributing tools.
- Disable semantics: explicit workflow disable disables the layer; a silent
  auto-match miss keeps it active.
- Diagnostics: `goga hooks` inspection covers pipeline subscriptions;
  registration never cached.
- Zero-impact guarantee: toolless environments behave exactly as before.
- Tool-author documentation of the new contract (usage docs: actions,
  moments, context members, failure semantics).

### Out of Scope

- Any consumer of the new surface: bundled, built-in, or reference
  `goga_tool_*` packages — including the artifacts → statuses integration
  (third-party territory).
- Stage-level events during afm execution and any change to afm itself
  (execution boundary).
- Raw compiled-flow mutation (the imperative post-compile surface — a
  rejected alternative).
- Host-side launcher moments (the `-t/--topic` switch, the `--todo`
  editor, the docker shape) and new host CLI flags (including a separate
  layer switch — `--no-workflow` covers disabling).
- Changes to workflow-file syntax or parser semantics (tools reuse the
  existing vocabulary; no new instruction kinds).
- Behavior of other hook domains (topics, statuses, onboarding).
- Reporting, analytics, or telemetry products built on the events.
- Onboarding-session integration for pipeline tools.

## Success Criteria

- **SC1** A third-party `goga_tool_*` package, with no goga code change,
  can subscribe to all three pipeline actions; `goga hooks` shows its
  pipeline subscriptions.
- **SC2** With such a tool installed, its composition contribution is
  reflected identically in the card and in the executed run for the same
  flags, and the card names the contributing tool (provenance).
- **SC3** Authored intent survives tool participation: workflow-file
  instructions and the runner's explicit skips are never overridden
  (authored-wins per slot — an authored skip is unbeatable); a machine
  without the tool composes the same authored result. A pipeline-file
  stage not protected by an authored skip may be removed by a tool — the
  authored skip, not stage presence, is the protection.
- **SC4** A failing amendment hook stops the launch before the runner with
  a clean error naming the tool and the action; a failing notification hook
  warns naming tool, action, and reason, and the run's exit code is
  unaffected.
- **SC5** `run_created` fires immediately before the runner launch;
  `run_completed` fires on every launch-attempt return — zero, non-zero,
  and spawn failures alike — and carries the current work's identity, its
  history status at the moment, the actual exit code, and the runtime dir
  path.
- **SC6** With no tool packages installed, every pipeline form behaves
  exactly as before — same output, same errors, same exit codes.
- **SC7** An explicit workflow disable composes the raw authored DSL (the
  layer is off); a silent auto-match miss keeps the layer active.
- **SC8** The tool-author documentation answers each integration scenario
  named in the problem — artifact → status integration on run completion,
  run reporting and automation, workflow personalization, on-the-fly
  composition add-ons — from moments, context members, and failure
  semantics alone.
- **SC9** Tool package edits apply from the next command without
  reinstall.
