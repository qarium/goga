---
name: goga-cookbook
description: Principles for applying DSL specification in cell and CODEMANIFEST design
---
# Goga Cookbook

## Purpose

Provides principles for applying DSL specification constructs when designing cells and CODEMANIFEST files. Defines how and when to apply DSL constructs.

This skill is called from other skills to obtain DSL design context.

## Behavior

Apply principles within the context of the calling skill. Do not reproduce or summarize the content — use it to make design decisions for CODEMANIFEST files and cells.

---

# Principles for Applying DSL Specification in Cell and CODEMANIFEST Design

The DSL specification defines what may or must appear in a cell and a CODEMANIFEST file. This document defines how and when to apply those constructs.

## Cell

### When to create a cell

Create a cell when you identify a distinct responsibility domain with a well-defined API boundary.
Enforce the principle: **one responsibility zone — one cell**.

A separate cell is warranted when **at least one** of the following holds:

- The logic can be decoupled from other system components
- The logic owns a data model distinct from other system components
- The functionality must be reused across multiple areas of the project
- The purpose can be stated in a single phrase without "and"

### Design order

Design cells bottom-up — from leaves to root. If cell A depends on cell B (via Imports), design B first.
A cell with no dependencies is designed first.

**Rationale:** The CODEMANIFEST of a dependency cell defines the types and practices that dependent cells import. You cannot correctly describe Imports without knowing exactly what the dependency provides.

### Granularity

A cell must be large enough to function as an independent unit, yet small enough to describe its contract without losing focus.

**Too fine** — one cell per function. When multiple types are always used together and have no independent meaning, they belong in the same cell.

**Too coarse** — a cell covers heterogeneous functionality. If describing the cell's purpose requires "and", consider splitting it into multiple cells.

### Usage file directories — two levels

Practices reside at two levels:

**Project-level `.goga/usages/`** (project root) — shared practices not bound to any specific cell: libraries, tools, conventions, standards. Available to every cell in the project. Referenced via path in the `Usages` directive of CODEMANIFEST.

**Cell-level `<cell_path>/.usages/`** (inside a cell) — practices for consumers of a specific cell's API: how to use the cell facade, which patterns to apply. Consumers reference them through `Imports` pointing to the provider cell.

Placement rules:
- If the practice describes a library, tool, or project-wide convention → project-level `.goga/usages/`
- If the practice describes how to consume a specific cell's API → cell-level `<cell_path>/.usages/`

### Writing usage files inside <cell_path>/.usages/

Create or update a `usage.md` file inside `<cell_path>/.usages/` when creating or updating CODEMANIFEST files, or when an external consumer requires guidance on working with the cell's API.

Follow these guidelines when writing or updating practice files in `<cell_path>/.usages/`:

**Purpose:**

Files in `<cell_path>/.usages/` are documentation **for the consumer** of the cell's API. They describe how to work with the cell facade — not requirements imposed on the cell itself.

**Content guidelines:**
- Design the CODEMANIFEST file first, then write the usage file in the `<cell_path>/.usages/` directory
- Open each file with a clear domain statement — which area the usage covers and its target audience
- Describe **ready-to-use patterns** — concrete API call scenarios with code examples
- Include typical usage examples — a minimal working example for each key scenario
- When a cell exposes a complex API with multiple entry points, group examples by functional domain into separate files within `<cell_path>/.usages/`
- When referencing contract types, use names matching the signatures in `CODEMANIFEST` so the consumer can locate the entity unambiguously
- Document side effects, preconditions, and constraints relevant to the consumer but not part of the contract itself

**Quality guidelines:**

- One file in `<cell_path>/.usages/` — one functional domain. Do not mix unrelated scenarios in a single file
- File names must be concise and descriptive of the content
- When connecting a practice via the `Usages` directive in `CODEMANIFEST`, the key must match the filename (without extension)
- Practices must be self-contained — consumers must understand the pattern without reading the cell's source code
- Practices must not reference other practices — all necessary context resides within the practice itself. Cross-references introduce implicit dependencies and break isolation
- Practices must not duplicate annotations from `CODEMANIFEST` — they describe **how to use**, not **what to implement**
- Practices do not impose contractual obligations on the cell — they remain documentation-level artifacts

## CODEMANIFEST File

### Design order

1. **Header** — define Imports, Usages, Annotations. This establishes the context in which the contract operates
2. **Body** — declare Entity, Routine. With context already set, types leverage available practices and imports
3. **Footer** — record Author, CreatedAt, Description

### Header

#### Imports — when to import

Import **Types** from another cell when:
- The current contract requires a type defined in another cell (in a signature, argument, or return value)
- You need to mutate or embed a type from another cell

Import **Usages** from another cell when:
- You need to reference a practice from another cell within annotations

#### Usages directive in the CODEMANIFEST header — when to declare a practice

Declare Usages when:
- An external library or tool exists that the agent must account for during implementation
- A pattern or convention applies to the contract's types
- A data structure or format recurs across multiple locations

**Three connection forms** — choose based on the situation:

