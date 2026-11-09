# Change Execution Report — Stage env delivery for script stages

## Summary

The per-stage `env` workflow instruction was delivered exclusively through
the stage `command` field (an exec closure over an agent wrapper). A script
stage — a pipeline stage whose body authors `script`, compiled with a
`script` field and no agent command — therefore received a spurious
inserted `command:` pointing at an agent wrapper beside its `script`, and
the env never reached the authored script action. The delivery now carries
a second form: a claimed stage bearing a compiled `script` field receives a
payload closure (the gate script-step closure shape — exports, then the
authored script lines as-is) and its `script:` line in the written
flow-file is patched in place. The gate-side confirmation asked for by the
task holds: `stages.<name>.gates[*].env` works with a `script` step
(`_render_step_closure` script branch, pinned by
`test_script_step_closure_exports_env_then_script`).

## Root Cause

`apply_stage_env_wrappers` resolved exactly one delivery channel — the
`command` field — and required an agent (stage agent, extend-entry agent,
or the global pipeline agent) for every claim. A script stage has no
command to patch, so the routine inserted one (corrupting the stage into a
command+script hybrid the engine never intended) and raised a strict
no-agent error when no agent resolved at all.

## Modified Cells

| Cell | Files Modified |
|------|----------------|
| goga/pipeline | stage_env_wrappers.py, run_pipeline.py, CODEMANIFEST, .usages/per-stage-env.md |
| tests (pipeline) | tests/pipeline/test_stage_env_wrappers_logic.py |

## Implemented Changes

| Change | File | Description |
|--------|------|-------------|
| Payload closure form | goga/pipeline/stage_env_wrappers.py | `_render_payload_closure` — shebang, verbatim exports, authored script payload (gate script-step shape) |
| Script field patch | goga/pipeline/stage_env_wrappers.py | `_patch_stage_script` rewrites the exact two-space `script:` line in place, consuming a block-literal value whole (`_field_value_end`); `script_before`/`script_after` never match |
| Claim classification | goga/pipeline/stage_env_wrappers.py | `apply_stage_env_wrappers` splits claims by the compiled stage's own fields: script claims wrap the payload (no agent resolution, no strict no-agent error), agent claims keep the exec-closure behavior verbatim |
| In-memory rebuild | goga/pipeline/stage_env_wrappers.py | `_with_script` returns a new `FlowStage` with the wrapper as the script value; unclaimed stages stay the same objects |
| Step-14 comment | goga/pipeline/run_pipeline.py | The run-coordination comment describes both delivery forms |
| Contract | goga/pipeline/CODEMANIFEST | `apply_stage_env_wrappers` annotations and the run-coordination steps describe the two-form delivery; `goga schema` validates |
| Usage | goga/pipeline/.usages/per-stage-env.md | Delivery mechanism documents both forms; authoring gains a script-stage example |

## Tests Added

| Test | File | What It Validates |
|------|------|-------------------|
| test_env_on_script_stage_patches_script_field | tests/pipeline/test_stage_env_wrappers_logic.py | Script patched in place, no command inserted, closure carries the payload, stage key order preserved |
| test_script_stage_needs_no_agent | tests/pipeline/test_stage_env_wrappers_logic.py | A script claim with `global_agent=None` raises nothing and wraps |
| test_script_closure_executes_env_and_payload | tests/pipeline/test_stage_env_wrappers_logic.py | The generated closure really exports the env and runs the payload (subprocess) |
| test_multiline_script_consumed_whole_and_following_fields_intact | tests/pipeline/test_stage_env_wrappers_logic.py | A block-literal value with a paragraph break is replaced whole; every other byte identical |
| test_loop_expanded_script_copies_each_get_wrapper | tests/pipeline/test_stage_env_wrappers_logic.py | Loop copies each receive their own payload wrapper |
| test_mixed_script_and_agent_claims_each_patch_their_own_field | tests/pipeline/test_stage_env_wrappers_logic.py | Both forms coexist in one flow, each patching its own field |
| test_illegal_env_key_on_script_stage_rejected_before_any_write | tests/pipeline/test_stage_env_wrappers_logic.py | Strict pre-run error before any wrapper or rewrite |
| test_script_before_and_after_of_a_script_stage_stay_untouched | tests/pipeline/test_stage_env_wrappers_logic.py | The exact `script:` prefix never captures the sibling script fields |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|------|---------------------|---------------|
| goga/pipeline | `apply_stage_env_wrappers` contract: two delivery forms, script claims resolve no exec target, script-patch grammar; run-coordination step 14 and the cell-level annotations reworded | `per-stage-env.md`: both delivery forms, the no-agent property of script claims, the patch grammar, a script-stage authoring example |

