# Tool Extension of the Cell-Contract Map (Schema Domain)

## Problem

goga is a contract-oriented toolkit: a project is a tree of cells, each described by a
CODEMANIFEST document, and the `goga/schema` domain generates the project's unified
cell-contract map — a JSON tree in which every cell node carries its description, types,
usages, dependencies, and children.

Installed tool packages (`goga_tool_*`) hold per-cell knowledge about a goga project —
documentation coverage, test status, metrics, annotations. The schema domain offers them
no integration point: its output node format is fixed and closed, and the hooks platform —
the established extension surface of goga domains — declares no schema-domain action.

As a result, a tool package author who wants the tool's facts to be part of the project
map has no supported way to contribute them at the schema generation moment. The tool's
data stays outside the map, and each tool must invent its own project discovery and
representation instead of reusing the schema generation flow.

## Users

### Primary: tool package author

The developer of an installed `goga_tool_*` package that holds per-cell knowledge about
a project.

- **Trying to accomplish:** make the tool's per-cell facts part of the cell-contract map
  at the moment the map is generated — without modifying goga core or the authored
  CODEMANIFEST files.
- **Context:** the opportunity occurs at schema generation time, when a consumer runs
  `goga schema` in a project where the tool package is installed.
- **What matters:** a supported subscription surface following the established hooks
  pattern; predictable failure treatment; isolation from other tools' contributions.
- **Constraint:** can only contribute through the declared action contract; cannot
  change existing schema node fields.

### Secondary: schema map consumer

Agents/AI assistants, CLI tooling, and developers who read `goga schema` output to
understand a project's cell structure.

- **Trying to accomplish:** get a complete, machine-readable picture of the project —
  including tool-contributed facts — from one deterministic source.
- **What matters:** existing node fields stay stable; tool-added data is attributable
  and deterministic; with no tools installed, the output is identical to today's.

## Goals

1. **Tool-contributed per-cell knowledge becomes part of the cell-contract map.** An
   installed tool package can make its per-cell facts appear in the schema output of a
   project where it is installed — through a supported, documented integration at the
   schema generation moment — so tool data no longer lives outside the map.
2. **The schema map stays stable while becoming richer.** Consumers keep relying on the
   existing node fields exactly as they are; tool-contributed facts arrive alongside
   them, attributable to their contributing tool and deterministic across runs.
3. **The schema domain joins the uniform domain extension pattern.** Tools integrate
   with the schema domain the same way they already integrate with the pipeline, build,
   config, and topics domains — one consistent extension model across goga, with no
   bespoke per-tool project discovery.

## User Experience

### Tool author — subscribing

Inside their `goga_tool_*` package, the author implements the `register_hooks` facade
callback and subscribes a hook to the new schema-domain action — the same subscribe flow
used by tools of the pipeline, build, config, and topics domains. No goga code changes
and no reinstall are needed; registration is never cached, so package edits apply from
the next run.

### Tool author — the hook

When any consumer runs `goga schema` in a project where the tool is installed, the
tool's hook is invoked separately for each cell included in the output. The hook reads
that cell's authored facts (path, description, types, usages, dependencies, children)
and contributes the tool's own facts for that cell through the delivered context.
Delivery is per-cell: a tool extends cells, not the tree root.

Every tool reads the authored cell data — never another tool's contributions (mutual
blindness). Deliveries follow deterministic tool-package enumeration order.

### Schema map consumer

The consumer runs `goga schema` (CLI command or schema routine) and receives the JSON
map on stdout: every existing node field exactly as today, plus — on the cell nodes the
tools extended — tool-contributed data under a namespaced extension area keyed by the
contributing tool's package name. Attribution is structural; collisions between tools
are impossible; base fields are never touched.

With no tool packages installed — or none subscribed to the schema action — the output
is byte-identical to today's.

Filters (`cells`, `max_depth`, `depends_on`) apply first: tool facts appear only on
cells that survive filtering.

### Failure behavior (hard action)

- A tool's hook that crashes while processing any cell — or contributes a structurally
  malformed payload — stops `goga schema` with a clean error naming the tool and the
  action; no partial map is printed on stdout.
- A tool package whose register facade fails to import stops the command the same way,
  with a clean error naming the package.

### Feedback

stdout stays data-clean JSON; warnings (for example, an invalid registration) go to
stderr; the schema command never prints progress noise.

### Recovery and repetition

The extension lives in memory for the current run only; authored CODEMANIFEST files are
never modified. Re-running is deterministic: the same tools and the same project produce
the same map. Fixing or removing a failing tool restores the command on the next run;
nothing is left behind.

## Requirements

### Subscription surface

- **R1.** The schema domain must open a hook action for installed tool packages through
  the existing subscription flow — domain-addressed subscription, hook name unique per
  tool per address, no reinstall required.
- **R2.** The action must be declared in the action catalog as an additive record with
  error class hard; existing catalog records are never rewritten.

### Delivery model

- **R3.** A subscribed hook must be invoked separately for each cell included in the
  schema output; cells pruned by the `cells` / `max_depth` / `depends_on` filters are
  never delivered.
- **R4.** The delivered context must expose the cell's authored facts (identity,
  description, types, usages, dependencies, children) read-only, and a contribution
  method for this tool's per-cell facts; attribute assignment on the context is blocked
  (platform rule).
- **R5.** Each tool receives an isolated view built from authored data only — a tool
  never sees another tool's contributions.
- **R6.** Deliveries must follow deterministic tool-package enumeration order, stable
  across runs.

### Output contract

- **R7.** Tool-contributed facts must appear on the extended cell node under an
  extension area namespaced by the contributing tool's package identity; the namespace
  key is derived by goga from the package name — a tool never names itself, so
  cross-tool collisions are impossible.
