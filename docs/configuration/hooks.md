# Configuration — Hooks

How a `goga_tool_*` package amends the project configuration at the load moment. For tool-package authors; no goga code changes are needed. The platform mechanism behind every hook action is covered in [Hooks](../features/hooks/index.md).

The config domain opens one action — the configuration amendment. It is a read-and-amend view over the authored project configuration, delivered at the load moment of `.goga/config.yml`, after the authored file is loaded and before any consumer reads the configuration. It is a **hard** action.

## The events

| Address | Error class | Fires |
|---|---|---|
| `config / amend_config` | **hard** | At the project-configuration load moment of every host-side command that loads `.goga/config.yml`: `pipeline`, `lint`, `contract`, `install` (bulk), `config`, `build`, `topics`, `usages status`, `usages sync`. In-container loads stay authored-only and fire nothing. |

A failing moment fires nothing: a missing or structurally invalid configuration file fails in the loader before the checkpoint.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("config", "amend_config", "hardening", harden_config)
```

- `domain` — always `"config"`; `action` — from the table; `name` — unique per tool per address; `hook` — the callable executed when the event fires.
- A hook receives values only for the parameters it declares by the fixed offered names: `context`, `self`.

## The amendment view

`amend_config` delivers a `ConfigAmendment` view per tool. The reads: `config` — the authored loaded project configuration, deeply read-only (attribute assignment and in-place mapping writes are blocked), values and environment mappings included with their values. Compose new environment values from the existing ones freely — secrecy is enforced on the output side: goga never prints a configuration value.

```python
def harden_config(context):
    if context.config.build is None:
        context.set("build.agent", "claude")        # applies only where authored is silent
    context.set("pipeline.env.LOG_LEVEL", "DEBUG")  # materializes the absent branch
    context.force("topics.base_ref", "origin/main") # overwrites the authored value
```

- `set(path, value)` buffers an amendment that applies only where the authored configuration is silent at the path — the absence markers of the loaded model (`None`, `{}`, `[]`); authored emptiness (`False`, `""`) is authored, not silent — a `set` on it is dropped, only `force` overwrites.
- `force(path, value)` buffers an amendment that overwrites the authored value — the explicit override intent.
- Paths address model-known leaves in the authored vocabulary — the same keys the file uses: `language`, `image`, `build.agent`, `build.env.KEY`, `build.review.roles` (a list-valued leaf, replaced wholesale), `build.review.additional.patience`, `pipeline.env.KEY`, `tools.<name>`, `usages.<group>.<dep>.ref`, `lint.ignore`, `topics.base_ref`, and every other leaf of the configuration model. A model-known path stays addressable when its intermediate branch is absent — the amendment materializes the missing nodes.
- A `usages` group or dep name must be a plain name (no `/`, no `\`, no `.`/`..`) — the same key rule the loader enforces on the authored file.
- Materializing an absent `usages.<group>.<dep>` branch requires the amendments to supply its `git` too — a materialized dep without `git` is the same hard structural failure. Amended `git`/`ref` values must be non-empty strings and `root` a safe relative subpath (no `..`, no absolute) — blank `git`/`ref` and unsafe `root` values are structural failures; a blank `root` means no root.
- A later amendment of your tool on the same path replaces its earlier one.

## The merge rules

The contributions merge deterministically — the same tools and the same authored file always produce the same effective configuration:

- Authored-wins by default: a `set` on a path where the authored configuration is not silent is dropped silently — no warning, no error.
- On one path `force` beats any `set` regardless of enumeration order.
- Among amendments of equal intent the later tool in enumeration order wins.
- Tools are mutually blind — every hook reads the authored configuration; each tool's contributions commit as a unit, in enumeration order.

## Failure treatment

The action is hard. The first failing tool stops the command with a clean error naming the tool and the action; the failing tool's whole contribution is discarded — nothing partial is applied, the command does not run. A structurally malformed contribution — an unknown path, a non-leaf address, or a value of the wrong type for the node — fails the same way. Semantic validity of well-formed values stays with the consumers, exactly as with the authored file.

## The run output

When amendments are applied, the command prints a short summary to stderr: one header plus one line per applied amendment — the tool, the path, `set` or `forced` — in enumeration order. Configuration values (including environment values) never appear in the summary or any informational output. `goga config` stdout stays data-clean and prints effective (amended) values. With no applied amendments nothing is printed. The authored file is never modified — after the run it is byte-identical, and repeated runs reproduce the same effective configuration.

## API

The zone facade is importable as `goga.config.hooks`:

```python
from goga.config.hooks import (
    ConfigHooks, ConfigAmendment, ConfigOverlay, merge_config_amendments,
    ToolAmendment, AppliedAmendment, PathAmendment,
)
```

`ConfigHooks().amend_config(config)` is the checkpoint surface the commands call; `ConfigOverlay` carries the effective configuration plus the applied records and their `summary_lines`. See [Hooks — API](../features/hooks/api.md).
