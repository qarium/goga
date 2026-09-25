# Topics Domain Extension Surface: Lifecycle Events and Artifact Amendment

## Problem

Goga users organize work as topics, but everything that happens to a topic — creation, publication, switching, todo entry, deletion — stays invisible outside goga. Teams that also track the same work in external systems (task trackers first of all) duplicate the bookkeeping manually: a ticket is created by hand when work starts, updated by hand when the todo changes, and closed by hand when the topic is deleted. The external record is slow to update, drifts, or is abandoned.

The root cause is structural. The hooks platform exists precisely as the extension surface of goga domains for installed tool packages, and several domains already declare actions — but the topics domain declares none. A tool author cannot observe the topic lifecycle at all, so no integration (a tracker syncer, a chat notifier, a dashboard feeder) can be built against it. The manual duplication is a symptom of this missing surface.

## Users

- **Primary: tool package author.** Builds `goga_tool_*` packages on the existing hooks platform (has already authored `register_hooks` callbacks for the statuses and onboarding actions). Wants to react to the topic lifecycle and to co-author topic artifacts — a task-tracker syncer is the first target. Needs stable action addresses, a predictable event context, clear failure semantics, and the guarantee that published catalog records are never rewritten by a goga update.
- **Secondary: goga end user.** Runs `goga topics create/switch/delete` daily and installs tool packages built by others. Needs topics commands to keep working exactly as today when hooks are installed: a broken integration degrades with a warning, never breaks topic work, and adds no new prompts or steps.
- **Affected: external-system readers** (team members). Read the tracker or dashboard without using goga; expect the external record to reflect the topic lifecycle accurately and timely, and expect artifact content (commit messages, todos) to reference the external record where an integration provides one.

## Goals

1. **Observable topic lifecycle.** A tool-package author can subscribe to every explicit operation of the topics domain — creation (across all its paths), publication, switching, todo entry, deletion — through the existing hooks platform, with stable action addresses and no goga code changes on the tool side.
2. **Integration-ready event facts.** Each notification event delivers the facts of the moment — topic identity (slug, year, hosting branch) plus the final content of the operation (todo text, commit message, deletion composition) — sufficient for a tool to update an external system from one event, without re-deriving repository state.
3. **Co-authored topic artifacts.** At the birth of a topic and at the revision of its todo, a tool can transform the content the domain is about to fix — the commit message and the todo text — so the repository and the external system reference each other (ticket ID in the commit message, signature in the todo).
4. **Dependable topics flow.** Topics commands behave exactly as today when nothing subscribes, and a failing hook of any topics action degrades predictably (soft) without breaking or blocking topic work.

Explicitly not optimized: ready-made integrations shipped with goga, two-way synchronization, and status-progression events (see Scope).

## User Experience

### The tool author's experience

**Entry point.** The author writes a `register_hooks(hooks)` callback in their `goga_tool_*` package and subscribes to any subset of the seven topics actions through the platform's `hooks.subscribe(domain, action, name, hook)` mechanism. Nothing is cached: package edits apply from the next run.

**Verification.** `goga hooks` shows the topics actions with their subscribed hooks grouped by tool, on par with the existing domains — wiring can be verified without running a topic operation.

**Notification events.** A hook receives `context` — a read-only view of the event facts built by the domain from the operation's own data (never re-read from the repository) — and may also declare `self`, the tool's isolated run-scoped state that links its hook invocations of one run. The five notification actions fire after the corresponding operation fully succeeds:

| Address | Fires |
|---|---|
| `topics.topic_created` | once per successful creation — every path: quarantined no-switch, switch path, publication path, and the fast creation of `ensure` |
| `topics.topic_published` | after a successful publication push to origin |
| `topics.topic_switched` | on every completed switch — local checkout, local branch created from a remote-tracking ref, and the idempotent already-on-branch outcome |
| `topics.topic_todo_entered` | when an editor entry on an existing topic completes with a saved write (not on cancellation) |
| `topics.topic_deleted` | once per fully deleted target, after its complete removal |

