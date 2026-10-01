# Project rules

## Layered responsibility for external inputs

Environment coupling lives at the boundary layer, never in the domain core. Configuration is routed by what
consumes it: operational inputs that steer an execution travel as explicit command arguments, while everything
consumed as environment travels only through the dedicated layered environment mechanism; the two channels never
mix, and coordination logic reads only the environment that genuinely belongs to it. The boundary layer resolves
external inputs by a fixed precedence ladder — an explicit argument over a configuration entry over a built-in
default, with a missing configuration file counted as unset — and passes primitive values inward. Parameters that
have no safe built-in default, such as reference revisions, are never silently defaulted to the current state or a
guessed mainline: when no source is present, the command fails up front, before any work, with an error naming both
sources. A resolved reference may be any resolvable revision, is used strictly read-only — never moved or pushed —
and being checked out on it is not an error.

The layered environment mechanism has fixed composition semantics of its own: the launch environment is composed as
a fixed, ordered stack of independent layers that only ever add on top of the inherited environment; composed layers
travel exclusively through the launch routine's environment parameter and apply to that one subprocess alone, and
the surrounding process environment is never mutated — not even temporarily with a restore afterwards. Data that
must cross the execution boundary through a medium that flattens every layer is composed once and carried in two
coordinated transport forms — plain entries plus an encoded payload — regenerated together from the same parsed
source on every launch; the pure encode and decode routines are owned by the shared boundary module that all
consumers already import, so the payload format has exactly one owner and no new modules or dependency edges are
introduced. Collisions between layers resolve uniformly and silently, and precedence protects explicit intent:
values composed by the launching side step aside for keys the user supplied explicitly, layers composed for the
target never override inherited launch-mechanics values, a documented explicit override always keeps winning, and
weaker colliding keys are simply dropped.

Hazardous one-shot external inputs follow the same discipline with a domain-owned ladder: the complete acquisition
ladder — explicit value, streamed content, interactive fallback, clean error — is owned by one routine inside the
responsible domain, and outer surface layers only translate their native options into domain parameters, never
resolving the channel themselves. One-shot channels are never probed eagerly, never read more than once, and are
consumed at exactly one defined resolution point in the flow: an explicit value always wins over streamed content,
undeclared or undecodable content fails as a clean, named error with nothing partially created, and non-interactive
input suppresses interactive prompts. Interactive prompting that resolves a missing input belongs to the outer
command layer, and a domain routine that must interact detects the non-interactive terminal and fails with a clean
error — keeping the domain core usable from non-interactive callers and inner layers independently testable.

Command callbacks stay thin in the same spirit: they only resolve inputs, run the interactive confirmation, delegate
to domain routines, render the result, and propagate the status, passing values through as opaque data without
validating or re-interpreting them — all computation, including scope resolution, projection, filter semantics, and
repository access, lives in domain modules and is never duplicated in the command layer. Grammar and normalization
rules for a value belong exclusively to the domain module. The domain core exposes all-or-nothing read-only
resolution with clean errors and mutation routines that run unconditionally once the caller has confirmed.

Configuration follows a strict provider/consumer split inside the same law. The generic value-provider layer
validates structure only — mapping shape, optional strings, empty-to-absent normalization — and stores values
verbatim, embedding no defaults and checking no semantics; semantic validation, such as allowed strategy values,
template grammar, and built-in defaults, belongs to the consuming domain, which raises the clean configuration
error naming the offending key. Retired keys are neither extracted nor interpreted: stale user-supplied values of
those names pass through silently with no warning, error, or effect, and migration is documented rather than
enforced.

Configuration amendment obeys the same ownership split at every load moment: the amendment checkpoint keeps a
single action, vocabulary, and semantics at every config-consuming load moment on both sides of the boundary, each
side consumes only the fields it owns, and contributions into the other side's fields stay applied but unconsumed
and silent, surfaced only as summary lines. The first failing tool aborts the command with a clean error naming the
tool and the action, before the target launches.

Sensitive host material obeys the same explicitness law at the same boundary: tooling never auto-discovers or
bind-mounts it; provisioning is fully user-owned, expressed as explicit configuration scoped to the single needed
file mounted read-only, and supported by user-facing documentation.

## Decisions before mutations, with staged commits and compensating rollback

Orchestrating algorithms order every read-only check and validation before the first state change, and an operation
first proves that work is needed: a target already carrying the required content is left completely untouched, the
currency check always precedes any reconciliation write, and a repeated invocation stays safe. The same shared rule
feeds both acting operations and read-only markers, and marker queries run purely from local state without network,
degrading to a neutral value instead of raising when an input is unconfigured or unresolvable.

