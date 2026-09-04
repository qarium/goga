# Topics

Organize work as **topics** — one directory per piece of work under `.goga/history/<year>/<topic>/`, each usually living on its own git branch.

The topics domain is the work-tracker view of the history tree: it answers *what is being worked on, where it lives, and how to get onto it*. Which tasks it solves:

- **See the work** — the board (`goga topics board`) is the cross-branch inventory of one year: every topic with its hosting branch, its statuses, and (with `--info`) its todo summary. It reads branch trees without checkout, so the board sees committed work on every branch — and the working copy of the current one.
- **Start work** — creation (`goga topics create`) plants a branch with the topic's first artifact (the committed `todo.md`) at an explicit base, or publishes it to `origin` in one step. By default you stay on your branch — the quarantine commit never touches your working copy.
- **Enter the intent** — the todo is the multi-line statement of the work, entered on the command line (`--todo`) or in the external editor; it feeds the `todo` status and the board's `--info` column.
- **Resume work** — switching (`goga topics switch`) resolves a branch name, a topic slug, or their prefix onto the hosting branch; `goga pipeline <name> -t <identifier>` runs the same resolution before a pipeline launch (see [Pipelines](../pipelines/cli.md#topic-switch)).
- **Finish work** — deletion (`goga topics delete`) removes a topic's local branch, its `origin` twin, and its directory in one confirmed step.

## Model

- A topic is identified by its **slug** — the normalized name (lowercase, non-ASCII dropped, anything outside `[a-z0-9]` as `-`, repeat hyphens collapsed, edges trimmed: `Feature/Foo_Bar` → `feature-foo-bar`).
- The topic directory is `.goga/history/<YYYY>/<slug>/`; its artifacts (`todo.md`, `prd.md`, …) carry the topic's statuses (see [History](../history/index.md)).
- Every mutation is local except the two `origin` pushes — the `--publish` push and the delete push; no fetch ever happens.
- Domain errors are clean one-line errors (exit 1, no traceback).

## In this directory

- [CLI](cli.md) — the full `goga topics` command reference
- [Configuration](configuration.md) — the `topics:` section of `.goga/config.yml`
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.topics` package facade
