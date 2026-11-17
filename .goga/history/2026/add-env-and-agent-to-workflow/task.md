# Workflow-level global `agent` and `env`

## Current State

The workflow-file grammar (owned by `goga/pipeline/workflow`) has no top-level `agent` or `env` keys — authoring them today is a structural error (unknown top-level key). Agent and environment settings are authorable only:

- per stage — `WorkflowStage.agent` and `WorkflowStage.env` (an empty env map equals absence);
- in the nested `build:` block — six fields across the tasks/review/additional passes (`WorkflowBuild`);
- on assistants (catalog entries and stage attachments) and on gate steps.

The pipeline run (`goga/pipeline`) sources its global settings only from the project configuration: `pipeline.agent` feeds the afm client command (`write_afm_config`), the exec fallback of the stage env wrappers (`apply_stage_env_wrappers` with `global_agent`), and the assistant agent fallback; `pipeline.env` is the afm launch env layer, with CLI entries (`-e` / `GOGA_EXTRA_ENV`) above it and engine-variable keys dropped silently. Gate AI-review steps require their own `agent`; no global fallback exists for them.

The build (`goga/build`) resolves each pass (tasks / review / additional) only from the configuration models (`BuildConfig`, `ReviewConfig`, `AdditionalReviewConfig`) overlaid by the workflow `build:` block (`merge_workflow_build`: agent fields override when set, env maps merge key-wise with the block winning per key). The agent-inheritance cascade (review inherits root, additional inherits review) runs from the effective root — the configuration overlaid by the workflow `build:` block (`merge_workflow_build` is applied before run-settings resolution), so a workflow `build.agent` already flows into the review/additional fallbacks today. Workflow selection for the build is `-w` / `GOGA_WORKFLOW`.

The overlay merge (`goga/pipeline/hooks.merge_workflow_overlay`) carries `profile` and `build` verbatim from the authored workflow; tool contributions cannot change them.

Motivation: this repository's own `.goga/profiles/default.yml` stamps the same `agent` and `env` onto ~20 stages precisely because the workflow-file has no global surface for them.

## Description

Add two top-level workflow-file keys — `agent` (a string) and `env` (a string-to-string map) — that override the main configuration (`.goga/config.yml`) and act as the global settings for both the pipeline run and the build, per the accepted ADR (`.goga/history/2026/add-env-and-agent-to-workflow/adr.md`):

- **Grammar** (`goga/pipeline/workflow`): a non-string `agent` is a structural error; an empty or whitespace-only `agent` normalizes to absence (the `profile` pattern). `env` follows the standard string-map pattern; an empty map equals absence (the stage-env pattern). Both keys count as content for the empty-workflow rule — a workflow consisting of `agent` alone is valid (`profile` still never counts).
- **Pipeline run** (`goga/pipeline`): the workflow global `agent` takes the place of `pipeline.agent` at its existing consumption points — the afm client command default, the stage env-wrapper exec fallback, and the assistant fallback (an assistant declaration without `agent` resolves to the workflow global agent, the effective global pipeline agent). The effective launch env is the key-wise merge of `pipeline.env` with the workflow global `env` (the workflow key wins per key, untouched config keys survive); CLI entries stay above everything; engine-variable keys are still dropped silently.
- **Build** (`goga/build`): each pass (tasks / review / additional) resolves its agent as: the `build:`-block field, else the workflow global key, else the configuration field; the agent-inheritance cascade runs from the effective, post-override root. Pass env merges key-wise with the layer order: configuration < workflow global < `build:` block < CLI. The global env also reaches the review and external-review env layers as a base under their own layers.
- **Overlay** (`goga/pipeline/hooks`): both keys ride verbatim from the authored workflow in `merge_workflow_overlay`, joining `profile` and `build` in the verbatim-from-base set — tool contributions can neither supply nor override them.
- **Activation**: the globals take effect only when the respective workflow is active on the surface — the pipeline run's workflow and the build's `-w` / `GOGA_WORKFLOW` selection.
- Per-stage, gate-step, and assistant env maps keep layering above the global layer (existing law, unchanged). The contributor-profile rendering passes the new keys through like the rest of the workflow-file; the `profile` peek and activation are unaffected.

## Scope

**In scope:**

- Workflow grammar and model: top-level `agent` and `env` keys, their normalization rules, and the empty-workflow content rule (`goga/pipeline/workflow`).
- Effective global agent resolution in the pipeline run at the three existing consumption points, and the effective launch env key-wise merge (`goga/pipeline`).
- Verbatim-from-base extension of the overlay merge with the two keys (`goga/pipeline/hooks`).
- Pass-level agent/env resolution with the workflow-global middle layer in the build (`goga/build`).
- Updates to the affected cell-level `.usages` documentation (grammar, run, layering, overlay docs).
- Tests mirroring the affected modules, including normalization and boundary cases.

**Out of scope:**

- `goga/pipeline/compiler` changes — stamping per-stage commands at compilation was rejected in the ADR; the compiler consumes neither key.
- `goga/agents/wrapper` and `goga/config/project` changes — wrapper path resolution and configuration models stay as-is.
- New CLI flags or new configuration fields.
- A global-agent fallback for gate AI-review steps (they still require their own `agent`).
- Tool-contributed globals through the overlay (rejected in the ADR).
- Simplifying this repository's own `.goga/profiles/default.yml` — an enabled follow-up after the feature lands, not part of this task.

