# Rename propose/brainstorm to specify/prototype — Change Plan & Execution Report

Task Classification: refactor (planned identifier rename with status-axis rework).
Breaking change: YES — user override obtained at the approval checkpoint.
Source task: `todo.md` in this topic directory.

## Change Plan (approved)

Rename two pipeline command/skill pairs and realign the history status axis:

- `goga:propose` / `goga-propose` → `goga:specify` / `goga-specify`
- `goga:brainstorm` / `goga-brainstorm` → `goga:prototype` / `goga-prototype`
- Sub-skills: 13× `goga-brainstorm-*` → `goga-prototype-*`; `goga-cells-by-brainstorm` → `goga-cells-by-prototype`; `goga-task-by-proposing` → `goga-task-by-specifying`
- Pipeline stage ids: `propose` → `specify` (refinement), `brainstorm` → `prototype` (development), with lockstep override keys in `.goga/workflows/*.yml`
- Status axis: `designed`@arch.md → `prototyped`@arch.md; `specified`@design.md → `designed`@design.md; final axis: empty, todo, defined, discovered, backlog, prototyped, designed, planned, done

Substitution discipline: compound tokens only; per-file axis order `designed`→`prototyped` strictly before `specified`→`designed`; English verbs and acme/propose-review examples untouched.

Affected cells: `goga/history/statuses` (axis contract), `goga/connect` (asset installation), `goga/pipeline/compiler` (stage ids), `goga/pipeline/workflow` (usage examples). Non-cell surfaces: `goga/assets/**`, `.goga/workflows/`, `docs/`, `tests/`, `README.md`, `mkdocs.yml`, `.goga/tools/mkdocs/traceability.yml`.

## Change Execution Report

### Summary

Renamed the propose/brainstorm command/skill surface to specify/prototype across shipped assets, committed workflow overrides, tests, and documentation, and reworked the built-in topic status axis so that `arch.md` marks `prototyped` and `design.md` marks `designed` (the name `specified` is dropped). The change was formally breaking (public identifiers and status names); the pipeline STOP was overridden by explicit user approval, and the whole suite, linters, and doc build verify the new state.

### Root Cause

Not a defect — a planned rename confirmed in `todo.md`. Causal chain verified by investigation: 17 skill directories + 2 command files, stage ids in `goga/assets/pipelines/{refinement,development}.yml`, 5 override keys in `.goga/workflows/`, the axis in `goga/history/statuses` (assembly.py + 3 mirrored copies + 7 axis-mirroring test files).

### Modified Cells

| Cell | Files Modified |
|---|---|
| goga/history/statuses | assembly.py, scale.py, CODEMANIFEST |
| goga/history (usages) | .usages/topic-statuses.md |
| goga/connect (assets) | 17 skill dirs (git mv), commands/{specify,prototype}.md, pipelines/{refinement,development}.yml |
| goga/pipeline/workflow (usages) | .usages/memory.md |
| goga/pipeline/compiler (tests/fixtures) | skill tokens in pipeline tests and fixtures |

### Implemented Changes

