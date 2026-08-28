# history — topic statuses

How to read the status of history topics with the `goga.history` facade. For
consumers that report progress: CLI status output, reviews, dashboards.

A topic's status is the process stage reached by its deepest present
artifact:

| Status | Deepest artifact present |
|---|---|
| empty | none |
| defined | prd.md |
| discovered | adr.md |
| backlog | task.md |
| designed | arch.md |
| specified | design.md |
| planned | plan.md |
| done | completed/plan.md |

## Listing a year with statuses

```python
from goga.history import collect_topic_statuses

records = collect_topic_statuses()             # current year
records = collect_topic_statuses(year="2025")  # explicit year
for record in records:
    print(record.topic, record.status.value)
```

- One `TopicRecord` per topic, sorted alphabetically by topic.
- An absent year or a year without topics yields an empty list — not an error.
- Filtering (by status name or topic substring) belongs to the consumer: the
  facade returns the full year.

## Resolving one topic's status

```python
from goga.history import resolve_topic_dir, resolve_topic_status

status = resolve_topic_status(resolve_topic_dir("history-commands"))
```

- `completed/plan.md` wins over every flat artifact when present.
- Read-only.

## Validating status names

```python
from goga.history import TopicStatus

TopicStatus("planned")  # -> TopicStatus.planned; ValueError for unknown names
```

- Use this to validate user-supplied status filters before matching records:
  the member set is fixed, and `record.status.value` carries the display name.
