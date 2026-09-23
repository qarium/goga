# Topics — API

The facade of the domain package **`goga.topics`** — the work-tracker view of the history tree. Git access lives in the nested leaf cell `goga.topics.git`, the interactive todo entry in `goga.topics.editor`, the lifecycle hook checkpoints in `goga.topics.hooks`; all surface through this facade's routines. Identity, addressing, and statuses come from `goga.history` (see [History — API](../history/api.md)).

The signatures below are the CODEMANIFEST contract of the cell.

## Board

```python
collect_topic_board(year: str | None = None, remote: bool = False,
                    hosts: tuple[str, ...] | None = None) -> list[BoardRecord]
```

Collect the cross-branch topic inventory of one year — every topic with its hosting branch, statuses, and todo summary. `year` as four digits (`None` — the current year); `remote=True` reads remote-tracking refs instead of local branches; `hosts` keeps only the records whose branch display name exactly equals one of the given names (union across values; an unknown name yields the empty list, never an error). Records sort by scale order of the first maximal status, then alphabetically by topic.

```python
BoardRecord(topic: str, branch: str, statuses: list[str], current: bool,
            remote: bool, todo: str | None = None)
```

One row of the board audit view. `topic` — the slug; `branch` — the display name of the hosting branch; `statuses` — the qualified names of the maximal present statuses in scale order; `current` — the row hosts the current working branch; `remote` — the hosting ref is remote-tracking; `todo` — the todo summary (the first non-empty line of `todo.md` after `#` markers are stripped) or `None`.

```python
aggregate_topic_board(records: list[BoardRecord],
                      hosts: tuple[str, ...] | None = None) -> list[BoardEntry]
```

Project the per-host records into the default board — a pure projection with no git access: one entry per topic that still has its own branch (a hosting branch whose branch part normalizes into the slug); a topic carried only by merged hosts produces no entry. Several own branches colliding resolves deterministically — the current-branch record, else a non-remote one, else the display-name alphabet — and the entry carries that record's statuses and todo summary. `hosts` keeps only the entries whose hosts list contains one of the given names (union; the own-branch gate stands first, so the filter never resurrects a merged-only topic). Entries sort by scale order of the first maximal status, then alphabetically by topic.

```python
BoardEntry(topic: str, branch: str, hosts: list[str], statuses: list[str],
           current: bool, remote: bool, todo: str | None = None)
```

One entry of the default board. `branch` — the display name of the topic's own branch; `hosts` — the display names of every branch carrying the topic's history, the own branch included, alphabetical; `current` — any record of the topic hosts the current branch; `remote` — the own branch is a remote-tracking ref; the rest as in `BoardRecord`.

## Switching and ensuring

```python
resolve_switch_candidates(identifier: str, year: str | None = None) -> list[SwitchCandidate]
switch_topic(identifier: str, todo: bool = False, year: str | None = None) -> str
ensure_topic(identifier: str, todo: bool = False, year: str | None = None) -> str
```

`resolve_switch_candidates` resolves an identifier through the three tiers — exact branch name, exact topic slug (local before remote), prefix — and returns the candidates. `switch_topic` brings the repository onto the hosting branch (a `ValueError` carries ambiguity and clean-failure reasons). `ensure_topic` is the combined orchestration: it switches onto hosted work and creates fresh work from the current HEAD when nothing hosts the identifier — the routine behind `goga pipeline <name> -t`. With `todo=True` the external editor opens the topic's `todo.md` after the switch. Each returns its single result line.

```python
SwitchCandidate(branch: str, topic: str | None, statuses: list[str],
                current: bool, remote: bool)
```

One resolution candidate — `topic` is `None` for a branch hosting no topic.

## Creation

```python
create_topic(branch_name: str, base_ref: str, todo: str | None = None,
             todo_from_stdin: bool = False, publish: bool = False,
             commit_message: str | None = None, year: str | None = None,
             switch: bool = False) -> str
```

Create fresh work — a branch named verbatim at `base_ref` with the topic of the year. The todo resolves through the acquisition ladder: a non-empty `todo` value wins and the piped channel stays unread; `todo_from_stdin=True` declares the piped stdin as the source — read fully once at todo-resolution time, decoded strictly UTF-8, verbatim; undeclared piped content is a clean error, a bare pipe falls through to the editor rung. The default path plants one quarantined commit carrying the topic's `todo.md` (git plumbing, the working copy untouched) — the todo is required there. `switch=True` checks the branch out instead (the topic directory lands uncommitted, the todo optional). `publish=True` builds the same one-commit branch and pushes it to `origin` without switching; `commit_message` is the publication-only commit template. Returns the result line.

```python
enter_topic_todo(topic: str, year: str | None = None,
                 branch: str | None = None) -> bool
publish_topic(branch_name: str, todo: str, base_ref: str,
              commit_message: str | None = None, year: str | None = None) -> str
```

`enter_topic_todo` opens the external editor on the topic's `todo.md` (`True` — saved, `False` — cancelled); `branch` is the branch fact of the delivered event identity (`None` leaves the identity without one). `publish_topic` is the fast creation-and-publication cycle.

The creation, publication, switch, ensure, todo-entry, and deletion routines all deliver the topics lifecycle checkpoints — the saved todo text and the commit message pass through the amendment hooks before they are fixed into the artifacts, and each completed moment emits its notification (see [Topics — Hooks](hooks.md)).

## Occupancy oracles

```python
check_branch_occupancy(branch_name: str, slug: str, year: str | None = None) -> str | None
check_slug_occupancy(slug: str, year: str | None = None) -> str | None
```

Read-only probes: the first returns the conflict reason when the branch name or the topic is already occupied, the second when the slug's topic directory or hosted branch exists. `None` — free.

## Deletion

```python
resolve_delete_targets(identifiers: list[str], year: str | None = None) -> list[DeleteTarget]
delete_topics(targets: list[DeleteTarget], year: str | None = None) -> str
```

`resolve_delete_targets` resolves every identifier first (all-or-nothing; a `ValueError` carries ambiguity, merged work, and current-branch reasons). `delete_topics` removes each target's local branch, `origin` twin, and topic directory; a rejected remote deletion restores the failing target's local branch. `DeleteTarget(topic, branch, remote, has_dir)` carries the resolved target.

## Example

```python
from goga.topics import collect_topic_board, ensure_topic

for record in collect_topic_board("2026"):
    print(record.topic, record.branch, record.statuses)

# onto the branch hosting feat-x — or fresh work when nothing hosts it
line = ensure_topic("feat-x")
print(line)  # e.g. "Switched to branch feat/x"
```
