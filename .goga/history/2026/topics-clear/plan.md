# Plan: `topics-clear`

Result of compiling `.goga/history/2026/topics-clear/design.md` (post design-review,
all 5 remarks fixed and user-approved) into a ralphex-compatible execution plan.

---

## Purpose

Implement the pointer-model topics board and the merged-topic clear over the existing
topics domain:

- **Board, pointer model** — `collect_topic_board` gains the primary own-branch filter
  (a topic keeps its records only when some ref of the FULL inventory has a branch part
  that normalizes into the topic slug) and the `topics` display filter;
  `aggregate_topic_board` gains the `topics` display filter and the remote-mode
  asymmetry requirement. A topic without its own branch appears in no view — it is
  history.
- **Deletion, shared assembly** — `_assemble_target` is rewritten once and shared by
  both resolvers: the own branch is name-based, a branchless topic with carriers is a
  clean error, a directory-only topic stays targetable, and `has_dir` is survivor-gated.
- **Clear scope** — new `resolve_clear_targets(base_ref, year)`: every own-branched
  topic of the year whose topic directory the base ref's tree carries, resolved
  read-only at the resolved base commit, executed by the unchanged `delete_topics`.
- **CLI** — `goga topics board` gains the repeatable `--topic` option; new
  `goga topics clear` subcommand (base ladder flag → `topics.base_ref` → clean error;
  one confirmation for the whole list; empty scope exits 0).

The most important gaps between contract and code: the four CODEMANIFESTs and the three
`.usages/` files are already materialized (apply-architecture stage; `goga lint` — 80
cells, 0 errors) while the implementation behind them still runs the old tree-hosted
semantics — no `resolve_clear_targets`, no `clear` subcommand, no `--topic` option, no
primary filter, and the old merged-work error in `_assemble_target`.

Overall strategy: implement strictly bottom-up — `goga/topics/deletion.py` (shared
`_assemble_target`, `resolve_clear_targets`, facade re-export) → `goga/topics/board.py`
(primary filter, `topics` params) → `goga/commands/topics/topics.py` (`--topic`,
`clear`) → integration tests over the real git cell.

## Context

### Contract Surface

All contracts below are ALREADY materialized in their CODEMANIFEST files and are
**read-only** for the implementation agent.

**Entity: `resolve_clear_targets`** (NEW — Routine)
- Type: function
- Declared `location`: `goga/topics/deletion.py`
- Facade obligation: must be importable from `goga.topics` (`__all__` gains it before
  `resolve_delete_targets`)
- Signature: `resolve_clear_targets(base_ref: str, year: str | None = None) -> targets: list[DeleteTarget]`
- Semantic requirements (from the CODEMANIFEST annotation): resolve the clear scope of
  one year against the base ref's tree — every own-branched topic whose history the
  base carries — into deletion targets; nothing is removed here. `base_ref` is any
  revision string git resolves, resolved by the caller; read-only, being on it is not
  an error. Branchless topics are out of scope silently; an empty scope yields `[]` —
  not an error. Targets are alphabetical by topic. The current branch being a target's
  own branch is a clean error asking to switch away first; the whole call cancels.
- Imported dependencies: `current_year`, `collect_history_tree`, `normalize_topic_slug`,
  `resolve_current_branch_name`, `resolve_history_root`, `remove_topic_dir` (from
  `goga/history`); `BranchRef`, `list_branch_refs`, `read_ref_tree_paths`,
  `resolve_ref_commit` (from `goga/topics/git`)
- Annotation context: `topic-paths` (year and tree-root patterns),
  `refs-and-switching` (inventory, tree-reading, revision-resolution patterns)

**Entity: `resolve_delete_targets`** (CHANGED — Routine)
- Type: function
- Declared `location`: `goga/topics/deletion.py`
- Facade obligation: importable from `goga.topics` (already exported)
- Signature: `resolve_delete_targets(identifiers: list[str], year: str | None = None) -> targets: list[DeleteTarget]` (unchanged)
- Changed semantics (algorithm step 4 rewritten): a topic without its own branch — no
  ref of the inventory whose branch part normalizes into the topic slug — is a clean
  error: the topic has no branch, there is nothing to delete — it is history. A topic
  with its own refs and other carriers loses its own refs only; its directory flag is
  survivor-gated. A topic directory no branch hosts stays targetable (no refs,
  directory only).
- Tiers, all-or-nothing, current-branch guard: unchanged.

**Entity: `DeleteTarget`** (CHANGED — data contract)
- Type: frozen kw-only dataclass
- Declared `location`: `goga/topics/deletion.py`
- Facade obligation: importable from `goga.topics` (already exported)
- Fields: `topic: str`, `branch: str | None` (the own local branch, or None),
  `remote: str | None` (the own origin twin short name, or None), `has_dir: bool`
- Changed semantics: `has_dir` is survivor-gated — True exactly when both hold:
  (a) the topic directory of the year exists on disk; (b) no branch surviving the
  deletion carries the topic in its tree. The survivors are the inventory minus the
  two refs the deletion removes — the target's own local branch and its origin twin.
  A non-origin remote-tracking ref named after the topic (e.g. `upstream/<slug>`)
  survives and gates the directory like any other survivor.

**Entity: `collect_topic_board`** (CHANGED — Routine)
- Type: function
- Declared `location`: `goga/topics/board.py`
- Facade obligation: importable from `goga.topics` (already exported)
- Signature: `collect_topic_board(year: str | None = None, remote: bool = False, hosts: tuple[str, ...] | None = None, topics: tuple[str, ...] | None = None) -> records: list[BoardRecord]`
- Changed semantics: algorithm step 8 is the new PRIMARY filter — a topic keeps its
  records only when it has its own branch: some ref of the full inventory of
  `list_branch_refs` — both local and remote-tracking entries — whatever `remote` mode
  enumerates — whose branch part (the whole name of a local branch, the short name of
  a remote-tracking ref) normalizes into the topic slug; a topic without an own branch
  is history and passes no records. Step 10 composes `hosts` and `topics` (both exact,
  union across values, AND across each other); the sort moved to step 11. `topics`:
  None or empty keeps every record; an unknown slug yields `[]`, never an error.
- Annotation context: `topic-paths`, `topic-statuses`, `refs-and-switching`

**Entity: `aggregate_topic_board`** (CHANGED — Routine)
- Type: function
- Declared `location`: `goga/topics/board.py`
- Facade obligation: importable from `goga.topics` (already exported)
- Signature: `aggregate_topic_board(records: list[BoardRecord], hosts: tuple[str, ...] | None = None, topics: tuple[str, ...] | None = None) -> entries: list[BoardEntry]`
- Changed semantics: step 7 composes the two display filters (exact, union within,
  AND across), applied AFTER the own-branch requirement — a filter never resurrects a
  topic without an own branch. New requirement: in remote mode a topic whose own
  branch exists only locally keeps its merged-host rows but produces no entry — the
  records carry no own-branch row for it; the local mode inventory covers every own
  branch. An unknown slug yields `[]`, never an error.

**Entity: `topics` group method `board`** (CHANGED)
- Type: click subcommand callback
- Declared `location`: `goga/commands/topics/topics.py`
- Facade obligation: registered on the `topics` group (the facade `__all__` keeps its
  four names — three renderers + the group)
- Signature: `board(remote: bool = False, info: bool = False, host: tuple[str, ...], per_host: bool = False, json_output: bool = False, topic: tuple[str, ...]) -> exit_code: int`
- Changed semantics: the repeatable `--topic` option (topic slugs, exact match, union
  across values, composed with `host`); the default view applies both filters at the
  `aggregate_topic_board` projection only, the per-host view at the collection.

**Entity: `topics` group method `clear`** (NEW)
- Type: click subcommand callback
- Declared `location`: `goga/commands/topics/topics.py`
- Facade obligation: registered on the `topics` group
- Signature: `clear(base_ref: str | None = None, yes: bool = False) -> exit_code: int`
- Subcommand surface: a `--base-ref` option, a `--yes/-y` flag
- Semantic requirements: base ladder — `base_ref`, otherwise the topics section of the
  effective `ConfigOverlay` (loaded via `load_project_config`; the load delivers the
  config amendment checkpoint via `ConfigHooks().amend_config(config=...)`); no base
  at all → clean error naming the flag and the configuration line, before anything
  else. NO current-HEAD rung (unlike `create`). Empty scope → one line, exit 0.
  Without `yes`: non-terminal → clean error; otherwise the topic-to-branch pairs and
  one confirmation for the whole list; declined → exit 0, nothing deleted.
