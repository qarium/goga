# Plan: `assistants-in-pipeline`

Result of compiling `.goga/history/2026/assistants-in-pipeline/design.md` (verified by the
design-review stage — all 4 remarks fixed) into a ralphex-compatible execution plan. The four
CODEMANIFEST contracts (`goga/pipeline/workflow`, `goga/pipeline/compiler`, `goga/pipeline/hooks`,
`goga/pipeline`), every referenced `.usages/` file, and the two rider docs
(`docs/features/pipelines/workflows.md`, `docs/features/pipelines/pipeline-file.md`) are **already
materialized in the working tree** — this plan realigns the Python implementation with them. The
contracts, the usage files, the rider docs, and every "unchanged"/"final" module named by the design
are read-only for the implementation agent.

## Purpose

Make the pipeline-file a first-class assistant authoring surface: a pipeline author declares a
stage's helper assistants in the stage body itself (`assistants:` map inside the stage), every
declaration attaches to its own stage on every run — with a workflow-file or without one — and the
workflow governs the shipped assistants through origin-aware
`stages.<stage>.assistants.<name>` entries (a `{skip: true}` veto or an additive extension that
merges prompt/skills and overrides `when`/`gate`). After implementation:

- `WorkflowAssistant` is the absence-preserving gate/when/skip model — `gate`/`when`/`skip` default
  `None`, absence stays distinguishable from every authored value, and a `{skip: true}` entry
  carries nothing but the veto.
- `parse_workflow` accepts the skip-entry form and optional `when` on stage entries (the parser
  decides nothing about origins); the cross-surface duplicate-name rule moves to compilation.
- `parse_dsl` extracts each stage body's `assistants` map into a typed
  `dict[str, PipelineAssistant]` step field (deep-copied; the verbatim body excludes the key) and
  rejects delivery keys (`agent`, `env`, `delegate`) at parse time.
- `compile_flow` step 4.10 assembles every stage's effective attachments over the two authoring
  surfaces (pipeline declarations first, workflow entries second), enforces one global namespace
  uniqueness domain with authored-site collision errors, applies the veto/extension merge, and emits
  the team list from the catalog plus the attached pipeline declarations — on the workflow path AND
  the workflow-less path.
- `write_afm_config` takes the parsed `pipeline` document as its fourth artifact: the profiles gate
  widens to `flow` + (`workflow` or `pipeline`) (the D1 defect fix), and a pipeline-declared name
  resolves its delivery fields from its workflow extension entry, else the global agent.
- `run_pipeline` step 17 threads the `compile_flow`-returned `PipelineDocument` into the
  configuration write.
- `merge_workflow_overlay` (hooks) is **functionally unchanged** — only docstrings/comments state
  the form-blind append rule over the new entry forms.

Most important gaps between contract and code: `PipelineAssistant` does not exist (module and facade
export missing); `WorkflowAssistant` still carries materialized `gate=False`/`when="checkpoints"`
defaults and no `skip` field; `PhaseStep`/`StageStep` carry no `assistants` field;
`parse_workflow` still requires `when` at parse time and still runs
`_validate_assistant_namespace`; `parse_dsl` lets the stage-body `assistants` key die inside the
verbatim body (rejected later by `_reject_authoring_output_keys`); `compile_flow` resolves
attachments from the workflow surface only and returns an empty emission on the workflow-less path;
`write_afm_config` takes three parameters and gates profiles on `flow`+`workflow` only;
`run_pipeline` passes three arguments.

Implementation strategy: per-cell realignment in the design's fixed order — `workflow` (model, then
parser) → `compiler` (model + step fields, then `parse_dsl`, then `compile_flow`) → `hooks`
(documentation + characterization tests) → `pipeline` (delivery, then wiring + end-to-end). Every
coding task follows the TDD workflow (contract tests → code → verification → logic tests →
debugging → re-verification → lint) and the Mandatory Rules below.

## Context

### Contract Surface

All signatures below are the **already-materialized contract state** (read-only). The
implementation must match them exactly.

#### Cell `goga/pipeline/workflow` (leaf — the workflow-file parser)

**Entity: `WorkflowAssistant`** — CHANGED (model)
- Type: `class` (Entity, `@dataclass(kw_only=True)`)
- Declared `location`: `workflow_assistant.py`
- Facade obligation: importable from `goga.pipeline.workflow`, listed in `__all__` (already there)
- Contract signature:
  `WorkflowAssistant(name: str, prompt: str | None = None, skills: list[str] | None = None, agent: str | None = None, delegate: bool | None = None, env: dict[str, str] | None = None, gate: bool | None = None, when: str | None = None, skip: bool | None = None)`
- Changes: `gate: bool = False` → `gate: bool | None = None`; `when: str = "checkpoints"` →
  `when: str | None = None`; NEW trailing field `skip: bool | None = None`. Field order fixed:
  name, prompt, skills, agent, delegate, env, gate, when, skip (nine fields).
- Semantic requirements: absence stays distinguishable from every authored value on all three
  attachment parameters (`gate`/`when`/`skip`); a `{skip: true}` entry carries `skip=True` and
  `None` for every other field; the model validates nothing (parse owns the vocabulary); consumers
  discriminate by PRESENCE, never truthiness — declaration ⇔ any of
  prompt/skills/agent/delegate/env is not `None`, veto ⇔ `skip is True`.

**Entity: `parse_workflow`** — CHANGED (step 6.7 rewrite, 6.5 narrowing)
- Type: `function` (Routine); `location`: `parse_workflow.py`; facade: `goga.pipeline.workflow`
- Signature: unchanged — `parse_workflow(text: str) -> document: WorkflowDocument`
- Changes: stage-entry grammar (6.7) — skip form, optional `when`, empty-entry rejection; 6.5 keeps
  per-map name rules only; `_validate_assistant_namespace` and its call site are DELETED (the
  document-wide duplicate-name guarantee moves to compilation). See Task 2 for the full algorithm
  and the exact error texts.

#### Cell `goga/pipeline/compiler` (pure transformer — imports the workflow cell)

**Entity: `PipelineAssistant`** — NEW
- Type: `class` (Entity, `@dataclass(kw_only=True)`)
- Declared `location`: `pipeline_assistant.py`
- Facade obligation: importable from `goga.pipeline.compiler`, listed in `__all__` (NEW export —
  the facade currently lacks it)
- Contract signature:
  `PipelineAssistant(name: str, prompt: str | None = None, skills: list[str] | None = None, when: str, gate: bool = False)`
- Field order fixed: name, prompt, skills, when, gate. `when` has **no default** (no
  compiler-side engagement default); `gate` defaults to `False` (materialized advisory). No
  delivery fields — `agent`, `env`, `delegate` are workflow-file territory.
- Semantic requirements: pure data; validates nothing (`parse_dsl` enforces the vocabulary);
  `skills: []` is a value (a declaration resolving content).

**Entity: `PhaseStep`** — CHANGED
- Declared `location`: `phase_step.py`; facade: `goga.pipeline.compiler`
- Contract signature:
  `PhaseStep(name: str, title: str, body: dict[str, Any], assistants: dict[str, PipelineAssistant] | None = None)`
- Change: NEW trailing field `assistants` — the step's pipeline declarations keyed by name in
  authored order, `None` when the source body carries no `assistants` key or an empty map; the
  verbatim `body` EXCLUDES the extracted key.

**Entity: `StageStep`** — CHANGED
- Declared `location`: `stage_step.py`; facade: `goga.pipeline.compiler`
- Contract signature:
  `StageStep(name: str, title: str, depends_on: list[str] | None, body: dict[str, Any], assistants: dict[str, PipelineAssistant] | None = None)`
- Change: the same NEW trailing `assistants` field with the same semantics.

**Entity: `parse_dsl`** — CHANGED (step 4a)
- Type: `function` (Routine); `location`: `parse_dsl.py`; facade: `goga.pipeline.compiler`
- Signature: unchanged — `parse_dsl(text: str) -> (header: PipelineHeader, fmt: BodyFormat, body: PhasesBody | StagesBody)`
- Change: NEW step 4a — `_extract_step_assistants(stage, item)` reads each step item's
  `assistants` map, validates it, builds `dict[str, PipelineAssistant]` (deep-copied), and the
  verbatim body excludes the key (`_PHASE_STEP_KEYS` / `_STAGE_STEP_KEYS` gain `"assistants"`).
  See Task 4 for the full algorithm and the exact error texts (D2 parse-time form `stage <name>`).

**Entity: `compile_flow`** — CHANGED (step 4.10 rewrite, team emission, workflow-less path)
- Type: `function` (Routine); `location`: `compile_flow.py`; facade: `goga.pipeline.compiler`
- Signature: unchanged —
  `compile_flow(pipeline_path: Path, flow_path: Path, workflow: WorkflowDocument | None = None, root_dir: str | None = None, project_name: str | None = None) -> (pipeline: PipelineDocument, flow: FlowDocument)`
- Changes: step 4.10 becomes the two-surface assembly (the ONLY place both documents meet);
  `_make_expanded_copy` deep-copies `assistants` onto every copy; extend-embedded steps construct
  with `assistants=None`; the workflow-less path builds `identity_ids = {step.name: [step.name] for
  step in reconstructed}` and calls `_collaboration_emission(None, {}, reconstructed,
  identity_ids)` so declarations attach without a workflow. See Task 5 for the full algorithm
  (A–F), helpers (`_assistant_namespace` collision ownership, the pipeline declaration index,
  `_assemble_stage_attachments`, `join_prompt`, `expand_skills`), and the exact error texts.
- Untouched within the cell: `serialize_flow`, `FlowAssistant`, `FlowTeamMember`,
  `FlowCollaboration`, `_reject_authoring_output_keys` (its `assistants` branch stays byte-for-byte
  — after the parse-time extraction it fires only for embedded extend bodies).

#### Cell `goga/pipeline/hooks` (imports the workflow cell)

**Entity: `merge_workflow_overlay`** — NO functional change
- Type: `function` (Routine); `location`: `overlay.py`; facade: `goga.pipeline.hooks`
- Signature and algorithm: unchanged. The existing presence-based declaration discriminator
  (`_is_assistant_declaration` — any of the five declaration fields present) already yields the
  contracted form-blind append rule over the new entry forms: a `{skip: true}` entry and a
  gate/when-only entry are NOT declaration-shaped → always append (subject only to the
  name-on-stage drop). Only the module docstring, `_merge_stage_assistants`, and
  `_is_assistant_declaration` docstrings are updated to state the new forms and the pipeline-blind
  posture (see Task 6).

#### Cell `goga/pipeline` (the pipeline domain — imports compiler, workflow, hooks)

**Entity: `write_afm_config`** — CHANGED
- Type: `function` (Routine); `location`: `afm_config.py`; facade: `goga.pipeline`
- Contract signature:
  `write_afm_config(agent: str | None, flow: FlowDocument | None = None, workflow: WorkflowDocument | None = None, pipeline: PipelineDocument | None = None) -> config_path: Path`