## Validation Results

- pytest tests/ — 8241 passed, 8 skipped
- ruff check goga/pipeline/ + the touched test file — all checks passed
- goga schema — validates (two initial `` `script` `` annotation links fixed to plain prose per the DSL reference rule)

## Compatibility Status

Compatible. The routine signature is unchanged (locked by the contract
test); env-free runs keep byte-identical flow output; agent-stage claims
behave exactly as before. Two behavior changes, both corrections of
previously broken states, were approved in the plan: a script stage with
env no longer receives an inserted agent `command` (and no longer fails
strictly without an agent), and the workflow-`agent`-override-on-
script-body combination is rejected at compile time (see the acceptance
addendum — the delivery initially wrapped the script instead of the
composed command; acceptance replaced that with a strict authoring
error).

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| The engine must accept an absolute executable path as a stage `script` value (the gate `run` precedent relies on the same property) | Low | The value runs under the same shell the engine gives any script value; the gate delivery uses the identical mechanism in production |
| Concurrent unrelated edit in goga/assets/afm/skin/goga.css appeared during this run (not part of this change) | Info | Left untouched; excluded from this change's file set |

## Updated Files

- goga/pipeline/stage_env_wrappers.py
- goga/pipeline/run_pipeline.py
- goga/pipeline/CODEMANIFEST
- goga/pipeline/.usages/per-stage-env.md
- tests/pipeline/test_stage_env_wrappers_logic.py
- .goga/history/2026/add-gates-to-workflow/patches/stage-env-script-delivery.md (this report)

## Acceptance addendum

The acceptance audit (Requirements & coverage audit stage) confirmed the
triple consistency of the delivery change (lint/schema/contract clean,
1954 pipeline-suite tests green) and flagged one WARNING: the
workflow-`agent`-override-on-`script`-body combination — the compiler
composed a `command` beside the authored `script` and the new
classification silently let the script claim win, leaving both fields in
the flow-file with no defined engine precedence. The delivery wrapped the
script and left the composed `command` untouched, but nothing pinned the
combination and no doc stated the precedence rule.

Approved fix (user decision): prohibit the combination instead of
documenting it. A stage's action is one — an agent stage (`agent`
instruction → `command`) or a script stage (`script`). Two compile-time
checks enforce it:

- `compile_flow` override pass — a workflow `agent` instruction (stages
  block or extend entry) on a body authoring `script` raises
  `StructuralError` ("agent is forbidden on a script stage in
  workflow.<name>: <agent>");
- step-5 canonical assembly — a `script` body carrying a verbatim
  `command` key (unknown-key passthrough; `command` is not pipeline
  vocabulary) raises `StructuralError` ("script is mutually exclusive
  with command in stage <name>"), symmetric with the existing
  script/prompt/skills exclusivity and the gates script-XOR-agent rule.

`before_script`/`after_script`/`timeout` are unaffected — they are the
invocation's bookends, not the action, and stay compatible with both
forms (pinned by a new compiler test). The env delivery itself is
unchanged; the classification in `apply_stage_env_wrappers` remains as
defense-in-depth. No in-repo workflow or fixture authored the
combination (verified by a full-repo scan), so the prohibition breaks
nothing.

Files touched by the addendum: goga/pipeline/compiler/compile_flow.py,
goga/pipeline/compiler/CODEMANIFEST, goga/pipeline/CODEMANIFEST,
goga/pipeline/stage_env_wrappers.py (docstrings),
goga/pipeline/.usages/per-stage-env.md,
tests/pipeline/compiler/test_compile_flow.py,
tests/pipeline/compiler/test_compile_flow_workflow.py.
