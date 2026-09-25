# [ARCHITECTURE_PLAN]

## Topic

**topics-hooks** — seven platform hook actions for the topics lifecycle: five post-fact notifications over the plain emission, two pre-fixation amendments over the staged per-tool delivery, home-path identity, no-read contexts.

Plan path: `.goga/history/2026/add-topics-hooks/arch.md` (this file).

## Implementation Order

1. **`goga/hooks/catalog`** (MODIFIED) — first: the record data every later emission resolves against; the cell has no Imports and nothing in this plan depends on order here, but the addresses must exist before any checkpoint fires.
2. **`goga/topics/hooks`** (CREATED) — second: the topics hooks zone; depends on `goga/hooks` (facade types + practices) and `goga/history` (path composition) — both already exist and are untouched by this plan.
3. **`goga/topics`** (MODIFIED) — last: the flows that call the zone; depends on `goga/topics/hooks` (Types + the `checkpoints` practice) — designed after its dependency exists.

## Artifacts

### Cell 1: `goga/hooks/catalog` — MODIFIED CODEMANIFEST (diff)

Only the `Requirements` of `declared_actions` changes: keep the first three bullets (deterministic, complete, statuses record) and the two onboarding bullets verbatim, then append seven bullets. Final current-state list:

```yaml
    Requirements:
    - Deterministic — the same records in the same order on every call
    - Complete — no filtering and no partial views
    - The catalog carries the statuses action — the record
      domain="statuses", name="register_statuses", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the onboarding session-declaration action — the
      record domain="onboarding", name="declare_session", error_class="soft":
      a failing hook of the action is skipped with a warning and the sequence
      continues
    - The catalog carries the onboarding config-amendment action — the
      record domain="onboarding", name="amend_config", error_class="soft": a
      failing hook of the action is skipped with a warning and the sequence
      continues
    - The catalog carries the topics creation-notification action — the
      record domain="topics", name="topic_created", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics publication-notification action — the
      record domain="topics", name="topic_published", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics switch-notification action — the
      record domain="topics", name="topic_switched", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics todo-entry-notification action — the
      record domain="topics", name="topic_todo_entered", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics deletion-notification action — the
      record domain="topics", name="topic_deleted", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics creation-amendment action — the record
      domain="topics", name="amend_creation", error_class="soft": a failing
      hook of the action is skipped with a warning and the command continues
    - The catalog carries the topics todo-entry-amendment action — the
      record domain="topics", name="amend_todo_entry", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
```

Algorithm, Constraints, `Action`, header, and footer: unchanged.

### Cell 2: `goga/topics/hooks` — CREATED

#### CODEMANIFEST (full file)

````yaml
Imports:
  - Types:
      - HookRegistry
      - emit_hook_event
      - wrap_context
      - build_hook_arguments
      - declared_actions
    Usages:
      - declaring-actions
      - per-tool-delivery
      - registering-hooks
    From: goga/hooks
  - Types:
      - resolve_topic_dir
    Usages:
      - topic-paths
    From: goga/history

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and
    testing in the project

  Use the `declaring-actions` practice for the emission contract of
  the notification checkpoints.
  Use the `per-tool-delivery` practice for the staged delivery loop of
  the amendment checkpoints — its loop skeleton, primitives, and
  failure handling apply with one refinement: the commit granularity
  is the single hook, not the tool — the per-hook requirements of the
  delivery methods take precedence over the practice's tool-grouped
  commit.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind every checkpoint.
  Use the `topic-paths` practice for the topic directory composition
  behind the home path of the identity.

  This cell owns the hooks zone of the topics domain: the identity
  vocabulary of the lifecycle events, the read-only notification
  contexts of the five moments, the amendment drafts of the two
  pre-fixation moments with their per-hook staged delivery, and the
  checkpoint surface that delivers the amendments and emits the
  notifications over the platform facade. One registry per run carries
  every checkpoint of a command — the checkpoints never multiply the
  package enumeration. Every context is built from the operation data
  the caller passes — no repository reads happen here. A failing hook
  never breaks the operation: the seven topics actions are soft, a
  failure is a warning naming the hook, the tool, the action, and the
  reason, and the delivery continues in the platform order. No package
  enumeration and no subscription state live here — the platform
  carries the tool packages. Use relative imports.

---

