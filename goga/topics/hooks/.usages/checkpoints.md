# topics — emitting lifecycle checkpoints

How the topics flows consume the checkpoint surface of the hooks zone:
delivering the two amendments before the content is fixed and emitting
the seven notifications after their moments. For the domain flows over
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
    commit_message=draft_message,  # None on paths that build no commit
    todo=draft_todo,  # None when none resolved
)
final_message = draft.commit_message
final_todo = draft.todo
```

- The identity-only form is valid — a path with no commit and no todo
  still delivers; the tool decides whether to act. On the ensure fast
  creation the creation amendment observes only — an amended todo does
  not land there; the todo-entry amendment owns the written text.
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
hooks.emit_created(
    identity,
    checked_out=False,
    published=False,
    todo=final_todo,
    commit_message=final_message,
    commit_hash=planted_hash,
)
hooks.emit_published(
    identity,
    remote_branch="origin/feat-x",
    commit_hash=tip_hash,
    commit_message=tip_message,
    outcome="pushed",
)
hooks.emit_switched(identity, outcome="created-from-remote")
hooks.emit_deleted(identity, local_branch=branch, origin_twin=twin, directory_removed=True)
hooks.emit_updated(identity, base="main", effective_tip=tip, strategy="merge", outcome="merged", published=True)
hooks.emit_propagated(identity, base="main", strategy="squash", outcome="squashed")
```

- Every `emit_*` is fire-and-forget: a failing hook warns under the
  soft error class and the command continues.
- Build every fact from the operation's own data — no git reads at a
  checkpoint.
- `topic_published` — `TopicPublished`: `identity`, `remote_branch`
  (origin/<name> — the branch that received the delivery),
  `commit_hash` / `commit_message` (git facts of the commit the remote
  branch carries at its tip after the operation), `outcome` (pushed /
  up-to-date / remote-ahead). The idempotent up-to-date and
  remote-ahead kinds emit like any other; a publication that pushed
  nothing — an already-current update, a nothing-to-do delivery —
  emits nothing.
- `topic_updated` — `TopicUpdated`: `identity`, `base`, `effective_tip`,
  `strategy` (merge / rebase / ff-else-merge / ff-else-rebase — the
  configured name; the realized kind is the outcome), `outcome` (merged /
  rebased / fast-forwarded / already-current), `published`. The
  idempotent already-current outcome emits like any other.
- `topic_propagated` — `TopicPropagated`: `identity`, `base`,
  `strategy`, `outcome` (merged / fast-forwarded / squashed /
  nothing-to-do). No pushed flag — the push is inherent; nothing-to-do
  emits.
- Both fire-and-forget under the soft error class; a declined propagate
  confirmation emits nothing.
