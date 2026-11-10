# Design Document: `pipeline-settings-calibration`

Complete architectural specification for the five settled decisions of the
topic (direct in-container execution, assistant partial overrides,
environment-driven configuration scalars, the governed stage set, and
fail-on-error signaling), derived from the changed CODEMANIFEST contracts.

The reader of this document is the implementation agent: every section
below is written to be implementable without re-deriving decisions.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/config/yaml/CODEMANIFEST` — **new cell**. Routine `parse_env_yaml`
  (location loader.py); practices `convention`, `yaml_env`.
- `goga/config/project/CODEMANIFEST` — Imports `parse_env_yaml` +
  usage `env-variables` from `goga/config/yaml`; inline `yaml` usage key
  deleted; `load_project_config` step 2, Requirements, Constraints rewritten.
- `goga/config/tool/CODEMANIFEST` — same import pattern; inline `yaml` usage
  key deleted; `load_tool_config` annotations rewritten.
- `goga/docker/CODEMANIFEST` — new routines `is_in_docker` (env.py) and
  `run_direct` (runner.py — added during this design, see Applied Fixes);
  marker-surface and execution-substrate paragraphs added; Description updated.
- `goga/pipeline/workflow/CODEMANIFEST` — `WorkflowAssistant.delegate`
  becomes `bool | None = None`; override-style entries (no prompt, no skills)
  parse legally; presence discipline (explicit empty `skills`/`env` preserved,
  `delegate` absent = `None`); parse steps 6.5/6.7 and Requirements rewritten.
- `goga/pipeline/hooks/CODEMANIFEST` — `merge_workflow_overlay` step 4a
  rewritten to the field-level override merge; Requirements and the
  no-partial-content-merge Constraint added.
- `goga/pipeline/compiler/CODEMANIFEST` — the effective-content check added
  to the namespace-building step of `compile_flow` step 4.10; Requirements
  and Constraints added.
- `goga/afm/CODEMANIFEST` — `run_flow` gains `exit_on_fail: bool = False`;
  argv-flag Requirements/Constraints added.
- `goga/pipeline/CODEMANIFEST` — `pipeline_cli` run subcommand gains
  `--fail-on-error`; `run_pipeline` gains `fail_on_error: bool = False`;
  `write_afm_config` writes five static fields (add_stage), keys env
  delivery on a non-empty effective map, materializes delegate False.
- `goga/commands/pipeline/CODEMANIFEST` — Imports `is_in_docker`,
  `run_direct`, usage `direct-runner` from `goga/docker`; dual-substrate
  paragraph; `pipeline` step 1a + `fail_on_error` parameter;
  `run_pipeline_container` step 12a + `fail_on_error`;
  `run_pipeline_info_container` step 7a.
- `goga/commands/build/CODEMANIFEST` — Imports `is_in_docker`, `run_direct`,
  usage `direct-runner`; dual-substrate paragraph; `build` step 1 (HOST PATH
  ONLY), step 1a, step 14a; Requirements and Constraints.

### New Entities

- `parse_env_yaml(text: str) -> data: object` — `goga/config/yaml/loader.py`.
  Environment-aware YAML load: every `!ENV NAME` scalar resolves to a plain
  string at load time through a loader-subclass constructor.
- `is_in_docker() -> flag: bool` — `goga/docker/env.py`. Non-terminal marker
  query (`GOGA_DOCKER == "1"`).
- `run_direct(argv: list[str], env: dict[str, str] | None = None) -> exit_code: int`
  — `goga/docker/runner.py`. Direct-execution substrate: spawn the composed
  argv as a child process, forward SIGTERM/SIGINT, return the child's exit
  code verbatim. (Added during this design with user approval.)

### Changed Entities

- `WorkflowAssistant` — `delegate: bool | None = None`; presence discipline
  for `skills`/`env` (authored empty values carried, never normalized).
- `parse_workflow` (steps 6.5/6.7) — the at-least-one-of-prompt-or-skills
  parse error is removed for both surfaces; `delegate` absent builds `None`;
  assistant `env` empty map preserved.
- `merge_workflow_overlay` (step 4a + stage pass) — field-level override
  merge over the winning delivered entry.
- `compile_flow` (step 4.10) — effective-content structural check with
  authoring-site error naming.
- `run_flow` — `exit_on_fail` parameter; `--exit-on-fail` argv flag.
- `run_pipeline` — `fail_on_error` parameter; forwards as `exit_on_fail`.
- `pipeline_cli` — `--fail-on-error` store-true flag on the run subcommand.
- `write_afm_config` — `add_stage: {enabled: false}` static field; non-empty
  effective env map; delegate materialization.
- `pipeline` (Click) — `--fail-on-error` flag; step 1a substrate resolution
  and host-only option rejection.
- `run_pipeline_container` — `fail_on_error` parameter; argv composition;
  step 12a direct branch.
- `run_pipeline_info_container` — step 7a direct branch.
- `build` (Click) — step 1a substrate resolution and host-only rejection;
  step 14a direct branch.
- `load_project_config` / `load_tool_config` — parse through
  `parse_env_yaml`.

### Deleted Entities

- The inline `yaml` usage keys of `goga/config/project` and
  `goga/config/tool` (superseded by the `parse_env_yaml` import).

### Usages and Annotations Changes

- New project-level practice `.goga/usages/cooks/yaml_env_constructor.md`
  (created during specify; referenced by `goga/config/yaml` as `yaml_env`).
- New cell-level usage `goga/config/yaml/.usages/env-variables.md`
  (imported by both config cells).
- New cell-level usage `goga/docker/.usages/direct-runner.md` (created
  during this design; imported by both command cells).
- `.goga/usages/cooks/afm.md` — the `--exit-on-fail` run flag and the
  `add_stage` config field documented (updated during specify).
- Dual-substrate and override-style paragraphs added to the global
  Annotations of the four affected cells (verified consistent with the
  contract bodies).

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

1. `goga/commands/pipeline/CODEMANIFEST` — the dual-substrate paragraph and
   step 12a referenced `--dry-run` on the direct path, but the `goga pipeline`
   surface has no `--dry-run` option (not in the Click signature, not in
   `run_pipeline_container`, not in the PRD's exhaustive run-form parameter
   list — R5.4). The wording was copied from the shared ADR sentence that
   covers both commands. **Fix (user-approved)**: both mentions removed; the
   dry-run direct-path behavior remains owned by `goga build`, whose surface
   carries the flag. *(defect type: interface ↔ interface inconsistency — a
   step referencing a nonexistent input)*
2. `goga/docker/CODEMANIFEST` (and the two command cells' Imports) — the
   direct-path spawn mechanics (child process + env overlay + signal
   forwarding + verbatim exit code) were specified inline three times
   (steps 12a, 7a, 14a) with no shared contract entity, forcing triplicated
   signal-handling logic. **Fix (user-approved)**: new routine `run_direct`
   in `goga/docker`; the three steps now route through it; usage
   `direct-runner` documents the executor contract. *(defect type: missing
   contract entity for a cross-cell shared behavior)*

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
HOST / IN-CONTAINER COMMAND SURFACE
==============================================================================

  goga pipeline (click)                      goga build (click)
  goga/commands/pipeline/pipeline.py         goga/commands/build/build.py
        |                                          |
        | step 1a: is_in_docker()  [goga/docker]   | step 1a: is_in_docker()
        |  True -> reject host-only options        |  True -> reject host-only options
        v                                          v
   +-----------+ GOGA_DOCKER!=1 +-----------+  direct   +--------------------+
   | host path |--------------->| docker run|<---------+ step 12a/7a/14a    |
   +-----------+                +-----------+           | run_direct(argv,   |
        | run_pipeline_container / _info / build       |   env) [goga/docker|
        |  - _compose_run_args(..., fail_on_error)     |        ]           |
        |  - env-file lines -> docker --env-file       |  - SAME composition |
        v                                             |    code (argv+env   |
  python3 -m goga.pipeline run NAME --port N ...  <----+    lines)          |
        |                (identical argv on both substrates)               |
        v                                             +--------------------+
  pipeline_cli [goga/pipeline/cli.py]  (--fail-on-error -> fail_on_error)
        |
        v
  run_pipeline(fail_on_error=...)  [goga/pipeline/run_pipeline.py]
        |  write_afm_config (add_stage.enabled=false; profiles; closures)
        |  compile_flow(flow, workflow)   [goga/pipeline/compiler]
        |    merge_workflow_overlay       [goga/pipeline/hooks]
        |      parse_workflow             [goga/pipeline/workflow]
        |        WorkflowAssistant (delegate: bool | None)
        |  load_project_config            [goga/config/project]
        |        parse_env_yaml           [goga/config/yaml]   (!ENV NAME)
        v
  run_flow(..., exit_on_fail=fail_on_error)  [goga/afm]
        |
        v
  afm run --port N [--max-parallel N] [--exit-on-fail] FLOW
```

### Data Flows

- **D1 (direct execution)**: the Click command resolves the substrate once
  for the host-only rejection; each launcher resolves it again at its own
  branch point (`is_in_docker` is a pure query — no caching). Both
  substrates share the argv composer (`_compose_run_args` /
  `_compose_argv` / `_cli_flags_to_args`) and the env-lines composer; the
  host writes the lines to a private env-file consumed by `docker run`, the
  direct path parses them into a dict consumed by `run_direct`.
- **D2 (assistant overrides)**: authored workflow → `parse_workflow`
  (presence-preserving model) → `merge_workflow_overlay` (field-level
  override over the winning delivered entry) → `compile_flow` (namespace ∪
  content check) → `write_afm_config` (profiles: agent resolution, env
  closures on non-empty maps, delegate materialization).
- **D3 (!ENV)**: `.goga/config.yml` text → `parse_env_yaml` (loader
  subclass, `!ENV` scalar constructor, `os.environ` resolution) → plain
  Python value → field validators of `load_project_config` /
  `load_tool_config` (unchanged semantics over resolved strings).
- **D4 (add_stage)**: `write_afm_config` static content dict gains
  `add_stage: {enabled: false}` unconditionally.
