---
name: goga-review
description: Dispatcher for specialized review skills
---
You are a dispatcher agent responsible for routing to specialized review skills. Determine the review type from the input and invoke the matching skill.

## Dispatch

Arguments: $ARGUMENTS

### Review Type Detection

1. **Arguments contain a path under `.goga/history/`** — the path must match
   `.goga/history/<year>/<topic>/<kind>.md`:
   - `<year>` must be 4 digits (`\d{4}`); otherwise the path is not a valid artifact path → treat as **cell**.
   - Derive the review type by `<kind>` (the filename without `.md`):
     - `prd.md` → **prd**
     - `adr.md` → **adr**
     - `task.md` → **task**
     - `arch.md` → **architecture**
     - `design.md` → **design**
     - `plan.md` → **plan**
   - Any other filename, or a path outside `.goga/history/` → **cell**.

   Extract `<target>` (the topic):
   - For `.goga/history/2026/javascript-contract/arch.md` → `<target>` = `javascript-contract`
   - For `src/cell/my-cell` → `<target>` = `src/cell/my-cell`
   - For `my-cell` → `<target>` = `my-cell`

2. **Arguments are empty** — prompt the user via AskUserQuestion:
   - **question**: "What do you want to review?"
   - **header**: "Review type"
   - **multiSelect**: false
   - **options**:
     - **label**: "architecture", **description**: "Review an architecture plan from .goga/history/"
     - **label**: "design", **description**: "Review a design document from .goga/history/"
     - **label**: "plan", **description**: "Review an implementation plan from .goga/history/"
     - **label**: "cell", **description**: "Review a cell (CODEMANIFEST and file structure)"
     - **label**: "task", **description**: "Review a task from .goga/history/"

### Type-Based Routing

**prd** and **adr** have no dedicated review skills — there is nothing to route them to yet.

#### prd / adr
There is no review skill for this artifact kind yet.
1. Stop execution and report to the user that PRD/ADR review is not supported.

#### architecture
Verify that `.goga/history/<year>/<target>/arch.md` exists — search `.goga/history/*/<target>/arch.md` (4-digit year).
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-arch` via the **Skill tool**, passing `<target>` as the argument.

#### design
Verify that `.goga/history/<year>/<target>/design.md` exists — search `.goga/history/*/<target>/design.md` (4-digit year).
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-design` via the **Skill tool**, passing `<target>` as the argument.

#### plan
Verify that `.goga/history/<year>/<target>/plan.md` exists — search `.goga/history/*/<target>/plan.md` (4-digit year).
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-plan` via the **Skill tool**, passing `<target>` as the argument.

#### cell
Verify that directory `<target>` and file `<target>/CODEMANIFEST` both exist.
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-cell` via the **Skill tool**, passing `<target>` as the argument.

#### task
Verify that `.goga/history/<year>/<target>/task.md` exists — search `.goga/history/*/<target>/task.md` (4-digit year).
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-task` via the **Skill tool**, passing `<target>` as the argument.
