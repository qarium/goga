# Plan: `pipeline-settings-calibration`

## Purpose

Implement the five settled decisions of the topic as code and tests: direct
in-container execution of `goga pipeline` / `goga build` (the
`GOGA_DOCKER == "1"` marker branches the launchers between `docker run` and a
child-process `run_direct`, with host-only options rejected by name),
assistant partial overrides (field-level merge over the winning delivered
entry, presence-preserving parse, compile-time content check),
environment-driven configuration scalars (the new `goga/config/yaml` cell's
`parse_env_yaml` resolving `!ENV NAME` at load time for both config loaders),
the governed stage set (`add_stage.enabled false` written unconditionally),
and fail-on-error signaling (`--fail-on-error` threading from the Click
surface through argv to the engine's `--exit-on-fail`).

All 11 CODEMANIFEST contracts and all `.usages/` files are ALREADY applied
and stay read-only — this plan touches code and tests only. The most
important gaps: the `goga/config/yaml` cell does not exist as code,
`is_in_docker` / `run_direct` do not exist, `WorkflowAssistant.delegate`
still defaults to `False`, the overlay still displaces, the compile content
check does not exist, and the fail-on-error chain is absent end to end.

Strategy: implement bottom-up in the design's dependency order (yaml cell →
docker → config loaders → workflow → overlay → compiler → afm_config →
run_flow → run_pipeline/cli → the three command surfaces), one TDD task per
entity group, every task gated by the Mandatory Rules below.

## Mandatory Rules

<!-- Extracted from the project convention `.goga/usages/conventions.md` (the
     `convention` practice wired into every cell of this feature — for working
     with the codebase, organizing the REPL development cycle, debugging and
     testing, and the test infrastructure), the language rules
     (`goga-cell-python`), the ruff configuration (`pyproject.toml`), and the
     repo gates (`.github/workflows/lint.yml`, `.github/workflows/tests.yml`,
     `.githooks/`). These rules are MANDATORY for every task in this plan.
     Where a task restates a rule, the restatement is a reminder, not a
     replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`.
- **Imports**: relative imports for ALL intra-package references inside
  `goga/` (`from .loader import parse_env_yaml` in the new cell's facade,
  `from ..yaml import parse_env_yaml` in the two config loaders,
  `from ...docker import is_in_docker, run_direct` in the command cells);
  absolute imports only for stdlib and third-party (`os`, `signal`,
  `subprocess`, `yaml`). Touched modules mirror the existing cell idiom:
  `from __future__ import annotations` at the top. Exception — tests:
  cross-directory references inside `tests/` use absolute imports rooted at
  the `tests` package.
- **Data models**: stdlib `dataclasses` only (never pydantic). The one model
  change of this feature — `WorkflowAssistant.delegate` — re-types to
  `bool | None = None` (note: the module already carries
  `from __future__ import annotations`; the ruff `UP045` ignore keeps
  `X | None` out of runtime-evaluated dataclass fields — follow the file's
  existing annotation style for the field). `None` means "not authored" ONLY
  (an inheritable value for the overlay merge); an authored `False` is an
  opt-out, an authored empty `skills: []` / `env: {}` is an override that
  clears — never normalize authored empties to `None`.
- **Docstrings**: Google style, MANDATORY for every public function, method,
  and class. First line starts with a capital letter and ends with a period.
  Include `Args` when the function accepts parameters, `Returns` when it
  returns a value, `Raises` when it raises beyond built-in types. Dataclass
  models document every field in the `Args:` block (the CODEMANIFEST field
  descriptions are the source text). Click command callbacks are the
  documented exception (no `Args`/`Returns`/`Raises` — the callbacks of
  `pipeline` and `build` gain only the new flag parameter and the
  substrate-rejection paragraph in their docstrings' hidden `\f` zone or
  body per the existing file idiom).
- **Code formatting**: inside function and method bodies, separate logical
  blocks by ONE blank line (initialization / conditions and loops / data
  preparation / processing / return).
- **Type hints**: mandatory everywhere. Allowed shapes: `str`, `int`, `float`,
  `bool`, `list[T]`, `dict[str, T]`, `T | None`. Forbidden: `*args`,
  `**kwargs`, bare `dict`, bare `list`.
- **Naming**: PascalCase classes, snake_case functions/methods/properties/
  modules; private helpers one leading underscore (`_construct_env`,
  `_EnvLoader`, `_override_entry`, `_compose_env_lines`, `_env_overlay`).
- **Facade**: each cell's `__init__.py` exposes the contract API through
  `__all__`, kept ALPHABETICAL. `goga/config/yaml/__init__.py` is NEW with
  exactly `["parse_env_yaml"]`. `goga/docker/__init__.py` gains
  `is_in_docker` (between `ensure_in_docker` and `profile_carriage_lines`)
  and `run_direct` (after `profile_carriage_lines`).
- **Logging**: stdlib `logging` only (`logger = logging.getLogger(__name__)`).
  This feature adds NO log sites — `run_direct` and `parse_env_yaml` never
  log (env values may carry secrets), and the existing compile WARNING for
  channel-less inline skills now also covers inherited skills without a new
  call site beyond the existing one. Do not add any log point.
- **Dependencies**: nothing new is added to `pyproject.toml` (PyYAML is the
  only external dependency touched, already declared `pyyaml>=6.0`).
- **Error handling**: NO new exception types anywhere. Channels: parse-time
  `WorkflowSyntaxError` (two rules REMOVED), compile-time `StructuralError`
  (one rule ADDED — the content check), the yaml library's own
  `yaml.constructor.ConstructorError` for malformed `!ENV` use, clean CLI
  errors (`click.ClickException` on the host command surface; plain
  `print(..., file=sys.stderr); return 1` inside `pipeline_cli`). Every
  error message string in the tasks below is contract — copy verbatim.

### Test Writing (strictly per `conventions.md`)

- **pytest**; tests mirror the source structure directly:
  `goga/config/yaml/loader.py` → `tests/config/yaml/test_loader.py`,
  `goga/docker/runner.py` → `tests/docker/test_runner.py`, etc. Every test
  directory carries `__init__.py` (create `tests/config/yaml/__init__.py`).
  Local fixtures live in the per-directory `conftest.py`; the existing
  shared `tests/conftest.py` and per-directory conftests are the pattern.
- **Naming**: files `test_<module>[_<kind>].py`; functions
  `test_<what>_<scenario>` (e.g. `test_parse_env_yaml_non_scalar_is_constructor_error`);
  grouping `class Test<Component>:` where the file groups by entity.
- **Coverage**: unit tests for every public function/method/class — main
  scenario plus typical data; edge cases for empty inputs (`None`, `""`,
  `[]`, `{}`), boundary values, invalid types, and expected exceptions via
  `pytest.raises(..., match=...)`. Boundary tables (the six host-only
  rejections of `goga pipeline`, the four of `goga build`, the four
  `GOGA_DOCKER` marker values, the two non-scalar `!ENV` node kinds) use
  `@pytest.mark.parametrize` with every boundary in the table.
- **Mocks**: NO mocks for pure logic — `parse_env_yaml`, `parse_workflow`,
  `merge_workflow_overlay`, `compile_flow` are pure (text/model in, model
  out; `tmp_path` where files are read). File I/O uses `tmp_path`
  exclusively. Subprocesses: `mock.patch`/`monkeypatch` the spawn
  (`subprocess.Popen` / `subprocess.run`) where deterministic assertions on
  the spawn matter; the signal test drives a REAL child stub. Environment:
  `monkeypatch.setenv`/`delenv` for `GOGA_DOCKER` and every `!ENV`-referenced
  variable — never rely on ambient values. Click surfaces:
  `click.testing.CliRunner` with `result.stderr`/`result.stdout` assertions.
- **Integration tests** covering multiple packages go to `tests/integration/`
  (`test_<scenario>.py`).
- **Self-documenting test names, minimal comments**; no
  `pytest.mark.skipif` needed (no external dependencies).
- Test libraries stay in `[project.optional-dependencies].test` (already
  declared: `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0`).
- **Existing tests asserting the OLD semantics fail by design** — update
  them alongside the code, re-deriving each assertion from the contracts;
  NEVER weaken an assertion to make it pass. The affected inventory is
  listed inside each task.

### Linters and Formatters — every development stage, every local commit

- **ruff is the project linter AND formatter**, configured in
  `pyproject.toml` (`target-version = "py310"`, `line-length = 120`, the
  full `select` rule set incl. `I`, `N`, `PT`, `RUF`, `PTH`, `C90`;
  `[tool.ruff.format]` double-quote / LF /
  `skip-magic-trailing-comma = false`). The CI gates
  (`.github/workflows/lint.yml`) run exactly:
  - `.venv/bin/ruff check goga/ tests/`
  - `.venv/bin/ruff format --check goga/ tests/` (run
    `.venv/bin/ruff format goga/ tests/` to fix)
- **No task is complete and NO local commit is made while any gate is red.**
  ralphex runs validation after each task and commits only after it passes —
  every task below ends with the full gate battery green:
  `.venv/bin/pytest tests/ -x`, `.venv/bin/ruff check goga/ tests/`,
  `.venv/bin/ruff format --check goga/ tests/`, plus `goga lint` (bare,
  from the repository root — per-path invocation yields false
  usage-filepath errors) and `goga schema` (must show the two new
  `goga/config/yaml` edges — the two config cells — and the
  `run_direct`/`is_in_docker`/`direct-runner` additions on both
  command-cell → `goga/docker` edges; no cycles).
- **All code executes inside the project virtualenv** (`.venv`, created in
  Task 1 — `python3 -m venv .venv && .venv/bin/pip install -e '.[test]'`);
  the venv is the only environment in which pytest / ruff / the REPL run.
  Python 3.10+ compatibility is enforced by CI
  (`.github/workflows/tests.yml` runs 3.10–3.14).
- **Git policy** (`.githooks/commit-msg`, `.githooks/pre-push`): no
  `Co-Authored-By:` trailers in commit messages.

### REPL Development Cycle — continuous evaluation, hot reload, migration to source

The `convention` practice is bound by every cell's annotations to
"Organizing the REPL development cycle". Every coding task works through an
interactive evaluate → edit → re-evaluate loop in the project virtualenv:

- **Continuous interactive evaluation**: exercise the REAL modules with
  concrete inputs — `.venv/bin/python -c` / `.venv/bin/python -i` feeding
  `"pipeline:\n  agent: !ENV PIPELINE_AGENT\n"` through `parse_env_yaml`,
  driving `run_direct` with a real `python3 -c "import signal, time;
  signal.pause()"` child and a real SIGTERM, parsing authored workflow
  texts with an override-style entry, calling `merge_workflow_overlay` /
  `compile_flow` over constructed documents, invoking the Click commands
  through `CliRunner` with `GOGA_DOCKER=1` — and inspecting the REAL
  outputs and the REAL exception messages. Never reason about behavior you
  have not observed; the PyYAML dispatch behavior (a tagged non-scalar node
  reaching the registered constructor) and the signal exit codes must be
  observed live, not assumed.
- **Hot reloading**: after each edit, re-evaluate in a FRESH process (or
  `importlib.reload`) — never trust stale interpreter state; the loop
  continues until the observed strings and shapes match the contract
  exactly (the error messages in this plan are frozen — evaluate them, do
  not re-derive them).
- **Code migrates to source files**: whatever expression or scenario was
  verified in the REPL is then migrated into the module (implementation) or
  the test file (scenario). The REPL is scratch; the source files and the
  test suite are the deliverable. Nothing verified only interactively stays
  out of the suite, and nothing enters the suite that was not evaluated.
