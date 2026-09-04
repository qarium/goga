# Connect

Install goga skills and commands into AI coding agents.

The connect domain wires goga into the agent layer. Which tasks it solves:

- **One-time setup** — `goga connect <agents>` installs the goga skill bundle centrally into `~/.goga/skills/` and symlinks it into each named agent's skills directory, so `/goga:<command>` slash commands and the `goga-*` skills appear in the agent session.
- **Tool surfacing** — the same run auto-discovers every installed `goga_tool_*` package: their skills land in the shared catalog and their pipeline-files install into `~/.goga/pipelines/` namespaced as `<tool>:<name>.yml`.
- **Re-sync** — every command that changes the installed package set (`goga install`, `goga uninstall`, `goga upgrade`) re-syncs the registered agents through this domain, keeping `~/.goga/` and each agent's symlink tree in step.

The connected agents are recorded in `~/.goga/connect.yml` (the home-level state — see [Configuration — Home](../../configuration/home.md)); the agent wrapper mechanics used by build and pipelines are covered in [Configuration — Agents](../../configuration/agents.md).

## In this directory

- [CLI](cli.md) — the full `goga connect` command reference
- [Configuration](configuration.md) — the domain reads no project configuration section
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.connect` package facade
