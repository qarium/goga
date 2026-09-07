# Install

Install and remove `goga-tool` packages — into the **exact interpreter that runs goga**.

The install domain manages the tool packages of the running environment. Which tasks it solves:

- **Install a tool** — `goga install <name>` pip-installs the package into the running interpreter's pip, regardless of how goga was deployed (pipx venv, system Python, anything else); `--version` pins through the four-form grammar (`1.0.x`, `1.x`, `1.0.1`, `latest`).
- **Install from source** — `goga install --local <path>[:<tool-name>]` pip-installs a local directory without a PyPI lookup.
- **Install the declared set** — a bare `goga install` installs every tool declared under `tools:` in `.goga/config.yml` in one pip call (see [Configuration](configuration.md)).
- **Post-install hooks** — after a successful pip, each freshly installed tool's optional `install(user)` facade callable runs (see [Hooks](hooks.md)).
- **Activate** — every agent recorded in `~/.goga/connect.yml` is re-synced, so the new tool's skills and pipelines appear immediately (`--no-connect` opts out — the install-only form for CI/Docker).
- **Remove a tool** — `goga uninstall <name>` removes exactly one package after a confirmation, then re-syncs the agents; a tool removed by hand with plain pip leaves its artifacts behind until the next re-sync.

## In this directory

- [CLI](cli.md) — the full `goga install` command reference
- [Uninstall](uninstall.md) — the full `goga uninstall` command reference
- [Configuration](configuration.md) — the `tools:` section of `.goga/config.yml`
- [Hooks](hooks.md) — the post-install hook and hook points for tool packages
- [API](api.md) — the `goga.commands.install` package facade