- Annotation context: `deleting` (deletion and clear contracts of the domain),
  `project-configuration` (topics section schema), `click` (confirmation, echo,
  exit-code propagation)

### Re-exports

- `resolve_clear_targets` — source: the `From: goga/topics` import of the CLI cell
  (`goga/commands/topics/CODEMANIFEST` already lists it in `Imports.Types`); within the
  domain cell it is re-exported from `.deletion` onto the `goga/topics/__init__.py`
  facade — `__all__` gains it before `resolve_delete_targets`; the module docstring
  gains the merged-topic clear scope sentence (Task 1).
- The CLI cell facade (`goga/commands/topics/__init__.py`) keeps exactly its four
  names; only its module docstring changes — "the switching, deletion, and clear
  procedures" (Task 3).

### Usages Context

- `convention` (`.goga/usages/conventions.md`): Python rules — relative imports,
  `dataclasses` with `kw_only=True`, Google-style docstrings, the CLI command
  docstring rule (no Args/Returns/Raises in click callback docstrings), the test
  structure and mock policy (mock at import points, real disk via `tmp_path`).
  Relevant to every task.
- `click` (`.goga/usages/cooks/click.md`): group/command/option construction,
  repeatable options, `click.confirm`, `click.echo`, exit-code propagation,
  clean-error rendering. Relevant to Task 3 (and the confirmation shape tested there).

### Imported Usages

- `topic-paths` (from `goga/history/.usages/topic-paths.md`): the year/tree-root path
  grammar. Used by Tasks 1 and 2 (year prefix composition — the same
  `<root>/<year>/` shape as `_hosted_slugs`).
- `topic-statuses` (from `goga/history/.usages/topic-statuses.md`): the status-scale
  patterns. Used by Task 2 (scale assembly and maximal-status computation — unchanged
  core).
- `refs-and-switching` (from `goga/topics/git/.usages/refs-and-switching.md`): branch
  inventory, ref-tree reading without checkout, revision resolution. Used by Tasks 1
  and 2 (`resolve_ref_commit` + `read_ref_tree_paths` at the resolved commit — covered
  by the Applied Fix that widened the git-cell `ref` annotation). Current; no update
  required.
- `deleting` (from `goga/topics/git/.usages/deleting.md`): the symmetric
  local-and-origin removal and restore-on-failure patterns. Used by Task 1
  (`delete_topics` unchanged — consumes the targets of either resolver).
- `deleting` (from `goga/topics/.usages/deleting.md`): consumer documentation of the
  deletion and clear contracts (includes "Resolving the clear scope of a year"). Used
  by Task 3 (CLI `clear` annotations). Current; no additions.
- `topic-board` (from `goga/topics/.usages/topic-board.md`): the board contract for
  consumers (pointer-only semantics, both filters). Used by Task 3 (CLI `board`).
  Current; no additions.
- `project-configuration` (from `goga/config/.usages/project-configuration.md`): the
  topics-section schema (`topics.base_ref`). Used by Task 3 (the clear base ladder).
- `checkpoints` (from `goga/config/hooks/.usages/checkpoints.md`): the config
  amendment checkpoint delivered at load time. Used by Task 3 (the lazy
  `_topics_section()` helper — identical to `create`).
- `beautiful_json`, `registering-hooks`, `switching`, `creating`, `publishing`,
  `todo-entry`: unchanged consumers; no action in this plan.

### Local Usages

No new `.usages/` files — the clear flow lives inside the existing deletion domain of
both cells. The three files touched by the design are already materialized and were
verified current by the design review:

- `goga/topics/.usages/topic-board.md` — replaced (pointer-only board, `topics`
  filter, per-host completeness clause dropped). No additions.
- `goga/topics/.usages/deleting.md` — replaced (pointer-model deletion semantics, the
  "Resolving the clear scope of a year" section). No additions.
- `goga/commands/topics/.usages/topics-command.md` — extended (`--topic` filter, the
  "Clearing merged topics" section, exit-codes paragraph). No additions.
- `goga/topics/git/.usages/refs-and-switching.md` — current; no file change (the
  widened CODEMANIFEST annotation is the authoritative contract).

### External Dependencies

- `click` — the CLI framework and the domain's clean-error type
  (`click.ClickException`); version already pinned in the project.
- git via subprocess — through the `goga/topics/git` cell only (`list_branch_refs`,
  `read_ref_tree_paths`, `resolve_ref_commit`, `delete_local_branch`,
  `delete_remote_branch`, `create_branch_at_commit`); never called directly from the
  domain or CLI cells.
- `yaml` — read by the CLI's `_topics_section()` config path (existing import).
- pytest + ruff — the test and lint gates (`pytest>=8.0`, `ruff>=0.15.0` in
  `pyproject.toml`).

### Entity Interaction and Data Flow (from the design, verbatim)

```
goga/commands (root group)
  └── topics (goga/commands/topics/topics.py, click.Group, --year/-y)
        ├── board  --remote/-r --info/-i --host* --topic* --per-host --json
        │     ├── collect_topic_board(year, remote, [hosts, topics])   → list[BoardRecord]
        │     ├── aggregate_topic_board(records, [hosts, topics])      → list[BoardEntry]
        │     └── render_topic_board | render_topic_host_rows | render_board_json
        ├── create ── create_topic …
        ├── switch ── switch_topic …
        ├── delete ── resolve_delete_targets → confirm → delete_topics
        └── clear   ── _topics_section (load_project_config + ConfigHooks.amend_config)
                      → resolve_clear_targets(base, year) → confirm → delete_topics

goga/topics (domain)
  ├── board.py        BoardRecord, collect_topic_board, BoardEntry, aggregate_topic_board
  ├── deletion.py     DeleteTarget, resolve_delete_targets, resolve_clear_targets, delete_topics
  ├── goga/history    normalize_topic_slug, current_year, collect_history_tree,
  │                   resolve_current_branch_name, resolve_history_root, remove_topic_dir
  └── goga/topics/git list_branch_refs, read_ref_tree_paths, resolve_ref_commit,
                      delete_local_branch, delete_remote_branch, create_branch_at_commit
```

**Data Flows** (verbatim):

- **Board, default view**: `board` callback → `collect_topic_board(scope.year, remote)`
  (no display filters — the hosts lists need every hosting branch) →
  `aggregate_topic_board(records, host, topic)` → renderer. The `topic` filter applies
  at the projection, exactly as `host`.
- **Board, per-host view**: `board` callback → `collect_topic_board(scope.year, remote,
  hosts=host, topics=topic)` → `render_topic_host_rows`. Both display filters apply at
  the collection.
- **Delete**: `delete` callback → `resolve_delete_targets(identifiers, scope.year)` →
  confirmation → `delete_topics(targets, scope.year)` → one result line.
- **Clear**: `clear` callback → base ladder (flag → `topics.base_ref` of the effective
  `ConfigOverlay` → clean error) → `resolve_clear_targets(base, scope.year)` → empty
  scope short-circuits (one line, exit 0) → confirmation → `delete_topics(targets,
  scope.year)` → one result line.
- **Clear resolution internals**: `resolve_clear_targets` → `current_year` →
  `list_branch_refs` → `resolve_ref_commit(base_ref)` (validates resolvability) →
  `read_ref_tree_paths(commit, <history-root>/<year>/)` (base tree topics) →
  own-branched set from the inventory names → scope = intersection → per-topic
  `DeleteTarget` assembly (own local branch, origin twin, survivor-gated `has_dir` via
  `collect_history_tree` + `read_ref_tree_paths`) → current-branch guard.

**Entity Dependencies** (verbatim): unchanged import graph (verified with
`goga schema`): the CLI cell imports `resolve_clear_targets` inside the existing
`From: goga/topics` block — the single new edge; `goga/commands` → CLI cell unchanged;
the domain import set unchanged. No cycles, no cross-imports. Design order (bottom-up):
`goga/topics/git` (wording only, already materialized) → `goga/topics` →
`goga/commands/topics` → `goga/commands` (annotation only, already materialized).

## Facts

