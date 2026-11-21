# Runtime

The host-side runtime state of builds and pipelines — one observable tree under `~/.goga/runtime/`, addressed and packaged by the `goga runtime` command group.

Every `goga build` and `goga pipeline` run writes its persistent state (run-state and logs) to a host directory that survives across runs, so an interrupted run can be resumed. The runtime domain is the host-side observer surface over exactly that state: it answers *where the state of this project, this branch, this pipeline lives* and turns one target of it into a portable archive. Which tasks it solves:

- **Locate build artifacts** — `goga runtime build` prints the build run-state directory of the current project and the effective branch: exactly one stdout line, nothing created, printable before anything has ever run.
- **Locate pipeline artifacts** — `goga runtime pipeline NAME` prints the named pipeline's run-state directory, with the name sanitized exactly as the run sanitizes it (`:` becomes `-`) — the directory the run actually uses.
- **Address another branch's state** — the group option `-b/--branch` (placed before the subcommand token) replaces the git-derived branch segment, so the state of a deleted or other branch stays addressable without a checkout.
- **Package one target** — `goga runtime archive` turns exactly one target (the build artifacts or one named pipeline's) into a single self-contained `.tar.gz` under a wrapper root — a bug report, a backup before `--clean`, a transfer between machines.

The location identity is one shared formula — `~/.goga/runtime/<builds|pipelines>/<normalized-project>/<branch>/<pipeline>/` — resolved from the current working directory and the effective branch; the printed paths are exactly what the build and pipeline runs bind-mount. Every subcommand is host-side only: inside the goga image it refuses with a clean error.

## In this directory

- [CLI](cli.md) — the full `goga runtime` command reference
- [Configuration](configuration.md) — the domain reads no configuration section
- [Hooks](hooks.md) — the domain offers no hook points
- [API](api.md) — the `goga.commands.runtime` package facade
