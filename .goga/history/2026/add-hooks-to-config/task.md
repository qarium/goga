# Open the config domain to tool hooks via an in-memory amendment checkpoint

## Current State

- The hooks platform (the `goga/hooks` facade over catalog, registry, dispatch, and tools) delivers domain checkpoints to installed tool packages: an additive action catalog (`goga/hooks/catalog` — `Action` records with error classes), one registry per run, per-tool staged delivery (`wrap_context` read-only proxy, `build_hook_arguments`, the `per-tool-delivery` practice). Five domains are opened: statuses, onboarding (including `onboarding / amend_config`, soft), topics, pipeline (`amend_workflow` — hard, the platform's first hard action; `run_created`; `run_completed`), and build (`validate_build` — hard with a recorded domain-local deviation; four soft notifications).
- The config domain has no hooks zone. `goga/config` is a behavior-free re-export facade over `goga/config/project` (model + loader; structural-only validation), `goga/config/home`, and `goga/config/git`. `load_project_config()` is authored-load-only: subscribed tools cannot read the loaded configuration and cannot shape the effective configuration of the current run without editing the authored file or changing goga itself.
- Source call sites of `load_project_config()`: nine host-side surfaces — the pipeline, lint, contract, install, config, build, and topics commands, plus the usages status and sync modules — and one in-container entry (`goga/build/__main__.py`, executed after `ensure_in_docker()`).
- Name divergence: the authored YAML key is `language`, the model field is `lang`, and the `goga config` command bridges the two with an alias map.
- Tool-author contract docs of the domains with hooks zones (pipeline, build, topics) live in the established form: `<domain>/hooks/.usages/checkpoints.md` plus `<domain>/.usages/registering-hooks.md`; onboarding documents its actions at the domain level only, statuses through the platform-level registering-hooks practice.

## Description

Open the config domain as the sixth opened domain per the ADR (`.goga/history/2026/add-hooks-to-config/adr.md` — the authoritative record of every contract axis; the PRD is aligned with it):

- One hard checkpoint — `config / amend_config` — fires at the project-configuration load moment, delivered over the existing hooks platform with per-tool staged delivery, mutual blindness, tool-granularity commit, and one registry per run.
- The delivered context provides the current project configuration for reading: the loaded authored configuration itself — values included, environment mappings included — through the platform's read-only proxy.
- The same context offers the amendment surface: **set** (applies where the authored configuration is silent) and **force** (overwrites authored values), addressing leaf paths known to the configuration model's type tree — scalar leaves, list-valued leaves replaced wholesale, and individual mapping entries. Model-known paths stay addressable through absent intermediate branches; the amendment materializes the missing nodes.
- The merge is deterministic per the ADR: authored silence means the absence markers of the loaded model (`None`, `{}`, `[]`); authored emptiness loses to `set`; on one path `force` beats any `set` regardless of enumeration order; among amendments of equal intent the later tool in enumeration order wins; a `set` on a non-silent authored path is dropped silently.
- A config-domain hooks zone owns the checkpoint surface: the command hands it the loaded authored config as operation data; the zone runs the per-tool delivery and returns the effective (in-memory, per-run) configuration plus applied-amendment data (tool, path, set/forced, in enumeration order). The loader contract stays authored-load-only.
- All nine host-side config-consuming surfaces switch to the zone entry (uniform reach). The in-container config loads (the `goga/build/__main__.py` entry; the same principle covers any in-container pipeline load) stay on the pure authored loader — in-container loading is correct behavior and is deliberately not switched.
- Commands print the amendment summary to stderr: one header plus one line per applied amendment in enumeration order. Configuration values (including environment values) never appear in the summary or any informational output — secrecy is enforced on the output side. Nothing is printed when nothing is applied. The stdout of `goga config` stays data-clean.
- The model field `lang` is renamed to `language` in the same major release so the authored file, the model, the CLI, and the amendment path vocabulary coincide; the `goga config` alias bridge is removed.
- Structural malformedness — an unknown path, a non-leaf address, or a wrong-typed value — is a hard delivery failure for that tool: its whole contribution is discarded and the command stops with a clean error naming the tool and the action. Semantic validation of well-formed values stays with the consumers.
- The tool-author contract is published in the established form of the opened domains.

## Scope

**In scope:**

- The additive catalog record: `domain="config"`, `name="amend_config"`, `error_class="hard"`.
- The config-domain hooks zone: the checkpoint surface, the read view, the `set`/`force` amendment surface, the deterministic merge, the structural validation against the model's type tree, and the applied-amendment data with its summary-line composition.
- Switching the nine host-side surfaces to the zone entry; stderr summary printing in the commands.
- The `lang` → `language` model rename with its consumer touch points (loader construction, the `goga config` alias removal, the `goga contract` field usage).
- The tool-author contract docs in the established form; unit and integration tests per the project conventions.
- The byte-identical passthrough guarantee when nothing is subscribed.

**Out of scope:**

- Persistent configuration changes; any new config authoring surface; exposing the home configuration (`~/.goga/config.yml`).
- New or changed config CLI commands — `goga config` remains the read-only value printer it is today; its CLI surface is unchanged, though once switched it prints effective (amended) values per the ADR.
- Changes to the hooks platform semantics (catalog rules, registry, dispatch, registration envelope) beyond the additive catalog record.
- Re-opening or amending the actions of other domains; veto or gate powers over runs.
- In-container config loads (`goga/build/__main__.py` and any in-container pipeline counterpart) — they stay on the pure authored loader.
- Redesign of the configuration model — new sections, fields, or defaults (the rename is not a redesign).
- Changes to tool package discovery, installation, or the trust model; amendments to git-derived project identity.

## Acceptance Criteria

- A tool package subscribed to the config action receives, during a real command run, the read-only view of the authored loaded project configuration, environment mappings included with their values.
- A `set` on a path where the authored configuration is silent changes what the command consumes; a `force` overwrites an authored value — verified by the command behaving per the amended effective configuration; a `set` targeting an authored value changes nothing and fails nothing (no warning, no error).
- The checkpoint is reached uniformly: each of the nine host-side config-consuming surfaces offers it.
- After a run with amendments applied, the authored `.goga/config.yml` on disk is byte-identical to before the run.
- The run output names each applied amendment — tool, path, set/forced — so the effective configuration is explainable from the run output alone; no configuration value ever appears in the summary or informational output.
- Two tools amending the same not-authored path: the later tool in enumeration order wins; each hook saw only the authored configuration; repeated runs with the same tools and file produce the same effective configuration.
- A failing hook — or a structurally malformed contribution (unknown path, non-leaf address, wrong-typed value) — during the config checkpoint stops the command with a clean error naming the tool and the action; none of that tool's amendments reach the effective configuration.
- With no tool packages installed — and with installed but unsubscribed tools — every config-loading command behaves exactly as before the change: identical output and exit codes, no summary, no registry assembly for config.
- After the rename, the authored key `language`, the model field, the `goga config` output, and the amendment path vocabulary coincide; the alias bridge is gone; no consumer references the old field name.
- The tool-author contract is published in the project's usage docs in the established form — a tool author can build against the checkpoint without reading goga source.

## Stack

- **Frameworks:** none beyond the existing project stack — click (CLI), pytest (tests), ruff (lint).
- **Libraries:** Python 3.10+ stdlib `dataclasses` (`frozen=True`, `kw_only=True`, per the `convention` practice; no pydantic); PyYAML (unchanged loader).
- **Infrastructure:** none.

## External Dependencies

| Component                              | Usage file                                             | Status                                      |
|----------------------------------------|--------------------------------------------------------|---------------------------------------------|
| Hooks platform (project cells)         | — (`goga/hooks/*` cells + `.usages` practices)         | existing, extended additively               |
| click                                  | `.goga/usages/cooks/click.md`                          | existing (covers stderr output)             |
| PyYAML                                 | inline `yaml` practice (`goga/config/project`)         | existing, unchanged                         |
| Project conventions                    | `.goga/usages/conventions.md`                          | existing, mandatory                         |

No new external dependencies; no new or updated cooks files required.

## Risks and Constraints

- The merge algebra and the structural validation (the model's type tree, absence markers, absent-branch materialization) are the intellectual core — the rules must match the ADR exactly; `force`-beats-`set` regardless of order and later-tool-wins among equal intent are easy to invert.
- Uniform reach is cross-cutting: nine surfaces across seven command cells and two usages modules — a missed surface breaks the uniformity guarantee.
- The `lang` → `language` rename touches the model, the loader construction, and at least two consumers (`goga config`, `goga contract`) plus their tests; same-major-release rename, no compatibility shim.
- Byte-identical passthrough with no subscriptions constrains the implementation: no registry assembly for config and no observable output change.
- Environment secrecy is output-side only: values are delivered in the read view but must never appear in the summary, warnings, or errors.
- No repository, git, or file reads at checkpoint time — every delivered context is built from the operation data the caller passes.
- One registry per run; the config checkpoint is usually the first checkpoint a command reaches, so registry assembly happens there (the platform's first-checkpoint behavior).
- The action address stays unambiguous against `onboarding / amend_config` — the (domain, name) pair is distinct by construction.

## Scope Estimate

Single task. One mechanism with one contract: the zone without consumers delivers no value and the consumers cannot switch without the zone — a split would create an artificial seam. Cell-level decomposition (the catalog record, the new zone cell, the touched consumer cells) happens at the architecture stage. Estimated shape: one new cell (~6–8 contract types: the zone surface, the read-and-amend context, the amendment records, the pure merge routine, the applied-amendment data), one modified leaf cell (the catalog), one modified model cell (the rename), nine switched consumer surfaces, docs, and unit plus integration tests.

## Existing Architecture

- `goga/hooks` — the platform facade: `goga/hooks/catalog` (`Action`, `declared_actions` — the additive record lands here), `goga/hooks/registry` (`HookRegistry`, `ToolHooks`), `goga/hooks/dispatch` (`emit_hook_event`, `wrap_context`, `build_hook_arguments`), `goga/hooks/tools` (`enumerate_tool_packages`). Platform semantics are not changed.
- `goga/pipeline/hooks`, `goga/build/hooks`, `goga/topics/hooks` — the structural precedents for a domain hooks zone: the zone surface entity, the contexts and amendments modules, the per-tool delivery loop, and `.usages/checkpoints.md`.
- `goga/config` — the behavior-free facade; `goga/config/project` (`ProjectConfig` model + `load_project_config` loader — the loader contract is unchanged); `goga/config/home` stays closed.
- Switching surfaces: `goga/commands/{pipeline, lint, contract, install, config, build, topics}` and `goga/usages/{status, sync}`.
- Rename touch points: `goga/config/project` (model field + loader construction), `goga/commands/config` (alias map), `goga/commands/contract` (the field usage).
- Docs: the new config hooks zone `.usages/checkpoints.md` and the config-level `registering-hooks.md`, following the pipeline and build forms.

## Notes

- Input artifacts: the ADR (`.goga/history/2026/add-hooks-to-config/adr.md`) is authoritative for every contract axis; the PRD (`.goga/history/2026/add-hooks-to-config/prd.md`) is aligned with it — its success criteria map to the acceptance criteria above.
- Formulation decisions from the interview: the read view is an explicit first-class requirement of the delivered context (user correction); the in-container loads stay on the pure loader — in-container loading is correct behavior for the build and pipeline domains and is not changed; the stack introduces no new external dependencies; the scope is a single task.
- No code examples and no architecture design are included in this task per the stage constraints; API shapes belong to the architecture stage.
