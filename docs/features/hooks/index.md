# Hooks

The extension platform connecting goga domains and tool packages.

The hooks domain is the mechanism behind every domain extension: a domain declares an **action** at a checkpoint of its run; an installed `goga_tool_*` package subscribes a hook to that action; when a command first reaches the checkpoint, goga enumerates the tool packages, calls each `register_hooks` callback, and delivers the action's context to the subscribed hooks. Which tasks it solves:

- **Domains expose extension points without knowing their consumers** — a domain declares an action address and the error class; the platform owns the enumeration, registration, and delivery.
- **Tool packages extend domains with no goga code changes** — a package registers its hooks at run time; registration is never cached, so package edits apply from the next run without reinstall.
- **Inspection** — `goga hooks` assembles the registry once and prints it as a tree: tool, domain, action — the fact of registration, including every refused registration with its reason.

The declared actions today:

| Domain | Address | Error class | Purpose |
|---|---|---|---|
| [History](../history/hooks.md) | `statuses/register_statuses` | soft | The status-scale registration. |
| [Init](../init/hooks.md) | `onboarding/declare_session`, `onboarding/amend_config` | soft | The two onboarding actions — a tool reaches them via `goga init -t <tool>`. |
| [Topics](../topics/hooks.md) | `topics/amend_creation`, `topics/amend_todo_entry` | soft | Two amendments before the content is fixed. |
| [Topics](../topics/hooks.md) | `topics/topic_created`, `topics/topic_published`, `topics/topic_switched`, `topics/topic_todo_entered`, `topics/topic_deleted`, `topics/topic_updated`, `topics/topic_propagated` | soft | Seven notifications after their moments. |
| [Pipelines](../pipelines/hooks.md) | `pipeline/amend_workflow` | **hard** | The workflow amendment delivered before compilation in both the run and the card form. |
| [Pipelines](../pipelines/hooks.md) | `pipeline/run_created`, `pipeline/run_completed` | soft | The two notifications around a run's launch. |
| [Pipelines](../pipelines/hooks.md) | the fifteen bridged mid-run events | soft | The thirteen stage transitions plus `run_resumed` / `run_interrupted`, delivered live while the run executes over afm's lifecycle hooks. |
| [Build](../build/hooks.md) | `build/validate_build` | **hard** | The validation gate with verdict collection over the resolved run facts, delivered before the first pass. |
| [Build](../build/hooks.md) | `build/build_started`, `build/pass_started`, `build/pass_completed`, `build/build_completed` | soft | The four run notifications carrying the run's facts. |
| [Configuration](../../configuration/hooks.md) | `config/amend_config` | **hard** | The read-and-amend view over the authored project configuration, delivered at the load moment of every host-side config-consuming command. |
| [Schema](../schema/hooks.md) | `schema/amend_cell` | **hard** | The read-and-contribute view over the authored facts of one cell, delivered at the generation moment of the project map. |
| [Schema](../schema/hooks.md) | `schema/validate_schema` | **hard** | The observe-and-veto pass with verdict collection over the final assembled tree, delivered after the tools overlay and before serialization. |
| [Contract](../contract/hooks.md) | `contract/amend_contract` | **hard** | The read-and-contribute view over the comparison facts of one cell, delivered at the comparison moment of the run. |
| [Usages](../usages/hooks.md) | `usages/sync_started`, `usages/sync_completed`, `usages/status_started`, `usages/status_completed` | soft | The started and completed notifications around each of the two usages operations. |
| [Codegraph](../codegraph/hooks.md) | `codegraph/amend_node`, `codegraph/validate_graph` | **hard** | The node amendment over the code-derived facts of one node and the validation gate with verdict collection over the final assembled tree — firing wherever the codegraph routine runs, including inside every drift run's producer calls. |
| [Drift](../drift/hooks.md) | `drift/run_started`, `drift/run_completed` | soft | The run moments around every drift comparison — completion fires on every terminal state, crashes included. |
| [Drift](../drift/hooks.md) | `drift/amend_report`, `drift/amend_entry` | **hard** | The whole-list report adjustment and the per-entry facts amendment. |

The authoring side — how a tool package writes its `register_hooks` callback — is the [registration contract](hooks.md). Four feature domains expose **no hook actions** today — [Connect](../connect/hooks.md), [Install](../install/hooks.md) (a post-install lifecycle callback instead), [Lint](../lint/hooks.md), and [Upgrade](../upgrade/hooks.md).

## Model

- **Action** — an address `domain / name` plus an error class (**soft**: a failing hook is skipped with a warning; **hard**: the command stops at the first failure). The owner domain chooses the class when it declares the action.
- **Registry** — one per run, assembled lazily on first use at a checkpoint: packages in alphabetical order of top-level module name, subscriptions delivered in enumeration order. Commands that use no hooks never build the registry.
- **Tool identity** — assigned by goga from the package name (the `goga_tool_` prefix dropped, underscores as hyphens); a package never names itself, and identical hook names of different tools never collide.
- **Delivery** — a hook receives values only for the parameters it declares by the fixed offered names (`context`, `self`); the context is read-only (attribute assignment blocked), `self` is the tool's isolated per-run state.

## In this directory

- [CLI](cli.md) — the `goga hooks` command reference
- [Configuration](configuration.md) — the domain reads no configuration section
- [Hooks](hooks.md) — the registration contract for tool-package authors
- [API](api.md) — the `goga.hooks` package facade
