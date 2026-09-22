# Plan: `add-hooks-to-config`

<!-- Topic: `.goga/history/2026/add-hooks-to-config/` — open the config domain to tool
hooks via an in-memory amendment checkpoint, rename the model field `lang` ->
`language`, and switch the nine host-side config-consuming surfaces. -->

## Purpose

Open the config domain to tool hooks. After implementation:

- `goga/config/hooks` (the zone, contract already materialized) exists in code: the
  per-tool read-and-amend view (`ConfigAmendment`), the buffered entries
  (`PathAmendment`), the merge (`merge_config_amendments`), the result
  (`ConfigOverlay`, `AppliedAmendment`, `ToolAmendment`), the checkpoint surface
  (`ConfigHooks`), and the 7-name facade — all importable from `goga.config.hooks`.
- The `ProjectConfig` model field `lang` is renamed to `language` (authored YAML
  vocabulary unchanged; the loader already reads the `language` key); the `goga config`
  alias bridge is deleted; `goga contract` resolves `config.language`.
- The hooks catalog declares the hard action `config / amend_config`.
- The nine host-side config-consuming surfaces (pipeline, lint, contract, install,
  config, build, topics, usages status, usages sync) deliver the checkpoint after the
  authored load, print the amendment summary to stderr, and consume
  `overlay.config` downstream.
- In-container loads (`goga/build/__main__`, the in-container pipeline counterpart)
  stay authored-only; `goga/commands/usages`, `goga/onboarding`, `goga/scaffold`
  are untouched.

The most important gaps: the zone has no `.py` files at all (contract only), the model
still carries `lang`, the catalog lacks the `config` record, and every consumer is
authored-only. Strategy: implement in the verified dependency order of the design
document (catalog → rename → zone leaves-to-root → consumers → integration), each task
TDD with the pinned message formats and the exact test scenarios of the design's
Test Stack Trace.

Source of truth: `.goga/history/2026/add-hooks-to-config/design.md` (verified against
the real sources; its traces, algorithms, and test scenarios are transferred into the
tasks below). CODEMANIFEST contracts are already materialized and validated
(`goga lint`: 80 cells, 0 errors) — they are **read-only** for the implementation
agent.

## Context

### Contract Surface

#### Cell: `goga/config/hooks` (the zone — all new code)

**Entity: `ConfigAmendment(config: ProjectConfig)`**
- Type: class (Entity)
- Declared `location`: `amendments.py`
- Facade obligation: importable from `goga.config.hooks` (listed in `__all__`)
- Properties: `config -> ProjectConfig` — the authored loaded project configuration,
  read-only for the receiving hook
- Methods:
  - `set(path: str, value: str | int | bool | list[str])` — buffer one amendment that
    applies only where the authored configuration is silent at the path
  - `force(path: str, value: str | int | bool | list[str])` — buffer one amendment
    that overwrites the authored value at the path
- Semantic requirements: reads deliver the authored configuration — read-only and
  identical for every tool; the buffered contributions belong to this tool alone; a
  later amendment of this tool on the same path replaces its earlier one; a set on a
  non-silent path is dropped silently (the drop happens in the merge, not here)
- Imported dependencies: `ProjectConfig` (from `goga/config/project`)
- Annotation context: `convention` for data-model rules and intra-package imports;
  `registering-hooks` for the hook signature that receives this view

**Entity: `PathAmendment(path: str, intent: str, value: str | int | bool | list[str])`**
- Type: class (Entity, pure data)
- Declared `location`: `amendments.py`
- Facade obligation: importable from `goga.config.hooks`
- Semantic requirements: pure data, constructed by the amendment buffer alone;
  `intent` is exactly `set` or `force`

**Entity: `ToolAmendment(tool: str, amendments: list[PathAmendment])`**
- Type: class (Entity, pure data)
- Declared `location`: `overlay.py`
- Facade obligation: importable from `goga.config.hooks`
- Semantic requirements: the committed contribution of one tool, amendments in buffer
  order; `tool` is the tool identity assigned by the platform

**Entity: `AppliedAmendment(tool: str, path: str, intent: str)`**
- Type: class (Entity, pure data)
- Declared `location`: `overlay.py`
- Facade obligation: importable from `goga.config.hooks`
- Semantic requirements: carries NO value — no configuration value travels into any
  output; `intent` is exactly `set` or `forced`

**Entity: `ConfigOverlay(config: ProjectConfig, applied: list[AppliedAmendment])`**
- Type: class (Entity)
- Declared `location`: `overlay.py`
- Facade obligation: importable from `goga.config.hooks`
- Properties: `config -> ProjectConfig` (the effective configuration of the run);
  `applied -> list[AppliedAmendment]` (one record per applied path, enumeration
  order); `summary_lines -> list[str]` (one header plus one line per applied
  amendment; empty when nothing applied; no configuration value ever appears)
- Semantic requirements: the effective configuration is a `ProjectConfig` — every
  downstream consumer of the run observes it

**Routine: `merge_config_amendments(base: ProjectConfig, contributions: list[ToolAmendment]) -> overlay: ConfigOverlay`**
- Type: function
- Declared `location`: `overlay.py`
- Facade obligation: importable from `goga.config.hooks`
- Semantic requirements (from the contract Algorithm): validate every amendment
  against the configuration model's type tree (unknown path / non-leaf address /
  wrong type = structural failure of the contributing tool, raised naming the tool,
  nothing applies); resolve deterministically (authored silence = absence markers
  None / empty mapping / empty list; a set on a non-silent path is dropped silently;
  force beats set regardless of order; among equal intent the later tool wins);
  compose in memory (materialize missing intermediates, wholesale list replacement,
  individual mapping entries, reconstruct affected instances); collect one
  `AppliedAmendment` per applied path in enumeration order; return the overlay.
  Deterministic, pure, structurally valid result. No filesystem. No semantic
  validation.

**Entity: `ConfigHooks()`**
- Type: class (Entity)
- Declared `location`: `events.py`
- Facade obligation: importable from `goga.config.hooks`
- Methods: `amend_config(config: ProjectConfig) -> overlay: ConfigOverlay` — deliver
  the config-amendment checkpoint and return the effective configuration with its
  applied amendments
- Semantic requirements: cheap construction (no enumeration, no imports at
  construction); one `HookRegistry` per run, built lazily; every context built from
  the values the caller passes (no repository/git/file reads); commit granularity is
  the tool; a raising hook or structurally malformed contribution is a hard failure —
  clean error naming the tool and the action, first failure stops, the tool's whole
  contribution discarded; an address without subscriptions returns the passthrough
  overlay (the passed object itself, empty applied, empty summary); the zone never
  prints
- Imported dependencies: `HookRegistry`, `wrap_context`, `build_hook_arguments`,
  `declared_actions` (from `goga/hooks`); practices `per-tool-delivery`,
  `registering-hooks` (from `goga/hooks`); the nine project models (from
  `goga/config/project`)

#### Changed entities outside the zone

- `ProjectConfig` (`goga/config/project/config.py:189`) — field `lang: str` →
  `language: str` (position and requiredness unchanged, `kw_only=True`); property
  `lang -> str` → `language -> str`.
- `load_project_config` (`goga/config/project/loader.py:754,773`) — local
  `lang = _parse_language(data)` → `language`; assembly kwarg `lang=lang` →
  `language=language`. `_parse_language` itself unchanged.
- `declared_actions` (`goga/hooks/catalog/catalog.py`) — `_DECLARED_ACTIONS` gains
  `Action(domain="config", name="amend_config", error_class="hard")` appended after
  the build block.
- `goga config` (`goga/commands/config/config.py:10,55-56`) — `_ALIAS_MAP` and the
  alias rewrite in `_resolve_option` deleted; `language` resolves directly through
  the unchanged `getattr` traversal.
- `goga contract` (`goga/commands/contract/contract.py:162`) — `config.lang` → the
  effective config's `language` (CLI `--lang` option and callback params stay).
- The nine consumers (Tasks 8–10).

### Re-exports

None — no `->Name: {}` embedding blocks exist in any touched CODEMANIFEST. The zone's
facade obligation is the Python-level `__all__` of `goga/config/hooks/__init__.py`
(exactly the seven contract names, alphabetical). The facade `goga/config`
(`goga/config/__init__.py`) is NOT extended — consumers import
`from ...config.hooks import ConfigHooks` directly.

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — project-wide Python rules: relative
  imports, `kw_only` dataclasses, Google docstrings, logging discipline, blank-line
  block formatting, test structure (`tests/<package>/...` mirrors source). Used by
  every touched file.
