# Contract Domain Extension Surface for Tool Packages

## Problem

The hooks platform is the declared extension surface of the goga domains for installed tool packages, and six domains (pipeline, usages, config, schema, build, topics) already expose their extension points — but the contract domain exposes none.

Tool package authors cannot subscribe to the contract workflow at all: no subscription address exists for the contract domain in the action catalog, so a tool that already participates in other domains is blind to the contract comparison. Teams running the contract comparison receive only the built-in output: their installed tools cannot deliver their own context (annotations, verdicts, extra signals) at the point where CODEMANIFEST declarations are checked against the implementation.

The problem matters equally for both sides:

- **Tool package authors** have no way to serve the contract workflow while their tools already serve every other domain — the ecosystem's extension pattern is inconsistent across domains.
- **Teams using goga with tool packages installed** lose tool-computed context exactly at the contract-checking moment and must work around the gap outside the product or go without it.

Evidence: the product documentation states "The contract domain exposes no hook actions of its own for tool packages today", and the action catalog contains no contract-domain records.

The intended direction was decided during definition: the schema domain hooks zone is the precedent. The contract domain receives an amending zone of the same kind — a per-cell read-and-contribute checkpoint where subscribed tools read the cell's comparison facts and contribute their own facts, with the contributions landing in the command's output next to the built-in comparison.

## Users

### Primary users

**Tool package author** — maintains an installed tool package that already subscribes to other goga domains and wants it to participate in the contract workflow too.

- Goal: subscribe the tool to the contract domain's checkpoint so the tool can read the contract comparison context and deliver its own facts there, the same way it already does in other domains.
- What matters: a documented subscription address; a stable, readable context contract; a well-defined contribute mechanism; deterministic delivery order; predictable failure treatment (a clean error naming the tool, the action, and the failing scope — never a raw traceback).

**Contract operator** — the person or AI agent operating goga in a repository where tool packages are installed; runs the contract comparison.

- Goal: see the contract comparison result enriched with the context of the installed tools, without losing the built-in comparison.
- What matters: the output stays complete and trustworthy; tool context is clearly attributable to the tool that produced it; when no tool contributes, behavior is indistinguishable from today; when a tool misbehaves, the failure is explicit and attributable.

### Secondary actors

**goga domain maintainer** — opens the extension point inside the contract domain following the platform's established practice; needs additive catalog extension, a zone matching the precedent's shape, and documentation that stays in sync.

**Output consumers** — automation and AI agents that parse the contract comparison output; need a stable base structure with tool-contributed context structurally separated and absent rather than empty when nothing contributed.

## Goals

1. **Extension surface completeness.** Tool package authors can extend the contract domain of goga the same way they already extend the other domains: a documented, stable subscription point exists in the contract workflow, so a tool can read the contract comparison context and deliver its own facts there.
2. **Tool context in the comparison.** Teams running the contract comparison receive the installed tools' context together with the built-in comparison, clearly attributable to the tool that produced it — so the moment where declarations are checked against the implementation is served by the ecosystem, not only by the built-in analysis.
3. **Trustworthy participation.** Tool participation in the contract workflow is predictable and safe: with no contributing tool the comparison behaves exactly as it does today, and a misbehaving tool surfaces as an explicit, attributable failure rather than silently corrupting the result.

## User Experience

### Decided shape

The contract checkpoint is **per cell**: a subscribed tool reads that cell's comparison facts — the codemanifest/implementation pairs per type and member, exactly as the output composes them — together with the cell's normalized path. The contribution is **per type** (revised during technical discovery; see the ADR): a tool buffers a type-addressed mapping, and the facts of each type land as the tools area of that **type's node** in the command's JSON output, next to the fixed keys `signature`/`properties`/`methods` — mirroring the schema precedent's delivery event, with the landing on the fixed-key node of this command's output.

### Entry points