**File** — path to an md file in `.goga/usages/`, relative to the project root:
- The practice is extensive and would clutter CODEMANIFEST if written inline
- The practice is reused across multiple cells — the file lives in project-level `.goga/usages/` and is referenced by path
- The practice evolves independently from the contract — it can be updated without modifying CODEMANIFEST
- Examples: design pattern descriptions, database conventions, library instructions

**Inline** — text directly in CODEMANIFEST:
- The practice is short — a few sentences or a single paragraph
- The practice is specific to this cell and has no meaning outside its context
- Creating a separate file would be overkill
- Example: "Use immutability for all return values"

**URL** — link to an external resource:
- The practice is external documentation with no value in duplicating (library docs, RFCs, standards)
- The practice is maintained by a third-party source and kept current there

**Recommendations:**
- When a practice imported via `Imports` may conflict by name with a local practice, use an alias in `Imports` (`practice_name AS alias`) rather than renaming the key in `Usages`
- Every connected practice must be referenced in at least one annotation — global, type-level, method-level, or property-level

#### Annotations

**Why** write annotations:
- Implementation requirements — what the agent must do when writing code
- Algorithms — step-by-step instructions for code behavior
- Constraints — what the agent must not do
- Architectural expectations — which structure or approach to use
- Practice application hints — which practice to apply and how
- **Annotations are the sole mechanism for binding a practice to a contract.** A practice connected via Usages or Imports applies only when an annotation references it. Without an annotation, the practice is connected but not applied.

**When** to write annotations:
Global (in the document header):
- Requirements apply to all types in the cell (e.g., a library, error style, logging)
- You need to prioritize between conflicting practices from Usages

At the type level:
- Defining responsibility
- The signature alone does not convey expected behavior
- Describing the type's interaction with other cells via usages; reference other types only when necessary — for example, to implement a pattern or algorithm

At the method/property level:
- Operation-specific details: input/output format, side effects, requirements, algorithms

Annotations at different levels must not:
- duplicate each other
- contain implementation details

### References in annotations

Use backtick references (`` ` ``) for:
- Signature variables — so the agent identifies the parameter under discussion
- Usages/Imports practices — so the agent knows which practice to apply
- Import types — so the agent identifies the data types

**Do not reference** anything outside the document context — every reference must resolve to an entity within the CODEMANIFEST file.

### Contract boundary isolation

Imports connect the current cell to external types and practices, but they do not transfer obligations across the boundary.

**Imported Types** (`Imports.Types`) constrain the current contract only through the type's signature — argument types,
return types, embedded/mutated forms. The internal behavior of the imported type (error handling, side effects, failure modes)
does not become an obligation of the current contract unless the current contract explicitly commits to that behavior in its own annotations.
A type used as an argument or return value is a dependency, not a behavioral mandate.

**Imported Usages** (`Imports.Usages`) document how to consume the provider cell's API.
They describe the provider cell's facade — not requirements imposed on the current cell.
The current contract is free to decide how to react to the provider's behavior (propagate, wrap, translate, recover),
because that decision belongs to the current cell's own contract.

The boundary rule:
- A dependency's behavior is a fact about the dependency, not a constraint on the dependent.
- Only the current cell's own contract text (signatures + annotations) defines what the current cell is obliged to do.
- When the current contract references an imported practice, the practice supplies context for implementation — it does not rewrite the current contract's obligations.

Example: if cell A imports a `Type` type whose `method` raises `Error`, that fact describes `Type`.
Cell A's own tool contract decides independently whether to propagate the exception, wrap it, or return an error result — unless cell
A's annotation explicitly commits to one of these behaviors.

### Body

#### Entity vs Routine — when to use which

**Entity** (with methods and/or properties) — when a type carries state and/or exposes multiple operations:

- An object with data and behavior
- A service with a set of methods
- A configuration with parameters

**Entity signature:**
- Describes how to obtain an instance of the type — how the consumer acquires the object
- Purpose: capture the input data required to construct the type

**Routine** (no methods or properties) — when a type represents a single operation:

- Transformer function (input → output)
- Factory/constructor
- Validator, parser, converter

**Routine signature:**
- Describes the input and output of the sole operation — what goes in and what comes out
- The return value carries a semantic label (e.g. `number:int`), where `number` clarifies the meaning of the returned type
- If the Routine returns nothing, omit the output

#### Mutation — when to use

Use mutation (`Object::Target`) when:

- You must explicitly indicate that the target type specializes or extends a base type
- The agent needs to understand the type relationship to select the correct implementation strategy

**Do not use mutation** when a type merely uses another type as an argument or return value — that is a standard dependency; Imports with a signature or annotations suffice.

#### Embedding — when to use

Use embedding (`->Entity: {}`) when:

- An imported type must become part of the current contract as-is
- The cell consumer needs to know the type is available through this cell (re-export)

**Do not embed** if the type is needed only for internal references — an import suffices.

### Footer

The footer does not affect the contract or architecture — it serves attribution purposes only.

Fill in upon initial CODEMANIFEST creation:
- `Author` — always `Goga`. Do not invent other names — all CODEMANIFEST files carry `Author: Goga`
- `CreatedAt` — creation date in day/month/year format
- `Description` — brief statement of why this manifest exists. Useful when the cell's purpose is not obvious from the header and annotations

---
