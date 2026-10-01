# Topics hooks — seven platform actions for the topics lifecycle

## Current State

- The hooks platform is complete and closed for this task: the `goga/hooks` facade (`HookRegistry`, `emit_hook_event`, `wrap_context`, `build_hook_arguments`, `declared_actions`, `enumerate_tool_packages`) over four subcells — catalog, dispatch, registry, tools. The catalog `goga/hooks/catalog` holds the actions of other domains (onboarding, history/statuses); the `goga hooks` command inspects them.
- The topics domain (`goga/topics`) implements the full lifecycle — creation (quarantined no-switch, switch, publication paths), the ensure orchestration, switching, todo entry, deletion — but emits no hook events. `docs/features/topics/hooks.md` is a stub stating that the topics domain exposes no hook actions.
- Two public emission mechanisms exist: the plain `emit_hook_event` (fire-and-forget; the statuses precedent) and the staged per-tool delivery over the public primitives (documented in `goga/hooks/.usages/per-tool-delivery.md`; the onboarding precedent).
- The domain discards values the hooks facts need: the creation plant returns a commit hash the callers ignore today; the final commit message and the resolved year are not threaded through the switching paths.

## Description

Open the topics lifecycle to installed tool packages through seven soft hook actions, per the accepted ADR at `.goga/history/2026/add-topics-hooks/adr.md` (the authoritative decision record for this task):

- Five notification actions — `topics/topic_created`, `topics/topic_published`, `topics/topic_switched`, `topics/topic_todo_entered`, `topics/topic_deleted` — emitted after the success of their moment via the plain platform emission.
- Two amendment actions — `topics/amend_creation`, `topics/amend_todo_entry` — delivered through the staged per-tool delivery pattern with per-hook buffers: a hook's buffered amendment commits only when its call returns without raising; a raising or empty/whitespace-only amendment is discarded with a platform-form warning; the enumeration continues in the platform order. The domain fixes only the final drafts into the artifacts and reports them as the final facts of the corresponding notifications.
- Topic identity in every context: slug + home path + branch as entered (branch-only in the marginal manual-switch corner); the home path `.goga/history/<year>/<topic>` is derived from slug and year without repository reads.
- Emission lives in the topics domain routines; pipeline topic resolution inherits the events through `ensure_topic`. `topic_created` is deferred until push success on the publication path; deletion emits per target inside the removal loop. Contexts are built from the operation's own data — the values discarded today (plant commit hash, final commit message, resolved year) are threaded through; no new git reads are introduced for events.
- The task completes with its documentation surface — the topics hooks reference replacing the stub and the synchronized action lists — and with unit tests per the project conventions covering every emission point and amendment semantic.

## Scope

**In scope:**

- Seven additive `error_class=soft` records in `goga/hooks/catalog`, never rewritten
- Notification emissions at the ADR moments: the four creation paths (exactly once per successful creation), publication (deferred until push success), switch (with the switch outcome kind: local-checkout / created-from-remote / already-on-branch), todo entry, per-target deletion inside the removal loop
- The amendment chain for both amendment actions: one shared draft holder per action, a read-only draft view with exactly one amendment operation replacing the full content, per-hook buffers, empty-amendment rejection at commit, platform-form warnings, hook-granular independence within a tool
- Context models per the ADR semantics: identity vocabulary; path facts; commit message + commit hash iff the path builds a commit; final todo; switch outcome kind; removal composition; identity-only degenerate case of `amend_creation` is valid; no prior todo text; no deleted-commit hash
- Threading of currently discarded values (commit hash from the plant, final commit message, resolved year) through the creation, publication, and switching paths
- Marginal corners per the ADR: `ensure --todo` on a branch hosting no topic fires `amend_todo_entry` + `topic_todo_entered` with derived identity and no `topic_created`; `switch --todo` onto a topic-less branch keeps its pre-mutation error and emits nothing
- Documentation: replace the stub `docs/features/topics/hooks.md` with the topics hooks reference (firing moment, error class, facts/drafts per action); synchronize the action lists in `docs/features/hooks/index.md`, `docs/features/hooks/hooks.md`, `docs/features/tools/hooks.md`
- Tests per the project conventions: unit coverage of every emission point and amendment semantic; CLI tested by direct handler calls; mocks only at the git/editor boundaries

**Out of scope:**

- Any change to the hooks platform core: registration, run registry, error classes, dispatch, the `goga hooks` command — all reused as-is
- New CLI commands or flags; changes to `goga/commands/topics` and `goga/commands/pipeline` (emission lives in the domain; the pipeline flow inherits the events through `ensure_topic` without caller changes)
- Behavior changes of the existing topics operations beyond threading the values — result lines, error surface, and mutation order stay as today
- Design-stage open questions from the ADR: sharing one `HookRegistry` within a command, exact member names and signatures of context views / drafts / amendment operations, exact warning reason wording, the concrete shape of the home-path fact
- ADR-rejected options: prior todo text in the todo contexts; `topic_created` for the `ensure --todo` directory creation; the deleted-commit hash in the deletion context; amendment delivery via the plain emission

