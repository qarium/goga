# Workflow

Goga organizes feature development as a sequence of agent commands, separated by review stages. Each command produces a concrete artifact (task, architecture, design, plan) — this lets you review decisions before they turn into code.

## Three paths

Goga supports three working modes. The choice depends on how deeply the change affects contracts.

> Command examples in this section use Claude Code style (`/goga:<command>`). For other agents, invoke the skill directly: `goga-<command>` (for example, `goga-propose`, `goga-change`).

| Path | When to use | Length |
|---|---|---|
| **Full cycle** | New feature that affects architecture and contracts | Long |
| **Propose → Change** | Contract stays the same, but an external dependency changes (new usage file, rewritten implementation) | Short |
| **Standalone change** | Point fix that does not touch contracts | Shortest |

### Full cycle

Use when a feature requires new architecture, new cells, or modifies existing contracts. Each artifact-producing step can be followed by a review of that artifact.

```
propose → review(task)
   → brainstorm → review(arch)
      → apply → design → review(design)
         → plan → review(plan)
            → goga build
               → change (bugfix loop)
                  → accept
```

> Reviews are **optional** at every stage — you decide how much verification each artifact needs. Skipping a review is acceptable when the change is small, the artifact is straightforward, or you are confident in the result. Run a review when the artifact introduces risk: large architectural changes, ambiguous contracts, or unfamiliar domains. Reviews catch drift while it is still cheap to fix.

### Propose → Change

Use when a cell's contract stays the same, but an external dependency changes: another library, another SDK, a rewritten parser. In this case you formulate the task (`propose`), obtain a new `usage` file, and rewrite the implementation through `change`, skipping the rest of the flow.

```
propose → review(task)
   → change → accept
```

This path significantly speeds up delivery when the contract is stable.

### Standalone change

Use for point fixes: bug fix, behavior tweak that does not touch contracts. `change` is followed by `accept` to formally close the fix.

```
change → accept
```

## Choosing a path

```text
Does the contract (CODEMANIFEST) change?
│
├─ Yes, new architecture or new cell
│   └─ Full cycle
│
├─ No, but an external dependency changes (usage, implementation)
│   └─ Propose → Change
│
└─ No, fix without a contract change
    └─ Standalone change
```

## Commands and artifacts

| Command | Input artifact | Output artifact |
|---|---|---|
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

- Starting a new feature — open [`propose`](propose.md).
- Need a point fix — [`change`](change.md).
- Want to accept completed work — [`accept`](accept.md).