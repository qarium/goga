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
inputs by a fixed precedence ladder — an explicit argument over a configuration entry over a built-in default, with a
missing configuration file counted as unset — and passes primitive values inward. Parameters that have no safe
built-in default, such as reference revisions, are never silently defaulted to the current state or a guessed
mainline: when no source is present, the command fails up front, before any work, with an error naming both sources.
A resolved reference may be any resolvable revision, is used strictly read-only — never moved or pushed — and being
checked out on it is not an error. Interactive prompting that resolves a missing input belongs to the outer command
layer, and a domain routine that must interact detects the non-interactive terminal and fails with a clean error —
keeping the domain core usable from non-interactive callers and inner layers independently testable.

Command callbacks stay thin in the same spirit: they only resolve inputs, run the interactive confirmation, delegate
to domain routines, render the result, and propagate the status, passing values through as opaque data without
validating or re-interpreting them — all computation, including scope resolution, projection, filter semantics, and
repository access, lives in domain modules and is never duplicated in the command layer. Grammar and normalization
rules for a value belong exclusively to the domain module. The domain core exposes all-or-nothing read-only
resolution with clean errors and mutation routines that run unconditionally once the caller has confirmed. The value
provider performs structural validation only (type and shape), stores values verbatim, embeds no defaults, and checks
no semantics — semantic interpretation and defaulting belong to the consumer.

## Decisions before mutations, with staged commits and compensating rollback

Orchestrating algorithms order every read-only check and validation before the first state change. Destructive list
operations resolve the complete target list first, then present it and ask exactly one confirmation for the entire
batch before any effect begins; an explicit opt-out flag skips the prompt, a non-interactive invocation without it
fails safely rather than hanging or auto-proceeding, and a declined answer performs nothing. Before any irreversible
step of a multi-step mutation, the state needed to undo it is captured; when a later step fails, prior effects are
restored by composing existing primitives, exactly one clean error with the root cause is reported, and a repeated
invocation stays safe. The rollback is scoped to the failed sequence — work completed outside it deliberately
remains. Rollback mechanisms belong to the access layer; the decision to roll back belongs to the caller.

Multi-part delivery follows the same law as staged commits: when a domain must condition its own state on the outcome
of delivered hooks, fire-and-forget emission is insufficient by construction — it collects nothing after the event, so
per-hook outcomes are out of reach. The domain then drives the delivery itself over the platform's public primitives
(registry subscriptions, per-tool contexts, the context wrapping, the argument projection), grouping subscriptions by
tool and committing a tool's contribution only after all of its hooks succeed. The commit point is also the
validation point: after all of a tool's hooks have returned, the merged contribution is checked for structural
validity, and a structurally malformed merged buffer is a hard failure equal to a crashed hook — the tool's entire
contribution is discarded and the walk stops before the next tool is called, preserving first-failure-in-walk-order
semantics under later-wins merging. The platform facade re-exports the primitives for that purpose; the platform
itself is never reworked to return outcomes, delivery is never filtered, and a tool's eligibility stays expressed in
its delivered context (a marker), never in the delivery loop.

## Producer-owned outcome reporting with a stable machine-output contract

The module that holds a computed result emits the result itself on its own standard error stream at the moment of
production: signatures remain unchanged, results are not exported outward for a commanding layer to print, and no
additional surfaces are made aware of the result.

Output intended for consumption by external tools is published as a consumer contract: record fields are always
present (explicit null instead of omission), later changes stay additive and non-breaking, key ordering is explicitly
non-normative, and the payload is never surrounded by human-oriented decoration.

Outcome grading follows the same producer-side discipline under one uniform exit-code and error convention for the
command group: success — including empty result sets, empty operation scopes, and declined confirmations — exits 0,
while usage mistakes and domain failures are kept distinct, map to their separate standardized non-zero exit codes,
and are each reported to the user as one clean message on stderr. Absence of data or an empty result is a successful
run with empty output, never a failure. Hard failures cross the command boundary implementation-agnostically: the
logic layer raises a clean error naming the failing tool, action, and cell path (the package for import failures) with
no dedicated exception type, and the CLI converts every logic-layer failure uniformly — one clean message on stderr,
a non-zero exit, nothing on stdout, and no raw traceback ever reaching the user.

## Unified read path with derived projections

When several views must be produced over the same data, a single collection pass stays the sole source of facts and
every view is computed as a projection over the collected records; parallel, independent read paths per view are
rejected so the views cannot drift apart over time. A filter is applied at the pipeline stage that preserves the
information the other stages still need — which may differ per view for the same flag — and a filter value that
matches nothing yields a valid empty result with success status rather than an error.

Filter composition follows a fixed algebra: exact-equality matching, repeatable flags, union across values of the same
filter, and conjunction across different filters. Filters only narrow the base eligible set — they can never re-admit
records the primary liveness rule removed — and an unmatched value yields an empty view rather than an error.

Views delivered to subscribed parties during a walk are a purely authored projection of the same collected facts:
fields such as children are filled from the authored document tree, so a delivered view's content is identical in
every run; runtime filters prune which cells are delivered, never the content of a delivered view.

## Additive regression-free extension