- All four CODEMANIFEST changes and all three `.usages/` replacements are already
  materialized in the working tree (apply-architecture stage); `goga lint` reports
  80 cells, 0 errors; `goga schema` edges unchanged. The implementation lags behind
  its contracts — this plan closes that gap.
- The two Applied Fixes live in the contracts already: `read_ref_tree_paths`'s `ref`
  annotation accepts any resolvable revision; `resolve_delete_targets` step 4 is
  name-based over the full inventory.
- Current `goga/topics/deletion.py`: `_assemble_target` still raises the old
  merged-work error ("is hosted by … as merged work") and computes
  `has_dir = topic in disk and not merged`; no `resolve_clear_targets` exists.
- Current `goga/topics/board.py`: `collect_topic_board(year, remote, hosts)` — no
  `topics` parameter, no primary filter; `aggregate_topic_board(records, hosts)` — no
  `topics` parameter.
- Current `goga/commands/topics/topics.py`: `board` has no `--topic` option; no
  `clear` subcommand; `_topics_section()` already exists (used by `create`) and
  returns `TopicsConfig | None`.
- `TopicsConfig.base_ref: str | None` exists (`goga/config/project/config.py`).
- `resolve_ref_commit` propagates `subprocess.CalledProcessError` raw — the domain
  wrapper's `git failed: <stderr>` message carries git's own reason (the
  `publish_topic` precedent).
- `_short_name` lives in `goga/topics/board.py` and is already imported by
  `deletion.py`; `_hosted_slugs`, `_slugs_under`, `_disk_slugs`, `_normalized_name`,
  `_guard_current_branch` exist in `deletion.py` and are reused by the clear resolver.
- Test infrastructure to reuse: `_wire_resolution(monkeypatch, inventory, trees,
  current)` and `_disk_topic(tmp_path, year, slug)` in `tests/topics/test_deletion.py`;
  `_wire_board(...)`, `_base_inventory()`, `_base_trees()`, `_record(...)` in
  `tests/topics/test_board.py`; `_topics_module` / `_TtyStdin` in
  `tests/commands/topics/test_topics.py`; `_init_topic_repo` / `_init_publish_repo` /
  `_git` / `_git_out` in `tests/integration/test_topic_workflows.py`.
- `_wire_resolution`'s trees stand-in asserts the year prefix
  `.goga/history/2026/` and answers by ref display name — the base tree read for the
  clear resolver passes the resolved commit hash as the ref key.
- **Environment limitation (carried over from design and review)**: `pytest` and
  `ruff` cannot run in the current container — `.venv/bin/python` symlinks into
  `/opt/homebrew` (macOS-built). The full gates (`pytest tests/ -x`, `ruff check`)
  must run in a capable environment before the work is done.

## Gap Analysis

- Missing contract entities: `resolve_clear_targets` (domain), the `clear` subcommand
  (CLI).
- Missing facade exposure: `resolve_clear_targets` absent from
  `goga/topics/__init__.py` imports and `__all__`.
- API mismatches: `collect_topic_board` and `aggregate_topic_board` lack the `topics`
  parameter; the `board` callback lacks the `topic` parameter and the `--topic`
  option; `goga topics` registers four subcommands, the contract declares five.
- Behavioral mismatches: no primary own-branch filter in `_board_records` (branchless
  topics still produce records); `_assemble_target` uses the tree-based hosting rule
  and the non-survivor-gated `has_dir`; the branchless error message names a hosting
  branch; a bare branch shadowing a merged-work topic errors instead of resolving as
  the own branch.
- Docstring gaps: module docstrings of `deletion.py`, `board.py`, `topics.py`, both
  facades; `DeleteTarget` field docwords; `collect_topic_board` /
  `aggregate_topic_board` / `board` docstrings lack the `topics` filter and the
  pointer-model wording.
- Existing code that can be reused: everything — the tiers (`_identify`,
  `_tier_exact_branch`, `_tier_exact_slug`, `_tier_prefix`), `_hosted_slugs`,
  `_slugs_under`, `_disk_slugs`, `_normalized_name`, `_guard_current_branch`,
  `delete_topics` (unchanged), the clean-error wrappers, the CLI `_topics_section`,
  the confirmation block of `delete` (mirrored by `clear`), `_collapse_remote_twins`,
  `_marks_current`, `_branch_part`, `_topic_hosts`.
- Test coverage gaps: 28 new scenarios and 17 re-pinned tests enumerated in the tasks
  below (the design's Test Stack Trace, including the integration suite the design
  review added).
- No `location` changes; no visibility gaps in git (all files tracked).

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting
> the next. Within each coding task, contract tests are written first (TDD workflow).
> No infrastructure task is needed — both cells exist and their facades are assembled;
> the single facade change (the `resolve_clear_targets` re-export) belongs to Task 1,
> whose contract tests demand facade importability.

### Task 1: Deletion — the shared target assembly and the clear resolver (TDD coding)

Implements, in `goga/topics/deletion.py` (+ the `goga/topics/__init__.py` facade), the
contract entities `resolve_clear_targets` (new), the rewritten assembly behind
`resolve_delete_targets` (changed algorithm step 4), and the re-documented
`DeleteTarget`. The pointer model governs everything here: a topic exists exactly as
long as its own branch exists — the own branch is found BY NAME over the full
inventory (`_normalized_name(ref) == topic`), never by tree carriage; history is
communal and is never deleted. One assembly rule serves both resolvers — rewrite
`_assemble_target` once, never fork a second one.

**Contract — `DeleteTarget` (modified data contract, verbatim from the design):**

`has_dir` is True exactly when both hold: (a) the topic directory of the year exists on
disk; (b) no branch surviving the deletion carries the topic in its tree. The survivors
are the inventory minus the two refs the deletion removes — the target's own local
branch and its origin twin. A non-origin remote-tracking ref named after the topic
(e.g. `upstream/<slug>`) survives (it is not deletable through origin) and therefore
gates the directory like any other survivor. The own branch's own tree carrying the
topic does NOT gate the directory (`branch` is excluded from survivors — its tree dies
with the branch). Update the field docwords of `DeleteTarget` to the contract wording:
`branch` — the own local branch name, or None; `remote` — the own origin twin name, or
None; `has_dir` — the survivor-gated flag as above.

**Contract — `_assemble_target(topic, refs, hosted, disk)` (rewritten, shared by both
resolvers — verbatim algorithm from the design):**

```
1. own_named = [ref for ref in refs if _normalized_name(ref) == topic]
2. IF own_named is empty:
     IF any ref hosts the topic (topic in hosted[ref.name]):
         raise ClickException(f"topic {topic!r} has no branch — "
                              "there is nothing to delete; it is history")
     return DeleteTarget(topic, None, None, has_dir=topic in disk)   # directory-only hygiene
3. local_names = [ref.name for ref in own_named if not ref.remote]
   IF len(local_names) > 1:
     raise ClickException(f"several branches host topic {topic!r}: {names} — "
                          "remove all but one of them before deleting")
4. branch = local_names[0] if local_names else None
   twin = first ref in own_named that is remote and starts with "origin/"
   remote = short_name(twin.name) if twin else None
5. survivors = [ref for ref in refs
                if ref.name != branch and (twin is None or ref.name != twin.name)]
   carried = any(topic in hosted[ref.name] for ref in survivors)
   has_dir = topic in disk and not carried
6. return DeleteTarget(topic, branch, remote, has_dir)
```

Errors: branchless-with-carriers → clean error (it is history; the message names NO
hosting branch); several local own branches → the existing clean error naming them
(order-independent — keep the existing message text). Edge cases pinned by tests:
directory-only topic → targetable, `has_dir` from disk; own branch exists but its tree
does not carry the topic while another branch does → still the own branch (name-based),
`has_dir=False` if a survivor carries it; a non-origin tracking ref named after the
topic → `branch=None`, `remote=None`, and the surviving ref carrying the topic gates
`has_dir=False` (a deliberate no-op deletion that still reports and emits its event);
`resolve_delete_targets` keeps its tier fall-through and identifier-order
independence — the assembly always walks the full inventory.

**Contract — `resolve_clear_targets(base_ref: str, year: str | None = None) ->
targets: list[DeleteTarget]` (new — verbatim algorithm from the design):**

