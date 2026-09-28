# Plan: `topic-update-and-propagate`

Result of compiling `.goga/history/2026/topic-update-and-propagate/design.md`
(verified by the design-review stage, fixes R1–R8 applied) into ralphex
execution tasks. The CODEMANIFEST contracts are **final** — implementation
follows them, never edits them.

---

## Purpose

Implement the topic↔base exchange — `goga topics update` and
`goga topics propagate` — plus its supporting surfaces: the nested topics
configuration (`base_ref` + `create`/`update`/`propagate` sections, the
silent retirement of `publish_commit`), 13 new git plumbing routines
(checkout-free exchange, git ≥ 2.38), two new soft hook actions with their
contexts and emissions, the board divergence marker (Base column +
`divergence` JSON key), and the shared commit-template engine.

After implementation: `update` brings a topic up to its base under
`merge`/`rebase`/`ff-else-merge`/`ff-else-rebase` (checkout-free for other
topics, in-place for the current one, optional publish with a lease-protected
rebase push); `propagate` delivers a topic into its base under
`merge`/`ff`/`squash` (checkout-free build-plant-push, one retry cycle,
uniform rollback, inherent push, exactly one confirmation); the board shows
each topic's divergence against the configured base.

Strategy: bottom-up through the dependency order
(catalog → config/project → config facade → config/hooks → topics/git →
topics/hooks → topics domain → commands), one cell completed before the next,
TDD inside every coding task. All 78 design test scenarios are distributed
across the tasks; traces and algorithms below are transferred verbatim from
the design document.

## Context

### Contract Surface

**Cell: `goga/hooks/catalog`**

**Entity: `declared_actions() -> actions: list[Action]`**
- Type: function (module constant `_DECLARED_ACTIONS` + sorted accessor)
- Declared `location`: `catalog.py` (existing)
- Facade obligation: importable from `goga/hooks/catalog`
- Change: add `Action(domain="topics", name="topic_updated", error_class="soft")`
  and `Action(domain="topics", name="topic_propagated", error_class="soft")`;
  keep the hand-ordered per-domain grouping of the literal; `declared_actions()`
  sorts on return — ordering is not a contract. The topics domain now counts
  nine actions. An emission before its record exists raises
  `ValueError(unknown hook action)` — this cell is implemented first.

**Cell: `goga/config/project`**

**Entity: `TopicsCreateConfig(commit: str | None = None)`**
- Type: class; Declared `location`: `config.py`
- `@dataclass(kw_only=True, frozen=True)`; field `commit: str | None = None`

**Entity: `TopicsUpdateConfig(strategy: str | None = None, commit: str | None = None)`**
- Type: class; Declared `location`: `config.py`; same frozen kw_only shape

**Entity: `TopicsPropagateConfig(strategy: str | None = None, commit: str | None = None)`**
- Type: class; Declared `location`: `config.py`; same frozen kw_only shape

**Entity: `TopicsConfig(base_ref: str | None, create: TopicsCreateConfig | None, update: TopicsUpdateConfig | None, propagate: TopicsPropagateConfig | None)`**
- Type: class; Declared `location`: `config.py` (rebuilt)
- All four fields `= None` defaults (overlay-friendly, `ReviewConfig` style);
  the `publish_commit` field and property are **deleted** — stale authored
  values pass through the loader silently (no warning, no effect)
- Value objects: no behavior, no validation (structure belongs to the loader,
  semantics to the consumer)

**Entity: `ProjectConfig`** — the `topics` property annotation updates for the
nested shape (field type `TopicsConfig | None` unchanged).

**Entity: `load_project_config() -> config: ProjectConfig`**
- Type: function; Declared `location`: `loader.py` (existing)
- Change: step 8 no longer extracts topics; the new step 9 performs the
  nested structural extraction; construct moves to step 10. Step 9 contract:
  `raw = data.get("topics")` → None → `topics = None`; non-mapping →
  `ValueError("'topics' must be a mapping in .goga/config.yml")`;
  `base_ref` via `_parse_topics_field` (absent/YAML-null → None; non-string →
  ValueError naming the key; empty/whitespace → None); per section in
  `("create", "update", "propagate")`: absent/YAML-null → section None,
  non-mapping → `ValueError("'topics.<name>' must be a mapping in
  .goga/config.yml")`, inside each `commit` (create) or `strategy`/`commit`
  (update, propagate) via `_parse_topics_field` with dotted keys
  (`topics.update.strategy`, `topics.update.commit`, `topics.create.commit`,
  `topics.propagate.strategy`, `topics.propagate.commit`); unknown keys —
  including the retired `publish_commit` — never read: silence by
  construction (the `data.get`-only style), not by a skip-list.

**Cell: `goga/config` (facade)**

Re-exports (see below): +3 embedding re-exports of the nested topics models;
`__all__` grows 14 → 17.

**Cell: `goga/config/hooks`**

**Entity: `merge_config_amendments(base: ProjectConfig, contributions: list[ToolAmendment]) -> overlay: ConfigOverlay`**
- Type: function; Declared `location`: `overlay.py` (existing)
- Change: the path-resolution type tree `_CONFIG_TREE["TopicsConfig"]`
  becomes `{"base_ref": _scalar(str), "create": _section("TopicsCreateConfig"),
  "update": _section("TopicsUpdateConfig"), "propagate":
  _section("TopicsPropagateConfig")}` plus the three per-model nodes
  (`commit` / `strategy` scalars); `_SECTION_DEFAULTS` grows
  `"TopicsCreateConfig": TopicsCreateConfig`, `"TopicsUpdateConfig":
  TopicsUpdateConfig`, `"TopicsPropagateConfig": TopicsPropagateConfig`, and
  the `TopicsConfig` lambda collapses to plain `TopicsConfig` (all-defaults
  shape). Amendment paths like `topics.update.strategy` resolve through the
  tree; missing sections materialize via the factories.

**Cell: `goga/topics/git`** — 13 new routines. Six single-invocation wrappers
plus the `replay_commits` scripted chain, all fixed by the traces (see
Facts). Signature list:

- `require_git_version()` — `exchange.py` (new)
- `is_ancestor(ancestor: str, descendant: str) -> contains: bool` — `exchange.py`
- `resolve_commit_tree(revision: str) -> tree: str` — `exchange.py`
- `merge_tree(ours: str, theirs: str, merge_base: str | None = None) -> tree: str | None` — `exchange.py`
- `create_commit_from_tree(tree: str, parents: list[str], message: str) -> commit: str` — `exchange.py`
- `replay_commits(onto: str, until: str) -> tip: str | None` — `exchange.py`
- `point_branch_at_commit(branch_name: str, commit: str)` — `exchange.py`
- `merge_into_current(revision: str, message: str)` — `switch.py` (existing file)
- `rebase_current_onto(revision: str)` — `switch.py`
- `fast_forward_current_branch(revision: str)` — `switch.py`
- `fetch_branch(branch_name: str)` — `publish.py` (existing file)
- `push_branch_with_lease(branch_name: str, expected_tip: str)` — `publish.py`
- `push_revision_to_branch(revision: str, branch_name: str)` — `publish.py`

Facade obligation: all thirteen importable from `goga/topics/git`
(`__all__` 15 → 28). `exchange.py` carries its own `_run_git` mirroring
`publish.py`'s (DEVNULL stdin, `input=` support, errors=replace); the
`switch.py`/`publish.py` additions reuse their modules' existing `_run_git`.

**Cell: `goga/topics/hooks`**

**Entity: `TopicUpdated(identity: TopicIdentity, base: str, effective_tip: str, strategy: str, outcome: str, published: bool)`**
- Type: class; Declared `location`: `contexts.py`; frozen kw_only dataclass
  mirroring `TopicSwitched`'s shape; read-only facts of a completed update;
  the idempotent `already-current` outcome emits like any other

**Entity: `TopicPropagated(identity: TopicIdentity, base: str, strategy: str, outcome: str)`**
- Type: class; Declared `location`: `contexts.py`; no pushed flag — the push
  is inherent to every propagate

**Entity: `TopicHooks.emit_updated(identity, base, effective_tip, strategy, outcome, published)` / `TopicHooks.emit_propagated(identity, base, strategy, outcome)`**
- Methods of the existing `TopicHooks`; Declared `location`: `events.py`;
  the exact idiom of `emit_switched`: build the context → `emit_hook_event(
  _run_registry(), "topics", "topic_updated"/"topic_propagated",
  context_for=lambda _tool: context)`; fire-and-forget; a failing hook warns
  and the delivery continues (soft class via the catalog). Module/class
  docstring emission counts five→seven; contexts docstring "five read-only
  fact bags" → seven. Facade `__init__.py` exports the two contexts.

**Cell: `goga/topics`**

**Entity: `ExchangeBase(name: str, tip: str, local_branch: str | None, reconciled: bool)`** — `exchange.py` (new); frozen kw_only dataclass.
**Entity: `resolve_exchange_base(base_ref: str, own_branch: str, own_tip: str) -> base: ExchangeBase`** — `exchange.py`; algorithm below.
**Entity: `ExchangeTarget(topic: str, branch: str, current: bool)`** — `exchange.py`; frozen kw_only dataclass.
**Entity: `resolve_exchange_target(identifier: str | None, year: str | None = None) -> target: ExchangeTarget`** — `exchange.py`; algorithm below.
**Entity: `render_commit_template(template: str, slug: str, base: str) -> message: str`** — `exchange.py`; pure text
(`template.replace("{slug}", slug).replace("{base}", base)`;
unknown placeholders stay verbatim; no repository reads) — the single
template engine of the domain's authored messages.
**Entity: `update_topic(identifier: str | None, base_ref: str, strategy: str | None, commit_message: str | None, publish: bool = False, year: str | None = None) -> result: str`** — `updating.py` (new); algorithm below.
**Entity: `PropagationPlan(target: ExchangeTarget, base_ref: str, strategy: str, message: str, year: str)`** — `propagating.py` (new); frozen kw_only dataclass.
**Entity: `resolve_propagation(identifier: str | None, base_ref: str, strategy: str | None, commit_message: str | None, year: str | None = None) -> plan: PropagationPlan`** — `propagating.py`; algorithm below.
**Entity: `execute_propagation(plan: PropagationPlan) -> result: str`** — `propagating.py`; algorithm below.
**Entity: `resolve_divergence(own_tip: str, base_ref: str | None) -> marker: str | None`** — `board.py` (existing); algorithm below.

