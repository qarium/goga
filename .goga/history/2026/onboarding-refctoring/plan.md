# Plan: `onboarding-refctoring` — extensible `goga init` onboarding (tool participation via hooks actions + dynamic image tag)

## Purpose

Materialize the contracts of the topic «Расширяемый онбординг `goga init`: участие
тулз через hooks-действия и динамический тег образов» into code: the four new
onboarding leaf cells (questions, participation, survey, generator), the
rewritten onboarding domain facade with the new `InitLogic`, the CLI `-t/--tool`
invitation flag, the `minor_version` tag routine, the two onboarding catalog
records, and the three hooks-facade re-exports.

After implementation the package provides:
- a declarative question-and-answer model (`Question`, `QuestionGroup`,
  `SessionAnswers`) shared by every session participant;
- per-tool participation in the session through the two hooks actions
  (`onboarding/declare_session`, `onboarding/amend_config`) delivered per tool
  with staged control and isolated answer views;
- a survey engine that asks the declarative records (core sections + tool
  blocks) and records answers at plan dot-paths;
- artifact generation from the committed answer space (Dockerfile, config.yml,
  conventions download, tool configs) with attribution;
- image hints completed with the runtime minor tag — never a hardcoded tag;
- `goga init [-t name]...` with dedup, invitation validation, and opaque
  passthrough.

The most important gaps between contract and code: none of the four leaf cells
exists yet (only CODEMANIFESTs); the old flat `InitAnswers`/`GogaConfigAnswers`
model, the old per-field `Questionnaire.ask_*` engine, and the old
`FileGenerator.generate(answers)` API must be replaced (modules deleted, logic
ported); `goga.hooks` does not yet re-export the delivery primitives; the
catalog carries no onboarding records; `minor_version` does not exist; the
`init` command has no `-t` flag.

Overall implementation strategy: dependency order leaves → root
(version → hooks catalog → hooks facade → questions → participation → survey →
generator → onboarding facade → commands/init), TDD per coding task, full
suite + `goga lint` at the end. The old modules are deleted in the facade
rewrite task — never earlier (the old facade imports them until then).

## Context

### Contract Surface

**Entity: `minor_version(version: str) -> minor: str`**
- Type: function (Routine)
- Declared `location`: `goga/version/version.py`
- Facade obligation: must be importable from `goga.version`
- Properties/Methods: none (routine)
- Semantic requirements from descriptions: reduce a version string to its `N.M`
  line; reuse the module-private `_release_segments` reducer (version.py:71);
  a missing minor segment is treated as `"0"`; an argument with no leading
  numeric major raises `ValueError` (message from the shared reducer); pure
  function — deterministic, no I/O, no logging; richer tails reduce silently
  (`1.2.1.dev3`, `1.2.0rc1`, `1.2.0.post1`, `1.2.0+local` → `1.2`); do not
  read the installed version — the caller owns the metadata boundary
- Imported dependencies: none
- Annotation context: `convention` practice (docstring style, pure-function
  discipline); mirrors `resolve_version`'s shape recognition

**Entity: `declared_actions()` data change (+2 records)**
- Type: data change in `goga/hooks/catalog/catalog.py` (`_DECLARED_ACTIONS`)
- Facade obligation: re-exported through `goga.hooks` (already present —
  `from .catalog import declared_actions`)
- Semantic requirements: add
  `Action(domain="onboarding", name="declare_session", error_class="soft")`
  and `Action(domain="onboarding", name="amend_config", error_class="soft")`;
  published records are never rewritten (the statuses record is untouched);
  ordering stays domain-then-name (`onboarding/amend_config`,
  `onboarding/declare_session`, `statuses/register_statuses`); the catalog
  stays supported-data only
- Annotation context: catalog contract Requirements already list all three
  records — the code must now match

**Entity: `goga.hooks` facade re-exports (+3)**
- Type: re-export (embeddings `->wrap_context: {}`, `->build_hook_arguments: {}`, `->enumerate_tool_packages: {}`)
- Declared `location`: `goga/hooks/__init__.py`
- Facade obligation: `wrap_context`, `build_hook_arguments` importable from
  `goga.hooks` (source `goga/hooks/dispatch`), `enumerate_tool_packages`
  importable from `goga.hooks` (source `goga/hooks/tools`); all three in
  `__all__`
- Semantic requirements: both sub-facades already export them
  (dispatch/__init__.py, tools/__init__.py verified); importing `goga.hooks`
  imports no `goga_tool_*` package and enumerates nothing (facade docstring
  invariant holds); no local name shadows the imports; the existing
  `declared_actions` re-export is untouched

