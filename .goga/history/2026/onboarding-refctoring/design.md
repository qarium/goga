# Design Document: `onboarding-refctoring`

Complete architectural specification for materializing the contracts of the
topic "Extensible `goga init` onboarding: tool participation via hooks actions
and the dynamic image tag" into code. Source contracts: the CODEMANIFEST set
materialized by the apply-architecture stage (9 cells) plus the two
approved fixes of this design stage (see Applied Fixes).

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/version/CODEMANIFEST`: new routine `minor_version` (after
  `host_goga_version`); usage file `minor-line.md` created.
- `goga/hooks/catalog/CODEMANIFEST`: +2 Requirements records in
  `declared_actions` — `onboarding/declare_session` (soft),
  `onboarding/amend_config` (soft).
- `goga/hooks/CODEMANIFEST` (facade): Imports +`wrap_context`,
  `build_hook_arguments` (from `goga/hooks/dispatch`) and
  `enumerate_tool_packages` (from `goga/hooks/tools`); +3 embeddings;
  global Annotations +1 sentence on the delivery re-exports; usage file
  `per-tool-delivery.md` created.
- `goga/onboarding/questions/CODEMANIFEST` (create): `Question`,
  `QuestionGroup` (questions.py), `SessionAnswers` (answers.py); usage
  `question-records.md`.
- `goga/onboarding/participation/CODEMANIFEST` (create): `ToolDeclaration`
  (declaration.py), `ToolContribution` (contribution.py),
  `ToolParticipation` (participation.py); usages `session-participation.md`,
  `tool-contexts.md`.
- `goga/onboarding/survey/CODEMANIFEST` (create): `core_questions` (core.py),
  `assemble_session_plan`, `apply_skips`, `SessionPlan` (plan.py),
  `Questionnaire` (questionnaire.py); usage `survey-run.md`.
- `goga/onboarding/generator/CODEMANIFEST` (create): `FileGenerator`,
  `CreatedFile` (generator.py); usage `artifact-generation.md`.
- `goga/onboarding/CODEMANIFEST` (facade, rewritten): `InitLogic` (logic.py)
  +13 re-export embeddings; old entities removed.
- `goga/commands/init/CODEMANIFEST`: `init` gains `tools: tuple[str, ...]`,
  invitation validation, dedup step, `ToolParticipation` wiring; usage
  `init.md` rewritten.

### New Entities

- `minor_version(version: str) -> minor: str` — goga/version/version.py.
- `Question`, `QuestionGroup`, `SessionAnswers` —
  goga/onboarding/questions/{questions.py, answers.py}.
- `ToolDeclaration`, `ToolContribution`, `ToolParticipation` —
  goga/onboarding/participation/{declaration.py, contribution.py, participation.py}.
- `core_questions`, `assemble_session_plan`, `apply_skips`, `SessionPlan`,
  `Questionnaire` — goga/onboarding/survey/{core.py, plan.py, questionnaire.py}.
- `FileGenerator` (new API), `CreatedFile` — goga/onboarding/generator/generator.py.

### Changed Entities

- `InitLogic` — constructor gains `participation: ToolParticipation`; `run`
  rewritten around the two tool moments, the plan assembly, and the dynamic
  image tag.
- `init` (goga/commands/init/init.py) — `-t/--tool` repeatable option,
  validation order extended, dedup, `ToolParticipation` construction.
- `declared_actions` data — two onboarding records (code change in
  `_DECLARED_ACTIONS`).
- `goga.hooks` facade — three additional re-exports.
- `goga.version` facade — `minor_version` re-export.

### Deleted Entities

- `InitAnswers`, `GogaConfigAnswers` (old goga/onboarding/answers.py) —
  replaced by the declarative `SessionAnswers` space; the flat answer
  container dissolves into nested mappings.
- Old `Questionnaire.ask/ask_goga_config/ask_*` per-field methods
  (goga/onboarding/questionnaire.py) — the engine is rebuilt around
  `run(plan, answers)` + `ask_question` + `ask_group`; per-field ask logic
  is ported into the engine's core-section survey.
- Old `FileGenerator.generate(answers: InitAnswers)` /
  `generate_goga_config(config: GogaConfigAnswers)` — replaced by the
  snapshot-driven API.
- Files `goga/onboarding/answers.py`, `goga/onboarding/questionnaire.py`,
  `goga/onboarding/generator.py` are deleted; their contracts live in the
  leaf cells.

### Usages and Annotations Changes

- New usage files: `minor-line.md`, `per-tool-delivery.md`,
  `question-records.md`, `session-participation.md`, `tool-contexts.md`,
  `survey-run.md`, `artifact-generation.md`.
- Rewritten: `onboarding-usage.md` (domain facade), `init.md` (CLI with
  `-t`).
- New header practices: survey gains inline `image_defaults` (tag-completed
  hints) and `agent_env_defaults` (agent → env keys); generator gains
  inline `yaml` and `lang_conventions` (moved from the old facade header).

## Applied Fixes

### Fixed CODEMANIFEST Defects

Both fixes approved by the user during this stage (file dialog q1, q2).

- `goga/onboarding/questions/CODEMANIFEST`: `SessionAnswers()` →
  `SessionAnswers(tools: list[str] | None = None)`; Requirements restate
  "Created empty — the space holds no answers; `tools` reserves the
  top-level keys of the tool sections"; `view_for` algorithm step 1 now
  reads "every top-level key except the reserved tool-section names"
  (reason: semantic gap — the core/tool distinction was not derivable by
  the object; defect type: unoperationalizable algorithm).
- `goga/onboarding/survey/CODEMANIFEST`: `assemble_session_plan` gains
  algorithm step 4 and Requirements bullet — a tool identity colliding
  with a section name of the `core` tree drops the tool's whole block with
  a warning; core section names are reserved; the tool keeps its amendment
  rights (reason: edge-case gap — `goga_tool_tools` → identity `tools`
  would silently merge the core `tools` section with the tool block;
  defect type: ambiguous plan-root naming).

Matching usage updates: `question-records.md` (constructor param),
`survey-run.md` (reserved names).

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
CLI: goga init [-t name]... [<tpl>] [--upgrade] [--ref r]
  └─ init (goga/commands/init)  ── validates flags, dedups tools
       ├─ Scaffold (tpl modes; unchanged)
       └─ InitLogic(Questionnaire, FileGenerator, ToolParticipation(tools))
            │
            │ 1. guard: existing .goga/config.yml → return 0
            │ 2. host_goga_version → minor_version → tag
            │ 3. ToolParticipation.collect_declarations ──── moment one
            │      ├─ HookRegistry.build_once ── enumerate_tool_packages
            │      │     └─ goga_tool_* facades: register_hooks(hooks)
            │      │           subscribe("onboarding","declare_session",…)
            │      ├─ per tool: wrap_context(ToolDeclaration) +
            │      │  build_hook_arguments(hook, view, self_context)
            │      │  → hook(context[, self]) → context.declare/.skip
            │      └─ declarations: list[ToolDeclaration]
            │ 4. resolve_project_name (goga/config), conventions.md check
            │    core_questions(tag, name, exists) → core tree
            │    assemble_session_plan(core, declarations) → SessionPlan
            │    apply_skips(plan, (tool, path) pairs) → SessionPlan
            │ 5. SessionAnswers(tools=plan.tools)
            │    Questionnaire.run(plan, answers)  ── click survey
            │ 6. ToolParticipation.collect_contributions(answers) ─ moment two
            │      ├─ per tool: view_for(tool) → ToolContribution(view)
            │      │  wrap_context + build_hook_arguments → hook(context)
            │      │  → context.answer / context.write_config
            │      └─ commit: answers.amend(...) per contribution; files kept
            │ 7. FileGenerator.generate(answers, contributions)
            │      ├─ Dockerfile (FROM base_image) when dockerfile path
            │      ├─ generate_goga_config: snapshot → .goga/config.yml
            │      │    └─ conventions download (lang_conventions)
            │      └─ generate_tool_configs → .goga/tools/<tool>/<file>
            │ 8. file report with attribution → exit 0
```

### Data Flows

- **Invitation flow**: CLI `-t` names → dedup (order-preserving) →
  `ToolParticipation(invited)` → per-tool `invited` marker on both
  surfaces → hook-side early return when False.
- **Declaration flow**: hook buffers `Question`/`QuestionGroup` +
  skip paths → `ToolDeclaration.questions/.skips` → plan blocks named by
  tool identity → skips `(tool, raw_path)` → `apply_skips`.
- **Answer flow**: `Questionnaire.run` records at plan paths → nested
  mappings in `SessionAnswers` → `view_for(tool)` isolates per tool →
  amendments `answer(id, value)` → committed via `amend` (recursive merge)
  → `snapshot()` → config mapping.
- **Tag flow**: `host_goga_version()` → `minor_version()` → `"N.M"` →
  `core_questions(image_tag)` → completed hints in the tree → prompts.
- **File flow**: committed `ToolContribution.files` +
  snapshot → `FileGenerator.generate` → `list[CreatedFile]` → report.

### Entity Dependencies

Implementation order (leaves → root, matching the schema):

1. `goga/version` (leaf) — `minor_version` reuses module-private
   `_release_segments`.
2. `goga/hooks/catalog` (leaf) — two data records.
3. `goga/hooks` facade — three re-exports.
4. `goga/onboarding/questions` (leaf) — no imports.
5. `goga/onboarding/participation` — imports questions + goga/hooks.
6. `goga/onboarding/survey` — imports questions + participation
   (`ToolDeclaration` only).
7. `goga/onboarding/generator` — imports questions + participation
   (`ToolContribution` only).
8. `goga/onboarding` facade — imports all four leaves + goga/version +
   goga/config.
9. `goga/commands/init` — imports the onboarding facade + goga/scaffold.

Construction order at runtime: `ToolParticipation` and `Questionnaire`
and `FileGenerator` are constructed by `init` and injected into
`InitLogic`; `SessionAnswers` is constructed inside `InitLogic.run` after
`apply_skips` (it needs `plan.tools`); `HookRegistry` is constructed once
inside `ToolParticipation` and shared by both moments.

---

## Code Stack Trace

### Trace: `minor_version(version)`

#### Chain
1. **Input**: caller `InitLogic.run` step 2 passes the string returned by
   `host_goga_version()`; tests pass literals.
2. **Step**: `_release_segments(version)` (module-private, already in
   version.py:71) reduces to `(major, minor | None)` — regex
   `_RELEASE_PREFIX_RE` strips dev/pre/post/local tails → checkpoint: the
   reducer exists at the same `location: version.py`; reuse, do not
   duplicate (constraint: "mirroring `resolve_version`").
3. **Step**: `minor = minor_seg if minor_seg is not None else "0"` →
   checkpoint: "Treat a missing minor segment as 0" — matches
   `compare_versions`'s convention (`"1" ≡ "1.0"`).
4. **Step**: `return f"{major}.{minor}"` → checkpoint: pure string join,
   no I/O — the practice `convention` pure-function discipline.
