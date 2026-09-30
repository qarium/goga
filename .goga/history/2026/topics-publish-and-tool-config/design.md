# Design Document: Topics publish command, tool config loading standard, and schema validation gate

Task source: `.goga/history/2026/topics-publish-and-tool-config/task.md`; accepted ADR:
`adr.md`; architecture plan: `arch.md` (already materialized into CODEMANIFEST by the
apply-architecture stage). This document is the complete architectural specification for
the **implementation** of those contracts: every signature, algorithm, error path, facade
placement, and test is elaborated. Implementation order follows `arch.md`
(cells 1→11); the plan's verification checklist applies verbatim and is not repeated
except where this design sharpens it.

Language: Python (`goga config language` = python). All code below is design-level
Python — signatures, structures, and call shapes are normative; docstring prose follows
the `convention` practice.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST` — the `declared_actions` Requirements gain one
  additive record description: `domain="schema", name="validate_schema"`,
  `error_class="hard"`, walk-to-completion, one violation per tool.
- `goga/topics/git/CODEMANIFEST` — new routine `resolve_commit_message(commit) -> message`
  at `publish.py`.
- `goga/config/tool/CODEMANIFEST` — **new cell**; single routine
  `load_tool_config(tool, filename, root=None) -> data` at `loader.py`; practices
  `convention` (project file) and `yaml` (inline).
- `goga/config/CODEMANIFEST` — facade: imports `load_tool_config` from
  `goga/config/tool`, re-exports it (`->load_tool_config: {}`), facade prose extended.
- `goga/topics/hooks/CODEMANIFEST` — `TopicPublished` reshaped to the five
  publication-centric fields; `emit_published` re-signed; zone annotations gain the
  publication-centric paragraph; `emit_published` gains the soft-failure requirement.
- `goga/topics/CODEMANIFEST` — imports `resolve_commit_message`; new routines
  `publish_existing_topic` and `resolve_publication_outcome` (both `publishing.py`);
  `publish_topic` step 9, `update_topic` step 9 + Requirements, `execute_propagation`
  step 6 + Requirements updated for the publication emission; zone description and the
  sanctioned network set extended.
- `goga/schema/hooks/CODEMANIFEST` — new facts `SchemaNode`, `Violation`, `GateVerdict`
  (`facts.py`); new context `SchemaValidation` with `veto` (`contexts.py`); new
  `SchemaHooks.validate_schema` method; zone annotations gain the gate paragraph.
- `goga/schema/CODEMANIFEST` — imports `SchemaNode`/`GateVerdict`; `schema` algorithm
  renumbered to 7 steps with the gate as step 6; three new Requirements; global
  annotations gain the gate sentence.
- `goga/commands/tool/CODEMANIFEST` — imports `load_tool_config` + usage
  `tool-configuration` from `goga/config` (the single new dependency edge of the plan);
  `build_injections` re-signed with `tool: str` and the `config` injection branch;
  dispatcher step 4 passes the resolved tool name.
- `goga/commands/topics/CODEMANIFEST` — imports `publish_existing_topic`; new `publish`
  subcommand surface (optional `IDENTIFIER` positional) and method.
- `goga/commands/schema/CODEMANIFEST` — the failure enumeration of step 2 gains the
  vetoed validation gate.

### New Entities

- `load_tool_config` — `goga/config/tool/loader.py` (read side of the tool-config
  standard; raw passthrough YAML load).
- `resolve_commit_message` — `goga/topics/git/publish.py` (read-only commit message).
- `publish_existing_topic` — `goga/topics/publishing.py` (delivery of an existing topic
  branch to origin; four-outcome resolution).
- `resolve_publication_outcome` — `goga/topics/publishing.py` (pure own-twin
  classification).
- `SchemaNode` — `goga/schema/hooks/facts.py` (one node of the final assembled tree).
- `Violation` — `goga/schema/hooks/facts.py` (one collected veto).
- `GateVerdict` — `goga/schema/hooks/facts.py` (collected verdict; `approved` property).
- `SchemaValidation` — `goga/schema/hooks/contexts.py` (**new module**; the gate's
  per-tool view with `veto`).
- `SchemaHooks.validate_schema` — `goga/schema/hooks/events.py` (the gate delivery).
- `topics.publish` — `goga/commands/topics/topics.py` (CLI subcommand).
- Catalog record `schema/validate_schema` (hard) — `goga/hooks/catalog/catalog.py`.

### Changed Entities

- `TopicPublished` / `TopicHooks.emit_published` — publication-centric reshape
  (`identity`, `remote_branch`, `commit_hash`, `commit_message`, `outcome`); `todo`
  removed; address and soft error class unchanged.
- `publish_topic` — step 9 emission calls the reshaped `emit_published`.
- `update_topic` — emits `topic_published` after a successful publish push.
- `execute_propagation` — emits `topic_published` after the successful inherent push,
  before the propagate notification.
- `build_injections` — second parameter `tool`; new `config` injection.
- `tool` (command) — step 4 forwards the resolved tool name.
- `schema` (routine) — new step 6 (gate) / step 7 (serialize).
- `declared_actions` — one additive record.

### Deleted Entities

- None. (`TopicPublished.todo` is a removed **field**, not a deleted entity; see the
  migration note in `goga/topics/.usages/registering-hooks.md`.)

### Usages and Annotations Changes

- New usage file `goga/config/.usages/tool-configuration.md` (consumer doc of
  `load_tool_config`).
- `goga/commands/tool/.usages/tool.md` — `config` injection row, example, opt-in bullet,
  purpose sentence.
- `goga/commands/topics/.usages/topics-command.md` — `publish` section + audience.
- `goga/commands/schema/.usages/schema.md` — "Validation failures" section.
- `goga/schema/.usages/registering-hooks.md` — two-action intro, events-table row,
  "The validation view" section.
- `goga/schema/hooks/.usages/checkpoints.md` — "Validate the final tree" section.
- `goga/topics/.usages/publishing.md` — new intro + "Publishing an existing branch".
- `goga/topics/.usages/update.md`, `propagate.md` — publication-emission bullets.
- `goga/topics/.usages/registering-hooks.md` — reshaped `topic_published` row and
  context documentation + migration note.
- `goga/topics/git/.usages/publishing.md` — "Reading publication facts" section.
- `goga/topics/hooks/.usages/checkpoints.md` — reshaped `emit_published` example and
  facts.

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Phase 3 audit found no DSL defects: `goga lint` — 82 cells, 0 errors; every
  `Imports → From` resolves to a cell created/modified earlier in the plan order; every
  referenced practice resolves (project files under `.goga/usages/`, imported usages at
  `{from}/.usages/{name}.md`, inline texts); no cross-imports; the single new edge
  `goga/commands/tool → goga/config` is acyclic (the config subtree imports no command
  layer).

### Applied `.usages/` Fixes (user-approved during this design)

- `goga/schema/.usages/registering-hooks.md` — the plan's verbatim sentence replacement
  left a redundant continuation ("... a read-and-contribute view delivered during the
  walk ... It is a read-and-contribute view over the authored facts of one cell ...").
  The paragraph tail was tightened to: "The cell amendment is that
  read-and-contribute view over the authored facts of one cell; both actions are hard."
  No semantic change; `goga lint` re-run clean.

### Applied design-review fixes (user-approved during the review stage)

Ten remarks of the review stage were traced and fixed, all user-approved:

- **R1 (Medium, design)** — D10's plumbing `--pretty=%B` appends one terminator
  newline beyond the stored message (verified byte-level: `%B` 30 bytes vs the stored
  29); the contract requires "as git stores it, verbatim". All design sites and the
  mocked test now carry `--pretty=format:%B` (byte-exact, 29 bytes).
- **R2 (Medium, design)** — D6's fresh copy left nested JSON values inside the
  `tools` overlay shared between the caller's projection and every delivered view; a
  hostile nested write could reach `result` and the serialized output. `_copy_json`
  (defined beside `_copy_tree` in `goga/schema/hooks/events.py`, imported by
  `schema.py` per the D5 private-import precedent — no cycle) now deep-copies overlay
  values on both sides; the per-tool copy test covers a nested mutation.
- **R3 (Low, design)** — the `propagating.py` section now lists its new import
  (`resolve_commit_message` into the `.git` block).
- **R4 (Low, usages)** — `goga/commands/tool/.usages/tool.md` exit-code bullet now
  names the tool-config load failure beside the manifest one (D9).
- **R5 (Low, design)** — `load_tool_config`'s Errors list gains `UnicodeDecodeError`
  (a `ValueError` subclass, propagated raw; the `tool` command already catches it).
- **R6–R9 (test gaps)** — the crash-override gate test setup pinned to one ordering
  (veto-then-raise in a single hook); two new tests pin the emission-suppression on a
  failed update publish push and the exactly-once emission across the propagation
  retry cycle; the merged-error test gains the whitespace-only-reason veto case.
- **R10 (Low, CODEMANIFEST)** — `goga/topics/git/CODEMANIFEST`: `resolve_commit_message`
  now applies the `git` practice for the invocation pattern like every routine of the
  cell; `goga lint` re-run clean (82 cells, 0 errors).

### Recorded Design Decisions (contract left open; resolved here)

- **D1 (user-approved, option A)** — `schema` keeps the early `return "[]"` for a filter
  emptied tree: no surviving cells → no checkpoints at all, the amendment walk and the
  gate alike. Output stays byte-identical `[]`; validators never see an empty tree.
- **D2 (user-approved, option A)** — the `.usages` editorial fix above.
- **D3** — `publish_existing_topic` result line: `Published topic {year}/{slug} — {outcome}`
  (one line, names the addressee and the outcome kind; mirrors the domain's
  `_RESULT_LINE` style of `updating`/`propagating`).
- **D4** — divergence error: `branch and origin twin diverged — own tip {own_tip}, twin
  tip {twin_tip}; reconcile manually with git, then re-run` (names both tips; hint style
  of the domain's manual-git hints).
- **D5** — `publish_existing_topic` reuses `_FETCHING_LINE` and `_projection` from
  `.exchange` (private intra-package import; the established precedent is
  `publishing.py` importing `_BOARD_HINT` from `.creation`).
- **D6** — `validate_schema` delivers a **deep fresh copy** of the tree to every tool
  (recursive new `SchemaNode`s with fresh lists/dicts **and recursively copied JSON
  values inside the `tools` overlay**), extending `_read_only_view`'s
  mutual-blindness guarantee to the gate; the caller's projection — nested overlay
  values included — is never shared with a tool.
- **D7** — no git version gate in `publish_existing_topic`: it uses no 2.40-only
  plumbing (`fetch`, `push`, `merge-base --is-ancestor`, `rev-parse`, `log`); the gate
  belongs to `resolve_exchange_base`, which publish never calls.
- **D8** — `_OFFERED_INJECTIONS` builders become `Callable[[str], object]` taking the
  tool name; the `ast` builder ignores it. The dict stays the single source of opt-in.
- **D9** — the `tool` command's injection-load failure message becomes
  `Failed to load project AST or tool config: {exc}` — accurate for both lazy sources
  that can now raise inside `build_injections` (contract pins only "user-facing
  message, exit with code 1").
- **D10** — `resolve_commit_message` reads `git log -1 --pretty=format:%B <commit>` and
  returns `stdout` **verbatim** (the stored message byte-for-byte — the `format:` form
  adds no terminator newline, where the bare `%B` form appends one extra trailing
  newline; no strip); an unresolvable commit propagates the raw
  `subprocess.CalledProcessError` (the domain boundary renders it, exactly as
  `resolve_ref_commit`).
- **D11** — the gate's merged error: `schema validation failed:` followed by one
  `- tool {tool} / hook {hook}: {reason}` line per violation, raised as `ValueError`
  (folds into `commands/schema`'s existing `except Exception` handler).
- **D12** — after a `pushed` outcome the twin tip is re-read via the projection
  (`origin/<branch>`), not assumed from `own_tip`: the honest post-operation read the
  contract's step 8 names, and `push_branch`'s `-u` guarantees the remote-tracking ref
  is current without network.

---

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

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

### Entity Dependencies

Initialization order for a run is the plan's cell order (leaves first):
`goga/hooks/catalog` → `goga/topics/git` → `goga/config/tool` → `goga/config` →
`goga/topics/hooks` → `goga/topics` → `goga/schema/hooks` → `goga/schema` →
`goga/commands/tool` → `goga/commands/topics` → `goga/commands/schema`.
`SchemaHooks` shares one lazily-built `HookRegistry` between `amend_cell` and
`validate_schema`; `TopicHooks` shares the module-level run registry across every
emission of the process.

---

## Code Stack Trace

### Trace: `load_tool_config`

#### Chain
1. **Input**: caller passes `tool` (platform tool identity, hyphen form — trusted, never
   validated), `filename` (verbatim, with extension), optional `root: Path | None`.
2. **Step**: flat-name guard — `filename` must be non-empty, not `.`/`..`, and contain
   neither `/` nor `\\` → otherwise `ValueError` naming the file name, before any read
   → checkpoint: error precedes every filesystem access ✓ (the write side buffers
   verbatim names; `config.yml` always passes).
3. **Step**: compose `base = root if root is not None else Path(".")` — the project-root
   anchor of the configuration loaders (`load_project_config` anchors `./.goga/config.yml`
   the same way) — then `path = base / ".goga" / "tools" / tool / filename` →
   checkpoint: identical composition to the writer
   (`goga/onboarding/generator/generator.py`: `Path(".goga") / "tools" / tool`) ✓.
4. **Step**: `path.exists()` False → return `None` → checkpoint: absence is the normal
   state, never an error ✓ (mirrors `load_home_config`).
5. **Step**: present file → `yaml.safe_load(path.read_text(encoding="utf-8"))`, return
   the parsed value as-is (mapping, list, string, scalar, `None` for an empty file) →
   checkpoint: no `isinstance` checks, no models, no merge, no cache ✓.
6. **Output**: `object | None` to the caller.

#### Checkpoint Summary
- Path standard ↔ write side: passed (same segments, verbatim filename).
- Error ordering: passed (guard before read).
- Raw passthrough: passed (no content decision at any step).

### Trace: `build_injections` (and the `tool` command)

#### Chain
1. **Input**: `main` — the imported `goga_tool_<name>` entry callable; `tool` — the
   dispatched `name` (the directory owner of the config files).
2. **Step**: `inspect.signature(main).parameters` filtered to
   `POSITIONAL_OR_KEYWORD | KEYWORD_ONLY` → checkpoint: positional-only, `*args`,
   `**kwargs` skipped ✓ (unchanged behavior).
3. **Step**: for each parameter, `_OFFERED_INJECTIONS.get(param.name)` — the dict is
   `{"ast": lambda _tool: _build_ast(), "config": lambda tool: load_tool_config(tool,
   "config.yml")}` → checkpoint: the offered set stays the single source of opt-in; any
   other name never triggers a build ✓.
4. **Step**: lazy build — `ast` constructs `AST(".")` + `.load()` per the `loading`
   practice; `config` calls `load_tool_config` → checkpoint: both builders run only
   when `main` declares the parameter ✓; the config value is raw data or `None` ✓.
5. **Output**: `dict[str, object]` forwarded as `main_fn(list(ctx.args), **injections)`
   by the command; a load failure of either source raises out of `build_injections` and
   the command renders `Failed to load project AST or tool config: {exc}`, exit 1 →
   checkpoint: user-facing message + code 1, no traceback ✓ (contract "Manifest load
   failure → user-facing message").

#### Checkpoint Summary
- Signature projection: passed (`Callable[[str], object]` builders, D8).
- Contract interaction with `load_tool_config`: passed (types line up: `str`, `str`,
  fixed `"config.yml"`; return `object | None` flows into `dict[str, object]`).
- AST behavior unchanged: passed (`_build_ast` untouched).

### Trace: `resolve_commit_message`

#### Chain
1. **Input**: `commit` — a resolvable commit hash (from `resolve_ref_commit`).
2. **Step**: `_run_git(["git", "log", "-1", "--pretty=format:%B", commit])` under the
   module's `LC_ALL=C`, `GIT_TERMINAL_PROMPT=0`, devnull-stdin env → checkpoint: same
   invocation discipline as every routine of `publish.py` ✓; the `format:` form emits
   the stored message byte-for-byte (the bare `%B` form appends one terminator newline).
3. **Step**: return `result.stdout` verbatim (the stored message byte-for-byte,
   trailing newline included) → checkpoint: no strip, no reformat ✓ (D10).
4. **Output**: `str`; an unresolvable commit raises `subprocess.CalledProcessError`
   (propagated raw — the caller's boundary wraps it as the clean git error).

#### Checkpoint Summary
- Read-only: passed (a `log` query mutates nothing).
- Verbatim contract: passed (`format:%B` emits the raw body byte-for-byte — no
  terminator newline).

### Trace: `resolve_publication_outcome`

#### Chain
1. **Input**: `own_tip` (hash), `twin_tip` (hash or None — the projection after the
   fetch).
2. **Step**: `twin_tip is None` → `"pushed"` (the push creates the twin) → checkpoint ✓.
3. **Step**: `twin_tip == own_tip` → `"up-to-date"` → checkpoint: equality precedes
   containment ✓ (contract Requirement).
4. **Step**: `is_ancestor(own_tip, twin_tip)` → `"remote-ahead"` — the twin strictly
   carries the local work → checkpoint: `is_ancestor(ancestor, descendant)` argument
   order verified against `goga/topics/git/exchange.py:74` ✓; equality already excluded,
   so "strictly" holds ✓.
5. **Step**: otherwise `click.ClickException` naming both tips + manual-git hint (D4) →
   checkpoint: clean error, no reconciliation attempt ✓.
6. **Output**: one of `pushed | up-to-date | remote-ahead`, or the clean error.

#### Checkpoint Summary
- Pure/read-only: passed (single containment probe, no mutation, no network).
- Outcome vocabulary: passed (exactly the three fixed kinds of the ADR).

### Trace: `publish_existing_topic`

#### Chain
1. **Input**: `identifier: str | None` (None = current topic), `year: str | None`.
2. **Step**: `resolved_year = year or current_year()`; `target =
   resolve_exchange_target(identifier, year)` → `ExchangeTarget(topic, branch, current)`
   → checkpoint: addressing identical to `update`/`propagate` (branch hosting no topic,
   remote-only twin → hint to switch — all reused) ✓; no version gate needed (D7) ✓.
3. **Step**: `origin_configured()` False → `ClickException("origin is not configured —
   publishing delivers to origin")` → checkpoint: before any network operation ✓.
4. **Step**: `own_tip = resolve_ref_commit(target.branch)` → checkpoint: local branch
   exists by construction of the target resolution ✓.
5. **Step**: `click.echo(_FETCHING_LINE.format(branch=target.branch))` **then**
   `fetch_branch(target.branch)`; `twin_tip = _projection(f"origin/{target.branch}")`
   → checkpoint: the reporting line precedes the fetch (sanctioned-network convention) ✓;
   an absent twin swallows `couldn't find remote ref` inside `fetch_branch` and the
   projection reads None ✓.
6. **Step**: `outcome = resolve_publication_outcome(own_tip, twin_tip)` (trace above).
7. **Step**: `pushed` → `push_branch(target.branch)` (creates the twin, binds upstream);
   `up-to-date`/`remote-ahead` → nothing mutated → checkpoint: no force, no lease on any
   path (only `push_branch` is reachable) ✓.
8. **Step**: `twin = _projection(f"origin/{target.branch}")`;
   `message = resolve_commit_message(twin)` → checkpoint: post-operation twin read (D12);
   for the idempotent outcomes this re-reads the already-known hash ✓.
9. **Step**: `identity = TopicIdentity(slug=target.topic, year=resolved_year,
   branch=target.branch)`; `TopicHooks().emit_published(identity,
   remote_branch=f"origin/{target.branch}", commit_hash=twin, commit_message=message,
   outcome=outcome)` → checkpoint: every success emits, idempotent outcomes included ✓;
   fire-and-forget soft emission cannot break the command ✓.
10. **Output**: `_PUBLISH_RESULT_LINE.format(...)` → `Published topic {year}/{slug} —
    {outcome}` (D3). Wrapper: the `publish_topic` exception boundary verbatim
    (`CalledProcessError` → "git failed:", `FileNotFoundError` → "git is not
    available:", `ImportError` → registry assembly, `OSError` → phase-neutral) →
    checkpoint: uniform clean-error boundary ✓.

#### Checkpoint Summary
- Sanctioned network set: passed (exactly one fetch + at most one push, both of the
  topic's own branch; reported by one stdout line).
- Ref immutability: passed (no local ref moved, created, or deleted).
- Emission contract: passed (shape matches the reshaped `emit_published` exactly).

### Trace: `TopicHooks.emit_published` / `TopicPublished`

#### Chain
1. **Input**: the five publication facts from the emitting site.
2. **Step**: construct `TopicPublished` (frozen kw_only dataclass; fields `identity`,
   `remote_branch`, `commit_hash`, `commit_message`, `outcome`) → checkpoint: field set
   and order match the CODEMANIFEST signature exactly ✓.
3. **Step**: `emit_hook_event(_run_registry(), "topics", "topic_published",
   context_for=lambda _tool: context)` → checkpoint: address and soft error class
   unchanged (catalog record untouched) ✓; one registry per run shared with every other
   topics checkpoint ✓.
4. **Output**: nothing (fire-and-forget); a failing hook warns under the soft class and
   the walk continues — now stated as an explicit Requirement of the method.

#### Checkpoint Summary
- Interface ↔ context: passed (constructor = signature = emission parameters).
- Catalog: passed (`topics/topic_published` soft record untouched).

### Trace: `publish_topic` (changed step 9)

#### Chain
1. **Input**: post-push state in `_publish_topic`: `identity`, `applied` message,
   `commit` hash, `branch_name`.
2. **Step**: `hooks.emit_published(identity, remote_branch=f"origin/{branch_name}",
   commit_hash=commit, commit_message=applied, outcome="pushed")` → checkpoint: the
   built commit's facts are in hand — no `resolve_commit_message` here, matching the
   contract's "the commit hash and message of the built commit" ✓; outcome is
   `pushed` — a publication push just completed ✓.
3. **Output**: unchanged result line; rollback paths still fire nothing.

### Trace: `update_topic` (changed step 9)

#### Chain
1. **Input**: `_update_topic` after the refresh gauntlet; `publish=True`; the refreshed
   branch pushed by `_publish_refreshed_branch`.
2. **Step**: on the successful return of `_publish_refreshed_branch` (before
   `_emit_updated`): `tip = resolve_ref_commit(f"origin/{target.branch}")`;
   `TopicHooks().emit_published(TopicIdentity(slug=target.topic, year=resolved_year,
   branch=target.branch), remote_branch=f"origin/{target.branch}", commit_hash=tip,
   commit_message=resolve_commit_message(tip), outcome="pushed")` → checkpoint: fires
   exactly when a push completed — the `already-current` early return (line ~270 of
   `updating.py`) precedes `if publish:` and emits only `topic_updated` with
   `published=False` ✓; a failed publish push raises out of
   `_publish_refreshed_branch` before the emission ✓ (the confirmed update stands —
   single atomicity exception, unchanged).
3. **Output**: `_emit_updated(...)` then the result line, unchanged.

#### Checkpoint Summary
- Ordering: passed (publication before the update notification).
- No-push paths: passed (already-current emits no publication).

### Trace: `execute_propagation` (changed step 6)

#### Chain
1. **Input**: `_deliver(plan, base, own_tip)` after a successful `_plant_and_push(plan,
   base, delivery)`; `delivery` commit hash in hand.
2. **Step**: compute the pushed branch name exactly as `_plant_and_push` spelled the
   refspec: `remote = base.local_branch if base.local_branch is not None else
   plan.base_ref.removeprefix("origin/")`; emit `topic_published` with
   `remote_branch=f"origin/{remote}"`, `commit_hash=delivery`,
   `commit_message=resolve_commit_message(delivery)`, `outcome="pushed"` → checkpoint:
   covers both step-6 paths (local `push_branch`, write-through
   `push_revision_to_branch`) and the retry cycle — a rejected first attempt raises
   `_RejectedDeliveryError` out of `_deliver` (no emission), the retry re-enters
   `_deliver` and emits once on its success ✓.
3. **Step**: then `_emit_propagated(...)` → checkpoint: publication precedes the
   propagate notification ✓; `_nothing_to_do` returns before `_plant_and_push` — no
   publication ✓.
4. **Output**: unchanged result line.

#### Checkpoint Summary
- Emission exactly-once under retry: passed (single emission point after the push
  inside the per-attempt `_deliver`).
- Branch spelling: passed (mirrors the refspec target, including nested `origin/x/y`
  bases).

### Trace: `topics.publish` (CLI)

#### Chain
1. **Input**: `scope: _TopicsScope` (group `--year`), `identifier: str | None`.
2. **Step**: `line = publish_existing_topic(identifier, scope.year)` — no configuration
   read, no `_topics_section()` call → checkpoint: the contract's "Do not read the
   configuration" ✓.
3. **Step**: `click.echo(line)`; `click.get_current_context().exit(0)` → checkpoint:
   exit 0 on all three success kinds; a `ClickException` from the domain renders via
   click's standard handler (stderr, exit 1) ✓ (mirrors the `update` subcommand shape).
4. **Output**: one stdout line, exit code.

### Trace: catalog record

1. `_DECLARED_ACTIONS` gains `Action(domain="schema", name="validate_schema",
   error_class="hard")` beside the `amend_cell` line; `declared_actions()` sorts by
   (domain, name) so the two schema actions stay adjacent → checkpoint: additive, no
   record rewritten; the topics records untouched ✓. Behavior: `hooks.subscribe` envelope
   validation and emission resolution accept the new address immediately (the catalog is
   the single source).

### Trace: `SchemaNode` / `Violation` / `GateVerdict` / `SchemaValidation`

1. `SchemaNode` — frozen kw_only dataclass; `tools` defaults to
   `field(default_factory=dict)` ("empty when no tool contributed"); `children:
   list[SchemaNode]` recursive; `dependencies: list[DependencyFacts]` (same module) →
   checkpoint: pure facts, nothing read inside; mirrors `CellFacts` ✓.
2. `Violation` — frozen kw_only `tool`/`hook`/`reason` → checkpoint: field-for-field the
   build-zone precedent ✓.
3. `GateVerdict` — frozen kw_only `violations` + derived `@property approved ->
   not self.violations` → checkpoint: derived property is not a constructor field,
   exactly the build-zone declaration ✓.
4. `SchemaValidation` (new `contexts.py`) — **non-frozen** kw_only (the buffer must be
   writable through `veto`); `tree: list[SchemaNode]` + `_veto: str | None =
   field(init=False, default=None, repr=False)`; `veto(reason)` assigns `self._veto =
   reason` (whole replacement, no hook identity recorded, empty reason stored as given)
   → checkpoint: `wrap_context` blocks attribute assignment on the proxy while calls
   pass through, so `context.tree = ...` raises and `context.veto(...)` works — the
   `BuildValidation` mechanism verbatim ✓.

### Trace: `SchemaHooks.validate_schema`

#### Chain
1. **Input**: `tree: list[SchemaNode]` — the final assembled tree in tree order.
2. **Step**: `registry = self._ensure_registry()` (shared with `amend_cell`; built once
   per run) → checkpoint: one enumeration per run ✓.
3. **Step**: resolve `schema.validate_schema` against `declared_actions`; a missing
   record → `ValueError("unknown hook action: schema.validate_schema")` → checkpoint:
   the emitting-side clean error, mirroring `amend_cell` ✓.
4. **Step**: group `registry.subscriptions_for("schema", "validate_schema")` per tool in
   enumeration order → checkpoint: no filtering by invitation ✓.
5. **Step**: per tool — `view = SchemaValidation(tree=_copy_tree(tree))` (deep fresh
   copy, D6); `proxy = wrap_context(view)`; snapshot `before = view._veto`; call
   `subscription.hook(**build_hook_arguments(subscription.hook, proxy,
   registry.self_context(tool)))`; a changed buffer attributes the veto to that
   subscription's name → checkpoint: mutual blindness + attribution-by-observation ✓.
6. **Step**: a raising hook → `crash = (subscription.name, str(reason))`, break that
   tool's remaining hooks; crash overrides the buffered veto; the walk continues with
   the next tool → checkpoint: walk-to-completion, one violation per tool, reason is
   `str(reason)` never a traceback ✓.
7. **Step**: collect — `crash` → `Violation(tool, crash[0], crash[1])`; else buffered
   veto → `Violation(tool, attributed_hook, view._veto)`; else no record → checkpoint:
   exactly one `Violation` per non-approving tool ✓.
8. **Output**: `GateVerdict(violations=...)` in enumeration order; no subscriptions →
   the empty approved verdict (the gate is inert with no tool packages) ✓.

#### Checkpoint Summary
- Platform primitives: passed (`per-tool-delivery` loop skeleton with the recorded
  refinement: no early stop, no contribution commit).
- Zone silence: passed (no printing; the verdict is data).

### Trace: `schema` routine (changed algorithm)

#### Chain
1. **Input**: `cells`, `max_depth`, `depends_on` — unchanged.
2. **Steps 1–5**: AST load, `_filter_tree`, `_build_cell_tree` per doc,
   `_filter_by_depends_on`, `_prune_depth`, early `return "[]"` when `result` is empty
   (D1) → checkpoint: unchanged behavior; no checkpoints fire on the empty assembly ✓.
3. **Step 5b (overlay)**: the `amend_cell` walk places `tools` on surviving nodes —
   unchanged → checkpoint: the gate sees the committed overlay ✓.
4. **Step 6 (new)**: `verdict = hooks.validate_schema([_to_schema_node(n) for n in
   result])`; `not verdict.approved` → `raise ValueError(merged)` (D11) → checkpoint:
   fires exactly once, after filters and overlay, before serialization; no partial JSON ✓.
5. **Step 7**: `return json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)`
   → checkpoint: an approved verdict leaves the output byte-identical (the projection is
   read-only over `result`; `_copy_tree` never touches the dicts) ✓.
6. **Output**: the JSON string, or `ValueError` listing every violation (tool, hook,
   reason).

#### Checkpoint Summary
- Gate placement: passed (single firing point, post-overlay, pre-serialization).
- Read-only projection: passed (`_to_schema_node` builds new records; `node.get("tools",
  {})` never writes back).

### Trace: `commands/schema` (verified, no code change)

`schema_logic` raising the merged `ValueError` is caught by the command's existing
`except Exception` → `click.echo(str(e), err=True)` + `ctx.exit(1)`; stdout stays empty,
no traceback → checkpoint: the extended step-2 enumeration is already implemented by the
current handler; only the contract text changed ✓.

---

## Algorithm Design

### `load_tool_config` (`goga/config/tool/loader.py`)

**Responsibility**: the read side of the tool-config standard — path standardization and
raw passthrough, nothing else.

```
1. GUARD filename: empty, ".", "..", or containing "/" or "\\"
   → raise ValueError(f"tool config file name must be a flat segment: {filename!r}")
2. base = root if root is not None else Path(".")        # the loaders' project-root anchor
   path = base / ".goga" / "tools" / tool / filename     # filename verbatim
3. IF NOT path.exists() → return None                    # absence is the normal state
4. RETURN yaml.safe_load(path.read_text(encoding="utf-8"))  # raw value, as parsed
```

**Errors**: `ValueError` (non-flat name — before any read); `yaml.YAMLError` (present
file fails to parse — propagated raw; interpreting is the consumer's job);
`OSError` (unreadable present file — propagated); `UnicodeDecodeError` (a `ValueError`
subclass — a present file not decodable as UTF-8; propagated raw and rendered by the
consumer's boundary, exactly as the project loaders' decode failures — the `tool`
command's except tuple already carries it).

**Edge cases**: empty YAML file → `yaml.safe_load` yields `None` → returned as-is (raw);
`tool` is never validated (platform identity); repeated calls re-read (no cache);
`root` override serves tests with a prepared tree; a binary (non-UTF-8) config file
raises `UnicodeDecodeError` out of the read — never a silent fallback.

Package: `goga/config/tool/__init__.py` — module docstring (zone description),
`from .loader import load_tool_config`, `__all__ = ["load_tool_config"]`.

### `build_injections` (`goga/commands/tool/tool.py`)

**Responsibility**: project the entry point's signature against the offered injections,
building each lazily; now tool-aware.

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

The `tool` command: `injections = build_injections(main_fn, name)`; the except clause
stays `(DocumentParseError, yaml.YAMLError, OSError, UnicodeDecodeError)` with the
message `Failed to load project AST or tool config: {exc}` (D9), stderr, `ctx.exit(1)`.
Import: `from ...config import load_tool_config` (the facade — the contract's import
site, exercising the re-export).

**Errors**: propagated raw from the builders; the command renders them.

**Edge cases**: `main` declaring neither name → `{}` (no file read, no AST build);
`config` declared but file absent → `None` injected; `ast` behavior byte-identical.

### `resolve_commit_message` (`goga/topics/git/publish.py`)

```
1. result = _run_git(["git", "log", "-1", "--pretty=format:%B", commit])
2. RETURN result.stdout        # verbatim, byte-for-byte as stored (format: adds no
                              # terminator newline; the bare %B form would add one)
```

**Errors**: `subprocess.CalledProcessError` (unresolvable commit — propagated raw; git's
reason rides in `stderr`), `OSError` (spawn).

**Edge cases**: multi-line messages preserved byte-for-byte; works on any resolvable
revision (hashes only by contract usage).

Facade: add to `goga/topics/git/__init__.py` import list and `__all__` (before
`resolve_commit_tree`).

### `resolve_publication_outcome` (`goga/topics/publishing.py`)

```
1. IF twin_tip IS None → RETURN "pushed"
2. IF twin_tip == own_tip → RETURN "up-to-date"
3. IF is_ancestor(own_tip, twin_tip) → RETURN "remote-ahead"
4. RAISE click.ClickException(
     f"branch and origin twin diverged — own tip {own_tip}, twin tip {twin_tip}; "
     "reconcile manually with git, then re-run")
```

**Errors**: the divergence is the only error; reconciliation belongs to the user.

**Edge cases**: equality must be probed before containment (step order is normative);
a containment probe failure (`is_ancestor` raising above its yes/no pair) propagates as
a git infrastructure failure.

### `publish_existing_topic` (`goga/topics/publishing.py`)

```
_CONSTANT _PUBLISH_RESULT_LINE = "Published topic {year}/{slug} — {outcome}"

publish_existing_topic(identifier, year=None):
  TRY _publish_existing_topic(...) EXCEPT the publish_topic boundary verbatim:
    CalledProcessError → ClickException("git failed: {stderr}"); FileNotFoundError →
    "git is not available: {exc}"; ImportError → ClickException(str(exc)) (registry
    assembly); OSError → "cannot complete the publication: {exc}"

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

New imports in `publishing.py`: `fetch_branch`, `is_ancestor`, `resolve_commit_message`
into the `.git` import block; `_FETCHING_LINE`, `_projection` into the `.exchange`
import block.

**Errors**: clean errors at steps 3/6 + the wrapper; nothing else.

**Edge cases**: diverged twin → nothing mutated before the error (steps 1–5 are
read-only; the fetch updates only the remote-tracking ref); idempotent outcomes emit;
dirty working tree irrelevant (no working-copy operation anywhere); `identifier=None`
publishes the current topic.

### `TopicPublished` / `emit_published` (`goga/topics/hooks`)

`contexts.py` — replace the dataclass:

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

`events.py` — re-sign `emit_published(self, identity, remote_branch, commit_hash,
commit_message, outcome)`, build the context field-for-field, emit the unchanged
address. Docstrings carry the contract annotations (publication-centric semantics, soft
failure Requirement).

### `publish_topic` step 9 (`goga/topics/publishing.py`)

Replace the emission call in `_publish_topic` with the reshaped five-fact call
(`remote_branch=f"origin/{branch_name}"`, built-commit facts, `outcome="pushed"`).
Update the routine docstring's step 8 wording to the new facts. Nothing else moves.

### `update_topic` step 9 (`goga/topics/updating.py`)

After the `if publish: _publish_refreshed_branch(...)` succeeds and before
`_emit_updated(...)`, call the new private helper:

```
_emit_published_delivery(target, resolved_year)

_emit_published_delivery(target, year):
  tip = resolve_ref_commit(f"origin/{target.branch}")
  TopicHooks().emit_published(
      TopicIdentity(slug=target.topic, year=year, branch=target.branch),
      remote_branch=f"origin/{target.branch}",
      commit_hash=tip, commit_message=resolve_commit_message(tip), outcome="pushed")
```

New imports: `resolve_commit_message` (extend the `.git` block); `TopicIdentity` if not
already imported in `updating.py` (verify — `_emit_updated` currently builds no
identity... it does via `TopicIdentity` — already imported). Docstring: extend step 9
and the Requirements bullet per the contract.

### `execute_propagation` step 6 (`goga/topics/propagating.py`)

In `_deliver`, between `_plant_and_push(plan, base, delivery)` and the
`_emit_propagated` call:

```
_emit_published_delivery(plan, base, delivery)

_emit_published_delivery(plan, base, delivery):
  remote = base.local_branch if base.local_branch is not None
           else plan.base_ref.removeprefix("origin/")
  TopicHooks().emit_published(
      TopicIdentity(slug=plan.target.topic, year=plan.year, branch=plan.target.branch),
      remote_branch=f"origin/{remote}",
      commit_hash=delivery, commit_message=resolve_commit_message(delivery),
      outcome="pushed")
```

Docstring: extend step 6 and the Requirements bullet per the contract.

New imports: `resolve_commit_message` into the `.git` import block of
`propagating.py` (`TopicIdentity` is already imported — `_emit_propagated` builds
identities).

### `topics.publish` (`goga/commands/topics/topics.py`)

Registered between `update` and `propagate` (the CODEMANIFEST body order):

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

(Command-callback docstring rules apply: user-facing help, no Args/Returns/Raises.)
Import: `publish_existing_topic` joins the `goga/topics` import block of the module.

### Catalog record (`goga/hooks/catalog/catalog.py`)

`Action(domain="schema", name="validate_schema", error_class="hard"),` directly after
the `amend_cell` line. No other change; module docstring unchanged (the catalog is
data).

### `SchemaNode`, `Violation`, `GateVerdict` (`goga/schema/hooks/facts.py`)

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

(`SchemaNode` needs `from dataclasses import dataclass, field`; the module docstring
grows the three names.) Placement: all three directly after `DependencyFacts`, before
the module serves `CellAmendment`'s imports — the CODEMANIFEST body order.

### `SchemaValidation` (`goga/schema/hooks/contexts.py` — new module)

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

### `SchemaHooks.validate_schema` (`goga/schema/hooks/events.py`)

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

`_copy_tree(nodes)` — module helper: recursive fresh `SchemaNode` per node with fresh
`list(...)`/`dict(...)` at every level, the `tools` overlay values copied through
`_copy_json` (D6). Imports: `SchemaValidation` from `.contexts`; `GateVerdict`,
`SchemaNode`, `Violation` from `.facts`. Method docstring carries the full contract
annotation (the walk-to-completion refinement of `per-tool-delivery`).

`_copy_json(value)` — module helper of the same file: `dict` → a fresh dict with every
value copied recursively, `list` → a fresh list with every item copied recursively,
any scalar → as-is; the JSON-shape domain of a committed contribution (validated at
the tool commit point of `amend_cell`) covers exactly these forms. Used by both
`_copy_tree` and the caller-side `_to_schema_node`, so no nested overlay value is
shared between the caller's projection (the `result` dicts that serialize) and any
delivered view.

### `schema` routine (`goga/schema/schema.py`)

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

`_copy_json` is defined beside `_copy_tree` in `goga/schema/hooks/events.py` (the
zone that owns delivery isolation) and imported here as
`from .hooks.events import _copy_json` — the same private intra-package import
direction D5 establishes (`publishing.py` ← `.exchange`); the hooks zone never
imports the domain, so no cycle. One recursive JSON copy serves both the projection
builder and the per-tool delivery copy: no nested overlay value is shared between
`result`, the caller's projection, and any delivered view.

after the amend_cell loop, before the return:
    verdict = hooks.validate_schema([_to_schema_node(n) for n in result])
    if not verdict.approved:
        details = "\n".join(
            f"- tool {v.tool} / hook {v.hook}: {v.reason}" for v in verdict.violations)
        raise ValueError(f"schema validation failed:\n{details}")
    return json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
```

The early `return "[]"` stays (D1). The routine docstring gains the gate paragraph and
the `ValueError` case (vetoed gate). Import: `SchemaNode` joins the `.hooks` import (for
the helper annotation).

### Facade updates

- `goga/config/tool/__init__.py` — new (above).
- `goga/config/__init__.py` — `from .tool.loader import load_tool_config`;
  `"load_tool_config"` in `__all__` after `"load_project_config"`.
- `goga/topics/git/__init__.py` — `resolve_commit_message` in the `.publish` import
  block and `__all__` (before `resolve_commit_tree`).
- `goga/topics/__init__.py` — `from .publishing import publish_existing_topic,
  publish_topic, resolve_publication_outcome`; `__all__` gains `publish_existing_topic`
  (after `publish_topic`) and `resolve_publication_outcome` (after
  `resolve_propagation`).
- `goga/schema/hooks/__init__.py` — imports `.contexts.SchemaValidation`, `.facts`
  gains `GateVerdict, SchemaNode, Violation`; `__all__` becomes
  `["CellAmendment", "CellFacts", "DependencyFacts", "GateVerdict", "SchemaHooks",
  "SchemaNode", "SchemaValidation", "ToolContribution",
  "merge_cell_contributions"]`; the module docstring lists the gate surface.

---

## Cross-cutting Concerns

- **Error handling**: three clean-error boundaries, unchanged by this design —
  `goga/topics` wraps git/registry failures as `click.ClickException` (publish reuses
  the `publish_topic` wrapper verbatim); `goga/config` loaders raise `ValueError` for
  structural input errors and propagate `yaml.YAMLError` raw (the `tool` command renders
  either); `goga/schema` raises `ValueError` for AST errors, checkpoint hard failures,
  the gate veto (merged, every violation), and `ImportError` for broken facades —
  `commands/schema` prints the message to stderr and exits 1 with stdout empty and no
  traceback. The gate's crash reasons go through `str(reason)` — never a traceback.
- **Logging**: no new logging. The zones stay silent (`Do not print — the caller owns
  all output`); the platform's soft-failure warnings (topics emission) and hard-failure
  errors (schema) flow through the existing platform/channels. The gate verdict
  surfaces as the raised `ValueError`, not a log record (unlike build's `logger.error`,
  the schema command owns all output and renders it once).
- **Validation**: contract-level only, at the edges — the flat-name guard of
  `load_tool_config` (before any read), the signature projection of `build_injections`
  (the offered set is the single opt-in), the four-outcome classification (equality
  before containment), the envelope validation of the platform (`subscribe` against the
  catalog). No content validation anywhere on the config path (raw passthrough is the
  contract).
- **Caching**: none. `load_tool_config` re-reads on every call (contract Requirement);
  the gate projection is built once per run and deep-copied per tool (isolation, not
  caching); the run registries (`HookRegistry` in `SchemaHooks`, the module-level
  `_RUN_REGISTRY` of the topics zone) are the only shared per-run state and are built
  lazily exactly once.
- **Concurrency**: single-threaded CLI semantics; no new threads or async. Frozen
  dataclasses for facts; the only mutable surface (`SchemaValidation._veto`) is
  confined to one tool's view; `wrap_context` proxies block attribute assignment, so
  delivered views are write-protected.

---

## Usages Analysis

### `convention` (`.goga/usages/conventions.md`)
- **What it provides**: Python 3.10+ rules — relative intra-package imports, kw_only
  dataclasses, Google docstrings (CLI callbacks render help: no Args/Returns/Raises),
  blank-line block formatting, test layout `tests/<pkg>/test_<module>.py`, tmp_path for
  file I/O, mocked subprocess, handler-direct CLI tests.
- **Where used**: every changed cell references it globally; each new entity's
  annotation applies it for data-model rules and docstring style.
- **Why chosen**: the project-wide mandatory baseline.
- **How exactly**: kw_only frozen dataclasses for the three facts and `TopicPublished`;
  non-frozen for `SchemaValidation` (writable buffer); relative imports
  (`from ..git import ...` forms inside `goga/topics`); new test files mirror the
  source tree.

### `yaml` (inline, `goga/config/tool`)
- **What it provides**: `yaml.safe_load()` on the file text; PyYAML requirement.
- **Where used**: `load_tool_config` step 4.
- **Why chosen**: the project's YAML baseline (same as the home/project loaders).
- **How exactly**: one `yaml.safe_load(path.read_text(encoding="utf-8"))`, result
  returned as-is.

### `click` (`.goga/usages/cooks/click.md`)
- **Where used**: `commands/tool.tool`, `commands/topics.publish` (and the group).
- **How exactly**: `@topics.command("publish")` + `@click.argument("identifier",
  required=False)` + `@click.pass_obj`; `click.echo` for the one result line;
  `ctx.exit(0)`; user-facing callback docstring.

### `loading` (imported from `goga/ast/.usages/loading.md`)
- **Where used**: `build_injections` ast branch (unchanged `_build_ast`).
- **How exactly**: `AST(".")` at the dispatcher's CWD + `.load()`; errors pass through.

### `tool-configuration` (imported from `goga/config/.usages/tool-configuration.md`)
- **What it provides**: the consumer contract of `load_tool_config` — path standard,
  raw passthrough, absence-None, flat names, `root` override.
- **Where used**: `build_injections` config branch.
- **Why chosen**: the dispatcher is the first in-tree consumer; the practice is the
  bridge that keeps the injection honest to the standard.
- **How exactly**: `load_tool_config(tool, "config.yml")` — verbatim file name, no
  suffix logic.

### `exchanging` (imported from `goga/topics/git/.usages/exchanging.md`)
- **Where used**: `publish_existing_topic` (fetch + containment), 
  `resolve_publication_outcome` (containment).
- **How exactly**: `fetch_branch` (single sanctioned fetch of the own branch),
  `is_ancestor(own_tip, twin_tip)` for the strict-ahead probe; the reporting line is
  the caller's (`publishing.py` echoes it).

### `refs-and-switching` (imported from `goga/topics/git/.usages/refs-and-switching.md`)
- **Where used**: `publish_existing_topic` revision resolution.
- **How exactly**: `resolve_ref_commit` for the own tip and the twin projection —
  revision-as-git-resolves-it, read-only.

### `publishing` — git zone (imported from `goga/topics/git/.usages/publishing.md`)
- **Where used**: `publish_existing_topic` (the publication push), `resolve_commit_message`.
- **How exactly**: `origin_configured` probe before anything; `push_branch(branch)` —
  exactly the named branch, upstream-bound; the new "Reading publication facts" section
  documents `resolve_commit_message` for consumers.

### `checkpoints` — topics zone (imported from `goga/topics/hooks/.usages/checkpoints.md`)
- **Where used**: every publication emission site (`publish_topic`,
  `publish_existing_topic`, `update_topic`, `execute_propagation`).
- **How exactly**: one `TopicHooks()` per emission site sharing the run registry; facts
  from the operation's own data (the twin-tip read is the operation's own post-state);
  fire-and-forget under the soft class.

### `declaring-actions` (imported from `goga/hooks/.usages/declaring-actions.md`)
- **Where used**: `emit_published` (the emission contract).
- **How exactly**: unchanged `emit_hook_event` form with `context_for=lambda _tool:
  context` — the read-only context carries no buffer, one shared instance is lawful.

### `per-tool-delivery` (imported from `goga/hooks/.usages/per-tool-delivery.md`)
- **Where used**: `SchemaHooks.validate_schema` (and existing `amend_cell`).
- **How exactly**: the loop skeleton (group per tool, `wrap_context`,
  `build_hook_arguments`, `self_context`) with the gate's recorded refinement — run to
  completion, collect vetoes, no contribution commit; per-hook attribution by buffer
  snapshot.

### `registering-hooks` (imported from `goga/hooks/.usages/registering-hooks.md`)
- **Where used**: `SchemaValidation` (the hook signature receiving the view);
  tool-package-facing docs of `goga/schema/.usages/registering-hooks.md`.
- **How exactly**: hooks declare `context` (and optionally `self`); undeclared names
  receive nothing — `build_hook_arguments` is the single projection.

### `documents` / `beautiful_json` (local, `goga/schema`)
- **Where used**: the `schema` routine (unchanged) — AST load and the final
  `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)`.

### Imported-usages dependency links created
- `goga/commands/tool → goga/config`: types `load_tool_config`, usage
  `tool-configuration` (file exists: `goga/config/.usages/tool-configuration.md`).
- `goga/schema → goga/schema/hooks`: usages `checkpoints` (already) — now covering both
  checkpoints.
- `goga/commands/topics → goga/topics`: usage `publishing` (already imported; now also
  referenced by the `publish` subcommand annotation).

---

## `.usages/` Update

All files below were materialized by the apply-architecture stage from `arch.md`; this
design verified each against the final contracts. Status is post-verification.

### Cell: `goga/config`
- **`tool-configuration`** → `goga/config/.usages/tool-configuration.md` — **current**
  (new). Matches the loader contract (paths, None-absence, flat names, raw return,
  `root` override, single-writer standard). No additions needed.

### Cell: `goga/commands/tool`
- **`tool`** → `.usages/tool.md` — **current after one review fix**: purpose sentence,
  injection table row, `config` example, opt-in bullet all match the re-signed
  `build_injections`; the exit-code bullet now names the tool-config load failure
  beside the manifest one (D9 — both lazy sources render the one message).

### Cell: `goga/commands/topics`
- **`topics-command`** → `.usages/topics-command.md` — **current**: audience includes
  "publishing an existing branch"; the `## publish` section matches the subcommand
  (outcomes, exit codes, no flags, one line). No additions.

### Cell: `goga/commands/schema`
- **`schema`** → `.usages/schema.md` — **current**: "Validation failures" section
  matches the step-2 enumeration and D11 rendering. No additions.

### Cell: `goga/schema`
- **`registering-hooks`** → `.usages/registering-hooks.md` — **current after the
  applied fix (D2)**: two-action intro, `validate_schema` events row, "The validation
  view" section with the `SchemaNode` field list and `veto` example.

### Cell: `goga/schema/hooks`
- **`checkpoints`** → `.usages/checkpoints.md` — **current**: "Validate the final tree"
  section (projection sketch, `verdict.approved` gate, walk-to-completion, byte-stable
  no-subscription output). No additions.

### Cell: `goga/topics`
- **`publishing`** → `.usages/publishing.md` — **current**: new intro (both routines),
  outcome table, fetch/no-force/emission bullets. No additions.
- **`update`** → `.usages/update.md` — **current**: the `publish=True` emission bullet.
- **`propagate`** → `.usages/propagate.md` — **current**: the inherent-push emission
  bullet.
- **`registering-hooks`** → `.usages/registering-hooks.md` — **current**: reshaped
  `topic_published` row and context documentation; migration note present.

### Cell: `goga/topics/git`
- **`publishing`** → `.usages/publishing.md` — **current**: "Reading publication facts"
  section. No additions.

### Cell: `goga/topics/hooks`
- **`checkpoints`** → `.usages/checkpoints.md` — **current**: reshaped `emit_published`
  example and the `topic_published` facts paragraph.

No new `.usages/` files are required by this design beyond those above (the apply
stage created the two new ones: `tool-configuration.md` and the section set). No
CODEMANIFEST `Usages` references point at own `.usages/` files.

---

## Test Stack Trace

### General Setup

- Layout mirrors source: `tests/config/tool/test_loader.py` (+ `__init__.py`),
  `tests/commands/tool/test_tool.py`, `tests/topics/git/test_publish.py`,
  `tests/topics/test_publishing.py`, `tests/topics/test_updating.py`,
  `tests/topics/test_propagating.py`, `tests/topics/hooks/test_contexts.py`,
  `tests/topics/hooks/test_events.py`, `tests/schema/hooks/test_facts.py`,
  `tests/schema/hooks/test_contexts.py` (new), `tests/schema/hooks/test_events.py`,
  `tests/schema/test_schema.py`, `tests/commands/topics/test_topics.py`,
  `tests/commands/schema/test_schema.py`.
- File I/O → `tmp_path` exclusively (`load_tool_config` tree). Subprocess (git) →
  `mock.patch` at the module's `_run_git`/call sites per `convention`. Hooks platform →
  the shared fixtures `pin_package_environment` / `install_tool_package`
  (`tests/hooks/conftest.py`, re-exported by `tests/schema/hooks/conftest.py` and
  `tests/topics/hooks/conftest.py`) plus registry reset between cases (the existing
  conftest pattern of the two zones).
- CLI tests call handlers directly or via `CliRunner` with `COLUMNS` pinned (the
  existing `tests/commands/topics` pattern).
- Domain flow tests for publish mock the git boundary inside `goga.topics.publishing`
  at its import points (the `_wire_*` pattern of the topics cell tests) and run the
  real domain orchestration.

### Source File Registry

`goga/config/tool/loader.py`, `goga/config/__init__.py`,
`goga/commands/tool/tool.py`, `goga/topics/git/publish.py` (+ facade),
`goga/topics/publishing.py`, `goga/topics/updating.py`,
`goga/topics/propagating.py`, `goga/topics/hooks/contexts.py`,
`goga/topics/hooks/events.py`, `goga/topics/__init__.py`,
`goga/schema/hooks/facts.py`, `goga/schema/hooks/contexts.py`,
`goga/schema/hooks/events.py`, `goga/schema/hooks/__init__.py`,
`goga/schema/schema.py`, `goga/commands/topics/topics.py`,
`goga/hooks/catalog/catalog.py`, `goga/commands/schema/schema.py` (no change —
verified).

---

### Positive Tests

#### `test_load_tool_config_returns_raw_mapping`

**Setup**: `tmp_path` with `.goga/tools/coverage/config.yml` written as
`threshold: 10\nname: cov\n`.

**Input**: `load_tool_config("coverage", "config.yml", root=tmp_path)`

**Trace**:
```
load_tool_config("coverage", "config.yml", tmp_path)
  → flat-name guard: "config.yml" passes
  → path = tmp_path/".goga"/"tools"/"coverage"/"config.yml"; exists → True
  → yaml.safe_load(text)
returns: {"threshold": 10, "name": "cov"}
```

**Assertions**:
```
result == {"threshold": 10, "name": "cov"}
isinstance(result, dict)
```

**Sufficiency**: pins the raw-mapping passthrough — the primary contract of the read
side; prevents any future "helpful" coercion or validation from creeping in.

#### `test_load_tool_config_raw_value_kinds` (parametrized)

**Setup**: `tmp_path` trees per case — `list.yml` = `- a\n- b\n`; `str.yml` =
`just a name\n`; `empty.yml` = `` (empty file).

**Input**: `load_tool_config("t", <filename>, root=tmp_path)` per case.

**Trace**:
```
load_tool_config("t", "list.yml", tmp_path)   → yaml.safe_load → ["a", "b"]
load_tool_config("t", "str.yml", tmp_path)    → "just a name"
load_tool_config("t", "empty.yml", tmp_path)  → None (yaml parses empty to None)
```

**Assertions**:
```
("list.yml", ["a", "b"]), ("str.yml", "just a name"), ("empty.yml", None) — exact
```

**Sufficiency**: pins "whatever the YAML parses to" — the raw-passthrough rule over
every value kind, including the empty file (a present file yielding None must not be
confused with absence).

#### `test_load_tool_config_absent_file_returns_none`

**Setup**: `tmp_path` containing `.goga/` but no `tools/` directory at all.

**Input**: `load_tool_config("coverage", "config.yml", root=tmp_path)`

**Trace**:
```
guard passes → path composed → path.exists() False → return None
```

**Assertions**: `result is None` (and no exception).

**Sufficiency**: absence is the normal state of a tool config — the load must never
raise for a tool without a config file; this is the invariant the dispatcher's
injection relies on.

#### `test_config_facade_reexports_load_tool_config`

**Setup**: none (import-only).

**Input**: `from goga.config import load_tool_config`

**Trace**:
```
goga.config.__init__ → from .tool.loader import load_tool_config → __all__ entry
python -c "from goga.config import load_tool_config"  (facade check command)
```

**Assertions**: `callable(load_tool_config)`; `"load_tool_config" in
goga.config.__all__`; `load_tool_config is goga.config.tool.load_tool_config`.

**Sufficiency**: the facade is the contract surface consumers import; guards the
single-entry-point rule of the `goga/config` cell.

#### `test_build_injections_config_declared_loads_raw`

**Setup**: `tmp_path` cwd monkeypatched (`monkeypatch.chdir(tmp_path)`) with
`.goga/tools/coverage/config.yml` = `threshold: 5`; entry `def main(argv, *, config):
...`; mock `load_tool_config` at its import site
(`goga.commands.tool.tool.load_tool_config`) to record and return `{"threshold": 5}`
— or run real with the chdir.

**Input**: `build_injections(main, "coverage")`

**Trace**:
```
signature(main) → params [argv, config(KEYWORD_ONLY)]
_OFFERED_INJECTIONS.get("argv") → None (skipped); .get("config") → builder
builder("coverage") → load_tool_config("coverage", "config.yml") → {"threshold": 5}
returns: {"config": {"threshold": 5}}
```

**Assertions**:
```
injections == {"config": {"threshold": 5}}
```

**Sufficiency**: pins the second injection — name-based opt-in, the fixed file name,
and the raw value forwarded as a keyword argument.

#### `test_build_injections_config_absent_yields_none`

**Setup**: `tmp_path` cwd without any `.goga/tools`; `def main(argv, *, config=None):
...`.

**Input**: `build_injections(main, "coverage")`

**Trace**: builder → `load_tool_config` → absent → `None`.

**Assertions**: `injections == {"config": None}`.

**Sufficiency**: an absent config must inject None (never an error, never a skipped
injection) — the tool's declared parameter always receives a value.

#### `test_build_injections_ast_unchanged_and_both_together`

**Setup**: entry `def main(argv, *, ast, config): ...` in a `tmp_path` with a minimal
valid CODEMANIFEST tree and a tool config; run with `monkeypatch.chdir`.

**Input**: `build_injections(main, "coverage")`

**Trace**: both builders run; `ast` builds `AST(".")` + `.load()`; `config` loads raw.

**Assertions**: `set(injections) == {"ast", "config"}`;
`isinstance(injections["ast"], AST)`; `injections["config"] == {...}`.

**Sufficiency**: guards the coexistence of both injections and that the `ast` path is
byte-identical in behavior after the signature change.

#### `test_resolve_commit_message_verbatim`

**Setup**: `mock.patch("goga.topics.git.publish._run_git")` returning
`CompletedProcess(stdout="Create topic 'feat-x'\n")`.

**Input**: `resolve_commit_message("abc123")`

**Trace**:
```
resolve_commit_message("abc123")
  → _run_git(["git", "log", "-1", "--pretty=format:%B", "abc123"])
  → return stdout verbatim
```

**Assertions**:
```
result == "Create topic 'feat-x'\n"
mock.assert_called_once_with(["git", "log", "-1", "--pretty=format:%B", "abc123"])
```

**Sufficiency**: pins the verbatim contract (the stored message byte-for-byte — the
`format:` form adds no terminator newline, so the trailing newline is the stored one)
and the exact plumbing invocation; every publication context message flows through
here.

#### `test_resolve_publication_outcome_matrix` (parametrized — the four-outcome pin)

**Setup**: mock `goga.topics.publishing.is_ancestor` to
`(a, b) -> a == "base" and b == "tip"`-style table per case.

**Input**: pairs — `(own="tip", twin=None)`; `(own="tip", twin="tip")`;
`(own="tip", twin="ahead")` with `is_ancestor("tip","ahead") → True`;
`(own="tip", twin="other")` with `is_ancestor → False`.

**Trace**:
```
(twin None)          → step 1 → "pushed"            (is_ancestor never called)
(twin == own)        → step 2 → "up-to-date"        (is_ancestor never called)
(ancestor True)      → step 3 → "remote-ahead"
(ancestor False)     → step 4 → click.ClickException
```

**Assertions**:
```
["pushed", "up-to-date", "remote-ahead"] exact; diverged case —
pytest.raises(click.ClickException) with message containing both "tip" hashes
and the manual-git hint; equality case asserts is_ancestor was NOT called
```

**Sufficiency**: the four-outcome matrix is the core decision table of the feature;
the not-called assertion pins "equality precedes containment".

#### `test_publish_existing_topic_pushed_creates_twin_and_emits`

**Setup**: git boundary mocked at `goga.topics.publishing` import points:
`resolve_exchange_target → ExchangeTarget(topic="feat-x", branch="feat-x",
current=False)`; `origin_configured → True`; `resolve_ref_commit` → `"c1"` then (after
push) for `origin/feat-x` → `"c1"`; `fetch_branch`/`push_branch` recorded;
`_projection` → `None` before push (or real `_projection` with the mocked
`resolve_ref_commit` raising for the pre-push read and returning after);
`resolve_commit_message → "msg"`; `TopicHooks.emit_published` mocked; `click.echo`
captured.

**Input**: `publish_existing_topic("feat-x")`

**Trace**:
```
→ resolve_exchange_target("feat-x", None) → target
→ origin_configured() True
→ resolve_ref_commit("feat-x") → "c1"
→ echo "Fetching origin/feat-x..." → fetch_branch("feat-x")
→ twin projection → None
→ resolve_publication_outcome("c1", None) → "pushed"
→ push_branch("feat-x")
→ projection("origin/feat-x") → "c1" → resolve_commit_message("c1") → "msg"
→ emit_published(identity(slug="feat-x", year=<current>, branch="feat-x"),
    remote_branch="origin/feat-x", commit_hash="c1", commit_message="msg",
    outcome="pushed")
→ return "Published topic <year>/feat-x — pushed"
```

**Assertions**:
```
push_branch called exactly once with "feat-x"; no lease/force call sites invoked
fetch_branch called exactly once, after the echo line
emit_published kwargs == the five facts above
result == f"Published topic {year}/feat-x — pushed"
```

**Sufficiency**: the happy path end-to-end — the fetch-then-classify-then-push order,
the reporting line placement, and the publication-centric emission facts in one pin.

#### `test_publish_existing_topic_idempotent_outcomes_emit_and_mutate_nothing`

**Setup**: as above with the projection returning `"c1"` (up-to-date) and `"c2"` with
`is_ancestor("c1","c2") → True` (remote-ahead); `push_branch` mocked to fail the test
if called.

**Input**: `publish_existing_topic("feat-x")` per case.

**Trace**: classification short-circuits before the push; emission still fires with
the twin facts; result line names the outcome kind.

**Assertions**:
```
push_branch.assert_not_called()
emit_published called once per run with outcome="up-to-date" / "remote-ahead",
  commit_hash == the twin tip, commit_message == its message
result endswith "— up-to-date" / "— remote-ahead"
```

**Sufficiency**: pins the ADR decision that idempotent outcomes are successes that
emit — the "work is on origin" signal subscribers rely on — and that nothing is
mutated on them.

#### `test_update_publish_emits_publication_after_push`

**Setup**: the existing `test_updating.py` fixtures for a checkout-free merge update
with `publish=True`; `resolve_commit_message` mocked → `"merged message"`;
`emit_published` mocked on `TopicHooks`.

**Input**: `update_topic("feat-x", "origin/main", "merge", None, True, "2026")`

**Trace**:
```
... refresh gauntlet (existing mocks) ...
→ _publish_refreshed_branch("merge", target, own_tip, refs) → push_branch OK
→ resolve_ref_commit("origin/feat-x") → refreshed tip
→ emit_published(identity, remote_branch="origin/feat-x",
    commit_hash=tip, commit_message="merged message", outcome="pushed")
→ _emit_updated(..., published=True)
```

**Assertions**:
```
emit_published called once, kwargs exactly as above
emit_updated still called once with published=True
call order: emit_published before emit_updated (record call order across the two mocks)
```

**Sufficiency**: pins the new update-path emission — facts, ordering before the update
notification, and exactly-once.

#### `test_update_failed_publish_push_emits_nothing_update_stands`

**Setup**: the existing `test_updating.py` fixtures for a checkout-free merge update
with `publish=True`; `push_branch` mocked to raise
`subprocess.CalledProcessError(1, "git", stderr="origin rejected the update")`;
`emit_published` and `emit_updated` both mocked on `TopicHooks`.

**Input**: `pytest.raises(click.ClickException): update_topic("feat-x", "origin/main",
"merge", None, True, "2026")`

**Trace**:
```
... refresh gauntlet → plant (the update completes) ...
→ _publish_refreshed_branch → push_branch raises CalledProcessError
→ the exception propagates out of _update_topic before both emissions;
  the wrapper renders "git failed: origin rejected the update"
```

**Assertions**:
```
pytest.raises(click.ClickException, match="git failed")
emit_published.assert_not_called()
emit_updated.assert_not_called()
point_branch_at_commit of the addressee's branch was called exactly once
  (the confirmed update stands — no rollback of the topic branch)
```

**Sufficiency**: the contract's "the publication event fires exactly when a push
completed" and the single-atomicity-exception semantics — a failed publish push
suppresses the publication emission and the update notification alike while the
confirmed update stands; prevents a future reorder that emits before the push.

#### `test_propagation_push_emits_publication_before_propagated`

**Setup**: the existing `test_propagating.py` fixtures for a squash delivery;
`resolve_commit_message` mocked; both `TopicHooks` emissions mocked with a shared
recorder.

**Input**: `execute_propagation(plan, confirmed)` (per the existing suite's entry
pattern).

**Trace**:
```
_deliver → build delivery "d1" → _plant_and_push → push OK
→ emit_published(identity(slug, year, branch), remote_branch="origin/<base local>",
    commit_hash="d1", commit_message=<message of d1>, outcome="pushed")
→ emit_propagated(identity, base=..., strategy="squash", outcome="squashed")
```

**Assertions**:
```
emit_published called once with commit_hash == the delivery hash and
  remote_branch == f"origin/{base}"
recorder order: "published" strictly before "propagated"
```

**Sufficiency**: pins the inherent-push emission, its position before the propagate
notification, and the base-branch spelling of `remote_branch`.

#### `test_propagation_retry_cycle_emits_publication_exactly_once`

**Setup**: the existing `test_propagating.py` fixtures for a squash delivery; the
first `push_branch` call raises `subprocess.CalledProcessError(1, "git", stderr=" !
[rejected] main -> main (non-fast-forward)")`, the retry (second call) succeeds;
`resolve_commit_message` mocked; both `TopicHooks` emissions mocked with a shared
recorder.

**Input**: `execute_propagation(plan)` (per the existing suite's entry pattern).

**Trace**:
```
attempt 1: _deliver → build → _plant_and_push → push rejected →
  _RejectedDeliveryError raises OUT of _deliver — before the emission point
→ rollback → re-resolution (its own reported fetch) → _deliver again →
  delivery rebuilt → push succeeds → _emit_published_delivery fires once →
  _emit_propagated fires once
```

**Assertions**:
```
emit_published.call_count == 1
the single call carries commit_hash == the hash of the SECOND delivery build
recorder order: "published" strictly before "propagated"
emit_propagated.call_count == 1
```

**Sufficiency**: pins the retry-cycle half of the contract ("the step 6 paths and the
retry-cycle success included") — the rejected attempt emits nothing and the retry
does not double-emit; without this pin a future relocation of the emission above
`_plant_and_push` would emit on the rejected attempt unnoticed.

#### `test_emit_published_builds_context_and_emits_address`

**Setup**: `install_tool_package("goga_tool_rec", register_hooks=...)` recording the
delivered context; registry reset fixture.

**Input**: `TopicHooks().emit_published(identity, remote_branch="origin/feat-x",
commit_hash="c1", commit_message="m", outcome="pushed")`

**Trace**:
```
TopicPublished(identity=..., remote_branch=..., commit_hash=..., commit_message=..., outcome=...)
→ emit_hook_event(registry, "topics", "topic_published", context_for=...)
→ hook(context=proxy)
```

**Assertions**:
```
context.identity is identity; context.remote_branch == "origin/feat-x"
context.commit_hash == "c1"; context.commit_message == "m"; context.outcome == "pushed"
not hasattr(context, "todo")
```

**Sufficiency**: pins the reshaped context on the wire — the five fields present,
`todo` gone (the breaking reshape) — against a real platform delivery.

#### `test_validate_schema_approved_with_no_subscriptions`

**Setup**: `pin_package_environment` with zero tool packages; registry reset.

**Input**: `SchemaHooks().validate_schema([node("goga/a")])`

**Trace**: `_ensure_registry` builds; `subscriptions_for("schema",
"validate_schema")` → empty; `groups` empty; loop skipped.

**Assertions**: `verdict.approved is True`; `verdict.violations == []`.

**Sufficiency**: the inert-gate requirement — with no tool packages installed the gate
is a no-op that approves (this is what keeps plain `goga schema` byte-identical).

#### `test_validate_schema_collects_one_violation_per_tool_walk_to_completion`

**Setup**: `install_tool_package("goga_tool_alpha", ...)` subscribing two hooks:
`veto_alpha` (vetoes) and `noop_alpha` (records invocation);
`goga_tool_beta` subscribing `noop_beta` (records invocation).

**Input**: `verdict = SchemaHooks().validate_schema(tree)`

**Trace**:
```
groups: alpha → [veto_alpha, noop_alpha], beta → [noop_beta]
alpha: before=None → hook vetoes → buffer changed → attributed "veto_alpha";
  noop_alpha still invoked (per-tool hooks run in order)
beta: no veto, no crash → no record
returns GateVerdict(violations=[Violation("alpha", "veto_alpha", reason)])
```

**Assertions**:
```
len(verdict.violations) == 1
verdict.violations[0] == Violation(tool="alpha", hook="veto_alpha", reason=<reason>)
noop_alpha.invoked and noop_beta.invoked  — every subscribed tool ran to completion
```

**Sufficiency**: the walk-to-completion deviation is the gate's defining semantics —
one violation per tool, no early stop, non-vetoing subscribers still invoked after a
veto exists.

#### `test_validate_schema_crash_overrides_buffered_veto`

**Setup**: `install_tool_package("goga_tool_alpha", register_hooks=...)` subscribing,
in registration order: `veto_and_boom` — calls `context.veto("v")` and then raises
`RuntimeError("kaboom")` inside the same hook — and `later` (records its invocation);
registry reset fixture.

**Input**: `verdict = SchemaHooks().validate_schema(tree)`

**Trace**:
```
alpha: before=None → veto_and_boom vetoes (buffer "v", attributed "veto_and_boom")
  → the same hook raises → crash = ("veto_and_boom", "kaboom"); break
later never invoked (the tool's remaining hooks stop; the walk itself continues)
returns GateVerdict(violations=[Violation("alpha", "veto_and_boom", "kaboom")])
```

**Assertions**:
```
verdict.violations == [Violation("alpha", "veto_and_boom", "kaboom")]
"Traceback" not in verdict.violations[0].reason      # str(reason), never a traceback
later.invoked is False   # per-tool stop; no second record for the buffered veto
```

**Sufficiency**: pins the three crash rules in one ordering that actually exercises
the override — the crash reason replaces the buffered veto of the same tool, the
reason is `str(reason)` without a traceback, and the tool's remaining hooks stop
while the walk continues.

#### `test_schema_validation_veto_semantics_and_write_protection`

**Setup**: plain `SchemaValidation(tree=[...])`; `wrap_context` from `goga.hooks`.

**Input**: `view.veto("first"); view.veto("")` ; `proxy = wrap_context(view)`;
`proxy.tree` read; `proxy.tree = []` attempted.

**Trace**: buffer replaced whole; proxy reads pass; assignment raises.

**Assertions**:
```
view._veto == ""            # replacement is whole; empty reason stored as given
proxy.tree is view.tree     # reads pass through
pytest.raises(Exception): proxy.tree = []   # attribute assignment blocked
proxy.veto("via proxy") works; view._veto == "via proxy"
```

**Sufficiency**: the view is the tools-facing surface — the buffer rules and the
write-protection must hold exactly as `BuildValidation` established them.

#### `test_validate_schema_delivers_fresh_tree_copy_per_tool`

**Setup**: two tools; the tree's root node carries a committed tools overlay with a
nested value (`tools={"alpha": {"nested": {"k": 1}}}`). Tool one records
`id(context.tree)` and mutates `context.tree[0].types.append("x")`; tool two records
the ids and mutates `context.tree[0].tools["alpha"]["nested"]["k"] = 2` inside its
hook.

**Input**: `validate_schema(tree)` with a caller-owned `tree` list.

**Trace**: each tool gets `_copy_tree(tree)`; an in-place append and a nested overlay
write each die with their tool's view.

**Assertions**:
```
the two delivered tree objects are not the same object as each other or as the
  caller's tree
after the walk: caller_tree[0].types == original value (never mutated)
caller_tree[0].tools["alpha"]["nested"]["k"] == 1  (a nested write never pierces)
the nested dicts of the two delivered copies are distinct objects (id-disjoint)
every node of every delivered copy is a fresh object (id sets disjoint)
```

**Sufficiency**: pins D6 — mutual blindness between tools and the observe-and-veto
rule ("the gate modifies nothing") even against hostile in-place writes, the nested
`tools` values included (a write there would otherwise reach the caller's `result`
dicts and the serialized output).

#### `test_schema_gate_no_subscriptions_byte_identical`

**Setup**: `tmp_path` project with a small CODEMANIFEST tree (existing
`tests/schema/test_schema.py` fixtures); no tool packages.

**Input**: `schema([], None, [])` before and after the change (golden string).

**Trace**: filters → build → amendment walk (no subscriptions) → gate (approved) →
`json.dumps`.

**Assertions**: output equals the recorded golden JSON exactly (byte-for-byte, the
six-field map, no `tools` keys).

**Sufficiency**: the regression guard for "an approved verdict leaves the output
byte-identical" — the gate must not leak into serialization.

#### `test_schema_gate_veto_raises_merged_error_listing_every_violation`

**Setup**: `tmp_path` project; `goga_tool_alpha` vetoing `"cell goga/x: broken"`;
`goga_tool_beta` crashing `ValueError("nope")`; `goga_tool_gamma` vetoing with a
whitespace-only reason (`context.veto("   ")`).

**Input**: `pytest.raises(ValueError): schema([], None, [])`

**Trace**: amendment walk (approved) → projection → gate → three violations → raise.

**Assertions**:
```
str(exc) starts with "schema validation failed:"
"- tool alpha / hook <name>: cell goga/x: broken" in message
"- tool beta / hook <name>: nope" in message
"- tool gamma / hook <name>:    " in message   # empty reason stored as given and
                                               # rendered verbatim — a veto, not a pass
exactly one line per violation (count of "\\n" == violations count)
nothing printed to stdout (routine returns or raises only)
```

**Sufficiency**: the merged-error contract — every violation named with tool, hook,
reason; this is the exact string `goga schema` will render on stderr. The gamma case
pins that an empty reason still produces the tool's single Violation and renders
verbatim (the buffer rule: stored as given, never trimmed into approval).

#### `test_publish_subcommand_delegates_and_exits_zero`

**Setup**: `CliRunner`; `publish_existing_topic` mocked at
`goga.commands.topics.topics` import site returning `"Published topic 2026/feat-x —
pushed"`; a spy on `_topics_section` (must not be called).

**Input**: `runner.invoke(topics, ["publish", "feat-x", "--year", "2026"])` and
`runner.invoke(topics, ["publish", "--year", "2026"])`

**Trace**: callback → `publish_existing_topic("feat-x", "2026")` (then
`(None, "2026")`) → echo → `exit(0)`.

**Assertions**:
```
exit_code == 0; output == "Published topic 2026/feat-x — pushed\\n"
publish_existing_topic called with ("feat-x", "2026") / (None, "2026")
_topics_section (config read) never called
```

**Sufficiency**: pins the thin-wrapper contract — delegation with identifier + scoped
year, the one echo line, exit 0, and the no-configuration constraint.

#### `test_publish_subcommand_exit_zero_on_all_success_kinds` (parametrized)

**Setup**: as above; the domain mock returns the three success lines.

**Input**: one run per outcome line.

**Assertions**: `exit_code == 0` for `pushed`, `up-to-date`, `remote-ahead` alike;
output is the single line.

**Sufficiency**: the CLI contract "0 on success (the up-to-date and remote-ahead
outcomes included)" — prevents a future mapping that turns idempotent outcomes into
failures.

#### `test_schema_command_gate_failure_stderr_exit_one`

**Setup**: `tmp_path` project; vetoing tool package installed; `CliRunner`.

**Input**: `runner.invoke(schema_cmd, [])`

**Trace**: `schema_logic` raises the merged `ValueError` → `except Exception` →
`click.echo(str(e), err=True)` → `ctx.exit(1)`.

**Assertions**:
```
exit_code == 1
result.stdout == ""            # nothing on stdout
"schema validation failed:" in result.stderr
"- tool alpha / hook" in result.stderr
```

**Sufficiency**: the command-level gate contract — stdout stays data-clean, one merged
stderr error, exit 1 (verified against the current handler; the test locks it).

---

### Negative Tests

#### `test_load_tool_config_rejects_non_flat_names` (parametrized)

**Setup**: none (guard fires before any filesystem access — assert with a nonexistent
root).

**Input**: `load_tool_config("t", name, root=tmp_path)` for `name` in
`["", ".", "..", "a/b", "a\\b", "config.yml/../../x"]`.

**Trace**: guard → `ValueError` before `exists()`.

**Assertions**:
```
pytest.raises(ValueError, match="flat segment") for every case
and the filename appears in the message
```

**Sufficiency**: the traversal protection of the standard — a non-flat segment must be
a clean error naming the file, never a read.

#### `test_publish_existing_topic_diverged_is_clean_error_nothing_mutated`

**Setup**: boundary mocks — projection `"c2"`, `is_ancestor("c1","c2") → False`,
`push_branch`/`fetch_branch` recorded, `resolve_commit_message` failing the test if
called, `emit_published` mocked.

**Input**: `publish_existing_topic("feat-x")`

**Trace**: classification → step 4 error; no push, no emission, no message read.

**Assertions**:
```
pytest.raises(click.ClickException) with both "c1" and "c2" in str(exc)
  and "reconcile" in str(exc)
push_branch.assert_not_called(); emit_published.assert_not_called()
resolve_commit_message.assert_not_called()
```

**Sufficiency**: divergence is the only failure outcome of the operation — surfaced
clean, nothing mutated (steps before it are read-only), no partial events.

#### `test_publish_existing_topic_origin_unconfigured_before_network`

**Setup**: `origin_configured → False`; `fetch_branch` failing the test if called.

**Input**: `publish_existing_topic("feat-x")`

**Trace**: target resolved → probe False → error before the fetch.

**Assertions**: `pytest.raises(click.ClickException, match="origin is not
configured")`; `fetch_branch.assert_not_called()`.

**Sufficiency**: pins the probe-before-network ordering — the sanctioned-network rule
("nothing else ever fetches").

#### `test_resolve_commit_message_unresolvable_commit`

**Setup**: `_run_git` mocked to raise `subprocess.CalledProcessError(128, "git",
stderr="fatal: bad object")`.

**Input**: `resolve_commit_message("deadbeef")`

**Trace**: `_run_git` raises; propagated raw.

**Assertions**: `pytest.raises(subprocess.CalledProcessError)` — the caller wraps.

**Sufficiency**: the read-only git fact surface follows the zone's propagate-raw
convention; the domain boundary owns the clean rendering.

#### `test_build_injections_skips_unknown_and_positional_only`

**Setup**: `def main(a, /, argv, *, logger=None): ...` under `monkeypatch.chdir` with
no `.goga` (the config builder must not run).

**Input**: `build_injections(main, "coverage")`

**Trace**: `a` positional-only skipped; `argv`/`logger` not offered → skipped.

**Assertions**: `injections == {}`; no file access occurred (chdir to empty tmp_path;
`load_tool_config` mock not called).

**Sufficiency**: the offered-injection set stays the single source of opt-in — a
parameter with another name never triggers a build, lazily proven by the empty root.

#### `test_validate_schema_unknown_address_is_emitting_side_error`

**Setup**: `monkeypatch.setattr("goga.schema.hooks.events.declared_actions", ...)` with
the `validate_schema` record removed (the existing pattern of `test_events.py`).

**Input**: `SchemaHooks().validate_schema([])`

**Assertions**: `pytest.raises(ValueError, match="unknown hook action:
schema.validate_schema")`.

**Sufficiency**: mirrors the `amend_cell` guard — the address must exist in the catalog
before any delivery.

#### `test_tool_command_renders_config_load_failure_cleanly`

**Setup**: entry declaring `config`; `tmp_path` cwd with
`.goga/tools/t/config.yml` = `: : :` (malformed YAML); `CliRunner` (or direct handler
with a fake ctx per the suite's pattern).

**Input**: invoke `tool` with name `t`.

**Trace**: import OK → `build_injections` → `load_tool_config` → `yaml.YAMLError` →
command except → secho + `ctx.exit(1)`.

**Assertions**: `exit_code == 1`; `"Failed to load project AST or tool config:"` in
stderr output; no traceback in output.

**Sufficiency**: pins D9 — a broken tool config is a user-facing clean failure, not a
crash, and the message names the true source set.

---

### Edge Case Tests

#### `test_load_tool_config_rereads_no_cache`

**Setup**: `tmp_path` with `config.yml` = `k: 1`.

**Input**: `load_tool_config("t", "config.yml", root=tmp_path)` → rewrite the file to
`k: 2` → call again.

**Trace**: two independent reads.

**Assertions**: first `{"k": 1}`, second `{"k": 2}`.

**Sufficiency**: the no-caching Requirement — repeated calls observe the current file.

#### `test_load_tool_config_root_defaults_to_cwd`

**Setup**: `monkeypatch.chdir(tmp_path)` with the tree under the cwd.

**Input**: `load_tool_config("coverage", "config.yml")` (root omitted).

**Assertions**: returns the parsed mapping — the `Path(".")` anchor behaves exactly as
`load_project_config`'s.

**Sufficiency**: pins the None-anchor semantics (the contract's "project-root anchor of
the configuration loaders").

#### `test_schema_empty_tree_returns_early_no_gate`

**Setup**: `tmp_path` project; a vetoing tool package installed (a gate firing would
raise); `schema(["nonexistent-cell"], None, [])`.

**Input**: cells filter that empties the tree.

**Trace**: `_filter_tree` → empty `result` → early `return "[]"`.

**Assertions**: result == `"[]"`; the vetoing hook was never invoked (recorder).

**Sufficiency**: pins D1 — the empty assembly runs no checkpoints (gate included);
without this pin a later "fix" could start delivering empty views.

#### `test_update_already_current_publishes_and_emits_nothing`

**Setup**: update fixtures with `is_ancestor(base.tip, own_tip) → True`,
`publish=True`; `push_branch` failing the test if called; `emit_published` mocked.

**Input**: `update_topic("feat-x", "origin/main", "merge", None, True, "2026")`

**Trace**: the idempotent early return fires `emit_updated(already-current,
published=False)` and returns before the publish block.

**Assertions**: `push_branch` and `emit_published` never called; `emit_updated` called
with `outcome="already-current", published=False`.

**Sufficiency**: the requirement "an already-current outcome publishes nothing and
emits no publication — the event fires exactly when a push completed".

#### `test_propagation_nothing_to_do_emits_no_publication`

**Setup**: propagation fixtures with the reachability idempotency hit
(`is_ancestor(own_tip, base.tip) → True`); `emit_published` mocked.

**Input**: `execute_propagation(plan, ...)` per the suite's entry pattern.

**Assertions**: `emit_published` not called; `emit_propagated` called with
`outcome="nothing-to-do"`.

**Sufficiency**: "a nothing-to-do delivery pushes nothing and emits no publication" —
the counterpart of the inherent-push emission.

#### `test_publish_existing_topic_no_force_or_lease_callsites` (repo sweep)

**Setup**: static — `inspect.getsource(goga.topics.publishing)`.

**Input**: the source text of `publishing.py` within the `publish_existing_topic` /
`_publish_existing_topic` region.

**Assertions**: the region references no `push_branch_with_lease` and no
`--force`/`force-with-lease` spelling.

**Sufficiency**: "no force and no lease under any outcome" is a property of the code
shape, not just the calls — the sweep catches an added path a mock-based test would
miss (the plan's checklist sweep, pinned as a test).

#### `test_gate_leaves_caller_tree_untouched_after_run`

**Setup**: a real projection `nodes = [_to_schema_node(n) for n in small_dict_tree]`;
deep-copied snapshot; a subscribing tool that only reads.

**Input**: `validate_schema(nodes)` → approved.

**Assertions**: `nodes == snapshot` (deep equality) — the caller's records are the
same objects with the same contents.

**Sufficiency**: "the gate is observe-and-veto — the tree is never modified" from the
caller's side, complementing the per-tool copy test.

#### `test_facade_reexports_schema_gate_surface`

**Setup**: import-only.

**Input**: `from goga.schema.hooks import GateVerdict, SchemaHooks, SchemaNode,
SchemaValidation, Violation`.

**Assertions**: all five resolve; each is in `goga.schema.hooks.__all__`;
`SchemaNode`/`Violation`/`GateVerdict` are frozen dataclasses (kw_only).

**Sufficiency**: the zone facade is the contract surface for the schema domain's
consumers (`goga/schema` imports `SchemaNode`/`GateVerdict` through it).

#### `test_topics_facade_reexports_publish_routines`

**Setup**: import-only.

**Input**: `from goga.topics import publish_existing_topic,
resolve_publication_outcome`.

**Assertions**: both callable and present in `goga.topics.__all__`; same for
`from goga.topics.git import resolve_commit_message` and `from goga.config import
load_tool_config` (combined facade sweep).

**Sufficiency**: the three new library surfaces must be reachable exactly at their
contracted import sites (the checklist's facade checks, pinned).

---

## Additional Instructions for the Implementation Agent

- Implement strictly in the plan's cell order (1→11 of `arch.md`); every facade import
  of a later cell then resolves against an earlier one. Do not modify any CODEMANIFEST
  or `.usages/` file — the contracts are final (this design + `arch.md`); any perceived
  contract gap is escalated, not patched in code.
- New modules carry module docstrings in the zone style (see `goga/topics/publishing.py`
  and `goga/schema/hooks/events.py` for the pattern); every public function/method gets
  a Google-style docstring carrying its CODEMANIFEST annotation (Algorithm/Requirements/
  Constraints as sections), CLI callbacks excepted (help text rules).
- Facade checks after each cell: `python -c "from goga.config import
  load_tool_config"`, `... from goga.topics import publish_existing_topic,
  resolve_publication_outcome"`, `... from goga.topics.git import
  resolve_commit_message"`, `... from goga.schema.hooks import SchemaNode, Violation,
  GateVerdict, SchemaValidation"`.
- Update the module docstring of `goga/commands/topics/topics.py` (subcommand list) and
  `tests` docstrings per the mirror convention; the publish subcommand registers
  between `update` and `propagate`.
- Gates: `pytest tests/ -x` green; `ruff check` clean on every touched package; repo
  sweep for residual old `topic_published` wording (any `todo`-carrying publication
  context) across contracts, usages, and tests — expected hits only in history records
  and `TopicCreated.todo` (creation context, untouched).
- The `goga/build/hooks` zone is the reference implementation for the gate primitives;
  copy its mechanics (`veto` buffer, attribution snapshot, crash override) — do not
  redesign them. The topics emission sites reuse the existing `TopicHooks()` per-site
  construction.
- Python 3.10 compatibility: `from __future__ import annotations` in new modules;
  `X | None` annotations are fine under it; `kw_only=True`/`frozen=True` per the
  convention.