- `click` (`.goga/usages/cooks/click.md`) — CLI framework practices: echo to stderr,
  `ClickException`, `CliRunner` testing. Used by the seven command cells and — newly —
  `goga/usages/status`, `goga/usages/sync`.
- `yaml` (inline, `goga/config/project`) — unchanged; `yaml.safe_load` in the loader;
  the rename touches no parse logic.

### Imported Usages

- `per-tool-delivery` from `goga/hooks` — `goga/hooks/.usages/per-tool-delivery.md`.
  The staged delivery loop skeleton (`HookRegistry`/`build_once`,
  `subscriptions_for`, `self_context`, `wrap_context`, `build_hook_arguments`,
  group-per-tool, commit-after-success). `ConfigHooks.amend_config` applies it as
  written; the deviation from its soft example (warn-and-continue) is the action's
  hard error class from the catalog record.
- `registering-hooks` from `goga/hooks` — `goga/hooks/.usages/registering-hooks.md`.
  The hook signature contract (`context`/`self` offered names) and the failure
  behavior behind the checkpoint; drives `build_hook_arguments` usage and the hard
  stop.
- `checkpoints` from `goga/config/hooks` — `goga/config/hooks/.usages/checkpoints.md`
  (already created by the apply stage; imported by the nine consumer CODEMANIFESTs).
  The consumer-side delivery shape: authored load → `amend_config(config=...)` →
  print `summary_lines` to stderr → consume `overlay.config`; the in-container
  authored-only rule.

### Local Usages

- `goga/config/hooks/.usages/checkpoints.md` — functional category: consuming the
  checkpoint from host-side commands. Status: created by the apply stage, current,
  no additions needed (the `print_summary_to_stderr` placeholder is consumer
  pseudocode by design). Related entities: `ConfigHooks`, `ConfigOverlay` and every
  consumer. No creation task.
- `goga/config/.usages/registering-hooks.md` — functional category: how a
  `goga_tool_*` package subscribes to `config / amend_config`. Status: extends
  existing — ONE bullet added to the path-vocabulary list covering the
  materialization corner and the `DepConfig` value rules (verbatim wording in
  Task 5). Related entities: `merge_config_amendments`, `ConfigAmendment`.
  Creation task reference: Task 5.
- `goga/config/.usages/project-configuration.md` — updated by the apply stage
  (`config.language` accessor examples, zone-entry note); no further updates needed.

### External Dependencies

- `click` — CLI framework (stderr echo, `ClickException`, `CliRunner`).
- PyYAML — `yaml.safe_load` in the loader (unchanged).
- `pytest` / `pytest-cov` — test runner; fixtures `pin_package_environment` and
  `install_tool_package` from `tests/hooks/conftest.py` (re-exported by the zone's
  `tests/config/hooks/conftest.py`).
- `ruff` — lint and format (`ruff check <src>/`, config in `pyproject.toml`).
- The hooks platform facade `goga.hooks` — exports `HookRegistry`,
  `build_hook_arguments`, `declared_actions`, `wrap_context` (verified in
  `goga/hooks/__init__.py:19-27`).

### Interaction Diagram (verbatim from the design)

```
                host-side command / module (9 surfaces)
                pipeline lint contract install config build topics | status sync
                    |                       |
                    | load_project_config() |  (authored load — loader stays hooks-free)
                    v                       |
                ProjectConfig (authored)    |
                    |                       |
                    | ConfigHooks().amend_config(config=authored)
                    v                       |
             goga/config/hooks (the zone)   |     summary_lines -----> click.echo(err=True)
              events.py  ConfigHooks -------+---> stderr (caller prints; zone never prints)
                |  _ensure_registry -----> HookRegistry.build_once()   [goga/hooks]
                |  subscriptions_for("config","amend_config")         [goga/hooks]
                |  per tool: ConfigAmendment(config) -> wrap_context -> build_hook_arguments
                |             hook(**args, self=ToolContext)          [goga/hooks]
                |  committed: ToolAmendment(tool, [PathAmendment...])
                v
              overlay.py  merge_config_amendments(base, contributions)
                |   type-tree validation -> resolution -> composition
                v
              ConfigOverlay(config=effective, applied=[AppliedAmendment...])
                    |
                    +---> overlay.config   -> every downstream consumer of the run
                    +---> overlay.summary_lines -> the caller prints to stderr

             goga/hooks/catalog: declared_actions carries config/amend_config (hard)
             goga/build/__main__ + in-container loads: authored-only, no checkpoint
```

## Facts

- The zone contract `goga/config/hooks/CODEMANIFEST` exists (7 types, locations
  `amendments.py`, `overlay.py`, `events.py`); the directory holds NO `.py` files yet.
- `goga/config/hooks/.usages/checkpoints.md` exists and is current.
- `goga/config/project/config.py:189` still declares `lang: str`;
  `loader.py:754` reads `lang = _parse_language(data)` and `loader.py:773` assembles
  `lang=lang`; `_parse_language` (loader.py:183-193) already reads `data["language"]`
  and raises `KeyError` on a missing key.
- `goga/hooks/catalog/catalog.py` `_DECLARED_ACTIONS` has no `config` domain record;
  `declared_actions()` returns records sorted by (domain, name) — list position is
  cosmetic.
- `goga/commands/config/config.py:10` still carries `_ALIAS_MAP = {"language": "lang"}`
  and the rewrite at lines 55-56; `goga/commands/contract/contract.py:162` still
  reads `config.lang`.
- The nine consumer load sites exist exactly as the design traces them:
  `pipeline.py:151-153`, `lint.py:24-30` (swallowing `except` → `ignore=None`),
  `install.py:305-314` (bulk path only), `config.py:117-130`,
  `build.py:301-304` (after the docker check; the home preamble loads separately),
  `topics.py:48-61` (`_topics_section`, `FileNotFoundError` → `None`),
  `status.py:62`, `sync.py:43` (fail-loud plain modules).
- The hooks facade `goga/hooks/__init__.py` exports `HookRegistry`,
  `build_hook_arguments`, `declared_actions`, `wrap_context` — the zone imports the
  platform through `...hooks`, never deep platform modules.
- The delivery-loop precedent exists and runs for real:
  `goga/pipeline/hooks/events.py` (`PipelineHooks`), with the identical hard-failure
  message format.
- All nine models are `@dataclass(kw_only=True, frozen=True)` with defaults — the
  materialization default instances (`BuildConfig()`, `ReviewConfig()`, …) construct
  with no arguments.
- Zone test precedent: `tests/pipeline/hooks/{conftest,test_amendments,test_events,
  test_overlay,test_identity}.py`; facade `__all__` assertions live in the per-module
  test files there.
- 68 test files contain the token `lang`; the design's sweep list (Task 2) separates
  model references (must change) from the CLI `--lang` surface and `_write_goga_yml(
  lang=...)` YAML-writing helpers (stay).
- No import cycles: the zone imports only `goga/hooks` and `goga/config/project`
  (relative: `...hooks` and `..project`); no consumer is imported by a provider.

## Gap Analysis

- Missing contract entities: all 7 zone types + the zone facade `__init__.py`
  (nothing of the zone exists in code).
- Missing facade exposure: `goga.config.hooks` is not a package yet.
- Rename not applied: model field, loader kwarg/local, `contract.py:162`, alias map
  still present; the model-level test vocabulary still says `lang`.
- Catalog record missing: no `config / amend_config` action.
- Behavioral gaps: the nine consumers are authored-only — no checkpoint delivery, no
  stderr summary, no effective-config consumption; lint's swallow would mask a hard
  failure without the two-step.
- Test coverage gaps: no `tests/config/hooks/` suite; no consumer switch tests; the
  rename sweep pending; no passthrough integration test.
