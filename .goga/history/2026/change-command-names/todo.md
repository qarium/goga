# TODO: Rename propose/brainstorm to specify/prototype and rework the status axis

Rename two pipeline command/skill pairs and realign the history status axis with the new stage names.

- Command `goga:propose` + skill `goga-propose` → `goga:specify` / `goga-specify`
- Command `goga:brainstorm` + skill `goga-brainstorm` → `goga:prototype` / `goga-prototype`
- Status axis: `designed`@arch.md → `prototyped`@arch.md; `specified`@design.md → `designed`@design.md; `backlog`@task.md stays. Final axis: empty, todo, defined, discovered, backlog, prototyped, designed, planned, done

Confirmed decisions:

1. All 13 sub-skills `goga-brainstorm-*` → `goga-prototype-*`
2. `goga-cells-by-brainstorm` → `goga-cells-by-prototype`; `goga-task-by-proposing` → `goga-task-by-specifying`
3. Pipeline stage ids rename too: `propose`→`specify` (refinement), `brainstorm`→`prototype` (development), plus committed `.goga/workflows/*.yml` and docs examples
4. `backlog` stays on task.md; `specified` is dropped from the axis

Mechanism: skills live at `goga/assets/skills/<name>/SKILL.md` (frontmatter `name:` must equal the directory name); commands are `goga/assets/commands/<name>.md` (name = filename); there is no Python registry — `goga connect` installs by the `goga-*` glob and purges stale entries on re-run.

## Safe compound-token substitutions

- `goga-brainstorm-` → `goga-prototype-`, then `goga-brainstorm` → `goga-prototype`, `goga:brainstorm` → `goga:prototype`, `goga-cells-by-brainstorm` → `goga-cells-by-prototype`, `goga-task-by-proposing` → `goga-task-by-specifying`, `goga-propose` → `goga-specify`, `goga:propose` → `goga:specify`
- NEVER substitute bare `propose`/`brainstorm`/`designed`/`specified` globally — only the per-file line edits listed below
- Status-axis replacement order per file: first `designed`→`prototyped`, then `specified`→`designed`

## Batch 1 — Skills (git mv + SKILL.md edits)

1a. `git mv` in `goga/assets/skills/` (17 directories): `goga-propose`→`goga-specify`, `goga-brainstorm`→`goga-prototype`, 13× `goga-brainstorm-*`→`goga-prototype-*`, `goga-cells-by-brainstorm`→`goga-cells-by-prototype`, `goga-task-by-proposing`→`goga-task-by-specifying`.

1b. In each moved SKILL.md: frontmatter `name:`, H1, description ("brainstorm pipeline" → "prototype pipeline"), sub-skill cross-references (token substitutions). Spot edits:

- `goga-specify/SKILL.md`: lines 11, 19 — dispatch to `goga-task-by-specifying`
- `goga-prototype/SKILL.md` (orchestrator): line 3 description, line 9 "brainstorm pipeline", line 90 "brainstorm passes"; line 15 "designed collaboratively" is plain English — do NOT touch
- `goga-cells-by-prototype/SKILL.md`: line 105 → `goga-prototype`
- `goga-task-by-specifying/SKILL.md`: line 12 → `goga-prototype`; keep the "Propose a hypothesis" prose
- Non-moved skills: `goga-apply/SKILL.md` lines 11, 29 (`/goga:brainstorm` → `/goga:prototype`), 36 (`goga-cells-by-brainstorm`); `goga-review-task/SKILL.md` line 9

Do NOT touch (false positives): English verbs propose/proposed in goga-review-design, goga-design-by-changes, goga-define-*, goga-discover; `Status: proposed` in adr-template.md; `/goga:design` **brainstorm mode** in goga-review-cell (102, 188, 217) — a mode of the design command.

## Batch 2 — Commands

`git mv goga/assets/commands/propose.md specify.md`, `brainstorm.md prototype.md`; inside each: H1, "Command dispatcher for …", "invoke the `goga-…` skill".

## Batch 3 — Pipelines and workflows

- `goga/assets/pipelines/refinement.yml`: line 35 `- name: propose` → `specify`; line 45 skill token
- `goga/assets/pipelines/development.yml`: line 5 `- name: brainstorm` → `prototype`; line 29 skill token. Line 27 "propose to user" is a verb — keep
- `.goga/workflows/`: `epic.yml:6`, `refinement.yml:6`, `story.yml:8`, `task.yml:10` — `propose:` → `specify:`; `development.yml:10` — `brainstorm:` → `prototype:`. Keep the "feedbacks, proposes, questions" header comments
- `goga/pipeline/workflow/.usages/memory.md`: lines 45, 62 — `brainstorm:` example stage keys → `prototype:`

Override keys must follow the rename in lockstep, otherwise the overrides silently stop applying.

## Batch 4 — Status axis

⚠️ Per-file replacement order: `designed`→`prototyped`, then `specified`→`designed`.

