---
name: goga-review-task
description: Review a task for completeness, correctness, and consistency
---
# Task Review

## Objective

Validates a task (`.goga/history/<year>/<topic>/task.md`) for **completeness, correctness, and consistency** — ensuring the task is formulated clearly enough to proceed to architecture (`goga-brainstorm`).

You **verify** the task, **report** findings, and **fix** the task when issues are discovered (with user approval).

---

## Core Principle

**The task must be self-contained and unambiguous.** Any architect reading the task must understand what needs to be done, what constraints exist, and what criteria will be used to evaluate the result. If the wording allows ambiguity — that is a finding.

### User Interaction Rule

**Always offer response options.** When asking the user for a decision or confirmation — always provide specific options to choose from. Never ask open-ended questions without offering selectable options.

---

## Verifiable Artifact

- Task file at `.goga/history/<year>/<topic>/task.md` — a formulated task being verified for completeness and correctness

---

## Phases

### Phase 1: Load Context

1. Read the task from `.goga/history/<year>/<topic>/task.md`
2. Load the DSL specification and DSL application principles:
   - Use the **Skill tool** to invoke `goga-cell` — for understanding cell terminology and CODEMANIFEST when verifying the "Existing Architecture" section
   - Use the **Skill tool** to invoke `goga-cookbook` — for understanding cell interaction principles when verifying the correctness of affected cells description
3. Get the project schema:
   - Execute `goga schema` to get the cell hierarchy
   - Use the result to verify the task's "Existing Architecture" section
4. Read the relevant CODEMANIFESTs of the cells mentioned in the task's "Existing Architecture" section
5. Read the relevant usages (`.goga/usages/cooks/`) mentioned in the task's "External Dependencies" section

---

### Phase 2: Structure Completeness

Verify that the task contains **all required sections**:

1. **Current State** — is the current situation described
2. **Description** — is the essence of the task formulated
3. **Boundaries** — is what is included and excluded defined
4. **Acceptance Criteria** — are there specific verifiable conditions
5. **Stack** — are frameworks, libraries, and infrastructure listed
6. **External Dependencies** — is there a table with components and usage file statuses
7. **Risks and Constraints** — are known constraints documented
8. **Scope** — is the task scale estimated
9. **Existing Architecture** — are the affected cells specified

If any section is missing — record as a **Critical** finding.
If any section is present but empty or contains placeholders (TBD, TODO) — record as **High**.

---

### Phase 3: Current State Correctness

**Objective:** Ensure the "Current State" section accurately reflects the actual situation.

1. **Compare with actual architecture** — based on the project schema (Phase 1), verify:
   - If it claims something "doesn't exist" — does it really not exist in the project?
   - If it claims something "works this way" — does it match the actual CODEMANIFEST or code?
   - If specific cells are mentioned — do they actually exist?

2. **Check completeness** — is there important existing behavior that affects the task but is omitted?

If the current state doesn't match reality — record as **Critical** (factual error) or **High** (incomplete description).

---

### Phase 4: Description and Boundaries Consistency

**Objective:** Ensure that description and boundaries don't contradict each other.

1. **Description vs Boundaries:**
   - Does everything described as "needs to be done" fall into the "Included" section?
   - Is there anything in "Included" that isn't mentioned in the description?
   - Is there anything in "Excluded" that is logically necessary for implementing what's described?

2. **Description vs Acceptance Criteria:**
   - Do the acceptance criteria cover all aspects of the description?
   - Are there criteria that don't relate to the described task?
   - Are the criteria specific enough for verification (can you unambiguously answer "yes/no")?

3. **Boundaries vs Existing Architecture:**
   - If boundaries exclude certain cells — is this reflected in the architecture section?
   - If the architecture mentions affected cells — do they match the described boundaries?

If contradictions are found — record as **High**.
If acceptance criteria are not specific — record as **High**.
If there are logical gaps between sections — record as **Medium**.

---

### Phase 5: Stack and Dependencies Correctness

**Objective:** Ensure that the stack and dependencies are specified correctly and completely.

1. **Stack:**
   - Are specific versions or version ranges of libraries/frameworks specified?
   - Does the stack match the technologies actually used in the project?

2. **External Dependencies:**
   - For each dependency in the table, check the usage file status:
     - "created" — does the file `.goga/usages/cooks/<name>.md` exist?
     - "updated" — does the content match the described usage patterns?
     - "exists" — is the file content relevant to the current task?
   - Are there components in the stack not reflected in the dependencies table?

