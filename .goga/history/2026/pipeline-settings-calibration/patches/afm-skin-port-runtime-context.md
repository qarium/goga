# Change Plan — afm skin, pinned port, collaboration runtime context

Task Classification: **extension** (approved by the user 2026-11-02, ad-hoc stage
"Formalize the task, make the plan and implement it" — the approval is also the explicit
override of the breaking-change STOP recorded in the Compatibility Report).

1. **`collaboration.runtime_context: wrapper`** — `write_afm_config` writes the
   collaboration section on EVERY launch, always headed by
   `runtime_context: wrapper` (the static execution-context decision: every command goga
   hands the engine — client and generated profiles alike — is an as-claude wrapper or a
   closure over one). The profiles and `limits.max_tasks` keep their existing
   conditionality (both documents given / delegation block authored).
2. **`goga pipeline <name> --port <port>`** — a long-only click option,
   `IntRange(1, 65535)`, run form only (listing/card forms accept it without effect).
   When given, the value replaces the ephemeral allocation verbatim on BOTH substrates —
   the docker `-p <port>:<port>` publish and the in-container `--port <port>` argv — and
   no free-port search runs; a taken port surfaces as the docker/afm bind error itself.
   `None` (default) keeps the allocation. NOT host-only: the direct substrate consumes
   the port identically.
3. **`skin_dir` + the goga skin** — the config gains the sixth static field
   `skin_dir: /home/goga/.afm/skins`, and the new routine
   `materialize_afm_skin()` copies the installed package's
   `goga/assets/afm/skin/` (user-authored: index.css, goga-old.css, favicon.png,
   title.txt) flat into `/home/goga/.afm/skins/goga/` on every launch — validate-all,
   then reset, then copy; a missing/empty packaged skin is one strict pre-run error that
   never wipes the previously materialized skin.

---

# Change Execution Report

## Summary

Three launcher-side settings were added to the goga↔afm integration per the user's
request: the always-written `collaboration.runtime_context: wrapper` head in the
generated afm configuration; a `--port <port>` option on `goga pipeline` that pins the
dashboard port instead of allocating an ephemeral one; and the `skin_dir` static field
together with per-launch materialization of the packaged goga dashboard skin into
`/home/goga/.afm/skins/goga/`. The change was executed through the specification-governed
workflow: the CODEMANIFESTs of both affected cells, three usage documents, the project
afm usage doc, and the user docs were reconciled in the same change, and the full test
suite plus every project validator pass.

## Root Cause

Feature gap (not a defect): the generated afm config lacked `skin_dir` and
`collaboration.runtime_context` (both recognized by the installed afm binary — verified
against `/srv/afm`: the `skin_dir` yaml tag, the `collaboration.runtime_context` /
`collaboration.profiles.*.runtime_context` config paths, and the `wrapper` value
constant); the host launcher always allocated an ephemeral port with no CLI override;
and the goga package shipped no dashboard skin even though afm's `skin_dir` mechanism
expects `skin_dir/<theme>/*` on disk (its warning string
`warning: skin_dir %q has no %s, using skin %q` documents the builtin fallback). The
user authored the skin files in the repository during planning; the integration now
carries them.

## Modified Cells