- Existing code reused: the platform (`goga/hooks`), the loader (unchanged parse),
  the `PipelineHooks` delivery precedent, the `tests/hooks/conftest.py` fixtures,
  the consumers' existing `(FileNotFoundError, KeyError, ValueError,
  yaml.YAMLError)` wrappers.
- CODEMANIFEST state: all contracts already materialized and validated — zero
  contract edits belong in this plan.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).

### Task 1: The catalog record — `config / amend_config` (TDD coding)

**Cell**: `goga/hooks/catalog`. Append the hard action record to `_DECLARED_ACTIONS`
in `goga/hooks/catalog/catalog.py` — the leaf change everything else resolves
against (the zone's `amend_config` step 2 looks the record up via `declared_actions()`).
The contract requirement (catalog CODEMANIFEST): "The catalog carries the config
amendment action — the record domain="config", name="amend_config", error_class=
"hard": the first failing tool of the action stops the command with a clean error
naming the tool and the action; a structurally malformed contribution of the
delivery is treated identically." Append after the build block
(`catalog.py`, the `Action(domain="build", ...)` records end at line 58); the list's
`declared_actions()` sorts by (domain, name), so list position is cosmetic. No other
record changes.

**Usages relevant to this task:**
- `convention`: module docstring and code style already in place — match the
  surrounding record formatting exactly.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: extend `tests/hooks/catalog/test_catalog.py` with
  `test_config_amend_config_record_present` — assert
  `Action(domain="config", name="amend_config", error_class="hard") in declared_actions()`
  and that the pre-existing records are unchanged (compare against a pinned expected
  list of all other records) (expected to fail at this stage)
- [x] **Code**: append `Action(domain="config", name="amend_config", error_class="hard"),`
  to `_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py`, after the build block
- [x] **Interface verification**: `python -m pytest tests/hooks/catalog/ -x` — all pass
- [x] **Logic tests**: verify ordering stability — `declared_actions()` still returns
  every record ordered by (domain, name); no record duplicated
- [x] **Debugging**: `python -m pytest tests/hooks/ -x` — fix implementation code
  until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: the record's domain/name/error_class match the
  catalog CODEMANIFEST requirement verbatim; no other record touched
- [x] **Lint**: `ruff check goga/hooks/catalog/` — fix formatting if necessary

### Task 2: The model rename `lang` → `language` + touch points + test sweep (TDD coding)

**Cell**: `goga/config/project` (+ two touch points in `goga/commands/{contract,config}`).
The rename is the base the zone and every consumer build on. The authored YAML
vocabulary is UNCHANGED — the loader already reads `data["language"]`
(`_parse_language`, loader.py:183-193, raises `KeyError` on a missing key, matching
the reworded contract Algorithm step 4). Changes exactly:

1. `goga/config/project/config.py:189` — field `lang: str` → `language: str`
   (position and requiredness unchanged; `kw_only=True` keeps all call sites
   keyword-based); property annotation `lang -> str` → `language -> str`; docstring
   `` `lang`: `` → `` `language`: ``.
2. `goga/config/project/loader.py:754` — local `lang = _parse_language(data)` →
   `language = _parse_language(data)`; `loader.py:773` — `ProjectConfig(lang=lang,
   ...)` → `ProjectConfig(language=language, ...)`. `_parse_language` unchanged.
3. `goga/commands/contract/contract.py:162` —
   `lang = lang if lang is not None else config.lang` → `... else config.language`
   (the CLI param `lang` and the `--lang` option stay — CLI surface, not the model).
4. `goga/commands/config/config.py` — delete `_ALIAS_MAP` (line 10) and the rewrite
   `if parts[0] in _ALIAS_MAP: parts[0] = _ALIAS_MAP[parts[0]]` (lines 55-56);
   `language` resolves through the unchanged `getattr` traversal; `goga config lang`
   stops resolving ("Option not found" — intended, one vocabulary).
5. `goga/config/project/__init__.py` — complete the cell facade to its own contract:
   import `DepConfig` and `LintConfig` from `.config` and add both to `__all__`.
   The project CODEMANIFEST declares both types, but the facade currently exports
   only 7 of the 9 model names — and the zone (Tasks 4–5) imports the nine model
   names from `..project`. This is an implementation completion of the existing
   contract, not a CODEMANIFEST change; the parent facade `goga/config/__init__.py`
   is NOT touched.

Do NOT add a `lang` compat property, alias, or deprecation shim — the rename is a
clean same-major-release break.

**Usages relevant to this task:**
- `convention`: `kw_only` dataclass field style, Google docstrings; keep field
  position in the dataclass body unchanged.
- `yaml`: unchanged — the loader's `yaml.safe_load` parse is untouched; only the
  local variable and the assembly kwarg rename.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: in `tests/config/test_config.py` — update the kw_only
  TypeError match string `"lang"` → `"language"`; add the breaking-removal guard
  `assert "lang" not in ProjectConfig.__dataclass_fields__`; assert
  `"language" in ProjectConfig.__dataclass_fields__`; assert the project facade
  exposes the full contract API — all nine model names plus `load_project_config`
  in `goga.config.project.__all__` (`DepConfig` and `LintConfig` arrive with
  change 5) (expected to fail at this stage)
- [x] **Code**: apply changes 1–5 above (config.py field + property, loader.py local
  + kwarg, contract.py:162, config.py alias-map deletion, project `__init__.py`
  facade completion)
- [x] **Interface verification**: `python -m pytest tests/config/ -x` — the project
  cell suites pass
- [x] **Logic tests**: the mechanical rename sweep of existing suites — model
  references `lang=` / `.lang` / `"lang" in ProjectConfig.__dataclass_fields__` →
  the `language` forms, in: `tests/config/test_config.py`,
  `tests/config/test_loader.py`, `tests/config/test_integration.py`,
  `tests/config/test_tools_integration.py`,
  `tests/config/test_project_cell_contract.py`,
  `tests/integration/test_parallel_flow.py`, `tests/integration/test_runtime_isolation.py`,
  `tests/integration/test_workflow_entity.py`, `tests/integration/test_pipeline_cli.py`,
  `tests/integration/test_docker_update_launch_integration.py`, all changed files under
  `tests/commands/pipeline/` (12 files),
  `tests/commands/build/test_build_runtime_isolation_integration.py`,
  `tests/commands/build/test_build.py`, `tests/build/test_build.py`,
  `tests/onboarding/generator/test_generator.py`.
  Explicitly NOT renamed: the CLI `--lang` surface (`tests/commands/test_contract.py`
  param assertions keep `lang`), the dispatcher signature tests
  (`tests/contract/test_dispatcher.py`), and the `_write_goga_yml(lang=...)` helper
  params in `tests/contract/test_integration_*.py` (YAML-writing helpers, not model
  references)
- [x] **Debugging**: `python -m pytest tests/ -x` — fix implementation code until all
  tests pass (do NOT fix test code); on any residual `AttributeError: lang` /
  `TypeError: unexpected keyword 'lang'`, sweep the missed file the same way
- [x] **Contract re-verification**: absence sweep —
  `grep -rn "\.lang\b\|lang=" goga/ | grep -v "__main__\|dispatcher\|--lang\|_write_goga_yml"`
  returns no model-field references; the only remaining `lang` tokens in `goga/` are
  the CLI `--lang` option/callback (`goga/commands/contract/contract.py`,
  `goga/contract/dispatcher.py`) and loader internals already renamed;
  `grep -rn "lang" tests/ | grep -v "language\|--lang\|_write_goga_yml\|test_contract\|test_dispatcher"`
  returns no model references
- [x] **Lint**: `ruff check goga/config/project/ goga/commands/contract/ goga/commands/config/` — fix formatting if necessary

### Task 3: Zone scaffold + `amendments.py` — `ConfigAmendment`, `PathAmendment` (TDD coding)

**Cell**: `goga/config/hooks`. First code inside the zone: the package scaffold and
the per-tool read-and-amend view with its buffered entries. `ConfigAmendment` is the
view a hook receives through `wrap_context` — the authored config read-only plus this
tool's amendment buffer. `PathAmendment` is pure data. Verbatim design (Algorithm
Design — `ConfigAmendment` / `PathAmendment`):

```
ConfigAmendment: @dataclass(kw_only=True)          # NOT frozen — it carries the buffer
  config: ProjectConfig                            # the authored object, shared per run
  _amendments: dict[str, PathAmendment] = field(init=False, default_factory=dict,
                                                repr=False)
  set(path, value):
    _amendments[path] = PathAmendment(path=path, intent="set", value=value)
  force(path, value):
    _amendments[path] = PathAmendment(path=path, intent="force", value=value)

PathAmendment: @dataclass(frozen=True, kw_only=True)
  path: str; intent: str ("set" | "force"); value: str | int | bool | list[str]
```

Algorithm (each method): construct the entry, store it keyed by `path` — a later
call on the same path replaces the earlier one and keeps the first-insertion
position (Python dict semantics = "buffer order"). No validation, no application, no
error paths here (structural validation belongs to the merge; the authored-silence
drop belongs to the resolution). Edge cases: a non-`str` `path` or an
out-of-vocabulary `value` is stored verbatim and fails later in the merge's
validation, naming the tool — the delivery never crashes on hook input.

The buffer is private (`_amendments`), read by the delivery walk of the same package
(the pipeline zone's `amendment._contribution` precedent — `list(buffer.values())`
at commit). Imports: `from ..project import ProjectConfig` (equivalently
`...config.project`).

**Usages relevant to this task:**
- `convention`: `kw_only` dataclasses, Google docstrings with Args/Returns/Raises,
  relative intra-package imports, module docstring stating the cell responsibility.
- `registering-hooks` (from `goga/hooks`, via the zone Imports): the hook signature
  that receives this view — `set`/`force` are the only write surface a hook gets.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/config/hooks/__init__.py` (empty) and
  `tests/config/hooks/test_amendments.py` — assert `ConfigAmendment` and
  `PathAmendment` are importable from `goga.config.hooks.amendments`, the constructor
  is `kw_only` (`TypeError` on positional args), `set`/`force` exist with the declared
  signatures, `config` is a plain attribute, `PathAmendment` is frozen (`FrozenInstanceError`
  on write) and `kw_only` (expected to fail at this stage)