- **The REPL never replaces the TDD gates**: contract tests are still
  written first (expected to fail), logic tests still follow the
  implementation; the REPL shortens the debug loop between them (each
  coding task's Code step embeds its probe).

## Context

### Interaction Diagram (verbatim from the design)

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

### Contract Surface

**Cell `goga/config/yaml`** (manifest `goga/config/yaml/CODEMANIFEST` — NEW
cell, code does not exist yet):

- **Routine: `parse_env_yaml(text: str) -> data: object`** (NEW)
  - Type: function; `location: loader.py` (new file)
  - Facade obligation: importable from `goga.config.yaml` (new
    `__init__.py` with `__all__ = ["parse_env_yaml"]`)
  - Parses a configuration YAML text with environment references resolved:
    every `!ENV NAME` scalar resolves from the process environment at load
    time into a plain string; returns the parsed value as-is (mapping /
    list / scalar — no models, no validation)
  - Requirements: resolved value always a `str` (no coercion); unset
    variable → `""`; malformed use (empty argument, non-scalar node)
    raises the yaml library's `ConstructorError` carrying the node
    position — no custom exception type; registration on the loader
    SUBCLASS only (other `yaml.safe_load` sites unaffected)
  - Constraints: do NOT register the tag on global `yaml.SafeLoader` /
    `yaml.Loader`; do not validate/interpret/normalize content; do not log
    resolved values (secrets)
  - Usages: `convention` (style), `yaml_env` (the constructor mechanism —
    the whole implementation contract)

**Cell `goga/docker`** (manifest `goga/docker/CODEMANIFEST`):

- **Routine: `is_in_docker() -> flag: bool`** (NEW)
  - Type: function; `location: env.py` (beside `ensure_in_docker`)
  - Facade obligation: export from `goga.docker` (add to `__all__`)
  - `True` only when `GOGA_DOCKER` equals `"1"`; `False` for every other
    value including unset. Pure query — no output, no termination, no
    caching; reads no other variable
- **Routine: `run_direct(argv: list[str], env: dict[str, str] | None = None) -> exit_code: int`** (NEW)
  - Type: function; `location: runner.py` (beside `DockerRunner`)
  - Facade obligation: export from `goga.docker`
  - Direct-execution substrate: spawn `argv` (program token first) as a
    child of the current environment, return the child's exit code
    verbatim. Child env = `{**os.environ, **env}` (caller's environment
    never written); SIGTERM/SIGINT handler installed BEFORE the spawn
    forwards the signal to the live child and exits `128 + signum`
    (130/143 — the DockerRunner convention); inherited stdio (streams
    live, byte-identical to the container stream); `finally` restores the
    previous handlers; `Popen` errors (`FileNotFoundError`/`OSError`)
    propagate raw (the caller wraps)
  - Constraints: no docker-CLI check, no image acquisition, no version
    check (those gate the docker substrate only); no env/argv composition
    (the caller owns both — one composition, two substrates); never print
    or log env values
- The `DockerRunner`/`ensure_in_docker`/codec entities are unchanged.

**Cell `goga/config/project`** (manifest `goga/config/project/CODEMANIFEST`):

- **Routine: `load_project_config() -> config: ProjectConfig`** (changed step 2)
  - `location: loader.py`
  - Step 2 becomes: read the file TEXT, then
    `data = parse_env_yaml(text)` (was handle-based `yaml.safe_load(f)` —
    the read becomes `config_path.read_text()`). Empty file parses to
    `None` → the existing `FileNotFoundError` branch preserved;
    `OSError`/`UnicodeDecodeError` propagate as today; `data is None` /
    non-mapping guards unchanged; field validators receive resolved
    strings and apply verbatim (an unset `pipeline.agent: !ENV X` arrives
    as `""` → `_parse_optional_agent` → `None`)
  - Imports gain `parse_env_yaml` + usage `env-variables` from
    `goga/config/yaml`; the code-unreferenced `import yaml` is REMOVED
    (docstring exception names stay); `ProjectConfig` shape unchanged

**Cell `goga/config/tool`** (manifest `goga/config/tool/CODEMANIFEST`):

- **Routine: `load_tool_config(tool: str, filename: str, root: Path | None = None) -> data: object | None`** (changed step 4)
  - `location: loader.py`
  - Present file: `parse_env_yaml(path.read_text(encoding="utf-8"))`
    replaces `yaml.safe_load(...)` — identical call shape; `yaml.YAMLError`
    (incl. constructor errors of malformed `!ENV` use) propagates raw; raw
    passthrough value unchanged; absent file → `None` unchanged; flat
    -segment guard unchanged; the home configuration stays on plain
    `safe_load` (product decision C3)

**Cell `goga/pipeline/workflow`** (manifest
`goga/pipeline/workflow/CODEMANIFEST`):

- **Entity: `WorkflowAssistant`** (changed)
  - `location: workflow_assistant.py`; `delegate: bool | None = None`
    (was `bool = False`)
  - Field order fixed: name, prompt, skills, agent, delegate, env, gate,
    when. Docstrings: `None` = not authored (inheritable via the overlay
    merge), `False` = authored opt-out, `True` = authored permission;
    downstream materializes `False` when effective `None`. `skills` /
    `env` docstrings: authored empty list/map is an explicit override that
    clears
- **Routine: `parse_workflow(text: str) -> workflow: WorkflowDocument`** (changed steps 6.5/6.7)
  - `location: parse_workflow.py`
  - The at-least-one-of-prompt-or-skills raise is DELETED in both
    `_build_assistant_catalog` (6.5) and the inline branch (6.7) — an
    entry carrying none of the five fields (`NAME: {}`) parses as an
    override-style entry with every field `None`
  - `delegate=fields.get("delegate")` (was `fields.get("delegate", False)`)
    in both builders
  - Assistant `env` validates through a presence-preserving helper
    `_validate_assistant_env` — an authored `env: {}` returns `{}` (NOT
    `None`); the per-STAGE `env` keeps `_validate_stage_env`'s
    empty→`None` rule (split helpers; the same split applies inside
    `_validate_attachment_field` — assistant fields route to the new
    helper)
  - `_is_declaration` becomes the FIVE-FIELD presence check:
    `entry.prompt is not None or entry.skills is not None or entry.agent
    is not None or entry.delegate is not None or entry.env is not None` —
    an override-style inline declaration now COUNTS for the
    duplicate-name rule
  - Type rules untouched: non-bool `delegate` still raises
    `"non-bool value in workflow.assistants.X.delegate"`; name grammar /
    reserved name / unknown-key rules unchanged
- All other entities (`WorkflowStage`, `WorkflowDocument`, the profile
  zone) unchanged.

**Cell `goga/pipeline/hooks`** (manifest
`goga/pipeline/hooks/CODEMANIFEST`):

- **Routine: `merge_workflow_overlay(base, contributions) -> overlay: WorkflowOverlay`** (changed step 4a + stage pass)
  - `location: overlay.py`
  - Step 4a (catalog): `winning[name]` = the LAST contribution's catalog
    entry per name (whole entry — later-tool-wins among tools unchanged,
    NOT field-level). Authored catalog entries: `winning` has the name →
    `_override_entry(authored, base)`; otherwise verbatim. Fresh delivered
    names (in `winning`, not in the authored seed) add verbatim,
    first-appearance order. The namespace seeds from authored catalog
    names + authored inline-declaration names (five-field discriminator)
  - Stage pass (`_merge_stage_assistants`, threaded with `winning`): an
    authored entry that IS a declaration and whose name is in `winning`
    is replaced in place with `_override_entry(authored,
    winning[name])` — POSITION PRESERVATION (the authored surface owns
    the landing; the delivered base contributes field values only). The
    tool attachment append loop unchanged
  - `_override_entry(authored, base)` is pure — constructs a fresh
    `WorkflowAssistant`: each of prompt/skills/agent/delegate/env takes
    the authored value when not `None`, else the base value;
    gate/when always authored (attachment params)
  - `_is_assistant_declaration` becomes the five-field check
  - Requirements: pure (inputs never mutated); collision-free workflows
    merge verbatim; each assistant name exactly once across catalog and
    inline declarations
  - Constraint: no partial content merge — prompt and skills replace
    whole (no concatenation, no list union); the field unit is the merge
    unit

**Cell `goga/pipeline/compiler`** (manifest
`goga/pipeline/compiler/CODEMANIFEST`):

- **Routine: `compile_flow(...)`** (changed step 4.10)
  - `location: compile_flow.py`
  - `_assistant_namespace(workflow)` value becomes `(entry, site)` with
    the site string `workflow.assistants.<name>` or
    `workflow.stages.<stage>.assistants.<name>`; the five-field
    discriminator decides which stage attachments join
  - The content check (NEW): for every namespace entry,
    `entry.prompt is None AND entry.skills is None` → raise
    `StructuralError` naming the assistant and its site. A reference
    (gate/when only) is not a namespace member and is never checked
  - `_assistants_by_id` consumes the namespace (unwrapping the entry);
    reference resolution, duplicate guard, script/planning-body checks
    unchanged
  - `_is_assistant_declaration` becomes the five-field check

**Cell `goga/pipeline`** (manifest `goga/pipeline/CODEMANIFEST`):

- **Routine: `write_afm_config(agent, flow, workflow) -> config_path: Path`** (changed)
  - `location: afm_config.py`
  - Static content gains the FIFTH static field
    `"add_stage": {"enabled": False}` — unconditional
  - `_resolve_profiles`: env-key validation and the "declares env but"
    clause of the no-agent error key on a NON-EMPTY effective map
    (`if declaration.env:` — `None` and `{}` both mean "no closure");
    `delegate` materializes `False` when `None`
    (`declaration.delegate if declaration.delegate is not None else
    False`)
  - `_collaboration_section`: closure creation on `if env:` (non-empty)
  - `_is_assistant_declaration` becomes the five-field check
- **Routine: `run_pipeline(...)`** (changed)
  - `location: run_pipeline.py`; signature gains
    `fail_on_error: bool = False` (LAST position, after `parallel`)
  - Step 21 becomes `run_flow(flow_path, port, max_parallel=parallel,
    exit_on_fail=fail_on_error, env=launch_layer)`
- **Routine: `pipeline_cli(argv)`** (changed)
  - `location: cli.py`; the run subparser gains
    `--fail-on-error` (`action="store_true", default=False`) — binds in
    both run and card invocations (inert with `--info`, the same surface
    pattern as `-w/-p/-s`); `_run_execution` passes
    `fail_on_error=args.fail_on_error` into `run_pipeline`

**Cell `goga/afm`** (manifest `goga/afm/CODEMANIFEST`):

- **Routine: `run_flow(flow_path, port, max_parallel=None, exit_on_fail=False, env=None) -> exit_code: int`** (changed)
  - `location: run_flow.py`; signature gains `exit_on_fail: bool = False`
    (between `max_parallel` and `env`)
  - Append `["--exit-on-fail"]` ONLY when `exit_on_fail` is `True`, after
    `--max-parallel`, before the positional; `AFM_EXIT_ON_FAIL` never set
    or read; exit-code propagation verbatim (127/126 arms unchanged)

**Cell `goga/commands/pipeline`** (manifest
`goga/commands/pipeline/CODEMANIFEST`):

- Imports gain `is_in_docker`, `run_direct`, usage `direct-runner` from
  `goga/docker`
- **Entity: `pipeline` (Click)** (changed)
  - `location: pipeline.py`; new `--fail-on-error` click option
    (`is_flag=True, default=False`, placed after `--parallel`; run form
    only in effect, accepted without effect by the listing/card forms);
    forwarded in the run-form dispatch as `fail_on_error=fail_on_error`
  - Step 1a (NEW, after the config load of step 1, before form
    validation): `direct = is_in_docker()`; when `direct`, reject every
    passed host-only option BEFORE any other work — SIX entries:
    `("--topic/-t", topic is not None)`, `("--todo", todo)`,
    `("--update/-u", update)`, `("--env/-e", bool(extra_env))`,
    `("--add-host", bool(add_host))`, `("--proxy", proxy is not None)` —
    each a clean `click.ClickException` naming the option (stderr, exit
    1; no topic procedure, no port allocation, no launch). The host path
    (marker absent) skips step 1a entirely
- **Routine: `run_pipeline_container(...)`** (changed — step 12a)
  - `location: run_pipeline_container.py`; signature gains
    `fail_on_error: bool = False` (last position); `_compose_run_args`
    gains `fail_on_error: bool = False` → appends `--fail-on-error` only
    when True (after `--parallel`)
  - Direct branch (12a): skip `_check_docker`, the `config.image is
    None` guard, the host runtime-dir machinery, the env-file write,
    image acquisition, `DockerRunner`. When `clean`, wipe the
    in-container AFM_DIR (`rmtree`-if-exists + `mkdir` parents). Compose
    the env lines through the SAME composition extracted from
    `_build_env_file` (`_compose_env_lines(...)`), parse them into a
    dict (`KEY=VALUE` split on the first `=`, applied in order — last
    write wins, mirroring `--env-file`), `args =
    _compose_run_args(..., fail_on_error)`, `return
    run_direct(["python3", *args], env=parsed)` — no env-file exists
    (nothing to unlink), no caller-side D7 handler (`run_direct` owns
    signals), `update` unreachable (rejected at 1a). The port is
    allocated on BOTH substrates; home config still loads
- **Routine: `run_pipeline_info_container(...)`** (changed — step 7a)
  - `location: run_pipeline_info_container.py`
  - Direct branch (7a): skip `_check_docker` and the image steps (incl.
    the image-None guard); home config loads; compose the argv via the
    existing `_compose_argv`; the cargo lines (existing
    `_compose_profile_carriage`, only when cargo exists) parse into the
    env layer; `return run_direct(["python3", *argv],
    env=_env_overlay(cargo) if cargo else None)`

**Cell `goga/commands/build`** (manifest
`goga/commands/build/CODEMANIFEST`):

- Imports gain `is_in_docker`, `run_direct`, usage `direct-runner` from
  `goga/docker`
- **Entity: `build` (Click)** (changed — steps 1a / 14a)
  - `location: build.py`
  - Step 1a (NEW, BEFORE the docker-CLI check of step 1): `direct =
    is_in_docker()`; on the direct path reject `extra_env` non-empty,
    `add_host` non-empty, `proxy is not None`, `update is True` — each a
    clean ClickException naming the option; step 1 (docker check)
    skipped entirely on the direct path (rejection precedes config load
    — the contract places 1a before 1)
  - Direct branch (14a): skip the image-None guard, the host ralphex
    runtime-dir steps (`resolve_build_runtime_dir` /
    `clean_build_runtime_dir` — docker-only), the env-file write, the
    docker-run assembly, `docker_build_if_not_exist`,
    `docker_update`, `DockerRunner`. When `clean`, wipe
    `<cwd>/.ralphex` (rmtree missing_ok). Compose the env lines through
    the SAME ladder code the host path writes (extract
    `_compose_env_lines`); parse into the child env layer; `args =
    ["-m", "goga.build", plan, *_cli_flags_to_args(cli_flags)]`; on
    `dry_run` print `shlex.join(["python3", *args])` to stderr and exit
    0; otherwise `run_direct(["python3", *args], env=parsed)`; in
    finally run `_cleanup_ralphex_in_project(Path.cwd())` as on the host
    (both substrates)

### Re-exports

None — no `->Name: {}` blocks in any of the eleven manifests. The new
routine `parse_env_yaml` is surfaced through its own cell facade
(`goga/config/yaml/__init__.py`); `is_in_docker` and `run_direct` through
`goga/docker/__init__.py`.

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — the mandatory project rules
  (code style, test rules, REPL cycle, validation commands). Relevance:
  every task; the Mandatory Rules section above is its extraction.
- `yaml_env` (`.goga/usages/cooks/yaml_env_constructor.md`) — the PyYAML
  scalar-constructor mechanism: the loader subclass, the
  `(loader, node) -> value` contract, `ConstructorError` with mark, the
  no-global-registration constraint, resolve-at-load-time-only.
  Relevance: Task 2 (its entire implementation contract).
- `afm` (`.goga/usages/cooks/afm.md`) — the engine facts consumed
  read-only: the `--exit-on-fail` run flag (v2.0.9; the argv flag over the
  `AFM_EXIT_ON_FAIL` variable) and the `add_stage` config map with the
  nested `enabled` key. Relevance: Task 9 (the field), Task 8 (the flag).
- `click` (`.goga/usages/cooks/click.md`) — the command-surface
  conventions: single command, flag options (`is_flag=True`),
  ClickException wrapping, `ctx.exit` propagation. Relevance: Tasks 11–12
  (the `--fail-on-error` flag, the step-1a rejections).

### Imported Usages

- `env-variables` from `goga/config/yaml` (path
  `goga/config/yaml/.usages/env-variables.md`, imported by both config
  cells) — the consumer-side authoring guide for `!ENV`: where the tag
  applies, the empty-string rule, the home-config exclusion. Relevance:
  Task 4 (both loaders parse through `parse_env_yaml`; no local tag
  handling).
- `direct-runner` from `goga/docker` (path
  `goga/docker/.usages/direct-runner.md`, imported by both command cells)
  — the executor contract for the direct substrate: the caller composes
  argv+env ONCE, the executor spawns/forwards/returns; constraints.
  Relevance: Tasks 11–12 (the three direct branches route through
  `run_direct`).
- `docker-runner`, `docker-builder`, `docker-image-version`,
  `extra-env-carriage`, `home-profiles-carriage` from `goga/docker` —
  unchanged host-substrate practices, still referenced by the host-path
  annotations. Relevance: Tasks 11–12 (the host branches are unchanged;
  do not disturb their practice wiring).

### Local Usages

None to create or update. The apply stage already created
`goga/config/yaml/.usages/env-variables.md` and
`goga/docker/.usages/direct-runner.md` and updated every consumer doc;
the design review verified all of them current against the final contract
state. They are read-only context for this plan, same as the manifests.

### External Dependencies

- PyYAML (`yaml` >= 6.0) — already declared; the `!ENV` constructor rides
  its standard constructor mechanism.
- click (>= 8.0) — the command surfaces (`CliRunner` for tests).
- pytest / pytest-cov / ruff (>= the declared minimums) — the test and
  gate toolchain, installed into `.venv` by Task 1.
- The external `afm` binary (v2.0.9 facts) — consumed read-only through
  argv/config; never installed or invoked by the test suite (spawns are
  mocked).

## Facts

- **Dependency order (bottom-up)**: `goga/config/yaml` →
  `goga/config/project`, `goga/config/tool`, `goga/docker` →
  `goga/pipeline/workflow` → `goga/pipeline/hooks`,
  `goga/pipeline/compiler`, `goga/afm` → `goga/pipeline` →
  `goga/commands/pipeline`, `goga/commands/build`. No import edge changes
  direction; the only new edges are the two config cells →
  `goga/config/yaml` and the `run_direct`/`is_in_docker`/`direct-runner`
  additions on the existing command-cells → `goga/docker` edges.
- **D1 (direct execution)**: the Click command resolves the substrate once
  for the host-only rejection; each launcher resolves it again at its own
  branch point (`is_in_docker` is a pure query — no caching). Both
  substrates share the argv composer and the env-lines composer; the host
  writes the lines to a private env-file consumed by `docker run`, the
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
  `run_flow(exit_on_fail=...)` → engine argv `--exit-on-fail`. Every hop
  forwards only when set (`False` ⇒ no flag).
- **The shared declaration discriminator is one rule in four places** —
  `parse_workflow._is_declaration`, `overlay._is_assistant_declaration`,
  `compile_flow._is_assistant_declaration`,
  `afm_config._is_assistant_declaration` — all become the five-field
  presence check; their docstrings share the "declaration rule" phrasing
  and are updated together.
- **Position preservation**: the authored surface owns the assistant name
  AND its landing position; the delivered base contributes field values
  only. A catalog override becomes a team member with the tool's content;
  an inline override stays stage-attached (inherited skills hit the
  existing compile WARNING channel — documented, not a silent drop).
- **Signals**: `run_direct` forwards SIGTERM/SIGINT to the child and exits
  `128 + signum` — the same convention as `DockerRunner` and the D7
  handlers. No caller-side D7 handler and no env-file exist on the direct
  paths; the host paths keep their D7 invariant verbatim.
- **Engine-as-shipped (C5)**: only shipped capabilities are consumed — the
  `--exit-on-fail` argv flag (never `AFM_EXIT_ON_FAIL`), the `add_stage`
  config map.
- **Home configuration stays on plain `yaml.safe_load`** (product decision
  C3) — a `!ENV` tag there remains an unknown-tag parse error.
- **The ADR governs wording conflicts**; where the design and the ADR
  differ, the ADR's decision text wins.

## Gap Analysis

- **Missing cell code**: `goga/config/yaml/` contains only `CODEMANIFEST` —
  no `loader.py`, no `__init__.py`.
- **Missing routines**: `is_in_docker` (absent from `goga/docker/env.py`
  and the facade), `run_direct` (absent from `goga/docker/runner.py` and
  the facade).
- **API mismatches**:
  `goga/pipeline/workflow/workflow_assistant.py:53` —
  `delegate: bool = False` (contract: `bool | None = None`);
  `goga/afm/run_flow.py:9` — no `exit_on_fail`;
  `goga/pipeline/run_pipeline.py` — no `fail_on_error` (step 21 at line
  ~539 forwards only `max_parallel`);
  `goga/pipeline/cli.py` — no `--fail-on-error` parser argument;
  `goga/commands/pipeline/pipeline.py` — no `--fail-on-error` option, no
  step 1a;
  `goga/commands/pipeline/run_pipeline_container.py:350` —
  `_compose_run_args` without `fail_on_error`, no direct branch;
  `goga/commands/pipeline/run_pipeline_info_container.py` — no direct
  branch; `goga/commands/build/build.py` — no step 1a / 14a.
- **Behavioral mismatches**:
  `goga/config/project/loader.py:769` — `yaml.safe_load(f)` (handle-based;
  contract: text read + `parse_env_yaml`); `goga/config/tool/loader.py:65`
  — `yaml.safe_load(...)`; `parse_workflow.py:1261,1399` — the
  at-least-one raises (to delete); `parse_workflow.py:1270,1408` —
  `fields.get("delegate", False)`; the old prompt/skills-only declaration
  discriminators in all four modules; `overlay.py` — whole-entry
  displacement semantics (no `_override_entry`, no `winning` threading);
  `compile_flow.py:844` — `_assistant_namespace` returns bare entries, no
  content check; `afm_config.py` — four static fields (no `add_stage`),
  env keying `is not None` (line 141), delegate never materialized.
- **Dead references after the swap**: `import yaml` in
  `goga/config/project/loader.py:3` and `goga/config/tool/loader.py:7`
  (ruff would flag the unused import — remove).
- **Test coverage gaps**: all 33 design test scenarios are new; existing
  suites pin the OLD semantics (see the per-task inventories).
- **Environment gap**: no `.venv` exists in the workspace and pytest/ruff
  are installed nowhere — Task 1 bootstraps it.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed
> before starting the next. Within each coding task, contract tests are
> written first (TDD workflow).

### Task 1: Bootstrap the project virtualenv and the gate battery (infrastructure)

The project convention requires all code to execute inside a virtualenv
(".venv", created if missing) — the workspace has none, and pytest/ruff
are installed nowhere. This task creates the environment every later task
runs in and proves the baseline gates pass BEFORE any change, so later
failures are attributable to the feature work.

**Usages relevant to this task:**
- `convention` (`.goga/usages/conventions.md`): "Execute all code within a
  virtualenv environment — create it if missing"; the Validation Commands
  table (`pytest tests/ -x`, `ruff check <src>/`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the virtualenv and install the project with the test extra:
  `python3 -m venv .venv && .venv/bin/pip install -e '.[test]'`
- [x] Verify the toolchain: `.venv/bin/python --version` (3.10+),
  `.venv/bin/pytest --version`, `.venv/bin/ruff --version`
  (Python 3.12.16, pytest 9.2.0, ruff 0.17.3)
- [x] Baseline gate 1: `.venv/bin/pytest tests/ -x` — the full existing
  suite must pass BEFORE any change (report the count)
  (7885 passed, 8 skipped. Two PRE-EXISTING baseline defects repaired,
  both test-infrastructure only, no source change: (1) an autouse
  `_isolate_goga_env` fixture in `tests/conftest.py` clears the ambient
  container carriage vars `GOGA_WORKFLOW`/`GOGA_PROFILE`/`GOGA_EXTRA_ENV`/
  `GOGA_HOME_PROFILES`/`GOGA_DOCKER` — the build cycle test relied on
  ambient values the convention forbids and CI never sets; (2) the
  shipped-workflows guard pinned six files while HEAD deliberately added
  the seventh `worker.yml` — set updated to the real seven)
- [x] Baseline gate 2: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — both clean
  (one pre-existing format defect repaired: `ruff format` on
  `goga/config/yaml/.usages/env-variables.md` — whitespace-only inside an
  example code fence, no contract semantics changed)
- [x] Baseline gate 3: `goga lint` (bare, from the repository root) —
  0 errors; `goga schema` — record the current edge set for the Task-12
  comparison (the two `goga/config/yaml` edges and the
  `run_direct`/`is_in_docker`/`direct-runner` command-edge additions must
  appear only after the code lands — the manifests already declare them,
  so a red schema here means a stale cache, not a code problem)
  (lint: 92 cells, 0 errors — one transient external-URL fetch timeout on
  the first run, clean on retry; schema baseline saved to
  `.ralphex/progress/schema-baseline-task1.json`: both config-cell →
  `goga/config/yaml` edges and the command-cell → `goga/docker` additions
  already declared by the manifests, no cycles)

### Task 2: `goga/config/yaml` — the `parse_env_yaml` routine and the cell facade

New cell code: `goga/config/yaml/loader.py` (the routine) and
`goga/config/yaml/__init__.py` (the facade). The routine is the
environment-aware YAML load of the configuration family: every `!ENV NAME`
scalar resolves to a plain string at load time through a loader-subclass
constructor. Verified algorithm (transfer from the design — implement
exactly):

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

Error channel: `yaml.constructor.ConstructorError` (a `yaml.YAMLError`
subclass) propagates raw, carries the file mark — the consumers' existing
`except yaml.YAMLError` handlers render it. Edge cases: unset variable →
`""`; value containing `=`/`:`/newlines → verbatim string; a scalar `!ENV`
in a mapping-KEY position resolves normally (no position special-casing).
The output is the parsed value as-is — no models, no validation, no
logging of resolved values (secrets). `_EnvLoader` and `_construct_env`
are module-private (leading underscore); only `parse_env_yaml` is the
facade surface.

**Usages relevant to this task:**
- `yaml_env` (`.goga/usages/cooks/yaml_env_constructor.md`): the loader
  subclass, the `(loader, node) -> value` constructor contract,
  `ConstructorError` with mark, the no-global-registration constraint
  (`add_constructor` mutates the class registry — register on the
  subclass ONLY).
- `convention`: Google docstrings, relative imports, the blank-line block
  formatting.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (new `tests/config/yaml/__init__.py` +
  `tests/config/yaml/test_loader.py`): facade accessibility
  (`from goga.config.yaml import parse_env_yaml`;
  `goga.config.yaml.__all__ == ["parse_env_yaml"]`); signature shape
  (`inspect.signature` — one required `text: str` parameter, return
  annotation `object`). Expected to fail at this stage
- [x] **REPL probe (before writing the module — observe, then freeze)**:
  in `.venv/bin/python -c` — (a) confirm PyYAML dispatches a tagged
  non-scalar node to the registered constructor (`"a: !ENV [x, y]"` with
  the guard commented out degrades to a raw `TypeError` — the guard is
  load-bearing); (b) confirm `ConstructorError` is caught by
  `except yaml.YAMLError`; (c) confirm a plain
  `yaml.safe_load("a: !ENV X")` still fails with an unknown tag AFTER a
  `parse_env_yaml` call in the same process (subclass scoping). Migrate
  each observed scenario into the tests below
- [x] **Code**: create `goga/config/yaml/loader.py` — the algorithm above
  (module docstring; `_construct_env`; `_EnvLoader`; `parse_env_yaml`
  with a Google docstring: purpose, `Args` (`text`), `Returns` (`data`),
  `Raises` (`yaml.YAMLError` — the constructor errors of malformed `!ENV`
  use))
- [x] **Code**: create `goga/config/yaml/__init__.py` — the facade with
  `__all__ = ["parse_env_yaml"]` (relative import)
- [x] **Interface verification**: `.venv/bin/pytest tests/config/yaml/ -v`
  — the contract tests pass
- [x] **Logic tests** (positive / negative / edge — in
  `tests/config/yaml/test_loader.py`):
  - `test_parse_env_yaml_resolves_env_reference` —
    `monkeypatch.setenv("PIPELINE_AGENT", "claude")`; input
    `"pipeline:\n  agent: !ENV PIPELINE_AGENT\n"`; assert
    `result == {"pipeline": {"agent": "claude"}}` and
    `isinstance(result["pipeline"]["agent"], str)` (SC6 core; regression
    guard against tag-object leakage into field validators)
  - `test_parse_env_yaml_empty_argument_is_constructor_error` — input
    `"a: !ENV\n"`; `pytest.raises(yaml.constructor.ConstructorError)`;
    `"!ENV"` or `"line"` appears in `str(exc)` (the mark names the
    position) (R3.4)
  - `test_parse_env_yaml_non_scalar_is_constructor_error` —
    `@pytest.mark.parametrize` over `"a: !ENV [x, y]\n"` (tagged sequence)
    and `"a: !ENV {k: v}\n"` (tagged mapping);
    `pytest.raises(yaml.constructor.ConstructorError)`; `"line"` in
    `str(exc)` (pins the error channel — without the scalar-node guard
    this degrades to a raw `TypeError` escaping every
    `except yaml.YAMLError` handler)
  - `test_parse_env_yaml_does_not_leak_tag_into_safe_load` — run
    `parse_env_yaml("a: !ENV X")` once; then
    `yaml.safe_load("a: !ENV X")` in the same process raises (unknown
    tag) — the constructor is scoped to the subclass (a leak would
    silently change every `safe_load` site, including the home config
    loader)
  - unset-variable edge: `monkeypatch.delenv(..., raising=False)` → the
    tagged scalar resolves to `""`
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation
  code until all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: facade importable, `__all__` exact,
  no global-loader registration, no logging of resolved values
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format goga/ tests/` — fix formatting if necessary;
  `goga lint` stays at 0 errors

### Task 3: `goga/docker` — `is_in_docker` and `run_direct`

Two new routines in the docker cell plus the facade exports.
`is_in_docker` (env.py, beside `ensure_in_docker`): the non-terminal
marker query — `os.environ.get("GOGA_DOCKER") == "1"`; exactly the marker
rule `ensure_in_docker` enforces (`!= "1"` refusal there, `== "1"` True
here); no other variable read, no output, no caching. `run_direct`
(runner.py, beside `DockerRunner`): the direct-execution substrate.
Verified algorithm (implement exactly):

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

The forward happens BEFORE the exit so the child terminates (the docker
substrate's `docker kill` analogue); `FileNotFoundError`/`OSError` from
`Popen` propagate raw (the caller wraps; the composed argv starts with
`python3`, present in the image). Edge cases: `env=None` → inherit
unchanged; a signal before `Popen` completes → `proc` is `None`, the
handler exits without a forward; the exit code of a child killed by the
forwarded signal is never returned — the `SystemExit(128 + signum)`
unwind owns that path. Export both from `goga/docker/__init__.py`
(`__all__` alphabetical: `is_in_docker` between `ensure_in_docker` and
`profile_carriage_lines`; `run_direct` after `profile_carriage_lines`).

**Usages relevant to this task:**
- `direct-runner` (`goga/docker/.usages/direct-runner.md` — read-only
  context; the caller-side contract this executor serves): argv carries
  the full child command INCLUDING the program token; env is a mapping
  applied over the inherited environment for the child only; the executor
  never composes argv or env.
- `convention`: docstring style, relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: facade accessibility
  (`from goga.docker import is_in_docker, run_direct`; both present in
  `__all__`); signature shapes (`is_in_docker()` no parameters → `bool`;
  `run_direct(argv: list[str], env: dict[str, str] | None = None) -> int`).
  Expected to fail at this stage
- [x] **REPL probe**: in `.venv/bin/python` — drive `run_direct` with a
  real stub child (`python3 -c "import signal, time; signal.pause()"`);
  send SIGTERM to the launcher from a driver script; observe exit 143 and
  the child's termination; observe `env=None` inheritance vs the
  `{"MARKER": "set"}` layer reaching the child only. Migrate the observed
  scenarios into the tests
- [x] **Code**: implement `is_in_docker` in `goga/docker/env.py` (pure
  query; Google docstring documenting the shared marker rule)
- [x] **Code**: implement `run_direct` in `goga/docker/runner.py`
  (algorithm above; Google docstring: `Args` `argv`/`env`, `Returns`
  `exit_code`, `Raises` — the raw `OSError` propagation note)
- [x] **Code**: export both from `goga/docker/__init__.py` —
  `__all__` alphabetical
- [x] **Interface verification**: `.venv/bin/pytest tests/docker/ -v` —
  the contract tests pass
- [x] **Logic tests**:
  - in `tests/docker/test_env.py`:
    `test_is_in_docker_branches` — `@pytest.mark.parametrize`:
    `GOGA_DOCKER=1` → `True`; unset → `False`; `GOGA_DOCKER=0` → `False`;
    `GOGA_DOCKER=yes` → `False` (the exact marker rule, both branches —
    C2, no new heuristics)
  - in `tests/docker/test_runner.py`:
    `test_run_direct_forwards_sigterm_and_exits_128_plus_signum` — a real
    child stub; SIGTERM to the launcher while the child runs; assert the
    launcher exit code `== 143` and the child process is no longer
    running (it received the signal) (the direct substrate's lifecycle
    contract — the docker-kill analogue)
  - `test_run_direct_env_layer_child_only` — a child stub printing
    `os.environ.get("MARKER")`; env layer `{"MARKER": "set"}`; assert the
    child stdout contains `set` and the launcher process's own
    `os.environ` has no `MARKER` after the call (the layer applies to the
    child only — secret safety and the run_flow-mirroring contract)
  - exit-code verbatim edge: a child stub exiting 7 → `run_direct`
    returns 7
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation
  code until all tests pass
- [x] **Contract re-verification**: facade exports, marker-rule sharing
  with `ensure_in_docker`, no caching, no docker-CLI gates inside
  `run_direct`
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors

### Task 4: The two config loaders parse through `parse_env_yaml`

`goga/config/project/loader.py` (`load_project_config` step 2) and
`goga/config/tool/loader.py` (`load_tool_config` step 4) swap
`yaml.safe_load` for the imported `parse_env_yaml`. Project loader: the
handle-based `yaml.safe_load(f)` at `goga/config/project/loader.py:769`
becomes a text read then `data = parse_env_yaml(text)`
 (`config_path.read_text()`); an empty file parses to `None` → the
existing `FileNotFoundError` branch preserved; `OSError`/
`UnicodeDecodeError` propagate as today; `data is None` / non-mapping
guards unchanged; the code-unreferenced `import yaml` (line 3) is REMOVED
(docstring exception names stay). Tool loader: line 65 becomes
`parse_env_yaml(path.read_text(encoding="utf-8"))` — identical call shape
(the routine already read text); `yaml.YAMLError` propagates raw;
likewise drop the now-dead `import yaml` (line 7). Import via
`from ..yaml import parse_env_yaml`. Field validators receive resolved
strings and apply verbatim — no coercion (`pipeline.agent: !ENV X` with
`X` unset arrives as `""` → `_parse_optional_agent` → `None`; a
non-string field receiving a resolved string fails its own rule). The
HOME configuration loader is explicitly NOT migrated (stays
`yaml.safe_load` — product decision C3).

**Usages relevant to this task:**
- `env-variables` (imported from `goga/config/yaml`, path
  `goga/config/yaml/.usages/env-variables.md`): the consumer-side
  authoring guide — where `!ENV` applies, the empty-string rule, the
  home-config exclusion.
- `convention`: relative imports (`from ..yaml import parse_env_yaml`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: both modules import `parse_env_yaml` from the
  yaml cell; neither module imports `yaml` at code level anymore (assert
  via `inspect`/module attributes — the docstrings keep the exception
  names); `load_project_config()` / `load_tool_config(...)` signatures
  unchanged. Expected to fail at this stage
  (TestLoadConfigEnvParseContract / TestLoadToolConfigEnvParseContract —
  observed red, then green)
- [x] **REPL probe**: in `.venv/bin/python` — build a `tmp_path` project
  with `language: python\npipeline:\n  agent: !ENV PIPELINE_AGENT\n`,
  chdir, call `load_project_config()` with the variable unset and set;
  observe `agent is None` and `"claude"`; observe the `ConstructorError`
  rendering for `"a: !ENV\n"`. Migrate into the tests
  (observed: unset→None, set→"claude" str, malformed→
  yaml.constructor.ConstructorError "expected a variable name in !ENV",
  home safe_load still rejects the tag in-process, tool→{"threshold":
  "85"}; every scenario migrated)
- [x] **Code**: `goga/config/project/loader.py` — text read +
  `parse_env_yaml`; remove `import yaml`
- [x] **Code**: `goga/config/tool/loader.py` — the swap; remove
  `import yaml`
- [x] **Interface verification**: `.venv/bin/pytest tests/config/ -v`
  (784 passed)
- [x] **Logic tests**:
  - in `tests/config/project/test_loader.py`:
    `test_load_project_config_env_agent_unset_resolves_absent` — `tmp_path`
    with `.goga/config.yml` containing
    `language: python\npipeline:\n  agent: !ENV PIPELINE_AGENT\n`;
    `monkeypatch.delenv("PIPELINE_AGENT", raising=False)`; chdir to
    `tmp_path`; `load_project_config()` → `config.pipeline.agent is None`
    (SC6 — unset variable ⇒ empty string ⇒ the established absent
    semantics; the configuration still loads)
  - in `tests/config/tool/test_loader.py`:
    `test_load_tool_config_resolves_env_reference` — `tmp_path` carrying
    `.goga/tools/ruff/settings.yml` with `threshold: !ENV RUFF_THRESHOLD\n`;
    `monkeypatch.setenv("RUFF_THRESHOLD", "85")`;
    `load_tool_config("ruff", "settings.yml", root=tmp_path)` →
    `result == {"threshold": "85"}`,
    `isinstance(result["threshold"], str)` (the tool half of SC6 — a
    regression back to `yaml.safe_load` fails on the unknown tag; the
    resolved string must arrive in the raw passthrough value)
  - in `tests/config/test_home_config.py`:
    `test_home_config_env_tag_still_unsupported` — a monkeypatched home
    `config.yml` containing `env: !ENV X`; `load_home_config()` raises
    `yaml.YAMLError` (unknown tag under `safe_load`) (C3 — accidental
    migration would make this pass silently)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x`
  (7935 passed, 8 skipped — no implementation fix needed beyond the swap)
- [x] **Contract re-verification**: raw passthrough preserved in the tool
  loader; the `FileNotFoundError`/`ValueError` branches intact; the home
  loader untouched
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors
  (ruff check clean; 1037 files formatted; goga lint: 92 cells, 0 errors)

### Task 5: `goga/pipeline/workflow` — presence-preserving assistant parse

Three coordinated changes in the workflow cell: (1) the
`WorkflowAssistant.delegate` model field re-types to `bool | None = None`
with updated field/property docstrings (`None` = not authored /
inheritable; `False` = authored opt-out; `True` = authored permission;
downstream materializes `False` when effective `None`; `skills`/`env`:
authored empty is an explicit override that clears). (2) `parse_workflow`
steps 6.5/6.7: DELETE the "requires at least one of prompt or skills"
raise in BOTH builders (`parse_workflow.py:1261` and `:1399`);
`delegate=fields.get("delegate")` (was `fields.get("delegate", False)`,
lines `:1270` and `:1408`); route assistant `env` validation through a
new presence-preserving `_validate_assistant_env(scope, value)` helper —
non-dict → `"non-mapping env in {scope}"`; non-str key/value → the
existing messages; return the value AS-IS (`{}` stays `{}` — the ONLY
divergence from `_validate_stage_env`, which keeps its empty→`None` rule
for the WorkflowStage env); the same split applies inside
`_validate_attachment_field` (assistant fields route to the new helper).
(3) `_is_declaration` (`parse_workflow.py:1478`) becomes the five-field
presence check:

```
entry.prompt is not None or entry.skills is not None
    or entry.agent is not None or entry.delegate is not None
    or entry.env is not None
```

Rationale (verified): with the presence discipline every authored
declaration key leaves a non-`None` value (authored `null`s are type
errors at parse), so this is exactly the parse-time key-set
discrimination (keys ⊆ {gate, when} ⇔ reference). The old
prompt/skills-only rule misclassifies override-style inline declarations
as references — breaking the duplicate-name walk. Docstrings of the
discriminator share the "declaration rule" phrasing — update
consistently (an authored `agent`/`delegate`/`env` now also makes a stage
attachment a declaration). Edge cases: `NAME: {}` (empty catalog entry)
parses — every field `None`, an override-style declaration joining the
namespace unconditionally; stage-level `env: {}` STILL normalizes to
`None` (the WorkflowStage rule is untouched).

**Usages relevant to this task:**
- `convention`: dataclass rules (`kw_only=True`), docstring style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: `WorkflowAssistant` field defaults — `delegate`
  defaults to `None` (construct with only `name`); field order unchanged
  (name, prompt, skills, agent, delegate, env, gate, when); facade
  importable from `goga.pipeline.workflow`. Expected to fail at this
  stage
  (observed red first — the signature-default pin and the new
  `test_workflow_assistant_delegate_defaults_to_none` — then green)
- [x] **REPL probe**: in `.venv/bin/python` — parse
  `"assistants:\n  x: {}\nstages:\n  s1:\n    prompt: p\n"` and the
  five-field discriminator cases; observe `delegate is None`, preserved
  `skills == []` / `env == {}`, and the stage `env: {} → None` divergence;
  observe `"assistant r requires at least one of prompt or skills"` is
  GONE for `agent`-only entries. Migrate into the tests
  (observed live both before — the at-least-one raises, `delegate False`,
  assistant `env: {} → None` — and after in a fresh process: `x: {}`
  all-`None`, tri-state `None`/`False`, the `{}` vs `None` divergence,
  inline `{when, agent}` under a catalog name → `duplicate assistant name:
  x`, references repeating freely, the non-bool message verbatim; every
  scenario migrated)
- [x] **Code**: `workflow_assistant.py` — the `delegate` re-type +
  docstring updates (field and property annotations per the manifest)
- [x] **Code**: `parse_workflow.py` — delete both at-least-one raises;
  both `fields.get("delegate")`; add `_validate_assistant_env`; route
  `_validate_attachment_field` assistant env through it; the five-field
  `_is_declaration` + docstring
  (the routing lands in `_validate_catalog_field`'s env arm, which
  `_validate_attachment_field` already delegates to for the five shared
  keys — one arm covers both surfaces; the builder/validator docstrings
  re-derived alongside)
- [x] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/workflow/ -v` — the contract tests pass
  (573 passed)
- [x] **Logic tests** (in `tests/pipeline/workflow/
  test_parse_workflow_assistants.py` unless noted):
  - `test_parse_workflow_preserves_explicit_empty_env_and_skills` —
    catalog `X: {prompt: p, skills: [], env: {}}`; a stage with `env: {}`;
    assert `catalog["X"].skills == []` (explicit empty — not `None`),
    `catalog["X"].env == {}`, `stage.env is None` (the stage rule is
    unchanged) (presence preservation is what the override semantics key
    on)
  - `test_parse_workflow_delegate_default_is_none` — catalog
    `X: {prompt: p}` → `catalog["X"].delegate is None` (was `False`
    before) (R2.1 — absent vs explicit-`false` must stay
    distinguishable)
  - `test_parse_workflow_empty_catalog_entry_parses_as_override_style` —
    catalog `X: {}` → parses; `X.prompt is None and X.skills is None`;
    `X` present in the namespace (counts for duplicates) (the degenerate
    override — legal parse, the compile content check owns the failure)
  - `test_parse_workflow_rejects_non_bool_delegate` — raw dict
    `assistants: {X: {delegate: yes-please, prompt: p}}` →
    `WorkflowSyntaxError` `"non-bool value in
    workflow.assistants.X.delegate"` (guards against over-relaxation —
    only the content requirement moved)
  - `test_parse_workflow_override_style_inline_counts_for_duplicate_name`
    — catalog `assistants: {X: {prompt: p}}`; a stage `s1` carrying
    `assistants: {X: {when: start, agent: y}}` →
    `WorkflowSyntaxError` `"duplicate assistant name: X"` (pins the
    five-field discriminator: the inline entry counts as a declaration
    via `agent is not None`; under the OLD rule it parsed as a reference
    and its `agent` was silently dropped)
  (all five added, plus the agent-only parse re-derivation of the removed
  catalog parametrize row)
- [x] **Migrate the affected existing tests** (they pin the OLD semantics
  — re-derive from the contracts, never weaken): in
  `tests/pipeline/workflow/test_parse_workflow_assistants.py` — the
  at-least-one error parametrizations (e.g. the
  `("assistants:\n  r:\n    agent: c\n", "assistant r requires at least
  one of prompt or skills")` row) become override-style PARSE tests;
  delegate-`False`-default assertions flip to `None`. In
  `test_workflow_assistant_contract.py` / `_logic.py` — the
  `delegate=False` default expectations (e.g. `assert entry.delegate is
  False` at line ~374) flip to `is None`; env-empty→`None` expectations
  for ASSISTANT fields flip to `{}` preserved
- [x] **Debugging**: `.venv/bin/pytest tests/ -x`
  (7940 passed, 8 skipped — one implementation fix required beyond the
  cell: `afm_config._resolve_profiles` materializes `delegate` `False`
  when `None` at the delivery boundary — Task 9's contract state — so the
  three collaboration tests constructing assistants without `delegate`
  keep asserting the written `delegate: False`; no test was weakened)
- [x] **Contract re-verification**: the type rules are untouched by the
  relaxation (non-bool delegate, unknown keys, name grammar, reserved
  name); stage env rule unchanged
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors
  (ruff check clean; 1037 files formatted; goga lint: 92 cells, 0 errors)

### Task 6: `goga/pipeline/hooks` — the field-level override merge

`merge_workflow_overlay` (`overlay.py`) gains the override merge. The
changed arms (transfer from the design — implement exactly):

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

The namespace seed (`_authored_namespace`) counts authored catalog names
+ authored inline-declaration names (the five-field
`_is_assistant_declaration` — same rule as Task 5). Design decision —
POSITION PRESERVATION: the authored surface owns the name AND the landing
position; the delivered base contributes field values only. Consequences
(all accepted, documented): a catalog override becomes a team member
carrying the tool's content; an inline override stays stage-attached (the
tool-inherited `skills` hit the pre-existing inline-skills WARNING channel
— documented, not a silent drop). Tool inline declarations under an
authored name stay silently dropped. `_override_entry` never mutates its
inputs. No new errors — the merge never raises. Edge cases: authored
`env: {}` over a tool env map → effective `{}` (a clear) → no closure at
delivery; authored `delegate: false` over tool `true` → `False`; absent
delegate over `true` → `True` (inherit); authored `skills: []` over tool
skills → `[]` (the content check still passes — `skills is not None`); a
tool delivering an override-style entry under a fresh name → verbatim,
content-less (the compile check names it).

