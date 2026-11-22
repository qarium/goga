# Investigation Report

## Task Summary

YAML links (anchors `&name`, aliases `*name`, merge keys `<<:`) are unsupported in workflow files and pipeline files: declaring a reusable "starting point" — a hidden top-level key such as `.anchor: &anchor` — and merging it (e.g. `stages: {<<: *anchor}`) causes parsing failures today. The requested outcome: such declarations must parse cleanly in both file families without breaking existing behavior.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga/pipeline/workflow` | `parse_workflow` strict top-level unknown-key rejection blocks hidden anchor declarations | P1 |
| `goga/pipeline/compiler` | `parse_dsl` splits header/body into two isolated `yaml.safe_load` calls (cross-segment anchors unresolvable, raw YAML errors leak) and treats every body map key as a stage (hidden body keys become bogus stages) | P1 |
| `goga/pipeline` | Loading paths that feed both parsers (`resolve_workflow`, `run_pipeline`, `describe_pipeline(s)`) | P2 |

## Tracing Summary

See `trace.md` in this topic directory. Workflow files flow read → peek → Jinja render → single `yaml.safe_load` → `_extract_top_level` strict validation. Pipeline files flow regex-split on the first `---` line → two independent `safe_load` calls (header at `parse_dsl.py:114`, body at `parse_dsl.py:493`) → `_build_body` where a dict body maps every top-level key to a stage name.

## Data Flow Analysis

All anchor/alias/merge resolution happens inside `yaml.safe_load`; every downstream consumer (`WorkflowDocument` models, `_build_body`, `compile_flow` reconstruction, `serialize_flow`) sees only plain dicts. Therefore:

- Aliases and `<<:` merges **within one load call** already resolve correctly (PyYAML `SafeLoader` implements merge-key flattening natively) — no fix needed there.
- The failures are purely in **what happens around the load calls**: strict key validation (workflow top level, pipeline body map) and the **load-call boundary** itself (pipeline header/body split).

## Manifest Algorithm Analysis

- Workflow CODEMANIFEST, `parse_workflow` step 5: "For every other top-level key — raise a structural error" — mandates the rejection that blocks `.anchor`. A fix must reconcile this step (pipeline Step 7).
- Compiler CODEMANIFEST, `parse_dsl` steps 1-4: split-then-load-twice is contractual; step 4 maps every dict-body key to a stage. Nothing in the manifest covers YAML-error wrapping (unlike `parse_workflow` step 2), matching the observed raw-error leak.

## Affected Usages

| Usage | Cell | Classification | Reason |
|-------|------|-----------------|--------|
| `.usages/parse-workflow.md` | `goga/pipeline/workflow` | DIRECTLY AFFECTED | "Accepted structure: Top-level keys …" list must document hidden dot-key tolerance |
| `.usages/parse-dsl.md` | `goga/pipeline/compiler` | DIRECTLY AFFECTED | Documents the header/body split contract; must document anchor carriage across the separator |
| `.usages/load-workflow.md` | `goga/pipeline/workflow` | INDIRECTLY AFFECTED | Loading chain description; parsing semantics referenced |
| `.usages/compile-flow.md`, `serialize-flow.md` | `goga/pipeline/compiler` | NOT AFFECTED | Downstream of parsed models; unchanged shapes |

## Rejected Hypotheses

| Hypothesis | Rejection evidence |
|---|---|
| "PyYAML `safe_load` cannot resolve `<<:` merge keys" | Direct experiment: `stages: {build: &b {...}, test: {<<: *b}}` resolves correctly in one load; the failure came from per-stage key validation of an unrelated field, proving resolution works. |
| "Jinja whole-file rendering breaks anchors" | All failures reproduce through `parse_workflow`/`parse_dsl` called directly on raw text, bypassing `render_workflow` entirely; rendering only substitutes `{{ }}`/`{% %}` markers. |
| "The hooks overlay merge drops merged content" | The overlay operates on parsed `WorkflowDocument` models after parsing; the parse fails before any overlay runs. The failures are at parse time. |
| "A custom `!ENV` loader interferes" (`goga/config/yaml`) | Neither parser routes through `parse_env_yaml`; both call `yaml.safe_load` directly. |

## Confirmed Root Cause

Three independent defects, each empirically reproduced on `main` (Python 3.12, PyYAML safe loader):

1. **RC1 — workflow top-level rejection** (`parse_workflow.py:400-401`): `_extract_top_level` raises `unknown key in workflow: .anchor; valid keys: …` for any key outside the twelve — including hidden dot-prefixed anchor-declaration keys. Reproduced: a workflow with `.anchor: &defaults` + `stages.build.<<: *defaults` fails with exactly this error.
2. **RC2 — pipeline cross-segment anchors** (`parse_dsl.py:114` + `:493`): the header and body are separate `yaml.safe_load` calls; YAML anchors are scoped per load, so an anchor declared in the header is undefined in the body. The resulting `yaml.ComposerError("found undefined alias 'defaults'")` propagates **raw** — not wrapped as `StructuralError` (a manifest-silent gap; `parse_workflow` wraps by contrast).
3. **RC3 — pipeline body hidden keys** (`parse_dsl.py:453-456`, `_extract_stage_step`): a dict body treats every top-level key as a stage name, so a `.anchor` declaration in the body dies as `StructuralError: stage value missing title` (or, worse, would silently compile a bogus `.anchor` stage if it carried a `title`).

Fix mechanism validated by experiment: a `SafeLoader` subclass overriding `compose_document` to keep the anchor registry across stream documents resolves header→body aliases with standard semantics (alias-before-anchor still fails, plain files unchanged, phases-list bodies support `<<:` inside list items); tolerating dot-prefixed top-level keys in `_extract_top_level` (workflow) and dropping them from the parsed body dict (pipeline) removes RC1/RC3 while leaving the existing `unknown_key` rejection intact for ordinary keys.

## Confidence Level

**HIGH** — every hypothesis was validated by direct reproduction against the real parsers on `main`, the causal code lines are identified and read, both manifests were checked against the code, and the candidate fix mechanism was exercised empirically (10 edge cases including no-separator, leading-separator, multi-separator, trailing-empty-body, alias-before-anchor).

## Breaking Change Assessment

1. **Will existing function call with same arguments produce different behavior?** — **YES, on inputs that error today**: texts with dot-prefixed top-level keys (today `WorkflowSyntaxError`/`StructuralError`, after fix accepted) and pipeline files with header-declared anchors (today raw `ComposerError`, after fix resolved). For every currently-valid input the parse result is byte-identical.
2. **Will existing file paths change?** — NO.
3. **Will output format change?** — NO (models, compiled flow-files, serializer untouched for anchor-free inputs).
4. **Will return value semantics change?** — NO for valid inputs. Error-path semantics tighten: raw `yaml.YAMLError` leaks from `parse_dsl` become wrapped `StructuralError` (also affects invalid-YAML bodies today, and >2-document streams).
5. **Will manifest-defined guarantees be altered?** — **YES**: workflow CODEMANIFEST step 5 ("every other top-level key" rejected) is narrowed to non-hidden keys; compiler CODEMANIFEST steps 1-4 gain anchor-carriage and error-wrapping clauses. Manifest reconciliation (pipeline Step 7) is required.
6. **Will existing tests break?** — NO known locks: the unknown-key test uses `unknown_key` (non-dot-prefixed) and stays green; no test asserts raw `YAMLError`, leading-`---`, or multi-`---` behavior (verified by grep over `tests/pipeline/`); baseline 215 parser tests pass on `main`.

**BREAKING CHANGE DETECTED** (questions 1 and 5 answered YES). Per goga-change policy the pipeline STOPS here; per the same policy only the user can override a STOP. The escalation is presented together with the change plan for the user's approval decision — no implementation happens before that approval.
