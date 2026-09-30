# Topics — Hooks

The topics domain exposes **nine hook actions** for tool packages — the lifecycle checkpoints of the topic flows. Seven are **notifications**: read-only facts of a completed moment, delivered after the moment fully succeeds. Two are **amendments**: per-hook views over the content a flow is about to fix, delivered before the fixation. All nine are soft — a failing hook is skipped with a warning and the command continues.

## The actions

| Address | Error class | Fires |
|---|---|---|
| `topics / amend_creation` | soft | Before the first mutation of the chosen creation path — every decision of `goga topics create` made (the publication ask included), and the fast creation of `goga pipeline <name> -t <new-branch>` (identity-only, advisory — see below). |
| `topics / amend_todo_entry` | soft | After a todo entry saves in the editor and before `todo.md` is written — the `--todo` entries of `goga topics switch` and `goga pipeline <name> -t <identifier> --todo`. |
| `topics / topic_created` | soft | After a creation completes — the quarantined plant, the checked-out path, the publication, and the pipeline fast creation. |
| `topics / topic_published` | soft | After every completed publication — the creation push (`--publish`, or the ask answered yes), the standalone `goga topics publish` (the idempotent outcomes included), the update publish push, and the push inherent to every propagate. |
| `topics / topic_switched` | soft | After every completed switch — the idempotent already-on-branch outcome included. |
| `topics / topic_todo_entered` | soft | After `todo.md` is written with the final text. |
| `topics / topic_deleted` | soft | After each target's full removal — local branch, origin twin, and directory (`goga topics delete` and `goga topics clear`). |
| `topics / topic_updated` | soft | After every completed update (`goga topics update`) — the idempotent `already-current` outcome included. |
| `topics / topic_propagated` | soft | After every completed delivery (`goga topics propagate`) — the idempotent `nothing-to-do` outcome included. |

A tool subscribes inside its `register_hooks` callback:

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("topics", "topic_created", "record", record_created)
    hooks.subscribe("topics", "amend_creation", "stamper", stamp_message)


def record_created(context):
    if context.checked_out:
        note(f"topic planted at {context.identity.home_path}")
    if context.commit_hash is not None:
        note(f"creation commit {context.commit_hash}")


def stamp_message(context):
    context.amend(commit_message=f"[{context.identity.slug}] {context.commit_message}", todo=context.todo)
