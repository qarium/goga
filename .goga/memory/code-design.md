# Project rules

## Contract–implementation co-evolution

Every section of a behavioral contract must agree with the rest: any input surface or requirement declared up front is actually consumed by the algorithm under the declared resolution order, and when the algorithm is corrected, the companion design trace and its derived tests are updated in the same change so no artifact describes a different behavior. User-visible behavior is pinned across the code, the contract manifests, the usage files, and the documentation, so any behavior change updates all of these together in one change, sweeps the repository for residual old wording, and re-runs lint, leaving no specification drift behind. Production code stays exactly within its declared contract: a failure caused by an unmet environmental precondition surfaces as a clean error and is repaired on the caller's side, never absorbed by hardening production beyond what the specification promises. When a defect surfaces at a contract boundary, fix the implementation to satisfy the existing specification and amend the specification only to state the boundary explicitly, then confirm consistency through the project's specification validation gates; never rewrite the specification to legitimize buggy behavior, because altering a specified guarantee is breaking drift.

## Grounded, hermetic, complete, and honest verification

Throwaway test repositories built by a fixture are provisioned at creation time with every piece of configuration their scenarios can reach, so outcomes never depend on ambient host or runner state; the reason is documented in the fixture and follows existing precedent fixtures. Expected values are themselves grounded before they are written: semantics borrowed from external dependencies and the behavior of designed algorithms are established live, via small probe runs against the installed dependency and direct simulation of the algorithm, and the expected outcomes of domain algorithms are derived from the domain's actual rules — eligibility preconditions, priority order, and the canonical ordering scale including its direction — with fixtures constructed from inputs that genuinely satisfy those preconditions, so every expected result is one the real algorithm can produce; recollection of how something should behave is not an acceptable basis, and existing pinned tests serve as the reference for rule direction. A passing suite is still not proof of correct semantics when the expectations themselves pin the wrong behavior: correcting the behavior requires rewriting those enshrined expectations and adding inverse cases at every test level, never preserving them merely because they pass. When the conflict runs the other way and a scenario's expected value disagrees with its own setup, the setup is extended so the case still exercises its intended behavior and the expectation stays meaningful; the expectation is never weakened to the accidentally-passing value, nor is the implementation's contract rewritten to match a mis-written test, because both silently delete the case's intent. When a verification probe fails partway, the probe itself is repaired and re-run, preserving results already verified, rather than continuing on unverified assumptions. Validate on the environments where defects actually reproduce, rely on existing parameterized coverage and the CI matrix for environments unavailable locally, disclose local-coverage gaps explicitly in every report, and never fabricate coverage by mocking internal components to force unreachable branches. Test plans are complete and executable as written: every fixed-order validation branch gets a negative arm, every tri-state knob gets both of its arms, boundary transport rules such as empty collections passing through unchanged are pinned explicitly, and every asymmetry documented in a design's edge-case section is pinned by its own dedicated test with a full trace, because reaching the underlying rule only indirectly through other tests leaves a regression path and does not count as coverage; each added case is a complete trace whose explanatory intermediate-step texts are part of the contract with the implementer and are verified against the real code and corrected where they diverge, even when the final assertions already pass, and every assertion line is syntactically correct, so the approved plan is executable as written rather than debugged downstream.

## Exhaustive and minimal change scoping

A fix's diff contains exactly what the approved task requires and nothing more: pre-existing unrelated uncommitted work is left untouched and explicitly out of scope, so the change set never mixes concerns. Within that approved scope execution is exhaustive — every verified review remark is applied regardless of severity, including test-gap additions and minor-severity precision fixes, never only a narrow factual subset — and affected chains are re-traced with lint re-run clean before completion is reported. When a design changes behavior, or removes or reshapes configuration types and keys, the affected-test inventory is compiled from an untruncated survey of the entire test corpus, unit and integration suites alike, and delivered as an explicit per-file disposition addendum — rewrite, fixture and assertion update, or deletion — with every affected test listed alongside its concrete new expectation instead of being left to the implementer's discretion, and a note on which incidental mentions remain harmless and are confirmed by a run, so the implementing agent executes the plan without further design decisions.

