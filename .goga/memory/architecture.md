# Project rules

## Dependency edges target the owner's facade and respect the fixed direction

All interaction with a subsystem's capabilities — code dependencies and documentation alike — targets the owning unit's
public surface. Internal sub-units are never direct dependency targets; nested capabilities publish their contracts at
the owner's level, and reuse happens through the owner's re-export, never by linking into the depths.

When a unit accumulates several functional zones (data, registry, dispatch, access to an external system), it is split
into leaf sub-units by zone, with the main API re-exported on the parent facade; consumers import only the facade. A zone
newly opened inside an existing domain is wired differently: each consumer surface imports the zone contract directly,
the domain facade stays unchanged and receives at most documentation artifacts, and facades are never extended into
re-export layers for zone contracts.

Direction is part of the same law: dependency direction between domains is fixed and one-way, and a reverse edge is
never introduced, whatever reuse it would buy — it creates a cycle that surfaces too late. When the fixed direction
puts a capability out of reach, the fallback is a consumer-side variant, never an edge shortcut. Specialization
therefore lives with the consumer: a domain that needs its own variant of a shared capability creates the variant
inside its own zone, and a provider's internal units are never extended to serve one specific consumer — misplacement
distorts the ownership map, and moving code after materialization is a full migration.

## Layered responsibility for external inputs

Environment coupling lives at the boundary layer, never in the domain core. The boundary layer resolves external
inputs — source precedence of explicit argument over configuration over built-in default — and passes primitive values
inward; interactive prompting that resolves a missing input belongs to the outer command layer, and a domain routine
that must interact detects the non-interactive terminal and fails with a clean error — keeping the domain core usable
from non-interactive callers and inner layers independently testable. Command callbacks stay thin in the
same spirit: they only resolve inputs, delegate to domain routines, and render results, passing values through as
opaque data without validating or re-interpreting them — grammar and normalization rules for a value
belong exclusively to the domain module. The domain core exposes all-or-nothing read-only resolution with clean errors
and mutation routines that run unconditionally once the caller has confirmed. The value provider performs structural
validation only (type and shape), stores values verbatim, embeds no defaults, and checks no semantics — semantic
interpretation and defaulting belong to the consumer.

## Domain-owned acquisition of hazardous one-shot inputs

The complete ladder for acquiring an external input — explicit value, streamed content, interactive fallback, clean
error — is owned by one routine inside the responsible domain; outer surface layers only translate their native
options into domain parameters and never resolve the channel themselves. One-shot external channels follow fixed
runtime semantics: they are never probed eagerly and never read more than once, and the channel is consumed at exactly
one defined resolution point in the flow. An explicit value always wins over streamed content; undeclared or
undecodable content fails as a clean, named error with nothing partially created; and non-interactive input suppresses
interactive prompts.

## Unified read path with derived projections

When several views must be produced over the same data, a single collection pass stays the sole source of facts and
every view is computed as a projection over the collected records; parallel, independent read paths per view are
rejected so the views cannot drift apart over time. A filter is applied at the pipeline stage that preserves the
information the other stages still need — which may differ per view for the same flag — and a filter value that
matches nothing yields a valid empty result with success status rather than an error.

## Additive regression-free extension

New functionality enters as a new unit beside the existing ones, never as a mode inside an existing unit. When
behavior is added to an existing routine instead, it arrives as an optional parameter so every current caller stays
valid and unchanged, and invocation forms that remain supported stay observationally identical in output shape and
exit behavior; no parallel routines duplicating existing logic are ever introduced. Existing observable behavior, its
contracts, and its tests are not edited and do not acquire new dependencies — including reads of new data sources.
Data-model extensions arrive as optional fields with a safe default so every existing construction site stays valid
without edits. Migrating existing functionality onto a new platform follows the same spirit as a near-rename: domain
objects move unchanged, and only the source of registrations changes (the cell emits the platform's action instead of
running its own enumeration mechanism).

When an established default changes, existing output layouts and frozen interactive flows carry over verbatim, the
previous surface stays reachable under an explicit flag, and pre-approved acceptance criteria are mapped onto the new
contracts before final approval.

## Producer-owned outcome reporting with a stable machine-output contract

The module that holds a computed result emits the result itself on its own standard error stream at the moment of
production: signatures remain unchanged, results are not exported outward for a commanding layer to print, and no
additional surfaces are made aware of the result.