- Changes: NEW trailing `pipeline` parameter (the parsed pipeline document — the carrier of the
  stage-body declarations); the profiles gate widens to `flow is not None and (workflow is not
  None or pipeline is not None)` (the D1 fix); `_resolve_profiles` resolves each referenced name
  across the workflow namespace FIRST, else the pipeline declaration index
  (`_pipeline_declaring_stages(pipeline)` — name → declaring stage from `pipeline.body.steps`);
  a pipeline-declared name takes delivery `(agent, delegate, env)` from its workflow extension
  entry `workflow.stages[<declaring stage>].assistants.get(name)` (all `None` when absent or no
  workflow); its site is `pipeline.<stage>` (D2). See Task 7 for the delivery algorithm.

**Entity: `run_pipeline`** — CHANGED (wiring only)
- Type: `function` (Routine); `location`: `run_pipeline.py`; facade: `goga.pipeline`
- Signature: unchanged. Change: algorithm step 17 only — the call becomes
  `write_afm_config(effective_agent, flow_doc, overlay.workflow, pipeline_doc)` with `pipeline_doc`
  being the `compile_flow` return already in scope at step 13. No other step changes.

### Re-exports

None. No `->Name: {}` block changes in any manifest. The compiler facade gains one direct export
of its own new entity (`PipelineAssistant`); the workflow and hooks facades are unchanged.

### Usages Context

- `convention` (`.goga/usages/conventions.md`): the mandatory ruleset for every touched module and
  test file — code style, dataclass discipline, docstring style, test layout and rules, lint and
  validation commands, and the organization of the REPL development cycle. Extracted in full into
  the **Mandatory Rules** section below and applied in every task.
- `beautiful_yaml` (`.goga/usages/cooks/beautiful_yaml.md`): the PyYAML serialization parameters
  for the written artifacts. Where used: `serialize_flow` and `write_afm_config` — both unchanged
  in their serialization calls; the new emission rides the existing structures. No new
  serialization sites. Context only — no task action.
- `afm` (`.goga/usages/cooks/afm.md`): the engine contract — profile shape (`{title, command,
  delegate}`), stage attachment strict-parsing (five keys only — no `skills` key on
  `FlowAssistant`), mode/trigger vocabularies (`pre_completion` is gated-only), limits, config
  layers. Where used: `FlowAssistant` emission, `_GATE_MODE` / `_WHEN_TRIGGER` /
  `_attachment_trigger` (unchanged mappings — the extension's effective gate/when feed the same
  mapping; every trigger written explicitly), `write_afm_config` profiles. Applied in Tasks 5 and 7.

### Imported Usages

- `assistants` from `goga/pipeline/workflow` (`goga/pipeline/workflow/.usages/assistants.md`) —
  the authoring vocabulary of the workflow surface and the governance forms (skip veto, extension)
  the compiler resolves. Applied in Tasks 5 and 7 (origin resolution, delivery expectations). The
  file is **final** (updated at materialization; verified against the design).
- `parse-workflow` from `goga/pipeline/workflow`
  (`goga/pipeline/workflow/.usages/parse-workflow.md`) — the parsed model's shape and the
  guarantees the compiler relies on (absence-preserving fields, skip carriage, no origin
  classification). Applied in Tasks 2 and 5. Final.
- `collaboration-emission` from `goga/pipeline/compiler`
  (`goga/pipeline/compiler/.usages/collaboration-emission.md`) — the compiled surface the profile
  ids are read from (imported by the `goga/pipeline` cell). Applied in Task 7. Final.
- `compile-flow`, `parse-dsl` from `goga/pipeline/compiler` and `checkpoints` from
  `goga/pipeline/hooks` — consulted for the respective surfaces; no new obligations. Final.

### Local Usages

None. The design's `.usages/` Update section confirms every usage file is status **current**
(updated at materialization; verified against the design — additions needed: none). Decision rule:
every change falls inside existing functional domains. This plan creates and modifies **no** usage
files.

### External Dependencies

- `pyyaml>=6.0` — YAML parse/dump (already a dependency; no new dependency).
- `pytest>=8.0` + `tmp_path` + `monkeypatch` — the test framework; no new test dependency.
- `ruff>=0.15.0` — lint and format (already in the `test` extra).
- `goga` CLI — `goga lint` (DSL validation over all cells; must stay 93 cells / 0 errors) and
  `goga schema` (the dependency map must stay unchanged).

## Mandatory Rules (extracted from `convention` — apply in every task, every stage, every commit)

The rules below are compiled for this change from the `convention` practice
(`.goga/usages/conventions.md` — engineering principles, development constraints, imports, data
models, logging, code formatting, docstrings, dependencies, the whole Testing section, and the
validation commands), the Python contract rules (mandatory type hints and their allowed forms,
naming, facade discipline), and the repository's own policy (the `pyproject.toml` ruff
configuration, the `.githooks` commit policy) — the CODEMANIFEST annotations attribute the
REPL-cycle organization to `convention`; R4 spells that attribution out concretely. They are
**mandatory** — the convention's own precedence applies: contract first, facade obligations second,
these conventions next, language idioms last. Violations are task failures, not style nits.

### R1. Coding style

- **Runtime**: Python 3.10+ only; all configuration through `pyproject.toml`; **all** code and
  tests execute inside the project virtualenv (create it if missing); never the system
  interpreter.
- **Imports**: relative imports for ALL intra-package references
  (`from .pipeline_assistant import PipelineAssistant`, `from ..workflow import WorkflowDocument`);
  absolute imports only for stdlib and third-party (`copy`, `dataclasses`, `logging`, `yaml`).
  Exception — tests: inside `tests/`, cross-directory references use absolute imports rooted at
  the `tests` package (`from tests.conftest import ...`).
- **Data models**: stdlib `dataclasses` only (NOT pydantic); every model class
  `@dataclass(kw_only=True)`; empty defaults for fields; `None` only for fields that represent the
  explicit absence of a value. The changed `WorkflowAssistant` fields (`gate`/`when`/`skip` →
  `None` defaults) and the new `PipelineAssistant` follow exactly this rule — absence vs authored
  value is the semantic core of this change.
- **Type hints**: mandatory on every public surface; allowed forms `str`, `int`, `float`, `bool`,
  `list[T]`, `dict[str, T]`, `T | None`; forbidden: `*args`/`**kwargs`, bare `dict`, bare `list`.
- **Naming**: PascalCase classes; snake_case functions, methods, and properties.
- **Function-body formatting**: logical blocks inside function/method bodies are separated by one
  blank line — initialization vs conditionals/loops, data preparation vs processing, processing vs
  the return.