Changed in place:
- `BoardRecord` / `BoardEntry` — +`divergence: str | None = None` field and property (the topic's own-branch divergence marker: `behind` / `current`, None when unconfigured or unresolvable).
- `collect_topic_board(year=None, remote=False, hosts=None, topics=None, base_ref: str | None = None)` — step 10 computes the marker per own-branched topic in the same pass; `base_ref` None → every marker None; additive, back-compatible.
- `aggregate_topic_board` — step 5 projects the winner's divergence marker into the entry (the winner is always an own-branch record; pure projection, no git).
- `create_topic` / `publish_topic` — every authored message composes through `render_commit_template(template, slug, base_name)`; built-in default `Create topic '{slug}'`; the existing `("...").replace("{slug}", ...)` sites route through the shared call; `{base}` becomes available everywhere.

Facade obligation: the ten new names importable from `goga/topics`
(`__all__` 17 → 27). The facade/module docstring's mutation sentence updates
(the sanctioned network set grew).

**Cell: `goga/commands/topics`**

**Entity: `topics` group** — two new methods on the existing click group
(`topics.py`):
- `update(identifier: str | None = None, base_ref: str | None = None, publish: bool = False) -> exit_code: int` — optional IDENTIFIER positional, `--base-ref`, `--publish/-p`; no confirmation; exit 0 on success (an already-current topic included), 1 on error.
- `propagate(identifier: str | None = None, base_ref: str | None = None, yes: bool = False) -> exit_code: int` — optional IDENTIFIER, `--base-ref`, `--yes/-y` (short form collides with the group `--year/-y` — positions distinguish them, the same documented collision as `delete`/`clear`); exit 0 on success (a nothing-to-do delivery and a declined confirmation included), 1 on error.
- `board` — new first step loads the configuration the way `clear` does and passes `base_ref` into both `collect_topic_board` calls; the json/info conflict check now precedes (renumbered steps).
- `create` — the template rung becomes `section.create.commit`; the `--commit` help text names `topics.create.commit`; the retired `section.publish_commit` reads are removed.
- Group/module docstrings grow the two subcommands; `--info` help text names the todo and base columns.

**Entity: `render_topic_board` / `render_topic_host_rows` / `render_board_json`** (`render.py`):
- default view under `info`: topic, branch, hosts, todo, base each capped at one sixth of `width` minus the dividers, statuses the non-negative remainder, minimum 8 per column; header `Topic | Branch | Hosts | Todo | Base | Statuses`.
- audit view under `info`: topic, branch, todo, base each capped at one fifth, statuses the remainder, minimum 8; header `Topic | Branch | Todo | Base | Statuses`.
- without `info` the rules are unchanged (four-/three-column); the Base cell carries the marker or empty when None; truncation/ellipsis, the current asterisk, row dividers, and the narrow-terminal exception behave exactly as the existing columns; the base header is the word `Base`.
- `render_board_json`: every entry → keys `topic, branch, hosts, statuses, current, remote, todo, divergence`; every record → the same without `hosts`; `divergence` is the string or null — always present, never omitted.

### Interaction Diagram

```
CLI layer                         topics domain                    git plumbing
─────────────────────────────     ─────────────────────────────    ─────────────────────────────
goga/commands/topics/topics.py    goga/topics/exchange.py          goga/topics/git/exchange.py
  topics update  ──────────────►    update_topic (updating.py)  ───►  require_git_version
    │ flags → base/strategy/        │  resolve_exchange_target      is_ancestor
    │ template from TopicsConfig    │  resolve_exchange_base  ─────►  merge_tree / replay_commits
    │ (goga/config facade)          │  render_commit_template       create_commit_from_tree
    │ no confirmation               │  pre-flight + real mutation    point_branch_at_commit
    ▼                               │  publish push              ──►  merge_into_current /
  echo result line                  │  TopicHooks.emit_updated        rebase_current_onto /
                                    ▼                                 fast_forward_current_branch
goga/commands/topics/topics.py    goga/topics/propagating.py    ──► goga/topics/git/publish.py
  topics propagate ─────────────►    resolve_propagation            fetch_branch
    │ flags → base/strategy/         │  read-only plan              push_branch_with_lease
    │ template; one confirmation     │  (origin probe, current-      push_revision_to_branch
    ▼                                │   branch guard, message)      (existing: push_branch,
  execute_propagation ──────────►    │  build → plant → push         origin_configured, ...)
  echo result line                   │  retry cycle, uniform         │
                                    │  rollback                     ▼
goga/commands/topics/topics.py    goga/topics/board.py          git (subprocess)
  topics board ────────────────►    collect_topic_board            every invocation:
    │ config load → base_ref         │  resolve_divergence          check=True, captured output,
    ▼                                │    (is_ancestor only)        GIT_TERMINAL_PROMPT=0
  render_topic_board /              aggregate_topic_board
  render_topic_host_rows /          goga/topics/creation.py + publishing.py
  render_board_json                   render_commit_template({slug},{base})
                                    goga/topics/hooks: TopicHooks.emit_updated /
                                      emit_propagated → TopicUpdated / TopicPropagated →
                                      hooks platform (catalog: topics/topic_updated,
                                      topics/topic_propagated — soft)
```

### Data Flows

**Flow 1 — `goga topics update` (current topic, strategy `merge`, `--publish`)**: CLI resolves `base_ref` (flag → `topics.base_ref` of the effective `ConfigOverlay`), `strategy` (`topics.update.strategy`, verbatim, possibly None), `template` (`topics.update.commit`, verbatim) → calls `update_topic(identifier, base_ref, strategy, template, publish, year)` → validates the strategy against the whitelist → `resolve_exchange_target` (current branch → slug + branch) → `resolve_ref_commit(branch)` = own tip → captures the base's local-branch tip as the rollback tip → `resolve_exchange_base(base_ref, branch, own_tip)`: version gate, one reported fetch, projections, containment, optional reconciliation commit → `is_ancestor(base.tip, own_tip)` decides already-current → ff decision → current topic: clean-tree probe, read-only pre-flight (`merge_tree` / `replay_commits` discarded), then the real mutation (`merge_into_current` / `rebase_current_onto` / `fast_forward_current_branch`) with the rendered message → `origin_configured` probe → `push_branch` (merge/ff) or `push_branch_with_lease(branch, pre-rebase own tip)` (rebase with twin) → `TopicHooks.emit_updated(identity, base.name, base.tip, effective strategy, outcome, published)` → one result line to stdout.

**Flow 2 — `goga topics propagate` (merge, local base)**: CLI resolves the inputs like update (strategy/template from `topics.propagate.*`) → `resolve_propagation`: strategy whitelist, `resolve_exchange_target`, `origin_configured` guard, current-branch guard, message render → the CLI asks exactly one confirmation (naming the topic, the target base, and the inherent push; `--yes` skips; non-interactive without `--yes` is a clean error; a decline exits 0) → `execute_propagation(plan)`: own tip, rollback capture, `resolve_exchange_base`, reachability nothing-to-do check, delivery build (`merge_tree(base.tip, own_tip)` → `create_commit_from_tree(tree, [base.tip, own_tip], plan.message)`), content-based nothing-to-do check, plant (`point_branch_at_commit(base.local_branch, delivery)`), push (`push_branch(base.local_branch)`), one retry cycle on a concurrent-movement rejection, uniform rollback on every failure → `TopicHooks.emit_propagated(identity, base.name, strategy, outcome)` → one result line.

**Flow 3 — `goga topics board` with a configured base**: CLI loads the configuration the way `clear` does (`load_project_config` + the `amend_config` checkpoint via `ConfigHooks`; a missing file counts as unset), prints the amendment summary lines to stderr, extracts `topics.base_ref` → `collect_topic_board(..., base_ref=base)` computes the divergence marker of every own-branched topic in the same pass (`resolve_divergence(own_tip, base_ref)` — local refs only, never a failure) → `aggregate_topic_board` projects the winner's marker → the renderers print the Base column (`--info`) or the `divergence` JSON key.

**Flow 4 — configuration load (nested topics)**: `.goga/config.yml` → `load_project_config` step 9: absent/YAML-null `topics` → None; a non-mapping → ValueError; `base_ref` and the three sub-mappings structurally validated (absent/YAML-null → None section; present non-mapping → ValueError; inside each, `strategy`/`commit` optional strings, empty/whitespace → None); unknown keys — including the retired `publish_commit` — silently ignored → `TopicsConfig` assembled into `ProjectConfig` → the `goga/config` facade re-exports the three new models → the `goga/config/hooks` amendment tree accepts nested paths (`topics.update.strategy`, `topics.create.commit`, …).

### Re-exports

- `->TopicsCreateConfig: {}`, `->TopicsUpdateConfig: {}`, `->TopicsPropagateConfig: {}` in `goga/config/CODEMANIFEST`
  - Source: `Imports.Types` from `goga/config/project`
  - Facade obligation: importable from `goga.config`; `__all__` count 17
  - Task 4

### Usages Context

- `convention` (`.goga/usages/conventions.md`, every changed cell): docstring style (Purpose/Algorithm/Requirements/Constraints/Raises), the REPL cycle, the test infrastructure (mocking at the import point), relative imports, pytest/ruff commands.
- `click` (`.goga/usages/cooks/click.md`, `goga/topics` + `goga/commands/topics`): group/command/option/argument decorators, echo, `click.confirm`, `click.prompt` with `IntRange`, the clean error channel (`click.ClickException`), exit-code propagation.
- `git` (inline, `goga/topics/git`): the invocation pattern — `subprocess.run`, `check=True`, captured output, `GIT_TERMINAL_PROMPT=0`, UTF-8 with replacement — now extended with the checkout-free exchange patterns (`merge-tree --write-tree`, `commit-tree` over parents, the plumbing replay, the single-ref plant, `merge-base --is-ancestor`, the commit→tree peel, the lease push, the targeted fetch, the real merge/rebase/ff, the version gate).
- `beautiful_json` (project-level cook, `goga/commands/topics`): pretty-printed, sorted-keys JSON serialization — `render_board_json` with the `divergence` key.

### Imported Usages

- `exchanging` from `goga/topics/git` — source `goga/topics/git/.usages/exchanging.md` (exists, current): the consumer patterns of the checkout-free exchange — gate, containment, tree identity, pre-flight + build + plant, replay, in-place moves, the network set. Plant last; the lease binds to the pre-replay tip; report each fetch with one stdout line before it runs.
- `refs-and-switching`, `publishing` from `goga/topics/git` (exist): the inventory and revision-resolution patterns (`_base_branch_names` builds on the inventory reading), the quarantined commit + plant + push + rollback patterns. `deleting` is unchanged by this topic and consumed by no affected entity — context only, intentionally referenced by no task.
- `checkpoints` from `goga/topics/hooks` — `goga/topics/hooks/.usages/checkpoints.md` (exists, updated): the emission contract — fire-and-forget under the soft class, facts from the operation's own data; seven emissions with `topic_updated` / `topic_propagated` contexts; no pushed flag on the propagate context.
- `update` / `propagate` from `goga/topics` — `goga/topics/.usages/{update,propagate}.md` (exist, current): the consumer contracts of the two operations — inputs, defaults, strategies, idempotency, atomicity, the inherent push; the CLI maps flags to the documented inputs and adds exactly one confirmation on propagate.
- `project-configuration` from `goga/config` — `goga/config/.usages/project-configuration.md` (exists, updated): the nested topics schema, the silent retirement of `publish_commit`, the migration note; read `topics.base_ref`, `topics.create.commit`, `topics.update.{strategy,commit}`, `topics.propagate.{strategy,commit}` with the per-sub-section None-guard.

### Local Usages

Verified current by the design pass (created/updated by the apply stage;
re-checked against the CODEMANIFEST — **no further changes required**, no
creation tasks). Tasks reference them as context:

- `goga/topics/git/.usages/exchanging.md` — the gate, containment, tree identity, pre-flight/build/plant, replay, in-place moves, the network set (matches the 13 new signatures).
- `goga/topics/.usages/update.md`, `propagate.md` — the two operation contracts (the uniform rollback including the ff error matches the fixed CODEMANIFEST).
- `goga/topics/.usages/topic-board.md` — `base_ref` and the divergence marker.
- `goga/topics/.usages/creating.md` / `publishing.md` — the template engine and the new default.
- `goga/topics/.usages/registering-hooks.md` — nine soft actions, seven notifications, the two new context rows, the no-pushed-flag note.
- `goga/topics/hooks/.usages/checkpoints.md` — seven emissions, the two new examples and context bullets.
- `goga/commands/topics/.usages/topics-command.md` — the two new sections, the Base column, the `divergence` JSON key, the create template key.
- `goga/config/.usages/project-configuration.md` — the nested schema, the field table, the migration note, the accessor block.

Rule applied by the design: no CODEMANIFEST `Usages` reference points at any own `.usages/` file — they stay consumer documentation only.

### External Dependencies

- git ≥ 2.38 (external binary, subprocess): `merge-tree --write-tree`, `commit-tree`, `update-ref`, `merge-base --is-ancestor` rc-trichotomy, `rev-parse --verify <rev>^{tree}`, `--force-with-lease=<full-ref>:<tip>`, `--force-with-lease` rejection wording, `fetch` with a forced single-branch refspec, `couldn't find remote ref` stderr matching.
- `click` (existing dependency): decorators, echo, confirm/prompt, `ClickException`.
- `pyyaml` (existing, loader), `pytest` + `pytest-cov`, `ruff` (test/lint infra).
- No new third-party packages.

## Facts

- Traces verified against the actual implementation files (the module `_run_git` helpers, the `switching.py` selection machinery, the `events.py` emission idiom, the `overlay.py` tree, the `loader.py` parse style) and the git plumbing API (git ≥ 2.38). Full traces: design.md "Code Stack Trace" (per-routine, line-referenced above in tasks).
- The fixed user-visible strings, single-sourced as module constants: `Updated topic {year}/{slug} from '{base}' via {strategy} ({outcome})`, `Propagated topic {year}/{slug} into '{base}' via {strategy} ({outcome})`, `Fetching origin/{branch}...`, `Reconcile base '{name}'`, and the three built-in templates `Create topic '{slug}'`, `Update topic '{slug}' from '{base}'`, `Propagate topic '{slug}' into '{base}'`.
- `is_ancestor` must run without `check=True` (rc 0 = containment, 1 = no containment, >1 = failure → raw `CalledProcessError`); every other new git invocation keeps `check=True`.
- `commit-tree` runs with DEVNULL stdin — `commit-tree -m` reads the operand from stdin otherwise and hangs (the documented `publish.py` pitfall).
- Parent orders are contract-fixed: update merge `[own_tip, base.tip]`; propagate merge `[base.tip, own_tip]`; squash `[base.tip]` exactly one parent; reconciliation `[local_tip, twin_tip]`.
- Outcome vocabularies: update `merged` / `rebased` / `fast-forwarded` / `already-current`; propagate `merged` / `fast-forwarded` / `squashed` / `nothing-to-do` (both idempotent forms emit like any other).
- Strategy whitelists live in the domain and fire before anything else, naming the configuration key: update `{"merge", "rebase", "ff-else-merge", "ff-else-rebase"}` (key `topics.update.strategy`, None → `merge`); propagate `{"merge", "ff", "squash"}` (key `topics.propagate.strategy`, None → `merge`). No validation at the CLI or the loader; template grammar is never validated.
- The error-handling boundary: `subprocess.CalledProcessError` (stderr detail or `str(exc)`), `FileNotFoundError`, `OSError`, the hooks-registry `ImportError`, and the new gate `RuntimeError` all fold into `click.ClickException` at the public entry points (`update_topic`, `resolve_propagation`, `execute_propagation` wrap their `_`-prefixed cores exactly like `board.py`/`publishing.py`); the git cell stays raw-propagating; rollback restores suppress their own failures.
- The sanctioned network set is exact: the targeted reported fetches, the inherent propagate push, the update publish push (plain or lease), the existing publication and deletion pushes; nothing else fetches; the board never touches the network.
- The checkout-free atomicity invariant: every built object dangles until a single `point_branch_at_commit` ref update; the in-place path of the current topic is the only working-copy touch (merge/rebase/ff), always behind a read-only pre-flight.
- The lease binds to the pre-rebase own tip (`own_tip`), never the replayed tip; no retry on the update side (the retry cycle belongs to propagate alone); a failed publish push leaves the confirmed update standing.
- `replay_commits` preserves author and message verbatim via `%an%x1f%ae%x1f%aI%x1f%B` reads and `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`/`GIT_AUTHOR_DATE` on the single `commit-tree` invocation; committer = repository identity; an empty range returns `onto` itself.
- Test constants: `BASE = "main"`, `TWIN = "origin/main"`, `LOCAL_TIP = "aa1"`, `TWIN_TIP = "bb2"`, `OWN = "cc3"`, `RECON = "dd4"`, `TREE = "tree-oid-1"`, slug `feat-x`, year `2026`.
- Facade counts after implementation: `goga.config` `__all__` = 17; `goga.topics.git` `__all__` = 28; `goga.topics` gains the ten exchange names.

## Gap Analysis

Verified against the working tree (current implementation state):

- **Missing contract entities**: `goga/topics/git/exchange.py` does not exist (all 7 routines); `switch.py` lacks `merge_into_current`/`rebase_current_onto`/`fast_forward_current_branch`; `publish.py` lacks `fetch_branch`/`push_branch_with_lease`/`push_revision_to_branch`; `goga/topics/exchange.py`, `updating.py`, `propagating.py` do not exist (all 10 domain types); `resolve_divergence` absent from `board.py`; `TopicUpdated`/`TopicPropagated`/`emit_updated`/`emit_propagated` absent; the three nested config models absent; the two catalog records absent.
- **Missing facade exposure**: `goga.config.__all__` = 14 (needs 17); `goga.topics.git.__all__` = 15 (needs 28); `goga.topics.__all__` = 17 (needs +10); hooks facade lacks the two contexts.
- **Behavioral mismatches (existing code to change)**: `config.py` still defines the flat `TopicsConfig(base_ref, publish_commit)` (field at config.py:188); `loader.py:_parse_topics` still reads `publish_commit` (loader.py:338); `overlay.py` tree still maps `"publish_commit": _scalar(str)` (overlay.py:222) and the factory passes `publish_commit=None` (overlay.py:351); `topics.py` still reads `section.publish_commit` (topics.py:339) and its `--commit` help names the retired key (topics.py:256); `BoardRecord`/`BoardEntry` lack `divergence`; `collect_topic_board` lacks `base_ref`; `creation.py`/`publishing.py` render messages via inline `.replace("{slug}", ...)`; the board CLI does not load the configuration; renderers lack the Base column and the JSON key.
- **Existing code reused**: `switching.py` (`resolve_switch_candidates`, `_choose_candidate` — one selection surface, imported from `.switching`); `publish.py`/`switch.py` `_run_git` idioms; the board pipeline (filters, sort, winner selection); `events.py` `emit_hook_event(_run_registry(), ...)` idiom; `loader.py` `_parse_topics_field`; the `_TtyStdin` fixture idiom of `tests/commands/topics/test_topics.py` (an `io.BytesIO` whose `isatty()` reads True; click wraps it in a `TextIOWrapper` that delegates the check); the `clear`-style `_topics_section()` lazy load.
- **Test coverage gaps**: new files `tests/topics/git/test_exchange.py`, `tests/topics/test_exchange.py`, `test_updating.py`, `test_propagating.py`; extensions to `tests/config/test_loader.py`, `tests/config/test_project_cell_contract.py` (the `{base_ref, publish_commit}` field-set assertion must become the nested set), `tests/config/hooks/test_overlay.py` (`_MODELS`/tree cross-check), `tests/hooks/catalog/test_catalog.py`, `tests/topics/hooks/test_contexts.py`/`test_events.py`, `tests/topics/test_board.py`, `tests/creation`-related suites, `tests/commands/topics/test_topics.py` (surface enumerations grow to seven subcommands; every mock of a topics-domain name moves to the `goga.topics` import point), `tests/commands/topics/test_render.py`.
- **Residual references to sweep**: `publish_commit` outside the loader's silence and the plan/design documents (CLI reads, help text, tests) — removed in this implementation.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow). Dependency order: `goga/hooks/catalog` → `goga/config/project` → `goga/config` → `goga/config/hooks` → `goga/topics/git` → `goga/topics/hooks` → `goga/topics` → `goga/commands/topics`.

**Package: `goga/hooks/catalog`**

### Task 1: Catalog — the two soft exchange actions (TDD coding)

Adds the two new soft-action records to `declared_actions` so the events cell's
`_error_class` can resolve the new addresses (`topics/topic_updated`,
`topics/topic_propagated`). Without the record an emission raises
`ValueError(unknown hook action)` at runtime — this cell is implemented first
in the dependency order.

**Usages relevant to this task:**
- `convention`: docstring style, test infrastructure, relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): in `tests/hooks/catalog/test_catalog.py` add `test_catalog_declares_both_new_actions` — **Input**: `declared_actions()`. **Assertions**: contains `Action("topics", "topic_updated", "soft")` and `Action("topics", "topic_propagated", "soft")`; the topics domain now counts nine actions. **Sufficiency**: an emission whose address is missing from the catalog raises `ValueError(unknown hook action)` at runtime — the record is the compile-time half of the contract.
- [x] **Code**: in `goga/hooks/catalog/catalog.py` add `Action(domain="topics", name="topic_propagated", error_class="soft")` and `Action(domain="topics", name="topic_updated", error_class="soft")` to `_DECLARED_ACTIONS`, keeping the literal's hand-ordered per-domain grouping (`declared_actions()` sorts on return — ordering is not a contract)
- [x] **Interface verification**: `python -m pytest tests/hooks/catalog/test_catalog.py -v` — all pass
- [x] **Logic tests**: extend the existing topics-action count assertions of the catalog suite to nine; confirm no existing action changed
- [x] **Debugging**: `python -m pytest tests/hooks/catalog/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: `declared_actions()` shape unchanged apart from the two records; facade import unaffected
- [x] **Lint**: `ruff check goga/hooks/catalog/ tests/hooks/catalog/` — fix formatting if necessary

**Package: `goga/config/project`**

### Task 2: Nested topics configuration models (TDD coding)

Rebuilds `TopicsConfig` into the nested form in `config.py`: three new frozen
kw_only dataclasses with `None` defaults (the defaults keep the overlay
materialization factories trivial and match the `ReviewConfig` style), the
`publish_commit` field deleted, `ProjectConfig.topics` annotated for the
nested shape. Value objects only — no behavior, no validation (structure
belongs to the loader, Task 3; semantics to the consumer).

**Usages relevant to this task:**
- `convention`: data-model rules (frozen kw_only dataclasses), docstring style, intra-package imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in `tests/config/test_project_cell_contract.py` update `TestTopicsConfigContract` — fields of `TopicsConfig` are exactly `{base_ref, create, update, propagate}` (the old `{base_ref, publish_commit}` assertion at test_project_cell_contract.py:119 goes); add shape checks for the three new models: `TopicsCreateConfig(commit)`, `TopicsUpdateConfig(strategy, commit)`, `TopicsPropagateConfig(strategy, commit)` — each frozen, kw_only, every field typed `str | None` **with `= None` default**; `TopicsConfig` has no `publish_commit` attribute; `ProjectConfig.topics` field type stays `TopicsConfig | None`
- [ ] **Code**: in `goga/config/project/config.py` add `TopicsCreateConfig(commit: str | None = None)`, `TopicsUpdateConfig(strategy: str | None = None, commit: str | None = None)`, `TopicsPropagateConfig(strategy: str | None = None, commit: str | None = None)` — all `@dataclass(kw_only=True, frozen=True)` — and rebuild `TopicsConfig(base_ref: str | None = None, create: TopicsCreateConfig | None = None, update: TopicsUpdateConfig | None = None, propagate: TopicsPropagateConfig | None = None)` in the same style; delete the `publish_commit` field and its property/docstring
- [ ] **Code**: update the `ProjectConfig.topics` property annotation/docstring for the nested shape (field type unchanged)
- [ ] **Interface verification**: `python -m pytest tests/config/test_project_cell_contract.py -v` — the model contract tests pass (loader tests may still fail — they are Task 3)
- [ ] **Logic tests**: every model constructible with no args (all-None defaults) and with kwargs; immutability (`FrozenInstanceError` on assignment)
- [ ] **Debugging**: `python -m pytest tests/config/test_project_cell_contract.py tests/config/test_config.py -x` — fix implementation code until the model-level tests pass
- [ ] **Contract re-verification**: signatures match the contract exactly (field names/order/types/defaults)
- [ ] **Lint**: `ruff check goga/config/project/` — fix formatting if necessary

### Task 3: Loader — the nested topics step 9 (TDD coding)

Rewrites `_parse_topics` in `loader.py`: `base_ref` plus the three
sub-mappings structurally validated; the retired `publish_commit` never read
(silence by construction — the `data.get`-only extraction style, no
skip-list, no warning). Trace (design "Trace: `load_project_config`"):
step 9 `raw = data.get("topics")` → None → None; non-mapping → ValueError;
`base_ref` via `_parse_topics_field`; per section: absent/YAML-null → None,
non-mapping → ValueError naming `topics.<name>`, leaves via
`_parse_topics_field` with dotted keys; step 10 assembles `ProjectConfig`.

**Usages relevant to this task:**
- `convention`: docstring style (Purpose/Args/Raises), loader test style (inline YAML in `tmp_path/.goga/config.yml`), relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): the loader surface — `_parse_topics` exists, returns `TopicsConfig | None`, raises `ValueError` on structural violations
- [ ] **Code**: in `goga/config/project/loader.py` add the helper `_parse_topics_section(raw, name, fields)` — absent/YAML-null → None; a non-mapping → `ValueError("'topics.<name>' must be a mapping in .goga/config.yml")`; inside, each named field through `_parse_topics_field` with the dotted key; rewrite `_parse_topics` to parse `base_ref` and the three sections via the helper and assemble `TopicsConfig(base_ref=..., create=..., update=..., propagate=...)`; unknown keys (including `publish_commit`) are never read; keep `_parse_topics_field` as-is (already the right normalization)
- [ ] **Interface verification**: `python -m pytest tests/config/test_loader.py -v` — all pass
- [ ] **Logic tests** (all six design scenarios, in `tests/config/test_loader.py`):
  - `test_loader_parses_nested_topics_section` — **Setup**: `tmp_path` `.goga/config.yml` with `language: python` and the full nested topics block (base_ref `origin/main`, create/update/propagate with `commit`/`strategy` values). **Assertions**: `config.topics.base_ref == "origin/main"`; `config.topics.create.commit == "Create topic '{slug}'"`; `config.topics.update.strategy == "rebase"`; `config.topics.propagate.strategy == "squash"`; every model frozen and kw_only (dataclass import checks). **Sufficiency**: the nested shape is the configuration contract of both new commands; a flat mis-parse would silently strand every knob at None.
  - `test_loader_retires_publish_commit_silently` — **Setup**: yaml `topics: {base_ref: main, publish_commit: "old"}` plus valid nested sections. **Assertions**: no warning (capsys empty); `config.topics` has no `publish_commit` attribute (`pytest.raises(AttributeError)`). **Sufficiency**: the retirement is contractual (no warning, no effect).
  - `test_loader_rejects_non_mapping_topics_section` — **Setup**: yaml `topics: 5`. **Assertions**: `pytest.raises(ValueError)` with message `'topics' must be a mapping in .goga/config.yml`.
  - `test_loader_rejects_non_mapping_update_section` — **Setup**: yaml `topics: {update: 5}`. **Assertions**: `ValueError` naming `topics.update`.
  - `test_loader_rejects_non_string_strategy` — **Setup**: yaml `topics: {update: {strategy: 3}}`. **Assertions**: `ValueError` naming `topics.update.strategy` (the shared `_parse_topics_field` contract holds on every nested leaf).
  - `test_loader_empty_and_whitespace_strings_resolve_none` — **Setup**: yaml `topics: {base_ref: "", update: {strategy: "  "}}`. **Assertions**: `base_ref is None`; `update.strategy is None`; the update section itself is a `TopicsUpdateConfig` (present section, unset leaves).
- [ ] **Debugging**: `python -m pytest tests/config/ -x` — fix implementation code until all tests pass (do NOT fix test code); update any existing loader tests that asserted the flat `publish_commit` behavior to the nested contract
- [ ] **Contract re-verification**: step numbering 9/10 of the loader algorithm matches the contract; Values verbatim (no default merge)
- [ ] **Lint**: `ruff check goga/config/project/ tests/config/` — fix formatting if necessary

**Package: `goga/config` (facade)**

### Task 4: Config facade — three new model re-exports (infrastructure)

The facade contract: +3 embedding re-exports beside `TopicsConfig`; the
single import entry point — consumers must not reach into
`goga.config.project`.

**Usages relevant to this task:**
- `convention`: facade/`__all__` rules, relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] In `goga/config/__init__.py` import `TopicsCreateConfig`, `TopicsUpdateConfig`, `TopicsPropagateConfig` from `.project` and add them to `__all__` (alphabetical placement beside `TopicsConfig`; count 14 → 17)
- [ ] Verify facade accessibility: `python -m pytest tests/config/test_config.py tests/config/test_project_cell_contract.py -v` — including `test_facade_reexports_nested_topics_models`: **Input**: `from goga.config import TopicsCreateConfig, TopicsUpdateConfig, TopicsPropagateConfig`. **Assertions**: the three names import; each is in `goga.config.__all__` beside `TopicsConfig`; the cell facade count is 17. **Sufficiency**: the facade is the single import entry point.
- [ ] Lint: `ruff check goga/config/` — fix formatting if necessary

**Package: `goga/config/hooks`**

### Task 5: Overlay — the nested topics amendment tree (TDD coding)

Extends the path-resolution type tree of `merge_config_amendments` with the
three nested topics models so `topics.update.strategy`-style amendment paths
resolve; missing sections materialize via the factories.

**Usages relevant to this task:**
- `convention`: overlay test style (the `tests/config/hooks/` fixtures), relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): `_CONFIG_TREE["TopicsConfig"]` equals the nested node set; `set(_CONFIG_TREE) == set(_MODELS)` cross-check extended with the three new models
- [ ] **Code**: in `goga/config/hooks/overlay.py` replace the `"publish_commit": _scalar(str)` node (overlay.py:222) with `{"base_ref": _scalar(str), "create": _section("TopicsCreateConfig"), "update": _section("TopicsUpdateConfig"), "propagate": _section("TopicsPropagateConfig")}`; add the three per-model nodes (`commit` / `strategy` scalars); grow `_SECTION_DEFAULTS` with the three models; collapse the `TopicsConfig` lambda (overlay.py:351) to plain `TopicsConfig`
- [ ] **Interface verification**: `python -m pytest tests/config/hooks/ -v` — the tree/`_MODELS` cross-checks pass
- [ ] **Logic tests**: `test_overlay_accepts_nested_topics_amendment_paths` — **Setup**: an authored config without a topics section; a tool amendment contributing `topics.update.strategy = "rebase"`. **Input**: `merge_config_amendments(base, [contribution])`. **Trace**: the path resolves through `ProjectConfig.topics` → `_section("TopicsConfig")` → `update` → `_section("TopicsUpdateConfig")` → `strategy` scalar; missing sections materialize via the factories. **Assertions**: the overlay's effective config carries `topics.update.strategy == "rebase"`; the summary line names the path. **Sufficiency**: the tree and factories are the amendment gate — a missing tree node rejects every nested topics amendment (the exact gap this topic closes)
- [ ] **Debugging**: `python -m pytest tests/config/hooks/ -x` — fix implementation code until all tests pass; update any existing overlay fixtures asserting the flat `publish_commit` node
- [ ] **Contract re-verification**: the `dataclasses.fields` cross-check tests extend to the three new models so tree drift stays detectable; the pinned `ValueError` summary format unchanged
- [ ] **Lint**: `ruff check goga/config/hooks/ tests/config/hooks/` — fix formatting if necessary

**Package: `goga/topics/git`**

### Task 6: Git exchange plumbing — `exchange.py` (TDD coding)

Creates `exchange.py` with its own `_run_git` mirroring `publish.py`'s
(DEVNULL stdin, `input=` support, `errors=replace`) and the seven
checkout-free routines. Six routines are single-invocation wrappers;
`replay_commits` is a scripted multi-invocation chain — all fixed by the
design traces. The cell stays silent — no echo.

**Usages relevant to this task:**
- `git` (inline practice): the invocation pattern — `subprocess.run`, `check=True` (except `is_ancestor`), captured output, `GIT_TERMINAL_PROMPT=0`, UTF-8 with replacement; the merge-tree/commit-tree/replay/single-ref-plant/peel patterns.
- `convention`: docstrings (Purpose/Algorithm/Requirements/Constraints/Raises), tests mock `subprocess.run` at the import point (`mock.patch("goga.topics.git.exchange.subprocess.run", ...)`), relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in the new `tests/topics/git/test_exchange.py` — module exists; every routine importable from `goga.topics.git.exchange` with the declared signatures; each single-shot routine runs exactly one git invocation (per the Requirements); `replay_commits` is a per-commit chain (rev-list → show → merge-tree → commit-tree) with no one-invocation requirement
- [ ] **Code**: create `goga/topics/git/exchange.py` with the module `_run_git` and:
  - `require_git_version()` — `git version` → parse `version (\d+)\.(\d+)` from the first line → `(major, minor) < (2, 38)` → `RuntimeError("goga needs git >= 2.38 for the topic exchange (found <present>)")`; a parse failure is an infrastructure anomaly treated as the gate failure (a clean error naming the unparsed output) — never a silent pass; read-only
  - `is_ancestor(ancestor, descendant) -> bool` — `git merge-base --is-ancestor <a> <d>` **without** `check=True`; rc 0 → True, 1 → False, otherwise raw `subprocess.CalledProcessError`
  - `resolve_commit_tree(revision) -> str` — `git rev-parse --verify <revision>^{tree}` → `stdout.strip()`; unresolvable → raw `CalledProcessError`; read-only, no network
  - `merge_tree(ours, theirs, merge_base=None) -> str | None` — `git merge-tree --write-tree [--merge-base=<base>] <ours> <theirs>`; rc 0 → first stdout line stripped (the tree oid); rc 1 → None (the conflict signal, not an error); rc > 1 → raw `CalledProcessError`; one invocation per merge; nothing else touched
  - `create_commit_from_tree(tree, parents, message) -> str` — `git commit-tree <tree> [-p <p1>] [-p <p2> ...] -m <message>` with DEVNULL stdin (load-bearing — `commit-tree -m` reads stdin otherwise and hangs); author/committer from the repository identity; no ref created; returns `stdout.strip()`
  - `replay_commits(onto, until) -> str | None` — `git rev-list --reverse <until> ^<onto>` (oldest first; with `--parents` for the per-commit parent); an empty list → return `onto` itself; per commit C with parent P (a merge commit uses its first parent): `tree = merge_tree(ours=<running>, theirs=C, merge_base=P)`; read C's author and message verbatim via `git show -s --format=%an%x1f%ae%x1f%aI%x1f%B C`; build via `git commit-tree <tree> -p <running> -m <message>` with `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`/`GIT_AUTHOR_DATE` exported for the single invocation; `tree is None` at any step → return None; no skipping/reordering/squashing
  - `point_branch_at_commit(branch_name, commit)` — `git update-ref refs/heads/<branch_name> <commit>` (the full-ref form — a dash-leading short name cannot parse as an option); exactly one ref update; the working copy, the index, and HEAD untouched; docstring documents the existence precondition (creation stays `create_branch_at_commit`; the caller owns the checked-out policy)
- [ ] **Interface verification**: `python -m pytest tests/topics/git/test_exchange.py -v` — contract tests pass
- [ ] **Logic tests** (the eleven design scenarios, in `tests/topics/git/test_exchange.py` — mock `subprocess.run` at the module import point with a side-effect function answering per argv):
  - `test_require_git_version_passes_modern_git` — stdout `git version 2.43.0 (Apple Git-151)\n` → returns None; exactly one invocation; argv `["git", "version"]`
  - `test_require_git_version_rejects_old_git` — stdout `git version 2.35.1\n` → `pytest.raises(RuntimeError)` whose message contains both `2.38` and `2.35.1`
  - `test_is_ancestor_maps_exit_codes` — a run fake answering returncode 0/1/128: True / False / `CalledProcessError`; `check=False` in the call kwargs (never `check=True`)
  - `test_resolve_commit_tree_peels_to_tree` — stdout `"tree-oid-1\n"` → argv `["git", "rev-parse", "--verify", "cc3^{tree}"]` (the `^{tree}` peel verbatim); exactly one invocation; returns `"tree-oid-1"`
  - `test_merge_tree_clean_and_conflict` — rc 0 stdout `"tree-oid-1\n\n"` → `"tree-oid-1"` (first line only); rc 1 → None; `("cc3", "aa1", "bb2")` → argv contains `--merge-base=bb2`; exactly one invocation per call
  - `test_create_commit_from_tree_argv_order` — stdout `"ee5\n"` → argv `["git", "commit-tree", "tree-oid-1", "-p", "cc3", "-p", "aa1", "-m", "Update topic 'feat-x'"]`; `stdin=subprocess.DEVNULL` in the run kwargs; returns `"ee5"`
  - `test_replay_commits_preserves_author_and_message` — scripted: `rev-list --reverse cc3 ^aa1` → `"c1 c0\n"`, `show -s --format=... c1` → `"Ann<a1f>ann@x.io<a1f>2026-01-02T03:04:05+00:00<a1f>Do the thing\n"`, `merge-tree` (base `c0`) → tree, `commit-tree` → `"f1\n"`. **Assertions**: return `"f1"`; the `commit-tree` invocation's env carries the three `GIT_AUTHOR_*` values verbatim; the message argument is `"Do the thing"`; `rev-list` argv ends with `["cc3", "^aa1"]` and includes `--reverse`
  - `test_replay_commits_two_commit_chain_chains_running_result` — rev-list → `"c1 c0\nc2 c1\n"`; the second `merge-tree` invocation received `ours=f1` and `--merge-base=c1` (the running result and each step's own parent, never `aa1`/`c0` again); returns `"f2"`
  - `test_replay_commits_conflict_returns_none` — the scripted `merge-tree` answers rc 1 → returns None; no `commit-tree` in the recorded argv
  - `test_replay_commits_empty_range_returns_onto` — rev-list → empty → `replay_commits("aa1", "aa1")` returns `"aa1"`; no commit-tree calls (a fully-carried line must not read as a conflict)
  - `test_point_branch_at_commit_single_ref_update` — argv `["git", "update-ref", "refs/heads/main", "ee5"]`; exactly one invocation
- [ ] **Debugging**: `python -m pytest tests/topics/git/test_exchange.py -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: every routine read-only where the contract says so; conflict-as-None vs infrastructure-error split holds; dangling guarantees hold
- [ ] **Lint**: `ruff check goga/topics/git/exchange.py tests/topics/git/test_exchange.py` — fix formatting, apply decomposition if necessary