**Entity: `Question(id, kind, prompt, choices=None, default=None, keys=None)`**
- Type: class (Entity, frozen dataclass `kw_only=True`)
- Declared `location`: `goga/onboarding/questions/questions.py`
- Facade obligation: must be importable from `goga.onboarding.questions (and
  re-exported by `goga.onboarding`)
- Properties: `id -> str` (local name, unique among siblings), `kind -> str`
  (choice | input | confirm | pairs), `prompt -> str`, `choices ->
  list[str] | None`, `default -> str | bool | None`, `keys -> list[str] | None`
- Semantic requirements: the record carries data only — rendering and answer
  validation belong to the survey engine; the kind fixes the parameterization
  (`choices` for choice, `default` for input/confirm, `keys` for pairs);
  answer values: choice/input — string, confirm — boolean, pairs — mapping of
  strings; no validation at construction (kinds are checked at ask time)
- Annotation context: `convention` data-model rules

**Entity: `QuestionGroup(id, prompt=None, children=None)`**
- Type: class (Entity, frozen dataclass `kw_only=True`)
- Declared `location`: `goga/onboarding/questions/questions.py`
- Facade obligation: importable from `goga.onboarding.questions` (and `goga.onboarding`)
- Properties: `id -> str`, `prompt -> str | None` (None for a purely structural
  node), `children -> list[Question | QuestionGroup] | None`
- Semantic requirements: the tree path (ids from root joined by dots) addresses
  the node in skip requests and answer paths; a group's answer value is a
  nested mapping keyed by child ids — never a flat dotted key; a tool-declared
  group is limited to one nesting level with simple children

**Entity: `SessionAnswers(tools: list[str] | None = None)`**
- Type: class (Entity — the single mutable accumulator of one run)
- Declared `location`: `goga/onboarding/questions/answers.py`
- Facade obligation: importable from `goga.onboarding.questions` (and `goga.onboarding`)
- Methods:
  - `record(id: str, value: str | bool | dict) -> None` — resolve `id`
    segment by segment creating intermediate mappings; set the value at the
    leaf; recording REPLACES (never merges)
  - `amend(id: str, value: str | bool | dict) -> None` — same walk; an
    existing mapping at the leaf merges recursively with `value`; scalars and
    lists replace; an absent leaf is created; silent
  - `view_for(tool: str) -> view: dict` — core section (every top-level key
    except the reserved tool-section names given at construction) plus the
    tool's own section re-keyed by local names without the tool prefix; a deep
    copy — a snapshot; other tools never present
  - `snapshot() -> view: dict` — deepcopy of the complete nested structure
- Semantic requirements: created empty — `tools` reserves the top-level keys
  without creating them; nested mappings only, no dotted keys ever stored;
  amendments apply in delivery order — a later amendment wins at every
  conflicting leaf; substituting a user's answer is silent
- Edge semantics: `record` over an existing scalar with a deeper path replaces
  the scalar with an intermediate mapping (the survey is authoritative);
  `view_for` of a tool without a recorded section → core-only view; a local
  name colliding with a core key wins in THAT tool's view only (update order)

**Entity: `ToolDeclaration(tool: str, invited: bool)`**
- Type: class (Entity — moment-one surface + buffer)
- Declared `location`: `goga/onboarding/participation/declaration.py`
- Facade obligation: importable from `goga.onboarding.participation` (and `goga.onboarding`)
- Properties: `tool -> str`, `invited -> bool`, `questions ->
  list[Question | QuestionGroup]` (declaration order), `skips -> list[str]`
- Methods: `declare(item)` — buffer one question or one-level group; a group
  whose children contain a `QuestionGroup` is refused with a logged warning
  naming the tool and the reason, the element is NOT buffered (structural
  violations are warnings, never exceptions); `skip(path)` — append the raw
  path string, no resolution here
- Semantic requirements: a hook of a non-invited tool returns immediately — no
  member is called; buffered data is read by the engine after delivery; a hook
  is never called to survey

**Entity: `ToolContribution(tool: str, invited: bool, answers: dict)`**
- Type: class (Entity — moment-two surface + staged buffer)
- Declared `location`: `goga/onboarding/participation/contribution.py`
- Facade obligation: importable from `goga.onboarding.participation` (and `goga.onboarding`)
- Properties: `tool -> str`, `invited -> bool`, `answers -> dict` (the isolated
  view), `amendments -> list[tuple[str, str | bool | dict]]` (call order),
  `files -> list[tuple[str, dict]]` (call order)
- Methods: `answer(id, value)` — buffer one amendment; `write_config(file,
  data)` — buffer one config file; the engine serializes and writes — a tool
  never writes its config files itself; writing the same file again replaces
  at write time
- Semantic requirements: the contribution is staged — buffered amendments and
  files apply only after every hook of the tool completed without failure; the
  view carries nothing of the other tools

**Entity: `ToolParticipation(invited: list[str])`**
- Type: class (Entity — mediator of both onboarding action moments)
- Declared `location`: `goga/onboarding/participation/participation.py`
- Facade obligation: importable from `goga.onboarding.participation` (and `goga.onboarding`)
- Properties: `invited -> list[str]` (deduplicated, flag order — defensive
  dedup in the constructor via `list(dict.fromkeys(invited))`)
- Methods:
  - `collect_declarations() -> list[ToolDeclaration]` — build the run registry
    once (`HookRegistry()`; `build_once()`; `ImportError` propagates — the
    single fatal case); warn for every invited identity not among
    `enumerate_tool_packages()` naming it; group
    `registry.subscriptions_for("onboarding", "declare_session")` per tool
    preserving enumeration order; per tool: `surface = ToolDeclaration(tool,
    invited=tool in self._invited)`, `proxy = wrap_context(surface)`, per
    subscription `hook(**build_hook_arguments(hook, proxy,
    registry.self_context(tool)))`; any `Exception` from a hook of the tool →
    the whole declaration is discarded with a warning naming tool, action,
    reason; return surviving declarations in enumeration order
  - `collect_contributions(answers: SessionAnswers) -> list[ToolContribution]`
    — same delivery over `subscriptions_for("onboarding", "amend_config")`
    with `surface = ToolContribution(tool, invited, answers=answers.view_for(tool))`;
    a failing hook discards the tool's whole contribution (amendments AND
    files) with a warning; commit pass in enumeration order:
    `answers.amend(path, value)` per buffered amendment; return the committed
    contributions
- Semantic requirements: every warning names the tool, the action, and the
  reason; an invited tool without a subscription participates silently; a
  subscribed tool without an invitation receives the not-invited marker (the
  hook returns immediately — the marker is never filtered by the platform);
  `_registry` is built lazily and shared by both moments
- Imported dependencies: `Question`, `QuestionGroup`, `SessionAnswers` +
  `question-records` usage (from `goga/onboarding/questions`); `HookRegistry`,
  `wrap_context`, `build_hook_arguments`, `enumerate_tool_packages` +
  `per-tool-delivery`, `registering-hooks` usages (from `goga/hooks`)

**Entity: `core_questions(image_tag: str, project_name: str | None, convention_exists: bool) -> tree: QuestionGroup`**
- Type: function (Routine)
- Declared `location`: `goga/onboarding/survey/core.py`
- Facade obligation: importable from `goga.onboarding.survey` (and `goga.onboarding`)
- Semantic requirements: build the eight sections in survey order — `language`
  (choice, order python/golang/kotlin/swift/javascript), `convention` (only
  when `convention_exists` is False; a confirm `adopt` with default False),
  `codemanifest` (usages pairs + annotations input), `build` (agent choice +
  env pairs), `docker_image` (dockerfile input default `.goga/Dockerfile`,
  base_image input with the tag-completed hints embedded in the prompt and
  default = LAST hint, image input with default `f"{project_name}:latest"` or
  no default when the name is None), `pipeline` (agent choice + env pairs),
  `tools` (pairs: name → version; empty version reads as latest; the four
  grammar forms documented in the prompt), `usages` (structural group, no
  declarable children — the engine drives the record loop); return
  `QuestionGroup(id="core", children=sections)` — the root id is never
  addressed in answers; the tag is never hardcoded (completed from
  `image_tag` via the `image_defaults` practice mapping)
- Imported dependencies: `Question`, `QuestionGroup` (from questions cell)

**Entity: `assemble_session_plan(core: QuestionGroup, declarations: list[ToolDeclaration]) -> plan: SessionPlan`**
- Type: function (Routine)
- Declared `location`: `goga/onboarding/survey/plan.py`
- Facade obligation: importable from `goga.onboarding.survey` (and `goga.onboarding`)
- Semantic requirements: `children = list(core.children)`; `reserved = {child.id
  for child in core.children}` (derived from the RECEIVED core — no hardcoded
  name list); per declaration in enumeration order: empty `questions` → no
  block; `declaration.tool in reserved` → warning naming the tool and the
  reserved name, the whole block is dropped (fix q2); local-name dedup within
  the declaration (a repeated id drops THAT element with a warning naming the
  tool and the reason; survivors stand); append `QuestionGroup(id=tool,
  prompt=f"--- Tool: {tool} ---", children=survivors)` and `tools.append(tool)`;
  return `SessionPlan(root=QuestionGroup(id="session", children=children),
  tools=tools)` — a fresh root, the core tree is never mutated; a tool whose
  every element was dropped still gets its (empty) block appended

**Entity: `apply_skips(plan: SessionPlan, skips: list[tuple[str, str]]) -> plan: SessionPlan`**
- Type: function (Routine)
- Declared `location`: `goga/onboarding/survey/plan.py`
- Facade obligation: importable from `goga.onboarding.survey` (and `goga.onboarding`)
- Semantic requirements: resolve every raw path against the ORIGINAL root:
  `segments[0]` a tool identity in `plan.tools` → address is the full path;
  ELIF `segments[0]` a core section id → address is the path from the root;
  ELIF `segments[0]` a local name of the DECLARING tool's own block → address
  is `[tool] + segments`; ELSE → warning no-op; existence is checked against
  the original tree only (a descendant of an already-skipped node resolves and
  is silently absorbed — set semantics, order-independent); rebuild new
  `QuestionGroup`s along removed branches, share frozen originals on
  unmodified branches; return a NEW `SessionPlan` with the same `tools` list
  (an emptied block stays); a path into a pairs question has no children to
  resolve → no-op warning; `core_section_ids` derived as
  `set(c.id for c in root.children) - set(plan.tools)`

**Entity: `SessionPlan(root: QuestionGroup, tools: list[str])`**
- Type: class (Entity, data record)
- Declared `location`: `goga/onboarding/survey/plan.py`
- Facade obligation: importable from `goga.onboarding.survey` (and `goga.onboarding`)
- Properties: `root -> QuestionGroup` (core children followed by tool blocks),
  `tools -> list[str]` (participating tools in block order)

**Entity: `Questionnaire()`**
- Type: class (Entity — the interactive survey engine)
- Declared `location`: `goga/onboarding/survey/questionnaire.py`
- Facade obligation: importable from `goga.onboarding.survey` (and `goga.onboarding`)
- Methods:
  - `run(plan: SessionPlan, answers: SessionAnswers) -> None` — echo the
    session header (`=== Goga Project Initialization ===` + wizard
    description, ported from the old `ask`); iterate `plan.root.children` in
    order; membership in `plan.tools` distinguishes tool blocks (echo the
    block prompt as the attribution heading, then `ask_group` with prefix =
    the tool id; suppress emptied blocks) from core sections
    (`survey_core_section`); records land at plan dot-paths (`"{tool}.{local}"`
    for tool answers); `click.Abort` propagates
  - `ask_question(question: Question) -> value` — choice →
    `click.prompt(prompt, type=click.Choice(choices))`; input →
    `click.prompt(prompt, default=default)` (None default → required);
    confirm → `click.confirm(prompt, default=default or False)`; pairs →
    proposed-keys confirm + per-key prompts, then an add-another loop of
    arbitrary key/value prompts (return `{}` when nothing collected); ELSE
    (unknown kind or missing parameterization such as a choice without
    `choices`) → `logger.warning` naming the question path (first segment is
    the tool identity) and the reason; the question is skipped — not asked,
    not recorded; the survey continues (tier 1 soft)
  - `ask_group(group: QuestionGroup, prefix: str | None = None) -> dict` —
    echo the group prompt as heading; children in order; recurse into
    groups. The optional `prefix` (the tool id) qualifies the record paths
    (`"{tool}.{local}"`); with the default `None` the declared
    one-argument call shape of the CODEMANIFEST
    (`ask_group(group) -> value: dict`) stays valid — matching the design's
    `ask_group(group, prefix=None)`
- Core-section conditional patterns (the engine's own logic — port the old
  per-field ask methods here): confirm gates are presentational (asked, drive
  control flow, NEVER recorded); only the children PRESENT in the post-skip
  section are asked — a skipped child is never asked; a branch whose driving
  question is absent collapses to the remaining path:
  - `language` → choice ask
  - `convention` → confirm gate; accept → prefill
    `({"conventions": ".goga/usages/conventions.md"}, "Use \`conventions\` for
    code writing rules and testing.")` for codemanifest; reject → `(None, None)`
  - `codemanifest` → usages pairs (prefill entries offered first), annotations
    input (prefill text)
  - `build` → confirm gate; accept → agent choice then env pairs (suggested
    keys from `agent_env_defaults[agent]` prompted first, then arbitrary
    additions — the old `_collect_agent_env` behavior); reject → nothing
    recorded
  - `docker_image` → IF the dockerfile question is absent (skipped) → no
    gate, the pull branch directly (image ask with hint presentation when
    base_image is present, else plain free-form); ELSE confirm gate
    ("Create Dockerfile?"): accept → dockerfile input → base_image ask only
    when present → image ask (plain label, record default); reject → the pull
    branch; a skipped `base_image` collapses the FROM — never asked, never
    recorded
  - `pipeline` → confirm gate, same shape as build
  - `tools` → confirm gate; accept → pairs loop (name prompt, version prompt;
    empty input → "latest")
  - `usages` → confirm gate; accept → record loop per record (group,
    dependency name, git URL, optional ref, optional root; empty → omitted);
    accumulate `{group: {dep: {git, ref?, root?}}}` (a later record of the
    same group merges under the group key); record the accumulated mapping at
    `"usages"`
- Imported dependencies: `Question`, `QuestionGroup`, `SessionAnswers`,
  `ToolDeclaration`; practices `click`, `image_defaults`, `agent_env_defaults`

**Entity: `FileGenerator()`**
- Type: class (Entity — the artifact generator, new snapshot-driven API)
- Declared `location`: `goga/onboarding/generator/generator.py`
- Facade obligation: importable from `goga.onboarding.generator` (and `goga.onboarding`)
- Methods:
  - `generate(answers: SessionAnswers, contributions: list[ToolContribution])
    -> files: list[CreatedFile]` — `Path(".goga/config.yml").is_file()` →
    skip the config and Dockerfile generation (jump to tool configs — the
    guarantee lives here, not only at the caller); ELSE: snapshot; Dockerfile
    written ONLY when BOTH `docker_image.dockerfile` AND
    `docker_image.base_image` are present (`FROM {base_image}\n`,
    `mkdir(parents=True, exist_ok=True)`, `CreatedFile(path, None)`); a
    skipped `base_image` collapses the branch — no Dockerfile and the config
    `dockerfile` field is omitted; then `generate_goga_config`; then
    `generate_tool_configs`; return the created files in generation order
    (Dockerfile, conventions.md when downloaded, config.yml, tool files)
  - `generate_goga_config(answers) -> None` — snapshot; `language` empty →
    clean `ValueError` naming the field (the single required-field check);
    conventions entry (when `codemanifest.usages` carries the `"conventions"`
    key) → download per `lang_conventions` (`requests.get(url, timeout=30)`),
    failure → clean error with the URL and the cause, config.yml NOT created;
    write `.goga/usages/conventions.md` first; `mkdir .goga`; assemble the
    ordered document per the mapping table; `yaml.dump(default_flow_style=False,
    allow_unicode=True, sort_keys=False)`; field order: language, image,
    dockerfile, build, pipeline, codemanifest, tools, usages
  - `generate_tool_configs(contributions) -> None` — per contribution, per
    buffered `(file, data)` in call order → `.goga/tools/<tool>/<file>`;
    a repeated file name replaces
- Snapshot → YAML field mapping (normative): `language` → language;
  `docker_image.image` → image; `docker_image.dockerfile` → dockerfile
  (omitted when absent — and absent when the Dockerfile was not written);
  `docker_image.base_image` → the Dockerfile FROM line only, NEVER emitted to
  the config; `build.{agent,env}` → `build.task_executor.{agent,env}` (nested
  under `task_executor`); `pipeline.{agent,env}` → the flat pipeline block;
  `codemanifest.{usages,annotations}` → the codemanifest block (annotations
  via the `_LiteralStr` literal-block representer); `tools` → top-level tools
  (dict[str,str]); `usages` → the nested records (dict[str, dict[str,
  DepConfig]], `git` required, `ref`/`root` optional); confirm-gate answers
  never carried (never recorded in the first place); no entry for tool
  sections — their data reaches `.goga/tools/<tool>/` through `write_config`
- Imported dependencies: `SessionAnswers`, `ToolContribution`; practices
  `yaml`, `lang_conventions`

**Entity: `CreatedFile(path: str, tool: str | None)`**
- Type: class (Entity, frozen dataclass)
- Declared `location`: `goga/onboarding/generator/generator.py`
- Facade obligation: importable from `goga.onboarding.generator` (and `goga.onboarding`)
- Properties: `path -> str` (relative to the project root), `tool -> str |
  None` (None for an engine file)

**Entity: `InitLogic(questionnaire: Questionnaire, generator: FileGenerator, participation: ToolParticipation)`**
- Type: class (Entity — orchestrator, rewritten)
- Declared `location`: `goga/onboarding/logic.py`
- Facade obligation: importable from `goga.onboarding`
- Methods: `run() -> exit_code: int` — the eight steps:
  1. existing `.goga/config.yml` → `return 0` immediately (no prompts, no
     events, no artifacts)
  2. `version = host_goga_version()` — `PackageNotFoundError` → one clean
     message, `return 1`; `tag = minor_version(version)` — `ValueError` →
     clean message, `return 1` (defensive)
  3. `declarations = self._participation.collect_declarations()` —
     `ImportError` → one clean message naming the package, `return 1`
  4. `project_name = resolve_project_name()` (tolerant, `None` on failure);
     `convention_exists = Path(".goga/usages/conventions.md").is_file()`;
     `core = core_questions(tag, project_name, convention_exists)`;
     `plan = assemble_session_plan(core, declarations)`;
     `skips = [(d.tool, p) for d in declarations for p in d.skips]`;
     `plan = apply_skips(plan, skips)`
  5. `answers = SessionAnswers(tools=plan.tools)`;
     `self._questionnaire.run(plan, answers)` — `click.Abort` → `return 1`
     (quiet); unexpected `Exception` → one clean message, `return 1`
  6. `contributions = self._participation.collect_contributions(answers)`
  7. `files = self._generator.generate(answers, contributions)`; render the
     report `created {path}` / `created {path} (tool: {tool})`
  8. `return 0` — tool failures never change the exit code
- Error tiers (cross-cutting): tool failures → `logger.warning`, element/tool
  drops, exit code untouched; session errors (broken import, unreadable
  version, empty language, download failure) → ONE `click.echo("Error: …",
  err=True)` + exit 1, never a traceback; user aborts (`click.Abort`) →
  exit 1, quiet
- Facade re-exports (13 embeddings, in order): `Question`, `QuestionGroup`,
  `SessionAnswers`, `SessionPlan`, `Questionnaire`, `core_questions`,
  `assemble_session_plan`, `apply_skips`, `ToolParticipation`,
  `ToolDeclaration`, `ToolContribution`, `FileGenerator`, `CreatedFile`

**Entity: `init(tpl, upgrade, ref, tools)` (changed)**
- Type: function (CLI command, `goga/commands/init/init.py`)
- Facade obligation: exposed as the `goga init` click command
- Signature change: `tools: tuple[str, ...]` via `@click.option("-t",
  "--tool", "tools", multiple=True, ...)`
- Semantic requirements (algorithm steps 1–6): ref placement check (ported) →
  `--ref requires <tpl> or --upgrade`; mode resolution (ported; `<tpl>` +
  `--upgrade` mutual exclusion) → `UPGRADE | SCAFFOLD_THEN_ONBOARDING |
  BARE_ONBOARDING`; invitation validation — `tools` non-empty AND mode
  UPGRADE → `-t/--tool requires an onboarding session and --upgrade runs
  none`, exit 1; dedup preserving flag order (`list(dict.fromkeys(tools))` —
  the tuple→list conversion happens here); already-initialized guard
  (BARE_ONBOARDING only, ported); dispatch — UPGRADE: `Scaffold().upgrade(ref)`;
  both onboarding modes: `InitLogic(Questionnaire(), FileGenerator(),
  ToolParticipation(invited=deduped))` → `ctx.exit(logic.run())`
- Constraints: the command passes names through as opaque data — no
  installation checks; delegates execution; scaffold before onboarding when
  `tpl` is given

### Interaction Diagram and Data Flows

Verbatim from the design document — the runtime composition every coding
task of this plan contributes to:

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

Data flows (verbatim from the design document):

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

Runtime construction order: `ToolParticipation` and `Questionnaire`
and `FileGenerator` are constructed by `init` and injected into
`InitLogic`; `SessionAnswers` is constructed inside `InitLogic.run` after
`apply_skips` (it needs `plan.tools`); `HookRegistry` is constructed once
inside `ToolParticipation` and shared by both moments.

### Re-exports

- `->minor_version` — source: `goga/version/version.py` (local type in the
  version cell); facade obligation: importable from `goga.version`; add to
  `__all__` in `goga/version/__init__.py`
- `->wrap_context`, `->build_hook_arguments` — source: `goga/hooks/dispatch`
  (Imports entry, sub-facade verified to export both); facade obligation:
  importable from `goga.hooks`
- `->enumerate_tool_packages` — source: `goga/hooks/tools` (Imports entry,
  sub-facade verified); facade obligation: importable from `goga.hooks`
- The 13 onboarding embeddings (see `InitLogic` above) — sources:
  `goga/onboarding/questions` (3), `goga/onboarding/survey` (5),
  `goga/onboarding/participation` (3), `goga/onboarding/generator` (2);
  facade obligation: importable from `goga.onboarding`, in the embedding
  order of the CODEMANIFEST; the facade docstring states the domain-facade
  role

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — mandatory code conventions:
  relative imports, dataclasses `kw_only=True`, docstring discipline, module
  logger per file, REPL/test infrastructure, `pytest tests/ -x` / `ruff check
  <src>/` commands. Relevant to EVERY task of this plan.
- `click` (`.goga/usages/cooks/click.md`) — the prompting cookbook:
  `click.prompt` / `click.confirm` / `click.Choice`, repeated collections.
  Relevant to the `Questionnaire` engine and the `init` command.
- `image_defaults` (inline in `goga/onboarding/survey/CODEMANIFEST`) —
  language → image-family mapping, tag completed at runtime, suggestions
  displayed, default = last entry, free-form accepted:
  python `qarium/goga-python-{3.10-3.14}`, golang
  `qarium/goga-golang-{1.23-1.26}`, javascript `qarium/goga-node-{22,24}`,
  kotlin `qarium/goga-kotlin-{2.0-2.3}`, swift `qarium/goga-swift-{6.0-6.2}`.
  Relevant to `core_questions` (builds the hints) and `Questionnaire`
  (renders them).
- `agent_env_defaults` (inline, survey) — agent → env key mapping (claude:
  ANTHROPIC_BASE_URL, ANTHROPIC_DEFAULT_HAIKU_MODEL,
  ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL,
  ANTHROPIC_MODEL; codex: CODEX_MODEL; cursor: CURSOR_MODEL; opencode:
  OPENCODE_MODEL, OPENCODE_VARIANT; qwen: OPENAI_BASE_URL, OPENAI_MODEL).
  Relevant to `core_questions` and the engine's build/pipeline env pairs.
- `yaml` (inline, generator) — `yaml.dump(default_flow_style=False)` for
  config and tool files; `sort_keys=False, allow_unicode=True`; annotations
  via the `_LiteralStr` representer (ported from the old generator).
- `lang_conventions` (inline, generator) — URL template
  `https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md`;
  save to `.goga/usages/conventions.md`; `requests.get(url, timeout=30)`;
  failure → clean error with URL and cause.

### Imported Usages

- `minor-line` from `goga/version` (`goga/version/.usages/minor-line.md`) —
  reading the installed version and deriving the tag; used by the `InitLogic`
  task. Status: current, no changes needed.
- `question-records` from `goga/onboarding/questions`
  (`goga/onboarding/questions/.usages/question-records.md`) — the record
  structure and the answer addressing rules; imported by the survey,
  participation, and generator tasks. Status: current.
- `per-tool-delivery`, `registering-hooks` from `goga/hooks`
  (`goga/hooks/.usages/{per-tool-delivery,registering-hooks}.md`) — the
  staged per-tool delivery loop and the registration contract; imported by
  the participation tasks. Status: current.
- `session-participation` from `goga/onboarding/participation`
  (`goga/onboarding/participation/.usages/session-participation.md`) — the
  two tool moments; used by the generator and `InitLogic` tasks. Status:
  current.
- `tool-contexts` from `goga/onboarding/participation`
  (`goga/onboarding/participation/.usages/tool-contexts.md`) — the hook
  signature pattern (`context` first, optional `self`); used by the
  participation tests. Status: current.
- `survey-run` from `goga/onboarding/survey`
  (`goga/onboarding/survey/.usages/survey-run.md`) — the plan assembly and
  the survey; used by the `InitLogic` task. Status: current.
- `artifact-generation` from `goga/onboarding/generator`
  (`goga/onboarding/generator/.usages/artifact-generation.md`) — the
  generation and the file report; used by the `InitLogic` task. Status:
  current.
- `onboarding-usage` from `goga/onboarding`
  (`goga/onboarding/.usages/onboarding-usage.md`) — the session API and the
  invitation semantics; used by the `init` command task. Status: current.
- `scaffold-usage` from `goga/scaffold` — the Scaffold API; used by the
  `init` command task. Status: current (unchanged).

### Local Usages

No new local usage files are planned. The design stage already created and
updated every usage file referenced by the contracts (`minor-line.md`,
`per-tool-delivery.md`, `question-records.md`, `session-participation.md`,
`tool-contexts.md`, `survey-run.md`, `artifact-generation.md`,
`onboarding-usage.md`, `init.md` — all verified current in the design
review). Implementation tasks must keep the code consistent with them but do
not create or modify usage files.

### External Dependencies

- `click` — CLI framework: the survey prompting (`prompt`, `confirm`,
  `Choice`, `Abort`) and the `goga init` command (`@click.option(multiple=True)`)
- `requests` — the conventions download (`requests.get(url, timeout=30)`,
  `requests.RequestException`)
- `PyYAML` (`yaml`) — config and tool file serialization, the `_LiteralStr`
  literal-block representer
- `importlib.metadata` — `host_goga_version` (already in version.py;
  `PackageNotFoundError` handling in `InitLogic`)
- Tools: `pytest` (with `CliRunner`), `ruff`, `goga lint`

## Facts

- The DSL graph has 76 cells, `goga lint` exits 0 — the baseline is green;
  the plan's changes are additive to the graph (new leaf cells + facade
  re-exports).
