# Plan: `support-afm-assistants`

<!-- Topic: `support-afm-assistants` — the afm (v2.x) assistants-collaboration
     bridge: assistant authoring in workflow-files (catalog / delegation / stage
     attachments), compilation into the flow-file collaboration block + team
     list + per-stage assistant entries, tool-contribution overlay merging under
     the assistant-namespace invariant, and delivery of generated profiles, env
     closures and delegation limits into the afm engine config.
     Source: `.goga/history/2026/support-afm-assistants/design.md` (design-review
     completed — 4 fixes applied, all "apply"; see its execution summary). This
     plan compiles the design into ralphex-executable tasks. -->

## Purpose

Implement the `support-afm-assistants` feature end-to-end against the already
applied CODEMANIFEST contracts: workflow-files gain three authoring surfaces
(top-level `assistants` catalog, top-level `delegation` block, per-stage
`assistants` attachment lists); the compiler emits the collaboration block
(`mode: assistants` + `max_depth`), the `team` list, and per-stage `assistants`
entries into every compiled flow-file; the overlay merge composes tool
contributions under the document-wide assistant-namespace invariant;
`write_afm_config` generates `collaboration.profiles` (one `goga-<name>` profile
per flow-referenced id, env assistants behind owner-only sh closures) and
`collaboration.limits.max_tasks` (delegation block only); `run_pipeline` threads
the compiled `FlowDocument` and the effective `WorkflowDocument` into the config
write so the flow-file and the engine config can never diverge.

After implementation the project provides:

- `goga/pipeline/workflow` — new models `WorkflowAssistant`
  (`workflow_assistant.py`) and `WorkflowDelegation` (`workflow_delegation.py`);
  `WorkflowStage.assistants` (last field, `list[WorkflowAssistant] | None`);
  `WorkflowDocument.assistants` (default empty dict) and `.delegation` (last
  fields); `parse_workflow` steps 6.5–6.8 (catalog, delegation, attachment
  grammar, extend prohibition) plus the document-wide duplicate-name pass and
  the extended empty-workflow rule; cell facade `__all__` 16 → 18.
- `goga/pipeline/compiler` — new models `FlowCollaboration`
  (`flow_collaboration.py`), `FlowTeamMember` (`flow_team_member.py`),
  `FlowAssistant` (`flow_assistant.py`); `FlowDocument` grows the
  `collaboration` and `team` slots between `memory` and `stages`; `FlowStage`
  carries the canonical `assistants` slot after `memory_use`;
  `compile_flow` steps 4.10 (attachment resolution + four checks) / 5
  (assistants assembly) / 6 (collaboration + team assembly);
  `serialize_flow` emits the new keys; cell facade `__all__` 16 → 19.
- `goga/pipeline/hooks` — `merge_workflow_overlay` steps 4a/4b/5a (catalog
  merge, whole-block delegation, per-stage append-with-dedup under the
  namespace invariant); the buffer-shape guard and empty-contribution
  vocabulary of `PipelineHooks.amend_workflow` gain `assistants`/`delegation`.
- `goga/pipeline` — `write_afm_config(agent, flow=None, workflow=None)` with
  generated profiles, env closures under `/tmp/goga-assistant-env` (0o700), and
  `limits.max_tasks`; `run_pipeline` step 16 threads `flow_doc` +
  `overlay.workflow`; `apply_skip_stages` carries `assistants`/`delegation`
  verbatim; `stage_env_wrappers._KEYS_AFTER_COMMAND` gains `"assistants"`.
  `goga/pipeline/__init__.py` is unchanged (`write_afm_config` is already
  exported; its signature change is internal).

The most important gaps between contract and code: the five new model files do
not exist; `parse_workflow` knows neither `assistants` nor `delegation`
(`_TOP_LEVEL_KEYS` / `_STAGE_KEYS` are the old 6/11-key tuples, the empty rule
counts five blocks); the compiler has no namespace/emission logic and
`_effective_overrides` drops attachments on extend-seeded stages (the C2.4
defect this design guards); the serializer emits neither `collaboration` nor
`team`; the overlay merge has no assistants arm; `write_afm_config` takes only
`agent` and writes no `collaboration` section; `run_pipeline` calls
`write_afm_config(config.pipeline.agent)`; `apply_skip_stages` rebuilds a
six-field document; `tests/pipeline/test_afm_config.py:42` pins
`parameters == ["agent"]` and the `tests/pipeline/test_run_pipeline.py` fake
(≈ line 1124) accepts only `(agent)`.

Strategy: leaves-first TDD in the design's mandated order — workflow (models →
parser top level → parser attachments) → compiler (models → serializer →
emission) → hooks (overlay) → pipeline (config write → threading) →
process-level integration proof. Every task is gated by the Mandatory Rules
below. CODEMANIFEST changes and all `.usages/`/docs supplements are **already
applied in the working tree** — this plan touches code and tests only.

## Mandatory Rules

<!-- Extracted verbatim from the project convention `.goga/usages/conventions.md`
     (the `convention` practice wired into every cell of this feature — for
     working with the codebase, organizing the REPL development cycle, debugging
     and testing, and the test infrastructure), the language rules
     (`goga-cell-python`), the ruff configuration (`pyproject.toml`), and the
     repo gates (`.github/workflows/lint.yml`, `.githooks/`). These rules are
     MANDATORY for every task in this plan. Where a task restates a rule, the
     restatement is a reminder, not a replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`.
- **Imports**: relative imports for ALL intra-package references inside `goga/`
  (`from .workflow_assistant import WorkflowAssistant`, `from ..workflow import
  WorkflowDocument`); absolute imports only for stdlib and third-party. The new
  model files mirror the existing cell idiom: `from __future__ import
  annotations` at the top. Exception — tests: cross-directory references inside
  `tests/` use absolute imports rooted at the `tests` package.
- **Data models**: stdlib `dataclasses` only; model classes use
  `@dataclass(kw_only=True)` with fields in the declared contract order (the
  `workflow_stage.py` / `flow_document.py` precedent); empty defaults for
  fields (`delegate=False`, `gate=False`, `when="checkpoints"`,
  `max_tasks=50`, `skills=[]`); `None` only for the explicit absence of a value
  (`prompt`, `skills`, `agent`, `env`, `depth`, `max_depth`, the stage
  `assistants` list, the whole `delegation` block).
- **Docstrings**: Google style, MANDATORY for every public function, method,
  and class. First line starts with a capital letter and ends with a period.
  Include `Args` when the function accepts parameters, `Returns` when it
  returns a value, `Raises` when it raises beyond built-in types. Dataclass
  models document every field in the `Args:` block (the
  `workflow_stage.py` precedent — the CODEMANIFEST field descriptions are the
  source text). Click command callbacks are the documented exception (no
  `Args`/`Returns`/`Raises`) — no CLI callback is touched by this plan.
- **Code formatting**: inside function and method bodies, separate logical
  blocks by ONE blank line (initialization / conditions and loops / data
  preparation / processing / return).
- **Type hints**: mandatory everywhere (drives facade signature extraction).
  Allowed shapes: `str`, `int`, `float`, `bool`, `list[T]`, `dict[str, T]`,
  `T | None`. Forbidden: `*args`, `**kwargs`, bare `dict`, bare `list`.
- **Naming**: PascalCase classes, snake_case functions/methods/properties/
  modules; private helpers one leading underscore.
- **Facade**: each cell's `__init__.py` exposes the contract API through
  `__all__`; only identifiers in `__all__` constitute the facade; `__all__`
  stays alphabetically sorted (uppercase first). Workflow 16 → 18
  (+ `WorkflowAssistant`, `WorkflowDelegation`); compiler 16 → 19
  (+ `FlowAssistant`, `FlowCollaboration`, `FlowTeamMember`); pipeline stays 19.
- **Logging**: stdlib `logging` (`logger = logging.getLogger(__name__)`);
  structured records with contextual metadata (`extra={...}`), lowercase
  messages, stable event names. The ONE new log point of this feature is
  `logger.info("wrote afm collaboration plumbing", extra={...profile count /
  has-limits...})` after the config write — never env values, never commands,
  never configuration content (the design's logging constraint).
- **Error messages are contractual**: the design's Error Message Catalog (and
  its mirror `goga/pipeline/workflow/.usages/assistants.md`) pins the wording;
  tests pin it with `pytest.raises(..., match=...)`. If a message must change
  during implementation, change the practice file in the same commit and record
  the reason (design Additional Instruction 6).
- **Dependencies**: no new third-party dependencies — `pyyaml`, `click` are
  already pinned in `pyproject.toml`; any hypothetical new library MUST go into
  `pyproject.toml` with a minimum version.
- **No public API beyond the contract** (design Additional Instruction 3): no
  `is_declaration` helper on the models, no new exports beyond the five new
  types, no shared closure module — the discriminator is a private one-line
  helper per consuming cell, the closure helpers are private to `afm_config.py`.

### Test Writing Rules (strictly per `conventions.md` — Testing)

- **Tools**: pytest (runner), ruff (lint + format of test code), pytest-cov
  (coverage). Test libraries live in `pyproject.toml`
  `[project.optional-dependencies]` under `test`.
- **Structure mirrors source directly**: `goga/pipeline/workflow/
  workflow_assistant.py` → `tests/pipeline/workflow/
  test_workflow_assistant_contract.py`; `goga/pipeline/compiler/
  flow_collaboration.py` → `tests/pipeline/compiler/
  test_flow_collaboration_contract.py`; the parser assistants suite lives in
  `tests/pipeline/workflow/test_parse_workflow_assistants.py`; the overlay
  suite in `tests/pipeline/hooks/test_overlay_assistants.py`; the config suite
  in `tests/pipeline/test_afm_config_collaboration.py`. Every test directory
  already carries `__init__.py`.
- **Fixtures**: local fixtures in `tests/<package>/conftest.py`, shared
  fixtures in `tests/conftest.py`. Available shared infrastructure (reused,
  never duplicated): `is_kw_only_dataclass` (`tests/conftest.py:70`); the
  `config_path` fixture of `tests/pipeline/test_afm_config.py:53` (the fixed
  home path constant patched into the tmp tree — never the filesystem root);
  the `_in_container_run_context` autouse fixture of
  `tests/pipeline/conftest.py:47`; the overlay fixtures of
  `tests/pipeline/hooks/test_overlay.py`; the run-pipeline wiring fakes of
  `tests/pipeline/test_run_pipeline.py` (the fake `_write_afm_config` at
  ≈ line 1124 MUST be updated to the new signature in the same change).
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`;
  grouping `class Test<Component>:` with docstrings; self-documenting test
  names; keep comments minimal.
- **Test types**: Unit — every public function/method/class, main scenario and
  typical data. Edge cases — empty inputs (`""`, `{}`, `[]`, absent blocks,
  `None`), boundary values (`depth: 0`, `max_tasks: 1`, `depth: 0` surviving
  to `max_depth: 0` — the falsy-zero trap), invalid types (the parser
  negative table), expected exceptions via `pytest.raises` with `match=`.
  Integration — only for interaction between modules/packages (the
  compile→serialize→config-write chain of Task 10).
- **Boundary tests**: the parser negative table and the `when` domain use
  `@pytest.mark.parametrize` with a table of values covering both sides of
  every boundary (all three `when` values valid; the invalid ones rejected).
- **Mocks**: pure logic — NO mocks (parser, compiler, serializer, overlay are
  mock-free); file I/O — the `tmp_path` fixture exclusively (pipeline-file +
  workflow-file into `tmp_path`, config path and closure base patched into
  `tmp_path`); external dependencies — `mock.patch` at the import point (the
  run-pipeline fakes). Mock only at external boundaries.
- **Golden values are grounded, never recalled**: every pinned golden fragment
  in this plan (the team/stage attachment YAML fragments, the closure text,
  the error messages) was verified by the design against the live sources and
  a real `yaml.dump` run with the serializer's exact parameters
  (`indent=2`, `default_flow_style=False`); if an assertion disagrees with a
  live run during implementation, the live run wins and the disagreement is
  reported — never silently "aligned". Do NOT "fix" indentation by altering
  the dumper (that would break byte-identity with the existing stage
  rendering).
- **Existing tests that pin the old surface are adapted in the same change**
  (design Additional Instruction 2): `test_afm_config.py` signature test
  (`["agent"]` → `["agent", "flow", "workflow"]`), the `test_run_pipeline.py`
  fake, the workflow stage/document/parse contract enumerations, the compiler
  `test_flow_document_contract.py` / `test_compile_flow.py` goldens (the
  collaboration block is inserted deliberately; keep the byte-identity
  assertion), the further compiler old-surface pins — the byte-exact
  full-text goldens of `test_compile_flow_workflow.py` (≈ line 2869) and
  `test_compile_flow_trigger.py` (≈ line 338) gain the two-line block, and
  the compiled top-level key-order pins `list(loaded.keys()) ==
  ["name", "description", "stages"]` of `test_integration.py` (line 94) and
  `test_integration_roles.py` (lines 106/154/194) gain `"collaboration"`
  between `description` and `stages` — and the source-text pin of
  `test_run_pipeline_contract.py` (line 417,
  `"write_afm_config(config.pipeline.agent)" in source`) is updated to the
  threaded three-argument call.

### Linter and Formatter Enforcement (all development stages and local commits)

The following gates are MANDATORY at the end of EVERY task and BEFORE EVERY
local commit, across all development stages. A failing gate is an actionable
defect, never acceptable noise. Local git hooks do NOT enforce formatting
(only the commit-msg / pre-push Co-Authored-By policy does) — the author runs
the formatter deliberately:

1. `ruff check goga/ tests/` — zero violations (the CI gate of
   `.github/workflows/lint.yml`; rule set per `pyproject.toml`: E, W, F, I, N,
   UP, B, SIM, PL, PLR, C4, DTZ, PT, ARG, RUF, PTH, C90; line length 120;
   target py310; mccabe max-complexity 10; the tests per-file-ignores apply).
2. `ruff format --check goga/ tests/` — zero reformattings; run
   `ruff format goga/ tests/` when it reports diffs.
3. `goga lint` — cell-level lint, **0 errors over 91 cells** (verified green
   on the pre-change tree; if a run reports an error a re-run does not
   reproduce, trust the re-run — the command is occasionally flaky in this
   tree; a persistent error is real).
4. Focused tests green, then `pytest tests/ -x` green (the full battery — the
   existing suites stay green except the deliberate adaptations listed in the
   Test Writing Rules).
5. Facade import checks green (see Validation Commands).
6. **Commit policy**: commit only with all gates green; commit messages MUST
   NOT contain `Co-Authored-By:` trailers (`.githooks/commit-msg` and
   `pre-push` reject them).
7. `CODEMANIFEST` files are READ-ONLY for the implementer — the contract
   changes are already applied in the working tree; if code does not match the
   contract, fix the code, never the contract.

### REPL Cycle Rules (continuous interactive evaluation, hot reloading, migration to source)

The `convention` practice is wired into every cell of this feature for
"Organizing the REPL development cycle". Every coding task in this plan
follows the same loop:

1. **Virtualenv first**: all code executes inside a virtualenv — create it if
   missing. No `.venv` exists in the workspace right now and the system
   interpreter (`/opt/goga/bin/python3`, Python 3.12.16) has no pytest/ruff —
   Task 1 bootstraps the environment (`python3 -m venv .venv` +
   `.venv/bin/pip install -e ".[test]"`) and verifies the baseline gates green
   BEFORE any change; every subsequent probe, test run, and lint run executes
   inside it.
2. **Probe before writing**: verify each non-trivial behavior interactively
   against real inputs BEFORE the verified snippet is written into a source
   file. The probes of this feature: construct `WorkflowAssistant` /
   `WorkflowDelegation` with defaults and confirm the kw-only shape (Task 1);
   round-trip a catalog YAML literal through `yaml.safe_load` and confirm the
   presence-based reads (`skills: []` satisfies at-least-one, `env: {}` →
   `None`, `depth: 0` is an authored int not an absence) (Tasks 2–3);
   construct the three flow models and render a hand-built `FlowDocument`
   through `yaml.dump(..., indent=2, default_flow_style=False)` to CONFIRM the
   pinned golden fragments (dash at parent-key indentation, item keys at
   dash-indent + 2, nested list items at the KEY's indentation, `[]` for empty
   lists) BEFORE writing the golden tests (Tasks 4–5); drive one
   `_collaboration_emission`-shaped namespace/attachment pair in the REPL to
   confirm reference-takes-declaration-fields and the translated-agents
   comparison (Task 6); drive one merge quadruple (base + two contributions)
   and confirm the drop/overwrite outcomes (Task 7); call `write_afm_config`
   with `_AFM_CONFIG_PATH` and `_CLOSURE_BASE` redirected into a tmp dir,
   re-read the YAML, `stat()` the closure file, and confirm the `0o700` mode
   and the exact closure text (Task 8); confirm the threading objects are the
   very same instances via `is` in a scratch run (Task 9).