Operations that involve an explicit user confirmation are divided into two phases: a fully inert resolution phase —
no network traffic, no ref writes, no working-copy touch — and an execution phase that performs effects only after
confirmation is granted. Destructive list operations resolve the complete target list first, then present it and ask
exactly one confirmation for the entire batch before any effect begins; an explicit opt-out flag skips the prompt, a
non-interactive invocation without it fails safely rather than hanging or auto-proceeding, and a declined answer
performs nothing at all — zero network operations, zero mutations, no emitted events.

Atomicity of the final effect obeys the same ownership split as rollback. Low-level plumbing reports a conflicting
step by returning a neutral signal rather than raising, keeps every intermediate artifact it builds dangling, and
never moves persisted state on its own — planting the final result is a single ref update owned by the caller, so a
failed exchange leaves nothing half-applied and policy decisions about how to react stay outside the plumbing layer.
Before any irreversible step of a multi-step mutation, the state needed to undo it is captured; when a later step
fails, prior effects are restored by composing existing primitives, exactly one clean error with the root cause is
reported, and a repeated invocation stays safe. The rollback is scoped to the failed sequence — work completed
outside it deliberately remains. Rollback mechanisms belong to the access layer; the decision to roll back belongs
to the caller.

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

## Dependency edges target the owner's facade and respect the fixed direction

All interaction with a subsystem's capabilities — code dependencies and documentation alike — targets the owning unit's
public surface. Internal sub-units are never direct dependency targets; nested capabilities publish their contracts at
the owner's level, and reuse happens through the owner's re-export, never by linking into the depths. New behavior is
owned by a dedicated child cell and only re-exported by its parent facade, which keeps its owns-no-behavior contract;
consumers import from the facade, never from the internal child-cell layout.

When a unit accumulates several functional zones (data, registry, dispatch, access to an external system), it is split
into leaf sub-units by zone, with the main API re-exported on the parent facade; consumers import only the facade. A zone
newly opened inside an existing domain is wired differently: each consumer surface imports the zone contract directly,
the domain facade stays unchanged and receives at most documentation artifacts, and facades are never extended into
re-export layers for zone contracts.

Direction is part of the same law: dependency direction between domains is fixed and one-way, and a reverse edge is
never introduced, whatever reuse it would buy — it creates a cycle that surfaces too late. A contract zone newly opened
inside a domain imports only its own foundational dependency and never imports its consumers; when a fact it needs
resembles a consumer's internal type, the zone defines its own value sets and the consumers project their data into
those records, keeping the dependency graph acyclic. A zone that needs a shared value shape likewise re-declares it
locally in the same form as existing precedent rather than importing another domain's type: zones depend only on the
shared platform and their base dependencies, so no edge is ever drawn between zones of different domains. When the
fixed direction puts a capability out of reach, the fallback is a consumer-side variant, never an edge shortcut.
Specialization therefore lives with the consumer: a domain that needs its own variant of a shared capability creates
the variant inside its own zone, and a provider's internal units are never extended to serve one specific consumer —
misplacement distorts the ownership map, and moving code after materialization is a full migration.

## Minimal structural footprint

New behavior is placed by extending the existing responsibility zones rather than carving out dedicated new modules
for it, and it is implemented with the standard platform library instead of introducing third-party dependencies.
Changes are absorbed into existing responsibility zones, and zones that become dead are deleted; new structural
units, types, or practices are created only when no existing zone can own the new behavior. New capabilities grow
existing zones instead of building parallel paths: a new operation arrives as a sibling resolver that delegates to the
unchanged existing machinery, inheriting its event emission and restore-on-failure behavior; existing modules and
practice documents absorb the new surface; and no new cell, module, or document is created when an existing zone
covers the responsibility. Growth stays frozen to the established structure: existing zones and cells are extended
instead of creating new cells or new dependency edges, so new types travel exclusively along already-established
import paths. No dependency edge may create a cycle.

Wiring is precedent-mirrored in the same spirit: when a new consumer must connect to an extension surface, or a new
extension surface must be created, the integration replicates the project's already-accepted wiring conventions
verbatim — the same connection mechanism, the same internal module organization, and the same style of consumer
usage documentation. Inventing a novel integration mechanism, a separate orchestrator, auto-dispatch, or a
from-scratch surface design is rejected in favor of the established pattern.

## Additive regression-free extension

