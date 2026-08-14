# Propose

Transform a free-form user request into a structured task definition. The skill runs an interactive dialogue that drives the conversation through concrete hypotheses — one question per message, each with selectable options.

## Synopsis

```text
/goga:propose <description>
```

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-propose` (Codex: `$goga-propose`). See [Workflow](index.md).

## Output artifact

`docs/tasks/<topic>.md` — a structured task with the following sections:

- Current State
- Description
- Scope (in / out)
- Acceptance Criteria
- Stack
- External Dependencies
- Risks and Constraints
- Scope Estimate
- Existing Architecture
- Notes

## Algorithm

### Phase 1. Input collection

Accept the user's description verbatim. It may be brief (one sentence) or detailed (full specification). Do not request clarifications at this stage — gaps are resolved in Phase 3. Retain the original description throughout the session.

### Phase 2. Context loading

| Step | Action |
|---|---|
| 1 | Load DSL specification via `goga-cell` — understand cell and CODEMANIFEST terminology. |
| 2 | Load DSL application principles via `goga-cookbook` — understand the two-level usages model and authoring rules. |
| 3 | Run `goga schema` to obtain the cell hierarchy. If no architecture exists yet, record that as a fact. |
| 4 | Load base annotations and usages via `goga-codemanifest-base`. |
| 5 | Read relevant external-library usages from `.goga/usages/cooks/`. |

### Phase 3. Task formulation (interactive)

Iteratively align with the user on scope. Each iteration:

1. Describe the current state — what is missing (new feature) or what is unsatisfactory (modification).
2. Propose a hypothesis — concrete formulation with boundaries: what to implement, what is out of scope, which existing cells are impacted.
3. Ask a single question with 2–4 concrete options.
4. Adjust and repeat until the user approves.

After approval, optionally offer to include code examples (target API, language-specific usage patterns).

**Completion criteria:** task essence unambiguous, boundaries defined, user approval obtained.

### Phase 4. Technology stack and external dependencies

1. Define the implementation stack (frameworks, libraries, databases, brokers, infrastructure).
2. Identify external dependencies not yet present in the project. For each, check whether a usage file exists in `.goga/usages/cooks/` — if missing or stale, schedule creation/update in Phase 5.
3. Wait for user approval.

### Phase 5. Usage file management

For each external dependency without a usage file: propose content, get user approval, create `.goga/usages/cooks/<name>.md`. For dependencies whose usage file lacks new patterns: propose additions, get approval, update.

### Phase 6. Scope estimation

Assess scale (number of entities, subsystems, interaction complexity). Present a single-task or subtask breakdown to the user for approval.

### Phase 7. Task persistence

Write the task to `docs/tasks/<topic>.md` using the task template. Present a summary: task name, stack, dependency count, scope, risks.

## Dialogue rules

- Drive via hypotheses, not open-ended questions.
- One question per message, with 2–4 concrete options.
- Structure every response.

## Inputs and outputs

| | |
|---|---|
| **Input** | Free-form description in natural language |
| **Output** | `docs/tasks/<topic>.md` |

## What happens next

- Run [`review`](review.md) with the `task` type to validate the formulation.
- On approval, proceed to [`brainstorm`](brainstorm.md) (full cycle) or [`change`](change.md) (short cycle).
