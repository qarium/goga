# Topics domain: seven hooks actions — post-fact notifications, staged amendment chain, home-path identity

**Status:** accepted

The `topics` domain opens its lifecycle to tool packages through seven soft actions of the existing hooks platform: five notifications (`topic_created`, `topic_published`, `topic_switched`, `topic_todo_entered`, `topic_deleted`) and two amendments (`amend_creation`, `amend_todo_entry`). Notifications ride the platform's plain fire-and-forget emission after the success of their moment; amendments ride the platform's staged per-tool delivery (the `onboarding` precedent) because R11's per-hook atomicity — "a raising hook's amendment is not applied" — is unreachable through the generic `emit_hook_event` intercept. Topic identity in every context is **slug + home path + branch**: the standalone `year` fact is deliberately replaced by the topic home path `.goga/history/<year>/<topic>`, the actionable address in the history tree (the year stays recoverable inside it).

## Decisions

1. **Catalog.** Seven records are added additively to the platform catalog (`goga/hooks/catalog`), all `error_class=soft`, never rewritten: `topics/topic_created`, `topics/topic_published`, `topics/topic_switched`, `topics/topic_todo_entered`, `topics/topic_deleted`, `topics/amend_creation`, `topics/amend_todo_entry`. No platform-core change (C1): registration, run registry, error classes, and `goga hooks` are reused as-is.
2. **Two mechanisms by kind.** Notification actions use plain `emit_hook_event` — fire-and-forget, one read-only context view per tool, optional per-tool `self`. Amendment actions use staged delivery over the platform's public primitives (the documented `per-tool-delivery` pattern, `onboarding/amend_config` precedent): the domain drives the subscription loop itself, because only it can commit or discard a hook's buffered amendment (q2).
3. **The amendment chain.** One shared draft holder per amendment action. Each draft is exposed read-only with exactly one amendment operation replacing its full content. Per-hook buffer: an `amend` call buffers; the buffer commits to the shared holder only when the hook call returns without raising; a raising hook's buffer is discarded, the platform-form warning `hook <name> of tool <tool> failed on topics.<action>: <reason>` is emitted, and the enumeration continues in the platform order (alphabetical tools × registration order within a tool). An empty or whitespace-only amendment is rejected at commit — the last buffered value is the one checked — with the same warning form. Hooks of one tool are independent (hook granularity, not tool granularity). No amendment can cancel, redirect, or defer the operation; the domain fixes only the final draft into the artifact (amended commit message into git, amended text into `todo.md`) and reports it as the final facts of the corresponding notifications (q2).
4. **Emission placement.** Emission lives in the topics domain routines, not in the CLI cell: pipeline topic resolution (`goga pipeline <name> -t`, the sole non-topics caller via `ensure_topic`) invokes the same routines and receives the same events. `topic_created` fires exactly once per successful creation from the unified post-success point of each of the four creation paths (quarantined no-switch, switch, publication, `ensure` fast creation); on the publication path it is deferred until the push succeeds — a rolled-back publication emits nothing at all (R3). Deletion emits per target inside the removal loop, after the target's full removal: targets fully removed before a later failure emit theirs (R6) (q5).
5. **Identity vocabulary.** Identity facts are **slug, home path, branch as entered**. The home path is derived deterministically from slug and year by the history path rules — no repository reads. Marginal manual switch onto a branch hosting no topic: identity degrades to **branch-only** (detection: `candidate.topic is None` in switch-candidate resolution — operation data, not a re-read) (q4a, q7i).
6. **Marginal corners.** `ensure --todo` on a branch hosting no topic creates the topic directory and enters a fresh todo today; it fires `amend_todo_entry` + `topic_todo_entered` with derived identity (slug normalized from the branch name, current year → home path) and fires **no** `topic_created` — directory creation is not one of R2's creation paths. `switch --todo` onto a topic-less branch keeps today's clean pre-mutation error and emits nothing (q4b, q4c).
7. **Context models** (semantics; names and shapes are design-stage):
   - `topic_created` — identity; final todo when resolved; path facts (checked out, published); commit message + commit hash **iff the path builds a commit** (quarantine and publication paths; absent on switch/`ensure` paths) (q7-1).
   - `topic_published` — identity; final commit message + commit hash; final todo (q7-2).
   - `topic_switched` — identity (branch-only in the marginal case); **switch outcome kind**: local-checkout / created-from-remote / already-on-branch (q7-3).
   - `topic_todo_entered` — identity; final written text (post-amendment). No prior text (q7-4).
   - `topic_deleted` — identity (slug, home path); removal composition: local branch (name), origin twin (name, when the target had one), whether the topic directory was removed. No deleted-commit hash (q7-5).
   - `amend_creation` — identity; path facts; draft commit message (iff the path builds one) + draft primary todo (when resolved); the identity-only degenerate case (switch path without a todo) is valid — the tool decides whether to act (R8).
   - `amend_todo_entry` — identity; draft of the saved text. No prior text (q7-4).
8. **Facts without repository reads.** Contexts are built from the operation's own data (R13): the domain threads the values it discards today — the creation plant's commit hash (return value), the final commit message (the amended text is an argument of the plant by construction of the amendment surface), the resolved year through switching. No `git log`/ref-tree re-reads are introduced for events.
9. **Inspection and documentation.** `goga hooks` changes nothing — the records appear automatically in its tool → domain → action presentation. The stub "no hook actions" statement in `docs/features/topics/hooks.md` is replaced by the topics hooks reference (firing moment, error class, facts/drafts per action); the action lists in `docs/features/hooks/index.md`, `docs/features/hooks/hooks.md`, and `docs/features/tools/hooks.md` are synchronized; the maintainer recipe `goga/hooks/.usages/declaring-actions.md` is followed.

## Deviations from the PRD (deliberately accepted)

- **`year` → home path** (R2/R4/R5/R6/R8/R9 list "slug, year"): the standalone year carries little integration value; the home path is the address a tool acts on and embeds the year (q6 custom answer, confirmed q7i).
- **Commit hash added** to `topic_created`/`topic_published` beyond R2/R3's enumerated facts — additive, near-zero cost (the plant already returns it), high value for tracker linkage (q3).
- **Switch outcome kind added** to `topic_switched` beyond R4's identity list — additive; lets consumers filter idempotent-switch noise (q7-3).

## Open Questions (design stage)

- Sharing one `HookRegistry` instance within a command (statuses creates a fresh registry per assembly; multiple topics emissions should not multiply enumeration/import costs).
- Exact member names and signatures of the context views, drafts, and amendment operations; exact wording of warning reasons.
- The concrete shape of the home path fact (string vs structured) — semantics fixed here, shape is the design's.

## Considered Options

- **`emit_hook_event` with immediate amendment application (statuses pattern)** — rejected: a landed amendment before a raise would survive, breaking R11's letter (q2).
- **`emit_hook_event` + softened R11 recorded as deviation** — rejected: per-hook atomicity is the published contract; staged delivery already exists as a documented platform pattern (q2).
- **Suppressing events in the `ensure --todo` marginal corner** — rejected: a silent observability gap (q4b).
- **`topic_created` for the `ensure --todo` directory creation** — rejected: expands R2's closed catalog of creation paths (q4b).
- **Bare `year` identity fact** — rejected in favor of the home path (q6/q7).
- **Prior todo text in the todo contexts** — rejected: minimal facts; a tool keeps its own state in `self` (q7-4).
- **Strict R4 switch identity without the outcome kind** — rejected (q7-3).
