---
name: goga-task-by-proposing
description: Interactive task formulation from a raw request
---
# Task Formulation

## Purpose

Transforms a raw user request (e.g., "add authorization") into a **formulated task** — a structured document containing
the description, technology stack, dependencies, and scope estimate. The output is persisted at the path printed by
`goga history path -f task.md` (run `goga history ensure` first if the topic directory does not exist)
and serves as input for the `goga-brainstorm` skill.

---

## Dialogue Rules

1. **Drive the conversation through hypotheses.** Present concrete options rather than open-ended questions.

2. **Ask one question per message.** Deliver a single focused question with 2-4 answer options.

3. **Structure every response.** This discipline prevents unstructured discussion.

---

### Phase 1: Input Collection

Accept the user's description of the desired outcome.

The description may be:
- **Brief** — a single sentence or feature name
- **Detailed** — a complete specification with requirements

If the description is brief, do not request clarifications yet. Phase 3 will resolve missing details.
Retain the original description throughout the session.

### Phase 2: Context Loading

#### Step 1: Load the DSL specification

Invoke `goga-cell` via the **Skill tool**.
Purpose:
- Understand cell and CODEMANIFEST terminology for analyzing the existing architecture

#### Step 2: Load DSL application principles

Invoke `goga-cookbook` via the **Skill tool**.
Purpose:
- Understand the two-level usages model (project-level `.goga/usages/` and cell-level `<cell_path>/.usages/`)
- Learn usage file authoring principles for creating `.goga/usages/cooks/`

#### Step 3: Retrieve the project schema

Run `goga schema` to obtain the cell hierarchy.

If the project lacks an existing architecture, record this as a known fact.

#### Step 4: Retrieve base annotations and usages

Invoke `goga-codemanifest-base` via the **Skill tool**.

#### Step 5: Read relevant usages

If the task involves external libraries or technologies, read their corresponding usages from `.goga/usages/cooks/`.

### Phase 3: Task Formulation

**Objective:** Align with the user on the exact scope and boundaries of the task.

Using the user's description (Phase 1) and project context (Phase 2), iteratively formulate the task:

1. **Define the current state** — based on Phase 2 context, describe:
   - For new features — what the project currently lacks
   - For modifications — how the affected area currently operates and what is unsatisfactory

2. **Propose a hypothesis** — a concrete task formulation with defined boundaries:
   - What to implement
   - What is explicitly out of scope
   - Which existing cells are impacted

3. **Ask a single question** — validate whether the current state description and hypothesis are correct, and whether any aspects are missing

4. **Await the response** — adjust and repeat

5. **After formulation approval** — offer to include code examples in the task:
   - If the task describes a library or API — suggest defining the target API with usage examples in the project's language
   - If the user emphasized a specific API or code during discussion — suggest capturing it in the task
   - If the user wants to write code directly — accept and include it in the task
   - If examples are unnecessary — proceed to Phase 4

**Completion criteria:**
- The task essence is formulated unambiguously
- Scope boundaries are defined (included and excluded)
- The user has approved the formulation

### Phase 4: Technology Stack and External Dependencies

**Objective:** Define the technology stack and identify external dependencies.

1. **Define the implementation stack** — technologies to be used:
   - Frameworks, libraries, databases, message brokers, infrastructure components
   - Existing project usages (in `.goga/usages/`) that already describe the tools in use

2. **Identify external dependencies** — components not yet present in the project:
   - If the task requires a new component, record it
   - For each external dependency, check whether a usage file exists in `.goga/usages/cooks/`
   - If no usage file exists, schedule creation in Phase 5
   - If the existing usage file does not cover new usage patterns, schedule an update in Phase 5

3. **Await feedback** — the user approves or requests changes
   - **Approved** → proceed to Phase 5
   - **Rejected** → propose a revised stack incorporating the feedback

**Completion criteria:**
- Implementation stack is defined (frameworks, libraries, databases, brokers, infrastructure)
- External dependencies are documented
- `.goga/usages/cooks` files to create or update are identified

### Phase 5: Usage File Management (.goga/usages/cooks)

**Objective:** Ensure all external dependencies from Phase 4 are covered by usage files.

For usage file authoring principles, invoke the `goga-cookbook` skill.

#### Creating new usage files

For each external dependency without a usage file:

1. **Propose usage file content:**
   - Component description and purpose
   - Usage patterns relevant to the current task
   - Code examples

2. **Await feedback** — the user approves or requests changes
   - **Approved** → create `.goga/usages/cooks/<name>.md`
   - **Rejected** → propose revised content

#### Updating existing usage files

For each dependency whose usage file does not cover new usage patterns:

1. **Propose additions** — sections and examples to add to the existing file

2. **Await feedback** — the user approves or requests changes
   - **Approved** → update `.goga/usages/cooks/<name>.md`
   - **Rejected** → propose revised additions

If all external dependencies are covered by current usage files, skip this phase.

### Phase 6: Scope Estimation

**Objective:** Assess the task scale and determine whether decomposition is necessary.

1. **Assess the scale:**
   - Number of entities/types involved
   - Presence of multiple independent subsystems
   - Complexity of interactions

2. **Present the estimate to the user:**
   - Single task or multiple tasks
   - If multiple, propose a breakdown into subtasks
   - Each subtask must deliver independent value

3. **Await feedback** — the user approves or requests changes

### Phase 7: Task Persistence

**Objective:** Save the formulated task to the path printed by `goga history path -f task.md`, using the template (run `goga history ensure` first if the topic directory does not exist).

The topic directory is resolved by `goga history path` from the current git branch.

1. Read the `task-template.md` template from the current skill directory and apply its structure.

2. Save the file and present a summary to the user:
   - Task name
   - Technology stack
   - External dependency count
   - Scope (single task / breakdown)
   - Risks and constraints

---
