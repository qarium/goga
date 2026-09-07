# History

The `.goga/history/` tree — one directory per topic per year, carrying the artifacts of the work.

The history domain is the single owner of the tree: it answers *where the work's artifacts live and in what state they are*. Which tasks it solves:

- **Address artifacts** — every piece of work has a topic directory `.goga/history/<YYYY>/<slug>/`; the domain resolves directory and artifact-file paths, checks existence, creates directories idempotently, and removes them.
- **See the state** — each artifact that lands (`todo.md`, `prd.md`, `adr.md`, `task.md`, `arch.md`, `design.md`, `plan.md`, `completed/plan.md`) deepens the topic's status on the built-in scale `empty → todo → defined → discovered → backlog → designed → specified → planned → done`. `goga history status` prints the maximal present statuses of one year; tool packages extend the scale with their own qualified statuses.
- **Browse the tree** — `goga history list` prints the inventory (years and topics); `goga history path` prints exactly one path for scripting.
- **Clean up** — `goga history prune` deletes the orphan topics of a year (topics no branch hosts anymore).

The tree is meant to stay out of git — add `.goga/history/` to your `.gitignore`. The cross-branch view of the same statuses (the board) is the [Topics](../topics/index.md) domain.

## In this directory

- [CLI](cli.md) — the full `goga history` command reference
- [Configuration](configuration.md) — the domain reads no configuration section
- [Hooks](hooks.md) — the `statuses` action: how tool packages extend the status scale
- [API](api.md) — the `goga.history` package facade