- **R8.** The existing node fields — `cell`, `description`, `types`, `usages`,
  `dependencies`, `children` — must remain unchanged in name, form, and content;
  extension only.
- **R9.** The extension area must appear only on cells that received at least one
  contribution; with no tool packages installed or no subscriptions to the schema
  action, the output must be byte-identical to the output before this change.
- **R10.** Every fact in the extension area must be attributable to its contributing
  tool through the structural namespace alone. A contribution that cannot be
  represented in the JSON map is malformed and treated as a failing contribution.

### Failure behavior

- **R11.** A tool hook that crashes during delivery on any cell must stop the schema
  command with a clean error naming the tool and the action; no partial map is printed
  on stdout.
- **R12.** A structurally malformed contribution must be treated identically to a
  crashed hook.
- **R13.** A tool package whose register facade fails to import must stop the command
  with a clean error naming the package.
- **R14.** Registration problems (wrong address, empty or repeated hook name) follow the
  platform rule: a warning naming the tool, action, and reason; the registration is
  skipped; the command continues.

### I/O discipline

- **R15.** stdout must remain data-clean JSON only; all warnings and diagnostics go to
  stderr.
- **R16.** Tool-contributed extensions live in memory for the current run only;
  authored CODEMANIFEST files and any project files must never be modified.

### Consistency

- **R17.** The same project with the same installed tools must produce the identical
  map on every run.

## Constraints

- **C1 (user-stated, mandatory).** Extension-only output — the existing schema node
  fields (`cell`, `description`, `types`, `usages`, `dependencies`, `children`) must
  never be changed, renamed, or removed; with no tools installed the schema output
  stays byte-identical.
- **C2 (platform law).** Catalog additivity — opening the schema action means one new
  record in the action catalog; published records are never rewritten.
- **C3 (platform law).** The extension must run over the existing hooks platform
  semantics — per-tool isolated contexts, fixed-name injection, deterministic
  enumeration, error classes, platform diagnostics. No parallel extension mechanism.
- **C4 (product structure).** The schema extension surface belongs to the schema domain
  as its own hooks zone, following the established `goga/<domain>/hooks` organization.
- **C5 (product law).** Authored sources are immutable — tool contributions live in
  memory for the current run; CODEMANIFEST and project files are never written.
- **C6 (I/O contract).** stdout of the schema command is machine-consumed JSON only;
  every warning or diagnostic goes to stderr.
- **C7 (user-confirmed semantics).** The schema action is hard — the first failing tool
  stops the command; a malformed contribution is treated identically.
- **C8 (user-confirmed shape).** Delivery is per-cell — only cell nodes are extendable,
  not the tree root.

## Scope

### In Scope

- One schema-domain hook action, declared additively in the action catalog with error
  class hard.
- The schema domain hooks zone: the per-cell delivery context (authored cell facts
  read-only + this tool's contribution buffer) and the checkpoint surface over the
  hooks platform facade.
- Integration of the checkpoint into the schema generation moment — delivered for every
  cell surviving the `cells` / `max_depth` / `depends_on` filters, on every entry path
  (CLI command `goga schema` and the schema routine).
- Placement of tool contributions in the output: namespaced per-tool extension area on
  extended cell nodes only; base fields untouched; byte-identical output with no
  subscriptions.
- Hard-failure and diagnostics behavior of `goga schema`: clean error naming the tool
  and the action; registration warnings on stderr; stdout stays data-clean.
- Tool-author documentation for the new subscription surface (the checkpoint usage
  documentation of the zone), so tools integrate without goga code changes.

### Out of Scope

- Any change to the existing schema node fields, filters, or base serialization —
  extension only (C1).
- Tree-root or whole-map extensions — per-cell delivery only (C8).
- Changes to the CODEMANIFEST DSL, the document model, or the AST domain — tool
  extension happens at generation time, not in authored files.
- Changes to the hooks platform itself (catalog semantics, registry, dispatch,
  tool-package enumeration) or new actions in other domains.
- Authoring, publishing, or blessing any concrete `goga_tool_*` package — the ecosystem
  side stays with tool authors.
- Semantic interpretation of tool-contributed facts — goga namespaces and places
  contributions; it does not understand, validate beyond structural form, or act on
  their content.
- Persistence or caching of contributions across runs.

## Success Criteria

- **SC1.** In a project with an installed tool subscribed to the schema action, the
  `goga schema` output carries that tool's contributed facts on the cells it extended,
  under its namespaced extension area.
- **SC2.** A tool package integrates without any goga code change — the documented
  `register_hooks` subscription surface alone is sufficient, and package edits apply
  from the next run without reinstall.
- **SC3.** In a project with no tool packages installed (or none subscribed to the
  schema action), the `goga schema` output is byte-identical to the output before this
  change.
- **SC4.** For every cell node of an extended output, the existing fields (`cell`,
  `description`, `types`, `usages`, `dependencies`, `children`) are exactly what they
  would be without the extension.
- **SC5.** Repeated runs over the same project with the same installed tools produce
  identical output, and every contributed fact is attributable to its tool through the
  namespace alone — no external knowledge needed.
- **SC6.** The new action is visible in the action catalog and in the registry
  inspection (`goga hooks`) alongside the other domains' actions, and the tool-author
  documentation for the schema subscription exists in the same form as the existing
  zones' checkpoint documentation.
- **SC7.** A crashing hook or structurally malformed contribution of a subscribed tool
  stops `goga schema` with a clean error naming the tool and the action — no partial
  JSON on stdout, no raw traceback.