- The contract operator runs `goga contract [CELLS] [--lang]` in a project where tool packages are installed (language from `--lang` or the effective configuration, as today).
- A tool package author registers a hook of their tool at the contract domain's new subscription address, discovered through the action catalog and the updated contract hooks documentation.
- The goga domain maintainer opens the extension point additively and keeps the documentation in sync.

### Primary flow

1. The operator runs the contract comparison for one or more cells.
2. The built-in comparison is produced for every requested cell exactly as today: declarations parsed, implementation contracts extracted per language, pairs built. Existing failures (unknown cell, implementation package not importable) fire exactly as today — before any hook runs.
3. For each requested cell — deduplicated by normalized path, in first-request order — the checkpoint delivers that cell's comparison facts to the tools subscribed at the contract address, in the platform's enumeration order.
4. Each subscribed tool reads the delivered facts through its own view and buffers its own type-addressed facts; tools are mutually blind.
5. A tool whose every hook succeeded commits its contribution as one unit; the committed facts of each addressed type land on that type's node of the cell's output under the tool's identity.
6. The operator reads the JSON result: the base comparison is unchanged; tool context sits alongside it on the type nodes, attributable per tool per type.

### Alternative flows

- No tool packages installed → the delivery is unobservable; the output is byte-identical to today's.
- Tools installed but none subscribed to the contract address → same byte-identical output.
- Subscribed tools contribute nothing → no tools area appears on any type node (absent, never an empty object).
- Several tools contribute → each under its own identity, in deterministic enumeration order, with repeated writes to the same fact name of the same type resolving to the last write inside one tool's contribution.
- The same cell path requested more than once → one node in the output as today, and one checkpoint delivery.
- A requested cell with no declared types → the checkpoint is delivered over the empty facts; there is no landing zone, so any non-empty contribution for such a cell is the unknown-address hard failure.
- Configuration amendment summary lines still print to stderr before the output, unchanged.

### Failure behavior and recovery

A subscribed tool's hook crashes, its buffered contribution is structurally unrepresentable in the output, or its contribution is addressed to a type the cell does not declare (hard failure class — the error names the offending type as well): the command stops at the first failure with a clean error naming the tool, the action, and the failing cell path — no raw traceback. The offending tool's whole contribution is discarded; nothing partial reaches the output. The operator fixes or uninstalls the tool and re-runs; a fresh run delivers fresh in-memory contributions.

Existing failures keep today's behavior: unknown cell → stderr error and error exit; implementation package not importable → stderr error and error exit; failed configuration load → clean error.

### States, feedback, and consequences

Everything lives in memory for the current run; authored files are never modified — the operation stays read-only analysis. The checkpoint itself prints nothing: the command owns all output. Success feedback is the JSON result; failure feedback is the clean error on stderr with the documented exit-code semantics. Repeating the command with the same inputs and tools yields the same output — delivery is deterministic.

### Documentation experience

The contract hooks documentation changes from "no hook actions today" to describing the new subscription address, what a hook reads, what it may contribute, and the failure treatment; the platform practices (declaring actions, registering hooks, per-tool delivery) apply as written; the hook registration inspection reflects the new registrations.

## Requirements

