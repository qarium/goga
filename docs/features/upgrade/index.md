# Upgrade

Upgrade the goga package — and optionally the installed tool packages — then re-sync every connected agent.

The upgrade domain keeps the whole installation in step. Which tasks it solves:

- **Stay current** — `goga upgrade` upgrades goga in the running interpreter's pip; `--tools` additionally upgrades every installed `goga_tool_*` package.
- **Stay on a line** — `--patch` upgrades to the latest patch of the installed minor line; `--minor` to the latest release of the installed major line; the default takes the latest release.
- **Keep agents in step** — after a successful pip, every agent recorded in `~/.goga/connect.yml` is re-synced (through the [Connect](../connect/index.md) domain), so the refreshed skills and commands appear in each agent immediately.
- **System installs** — `--sudo` runs the pip with `sudo --preserve-env=HOME`; `--user NAME` re-syncs another user's goga installation.

## In this directory

- [CLI](cli.md) — the full `goga upgrade` command reference
- [Configuration](configuration.md) — the domain reads no configuration section
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.commands.upgrade` package facade
