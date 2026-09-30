# Plan: `topics-publish-and-tool-config`

Result of compiling the verified design document
(`.goga/history/2026/topics-publish-and-tool-config/design.md`, post design-review with
all 10 approved fixes applied) into ralphex execution tasks. Contract source of truth:
the 11 CODEMANIFEST files already materialized by the apply-architecture stage — they
are **read-only** for every task below, exactly like every `.usages/` file.

---

## Purpose

Implement three features over the existing goga cells, strictly in the architecture
plan's cell order (1→11 of `arch.md`):

1. **`goga topics publish`** — delivery of an existing topic branch to origin as an
   operation of its own (`publish_existing_topic` + `resolve_publication_outcome` +
   `resolve_commit_message` + the `publish` CLI subcommand), with the reshaped
   publication-centric `TopicPublished` / `TopicHooks.emit_published` context emitted
   from all four publication sites.
2. **Tool-config loading standard** — the new `goga/config/tool` cell
   (`load_tool_config`), re-exported by the `goga/config` facade, and the `config`
   injection of `build_injections` in the `tool` command.
3. **Schema validation gate** — the `schema/validate_schema` hard checkpoint
   (`SchemaNode` / `Violation` / `GateVerdict` / `SchemaValidation` /
   `SchemaHooks.validate_schema`) fired by the `schema` routine between the
   amendment walk and serialization, raising one merged `ValueError` rendered by the
   existing `goga schema` handler.

After implementation every changed CODEMANIFEST signature resolves against real code,
every facade exposes its re-exports, and the full suite plus lint are green.

## Context

### Contract Surface

**Entity: `load_tool_config`** (new — Routine)
- Type: `function`
- Declared `location`: `goga/config/tool/loader.py`
- Signature: `load_tool_config(tool: str, filename: str, root: Path | None = None) -> data: object | None`
- Facade obligation: importable from `goga.config.tool` (`__all__ = ["load_tool_config"]`)
  **and** from `goga.config` (re-export block `->load_tool_config: {}`)
- Semantic requirements: read side of the tool-config standard — flat-name guard
  before any filesystem access; path `<root>/.goga/tools/<tool>/<filename>` with
  `filename` verbatim (identical composition to the write side in
  `goga/onboarding/generator/generator.py`); absent file → `None` (the normal state);
  present file → `yaml.safe_load(path.read_text(encoding="utf-8"))` returned **as-is**
  (mapping, list, string, scalar, or `None` for an empty file); no content models, no
  merge, no cache; `root=None` anchors at `Path(".")` (the loaders' project-root
  anchor, exactly as `load_project_config` anchors `./.goga/config.yml`)
- Errors: `ValueError` (non-flat name — before any read); `yaml.YAMLError`,
  `OSError`, `UnicodeDecodeError` (present file failing to parse / read / decode —
  propagated raw; the `tool` command already catches all three)
- Imported dependencies: none (leaf cell); practices `convention` (project file) and
  `yaml` (inline)

**Entity: `resolve_commit_message`** (new — Routine)
- Type: `function`
- Declared `location`: `goga/topics/git/publish.py`
- Signature: `resolve_commit_message(commit: str) -> message: str`
- Facade obligation: importable from `goga.topics.git` — added to the `.publish`
  import block and `__all__` **before** `resolve_commit_tree`
- Semantic requirements: read-only git fact; `git log -1 --pretty=format:%B <commit>`
  via the module's `_run_git` (same invocation discipline as every routine of
  `publish.py`); return `result.stdout` **verbatim** — the stored message
  byte-for-byte, no strip, no reformat. The `format:` form is normative: the bare
  `%B` form appends one extra terminator newline beyond the stored message
  (byte-verified during design review: 30 vs 29 bytes); the `format:` form adds none
- Errors: `subprocess.CalledProcessError` (unresolvable commit — propagated raw, the
  domain boundary renders it exactly as `resolve_ref_commit` does); `OSError` (spawn)
- Practice: the cell's `git` practice for the invocation pattern; `publishing`
  (git zone) documents it for consumers

**Entity: `publish_existing_topic`** (new — Routine)
- Type: `function`
- Declared `location`: `goga/topics/publishing.py`
- Signature: `publish_existing_topic(identifier: str | None, year: str | None = None) -> result: str`
- Facade obligation: importable from `goga.topics` (`__all__`, after `publish_topic`)
- Semantic requirements (contract algorithm, 10 steps — see Task 6 for the full
  verbatim elaboration): resolve the addressee via `resolve_exchange_target`;
  `origin_configured` False → clean error **before any network operation**; own tip
  via `resolve_ref_commit`; echo one stdout line `Fetching origin/<branch>...` then
  `fetch_branch` of the own branch; twin projection after the fetch (absent twin
  reads `None`); classify via `resolve_publication_outcome`; `pushed` → `push_branch`
  of the own branch; `up-to-date`/`remote-ahead` → success with nothing mutated;
  read the twin tip + `resolve_commit_message` **after** the operation; emit
  `topic_published` (every success emits, idempotent outcomes included); return
  exactly one result line naming the outcome kind — `Published topic {year}/{slug} — {outcome}` (D3)
- Requirements: delivery, never history rewriting — no force and no lease under any
  outcome; no confirmation; the working-tree state is irrelevant
- Constraints: do not move, create, or delete any local ref; do not push anything
  but the topic's own branch
- Exceptions: the `publish_topic` wrapper boundary verbatim — `CalledProcessError` →
  `ClickException("git failed: {stderr}")`; `FileNotFoundError` → "git is not
  available:"; `ImportError` → registry assembly; `OSError` → phase-neutral
- Imported dependencies: `resolve_exchange_target`, `fetch_branch`, `push_branch`,
  `is_ancestor`, `resolve_ref_commit`, `origin_configured` (git zone),
  `resolve_commit_message` (new), `TopicIdentity`, `TopicHooks`, `current_year`,
  plus private `_FETCHING_LINE` / `_projection` from `.exchange` (D5 — the
  established private intra-package import precedent)

**Entity: `resolve_publication_outcome`** (new — Routine)
- Type: `function`
- Declared `location`: `goga/topics/publishing.py`
- Signature: `resolve_publication_outcome(own_tip: str, twin_tip: str | None) -> outcome: str`
- Facade obligation: importable from `goga.topics` (`__all__`, after `resolve_propagation`)
- Semantic requirements: the pure four-outcome decision — `twin_tip is None` →
  `"pushed"`; `twin_tip == own_tip` → `"up-to-date"` (equality probe **precedes**
  containment); `is_ancestor(own_tip, twin_tip)` → `"remote-ahead"`
  (`is_ancestor(ancestor, descendant)` argument order — verified against
  `goga/topics/git/exchange.py:74`); otherwise `click.ClickException` naming both
  tips with the manual-git hint (D4): `branch and origin twin diverged — own tip
  {own_tip}, twin tip {twin_tip}; reconcile manually with git, then re-run`
- Requirements: read-only — containment probes only; no mutation, no network

**Entity: `TopicPublished`** (changed — Entity, data)
- Type: `class` (frozen `kw_only` dataclass)
- Declared `location`: `goga/topics/hooks/contexts.py`
- Signature: `TopicPublished(identity: TopicIdentity, remote_branch: str, commit_hash: str, commit_message: str, outcome: str)`
- Facade obligation: already exported by `goga.topics.hooks` — the reshape must not
  change its importability
- Semantic requirements: read-only facts of one completed publication; the five
  publication-centric fields replace the old four-field shape (`todo` removed — a
  field removal, the breaking reshape); address (`topics/topic_published`) and soft
  error class unchanged (the catalog record is untouched)

**Entity: `TopicHooks.emit_published`** (changed — method)
- Type: method of `TopicHooks`
- Declared `location`: `goga/topics/hooks/events.py`
- Signature: `emit_published(self, identity: TopicIdentity, remote_branch: str, commit_hash: str, commit_message: str, outcome: str)`
- Semantic requirements: build the reshaped `TopicPublished` field-for-field; emit
  the unchanged address via `emit_hook_event(_run_registry(), "topics",
  "topic_published", context_for=lambda _tool: context)` — one registry per run
  shared with every other topics checkpoint; fire-and-forget: a failing hook warns
  under the soft class and the walk continues (now an explicit contract Requirement)

**Entity: `SchemaNode`** (new — Entity, data)
- Type: `class` (frozen `kw_only` dataclass)
- Declared `location`: `goga/schema/hooks/facts.py` — placed directly after
  `DependencyFacts`, before the module serves `CellAmendment`'s imports (body order)
- Signature: `SchemaNode(path: str, description: str, types: list[str], usages: list[str], dependencies: list[DependencyFacts], children: list[SchemaNode], tools: dict[str, dict[str, object]])`
- Properties: the seven fields above; `tools` defaults to `field(default_factory=dict)`
  ("empty when no tool contributed"); `children` recursive
- Facade obligation: importable from `goga.schema.hooks`

**Entity: `Violation`** (new — Entity, data)
- Type: `class` (frozen `kw_only` dataclass)
- Declared `location`: `goga/schema/hooks/facts.py` (beside `SchemaNode`)
- Signature: `Violation(tool: str, hook: str, reason: str)`

**Entity: `GateVerdict`** (new — Entity)
- Type: `class` (frozen `kw_only` dataclass)
- Declared `location`: `goga/schema/hooks/facts.py`
- Signature: `GateVerdict(violations: list[Violation])`
- Properties: derived `@property approved -> bool` returning `not self.violations`
  (a derived property, **not** a constructor field)

