# Architecture Plan — Contract Hooks Zone

## Topic

**Contract hooks zone** — per-cell read-and-contribute checkpoint (`amend_contract`) for the contract domain.

Plan path: `.goga/history/2026/add-hooks-to-contract/arch.md` (topic: `add-hooks-to-contract`).

Approved through the prototype pipeline 2026-09-29: primary analysis, type map, type detailing, cell
distribution, per-cell contracts, cell assembly, final approval summary.

## Implementation Order

Cells ordered from leaves to root:

1. **`goga/hooks/catalog`** (modify) — has no Imports; the platform leaf. The record is published first so
   the address exists before any consumer resolves it.
2. **`goga/contract/hooks`** (create) — depends only on `goga/hooks` (Types: `HookRegistry`, `wrap_context`,
   `build_hook_arguments`, `declared_actions`; Usages: `per-tool-delivery`, `registering-hooks`). Does not
   import `goga/contract` or any command cell.
3. **`goga/commands/contract`** (modify) — depends on the new zone (Types + Usages) in addition to its
   existing imports (`goga/ast`, `goga/contract`, `goga/config`, `goga/config/hooks`). The root consumer.

Documentation pages and tests are implementation-stage deliverables recorded in the task file
(`docs/features/contract/hooks.md`, `docs/features/hooks/index.md`, `docs/features/tools/hooks.md`,
`docs/features/contract/cli.md`, command help; tests mirroring the source structure per the `convention`
practice) — they are not CODEMANIFEST/`.usages` artifacts of this plan.

## Artifacts

### Cell: `goga/contract/hooks` — CREATED ANEW

#### CODEMANIFEST — `goga/contract/hooks/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - HookRegistry
      - wrap_context
      - build_hook_arguments
      - declared_actions
    Usages:
      - per-tool-delivery
      - registering-hooks
    From: goga/hooks

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of
  development and testing in the project

  This cell owns the hooks zone of the contract domain: the per-cell
  read view of the comparison facts, the per-tool contribution model
  with its type-addressed unit commit, and the checkpoint surface that
  delivers the contract amendment over the platform facade. One
  registry per run carries every checkpoint of a command — the
  checkpoints never multiply the package enumeration. Every context is
  built from the operation data the caller passes — no configuration,
  git, or file reads happen here, and the extended domain is not
  imported. The amendment action is hard: the first failing hook of
  the delivery walk — a crashed hook, a structurally malformed
  contribution, or a contribution addressed to a type the cell does
  not declare — stops the command with a clean error naming the tool,
  the action, and the failing cell path, and the offending type name
  for a bad address; the tool's whole contribution is discarded.
  Tools are mutually blind — every delivered view reads the authored
  comparison facts only, never another tool's contribution; each
  tool's contribution commits as a unit, in enumeration order, per
  cell. The contributions live in memory for the current run — the
  comparison output is composed fresh from the caller's data.
  Use the `per-tool-delivery` practice for the staged delivery loop of
  the amendment checkpoint — its loop skeleton, primitives, and
  tool-grouped commit apply as written.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind the checkpoint.
  Use relative imports.

---

"CellFacts(path: str, types: list[TypeFacts])":
  location: facts.py
  annotations: |
    The comparison facts of one cell — the per-cell read view
    delivered to a subscribed hook.

    `path`: the normalized cell path
    `types`: the comparison facts of each declared type of the cell

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the constructing operation passes resolved values;
      nothing is read here
    - Authored projection only — the declared and extracted forms
      exactly as the caller's comparison composes them; identical for
      every tool
    - One shape for every implementation language — no per-language
      projection
  properties:
    "path -> str": |
      The normalized cell path.
    "types -> list[TypeFacts]": |
      The comparison facts of each declared type of the cell.

"TypeFacts(name: str, signature: FormFacts, properties: list[MemberFacts], methods: list[MemberFacts])":
  location: facts.py
  annotations: |
    The comparison facts of one declared type — the name with the
    compared signature and the compared members.

    `name`: the declared type name
    `signature`: the compared signature of the type
    `properties`: the compared property members — empty for a routine
    `methods`: the compared method members — empty for a routine

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the caller from its own comparison
      values
  properties:
    "name -> str": |
      The declared type name.
    "signature -> FormFacts": |
      The compared signature of the type.
    "properties -> list[MemberFacts]": |
      The compared property members — empty for a routine.
    "methods -> list[MemberFacts]": |
      The compared method members — empty for a routine.

