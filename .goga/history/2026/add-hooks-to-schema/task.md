# Schema domain hooks zone: `amend_cell` hard action with a wrapper-keyed `tools` extension area

Sources: ADR `add-hooks-to-schema` (accepted, discover interview 2026-09-23) and PRD of the
same topic. This task is their execution contract for formulation purposes; the contract
surface (types, signatures, locations, cell wiring) is owned by the design stage.

## Current State

- `goga schema` — the routine `schema` of the cell `goga/schema` — generates the project
  JSON map from the `AST` entity: every cell node carries six base fields (`cell`,
  `description`, `types`, `usages`, `dependencies`, `children`); filters `cells`,
  `max_depth`, `depends_on` apply before output; serialization runs through the
  `beautiful_json` pattern (indent, sorted keys, non-ASCII preserved). The CLI wrapper
  `goga/commands/schema` only delegates to the routine.
- The hooks platform (`goga/hooks` facade over `catalog`, `registry`, `dispatch`,
  `tools`) is the established extension surface of goga domains: a data-only additive
  action catalog, a run registry with per-tool isolated contexts, fixed-name injection,
  transparent delivery proxies, deterministic package enumeration, and soft/hard error
  classes. Hard actions already exist: `pipeline/amend_workflow`, `build/validate_build`,
  `config/amend_config`.
- Four domains own hooks zones following the `goga/<domain>/hooks` organization:
  `goga/pipeline/hooks`, `goga/build/hooks`, `goga/config/hooks`, `goga/topics/hooks`.
- Missing: no schema-domain action in the catalog, no schema hooks zone, and no supported
  way for an installed `goga_tool_*` package to contribute its per-cell facts to the
  schema map. Tool knowledge stays outside the map.

## Description

Open the schema domain for tool extension over the existing hooks platform, exactly as
settled in the ADR:

1. **Catalog record (additive).** One new record in the action catalog:
   domain `schema`, name `amend_cell`, error class `hard`. No published record is
   rewritten; the catalog stays data-only.
2. **Schema hooks zone.** A new hooks zone of the schema domain following the
   `goga/<domain>/hooks` organization, owning:
   - the per-cell read view delivered to a subscribed hook — the cell's authored facts
     only (path, description, type names, usages file names, dependencies with their
     imported types/usages, children as paths); never another tool's contributions,
     generated data, or the run's filter parameters;
   - the contribution model — one JSON mapping per tool per cell; multiple hooks of the
     same tool merge key-wise in registration order, a later write replacing an earlier
     one on key conflict; a tool never names itself — the namespace key is the platform
     tool identity (the canonical hyphen form of the package name without the
     `goga_tool_` prefix, assigned by the environment);
   - the checkpoint surface over the platform facade with cell-major delivery order:
     cells in tree order, tools in package-enumeration order within each cell; only
     cells surviving the `cells` / `max_depth` / `depends_on` filters are delivered.
3. **Generation-moment integration.** The checkpoint runs inside the schema generation
   moment on every entry path (the schema routine and the CLI command). Contributed
   facts land on extended cell nodes under the single wrapper key `tools` with the shape
   `tools -> {tool identity -> {fact -> value}}`. Empty objects never appear at any of
   the three levels: the `tools` key exists on a node iff at least one tool wrote at
   least one fact on that cell; a tool's key exists iff that tool wrote at least one
   fact; with no subscriptions the output is byte-identical to today's.
4. **Hard failure behavior.** A crashed hook and a structurally malformed contribution
   — a payload not representable in the JSON map: a non-mapping payload, non-string
   keys, or non-serializable values at any nesting level — are treated identically: the
   first failure in the delivery walk stops the schema command with a clean error naming
   the tool, the action, and the failing cell path; no partial map is printed on stdout.
   Registration problems keep the platform rule (warning on stderr naming the tool, the
   action, and the reason; the registration is skipped; the command continues). A tool
   package whose register facade fails to import stops the command with a clean error
   naming the package.
5. **Tool-author documentation.** Checkpoint usage documentation of the zone in the same
   form as the existing zones' checkpoint documentation, so a tool author integrates
   without goga code changes.

## Scope

**In scope:**
- The additive `schema` / `amend_cell` hard-action record in the action catalog.
- The schema domain hooks zone: per-cell read view of authored facts, per-tool
  contribution model with key-wise merge, cell-major checkpoint surface over the
  platform facade.
- Integration of the checkpoint into the schema generation walk: `tools` wrapper key on
  extended nodes, filter-surviving cells only, byte-identical output without
  contributions.
- Hard-failure and diagnostics behavior of `goga schema`: clean errors naming tool,
  action, cell path; registration warnings on stderr; stdout stays data-clean JSON.
- Tool-author documentation of the new subscription surface.
- Tests of the new behavior, including byte-identity without subscriptions and
  hard-stop on malformed contributions.

**Out of scope:**
- Any change to the existing schema node fields, filters, or base serialization —
  extension only.
- Tree-root or whole-map extensions — per-cell delivery only.
- Changes to the CODEMANIFEST DSL, the document model, or the AST domain.
- Changes to the hooks platform itself (catalog semantics, registry, dispatch,
  tool-package enumeration) or actions of other domains.
- Authoring, publishing, or blessing any concrete `goga_tool_*` package.
- Semantic interpretation or validation of contributed facts beyond structural form.
- Persistence or caching of contributions across runs.

## Acceptance Criteria

- With an installed tool subscribed to the schema action, `goga schema` output carries
  that tool's facts on the cells it extended, under its identity key inside the `tools`
  wrapper area; every contributed fact is attributable through the namespace alone.
