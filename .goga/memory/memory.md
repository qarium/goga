# Project rules

## Boundary isolation of external interaction

All mechanics of interacting with a human — prompt loops, entry-termination detection, terminal capability checks — belong exclusively to the outermost command layer. Deeper layers receive already-resolved primitive values and stay free of any dependency on the input device or environment.

## Domain-anchored data invariants

Rules governing the integrity of produced data (for example, that an empty artifact can never be created) are stated and enforced in the core contracts, so every entry point — interactive or programmatic — is forced to conform. The outer layers are merely callers of the enforcing core.

## Declarative contract altitude

Contract annotations describe observable behavior — what terminates an entry, how absent or empty input is handled, which error is produced — and never narrate implementation devices or library mechanics. Reusable procedural know-how lives in dedicated practice documents beside their consumers, not inside contracts.

## Total, unambiguous degenerate-state semantics

The state space of inputs and artifacts is enumerated explicitly, with every state keeping a distinct meaning: absence is never conflated with presence that normalizes to nothing; a valued, valueless, and missing option are three separate states; observation never mutates; and unsatisfiable states fail with clean user-facing errors instead of raw crashes.
