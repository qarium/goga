# history — topic paths and creation

How to compute history topic paths and create topic directories with the
`goga.history` facade. For consumers that address the `.goga/history/` tree:
CLI commands, workflow scripts, and branch preparation.

Every routine accepting a topic value normalizes it first: pass a branch name
(`release/1.3.0`) or an already-normalized slug (`release-1-3-0`) — both give
`.goga/history/<year>/release-1-3-0/`. An input that normalizes to an empty
slug raises a clean error; there is no fallback name.

## Computing a topic directory

```python
from goga.history import resolve_topic_dir

topic_dir = resolve_topic_dir("Feature/Foo_Bar")  # current year
# -> .goga/history/2026/feature-foo-bar

topic_dir = resolve_topic_dir("release-1-3-0", year="2025")
# -> .goga/history/2025/release-1-3-0
```

- Pure: nothing is created on disk.
- The year defaults to the current year (four digits, local time).

## Computing an artifact file path

```python
from goga.history import resolve_topic_file

plan = resolve_topic_file("history-commands", "plan.md")
# -> .goga/history/2026/history-commands/plan.md
```

- The filename is arbitrary but must carry an extension (`plan.md`);
  a name without one is a clean error.
- The file is neither created nor checked for existence — the artifact's
  producer writes it.

## Checking whether a topic exists

```python
from goga.history import topic_exists

if topic_exists("release-1-3-0"):
    ...  # topic already occupied this year
```

- True only when the topic path exists as a directory; a stray file with the
  slug's name does not occupy a topic.
- Read-only.

## Creating a topic directory

```python
from goga.history import ensure_topic_dir

topic_dir = ensure_topic_dir("Feature/Foo_Bar")
# -> .goga/history/2026/feature-foo-bar (now existing)
```

- Always for the current year.
- Idempotent: an existing topic directory is a success, not a conflict.
  Decide occupancy *before* creating (via `topic_exists`) when the
  distinction matters.

## The slug grammar

`normalize_topic_slug` applies: lowercase → drop non-ASCII → everything
outside `[a-z0-9]` becomes `-` → collapse repeats → trim edges.

```python
from goga.history import normalize_topic_slug

normalize_topic_slug("Feature/Foo_Bar")  # "feature-foo-bar"
normalize_topic_slug("release/1.3.0")    # "release-1-3-0"
normalize_topic_slug("aБb")              # "ab"
```

- Pure and deterministic; no transliteration; a fully non-ASCII name yields
  an empty string — the caller decides what an empty slug means.

## Reading the current branch as a topic source

```python
from goga.history import resolve_current_branch_name

branch = resolve_current_branch_name()
if branch is None:
    ...  # not a git repository / detached HEAD / git missing
topic_dir = resolve_topic_dir(branch)
```

- Returns the raw branch name, or None when it cannot be determined; the
  error policy belongs to the caller.
