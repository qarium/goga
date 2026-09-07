# Project rules — architecture

## Dependency edges target the owner's facade and respect the fixed direction

All interaction with a subsystem's capabilities — code dependencies and documentation alike — targets the owning unit's
public surface. Internal sub-units are never direct dependency targets; nested capabilities publish their contracts at
the owner's level, and reuse happens through the owner's re-export, never by linking into the depths.

When a unit accumulates several functional zones (data, registry, dispatch, access to an external system), it is split
into leaf sub-units by zone, with the main API re-exported on the parent facade; consumers import only the facade.

Direction is part of the same law: dependency direction between domains is fixed and one-way, and a reverse edge is
never introduced, whatever reuse it would buy — it creates a cycle that surfaces too late. When the fixed direction
puts a capability out of reach, the fallback is a consumer-side variant, never an edge shortcut.

## Single access zone per external system

All operations that reach one external system inside a domain belong to exactly one dedicated leaf unit that owns the
access, mirrors the structure of the existing access leaves, exposes a minimal public surface, and is consumed only
through the domain facade. When the access happens and with what content remains the responsibility of consumer
orchestrations. New capabilities extend that unit's zone instead of spawning a parallel sibling — even when the
extension forces an exception to the zone's established invariants. Extending a zone never rewrites already published
contract fragments: their invariants stay verbatim, and every new allowance is recorded only in the fragments of the
new elements.

## Core-anchored invariants and shared parameters

Guarantees that must hold for every caller are specified and enforced in the core domain contracts, never at a single
entry point; a rule guarded inside one command counts as unenforced, because every other caller could bypass it. The
same law governs the command surface: a parameter shared by every subcommand of a command group is declared once on
the group itself and applied implicitly by all subcommands — subcommand surfaces and declared signatures carry no copy
of it. The mechanism that transports the value to the subcommands is an implementation detail kept out of the
contract.

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

## Graded outcome-to-exit mapping

Absence of data or an empty result is a successful run with empty output, never a failure. Usage mistakes and domain
failures are kept distinct and map to separate standardized non-zero exit codes, each reported to the user as one
clean message — internal tracebacks never reach the output.

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

## Decisions before mutations, with compensating rollback

Orchestrating algorithms order every read-only check and validation before the first state change. Before any
irreversible step of a multi-step mutation, the state needed to undo it is captured; when a later step fails, prior
effects are restored by composing existing primitives, exactly one clean error with the root cause is reported, and a
repeated invocation stays safe. The rollback is scoped to the failed sequence — work completed outside it deliberately
remains. Rollback mechanisms belong to the access layer; the decision to roll back belongs to the caller.

## Mechanism-agnostic contracts

Contracts express only the abstract order of actions through references to practices and types. Concrete mechanisms,
tool choices, and lifecycle detail are fixed in separate project-level practice documents with executable guidance,
never inside contract annotations.

## Closed binding of names in a contract

Every name declared as an imported dependency must be referenced within the contract's own text, and every mention must
resolve within that same contract: either through a declared dependency or through a locally declared practice (when a
direct dependency is impossible — cycles, unreachability). No dangling declarations, no free-floating mentions —
otherwise the contract cannot stand alone and the implementation cannot be rebuilt from it. References use the
contract's own notation, without procedural phrases about where names come from.

## Names state their scope

An operation's name states its exact coverage — never broader than what it does (no implying remote-side effects of a
local-only operation), never narrower. Scope inaccuracy in a name is a contract defect; a rename is applied across all
already produced artifacts so that stages never disagree on names.

## Specialization lives with the consumer

When a domain needs its own variant of a shared capability, the variant is created inside the consumer's zone. A
provider's internal units are never extended to serve one specific consumer — misplacement distorts the ownership map,
and moving code after materialization is a full migration.

## Mode-based safety of destructive operations

Protection in destructive operations comes from explicit prior modes, not from value-based exemptions. A no-execution
report mode previews the full effect before anything is removed; execution itself is unconditional — record attributes
never protect a record from removal. An operation is either unconditional or explicitly scoped by the caller; sparing
modes keyed to the data being destroyed are not invented.

## Stage artifact purity

A process stage produces only its designated artifact type; transformations belonging to later stages never start early.
A planning stage does not modify implementation artifacts — materialization belongs to the next stage. Mixing planning
with materialization destroys the workflow's guarantees: unreviewed code changes without an approved plan.

## One document — one behavior domain

Consumer documentation is structured by behavior domain: a new domain gets its own self-contained document, documents of
unchanged behavior are not edited, and cross-references between sibling documents are not introduced. The set of
documents to touch is decided by this rule, not by the task's original list.

## Fix-in-place verification gates

Defects surfaced by verification are repaired in the artifact itself, and the complete check suite is re-run to green
before approval. Approving with known breakage and deferring the repair to a later stage is rejected.