```

A failing moment fires nothing: a creation that fails its preflight, a publication whose push rolls back, a switch refused before its first mutation — the checkpoints of the moment never arrive.

## The contexts

Every context carries one `TopicIdentity` — the record at the page bottom.

### `amend_creation` — `CreationAmendment` (soft)

One fresh view per hook over the live shared draft.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the topic the creation fixes |
| `checked_out` | `bool` | the chosen path checks out the fresh branch |
| `published` | `bool` | the chosen path publishes the work |
| `commit_message` / `todo` | `str | None` (live read-through) | the current draft — a later hook sees the committed amendments of the earlier hooks |

| Method | Effect |
|---|---|
| `amend(commit_message, todo)` | buffers a whole replacement; `None` keeps a field structurally absent — a field left out comes back as `None`, not kept as the previous value; a present-but-blank field rejects the whole buffer — a warning, the walk continues. |

The walk delivers the subscriptions in enumeration order; a hook's buffer commits only when the hook returns without raising, and two hooks of one tool never share a buffer or a failure. The last committed buffer wins. A raised hook, its discarded buffer, and a rejected buffer each warn on stderr naming the hook, the tool, the action, and the reason — the walk continues and the operation never breaks. An amendment transforms content; it cannot cancel, redirect, or defer the operation. The identity-only form — a creation path that builds no commit and resolved no todo — still delivers `amend_creation` with both fields `None`; the tool decides whether to act.

> **Advisory on the pipeline fast creation.** On the fast creation of `goga pipeline <name> -t <new-branch>`, the creation amendment **observes only**: an amended todo does not land there — the todo resolves later through the entry's own `amend_todo_entry`, which owns the written text — and `commit_message` stays `None` (the path builds no commit).

### `amend_todo_entry` — `TodoEntryAmendment` (soft)

One fresh view per hook.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the topic whose todo entry saves |
| `text` | `str` (live read-through) | the current entry text — a later hook sees the committed amendments of the earlier hooks |

| Method | Effect |
|---|---|
| `amend(text)` | buffers the replacement; `None` or whitespace-only is rejected with a warning. |

The same amendment contract as the creation view — whole replacement, per-hook commit in enumeration order, the last committed buffer wins; a raised hook or a rejected buffer warns on stderr and the walk continues; content only.

### `topic_created` — `TopicCreated` (soft)

One shared read-only instance for every subscribed tool — no per-tool copies, no stale facts.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the created topic |
| `checked_out` | `bool` | the path checked out the fresh branch |
| `published` | `bool` | the path published the work |
| `todo` | `str | None` | the final text, `None` when none resolved |
| `commit_message` | `str | None` | present exactly when the path builds a commit — the quarantined plant and the publication; `None` on the checked-out and fast-creation paths |
| `commit_hash` | `str | None` | the hash of the built commit — present under the same condition |

Read-only facts; no methods.

### `topic_published` — `TopicPublished` (soft)

One shared read-only instance for every subscribed tool — no per-tool copies, no stale facts.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the published topic |
| `remote_branch` | `str` | the origin branch that received the delivery, in the `origin/<name>` form — the topic's own twin, or the base branch of a propagate |
| `commit_hash` | `str` | the hash of the commit the remote branch carries at its tip after the operation |
| `commit_message` | `str` | the message of that commit |
| `outcome` | `str` | exactly one of `pushed` / `up-to-date` / `remote-ahead` |

Read-only facts; no methods.

> **Migration note (reshaped context).** `todo` is gone from `topic_published` — a subscriber reading it must switch to `topic_created`, which still carries it; `remote_branch`, `commit_hash`/`commit_message` (of the commit the remote branch carries at its tip after the operation), and `outcome` replace it. The emission also broadened: every completed publication emits, the idempotent `up-to-date` and `remote-ahead` kinds included, and a publication that pushed nothing — an already-current update, a nothing-to-do delivery — emits nothing.

### `topic_switched` — `TopicSwitched` (soft)

One shared read-only instance for every subscribed tool — no per-tool copies, no stale facts.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the switched work — the branch-only form when the switched branch hosts no topic |
| `outcome` | `str` | exactly one of `local-checkout` / `created-from-remote` / `already-on-branch` |

Read-only facts; no methods.

### `topic_todo_entered` — `TopicTodoEntered` (soft)

One shared read-only instance for every subscribed tool — no per-tool copies, no stale facts.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the topic whose todo was entered |
| `text` | `str` | the final written text, after every amendment — no prior text is carried; a tool keeps its own state in its own `self` context |

Read-only facts; no methods.

### `topic_deleted` — `TopicDeleted` (soft)

One shared read-only instance for every subscribed tool — no per-tool copies, no stale facts.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the removed topic — no branch fact |
| `local_branch` | `str | None` | the removed local branch name, `None` when the target had none |
| `origin_twin` | `str | None` | the removed origin twin name, `None` when the target had none |
| `directory_removed` | `bool` | the topic directory was removed — no deleted-commit hash travels |

Read-only facts; no methods.

### `topic_updated` — `TopicUpdated` (soft)

One shared read-only instance for every subscribed tool — no per-tool copies, no stale facts.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the updated topic |
| `base` | `str` | the base name as addressed by the operation |
| `effective_tip` | `str` | the effective base tip the topic was brought to |
| `strategy` | `str` | the configured name — `merge` / `rebase` / `ff-else-merge` / `ff-else-rebase` |
| `outcome` | `str` | exactly one of `merged` / `rebased` / `fast-forwarded` / `already-current` |
| `published` | `bool` | the update published the refreshed branch |

Read-only facts; no methods.

### `topic_propagated` — `TopicPropagated` (soft)

One shared read-only instance for every subscribed tool — no per-tool copies, no stale facts.

| Read | Type | Meaning |
|---|---|---|
| `identity` | `TopicIdentity` | the propagated topic |
| `base` | `str` | the target base name as addressed by the operation |
| `strategy` | `str` | `merge` / `ff` / `squash` |
| `outcome` | `str` | exactly one of `merged` / `fast-forwarded` / `squashed` / `nothing-to-do` |

Read-only facts; no methods. No pushed flag — the push is inherent to every propagate.

## The fact records

Every context and every view carries one `TopicIdentity` — pure composition from the identity inputs; a checkpoint never reads the repository.

| Record | Fields |
|---|---|
| `TopicIdentity` | `slug` (`str | None` — `None` in the branch-only form: a switch onto a branch hosting no topic), `year` (`str`), `branch` (`str | None` — `None` only in the deletion context, whose branch names travel in the removal composition instead), `home_path` (`str | None` property — `.goga/history/<year>/<slug>`, `None` when the slug is `None`) |

The platform mechanism behind the action (enumeration, the registry, delivery, inspection with `goga hooks`) is the [Hooks](../hooks/index.md) domain; the registration contract for tool authors is covered in [Hooks — The registration contract](../hooks/hooks.md); the flows that fire the checkpoints are covered in [CLI](cli.md). The topics flows additionally read the effective configuration through the config amendment checkpoint delivered at their configuration load (see [Configuration — Hooks](../../configuration/hooks.md)).
