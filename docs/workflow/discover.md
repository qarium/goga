# Discover

Interview the user relentlessly about a decision until every branch of the design tree is resolved, then record the result as a short ADR. The skill drives the conversation in rounds of numbered questions — each with a recommended answer — and does not write anything down until the user confirms shared understanding.

## Synopsis

```text
/goga:discover <topic>
```

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-discover` (Codex: `$goga-discover`). See [Workflow](index.md).

## Output artifact

`.goga/history/<year>/<topic>/adr.md` — a short ADR (the topic comes from the current git branch; the directory is created lazily if needed). An ADR is 1–3 sentences: the context, the decision, and why. Optional sections (`Status`, `Considered Options`, `Consequences`) are included only when they add genuine value.

## Algorithm

### Design tree

The decision under discussion is mapped as a **design tree**: every decision branches into the decisions that hang off it. The interview works the tree in rounds.

The **frontier** is every decision whose prerequisites are already settled — the questions that can be asked *now* without guessing at answers not yet heard. Each round asks the whole frontier at once: every question is numbered and carries a recommended answer. The next round starts only after the user answers.

Answers reshape the tree: settled decisions push the frontier outward and unblock the questions that depended on them. A question whose answer depends on another question still open in the current round belongs to a *later* round.

### Roles

- **Facts are the skill's job, never the user's.** When a frontier question needs a fact from the environment (filesystem, tools), a sub-agent is dispatched to find it. A running exploration is an unsettled prerequisite — only the questions downstream of it wait for the report; the rest of the frontier is asked immediately.
- **Decisions are the user's.** Each decision is put to the user, and the skill waits.

### Working context

A working context is kept in the context window (never written to disk):

```yaml
terms:    # glossary: term -> definition, captured during the interview
decided:  # what has been settled in this session, not to be re-litigated
```

The context only grows — entries are appended, never overwritten. After each round, new or sharpened definitions land in `terms` and confirmed decisions in `decided`.

### Term discipline

- A **fuzzy term** is pinned down with a concrete definition before moving on — one is proposed and put to the user.
- An **overloaded word** doing two or three jobs across questions is named explicitly, split definitions are proposed, and the user chooses.
- An **informal term** from the user is captured in its formal version in `terms` and used consistently from then on.
- A term already in `terms` is used with that exact definition — no re-coining, no paraphrasing, no drift.

The ADR's "why" only makes sense if the vocabulary it uses is sharp — this is why term discipline runs throughout the interview, not as a final pass.

Questions drifting into contracts — signatures, cell boundaries, wiring — are not answered: they are recorded in the ADR as unresolved and the interview moves on.

### Completion

The interview is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. The ADR is written only after the user confirms shared understanding.

## When to write an ADR

All three of these must be true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful.
2. **Surprising without context** — a future reader will look at the code and wonder why it was done this way.
3. **The result of a real trade-off** — there were genuine alternatives and one was picked for specific reasons.

If a decision is easy to reverse, skip it. If it is not surprising, nobody will wonder why. If there was no real alternative, there is nothing to record beyond "we did the obvious thing."

## Inputs and outputs

| | |
|---|---|
| **Input** | A decision worth recording, in natural language |
| **Output** | `.goga/history/<year>/<topic>/adr.md` — a short ADR |

## What happens next

- Proceed to [`propose`](propose.md) to turn the settled decision into a structured task — the task review at the end of refinement verifies the result, the settled decisions included.