3. **Hot feedback after every edit**: immediately re-run the focused test file
   and the facade import check in the same virtualenv; iterate in small
   steps. A long-lived REPL session re-imports edited modules
   (`importlib.reload` or a fresh `python -c`) — never trust stale module
   state as evidence; module-level state (the `_TOP_LEVEL_KEYS` /
   `_STAGE_KEYS` / `_CANONICAL_KEY_ORDER` / `_KEYS_AFTER_COMMAND` tuples, the
   `_GATE_MODE` / `_WHEN_TRIGGER` maps) demands a fresh interpreter after
   every edit.
4. **Migrate verified code to source files**: REPL-verified snippets are
   migrated into the target `location` file with type hints, Google
   docstrings, relative imports, and convention formatting; REPL scratch
   never ships and is never referenced by source.
5. **Close the loop per task**: probe → implement (migrate) → focused tests →
   full battery → lint/format gates → commit (gates green).

## Context

### Contract Surface

**Entity: `WorkflowAssistant`** (cell `goga/pipeline/workflow` — NEW,
`location: workflow_assistant.py`)
- Type: data model (pure data; no validation, no resolution)
- Declared signature (CODEMANIFEST, exact):
  `WorkflowAssistant(name: str, prompt: str | None = None, skills: list[str] | None = None, agent: str | None = None, delegate: bool = False, env: dict[str, str] | None = None, gate: bool = False, when: str = "checkpoints")`
- Facade obligation: importable from `goga.pipeline.workflow`; joins `__all__`
  (16 → 18)
- Implementation (design, verbatim):

  ```python
  @dataclass(kw_only=True)
  class WorkflowAssistant:
      name: str                                  # required, no default
      prompt: str | None = None
      skills: list[str] | None = None
      agent: str | None = None
      delegate: bool = False
      env: dict[str, str] | None = None
      gate: bool = False
      when: str = "checkpoints"
  ```

- Semantic requirements: one model for all three entry forms — catalog
  declaration, full inline stage declaration, stage reference (with overrides).
  Docstring documents every arg: name grammar and uniqueness enforced by
  `parse_workflow` (name pattern `[A-Za-z0-9._-]+` fullmatch, reserved name
  `assistant`); `gate`/`when` authored only on attachments; consumers own
  resolution and delivery. Constraints honored: no validation, no profile-id
  derivation, no env action.
- Edge cases: `skills=[]` and `prompt=""` are PRESENCE, not truthiness — the
  declaration discriminator is `prompt is not None or skills is not None`
  (identity check, never truthiness; approved decision 2).

**Entity: `WorkflowDelegation`** (cell `goga/pipeline/workflow` — NEW,
`location: workflow_delegation.py`)
- Type: data model of the delegation block with materialized defaults
- Declared signature (CODEMANIFEST, exact):
  `WorkflowDelegation(depth: int | None = None, max_tasks: int = 50)`
- Facade obligation: importable from `goga.pipeline.workflow`; joins `__all__`
- Implementation (design, verbatim): `@dataclass(kw_only=True)` with the two
  fields above.
- Semantic requirements: `depth` `None` when absent (an authored `0` is a
  VALUE — the falsy-zero guard); `max_tasks` materializes to 50 when absent
  (the engine default of 20 is never relied upon); an empty block is valid and
  yields `WorkflowDelegation(depth=None, max_tasks=50)`.

**Entity: `WorkflowStage`** (cell `goga/pipeline/workflow` — CHANGED,
`location: workflow_stage.py`)
- Delta: the field set gains `assistants: list[WorkflowAssistant] | None = None`
  as the LAST field (after `memory`), mirroring the CODEMANIFEST signature
  `... memory: bool | None = None, assistants: list[WorkflowAssistant] | None = None)`.
  The `Args:` docstring gains the contract's field description (the stage's
  assistant attachments or `None`; validated by `parse_workflow`; consumed by
  the compiler to emit the stage's assistants entries; declarative).
- Facade obligation: already exported; no `__all__` change for this entity.

**Entity: `WorkflowDocument`** (cell `goga/pipeline/workflow` — CHANGED,
`location: workflow_document.py`)
- Delta: the field set gains `assistants: dict[str, WorkflowAssistant] =
  field(default_factory=dict)` (default empty dict) and, LAST,
  `delegation: WorkflowDelegation | None = None` — matching the CODEMANIFEST
  "assistants/delegation (last fields)" rule. Docstring `Args:` entries added.
- Facade obligation: already exported.

**Routine: `parse_workflow(text: str) -> document: WorkflowDocument`** (cell
`goga/pipeline/workflow` — CHANGED, `location: parse_workflow.py`)
- Delta: steps 6.5–6.8 plus the extraction/valid-keys/empty/return
  consistency updates. New/changed internals (design Algorithm Design,
  verbatim — existing structure preserved, additions only):

  ```
  _TOP_LEVEL_KEYS += ("assistants", "delegation")            # message order pinned
  _STAGE_KEYS      += ("assistants",)
  _ASSISTANT_CATALOG_KEYS = ("name", "prompt", "skills", "agent", "delegate", "env")
  _ATTACHMENT_DECLARATION_KEYS = catalog keys + ("gate", "when")
  _DELEGATION_KEYS = ("depth", "max_tasks")
  _WHEN_VALUES = ("start", "checkpoints", "finish")
  _ASSISTANT_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]+")   # fullmatch
  _RESERVED_ASSISTANT_NAME = "assistant"

  _build_stage_assistants(stage, value):
    1. non-list → "non-list assistants in workflow.stages.{stage}"
    2. empty → None (absence)
    3. per element, in list order → _build_attachment_entry(stage, element)
    → list[WorkflowAssistant]

  _build_attachment_entry(stage, element):
    1. str element → reference: _validate_assistant_name(element) →
       WorkflowAssistant(name=element) (all defaults materialized)
    2. dict element:
       a. keys ⊆ {name, gate, when} → reference with overrides:
          name required+str; gate bool; when domain
       b. else → full inline declaration: unknown-key check against
          _ATTACHMENT_DECLARATION_KEYS; per-field validation (catalog rules);
          gate bool; when domain; at-least-one-of prompt/skills; name rules
    3. non-str non-dict element → "invalid assistant entry in
       workflow.stages.{stage}.assistants"
    → WorkflowAssistant

  _build_assistant_catalog(raw): step 6.5 over list entries
    (scope workflow.assistants.NAME; unknown keys include gate/when;
     at-least-one; name rules; a name repeating WITHIN the catalog raises
     "duplicate assistant name: {name}" AT BUILD TIME — a local seen set in
     the entry loop, because the dict is keyed by name and the later
     namespace walk over values() could never see an in-catalog repeat)
    → dict[str, WorkflowAssistant] (authored order)

  _build_delegation(raw): step 6.6 (int checks exclude bool; presence-based;
    max_tasks materialized 50) → WorkflowDelegation | None

  _validate_assistant_namespace(assistants, stages):
    seen = set()
    for entry in assistants.values():            # catalog order
        if entry.name in seen: raise "duplicate assistant name: {name}"
        seen.add(entry.name)
    for stage in stages.values():                # authored stage order
        for entry in stage.assistants or []:
            if _is_declaration(entry):
                if entry.name in seen: raise "duplicate assistant name: {name}"
                seen.add(entry.name)
  ```

  `_validate_assistant_name(name)`: non-str handled by the callers'
  required/str checks; grammar `fullmatch` else `invalid assistant name:
  {name}`; `name == "assistant"` → `assistant name is reserved`.
- Parser wiring (design Trace 1, verbatim): `yaml.safe_load` → mapping check →
  `_extract_top_level` gains the dispatch arms (`assistants` must be a `list`,
  else `non-list assistants block in workflow`; `delegation` must be a `dict`,
  else `non-mapping delegation block in workflow`) and returns an **8-tuple**;
  `_build_stages` → `_validate_stage_field` gains the `assistants` arm
  dispatching to `_build_stage_assistants(name, value)`, and the 6.1.2
  unknown-key message lists `assistants` last; `_build_extend` →
  `_reject_forbidden_extend_keys` tuple gains `"assistants"`; the catalog
  (6.5) and delegation (6.6) passes follow the extend pass; the
  duplicate-name pass runs last (it needs the catalog).
- Ordering decision (design, binding): stage attachments validate inside the
  stage pass (contract 6.1.14 builds `WorkflowStage` from validated values
  including `assistants`); single-defect files pin exactly one message;
  multi-defect files surface the earlier pass's error — the deterministic pass
  order.
- Empty-workflow rule (verbatim): `prompt is None AND stages empty AND extend
  empty AND memory is None AND build is None AND assistants empty AND
  delegation is None` → the pinned extended message (see Error Catalog);
  assistants-only and delegation-only workflows are VALID.
- Edge cases (design): empty catalog list `assistants: []` → empty dict (and
  does not rescue an empty workflow); `delegation: {}` →
  `WorkflowDelegation(None, 50)`; `skills: []` on a declaration satisfies
  at-least-one (presence, not truthiness) and the entry IS a declaration;
  `env: {}` → `None`; a duplicate reference on one stage list is legal at
  parse time (the compiler owns the per-stage duplicate check); `assistants`
  on an extend-entry is rejected (appended last to the forbidden tuple).
- Error type: every parser error above is `WorkflowSyntaxError`.

**Entities: `FlowCollaboration`, `FlowTeamMember`, `FlowAssistant`** (cell
`goga/pipeline/compiler` — NEW, `location:` `flow_collaboration.py` /
`flow_team_member.py` / `flow_assistant.py`)
- Type: plain kw-only dataclasses mirroring the emission order (design,
  verbatim):

  ```python
  @dataclass(kw_only=True)
  class FlowCollaboration:
      mode: str = "assistants"
      max_depth: int | None = None

  @dataclass(kw_only=True)
  class FlowTeamMember:
      id: str
      title: str
      profile: str
      instruction: str
      skills: list[str]

  @dataclass(kw_only=True)
  class FlowAssistant:
      profile: str
      title: str
      instruction: str
      mode: str
      trigger: str
      skills: list[str]
  ```

- Facade obligation: importable from `goga.pipeline.compiler`; `__all__`
  16 → 19 (alphabetical).
- Semantic requirements: `mode` is `"assistants"` in every emitted block;
  `instruction = prompt if not None else ""`, `skills = skills if not None
  else []` at emission; `profile` is the `goga-<name>` binding; `mode` /
  `trigger` are the translated `gate` / `when` vocabularies.

**Entity: `FlowDocument`** (cell `goga/pipeline/compiler` — CHANGED,
`location: flow_document.py`)
- Delta: the eight-key contract — gains `collaboration:
  FlowCollaboration | None` and `team: list[FlowTeamMember] | None` BETWEEN
  `memory` and `stages` (field order is the emission order). Docstring
  updated: "up to eight top-level keys", the two new slots emitted between
  `memory` and `stages` when present.
- Facade obligation: already exported.

**Entity: `FlowStage`** (cell `goga/pipeline/compiler` — CHANGED,
`location: flow_stage.py`)
- Delta: the `fields` docstring contract gains the canonical `assistants`
  slot after `memory_use` (docstring-level change; the fields dict itself is
  keyed — `_CANONICAL_KEY_ORDER` owns the order in `compile_flow`).

**Routine: `compile_flow(...)`** (cell `goga/pipeline/compiler` — CHANGED,
`location: compile_flow.py`)
- Delta: steps 4.10 / 5 / 6. Collaboration internals (design, verbatim):

  ```
  _PROFILE_PREFIX = "goga-"
  _GATE_MODE = {True: "required", False: "advisory"}
  _WHEN_TRIGGER = {"start": "one_shot", "checkpoints": "checkpoints",
                   "finish": "on_completion"}

  _is_assistant_declaration(entry) -> entry.prompt is not None or entry.skills is not None

  _assistant_namespace(workflow) -> dict[str, WorkflowAssistant]:
    namespace = dict(workflow.assistants)
    for stage in workflow.stages.values():
        for entry in stage.assistants or []:
            if _is_assistant_declaration(entry): namespace[entry.name] = entry
    → namespace (parser/overlay guarantee: no duplicate names)
  ```

- Step 4.10 `_collaboration_emission(workflow, effective, expanded,
  expanded_ids)` (design, verbatim essentials):
  1. `namespace = _assistant_namespace(workflow)` (None workflow → empty).
  2. `team = [FlowTeamMember(id=n, title=n, profile=_PROFILE_PREFIX+n,
     instruction=prompt or "", skills=skills or []) for n, e in
     workflow.assistants.items()]` — authored order, empty list when no
     catalog.
  3. `block = FlowCollaboration(mode="assistants", max_depth=
     workflow.delegation.depth if workflow.delegation else None)` — on EVERY
     compilation (workflow-less included).
  4. Attachment resolution per base name with a non-empty effective
     attachment list, per entry in list order, then per produced id — the
     four checks in CONTRACT ORDER: unknown reference → duplicate in one
     stage list → body carries `script` → translated agents exactly
     `["planning"]` (computed as `[translate_role(r) for r in roles]` when
     `_has_usable_roles(body)`, else the `["auto"]` default). Then the
     `FlowAssistant` list is built once per base stage and mapped onto every
     produced id (uniform across loop copies): references take the
     declaration fields (prompt/skills/agent/delegate/env) from the namespace
     entry and keep their OWN `gate`/`when`; declarations are their own
     source.
- Step 5 assembly (verbatim): `_reject_authoring_output_keys` gains the
  `assistants` prohibition (pinned message below); `_canonical_fields` gains
  the `assistants_fields` argument; `_assemble_assistants(source, assistants)`
  assigns the list into the rebuilt fields before the canonical-order loop,
  which slots it after `memory_use` (`_CANONICAL_KEY_ORDER` gains
  `"assistants"` LAST); the value deep-copies through the canonical loop like
  every other field; `None`/empty assembles no key.
- Step 6 assembly (verbatim): `FlowDocument(..., memory=...,
  collaboration=emission.block, team=emission.team, stages=...)`.
- **C2.4 — `_effective_overrides` (approved decision 5, MANDATORY)**:
  extend-seeded defaults stay `assistants=None`; the MERGED branch adds
  `assistants=stg.assistants` explicitly. Without it, a stage that has both an
  extend-entry and a stages-block entry loses its attachments — the
  silent-drop defect this design guards.
- Assembly wiring (verbatim): `_reconstruct_body` returns the emission as a
  fourth value; workflow-less compiles construct the default emission
  (`block=FlowCollaboration(mode="assistants", max_depth=None), team=[],
  assistants_by_id={}`).
- Edge cases: skipped stage → removed before the loop, attachments never
  checked, no ids in the flow, no profile later; loop-expanded copies share
  the same `FlowAssistant` list (uniform) and each copy's body is checked;
  `roles` missing → default `["auto"]` never trips the planning check;
  `workflow=None` → block only.
- Error type: `StructuralError` for the four structural checks + the body-key
  prohibition.

**Routine: `serialize_flow(doc: FlowDocument) -> text: str`** (cell
`goga/pipeline/compiler` — CHANGED, `location: serialize_flow.py`)
- Delta (design, verbatim):

  ```
  if doc.collaboration is not None:
      top["collaboration"] = {"mode": …, "max_depth": …}   # max_depth dropped when None
  if doc.team:                                             # empty/None → omitted
      top["team"] = [_member_repr(m) for m in doc.team]

  _member_repr(m) = {"id": …, "title": …, "profile": …,
                     "instruction": _BlockLiteralScript(m.instruction) if "\n" in m.instruction else m.instruction,
                     "skills": m.skills}

  # in _build_stage_repr, for the "assistants" key (value: list[FlowAssistant]):
  [{"profile": e.profile, "title": e.title,
    "instruction": wrapped-or-plain(e.instruction),
    "mode": e.mode, "trigger": e.trigger, "skills": e.skills} for e in value]
  ```