- **Docstrings**: Google style, mandatory for all public functions, methods, and classes. First
  line capitalized and ending with a period; `Args` when parameters exist, `Returns` when a value
  returns, `Raises` for exceptions beyond built-in behavior. Module docstrings in the cell's
  one-line form (e.g. "The ``PipelineAssistant`` dataclass — one pipeline-file stage-declared
  helper."). Keep comments laconic and professional — one point per comment.
- **Logging**: stdlib `logging` with module-level `logger = logging.getLogger(__name__)`;
  lowercase, structured, operationally worded messages with contextual metadata. This change adds
  **no** log lines: the one existing WARNING site (the inline-declaration skills warning) keeps
  its exact wording and trigger, now excluding pipeline declarations (they have a team channel);
  the `compile_flow` info line and the `write_afm_config` profiles info line are unchanged.
- **Dependencies**: any third-party library must live in `pyproject.toml` with a minimum version.
  This change adds none.

### R2. Test writing

- **Framework and layout**: pytest; tests mirror the source structure directly —
  `goga/pipeline/compiler/pipeline_assistant.py` →
  `tests/pipeline/compiler/test_data_models.py` (the existing data-model suite — no new file per
  the design registry); every test directory carries `__init__.py`; local fixtures in
  `tests/<package>/conftest.py`, shared fixtures in `tests/conftest.py`. No new directories — all
  target test files exist.
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`
  (e.g. `test_complexity_with_empty_input` — the convention's own example shape, as in
  `test_sc2_skip_veto_removes_attachment_team_and_profile`); grouping `class Test<Component>:`.
  Self-documenting names; minimal comments.
- **Order (TDD)**: contract tests FIRST in every coding task (facade importability, `__all__`
  membership, signature shape via `inspect.signature`, field lists/defaults/annotations) — they
  fail before implementation and that failure is expected; logic tests AFTER the implementation
  (positive, negative, edge — empty inputs `None`/`""`/`[]`/`{}`, boundary values such as `0` and
  `False`, invalid types, expected exceptions via `pytest.raises`).
- **Boundary tables**: for thresholds, ranges, and vocabulary domains — `@pytest.mark.parametrize`
  with a table of values including each boundary (the design's
  `test_pipeline_declaration_vocabulary_rejections` is exactly this shape).
- **Assertions**: expected exceptions via `pytest.raises(..., match=<regex>)`; for long messages
  match a regex prefix (`re.escape` on the pinned prefix), never exact equality on a message that
  continues beyond the pinned part; for the contract-fixed texts the design pins, assert the exact
  string.
- **Mocks**: pure logic is tested **without mocks** — the parser and compiler tests are mock-free;
  file I/O uses `tmp_path` exclusively (pipeline-files as `tmp_path/"pipeline.yml"`, workflows as
  `tmp_path/"workflow.yml"`); no network, no subprocess. Mock only at external boundaries —
  business-logic tests stay mock-free. Delivery tests monkeypatch the closure/env foundations per
  the existing `tests/pipeline/test_afm_config_collaboration.py` pattern.
- **Routine testing**: call the handler function directly via Python (`parse_dsl(text)`,
  `compile_flow(...)`, `write_afm_config(...)`, `run_pipeline(...)`) — never a subprocess.
- **Traceability**: every test names the contract entity and scenario it verifies; the mapping
  entity → location → tests is auditable per task.

### R3. Lint and format enforcement (all development stages and local commits)

- **Lint gate**: `ruff check goga/` and `ruff check tests/` (the project linter, configured in
  `pyproject.toml` — line length 120, target py310, the full rule selection with the tests
  per-file ignores). The gate runs at: STEP 7 (Lint) of every coding task, the completion of every
  task, and **before every local commit**. A commit with lint findings is forbidden — fix the
  findings or do not commit.
- **Format gate**: `ruff format` per the `[tool.ruff.format]` config (double quotes, space indent,
  LF line endings, magic trailing comma honored) over **every Python file the task touched**,
  included in the same commit. The repository is currently fully format-clean (1070 files) — it
  must remain so; never leave a touched file unformatted.
- **Test gate before commit**: the task's scoped test command green and `pytest tests/ -x` green
  (no new failures against the recorded baseline — see Facts); `goga lint` green (93 cells, 0
  errors — proves the CODEMANIFESTs stayed untouched); `goga schema` unchanged map.
- **Commits**: conventional, per-task commits; the repo's `.githooks` policy applies (commit-msg
  blocks any `Co-Authored-By` trailer; pre-push scans new commits) — `make install-hooks` if the
  hooks path is not yet set.

### R4. REPL development cycle (continuous interactive evaluation → hot reloading → migration to source files)

Every coding task works as a REPL-driven loop, per the `convention` practice's REPL-cycle role
(the CODEMANIFEST annotations name it first among the practice's uses):

1. **Evaluate interactively before coding.** Probe every behavior you do not know exactly in an
   active Python session inside the venv, against the real dependencies: `dataclasses.fields`
   order and `inspect.signature` shape after a model edit; `copy.deepcopy` independence of a
   nested `dict[str, PipelineAssistant]`; dict iteration order for the namespace walks; the
   composed error-message strings (`f"{site1}, {site2}"` collision shape); the presence-based
   `join_prompt` behavior with authored empty-string prompts; the `entry.gate if entry.gate is not
   None else decl.gate` selection on all three gate states. A behavior whose live shape is unknown
   is not yet implementable.
2. **Keep the loop continuous.** After each edit of a module, re-import in a fresh interpreter
   (`python -c` probe or a new REPL) and re-run the focused probes — the touched modules are pure
   and import-time-cheap, so the evaluation loop is seconds, not minutes. In a long-lived session
   use `importlib.reload` for a just-edited module; when state goes stale, **restart the
   interpreter** — never work around stale imports.
3. **Migrate verified code to source files.** The REPL is scratch space only: every verified
   expression, message format, and edge-case result migrates into the module at its declared
   `location` (implementation) or into the task's test files (as assertions). Nothing verified in
   a session may live only there.
4. **Probes inform tests, never replace them.** Every task still ends with the pytest and lint
   commands of the Validation Commands section; a REPL observation that a test must capture goes
   into the test, not into memory.

## Facts

- The branch is `assistants-in-pipeline`; the four CODEMANIFESTs, the seven `.usages/` files, and
  the two rider docs are already materialized in the working tree (unstaged diff vs HEAD);
  `goga lint` — **93 cells, 0 errors**; `goga schema` — the unchanged dependency map
  (workflow ← compiler ← pipeline; workflow ← hooks ← pipeline), no cycles. They are the read-only
  source of truth.
- The design passed the design-review stage: 4 remarks fixed (High 1, Medium 2, Low 2) — the
  `on_completion` trigger expectation for an explicitly downgraded finish extension, the two new
  pipeline-side negative-test specifications, the pinned-test rework groups, the D2 wording and
  the `join_prompt` presence rule.
- Baseline state (verified in the authoring environment): `pytest tests/pipeline -q` → 2055
  passed, **6 failed** — all six pre-existing at clean HEAD (`git stash` verified) and
  environmental: they spawn subprocess interpreters that lack PyYAML on their path
  (`test_hook_bridge.py` ×3, `test_pipeline_contract.py::TestFacadeLaziness` ×3). Out of scope for
  this change; the gate is "no NEW failures". `ruff check goga/` clean; `ruff check tests/` clean;
  `ruff format --check` — 1070 files already formatted. Python 3.12.16, ruff 0.17.6, pytest 9.2.0.
- `WorkflowAssistant` (`goga/pipeline/workflow/workflow_assistant.py:58-65`) carries exactly eight
  fields with `gate: bool = False` and `when: str = "checkpoints"` — pinned by
  `tests/pipeline/workflow/test_workflow_assistant_contract.py::test_workflow_assistant_signature_matches_contract`
  (the eight-parameter list, defaults `[empty, None×5, False, "checkpoints"]`, annotations) and
  `..._field_order_fixed`; logic pins in `test_workflow_assistant_logic.py`
  (`test_workflow_assistant_defaults_are_materialized` asserts the materialized defaults). These
  fail on the first model edit — rework them FIRST (the design's Additional Instructions).
- `parse_workflow` (`goga/pipeline/workflow/parse_workflow.py`): the parse-time `when`-required
  check lives at `_build_stage_assistants` (lines 1669-1672, checked before form discrimination);
  the reference/declaration discrimination is `set(entry_value) <= {"gate", "when"}` (line 1687);
  `_validate_assistant_namespace` (line 1803) is called at line 267. Pinned by
  `tests/pipeline/workflow/test_parse_workflow_assistants.py`:
  `test_parse_attachment_missing_when` (line 556), the `when is required` parametrized rows
  (lines 613-621), `test_parse_duplicate_assistant_name_across_surfaces` (line 349),
  `test_parse_workflow_override_style_inline_counts_for_duplicate_name` (line 364), the duplicate
  row at line 644 — these move to the compiler suite (Task 5) per the design; the
  materialized-default rows (lines 115-116, 121, 519) are reworked in place (Task 2).
- `goga/pipeline/compiler/pipeline_assistant.py` does not exist; the compiler facade
  (`goga/pipeline/compiler/__init__.py`) does not list `PipelineAssistant` (alphabetical slot:
  between `"PhasesBody"` and `"PipelineDocument"`).
- `PhaseStep` / `StageStep` (`phase_step.py:22-25`, `stage_step.py:26-31`) carry no `assistants`
  field; `parse_dsl`'s `_PHASE_STEP_KEYS` (line 39) and `_STAGE_STEP_KEYS` (line 45) exclude
  `assistants`, so today the key lands in the verbatim body and dies in
  `_reject_authoring_output_keys` (`compile_flow.py:331-332`, text `"assistants key is forbidden
  in stage body; use assistants in workflow.stages"`) — pinned by
  `tests/pipeline/compiler/test_compile_flow_collaboration.py::test_authored_assistants_key_in_stage_body_rejected`
  (line 132; its list-form fixture must move to an embedded extend body — Task 5).
- `compile_flow` (`goga/pipeline/compiler/compile_flow.py`): `_collaboration_emission` (line 1259)
  early-returns an empty emission when `workflow is None` (lines 2295-2300); the workflow-less
  branch in `compile_flow` (lines 2289-2292) calls `_collaboration_emission(None, {}, [], {})`;
  `_assistants_by_id` (line 1132) resolves workflow entries only; `_team_members` (line 1047)
  draws from the catalog only; `_reject_attachment_body` (line 1102) hardcodes the
  `workflow.stages.` site prefix; `_make_expanded_copy` (line 1624) copies name/title/body
  (and depends_on) — no `assistants` carriage; `_GATE_MODE`/`_WHEN_TRIGGER`/`_attachment_trigger`
  (lines 181-216) are the fixed translation tables (`pre_completion` gated-finish-only).
- `write_afm_config` (`goga/pipeline/afm_config.py:318-322`) takes exactly `(agent, flow=None,
  workflow=None)`; the profiles gate is `flow is not None and workflow is not None` (line 415) —
  pinned by `tests/pipeline/test_afm_config_collaboration.py::
  test_collaboration_profiles_require_both_flow_and_workflow` (line 99; reworked in Task 7) and the
  three-parameter signature itself by `tests/pipeline/test_afm_config.py::
  TestWriteAfmConfigContract::test_write_afm_config_signature_matches_contract` (line 55; reworked
  in Task 7);
  `_resolve_profiles` (line 146) resolves through the workflow namespace only;
  `_assistant_namespace` (line 77) sites entries as `workflow.stages.<stage>`; the file imports
  `FlowDocument` from `.compiler` at runtime (line 14) — `PipelineDocument` joins that import.
- `run_pipeline` (`goga/pipeline/run_pipeline.py`): `compile_flow` returns `pipeline_doc` at line
  477; the delivery call at line 532 passes three arguments. The exact call text is source-pinned
  by `tests/pipeline/test_run_pipeline_contract.py::
  test_run_pipeline_source_consumes_the_effective_configuration` (line 453, the assert at 467;
  reworked in Task 8).
- The overlay (`goga/pipeline/hooks/overlay.py`): `_is_assistant_declaration` (line 88),
  `_merge_stage_assistants` (line 229), `_authored_namespace` (line 408) — the presence-based
  discriminator already implements the contracted form-blind rule; no functional edit.
  `tests/pipeline/hooks/test_overlay_assistants.py` exists (contract + behavior classes).
- The `_compile` helper pattern (`tests/pipeline/compiler/test_compile_flow_collaboration.py:75`)
  writes `tmp_path/"pipeline.yml"` (+ optional workflow), compiles, returns documents + text — the
  shape the new compile tests reuse. The serialization golden pattern lives in
  `tests/pipeline/compiler/test_serialize_flow_collaboration.py` (frozen byte-identity literals).
- No new dependencies, no new cells, no `.usages/` changes, no docs changes (riders final).

### Entity Interaction and Data Flow (from the design — verified, transfer verbatim)

```
 pipeline-file (stage bodies carry assistants:)          workflow-file
        │                                                      │
        ▼                                                      ▼
  parse_dsl ──(4a)──► PipelineAssistant ──► PhaseStep/StageStep.assistants
        │                                                      │
        │                                                parse_workflow
        │                                                      │
        │                                     WorkflowAssistant (gate/when/skip
        │                                     absence-preserving; skip veto)
        │                                                      │
        ▼                                                      ▼
        └──────────────────► compile_flow ◄─────────────────────┘
                              (step 4.10 — the ONLY place both documents meet)
                              │  namespace: catalog ∪ inline ∪ pipeline decls
                              │  per stage: pipeline decls first, then wf entries
                              │  veto / extension / reference / inline resolution
                              ▼
                    FlowDocument { collaboration, team, stages[].assistants }
                              │                       │
                              │                       ▼
                              │              serialize_flow → flow-file
                              ▼
                       PipelineDocument (ORIGINAL body — declarations carried)
                              │
   run_pipeline (step 17) ────┤  write_afm_config(agent, flow, workflow, pipeline)
                              ▼
                    afm config: collaboration.profiles.goga-<name>, limits
                              │
   workflow amendment (hooks) │  merge_workflow_overlay — form-blind append,
                              ▼  pipeline-blind; collisions surface at compile
```

**Data flows**:

1. **Flow 1 — authoring (pipeline side).** `parse_dsl` splits header/body, builds steps; step 4a
   extracts each step's `assistants` map into `dict[str, PipelineAssistant]` (deep-copied),
   excludes the key from the verbatim body. Declarations ride `PipelineDocument.body` untouched to
   every consumer.
2. **Flow 2 — authoring (workflow side).** `parse_workflow` builds `WorkflowAssistant` entries
   with `gate`/`when`/`skip` carried as authored or `None`. The parser performs NO origin
   classification and NO cross-surface uniqueness check.
3. **Flow 3 — amendment.** `merge_workflow_overlay` merges tool contributions into the workflow
   document; every stage-entry form (veto, when-less extension, reference, declaration) rides the
   append rule; entries addressing pipeline names pass through unresolved.
4. **Flow 4 — compilation.** `compile_flow` builds the working body (deep copy → extend embed →
   skip removal → overrides → loop expansion; copies carry the declarations), then step 4.10
   assembles per-stage attachments (pipeline declarations first, workflow entries second), detects
   namespace collisions, enforces the origin-aware `when` check, applies veto/extension, and emits
   the team list (catalog then attached pipeline declarations) and the per-stage `assistants`
   lists. Output-side only — `PipelineDocument` is never mutated.
5. **Flow 5 — delivery.** `run_pipeline` step 17 calls `write_afm_config` with the effective
   agent, the compiled flow, the effective (overlay) workflow, and the parsed pipeline document.
   For each flow-referenced `goga-<name>` id the delivery source resolves across the workflow
   namespace and the pipeline declarations; a pipeline-declared name takes delivery fields from its
   workflow extension entry, else the global agent.

**Entity dependencies** (implementation order, bottom-up; matches the contract dependency map):

1. `goga/pipeline/workflow` — `WorkflowAssistant` model, then `parse_workflow` (no dependencies).
2. `goga/pipeline/compiler` — `PipelineAssistant`, `PhaseStep`/`StageStep`, `parse_dsl` 4a, then
   `compile_flow` 4.10 (imports workflow).
3. `goga/pipeline/hooks` — docstring updates only (imports workflow).
4. `goga/pipeline` — `afm_config`, then `run_pipeline` step 17 (imports all).

## Gap Analysis

- **Missing contract entities**: `PipelineAssistant` (Entity, `pipeline_assistant.py`) — no module,
  no facade export, no tests.
- **Missing facade exposure**: `"PipelineAssistant"` absent from
  `goga/pipeline/compiler/__init__.py` (`__all__` and the import block).
- **API mismatches**:
  - `WorkflowAssistant`: `gate`/`when` still materialized (`False`/`"checkpoints"`), no `skip`
    field;
  - `PhaseStep`/`StageStep`: no trailing `assistants` field;
  - `parse_dsl`: no step 4a — the `assistants` key is neither extracted nor excluded;
  - `write_afm_config`: no `pipeline` parameter; the gate is `flow`+`workflow` only (the D1
    defect);
  - `run_pipeline`: three-argument delivery call.
- **Behavioral mismatches**: `parse_workflow` rejects skip entries, requires `when` at parse time,
  and runs the document-wide duplicate-name check (all three must move/change);
  `compile_flow`'s workflow-less path emits nothing (no `identity_ids`, empty emission), the
  assembly resolves workflow entries only (no pipeline declarations, no veto, no extension merge,
  no origin-aware `when` check, no cross-surface namespace), the team draws from the catalog only,
  body prohibitions always say `workflow.stages.`, and `_make_expanded_copy` drops `assistants`;
  `_resolve_profiles` never resolves a pipeline-declared name.
- **Existing code reused as-is**: `_GATE_MODE`/`_WHEN_TRIGGER`/`_attachment_trigger`,
  `serialize_flow`, `FlowAssistant`/`FlowTeamMember`/`FlowCollaboration`,
  `_reject_authoring_output_keys` (byte-identical branch), the whole overlay merge machinery, the
  `_compile` test helper, the delivery-test scaffolding (closure/env foundations), the run-level
  test scaffolding of `test_run_pipeline_workflow.py`.
- **Test coverage gaps**: no tests for the skip grammar, the absence-preserving model, step 4a
  (all seven rejection cases + the positive carriage), the two-surface assembly (SC1–SC3), the
  moved checks (when-required, duplicate-name), the widened delivery gate (D1), the pipeline
  delivery branch, and the step-17 threading; the pinned suites named in Facts assert the OLD
  behavior and must be reworked in the same change sets as the code they pin.
- **Usage files / docs**: current and final — no gaps, no tasks.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next,
> in the design's fixed order `workflow → compiler → hooks → pipeline` (each cell consumes only
> what the earlier ones provide; the dependency direction never reverses). Within each coding
> task, contract tests are written first (TDD workflow).