### Task 7: Git in-place moves — `switch.py` additions (TDD coding)

The three bounded host-side mutations of the current branch (the sanctioned
in-place path of the current topic). Reuses `switch.py`'s existing `_run_git`.

**Usages relevant to this task:**
- `git` (inline practice): the invocation pattern (`check=True` for all three).
- `convention`: docstring style, tests mock at the module import point.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in `tests/topics/git/test_switch.py` — the three names importable from `goga.topics.git.switch` with the declared signatures
- [ ] **Code**: in `goga/topics/git/switch.py` add:
  - `merge_into_current(revision, message)` — `git merge --no-ff --no-edit -m <message> <revision>` (`--no-ff` guarantees a merge commit even when a fast-forward is possible; `--no-edit` suppresses any editor prompt); failure (conflict included) → raw `CalledProcessError`; no push; no cleanliness probe (the caller does, before the call)
  - `rebase_current_onto(revision)` — `git rebase <revision>` (plain — no `--onto` forms, no autostash); no pre-rebase tip capture here (the caller captured it for the lease push); no push
  - `fast_forward_current_branch(revision)` — `git merge --ff-only <revision>`; a non-fast-forwardable situation is a git error surfaced raw — no fallback merge; no commit authored
- [ ] **Interface verification**: `python -m pytest tests/topics/git/test_switch.py -v` — contract tests pass
- [ ] **Logic tests** (in `tests/topics/git/test_switch.py`):
  - `test_merge_into_current_never_fast_forwards` — argv contains both `--no-ff` and `--no-edit` before the revision: `["git", "merge", "--no-ff", "--no-edit", "-m", "Update topic 'feat-x'", "aa1"]`
  - `test_rebase_current_onto_uses_rebase` — argv exactly `["git", "rebase", "aa1"]`; no other flags; exactly one invocation
  - `test_fast_forward_current_branch_uses_ff_only` — argv exactly `["git", "merge", "--ff-only", "aa1"]`; no other flags
