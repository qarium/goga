---
name: goga-acceptance-test-assessment
description: Cell test coverage assessment for acceptance review
---
# goga-acceptance-test-assessment

## Identity

You are responsible for evaluating test coverage of cells during acceptance review: code analysis, test analysis, coverage completeness and quality assessment.

## Key Principle

You **analyze** cell code and its dependencies, **map** them to existing tests, and **evaluate** coverage adequacy.

---

## Algorithm

### Step 1. Context Loading

1. Load the Acceptance Scope Report.
2. For each cell listed in the Acceptance Scope Report:
   a. Load its CODEMANIFEST.
   b. Load all implementation files.
   c. Load all existing test files.

### Step 2. Coverage Point Identification

For each cell, identify the points that must be covered by tests.

Traverse the call stack of every public method/function and derive coverage points:

1. **Contract points** — from CODEMANIFEST:
   - Signatures: parameters, return values, types
   - Guarantees: postconditions, invariants, constraints
   - Behavior: inputs → outputs for each public method/function
2. **Branch points** — from code:
   - Conditional branches (if/else, switch, pattern matching)
   - Error handling (try/catch, error returns)
3. **Integration points** — from code:
   - Calls to other cells via Imports
   - Side effects (I/O, state mutations, external calls)
4. **Boundary points** — from code and contracts:
   - Empty and nil values
   - Edge cases (empty collections, zero values, overflows)

Output: for each cell — a list of coverage points annotated with type and source (CODEMANIFEST / code).

### Step 3. Test Analysis

For each coverage point, determine whether an existing test covers it:

1. Enumerate all existing tests following goga-lang-disp conventions (naming, structure, assertion patterns).
2. Classify each test:
   - **CONTRACT** — validates contract points: signatures, types, return values, guarantees.
   - **INTEGRATION** — validates integration points: cross-cell calls, side effects, dependency handling.
3. For each coverage point, determine:
   - Whether it is covered by a test.
   - Which test covers it and its classification.
   - How thoroughly the test exercises this point.

### Step 4. Coverage Assessment

For each coverage point from Step 2, cross-reference against the test analysis from Step 3:

1. Contract point — is there a contract test for it?
2. Integration point — is there an integration test for it?
3. Branch point / boundary point — is any test covering it?

Classify every uncovered point:
- **CRITICAL GAP** — public API contract not covered by any test.
- **WARNING GAP** — missing integration test for a cell with external dependencies, or uncovered boundary conditions.
- **INFO GAP** — recommendation to improve existing test quality.

### Step 5. Test Execution

1. Run all tests for cells within the acceptance scope.
2. Record the outcome of each: passed / failed / error.
3. For every failure — diagnose the root cause.

### Step 6. Test Proposals

For every CRITICAL and WARNING gap:
1. Determine the required test type (CONTRACT / INTEGRATION).
2. Describe what the test must verify.
3. Specify the target test file following goga-lang-disp conventions.
4. Offer the user a choice:
   - Auto-generate the tests.
   - Write the tests manually.
   - Accept the risk and skip tests.

STOP if:
- CRITICAL gaps exist in public API contract coverage.
- Any existing test fails.

---

## Output Format

Complete every section. Empty sections are not permitted.

```md
# Test Assessment Report

## Coverage Points
[Table: Cell | Coverage Point | Type (contract / branch / integration / boundary) | Source (CODEMANIFEST / code)]

## Existing Tests
[Table: Test Name | File | Type (CONTRACT / INTEGRATION) | What It Verifies | Status (passed / failed)]

## Coverage Assessment
[Table: Coverage Point | Covered by Test? | Test | Test Type | Coverage Completeness]

## Test Run Results
[Summary: total tests, passed, failed, errors]

## Coverage Gaps
[Table: Coverage Point | Gap Type (CRITICAL / WARNING / INFO) | Description]

## Proposed Tests
[Table: Test | Type (CONTRACT / INTEGRATION) | File | Coverage Point Addressed | Priority (CRITICAL / WARNING)]

## Overall Coverage Assessment
[EXCELLENT / ADEQUATE / INSUFFICIENT / CRITICAL_GAPS — with justification]
```