**Entity: `SchemaValidation`** (new — Entity, the gate's delivered view)
- Type: `class` (**non-frozen** `kw_only` dataclass — the buffer must be writable)
- Declared `location`: `goga/schema/hooks/contexts.py` — **new module**
- Signature: `SchemaValidation(tree: list[SchemaNode])`
- Method: `veto(reason: str)` — assigns `self._veto = reason` (whole replacement; no
  hook identity recorded; empty or whitespace-only reason stored as given)
- Field: `_veto: str | None = field(init=False, default=None, repr=False)`
- Semantic requirements: `wrap_context` proxies block attribute assignment while
  calls pass through — `context.tree = ...` raises, `context.veto(...)` works (the
  `BuildValidation` mechanism verbatim, reference `goga/build/hooks/contexts.py:26`)
- Facade obligation: importable from `goga.schema.hooks`

**Entity: `SchemaHooks.validate_schema`** (new — method)
- Type: method of `SchemaHooks`
- Declared `location`: `goga/schema/hooks/events.py`
- Signature: `validate_schema(tree: list[SchemaNode]) -> verdict: GateVerdict`
- Semantic requirements (contract algorithm, 6 steps — see Task 11): shared
  `_ensure_registry()` with `amend_cell` (one enumeration per run); resolve
  `schema/validate_schema` against `declared_actions` (missing →
  `ValueError("unknown hook action: schema.validate_schema")`); walk subscriptions per
  tool in enumeration order — no filtering by invitation; per tool a **deep fresh
  copy** of the tree (`_copy_tree`, D6), `wrap_context` proxy, per-hook veto-buffer
  snapshot for attribution; a raising hook → crash record `str(reason)` (never a
  traceback), break that tool's remaining hooks, **walk continues** with the next
  tool; crash overrides the buffered veto; exactly one `Violation` per non-approving
  tool; no subscriptions → the empty approved verdict
- Requirements: every subscribed tool's hooks run — no early stop; the gate modifies
  nothing
- Constraints: do not stop the walk at the first veto or crash; do not skip a
  subscriber; do not read repositories or the filesystem; do not print — the verdict
  is data

**Entity: `topics.publish`** (new — CLI subcommand)
- Type: method/callback on the `topics` group
- Declared `location`: `goga/commands/topics/topics.py` — registered **between
  `update` and `propagate`** (the CODEMANIFEST body order)
- Signature: `publish(identifier: str | None = None) -> exit_code: int`
- Semantic requirements: optional `IDENTIFIER` positional; delegate to
  `publish_existing_topic(identifier, scope.year)`; echo the single result line;
  exit 0 on all three success kinds (`pushed`, `up-to-date`, `remote-ahead`), 1 on
  error; a `ClickException` renders via click's standard handler
- Constraints: do not read the configuration (`_topics_section` is never called); do
  not ask a confirmation; command-callback docstring carries user-facing help only
  (no Args/Returns/Raises — CLI callback rules of `convention`)

**Entity: catalog record `schema/validate_schema`** (new — data)
- Type: one additive `Action` record
- Declared `location`: `goga/hooks/catalog/catalog.py`
- Semantic requirements: `Action(domain="schema", name="validate_schema",
  error_class="hard")` directly after the `amend_cell` line; `declared_actions()`
  sorts by `(domain, name)` so the two schema actions stay adjacent; additive only —
  no other record rewritten; the catalog stays the single source (envelope
  validation and emission resolution accept the new address immediately)

**Changed entities (behavioral deltas, no new signatures):**
- `publish_topic` (`goga/topics/publishing.py`, step 9) — the emission call is
  re-signed to the reshaped five-fact call: `emit_published(identity,
  remote_branch=f"origin/{branch_name}", commit_hash=commit, commit_message=applied,
  outcome="pushed")` — the built commit's facts are in hand, no
  `resolve_commit_message` here; rollback paths still fire nothing
- `update_topic` (`goga/topics/updating.py`, step 9) — after a successful
  `_publish_refreshed_branch` and before `_emit_updated`: new private helper
  `_emit_published_delivery(target, year)` reads `resolve_ref_commit(f"origin/{target.branch}")`
  and emits with `outcome="pushed"`; the `already-current` early return emits only
  `topic_updated` with `published=False`; a failed publish push raises before the
  emission (the confirmed update stands)
- `execute_propagation` (`goga/topics/propagating.py`, step 6) — in `_deliver`,
  between `_plant_and_push` and `_emit_propagated`: new private helper
  `_emit_published_delivery(plan, base, delivery)` computing the pushed branch name
  exactly as `_plant_and_push` spelled the refspec (`remote = base.local_branch if
  base.local_branch is not None else plan.base_ref.removeprefix("origin/")`) and
  emitting with the delivery commit in hand; a rejected first attempt raises
  `_RejectedDeliveryError` before the emission point, so the retry cycle emits
  exactly once; `_nothing_to_do` emits no publication
- `build_injections` (`goga/commands/tool/tool.py`) — re-signed
  `build_injections(main: Callable, tool: str) -> injections: dict[str, object]`;
  `_OFFERED_INJECTIONS` becomes `dict[str, Callable[[str], object]]` with the
  `config` branch (D8); the command passes the resolved `name` and its injection-load
  failure message becomes `Failed to load project AST or tool config: {exc}` (D9)
- `schema` (`goga/schema/schema.py`) — algorithm renumbered to 7 steps with the gate
  as step 6: `verdict = hooks.validate_schema([_to_schema_node(n) for n in result])`;
  `not verdict.approved` → `raise ValueError(merged)` (D11); step 7 serializes. The
  early `return "[]"` for an emptied tree stays (D1). Approved verdict → byte-identical output
- `declared_actions` — the one additive record above
- `goga/commands/schema` — **no code change** (verified during design): the merged
  `ValueError` is caught by the existing `except Exception` handler → stderr + exit 1

### Re-exports

- `->load_tool_config: {}` in `goga/config/CODEMANIFEST` — source: `Imports` entry
  `goga/config/tool`; facade obligation: `from goga.config import load_tool_config`
  must resolve; hierarchy constraint satisfied (the tool subpackage sits below the
  facade). Facade change: `from .tool.loader import load_tool_config` plus the
  `"load_tool_config"` entry in `__all__` **after** `"load_project_config"`
- `goga/topics/git` facade — `resolve_commit_message` added to the `.publish` import
  block and `__all__` (before `resolve_commit_tree`)
- `goga/topics` facade — `from .publishing import publish_existing_topic,
  publish_topic, resolve_publication_outcome`; `__all__` gains
  `publish_existing_topic` (before `publish_topic`) and `resolve_publication_outcome`
  (after `resolve_propagation`)
- `goga/schema/hooks` facade — imports `.contexts.SchemaValidation`; `.facts` gains
  `GateVerdict, SchemaNode, Violation`; `__all__` becomes
  `["CellAmendment", "CellFacts", "DependencyFacts", "GateVerdict", "SchemaHooks",
  "SchemaNode", "SchemaValidation", "ToolContribution",
  "merge_cell_contributions"]`; the module docstring lists the gate surface

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — Python 3.10+ rules: relative
  intra-package imports, `kw_only` dataclasses, Google docstrings (CLI callbacks
  render help: no Args/Returns/Raises), test layout `tests/<pkg>/test_<module>.py`,
  `tmp_path` for file I/O, mocked subprocess, handler-direct CLI tests. Validation
  commands table: `pytest tests/ -x`, `ruff check <src>/`,
  `python -c "from package import Entity"`. Relevant to **every** task.
- `yaml` (inline, `goga/config/tool` CODEMANIFEST) — `yaml.safe_load()` on the file
  text; PyYAML requirement. Used by Task 3 step "parse".
- `click` (`.goga/usages/cooks/click.md`) — command/argument/echo/exit mechanics for
  Tasks 13–14.
- `git` (git-cell invocation practice) — `_run_git` invocation discipline for Task 2.

### Imported Usages

- `loading` ← `goga/ast/.usages/loading.md` — `AST(".")` at the dispatcher's CWD +
  `.load()`; errors pass through. Task 13 (unchanged `_build_ast`).
- `tool-configuration` ← `goga/config/.usages/tool-configuration.md` — the consumer
  contract of `load_tool_config` (path standard, raw passthrough, absence-None, flat
  names, `root` override). Task 13: `load_tool_config(tool, "config.yml")` — verbatim
  file name, no suffix logic.
- `exchanging` ← `goga/topics/git/.usages/exchanging.md` — `fetch_branch` (single
  sanctioned fetch of the own branch), `is_ancestor(own_tip, twin_tip)` for the
  strict-ahead probe; the reporting line belongs to the caller (`publishing.py`
  echoes it). Task 6.
- `refs-and-switching` ← `goga/topics/git/.usages/refs-and-switching.md` —
  `resolve_ref_commit` for the own tip and the twin projection; revision-as-git-
  resolves-it, read-only. Task 6.
- `publishing` (git zone) ← `goga/topics/git/.usages/publishing.md` —
  `origin_configured` probe before anything; `push_branch(branch)` exactly the named
  branch, upstream-bound; the "Reading publication facts" section documents
  `resolve_commit_message`. Tasks 2 and 6.
- `checkpoints` (topics zone) ← `goga/topics/hooks/.usages/checkpoints.md` — one
  `TopicHooks()` per emission site sharing the run registry; facts from the
  operation's own data; fire-and-forget under the soft class. Tasks 6, 7, 8.
- `declaring-actions` ← `goga/hooks/.usages/declaring-actions.md` — the unchanged
  `emit_hook_event` form with `context_for=lambda _tool: context`; the read-only
  context carries no buffer, one shared instance is lawful. Task 5.
- `per-tool-delivery` ← `goga/hooks/.usages/per-tool-delivery.md` — the loop skeleton
  (group per tool, `wrap_context`, `build_hook_arguments`, `self_context`) with the
  gate's recorded refinement: run to completion, collect vetoes, no contribution
  commit; per-hook attribution by buffer snapshot. Task 11.
- `registering-hooks` ← `goga/hooks/.usages/registering-hooks.md` — hooks declare
  `context` (and optionally `self`); undeclared names receive nothing;
  `build_hook_arguments` is the single projection. Task 10.
- `publishing` (topics domain) ← already imported by `goga/commands/topics`; now also
  referenced by the `publish` subcommand annotation. Task 14.

### Local Usages

All `.usages/` files below were materialized by the apply-architecture stage and
verified current by the design (and its review). **No creation or modification tasks
exist for them — they are read-only context for the implementation agent.**

- `goga/config/.usages/tool-configuration.md` — consumer doc of `load_tool_config`;
  status: current (new file created by the apply stage)
- `goga/commands/tool/.usages/tool.md` — `config` injection row, example, opt-in
  bullet, D9 exit-code bullet; current
- `goga/commands/topics/.usages/topics-command.md` — `publish` section + audience;
  current
- `goga/commands/schema/.usages/schema.md` — "Validation failures" section; current
- `goga/schema/.usages/registering-hooks.md` — two-action intro, events-table row,
  "The validation view" section; current (post D2 fix)
- `goga/schema/hooks/.usages/checkpoints.md` — "Validate the final tree" section;
  current
- `goga/topics/.usages/publishing.md`, `update.md`, `propagate.md`,
  `registering-hooks.md` — publication sections; current
- `goga/topics/git/.usages/publishing.md` — "Reading publication facts" section;
  current
- `goga/topics/hooks/.usages/checkpoints.md` — reshaped `emit_published` example and
  facts; current

### External Dependencies

- `click` — commands, `ClickException` clean errors, `CliRunner` in tests
- `PyYAML` (`yaml.safe_load`) — Task 3
- `subprocess` (via the git zone's `_run_git`), `pathlib.Path` — Tasks 2, 3, 6
- `pytest` + `unittest.mock.patch` — all test tasks; shared fixtures
  `pin_package_environment` / `install_tool_package`
  (`tests/hooks/conftest.py`, re-exported by `tests/schema/hooks/conftest.py` and
  defined in `tests/topics/hooks/conftest.py`)
- `goga/build/hooks` zone — the reference implementation of the gate primitives
  (`BuildValidation` at `goga/build/hooks/contexts.py:26`, `Violation` at
  `goga/build/hooks/facts.py:136`): copy its mechanics, do not redesign them

### Entity Interaction and Data Flow (verbatim from the design)

```
                       goga topics publish [IDENTIFIER]
                                     │
                     goga/commands/topics.topics.publish
                                     │ publish_existing_topic(identifier, scope.year)
                                     ▼
        goga/topics.publishing.publish_existing_topic ──── resolve_exchange_target ──► (exchange.py)
              │            │            │            │                                   │
              │            │            │            │ origin_configured                 ▼
              │            │            │            └────────────► goga/topics/git.publish
              │            │            │ resolve_ref_commit / fetch_branch / push_branch
              │            │            │ is_ancestor                                       │
              │            │            ▼                                                   │
              │            │     resolve_publication_outcome(own_tip, twin_tip)             │
              │            │                                                                   │
              │            └────────── resolve_commit_message(twin_tip) ◄────────────────────┘
              ▼
        TopicHooks.emit_published(identity, remote_branch, commit_hash,
                                  commit_message, outcome)
              │  builds TopicPublished, emits topics/topic_published (soft)
              ▼
        goga/hooks platform (registry, wrap_context, build_hook_arguments)


  goga tool <name>                      goga schema / schema()
  ─────────────                         ────────────────────────────
  commands/tool.tool(name)              schema.schema(cells, max_depth, depends_on)
    │ build_injections(main_fn, name)     │ walk cells ── SchemaHooks.amend_cell (per cell)
    │   ├─ ast  → AST(".").load()         │ build SchemaNode projection of final dict tree
    │   └─ config → load_tool_config(     │ SchemaHooks.validate_schema(nodes)
    │        name, "config.yml")          │   ├─ approved → json.dumps (byte-identical)
    │        └► goga/config/tool.loader   │   └─ violations → ValueError(merged) →
    │            (re-exported by            │       commands/schema: stderr, exit 1
    │             goga/config facade)      │ SchemaValidation view per tool:
    ▼                                     │   context.tree (fresh copy) + context.veto(reason)
  main(argv, **injections)                ▼
```

**Data flows:**

1. **Publish command flow** — CLI `IDENTIFIER` (or None) + group `--year` →
   `publish(scope, identifier)` → `publish_existing_topic(identifier, year)` →
   `ExchangeTarget(topic, branch, current)` → own tip hash + twin tip hash (or None) →
   outcome kind string → (pushed only) `push_branch` → twin tip + message →
   `TopicIdentity` + five facts → `TopicPublished` → hooks platform → one result line →
   `click.echo` + `exit(0)`.
2. **Config injection flow** — dispatched `name` → `build_injections(main, name)` →
   signature projection over `{ast, config}` → lazily: `AST` instance and/or raw
   `object | None` from `load_tool_config(name, "config.yml")` → `main(list(args),
   **injections)`.
3. **Gate flow** — final filtered dict tree (six fields + committed `tools` overlays) →
   recursive `SchemaNode` projection → per-tool `SchemaValidation` (fresh tree copy,
   private veto buffer) → hook calls via `wrap_context`/`build_hook_arguments` →
   `Violation(tool, hook, reason)` per vetoing/crashing tool → `GateVerdict` →
   approved: `json.dumps`; not approved: `ValueError` → CLI stderr + exit 1.
4. **Publication emission at the three existing sites** — `publish_topic` (built commit
   facts in hand), `update_topic` (post-push twin read), `execute_propagation` (delivery
   commit in hand) → the same reshaped `emit_published`.

**Entity dependencies** — initialization order for a run is the plan's cell order
(leaves first): `goga/hooks/catalog` → `goga/topics/git` → `goga/config/tool` →
`goga/config` → `goga/topics/hooks` → `goga/topics` → `goga/schema/hooks` →
`goga/schema` → `goga/commands/tool` → `goga/commands/topics` →
`goga/commands/schema`. `SchemaHooks` shares one lazily-built `HookRegistry` between
`amend_cell` and `validate_schema`; `TopicHooks` shares the module-level run registry
across every emission of the process.

## Facts

- Language: Python (`goga config language` = python); Python 3.10 compatibility —
  `from __future__ import annotations` in new modules; `X | None` annotations fine
  under it; `kw_only=True` / `frozen=True` per the convention
- `goga lint` — 82 cells, 0 errors (contracts are consistent; every import resolves)
- Cell implementation order (leaves first): `goga/hooks/catalog` → `goga/topics/git`
  → `goga/config/tool` → `goga/config` → `goga/topics/hooks` → `goga/topics` →
  `goga/schema/hooks` → `goga/schema` → `goga/commands/tool` →
  `goga/commands/topics` → `goga/commands/schema` (no change)
- The single new dependency edge of the plan: `goga/commands/tool → goga/config`
  (acyclic — the config subtree imports no command layer)
- `SchemaHooks` shares one lazily-built `HookRegistry` between `amend_cell` and
  `validate_schema`; `TopicHooks` shares the module-level run registry across every
  emission of the process
- Existing private-import precedents (D5): `publishing.py` imports `_BOARD_HINT`
  from `.creation`; `schema.py` will import `_copy_json` from
  `.hooks.events` (the hooks zone never imports the domain — no cycle)
- `_FETCHING_LINE` lives at `goga/topics/exchange.py:45` and `_projection` at
  `goga/topics/exchange.py:484`; `_publish_refreshed_branch` is at
  `goga/topics/updating.py:417`; the current (old-shape) `emit_published` call in
  `_publish_topic` is at `goga/topics/publishing.py:248`
- Existing tests that pin the old shapes and MUST be updated as part of the
  corresponding tasks (they fail the moment the contract changes — expected):
  - `tests/hooks/catalog/test_catalog.py::test_schema_amend_cell_record_present`
    asserts `schema == [("amend_cell", "hard")]` and `len(triples) ==
    len(pre_existing) + 1` — gains `validate_schema` (Task 1)
  - `tests/topics/hooks/test_contexts.py` — the declared field-set table carries the
    old four-field `TopicPublished` (Task 5)
  - `tests/topics/hooks/test_events.py` — signature data for `emit_published`
    (line ~73) and old-shape emission assertions (Task 5)
  - `tests/topics/test_publishing.py` / `test_updating.py` / `test_propagating.py` —
    any assertion touching the publication emission or the catalog-dependent
    enumerations is re-pinned to the new shapes (Tasks 6–8)
- `--pretty=format:%B` is byte-exact (29 bytes for the sample message) where bare
  `--pretty=%B` appends one terminator newline (30 bytes) — verified empirically in a
  scratch git repository during design review (R1)
- The `goga schema` failure handler already renders any exception as stderr + exit 1
  with stdout empty — the merged gate `ValueError` needs no command change
- No new logging, no caching, no threads/async anywhere in the change set; the zones
  stay silent (`Do not print — the caller owns all output`)

## Gap Analysis

Verified against the working tree (branch `topics-publish-and-tool-config`, CODEMANIFEST
and `.usages/` changes already applied by the apply-architecture stage):

- **Missing contract entities**:
  - `goga/config/tool/` contains only `CODEMANIFEST` — `loader.py` and the package
    `__init__.py` facade do not exist
  - `resolve_commit_message` absent from `goga/topics/git/publish.py`
  - `publish_existing_topic` / `resolve_publication_outcome` absent from
    `goga/topics/publishing.py`
  - `SchemaNode` / `Violation` / `GateVerdict` absent from `goga/schema/hooks/facts.py`;
    `goga/schema/hooks/contexts.py` does not exist; `validate_schema`,
    `_copy_tree`, `_copy_json` absent from `goga/schema/hooks/events.py`
  - `_to_schema_node` and the gate step absent from `goga/schema/schema.py`
  - `publish` subcommand absent from `goga/commands/topics/topics.py`
  - catalog record `schema/validate_schema` absent from
    `goga/hooks/catalog/catalog.py`
- **Missing facade exposure**:
  - `goga/config/__init__.py` — no `load_tool_config` (import + `__all__`)
  - `goga/topics/__init__.py` — imports only `publish_topic` from `.publishing`
  - `goga/topics/git/__init__.py` — no `resolve_commit_message`
  - `goga/schema/hooks/__init__.py` — `__all__` lacks the five gate names
- **Incorrect `location` placement**: none — all target files exist at their
  contracted locations except the two new ones (`goga/config/tool/loader.py`,
  `goga/schema/hooks/contexts.py`), which the tasks create
- **API mismatches**:
  - `TopicPublished` carries the old four-field shape (`identity`, `commit_message`,
    `commit_hash`, `todo`) at `goga/topics/hooks/contexts.py:49`
  - `emit_published(self, identity, commit_message, commit_hash, todo)` at
    `goga/topics/hooks/events.py:404`
  - `build_injections(main: Callable)` with
    `_OFFERED_INJECTIONS: dict[str, Callable[[], object]] = {"ast": _build_ast}` at
    `goga/commands/tool/tool.py:42-45`
- **Behavioral mismatches**:
  - `_publish_topic` emits the old shape (`publishing.py:248`)
  - `update_topic` / `execute_propagation` emit no publication
  - `schema` routine returns `json.dumps` directly after the amendment walk
    (`goga/schema/schema.py:204`), early `return "[]"` at line 182 (stays)
- **Existing code that can be reused** (do not reimplement):
  - `resolve_exchange_target`, `fetch_branch`, `push_branch`, `is_ancestor`,
    `resolve_ref_commit`, `origin_configured` — the git/exchange zones, as-is
  - `_FETCHING_LINE`, `_projection` from `.exchange` (D5)
  - `emit_hook_event`, `wrap_context`, `build_hook_arguments`, `HookRegistry`,
    `declared_actions` — the hooks platform, as-is
  - `goga/build/hooks` gate mechanics as the copy source for the veto buffer,
    attribution snapshot, crash override
  - the `_wire_*` domain-mock pattern of `tests/topics/test_updating.py` and the
    `pin_package_environment` / `install_tool_package` fixtures
- **Test coverage gaps**: `tests/config/tool/` does not exist; none of the 42 design
  test scenarios exist; the old-shape tests listed under Facts must be re-pinned
- **Missing visibility in workspace or git**: the CODEMANIFEST/`.usages` changes are
  already staged in the working tree (modified, untracked `goga/config/tool/` and
  `goga/config/.usages/tool-configuration.md`) — no further contract edits happen

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).
>
> **Read-only contract**: every `CODEMANIFEST` and every `.usages/` file is final. If
> implementation does not match the contract, fix the implementation — never the
> contract. Any perceived contract gap is escalated, not patched in code.

### Task 1: Catalog record `schema/validate_schema` (goga/hooks/catalog)

The `goga/hooks/catalog` cell is the single source of hook addresses. This task adds
the one additive record the schema gate resolves against — it must exist before the
schema zone (Tasks 9–12) can resolve the address. Contract entity: the
`declared_actions` Requirements gain `Action(domain="schema", name="validate_schema",
error_class="hard")` — walk-to-completion, one violation per tool. The record goes
directly after the `amend_cell` line in `_DECLARED_ACTIONS`
(`goga/hooks/catalog/catalog.py`, the block around lines 41–66); nothing else in the
module changes (the catalog is data). `declared_actions()` already sorts by
`(domain, name)`, so the two schema actions stay adjacent — no sort change.

**Usages relevant to this task:**
- `convention`: docstring/test conventions; the module docstring stays unchanged.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: in `tests/hooks/catalog/test_catalog.py`, extend
  `test_schema_amend_cell_record_present` (it currently asserts
  `schema == [("amend_cell", "hard")]` and `len(triples) == len(pre_existing) + 1` —
  both break with the new record, which is the expected failure): assert
  `Action(domain="schema", name="validate_schema", error_class="hard") in records`;
  `schema == [("amend_cell", "hard"), ("validate_schema", "hard")]`; the frozen
  `pre_existing` list stays valid (the whole catalog stays pinned against it); the
  count becomes `len(pre_existing) + 2`; the `(domain, name)` ordering assertion
  stays. Add the docstring sentence: `validate_schema` is the hard verdict-collecting
  gate of the schema domain (walk-to-completion, one violation per tool)
- [x] **Code**: add `Action(domain="schema", name="validate_schema", error_class="hard"),`
  directly after the `Action(domain="schema", name="amend_cell", error_class="hard"),`
  line in `_DECLARED_ACTIONS` — no other edit to the module
- [x] **Interface verification**: `pytest tests/hooks/catalog/test_catalog.py -v` —
  all pass
- [x] **Logic tests**: confirm via the existing catalog suite that no other domain
  block changed (`pytest tests/hooks/ -k catalog -v`); the emission-resolution and
  envelope-validation behavior over the new address is exercised end-to-end by the
  gate tests of Tasks 11–12
- [x] **Debugging**: `pytest tests/hooks/ -x` — fix implementation code until all
  tests pass (do NOT fix test code beyond the re-pin above)
- [x] **Contract re-verification**: `python -c "from goga.hooks.catalog import
  declared_actions; assert any(a.domain == 'schema' and a.name == 'validate_schema'
  for a in declared_actions())"`
- [x] **Lint**: `ruff check goga/hooks/catalog/` — fix formatting if necessary

### Task 2: `resolve_commit_message` routine (goga/topics/git)

The git access zone gains one read-only routine: the commit message of one commit as
git stores it. Contract entity: `resolve_commit_message(commit: str) -> message: str`
at `location` `publish.py`, added to the module's public functions (it becomes the
read-side sibling of `resolve_ref_commit`). Facade: add to the `.publish` import
block and `__all__` of `goga/topics/git/__init__.py` **before** `resolve_commit_tree`
(the current `__all__` entry sits at line ~83). The routine applies the cell's `git`
practice for the invocation pattern, exactly like every routine of the cell (R10).
`goga/topics` (Task 6) consumes it for every publication emission.

