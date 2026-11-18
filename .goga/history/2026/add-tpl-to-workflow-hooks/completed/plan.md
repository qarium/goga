# Change Plan: gate-aware finish trigger for assistants compilation

## Task Classification
Type: bugfix — a gated `when: finish` attachment compiled to an engine
trigger that cannot gate (`on_completion`); it must compile to
`pre_completion` (afm v2.2.9 pre-completion review).

## Task
Fix the assistants compilation: the combination `gate: true` +
`when: finish` must produce `trigger: pre_completion`.

## Affected Cells

| Cell | Files to Modify | What Changes |
|------|----------------|--------------|
| `goga/pipeline/compiler` | `compile_flow.py`, `flow_assistant.py`, `CODEMANIFEST`, `.usages/collaboration-emission.md` | Gate-aware `when`→`trigger` mapping; spec and practice updates |
| project practice | `.goga/usages/cooks/afm.md` | Stage-helper trigger vocabulary updated to the afm v2.2.9 reality (`+pre_completion`, `+on_message`) |
| `goga/pipeline/workflow` | — | No changes: its contract maps no engagement values |

## Root Cause
The `_WHEN_TRIGGER` vocabulary was authored against afm v2.0.9 (no
`pre_completion` then) and mapped `finish → on_completion` unconditionally.
`on_completion` gives the helper a final turn when the result is ready —
after completion — so a required verdict could never block the stage,
contradicting the authored gate semantics ("the verdict must pass before
the stage finishes"). afm v2.2.9 provides `pre_completion` — the
pre-completion review round that runs after the stage agent's turn and
before the stage completes — exactly the gate mechanism.

## Change Strategy
1. `compile_flow.py`: documented helper `_attachment_trigger(gate, when)`
   — the single engagement-translation site: `gate=true` + `when=finish` →
   `pre_completion`; otherwise the `_WHEN_TRIGGER` row.
2. `flow_assistant.py`: `trigger` docstring updated to the gate-aware mapping.
3. `CODEMANIFEST` (compiler): Collaboration-emission annotations updated
   (global annotation, `FlowAssistant` type + `trigger` property,
   test-expectations block).
4. `.usages/collaboration-emission.md`: trigger table row + gate-aware
   explanation.
5. `.goga/usages/cooks/afm.md`: stage-helper `trigger` key vocabulary and
   the Dashboard-triggers paragraph updated to v2.2.9.
6. Tests: two gated-finish assertions updated; an 8-row parameterized
   (gate × when) matrix added; direct-construction samples aligned.

## Compatibility Verification
Deliberately NOT backward compatible for the gated-finish input class:
`compile_flow` emits `trigger: pre_completion` instead of `on_completion`
(output value change; 2 tests updated; manifest annotation rewritten).
Approved explicitly by the user with the plan. All other gate/when
combinations, API signatures, paths, structures, and side effects are
unchanged.

## Test Strategy
Matrix test over the full (gate × when) domain; materialization tests
assert the emitted YAML text and the model; serialization round-trip;
direct construction. Validation: venv, `pytest tests/ -q`, `ruff check`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Behavioral shift for existing gated-finish workflows | Certain | Planned | User-approved via plan; advisory `finish` unchanged |
| Wrong `pre_completion` spelling | Low | High (engine rejects) | Value verified against the afm v2.2.9 binary; tests pin the string |
| Spec/usage inconsistency after the edit | Medium | Medium | Manifest/Usage Reconciliation + Drift Analysis steps |
| Stale assertions elsewhere | Low | Low | Full suite run |

---

# Change Execution Report

## Summary
Fixed the assistants compilation for the afm engine: the combination
`gate: true` + `when: finish` now compiles to `trigger: pre_completion`
(the engine's pre-completion review round, able to block stage
completion) instead of `on_completion` (the post-result final turn, which
could never gate). The mapping lives in one new helper,
`_attachment_trigger`, consumed at the single emission site; the
specification (CODEMANIFEST) and the practices (cell usage + afm cook)
were reconciled in the same change, and the behavior is pinned by an
8-combination (gate × when) parameterized test.

## Root Cause
The `finish → on_completion` vocabulary was authored against afm v2.0.9,
which had no `pre_completion`; the gated case silently inherited the
advisory mapping. Evidence chain: single mapping site
(`compile_flow.py` `_WHEN_TRIGGER` + one consumption site), the manifest
documenting the same mapping, afm v2.2.9 binary confirming `pre_completion`
with gate semantics, and the authoring practice promising
"the verdict must pass before the stage finishes".

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga/pipeline/compiler` | `compile_flow.py`, `flow_assistant.py`, `CODEMANIFEST`, `.usages/collaboration-emission.md` |
| project practice | `.goga/usages/cooks/afm.md` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Gate-aware trigger mapping | `goga/pipeline/compiler/compile_flow.py` | `_attachment_trigger(gate, when)` helper: gated finish → `pre_completion`, otherwise `_WHEN_TRIGGER[when]`; vocabulary comment updated; emission site uses the helper |
| Docstring update | `goga/pipeline/compiler/flow_assistant.py` | `trigger` arg docstring describes the gate-aware mapping |
| Spec reconciliation | `goga/pipeline/compiler/CODEMANIFEST` | 5 vocabulary sites updated (global Collaboration-emission annotation, `FlowAssistant` type annotation, `trigger` property, content-check test expectations) |
| Practice update | `goga/pipeline/compiler/.usages/collaboration-emission.md` | trigger table row + gate-aware `when: finish` paragraph |
| Engine-practice update | `.goga/usages/cooks/afm.md` | stage-helper trigger vocabulary `+pre_completion` `+on_message`; Dashboard-triggers semantics for pre-completion review |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `test_compile_gate_when_trigger_matrix` (8 params) | `tests/pipeline/compiler/test_compile_flow_collaboration.py` | Full (gate × when) → (mode, trigger) matrix, model + serialized text |
| Updated: `test_compile_team_and_stage_attachments_full_materialization`, `test_compile_reference_takes_declaration_fields_keeps_own_gate_when` | same file | Gated finish materializes `pre_completion` |
| Updated samples | `test_data_models.py`, `test_serialize_flow_collaboration.py` | Direct construction + serialization/round-trip with the new value |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga/pipeline/compiler` | Collaboration-emission annotations: gated finish override rule | `collaboration-emission.md` vocabulary |
| project | — | `cooks/afm.md` engine vocabulary to v2.2.9 |

## Validation Results
VERIFIED. Full suite: 8355 passed, 8 skipped (pre-existing conditional
skips), 0 failed. `ruff check goga/ tests/`: passed. `goga lint`: 93
cells, 0 errors. Coverage of `_attachment_trigger`: 100% of lines, both
branches. Triple consistency (CODEMANIFEST ↔ implementation ↔ usages)
confirmed by cross-grep; no residual `finish → on_completion` claims
outside the ungated-finish context.

## Compatibility Status
Breaking by design, user-approved: for workflows authoring
`gate: true` + `when: finish` the compiled flow-file now carries
`trigger: pre_completion` (was `on_completion`). Two existing tests
updated accordingly. Everything else (advisory finish, gate with
start/checkpoints/message, APIs, paths, emission order, side effects)
is unchanged and regression-pinned.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Behavioral shift for gated-finish workflows | Accepted | User-approved plan; scoped to exactly this combination |
| Engine vocabulary mismatch | Low | Value verified against afm v2.2.9 binary; matrix test pins it |
| Documentation staleness | Low | Reconciliation + drift steps passed; `goga lint` clean |

## Updated Files
- goga/pipeline/compiler/compile_flow.py
- goga/pipeline/compiler/flow_assistant.py
- goga/pipeline/compiler/CODEMANIFEST
- goga/pipeline/compiler/.usages/collaboration-emission.md
- .goga/usages/cooks/afm.md
- tests/pipeline/compiler/test_compile_flow_collaboration.py
- tests/pipeline/compiler/test_data_models.py
- tests/pipeline/compiler/test_serialize_flow_collaboration.py