**Usages relevant to this task:**
- `convention`: pure-function style, docstring formatting.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: `_override_entry` semantics via the public merge
  (field-level override observable); the merge stays pure (input
  documents unchanged after the call — deep field comparisons).
  Expected to fail at this stage
  (observed red — `test_catalog_override_is_field_level_not_displacement`
  failed on the `is not` identity assertion against the old
  displacement code, then green)
- [x] **REPL probe**: in `.venv/bin/python` — construct the authored
  catalog `{X: {agent: my-agent}}` + a tool contribution catalog
  `{X: {prompt: tool-prompt, skills: [s1], agent: tool-agent, delegate:
  true, env: {K: V}}}`; run `merge_workflow_overlay`; observe every
  merged field; then the `env: {}`-clear and `delegate: false`-opt-out
  cases. Migrate into the tests
  (observed live before — displacement: the authored entry standing
  alone, the catalog stealing an inline name, no field flow — and after
  in a fresh process: prompt/skills/env flow with agent authored,
  inline stays stage-attached, env `{}` clears, delegate
  False/True/inherit, skills `[]` clears; every scenario migrated)
- [x] **Code**: `_override_entry`; the `_merge_catalog` field-override
  arms; thread `winning` into `_merge_stage_assistants` with the
  in-place replacement; the five-field
  `_is_assistant_declaration` + docstring
  (`_merge_catalog` returns `(merged, winning)`; `winning` threads
  `merge_workflow_overlay` → `_merge_stages` → `_merge_stage` →
  `_merge_stage_assistants`)