Design-verified algorithm (D10 — the `format:` form is normative and byte-verified):

```
1. result = _run_git(["git", "log", "-1", "--pretty=format:%B", commit])
2. RETURN result.stdout        # verbatim, byte-for-byte as stored (format: adds no
                              # terminator newline; the bare %B form would add one)
```

Errors: `subprocess.CalledProcessError` (unresolvable commit — propagated raw, git's
reason rides in `stderr`; the domain boundary renders it); `OSError` (spawn). Edge
cases: multi-line messages preserved byte-for-byte; works on any resolvable revision
(hashes only by contract usage). `_run_git` (at `goga/topics/git/publish.py:452`)
already carries the module's `LC_ALL=C`, `GIT_TERMINAL_PROMPT=0`, devnull-stdin env.

**Usages relevant to this task:**
- `convention`: Google docstring carrying the CODEMANIFEST annotation
  (Algorithm/Requirements/Constraints as sections); mocked-subprocess tests.
- `publishing` (git zone, `goga/topics/git/.usages/publishing.md`): the "Reading
  publication facts" section documents this routine for consumers — match its wording.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: in `tests/topics/git/test_publish.py` — assert
  `resolve_commit_message` is importable from `goga.topics.git` (facade), present in
  `__all__`, and has signature `(commit: str) -> str` (expected to fail before
  implementation)
- [x] **Code**: implement `resolve_commit_message` in `goga/topics/git/publish.py`
  per the algorithm above — `_run_git` invocation, `result.stdout` returned verbatim,
  no strip, no reformat
- [x] **Code**: add the facade re-export in `goga/topics/git/__init__.py` — the
  `.publish` import block and `__all__`, before `resolve_commit_tree`
- [x] **Interface verification**: `python -c "from goga.topics.git import
  resolve_commit_message"` and `pytest tests/topics/git/test_publish.py -v`
- [x] **Logic tests**: in `tests/topics/git/test_publish.py`:
  - `test_resolve_commit_message_verbatim` — Setup:
    `mock.patch("goga.topics.git.publish._run_git")` returning
    `CompletedProcess(stdout="Create topic 'feat-x'\n")`; Input:
    `resolve_commit_message("abc123")`; Assertions:
    `result == "Create topic 'feat-x'\n"` **and**
    `mock.assert_called_once_with(["git", "log", "-1", "--pretty=format:%B", "abc123"])`
    (the exact plumbing invocation; the trailing newline is the stored one because
    `format:` adds none)
  - `test_resolve_commit_message_unresolvable_commit` (negative) — Setup: `_run_git`
    mocked to raise `subprocess.CalledProcessError(128, "git", stderr="fatal: bad
    object")`; Assertions: `pytest.raises(subprocess.CalledProcessError)` — the
    caller wraps
