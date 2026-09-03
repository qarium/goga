# Project rules

## Independent Root-Cause Isolation

When multiple failure classes arrive together, reproduce and prove each cause separately against authoritative sources
such as official documentation and actual runtime sources before fixing anything; never assume a single shared cause or
diagnose solely from an aggregated CI report.

## Specification-Implementation Co-Evolution

When a defect surfaces at a contract boundary, fix the implementation to satisfy the existing specification and amend
the specification only to state the boundary explicitly, then confirm consistency through the project's specification
validation gates; never rewrite the specification to legitimize buggy behavior.

## Explicit Version-Stable Validation

Encode edge-case semantics explicitly in production validation logic so behavior is identical on every supported runtime
version, rather than relying on standard-library behavior that silently changes between versions.

## Honest Verification Scope

Validate on the environments where the defects actually reproduce, rely on existing parameterized coverage and the CI
matrix for environments unavailable locally, disclose local-coverage gaps explicitly in every report, and never
fabricate coverage by mocking internal components to force unreachable branches.