## Confirmed-problem gating

Surprising behavior is checked against intended semantics before being treated as a defect, since a legitimate empty or terminal state is not a bug to patch; the work item is the problem explicitly named by the user, never a task inferred from incidental ambient state. When root-cause analysis establishes that no production defect exists, report the verdict with its full evidence trace and close only the genuine gap — the missing regression coverage for the untested scenario — leaving production code, specifications, and usage documents unchanged; never rework correct logic to appear productive, and never end the effort without protecting the untested seam.

## Root-cause isolation and fix locus

When multiple failure classes arrive together, reproduce and prove each cause separately against authoritative material — official documentation and the actual runtime sources — before fixing anything; never assume a single shared cause or diagnose solely from an aggregated CI report. The correction then lands at the single shared dependency that all affected cases pass through, never in outer orchestration configuration that only masks the symptom for one execution context, and never as per-case rewrites that work around the symptom.

## Own-state and name-based ownership semantics

What belongs to an entity is decided only by the entity's own direct facts, never by incidental associations. Indicators shown in aggregated views are derived from an entity's own direct state, never propagated from related or merged entities that merely carry its history. A branch bearing a topic's exact name is that topic's own branch, with no requirement that its tree carry the topic: deletion of an unpublished topic therefore cascades to that branch, a branchless topic reports an explicit nothing-to-delete outcome, and a topic without its own branch stays invisible on the board.

## Facade–subcommand surface separation

A command module's export list and the subcommands registered on its group are distinct surfaces with distinct counts and distinct tests: registering an additional subcommand changes only the registration surface and is never accommodated by inflating the export contract.

## User-owned presentation conventions

Formatting of visible output — header casing, layout of multi-value cells — is settled by explicit user decision, and that decision overrides both the existing output and any technically valid alternative proposed during implementation.

## Boundary-consistent structural validation

A merge path that accepts amended configuration values enforces the same structural rules the loading boundary already enforces — required strings must be non-blank, path values must be safe, blank normalizes to absent — raising hard errors that name the offending contributor and path instead of producing a configuration the loader itself would reject.

## Final-pass success gating

In a multi-phase execution workflow, terminal whole-run decisions run as a single final pass after all contributing steps complete, never inside the apply loop: validity checks over composed configuration execute only after all winning amendments are applied, so outcomes never depend on amendment order, composition stays pure and all-or-nothing, and companion tests are expressed as order-independent. An output artifact may likewise be relocated to its completed location only when the last required phase exits successfully; a failure of any later phase must leave the artifact in place and propagate a non-zero exit, so the run stays resumable instead of losing its state.

## Degenerate-input guards before side effects

Flows guard degenerate inputs at the very top, before validation, fact construction, and any event emission, honoring the rule that pre-launch failures fire no events; a path already guarded by an upstream launcher is still treated as reachable through direct invocation, and the guard mirrors existing degenerate-case precedents with a logged error and a nonzero exit instead of a traceback.

## Exhaustive error-behavior statements

Cross-cutting error-handling claims enumerate documented exceptions instead of asserting absolutes: when platform documentation defines a fatal case that legitimately escapes unhandled, the design's statement carries that carve-out explicitly rather than resolving the internal contradiction by catching the exception and diverging from platform precedent.

## Key-exact guidance documentation

Usage and practice documents name the exact configuration keys they describe, distinguishing which key each value is written to and where each value is sourced from, because loosely-named keys steer an implementer into writing values to the wrong place; the loose wording itself is replaced.

## Externalized Python environments

All Python virtual environments used for testing and tooling are created and kept outside the project tree, in a dedicated temporary location, with the project installed into them and all test, lint, and CLI tooling run from that interpreter, so the repository never accumulates environment artifacts.