- [ ] **Debugging**: `python -m pytest tests/topics/git/test_switch.py -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: the three wrappers touch the working copy only (no ref plumbing, no push); constraints hold
- [ ] **Lint**: `ruff check goga/topics/git/switch.py tests/topics/git/test_switch.py` — fix formatting if necessary

### Task 8: Git network additions — `publish.py` (TDD coding)

The three exchange network routines: the targeted fetch, the lease push, the
write-through push. Reuses `publish.py`'s existing `_run_git` (full-ref
refspecs, `--no-follow-tags`). The cell stays silent — the reporting line of
a fetch belongs to the calling module.

**Usages relevant to this task:**
- `git` (inline practice): the lease pattern (full-ref `--force-with-lease`), the forced single-branch fetch refspec, `--no-follow-tags`.
- `convention`: docstring style, tests mock at the module import point.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in `tests/topics/git/test_publish.py` — the three names importable from `goga.topics.git.publish` with the declared signatures
- [ ] **Code**: in `goga/topics/git/publish.py` add:
  - `fetch_branch(branch_name)` — `git fetch origin +refs/heads/<b>:refs/remotes/origin/<b>` (the explicit forced refspec updates exactly one remote-tracking ref; the working copy, the index, and HEAD untouched); rc ≠ 0 → inspect stderr: it contains `couldn't find remote ref` → return normally (the twin stays absent; the one git wording pair across the supported floor 2.38 — documented); any other stderr → raw `CalledProcessError`; silent — no printing
  - `push_branch_with_lease(branch_name, expected_tip)` — `git push --no-follow-tags --force-with-lease=refs/heads/<b>:<expected_tip> origin refs/heads/<b>:refs/heads/<b>` (the full-ref lease form is unambiguous; the full refspec can never start with a dash); a remote standing anywhere else refuses → raw error; no fetch refreshes the lease, no retry — both belong to the caller
  - `push_revision_to_branch(revision, branch_name)` — `git push --no-follow-tags origin <revision>:refs/heads/<b>` (a plain push — no force, no lease, no `-u`); a non-fast-forward remote rejects → raw error; no local branch created; exactly the named branch