- [x] **Debugging**: `pytest tests/topics/git/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade import resolves; the routine is read-only
  (a `log` query mutates nothing); docstring carries the annotation
- [x] **Lint**: `ruff check goga/topics/git/` — fix formatting if necessary

### Task 3: New cell `goga/config/tool` — `load_tool_config` (loader + package facade)

The new leaf cell owns the read side of the tool-config standard. The cell directory
`goga/config/tool/` exists with its `CODEMANIFEST` only — this task creates the
implementation and the package facade. Contract entity:
`load_tool_config(tool: str, filename: str, root: Path | None = None) -> data: object | None`
at `location` `loader.py`. Practices: `convention` (project file) and `yaml`
(inline). Python 3.10 compatibility: `from __future__ import annotations`.

Design-verified algorithm (guard before any filesystem access; path composition
identical to the write side `goga/onboarding/generator/generator.py`:
`Path(".goga") / "tools" / tool`):

```
1. GUARD filename: empty, ".", "..", or containing "/" or "\\"
   → raise ValueError(f"tool config file name must be a flat segment: {filename!r}")
2. base = root if root is not None else Path(".")        # the loaders' project-root anchor
   path = base / ".goga" / "tools" / tool / filename     # filename verbatim
3. IF NOT path.exists() → return None                    # absence is the normal state
4. RETURN yaml.safe_load(path.read_text(encoding="utf-8"))  # raw value, as parsed
```

Errors: `ValueError` (non-flat name — before any read); `yaml.YAMLError` (present
file fails to parse — propagated raw; interpreting is the consumer's job); `OSError`
(unreadable present file — propagated); `UnicodeDecodeError` (a `ValueError`
subclass — present file not decodable as UTF-8; propagated raw, never a silent
fallback). Edge cases: empty YAML file → `yaml.safe_load` yields `None` → returned
as-is; `tool` is never validated (platform identity); repeated calls re-read (no
cache); `root` override serves tests with a prepared tree.

Package facade `goga/config/tool/__init__.py`: module docstring (zone description),
`from .loader import load_tool_config`, `__all__ = ["load_tool_config"]`.

**Usages relevant to this task:**
- `convention`: `kw_only`/docstring rules, relative imports, `tmp_path` file I/O
  tests, test layout `tests/config/tool/test_loader.py` (+ `__init__.py`).
- `yaml` (inline practice): one `yaml.safe_load(path.read_text(encoding="utf-8"))`,
  result returned as-is — the project's YAML baseline (same as the home/project
  loaders).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/config/tool/__init__.py` and
  `tests/config/tool/test_loader.py` — assert `load_tool_config` is importable from
  `goga.config.tool`, in its `__all__`, with signature
  `(tool: str, filename: str, root: Path | None = None) -> object | None` (expected
  to fail before implementation)
- [x] **Code**: create `goga/config/tool/loader.py` per the algorithm above —
  flat-name guard first, `Path(".")` anchor, `path.exists()` → `None`,
  `yaml.safe_load` passthrough; docstring carries the CODEMANIFEST annotation
  (Algorithm/Requirements/Constraints)
- [x] **Code**: create `goga/config/tool/__init__.py` — module docstring,
  `from .loader import load_tool_config`, `__all__ = ["load_tool_config"]`
- [x] **Interface verification**: `python -c "from goga.config.tool import
  load_tool_config"` and `pytest tests/config/tool/test_loader.py -v`
- [x] **Logic tests**: in `tests/config/tool/test_loader.py`:
  - `test_load_tool_config_returns_raw_mapping` — Setup: `tmp_path` with
    `.goga/tools/coverage/config.yml` written as `threshold: 10\nname: cov\n`;
    Input: `load_tool_config("coverage", "config.yml", root=tmp_path)`; Assertions:
    `result == {"threshold": 10, "name": "cov"}` and `isinstance(result, dict)`
  - `test_load_tool_config_raw_value_kinds` (parametrized) — `list.yml` = `- a\n- b\n`
    → `["a", "b"]`; `str.yml` = `just a name\n` → `"just a name"`; `empty.yml` = ``
    → `None` (exact values)
  - `test_load_tool_config_absent_file_returns_none` — Setup: `tmp_path` containing
    `.goga/` but no `tools/` at all; Assertions: `result is None`, no exception
  - `test_load_tool_config_rejects_non_flat_names` (parametrized, negative) —
    Input names `["", ".", "..", "a/b", "a\\b", "config.yml/../../x"]`;
    Assertions: `pytest.raises(ValueError, match="flat segment")` for every case and
    the filename appears in the message (guard fires before `exists()` — assert with
    a nonexistent root)
  - `test_load_tool_config_rereads_no_cache` (edge) — `config.yml` = `k: 1`, read,
    rewrite to `k: 2`, read again; Assertions: first `{"k": 1}`, second `{"k": 2}`
  - `test_load_tool_config_root_defaults_to_cwd` (edge) —
    `monkeypatch.chdir(tmp_path)` with the tree under the cwd; Input:
    `load_tool_config("coverage", "config.yml")` (root omitted); Assertions: returns
    the parsed mapping — the `Path(".")` anchor behaves exactly as
    `load_project_config`'s
- [x] **Debugging**: `pytest tests/config/ -x` — fix implementation code until all
  tests pass (do NOT fix test code)
- [x] **Contract re-verification**: no content decision at any step (no `isinstance`
  checks, no models, no merge, no cache); error precedes every filesystem access
- [x] **Lint**: `ruff check goga/config/tool/ tests/config/tool/` — fix formatting if
  necessary

### Task 4: `goga/config` facade re-export (infrastructure)

The `goga/config` facade cell embeds the new type: the contract's re-export block
`->load_tool_config: {}` over the `Imports` entry pointing at `goga/config/tool`.
Facade obligation: `from goga.config import load_tool_config` must resolve. Current
state: `goga/config/__init__.py` (fully read in the design) ends its import block
with `from .project.loader import load_project_config` and its `__all__` with
`"load_home_config"`, `"load_project_config"`, `"resolve_project_name"`. This is the
facade-only task of the cell — no behavioral code.

**Usages relevant to this task:**
- `convention`: facade assembly style — alphabetical `__all__`, one import line per
  source module.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Add `from .tool.loader import load_tool_config` to
  `goga/config/__init__.py` (after the `.project.loader` import)
- [x] Add `"load_tool_config"` to `__all__` **after** `"load_project_config"`
- [x] Add `test_config_facade_reexports_load_tool_config` to
  `tests/config/test_config.py` (import-only): Assertions:
  `callable(load_tool_config)`;
  `"load_tool_config" in goga.config.__all__`;
  `load_tool_config is goga.config.tool.load_tool_config`
  (also re-pinned the facade-count assertion 17 → 18 — the additive entry
  breaks the old pin, the expected failure)
- [x] Verify facade accessibility: `python -c "from goga.config import
  load_tool_config"`
- [x] Lint: `ruff check goga/config/` — fix formatting if necessary

### Task 5: Reshape `TopicPublished` and re-sign `emit_published` (goga/topics/hooks)

The topics hooks zone delivers the reshaped publication context. Contract entities:
`TopicPublished(identity: TopicIdentity, remote_branch: str, commit_hash: str,
commit_message: str, outcome: str)` at `contexts.py` (frozen `kw_only` dataclass —
the five publication-centric fields; `todo` removed, the breaking reshape) and
`TopicHooks.emit_published(self, identity, remote_branch, commit_hash,
commit_message, outcome)` at `events.py` (address `topics/topic_published` and soft
error class unchanged — the catalog record is untouched). The constructor, the
signature, and the emission parameters must match field-for-field. Emission:
`emit_hook_event(_run_registry(), "topics", "topic_published", context_for=lambda
_tool: context)` — one registry per run shared with every other topics checkpoint;
fire-and-forget: a failing hook warns under the soft class and the walk continues
(now an explicit Requirement of the method).

Replacement dataclass (design-verbatim):

```python
@dataclass(frozen=True, kw_only=True)
class TopicPublished:
    """The read-only context of the publication notification — the delivery facts of one completed publication."""
    identity: TopicIdentity
    remote_branch: str
    commit_hash: str
    commit_message: str
    outcome: str
```

**Usages relevant to this task:**
- `convention`: `kw_only` frozen dataclasses; Google docstrings; mirrored test
  layout.
- `declaring-actions` (`goga/hooks/.usages/declaring-actions.md`): the unchanged
  `emit_hook_event` form with `context_for=lambda _tool: context` — the read-only
  context carries no buffer, one shared instance is lawful.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/topics/hooks/test_contexts.py` — update the
  declared field-set table (currently the old
  `{"identity", "commit_message", "commit_hash", "todo"}` block at line ~44) to the
  five-field shape with types
  `{"identity": TopicIdentity, "remote_branch": str, "commit_hash": str,
  "commit_message": str, "outcome": str}`; in `tests/topics/hooks/test_events.py` —
  update the `emit_published` signature data (line ~73) and every old-shape emission
  assertion (expected to fail before implementation)
- [ ] **Code**: replace the `TopicPublished` dataclass in
  `goga/topics/hooks/contexts.py` with the five-field shape above; docstring carries
  the contract annotations (publication-centric semantics, read-only Requirement)
- [ ] **Code**: re-sign `emit_published` in `goga/topics/hooks/events.py` to
  `(self, identity: TopicIdentity, remote_branch: str, commit_hash: str,
  commit_message: str, outcome: str) -> None`; build the context field-for-field;
  emit the unchanged address; docstring gains the soft-failure Requirement
- [ ] **Interface verification**: `pytest tests/topics/hooks/ -v` — the updated
  contract tests pass
- [ ] **Logic tests**: `test_emit_published_builds_context_and_emits_address` in
  `tests/topics/hooks/test_events.py` — Setup:
  `install_tool_package("goga_tool_rec", register_hooks=...)` recording the delivered
  context; registry reset fixture; Input:
  `TopicHooks().emit_published(identity, remote_branch="origin/feat-x",
  commit_hash="c1", commit_message="m", outcome="pushed")`; Assertions:
  `context.identity is identity`; `context.remote_branch == "origin/feat-x"`;
  `context.commit_hash == "c1"`; `context.commit_message == "m"`;
  `context.outcome == "pushed"`; `not hasattr(context, "todo")` (the breaking
  reshape, pinned against a real platform delivery)
- [ ] **Debugging**: `pytest tests/topics/hooks/ tests/topics/test_publishing.py -x`
  — fix implementation code until all tests pass; where a downstream suite still
  asserts the old call shape, re-pin it to the five-fact call (the reshape is the
  contract)
- [ ] **Contract re-verification**: `python -c "from goga.topics.hooks import
  TopicHooks, TopicPublished"`; the catalog record `topics/topic_published` (soft) is
  untouched
- [ ] **Lint**: `ruff check goga/topics/hooks/` — fix formatting if necessary

### Task 6: `publishing.py` — `resolve_publication_outcome`, `publish_existing_topic`, and the `publish_topic` step-9 re-sign (goga/topics)

The topics domain gains the publication operation at `location` `publishing.py`
(three contract entities share this `location` and form one task; the pure
classifier is implemented and verified before the orchestrator consumes it). Facade:
`goga/topics/__init__.py` (see checkboxes). New imports in `publishing.py`:
`fetch_branch`, `is_ancestor`, `resolve_commit_message` into the `.git` import
block (currently `from .git import (...)` at line 43); `_FETCHING_LINE`,
`_projection` into the `.exchange` import block (currently line 42 — private
intra-package import per the D5 precedent `publishing.py ← .creation._BOARD_HINT`;
sources at `goga/topics/exchange.py:45` and `:484`).

Design-verified algorithms (verbatim):

`resolve_publication_outcome` — the pure four-outcome decision (equality precedes
containment; `is_ancestor(ancestor, descendant)` argument order verified against
`goga/topics/git/exchange.py:74`):

```
1. IF twin_tip IS None → RETURN "pushed"
2. IF twin_tip == own_tip → RETURN "up-to-date"
3. IF is_ancestor(own_tip, twin_tip) → RETURN "remote-ahead"
4. RAISE click.ClickException(
     f"branch and origin twin diverged — own tip {own_tip}, twin tip {twin_tip}; "
     "reconcile manually with git, then re-run")
```

`publish_existing_topic` — the wrapper reuses the `publish_topic` exception boundary
verbatim (`CalledProcessError` → `ClickException("git failed: {stderr}")`;
`FileNotFoundError` → "git is not available: {exc}"; `ImportError` → registry
assembly; `OSError` → phase-neutral):

