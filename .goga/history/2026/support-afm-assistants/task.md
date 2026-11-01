# Support afm assistants and run agents in goga workflows

## Current State

goga authors run customization in workflow-files (`.goga/workflows/*.yml`): the
`goga/pipeline/workflow` cell parses them into `WorkflowDocument` instructions, the
`goga/pipeline/compiler` cell compiles pipelines into afm flow-files, and the
`goga/pipeline` cell coordinates runs — rewriting the whole `~/.afm/config.yaml` on
every launch (`write_afm_config`) and delivering per-stage env through generated
sh-closure wrappers (`apply_stage_env_wrappers`, with agent names resolved via
`resolve_wrapper_path` from `goga/agents`).

None of this reaches the engine's collaboration mechanism (afm v2.x):

- the workflow-file grammar has no `assistants:` catalog, no `delegation:` block, and
  no per-stage `assistants:` instruction;
- the compiler emits no `collaboration` block, no `team` list, and no stage
  `assistants` entries;
- the config write carries no helper profiles and no task limits — and because goga
  fully rewrites the engine config on every launch, even manually configured helper
  profiles are silently destroyed.

As a result, review/QA/audit attention in goga-run flows stays entirely on the human,
runs cannot delegate work to helper agents, and the operator can neither bound
delegation nor obtain the assistants dashboard mode.

## Description

Deliver afm collaboration — stage assistants and run agents — authored in the
workflow-file, through the two channels the engine offers, exactly per the ADR in
this topic directory (the decision source; the PRD is the requirements source):

1. **Authoring (workflow-file).** A top-level `assistants:` catalog — each entry
   requires `name` and carries at least one of `prompt` (its instruction) or
   `skills` (the assistant's own skills; an entry with neither is a validation
   error). `agent` (a goga agent name), `delegate` (bool, default false), and `env`
   (mapping) are optional — an omitted `agent` resolves at delivery to the
   effective global pipeline agent (the stage-agent fallback precedent). A
   top-level `delegation:` block with optional `depth` (integer ≥ 0) and
   `max_tasks` (integer ≥ 1). A per-stage `assistants:` instruction accepting three
   entry forms: a bare name referencing the catalog; a map reference that overrides
   only `gate` and `when`; a full inline declaration (`name` required, at least one
   of `prompt` or `skills`, the same optional set as a catalog entry — `agent`,
   `delegate`, `env` — plus the attachment-level `gate` and `when`) independent of
   the catalog. A map entry is a full inline declaration when
   it carries any key beyond `name`/`gate`/`when`; a map carrying only
   `name`/`gate`/`when` is a reference.
   Assistant names are globally unique across the workflow-file — the catalog and all
   inline declarations form one namespace. The name `assistant` is rejected — its
   dashboard handle `@assistant` is reserved by the engine. `when` accepts exactly
   `start`, `checkpoints`, `finish` (default `checkpoints`); `gate` is bool, absent =
   advisory.
2. **Compilation (flow-file).** Emit `collaboration: {mode: assistants}` into every
   compiled flow (the one deliberate byte-level change to collaboration-free
   workflows) plus `max_depth` when `delegation.depth` is authored. Emit the `team`
   list from catalog entries — member `id`/`title` from the authored name (dashboard
   handle `@<name>`), `profile: goga-<name>`, with `instruction` and `skills`
   materialized. Emit stage `assistants` entries — every entry in object form
   carrying `profile: goga-<name>`, the engine-required binding to the generated
   profile (this is how the compiled flow references the ids the config write
   materializes) — with defaults always materialized:
   `gate` → `mode: required|advisory`, `when: start|checkpoints|finish` →
   `trigger: one_shot|checkpoints|on_completion` (goga's `checkpoints` default must
   be written explicitly — the engine default is `one_shot`), `title`,
   `instruction` (the authored `prompt`, empty when none is authored), and `skills`
   (forward-compat: the engine ignores unknown keys today). Top-level
   key order: `prompt, root_dir, name, description, memory, collaboration, team,
   stages`.