- [ ] **Interface verification**: `python -m pytest tests/topics/git/test_publish.py -v` — contract tests pass
- [ ] **Logic tests** (in `tests/topics/git/test_publish.py`):
  - `test_fetch_branch_updates_single_tracking_ref` — argv `["git", "fetch", "origin", "+refs/heads/main:refs/remotes/origin/main"]`; nothing printed
  - `test_fetch_branch_absent_remote_is_silence` — the fake raises `CalledProcessError(1, cmd)` with stderr `"fatal: couldn't find remote ref refs/heads/main\n"` → returns None; no exception
  - `test_fetch_branch_other_failure_raises` — stderr `"fatal: unable to access 'origin': network\n"` → `pytest.raises(subprocess.CalledProcessError)` (a network outage must not read as twin-absent)
  - `test_push_branch_with_lease_binds_expected_tip` — argv `["git", "push", "--no-follow-tags", "--force-with-lease=refs/heads/feat-x:cc3", "origin", "refs/heads/feat-x:refs/heads/feat-x"]`
  - `test_push_revision_to_branch_writes_through` — argv `["git", "push", "--no-follow-tags", "origin", "ee5:refs/heads/main"]`; no `-u`, no force flags
- [ ] **Debugging**: `python -m pytest tests/topics/git/test_publish.py -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: the twin-absent matcher is the one documented wording; the network set grew by exactly these three; no retry/rollback inside the cell
- [ ] **Lint**: `ruff check goga/topics/git/publish.py tests/topics/git/test_publish.py` — fix formatting if necessary

### Task 9: Git facade — export the exchange surface (infrastructure)

The domain imports the exchange surface from the package root — a missing
export breaks the facade contract the CODEMANIFEST declares.

**Usages relevant to this task:**
- `convention`: facade/`__all__` rules, relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] In `goga/topics/git/__init__.py` import from `.exchange` (7 names), `.switch` (3 new), `.publish` (3 new) and extend `__all__` (15 → 28, alphabetical)
- [ ] Update the facade/module docstring's inventory sentence to cover the exchange zone (checkout-free merges/replay/plant, containment, tree resolution, the version gate, the targeted fetch/lease/revision pushes, the in-place merge/rebase/ff)
- [ ] Verify facade accessibility: `python -m pytest tests/topics/git/ -v` — including `test_topics_git_facade_exports_exchange_surface` (in the git test home): **Input**: `from goga.topics.git import require_git_version, is_ancestor, resolve_commit_tree, merge_tree, create_commit_from_tree, replay_commits, point_branch_at_commit, merge_into_current, rebase_current_onto, fast_forward_current_branch, fetch_branch, push_branch_with_lease, push_revision_to_branch`. **Assertions**: all thirteen import and appear in `__all__` (28 exported names total). **Sufficiency**: the domain imports the exchange surface from the package root.
- [ ] Lint: `ruff check goga/topics/git/` — fix formatting if necessary

**Package: `goga/topics/hooks`**

### Task 10: Hook contexts and emissions — `topic_updated` / `topic_propagated` (TDD coding)

Two read-only fact bags + two fire-and-forget emissions in the exact idiom
of the existing five; the addresses resolve through the catalog records of
Task 1 (implementation order matters — an emission before the record exists
would raise).

**Usages relevant to this task:**
- `checkpoints` (imported practice): the emission contract — fire-and-forget under the soft class, facts from the operation's own data; seven emissions; no pushed flag on the propagate context.
- `convention`: data-model rules, the events test fixtures of `tests/topics/hooks/`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in `tests/topics/hooks/test_contexts.py` — `TopicUpdated`/`TopicPropagated` are frozen kw_only dataclasses with the exact field sets (`identity, base, effective_tip, strategy, outcome, published` / `identity, base, strategy, outcome`); in `tests/topics/hooks/test_events.py` — `TopicHooks.emit_updated`/`emit_propagated` exist with the declared signatures
- [ ] **Code**: in `goga/topics/hooks/contexts.py` add the two frozen kw_only dataclasses in the file's documented style; the module docstring's "five read-only fact bags" becomes seven
- [ ] **Code**: in `goga/topics/hooks/events.py` add `emit_updated` / `emit_propagated` in the exact idiom of `emit_switched` (context build → `emit_hook_event(_run_registry(), "topics", "topic_updated"/"topic_propagated", context_for=lambda _tool: context)` — the shared run registry, one `HookRegistry.build_once()` per run, the per-tool context view over the same instance); the class and module docstrings' emission counts update five→seven
- [ ] **Code**: export the two contexts from `goga/topics/hooks/__init__.py`
- [ ] **Interface verification**: `python -m pytest tests/topics/hooks/ -v` — contract tests pass
- [ ] **Logic tests**: `test_emit_updated_and_emit_propagated_addresses` — **Setup**: the existing `tests/topics/hooks` registry fixtures. **Input**: `TopicHooks().emit_updated(identity, base="main", effective_tip="cc3", strategy="merge", outcome="merged", published=True)`; `emit_propagated(identity, base="main", strategy="ff", outcome="fast-forwarded")`. **Trace**: context built → `emit_hook_event(registry, "topics", "topic_updated"/"topic_propagated", ...)` under the soft class. **Assertions**: the receiving tool saw a `TopicUpdated` / `TopicPropagated` instance with the exact fields; a raising hook is warned-and-skipped (the fixture's failing-hook case) and the call returns None; contexts frozen
- [ ] **Debugging**: `python -m pytest tests/topics/hooks/ -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: fire-and-forget (nothing collected, nothing returned); the address/error-class pairing resolves `soft` through the catalog
- [ ] **Lint**: `ruff check goga/topics/hooks/ tests/topics/hooks/` — fix formatting if necessary

**Package: `goga/topics`**

### Task 11: Domain exchange core — `exchange.py` (TDD coding)

The shared machinery of update and propagate: the base resolution (one
targeted reported fetch, containment, the reconciliation merge), the
addressee resolution (reusing the switch tiers), and the template engine.

**Usages relevant to this task:**
- `exchanging` (imported from `goga/topics/git`): the fetch, containment, and reconciliation patterns — plant last; report each fetch with one stdout line before it runs.
- `refs-and-switching` (imported): the inventory and revision-resolution patterns.
- `click` (project cook): the numbered candidate selection and the non-interactive detection (`_choose_candidate` of `switching.py`, imported from `.switching` — one selection surface in the package).
- `topic-paths` (imported via the history facade): the slug and current-branch patterns.
- `convention`: docstring style, tests mock the imported git-cell names at the domain module's import point plus the hooks facade.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in the new `tests/topics/test_exchange.py` — `ExchangeBase`, `ExchangeTarget` frozen kw_only dataclasses with the declared fields; `resolve_exchange_base`, `resolve_exchange_target`, `render_commit_template` importable with the declared signatures; `render_commit_template` is pure text
- [ ] **Code**: create `goga/topics/exchange.py`:
  - `ExchangeBase(name, tip, local_branch, reconciled)` and `ExchangeTarget(topic, branch, current)` — frozen kw_only dataclasses
  - `render_commit_template(template, slug, base)` — `template.replace("{slug}", slug).replace("{base}", base)`; unknown placeholders stay verbatim; no repository reads
  - the module helper `_base_branch_names(base_ref, refs)` — if `base_ref` starts with `origin/` → `(local := short(base_ref), twin := base_ref)`; else `(local := base_ref, twin := f"origin/{base_ref}")`; shared by `update_topic`, `resolve_propagation`, and `execute_propagation` for their rollback-capture and current-branch guards — one detection rule everywhere
  - `resolve_exchange_base` per the verbatim algorithm:
    ```
    1. require_git_version()
    2. IF base_ref == own_branch OR base_ref == f"origin/{own_branch}":
       - raise clean error "the topic is its own base"
    3. (local, twin) = _base_branch_names(base_ref, list_branch_refs())
       IF local not in inventory AND twin not in inventory:
       - tip = resolve_ref_commit(base_ref)        # tag/hash, no fetch
       - RETURN ExchangeBase(base_ref, tip, None, False)
       IF local == resolve_current_branch_name():
       - raise clean error "switch away first"     # the checked-out base
    4. echo f"Fetching origin/{local}..."
       fetch_branch(local)                          # absent remote -> twin stays absent
    5. projections = [resolve_ref_commit(x) for x in (local, twin) if x exists]
    6. IF len(projections) == 1: effective = projections[0]
       ELIF is_ancestor(local_tip, twin_tip): effective = twin_tip
       ELIF is_ancestor(twin_tip, local_tip): effective = local_tip
       ELSE:                                        # the pair diverged
         IF is_ancestor(local_tip, own_tip) AND is_ancestor(twin_tip, own_tip):
         - effective = own_tip; written = False     # already carried, nothing written
         ELSE:
         - tree = merge_tree(local_tip, twin_tip)
         - IF tree is None: raise clean error "reconcile base '{base_ref}' manually"
         - commit = create_commit_from_tree(tree, [local_tip, twin_tip],
                                             f"Reconcile base '{base_ref}'")
         - point_branch_at_commit(local, commit)
         - effective = commit; written = True
    7. RETURN ExchangeBase(base_ref, effective, local if local exists else None, written)
    ```
    Errors as `click.ClickException`: git-too-old (`RuntimeError` → clean); self-base; the base's local branch being the current branch (switch away first — before the fetch); unresolvable revision; fetch failure (other than twin-absent); reconciliation conflict.
  - `resolve_exchange_target` per the verbatim algorithm:
    ```
    1. IF identifier is None:
       - current = resolve_current_branch_name(); None -> clean error
       - candidates = resolve_switch_candidates(current, year)
         keep branch == current; empty or topic is None -> clean error naming branch
    2. ELSE:
       - candidates = resolve_switch_candidates(identifier, year)
       - none -> clean error with the board hint
       - several -> _choose_candidate(candidates)   # the switching.py numbered
                                                    # prompt; clean error w/o a TTY
       - chosen.topic is None -> clean error (a branch without a topic)
    3. chosen.remote -> clean error hinting `goga topics switch`
    4. RETURN ExchangeTarget(chosen.topic, chosen.branch,
                             chosen.branch == resolve_current_branch_name())
    ```
    Read-only; the remote-only refusal fires here for both exchange operations.
- [ ] **Interface verification**: `python -m pytest tests/topics/test_exchange.py -v` — contract tests pass
- [ ] **Logic tests** (the eleven design scenarios, in `tests/topics/test_exchange.py`; mocked at `goga.topics.exchange` — `list_branch_refs`, `resolve_ref_commit`, `is_ancestor`, `merge_tree`, `create_commit_from_tree`, `point_branch_at_commit`, `fetch_branch`, `require_git_version`, `resolve_current_branch_name`, `resolve_switch_candidates`; echo captured):
  - `test_render_commit_template_placeholders` — `("Do {what} for {slug} from {base}", "feat-x", "main")` → `"Do {what} for feat-x from main"` (unknown placeholders verbatim — a `str.format` implementation would raise on `{what}`)
  - `test_resolve_exchange_base_reconciliation_flow` — `list_branch_refs` → `[BranchRef("main", False), BranchRef("origin/main", True)]`; `resolve_ref_commit` → `{"main": LOCAL_TIP, "origin/main": TWIN_TIP}`; `is_ancestor` → False everywhere; `merge_tree` → `TREE`; `create_commit_from_tree` → `RECON`; **Input**: `resolve_exchange_base("main", "feat-x", OWN)`. **Assertions**: the returned `ExchangeBase("main", RECON, "main", True)`; the reconciliation message exactly `Reconcile base 'main'`; the echo line `Fetching origin/main...` printed before `fetch_branch` was called (order via a `mock.Mock` attached helper or call order list); exactly one `fetch_branch` call
  - `test_resolve_exchange_base_already_carried_writes_nothing` — `is_ancestor(LOCAL_TIP, OWN)` and `is_ancestor(TWIN_TIP, OWN)` → True. **Assertions**: `base.tip == OWN`, `base.reconciled is False`; `merge_tree` not called; `point_branch_at_commit` not called
  - `test_resolve_exchange_base_tag_base_never_fetches` — `list_branch_refs` → `[]`; `resolve_ref_commit("v2.0")` → `"tagcommit"` → `ExchangeBase("v2.0", "tagcommit", None, False)`; `fetch_branch` not called; no echo
  - `test_resolve_exchange_base_rejects_self_base` — `("feat-x", "feat-x", OWN)` and `("origin/feat-x", "feat-x", OWN)` → `click.ClickException` naming the topic as its own base; `list_branch_refs` never consulted (the guard precedes)
  - `test_resolve_exchange_base_rejects_checked_out_base` — inventory `[main, origin/main]`; `resolve_current_branch_name` → `"main"`. **Assertions**: `click.ClickException` mentioning switching away; `fetch_branch` not called; `merge_tree` and `point_branch_at_commit` not called; a detached HEAD (`None`) passes to the fetch. **Sufficiency**: `update-ref` bypasses git's own current-branch protection — without the guard a checkout-free update while sitting on the base leaves HEAD pointing past the files on disk
  - `test_resolve_exchange_base_reconcile_conflict_is_clean_error` — diverged pair; `merge_tree(LOCAL_TIP, TWIN_TIP)` → None. **Assertions**: `click.ClickException` mentioning the manual reconciliation; `create_commit_from_tree` not called; `point_branch_at_commit` not called (never a raw plumbing failure or a half-written state)
  - `test_resolve_exchange_base_remote_only_base_single_projection` — inventory `[BranchRef("origin/main", True)]` only → `("origin/main", TWIN_TIP, None, False)`; the fetch echo printed for the short name `main`
  - `test_resolve_exchange_base_descendant_of_pair` — `is_ancestor(LOCAL_TIP, TWIN_TIP)` → True → effective TWIN_TIP, `reconciled=False`, no `merge_tree`
  - `test_resolve_exchange_target_refuses_remote_only` — `resolve_switch_candidates` → `[SwitchCandidate("origin/feat-x", "feat-x", [], False, True)]` → `click.ClickException` mentioning `goga topics switch`
  - `test_resolve_exchange_target_no_candidate_hints_board` — candidates → `[]` → the error message contains the board hint
