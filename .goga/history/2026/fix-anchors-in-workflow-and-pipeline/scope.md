# Scope Resolution Report

## Task Summary

YAML links (anchors `&`, aliases `*`, and merge keys `<<:`) are not supported in workflow files and pipeline files. Users need to declare reusable "starting points" — a hidden top-level key such as `.anchor: &anchor` holding shared content — and merge them into mapping nodes (e.g. `stages: <<: *anchor`). Today such declarations cause parsing issues. The task: make anchor/alias/merge-key declarations parse cleanly in both file families without breaking existing behavior.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga/pipeline/compiler` | Parses pipeline DSL files via `yaml.safe_load` twice — header and body are parsed as separate texts (`parse_dsl.py:114`, `parse_dsl.py:493`); anchors declared at file top land in one text and aliases/merges referencing them from the other text cannot resolve; structural validation may reject unknown top-level keys like `.anchor` | P1 |
| `goga/pipeline/workflow` | Parses workflow files via `yaml.safe_load(text)` (`parse_workflow.py:236`) with strict key validation; a top-level `.anchor` key and merge keys inside `stages` must survive parsing | P1 |
| `goga/pipeline` | Owns discovery of `*.yml` pipeline files and `resolve_workflow` — the loading paths that feed both parsers; participates behaviorally if file text is pre-processed before parsing | P2 |

## Included Dependencies

| Cell | Behavioral Relevance |
|------|---------------------|
| `goga/pipeline/workflow` (dep of compiler, hooks) | Source of workflow-file parsing; anchor handling must be traced here regardless of caller |
| `goga/pipeline/compiler` (dep of `goga/pipeline`) | Source of pipeline-file parsing; header/body split is the likely anchor-breaking mechanism |

## Excluded Dependencies

| Cell | Exclusion Reason |
|------|------------------|
| `goga/pipeline/hooks` | Consumes already-parsed `WorkflowDocument` types; overlay merge works on parsed dicts, never on YAML text — infrastructural-only relevance |
| `goga/config/yaml` | `parse_env_yaml` serves the project/tool configuration family only; workflow and pipeline files do not load through it |
| `goga/afm` | Subprocess wrapper over the external `afm` binary; no YAML parsing |
| `goga/commands/pipeline` | Host-side Docker launcher; no YAML parsing |
| `goga/config`, `goga/docker`, `goga/history`, `goga/agents` | Run-coordination infrastructure; no participation in file parsing |

## Usage Relationships

| Usage | Relevance |
|-------|-----------|
| `goga/pipeline/compiler/.usages/parse-dsl.md` | Documents pipeline DSL parsing contract; must reflect anchor support after the change |
| `goga/pipeline/workflow/.usages/parse-workflow.md` | Documents workflow parsing contract; must reflect anchor support after the change |
| `goga/pipeline/workflow/.usages/load-workflow.md` | Workflow file loading path — participates if loading preprocesses text |
| `goga/pipeline/compiler/.usages/compile-flow.md`, `serialize-flow.md` | Downstream of `parse_dsl`; participate only if the parsed body shape changes |

## Semantic Participation Summary

Both file families parse through exactly two cells: pipeline files via `parse_dsl` (compiler) and workflow files via `parse_workflow` (workflow). `goga/pipeline` discovers and hands the file texts to these parsers. Any anchor/alias/merge-key behavior therefore lives in these three cells; cells downstream of the parsed documents (hooks overlay, flow serialization) see only plain dicts and do not participate.

## Final Investigation Scope

- `goga/pipeline/compiler` — `parse_dsl` header/body split and structural validation
- `goga/pipeline/workflow` — `parse_workflow` loading and key validation
- `goga/pipeline` — discovery/loading paths (`list_pipelines`, `resolve_workflow`, run/describe callers) that feed the parsers

## Scope Risks

- **Under-scoping**: fixing only one parser (e.g. workflow) leaves pipeline files broken — the task names both families.
- **Under-scoping**: the header/body split in `parse_dsl` may require whole-file anchor resolution before splitting; a fix local to one `safe_load` call would miss cross-section anchors.
- **Over-scoping**: routing these parsers through `goga/config/yaml` (`parse_env_yaml`) or touching the hooks overlay would pull in unrelated config-family behavior.

## Notes

- Branch `fix-anchors-in-workflow-and-pipeline` is at `main` with no prior work; only this history topic directory exists.
- The task's example uses a dot-prefixed top-level key (`.anchor`) — a "hidden key" idiom; both parsers' unknown-key validation must tolerate (and presumably ignore) it.