| Change | File | Description |
|---|---|---|
| Skills rename | goga/assets/skills/* (17 dirs) | git mv + frontmatter/H1/description/cross-reference token updates |
| Non-moved skill refs | goga-apply/SKILL.md, goga-review-task/SKILL.md | `/goga:prototype`, `goga-cells-by-prototype`, `goga-prototype` references |
| Commands rename | goga/assets/commands/{specify,prototype}.md | git mv + H1/dispatcher/skill invocation |
| Pipeline stage ids | goga/assets/pipelines/refinement.yml, development.yml | `- name: specify` / `- name: prototype` + skill tokens |
| Workflow overrides | .goga/workflows/{epic,refinement,story,task,development}.yml | `specify:` / `prototype:` keys in lockstep |
| Status axis | goga/history/statuses/{assembly.py,scale.py,CODEMANIFEST} | ordered substitution: designed→prototyped, then specified→designed |
| Axis usage doc | goga/history/.usages/topic-statuses.md | axis enumeration updated |
| Workflow usage doc | goga/pipeline/workflow/.usages/memory.md | example stage keys `prototype:` |
| Axis tests | 7 test files + tests/build mocks | axis mirrors and mocks aligned |
| Connect tests | tests/commands/test_connect.py | renamed skill dirs + re-sorted command list |
| Pipeline tests/fixtures | tests/pipeline/**, tests/integration/fixtures | skill tokens substituted; synthetic stage ids kept |
| MkDocs docs | docs/workflow/{specify,prototype}.md (git mv), mkdocs.yml nav, ~15 pages | tokens, chains, links, nav |
| README / marketing | README.md, docs/overrides/main.html, .goga/tools/mkdocs/traceability.yml | stage chains, doc-path keys; acme examples preserved |

### Tests Added

None — the change renames data literals; the existing parametrized suites pin the full new state (axis progression table, axis member lists, connect installation, pipeline compilation). Regression tests for old names are inapplicable to an intentional rename.

### Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga/history/statuses | `StatusScale` Requirement axis sentence: backlog, prototyped, designed, planned, done | topic-statuses.md axis enumeration |
| goga/pipeline/workflow | — | memory.md example stage keys |

### Validation Results

VERIFIED — full suite 6176 passed / 0 failed; `goga lint` 81 cells 0 errors; `mkdocs build --strict` exit 0; identifier invariant grep returns zero hits; axis residue grep returns zero hits; frontmatter `name:` equals directory name for all 17 moved skills.

### Compatibility Status

BREAKING (formal): renamed status axis names (public paths, CLI output, file paths). STOP overridden by user decision at the approval checkpoint. Post-merge action: re-run `goga connect` (purges old propose.md/brainstorm.md from `~/.goga/commands`) and restart open agent sessions.

### Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Double substitution designed/specified | High | per-file ordered substitution applied and re-verified by greps |
| Dead workflow override keys | High | 5 keys renamed in lockstep; invariant grep clean |
| Stale `~/.goga` entries after merge | Medium | re-run `goga connect` (documented post-merge step) |
| External status consumers using `specified` | Medium | breaking change announced; user-approved |

### Updated Files

- .goga/tools/mkdocs/traceability.yml
- .goga/workflows/development.yml
- .goga/workflows/epic.yml
- .goga/workflows/refinement.yml
- .goga/workflows/story.yml
- .goga/workflows/task.yml
- README.md
- docs/cli/index.md
- docs/features/history/cli.md
- docs/features/history/index.md
- docs/features/pipelines/index.md
- docs/features/pipelines/pipeline-file.md
- docs/features/pipelines/shipped.md
- docs/features/pipelines/workflows.md
- docs/features/topics/cli.md
- docs/getting-started.md
- docs/index.md
- docs/overrides/main.html
- docs/workflow/apply.md
- docs/workflow/change.md
- docs/workflow/define.md
- docs/workflow/discover.md
- docs/workflow/index.md
- docs/workflow/review.md
- docs/workflow/propose.md → docs/workflow/specify.md (git mv)
- docs/workflow/brainstorm.md → docs/workflow/prototype.md (git mv)
- mkdocs.yml
- goga/assets/commands/propose.md → goga/assets/commands/specify.md (git mv)
- goga/assets/commands/brainstorm.md → goga/assets/commands/prototype.md (git mv)
- goga/assets/pipelines/development.yml
- goga/assets/pipelines/refinement.yml
- goga/assets/skills/goga-propose/ → goga/assets/skills/goga-specify/ (git mv)
- goga/assets/skills/goga-brainstorm/ → goga/assets/skills/goga-prototype/ (git mv)
- goga/assets/skills/goga-brainstorm-*/ → goga/assets/skills/goga-prototype-*/ (13 dirs, git mv)
- goga/assets/skills/goga-cells-by-brainstorm/ → goga/assets/skills/goga-cells-by-prototype/ (git mv)
- goga/assets/skills/goga-task-by-proposing/ → goga/assets/skills/goga-task-by-specifying/ (git mv)
- goga/assets/skills/goga-apply/SKILL.md
- goga/assets/skills/goga-review-task/SKILL.md
- goga/history/.usages/topic-statuses.md
- goga/history/statuses/CODEMANIFEST
- goga/history/statuses/assembly.py
- goga/history/statuses/scale.py
- goga/pipeline/workflow/.usages/memory.md
- tests/build/hooks/test_contexts.py
- tests/build/hooks/test_events.py
- tests/build/test_build.py
- tests/commands/pipeline/test_pipeline_dispatch.py
- tests/commands/test_connect.py
- tests/commands/topics/test_topics.py
- tests/history/statuses/conftest.py
- tests/history/statuses/test_assembly.py
- tests/history/statuses/test_scale.py
- tests/history/test_status.py
- tests/integration/fixtures/feature-phases.yml
- tests/integration/fixtures/feature-stages.yml
- tests/pipeline/compiler/fixtures/integration/phases.yml
- tests/pipeline/compiler/fixtures/integration/stages.yml
- tests/pipeline/compiler/fixtures/parse_dsl/phases.yml
- tests/pipeline/compiler/fixtures/parse_dsl/stages.yml
- tests/pipeline/compiler/test_compile_flow_stage_defaults.py
- tests/pipeline/compiler/test_compile_flow_workflow.py
- tests/pipeline/compiler/test_compile_flow_workflow_integration.py
- tests/pipeline/compiler/test_integration.py
- tests/pipeline/compiler/test_serialize_flow.py
- tests/pipeline/workflow/test_parse_workflow_logic.py
- tests/pipeline/workflow/test_workflow_stage_contract.py
- tests/pipeline/workflow/test_workflow_stage_logic.py
- tests/topics/conftest.py

Environment note: the project venv was not used; verification ran in an external virtualenv at `/home/goga/.venvs/goga-rename`.