- [x] **Interface verification**: `.venv/bin/pytest tests/pipeline/hooks/
  -v`
  (122 passed)
- [x] **Logic tests** (in `tests/pipeline/hooks/test_overlay_assistants.py`):
  - `test_merge_overlay_catalog_entry_overrides_agent_only` — authored
    catalog `assistants: {X: {agent: my-agent}}`; tool contribution with
    catalog `assistants: {X: {prompt: tool-prompt, skills: [s1], agent:
    tool-agent, delegate: true, env: {K: V}}}`;
    `merge_workflow_overlay(base, [ToolContribution(tool="t",
    document=tool_doc)])` →
    `overlay.workflow.assistants["X"].prompt == "tool-prompt"`,
    `.skills == ["s1"]`, `.agent == "my-agent"` (authored),
    `.delegate is True` (inherited), `.env == {"K": "V"}` (SC4 — the
    displacement behavior would return `prompt=None`/`skills=None` and
    fail)
  - `test_merge_override_authored_empty_env_clears_tool_env` — authored
    `X: {agent: a, env: {}}`; tool `X: {prompt: p, env: {K: V}}` →
    `merged["X"].env == {}` (the clear wins) and
    `merged["X"].prompt == "p"` (omitted fields flow) (R2.1)
  - `test_merge_override_delegate_false_opts_out_and_none_inherits` —
    two authored entries over tool `delegate: true`:
    `A: {prompt: q, delegate: false}` and `B: {prompt: q}` →
    `merged["A"].delegate is False`; `merged["B"].delegate is True`
    (the tri-state discipline end to end)
  - `test_merge_no_collision_passthrough_verbatim` — an authored
    workflow with a catalog and inline declarations; no contributions
    carry those names → the merged document's assistants equal the
    authored ones (field-equal; `is` comparisons where instances are
    reused); provenance lists the tools (C8 — non-colliding authoring
    unchanged)
  - `test_merge_inline_override_stays_on_stage` — a stage attachment
    `X: {when: start, agent: my-agent}` (full inline declaration); tool
    catalog `X: {prompt: p, skills: [s]}` →
    `"X" not in merged.assistants` (the catalog does not own it),
    `merged stage attachments["X"].prompt == "p"` (inherited content),
    `.when == "start"` (attachment params kept),
    `.agent == "my-agent"` (override) (pins position preservation —
    prevents a future "move to catalog" regression silently changing
    team membership)