- Emission order: `prompt` → `root_dir` → `name` → `description` → `memory`
  (None fields dropped) → **`collaboration`** (key order `mode, max_depth`;
  `max_depth` omitted when `None` — the omission rule is `is None`, NEVER
  truthiness) → **`team`** (each member `id, title, profile, instruction,
  skills`; `instruction` wrapped in `_BlockLiteralScript` iff it contains
  `\n`; `skills` a plain list, `[]` when empty) → `stages`. Stage fields: the
  `assistants` value becomes a list of ordered mappings `profile, title,
  instruction, mode, trigger, skills` with the same wrapping; `mode`/`trigger`
  plain scalars; `skills: []` when empty.
- Constraint (binding): `yaml.dump(default_flow_style=False)` already renders
  empty lists as `[]` (the `depends_on: []` precedent) and mappings as block
  style — NO new representer; the existing `_BlockLiteralScript` representer
  is REUSED. Do not reorder; do not "fix" the indentation by altering the
  dumper (byte-identity with the existing stage rendering).
- Output: canonical YAML string, single trailing newline.

**Routine: `merge_workflow_overlay(base, contributions) -> overlay:
WorkflowOverlay`** (cell `goga/pipeline/hooks` — CHANGED,
`location: overlay.py`)
- Delta — steps 4a / 4b / 5a (design, verbatim):

  ```
  _STAGE_FIELDS += ("assistants",)                 # last; _STAGE_DEFAULTS keeps None
  _is_assistant_declaration(entry)                 # same one-line rule as the compiler

  merge_workflow_overlay(base, contributions):
    1. passthrough when no contributions (unchanged)
    2. namespace = {authored catalog names} ∪ {declaration names of authored stage entries}
    3. assistants = _merge_catalog(base, contributions, namespace)
         merged = dict(base.assistants) if base else {}
         for c in contributions:
             for name, entry in c.document.assistants.items():
                 if name in seed: continue          # seed = the step-2 namespace snapshot
                 merged[name] = entry               # later contribution wins per name
         namespace |= merged.keys()
    4. delegation = _merge_delegation(base, contributions)   # whole block, like memory
    5. stages = _merge_stages(base, contributions, namespace)  # threads the namespace
         _merge_stage: field loop SKIPS "assistants";
           values["assistants"] = _merge_stage_assistants(...)
    6. WorkflowDocument(prompt, stages, extend, memory, profile, build,
                        assistants, delegation)
  ```

- `_merge_stage_assistants(authored_list, stage_name, contributions, namespace)`
  (Trace 4 step 5, verbatim): result = authored list (verbatim, authored
  order) when present else `[]`; `present_on_stage` = its names; for each
  contribution carrying the stage, for each entry in enumeration order:
  dropped when the name is already on the stage; an appended DECLARATION
  additionally dropped when its name is in the evolving namespace; accepted
  entries append, join `present_on_stage`, and accepted declarations join the
  namespace (later stages see them). Empty result → `None`.
- **Cross-kind collision, outcome PINNED** (design-review fix 3): because
  `_merge_catalog` consults only the authored seed (the catalog pass runs
  before any stage append is accepted, per the 4a → 5a step order), a LATER
  tool's catalog entry DISPLACES an EARLIER tool's inline declaration (the
  catalog entry is accepted; the earlier declaration is dropped at stage-merge
  time by the namespace check — the stage loses that attachment; the name
  lives on only as the catalog entry). The mirror direction keeps the earlier
  catalog entry and drops the later declaration. Deterministic,
  invariant-preserving — pinned by
  `test_overlay_catalog_entry_displaces_earlier_inline_declaration`.
- `_merge_delegation`: authored block when present (unbeatable); else the last
  contribution carrying a block wins; no field merging — identical to
  `_merge_memory` (whole-block).
- Constraints: every collision is a SILENT drop (no-raise); inputs never
  mutated; the merged result stays declarative (compilable); the namespace
  never duplicates.

**Methods: `WorkflowAmendment.contribute` / `PipelineHooks.amend_workflow`**
(cell `goga/pipeline/hooks` — CHANGED, `location: events.py`)
- Delta (Trace 4 step 7 / Trace 8, verbatim): the per-hook buffer shape guard
  (currently `for fact in ("prompt", "stages", "extend", "memory"):`
  at `events.py:150`) gains `"assistants"` and `"delegation"` — without them a
  duck-typed buffer missing the new attributes would raise `AttributeError`
  inside `merge_workflow_overlay`, OUTSIDE the per-hook intercept. The
  empty-document condition (`events.py:164`) gains `not document.assistants
  and document.delegation is None`. A delegation-only contribution IS content
  (not a no-op) and reaches the merge; the warning and discard behavior are
  unchanged.

**Routine: `write_afm_config(agent, flow=None, workflow=None) ->
config_path: Path`** (cell `goga/pipeline` — CHANGED, fully replaced,
`location: afm_config.py`)
- Declared signature (CODEMANIFEST, exact):
  `write_afm_config(agent: str | None, flow: FlowDocument | None = None, workflow: WorkflowDocument | None = None) -> config_path: Path`
- Algorithm (design, verbatim):

  ```
  _CLOSURE_BASE = Path("/tmp/goga-assistant-env")
  _LEGAL_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
  _PROFILE_PREFIX = "goga-"

  write_afm_config(agent, flow=None, workflow=None):
    1. wrapper = resolve_wrapper_path(agent) if agent is not None else None
    2. content = {client?, theme, open_browser, proxy, prompts_dir, hooks}   # unchanged
    3. if flow is not None and workflow is not None:
         content["collaboration"] = _collaboration_section(agent, flow, workflow)
    4. write whole file (yaml.safe_dump, sort_keys=False) → return path

  _collaboration_section(agent, flow, workflow):
    1. names = ordered-unique([m.id for m in flow.team] +
                              [e.title for s in flow.stages
                               for e in s.fields.get("assistants", [])])
    2. namespace = workflow.assistants ∪ inline declarations (with site:
       "workflow.assistants" or f"workflow.stages.{stage}")
    3. resolved = {}                                  # name → (delegate, env, command) — no I/O
       for name in names:
           decl, site = namespace[name] or raise ValueError(
               f"unknown assistant reference in the compiled flow: {name}")
           if decl.env is not None:
               for key in decl.env:
                   if not _LEGAL_ENV_NAME_PATTERN.fullmatch(key):
                       raise ValueError(f"invalid environment variable name in the {name} assistant env: {key!r}")
           target_agent = decl.agent if decl.agent is not None else agent
           if target_agent is None:
               raise ValueError(f"assistant {name} at {site} "
                                 f"{'declares env but ' if decl.env is not None else ''}"
                                 f"resolved no agent: set its agent or a global agent")
           resolved[name] = (decl.delegate, decl.env, resolve_wrapper_path(target_agent))
    4. _CLOSURE_BASE.mkdir(parents=True, exist_ok, mode=0o700); chmod(0o700)
       for name, (_, env, target) in resolved.items():
           if env is not None:
               path = _CLOSURE_BASE / f"{_PROFILE_PREFIX}{name}"
               _write_owner_only(path, _render_closure(env, target))   # local helpers
               command = str(path)
           else:
               command = target
           profiles[f"{_PROFILE_PREFIX}{name}"] = {"title": name, "command": command,
                                                   "delegate": resolved[name][0]}
    5. section = {"profiles": profiles}
       if workflow.delegation is not None:
           section["limits"] = {"max_tasks": workflow.delegation.max_tasks}
       → section
  ```

- `_render_closure(env, target)` = `#!/bin/sh\n` + one `export K=V` per entry
  (`shlex.quote`) + `exec target "$@"\n` (the `per-stage-env` content
  contract, implemented LOCALLY — no cross-module private import);
  `_write_owner_only` = `os.open(path, O_WRONLY|O_CREAT|O_TRUNC, 0o700)`.