"FormFacts(codemanifest: str, implementation: str | None)":
  location: facts.py
  annotations: |
    One compared form — the declared string and its extracted
    counterpart, including an absent counterpart.

    `codemanifest`: the declared form of the CODEMANIFEST
    `implementation`: the extracted counterpart — absent when the
                      implementation carries none

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure strings only — the language-agnostic shape carries no
      parsed structures
  properties:
    "codemanifest -> str": |
      The declared form of the CODEMANIFEST.
    "implementation -> str | None": |
      The extracted counterpart — absent when the implementation
      carries none.

"MemberFacts(name: str, form: FormFacts)":
  location: facts.py
  annotations: |
    The compared form of one named member — a property or a method.

    `name`: the declared member name
    `form`: the compared form of the member

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the caller from its own comparison
      values
  properties:
    "name -> str": |
      The declared member name.
    "form -> FormFacts": |
      The compared form of the member.

"ContractAmendment(cell: CellFacts)":
  location: amendments.py
  annotations: |
    The read-and-contribute view of one tool for one cell — the
    delivered facts of the amendment checkpoint and the buffer of
    this tool's type-addressed contributions.

    `cell`: the comparison facts of the cell being amended —
            read-only and identical for every tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads deliver the comparison facts — a tool never sees
      another tool's contribution
    - The buffered contributions belong to this tool alone
  properties:
    "cell -> CellFacts": |
      The comparison facts of the cell; read-only for the receiving
      hook.
  methods:
    "contribute(facts: dict[str, dict[str, object]])": |
      Buffer one type-addressed contribution of this tool.

      `facts`: the type-addressed mapping — declared type name to
               the tool's fact mapping for that type

      Requirements:
      - The call buffers into the buffer of this tool alone and
        changes nothing until the delivery commits it
      - The buffer merges key-wise — for one type, a later write
        replaces an earlier one on fact-name conflict; a repeated
        type address merges its facts
      - An empty outer mapping contributes nothing

      Constraints:
      - Do not cancel, redirect, or defer the operation — a
        contribution extends the addressed type nodes' tools areas
        only

"ToolContribution(tool: str, facts: dict[str, dict[str, object]])":
  location: overlay.py
  annotations: |
    The committed contribution of one tool for one cell — the pairing
    of the tool identity with its type-addressed fact mappings.

    `tool`: the tool identity assigned by the platform
    `facts`: the committed type-addressed contributions of the tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the checkpoint delivery alone
  properties:
    "tool -> str": |
      The tool identity assigned by the platform.
    "facts -> dict[str, dict[str, object]]": |
      The committed type-addressed contributions of the tool.

"merge_type_contributions(contributions: list[ToolContribution]) -> tools: dict[str, dict[str, dict[str, object]]]":
  location: overlay.py
  annotations: |
    The deterministic per-type tools-area composition — the mapping
    of each addressed type name to its tools area, built from the
    committed contributions.

    `contributions`: the committed contributions in enumeration order
    `tools`: the tools area per addressed type name — empty when
             nothing contributed

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Take the contributions in enumeration order
    2. Skip a contribution whose mapping is empty — a tool exists on
       a type iff that tool wrote at least one fact for that type
    3. For each type name the contribution addresses, place the
       tool's fact mapping under the tool identity inside that type's
       area
    4. A type name absent from every committed contribution is
       absent from the result
    5. Return the composed mapping — empty when every contribution
       was empty or none committed

    Requirements:
    - Deterministic — the same contributions give the same mapping
    - Pure — the inputs stay unmutated; the result is a new mapping
    - Structural validation is not here — it happened at the tool
      commit point of the delivery

    Constraints:
    - Do not read or write the filesystem
    - Do not mutate `contributions` or their maps

"ContractHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the contract domain — the
    contract-amendment delivery over the platform facade.

    Apply the `convention` practice for the code style and
    intra-package imports.
    Use the `per-tool-delivery` practice for the staged delivery loop
    of the amendment checkpoint.
    Use the `registering-hooks` practice for the registration contract
    behind the checkpoint.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a
      command — the assembly runs once per run whatever the number
      of checkpoints
    - Every context is built from the values the caller passes — no
      configuration, git, or file reads happen at the checkpoint
  methods:
    "amend_contract(cell: CellFacts) -> tools: dict[str, dict[str, dict[str, object]]]": |
      Deliver the contract-amendment checkpoint for one cell and
      return the tools area per addressed type.

      `cell`: the comparison facts of the cell — operation data
              handed over by the calling command
      `tools`: the tools area per addressed type name — empty when
               nothing contributed

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="contract", action="amend_contract"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in
         enumeration order: build the tool's `ContractAmendment` view
         over the delivered facts — every tool reads the same `cell` —
         wrap it via `wrap_context`, project the call arguments via
         `build_hook_arguments` with the tool's own context, and call
         each hook of the tool
      3. A tool whose every hook returned without raising passes the
         structural check of its merged buffer — a payload not
         representable on the type nodes (a non-mapping payload,
         non-string keys, non-serializable values, or an empty
         mapping at any nesting level) or an address naming a type
         the cell does not declare is the same hard failure as a
         crashed hook
      4. A passing tool commits as one `ToolContribution`; an empty
         merged buffer commits nothing
      5. A hard failure stops the delivery at the first failure in
         the walk — a clean error naming the tool, the action, and
         the failing cell path, and the offending type name for a
         bad address; the tool's contribution is discarded
      6. Compose the tools areas of the committed contributions via
         `merge_type_contributions` and return them

      Requirements:
      - The commit granularity is the tool — a tool's whole
        contribution commits only after every hook of the tool
        succeeds and the merged buffer is structurally representable
        and fully addressed to declared types
      - An address without subscriptions returns an empty mapping —
        the delivery is unobservable, the caller's output stays
        byte-identical
      - With no tool packages installed the checkpoint returns an
        empty mapping

      Constraints:
      - Do not apply any contribution outside the single composition
        after the walk
      - Do not skip a subscriber of the address
      - Do not read configuration, git, or the filesystem at the
        checkpoint
      - Do not print — the caller owns all output

---

Author: Goga
CreatedAt: 29/09/26
Description: |
  Owner of the contract domain hooks zone — the per-cell read view, the
  per-tool contribution model, and the checkpoint surface over the
  hooks platform.
```

#### `.usages/` files — `goga/contract/hooks/.usages/checkpoints.md`

```md
# contract — amending type nodes with tool facts

How the contract comparison uses the hooks zone of the contract domain:
delivering the contract-amendment checkpoint after the built-in
comparison and placing the contributed facts on the type nodes of the
JSON output. For every entry path that runs the contract comparison —
the CLI command.

## The checkpoint surface

One `ContractHooks` object serves the checkpoints of a run — the
surface shares one registry per run, so a command that reaches further
checkpoints enumerates the tool packages once.

```python
from goga.contract.hooks import ContractHooks

hooks = ContractHooks()
```

## Amend each compared cell

Run the built-in comparison of every requested cell first — existing
failures fire before any hook runs. Then walk the requested cells
deduplicated by normalized path, in first-request order: build the
comparison facts of each cell from your own comparison data, hand them
to the zone entry, and place each returned tools area on its type's
node — the key exists iff the mapping is non-empty.

```python
from goga.contract.hooks import CellFacts, TypeFacts, FormFacts, MemberFacts

for path in unique_normalized_paths(cells):
    facts = CellFacts(
        path=path,
        types=[
            TypeFacts(
                name=type_name,
                signature=FormFacts(codemanifest=declared, implementation=extracted),
                properties=[MemberFacts(name=n, form=FormFacts(codemanifest=d, implementation=i)) for n, d, i in props],
                methods=[MemberFacts(name=n, form=FormFacts(codemanifest=d, implementation=i)) for n, d, i in methods],
            )
            for type_name, declared, extracted, props, methods in comparison_of(path)
        ],
    )
    tools = hooks.amend_contract(cell=facts)
    for type_name, area in tools.items():
        output[path][type_name]["tools"] = area  # never an empty object
```

- The delivered view is built from the values you pass — the
  checkpoint reads no configuration, no git, no files; the facts are
  the comparison facts of the cell only, one shape for every
  implementation language.
- Tools are mutually blind: every hook reads the same comparison
  facts, never another tool's contribution; each tool's contribution
  commits as a unit, in enumeration order, per cell.
