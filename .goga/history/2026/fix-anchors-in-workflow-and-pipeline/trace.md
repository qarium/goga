# Trace Report

## Call Flow

Workflow-file path (`goga/pipeline/workflow`):

```
goga/pipeline.run_pipeline / describe_pipeline
  → resolve_workflow(pipeline_name, workflow_name, no_workflow, …)      [goga/pipeline]
    → load_workflow(workflow_path, …)                                   [goga/pipeline/workflow]
      → workflow_path.read_text()
      → _peek_literal_profile(text)          (raw `profile:` line scan — unaffected by anchors)
      → render_workflow(text, profile.data)  (whole-file Jinja — no anchor interaction)
      → parse_workflow(rendered)             [parse_workflow.py:236]
        → yaml.safe_load(text)               (anchors/aliases/`<<:` merges resolve natively)
        → _extract_top_level(loaded)         [parse_workflow.py:373-401]
          → strict unknown-key rejection: `unknown key in workflow: KEY` (line 401)
```

Pipeline-file path (`goga/pipeline/compiler`):

```
goga/pipeline.run_pipeline:113 / describe_pipeline:123 / describe_pipelines:45 / compiler.compile_flow:2535
  → parse_dsl(text)                          [parse_dsl.py:461]
    → _split_segments(text)                  (regex split on first `^---\r?$` line)
    → _parse_header(header_text)             → yaml.safe_load #1  [parse_dsl.py:114]
    → yaml.safe_load(body_text)              → yaml.safe_load #2  [parse_dsl.py:493]
    → _build_body(parsed_body)
      → dict body: _extract_stage_step per top-level key  [parse_dsl.py:454]
      → list body: _extract_phase_step per item           [parse_dsl.py:449]
```

## Data Flow

File text → regex split → **two isolated YAML streams** (header, body) → parsed plain dicts → typed models (`PipelineHeader`, `PhasesBody`/`StagesBody`, `WorkflowDocument`) → `compile_flow` reconstruction → `FlowDocument` → `serialize_flow` → afm flow-file. Anchor/alias resolution happens entirely inside each `yaml.safe_load` call; nothing downstream ever sees YAML-node identity — only plain dicts — so all anchor semantics live and die at the two load sites.

## Manifest Algorithm Mapping

| Manifest step | Code path | Match |
|---|---|---|
| workflow `parse_workflow` step 2 (parse YAML, wrap errors) | `parse_workflow.py:235-240` | ✓ |
| workflow step 5 (reject every other top-level key) | `parse_workflow.py:400-401` | ✓ — this step is what rejects `.anchor` |
| compiler `parse_dsl` step 1 (split on three-dash) | `parse_dsl.py:74-94` | ✓ |
| compiler step 2 (parse header, name/description/roles/repeatable) | `parse_dsl.py:97-199` | ✓ — unknown header keys silently ignored |
| compiler step 3 (parse body segment) | `parse_dsl.py:493` | ✓ — **but YAML errors are NOT wrapped** (manifest silent; raw `yaml.YAMLError` leaks) |
| compiler step 4 (dict body → STAGES, every map key is a stage) | `parse_dsl.py:453-456`, `_extract_stage_step:388` | ✓ — a `.anchor` body key becomes a bogus stage name |

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| `goga/pipeline` | `goga/pipeline/compiler` | call | `run_pipeline` / `describe_pipeline` / `describe_pipelines` / `compile_flow` → `parse_dsl` |
| `goga/pipeline` | `goga/pipeline/workflow` | call | `resolve_workflow` → `load_workflow` → `parse_workflow` |
| `goga/pipeline/compiler` | `goga/pipeline/workflow` | data | `compile_flow(pipeline_path, flow_path, workflow=WorkflowDocument)` consumes parsed workflow models |

## Inconsistencies

| Type | Location | Expected | Actual |
|---|---|---|---|
| code path not covered by manifest | `parse_dsl.py:114`, `parse_dsl.py:493` | invalid YAML wrapped in a structural error (the `parse_workflow` precedent: "invalid YAML in workflow-file") | raw `yaml.YAMLError` (e.g. `ComposerError: found undefined alias`) propagates out of `parse_dsl` unwrapped |
| manifest gap vs task intent | workflow CODEMANIFEST step 5, compiler CODEMANIFEST step 4 | (task) hidden anchor-declaration keys tolerated | both manifests mandate rejection of every non-listed top-level key / every body map key as a stage |

## Trace Graph

```
                    ┌─ workflow file ─────────────────────────────────┐
 .goga/workflows/   │ read → peek → jinja render → yaml.safe_load     │
 *.yml ────────────►│                              │                  │
                    │              merged dicts ──►│_extract_top_level│──► RC1: `.anchor` rejected
                    └──────────────────────────────┴──────────────────┘
                    ┌─ pipeline file ─────────────────────────────────┐
 .goga/pipelines/  │ read ──► regex split ──► safe_load(header) ─┐   │
 *.yml ────────────►│                        safe_load(body) ───┼─►  │
                    │   anchor registry NOT shared ──► RC2: raw  │   │
                    │   ComposerError on cross-segment alias     │   │
                    │   body dict top-level keys = stages ──► RC3:   │
                    │   `.anchor` body key = bogus stage             │
                    └────────────────────────────────────────────────┘
```