"TopicIdentity(slug: str | None, year: str, branch: str | None)":
  location: identity.py
  annotations: |
    The identity vocabulary of every topics event — the topic slug,
    its home path, and the branch as entered by the operation.

    `slug`: the normalized topic slug; None in the branch-only form —
            a switch onto a branch hosting no topic
    `year`: the resolved year as four digits — the composition input
             of the home path; it always arrives resolved — the
             constructing operation passes its year input when given,
             otherwise the current year
    `branch`: the branch name as entered by the operation; None only
              in the deletion context, whose removal composition
              carries the branch names

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `topic-paths` practice for the topic directory composition
    behind the home path — the composition runs through
    `resolve_topic_dir`.

    Requirements:
    - Pure composition — the home path derives from `slug` and `year`
      without repository reads and without creating anything
  properties:
    "slug -> str | None": |
      The normalized topic slug, or None in the branch-only form.
    "home_path -> str | None": |
      The topic home path .goga/history/<year>/<slug> as a posix
      string, composed from the slug and the year inputs; None when
      the slug is None. Pure composition — nothing is read or
      created.
    "branch -> str | None": |
      The branch name as entered by the operation, or None in the
      deletion context.

"TopicCreated(identity: TopicIdentity, checked_out: bool, published: bool, todo: str | None, commit_message: str | None, commit_hash: str | None)":
  location: contexts.py
  annotations: |
    The read-only context of the creation notification — the final
    facts of one completed creation.

    `identity`: the identity of the created topic
    `checked_out`: True when the creation path checked out the fresh
                   branch
    `published`: True when the creation path published the work
    `todo`: the final todo text, or None when none resolved
    `commit_message`: the final commit message — present exactly when
                      the creation path builds a commit, None otherwise
    `commit_hash`: the hash of the built commit — present exactly when
                   the creation path builds a commit, None otherwise

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a completed operation — a hook observes the
      outcome and cannot alter it
  properties:
    "identity -> TopicIdentity": |
      The identity of the created topic.
    "checked_out -> bool": |
      True when the creation path checked out the fresh branch.
    "published -> bool": |
      True when the creation path published the work.
    "todo -> str | None": |
      The final todo text, or None when none resolved.
    "commit_message -> str | None": |
      The final commit message — present exactly when the creation
      path builds a commit, None otherwise.
    "commit_hash -> str | None": |
      The hash of the built commit — present exactly when the creation
      path builds a commit, None otherwise.

"TopicPublished(identity: TopicIdentity, commit_message: str, commit_hash: str, todo: str)":
  location: contexts.py
  annotations: |
    The read-only context of the publication notification — the final
    facts of one successful publication push.

    `identity`: the identity of the published topic
    `commit_message`: the final commit message landed in git
    `commit_hash`: the hash of the publication commit
    `todo`: the final todo text landed in the publication commit

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of a completed operation
  properties:
    "identity -> TopicIdentity": |
      The identity of the published topic.
    "commit_message -> str": |
      The final commit message landed in git.
    "commit_hash -> str": |
      The hash of the publication commit.
    "todo -> str": |
      The final todo text landed in the publication commit.

"TopicSwitched(identity: TopicIdentity, outcome: str)":
  location: contexts.py
  annotations: |
    The read-only context of the switch notification — the outcome of
    one completed switch.

    `identity`: the identity of the switched work — the branch-only
                form when the branch hosts no topic
    `outcome`: the outcome kind — exactly one of local-checkout,
               created-from-remote, already-on-branch

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The outcome value is exactly one of the three fixed kinds
    - Read-only facts of a completed operation
  properties:
    "identity -> TopicIdentity": |
      The identity of the switched work — the branch-only form when
      the branch hosts no topic.
    "outcome -> str": |
      The outcome kind — local-checkout, created-from-remote, or
      already-on-branch.

"TopicTodoEntered(identity: TopicIdentity, text: str)":
  location: contexts.py
  annotations: |
    The read-only context of the todo-entry notification — the final
    text of one saved todo entry.

    `identity`: the identity of the topic whose todo was entered
    `text`: the final written text — after every amendment

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - No prior text is carried — a tool keeps its own state in its own
      context
    - Read-only facts of a completed operation
  properties:
    "identity -> TopicIdentity": |
      The identity of the topic whose todo was entered.
    "text -> str": |
      The final written text — after every amendment.

"TopicDeleted(identity: TopicIdentity, local_branch: str | None, origin_twin: str | None, directory_removed: bool)":
  location: contexts.py
  annotations: |
    The read-only context of the deletion notification — the removal
    composition of one fully removed target.

    `identity`: the identity of the removed topic — slug and home
                path; no branch fact
    `local_branch`: the removed local branch name, or None when the
                    target had none
    `origin_twin`: the removed origin twin name, or None when the
                   target had none
    `directory_removed`: True when the topic directory was removed

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - No deleted-commit hash is carried
    - Read-only facts of a completed operation
  properties:
    "identity -> TopicIdentity": |
      The identity of the removed topic — slug and home path; no
      branch fact.
    "local_branch -> str | None": |
      The removed local branch name, or None.
    "origin_twin -> str | None": |
      The removed origin twin name, or None.
    "directory_removed -> bool": |
      True when the topic directory was removed.