```
1. resolved_year = year or current_year()
2. refs = list_branch_refs()
   own_branched = { _normalized_name(ref) for ref in refs } - {""}
3. commit = resolve_ref_commit(base_ref)
   # unresolvable → CalledProcessError → the wrapper's clean error carrying the git reason
4. year_prefix = f"{resolve_history_root().as_posix()}/{resolved_year}/"
   base_topics = _slugs_under(read_ref_tree_paths(commit, year_prefix), year_prefix)
5. scope = sorted(base_topics & own_branched)
   IF scope is empty: return []
6. hosted = _hosted_slugs(refs, resolved_year); disk = _disk_slugs(resolved_year)
   targets = [_assemble_target(topic, refs, hosted, disk) for topic in scope]
7. _guard_current_branch(targets)
8. return targets (alphabetical by topic)
```

Verified chain checkpoints from the design's Code Stack Trace (transfer verbatim):
the clean-error wrapper mirrors `resolve_delete_targets` (`subprocess.CalledProcessError`,
`FileNotFoundError`, `OSError` → `click.ClickException`; an unresolvable base surfaces
as `click.ClickException(f"git failed: <git reason>")` — the `resolve_ref_commit`
stderr carries git's own message, identical to the `publish_topic` precedent);
`resolve_ref_commit` accepts any revision string and returns a commit hash (annotated
tags peel); reading at the resolved commit pins ONE snapshot (a moving ref is not
resolved twice) and costs one git invocation; resolve the base BEFORE the per-ref tree
reads and skip them entirely on an empty scope (empty scope costs 1 rev-parse + 1 base
ls-tree); the guard's slug arm stays for symmetry; the base is never moved or pushed;
being on the base is not an error — it is only read. Read set: 1 rev-parse + 1 base
ls-tree + N ref ls-trees + 1 disk walk — the same order as the delete resolution.
`delete_topics` is UNCHANGED — it consumes `list[DeleteTarget]` from either resolver;
the `has_dir` flag simply carries the survivor-gated decision.

Docstrings (Google style, per `convention`): `resolve_clear_targets` gets a full
docstring (Args / Returns / Algorithm / Requirements / Constraints / Raises); the
`resolve_delete_targets` docstring's assembly step is reworded to the pointer model
(branchless-with-carriers clean error naming no host; survivor-gated directory flag;
directory-only stays targetable); the `deletion.py` module docstring gains the
merged-topic clear scope wording (and loses the "keeps merged work out of scope"
tree-based phrasing).

Facade (`goga/topics/__init__.py`): add `resolve_clear_targets` to the
`.deletion` import block and to `__all__` (before `resolve_delete_targets`); the
module docstring gains the merged-topic clear scope sentence.

**Usages relevant to this task:**
- `convention`: relative imports, Google-style docstrings, kw-only frozen dataclass,
  test structure and mock policy (mock at `goga.topics.deletion` import points, real
  disk via `tmp_path` + `monkeypatch.chdir`).
- `topic-paths`: the `<root>/<year>/` prefix composition — reuse `_hosted_slugs` and
  `_slugs_under` verbatim; do not re-derive the path grammar.
- `refs-and-switching`: inventory, tree-reading, revision-resolution patterns —
  `resolve_ref_commit` + `read_ref_tree_paths(commit, prefix)` at the resolved commit
  (covered by the widened git-cell contract).
- `deleting` (git cell): the removal patterns consumed by the unchanged `delete_topics`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **Contract tests** (extend `TestDeletionContract` in `tests/topics/test_deletion.py`;
      expected to fail at this stage):
      `test_resolve_clear_targets_signature` — `inspect.signature` matches
      `(base_ref: str, year: str | None = None) -> list[DeleteTarget]`, positional-or-keyword
      parameters, `year` default `None`, `typing.get_type_hints` equality (mirror
      `test_resolve_delete_targets_signature`);
      `test_resolve_clear_targets_importable_from_the_cell_facade` —
      `from goga.topics import resolve_clear_targets`; identity with the module member;
      `"resolve_clear_targets"` in `goga.topics.__all__`.
- [x] **Code**: rewrite `_assemble_target` in `goga/topics/deletion.py` per the
      algorithm above — name-based `own_named`, the branchless-with-carriers clean
      error `f"topic {topic!r} has no branch — there is nothing to delete; it is
      history"`, the directory-only `DeleteTarget(topic, None, None, has_dir=topic in
      disk)`, the unchanged several-locals error, the origin-twin selection, and the
      survivor-gated `has_dir = topic in disk and not carried` (survivors = refs minus
      the own local branch and the twin); delete the old `hosts`/`eligible`/`merged`
      tree-based branches
- [x] **Code**: add `resolve_clear_targets` + its `_resolve_clear_targets` unwrapped
      core to `goga/topics/deletion.py` per the algorithm above — wrapper with the
      same exception set as `resolve_delete_targets`, base resolution before the
      per-ref reads, empty-scope early `[]`, shared assembly, guard; full Google
      docstring
- [x] **Code**: update the `DeleteTarget` field docwords, the
      `resolve_delete_targets` docstring assembly step, and the module docstring to
      the pointer-model wording
- [x] **Code**: re-export `resolve_clear_targets` from the `goga/topics/__init__.py`
      facade (import block + `__all__` before `resolve_delete_targets` + module
      docstring sentence)
- [x] **Interface verification**: run
      `pytest tests/topics/test_deletion.py -k "TestDeletionContract" -v` — all
      contract tests, old and new, must pass
- [x] **Logic tests** (new scenarios in `tests/topics/test_deletion.py`; setups and
      traces verbatim from the design — reuse `_wire_resolution`, `_disk_topic`,
      `_twin_inventory`/`_twin_trees`; additionally `monkeypatch.setattr(deletion,
      "resolve_ref_commit", ...)` returning a fixed hash, and for the unresolvable
      case raising `subprocess.CalledProcessError(returncode=128, cmd=[...],
      stderr="fatal: bad revision 'nope'")`; the base tree stand-in answers the commit
      key under the same `.goga/history/2026/` prefix):
      - `test_resolve_clear_targets_scope_is_the_intersection` — inventory
        `[BranchRef("feature-foo", False), BranchRef("origin/feature-foo", True),
        BranchRef("feature-bar", False), BranchRef("main", False)]`; own-ref trees
        carrying `feature-foo` and `feature-bar`; base commit answers
        `[".goga/history/2026/feature-foo/prd.md",
        ".goga/history/2026/other-topic/prd.md"]`; disk has `feature-foo`; current
        `"main"`; input `resolve_clear_targets("origin/release/2.0.0", year="2026")`;
        trace: `own_branched = {feature-foo, feature-bar, main}`, `base_topics =
        {feature-foo, other-topic}` (other-topic branchless), scope `{feature-foo}`,
        assembly `branch="feature-foo"`, twin `"origin/feature-foo"`, survivors
        `{feature-bar, main}` carry nothing → `has_dir=True`, guard passes; assert
        `targets == [DeleteTarget(topic="feature-foo", branch="feature-foo",
        remote="feature-foo", has_dir=True)]`
      - `test_resolve_clear_targets_survivor_keeps_the_directory` — same setup but
        trees also carry `feature-foo` on `main` and the disk dir exists; input with
        base `"release/2.0.0"`; trace: survivors `{main}` carry `feature-foo` →
        `has_dir=False`; assert `targets[0].has_dir is False` (branch and twin
        unchanged)
      - `test_resolve_clear_targets_unresolvable_base_is_clean_error` —
        `resolve_ref_commit` raises the `CalledProcessError`; assert
        `pytest.raises(click.ClickException)` with `"fatal: bad revision"` in the
        message and no removal primitive invoked
      - `test_resolve_clear_targets_current_branch_guard` — the intersection scenario
        with current `"feature-foo"`; assert `pytest.raises(click.ClickException)`
        with `"switch away"` in the message
      - `test_resolve_clear_targets_several_local_own_branches_error` — inventory
        `[BranchRef("Feature/Foo", False), BranchRef("feature-foo", False)]`; base
        tree carries `feature-foo`; assert `"several branches"` in the message and
        both names in the message
      - `test_delete_topics_consumes_clear_targets_end_to_end` — real `delete_topics`
        with `resolve_ref_commit`/`delete_local_branch`/`delete_remote_branch`/
        `remove_topic_dir` patched as recorders (the `_wire_removal` pattern);
        `_disk_topic` created; target `DeleteTarget("feature-foo", "feature-foo",
        "feature-foo", True)`; input `delete_topics([target], year="2026")`; trace:
        capture commit → delete local → delete remote → remove directory → emit
        `topic_deleted`; assert the three removal calls happened in order, the disk
        dir is gone, the result line is exactly
        `"Deleted 1 topic(s) of 2026: feature-foo"`, and the event carries the
        composition (branch, twin, `directory_removed=True`)
      - `test_resolve_delete_targets_directory_only_stays_targetable` (edge) — no
        trees (nothing hosted); disk has `_disk_topic(tmp_path, "2026",
        "litter-topic")`; inventory `[BranchRef("main", False)]`; current `"main"`;
        input `resolve_delete_targets(["litter-topic"], year="2026")`; trace: slug tier
        resolves via disk → assembly: own_named empty, no carriers → directory-only;
        assert `targets == [DeleteTarget("litter-topic", None, None, True)]`
      - `test_resolve_delete_targets_own_branch_by_name_without_tree_carriage`
        (edge) — inventory `[BranchRef("feature-foo", False), BranchRef("main",
        False)]`; trees carry `feature-foo` on `main` only; disk has the dir; input
        `resolve_delete_targets(["feature-foo"], year="2026")`; trace: slug tier
        resolves (main hosts) → assembly: own_named `[feature-foo]` (name-based),
        survivors `{main}` carry it → `has_dir=False`; assert
        `targets == [DeleteTarget("feature-foo", "feature-foo", None, False)]`
      - `test_resolve_delete_targets_non_origin_remote_survivor_gates_directory`
        (edge — re-pin of
        `test_resolve_delete_targets_non_origin_remote_is_not_the_twin`) — inventory
        `[BranchRef("upstream/feature-x", True)]`; trees carry `feature-x` on it;
        disk has the dir; current `"main"`; input
        `resolve_delete_targets(["feature-x"], year="2026")`; trace: own_named
        `[upstream/feature-x]` → no local, no origin twin → `branch=None,
        remote=None`; survivors = everything → upstream carries → `has_dir=False`;
        assert `targets == [DeleteTarget("feature-x", None, None, False)]` (was
        `has_dir=True` before — the pinned corner flip)
- [x] **Logic tests** (re-pin the existing behavior deltas in
      `tests/topics/test_deletion.py`, new expectations verbatim from the design):
      - `test_resolve_delete_targets_merged_topic_is_error` → rename to
        `test_resolve_delete_targets_branchless_topic_is_clean_error` and replace the
        body:
        inventory `[BranchRef("main", False), BranchRef("origin/main", True)]`; trees
        carrying `feature-x` on both; current `"other"`; input
        `resolve_delete_targets(["feature-x"], year="2026")`; trace: slug tier
        resolves feature-x (hosted) → assembly: own_named empty, main hosts it →
        ClickException; assert `"has no branch" in message`,
        `"nothing to delete" in message`, `"feature-x" in message`,
        `"main" not in message`
      - `test_resolve_delete_targets_slug_tier_names_one_topic_of_multi_topic_host`
        → the same branchless message: assert `"has no branch"` / `"feature-b"`;
        drop the `"merged work"` and `"main"` assertions (the new message names no
        hosting branch)
      - `test_resolve_delete_targets_integration_branch_named_directly_is_error` →
        the same replacement: `"cleanup"` stays, `"main"` goes
      - `test_resolve_delete_targets_bare_branch_shadow_reaches_merged_work_guard`
        → behavior flips from a clean error to a resolved target: the bare
        same-named branch is the own branch by name — expect
        `DeleteTarget("feature-x", "feature-x", None, has_dir=False)` (no disk
        directory; the merged host `main` survives and carries the topic)
      - `test_resolve_delete_targets_exact_name_falls_through_bare_branch_to_disk_topic`
        → the target gains the branch: expect
        `DeleteTarget("feature-foo", "feature-foo", None, has_dir=True)` — the bare
        branch is the topic's own branch under the pointer model; the tier
        fall-through itself is unchanged
- [x] **Debugging**: run `pytest tests/topics/test_deletion.py -x -v` — fix
      implementation code until all tests pass (do NOT fix test code; the expectations
      above are the design's verified traces)
- [x] **Contract re-verification**: facade (`from goga.topics import
      resolve_clear_targets`; `__all__` content), API shapes (both resolver
      signatures), behavior (pointer-model assembly, survivor gate, clean errors)
- [x] **Lint**: `ruff check goga/topics/` — fix formatting, apply decomposition if
      necessary

### Task 2: Board — the primary own-branch filter and the topics filters (TDD coding)

Implements, in `goga/topics/board.py`, the changed contract entities
`collect_topic_board` and `aggregate_topic_board`: the PRIMARY own-branch filter and
the `topics` display filter on both. The collection is the single source of board
facts; the aggregation is a pure projection. Nothing else in the collection changes —
statuses, todo summaries, twin collapse, and current marking stay exactly as they are;
the primary filter is inserted after the twin collapse and before the current marking,
and the display filters compose after it (so they can never resurrect a branchless
topic).

**Contract — `collect_topic_board` (modified — verbatim algorithm from the design):**

```
1. resolved_year = year or current_year()
2. scale = assemble_status_scale()
3. inventory = list_branch_refs()                # FULL inventory, both kinds
   current = resolve_current_branch_name()
   refs = remote-tracking entries of inventory if remote else inventory
4. per ref: topics_by_ref[ref] = _year_topics(read_ref_tree_paths(ref.name, root_prefix), year)
5. rows[(slug, ref.name)] = (ref.remote, maximal statuses, todo summary)   # working copy
   for the current branch's own topic and its merged topics, ref trees otherwise
6. rows = _collapse_remote_twins(rows)           # the local branch wins
7. own = { normalize_topic_slug(branch_part(ref)) for ref in inventory } - {""}
   where branch_part(ref) = ref.name            if not ref.remote
                          = short_name(ref.name) otherwise
   records = [record for record in records if record.topic in own]        # PRIMARY FILTER
8. records = [ … current=_marks_current(branch, current, remote) … ]
9. IF hosts non-empty: records = [r for r in records if r.branch in set(hosts)]
   IF topics non-empty: records = [r for r in records if r.topic in set(topics)]
10. records.sort(key=(scale_order[first maximal status], topic))
11. return records
```

Signature gains `topics: tuple[str, ...] | None = None` after `hosts` (mirror `hosts`).
**The primary filter reads the FULL `list_branch_refs()` inventory (`inventory`),
never the mode-sliced `refs`.** Verified checkpoints from the design's trace (transfer
verbatim): the branch-part rule (whole local name, short name after the first `/` for
remote-tracking) is the same rule `aggregate_topic_board` step 3 uses; a branchless
topic passes no records in any mode; a topic hosted only by a remote-tracking ref keeps
its row (the remote-tracking entry normalizes — existing behavior preserved); the
current branch's OWN topic row can never be a dropped row (the current branch is a
local ref of the inventory, so its slug sits in `own`) — while merged-topic rows hosted
by the current branch are marked and dropped with their branchless topics, markers and
all; edge — remote mode + own branch local-only → the local entry of the full inventory
passes the topic the primary filter, its merged-host remote rows stay, the projection
later hides the entry; edge — own branch exists but its tree carries no topic directory
→ the topic keeps records carried by other hosts (the primary filter is name-based),
the aggregated view produces no entry (a documented asymmetry).