```
_CONSTANT _PUBLISH_RESULT_LINE = "Published topic {year}/{slug} — {outcome}"

publish_existing_topic(identifier, year=None):
  TRY _publish_existing_topic(...) EXCEPT the publish_topic boundary verbatim

_publish_existing_topic(identifier, year):
 1. resolved_year = year or current_year()
 2. target = resolve_exchange_target(identifier, year)
 3. IF NOT origin_configured() → ClickException(
      "origin is not configured — publishing delivers to origin")
 4. own_tip = resolve_ref_commit(target.branch)
 5. click.echo(_FETCHING_LINE.format(branch=target.branch))
    fetch_branch(target.branch)
    twin_tip = _projection(f"origin/{target.branch}")
 6. outcome = resolve_publication_outcome(own_tip, twin_tip)
 7. IF outcome == "pushed": push_branch(target.branch)
 8. twin = _projection(f"origin/{target.branch}")
    message = resolve_commit_message(twin)
 9. identity = TopicIdentity(slug=target.topic, year=resolved_year, branch=target.branch)
    TopicHooks().emit_published(identity, remote_branch=f"origin/{target.branch}",
        commit_hash=twin, commit_message=message, outcome=outcome)
10. RETURN _PUBLISH_RESULT_LINE.format(year=resolved_year, slug=target.topic, outcome=outcome)
```

Behavioral checkpoints already verified in the design: the reporting line precedes
the fetch (sanctioned-network convention); an absent twin swallows `couldn't find
remote ref` inside `fetch_branch` and the projection reads `None`; step 8 re-reads
the twin via the projection after the operation (D12 — `push_branch`'s `-u`
guarantees the remote-tracking ref is current without network); no git version gate
(D7 — no 2.40-only plumbing here); every success emits, idempotent outcomes
included; only `push_branch` is reachable — no force, no lease on any path.

