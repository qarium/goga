# Change Plan

## Task Classification

Type: **bugfix** (parsing defect — YAML anchors/aliases/merge keys rejected or unresolvable in workflow files and pipeline files), with a small contract extension (hidden dot-prefixed declaration keys).

## Affected Cells

| Cell | Files to Modify | What Changes |
|------|----------------|--------------|
| `goga/pipeline/workflow` | `parse_workflow.py` | `_extract_top_level` skips hidden dot-prefixed top-level keys (anchor declaration sites); docstring updated |
| `goga/pipeline/compiler` | `parse_dsl.py` | Single-stream anchor-carrying parse (custom `SafeLoader` subclass + `yaml.load_all`) replacing the two isolated `safe_load` calls; YAML errors wrapped as `StructuralError`; hidden dot-prefixed body keys dropped before stage assembly; `_parse_header` refactored to accept the parsed mapping |
| `goga/pipeline/workflow` | `CODEMANIFEST` | `parse_workflow` annotations: step 5 narrowed (hidden keys skipped), Requirements addition |
| `goga/pipeline/compiler` | `CODEMANIFEST` | `parse_dsl` annotations: steps 1-3 amended (anchor carriage, error wrapping, exactly-two-documents rule), Requirements additions |
| `goga/pipeline/workflow` | `.usages/parse-workflow.md` | Document hidden-key tolerance + anchor/merge authoring with examples |
| `goga/pipeline/compiler` | `.usages/parse-dsl.md` | Document anchor carriage across the `---` separator + hidden body keys with examples |
| tests | `tests/pipeline/workflow/test_parse_workflow_logic.py`, `tests/pipeline/compiler/test_parse_dsl.py`, `tests/pipeline/compiler/test_compile_flow_workflow.py` | New coverage for all anchor paths (see Test Strategy) |

## Root Cause Analysis

Three defects (see `investigation.md` for the full evidence chain):

- **RC1** — `parse_workflow._extract_top_level` (`parse_workflow.py:400-401`) rejects every top-level key outside the twelve valid ones, including hidden dot-prefixed anchor declarations: `unknown key in workflow: .anchor`.
- **RC2** — `parse_dsl` loads header and body with two isolated `yaml.safe_load` calls (`parse_dsl.py:114`, `:493`); YAML anchors are scoped per load, so a header-declared anchor is an undefined alias in the body, leaking a raw `yaml.ComposerError`.
- **RC3** — `parse_dsl`'s dict-body format maps every top-level body key to a stage name (`parse_dsl.py:453-456`), so a hidden `.anchor` body key dies as `stage value missing title` (or silently compiles a bogus stage if it carries `title`).

PyYAML itself resolves aliases and `<<:` merge keys natively within one load; all three defects are in the validation/splitting around the load calls.

## Trace Summary

Affected paths (see `trace.md`): workflow `load_workflow → render_workflow → parse_workflow → _extract_top_level`; pipeline `run_pipeline/describe_pipeline(s)/compile_flow → parse_dsl → _split_segments/_parse_header/_build_body`. Downstream consumers see only plain dicts — no changes beyond the two parsers.

## Change Strategy

1. **Workflow — tolerate hidden declaration keys** (`parse_workflow.py`): in `_extract_top_level`'s key loop, `continue` for `isinstance(key, str) and key.startswith(".")` before the unknown-key rejection. After `yaml.safe_load` the anchor content is already merged into its use sites; the dot-key is a leftover declaration that carries no workflow content. Non-str keys and ordinary unknown keys keep raising the unchanged error. The empty-workflow rule is untouched (a dot-key alone is not content).
2. **Pipeline — single-stream anchor-carrying parse** (`parse_dsl.py`):
   - Add module-private `_PipelineFileLoader(yaml.SafeLoader)` overriding `compose_document` to NOT reset the anchor registry between stream documents (validated experimentally: header→body aliases resolve; alias-before-anchor still fails; plain files unchanged).
   - `parse_dsl` keeps `_split_segments` as the structural pre-check (separator presence, exactly-three-dashes, CRLF — preserves "missing body separator" and the four-dash rejection verbatim), then parses the FULL text once: `documents = list(yaml.load_all(text, Loader=_PipelineFileLoader))`, wrapping `yaml.YAMLError` as `StructuralError("invalid YAML in pipeline-file")`.
   - Document dispatch: `len == 1` → `StructuralError("header missing name/description")` (empty/comment-only header segment — today's exact message); `len == 2 and not header_text.strip()` → same error (leading-separator file — today's message); `len == 2` → `documents[0]` is the header, `documents[1]` the body (`None` body normalizes to `[]` as today); `len > 2` → `StructuralError("extra body separator")` (today a raw `ComposerError`).
   - `_parse_header` accepts the already-parsed mapping instead of re-loading text (private helper; same validation order and messages).
   - Before `_build_body`, drop `isinstance(key, str) and key.startswith(".")` entries from a dict body (hidden declaration sites; a list body cannot carry them).