- **D5 (fail-on-error)**: click `--fail-on-error` → in-container argv
  `--fail-on-error` → argparse `fail_on_error` → `run_pipeline` →
  `run_flow(exit_on_fail=...)` → engine argv `--exit-on-fail`.

### Entity Dependencies

Design/implementation order (bottom-up): `goga/config/yaml` →
`goga/config/project`, `goga/config/tool`, `goga/docker` →
`goga/pipeline/workflow` → `goga/pipeline/hooks`, `goga/pipeline/compiler`,
`goga/afm` → `goga/pipeline` → `goga/commands/pipeline`,
`goga/commands/build`. No import edge changes direction; the only new edges
are the two config cells → `goga/config/yaml` and the `run_direct` /
`direct-runner` additions on the existing command-cells → `goga/docker`
edges.

---

## Code Stack Trace

### Trace: `parse_env_yaml` (new)

#### Chain
1. **Input**: raw YAML text of a configuration file (`str`).
2. A module-private loader subclass `class _EnvLoader(yaml.SafeLoader)` is
   defined once; the `!ENV` scalar constructor is registered on the subclass
   only via `_EnvLoader.add_constructor("!ENV", _construct_env)` →
   checkpoint: global `yaml.SafeLoader`/`yaml.Loader` untouched, other
   `safe_load` sites of the process unaffected (verified against the
   `yaml_env` practice: `add_constructor` mutates the class registry).
3. `_construct_env(loader, node)`: a non-scalar node raises
   `yaml.constructor.ConstructorError(None, None, "expected a scalar
   argument in !ENV", node.start_mark)`; an empty `node.value` raises
   `yaml.constructor.ConstructorError(None, None, "expected a variable name in !ENV", node.start_mark)`
   → checkpoint: `ConstructorError` is a `yaml.YAMLError` subclass, so every
   existing `except yaml.YAMLError` handler (e.g. the Click wrappers of both
   commands, `pipeline_cli`'s `except yaml.YAMLError`) keeps catching it;
   the mark makes the rendered error name the file position.
4. `os.environ.get(node.value, "")` → checkpoint: string-only resolution,
   unset variable → `""`, no coercion.
5. `yaml.load(text, Loader=_EnvLoader)` → the parsed value with every
   tagged scalar already a plain string → checkpoint: a `!ENV` tag in a
   non-scalar position (a sequence/mapping node, e.g. `key: !ENV [x, y]`)
   is rejected by the constructor's own scalar-node check of step 3 —
   PyYAML dispatches a tagged non-scalar node to the registered
   constructor (verified: without the check, `os.environ.get(<list>)`
   raises a raw `TypeError` that no `yaml.YAMLError` handler catches). A
   scalar `!ENV` in a mapping-KEY position resolves normally (it is a
   scalar node; the resolved string becomes the key) — no special-casing
   of positions exists (practice constraint).
6. **Output**: the parsed value as-is (mapping / list / scalar); no models,
   no validation, no logging of resolved values (secrets).

#### Checkpoint Summary
- Subclass-scoped registration: passed (practice verified).
- Error channel: passed (library-native `ConstructorError` with mark).
- String-only resolution: passed.

### Trace: `load_project_config` (changed step 2)

#### Chain
1. **Input**: cwd-anchored `.goga/config.yml`.
2. Existence check unchanged (`FileNotFoundError` when absent).
3. Read the file TEXT, then `data = parse_env_yaml(text)` — replaces
   `yaml.safe_load(f)` → checkpoint: `parse_env_yaml` takes `str`, so the
   handle-based read becomes a text read (`config_path.read_text()`); an
   empty file parses to `None` → the existing `FileNotFoundError` branch is
   preserved; `OSError`/`UnicodeDecodeError` propagate as today.
4. `data is None` / non-mapping guards unchanged.
5. Field validators receive resolved strings: `pipeline.agent: !ENV X` with
   `X` unset arrives as `""` → `_parse_optional_agent` strips → `None`
   (established emptiness semantics) → checkpoint: SC6 satisfied — the
   configuration loads and the field behaves as absent.
6. A non-string field receiving a `!ENV` string (e.g. `build.max_iterations:
   !ENV N`) is rejected by its own validator (`must be an int`) →
   checkpoint: no coercion, per-field validation applies verbatim.
7. **Output**: `ProjectConfig` unchanged in shape.

#### Checkpoint Summary
- Text-vs-handle read: passed (design notes the mechanical change).
- Empty-value semantics: passed (agent → `None`).
- `import yaml` in `loader.py` becomes code-unreferenced after the swap —
  remove it (docstring exception names stay); ruff would flag the unused
  import. Passed.

### Trace: `load_tool_config` (changed step 4)

#### Chain
1. **Input**: `(tool, filename, root=None)`; flat-segment filename guard
   unchanged (clean `ValueError` before any read).
2. Absent file → `None` unchanged.
3. Present file: `parse_env_yaml(path.read_text(encoding="utf-8"))`
   replaces `yaml.safe_load(...)` → checkpoint: identical call shape (the
   routine already read text); `yaml.YAMLError` (incl. constructor errors of
   malformed `!ENV` use) propagates raw — interpreting is the consumer's
   job.
4. **Output**: the raw value as-is (resolved strings inside).

#### Checkpoint Summary
- Raw passthrough preserved: passed.
- Home configuration explicitly NOT migrated (stays `yaml.safe_load`;
  a `!ENV` tag there remains an unknown-tag parse error — the documented
  product decision, C3).

### Trace: `is_in_docker` (new)

#### Chain
1. **Input**: none.
2. `os.environ.get("GOGA_DOCKER")` → `return value == "1"` → checkpoint:
   exactly the `ensure_in_docker` marker rule (`!= "1"` refusal there,
   `== "1"` True here); no other variable read, no output, no caching.
3. **Output**: `bool`.

#### Checkpoint Summary
- Marker-rule sharing with `ensure_in_docker`: passed.

### Trace: `run_direct` (new)

#### Chain
1. **Input**: full child argv (program token first) + optional env layer.
2. Compose child env `{**os.environ, **env}` → checkpoint: the caller's
   process environment is never written (mirrors `run_flow`'s layer
   contract).
3. Save previous SIGTERM/SIGINT handlers; install a handler that forwards
   the signal to the live child and exits `128 + signum` → checkpoint:
   same shell convention as `DockerRunner` (130/143); the forward happens
   BEFORE the exit so the child terminates (the docker substrate's
   `docker kill` analogue).
4. `subprocess.Popen(argv, env=composed)` with inherited stdio → output
   streams live, byte-identical to the container stream → checkpoint:
   no capture, no docker, no version check (substrate-scoped gates belong
   to `DockerRunner` only).
5. `proc.wait()`; finally restores the handlers.
6. **Output**: the child's returncode verbatim (or the SystemExit
   `128 + signum` unwind on a signal).

#### Checkpoint Summary
- Signal forwarding + exit convention: passed (matches DockerRunner
  semantics minus docker kill).
- No substrate-scoped gates: passed.

### Trace: `parse_workflow` steps 6.5 / 6.7 (changed)

#### Chain
1. **Input**: the rendered workflow mapping.
2. Catalog entry (6.5): validate the entry is a mapping; validate each field
   via `_validate_catalog_field` (types unchanged: str prompt/agent, list-of-str
   skills, bool delegate, str→str env) → checkpoint: assistant `env` now
   validates through a presence-preserving variant — an authored `env: {}`
   returns `{}` (NOT `None`); the per-STAGE `env` of `WorkflowStage` keeps
   `_validate_stage_env`'s empty→`None` rule (split helpers, see Algorithm
   Design).
3. The at-least-one-of-prompt-or-skills check is DELETED (both 6.5 and the
   inline branch of 6.7) → checkpoint: an entry carrying none of the five
   fields (`NAME: {}`) now parses as an override-style entry with every
   field `None` — legal authoring whose content requirement moves to
   compilation.
4. `delegate=fields.get("delegate")` — absent builds `None` (was `False`)
   → checkpoint: `None` vs `False` distinguishable for the overlay merge.
5. Name grammar / reserved name / duplicate-namespace rules unchanged;
   the namespace walk's `_is_declaration` discriminator becomes the
   five-field presence check (see Algorithm Design) → checkpoint: an
   override-style inline declaration (`{when: start, agent: x}`) now COUNTS
   for the duplicate-name rule (previously it would have been
   misclassified as a reference by the prompt/skills-only discriminator).
6. **Output**: `WorkflowDocument` with presence-preserving
   `WorkflowAssistant` models.

#### Checkpoint Summary
- Parse relaxation + presence discipline: passed.
- Discriminator equivalence: passed — for stage attachments the five-field
  check is EXACTLY the parse-time key-set discrimination (a full inline
  declaration authors ≥1 key beyond gate/when; every authored key leaves a
  non-`None` value because authored `null`s are type errors in the
  validators).

### Trace: `merge_workflow_overlay` step 4a + stage pass (changed)

#### Chain
1. **Input**: authored `base` (or `None`) + committed `contributions` in
   enumeration order. Empty contributions → passthrough (unchanged).
2. Seed namespace `_authored_namespace(base)`: authored catalog names +
   authored inline-declaration names (five-field discriminator) →
   checkpoint: override-style authored inline declarations now seed the
   namespace (they own their name).
3. Catalog pass (4a):
   a. `winning[name]` = the LAST contribution's catalog entry per name
      (whole entry — the later-tool-wins rule among tools is unchanged and
      NOT field-level) → checkpoint: tool-vs-tool precedence untouched.
   b. Authored catalog entries: for each, if `winning` has the name, build
      the field-merged entry (`_override_entry(authored, base)`);
      otherwise keep verbatim → checkpoint: "no delivered entry under the
      name leaves the authored entry standing alone".
   c. Fresh delivered names (in `winning`, not in the seed): add the
      winning entry verbatim, first-appearance order across contributions.
   d. `namespace.update(merged)`.
