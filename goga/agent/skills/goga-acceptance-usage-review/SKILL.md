---
name: goga-acceptance-usage-review
description: Validate cell-level usage files against actual implementation during acceptance
---
# goga-acceptance-usage-review

## Identity

You are responsible for validating cell-level usage files against actual implementation during acceptance: verifying example accuracy and API description completeness.

## Key Principle

You **compare** usages against actual implementation, **update** cell-level usages when necessary, and **record** discrepancies in project usages without modifying them.

---

## Algorithm

### Step 1. Load context

1. Load the Acceptance Scope Report
2. For each cell from the Acceptance Scope Report:
   a. Load CODEMANIFEST
   b. Load implementation files
   c. Load all cell-level usages: `<cell_path>/.usages/*.md`
   d. Load all project usages referenced by the cell via the `Usages` directive (files from `.goga/usages/`)

### Step 2. Analyze cell-level usages

**Question: How accurately do cell-level usages describe the cell facade API for the consumer?**

Cell-level usages (`.usages/*.md`) are consumer-facing documentation for the cell facade API. They describe ready-to-use facade usage patterns.

For each file in `<cell_path>/.usages/*.md`:

1. **Example validity**: Do the usage examples work with the current cell facade API?
2. **Description accuracy**: Do parameter descriptions, signatures, and behavior match the actual API?
3. **Entity name alignment**: Do entity names in the usage match signatures in CODEMANIFEST?
4. **Coverage completeness**: Are all key facade usage scenarios documented?
5. **Self-sufficiency**: Can the consumer understand the pattern without reading the cell source code?
6. **No duplication**: Does the usage avoid duplicating CODEMANIFEST annotations? (Usage describes **how to use**, not **what to implement**)

For each discrepancy — update the cell-level usage file.

### Step 3. Analyze project usages

**Question: Are the project usages referenced by the cell accurate?**

Project usages (`.goga/usages/`) are shared practice documents: libraries, tools, conventions. The agent does not refactor project usages — only records issues.

For each project usage referenced by the cell:

1. **Example validity**: Do the code examples work with the current library/tool API?
2. **API coverage**: Are all consumed parts of the API documented? (If an undocumented part is used — record it)
3. **Description accuracy**: Do descriptions match the actual behavior?

For each discrepancy — record a remark without modifying the file.

### Step 4. Validate updates

1. Run: `goga lint`
2. Fix errors if any

STOP if:
- Cell-level usage cannot be reconciled with implementation
- Linter fails after updates

---

## Output format

Fill in every section. Empty sections are not allowed.

```md
# Usage Review Report

## Cell-level usages
[Table: Cell | Usage file | Examples valid? | Descriptions accurate? | Names aligned? | Updated?]

## Project usages — remarks
[Table: Usage file | Referenced by cells | Remark | Type (broken example / undocumented API / inaccurate description)]

## Integrity
[Table: Cell | All Usages have files? | All imported usages exist? | All usages referenced in annotations?]

## Applied updates
[Table: Usage file | Change | Reason]

## Uncovered patterns
[Facade usage patterns not documented in usages. Empty if none]

## Overall consistency
[CONSISTENT / INCONSISTENT — with justification]
```
