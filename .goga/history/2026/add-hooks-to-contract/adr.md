# Contract hooks zone: per-cell delivery with per-type contribution landing

## Status

accepted (2026-09-29)

## Context and decision

The contract domain opens its extension surface on the hooks platform along the schema precedent:
one hard catalog record — ("contract", "amend_contract", hard), published once, never rewritten —
and one checkpoint surface consumed by the `goga contract` command. One deliberate deviation from
the precedent was settled during discovery: **the delivery event is per cell, but a tool's
contribution is addressed per declared type and lands as the `tools` area on the type node** (next
to the fixed keys `signature`/`properties`/`methods`), not on the cell node.

Why: the cell node of `goga contract`'s output is a mapping keyed by arbitrary type names, unlike
`goga schema`'s fixed-field cell node. A cell-level `tools` key would live inside the type-name
namespace; a declared type literally named `tools` would force a collision rule in which either the
contribution disappears (bends R6) or the built-in comparison is overwritten (bends R8). The type
node is this command's fixed-key node; landing there eliminates the collision class entirely and
attaches each fact to the node it is about. The generalization left behind: **the tools area lives
on the fixed-key node of a command's output** — the cell node in `schema`, the type node in
`contract`.

## Considered options

- **Per-cell landing (the schema precedent verbatim)** — rejected: needs a reserved-key collision
  rule inside the type-name namespace, and every treatment of the pathological case bends R6 or R8.
- **Per-type delivery** (a checkpoint per cell×type) — rejected: multiplies deliveries and takes
  the whole-cell view away from the tool.
- **Per-cell delivery with per-type addressed landing (chosen)** — the delivery model stays
  identical to the precedent; contributions attach precisely where they belong.

## Related decisions settled in the same interview

- Existing failures keep precedence: the built-in comparison of every requested cell completes
  before any hook runs; delivery then walks the cells in first-request order.
- The delivered facts mirror the cell's comparison structure exactly as the output composes it,
  plus the normalized path — no re-projected facts model; one shape for all five languages (C8).
- Requested paths are deduplicated: one delivery per unique normalized path, in first-request
  order.
- A contribution addressed to a type the cell does not declare is the hard structural failure —
  the clean error names the tool, the action, the cell path, and the offending type name.

## Consequences

- There is deliberately **no cell-level landing**: a tool's cell-level context lives inside its
  per-type facts. Addressing deeper than the type is the tool's own fact vocabulary, not a
  structure goga composes.
- A requested cell with no declared types has no landing zone: the checkpoint is delivered over
  empty facts, and any non-empty contribution for it is the unknown-address hard failure.
- Output consumers read the tools area from type nodes here and from cell nodes in `goga schema`
  — a deliberate difference: each command places the area on its own fixed-key node.
- The PRD was revised accordingly (Decided shape, primary and alternative flows, R2–R4, R6, R8,
  R9, In Scope, SC2, SC5).

## Unresolved questions (for the design stage)

- Zone placement and internal structure: cell boundaries within the contract domain, module
  layout, the names and signatures of the facts view, the contribute surface, and the checkpoint
  entry; CODEMANIFEST structure and Imports/Usages wiring.
- Exact wording of the clean error messages.