- The contribution is addressed per declared type — an address naming
  a type the cell does not declare is the hard failure of the
  delivery.
- The action is hard: the first failing hook — or a structurally
  malformed contribution (a non-mapping payload, non-string keys,
  non-serializable values, or an empty mapping at any nesting level) —
  stops the command with a clean error naming the tool, the action,
  and the failing cell path; a bad address also names the offending
  type. No partial output reaches stdout.
- A tool package whose facade fails to import stops the command the
  same way — the error names the package (raised as ImportError at
  the registry build); convert it to the same clean error, never a
  raw traceback.
- An address without subscriptions returns an empty mapping — place
  no `tools` key on any type node; with no tool packages installed the
  output is byte-identical to the comparison without the extension.
- A cell with no declared types has no landing zone: the checkpoint is
  delivered over empty facts, and any non-empty contribution for it is
  the unknown-address hard failure.
- The output and the CODEMANIFEST files are never modified — the
  contributions live in memory for the run; repeated runs with the
  same tools reproduce the output deterministically.
- stdout stays data-clean JSON; every warning and diagnostic goes to
  stderr.

## The output shape

Each addressed type node carries one wrapper key: `tools -> {tool
identity -> {fact -> value}}`, next to the fixed keys
`signature`/`properties`/`methods`. The namespace key is the platform
tool identity — the canonical hyphen form of the package name without
the `goga_tool_` prefix; a tool never names itself. Base fields and
extensions stay structurally separated; empty objects never appear at
any of the three levels. There is deliberately no cell-level landing:
a tool's cell-level context lives inside its per-type facts.
```

### Cell: `goga/hooks/catalog` — MODIFIED

#### CODEMANIFEST diff — `goga/hooks/catalog/CODEMANIFEST`

Header (Usages, Annotations) — unchanged. Body type `Action` — unchanged. Footer — unchanged.

**Change 1 — add to the `Requirements` of `declared_actions`** (append at the end of the bullet list):

```yaml
    - The catalog carries the contract amendment action — the record
      domain="contract", name="amend_contract", error_class="hard": the
      first failing hook of the action — a crashed hook, a structurally
      malformed contribution, or a contribution addressed to a type the
      cell does not declare — stops the command with a clean error naming
      the tool, the action, and the failing cell path, and the offending
      type name for a bad address
```

No records are rewritten; the record ordering rule (domain, then name) is
the existing Algorithm — the new record lands between the `config` and
`onboarding` records in the returned list (domain-alphabetical: build,
config, contract, onboarding, pipeline, …).

#### `.usages/` files

None — unchanged (the cell has no `.usages/` directory; the address is documented through the zone's usage file and the documentation pages).

### Cell: `goga/commands/contract` — MODIFIED

#### CODEMANIFEST diff — `goga/commands/contract/CODEMANIFEST`

**Change 0 — normalize the header practice key and the base annotation**
(before Change 1; aligns the header with the project base of
`.goga/config.yml` and the `goga/commands/schema` precedent):

1. In `Usages:` rename the key `conventions` → `convention` — the value
   path stays `.goga/usages/conventions.md`.
2. In the global `Annotations:` replace the rephrased first paragraph with
   the project base annotation transferred verbatim:

```yaml
The `convention` practice is used for:
- Working with the codebase
- Organizing the REPL development cycle
- Debugging and testing
- Organizing the test infrastructure
- Understanding the general principles and rules of development and testing in the project
```

The remaining paragraphs of the global `Annotations:` and the annotation of
the `contract` Routine are untouched — no annotation references the renamed
key, and the anchors of the changes below stay valid.

**Change 1 — append to `Imports`** (after the existing `goga/config/hooks` block):

```yaml
  - Types:
      - ContractHooks
      - CellFacts
      - TypeFacts
      - FormFacts
      - MemberFacts
    Usages:
      - checkpoints AS contract-checkpoints
    From: goga/contract/hooks
```

The `AS` alias resolves the name clash with the existing `checkpoints`
import of `goga/config/hooks`.

**Change 2 — append to the global `Annotations`** (after the existing
`checkpoints` paragraph):

```yaml
  Use the `contract-checkpoints` practice for the contract amendment
  checkpoint at the comparison moment — the command builds the
  comparison facts of each requested cell, delivers the checkpoint over
  the `ContractHooks` surface after the built-in comparison of every
  requested cell, and composes the returned tools areas onto the type
  nodes of the JSON output.