4. Stage pass (`_merge_stage_assistants`, threaded with `winning`):
   a. Start from the authored attachment map; for each authored entry that
      is a DECLARATION (five-field), if `winning` has the name, replace it
      in the result with `_override_entry(authored, winning[name])` →
      checkpoint: **position preservation** — the merged entry stays ON THE
      STAGE (the authored surface owns the landing); the delivered base
      contributes field values only. Team membership therefore follows the
      authored surface: a catalog override becomes a team member with the
      tool's content; an inline override stays stage-attached (the
      tool-inherited `skills` then hit the pre-existing inline-skills
      warning channel — documented, not a silent drop).
   b. Tool attachment append loop unchanged: entries under names already on
      the stage or in the namespace are dropped (tool INLINE declarations
      under an authored name stay silently dropped); fresh tool inline
      declarations append and join the namespace.
   c. `_override_entry` never mutates its inputs — it constructs a fresh
      `WorkflowAssistant` (merge constraint).
5. **Output**: rebuilt `WorkflowDocument`; each assistant name exactly once
   across catalog and inline declarations → checkpoint: a workflow whose
   names collide with no delivery merges to itself verbatim (every merge
   arm is conditional on a delivered base or a fresh name).

#### Checkpoint Summary
- Field-presence override (`None` flows, `{}`/`[]` clear, `False` opts
  out): passed.
- Namespace-once invariant: passed.
- Verbatim passthrough for collision-free workflows: passed.

### Trace: `compile_flow` step 4.10 (changed — content check)

#### Chain
1. **Input**: the effective workflow (post-overlay) + working body.
2. `_assistant_namespace(workflow)` builds catalog ∪ inline declarations —
   the value becomes `(entry, site)` with the site string
   `workflow.assistants.<name>` or `workflow.stages.<stage>.assistants.<name>`
   → checkpoint: the afm_config cell already carries a `(entry, site)`
   namespace (its no-agent error names sites) — the same shape here; the
   five-field discriminator decides which stage attachments join.
3. The content check (NEW): for every namespace entry, `entry.prompt is
   None AND entry.skills is None` → raise `StructuralError` naming the
   assistant and its site → checkpoint: an override-style entry WITH a
   delivered base carries the base's prompt/skills after the overlay merge,
   so the check passes exactly when content resolved (SC5); a reference
   (gate/when only) is not a namespace member and is never checked — it
   resolves against a declaration as today.
4. `_assistants_by_id` consumes the namespace (unwrapping the entry);
   reference resolution, duplicate guard, script/planning-body checks
   unchanged → checkpoint: "a workflow without same-name collisions
   compiles exactly as the same workflow carrying no override entries".
5. **Output**: `_CollaborationEmission` unchanged in shape.

#### Checkpoint Summary
- Check placement over declarations of the effective document: passed.
- Error channel: passed (existing `StructuralError` → clean stderr in
  `pipeline_cli` / the Click wrapper).

### Trace: `write_afm_config` (changed)

#### Chain
1. **Input**: `(agent, flow, workflow)`.
2. Static content: `theme`, `open_browser`, `proxy.enabled`,
   `prompts_dir`, and NEW `add_stage: {"enabled": False}` — unconditional,
   product-owned → checkpoint: SC7; serialized programmatically via
   `yaml.safe_dump` (no hand-escaping).
3. `_resolve_profiles`: env-key validation and the "declares env but" clause
   of the no-agent error now key on a NON-EMPTY effective map
   (`if declaration.env:` — `None` and `{}` both mean "no closure");
   `delegate` materializes `False` when `None`
   (`declaration.delegate if declaration.delegate is not None else False`)
   → checkpoint: the model's tri-state (`None`/`False`/`True`) collapses to
   the engine's bool exactly once, at the delivery boundary.
4. `_collaboration_section`: closure creation on `if env:` (non-empty);
   profile dict `{title, command, delegate}` with materialized delegate.
5. **Output**: the config file at the fixed in-container path.

#### Checkpoint Summary
- Non-empty-map keying + delegate materialization: passed.

### Trace: `run_flow` (changed)

#### Chain
1. **Input**: `(flow_path, port, max_parallel=None, exit_on_fail=False, env=None)`.
2. `cmd = ["afm", "run", "--port", str(port)]`; append
   `["--max-parallel", str(max_parallel)]` only when not `None`; append
   `["--exit-on-fail"]` only when `exit_on_fail` is `True`; then the
   positional `str(flow_path)` → checkpoint: flag order matches the
   contract step 3; the flag is argv-visible; `AFM_EXIT_ON_FAIL` is never
   set anywhere.
3. Spawn with the env layer over the inherited environment (unchanged);
   FileNotFoundError → 127; other OSError/ValueError → 126 (unchanged).
4. **Output**: the engine's exit code verbatim — with the flag, a failed
   stage surfaces as the engine's exit 1 returned untouched (SC8; no new
   exit machinery).

#### Checkpoint Summary
- Flag-only channel: passed (afm practice: argv flag over the env var).

### Trace: `run_pipeline` (changed) and `pipeline_cli` (changed)

#### Chain
1. `pipeline_cli` `_build_parser`: the run subparser gains
   `--fail-on-error` (`action="store_true", default=False`); it parses in
   both run and card invocations (`run NAME --info --fail-on-error` is
   legal and inert) — the same surface pattern as `-w/-p/-s`.
2. `_run_execution` passes `fail_on_error=args.fail_on_error` into
   `run_pipeline`.
3. `run_pipeline` signature gains `fail_on_error: bool = False` (last
   position); step 21 becomes `run_flow(flow_path, port,
   max_parallel=parallel, exit_on_fail=fail_on_error, env=launch_layer)`.
4. **Output**: `run_flow`'s exit code propagates through the unchanged
   step-22 status recompute and return.

#### Checkpoint Summary
- The full D5 chain (click → argv → argparse → run_pipeline → run_flow →
  engine): passed; every hop forwards only when set (`False` ⇒ no flag).

### Trace: `pipeline` Click command (changed)

#### Chain
1. **Input**: click-parsed options incl. new `--fail-on-error`
   (`is_flag=True, default=False`; run form only in effect, accepted
   without effect by the listing/card forms).
2. Step 1 unchanged: config load + amendment checkpoint (clean
   ClickException wrap).
3. Step 1a (NEW): `direct = is_in_docker()`; when `direct`, reject every
   passed host-only option BEFORE any other work — `topic is not None`,
   `todo is True`, `update is True`, `extra_env` non-empty, `add_host`
   non-empty, `proxy is not None` — each one clean `click.ClickException`
   naming the option (stderr, exit 1; no topic procedure, no port
   allocation, no launch) → checkpoint: the rejection is form-independent
   (SC2 "nothing is silently ignored" on this path) even where the host
   silently ignores `-t/--todo` in the listing forms — the host behavior
   is untouched (C1).
4. Steps 2–4 unchanged (form validation, topic procedure, home bundle) —
   on the direct path the topic procedure is unreachable for `-t` (rejected
   at 1a) and a no-op otherwise.
5. Step 5 dispatch: the run form passes `fail_on_error=fail_on_error` to
   `run_pipeline_container`; the listing/card dispatches unchanged.
6. **Output**: `ctx.exit(exit_code)`.

#### Checkpoint Summary
- Rejection ordering (after config load — the step numbering 1a — before
  form validation): passed.
- Host path untouched when the marker is absent: passed.

### Trace: `run_pipeline_container` (changed — step 12a)

#### Chain
1. **Input**: full argument set incl. `fail_on_error: bool = False`.
2. Preamble: `_check_docker()` SKIPPED on the direct path (no docker CLI
   inside the image); home config still loads (home.env is a direct-path
   env layer; `home.docker.*` tokens feed `AFM_DOCKER_FILE_ROOTS`
   composition); the `config.image is None` guard is substrate-scoped —
   skipped on the direct path (no image is ever pulled/built/run there).
3. `_run_named`: `port = _allocate_port()` on BOTH substrates (the port is
   part of the composed contract).
4. Direct branch (12a): skip the host runtime-dir machinery entirely; when
   `clean`, wipe the in-container AFM_DIR (`/home/goga/pipeline`:
   rmtree-if-exists + mkdir, mirroring `clean_pipeline_runtime_dir`'s
   wipe-and-recreate); compose the env lines through the SAME line
   composition the host path writes (`_compose_env_lines(...)`, extracted
   from `_build_env_file`); parse the lines into a dict
   (`KEY=VALUE` split on the first `=`, applied in order — last write wins,
   mirroring `--env-file`); `args = _compose_run_args(..., fail_on_error)`;
   spawn `run_direct(["python3", *args], env=parsed)`; return its code →
   checkpoint: no env-file exists on this path (nothing to unlink); signal
   handling lives inside `run_direct` (no caller-side D7 handler — there is
   no secret file to protect); `update` is unreachable (rejected at 1a).
5. Host branch: unchanged steps 5–13 (runtime dir, D7 handler, env-file,
   mounts, image acquisition, `DockerRunner`, finally unlink + handler
   restore). `_build_env_file` becomes a thin wrapper: compose lines →
   `_write_env_file(lines)`.
6. **Output**: the container's / child's exit code.

#### Checkpoint Summary
- One composition, two sinks: passed (lines → file vs lines → dict).
- Substrate-scoped skips: passed (docker check, image guard, runtime dir,
  image acquisition, DockerRunner).

### Trace: `run_pipeline_info_container` (changed — step 7a)

#### Chain
1. **Input**: the info-form argument set (no port, no fail_on_error).
2. Direct branch (7a): skip `_check_docker` and the image steps (incl. the
   image-None guard — substrate-scoped); home config loads (cargo
   composition needs the bundle only — `home.env` is NOT part of the info
   env contract, matching the host minimal shape); compose the argv via the
   existing `_compose_argv`; the profile cargo lines (existing
   `_compose_profile_carriage`, only when cargo exists) parse into the env
   layer; `run_direct(["python3", *argv], env=cargo)` → checkpoint: minimal
   read-only shape on both substrates — no port, no persistent state, no
   env-file, no caller-side signal handler (the host info path installs
   none either).
3. **Output**: the child's exit code verbatim.

#### Checkpoint Summary
- Minimal-shape parity: passed.

### Trace: `build` Click command (changed — steps 1a / 14a)

#### Chain
1. **Input**: click-parsed options (no `--fail-on-error` — build keeps its
   own exit semantics).
