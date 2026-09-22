# Topics — Hooks

The topics domain exposes **seven hook actions** for tool packages — the lifecycle checkpoints of the topic flows. Five are **notifications**: read-only facts of a completed moment, delivered after the moment fully succeeds. Two are **amendments**: per-hook views over the content a flow is about to fix, delivered before the fixation. All seven are soft — a failing hook is skipped with a warning and the command continues.

## The actions

| Address | Error class | Fires |
|---|---|---|
| `topics / amend_creation` | soft | Before the first mutation of the chosen creation path — every decision of `goga topics create` made (the publication ask included), and the fast creation of `goga pipeline <name> -t <new-branch>` (identity-only, advisory — see below). |
| `topics / amend_todo_entry` | soft | After a todo entry saves in the editor and before `todo.md` is written — the `--todo` entries of `goga topics switch` and `goga pipeline <name> -t <identifier> --todo`. |
| `topics / topic_created` | soft | After a creation completes — the quarantined plant, the checked-out path, the publication, and the pipeline fast creation. |
| `topics / topic_published` | soft | After a successful publication push (`--publish`, or the ask answered yes). |
| `topics / topic_switched` | soft | After every completed switch — the idempotent already-on-branch outcome included. |
| `topics / topic_todo_entered` | soft | After `todo.md` is written with the final text. |
| `topics / topic_deleted` | soft | After each target's full removal — local branch, origin twin, and directory (`goga topics delete`). |

A tool subscribes inside its `register_hooks` callback:

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("topics", "topic_created", "record", record_created)
    hooks.subscribe("topics", "amend_creation", "stamper", stamp_message)


def record_created(context):
    ...  # read-only facts of the completed creation


def stamp_message(context):
    context.amend(commit_message=f"[{context.identity.slug}] {context.commit_message}", todo=context.todo)
```

A failing moment fires nothing: a creation that fails its preflight, a publication whose push rolls back, a switch refused before its first mutation — the checkpoints of the moment never arrive.

## The identity

Every context carries one `TopicIdentity`:

- `slug` — the normalized topic slug, or None in the **branch-only form**: a switch onto a branch hosting no topic.
- `home_path` — `.goga/history/<year>/<slug>` as a posix string (None when the slug is None). Composed from the identity inputs — a checkpoint never reads the repository.
- `branch` — the branch name as entered by the operation; None only in the deletion context, whose branch names travel in the removal composition instead.

## The notification contexts

Each notification delivers **the same context instance** to every subscribed tool — no per-tool copies, no stale facts. A hook observes the outcome and cannot alter it.

- `topic_created` — `TopicCreated`: `identity`, `checked_out` (the path checked out the fresh branch), `published` (the path published the work), `todo` (the final text, or None when none resolved), `commit_message` and `commit_hash` (present exactly when the path builds a commit — the quarantined plant and the publication; None on the checked-out and fast-creation paths).
- `topic_published` — `TopicPublished`: `identity`, `commit_message`, `commit_hash`, `todo` — the facts of one successful push, identical to the paired `topic_created`.
- `topic_switched` — `TopicSwitched`: `identity`, `outcome` — exactly one of `local-checkout`, `created-from-remote`, `already-on-branch`. The identity degrades to the branch-only form when the switched branch hosts no topic.
- `topic_todo_entered` — `TopicTodoEntered`: `identity`, `text` — the final written text, after every amendment. No prior text is carried; a tool keeps its own state in its own `self` context.
- `topic_deleted` — `TopicDeleted`: `identity` (no branch fact), `local_branch` and `origin_twin` (each None when the target had none), `directory_removed`. No deleted-commit hash is carried.

## The amendment views

Each amendment checkpoint delivers a **fresh view per hook** over the live shared draft. The read-through attributes — `commit_message` / `todo` on the creation view, `text` on the entry view — read the live holder, so a later hook sees the committed amendments of the earlier hooks.

- `amend_creation` — `CreationAmendment`: `identity`, `checked_out`, `published`, the reads `commit_message` / `todo`, and `amend(commit_message, todo)`.
- `amend_todo_entry` — `TodoEntryAmendment`: `identity`, the read `text`, and `amend(text)`.

The amendment contract:

- **Whole replacement** — `amend` buffers the complete new content; a field left out comes back as None, it is not kept as the previous value. The last committed buffer wins.
- **Per-hook commit** — the walk delivers the subscriptions in enumeration order; a hook's buffer commits only when the hook returns without raising, and two hooks of one tool never share a buffer or a failure.
- **Empty rejection** — a structurally present field that is empty or whitespace-only rejects the whole buffer (on the todo entry, a None text is rejected too).
- **Soft failure** — a raised hook, its discarded buffer, and a rejected buffer each warn on stderr naming the hook, the tool, the action, and the reason; the walk continues and the operation never breaks.
- **Content only** — an amendment transforms content; it cannot cancel, redirect, or defer the operation.
- **Identity-only form** — a creation path that builds no commit and resolved no todo still delivers `amend_creation` with both fields None; the tool decides whether to act.

> **Advisory on the pipeline fast creation.** On the fast creation of `goga pipeline <name> -t <new-branch>`, the creation amendment **observes only**: an amended todo does not land there — the todo resolves later through the entry's own `amend_todo_entry`, which owns the written text — and `commit_message` stays None (the path builds no commit).

The platform mechanism behind the action (enumeration, the registry, delivery, inspection with `goga hooks`) is the [Hooks](../hooks/index.md) domain; the registration contract for tool authors is covered in [Hooks — The registration contract](../hooks/hooks.md); the flows that fire the checkpoints are covered in [CLI](cli.md). The topics flows additionally read the effective configuration through the config amendment checkpoint delivered at their configuration load (see [Configuration — Hooks](../../configuration/hooks.md)).
