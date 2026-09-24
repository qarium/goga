# Change: goga-change artifact persistence

Completed fix of the goga-change skill: after a run, the Change Plan and the Final Change
Execution Report existed only in the conversation and were lost. Branch `release/2.0.0`,
25/09/26.

---

## Defect

goga-change was the only workflow in the ecosystem that did not persist its artifacts. Every
sibling workflow (goga-plan, goga-design, goga-define, goga-brainstorm, goga-propose,
goga-discover) writes its artifacts via `goga history path` + `goga history ensure`, and
downstream consumers (goga-review, goga-apply) read artifacts from the history tree. A
goga-change plan and report vanished with the session and were unusable downstream.

## Change Plan (approved)

Gate rule, then typed scheme:

| Decision | Choice |
|---|---|
| Gate | `completed/plan.md` absent in the branch topic → write the record there (marks the topic `done`); present → typed scheme |
| Format | One document: Change Plan + Final Change Execution Report |
| Timing | Persisted once, at Step 11 (reporting) |
| Type | Agent classifies the task: defect fix → `bugs`, enhancement → `patches` (Task Classification of the plan) |
| Topic | Current git branch (no positional argument) |
| Title | Short unique kebab-case slug composed from the task; on collision a different title — numeric suffixes forbidden |

No CLI changes: `goga history path -f` accepts nested filenames verbatim, `completed/plan.md`
is the built-in `done` status anchor, and nested artifacts are honored by `goga history
status`.

## Implemented changes (3 files, +11/-2)

1. `goga/assets/skills/goga-change-reporting/SKILL.md` — Algorithm step 5 "Persist
   artifacts": ensure → gate on `completed/plan.md` → typed fallback with classification,
   title composition, and the collision rule; report the saved path.
2. `goga/assets/skills/goga-change/SKILL.md` — Step 11 Output extended with
   "+ artifacts persisted to the history tree".
3. `docs/workflow/change.md` — "Output artifacts": persisted change record with the gate
   rule; Step 11 references it.

Untouched: `goga-change-planner` (persistence happens at the end only), CLI code, tests
(skill assets carry no test coverage by design).

## Verification

| Check | Result |
|---|---|
| `goga lint` | 81 cells, 0 errors |
| `goga history path -f completed/plan.md` | `.goga/history/2026/release-2-0-0/completed/plan.md` |
| `goga history path -f bugs/smoke-test.md` | nested filename accepted verbatim |
| `goga history status` | intact with nested artifacts |

This document is the first application of the new rule (dogfooding): topic `release-2-0-0`
had no `completed/plan.md`, so the record lands there.
