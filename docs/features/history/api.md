# History — API

The facade of the domain package **`goga.history`** — the single owner of the `.goga/history/` tree. The git branch reader lives in the nested leaf cell `goga.history.git`, the status scale in `goga.history.statuses`; both are re-exported on this facade.

The signatures below are the CODEMANIFEST contract of the cell.

## Identity and addressing

```python
normalize_topic_slug(name: str) -> str
current_year() -> str
```

The slug grammar — lowercase, non-ASCII dropped, anything outside `[a-z0-9]` as `-`, repeat hyphens collapsed, edges trimmed (`Feature/Foo_Bar` → `feature-foo-bar`) — and the current year as four digits.

```python
resolve_history_root() -> Path
resolve_topic_dir(topic: str, year: str | None = None) -> Path
resolve_topic_file(topic: str, filename: str, year: str | None = None) -> Path
topic_exists(topic: str, year: str | None = None) -> bool
ensure_topic_dir(name: str, year: str | None = None) -> Path
remove_topic_dir(name: str, year: str | None = None) -> bool
```

Topic addressing: the tree root, the topic directory, and an artifact file path (the filename taken verbatim, extension required). `ensure_topic_dir` creates the directory idempotently (parents as needed); `remove_topic_dir` removes it idempotently (`True` — removed).

## Statuses

```python
resolve_topic_status(topic_dir: Path, scale: StatusScale) -> list[str]
collect_topic_statuses(year: str | None = None, scale: StatusScale | None = None) -> list[TopicRecord]
TopicRecord(topic: str, statuses: list[str])
```

The maximal present statuses of one topic and of one year's every topic — computed against the assembled scale, in scale order.

```python
assemble_status_scale() -> StatusScale
StatusScale(stages: list[Stage])
Stage(name: str, filepath: str, before: str | None = None, after: str | None = None)
StatusRegistry(builtin_stages: list[Stage], tool_prefix: str)
```

The scale assembly — the built-in artifact axis plus the registrations of installed tool packages (see [Hooks](hooks.md)). `assemble_status_scale` is the single entry point; a broken `goga_tool_*` import raises `ImportError`, an invalid registration surfaces as `ValueError`.

## Tree traversal and cleanup

```python
collect_history_tree(year: str | None = None) -> list[HistoryYear]
HistoryYear(year: str, topics: list[str])
prune_topics(year: str | None = None, dry_run: bool = False) -> list[str]
```

`collect_history_tree` walks the tree (one year with `year`, every year with `None`). `prune_topics` deletes the orphan topics of the scoped year — the topics no branch of the repository inventory hosts — returning the removed slugs (`dry_run=True` lists without deleting).

## Git embedding

```python
resolve_current_branch_name() -> str | None
list_branch_refs() -> list[BranchRef]
BranchRef(name: str, ...)
```

The read-only branch surface: the current branch name (`None`-modes surface as `ValueError` reasons at the CLI layer) and the branch inventory used by the board, switching, and prune protection.

## Example

```python
from goga.history import collect_topic_statuses, resolve_topic_file

for record in collect_topic_statuses("2026"):
    print(record.topic, record.statuses)

plan = resolve_topic_file("feat-x", "plan.md")  # .goga/history/2026/feat-x/plan.md
```