- [x] **Migrate the affected existing tests**: in
  `tests/pipeline/hooks/test_overlay_assistants.py` — the
  displacement-semantics expectations (same-name tool entries replacing
  authored entries wholesale) re-derive to the field-level override
  outcomes; the namespace-seed expectations now count override-style
  inline declarations
  (`test_overlay_catalog_merge_later_tool_wins_and_namespace_drop`
  re-derived as `..._authored_fields_win_fresh_names_later_tool` (the
  authored prompt wins, the agent flows from the WINNING later tool's
  whole entry); `_declaration_names` helper flipped to the five-field
  rule; no assertion weakened)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x`
  (7947 passed, 8 skipped — one transient external-URL fetch timeout in
  `tests/ast/test_ast_integration.py::test_ast_rules` on the first run,
  37/37 green on retry, the same flake Task 1 documented; no
  implementation fix needed)
- [x] **Contract re-verification**: purity (no input mutation), the
  namespace-once invariant, verbatim passthrough for collision-free
  workflows, no content-field partial merge
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors
  (ruff check clean; 1037 files formatted — 2 reformatted; goga lint:
  92 cells, 0 errors; `goga schema` exit 0, both `goga/config/yaml`
  edges and both command-cell → `goga/docker` edges present, no cycles —
  this task adds no cell edges)

### Task 7: `goga/pipeline/compiler` — the effective-content check

`compile_flow` (`compile_flow.py`) step 4.10 gains the content check over
the namespace. Algorithm delta (implement exactly):

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

`_assistant_namespace` (`compile_flow.py:844`) returns `(entry, site)`
pairs; the five-field `_is_assistant_declaration` (line `:828`) decides
which stage attachments join. `_assistants_by_id` consumes the namespace
unwrapping the entry; reference resolution, the duplicate guard, the
script/planning-body checks unchanged. An override-style entry WITH a
delivered base carries the base's prompt/skills after the overlay merge,
so the check passes exactly when content resolved (SC5); a reference
(gate/when only) is not a namespace member and is never checked. The
existing inline-declaration skills WARNING now also covers inherited
skills (no new log site — the same warning fires for the resolved source
being an inline declaration authoring skills).

**Usages relevant to this task:**
- `convention`: docstring style, the exception-channel rules.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: the check raises `StructuralError` (a
  `ValueError` subclass) through the public `compile_flow` surface.
  Expected to fail at this stage
  (observed red first — `DID NOT RAISE StructuralError` on the
  `Ghost: {agent: a1}` catalog compile — then green)
- [x] **REPL probe**: in `.venv/bin/python` — compile a workflow whose
  catalog carries `Ghost: {agent: a1}` with no delivery; observe the
  exact error string (both message fragments); then feed the same pair
  through `merge_workflow_overlay` first and observe the check pass.
  Migrate into the tests
  (observed live: `"assistant Ghost at workflow.assistants.Ghost
  resolves neither prompt nor skills"` and the inline twin naming
  `workflow.stages.build.assistants.Ghost`; the merged pair compiles —
  team id `X` instruction `tool-prompt`, stage profile `goga-X`; every
  scenario migrated)