`publish_topic` step 9 — replace the emission call in `_publish_topic` (the old
call sits at `goga/topics/publishing.py:248`) with the reshaped five-fact call:
`hooks.emit_published(identity, remote_branch=f"origin/{branch_name}",
commit_hash=commit, commit_message=applied, outcome="pushed")` — the built commit's
facts are in hand, no `resolve_commit_message` here (matching the contract's "the
commit hash and message of the built commit"). Update the routine docstring's step 8
wording to the new facts. Nothing else moves; rollback paths still fire nothing.

**Usages relevant to this task:**
- `exchanging` (`goga/topics/git/.usages/exchanging.md`): `fetch_branch` (single
  sanctioned fetch of the own branch), `is_ancestor(own_tip, twin_tip)` for the
  strict-ahead probe; the reporting line is the caller's.
- `refs-and-switching` (`goga/topics/git/.usages/refs-and-switching.md`):
  `resolve_ref_commit` for the own tip and the twin projection — read-only.
- `publishing` git zone (`goga/topics/git/.usages/publishing.md`):
  `origin_configured` probe before anything; `push_branch(branch)` exactly the named
  branch, upstream-bound.
- `checkpoints` topics zone (`goga/topics/hooks/.usages/checkpoints.md`): one
  `TopicHooks()` per emission site sharing the run registry; facts from the
  operation's own data; fire-and-forget under the soft class.
- `convention`: the `_wire_*` domain-mock pattern — git boundary mocked at its
  `goga.topics.publishing` import points; the real domain orchestration runs.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/topics/test_publishing.py` — assert
  `resolve_publication_outcome` and `publish_existing_topic` are importable from
  `goga.topics` and in `__all__`; signature checks against the declared forms
  (expected to fail before implementation)
- [ ] **Code**: implement `resolve_publication_outcome` per the algorithm — the
  four-outcome decision, equality before containment, D4 divergence error
- [ ] **Code**: implement `publish_existing_topic` / `_publish_existing_topic` per
  the algorithm — `_PUBLISH_RESULT_LINE` constant (D3), the wrapper with the
  `publish_topic` boundary verbatim, steps 1–10; docstrings carry the contract
  annotations (Algorithm/Requirements/Constraints)
- [ ] **Code**: re-sign the `publish_topic` step-9 emission call to the reshaped
  five-fact call; update the routine docstring's step wording
- [ ] **Code**: extend the import blocks (`fetch_branch`, `is_ancestor`,
  `resolve_commit_message` → `.git`; `_FETCHING_LINE`, `_projection` → `.exchange`)
  and the facade `goga/topics/__init__.py`: `from .publishing import
  publish_existing_topic, publish_topic, resolve_publication_outcome`; `__all__`
  gains `publish_existing_topic` (before `publish_topic`) and
  `resolve_publication_outcome` (after `resolve_propagation`)
- [ ] **Interface verification**: `python -c "from goga.topics import
  publish_existing_topic, resolve_publication_outcome"` and
  `pytest tests/topics/test_publishing.py -v`
- [ ] **Logic tests**: in `tests/topics/test_publishing.py` (git boundary mocked at
  the module's import points; `resolve_commit_message` → `"msg"`; `TopicHooks.
  emit_published` mocked; `click.echo` captured):
  - `test_resolve_publication_outcome_matrix` (parametrized, the four-outcome pin) —
    mock `goga.topics.publishing.is_ancestor` per case; pairs `(own="tip",
    twin=None)` → `"pushed"`; `(own="tip", twin="tip")` → `"up-to-date"`;
    `(own="tip", twin="ahead")` with `is_ancestor("tip","ahead") → True` →
    `"remote-ahead"`; `(own="tip", twin="other")` with `is_ancestor → False` →
    `pytest.raises(click.ClickException)` with both "tip" hashes and "reconcile" in
    the message; the equality case asserts `is_ancestor` was **NOT** called
    ("equality precedes containment")
  - `test_publish_existing_topic_pushed_creates_twin_and_emits` — Setup:
    `resolve_exchange_target → ExchangeTarget(topic="feat-x", branch="feat-x",
    current=False)`; `origin_configured → True`; `resolve_ref_commit` → `"c1"`;
    pre-push projection `None`, post-push `"c1"`; `fetch_branch`/`push_branch`
    recorded; Assertions: `push_branch` called exactly once with `"feat-x"`; no
    lease/force call sites invoked; `fetch_branch` called exactly once, after the
    echo line; `emit_published` kwargs == the five facts
    (`identity(slug="feat-x", year=<current>, branch="feat-x")`,
    `remote_branch="origin/feat-x"`, `commit_hash="c1"`, `commit_message="msg"`,
    `outcome="pushed"`); `result == f"Published topic {year}/feat-x — pushed"`
  - `test_publish_existing_topic_idempotent_outcomes_emit_and_mutate_nothing` —
    Setup: projection `"c1"` (up-to-date) and `"c2"` with
    `is_ancestor("c1","c2") → True` (remote-ahead); `push_branch` mocked to fail
    the test if called; Assertions: `push_branch.assert_not_called()`;
    `emit_published` called once per run with `outcome="up-to-date"` /
    `"remote-ahead"`, `commit_hash ==` the twin tip, `commit_message ==` its
    message; result endswith `"— up-to-date"` / `"— remote-ahead"`
  - `test_publish_existing_topic_diverged_is_clean_error_nothing_mutated`
    (negative) — Setup: projection `"c2"`, `is_ancestor("c1","c2") → False`,
    `push_branch`/`fetch_branch` recorded, `resolve_commit_message` failing the test
    if called, `emit_published` mocked; Assertions:
    `pytest.raises(click.ClickException)` with both `"c1"` and `"c2"` in `str(exc)`
    and `"reconcile"` in `str(exc)`; `push_branch.assert_not_called()`;
    `emit_published.assert_not_called()`;
    `resolve_commit_message.assert_not_called()`
  - `test_publish_existing_topic_origin_unconfigured_before_network` (negative) —
    Setup: `origin_configured → False`; `fetch_branch` failing the test if called;
    Assertions: `pytest.raises(click.ClickException, match="origin is not
    configured")`; `fetch_branch.assert_not_called()`
  - `test_publish_existing_topic_no_force_or_lease_callsites` (edge, repo sweep) —
    static: `inspect.getsource(goga.topics.publishing)`; Assertions: the
    `publish_existing_topic` / `_publish_existing_topic` region references no
    `push_branch_with_lease` and no `--force`/`force-with-lease` spelling
  - re-pin the existing `publish_topic` emission assertions to the five-fact call
    (`remote_branch=f"origin/{branch_name}"`, built-commit facts,
    `outcome="pushed"`)
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: facade imports resolve; the sanctioned network
  set holds (exactly one fetch + at most one push, both of the topic's own branch,
  reported by one stdout line); no local ref moved, created, or deleted; the
  emission shape matches the reshaped `emit_published` exactly
- [ ] **Lint**: `ruff check goga/topics/` — fix formatting if necessary

### Task 7: `updating.py` — the update-path publication emission (goga/topics)

`update_topic` (step 9 of its contract) emits `topic_published` after a successful
publish push. Location: `goga/topics/updating.py`. The insertion point: after the
`if publish: _publish_refreshed_branch(...)` block succeeds (`_publish_refreshed_branch`
at `goga/topics/updating.py:417`) and **before** `_emit_updated(...)`. New private
helper (design-verbatim):

```
_emit_published_delivery(target, year):
  tip = resolve_ref_commit(f"origin/{target.branch}")
  TopicHooks().emit_published(
      TopicIdentity(slug=target.topic, year=year, branch=target.branch),
      remote_branch=f"origin/{target.branch}",
      commit_hash=tip, commit_message=resolve_commit_message(tip), outcome="pushed")
```

Ordering facts verified in the design: the `already-current` early return (line
~270) precedes `if publish:` and emits only `topic_updated` with `published=False`;
a failed publish push raises out of `_publish_refreshed_branch` before the emission
(the confirmed update stands — the single atomicity exception, unchanged);
publication precedes the update notification. New imports:
`resolve_commit_message` extends the `.git` block (line 43); `TopicIdentity` is
already imported. Docstring: extend step 9 and the Requirements bullet per the
contract.

**Usages relevant to this task:**
- `checkpoints` topics zone: facts from the operation's own post-state (the
  post-push twin read is the operation's own data); one `TopicHooks()` per site.
- `convention`: the `_wire_update` scenario factory of
  `tests/topics/test_updating.py` (line 54) is the fixture pattern to extend.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/topics/test_updating.py` — a signature/shape
  check that `update_topic` still carries
  `(identifier, base_ref, strategy, commit_message, publish, year) -> str` and that
  the module imports `resolve_commit_message` (the wiring under test; expected to
  fail before implementation)
- [ ] **Code**: add `_emit_published_delivery(target, year)` to
  `goga/topics/updating.py` per the algorithm above; call it after the successful
  `_publish_refreshed_branch`, before `_emit_updated`
- [ ] **Code**: extend the `.git` import block with `resolve_commit_message`;
  update the `update_topic` docstring (step 9 + Requirements bullet per the
  contract)
- [ ] **Interface verification**: `pytest tests/topics/test_updating.py -v`
- [ ] **Logic tests**: in `tests/topics/test_updating.py` (existing checkout-free
  merge-update fixtures; `resolve_commit_message` mocked → `"merged message"`;
  `emit_published` mocked on `TopicHooks`):
  - `test_update_publish_emits_publication_after_push` — Input:
    `update_topic("feat-x", "origin/main", "merge", None, True, "2026")`;
    Assertions: `emit_published` called once with kwargs exactly
    (`identity(slug="feat-x", year="2026", branch="feat-x")`,
    `remote_branch="origin/feat-x"`, `commit_hash=tip`,
    `commit_message="merged message"`, `outcome="pushed"`) where `tip ==
    resolve_ref_commit("origin/feat-x")`; `emit_updated` still called once with
    `published=True`; call order: `emit_published` before `emit_updated` (record
    call order across the two mocks)
  - `test_update_failed_publish_push_emits_nothing_update_stands` (negative, review
    fix R6) — Setup: `push_branch` mocked to raise
    `subprocess.CalledProcessError(1, "git", stderr="origin rejected the update")`;
    both emissions mocked; Input:
    `pytest.raises(click.ClickException): update_topic("feat-x", "origin/main",
    "merge", None, True, "2026")`; Assertions: the wrapper renders `"git failed"`;
    `emit_published.assert_not_called()`; `emit_updated.assert_not_called()`;
    `point_branch_at_commit` of the addressee's branch was called exactly once (the
    confirmed update stands — no rollback of the topic branch)
  - `test_update_already_current_publishes_and_emits_nothing` (edge) — Setup:
    `is_ancestor(base.tip, own_tip) → True`, `publish=True`; `push_branch` failing
    the test if called; `emit_published` mocked; Assertions: `push_branch` and
    `emit_published` never called; `emit_updated` called with
    `outcome="already-current", published=False`
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: publication fires exactly when a push completed;
  the already-current path emits no publication; `update_topic`'s signature and
  result line are unchanged
- [ ] **Lint**: `ruff check goga/topics/` — fix formatting if necessary

### Task 8: `propagating.py` — the propagation-path publication emission (goga/topics)

`execute_propagation` (step 6 of its contract) emits `topic_published` after the
successful inherent push, before the propagate notification. Location:
`goga/topics/propagating.py`. The insertion point: in `_deliver`, between
`_plant_and_push(plan, base, delivery)` and the `_emit_propagated` call. New private
helper (design-verbatim — the branch spelling mirrors the refspec target, including
nested `origin/x/y` bases):

```
_emit_published_delivery(plan, base, delivery):
  remote = base.local_branch if base.local_branch is not None
           else plan.base_ref.removeprefix("origin/")
  TopicHooks().emit_published(
      TopicIdentity(slug=plan.target.topic, year=plan.year, branch=plan.target.branch),
      remote_branch=f"origin/{remote}",
      commit_hash=delivery, commit_message=resolve_commit_message(delivery),
      outcome="pushed")
```

Retry-cycle facts verified in the design: a rejected first attempt raises
`_RejectedDeliveryError` out of `_deliver` **before** the emission point, the retry
re-enters `_deliver` and emits once on its success — exactly-once under retry;
`_nothing_to_do` returns before `_plant_and_push` — no publication; the emission
covers both step-6 paths (local `push_branch`, write-through
`push_revision_to_branch`). New imports: `resolve_commit_message` into the `.git`
import block (R3); `TopicIdentity` is already imported (`_emit_propagated` builds
identities). Docstring: extend step 6 and the Requirements bullet per the contract.

**Usages relevant to this task:**
- `checkpoints` topics zone: the delivery commit in hand is the operation's own
  data; one `TopicHooks()` per site; soft fire-and-forget.
- `convention`: the existing squash-delivery fixtures of
  `tests/topics/test_propagating.py` are the pattern to extend.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/topics/test_propagating.py` — a wiring check
  that `goga.topics.propagating` imports `resolve_commit_message` and
  `execute_propagation` keeps its declared signature (expected to fail before
  implementation)
- [ ] **Code**: add `_emit_published_delivery(plan, base, delivery)` to
  `goga/topics/propagating.py` per the algorithm above; call it in `_deliver`
  between `_plant_and_push` and `_emit_propagated`
- [ ] **Code**: extend the `.git` import block with `resolve_commit_message`;
  update the `execute_propagation` docstring (step 6 + Requirements bullet)
- [ ] **Interface verification**: `pytest tests/topics/test_propagating.py -v`
- [ ] **Logic tests**: in `tests/topics/test_propagating.py` (existing
  squash-delivery fixtures; `resolve_commit_message` mocked; both `TopicHooks`
  emissions mocked with a shared recorder):
  - `test_propagation_push_emits_publication_before_propagated` — Assertions:
    `emit_published` called once with `commit_hash ==` the delivery hash and
    `remote_branch == f"origin/{base}"`; recorder order: "published" strictly
    before "propagated"
  - `test_propagation_retry_cycle_emits_publication_exactly_once` (review fix R6) —
    Setup: the first `push_branch` call raises
    `subprocess.CalledProcessError(1, "git", stderr=" ! [rejected] main -> main
    (non-fast-forward)")`, the second succeeds; Assertions:
    `emit_published.call_count == 1`; the single call carries `commit_hash ==` the
    hash of the **second** delivery build; recorder order: "published" strictly
    before "propagated"; `emit_propagated.call_count == 1`
  - `test_propagation_nothing_to_do_emits_no_publication` (edge) — Setup:
    reachability idempotency hit (`is_ancestor(own_tip, base.tip) → True`);
    Assertions: `emit_published` not called; `emit_propagated` called with
    `outcome="nothing-to-do"`
- [ ] **Debugging**: `pytest tests/topics/ -x` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: publication precedes the propagate
  notification; the rejected attempt emits nothing and the retry does not
  double-emit; `execute_propagation`'s signature and result line are unchanged
- [ ] **Lint**: `ruff check goga/topics/` — fix formatting if necessary

### Task 9: `SchemaNode`, `Violation`, `GateVerdict` facts (goga/schema/hooks)

The schema hooks zone gains the three gate facts at `location` `facts.py`, placed
directly after `DependencyFacts`, before the module serves `CellAmendment`'s imports
(the CODEMANIFEST body order). Facade: `goga/schema/hooks/__init__.py` — the `.facts`
import gains `GateVerdict, SchemaNode, Violation` and `__all__` gains the three
names (the full `__all__` rewrite lands in Task 11 together with
`SchemaValidation`; this task adds the three facts names). `SchemaNode` needs
`from dataclasses import dataclass, field`; the module docstring grows the three
names. Pure facts — nothing read inside; mirrors `CellFacts`. The
`goga/build/hooks/facts.py` zone is the field-for-field precedent (`Violation` at
line 136).

Design-verbatim definitions:

```python
@dataclass(frozen=True, kw_only=True)
class SchemaNode:
    """One node of the final assembled tree — the read-only delivered view of the validation gate."""
    path: str
    description: str
    types: list[str]
    usages: list[str]
    dependencies: list[DependencyFacts]
    children: list["SchemaNode"]
    tools: dict[str, dict[str, object]] = field(default_factory=dict)

@dataclass(frozen=True, kw_only=True)
class Violation:
    """One collected veto of the validation walk."""
    tool: str
    hook: str
    reason: str

@dataclass(frozen=True, kw_only=True)
class GateVerdict:
    """The collected verdict of the validation walk."""
    violations: list[Violation]

    @property
    def approved(self) -> bool:
        """True when no violation was collected — the generation may proceed."""
        return not self.violations
```

**Usages relevant to this task:**
- `convention`: frozen `kw_only` dataclasses; Google docstrings; mirrored test
  layout `tests/schema/hooks/test_facts.py` (exists — extend it).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/schema/hooks/test_facts.py` — assert the three
  names are importable from `goga.schema.hooks`, frozen and `kw_only`, with exactly
  the declared fields (`SchemaNode`: seven fields, `tools` defaulting to `{}`;
  `Violation`: `tool`/`hook`/`reason`; `GateVerdict`: `violations` only, `approved`
  a derived property, **not** a constructor field) (expected to fail before
  implementation)
- [ ] **Code**: add the three dataclasses to `goga/schema/hooks/facts.py` per the
  definitions above, directly after `DependencyFacts`; extend the `dataclasses`
  import with `field`; grow the module docstring
- [ ] **Code**: add `GateVerdict, SchemaNode, Violation` to the `.facts` import and
  `__all__` of `goga/schema/hooks/__init__.py`
- [ ] **Interface verification**: `python -c "from goga.schema.hooks import
  SchemaNode, Violation, GateVerdict"` and `pytest tests/schema/hooks/test_facts.py -v`
- [ ] **Logic tests**: in `tests/schema/hooks/test_facts.py` — `GateVerdict([]).
  approved is True`; `GateVerdict([Violation("t", "h", "r")]).approved is False`;
  `SchemaNode(...)` with omitted `tools` yields `{}`; a `SchemaNode` whose
  `children` contain another `SchemaNode` round-trips (recursion); mutation of a
  frozen instance raises
- [ ] **Debugging**: `pytest tests/schema/hooks/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the three names resolve from the facade; pure
  facts — no reads inside
- [ ] **Lint**: `ruff check goga/schema/hooks/` — fix formatting if necessary

### Task 10: `SchemaValidation` delivered view — new module `contexts.py` (goga/schema/hooks)

The gate's per-tool view at `location` `contexts.py` — a **new module** of the zone.
It is the `BuildValidation` mechanism verbatim (`goga/build/hooks/contexts.py:26`):
**non-frozen** `kw_only` (the buffer must be writable through `veto`);
`wrap_context` blocks attribute assignment on the proxy while calls pass through, so
`context.tree = ...` raises and `context.veto(...)` works. Python 3.10
compatibility: `from __future__ import annotations`. Facade: the
`goga/schema/hooks/__init__.py` `.contexts` import (new) and `__all__` entry.

Design-verbatim module:

```python
"""The delivered view of the schema validation gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import SchemaNode


@dataclass(kw_only=True)
class SchemaValidation:
    """The gate's delivered view of one tool — the read-only final tree plus the veto buffer of this tool alone.

    Args:
        tree: the final assembled tree in tree order — the tools overlay included;
            read-only for the receiving hook (a fresh copy per tool).
    """

    tree: list[SchemaNode]

    _veto: str | None = field(init=False, default=None, repr=False)

    def veto(self, reason: str) -> None:
        """Buffer this tool's veto of the final tree.

        The replacement is whole — a later call replaces the earlier reason.
        The view records no hook identity: the walk attributes the veto by
        observing the buffer change around each call. The call changes nothing
        until the walk collects it; it does not cancel, redirect, or defer the
        operation — a veto stops the generation through the collected verdict
        only. An empty or whitespace-only reason is stored as given; the merged
        error renders it verbatim.

        Args:
            reason: the human-readable violation reason.
        """
        self._veto = reason
```

**Usages relevant to this task:**
- `registering-hooks` (`goga/hooks/.usages/registering-hooks.md`): hooks declare
  `context` (and optionally `self`); undeclared names receive nothing — the view is
  the `context` argument of the gate hooks.
- `convention`: mirrored test layout — `tests/schema/hooks/test_contexts.py` is a
  **new** test file.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/schema/hooks/test_contexts.py` — assert
  `SchemaValidation` is importable from `goga.schema.hooks`, `kw_only` and **not**
  frozen, constructed as `SchemaValidation(tree=[...])` with `_veto` excluded from
  `init` and `repr` (expected to fail before implementation)
- [ ] **Code**: create `goga/schema/hooks/contexts.py` per the module above
- [ ] **Code**: import `.contexts.SchemaValidation` in
  `goga/schema/hooks/__init__.py` and add `"SchemaValidation"` to `__all__`
- [ ] **Interface verification**: `python -c "from goga.schema.hooks import
  SchemaValidation"` and `pytest tests/schema/hooks/test_contexts.py -v`
- [ ] **Logic tests**: `test_schema_validation_veto_semantics_and_write_protection`
  in `tests/schema/hooks/test_contexts.py` — Setup: plain
  `SchemaValidation(tree=[...])`; `wrap_context` from `goga.hooks`; Input:
  `view.veto("first"); view.veto("")`; `proxy = wrap_context(view)`; `proxy.tree`
  read; `proxy.tree = []` attempted; Assertions:
  `view._veto == ""` (replacement is whole; empty reason stored as given);
  `proxy.tree is view.tree` (reads pass through);
  `pytest.raises(Exception): proxy.tree = []` (attribute assignment blocked);
  `proxy.veto("via proxy")` works and `view._veto == "via proxy"`
- [ ] **Debugging**: `pytest tests/schema/hooks/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the mechanism matches `BuildValidation`
  verbatim; the view records no hook identity
- [ ] **Lint**: `ruff check goga/schema/hooks/` — fix formatting if necessary

### Task 11: `SchemaHooks.validate_schema` — the gate delivery (goga/schema/hooks)

The gate delivery at `location` `events.py`. Contract: `validate_schema(tree:
list[SchemaNode]) -> verdict: GateVerdict` — the `per-tool-delivery` loop skeleton
with the recorded refinement: the walk runs to completion and collects vetoes; no
early stop, no contribution commit; per-hook attribution by buffer snapshot. It
shares `self._ensure_registry()` with `amend_cell` (one enumeration per run). Copy
the mechanics from the `goga/build/hooks` reference (veto buffer, attribution
snapshot, crash override) — do not redesign them. Facade: `__all__` becomes
`["CellAmendment", "CellFacts", "DependencyFacts", "GateVerdict", "SchemaHooks",
"SchemaNode", "SchemaValidation", "ToolContribution", "merge_cell_contributions"]`;
the module docstring lists the gate surface.

Design-verified algorithm (verbatim):

```
1. registry = self._ensure_registry()
2. record = the declared_actions entry ("schema", "validate_schema")
   IF None → raise ValueError("unknown hook action: schema.validate_schema")
3. groups = subscriptions_for("schema", "validate_schema") grouped per tool
4. violations = []
   FOR (tool, subscriptions) IN groups (enumeration order):
     view = SchemaValidation(tree=_copy_tree(tree))
     proxy = wrap_context(view)
     attributed_hook = ""; crash = None
     FOR subscription IN subscriptions:
       before = view._veto
       TRY subscription.hook(**build_hook_arguments(subscription.hook, proxy,
                                                    registry.self_context(tool)))
       EXCEPT Exception AS reason: crash = (subscription.name, str(reason)); BREAK
       IF view._veto != before: attributed_hook = subscription.name
     IF crash IS NOT None: violations.append(Violation(tool, crash[0], crash[1]))
     ELIF view._veto IS NOT None:
       violations.append(Violation(tool, attributed_hook, view._veto))
5. RETURN GateVerdict(violations=violations)
```

Module helpers of the same file:

- `_copy_tree(nodes)` — recursive fresh `SchemaNode` per node with fresh
  `list(...)`/`dict(...)` at every level, the `tools` overlay values copied through
  `_copy_json` (D6 — the deep fresh copy extends `_read_only_view`'s
  mutual-blindness guarantee to the gate; the caller's projection — nested overlay
  values included — is never shared with a tool).
- `_copy_json(value)` — `dict` → a fresh dict with every value copied recursively,
  `list` → a fresh list with every item copied recursively, any scalar → as-is; the
  JSON-shape domain of a committed contribution (validated at the tool commit point
  of `amend_cell`) covers exactly these forms. It is also imported by
  `goga/schema/schema.py` (Task 12) — the same private intra-package import
  direction D5 establishes; the hooks zone never imports the domain, so no cycle.

Imports: `SchemaValidation` from `.contexts`; `GateVerdict`, `SchemaNode`,
`Violation` from `.facts`. Method docstring carries the full contract annotation
(the walk-to-completion refinement of `per-tool-delivery`, the Requirements, and the
Constraints — no printing, no repository reads).

**Usages relevant to this task:**
- `per-tool-delivery` (`goga/hooks/.usages/per-tool-delivery.md`): the loop skeleton
  (group per tool, `wrap_context`, `build_hook_arguments`, `self_context`) with the
  gate's recorded refinement — run to completion, collect vetoes, no contribution
  commit; per-hook attribution by buffer snapshot.
- `convention`: the shared fixtures `pin_package_environment` /
  `install_tool_package` (re-exported by `tests/schema/hooks/conftest.py`) plus the
  registry reset between cases (the existing conftest pattern of the zone).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/schema/hooks/test_events.py` — assert
  `SchemaHooks` exposes `validate_schema` with signature
  `(tree: list[SchemaNode]) -> GateVerdict` and that `SchemaHooks` remains in the
  zone facade `__all__` alongside the gate names (expected to fail before
  implementation)
- [ ] **Code**: add `_copy_json` and `_copy_tree` module helpers to
  `goga/schema/hooks/events.py` per the definitions above
- [ ] **Code**: implement `SchemaHooks.validate_schema` per the algorithm —
  shared registry, address resolution with the clean unknown-address error, the
  per-tool walk with snapshot attribution, crash override, `GateVerdict` return
- [ ] **Code**: extend the imports (`.contexts.SchemaValidation`; `.facts` gains
  `GateVerdict, SchemaNode, Violation`) and rewrite the zone facade
  `goga/schema/hooks/__init__.py` `__all__` to the nine-name list above; the module
  docstring lists the gate surface
- [ ] **Interface verification**: `python -c "from goga.schema.hooks import
  SchemaNode, Violation, GateVerdict, SchemaValidation"` and
  `pytest tests/schema/hooks/test_events.py -v`
- [ ] **Logic tests**: in `tests/schema/hooks/test_events.py`:
  - `test_validate_schema_approved_with_no_subscriptions` — Setup:
    `pin_package_environment` with zero tool packages; registry reset; Input:
    `SchemaHooks().validate_schema([node("goga/a")])`; Assertions:
    `verdict.approved is True`; `verdict.violations == []` (the inert gate — this
    is what keeps plain `goga schema` byte-identical)
  - `test_validate_schema_collects_one_violation_per_tool_walk_to_completion` —
    Setup: `install_tool_package("goga_tool_alpha", ...)` subscribing two hooks:
    `veto_alpha` (vetoes) and `noop_alpha` (records invocation);
    `goga_tool_beta` subscribing `noop_beta` (records invocation); Assertions:
    `len(verdict.violations) == 1`;
    `verdict.violations[0] == Violation(tool="alpha", hook="veto_alpha",
    reason=<reason>)`; `noop_alpha.invoked and noop_beta.invoked` — every
    subscribed tool ran to completion
  - `test_validate_schema_crash_overrides_buffered_veto` — Setup:
    `install_tool_package("goga_tool_alpha", register_hooks=...)` subscribing, in
    registration order: `veto_and_boom` — calls `context.veto("v")` and **then**
    raises `RuntimeError("kaboom")` inside the same hook — and `later` (records its
    invocation); registry reset fixture (review fix R6: one ordering —
    veto-then-raise in a single hook — that actually exercises the override);
    Assertions: `verdict.violations == [Violation("alpha", "veto_and_boom",
    "kaboom")]`; `"Traceback" not in verdict.violations[0].reason` (`str(reason)`,
    never a traceback); `later.invoked is False` (per-tool stop; no second record
    for the buffered veto)
  - `test_validate_schema_unknown_address_is_emitting_side_error` (negative) —
    Setup: `monkeypatch.setattr("goga.schema.hooks.events.declared_actions", ...)`
    with the `validate_schema` record removed (the existing pattern of
    `test_events.py`); Input: `SchemaHooks().validate_schema([])`;
    Assertions: `pytest.raises(ValueError, match="unknown hook action:
    schema.validate_schema")`
  - `test_validate_schema_delivers_fresh_tree_copy_per_tool` — Setup: two tools;
    the tree's root node carries a committed tools overlay with a nested value
    (`tools={"alpha": {"nested": {"k": 1}}}`); tool one records `id(context.tree)`
    and mutates `context.tree[0].types.append("x")`; tool two records the ids and
    mutates `context.tree[0].tools["alpha"]["nested"]["k"] = 2` inside its hook
    (review fix R2: the nested overlay mutation); Input: `validate_schema(tree)`
    with a caller-owned `tree` list; Assertions: the two delivered tree objects are
    not the same object as each other or as the caller's tree; after the walk
    `caller_tree[0].types ==` original value (never mutated);
    `caller_tree[0].tools["alpha"]["nested"]["k"] == 1` (a nested write never
    pierces); the nested dicts of the two delivered copies are distinct objects
    (id-disjoint); every node of every delivered copy is a fresh object (id sets
    disjoint)
- [ ] **Debugging**: `pytest tests/schema/hooks/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: no early stop; exactly one `Violation` per
  non-approving tool; no subscriptions → the empty approved verdict; the gate
  modifies nothing; no printing
- [ ] **Lint**: `ruff check goga/schema/hooks/` — fix formatting if necessary

### Task 12: The `schema` routine gate step (goga/schema)

The domain routine fires the gate between the amendment walk and serialization.
Location: `goga/schema/schema.py` (the early `return "[]"` at line 182 stays — D1;
the current unconditional `return json.dumps(...)` at line 204 gains the gate before
it). Imports: `SchemaNode` joins the `.hooks` import (for the helper annotation);
`from .hooks.events import _copy_json` — the D5 private-import precedent, hooks zone
never imports the domain, no cycle. The routine docstring gains the gate paragraph
and the `ValueError` case (vetoed gate).

Design-verified algorithm (verbatim — the new helper and the gate placement):

```
_new helper:
_to_schema_node(node: dict) -> SchemaNode:
    SchemaNode(path=node["cell"], description=node["description"],
               types=list(node["types"]), usages=list(node["usages"]),
               dependencies=[DependencyFacts(path=p, types=list(d["types"]),
                                             usages=list(d["usages"]))
                             for p, d in node["dependencies"].items()],
               children=[_to_schema_node(c) for c in node["children"]],
               tools={t: _copy_json(f) for t, f in node.get("tools", {}).items()})

after the amend_cell loop, before the return:
    verdict = hooks.validate_schema([_to_schema_node(n) for n in result])
    if not verdict.approved:
        details = "\n".join(
            f"- tool {v.tool} / hook {v.hook}: {v.reason}" for v in verdict.violations)
        raise ValueError(f"schema validation failed:\n{details}")
    return json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
```

Checkpoints verified in the design: the gate fires exactly once, after filters and
overlay, before serialization — no partial JSON; the projection is read-only over
`result` (`_to_schema_node` builds new records; `node.get("tools", {})` never
writes back; `_copy_tree` never touches the dicts) — an approved verdict leaves the
output byte-identical; the empty assembly (`result == []`) returns `"[]"` before
any checkpoint, the gate included.

**Usages relevant to this task:**
- `documents` / `beautiful_json` (local, `goga/schema`): the AST load and the final
  `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)` — unchanged.
- `convention`: golden-string tests under `tmp_path`; the existing
  `tests/schema/test_schema.py` fixtures.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/schema/test_schema.py` — assert `schema` keeps
  its declared signature `(cells, max_depth, depends_on) -> str` and that
  `goga.schema.schema` (module) imports `SchemaNode` and `_copy_json` (the wiring
  under test; expected to fail before implementation)
- [ ] **Code**: add `_to_schema_node` to `goga/schema/schema.py` per the definition
  above; extend the imports (`SchemaNode` → `.hooks`; `_copy_json` →
  `.hooks.events`)
- [ ] **Code**: insert the gate step after the `amend_cell` loop and before the
  return, per the algorithm — the merged `ValueError` (D11) lists one
  `- tool {tool} / hook {hook}: {reason}` line per violation; update the routine
  docstring (gate paragraph + `ValueError` case)
- [ ] **Interface verification**: `pytest tests/schema/test_schema.py -v`
- [ ] **Logic tests**: in `tests/schema/test_schema.py`:
  - `test_schema_gate_no_subscriptions_byte_identical` — Setup: `tmp_path` project
    with a small CODEMANIFEST tree (the existing fixtures); no tool packages;
    Input: `schema([], None, [])` before and after the change (golden string);
    Assertions: output equals the recorded golden JSON exactly (byte-for-byte, the
    six-field map, no `tools` keys)
  - `test_schema_gate_veto_raises_merged_error_listing_every_violation` — Setup:
    `tmp_path` project; `goga_tool_alpha` vetoing `"cell goga/x: broken"`;
    `goga_tool_beta` crashing `ValueError("nope")`; `goga_tool_gamma` vetoing with a
    whitespace-only reason (`context.veto("   ")`) (review fix R6); Input:
    `pytest.raises(ValueError): schema([], None, [])`; Assertions:
    `str(exc)` starts with `"schema validation failed:"`;
    `"- tool alpha / hook <name>: cell goga/x: broken"` in message;
    `"- tool beta / hook <name>: nope"` in message;
    `"- tool gamma / hook <name>:    "` in message (the empty reason stored as
    given and rendered verbatim — a veto, not a pass); exactly one line per
    violation (count of `"\n"` == violations count); nothing printed to stdout
  - `test_schema_empty_tree_returns_early_no_gate` (edge) — Setup: `tmp_path`
    project; a vetoing tool package installed (a gate firing would raise); Input:
    `schema(["nonexistent-cell"], None, [])`; Assertions: `result == "[]"`; the
    vetoing hook was never invoked (recorder)
- [ ] **Debugging**: `pytest tests/schema/ -x` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the gate placement is single (post-overlay,
  pre-serialization); the early `"[]"` return stays; the approved-path output is
  byte-identical
- [ ] **Lint**: `ruff check goga/schema/` — fix formatting if necessary

### Task 13: `build_injections` re-sign and the `config` injection (goga/commands/tool)

The tool dispatcher becomes tool-aware. Location: `goga/commands/tool/tool.py`
(current state: `_OFFERED_INJECTIONS: dict[str, Callable[[], object]] = {"ast":
_build_ast}` at line 42 and `build_injections(main: Callable)` at line 45).
Contract:
`build_injections(main: Callable, tool: str) -> injections: dict[str, object]` with
the `config` branch. Import: `from ...config import load_tool_config` (the facade —
the contract's import site, exercising the re-export; this is the single new
dependency edge of the plan). D8: the builders become `Callable[[str], object]`
taking the tool name; the `ast` builder ignores it; the dict stays the single source
of opt-in. D9: the command's injection-load failure message becomes
`Failed to load project AST or tool config: {exc}` — accurate for both lazy sources
that can now raise inside `build_injections` (the except tuple stays
`(DocumentParseError, yaml.YAMLError, OSError, UnicodeDecodeError)`, stderr,
`ctx.exit(1)`); the contract pins only "user-facing message, exit with code 1".
The dispatcher step 4 passes the resolved tool name: `injections =
build_injections(main_fn, name)`.

Design-verified algorithm (verbatim):

```
_OFFERED_INJECTIONS: dict[str, Callable[[str], object]] = {
    "ast": lambda _tool: _build_ast(),
    "config": lambda tool: load_tool_config(tool, "config.yml"),
}

1. params = keyword-capable parameters of inspect.signature(main)
2. injections = {}
3. FOR param IN params:
     builder = _OFFERED_INJECTIONS.get(param.name)
     IF builder IS None: continue
     injections[param.name] = builder(tool)     # lazy: runs only on a declared name
4. RETURN injections
```

Edge cases: `main` declaring neither name → `{}` (no file read, no AST build);
`config` declared but file absent → `None` injected; `ast` behavior byte-identical.

**Usages relevant to this task:**
- `tool-configuration` (`goga/config/.usages/tool-configuration.md`): the consumer
  contract of `load_tool_config` — `load_tool_config(tool, "config.yml")` — verbatim
  file name, no suffix logic; absence-None; raw passthrough.
- `loading` (`goga/ast/.usages/loading.md`): the unchanged `ast` branch —
  `AST(".")` at the dispatcher's CWD + `.load()`; errors pass through.
- `click` (`.goga/usages/cooks/click.md`): the command handler, `secho` to stderr,
  `ctx.exit(1)`.
- `convention`: signature-projection tests with plain functions; `CliRunner` or the
  direct-handler pattern of `tests/commands/tool/test_tool.py`.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/commands/tool/test_tool.py` — assert
  `build_injections` has signature `(main: Callable, tool: str) -> dict[str,
  object]` and `_OFFERED_INJECTIONS` offers exactly `{"ast", "config"}` with
  `Callable[[str], object]` builders (expected to fail before implementation)
- [ ] **Code**: re-sign `build_injections` and rewrite `_OFFERED_INJECTIONS` per
  the algorithm above; the `ast` builder ignores the tool name
- [ ] **Code**: import `from ...config import load_tool_config`; pass the resolved
  name at the call site (`build_injections(main_fn, name)`); change the failure
  message to `Failed to load project AST or tool config: {exc}` (D9); update the
  docstrings per the contract annotations
- [ ] **Interface verification**: `pytest tests/commands/tool/test_tool.py -v`
- [ ] **Logic tests**: in `tests/commands/tool/test_tool.py`:
  - `test_build_injections_config_declared_loads_raw` — Setup: `tmp_path` cwd
    monkeypatched (`monkeypatch.chdir(tmp_path)`) with
    `.goga/tools/coverage/config.yml` = `threshold: 5`; entry
    `def main(argv, *, config): ...`; Input:
    `build_injections(main, "coverage")`; Assertions:
    `injections == {"config": {"threshold": 5}}`
  - `test_build_injections_config_absent_yields_none` — Setup: `tmp_path` cwd
    without any `.goga/tools`; `def main(argv, *, config=None): ...`;
    Assertions: `injections == {"config": None}`
  - `test_build_injections_ast_unchanged_and_both_together` — Setup: entry
    `def main(argv, *, ast, config): ...` in a `tmp_path` with a minimal valid
    CODEMANIFEST tree and a tool config; run with `monkeypatch.chdir`;
    Assertions: `set(injections) == {"ast", "config"}`;
    `isinstance(injections["ast"], AST)`;
    `injections["config"] == {...}`
  - `test_build_injections_skips_unknown_and_positional_only` (negative) — Setup:
    `def main(a, /, argv, *, logger=None): ...` under `monkeypatch.chdir` with no
    `.goga`; Assertions: `injections == {}`; no file access occurred
    (`load_tool_config` mock not called)
  - `test_tool_command_renders_config_load_failure_cleanly` (negative) — Setup:
    entry declaring `config`; `tmp_path` cwd with `.goga/tools/t/config.yml` =
    `: : :` (malformed YAML); `CliRunner` (or direct handler with a fake ctx per
    the suite's pattern); Input: invoke `tool` with name `t`; Assertions:
    `exit_code == 1`; `"Failed to load project AST or tool config:"` in stderr
    output; no traceback in output
- [ ] **Debugging**: `pytest tests/commands/tool/ -x` — fix implementation code
  until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the offered-injection set stays the single
  source of opt-in; the `ast` path is byte-identical in behavior; `_build_ast` is
  untouched
- [ ] **Lint**: `ruff check goga/commands/tool/` — fix formatting if necessary

### Task 14: The `publish` subcommand (goga/commands/topics)

The CLI surface of the feature. Location: `goga/commands/topics/topics.py` — the
subcommand registers **between `update` (line 511) and `propagate` (line 576)** (the
CODEMANIFEST body order). Import: `publish_existing_topic` joins the `goga/topics`
import block of the module. The module docstring's subcommand list gains `publish`.
Contract: `publish(identifier: str | None = None) -> exit_code: int` — 0 on success
(the up-to-date and remote-ahead outcomes included), 1 on error; do not read the
configuration (`_topics_section` is never called); do not ask a confirmation.

Design-verbatim callback (command-callback docstring rules apply: user-facing help,
no Args/Returns/Raises):

```python
@topics.command("publish")
@click.argument("identifier", required=False)
@click.pass_obj
def publish(scope: _TopicsScope, identifier: str | None = None) -> None:
    """Deliver an existing topic branch to origin.

    An omitted IDENTIFIER addresses the current topic; a given one is a branch
    name, a topic slug, or their prefix. The delivery resolves one of three
    success kinds — pushed, up-to-date, remote-ahead — and a diverged origin
    twin is a clean error naming both tips. No confirmation, no force, no
    configuration keys. One result line on stdout.
    """
    line = publish_existing_topic(identifier, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)
```

**Usages relevant to this task:**
- `click` (`.goga/usages/cooks/click.md`): `@topics.command("publish")` +
  `@click.argument("identifier", required=False)` + `@click.pass_obj`;
  `click.echo` for the one result line; `ctx.exit(0)`; a `ClickException` from the
  domain renders via click's standard handler (stderr, exit 1) — the `update`
  subcommand shape.
- `publishing` (topics domain usage, already imported by the cell): the publication
  contract of the domain.
- `convention`: handler-direct CLI tests or `CliRunner` with `COLUMNS` pinned (the
  existing `tests/commands/topics` pattern).

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/commands/topics/test_topics.py` — assert the
  `topics` group exposes a `publish` command registered between `update` and
  `propagate`, taking an optional `IDENTIFIER` positional (expected to fail before
  implementation)
- [ ] **Code**: add the `publish` callback per the code above, between `update` and
  `propagate`; add the import; update the module docstring's subcommand list
- [ ] **Interface verification**: `pytest tests/commands/topics/test_topics.py -v`
- [ ] **Logic tests**: in `tests/commands/topics/test_topics.py`:
  - `test_publish_subcommand_delegates_and_exits_zero` — Setup: `CliRunner`;
    `publish_existing_topic` mocked at the `goga.commands.topics.topics` import
    site returning `"Published topic 2026/feat-x — pushed"`; a spy on
    `_topics_section` (must not be called); Input:
    `runner.invoke(topics, ["publish", "feat-x", "--year", "2026"])` and
    `runner.invoke(topics, ["publish", "--year", "2026"])`; Assertions:
    `exit_code == 0`; `output == "Published topic 2026/feat-x — pushed\n"`;
    `publish_existing_topic` called with `("feat-x", "2026")` / `(None, "2026")`;
    `_topics_section` (config read) never called
  - `test_publish_subcommand_exit_zero_on_all_success_kinds` (parametrized) —
    Setup: as above; the domain mock returns the three success lines;
    Assertions: `exit_code == 0` for `pushed`, `up-to-date`, `remote-ahead` alike;
    output is the single line
- [ ] **Debugging**: `pytest tests/commands/topics/ -x` — fix implementation code
  until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: delegation with identifier + scoped year; one
  echo line; exit 0 on all three success kinds; no configuration read; no
  confirmation
- [ ] **Lint**: `ruff check goga/commands/topics/` — fix formatting if necessary

### Task 15: Integration tests — cross-cell facades, gate isolation, and the `goga schema` failure rendering

Cross-entity scenarios spanning multiple cells. The `goga/commands/schema` cell
(cell 11 of the plan) requires **no code change** — its existing `except Exception`
handler already renders the merged gate `ValueError` (verified during design); this
task locks that behavior and the cross-cell facades with tests.

**Usages relevant to this task:**
- `convention`: facade checks via `python -c "from package import Entity"` pinned
  as import-only tests; `CliRunner` with `COLUMNS` pinned.
- `checkpoints` (schema zone, `goga/schema/hooks/.usages/checkpoints.md`): the
  "Validate the final tree" section — projection sketch, `verdict.approved` gate,
  walk-to-completion, byte-stable no-subscription output.

**CRITICAL: `CODEMANIFEST` files and `.usages/` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create/extend the facade sweep tests:
  - `test_facade_reexports_schema_gate_surface` in
    `tests/schema/hooks/test_facade.py` — Input: `from goga.schema.hooks import
    GateVerdict, SchemaHooks, SchemaNode, SchemaValidation, Violation`;
    Assertions: all five resolve; each is in `goga.schema.hooks.__all__`;
    `SchemaNode`/`Violation`/`GateVerdict` are frozen dataclasses (`kw_only`)
  - `test_topics_facade_reexports_publish_routines` in
    `tests/topics/test_facade.py` (combined facade sweep) — Input:
    `from goga.topics import publish_existing_topic,
    resolve_publication_outcome`; Assertions: both callable and present in
    `goga.topics.__all__`; same for `from goga.topics.git import
    resolve_commit_message` and `from goga.config import load_tool_config`
- [ ] Test the gate↔domain boundary: `test_gate_leaves_caller_tree_untouched_after_run`
  in `tests/schema/test_schema.py` — Setup: a real projection
  `nodes = [_to_schema_node(n) for n in small_dict_tree]`; deep-copied snapshot; a
  subscribing tool that only reads; Input: `validate_schema(nodes)` → approved;
  Assertions: `nodes == snapshot` (deep equality) — the caller's records are the
  same objects with the same contents
- [ ] Test the command-level gate contract:
  `test_schema_command_gate_failure_stderr_exit_one` in
  `tests/commands/test_schema.py` (extend the existing `goga schema` command suite —
  the `pin_package_environment` autouse fixture and `CliRunner` are already there) —
  Setup: `tmp_path` project; vetoing tool
  package installed; `CliRunner`; Input: `runner.invoke(schema_cmd, [])`;
  Assertions: `exit_code == 1`; `result.stdout == ""` (nothing on stdout);
  `"schema validation failed:"` in `result.stderr`; `"- tool alpha / hook"` in
  `result.stderr`
- [ ] Run the full gate: `pytest tests/ -x` — all green
- [ ] Residual-wording sweep: `grep -rn "todo" --include="*.py" goga/topics
  tests/topics | grep -v "TopicCreated\|amend_todo\|todo_entered\|creation"`
  — expected hits only in the creation context (`TopicCreated.todo`, untouched)
  and history records; no `todo`-carrying publication context remains
- [ ] Lint: `ruff check goga/ tests/` — fix formatting if necessary

---

## Validation Commands

- `pytest tests/ -x`: Run all tests (the conventions' canonical full run)
- `pytest tests/<pkg>/test_<module>.py -v`: Run one suite (task-level verification)
- `ruff check goga/ tests/`: Lint check over the touched packages
- `python -c "from goga.config.tool import load_tool_config"`: Tool-cell facade
- `python -c "from goga.config import load_tool_config"`: Config facade re-export
- `python -c "from goga.topics.git import resolve_commit_message"`: Git facade re-export
- `python -c "from goga.topics import publish_existing_topic, resolve_publication_outcome"`: Topics facade re-exports
- `python -c "from goga.schema.hooks import SchemaNode, Violation, GateVerdict, SchemaValidation"`: Schema hooks gate surface
- `goga lint`: Contract consistency (82 cells, 0 errors before and after)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is accessible from the facade
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior
- [ ] Contract dependencies are met
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them
- [ ] No package boundary was expanded (the single sanctioned new edge is the contract-declared `goga/commands/tool → goga/config` import)
- [ ] `CODEMANIFEST` files and `.usages/` files were not modified (contracts are read-only)
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check goga/ tests/`, every facade check, `goga lint`)
- [ ] Every Usages entry is mentioned in at least one task (Phase 2 calibration)
- [ ] The residual-wording sweep finds no `todo`-carrying publication context
- [ ] The no-subscription `goga schema` output is byte-identical to the pre-change golden