> **Global implementation rules (apply to every task)**:
> - **`CODEMANIFEST` files are read-only.** If implementation does not match the contract, fix the
>   implementation — never fix the contract. `goga lint` must stay 93 cells / 0 errors.
> - **The seven `.usages/` files and the two rider docs are final** — do not touch them; the code
>   is made to match them.
> - **Do not touch** `serialize_flow`, `FlowAssistant`, `FlowTeamMember`, `FlowCollaboration`,
>   `_reject_authoring_output_keys`' `assistants` branch (byte-identical), the overlay merge logic
>   (docstrings only), or `goga/pipeline/cli.py` — final as they stand.
> - **Error texts are part of the contract** — copy them verbatim from this plan (which carries
>   them verbatim from the design): the D2 message set is normative; the pre-existing messages
>   quoted in the algorithms must not change by a character (SC5 covers outputs; the unchanged
>   wording covers errors).
> - The **Mandatory Rules** (R1 style, R2 tests, R3 lint/format + commit gates, R4 REPL cycle)
>   apply to every task and every commit — R3's gates are part of every task's completion.
> - Implement in the dependency order of the tasks; after each cell, run `ruff check goga/` and
>   the cell's test module before moving on (the design's Additional Instructions).
> - The parsed pipeline document mirrors the authored source: never mutate `PipelineDocument` or
>   its steps during compilation; the extension applies output-side only.

### Task 1: The absence-preserving `WorkflowAssistant` model (goga/pipeline/workflow)

Rework `WorkflowAssistant` (`workflow_assistant.py`) to the absence-preserving gate/when/skip
model and rework its pinned suites FIRST (they fail on the first field edit — the design's
ordering instruction for this cell). One dataclass edit, one docstring rewrite, two test modules
reworked; no behavior — the model validates nothing.

**Contract entity**: `WorkflowAssistant` (location `workflow_assistant.py`), contract signature
`WorkflowAssistant(name, prompt=None, skills=None, agent=None, delegate=None, env=None,
gate: bool | None = None, when: str | None = None, skip: bool | None = None)`. Facade: already
importable from `goga.pipeline.workflow` and listed in `__all__` — unchanged.

**Usages relevant to this task:**
- `convention`: dataclass discipline (`kw_only=True`, `None` only for explicit absence — R1),
  Google docstring style, test rules R2, gates R3, REPL cycle R4 (probe the post-edit signature
  live before pinning the test expectations).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Model algorithm (from the design — verbatim; construction only — pure data):

```
1. parse_workflow constructs:
   - catalog entry   → name, prompt?, skills?, agent?, delegate?, env?
                        (gate/when/skip stay None — catalog rejects the keys)
   - skip entry      → name, skip=True (every other field None)
   - other entry     → the seven authored fields; gate/when None when absent
2. consumers discriminate by PRESENCE (never truthiness):
   declaration ⇔ any of prompt/skills/agent/delegate/env is not None
   veto        ⇔ skip is True
```

Edge cases: `skills: []` / `env: {}` are authored values (explicit overrides that clear);
`delegate`/`gate`/`when`/`skip` absent are `None` — absence and authored `false` stay
distinguishable.

REPL-cycle checkpoints (R4): before writing the reworked assertions, probe live —
`[(f.name, f.default) for f in dataclasses.fields(WorkflowAssistant)]` after the edit;
`inspect.signature(WorkflowAssistant)` parameter list and annotation strings; construct
`WorkflowAssistant(name="x", skip=True)` and confirm every other field `None`.

- [x] **Contract tests**: rework `tests/pipeline/workflow/test_workflow_assistant_contract.py` —
      `test_workflow_assistant_signature_matches_contract`: nine parameters
      `[name, prompt, skills, agent, delegate, env, gate, when, skip]`, defaults
      `[empty, None, None, None, None, None, None, None, None]`, annotations
      `[str, str | None, list[str] | None, str | None, bool | None, dict[str, str] | None,
      bool | None, str | None, bool | None]`; `test_workflow_assistant_field_order_fixed`: the
      nine-name list; update the module docstring (nine fields, absence-preserving attachment
      parameters) (expected to fail at this stage)
- [x] **Code**: edit `goga/pipeline/workflow/workflow_assistant.py` — `gate: bool | None = None`,
      `when: str | None = None`, new trailing `skip: bool | None = None`; rewrite the docstring:
      `gate` (None when not authored — absence vs authored false is the extension-inheritance
      distinction), `when` (None when not authored; legal only where the origin check allows —
      compile owns it), `skip` (the veto carriage — None on every non-skip entry, True on a
      `{skip: true}` entry addressing a pipeline-declared name of that stage)
- [x] **Interface verification**: `pytest tests/pipeline/workflow/test_workflow_assistant_contract.py -x`
      — all pass
- [x] **Logic tests**: rework `tests/pipeline/workflow/test_workflow_assistant_logic.py` —
      `test_workflow_assistant_defaults_are_materialized` becomes the absence test (constructing
      with only `name` yields `gate is None`, `when is None`, `skip is None`); add
      `test_skip_shaped_instance_carries_only_the_veto` (`WorkflowAssistant(name="x", skip=True)`:
      every other field `None`); keep the verbatim-storage and equality tests (add `skip` to the
      constructed values where they enumerate fields)
- [x] **Debugging**: `pytest tests/pipeline/workflow -x` — fix implementation code until all tests
      pass, EXCEPT the parse-suite failures owned by Task 2 (the `when`-required, duplicate-name,
      and materialized-default pins); do NOT fix test code to make a broken implementation pass
- [x] **Contract re-verification**: facade unchanged; the model stays pure data (no validation);
      `goga lint` still 0 errors
- [x] **Lint**: `ruff check goga/ tests/pipeline/workflow/` — fix findings; `ruff format` the
      touched files (`workflow_assistant.py`, both test modules)

### Task 2: `parse_workflow` step 6.7 — skip grammar, optional `when`, namespace-check deletion (goga/pipeline/workflow)

Rewrite the stage-entry grammar of `_build_stage_assistants`: accept the skip form, make `when`
optional (carried as `None` when absent), reject empty entries, keep the catalog five-key set —
and delete `_validate_assistant_namespace` with its call site (the duplicate-name guarantee moves
to compilation, Task 5). The parser decides nothing about origins.

**Contract entity**: `parse_workflow` (location `parse_workflow.py`, steps 6.5/6.7). Facade:
unchanged.

**Usages relevant to this task:**
- `convention`: style R1, tests R2 (mirror layout, parametrized boundary tables, `pytest.raises`
  with the exact texts), gates R3, REPL cycle R4 (probe the branch order live: `{}`, `{skip:
  false}`, `{skip: true, when: start}` each die in their own branch).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm (from the design — verbatim; all errors `WorkflowSyntaxError`):

```
1. IF the stage's assistants value is not a mapping
   → raise "non-mapping assistants in workflow.stages.NAME; author the map
     form keyed by assistant name"
2. IF the map is empty → return None
3. FOR each (name, entry_value) in authored order:
   a. IF entry_value is not a mapping
      → raise "non-mapping assistant attachment in workflow.stages.NAME.name"
   b. IF "skip" in entry_value:
      - IF any other key present
        → raise "skip cannot be combined with extension keys in
          workflow.stages.NAME.assistants.name"
      - IF the value is not strictly bool
        → raise "non-bool value in workflow.stages.NAME.assistants.name.skip"
      - IF the value is False
        → raise "skip: false requires an extension field in
          workflow.stages.NAME.assistants.name"
      - validate the name rules; append WorkflowAssistant(name, skip=True)
      - CONTINUE
   c. IF entry_value is empty
      → raise "empty assistant entry in workflow.stages.NAME.assistants.name"
   d. FOR each key of entry_value (seven-key set):
      - gate  → strictly bool, else "non-bool value in … .gate"
      - when  → validated domain (only when authored — the key is here, so
                authored), else "when must be one of: … in …"
      - prompt/agent → str; skills → list[str]; delegate → bool;
        env → str→str map (empty preserved) — catalog rules verbatim
      - any other key → "unknown key in workflow.stages.NAME.assistants.name:
        KEY; valid keys: prompt, skills, agent, delegate, env, gate, when"
   e. validate the name rules
   f. append WorkflowAssistant(name, <fields>, gate=None-or-bool,
      when=None-or-str)
4. RETURN the map  — and DELETE _validate_assistant_namespace + its call
```

