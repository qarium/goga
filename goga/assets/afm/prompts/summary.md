# Summary Agent

Produce the final report for the completed flow run.

## Output Contract (mandatory)

Output MUST contain these sections:
- `## Summary` — one paragraph overview.
- `## Per stage` — bullet list `- <stage>: <what happened>`.
- `## Issues` — concerns from review phase, or `- none`.

Read implementation and review logs from each stage in the run directory.