- `_release_segments(version)` already exists at `goga/version/version.py:71`
  (module-private, returns `(major, minor | None)`, raises `ValueError` on no
  leading numeric major) — `minor_version` reuses it, does not duplicate it.
- `wrap_context` is at `goga/hooks/dispatch/delivery.py:28` (resolves
  attribute reads and bound methods; writes blocked — `declare`/`skip`/
  `answer`/`write_config` are method calls and pass through);
  `build_hook_arguments` at `delivery.py:69` (only a declared `context` and
  optional `self` receive values).
- `HookRegistry` (`goga/hooks/registry/state.py`) provides `build_once()`,
  `subscriptions_for(domain, action)`, `self_context(tool)`;
  `subscribe` resolves the address through `declared_actions`
  (registration.py:99) — without the two catalog records every onboarding
  subscription is rejected as «unknown action».
- `goga/hooks/dispatch/__init__.py` and `goga/hooks/tools/__init__.py`
  already export `wrap_context`, `build_hook_arguments`,
  `enumerate_tool_packages` — the facade re-export is a pure wiring change.
- Old modules to port from (then delete): `goga/onboarding/questionnaire.py`
  (486 lines: `_IMAGE_MAP`, `_LANGUAGES` order python/golang/kotlin/swift/
  javascript, `_AGENT_ENV_MAP`, `_AGENTS`, `_collect_agent_env`, prompt
  texts, docker branch), `goga/onboarding/generator.py` (174 lines:
  `_LiteralStr` + representer, `_CONVENTION_URL_TEMPLATE`, download logic,
  `_build_block`), `goga/onboarding/answers.py` (26 lines, to delete without
  porting — replaced by `SessionAnswers`).
- Old facade `goga/onboarding/__init__.py` exports `GogaConfigAnswers`,
  `InitAnswers` — the surface must never expose them again after the rewrite.
- The old `init.py` (104 lines) already carries the ref-placement and mode
  logic to port verbatim; it lacks only the `tools` parameter.
- Python conventions: type hints mandatory; `snake_case` functions/methods,
  `PascalCase` classes; relative intra-package imports; module docstrings in
  the established style; one module logger per file; ruff line-length 120,
  mccabe max-complexity 10.
- Test infrastructure: pytest `testpaths=["tests"]`; `tests/conftest.py`
  autouse `_isolate_home`; `tests/onboarding/conftest.py` provides
  `_clean_cwd` (applies to nested test dirs automatically); the repo CWD
  contains its own `.goga/` — every filesystem test needs `_clean_cwd`;
  tool-package simulation pattern lives in `tests/hooks/conftest.py`
  (`sys.modules` injection + enumeration monkeypatch); `tests/hooks/` has
  per-cell subpackages (catalog/, dispatch/, registry/, tools/) plus
  `test_facade.py`.
- The project-config loader (`goga/config/project/loader.py`) validates the
  written config: `tools` is `dict[str, str]` (loader.py:253); `usages` is
  `dict[str, dict[str, DepConfig]]` with `git` required and `ref`/`root`
  optional strings (loader.py:365-370) — the mapping table matches.
- Runtime construction order: `ToolParticipation`, `Questionnaire`,
  `FileGenerator` are constructed by `init` and injected into `InitLogic`;
  `SessionAnswers` is constructed inside `InitLogic.run` after `apply_skips`
  (it needs `plan.tools`); `HookRegistry` is constructed once inside
  `ToolParticipation` and shared by both moments.
- Reverse dependencies of the changed cells are unaffected: `goga/version`
  consumers (docker, commands/upgrade, commands/install) use existing names;
  `goga/hooks` consumers (history/statuses, commands/hooks) use existing
  re-exports; all changes are additive.
- The `review` core section is explicitly out of scope — do not add it.

## Gap Analysis

- Missing contract entities:
  - `minor_version` — not implemented (version.py lacks it)
  - `Question`, `QuestionGroup`, `SessionAnswers` — cells have only
    CODEMANIFEST, no code
  - `ToolDeclaration`, `ToolContribution`, `ToolParticipation` — no code
  - `core_questions`, `assemble_session_plan`, `apply_skips`, `SessionPlan`,
    new `Questionnaire` — no code
  - new-API `FileGenerator`, `CreatedFile` — no code
  - new `InitLogic` (3-collaborator constructor, 8-step run) — old 2-
    collaborator version present
- Missing facade exposure:
  - `goga/version/__init__.py`: `minor_version` absent from imports/`__all__`
  - `goga/hooks/__init__.py`: `wrap_context`, `build_hook_arguments`,
    `enumerate_tool_packages` absent
  - `goga/onboarding/__init__.py`: exports the wrong surface
    (`GogaConfigAnswers`, `InitAnswers`); the 13 embeddings + `InitLogic`
    missing
- Incorrect `location` placement: none — all planned files match the
  CODEMANIFEST `location`s; the leaf-cell packages
  (`goga/onboarding/{questions,participation,survey,generator}/`) exist as
  directories with CODEMANIFEST only.
