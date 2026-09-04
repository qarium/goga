# Features

The functional domains of goga — one directory per domain, five pages per domain.

A **domain** is a user-facing functional area of the product: what it solves, how it is configured, which CLI commands drive it, which hook points it offers to tool packages, and which Python API its package facade exposes. Internal machinery (the AST, the pipeline compiler, contract extraction) lives in [Architecture](../architecture/index.md) and [Languages](../languages/index.md); the DSL itself is covered in [Cell](../cell/index.md).

## The domains

| Domain | What it solves | CLI |
|---|---|---|
| [Topics](topics/index.md) | Organizing work: branches, the board, todo entries, creation, switching, deletion, publication | `goga topics` |
| [History](history/index.md) | The `.goga/history/` artifact tree, the status scale, orphan cleanup, scriptable paths | `goga history` |
| [Pipelines](pipelines/index.md) | Running agent-driven cycles: pipeline-files, workflows, shipped pipelines | `goga pipeline` |
| [Build](build/index.md) | Executing build plans through a ralph-loop in a container | `goga build` |
| [Tools](tools/index.md) | The tool ecosystem: using, packaging, and naming `goga-tool` packages | `goga tool` |
| [Connect](connect/index.md) | Installing goga skills and commands into AI agents | `goga connect` |
| [Upgrade](upgrade/index.md) | Upgrading goga (and tools) with agent re-sync | `goga upgrade` |
| [Install](install/index.md) | Installing and removing tool packages into the running interpreter | `goga install`, `goga uninstall` |
| [Init](init/index.md) | Interactive project initialization and template scaffolding | `goga init` |
| [Usages](usages/index.md) | Syncing cell-level usages from declared git dependencies | `goga usages` |
| [Schema](schema/index.md) | JSON schema trees from CODEMANIFEST files | `goga schema` |
| [Contract](contract/index.md) | Comparing CODEMANIFEST declarations with the implementation | `goga contract` |
| [Hooks](hooks/index.md) | The extension platform connecting domains and tool packages | `goga hooks` |
| [Lint](lint/index.md) | Validating CODEMANIFEST files | `goga lint` |

## The page model

Every domain directory carries the same five pages:

| Page | Content |
|---|---|
| **Overview** (`index.md`) | The functional area — which tasks the domain solves, its model and boundaries |
| **CLI** (`cli.md`) | The full normative command reference: synopsis, options, behavior, exit codes |
| **Configuration** (`configuration.md`) | The `.goga/config.yml` sections the domain reads (or a statement that it reads none) |
| **Hooks** (`hooks.md`) | The hook points the domain offers to tool packages (or a statement that it offers none) |
| **API** (`api.md`) | The facade API of the domain's Python package: types, signatures, parameters, purpose, usage examples |

The command reference for the whole product — one table, every command mapped to its domain — is kept in the [CLI](../cli/index.md) cross-road.