- [x] **Code**: create `goga/config/hooks/__init__.py` as a docstring-only
  placeholder (the facade `__all__` is written in Task 7 — the zone's `__init__.py`
  is written last within the zone) and `goga/config/hooks/amendments.py` implementing
  the two dataclasses exactly as the block above
- [x] **Interface verification**: `python -m pytest tests/config/hooks/test_amendments.py -x` — all pass
- [x] **Logic tests**: buffer semantics in `test_amendments.py` —
  (a) `set("build.agent", "claude")` stores `PathAmendment(path="build.agent",
  intent="set", value="claude")` and `force(...)` stores `intent="force"`;
  (b) same-path replacement: `set("p", 1)` then `force("p", 2)` → the buffer holds
  exactly one entry, `intent="force"`, `value=2`, at the first-insertion position
  (dict order — add a second distinct path and assert positions);
  (c) isolation: two `ConfigAmendment` instances over the same config never share
  buffer state;
  (d) verbatim storage: a non-`str` path / out-of-vocabulary value is stored without
  raising (validation belongs to the merge);
  (e) `wrap_context` interop: attribute assignment on the proxy raises
  (`FrozenInstanceError`-style block), method calls pass through — reuse the
  `tests/hooks/dispatch/test_delivery.py` expectations
- [x] **Debugging**: `python -m pytest tests/config/hooks/ tests/hooks/ -x` — fix
  implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: both entities live at `location: amendments.py`;
  signatures match the CODEMANIFEST (`set(path: str, value: str | int | bool |
  list[str])`); no validation/no application added here
- [x] **Lint**: `ruff check goga/config/hooks/` — fix formatting if necessary

### Task 4: `overlay.py` data layer — `ToolAmendment`, `AppliedAmendment`, `ConfigOverlay`, the descriptor table (TDD coding)

**Cell**: `goga/config/hooks`. The pure-data carriers of the merge result plus the
hand-written validation table the merge resolves paths against (the pipeline zone's
hand-written `_STAGE_FIELDS` precedent). Verbatim design:

```
ConfigOverlay: @dataclass(frozen=True, kw_only=True)
  config: ProjectConfig
  applied: list[AppliedAmendment]
  @property summary_lines -> list[str]:
      [] when applied is empty
      else [f"config amendments: {len(applied)} applied"] +
           [f"- {a.tool} {a.intent} {a.path}" for a in applied]   # intent: set|forced

AppliedAmendment / ToolAmendment: @dataclass(frozen=True, kw_only=True) — pure data
```

`summary_lines` composes from `applied` only — `AppliedAmendment` has NO value field,
so no configuration value can leak into a line by construction. Empty `applied` →
`[]` → the caller prints nothing. The format is pinned (tests assert the exact
strings): header `config amendments: N applied`, line `- <tool> <set|forced> <path>`.

The configuration type tree — a hand-written module-level descriptor in `overlay.py`,
mirroring the model fields (a unit test cross-checks it against
`dataclasses.fields(...)` of every model so drift is detectable):

```
ProjectConfig:
  language      scalar str                      (required — always authored)
  image         scalar str   (None-able)
  dockerfile    scalar str   (None-able)
  build         section BuildConfig             (None-able)
  pipeline      section PipelineConfig          (None-able)
  commands      free-form mapping               (commands.<any> — no node type check)
  codemanifest  section CodemanifestConfig      (None-able)
  tools         mapping str -> str              (tools.<name>)
  usages        mapping group -> mapping dep -> section DepConfig
  lint          section LintConfig              (None-able)
  topics        section TopicsConfig            (None-able)

BuildConfig:     agent str | env map | max_iterations int | session_timeout str |
                 idle_timeout str | wait str | prompts_dir str | agents_dir str |
                 proxy str | hosts map (build.hosts.<host>) | review section
ReviewConfig:    skip bool | agent str | env map (build.review.env.<key>) |
                 roles list[str] (wholesale) | base_ref str | strategy str |
                 finalize str | additional section |
                 session_timeout str | idle_timeout str | wait str
AdditionalReviewConfig: agent str | patience int | max_iterations int
PipelineConfig:  agent str | env map (pipeline.env.<key>) | proxy str |
                 hosts map (pipeline.hosts.<host>)
CodemanifestConfig: usages map (codemanifest.usages.<name>) | annotations str
DepConfig (usages.<group>.<dep>): git str (REQUIRED — materialization constraint) |
                 ref str | root str
LintConfig:      ignore list[str] (wholesale)
TopicsConfig:    base_ref str | publish_commit str
```

**Usages relevant to this task:**
- `convention`: `kw_only` frozen dataclasses for pure data, Google docstrings,
  relative imports (`..project` for the nine model names — all nine importable
  there after the Task 2 facade completion).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/config/hooks/test_overlay.py` — assert
  `ToolAmendment`, `AppliedAmendment`, and `ConfigOverlay` are importable from
  `goga.config.hooks.overlay` (`merge_config_amendments` is asserted in Task 5,
  which implements it); `ConfigOverlay` is frozen `kw_only`;
  `summary_lines` is a property returning `list[str]`; `AppliedAmendment` has exactly
  the fields `tool`, `path`, `intent` and NO value field (expected to fail at this
  stage)
- [x] **Code**: create `goga/config/hooks/overlay.py` with `ToolAmendment`,
  `AppliedAmendment`, `ConfigOverlay` (+ the `summary_lines` property), and the
  module-level descriptor table exactly as the block above (node kinds: scalar
  str/int/bool, list leaf, mapping entry, section, free-form)
- [x] **Interface verification**: `python -m pytest tests/config/hooks/test_overlay.py -x` — the shape tests pass
- [x] **Logic tests**:
  (a) `summary_lines` format: empty `applied` → `[]`; two applied records →
  `["config amendments: 2 applied", "- harden set build.agent",
  "- guard forced topics.base_ref"]` (exact strings);
  (b) `test_descriptor_table_matches_model_fields` — import the descriptor table and
  the nine models (`ProjectConfig`, `BuildConfig`, `ReviewConfig`,
  `AdditionalReviewConfig`, `PipelineConfig`, `CodemanifestConfig`, `DepConfig`,
  `LintConfig`, `TopicsConfig`; no filesystem, no registry); for each model compare
  the field-name set of the dataclass with the field-name set the table records, in
  both directions (`{f.name for f in fields(ProjectConfig)} ==
  set(table["ProjectConfig"].fields)` … one line per model, all nine), assert
  `set(table) ==` the nine model names, and check the node kind of every classified
  field (scalar / list / mapping / section / free-form) against the table's entry;
  (c) no-value-leak: `AppliedAmendment` accepts no `value` kwarg (`TypeError`)
- [x] **Debugging**: `python -m pytest tests/config/hooks/ -x` — fix implementation
  code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: entities live at `location: overlay.py`;
  `summary_lines` contract clause "No configuration value ever appears in a line"
  holds by construction
- [x] **Lint**: `ruff check goga/config/hooks/` — fix formatting if necessary

### Task 5: `merge_config_amendments` — the deterministic merge (TDD coding)

**Cell**: `goga/config/hooks`. The core algorithm of the zone in
`goga/config/hooks/overlay.py` (same `location` as Task 4). Verbatim design
(Algorithm — merge_config_amendments):

```
1. VALIDATE — for every contribution, for every PathAmendment (buffer order):
   resolve path against the tree:
   - resolve each segment; a segment that names no field / no admitted mapping key,
     or continues below a leaf                                     -> FAILURE (unknown path)
   - the final segment resolves to a section or a whole mapping    -> FAILURE (non-leaf)
   - the node kind vs the value:
       str node    : isinstance(value, str)
       int node    : isinstance(value, int) and not isinstance(value, bool)
       bool node   : isinstance(value, bool)
       list node   : isinstance(value, list) and all elements str
       map entry   : isinstance(value, str)
       free-form   : no check (commands.<any>)
     mismatch                                                      -> FAILURE (wrong type)
   DepConfig scalar leaves additionally carry the loader's own structural
   rules (design decision, within "a structurally valid configuration"):
       usages.<g>.<d>.git  : isinstance(value, str) and value.strip() != ""
       usages.<g>.<d>.ref  : isinstance(value, str) and value.strip() != ""
       usages.<g>.<d>.root : the loader's path-safety rule — no leading "/",
                             no UNC anchor, no ".." segment; a blank value is
                             NOT an error (it composes as None)
     violation                                                     -> FAILURE (wrong type)
   FAILURE = ValueError(f"tool {tool}: amendment at {path!r} {detail}")
   raised before anything applies — no partial application.
