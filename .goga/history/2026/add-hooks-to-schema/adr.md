# Schema domain hook extension: `amend_cell` action with a wrapper-keyed `tools` area

Installed tool packages get their per-cell facts into the `goga schema` map through one
new hard action `amend_cell` — declared additively in the action catalog
(domain="schema", name="amend_cell", error_class="hard") and delivered per cell over
the existing hooks platform, so the schema domain joins pipeline/build/config/topics in
the uniform domain extension pattern instead of a parallel mechanism. Output is
extension-only: tool facts land on extended cell nodes under a single wrapper key
`tools` — `{"tools": {<tool>: {<fact>: <value>}}}` — and with no contributions the key
is absent everywhere, so the map stays byte-identical to today's.

## Decisions and why

- **Wrapper key `tools`, not flat tool keys on the node.** The flat layout was
  considered and rejected: tool identities are derived from package names
  (`goga_tool_types` → `types`), so flat keys could collide with the six base node
  fields and would freeze the node's top level forever — a future base field could
  clash with an already-deployed tool. The wrapper makes cross-tool and
  tool-vs-goga collisions impossible by construction and lets map consumers separate
  base fields from extensions structurally.
- **Namespace key = platform tool identity.** The canonical hyphen form assigned by
  the environment (`goga_tool_docs` → `docs`) — the same identity used in platform
  warnings and `goga hooks` — so attribution is consistent end-to-end and a tool never
  names itself.
- **Contribution model: one JSON mapping per tool per cell.** Multiple hooks of the
  same tool merge key-wise in registration order, a later write replacing an earlier
  one on key conflict. Empty objects never appear: the `tools` key exists on a node
  iff at least one tool wrote at least one fact on that cell, and a tool's key exists
  iff that tool wrote at least one fact — including the global case of no
  subscriptions → byte-identical output.
- **"Structurally malformed" contribution = not representable in the JSON map**: a
  non-mapping payload, non-string keys, or non-serializable values at any nesting
  level. Treated identically to a crashed hook: the hard action stops the command with
  a clean error naming the tool, the action, and the failing cell path; no partial map
  is printed on stdout.
- **Delivery order: cell-major.** Cells in tree order, tools in package-enumeration
  order within each cell — deterministic run-to-run, and the first hard failure is the
  first failure in that walk order. Only cells surviving the `cells` / `max_depth` /
  `depends_on` filters are delivered.
- **Read view: authored cell facts only.** The delivered context exposes the cell's
  authored facts — path, description, type names, usages file names, dependencies with
  their imported types/usages, children as paths — never another tool's contributions,
  generated data, or the run's filter parameters.

## Open points (owned by the design stage, not this record)

The zone's contract surface — types, signatures, locations, cell boundaries,
Imports/Usages wiring — and the checkpoint's mechanics inside the generation walk.

## Status

accepted (discover interview, rounds 1–4, 2026-09-23)
