# history — topic statuses

How to read the statuses of history topics with the `goga.history` facade.
For consumers that report progress: CLI status output, boards, reviews,
dashboards.

A topic's status is the set of its maximal present statuses on the topic
status scale. The built-in axis is fixed — empty, todo, defined, discovered,
backlog, designed, specified, planned, done. `empty` is the floor for a
topic with no artifact at all; each of the other eight is marked by one
artifact inside the topic directory, in axis order — todo by todo.md,
defined by prd.md, discovered by adr.md, backlog by task.md, designed by
arch.md, specified by design.md, planned by plan.md, done by
completed/plan.md. Tool packages extend the scale
with qualified statuses `<tool>.<name>`, so one topic can carry several
statuses at once — all of them are shown.

## Listing a year with statuses

```python
from goga.history import assemble_status_scale, collect_topic_statuses

records = collect_topic_statuses()  # current year, scale assembled here
scale = assemble_status_scale()
records = collect_topic_statuses(year="2025", scale=scale)  # reuse one scale
for record in records:
    print(record.topic, " ".join(f"[{s}]" for s in record.statuses))
```

- One `TopicRecord` per topic, sorted alphabetically by topic; the record
  carries every maximal status name in scale order.
- Pass an assembled `scale` to reuse one assembly across calls; None
  assembles it once inside.
- `year`: `None` and the empty string mean the current year; an absent
  year or a year without topics yields an empty list — not an error.

## Resolving one topic's statuses

```python
from goga.history import (
    assemble_status_scale,
    resolve_topic_dir,
    resolve_topic_status,
)

scale = assemble_status_scale()
statuses = resolve_topic_status(resolve_topic_dir("history-commands"), scale)
```

- Nested artifact paths are honored (completed/plan.md counts).
- Read-only.

## Validating status names

```python
from goga.history import assemble_status_scale

scale = assemble_status_scale()
stage = scale.resolve_status("mkdocs.published")  # unknown name -> clean error
```

- Use this to validate user-supplied status filters before matching records:
  the member set is the assembled scale, and `stage.name` carries the
  display name.
