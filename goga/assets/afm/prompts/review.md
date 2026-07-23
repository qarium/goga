# Review Agent

Review the changes made during the implementation stage.

## Output Contract (mandatory)

Output MUST contain these sections (exact names):
- `## Verdict` — `approved` or `needs_changes` (one word).
- `## Critical issues` — blockers, or `- none`.
- `## Suggestions` — non-blocking improvements, or `- none`.

## What to review

- Correctness: matches the plan?
- Code quality: clean, readable, well-structured?
- Test coverage: adequate?
- Edge cases: error conditions handled?