"CreationDraft(commit_message: str | None, todo: str | None)":
  location: amendments.py
  annotations: |
    The shared draft holder of the creation amendment — the content
    the creation path is about to fix, and after the delivery the
    final amended content.

    `commit_message`: the draft commit message — None on paths that
                      build no commit
    `todo`: the draft todo text — None when none resolved

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The content changes only through the delivery commit of the
      amendment checkpoint — never through a delivered view
  properties:
    "commit_message -> str | None": |
      The draft or final commit message — None on paths that build no
      commit.
    "todo -> str | None": |
      The draft or final todo text — None when none resolved.

"TodoEntryDraft(text: str)":
  location: amendments.py
  annotations: |
    The shared draft holder of the todo-entry amendment — the saved
    text the entry path is about to write, and after the delivery the
    final amended text.

    `text`: the saved draft text

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The content changes only through the delivery commit of the
      amendment checkpoint — never through a delivered view
  properties:
    "text -> str": |
      The saved draft or final amended text.

"CreationAmendment(identity: TopicIdentity, checked_out: bool, published: bool, draft: CreationDraft)":
  location: amendments.py
  annotations: |
    The creation-amendment view of one hook — the read-only surface
    over the live shared draft, delivered at the pre-fixation moment
    of a creation.

    `identity`: the identity of the topic being created
    `checked_out`: True when the chosen path checks out the fresh
                   branch
    `published`: True when the chosen path publishes the work
    `draft`: the live shared holder the view reads through

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads pass through to the live holder — a later hook sees
      the committed amendments of the earlier hooks
    - The identity-only form — no commit message and no todo on the
      chosen path — is valid; the tool decides whether to act
  properties:
    "identity -> TopicIdentity": |
      The identity of the topic being created.
    "checked_out -> bool": |
      True when the chosen path checks out the fresh branch.
    "published -> bool": |
      True when the chosen path publishes the work.
    "commit_message -> str | None": |
      The live draft commit message — None on paths that build no
      commit.
    "todo -> str | None": |
      The live draft todo text — None when none resolved.
  methods:
    "amend(commit_message: str | None, todo: str | None)": |
      Buffer one amendment replacing the full draft content.

      `commit_message`: the complete new commit message — None keeps
                        the field structurally absent
      `todo`: the complete new todo text — None keeps the field
              structurally absent

      Requirements:
      - The call buffers into the buffer of this hook alone and
        changes nothing until the delivery commits it
      - The replacement is whole — a field left out is returned as
        None, not kept as the previous value

      Constraints:
      - Do not cancel, redirect, or defer the operation — an
        amendment transforms content only

"TodoEntryAmendment(identity: TopicIdentity, draft: TodoEntryDraft)":
  location: amendments.py
  annotations: |
    The todo-entry-amendment view of one hook — the read-only surface
    over the live shared draft, delivered at the pre-fixation moment
    of a todo entry.

    `identity`: the identity of the topic whose todo is being entered
    `draft`: the live shared holder the view reads through

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.
  properties:
    "identity -> TopicIdentity": |
      The identity of the topic whose todo is being entered.
    "text -> str": |
      The live draft text.
  methods:
    "amend(text: str)": |
      Buffer one amendment replacing the full text.

      `text`: the complete new text

      Requirements:
      - The call buffers into the buffer of this hook alone and
        changes nothing until the delivery commits it

      Constraints:
      - Do not cancel, redirect, or defer the operation — an
        amendment transforms content only

"TopicHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the topics lifecycle — the two amendment
    deliveries and the five notification emissions over the platform
    facade.

    Apply the `convention` practice for the code style and
    intra-package imports.
    Use the `declaring-actions` practice for the emission contract of
    the notification checkpoints.
    Use the `per-tool-delivery` practice for the staged delivery loop
    of the amendment checkpoints.
    Use the `registering-hooks` practice for the registration contract
    behind every checkpoint.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a
      command — the assembly runs once per run whatever the number of
      checkpoints; the transport of the shared `HookRegistry` is an
      implementation detail
    - Every context and draft is built from the values the caller
      passes — no repository reads happen at a checkpoint
  methods:
    "amend_creation(identity: TopicIdentity, checked_out: bool, published: bool, commit_message: str | None, todo: str | None) -> draft: CreationDraft": |
      Deliver the creation-amendment checkpoint and return the holder
      with the final content.

      `identity`: the identity of the topic being created
      `checked_out`: True when the chosen path checks out the fresh
                     branch
      `published`: True when the chosen path publishes the work
      `commit_message`: the draft commit message — None on paths that
                        build no commit
      `todo`: the draft todo text — None when none resolved
      `draft`: the holder carrying the final amended values

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="topics", action="amend_creation"
         against `declared_actions`
      2. Create the shared `CreationDraft` with the draft values
      3. Walk the subscriptions of the address in enumeration order:
         per subscription build the hook's `CreationAmendment` view
         over the live holder, wrap it via `wrap_context`, project the
         call arguments via `build_hook_arguments` with the tool's own
         context, and call the hook
      4. A hook that returns without raising and buffered an
         amendment: the buffer replaces the holder content — except
         when a structurally present field of the buffer is empty or
         whitespace-only, which rejects the whole buffer
      5. A hook that raised: its buffer is discarded
      6. Both rejection cases emit the warning
         hook <name> of tool <tool> failed on
         topics.amend_creation: <reason> — the raised error for the
         discard, the empty-amendment reason for the rejection — and
         the walk continues with the next hook
      7. Return the holder

      Requirements:
      - The delivery is per hook — two hooks of one tool never share
        a buffer or a failure
      - The final holder content is the last committed buffer, or the
        original draft values when no buffer committed
      - An address without subscriptions returns the original draft
        values — not an error

      Constraints:
      - Do not apply any amendment after the walk ends — the caller
        fixes the final draft into the artifacts itself
      - Do not skip a subscriber of the address
    "amend_todo_entry(identity: TopicIdentity, text: str) -> draft: TodoEntryDraft": |
      Deliver the todo-entry-amendment checkpoint and return the
      holder with the final text.

      `identity`: the identity of the topic whose todo is being
                  entered
      `text`: the saved draft text
      `draft`: the holder carrying the final amended text

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="topics",
         action="amend_todo_entry" against `declared_actions`
      2. Create the shared `TodoEntryDraft` with the draft text
      3. Walk the subscriptions in enumeration order with a per-hook
         `TodoEntryAmendment` view over the live holder — the same
         call, commit, and rejection rules as the creation amendment
      4. Return the holder

      Requirements:
      - The delivery is per hook — two hooks of one tool never share
        a buffer or a failure
      - The final holder text is the last committed buffer, or the
        saved draft when no buffer committed
      - An address without subscriptions returns the saved draft —
        not an error

      Constraints:
      - Do not apply any amendment after the walk ends — the caller
        writes the final text itself
      - Do not skip a subscriber of the address
    "emit_created(identity: TopicIdentity, checked_out: bool, published: bool, todo: str | None, commit_message: str | None, commit_hash: str | None)": |
      Emit the creation notification — the facts of one completed
      creation.

      `identity`: the identity of the created topic
      `checked_out`: True when the creation path checked out the fresh
                     branch
      `published`: True when the creation path published the work
      `todo`: the final todo text, or None
      `commit_message`: the final commit message — None on paths
                        building none
      `commit_hash`: the hash of the built commit — None on paths
                     building none

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicCreated` context from the values
      2. Emit the address domain="topics", action="topic_created" via
         `emit_hook_event` — the context view of every receiving tool
         reads the same instance through the delivery proxy

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - A failing hook is skipped with a warning under the soft error
        class of the action
    "emit_published(identity: TopicIdentity, commit_message: str, commit_hash: str, todo: str)": |
      Emit the publication notification — the facts of one successful
      publication push.

      `identity`: the identity of the published topic
      `commit_message`: the final commit message landed in git
      `commit_hash`: the hash of the publication commit
      `todo`: the final todo text landed in the publication commit

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicPublished` context from the values
      2. Emit the address domain="topics", action="topic_published"
         via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
    "emit_switched(identity: TopicIdentity, outcome: str)": |
      Emit the switch notification — the outcome of one completed
      switch.

      `identity`: the identity of the switched work — the branch-only
                  form when the branch hosts no topic
      `outcome`: the outcome kind — local-checkout,
                 created-from-remote, or already-on-branch

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicSwitched` context from the values
      2. Emit the address domain="topics", action="topic_switched"
         via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
    "emit_todo_entered(identity: TopicIdentity, text: str)": |
      Emit the todo-entry notification — the final text of one saved
      todo entry.

      `identity`: the identity of the topic whose todo was entered
      `text`: the final written text

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicTodoEntered` context from the values
      2. Emit the address domain="topics",
         action="topic_todo_entered" via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
    "emit_deleted(identity: TopicIdentity, local_branch: str | None, origin_twin: str | None, directory_removed: bool)": |
      Emit the deletion notification — the removal composition of one
      fully removed target.

      `identity`: the identity of the removed topic — slug and home
                  path; no branch fact
      `local_branch`: the removed local branch name, or None
      `origin_twin`: the removed origin twin name, or None
      `directory_removed`: True when the topic directory was removed

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `TopicDeleted` context from the values
      2. Emit the address domain="topics", action="topic_deleted"
         via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns

---

Author: Goga
CreatedAt: 16/09/26
Description: |
  Owner of the topics domain hooks zone — the event identity, the
  notification contexts, the amendment drafts, and the checkpoint
  surface over the hooks platform.
````

#### `.usages/` file

**File:** `goga/topics/hooks/.usages/checkpoints.md`

````markdown
# topics — emitting lifecycle checkpoints

How the topics flows consume the checkpoint surface of the hooks zone:
delivering the two amendments before the content is fixed and emitting
the five notifications after their moments. For the domain flows over
the topics facade.

## The checkpoint surface

One `TopicHooks` object serves every checkpoint of a command — the
surface shares one registry per run, so a command that reaches several
checkpoints enumerates the tool packages once.

```python
from goga.topics.hooks import TopicHooks, TopicIdentity

hooks = TopicHooks()
identity = TopicIdentity(slug="add-topics-hooks", year="2026", branch="add-topics-hooks")
```

`TopicIdentity` carries the three identity facts of every event: the
slug, the home path (composed from slug and year — no repository
reads), and the branch as entered. The branch-only form — slug None —
serves a manual switch onto a branch hosting no topic.

## Amend before the content is fixed

Deliver the amendment checkpoint before the mutation that fixes the
content, then read the final values from the returned holder and fix
them.

```python
draft = hooks.amend_creation(
    identity,
    checked_out=False,
    published=False,
    commit_message=draft_message,   # None on paths that build no commit
    todo=draft_todo,                # None when none resolved
)
final_message = draft.commit_message
final_todo = draft.todo
```

- The identity-only form is valid — a path with no commit and no todo
  still delivers; the tool decides whether to act.
- A hook's buffered amendment commits only when the hook returns
  without raising; an empty or whitespace-only value rejects the whole
  buffer; both cases warn and the walk continues — the operation never
  breaks.
- The caller fixes the final values into the artifacts itself; nothing
  is applied to the repository here.

```python
draft = hooks.amend_todo_entry(identity, saved_text)
write_todo(draft.text)
hooks.emit_todo_entered(identity, draft.text)
```

## Emit after the moment

Emit each notification after its moment fully succeeds, with the final
facts — the amended content is the reported content.

```python
hooks.emit_created(identity, checked_out=False, published=False,
                   todo=final_todo, commit_message=final_message,
                   commit_hash=planted_hash)
hooks.emit_published(identity, commit_message=final_message,
                     commit_hash=planted_hash, todo=final_todo)
hooks.emit_switched(identity, outcome="created-from-remote")
hooks.emit_deleted(identity, local_branch=branch, origin_twin=twin,
                   directory_removed=True)
```

- Every `emit_*` is fire-and-forget: a failing hook warns under the
  soft error class and the command continues.
- Build every fact from the operation's own data — no git reads at a
  checkpoint.
````

### Cell 3: `goga/topics` — MODIFIED CODEMANIFEST (diff)

**Header — add one Imports block** (after the `goga/topics/editor` block):

```yaml
  - Types:
      - TopicIdentity
      - TopicHooks
      - CreationDraft
      - TodoEntryDraft
    Usages:
      - checkpoints
    From: goga/topics/hooks
```

**Global Annotations — two insertions** (after the `deleting` practice paragraph):

```
Use the `checkpoints` practice for the lifecycle checkpoint patterns
of the topics hooks zone — the identity construction, the amendment
delivery before the content is fixed, and the notification emission
after the moment.
```

(inside the zone-description paragraph, after the deletion sentence:)

```
The domain opens its lifecycle to tool packages through its hooks
zone: the creation, publication, switch, todo-entry, and deletion
checkpoints fire inside the domain routines — a failing hook of the
soft actions warns and never breaks the operation, and every event
fact comes from the operation's own data.
```

**Body — replace the annotations of the six routines below** (everything not shown stays verbatim; `checkpoints` practice lines added to each):

### `enter_topic_todo` — final signature + annotation

