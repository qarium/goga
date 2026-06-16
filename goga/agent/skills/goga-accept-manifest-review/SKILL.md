---
name: goga-accept-manifest-review
description: Verify each Cell's CODEMANIFEST against the implementation
---
# goga-accept-manifest-review

## Identity

The Agent verifies each Cell's CODEMANIFEST against its implementation during acceptance: code vs requirements, requirements vs code, manifest accuracy.

## Core Principle

The Agent **compares** CODEMANIFEST with the actual implementation, **updates** the manifest as needed, and **records** any unresolvable discrepancies.

### User Interaction Rule

**Always provide response options.** When addressing the User, always offer 2–4 concrete choices.

---

## Algorithm

### Step 1. Load Context

1. Load the Acceptance Scope Report.
2. Invoke skill `goga-lang-disp` to retrieve language conventions for the target language.
3. Load the DSL specification:
   - Invoke skill `goga-cell` to understand CODEMANIFEST DSL syntax, structural rules, and semantics.
   - Invoke skill `goga-cookbook` to understand principles for working with Cell and CODEMANIFEST files.
4. Invoke skill `goga-codemanifest-base` to retrieve baseline Usages and Annotations.

### Step 2. Pre-flight Check

1. Run the linter: `goga lint`.
2. Record all errors as CRITICAL. Resolve them before proceeding.

### Step 3. Per-Cell Review

Process each Cell listed in the Acceptance Scope Report:

#### Sub-step 1. Load Data

1. Read the Cell's CODEMANIFEST.
2. Parse all entities, methods, properties, imports, usages, annotations, re-exports, and locations per the goga-cell and goga-cookbook skill definitions.
3. Enumerate all source files (exclude `.usages/`, build artifacts, and test files).
4. Read every source file at its declared `location`.
5. Verify the Facade file exists.

#### Sub-step 2. Code Analysis

**Question: Does the code satisfy the CODEMANIFEST requirements, baseline practices, and language conventions?**

1. Run the contract comparison: `goga contract <cell-path>`.

2. For each Entity, compare:
   - **Constructor Signature**: CODEMANIFEST vs implementation.
   - **Methods**: CODEMANIFEST vs implementation — per method.
   - **Properties**: CODEMANIFEST vs implementation — per property.
3. For each Routine:
   - **Signature match**: contract result — CODEMANIFEST vs implementation.
   - **Facade export**: is the Routine exported through the Facade.
4. Check Facade exposure — every Entity must be present in the Facade.
5. Check code compliance with baseline Usages and Annotations from skill `goga-codemanifest-base`.
6. Check code compliance with language conventions from skill `goga-lang-disp`.

Additional checks:
- **Location**: the file at `<cell-path>/<location>` must exist.

#### Sub-step 3. CODEMANIFEST Completeness Analysis

**Question: Is all meaningful code reflected in the CODEMANIFEST?**

For every code element absent from CODEMANIFEST, classify criticality:

**HIGH** — must be added:
- Undeclared public Entity (class with state or behavior).
- Undeclared public Routine (transformer function, factory, validator).
- Re-exported types not declared via Embedding.
- Unreported Mutations (`Object::Target`).

**MEDIUM** — must be added:
- Missing methods or properties on a declared Entity.
- Signature inaccuracies (parameters, return values, semantic labels).
- Used Imports not declared.

**LOW** — no action required:
- Private members, internal implementation details.
- Helper functions not included in the Facade.
- Stylistic annotation improvements.

Annotation quality checks:
- Each Annotation starts with a clear purpose statement.
- Every parameter is documented as `parameter_name`: description.
- Non-trivial logic includes an `Algorithm:` section.
- Constraints are described under `Requirements:`.
- No TBD, TODO, or vague wording.

#### Sub-step 4. Algorithm Comparison

For each Entity and Routine, compare Annotations against the implementation along these axes:
- **Behavior**: does the code perform what the Annotation describes.
- **Algorithm**: steps, order, conditions, branching.
- **Operational Flow**: inputs, outputs, side effects.
- **Guarantees**: post-conditions, invariants, constraints.
- **Engineering Practices**: error handling, logging, validation.

For each discrepancy:
- **CODEMANIFEST inaccurate, code correct** → update CODEMANIFEST.
- **Code incorrect, CODEMANIFEST accurate** → create a Task.
- **Both partially inaccurate** → propose edits for both sides, request User confirmation.

### Step 4. Baseline Usages and Annotations Audit

For each Cell, verify against `goga-codemanifest-base`:
1. Retrieve baseline Usages from `goga-codemanifest-base`.
2. Verify every baseline Usage appears in the CODEMANIFEST `Usages` directive.
3. Retrieve baseline Annotations from `goga-codemanifest-base`.
4. Verify every baseline Annotation appears in the CODEMANIFEST `Annotations` directive.
5. **Auto-add** any missing baseline Usages or Annotations.

### Step 5. Classify Findings

For each finding:

1. Assign a severity:
   - **CRITICAL**: Facade violation, missing implementation, CODEMANIFEST syntax error, implementation contradicts a correct manifest.
   - **WARNING**: inaccurate description, missing parameter in Annotation, stale manifest algorithm.
   - **INFO**: writing-quality improvement recommendation.

2. Propose a concrete action:
   - Analysis 1 (code fails requirements) → create a Task describing the discrepancy.
   - Analysis 2 (requirements diverge from code) → edit CODEMANIFEST.
   - Algorithm mismatch → update manifest if implementation is correct, or create a Task.

3. Request User confirmation for all CRITICAL and WARNING findings.

### Step 6. Execute Approved Actions

For each approved action:

1. **Code fails requirements** → create a Task with discrepancy details.
2. **Requirements diverge from code** → apply CODEMANIFEST edits.
3. **Manifest is stale** → update CODEMANIFEST and record the reason.
4. **Implementation is incorrect** → record CRITICAL, create a Task.

### Step 7. Validate Updates

1. Run: `goga lint`.
2. Fix any syntax errors.
3. Repeat until the linter passes with zero errors.

STOP if:
- CRITICAL violations exist in any Cell.
- Implementation contradicts manifest and manifest is correct.
- CODEMANIFEST linter errors are present.
- Facade exposure violations are detected.

---

## Output Format

Fill in every section. Empty sections are prohibited.

```md
# Manifest Review Report

## Linter Results
[Table: Cell | Linter Status | Errors (if any)]

## Analysis 1 — Code vs Requirements
[Table: Cell | Signature Match | Method Coverage | Property Coverage | Facade | Status]

## Analysis 2 — Requirements vs Code
[Table: Cell | Undocumented Entities | Description Accuracy | Annotation Quality | Status]

## Algorithm Consistency
[Per Cell: manifest algorithm vs implementation — match / discrepancy]

## Operational Flow Consistency
[Per Cell: manifest flow vs implementation — match / discrepancy]

## Guarantee Verification
[Per Cell: manifest guarantees vs implementation — preserved / violated]

## Practice Consistency
[Per Cell: manifest practices vs implementation — match / discrepancy]

## Baseline Usages/Annotations Audit
[Table: Cell | Baseline Usages present? | Baseline Annotations present?]

## Findings
[Table: Cell | Analysis | Finding | Severity (CRITICAL/WARNING/INFO) | Proposed Action]

## Applied Updates
[Table: Cell | Updated Section | Previous Value | New Value | Reason]

## Critical Discrepancies
[List of CRITICAL items. Empty if none.]

## Overall Status
[CONSISTENT / INCONSISTENT — with justification]
```
