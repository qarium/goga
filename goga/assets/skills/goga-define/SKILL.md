---
name: goga-define
description: Orchestrate the product definition pipeline and generate the PRD
---

# goga-define

## Purpose

Orchestrate the product definition workflow and generate a complete PRD.

The orchestrator owns the workflow, not the product decisions.

It must keep the execution linear, delegate product work to specialized subskills, maintain the shared product context within the current agent session, detect conflicts, invoke the resolver when necessary, and finally generate the PRD.

---

## Core Principle

The orchestrator is intentionally thin.

It must not perform product analysis itself when a specialized subskill exists for the task.

Its responsibilities are:

1. initialize the product context;
2. create and execute the workflow;
3. pass the required context to each subskill;
4. collect produced decisions;
5. detect conflicts;
6. invoke `goga-define-resolve` when conflicts occur;
7. update the shared context after resolution;
8. continue the linear pipeline;
9. generate the final PRD;
10. save it to the required location.

---

## Shared Context

Maintain the product definition as an in-session context.

Do not create a separate database, persistent state store, or external context file.

Use a simple structure:

```yaml
context:
  product: null
  input: null
  problem: null
  users: null
  goals: null
  user_experience: null
  requirements: null
  constraints: null
  scope: null
  success_criteria: null
  conflicts: []
```

This context is the source of truth for the current execution.

Subskills consume values from this context and produce new values.

Do not add IDs, metadata, timestamps, references, or other information that is not required for product reasoning.

---

## Subskill Contracts

Each subskill declares what it consumes and produces.

Example:

```yaml
consume:
  - product
  - problem
  - users

produce:
  - goals
```

The orchestrator must respect these contracts.

Do not pass arbitrary context when the subskill does not require it.

Do not ask a subskill to produce information outside its declared responsibility.

---

## Workflow

Execute the following pipeline in order:

```text
1. goga-define-project
2. goga-define-problem
3. goga-define-users
4. goga-define-goals
5. goga-define-experience
6. goga-define-requirements
7. goga-define-constraints
8. goga-define-scope
9. goga-define-success
10. goga-define-challenge
11. goga-define-prd
```

`goga-define-resolve` is not part of the normal pipeline.

It is invoked only when a conflict is reported.

---

## Initialize Context

Before starting the pipeline:

1. Obtain the user's product request.
2. Initialize:

```yaml
context:
  product: null
  input: <user request>
```

3. Execute `goga-define-project` as the first pipeline stage.
4. Store its `product` result in `context`.

`goga-define-project` is responsible for obtaining and interpreting the current project context.

Do not attempt to solve the problem during initialization.

---

## Execute a Subskill

For every subskill:

1. Read its `consume` contract.
2. Provide only the required values from `context`.
3. Execute the subskill.
4. Store its `produce` result in `context`.
5. Inspect the result for conflicts.

The first stage, `goga-define-project`, is responsible for populating `context.product` from the current project. Subsequent stages consume that product context.

The orchestrator must not reinterpret or rewrite a valid subskill result.

---

## Conflict Handling

Any subskill may report a conflict.

When a conflict is detected:

```text
Current pipeline step
        ↓
Conflict
        ↓
goga-define-resolve
        ↓
Updated context
        ↓
Re-check consistency
        ↓
Continue pipeline
```

The resolver receives the complete relevant context, not only the local section where the conflict was found.

---

## Resolver Rules

When invoking `goga-define-resolve`:

1. Pass the complete current product context.
2. Include all detected conflicts.
3. Allow the resolver to reconsider decisions across the entire context.
4. Apply the resolver's updated decisions to `context`.
5. Clear resolved conflicts.
6. Verify that the context is internally consistent.
7. Resume the linear pipeline.

Do not restart the entire pipeline automatically.

Continue from the point where the conflict was detected unless the resolver explicitly changed an earlier decision that invalidates downstream results.

If an earlier decision was changed, re-run the earliest affected subskill and continue forward from there.

---

## Stable Linear Workflow

