# Architecture plan — Topics publish command, tool config loading standard, and schema validation gate

Task source: `.goga/history/2026/topics-publish-and-tool-config/task.md`; accepted ADR:
`.goga/history/2026/topics-publish-and-tool-config/adr.md`. Three changes, one plan.
Settled decisions: verdict types re-declared in `goga/schema/hooks` (no inter-zone edge);
`topic_published` fires exactly when a push to origin completed (idempotent publish-command
outcomes emit; `already-current` update and `nothing-to-do` propagate do not);
`remote_branch` in the `origin/<name>` form; typed recursive `SchemaNode` view;
`resolve_commit_message` added to `goga/topics/git`; the tool-config loader lives in the
new child cell `goga/config/tool` re-exported by the `goga/config` facade.

## Topic

Short name: **Topics publish, tool config loading, and schema validation gate**
Plan path: `.goga/history/2026/topics-publish-and-tool-config/arch.md`

## Implementation Order

1. **`goga/hooks/catalog`** (modify) — leaf (convention only); the additive record must exist
   before the schema zone resolves the new address.
2. **`goga/topics/git`** (modify) — leaf access zone; `resolve_commit_message` is consumed by
   `goga/topics`.
3. **`goga/config/tool`** (create) — new leaf cell; imports nothing inside the project.
4. **`goga/config`** (modify) — facade; embeds the new type from `goga/config/tool`.
5. **`goga/topics/hooks`** (modify) — depends on `goga/hooks` + `goga/history`; the reshaped
   context and emission method must exist before `goga/topics` wires its emission sites.
6. **`goga/topics`** (modify) — depends on `goga/topics/git` (+`resolve_commit_message`),
   `goga/topics/hooks` (reshaped `emit_published`), `goga/history`, `goga/topics/editor`.
7. **`goga/schema/hooks`** (modify) — depends on `goga/hooks`; delivers the new gate types and
   checkpoint method before the domain fires them.
8. **`goga/schema`** (modify) — depends on `goga/schema/hooks` (+`SchemaNode`,
   `GateVerdict`) and `goga/ast`.
9. **`goga/commands/tool`** (modify) — depends on `goga/ast` and, newly, `goga/config`
   (`load_tool_config`) — the only new dependency edge of the plan.
10. **`goga/commands/topics`** (modify) — depends on `goga/topics` (`publish_existing_topic`).
11. **`goga/commands/schema`** (modify) — depends on `goga/schema` (failure rendering).

## Artifacts

### 1. `goga/hooks/catalog/CODEMANIFEST` — MODIFY

**ADD** to `declared_actions` → `Requirements` (after the `schema/amend_cell` bullet):

```
- The catalog carries the schema validation-gate action — the record
  domain="schema", name="validate_schema", error_class="hard": a veto
  or a crashed hook of the action stops the schema command; the walk
  runs every subscribed tool's hooks to completion and collects one
  violation per tool
```

Nothing else changes; the `topics/topic_published` record (soft) stays verbatim.

### 2. `goga/topics/git/CODEMANIFEST` — MODIFY

**ADD** to Body (after `resolve_ref_commit`):

```yaml
"resolve_commit_message(commit: str) -> message: str":
  location: publish.py
  annotations: |
    Read the commit message of one commit — the git fact of the
    publication context.

    `commit`: the commit hash
    `message`: the commit's message text as git stores it, verbatim

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Ask git for the commit message of `commit`, verbatim as git
       stores it
    2. An unresolvable commit surfaces as a clean error carrying the
       git reason

    Requirements:
    - Read-only — no ref, index, or working-copy mutation
    - An unresolvable commit is a clean error carrying the git reason

    Constraints:
    - Do not print — the caller owns all output
```

**MODIFY** `goga/topics/git/.usages/publishing.md` — **ADD** section:

```md
## Reading publication facts

The publication context carries the commit facts of the remote branch
tip after the operation. `resolve_commit_message` reads the message of
one commit — read-only, verbatim as git stores it.

    from goga.topics.git import resolve_commit_message

    message = resolve_commit_message(tip_hash)
```

### 3. `goga/config/tool/CODEMANIFEST` — CREATE

