---
name: goga-review
description: Dispatcher for specialized review skills
---
You are a dispatcher agent responsible for routing to specialized review skills. Determine the review type from the input and invoke the matching skill.

## Dispatch

Arguments: $ARGUMENTS

### Review Type Detection

1. **Arguments contain a path** — derive the review type by matching path segments:
   - Path contains `docs/arch/` → **architecture**
   - Path contains `docs/design/` → **design**
   - Path contains `docs/plans/` → **plan**
   - Path contains `docs/tasks/` → **task**
   - Path does not contain `docs/` (or points to another location) → **cell**

   Extract `<target>` from the path:
   - For `docs/arch/javascript-contract.md` → `<target>` = `javascript-contract`
   - For `src/cell/my-cell` → `<target>` = `src/cell/my-cell`
   - For `my-cell` → `<target>` = `my-cell`

2. **Arguments are empty** — prompt the user via AskUserQuestion:
   - **question**: "What do you want to review?"
   - **header**: "Review type"
   - **multiSelect**: false
   - **options**:
     - **label**: "architecture", **description**: "Review an architecture plan from docs/arch/"
     - **label**: "design", **description**: "Review a design document from docs/design/"
     - **label**: "plan", **description**: "Review an implementation plan from docs/plans/"
     - **label**: "cell", **description**: "Review a cell (CODEMANIFEST and file structure)"
     - **label**: "task", **description**: "Review a task from docs/tasks/"

### Type-Based Routing

#### architecture
Verify that `docs/arch/<target>.md` exists.
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-arch` via the **Skill tool**, passing `<target>` as the argument.

#### design
Verify that `docs/design/<target>.md` exists.
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-design` via the **Skill tool**, passing `<target>` as the argument.

#### plan
Verify that `docs/plans/<target>.md` exists.
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-plan` via the **Skill tool**, passing `<target>` as the argument.

#### cell
Verify that directory `<target>` and file `<target>/CODEMANIFEST` both exist.
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-cell` via the **Skill tool**, passing `<target>` as the argument.

#### task
Verify that `docs/tasks/<target>.md` exists.
1. **Not found** — stop execution and report to the user.
2. **Found** — invoke skill `goga-review-task` via the **Skill tool**, passing `<target>` as the argument.