```yaml
"enter_topic_todo(topic: str, year: str | None = None, branch: str | None = None) -> written: bool":
  location: creation.py
  annotations: |
    Enter the todo of a topic — the editor session with the topic's
    todo.md and the write of the saved text, without a commit; the
    saved text passes through the todo-entry amendment before the
    write, and the completed entry emits its notification.

    `topic`: topic input — a branch name or an already-normalized slug
    `year`: optional year as four digits; None means the current year
    `branch`: the branch fact of the identity, passed by the calling
              operation; None leaves the identity without a branch
              fact
    `written`: True when the saved text was written; False when the
               entry was cancelled

    Apply the `editor-entry` practice for the editor session pattern.
    Apply the `topic-paths` practice for the todo-file path pattern.
    Apply the `checkpoints` practice for the amendment delivery and
    the notification emission.

    Algorithm:
    1. Resolve the todo.md path of the topic via `resolve_topic_file`;
       an existing file provides the initial text
    2. Open the editor session via `edit_text` with the initial text
    3. A cancelled entry -> False — the file stays untouched, nothing
       is delivered or emitted
    4. A saved text -> deliver the todo-entry amendment over
       `TopicHooks`: the identity via `TopicIdentity` — the normalized
       slug, the resolved year, `branch` — and amend_todo_entry with
       the saved text; the final text of the returned `TodoEntryDraft`
       replaces the text being written
    5. Write todo.md with the final text as entered with exactly one
       trailing newline — a text already ending in one keeps it —
       encoded UTF-8, without a commit -> True
    6. Emit topic_todo_entered — the identity and the final written
       text

    Requirements:
    - The topic directory exists — directory creation belongs to the
      caller
    - The write is the last mutation — nothing mutates after it; the
      notification emission follows the write and mutates nothing
    - The amendment delivers after the save and before the write; the
      write carries the final amended text
    - An entry completing with a saved write emits
      topic_todo_entered; a cancelled entry delivers and emits nothing
    - The identity needs no repository reads — the slug, the year, and
      the branch arrive as inputs

    Constraints:
    - Do not create the topic directory
    - Do not commit the write
```

### `create_topic` — final Algorithm + new Requirements (annotation head, practice lines, and Constraints otherwise verbatim; practice lines gain the `checkpoints` line)

```yaml
    Apply the `click` practice for the publication ask and the
    non-interactive detection.
    Apply the `editor-entry` practice for the editor session.
    Apply the `topic-paths` practice for the slug, existence, directory
    creation, and todo-file path patterns.
    Apply the `refs-and-switching` practice for the checkout pattern.
    Apply the `checkpoints` practice for the creation amendment and
    the creation notification.

    Algorithm:
    1. Preflight, read-only and before any input: [verbatim]
    2. Resolve the todo: [verbatim]
    3. `publish` without a resolved todo -> clean error asking for the
       todo, before any mutation
    4. Neither `publish` nor `switch` without a resolved todo -> clean
       error [verbatim tail]
    5. The publication ask — [verbatim]
    6. Deliver the creation amendment over `TopicHooks`: build the
       identity via `TopicIdentity` — the normalized slug, the
       resolved year, `branch_name` as entered — and deliver
       amend_creation with the path facts — checked_out as `switch`
       dictates, published as the chosen path dictates — the draft
       commit message of the path (the no-switch and the publication
       paths build one; the switch path delivers None) and the draft
       todo when resolved; the amended values of the returned
       `CreationDraft` replace the todo and the commit message carried
       into the mutation steps
    7. The normal path without `switch`: build one quarantined commit
       carrying the todo file todo.md — the path resolved via
       `resolve_topic_file` — with the final todo content and the
       final commit message on the base commit via
       `commit_file_on_base`, capture the returned commit hash, and
       plant the branch named as entered at it; the working copy, the
       index, and HEAD stay untouched — the caller stays on their
       branch; then emit topic_created over `TopicHooks` — the
       identity, checked_out False, published False, the final todo,
       the final commit message, and the captured commit hash
    8. The normal path under `switch`: create the branch at the base
       commit via `create_branch_at_commit` and switch to it via
       `checkout_local_branch` — a failed checkout rolls the planted
       branch back via `delete_local_branch` (the occupancy oracle
       would otherwise block the retry) —, create the topic directory
       of the year via `ensure_topic_dir`, and write the todo file
       todo.md when a todo resolved; the write is the last mutation of
       the path; then emit topic_created — the identity, checked_out
       True, published False, the final todo when written, and no
       commit facts
    9. The publication path: delegate to `publish_topic` with the
       name, the amended todo, the base, the amended template, and the
       year — the publication path fires its checkpoints inside the
       delegated routine; nothing fires here
    10. Return the single result line

    Requirements:
    - [existing bullets verbatim]
    - The creation amendment delivers exactly once per creation,
      immediately before the first mutation of the chosen path, with
      the draft content of that path; the identity-only form is valid
    - topic_created fires exactly once per successful creation — from
      this routine on the no-switch and switch paths, from the
      delegated publication routine after its push succeeds; a failed
      creation fires nothing
```

### `publish_topic` — final Algorithm + new Requirement (head, practice lines + `checkpoints`, Requirements, Constraints otherwise verbatim)