| Cell | Files Modified |
|---|---|
| goga/pipeline | afm_config.py, afm_skin.py (new), run_pipeline.py, __init__.py, CODEMANIFEST, .usages/run-pipeline.md, .usages/pipeline-cli.md, assets/afm/skin/* (user-authored, consumed as-is) |
| goga/commands/pipeline | pipeline.py, run_pipeline_container.py, CODEMANIFEST, .usages/pipeline-command.md |
| (project-level) | .goga/usages/cooks/afm.md |
| (user docs) | docs/features/pipelines/cli.md, docs/features/pipelines/api.md, README.md |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| runtime_context head | goga/pipeline/afm_config.py | `_RUNTIME_CONTEXT = "wrapper"`; `_collaboration_section` emits the head; `write_afm_config` writes the bare head when flow/workform are not both given; `skin_dir` static field added (`_SKINS_DIR`) |
| Skin materialization | goga/pipeline/afm_skin.py (new) | `materialize_afm_skin() -> Path`: resolve the packaged dir, validate (non-empty), reset `/home/goga/.afm/skins/goga/`, flat copy, structured log line |
| Run-coordination step | goga/pipeline/run_pipeline.py | step 16 extended into afm-home authorship: `materialize_afm_skin()` right after `write_afm_config`, same failure window (before any run event) |
| Facade export | goga/pipeline/__init__.py | `materialize_afm_skin` in `__all__` (20 names) |
| `--port` option | goga/commands/pipeline/pipeline.py | long-only click option, `IntRange(1, 65535)`, default None; forwarded by keyword in the run-form dispatch |
| Port threading | goga/commands/pipeline/run_pipeline_container.py | `port: int \| None = None` on `run_pipeline_container` and `_run_named`; both substrate sites resolve `port if port is not None else _allocate_port()` |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| TestMaterializeAfmSkinContract / Logic | tests/pipeline/test_afm_skin.py | flat verbatim copy; the real packaged directory resolution; reset semantics (stale file removed); missing/empty source pre-run error; a failed validation never wipes a working skin |
| test_write_afm_config_static_fields_carry_six_entries; …_without_documents_writes_collaboration_head | tests/pipeline/test_afm_config.py | the six statics incl. `skin_dir`; the bare collaboration head |
| test_collaboration_profiles_require_both_flow_and_workflow; …_empty_profiles (updated) | tests/pipeline/test_afm_config_collaboration.py | section always written; profiles still require both documents; head + profiles + limits shape |
| TestPipelineRunPort (docker + direct) | tests/commands/pipeline/test_run_pipeline_container.py | given port skips `_allocate_port`; both sinks carry it verbatim; None keeps allocating |
| TestPipelinePortOption | tests/commands/pipeline/test_pipeline.py | forwarding, IntRange rejection (0/65536/-1/non-int), boundary acceptance (1/65535), list-form no-op |
| Updated assertions | tests/pipeline/{conftest,test_pipeline_contract,test_afm_config*}.py, tests/commands/pipeline/* | hermetic skins-base relocation (autouse), facade 19→20, signature lists ending in `port`, exact-call dispatch with `port=None` |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga/pipeline | cell annotations (afm-facing machinery, run parameters, skin step, collaboration delivery); new `default_skin` inline practice; `write_afm_config` rewritten (six fields, always-section, algorithm/requirements/constraints); new `materialize_afm_skin` contract; `run_pipeline` step 16 + requirements/constraints; port param doc; facade; Description footer | run-pipeline.md (six fields, always-head collaboration, new "afm skin materialization" section, port wording, `--port` threading chain); pipeline-cli.md (`--port` wording) |
| goga/commands/pipeline | `pipeline` signature + `port` param + dispatch + requirements; `run_pipeline_container` signature + `port` param + algorithm step 3 (resolve) + single-source note | pipeline-command.md (`--port` and the pre-existing `--fail-on-error` rows, ignored-forms list, docker shapes, direct path, `-p` namespaces, threading chain) |
| project | — | afm.md (`skin_dir` field row, `runtime_context` collaboration row, goga stance, six-constants integration pattern, pinned-port paragraph, `~/.afm/` tree with `skins/goga/`) |

## Validation Results

VERIFIED — full suite 8041 passed / 8 skipped (pre-existing skips) / 0 failed;
`ruff check goga/ tests/` clean; `goga lint` 92 cells / 0 errors; `goga schema` OK;
smoke render of the generated config shows exactly the requested content
(`skin_dir: /home/goga/.afm/skins`, `collaboration: {runtime_context: wrapper}`) and the
materialized skin directory carries the four packaged files.

## Compatibility Status

BREAKING (user-overridden): the generated afm config content changes for unchanged
callers (two new keys; the collaboration section appears even without flow/workflow) —
this IS the requested deliverable; afm accepts both keys (verified against the binary).
Everything else is additive-optional: signatures gain only defaulted parameters, absent
flags keep prior behavior, no paths move, no error messages change. The user approved
the plan with these consequences stated (autonomous_execution.q3.answer.json = "A").

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| afm rejects a bare `collaboration: {runtime_context: wrapper}` section | Low | Key and value verified in the installed binary; covered by contract tests; worst case the section head becomes conditional (one-line change) |
| Given port already occupied | Medium (operational) | The docker/afm bind error surfaces verbatim — the documented no-silent-fallback contract |
| Skin diverges from dashboard expectations | Low | The skin is the user's own authoring (goga-old.css imports afm's builtin `../goga/index.css`); afm falls back to the builtin skin with a warning |
| Test churn on future field additions | Low | The field-set assertions document the contract explicitly — a deliberate tripwire |

## Updated Files

- goga/pipeline/afm_config.py
- goga/pipeline/afm_skin.py (new)
- goga/pipeline/run_pipeline.py
- goga/pipeline/__init__.py
- goga/pipeline/CODEMANIFEST
- goga/pipeline/.usages/run-pipeline.md
- goga/pipeline/.usages/pipeline-cli.md
- goga/commands/pipeline/pipeline.py
- goga/commands/pipeline/run_pipeline_container.py
- goga/commands/pipeline/CODEMANIFEST
- goga/commands/pipeline/.usages/pipeline-command.md
- .goga/usages/cooks/afm.md
- docs/features/pipelines/cli.md
- docs/features/pipelines/api.md
- README.md
- tests/pipeline/conftest.py
- tests/pipeline/test_afm_config.py
- tests/pipeline/test_afm_config_collaboration.py
- tests/pipeline/test_afm_skin.py (new)
- tests/pipeline/test_pipeline_contract.py
- tests/commands/pipeline/test_pipeline.py
- tests/commands/pipeline/test_pipeline_dispatch.py
- tests/commands/pipeline/test_run_pipeline_container.py
- tests/commands/pipeline/test_run_pipeline_container_contract.py
- tests/commands/pipeline/test_run_pipeline_container_persistent.py
- goga/assets/afm/skin/ (user-authored, consumed as-is: index.css, goga-old.css, favicon.png, title.txt)
