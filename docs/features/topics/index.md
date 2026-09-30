# Topics

Organize work as **topics** — one directory per piece of work under `.goga/history/<year>/<topic>/`, each usually living on its own git branch.

The topics domain is the work-tracker view of the history tree: it answers *what is being worked on, where it lives, and how to get onto it*. Which tasks it solves:

- **See the work** — the board (`goga topics board`) is the cross-branch inventory of one year: one entry per topic with its own branch, its statuses, its hosting branches, and (with `--info`) its todo summary and its divergence marker against the configured `topics.base_ref` — or the `--per-host` audit view with one row per topic and hosting branch of the own-branched topics, and `--json` for the machine-readable form. It reads branch trees without checkout, so the board sees committed work on every branch — and the working copy of the current one.
- **Start work** — creation (`goga topics create`) plants a branch with the topic's first artifact (the committed `todo.md`) at an explicit base, or publishes it to `origin` in one step. By default you stay on your branch — the quarantine commit never touches your working copy.
- **Enter the intent** — the todo is the multi-line statement of the work, entered on the command line (`--todo` with a value), piped into stdin (the value-less `--todo`), or in the external editor; it feeds the `todo` status and the board's `--info` column.
- **Resume work** — switching (`goga topics switch`) resolves a branch name, a topic slug, or their prefix onto the hosting branch; `goga pipeline <name> -t <identifier>` runs the same resolution before a pipeline launch (see [Pipelines](../pipelines/cli.md#topic-switch)).
- **Exchange work with the base** — `goga topics update` brings a topic up to its base (merge, rebase, or fast-forward under `topics.update.strategy`), and `goga topics propagate` delivers a finished topic into its base and pushes it (merge, ff, or squash, one confirmation). Both are checkout-free for other topics — and the update of the current topic runs behind a read-only pre-flight — with a uniform rollback on every failure.
- **Deliver existing work** — `goga topics publish` pushes a topic's own branch to `origin` as an operation of its own (`pushed` — the twin created or fast-forwarded from behind, `up-to-date`, `remote-ahead`; a diverged twin is a clean error).
- **Finish work** — deletion (`goga topics delete`) removes a topic's own local branch, its `origin` twin, and its directory in one confirmed step, or clear the merged topics of a year in one confirmed pass (`goga topics clear`) — every own-branched topic the base ref's tree already carries; a topic without its own branch is history and appears in no view.

## Model

- A topic is identified by its **slug** — the normalized name (lowercase, non-ASCII dropped, anything outside `[a-z0-9]` as `-`, repeat hyphens collapsed, edges trimmed: `Feature/Foo_Bar` → `feature-foo-bar`).
- The topic directory is `.goga/history/<YYYY>/<slug>/`; its artifacts (`todo.md`, `prd.md`, …) carry the topic's statuses (see [History](../history/index.md)).
- Every mutation is local except the `origin` network set — the `--publish` push, the delete push, the update publish push, the publication fetch and publication push of `goga topics publish`, the push inherent to every propagate, and the single targeted fetch of a base resolution. The exchange (`update`, `propagate`) needs git >= 2.40.
- Domain errors are clean one-line errors (exit 1, no traceback).

## In this directory

- [CLI](cli.md) — the full `goga topics` command reference
- [Configuration](configuration.md) — the `topics:` section of `.goga/config.yml`
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.topics` package facade