2. Step 1a (NEW, BEFORE the docker-CLI check of step 1): `direct =
   is_in_docker()`; on the direct path reject `extra_env` non-empty,
   `add_host` non-empty, `proxy is not None`, `update is True` — each a
   clean ClickException naming the option; step 1 (docker check) skipped
   entirely on the direct path → checkpoint: rejection precedes config
   load on this command (the contract places 1a before 1).
3. Steps 2–8 unchanged (config load, build-section guard, argv
   parsability, workflow checks, cli_flags, proxy/hosts resolution, git
   identity, env ladder composition).
4. Direct branch (14a): skip the image-None guard (substrate-scoped), the
   host ralphex runtime-dir steps (`resolve_build_runtime_dir` /
   `clean_build_runtime_dir` — docker-only), the env-file write, the
   docker-run assembly, `docker_build_if_not_exist`, `docker_update`,
   `DockerRunner`; when `clean`, wipe `<cwd>/.ralphex` (the location
   ralphex uses without the nested bind-mount); compose the env lines
   through the SAME ladder code the host path writes; parse into the child
   env layer; `args = ["-m", "goga.build", plan, *_cli_flags_to_args(cli_flags)]`;
   on `dry_run` print `shlex.join(["python3", *args])` to stderr and exit 0;
   otherwise `run_direct(["python3", *args], env=parsed)`; in finally run
   `_cleanup_ralphex_in_project(Path.cwd())` as on the host → checkpoint:
   the no-`.ralphex`-in-project invariant holds under every exit path on
   both substrates; ralphex state does not persist across direct runs (no
   host runtime mount) — an accepted, documented property of the direct
   surface.
5. Host branch: unchanged.
6. **Output**: `ctx.exit(exit_code)`.

#### Checkpoint Summary
- Ordering (1a before the docker check): passed.
- Invariant parity (`.ralphex` cleanup in finally): passed.

---

## Algorithm Design

### `parse_env_yaml` — `goga/config/yaml/loader.py` (new file)

**Responsibility**: the environment-aware YAML load of the configuration
family.

**Algorithm:**
```
1. Define _construct_env(loader, node):
   - IF not isinstance(node, yaml.ScalarNode): raise ConstructorError(None, None,
     "expected a scalar argument in !ENV", node.start_mark)
     # a !ENV-tagged sequence/mapping node dispatches HERE — the library
     # raises nothing on its own; without this guard os.environ.get(<list>)
     # throws a raw TypeError that escapes every except yaml.YAMLError handler
   - IF node.value == "": raise ConstructorError(None, None,
     "expected a variable name in !ENV", node.start_mark)
   → returns os.environ.get(node.value, "")           # string only, "" when unset
2. Define class _EnvLoader(yaml.SafeLoader) once at module import
3. _EnvLoader.add_constructor("!ENV", _construct_env)  # subclass only
4. return yaml.load(text, Loader=_EnvLoader)           # value as-is
```

**Errors:**
- `yaml.constructor.ConstructorError` (empty argument / non-scalar node —
  the constructor itself must reject both; PyYAML dispatches a tagged
  non-scalar node to the registered constructor instead of failing on its
  own) → propagates raw, carries the file mark → the consumer's existing
  `yaml.YAMLError` handling renders it.