- [ ] **Debugging**: `python -m pytest tests/topics/test_exchange.py -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: exactly one fetch per resolution reported before it runs; the already-carried check precedes the write; the reconciliation lands only on the local base branch and is never pushed; read-only target resolution
- [ ] **Lint**: `ruff check goga/topics/exchange.py tests/topics/test_exchange.py` — fix formatting, apply decomposition if necessary

### Task 12: Board divergence — `board.py` (TDD coding)

The binary marker computed from local refs without network, the additive
record/entry field, the collection pass, and the aggregate projection.

**Usages relevant to this task:**
- `exchanging` (imported): the containment pattern.
- `refs-and-switching` (imported): the inventory and revision-resolution patterns.
- `convention`: board test style (the existing board fixture), docstring style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in `tests/topics/test_board.py` — `BoardRecord`/`BoardEntry` grow the `divergence: str | None = None` field (existing constructions keep working — additive); `resolve_divergence(own_tip, base_ref)` importable; `collect_topic_board` accepts `base_ref`
- [ ] **Code**: in `goga/topics/board.py`:
  - add `divergence: str | None = None` to `BoardRecord` and `BoardEntry` (+ properties)
  - implement `resolve_divergence` per the verbatim algorithm:
    ```
    1. base_ref None -> None
    2. projections: branch-shaped -> {local tip, twin tip} as they exist locally
                      (each skipped on a resolution failure);
                      tag/hash -> {resolve_ref_commit(base_ref)}
       projections empty -> None
    3. RETURN "current" IF every projection satisfies is_ancestor(p, own_tip)
          ELSE "behind"
    ```
    Read-only — no fetch, no mutation, never a failure (an unresolvable side is skipped via `try/except subprocess.CalledProcessError`; every side unresolvable → None)
  - `collect_topic_board`: add the `base_ref: str | None = None` parameter; the collection proceeds exactly as today through step 9; step 10 — for every own-branched topic (the primary-filter survivors): resolve the own-branch tip (the local branch's `resolve_ref_commit(name)` when the inventory carries it, else the twin's) and compute `resolve_divergence(own_tip, base_ref)` when `base_ref` is not None, else None → the marker is **topic-scoped**: every record of the topic carries the same `divergence` value; `base_ref` None → every marker None; the rest of the pipeline (filters, sort) untouched
  - `aggregate_topic_board`: step 5 additionally copies the winner's `divergence` into the entry (the winner is always an own-branch record); no git access
- [ ] **Interface verification**: `python -m pytest tests/topics/test_board.py -v` — contract tests pass
- [ ] **Logic tests** (in `tests/topics/test_board.py`):
  - `test_resolve_divergence_marker_matrix` — mocked `resolve_ref_commit` and `is_ancestor`; four cases: base None → None; unresolvable base (every side raises `CalledProcessError` internally, swallowed) → None; both projections contained → `"current"`; one projection not contained → `"behind"`; no exception in any case
  - `test_collect_topic_board_sets_topic_scoped_divergence` — the existing board fixture (two branches hosting `feat-x`, one merged host) extended: base_ref `"main"`; `resolve_divergence` mocked per tip. **Input**: `collect_topic_board(year="2026", base_ref="main")`. **Assertions**: every record of `feat-x` carries the same marker; `aggregate_topic_board` projects the winner's marker into the entry; calling without `base_ref` yields all-None markers
- [ ] **Debugging**: `python -m pytest tests/topics/test_board.py -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: the pass never fetches and never fails on an unconfigured or unresolvable base; the additive back-compatible change holds (existing callers omitting `base_ref` see None markers)
- [ ] **Lint**: `ruff check goga/topics/board.py tests/topics/test_board.py` — fix formatting if necessary

### Task 13: Template engine switch — `creation.py` / `publishing.py` (TDD coding)

Routes every authored message through `render_commit_template` (Task 11); the
built-in default becomes `Create topic '{slug}'` with `{slug}` and `{base}`.

**Usages relevant to this task:**
- `convention`: creation/publishing test styles (mock at the module import point), docstring style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): `create_topic`/`publish_topic` signatures unchanged; the rendered message contains both substituted placeholders
- [ ] **Code**: in `goga/topics/creation.py` and `goga/topics/publishing.py` replace every `("...").replace("{slug}", ...)` message site with `render_commit_template(template, slug, base_name)` (imported from `.exchange`); the default template constant `Create topic '{slug}'` (module constant, single-sourced); `creation.py`'s no-switch path renders the built-in default with the operation's `base_ref` as the base; unchanged result lines; the checkpoints receive the rendered message as before
- [ ] **Interface verification**: `python -m pytest tests/topics/test_creation.py tests/topics/test_publishing.py -v` — all pass
- [ ] **Logic tests**: `test_publish_topic_renders_create_section_template` — **Setup**: the publication mocks per the existing style; template `"Create {slug} from {base}"`. **Input**: `publish_topic("feat-x", "Fix retries.", "main", "Create {slug} from {base}", "2026")`. **Assertions**: the commit message is `Create feat-x from main` (both placeholders, `{base}` included — the old single-placeholder replace would leave it literal); adjust the existing creation/publishing message assertions to the template engine (unknown placeholders stay verbatim)
- [ ] **Debugging**: `python -m pytest tests/topics/ -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: unchanged signatures and result lines; the `{base}` placeholder available everywhere; single engine (no residual inline `.replace("{slug}"...)` message sites)
- [ ] **Lint**: `ruff check goga/topics/creation.py goga/topics/publishing.py` — fix formatting if necessary

### Task 14: The update operation — `updating.py` (TDD coding)

`update_topic` brings a topic up to its base under the configured strategy;
no confirmation; publish optional; `_restore_base` guards every conflict.

**Usages relevant to this task:**
- `exchanging` (imported): the build, plant, and push patterns — plant last; the lease binds to the pre-replay tip.
- `refs-and-switching` (imported): the tip-resolution pattern.
- `publishing` (imported): the publication push pattern.
- `checkpoints` (imported): the update notification.
- `convention`: docstring style, tests mock the imported git-cell names at the domain module's import point plus the hooks facade.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in the new `tests/topics/test_updating.py` — `update_topic(identifier, base_ref, strategy, commit_message, publish=False, year=None) -> str` importable from `goga.topics.updating`; public entry wraps its `_`-prefixed core exactly like `board.py`/`publishing.py` (`CalledProcessError`/`FileNotFoundError`/`OSError`/`RuntimeError`/`ImportError` → `click.ClickException`)
- [ ] **Code**: create `goga/topics/updating.py` implementing the verbatim algorithm:
    ```
    1. IF strategy is None: effective = "merge"
       ELIF strategy in {merge, rebase, ff-else-merge, ff-else-rebase}: effective = strategy
       ELSE: raise clean config error naming topics.update.strategy
    2. target = resolve_exchange_target(identifier, year)
       own_tip = resolve_ref_commit(target.branch)
    3. (local, _) = _base_branch_names(base_ref, list_branch_refs())
       rollback_tip = resolve_ref_commit(local) IF local exists ELSE None
       base = resolve_exchange_base(base_ref, target.branch, own_tip)
    4. IF is_ancestor(base.tip, own_tip):                          # already current
       - emit_updated(identity, base.name, base.tip, effective, "already-current", False)
       - RETURN result line                                       # publish publishes nothing
    5. realized = ("fast-forward"
                  IF effective in {ff-else-merge, ff-else-rebase}
                  AND is_ancestor(own_tip, base.tip)
                  ELSE effective)
    6. message = render_commit_template(commit_message or "Update topic '{slug}' from '{base}'",
                                        target.topic, base.name)
    7. IF target.current:                                         # the in-place path
       - not is_working_tree_clean() -> clean error + _restore_base
       - pre-flight: merge -> merge_tree(own_tip, base.tip)
                     rebase -> replay_commits(base.tip, own_tip)   # discarded
                     None -> clean error suggesting manual git + _restore_base
       - mutate: merge -> merge_into_current(base.tip, message)
                 rebase -> rebase_current_onto(base.tip)
                 ff     -> fast_forward_current_branch(base.tip)
       ELSE:                                                      # checkout-free
       - merge -> tree=merge_tree(own_tip, base.tip)
                  None  -> clean error suggesting manual git + _restore_base
                  commit=create_commit_from_tree(tree, [own_tip, base.tip], message)
                  point_branch_at_commit(target.branch, commit)
       - rebase -> tip=replay_commits(base.tip, own_tip)
                   None  -> clean error suggesting manual git + _restore_base
                   point_branch_at_commit(target.branch, tip)
       - ff     -> point_branch_at_commit(target.branch, base.tip)
    8. IF publish:
       - not origin_configured() -> clean error
       - merge/ff -> push_branch(target.branch)
       - rebase   -> twin exists ? push_branch_with_lease(target.branch, own_tip)
                                 : push_branch(target.branch)
       - a failed push -> clean error carrying git's reason    # the update stands
    9. outcome = {merge: "merged", rebase: "rebased", fast-forward: "fast-forwarded"}
       emit_updated(identity, base.name, base.tip, effective, outcome, publish)
       RETURN f"Updated topic {resolved_year}/{target.topic} from '{base.name}' via {effective} ({outcome})"
    ```
  - the rollback guard `_restore_base(base, rollback_tip)`: `if base.reconciled and rollback_tip is not None: point_branch_at_commit(base.local_branch, rollback_tip)` with suppressed restore failures — invoked on the dirty-tree error, the pre-flight conflict error, and every checkout-free build conflict (merge tree `None`, replay `None`)
  - the template default `Update topic '{slug}' from '{base}'` and the result line as module constants, single-sourced
- [ ] **Interface verification**: `python -m pytest tests/topics/test_updating.py -v` — contract tests pass
- [ ] **Logic tests** (the twelve design scenarios, in `tests/topics/test_updating.py`; mocked at `goga.topics.updating` — the exchange-core names, the git-cell names, the hooks facade; target/`ExchangeBase` fixtures):
  - `test_update_topic_checkout_free_merge_plants_two_parent_commit` — target `ExchangeTarget("feat-x", "feat-x", False)`; `resolve_ref_commit` → OWN; inventory without a local `main` but with `origin/main`; base `ExchangeBase("main", BASE_TIP, None, False)`; containments False; `merge_tree(OWN, BASE_TIP)` → TREE; `create_commit_from_tree` → NEW. **Input**: `update_topic(None, "main", None, None, publish=False, year="2026")`. **Assertions**: the parent order `[OWN, BASE_TIP]`; the message `Update topic 'feat-x' from 'main'`; the planted branch `feat-x`; the emitted facts `(identity, "main", BASE_TIP, "merge", "merged", False)`; the result line exactly `Updated topic 2026/feat-x from 'main' via merge (merged)`; `push_branch` not called
  - `test_update_topic_already_current_is_idempotent` — `is_ancestor(BASE_TIP, OWN)` → True; publish True. **Assertions**: no `merge_tree`/`point_branch_at_commit`/`push_branch`; the emitted `published` is False despite the flag; the line names `already-current`
  - `test_update_topic_invalid_strategy_is_config_error` — **Input**: `update_topic(None, "main", "squash", None)`. **Assertions**: `click.ClickException` naming `topics.update.strategy` and `squash`; `resolve_exchange_target` not called (the whitelist fires before anything else)
  - `test_update_topic_rebase_publish_uses_lease_against_pre_rebase_tip` — target not current; base `ExchangeBase("main", BASE_TIP, None, False)`; inventory carries `origin/feat-x`; `replay_commits(BASE_TIP, OWN)` → REPLAYED. **Input**: `update_topic("feat-x", "main", "rebase", None, publish=True)`. **Assertions**: the lease tip is exactly `OWN` (the pre-rebase own tip, not REPLAYED); `push_branch` not called; `replay_commits` called exactly once (the build itself — this path runs no separate pre-flight); the emitted outcome `"rebased"`, strategy `"rebase"`, published True
  - `test_update_topic_preflight_conflict_rolls_back_reconciliation` — target current; base `ExchangeBase("main", RECON, "main", True)`; local `main` in inventory → `rollback_tip = LOCAL_TIP`; `merge_tree(OWN, RECON)` → None. **Assertions**: `click.ClickException` raised; `point_branch_at_commit("main", LOCAL_TIP)` happened after the failed pre-flight; nothing else mutated
  - `test_update_topic_checkout_free_conflict_rolls_back_reconciliation` — target not current (another topic); base reconciled with rollback captured; `merge_tree(OWN, RECON)` → None (the build conflict). **Assertions**: `click.ClickException`; `point_branch_at_commit` called with `("main", LOCAL_TIP)` and never with `("feat-x", …)`; `create_commit_from_tree` not called; no emission of a merged outcome
  - `test_update_topic_publish_without_origin_is_clean_error` — `origin_configured` → False; the update itself succeeded (mocked plant ok). **Input**: `update_topic(..., publish=True)`. **Assertions**: `click.ClickException`; the planted update stands (the plant call remains in the recorded calls — the atomicity exception is deliberate)
  - `test_update_topic_ff_else_with_no_own_work_fast_forwards` — strategy `"ff-else-merge"`; `is_ancestor(OWN, BASE_TIP)` → True; a non-current topic. **Assertions**: no `create_commit_from_tree`; the plant target is BASE_TIP; the emitted strategy is `"ff-else-merge"` with outcome `"fast-forwarded"` (the configured name stays; the realized kind is the outcome)
  - `test_update_topic_current_topic_dirty_tree_clean_error` — target current; `is_working_tree_clean` → False; base reconciled with rollback captured. **Assertions**: clean error before any mutation call; the reconciliation restored
  - `test_update_topic_current_topic_merge_is_in_place` — target current; clean tree; strategy merge. **Assertions**: `merge_tree` called exactly once (the discarded pre-flight) and `merge_into_current` once; no `point_branch_at_commit` on the topic branch
  - `test_update_topic_current_topic_rebase_is_in_place_with_lease` — target current; clean tree; strategy rebase, publish=True; inventory carries `origin/feat-x`; `replay_commits(BASE_TIP, OWN)` → REPLAYED. **Assertions**: `replay_commits` called exactly once (the pre-flight — the real mutation is git's own rebase); `rebase_current_onto` called once with BASE_TIP; `point_branch_at_commit` never called on `feat-x`; the lease tip is exactly OWN; the emitted outcome `"rebased"`, published True
  - `test_update_topic_lease_rejection_is_clean_error_update_stands` — as above, but `push_branch_with_lease` raises `CalledProcessError(1, cmd)` with stderr `! [rejected] feat-x -> feat-x (stale info)`. **Assertions**: `click.ClickException` carrying `stale info`; `push_branch_with_lease` called exactly once (no retry — the retry cycle belongs to propagate alone); `_restore_base` not invoked; `rebase_current_onto` remains in the recorded calls
- [ ] **Debugging**: `python -m pytest tests/topics/test_updating.py -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: no confirmation; every conflict detected read-only before any topic mutation; the in-place path never runs without its pre-flight; the lease binds to the own tip immediately before the rebase with no extra fetch; exactly one result line
- [ ] **Lint**: `ruff check goga/topics/updating.py tests/topics/test_updating.py` — fix formatting, apply decomposition if necessary