3. **Connection to description:**
   - Is the use of each stack component justified by the task?
   - Are there requirements in the description for which no corresponding tool is specified in the stack?

If a usage file is missing despite a "created" status — record as **Critical**.
If the stack doesn't cover the description's needs — record as **High**.
If a dependency lacks justification — record as **Medium**.

---

### Phase 6: Existing Architecture Correctness

**Objective:** Ensure the "Existing Architecture" section accurately describes the affected cells.

1. **Cell existence** — do all mentioned cells exist in the project schema?
2. **Integration description correctness** — is the description of how cells interact correct?
3. **Completeness** — are there cells logically affected by the task (based on description and boundaries) that are omitted?
4. **Direction of impact** — is it correctly specified which cells need to be created and which need to be modified?

If specified cells don't exist — record as **Critical**.
If the integration description is incorrect — record as **High**.
If affected cells are omitted — record as **High**.

---

### Phase 7: Risks and Constraints

**Objective:** Ensure risks are realistic and complete.

1. **Realism** — is each risk based on actual constraints rather than generic phrases?
2. **Completeness** — does the task account for:
   - Compatibility constraints (versions, platforms)?
   - Performance constraints?
   - Constraints arising from the current architecture?
   - Dependencies on external components?

If risks consist of generic phrases — record as **Medium**.
If obvious risks are omitted — record as **Medium**.

---

### Phase 8: Scope

**Objective:** Ensure the scope estimate is justified.

1. **Justification** — does the estimate match the scale of the description?
2. **Breakdown** — if a breakdown into subtasks is provided:
   - Does each subtask have standalone value?
   - Do the subtasks together cover the entire task?
   - Is there overlap between subtasks?
3. **Absence of breakdown** — if the task is marked as "single", is it truly small enough?

If the scope estimate doesn't match the description's scale — record as **Medium**.
If subtasks overlap or don't cover the task — record as **High**.

---

### Phase 9: Report and Fix Findings (Interactive)

Collect all findings from Phases 2–8 before presenting them. Sort by severity: Critical → High → Medium.

Present findings **one at a time**. For each finding:

#### Step 1. Show the finding

Present one finding with:

- **Severity** (Critical / High / Medium)
- **Area** (Structure / Current State / Description and Boundaries / Stack and Dependencies / Architecture / Risks / Scope)
- **Location** — exact reference to the task section
- **Issue** — clear description of the problem
- **Suggested fix** — specific required change, not vague advice

#### Step 2. Request user decision

Use AskUserQuestion with options:

1. **Apply suggested fix** — apply the fix to the task immediately
2. **Suggest alternative** — user describes a different fix approach
3. **Skip** — user skips the finding

#### Step 3. Apply the decision

- **Apply suggested fix**: update the task file, then re-verify that the fix doesn't introduce new issues (re-run relevant checks). Briefly report the re-verification result.
- **Skip**: record the finding as "skipped" and continue.
- **Suggest alternative**: discuss the alternative with the user, agree on a fix, apply it, re-verify.

#### Step 4. Proceed to next finding

Repeat from Step 1 for the next finding. Show a brief counter: "Finding 3 of 12".

After processing all findings, show the summary:

- **Fixed**: N findings (list by severity and area)
- **Skipped**: N findings (list by severity and area)
- **Task status**: updated / unchanged

---

## Output

- Findings summary: count of fixed / skipped by severity and area
- Updated task file (if fixes were applied)
- Verification verdict: passed / failed

---

## Final Self-Check

Before completing, verify:

1. Was the DSL specification loaded via `goga-cell` and `goga-cookbook` skills?
2. Was the current project schema loaded?
3. Was the task structure completeness checked (all 9 required sections)?
4. Was the current state correctness checked (consistency with project schema and CODEMANIFEST)?
5. Was the consistency of description, boundaries, and acceptance criteria checked?
6. Were the stack and external dependencies checked (usage file existence, justification)?
7. Was the existing architecture correctness checked (cell existence, completeness, direction of impact)?
8. Were risks and constraints checked (realism, completeness)?
9. Was the scope estimate checked (justification, subtask breakdown)?
10. Was each finding presented one at a time with a fix decision?
11. Were approved fixes applied and re-verified?
12. Was a summary of fixed/skipped findings provided?

If any answer is "no" — complete the missing verification before returning.

---