**Edge Cases:**
- Unset variable → `""` (each field's emptiness semantics apply).
- Value containing `=`/`:`/newlines → verbatim string (no parsing).
- `goga/config/yaml/__init__.py` re-exports `parse_env_yaml` (sibling cells
  import `from ..yaml import parse_env_yaml`; a module directly inside
  `goga/config` would use `from .yaml import …`).

### `is_in_docker` — `goga/docker/env.py`

**Responsibility**: the non-terminal marker query.

**Algorithm:**
```
1. marker = os.environ.get("GOGA_DOCKER")
2. return marker == "1"
```

**Edge Cases:** unset / `"0"` / any other value → `False`. Export from
`goga/docker/__init__.py` beside `ensure_in_docker`.

### `run_direct` — `goga/docker/runner.py`

**Responsibility**: the direct-execution substrate (child spawn + signals).

**Algorithm:**
```
1. child_env = {**os.environ, **env} when env else None (inherit untouched)
2. prev_term, prev_int = save handlers
3. proc = None
   handler(signum): IF proc is not None and proc.poll() is None:
                        proc.send_signal(signum)
                    raise SystemExit(128 + signum)
4. install handler for SIGTERM and SIGINT
5. TRY: proc = subprocess.Popen(argv, env=child_env)   # inherited stdio
        return proc.wait()
   FINALLY: restore prev handlers
```

**Errors:** `FileNotFoundError`/`OSError` from Popen propagate raw (the
caller wraps; the composed argv starts with `python3`, present in the
image).

**Edge Cases:**
- `env=None` → the child inherits the current environment unchanged.
- A signal before Popen completes → `proc` is `None`; the handler exits
  without a forward (nothing to terminate).
- The exit code of a child killed by the forwarded signal is never
  returned — the `SystemExit(128 + signum)` unwind owns that path.

### The shared declaration discriminator (four cells)

`parse_workflow._is_declaration`, `overlay._is_assistant_declaration`,
`compile_flow._is_assistant_declaration`, `afm_config._is_assistant_declaration`
all become the SAME one-line rule:

```
entry.prompt is not None or entry.skills is not None
    or entry.agent is not None or entry.delegate is not None
    or entry.env is not None
```

Rationale: with the presence discipline, every authored declaration key
leaves a non-`None` value (authored `null`s are type errors at parse), so
this is exactly the parse-time key-set discrimination
(keys ⊆ {gate, when} ⇔ reference). The old prompt/skills-only rule
misclassifies override-style inline declarations as references — breaking
the duplicate-name walk (parse), the namespace seed (overlay), and the
namespace/reference resolution (compile, afm_config).

### `parse_workflow` step 6.5 / 6.7 changes

**Algorithm (deltas only):**
```
_build_assistant_catalog / _build_stage_assistants:
  - DELETE the "requires at least one of prompt or skills" raise
  - delegate=fields.get("delegate")            # was fields.get("delegate", False)
  - env via _validate_assistant_env            # {} preserved (see below)

_validate_assistant_env(scope, value):         # NEW helper (or flag param)
  - non-dict → "non-mapping env in {scope}"
  - non-str key/value → existing messages
  - return value AS-IS ({} stays {})           # the ONLY divergence from
                                               # _validate_stage_env
```

`WorkflowAssistant`: `delegate: bool | None = None` (docstring: `None`
when not authored — inheritable; `False` authored opt-out; `True`
authored permission; downstream materializes `False` when effective
`None`). `env` docstring: authored empty map is an explicit override that
clears. `skills` docstring: authored empty list likewise.

**Edge Cases:**
- `NAME: {}` (empty catalog entry) parses — every field `None`; it is an
  override-style declaration (joins the namespace unconditionally — catalog
  entries always count); with no delivered base the compile content check
  fires naming `workflow.assistants.<name>`.
- Stage-level `env: {}` STILL normalizes to `None` (the `WorkflowStage`
  rule is untouched — only the assistant fields change discipline).

### `merge_workflow_overlay` — field-level override

**Algorithm (the changed arms):**
```
_override_entry(authored, base):               # pure — fresh instance
    WorkflowAssistant(
        name=authored.name,
        prompt  = authored.prompt  if authored.prompt  is not None else base.prompt,
        skills  = authored.skills  if authored.skills  is not None else base.skills,
        agent   = authored.agent   if authored.agent   is not None else base.agent,
        delegate= authored.delegate if authored.delegate is not None else base.delegate,
        env     = authored.env     if authored.env     is not None else base.env,
        gate=authored.gate, when=authored.when)  # attachment params: authored wins

_merge_catalog(base, contributions, namespace):
  1. winning = {} ; for contribution in contributions (enumeration order):
         for name, entry in contribution.document.assistants.items():
             winning[name] = entry            # later tool wins, WHOLE entry
  2. merged = {}
     for name, entry in base.assistants.items():        # authored order
         merged[name] = _override_entry(entry, winning[name]) \
                        if name in winning else entry
  3. for contribution in contributions: for name in contribution
     catalog order: IF name in winning AND name not in authored_seed
     AND name not in merged: merged[name] = winning[name]
                                             # fresh delivered names, verbatim,
                                             # first-appearance order
  4. namespace.update(merged)

_merge_stage_assistants(authored_map, stage, contributions, namespace, winning):
  1. result = dict(authored_map) if authored_map else {}
  2. for name, entry in list(result.items()):
         IF _is_assistant_declaration(entry) and name in winning:
             result[name] = _override_entry(entry, winning[name])
                                             # position preservation: the merged
                                             # entry stays on the stage
  3. (unchanged append loop over tool stage entries with the
     on-stage and namespace dedup rules)
```

**Design decision — position preservation**: the authored surface owns the
name AND the landing position; the delivered base contributes field values
only. Consequences (all accepted and documented): a catalog override
becomes a team member carrying the tool's content (SC4 fully); an inline
override stays stage-attached — its inherited `skills` have no engine
channel and hit the existing compile WARNING (not a silent drop); the
compile content-check site naming stays truthful (the entry never moves
between surfaces); collision-free workflows merge verbatim trivially.

**Errors:** none new — the merge never raises (invalid shapes are
compile-time structural errors).

**Edge Cases:**
- Authored `env: {}` over a tool env map → the effective env is `{}` (a
  clear) → no closure at delivery (`if env:` non-empty keying).
- Authored `delegate: false` over a tool `delegate: true` → effective
  `False` (opt-out); absent delegate over `true` → `True` (inherit).
- Authored `skills: []` over tool skills → effective `[]` → the content
  check still passes (`skills is not None`), the team member carries an
  empty skills list.
- A tool delivering an override-style (content-less) entry under a fresh
  name → adds verbatim, content-less → the compile content check names it.

### `compile_flow` — the content check

**Algorithm (delta in `_collaboration_emission`):**
```
namespace = _assistant_namespace(workflow)     # now name -> (entry, site)
                                            # site: "workflow.assistants.<name>"
                                            # or "workflow.stages.<stage>.assistants.<name>"
for name, (entry, site) in namespace.items():
    IF entry.prompt is None and entry.skills is None:
        raise StructuralError(
            f"assistant {name} at {site} resolves neither prompt nor skills")
_assistants_by_id(..., unwrapped namespace, workflow.assistants)
```

**Errors:** `StructuralError` → the existing channels (`pipeline_cli`
stderr render, Click wrap on the host) — readable, names the assistant and
its authoring site (SC5).

### `write_afm_config`

**Algorithm (deltas):**
```
content statics += {"add_stage": {"enabled": False}}     # fifth static field
_resolve_profiles:
    IF declaration.env:                 # non-empty only (None and {} skip)
        validate keys (legal env names)
    target_agent = declaration.agent or the global agent fallback (unchanged)
    no-agent error: "'declares env but ' if declaration.env else ''" (re-keyed)
    delegate_effective = declaration.delegate if declaration.delegate is not None
                         else False
_collaboration_section:
    IF env:                              # non-empty → closure
        write the owner-only closure, command = closure path
```

### `run_flow`

**Algorithm (delta):**
```
cmd = ["afm", "run", "--port", str(port)]
IF max_parallel is not None: cmd += ["--max-parallel", str(max_parallel)]
IF exit_on_fail:            cmd += ["--exit-on-fail"]
cmd.append(str(flow_path))
```
(`AFM_EXIT_ON_FAIL` is never read or set.)

### `pipeline_cli` / `run_pipeline`

**Algorithm (deltas):**
```
run_parser.add_argument("--fail-on-error", action="store_true", default=False,
                        help="exit non-zero when a stage fails "
                             "(threads to afm --exit-on-fail; run mode only)")
_run_execution: run_pipeline(..., parallel=args.parallel,
                             fail_on_error=args.fail_on_error)
run_pipeline signature += fail_on_error: bool = False
step 21: run_flow(flow_path, port, max_parallel=parallel,
                  exit_on_fail=fail_on_error, env=launch_layer)
```

### `pipeline` Click command

**Algorithm (delta — step 1a):**
```
direct = is_in_docker()
IF direct:
    host_only = [
        ("--topic/-t",   topic is not None),
        ("--todo",       todo),
        ("--update/-u",  update),
        ("--env/-e",     bool(extra_env)),
        ("--add-host",   bool(add_host)),
        ("--proxy",      proxy is not None),
    ]
    for flag, passed in host_only:
        IF passed: raise click.ClickException(
            f"{flag} is host-only: it configures the docker launch, "
            f"which does not exist inside the goga container")
```
Plus: the `--fail-on-error` click option (placed after `--parallel`;
`is_flag=True, default=False`), forwarded in the run-form dispatch as
`fail_on_error=fail_on_error`.

### `run_pipeline_container` / `run_pipeline_info_container` / `build` — the direct branches

**Shared refactoring (per command cell):** extract the env-line composition
from the env-file builder so both substrates call the same composer:
`_compose_env_lines(...) -> list[str]` (pipeline run: home.env base, git
identity, raw CLI lines, engine lines with the skip rule, GOGA_EXTRA_ENV
payload, carriage lines) / the build ladder / the info cargo lines. Host:
`_write_env_file(lines)`. Direct: `_env_overlay(lines)` —
`dict(line.split("=", 1) for line in lines)` (order-preserving last write
wins, mirroring `--env-file`).

**run_pipeline_container (12a):**
```
IF is_in_docker():
    IF clean: wipe /home/goga/pipeline (rmtree-if-exists + mkdir parents)
    lines = _compose_env_lines(home.env, home.docker.run, extra_env, proxy,
                               ambient GOGA_PROFILE, home_profiles,
                               _resolve_workflow_env_name(...))
    args = _compose_run_args(name, port, workflow, no_workflow, profile,
                             skip, parallel, fail_on_error)
    return run_direct(["python3", *args], env=_env_overlay(lines))
# else the unchanged host path (runtime dir, D7 handler, env-file, mounts,
# docker_build_if_not_exist, docker_update, DockerRunner)
```
Substrate-scoped skips on the direct path: `_check_docker`, the
`config.image is None` guard, the host runtime-dir machinery. `_compose_run_args`
gains `fail_on_error: bool = False` → appends `--fail-on-error` only when
True (after `--parallel`).

**run_pipeline_info_container (7a):**
```
IF is_in_docker():
    cargo = _compose_profile_carriage(home_profiles)      # existing helper
    return run_direct(["python3", *_compose_argv(...)],
                      env=_env_overlay(cargo) if cargo else None)
```

**build (14a):**
```
IF direct:
    IF clean: rmtree(<cwd>/.ralphex, missing_ok)
    lines = the SAME ladder composition (home.env + git identity + CLI
             entries + engine proxy triple + GOGA_EXTRA_ENV + carriage)
    args = ["-m", "goga.build", plan, *_cli_flags_to_args(cli_flags)]
    IF dry_run: print(shlex.join(["python3", *args]), file=sys.stderr);
                ctx.exit(0)
    exit_code = run_direct(["python3", *args], env=_env_overlay(lines))
    ctx.exit(exit_code)
FINALLY (both substrates): _cleanup_ralphex_in_project(Path.cwd())
```

---

## Cross-cutting Concerns

- **Error handling**: no new exception types anywhere. Parse-time: the
  existing `WorkflowSyntaxError` channel (with two rules REMOVED).
  Compile-time: the existing `StructuralError` channel (one rule ADDED —
  the content check). YAML: the library's own `ConstructorError`
  (a `yaml.YAMLError` subclass) for malformed `!ENV` use. CLI: clean
  stderr messages with exit 1 (`click.ClickException` on the host command
  surface; plain `print(..., file=sys.stderr); return 1` inside
  `pipeline_cli`). Direct-path host-option rejections are ClickExceptions
  naming the option.
- **Validation**: unchanged field validators consume resolved strings
  (`!ENV` adds no coercion — a non-string field receiving a resolved string
  fails per its own rule). The workflow model's presence discipline is the
  new validation surface: parse preserves authored empties; consumers key
  on presence (`is not None`) and non-emptiness (`if env:`) explicitly.
- **Logging**: no new log sites. `run_direct` and `parse_env_yaml` never
  log (env values may carry secrets — the established constraint);
  the existing compile WARNING for channel-less inline skills now also
  covers inherited skills. The existing debug "launching read-only info
  container" line gains nothing; a direct-launch debug line is optional
  and must not carry env values.
- **Caching**: none. `is_in_docker` deliberately caches nothing (callers
  may test at any moment); `parse_env_yaml` resolves per load (the
  feature: one file, many environments).
- **Concurrency / signals**: the direct substrate forwards SIGTERM/SIGINT
  to the child and exits `128 + signum` — the same convention as
  `DockerRunner` and the host launchers' D7 handlers. No threads are
  introduced; `Popen` + `wait` with inherited stdio (streaming by
  inheritance, byte-identical across substrates).
- **Security**: the direct path writes NO env-file (the host's secret-file
  leak surface disappears there); owner-only closure files unchanged; env
  layer values never logged or printed.

---

## Usages Analysis

### `yaml_env` — `.goga/usages/cooks/yaml_env_constructor.md`
- **What it provides**: the PyYAML scalar-constructor mechanism (loader
  subclass, `(loader, node) -> value` contract, `ConstructorError` with
  mark, no-global-registration constraint).
- **Where used**: `parse_env_yaml` (its entire implementation contract).
- **Why chosen**: library-native mechanism — no preprocessing, no
  post-parse walk (practice constraint "resolve at load time only").
- **How exactly**: `EnvLoader.add_constructor("!ENV", _construct_env)`;
  `os.environ.get(node.value, "")`.

### `convention` — `.goga/usages/conventions.md`
- **What it provides**: project code/test conventions (docstring style,
  relative imports, pytest/ruff).
- **Where used**: every touched cell's global annotations.
- **Why chosen**: mandatory project-wide practice.
- **How exactly**: Google-style docstrings, intra-package relative imports,
  `pytest tests/ -x` + `ruff check goga/` green.

### `afm` — `.goga/usages/cooks/afm.md`
- **What it provides**: the engine facts consumed read-only — the
  `--exit-on-fail` run flag (v2.0.9; the argv flag over the
  `AFM_EXIT_ON_FAIL` variable) and the `add_stage` config map with the
  nested `enabled` key.
- **Where used**: `run_flow` (flag), `write_afm_config` (field).
- **Why chosen**: engine-as-shipped constraint (C5) — only shipped
  capabilities are consumed.
- **How exactly**: argv append when the flag is set; the static config map
  `{"add_stage": {"enabled": False}}`.

### `click` — `.goga/usages/cooks/click.md`
- **What it provides**: the command-surface conventions (single command,
  flag options, ClickException wrapping, `ctx.exit` propagation).
- **Where used**: `pipeline` (`--fail-on-error` flag, step-1a
  rejections), `build` (step-1a rejections).
- **How exactly**: `is_flag=True` options; `raise click.ClickException`
  for the host-only rejections (stderr + exit 1).

### Imported Usages
- `env-variables` from `goga/config/yaml` — the consumer-side authoring
  guide for `!ENV` (where the tag applies, the empty-string rule, the
  home-config exclusion).
  - Path: `goga/config/yaml/.usages/env-variables.md` (imported by
    `goga/config/project`, `goga/config/tool`).
- `direct-runner` from `goga/docker` — the executor contract for the
  direct substrate (caller composes argv+env; executor spawns/forwards/
  returns; constraints).
  - Path: `goga/docker/.usages/direct-runner.md` (imported by both command
    cells; created during this design).
- `docker-runner`, `docker-builder`, `docker-image-version`,
  `extra-env-carriage`, `home-profiles-carriage` from `goga/docker` —
  unchanged host-substrate practices, still referenced by the host-path
  annotations.

---

## `.usages/` Update

### Cell: `goga/docker`

#### Existing Files — Consistency
- **`ensure-in-docker.md`** → current (the `is_in_docker` bullet was added
  by the apply stage; matches the contract).

#### New Files
- **direct-runner** → `goga/docker/.usages/direct-runner.md`
  - Reason: new functional domain — the direct-execution substrate
    (`run_direct` consumer guidance: when to use, the argv/env contract,
    lifecycle, constraints, testing note).
  - Related entities: `run_direct`, `is_in_docker`, `DockerRunner`.

### Cell: `goga/config/yaml`

#### New Files
- **env-variables** → `goga/config/yaml/.usages/env-variables.md` —
  created by the apply stage; verified current against the contract.

### Other affected cells

`goga/pipeline/workflow` (assistants.md, parse-workflow.md),
`goga/pipeline/hooks` (checkpoints.md), `goga/pipeline/compiler`
(compile-flow.md), `goga/afm` (run-flow.md), `goga/pipeline`
(pipeline-cli.md, run-pipeline.md), `goga/commands/pipeline`
(pipeline-command.md), `goga/commands/build` (build.md),
`goga/config` (project-configuration.md, tool-configuration.md) — all
updated by the apply stage; verified during this design against the final
contract state (including the `run_direct` routing — the consumer docs
describe the surface behavior "the composed argv and env contract execute
as a child process", which the executor change does not alter). No further
updates needed.

---

## Test Stack Trace

### General Setup

- Tests live under `tests/` mirroring the cell layout (`tests/config/`,
  `tests/docker/`, `tests/pipeline/...`, `tests/commands/...`,
  `tests/afm/`).
- Environment control: `monkeypatch.setenv`/`delenv` for `GOGA_DOCKER` and
  every `!ENV`-referenced variable (never rely on ambient values — the
  practice note).
- Click surfaces: `click.testing.CliRunner`.
- Subprocess fakes: a small `fake_bin` fixture writing a shell/python stub
  onto PATH (for `run_direct`), or `monkeypatch` of
  `goga.docker.runner.subprocess.Popen` where deterministic assertions on
  the spawn matter.
- Workflow/tool fixtures: `tmp_path` project trees (`.goga/config.yml`,
  `.goga/workflows/*.yml`, `.goga/tools/<tool>/*.yml`).

### Source File Registry

- `goga/config/yaml/loader.py`, `goga/config/yaml/__init__.py` (new)
- `goga/config/project/loader.py`, `goga/config/tool/loader.py`
- `goga/docker/env.py`, `goga/docker/runner.py`, `goga/docker/__init__.py`
- `goga/pipeline/workflow/workflow_assistant.py`,
  `goga/pipeline/workflow/parse_workflow.py`
- `goga/pipeline/hooks/overlay.py`
- `goga/pipeline/compiler/compile_flow.py`
- `goga/pipeline/afm_config.py`, `goga/pipeline/cli.py`,
  `goga/pipeline/run_pipeline.py`
- `goga/afm/run_flow.py`
- `goga/commands/pipeline/pipeline.py`,
  `goga/commands/pipeline/run_pipeline_container.py`,
  `goga/commands/pipeline/run_pipeline_info_container.py`
- `goga/commands/build/build.py`

---

### Positive Tests

#### `test_parse_env_yaml_resolves_env_reference`

**Setup**: `monkeypatch.setenv("PIPELINE_AGENT", "claude")`.

**Input**: `"pipeline:\n  agent: !ENV PIPELINE_AGENT\n"`.

**Trace**:
```
parse_env_yaml(text)
  → yaml.load(text, Loader=_EnvLoader)      # entry
    → _construct_env(loader, node)          # node.value == "PIPELINE_AGENT"
      returns: os.environ["PIPELINE_AGENT"] == "claude"
  → returns {"pipeline": {"agent": "claude"}}
```

**Assertions**:
```
result == {"pipeline": {"agent": "claude"}}
isinstance(result["pipeline"]["agent"], str)
```

**Sufficiency**: SC6 core — the tag resolves at load time into a plain
string; regression guard against tag-object leakage into field validators.

---

#### `test_load_project_config_env_agent_unset_resolves_absent`

**Setup**: `tmp_path` with `.goga/config.yml` containing
`language: python\npipeline:\n  agent: !ENV PIPELINE_AGENT\n` and
`monkeypatch.delenv("PIPELINE_AGENT", raising=False)`; chdir to `tmp_path`.

**Input**: `load_project_config()`.

**Trace**:
```
load_project_config()
  → parse_env_yaml(text)          # agent resolves to ""
  → _parse_optional_agent("", "pipeline")
    stripped == "" → returns None
  → ProjectConfig(pipeline=PipelineConfig(agent=None, ...))
```

**Assertions**:
```
config.pipeline.agent is None
```

**Sufficiency**: SC6 — unset variable ⇒ empty string ⇒ the established
absent semantics; the configuration still loads.

---

#### `test_load_tool_config_resolves_env_reference`

**Setup**: `tmp_path` carrying `.goga/tools/ruff/settings.yml` with the
content `threshold: !ENV RUFF_THRESHOLD\n`;
`monkeypatch.setenv("RUFF_THRESHOLD", "85")`.

**Input**: `load_tool_config("ruff", "settings.yml", root=tmp_path)`.

**Trace**:
```
load_tool_config("ruff", "settings.yml", root=tmp_path)
  → flat-segment guard passes → file exists
  → parse_env_yaml(path.read_text(encoding="utf-8"))
    → _construct_env: node.value == "RUFF_THRESHOLD"
      returns os.environ["RUFF_THRESHOLD"] == "85"
  → returns the raw value as-is
```

**Assertions**:
```
result == {"threshold": "85"}
isinstance(result["threshold"], str)
```

**Sufficiency**: the tool-configuration half of SC6 (chain D3's second
consumer) — a regression back to `yaml.safe_load` fails on the unknown
tag, a lost text-read fails on the call shape; the resolved string must
arrive in the raw passthrough value.

---

#### `test_merge_overlay_catalog_entry_overrides_agent_only`

**Setup**: authored workflow with catalog
`assistants: {X: {agent: my-agent}}`; tool contribution with catalog
`assistants: {X: {prompt: tool-prompt, skills: [s1], agent: tool-agent,
delegate: true, env: {K: V}}}`.

**Input**: `merge_workflow_overlay(base, [ToolContribution(tool="t",
document=tool_doc)])`.

**Trace**:
```
merge_workflow_overlay(base, [contribution])
  → _authored_namespace(base) → {"X"}
  → _merge_catalog: winning = {"X": tool_entry(X)}
    merged["X"] = _override_entry(authored X, tool X)
      prompt: None → base "tool-prompt"; skills: None → [s1]
      agent: "my-agent" (authored); delegate: None → True; env: None → {K: V}
  → _merge_stages (no stage attachments)
```

**Assertions**:
```
overlay.workflow.assistants["X"].prompt == "tool-prompt"
overlay.workflow.assistants["X"].skills == ["s1"]
overlay.workflow.assistants["X"].agent == "my-agent"
overlay.workflow.assistants["X"].delegate is True
overlay.workflow.assistants["X"].env == {"K": "V"}
```

**Sufficiency**: SC4 — an entry specifying `agent` overrides it while every
unspecified field flows from the tool (the displacement behavior would
return prompt=None/skills=None and fail these assertions).

---

#### `test_compile_flow_override_entry_with_base_compiles`

**Setup**: effective workflow whose catalog carries the merged entry from
the previous test (or the same base+contribution pair fed through
`merge_workflow_overlay`); a minimal one-stage pipeline document whose
stage attaches `X` as a reference (`{when: checkpoints}`).

**Input**: `compile_flow(...)` with the overlay workflow.

**Trace**:
```
compile_flow(...)
  → _collaboration_emission(workflow, ...)
    → _assistant_namespace → {"X": (entry, "workflow.assistants.X")}
      content check: entry.prompt == "tool-prompt" → passes
    → _assistants_by_id: reference resolves against namespace
  → FlowDocument with collaboration block, team member X, attachment
```

**Assertions**:
```
team contains member id "X" with instruction "tool-prompt"
the stage's assistants list carries profile "goga-X"
```

**Sufficiency**: SC4 end-to-end through compilation; a regression in the
check placement (e.g. checking references) would fail.

---

#### `test_run_flow_appends_exit_on_fail_flag`

**Setup**: `monkeypatch` of `goga.afm.run_flow.subprocess.run` capturing
`cmd`, returning `returncode=0`; a `tmp_path` flow file.

**Input**: `run_flow(path, 5000, max_parallel=2, exit_on_fail=True)`.

**Trace**:
```
run_flow(...)
  cmd = ["afm", "run", "--port", "5000", "--max-parallel", "2",
         "--exit-on-fail", str(path)]
  → subprocess.run(cmd, check=False) → returncode 0
```

**Assertions**:
```
captured_cmd == ["afm", "run", "--port", "5000", "--max-parallel", "2",
                 "--exit-on-fail", str(path)]
```

**Sufficiency**: D5 — the flag rides the argv (visible in the process
listing), never the environment.

---

#### `test_run_flow_omits_exit_on_fail_by_default`

**Setup**: as above.

**Input**: `run_flow(path, 5000)`.

**Trace**: cmd without `--exit-on-fail` → subprocess.run.

**Assertions**: `"--exit-on-fail" not in captured_cmd` and
`"AFM_EXIT_ON_FAIL" not in (captured env or os.environ)`.

**Sufficiency**: R5.3 — without the flag, exit behavior is unchanged.

---

#### `test_write_afm_config_add_stage_disabled`

**Setup**: `tmp_path`; `monkeypatch` of `_AFM_CONFIG_PATH` (module
constant) into `tmp_path`; `flow=None, workflow=None`.

**Input**: `write_afm_config(None)`.

**Trace**:
```
write_afm_config(None)
  → content = {theme: goga, open_browser: False, proxy: {enabled: False},
               prompts_dir: /home/goga/pipeline/prompts,
               add_stage: {enabled: False}, hooks: [goga observer]}
  → yaml.safe_dump → write
```

**Assertions**:
```
parsed["add_stage"] == {"enabled": False}
parsed["theme"] == "goga"            # the four existing statics intact
```

**Sufficiency**: SC7 — the generated config carries the disabled
stage-addition setting unconditionally.

---

#### `test_pipeline_direct_run_spawns_child_and_forwards_flag`

**Setup**: `monkeypatch.setenv("GOGA_DOCKER", "1")`; `tmp_path` project
with a pipeline section in `.goga/config.yml`; `monkeypatch` of
`goga.commands.pipeline.run_pipeline_container` is NOT used — instead
monkeypatch `goga.docker.runner.run_direct`'s spawn (or
`subprocess.Popen`) to capture argv; run through `CliRunner` with
`["deploy", "--fail-on-error"]`.

**Input**: `goga pipeline deploy --fail-on-error` (in-image env).

**Trace**:
```
pipeline(...) → load_project_config (loads, pipeline section present)
  → step 1a: is_in_docker() True; no host-only option passed → no rejection
  → dispatch → run_pipeline_container(..., fail_on_error=True)
    → _allocate_port()
    → direct branch: compose env lines; parse overlay
    → _compose_run_args(..., fail_on_error=True)
      appends "--fail-on-error"
    → run_direct(["python3", "-m", "goga.pipeline", "run", "deploy",
                  "--port", "<p>", "--fail-on-error"], env=overlay)
```

**Assertions**:
```
argv[0:4] == ["python3", "-m", "goga.pipeline", "run"]
"deploy" in argv and "--fail-on-error" in argv
"--topic" not in any composed token; no docker subprocess ran
```

**Sufficiency**: SC1 + SC8 plumbing — the direct path executes the same
composed argv with the flag, no docker CLI touched.

---

#### `test_build_direct_spawns_child_with_env_overlay`

**Setup**: `GOGA_DOCKER=1`; `tmp_path` project with a build section;
monkeypatch the spawn to capture `(argv, env)`; git config absent.

**Input**: `goga build plan.md` via CliRunner (cwd=`tmp_path`).

**Trace**:
```
build(...) → step 1a: direct; no host-only option → proceed
  → config load (build section guard passes)
  → step 14a: compose ladder lines; overlay
  → run_direct(["python3", "-m", "goga.build", "plan.md"], env=overlay)
  → finally: _cleanup_ralphex_in_project(cwd)
```

**Assertions**:
```
argv == ["python3", "-m", "goga.build", "plan.md"]
overlay["GOGA_EXTRA_ENV"] == encode_extra_env([])   # payload line present
not (tmp_path / ".ralphex").exists()                # cleanup ran
```

**Sufficiency**: SC1 (build form) — direct execution with the same env
contract and the project-directory invariant.

---

### Negative Tests

#### `test_parse_env_yaml_empty_argument_is_constructor_error`

**Setup**: none.

**Input**: `"a: !ENV\n"` (empty argument).

**Trace**:
```
parse_env_yaml(text)
  → _construct_env: node.value == "" → raise ConstructorError(..., node.start_mark)
```

**Assertions**:
```
pytest.raises(yaml.YAMLError) — and specifically yaml.constructor.ConstructorError;
"!ENV" or "line" appears in str(exc) (the mark names the position)
```

**Sufficiency**: R3.4 — malformed use is a structural configuration error
through the library's own machinery.

---

#### `test_parse_env_yaml_non_scalar_is_constructor_error`

**Setup**: none.

**Input** (parametrized): `"a: !ENV [x, y]\n"` (a tagged sequence node);
`"a: !ENV {k: v}\n"` (a tagged mapping node).

**Trace**:
```
parse_env_yaml(text)
  → yaml.load(text, Loader=_EnvLoader)
    → composer builds a SequenceNode / MappingNode carrying the !ENV tag
    → _construct_env(loader, node): not isinstance(node, yaml.ScalarNode)
      → raise ConstructorError(None, None, "expected a scalar argument
        in !ENV", node.start_mark)
```

**Assertions**:
```
pytest.raises(yaml.constructor.ConstructorError)
"line" appears in str(exc)          # the mark names the file position
```

**Sufficiency**: R3.4's non-scalar clause — PyYAML dispatches a tagged
non-scalar node to the registered constructor instead of failing on its
own; without the constructor's scalar-node guard the call degrades to a
raw `TypeError: str expected, not list` (verified against PyYAML) that
escapes every `except yaml.YAMLError` handler and surfaces as a
traceback. This test pins the error channel.

---

#### `test_pipeline_direct_rejects_each_host_only_option`

**Setup**: `GOGA_DOCKER=1`; minimal valid project config; CliRunner.

**Input** (parametrized): `deploy -t feat`, `deploy --todo`, `deploy -u`,
`deploy -e K=V`, `deploy --add-host h:1.2.3.4`, `deploy --proxy http://p`.

**Trace**:
```
pipeline(...) → config load → step 1a: is_in_docker() True
  → the passed host-only option → click.ClickException naming the option
  → exit code 1, message on stderr; no port allocation, no spawn
```

**Assertions**:
```
result.exit_code == 1
the option token (e.g. "--add-host") appears in result.stderr
the spawn mock was never called
```

**Sufficiency**: SC2 — each option fails with an error naming it; nothing
is silently ignored (a silent-ignore regression fails the mock assertion).

---

#### `test_build_direct_rejects_host_only_options`

**Setup**: `GOGA_DOCKER=1`; CliRunner; spawn mocked.

**Input** (parametrized): `plan.md -e K=V`, `plan.md --add-host h:ip`,
`plan.md --proxy http://p`, `plan.md -u`.

**Assertions**: `exit_code == 1`; option named in stderr; spawn never
called; rejection happens BEFORE the config load error surface is reached
for a config-less project (ordering: a missing config with `-e` still
reports the host-only error first — assert the host-only message, not the
config message).

**Sufficiency**: SC2 for the build surface; ordering regression guard.

---

#### `test_compile_flow_override_without_base_is_structural_error`

**Setup**: a workflow with catalog `assistants: {Ghost: {agent: a1}}` (no
tool delivery); a one-stage pipeline attaching `Ghost`.

**Input**: `compile_flow(...)`.

**Trace**:
```
compile_flow(...)
  → _assistant_namespace → {"Ghost": (entry, "workflow.assistants.Ghost")}
    content check: prompt None AND skills None
    → StructuralError("assistant Ghost at workflow.assistants.Ghost ...")
```

**Assertions**:
```
pytest.raises(StructuralError); "Ghost" in str(exc)
"workflow.assistants.Ghost" in str(exc)
```

**Sufficiency**: SC5 — an override-style entry naming an undelivered
assistant stops compilation with a readable error naming it (and its site).

---

#### `test_compile_flow_inline_override_without_base_names_stage_site`

**Setup**: a workflow with a stage attachment
`assistants: {Ghost: {when: start, agent: a1}}` and no catalog/no delivery.

**Input**: `compile_flow(...)`.

**Assertions**: `StructuralError` message contains `Ghost` and
`workflow.stages.<stage>.assistants.Ghost`.

**Sufficiency**: SC5's site-naming for the inline authoring surface.

---

#### `test_parse_workflow_rejects_non_bool_delegate`

**Setup**: raw workflow dict with `assistants: {X: {delegate: yes-please,
prompt: p}}`.

**Input**: `parse_workflow(...)`.

**Assertions**: `WorkflowSyntaxError` "non-bool value in
workflow.assistants.X.delegate" — the type rules are untouched by the
relaxation.

**Sufficiency**: guards against over-relaxation (only the content
requirement moved).

---

#### `test_parse_workflow_override_style_inline_counts_for_duplicate_name`

**Setup**: raw workflow mapping with catalog
`assistants: {X: {prompt: p}}`; a stage `s1` carrying
`assistants: {X: {when: start, agent: y}}`.

**Input**: `parse_workflow(...)`.

**Trace**:
```
parse_workflow(...)
  → _build_assistant_catalog: X is a declaration (prompt authored)
  → _validate_assistant_namespace: the inline X passes the FIVE-FIELD
    discriminator (agent is not None) → counts as a declaration
    → "X" already in seen → raise WorkflowSyntaxError
```

**Assertions**:
```
pytest.raises(WorkflowSyntaxError)
"duplicate assistant name: X" in str(exc)
```

**Sufficiency**: pins the declaration-counting change of the five-field
discriminator — one authoring surface owns the name (an override of a
catalog-delivered assistant is authored in the catalog entry, not as a
stage attachment). Under the OLD prompt/skills-only discriminator this
scenario parsed (the inline entry classified as a reference, its `agent`
silently dropped at resolution) — the test fails on any regression back
to that rule.

---

### Edge Case Tests

#### `test_parse_workflow_preserves_explicit_empty_env_and_skills`

**Setup/Input**: catalog
`X: {prompt: p, skills: [], env: {}}`; stage with `env: {}`.

**Trace**: catalog builds `WorkflowAssistant(skills=[], env={})`; the
STAGE env builds `None`.

**Assertions**:
```
catalog["X"].skills == []          # explicit empty — not None
catalog["X"].env == {}             # explicit empty — not None
stage.env is None                  # the stage rule is unchanged
```

**Sufficiency**: the "Model discipline" risk — presence preservation is
what the override semantics key on; the stage/assistant divergence is
pinned.

---

#### `test_parse_workflow_delegate_default_is_none`

**Input**: catalog `X: {prompt: p}`.

**Assertions**: `catalog["X"].delegate is None` (was `False` before).

**Sufficiency**: R2.1 — absent vs explicit-`false` must stay
distinguishable.

---

#### `test_parse_workflow_empty_catalog_entry_parses_as_override_style`

**Input**: catalog `X: {}`.

**Assertions**: parses; `X.prompt is None and X.skills is None`;
`X` present in the namespace (counts for duplicates).

**Sufficiency**: the degenerate override — legal parse, compile-time
content check owns the failure (with no base).

---

#### `test_merge_override_authored_empty_env_clears_tool_env`

**Setup**: authored `X: {agent: a, env: {}}`; tool `X: {prompt: p, env:
{K: V}}`.

**Assertions**:
```
merged["X"].env == {}              # the clear wins
merged["X"].prompt == "p"          # omitted fields flow
```

**Sufficiency**: R2.1 — an explicitly authored empty value is an override,
not an omission (a `None`-normalizing regression returns `{K: V}`).

---

#### `test_merge_override_delegate_false_opts_out_and_none_inherits`

**Setup**: two authored entries over tool `delegate: true`:
`A: {prompt: q, delegate: false}` and `B: {prompt: q}`.

**Assertions**: `merged["A"].delegate is False`;
`merged["B"].delegate is True` (inherited).

**Sufficiency**: the tri-state discipline end to end.

---

#### `test_merge_no_collision_passthrough_verbatim`

**Setup**: authored workflow with a catalog and inline declarations; no
contributions carry those names.

**Assertions**: the merged document's assistants equal the authored ones
object-for-object (`is` comparisons hold where the implementation
reuses instances, or field-equal otherwise); provenance lists the tools.

**Sufficiency**: C8 — non-colliding authoring unchanged.

---

#### `test_merge_inline_override_stays_on_stage`

**Setup**: stage attachment `X: {when: start, agent: my-agent}` (full
inline declaration); tool catalog `X: {prompt: p, skills: [s]}`.

**Assertions**:
```
"X" not in merged.assistants                       # catalog does not own it
merged stage attachments["X"].prompt == "p"        # inherited content
merged stage attachments["X"].when == "start"      # attachment params kept
merged stage attachments["X"].agent == "my-agent"  # override
```

**Sufficiency**: pins the position-preservation decision — the authored
surface owns the landing; prevents a future "move to catalog" regression
silently changing team membership.

---

#### `test_run_direct_forwards_sigterm_and_exits_128_plus_signum`

**Setup**: a child stub `python3 -c "import signal, time;
signal.pause()"` (or a PATH fake recording its own termination);
launch `run_direct([...])` in a subprocess driver that sends SIGTERM to
the launcher process.

**Input**: SIGTERM to the launcher while the child runs.

**Trace**: handler fires → `proc.send_signal(SIGTERM)` → child terminates
→ `SystemExit(143)` unwinds → handlers restored.

**Assertions**: launcher exit code `== 143`; the child process is no
longer running (it received the signal).

**Sufficiency**: the direct substrate's lifecycle contract (the
docker-kill analogue); duplicated-logic regressions (three copies) are
what this shared entity exists to prevent.