**Event composition.** A published creation emits `topic_created` then `topic_published`. A switch with the todo entry emits `topic_switched`, then (after the editor session) `topic_todo_entered`. `ensure` emits the underlying moment — `topic_created` or `topic_switched`, plus `topic_todo_entered` under its todo flag — and introduces no separate event of its own. The same events fire when pipelines invoke the same domain routines (`goga pipeline <name> -t <identifier>`); in that flow the topic always exists, because the ensure semantics creates it.

**Amendment actions.** Two pre-fixation moments let a tool transform the content the domain is about to fix:

- `topics.amend_creation` — after all user input is resolved (the todo value from the command line or from the creation editor session) and after the publication ask, immediately before the first mutation of a creation, on every creation path. The context carries the topic identity facts, the draft commit message when the chosen path builds a commit (quarantine and publication paths; absent for the switch and ensure paths, which write the todo without a commit), and the draft primary todo when one is resolved (absent on the switch path without a todo — the event still fires with the identity facts, and the tool decides whether to act without a description).
- `topics.amend_todo_entry` — when the user saves the todo of an existing topic in an editor session (`switch --todo`, `ensure --todo`), after the save and before the file write. The context carries the saved draft text and the identity facts.

**The amendment chain.** Each draft is exposed read-only together with one amendment operation that replaces its full content. Tools apply in the platform's deterministic enumeration order, each tool seeing the result of the previous one. The domain fixes only the final draft: the amended commit message lands in git history, the amended todo lands in `todo.md`, and the corresponding notification events report the final content. The author's typical flow — create the tracker ticket from the draft todo at `amend_creation`, stamp its ID into the commit message and a signature into the todo — completes within one subscription.

**Amendment guards.** A hook that raises is skipped: its amendment is not applied, the draft stands as the previous tool left it (or as the default), a warning names the tool, the action, and the reason, and the chain continues. An amendment to empty or whitespace-only content is rejected the same way. An amendment can never cancel, redirect, or defer the operation.

### The end user's experience

Nothing new to learn. Topics commands keep their current outcomes, outputs, exit codes, prompts, and mutation boundaries. With no tool subscribed, commands behave and perform exactly as before the change. With integrations installed, the only additions are: platform-standard warning lines on stderr when a hook fails (naming the tool, the action, and the reason), and tool-authored content inside the artifacts the user already works with (a ticket reference in a creation commit message, a signature line in `todo.md`). A broken tool package import remains the only fatal case, as on the platform today.

### Boundaries of the experience

- Notification events are observations after the fact: hooks cannot veto, alter, or roll back an operation, and nothing is returned from them.
- Amendment influence is limited to the two content kinds (creation commit message, todo text) at the two pre-fixation moments.
- Delivery is fire-and-forget with no replay, queueing, or event log: a tool that missed an event rebuilds its state from the board and the history tree. External consistency after a soft skip is the tool's responsibility.
- A manual `goga topics switch` onto a branch hosting no topic is the one marginal case: `topic_switched` fires with branch-only identity (no topic facts present).

## Requirements

### Action catalog

- **R1.** The product must declare seven actions under the `topics` domain, addressable through the existing subscription mechanism: five notification actions — `topic_created`, `topic_published`, `topic_switched`, `topic_todo_entered`, `topic_deleted` — and two amendment actions — `amend_creation`, `amend_todo_entry`. All seven carry the soft error class. Catalog records are additive and never rewritten; the existing actions of other domains keep their addresses and behavior.

### Notification events