5. **Output**: `"N.M"` string; `ValueError` propagates from
   `_release_segments` for an argument with no leading numeric major.

#### Checkpoint Summary
- reuse of `_release_segments`: passed (same module, same location).
- error contract: passed (ValueError, message from the shared reducer).

### Trace: `declared_actions()` (changed data)

#### Chain
1. **Input**: no arguments; called by `HookRegistrar.subscribe`
   (registration.py:99) and `emit_hook_event` (emit.py:72) on every
   registration/emission.
2. **Step**: `_DECLARED_ACTIONS` gains
   `Action(domain="onboarding", name="declare_session", error_class="soft")`
   and `Action(domain="onboarding", name="amend_config", error_class="soft")`
   → checkpoint: frozen dataclasses, catalog constant stays supported-data
   only; the pair is unique; error_class is exactly `soft`.
3. **Step**: `sorted(..., key=(domain, name))` yields
   `onboarding/amend_config`, `onboarding/declare_session`,
   `statuses/register_statuses` → checkpoint: ordering rule unchanged; the
   `goga hooks` inspection output gains the two rows — additive only.
4. **Output**: new list per call; registration of the onboarding addresses
   becomes acceptable (`subscribe` no longer rejects
   "unknown action onboarding.declare_session").

#### Checkpoint Summary
- additive catalog extension: passed (published records are never
  rewritten; the statuses record is untouched).

### Trace: `goga.hooks` facade import (changed)

#### Chain
1. **Input**: `from goga.hooks import HookRegistry, ToolHooks,
   emit_hook_event, wrap_context, build_hook_arguments,
   enumerate_tool_packages` (consumer: goga/onboarding/participation).
2. **Step**: facade `__init__.py` adds `from .dispatch import
   build_hook_arguments, wrap_context` and `from .tools import
   enumerate_tool_packages`; `__all__` gains the three names → checkpoint:
   both sub-facades already export them (dispatch/__init__.py,
   tools/__init__.py verified); no tool package is imported and nothing is
   enumerated at import time (facade docstring invariant holds).
3. **Step**: name-collision check — no local names shadow the imports;
   `declared_actions` re-export untouched.