---

#### `test_run_direct_env_layer_child_only`

**Setup**: child stub printing `os.environ.get("MARKER")`; env layer
`{"MARKER": "set"}`.

**Assertions**: child stdout contains `set`; the launcher process's own
`os.environ` has no `MARKER` after the call.

**Sufficiency**: the layer applies to the child only (secret-safety and
the run_flow-mirroring contract).

---

#### `test_is_in_docker_branches`

**Input** (parametrized): `GOGA_DOCKER=1` → `True`; unset → `False`;
`GOGA_DOCKER=0` → `False`; `GOGA_DOCKER=yes` → `False`.

**Sufficiency**: the exact marker rule, both branches covered
(C2 — no new heuristics).

---

#### `test_pipeline_cli_fail_on_error_flag_binds_in_both_modes`

**Input**: `["run", "deploy", "--info", "--fail-on-error"]` (card) and
`["run", "deploy", "--port", "5000", "--fail-on-error"]` (run, run_pipeline
mocked).

**Assertions**: the card invocation exits without an argparse error (flag
accepted, inert); the run invocation passes `fail_on_error=True` to
`run_pipeline`.

**Sufficiency**: R5.4 — the flag binds in both modes, takes effect in run
mode only (the same pattern as the workflow/profile/skip flags).

---