3. **No other cells change.** `goga/config/yaml`, hooks overlay, compiler reconstruction, serializer are untouched.

## Specification Impact

- Workflow `CODEMANIFEST`, `parse_workflow` annotations: step 5 reworded to "…every other top-level key that is not a hidden declaration key (a `str` starting with `.`)…"; new Requirements bullet: hidden dot-prefixed top-level keys are skipped after YAML resolution (anchor declaration sites), do not count as content, and are not listed among valid keys.
- Compiler `CODEMANIFEST`, `parse_dsl` annotations: steps 1-3 amended — the split stays the structural pre-check; the stream is parsed once with anchor carriage across the separator; invalid YAML raises `StructuralError("invalid YAML in pipeline-file")`; exactly two documents required (a third raises "extra body separator"); hidden dot-prefixed body keys are dropped before stage assembly. Requirements gain the corresponding bullets.

## Usage Impact

- `parse-workflow.md`: "Accepted structure" gains a note — top-level keys starting with `.` are tolerated declaration sites for YAML anchors; a worked example (`.anchor: &defaults` + `stages.<name>.<<: *defaults` and the `stages: {<<: *anchor}` block merge) with the constraint that hidden keys are ignored, not validated, and alone do not satisfy the empty-workflow rule.
- `parse-dsl.md`: new "Anchors and shared starting points" section — anchors declared in the header or in hidden body keys resolve across the `---` separator; examples for STAGES and PHASES bodies; the error-wrapping note (`invalid YAML in pipeline-file`).
- `load-workflow.md`: no change needed (loading chain behavior unchanged; parsing details reference `parse-workflow`).

## Compatibility Verification

**Not fully backward compatible — breaking change disclosed and requiring user override:**

- Inputs that error today and succeed after the fix: workflow files with dot-prefixed top-level keys (RC1); pipeline files with header-declared anchors aliased in the body (RC2) or hidden body keys (RC3).
- Error-path changes on inputs that remain invalid: raw `yaml.YAMLError` leaks from `parse_dsl` become `StructuralError("invalid YAML in pipeline-file")`; a body containing an extra `---` line changes from raw `ComposerError` to `StructuralError("extra body separator")`.
- Every currently-valid file parses to byte-identical models (verified experimentally: plain STAGES/PHASES files, CRLF files, roles/repeatable headers unchanged); all 215 existing parser tests pass on `main` and none lock the changed behaviors (verified by grep: no test asserts raw YAML errors, empty-header, or leading-separator behavior; the four-dash and no-separator tests are preserved by design).

## Test Strategy

New tests (logic suites of both parsers + one compile integration):

- Workflow (`test_parse_workflow_logic.py`): dot-key + merge into a stage parses with merged fields; block-level merge `stages: {<<: *anchor}` (the TODO example) parses; dot-key alone still raises "empty workflow"; a dot key whose value is irrelevant to parsing (scalar/map) is skipped; ordinary unknown keys still rejected (existing test retained as the guard).
- Pipeline (`test_parse_dsl.py`): header-declared anchor merged into a STAGES stage (RC2); body-hidden dot-key + merge (RC3); PHASES list body with header anchor merged into an item; anchor + alias fully inside one segment (regression); alias-before-anchor fails as wrapped `StructuralError`; invalid YAML raises "invalid YAML in pipeline-file"; extra separator raises "extra body separator"; CRLF pipeline file parses; empty/comment-only header keeps "header missing name/description"; no-separator and four-dash cases keep "missing body separator" (existing tests, unchanged).
- Integration (`test_compile_flow_workflow.py` or a new module): end-to-end `compile_flow` over a pipeline file and workflow file that both use anchors — merged content reaches the compiled flow document.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `compose_document` override interacts with a future PyYAML release | Low | High (parse breakage) | The override is two lines over a stable API; add a pinning test for the anchor-carriage behavior so any drift fails loudly |
| Hidden keys silently absorb typos (`.stagse:` ignored instead of rejected) | Medium | Low (authoring surprise) | Documented tradeoff of the dot-idiom in both usage files; ordinary typos without the dot still error |
| Error-message drift on invalid inputs confuses tooling that matches raw YAML errors | Low | Low | Grep shows no internal consumer matching raw `yaml.*Error` from `parse_dsl`; messages remain one-line structural errors |
| Scope creep into config/profile YAML loading | Low | Medium | Explicitly out of scope; the fix touches only the two parser modules |
