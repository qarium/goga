# Compatibility Report

## Checklist Results

### API Compatibility
| Question | Answer | Evidence |
|----------|--------|----------|
| Function signature unchanged for existing callers? | YES | `parse_workflow(text: str) -> WorkflowDocument` and `parse_dsl(text: str) -> tuple[...]` keep their public signatures; only the private helper `_parse_header` changes its parameter (text → parsed mapping) — not part of any facade (`__all__` unchanged) |
| Return type unchanged? | YES | Same models returned; a `None` body still normalizes to `[]` exactly as today |
| Default parameter values preserved? | YES | Neither routine has parameters with defaults |

### Semantic Compatibility
| Question | Answer | Evidence |
|----------|--------|----------|
| Same arguments produce same behavior? | **NO** | Inputs that error today parse after the fix: workflow texts with dot-prefixed top-level keys (`WorkflowSyntaxError` → success); pipeline texts with header-declared anchors (raw `ComposerError` → success) or hidden body keys (`StructuralError` → success). All currently-valid inputs produce identical results (experiment: plain/CRLF/roles files parse identically) |
| Output format unchanged? | YES | Parsed models, compiled flow-files, and the serializer are untouched; hidden keys never reach any output |
| File paths unchanged? | YES | No path handling changes anywhere in the plan |
| Error messages and codes unchanged? | **NO** | On inputs that remain invalid: raw `yaml.YAMLError` leaks from `parse_dsl` become `StructuralError("invalid YAML in pipeline-file")`; a body with an extra `---` line changes from raw `ComposerError` to `StructuralError("extra body separator")`. Messages for every test-locked path are preserved verbatim (`missing body separator`, `header missing name/description`, `unknown key in workflow: …`) |

### Algorithmic Compatibility
| Question | Answer | Evidence |
|----------|--------|----------|
| Manifest-defined algorithm steps preserved? | **NO** | Workflow CODEMANIFEST step 5 is narrowed (hidden dot-prefixed keys skipped instead of rejected); compiler CODEMANIFEST steps 1-3 are amended (single-stream anchor-carrying parse replaces the two isolated loads; YAML-error wrapping; two-documents rule). Reconciliation is an explicit pipeline step (Step 7) |
| Execution order unchanged? | YES | Split pre-check → header validation → body parse → body build; validation order and message precedence inside each parser are preserved |
| Side effects unchanged? | YES | Both parsers stay pure (no I/O); `parse_dsl` still performs exactly one file-level operation per call (the stream parse replaces two loads — no new side effects) |

### Consumer Compatibility
| Question | Answer | Evidence |
|----------|--------|----------|
| Existing tests pass without modification? | YES | Baseline 215 parser tests pass on `main`; grep confirms none assert raw YAML errors, empty-header, or leading-separator behavior; the four-dash and no-separator tests are preserved by the regex pre-check design |
| Usage recipes remain valid? | YES | Every example in `parse-dsl.md`/`parse-workflow.md` parses identically (verified experimentally: case I of the loader validation) |
| Downstream consumers unaffected? | YES | `compile_flow`, hooks overlay, `serialize_flow`, run/describe coordinators consume typed models only; model shapes unchanged |

## Verdict

**BREAKING** — failed checkboxes: "Same arguments produce same behavior?", "Error messages and codes unchanged?", "Manifest-defined algorithm steps preserved?"

## Breaking Change Details

All three failures are confined to **inputs that are broken today** (structural errors) or to **specification text amended alongside the code**:

1. Error→success transitions on anchor-bearing files — this IS the requested fix (the task's purpose).
2. Raw `yaml.YAMLError` → wrapped `StructuralError` — error-type tightening on invalid input, matching the `parse_workflow` precedent ("invalid YAML in workflow-file"); no internal consumer matches raw YAML errors (grep-verified).
3. Manifest amendments — reconciled in pipeline Step 7 with the implementation, keeping triple consistency.

**User override recorded**: the breaking-change disclosure (all three items above, item by item) was presented with the change plan in stage question q1 on 2026-11-22; the user selected "Утвердить план — приступить к реализации". Per goga-change policy ("Only user can override a STOP"), the pipeline proceeds to implementation.