### Task 15: The propagation operation — `propagating.py` (TDD coding)

The two halves of the delivery: a fully read-only plan the caller confirms,
then the checkout-free build-plant-push with one retry cycle and a uniform
rollback.

**Usages relevant to this task:**
- `exchanging` (imported): the build, plant, fetch, and push patterns.
- `refs-and-switching` (imported): the tip-resolution pattern.
- `checkpoints` (imported): the propagate notification.
- `convention`: docstring style, tests mock at the domain module's import point plus the hooks facade.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in the new `tests/topics/test_propagating.py` — `PropagationPlan(target, base_ref, strategy, message, year)` frozen kw_only; `resolve_propagation` / `execute_propagation` importable with the declared signatures; both public entries wrap their `_`-prefixed cores (`CalledProcessError`/`FileNotFoundError`/`OSError`/`RuntimeError`/`ImportError` → `click.ClickException`)
- [ ] **Code**: create `goga/topics/propagating.py`:
  - `PropagationPlan` — frozen kw_only dataclass
  - `resolve_propagation` per the verbatim algorithm:
    ```
    1. strategy in {merge, ff, squash} else clean config error (topics.propagate.strategy)
    2. target = resolve_exchange_target(identifier, year)
    3. not origin_configured() -> clean error
    4. (local, _) = _base_branch_names(base_ref, list_branch_refs())
       local == resolve_current_branch_name() -> clean error "switch away first"
    5. message = render_commit_template(
          commit_message or "Propagate topic '{slug}' into '{base}'", target.topic, base_ref)
    6. RETURN PropagationPlan(target, base_ref, strategy, message, resolved_year)
    ```
    Fully read-only — no fetch, no ref write, no working-copy touch; the ff fast-forwardability stays unverified here (authoritative only at execution)
  - `execute_propagation` per the verbatim algorithm:
    ```
    1. own_tip = resolve_ref_commit(plan.target.branch)
       (local, _) = _base_branch_names(plan.base_ref, list_branch_refs())
       rollback_tip = resolve_ref_commit(local) IF local exists ELSE None
    2. base = resolve_exchange_base(plan.base_ref, plan.target.branch, own_tip)
       base.local_branch == resolve_current_branch_name() -> clean error
    3. IF is_ancestor(own_tip, base.tip):                          # reachability idempotency
       - emit_propagated(..., "nothing-to-do"); RETURN line        # reconciliation stands
    4. base_tree = resolve_commit_tree(base.tip)
       merge/squash: tree = merge_tree(base.tip, own_tip); None -> conflict
                     merge   -> delivery = create_commit_from_tree(tree, [base.tip, own_tip], message)
                     squash  -> delivery = create_commit_from_tree(tree, [base.tip], message)
       ff: not is_ancestor(base.tip, own_tip) -> clean error suggesting manual git (+ rollback)
           delivery = own_tip; delivery_tree = resolve_commit_tree(own_tip)
       IF delivery_tree == base_tree:                              # content idempotency
       - emit_propagated(..., "nothing-to-do"); RETURN line        # nothing planted/pushed
    5. plant: local path -> point_branch_at_commit(base.local_branch, delivery)
             remote-only -> nothing planted locally
    6. push: local path -> push_branch(base.local_branch)
             write-through -> push_revision_to_branch(delivery, short_name(plan.base_ref))
    7. ON push failure WITH the concurrent-movement stderr signature, ONCE:
       - echo f"Fetching origin/{short}..."; fetch_branch(short)
       - re-run the resolution tail (projections/containment/reconciliation)
       - rebuild delivery (step 4 logic, nothing-to-do included); re-plant; re-push
       - a second rejection -> rollback + clean error
    8. ON any failure: rollback (point_branch_at_commit(base.local_branch, rollback_tip)
       when both are not None — removes a written reconciliation, a no-op otherwise),
       then the clean error
    9. emit_propagated(identity, base.name, plan.strategy, outcome)   # merged|fast-forwarded|squashed
    10. RETURN f"Propagated topic {year}/{slug} into '{base.name}' via {strategy} ({outcome})"
    ```
    The concurrent-movement rejection signature: stderr matches `rejected`, `non-fast-forward`, or `fetch first`; `short_name` strips a leading `origin/`; the template default and the result line as module constants, single-sourced
- [ ] **Interface verification**: `python -m pytest tests/topics/test_propagating.py -v` — contract tests pass
- [ ] **Logic tests** (the fourteen design scenarios, in `tests/topics/test_propagating.py`; mocked at `goga.topics.propagating`):
  - `test_resolve_propagation_is_read_only` — target mocked; inventory with local `main`; current branch `feat-x`. **Input**: `resolve_propagation("feat-x", "main", None, None, year="2026")`. **Assertions**: `PropagationPlan(target, "main", "merge", "Propagate topic 'feat-x' into 'main'", "2026")`; `resolve_exchange_base`/`fetch_branch`/any write not called (a declined confirmation must have performed nothing)
  - `test_execute_propagation_merge_builds_plants_pushes` — own tip OWN; base `ExchangeBase("main", BASE_TIP, "main", False)`; rollback LOCAL_TIP; reachability False; `merge_tree(BASE_TIP, OWN)` → TREE; `resolve_commit_tree` → base tree `"t0"`, delivery tree `"t1"`; `create_commit_from_tree` → DELIVERY; `push_branch` ok. **Input**: plan (merge, message M). **Assertions**: the parent order `[BASE_TIP, OWN]`; the plant `("main", DELIVERY)`; one `push_branch("main")`; no `push_revision_to_branch`; the emitted `(identity, "main", "merge", "merged")`; the line `Propagated topic 2026/feat-x into 'main' via merge (merged)`
  - `test_execute_propagation_reachability_nothing_to_do` — `is_ancestor(OWN, BASE_TIP)` → True; base reconciled=True with local branch `main`, rollback captured. **Assertions**: no `merge_tree`, no plant, no push; `point_branch_at_commit` not called with the rollback tip (the reconciliation **stands** — sanctioned base bookkeeping); the emitted outcome `nothing-to-do`; the line names it
  - `test_execute_propagation_content_nothing_to_do` — reachability False; `merge_tree` → TREE; `resolve_commit_tree` → `"t0"` for both the base tip and the delivery. **Assertions**: no `create_commit_from_tree`, no plant, no push; the emitted outcome `nothing-to-do` (carried means content — e.g. a squash already landed with a different commit)
  - `test_execute_propagation_squash_single_parent` — merge tree ok; trees differ. **Assertions**: exactly one `-p` parent (BASE_TIP); the outcome `("squash", "squashed")`
  - `test_execute_propagation_ff_delivers_own_tip_without_commit` — `is_ancestor(BASE_TIP, OWN)` → True; reachability False. **Assertions**: no `create_commit_from_tree`; the plant target is OWN; emit `("ff", "fast-forwarded")`
  - `test_execute_propagation_ff_impossible_rolls_back` — both containments False; base reconciled with rollback captured. **Assertions**: `click.ClickException` suggesting manual git; the restore `point_branch_at_commit("main", LOCAL_TIP)` happened (regression of the fixed CODEMANIFEST defect — the ff error joins the uniform rollback); nothing pushed
  - `test_execute_propagation_retry_cycle_recovers_once` — `push_branch` fails first with `CalledProcessError(1, cmd)` stderr `! [rejected] main -> main (non-fast-forward)`; the retry fetch + re-resolution yields a moved `BASE_TIP2` (already containing the first delivery); second push succeeds. **Assertions**: `fetch_branch` called exactly once during retry; the echo line `Fetching origin/main...` printed; exactly two `push_branch` calls; no restore with the rollback tip on success; the result line returned
  - `test_execute_propagation_second_rejection_fails_with_rollback` — both pushes rejected with the signature; reconciliation was written. **Assertions**: `click.ClickException` carrying git's reason; `point_branch_at_commit("main", LOCAL_TIP)` (the pre-resolution tip) called after the second failure; exactly two pushes
  - `test_execute_propagation_write_through_remote_only_base` — base `ExchangeBase("origin/main", BASE_TIP, None, False)`; no local `main` → no rollback tip. **Assertions**: `point_branch_at_commit` not called; `push_revision_to_branch` called with `(DELIVERY, "main")` (the `origin/` prefix stripped); no rollback attempted
  - `test_resolve_propagation_invalid_strategy_is_config_error` — **Input**: `resolve_propagation("feat-x", "main", "merge-nono", None)`. **Assertions**: `click.ClickException` containing `topics.propagate.strategy` and `merge-nono`; `resolve_exchange_target` not called
  - `test_resolve_propagation_without_origin_is_clean_error` — `origin_configured` → False. **Assertions**: `click.ClickException` mentioning origin; nothing resolved further
  - `test_resolve_propagation_rejects_current_branch_base` — the addressed topic resolved on branch `feat-x` (not current); inventory carries a local `main`; `resolve_current_branch_name` → `"main"`; origin configured. **Input**: `resolve_propagation("feat-x", "main", None, None)`. **Assertions**: `click.ClickException` asking to switch away first; `render_commit_template` not called; no `PropagationPlan` built
  - `test_execute_propagation_current_branch_base_guard` — `base.local_branch == "feat-x"` == current branch. **Assertions**: clean error before any build (the plan may be executed later, when the user has switched)
