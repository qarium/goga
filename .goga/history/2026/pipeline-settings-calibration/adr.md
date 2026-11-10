# In-Container Direct Execution, Assistant Partial Override, and Environment-Driven Configuration

Five changes calibrate how `goga pipeline` / `goga build` run and how their settings
resolve: inside the goga container the normal commands must work directly, tool-delivered
assistants must stay tool-delivered while the project configures their launch, configuration
scalars must come from the environment, goga-managed runs must not accept out-of-model
stage addition, and a failing stage must fail the `goga pipeline` invocation. The decisions
below were settled in a technical interview on 2026-11-02 against the shipped code and the
afm v2.0.9 engine; the product-level definition lives in
[prd.md](prd.md).

## Decisions

1. **Direct in-container execution reuses the launcher's own composition.** The Click
   commands keep composing exactly today's in-container command line
   (`python3 -m goga.pipeline run NAME --port N …` / `python3 -m goga.build PLAN …`) and
   env contract (same variables, same encoders, `AFM_DIR=/home/goga/pipeline`); when the
   established in-image marker `GOGA_DOCKER=1` is present, that command is executed
   directly as a child process in the current environment instead of through
   `docker run`, the docker-CLI check is not performed, and the port is still allocated
   and passed as today. We deliberately spawn the same subprocess instead of calling the
   operation functions in-process: one execution substrate, identical behavior and output
   on both surfaces. Host-only options (`-t/--topic`, `--todo`, `--update`, `-e/--env`,
   `--add-host`, `--proxy`) fail with an explicit error naming the option; `--clean`
   keeps its meaning and wipes the in-container `AFM_DIR`; `--dry-run` prints the direct
   command it would run.

2. **Same-name assistant entries become partial overrides instead of displacement.** The
   field-level merge lives in the existing workflow overlay merge: the winning delivered
   entry (the unchanged "later tool wins" rule among tools) is the base, and every field
   the authored entry specifies (`agent`, `env`, `delegate`, `prompt`, `skills`) replaces
   the base value while omitted fields keep flowing from the tool. Field presence
   decides — an explicitly authored empty `skills: []` / `env: {}` is an override, so the
   workflow model must preserve "explicitly empty" versus "not authored" (`None`), and
   downstream consumers key env effects on a non-empty effective map. The parser accepts
   entries with neither `prompt` nor `skills` (override-style entries); the content
   requirement moves to compilation, where an effective entry that still resolves no
   `prompt` and no `skills` — including an override naming an assistant no tool delivers —
   fails with a readable error naming the assistant and its authoring site through the
   existing structural-error channel. An assistant name stays owned by one authoring
   surface (catalog or one inline declaration; a `{gate, when}` reference is not a
   surface), extending today's namespace discipline to overrides. Tool inline
   declarations under an authored name remain silently dropped as today.

3. **`!ENV NAME` is a registered YAML scalar constructor, not a preprocessing step.** The
   project-config and tool-config loaders resolve the tag through the yaml library's
   standard constructor mechanism at load time; the home-config loader stays on plain
   `yaml.safe_load` (explicit exclusion). The resolved value is always a string — no type
   coercion: each field's existing validation and empty-value semantics apply (an unset
   variable resolves to `""`, which the `agent` fields already treat as absence, while
   non-string fields reject it as today). Malformed use is reported by the yaml library's
   own error machinery (constructor errors carry the file position) rather than a custom
   error type.

4. **`add_stage: {enabled: false}` is a static field of the generated afm config.**
   `write_afm_config` writes it unconditionally next to the four existing static launcher
   fields, joining them in being product-owned and non-configurable; the stage set
   presented to the engine stays exactly the compiled pipeline.

5. **`--fail-on-error` maps onto the engine's native `afm run --exit-on-fail` flag.** The
   run-form flag is carried inside the composed in-container argv, threaded through the
   in-container CLI to the engine launch, and added as an explicit argv flag (visible in
   the process listing) rather than the `AFM_EXIT_ON_FAIL` environment variable. The
   engine's exit code already propagates verbatim to the `goga pipeline` exit status, so
   no new exit machinery is introduced.

## Consequences

- The engine integration consumes only shipped capabilities (afm v2.0.9 `--exit-on-fail`,
  `add_stage` config); the afm cook usage doc gains these two engine facts.
- Same-name collision semantics change intentionally from full displacement to partial
  override; workflows that restated a tool's content under the same name keep compiling
  but now also inherit unspecified fields from the tool.
- Host behavior is untouched: every in-container branch is gated on `GOGA_DOCKER=1`, and
  the composition code the host path uses is the code the direct path reuses.