- **R1 — Extension address.** The contract domain must expose exactly one subscription address for tool packages in the platform's action catalog — domain "contract", action name following the precedent convention (`amend_contract`), failure class hard. The record is published once and never rewritten.
- **R2 — Per-cell delivery.** When the contract comparison runs over requested cells, the product must deliver, for each requested cell, that cell's comparison facts to every tool subscribed at the contract address, in the platform's enumeration order. The delivery covers exactly the cells the operator asked for — no more, no fewer; a path requested more than once is delivered once, in first-request order, and the delivery runs only after the built-in comparison of every requested cell succeeded, so existing failures keep today's precedence over hook failures.
- **R3 — Read view.** A subscribed hook must receive a per-cell view that carries the cell's normalized path and its comparison facts exactly as the command's output composes them: for every declared type and member, the declared (codemanifest) form and the extracted (implementation) counterpart as pairs, including absent counterparts — one language-agnostic shape of string pairs. The delivered facts are read-only; the view exposes no way to alter them, and no way to read another tool's contribution.
- **R4 — Contribute mechanism.** A subscribed tool must be able to contribute its own facts for a cell, addressed per declared type: a mapping from type name to the tool's fact mapping for that type. A tool's contribution commits as one unit — only after every hook of that tool returned without failing and the buffered facts are structurally representable in the output (an address naming a type the cell does not declare is a structural failure). A partially committed or partially discarded contribution of one tool must never appear. Addressing deeper than the type is not composed by the product — a tool organizes member-level notes inside its own fact vocabulary.
- **R5 — Mutual blindness.** Every subscribed tool must receive the same authored comparison facts for a cell; no tool may observe another tool's contribution, buffered or committed.
- **R6 — Output composition.** The command's JSON output must carry, per type node of each compared cell, the committed contributions of the tools under each contributing tool's identity as a distinct tools area — next to the fixed keys signature/properties/methods, so no collision with the type-name namespace of the cell node exists. The area is present on a type node exactly when at least one tool contributed at least one fact for that type; it is absent — never an empty object — otherwise. Inside one tool's contribution for one type, repeated writes to the same fact name resolve to the last write. There is deliberately no cell-level landing: a tool's cell-level context lives inside its per-type facts.
- **R7 — Unchanged baseline.** With no tool packages installed, with none subscribed at the contract address, or with subscriptions that contribute nothing, the output of the command must be identical to the output of the same invocation before the extension existed.
- **R8 — Built-in comparison invariant.** Tool participation must not change the built-in comparison: the base output content (cells, types, members, pairs) must remain exactly what it is without the extension. Tools extend the type nodes with their own area; they cannot modify, remove, or reorder the built-in content and cannot change which cells are compared or the resolved language.
- **R9 — Hard failure.** A hook that fails, a contribution that is not structurally representable in the output, or a contribution addressed to a type the cell does not declare, must stop the command at the first such failure in the delivery with a clean error on stderr naming the tool, the action, and the failing cell path — and, for a bad address, the offending type name — no raw traceback — and the command must exit through its error path. The failing tool's whole contribution is discarded; no output is produced for the run.
- **R10 — Existing failures preserved.** Existing behavior must remain unchanged: unknown cell → stderr error and error exit; implementation package not importable → stderr error and error exit; configuration load failure → clean error. stdout carries only the JSON result; all errors go to stderr; the command help keeps explaining the response structure (now including the tools area semantics) for AI agents.
- **R11 — Determinism and purity.** The same invocation with the same inputs and the same installed tools must produce the same output. Contributions exist only in memory for the current run; the checkpoint must not modify any project or authored file, and must not persist any state between runs.
- **R12 — Documentation.** The product documentation must state the new contract hook action: its address and failure class, what a hook reads, what it may contribute, how contributions appear in the output, and the failure treatment. The current "no hook actions today" statement must be replaced. Tool registration inspection must show hooks registered at the new address.

## Constraints

- **C1 — Platform only.** The extension point must be built on the existing hooks platform: the contract domain declares its action in the catalog and emits at its checkpoint; package enumeration, delivery, envelope validation, error classes, and diagnostics belong to the platform. No parallel extension mechanism may be introduced.
- **C2 — Catalog additivity.** The action catalog is extended additively; a published record's domain, name, and error class are never rewritten. The contract address is durable once published.
- **C3 — Published output surface.** The command's JSON output structure is a published surface documented in the command help for AI agents: the base comparison fields cannot change; the tools area may only be added, and is absent when nothing contributed.
- **C4 — Read-only domain.** The contract workflow is read-only analysis: the solution must not write authored or project files; tool contributions exist in memory for the current run only.
- **C5 — Command conventions.** The command's output discipline and exit-code contract are fixed: stdout carries only the JSON result, all errors go to stderr as clean messages without tracebacks (carrying no credential-bearing values), success exits 0, failures exit through the error path.
- **C6 — Caller-supplied context.** The checkpoint's delivered context is built only from the values the caller passes; the zone itself performs no configuration reads, git access, or file reads, and does not import the domain it extends.
- **C7 — One registry per run.** One hook registry per run carries every checkpoint of the command; delivering the checkpoint over many cells must not multiply the tool package enumeration.
- **C8 — Language-uniform view.** The contract domain serves five implementation languages (python, golang, javascript, kotlin, swift); the per-cell delivered facts must have one language-agnostic shape regardless of the resolved language.