- [ ] **Debugging**: `python -m pytest tests/topics/test_propagating.py -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: always checkout-free; both nothing-to-do forms emit and return exit-0 lines; the topic's branch and directory untouched; failure atomicity uniform; the retry exactly once
- [ ] **Lint**: `ruff check goga/topics/propagating.py tests/topics/test_propagating.py` — fix formatting, apply decomposition if necessary

### Task 16: Topics facade — export the exchange operations (infrastructure)

The CLI's import path — the facade-only rule.

**Usages relevant to this task:**
- `convention`: facade/`__all__` rules, relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] In `goga/topics/__init__.py` import and `__all__`-export the ten new names: `ExchangeBase`, `ExchangeTarget`, `PropagationPlan`, `resolve_exchange_base`, `resolve_exchange_target`, `render_commit_template`, `update_topic`, `resolve_propagation`, `execute_propagation`, `resolve_divergence`
- [ ] Update the facade/module docstring's mutation sentence — the sanctioned network set grew (the targeted reported fetches, the inherent propagate push, the update publish push)
- [ ] Verify facade accessibility: `python -m pytest tests/topics/ -v` — including `test_topics_facade_exports_operations`: **Input**: `from goga.topics import update_topic, resolve_propagation, execute_propagation` (and `__all__` inspection). **Assertions**: present in `__all__` beside the existing surface. **Sufficiency**: the CLI's import path — the facade-only rule
- [ ] Lint: `ruff check goga/topics/` — fix formatting if necessary

**Package: `goga/commands/topics`**

### Task 17: CLI — `update` / `propagate` subcommands, board config step, create rung (TDD coding)

The two new subcommands, the board's configuration-load first step, the
create template rung switch, and the `publish_commit` sweep. Input resolution
per the contract: flag beats configuration with no current-HEAD rung;
strategy and template verbatim; update asks no confirmation; propagate asks
exactly one with the `--yes` escape.

**Usages relevant to this task:**
- `update` / `propagate` (imported from `goga/topics`): the consumer contracts — the CLI maps flags to the documented inputs and adds exactly one confirmation on propagate (naming the target and the push).
- `project-configuration` (imported from `goga/config`): read `topics.base_ref`, `topics.update.{strategy,commit}`, `topics.propagate.{strategy,commit}` with the per-sub-section None-guard.
- `checkpoints` (imported): the config amendment checkpoint at the configuration-load moment (`ConfigHooks().amend_config(config=...)`, summary lines to stderr, FileNotFoundError → None — the `_topics_section()` lazy load).
- `click` (project cook): decorators, echo, the confirmation with the `sys.stdin.isatty()` guard, exit-code propagation.
- `convention`: the CLI test style (`CliRunner`, the `_TtyStdin` fixture, mock at the `goga.topics` import point).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in `tests/commands/topics/test_topics.py` — the group surface enumerations (the sorted subcommand list, the per-subcommand parametrizations — the five-name lists around the group surface tests) grow `update` and `propagate` to seven entries; `topics update --help` and `topics propagate --help` exist
- [ ] **Code**: in `goga/commands/topics/topics.py`:
  - `update` — `@topics.command("update")`, optional `IDENTIFIER` positional, `--base-ref`, `--publish/-p`, `@click.pass_obj` with the shared `_TopicsScope`; resolution: `section = _topics_section()` lazily (only when `base_ref is None` or the template/strategy must come from the configuration; the three read together means one load); `base = base_ref or section.base_ref` → None → clean error naming the flag and the configuration line, before anything else; `strategy = section.update.strategy if section and section.update else None` (verbatim); `template = section.update.commit ...` (verbatim); delegate to `update_topic(identifier, base, strategy, template, publish, scope.year)`; echo the result line; exit 0/1; no strategy validation at the CLI; no confirmation; the `--help` text names the addressee rule (omitted IDENTIFIER addresses the current topic)
  - `propagate` — `@topics.command("propagate")`, optional `IDENTIFIER`, `--base-ref`, `--yes/-y`; the same base/strategy/template resolution over `topics.propagate.*`; `plan = resolve_propagation(identifier, base, strategy, template, scope.year)`; without `yes`: `not sys.stdin.isatty()` → clean error (naming the interactive-terminal requirement and `--yes`); else one `click.confirm(f"Propagate topic {plan.target.topic} into '{base}' (pushes to origin)?")` — declined → `ctx.exit(0)` with nothing done; `execute_propagation(plan)`; echo the line
  - `board` — new first step: `section = _topics_section()` (the `clear`-style lazy load; missing file → None); `base = section.base_ref if section is not None else None`; both `collect_topic_board` calls receive `base_ref=base`; the json/info conflict check now precedes (renumbered steps); the rest unchanged
  - `create` — the template rung becomes `section.create.commit` (per-sub-section None-guard); the `--commit` help text names `topics.create.commit`; remove the `section.publish_commit` read (topics.py:339) and the retired-key mention in the help (topics.py:256)
  - the group docstring's subcommand list and the module docstring grow the two subcommands; the `--info` help text names the todo and base columns
- [ ] **Interface verification**: `python -m pytest tests/commands/topics/test_topics.py -v` — contract tests pass
- [ ] **Logic tests** (in `tests/commands/topics/test_topics.py`):
  - `test_cli_update_resolves_configuration_inputs` — **Setup**: CliRunner; `load_project_config` + `ConfigHooks` mocked to an overlay whose effective topics is `TopicsConfig(base_ref="origin/main", update=TopicsUpdateConfig(strategy="rebase", commit="U {slug}"))`; `update_topic` mocked (at the `goga.topics` import point). **Input**: `["topics", "update"]`. **Assertions**: the delegation kwargs `update_topic(None, "origin/main", "rebase", "U {slug}", False, None)`; the amendment summary lines went to stderr; exit 0; the domain's line echoed to stdout
  - `test_cli_propagate_confirmation_and_yes` — **Setup**: CliRunner; `resolve_propagation` mocked to a plan (`target.topic="feat-x"`, `base_ref="main"`); `execute_propagation` mocked returning a line; the confirm gate needs a terminal — the `_TtyStdin` fixture (a plain string `input=` is not a TTY and would hit the non-interactive clean error instead). **Input**: (a) `["topics", "propagate"]` with `input=_TtyStdin("y\n")`; (b) `["topics", "propagate", "--yes"]` (no TTY needed); (c) `input=_TtyStdin("n\n")`; (d) a plain non-TTY stdin without `--yes`. **Assertions**: (a) output contains `feat-x` and `main` and a push mention; `execute_propagation` called once; (b) called once without any prompt text; (c) `execute_propagation` not called, exit_code 0; (d) not called, exit_code 1, the error names the interactive-terminal requirement and `--yes`
  - `test_cli_board_passes_configured_base` — **Setup**: `_topics_section` mocked to `TopicsConfig(base_ref="main")`; `collect_topic_board`/`aggregate_topic_board` mocked. **Input**: `["topics", "board", "--info"]`. **Assertions**: `collect_topic_board` received `base_ref="main"` in both views; with the configuration absent (None) the parameter is None and the command still exits 0
  - `test_cli_create_template_comes_from_create_section` — **Setup**: the effective topics `TopicsConfig(create=TopicsCreateConfig(commit="C {slug}"))`. **Input**: `["topics", "create", "feat-x", "--publish", "--todo", "Fix."]`. **Assertions**: `create_topic` received the template `"C {slug}"` (not the retired `publish_commit`, not the default)
  - `test_cli_update_help_names_addressee_rule` — **Input**: `["topics", "update", "--help"]`. **Assertions**: the help text states that an omitted IDENTIFIER addresses the current topic
- [ ] **Debugging**: `python -m pytest tests/commands/topics/ -x` — fix implementation code until all tests pass; move every mock of a topics-domain name to the `goga.topics` import point; update the existing `create`/`clear` tests that asserted the flat `publish_commit` rung
- [ ] **Contract re-verification**: exit codes per the contract (0 on success — a declined confirmation and a nothing-to-do delivery included; 1 on error); no CLI-layer validation added; the `-y` collision documented
- [ ] **Lint**: `ruff check goga/commands/topics/topics.py tests/commands/topics/test_topics.py` — fix formatting, apply decomposition if necessary

### Task 18: Renderers — the Base column and the `divergence` key (TDD coding)

The visible board change: the sixth/fifth share rules under `--info` and the
always-present JSON key.

**Usages relevant to this task:**
- `beautiful_json` (project cook): the pretty-printed, sorted-keys JSON serialization.
- `click` (project cook): the echo of the rendered table.
- `convention`: render test style (`tests/commands/topics/test_render.py`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): in `tests/commands/topics/test_render.py` — the three renderer signatures unchanged; the new column/key observable
- [ ] **Code**: in `goga/commands/topics/render.py`:
  - `render_topic_board` — without `info` unchanged (the four-column rule); under `info` the six-column rule: topic, branch, hosts, todo, base each capped at `(width - dividers) // 6`, statuses the non-negative remainder, minimum 8 per column; header order `Topic | Branch | Hosts | Todo | Base | Statuses`; the Base cell carries the marker (`behind`/`current`) or empty when None
  - `render_topic_host_rows` — the five-column rule under `info`: topic, branch, todo, base each capped at one fifth, statuses the remainder, minimum 8; header `Topic | Branch | Todo | Base | Statuses`
  - truncation/ellipsis, the current asterisk, the row dividers, and the narrow-terminal exception behave exactly as the existing columns
  - `render_board_json` — every entry shapes into the eight keys `topic, branch, hosts, statuses, current, remote, todo, divergence`; every record into the same without `hosts`; `divergence` is the string or null — always present, never omitted
- [ ] **Interface verification**: `python -m pytest tests/commands/topics/test_render.py -v` — contract tests pass
- [ ] **Logic tests** (in `tests/commands/topics/test_render.py`):
  - `test_render_topic_board_info_six_columns_with_base` — **Setup**: entries `[BoardEntry(topic="feat-x", branch="feat-x", hosts=["feat-x", "main"], statuses=["[todo]"], current=True, remote=False, todo="Fix retries", divergence="behind")]`. **Input**: `render_topic_board(entries, width=120, info=True)`. **Assertions**: the header words in order `Topic | Branch | Hosts | Todo | Base | Statuses`; the cell `behind` in Base; a None divergence renders an empty cell (second entry); the table never exceeds the width above the narrow threshold
  - `test_render_board_json_carries_divergence_key` — **Input**: `render_board_json([entry_with_divergence, entry_without])`. **Assertions**: every JSON object has `divergence` (`"behind"` / `null`); the entry key set is exactly `{topic, branch, hosts, statuses, current, remote, todo, divergence}`; records shape without `hosts`
- [ ] **Debugging**: `python -m pytest tests/commands/topics/test_render.py -x` — fix implementation code until all tests pass
- [ ] **Contract re-verification**: read-only over the input; the without-`info` rules unchanged; the JSON key set exact
- [ ] **Lint**: `ruff check goga/commands/topics/render.py tests/commands/topics/test_render.py` — fix formatting if necessary

### Task 19: Integration verification across the exchange stack (integration tests)

No new scenarios — the cross-cell wiring check over the finished stack: the
78 design scenarios all green, every facade importable, the retired key
swept, the contracts untouched.

**Usages relevant to this task:**
- `convention`: the full-suite commands (`pytest tests/ -x`, `ruff check`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Run the full suite: `python -m pytest tests/ -x` — all tests pass (all 78 design scenarios plus the pre-existing suites)
- [ ] Facade smoke across the three grown facades: `python -c "from goga.config import TopicsCreateConfig, TopicsUpdateConfig, TopicsPropagateConfig; from goga.topics.git import require_git_version, is_ancestor, resolve_commit_tree, merge_tree, create_commit_from_tree, replay_commits, point_branch_at_commit, merge_into_current, rebase_current_onto, fast_forward_current_branch, fetch_branch, push_branch_with_lease, push_revision_to_branch; from goga.topics import update_topic, resolve_propagation, execute_propagation; print('facades ok')"` — imports succeed
- [ ] CLI surface smoke: `python -m goga topics --help` (or the project's CLI entry) lists the seven subcommands including `update` and `propagate`
- [ ] Sweep for residual references: `grep -rn "publish_commit" goga/ tests/` returns hits only in the loader's documented silence context (none expected anywhere in code) — any residual reader is removed
- [ ] Contracts untouched: `goga lint` exits 0 (81 cells, 0 errors)
- [ ] Lint the whole change: `ruff check goga/ tests/` — clean

---

## Validation Commands

- `python -m pytest tests/hooks/catalog/ -v`: the two new action records
- `python -m pytest tests/config/ -v`: nested models, loader step 9, facade 17, overlay tree
- `python -m pytest tests/topics/git/ -v`: the 13 exchange routines + facade 28
- `python -m pytest tests/topics/ -v`: exchange core, board divergence, updating, propagating, facade, hooks contexts/events
- `python -m pytest tests/commands/topics/ -v`: the CLI subcommands and the renderers
- `python -m pytest tests/ -x`: Run all tests
- `ruff check goga/ tests/`: Lint check
- `goga lint`: CODEMANIFEST integrity — the contracts stay untouched (81 cells, 0 errors)
- Facade checks: the Task 19 import smoke over `goga.config`, `goga.topics.git`, `goga.topics` — verify that all facade entities are importable

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is accessible from the facade (`goga.config` 17, `goga.topics.git` 28, `goga.topics` +10, hooks contexts exported)
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior (the algorithms above verbatim)
- [ ] Contract dependencies are met (imports resolve; no cross-imports between cells)
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them (Task 19 stack verification; CLI tasks exercise the cross-cell wiring)
- [ ] No package boundary was expanded
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task