- **R2. `topic_created`** must fire exactly once per successful creation, on every creation path (quarantined no-switch, switch path, publication path, and `ensure`'s fast creation), only after the operation fully succeeds. The context must carry the final facts: the topic slug, the year, the branch name as entered, the final todo text when one was resolved, and the path facts stating whether the branch was checked out and whether the topic was published.
- **R3. `topic_published`** must fire after a successful publication push. A published creation emits `topic_created` and then `topic_published`; both carry the final content, including the final commit message. A publication that fails and rolls back emits no events at all.
- **R4. `topic_switched`** must fire on every completed switch: a local checkout, a local branch created from a remote-tracking ref, and the idempotent already-on-branch outcome. The context must carry the branch name always; the topic slug and year when the branch hosts a topic of the command's scope; branch-only identity when it does not (the marginal manual-switch case).
- **R5. `topic_todo_entered`** must fire when an editor entry on an existing topic completes with a saved write, and must not fire on a cancelled entry. The context must carry the final written text, the slug, the year, and the branch.
- **R6. `topic_deleted`** must fire once per target whose deletion completed — the local branch, the origin twin when present, and the topic directory when targeted, all removed. A target whose deletion fails midway (and is restored) must emit nothing; targets fully removed before the failure must emit theirs. The context must carry the slug, the year, and which elements were removed.
- **R7.** Events of one command must fire in operation order, after the success of their moment; delivery to hooks follows the platform's tool enumeration order.

### Amendment actions

- **R8. `amend_creation`** must fire on every creation path after all user input is resolved and after the publication ask, immediately before the first mutation. The context must carry the identity facts (slug, year, branch as entered, path facts), the draft commit message when the path builds a commit, and the draft primary todo when one is resolved; absent drafts are simply not present.
- **R9. `amend_todo_entry`** must fire after the user saves the todo of an existing topic in an editor session and before the file write. The context must carry the saved draft text and the identity facts.
- **R10.** Amendment must follow the transformation-chain semantics: each draft is readable, each has one amendment operation replacing its full content; subscribed tools apply in enumeration order, each receiving the result of the previous one; the domain fixes only the final draft into the artifact (commit message or todo file).
- **R11.** Amendment guards must hold for both actions: a raising hook is skipped with its amendment unapplied and a warning naming the tool, the action, and the reason — the draft stands and the chain continues; an amendment to empty or whitespace-only content is rejected with the same warning form; no amendment can cancel, redirect, or defer the operation.
- **R12.** Amended content must be observable where the artifact lives: the final commit message in git history, the final todo text in `todo.md`, and both reported as final facts by the corresponding notification events.

### Common contract

- **R13.** Event contexts must be built by the domain from the operation's own data, without re-reading the repository; facts are read-only views; per-tool isolation and the optional per-tool `self` follow the platform rules.
- **R14.** With no subscriber for an action, the command must behave and perform exactly as today — identical output, exit codes, and prompts. No topics action may introduce a new prompt, question, or required input; the existing preflight, todo resolution, and publication-ask ordering is preserved.
- **R15.** `goga hooks` must list all seven topics actions with their subscribed hooks grouped by tool, consistent with the presentation of the existing domains.
- **R16.** The topics hooks documentation must describe every action — its firing moment, error class, context facts (and, for the amendment actions, the drafts and the chain semantics) — and must replace the current statement that the topics domain exposes no hook actions; the action lists in the platform documentation must be synchronized.

## Constraints

- **C1.** The extension must use the existing hooks platform only — `register_hooks`/`subscribe` registration, the run registry, fire-and-forget delivery, per-tool context views, soft/hard error classes, `goga hooks` inspection. No parallel registration or delivery mechanism may be introduced; the amendment surface uses the platform's established capability of method-bearing contexts (the statuses action is the precedent).
- **C2.** The action catalog is additive and published records are never rewritten: the seven records and their soft error class are permanent.
- **C3.** Existing actions and their subscribers must not break: no address renames, no silent disappearances of previously registered hooks.
- **C4.** Topics command semantics remain unchanged: outcomes, outputs, exit codes, prompts, and mutation boundaries (all mutations local except the two origin pushes — publication and deletion; no fetch ever happens). The amendment actions add no user decision points and no new interactive moments.
- **C5.** Goga itself performs no external-system interaction: no tracker APIs, credentials, or integration configuration in goga; the network surface of the affected commands remains exactly the two pushes. All integration behavior lives in tool packages.
- **C6.** Topic identity, addressing, and statuses remain owned by the history domain: events carry facts consistent with that model; no status-progression events are introduced by this change.
- **C7.** Emission must be unobtrusive: without subscribers there is no user-visible change in behavior or speed of the commands; the only permitted new output is the platform-standard hook diagnostic (the warning naming tool, action, and reason).

## Scope

### In Scope

- The seven catalog actions of the `topics` domain and their emission at every checkpoint of the topics-domain operations, including the same domain routines invoked through pipeline topic resolution (`goga pipeline <name> -t <identifier>`).
- The event context contract per action: identity and moment facts for notifications; drafts plus amendment operations and the transformation-chain semantics for the amendment actions.
- The amendment guards (soft skip, empty-amendment rejection) and the fixation of amended content into the artifacts.
- Inspection of topics subscriptions through `goga hooks`.
- Documentation: the topics hooks reference covering all seven actions, replacement of the "no hook actions" statement, and synchronization of the action lists in the hooks platform documentation.

### Out of Scope

- Ready-made integrations and reference tool packages (trackers, chats, dashboards) — goga ships the surface only.
- Two-way synchronization: any reading of, or reacting to, external systems by goga itself.
- Status-progression events of topics (the derived status scale belongs to the history domain; a possible future topic).
- Events for read operations (the board, status listings).
- Delivery guarantees beyond fire-and-forget: replay, queueing, an event log, at-least-once semantics.
- End-user controls over hooks (configuration toggles, filters, enable/disable) — hook management stays with the tool packages and the platform.
- Changes to the hooks platform core (registry, dispatch, error-class model) beyond the additive catalog records.
- Changes to topics command semantics, prompts, or outputs.
- Emission from history-domain mutations (e.g., orphan pruning).

## Success Criteria

1. **Subscribable lifecycle.** A subscribed tool package receives each notification event on the corresponding successful operation: every creation path fires `topic_created`; `--publish` additionally fires `topic_published`; switches — local checkout, remote-created, and idempotent — fire `topic_switched`; a saved editor todo fires `topic_todo_entered`; each fully deleted target fires `topic_deleted`.
2. **Facts sufficiency.** From the notification context alone, a hook identifies the topic (slug, year, branch) and the final facts of the moment (todo text, commit message, publication fact, deletion composition) without reading the repository.
3. **Composition.** `ensure` emits `topic_created` or `topic_switched` (plus `topic_todo_entered` under its todo flag) and no separate event of its own; `switch --todo` emits `topic_switched` then `topic_todo_entered`; a published creation emits `topic_created` then `topic_published`.
4. **No success — no event.** A rolled-back publication, a switch aborted on a dirty tree, and a deletion that fails and restores emit no events for the failed part; fully completed parts before a failure emit theirs.
5. **Amendment chain.** With two subscribed tools, amendments apply in enumeration order, each tool seeing the previous tool's result; the fixed artifact (the commit message in git history, the `todo.md` content) carries the final amended content, and the notification events report it as the final facts.
6. **Amendment guards.** A raising hook leaves the draft unchanged, the command completes successfully, one warning names the tool, action, and reason, and the remaining hooks still run; an empty amendment is rejected the same way.
7. **Marginal switch.** A manual switch onto a branch hosting no topic emits `topic_switched` with branch-only identity; a pipeline-driven (ensure) switch always carries full topic identity.
8. **Transparency.** With no subscribed tools, every topics command produces byte-identical output, exit codes, and prompts as before the change.
9. **Soft degradation.** A failing notification hook does not change the command's outcome; exactly one warning is shown; other subscribed hooks still receive the event.
10. **Inspection.** `goga hooks` shows the topics actions with subscribed tools grouped under the topics domain, on par with the existing domains.
11. **Stability.** Existing `statuses` and `onboarding` subscriptions keep working without re-registration after the update.
12. **Documentation.** All seven actions are documented with their firing moment, error class, and context facts or drafts; no stale "no hook actions" claim remains in the shipped documentation.