Do not turn the pipeline into an autonomous graph.

Do not repeatedly call subskills to "see if something changed."

The normal execution remains strictly linear.

The only exception is explicit conflict resolution.

Example:

```text
problem
  ↓
users
  ↓
goals
  ↓
experience
  ↓
requirements
  ↓
constraints
  ↓
scope
  ↓
success
  ↓
challenge
```

If `challenge` reports a conflict:

```text
challenge
  ↓
resolver
  ↓
affected stage
  ↓
continue forward
```

Do not introduce iterative optimization loops.

---

## Reprocessing After Resolution

If the resolver changes a decision produced by an earlier stage, determine the earliest stage affected by that change.

For example:

```text
resolver changes goals
        ↓
experience is stale
        ↓
requirements are stale
        ↓
constraints may be stale
        ↓
scope may be stale
        ↓
success criteria may be stale
```

Re-run only the necessary downstream stages in their normal order.

Never retain downstream decisions that depend on an invalidated upstream decision.

---

## Task List

Maintain a simple internal task list for workflow control.

Example:

```yaml
tasks:
  - goga-define-problem
  - goga-define-users
  - goga-define-goals
  - goga-define-experience
  - goga-define-requirements
  - goga-define-constraints
  - goga-define-scope
  - goga-define-success
  - goga-define-challenge
  - goga-define-prd
```

The task list is execution state only.

Do not expose it as part of the PRD.

Do not persist it outside the current session.

---

## User Interaction

The orchestrator does not conduct the product interview.

Each subskill owns the product decisions within its domain and is responsible for interviewing the user when those decisions cannot be derived from the existing context.

When a subskill asks a product question:

1. surface the question to the user;
2. receive the answer;
3. provide the answer back to the same subskill;
4. allow the subskill to continue its decision process;
5. store the final produced result only after the subskill has completed its interview.

Do not reinterpret the user's answer.

Do not answer a subskill's question on behalf of the user.

Do not allow a subskill to silently replace an unresolved product decision with an assumption.

---

## Challenge and Final Validation

`goga-define-challenge` is the final product-definition validation step before PRD generation.

It must receive the complete context.

If it returns:

```yaml
conflicts: []
```

continue to `goga-define-prd`.

If it returns conflicts:

1. invoke `goga-define-resolve`;
2. apply the resolution;
3. re-run the earliest affected stage;
4. continue the linear pipeline;
5. invoke `goga-define-challenge` again before generating the PRD.

Never generate a PRD while unresolved conflicts remain.

---

## PRD Generation

Once the product definition is validated:

1. invoke `goga-define-prd`;
2. provide the complete validated context;
3. receive the final Markdown document;
4. save it at the path printed by `goga history path -f prd.md`
   (run `goga history ensure` first if the topic directory does not exist).

Do not overwrite an unrelated existing PRD.

If a PRD with the same topic already exists, handle the collision explicitly rather than silently replacing unrelated work.

---

## Final Validation

Before saving the PRD, verify:

- all required sections are present;
- no unresolved conflicts remain;
- the PRD represents the current context;
- no technical implementation has been invented;
- no new product decision was introduced during generation;
- scope is preserved;
- success criteria are preserved.

The orchestrator must not edit the PRD to fix product issues.

If the generated PRD is inconsistent with the context, return the issue to the appropriate stage.

---

## Failure Handling

If a subskill fails to produce its declared output:

- do not fabricate the result;
- do not silently skip the stage;
- determine whether the failure can be retried safely;
- otherwise stop the workflow and report the failed stage.

If a subskill reports that a product decision requires user input, pause the workflow and return control to that subskill after receiving the user's answer.

The orchestrator must not formulate or resolve the decision itself.

---

## Output

The primary output of `goga-define` is one Markdown file saved at the path
printed by `goga history path -f prd.md`.

The orchestrator should provide a concise completion message containing:

- the PRD path;
- a short summary of what was defined.

Do not expose the internal task list, shared context, or orchestration mechanics unless explicitly requested.