**Contract — `aggregate_topic_board` (modified — verbatim algorithm from the design):**

```
1. scale = assemble_status_scale(); scale_order = {stage.name: index}
2. groups = {slug: [records]} (first-encounter order)
3. per slug:
     own = [r for r in group if normalize_topic_slug(_branch_part(r)) == slug]
     IF own is empty: continue                       # no entry, whatever hosts carry it
     winner = min(own, key=(not current, remote, branch))
     entry = BoardEntry(topic, winner.branch, _topic_hosts(group), winner.statuses,
                        winner.current, winner.remote, winner.todo)
4. entries.sort(key=(scale_order[first maximal status], topic))
5. IF hosts non-empty: entries = [e for e in entries if any(h in set(hosts) for h in e.hosts)]
   IF topics non-empty: entries = [e for e in entries if e.topic in set(topics)]
6. return entries
```

Signature gains `topics: tuple[str, ...] | None = None`. New requirement pinned by the
contract: in remote mode a topic whose own branch exists only locally keeps its
merged-host rows but produces no entry. Edge cases: empty `records` → `[]`; unknown
`hosts`/`topics` values → `[]`, never an error; a filter can never resurrect a topic
without an own branch (step 3 precedes step 5).

Docstrings: both functions' Google docstrings gain the `topics` parameter
(union-within / AND-across / empty-not-error wording of the contract), the primary
filter step, and the pointer-model responsibility phrasing ("of the topics that still
have their own branch"); the `board.py` module docstring moves to the pointer-model
wording.

**Usages relevant to this task:**
- `convention`: docstring style, test structure, mock-at-import-points policy.
- `topic-paths`: the slug normalization pattern (`normalize_topic_slug`) and the
  tree-root prefix (reuse `_history_prefix`).
- `topic-statuses`: scale assembly and maximal-status computation — unchanged core,
  the sort axis of both functions.
- `refs-and-switching`: the inventory and tree-reading patterns — unchanged; only the
  filter set over the inventory is new.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **Contract tests** (re-pin the two signature tests in `TestBoardContract` of
      `tests/topics/test_board.py`; expected to fail at this stage):
      `test_collect_topic_board_signature` → the parameter list gains `topics` with
      the `tuple[str, ...] | None` hint and the `None` default (mirror `hosts`);
      `test_aggregate_topic_board_signature` → the same for
      `(records, hosts, topics)`
- [x] **Code**: add the `topics` parameter to `collect_topic_board` (after `hosts`)
      and thread it into `_board_records`
- [x] **Code**: insert the primary filter in `_board_records` after the twin collapse
      and before the current marking — `own = {normalize_topic_slug(_short_name(
      ref.name) if ref.remote else ref.name) for ref in inventory} - {""}`, keep only
      records whose topic is in `own` (built from `inventory`, never the mode-sliced
      `refs`; reuse `_branch_part`-equivalent logic consistently)
- [x] **Code**: apply the `hosts` and `topics` display filters (exact membership, AND
      across the two) after the primary filter, then sort
- [x] **Code**: add the `topics` parameter to `aggregate_topic_board`, thread it into
      `_aggregate_board`, and apply it after the own-branch requirement and the sort
      (`entry.topic in set(topics)` when non-empty)
- [x] **Code**: update both docstrings and the module docstring to the pointer-model
      wording with the `topics` parameter
- [x] **Interface verification**: run
      `pytest tests/topics/test_board.py -k "signature" -v` — both signature tests
      pass
- [x] **Logic tests** (new scenarios in `tests/topics/test_board.py`; reuse
      `_wire_board`, `builtin_scale`, `_base_inventory`, `_base_trees`, `_record`,
      `_working_copy_topic`, `_working_todo`; setups and traces verbatim from the
      design):
      - `test_collect_topic_board_primary_filter_drops_branchless_topics` —
        `builtin_scale`; inventory `[BranchRef("main", False),
        BranchRef("origin/main", True)]`; trees
        `{"main": [".goga/history/2026/feature-x/plan.md"], "origin/main":
        [".goga/history/2026/feature-x/plan.md"]}`; current `"other"`; no
        working-copy topics; input `collect_topic_board(year="2026")`; trace: rows
        built for feature-x on main and origin/main → twin collapse drops the
        origin/main row → primary filter: `own = {"main"}`, feature-x not in own →
        the surviving main row drops too → sort of `[]` → `[]`; assert
        `records == []`
      - `test_collect_topic_board_primary_filter_uses_full_inventory_in_remote_mode`
        — inventory `[BranchRef("feature-foo", False), BranchRef("origin/main",
        True)]`; trees `{"origin/main":
        [".goga/history/2026/feature-foo/plan.md"]}` (the local branch's tree
        carries nothing); current `"feature-foo"`; `remote=True`; input
        `collect_topic_board(year="2026", remote=True)`; trace: refs =
        remote-tracking only → `[origin/main]`; row `(feature-foo, origin/main,
        ["planned"], current=False, remote=True)`; primary filter: own from FULL
        inventory `{"feature-foo", "main"}` → feature-foo passes; assert
        `[(r.topic, r.branch, r.remote) for r in records] == [("feature-foo",
        "origin/main", True)]`
      - `test_collect_topic_board_topic_filter_union_composition_and_unknown`
        (parametrized) — `_base_inventory()` + `BranchRef("feat/b", False)` so both
        topics are own-branched; `_base_trees()` plus `"feat/b":
        [".goga/history/2026/feat-b/prd.md"]`; inputs
        `topics=("feat-a",)`, `topics=("feat-a", "feat-b")`,
        `hosts=("origin/feat/a",), topics=("feat-b",)`, `topics=("nope",)`;
        trace: records built (feat-a on feat/a and origin/feat/a; feat-b on feat/b
        and origin/feat/b) → primary filter keeps both (`own = {feat-a, feat-b}`)
        → topics filter exact slug membership; hosts filter exact display-name
        membership; AND → unknown slug: no record matches → `[]`; assert topic sets
        per case: `{feat-a}`; `{feat-a, feat-b}`; `[]` (feat-b rows sit on
        `feat/b`/`origin/feat/b`, host `origin/feat/a` excluded); `[]`
      - `test_aggregate_topic_board_topic_filter_and_no_resurrection`
        (parametrized) — records built with `_record`:
        `[("feat-a","feat-a",["planned"]), ("feat-a","main",["planned"]),
        ("feat-b","feat-b",["defined"]), ("feat-b","main",["defined"])]`; inputs
        `topics=("feat-a",)`, `hosts=("main",), topics=("feat-b",)`,
        `topics=("ghost",)`; trace: groups; own-branch records (feat-a→feat-a,
        feat-b→feat-b); winners; sort; hosts: feat-a `[feat-a, main]`, feat-b
        `[feat-b, main]` → topics filter exact slug; hosts×topics compose AND →
        case 2: feat-b passes both, feat-a fails topics; ghost: no entry matches;
        assert `[e.topic for e in entries]` per case: `["feat-a"]`; `["feat-b"]`;
        `[]`
      - `test_aggregate_topic_board_remote_mode_local_own_branch_no_entry` (edge) —
        records (as a remote-mode collection would produce):
        `[_record("feat-a", "origin/main", ["planned"], remote=True)]` — merged-host
        row only; input `aggregate_topic_board(records)`; trace: own = records
        whose branch part normalizes into feat-a → origin/main short name "main" →
        none → no entry; assert `entries == []`
      - `test_collect_topic_board_own_branch_by_name_without_tree_carriage` (edge) —
        `builtin_scale`; inventory `[BranchRef("feature-foo", False),
        BranchRef("main", False)]`; trees `{"main":
        [".goga/history/2026/feature-foo/plan.md"]}` (the feature-foo tree carries
        nothing); current `"main"`; no working-copy topics; input
        `records = collect_topic_board(year="2026")`, then
        `aggregate_topic_board(records)`; trace: `own = {feature-foo, main}`
        (name-based, feature-foo from its branch name); row `(feature-foo, main)`
        built — main hosts the topic in its tree, current-marked (main is the
        current branch — the marked row is a merged-topic row, not an own row);
        primary filter: feature-foo ∈ own → the row stays (no own-branch row exists
        — the feature-foo tree is empty, so no `(feature-foo, feature-foo)` row, no
        twin collapse); aggregate: no record whose branch part normalizes into
        feature-foo → no entry; assert
        `[(r.topic, r.branch) for r in records] == [("feature-foo", "main")]` and
        `aggregate_topic_board(records) == []`
- [x] **Logic tests** (re-pin the existing board scenarios whose fixtures carry topics
      without their own branch — new expectations verbatim from the design):
      - `test_collect_topic_board_current_branch_hosts_merged_topics` → the
        branchless `feat-b` rows drop: add a `feat/b` branch to the fixture
        inventory, or assert the dropped rows, per the scenario's intent
      - `test_collect_topic_board_reads_todo_summaries_local_and_ref` → the
        branchless `main-only` row drops under the primary filter: host the
        `main-only` topic from a ref named after it, or drop the row from the
        expectation and keep the absent-todo coverage on an own-branched row
      - `test_collect_topic_board_current_branch_own_topic_wins_over_tree` → the
        merged `feat-b` row on `feat/a` drops: add a `feat/b` ref to the inventory
        or assert the dropped row
      - sweep every other board scenario whose inventory carries topics without
        their own branch (e.g. the todo-summary, twin, and projection scenarios) —
        add the own branch to the fixture inventory or assert the dropped rows, per
        each scenario's intent; a scenario may also need its hosts-column
        expectation revisited only where a dropped row fed it
- [x] **Debugging**: run `pytest tests/topics/test_board.py -x -v` — fix
      implementation code until all tests pass (do NOT fix test code beyond the
      sanctioned re-pins above)
- [x] **Contract re-verification**: signatures (`topics` parameter on both functions,
      `tuple[str, ...] | None` hint, `None` default), facade importability unchanged,
      behavior (primary filter over the full inventory in both modes; filters compose
      AND, empty-not-error; no resurrection)
- [x] **Lint**: `ruff check goga/topics/` — fix formatting, apply decomposition if
      necessary

### Task 3: CLI — the --topic option and the clear subcommand (TDD coding)

Implements, in `goga/commands/topics/topics.py` (+ the
`goga/commands/topics/__init__.py` module docstring), the changed `board` method and
the new `clear` method of the `topics` group. The CLI stays a thin wrapper: it resolves
inputs, delegates every computation to the domain, and confirms the deletion and the
clear. Domain errors surface as clean CLI errors.

**Contract — CLI `topics.board` (extended — verbatim sketch from the design):**

```
@click.option("--topic", multiple=True, default=(),
              help="Topic slug to keep — an exact match; repeatable, the union across values.")
def board(scope, remote=False, info=False, host=(), per_host=False, json_output=False, topic=()):
    …guard --json+--info…
    if not per_host:
        records = collect_topic_board(scope.year, remote)
        entries = aggregate_topic_board(records, host, topic)
    else:
        records = collect_topic_board(scope.year, remote, hosts=host, topics=topic)
    …render / json… exit 0
```

The `topic` param mirrors the established `host` param (declaration order, tuple type,
default `()`); the default view collects the FULL inventory (the hosts lists need
every hosting branch) and hands both filters to the pure projection alone; the
per-host view filters the collection. The callback docstring gains the `--topic`
sentence (CLI docstring rule: no Args/Returns/Raises).

**Contract — CLI `topics.clear` (new — verbatim sketch from the design):**

```
@topics.command("clear")
@click.option("--base-ref", default=None,
              help="Base whose tree defines the clear scope; beats topics.base_ref of .goga/config.yml.")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip the confirmation; sits after the subcommand token, unlike the group -y year.")
@click.pass_obj
def clear(scope, base_ref=None, yes=False) -> None:
    base = base_ref
    if base is None:
        section = _topics_section()
        base = section.base_ref if section is not None else None
    if base is None:
        raise click.ClickException(
            "no base for the clear — pass --base-ref or set topics.base_ref in .goga/config.yml:\n"
            "topics:\n  base_ref: origin/release/2.0.0")
    targets = resolve_clear_targets(base, scope.year)
    if not targets:
        click.echo("No merged topics to clear.")
        click.get_current_context().exit(0)
    if not yes:
        if not sys.stdin.isatty():
            raise click.ClickException(
                "the clear confirmation needs an interactive terminal — pass --yes/-y to skip it")
        for target in targets:
            click.echo(f"{target.topic} -> {target.branch or target.remote or '(directory only)'}")
        if not click.confirm(f"Clear {len(targets)} topic(s)?"):
            click.get_current_context().exit(0)
    click.echo(delete_topics(targets, scope.year))
    click.get_current_context().exit(0)
```

Verified checkpoints from the design's traces (transfer verbatim): the base ladder is
lazy — `_topics_section()` (`load_project_config` + `ConfigHooks().amend_config(
config=...)`, amendment summary lines to stderr, missing file = unset) runs only when
the flag is absent; "minus the current HEAD" — no `--from-current` rung, unlike
`create`; `TopicsConfig.base_ref: str | None` exists; the empty-scope line is one line,
yearless (the CLI cell imports no year oracle — the domain owns the default); the
confirmation mirrors `delete` line-for-line — `sys.stdin.isatty()` probe, the
topic-to-branch pairs, one `click.confirm` for the whole list, declined → exit 0 with
nothing deleted; `delete_topics(targets, year) -> str` matches; the `-y` collision
with the group `--year` resolves by position, exactly as `delete`. Import
`resolve_clear_targets` from `...topics` (the domain facade) and add it to the CLI
module's domain import block. The callback docstring follows the CLI docstring rule
(help text only). Module docstrings: `topics.py` gains the `clear` subcommand and the
`--topic` filter wording; `goga/commands/topics/__init__.py` — "the switching,
deletion, and clear procedures".

**Usages relevant to this task:**
- `convention`: the CLI command docstring rule, test structure, CliRunner patterns.
- `click`: repeatable options (`multiple=True`), `click.confirm`, `click.echo`,
  exit-code propagation, clean-error rendering; `sys.stdin.isatty()` for the
  non-interactive guard.
- `deleting` (domain practice): the deletion and clear contracts the CLI wraps.
- `topic-board`: the board contract (`--topic` routes exactly per the CODEMANIFEST
  algorithm steps 2–3).
- `project-configuration` + `checkpoints`: the topics-section schema and the config
  amendment checkpoint — the lazy `_topics_section()` helper, identical to `create`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] **Contract tests** (in `tests/commands/topics/test_topics.py`; expected to fail
      at this stage): `test_board_carries_the_topic_option` — the Click param is
      repeatable (`multiple=True`) with default `()` (mirror
      `test_board_carries_the_host_option`);
      `test_clear_carries_the_base_ref_option_and_yes_flag`;
      `test_clear_callback_signature` — the callback signature gains
      `topic: tuple[str, ...] = ()` on `board` and reads
      `(scope, base_ref=None, yes=False)` on `clear`;
      `test_clear_help_lists_the_surface` — the help text lists `--base-ref` and
      `--yes/-y` (CLI docstring rule); re-pin `test_board_callback_signature` → the
      parameter list gains `topic`; rename `test_topics_registers_four_subcommands` →
      `test_topics_registers_five_subcommands` asserting
      `["board", "create", "delete", "switch", "clear"]`;
      `test_facade_exports_four_names` stays valid UNCHANGED — `clear` registers on
      the group; the facade `__all__` keeps its four names (three renderers + the
      group)