1. `goga/history/statuses/assembly.py` lines 28-29: `Stage(name="prototyped", filepath="arch.md")`, `Stage(name="designed", filepath="design.md")`
2. `goga/history/statuses/scale.py` lines 53-57 (docstring axis sentence)
3. `goga/history/statuses/CODEMANIFEST` line 50 — the single textual copy of the axis (verified)
4. `goga/history/.usages/topic-statuses.md` lines 8-14
5. Axis-mirroring tests: `tests/history/statuses/conftest.py` (14, 23-24), `test_scale.py` (112-121: `(arch.md, designed)`→`prototyped`, `(design.md, specified)`→`designed`; the `[:8]` slices stay — planned remains index 7), `test_assembly.py` (44-45, 265-266), `tests/history/test_status.py` (55-56, 148-149), `tests/topics/conftest.py` (53, 62-63), `tests/commands/topics/test_topics.py` (1723, 1732-1733), `tests/commands/pipeline/test_pipeline_dispatch.py` (577-578)
6. Optional (semantic alignment only — mocks stay legal either way): `["backlog", "designed"]` mocks in `tests/build/test_build.py` (668, 702, 730), `tests/build/hooks/test_contexts.py` (256, 263), `test_events.py` (432, 473)
7. Axis docs: `docs/features/history/cli.md` lines 59-60 (table), `docs/features/history/index.md:8`, `docs/features/topics/cli.md:51`, `README.md:674`

Statuses are derived from files on disk at every run — no data migration; `.goga/history/2026/*` untouched; `after="planned"` anchors unchanged.

## Batch 5 — MkDocs docs

- `git mv docs/workflow/propose.md specify.md`, `brainstorm.md prototype.md`; `mkdocs.yml` lines 43, 46 (nav) — in the same commit as the moves
- `docs/workflow/specify.md`: H1 `# Specify`, lines 8, 11 (tokens), 91 link to prototype.md
- `docs/workflow/prototype.md`: H1, lines 8, 13, sub-skill table 57-66 plus 119-121, line 81 "brainstormed" → "prototyped"; line 154 is a verb — keep
- `docs/workflow/index.md`: 9-10, 22, 25, 28, 34, 39, 59, 64, 80-81, 95, 97, 111 (chains, links, stage names)
- `docs/workflow/define.md:49`, `discover.md:77`, `change.md:186,189`, `apply.md:59,89`, `review.md:37,40`
- `docs/index.md:73,76,95`; `docs/getting-started.md:101-102,110,147,160,173`; `docs/cli/index.md:63`
- `docs/features/pipelines/index.md:4,13`; `shipped.md:9,90,94,96,109,113`; `pipeline-file.md:67,68,73,97,98,103,107` (stage title "from a user propose" → "from a user specification"); `workflows.md` — update 56, 203, 214, 379, 443, 531-532, 537, 548, 550, 841, 852, 888, 890, 898, 903, 909, 922, 924; keep the invented `propose-review` example (869-880) and `cli.md:193,197`

## Batch 6 — Test sample strings

Substitute skill tokens only; synthetic stage ids (`propose`, `brainstorm`, `propose-review`, …) stay — they do not mirror shipped pipelines (`test_shipped_pipelines_compile.py` is name-agnostic).

- `tests/commands/test_connect.py`: lines 150-151 (skill dirs), **315-321 — re-sort**: `["accept.md","apply.md","change.md","define.md","design.md","discover.md","plan.md","prototype.md","review.md","specify.md","tool.md"]` (compared against `sorted()`)
- Skill tokens in: `tests/pipeline/workflow/test_workflow_stage_contract.py:123,135`; `test_parse_workflow_logic.py:98,105`; `test_workflow_stage_logic.py:99,101`; `tests/pipeline/compiler/test_compile_flow_stage_defaults.py:178,209`; `test_compile_flow_workflow.py:365,1201-1215,1389`; `test_compile_flow_workflow_integration.py:129-141,201-254`; `test_integration.py:163`; `test_serialize_flow.py:33,134`; fixtures `tests/pipeline/compiler/fixtures/{parse_dsl,integration}/{stages,phases}.yml:14`; `tests/integration/fixtures/feature-stages.yml:14,39`, `feature-phases.yml:14,37`

## Batch 7 — README, marketing, traceability

- `README.md`: 29, 111-112, 124, 128, 131, 141, 150-151, 158, 160, 178, 187, 200, 213, 249-257, 285, 290, 588, 593, 644, 674. Do NOT touch the `acme` examples (420-431, 469, 250)
- `docs/overrides/main.html:172`: "Propose → brainstorm → apply → …" → "Specify → prototype → apply → design → plan → build → change → accept…"
- `.goga/tools/mkdocs/traceability.yml:355,359`: doc-path keys → specify.md / prototype.md

Untouched throughout: `.goga/history/2026/*` (except this file), `.goga/memory/*.md`, CHANGELOG.

## Verification

1. `.venv/bin/python -m pytest` (full suite)
2. Identifier invariant — must return zero hits: `grep -rn "goga-propose\|goga:propose\|goga-brainstorm\|goga:brainstorm\|task-by-proposing\|cells-by-brainstorm" goga/ docs/ tests/ README.md mkdocs.yml .goga/workflows/ .goga/tools/`
3. Axis residue check: `grep -rn "specified" goga/history docs/features/history docs/features/topics README.md | grep -v "not specified"` — only intentional English hits
4. `.venv/bin/goga lint` — exit 0 (CODEMANIFEST and .usages were edited)
5. `.venv/bin/mkdocs build --strict` (or without `--strict` if the config does not tolerate it) — catches broken links and nav mismatches
6. Per moved directory: frontmatter `name:` equals the directory name
7. After merge: re-run `goga connect` (purges the old propose.md/brainstorm.md from `~/.goga/commands`) and restart open agent sessions

## Risks

- Double substitution of designed/specified — observe the per-file order
- The sorted list in `test_connect.py:315` fails silently without re-sorting
- `.goga/workflows/*.yml` override keys must rename in lockstep with the pipelines (dead config raises no error)
- No global sed of bare words — compound tokens and enumerated lines only