New functionality enters as a new unit beside the existing ones, never as a mode inside an existing unit. When
behavior is added to an existing routine instead, it arrives as an optional parameter so every current caller stays
valid and unchanged, and invocation forms that remain supported stay observationally identical in output shape and
exit behavior; no parallel routines duplicating existing logic are ever introduced. Existing observable behavior, its
contracts, and its tests are not edited and do not acquire new dependencies — including reads of new data sources.
Data-model extensions arrive as optional fields with a safe default so every existing construction site stays valid
without edits. Extending a structured output with a contributor-keyed area obeys the same law from the output side:
when nothing contributes, the base output stays byte-identical — no empty wrapper objects appear at any level, and the
extension key exists on a node exactly when at least one contributor wrote at least one fact there. Migrating existing
functionality onto a new platform follows the same spirit as a near-rename: domain objects move unchanged, and only
the source of registrations changes (the cell emits the platform's action instead of running its own enumeration
mechanism).

When an established default changes, existing output layouts and frozen interactive flows carry over verbatim, the
previous surface stays reachable under an explicit flag, and pre-approved acceptance criteria are mapped onto the new
contracts before final approval.

## Mechanism-agnostic contracts

Contracts express only the abstract order of actions through references to practices and types. Concrete mechanisms,
tool choices, and lifecycle detail are fixed in separate project-level practice documents with executable guidance,
never inside contract annotations.

Every behavior change is planned as one synchronized change-set that rewrites the contract manifests and the affected
practice documentation together with the implementation, so documents never describe superseded semantics;
documentation drift is never deferred to a later stage.

Documentation coverage per domain has a fixed shape of its own: every domain that participates in hooks carries a
matched pair of usage documents — a domain-level document explaining hook registration to tool authors, and a
zone-level document holding the hooks zone's checkpoints — and a plan for a new hooks domain includes both levels
from the start.

## Fix-in-place verification gates

Correctness is established by executing checks, never by eyeballing: assembled documents have their embedded
structured blocks extracted and parsed, are scanned for unfilled placeholder markers, and have declared locations
checked against the allowed set; behavior change-sets must pass the standard test and lint gates. All verification
runs before the artifact is confirmed or accepted, so defects surface at planning time rather than implementation
time. Defects surfaced by verification are repaired in the artifact itself, and the complete check suite is re-run to
green before approval; approving with known breakage and deferring the repair to a later stage is rejected.

The same gate disciplines plan approval: when the user identifies a missing artifact as a stable project pattern, the
statement is authoritative even when lint passes and the DSL does not demand the artifact — survey the codebase to
confirm the pattern holds, fold the artifact into the plan, and only then re-submit for approval; contradicting a
user-declared pattern with tool output is rejected.

## Core-anchored invariants and shared parameters

Guarantees that must hold for every caller are specified and enforced in the core domain contracts, never at a single
entry point; a rule guarded inside one command counts as unenforced, because every other caller could bypass it. The
same law governs the command surface: a parameter shared by every subcommand of a command group is declared once on
the group itself and applied implicitly by all subcommands — subcommand surfaces and declared signatures carry no copy
of it. The mechanism that transports the value to the subcommands is an implementation detail kept out of the
contract.

The command surface stays sibling-symmetric: a new subcommand mirrors the option surface and naming conventions of its
siblings in the same command group, and a short-form collision with a group-level option is resolved by the group's
established positional disambiguation rule rather than by ad-hoc renames that break symmetry.

## Deterministic identity and liveness resolution

When several candidates normalize to the same identity, the canonical one is selected by a fixed priority order, never
by insertion order or chance. Liveness is anchored to the entity's own authoritative source: a topic exists exactly as
long as its own branch (local or remote-tracking) exists, and that own-branch predicate is the single authoritative
liveness test, applied identically in every view, output mode, and deletion-eligibility check, so records vanish from
all of them the moment the branch is gone. Entities that survive only through secondary sources are excluded from the
primary view and cannot advance its state — a topic whose history survives only on other branches is history, so
requesting its deletion is refused outright with a statement that there is nothing to delete, never an attempted
deletion and never advice to excise its content from surviving branches. Communal merged history belongs to no topic
and is never rewritten or deleted.

Every derived fact about a destructive operation's outcome is computed over the post-operation inventory: the full set
of refs minus the target's own. The target's own branch is never a gate on what remains (its tree dies with it), while
anything a surviving branch still carries — including on-disk directories — is preserved and never deleted.

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

## Domain-owned acquisition of hazardous one-shot inputs

The complete ladder for acquiring an external input — explicit value, streamed content, interactive fallback, clean
error — is owned by one routine inside the responsible domain; outer surface layers only translate their native
options into domain parameters and never resolve the channel themselves. One-shot external channels follow fixed
runtime semantics: they are never probed eagerly and never read more than once, and the channel is consumed at exactly
one defined resolution point in the flow. An explicit value always wins over streamed content; undeclared or
undecodable content fails as a clean, named error with nothing partially created; and non-interactive input suppresses
interactive prompts.

## Minimal structural footprint

New behavior is placed by extending the existing responsibility zones rather than carving out dedicated new modules
for it, and it is implemented with the standard platform library instead of introducing third-party dependencies.
New capabilities grow existing zones instead of building parallel paths: a new operation arrives as a sibling resolver
that delegates to the unchanged existing machinery, inheriting its event emission and restore-on-failure behavior;
existing modules and practice documents absorb the new surface; and no new cell, module, or document is created when
an existing zone covers the responsibility. No dependency edge may create a cycle.

## Stage artifact purity

A process stage produces only its designated artifact type; transformations belonging to later stages never start
early. A planning stage does not modify implementation artifacts — materialization belongs to the next stage. Mixing
planning with materialization destroys the workflow's guarantees: unreviewed code changes without an approved plan.

## Up-front option-combination guards

Meaningless or contradictory option combinations are rejected as the first step of a command with a single actionable
message and a failure exit status — never silently ignored, never surfaced as a raw crash.