- Requirements (binding): both pre-run `ValueError`s fire BEFORE any file is
  written (closures included — resolve everything in memory first, then
  materialize); profiles exist exactly for the flow-referenced ids (the
  compiled flow is the single source of truth — an attachment removed by a
  stage skip never appears in the flow, so no dead profile); each profile has
  EXACTLY three keys `{title, command, delegate}`; `limits.max_tasks` only
  when the workflow carries a delegation block; the kill-switch
  (`collaboration.enabled` / `AFM_COLLABORATION`) is neither read nor
  written; closures are owner-only from the first byte (`os.open` `0o700`,
  never create-then-chmod); file names are always `goga-`-prefixed so the
  `[A-Za-z0-9._-]` name grammar cannot produce `.`/`..` path segments; the
  project-layer `.afm/config.yaml` is never touched (the `goga-` prefix is
  the user's deliberate override channel); whole-file rewrite on every launch
  (repeated invocation safe); one `logger.info` after the write.
- Error type: `ValueError` (house precedent: `apply_stage_env_wrappers`, the
  amendment delivery); it propagates out of `run_pipeline` before any run
  event fires.

**Routine: `run_pipeline(...)`** (cell `goga/pipeline` — CHANGED,
`location: run_pipeline.py`)
- Delta (Trace 6, verbatim): step 16 becomes
  `write_afm_config(config.pipeline.agent, flow_doc, overlay.workflow)` —
  currently `write_afm_config(config.pipeline.agent)` at `run_pipeline.py:457`
  — placed after the prompt materialization, before the composition/launch.
  `flow_doc` is the exact document the flow-file was serialized from;
  `overlay.workflow` is the exact document it was compiled from (the overlay
  workflow when the amendment layer is on, the skip-merged resolved workflow
  when disabled, `None` when nothing resolved) — the two artifacts cannot
  diverge. A collaboration `ValueError` surfaces here with no events fired.

**Routine: `apply_skip_stages(...)`** (cell `goga/pipeline` — CHANGED,
`location: apply_skip_stages.py`)
- Delta (Trace 7, verbatim): the rebuild (currently `apply_skip_stages.py:60`
  — a six-field `WorkflowDocument(...)`) passes
  `assistants=workflow.assistants if workflow is not None else {}` (same
  object — opaque carry) and `delegation=workflow.delegation if workflow is
  not None else None` — the memory/profile/build precedent. `None` workflow +
  skips synthesizes a document with the default empty catalog. Input never
  mutated; skipped stages' `WorkflowStage(skip=True)` entries carry
  `assistants=None` (constructor default) — correct: skip removes the stage
  before the attachment checks.

**Anchor change: `stage_env_wrappers.py`** (cell `goga/pipeline` — one line,
design Additional Instruction 9)
- The command-insertion anchor tuple `_KEYS_AFTER_COMMAND`
  (`stage_env_wrappers.py:30`) gains `"assistants"` LAST (after
  `memory_use`). Without it, an env-declaring stage that carries attachments
  but neither a `command` line nor any present anchor key gets its generated
  `command` inserted before `depends_on` — i.e. AFTER `assistants` — breaking
  the canonical key order of the patched flow-file (afm is order-agnostic;
  the invariant is goga's own generated-artifact consistency). The stage-block
  span detection and the `  command:` rewrite are unaffected (assistant
  entries nest at ≥ 4 spaces; block-literal instructions indent deeper still).

### Error Message Catalog (pinned for tests — design, verbatim)

`WorkflowSyntaxError` (parser):

| Condition | Message |
|---|---|
| `assistants:` non-list | `non-list assistants block in workflow` |
| catalog entry non-mapping | `non-mapping assistant entry in workflow.assistants` |
| catalog unknown key (incl. gate/when) | `unknown key in workflow.assistants.NAME: KEY; valid keys: name, prompt, skills, agent, delegate, env` |
| catalog missing name | `name is required in workflow.assistants entry` |
| entry name non-str | `non-str name in workflow.assistants entry` / `non-str name in workflow.stages.STAGE.assistants entry` |
| no prompt and no skills | `assistant NAME requires at least one of prompt or skills` |
| name grammar | `invalid assistant name: NAME` |
| reserved name | `assistant name is reserved` |
| duplicate declaration name | `duplicate assistant name: NAME` |
| `delegation:` non-mapping | `non-mapping delegation block in workflow` |
| delegation unknown key | `unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks` |
| `depth` non-int / < 0 | `non-int value in workflow.delegation.depth` / `depth must be >= 0 in workflow.delegation` |
| `max_tasks` non-int / < 1 | `non-int value in workflow.delegation.max_tasks` / `max_tasks must be >= 1 in workflow.delegation` |
| stage `assistants` non-list | `non-list assistants in workflow.stages.NAME` |
| attachment element non-str non-map | `invalid assistant entry in workflow.stages.NAME.assistants` |
| attachment missing name | `name is required in workflow.stages.NAME.assistants entry` |
| attachment unknown key (declaration) | `unknown key in workflow.stages.STAGE.assistants.NAME: KEY; valid keys: name, prompt, skills, agent, delegate, env, gate, when` |
| `gate` non-bool | `non-bool value in workflow.stages.STAGE.assistants.NAME.gate` |
| `when` out of domain | `when must be one of: start, checkpoints, finish in workflow.stages.STAGE.assistants.NAME` |
| `assistants` in extend-entry | `assistants is forbidden in workflow.extend.NAME` |
| top-level unknown key | `… valid keys: prompt, stages, extend, memory, profile, build, assistants, delegation` |
| stage unknown key | `… valid keys: agent, env, prompt, loop, skills, skip, approve, manual, notes, reflect, memory, assistants` |
| empty workflow | `empty workflow — provide at least prompt, one stage, one extend entry, the memory block, the build block, the assistants block, or the delegation block` |

`StructuralError` (compiler):

| Condition | Message |
|---|---|
| reference names no namespace member | `unknown assistant reference in workflow.stages.NAME: X` |
| same name twice in one stage list | `duplicate assistant in workflow.stages.NAME: X` |
| attachment on a script stage | `assistant is forbidden on a script stage in workflow.stages.NAME: X` |
| attachment on a planning-only stage | `assistant is forbidden on a planning-only stage in workflow.stages.NAME: X` |
| authored `assistants` in a stage body | `assistants key is forbidden in stage body; use assistants in workflow.stages` |

`ValueError` (`write_afm_config`):

| Condition | Message |
|---|---|
| illegal env key | `invalid environment variable name in the NAME assistant env: 'KEY'` |
| no agent (env assistant) | `assistant NAME at SITE declares env but resolved no agent: set its agent or a global agent` |
| no agent (plain assistant) | `assistant NAME at SITE resolved no agent: set its agent or a global agent` |
| flow references an undeclared name (defensive) | `unknown assistant reference in the compiled flow: NAME` |

Two deliberate refinements of the approved wording (binding — do NOT "correct"
them back): the no-agent pre-run errors carry the AUTHORING SITE fragment
(`at workflow.assistants` / `at workflow.stages.NAME`); attachment-entry field
errors are scoped to the ENTRY (`workflow.stages.STAGE.assistants.NAME.when`)
so a multi-entry list names the offending entry.

### Entity Interaction and Data Flow (verbatim from the design)

```
workflow-file (YAML)
      │ parse_workflow                     ┌────────────────────────────────┐
      ▼                                    │ afm engine (v2.x)              │
WorkflowDocument                           │  flow-file: collaboration,     │
  .assistants   dict[name → WorkflowAssistant]  │           team, stages[].assistants │
  .delegation   WorkflowDelegation|None    │  config: collaboration.profiles│
  .stages[*].assistants list[WorkflowAssistant] │         collaboration.limits  │
      │                                   └────────────────────────────────┘
      │                    │                          ▲              ▲
      │ compile_flow       │ merge_workflow_overlay   │ serialize    │ write_afm_config
      ▼                    ▼ (hooks: tool              │ (compiler)  │ (pipeline)
assistant namespace ──────▶ contributions append)      │              │
 = catalog ∪ inline declarations                        │   flow: FlowDocument + workflow:
      │                                                 │     profile ids ← flow
      ▼                                                 │     declarations ← workflow
FlowDocument                                             │     closures ← assistant env
  .collaboration FlowCollaboration (always)              │
  .team         list[FlowTeamMember] (catalog order)     │
  .stages[*].fields["assistants"] list[FlowAssistant] ───┘
```

**Data Flows** (verbatim summaries of the four design flows):

- **Flow 1 — authoring to flow-file.** `parse_workflow` validates the three
  authoring surfaces and materializes defaults → `WorkflowDocument`. The
  compiler builds the namespace, resolves attachments, emits the collaboration
  block, team list, and per-stage assistant entries → `serialize_flow` →
  flow-file bytes.
- **Flow 2 — flow-file + workflow to engine config.** `run_pipeline` step 16
  passes the compiled `FlowDocument` and the effective `WorkflowDocument` to
  `write_afm_config`. The config write walks the flow for referenced profile
  ids (`goga-<name>` of every team member and every stage attachment), walks
  the workflow for each id's declaration, resolves the command (env closure or
  wrapper), and writes `collaboration.profiles` + (when authored)
  `collaboration.limits.max_tasks`. The compiled flow is the single source of
  truth for which ids exist.
- **Flow 3 — tool contributions.** `PipelineHooks.amend_workflow` buffers tool
  contributions (each a parsed `WorkflowDocument`, internally
  duplicate-name-free), drops empty ones, and `merge_workflow_overlay` composes
  the overlay: catalog merge by name (namespace invariant), whole-block
  delegation, per-stage append-with-dedup. The merged document feeds Flow 1.
- **Flow 4 — skip.** `apply_skip_stages` rebuilds the document carrying
  `assistants`/`delegation` verbatim; the compiler removes skipped stages
  before the attachment checks, so a skipped stage attaches nothing and its
  ids never reach the flow (hence no profile).

**Entity dependencies — implementation order (bottom-up, leaves first)**:
1. `workflow` cell — models + parser (no imports).
2. `compiler` cell — models + `compile_flow`/`serialize_flow` (imports
   workflow types).
3. `hooks` cell — overlay merge (imports `WorkflowDocument` only).
4. `pipeline` cell — `afm_config`, `run_pipeline`, `apply_skip_stages`
   (imports compiler + workflow types).
Facade updates ride with each cell. `goga/pipeline/__init__.py` is unchanged.

### Re-exports

- `WorkflowAssistant`, `WorkflowDelegation` — source:
  `goga/pipeline/workflow/workflow_assistant.py` / `workflow_delegation.py`;
  facade obligation: importable from `goga.pipeline.workflow`; `__all__`
  16 → 18 (alphabetical: `WorkflowAssistant` after `WorkflowStage`...
  uppercase-first alphabetical order — insert at the sorted positions).
- `FlowCollaboration`, `FlowTeamMember`, `FlowAssistant` — source:
  `goga/pipeline/compiler/flow_collaboration.py` / `flow_team_member.py` /
  `flow_assistant.py`; facade obligation: importable from
  `goga.pipeline.compiler`; `__all__` 16 → 19.
- `write_afm_config` — already importable from `goga.pipeline` (`__all__`
  carries it among its 19 names — verified); the signature change is internal;
  NO facade change.

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — the project-wide mandatory
  practice: relative intra-package imports, `kw_only` dataclasses, Google
  docstrings, log levels and structured logging, blank-line block formatting,
  REPL/test infrastructure rules, validation commands. Referenced by the
  manifests' global annotations; applied to every new/changed entity.
  Extracted in full into the Mandatory Rules above.
- `afm` (`.goga/usages/cooks/afm.md`) — the engine's collaboration contract:
  profile shape (`title`, `command` required and non-inheriting, `delegate`),
  stage-helper keys (`profile` required; `mode` advisory|required; `trigger`
  one_shot|checkpoints|on_completion; engine defaults advisory/one_shot),
  team-member keys (`id` `[A-Za-z0-9._-]`, `profile`, `title`, `@assistant`
  reserved), flow-overridable keys (`mode`, `max_depth` only), config-layer
  keys (`profiles`, `limits`), the kill-switch stance. Verified against the
  `v2.0.9` binary in the image — the single authority for the emitted surface.
  Applied via `_GATE_MODE` / `_WHEN_TRIGGER` mappings;
  `collaboration: {mode: assistants}` always (flow is the only layer goga
  authors, precedence flow > project > global); `checkpoints` written
  explicitly because the engine default is `one_shot`; profiles exactly
  `{title, command, delegate}`; `limits.max_tasks` only with a delegation
  block.

### Imported Usages

- `assistants` from `goga/pipeline/workflow` (imported by compiler + pipeline)
  — source path `goga/pipeline/workflow/.usages/assistants.md`; the authoring
  vocabulary: three entry forms, key tables, defaults, the complete
  structural-error table, anti-patterns. The discriminator (`prompt`/`skills`
  presence) and the reference-takes-declaration-fields rule are read from its
  entry-form section. Its error table duplicates the parser messages verbatim
  — if any message is re-worded during implementation, update it in the same
  commit.
- `collaboration-emission` from `goga/pipeline/compiler` (imported by
  pipeline) — source path `goga/pipeline/compiler/.usages/
  collaboration-emission.md`; the compiled flow surface: always-emitted block,
  team table, attachment table, compilation checks. `write_afm_config` reads
  the profile ids exactly from that surface (`flow.team` members and stage
  `assistants` entries).
- `per-stage-env` (cell-level, `goga/pipeline/.usages/per-stage-env.md`) —
  the sh-closure delivery pattern and the new "Assistant env" section (closure
  path becomes the profile command): `#!/bin/sh` + `export` lines + `exec
  target "$@"`, owner-only file, per-launch regeneration. Same mechanism,
  second consumer.
- `resolve-wrapper-path` from `goga/agents` (imported by pipeline) —
  `resolve_wrapper_path`: agent name → in-container wrapper path (pure string
  composition); the single resolution site (contract: "the command resolved
  the stage-agent way") for the client command and every generated profile
  command; the closure path replaces it for env assistants.
- `parse-workflow`, `compile-flow`, `serialize-flow`, `checkpoints`,
  `run-pipeline`, `memory`, `memory-emission`, `profiles`, `load-workflow`
  (imported/declared) — unchanged in role; the collaboration paths follow the
  same patterns they document (extraction normalization, emission companions,
  canonical slots, overlay merge vocabulary). All still referenced by at
  least one annotation (lint-verified).

### Local Usages

None created or updated by this plan. The design's `.usages/` review found
every file already materialized by the apply-architecture stage (verified in
the working tree): NEW `goga/pipeline/workflow/.usages/assistants.md`,
`goga/pipeline/compiler/.usages/collaboration-emission.md`,
`goga/pipeline/.usages/collaboration-delivery.md`; MODIFIED
`parse-workflow.md`, `compile-flow.md`, `serialize-flow.md`,
`checkpoints.md`, `run-pipeline.md`, `per-stage-env.md`. The design stage
confirmed they match the contracts (the `collaboration-emission.md` tables
equal the `_collaboration_emission` mapping; `assistants.md`'s error table
equals the parser catalog; `collaboration-delivery.md`'s profile table equals
`_collaboration_section`). No further `.usages/` change is required by the
code design; the single follow-up note is the same-commit update rule for
re-worded parser messages (see Error Message Catalog).

### External Dependencies

- **afm binary v2.0.9** (in-container) — the collaboration engine; the
  emitted vocabulary (`mode`, `trigger`, `max_depth`, profile shape) is
  verified against it. Three ADR engine assumptions to verify at
  implementation time (Additional Instruction 7): profile ids tolerate
  `goga-<name>`; `limits.max_tasks` follows project > global precedence;
  `max_depth: 0` suppresses helper creation but not team members. Verify by
  `afm validate` on a compiled fixture; record deviations in the topic's
  `todo.md` — do not silently widen the design.
- `pyyaml` (pinned) — `yaml.safe_load` (parser), `yaml.dump` with the custom
  dumper (serializer), `yaml.safe_dump` (config write).
- `shlex` (stdlib) — `shlex.quote` of env values in the closure rendering.
- pytest / pytest-cov / ruff (test extras, pinned) — no new versions required.

## Facts

- The working tree already carries the contract side (verified): the four
  changed CODEMANIFESTs (`workflow`, `compiler`, `hooks`, `pipeline`) declare
  every entity of this plan; `goga lint` is clean over **91 cells / 0 errors**
  on the pre-change tree.
- The `.usages/` files and `docs/features/pipelines/workflows.md` are already
  materialized (apply-architecture artifacts) — no documentation work belongs
  to the implementation stage (Additional Instruction 8).
- `goga/pipeline/workflow/parse_workflow.py` today: `_TOP_LEVEL_KEYS` = 6
  keys (line 18), `_STAGE_KEYS` = 11 keys (line 22), `_extract_top_level`
  returns a 6-tuple (line 143), `_build_stages` (258), `_build_stage` (275),
  `_validate_stage_field` (325, one direct branch per validated field),
  `_validate_stage_env` (841), `_build_memory` (489, the `max_rules`
  bool-counts-as-non-int precedent), the empty rule at ~line 133
  (`prompt is None and not stages and not extend and memory is None and
  build is None`), `_reject_forbidden_extend_keys` (472).
- `WorkflowStage` (`workflow_stage.py`) fields end at `memory: bool | None =
  None`; `WorkflowDocument` (`workflow_document.py`) fields end at
  `build: WorkflowBuild | None = None` — both already `@dataclass(kw_only=True)`
  with `from __future__ import annotations`.
- Facade counts (AST-verified): `goga/pipeline/workflow/__init__.py` `__all__`
  = 16 names; `goga/pipeline/compiler/__init__.py` `__all__` = 16 names;
  `goga/pipeline/__init__.py` `__all__` = 19 names with `write_afm_config`
  present. Facade tests are membership-style (`"name" in facade.__all__`) —
  no count pins to adapt for the two cells; the new contract test files
  assert membership of the new names.
- `compile_flow.py`: `_CANONICAL_KEY_ORDER` (line 58) currently ends
  `... "reflect", "memory_use"`; `_reject_authoring_output_keys` (221);
  `_canonical_fields` (339); `_effective_overrides` (517); `_reconstruct_body`
  (1263) currently returns a 3-tuple; `compile_flow` (1312);
  `_DEFAULT_AGENTS = ("auto",)` (127); `translate_role` (145);
  `_has_usable_roles` (160).
- `serialize_flow.py`: `_BlockLiteralScript` + its representer (53–80),
  `_build_stage_repr` (83), `serialize_flow` (121), top-level emission
  `prompt → root_dir → name → description → memory → stages` (151+).
- `flow_document.py`: 6 fields, `memory: FlowMemory | None = None` before
  `stages: list[FlowStage]` — the two new slots go between them.
- `overlay.py`: `_STAGE_FIELDS` = 11 fields (line 9), `_STAGE_DEFAULTS`
  (24–25, `skip=False`), `_merge_stage` (100), `_merge_memory` (170, the
  whole-block precedent), `merge_workflow_overlay` (238).
- `events.py`: buffer shape guard `for fact in ("prompt", "stages", "extend",
  "memory"):` (150); empty-document condition (164).
- `afm_config.py`: `write_afm_config(agent: str | None) -> Path` (15);
  `_AFM_CONFIG_PATH = Path("/home/goga/.afm/config.yaml")` (11);
  `resolve_wrapper_path` imported from `..agents` (9); the four static fields
  + observer hook already compose the content; `yaml.safe_dump(content,
  default_flow_style=False, sort_keys=False)` (65).
- `run_pipeline.py`: `write_afm_config(config.pipeline.agent)` at line 457;
  import at line 22.
- `apply_skip_stages.py`: the rebuild at lines 60–66 passes exactly six
  fields (prompt/stages/extend/memory/profile/build).
- `stage_env_wrappers.py`: `_KEYS_AFTER_COMMAND` tuple at line 30 (currently
  ends before `memory_use`-equivalent tail anchors; `depends_on` appended at
  use site line 275).
- Tests pinning the old surface (design Additional Instruction 2):
  `tests/pipeline/test_afm_config.py:42` `assert parameters == ["agent"]`;
  the `tests/pipeline/test_run_pipeline.py` fake `_write_afm_config(agent)`
  at ≈ line 1124 and the source-text pin
  `tests/pipeline/test_run_pipeline_contract.py:417`
  (`"write_afm_config(config.pipeline.agent)" in source`); the
  workflow/compiler contract enumerations
  (`test_workflow_stage_contract.py`, `test_workflow_document_contract.py`,
  `test_parse_workflow_contract.py` / `_logic.py`,
  `test_flow_document_contract.py`, `test_compile_flow.py` goldens) and the
  further compiler compiled-output pins — the byte-exact goldens of
  `test_compile_flow_workflow.py:2869` and `test_compile_flow_trigger.py:338`
  and the top-level key-order pins of `test_integration.py:94` and
  `test_integration_roles.py:106/154/194`
  (`list(loaded.keys()) == ["name", "description", "stages"]`).
- Test infrastructure reuse: `is_kw_only_dataclass` (`tests/conftest.py:70`),
  `config_path` (`tests/pipeline/test_afm_config.py:53`),
  `_in_container_run_context` autouse (`tests/pipeline/conftest.py:47`),
  overlay fixtures (`tests/pipeline/hooks/test_overlay.py`), run-pipeline
  wiring fakes (`tests/pipeline/test_run_pipeline.py`).
- No `.venv` exists in the workspace; the system interpreter
  (`/opt/goga/bin/python3`, Python 3.12.16) has no pytest/ruff — Task 1
  bootstraps the environment and verifies the baseline green.
- afm v2.0.9 fact base (`.goga/usages/cooks/afm.md`): engine defaults
  `mode: advisory` / `trigger: one_shot` (never relied upon — goga writes
  both explicitly); profiles `title`/`command` are required and do NOT
  inherit; `delegate` bool; team `id` grammar `[A-Za-z0-9._-]` with
  `@assistant` reserved; flow-overridable keys are `mode` and `max_depth`
  only; config layer `profiles` + `limits`; the kill-switch
  (`collaboration.enabled` / `AFM_COLLABORATION`) exists and is neither read
  nor written by goga.

## Gap Analysis

- **Missing contract entities**: `workflow_assistant.py`,
  `workflow_delegation.py`, `flow_collaboration.py`, `flow_team_member.py`,
  `flow_assistant.py` — all five absent; the parser/compiler/overlay/config
  collaboration paths absent.
- **Missing facade exposure**: workflow `__all__` lacks the two new model
  names (16 → 18); compiler `__all__` lacks the three (16 → 19).
- **API / behavior mismatches vs the contract**: `WorkflowStage` /
  `WorkflowDocument` / `FlowDocument` field sets short; `parse_workflow`
  rejects the new top-level/stage keys (unknown-key errors) and its empty
  rule under-counts; `_extract_top_level` returns a 6-tuple; the compiler
  has no namespace/emission and `_effective_overrides` drops attachments on
  extend-seeded stages (C2.4); the serializer emits neither `collaboration`
  nor `team`; the overlay merge has no assistants/delegation arms and its
  buffer guard misses the two new attributes; `write_afm_config` takes only
  `agent` and writes no `collaboration` section; `run_pipeline` threads
  nothing; `apply_skip_stages` drops the collaboration fields on rebuild;
  `_KEYS_AFTER_COMMAND` lacks `"assistants"`.
- **Existing code reused (not rewritten)**: `_BlockLiteralScript` +
  representer; `_canonical_fields` / canonical-order loop; `translate_role` /
  `_has_usable_roles` / `_DEFAULT_AGENTS`; `_merge_memory` (the whole-block
  precedent); `_validate_stage_env`; `resolve_wrapper_path`; the `config_path`
  fixture and `_AFM_CONFIG_PATH` patch point; the run-pipeline wiring fakes;
  the per-stage-env closure mechanism (re-implemented locally per the
  no-shared-module decision, same content contract).
- **Test coverage gaps**: no assistants/collaboration suites exist (the eight
  new test files of the design); the five model-contract files absent; the
  signature/fake/enumeration adaptations listed in Facts.
- **Out of scope (explicitly untouched)**: `goga/pipeline/__init__.py`
  (facade unchanged); `parse_workflow_memory.py` tests; the platform
  (`goga/hooks`), the catalog, the bridge (`hook_bridge.py`), the CLI, the
  host-side launcher; `docs/` and `.usages/` (already applied); the
  `describe_*`/`list_*` surfaces. No new cells, no new public API beyond the
  five exported types.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before
> starting the next. Package order: `goga/pipeline/workflow` →
> `goga/pipeline/compiler` → `goga/pipeline/hooks` → `goga/pipeline`. Within
> each coding task, contract tests are written first (TDD workflow). Only ONE
> task is executed per ralphex iteration.

### Task 1: Workflow models — `WorkflowAssistant`, `WorkflowDelegation`, stage/document fields, cell facade (TDD coding; bootstraps the environment)

<Context: the leaf cell `goga/pipeline/workflow` (dir `goga/pipeline/workflow/`)
gains its two new data models and the two field extensions, and exports the
new types from the cell facade. Entities: `WorkflowAssistant`
(`workflow_assistant.py`, NEW), `WorkflowDelegation` (`workflow_delegation.py`,
NEW), `WorkflowStage.assistants` (last field), `WorkflowDocument.assistants`
(default empty dict) + `.delegation` (last field) — exact shapes in the
Contract Surface above. They are pure data: `@dataclass(kw_only=True)`, no
validation logic, no methods — the identical idiom as the neighboring models
(`from __future__ import annotations`, Google docstring with one `Args:` entry
per field, the CODEMANIFEST field descriptions as the source text). The facade
`goga/pipeline/workflow/__init__.py` grows `__all__` 16 → 18 (+
`WorkflowAssistant`, `WorkflowDelegation`, alphabetical). This task ALSO
bootstraps the development environment (virtualenv + test extras) — the
workspace has no `.venv` and the system interpreter lacks pytest/ruff.>

**Usages relevant to this task:**
- `convention`: data-model rules (`kw_only=True`, empty defaults, `None` only
  for explicit absence — `delegate=False`, `gate=False`, `when="checkpoints"`,
  `max_tasks=50` are EMPTY defaults; `prompt`/`skills`/`agent`/`env`/`depth`
  are absence-`None`), docstring style, relative imports; the Mandatory Rules
  above apply in full (REPL loop, lint gates, commit policy).
- `assistants` (the cell's own practice, `goga/pipeline/workflow/.usages/
  assistants.md`): the entry-form vocabulary the model carries — one model for
  catalog declaration, inline declaration, and reference; `gate`/`when`
  authored only on attachments.
- `profiles` / `load-workflow` (the cell's own practices): unchanged
  consumers — the facade growth touches neither the profile-source nor the
  loading surface, so both practices stay accurate without edits.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. The contract changes are already applied in the working tree. If
implementation does not match the contract, fix the implementation — never fix
the contract.**

- [x] **STEP 0 (DECLARATION + environment)**: declare this task; bootstrap the
      virtualenv — `python3 -m venv .venv && .venv/bin/pip install -e
      ".[test]"`; verify the BASELINE is green before any change:
      `.venv/bin/ruff check goga/ tests/`, `.venv/bin/ruff format --check
      goga/ tests/`, `.venv/bin/pytest tests/ -x`, `goga lint` (0 errors /
      91 cells; re-run once on a surprising failure — the command is
      occasionally flaky)
- [x] **STEP 1 (Contract tests)**: create
      `tests/pipeline/workflow/test_workflow_assistant_contract.py` and
      `tests/pipeline/workflow/test_workflow_delegation_contract.py` (class
      `TestWorkflowAssistantContract:` / `TestWorkflowDelegationContract:`,
      the house contract pair): both names importable from
      `goga.pipeline.workflow` AND listed in `facade.__all__`; each passes
      `is_kw_only_dataclass` (from `tests.conftest`); `inspect.signature`
      parameter order matches the contract EXACTLY —
      `WorkflowAssistant(name, prompt, skills, agent, delegate, env, gate,
      when)` with defaults `(MISSING, None, None, None, False, None, False,
      "checkpoints")`, `WorkflowDelegation(depth, max_tasks)` with defaults
      `(None, 50)`; field order pinned (dataclass ordering rule). Also extend
      `tests/pipeline/workflow/test_workflow_stage_contract.py` (+ the
      `assistants` field, default `None`, annotation `list[WorkflowAssistant]
      | None`, LAST) and `tests/pipeline/workflow/
      test_workflow_document_contract.py` (+ `assistants` default empty dict,
      `delegation` default `None` last). Expected to fail at this stage —
      this is correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      construct `WorkflowAssistant(name="reviewer")` and confirm every default
      materializes (`prompt is None`, `skills is None`, `delegate is False`,
      `gate is False`, `when == "checkpoints"`), and
      `WorkflowDelegation()` → `(None, 50)`; confirm kw-only rejection of a
      positional call (`TypeError`); then implement: create
      `goga/pipeline/workflow/workflow_assistant.py` and
      `goga/pipeline/workflow/workflow_delegation.py` with the exact
      dataclasses from the Contract Surface (module docstring, `from
      __future__ import annotations`, `from dataclasses import dataclass`,
      Google docstrings documenting every arg: name grammar and uniqueness
      enforced by `parse_workflow`; `gate`/`when` authored only on
      attachments; consumers own resolution and delivery; `depth` `None` when
      absent, an authored `0` is a value; `max_tasks` materializes 50);
      extend `workflow_stage.py` (`assistants: list[WorkflowAssistant] | None
      = None` last + `Args:` entry, importing the type relatively) and
      `workflow_document.py` (`assistants: dict[str, WorkflowAssistant] =
      field(default_factory=dict)` + `delegation: WorkflowDelegation | None =
      None` last + `Args:` entries); update the facade `__init__.py` —
      `from .workflow_assistant import WorkflowAssistant`, `from
      .workflow_delegation import WorkflowDelegation`, `__all__` 16 → 18
      alphabetical
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/workflow/ -v` — all pass; facade checks:
      `.venv/bin/python -c "from goga.pipeline.workflow import
      WorkflowAssistant, WorkflowDelegation"` and `len(__all__) == 18`
- [x] **STEP 4 (Logic tests)**: construction passthrough — build each model
      with keyword arguments and assert every field carries its value
      verbatim; two identical `WorkflowAssistant` constructions compare equal
      (dataclass `__eq__`); a reference-shaped instance
      (`WorkflowAssistant(name="reviewer", gate=True, when="finish")`) keeps
      `prompt is None` (the model never invents declaration fields — the
      discriminator premise)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — the full battery
      stays green (the additive fields default cleanly; any failure is fixed
      in code, never by weakening an unrelated test)
- [x] **STEP 6 (Contract re-verification)**: both models importable from the
      facade and in `__all__` (18); signatures match the CODEMANIFEST exactly;
      `WorkflowStage`/`WorkflowDocument` field sets match the contract order;
      no validation logic added; no other entity touched
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations; fix formatting if necessary
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit with all gates green
      and NO `Co-Authored-By:` trailer → REVIEW → APPROVAL → NEXT TASK

### Task 2: `parse_workflow` — the top-level authoring surfaces: catalog (6.5) + delegation (6.6) (TDD coding)

<Context: the cell `goga/pipeline/workflow` (dir `goga/pipeline/workflow/`)
extends `parse_workflow` in `parse_workflow.py` with the two TOP-LEVEL
authoring surfaces. Changes: `_TOP_LEVEL_KEYS` 6 → 8 (`assistants`,
`delegation` last — the top-level unknown-key message order is pinned);
`_extract_top_level` gains the dispatch arms (`assistants` must be a `list`,
else `non-list assistants block in workflow`; `delegation` must be a `dict`,
else `non-mapping delegation block in workflow`) and returns an **8-tuple**;
`_build_assistant_catalog(raw)` implements contract step 6.5 (per entry:
mapping check → name required/str → unknown-key check against
`("name", "prompt", "skills", "agent", "delegate", "env")` — `gate`/`when`
are UNKNOWN here → per-field validation: `prompt`/`agent` str, `skills`
list[str], `delegate` bool, `env` via `_validate_stage_env` with empty→`None`
→ at-least-one-of-prompt-or-skills → name grammar `[A-Za-z0-9._-]+`
fullmatch + reserved `assistant`; a name repeating WITHIN the catalog raises
`duplicate assistant name: NAME` at build time (a local seen set in the
entry loop — the dict is keyed by name, so the later namespace walk over
`values()` can never see an in-catalog repeat); returns
`dict[str, WorkflowAssistant]` in authored order); `_build_delegation(raw)` implements step 6.6 (key set
{`depth`, `max_tasks`}; `depth` int — bool EXCLUDED like `max_rules` — ≥ 0,
presence-based; `max_tasks` int — bool excluded — ≥ 1; `max_tasks`
materializes to 50 when absent; an empty block is valid). The empty-workflow
rule gains `and not assistants and delegation is None` and the message gains
the two new fragments. `WorkflowDocument(..., assistants=assistants,
delegation=delegation)`. Test home: the new
`tests/pipeline/workflow/test_parse_workflow_assistants.py`.>

**Usages relevant to this task:**
- `convention`: house validator message shapes mirrored from the existing
  validators (`non-list X block`, `non-mapping X block`, `unknown key in
  {scope}: {key}; valid keys: …`, `X must be one of: … in {scope}`); REPL
  loop; lint gates.
- `assistants` (the cell's own practice): the catalog key table and the
  at-least-one rule — the practice's error table duplicates these messages
  verbatim.
- `parse-workflow` (the cell's own practice): the extraction-normalization
  pattern the two new passes follow (raw block → validated model with
  materialized defaults).
- `memory` (the cell's own practice): the `_build_memory` block/defaults
  precedent the delegation pass mirrors (key set, int checks with bool
  excluded, materialized default).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm the Task 1 gates
      are green (the venv exists)
- [x] **STEP 1 (Contract tests)**: in the new
      `tests/pipeline/workflow/test_parse_workflow_assistants.py` (class
      `TestAssistantCatalog:` / `TestDelegationBlock:`): `parse_workflow`
      accepts the two new top-level keys (a workflow carrying both parses);
      an unknown top-level key now yields the EIGHT-key valid-keys message
      (`prompt, stages, extend, memory, profile, build, assistants,
      delegation`); the extended empty-workflow message fires for `{}`;
      extend the enumerations of the existing
      `tests/pipeline/workflow/test_parse_workflow_contract.py` /
      `test_parse_workflow_logic.py` (top-level key set, empty rule — the
      design's Additional Instruction 2; `test_parse_workflow_memory.py`
      stays untouched). Expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      round-trip the design's catalog YAML literal through `yaml.safe_load`
      and confirm the presence-based reads (`skills: []` present-but-empty,
      `env: {}` present-but-empty, `delegation: {}` empty mapping,
      `depth: 0` is an authored int); then implement per the Contract
      Surface: extend `_TOP_LEVEL_KEYS` (message order pinned — assistants,
      delegation LAST); add the module constants
      `_ASSISTANT_CATALOG_KEYS`, `_DELEGATION_KEYS`, `_WHEN_VALUES`,
      `_ASSISTANT_NAME_PATTERN`, `_RESERVED_ASSISTANT_NAME`; extend
      `_extract_top_level` to the 8-tuple with the two dispatch arms; write
      `_build_assistant_catalog` and `_build_delegation` with Google
      docstrings, per-field validation mirrored from the house validators
      (`_build_memory` for the int/bool exclusion, `_validate_stage_env` for
      env), all errors `WorkflowSyntaxError` with the pinned messages; wire
      the passes after the extend pass; extend the empty rule + message;
      thread `assistants=assistants, delegation=delegation` into the returned
      `WorkflowDocument`
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/workflow/test_parse_workflow_assistants.py
      tests/pipeline/workflow/test_parse_workflow_contract.py -v` — pass
- [x] **STEP 4 (Logic tests)**: in `test_parse_workflow_assistants.py`:
      `test_parse_assistants_catalog_full_form_materializes_defaults` — the
      CATALOG half now (the attachment half lands in Task 3): input the
      design's YAML (catalog `reviewer` with agent/delegate/skills/prompt);
      assertions `doc.assistants.keys() == ["reviewer"]` (authored order),
      `doc.assistants["reviewer"].prompt == "Review the stage changes.\n"`,
      `.skills == ["code-audit"]`, `.agent == "claude"`, `.delegate is True`,
      `.env is None`, `.gate is False` (catalog default), `.when ==
      "checkpoints"` (catalog default), `doc.delegation is None`;
      `test_parse_delegation_block_materializes_max_tasks` — `delegation:
      {depth: 3}` (+ one stage) → `(3, 50)`; `delegation: {}` alone →
      `WorkflowDelegation(None, 50)` and the empty rule does NOT fire;
      `max_tasks: 7` → 7; the BOUNDARY row `delegation: {depth: 0}` (+ one
      stage) → `WorkflowDelegation(0, 50)` — an authored zero is a VALUE,
      not an absence (the falsy-zero trap; this is the parse half of the
      design's `test_parse_delegation_depth_zero_survives_to_max_depth_zero`,
      whose compile half lands in Task 6); the NEGATIVE table rows for these surfaces
      (parametrized, exact `match=`): `assistants: {a: 1}` → `non-list
      assistants block in workflow`; `assistants: [x]` → `non-mapping
      assistant entry in workflow.assistants`; `assistants: [{prompt: p}]` →
      `name is required in workflow.assistants entry`; `assistants: [{name:
      r, gate: true}]` and `[{name: r, when: start}]` → the catalog
      unknown-key message with the six-key list; `assistants: [{name: r,
      agent: c}]` → `assistant r requires at least one of prompt or skills`;
      `[{name: "a b", prompt: p}]` → `invalid assistant name: a b`;
      `[{name: assistant, prompt: p}]` → `assistant name is reserved`;
      `[{name: r, prompt: p}, {name: r, prompt: q}]` → `duplicate
      assistant name: r` (the within-catalog repeat — rejected at build
      time by `_build_assistant_catalog`, NOT by the namespace pass);
      house-style (unpinned wording, assert the exception + a stable
      fragment): non-str prompt, non-list-of-str skills, non-bool delegate,
      non-mapping env, non-str env value; `delegation: [1]` → `non-mapping
      delegation block in workflow`; `delegation: {x: 1}` → the two-key
      unknown-key message; `delegation: {depth: -1}` → `depth must be >= 0 in
      workflow.delegation`; `delegation: {depth: true}` → `non-int value in
      workflow.delegation.depth`; `delegation: {max_tasks: 0}` → `max_tasks
      must be >= 1 in workflow.delegation`; `delegation: {max_tasks: true}` →
      `non-int value in workflow.delegation.max_tasks`
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/pipeline/workflow/ -x`
      then the full battery — fix implementation code until all pass (do NOT
      fix test code)
- [x] **STEP 6 (Contract re-verification)**: steps 6.5/6.6 behavior matches
      the CODEMANIFEST annotations (validation-only cell: no resolution, no
      emission); every pinned message byte-exact; the empty rule counts all
      seven content blocks; single-defect files pin exactly one message
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 3: `parse_workflow` — stage attachments (6.7), extend prohibition (6.8), document-wide namespace (TDD coding)

<Context: the cell `goga/pipeline/workflow` (dir `goga/pipeline/workflow/`)
completes the parser: the PER-STAGE attachment grammar, the extend-entry
prohibition, and the duplicate-name pass. Changes: `_STAGE_KEYS` 11 → 12
(`assistants` last — the stage unknown-key message order is pinned);
`_validate_stage_field` gains the `assistants` arm dispatching to
`_build_stage_assistants(name, value)` (non-list → pinned message; empty →
`None`; per element `_build_attachment_entry`); the THREE entry forms of
6.7 (bare str reference → `WorkflowAssistant(name=element)` with all
defaults; dict with keys ⊆ {name, gate, when} → reference with overrides:
name required+str, gate bool, when domain; any other dict → full inline
declaration: unknown-key check against the eight-key
`_ATTACHMENT_DECLARATION_KEYS`, catalog per-field rules, gate bool, when
domain, at-least-one-of prompt/skills, name rules); non-str non-dict →
pinned message; `_reject_forbidden_extend_keys` tuple gains `"assistants"`
(appended last); `_validate_assistant_namespace(assistants, stages)` walks
the catalog then every stage DECLARATION (the discriminator `prompt is not
None or skills is not None`) in stage/attachment order — the second
occurrence of a name raises `duplicate assistant name: NAME`; references
never count. Scope note: the catalog-INTERNAL repeat was already rejected
at build time (Task 2), so this pass covers exactly the two remaining
collision kinds — catalog ↔ inline declaration and inline ↔ inline
(across stages and within one stage list). Test home: extend
`tests/pipeline/workflow/test_parse_workflow_assistants.py`.>

**Usages relevant to this task:**
- `convention`: house validator message shapes; the per-field scoping
  precedent (`approve must be one of: … in {scope}`) behind the
  entry-scoped attachment errors; REPL loop; lint gates.
- `assistants` (the cell's own practice): the three entry forms, the
  attachment key table (`name, prompt, skills, agent, delegate, env, gate,
  when`), and the "no attachments in extend" anti-pattern.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Task 2 gates green
- [x] **STEP 1 (Contract tests)**: in
      `tests/pipeline/workflow/test_parse_workflow_assistants.py` (class
      `TestStageAttachments:`): a stage carrying `assistants:` parses into
      `doc.stages[name].assistants`; an unknown STAGE key now yields the
      twelve-key valid-keys message (`agent, env, prompt, loop, skills,
      skip, approve, manual, notes, reflect, memory, assistants`);
      `assistants` on an extend-entry raises the pinned prohibition.
      Expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      feed the three entry-form elements through the dict/str shape checks
      and confirm the discriminator premise (`{"name": "x", "gate": True}`
      is a reference-with-overrides because `prompt`/`skills` are both
      ABSENT; `{"name": "x", "skills": []}` IS a declaration because
      `skills` is PRESENT though empty); then implement per the Contract
      Surface: extend `_STAGE_KEYS`; add
      `_ATTACHMENT_DECLARATION_KEYS = _ASSISTANT_CATALOG_KEYS + ("gate",
      "when")`; write `_build_stage_assistants`, `_build_attachment_entry`,
      `_validate_assistant_name`, `_validate_assistant_namespace` (the
      private `_is_declaration` one-liner — identity check, never
      truthiness); append `"assistants"` to the forbidden-extend tuple; wire
      the namespace pass LAST (after the catalog/delegation passes — it
      needs the catalog); keep the deterministic pass order (stage
      attachments validate inside the stage pass; single-defect files pin
      exactly one message)
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/workflow/ -v` — all pass, including the Task 2 suites
- [x] **STEP 4 (Logic tests)**: in `test_parse_workflow_assistants.py`:
      `test_parse_attachment_three_entry_forms` (design, verbatim) — input
      the design's YAML (bare `reviewer`; `{name: reviewer2, gate: true}`;
      `{name: security, agent: codex, prompt: Audit., when: start}` with a
      catalog declaring `reviewer`, `reviewer2`); assertions
      `[(a.name, a.gate, a.when, a.prompt) for a in
      doc.stages["build"].assistants] == [("reviewer", False, "checkpoints",
      None), ("reviewer2", True, "checkpoints", None), ("security", False,
      "start", "Audit.")]`; extend
      `test_parse_assistants_catalog_full_form_materializes_defaults` with
      its ATTACHMENT half (the design's full input: the stage reference
      `reviewer` with `gate: true, when: finish`) — assert
      `doc.stages["build"].assistants[0].gate is True` and `.prompt is None`
      (attachment overrides do not leak into the catalog object); the
      NEGATIVE table rows (parametrized, exact `match=`): `stages: {b:
      {assistants: {}}}` → `non-list assistants in workflow.stages.b`;
      `assistants: [42]` → `invalid assistant entry in
      workflow.stages.b.assistants`; `[{gate: true}]` → `name is required in
      workflow.stages.b.assistants entry`; `[{name: r, prompt: p,
      bogus: 1}]` → the eight-key unknown-key message scoped
      `workflow.stages.b.assistants.r`; `[{name: r, when: later}]` → `when
      must be one of: start, checkpoints, finish in
      workflow.stages.b.assistants.r`; `[{name: r, gate: "x"}]` →
      `non-bool value in workflow.stages.b.assistants.r.gate`; `extend: {n:
      {assistants: [], before: [b]}}` → `assistants is forbidden in
      workflow.extend.n`; catalog `r` + stage DECLARATION `r` → `duplicate
      assistant name: r`; EDGE tests (design, verbatim):
      `test_parse_assistants_only_workflow_is_valid` (`assistants:
      [{name: r, prompt: p}]` alone parses),
      `test_parse_delegation_only_workflow_is_valid` (covered in Task 2),
      `test_parse_empty_assistants_list_equals_absence` — `stages: {b:
      {assistants: []}}` → `doc.stages["b"].assistants is None`; top-level
      `assistants: []` → empty dict AND does not rescue an otherwise-empty
      workflow (the extended empty message fires);
      `test_parse_empty_env_and_empty_skills_forms` — declaration with
      `env: {}` → `env is None`; declaration with `skills: []` + no prompt →
      still a declaration (presence rule) and passes at-least-one; a
      duplicate REFERENCE on one stage list is legal at parse time (two
      identical bare-string entries parse — the compiler owns the
      per-stage duplicate check)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix
      implementation code until all pass
- [x] **STEP 6 (Contract re-verification)**: steps 6.7/6.8 + the namespace
      pass match the CODEMANIFEST annotations; the namespace is
      document-wide (a skipped stage's declaration still counts — skip is a
      compiler concept); references may repeat names freely; every pinned
      message byte-exact
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 4: Compiler models — `FlowCollaboration`, `FlowTeamMember`, `FlowAssistant`, `FlowDocument` slots, cell facade (TDD coding)

<Context: the cell `goga/pipeline/compiler` (dir `goga/pipeline/compiler/`)
gains its three emission models and the `FlowDocument` field extension, and
exports the new types. Entities: `FlowCollaboration`
(`flow_collaboration.py`, NEW — `mode: str = "assistants"`, `max_depth: int |
None = None`), `FlowTeamMember` (`flow_team_member.py`, NEW — `id`, `title`,
`profile`, `instruction`, `skills` in emission order), `FlowAssistant`
(`flow_assistant.py`, NEW — `profile`, `title`, `instruction`, `mode`,
`trigger`, `skills`) — exact dataclasses in the Contract Surface. `FlowDocument`
(`flow_document.py`) gains `collaboration: FlowCollaboration | None = None`
and `team: list[FlowTeamMember] | None = None` BETWEEN `memory` and `stages`
(field order IS the emission order); `FlowStage` (`flow_stage.py`) gains the
canonical `assistants` slot in its `fields` docstring contract (after
`memory_use`). Facade `goga/pipeline/compiler/__init__.py` `__all__` 16 → 19
(+ `FlowAssistant`, `FlowCollaboration`, `FlowTeamMember`, alphabetical).>

**Usages relevant to this task:**
- `convention`: data-model rules (kw-only, emission-order fields, `skills`
  as `list[str]` NOT `list[str] | None` — the emission materializes `[]`),
  docstring style, relative imports; the Mandatory Rules in full.
- `afm` (`.goga/usages/cooks/afm.md`): the emitted vocabulary the models
  carry — `mode` advisory|required, `trigger`
  one_shot|checkpoints|on_completion, team-member keys (`id` grammar,
  `profile`, `title`), profile binding `goga-<name>`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Tasks 1–3 gates
      green (the workflow types exist for the docstring cross-references)
- [x] **STEP 1 (Contract tests)**: create
      `tests/pipeline/compiler/test_flow_collaboration_contract.py`,
      `test_flow_team_member_contract.py`,
      `test_flow_assistant_contract.py`: the three names importable from
      `goga.pipeline.compiler` AND in `facade.__all__`; each passes
      `is_kw_only_dataclass`; `inspect.signature` parameter order matches
      the contract exactly (`FlowCollaboration(mode, max_depth)` defaults
      `("assistants", None)`; `FlowTeamMember(id, title, profile,
      instruction, skills)` all required; `FlowAssistant(profile, title,
      instruction, mode, trigger, skills)` all required); extend
      `tests/pipeline/compiler/test_flow_document_contract.py` — the
      signature carries `collaboration` and `team` between `memory` and
      `stages`, defaults `None`/`None`; extend the existing
      `tests/pipeline/compiler/test_data_models.py` with the three new
      models (the suite's own per-model pattern). Expected to fail —
      correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      construct `FlowCollaboration()` and confirm `("assistants", None)`;
      construct a `FlowTeamMember` and `FlowAssistant` with keyword
      arguments; construct a `FlowDocument(name=..., description=...,
      collaboration=..., team=..., stages=[])` and confirm the field order;
      then implement the three model files (the Contract Surface dataclasses
      verbatim, house idiom, Google docstrings documenting every field per
      the CODEMANIFEST descriptions); extend `flow_document.py` (two fields
      between `memory` and `stages` + `Args:` entries + the "up to eight
      top-level keys" docstring update + relative imports); extend the
      `flow_stage.py` fields docstring with the canonical `assistants` slot
      after `memory_use`; update the facade `__init__.py` `__all__` 16 → 19
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/compiler/ -v` — all pass; facade check:
      `.venv/bin/python -c "from goga.pipeline.compiler import
      FlowAssistant, FlowCollaboration, FlowTeamMember"`
- [x] **STEP 4 (Logic tests)**: construction passthrough for each model;
      `FlowCollaboration` default materialization (`mode == "assistants"`);
      equality of identical constructions; `FlowDocument` default carries
      `collaboration=None` / `team=None` (omission semantics — the
      serializer keys on these)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — the full
      battery stays green (the additive slots default cleanly; existing
      `FlowDocument` constructions keep working)
- [x] **STEP 6 (Contract re-verification)**: three models on the facade
      (19 names); field order matches the emission order;
      `FlowDocument`'s eight-key contract; `FlowStage` docstring carries
      the canonical slot
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 5: `serialize_flow` — the collaboration block, team list, stage assistant entries (TDD coding)

<Context: the cell `goga/pipeline/compiler` (dir `goga/pipeline/compiler/`)
extends `serialize_flow` in `serialize_flow.py` with the three emission
surfaces — exact algorithm in the Contract Surface. Top level: after
`memory`, `collaboration` (when not `None`: block mapping, key order
`mode, max_depth`, `max_depth` OMITTED when `None` — the omission rule is
`is None`, never truthiness) then `team` (when non-empty: block list; each
member the ordered mapping `id, title, profile, instruction, skills`;
`instruction` wrapped in `_BlockLiteralScript` iff it contains `\n`;
`skills` a plain list, `[]` when empty) then `stages`. Stage fields: in
`_build_stage_repr`, the `assistants` value (a `list[FlowAssistant]`)
becomes a list of ordered mappings `profile, title, instruction, mode,
trigger, skills` with the same instruction wrapping. NO new representer —
`yaml.dump(default_flow_style=False)` already renders empty lists as `[]`
(the `depends_on: []` precedent) and mappings as block style; the existing
`_BlockLiteralScript` representer is REUSED. Test home: the new
`tests/pipeline/compiler/test_serialize_flow_collaboration.py`.>

**Usages relevant to this task:**
- `afm`: the flow-file key vocabulary and the flow-overridable keys (`mode`,
  `max_depth` only) — the block shape the engine parses.
- `beautiful_yaml` (`.goga/usages/cooks/beautiful_yaml.md`): the
  serializer's parameter set (`sort_keys=False, default_flow_style=False,
  allow_unicode=True, indent=2`) — the new `collaboration` / `team` /
  stage-assistants arms reuse it unchanged; NO new representer, the
  existing `_BlockLiteralScript` representer is reused.
- `convention`: golden tests are grounded in a REAL `yaml.dump` run — the
  design's layout note (verified with the serializer's exact parameters
  `indent=2`, `default_flow_style=False`): a list item's dash sits at the
  PARENT key's indentation (column 0 under a top-level `team:`, column 2
  under a stage's `assistants:`), the item's own keys at dash-indent + 2,
  and a nested list's items at the KEY's indentation — never indented under
  their key. Do NOT "fix" the indentation by altering the dumper (that
  would break byte-identity with the existing stage rendering).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Task 4 gates
      green
- [x] **STEP 1 (Contract tests)**: in the new
      `tests/pipeline/compiler/test_serialize_flow_collaboration.py`:
      `serialize_flow` on a `FlowDocument` with `collaboration=FlowCollaboration()`
      emits the `collaboration:` block and omits `max_depth` when `None`; a
      `team` list emits the `team:` block; `collaboration=None`/`team=None`/
      `team=[]` omit the keys entirely (byte-identity for old documents).
      Expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      build the design's hand-built `FlowDocument` (a multi-line team
      instruction, an assistant with `skills=[]` and `instruction=""`) and
      render `yaml.dump(..., Dumper=_CanonicalDumper, sort_keys=False,
      default_flow_style=False, allow_unicode=True, indent=2)` (the
      serializer's exact call shape) to CONFIRM the golden fragments below
      BEFORE writing them into tests;
      then implement per the Contract Surface: the `collaboration` /
      `team` arms in the top-level emission (between `memory` and
      `stages`), the private `_member_repr(m)`, and the `assistants` arm in
      `_build_stage_repr`
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/compiler/test_serialize_flow_collaboration.py
      tests/pipeline/compiler/test_serialize_flow.py -v` — pass (the
      existing serializer suites stay green: old documents are unchanged)
- [x] **STEP 4 (Logic tests)**:
      `test_serialize_collaboration_styles` (design, verbatim) — input: a
      hand-built `FlowDocument` with a multi-line team instruction and an
      assistant whose `skills` is `[]` and `instruction` is `""`; assertions
      (exact goldens): the multi-line member's `instruction:` renders as a
      block literal (`|`); `skills: []` renders as the explicit empty list;
      the empty instruction renders as `''` (plain scalar); key orders
      `mode → max_depth`; `id → title → profile → instruction → skills`;
      `profile → title → instruction → mode → trigger → skills`;
      `max_depth: 0` is KEPT (the `is None` omission rule — the falsy-zero
      trap); `team=[]` omits the `team:` key
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix
      implementation code until all pass
- [x] **STEP 6 (Contract re-verification)**: emission order and key orders
      match the CODEMANIFEST serialize annotations; no representer added;
      no reordering of existing keys; canonical output with a single
      trailing newline
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 6: `compile_flow` — collaboration emission, steps 4.10 / 5 / 6 (TDD coding)

<Context: the cell `goga/pipeline/compiler` (dir `goga/pipeline/compiler/`)
implements the emission itself in `compile_flow.py` — the full algorithm is
in the Contract Surface (`_PROFILE_PREFIX`, `_GATE_MODE`, `_WHEN_TRIGGER`,
`_is_assistant_declaration`, `_assistant_namespace`, the private
`_CollaborationEmission` dataclass (`block`, `team`, `assistants_by_id`),
`_collaboration_emission`, and the assembly wiring). THE THREE MANDATORY
TOUCH POINTS: (a) `_effective_overrides` merged branch gains
`assistants=stg.assistants` (approved decision 5 — without it a stage with
BOTH an extend-entry and a stages-block entry loses its attachments);
(b) `_CANONICAL_KEY_ORDER` gains `"assistants"` LAST and `_canonical_fields`
gains the `assistants_fields` argument with `_assemble_assistants` assigning
the list into the rebuilt fields BEFORE the canonical-order loop (None/empty
assembles no key); (c) `_reject_authoring_output_keys` gains the
`assistants` prohibition (`assistants key is forbidden in stage body; use
assistants in workflow.stages`). `_reconstruct_body` returns the emission as
a FOURTH value; workflow-less compiles construct the default emission
(`FlowCollaboration("assistants", None)`, `team=[]`, `assistants_by_id={}`
— `FlowDocument` then always carries the block). Test home: the new
`tests/pipeline/compiler/test_compile_flow_collaboration.py`; the byte
counts of `tests/pipeline/compiler/test_compile_flow.py` goldens gain the
two-line block deliberately.>

**Usages relevant to this task:**
- `assistants` (imported from `goga/pipeline/workflow/.usages/assistants.md`):
  the entry-form semantics — the discriminator (`prompt`/`skills` presence)
  and the reference-takes-declaration-fields rule.
- `afm`: the emitted vocabularies — `_GATE_MODE {True: "required", False:
  "advisory"}`, `_WHEN_TRIGGER {start: "one_shot", checkpoints:
  "checkpoints", finish: "on_completion"}`; `checkpoints` written explicitly
  because the engine default is `one_shot`; profile binding `goga-<name>`.
- `compile-flow` / `serialize-flow` / `memory-emission` (the cell's own
  practices): the emission-companion and canonical-slot patterns the new
  code follows.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Tasks 1–5 gates
      green (the serializer already renders the new keys)
- [x] **STEP 1 (Contract tests)**: in the new
      `tests/pipeline/compiler/test_compile_flow_collaboration.py`:
      `compile_flow` accepts a workflow carrying the new blocks (no
      `StructuralError`); the returned `FlowDocument` carries
      `collaboration` on EVERY compile (workflow-less included); a stage
      body authored with `assistants:` raises the pinned prohibition.
      Expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL with
      a scratch namespace/attachment pair — confirm a REFERENCE resolves to
      the namespace entry's declaration fields while keeping its own
      `gate`/`when`, and that `[translate_role(r) for r in ["planner"]] ==
      ["planning"]` (the translated comparison); then implement per the
      Contract Surface: the module literals, `_is_assistant_declaration`
      (private one-liner), `_assistant_namespace`, `_CollaborationEmission`,
      `_collaboration_emission` (the four checks in CONTRACT ORDER per
      entry: unknown reference → duplicate in one stage list → body carries
      `script` → translated agents exactly `["planning"]`, computed as
      `[translate_role(r) for r in roles]` when `_has_usable_roles(body)`
      else `list(_DEFAULT_AGENTS)`; the `FlowAssistant` list built once per
      base stage, mapped onto every produced id); apply touch points (a)
      (b) (c); `_reconstruct_body` returns the 4-tuple; step 6 assembles
      `FlowDocument(..., collaboration=emission.block, team=emission.team,
      ...)`; byte-stable: the compiler logs nothing new
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/compiler/test_compile_flow_collaboration.py -v` — the
      contract class passes; facade check unchanged (no new exports)
- [x] **STEP 4 (Logic tests)**: in
      `test_compile_flow_collaboration.py` (compile tests write a
      pipeline-file + optional workflow-file into `tmp_path`, build the
      `WorkflowDocument` via `parse_workflow`, call `compile_flow`, assert
      on the returned `FlowDocument` AND the written flow-file text):
      `test_compile_collaboration_block_always_emitted` (design, verbatim)
      — `workflow=None`; assertions on the written text:
      `"collaboration:\n  mode: assistants\n" in text`, `"max_depth" not in
      text`, `"team:" not in text`, and the remainder byte-identical to the
      pre-change golden except that block (remove the two lines and
      compare); `test_compile_team_and_stage_attachments_full_
      materialization` (design, verbatim) — catalog `reviewer`
      (prompt/skills), delegation depth 2, stage `build` attaches `reviewer`
      with `gate: true, when: finish`; assertions (flow-file text):
      the team block `"- id: reviewer\n  title: reviewer\n  profile:
      goga-reviewer\n  instruction: Review.\n  skills:\n  - code-audit\n"`;
      the stage block contains `"  assistants:\n  - profile:
      goga-reviewer\n    title: reviewer\n    instruction: Review.\n
      mode: required\n    trigger: on_completion\n    skills:\n    -
      code-audit\n"` after the memory/reflect slots; `"max_depth: 2"`
      present; and `flow_doc.stages[i].fields["assistants"][0].trigger ==
      "on_completion"`; `test_compile_attachments_uniform_across_loop_
      copies` — stage `build` with `loop: 3` and one attachment; all three
      serialized stage blocks carry IDENTICAL `assistants:` entries and the
      flow references `goga-<name>` three times (one profile still — the
      config side collapses); `test_compile_collaboration_free_workflow_
      byte_identical_except_mode` — an existing golden pipeline+workflow
      pair without collaboration: the serialized output equals the stored
      golden with exactly the `collaboration:\n  mode: assistants\n` block
      inserted after `description`/`memory`; `test_compile_reference_to_
      inline_declaration_of_another_stage` — stage `a` declares `security`
      inline, stage `b` references it; both stages carry `goga-security`
      entries taking the declaration's prompt/skills; NEGATIVE:
      `test_compile_unknown_reference_raises` (stage attaches `"ghost"`; no
      catalog/declaration → `StructuralError`, `match="unknown assistant
      reference in workflow.stages.build: ghost"`),
      `test_compile_duplicate_same_stage_raises` (`assistants: [reviewer,
      reviewer]` on one stage; also the reference + declaration variant →
      `duplicate assistant in workflow.stages.build: reviewer`),
      `test_compile_script_and_planning_only_rejected` (stage body with
      `script: echo hi` + attachment → `assistant is forbidden on a script
      stage in workflow.stages.build: r`; `roles: [planner]` + attachment →
      the planning-only message; ALSO `roles: [planning]` authored directly
      — the same message, proving the translated comparison),
      `test_compile_authored_assistants_key_in_stage_body_rejected`
      (pipeline-file stage body carrying `assistants: [...]` directly →
      `assistants key is forbidden in stage body; use assistants in
      workflow.stages`); EDGE: `test_parse_delegation_depth_zero_survives_
      to_max_depth_zero` (design, verbatim — the parse half ran in Task 2;
      HERE the compile half): compile with the `depth: 0` workflow →
      `FlowCollaboration(max_depth=0)` and the flow-file text contains
      `max_depth: 0` inside the collaboration block (the falsy-zero trap —
      a truthiness check anywhere would silently drop the authored bound);
      extend-with-attachments case pinning touch point (a): a stage with an
      extend-ENTRY and a stages-BLOCK entry carrying attachments keeps its
      `assistants` (the C2.4 regression guard)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/pipeline/compiler/ -x`
      then the full battery — the `test_compile_flow.py` goldens gain the
      two-line block deliberately (regenerate deliberately and keep the
      byte-identity assertion; live run wins over a stale golden — report
      the disagreement); the same deliberate adaptation covers the other
      compiler old-surface pins — the byte-exact goldens of
      `test_compile_flow_workflow.py` (≈ 2869) and `test_compile_flow_trigger.py`
      (≈ 338) and the top-level key-order pins of `test_integration.py` (94)
      and `test_integration_roles.py` (106/154/194), which gain
      `"collaboration"` between `description` and `stages`
- [x] **STEP 6 (Contract re-verification)**: steps 4.10/5/6 match the
      CODEMANIFEST annotations; the four checks fire in contract order;
      `PipelineDocument` and the source bodies stay untouched; attachments
      ride the `effective` map, NEVER the step bodies; the emission is
      byte-stable (no logging)
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations (watch the mccabe ceiling on `_collaboration_emission` —
      decompose per the house style rather than `# noqa`)
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 7: Hooks — `merge_workflow_overlay` steps 4a / 4b / 5a + `amend_workflow` vocabulary (TDD coding)

<Context: the cell `goga/pipeline/hooks` (dir `goga/pipeline/hooks/`)
teaches the overlay merge the collaboration fields. Changes in `overlay.py`:
`_STAGE_FIELDS` 11 → 12 (`assistants` last; `_STAGE_DEFAULTS` keeps it
`None`); the private `_is_assistant_declaration` one-liner (the same rule as
the compiler's); `merge_workflow_overlay` gains the namespace seed (authored
catalog names ∪ inline-declaration names of authored stage entries),
`_merge_catalog` (authored wins via the seed; later contribution OVERWRITES
an earlier one per fresh name; then `namespace |= merged.keys()`),
`_merge_delegation` (whole-block, the `_merge_memory` precedent: authored
when present, else the last contribution carrying a block wins, no field
merging), and `_merge_stage_assistants` inside `_merge_stage` (the
field-set-complete loop SKIPS `assistants` per the contract carve-out;
authored list verbatim; contributions append in enumeration order with the
on-stage dedup, the namespace rule for appended DECLARATIONS only, the
evolving namespace, empty result → `None`); the rebuilt `WorkflowDocument`
carries `assistants` and `delegation`; inputs never mutated; every collision
a SILENT drop. Changes in `events.py`: the buffer shape guard tuple (line
150) gains `"assistants"` and `"delegation"`; the empty-document condition
(line 164) gains `not document.assistants and document.delegation is None`.
The cross-kind collision outcome is PINNED (see Contract Surface). Test
home: the new `tests/pipeline/hooks/test_overlay_assistants.py`.>

**Usages relevant to this task:**
- `checkpoints` (the zone's own practice, `goga/pipeline/hooks/.usages/
  checkpoints.md`): the amendment loop that buffers the contributions — the
  merge is its commit phase.
- `assistants` (imported from `goga/pipeline/workflow`): the entry-form
  vocabulary — the declaration discriminator drives both the namespace seed
  and the append rules.
- `convention`: pure-logic tests WITHOUT mocks; the overlay fixtures of
  `tests/pipeline/hooks/test_overlay.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Tasks 1–6 gates
      green
- [x] **STEP 1 (Contract tests)**: in the new
      `tests/pipeline/hooks/test_overlay_assistants.py`: a base document
      carrying `assistants`/`delegation` merges with contributions carrying
      the same fields; `contributions=[]` is the unchanged passthrough (the
      same object returns); a duck-typed buffer missing the new attributes
      is caught by the guard inside the per-hook intercept (an
      `AttributeError` never escapes to `merge_workflow_overlay`).
      Expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      drive one merge quadruple (base + two contributions carrying catalog
      entries and stage declarations) against a scratch implementation of
      the drop/overwrite rules and confirm the pinned outcomes BEFORE
      writing the source; then implement per the Contract Surface:
      `_STAGE_FIELDS` + the merge arms in `overlay.py` (namespace seed →
      catalog → delegation → stages threading the namespace → the rebuilt
      `WorkflowDocument`); the guard tuple + empty condition in
      `events.py`
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/hooks/ -v` — all pass (the existing overlay suites
      stay green: contribution-free and collaboration-free documents are
      unaffected)
- [x] **STEP 4 (Logic tests)**: in `test_overlay_assistants.py` (construct
      base/contribution documents, call `merge_workflow_overlay`, assert
      the rebuilt document):
      `test_overlay_catalog_merge_later_tool_wins_and_namespace_drop`
      (design, verbatim) — base catalog `{reviewer}`; contribution A
      catalog `{reviewer, qa}`; contribution B catalog `{reviewer, qa,
      ops}`; assertions `merged.assistants.keys() == ["reviewer", "qa",
      "ops"]` and `merged.assistants["qa"] is B's entry object`;
      `test_overlay_stage_assistants_append_with_dedup` (design, verbatim)
      — authored stage `build` attaches `[reviewer(gate=true)]`; tool 1
      attaches `[reviewer, security(decl)]`; tool 2 attaches
      `[security(decl), audit(ref)]`; assertions: stage list names in order
      `["reviewer", "security", "audit"]`; the merged namespace has each
      name once; references are dropped ONLY by the on-stage rule, never
      by the namespace rule; an authored inline declaration on another
      stage blocks a tool's same-name declaration (a sibling scenario);
      `test_overlay_catalog_entry_displaces_earlier_inline_declaration`
      (design, verbatim — the pinned cross-kind collision): contribution A
      appends an inline declaration `sec` (prompt authored) to stage
      `build`; contribution B carries a catalog entry `sec`; no authored
      collaboration content; assertions `merged.assistants.keys() ==
      ["sec"]`, `merged.assistants["sec"] is B's entry object`,
      `merged.stages["build"].assistants is None` (the declaration was
      dropped — the assistant no longer attaches to the stage), and the
      merged namespace carries `sec` exactly once;
      `test_overlay_passthrough_unchanged_and_no_contributions` (design,
      verbatim) — base with collaboration fields, `contributions=[]` → the
      same object returns (passthrough); with contributions, the same
      inline name contributed to two stages keeps the namespace
      duplicate-free; the delegation arms: authored block unbeatable; the
      last contribution carrying a block wins; a delegation-ONLY
      contribution is content (not a no-op) and reaches the merge
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix
      implementation code until all pass
- [x] **STEP 6 (Contract re-verification)**: the assistant-namespace
      invariant holds on every path (each name exactly once in the merged
      namespace); no-raise (silent drops); inputs never mutated; the merged
      document is a valid `WorkflowDocument` (compilable — exactly what
      `compile_flow`'s step 4.10 assumes); the buffer guard fires inside
      the per-hook intercept
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 8: `write_afm_config` — collaboration plumbing: profiles, env closures, limits (TDD coding)

<Context: the cell `goga/pipeline` (dir `goga/pipeline/`) REPLACES
`write_afm_config` in `afm_config.py` with the three-argument form
(`agent: str | None, flow: FlowDocument | None = None, workflow:
WorkflowDocument | None = None`) — the full algorithm is in the Contract
Surface (the `_CLOSURE_BASE` / `_LEGAL_ENV_NAME_PATTERN` / `_PROFILE_PREFIX`
module literals, the private `_collaboration_section`, `_render_closure`,
`_write_owner_only` helpers — implemented LOCALLY, no cross-module private
import). THE BINDING ORDER: resolve EVERYTHING in memory first (step 3 —
both pre-run `ValueError`s), THEN materialize closures (step 4), THEN write
the whole file — the "before any file is written" guarantee. The base
content (client block, four static fields, observer hook) is unchanged; the
`collaboration` section is appended only when BOTH `flow` and `workflow` are
not `None`. The signature test at `tests/pipeline/test_afm_config.py:42`
MUST be adapted in the same change (`["agent"]` → `["agent", "flow",
"workflow"]` with `None` defaults). Test home: the new
`tests/pipeline/test_afm_config_collaboration.py` (uses the `config_path`
fixture; patches `_CLOSURE_BASE` into `tmp_path` likewise; builds
`FlowDocument`/`WorkflowDocument` in memory).>

**Usages relevant to this task:**
- `afm` (`.goga/usages/cooks/afm.md`): the config-layer collaboration
  contract — `profiles` (`title`, `command` required and non-inheriting,
  `delegate`), `limits` (`max_tasks`), the kill-switch stance (never read,
  never written), profile-id layering (`goga-` prefix is goga's channel;
  the project layer `.afm/config.yaml` is the user's override channel —
  never touched).
- `collaboration-emission` (imported from
  `goga/pipeline/compiler/.usages/collaboration-emission.md`): the compiled
  flow surface the profile ids are read from (`flow.team` members + stage
  `assistants` entries) — the single source of truth.
- `per-stage-env` (the cell's own practice,
  `goga/pipeline/.usages/per-stage-env.md`): the sh-closure delivery
  pattern and its "Assistant env" section — same mechanism, second
  consumer; the closure path BECOMES the profile command.
- `resolve-wrapper-path` (imported from `goga/agents`): the single command
  resolution site for the client and the plain assistants.
- `convention`: file I/O tests use `tmp_path` exclusively; structured
  logging (one `logger.info` after the write — never env values, never
  commands).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task; confirm Tasks 1–7 gates
      green
- [ ] **STEP 1 (Contract tests)**: adapt the signature test of
      `tests/pipeline/test_afm_config.py` —
      `test_write_afm_config_signature_matches_contract`:
      `parameters == ["agent", "flow", "workflow"]`,
      both new parameters default `None`, `agent` keeps no default, the
      return annotation stays `Path`; add to the new
      `tests/pipeline/test_afm_config_collaboration.py`: `write_afm_config`
      importable from `goga.pipeline` (already), and the collaboration
      section appears only when both `flow` and `workflow` are given (a
      `flow`-less or `workflow`-less call writes the OLD content shape —
      no `collaboration` key). Expected to fail — correct
- [ ] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      call `write_afm_config("claude", flow, workflow)` with
      `_AFM_CONFIG_PATH` and `_CLOSURE_BASE` redirected into a tmp dir,
      `yaml.safe_load` the file back, and `stat()` the closure; confirm the
      profile shape (exactly three keys), the `0o700` mode, and the exact
      closure text; then implement per the Contract Surface: the module
      literals; the private `_is_assistant_declaration` one-liner (the same
      identity-presence rule as the compiler's and the hooks' — design
      decision 2; private to `afm_config.py`, no shared module) that drives
      the namespace walk; the `_collaboration_section` steps 1–5
      (ordered-unique names from the flow; the namespace with sites; the
      in-memory
      resolution loop with the two pre-run `ValueError`s and the env-key
      `fullmatch`; the closure materialization with
      `_CLOSURE_BASE.mkdir(parents=True, exist_ok, mode=0o700)` +
      `chmod(0o700)` and `_write_owner_only` per closure; the profiles dict
      with exactly three keys; `limits` only with a delegation block); the
      `write_afm_config` rewrite threading the section; extend the
      docstring (`Args:` for the two new parameters, `Raises:` for the
      three `ValueError` conditions); ONE `logger.info("wrote afm
      collaboration plumbing", extra={...profile count / has-limits...})`
      after the write — no env values, no commands
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/test_afm_config.py
      tests/pipeline/test_afm_config_collaboration.py -v` — the adapted
      signature test and the existing with/without-agent tests pass;
      facade check `.venv/bin/python -c "from goga.pipeline import
      write_afm_config"`
- [ ] **STEP 4 (Logic tests)**: in `test_afm_config_collaboration.py`
      (parsed YAML at the patched path):
      `test_afm_config_profiles_exactly_for_referenced_ids` (design,
      verbatim) — flow with team `[reviewer]` + stage attachment
      `goga-reviewer` + stage attachment `goga-security` (security declared
      inline, attached on a stage); workflow catalog `{reviewer}`, inline
      `security`; `agent="claude"`; assertions:
      `config["collaboration"]["profiles"].keys() == ["goga-reviewer",
      "goga-security"]` (dedup: team first, then stage entries); each
      profile `== {"title": <name>, "command":
      "/home/goga/bin/<agent>-as-claude.sh", "delegate": <bool>}`;
      `"limits" not in config["collaboration"]` (no delegation block);
      `config["client"]["command"] ==
      "/home/goga/bin/claude-as-claude.sh"` (unchanged base);
      `test_afm_config_env_closure_delivery` (design, verbatim) — catalog
      assistant `reviewer` with `env={"REVIEW_MODE": "strict"}` and
      `agent="codex"`; `_CLOSURE_BASE` patched into `tmp_path`; flow team
      `[reviewer]`; assertions: the closure file exists at
      `<tmp>/goga-assistant-env/goga-reviewer`, its text is EXACTLY
      `'#!/bin/sh\nexport REVIEW_MODE=strict\nexec
      /home/goga/bin/codex-as-claude.sh "$@"\n'`, `stat().st_mode & 0o777
      == 0o700`, the profile `command` equals `str(closure path)`,
      `delegate` from the declaration;
      `test_afm_config_max_tasks_only_with_delegation` (design, verbatim) —
      without `delegation`: no `limits`; with `delegation {max_tasks: 7}` →
      `limits == {"max_tasks": 7}`; with `delegation {}` →
      `{"max_tasks": 50}`; NEGATIVE:
      `test_afm_config_illegal_env_key_before_any_file` (design, verbatim)
      — catalog assistant with `env={"BAD-KEY": "v"}`; `_AFM_CONFIG_PATH`
      and `_CLOSURE_BASE` under `tmp_path`; assertions: `ValueError`
      matching `invalid environment variable name in the reviewer assistant
      env: 'BAD-KEY'`, the config path does NOT exist, the closure
      directory contains NO files;
      `test_afm_config_no_agent_pre_run_error_names_site` (design,
      verbatim) — `agent=None`; catalog assistant without `agent` (variant:
      with `env`); assertions: `ValueError` matching `assistant reviewer at
      workflow.assistants resolved no agent: set its agent or a global
      agent` (the env variant carries `declares env but`); no config file
      written; EDGE: `test_write_afm_config_repeated_invocation_safe`
      (design, verbatim) — two consecutive writes with the same arguments:
      the second replaces the first wholesale (same content); closures
      regenerated (same path, truncated content);
      `test_kill_switch_never_touched` (design, verbatim) —
      `monkeypatch.delenv("AFM_COLLABORATION", raising=False)` and no
      `os.environ` access in the module under test; the written config
      contains NO `enabled` key under `collaboration`; plus the defensive
      branch: a hand-built flow referencing an undeclared name →
      `unknown assistant reference in the compiled flow: NAME`
- [ ] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/pipeline/ -x` then
      the full battery — the `test_run_pipeline.py` wiring fake
      `_write_afm_config(agent)` NECESSARILY raises `TypeError` on the new
      three-argument call (a `MagicMock(side_effect=...)` invokes its
      function with the mock's exact arguments — there is no arity
      tolerance), so the minimal arity adaptation of the fake (accept
      `(agent, flow=None, workflow=None)`) is MANDATORY in this task to
      keep the battery green; the full fake update (spy-recording +
      threading assertions) still belongs to Task 9, and the minimal fix is
      reported in the commit message
- [ ] **STEP 6 (Contract re-verification)**: profiles exist exactly for
      the flow-referenced ids; exactly three keys per profile; both
      pre-run errors fire before any file write (closures included);
      closures owner-only from the first byte; the kill-switch untouched;
      the project layer untouched; `ValueError` propagates to
      `run_pipeline` (nothing caught here)
- [ ] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [ ] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 9: Pipeline wiring — `run_pipeline` threading, `apply_skip_stages` carry, `stage_env_wrappers` anchor (TDD coding)

<Context: the cell `goga/pipeline` (dir `goga/pipeline/`) lands the three
wiring changes. (A) `run_pipeline.py` step 16 (line ~457):
`write_afm_config(config.pipeline.agent, flow_doc, overlay.workflow)` —
after the prompt materialization, before the composition/launch; `flow_doc`
is the exact document the flow-file was serialized from and
`overlay.workflow` the exact document it was compiled from. (B)
`apply_skip_stages.py` rebuild (lines 60–66): add
`assistants=workflow.assistants if workflow is not None else {}` (the SAME
object — opaque carry) and `delegation=workflow.delegation if workflow is
not None else None`. (C) `stage_env_wrappers.py` line 30:
`_KEYS_AFTER_COMMAND` gains `"assistants"` LAST. (D) The
`tests/pipeline/test_run_pipeline.py` fake `_write_afm_config(agent)` at
≈ line 1124 gains the two parameters and the threading assertions (design
Additional Instruction 2), and the source-text pin of
`tests/pipeline/test_run_pipeline_contract.py:417`
(`"write_afm_config(config.pipeline.agent)" in source`) is updated to the
threaded three-argument call in the same change.>

**Usages relevant to this task:**
- `run-pipeline` (the cell's own practice,
  `goga/pipeline/.usages/run-pipeline.md`): the step-16 placement — the
  config write happens before the composition/launch; a collaboration
  `ValueError` surfaces with no events fired.
- `per-stage-env` (the cell's own practice): the anchor mechanism the
  one-line change extends — canonical key order of the patched flow-file.
- `collaboration-delivery` (the cell's own practice,
  `goga/pipeline/.usages/collaboration-delivery.md`): the delivery
  contract the threading realizes (flow + workflow are the two artifacts;
  they cannot diverge).
- `convention`: pure wiring changes keep docstrings accurate; the wiring
  fakes are the established mock point.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task; confirm Task 8 gates
      green
- [ ] **STEP 1 (Contract tests)**: in `tests/pipeline/test_run_pipeline.py`
      — the fake `_write_afm_config` accepts `(agent, flow=None,
      workflow=None)` and RECORDS `(agent, flow, workflow)`; in
      `tests/pipeline/test_apply_skip_stages.py` — a workflow with
      collaboration fields survives the skip rebuild. Expected to fail —
      correct
- [ ] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      build a resolved workflow with `assistants`/`delegation`, run the
      rebuild, and confirm the carried objects are the VERY SAME instances
      (`is`); then implement the three source changes (A) (B) (C) exactly
      as specified; update the `run_pipeline` docstring's step-16
      description and `Raises:` entry (the collaboration `ValueError`
      propagates before any run event); update the fake + add the
      threading assertions
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/test_run_pipeline.py
      tests/pipeline/test_apply_skip_stages.py -v` — pass
- [ ] **STEP 4 (Logic tests)**:
      `test_run_pipeline_threads_flow_and_workflow_to_config_write`
      (design, verbatim) — the existing run-pipeline wiring fakes; the
      updated fake spy-records `(agent, flow, workflow)`; assertions: the
      spy's flow IS the object returned by `compile_flow` (`flow_doc`)
      and the workflow IS `overlay.workflow` (the merged document when a
      tool contributed); `test_apply_skip_stages_carries_collaboration_
      verbatim` (design, verbatim) — workflow with catalog + delegation +
      stage attachments, skip `["build"]`; assertions: the rebuilt
      document's `assistants` is the same object (`is`), `delegation` is
      the same object, non-skipped stages keep their attachment lists;
      `test_run_pipeline_collaboration_error_fires_no_events` (design,
      verbatim) — wiring fakes with a workflow whose assistant resolves no
      agent and `config.pipeline.agent is None`; assertions: `ValueError`
      propagates, no `run_created` fact recorded, the launch function
      never called
- [ ] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — the full
      battery stays green
- [ ] **STEP 6 (Contract re-verification)**: the threading objects are the
      compile input and output themselves (no copies, no re-derivation);
      the verbatim carry preserves identity; the anchor tuple keeps
      `command` before `assistants` in every patched flow-file (span
      detection and the `  command:` rewrite unaffected — assistant
      entries nest at ≥ 4 spaces)
- [ ] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [ ] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 10: Integration — end-to-end collaboration delivery + engine verification (integration tests)

<Context: the cross-entity proof spanning all four cells: the compile →
serialize → config-write chain on one fixture set, plus the post-implementation
verification checklist (design Additional Instructions 7–8). The whole
feature is now implemented; this task proves the no-dead-profile invariant
end to end, the document-wide namespace across stages, and the engine
assumptions against the real afm binary, then closes the verification
checklist.>

**Usages relevant to this task:**
- `afm`: the engine's validation surface — `afm validate` on a compiled
  fixture verifies the three ADR assumptions (profile ids tolerate
  `goga-<name>`; `limits.max_tasks` follows project > global precedence;
  `max_depth: 0` suppresses helper creation but not team members).
- `collaboration-delivery` / `collaboration-emission` (the cells'
  practices): the delivered surface the chain must produce.
- `convention`: integration tests live in the mirrored suite; file I/O via
  `tmp_path`; no mocks on the pure chain.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] Create the integration class of
      `tests/pipeline/test_afm_config_collaboration.py` (or a dedicated
      `tests/pipeline/integration/` module per the house rule if the
      scenario spans packages): `test_compile_skipped_stage_attaches_
      nothing_and_leaves_no_profile` (design, verbatim) — workflow with
      catalog `{reviewer}`, stage `build` (attachment) skipped via CLI
      skip, stage `verify` (attachment, not skipped); run
      `apply_skip_stages` → `compile_flow` → `serialize_flow` →
      `write_afm_config` on the artifacts; assertions: the flow-file has
      NO `build` stage; `assistants:` appear only under `verify`; the
      config profiles `== ["goga-reviewer"]` (the team member + the
      attachment collapse to one id — the no-dead-profile invariant end to
      end); plus the cross-stage namespace scenario re-verified through
      the full chain (stage `a` inline-declares `security`, stage `b`
      references it; the config locates the declaration at
      `workflow.stages.a`)
- [ ] Run the focused suites then the FULL battery:
      `.venv/bin/pytest tests/pipeline/ -x` then `pytest tests/ -x` —
      green
- [ ] Post-implementation verification — Docs item (verification only,
      already applied): confirm `docs/features/pipelines/workflows.md`
      carries the assistants authoring surfaces and that
      `.usages/assistants.md`'s error table still equals the parser
      messages verbatim (if any message was re-worded during
      implementation, the practice file was updated in the same commit —
      verify, and record the reason in the commit)
- [ ] Engine verification (design Additional Instruction 7, with the
      `v2.0.9` binary in the image): compile a fixture carrying a
      `goga-`prefixed profile, a `limits.max_tasks`, and a `max_depth: 0`
      delegation; run `afm validate` on it; the three assumptions hold —
      if any DEVIATES, record it in the topic's `todo.md`
      (`.goga/history/2026/support-afm-assistants/todo.md`) and do NOT
      silently widen the design; if no afm binary is reachable in the
      session, record the check as PENDING with the exact commands
- [ ] Lint gates: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` (0
      errors / 91 cells) — zero violations; commit (gates green, no
      `Co-Authored-By:`)

---

## Validation Commands

(All inside the virtualenv created in Task 1 — `.venv/bin/...`)

- `.venv/bin/pytest tests/ -x`: Run all tests (the full battery)
- `.venv/bin/pytest tests/pipeline/workflow/ tests/pipeline/compiler/
  tests/pipeline/hooks/ tests/pipeline/test_afm_config.py
  tests/pipeline/test_afm_config_collaboration.py
  tests/pipeline/test_run_pipeline.py
  tests/pipeline/test_apply_skip_stages.py -v`: The focused suites of this
  feature
- `.venv/bin/ruff check goga/ tests/`: Lint check (the CI gate of
  `.github/workflows/lint.yml`)
- `.venv/bin/ruff format --check goga/ tests/`: Format check (run
  `ruff format goga/ tests/` to fix)
- `goga lint`: Cell-level lint — 0 errors over 91 cells
- `.venv/bin/python -c "from goga.pipeline.workflow import
  WorkflowAssistant, WorkflowDelegation"`: Workflow facade (18 names)
- `.venv/bin/python -c "from goga.pipeline.compiler import
  FlowAssistant, FlowCollaboration, FlowTeamMember"`: Compiler facade
  (19 names)
- `.venv/bin/python -c "from goga.pipeline import write_afm_config;
  import inspect; assert list(inspect.signature(write_afm_config).
  parameters) == ['agent', 'flow', 'workflow']"`: The pipeline facade
  signature (19 names, unchanged surface)

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
  (`workflow_assistant.py`, `workflow_delegation.py`,
  `flow_collaboration.py`, `flow_team_member.py`, `flow_assistant.py`;
  the six extended files of the workflow cell; the four of the compiler;
  `overlay.py` + `events.py`; `afm_config.py`, `run_pipeline.py`,
  `apply_skip_stages.py`, `stage_env_wrappers.py`)
- [ ] Every contract entity is accessible from its facade (workflow 18,
  compiler 19; pipeline unchanged at 19 with the new signature)
- [ ] Properties and methods match the declared API (dataclass field sets
  and orders exact; the `write_afm_config` three-argument signature with
  `None` defaults)
- [ ] Descriptions are reflected in behavior (presence-based validation
  and defaults; the document-wide namespace; the pinned overlay outcomes;
  the always-emitted collaboration block; profiles exactly for
  flow-referenced ids; both pre-run errors before any file write;
  owner-only closures; `limits` only with a delegation block; verbatim
  carry; identity threading)
- [ ] Contract dependencies are met (workflow → compiler → hooks →
  pipeline order; imported usages applied where their annotations bind
  them)
- [ ] Re-exports are accessible from the facade (two workflow names,
  three compiler names)
- [ ] Every coding task followed the TDD workflow (contract tests → REPL
  probe + code → verification → logic tests → debugging → re-verification
  → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior
  within each coding task (all 34 design test scenarios implemented:
  `test_parse_assistants_catalog_full_form_materializes_defaults`,
  `test_parse_attachment_three_entry_forms`,
  `test_parse_delegation_block_materializes_max_tasks`,
  `test_parse_assistants_error_table`,
  `test_parse_assistants_only_workflow_is_valid`,
  `test_parse_delegation_only_workflow_is_valid`,
  `test_parse_empty_assistants_list_equals_absence`,
  `test_parse_empty_env_and_empty_skills_forms`,
  `test_parse_delegation_depth_zero_survives_to_max_depth_zero`,
  `test_compile_collaboration_block_always_emitted`,
  `test_compile_team_and_stage_attachments_full_materialization`,
  `test_compile_attachments_uniform_across_loop_copies`,
  `test_compile_unknown_reference_raises`,
  `test_compile_duplicate_same_stage_raises`,
  `test_compile_script_and_planning_only_rejected`,
  `test_compile_authored_assistants_key_in_stage_body_rejected`,
  `test_compile_skipped_stage_attaches_nothing_and_leaves_no_profile`,
  `test_compile_reference_to_inline_declaration_of_another_stage`,
  `test_compile_collaboration_free_workflow_byte_identical_except_mode`,
  `test_serialize_collaboration_styles`,
  `test_overlay_catalog_merge_later_tool_wins_and_namespace_drop`,
  `test_overlay_stage_assistants_append_with_dedup`,
  `test_overlay_passthrough_unchanged_and_no_contributions`,
  `test_overlay_catalog_entry_displaces_earlier_inline_declaration`,
  `test_afm_config_profiles_exactly_for_referenced_ids`,
  `test_afm_config_env_closure_delivery`,
  `test_afm_config_max_tasks_only_with_delegation`,
  `test_afm_config_illegal_env_key_before_any_file`,
  `test_afm_config_no_agent_pre_run_error_names_site`,
  `test_write_afm_config_repeated_invocation_safe`,
  `test_kill_switch_never_touched`,
  `test_run_pipeline_threads_flow_and_workflow_to_config_write`,
  `test_run_pipeline_collaboration_error_fires_no_events`,
  `test_apply_skip_stages_carries_collaboration_verbatim`)
- [ ] Integration tests exist where cross-entity scenarios require them
  (the end-to-end no-dead-profile chain; the engine validation)
- [ ] No package boundary was expanded; no new cells; no public API
  beyond the five exported types (private one-line discriminators per
  cell; private closure helpers)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (battery, ruff check + format,
  `goga lint`, facade imports + signature)
- [ ] Every Usages entry is mentioned in at least one task (`convention`,
  `afm`, `beautiful_yaml`, `assistants`, `collaboration-emission`,
  `collaboration-delivery`, `per-stage-env`, `resolve-wrapper-path`,
  `checkpoints`, `run-pipeline`, `parse-workflow`, `compile-flow`,
  `serialize-flow`, `memory`, `memory-emission`, `profiles`,
  `load-workflow`)
- [ ] The Mandatory Rules were enforced at every task boundary and every
  local commit (style, tests, linters/formatters, REPL cycle; no
  `Co-Authored-By:` trailers)

