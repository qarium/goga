# Workflow-level global `agent` and `env`

The workflow-file had no way to set an agent or an environment globally: authors
repeated `agent`/`env` per stage (this repository's own `default.yml` profile
stamps ~20 stages for exactly this reason), and the only workflow-scoped build
surface was the nested `build:` block. We decided to add two top-level
workflow-file keys — `agent` (str) and `env` (str→str map) — that override the
main configuration (`.goga/config.yml`) and act as the global settings for both
the pipeline run and the build.

## Decision

- **Scope — both surfaces.** The global `agent` takes the place of
  `pipeline.agent` at its existing consumption points (the afm client command
  that defaults every stage without its own `command`, the env-wrapper exec
  fallback, and the assistant fallback), and the global `env` takes the place
  of `pipeline.env` in the afm launch env layer. For the build, each pass
  (tasks / review / additional) resolves: the `build:`-block field, else the
  global key, else the config field. The config's agent-inheritance cascade
  (review inherits root, additional inherits review) keeps working — from the
  effective, post-override root.
- **Env merge law — key-wise everywhere.** A workflow key overrides the
  same-named config key; untouched config keys survive. The same law the
  `build:` block already follows. Layer order: config < workflow global <
  `build:` block < CLI (`-e` / `GOGA_EXTRA_ENV` stays above everything).
  Per-stage, gate-step, and assistant env maps keep layering above the global
  layer (existing law, unchanged).
- **Grammar.** `agent`: a non-str is a structural error; an empty/whitespace
  value normalizes to None (the `profile` pattern). `env`: the standard
  string-map pattern; an empty map equals absence (the stage-env pattern, not
  the assistant explicit-clear pattern). Both keys count as content for the
  empty-workflow rule — a workflow consisting of `agent:` alone is valid
  (`profile` still never counts).
- **Overlay merge.** The global `agent`/`env` ride verbatim from the authored
  workflow-file, exactly like `profile` and `build` — tool contributions
  cannot supply or override them.

## Considered options

- **Pipeline-run-only scope** — rejected: the task explicitly asks for global
  settings "for the pipeline and build", and both surfaces consume the same
  config-level globals today.
- **Stamping every stage's `command` at compilation** — rejected: it would
  override stages' own authored `command` values from the pipeline-file,
  while the afm client-command level already provides the global default
  without touching per-stage commands.
- **Full replacement of the config env layer** — rejected: keys absent from
  the workflow would silently disappear from the effective layer; key-wise
  merge preserves the "override one variable" use case already accepted for
  the `build:` block and keeps the config's downward inheritance rules intact.
- **Tool-contributable globals in the overlay** (memory-style later-tool-wins)
  — rejected: global run settings belong to the workflow author, not to
  tools; they join `profile`/`build` in the verbatim-from-base set.

## Consequences

- The global `env` is ambient: every wrapper (stage, gate, assistant) and both
  consumers (pipeline, build) inherit it, as they inherit `pipeline.env` and
  the build env layers today. It reaches the review and external-review env
  layers as a base under their own layers — a deliberate new workflow layer;
  the config's own fields still never inherit into each other.
- An assistant declaration without `agent` resolves to the workflow's global
  agent (it becomes the "effective global pipeline agent").
- The globals take effect only when the respective workflow is active on the
  surface (the pipeline run's workflow; the build's `-w`/`GOGA_WORKFLOW`
  selection).
- Gate AI-review steps still require their own `agent` — the global agent is
  not their fallback.
- The keys are rendered by the contributor profile like the rest of the
  workflow-file; the `profile` peek and activation are unaffected.