## Acceptance Criteria

- `goga/hooks/catalog` declares exactly seven new topics actions, all `error_class=soft`, added additively; the existing actions are untouched
- Each notification fires exactly at its ADR moment: `topic_created` once per successful creation on each of the four paths; deferred until push success on the publication path (a rolled-back publication emits nothing); `topic_deleted` per fully removed target even before a later failure; `switch --todo` onto a topic-less branch emits nothing
- The marginal corners hold: `ensure --todo` on a branch hosting no topic fires `amend_todo_entry` + `topic_todo_entered` with derived identity (slug normalized from the branch name, current year → home path) and emits no `topic_created`; a manual switch onto a branch hosting no topic emits `topic_switched` with branch-only identity
- Amendment semantics hold: a raising hook's amendment is not applied; an empty or whitespace-only amendment is rejected at commit; hooks of one tool are independent; warnings follow the platform form `hook <name> of tool <tool> failed on topics.<action>: <reason>`; the enumeration continues in the platform order
- The final amended drafts reach the artifacts (amended commit message into git, amended text into todo.md) and are reported as the final facts of the corresponding notifications
- No new git reads for events: contexts are built from operation data — the plant commit hash, the final commit message, and the resolved year are threaded through
- `goga pipeline <name> -t` receives the same events as the topics CLI paths — emission lives in the domain routines, not in the CLI cell
- `goga hooks` shows the seven topics actions in its tool → domain → action presentation without any change to the command
- The four documentation files are synchronized: the topics hooks reference replaces the stub; the action lists include the topics domain
- `pytest tests/ -x` passes; `ruff check` over the touched sources passes

## Stack

- **Frameworks:** none beyond the existing — the goga hooks platform facade (`goga/hooks`) consumed as-is
- **Libraries:** Python 3.10+ stdlib (dataclasses `kw_only=True`, logging); click (existing, unchanged CLI surface)
- **Infrastructure:** none — no databases, brokers, or services

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| (none new) | — | no new external components; `pyproject.toml` unchanged |

Practices the task relies on: `.goga/usages/conventions.md` (mandatory base), `.goga/usages/cooks/click.md` (existing, unchanged), `goga/hooks/.usages/declaring-actions.md` and `goga/hooks/.usages/per-tool-delivery.md` (cell-level practices of `goga/hooks`, to be connected via Imports at the design stage).

## Risks and Constraints

- Per-hook atomicity is reachable only through the staged delivery pattern — the plain emission cannot provide it; falling back to `emit_hook_event` for amendments breaks the published atomicity contract (a landed amendment before a raise would survive)
- The amendment chain adds hook-driven moments inside the creation/ensure flows — a registered tool package that raises must not break the command (soft class), and the enumeration order must remain the platform's
- Threading the values changes internal call shapes of the domain routines — the external behavior, result lines, and error surface must stay identical
- Contexts must not introduce repository reads: any fact requiring a git lookup is a defect
- The marginal corners (branch-only identity, `ensure --todo` on a topic-less branch) are easy to miss — they are explicit acceptance criteria
- Documentation drift risk: four files must present identical action sets

## Scope Estimate

Single task. One cohesive domain feature: one domain (topics), one additive platform touch (catalog records), one documentation surface. All parts share the identity vocabulary and the amendment mechanics feeding the notifications' final facts — a split would produce fragments without independent value and would duplicate context. Moderately large, but homogeneous in domain and stack.

## Existing Architecture

- **`goga/hooks/catalog`** — additive edit: seven topics action records
- **`goga/topics`** — the emitting domain: emission points in `create_topic`, `enter_topic_todo` (creation), `publish_topic` (publishing), `switch_topic` (switching), `ensure_topic` (ensuring), `delete_topics` (deletion); the amendment chain machinery and the context views live in this cell
- **`goga/hooks`** — consumed as-is via its public surface: `emit_hook_event` for notifications; the staged delivery primitives per `goga/hooks/.usages/per-tool-delivery.md` for amendments
- **`goga/topics/git`** — consumed as-is; the plant's commit hash return value starts being used by the domain
- **`goga/commands/topics`, `goga/commands/pipeline`** — no changes; the pipeline flow inherits the events through `ensure_topic`
- **`goga/commands/hooks`** — no changes; the new actions appear in the inspection automatically
- Cross-import rule holds: `goga/topics` importing from `goga/hooks` creates no cycle (`goga/hooks` does not import `goga/topics`)
- Documentation surface: `docs/features/topics/hooks.md`, `docs/features/hooks/index.md`, `docs/features/hooks/hooks.md`, `docs/features/tools/hooks.md`

## Notes

- The ADR at `.goga/history/2026/add-topics-hooks/adr.md` is the authoritative decision record; this task inherits its nine decisions and its three deliberate PRD deviations (year → home path, commit hash added, switch outcome kind added)
- ADR open questions (registry sharing within a command, member names and signatures, home-path fact shape) remain design-stage questions — the task deliberately leaves them open
- The task contains no code examples and prescribes no architecture, per stage constraints; contract shapes are the design stage's output