Output intended for consumption by external tools is published as a consumer contract: record fields are always
present (explicit null instead of omission), later changes stay additive and non-breaking, key ordering is explicitly
non-normative, and the payload is never surrounded by human-oriented decoration.

Outcome grading follows the same producer-side discipline: absence of data or an empty result is a successful run with
empty output, never a failure. Usage mistakes and domain failures are kept distinct and map to separate standardized
non-zero exit codes, each reported to the user as one clean message — internal tracebacks never reach the output.

## Decisions before mutations, with staged commits and compensating rollback

Orchestrating algorithms order every read-only check and validation before the first state change. Before any
irreversible step of a multi-step mutation, the state needed to undo it is captured; when a later step fails, prior
effects are restored by composing existing primitives, exactly one clean error with the root cause is reported, and a
repeated invocation stays safe. The rollback is scoped to the failed sequence — work completed outside it deliberately
remains. Rollback mechanisms belong to the access layer; the decision to roll back belongs to the caller.

Multi-part delivery follows the same law as staged commits: when a domain must condition its own state on the outcome
of delivered hooks, fire-and-forget emission is insufficient by construction — it collects nothing after the event, so
per-hook outcomes are out of reach. The domain then drives the delivery itself over the platform's public primitives
(registry subscriptions, per-tool contexts, the context wrapping, the argument projection), grouping subscriptions by
tool and committing a tool's contribution only after all of its hooks succeed. The platform facade re-exports the
primitives for that purpose; the platform itself is never reworked to return outcomes, delivery is never filtered, and
a tool's eligibility stays expressed in its delivered context (a marker), never in the delivery loop.

## Deterministic identity resolution

When several candidates normalize to the same identity, the canonical one is selected by a fixed priority order, never
by insertion order or chance; entities that survive only through secondary sources are excluded from the primary view
and cannot advance its state.

## Up-front option-combination guards

Meaningless or contradictory option combinations are rejected as the first step of a command with a single actionable
message and a failure exit status — never silently ignored, never surfaced as a raw crash.

## Minimal structural footprint

New behavior is placed by extending the existing responsibility zones rather than carving out dedicated new modules
for it, and it is implemented with the standard platform library instead of introducing third-party dependencies.

## Single access zone per external system

All operations that reach one external system inside a domain belong to exactly one dedicated leaf unit that owns the
access, mirrors the structure of the existing access leaves, exposes a minimal public surface, and is consumed only
through the domain facade. When the access happens and with what content remains the responsibility of consumer
orchestrations. New capabilities extend that unit's zone instead of spawning a parallel sibling — even when the
extension forces an exception to the zone's established invariants. Extending a zone never rewrites already published
contract fragments: their invariants stay verbatim, and every new allowance is recorded only in the fragments of the
new elements.

The zone is entered through its thin launcher exclusively: an external execution engine is invoked only through that
launcher — never bypassed, never through side channels. The launcher's fixed option-to-flag mapping is extended
additively when new options must be supported, and all option-resolution logic stays in the calling module rather than
moving into the launcher.

## Core-anchored invariants and shared parameters

Guarantees that must hold for every caller are specified and enforced in the core domain contracts, never at a single
entry point; a rule guarded inside one command counts as unenforced, because every other caller could bypass it. The
same law governs the command surface: a parameter shared by every subcommand of a command group is declared once on
the group itself and applied implicitly by all subcommands — subcommand surfaces and declared signatures carry no copy
of it. The mechanism that transports the value to the subcommands is an implementation detail kept out of the
contract.

## Stage artifact purity

A process stage produces only its designated artifact type; transformations belonging to later stages never start
early. A planning stage does not modify implementation artifacts — materialization belongs to the next stage. Mixing
planning with materialization destroys the workflow's guarantees: unreviewed code changes without an approved plan.

## Fix-in-place verification gates

Defects surfaced by verification are repaired in the artifact itself, and the complete check suite is re-run to green
before approval. Approving with known breakage and deferring the repair to a later stage is rejected.

## Mechanism-agnostic contracts

Contracts express only the abstract order of actions through references to practices and types. Concrete mechanisms,
tool choices, and lifecycle detail are fixed in separate project-level practice documents with executable guidance,
never inside contract annotations.