2. RESOLVE — collect candidates per path (each carries (contribution_idx, buffer_idx)):
   a. authored silence (against `base` only):
        scalar leaf: value is None
        list leaf:   value is None or []
        mapping entry: container None/{}/empty OR key absent
        leaf under a None section: silent
        (False, "", a present entry value: authored — NOT silent)
   b. drop every `set` candidate on a non-silent path — silently, no record
   c. per remaining path: winner = the LAST `force` candidate if any force exists,
      otherwise the LAST `set` candidate
3. COMPOSE — for each winner in applied order, apply to a working copy of `base`:
   - walk root -> leaf; where an intermediate is None or a mapping lacks the key,
     materialize: the section default instance (see the table of defaults) or a
     fresh dict for mappings
   - replace list-valued leaves wholesale — storing a fresh list copy
     (list(value)), never an alias of the contribution's list (free-form
     list values under commands copy the same way)
   - set mapping entries; assign scalars
   - reconstruct affected frozen instances bottom-up (dataclasses.replace / cls(**f));
     unmodified sections pass by reference; modified mappings are fresh dicts
   - a blank usages.<group>.<dep>.root value composes as None (the field never
     stores "", mirroring the loader's _parse_depcfg_root normalization)
   - FINAL PASS after every winner is applied — order-independent, evaluated
     once over the finished composition: every DepConfig materialized during
     the composition whose git is still None
     -> ValueError(f"tool {tool}: amendment at {path!r} materializes "
                   f"usages.{group}.{dep} without its required git")
        (tool = the first applied amendment under that dep branch)
4. COLLECT — AppliedAmendment(tool, path, "set"|"forced") per applied path,
   ordered by the winner's (contribution_idx, buffer_idx)
5. RETURN — ConfigOverlay(config=effective, applied=[...])
   Empty contributions -> ConfigOverlay(config=base, applied=[])  # passthrough,
                                                             the passed object itself
```

Materialization default instances (all models are `kw_only` with defaults):
`BuildConfig()`, `ReviewConfig()`, `AdditionalReviewConfig()`, `PipelineConfig()`,
`CodemanifestConfig()`, `TopicsConfig(base_ref=None, publish_commit=None)`,
`LintConfig(ignore=[])`, `DepConfig(git=None, ref=None, root=None)`, fresh `dict`s
for mappings. Errors: `ValueError` (structural) — the delivery wraps it with the
action name (Task 6) → the command's `ClickException` → exit 1, nothing applied.
Edge cases (design, verbatim): no contributions → passthrough (byte-identical
object); two tools on one path — `force` (any position) beats `set`, later beats
earlier within equal intent; one tool on one path twice — the buffer kept only the
later entry; authored `""` scalar / `False` bool / non-empty mapping value →
non-silent; `commands.<any-key>` accepts any buffer value without a node check;
same branch materialized by several amendments → idempotent (defaults constructed
once per walk); an amended `usages.<g>.<d>.git`/`.ref` of `""` or an unsafe `root`
(`"../.."`, absolute) → structural failure, a blank `root` composes as `None`; list
values land as fresh copies (`list(value)`), never aliases.

Purity: `base`, the contributions, and their collections are never mutated;
unmodified sections pass by reference (the repo shallow-copy convention, as in
`merge_workflow_overlay`); same base + same contributions → the same overlay.

**Usages relevant to this task:**
- `convention`: Google docstring with the full Algorithm in the module/method
  docstring; `dataclasses.replace` for frozen reconstruction; no filesystem access.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: in `tests/config/hooks/test_overlay.py` —
  `merge_config_amendments` importable from `goga.config.hooks.overlay`; signature
  check (`merge_config_amendments(base, contributions)` returns a `ConfigOverlay` of
  the zone module); the passthrough branch: empty contributions →
  `overlay.config is base` (the passed object itself — zero rebuild),
  `overlay.applied == []`, `overlay.summary_lines == []` (expected to fail at this
  stage)
- [x] **Code**: implement `merge_config_amendments` in `goga/config/hooks/overlay.py`
  — validate → resolve → compose (with the final-pass postcheck) → collect → return,
  against the Task 4 descriptor table; internal helpers may be extracted into the
  module (validate / resolve / compose stages) if this improves clarity
- [x] **Interface verification**: `python -m pytest tests/config/hooks/test_overlay.py -x` — all pass
- [x] **Logic tests** (the design's verified scenarios, in `tests/config/hooks/test_overlay.py`):
  - `test_set_applies_on_silent_path` — base `ProjectConfig(language="python",
    image=None, dockerfile=None, build=None, pipeline=None, commands={})`;
    harden sets `build.agent="claude`"; assert `overlay.config.build.agent ==
    "claude"`, `overlay.applied == [AppliedAmendment(tool="harden",
    path="build.agent", intent="set")]`, `overlay.summary_lines ==
    ["config amendments: 1 applied", "- harden set build.agent"]`, and
    `base.build is None` (purity)
  - `test_force_overwrites_authored_and_beats_set_cross_order` — base
    `topics=TopicsConfig(base_ref="origin/dev", publish_commit=None)`; polite sets
    `topics.base_ref="origin/main"` (non-silent — dropped), guard forces
    `"origin/stable"`; assert `overlay.config.topics.base_ref == "origin/stable"`,
    applied == `[("guard", "topics.base_ref", "forced")]`, `"polite"` in no summary
    line
  - `test_later_tool_wins_equal_intent` — build=None; tool a then tool b set
    `pipeline.env.LOG_LEVEL`; assert `overlay.config.pipeline.env ==
    {"LOG_LEVEL": "DEBUG"}` and applied == `[("b", "set")]`
  - `test_unknown_path_is_structural_failure` —
    `pytest.raises(ValueError, match="tool harden: amendment at
    'build.nonexistent'")`; `base` unchanged field-by-field
    (`dataclasses.astuple` / field-by-field compare)
  - `test_non_leaf_address_and_wrong_type_fail` — (a) `build.env` with a dict value
    → match "non-leaf"; (b) `build.max_iterations` with `True` → the bool-at-int
    gate; (c) `build.agent.deep` → continues below a str leaf; (d)
    `commands.run.cmd` → below a free-form entry; each `pytest.raises(ValueError)`
    with the pinned wording ("unknown path"/"wrong type"/"non-leaf")
  - `test_materialized_dep_without_git_fails` — base usages=None; tool sets
    `usages.docs.scriba.ref="v2"` (no git anywhere) → `pytest.raises(ValueError)`
    matching `"usages.docs.scriba"` and `"required git"`; companion positive — BOTH
    `usages.docs.scriba.git` and `.ref` set, in either buffer order → the dep
    materializes fully and applies (the postcheck is a final pass; order within the
    run never matters)
  - `test_depcfg_value_rules_match_the_loader` — authored dep `usages.docs.scriba`
    (git set); (a) `force git=""` → ValueError naming tool + path; (b)
    `force ref=""` → same; (c) `force root="../.."` → same; (d) `force root=""`
    alongside `set ref="v2"` on one merge → clean: `root is None` and `ref == "v2"`
  - `test_purity_and_determinism` — one base + one contributions list, merged
    twice: `o1.applied == o2.applied`, `o1.config == o2.config`, base field-by-field
    unchanged, and an unmodified branch passes by reference
    (`o1.config.codemanifest is base.codemanifest`)
  - `test_set_on_authored_empty_containers_applies` — base
    `lint=LintConfig(ignore=[])`, `build=BuildConfig(env={}, ...)`: set
    `lint.ignore=["x/"]`, set `build.env.KEY="v"`, set `commands.report="on"` → all
    apply; counterpart: authored `review.skip=False` + set → dropped, authored
    `image=""` + set → dropped (False/"" are authored, not silence markers)
- [x] **Debugging**: `python -m pytest tests/config/hooks/ -x` — fix implementation
  code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: deterministic + pure (inputs unmutated); the
  commands mapping is free-form; the result is structurally valid; no filesystem
  read/write; no semantic validation; `base`, contributions, and their collections
  never mutated
- [x] **Code**: add ONE bullet to the path-vocabulary list of
  `goga/config/.usages/registering-hooks.md` (the design's verbatim wording):
  "Materializing an absent `usages.<group>.<dep>` branch requires the amendments
  to supply its `git` too — a materialized dep without `git` is the same hard
  structural failure. Amended `git`/`ref` values must be non-empty strings and
  `root` a safe relative subpath (no `..`, no absolute) — blank `git`/`ref` and
  unsafe `root` values are structural failures; a blank `root` means no root."
- [x] **Lint**: `ruff check goga/config/hooks/` — fix formatting if necessary

### Task 6: `events.py` — `ConfigHooks`, the checkpoint delivery (TDD coding)

**Cell**: `goga/config/hooks`. The checkpoint surface over the platform facade —
the staged per-tool delivery of the hard `config / amend_config` action. Verbatim
design (Algorithm — ConfigHooks):

```
class ConfigHooks:
  __init__: self._registry = None                      # cheap — nothing enumerated
  _ensure_registry() -> HookRegistry:                  # built once per run
      registry = HookRegistry(); registry.build_once(); cache on self

  amend_config(config: ProjectConfig) -> ConfigOverlay:
    1. registry = self._ensure_registry()
    2. record = declared_actions() entry domain="config", name="amend_config"
       None -> ValueError("unknown hook action: config.amend_config")
    3. groups = {} ; for sub in registry.subscriptions_for("config", "amend_config"):
           groups.setdefault(sub.tool, []).append(sub)
    4. contributions = []
       for tool, subs in groups.items():               # enumeration order
           amendment = ConfigAmendment(config=config)  # fresh view + buffer per tool
           proxy = wrap_context(amendment)
           for sub in subs:
               try: sub.hook(**build_hook_arguments(sub.hook, proxy,
                                                    registry.self_context(tool)))
               except Exception as reason:
                   raise ValueError(f"hook {sub.name} of tool {tool} "
                                    f"failed on config.amend_config: {reason}") from reason
           if amendment._amendments:
               contributions.append(ToolAmendment(
                   tool=tool, amendments=list(amendment._amendments.values())))
           # empty buffer -> commits nothing, silent
    5. try: return merge_config_amendments(config, contributions)
       except ValueError as reason:
           raise ValueError(f"amendment rejected on config.amend_config: "
                            f"{reason}") from reason
    6. return the overlay                              # never prints
```

The message formats are pinned (tests assert them): the hook-failure line copies the
pipeline precedent (`goga/pipeline/hooks/events.py`) verbatim; the merge wrapper adds
the action. Errors: `ImportError` (a broken tool package) — the single fatal case,
raised by `build_once`, names the package, outside the action's error class;
`ValueError` (hard failure) — names the hook/tool + action, or the tool +
malformedness + action. Edge cases: no subscriptions → empty `groups` → empty
`contributions` → the passthrough overlay ("the delivery is unobservable"); a tool
with several hooks commits only after every hook of the tool returned (commit
granularity = the tool); a tool whose every hook is a no-op commits nothing — no
warning. The platform derives the tool identity from the package name
(`goga_tool_hardener` → `hardener` — prefix dropped, underscores to hyphens,
`ToolPackage.tool`). The zone never prints, never logs on the happy path.

Imports (relative, per `convention`): `from ...hooks import (HookRegistry,
build_hook_arguments, declared_actions, wrap_context)` — the platform facade, never
deep platform modules; `from .amendments import ConfigAmendment`; `from .overlay
import ConfigOverlay, ToolAmendment, merge_config_amendments`.

Test infrastructure (this task): `tests/config/hooks/conftest.py` re-exports
`pin_package_environment` and `install_tool_package` from `tests/hooks/conftest.py`
— the platform code under test runs for real; only `packages_distributions` and the
`sys.modules` entry of a fake `goga_tool_*` package are pinned. Fake tools subscribe
via `install_tool_package("goga_tool_harden", lambda hooks: hooks.subscribe("config",
"amend_config", "hardening", harden))`.

**Usages relevant to this task:**
- `per-tool-delivery` (from `goga/hooks`): the staged delivery loop skeleton applies
  as written — group-per-tool, fresh view per tool, commit-after-success; the
  deviation from its soft example is the action's hard error class from the catalog
  record (exactly the practice's "treat a failure per the action's error class" rule).
- `registering-hooks` (from `goga/hooks`): the hook signature contract
  (`context`/`self` offered names) behind `build_hook_arguments`.
- `convention`: relative imports, Google docstrings, `logger = logging.getLogger(
  __name__)` only if logging appears (the zone logs nothing on the happy path).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/config/hooks/test_events.py` —
  `ConfigHooks` importable from `goga.config.hooks.events`; construction is cheap
  and enumerates nothing (assert the `packages_distributions` boundary mock is NOT
  called at construction); `amend_config` exists with the declared signature
  (expected to fail at this stage)
- [x] **Code**: create `goga/config/hooks/events.py` implementing `ConfigHooks`
  exactly as the block above
- [x] **Interface verification**: `python -m pytest tests/config/hooks/test_events.py -x` — all pass
- [ ] **Logic tests** (the design's verified scenarios, in `tests/config/hooks/test_events.py`
  — all over the real platform via the conftest fixtures):
  - `test_config_hooks_passthrough_without_subscriptions` —
    `pin_package_environment({})`; `authored` built by the real loader from a real
    `.goga/config.yml` in `tmp_path` (+ `os.chdir`); assert `overlay.config is
    authored` (the passed object itself), `overlay.applied == []`,
    `overlay.summary_lines == []`
  - `test_subscribed_tool_with_empty_buffer_commits_nothing` —
    `pin_package_environment({"goga_tool_silent": ["silent-dist"]})` +
    `install_tool_package("goga_tool_silent", register)` where register subscribes
    `observe(context)` that reads `context.config.image` and buffers nothing; assert
    `overlay.config is authored`, `overlay.applied == []`, `overlay.summary_lines ==
    []` (silent continue — no warning, no empty `ToolAmendment`)
  - `test_per_tool_delivery_commits_buffered_amendments` —
    `pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})`;
    `harden(context)` reads `context.config.build` (mutual-blindness read) and calls
    `context.set("build.agent", "claude")` + `context.force("lint.ignore", ["a/",
    "b/"])`; authored base with `build=None`, `lint=None`; assert
    `overlay.config.build.agent == "claude"`, `overlay.config.lint.ignore ==
    ["a/", "b/"]`, and `[(a.tool, a.path, a.intent) for a in overlay.applied] ==
    [("hardener", "build.agent", "set"), ("hardener", "lint.ignore", "forced")]`
    (the platform derives `goga_tool_hardener` → `hardener`)
  - `test_raising_hook_stops_command_names_tool_and_action` — fake tool whose hook
    raises `RuntimeError("boom")`; a SECOND subscribed tool after it in enumeration
    order; `pytest.raises(ValueError, match=r"hook \w+ of tool \w+ failed on
    config\.amend_config: boom")`; `second_tool_hook.called is False` (first-failure
    stop, nothing committed, nothing merged)
  - `test_within_tool_later_same_path_replaces_earlier` (delivery variant) — one
    tool whose hook calls `set("build.agent", "a")` then `force("build.agent", "b")`;
    assert `overlay.config.build.agent == "b"` and `applied ==
    [AppliedAmendment(tool, "build.agent", "forced")]`
  - merge-wrap format: a structurally malformed contribution (unknown path) →
    `pytest.raises(ValueError, match="amendment rejected on config.amend_config:
    tool ...")` — the wrapper adds the action to the merge's own message (which
    already names tool + path), no duplication