## Acceptance Criteria

- A workflow-file with top-level `agent` and/or `env` parses successfully; both keys are present in the parsed workflow document.
- A non-string `agent` (map, list, number) produces a structural error; an empty or whitespace-only `agent` is treated as absent.
- A non-string-map `env` (scalar, list, non-string keys or values) produces a structural error; an empty `env` map is treated as absent.
- A workflow containing only `agent` (or only `env`) is non-empty — it does not trigger the empty-workflow error; a workflow containing only `profile` is still empty.
- Pipeline run: with the workflow global `agent` set, the afm client command, the stage env-wrapper fallback, and the assistant fallback use it; with it absent, `pipeline.agent` applies exactly as today.
- Pipeline run: the launch env contains the key-wise merge of `pipeline.env` and the workflow `env`; a workflow key overrides the same-named config key, untouched config keys survive, CLI entries still win, engine-variable keys are still dropped.
- An assistant without `agent` resolves to the workflow global agent, then to the existing fallback chain.
- A gate AI-review step without its own `agent` still fails strictly (no global fallback).
- Build: each pass resolves its agent by build-block > workflow global > config; the inheritance cascade runs from the effective root; pass env merges key-wise as configuration < workflow global < build-block < CLI for all three passes.
- Overlay merge: authored global `agent`/`env` survive tool contributions verbatim; a tool-supplied global key never reaches the final document.
- The globals activate only via the active workflow selection on each surface; with no workflow active, behavior is identical to today.
- Compiler, wrapper resolution, and configuration models remain untouched (no contract drift there).

## Stack

- **Frameworks:** none beyond the existing project stack
- **Libraries:** PyYAML >= 6.0 (workflow parsing), jinja2 >= 3.1 (whole-file workflow rendering, unchanged), click >= 8.0 (existing CLI surface)
- **Infrastructure:** none — pure in-repo feature over Python 3.10+

## External Dependencies

| Component | Usage file                                  | Status   |
|-----------|---------------------------------------------|----------|
| jinja2    | `.goga/usages/cooks/jinja2.md`              | existing |
| PyYAML    | `.goga/usages/cooks/yaml_env_constructor.md`| existing |
| click     | `.goga/usages/cooks/click.md`               | existing |
| afm       | `.goga/usages/cooks/afm.md`                 | existing |
| agent-wrappers | `.goga/usages/cooks/agent-as-claude-wrappers.md` | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- Backward compatibility is safe by construction: top-level `agent`/`env` were structural errors before, so no existing workflow silently changes meaning.
- The overlay merge contract extension must not weaken the existing verbatim guarantees for `profile` and `build`, nor the authored-unbeatable fill semantics of the remaining blocks (`memory`, `delegation`, `repeat`, `gates`).
- The build env layering gains a middle layer — the review/additional env isolation invariants must be preserved (the global env is a base under their own layers, not an inheritance between config blocks).
- The empty-workflow content rule change shifts the emptiness conditions and error text — tests asserting the exact message need updating.
- The assistant explicit-clear env semantics (an authored empty map clears) must not be confused with the global env's empty-equals-absence normalization — the two patterns coexist deliberately.
- All changes must respect the project `convention` practice (frozen kw_only dataclasses, relative imports, Google-style docstrings, mirror-structured tests).

## Scope Estimate

Single task — no decomposition. Two new workflow-model keys plus one resolution law applied at the existing consumption points across four cells; the parts carry no independent value separately and are governed by one ADR.

## Existing Architecture

Affected cells and integration requirements:

- `goga/pipeline/workflow` — owner of the grammar and the `WorkflowDocument` model; extends with the two top-level keys and their normalization; a pure parser with no Imports (stdlib + PyYAML on the parse path, plus jinja2 for whole-file rendering in the contributor-profile zone). The graph is one-directional: the compiler and the pipeline import from it, never the reverse.
- `goga/pipeline` — run coordination; imports `WorkflowDocument` and `load_workflow` from `goga/pipeline/workflow`; resolves the effective global agent and launch env feeding `write_afm_config`, `apply_stage_env_wrappers`, and the assistant fallback; the per-stage/gate env wrapper generation keeps its law, gaining the global env as a base layer.
- `goga/pipeline/hooks` — imports `WorkflowDocument` from `goga/pipeline/workflow`; `merge_workflow_overlay` extends its verbatim-from-base set with the two keys; the amendment and tool-contribution surfaces are otherwise untouched.
- `goga/build` — imports `load_workflow` and `WorkflowBuild` from `goga/pipeline/workflow` and the configuration models from `goga/config`; extends the workflow layering so each pass resolves agent/env with the global middle layer; `goga/commands/build` needs no changes (workflow carriage and `-w` forwarding already exist).
- Untouched but verified: `goga/pipeline/compiler` (consumes neither key), `goga/agents/wrapper` (pure path resolution), `goga/config/project` (models and verbatim exposure unchanged).

## Notes

- Input artifacts: the ADR and the original TODO in this topic directory. All design decisions come from the ADR's accepted interview rounds; contract and signature design is intentionally left to the later specification stages.
- The global `env` empty-equals-absence normalization follows the stage-env pattern, not the assistant explicit-clear pattern — a deliberate distinction recorded in the ADR.
- The motivating consumer (de-stamping `.goga/profiles/default.yml`) is intentionally deferred; it doubles as a natural end-to-end validation scenario after implementation.
