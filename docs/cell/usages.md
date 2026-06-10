# Usages

Usages (practices) form the documentation layer for consumers of a cell's API. They describe **how to work with the cell facade** — not requirements imposed on the cell itself. Practices do not define entities; they describe how to consume them.

## Two levels

Practices reside at two levels:

### Project-level `.goga/usages/`

Located at the project root. Contains shared practices not bound to any specific cell: libraries, tools, conventions, standards. Available to every cell in the project. Referenced via path in the `Usages` directive of CODEMANIFEST.

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  encoding_lib: .goga/usages/encoding.md
```

### Cell-level `<cell_path>/.usages/`

Located inside a cell. Contains practices for consumers of a specific cell's API: how to use the cell facade, which patterns to apply. Consumers reference them through `Imports` pointing to the provider cell.

```yaml
Imports:
  - Usages:
      - reading       # resolves to auth/data/.usages/reading.md
    From: auth/data
```

### Placement rules

- If the practice describes a library, tool, or project-wide convention → project-level `.goga/usages/`
- If the practice describes how to consume a specific cell's API → cell-level `<cell_path>/.usages/`

## Three connection forms

Choose how to connect a practice based on the situation:

### File — path to an `.md` file

```yaml
Usages:
  conventions: .goga/usages/conventions.md
```

Use when:

- The practice is extensive and would clutter CODEMANIFEST if written inline
- The practice is reused across multiple cells
- The practice evolves independently from the contract

### Inline — text directly in CODEMANIFEST

```yaml
Usages:
  pattern: |
    Use immutability for all return values.
    Prefer composition over inheritance.
```

Use when:

- The practice is short — a few sentences or a single paragraph
- The practice is specific to this cell and has no meaning outside its context
- Creating a separate file would be overkill

### URL — link to an external resource

```yaml
Usages:
  rest_guide: https://example.com/docs/rest-best-practices
```

Use when:

- The practice is external documentation with no value in duplicating (library docs, RFCs, standards)
- The practice is maintained by a third-party source and kept current there

## Connecting practices

Practices are connected through two mechanisms:

1. **Declaration** in the `Usages` section — the practice is defined by its value (file, inline, or URL)
2. **Import** via the `Imports` section — the practice is imported from another cell's `.usages/` directory by filename without the `.md` extension

Imported practices:

- Reside in the source cell at `{From}/.usages/`
- Are referenced by filename without the `.md` extension
- Establish a **tracked dependency** — when a practice changes, consumers are identified through the import graph
- **Do not** create contractual obligations — they serve as documentation for the consumer
- Must not conflict with local `Usages` keys in the document header (resolve conflicts via the `AS` alias in `Imports`)

## Writing usage files

Create or update a `usage.md` file inside `<cell_path>/.usages/` when creating or updating CODEMANIFEST files, or when an external consumer requires guidance on working with the cell's API.

### Content guidelines

- Design the CODEMANIFEST file first, then write the usage file in the `<cell_path>/.usages/` directory
- Open each file with a clear domain statement — which area the usage covers and its target audience
- Describe **ready-to-use patterns** — concrete API call scenarios with code examples
- Include typical usage examples — a minimal working example for each key scenario
- When a cell exposes a complex API with multiple entry points, group examples by functional domain into separate files within `<cell_path>/.usages/`
- When referencing contract types, use names matching the signatures in `CODEMANIFEST` so the consumer can locate the entity unambiguously
- Document side effects, preconditions, and constraints relevant to the consumer but not part of the contract itself

### Quality guidelines

- **One file — one functional domain.** Do not mix unrelated scenarios in a single file
- File names must be concise and descriptive of the content
- When connecting a practice via the `Usages` directive in CODEMANIFEST, the key must match the filename (without extension)
- Practices must be **self-contained** — consumers must understand the pattern without reading the cell's source code
- Practices must **not reference other practices** — all necessary context resides within the practice itself. Cross-references introduce implicit dependencies and break isolation
- Practices must **not duplicate annotations** from CODEMANIFEST — they describe **how to use**, not **what to implement**
- Practices do not impose contractual obligations on the cell — they remain documentation-level artifacts