- [x] **Debugging**: `python -m pytest tests/config/hooks/ -x` — fix implementation
  code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: cheap construction; one registry per run; commit
  granularity is the tool; passthrough on no subscriptions; no repository/git/filesystem
  reads at the checkpoint; the zone never prints
- [x] **Lint**: `ruff check goga/config/hooks/` — fix formatting if necessary

### Task 7: The zone facade — `goga/config/hooks/__init__.py` (infrastructure)

**Cell**: `goga/config/hooks`. Assemble the facade: exactly the seven contract names,
re-exported from `amendments`, `overlay`, `events`, exposed through `__all__`
(Python facade rule: only identifiers listed in `__all__` constitute the cell
facade). The zone's `__init__.py` is written last within the zone (the placeholder
from Task 3 now becomes the facade).

```
__all__ = ["AppliedAmendment", "ConfigAmendment", "ConfigHooks", "ConfigOverlay",
           "PathAmendment", "ToolAmendment", "merge_config_amendments"]
```

**Usages relevant to this task:**
- `convention`: facade assembly at the package surface; alphabetical `__all__`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Replace the placeholder `goga/config/hooks/__init__.py` with the facade:
      re-export the seven names from their implementing modules, `__all__` exactly
      as above
- [ ] Create `tests/config/hooks/test_facade.py` with
      `test_facade_all_exactly_seven_names`: `import goga.config.hooks as zone`;
      assert `zone.__all__ ==` the exact seven-name list (alphabetical), each name
      importable and the implementing class/function, and `ConfigHooks()` constructs
      without enumeration (the `packages_distributions` mock not called)