#### `test_parse_env_yaml_does_not_leak_tag_into_safe_load`

**Setup**: run `parse_env_yaml("a: !ENV X")` once; then
`yaml.safe_load("a: !ENV X")` in the same process.

**Assertions**: the second call raises (unknown tag) — the constructor is
scoped to the subclass; global loaders unaffected.

**Sufficiency**: the registration constraint (a leak would silently change
every `safe_load` site, including the home config loader).

---

#### `test_home_config_env_tag_still_unsupported`

**Setup**: `~/.goga/config.yml` (via `HOME`/monkeypatched path) containing
`env: !ENV X`.

**Input**: `load_home_config()`.

**Assertions**: raises `yaml.YAMLError` (unknown tag under `safe_load`).

**Sufficiency**: C3 — the home loader stays on plain `safe_load`;
accidental migration would make this pass silently.

---

#### `test_build_direct_dry_run_prints_child_command_and_exits_zero`

**Setup**: `GOGA_DOCKER=1`; `tmp_path` project with a build section; the
spawn monkeypatched to capture calls.

**Input**: `goga build plan.md --dry-run` via CliRunner (cwd=`tmp_path`).

**Trace**:
```
build(...) → step 1a: direct; no host-only option → proceed
  → config load (build section guard passes)
  → step 14a: dry_run → print(shlex.join(["python3", "-m", "goga.build",
    "plan.md", *cli_flags]), file=sys.stderr) → ctx.exit(0)
  → finally: _cleanup_ralphex_in_project(cwd)
```