New functionality enters as a new unit beside the existing ones, never as a mode inside an existing unit. When
behavior is added to an existing routine instead, its contract is extended by appending optional parameters with safe
defaults that read as inherited behavior unchanged and mirror the project's existing wiring precedent — changing only
the call sites that must thread the new levers and leaving unchanged every signature that already carries them — so
every current caller stays valid and unchanged instead of confronting a required parameter or a wholesale-replacement
semantic, and invocation forms that remain supported stay observationally identical in output shape and exit
behavior; no parallel routines duplicating existing logic are ever introduced. The caller owns composing the input;
the routine only applies what it receives. Existing observable behavior, its contracts, and its tests are not edited
and do not acquire new dependencies — including reads of new data sources. Data-model extensions arrive as optional
fields with a safe default so every existing construction site stays valid without edits. Usage imports obey the same
additive law when names clash: a newly imported practice whose key collides with a key the same cell already imports
is brought in through the specification's alias mechanism — under an additional distinct key — while the existing
import and the practice's own name both remain untouched; reusing the bare name, renaming the source, or dropping
one of the two imports is rejected. Extending a structured output with a contributor-keyed area obeys the same law
from the output side: when nothing contributes, the base output stays byte-identical — no empty wrapper objects
appear at any level, and the extension key exists on a node exactly when at least one contributor wrote at least one
fact there. Migrating existing functionality onto a new platform follows the same spirit as a near-rename: domain
objects move unchanged, and only the source of registrations changes (the cell emits the platform's action instead
of running its own enumeration mechanism).

When an established default changes, existing output layouts and frozen interactive flows carry over verbatim, the
previous surface stays reachable under an explicit flag, and pre-approved acceptance criteria are mapped onto the new
contracts before final approval.

## Core-anchored invariants and shared parameters

Guarantees that must hold for every caller are specified and enforced in the core domain contracts, never at a single
entry point; a rule guarded inside one command counts as unenforced, because every other caller could bypass it.
Guard placement follows the guard's nature: value guards anchor on effective — amendable — values inside the domain
orchestrator, early, right after configuration resolution and before the first persistent state write, so every
caller is protected; structural guards stay host-side on the host-effective configuration, before any boundary
command is assembled; and entrypoints remain thin parse-load-delegate shells that own no rules. The same law governs
the command surface: a parameter shared by every subcommand of a command group is declared once on the group itself
and applied implicitly by all subcommands — subcommand surfaces and declared signatures carry no copy of it. The
mechanism that transports the value to the subcommands is an implementation detail kept out of the contract.

The command surface stays sibling-symmetric: a new subcommand mirrors the option surface and naming conventions of its
siblings in the same command group, and a short-form collision with a group-level option is resolved by the group's
established positional disambiguation rule rather than by ad-hoc renames that break symmetry. Routine naming follows
the same surface discipline: a new routine's name literally restates the operation's established glossary definition,
stays self-documenting, and follows the naming style of sibling routines on the same surface; importing vocabulary
from a lower layer or reusing an ambiguous short name is rejected. A naming decision therefore adopts a single
vocabulary anchored to the user-facing concept it serves and to established naming precedent, and propagates it
consistently into every downstream artifact; mixed vocabularies and stale old names leaking into later artifacts are
rejected.

## Unified read path with derived projections

Every user-facing form of a behavior, whether an inspection or preview form or an actual execution, resolves its
inputs through one shared rule set and composition machinery, so identical inputs yield identical composition and
provenance regardless of the surface presenting them. When several views must be produced over the same data, a
single collection pass stays the sole source of facts and every view is computed as a projection over the collected
records; parallel, independent read paths per view are rejected so the views cannot drift apart over time. A filter
is applied at the pipeline stage that preserves the information the other stages still need — which may differ per
view for the same flag — and a filter value that matches nothing yields a valid empty result with success status
rather than an error.

Filter composition follows a fixed algebra: exact-equality matching, repeatable flags, union across values of the same
filter, and conjunction across different filters. Filters only narrow the base eligible set — they can never re-admit
records the primary liveness rule removed — and an unmatched value yields an empty view rather than an error.

Views delivered to subscribed parties during a walk are a purely authored projection of the same collected facts:
fields such as children are filled from the authored document tree, so a delivered view's content is identical in
every run; runtime filters prune which cells are delivered, never the content of a delivered view. Subscribers that
must inspect an assembled structure receive a typed recursive projection with read-only properties, built once per
run; raw mutable mappings are never handed out, and any visibility beyond authored facts is recorded as an explicit
exception.

## Producer-owned outcome reporting with a stable machine-output contract

The module that holds a computed result emits the result itself on its own standard error stream at the moment of
production: signatures remain unchanged, results are not exported outward for a commanding layer to print, and no
additional surfaces are made aware of the result. Console output is owned by the domain module that performs an
operation, while environment-access plumbing stays silent, keeping output policy out of the plumbing layer.

Structured payloads intended for consumption outside the producing module are built as data structures and serialized
programmatically, never hand-escaped as strings. This covers machine-readable output and interactive questions alike:
the parsed structure is re-validated before waiting for an answer, and a damaged question is re-issued as a fresh
numbered turn with identical content instead of being left in place for the user to discover and report.

