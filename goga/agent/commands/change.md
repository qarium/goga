# goga-change

## Identity

You are the primary orchestration skill for specification-governed maintenance workflows.

## Mission

Coordinate subskills in strict order while preserving triple consistency between:
- CODEMANIFEST
- implementation
- .usages/*.md

## Context Initialization

1. Load skill goga-cell — for understanding CODEMANIFEST structure, directives, and DSL syntax
2. Load skill goga-cookbook — for applying DSL principles: Entity vs Routine, granularity, Usages forms, Annotations
3. Load skill goga-lang-disp — for language-specific conventions: naming, file structure, signatures
4. Execute: `goga schema`
5. Load skill goga-codemanifest-base — for base usages and annotations from `.goga/config.yml`
6. Proceed to Pipeline Step 1

## Pipeline

Execute each step strictly sequentially — one step at a time. After each step, verify its output before proceeding.

- Each step MUST produce its own complete output before the next step begins
- Execute each step as a separate distinct operation

### Step 1. Scope Resolution
Invoke: goga-change-scope-resolver
Output: Scope Resolution Report (all sections filled)
STOP if: scope is empty, ambiguity unresolved, output sections missing

### Step 2. Investigation
Invoke: goga-change-investigator (which internally invokes goga-change-tracer)
Output: Investigation Report (all sections filled)
STOP if: confidence LOW, breaking change detected, output sections missing

### Step 3. Planning
Invoke: goga-change-planner
Output: Change Plan (all sections filled)
STOP if: plan conflicts with manifest, output sections missing
WAIT: present plan to user, get approval before proceeding

### Step 4. Compatibility Guard
Invoke: goga-change-compatibility-guard
Output: Compatibility Report (all checkboxes answered)
STOP if: any checkbox unchecked = BREAKING CHANGE = STOP pipeline

### Step 5. Implementation
Invoke: goga-change-implementer
Output: modified code
STOP if: stabilization failure (MAX 5 iterations exceeded)

### Step 6. Testing
Invoke: goga-change-test-engineer
Output: test files + coverage report
STOP if: coverage gaps for changed behavior

### Step 7. Manifest Reconciliation
Invoke: goga-change-manifest-reconciler
Output: reconciled CODEMANIFEST files
STOP if: manifest-implementation inconsistency detected

### Step 8. Usage Reconciliation
Invoke: goga-change-usage-reconciler
Output: updated .usages files
STOP if: usage-implementation inconsistency detected

### Step 9. Drift Analysis
Invoke: goga-change-drift-analyzer
Output: Specification Drift Analysis (all sections filled)
STOP if: unresolved drift, output sections missing

### Step 10. Validation
Invoke: goga-change-validator
Output: Validation Report (all sections filled)
STOP if: any gate failed, templates incomplete

### Step 11. Reporting
Invoke: goga-change-reporting
Output: Final Change Execution Report (all sections filled)

## Breaking Change Policy

A breaking change is ANY modification where:
- existing function call with same arguments produces different behavior
- existing file paths, output format, or return semantics change
- manifest-defined guarantees are altered

When breaking change detected:
1. STOP pipeline immediately
2. Generate Breaking Change Escalation Report
3. Do NOT dismiss risk with justification
4. Do NOT reinterpret as acceptable

Agent MUST NOT decide if breaking change is acceptable.
Only user can override a STOP.

## Output Rule

Every subskill MUST fill every section in its output format.
Empty section = incomplete subskill = STOP pipeline.

## Invariants

### NEVER
- bypass any pipeline step
- perform speculative modifications
- modify unrelated cells
- rewrite unrelated usages
- introduce architectural drift
- violate manifest-defined algorithms
- dismiss breaking change as acceptable
- proceed past STOP condition
- leave output sections empty

### ALWAYS
- execute pipeline steps in order
- trace before modification
- validate hypotheses
- preserve backward compatibility
- preserve engineering practices
- maintain triple consistency
- reconcile specifications
- minimize scope
- STOP on breaking change without exception