- [x] **Code**: `_assistant_namespace` → `(entry, site)` values; the
  content-check loop before `_assistants_by_id`; the five-field
  `_is_assistant_declaration` + docstring; unwrap at the
  `_assistants_by_id` boundary
  (the unwrap lands in `_collaboration_emission`, which now computes the
  namespace once, runs the check over the `(entry, site)` pairs, and
  passes the unwrapped declarations map into `_assistants_by_id`; the
  emission docstring gains the `Raises` arm)
- [x] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/compiler/ -v`
  (623 passed)
- [x] **Logic tests** (in
  `tests/pipeline/compiler/test_compile_flow_collaboration.py`):
  - `test_compile_flow_override_entry_with_base_compiles` — an effective
    workflow whose catalog carries the merged entry of a
    base+contribution override pair (authored `{agent: my-agent}` over
    tool `{prompt: tool-prompt, skills: [s1], ...}` fed through
    `merge_workflow_overlay`); a minimal one-stage pipeline whose stage
    attaches `X` as a reference (`{when: checkpoints}`); `compile_flow`
    → the flow's team contains member id `X` with instruction
    `"tool-prompt"`; the stage's assistants list carries profile
    `"goga-X"` (SC4 end-to-end; a regression checking references would
    fail)
  - `test_compile_flow_override_without_base_is_structural_error` — a
    workflow with catalog `assistants: {Ghost: {agent: a1}}` (no tool
    delivery); a one-stage pipeline attaching `Ghost`;
    `pytest.raises(StructuralError)`; `"Ghost" in str(exc)` and
    `"workflow.assistants.Ghost" in str(exc)` (SC5 — an override-style
    entry naming an undelivered assistant stops compilation with a
    readable error naming it and its site)
  - `test_compile_flow_inline_override_without_base_names_stage_site` —
    a workflow with a stage attachment
    `assistants: {Ghost: {when: start, agent: a1}}` and no catalog/no
    delivery → `StructuralError` message contains `Ghost` and
    `workflow.stages.<stage>.assistants.Ghost` (SC5's site-naming for
    the inline authoring surface)
  (all three added in `TestEffectiveContentCheck`, the verbatim message
  pinned via `match=re.escape` plus the two fragment asserts; the
  contract test lives in `TestCompileFlowCollaborationContract`)
- [x] **Migrate the affected existing tests**: in
  `tests/pipeline/compiler/test_compile_flow_collaboration.py` — any
  scenario asserting a content-less catalog/inline entry parses through
  compilation now expects `StructuralError`; namespace-shape helpers in
  the suite unwrap `(entry, site)`
  (the inventory came out EMPTY: no test compiled a content-less entry
  (unparseable before Task 5) and no suite helper touches
  `_assistant_namespace` (its only test reference is the
  not-on-facade assertion) — the full battery stayed green with zero
  test edits beyond the additions)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x`
  (7951 passed, 8 skipped — no implementation fix needed beyond the
  planned delta)
- [x] **Contract re-verification**: "a workflow without same-name
  collisions compiles exactly as the same workflow carrying no override
  entries"; the error channel renders clean in `pipeline_cli` / the
  Click wrapper
  (the golden-output and shipped-pipeline suites stayed green —
  byte-identical compilation for collision-free workflows; the error
  renders through the existing `except StructuralError` arm of
  `pipeline_cli` and the `except ValueError` arm of the Click wrapper —
  `StructuralError` subclasses `ValueError`)
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors
  (ruff check clean; 1037 files formatted — the new test block
  reformatted once; goga lint: 92 cells, 0 errors)

### Task 8: `goga/afm` — `run_flow` gains `exit_on_fail`

`run_flow` (`run_flow.py:9`) gains `exit_on_fail: bool = False` between
`max_parallel` and `env`. Algorithm delta (implement exactly):

```
cmd = ["afm", "run", "--port", str(port)]
IF max_parallel is not None: cmd += ["--max-parallel", str(max_parallel)]
IF exit_on_fail:            cmd += ["--exit-on-fail"]
cmd.append(str(flow_path))
```

`AFM_EXIT_ON_FAIL` is never read or set anywhere. The spawn mechanics,
the env layer, and the 127/126 arms are unchanged; with the flag, a
failed stage surfaces as the engine's exit 1 returned verbatim (SC8 — no
new exit machinery). Docstring gains the `exit_on_fail` Arg (the
engine's explicit `--exit-on-fail` flag; an argv flag — visible in the
process listing — never the `AFM_EXIT_ON_FAIL` environment variable).

**Usages relevant to this task:**
- `afm` (`.goga/usages/cooks/afm.md`): the `--exit-on-fail` run flag —
  argv flag over the env variable (the single channel).
- `convention`: docstring style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: signature shape — `exit_on_fail` present with
  default `False`, positioned after `max_parallel`, before `env`.
  Expected to fail at this stage
  (observed red first — the signature pin failed with `At index 3 diff:
  'env' != 'exit_on_fail'` — then green)
- [x] **REPL probe**: in `.venv/bin/python` — monkeypatch
  `goga.afm.run_flow.subprocess.run` capturing `cmd`; call both variants;
  observe the exact argv lists. Migrate into the tests
  (observed live: with the flag
  `[afm, run, --port, 5000, --max-parallel, 2, --exit-on-fail, <path>]`,
  default `[afm, run, --port, 5000, <path>]`, flag-without-parallel
  `[afm, run, --port, 5000, --exit-on-fail, <path>]`, explicit `False`
  omits, engine exit 1 propagates verbatim, `AFM_EXIT_ON_FAIL` never in
  `os.environ`; every scenario migrated)
- [x] **Code**: the parameter + the conditional append + the docstring
  Arg
- [x] **Interface verification**: `.venv/bin/pytest tests/afm/ -v`
  (22 passed)
- [x] **Logic tests** (in `tests/afm/test_run_flow.py`):
  - `test_run_flow_appends_exit_on_fail_flag` — `monkeypatch` of
    `goga.afm.run_flow.subprocess.run` capturing `cmd`, returning
    `returncode=0`; a `tmp_path` flow file;
    `run_flow(path, 5000, max_parallel=2, exit_on_fail=True)` →
    `captured_cmd == ["afm", "run", "--port", "5000", "--max-parallel",
    "2", "--exit-on-fail", str(path)]` (D5 — the flag rides the argv,
    never the environment)
  - `test_run_flow_omits_exit_on_fail_by_default` — as above with
    `run_flow(path, 5000)` → `"--exit-on-fail" not in captured_cmd` and
    `"AFM_EXIT_ON_FAIL" not in (the captured env or os.environ)` (R5.3 —
    without the flag, exit behavior is unchanged)
  (both added, plus the flag-without-parallel, explicit-`False`, and
  engine-exit-1-propagation edges)
- [x] **Migrate the affected existing tests**: in
  `tests/afm/test_run_flow.py` — argv-order expectations that append the
  positional right after `--max-parallel` gain the conditional flag slot
  (only-when-True); no assertion is weakened
  (the signature contract pin re-derived to the five-parameter shape with
  the `exit_on_fail` position/default/annotation asserts; the existing
  exact-argv expectations stay as the omitted-flag slot — none pass
  `exit_on_fail`; the only source caller `run_pipeline.py:539` uses
  keyword args and stays valid)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x`
  (7957 passed, 8 skipped — one transient external-URL fetch timeout in
  `tests/ast/test_ast_integration.py` on the first run, green on retry,
  the same flake Tasks 1 and 6 documented; no implementation fix needed)
- [x] **Contract re-verification**: flag order matches the contract
  step 3; exit-code propagation verbatim
  (`--exit-on-fail` after `--max-parallel`, before the positional —
  pinned by exact-list asserts; `AFM_EXIT_ON_FAIL` absent from every
  goga/ and tests/ code path — the docstring wording only)
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors
  (ruff check clean; 1037 files formatted — one new-test def line
  collapsed; goga lint: 92 cells, 0 errors)

### Task 9: `goga/pipeline` — `write_afm_config` (add_stage, env keying, delegate materialization)

Three deltas in `afm_config.py`: (1) the static content dict
(`afm_config.py:308-311`) gains the fifth static field
`"add_stage": {"enabled": False}` — unconditional, serialized via the
existing `yaml.safe_dump` (SC7). (2) `_resolve_profiles`: the env-key
validation and the "declares env but" clause of the no-agent error
(line `:141`, `:151`) key on a NON-EMPTY effective map
(`if declaration.env:` — `None` and `{}` both mean "no closure");
`delegate` materializes `False` when `None`
(`declaration.delegate if declaration.delegate is not None else False`) —
the model's tri-state collapses to the engine's bool exactly once, at
the delivery boundary. (3) `_collaboration_section`: closure creation on
`if env:` (non-empty, line `:235`); the profile dict `{title, command,
delegate}` carries the materialized delegate. Also:
`_is_assistant_declaration` (`afm_config.py:38`) becomes the five-field
check (the fourth copy of the shared rule).

**Usages relevant to this task:**
- `afm` (`.goga/usages/cooks/afm.md`): the `add_stage` config map with
  the nested `enabled` key — the engine field this task writes.
- `convention`: docstring style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: the written config parses as YAML and carries
  the five static fields; the profile dict shape `{title, command,
  delegate}` unchanged. Expected to fail at this stage
  (observed red first — `KeyError: 'add_stage'` on the five-statics
  parse — then green; the profile-shape pin
  (`test_generated_profile_shape_is_exactly_title_command_delegate`)
  passed throughout: the shape is unchanged)
- [x] **REPL probe**: in `.venv/bin/python` — monkeypatch
  `_AFM_CONFIG_PATH` into a scratch dir; call `write_afm_config(None)`;
  `yaml.safe_load` the result; observe `add_stage` beside the four
  existing statics. Migrate into the tests
  (observed live before — four statics, no `add_stage`; the nested map
  round-trips `enabled: false → False` through the same `safe_dump` —
  and after in a fresh process: five statics, `env: {}` over a codex
  agent leaves no closure and the wrapper command, the no-agent message
  for `env: {}` carries no "declares env but" clause, delegate
  None/True/False → False/True/False; every scenario migrated)
- [x] **Code**: the fifth static field; the non-empty env keying
  (validation + no-agent clause + closure creation); the delegate
  materialization; the five-field `_is_assistant_declaration` + docstring
  (the delegate materialization already landed with Task 5's delivery
  boundary fix — verified in place; the fourth discriminator copy shares
  the compile_flow/overlay docstring phrasing; the `write_afm_config` /
  `_resolve_profiles` / `_collaboration_section` docstrings re-derived:
  five statics, non-empty env maps)
- [x] **Interface verification**: `.venv/bin/pytest tests/pipeline/
  test_afm_config*.py -v`
  (32 passed)
- [x] **Logic tests** (in `tests/pipeline/test_afm_config_collaboration.py`):
  - `test_write_afm_config_add_stage_disabled` — `tmp_path`;
    `monkeypatch` of the `_AFM_CONFIG_PATH` module constant into
    `tmp_path`; `write_afm_config(None)` with `flow=None,
    workflow=None`; read back and parse →
    `parsed["add_stage"] == {"enabled": False}` and
    `parsed["theme"] == "goga"` (the four existing statics intact) (SC7 —
    the generated config carries the disabled stage-addition setting
    unconditionally)
  - env-keying edges: a declaration with `env={}` over a resolvable
    agent → NO closure file, no env-key validation error; a declaration
    with `env={"K": "V"}` → the closure exists (non-empty keying)
  - delegate materialization: effective `None` → the written profile
    carries `delegate: False`; authored `True` → `True`; authored
    `False` → `False`
  (all four added: `test_write_afm_config_add_stage_disabled`,
  `test_afm_config_env_delivery_keys_on_nonempty_map` (the `env: {}`
  clear and the `env: {"K": "V"}` closure in one contrast),
  `test_afm_config_empty_env_no_agent_error_without_clause`,
  `test_afm_config_delegate_materializes_false_when_none`)
- [x] **Migrate the affected existing tests**: in
  `tests/pipeline/test_afm_config_collaboration.py` (and
  `test_afm_config.py` where relevant) — env-declaring expectations
  keyed on `is not None` re-derive to the non-empty keying; delegate
  expectations re-derive to the materialized values
  (the three static-set assertions in `tests/pipeline/test_afm_config.py`
  gain `add_stage` — the full-document equality of the with-agent test
  and both `set(data)` pins; the collaboration suite needed no edit: its
  env-declaring scenarios already use non-empty maps and its delegate
  expectations were re-derived to the materialized values with Task 5's
  boundary fix; no assertion weakened)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x`
  (7963 passed, 8 skipped — no implementation fix needed beyond the
  planned delta)
