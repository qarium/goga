# Task: pipeline-settings-calibration

Captured verbatim in substance from the product owner's answer during the
define stage (2026-11-01/02); the full validated definition lives in
[prd.md](prd.md).

1. `goga pipeline` must be runnable inside Docker: the command must detect it
   is already in the container and invoke the in-container entrypoint
   directly. Mirrored to `goga build` per the owner's request. Primary
   scenario: developer/DevOps running pipelines in CI.
2. Tool-delivered workflow assistants cannot be configured by the user at all
   today (a same-name user entry displaces the tool's delivery entirely) —
   the user must be able to configure the agent and env of a tool-delivered
   assistant. Decided channel: the workflow file; any specified field
   overrides, unspecified fields inherit from the tool; an override naming an
   undelivered assistant is a compilation error.
3. Project config and tool config gain an `!ENV NAME` scalar (example:
   `pipeline: agent: !ENV PIPELINE_AGENT`); an unset variable resolves to the
   empty string; home config is not touched.
4. The generated afm config gains `add_stage: enabled: false` (static,
   preventive integrity of the compiled stage set).
5. `goga pipeline` gains a `--fail-on-error` option that adds the engine's
   `--exit-on-fail` to the afm launch, so a failed stage ends the pipeline
   run with an error.