- With no tool packages installed — or none subscribed to the schema action — the
  `goga schema` output is byte-identical to the output before this change; no `tools`
  key appears anywhere.
- On every extended node the six base fields are exactly what they would be without the
  extension; filters prune delivery exactly as they prune output.
- A crashing hook or structurally malformed contribution stops `goga schema` with a
  clean error naming the tool, the action, and the cell path; no partial JSON reaches
  stdout and no raw traceback is shown.
- Repeated runs over the same project with the same installed tools produce identical
  output (deterministic delivery order and merge).
- The new action is visible in the action catalog and in the registry inspection
  (`goga hooks`) alongside the other domains' actions; the zone's tool-author
  documentation exists in the same form as the existing zones' checkpoint documentation.
- The tool package integrates without any goga code change — the documented subscription
  surface alone is sufficient.

## Stack

- **Frameworks:** none new — the existing goga hooks platform (`goga/hooks` facade:
  `declared_actions`, delivery primitives, package enumeration) is the framework.
- **Libraries:** Python 3.10+ standard library only — `json` (serialization and the
  structural representability check of contributions), `dataclasses` with `kw_only=True`
  for the zone's data models.
- **Infrastructure:** none — no databases, brokers, or services.
- **Practices:** `conventions` (mandatory base practice); platform cell-level usages
  `declaring-actions`, `per-tool-delivery`, `registering-hooks` imported through the
  facade as the existing zones do; the `beautiful_json` serialization pattern already
  applied in `goga/schema`.
- **Testing:** pytest, ruff, pytest-cov per `conventions`; CLI tested by direct handler
  call.

## External Dependencies

None — no new components outside the project. No `.goga/usages/cooks/` files to create
or update.

| Component | Usage file | Status |
|-----------|------------|--------|
| — | — | no external dependencies |

## Risks and Constraints

- **Byte-identity is a hard contract** (user-stated): with no contributions the output
  must stay byte-identical; the no-empty-objects rule at all three levels (`tools` key,
  tool key, fact mapping) must hold exactly — an accidentally emitted empty `tools`
  object breaks the contract silently.
- **Hard error class on a read-only-looking command**: `goga schema` becomes stoppable
  by third-party tool code; the clean-error discipline (named tool, action, cell path;
  no partial stdout; no raw traceback) must hold on every failure path, including the
  register-facade import failure.
- **Mutual blindness of tools**: every delivered view is built from authored data only —
  a tool must never observe another tool's contributions or staged state; isolation is
  per-tool by platform law.
- **Cross-import prohibition**: the zone must not import from `goga/schema`; the read
  view is built from operation data the caller passes (the config-zone pattern), keeping
  the dependency direction `goga/schema` → zone → `goga/hooks` acyclic.
- **Catalog additivity** (platform law): opening the action is one new record; published
  records are never rewritten.
- **Authored sources are immutable**: contributions live in memory for the current run;
  CODEMANIFEST and project files are never written.
- **stdout discipline**: stdout is machine-consumed JSON only; every warning and
  diagnostic goes to stderr.

## Scope Estimate

Single task, no decomposition. The parts are tightly coupled over one checkpoint (zone,
catalog record, walk integration) and none carries independent value alone; scale is
comparable to the config domain hooks zone (roughly 5–7 contract types, 3 affected
cells + 1 new, one additive catalog record, tests, zone documentation). No additional
topics were created.

## Existing Architecture

Affected cells and integration requirements:

- `goga/hooks/catalog` — one additive record: domain `schema`, name `amend_cell`,
  error class `hard`. The catalog cell owns no other change.
- New zone cell under `goga/schema/hooks` (naming follows the established
  `goga/<domain>/hooks` organization) — imports types and practices from the `goga/hooks`
  facade only (`HookRegistry`, `declared_actions`, `wrap_context`, `build_hook_arguments`,
  delivery enumeration; usages `declaring-actions`, `per-tool-delivery`,
  `registering-hooks`). Does not import `goga/schema` — the cross-import prohibition
  holds.
- `goga/schema` — the generation walk integrates the checkpoint: per-cell delivery while
  building the node tree (or an equivalent single checkpoint surface over the walk),
  `tools` placement on extended nodes after filters. Its existing dependency on
  `goga/ast` is unchanged; it gains a dependency on the zone.
- `goga/commands/schema` — the CLI wrapper keeps pure delegation; hard errors surface as
  clean command failures with a non-zero exit and nothing on stdout.

Existing link connections examined: the dependency chain `goga/commands/schema` →
`goga/schema` → (`goga/ast`, new zone) → `goga/hooks` introduces no cycle; the platform
facade already re-exports everything the zone needs; the four existing zones (pipeline,
build, config, topics) provide the delivery and documentation patterns to follow — the
config zone is the closest analog for a hard amendment action with per-tool commit
granularity and structurally malformed contribution handling.

## Notes

- Decisions are settled in the ADR (`add-hooks-to-schema`): wrapper key `tools` over
  flat tool keys (collision-impossible by construction, base fields structurally
  separated); namespace key = platform tool identity; one JSON mapping per tool per
  cell with key-wise merge in registration order; structural malformedness defined as
  non-representability in the JSON map, treated as a crashed hook; cell-major delivery;
  read view of authored cell facts only; no empty objects at any level.
- The contract surface (types, signatures, file locations, exact cell wiring) is an open
  point owned by the design stage per the ADR — this task deliberately fixes behavior,
  not architecture.
- No code examples are included in this task by stage constraint; the `tools` shape
  notation above restates the ADR's decided output format.