- [x] **Contract re-verification**: the five statics are constants (never
  configurable); the file lands only at the fixed path; profiles exactly
  for the referenced ids
  (the five statics are literals inside `write_afm_config`; the file
  lands only at `_AFM_CONFIG_PATH`; profiles-exactly-for-referenced-ids
  pinned by the existing `test_afm_config_profiles_exactly_for_referenced_ids`;
  namespace parity with the compiler's five-field rule observed live — an
  agent-only inline entry joins at its stage site in both modules, a
  gate/when reference joins in neither)
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors
  (ruff check clean; 1037 files formatted — none changed; goga lint: 92
  cells, 0 errors — one transient external-URL fetch timeout on the
  first run, clean on retry and stable on a third run, the same flake
  Tasks 1, 6, and 8 documented)

### Task 10: `goga/pipeline` — `run_pipeline` + `pipeline_cli` thread `fail_on_error`

The in-container half of the D5 chain. `pipeline_cli` (`cli.py`): the run
subparser gains `--fail-on-error`
(`run_parser.add_argument("--fail-on-error", action="store_true",
default=False, help="exit non-zero when a stage fails (threads to afm
--exit-on-fail; run mode only)")`) — it parses in both run and card
invocations (`run NAME --info --fail-on-error` is legal and inert — the
same surface pattern as `-w/-p/-s`); `_run_execution` passes
`fail_on_error=args.fail_on_error` into `run_pipeline` (beside
`parallel=args.parallel`). `run_pipeline` (`run_pipeline.py`): signature
gains `fail_on_error: bool = False` (LAST position, after `parallel`);
step 21 (line `:539`) becomes `run_flow(flow_path, port,
max_parallel=parallel, exit_on_fail=fail_on_error, env=launch_layer)`.
Docstrings gain the parameter descriptions per the manifest.

**Usages relevant to this task:**
- `convention`: docstring style, the argparse idioms of the file.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: `run_pipeline` signature — `fail_on_error`
  last, default `False`; the parser accepts `--fail-on-error` (no
  argparse error) in both modes. Expected to fail at this stage
- [ ] **REPL probe**: in `.venv/bin/python` — invoke
  `pipeline_cli(["run", "x", "--info", "--fail-on-error"])` (fixture
  project) and observe exit without an argparse error; invoke the run
  mode with `run_pipeline` mocked and capture the forwarded kwargs.
  Migrate into the tests
- [ ] **Code**: the argparse argument + help text; the
  `_run_execution` forward; the `run_pipeline` parameter + step-21
  forward + docstring
- [ ] **Interface verification**: `.venv/bin/pytest
  tests/pipeline/test_pipeline_cli.py tests/pipeline/test_run_pipeline.py
  -v`
- [ ] **Logic tests**:
  - in `tests/pipeline/test_pipeline_cli.py`:
    `test_pipeline_cli_fail_on_error_flag_binds_in_both_modes` — the card
    invocation `["run", "deploy", "--info", "--fail-on-error"]` exits
    without an argparse error (flag accepted, inert); the run invocation
    `["run", "deploy", "--port", "5000", "--fail-on-error"]` (with
    `run_pipeline` mocked) passes `fail_on_error=True` (R5.4 — binds in
    both modes, takes effect in run mode only)
  - in `tests/pipeline/test_run_pipeline.py`: the run coordination
    forwards `exit_on_fail=True` to `run_flow` when
    `fail_on_error=True` (mock `run_flow`, capture the call) and omits
    it (`False`) by default
- [ ] **Migrate the affected existing tests**: argv/composition
  expectations in `tests/pipeline/test_pipeline_cli.py` and
  `test_run_pipeline*.py` that pin the old call shapes gain the new
  default-valued parameter (existing call sites stay valid — the default
  keeps them so)
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x`
- [ ] **Contract re-verification**: every hop forwards only when set
  (`False` ⇒ no flag); the step-22 status recompute unchanged
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors

### Task 11: `goga/commands/pipeline` — the direct substrate on all three surfaces

The command cell consumes `is_in_docker` / `run_direct` (import via
`from ...docker import is_in_docker, run_direct`). Three coordinated
changes:

**(a) `pipeline.py` (Click)** — the `--fail-on-error` click option
(`is_flag=True, default=False`, placed after `--parallel`, help per the
existing option idiom — run mode only, threads to the engine's
`--exit-on-fail`); forwarded in the run-form dispatch as
`fail_on_error=fail_on_error` (the listing/card dispatches unchanged —
the flag is accepted without effect there). Step 1a (NEW — after the
config load of step 1, before form validation):

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

The SIX-entry list is exhaustive (SC2). The host path (marker absent)
skips step 1a entirely — the host behavior is untouched (C1).

**(b) `run_pipeline_container.py`** — signature gains
`fail_on_error: bool = False` (last); `_compose_run_args` gains
`fail_on_error: bool = False` → appends `--fail-on-error` only when True
(after `--parallel`). Extract the env-line composition from
`_build_env_file` into `_compose_env_lines(...) -> list[str]` (home.env
base, git identity, raw CLI lines, the engine lines with the skip rule —
AFM_DIR, AFM_DOCKER_FILE_ROOTS, the proxy triple, GOGA_EXTRA_ENV,
GOGA_PROFILE, GOGA_HOME_PROFILES, GOGA_WORKFLOW — same encoders, same
skip rules); `_build_env_file` becomes a thin wrapper (compose lines →
write). Add `_env_overlay(lines) -> dict[str, str]`
(`dict(line.split("=", 1) for line in lines)` — order-preserving last
write wins, mirroring `--env-file`). Direct branch (12a):

```
IF is_in_docker():
    IF clean: wipe /home/goga/pipeline (rmtree-if-exists + mkdir parents)
    lines = _compose_env_lines(...)
    args = _compose_run_args(..., fail_on_error)
    return run_direct(["python3", *args], env=_env_overlay(lines))
# else the unchanged host path
```

Substrate-scoped skips on the direct path: `_check_docker`, the
`config.image is None` guard, the host runtime-dir machinery, image
acquisition, `DockerRunner`. `_allocate_port()` runs on BOTH substrates
(the port is part of the composed contract). Home config still loads.
`update` is unreachable (rejected at 1a). No env-file, no caller-side D7
handler.

**(c) `run_pipeline_info_container.py`** — direct branch (7a):

```
IF is_in_docker():
    cargo = _compose_profile_carriage(home_profiles)      # existing helper
    return run_direct(["python3", *_compose_argv(...)],
                      env=_env_overlay(cargo) if cargo else None)
```

Skip `_check_docker` and the image steps (incl. the image-None guard —
substrate-scoped); home config loads (cargo composition needs the
bundle only). Minimal read-only shape on both substrates — no port, no
persistent state, no env-file, no caller-side signal handler.

**Usages relevant to this task:**
- `direct-runner` (imported from `goga/docker`, path
  `goga/docker/.usages/direct-runner.md`): the executor contract — the
  caller composes argv+env ONCE; `run_direct` spawns/forwards/returns;
  divergence between the two surfaces is a defect.
- `click` (`.goga/usages/cooks/click.md`): `is_flag=True` options;
  `raise click.ClickException` for the host-only rejections (stderr +
  exit 1).
- `docker-runner` / `docker-builder` / `docker-image-version` /
  `extra-env-carriage` / `home-profiles-carriage` (imported from
  `goga/docker`): the UNCHANGED host-substrate practices — the host
  branch keeps its wiring verbatim (image acquisition, version check,
  env-file ladder, carriage lines).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: the click surface exposes `--fail-on-error`
  (CliRunner `--help` or a flag-parse invocation);
  `run_pipeline_container` signature gains `fail_on_error` default
  `False`; `_compose_run_args` accepts `fail_on_error` (default `False`
  — every existing call site stays valid). Expected to fail at this
  stage
- [ ] **REPL probe**: in `.venv/bin/python` — with
  `monkeypatch.setenv("GOGA_DOCKER", "1")` and a `tmp_path` project, run
  the Click command through `CliRunner` with the spawn monkeypatched;
  observe the composed argv (including `--fail-on-error`), the parsed
  env overlay, and each rejection message. Migrate into the tests
- [ ] **Code**: the click option + dispatch forward; step 1a (the
  six-entry rejection)
- [ ] **Code**: `_compose_env_lines` extraction + `_build_env_file`
  wrapper + `_env_overlay`; `_compose_run_args` `fail_on_error`; the
  `fail_on_error` signature parameter; the 12a direct branch
- [ ] **Code**: the 7a direct branch in the info container
- [ ] **Interface verification**: `.venv/bin/pytest
  tests/commands/pipeline/ -v`
- [ ] **Logic tests**:
  - in `tests/commands/pipeline/test_pipeline_command.py` (or the file
    owning the click surface):
    `test_pipeline_direct_run_spawns_child_and_forwards_flag` —
    `monkeypatch.setenv("GOGA_DOCKER", "1")`; `tmp_path` project with a
    pipeline section in `.goga/config.yml`; monkeypatch
    `goga.docker.runner.subprocess.Popen` (or `run_direct`'s spawn) to
    capture argv; `CliRunner` with `["deploy", "--fail-on-error"]` →
    `argv[0:4] == ["python3", "-m", "goga.pipeline", "run"]`;
    `"deploy" in argv and "--fail-on-error" in argv`; no `--topic`-like
    host tokens; no docker subprocess ran (SC1 + SC8 plumbing — the
    direct path executes the same composed argv with the flag)
  - `test_pipeline_direct_rejects_each_host_only_option` —
    `@pytest.mark.parametrize` over `deploy -t feat`, `deploy --todo`,
    `deploy -u`, `deploy -e K=V`, `deploy --add-host h:1.2.3.4`,
    `deploy --proxy http://p` → `result.exit_code == 1`; the option
    token (e.g. `--add-host`) appears in `result.stderr`; the spawn mock
    was never called (SC2 — each option fails with an error naming it;
    nothing is silently ignored)
  - the host path untouched edge: with `GOGA_DOCKER` unset, a run-form
    invocation reaches the docker launcher exactly as before (existing
    tests cover this — keep them green)
  - in `tests/commands/pipeline/test_run_pipeline_container.py`:
    the direct branch composes the SAME env lines as the host env-file
    (compose via `_compose_env_lines`, assert the overlay parses
    first-`=`-split last-write-wins); `_compose_run_args` appends
    `--fail-on-error` only when True (parametrize True/False)
  - `test_direct_clean_wipes_before_launch` (pipeline arm — parametrized
    with the build arm of Task 12): `GOGA_DOCKER=1`; a stale marker under
    the in-container AFM_DIR path (the module constant monkeypatched
    into `tmp_path`); the spawn monkeypatched to record the directory
    contents at call time; `goga pipeline deploy --clean` → the spawn
    mock was called (the launch happened) and the stale marker file does
    not exist after the run
  - in `tests/commands/pipeline/test_run_pipeline_info_container.py`:
    the direct branch spawns `python3 -m goga.pipeline ...` with the
    cargo overlay (and `env=None` when no cargo); no docker calls