- API mismatches:
  - old `FileGenerator.generate(answers: InitAnswers) -> None` vs new
    `generate(answers: SessionAnswers, contributions: list[ToolContribution])
    -> list[CreatedFile]`
  - old `Questionnaire.ask()` family vs new `run(plan, answers)` +
    `ask_question` + `ask_group`
  - old `init(tpl, upgrade, ref)` vs new `init(tpl, upgrade, ref, tools)`
- Behavioral mismatches:
  - no tool participation exists at all (no onboarding catalog records, no
    delivery)
  - image hints carry the tag only via the old wizard's per-language lists —
    the new tag threading (`host_goga_version` → `minor_version` →
    `core_questions`) does not exist
  - no `usages`/`tools` survey sections in the old wizard (NEW user-facing
    sections)
- Existing code that can be reused:
  - `_release_segments` (version.py) — direct reuse
  - old questionnaire data + prompt texts + `_collect_agent_env` — port into
    survey cell
  - old generator `_LiteralStr`, URL template, download logic, `_build_block`
    — port into generator cell
  - old init.py validation order — port verbatim, extend
  - hooks platform (registry, dispatch, tools sub-cells) — consume via the
    facade, no changes
- Test coverage gaps: all 33 scenarios of the design's Test Stack Trace;
  existing `tests/onboarding/test_answers.py`, `test_generator.py`,
  `test_questionnaire.py` test the old API and are deleted with the modules
  (cases ported); `tests/commands/test_init.py` imports the deleted modules
  at collection level (`goga.onboarding.answers`, `goga.onboarding.questionnaire`)
  and is adapted to the facade imports in Task 17;
  `tests/onboarding/test_logic.py` and
  `test_integration.py` are rewritten; `tests/version/test_version.py`,
  `tests/hooks/catalog/test_catalog.py`, `tests/hooks/test_facade.py` are
  extended.
- Missing visibility in workspace or git: the four leaf-cell directories are
  untracked (`?? goga/onboarding/{generator,participation,questions,survey}/`)
  — CODEMANIFESTs only; `goga/hooks/.usages/per-tool-delivery.md`,
  `goga/version/.usages/minor-line.md`, `goga/commands/init/.usages/`
  init.md updates are uncommitted but present (no action needed by this plan).

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).

### Task 1: `minor_version` routine in the version cell (TDD coding)

The version cell (leaf, `goga/version/`) gains the routine
`minor_version(version: str) -> minor: str` at `location: version.py` — the
`N.M` line derivation consumed by the onboarding image hints. The routine is
a pure function reusing the module-private `_release_segments` reducer that
already exists at `goga/version/version.py:71` (`(major, minor | None)`,
`ValueError` on no leading numeric major) — mirror `resolve_version`'s shape
recognition, do not duplicate the reducer. Also add the facade re-export:
`minor_version` importable from `goga.version`, added to `__all__` in
`goga/version/__init__.py` (alphabetical position maintained by the linter's
isort). Extend `tests/version/test_version.py`.

**Usages relevant to this task:**
- `convention`: docstring style in the established version.py pattern; the
  pure-function discipline (no side effects, deterministic output, no
  logging); `kw` conventions for tests; run tests with `pytest tests/version/test_version.py -v`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): in `tests/version/test_version.py` add — `from goga.version import minor_version` succeeds; `"minor_version" in goga.version.__all__`; `callable(minor_version)`
