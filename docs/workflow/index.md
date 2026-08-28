# Workflow

Goga organizes feature development as two global workrounds — **refinement** and **development** — separated by review stages. Each command produces a concrete artifact (PRD, ADR, task, architecture, design, plan) — this lets you review decisions before they turn into code.

## Two workrounds

| Workround | Purpose | Commands |
|---|---|---|
| **Refinement** | Settle the *what and why*: turn a product idea into a verified engineering task | `define` → `discover` → `propose` → `review(task)` |
| **Development** | Build the *how*: from a verified task to accepted implementation | `brainstorm` → `apply` → `design` → `plan` → `build` → `change` → `accept` |

The refinement workround ends with a task review: once the task in `.goga/history/<year>/<topic>/task.md` is verified, the product side is settled and development can start. The development workround picks up the verified task and takes it all the way to an acceptance report.

> Command examples in this section use the slash-command form `/goga:<command>`. This form works in agents that consume the goga command bundle — currently `claude`, `opencode`, and `qwen` (see [`goga connect`](../cli/connect.md)). Codex and cursor do not register commands; in those agents invoke the skill directly: `goga-<command>` (Codex uses the `$` prefix — for example, `$goga-propose`).

### Refinement

Refinement turns a raw idea into a task definition that is worth engineering. Three entry depths exist, depending on how much elaboration the idea needs:

- **[`define`](define.md)** — the product is not yet understood: the problem, users, goals, and success criteria are extracted into a PRD (`.goga/history/<year>/<topic>/prd.md`). The longest refinement path opens here.
- **[`discover`](discover.md)** — the product is clear, but hard-to-reverse technical decisions are not: `discover` interviews them out and records short ADRs (`.goga/history/<year>/<topic>/adr.md`).
- **[`propose`](propose.md)** — everything above is already settled: the request is formulated directly as a structured task (`.goga/history/<year>/<topic>/task.md`).

```
define → discover → propose → review(task)
```

Every stage is optional on its own — a workround may start at `discover` or `propose` when the earlier artifacts already exist. The workround closes with [`review`](review.md) in its `task` mode, which verifies the formulated task before implementation begins.

### Development

Development takes a verified task to accepted code. Its length depends on how much technical elaboration the task needs — three depths again:

- **Full path** — the task requires new architecture, new cells, or contract changes. [`brainstorm`](brainstorm.md) produces the architecture plan, [`apply`](apply.md) materializes it into cell file structure, [`design`](design.md) details the modified CODEMANIFESTs, [`plan`](plan.md) compiles the ralph-loop execution plan, and [`build`](build.md) implements it.
- **Short path** — the architecture is clear and contracts stay stable (for example, an external dependency changes and the implementation is rewritten against a new usage file). Start at [`change`](change.md) directly.
- **Point fix** — a bug fix or behavior tweak that does not touch contracts: [`change`](change.md) alone.

```
brainstorm → apply → design → plan → build → change (bugfix loop) → accept
change → accept                                   # short path / point fix
```

Reviews of architecture, design, and plan artifacts are run via [`review`](review.md) between the stages — see below on when they are worth running.

> A point fix with no contract change can skip the refinement workround entirely: `change` → `accept`.

## Choosing a path

```text
Is the product side (problem, users, success criteria) settled?
│
├─ No
│   └─ Start refinement at define
│
├─ Yes, but hard-to-reverse technical decisions remain
│   └─ Start refinement at discover
│
├─ Yes, the task just needs formulation
│   └─ Start refinement at propose
│
└─ A verified task exists
    │
    ├─ Requires new architecture / cells / contract changes
    │   └─ Full development path (brainstorm → … → accept)
    │
    ├─ Architecture clear, contracts stable
    │   └─ Short path (change → accept)
    │
    └─ Point fix without a contract change
        └─ Standalone change (change → accept)
```

## Reviews

Reviews are **optional** at every stage — you decide how much verification each artifact needs. Skipping a review is acceptable when the change is small, the artifact is straightforward, or you are confident in the result. Run a review when the artifact introduces risk: large architectural changes, ambiguous contracts, or unfamiliar domains. Reviews catch drift while it is still cheap to fix.

The task review that closes refinement is the natural checkpoint between the two workrounds — it verifies the handoff artifact before implementation effort is spent.

```
define → discover → propose → review(task)
   → brainstorm → review(arch)
      → apply → design → review(design)
         → plan → review(plan)
            → goga build
               → change (bugfix loop)
                  → accept
```

## Commands and artifacts

| Command | Workround | Input artifact | Output artifact |
|---|---|---|---|
| [`define`](define.md) | Refinement | Product idea | `.goga/history/<year>/<topic>/prd.md` (PRD) |
| [`discover`](discover.md) | Refinement | A decision worth recording | `.goga/history/<year>/<topic>/adr.md` (short ADR) |
| [`propose`](propose.md) | Refinement | User request text | `.goga/history/<year>/<topic>/task.md` |
| [`review`](review.md) | both | Any artifact in `.goga/history/` (or a cell) | Review report |
| [`brainstorm`](brainstorm.md) | Development | `.goga/history/<year>/<topic>/task.md` | `.goga/history/<year>/<topic>/arch.md` |
| [`apply`](apply.md) | Development | `.goga/history/<year>/<topic>/arch.md` | Cell file structure (CODEMANIFEST, `.usages/`) |
| [`design`](design.md) | Development | Modified CODEMANIFEST | `.goga/history/<year>/<topic>/design.md` |
| [`plan`](plan.md) | Development | `.goga/history/<year>/<topic>/design.md` | `.goga/history/<year>/<topic>/plan.md` |
| [`build`](build.md) | Development | `.goga/history/<year>/<topic>/plan.md` | Implemented code (via a ralph-loop); the plan moves to `.goga/history/<year>/<topic>/completed/` on success |
| [`change`](change.md) | Development | Change description | Modified code + reconciled contracts and usages |
| [`accept`](accept.md) | Development | Completed implementation | Final acceptance report |

Workflow artifacts live at `.goga/history/<year>/<topic>/<kind>.md` (`<kind>` ∈ `prd | adr | task | arch | design | plan`): `<year>` is the current year as `YYYY`, and `<topic>` is a lowercase kebab-case slug — non-ASCII dropped, anything outside `[a-z0-9]` as `-`, repeat hyphens collapsed, edges trimmed (branch `release/1.3.0` → `release-1-3-0`). The topic directory is created lazily by the stage that first writes into it, and the whole `.goga/history/` tree is git-ignored by default. `goga pipeline <name> -b <branch>` prepares both a fresh branch and its fresh topic before a run.

## Next steps

- Product side not settled — open [`define`](define.md).
- Starting work that needs deep elaboration — open [`discover`](discover.md).
- Starting a straightforward task — open [`propose`](propose.md).
- Need a point fix — [`change`](change.md).
- Want to accept completed work — [`accept`](accept.md).