- [ ] Verify facade accessibility:
      `python -c "from goga.config.hooks import AppliedAmendment, ConfigAmendment, ConfigHooks, ConfigOverlay, PathAmendment, ToolAmendment, merge_config_amendments; print('ok')"`
- [ ] Lint: `ruff check goga/config/hooks/` — fix formatting if necessary

### Task 8: The common-shape consumers — pipeline, contract, install, config, build (TDD coding)

**Cells**: `goga/commands/{pipeline,contract,install,config,build}`. Five surfaces
whose load try already wraps `ValueError` — the delivery sits INSIDE the existing
try. The common shape (verbatim from the design):

```python
from ...config.hooks import ConfigHooks            # relative import per `convention`

try:
    authored = load_project_config()
    overlay = ConfigHooks().amend_config(config=authored)      # inside the try:
except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
    raise click.ClickException(str(exc)) from exc              # hard failure -> clean

for line in overlay.summary_lines:                              # nothing when empty
    click.echo(line, err=True)

config = overlay.config           # every downstream read is unchanged code on the
                                  # effective configuration
```

Per-surface specifics (each verified against the current source in the design):

1. **pipeline** (`goga/commands/pipeline/pipeline.py:151-153`) — the load try gains
   the delivery; after the try: summary to stderr, then `config = overlay.config`;
   the `config.pipeline is None` guard and every downstream read address the
   effective configuration unchanged.
2. **contract** (`goga/commands/contract/contract.py:157-162`) — the delivery joins
   the load inside the existing try; step 2 resolves
   `lang = lang if lang is not None else overlay.config.language`.
3. **install** (`goga/commands/install/install.py:305-314`) — ONLY the bulk path's
   load try gains the delivery; `tools = overlay.config.tools if ... is not None
   else {}`. The single and local paths are untouched (no load, no checkpoint).
4. **config** (`goga/commands/config/config.py:117-130`) — the delivery joins the
   existing try; `_resolve_option(overlay.config, option)`; stdout stays the
   data-clean value surface (headers + effective values only; the summary goes to
   stderr); exit codes unchanged. (`_ALIAS_MAP` was already deleted in Task 2.)
5. **build** (`goga/commands/build/build.py:301-304`) — the delivery joins the load
   try (step 2, after the docker check); the home configuration load stays
   authored-only (closed surface); `config = overlay.config` before the
   `config.build is None` guard and the agent guard; every downstream field access
   is unchanged code reading the effective object.

stderr only: stdout of every command is unchanged.

**Usages relevant to this task:**
- `checkpoints` (from `goga/config/hooks`): the consumer-side delivery shape this
  task implements — authored load → `amend_config(config=...)` → print
  `summary_lines` to stderr → consume `overlay.config`.
- `click`: `click.echo(line, err=True)` per summary line; the existing
  `ClickException` wrappers carry the hard failure.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: for each of the five commands, a test asserting the
  checkpoint is delivered after a successful load (fake tool forcing one observable
  knob; the command behaves per the EFFECTIVE value) and that the summary line is
  on stderr while stdout is unchanged vs the no-tools run (expected to fail at this
  stage) — suites: `tests/commands/pipeline/`, `tests/commands/test_contract.py`,
  `tests/commands/install/`, `tests/commands/test_config.py`,
  `tests/commands/build/`
- [ ] **Code**: apply the common shape + per-surface specifics 1–5 above in the five
  command modules