```yaml
    Algorithm:
    1. Normalize `branch_name` into a slug via `normalize_topic_slug`
    2. [verbatim]
    3. [verbatim]
    4. [verbatim]
    5. [verbatim]
    6. Build the publication commit via `commit_file_on_base` — the
       parent commit, the todo.md path resolved via
       `resolve_topic_file` as a repository-root-relative posix
       string, the final todo content, and the applied commit
       message — and capture the returned commit hash
    7. Plant the branch named exactly as entered via
       `create_branch_at_commit`
    8. Publish via `push_branch`; a failed publication deletes the
       branch via `delete_local_branch` and surfaces one clean error
       carrying the reason — nothing fires on the failure
    9. After the successful push, emit over `TopicHooks` with the
       identity via `TopicIdentity` — the normalized slug, the
       resolved year, `branch_name` as entered: topic_created —
       checked_out False, published True, the final todo, the applied
       commit message, the captured commit hash — then
       topic_published — the same final commit message, commit hash,
       and todo
    10. Return the single result line

    Requirements:
    - [existing bullets verbatim]
    - The creation amendment belongs to the creating orchestration —
      this routine fires the publication checkpoints only; a direct
      call publishes without amend_creation
    - The two publication checkpoints fire only after the push
      succeeds, in the order topic_created then topic_published; a
      failed publication that rolls back fires nothing
```

### `switch_topic` — final Algorithm + new Requirements (head/practice lines + `checkpoints`, otherwise verbatim)

```yaml
    Algorithm:
    1. [verbatim]
    2. [verbatim]
    3. `todo` and the chosen candidate hosts no topic -> clean error —
       switching creates nothing; nothing fires
    4. [verbatim idempotent]
    5. [verbatim mutation]
    6. Emit topic_switched over `TopicHooks` — the identity via
       `TopicIdentity`: the hosted slug of the chosen candidate when
       it hosts one, the resolved year, the branch as entered; the
       branch-only identity when it hosts none — and the outcome kind:
       already-on-branch, local-checkout, or created-from-remote
    7. With `todo` -> enter the todo of the topic via
       `enter_topic_todo`, passing the switched branch as the branch
       fact
    8. Return the single result line

    Requirements:
    - [existing bullets verbatim]
    - topic_switched fires on every completed switch, every outcome
      included; the identity degrades to branch-only when the chosen
      candidate hosts no topic
    - `todo` onto a branch hosting no topic keeps the clean
      pre-mutation error and fires nothing
    - The identity facts are the operation's own data — the hosted
      slug of the chosen candidate, the resolved year, and the branch
      name
```

### `ensure_topic` — final Algorithm + new Requirements (head/practice lines + `checkpoints`, otherwise verbatim)

```yaml
    Algorithm:
    1. [verbatim]
    2. [verbatim]
    3. No candidate -> the fast creation: normalize `identifier` into
       a slug via `normalize_topic_slug`; an empty slug or an
       occupancy conflict [verbatim tail]; deliver the creation
       amendment over `TopicHooks` with the identity via
       `TopicIdentity` — the normalized slug, the resolved year, the
       branch name as entered — checked_out True, published False, no
       draft commit message (the path builds no commit), and no draft
       todo (the todo resolves later through the entry); create the
       branch named as entered from the current HEAD and switch to it
       via `create_and_switch_branch`; create the topic directory of
       the year via `ensure_topic_dir`; with `todo` enter the todo of
       the fresh topic via `enter_topic_todo`, passing the branch
       name as the branch fact — the entry starts only after the
       switch; after the creation completes, emit topic_created over
       `TopicHooks` — the identity, checked_out True, published False,
       the final todo when the entry resolved one, and no commit
       facts
    4. Otherwise -> the switch procedure via `switch_topic` without
       the entry — the switch notification fires inside it; with
       `todo`, take the hosted topic of the switched work [verbatim
       resolution] — and: a hosted topic exists -> enter its todo via
       `enter_topic_todo` with the branch fact; the hosting branch
       hosts no topic -> an empty slug of its name is a clean error,
       otherwise create the topic directory of the year via
       `ensure_topic_dir`, then enter the todo of the fresh topic via
       `enter_topic_todo` with the derived identity — the slug
       normalized from the branch name, the resolved year — as the
       topic input and the branch fact; no creation checkpoint fires
       for the directory creation
    5. Return the single result line

    Requirements:
    - [existing bullets verbatim, except `With `todo`, no step follows
      the todo write`, reworded as below]
    - With `todo`, no mutation follows the todo write — the creation
      notification alone may follow it
    - The fast creation delivers the creation amendment exactly once,
      immediately before its first mutation, and emits topic_created
      after the creation completes — the identity-only amendment form
      is the norm on this path
    - Directory creation under the todo flag of a topic-less branch
      fires no creation checkpoint — the todo entry alone fires its
      two
    - The todo entries pass the operation's branch fact into the
      entry
```

