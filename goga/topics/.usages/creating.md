# topics — creating fresh work

How to create a new branch with its topic directory using the `goga.topics`
facade. For consumers that start new work: the topics create command.

`create_topic` takes the branch name as entered. The branch keeps the name
verbatim; the topic directory takes the normalized slug of the year — the
two may deliberately differ (Feature/Foo_Bar branches into the
feature-foo-bar topic).

## Creating

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar")             # current year
result = create_topic("Feature/Foo_Bar", year="2025")
print(result)  # one line describing what was created
```

- A free name creates the branch, switches to it, and creates the topic
  directory of the year.
- The current branch already hosting the same slug is an idempotent
  success — no mutation.
- An occupied name or an empty slug triggers a re-ask on an interactive
  terminal, or a clean error with the reason and a hint otherwise.
- Occupancy oracles: a local branch ref, a remote-tracking ref, and the
  topic directory of the year — exposed as `check_branch_occupancy`.
- No artifact files are written inside the topic directory — artifacts
  belong to their producers.
