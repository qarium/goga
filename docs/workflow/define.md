# Define

Transform a raw product idea into a complete Product Requirements Document (PRD). The command runs a linear interview pipeline where every stage of the product definition — problem, users, goals, experience, requirements, constraints, scope, success criteria — is produced by a specialized subskill, and the results are assembled into a single consistent document.

## Synopsis

```text
/goga:define <description>
```

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-define` (Codex: `$goga-define`). See [Workflow](index.md).

## Output artifact

`docs/defines/<topic>.md` — a PRD with sections for the problem, users, goals, user experience, requirements, constraints, scope, and success criteria. If a PRD with the same topic already exists, the collision is handled explicitly rather than silently overwriting unrelated work.

## Pipeline

The orchestrator is intentionally thin: it never performs product analysis itself, it only sequences subskills and maintains the shared product context (kept in the session, not on disk).

```text
project → problem → users → goals → experience
       → requirements → constraints → scope → success
       → challenge → prd
```

Each stage declares what it consumes and produces:

| Stage | Produces |
|---|---|
| `project` | Project context — what the product is |
| `problem` | The problem worth solving |
| `users` | Who the users are |
| `goals` | User and product goals |
| `experience` | The user experience |
| `requirements` | Requirements |
| `constraints` | Constraints |
| `scope` | Scope boundaries (in / out) |
| `success` | Success criteria |
| `challenge` | Validation of the whole definition |
| `prd` | The final PRD document |

## Conflicts

Any stage may report a conflict with an earlier decision. Conflicts are resolved before the pipeline continues: a resolver reconsiders the decisions across the entire context, and if an earlier decision changes, the earliest affected stage is re-run from that point. A PRD is never generated while unresolved conflicts remain.

## When to use

Use `define` when the work starts from a product idea rather than a technical task — before [discover](discover.md) and [propose](propose.md), when the "what and why" has not been settled yet. The PRD then feeds the refinement cycle: `discover` settles the hard technical decisions, `propose` formulates the engineering task.