### `delete_topics` — final Algorithm + new Requirements (head/practice lines + `checkpoints`, otherwise verbatim)

```yaml
    Algorithm:
    1. Per target, in order: a local branch exists -> capture its
       commit via `resolve_ref_commit` first, then delete the local
       branch via `delete_local_branch`
    2. An origin twin exists -> delete it on origin via
       `delete_remote_branch`; a failed deletion restores the local
       branch at the captured commit via `create_branch_at_commit`
       and surfaces one clean error — the targets removed before the
       failure stay removed and fired theirs
    3. A target with only an origin twin -> delete it on origin via
       `delete_remote_branch`
    4. A target with a directory -> remove the topic directory via
       `remove_topic_dir`
    5. After the target's full removal, emit topic_deleted over
       `TopicHooks` — the identity via `TopicIdentity`: the target's
       slug and the resolved year, no branch fact — with the removal
       composition: the removed local branch name or None, the
       removed origin twin name or None, and whether the topic
       directory was removed
    6. Return the single result line

    Requirements:
    - [existing bullets verbatim]
    - A target fires after its complete removal; targets fully
      removed before a later failure fire theirs; a target whose
      removal fails midway fires nothing
    - No deleted-commit hash is carried — the captured rollback
      commit stays internal
```

**Footer — append one clause** to the Description:

```
; the lifecycle events of the domain fire through its hooks zone
```

**`.usages/` files of `goga/topics`:** `todo-entry.md` and
`creating.md` gain one clause each — the written todo.md content (and
the built commit message) is the final amended text when a tool
package subscribes an amendment hook; the remaining files are
unchanged.

## Dependency Map

```
goga/hooks/catalog ─┐
goga/hooks/dispatch+registry+tools ─┤ (unchanged platform)
                                     ▼
                               goga/hooks ──(5 Types + 3 Usages)──▶ goga/topics/hooks ◀──(resolve_topic_dir + topic-paths)── goga/history
                                                                     ▲
                                     (TopicIdentity, TopicHooks,    │
                                      CreationDraft, TodoEntryDraft,│
                                      checkpoints)                  │
                                                                     ▼
                                 goga/commands/topics+pipeline+hooks ◀── goga/topics (MODIFIED)
```

No cycles. Order: catalog → topics/hooks → topics.

## Verification Checklist

After implementing each artifact:

- [ ] `goga lint` passes over all touched CODEMANIFESTs (DSL syntax, references, casing)
- [ ] Cell 2 facade imports: `python -c "from goga.topics.hooks import TopicHooks, TopicIdentity, CreationDraft, TodoEntryDraft, TopicCreated, TopicPublished, TopicSwitched, TopicTodoEntered, TopicDeleted, CreationAmendment, TodoEntryAmendment"`
- [ ] `goga hooks` lists the seven topics actions (tool → domain → action) with no command change
- [ ] `goga schema goga/topics` shows the new subcell with its 11 types and the parent's new dependency
- [ ] Each notification fires exactly at its moment: created once per path (no-switch, switch, publication-after-push, ensure fast); rolled-back publication emits nothing; deleted per fully removed target; `switch --todo` onto a topic-less branch emits nothing
- [ ] Marginal corners: `ensure --todo` on a topic-less branch fires `amend_todo_entry` + `topic_todo_entered` with derived identity and no `topic_created`; manual switch onto a topic-less branch emits branch-only `topic_switched`
- [ ] Amendment semantics: raising hook → buffer discarded; empty/whitespace buffer → rejected at commit; hooks of one tool independent; warning form `hook <name> of tool <tool> failed on topics.<action>: <reason>`; enumeration continues
- [ ] Final amended drafts land in the artifacts and are reported as the final facts of the corresponding notifications
- [ ] No new git reads for events (identity facts from operation data only; the plant hash from the existing return value)
- [ ] `goga pipeline <name> -t` receives the same events (emission in the domain routines; commands untouched)
- [ ] Docs synchronized: `docs/features/topics/hooks.md` reference replaces the stub; action lists in `docs/features/hooks/index.md`, `docs/features/hooks/hooks.md`, `docs/features/tools/hooks.md` include the topics domain
- [ ] Tests per conventions: `tests/topics/hooks/` covers identity, contexts, amendments, events; flow tests extended; `tests/hooks/catalog/test_catalog.py` asserts the seven records; CLI tested by direct handler calls; mocks only at git/editor boundaries
- [ ] `pytest tests/ -x` passes; `ruff check` over the touched sources passes
- [ ] Existing behavior unchanged: result lines, error surface, mutation order of every flow