```yaml
Usages:
  convention: .goga/usages/conventions.md
  yaml: |
    Use yaml.safe_load() to parse the tool config file.
    Requires the PyYAML library.

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of
    development and testing in the project

  This cell owns the read side of the tool-config standard: the
  standardized path composition of one tool config file and its raw
  passthrough load. The write side buffers verbatim filenames under
  the same path standard; this loader reads them back with no
  interpretation — the content belongs to the tool that owns it.
  Use the `yaml` practice for the raw parse. Use relative imports.

---

"load_tool_config(tool: str, filename: str, root: Path | None = None) -> data: object | None":
  location: loader.py
  annotations: |
    Load one tool config file — the read-side counterpart of the
    tool-config write standard.

    `tool`: the tool identity — the directory name under .goga/tools
    `filename`: the config file name, verbatim with extension — exact
                match
    `root`: optional root-directory override for tests; None uses the
            project-root anchor of the configuration loaders
    `data`: the raw parsed content as-is — a mapping, a string, a
            list, whatever the YAML parses to — or None when the file
            is absent

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `yaml` practice for the raw parse.

    Algorithm:
    1. Compose the path <root>/.goga/tools/<tool>/<filename> with
       `filename` taken verbatim
    2. A `filename` that is empty, carries a path separator, or equals
       .. — a non-flat name segment — is a clean error before any read
    3. An absent file returns None — absence is the normal state of a
       tool config
    4. A present file parses via the `yaml` practice and returns the
       raw value as-is

    Requirements:
    - Path standardization only — the same standard as the write side
    - No content models, no structural expectations, no validation
    - No merging with any configuration layer, no caching

    Constraints:
    - Do not interpret the content — interpreting is the consuming
      tool's responsibility

---

Author: Goga
CreatedAt: 29/09/26
Description: |
  Owner of the read side of the tool-config standard.
```

### 4. `goga/config/CODEMANIFEST` — MODIFY

**ADD** to `Imports` (new entry after the `goga/config/git` entry):

```yaml
  - Types:
      - load_tool_config
    From: goga/config/tool
```

**ADD** to Body (embeddings, after `->resolve_project_name: {}`):

```yaml
->load_tool_config: {}
```

**REPLACE** the facade paragraph of the global `Annotations` with:

```
This cell is a re-export facade: it embeds (re-exports) all configuration
types from goga/config/project (project configuration, including the
two-part build section and the topics section),
goga/config/home (home/docker configuration), goga/config/git
(git-environment introspection — `resolve_project_name`), and
goga/config/tool (tool-config loading — the read side of the
tool-config standard) so consumers import a single entry point (From:
goga/config). It owns no behavior — all logic lives in the child
cells.
```

**REPLACE** the footer `Description` with:

```
Re-export facade — embeds project (goga/config/project), home
(goga/config/home), git-introspection (goga/config/git), and
tool-config (goga/config/tool) configuration types so consumers import
a single entry point. Owns no behavior.
```

**CREATE** `goga/config/.usages/tool-configuration.md`:

```md
# config — reading tool configuration

How to read a tool config file through the `goga.config` facade. For
consumers that need a tool's own configuration: the tool dispatcher's
config injection, tool packages reading their sibling files,
higher-level orchestration.

`load_tool_config` takes the tool identity and a file name — verbatim,
with extension — and returns the raw parsed content as-is, or `None`
when the file is absent. The path standard is fixed on both sides:
`.goga/tools/<tool>/<filename>`.

## Reading a tool config

    from goga.config import load_tool_config

    data = load_tool_config("coverage", "config.yml")     # mapping, string, list — as parsed
    data = load_tool_config("coverage", "overrides.yml")  # None when absent

- Absence is the normal state of a tool config — `None`, never an
  error.
- The file name is flat and verbatim: non-empty, no separators, no
  `..` — anything else is a clean error naming the file name.
- The returned value is the raw parse — no models, no validation, no
  merging with the project or home layers, no caching.
- Interpreting the content is the consuming tool's responsibility.
- Tests may pass a `root` directory override to read a prepared tree.

## The standard

The onboarding engine is the single writer: it buffers verbatim file
names and writes them under the same path. Reading follows the write
side exactly — no suffix rules, no fallbacks.
```

### 5. `goga/topics/hooks/CODEMANIFEST` — MODIFY

**ADD** to the global `Annotations` (after the update/propagate paragraph):

```
The publication moment is publication-centric: the context carries
the delivery facts — the remote branch that received the work, the
commit facts of the tip that remote branch carries after the
operation, and the outcome kind — never the facts of whichever
operation invoked the emission. The idempotent outcome kinds emit
like any other.
```

**REPLACE** the `TopicPublished` declaration with:

```yaml
"TopicPublished(identity: TopicIdentity, remote_branch: str, commit_hash: str, commit_message: str, outcome: str)":
  location: contexts.py
  annotations: |
    The read-only context of the publication notification — the
    delivery facts of one completed publication.

    `identity`: the identity of the published topic
    `remote_branch`: the origin branch that received the delivery, in
                     the origin/<name> form — the topic's own twin, or
                     the base branch of a delivery into a base
    `commit_hash`: the hash of the commit the remote branch carries
                   at its tip after the operation
    `commit_message`: the message of that commit
    `outcome`: the outcome kind — exactly one of pushed, up-to-date,
               remote-ahead

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a completed publication
    - The outcome value is exactly one of the three fixed kinds
  properties:
    "identity -> TopicIdentity": |
      The identity of the published topic.
    "remote_branch -> str": |
      The origin branch that received the delivery, in the
      origin/<name> form.
    "commit_hash -> str": |
      The hash of the commit the remote branch carries at its tip
      after the operation.
    "commit_message -> str": |
      The message of the commit the remote branch carries at its tip
      after the operation.
    "outcome -> str": |
      The outcome kind — pushed, up-to-date, or remote-ahead.
```

**REPLACE** the `emit_published` method of `TopicHooks` with:

```yaml
    "emit_published(identity: TopicIdentity, remote_branch: str, commit_hash: str, commit_message: str, outcome: str)": |
      Emit the publication notification — the delivery facts of one
      completed publication.

      `identity`: the identity of the published topic
      `remote_branch`: the origin branch that received the delivery, in
                       the origin/<name> form
      `commit_hash`: the hash of the commit the remote branch carries at
                     its tip after the operation
      `commit_message`: the message of that commit
      `outcome`: pushed, up-to-date, or remote-ahead

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicPublished` context from the values
      2. Emit the address domain="topics", action="topic_published" via
         `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - A failing hook is skipped with a warning under the soft error
        class of the action
```

**MODIFY** `goga/topics/hooks/.usages/checkpoints.md` — in "Emit after the moment",
**REPLACE** the `emit_published` example and its follow-up facts with:

```md
hooks.emit_published(
    identity,
    remote_branch="origin/feat-x",
    commit_hash=tip_hash,
    commit_message=tip_message,
    outcome="pushed",
)
```

```md
- `topic_published` — `TopicPublished`: `identity`, `remote_branch`
  (origin/<name> — the branch that received the delivery),
  `commit_hash` / `commit_message` (git facts of the commit the remote
  branch carries at its tip after the operation), `outcome` (pushed /
  up-to-date / remote-ahead). The idempotent up-to-date and
  remote-ahead kinds emit like any other; a publication that pushed
  nothing — an already-current update, a nothing-to-do delivery —
  emits nothing.
```

### 6. `goga/topics/CODEMANIFEST` — MODIFY

