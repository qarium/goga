# Init

Interactive project initialization, with optional template scaffolding.

The init domain turns an empty directory into a goga project. Which tasks it solves:

- **Configure a project** — `goga init` walks an interactive questionnaire: the language, the container image, the agents, the initial `.goga/config.yml` sections, the optional Dockerfile — and writes `.goga/config.yml` (plus the Dockerfile) from the answers.
- **Invite tool packages** — `goga init -t <tool-name>` (repeatable) invites installed tool packages into the session: each invited tool declares its own question block (asked after the core sections) and contributes its config files under `.goga/tools/<tool>/` (see [Hooks](hooks.md)).
- **Scaffold from a template** — `goga init <template-url>` starts from a [copier](https://copier.readthedocs.io/) repo template (optionally pinned with `#ref` or `--ref`) and then asks only the questions the template left open.
- **Migrate a scaffolded project** — `goga init --upgrade` migrates an existing scaffolded project to the current generator version.

## In this directory

- [CLI](cli.md) — the full `goga init` command reference
- [Configuration](configuration.md) — the domain writes (not reads) the configuration
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.onboarding` package facade