Name rules unchanged (`"invalid assistant name: <name>"`, `"assistant name is reserved"`). Edge
cases: a gate-only entry (`{gate: true}`) parses (reference form, `when=None` — the compile-time
origin check decides); a when-less entry addressing nothing fails at compilation, not here; the
catalog (6.5) keeps its five-key set — `gate`/`when`/`skip` are unknown keys there. Overlay
safety (verified by the design): `_override_entry` composes `None` gate/when safely — the model
accepts them.

- [x] **Contract tests**: extend `tests/pipeline/workflow/test_parse_workflow_assistants.py`
      `TestAssistantMapContract` — the stage-attachment grammar tests document the new acceptance:
      a skip entry, a when-less entry, and a gate-only entry all PARSE (expected to fail at this
      stage)
- [x] **Code**: rewrite `_build_stage_assistants` per the algorithm — skip-form discrimination
      BEFORE the empty-entry check and the seven-key loop; `when` validated only when authored;
      `gate`/`when` carried as `None` when absent; drop the parse-time `when`-required check
      (lines 1669-1672) and the `set(entry_value) <= {"gate", "when"}` reference discrimination
      (line 1687 — a when-less `{gate: true}` is now just a reference with `when=None`)
- [x] **Code**: delete `_validate_assistant_namespace` (line 1803) and its call site (line 267);
      do not leave the parse-time duplicate-name or when-required checks behind as dead code —
      their assertions move to the compiler tests (Task 5)
- [x] **Code**: update the routine docstring's Raises vocabulary to the new grammar (skip-form
      texts, optional `when`, empty entry, the seven-key unknown-key message)
- [x] **Interface verification**: `pytest tests/pipeline/workflow/test_parse_workflow_assistants.py -x`
      — the contract class passes
- [x] **Logic tests** (mock-free, plain strings, per R2) — the design's scenarios plus the rework:
      - `test_parse_time_skip_grammar_errors` (parametrized, four cases): `{skip: true, when:
        start}` → `"skip cannot be combined with extension keys in …"`; `{skip: false}` →
        `"skip: false requires an extension field in …"`; `{}` → `"empty assistant entry in …"`;
        `{skip: "yes"}` → `"non-bool value in … .skip"` (exact texts)
      - skip-form carriage: `{skip: true}` → `WorkflowAssistant(name, skip=True)`, every other
        field `None`
      - when-less acceptance: `{gate: true}` and `{prompt: "X"}` entries parse with
        `when is None`, `gate` as authored or `None`
      - unknown key on a stage entry now lists seven valid keys (rework the existing rows that
        pin the seven-key set — the message gains nothing; confirm `gate`/`when` accepted, and
        `skip` combined-checks fire first)
      - catalog isolation: `gate`/`when`/`skip` remain unknown keys in the CATALOG (6.5) — keep
        the existing catalog rejection rows green
      - rework the moved pins: `test_parse_attachment_missing_when`, the `when is required`
        parametrized rows (lines 613-621), `test_parse_duplicate_assistant_name_across_surfaces`,
        `test_parse_workflow_override_style_inline_counts_for_duplicate_name`, and the duplicate
        row (line 644) are DELETED here — their scenarios land in the compiler suite as
        `test_when_missing_on_workflow_reference_raises_at_compile` and
        `test_namespace_collision_names_both_sites` (Task 5); note the deletion in the module
        docstring's coverage summary
      - rework the materialized-default assertions to the absence expectations: the catalog
        entry's `gate is False` / `when == "checkpoints"` (lines 115-116), the un-authored
        `attachment.gate is False` (line 121), and the when-only reference's `entry.gate is False`
        (line 519, docstring included) become `gate is None` / `when is None` per the
        absence-preserving model (the authored-`when` rows such as line 498 stay green)