Output intended for consumption by external tools is published as a consumer contract: record fields are always
present (explicit null instead of omission), later changes stay additive and non-breaking, key ordering is explicitly
non-normative, and the payload is never surrounded by human-oriented decoration. Concrete parameter types chosen at a
boundary mirror the native output of the producing surface, and semantically equivalent empty states are given a
single shared meaning instead of distinct semantics. Recorded facts keep their canonical form under the same
contract: they are written in the fully qualified canonical form that preserves the distinction between differently
scoped names and matches how the reference is displayed, never a compact short form that erases that distinction.

Outcome grading follows the same producer-side discipline under one uniform exit-code and error convention for the
command group: success — including empty result sets, empty operation scopes, and declined confirmations — exits 0,
while usage mistakes and domain failures are kept distinct, map to their separate standardized non-zero exit codes,
and are each reported to the user as one clean message on stderr. Absence of data or an empty result is a successful
run with empty output, never a failure. Hard failures cross the command boundary implementation-agnostically: the
logic layer raises a clean error naming the failing tool, action, and cell path (the package for import failures) with
no dedicated exception type, and the CLI converts every logic-layer failure uniformly — one clean message on stderr,
a non-zero exit, nothing on stdout, and no raw traceback ever reaching the user.

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

External tools follow a minimal-floor dependency policy at the same boundary: a tool is depended on as a host-provided
binary invoked as a subprocess, only the true functional minimum version is pinned as a floor with no upper bound, and
the tool is never installed, updated, or vendored for the user. Every entry point funnels through a single upfront
version gate that fails with a clean error naming the required and the present version.

## Read-only inspection is not interaction

A ban on new operations is read as prohibiting new kinds of interaction, not read-only inspection: a required fact is
grounded by a read-only reader on the owning unit's existing access surface instead of being captured only where the
operation authored it. Read-only logic is likewise extracted rather than embedded in orchestration: a multi-outcome
decision matrix becomes a separate pure read-only classifier routine mirroring existing classification precedent and
pinned by dedicated tests, so orchestration routines stay orchestration and the matrix is testable in isolation.

## Non-invasive moment and event semantics

Observation moments wrap an operation without changing it. The start moment fires once the effective configuration is
resolved, and the completion moment fires on every return path of a started run — success, per-item failure, no-op,
and crash alike — carrying a terminal marker and, for a crash, a reason free of credentials. Nothing fires when the
run aborts at the configuration boundary, the original exception is re-raised after the crash emission, and outputs,
exit codes, and best-effort semantics stay identical under any subscription state.

Event naming stays factual under the same law: an event named after an operation is emitted exactly when that
operation's defining action actually happened, and completions that performed no such action keep their existing
completion event and do not emit it, so an event's name never overstates what occurred.

## Mechanism-agnostic contracts

Contracts express only the abstract order of actions through references to practices and types. Concrete mechanisms,
tool choices, and lifecycle detail are fixed in separate project-level practice documents with executable guidance,
never inside contract annotations.

Documentation coverage per domain has a fixed shape of its own: every domain that participates in hooks carries a
matched pair of usage documents — a registration guide published on the domain facade for external tool authors, and
a checkpoint guide inside the owning hooks zone — and a plan for a new hooks domain includes both levels from the
start. The facade-level guide is wired into every consuming command cell through a usage import so the practice
travels with each integration, and the documentation convention is confirmed against existing code before a plan is
finalized.

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
user-declared pattern with tool output is rejected. When a challenge questions whether a planned artifact exists or
is wired, the claim is re-verified against the codebase and answered with that evidence, and a plan presentation
carries a consolidated table of every artifact with its intended action, so planned artifacts stay trackable across
incremental approvals.

## Atomic convergent change-sets

Every behavior change is planned and landed as one synchronized change-set that rewrites the contract manifests and
the affected practice documentation together with the implementation, so documents never describe superseded
semantics; documentation drift is never deferred to a later stage. When independent workstreams alter the same
contract or routine, they land together as one coherent change-set so that no intermediate state leaves specifications
or usage documentation describing a half-migrated surface.

Deletion follows the same law inside the same change-set: deleting an artifact triggers a repository-wide search for
its name, and every surface still referencing it is realigned or rewritten within that change-set. Once a
configuration channel is removed, its names are neither written nor interpreted: stale user-supplied values of those
names pass through verbatim with no warning, error, or effect, and the breaking removal is accepted deliberately and
recorded in release notes.

## Stage artifact purity

A process stage produces only its designated artifact type; transformations belonging to later stages never start
early. A planning stage does not modify implementation artifacts — materialization belongs to the next stage. Mixing
planning with materialization destroys the workflow's guarantees: unreviewed code changes without an approved plan.