**ADD** `resolve_commit_message` to the `Types` list of the `From: goga/topics/git`
import entry (list order follows the entry's existing convention).

**Global `Annotations`:**

**ADD** to the zone description (after the clear-scope sentence, inside the
operations enumeration):

```
the publication of an existing topic branch as an operation of its
own — one targeted fetch of its own origin twin, the four-outcome
resolution, and one result line naming the outcome kind
```

**REPLACE** the sanctioned-network-set sentence with:

```
The sanctioned network set is exact: the targeted fetch of the
operation's own refs (each reported by one stdout line before it
runs), the publication fetch of a topic's own twin and its
publication push, the push inherent to every propagate, the explicit
update publish push (plain or lease-protected), and the deletion
pushes; nothing else ever fetches, and the board never touches the
network.
```

**ADD** to Body (after `publish_topic`):

```yaml
"publish_existing_topic(identifier: str | None, year: str | None = None) -> result: str":
  location: publishing.py
  annotations: |
    Deliver an existing topic branch to origin — the publication of a
    topic's own branch as an operation of its own.

    `identifier`: the addressee input; None addresses the current topic
    `year`: optional year as four digits; None means the current year
    `result`: one line naming the outcome kind

    Apply the `exchanging` practice for the fetch and containment
    patterns.
    Apply the `refs-and-switching` practice for the revision-resolution
    patterns.
    Apply the `publishing` practice for the publication push pattern.
    Apply the `checkpoints` practice for the publication notification.

    Algorithm:
    1. Resolve the addressee via `resolve_exchange_target`
    2. `origin_configured` reads False -> clean error before any
       network operation
    3. Resolve the own tip via `resolve_ref_commit`
    4. Echo one stdout line Fetching origin/<branch>... then
       `fetch_branch` of the own branch; the twin projection after the
       fetch — an absent twin reads as None
    5. Classify the pair via `resolve_publication_outcome`
    6. pushed -> `push_branch` of the own branch — the twin is created
    7. up-to-date and remote-ahead -> success with nothing to do and
       nothing mutated
    8. Read the publication facts of the commit the remote branch
       carries at its tip after the operation — the twin tip — via
       `resolve_ref_commit` and `resolve_commit_message`
    9. Emit topic_published over `TopicHooks` with the identity via
       `TopicIdentity` — the slug, the resolved year, the branch as
       entered — the remote branch origin/<branch>, the commit facts,
       and the outcome kind; every success emits, the idempotent
       outcomes included
    10. Return the single result line naming the outcome kind

    Requirements:
    - Delivery, never history rewriting — no force and no lease under
      any outcome
    - No confirmation is asked; the working-tree state is irrelevant
      to the push
    - The result is exactly one line and names the outcome kind

    Constraints:
    - Do not move, create, or delete any local ref — the branch itself
      stays untouched
    - Do not push anything but the topic's own branch

"resolve_publication_outcome(own_tip: str, twin_tip: str | None) -> outcome: str":
  location: publishing.py
  annotations: |
    Classify the own-twin pair into the publication outcome — the pure
    decision of the publication operation.

    `own_tip`: the tip commit of the topic's own branch
    `twin_tip`: the tip commit of the origin twin as it exists after
                the fetch; None when the twin is absent
    `outcome`: the outcome kind — pushed, up-to-date, or remote-ahead

    Apply the `exchanging` practice for the containment pattern.
    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. `twin_tip` None -> pushed — the push creates the twin
    2. `twin_tip` equals `own_tip` -> up-to-date — the twin already
       carries the tip, nothing to do
    3. `own_tip` contained in `twin_tip` via `is_ancestor` ->
       remote-ahead — the remote strictly carries the local work
    4. Otherwise a clean error naming both tips; reconciliation is
       manual git, then a re-run

    Requirements:
    - Read-only — containment probes via `is_ancestor` only; no
      mutation and no network
    - The equality probe precedes the containment probes

    Constraints:
    - Do not reconcile — divergence is surfaced by the caller
```

**REPLACE** in `publish_topic`, step 9, the `topic_published` tail with:

```
then topic_published — the remote branch origin/<branch_name>, the
commit hash and message of the built commit, and the outcome pushed
```

**ADD** to `update_topic`, step 9 (after the successful publish push):

```
after a successful publish push, emit topic_published over
`TopicHooks` with the identity, the remote branch origin/<addressee
branch>, the commit facts of the refreshed tip the twin carries —
`resolve_ref_commit` and `resolve_commit_message` — and the outcome
pushed
```

**ADD** to `update_topic` `Requirements`:

```
- An already-current outcome publishes nothing and emits no
  publication — the publication event fires exactly when a push
  completed
```

**ADD** to `execute_propagation`, after the successful inherent push
(step 6 paths and the retry-cycle success, before the propagate
notification of step 9):

```
after a successful inherent push, emit topic_published over
`TopicHooks` with the identity, the remote branch origin/<base>, the
commit facts of the delivery commit the base twin carries, and the
outcome pushed — before the propagate notification
```

**ADD** to `execute_propagation` `Requirements`:

```
- A nothing-to-do delivery pushes nothing and emits no publication
```

**MODIFY** `goga/topics/.usages/publishing.md` — **REPLACE** the title and the
intro paragraph with:

```md
# topics — publishing work

How to publish topic work without leaving the current branch through the
`goga.topics` facade — fresh work via `publish_topic`, an existing branch
via `publish_existing_topic`. For consumers that register new or finished
work on the remote board while the user keeps working: the topics command
group, higher-level orchestration.
```

**ADD** section:

```md
## Publishing an existing branch

`publish_existing_topic` delivers a topic's own branch to origin as an
operation of its own — creating fresh work is not part of it.

    from goga.topics import publish_existing_topic

    result = publish_existing_topic("feat-x")
    print(result)  # one line: the outcome kind

| origin twin vs own tip | Outcome |
|---|---|
| twin absent | pushed — the push creates the twin |
| twin == tip | up-to-date — success, nothing to do |
| twin strictly ahead | remote-ahead — success, nothing to push |
| diverged | clean error naming both tips; reconcile via git, re-run |

- One targeted fetch of the topic's own twin, reported by one stdout
  line before it runs; no confirmation; a dirty tree is irrelevant.
- Delivery only — no force, no lease, ever; the local branch and the
  working copy stay untouched.
- Every completed publication — the idempotent outcomes included —
  emits `topic_published` with `remote_branch=origin/<branch>`, the
  commit facts of the twin tip, and the outcome kind.
- `origin` unconfigured is a clean error before any network operation.
```

**MODIFY** `goga/topics/.usages/update.md` — **ADD** bullet to the list:

```md
- `publish=True` emits `topic_published` after the push — remote
  branch `origin/<branch>`, commit facts of the refreshed tip, outcome
  pushed; an already-current update publishes nothing and emits no
  publication.
```

**MODIFY** `goga/topics/.usages/propagate.md` — **ADD** bullet to the list:

```md
- The inherent push emits `topic_published` after it lands — remote
  branch `origin/<base>`, commit facts of the delivery commit, outcome
  pushed; a nothing-to-do delivery pushes nothing and emits no
  publication.
```

**MODIFY** `goga/topics/.usages/registering-hooks.md` — **REPLACE** the
`topic_published` row of the events table with:

```md
| `topics / topic_published` | After every completed publication — the creation push of `publish_topic`, the `publish` command (its idempotent outcomes included), the explicit update publish push, and the inherent push of a propagate. |
```

**REPLACE** the `topic_published` documentation of "The notification
contexts" with:

```md
- `topic_published` — `TopicPublished`: `identity`, `remote_branch`
  (`origin/<name>` — the branch that received the delivery),
  `commit_hash` / `commit_message` (git facts of the commit the remote
  branch carries at its tip after the operation), `outcome` (pushed /
  up-to-date / remote-ahead). The idempotent up-to-date and
  remote-ahead kinds emit like any other; a publication that pushed
  nothing — an already-current update, a nothing-to-do delivery —
  emits nothing.
```

**ADD** the migration note:

```md
### Migration note — reshaped `topic_published` context

The context is publication-centric. `todo` is gone: it was creation
context. `remote_branch` (`origin/<name>` — the branch that received
the delivery), `commit_hash` / `commit_message` (git facts of the
commit the remote branch carries at its tip after the operation), and
`outcome` (`pushed` / `up-to-date` / `remote-ahead`) replace it. A
subscriber reading `todo` must switch to `topic_created`, which still
carries it. The action address and the soft error class are unchanged.
```

### 7. `goga/schema/hooks/CODEMANIFEST` — MODIFY

**ADD** to the global `Annotations` (after the zone description paragraph):

```
The validation gate is the domain's hard observe-and-veto action with
the walk-to-completion deviation: the per-tool walk runs every
subscribed tool's validation hooks to completion — no early stop
between tools — and collects one violation per tool; a vetoing or a
crashed hook contributes exactly one violation of its tool. The
delivered view is the final assembled tree — the committed tools
overlay included, a recorded exception to the authored-facts-only
delivery rule; a validator observes and vetoes, and the tree is never
modified by a validator.
```

**ADD** to Body (after `CellFacts`/`DependencyFacts`, before `CellAmendment`):

```yaml
"SchemaNode(path: str, description: str, types: list[str], usages: list[str], dependencies: list[DependencyFacts], children: list[SchemaNode], tools: dict[str, dict[str, object]])":
  location: facts.py
  annotations: |
    One node of the final assembled tree — the read-only delivered
    view of the validation gate.

    `path`: the normalized cell path
    `description`: the footer description of the cell manifest
    `types`: the entity and routine names of the cell body
    `usages`: the usages file names of the cell
    `dependencies`: the cell's imports grouped per source path
    `children`: the children of the node, in tree order
    `tools`: the committed tools overlay of the node — empty when no
             tool contributed

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the constructing operation passes the assembled
      values; nothing is read here
    - The node carries the final result, the tools overlay included
  properties:
    "path -> str": |
      The normalized cell path.
    "description -> str": |
      The footer description of the cell manifest.
    "types -> list[str]": |
      The entity and routine names of the cell body.
    "usages -> list[str]": |
      The usages file names of the cell.
    "dependencies -> list[DependencyFacts]": |
      The cell's imports grouped per source path.
    "children -> list[SchemaNode]": |
      The children of the node, in tree order.
    "tools -> dict[str, dict[str, object]]": |
      The committed tools overlay of the node; empty when no tool
      contributed.
```

**ADD** to Body (facts.py, beside the fact types):

```yaml
"Violation(tool: str, hook: str, reason: str)":
  location: facts.py
  annotations: |
    One collected veto of the validation walk.

    `tool`: the tool identity assigned by the platform
    `hook`: the hook name that vetoed or crashed
    `reason`: the veto reason — a hook-authored message or the crash
              reason; never a raw traceback

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "tool -> str": |
      The tool identity of the vetoing tool.
    "hook -> str": |
      The hook name that vetoed or crashed.
    "reason -> str": |
      The veto reason — authored or crash-derived; never a raw
      traceback.

"GateVerdict(violations: list[Violation])":
  location: facts.py
  annotations: |
    The collected verdict of the validation walk — every veto of every
    subscribed tool, in enumeration order.

    `violations`: the collected violations; an empty list means
                  approved

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The verdict is data only — acting on it (the merged error, the
      exit code) belongs to the operation
  properties:
    "violations -> list[Violation]": |
      The collected violations in enumeration order.
    "approved -> bool": |
      True when no violation was collected — the generation may
      proceed.
```

**ADD** to Body (contexts.py, after `CellAmendment`):

```yaml
"SchemaValidation(tree: list[SchemaNode])":
  location: contexts.py
  annotations: |
    The gate's delivered view of one tool — the read-only final tree
    plus the veto buffer of this tool alone.

    `tree`: the final assembled tree in tree order — the tools
            overlay included

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads deliver the final tree — read-only; a hook observes
      and cannot alter anything
    - The veto buffer belongs to this tool alone
  properties:
    "tree -> list[SchemaNode]": |
      The final assembled tree, in tree order; read-only for the
      receiving hook.
  methods:
    "veto(reason: str)": |
      Buffer this tool's veto of the final tree.

      `reason`: the human-readable violation reason

      Requirements:
      - The call buffers into the buffer of this tool alone and
        changes nothing until the walk collects it
      - The replacement is whole — a later call replaces the earlier
        reason
      - The view records no hook identity — the walk attributes the
        veto to a hook by observing the buffer change around each call
      - An empty or whitespace-only reason is stored as given — the
        merged error renders it verbatim

      Constraints:
      - Do not cancel, redirect, or defer the operation — a veto stops
        the generation through the collected verdict only
```

**ADD** method to `SchemaHooks` (after `amend_cell`):

```yaml
    "validate_schema(tree: list[SchemaNode]) -> verdict: GateVerdict": |
      Deliver the validation gate over the final assembled tree and
      return the collected verdict.

      `tree`: the final assembled tree in tree order
      `verdict`: the collected verdict — approved when no tool vetoed

      Use the `per-tool-delivery` practice for the staged walk — with
      the recorded refinement: the walk runs to completion and
      collects vetoes; no early stop, no contribution commit.

      Algorithm:
      1. Resolve the address domain="schema", action="validate_schema"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `SchemaValidation` view over the
         delivered tree, wrap it via `wrap_context`, project the call
         arguments via `build_hook_arguments` with the tool's own
         context, and call each hook of the tool; snapshot the view's
         veto buffer before each hook call — a buffer change during a
         call attributes the veto to that hook's subscription name
      3. A tool whose every hook returned without raising and whose
         view carries no buffered veto approves silently — no record
      4. A tool whose view carries a buffered veto contributes exactly
         one `Violation` — the tool, the attributed vetoing hook, the
         reason
      5. A tool with a raising hook contributes exactly one
         `Violation` with the crash reason as the reason — never a raw
         traceback — and the walk continues; a crash overrides the
         tool's buffered veto; the walk never stops between tools
      6. Return the `GateVerdict` with the violations in enumeration
         order

      Requirements:
      - Every subscribed tool's hooks run — no early stop; a
        non-vetoing subscriber is invoked even when another tool
        already vetoed
      - Exactly one `Violation` per tool
      - An address without subscriptions returns an approved verdict;
        with no tool packages installed the gate is inert
      - The gate modifies nothing — no mutation of the delivered tree

      Constraints:
      - Do not stop the walk at the first veto or crash — verdict
        collection requires every tool's outcome
      - Do not skip a subscriber of the address
      - Do not read repositories or the filesystem at the checkpoint
      - Do not print — the caller owns all output
```

**MODIFY** `goga/schema/hooks/.usages/checkpoints.md` — **ADD** section:

```md
## Validate the final tree

Build the read-only `SchemaNode` projection of the fully assembled
tree — every surviving node with its committed tools overlay — and
deliver the gate before serialization.

    from goga.schema.hooks import SchemaHooks, SchemaNode

    hooks = SchemaHooks()
    nodes = [to_schema_node(n) for n in final_tree]  # recursive: children + tools
    verdict = hooks.validate_schema(nodes)
    if not verdict.approved:
        raise merge_veto_error(verdict.violations)

- The walk runs to completion: every subscribed tool's hooks run, one
  violation per vetoing or crashing tool (tool, hook, reason).
- The delivered tree is the final result, tools overlay included; a
  validator observes and vetoes — never modifies.
- No subscriptions (or no tool packages installed) → approved; the
  output stays byte-identical.
```

### 8. `goga/schema/CODEMANIFEST` — MODIFY

**ADD** `SchemaNode` and `GateVerdict` to the `Types` list of the
`From: goga/schema/hooks` import entry.

**ADD** to the global `Annotations` (after the `checkpoints` sentence):

```
The caller uses the `checkpoints` practice to deliver the validation
gate of the generation walk over the final assembled tree, before
serialization.
```

**REPLACE** `schema` algorithm step 6 with two steps (renumbered):

```
6. Build the read-only `SchemaNode` projection of the final tree —
   every surviving node with its committed tools overlay — and
   deliver the validation gate over `SchemaHooks`; a not-approved
   `GateVerdict` raises one merged error listing every violation (the
   tool, the hook, the reason) — no JSON is returned
7. Return the JSON string using the `beautiful_json` practice
```

**ADD** to `schema` `Requirements`:

```
- The validation gate fires exactly once over the final assembled
  tree — after the filters and the tools overlay, before
  serialization; an approved verdict leaves the output byte-identical
- The delivered view carries the final result, the tools overlay
  included — the recorded exception to the authored-facts-only rule
- The gate is observe-and-veto — the tree is never modified by a
  validator
```

**MODIFY** `goga/schema/.usages/registering-hooks.md` — **REPLACE** the opening
sentence of the intro ("The domain opens one action — the cell amendment.")
with:

```md
The domain opens two hard actions — the cell amendment, a
read-and-contribute view delivered during the walk, and the validation
gate, an observe-and-veto pass over the final assembled tree.
```

**ADD** the events-table row and the section:

```md
| `schema / validate_schema` | hard | Once over the final assembled tree of every entry path that builds the project map (`goga schema` and the schema routine) — after the tools overlay and the filters, before serialization. The walk runs to completion; one violation per vetoing or crashing tool. |
```

```md
## The validation view

`validate_schema` delivers a `SchemaValidation` view per tool: the
read-only final tree (`context.tree` — recursive `SchemaNode` with
`path`, `description`, `types`, `usages`, `dependencies`, `children`,
`tools`, the overlay included) and `veto(reason)`.

    def validate_tree(context):
        for node in context.tree:
            if broken(node):
                context.veto(f"{node.path}: broken shape")
                return

- Veto or crash = exactly one violation of your tool (tool, hook,
  reason); every subscribed tool runs — no early stop.
- On any violation: nothing on stdout, one merged error on stderr,
  exit 1. Observe and veto only — the tree is never modified.
- With no subscriptions the output is byte-for-byte unchanged.
```

### 9. `goga/commands/tool/CODEMANIFEST` — MODIFY

**ADD** to `Imports`:

```yaml
  - Types:
      - load_tool_config
    Usages:
      - tool-configuration
    From: goga/config
```

**REPLACE** `tool` algorithm step 4 with:

```
4. Compute the optional injections via `build_injections` with the
   resolved tool name
```

**REPLACE** the `build_injections` declaration with:

```yaml
"build_injections(main: Callable, tool: str) -> injections: dict[str, object]":
  location: tool.py
  annotations: |
    Project the tool entry point's signature against the optional
    injections the dispatcher can supply, building each requested
    value lazily.

    `main`: the tool package entry callable.
    `tool`: the dispatched tool name — the directory owner of the
            tool config files.
    `injections`: the keyword arguments to forward to the entry point.

    Algorithm:
    1. Examine the signature of `main` to enumerate its
       keyword-capable parameters
    2. Start from an empty set of injections
    3. For each declared parameter whose name matches an injection the
       dispatcher offers (currently the parameters named ast, of type
       `AST`, and config, of raw parsed type), build the value lazily
       and collect it:
       - for ast -> construct the project AST at the current project
         root and load it, following `loading`
       - for config -> load the tool config file config.yml of
         `tool` via `load_tool_config`, following
         `tool-configuration` — the raw data as-is, or None when the
         file is absent
    4. Return the collected injections

    Requirements:
    - Only keyword-capable parameters (positional-or-keyword and
      keyword-only) are considered; positional-only parameters and
      parameters whose name is not offered are skipped
    - The ast injection is built only when `main` declares it
    - The config injection is built only when `main` declares it; an
      absent config file yields None

    Constraints:
    - Do not block or transform on non-empty `AST` errors; validation
      errors pass through to the tool unchanged
    - Structural manifest failures (an unparseable manifest) propagate
      to the caller; only the validation errors exposed by the `AST`
      pass through as data
    - The offered-injection set is the single source of opt-in: a
      parameter with another name never triggers a build
```

**MODIFY** `goga/commands/tool/.usages/tool.md` — **REPLACE** the Purpose
sentence ("The entry point may optionally receive the project AST.") with:

```md
The entry point may optionally receive the project AST and the tool's
raw config.
```

**ADD** the injection table row and the example:

```md
| `config` | raw parsed YAML — a mapping, list, string, or any parsed value | The tool's `.goga/tools/<name>/config.yml`, loaded raw — or `None` when absent | Yes — only when `main` declares `config` |
```

```md
Declaring `config` receives the tool's own configuration:

    def main(argv: list[str], *, config: dict | None = None) -> None:
        if config is None:
            return  # no config file — the normal state
        threshold = config.get("threshold", 0)
```

**ADD** opt-in bullet:

```md
- A parameter named `config` (and only `config`) loads
  `.goga/tools/<name>/config.yml` — raw as-is, `None` when absent; no
  other name triggers a load.
```

### 10. `goga/commands/topics/CODEMANIFEST` — MODIFY

**ADD** `publish_existing_topic` to the `Types` list of the `From: goga/topics`
import entry (beside `update_topic`).

**ADD** to the `topics` group "Subcommand surfaces" list:

```
    - publish — an optional IDENTIFIER positional
```

**ADD** method to the `topics` group (after `update`, before `propagate`):

```yaml
    "publish(identifier: str | None = None) -> exit_code: int": |
      Subcommand goga topics publish: deliver an existing topic branch
      to origin — the current topic when IDENTIFIER is omitted, the
      identified one otherwise.

      `identifier`: IDENTIFIER positional — a branch name, a topic
                    slug, or their prefix; omitted addresses the
                    current topic
      `exit_code`: 0 on success (the up-to-date and remote-ahead
                   outcomes included), 1 on error

      Apply the `publishing` practice for the publication contract of
      the domain.
      Apply the `click` practice for the positional, echo, and
      exit-code propagation.

      Algorithm:
      1. Delegate to `publish_existing_topic` with the identifier and
         the scoped year
      2. Echo the single result line
      3. Propagate the exit code

      Constraints:
      - Do not read the configuration — the publication resolves no
        configuration keys
      - Do not ask a confirmation — the push is the requested action
```

**MODIFY** `goga/commands/topics/.usages/topics-command.md` — **REPLACE** the
audience enumeration of the intro ("boarding, creating, updating,
propagating, switching, deleting, and clearing") with:

```md
boarding, creating, publishing an existing branch, updating,
propagating, switching, deleting, and clearing
```

**ADD** section:

```md
## publish

`goga topics publish [IDENTIFIER]` delivers an existing topic branch
to origin. Omitted IDENTIFIER addresses the current topic.

    goga topics publish          # publish the current topic
    goga topics publish feat-x   # publish the identified topic

- Exit 0 on pushed, up-to-date, and remote-ahead alike; divergence is
  a clean error naming both tips (reconcile via git, re-run).
- No flags: no confirmation, no force; the command reads no
  configuration keys.
- The result is exactly one stdout line naming the outcome kind.
```

### 11. `goga/commands/schema/CODEMANIFEST` — MODIFY

**REPLACE** the `schema` command algorithm step 2 error enumeration with:

```
2. On any error from `schema_logic` — AST parse errors, a hard failure
   of the cell-amendment checkpoint (a crashed hook or a structurally
   malformed contribution; the error names the tool, the action, and
   the failing cell path), a vetoed validation gate of the final tree
   (the merged error lists every violation — the tool, the hook, the
   reason), or a register-facade import failure (the error names the
   package) — write the error message to stderr and exit 1; nothing is
   printed to stdout and no raw traceback is shown
```

**MODIFY** `goga/commands/schema/.usages/schema.md` — **ADD** section:

```md
## Validation failures

A vetoing or crashing tool hook fails the command: nothing is printed
to stdout, one merged error lists every violation (tool, hook,
reason) on stderr, exit code 1. With no subscriptions the output is
byte-for-byte the plain schema.
```

## Dependency Map

```
goga/hooks ──┬──> goga/hooks/catalog ──(declared_actions)──> [all zones]
             ├──> goga/topics/hooks ──(TopicIdentity, TopicHooks,
             │        reshaped TopicPublished / emit_published)──> goga/topics
             └──> goga/schema/hooks ──(SchemaHooks, CellFacts,
                      DependencyFacts, SchemaNode, GateVerdict)──> goga/schema

goga/topics/git ──(28 routines + resolve_commit_message)──> goga/topics

goga/config/tool ──(load_tool_config)──> goga/config ──┬─> goga/commands/tool   [NEW edge]
                                                        └─> (re-exports to consumers)

goga/topics ──> goga/commands/topics
goga/schema ──> goga/commands/schema
goga/ast ──> goga/commands/tool ; goga/schema
```

New edge: exactly one — `goga/commands/tool → goga/config` (acyclic; the config
subtree imports no command layer). No new cell except `goga/config/tool`; no
cross-zone edges between hook zones.

## Verification Checklist

After each artifact lands:

- **DSL validity** — `goga lint` is clean over the whole tree (every new or
  edited CODEMANIFEST parses; keys keep exact casing; `location` values stay
  flat module files beside their CODEMANIFEST).
- **catalog** — `declared_actions` gains exactly one record
  (`schema/validate_schema`, hard); domain-then-name ordering keeps the two
  schema actions adjacent; the `topics/topic_published` record is untouched.
- **topics/git** — `resolve_commit_message` exported through the zone's facade;
  read-only; unresolvable commit surfaces as a clean error; no printing.
- **config/tool** — package `goga/config/tool` with `loader.py` and `__init__.py`
  exposing `load_tool_config` via `__all__`; facade check
  `python -c "from goga.config import load_tool_config"`; absent file → None;
  present file returns the verbatim parse (mapping, string, and list cases);
  empty/separator/`..` filenames raise the clean error; `root` override honored;
  repeated calls re-read (no cache).
- **topics/hooks** — `TopicPublished` carries exactly the five publication
  fields; `emit_published` signature matches; the emitted address and the soft
  error class are unchanged.
- **topics** — `publish_existing_topic` and `resolve_publication_outcome`
  exported via the facade `__all__`; the four-outcome matrix pinned by
  parametrized tests (absent/equal/ahead/diverged); the fetch is reported by one
  stdout line before it runs; no code path constructs a force or lease push
  (repo sweep for force/lease inside publish paths); every publishing site emits
  — publish command including its idempotent outcomes, `publish_topic`,
  `update_topic` after its push, `execute_propagation` after its inherent push —
  and the no-push outcomes (`already-current`, `nothing-to-do`) emit no
  publication; the success output is exactly one line naming the outcome kind.
- **schema/hooks** — `SchemaNode`, `Violation`, `GateVerdict`, `SchemaValidation`
  exported via the zone facade; walk-to-completion pinned (a non-vetoing
  subscriber is invoked after another tool already vetoed); exactly one
  `Violation` per tool; a crash overrides the buffered veto; an empty address
  returns an approved verdict; attribute assignment on the delivered view is
  blocked.
- **schema** — the gate fires exactly once after the overlay merge and the
  filters, before serialization; with no subscriptions (and no tool packages
  installed) the output is byte-for-byte the six-field map; a not-approved
  verdict raises one merged error naming every violation's tool, hook, and
  reason; no partial JSON.
- **commands/tool** — `config` is injected as a keyword argument only when the
  entry point declares it; the load is lazy (no file read for non-declaring
  entry points); absent config yields None; `ast` behavior unchanged; tests
  call the handler directly.
- **commands/topics** — `publish_existing_topic` imported through the
  `goga/topics` import entry; the `publish` subcommand mirrors its siblings'
  option surface (an optional IDENTIFIER only); direct-handler tests cover all
  four outcomes and the clean-error paths; exit 0 on all three success kinds.
- **commands/schema** — a vetoing run prints nothing to stdout, one merged
  stderr error, exit 1; approved runs are byte-identical.
- **Usage files** — the matched pairs stay consistent (facade registration guide
  + zone checkpoint guide for `topics` and `schema`); the migration note is in
  `goga/topics/.usages/registering-hooks.md`; every connected practice is
  referenced by at least one annotation.
- **Project gates** — `pytest tests/ -x` green; `ruff check` clean on every
  touched package; repo sweep confirms no residual old `topic_published` wording
  (`todo`-carrying publication context) in contracts, usages, or tests.