4. **Output**: the delivery primitives and the enumeration are consumable
   through the facade only (participation's `From: goga/hooks` resolves).

#### Checkpoint Summary
- export availability: passed.
- import-side-effect invariant: passed (importing goga.hooks imports no
  `goga_tool_*`).

### Trace: `Question(...)` / `QuestionGroup(...)` constructors

#### Chain
1. **Input**: keyword construction (`kw_only=True` per the `convention`
   practice data-model rules), e.g.
   `Question(id="token", kind="input", prompt="Service token")`.
2. **Step**: frozen dataclasses with fields exactly as the signatures;
   `choices`/`default`/`keys` default to `None` (absence semantics) →
   checkpoint: convention rule "dataclasses, kw_only=True"; `None` only
   for explicit absence — the optionality here IS absence of the
   parameterization.
3. **Step**: no validation in the records ("the record carries data only —
   rendering and validating the answer value belong to the survey
   engine") → checkpoint: kinds are checked at ask time, not at
   construction.
4. **Output**: immutable value objects; `QuestionGroup.children` defaults
   to `None`, a structural node carries no prompt.

#### Checkpoint Summary
- data-only discipline: passed (no methods, no properties beyond fields).

### Trace: `SessionAnswers.record(id, value)`

#### Chain
1. **Input**: the survey passes the plan dot-path (`"build.agent"`,
   `"my-tool.token"`) and the answer value
   (`str | bool | dict`).
2. **Step**: split `id` on `"."`; walk `self._data` creating intermediate
   `dict`s for traversed groups → checkpoint: a leaf collision with an
   existing scalar mid-path is replaced by a mapping (record wins — the
   survey is the authoritative writer of the run).
3. **Step**: set `value` at the leaf name → checkpoint: "Recording
   replaces" — assignment, never merge.
4. **Output**: nested mapping; `snapshot()` reflects it; no return value.

#### Checkpoint Summary
- dotted-key ban: passed — the dotted path is split, never stored as a
  literal key.

### Trace: `SessionAnswers.amend(id, value)`

#### Chain
1. **Input**: committed contribution buffer entry `(path, value)` from
   `ToolParticipation.collect_contributions` step 3.
2. **Step**: same segment walk creating intermediates.
3. **Step**: at the leaf — existing `dict` AND `value` is `dict` →
   recursive merge (`merge(old[k], new[k])` per key; keys of `value`
   win/replace per the same rule); otherwise (scalar, list, absent, or
   type mismatch) → plain assignment → checkpoint: the exact rule
   "mappings merge recursively; scalars and lists replace" — merge happens
   only when BOTH sides are mappings.
4. **Step**: delivery order is the caller's responsibility
   ("a later amendment wins at every conflicting leaf" — later assignment
   overwrites).
5. **Output**: mutated space; silent (no warning — "substituting a user's
   answer is a tool's lawful right").

#### Checkpoint Summary
- merge asymmetry handled: passed (scalar-under-mapping and
  mapping-under-scalar both fall to replace).

### Trace: `SessionAnswers.view_for(tool)`

#### Chain
1. **Input**: `tool` identity from `ToolParticipation` (a subscribing tool
   of `amend_config`).
2. **Step**: `view = deepcopy({k: v for k, v in self._data.items() if k
   not in self._tool_sections})` → checkpoint: core = top-level keys minus
   the reserved names given at construction (`tools` param, fix q1); the
   survey records tool blocks exactly under those names.
3. **Step**: `own = self._data.get(tool)`; if a mapping, `view.update(deepcopy(own))`
   → checkpoint: own local names land at the top level ("without the tool
   prefix"); on a local-name collision with a core key the tool's own
   value wins (update order) — the tool shadows only its own view; an
   absent own section (no block, fully skipped, or non-declaring tool)
   yields the core-only view.
4. **Step**: deep copy everywhere → checkpoint: "The view is a snapshot —
   amendments applied after the call do not appear in it" and a hook
   mutating the view cannot touch the space.
5. **Output**: `dict` delivered as `ToolContribution.answers`.

#### Checkpoint Summary
- isolation of other tools: passed (excluded by the reserved set).
- snapshot immutability: passed (deepcopy).

### Trace: `SessionAnswers.snapshot()`

#### Chain
1. **Input**: `FileGenerator.generate_goga_config` step 1 (after the
   contributions are committed).
2. **Step**: `deepcopy(self._data)` — the complete nested structure: core
   sections and every committed tool section.
3. **Output**: `dict`; generation maps core fields and ignores tool
   sections (their data reaches `.goga/tools/<tool>/` through
   `write_config`, not through config.yml) → checkpoint: mapping table has
   no entry for tool sections — intentional.

### Trace: `ToolDeclaration` delivery (moment one, per tool)

#### Chain
1. **Input**: `ToolParticipation.collect_declarations` groups
   `registry.subscriptions_for("onboarding", "declare_session")` by
   `subscription.tool` preserving enumeration order.
2. **Step**: `surface = ToolDeclaration(tool=..., invited=tool in
   self._invited)`; `proxy = wrap_context(surface)` → checkpoint:
   `wrap_context` (delivery.py:28) resolves attribute reads and bound
   methods; writes blocked — `declare`/`skip` are METHOD calls, they pass.
3. **Step**: per subscription `arguments = build_hook_arguments(hook,
   proxy, registry.self_context(tool))`; `hook(**arguments)` → checkpoint:
   only a declared `context` (and optional `self`) receives values
   (delivery.py:69); the hook signature pattern from
   `tool-contexts.md` works verbatim.
4. **Step**: the hook checks `context.invited`; False → immediate return
   (empty buffer — "A tool without declarations contributes no block");
   True → `context.declare(...)`, `context.skip(...)` buffer into the
   surface.
5. **Step**: any `Exception` from a hook of the tool → the whole
   declaration of that tool is discarded with a warning; the delivery
   continues with the next tool → checkpoint: staged control per the
   `per-tool-delivery` practice (commit only after every hook of the tool
   succeeded).
6. **Output**: surviving declarations in enumeration order.

#### Checkpoint Summary
- read-only context + callable members: passed.
- never called to survey: passed (the engine asks the buffered records
  itself later).

### Trace: `ToolDeclaration.declare(item)` / `.skip(path)`

#### Chain
1. **Input**: a `Question`, or a one-level `QuestionGroup` with simple
   children; a raw skip path string.
2. **Step**: `declare` validates the one-level rule — a group whose
   `children` contain a `QuestionGroup` is refused with a logged warning
   naming the tool and the reason; the element is not buffered →
   checkpoint: the Requirement lives on `declare`; enforcement at the
   surface, single point.
3. **Step**: accepted items append to `questions`; `skip` appends the raw
   string — no resolution here ("the engine resolves and applies every
   declared skip as one set").
4. **Output**: buffered lists readable via the properties after delivery.

### Trace: `ToolContribution` delivery (moment two, per tool)

#### Chain
1. **Input**: `collect_contributions(answers)` after the survey; the same
   registry; subscriptions of `onboarding/amend_config` grouped per tool.
2. **Step**: `view = answers.view_for(tool)`; `surface =
   ToolContribution(tool=..., invited=..., answers=view)` → checkpoint:
   type flow — `view_for -> dict` matches `ToolContribution.answers: dict`.
3. **Step**: `wrap_context` + `build_hook_arguments` + call, identical to
   moment one; the hook reads `context.answers`, buffers
   `context.answer(path, value)` and `context.write_config(file, data)`.
4. **Step**: failure → the tool's whole contribution (amendments AND
   files) discarded with a warning; other tools stand.
5. **Step**: commit pass in enumeration order: `answers.amend(path,
   value)` per buffered amendment; the contribution object (with its file
   buffer) is returned for generation.
6. **Output**: `list[ToolContribution]` — the committed contributions.

#### Checkpoint Summary
- staged commit: passed (buffer → all hooks of the tool succeed →
  commit).
- file buffers: passed (returned, not written here — generation owns the
  write path).

### Trace: `core_questions(image_tag, project_name, convention_exists)`

#### Chain
1. **Input**: `InitLogic.run` step 4 — tag from step 2, name from
   `resolve_project_name()` (`str | None`), flag from
   `Path(".goga/usages/conventions.md").is_file()`.
2. **Step**: build the section list in survey order: `language`,
   `convention` (only when the file is absent), `codemanifest`, `build`,
   `docker_image`, `pipeline`, `tools`, `usages` → checkpoint: eight
   sections with convention; omission rule exact.
3. **Step**: image hints — the `image_defaults` mapping completed with
   `image_tag` (e.g. `qarium/goga-python-3.12:1.3`): the completed list is
   embedded in the prompt text of the `base_image` question and its
   default is the LAST entry; the `image` question carries the
   built-branch default `f"{project_name}:latest"` or no default when the
   name is `None` → checkpoint: kind stays `input` (free-form accepted,
   matching the old `click.prompt(default=images[-1])` behavior); the tag
   is never hardcoded.
4. **Output**: `QuestionGroup(id="core", children=[sections])` — the root
   id is never addressed in answers (sections are the top-level keys).

#### Checkpoint Summary
- tag threading: passed (single source, `minor_version` output).
- free-form image input preserved: passed.

### Trace: `assemble_session_plan(core, declarations)`

#### Chain
1. **Input**: the core tree + surviving declarations in enumeration
   order.
2. **Step**: `children = list(core.children)`; `tools: list[str] = []`;
   `reserved = {child.id for child in core.children}`.
3. **Step**: per declaration — empty `questions` → skip ("contributes no
   block"); `declaration.tool in reserved` → warning naming the tool and
   the reserved name, skip the whole block (fix q2) → checkpoint: the
   guard compares against the RECEIVED core's children — no hardcoded
   name list.
4. **Step**: local-name dedup within the declaration: walk
   `declaration.questions` in order tracking seen ids; a repeated id drops
   THAT element with a warning naming the tool and the reason; survivors
   stand → checkpoint: element-level rejection only.
5. **Step**: append `QuestionGroup(id=declaration.tool, prompt=ATTRIBUTION_HEADING,
   children=survivors)`; `tools.append(declaration.tool)` → checkpoint:
   the block prompt doubles as the attribution heading the engine echoes.
6. **Output**: `SessionPlan(root=QuestionGroup(id="session",
   children=children), tools=tools)` — a fresh root; the core tree is
   never mutated (records are frozen).

#### Checkpoint Summary
- determinism: passed (core order then enumeration order).
- immutability of inputs: passed (fresh containers; shared frozen
  records).

### Trace: `apply_skips(plan, skips)`

#### Chain
1. **Input**: the assembled plan; `[(tool, raw_path), ...]` flattened by
   `InitLogic` from the declarations' buffers.
2. **Step**: resolve every raw path against the ORIGINAL root:
   segments = `raw_path.split(".")`; IF `segments[0]` is a tool identity
   in `plan.tools` → the address is the full path from the root; ELSE IF
   `segments[0]` resolves among the core section ids → the address is the
   path from the root; ELSE IF `segments[0]` matches a local name of the
   DECLARING `tool`'s own block → the address is `tool` + the path; ELSE →
   warning no-op → checkpoint: the three-way rule of the contract
   (prefixed / core / own-block) is fully deterministic; a path under a
   pairs question simply has no children to resolve → no-op warning
   ("only the node as a whole").
3. **Step**: existence is checked against the original tree only — a
   descendant of an already-skipped node resolves in the original, so the
   set removal absorbs it silently (no spurious warning) → checkpoint:
   "apply all skips as one set — order-independent".
4. **Step**: rebuild — construct new `QuestionGroup`s along removed
   branches, dropping resolved nodes; unmodified branches share the
   frozen originals.
5. **Output**: a NEW `SessionPlan` (same `tools` list — an emptied block
   stays; the engine suppresses its empty heading and its section simply
   never records).

#### Checkpoint Summary
- order independence: passed (set semantics against the original).
- immutability: passed (new plan, no mutation of the input).

### Trace: `Questionnaire.run(plan, answers)`

#### Chain
1. **Input**: the final plan; the empty `SessionAnswers(tools=plan.tools)`.
2. **Step**: session header echoes (`=== Goga Project Initialization ===`
   + wizard description — ported from the old `ask`).
3. **Step**: iterate `plan.root.children` in order; membership in
   `plan.tools` distinguishes tool blocks from core sections → checkpoint:
   assembly guarantees tool blocks come after all core children.
4. **Step**: core sections — the engine's conditional patterns (see
   Algorithm Design: `Questionnaire`): the confirm gates are
   presentational (asked, drive control flow, NEVER recorded); the
   collected values record at their plan paths.
5. **Step**: tool blocks — echo the block's prompt (the attribution
   heading), then `ask_group(block)`; records land at
   `"{tool}.{local}"` paths → checkpoint: answers of a tool nest under
   the reserved tool-section key, exactly the key `view_for` later
   strips.
6. **Output**: populated answer space; `click.Abort` propagates to
   `InitLogic` (exit 1, quiet).

#### Checkpoint Summary
- "nothing calls a tool hook to survey": passed — the engine asks the
  buffered records; hooks are already done.

### Trace: `FileGenerator.generate(answers, contributions)`

#### Chain
1. **Input**: the committed space; the committed contributions.
2. **Step**: `Path(".goga/config.yml").is_file()` → skip steps 2 (Dockerfile
   and config) — the guarantee lives here, not only at the caller →
   checkpoint: double guard with `InitLogic` step 1 is intentional.
3. **Step**: snapshot = `answers.snapshot()`; `docker_image.dockerfile` AND
   `docker_image.base_image` both present → write the Dockerfile
   (`FROM {base_image}` + newline, `mkdir(parents=True, exist_ok=True)`) →
   `CreatedFile(path, None)`; a skipped `base_image` collapses the branch —
   no Dockerfile is written and the config `dockerfile` field is omitted.
4. **Step**: `generate_goga_config(answers)` — inside it, the conventions
   download writes `.goga/usages/conventions.md` (→ `CreatedFile(...,
   None)`) before the config serialization (→ `CreatedFile(".goga/config.yml",
   None)`).
5. **Step**: `generate_tool_configs(contributions)` — per contribution,
   per buffered `(file, data)` in call order → `.goga/tools/<tool>/<file>`
   (→ `CreatedFile(path, tool)`); a repeated file name replaces.
6. **Output**: `list[CreatedFile]` in generation order: Dockerfile,
   conventions.md (when downloaded), config.yml, tool files.

#### Checkpoint Summary
- generation order: passed (Dockerfile before config — the config names
  the image built from it).
- attribution: passed (None for engine files, identity for tool files).

### Trace: `FileGenerator.generate_goga_config(answers)`

#### Chain
1. **Step**: snapshot; `language = snapshot.get("language")` — empty →
   clean `ValueError` naming the field (the single required-field check).
2. **Step**: conventions entry — `codemanifest.usages` carries the
   `"conventions"` key → download per `lang_conventions` (URL template,
   `requests.get(url, timeout=30)`); failure → clean error with the URL
   and the cause (ported verbatim from the old generator; config.yml is
   NOT created on failure).
3. **Step**: `mkdir .goga`; assemble the ordered document per the mapping
   table: `language`; `image` ← `docker_image.image`; `dockerfile` ←
   `docker_image.dockerfile` (omitted when absent); `build` ←
   `{"task_executor": {agent?, env?}}` from `build.{agent,env}` (omitted
   when empty); `pipeline` ← `{agent?, env?}` flat block (same rules);
   `codemanifest` ← `{usages?, annotations?}` (`_LiteralStr` literal
   block); `tools` ← top-level tools section (omitted when absent/empty);
   `usages` ← the nested records (omitted when absent/empty) → checkpoint
   against `goga/config/project/loader.py`: `tools` is `dict[str, str]`
   (loader.py:253), `usages` is `dict[str, dict[str, DepConfig]]` with
   `git` required and `ref`/`root` optional strings (loader.py:365-370) —
   the survey's `{group: {dep: {git, ref, root}}}` nesting matches; build
   nests under `task_executor` while pipeline stays flat — matches the old
   writer and the loader.
4. **Step**: `yaml.dump(data, default_flow_style=False, allow_unicode=True,
   sort_keys=False)` — field order preserved by dict insertion order.
5. **Output**: `.goga/config.yml` passing the core schema loader.

#### Checkpoint Summary
- mapping table vs config schema: passed (verified field by field).
- confirm gates / convention answers never carried: passed (never
  recorded in the first place — the design's gate rule).

### Trace: `InitLogic.run()`

#### Chain
1. **Step**: existing `.goga/config.yml` → `return 0` immediately (no
   prompts, no events, no artifacts).
2. **Step**: `version = host_goga_version()` — `PackageNotFoundError` →
   one clean message, `return 1`; `tag = minor_version(version)` —
   `ValueError` → clean message, `return 1` (defensive; practically
   unreachable for metadata versions).
3. **Step**: `declarations = self._participation.collect_declarations()`
   — `ImportError` (broken package import, named by the platform wrapper)
   → one clean message, `return 1`; warnings for soft failures already
   logged inside.
4. **Step**: `project_name = resolve_project_name()` (tolerant, `None` on
   failure — never raises); `convention_exists =
   Path(".goga/usages/conventions.md").is_file()`; `core =
   core_questions(tag, project_name, convention_exists)`; `plan =
   assemble_session_plan(core, declarations)`; `skips = [(d.tool, p) for
   d in declarations for p in d.skips]`; `plan = apply_skips(plan, skips)`.
5. **Step**: `answers = SessionAnswers(tools=plan.tools)`;
   `self._questionnaire.run(plan, answers)` — `click.Abort` → `return 1`
   (quiet); unexpected `Exception` → one clean message, `return 1`.
6. **Step**: `contributions =
   self._participation.collect_contributions(answers)`.
7. **Step**: `files = self._generator.generate(answers, contributions)`;
   render the report: `created {path}` / `created {path} (tool: {tool})`.
8. **Output**: `return 0` — tool failures never change the exit code.

#### Checkpoint Summary
- error tiers: passed (see Cross-cutting Concerns).
- type flow across all six imported leaves: passed (every boundary
  checked in the traces above).

### Trace: `init(tpl, upgrade, ref, tools)` (goga/commands/init)

#### Chain
1. **Input**: click passes `tpl: str | None`, `upgrade: bool`,
   `ref: str | None`, `tools: tuple[str, ...]` (`@click.option("-t",
   "--tool", "tools", multiple=True, ...)`).
2. **Step**: ref placement check (ported verbatim) → exit 1 message
   `--ref requires <tpl> or --upgrade`.
3. **Step**: mode resolution (ported verbatim; `<tpl>` + `--upgrade`
   mutual exclusion) → `UPGRADE | SCAFFOLD_THEN_ONBOARDING |
   BARE_ONBOARDING`.
4. **Step**: invitation validation — `tools` non-empty AND mode
   `UPGRADE` → message `-t/--tool requires an onboarding session and
   --upgrade runs none`, exit 1 → checkpoint: contract algorithm step 3;
   message text matches `init.md`.
5. **Step**: dedup preserving flag order — `list(dict.fromkeys(tools))`.
6. **Step**: already-initialized guard (BARE_ONBOARDING only) → ported.
7. **Step**: dispatch — UPGRADE: `Scaffold().upgrade(ref)`; the two
   onboarding modes: `InitLogic(Questionnaire(), FileGenerator(),
   ToolParticipation(invited=deduped))` → `ctx.exit(logic.run())` →
   checkpoint: tuple→list conversion happens at the dedup step; the
   facade signature `ToolParticipation(invited: list[str])` receives a
   list.
8. **Output**: `ctx.exit(code)`.

#### Checkpoint Summary
- validation order matches the contract algorithm 1–6: passed.
- opaque passthrough (no installation checks in the command): passed.

---

## Algorithm Design

### `minor_version`

**Responsibility**: reduce a version string to its `N.M` line — the same
reduction the host↔image comparison uses.

**Algorithm:**
```
1. major, minor_seg = _release_segments(version)   # shared reducer; ValueError on no major
2. minor = minor_seg if minor_seg is not None else "0"
3. return f"{major}.{minor}"
```

**Errors:**
- `ValueError` (from the reducer) → propagates; the caller (`InitLogic`)
  translates into a clean session message.

**Edge Cases:**
- `"1.2.1.dev3"`, `"1.2.0rc1"`, `"1.2.0.post1"`, `"1.2.0+local"` → all
  `"1.2"` (tails discarded by the reducer).
- `"2"` → `"2.0"`.

### `Question`, `QuestionGroup`

**Responsibility**: immutable declarative records of the survey.

**Algorithm:** frozen dataclasses, `kw_only=True`, fields per the
signatures; no behavior.

**Edge Cases:** none — validation belongs to the engine.

### `SessionAnswers`

**Responsibility**: the single mutable accumulator of one run.

**Algorithm:**
```
construct(tools=None):
  _data = {}; _tool_sections = frozenset(tools or ())

record(id, value):
  walk segments of id, creating dicts; set leaf = value (replace)

amend(id, value):
  walk segments of id, creating dicts
  leaf existing dict AND value dict → recursive merge (per key: same rule)
  otherwise → replace/create

view_for(tool):
  core = deepcopy of _data items whose key not in _tool_sections
  own = _data.get(tool); if mapping → core.update(deepcopy(own))
  return core

snapshot():
  return deepcopy(_data)
```

**Errors:** none raised — the accumulator is total.

**Edge Cases:**
- `record` over an existing scalar with a deeper path → the scalar is
  replaced by the intermediate mapping (the survey is authoritative).
- `view_for` of a tool without a recorded section → core-only view.
- local name of the tool colliding with a core key in ITS view → the
  tool's own value wins (update order); only that tool's view is
  affected.

### `ToolDeclaration`

**Responsibility**: moment-one surface + buffer of one tool.

**Algorithm:**
```
declare(item):
  IF item is QuestionGroup and any(child is QuestionGroup for child in item.children):
      logger.warning("rejected declaration of tool %s: a tool group is limited to one nesting level with simple children", tool)
      return                      # element dropped, delivery continues
  questions.append(item)

skip(path):
  skips.append(path)              # raw; resolution belongs to apply_skips
```

**Errors:** structural violations are warnings, never exceptions (a
raise would kill the tool's whole declaration — disproportionate for one
bad element; the contract reserves exceptions for real failures).

**Edge Cases:**
- non-invited tool: the hook returns before any call — the buffer stays
  empty and the tool contributes no block.

### `ToolContribution`

**Responsibility**: moment-two surface + staged buffer.

**Algorithm:**
```
answer(id, value):   amendments.append((id, value))     # call order kept
write_config(file, data): files.append((file, data))    # a later same name replaces at write time
```

**Edge Cases:** `answers` is the isolated deep-copied view — a hook
mutating it harms only itself.

### `ToolParticipation`

**Responsibility**: the mediator of both onboarding action moments.

**Algorithm:**
```
construct(invited):
  _invited = list(dict.fromkeys(invited))   # defensive dedup, flag order
  _registry = None

collect_declarations():
  _ensure_registry()                          # HookRegistry(); build_once()
                                               # ImportError propagates — the single fatal case
  for name in _invited:
      IF name not in {pkg.tool for pkg in enumerate_tool_packages()}:
          logger.warning("invited tool %s is not installed; continuing without its block", name)
  groups = per-tool grouping of subscriptions_for("onboarding", "declare_session")
           preserving enumeration order
  declarations = []
  for tool, subs in groups:
      surface = ToolDeclaration(tool=tool, invited=tool in _invited)
      proxy = wrap_context(surface)
      try:
          for sub in subs:
              sub.hook(**build_hook_arguments(sub.hook, proxy, _registry.self_context(tool)))
      except Exception as reason:
          logger.warning("declaration of tool %s dropped on onboarding.declare_session: %s", tool, reason)
          continue                            # whole declaration discarded
      declarations.append(surface)
  return declarations

collect_contributions(answers):
  _ensure_registry()
  groups = per-tool grouping of subscriptions_for("onboarding", "amend_config")
  contributions = []
  for tool, subs in groups:                   # enumeration order
      surface = ToolContribution(tool=tool, invited=tool in _invited,
                                 answers=answers.view_for(tool))
      proxy = wrap_context(surface)
      try:
          for sub in subs:
              sub.hook(**build_hook_arguments(sub.hook, proxy, _registry.self_context(tool)))
      except Exception as reason:
          logger.warning("contribution of tool %s discarded on onboarding.amend_config: %s", tool, reason)
          continue                            # amendments AND files discarded together
      contributions.append(surface)
  for surface in contributions:                # commit pass, delivery order
      for path, value in surface.amendments:
          answers.amend(path, value)
  return contributions
```

**Errors:**
- broken package import → `ImportError` propagates from `build_once` →
  `InitLogic` renders one clean message naming the package, exit 1.
- hook failure → warning naming tool, action, reason; the tool drops out
  of that moment; the session continues.

**Edge Cases:**
- invited tool without a subscription to the action → absent from
  `groups` → silent, no block, no warning.
- subscribed tool without an invitation → surface `invited=False` → the
  hook returns immediately; empty buffer → no block, but its moment-two
  surface is still built (a non-invited tool also returns immediately).
- `collect_contributions` without a prior `collect_declarations` →
  `_ensure_registry` builds lazily (defensive; the session flow always
  calls moment one first).

### `core_questions`

**Responsibility**: the core tree — eight sections in survey order with
the tag-completed hints.

**Algorithm:**
```
sections = []
1. language: Question(id="language", kind="choice", prompt=..., choices=_LANGUAGES)
   # order preserved from the old wizard: python, golang, kotlin, swift, javascript
2. IF not convention_exists:
   convention: QuestionGroup(id="convention", prompt="--- Base Convention ---",
       children=[Question(id="adopt", kind="confirm", prompt="Download base convention", default=False)])
3. codemanifest: QuestionGroup(children=[
       Question(id="usages", kind="pairs", prompt="Codemanifest usages (name → path)"),
       Question(id="annotations", kind="input", prompt="Codemanifest annotations")])
   # defaults for both are supplied at ask time when the convention gate was accepted
   # (engine-side prefill — see Questionnaire)
4. build: QuestionGroup(children=[
       Question(id="agent", kind="choice", prompt="Build agent", choices=_AGENTS),
       Question(id="env", kind="pairs", prompt="Build env (KEY → value)")])
5. docker_image: QuestionGroup(children=[
       Question(id="dockerfile", kind="input", prompt="Dockerfile path", default=".goga/Dockerfile"),
       Question(id="base_image", kind="input",
                prompt="Base image (FROM)\nAvailable images:\n  - hint1\n  - hint2…",
                default=<last completed hint>),
       Question(id="image", kind="input", prompt="Built image name",
                default=f"{project_name}:latest" if project_name is not None else None)])
6. pipeline: QuestionGroup(children=[
       Question(id="agent", kind="choice", prompt="Pipeline agent", choices=_AGENTS),
       Question(id="env", kind="pairs", prompt="Pipeline env (KEY → value)")])
7. tools: Question(id="tools", kind="pairs",
       prompt="Tools (name → version; empty version reads as latest; forms N / N.M / N.M.K / N.x / N.M.x)")
8. usages: QuestionGroup(id="usages", prompt="--- Usages ---")
   # no declarable children — the engine drives the record loop (see Questionnaire)
return QuestionGroup(id="core", children=sections)
```

Hints: the completed list (practice mapping × `image_tag`) is embedded in
the `base_image` prompt with the last entry as its default — the values
are data of the tree; the ENGINE renders them per the `image_defaults`
practice (list the lines, default the last, accept free-form).

**Edge Cases:**
- `project_name is None` → the `image` default is absent → the built-image
  prompt is required (click re-prompts on empty).
- unknown language at the engine (impossible — choice constrains) → no
  hints: plain free-form prompt.

### `assemble_session_plan`

**Responsibility**: one root — the core children plus the tool blocks.

**Algorithm:**
```
children = list(core.children); tools = []
reserved = {child.id for child in core.children}
for declaration in declarations:                      # enumeration order
    IF not declaration.questions: continue            # no block
    IF declaration.tool in reserved:
        logger.warning("tool %s skipped: its identity collides with the reserved section name %s",
                       declaration.tool, declaration.tool)
        continue                                       # whole block dropped (fix q2)
    seen = set(); survivors = []
    for item in declaration.questions:
        IF item.id in seen:
            logger.warning("element %s of tool %s dropped: repeated local name in the declaration",
                           item.id, declaration.tool)
            continue
        seen.add(item.id); survivors.append(item)
    children.append(QuestionGroup(id=declaration.tool,
                                  prompt=f"--- Tool: {declaration.tool} ---",
                                  children=survivors))
    tools.append(declaration.tool)
return SessionPlan(root=QuestionGroup(id="session", children=children), tools=tools)
```

**Edge Cases:**
- a tool whose every element was dropped by the repeated-name rule → an
  empty block is still appended with its heading; the engine suppresses
  empty headings; no answers record under it. (The block exists — the
  tool declared; only its duplicated elements were rejected.)

### `apply_skips`

**Responsibility**: remove the addressed subtrees as one set.

**Algorithm:**
```
blocks = {tool: [child.id for child in block_group.children] for tool in plan.tools}
targets = []
for tool, raw in skips:
    segs = raw.split(".")
    IF segs[0] in plan.tools:            address = segs                    # prefixed path
    ELIF segs[0] in core_section_ids:    address = segs                    # core path
    ELIF tool in blocks and segs[0] in blocks[tool]:
                                          address = [tool] + segs          # own-block local path
    ELSE:
        logger.warning("skip of tool %s is a no-op: %s resolves to nothing", tool, raw)
        continue
    IF resolves(plan.root, address):     targets.append(address)
    ELSE: warning no-op (as above)
new_root = rebuild_without(plan.root, targets)      # fresh groups along changed branches
return SessionPlan(root=new_root, tools=plan.tools)
```

`core_section_ids` = ids of the plan-root children that are NOT tool
blocks (`set(c.id for c in root.children) - set(plan.tools)`) — derived,
not hardcoded.

**Edge Cases:**
- descendant of a removed node → resolves in the original, silently
  absorbed by the set removal.
- path into a pairs question (`"build.env.SOME_KEY"`) → no children to
  resolve → no-op warning ("only the node as a whole").
- skip emptying a whole block → the block stays (empty); the engine
  suppresses the heading; the tool's section never records.

### `Questionnaire`

**Responsibility**: the interactive engine — asks the declarative records,
owns the core conditional patterns, records at plan paths.

**Algorithm:**
```
run(plan, answers):
  echo session header + wizard description
  tool_ids = set(plan.tools)
  for section in plan.root.children:
      IF section.id in tool_ids:
          IF section.children:                     # suppress emptied blocks
              ask_group(section, prefix=section.id)
      ELSE:
          survey_core_section(section, answers)
  # recording: every collected leaf records at its walked path

# Core-section rule: the patterns ask only the children present in the
# post-skip section — a skipped child is never asked; a branch whose driving
# question is absent collapses to the remaining path.
survey_core_section(section, answers):              # the conditional patterns
  language        → ask_question(choice)
  convention      → confirm gate ("Download base convention?"):
                       accept → prefill = ({"conventions": ".goga/usages/conventions.md"},
                                           "Use `conventions` for code writing rules and testing.")
                     reject → prefill = (None, None)
                     # gate answer NOT recorded (presentational)
  codemanifest    → usages pairs (default/prefill: prefill usages dict entries offered first),
                    annotations input (default/prefill: prefill text)
  build           → confirm gate ("Configure a build agent?"):
                       accept → the remaining children in order — agent choice,
                       then env pairs (each asked only when present;
                       suggested keys from agent_env_defaults[agent] prompted first,
                        then arbitrary KEY → value additions — old _collect_agent_env behavior)
                       reject → nothing recorded (block omitted at generation)
  docker_image    → IF the dockerfile question is absent (skipped) → no gate;
                       the pull branch directly: image ask with the hint
                       presentation when base_image is present (hint lines of
                       its prompt, default = last hint), else plain free-form
                       (default = the image record default when it carries one)
                     confirm gate ("Create Dockerfile?") otherwise:
                       accept → dockerfile input (default .goga/Dockerfile)
                                → base_image ask only when present
                                  (record at docker_image.base_image)
                                → image ask, plain label, default = record default
                                  (project:latest) → record at docker_image.image
                       reject → the pull branch as above (the hints of base_image
                                when present, else plain free-form)
  pipeline        → confirm gate ("Configure a pipeline agent?"): same shape as build
  tools           → confirm gate ("Register tools?"):
                       accept → pairs loop: name prompt, version prompt
                                (empty input → "latest"; the four forms documented in the
                                 prompt; grammar enforcement belongs to the install consumer)
  usages          → confirm gate ("Register usages?"):
                       accept → record loop per record: group, dependency name, git URL,
                                optional ref, optional root (empty → omitted);
                                accumulate {group: {dep: {git, ref?, root?}}} (later record
                                of the same group merges under the group key)
                     → record the accumulated mapping at "usages"

ask_question(question):
  choice  → click.prompt(question.prompt, type=click.Choice(question.choices))
  input   → click.prompt(question.prompt, default=question.default)   # None default → required
  confirm → click.confirm(question.prompt, default=question.default or False)
  pairs   → IF question.keys: confirm("Set proposed keys?") → prompt each proposed key
            then confirm("Add another?") loop → arbitrary key/value prompts
            return the accumulated dict (None → {} when nothing collected)
  ELSE    → an unknown kind or a missing required parameterization (a choice
            without choices): logger.warning naming the question path (its
            first segment is the tool identity) and the reason; the question
            is skipped — not asked, not recorded; the survey continues (tier 1)

ask_group(group, prefix=None):
  echo group.prompt as the heading (attribution for tool blocks)
  for child in group.children:
      value = ask_question(child) if Question else ask_group(child, …)
      record at the walked path
```

**Errors:** `click.Abort` (Ctrl-C / empty required prompt) propagates —
`InitLogic` exits 1 quietly.

**Edge Cases:**
- a tool block group with `prompt=None` (structural) → the engine still
  renders the attribution heading from the block id.
- free-form image input: any string accepted; the hints are suggestions
  only (old behavior preserved).
- a skipped child of a core section is never asked — the pattern asks the
  remaining children only; the docker_image branch collapses per the
  core-section rule (skipped `dockerfile` → the pull branch directly;
  skipped `base_image` → the FROM is never recorded).
- an unknown question kind or a missing required parameterization (a
  choice without `choices`) from a tool — a warning naming the question
  path; the question is skipped and never recorded; the survey continues
  (tier 1 soft, per the cross-cutting table's "bad declaration element").

### `FileGenerator`

**Responsibility**: write every artifact; the single write path of the
tool configs; never rewrite an existing config.yml.

**Algorithm:**
```
generate(answers, contributions):
  files = []
  IF Path(".goga/config.yml").is_file(): files_from_config = skip → jump to tool configs
  ELSE:
      snap = answers.snapshot()
      IF snap["docker_image"]["dockerfile"] present AND snap["docker_image"]["base_image"] present:
          write Dockerfile "FROM {base_image}\n" at that path; files.append(CreatedFile(path, None))
          # a Dockerfile without a FROM cannot be composed — a skipped base_image
          # collapses the branch; the config dockerfile field is emitted only
          # when the Dockerfile was written
      # generate_goga_config:
      IF language empty → clean ValueError naming "language"
      IF codemanifest usages carry "conventions":
          download per lang_conventions; on failure → clean error with URL and cause
          write .goga/usages/conventions.md; files.append(CreatedFile(path, None))
      assemble the ordered document per the mapping table; yaml.dump to .goga/config.yml
      files.append(CreatedFile(".goga/config.yml", None))
  for contribution in contributions:
      for file, data in contribution.files:            # call order
          write yaml to .goga/tools/{contribution.tool}/{file}
          files.append(CreatedFile(path, contribution.tool))
  return files
```

**Errors:**
- empty required `language` → `ValueError("required field language is empty")`
  → `InitLogic` renders one clean message, exit 1.
- conventions download failure → clean error with URL + cause; config.yml
  is NOT written on failure (old contract preserved).

**Edge Cases:**
- existing config.yml → only tool configs generate (the caller normally
  ends the session earlier; this guard protects direct consumers).
- `dockerfile` present without `base_image` (the base question was
  skipped) → no Dockerfile is written and the config omits the
  `dockerfile` field — a FROM line cannot be composed.
- same tool file buffered twice → the later buffer wins (replace).
- `usages` records with omitted ref/root → the loader's optional fields;
  `git` required by the survey loop (empty git re-prompted).

### `InitLogic`

**Responsibility**: orchestrate one session end to end.

**Algorithm:** the eight steps of the CODEMANIFEST, elaborated in the
trace above. Constructor stores the three collaborators (dependency
injection unchanged in style from the old logic.py).

**Errors:** the three tiers (see Cross-cutting Concerns). Every session
error is ONE `click.echo(f"Error: {exc}", err=True)` + `logger.error` —
no traceback ever reaches the user.

**Edge Cases:**
- zero invited tools and no installed tool packages → both moments are
  no-ops over an empty subscription list → the session degrades exactly
  to the plain behavior (`declarations == []`, `contributions == []`).

### `init` (goga/commands/init)

**Responsibility**: CLI wrapper — flag validation, mode routing, guard,
tool passthrough.

**Algorithm:** steps 1–6 of the CODEMANIFEST (see trace). The `-t/--tool`
option: `multiple=True`, help text mirroring `init.md`.

**Edge Cases:**
- `-t a -t b -t a` → invited `["a", "b"]` (dedup preserving first-seen
  order).
- `-t` with `--upgrade` → rejected before any filesystem work.
- `-t` with `<tpl>` → allowed (SCAFFOLD_THEN_ONBOARDING carries the
  invitation into the session).

---

## Cross-cutting Concerns

- **Error handling** — three tiers, strictly separated:
  1. *Tool failures* (a hook raising, a bad declaration element, an
     unknown skip path, an uninstalled invited name): soft —
     `logger.warning` naming the tool, the action, and the reason; the
     element/tool drops out; the session continues; the exit code is
     untouched.
  2. *Session errors* (broken package import, unreadable installed
     version, empty required language, conventions download failure): one
     clean `click.echo("Error: …", err=True)` + exit 1; never a
     traceback.
  3. *User aborts* (`click.Abort` — Ctrl-C, empty required prompt):
     exit 1, quiet (ported from the old `InitLogic.run`).
- **Logging**: stdlib `logging`, one module logger per file
  (`logger = logging.getLogger(__name__)`); warnings carry structured
  extras where the old code used them; pure records and `minor_version`
  never log.
- **Validation**: registration envelope (registrar, existing); the
  one-level declaration rule (at `declare`); repeated local names +
  reserved block names (at `assemble_session_plan`); skip paths (at
  `apply_skips`, no-op warnings); the question kind and its parameterization
  — at ask time, soft (a warning naming the question path; the question is
  skipped, never recorded); the four-form version grammar — NOT
  re-validated at survey time (prompt documents the forms; `resolve_version`
  at the install consumer owns the grammar); the written config passes the
  project-config loader.
- **Caching**: none — one registry per session (`build_once` idempotent);
  no cross-run state (platform invariant).
- **Concurrency**: single-threaded interactive CLI; no thread-safety
  requirements.

## Usages Analysis

### `convention` (.goga/usages/conventions.md)
- **What it provides**: mandatory code conventions — relative imports,
  dataclasses `kw_only=True`, docstring discipline, logging, REPL/test
  infrastructure.
- **Where used**: every changed/created cell (global Annotations + type
  annotations).
- **Why chosen**: project-wide practice.
- **How exactly**: frozen `kw_only` dataclasses for records; relative
  intra-package imports (`from .questions import Question` inside the
  leaves; `from .questions import …` in the facade); module docstrings in
  the established style (see old generator.py / delivery.py).

### `click` (.goga/usages/cooks/click.md)
- **What it provides**: the prompting cookbook for the interactive survey.
- **Where used**: `Questionnaire` (survey cell) — prompting, confirmation,
  choices, repeated collections.
- **Why chosen**: the survey is interactive on the host.
- **How exactly**: `click.prompt` / `click.confirm` / `click.Choice` per
  the old questionnaire.py patterns (`_collect_agent_env` is the template
  for the gated env pairs).

### `image_defaults` (inline, survey)
- **What it provides**: language → image-family mapping; tag completed at
  runtime; suggestions displayed; default = last entry; free-form
  accepted.
- **Where used**: `core_questions` (builds the completed hints),
  `Questionnaire` (renders them).
- **Why chosen**: the hints must match the installed minor.
- **How exactly**: hints embedded in the `base_image` prompt + default;
  the pull branch reuses the same completed values.

### `agent_env_defaults` (inline, survey)
- **What it provides**: agent → env key mapping for prompting.
- **Where used**: `Questionnaire` (build/pipeline env pairs).
- **Why chosen**: parity with the old `_AGENT_ENV_MAP`.
- **How exactly**: at pairs-ask time, the engine prompts the suggested
  keys of the selected agent, then offers arbitrary additions.

### `yaml` (inline, generator)
- **What it provides**: `yaml.dump(default_flow_style=False)` for config
  and tool files.
- **Where used**: `generate_goga_config`, `generate_tool_configs`.
- **Why chosen**: human-readable output, field order preserved.
- **How exactly**: `sort_keys=False, allow_unicode=True`; annotations via
  the `_LiteralStr` representer (ported).

### `lang_conventions` (inline, generator)
- **What it provides**: the conventions download URL template and target
  path.
- **Where used**: `generate_goga_config` step 3.
- **Why chosen**: unchanged behavior from the old generator.
- **How exactly**: `requests.get(url, timeout=30)`; failure → clean error
  with URL and cause.

### Imported Usages
- `minor-line` from `goga/version` — reading the installed version and
  deriving the tag; used by `InitLogic` annotations. Path:
  `goga/version/.usages/minor-line.md`.
- `survey-run` / `session-participation` / `artifact-generation` from the
  three leaves — used by `InitLogic` annotations (the facade documents the
  session API composition). Paths: `goga/onboarding/{survey,participation,generator}/.usages/*.md`.
- `question-records` from `goga/onboarding/questions` — imported by
  survey, participation, generator; the record structure and the answer
  addressing rules. Path: `goga/onboarding/questions/.usages/question-records.md`.
- `per-tool-delivery`, `registering-hooks` from `goga/hooks` — imported
  by participation; the staged delivery loop and the registration
  contract. Paths: `goga/hooks/.usages/{per-tool-delivery,registering-hooks}.md`.
- `onboarding-usage` from `goga/onboarding` — imported by
  goga/commands/init; the session API and the invitation semantics. Path:
  `goga/onboarding/.usages/onboarding-usage.md`.
- `scaffold-usage` from `goga/scaffold` — imported by goga/commands/init
  (unchanged).

## `.usages/` Update

### Cell: `goga/onboarding/questions`
- **`question-records.md`** → current after this stage's edit (the
  `SessionAnswers(tools=None)` entry updated). No further changes needed.

### Cell: `goga/onboarding/survey`
- **`survey-run.md`** → current after this stage's edit (reserved-names
  note added to `assemble_session_plan`). No further changes needed.

### Cell: `goga/onboarding/participation`
- **`session-participation.md`**, **`tool-contexts.md`** → current (match
  the contracts verbatim; the tool-context hook examples align with the
  delivery primitives).

### Cell: `goga/onboarding/generator`
- **`artifact-generation.md`** → current.

### Cell: `goga/onboarding` (facade)
- **`onboarding-usage.md`** → current (the facade import list matches the
  13 embeddings + `InitLogic`).

### Cell: `goga/version`
- **`minor-line.md`** → current.

### Cell: `goga/hooks`
- **`per-tool-delivery.md`** → current (imports `from goga.hooks import
  HookRegistry, wrap_context, build_hook_arguments` — enabled by this
  change).

### Cell: `goga/commands/init`
- **`init.md`** → current (syntax with `-t`, modes table, exit codes,
  anti-patterns).

## Test Stack Trace

### General Setup

- pytest; click testing via `CliRunner` for the command and the survey
  (existing project pattern — see tests/onboarding/test_questionnaire.py).
- `tmp_path` + `monkeypatch.chdir(tmp_path)` for every filesystem test
  (the repo CWD contains its own `.goga/` — see tests/onboarding/conftest.py
  `_clean_cwd`).
- Tool-package simulation: monkeypatch
  `goga.hooks.enumerate_tool_packages` (or `packages_distributions`) and
  register hooks directly through `HookRegistrar`/a fake facade module
  via `sys.modules` injection — the existing tests/hooks/conftest.py
  pattern.
- Caplog at WARNING for the warning-path assertions.

### Source File Registry

- goga/version/version.py, goga/hooks/catalog/catalog.py,
  goga/hooks/__init__.py
- goga/onboarding/questions/{questions.py, answers.py, __init__.py}
- goga/onboarding/participation/{declaration.py, contribution.py,
  participation.py, __init__.py}
- goga/onboarding/survey/{core.py, plan.py, questionnaire.py, __init__.py}
- goga/onboarding/generator/{generator.py, __init__.py}
- goga/onboarding/{logic.py, __init__.py}
- goga/commands/init/init.py
- Test layout: tests/onboarding/{questions, survey, participation,
  generator}/test_*.py; tests/onboarding/test_logic.py (facade),
  tests/onboarding/test_integration.py (end-to-end); old
  test_answers.py / test_generator.py / test_questionnaire.py are
  deleted with the old modules (their cases are ported into the new
  layout); tests/version/test_version.py and tests/hooks/* extended.

---

### Positive Tests

#### `test_minor_version_reduces_to_minor_line`

**Setup**: none (pure function).

**Input**: `minor_version("1.3.2")`.

**Trace**:
```
minor_version("1.3.2")
  → _release_segments("1.3.2")     # ("1", "3")
  → minor = "3"
  → f"1.3" returned
```

**Assertions**:
```
minor_version("1.3.2") == "1.3"
minor_version("1.2.1.dev3") == "1.2"
minor_version("1.2.0rc1") == "1.2"
minor_version("1.2.0.post1") == "1.2"
minor_version("1.2.0+local") == "1.2"
minor_version("2") == "2.0"
```

**Sufficiency**: pins the tag derivation every image hint consumes; a
regression here desyncs the host↔image minor agreement by construction.

#### `test_catalog_carries_onboarding_actions`

**Setup**: none.

**Input**: `declared_actions()`.

**Trace**:
```
declared_actions()
  → sorted(_DECLARED_ACTIONS, key=(domain, name))
  → [("onboarding","amend_config","soft"), ("onboarding","declare_session","soft"),
     ("statuses","register_statuses","soft")]
```

**Assertions**:
```
records = declared_actions()
("onboarding", "declare_session", "soft") in {(r.domain, r.name, r.error_class) for r in records}
("onboarding", "amend_config", "soft") in {…}
[ (r.domain, r.name) for r in records ] == sorted((r.domain, r.name) for r in records)
```

**Sufficiency**: without the records, every tool subscription of the two
onboarding actions is rejected as "unknown action" — the whole feature
dies at registration.

#### `test_hooks_facade_reexports_delivery_primitives`

**Setup**: none.

**Input**: `import goga.hooks`.

**Trace**:
```
import goga.hooks
  → from .dispatch import build_hook_arguments, wrap_context, emit_hook_event
  → from .tools import enumerate_tool_packages
  → __all__ contains the names
```

**Assertions**:
```
goga.hooks.wrap_context is goga.hooks.dispatch.wrap_context
goga.hooks.build_hook_arguments is goga.hooks.dispatch.build_hook_arguments
goga.hooks.enumerate_tool_packages is goga.hooks.tools.enumerate_tool_packages
{"wrap_context", "build_hook_arguments", "enumerate_tool_packages"} <= set(goga.hooks.__all__)
```

**Sufficiency**: the participation cell (and `per-tool-delivery.md`)
addresses the platform through the facade only — a missing re-export is
an ImportError in the whole onboarding domain.

#### `test_record_creates_nested_mappings`

**Setup**: `answers = SessionAnswers()`.

**Input**: `answers.record("build.agent", "claude")`.

**Trace**:
```
record("build.agent", "claude")
  → segments ["build", "agent"]; create _data["build"] = {}
  → _data["build"]["agent"] = "claude"
```

**Assertions**:
```
answers.snapshot() == {"build": {"agent": "claude"}}
```

**Sufficiency**: the no-dotted-keys invariant — the space must hold
nested mappings, or every downstream consumer (view, snapshot mapping)
breaks.

#### `test_amend_merges_mappings_replaces_scalars`

**Setup**: `answers.record("pipeline", {"agent": "codex", "env": {"A": "1"}})`.

**Input**: `answers.amend("pipeline", {"env": {"B": "2"}, "agent": "claude"})`.

**Trace**:
```
amend → leaf _data["pipeline"] is dict AND value is dict → recursive merge
  env: dict+dict → merge → {"A": "1", "B": "2"}
  agent: str → replace → "claude"
```

**Assertions**:
```
answers.snapshot() == {"pipeline": {"agent": "claude", "env": {"A": "1", "B": "2"}}}
```

**Sufficiency**: the amendment semantics are the tools' only write path
into shared sections — a wrong merge rule silently corrupts user answers.

#### `test_view_for_isolates_and_flattens`

**Setup**: `answers = SessionAnswers(tools=["my-tool", "viewer"])`;
`answers.record("language", "python")`;
`answers.record("my-tool.token", "t0")`;
`answers.record("viewer.flag", True)`.

**Input**: `view = answers.view_for("my-tool")`.

**Trace**:
```
view_for("my-tool")
  → core = {"language": "python"}          # my-tool and viewer keys excluded
  → own = {"token": "t0"} → core.update → {"language": "python", "token": "t0"}
  → deepcopy
```

**Assertions**:
```
view == {"language": "python", "token": "t0"}
"viewer" not in view and "flag" not in view     # other tool invisible
view["token"] = "mutated"; answers.snapshot()["my-tool"]["token"] == "t0"   # snapshot copy
```

**Sufficiency**: the isolation guarantee of the platform — a tool reading
another tool's answers (or mutating the space through its view) would be
a cross-tool data leak.

#### `test_collect_declarations_delivers_invitation_marker`

**Setup**: fake installed package `goga_tool_my-tool` (enumeration
monkeypatched) whose `register_hooks` subscribes
`("onboarding", "declare_session", "d1", hook)`; `ToolParticipation(invited=["my-tool"])`.

**Input**: `declarations = participation.collect_declarations()`.

**Trace**:
```
collect_declarations()
  → registry.build_once() → enumeration → registration → one subscription
  → groups {"my-tool": [sub]}
  → surface = ToolDeclaration(tool="my-tool", invited=True)
  → wrap_context + build_hook_arguments → hook(context=proxy)
    → hook: context.invited is True → context.declare(Question(id="token", …))
  → [surface]
```

**Assertions**:
```
len(declarations) == 1
declarations[0].tool == "my-tool" and declarations[0].invited is True
declarations[0].questions[0].id == "token"
```

**Sufficiency**: the invitation marker is the eligibility contract of
moment one — a broken marker either shows questions of an uninvited tool
or hides an invited one's.

#### `test_collect_contributions_commits_in_order`

**Setup**: two fake tools `goga_tool_alpha`, `goga_tool_beta` (alpha
enumerates first) each buffering `context.answer("tools", {"alpha":
"1.0"})` / `{"beta": "2.0"}` via `amend_config`; answers space with the
core `tools` section absent.

**Input**: `contributions = participation.collect_contributions(answers)`.

**Trace**:
```
collect_contributions(answers)
  → groups alpha, beta (enumeration order)
  → surfaces built with view_for(tool); hooks buffer amendments
  → commit: amend("tools", {"alpha": "1.0"}) then amend("tools", {"beta": "2.0"})
    → dict+dict → merge → {"alpha": "1.0", "beta": "2.0"}
```

**Assertions**:
```
[c.tool for c in contributions] == ["alpha", "beta"]
answers.snapshot()["tools"] == {"alpha": "1.0", "beta": "2.0"}
```

**Sufficiency**: delivery order is the tiebreaker for conflicting leaves
— the determinism of the commit pass is the whole point of staged
contributions.

#### `test_core_questions_builds_eight_sections_with_tag`

**Setup**: none (pure builder).

**Input**: `core_questions(image_tag="1.3", project_name="my-app",
convention_exists=False)`.

**Trace**:
```
core_questions("1.3", "my-app", False)
  → sections language, convention, codemanifest, build, docker_image, pipeline, tools, usages
  → base_image prompt contains "qarium/goga-python-3.14:1.3"; default is the last hint
  → image default "my-app:latest"
```

**Assertions**:
```
[child.id for child in core.children] == ["language","convention","codemanifest","build","docker_image","pipeline","tools","usages"]
base = the docker_image child with id "base_image"
"qarium/goga-python-3.14:1.3" in base.prompt and base.default == "qarium/goga-python-3.14:1.3"
image child default == "my-app:latest"
# convention_exists=True drops the section:
[child.id for child in core_questions("1.3", None, True).children][0] == "language" and "convention" not in …
```

**Sufficiency**: the dynamic tag is the feature's namesake — a
hardcoded `1.3` string here is exactly the regression the topic exists
to remove.

#### `test_assemble_session_plan_orders_blocks_and_drops_repeats`

**Setup**: core tree with sections `language`, `tools`; declaration of
`my-tool` with questions `[Question(id="token"), Question(id="token")]`;
declaration of `viewer` with one question; declaration of `empty-tool`
with no questions.

**Input**: `plan = assemble_session_plan(core, [d_my, d_viewer, d_empty])`.

**Trace**:
```
assemble → children = core children
  my-tool: second "token" dropped (warning) → block [token]
  viewer: block [q]
  empty-tool: no block
→ root children: language, tools, my-tool, viewer; tools ["my-tool", "viewer"]
```

**Assertions**:
```
[child.id for child in plan.root.children] == ["language", "tools", "my-tool", "viewer"]
plan.tools == ["my-tool", "viewer"]
my_block.children[0].id == "token" and len(my_block.children) == 1
```

**Sufficiency**: plan determinism + element-level rejection — the survey
and every skip path derive from this ordering.

#### `test_questionnaire_records_core_and_tool_answers`

**Setup**: plan from a minimal core (`language` choice) + `my-tool` block
(input `token`); `answers = SessionAnswers(tools=["my-tool"])`;
`runner = CliRunner()` with inputs `["python", "t0"]`.

**Input**: `Questionnaire().run(plan, answers)` under the runner.

**Trace**:
```
run → header → language section → ask_question(choice) → "python" → record("language", "python")
  → my-tool block → heading → ask_question(input) → "t0" → record("my-tool.token", "t0")
```

**Assertions**:
```
answers.snapshot() == {"language": "python", "my-tool": {"token": "t0"}}
```

**Sufficiency**: the path-addressing contract — tool answers must nest
under the reserved tool key, or isolation and generation both miss.

#### `test_generate_writes_dockerfile_then_config`

**Setup**: `_clean_cwd`; answers with
`docker_image = {"dockerfile": ".goga/Dockerfile", "base_image":
"qarium/goga-python-3.13:1.3", "image": "my-app:latest"}`, `language =
"python"`, no conventions entry; contributions `[]`.

**Input**: `files = FileGenerator().generate(answers, contributions)`.

**Trace**:
```
generate → snapshot → dockerfile present → write "FROM qarium/goga-python-3.13:1.3\n"
  → no conventions key → mkdir .goga → yaml.dump
→ files [CreatedFile(".goga/Dockerfile", None), CreatedFile(".goga/config.yml", None)]
```

**Assertions**:
```
Path(".goga/Dockerfile").read_text() == "FROM qarium/goga-python-3.13:1.3\n"
cfg = yaml.safe_load(Path(".goga/config.yml").read_text())
cfg["language"] == "python" and cfg["image"] == "my-app:latest"
cfg["dockerfile"] == ".goga/Dockerfile" and "base_image" not in cfg
[f.path for f in files] == [".goga/Dockerfile", ".goga/config.yml"] and all(f.tool is None for f in files)
```

**Sufficiency**: the FROM-line mapping ("never emitted to the config") and
the generation order are normative for build/pipeline consumers.

#### `test_generate_tool_configs_with_attribution`

**Setup**: `_clean_cwd`; `answers = SessionAnswers()` with the surveyed
core recorded: `answers.record("language", "python")` and no docker_image;
a committed contribution of `my-tool` with files
`[("service.yml", {"token_source": "env"}), ("service.yml", {"interval":
60})]` (same name twice — later wins).

**Input**: `FileGenerator().generate(answers, [contribution])`.

**Trace**:
```
generate → config written (minimal answers) → tool configs:
  .goga/tools/my-tool/service.yml ← {"interval": 60}   (second buffer replaced the first)
→ CreatedFile(".goga/tools/my-tool/service.yml", "my-tool")
```

**Assertions**:
```
yaml.safe_load(Path(".goga/tools/my-tool/service.yml").read_text()) == {"interval": 60}
last = files[-1]; last.tool == "my-tool" and last.path == ".goga/tools/my-tool/service.yml"
```

**Sufficiency**: the engine is the single write path of tool configs;
attribution feeds the final report.

#### `test_init_full_session_with_invited_tool`

**Setup**: `_clean_cwd`; fake `goga_tool_my-tool` installed (declare +
amend subscribed; declares `token` input, buffers `answer("tools",
{"my-tool": "latest"})` and `write_config("service.yml", {...})`);
CliRunner inputs for the whole survey.

**Input**: `runner.invoke(init_cli, ["-t", "my-tool", "-t", "my-tool"])`.

**Trace**:
```
init(tools=("my-tool","my-tool"))
  → ref/mode checks pass → dedup ["my-tool"] → no .goga/ → BARE_ONBOARDING
  → InitLogic(Questionnaire(), FileGenerator(), ToolParticipation(["my-tool"])).run()
     → declarations [token] → plan → survey (core + tool block) → contributions committed
     → files: config.yml (+ tools entry), .goga/tools/my-tool/service.yml → report → 0
```

**Assertions**:
```
result.exit_code == 0
cfg = yaml.safe_load(Path(".goga/config.yml").read_text()); cfg["tools"] == {"my-tool": "latest"}
Path(".goga/tools/my-tool/service.yml").exists()
"(tool: my-tool)" in result.output
```

**Sufficiency**: the end-to-end acceptance of the feature — invitation,
dedup, both moments, amendment into config, tool file, attributed report.

---

### Negative Tests

#### `test_minor_version_no_major_raises`

**Setup**: none.

**Input**: `minor_version("latest")`.

**Trace**:
```
minor_version("latest") → _release_segments → no numeric major → ValueError
```

**Assertions**:
```
with pytest.raises(ValueError): minor_version("latest")
```

**Sufficiency**: the error contract mirrors `resolve_version`'s shape
recognition — silent garbage would corrupt the tag.

#### `test_collect_declarations_warns_for_uninstalled_invited`

**Setup**: no tool packages installed (enumeration → `[]`);
`ToolParticipation(invited=["ghost"])`; caplog WARNING.

**Input**: `collect_declarations()`.

**Trace**:
```
build_once → no packages → no subscriptions
  → "ghost" not among installed → warning naming it
  → groups empty → []
```

**Assertions**:
```
declarations == []
any("ghost" in rec.message for rec in caplog.records) is True
```

**Sufficiency**: the invitation is opaque data at the command — the
warning is the only feedback a typo'd `-t` name ever gets.

#### `test_failing_hook_drops_whole_declaration`

**Setup**: fake tools `good` and `bad` subscribed to `declare_session`;
`bad`'s hook raises `RuntimeError("boom")` before declaring; `good`
declares one question; caplog.

**Input**: `collect_declarations()`.

**Trace**:
```
groups bad, good (enumeration order)
  bad → hook raises → warning ("bad", declare_session, boom) → dropped
  good → block stands
→ [good_declaration]
```

**Assertions**:
```
[d.tool for d in declarations] == ["good"]
any("bad" in r.message and "boom" in r.message for r in caplog.records)
```

**Sufficiency**: one tool's crash must never cancel another tool or the
session — the core softness guarantee.

#### `test_failing_hook_discards_files_with_amendments`

**Setup**: fake tool subscribed to `amend_config` whose hook buffers
`answer("tools", …)` and `write_config("x.yml", …)` then raises;
`_clean_cwd`; `answers = SessionAnswers()` with the surveyed core recorded:
`answers.record("language", "python")` (no docker_image — no Dockerfile).

**Input**: `collect_contributions(answers)` then `FileGenerator().generate(answers, [])`.

**Trace**:
```
hook buffers then raises → contribution discarded (amendments AND files)
→ [] returned; answers untouched; generate succeeds (config.yml written
from the recorded core) — nothing of the tool is written
```

**Assertions**:
```
contributions == []
"tools" not in answers.snapshot()
not Path(".goga/tools").exists()
```

**Sufficiency**: staged commit means a failed tool leaves NO trace —
half-committed state (files without amendments or vice versa) would
corrupt the project.

#### `test_broken_package_import_is_clean_session_error`

**Setup**: enumeration monkeypatched to a package whose facade raises on
import (`call_register_hooks` → platform-wrapped `ImportError`);
`_clean_cwd`.

**Input**: `InitLogic(...).run()` (or the CLI invocation).

**Trace**:
```
collect_declarations → build_once → ImportError("package goga_tool_broken failed to import: …")
  → propagates out of collect_declarations
  → InitLogic catches → click.echo("Error: …") → return 1
```

**Assertions**:
```
result.exit_code == 1
"Error:" in result.output and "goga_tool_broken" in result.output
"Traceback" not in result.output
```

**Sufficiency**: the single fatal case must be a named clean message —
a traceback here is the canonical session-error violation.

#### `test_generate_empty_language_is_clean_error`

**Setup**: `_clean_cwd`; answers snapshot without `language`;
contributions `[]`.

**Input**: `FileGenerator().generate(answers, [])`.

**Trace**:
```
generate_goga_config → language empty → ValueError("language")
  → InitLogic tier renders one message, exit 1
```

**Assertions**:
```
with pytest.raises(ValueError, match="language"): FileGenerator().generate(answers, [])
not Path(".goga/config.yml").exists()
```

**Sufficiency**: the required-field gate is the last line of defense for
config validity; the file must not appear on failure.

#### `test_conventions_download_failure_names_url`

**Setup**: `_clean_cwd`; answers with `language="python"` and
`codemanifest={"usages": {"conventions": ".goga/usages/conventions.md"}}`;
`requests.get` monkeypatched to raise `requests.ConnectionError("down")`.

**Input**: `FileGenerator().generate(answers, [])`.

**Trace**:
```
conventions key present → url = …/python/project.md → get raises
  → clean error f"Failed to download convention from {url}: down"
  → config.yml NOT written
```

**Assertions**:
```
with pytest.raises(RuntimeError, match="https://raw.githubusercontent.com/.*/python/project.md"):
    FileGenerator().generate(answers, [])
not Path(".goga/config.yml").exists()
```

**Sufficiency**: network failure at onboarding must be diagnosable (URL +
cause) and non-destructive (no half-config).

#### `test_init_rejects_tools_with_upgrade`

**Setup**: CliRunner; a directory with `.goga/scaffold.yml` present or
not (irrelevant — rejected before any work).

**Input**: `runner.invoke(init_cli, ["--upgrade", "-t", "my-tool"])`.

**Trace**:
```
init(upgrade=True, tools=("my-tool",))
  → ref None → mode UPGRADE (no tpl) → tools non-empty + UPGRADE
  → echo "-t/--tool requires an onboarding session and --upgrade runs none" → exit 1
```

**Assertions**:
```
result.exit_code == 1
"-t/--tool requires an onboarding session" in result.output
```

**Sufficiency**: the new flag combination's guard — running upgrade with
a silently dropped invitation would be the confusing alternative.

---

### Edge Case Tests

#### `test_init_dedup_preserves_flag_order`

**Setup**: CliRunner; stubbed InitLogic capturing the constructed
ToolParticipation.

**Input**: `["-t", "b", "-t", "a", "-t", "b"]`.

**Trace**:
```
tools ("b","a","b") → dedup ["b","a"] → ToolParticipation(invited=["b","a"])
```

**Assertions**:
```
captured.invited == ["b", "a"]
```

**Sufficiency**: one invitation per name, one block per tool, first-seen
order — the plan ordering derives from it.

#### `test_view_for_unknown_tool_returns_core_only`

**Setup**: `SessionAnswers(tools=["my-tool"])` with core + `my-tool`
answers recorded.

**Input**: `view_for("not-declared")`.

**Trace**: own section absent → core only.

**Assertions**:
```
view == {"language": "python"}          # no "not-declared" key, no tool sections
```

**Sufficiency**: a tool subscribing only to `amend_config` (no moment
one) still gets a lawful view.

#### `test_assemble_reserved_name_drops_block`

**Setup**: core tree with section `tools`; declaration of a tool with
identity `tools` and one question; caplog.

**Input**: `assemble_session_plan(core, [declaration])`.

**Trace**:
```
"tools" in reserved → warning naming the tool and the reserved name → no block
```

**Assertions**:
```
plan.tools == [] and [c.id for c in plan.root.children] == ["tools"]   # core only
any("tools" in r.message for r in caplog.records)
```

**Sufficiency**: the collision fix (q2) — without the guard, two `tools`
children merge answers of the core section and the tool block.

#### `test_apply_skips_prefixed_own_and_unknown`

**Setup**: plan with core `language` + `build` sections and blocks
`my-tool` (`reporting` group with `enabled`) and `viewer` (`opt`);
skips `[("my-tool", "reporting.enabled"), ("viewer", "my-tool.reporting.enabled"),
("viewer", "language"), ("my-tool", "no.such.path")]`.

**Input**: `plan2 = apply_skips(plan, skips)` (caplog).

**Trace**:
```
("my-tool","reporting.enabled") → own-block: address my-tool.reporting.enabled → removed
("viewer","my-tool.reporting.enabled") → prefixed → already removed? resolves in ORIGINAL → removed (same node)
("viewer","language") → core → language section removed
("my-tool","no.such.path") → unresolvable → warning no-op
```

**Assertions**:
```
ids of plan2.root.children: "language" absent, "build" present, "my-tool" present (emptied group), "viewer" present
"enabled" not reachable under my-tool block
any("no.such.path" in r.message for r in caplog.records)
```

**Sufficiency**: the three-way resolution rule + set semantics +
absorbed-descendant silence — the most intricate rule of the plan layer.

#### `test_existing_config_ends_session_silently`

**Setup**: `_clean_cwd` with `.goga/config.yml` pre-created (content
irrelevant); stubbed collaborators asserting no calls.

**Input**: `InitLogic(Questionnaire(), FileGenerator(),
ToolParticipation([])).run()`.

**Trace**:
```
run → Path(".goga/config.yml").is_file() → return 0 immediately
```

**Assertions**:
```
result == 0
questionnaire.run not called; participation.collect_declarations not called; generator.generate not called
```

**Sufficiency**: "whoever created it first wins" — after a copier
template brings a config, onboarding must be a silent no-op (no events,
no prompts).

#### `test_unreadable_version_is_clean_error`

**Setup**: `_clean_cwd`; `host_goga_version` monkeypatched to raise
`PackageNotFoundError("goga")`.

**Input**: `InitLogic(...).run()`.

**Trace**:
```
run → host_goga_version raises → clean message → return 1
```

**Assertions**:
```
result == 1 and "Error:" in output and "Traceback" not in output
```

**Sufficiency**: the metadata boundary tier — an uninstalled-host
scenario must not traceback.

#### `test_tool_failure_never_changes_exit_code`

**Setup**: full-session setup of the positive end-to-end test, with the
tool's `amend_config` hook raising instead of contributing.

**Input**: CLI invocation with `-t my-tool`.

**Trace**:
```
moment two → hook raises → contribution discarded with warning → generate (no tool files) → 0
```

**Assertions**:
```
result.exit_code == 0
not Path(".goga/tools/my-tool").exists()
warning named the tool in caplog
```

**Sufficiency**: "the softness of the tool moments is theirs" — the
session's success is independent of any tool's failure.

#### `test_declare_rejects_nested_group_with_warning`

**Setup**: `surface = ToolDeclaration(tool="t", invited=True)`; a group
whose children contain another group; caplog.

**Input**: `surface.declare(QuestionGroup(id="deep", children=[QuestionGroup(id="inner")]))`.

**Trace**:
```
declare → one-level rule violated → warning naming the tool → not buffered
```

**Assertions**:
```
surface.questions == []
any("one nesting level" in r.message for r in caplog.records)
and any("t" in r.message for r in caplog.records)
```

**Sufficiency**: the tree-shape bound of tool declarations — a deeper
tree would break the engine's simple survey and the answer nesting rules.

#### `test_noninvited_subscribed_tool_is_marked_and_silent`

**Setup**: fake installed `goga_tool_my-tool` subscribed to BOTH actions;
the hook bodies record the marker into their `self` context
(`self.saw_invited = context.invited`) and would declare a question only
when `context.invited` (the contract early return); `ToolParticipation(invited=["other"])`;
`answers = SessionAnswers()`; caplog at WARNING.

**Input**: `declarations = p.collect_declarations()`; then
`contributions = p.collect_contributions(answers)`.

**Trace**:
```
build_once → one subscription per action → groups {"my-tool": […]}
  moment one: surface = ToolDeclaration(tool="my-tool", invited=False)
    → hook reads context.invited → False → immediate return, no member called
    → empty buffer → no block in the plan (assemble skips it)
  moment two: surface = ToolContribution(tool="my-tool", invited=False,
    answers=core-only view) → same immediate return → empty buffers
```

**Assertions**:
```
declarations == []                       # empty buffer → contributes no block
[c.tool for c in contributions] == ["my-tool"]
contributions[0].amendments == [] and contributions[0].files == []
the captured self-context marker is False
"my-tool" not in answers.snapshot()      # nothing recorded, nothing amended
not caplog.records                       # silent participation — not a warning
```

**Sufficiency**: the False marker is the eligibility contract of both
moments — a regression to an always-True marker leaks an uninvited tool's
questions into every session, and no other test of the design would
catch it (delivery is never filtered by invitation per the
`per-tool-delivery` practice).

#### `test_skip_of_base_image_collapses_dockerfile_branch`

**Setup**: `_clean_cwd`; fake installed `goga_tool_my-tool` (subscribed,
invited) whose `declare_session` hook calls only
`context.skip("docker_image.base_image")`; CliRunner inputs walking the
survey: language `python`, every confirm gate `n` except the Dockerfile
gate `y`, dockerfile path default (empty input), built image name
`my-app:latest`.

**Input**: `runner.invoke(init_cli, ["-t", "my-tool"])`.

**Trace**:
```
collect_declarations → skip buffered ("my-tool", "docker_image.base_image")
  → apply_skips removes the base_image question from the docker_image section
  → survey: docker gate accepted → dockerfile asked (default) → base_image
    NOT asked (absent from the tree) → image asked plain (default my-app:latest)
  → snapshot: docker_image = {dockerfile, image} — no base_image
  → generate: dockerfile present BUT base_image absent → no Dockerfile;
    config omits the dockerfile field → report → 0
```

**Assertions**:
```
result.exit_code == 0
"Base image" not in result.output
cfg = yaml.safe_load(Path(".goga/config.yml").read_text())
cfg["image"] == "my-app:latest" and "dockerfile" not in cfg and "base_image" not in cfg
not Path(".goga/Dockerfile").exists()
```

**Sufficiency**: pins the partial-skip semantics of the docker_image
branch — the contract invariant "a skipped subtree is never asked" plus
the FROM-composition rule; without it an implementer either asks the
removed question or composes a Dockerfile with no base image.

#### `test_unknown_kind_is_skipped_with_warning`

**Setup**: plan with a `my-tool` block carrying
`Question(id="bad", kind="text", prompt="Weird")` and
`Question(id="ok", kind="input", prompt="Token")`;
`answers = SessionAnswers(tools=["my-tool"])`; `runner = CliRunner()` with
input `["t0"]`; caplog at WARNING.

**Input**: `Questionnaire().run(plan, answers)` under the runner.

**Trace**:
```
run → my-tool block → ask_group → ask_question(bad):
  kind "text" matches no branch → warning naming "my-tool.bad" → skipped, not recorded
  → ask_question(ok): input → "t0" → record("my-tool.ok", "t0")
```

**Assertions**:
```
answers.snapshot() == {"my-tool": {"ok": "t0"}}
any("my-tool.bad" in r.message for r in caplog.records)
"Weird" not in result.output
```

**Sufficiency**: the soft principle for a bad declaration element —
without the defined branch the survey dies as a tier-2 session error,
contradicting the cross-cutting tier table.

---

## Additional Instructions for the Implementation Agent

- Delete `goga/onboarding/answers.py`, `goga/onboarding/questionnaire.py`,
  `goga/onboarding/generator.py` together with creating the leaf cells —
  the facade must never expose `InitAnswers`/`GogaConfigAnswers` again;
  port (not rewrite from scratch) the old prompt texts and the
  `_collect_agent_env`, `_IMAGE_MAP` (now completed with the tag),
  `_AGENT_ENV_MAP`, `_LiteralStr`, conventions-download logic into the
  new modules.
- Re-export surface of the facade `goga/onboarding/__init__.py`: the 13
  embedded types + `InitLogic`, in the embedding order of the
  CODEMANIFEST; docstring states the domain-facade role.
- Implementation order: the dependency order of the Design (version →
  catalog → hooks facade → questions → participation → survey →
  generator → onboarding facade → commands/init); after each cell run
  its tests, at the end run `goga lint` (must stay 0 errors) and the
  full pytest suite.
- The `usages`/`tools` core sections are NEW user-facing survey sections
  (the old wizard had neither) — keep prompt texts aligned with
  `init.md`'s created-files list.
- `goga hooks` output gains the two onboarding rows automatically from
  the catalog — no CLI change.
- Do not add the `review` section (a future additive core section,
  explicitly out of scope).
