---
name: goga-plan-by-design
description: Compile a design document into a ralphex execution plan
---
# Planning Agent: Design Document → ralphex Plan

## Purpose

Compiles a finalized **architectural decision from a design document** into a **ralphex-compatible execution plan** —
a structured markdown file that [ralphex](https://github.com/umputun/ralphex) can autonomously execute through Claude Code.
You **decompose** a finalized architectural decision into coding tasks.

---

### Phase 1: Context Loading

#### Step 1: Load DSL Specification

Use the **Skill tool** to invoke `goga-cell`.

Use for:
- Understanding DSL terminology when compiling the design document into tasks

#### Step 2: Load DSL Application Principles

Use the **Skill tool** to invoke `goga-cookbook`.

Use for:
- Understanding Entity vs Routine when compiling entities into tasks
- Principles for working with `.usages/` when planning tasks for creating/updating usage files

#### Step 3: Load Language Implementation Rules

Use the **Skill tool** to invoke `goga-lang-disp`.

The language skill defines implementation conventions: cell structure, facade, signature rules, **naming**.
Examples in other skills (DSL, cookbook, templates) may use naming from one language
(e.g., snake_case) while the target language requires another (e.g., PascalCase) — the language skill
contains authoritative rules for the target language. Apply them when compiling the plan.

#### Step 4: Load Plan Template

Read the file `output-template.md` from the current skill.

Use for:
- Plan structure (sections, headings, checkboxes)
- Templates for three task types (infrastructure, TDD coding, integration tests)
- Format for "Validation Commands" and "Completion Criteria" sections

#### Step 5: Load Project Conventions

Read the file `conventions.md` from the current skill.

Use for:
- Implementation rules (internal cell structure, public surface, naming)
- Traceability rules and contract-to-test mapping
- Test classification (contract, logic, integration)

#### Step 6: Load Design Document

Read the file from the path printed by `goga history path -f design.md`.
If the design document does not exist — stop and ask the user to run `/goga:design` first.

---

### Phase 2: Compile Design Document into Plan

Goal: decompose the architectural decision from the design document into ralphex tasks.

#### Step 1: Extract Data from Design Document

Extract from the design document:

- **Contract changes** → determine task scope (which entities are new/modified/deleted)
- **Applied fixes** → context for tasks (what was fixed and why)
- **Entity interactions** → transfer diagrams and data flows verbatim into task context
- **Code Stack Trace** → include verified logical chains into task context
- **Algorithm Design** → algorithm steps become implementation checkboxes in tasks
- **Cross-cutting concerns** → distribute across relevant tasks
- **Usages Analysis** → include usages context in tasks where they are used
- **.usages/ updates** → tasks for creating/updating usage files
- **Test Stack Trace** → test scenarios become instructions in task checkboxes
- **Additional instructions** → include in task context

**Critical**: traces, diagrams, and test scenarios from the design document contain verified knowledge.
Transfer them verbatim into relevant task context, do not summarize.

#### Step 2: Compile into ralphex Tasks

For each entity from the design document, create tasks following the rules:
- DSL → plan compilation table (see "DSL Compilation Rules" section)
- Cell boundaries (see "Boundaries" section)
- ralphex format requirements (see "Ralphex Integration" section)
- task ordering principles (see "Task Ordering Principles" in "DSL Compilation Rules" section)
- TDD workflow (see "Test Planning Rules" section)
- task formation rules (see "Execution Planning Rules": task structure, requirements, checkbox granularity, validation command placement, anti-patterns)
- templates from `output-template.md` (loaded in Step 4)
- project conventions from `conventions.md` (loaded in Step 5)

Use the `goga-cell` skill for correct interpretation of DSL elements during compilation.

#### Step 3: Save the Plan

Write the plan to the path printed by `goga history path -f plan.md`, using the template from `output-template.md`.

The topic is the current one in the history tree; name it to reflect the plan's scope, not the Cell name.
Run `goga history ensure` first if the topic directory does not exist.

---

### Phase 3: Plan Verification

Before completion, verify:

1. Is every entity from the contract changes in the design document covered by a task?
2. Is every test scenario from the design document included in task test instructions?
3. Is every Usages Analysis entry from the design document included in at least one task?
4. Does every planned `.usages/` entry from the design document have a creation task or step?
5. Are interaction diagrams and traces transferred verbatim, not summarized?
6. Do all coding tasks follow the TDD workflow?
7. Is the ralphex format correct (`### Task N:` headings, `- [ ]` checkboxes)?
8. Is every task atomic and self-contained?
9. Are validation commands defined?
10. Are `CODEMANIFEST` files marked as read-only?

If any answer is "no" — rework the plan.

---

### Phase 4: Present Summary

After saving the plan, output a brief summary for the user:

- **Task table**: numbered list of all tasks with type (infrastructure / TDD coding / integration tests) and one-line description
- **Key design decisions**: maximum 3-5 points
- **Total test count**: how many test scenarios are planned

Do NOT repeat the full plan contents. Keep it to a minimum of lines.

---

## Ralphex Integration

### Plan Format Requirements
The plan **must** follow this structure for ralphex compatibility:
- `### Task N: <title>` headings define individual tasks
- `- [ ]` checkboxes mark incomplete items within each task
- `- [x]` checkboxes mark completed items (none initially)
- `## Validation Commands` section contains commands for verifying correctness
- Only ONE task is executed per ralphex iteration

### Designing Tasks for AI Execution
Each task must be:
- **Atomic** — executable by an AI agent in a single Claude Code session
- **Self-contained** — includes all context needed for implementation without reading other tasks
- **Ordered** — within a Cell: infrastructure before entities; simple before complex; each task follows the TDD workflow
- **Verifiable** — has clear completion criteria and validation commands

### ralphex Execution Protocol
Steps 1–7 must be present as checkboxes in each coding task of the plan — the protocol is self-enforcing through the plan structure.
When ralphex executes a coding task, the AI agent follows these checkboxes:
1. **STEP 0 (DECLARATION)** — declare which task is being worked on
2. **STEP 1 (CONTRACT TESTS)** — write contract tests for the entities/interfaces in this task (they will fail — this is expected)
3. **STEP 2 (IMPLEMENTATION)** — write the code for this one task
4. **STEP 3 (INTERFACE VERIFICATION)** — run the contract tests from step 1 to verify implemented interfaces match the contract
5. **STEP 4 (LOGIC TESTS)** — write tests verifying behavioral logic (positive, negative, edge cases)
6. **STEP 5 (DEBUGGING)** — run all tests and fix implementation code until all tests pass
7. **STEP 6 (CONTRACT RE-VERIFICATION)** — verify that all contract obligations are still met (facade, API shape, behavior)
8. **STEP 7 (LINT)** — run linter, fix formatting and decompose if necessary
9. **STEP 8 (COMPLETION)** — mark checkboxes as completed
10. **→ REVIEW → APPROVAL → NEXT TASK** — after completion, ralphex submits the task for code review; review must be approved before moving to the next task

---

## Boundaries

### Allowed Within the Current Cell
You may plan:
- additional internal files and modules
- helper functions and classes
- private abstractions
- internal restructuring
- decomposition of implementation into smaller internal units

### Prohibited
You must not plan:
- creating new Cells
- defining new interfaces at the Cell level outside the current one
- expanding system boundaries beyond the current Cell
- replacing contract entities with internally-only-accessible abstractions
- violating facade accessibility requirements
- ignoring `location`
- modifying `CODEMANIFEST` files — they are **read-only** for the implementation agent

---

## DSL Compilation Rules

Use the `goga-cell` skill to interpret DSL elements during compilation.
Follow the project conventions from `conventions.md`.

### Compilation Mapping

| DSL Element                  | Result in Plan                                                          |
|------------------------------|-------------------------------------------------------------------------|
| `Types Import`               | Context section — internal types grouped under a single `From`          |
| `Usages Import`              | Context section — imported practice from another cell's `.usages/`      |
| `Usages`                     | Context section with implementation guidance                            |
| `Annotations`                | Contextual hints embedded into task descriptions                        |
| `->Re-exports`               | Task: ensure importability from the facade                              |
| `Entity` with `properties`   | Task: create entity in `location`, implement properties                 |
| `Entity` with `methods`      | Task: implement methods in `location` with behavior from descriptions   |
| `Standalone function`        | Task: implement function in `location`                                  |
| `Type::` mutation            | Task: implement interface mutation mechanism                            |
| Method/property descriptions | Reflected in task implementation instructions                           |

### Task Ordering Principles
Tasks are ordered **within a Cell**. Each Cell is completed before moving to the next.

Within a single Cell:
1. **Infrastructure tasks** — Cell structure, facade, re-exports
2. **Entity skeleton tasks** — creating classes/functions in correct `location`s
3. **Property implementation tasks** — implementing facade-visible properties
4. **Method implementation tasks** — implementing methods with described behavior
5. **Interface mutation tasks** — implementing `Type::` mutations
6. **Integration test tasks** — cross-entity, edge cases

When the plan spans multiple Cells:
- Leaf Cells first, then parent Cells
- Respect dependency order: if A imports from B, complete B first

Entities with the same `location` are grouped into one task.

### Descriptions Are Mandatory
Descriptions attached to properties, methods, and functions define semantics, behavioral expectations,
constraints, and implementation requirements. They must appear in task instructions.

### Imports — Internal Dependencies and Tracked Practice References
Imports define:
1. **Contract dependencies** — types from other `CODEMANIFEST` via `Types:` + `From:`
2. **Practice dependencies** — usages from other cells' `.usages/` via `Usages:` + `From:`
External library types are described in `Usages`, not in `Imports`.

### Usages — Documentation for Cell API Consumers
`Usages` provides context: external library types, specifications, conventions.
Include Usages context in the plan from the design document (Usages Analysis section).

**Two-level usages model**:
- **Global** — project root `.goga/usages/`
- **Local** — `.usages/` inside the cell
- **Imported** — from other cells via `Imports` → `Usages`

### Re-exports — Facade Obligations
Re-export blocks (`->Name: {}`) define names that must be available on the facade.
Every re-exported name must be importable.

### Annotations — Prescriptive Instructions
`annotations` at the file, entity, or function level provide instructions for the implementation agent.
Embed them as requirements in task descriptions.

---

## Execution Planning Rules

### Task Structure

Task templates are defined in `output-template.md`. Follow them when forming each task in the plan.

There are three task types:
- **Infrastructure** — Cell structure, facade, re-exports (code → verification → lint)
- **TDD Coding** — entity implementation with the ralphex protocol (steps 0–8 from "ralphex Execution Protocol" section)
- **Integration Tests** — cross-entity scenarios (separate tasks)

### Task Requirements
Each task must:
- have a clear, descriptive title
- include enough context for implementation without reading other tasks, including:
  - which contract entities it covers
  - which `location` files are involved
  - relevant imports and usages
  - behavioral requirements from descriptions
  - annotations as prescriptive instructions for the implementation agent
- list implementation steps as `- [ ]` checkboxes
- explicitly specify target files
- identify covered contract entities
- include at least one validation checkpoint
- be executable in a single Claude Code session

### Checkbox Granularity
Each `- [ ]` checkbox must be:
- a specific, verifiable action (e.g., "Create implementation file for `location`", "Implement method `load()` returning a collection of items")
- verifiable by running a command or checking file existence
- not a vague goal (avoid "Implement service" without specifics)

### Validation Command Placement
- Each task includes at least one inline validation step (checkbox with a verification command).
- The `## Validation Commands` section at the plan level lists global commands.
- Task-level commands verify the outcome of a specific task.
- Plan-level commands verify overall contract compliance.

### Anti-patterns
- Vague tasks like "implement X" without specific steps
- Tasks covering multiple unrelated contract entities
- Tasks without validation commands
- Tasks assuming context from previous tasks without restating it
- Tasks too large for a single AI session
- Tasks that propose modifying `CODEMANIFEST` files
- Coding tasks without contract tests (violates TDD)
- Coding tasks without a debugging step

---

## Test Planning Rules

### Tests Within Coding Tasks
1. **Contract tests** — written FIRST; verify facade, API shape, signatures
2. **Logic tests** — written AFTER implementation; verify behavior

Both types are embedded in coding task checkboxes.

### Integration Test Tasks
Create for cross-entity scenarios spanning multiple entities or multiple Cells.

### Test Categories
- **Contract** — facade and API shape (mandatory, embedded in coding tasks)
- **Logic** — behavioral requirements (mandatory, embedded in coding tasks)
- **Integration** — cross-entity interactions (separate tasks, when appropriate)

---

## Validation Commands

The plan must include a `## Validation Commands` section.
Specific commands are defined based on project specifications and practices.

```markdown
## Validation Commands
- <run all tests command>: Run all tests
- <lint command>: Lint check
- <facade check command>: Facade accessibility
```

---