- [ ] **Code**: add the `--topic` option and the `topic` parameter to `board` in
      `goga/commands/topics/topics.py`; route both filters per the sketch (default
      view: aggregate only; per-host view: collection); extend the docstring
- [ ] **Code**: add the `clear` subcommand per the sketch — the lazy base ladder, the
      empty-scope one-line exit 0, the terminal guard, the pairs + one confirmation,
      the delegation, the exact error-message texts:
      `"no base for the clear — pass --base-ref or set topics.base_ref in
      .goga/config.yml:\ntopics:\n  base_ref: origin/release/2.0.0"`,
      `"No merged topics to clear."`, `f"Clear {len(targets)} topic(s)?"`, and the
      terminal-guard message naming `--yes/-y`
- [ ] **Code**: import `resolve_clear_targets` from the domain facade; update the
      `topics.py` module docstring and the
      `goga/commands/topics/__init__.py` docstring ("the switching, deletion, and
      clear procedures")
- [ ] **Interface verification**: run
      `pytest tests/commands/topics/test_topics.py -k "Contract" -v` — all contract
      tests pass
- [ ] **Logic tests** (new scenarios in `tests/commands/topics/test_topics.py`;
      CliRunner, domain functions monkeypatched at
      `goga.commands.topics.topics` via `_topics_module`; setups and traces verbatim
      from the design):
      - `test_board_default_view_passes_topic_to_aggregate_only` — collect and
        aggregate patched to capture kwargs and return `[]`; renderers patched;
        input `runner.invoke(topics, ["board", "--topic", "feat-a", "--host",
        "main"])`; trace: default view collects `(scope.year, remote)` with no
        display filters, aggregates with `hosts=("main",), topics=("feat-a",)`;
        assert collect kwargs exclude `hosts`/`topics` and aggregate kwargs are
        exactly those
      - `test_board_per_host_view_filters_collection_by_topic` — as above; input
        `runner.invoke(topics, ["board", "--per-host", "--topic", "feat-a"])`;
        trace: `collect(scope.year, remote, hosts=(), topics=("feat-a",))`; assert
        the collect kwargs
      - `test_clear_resolves_base_flag_over_configuration_and_delegates` —
        `resolve_clear_targets` patched to capture `(base, year)` and return
        `[DeleteTarget("feature-foo", "feature-foo", "feature-foo", True)]`;
        `delete_topics` patched to return `"Deleted 1 topic(s) of 2026:
        feature-foo"`; `_topics_section` patched to prove it is NOT called when the
        flag is given; input `runner.invoke(topics, ["--year", "2026", "clear",
        "--base-ref", "origin/release/2.0.0", "-y"])`; trace: flag wins, config
        never read → resolve → 1 target → yes → no confirmation → delete → echo →
        exit 0; assert `result.exit_code == 0`, `"Deleted 1 topic(s)" in
        result.stdout`, captured `("origin/release/2.0.0", "2026")`,
        `_topics_section` not called
      - `test_clear_base_from_configuration_section` — `_topics_section` patched to
        return `TopicsConfig(base_ref="release/2.0.0", publish_commit=None)`;
        domain patched to return `[]` this time; input `runner.invoke(topics,
        ["clear", "-y"])`; trace: `base_ref` None → section → base
        `"release/2.0.0"` → resolve → `[]` → echo `"No merged topics to clear."` →
        exit 0; assert the line in stdout and the captured base
      - `test_clear_without_any_base_is_clean_error` — `_topics_section` patched to
        return `None` (missing config); input `runner.invoke(topics, ["clear",
        "-y"])`; trace: base None → ClickException naming the flag and the
        configuration line; assert `result.exit_code == 1`,
        `"--base-ref" in result.output`, `"topics.base_ref" in result.output`,
        `resolve_clear_targets` never called
      - `test_clear_confirmation_needs_a_terminal` — CliRunner (non-tty stdin by
        default); `resolve_clear_targets` returns one target; `yes=False`; input
        `runner.invoke(topics, ["clear", "--base-ref", "origin/main"])`; trace:
        targets resolved → not yes → `sys.stdin.isatty()` False → ClickException;
        assert `result.exit_code == 1`, the message names `--yes/-y`,
        `delete_topics` never called
      - `test_clear_declined_confirmation_exits_zero` — drive the tty-simulating
        stdin with the established `_TtyStdin` pattern of
        `test_delete_declined_confirmation_exits_zero` (optionally mocking
        `click.confirm` to return False); `resolve_clear_targets` returns one
        target; `delete_topics` recorder; input `runner.invoke(topics, ["clear",
        "--base-ref", "origin/main"], input=…)`; trace: pairs printed
        (`"feature-foo -> feature-foo"`) → confirm `"Clear 1 topic(s)?"` → n →
        exit 0; assert `result.exit_code == 0`, the pair line in output,
        `delete_topics` not called
- [ ] **Debugging**: run `pytest tests/commands/topics/test_topics.py -x -v` — fix
      implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the group registers five subcommands; `--topic`
      on `board`; `clear`'s option surface and callback shape; the facade `__all__`
      still carries exactly its four names; help texts follow the CLI docstring rule
- [ ] **Lint**: `ruff check goga/commands/` — fix formatting, apply decomposition if
      necessary

### Task 4: Integration tests — the pointer model over the real git cell (integration tests)

Re-pins the four integration scenarios of `tests/integration/test_topic_workflows.py`
whose expectations flip under the pointer model, exercising the domain and the CLI over
real git refs (no mocks of the git cell). These are behavior-delta re-pins verified by
the design review — the new expectations below are exact.

**Usages relevant to this task:**
- `convention`: the integration-test structure — real git via `_git`/`_git_out`,
  `tmp_path` + `monkeypatch.chdir`, CliRunner for the CLI round trips.
- `refs-and-switching` / `topic-paths`: the real inventory and tree-reading behavior
  the scenarios observe.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] Re-pin `test_board_standing_on_the_merged_host_keeps_the_topic` — after
      `branch -d feat-b` the branchless topic appears in NO view: the default view
      keeps only the `feat-a` entry, and the `--per-host` audit loses the
      `(* feat-b, main, …)` row; reword the docstring — the board no longer "keeps
      merged work in view", a branchless topic is history