- [x] **Debugging**: `pytest tests/pipeline/workflow -x` — fix implementation code until all tests
      pass (the overlay suite `tests/pipeline/hooks` may also depend on the model — run it; its
      failures owned by this task's model change are fixed here, its Task 6 additions are not)
- [x] **Contract re-verification**: the parser performs NO origin classification and NO
      cross-surface uniqueness check (grep for the deleted helper); absence preserved on every
      attachment parameter; facade unchanged; `goga lint` still 0 errors
- [x] **Lint**: `ruff check goga/ tests/pipeline/workflow/ tests/pipeline/hooks/` — fix findings;
      `ruff format` the touched files

### Task 3: `PipelineAssistant` and the typed `assistants` step fields (goga/pipeline/compiler)

Create the new data model, thread the typed field through both step models, and export the entity
from the compiler facade. Pure structure — the extraction logic is Task 4, the consumption is
Task 5.

**Contract entities**: `PipelineAssistant` (location `pipeline_assistant.py` — NEW),
`PhaseStep` (`phase_step.py`), `StageStep` (`stage_step.py`). Facade: `PipelineAssistant` joins
`goga.pipeline.compiler.__all__` (alphabetical slot between `"PhasesBody"` and
`"PipelineDocument"`).

**Usages relevant to this task:**
- `convention`: dataclass discipline (R1 — `kw_only=True` keeps the required `when` legal after
  defaulted parameters), relative imports (`.pipeline_assistant`), test rules R2, gates R3, REPL
  cycle R4 (probe `PipelineAssistant(name="x", when="start")` and the `TypeError` shapes).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Model specification (from the design — verbatim): fields `name, prompt=None, skills=None,
when=<required>, gate=False`; `@dataclass(kw_only=True)`. Errors: none. Edge cases:
`skills: []` is a value (a declaration resolving content); `gate` materializes `False` when not
authored; no default `when` exists. Constraints: no name/type validation here (`parse_dsl` owns
it); no delivery fields — `agent`, `env`, `delegate` are workflow-file territory.

The step fields: trailing `assistants: dict[str, PipelineAssistant] | None = None` on both
models; the `body` docstring line gains "and the extracted assistants key" (the verbatim body
excludes it).

- [ ] **Contract tests**: extend `tests/pipeline/compiler/test_data_models.py`
      `TestDataModelsContract` — `PipelineAssistant`: facade identity + `__all__` membership,
      `is_kw_only_dataclass`, signature exactly `[name, prompt, skills, when, gate]` with
      defaults `[empty, None, None, empty, False]` and annotations `[str, str | None,
      list[str] | None, str, bool]`; `PhaseStep`/`StageStep`: the parameter lists gain trailing
      `assistants` defaulting `None` with annotation `dict[str, PipelineAssistant] | None`;
      update the module docstring's coverage line (expected to fail at this stage)
- [ ] **Code**: create `goga/pipeline/compiler/pipeline_assistant.py` — one-line module docstring
      ("The ``PipelineAssistant`` dataclass — one pipeline-file stage-declared helper."),
      `from __future__ import annotations`, `@dataclass(kw_only=True)` class with Google-style
      docstring (Args per field: name/prompt/skills/when/gate semantics from the contract)
- [ ] **Code**: add the trailing `assistants` field to `PhaseStep` (`phase_step.py`) and
      `StageStep` (`stage_step.py`) with docstring lines ("The step's pipeline assistant
      declarations keyed by assistant name, in authored order — None when the source body carries
      no assistants key or an empty map"); both models import `PipelineAssistant` for the
      annotation (TYPE_CHECKING or runtime per the file's existing style — the modules currently
      import nothing beyond `dataclasses`/`typing`; a `TYPE_CHECKING` import keeps them
      import-cheap, matching `from __future__ import annotations`)
- [ ] **Code**: export from the facade — in `goga/pipeline/compiler/__init__.py` add
      `from .pipeline_assistant import PipelineAssistant` (alphabetical position after
      `from .phases_body import PhasesBody`, before `from .pipeline_document import
      PipelineDocument`) and `"PipelineAssistant"` in `__all__` in the same slot
- [ ] **Interface verification**: `pytest tests/pipeline/compiler/test_data_models.py -x` — all
      pass
- [ ] **Logic tests**: extend `TestDataModelsLogic` — `PipelineAssistant(name="x", when="start")`
      carries `gate=False` and `None` prompt/skills; `skills=[]` round-trips as a value;
      constructing without `when` raises `TypeError`; positional construction raises `TypeError`
- [ ] **Debugging**: `pytest tests/pipeline/compiler/test_data_models.py -x` — fix implementation
      code until all tests pass
- [ ] **Contract re-verification**: facade import works
      (`python -c "from goga.pipeline.compiler import PipelineAssistant"`); the model validates
      nothing; `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/compiler/` — fix findings; `ruff format` the
      touched files (`pipeline_assistant.py`, `phase_step.py`, `stage_step.py`, `__init__.py`,
      `test_data_models.py`)

### Task 4: `parse_dsl` step 4a — the stage-body assistants extraction (goga/pipeline/compiler)

Extract and validate each step item's `assistants` map into the typed field: vocabulary checks
(four keys only — the delivery keys are rejected with the contractual clause), name rules, the
content rule, deep-copy discipline, and the verbatim-body exclusion.

**Contract entity**: `parse_dsl` (location `parse_dsl.py`, step 4a). Facade: unchanged.

**Usages relevant to this task:**
- `parse-dsl` (own cell's practice, final): the parsed-model documentation this step extends —
  the stage-body `assistants` map section updated at materialization; match it, do not touch it.
- `convention`: style R1, tests R2 (parametrized rejections table, exact texts), gates R3, REPL
  cycle R4 (probe the branch order live: an empty entry dies as "when is required", never as an
  unknown key).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm (from the design — verbatim; all errors `StructuralError`, texts above; D2 parse-time
form `stage <name>`):

```
1. FOR each parsed step item (both formats):
   a. raw = item.get("assistants")
   b. IF the key is absent → assistants = None; GOTO f
   c. IF raw is not a mapping
      → raise "non-mapping assistants in stage NAME; author the map form
        keyed by assistant name"
   d. IF raw is empty → assistants = None; GOTO f
   e. FOR each (name, entry) in authored order:
      - IF entry is not a mapping
        → raise "non-mapping assistant declaration in stage NAME.assistants.name"
      - IF "when" not in entry
        → raise "when is required in stage NAME.assistants.name"
      - FOR each key (prompt, skills, when, gate):
          prompt → strictly str; skills → list[str];
          when → one of the four values; gate → strictly bool
        any other key → raise "unknown key in stage NAME.assistants.name:
          KEY; valid keys: prompt, skills, when, gate; agent, env, delegate
          are workflow-file territory"
      - name rules → "invalid assistant name in stage NAME.assistants.name:
        name" / "assistant name is reserved"
      - IF prompt is None and skills is None
        → raise "assistant declaration name in stage NAME resolves neither
          prompt nor skills"
      - build PipelineAssistant(name, prompt, skills, when,
        gate=authored-or-False)
   f. assistants = deepcopy(the built map)
   g. body = _deep_copy_without(item, reserved ∪ {"assistants"})
2. RETURN the step carrying (name, title, [depends_on,] body, assistants)
```

Type-check error texts: `"non-str value in stage <s>.assistants.<a>.prompt"`,
`"non-list-of-str skills in stage <s>.assistants.<a>"`, `"when must be one of: start,
checkpoints, finish, message in stage <s>.assistants.<a>"`, `"non-bool value in
stage <s>.assistants.<a>.gate"`. Edge cases: an empty map equals absence; `when` presence is
checked before the key loop (an empty entry dies as "when is required"); the reserved name keeps
the cross-surface message; the delivery-key clause in the unknown-key message is contractual.

- [ ] **Contract tests**: extend `tests/pipeline/compiler/test_parse_dsl.py` — a contract-class
      test that both body formats produce steps whose `assistants` field exists with the declared
      annotation and default (expected to fail at this stage)
- [ ] **Code**: implement `_extract_step_assistants(stage, item)` in `parse_dsl.py` per the
      algorithm; call it from `_extract_phase_step` and `_extract_stage_step`; add `"assistants"`
      to `_PHASE_STEP_KEYS` and `_STAGE_STEP_KEYS` (the verbatim body excludes the key); construct
      the steps with the extracted field
- [ ] **Interface verification**: `pytest tests/pipeline/compiler/test_parse_dsl.py -x` — all pass
- [ ] **Logic tests** (mock-free, plain strings) — the design's scenarios:
      - `test_stage_body_assistant_parses_into_typed_field` (both formats): the typed field
        carries the declaration with every value; the verbatim body excludes the key
        (`"assistants" not in step.body`); the map is deep-copied (mutating the step's map cannot
        reach the caller's parsed structure — probe with a sentinel mutation)
      - `test_delivery_key_in_stage_declaration_rejected` — `agent: codex` in a declaration →
        `StructuralError` matching the exact unknown-key text with the delivery-keys clause
      - `test_content_free_stage_declaration_rejected` — `{when: start}` alone → `"assistant
        declaration auditor in stage build resolves neither prompt nor skills"`
      - `test_pipeline_declaration_vocabulary_rejections` (parametrized, seven cases; exact
        texts): non-bool `gate: "yes"`; invalid `when: daily`; unknown key `env`; invalid name
        `bad name!`; reserved name `assistant`; non-mapping entry `auditor: "not a map"`;
        non-mapping map `assistants:` as a list
      - `test_pipeline_declaration_when_missing_rejected` (two cases): `{prompt: "X"}` and `{}`
        both die `"when is required in stage build.assistants.auditor"`
      - `test_empty_stage_assistants_map_equals_absence` (parse half): `assistants: {}` →
        `step.assistants is None`
- [ ] **Debugging**: `pytest tests/pipeline/compiler/test_parse_dsl.py -x` — fix implementation
      code until all tests pass
- [ ] **Contract re-verification**: delivery keys never enter the model; `_deep_copy_without`
      still deep-copies bodies (declarations deep-copied separately — later working-body mutation
      cannot reach `PipelineDocument`); facade unchanged; `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/compiler/` — fix findings; `ruff format` the
      touched files

### Task 5: `compile_flow` step 4.10 — two-surface assembly, veto/extension, team emission (goga/pipeline/compiler)

Rewrite the collaboration emission into the single place both documents meet: the two-surface
namespace (workflow catalog ∪ inline ∪ pipeline declarations) with authored-site collision
errors, the per-stage assembly (pipeline declarations first — veto or extension merge; workflow
entries second — origin-aware `when` check, reference/inline resolution), the team emission from
the catalog plus the attached pipeline declarations, the loop-copy carriage, and the workflow-less
attachment path. With no step carrying `assistants` and no workflow collaboration, every new
branch is data-empty — the output stays byte-identical (SC5).

**Contract entity**: `compile_flow` (location `compile_flow.py`, step 4.10 + the workflow-less
branch + `_make_expanded_copy`). Facade: unchanged.

**Usages relevant to this task:**
- `afm`: the engine attachment contract — `FlowAssistant` carries NO `skills` key; mode/trigger
  vocabularies via the unchanged `_GATE_MODE`/`_WHEN_TRIGGER`/`_attachment_trigger` (`pre_completion`
  is gated-finish-only); every trigger written explicitly.
- `assistants` (imported, from `goga/pipeline/workflow`): the governance forms (skip veto,
  extension) this assembly resolves; the visibility rule (a pipeline declaration is invisible to
  other stages).
- `parse-workflow` (imported): the parsed model's guarantees — absence-preserving fields, skip
  carriage, no origin classification in the parser.
- `compile-flow` (own cell's practice, final) and `beautiful_yaml`: the emission rides the
  existing structures — `serialize_flow` and its dump parameters are untouched; no new
  serialization sites (byte-exactness is the constraint, proven by SC5).
- `convention`: style R1 (blank-line block separation in the new helpers), tests R2, gates R3,
  REPL cycle R4 (probe live: the collision message shape `(<site1>, <site2>)`;
  `join_prompt("Base", "")` — the authored empty string participates; the extension
  gate/when selection on all three states).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Algorithm (from the design — verbatim; `_collaboration_emission(workflow, effective, expanded,
expanded_ids)` and helpers):

```
A. Build the workflow namespace (reference resolution AND the content check):
   ns = {}
   FOR (name, entry) of workflow.assistants            → site
   "workflow.assistants.name"
       IF name in ns → collision error (both sites)
       ns[name] = (entry, site)
   FOR each stage, each entry of stage.assistants
       IF declaration(entry):
           site = "workflow.stages.S.assistants.name"
           IF name in ns → collision error (both sites)
           ns[name] = (entry, site)
B. Build the pipeline declaration index (base stage → map) walking
   expanded_ids in working-body order (loop copies collapse: every copy of
   one base shares the map):
   FOR (base, produced_ids) of expanded_ids:
       decls = <the base's step>.assistants or {}
       IF decls: pipeline_decls[base] = decls
       FOR (name) of decls:
           site = "pipeline.base.assistants.name"
           IF name in ns or name in pipeline_name_sites
             → collision error (both sites)
           pipeline_name_sites[name] = site
C. Content check — every ns member resolves prompt or skills
   (existing message; pipeline declarations are NOT ns members)
D. Per-stage assembly — _assemble_stage_attachments(base, produced_ids):
   wf_entries = effective[base].assistants or {}   ({} without a workflow)
   decls      = pipeline_decls.get(base) or {}
   bodies     = {produced_id → working body}
   assembled  = []; attached_pipeline = []
   1. FOR (name, decl) of decls in authored order:        # pipeline first
      entry = wf_entries.get(name)
      IF entry is not None and entry.skip is True:
          CONTINUE                                        # the veto
      eff_when  = entry.when  if entry and entry.when  is not None else decl.when
      eff_gate  = entry.gate  if entry and entry.gate  is not None else decl.gate
      eff_prompt= join_prompt(decl.prompt, entry.prompt if entry else None)
                  # both authored → "pipeline-text\n\nworkflow-text";
                  # single-sided → that text alone; neither → None
      eff_skills= expand_skills(decl.skills, entry.skills if entry else None)
                  # declaration entries first, then entry entries,
                  # deduplicated by value preserving first occurrence
      FOR pid of produced_ids:
          _reject_attachment_body("pipeline.base", name, bodies[pid])
          # "assistant is forbidden on a script stage in pipeline.base: name"
          # "assistant is forbidden on a planning-only stage in pipeline.base: name"
      assembled.append(FlowAssistant(
          profile="goga-"+name, title=name,
          instruction=eff_prompt or "", mode=_GATE_MODE[eff_gate],
          trigger=_attachment_trigger(eff_gate, eff_when)))
      attached_pipeline.append((name, eff_prompt, eff_skills))
   2. FOR (name, entry) of wf_entries in authored order:  # workflow second
      IF name in decls: CONTINUE                          # consumed above
      IF entry.skip is True
        → raise "skip targets a pipeline-declared assistant in
          workflow.stages.base.assistants.name"
      source = entry if declaration(entry) else ns.get(name)
      IF source is None
        → raise "unknown assistant reference in workflow.stages.base: name"
          # a name pipeline-declared by ANOTHER stage lands here: ns excludes
          # pipeline declarations — the visibility rule
      IF entry.when is None
        → raise "when is required in workflow.stages.base.assistants.name"
          # the origin-aware check: legal only as an extension (consumed in 1)
      IF name in seen → duplicate guard (programmatic defense)
      FOR pid of produced_ids:
          _reject_attachment_body("workflow.stages.base", name, bodies[pid])
          # messages byte-identical to today
      gate = entry.gate if entry.gate is not None else False   # materialize
      IF source.skills is not None and name not in catalog and not warned:
          warn once: inline declaration skills have no engine channel
      assembled.append(FlowAssistant(profile="goga-"+name, title=name,
          instruction=source.prompt or "", mode=_GATE_MODE[gate],
          trigger=_attachment_trigger(gate, entry.when)))
   3. IF assembled: for pid of produced_ids → assistants_by_id[pid] = assembled
E. Team emission — catalog members in authored order (existing
   _team_members), then one member per attached_pipeline record in collection
   order (pipeline body stage order; authored order within a stage):
   FlowTeamMember(id=title=name, profile="goga-"+name,
                  instruction=eff_prompt or "", skills=eff_skills or [])
   # vetoed and stage-skipped records never collected; a name joins exactly
   # once (the namespace uniqueness guarantees it)
F. Block — FlowCollaboration(mode="assistants",
   max_depth=workflow.delegation.depth or None)  (every compilation)
```

`join_prompt` joins by PRESENCE, not truthiness: an authored empty pipeline `prompt: ""`
participates in the join (the plain two-segment text results, leading blank line included); empty
texts are NOT dropped here — unlike the overlay's prompt merge — so `None` stays the only
non-joining side. Errors: the collision `duplicate assistant name: <name> (<site1>, <site2>)`;
skip-target; unknown-reference (existing text); when-required (existing text, new location);
script/planning rejections (parameterized site, D2); the duplicate-in-one-stage defense
(existing); the content check (existing). Additional structural changes: `_make_expanded_copy`
deep-copies `assistants` (deep copies of the declarations, never aliases); `_embed_extend_stages_*`
construct steps without assistants (the default); the workflow-less branch becomes
`reconstructed = list(body.steps)`; `identity_ids = {step.name: [step.name] for step in
reconstructed}`; `_collaboration_emission(None, {}, reconstructed, identity_ids)`.

Edge cases (from the design — verbatim): workflow-less compile → empty ns, empty wf_entries, no
content check; steps' declarations still assemble (SC1). A vetoed declaration produces no
attachment, no team member, no profile — the stage still runs (SC2). Loop-expanded copies share
one assembled list; the team counts each base once (first occurrence) (SC3). Extend-embedded
steps carry `assistants=None`; a raw `assistants` key in an extend body still dies in
`_reject_authoring_output_keys` (defensive re-check, unchanged message). `gate: false` authored
on an extension downgrades a gated declaration (absence inherits).

- [ ] **Contract tests**: extend `tests/pipeline/compiler/test_compile_flow_collaboration.py`
      `TestCompileFlowCollaborationContract` — rework
      `test_authored_assistants_key_in_stage_body_rejected`: after the parse-time extraction its
      current fixture (a list-form `assistants:` in a pipeline stage body) dies at PARSE with
      `"non-mapping assistants in stage build; author the map form keyed by assistant name"`
      (covered by Task 4's parametrized table); move the pinned compile-side prohibition test
      onto an embedded extend body (or a programmatic body) — the pinned text `"assistants key is
      forbidden in stage body; use assistants in workflow.stages"` stays byte-identical
      (expected to fail at this stage)
- [ ] **Code**: rewrite `_collaboration_emission` per algorithm A–F (the `workflow is None`
      early return is REPLACED by the empty-ns/empty-entries path over `identity_ids`); implement
      `_assemble_stage_attachments`, `join_prompt`, `expand_skills`, the pipeline declaration
      index, and the collision-error helper (both-sites text); parameterize `_reject_attachment_body`
      with the site prefix (`pipeline.<base>` / `workflow.stages.<base>`)
- [ ] **Code**: `_make_expanded_copy` deep-copies `assistants` onto every copy; the
      extend-embedding constructors leave `assistants` at the default `None`; the workflow-less
      branch builds `identity_ids` and passes `reconstructed` into the emission (delete the
      `_collaboration_emission(None, {}, [], {})` call)
- [ ] **Code**: update the docstrings of the routine and the touched helpers (the two-surface
      model, the ordering laws, the D2 sites) per R1
- [ ] **Interface verification**: `pytest tests/pipeline/compiler/test_compile_flow_collaboration.py -x`
      — the contract class passes
- [ ] **Logic tests** (extend the suite; reuse the `_compile` helper; mock-free) — the design's
      scenarios:
      - `test_phases_format_stage_assistants_compile_without_workflow` (SC1 compile half): the
        compiled flow carries the stage entry `{profile: goga-watcher, title: watcher,
        instruction: "Watch.", mode: advisory, trigger: checkpoints}`; the team is
        `[{id: watcher, title: watcher, profile: goga-watcher, instruction: "Watch.", skills:
        [lint]}]`; no workflow was needed
      - `test_sc2_skip_veto_removes_attachment_team_and_profile` (compile half): the vetoed stage
        still compiles (present in stages) with no `assistants` key, no team member
      - `test_sc3_extension_merge_and_ordering` (SC3): exact expected values —
        `instruction == "Base audit.\n\nAlso the lockfile."` (exactly one blank line);
        `skills == ["audit", "deps", "lock"]`; `mode == "advisory"` (downgraded), `trigger ==
        "checkpoints"`; the stage's list orders `sec` before `reviewer`; the team list is
        `[reviewer, sec, noter]`; both `review-1`/`review-2` carry the same `noter` entry
      - `test_when_missing_on_workflow_reference_raises_at_compile` — `StructuralError("when is
        required in workflow.stages.build.assistants.reviewer")`, the exact former parse-time
        text now from the compiler
      - `test_skip_targeting_non_pipeline_name_rejected` — `"skip targets a pipeline-declared
        assistant in workflow.stages.build.assistants.reviewer"`
      - `test_cross_stage_pipeline_reference_is_unknown` — `"unknown assistant reference in
        workflow.stages.review: watcher"`
      - `test_namespace_collision_names_both_sites` — `"duplicate assistant name: auditor
        (workflow.assistants.auditor, pipeline.build.assistants.auditor)"`; the inline-vs-catalog
        and pipeline-vs-pipeline variants raise the same shape with their site pairs
      - `test_pipeline_declaration_on_script_stage_rejected` — `"assistant is forbidden on a
        script stage in pipeline.build: auditor"` on a workflow-less compile; the planning-only
        variant analogously
      - `test_stage_level_skip_removes_declarations_too` — workflow `stages.build.skip: true` over
        a pipeline declaration: `build` absent from the compiled stages; no team member; no error
      - `test_extension_absence_inheritance_and_explicit_false` — (a) `{prompt: "X"}` inherits
        `when: finish`, `gate: true` → `mode: required, trigger: pre_completion`; (b) `{gate:
        false}` alone → `mode: advisory, trigger: on_completion` (an ungated finish keeps the
        `on_completion` row; `pre_completion` is gated-only)
      - `test_single_sided_prompt_and_skills_stand_alone` — declaration without prompt +
        extension with prompt only → `instruction == "<extension text>"` (no leading separator);
        skills = the declaration's list
      - `test_team_loop_collapse_and_authored_empty_skills` — a loop: 2 stage declaring `noter`
        with `skills: []`: one team member; `skills: []` in the member; both copies attach
      - `test_empty_stage_assistants_map_equals_absence` (compile half) — no stage `assistants`
        key, no team entries
      - `test_sc6_existing_workflow_only_behavior_unchanged` — the existing catalog/reference/
        inline scenarios (full materialization, reference field split, inline warning, delegation
        depth, override-style content check) hold unchanged, WARNING text and once-per-name
        behavior included (run the existing suite unedited)
      - `test_sc5_byte_identical_compile_without_assistants` — an assistant-free pipeline + a
        collaboration-free workflow compiles byte-identically to the recorded golden (frozen
        literal per the `test_serialize_flow_collaboration.py` pattern; collaboration mode key
        excepted as today)
- [ ] **Debugging**: `pytest tests/pipeline/compiler -x` — fix implementation code until all tests
      pass
- [ ] **Contract re-verification**: `PipelineDocument(header, fmt, body)` still built from the
      ORIGINAL body; working-body copies never alias it; `serialize_flow`/`FlowAssistant`/
      `FlowTeamMember`/`FlowCollaboration` untouched; `_reject_authoring_output_keys`' assistants
      branch byte-identical; the one WARNING site unchanged (wording and trigger, now excluding
      pipeline declarations); `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/compiler/` — fix findings; `ruff format` the
      touched files

### Task 6: Overlay documentation — the form-blind append stated (goga/pipeline/hooks)

State the contracted overlay behavior in the code and pin it with characterization tests: a skip
entry and a when-less extension entry append like every other entry (never dropped by the
namespace rule); a declaration-shaped contribution colliding with the workflow-side namespace
drops silently; the overlay never resolves a name beyond the workflow document. **No functional
edit** — resist any change to the merge logic.

**Contract entity**: `merge_workflow_overlay` (location `overlay.py`). Facade: unchanged.

**Usages relevant to this task:**
- `checkpoints` (own cell's practice, final): the form-blind append documentation the docstrings
  now mirror.
- `convention`: docstring style R1 (the docstring rewrite IS the change), tests R2, gates R3,
  REPL cycle R4 (probe the discriminator live: `_is_assistant_declaration(WorkflowAssistant(
  name="x", skip=True))` → `False`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Documentation change (from the design — verbatim): update the module docstring, the
`_merge_stage_assistants` docstring, and the `_is_assistant_declaration` docstring to state: a
skip entry and a gate/when-only entry append like every other entry (never dropped by the
namespace rule); an entry shaped as a declaration (any key beyond gate/when/skip — i.e. any of
the five declaration fields present) whose name is in the merged workflow-side namespace is
dropped; the overlay never resolves a name beyond the workflow document. Errors: none new. Edge
cases: a tool-contributed extension entry addressing a pipeline-declared name appends (the
pipeline namespace is invisible here); its collision with a workflow declaration of the same name
surfaces at compilation.

- [ ] **Tests (characterization — they pin CURRENT behavior and must pass BEFORE and AFTER the
      docstring edit)**: extend `tests/pipeline/hooks/test_overlay_assistants.py` —
      `test_overlay_appends_skip_and_extension_forms_form_blind`: a base workflow stage with an
      authored entry; a contribution carrying on the same stage a `{skip: true}` entry (new name)
      and on another stage a when-less `{agent: codex}` entry addressing a pipeline name; a
      contribution declaration colliding with an authored catalog name. Assert: the skip entry
      and the when-less extension append verbatim; the colliding declaration drops silently; no
      error, no resolution
- [ ] **Code**: update the three docstrings per the documentation change (no logic edit)
- [ ] **Run validation**: `pytest tests/pipeline/hooks -x` — all pass (the new test included,
      before and after the docstring edit)
- [ ] **Contract re-verification**: `git diff` over `overlay.py` shows docstring/comment lines
      only; `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/hooks/` — fix findings; `ruff format` the touched
      files

### Task 7: `write_afm_config` — the three-artifact delivery (goga/pipeline)

Widen the delivery to the fourth artifact: the `pipeline` parameter, the fixed profiles gate
(`flow` + (`workflow` or `pipeline`) — the D1 defect fix), and the pipeline declaration branch of
`_resolve_profiles` (workflow namespace first, else the pipeline declaration index; delivery
fields from the workflow extension entry; site `pipeline.<stage>`).

**Contract entity**: `write_afm_config` (location `afm_config.py`). Facade:
`goga.pipeline` (already exports it — unchanged).

**Usages relevant to this task:**
- `afm`: the profile shape (`{title, command, delegate}` — nothing else), the strict pre-run
  error discipline (every resolution error before any file is written), the limits contract.
- `collaboration-emission` (imported, from `goga/pipeline/compiler`): the compiled surface the
  profile ids are read from (`_referenced_names` — team members then stage attachments,
  ordered-unique; the flow stays the single source of truth).
- `assistants` (imported): the delivery expectations of the extension entries.
- `convention`: style R1 (relative import — `PipelineDocument` joins the runtime
  `from .compiler import` line), tests R2 (monkeypatched closure/env foundations per the existing
  pattern), gates R3, REPL cycle R4 (probe the gate expression on all four artifact combinations;
  probe the extension lookup on a skipped declaring stage).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Delivery algorithm (from the design — verbatim):

```
1. wrapper = resolve_wrapper_path(agent) if agent is not None else None
2. base content: client (when wrapper), five static fields, observer hook
3. IF flow is not None and (workflow is not None or pipeline is not None):
      collaboration = _collaboration_section(agent, flow, workflow, pipeline)
   ELSE: the bare static head; profile_command_names = {}
4. _resolve_profiles:
   ns = workflow namespace (catalog + inline declarations; delivery sources)
   pd = {name → declaring stage} built from pipeline.body.steps
        (each step's assistants field keys; the step name is the site)
   FOR name of _referenced_names(flow):
     IF name in ns: (declaration, site) = ns[name]
     ELIF name in pd:
         stage = pd[name]
         ext = workflow.stages[stage].assistants.get(name) if workflow else None
         delivery = (ext.agent, ext.delegate, ext.env)  # Nones when absent
         site = "pipeline." + stage
     ELSE: raise (defensive) "unknown assistant reference in the compiled
           flow: name"
     validate the env keys of a non-empty effective env map (existing error)
     target_agent = delivery.agent else agent
     IF target_agent is None
       → raise "assistant name at site resolved no agent: set its agent or a
         global agent"
     delegate = delivery.delegate if not None else False
5. profiles["goga-"+name] = {title, command, delegate}; env → owner-only sh
   closure path as the command; command_names labels
6. limits.max_tasks only when workflow carries a delegation block
7. write the whole file; return the fixed path
```

Verified checkpoints (from the design): a pipeline-declared name has at most one workflow entry
addressing it (its own stage's — cross-stage entries die at compile), so the extension lookup is
unambiguous; a vetoed declaration never appears in the flow → never referenced → no profile (no
dead profiles); a name pipeline-declared on a stage the flow no longer carries (skipped) is not
flow-referenced, never resolved; an explicitly cleared env (`{}`) is no env (no closure).
`_collaboration_section` gains the `pipeline` parameter (threaded into `_resolve_profiles`);
`limits` still keys on the workflow delegation block alone.

- [ ] **Contract tests**: rework
      `tests/pipeline/test_afm_config.py::TestWriteAfmConfigContract::test_write_afm_config_signature_matches_contract`
      (line 55) — the pinned parameter list `["agent", "flow", "workflow"]` gains the trailing
      `pipeline` (default `None`, annotation `PipelineDocument | None`) in the same change set as
      the code; extend `tests/pipeline/test_afm_config_collaboration.py`
      `TestWriteAfmConfigCollaborationContract` — the signature gains the trailing `pipeline`
      parameter defaulting `None` (`inspect.signature` parameter list); REWORK
      `test_collaboration_profiles_require_both_flow_and_workflow` into the D1 shape: profiles
      require `flow` plus at least one of `workflow`/`pipeline` (`write_afm_config("claude",
      flow=flow)` → bare head; `write_afm_config("claude", workflow=workflow)` → bare head;
      `write_afm_config("claude", flow=flow, workflow=workflow)` → profiles; NEW:
      `write_afm_config("claude", flow=flow, pipeline=pipeline)` → profiles)
      (expected to fail at this stage)
- [ ] **Code**: add the `pipeline: PipelineDocument | None = None` parameter (last) to
      `write_afm_config`; import `PipelineDocument` from `.compiler` (joins the existing runtime
      import line); replace the gate with `flow is not None and (workflow is not None or
      pipeline is not None)`; thread `pipeline` into `_collaboration_section` and
      `_resolve_profiles`; implement `_pipeline_declaring_stages(pipeline)` and the pipeline
      branch per the algorithm
- [ ] **Code**: update the docstrings (the `pipeline` arg line per the contract annotation —
      "None when no pipeline document is at hand — the section head still writes and no
      pipeline-declared profile resolves"; the gating sentence — "the profiles join it when `flow`
      is given with `workflow` or `pipeline`; the task budget joins it only when `workflow` is
      given")
- [ ] **Interface verification**: `pytest tests/pipeline/test_afm_config_collaboration.py -x` —
      the contract class passes
- [ ] **Logic tests** (monkeypatch the closure/env foundations per the existing pattern) — the
      design's scenarios:
      - `test_sc1_profile_generated_without_workflow` — the SC1 flow + `write_afm_config("claude",
        flow=doc, workflow=None, pipeline=pipeline_doc)`: the written config carries
        `collaboration.profiles.goga-watcher` with the global-agent wrapper command; `limits`
        absent
      - the SC2 delivery half — the vetoed SC2 flow (`watcher` skip-vetoed by the workflow)
        delivers NO `goga-watcher` profile (`_referenced_names` is empty → `profiles == {}`); no
        dead profiles remain
      - `test_extension_delivery_fields_reach_the_profile` (SC3 delivery) — `sec` resolves via
        the pipeline branch → `ext = build.assistants["sec"]` → `profiles["goga-sec"].command`
        is the codex wrapper; `reviewer`'s profile unchanged from the current behavior
      - `test_write_afm_config_bare_head_without_artifacts` — `write_afm_config("claude")` and
        `write_afm_config("claude", flow=doc)` (no workflow, no pipeline): the collaboration
        section carries only `runtime_context` and `hide_attach_helpers`; no profiles (the fixed
        gating's negative half, D1)
      - the no-agent pipeline branch — a pipeline-declared name with no workflow and
        `agent=None` → `ValueError` matching `r"assistant watcher at pipeline\.review resolved no
        agent: set its agent or a global agent"` (the D2 site)
- [ ] **Debugging**: `pytest tests/pipeline -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: the `{title, command, delegate}` profile shape unchanged;
      every resolution error fires before any file is written; the defensive unknown-reference
      text unchanged; `goga lint` still 0 errors
- [ ] **Lint**: `ruff check goga/ tests/pipeline/` — fix findings; `ruff format` the touched files

### Task 8: `run_pipeline` step 17 — threading and the end-to-end delivery (goga/pipeline)

Thread the parsed pipeline document into the configuration write and prove the delivery
end-to-end. One argument at one call site; the run-level test is the cross-cell integration
scenario of this change (pipeline-file declaration → parse → compile → delivery → engine config).

**Contract entity**: `run_pipeline` (location `run_pipeline.py`, step 17). Facade: unchanged
signature.

**Usages relevant to this task:**
- `run-pipeline` (own cell's practice, final): the step-17 threading documentation the wiring
  matches.
- `convention`: tests R2 (call the handler directly; reuse the `test_run_pipeline_workflow.py`
  scaffolding; `tmp_path`-pinned project trees; stub the launch), gates R3, REPL cycle R4.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

Wiring (from the design — verbatim): replace the call with
`write_afm_config(effective_agent, flow_doc, overlay.workflow, pipeline_doc)` — `pipeline_doc` is
the `compile_flow` return already in scope at step 13 (`run_pipeline.py:477`). No other step
changes.

- [ ] **Contract tests**: the `run_pipeline` signature is UNCHANGED — but the step-17 call shape
      IS source-pinned: rework `tests/pipeline/test_run_pipeline_contract.py::
      test_run_pipeline_source_consumes_the_effective_configuration` (line 453) in the same change
      set — the expected call string becomes `write_afm_config(effective_agent, flow_doc,
      overlay.workflow, pipeline_doc)` and the docstring's "two artifacts" wording becomes the
      four-artifact threading; the other signature/facade assertions of the suite run unedited
      and green
- [ ] **Code**: add the `pipeline_doc` argument at the delivery site
      (`goga/pipeline/run_pipeline.py:532`)
- [ ] **Interface verification**: `pytest tests/pipeline/test_run_pipeline_contract.py
      tests/pipeline/test_run_pipeline_workflow.py -x` — the unchanged surface still passes
- [ ] **Logic tests / integration scenario**: extend `tests/pipeline/test_run_pipeline_workflow.py`
      `TestRunPipelineWorkflowResolution` (per its conventions, with a pipeline-declared
      assistant) — `test_run_pipeline_threads_pipeline_document`: a run-level test whose pipeline
      declares an assistant on a stage; assert the written engine config carries the
      `goga-<name>` profile (the threading through step 17 is exercised end-to-end; stub the
      launch layer per the suite's established pattern)
- [ ] **Debugging**: `pytest tests/pipeline -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: step 17's contract wording holds (all four artifacts passed;
      pre-run collaboration errors still fail the launch cleanly before any events); `goga lint`
      still 0 errors; `goga schema` unchanged map
- [ ] **Lint**: `ruff check goga/ tests/pipeline/` — fix findings; `ruff format` the touched files

---

## Validation Commands

All commands run in the project virtualenv; Python 3.10+ compatibility required.

- `pytest tests/pipeline/workflow -x`: the workflow-cell suites (Tasks 1–2 scope)
- `pytest tests/pipeline/compiler -x`: the compiler-cell suites (Tasks 3–5 scope)
- `pytest tests/pipeline/hooks -x`: the hooks-zone suite (Task 6 scope)
- `pytest tests/pipeline -x`: the delivery and wiring scope (Tasks 7–8 scope; also the
  cross-cell aggregate — no NEW failures against the recorded 6-failure environmental baseline)
- `pytest tests/ -x`: Run all tests (the convention's command; green at every task end and before
  every local commit, modulo the recorded pre-existing environmental failures)
- `ruff check goga/`: Lint check (the convention's lint command — after every coding task and
  before every local commit)
- `ruff check tests/`: Test-code lint (the convention makes ruff the test linter/formatter)
- `ruff format <touched files>`: Formatter per `[tool.ruff.format]` over every file the task
  touched (the repository is fully format-clean — 1070 files — and must remain so)
- `goga lint`: DSL validation over all cells — the contracts are read-only and must stay green
  (93 cells, 0 errors)
- `goga schema`: the dependency map must stay unchanged (workflow ← compiler ← pipeline;
  workflow ← hooks ← pipeline)
- `python -c "from goga.pipeline.compiler import PipelineAssistant"`: Facade accessibility — the
  new entity's facade obligation
- `python -c "from goga.pipeline.workflow import WorkflowAssistant; from goga.pipeline import
  write_afm_config"`: Facade accessibility — the changed entities

---

## Completion Criteria

- [ ] Every changed contract entity is implemented in its declared `location`:
      `workflow_assistant.py`, `parse_workflow.py`, `pipeline_assistant.py` (new),
      `phase_step.py`, `stage_step.py`, `parse_dsl.py`, `compile_flow.py`, `overlay.py`
      (docstrings only), `afm_config.py`, `run_pipeline.py` — and matches the materialized
      signatures exactly (the nine-field absence-preserving model; the five-field
      `PipelineAssistant` with required `when`; the trailing `assistants` step fields; the
      four-parameter `write_afm_config`)
- [ ] `PipelineAssistant` is importable from `goga.pipeline.compiler` and listed in `__all__`;
      every other facade is unchanged
- [ ] The two-surface assembly holds: pipeline declarations attach on BOTH paths (with and
      without a workflow); the veto removes exactly the assistant (SC2); the extension merge
      produces the exact join/dedup/ordering laws (SC3); the team lists catalog members first,
      then attached pipeline declarations, loop copies collapsing (SC3); the namespace is one
      global uniqueness domain with both-sites collision errors; the origin-aware `when` check
      keeps its exact former text; body prohibitions apply with `pipeline.<stage>` sites (D2)
- [ ] The delivery holds: the profiles gate is `flow` + (`workflow` or `pipeline`) (D1 proven
      behaviorally); a pipeline-declared name resolves delivery from its workflow extension entry,
      else the global agent, with the `pipeline.<stage>` site (D2); `run_pipeline` threads
      `pipeline_doc` end-to-end
- [ ] The overlay is functionally untouched (docstrings only) and the form-blind append is pinned
      by a passing characterization test
- [ ] All 26 design test scenarios are implemented (8 positive + 11 negative + 7 edge, parametrized
      tables counted once) and the pinned suites are reworked in the same change sets as the code
      they pin (the model contract/logic suites, the parse assistants suite, the data-models
      suite, the afm-config gating and signature tests, the compile stage-body rejection test,
      the run-pipeline step-17 source pin)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic
      tests → debugging → re-verification → lint)
- [ ] The Mandatory Rules were observed in every task and every commit: R1 style (relative
      imports, `kw_only` discipline, Google docstrings, blank-line block separation), R2 test
      rules (mirror layout, `test_<what>_<scenario>` naming, parametrized boundary tables,
      mock-free pure-logic tests, direct handler calls, `tmp_path` for file I/O), R3 lint/format
      gates (`ruff check goga/ tests/` + `ruff format` on touched files before every local
      commit; no commit behind red tests or lint findings), R4 REPL cycle (live-probed behavior,
      fresh-interpreter re-evaluation, all verified code migrated into source files and tests)
- [ ] No package boundary was expanded; no new cells; no `.usages/` files or rider docs created
      or modified; the final modules (`serialize_flow`, `FlowAssistant`, `FlowTeamMember`,
      `FlowCollaboration`, `_reject_authoring_output_keys`, the overlay merge logic, `cli.py`)
      are untouched
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (`pytest tests/ -x` modulo the recorded pre-existing
      environmental failures, `ruff check goga/` and `tests/`, `goga lint` 93/0, `goga schema`
      unchanged, the facade checks); SC5's golden-file comparison passes byte-exactly