- [ ] **Migrate the affected existing tests**: the dispatch/composition
  suites in `tests/commands/pipeline/` (test_pipeline_dispatch.py,
  test_run_pipeline_container*.py, test_run_pipeline_info_container.py)
  — call-shape expectations gain the default-valued parameter; env-file
  composition tests move to the extracted `_compose_env_lines` where
  they assert line content (the wrapper keeps the file-write tests)
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x`
- [ ] **Contract re-verification**: one composition two sinks (no
  independent re-derivation of the layers for the direct path);
  substrate-scoped skips only; the host paths byte-identical
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors

### Task 12: `goga/commands/build` — the direct substrate and its dry-run

The build command consumes `is_in_docker` / `run_direct`. Step 1a (NEW —
BEFORE the docker-CLI check of step 1; the contract places 1a before 1 —
the rejection precedes the config load): `direct = is_in_docker()`; on
the direct path reject `extra_env` non-empty, `add_host` non-empty,
`proxy is not None`, `update is True` — each a clean ClickException
naming the option; step 1 (docker check) skipped entirely. Direct branch
(14a): skip the image-None guard, the host ralphex runtime-dir steps
(`resolve_build_runtime_dir` / `clean_build_runtime_dir` — docker-only),
the env-file write, the docker-run assembly, `docker_build_if_not_exist`,
`docker_update`, `DockerRunner`. Extract the ladder composition from the
`build` body (the `lines` assembly at `build.py:415-445` — home.env +
git identity + CLI entries + engine proxy triple + GOGA_EXTRA_ENV +
carriage lines) into `_compose_env_lines(...) -> list[str]` so both
substrates call the same composer; `_write_env_file(lines)` stays the
host sink. Direct path:

```
IF direct:
    IF clean: rmtree(<cwd>/.ralphex, missing_ok)
    lines = the SAME ladder composition
    args = ["-m", "goga.build", plan, *_cli_flags_to_args(cli_flags)]
    IF dry_run: print(shlex.join(["python3", *args]), file=sys.stderr);
                ctx.exit(0)
    exit_code = run_direct(["python3", *args], env=_env_overlay(lines))
    ctx.exit(exit_code)
FINALLY (both substrates): _cleanup_ralphex_in_project(Path.cwd())
```

Ralphex state does not persist across direct runs (no host runtime
mount) — an accepted, documented property. The no-`.ralphex`-in-project
invariant holds under every exit path on both substrates (the finally
runs on both). Host branch unchanged.

**Usages relevant to this task:**
- `direct-runner` (imported from `goga/docker`): the executor contract —
  same as Task 11.
- `click` (`.goga/usages/cooks/click.md`): ClickException rejections.
- `docker-runner` / `docker-builder` / `docker-image-version` /
  `extra-env-carriage` / `home-profiles-carriage` (imported from
  `goga/docker`): the UNCHANGED host-substrate practices — the host
  branch (steps 8–18) keeps its wiring verbatim.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: the build surface rejects each host-only
  option on the direct path; the direct dry-run prints and exits 0.
  Expected to fail at this stage
- [ ] **REPL probe**: in `.venv/bin/python` — `GOGA_DOCKER=1`,
  `tmp_path` project with a build section, spawn monkeypatched;
  `goga build plan.md` → observe `argv == ["python3", "-m",
  "goga.build", "plan.md"]` and the overlay's `GOGA_EXTRA_ENV` payload;
  `--dry-run` → observe the stderr line and exit 0. Migrate into the
  tests
- [ ] **Code**: step 1a (the four-entry rejection, before the docker
  check); `_compose_env_lines` extraction; the 14a direct branch with
  the clean wipe, dry-run print, `run_direct` spawn, and the shared
  finally cleanup
- [ ] **Interface verification**: `.venv/bin/pytest
  tests/commands/build/ tests/commands/test_build.py -v`
- [ ] **Logic tests**:
  - `test_build_direct_spawns_child_with_env_overlay` — `GOGA_DOCKER=1`;
    `tmp_path` project with a build section; monkeypatch the spawn to
    capture `(argv, env)`; git config absent; `goga build plan.md` via
    CliRunner (cwd=`tmp_path`) →
    `argv == ["python3", "-m", "goga.build", "plan.md"]`;
    `overlay["GOGA_EXTRA_ENV"] == encode_extra_env([])` (the payload
    line present); `not (tmp_path / ".ralphex").exists()` (the cleanup
    ran) (SC1 build form — direct execution with the same env contract
    and the project-directory invariant)
  - `test_build_direct_rejects_host_only_options` —
    `@pytest.mark.parametrize` over `plan.md -e K=V`,
    `plan.md --add-host h:ip`, `plan.md --proxy http://p`, `plan.md -u`
    → `exit_code == 1`; the option named in `result.stderr`; the spawn
    never called; ORDERING: a config-less project with `-e` still
    reports the host-only error first (assert the host-only message,
    not the config message) (SC2 + the ordering guard)
  - `test_build_direct_dry_run_prints_child_command_and_exits_zero` —
    `GOGA_DOCKER=1`; `tmp_path` project with a build section; the spawn
    monkeypatched; `goga build plan.md --dry-run` via CliRunner →
    `result.exit_code == 0`;
    `"python3 -m goga.build plan.md" in result.stderr` (the DIRECT
    line, never a docker run line); the spawn mock was never called
    (the distinct dry-run behavior of the direct path)
  - `test_direct_clean_wipes_before_launch` (build arm — the parametrize
    partner of Task 11's pipeline arm): `GOGA_DOCKER=1`; a stale
    `<tmp_path>/.ralphex/stale` marker; the spawn monkeypatched to
    record the directory contents at call time; `goga build plan.md
    --clean` → the spawn mock was called and the stale marker file does
    not exist after the run
- [ ] **Migrate the affected existing tests**: the build suites
  (`tests/commands/build/test_build.py`, `tests/commands/test_build.py`)
  — the env-ladder content assertions move to `_compose_env_lines`;
  dry-run expectations on the host path stay; new direct-path arms added
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x`
- [ ] **Contract re-verification**: ordering (1a before the docker
  check); invariant parity (`.ralphex` cleanup in finally on both
  substrates); one composition two sinks
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` +
  `.venv/bin/ruff format goga/ tests/`; `goga lint` 0 errors;
  `goga schema` — the two `goga/config/yaml` edges and the
  `run_direct`/`is_in_docker`/`direct-runner` additions on both
  command-cell edges; no cycles

### Task 13: Integration tests — the D5 chain and the D1 parity

Cross-cell scenarios spanning multiple packages: the full fail-on-error
chain (click → in-container argv → argparse → `run_pipeline` →
`run_flow` → engine argv) and the substrate parity of the composed
command (one composition, two sinks). These live in
`tests/integration/` per the convention.

**Usages relevant to this task:**
- `convention`: "Integration — only for interaction between
  modules/packages"; `tests/integration/` placement.
- `direct-runner`: the parity contract (divergence between the surfaces
  is a defect).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/integration/test_direct_substrate_and_fail_on_error.py`
  (the directory exists with `__init__.py`)
- [ ] D5 chain end-to-end (mocked at the spawn boundary only):
  `GOGA_DOCKER=1`, a `tmp_path` project, the spawn monkeypatched;
  `goga pipeline deploy --fail-on-error` through CliRunner → the child
  argv carries `--fail-on-error` (the click flag reached the composed
  in-container argv); then feeding that argv to `pipeline_cli` (with
  `run_pipeline` mocked) forwards `fail_on_error=True`; then
  `run_pipeline` → `run_flow` (mocked) receives `exit_on_fail=True`;
  then `run_flow` with the spawn mocked appends `--exit-on-fail` — each
  hop asserted in one test, proving the chain never silently drops the
  flag
- [ ] D1 parity edge: the direct-path child argv equals
  `["python3", *_compose_run_args(...)]` and the direct-path env overlay
  equals the parse of the SAME `_compose_env_lines(...)` the host path
  writes — assert composition sharing, not re-derivation (the host-path
  env-file content test already pins the line set)
- [ ] D3 chain (config → engine values): a `tmp_path` project whose
  `.goga/config.yml` carries `pipeline.agent: !ENV PIPELINE_AGENT` loads
  through `load_project_config` with the variable set — resolved into
  the effective config the run coordination consumes (the
  `parse_env_yaml` → validators → config chain)
- [ ] Run validation: `.venv/bin/pytest tests/integration/ -v`, then the
  full battery `.venv/bin/pytest tests/ -x`,
  `.venv/bin/ruff check goga/ tests/`,
  `.venv/bin/ruff format --check goga/ tests/`, `goga lint`,
  `goga schema`

---

## Validation Commands

- `.venv/bin/pytest tests/ -x`: Run all tests (the full battery; the
  `-x` stop-at-first-failure form the convention pins)
- `.venv/bin/pytest tests/<area>/ -v`: Run one area's tests (per-task
  interface verification)
- `.venv/bin/ruff check goga/ tests/`: Lint check (the CI gate verbatim)
- `.venv/bin/ruff format --check goga/ tests/`: Format check (the CI
  gate verbatim; `ruff format goga/ tests/` to fix)
- `goga lint` (bare, from the repository root): Cell-level contract
  lint — stays at 0 errors
- `goga schema`: Dependency graph — the two new `goga/config/yaml`
  edges (from both config cells) and the
  `run_direct`/`is_in_docker`/`direct-runner` additions on both
  command-cell → `goga/docker` edges; no cycles
- `.venv/bin/python -c "from goga.config.yaml import parse_env_yaml;
  from goga.docker import is_in_docker, run_direct"`: Facade
  accessibility of the three new surfaces
- `.venv/bin/python -c "from goga.pipeline.workflow import
  WorkflowAssistant; assert WorkflowAssistant(name='x').delegate is
  None"`: The delegate default after the model change

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
  (the new `goga/config/yaml/loader.py` + `__init__.py`;
  `is_in_docker` in `goga/docker/env.py`; `run_direct` in
  `goga/docker/runner.py`; all changed entities in their files)
- [ ] Every contract entity is accessible from its facade
  (`parse_env_yaml`, `is_in_docker`, `run_direct` in `__all__`,
  alphabetical)
- [ ] Properties and methods match the declared API (the
  `run_flow`/`run_pipeline`/`_compose_run_args`/container signatures
  gain their parameters with the declared defaults and positions)
- [ ] Descriptions are reflected in behavior (presence discipline, the
  field-level override, position preservation, the content check, the
  substrate-scoped skips, the five-field discriminator in all four
  modules)
- [ ] Contract dependencies are met (the two config cells import from
  `goga/config/yaml`; both command cells import `is_in_docker` /
  `run_direct` from `goga/docker`)
- [ ] No re-export obligations exist (none declared)
- [ ] Every coding task followed the TDD workflow (contract tests →
  code → verification → logic tests → debugging → re-verification →
  lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior
  within each coding task; all 33 design test scenarios exist (several
  parametrized — the boundary tables enumerate every boundary)
- [ ] Integration tests exist for the cross-entity scenarios (Task 13:
  the D5 chain, D1 parity, D3 chain)
- [ ] No package boundary was expanded (no new cells beyond the
  contracted `goga/config/yaml`; no cross-imports against the
  dependency order)
- [ ] `CODEMANIFEST` files and `.usages/` files were not modified
  (contract and practices are read-only for this plan)
- [ ] All validation commands pass (the full battery green; `goga lint`
  0 errors; `goga schema` shows the new edges, no cycles)
- [ ] Every Usages entry is mentioned in at least one task (`convention`
  — every task via the Mandatory Rules; `yaml_env` — Task 2; `afm` —
  Tasks 8, 9; `click` — Tasks 11, 12; `env-variables` — Task 4;
  `direct-runner` — Tasks 3, 11, 12, 13; the five unchanged
  docker-host practices — Tasks 11, 12)
- [ ] The affected existing tests were migrated, not weakened (the
  per-task inventories; every re-derived assertion traceable to a
  contract)
- [ ] The Mandatory Rules were enforced at every task boundary and every
  local commit (style, tests, linters/formatters, REPL cycle; no
  `Co-Authored-By:` trailers)