- [ ] **Interface verification**: `python -m pytest tests/commands/ -x` — all pass
- [ ] **Logic tests** (the design's verified scenarios):
  - `tests/commands/test_config.py::test_config_language_direct_and_effective_values` —
    real `.goga/config.yml` in `tmp_path` (`language: python`, `build: {agent:
    codex}`); a fake tool forcing `build.agent` to `claude`; `CliRunner`:
    `runner.invoke(config_cmd, ["language"])` → `result.exit_code == 0`,
    `result.output == "# language\npython\n"` (stdout data-clean);
    `["build.agent"]` → `"# build.agent\nclaude\n"` (effective value); the summary
    line `- hardener forced build.agent` appears in stderr, not stdout
  - `tests/commands/test_contract.py::test_contract_resolves_language_from_effective_config` —
    real config (`language: python`); a fake tool forcing `language` to `golang`;
    spy on `goga.contract.dispatcher.contract` (mock.patch at the import point);
    `--lang` absent → `spy.call_args.args[0] == "golang"` (effective; the call site
    passes `lang` positionally); with `--lang swift` → `spy.call_args.args[0] ==
    "swift"` (CLI wins)
  - the uniform-reach switch tests (one per remaining surface, same skeleton): a
    fake tool forces one observable knob (`pipeline.env.KEY` for pipeline,
    `tools.viewer` for install bulk, `build.agent`/a build knob for build); assert
    (a) the command behaves per the effective value, (b) the summary line is on
    stderr, (c) stdout unchanged vs the no-tools run, (d) exit codes unchanged
  - hard failure per command: a fake tool whose hook raises →
    `runner.invoke(...)` → `exit_code == 1`, `"failed on config.amend_config"` in
    output, no traceback
- [ ] **Debugging**: `python -m pytest tests/commands/ -x` — fix implementation
  code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the delivery sits inside the load try in all
  five; stdout unchanged; `goga config` stdout carries only headers + effective
  values; install single/local paths untouched; build home load untouched
- [ ] **Lint**: `ruff check goga/commands/pipeline/ goga/commands/contract/ goga/commands/install/ goga/commands/config/ goga/commands/build/` — fix formatting if necessary

### Task 9: The guarded consumers — lint, topics (TDD coding)

**Cells**: `goga/commands/{lint,topics}`. The two surfaces whose delivery is
conditional or must escape a swallowing wrapper.

**lint** (`goga/commands/lint/lint.py:24-30`) — two-step, because the existing
except swallows `ValueError` into `ignore=None` (config optional for lint): the
loader try keeps its swallow semantics; on SUCCESS the delivery runs OUTSIDE that
try in its own

```python
try: ... except ValueError as exc: raise click.ClickException(str(exc)) from exc
```

— a hard checkpoint failure must stop lint with a clean error, never be treated as
"config absent", never a raw traceback. Then the summary prints to stderr and
`ignore` derives from `overlay.config.lint` (`None` section → `ignore=None`).
A failed/absent load: `ignore = None`, no checkpoint (nothing was loaded).

**topics** (`goga/commands/topics/topics.py:48-61`) — inside `_topics_section()`:
the delivery runs after a successful load (its `ValueError` joins the existing
`(KeyError, ValueError, yaml.YAMLError)` → `ClickException` wrapper); the summary
prints there; `return overlay.config.topics`. `FileNotFoundError` → `None` (unset,
no checkpoint — nothing was loaded). The load happens only when
`base_ref is None or commit_message is None` (the create step's existing guard) —
with both flags given, no load and no checkpoint, exactly as the contract's
"read only for values no flag provided".

**Usages relevant to this task:**
- `checkpoints` (from `goga/config/hooks`): the delivery shape; the absent-config
  rule (lint) and the read-only-when-flagged rule (topics).
- `click`: stderr summary echo; `ClickException` wrappers.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: lint — the effective `ignore` derives from the checkpoint
  (`overlay.config.lint`); topics — `_topics_section()` returns the effective
  topics section (expected to fail at this stage) — suites `tests/commands/test_lint.py`,
  `tests/commands/topics/` (or the topics suite's current home)
- [ ] **Code**: apply the lint two-step and the topics `_topics_section` switch as
  specified above
- [ ] **Interface verification**: `python -m pytest tests/commands/test_lint.py tests/commands/ -x -k "lint or topics"` — all pass
- [ ] **Logic tests** (the design's verified scenarios):
  - `test_lint_checkpoint_failure_is_clean_error` — fake tool RAISES inside its
    hook → `runner.invoke(lint_cmd, ["."])` → `exit_code == 1`,
    `"failed on config.amend_config"` in output, no traceback, and lint does NOT
    run unfiltered (the delivery is outside the swallow)
  - lint absent config — no `.goga/config.yml` → lint runs unfiltered, no registry
    assembly (assert the `packages_distributions` mock not called), no stderr
    output
  - lint effective ignore — fake tool forces `lint.ignore=["x/"]` on a config
    without a lint section → lint filters per the effective value; the summary
    line is on stderr
  - topics effective base — fake tool forces `topics.base_ref` → the create step
    resolves the amended base; with both flags given (`--base-ref` and
    `--commit-message` as applicable) no load and no checkpoint occurs
- [ ] **Debugging**: `python -m pytest tests/commands/ -x` — fix implementation
  code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the loader swallow semantics unchanged (a
  present-but-invalid config still runs lint unfiltered); the checkpoint failure
  path is a clean error, never `ignore=None`; topics `FileNotFoundError` → `None`
  with no checkpoint
- [ ] **Lint**: `ruff check goga/commands/lint/ goga/commands/topics/` — fix formatting if necessary

### Task 10: The plain-module consumers — usages status, usages sync (TDD coding)

**Cells**: `goga/usages/{status,sync}`. Plain modules (no try around the load —
they fail loud by contract). After the fail-loud load: deliver, print the summary
via `click.echo(line, err=True)` (the NEW `import click` per the `click` practice
each module gains), then use `overlay.config` (`status` iterates
`overlay.config.usages`; `sync` reads `overlay.config.usages` and proceeds
unchanged). A checkpoint `ValueError` propagates — the `goga usages` command's
existing wrapper converts it to `ClickException`. The report rendering itself
stays where it is (status/sync do not print the report — only the summary lines
print to stderr).

Relative import depth: `from ...config.hooks import ConfigHooks` (both modules sit
three levels below `goga`, the same depth today's `from ...config import ...` in
status.py already uses).

**Usages relevant to this task:**
- `checkpoints` (from `goga/config/hooks`): the delivery shape; the summary-to-stderr
  rule.
- `click` (newly connected in both cells' CODEMANIFESTs): `import click`,
  `click.echo(line, err=True)`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: both modules deliver the checkpoint and iterate the
  effective `usages` section; the summary lines go to stderr (expected to fail at
  this stage) — suites `tests/usages/status/`, `tests/usages/sync/`
- [ ] **Code**: apply the switch in `goga/usages/status/status.py` (after the
  load at line 62) and `goga/usages/sync/sync.py` (after the load at line 43) —
  `import click` added to both
- [ ] **Interface verification**: `python -m pytest tests/usages/ -x` — all pass
- [ ] **Logic tests**: the uniform-reach skeleton per surface — fake tool forces
  `usages.<g>.<d>.ref` (or amends the dep set): (a) status/sync behave per the
  effective usages section, (b) the summary line is on stderr, (c) stdout unchanged
  vs the no-tools run, (d) exit codes unchanged; hard failure — a raising hook →
  `runner.invoke(usages_cmd, ["status"])` → `exit_code == 1`,
  `"failed on config.amend_config"` in output (the `goga usages` wrapper converts
  the propagated `ValueError`), no traceback
- [ ] **Debugging**: `python -m pytest tests/usages/ -x` — fix implementation code
  until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the modules keep their fail-loud load contract
  (`FileNotFoundError` etc. propagate); only the summary prints (stderr); report
  rendering stays with the command
- [ ] **Lint**: `ruff check goga/usages/` — fix formatting if necessary

### Task 11: Integration tests — passthrough, secrecy, and the final verification sweep (integration tests)

**Scope**: cross-entity, end-to-end over the real platform — the nine surfaces
against a real project tree, with and without a forcing tool. This task also runs
the plan's verification checklist verbatim (the design's *Additional Instructions*).

**Usages relevant to this task:**
- `checkpoints` (from `goga/config/hooks`): the in-container authored-only rule —
  asserted here negatively (no checkpoint wiring exists in `goga/build/__main__`).
- `click`: `CliRunner` invocation and stderr capture.
- `convention`: test structure mirrors `tests/<package>/...`; fixtures re-exported
  from `tests/hooks/conftest.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/integration/test_config_hooks_passthrough.py` — a real project
      tree in `tmp_path` (config + one CODEMANIFEST cell); the nine commands invoked
      via `CliRunner` twice — with no tool packages and with a forcing tool installed
      (e.g. `lint`, `config <path>`, `install` bulk, `usages status`, …)
- [ ] Test passthrough: no-tool run — stdout byte-identical to the pre-change
      baseline snapshot; stderr empty; exit codes identical
- [ ] Test the effective run: with-tool run — stdout unchanged vs the no-tool run
      (except where the effective value IS the output — `goga config` prints the
      amended value); stderr carries exactly the summary lines;
      `.goga/config.yml` byte-identical after the run (the authored file is never
      modified); no configuration value appears on any stderr/stdout surface beyond
      the data surfaces that already print values
- [ ] Run the verification checklist verbatim:
      `goga lint` (80 cells, 0 errors);
      the facade one-liner
      `python -c "from goga.config.hooks import AppliedAmendment, ConfigAmendment, ConfigHooks, ConfigOverlay, PathAmendment, ToolAmendment, merge_config_amendments; print('ok')"`;
      the absence sweep (`grep -rn "\.lang\b\|lang=" goga/` → only the CLI
      `--lang`/dispatcher surface remains);
      the catalog check (`Action(domain="config", name="amend_config",
      error_class="hard") in declared_actions()`);
      `goga schema` (the zone with exactly its planned dependencies);
      `python -m pytest tests/ -x`;
      `ruff check goga/config/hooks/ goga/config/project/ goga/hooks/catalog/ goga/commands/ goga/usages/`;
      the merge-algebra / summary-format / uniform-reach checks (the suites of
      Tasks 5–10 green)
- [ ] Run validation: `python -m pytest tests/integration/test_config_hooks_passthrough.py -x` — all pass

---

## Validation Commands

- `goga lint`: cell/contract lint over all cells (0 errors expected)
- `goga schema`: the dependency graph — the zone imports exactly `goga/hooks` and `goga/config/project`, no cycles
- `python -c "from goga.config.hooks import AppliedAmendment, ConfigAmendment, ConfigHooks, ConfigOverlay, PathAmendment, ToolAmendment, merge_config_amendments; print('ok')"`: facade accessibility — all seven contract names importable
- `python -c "from goga.hooks import declared_actions; assert any(a.domain == 'config' and a.name == 'amend_config' and a.error_class == 'hard' for a in declared_actions()); print('ok')"`: the catalog record
- `grep -rn "\.lang\b\|lang=" goga/ | grep -v "dispatcher\|--lang"`: absence sweep — no model-field `lang` reference survives (the CLI `--lang` surface and test YAML-writing helpers excepted)
- `python -m pytest tests/ -x`: run all tests
- `ruff check goga/config/hooks/ goga/config/project/ goga/hooks/catalog/ goga/commands/ goga/usages/`: lint check over every touched package
- `git diff --stat -- .goga/config.yml` (inside the integration test tree): the authored file is never modified (asserted byte-identical in Task 11)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
      (`amendments.py`, `overlay.py`, `events.py`; the catalog record in
      `catalog.py`; the rename in `config.py`/`loader.py`)
- [ ] Every contract entity is accessible from the facade
      (`goga.config.hooks` `__all__` = exactly the seven names)
- [ ] Properties and methods match the declared API
      (`set`/`force`, `config`/`applied`/`summary_lines`, `amend_config`)
- [ ] Descriptions are reflected in behavior (merge algebra, hard-failure formats,
      passthrough, summary format, materialization postcheck, DepConfig rules)
- [ ] Contract dependencies are met (the zone imports only `goga/hooks` +
      `goga/config/project`; consumers import `ConfigHooks` from
      `...config.hooks`)
- [x] The rename is complete and shim-free (`lang` gone from the model; `goga config
      lang` → "Option not found"; CLI `--lang` unchanged)
- [ ] Every coding task followed the TDD workflow (contract tests → code →
      verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each
      coding task
- [ ] Integration tests exist (`tests/integration/test_config_hooks_passthrough.py`)
      and pass
- [ ] No package boundary was expanded (no new cells; `goga/config/__init__.py`
      NOT extended; the `goga/config/project` facade completed to its own already
      contracted names — `DepConfig`, `LintConfig` in `__all__`, Task 2;
      in-container loads stay authored-only)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] The `registering-hooks.md` materialization bullet was applied (Task 5)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (`convention` — all
      tasks; `click` — Tasks 8–10; `yaml` — unchanged loader context, Task 2;
      `per-tool-delivery`, `registering-hooks` — Tasks 3, 6; `checkpoints` —
      Tasks 8–11)
