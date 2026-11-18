# Workflow-driven build settings layering

## Domain

How a workflow-file drives build settings on top of .goga/config.yml:
the two global run settings (`agent`, `env`), the six-field `build:`
block, the key-wise env merge, and the config < workflow global <
workflow build: < CLI order. Target audience: configuration authors
(deciding what lives in config vs workflow) and contributors inheriting
a workflow inside a pipeline runtime.

## The block

A workflow-file may carry a top-level `build:` block with exactly six
fields — `agent`, `env`, `review.agent`, `review.env`,
`review.additional.agent`, `review.additional.env`. Anything else in
the block (including `proxy` and `hosts`) is a structural error: those
are consumed on the host before the container starts, and the host
launcher never reads workflow files.

## Layering order

    .goga/config.yml  <  workflow global (agent/env)  <  workflow build:  <  CLI flags

The workflow-file may carry two global run settings — top-level
`agent` (a string) and top-level `env` (a str→str map) — that apply
whenever a workflow is in effect, with or without a `build:` block:

- Agent: each pass (root, review, additional) resolves the
  `build:`-block field, else the global `agent`, else the config
  field. The config's inheritance cascade (review inherits root,
  additional inherits review) then fills the still-unset fields from
  the effective, post-override root.
- Env: each pass env merges key-wise — config < workflow global <
  `build:` block < CLI. The global env is a base under the review and
  external-review env layers too; the config's own fields still never
  inherit into each other (config root env stays tasks-only).
- Absent values at any layer never override; an empty global env map
  equals absence.
- The `.goga/config.yml` `build:` section is optional: an absent
  section resolves to the empty default, so the workflow globals and
  the `build:` block can hold the whole build configuration.

Example: the workflow sets one global model variable — every pass
(task, review, external review) receives it above its own config env,
and a `build.env` key can still win per key.

## Workflow selection

- Host builds: `-w/--workflow NAME` selects the workflow (existence
  validated host-side).
- Builds inside a pipeline runtime: the pipeline-run launcher writes
  `GOGA_WORKFLOW` naming the effective workflow; the in-container build
  picks it up with no extra options. The CLI flag beats the
  environment value.
- No workflow selected → no layering, and profile activation is
  ignored entirely.

## Profile activation

The build honors the same activation channels and precedence as
pipelines (`--profile` > `GOGA_PROFILE` > workflow `profile:` default);
the workflow-file is rendered with the active profile before its
`build:` block is read. A successful launch with an effective profile
prints one stderr line: `Build running with workflow "<w>" and profile
"<p>"`.

## Invariants

Ralphex invocation shape, the two-pass cycle, hooks checkpoints, and
plan relocation follow the build contract as configured. Env delivery
to executors rides generated per-role wrappers — agents receive the same
effective environment through the wrappers, and the command fields in
`.ralphex/config` point at the generated wrappers.
