# history — year and topic inventory

How to walk the `.goga/history/` tree with the `goga.history` facade.
For consumers that inventory history: CLI list output, audits, cleanups.

## Collecting the full tree

```python
from goga.history import collect_history_tree

tree = collect_history_tree()
for year_record in tree:
    print(year_record.year)           # "2026"
    for topic in year_record.topics:  # sorted alphabetically
        print(topic)
```

## Collecting one year

```python
from goga.history import collect_history_tree

tree = collect_history_tree(year="2025")  # one section only
for year_record in tree:
    ...  # exactly one HistoryYear when the year exists
```

- One `HistoryYear` per year, sorted by year ascending; topics within a
  year sorted alphabetically.
- A year directory is a directory named with exactly four digits; anything
  else in the history root is ignored. Only directories count as topics.
- An absent history root — or a year missing from the tree — yields an empty
  list, not an error.
- The tree carries names only: no statuses, no artifact lists.