```

**Change 3 — replace the annotation of the `contract` Routine** with:

```yaml
    Command for comparing CODEMANIFEST contract with implementation.

    `cells`: paths to cells for comparison, one or more
    `lang`: implementation language. Priority: CLI argument > `ProjectConfig`. If None — taken from `ProjectConfig`.language

    CLI options:
    - --lang: implementation language. If not specified — the value from `ProjectConfig`.language is used

    Algorithm:
    1. Load configuration via `load_project_config` → `ProjectConfig`;
       deliver the config amendment checkpoint per the `checkpoints`
       practice via the `ConfigHooks` checkpoint surface —
       amend_config(config=...). A load or checkpoint failure —
       ValueError covers the hard action, ImportError a broken tool
       package facade — wraps into the same user-facing
       click.ClickException, never a raw traceback
    2. Resolve language from the effective configuration of the
       `ConfigOverlay`:
       - If `lang` is provided (not None) — use CLI value
       - Otherwise — use the language field of `ProjectConfig` (the
         CLI option surface is unchanged)
    3. Create `AST` object and load the project using the `loading` practice
    4. For each path from `cells`:
       - Find the document in the tree using the `loading` practice
       - Extract types from document body: entities and routines
       - Get the implemented contract via `contract_logic`
       - For each type from CODEMANIFEST find the match in implementation by name
       - Build comparison structure (CODEMANIFEST is primary)
    5. Deliver the contract amendment checkpoint per the
       `contract-checkpoints` practice: build the `CellFacts` of each
       requested cell — with the `TypeFacts`, `FormFacts`, and
       `MemberFacts` of each declared type — from the command's own
       comparison data, and hand them to the `ContractHooks` checkpoint
       surface —
       amend_contract(cell=...) — once per unique normalized path, in
       first-request order, only after the built-in comparison of
       every requested cell succeeded. A checkpoint failure —
       ValueError covers the hard action, ImportError a broken tool
       package facade — wraps into the same user-facing
       click.ClickException, never a raw traceback
    6. Compose the tools areas onto the type nodes: each addressed
       type of a cell carries its tools area under the `tools` key,
       next to the fixed keys; the key is absent when nothing
       contributed

    Key principle: CODEMANIFEST is the source of truth. Traversal goes by types,
    methods and properties from the contract. Implementation fills the implementation
    field or null if not found.

    For entity:
    - signature: constructor parameters from codemanifest and implementation
    - properties: for each property from codemanifest find in implementation
    - methods: for each method from codemanifest find in implementation

    For routine:
    - signature: full signature from codemanifest and implementation

    Output the result via the `beautiful_json` practice.

    Output format:
    ```
    {
      "norm/path/to/cell": {
        "TypeName": {
          "signature": { "codemanifest": "...", "implementation": "..." },
          "properties": { "name": { "codemanifest": "...", "implementation": "..." } },
          "methods": { "name": { "codemanifest": "...", "implementation": "..." } },
          "tools": { "tool-name": { "fact": "value" } }
        },
        "RoutineName": {
          "signature": { "codemanifest": "...", "implementation": "..." }
        }
      }
    }
    ```

    (the `tools` key appears on a type node exactly when at least one
    tool contributed at least one fact for that type)

    Requirements:
    - output must contain nothing except the json structure
    - if cell path not found → output error to stderr and exit with code 1
    - output errors to stderr (click.echo with err=True)
    - exit code: 0 on success, 1 on error
    - command help must explain the response structure, including the
      tools-area semantics, clearly for AI agents
    - The amendment summary lines of the `ConfigOverlay` print to stderr
      (nothing when empty)
    - The built-in comparison of every requested cell completes before
      any hook runs — existing failures keep their precedence
    - A path requested more than once is delivered once, in
      first-request order
    - With no tool packages installed, none subscribed, or
      subscriptions that contribute nothing, the output is identical
      to the same invocation without the checkpoint
```

Footer — unchanged.

#### `.usages/` files diff — `goga/commands/contract/.usages/contract.md`

**Change 1 — extend the `## Output format` section**: add the `tools` key
to the JSON example (on the type node, after `methods`) and append the
note:

```md
The `tools` key appears on a type node exactly when at least one installed
tool package contributed at least one fact for that type through the contract
amendment checkpoint; it is absent otherwise — never an empty object. Each key
inside `tools` is the contributing tool's identity.
```

All other sections (Purpose, Syntax, Arguments, Options, Exit code,
Examples) — unchanged.

## Dependency Map

```
 goga/hooks (platform facade, as-is)
   │  Types: HookRegistry, wrap_context, build_hook_arguments, declared_actions
   │  Usages: per-tool-delivery, registering-hooks
   ▼
 goga/contract/hooks  (CREATE)
   │  Types: ContractHooks, CellFacts, TypeFacts, FormFacts, MemberFacts
   │  Usages: checkpoints AS contract-checkpoints
   ▼
 goga/commands/contract  (MODIFY — root consumer)
   ├── goga/ast            (existing: AST + loading)
   ├── goga/contract       (existing: contract dispatcher — the zone never imports it)
   ├── goga/config         (existing: ProjectConfig, load_project_config)
   └── goga/config/hooks   (existing: ConfigHooks, ConfigOverlay + checkpoints)

 goga/hooks/catalog (MODIFY): one additive record — data, not an Imports edge
 goga/contract (domain): unchanged; not imported by the zone
```

No circular dependencies: the platform does not know the zone; the domain
does not know the zone; the zone does not know the command.

## Verification Checklist

After implementing each artifact, verify:

- **`goga/hooks/catalog`**
  - `goga lint` passes on the modified CODEMANIFEST
  - `declared_actions()` returns the `contract`/`amend_contract`/hard record
    ordered between the `config` and `onboarding` records; every existing
    record is byte-identical
  - `goga hooks` shows a hook registered at the new address once a tool
    package subscribes
- **`goga/contract/hooks`**
  - `goga lint` passes on the new CODEMANIFEST; locations are exactly
    `facts.py`, `amendments.py`, `overlay.py`, `events.py` at the cell root
  - The facade `__init__.py` exposes the full contract API through
    `__all__` per the Python language rules
  - One registry build per run across many `amend_contract` calls (the
    enumeration is not multiplied)
  - Baseline: with no subscriptions `amend_contract` returns an empty
    mapping; committed contributions merge deterministically in
    enumeration order; a repeated fact write inside one tool's type
    address resolves to the last write
  - Hard failures: a crashing hook, a non-representable payload, or an
    address to an undeclared type each raise a clean error naming the
    tool, the action, the cell path (and the type name for a bad
    address) — no traceback, nothing committed for the failing tool
  - Tests mirror the source structure under `tests/contract/hooks/`
    per the `convention` practice
- **`goga/commands/contract`**
  - `goga lint` passes on the modified CODEMANIFEST; the aliased import
    `contract-checkpoints` resolves and the config `checkpoints` import
    stays intact
  - Built-in comparison failures (unknown cell; package not importable;
    extraction failure; configuration load failure) fire before any
    hook is invoked; a path requested twice delivers one checkpoint, in
    first-request order
  - Tools areas land on type nodes only (`tools` key next to
    `signature`/`properties`/`methods`); absent — never empty — when
    nothing contributed; a declared type literally named `tools` keeps
    working unchanged
  - With no tool packages installed / none subscribed / empty
    contributions, the output is byte-identical to the pre-extension
    invocation of the same request
  - The command help explains the response structure including the
    tools-area semantics; stdout carries only the JSON; errors go to
    stderr as clean messages
  - Tests under `tests/commands/test_contract.py` cover delivery,
    composition, baseline identity, and the clean hard-failure path per
    the `convention` practice (CLI tested by direct handler call)
- **Documentation (implementation-stage deliverables)**
  - `docs/features/contract/hooks.md` describes the address
    (`contract`/`amend_contract`, hard), what a hook reads, what it may
    contribute, where contributions appear, and the failure treatment —
    replacing the "no hook actions today" statement
  - `docs/features/hooks/index.md` and `docs/features/tools/hooks.md`
    enumerate the new declared action
  - `docs/features/contract/cli.md` documents the tools area of the
    response structure
- **Validation gates**: `pytest tests/ -x` passes; `ruff check` is clean
  for all touched code