- [x] **Code**: implement `minor_version(version: str) -> str` in `goga/version/version.py` placed after `host_goga_version`, algorithm: (1) `major, minor_seg = _release_segments(version)`; (2) `minor = minor_seg if minor_seg is not None else "0"`; (3) `return f"{major}.{minor}"` — `ValueError` propagates from the reducer
- [x] **Code**: add `from .version import … minor_version` and the `__all__` entry in `goga/version/__init__.py`
- [x] **Interface verification**: `pytest tests/version/test_version.py -v` — the contract tests pass
- [x] **Logic tests**: add `test_minor_version_reduces_to_minor_line` — assertions: `minor_version("1.3.2") == "1.3"`; `minor_version("1.2.1.dev3") == "1.2"`; `minor_version("1.2.0rc1") == "1.2"`; `minor_version("1.2.0.post1") == "1.2"`; `minor_version("1.2.0+local") == "1.2"`; `minor_version("2") == "2.0"` (missing minor → 0). Add `test_minor_version_no_major_raises` — `with pytest.raises(ValueError): minor_version("latest")` (a `match` was added for the repo's PT011 lint rule)
- [x] **Debugging**: `pytest tests/version/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade importable; signature `(version: str) -> str`; pure (no I/O, no logging); `goga version` CLI behavior untouched
- [x] **Lint**: `ruff check goga/version/` — fix formatting if necessary

### Task 2: onboarding action records in the hooks catalog (TDD coding)

The catalog cell (leaf, `goga/hooks/catalog/`) gains two records in the
`_DECLARED_ACTIONS` constant of `catalog.py`:
`Action(domain="onboarding", name="declare_session", error_class="soft")`
and `Action(domain="onboarding", name="amend_config", error_class="soft")`.
This is the additive catalog extension that makes every tool subscription of
the two onboarding actions acceptable at `HookRegistrar.subscribe`
(registration.py:99 resolves addresses through `declared_actions()`) —
without it the whole feature dies at registration. The statuses record is
untouched; published records are never rewritten; the catalog stays
supported-data only. Extend `tests/hooks/catalog/test_catalog.py`.

**Usages relevant to this task:**
- `convention`: the data-model rules; test conventions.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: the existing catalog surface tests in `tests/hooks/catalog/test_catalog.py` must keep passing after the change (facade `declared_actions` importable, record shape unchanged) — run them first to establish the baseline
- [x] **Code**: append the two `Action(...)` records to `_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py` (order in the constant is irrelevant — `declared_actions()` sorts by `(domain, name)`)
- [x] **Interface verification**: `pytest tests/hooks/catalog/ -v` — the baseline still passes
- [x] **Logic tests**: add `test_catalog_carries_onboarding_actions` — assertions: `records = declared_actions()`; `("onboarding", "declare_session", "soft")` and `("onboarding", "amend_config", "soft")` are among `{(r.domain, r.name, r.error_class) for r in records}`; `[(r.domain, r.name) for r in records] == sorted((r.domain, r.name) for r in records)`; the statuses record still present
- [x] **Debugging**: `pytest tests/hooks/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: `declared_actions()` returns a new list per call; records frozen; `goga hooks` inspection output gains exactly the two onboarding rows (additive only)
- [x] **Lint**: `ruff check goga/hooks/catalog/` — fix formatting if necessary

### Task 3: hooks facade re-exports of the delivery primitives (infrastructure)

The hooks facade (`goga/hooks/__init__.py`) re-exports three names so that
domains orchestrating per-tool delivery address the platform through the
facade only: `wrap_context` and `build_hook_arguments` (from
`goga/hooks/dispatch`, already exported by its sub-facade) and
`enumerate_tool_packages` (from `goga/hooks/tools`, already exported). Both
the participation cell and `goga/hooks/.usages/per-tool-delivery.md` import
`from goga.hooks import HookRegistry, wrap_context, build_hook_arguments` —
a missing re-export is an ImportError of the whole onboarding domain. No
name collision exists; the `declared_actions` re-export is untouched;
importing `goga.hooks` must keep importing no `goga_tool_*` package and
enumerating nothing. Extend `tests/hooks/test_facade.py`.

**Usages relevant to this task:**
- `convention`: relative intra-package imports (`from .dispatch import …`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): in `tests/hooks/test_facade.py` add `test_hooks_facade_reexports_delivery_primitives` — assertions: `goga.hooks.wrap_context is goga.hooks.dispatch.wrap_context`; `goga.hooks.build_hook_arguments is goga.hooks.dispatch.build_hook_arguments`; `goga.hooks.enumerate_tool_packages is goga.hooks.tools.enumerate_tool_packages`; `{"wrap_context", "build_hook_arguments", "enumerate_tool_packages"} <= set(goga.hooks.__all__)`
- [x] **Code**: in `goga/hooks/__init__.py` add `from .dispatch import build_hook_arguments, emit_hook_event, wrap_context` (replacing the single-name import) and `from .tools import enumerate_tool_packages`; extend `__all__` with the three names
- [x] Verify facade accessibility: `pytest tests/hooks/test_facade.py -v` — all pass, including the pre-existing facade invariants (no import side effects)
- [x] Lint: `ruff check goga/hooks/__init__.py` — fix formatting if necessary

### Task 4: questions cell structure (infrastructure)

Create the package structure of the new leaf cell
`goga/onboarding/questions/` (the directory exists with CODEMANIFEST only —
untracked). The cell owns the declarative question-and-answer model: data
and pure answer operations only — no interactivity, no filesystem, no tool
delivery. Create the two `location` module files with module docstrings and
the package facade `__init__.py` with the domain docstring (no exports yet —
the entity tasks add them). Create the test subpackage
`tests/onboarding/questions/` (`__init__.py` empty). The
`tests/onboarding/conftest.py` `_clean_cwd` fixture applies automatically to
nested dirs.

**Usages relevant to this task:**
- `convention`: module docstrings in the established style (see
  `goga/hooks/catalog/catalog.py` header); relative imports; test
  infrastructure layout.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga/onboarding/questions/questions.py` — module docstring naming the cell entities (`Question`, `QuestionGroup` at `location: questions.py`), no code yet
- [x] Create `goga/onboarding/questions/answers.py` — module docstring naming `SessionAnswers` at `location: answers.py`, no code yet
- [x] Create `goga/onboarding/questions/__init__.py` — domain docstring (the cell owns the declarative question-and-answer model of the onboarding session); empty `__all__: list[str] = []` placeholder to be filled by the entity tasks
- [x] Create `tests/onboarding/questions/__init__.py` (empty)
- [x] Verify importability: `python -c "import goga.onboarding.questions"` — exits 0
- [x] Lint: `ruff check goga/onboarding/questions/` — passes

### Task 5: `Question` and `QuestionGroup` records (TDD coding)

Implement the two immutable declarative records of the questions cell at
`location: goga/onboarding/questions/questions.py` and expose them through
the cell facade. Frozen dataclasses, `kw_only=True`, fields exactly per the
signatures; `None` only for explicit absence (`choices`/`default`/`keys` on
`Question`; `prompt`/`children` on `QuestionGroup`). NO validation in the
records — kinds are checked at ask time, not at construction; no methods, no
properties beyond the fields (data-only discipline). A `QuestionGroup` with
`children=None` is a structural node carrying no prompt.

**Usages relevant to this task:**
- `convention`: dataclass rules — `@dataclass(frozen=True, kw_only=True)` in
  the `catalog.py` `Action` style; attribute docstrings; do not log (pure
  records never log).
- `question-records` (imported from the questions cell itself —
  `goga/onboarding/questions/.usages/question-records.md`): the record
  structure and the answer addressing rules; construct with keyword
  arguments, e.g. `Question(id="token", kind="input", prompt="Service token")`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/questions/test_questions.py` — `from goga.onboarding.questions import Question, QuestionGroup` succeeds; both in `__all__`; keyword construction `Question(id="token", kind="input", prompt="Service token")` works; frozen (assigning a field raises `dataclasses.FrozenInstanceError`); `QuestionGroup(id="g", children=None)` constructible without `prompt`
- [x] **Code**: implement `Question(id: str, kind: str, prompt: str, choices: list[str] | None = None, default: str | bool | None = None, keys: list[str] | None = None)` and `QuestionGroup(id: str, prompt: str | None = None, children: list[Question | QuestionGroup] | None = None)` in `goga/onboarding/questions/questions.py` — frozen `kw_only` dataclasses, field docstrings per the CODEMANIFEST property annotations
- [x] **Code**: export both from `goga/onboarding/questions/__init__.py` (`from .questions import Question, QuestionGroup`, `__all__` entries)
- [x] **Interface verification**: `pytest tests/onboarding/questions/test_questions.py -v` — contract tests pass
- [x] **Logic tests**: positive — `Question(id="q", kind="choice", prompt="Pick", choices=["a", "b"], default="a")` exposes all fields with the given values; a group round-trips `children=[Question(id="x", kind="input", prompt="X")]`; negative — positional construction is refused (`kw_only`); edge — defaults are `None` for `choices`/`default`/`keys`/`prompt`/`children`
- [x] **Debugging**: `pytest tests/onboarding/questions/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: no methods or computed properties beyond the fields; no validation raising at construction; hashable/immutable value objects
- [x] **Lint**: `ruff check goga/onboarding/questions/` — fix formatting if necessary

### Task 6: `SessionAnswers` accumulator (TDD coding)

Implement the single mutable accumulator of one run at `location:
goga/onboarding/questions/answers.py` and expose it through the cell facade.
Constructor `SessionAnswers(tools: list[str] | None = None)` creates an
empty space; `tools` reserves the top-level keys of the tool sections
WITHOUT creating them (`_tool_sections = frozenset(tools or ())`,
`_data = {}`). Four methods: `record` (segment walk creating intermediate
dicts; set leaf — REPLACE, never merge; a leaf collision with an existing
scalar mid-path is replaced by a mapping — the survey is the authoritative
writer), `amend` (same walk; at the leaf an existing dict AND a dict value →
recursive per-key merge; otherwise plain assignment; silent — no warning;
delivery order is the caller's responsibility), `view_for(tool)` (deepcopy
of the core items — every top-level key except the reserved names — updated
with a deepcopy of the tool's own section re-keyed by local names; a
local-name collision with a core key wins in THAT tool's view only;
an absent own section → core-only view), `snapshot()` (`deepcopy(_data)`).
No dotted keys are ever stored as literal keys — the path is split.

**Usages relevant to this task:**
- `convention`: type hints mandatory (`dict`, `str | bool | dict` value
  types); no logging (the accumulator is total, raises nothing).
- `question-records` (`goga/onboarding/questions/.usages/question-records.md`):
  the answer addressing rules — plan dot-paths (`"build.agent"`,
  `"my-tool.token"`), nested mappings keyed by question ids.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/questions/test_answers.py` — `from goga.onboarding.questions import SessionAnswers` succeeds; in `__all__`; `SessionAnswers()` and `SessionAnswers(tools=["my-tool"])` both construct empty (`snapshot() == {}`)
- [x] **Code**: implement `SessionAnswers` with `record`, `amend`, `view_for`, `snapshot` per the semantics above (walk helper may be a module-private function)
- [x] **Code**: export `SessionAnswers` from `goga/onboarding/questions/__init__.py`
- [x] **Interface verification**: `pytest tests/onboarding/questions/test_answers.py -v` — contract tests pass
- [x] **Logic tests** (from the design, transfer verbatim): `test_record_creates_nested_mappings` — `answers.record("build.agent", "claude")` → `snapshot() == {"build": {"agent": "claude"}}`; `test_amend_merges_mappings_replaces_scalars` — setup `answers.record("pipeline", {"agent": "codex", "env": {"A": "1"}})`, input `answers.amend("pipeline", {"env": {"B": "2"}, "agent": "claude"})` → `snapshot() == {"pipeline": {"agent": "claude", "env": {"A": "1", "B": "2"}}}`; `test_view_for_isolates_and_flattens` — setup `SessionAnswers(tools=["my-tool", "viewer"])` with `language`/`my-tool.token`/`viewer.flag` recorded, `view_for("my-tool")` → `{"language": "python", "token": "t0"}`, `"viewer" not in view`, mutating the view does not touch the space (`answers.snapshot()["my-tool"]["token"] == "t0"`); `test_view_for_unknown_tool_returns_core_only` — `view_for("not-declared")` → core only; edge — `record("a.b", 1)` then `record("a.b.c", 2)` replaces the scalar with a mapping
- [x] **Debugging**: `pytest tests/onboarding/questions/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: reserved names come from the constructor param (fix q1 — no hardcoded list); merge happens only when BOTH sides are mappings; every returned view is a deep copy
- [x] **Lint**: `ruff check goga/onboarding/questions/` — fix formatting if necessary

### Task 7: participation cell structure (infrastructure)

Create the package structure of the new leaf cell
`goga/onboarding/participation/` (directory exists with CODEMANIFEST only).
The cell owns the tool participation: the invitation, the two onboarding
action moments delivered per tool with staged control, the surfaces, and
the isolated answer views. Create the three `location` module files with
module docstrings and the facade. Create the test subpackage
`tests/onboarding/participation/`.

**Usages relevant to this task:**
- `convention`: module docstrings; relative imports; test layout.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga/onboarding/participation/declaration.py` — module docstring naming `ToolDeclaration`
- [x] Create `goga/onboarding/participation/contribution.py` — module docstring naming `ToolContribution`
- [x] Create `goga/onboarding/participation/participation.py` — module docstring naming `ToolParticipation`
- [x] Create `goga/onboarding/participation/__init__.py` — domain docstring; empty `__all__` placeholder
- [x] Create `tests/onboarding/participation/__init__.py` (empty)
- [x] Verify importability: `python -c "import goga.onboarding.participation"` — exits 0
- [x] Lint: `ruff check goga/onboarding/participation/` — passes

### Task 8: `ToolDeclaration` and `ToolContribution` surfaces (TDD coding)

Implement the two delivery surfaces at `location:
goga/onboarding/participation/{declaration.py, contribution.py}` and expose
them through the cell facade. Both are the hook-facing objects wrapped by
`wrap_context` (attribute reads resolve; writes are blocked; the buffer
methods are calls and pass through). `ToolDeclaration(tool: str, invited:
bool)` — properties `tool`, `invited`, `questions` (declaration order),
`skips`; `declare(item)` enforces the one-level rule: a `QuestionGroup`
whose `children` contain a `QuestionGroup` is refused with a
`logger.warning` naming the tool and the reason ("a tool group is limited
to one nesting level with simple children"), the element is NOT buffered,
delivery continues (structural violations are warnings, never exceptions);
accepted items append to `questions`. `skip(path)` appends the raw string —
no resolution here. `ToolContribution(tool: str, invited: bool, answers:
dict)` — properties `tool`, `invited`, `answers`, `amendments`, `files`;
`answer(id, value)` appends `(id, value)` keeping call order;
`write_config(file, data)` appends `(file, data)` — a later same name
replaces at write time, not here. Both carry a module logger
(`logger = logging.getLogger(__name__)`).

**Usages relevant to this task:**
- `convention`: dataclass/buffer style; one module logger per file; warnings
  carry the tool name and the reason.
- `question-records` (`goga/onboarding/questions/.usages/question-records.md`):
  the declaration records — `Question` or a one-level `QuestionGroup`.
- `registering-hooks` (`goga/hooks/.usages/registering-hooks.md`): the hook
  signature (`context` first, optional `self`) and the failure handling
  behind the actions — the surfaces are what a hook receives as `context`.
- `per-tool-delivery` (`goga/hooks/.usages/per-tool-delivery.md`): the staged
  delivery loop the surfaces participate in.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/participation/test_declaration.py` and `test_contribution.py` — `from goga.onboarding.participation import ToolDeclaration, ToolContribution` succeeds; both in `__all__`; keyword construction `ToolDeclaration(tool="t", invited=True)` / `ToolContribution(tool="t", invited=True, answers={})` works; buffers start empty
- [x] **Code**: implement `ToolDeclaration` in `declaration.py` (fields `tool`, `invited`; buffered `questions: list`, `skips: list` — mutable lists on a non-frozen dataclass or equivalent) and `ToolContribution` in `contribution.py` (fields `tool`, `invited`, `answers`; buffered `amendments`, `files`)
- [x] **Code**: export both from `goga/onboarding/participation/__init__.py`
- [x] **Interface verification**: `pytest tests/onboarding/participation/ -v` — contract tests pass
- [x] **Logic tests**: positive — `declare(Question(id="token", kind="input", prompt="Token"))` buffers it in order; `skip("build.env")` buffers the raw string; `answer("tools", {"t": "1.0"})` and `write_config("service.yml", {"a": 1})` buffer tuples in call order (a same-named file buffered twice keeps BOTH entries — replacement happens at write time). Negative/edge: `test_declare_rejects_nested_group_with_warning` — `surface.declare(QuestionGroup(id="deep", children=[QuestionGroup(id="inner")]))` with caplog at WARNING → `surface.questions == []` AND `any("one nesting level" in r.message for r in caplog.records)` AND `any("t" in r.message for r in caplog.records)` (two independent `any()` joined by `and`)
- [x] **Debugging**: `pytest tests/onboarding/participation/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: `declare` never raises; the one-level Requirement is enforced at the surface (single point); buffers readable via the properties after delivery
- [x] **Lint**: `ruff check goga/onboarding/participation/` — fix formatting if necessary

### Task 9: `ToolParticipation` mediator (TDD coding)

Implement the mediator of both onboarding action moments at `location:
goga/onboarding/participation/participation.py` and expose it through the
cell facade. Constructor `ToolParticipation(invited: list[str])` — defensive
dedup preserving flag order (`_invited = list(dict.fromkeys(invited))`),
`_registry = None` (built lazily by `_ensure_registry()` — `HookRegistry()`
+ `build_once()`; `ImportError` from a broken package import propagates —
the single fatal case). `collect_declarations()`: warn for every invited
identity not among `{pkg.tool for pkg in enumerate_tool_packages()}`
("invited tool %s is not installed; continuing without its block"); group
`registry.subscriptions_for("onboarding", "declare_session")` per
`subscription.tool` preserving enumeration order; per tool build the surface
(`invited=tool in self._invited`), `proxy = wrap_context(surface)`, call
`sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))`
per subscription; any `Exception` → `logger.warning` naming tool, action
("onboarding.declare_session"), reason; the whole declaration of that tool
is discarded; return the surviving surfaces in enumeration order.
`collect_contributions(answers)`: identical delivery over
`subscriptions_for("onboarding", "amend_config")` with
`ToolContribution(tool, invited, answers=answers.view_for(tool))`; a
failure discards amendments AND files together; then a commit pass in
enumeration order — `answers.amend(path, value)` per buffered amendment;
return the committed contributions. Import the platform names from the
facade: `from goga.hooks import HookRegistry, build_hook_arguments,
enumerate_tool_packages, wrap_context` (enabled by Task 3).

Test setup pattern (from the design's General Setup): fake installed
packages via monkeypatched `goga.hooks.enumerate_tool_packages` (or
`packages_distributions`) + hooks registered directly through
`HookRegistrar`/a fake facade module injected via `sys.modules` — the
existing `tests/hooks/conftest.py` pattern. Caplog at WARNING for the
warning-path assertions.

**Usages relevant to this task:**
- `convention`: one module logger; warnings name the tool, the action, and
  the reason.
- `per-tool-delivery` (`goga/hooks/.usages/per-tool-delivery.md`): the
  staged delivery loop — commit only after every hook of the tool
  succeeded; delivery is NEVER filtered by invitation (the marker travels
  to the hook).
- `registering-hooks` (`goga/hooks/.usages/registering-hooks.md`): the
  registration envelope behind the two actions.
- `tool-contexts` (`goga/onboarding/participation/.usages/tool-contexts.md`):
  the hook signature pattern the fake hooks in tests follow (`context`
  first, optional `self`).
- `question-records`: the declaration records the hooks buffer.
- `session-participation`
  (`goga/onboarding/participation/.usages/session-participation.md`): the
  two moments' composition this class realizes.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/participation/test_participation.py` — `from goga.onboarding.participation import ToolParticipation` succeeds; in `__all__`; `ToolParticipation(invited=["a", "a", "b"]).invited == ["a", "b"]` (dedup, flag order); `collect_declarations`/`collect_contributions` callable
- [x] **Code**: implement `ToolParticipation` with `_ensure_registry`, `collect_declarations`, `collect_contributions` per the semantics above
- [x] **Code**: export `ToolParticipation` from `goga/onboarding/participation/__init__.py`
- [x] **Interface verification**: `pytest tests/onboarding/participation/test_participation.py -v` — contract tests pass
- [x] **Logic tests** (from the design, transfer verbatim): `test_collect_declarations_delivers_invitation_marker` — fake `goga_tool_my-tool` subscribed `("onboarding", "declare_session", "d1", hook)`, `ToolParticipation(invited=["my-tool"])` → one declaration, `tool == "my-tool"`, `invited is True`, `questions[0].id == "token"`; `test_collect_contributions_commits_in_order` — two fake tools alpha/beta (alpha first) each buffering `context.answer("tools", {name: version})` → `[c.tool for c in contributions] == ["alpha", "beta"]` and `answers.snapshot()["tools"] == {"alpha": "1.0", "beta": "2.0"}`; `test_collect_declarations_warns_for_uninstalled_invited` — no packages, `invited=["ghost"]`, caplog → `declarations == []` and a warning naming "ghost"; `test_failing_hook_drops_whole_declaration` — tools `bad` (raises `RuntimeError("boom")`) and `good` (declares one) → `[d.tool for d in declarations] == ["good"]`, warning carries "bad" and "boom"; `test_noninvited_subscribed_tool_is_marked_and_silent` — fake tool subscribed to BOTH actions, hooks record `self.saw_invited = context.invited` and return immediately when not invited, `ToolParticipation(invited=["other"])` → `declarations == []`, `[c.tool for c in contributions] == ["my-tool"]` with empty `amendments`/`files`, captured marker is False, `"my-tool" not in answers.snapshot()`, `not caplog.records` (silent — not a warning); moment-two failure — a tool whose `amend_config` hook buffers then raises → `contributions == []`, `"tools" not in answers.snapshot()` (participation side only; the generate side is covered in Task 16)
- [x] **Debugging**: `pytest tests/onboarding/participation/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: `_registry` built once and shared by both moments; delivery order is enumeration order; the invitation marker is never filtered platform-side; `ImportError` propagates uncaught
- [x] **Lint**: `ruff check goga/onboarding/participation/` — fix formatting, apply decomposition if necessary

### Task 10: survey cell structure (infrastructure)

Create the package structure of the new leaf cell
`goga/onboarding/survey/` (directory exists with CODEMANIFEST only). The
cell owns the survey: the core question tree, the plan assembly, the skip
application, and the interactive run. Create the three `location` module
files with module docstrings and the facade. Create the test subpackage
`tests/onboarding/survey/`.

**Usages relevant to this task:**
- `convention`: module docstrings; relative imports; test layout.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga/onboarding/survey/core.py` — module docstring naming `core_questions`
- [x] Create `goga/onboarding/survey/plan.py` — module docstring naming `assemble_session_plan`, `apply_skips`, `SessionPlan`
- [x] Create `goga/onboarding/survey/questionnaire.py` — module docstring naming `Questionnaire`
- [x] Create `goga/onboarding/survey/__init__.py` — domain docstring; empty `__all__` placeholder
- [x] Create `tests/onboarding/survey/__init__.py` (empty)
- [x] Verify importability: `python -c "import goga.onboarding.survey"` — exits 0
- [x] Lint: `ruff check goga/onboarding/survey/` — passes

### Task 11: `core_questions` tree builder (TDD coding)

Implement the core tree builder at `location: goga/onboarding/survey/core.py`
and expose it through the cell facade. Port the data of the old wizard from
`goga/onboarding/questionnaire.py` (do not rewrite from scratch):
`_IMAGE_MAP` → the `image_defaults` mapping (families per the practice),
`_LANGUAGES = ["python", "golang", "kotlin", "swift", "javascript"]`,
`_AGENT_ENV_MAP` → the `agent_env_defaults` mapping, `_AGENTS =
list(_AGENT_ENV_MAP)`. Signature `core_questions(image_tag: str,
project_name: str | None, convention_exists: bool) -> QuestionGroup`.
Sections in order: (1) `language` — choice of `_LANGUAGES`; (2) `convention`
— only when `not convention_exists`: `QuestionGroup(id="convention",
prompt="--- Base Convention ---", children=[Question(id="adopt", kind="confirm",
prompt="Download base convention", default=False)])`; (3) `codemanifest` —
usages pairs + annotations input (defaults supplied at ask time when the
convention gate was accepted — engine-side prefill, NOT tree defaults);
(4) `build` — agent choice + env pairs; (5) `docker_image` — dockerfile
input (default `.goga/Dockerfile`), base_image input (prompt embeds the
completed hint list, default = LAST entry), image input (default
`f"{project_name}:latest"` or absent when `project_name is None`); (6)
`pipeline` — agent choice + env pairs; (7) `tools` — pairs question with the
four-form grammar documented in the prompt; (8) `usages` — structural
`QuestionGroup(id="usages", prompt="--- Usages ---")` with no declarable
children. Return `QuestionGroup(id="core", children=sections)`. The
completed hints are data of the tree (embedded in the `base_image` prompt +
default) — the ENGINE renders them; the tag is never hardcoded. The
`tools`/`usages` sections are NEW user-facing sections — keep their prompt
texts aligned with the created-files list of
`goga/commands/init/.usages/init.md` (`.goga/config.yml`,
`.goga/usages/conventions.md`, the Dockerfile, `.goga/tools/<tool>/<file>`)
— a design instruction carried into this task.

**Usages relevant to this task:**
- `convention`: docstring style; pure builder (no I/O).
- `image_defaults` (inline practice in the survey CODEMANIFEST): the
  language → family mapping; complete each name with `image_tag`; default =
  last entry; free-form accepted (kind stays `input`).
- `agent_env_defaults` (inline practice): the agent → env key mapping for
  the `keys` parameterization of the env pairs questions.
- `question-records`: the record structure the builder emits.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/survey/test_core.py` — `from goga.onboarding.survey import core_questions` succeeds; in `__all__`; `core_questions("1.3", "my-app", False)` returns a `QuestionGroup` with `id == "core"`
- [x] **Code**: port the mapping data and implement `core_questions` in `goga/onboarding/survey/core.py` per the section list above
- [x] **Code**: export `core_questions` from `goga/onboarding/survey/__init__.py`
- [x] **Interface verification**: `pytest tests/onboarding/survey/test_core.py -v` — contract tests pass
- [x] **Logic tests**: `test_core_questions_builds_eight_sections_with_tag` — assertions: `[child.id for child in core.children] == ["language", "convention", "codemanifest", "build", "docker_image", "pipeline", "tools", "usages"]`; the `base_image` question's prompt contains `"qarium/goga-python-3.14:1.3"` and its default equals the last completed hint; the `image` question default == `"my-app:latest"`; `core_questions("1.3", None, True)` drops the `convention` section (first section is `language`); edge — `project_name=None` → the `image` default is `None` (absent)
- [x] **Debugging**: `pytest tests/onboarding/survey/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: the root id `"core"` is never addressed in answers (sections are the top-level keys); kind of `base_image`/`image` stays `input` (free-form); the tag threads from the single argument — no hardcoded `1.3`
- [x] **Lint**: `ruff check goga/onboarding/survey/` — fix formatting if necessary

### Task 12: plan layer — `SessionPlan`, `assemble_session_plan`, `apply_skips` (TDD coding)

Implement the plan layer at `location: goga/onboarding/survey/plan.py` and
expose the three names through the cell facade. `SessionPlan(root, tools)`
is a data record (frozen `kw_only` dataclass). `assemble_session_plan(core,
declarations)` — the algorithm with the fix-q2 guard (reserved names
derived from the RECEIVED core's children; a colliding tool identity drops
the whole block with a warning naming the tool and the reserved name; the
tool keeps its amendment rights) and the local-name dedup (a repeated id
drops THAT element with a warning; survivors stand; a fully-dropped tool
still gets its empty block). `apply_skips(plan, skips)` — the three-way
resolution rule (prefixed / core / own-block) against the ORIGINAL root,
set semantics (order-independent, descendants of removed nodes silently
absorbed), rebuild with new groups along changed branches sharing frozen
originals, a NEW `SessionPlan` with the same `tools` list, no-op warnings
for unresolvable paths. Module logger for the warnings.

**Usages relevant to this task:**
- `convention`: pure transformers; one module logger; warnings name the
  tool and the reason.
- `question-records`: the record structure and the tree-path addressing
  (ids joined by dots).
- `survey-run` (`goga/onboarding/survey/.usages/survey-run.md`): the
  reserved-names note of `assemble_session_plan` and the plan semantics.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/survey/test_plan.py` — `from goga.onboarding.survey import SessionPlan, assemble_session_plan, apply_skips` succeeds; all three in `__all__`; `assemble_session_plan(core, [])` returns a `SessionPlan` whose root children equal the core children and `tools == []`
- [x] **Code**: implement `SessionPlan`, `assemble_session_plan`, `apply_skips` in `goga/onboarding/survey/plan.py` per the algorithms above (a `_resolve_path` helper and a `_rebuild_without` helper are natural internal decomposition)
- [x] **Code**: export the three names from `goga/onboarding/survey/__init__.py`
- [x] **Interface verification**: `pytest tests/onboarding/survey/test_plan.py -v` — contract tests pass
- [x] **Logic tests** (from the design, transfer verbatim): `test_assemble_session_plan_orders_blocks_and_drops_repeats` — core with `language`, `tools`; declarations of `my-tool` (two questions both id `token`), `viewer` (one), `empty-tool` (none) → root children ids `["language", "tools", "my-tool", "viewer"]`, `plan.tools == ["my-tool", "viewer"]`, the my-tool block has exactly one `token` child; `test_assemble_reserved_name_drops_block` — core with a `tools` section; a declaration of a tool with identity `tools` → `plan.tools == []`, root children `["tools"]` (core only), a warning naming "tools" in caplog; `test_apply_skips_prefixed_own_and_unknown` — plan with core `language` + `build` and blocks `my-tool` (group `reporting` with `enabled`) and `viewer` (`opt`); skips `[("my-tool", "reporting.enabled"), ("viewer", "my-tool.reporting.enabled"), ("viewer", "language"), ("my-tool", "no.such.path")]` → `language` absent, `build` present, both blocks present (`my-tool` emptied group), `"enabled"` not reachable under the my-tool block, a warning naming "no.such.path"; edge — applying the same plan's skips in reversed order yields the same result (order independence)
- [x] **Debugging**: `pytest tests/onboarding/survey/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: the core tree is never mutated (records frozen, fresh containers); an emptied block stays in the plan; `core_section_ids` derived, not hardcoded
- [x] **Lint**: `ruff check goga/onboarding/survey/` — fix formatting, apply decomposition if necessary

### Task 13: `Questionnaire` survey engine (TDD coding)

Implement the interactive engine at `location:
goga/onboarding/survey/questionnaire.py` and expose it through the cell
facade. Port the prompt texts and the interactive patterns of the old
`goga/onboarding/questionnaire.py` (session header, language choice, base
convention gate with prefill, codemanifest usages/annotations, agent
gates, `_collect_agent_env`, docker branch with hints, image name) — the
old `ask`/`ask_*` per-field methods become the engine's core-section
patterns; `ask_goga_config`'s config-exists short-circuit is NOT ported
(that guard moved to `InitLogic`/`FileGenerator`). API: `run(plan,
answers)` — header echo, core sections via the conditional patterns, tool
blocks after the core under the attribution heading (suppress emptied
blocks; a group with `prompt=None` still renders the heading from the block
id); records land at plan dot-paths. `ask_question(question)` — the four
kinds via click plus the ELSE soft-skip branch (unknown kind or missing
parameterization → warning naming the question path, not asked, not
recorded, survey continues). `ask_group(group, prefix=None)` — heading
echo, children in order, recursion (the optional prefix keeps the
contract's one-argument call shape). The core-section rule: only the children
present in the post-skip section are asked; the confirm gates are
presentational (never recorded); the docker_image branch collapses per the
rule (skipped `dockerfile` → the pull branch directly; skipped `base_image`
→ the FROM is never recorded/asked). The usages record loop accumulates
`{group: {dep: {git, ref?, root?}}}` and records it at `"usages"`.
`click.Abort` propagates. Test with `CliRunner` (the existing
`tests/onboarding/test_questionnaire.py` pattern — port the old cases into
`tests/onboarding/survey/test_questionnaire.py`).

**Usages relevant to this task:**
- `click` (`.goga/usages/cooks/click.md`): `click.prompt` /
  `click.confirm` / `click.Choice`; the repeated key-value collection
  pattern; `_collect_agent_env` is the template for the gated env pairs.
- `convention`: one module logger (the ELSE branch warns); type hints.
- `image_defaults` (inline practice): render the hint lines of the
  `base_image` prompt, default the last, accept free-form.
- `agent_env_defaults` (inline practice): prompt the suggested keys of the
  selected agent first, then arbitrary additions.
- `question-records`: the records the engine asks; the answer-value types
  per kind.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/survey/test_questionnaire.py` — `from goga.onboarding.survey import Questionnaire` succeeds; in `__all__`; `Questionnaire()` constructs with no arguments; `run`, `ask_question`, `ask_group` callable
- [x] **Code**: implement `Questionnaire` in `goga/onboarding/survey/questionnaire.py` — `run`, `ask_question`, `ask_group`, and the private core-section patterns (`_survey_language`, `_survey_convention`, `_survey_codemanifest`, `_survey_build`, `_survey_docker_image`, `_survey_pipeline`, `_survey_tools`, `_survey_usages` — or an equivalent internal decomposition under mccabe 10)
- [x] **Code**: export `Questionnaire` from `goga/onboarding/survey/__init__.py`
- [x] **Interface verification**: `pytest tests/onboarding/survey/test_questionnaire.py -v` — contract tests pass
- [x] **Logic tests** (from the design, transfer verbatim): `test_questionnaire_records_core_and_tool_answers` — plan from a minimal core (`language` choice) + `my-tool` block (input `token`); `answers = SessionAnswers(tools=["my-tool"])`; CliRunner inputs `["python", "t0"]` → `answers.snapshot() == {"language": "python", "my-tool": {"token": "t0"}}`; `test_unknown_kind_is_skipped_with_warning` — a `my-tool` block with `Question(id="bad", kind="text", prompt="Weird")` and `Question(id="ok", kind="input", prompt="Token")`; input `["t0"]`; caplog → `answers.snapshot() == {"my-tool": {"ok": "t0"}}`, a warning naming "my-tool.bad", `"Weird" not in result.output`; port the old questionnaire test cases (convention gate accept/reject prefill, agent gates, docker branch hints, image default) adapted to the plan/answers API
- [x] **Debugging**: `pytest tests/onboarding/survey/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: gates never record; a skipped subtree is never asked; tool answers nest under the reserved tool key; a hook is never called to survey (the engine asks the buffered records)
- [x] **Lint**: `ruff check goga/onboarding/survey/` — fix formatting, apply decomposition if necessary

### Task 14: generator cell structure (infrastructure)

Create the package structure of the new leaf cell
`goga/onboarding/generator/` (directory exists with CODEMANIFEST only; the
OLD module `goga/onboarding/generator.py` — a file — coexists until the
facade rewrite deletes it; Python resolves `goga.onboarding.generator` to
the package once it has `__init__.py`, so create the facade only when the
entity code is ready in Task 15 — this task creates the module file and the
test subpackage, and the facade together with Task 15's first code step).
Create `goga/onboarding/generator/generator.py` with its module docstring
and `tests/onboarding/generator/__init__.py`.

**Usages relevant to this task:**
- `convention`: module docstrings; test layout.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga/onboarding/generator/generator.py` — module docstring naming `FileGenerator` and `CreatedFile` at `location: generator.py`
- [x] Create `tests/onboarding/generator/__init__.py` (empty)
- [x] Verify no import shadowing breakage: `pytest tests/onboarding/ -x --co -q` — the OLD tests still collect and pass (the old `generator.py` module is untouched; the new package has no `__init__.py` yet, so `goga.onboarding.generator` still resolves to the old file)
- [x] Lint: `ruff check goga/onboarding/generator/` — passes

### Task 15: `FileGenerator.generate` + `generate_goga_config` + `CreatedFile` (TDD coding)

Implement the artifact generator core at `location:
goga/onboarding/generator/generator.py` and expose `FileGenerator` +
`CreatedFile` through the cell facade (`goga/onboarding/generator/__init__.py`
created NOW — from this point `goga.onboarding.generator` resolves to the
package). Port from the old `goga/onboarding/generator.py`: the
`_LiteralStr` class + `yaml.add_representer` registration, the
`_CONVENTION_URL_TEMPLATE`, the requests download with timeout 30 and the
clean error with URL and cause, the `_build_block` shape, the field order.
New API: `generate(answers, contributions) -> list[CreatedFile]` — the
existing-config guard (`Path(".goga/config.yml").is_file()` → skip the
config and Dockerfile generation, jump to tool configs); snapshot; the
Dockerfile written ONLY when BOTH `docker_image.dockerfile` AND
`docker_image.base_image` are present (`FROM {base_image}\n`,
`CreatedFile(path, None)`); then `generate_goga_config(answers)` (the
conventions download writes `.goga/usages/conventions.md` → `CreatedFile`
BEFORE the config serialization); then `generate_tool_configs`
(implemented fully in this task; Task 16 verifies it in isolation and
adds the cross-entity negative trace of the design).
`generate_goga_config(answers)` — snapshot; empty `language` →
`ValueError` naming the field; the conventions entry check; `mkdir .goga`;
the mapping table (see Contract Surface — build nests under
`task_executor`, pipeline stays flat, `base_image` NEVER emitted,
`dockerfile` omitted when absent, blocks omitted when empty, annotations as
a `_LiteralStr` literal block); `yaml.dump(default_flow_style=False,
allow_unicode=True, sort_keys=False)`. `CreatedFile(path, tool)` — frozen
`kw_only` dataclass.

**Usages relevant to this task:**
- `yaml` (inline practice in the generator CODEMANIFEST):
  `yaml.dump(default_flow_style=False)`; `sort_keys=False,
  allow_unicode=True`; the literal-block representer for annotations.
- `lang_conventions` (inline practice): the URL template, the target path,
  `requests.get(url, timeout=30)`, the failure semantics (clean error with
  URL + cause; config.yml NOT created on failure).
- `question-records`: the answer-space structure the snapshot yields.
- `session-participation`: the committed contributions shape.
- `convention`: docstring style; the module logger is NOT needed for the
  happy path (errors are exceptions, not warnings).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create `tests/onboarding/generator/test_generator.py` — `from goga.onboarding.generator import CreatedFile, FileGenerator` succeeds; both in `__all__`; `FileGenerator()` constructs; `CreatedFile(path="p", tool=None)` exposes both fields; `generate`/`generate_goga_config`/`generate_tool_configs` callable on the instance
- [x] **Code**: port `_LiteralStr` + representer and the URL template; implement `CreatedFile`, `FileGenerator.generate`, `FileGenerator.generate_goga_config`, and `FileGenerator.generate_tool_configs` (per-contribution loop writing `.goga/tools/<tool>/<file>` in call order, a repeated name replacing) in `goga/onboarding/generator/generator.py`
- [x] **Code**: create `goga/onboarding/generator/__init__.py` — domain docstring + `from .generator import CreatedFile, FileGenerator` + `__all__`
- [x] **Interface verification**: `pytest tests/onboarding/generator/ -v` — contract tests pass; `python -c "from goga.onboarding.generator import FileGenerator"` — exits 0
- [x] **Logic tests** (from the design, transfer verbatim): `test_generate_writes_dockerfile_then_config` — `_clean_cwd`; answers with `docker_image = {"dockerfile": ".goga/Dockerfile", "base_image": "qarium/goga-python-3.13:1.3", "image": "my-app:latest"}`, `language = "python"`, no conventions entry, contributions `[]` → `Path(".goga/Dockerfile").read_text() == "FROM qarium/goga-python-3.13:1.3\n"`; `cfg = yaml.safe_load(...)` → `cfg["language"] == "python"`, `cfg["image"] == "my-app:latest"`, `cfg["dockerfile"] == ".goga/Dockerfile"`, `"base_image" not in cfg`; `[f.path for f in files] == [".goga/Dockerfile", ".goga/config.yml"]`, all `f.tool is None`; `test_generate_empty_language_is_clean_error` — snapshot without `language` → `with pytest.raises(ValueError, match="language")`, `not Path(".goga/config.yml").exists()`; `test_conventions_download_failure_names_url` — answers with `language="python"` and `codemanifest={"usages": {"conventions": ".goga/usages/conventions.md"}}`, `requests.get` monkeypatched to raise `requests.ConnectionError("down")` → `with pytest.raises(RuntimeError, match="https://raw.githubusercontent.com/.*/python/project.md")`, `not Path(".goga/config.yml").exists()`; edge — existing config.yml → generate skips config/Dockerfile and returns only tool-file entries
- [x] **Debugging**: `pytest tests/onboarding/generator/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: the written file passes the project-config loader (`from goga.config import load config schema` — the core schema loader); field order language, image, dockerfile, build, pipeline, codemanifest, tools, usages; `base_image` never in the config
- [x] **Lint**: `ruff check goga/onboarding/generator/` — fix formatting if necessary

### Task 16: tool-config generation with attribution (TDD coding)

Complete the tool-config write path of the generator cell: the staged-commit
story end to end. `generate_tool_configs(contributions)` iterates the
committed contributions in enumeration order and their buffered `(file,
data)` in call order, serializes per the `yaml` practice, and writes
`.goga/tools/<tool>/<file>` — a repeated file name replaces; every entry
returns `CreatedFile(path, tool)` with the tool identity (attribution).
Task 15 implemented the method fully; this task verifies it in isolation
and adds the cross-entity negative trace of the design.

**Usages relevant to this task:**
- `yaml` (inline practice): the tool file serialization.
- `session-participation` (`goga/onboarding/participation/.usages/session-participation.md`):
  the committed contributions — buffers of `write_config` calls.
- `convention`: test conventions; `_clean_cwd` for filesystem tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: `from goga.onboarding.generator import FileGenerator`; `generate_tool_configs([])` is a no-op returning `None`; the method exists on the facade-exported class
- [x] **Code**: ensure `generate_tool_configs` matches the contract (per-contribution, per-buffer loops; `.goga/tools/<tool>/<file>`; replace on repeat; `CreatedFile(path, tool)` appended by `generate`)
- [x] **Interface verification**: `pytest tests/onboarding/generator/ -v` — all pass
- [x] **Logic tests** (from the design, transfer verbatim): `test_generate_tool_configs_with_attribution` — `_clean_cwd`; `answers = SessionAnswers()` with `answers.record("language", "python")` and no docker_image; a committed contribution of `my-tool` with files `[("service.yml", {"token_source": "env"}), ("service.yml", {"interval": 60})]` → `yaml.safe_load(Path(".goga/tools/my-tool/service.yml").read_text()) == {"interval": 60}` (later buffer wins); the last `CreatedFile` has `tool == "my-tool"` and `path == ".goga/tools/my-tool/service.yml"`; `test_failing_hook_discards_files_with_amendments` — `_clean_cwd`; a fake tool subscribed to `amend_config` whose hook buffers `answer("tools", …)` and `write_config("x.yml", …)` then raises; `answers.record("language", "python")` in the setup (the generator's required-field gate would otherwise fire before the assertions); run `collect_contributions(answers)` then `FileGenerator().generate(answers, [])` → `contributions == []`, `"tools" not in answers.snapshot()`, `not Path(".goga/tools").exists()`, config.yml written from the recorded core
- [x] **Debugging**: `pytest tests/onboarding/generator/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: the engine is the single write path of tool configs — data written verbatim, no interpretation; attribution None for engine files, identity for tool files
- [x] **Lint**: `ruff check goga/onboarding/generator/` — fix formatting if necessary

### Task 17: onboarding facade rewrite — `InitLogic`, 13 re-exports, old-module deletion (TDD coding)

Rewrite the onboarding domain facade (`goga/onboarding/`): the new
`InitLogic` at `location: logic.py` (constructor gains `participation:
ToolParticipation` — three injected collaborators), the facade
`__init__.py` re-exporting the 13 embedded types + `InitLogic` in the
embedding order of the CODEMANIFEST, and the deletion of the old modules
`goga/onboarding/answers.py`, `goga/onboarding/questionnaire.py`,
`goga/onboarding/generator.py` together with their old test files
`tests/onboarding/test_answers.py`, `tests/onboarding/test_generator.py`,
`tests/onboarding/test_questionnaire.py` (their cases were ported into the
leaf test layout in Tasks 5–16). The facade must never expose
`InitAnswers`/`GogaConfigAnswers` again. `InitLogic.run()` implements the
eight steps (see Contract Surface — guard, version/tag, moment one,
plan assembly with `resolve_project_name` from `goga/config` and the
conventions check, survey, moment two, generation + report, `return 0`) and
the three error tiers (tool failures soft — already warned inside the
collaborators; session errors — ONE `click.echo(f"Error: {exc}", err=True)`
+ `logger.error`, exit 1, never a traceback; `click.Abort` — exit 1,
quiet). Rewrite `tests/onboarding/test_logic.py` for the new constructor
and API.

**Usages relevant to this task:**
- `convention`: dependency-injection style of the old logic.py; relative
  imports (`from .generator import FileGenerator`, `from .participation
  import ToolParticipation`, `from .questions import SessionAnswers`,
  `from .survey import Questionnaire, apply_skips, assemble_session_plan,
  core_questions`); one module logger.
- `minor-line` (`goga/version/.usages/minor-line.md`): reading the
  installed version and deriving the tag (`host_goga_version` →
  `minor_version`).
- `session-participation`: the two tool moments.
- `survey-run`: the plan assembly and the survey.
- `artifact-generation`: the generation and the file report.
- `onboarding-usage` (`goga/onboarding/.usages/onboarding-usage.md`): the
  facade import list this task realizes (13 embeddings + `InitLogic`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): rewrite `tests/onboarding/test_logic.py` — `from goga.onboarding import InitLogic` plus the 13 re-exported names succeeds; all 14 in `__all__`; `InitLogic(questionnaire, generator, participation)` requires three positional/keyword collaborators; `goga.onboarding` no longer exports `InitAnswers`/`GogaConfigAnswers` (`not hasattr(goga.onboarding, "InitAnswers")`)
- [x] **Code**: rewrite `goga/onboarding/logic.py` — the new `InitLogic` with the eight-step `run()` per the Contract Surface algorithm
- [x] **Code**: rewrite `goga/onboarding/__init__.py` — the domain-facade docstring; imports from the four leaves + `InitLogic` from `.logic`; `__all__` with the 13 embeddings in CODEMANIFEST embedding order followed by `InitLogic` (mirror the same order in the import block)
- [x] **Code**: delete `goga/onboarding/answers.py`, `goga/onboarding/questionnaire.py`, `goga/onboarding/generator.py`; delete `tests/onboarding/test_answers.py`, `tests/onboarding/test_generator.py`, `tests/onboarding/test_questionnaire.py`
- [x] **Code**: adapt `tests/commands/test_init.py` to the deletion — replace its module-level imports of the deleted modules (`from goga.onboarding.answers import GogaConfigAnswers, InitAnswers`; `from goga.onboarding.questionnaire import Questionnaire`) with facade imports (`from goga.onboarding import FileGenerator, InitLogic, Questionnaire, ToolParticipation`); rewrite the tests that drive the real `InitLogic` (the `mock_q.ask` / `InitAnswers` stubbing of `test_init_cli_command`) into the `mock.patch.object(_cmd_init_module, "InitLogic", ...)` pattern used by the file's other tests — the exit-code propagation they verify is unchanged. Also drop the stale `GogaConfigAnswers` mention from the `_run_goga_config` docstring in `tests/config/test_resolve_project_name_flows.py` (a leftover docstring reference, not an import)
- [x] **Interface verification**: `pytest tests/onboarding/test_logic.py -v` — contract tests pass; `pytest tests/commands/ --co -q` — collects cleanly; `grep -r "InitAnswers\|GogaConfigAnswers" goga/ tests/` returns no hits
- [x] **Logic tests** (from the design, transfer verbatim): `test_existing_config_ends_session_silently` — `_clean_cwd` with `.goga/config.yml` pre-created; stubbed collaborators asserting no calls → `run() == 0`, neither `questionnaire.run` nor `participation.collect_declarations` nor `generator.generate` called; `test_unreadable_version_is_clean_error` — `host_goga_version` monkeypatched to raise `PackageNotFoundError("goga")` → `run() == 1`, "Error:" in output, "Traceback" not in output; `test_broken_package_import_is_clean_session_error` — enumeration monkeypatched to a package whose facade raises on import (platform-wrapped `ImportError`) → `run() == 1`, "Error:" and "goga_tool_broken" in output, "Traceback" not in output; edge — zero invited tools and no installed packages → the session degrades to the plain behavior (`declarations == []`, `contributions == []`, core-only survey)
- [x] **Debugging**: `pytest tests/onboarding/ -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: the facade import order matches the embeddings; no old names anywhere; the `InitLogic` error tiers hold (one message, no traceback, exit codes 0/1)
- [x] **Lint**: `ruff check goga/onboarding/` — fix formatting if necessary

### Task 18: `init` command — `-t/--tool` invitation flag (TDD coding)

Extend the CLI command at `location: goga/commands/init/init.py` with the
repeatable `-t/--tool` option: `@click.option("-t", "--tool", "tools",
multiple=True, help=...)` (help text mirroring `init.md`). The command
signature becomes `init(tpl, upgrade, ref, tools: tuple[str, ...])`.
Validation order (contract algorithm 1–6): ref placement check (ported
verbatim) → mode resolution (ported; mutual exclusion) → invitation
validation (`tools` non-empty AND mode UPGRADE → message `-t/--tool
requires an onboarding session and --upgrade runs none`, exit 1) → dedup
preserving flag order (`list(dict.fromkeys(tools))` — the tuple→list
conversion happens HERE; the facade signature
`ToolParticipation(invited: list[str])` receives a list) →
already-initialized guard (BARE_ONBOARDING only, ported) → dispatch
(UPGRADE: `Scaffold().upgrade(ref)`; both onboarding modes:
`InitLogic(Questionnaire(), FileGenerator(), ToolParticipation(invited=
deduped))` → `ctx.exit(logic.run())`). The command passes names through as
opaque data — no installation checks. Port the existing ref/mode/guard
logic verbatim from the current init.py; do not restructure it. The
module-level imports of `tests/commands/test_init.py` were already
adapted to the facade in Task 17 — this task only extends the file with
the `-t/--tool` tests.

**Usages relevant to this task:**
- `click` (`.goga/usages/cooks/click.md`): `@click.option(multiple=True)`;
  the command wrapper conventions.
- `onboarding-usage` (`goga/onboarding/.usages/onboarding-usage.md`): the
  session API and the invitation semantics; the message text of the
  rejection.
- `scaffold-usage` (`goga/scaffold/.usages/scaffold-usage.md`): the
  `Scaffold` API for the UPGRADE dispatch.
- `conventions` (`.goga/usages/conventions.md`): the command's code style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): extend `tests/commands/test_init.py` — `runner.invoke(init_cli, ["--help"])` shows `-t, --tool`; the command accepts repeated `-t`; `-t` with `--upgrade` rejected
- [x] **Code**: add the `tools` option and the parameter to `init` in `goga/commands/init/init.py`; insert the invitation-validation step and the dedup step in the contract order; wire `ToolParticipation` into both onboarding dispatch branches
- [x] **Interface verification**: `pytest tests/commands/test_init.py -v` — contract tests pass; the pre-existing mode/ref/guard tests still pass (ported logic untouched)
- [x] **Logic tests** (from the design, transfer verbatim): `test_init_rejects_tools_with_upgrade` — `runner.invoke(init_cli, ["--upgrade", "-t", "my-tool"])` → exit 1, `"-t/--tool requires an onboarding session" in result.output`; `test_init_dedup_preserves_flag_order` — stubbed `InitLogic` capturing the constructed `ToolParticipation`; `["-t", "b", "-t", "a", "-t", "b"]` → `captured.invited == ["b", "a"]`; edge — `-t` with `<tpl>` allowed (SCAFFOLD_THEN_ONBOARDING carries the invitation into the session)
- [x] **Debugging**: `pytest tests/commands/test_init.py -x` — fix implementation code until all tests pass
- [x] **Contract re-verification**: validation order matches the contract algorithm 1–6; opaque passthrough (no installation checks in the command); `--upgrade` never runs onboarding
- [x] **Lint**: `ruff check goga/commands/init/` — fix formatting if necessary

### Task 19: Integration tests — end-to-end session with invited tools

Cross-entity verification of the whole feature through the CLI: invitation
→ dedup → both moments → survey → amendments → generation → attributed
report. Rewrite `tests/onboarding/test_integration.py` (the old file tests
the old API). Setup pattern: `_clean_cwd`; fake installed
`goga_tool_my-tool` package (enumeration monkeypatched; `register_hooks`
subscribes both actions) — the `tests/hooks/conftest.py` `sys.modules`
injection pattern; `CliRunner` inputs walking the whole survey; caplog at
WARNING.

**Usages relevant to this task:**
- `onboarding-usage`: the full session API composition the test drives.
- `session-participation`: the fake tool's hook bodies (declare/amend
  contexts).
- `tool-contexts` (`goga/onboarding/participation/.usages/tool-contexts.md`):
  the hook signature pattern for the fakes.
- `artifact-generation`: the expected artifacts and the report format.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Rewrite `tests/onboarding/test_integration.py` with the shared fake-tool fixtures (declare + amend subscribed; declares a `token` input; buffers `answer("tools", {"my-tool": "latest"})` and `write_config("service.yml", {...})`)
- [x] Test cross-entity interaction: `test_init_full_session_with_invited_tool` — `runner.invoke(init_cli, ["-t", "my-tool", "-t", "my-tool"])` with the full survey inputs → `result.exit_code == 0`; `cfg = yaml.safe_load(Path(".goga/config.yml").read_text())` → `cfg["tools"] == {"my-tool": "latest"}`; `Path(".goga/tools/my-tool/service.yml").exists()`; `"(tool: my-tool)" in result.output`
- [x] Test edge case: `test_tool_failure_never_changes_exit_code` — the full-session setup with the tool's `amend_config` hook raising instead of contributing → `result.exit_code == 0`; `not Path(".goga/tools/my-tool").exists()`; a warning naming the tool in caplog
- [x] Test edge case: `test_skip_of_base_image_collapses_dockerfile_branch` — fake tool whose `declare_session` hook calls only `context.skip("docker_image.base_image")`; CliRunner inputs: language `python`, every confirm gate `n` except the Dockerfile gate `y`, dockerfile path default (empty input), built image name `my-app:latest` → `result.exit_code == 0`; `"Base image" not in result.output`; `cfg["image"] == "my-app:latest"` and `"dockerfile" not in cfg` and `"base_image" not in cfg`; `not Path(".goga/Dockerfile").exists()`
- [x] Run validation: `pytest tests/onboarding/ -x` then the full suite `pytest tests/ -x` — all pass (137 onboarding, 5471 total)
- [x] Final platform check: `goga lint` — 0 errors (76+ cells; the four new cells join the graph)

---

## Validation Commands

- `pytest tests/version/ -v`: version cell tests (`minor_version`)
- `pytest tests/hooks/ -v`: hooks catalog + facade re-export tests
- `pytest tests/onboarding/questions/ -v`: questions cell tests
- `pytest tests/onboarding/participation/ -v`: participation cell tests
- `pytest tests/onboarding/survey/ -v`: survey cell tests
- `pytest tests/onboarding/generator/ -v`: generator cell tests
- `pytest tests/onboarding/ -v`: onboarding domain (logic + integration)
- `pytest tests/commands/ -v`: init CLI tests
- `pytest tests/ -x`: Run all tests (full suite)
- `ruff check goga/`: Lint check (line-length 120, mccabe 10)
- `goga lint`: Facade/contract graph check — must stay 0 errors
- `python -c "from goga.onboarding import InitLogic, Question, QuestionGroup, SessionAnswers, SessionPlan, Questionnaire, core_questions, assemble_session_plan, apply_skips, ToolParticipation, ToolDeclaration, ToolContribution, FileGenerator, CreatedFile"`: Verify that all facade entities are importable
- `python -c "from goga.hooks import HookRegistry, wrap_context, build_hook_arguments, enumerate_tool_packages"`: Verify the hooks facade re-exports
- `python -c "from goga.version import minor_version"`: Verify the version facade re-export

---

## Completion Criteria

- [x] Every contract entity is implemented in the correct `location`
- [x] Every contract entity is accessible from the facade
- [x] Properties and methods match the declared API
- [x] Descriptions are reflected in behavior
- [x] Contract dependencies are met
- [x] Re-exports are accessible from the facade
- [x] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [x] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [x] Integration tests exist where cross-entity scenarios require them
- [x] No package boundary was expanded
- [x] `CODEMANIFEST` files were not modified (contract is read-only)
- [x] All validation commands pass
- [x] Every Usages entry is mentioned in at least one task (Phase 2 calibration)
- [x] The old modules `goga/onboarding/{answers,questionnaire,generator}.py` and their test files are deleted; `InitAnswers`/`GogaConfigAnswers` appear nowhere
- [x] The written `.goga/config.yml` passes the project-config loader
- [x] The image tag is never hardcoded — it threads `host_goga_version` → `minor_version` → `core_questions`