## Scope

### In Scope

- The contract domain's new subscription address in the platform action catalog (domain "contract", hard failure class), published once (R1, C2).
- The contract domain hooks zone as a product surface: the per-cell read-and-contribute view over the cell's comparison facts, the per-tool unit-commit type-addressed contribution model, and the deterministic composition of committed contributions onto the type nodes (R2–R6).
- Integration of the per-cell checkpoint into the contract comparison command: delivery over the requested cells after the built-in comparison, the tools area on each type node of the JSON output, and the unchanged baseline when nothing contributes (R2, R6, R7, R8).
- Hard-failure behavior of the checkpoint wired into the command's documented error path, with existing failure behavior preserved (R9, R10).
- One language-agnostic shape of the delivered facts, working uniformly for all five supported implementation languages (R3, C8).
- Documentation of the new surface: the contract hooks documentation page and the command help's response-structure description (R12).

### Out of Scope

- Notification moments of the contract workflow (started/completed events) — the recorded decision is the amendment-only schema precedent; no run-event facts are added.
- Any change to the built-in comparison itself — new checks, verdicts, diff semantics, or letting tools alter the comparison; tools extend the output only (R8).
- Platform changes — new error classes, delivery styles, registry or enumeration behavior; the platform is consumed as is (C1, C7).
- Rewriting or extending other domains' published catalog records (C2).
- Authoring or shipping any concrete tool package contributions — the ecosystem content belongs to tool authors, not to this change.
- Persisting contributions or introducing cross-run state (C4).
- New operator controls — no flags to disable or configure tool participation; the precedent has none.
- Extending other commands or future contract-domain consumers — none exist today; the checkpoint is delivered where the comparison runs.

## Success Criteria

- **SC1 — Subscribable address.** A tool package author can register a hook at the contract domain's action (visible through hook registration inspection), and the hook is invoked when the contract comparison runs. The action catalog contains exactly one new contract-domain record with the hard failure class.
- **SC2 — Tool context surfaced.** With a subscribed tool contributing facts, the comparison output carries those facts under that tool's identity on the contributed type's node; the built-in comparison stands unchanged alongside them; the same delivered-facts shape is observed for each of the five supported implementation languages.
- **SC3 — Multiple tools.** Contributions of several subscribed tools all appear in one run, each under its own identity, in the platform's enumeration order.
- **SC4 — Unchanged baseline.** With no tool packages installed, no subscriptions, or empty contributions, the command's output is byte-identical to the output of the same invocation before the extension.
- **SC5 — Clean hard failure.** A crashing hook, a structurally unrepresentable contribution, or a contribution addressed to an undeclared type stops the command with a clean stderr error naming the tool, the action, and the failing cell path (and the offending type name for a bad address); the command exits through its error path and produces no result output for that run; after the tool is fixed or uninstalled, a re-run completes cleanly.
- **SC6 — Pure and repeatable.** Running the command with contributing tools changes no project or authored file, and repeated identical invocations produce identical output.
- **SC7 — Documented surface.** The documentation describes the contract hook action — address, error class, what a hook reads, what it may contribute, where contributions appear, and the failure treatment — replacing the current "no hook actions today" statement; the command help explains the tools area semantics of the response structure.
