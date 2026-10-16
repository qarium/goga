# Workflow-driven build settings layering

## Domain

How a workflow-file drives build settings on top of .goga/config.yml:
the six-field `build:` block, the key-wise env merge, and the
config < workflow < CLI order. Target audience: configuration authors
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

    .goga/config.yml  <  workflow build:  <  CLI flags

- Absent block fields never override the configuration.
- Agent fields override when set (root, review, additional — each
  independently).
- Env maps merge KEY-WISE: a workflow key overrides the same-named
  config key; every other config env entry survives. Example: the
  workflow sets one model variable, the config keeps the rest.

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

## What does NOT change

Ralphex invocation shape, the two-pass cycle, hooks checkpoints, and
plan relocation are unchanged. Env delivery to executors moves to
generated per-role wrappers — agents receive the same effective
environment through the wrappers; only the command fields in `.ralphex/config`
now point at the generated wrappers.