3. **Engine-config plumbing.** The global config write gains generated profiles
   `collaboration.profiles.goga-<name>` = `{title, command, delegate}` — nothing else
   in the profile — materialized exactly for the ids the compiled flow references
   (the compiled flow is the single source of truth; the two artifacts cannot
   diverge, and no dead profiles remain for attachments removed by stage skips).
   Author `collaboration.limits.max_tasks` (materialized as 50 when `delegation:` is
   authored without the value — the engine default is 20) only when the block is
   authored. Assistant `env` follows the stage precedent: the sh-closure pattern,
   with the closure path becoming the profile's `command` (a profile carries its own
   command and does not inherit `client.command`); closures are recreated every
   launch so authored configuration survives the per-launch rewrite. Agent names
   resolve exactly like stage agents — implicitly, no user-facing profile concept:
   an assistant without an authored `agent` uses the effective global pipeline
   agent, and the profile's `command` is the resolved wrapper path (or the
   env-closure path when `env` is authored).
4. **Validation (project's two-layer pattern).** Structural checks in the workflow
   parser: entry forms, types, `when` values, unknown keys, name charset
   (`[A-Za-z0-9._-]`), duplicate names, the reserved `assistant` name, `assistants`
   forbidden inside extend-entries.
   Cross-reference checks in the compiler: unknown assistant reference, attachment on
   a script-only stage (translated body carries `script`) or a planning-only stage
   (`agents == ["planning"]`), the same assistant twice on one stage. Agent names are
   not resolved in the compiler: like stage agents, they resolve at delivery time in
   `goga/pipeline` (wrapper path / env-closure command), where a name that resolves
   to nothing fails the launch with a pre-run error naming the assistant — no extra
   existence check (per the ADR). `skip: true` plus attachments is silent — the stage
   is removed and nothing attaches. Every error names the workflow location (the
   delivery-time agent error names the assistant and its authoring site) and fails
   before launch.
5. **Tool-contributor overlay.** For stage `assistants` lists the overlay merge
   appends with deduplication by name — authored entries first, a tool entry whose
   name is already present is dropped silently. The catalog merges like `extend`
   (authored names win, tools add fresh names); `delegation` merges like `memory`
   (whole-block authored-unbeatable). The new blocks participate in
   contributor-profile rendering and activation exactly like existing blocks.
6. **Documentation.** Update `docs/features/pipelines/workflows.md` for the new
   authoring blocks.

goga never reads or writes `collaboration.enabled` or `AFM_COLLABORATION`: an
environment that disables collaboration gets engine warnings and skipped helpers, and
the run proceeds.

## Scope

**In scope:**

- Workflow-file authoring: the `assistants:` catalog (with `env`), the `delegation:`
  block, and the per-stage `assistants:` instruction with all three entry forms, plus
  full goga-side structural validation with clean pre-launch errors.
- Compilation and delivery: the always-emitted `collaboration.mode` and authored
  `max_depth`; the `team` list; stage assistant entries with materialized defaults;
  the fixed top-level key order; generated `goga-<name>` profiles and
  `limits.max_tasks` in the engine config written on every launch; assistant env
  closures via the stage wrapper precedent; implicit agent-name resolution.
- Behavior delivered by the engine contract: run agents present from run start and
  reachable by name; automatic stage attachment (loop-expanded copies carry their
  assistants; skipped stages attach nothing); gate verdicts with human waive; bounded
  delegation; resume reusing existing run agents without duplicated attachments.
- Validation split and overlay merge semantics as described above.
- Backward compatibility: collaboration-free workflows compile byte-identically to
  today, except the always-emitted mode key.
- Update of user-facing workflow authoring documentation.
- Keeping `.goga/usages/cooks/afm.md` accurate: if implementation-time verification
  of the engine assumptions contradicts the fact base, update it within the task.

**Out of scope:**

- Authoring collaboration in the pipeline-file DSL (stage bodies or header).
- Any user-facing profile concept, profile-management commands, or new CLI flags.
- Any dashboard mode other than assistants (team view, Board, human task posting,
  "Add run agent").
- Modifying or extending the afm engine itself.
- Mid-run helper orchestration initiated from goga (attach/detach during a live run).
- Runtime one-shot helper spawning by stage agents — an existing engine capability,
  unchanged by this work.
- Adjacent flow-level engine settings unrelated to collaboration (`side_agent`,
  `max_parallel`, `worktrees`, `repeat`).
- Cell/CODEMANIFEST architecture design — the next stage's work; this task names
  affected cells but does not design their contracts.

## Acceptance Criteria

- The workflow-file accepts the catalog, the delegation block, and stage attachments
  (all three entry forms); the new blocks render with contributor profiles and
  activate exactly like existing blocks.
- A catalog assistant is present from run start, idle and reachable by name for the
  whole run; on resume, existing run agents are reused rather than duplicated.
- Stage assistants attach automatically when the stage enters execution — no
  dashboard interaction; every loop-expanded copy carries them; skipped stages attach
  nothing.
- Gate semantics are delivered: a `gate: true` assistant materializes as
  `mode: required` — the stage does not finish until its verdict passes or a human
  waives; advisory attachments materialize as `mode: advisory`.
- `when` maps to `trigger` correctly with goga's `checkpoints` default written
  explicitly.
- Delegation stays bounded: `depth` reaches the flow as `max_depth`, `max_tasks`
  reaches the engine config and materializes as 50 when authored without a value;
  both are authored only when the `delegation:` block is present.
- The config write materializes `goga-<name>` profiles exactly for the ids the
  compiled flow references — `{title, command, delegate}` only; no divergence
  between flow and config is possible; the same authoring takes effect on every
  consecutive launch (the rewrite destroys nothing).
- Assistant `env` arrives through generated closures and the closure path is the
  profile's `command`.
- Each invalid authoring case fails with a pre-launch goga error naming the workflow
  location: unknown assistant reference; missing required field; wrong value type;
  invalid `when` value; duplicate assistant names; the same assistant attached twice
  to one stage; an attachment on a script-only or planning-only stage; an
  unresolvable agent name; `assistants` inside an extend-entry; an authored name
  outside `[A-Za-z0-9._-]`; the authored name `assistant` (reserved dashboard
  handle).
- A collaboration-free workflow compiles byte-identically to today except the added
  mode key; existing pipelines run unchanged.
- When collaboration is disabled in the environment, declared helpers are skipped
  with engine warnings and the run proceeds; goga does not fail the run.
- Unit tests follow the project conventions (structure mirroring, edge cases,
  parametrized boundaries); the full test suite and lint pass.

## Stack

- **Frameworks:** none new — Click CLI surface unchanged (no new commands/flags).
- **Libraries:** Python 3.10+ standard library (`dataclasses` with `kw_only=True`
  for all new models); pyyaml (existing) for workflow parsing and flow/config
  serialization (`sort_keys=False` per the project YAML convention); pytest + ruff
  as test/lint tooling.
- **Infrastructure:** none — the task lives entirely inside the repository plus the
  contract of the external engine binary.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| afm (external engine, v2.x collaboration contract) | `.goga/usages/cooks/afm.md` | existing |
| `*-as-claude.sh` wrapper convention (env-closure precedent) | `.goga/usages/cooks/agent-as-claude-wrappers.md` | existing (reference) |
| YAML serialization convention | `.goga/usages/cooks/beautiful_yaml.md` | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- **Engine assumptions to verify during implementation** (recorded in the ADR;
  update the afm cook in-task if contradicted): profile ids tolerate `goga-<name>`
  where `<name>` matches `[A-Za-z0-9._-]`; `limits.max_tasks` follows project >
  global precedence (a user's project-layer value overrides goga's global write);
  `max_depth: 0` suppresses helper creation but not team members.
- **Backward compatibility:** serialization changes must preserve existing byte-level
  output for collaboration-free workflows — the always-emitted mode key is the only
  permitted difference.
- **Cell discipline:** the workflow parser cell must stay dependency-free and the
  compiler may depend only on the workflow cell — no imports back into
  `goga/pipeline` or `goga/pipeline/hooks` (no cycles).
- **Namespace:** the `goga-` profile prefix is the intended override channel — a
  user-authored `goga-<name>` in `.afm/config.yaml` deliberately overrides goga's
  plumbing; the project-layer engine config is user territory goga never touches.
- **Strict grammar:** the engine does not reject unknown flow keys — goga's own
  validation is the only guard against silent typos in the workflow-file.
- **Vocabulary:** the DSL's `trigger` stage directive keeps its stage-launch meaning;
  assistant engagement uses `when`.
- **Forward-compat:** `skills` on attachment entries is emitted though the engine
  does not interpret it yet — it must pass validation untouched.

## Scope Estimate

Single task — no decomposition. One vertical feature through the
`workflow → compiler → hooks → pipeline` chain (~4 affected cells, ~6 new models,
moderate complexity, all design decisions pre-settled by the ADR); candidate split
points would not deliver independent value (a flow referencing profiles the config
does not carry fails engine preflight; parsing without delivery silently drops
authoring). No additional topics created.

## Existing Architecture

Affected cells and integration requirements (contract design belongs to the next
stage):

- `goga/pipeline/workflow` — leaf cell (no dependencies): owns `WorkflowDocument`,
  `WorkflowStage`, workflow parsing, and the contributor-profile zone. Gains the new
  authoring blocks and structural validation. Must remain dependency-free.
- `goga/pipeline/compiler` — depends only on `goga/pipeline/workflow`: owns
  `FlowDocument`, `FlowStage`, `compile_flow`, `serialize_flow`. Gains the
  `collaboration`/`team`/stage-`assistants` emission and cross-reference validation.
- `goga/pipeline/hooks` — owns `merge_workflow_overlay` (preserves the full workflow
  model). Gains append-with-name-dedup for stage assistants; catalog merge like
  `extend`; delegation merge like `memory`.
- `goga/pipeline` — owns `write_afm_config` (currently agent-only), the run
  coordination, and `apply_stage_env_wrappers` (the env-closure precedent to extend).
  Gains profiles/limits materialization from the compiled flow and assistant
  closures.
- `goga/agents` (facade over `goga/agents/wrapper`) — `resolve_wrapper_path`
  consumed as-is.
- `goga/afm` — untouched (subprocess launch only).

`WorkflowDocument` has three type-level consumers (compiler, hooks, pipeline) plus
`goga/build`, `goga/commands/pipeline`, and `goga/commands/build` importing other
workflow types — all must keep compiling unchanged; the CLI-facing surface does not
change. Forced design order: workflow → compiler → hooks → pipeline.

## Notes

- Input artifacts: `adr.md` (decision source) and `prd.md` (requirements source) in
  this topic directory; the original request is `todo.md`.
- Stage constraints honored: no code examples in this task; no architecture design —
  cells/CODEMANIFEST contracts are the next stage's work, so the code-example step of
  the formulation interview was deliberately skipped.
- Fixed defaults (settled in the ADR, do not revisit): `when: checkpoints`;
  `gate` absent = advisory; `max_tasks` materializes as 50; `mode: assistants`
  always emitted; profile = `{title, command, delegate}` only; instruction/title/
  mode/trigger/skills always ride in flow entries, defaults included. An omitted
  `agent` resolves to the effective global pipeline agent, and `prompt` may be
  omitted when `skills` is authored (at least one of the two is required) — both
  decided at task review, superseding the PRD's required-`agent`/`prompt` wording
  (PRD requirements 1 and 3).
- goga neither reads nor writes `collaboration.enabled` / `AFM_COLLABORATION`; the
  kill-switch is not goga's business.