- [ ] Re-pin the `legacy-work` scenario
      (`test_board_old_title_txt_only_topic_is_empty_status`) — the audit row
      `("legacy-work", "legacy", "", "[empty]")` drops under the primary filter (the
      topic has no branch of its own — "legacy" does not normalize into
      "legacy-work"); assert its absence, keep the byte-exact ref-tree assertion
- [ ] Re-pin `test_delete_merged_work_is_an_error_over_real_refs` — the new
      branchless message: keep the `"feature-x"` assertion, drop the `"main"`
      assertion (the message names no hosting branch); keep the no-refs-mutated
      assertion
- [ ] Re-pin `test_delete_unpublished_topic_by_exact_name_over_real_git` — the
      doctrine flip: the bare branch is the topic's own branch by name — expect
      `DeleteTarget("feature-foo", "feature-foo", None, has_dir=True)` and assert
      the branch ref is GONE after `delete_topics` (the disk directory still goes
      with it); reword the docstring from "the bare branch stays" to the
      pointer-model reading
- [ ] Run validation: `pytest tests/integration/test_topic_workflows.py -x -v` — all
      pass
- [ ] Run the full gate: `pytest tests/ -x` — the whole suite passes (this is the
      plan's completion gate; run it in an environment where pytest is available)

---

## Validation Commands

- `pytest tests/ -x`: Run all tests (the full completion gate; per-task slices are
  listed inside each task)
- `ruff check goga/`: Lint check
- `python -c "from goga.topics import resolve_clear_targets; from goga.commands.topics import topics; assert 'resolve_clear_targets' in __import__('goga.topics').__all__"`:
  Facade accessibility smoke check (the contract tests pin it fully)
- `goga lint`: Cells and CODEMANIFEST integrity (80 cells, 0 errors before and after)
- `goga schema`: Import-graph integrity (the single new edge
  `goga/commands/topics → goga/topics` for `resolve_clear_targets`; no cycles)

**Environment note (carried over from the design and its review)**: `pytest` and
`ruff` cannot run in the current container — `.venv/bin/python` symlinks into
`/opt/homebrew` (macOS-built binaries). Run the pytest/ruff gates in a capable
environment (e.g. `uv run pytest tests/ -x`, `uv run ruff check goga/`) before
declaring the work done. `goga lint` and `goga schema` DO run here and must stay
clean.

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
      (`resolve_clear_targets`, `resolve_delete_targets`, `DeleteTarget` in
      `goga/topics/deletion.py`; `collect_topic_board`, `aggregate_topic_board` in
      `goga/topics/board.py`; `board`, `clear` in `goga/commands/topics/topics.py`)
- [ ] Every contract entity is accessible from the facade
      (`resolve_clear_targets` importable from `goga.topics` and listed in `__all__`;
      `clear` registered on the `topics` group; the CLI facade keeps its four names)
- [ ] Properties and methods match the declared API (the `topics` parameters, the
      `clear(base_ref, yes)` shape, the `board` `topic` parameter)
- [ ] Descriptions are reflected in behavior (pointer-model primary filter over the
      full inventory; name-based own branch; branchless clean error naming no host;
      survivor-gated `has_dir`; silent branchless exclusion from the clear scope;
      empty scope → `[]`/one line + exit 0; the exact error-message texts)
- [ ] Contract dependencies are met (the CLI imports `resolve_clear_targets` from
      the domain facade; `delete_topics` consumes the targets of either resolver
      unchanged)
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code →
      verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each
      coding task
- [ ] Integration tests exist and are re-pinned for the cross-entity pointer-model
      scenarios over the real git cell
- [ ] No package boundary was expanded (no new cells, no new interfaces beyond the
      contract, internal helpers only within the existing cells)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check goga/` in a
      capable environment; `goga lint`, `goga schema` here)
- [ ] Every Usages entry is mentioned in at least one task (convention, click,
      topic-paths, topic-statuses, refs-and-switching, deleting ×2, topic-board,
      project-configuration, checkpoints)
