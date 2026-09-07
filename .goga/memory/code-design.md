# Project rules

## Confirmed-problem gating

Surprising behavior is checked against intended semantics before being treated as a defect, since a legitimate empty or
terminal state is not a bug to patch. The work item is the problem explicitly named by the user, never a task inferred
from incidental ambient state.

## Root-cause isolation and fix locus

When multiple failure classes arrive together, reproduce and prove each cause separately against authoritative
material — official documentation and the actual runtime sources — before fixing anything; never assume a single shared
cause or diagnose solely from an aggregated CI report. The correction then lands at the single shared dependency that
all affected cases pass through, never in outer orchestration configuration that only masks the symptom for one
execution context, and never as per-case rewrites that work around the symptom.

## Specification-implementation co-evolution

Production code stays exactly within its declared behavioral contract: a failure caused by an unmet environmental
precondition surfaces as a clean error and is repaired on the caller's side, never absorbed by hardening production
beyond what the specification promises. When a defect surfaces at a contract boundary, fix the implementation to satisfy
the existing specification and amend the specification only to state the boundary explicitly, then confirm consistency
through the project's specification validation gates; never rewrite the specification to legitimize buggy behavior,
because altering a specified guarantee is breaking drift.

## Minimal change-set isolation

A fix's diff contains exactly what the approved task requires and nothing more: pre-existing unrelated uncommitted work
is left untouched and explicitly out of scope, so the change set never mixes concerns.

## Hermetic and honest verification

Throwaway test repositories built by a fixture are provisioned at creation time with every piece of configuration their
scenarios can reach, so outcomes never depend on ambient host or runner state; the reason is documented in the fixture
and follows existing precedent fixtures. Validate on the environments where defects actually reproduce, rely on existing
parameterized coverage and the CI matrix for environments unavailable locally, disclose local-coverage gaps explicitly
in every report, and never fabricate coverage by mocking internal components to force unreachable branches.

## Explicit version-stable validation

Encode edge-case semantics explicitly in production validation logic so behavior is identical on every supported runtime
version, rather than relying on standard-library behavior that silently changes between versions.
