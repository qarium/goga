# Project rules

## Contract–implementation co-evolution

Every section of a behavioral contract must agree with the rest: any input surface or requirement declared up front is actually consumed by the algorithm under the declared resolution order, and when the algorithm is corrected, the companion design trace and its derived tests are updated in the same change so no artifact describes a different behavior. Production code stays exactly within its declared contract: a failure caused by an unmet environmental precondition surfaces as a clean error and is repaired on the caller's side, never absorbed by hardening production beyond what the specification promises. When a defect surfaces at a contract boundary, fix the implementation to satisfy the existing specification and amend the specification only to state the boundary explicitly, then confirm consistency through the project's specification validation gates; never rewrite the specification to legitimize buggy behavior, because altering a specified guarantee is breaking drift.

## Exhaustive and minimal change scoping

A fix's diff contains exactly what the approved task requires and nothing more: pre-existing unrelated uncommitted work is left untouched and explicitly out of scope, so the change set never mixes concerns. When a design removes or reshapes configuration types and keys, the affected-consumer list is built from an untruncated survey of the whole test tree and delivered as an explicit per-file disposition addendum — rewrite, fixture and assertion update, or deletion — alongside a note on which incidental mentions remain harmless and are confirmed by a run, so the implementing agent executes the plan without further design decisions.

## Degenerate-input guards before side effects

Flows guard degenerate inputs at the very top, before validation, fact construction, and any event emission, honoring the rule that pre-launch failures fire no events; a path already guarded by an upstream launcher is still treated as reachable through direct invocation, and the guard mirrors existing degenerate-case precedents with a logged error and a nonzero exit instead of a traceback.

## Hermetic, complete, and honest verification

Throwaway test repositories built by a fixture are provisioned at creation time with every piece of configuration their scenarios can reach, so outcomes never depend on ambient host or runner state; the reason is documented in the fixture and follows existing precedent fixtures. Validate on the environments where defects actually reproduce, rely on existing parameterized coverage and the CI matrix for environments unavailable locally, disclose local-coverage gaps explicitly in every report, and never fabricate coverage by mocking internal components to force unreachable branches. Test plans are complete and executable as written: every fixed-order validation branch gets a negative arm, every tri-state knob gets both of its arms, and boundary transport rules such as empty collections passing through unchanged are pinned explicitly; each added case is a complete trace and every assertion line is syntactically correct, so the approved plan is executable as written rather than debugged downstream.

## Key-exact guidance documentation

Usage and practice documents name the exact configuration keys they describe, distinguishing which key each value is written to and where each value is sourced from, because loosely-named keys steer an implementer into writing values to the wrong place; the loose wording itself is replaced.

## Exhaustive error-behavior statements

Cross-cutting error-handling claims enumerate documented exceptions instead of asserting absolutes: when platform documentation defines a fatal case that legitimately escapes unhandled, the design's statement carries that carve-out explicitly rather than resolving the internal contradiction by catching the exception and diverging from platform precedent.

## Confirmed-problem gating

Surprising behavior is checked against intended semantics before being treated as a defect, since a legitimate empty or terminal state is not a bug to patch. The work item is the problem explicitly named by the user, never a task inferred from incidental ambient state.

## Root-cause isolation and fix locus

When multiple failure classes arrive together, reproduce and prove each cause separately against authoritative material — official documentation and the actual runtime sources — before fixing anything; never assume a single shared cause or diagnose solely from an aggregated CI report. The correction then lands at the single shared dependency that all affected cases pass through, never in outer orchestration configuration that only masks the symptom for one execution context, and never as per-case rewrites that work around the symptom.

## Explicit version-stable validation

Encode edge-case semantics explicitly in production validation logic so behavior is identical on every supported runtime version, rather than relying on standard-library behavior that silently changes between versions.
