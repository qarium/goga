# Workflow

Goga organizes feature development as a sequence of agent commands, separated by review stages. Each command produces a concrete artifact (task, architecture, design, plan) — this lets you review decisions before they turn into code.

## Two cycles and a shortcut

Goga supports two cycles plus a shortcut. The choice depends on how much technical elaboration the work needs.

> Command examples in this section use the slash-command form `/goga:<command>`. This form works in agents that consume the goga command bundle — currently `claude`, `opencode`, and `qwen` (see [`goga connect`](../cli/connect.md)). Codex and cursor do not register commands; in those agents invoke the skill directly: `goga-<command>` (Codex uses the `$` prefix — for example, `$goga-propose`).

| Path | When to use | Length |
|---|---|---|
| **Full cycle** | Work that requires deep technical elaboration: new architecture, new cells, contract changes, hard-to-reverse decisions | Longest |
| **Short cycle** | Work that does not require deep technical elaboration — the architecture is clear and the contracts stay stable (for example, an external dependency changes and the implementation is rewritten against a new usage file) | Short |
| **Standalone change** | Point fix that does not touch contracts | Shortest |

### Full cycle

The longest path, opened by [`discover`](discover.md). Use when a feature requires new architecture, new cells, or modifies existing contracts — work that needs deep technical elaboration. [`discover`](discover.md) settles hard-to-reverse decisions and records them as ADRs before the task is formulated; each subsequent artifact-producing step can be followed by a review of that artifact.

```
discover → propose → review(task)
   → brainstorm → review(arch)
      → apply → design → review(design)
         → plan → review(plan)
            → goga build
               → change (bugfix loop)
                  → accept
```

> Reviews are **optional** at every stage — you decide how much verification each artifact needs. Skipping a review is acceptable when the change is small, the artifact is straightforward, or you are confident in the result. Run a review when the artifact introduces risk: large architectural changes, ambiguous contracts, or unfamiliar domains. Reviews catch drift while it is still cheap to fix.

### Short cycle

Starts with [`propose`](propose.md). Use when the work does not require deep technical elaboration: the architecture is clear, the contracts stay stable, and the middle of the full cycle — `brainstorm`, `apply`, `design`, `plan`, `build` — would produce nothing of value. A typical case: a cell's contract stays the same, but an external dependency changes (another library, another SDK, a rewritten parser) — you formulate the task (`propose`), obtain a new `usage` file, and rewrite the implementation through `change`.

```
propose → review(task)
   → change → accept
```

This path significantly speeds up delivery when no elaboration is needed.

### Standalone change

Use for point fixes: bug fix, behavior tweak that does not touch contracts. `change` is followed by `accept` to formally close the fix.

```
change → accept
```

## Choosing a path

```text
Does the work require deep technical elaboration
(new architecture, new cells, contract changes, hard-to-reverse decisions)?
│
├─ Yes
│   └─ Full cycle (opens with discover)
│
├─ No, but the task needs formulation and an implementation pass
│   └─ Short cycle (opens with propose)
│
└─ No, point fix without a contract change
    └─ Standalone change
```

## Commands and artifacts

| Command | Input artifact | Output artifact |
|---|---|---|
| [`discover`](discover.md) | A decision worth recording | `docs/proposals/<topic>.md` (short ADR) |
| [`propose`](propose.md) | User request text | `docs/tasks/<topic>.md` |
| [`review`](review.md) | Any artifact in `docs/` | Review report |
| [`brainstorm`](brainstorm.md) | `docs/tasks/<topic>.md` | `docs/arch/<topic>.md` |
| [`apply`](apply.md) | `docs/arch/<topic>.md` | Cell file structure (CODEMANIFEST, `.usages/`) |
| [`design`](design.md) | Modified CODEMANIFEST | `docs/design/<topic>.md` |
| [`plan`](plan.md) | `docs/design/<topic>.md` | `docs/plans/<topic>.md` |
| [`build`](build.md) | `docs/plans/<topic>.md` | Implemented code (via ralphex) |
| [`change`](change.md) | Change description | Modified code + reconciled contracts and usages |
| [`accept`](accept.md) | Completed implementation | Final acceptance report |

## Next steps

- Starting work that needs deep elaboration — open [`discover`](discover.md).
- Starting a straightforward task — open [`propose`](propose.md).
- Need a point fix — [`change`](change.md).
- Want to accept completed work — [`accept`](accept.md).