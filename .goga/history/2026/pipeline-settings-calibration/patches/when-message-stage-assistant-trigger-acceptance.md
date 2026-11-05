# Acceptance: `when: message` — the on_message stage-assistant trigger

Acceptance of commit `e5b6ad1f` (feat: add when: message stage-assistant
trigger). Run: `Patch-20261105-213143-4b8e`, stage `accept-result`.

## Summary

The acceptance pipeline (scope → manifest review → usage review → test
assessment → report) verified the `when: message` vocabulary extension across
both touched cells. Code, global manifest annotations, cell usages, and tests
already agreed; six entity/routine-level manifest annotations still enumerated
the old three-value vocabulary and were aligned (user-approved). Lint is clean
(92 cells, 0 errors) and the full test suite is green (8048 passed, 8 skipped).

## Acceptance Scope

| Cell | Path | Change types |
|---|---|---|
| workflow | `goga/pipeline/workflow` | CODE, MANIFEST, USAGE, TEST |
| compiler | `goga/pipeline/compiler` | CODE, MANIFEST, USAGE, TEST |

Affected dependencies (imports): `goga/pipeline` (DIRECT — imports
`compile_flow`, `FlowAssistant`, usages `collaboration-emission`/`assistants`/
`parse-workflow`), `goga/pipeline/hooks` (DIRECT — `WorkflowDocument` type
only, signature unchanged), `goga/build`, `goga/commands/build`,
`goga/commands/pipeline` (DIRECT — unchanged import surfaces),
`goga/commands/pipeline` (TRANSITIVE via `goga/pipeline` usages). The change
adds a value to a closed vocabulary; no signature changed — all dependents
unaffected unless they author `when: message`.

## CODEMANIFEST Status

**CONSISTENT** after 6 updates (all WARNING stale annotations, user-approved):

| Cell | Location | Previous | New |
|---|---|---|---|
| workflow | `WorkflowAssistant` `when` param | one of "start", "checkpoints", "finish" | + `"message"` and the resting-engagement semantics |
| workflow | `WorkflowAssistant` property `when -> str` | start, checkpoints, or finish | + `message` |
| workflow | `parse_workflow` Algorithm 6.7 | start/checkpoints/finish | start/checkpoints/finish/message |
| workflow | `parse_workflow` Requirements | is one of start/checkpoints/finish | + `/message` |
| compiler | `FlowAssistant` `trigger` param | one_shot/checkpoints/on_completion | + `"on_message" from message` (resting engagement) |
| compiler | `FlowAssistant` property `trigger -> str` | one_shot, checkpoints, or on_completion | + `on_message` |

Pre-flight and post-update `goga lint`: 92 cells, 0 errors. `goga contract`
exit 0 for both cells; facade exposure verified (`__all__` carries every
contract type). Baseline usages/annotations present verbatim in both manifests.

## Usages Status

**CONSISTENT** — no updates needed. `assistants.md` (when-table, gate-stall
paragraph) and `collaboration-emission.md` (trigger table, resting-engagement
paragraph) were already aligned by the implementation commit. Integrity checks
(usage files exist, imported usages exist, all usages referenced) pass via
lint rules.

## Test Coverage Assessment

**EXCELLENT** — every changed contract point has a dedicated test:

- `test_parse_attachment_when_message_is_accepted` (CONTRACT: parse + verbatim
  carry + gate True)
- parametrized `when: later` case (CONTRACT: four-value error text)
- `test_compile_when_message_maps_to_on_message` (INTEGRATION: real
  parse → compile path, model + serialized text)
- `test_compile_when_message_combines_with_gate` (CONTRACT: `mode: required` +
  `trigger: on_message`)

Runs: changed files 111 passed; `tests/pipeline/` 1763 passed; full suite
**8048 passed, 8 skipped, 0 failed**.

## Critical Findings

None.

## Warnings

| Source | Finding | Recommendation |
|---|---|---|
| Manifest | 6 stale when/trigger enumerations | fixed during acceptance (table above) |
| Project usage | `.goga/usages/cooks/afm.md` documents `trigger` as the three-value set (line 138) and its "Dashboard triggers" section omits `on_message`, which the compiler now emits | update `afm.md` in a follow-up (acceptance records the remark; project usages are not modified here) |
| Usage (INFO) | `assistants.md` examples show three of four `when` values; `message` documented in table/prose only | optional yaml snippet in a follow-up |

## Applied Updates

- `goga/pipeline/workflow/CODEMANIFEST` — 4 annotation alignments
- `goga/pipeline/compiler/CODEMANIFEST` — 2 annotation alignments
- this report file

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| gated `when: message` helper can stall a stage until messaged | documented behavior | warning paragraph in `assistants.md`; user-approved combinability |
| `afm.md` project usage lags the emitted vocabulary | low | recorded remark; follow-up update |

## Verdict

**ACCEPTED_WITH_NOTES** — no critical findings, coverage excellent, manifest
and usages consistent after the six approved alignment edits; remaining notes
(`afm.md` remark, optional example snippet) do not block acceptance.
