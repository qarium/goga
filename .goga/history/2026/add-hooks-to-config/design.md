# Design Document: `add-hooks-to-config`

<!-- Topic: `.goga/history/2026/add-hooks-to-config/` — open the config domain to tool
hooks via an in-memory amendment checkpoint, rename the model field `lang` -> `language`,
and switch the nine host-side config-consuming surfaces. -->

## Contract Changes

The contracts were materialized by the apply-architecture stage and validated there
(`goga lint`: 80 cells, 0 errors; `goga schema`: the zone with exactly its planned
dependencies). This design stage re-validated them (Phase 3 gap analysis + four-dimension
consistency audit — see *Applied Fixes*: none were needed) and produces the code-level
specification below. No CODEMANIFEST changes were made by this stage.

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST`: `declared_actions` Requirements gain one catalog
  record — `domain="config", name="amend_config", error_class="hard"` (additive; no
  existing record touched).
- `goga/config/project/CODEMANIFEST`: `ProjectConfig` signature param `lang` -> `language`,
  the param annotation, the property `lang -> str` -> `language -> str`, and
  `load_project_config` Algorithm step 4 reworded (the `language` key is required —
  a missing key raises `KeyError`).
- `goga/usages/status/CODEMANIFEST`: import block from `goga/config/hooks`
  (`ConfigHooks`, `ConfigOverlay`, the `checkpoints` practice), the `click` practice,
  Algorithm step 1 switch, the print constraint narrowed to report rendering.
- `goga/usages/sync/CODEMANIFEST`: the same common wiring as `status`.
- `goga/commands/{pipeline,lint,contract,install,config,build,topics}/CODEMANIFEST`:
  the common import block, the common global `checkpoints` clause, the per-cell
  load-step switch (deliver → consume `overlay.config` → stderr summary), the stderr
  requirement; `contract` and `config` additionally carry the rename touch points.
- `goga/config/hooks/CODEMANIFEST` (created): the zone — 7 types
  (`ConfigAmendment`, `PathAmendment`, `ToolAmendment`, `AppliedAmendment`,
  `ConfigOverlay`, `merge_config_amendments`, `ConfigHooks`).
- `goga/config/CODEMANIFEST`: unchanged (docs-only cell) — its usage files changed
  (see *Usages and Annotations Changes*).

### New Entities

- `ConfigAmendment(config: ProjectConfig)` — `goga/config/hooks/amendments.py`. The
  read-and-amend view of one tool: the authored config read-only plus this tool's
  amendment buffer (`set` / `force`).
- `PathAmendment(path: str, intent: str, value: str | int | bool | list[str])` —
  `goga/config/hooks/amendments.py`. One buffered amendment (pure data).
- `ToolAmendment(tool: str, amendments: list[PathAmendment])` —
  `goga/config/hooks/overlay.py`. One tool's committed contribution.
- `AppliedAmendment(tool: str, path: str, intent: str)` —
  `goga/config/hooks/overlay.py`. One applied (winning) amendment record — carries no
  value.
- `ConfigOverlay(config: ProjectConfig, applied: list[AppliedAmendment])` —
  `goga/config/hooks/overlay.py`. The effective configuration plus the applied
  amendments plus the composed `summary_lines`.
- `merge_config_amendments(base, contributions) -> overlay` —
  `goga/config/hooks/overlay.py`. The deterministic type-checked in-memory merge.
- `ConfigHooks()` — `goga/config/hooks/events.py`. The checkpoint surface:
  `amend_config(config) -> overlay` delivered over the platform facade.

### Changed Entities

- `ProjectConfig` (`goga/config/project/config.py`) — the field `lang: str` becomes
  `language: str`. The loader already reads the authored YAML key `language`
  (`_parse_language`); only the model field, the constructor kwarg at the loader's
  assembly (`loader.py`, `ProjectConfig(lang=lang, ...)` -> `language=language`), and
  the local variable name change.
- `declared_actions` (`goga/hooks/catalog/catalog.py`) — `_DECLARED_ACTIONS` gains the
  `config / amend_config` hard record appended after the build block.
- `goga config` (`goga/commands/config/config.py`) — `_ALIAS_MAP` (`{"language": "lang"}`)
  and the alias rewrite in `_resolve_option` are deleted; `language` resolves directly.
- `goga contract` (`goga/commands/contract/contract.py`) — `config.lang` becomes
  `config.language` (the CLI `--lang` option and the `lang` parameter of the command
  callback and of `goga/contract/dispatcher.py` stay unchanged — they are CLI surface,
  not the model field).
- The nine host-side consumers (see *Algorithm Design — Consumer Switches*).

### Deleted Entities

- The `ProjectConfig.lang` property (replaced by `language`). No other deletions; the
  `goga config` alias map is deleted as dead code, not as a contract entity.

### Usages and Annotations Changes

- `goga/config/hooks/.usages/checkpoints.md` (created) — how consumers deliver the
  checkpoint and consume the overlay.
- `goga/config/.usages/registering-hooks.md` (created) — how a `goga_tool_*` package
  subscribes to `config / amend_config`; the events table, the view members, the merge
  rules, the failure treatment, the run output.
- `goga/config/.usages/project-configuration.md` (updated) — `config.language` accessor
  examples (3 places) and the zone-entry note in the Loading Configuration chapter.
- Consumer CODEMANIFESTs: the common import block (`ConfigHooks`, `ConfigOverlay`,
  `checkpoints` from `goga/config/hooks`), the common global clause, the stderr
  requirements; `status`/`sync` additionally connect the `click` practice.

## Applied Fixes

### Fixed CODEMANIFEST Defects

None. The Phase 3 audit (signature/location/DSL syntax, interface ↔ type, type ↔
mutation — none present, interface ↔ interface, annotation ↔ reference resolution)
found no defects: `goga lint` passes with 0 errors over 80 cells, every backtick
reference resolves inside its document, the zone imports only `goga/hooks` and
`goga/config/project` with no import cycle, and the consumer wiring matches the
materialized plan byte-for-byte. One implementation-level corner the contract implies
but does not spell out — materializing a `DepConfig` branch whose required `git` no
amendment supplies — is resolved inside the existing requirements ("the result is a
structurally valid configuration" + the hard-failure semantics naming the tool and the
action) and is specified under *Algorithm Design — merge_config_amendments*; it needs
no contract edit.

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

1. **Amendment delivery** (the checkpoint): command → `load_project_config()` →
   `ProjectConfig(authored)` → `ConfigHooks().amend_config(config=...)` →
   `HookRegistry` (built once per run; enumerates `goga_tool_*` packages, runs their
   `register_hooks`) → per subscribed tool: fresh `ConfigAmendment(config=authored)`
   wrapped by `wrap_context`, hooks called via `build_hook_arguments` with the tool's
   `self` context → per-tool buffer `{path: PathAmendment}` → committed
   `ToolAmendment` list → `merge_config_amendments(authored, contributions)` →
   `ConfigOverlay` → command prints `overlay.summary_lines` to stderr and reads
   `overlay.config` downstream.
2. **The rename**: `.goga/config.yml` key `language` (unchanged authored vocabulary) →
   `_parse_language` (unchanged) → `ProjectConfig(language=...)` (renamed kwarg) →
   consumers read `config.language`; `goga config language` resolves directly; the
   alias bridge is deleted.
3. **Hard failure**: a raising hook or a structurally malformed contribution →
   `ValueError` naming the hook/tool and the action (or the tool and the
   malformedness) → the command's existing `(FileNotFoundError, KeyError, ValueError,
   yaml.YAMLError)` wrapper turns it into `click.ClickException` (clean message,
   exit 1) — in `status`/`sync` the `ValueError` propagates and the `goga usages`
   command wrapper converts it.

### Entity Dependencies

Implementation order (leaves → root, matching the plan):

1. `goga/hooks/catalog/catalog.py` — append the record (no dependencies).
2. `goga/config/project/` — the rename (`config.py` field, `loader.py` kwarg + local).
3. `goga/config/hooks/` — `amendments.py` (imports `goga/config/project` types) →
   `overlay.py` (imports `amendments.py` + `goga/config/project` types) → `events.py`
   (imports `goga/hooks` facade + `amendments.py` + `overlay.py`) → `__init__.py`
   facade (`__all__` = the 7 contract names).
4. The nine consumers — each imports `ConfigHooks` from `goga.config.hooks`
   (relative: `from ...config.hooks import ConfigHooks` in the commands and in
   `usages/status`/`usages/sync` — both sit three levels below `goga`, the same
   depth today's `from ...config import ...` in status.py already uses).
5. Tests — mirror the source structure.

No import cycles: the zone imports only `goga/hooks` and `goga/config/project`; the
facade `goga/config` is untouched by the zone; no consumer is imported by a provider.

## Code Stack Trace

Verified against the real sources: `goga/hooks/dispatch/delivery.py` (`wrap_context`,
`build_hook_arguments`), `goga/hooks/registry/state.py` (`HookRegistry.build_once`,
`subscriptions_for`, `self_context`), `goga/hooks/catalog/catalog.py`,
`goga/pipeline/hooks/events.py` (the delivery-loop precedent), the nine consumer call
sites, and `goga/build/__main__.py`.

### Trace: `ConfigHooks.amend_config(config)`

#### Chain
1. **Input**: the command calls `ConfigHooks().amend_config(config=authored)` right
   after a successful authored load. `ConfigHooks()` is cheap: `__init__` only sets
   `self._registry = None` — no enumeration, no imports (precedent:
   `PipelineHooks.__init__`).
2. **Step**: `_ensure_registry()` — `HookRegistry()` + `build_once()`; lazily once per
   surface instance; enumerates `goga_tool_*` packages and runs `register_hooks`.
   → checkpoint: platform API verified (`state.py:54-108`); a broken package import
   raises `ImportError` naming the package — the single fatal case, outside the
   action's semantics. → passes.
3. **Step**: resolve `domain="config", action="amend_config"` against
   `declared_actions()`; the record must exist after the catalog append.
   → checkpoint: the record is added in implementation step 1; an unknown address
   raises `ValueError("unknown hook action: config.amend_config")`. → passes.
4. **Step**: `registry.subscriptions_for("config", "amend_config")` grouped per tool
   in enumeration order (`dict` keyed by tool preserves insertion order).
   → checkpoint: no subscriptions → empty contributions → passthrough overlay (the
   authored object itself, empty applied, empty summary) — "the delivery is
   unobservable". → passes.
5. **Step**: per tool — fresh `ConfigAmendment(config=authored)` (fresh facts, fresh
   buffer; every tool reads the SAME authored object — mutual blindness),
   `proxy = wrap_context(amendment)` (reads/calls pass; assignment blocked),
   `sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))`
   (only declared `context`/`self` names receive values).
   → checkpoint: hook type flow verified — `context` receives the proxy,
   `ConfigAmendment.config` is a frozen `ProjectConfig` (attribute writes raise
   `FrozenInstanceError`), the buffer is written only through `set`/`force`.
   → passes.
6. **Step**: a raising hook → `ValueError(f"hook {sub.name} of tool {tool} failed on
   config.amend_config: {reason}")` (the pipeline message format); the view and its
   buffer die with the tool — the tool's whole contribution is discarded; the command
   stops at the first failure.
   → checkpoint: matches the catalog record (hard) and the zone contract steps 4.
   → passes.
7. **Step**: a tool whose every hook returned commits `ToolAmendment(tool,
   amendments=list(buffer.values()))` (buffer order); an empty buffer commits nothing
   — silent continue (unlike the pipeline zone there is no empty-content warning:
   "commits nothing" is silent by contract).
   → passes.
8. **Step**: `merge_config_amendments(config, contributions)`; a `ValueError` from the
   merge (a structural failure) is re-raised as
   `ValueError(f"amendment rejected on config.amend_config: {reason}")` — the merge's
   own message already names the tool and the malformedness, the wrapper adds the
   action.
   → checkpoint: names tool + action + malformedness, no duplication. → passes.
9. **Output**: the `ConfigOverlay`. The zone never prints; the caller prints
   `summary_lines` to stderr and consumes `overlay.config`.

#### Checkpoint Summary
- Registry/platform API match: passed (verified against `state.py`, `delivery.py`).
- Hard-error format: passed (pipeline precedent format reused verbatim).
- Passthrough semantics: passed (empty contributions → the passed object, zero
  rebuild — mirrors `merge_workflow_overlay` step 1).

### Trace: `merge_config_amendments(base, contributions)`

#### Chain
1. **Input**: `base` — the authored `ProjectConfig` (loaded, frozen); `contributions`
   — the committed `ToolAmendment` list in enumeration order (each amendment list in
   buffer order).
2. **Step (validate)**: every amendment of every contribution is resolved against the
   configuration type tree (the descriptor table under *Algorithm Design*). A path is
   known iff it resolves to a leaf: a scalar leaf (`str`/`int`/`bool`), a list-valued
   leaf (`list[str]`), or an individual mapping entry (`str` under `dict[str, str]`;
   free-form under `commands`). An unknown path, a non-leaf address (a section or a
   whole mapping), or a wrong-typed value at the node raises
   `ValueError(f"tool {tool}: amendment at {path!r} {detail}")` — nothing of the run
   applies.
   → checkpoint: the value vocabulary `str | int | bool | list[str]` covers every
   model-known leaf type (verified field-by-field against `config.py`: str scalars,
   `review.skip` bool, `max_iterations`/`patience` ints, `review.roles`/`lint.ignore`
   lists, mapping entries under `env`/`hosts`/`tools`/`codemanifest.usages`;
   `commands` free-form). `bool` at an `int` node is rejected explicitly
   (`isinstance(True, int)` — mirrors the loader's `_parse_optional_int` gate).
   The three `DepConfig` scalars additionally carry the loader's own structural
   rules (design decision, within "the result is a structurally valid
   configuration"): `usages.<g>.<d>.git` must be a non-blank string, `.ref`
   must be non-blank when amended, and `.root` must pass the loader's
   path-safety rule (no absolute path, no `..` segment) — a blank `root`
   normalizes to `None` at compose, never an error. Without these, a tool
   could `force` `git=""` / `ref=""` / `root="../../"` and produce a
   configuration the loader itself rejects — the same argument that
   motivates the materialization postcheck applies verbatim.
   → passes.
3. **Step (resolve)**: authored silence is evaluated against `base` only (never the
   merged state): a scalar is silent iff `None`; a list leaf iff `None` or `[]`; a
   mapping entry iff its container is `None`/`{}` or the key is absent; every leaf
   under a `None` section is silent; `False`, `""`, and a present mapping value are
   authored (not silent). `set` on a non-silent path is dropped silently. Per path:
   any `force` candidate beats every `set`; among equal intent the later (tool, buffer)
   position wins.
   → checkpoint: algebra matches the ADR ("Merge algebra", "Authored silence").
   Note: authored `""` (e.g. a verbatim `image: ""`) is non-silent — set drops,
   force overwrites; deterministic either way. → passes.
4. **Step (compose)**: each winning amendment applies to `base` in applied order —
   materialize missing intermediate nodes of model-known paths (default instances:
   `BuildConfig()`, `ReviewConfig()`, `AdditionalReviewConfig()`, `PipelineConfig()`,
   `CodemanifestConfig()`, `TopicsConfig(base_ref=None, publish_commit=None)`,
   `LintConfig(ignore=[])`, `DepConfig(git=None, ref=None, root=None)`, fresh `dict`s
   for mappings), replace list-valued leaves wholesale, set individual mapping
   entries, reconstruct the affected frozen instances bottom-up
   (`dataclasses.replace` / `cls(**fields)`).
   → checkpoint A: purity — `base`, the contributions, and their collections are never
   mutated; unmodified sections pass by reference (the repo shallow-copy convention,
   as in `merge_workflow_overlay`); modified mappings are fresh dicts; list values
   land as fresh copies (`list(value)`), so the result never aliases a
   contribution's collection. → passes.
   → checkpoint B (the materialization corner): a materialized `DepConfig` whose
   `git` stays `None` after every winner of the run is applied (no amendment of
   any tool supplied `usages.<group>.<dep>.git`) cannot be a structurally valid
   configuration (`git: str`, required, and the sync consumer would later pass
   `None` to git).
   Resolution: the composer's postcheck — a FINAL PASS over the finished
   composition, after every winner is applied, never inside the per-winner loop —
   raises the structural failure
   `ValueError(f"tool {tool}: amendment at {path!r} materializes "
   f"usages.{group}.{dep} without its required git")` naming the tool of the first
   applied amendment under that dep branch. The check is order-independent: a
   contribution may set `usages.<g>.<d>.ref` before any tool supplies `.git` —
   only a branch left without `git` at the end fails. This is the tool's
   structural failure — the same hard treatment as an unknown path; it is a
   faithful reading of the existing Requirements ("the result is a structurally
   valid configuration" + "raise naming the tool and the malformedness"), not a
   contract change.
   `LintConfig(ignore=[])` and `TopicsConfig(None, None)` materializations are valid
   (the loader's own absence shapes). → passes (design decision recorded).
5. **Step (collect)**: one `AppliedAmendment(tool, path, intent)` per applied path —
   `intent` is exactly `set` or `forced` (the applied vocabulary; the buffer's `force`
   records as `forced`) — ordered by the winning amendment's (contribution index,
   buffer index).
   → checkpoint: "in enumeration order — one record per applied path" pinned to the
   winner's enumeration position. → passes.
6. **Output**: `ConfigOverlay(config=effective, applied=[...])`. Empty contributions →
   the passthrough overlay: the passed `base` object itself, `applied=[]`,
   `summary_lines=[]` — zero rebuild (the no-tool-packages guarantee).

#### Checkpoint Summary
- Type-tree coverage: passed (every model field classified; table below).
- Merge algebra: passed (ADR-faithful).
- Purity/determinism: passed (same base + same contributions → the same overlay).
- `DepConfig` materialization corner: passed with the recorded decision.

### Trace: `ConfigAmendment.set / force` (the buffer)

#### Chain
1. **Input**: a hook (through the `wrap_context` proxy) calls
   `context.set("build.agent", "claude")` or `context.force("topics.base_ref", "origin/main")`.
2. **Step**: the proxy passes the method call through (calls are transparent; only
   attribute assignment is blocked).
3. **Step**: `set` constructs `PathAmendment(path=path, intent="set", value=value)` and
   stores it in `self._amendments[path]` — a plain `dict` keyed by path, so a later
   amendment of the same tool on the same path replaces the earlier one and keeps the
   first-insertion position (Python dict semantics = "buffer order").
   `force` does the same with `intent="force"`. Nothing else changes; nothing is
   applied here. A `set` on a non-silent authored path is NOT checked here — the drop
   happens in the merge (the view owns no knowledge of winning).
   → checkpoint: "buffers into the buffer of this tool alone and changes nothing until
   the delivery commits it" — the buffer is private (`_amendments`, accessed by the
   delivery walk of the same package, the `amendment._contribution` precedent).
   → passes.
4. **Output**: the buffer entry; the walk later commits `list(self._amendments.values())`.

#### Checkpoint Summary
- Same-path replacement: passed (dict-keyed buffer).
- Isolation: passed (fresh `ConfigAmendment` per tool; buffers never shared).

### Trace: `ConfigOverlay.summary_lines`

#### Chain
1. **Input**: `overlay.summary_lines` (a `@property`, return annotation `list[str]`).
2. **Step**: `applied` empty → `[]`. Otherwise one header
   `f"config amendments: {len(applied)} applied"` plus one line per applied amendment
   in applied order: `f"- {tool} {intent} {path}"` with `intent` ∈ {`set`, `forced`}.
3. **Output**: the composed lines — data only (the zone never prints); no
   configuration value appears in any line (the records carry no value by construction
   — `AppliedAmendment` has no value field).
   → checkpoint: format pinned (design decision — the first summary surface of its
   kind; tests assert the exact strings). → passes.

### Trace: the rename (`lang` -> `language`)

#### Chain
1. **Input**: `.goga/config.yml` with the top-level `language:` key (the authored
   vocabulary is unchanged — the loader reads `data["language"]` today).
2. **Step**: `config.py` — `ProjectConfig.lang: str` → `language: str` (position and
   requiredness unchanged; `kw_only=True` keeps all call sites keyword-based).
3. **Step**: `loader.py` — the local `lang = _parse_language(data)` renames to
   `language`; the assembly `ProjectConfig(lang=lang, ...)` becomes
   `ProjectConfig(language=language, ...)`. `_parse_language` itself is unchanged
   (already reads `language`, already raises `KeyError` on a missing key — matching
   the reworded Algorithm step 4).
4. **Step**: `goga/commands/contract/contract.py:162` —
   `lang = lang if lang is not None else config.lang` → `... else config.language`
   (the CLI param `lang` and `--lang` option stay).
5. **Step**: `goga/commands/config/config.py` — delete `_ALIAS_MAP` and the
   `parts[0] in _ALIAS_MAP` rewrite in `_resolve_option`; `language` resolves through
   the unchanged `getattr` traversal; `goga config lang` stops resolving ("Option not
   found" — intended, one vocabulary).
6. **Output**: every model-field consumer reads `config.language`.
   → checkpoint: absence sweep — the remaining `lang` tokens in the repo are NOT
   model-field references: the CLI `--lang` option and callback param
   (`goga/commands/contract/contract.py`, `goga/contract/dispatcher.py`) and
   test-local helper params (`_write_goga_yml(lang=...)` in
   `tests/contract/test_integration_*.py` — they write the YAML file, not the model;
   they MAY stay, renaming them is optional cosmetics). All `.lang` accesses and
   `lang=` constructor kwargs in `tests/` ARE model references and must change (the
   file list is under *Test Stack Trace*). → passes.

### Trace: the consumer switches (nine surfaces)

Each verified against its current source:

1. **`goga/commands/pipeline/pipeline.py:151-165`** — the load try gains the delivery
   (see the shape below); the `ValueError` of a hard failure is caught by the existing
   `(FileNotFoundError, KeyError, ValueError, yaml.YAMLError)` → `ClickException`
   wrapper (clean, exit 1). After the try: print the summary to stderr, then
   `config = overlay.config`; the `config.pipeline is None` guard and every downstream
   read address the effective configuration unchanged. → passes.
2. **`goga/commands/lint/lint.py:24-30`** — two-step, because the existing except
   swallows `ValueError` into `ignore=None` (config optional for lint): the loader
   try keeps its swallow semantics; on SUCCESS the delivery runs OUTSIDE that try in
   its own `try: ... except ValueError as exc: raise click.ClickException(str(exc))
   from exc` — a hard checkpoint failure must stop lint with a clean error, never be
   treated as "config absent", never a raw traceback. Then the summary prints to
   stderr and `ignore` derives from `overlay.config.lint`. → passes (the one consumer
   whose wrapper would otherwise mask the hard failure).
3. **`goga/commands/contract/contract.py:157-162`** — the delivery joins the load
   inside the existing try (its `ValueError` → `ClickException` ✓); step 2 resolves
   `lang` from `overlay.config.language`. → passes.
4. **`goga/commands/install/install.py:305-314`** — the bulk path's load try gains the
   delivery; `tools = overlay.config.tools if ... is not None else {}`. The single
   and local paths are untouched (no load, no checkpoint). → passes.
5. **`goga/commands/config/config.py:117-130`** — the delivery joins the existing try;
   `_resolve_option(overlay.config, option)`; `_ALIAS_MAP` deleted; stdout stays the
   data-clean value surface (the summary goes to stderr); exit codes unchanged.
   → passes.
6. **`goga/commands/build/build.py:301-314`** — the delivery joins the load try (step
   2, after the docker check and the home preamble — home stays authored-only);
   `config = overlay.config` before the `config.build is None` guard and the agent
   guard; every downstream field access is unchanged code reading the effective
   object. → passes.
7. **`goga/commands/topics/topics.py:48-61`** — `_topics_section()`: the delivery runs
   after a successful load (its `ValueError` joins the existing
   `(KeyError, ValueError, yaml.YAMLError)` → `ClickException` wrapper); the summary
   prints there; `return overlay.config.topics`. `FileNotFoundError` → `None` (unset,
   no checkpoint — nothing was loaded); the load happens only when
   `base_ref is None or commit_message is None` (the create step's existing guard) —
   with both flags given, no load and no checkpoint, exactly as the contract's
   "read only for values no flag provided". → passes.
8. **`goga/usages/status/status.py:62`** — after the fail-loud load: deliver, print
   the summary via `click.echo(line, err=True)` (the new `click` import — the module
   gains `import click` per the `click` practice), iterate
   `overlay.config.usages`. A checkpoint `ValueError` propagates; the
   `goga usages status` command's existing wrapper converts it to
   `ClickException`. → passes.
9. **`goga/usages/sync/sync.py:43`** — the same shape as `status`; a `click` import is
   added. → passes.

Deliberately unchanged: `goga/build/__main__.py` (the in-container authored-only
load), `goga/commands/usages` (owns no load; the summary printing belongs to
`status`/`sync`), `goga/onboarding`, `goga/scaffold`, `goga/pipeline` (in-container
consumers), the whole hooks platform beyond the catalog record.

## Algorithm Design

### `ConfigAmendment` / `PathAmendment` (amendments.py)

**Responsibility**: the per-tool read-and-amend view and its buffered entries.

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

**Algorithm** (each method): construct the entry, store it keyed by `path` — a later
call on the same path replaces the earlier one and keeps the first-insertion position.
No validation, no application, no error paths here (structural validation belongs to
the merge; the authored-silence drop belongs to the resolution).

**Errors**: none raised.

**Edge cases**: a non-`str` `path` or an out-of-vocabulary `value` is stored verbatim
and fails later in the merge's validation, naming the tool — the delivery never
crashes on hook input.

### `merge_config_amendments` (overlay.py)

**Responsibility**: the deterministic, pure, type-checked composition of the effective
configuration.

**The configuration type tree** (the validation table — a hand-written module-level
descriptor in `overlay.py`, mirroring the pipeline zone's hand-written
`_STAGE_FIELDS` precedent; a unit test cross-checks it against
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

**Algorithm:**
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

**Errors:**
- `ValueError` (structural) → the delivery wraps it with the action name → the
  command's `ClickException` → the user sees one clean line naming the tool, the
  action, and the malformedness; nothing applied; exit 1.

**Edge cases:**
- No contributions → passthrough (byte-identical object).
- Two tools on one path: `force` (any position) beats `set`; later beats earlier
  within equal intent.
- One tool on one path twice: the buffer kept only the later entry.
- Authored `""` scalar / `False` bool / non-empty mapping value → non-silent.
- `commands.<any-key>` accepts any buffer value without a node check.
- Same branch materialized by several amendments → materialization is idempotent
  (defaults constructed once per walk).
- An amended `usages.<g>.<d>.git`/`.ref` of `""` or an unsafe `root`
  (`"../.."`, absolute) → the same structural failure; a blank `root`
  composes as `None` (the field never stores `""`).
- List values land as fresh copies (`list(value)`), never aliases of the
  contribution's list objects.

### `ConfigOverlay` (overlay.py)

**Responsibility**: the amendment result — effective config, applied records, summary.

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

**Algorithm**: `summary_lines` composes from `applied` only — no value field exists on
`AppliedAmendment`, so no configuration value can leak into a line by construction.

**Errors**: none.

**Edge cases**: empty `applied` → `[]` → the caller prints nothing.

### `ConfigHooks` (events.py)

**Responsibility**: the checkpoint surface — the staged per-tool delivery of the hard
`config / amend_config` action over the platform facade.

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

**Errors:**
- `ImportError` (a broken tool package) — the single fatal case, raised by
  `build_once`, names the package; outside the action's error class.
- `ValueError` (hard failure) — names the hook/tool + action, or the tool +
  malformedness + action; the command converts it to `ClickException`.

**Edge cases:**
- No subscriptions → empty `groups` → empty `contributions` → the passthrough overlay;
  the delivery is unobservable.
- A tool with several hooks: the contribution commits only after every hook of the
  tool returned (commit granularity = the tool).
- A tool whose every hook is a no-op (empty buffer) commits nothing — no warning.

### `goga/config/hooks/__init__.py` (the facade)

`__all__ = ["AppliedAmendment", "ConfigAmendment", "ConfigHooks", "ConfigOverlay",
"PathAmendment", "ToolAmendment", "merge_config_amendments"]` — exactly the seven
contract names, re-exported from `amendments`, `overlay`, `events`.

### Consumer Switches (the nine surfaces)

The common shape (commands whose load try already wraps `ValueError` — pipeline,
contract, install, config, build):

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

Per-surface deviations:

- **lint** — the two-step (delivery outside the swallowing try; its own
  `except ValueError -> ClickException`; `ignore` derives from `overlay.config.lint`;
  a failed/absent load: `ignore = None`, no checkpoint).
- **topics** — inside `_topics_section()`; `FileNotFoundError` → `None` (no
  checkpoint); returns `overlay.config.topics`.
- **install** — only the bulk path; `tools` from `overlay.config.tools`.
- **config** — traversal over `overlay.config`; `_ALIAS_MAP` deleted.
- **contract** — `lang = lang if lang is not None else overlay.config.language`.
- **status/sync** (plain modules): deliver after the fail-loud load, print the
  summary with `click.echo(..., err=True)` (new `import click`), then use
  `overlay.config`; `ValueError` propagates to the `goga usages` wrapper.
- **stderr only**: stdout of every command is unchanged; `goga config` stdout stays
  headers + effective values only.

### The catalog record (`goga/hooks/catalog/catalog.py`)

Append after the build block (the manifest's "after the existing records";
`declared_actions()` sorts by (domain, name), so list position is cosmetic):

```python
Action(domain="config", name="amend_config", error_class="hard"),
```

## Cross-cutting Concerns

- **Error handling**: the hard action raises `ValueError` from the zone; every command
  surface converts it to `click.ClickException` (clean single-line message, exit 1) —
  via the existing `(FileNotFoundError, KeyError, ValueError, yaml.YAMLError)` wrapper
  where the delivery sits inside the load try (pipeline, contract, install, config,
  build, topics, and the `goga usages` wrappers over status/sync), via a dedicated
  wrapper for lint (whose loader swallow must not mask it). No raw tracebacks. The
  messages never contain configuration values.
- **Logging**: the zone logs nothing on the happy path (the summary lines are the
  observable; the passthrough is unobservable; dropped sets are silent by contract);
  the platform's own registration warnings stay. Commands keep their existing logs.
- **Validation**: structural only, entirely inside `merge_config_amendments`, before
  anything applies (all-or-nothing per run). No semantic validation (whitelists,
  ranges, resolvability stay with the consumers — the loader's own stance).
- **Caching**: one `HookRegistry` per `ConfigHooks` instance per run, built lazily on
  the first checkpoint (`build_once`); nothing cached across runs. A command
  constructs the surface at its load moment — the config checkpoint is usually the
  run's first checkpoint, so the enumeration happens there and later checkpoints of
  the same run would reuse it.
- **Concurrency**: single-threaded CLI surfaces; no thread-safety requirements (the
  frozen models and the per-tool buffers need none).

## Usages Analysis

### `convention` (`.goga/usages/conventions.md`)
- **What it provides**: the project-wide Python rules — relative imports, kw_only
  dataclasses, Google docstrings, logging discipline, blank-line block formatting,
  test structure.
- **Where used**: every touched file; the zone models and the test suites mirror it.
- **Why chosen**: mandatory for all cells.
- **How exactly**: `from ...hooks import ...` (the platform facade) and
  `from ..project import ...` (the models — equivalently `...config.project`)
  in the zone; `@dataclass(kw_only=True)` (+ `frozen=True` for pure data); Google-style
  docstrings with Args/Returns/Raises; `logger = logging.getLogger(__name__)` where
  logging appears; tests mirror `tests/<package>/...`.

### `click` (`.goga/usages/cooks/click.md`)
- **What it provides**: the CLI framework practices — echo to stderr, ClickException,
  CliRunner testing.
- **Where used**: the seven commands (summary printing, error wrapping) and — newly —
  `status`/`sync` (stderr summary lines).
- **Why chosen**: the commands are click surfaces; the summary must go to stderr
  without touching stdout.
- **How exactly**: `click.echo(line, err=True)` per summary line; `raise
  click.ClickException(str(exc)) from exc` for the hard failure.

### `yaml` (inline, `goga/config/project`)
- Unchanged — `yaml.safe_load` in the loader; the rename touches no parse logic.

### Imported Usages
- `per-tool-delivery` from `goga/hooks` — path `goga/hooks/.usages/per-tool-delivery.md`.
  The staged delivery loop skeleton (`HookRegistry`/`build_once`,
  `subscriptions_for`, `self_context`, `wrap_context`, `build_hook_arguments`,
  group-per-tool, commit-after-success). `ConfigHooks.amend_config` applies it as
  written; the deviation from its soft-example (warn-and-continue) is the action's
  hard error class, taken from the catalog record — exactly the "treat a failure per
  the action's error class" rule of the practice.
- `registering-hooks` from `goga/hooks` — path
  `goga/hooks/.usages/registering-hooks.md`. The hook signature contract
  (`context`/`self` offered names) and the failure behavior behind the checkpoint;
  drives `build_hook_arguments` usage and the hard stop.
- `checkpoints` (imported by the nine consumers) — path
  `goga/config/hooks/.usages/checkpoints.md`. The consumer-side delivery shape:
  authored load → `amend_config(config=...)` → print `summary_lines` to stderr →
  consume `overlay.config`; the in-container authored-only rule.

## `.usages/` Update

### Cell: `goga/config/hooks`

#### Existing Files — Consistency
- **`checkpoints.md`** → `goga/config/hooks/.usages/checkpoints.md`
  - Status: current — matches the contract (`ConfigHooks()`, `amend_config`,
    `overlay.summary_lines` to stderr, passthrough, in-container authored-only).
  - Additions needed: none (the `print_summary_to_stderr` placeholder is consumer
    pseudocode by design).
  - Updates needed: none.

#### New Files (if any)
- None beyond the created file.

### Cell: `goga/config`

#### Existing Files — Consistency
- **`registering-hooks.md`** → `goga/config/.usages/registering-hooks.md`
  - Status: current against the contract (events table, view members, merge rules,
    failure treatment, run output).
  - Additions needed (recommended, defer to the implementation stage): one bullet in
    the path-vocabulary list covering the materialization corner — proposed wording:
    "Materializing an absent `usages.<group>.<dep>` branch requires the amendments
    to supply its `git` too — a materialized dep without `git` is the same hard
    structural failure. Amended `git`/`ref` values must be non-empty strings and
    `root` a safe relative subpath (no `..`, no absolute) — blank `git`/`ref` and
    unsafe `root` values are structural failures; a blank `root` means no root."
    (A tool-author precision fix surfaced by the trace and the review; the
    contract already implies it — "the result is a structurally valid
    configuration".)
  - Updates needed: none.
- **`project-configuration.md`** → `goga/config/.usages/project-configuration.md`
  - Status: current — `config.language` accessor examples and the zone-entry note
    landed with the materialization.
  - Additions/Updates needed: none.

### Cell: `goga/usages/status`, `goga/usages/sync`, the seven command cells
- No `.usages/` directories exist in these cells — nothing to update (the `click`
  and `checkpoints` practices are imported, which is the correct connection form).

## Test Stack Trace

### General Setup

- Zone suites pin the same two platform boundary fixtures as the pipeline/topics
  zones: `tests/config/hooks/conftest.py` re-exports `pin_package_environment` and
  `install_tool_package` from `tests/hooks/conftest.py` — the platform code under
  test runs for real; only `packages_distributions` and the `sys.modules` entry of a
  fake `goga_tool_*` package are pinned.
- A minimal authored config fixture (built with the real
  `ProjectConfig(language="python", ...)` constructors or by writing a real
  `.goga/config.yml` into `tmp_path` + `os.chdir` for loader-level tests).
- Fake tools subscribe via `install_tool_package("goga_tool_harden",
  lambda hooks: hooks.subscribe("config", "amend_config", "hardening", harden))`.
- CLI consumer tests use `click.testing.CliRunner` and assert on
  `result.output` (stdout) and the runner's stderr capture.

### Source File Registry

Under test: `goga/config/hooks/{amendments,overlay,events,__init__}.py`,
`goga/config/project/{config,loader}.py`, `goga/hooks/catalog/catalog.py`,
`goga/commands/{pipeline,lint,contract,install,config,build,topics}/*.py`,
`goga/usages/{status,sync}/*.py`, `goga/commands/config/config.py` alias removal,
`goga/commands/contract/contract.py` language resolution.

---

### Positive Tests

#### `tests/config/hooks/test_overlay.py::test_set_applies_on_silent_path`

**Setup**: `base = ProjectConfig(language="python", image=None, dockerfile=None,
build=None, pipeline=None, commands={})` (build absent — the branch is silent);
`contributions = [ToolAmendment(tool="harden", amendments=[PathAmendment(
path="build.agent", intent="set", value="claude")])]`.

**Input**: `merge_config_amendments(base, contributions)`.

**Trace**:
```
merge_config_amendments(base, [harden])
  -> validate: "build.agent" resolves: build -> section (None-able) -> agent -> str leaf;
     value "claude" is str                                    -> known, typed
  -> resolve: base.build is None -> branch silent -> set survives, wins
  -> compose: materialize BuildConfig(), set agent="claude"
     -> ProjectConfig.replace(build=BuildConfig(agent="claude", env={}, ...))
  -> collect: [AppliedAmendment(tool="harden", path="build.agent", intent="set")]
  -> ConfigOverlay(config=effective, applied=[...])
  -> overlay.summary_lines == ["config amendments: 1 applied",
                               "- harden set build.agent"]
```

**Assertions**:
```
overlay.config.build is not None
overlay.config.build.agent == "claude"
overlay.applied == [AppliedAmendment(tool="harden", path="build.agent", intent="set")]
overlay.summary_lines == ["config amendments: 1 applied", "- harden set build.agent"]
base.build is None                       # purity — the authored object untouched
```

**Sufficiency**: pins the core scenario of the ADR (a prepared parameter set on a
minimal config materializes the absent branch) and the exact summary format; prevents
regression of materialization or of the summary vocabulary.

---

#### `test_force_overwrites_authored_and_beats_set_cross_order`

**Setup**: `base` with `topics=TopicsConfig(base_ref="origin/dev", publish_commit=None)`;
two contributions in enumeration order: tool "polite" sets `topics.base_ref` =
"origin/main" (a set on a NON-silent path) and tool "guard" forces `topics.base_ref`
= "origin/stable".

**Input**: `merge_config_amendments(base, [polite_set, guard_force])`.

**Trace**:
```
  -> validate: both paths known (topics -> base_ref -> str leaf), values str
  -> resolve: base_ref authored "origin/dev" (non-silent) -> polite's set dropped
     silently; guard's force survives -> winner = guard (the only force)
  -> compose: TopicsConfig(base_ref="origin/stable", publish_commit=None)
  -> applied == [AppliedAmendment("guard", "topics.base_ref", "forced")]
```

**Assertions**:
```
overlay.config.topics.base_ref == "origin/stable"
[(a.tool, a.path, a.intent) for a in overlay.applied] == [("guard", "topics.base_ref", "forced")]
"polite" not in any summary line          # a dropped set leaves no trace
```

**Sufficiency**: pins the two ADR algebra rules (authored-wins for set; force beats
set regardless of order) and that a dropped set is fully silent — no warning, no
record, no line.

---

#### `test_later_tool_wins_equal_intent`

**Setup**: `base` with `build=None`; contributions: tool "a" sets
`pipeline.env.LOG_LEVEL="INFO"` then tool "b" sets `pipeline.env.LOG_LEVEL="DEBUG"`
(enumeration order a, b).

**Input**: `merge_config_amendments(base, [a, b])`.

**Trace**:
```
  -> validate: pipeline -> env -> mapping entry "LOG_LEVEL" (str leaf); values str
  -> resolve: pipeline absent -> branch silent; equal intent -> later tool (b) wins
  -> compose: materialize PipelineConfig(), fresh env dict {"LOG_LEVEL": "DEBUG"}
  -> applied == [AppliedAmendment("b", "pipeline.env.LOG_LEVEL", "set")]
```

**Assertions**:
```
overlay.config.pipeline.env == {"LOG_LEVEL": "DEBUG"}
[(a.tool, a.intent) for a in overlay.applied] == [("b", "set")]
```

**Sufficiency**: pins "among equal intent the later tool in enumeration order wins"
and the mapping-entry materialization (`pipeline.env.KEY` on an absent branch).

---

#### `test_config_hooks_passthrough_without_subscriptions`

**Setup**: `pin_package_environment({})` (no tool packages); `authored` built by the
real loader from a real `.goga/config.yml` in `tmp_path`.

**Input**: `overlay = ConfigHooks().amend_config(config=authored)`.

**Trace**:
```
  -> _ensure_registry: HookRegistry().build_once() enumerates nothing
  -> subscriptions_for("config", "amend_config") == []
  -> contributions == [] -> merge passthrough branch
  -> ConfigOverlay(config=authored, applied=[])
```

**Assertions**:
```
overlay.config is authored           # the passed object itself — zero rebuild
overlay.applied == []
overlay.summary_lines == []
```

**Sufficiency**: the no-tool-packages guarantee — with nothing installed, every
config-loading command composes exactly what was passed; prevents any accidental
rebuild/copy that would break byte-identity expectations downstream.

---

#### `test_subscribed_tool_with_empty_buffer_commits_nothing`

**Setup**: `pin_package_environment({"goga_tool_silent": ["silent-dist"]})`;
`install_tool_package("goga_tool_silent", register)` where `register` subscribes
`observe(context)`: the hook reads `context.config.image` and buffers nothing;
`authored` built by the real loader from a real `.goga/config.yml` in `tmp_path`.

**Input**: `overlay = ConfigHooks().amend_config(config=authored)`.

**Trace**:
```
  -> registry built once; one subscription of goga_tool_silent
  -> observe() runs for real, returns; the buffer stays empty
  -> the tool commits nothing — silent continue, no warning, no empty ToolAmendment
  -> contributions == [] -> the merge passthrough branch
  -> ConfigOverlay(config=authored, applied=[])
```

**Assertions**:
```
overlay.config is authored
overlay.applied == []
overlay.summary_lines == []
```

**Sufficiency**: pins the no-op contribution semantics — a subscribed tool whose
hooks only read commits nothing, silently — distinct from the no-subscription
case; prevents an empty `ToolAmendment` or a no-op warning from ever being
emitted.

---

#### `tests/config/hooks/test_events.py::test_per_tool_delivery_commits_buffered_amendments`

**Setup**: `pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})`;
`install_tool_package("goga_tool_hardener", register)` where `register` subscribes
`harden(context)`: reads `context.config.build` (mutual-blindness read) and calls
`context.set("build.agent", "claude")` and `context.force("lint.ignore", ["a/", "b/"])`;
authored base with `build=None`, `lint=None`.

**Input**: `overlay = ConfigHooks().amend_config(config=authored)`.

**Trace**:
```
  -> registry built once; one subscription of goga_tool_hardener
  -> ConfigAmendment(config=authored) -> wrap_context -> build_hook_arguments
     projects only the declared `context`
  -> harden() runs for real: two buffered PathAmendments
  -> tool committed: ToolAmendment("hardener", [...])  # the platform derives
     the identity from the package name: goga_tool_hardener -> hardener
     (prefix dropped, underscores to hyphens — ToolPackage.tool)
  -> merge: both paths known (list-valued leaf lint.ignore wholesale); silent branch
     materializes BuildConfig(agent=...) and LintConfig(ignore=[...])
  -> overlay returned; nothing printed by the zone
```

**Assertions**:
```
overlay.config.build.agent == "claude"
overlay.config.lint.ignore == ["a/", "b/"]
[(a.tool, a.path, a.intent) for a in overlay.applied]
    == [("hardener", "build.agent", "set"),
        ("hardener", "lint.ignore", "forced")]
```

**Sufficiency**: the end-to-end delivery over the real platform — the per-tool view,
the buffer, the commit granularity, and the wholesale list replacement in one
integration of the zone; prevents wiring regressions between events.py and overlay.py.

---

#### `tests/commands/test_config.py::test_config_language_direct_and_effective_values`

**Setup**: real `.goga/config.yml` in `tmp_path` (`language: python`, `build: {agent:
codex}`); a fake tool forcing `build.agent` to `claude`; `CliRunner`.

**Input**: `runner.invoke(config_cmd, ["language"])` then `["build.agent"]`.

**Trace**:
```
  -> config command: load -> ConfigHooks().amend_config -> ClickException never
  -> summary lines to stderr; stdout carries only "# <option>" + value
  -> _resolve_option(overlay.config, "language") — getattr hit, no alias map
  -> _resolve_option(overlay.config, "build.agent") == "claude"  (amended)
```

**Assertions**:
```
result.exit_code == 0
result.output == "# language\npython\n"            # stdout data-clean
"# build.agent\nclaude\n" for the second invoke
the summary line "- hardener forced build.agent" appears in stderr, not stdout
```

**Sufficiency**: pins the rename payoff (direct `language` resolution, alias map
gone), the effective-value printing (R10), and the stdout/stderr split of the data
surface vs the amendment summary.

---

#### `test_contract_resolves_language_from_effective_config`

**Setup**: real config (`language: python`); a fake tool forcing `language` =
`golang`; `CliRunner` invoking the contract command with `--lang` absent; a spy on
`goga.contract.dispatcher.contract` (mock.patch at the import point).

**Input**: `runner.invoke(contract_cmd, ["goga/config/project"])`.

**Trace**:
```
  -> load -> amend_config (CLI lang is None) -> effective language == "golang"
  -> dispatcher.contract(lang="golang", ...) invoked
```

**Assertions**:
```
spy.call_args.args[0] == "golang"             # effective, not authored; the call
                                              # site passes lang positionally —
                                              # contract_logic(lang, cell_path)
```
and with `--lang swift` given: `spy.call_args.args[0] == "swift"` (CLI wins).

**Sufficiency**: pins the renamed field resolution and the CLI-over-config priority;
prevents the resolution silently falling back to the authored value.

---

#### The uniform-reach consumer tests (pipeline, lint, install, build, topics, status, sync)

One switch test per surface, same skeleton: fake tool forces one observable knob
(e.g. `lint.ignore`, `tools.viewer`, `topics.base_ref`, `pipeline.env.KEY`,
`usages.<g>.<d>.ref`); assert (a) the command behaves per the EFFECTIVE value (lint
filters / install resolves the amended tool spec / build guard passes an amended
build section / topics resolves the amended base / status-sync iterate the amended
usages), (b) the summary line is on stderr, (c) stdout is unchanged vs the
no-tools run, (d) exit codes unchanged. Two special cases:

- **lint (`test_lint_checkpoint_failure_is_clean_error`)**: fake tool RAISES inside
  its hook → `runner.invoke(lint_cmd, ["."])` → `exit_code == 1`,
  `"failed on config.amend_config"` in output, no traceback, and lint does NOT run
  unfiltered (the delivery is outside the swallow).
- **lint absent config**: no `.goga/config.yml` → lint runs unfiltered, no registry
  assembly (assert `packages_distributions` mock not called), no stderr output.

**Sufficiency**: the uniform-reach acceptance axis — each of the nine surfaces
delivers the checkpoint, consumes the effective configuration, and keeps its output
contract; prevents a surface silently keeping the authored-only load.

---

### Negative Tests

#### `tests/config/hooks/test_overlay.py::test_unknown_path_is_structural_failure`

**Setup**: `base` minimal; `ToolAmendment(tool="harden",
amendments=[PathAmendment(path="build.nonexistent", intent="set", value="x")])`.

**Input**: `pytest.raises(ValueError, match="tool harden: amendment at
'build.nonexistent'")` around the merge.

**Trace**:
```
  -> validate: "build" resolves to section; "nonexistent" names no BuildConfig field
  -> ValueError raised BEFORE resolution/composition — no partial application
```

**Assertions**:
```
excinfo.match("tool harden")
excinfo.match("build.nonexistent")
base unchanged (compare via dataclasses.astuple / field-by-field)
```

**Sufficiency**: pins the all-or-nothing validation and the message contract (tool +
path); prevents the merge from ever applying a partially validated run.

---

#### `test_non_leaf_address_and_wrong_type_fail`

**Setup**: four merges — (a) `path="build.env"` with value `{"K": "v"}` (a whole
mapping — non-leaf); (b) `path="build.max_iterations"` with value `True` (a bool at
an int node); (c) `path="build.agent.deep"` (continues below a str leaf);
(d) `path="commands.run.cmd"` (below a free-form entry — `commands.<key>` is a
leaf; one level only).

**Input**: `pytest.raises(ValueError)` for each.

**Trace**:
```
(a) "build.env" resolves to the mapping node itself -> non-leaf -> FAILURE
(b) int node gate: isinstance(True, bool) -> rejected explicitly -> FAILURE
(c) "build.agent" resolves to a str leaf; "deep" continues below it -> FAILURE
(d) "commands.run" resolves to a free-form leaf; "cmd" continues below it -> FAILURE
```

**Assertions**:
```
(a) match "non-leaf"; (b)(c)(d) match "unknown path"/"wrong type"
    (message wording pinned)
```

**Sufficiency**: pins leaves-only addressing (the ADR granularity decision) and the
bool-at-int gate (the loader's own `_parse_optional_int` discipline held at the
amendment boundary).

---

#### `tests/config/hooks/test_events.py::test_raising_hook_stops_command_names_tool_and_action`

**Setup**: fake tool whose hook raises `RuntimeError("boom")`; a SECOND subscribed
tool after it in enumeration order.

**Input**: `pytest.raises(ValueError)` around `ConfigHooks().amend_config(...)`.

**Trace**:
```
  -> hard action: the first failure stops the walk at once
  -> ValueError("hook <name> of tool <tool> failed on config.amend_config: boom")
  -> the second tool's hook is never called; nothing committed, nothing merged
```

**Assertions**:
```
excinfo.match(r"hook \w+ of tool hardener failed on config\.amend_config: boom")
second_tool_hook.called is False
```

**Sufficiency**: the hard error class end-to-end — the clean message format (the
pipeline precedent), first-failure stop, and no partial application; prevents a soft
skip-over ever creeping into a hard action.

---

#### `test_materialized_dep_without_git_fails`

**Setup**: `base` with `usages=None`; tool sets `usages.docs.scriba.ref="v2"` (no
`git` amendment anywhere).

**Input**: `pytest.raises(ValueError)` around the merge.

**Trace**:
```
  -> path known (usages -> group key -> dep key -> ref -> str leaf); value typed
  -> compose: materialize DepConfig(git=None, ref="v2", root=None)
  -> POSTCHECK: git is None on a materialized dep
  -> ValueError("tool <tool>: amendment at 'usages.docs.scriba.ref' materializes
     usages.docs.scriba without its required git")
```

**Assertions**:
```
excinfo.match("usages.docs.scriba")
excinfo.match("required git")
```
and the companion positive: set BOTH `usages.docs.scriba.git` and `.ref` — in
either buffer order — → the dep materializes fully and applies (the postcheck is
a final pass; the order within the run never matters).

**Sufficiency**: pins the recorded materialization decision — a structurally invalid
configuration can never be produced, and the failure is the tool's, clean and named.

---

#### `test_depcfg_value_rules_match_the_loader`

**Setup**: `base` with an authored `usages.docs.scriba` dep (git="..."); four
amendments on separate merges — (a) `force("usages.docs.scriba.git", "")`;
(b) `force("usages.docs.scriba.ref", "")`; (c) `force("usages.docs.scriba.root",
"../..")`; (d) `force("usages.docs.scriba.root", "")` on one merge and
`set("usages.docs.scriba.ref", "v2")` alongside.

**Input**: `pytest.raises(ValueError)` for (a)–(c); a clean merge for (d).

**Trace**:
```
(a)(b)(c) validate: the DepConfig scalar rules reject a blank git, a blank ref,
       and an unsafe root -> ValueError naming tool + path (nothing applies)
(d)   validate: a blank root passes (not an error); compose stores root=None
       (the field never holds ""), ref applies
```

**Assertions**:
```
(a) match "tool" and "usages.docs.scriba.git"
(b) match "usages.docs.scriba.ref"
(c) match "usages.docs.scriba.root"
(d) overlay.config.usages["docs"]["scriba"].root is None
    overlay.config.usages["docs"]["scriba"].ref == "v2"
```

**Sufficiency**: pins the loader-parity decision — the amendment boundary holds
the same structural rules the authored load enforces (`_parse_depcfg` /
`_parse_depcfg_root`), so no tool can produce a configuration the loader itself
would reject; the blank-root normalization keeps the model invariant.

---

### Edge Case Tests

#### `test_purity_and_determinism`

**Setup**: one `base` and one contributions list; call the merge twice.

**Input**: `o1 = merge(base, cs); o2 = merge(base, cs)`.

**Trace**: two independent compositions over untouched inputs.

**Assertions**:
```
o1.applied == o2.applied
o1.config == o2.config                    # dataclass equality
base field-by-field unchanged after both calls
shared sections pass by reference: o1.config.codemanifest is base.codemanifest
                                        (unmodified branch — shallow-copy convention)
```

**Sufficiency**: the ADR's determinism guarantee (repeated runs reproduce the
effective configuration) and the purity requirement (the authored file's in-memory
image is never mutated).

---

#### `test_set_on_authored_empty_containers_applies` (authored emptiness loses to set)

**Setup**: `base` with `lint=LintConfig(ignore=[])` and
`build=BuildConfig(env={}, ...)`.

**Input**: set `lint.ignore=["x/"]`, set `build.env.KEY="v"`, and set
`commands.report="on"` (the free-form mapping — no node check).

**Trace**: `[]` and `{}` are absence markers → both silent → both apply; the
absent `commands.report` key is silent → applies.

**Assertions**:
```
overlay.config.lint.ignore == ["x/"]
overlay.config.build.env == {"KEY": "v"}
overlay.config.commands == {"report": "on"}
```
and the counterpart: `review.skip=False` authored + set → dropped (False is
authored, not silent); `image=""` authored + set → dropped ("" is not a marker).

**Sufficiency**: pins the absence-marker set (`None`, `{}`, `[]`) — the subtlest
merge rule — including the `False`/`""` non-markers.

---

#### `test_within_tool_later_same_path_replaces_earlier`

**Setup**: one tool whose hook calls `set("build.agent", "a")` then
`force("build.agent", "b")`.

**Input**: delivery via `ConfigHooks` (or the buffer directly).

**Trace**: the dict-keyed buffer keeps only the later entry at the first-insertion
position.

**Assertions**:
```
overlay.config.build.agent == "b"
applied == [AppliedAmendment(tool, "build.agent", "forced")]
```

**Sufficiency**: the staged-buffer replacement semantics (the ADR consequence);
prevents double-application or order inversion inside one tool.

---

#### `test_facade_all_exactly_seven_names`

**Setup/Input**: `import goga.config.hooks as zone`.

**Assertions**:
```
zone.__all__ == ["AppliedAmendment", "ConfigAmendment", "ConfigHooks",
                 "ConfigOverlay", "PathAmendment", "ToolAmendment",
                 "merge_config_amendments"]
each name importable and is the implementing class/function
ConfigHooks() constructs without enumeration (packages mock not called)
```

**Sufficiency**: the facade check of the plan's verification checklist; also pins
cheap construction.

---

#### `tests/config/hooks/test_overlay.py::test_descriptor_table_matches_model_fields`

**Setup**: import the module-level descriptor table of `overlay.py` and the nine
models — `ProjectConfig`, `BuildConfig`, `ReviewConfig`, `AdditionalReviewConfig`,
`PipelineConfig`, `CodemanifestConfig`, `DepConfig`, `LintConfig`, `TopicsConfig`
(no filesystem, no registry).

**Input**: `dataclasses.fields(...)` of every model, walked against the table.

**Trace**: for each model the test compares the field-name set of the dataclass
with the field-name set the descriptor table records, in both directions, and
checks the node kind of every classified field (scalar / list / mapping /
section / free-form) against the table's entry.

**Assertions**:
```
{f.name for f in fields(ProjectConfig)} == set(table["ProjectConfig"].fields)
... one line per model, all nine ...
set(table) == {"ProjectConfig", "BuildConfig", "ReviewConfig",
               "AdditionalReviewConfig", "PipelineConfig", "CodemanifestConfig",
               "DepConfig", "LintConfig", "TopicsConfig"}
```

**Sufficiency**: a model field added, removed, or retyped without a matching
descriptor update fails the suite — the drift-detection stance of the pipeline
zone's `test_models_carry_exactly_the_declared_fields`; prevents the validation
table from silently accepting an unknown new field (or rejecting a renamed one)
after a model change.

---

#### `tests/hooks/catalog/test_catalog.py::test_config_amend_config_record_present`

**Setup/Input**: `declared_actions()`.

**Assertions**:
```
Action(domain="config", name="amend_config", error_class="hard") in declared_actions()
the pre-existing records are unchanged (compare against a pinned expected list)
```

**Sufficiency**: the catalog check of the plan — the record exists, the published
records are byte-identical.

---

#### The rename sweep (existing suites)

Mechanical updates — `lang=` / `.lang` / `"lang" in ProjectConfig.__dataclass_fields__`
→ the `language` forms — in: `tests/config/test_config.py` (incl. the kw_only
TypeError match string `"lang"` → `"language"`), `tests/config/test_loader.py`,
`tests/config/test_integration.py`, `tests/config/test_tools_integration.py`,
`tests/config/test_project_cell_contract.py`, `tests/integration/test_parallel_flow.py`,
`test_runtime_isolation.py`, `test_workflow_entity.py`, `test_pipeline_cli.py`,
`test_docker_update_launch_integration.py`, `tests/commands/pipeline/*` (12 files),
`tests/commands/build/test_build_runtime_isolation_integration.py`,
`tests/commands/build/test_build.py`, `tests/build/test_build.py`,
`tests/onboarding/generator/test_generator.py`. Plus a new
`assert "lang" not in ProjectConfig.__dataclass_fields__` in `tests/config/test_config.py`
(the breaking-removal guard). Explicitly NOT renamed: the CLI `--lang` surface
(`tests/commands/test_contract.py` param assertions keep `lang`), the dispatcher
signature tests (`tests/contract/test_dispatcher.py`), and the
`_write_goga_yml(lang=...)` helper params (YAML-writing helpers, not model
references).

**Sufficiency**: the absence check of the plan — no model-field `lang` reference
survives anywhere the model is constructed or read.

---

#### Integration: `tests/integration/test_config_hooks_passthrough.py`

**Setup**: a real project tree in `tmp_path` (config + one CODEMANIFEST cell); the
nine commands invoked via `CliRunner` twice — with no tool packages and with a
forcing tool installed.

**Input**: e.g. `lint`, `config <path>`, `install` (bulk), `usages status`…

**Assertions**:
```
no-tool run: stdout byte-identical to the pre-change baseline snapshot; stderr empty;
             exit codes identical
with-tool run: stdout unchanged vs the no-tool run (except where the effective value
             IS the output — goga config prints the amended value); stderr carries
             exactly the summary lines; .goga/config.yml byte-identical after the run
```

**Sufficiency**: the passthrough and secrecy axes of the plan's checklist — the
authored file is never modified, output contracts hold, values never leak.

## Additional Instructions for the Implementation Agent

- Follow the implementation order of *Entity Dependencies* (catalog → rename → zone
  leaves→root → consumers → tests); the zone's `__init__.py` is written last within
  the zone.
- Relative imports only (`convention`); the zone imports the platform through
  `...hooks` (the facade), never deep platform modules; consumers import
  `ConfigHooks` from `...config.hooks` — the facade `goga/config` is NOT extended
  (distribution D4, Option 2).
- `goga/build/__main__.py`, `goga/commands/usages`, `goga/onboarding`,
  `goga/scaffold`, and the in-container pipeline counterpart stay authored-only —
  do not wire the checkpoint there.
- The delivery call sits INSIDE the existing loader-wrapping try everywhere except
  lint, where it must sit in its own `ValueError` → `ClickException` wrapper so the
  optional-config swallow cannot mask a hard failure.
- Keep the message formats exactly as pinned here (they are asserted by tests): the
  hook-failure line copies the pipeline precedent; the merge failure names tool +
  path + malformedness; the wrapper adds the action; the summary header/line format
  is `config amendments: N applied` / `- <tool> set|forced <path>`.
- The descriptor table in `overlay.py` is hand-written data next to the merge; the
  sync test against `dataclasses.fields(...)` of every model is mandatory (drift
  detection), mirroring the pipeline zone's `_STAGE_FIELDS` stance.
- Do not add a `lang` compat property, alias, or deprecation shim — the rename is a
  clean same-major-release break; `goga config lang` resolving to "Option not found"
  is the intended behavior.
- The zone prints nothing and logs nothing on the happy path; the summary lines are
  data the callers act on.
- After implementation, run the plan's verification checklist verbatim (`goga lint`,
  facade import one-liner, absence sweep, catalog/schema checks, `pytest tests/ -x`,
  `ruff check` over the touched packages, passthrough/merge-algebra/summary/
  uniform-reach checks).
- Apply the recommended `registering-hooks.md` bullet (see *`.usages/` Update*) in
  the same change, so tool authors see the materialization rule.