**Assertions**:
```
result.exit_code == 0
"python3 -m goga.build plan.md" in result.stderr   # the DIRECT line,
                                                    # not a docker run line
the spawn mock was never called
```

**Sufficiency**: the distinct dry-run behavior of the direct path — the
printed line is the direct child command (never the docker run
assembly), and nothing launches; a regression printing the docker form
or actually spawning fails either assertion.

---

#### `test_direct_clean_wipes_before_launch`

**Setup** (parametrized per command): `GOGA_DOCKER=1`; for the build
form — a stale `<tmp_path>/.ralphex/stale` marker file; for the pipeline
form — a stale marker under the in-container AFM_DIR path (the module
constant monkeypatched into `tmp_path`); the spawn monkeypatched to
record the directory contents at call time.

**Input**: `goga build plan.md --clean` / `goga pipeline deploy --clean`.

**Trace**:
```
command → step 1/1a: direct → 14a/12a: clean
  → rmtree-if-exists + mkdir of <cwd>/.ralphex | the in-container AFM_DIR
    (build)                                            (pipeline)
  → compose env lines/argv → run_direct(spawn mock)   # sees the wiped dir
```

**Assertions**:
```
the spawn mock was called                    # the launch happened
the stale marker file does not exist after the run
```

**Sufficiency**: the pre-launch wipe of both direct paths (pipeline
wipes the in-container AFM_DIR mirroring `clean_pipeline_runtime_dir`;
build wipes `<cwd>/.ralphex`); a regression that ignores `--clean` on
the direct substrate leaves the stale marker behind and fails.

---

## Additional Instructions for the Implementation Agent

1. **Implement bottom-up in this order** (each step compiles/lints
   independently): (1) `goga/config/yaml` (loader + `__init__` export);
   (2) `goga/docker` (`is_in_docker`, `run_direct`, `__init__` exports);
   (3) the two config loaders; (4) `WorkflowAssistant` +
   `parse_workflow`; (5) `overlay.py`; (6) `compile_flow`; (7)
   `afm_config`; (8) `run_flow`; (9) `run_pipeline` + `pipeline_cli`;
   (10) the three command-cell direct branches + the `--fail-on-error`
   click option.
2. **The five-field declaration discriminator is one rule in four
   places** — `parse_workflow._is_declaration`,
   `overlay._is_assistant_declaration`,
   `compile_flow._is_assistant_declaration`,
   `afm_config._is_assistant_declaration`. Change all four together;
   their docstrings share the "declaration rule" phrasing — update them
   consistently (an authored `agent`/`delegate`/`env` now also makes a
   stage attachment a declaration).
3. **Do not move merged entries between surfaces** (position
   preservation) — the catalog pass owns authored-catalog merges and
   fresh delivered names; the stage pass owns authored-inline merges.
   The delivered `winning` map (catalog entries of contributions only)
   threads from the catalog pass into the stage pass.
4. **Split the env validators**: `_validate_assistant_env` (assistant
   fields — `{}` preserved) vs `_validate_stage_env` (WorkflowStage env —
   empty equals `None`, unchanged). The same split applies inside
   `_validate_attachment_field` (assistant fields route to the new
   helper).
5. **Direct-path skips are substrate-scoped**: `_check_docker`, the
   `config.image is None` guards, the host runtime-dir machinery
   (pipeline + build), `docker_build_if_not_exist` / `docker_update` /
   `DockerRunner`. Home config STILL loads on the direct path (home.env
   and the carriage bundle are env-contract layers;
   `AFM_DOCKER_FILE_ROOTS` composes from `home.docker.run` tokens as
   always).
6. **One composition, two sinks**: extract `_compose_env_lines` from each
   env-file builder; the direct path parses the lines
   (`line.split("=", 1)` in order — last write wins). Do not re-derive
   the layers independently for the direct path — divergence between the
   surfaces is the defect the contract forbids.
7. **Signals**: on the direct run/build paths, no caller-side D7 handler
   and no env-file exist — `run_direct` owns the handler. The host paths
   keep their D7 invariant verbatim.
8. **`--clean` on the direct paths**: pipeline wipes
   `/home/goga/pipeline` (rmtree-if-exists + mkdir, idempotent); build
   wipes `<cwd>/.ralphex` and still runs `_cleanup_ralphex_in_project`
   in finally on every exit path.
9. **Cleanup of now-dead references**: `goga/config/project/loader.py`
   drops its code-unreferenced `import yaml` after the swap (docstring
   exception names remain); `goga/config/tool/loader.py` likewise.
   `_compose_run_args` and both container signatures gain
   `fail_on_error: bool = False` (default keeps every existing call site
   valid).
10. **Existing tests that assert the OLD semantics will fail by design** —
    update them alongside: `tests/pipeline/workflow/
    test_parse_workflow_assistants.py` (at-least-one errors, delegate
    False, env-empty→None for assistants), `test_workflow_assistant_*
    .py` (delegate default), `tests/pipeline/hooks/
    test_overlay_assistants.py` (displacement semantics), `tests/pipeline/
    compiler/test_compile_flow_collaboration.py` (content check),
    `tests/pipeline/test_afm_config_collaboration.py` (env/delegate
    keying), `tests/afm/*` (run_flow argv), `tests/commands/*` and
    `tests/docker/*` (substrate branches). Do not weaken an assertion to
    make it pass — re-derive it from the contracts.
11. **Verification gate** (project convention): `pytest tests/ -x` green
    and `ruff check goga/` clean; `goga lint` stays at 0 errors and
    `goga schema` shows the two new `goga/config/yaml` edges and the
    `run_direct` additions on both command-cell edges.
12. **The ADR governs wording conflicts**; where this document and the
    ADR differ, the ADR's decision text wins (task Notes).
