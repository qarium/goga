# topics — registering hooks

How a `goga_tool_*` package subscribes its hooks to the lifecycle
events of the topics domain. For tool package authors; no goga code
changes are needed.

The domain opens seven soft actions. Five are notifications — the
read-only facts of a completed moment, delivered after the moment fully
succeeds. Two are amendments — a per-hook view over the content a flow
is about to fix, delivered before the fixation. Every failing hook is
skipped with a log warning naming the hook, the tool, the action, and
the reason; the command continues — no topics hook can break a command.

## The events

| Address | Fires |
|---|---|
| `topics / amend_creation` | Before the first mutation of the chosen creation path — every path decision of `create_topic` made, the publication ask included — and the fast creation of `ensure_topic` (identity-only, advisory — see below). |
| `topics / amend_todo_entry` | After a todo entry saves in the editor and before `todo.md` is written — the optional todo entry of a switch. |
| `topics / topic_created` | After a creation completes — the quarantined plant, the checked-out path, the publication, and the fast creation of `ensure_topic`. |
| `topics / topic_published` | After a successful publication push, paired with the `topic_created` of the same cycle. |
| `topics / topic_switched` | After every completed switch — the idempotent already-on-branch outcome included. |
| `topics / topic_todo_entered` | After `todo.md` is written with the final text. |
| `topics / topic_deleted` | After each target's full removal — local branch, origin twin, and directory. |

A failing moment fires nothing: a creation that fails its preflight, a
publication whose push rolls back, a switch refused before its first
mutation — the events of the moment never arrive.

## Subscribe

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("topics", "topic_created", "record", record_created)
    hooks.subscribe("topics", "amend_creation", "stamper", stamp_message)
```

- `domain` — always `"topics"`.
- `action` — the event name from the table above.
- `name` — the hook name, unique per tool per address.
- `hook` — the callable executed when the event fires.

A hook receives values only for the parameters it declares by the fixed
offered names: `context` — the delivered object of the event, read
attributes and call methods freely, attribute assignment is blocked;
`self` — the isolated context of your tool, one instance links all its
hook invocations of a run, freely mutable. The declaration order does
not matter; names you did not declare receive nothing.

```python
def record_created(context):
    ...  # read-only facts of the completed creation


def stamp_message(context):
    context.amend(commit_message=f"[{context.identity.slug}] {context.commit_message}", todo=context.todo)
```

## The identity

Every context carries one `TopicIdentity`: `slug` — the normalized
topic slug, or None in the branch-only form (a switch onto a branch
hosting no topic); `home_path` — `.goga/history/<year>/<slug>` as a
posix string, None when the slug is None; `branch` — the branch name as
entered by the operation, None only in the deletion context.

## The notification contexts

Each notification delivers the same context instance to every
subscribed tool — no per-tool copies, no stale facts. A hook observes
the outcome and cannot alter it.

- `topic_created` — `TopicCreated`: `identity`, `checked_out` (the path
  checked out the fresh branch), `published` (the path published the
  work), `todo` (the final text, or None when none resolved),
  `commit_message` and `commit_hash` (present exactly when the path
  builds a commit — the quarantined plant and the publication; None on
  the checked-out and fast-creation paths).
- `topic_published` — `TopicPublished`: `identity`, `commit_message`,
  `commit_hash`, `todo` — the facts of one successful push, identical
  to the paired `topic_created`.
- `topic_switched` — `TopicSwitched`: `identity`, `outcome` — exactly
  one of `local-checkout`, `created-from-remote`, `already-on-branch`.
  The identity degrades to the branch-only form when the switched
  branch hosts no topic.
- `topic_todo_entered` — `TopicTodoEntered`: `identity`, `text` — the
  final written text, after every amendment. No prior text is carried;
  keep your own state in your own `self` context.
- `topic_deleted` — `TopicDeleted`: `identity` (no branch fact),
  `local_branch` and `origin_twin` (each None when the target had
  none), `directory_removed`. No deleted-commit hash is carried.

## The amendment views

Each amendment delivers a fresh view per hook over the live shared
draft. The read-through attributes — `commit_message` / `todo` on
`CreationAmendment`, `text` on `TodoEntryAmendment` — read the live
holder, so a later hook sees the committed amendments of the earlier
hooks.

- `amend_creation` — `CreationAmendment`: `identity`, `checked_out`,
  `published`, the reads `commit_message` / `todo`, and
  `amend(commit_message, todo)`.
- `amend_todo_entry` — `TodoEntryAmendment`: `identity`, the read
  `text`, and `amend(text)`.

The amendment contract:

- Whole replacement — `amend` buffers the complete new content; a field
  left out comes back as None, it is not kept as the previous value.
  The last committed buffer wins.
- Per-hook commit — the walk delivers the subscriptions in enumeration
  order; a hook's buffer commits only when the hook returns without
  raising, and two hooks of one tool never share a buffer or a failure.
- Empty rejection — a structurally present field that is empty or
  whitespace-only rejects the whole buffer (on the todo entry, a None
  text is rejected too); a raised hook and a rejected buffer each warn
  in the log and the walk continues.
- Content only — an amendment transforms content; it cannot cancel,
  redirect, or defer the operation.
- Identity-only form — a creation path that builds no commit and
  resolved no todo still delivers `amend_creation` with both fields
  None; the tool decides whether to act.
- Advisory on the fast creation of `ensure_topic`: there the creation amendment
  observes only — an amended todo does not land (the todo resolves
  later through `amend_todo_entry`, which owns the written text), and
  `commit_message` stays None.
