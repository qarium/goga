# Plan: `support-afm-hooks`

<!-- Topic: `support-afm-hooks` — the afm lifecycle-hooks bridge: goga's observer hook
     registered on every launch, bridging the fifteen curated mid-run events onto the
     hooks platform. Source: `.goga/history/2026/support-afm-hooks/design.md`
     (design-review completed — 9 fixes applied, all "apply"; see its execution
     summary). This plan compiles the design into ralphex-executable tasks. -->

## Purpose

Implement the `support-afm-hooks` feature end-to-end: afm (v1.2.17+) lifecycle-hooks
become observable by goga tool packages. The in-container run coordination writes
goga's own observer hook into `~/.afm/config.yaml` on every launch; afm then spawns
`python3 -m goga.pipeline hook` once per lifecycle event, and the hook bridges each
curated event onto the hooks platform as a soft emission.

After implementation the project provides:

- `goga/hooks/catalog` — `declared_actions()` carries 15 additional pipeline records
  (13 verbatim stage-transition names + `run_resumed` + `run_interrupted`, all
  `error_class="soft"`); 49 records total, 18 in the pipeline domain;
- `goga/pipeline/hooks` — four new context models (`RunIdentity`, `StageTransition`,
  `RunEvent`, `StageEvent` in `contexts.py`), two new soft-emission methods on
  `PipelineHooks` (`emit_run_event`, `emit_stage_event`), zone facade `__all__` 11 → 15;
- `goga/pipeline` — the new `hook_bridge.py` (`run_hook`, `map_event_action`,
  `build_run_event`, `build_stage_event`), the observer hook entry in
  `write_afm_config`, the third CLI subcommand `hook` in `pipeline_cli`, the package
  facade 15 → 19, and the platform-free fast path (lazy imports per D1 — including the
  root facade `goga/__init__.py`).

The most important gaps between contract and code: `hook_bridge.py` does not exist;
the catalog carries 34 records (needs 49); the zone facade and contexts lack the four
bridged types and both emission methods; `write_afm_config` writes no `hooks` entry;
`pipeline_cli` has two subcommands with platform-carrying static imports; both the
pipeline and the root facades statically import the platform (~0.39 s of the ~0.45 s
process import chain), so the fast-path guarantee ("no platform modules in
`sys.modules`" for a non-curated event) is currently unachievable.

Strategy: leaves-first TDD in the design's mandated order — catalog records → zone
(contexts, events, facade) → bridge module + `afm_config` + `cli` (+ facade laziness)
→ process-level integration proof. Every task is gated by the Mandatory Rules below.
CODEMANIFEST changes and all `.usages/`/docs supplements are **already applied in the
working tree** — this plan touches code and tests only.

## Mandatory Rules

<!-- Extracted verbatim from the project convention `.goga/usages/conventions.md`
     (the `convention` practice wired into every cell of this feature — for working
     with the codebase, organizing the REPL development cycle, debugging and testing,
     and the test infrastructure), the language rules (`goga-cell-python`), the ruff
     configuration (`pyproject.toml`), and the repo gates (`.github/workflows/lint.yml`,
     `.githooks/`). These rules are MANDATORY for every task in this plan. Where a
     task restates a rule, the restatement is a reminder, not a replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`.
- **Imports**: relative imports for ALL intra-package references inside `goga/`
  (`from .hooks import PipelineHooks`, `from ..workflow import WorkflowDocument`);
  absolute imports only for stdlib and third-party. Exception — tests:
  cross-directory references inside `tests/` use absolute imports rooted at the
  `tests` package (`from tests.hooks.conftest import install_tool_package`).
- **Data models**: stdlib `dataclasses` only; model classes use `kw_only=True`
  (NOT frozen — the existing zone contexts are plain `kw_only`; read-only enforcement
  is the platform's delivery proxy, not the model's); empty defaults for fields
  (`reason=""`); `None` only for the explicit absence of a value.
- **Docstrings**: Google style, MANDATORY for every public function, method, and
  class. First line starts with a capital letter and ends with a period. Include
  `Args` when the function accepts parameters, `Returns` when it returns a value,
  `Raises` when it raises beyond built-in types. Dataclass models use the `Args:`
  block per field (the `contexts.py` precedent).
- **Code formatting**: inside function and method bodies, separate logical blocks by
  ONE blank line (initialization / conditions and loops / data preparation /
  processing / return).
- **Type hints**: mandatory everywhere (drives facade signature extraction). Allowed
  shapes: `str`, `int`, `float`, `bool`, `list[T]`, `dict[str, T]`, `T | None`.
  Forbidden: `*args`, `**kwargs`, bare `dict`, bare `list`. Annotations may use
  `from __future__ import annotations` + a `TYPE_CHECKING` block (the D1 pattern of
  `hook_bridge.py`).
- **Naming**: PascalCase classes, snake_case functions/methods/properties/modules.
- **Facade**: each cell's `__init__.py` exposes the contract API via `__all__`; only
  identifiers in `__all__` constitute the facade; `__all__` stays alphabetically
  sorted (uppercase first).
- **Logging**: the bridge adds NO new log points — subscriber failures are logged by
  the platform (`logger.warning` naming the hook, tool, address, reason); the bridge
  stays silent on the happy path by contract. Any log record follows the structured
  format with contextual metadata (`extra={...}`), lowercase messages.
- **Dependencies**: no new third-party dependencies — `pyyaml`, `jinja2` are already
  pinned in `pyproject.toml`; any hypothetical new library MUST go into
  `pyproject.toml` with a minimum version.

### Test Writing Rules (strictly per `conventions.md` — Testing)

- **Tools**: pytest (runner), ruff (lint + format of test code), pytest-cov
  (coverage). Test libraries live in `pyproject.toml`
  `[project.optional-dependencies]` under `test`.
- **Structure mirrors source directly**: `goga/pipeline/hook_bridge.py` →
  `tests/pipeline/test_hook_bridge.py`; `goga/pipeline/hooks/events.py` emission
  tests → `tests/pipeline/hooks/test_bridged_events.py`. Every test directory
  already carries `__init__.py`.
- **Fixtures**: local fixtures in `tests/<package>/conftest.py`, shared fixtures in
  `tests/conftest.py`. Available shared infrastructure (reused, never duplicated):
  - `pin_package_environment(mapping)` / `install_tool_package(...)` of
    `tests/hooks/conftest.py`, re-exported by `tests/pipeline/conftest.py` and
    `tests/pipeline/hooks/conftest.py` — pin the two outside-world points (the
    `packages_distributions` read, the `sys.modules` entry of a `goga_tool_*`
    package) with the platform code under test running for real;
  - `tests/pipeline/conftest.py::_in_container_run_context` (autouse) — redirects
    `_AFM_CONFIG_PATH` into the tmp tree and pins the package environment empty;
  - `config_path` fixture of `tests/pipeline/test_afm_config.py` — the fixed home
    path constant patched into the tmp tree (never the filesystem root);
  - `is_kw_only_dataclass` (tests/conftest), `ZONE_ALL` / `field_defaults`
    (tests/pipeline/hooks/conftest).
- **Mocking pattern for shadowed modules**: `goga.pipeline` shadows its `cli`,
    `run_pipeline`, `afm_config`, `hook_bridge` submodule names in the package
    `__init__`, so a string-based `mock.patch` path walking through the package
    fails on Python 3.10 — resolve the real module via
    `sys.modules["goga.pipeline.cli"]` and patch its attributes directly (the
    established `[[feedback_mock_patch_module_shadowing]]` pattern of
    `tests/pipeline/test_pipeline_cli.py`).
- **Bridge tests manipulate the two process inputs directly**:
  `monkeypatch.setenv("AFM_HOOK_EVENT", …)` and
  `monkeypatch.setattr("sys.stdin", io.StringIO(json_text))`.
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`;
  grouping `class Test<Component>:` with docstrings; self-documenting test names;
  keep comments minimal.
- **Test types**: Unit — every public function/method/class, main scenario and
  typical data. Edge cases — empty inputs (`""`, `{}`, missing keys), invalid types,
  expected exceptions via `pytest.raises`. Integration — only for interaction
  between modules/packages (the subprocess fast-path proof is the integration
  scenario of this feature).
- **Boundary tests**: for the curated/non-curated vocabulary split use
  `@pytest.mark.parametrize` with a table of values covering both sides of the
  boundary (all fifteen curated names; the non-curated set including `""`).
- **Mocks**: pure logic — NO mocks (the catalog, `map_event_action`, and both
  builders are mock-free record tests); file I/O — the `tmp_path` fixture
  exclusively; subprocesses — the integration test spawns a REAL child
  (`subprocess.run([sys.executable, "-c", ...])`, not a mock — the whole point is
  the process-level import proof); external dependencies — `mock.patch` at the
  import point. Mock only at external boundaries.
- **CLI testing**: invoke `pipeline_cli(argv)` by direct Python call (no
  subprocess); argparse errors are `SystemExit` with `.code == 2` and usage on
  stderr — assert via `pytest.raises(SystemExit)`.
- **Expected values are grounded, never recalled**: every fixture expectation in
  this plan was verified by the design against the live afm binary (JSON tags,
  YAML keys) and the live sources; if an assertion disagrees with a live run during
  implementation, the live run wins and the disagreement is reported — never
  silently "aligned".

### Linter and Formatter Enforcement (all development stages and local commits)

The following gates are MANDATORY at the end of EVERY task and BEFORE EVERY local
commit, across all development stages. A failing gate is an actionable defect, never
acceptable noise. Local git hooks do NOT enforce formatting (only the commit-msg /
pre-push Co-Authored-By policy does) — the author runs the formatter deliberately:

1. `ruff check goga/ tests/` — zero violations (the CI gate of
   `.github/workflows/lint.yml`; rule set per `pyproject.toml`: E, W, F, I, N, UP,
   B, SIM, PL, PLR, C4, DTZ, PT, ARG, RUF, PTH, C90; line length 120; target
   py310).
2. `ruff format --check goga/ tests/` — zero reformattings; run
   `ruff format goga/ tests/` when it reports diffs.
3. `goga lint` — cell-level lint, **0 errors over 91 cells** (if a run reports an
   error that a re-run does not reproduce, trust the re-run — the command is
   occasionally flaky in this tree; a persistent error is real).
4. Focused tests green, then `pytest tests/ -x` green (the full battery — the
   catalog/contract count adaptations exist precisely so the battery stays green).
5. Facade import checks green (see Validation Commands).
6. **Commit policy**: commit only with all gates green; commit messages MUST NOT
   contain `Co-Authored-By:` trailers (`.githooks/commit-msg` and `pre-push`
   reject them).
7. `CODEMANIFEST` files are READ-ONLY for the implementer — the contract changes
   are already applied in the working tree; if code does not match the contract,
   fix the code, never the contract.

### REPL Cycle Rules (continuous interactive evaluation, hot reloading, migration to source)

The `convention` practice is wired into every cell of this feature for "Organizing
the REPL development cycle". Every coding task in this plan follows the same loop:

1. **Virtualenv first**: all code executes inside a virtualenv — create it if
   missing. No `.venv` exists in the workspace right now and the system interpreter
   (`/opt/goga/bin/python3`) has no pytest/ruff — Task 1 bootstraps the environment
   (`python3 -m venv .venv` + `.venv/bin/pip install -e ".[test]"`) and verifies the
   baseline gates green BEFORE any change; every subsequent probe, test run, and
   lint run executes inside it.
2. **Probe before writing**: verify each non-trivial behavior interactively against
   real inputs BEFORE the verified snippet is written into a source file. The probes
   of this feature: confirm the sorted position of the 15 new catalog records by
   evaluating `declared_actions()` in a REPL (Task 1); confirm the dataclass
   field/default ordering of the four contexts by constructing them (Task 2);
   confirm `emit_hook_event`'s `context_for` per-tool call shape and the
   `_DeliveryProxy` write-blocking by driving one subscribed fake tool live (Task 3);
   confirm the payload parsing and the `payload.get("reason") or ""` JSON-null
   behavior against the design's afm-shaped payload dict (Task 4); re-read the
   written `config.yaml` after a live `write_afm_config` call into a tmp path
   (Task 5); confirm the argparse `hook` subparser rejects options with exit 2 via a
   scratch `pipeline_cli(["hook", "--port", "1"])` call (Task 6); confirm the PEP
   562 `__getattr__` semantics (import system sets the attribute on first submodule
   import, `__getattr__` fires at most once per name; `from goga import app, AST`
   still resolves) with a fresh `python -c` child per probe (Task 7).
3. **Hot feedback after every edit**: immediately re-run the focused test file and
   the facade import check in the same virtualenv; iterate in small steps. A
   long-lived REPL session re-imports edited modules (`importlib.reload` or a fresh
   `python -c`) — never trust stale module state as evidence; module-level state
   (the `_DECLARED_ACTIONS` list, `_EVENT_ACTION_MAP`) demands a fresh interpreter
   after every edit.
4. **Migrate verified code to source files**: REPL-verified snippets are migrated
   into the target `location` file with type hints, Google docstrings, relative
   imports, and convention formatting; REPL scratch never ships and is never
   referenced by source.
5. **Close the loop per task**: probe → implement (migrate) → focused tests → full
   battery → lint/format gates → commit (gates green).

## Context

### Contract Surface

**Routine: `declared_actions() -> actions: list[Action]`** (cell `goga/hooks/catalog`
— CHANGED, additive)
- Declared `location`: `catalog.py`
- Facade obligation: importable from `goga.hooks.catalog` (and re-exported by
  `goga.hooks`)
- Semantic requirements: return `sorted(_DECLARED_ACTIONS, key=(domain, name))` —
  now 49 records (34 existing + 15 new), deterministic, complete, no filtering. The
  15 additions (all `domain="pipeline"`, `error_class="soft"`, D6 placement after
  `run_completed` in the pipeline group of `_DECLARED_ACTIONS`): `run_resumed`,
  `run_interrupted`, and the thirteen stage names `stage_planning_started`,
  `stage_plan_ready`, `stage_approved`, `stage_revision_started`,
  `stage_execution_started`, `stage_question_asked`, `stage_question_answered`,
  `stage_retry_scheduled`, `stage_retry_started`, `stage_paused`, `stage_resumed`,
  `stage_finished`, `stage_failed`. No existing record rewritten.
- Verified trace (design, verbatim): the sort places the new pipeline records as
  `run_interrupted`, `run_resumed`, `stage_approved`, `stage_execution_started`,
  `stage_failed`, `stage_finished`, `stage_paused`, `stage_plan_ready`,
  `stage_planning_started`, `stage_question_answered`, `stage_question_asked`,
  `stage_retry_scheduled`, `stage_retry_started`, `stage_resumed`,
  `stage_revision_started` after `amend_workflow`, `run_created`, `run_completed`;
  the `(domain, name)` pairs do not collide with the existing 34 records.
  `emit_hook_event` resolves `pipeline / <action>` for the 15 new addresses —
  data-driven, no dispatch code change.
- Annotation context: catalog is data only — no package enumeration, no discovery;
  published records never rewritten.

**Entities: `RunIdentity`, `StageTransition`, `RunEvent`, `StageEvent`** (cell
`goga/pipeline/hooks` — NEW, `location: contexts.py`)
- Declared `location`: `contexts.py` (same file as `CompositionStage` / `RunCreated`
  / `RunCompleted` — the file already imports `dataclass` and uses
  `from __future__ import annotations`)
- Facade obligation: importable from `goga.pipeline.hooks`; join `__all__` (11 → 15)
- Signatures (exact, from the CODEMANIFEST):
  - `RunIdentity(run_id: str, run_dir: str, root_dir: str, resumed: bool)`
  - `StageTransition(id: str, name: str, from_status: str, to_status: str, phase: str)`
  - `RunEvent(pipeline: str, run: RunIdentity, event_id: str, occurred_at: str, reason: str = "")`
  - `StageEvent(pipeline: str, run: RunIdentity, stage: StageTransition, event_id: str, occurred_at: str, reason: str = "")`
- Semantic requirements: `@dataclass(kw_only=True)` field assignment, no validation
  logic, no methods — the identical shape as `CompositionStage` / `RunCreated` /
  `RunCompleted`; fields in the declared order; `reason` defaults to `""` and sits
  LAST in both event signatures (dataclass ordering rule); NOT frozen — plain
  `kw_only` like the existing contexts; read-only enforcement is the platform's
  `wrap_context` proxy at delivery time (plain dataclass attributes are readable
  through `_DeliveryProxy.__getattr__` — verified in `delivery.py`).
- Edge cases: `from_status` / `to_status` — the raw `from` / `to` keywords never
  become attribute names (the documented rename); `reason` absent in the source →
  `""` (the only default).

**Methods: `PipelineHooks.emit_run_event` / `emit_stage_event`** (cell
`goga/pipeline/hooks` — NEW on `PipelineHooks`, `location: events.py`)
- Declared `location`: `events.py`
- Facade obligation: methods on `PipelineHooks` (already on the zone facade)
- Signatures: `emit_run_event(action: str, context: RunEvent)` and
  `emit_stage_event(action: str, context: StageEvent)`; return `None`
- Semantic requirements (verified trace, verbatim from the design):
  1. `registry ← self._ensure_registry()` — the existing lazy pattern; the registry
     builds once per surface (per event process); `PipelineHooks()` construction
     stays cheap;
  2. `emit_hook_event(registry, "pipeline", action, context_for=lambda _tool:
     context)` — the address resolves against `declared_actions()` (implementation
     dependency: the catalog records land FIRST — Task 1); `context_for` returning
     the same instance for every tool satisfies "one shared read-only context
     instance" — the platform builds one view per distinct tool, all wrapping the
     same object;
  3. per subscription: `wrap_context(view)` (read-only proxy),
     `build_hook_arguments(hook, view, registry.self_context(tool))` (the hook
     receives only the parameters it declares: `context`, `self`), call — nothing
     collected, nothing returned;
  4. failure handling — the record's `error_class` is `soft`: a raising hook logs
     `WARNING` ("hook %s of tool %s failed on pipeline.%s: %s") and the sequence
     continues; an UNKNOWN action raises `ValueError("unknown hook action:
     pipeline.<action>")` from the platform's address resolution (caller error →
     bridge-internal failure → exit 1);
  5. the two methods are intentionally symmetric — one per context type; the
     signatures stay typed, no union parameter.
- Edge cases: address without subscriptions → nothing emits, return `None`
  (a run with no tool packages stays behaviorally identical); multiple hooks of one
  tool → one shared view per tool (platform rule), same context instance for every
  tool.

**Routine: `run_hook() -> exit_code: int`** (cell `goga/pipeline` — NEW,
`location: hook_bridge.py`)
- Declared `location`: `hook_bridge.py` (new file)
- Facade obligation: importable from `goga.pipeline` (static import — the module top
  is stdlib-only, so the facade import is cheap)
- Signature: no parameters; returns the process exit code — 0 on success, on
  ignored events, and on subscriber soft failures; non-zero only on a
  bridge-internal failure
- Algorithm (design, verbatim):
  ```
  1. action ← map_event_action(os.environ.get("AFM_HOOK_EVENT", ""))
     IF action is None: return 0                   # before any platform import; stdin unread
  2. TRY
     payload ← json.loads(sys.stdin.read())
     IF not isinstance(payload, dict): raise ValueError(
         "lifecycle event payload is not a JSON object")
     context ← build_stage_event(payload) if action not in _RUN_LEVEL_ACTIONS
               else build_run_event(payload)     # {"run_resumed", "run_interrupted"}
     from .hooks import PipelineHooks            # function-local — after the filter
     hooks ← PipelineHooks()
     hooks.emit_stage_event(action, context) / hooks.emit_run_event(action, context)
     return 0
   EXCEPT (ValueError, ImportError, OSError) as reason:
     print(f"Error: {reason}", file=sys.stderr)  # the afm per-hook log carries it
     return 1
  ```
- Requirements: the curated filter runs before any platform import; no cross-event
  state; the command completes far inside the afm default per-hook timeout
  (measured worst case ~0.5 s vs 30 s); the happy path prints nothing; catch exactly
  `(ValueError, ImportError, OSError)` — `JSONDecodeError` and
  `UnicodeDecodeError` arrive as `ValueError` subclasses; `ImportError` covers a
  broken tool facade (the `run_pipeline` CLI precedent).
- Constraints: read nothing besides stdin and the `AFM_*` environment values; write
  no files; never mutate the process environment; never let a subscriber failure
  change the outcome; never emit the run boundaries (`run_created` /
  `run_completed` belong to the run coordination).
- Edge cases: unset/empty `AFM_HOOK_EVENT` → exit 0 (non-curated); empty stdin on a
  curated event → `json.loads("")` raises → exit 1; no tool packages installed →
  empty registry → no-op emission → exit 0.

**Routine: `map_event_action(event: str) -> action: str | None`** (cell
`goga/pipeline` — NEW, `location: hook_bridge.py`)
- Facade obligation: importable from `goga.pipeline`
- Algorithm (design, verbatim):
  ```
  _EVENT_ACTION_MAP: dict[str, str] = {           # module-level literal
      "flow_resumed": "run_resumed",
      "flow_interrupted": "run_interrupted",
      "stage_planning_started": "stage_planning_started",
      ... the thirteen stage names, verbatim ...
  }
  1. return _EVENT_ACTION_MAP.get(event)
     → None for everything else (flow_started/finished/failed, the nine script
       events, internal names, unknown names, "")
  ```
- Requirements: pure and deterministic — a dict-literal lookup, no environment or
  filesystem access, callable before any platform import. Vocabulary coverage: 13
  verbatim + 2 normalized = 15 = the catalog records = the `registering-hooks.md`
  table.
- Edge cases: unset/empty env value → `.get("") → None`; a future afm event name →
  `None` (forward-compatible by design — the ADR's reason for `events: all`).

**Routine: `build_run_event(payload: dict[str, Any]) -> context: RunEvent`** (cell
`goga/pipeline` — NEW, `location: hook_bridge.py`)
- Facade obligation: importable from `goga.pipeline`
- Verified payload shape (binary-confirmed JSON tags): flow block
  `{name, run_id, resumed, run_dir, root_dir}`; event facts `event_id` (the
  documented idempotency key), `occurred_at` (ISO-8601 UTC string, carried
  verbatim, never re-parsed), `reason` (optional). Algorithm (design, verbatim —
  shared skeleton with `build_stage_event`):
  ```
  1. flow ← payload["flow"]          # ValueError naming "flow block" if absent/non-dict
  2. identity ← RunIdentity(run_id=flow["run_id"], run_dir=flow["run_dir"],
                            root_dir=flow["root_dir"], resumed=flow["resumed"])
  3. facts ← event_id=payload["event_id"],      # ValueError naming the fact if absent
             occurred_at=payload["occurred_at"],
             reason=payload.get("reason") or ""
  4. return RunEvent(pipeline=flow["name"], run=identity, **facts)
  ```
- Requirements: pure passthrough — values carry under idiomatic names only; the raw
  payload never attaches to the context; a missing required fact raises a clean
  `ValueError` naming it; nothing invented, nothing defaulted except `reason`.
- Edge cases: extra payload fields (`schema_version`, `event`) → ignored by
  construction; `reason: null` in JSON → `payload.get("reason") or ""` lands `""`.

**Routine: `build_stage_event(payload: dict[str, Any]) -> context: StageEvent`**
(cell `goga/pipeline` — NEW, `location: hook_bridge.py`)
- Facade obligation: importable from `goga.pipeline`
- Algorithm: reads the flow block and the event facts exactly as `build_run_event`
  (SHARED private helpers — `_flow_block`, `_run_identity`, `_event_facts` — keep
  the two builders in step; a divergence is structurally impossible), plus:
  ```
  stage ← payload["stage"]      # ValueError naming "stage block" if absent/non-dict
         # block shape {id, name, from, to, phase} — binary-confirmed tags
  transition ← StageTransition(id=stage["id"], name=stage["name"],
                               from_status=stage["from"], to_status=stage["to"],
                               phase=stage["phase"])
  return StageEvent(pipeline=flow["name"], run=identity, stage=transition, **facts)
  ```
- Requirements: pure passthrough; a payload without the stage block raises a clean
  `ValueError("stage-level lifecycle event payload carries no stage block")` — a
  stage-level event always carries one; the `from`/`to` renames are the documented
  keyword workaround.

**Routine: `write_afm_config(agent: str | None) -> config_path: Path`** (cell
`goga/pipeline` — CHANGED, `location: afm_config.py`)
- Facade obligation: importable from `goga.pipeline` (already); signature unchanged
- Delta: the composed content additionally carries goga's observer hook entry in
  the global `hooks` layer. Algorithm step 2 (design, verbatim):
  ```
  content["hooks"] = [{                          # the observer registration
      "id": "goga",
      "events": "all",
      "command": "python3 -m goga.pipeline hook",
      "inherit_env": True,                       # timeout/retries omitted → afm defaults
  }]
  ```
- Requirements (binary-verified against the afm binary: `yaml:"hooks,omitempty"`,
  `yaml:"id"`, `yaml:"events"`, `yaml:"command"`, `yaml:"inherit_env,omitempty"`):
  `timeout` / `retries` intentionally OMITTED (both `omitempty` in afm → defaults
  30 s / 0 — exactly what the manifest and ADR fix); no `env` map (the bridge has
  no secret references of its own); the entry is a constant, never configurable —
  whole-file rewrite on every run keeps repeated invocation safe (the entry never
  duplicates); `yaml.safe_dump(content, default_flow_style=False, sort_keys=False)`
  at the unchanged `_AFM_CONFIG_PATH`; `OSError` propagates unchanged (existing
  semantics).
- Edge cases: `agent=None` → the `client` block is omitted; the hook entry still
  registers (the bridge is agent-independent).

**Routine: `pipeline_cli(argv: list[str]) -> exit_code: int`** (cell
`goga/pipeline` — CHANGED, `location: cli.py`)
- Facade obligation: importable from `goga.pipeline` (already)
- Delta — parser: a third subparser
  `subparsers.add_parser("hook", help="afm-facing machinery: bridge one lifecycle event")`
  with NO arguments (any option or positional extra is an argparse error — exit 2;
  the "no options" requirement falls out of declaring none; `--help` lists the
  subcommand).
- Delta — dispatch (design, verbatim):
  ```
  IF args.command == "hook": return run_hook()
  # the hook branch binds on args.command BEFORE any read of args.info —
  # the hook subparser declares no --info, so its Namespace carries no `info`
  # attribute; a branch placed after the unconditional `if args.info:` read
  # would raise AttributeError on every hook invocation
  # run/card branches unchanged except: their operation modules are imported
  # inside the branch functions (see D1)
  ```
- Errors: argparse errors → 2 (SystemExit, not a returned code — the existing
  CLI-test precedent); `run_hook` failures self-render (stderr + 1) and the branch
  returns the code — pure delegation, no CLI-side catch for the hook branch.
- Edge cases: `hook --anything` / `hook extra` → exit 2 with usage; the hook happy
  path prints nothing.

**Design decisions binding for the implementation (D1–D6, verbatim essentials):**

- **D1 — platform-free fast path (lazy imports).** afm spawns one process per event;
  the measured static import chain costs ~450 ms — ~390 ms of it the root package
  facade, ~86 ms the in-container chain. The interpreter always imports the parent
  packages before `goga.pipeline.__main__` runs, so the root facade must go lazy
  together with the cell facade. Four coordinated changes deliver it:
  1. `hook_bridge.py`: module top imports stdlib only (`json`, `os`, `sys`,
     `typing.Any`); every `goga` import lives inside function bodies. Annotations
     use `from __future__ import annotations` + a `TYPE_CHECKING` block.
  2. `cli.py`: `from .describe_pipeline import describe_pipeline` and
     `from .run_pipeline import run_pipeline` move into the branch functions that
     use them (`_run_card`, `_run_execution`); the remaining top-level imports
     (`argparse`, `sys`, `pathlib`, `yaml`, `jinja2`, `.compiler`,
     `.describe_pipelines`, `.list_pipelines`, `.pipeline_entry`, `.workflow`,
     `.hook_bridge`) are platform-free — verified by import-trace. `run_hook` may
     stay top-level (its module is stdlib-only).
  3. `goga/pipeline/__init__.py`: the two platform-carrying re-exports
     (`describe_pipeline`, `run_pipeline`) become lazy via a PEP 562 module
     `__getattr__` that `importlib.import_module`s the submodule on first attribute
     access; every other facade import stays static. The facade surface (`__all__`,
     nineteen names after D5) is unchanged — `from goga.pipeline import
     run_pipeline` still works; the import system sets the attribute on first
     submodule import, so `__getattr__` fires at most once per name.
  4. `goga/__init__.py`: the root facade is the dominant carrier (measured: all 17
     platform modules, ~0.39 s, present in `sys.modules` after a bare `import
     goga`). Both root re-exports (`AST` from `.ast`, `app` from `.cli`) become
     lazy via the same PEP 562 mechanism; `__all__ = ["AST", "app"]` is unchanged.
     Verified: the console script `goga = "goga.cli:app"` imports `goga.cli`
     directly and is unaffected; `from goga import app, commands` keeps working
     (when the attribute lookup raises, the import system falls back to importing
     the submodule); no goga-internal module reads `goga.app`/`goga.AST` at import
     time.
- **D2 — hook entry shape (binary-verified).** `hooks: [{id: goga, events: all,
  command: python3 -m goga.pipeline hook, inherit_env: true}]`; `timeout` /
  `retries` omitted; no `env` map.
- **D3 — run-level split.** `_RUN_LEVEL_ACTIONS: frozenset[str] =
  frozenset({"run_resumed", "run_interrupted"})` in `hook_bridge.py`; membership
  picks the builder after mapping.
- **D4 — failure rendering.** `run_hook` itself renders bridge-internal failures
  (`Error: <reason>` to stderr) and returns 1 — the manifest's "return a
  non-zero exit" wording, and the afm per-hook log stays informative;
  `pipeline_cli`'s hook branch is pure delegation.
- **D5 — facades.** `goga/pipeline/hooks/__init__.py`: `__all__` grows 11 → 15 (+
  `RunEvent`, `RunIdentity`, `StageEvent`, `StageTransition`; import from
  `.contexts`). `goga/pipeline/__init__.py`: `__all__` grows 15 → 19 (+
  `build_run_event`, `build_stage_event`, `map_event_action`, `run_hook`; static
  import from `.hook_bridge`), alphabetical. Test scaffolding mirrors: `ZONE_ALL`
  (zone conftest) 11 → 15; `test_pipeline_contract.py` fifteen → nineteen.
- **D6 — catalog placement.** The 15 records join the existing pipeline group of
  `_DECLARED_ACTIONS` after `run_completed`; the public ordering stays derived by
  the existing `sorted()`.

### Entity Interaction and Data Flow (verbatim from the design)

```
afm (external binary, run by run_flow inside the container)
  │  spawns per lifecycle event: sh -c "python3 -m goga.pipeline hook"
  │  CWD = flow root_dir; JSON payload on stdin; AFM_* in the (inherited) env
  ▼
goga.pipeline.__main__ ── ensure_in_docker() ──► goga.docker
  │ pipeline_cli(argv)
  ▼
goga.pipeline.cli::pipeline_cli  ── parse (argparse, subcommand "hook") ──► dispatch
  │ run_hook()
  ▼
goga.pipeline.hook_bridge::run_hook
  │ 1. AFM_HOOK_EVENT ──► map_event_action ──► action | None
  │        │ None (script events, flow_started/finished/failed, unknown) ──► return 0
  │        │      (fast path: no platform module imported — verified goal)
  │ 2. stdin ──► json parse ──► payload: dict         (damaged ──► Error + exit 1)
  │ 3. action ∈ {run_resumed, run_interrupted}?
  │        ├─ yes ──► build_run_event(payload)  ──► RunEvent
  │        └─ no  ──► build_stage_event(payload) ──► StageEvent
  │ 4. from .hooks import PipelineHooks   (function-local: after the filter)
  │    PipelineHooks().emit_run_event / emit_stage_event(action, context)
  ▼
goga.pipeline.hooks.events::PipelineHooks
  │ _ensure_registry() ──► HookRegistry (built once per event process)
  │ emit_hook_event(registry, "pipeline", action, context_for=lambda _: context)
  ▼
goga.hooks.dispatch.emit::emit_hook_event
  │ resolves domain/action against declared_actions()  ◄── goga.hooks.catalog
  │        (the 15 new soft pipeline records live here)
  │ per subscription: wrap_context (read-only proxy) + build_hook_arguments + call
  │ soft error class: a failing hook ──► logger.warning, sequence continues
  ▼
goga_tool_* subscriber hooks  (context: RunEvent | StageEvent — reads only)

Registration side (once per run, before the launch):
goga.pipeline.run_pipeline ── write_afm_config(agent) ──► ~/.afm/config.yaml
  content: client.command? + theme/open_browser/proxy.enabled/prompts_dir
         + hooks: [{id: goga, events: all, command: python3 -m goga.pipeline hook,
                    inherit_env: true}]          (timeout/retries omitted ── afm defaults)
```

**Data Flows** (verbatim summaries of the five design flows):

- **Flow 1 — registration (once per run).** `run_pipeline` step 16 calls
  `write_afm_config(config.pipeline.agent)`; the routine composes the content dict —
  optional `client` block, the four static fields, and now the `hooks` list — and
  serializes with `yaml.safe_dump` to the fixed path. Nothing is printed. On the
  next `afm run`, afm unions the global layer (goga-authored) with
  project/flow/stage layers and invokes the hook once per lifecycle event.
- **Flow 2 — non-curated event (the fast path).** afm spawns the hook process for
  an event outside the curated vocabulary; `run_hook` reads `AFM_HOOK_EVENT`,
  `map_event_action` returns `None`, the process returns exit 0 — without importing
  any `goga.hooks` / `goga.pipeline.hooks` module and without building the
  registry. stdin is not read.
- **Flow 3 — curated stage event.** afm spawns the process with, e.g.,
  `AFM_HOOK_EVENT=stage_execution_started` and the full JSON payload on stdin; the
  filter resolves the verbatim action name; the payload is parsed;
  `build_stage_event` composes the context; `PipelineHooks().emit_stage_event`
  delivers the shared read-only context to every subscriber; the process returns 0.
  Subscriber failures warn inside the platform and do not change the exit code.
- **Flow 4 — curated run-level event.** Same as Flow 3 with
  `AFM_HOOK_EVENT=flow_resumed` (→ `run_resumed`) or `flow_interrupted`
  (→ `run_interrupted`); the context is composed by `build_run_event` (no stage
  block).
- **Flow 5 — bridge-internal failure.** Damaged stdin, a missing flow block, a
  missing required event fact, or a missing stage block on a stage-level event:
  the builders raise a clean `ValueError` naming the missing fact; `run_hook`
  renders `Error: <reason>` to stderr and returns 1. afm records the non-zero exit
  in the per-hook log (`.afm/runs/<run-id>/hooks/goga.log`) and warns on the
  dashboard; the run is unaffected either way (observer semantics).

**Initialization order** for a bridged emission (one process): `run_hook` →
`map_event_action` (pure, no imports) → parse → build context (zone dataclasses) →
`PipelineHooks()` (cheap — no enumeration at construction) → first emission builds
the `HookRegistry` once (`build_once`) → delivery. The zone surface instance is
created per event process and dies with it; no cross-event state exists anywhere in
the bridge.

### Re-exports

- `RunIdentity`, `StageTransition`, `RunEvent`, `StageEvent` — source:
  `goga/pipeline/hooks/contexts.py`; facade obligation: importable from
  `goga.pipeline.hooks`; `__all__` 11 → 15 (D5).
- `run_hook`, `map_event_action`, `build_run_event`, `build_stage_event` — source:
  `goga/pipeline/hook_bridge.py`; facade obligation: importable from
  `goga.pipeline` via STATIC imports from `.hook_bridge` (the module top is
  stdlib-only — the import keeps the facade cheap); `__all__` 15 → 19 (D5).
- `describe_pipeline`, `run_pipeline` — stay importable from `goga.pipeline`
  (facade surface unchanged) but become LAZY PEP 562 re-exports (D1 item 3).
- `AST`, `app` — stay importable from `goga` (`__all__ = ["AST", "app"]`
  unchanged) but become LAZY PEP 562 re-exports (D1 item 4); the console script
  `goga = "goga.cli:app"` imports `goga.cli` directly and is unaffected.

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — the project-wide mandatory
  practice: relative intra-package imports, `kw_only` dataclasses, Google
  docstrings, log levels, REPL/test infrastructure rules. Referenced by the
  manifests' global annotations of all three cells; applied to every new/changed
  entity (the four context models, both emission methods, all four bridge
  routines, the catalog records, the facade updates). Extracted in full into the
  Mandatory Rules above.
- `afm` (`.goga/usages/cooks/afm.md`) — the external afm CLI contract:
  configuration-file fields, the lifecycle-hooks mechanism (declaration layers,
  entry fields, event catalog, JSON payload, `AFM_*` env, execution model, failure
  semantics), and goga's registration stance. Used by `write_afm_config` (the hook
  entry), `run_hook` (execution model, payload, env, failure semantics),
  `map_event_action` (the event catalog), `build_run_event` / `build_stage_event`
  (the payload shape), and the bridging paragraph of the global annotations. Every
  fact the bridge relies on was re-verified against the afm binary itself.
- `argparse` (inline, `goga/pipeline`) — the CLI parsing rules, now three
  subcommands; `hook` has no options and receives the event through the process
  environment and stdin.
- `cli_entrypoint` (inline, `goga/pipeline`) — the thin `__main__` delegation with
  the docker guard; unchanged — the hook entry rides the same entrypoint, so
  `ensure_in_docker` covers it (the ADR's reason to reject a dedicated module).

### Imported Usages

- `checkpoints` from `goga/pipeline/hooks` (imported by `goga/pipeline`) — source
  path `goga/pipeline/hooks/.usages/checkpoints.md`; the "Emit the bridged
  run-interior events" section (already present in the working tree) documents
  exactly the consumption shape the bridge implements: build the surface per event
  process, emit once, exit.
- `declaring-actions` from `goga/hooks` (imported by `goga/pipeline/hooks`) —
  source path `goga/hooks/.usages/declaring-actions.md`; the emission contract
  both new methods reference ("Emit at the checkpoint" — `emit_hook_event` with
  the shared `context_for`); the catalog record addition is the practice's
  "Declare the action" step, `soft` class.
- `registering-hooks` from `goga/hooks` (imported by `goga/pipeline/hooks`) — the
  hook signature and failure handling behind every checkpoint; unchanged
  application.
- `per-tool-delivery` from `goga/hooks` (imported by `goga/pipeline/hooks`) — the
  amendment loop only; NOT used by the bridged emissions (fire-and-forget, no
  staged commit).
- `resolve-wrapper-path` from `goga/agents` (imported by `goga/pipeline`) — the
  agent command resolution the hook entry does not touch; unchanged consumer.

### Local Usages

None created or updated by this plan. The design's `.usages/` review found every
file current, and the single approved supplement is ALREADY applied in the working
tree (verified): `goga/pipeline/.usages/run-pipeline.md` carries the observer-hook
registration paragraph (the always-on global-layer entry, the fifteen-action
bridging, the boundary split, the authored-global-layer consequence —
self-contained, no cross-references, per the cookbook isolation rule). The
bridged events belong to the existing functional domains of the two cells, so the
existing files were supplemented, not split. `CODEMANIFEST` changes for all three
cells are likewise already applied in the working tree.

### External Dependencies

- **afm binary ≥ v1.2.17** (in-container, `/srv/afm`) — the lifecycle-hooks
  mechanism; not a Python dependency. Registration per "goga's stance" (global
  layer, whole-file rewrite); parsing per "JSON payload (stdin)"; env per
  "`AFM_*` environment"; exit semantics per "Failure semantics and delivery
  guarantees".
- `pyyaml` (pinned) — `yaml.safe_dump` of the afm configuration.
- `jinja2` (pinned) — stays in the `cli.py` top-level import set
  (`UndefinedError` for the card branch); platform-free, verified.
- pytest / pytest-cov / ruff (test extras, pinned) — no new versions required.

## Facts

- The working tree already carries the contract side: `goga/hooks/catalog/CODEMANIFEST`
  (+3 Requirements bullets), `goga/pipeline/hooks/CODEMANIFEST` (+4 types, +2
  methods), `goga/pipeline/CODEMANIFEST` (+4 routines, amended `argparse` practice,
  extended `write_afm_config` / `pipeline_cli`), the `run-pipeline.md` supplement,
  and `docs/features/pipelines/hooks.md` (eighteen actions, contexts, delivery
  contract). `goga lint` is clean over 91 cells / 0 errors.
- `_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py` currently lists exactly 34
  records; the pipeline group holds 3 (`amend_workflow` hard, `run_created` soft,
  `run_completed` soft); `tests/hooks/catalog/test_catalog.py` pins `len == 34` at
  six assertion sites (lines ~161, 201, 285, 304, 333, 486) and pins the pipeline
  group's exact sorted three-name list at ~line 328 — seven adaptation sites in
  total.
- `goga/pipeline/hooks/__init__.py` `__all__` lists 11 names; `ZONE_ALL` in
  `tests/pipeline/hooks/conftest.py` mirrors the same 11;
  `tests/pipeline/test_pipeline_contract.py::test_facade_all_has_fifteen_names`
  pins 15.
- `goga/pipeline/hook_bridge.py` does not exist; `goga/pipeline/__init__.py` has 15
  static imports and `__all__`; `goga/__init__.py` statically imports `AST` and
  `app`.
- `cli.py` statically imports `describe_pipeline` (line 13) and `run_pipeline`
  (line 17) at module top and reads `args.info` unconditionally at dispatch
  (line 302) — the hook branch must bind on `args.command` first.
- Measured import costs (design): full static chain ~450 ms/process — ~390 ms root
  facade (all 17 platform modules after a bare `import goga`), ~86 ms in-container
  chain (jinja2+yaml ~44 ms of that). The fast path (non-curated) imports stdlib
  only (~tens of ms).
- afm payload facts (binary-verified JSON tags): flow block
  `{name, run_id, resumed, run_dir, root_dir}`; stage block `{id, name, from, to,
  phase}`; event facts `event_id`, `occurred_at`, `reason`; afm event catalog —
  flow (5), stage (13), script (9); curated set is exactly 15.
- afm runs one hook's invocations sequentially — no concurrent bridge processes of
  the same hook (single registration `id: goga`); every event is a fresh process
  with fresh module state.
- The platform (`goga/hooks`) needs no changes: `emit_hook_event` address
  resolution is data-driven over `declared_actions()`; `wrap_context` delivers a
  fresh read-only `_DeliveryProxy` per subscription; soft failures log
  `WARNING` and continue.
- Test infrastructure reuse (see Mandatory Rules → Test Writing Rules): the
  boundary fixtures, the autouse in-container context, `config_path`,
  `is_kw_only_dataclass`, `ZONE_ALL` / `field_defaults`, and the
  sys.modules-shadowing mock pattern.
- No `.venv` exists in the workspace; the system interpreter lacks pytest/ruff —
  the environment bootstrap (Task 1) creates it and installs `.[test]`.

## Gap Analysis

- **Missing contract entities**: `hook_bridge.py` entirely absent (`run_hook`,
  `map_event_action`, `build_run_event`, `build_stage_event`); the four context
  models absent from `contexts.py`; `emit_run_event` / `emit_stage_event` absent
  from `events.py`.
- **Missing facade exposure**: zone `__all__` lacks the four context names
  (11 → 15); pipeline `__all__` lacks the four bridge names (15 → 19);
  `ZONE_ALL` and the pipeline-contract test pin the old counts.
- **API / behavior mismatches vs the contract**: `_DECLARED_ACTIONS` lacks the 15
  records (34 ≠ 49); `write_afm_config` writes no `hooks` entry; `pipeline_cli`
  declares no `hook` subparser and its dispatch would raise `AttributeError` on a
  hook Namespace (`args.info` read before the command branch); `cli.py`,
  `goga/pipeline/__init__.py`, and `goga/__init__.py` statically import the
  platform — the fast-path guarantee is unachievable without D1.
- **Existing code reused (not rewritten)**: `_ensure_registry` (lazy registry),
  `emit_hook_event` / `wrap_context` / `build_hook_arguments` (platform delivery),
  the `contexts.py` dataclass idiom, the `config_path` fixture and
  `_AFM_CONFIG_PATH` patch point, the boundary fixtures, the shadowing-aware mock
  pattern.
- **Test coverage gaps**: no bridge suite exists; the catalog suite pins the old
  count (adapt 7 sites: 34 → 49 total, pipeline group 3 → 18); the facade contract
  suites pin the old `__all__` sizes; no test pins the process-level import
  discipline.
- **Out of scope (explicitly untouched)**: `run_pipeline`, `describe_*`, the
  compiler, the workflow layer, the host-side launcher, the flow-file bytes and
  CLI outputs of a no-tool-packages run (byte-identical) — the sole exception is
  the mechanical lazy-`__getattr__` change of `goga/__init__.py` (facade mechanics
  only, no behavior, no surface change). No docs or `.usages/` work (already
  applied).

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before
> starting the next. Package order: `goga/hooks/catalog` → `goga/pipeline/hooks` →
> `goga/pipeline`. Within each coding task, contract tests are written first (TDD
> workflow). Only ONE task is executed per ralphex iteration.

### Task 1: Catalog — the fifteen bridge records (TDD coding)

<Context: the leaf cell `goga/hooks/catalog` (dir `goga/hooks/catalog/`) extends
`_DECLARED_ACTIONS` in `catalog.py` with the 15 new soft pipeline records per D6.
This is the enablement for everything downstream — the bridged emissions resolve
their addresses through `declared_actions()`, so every later task depends on this
one. The entity is the existing routine `declared_actions() -> actions:
list[Action]`; the change is purely additive data (no published record rewritten).
This task ALSO bootstraps the development environment (virtualenv + test extras) —
the workspace has no `.venv` and the system interpreter lacks pytest/ruff.>

**Usages relevant to this task:**
- `convention`: data-model rules (`Action` stays the frozen `kw_only` dataclass it
  is — only the LIST gains entries), docstring style, relative imports; the
  Mandatory Rules above apply in full (REPL loop, lint gates, commit policy).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. The contract changes are already applied in the working tree. If
implementation does not match the contract, fix the implementation — never fix
the contract.**

- [x] **STEP 0 (DECLARATION + environment)**: declare this task; bootstrap the
      virtualenv — `python3 -m venv .venv && .venv/bin/pip install -e ".[test]"`;
      verify the BASELINE is green before any change: `.venv/bin/ruff check goga/
      tests/`, `.venv/bin/ruff format --check goga/ tests/`, `.venv/bin/pytest
      tests/ -x`, `goga lint` (0 errors / 91 cells; re-run once on a surprising
      failure — the command is occasionally flaky)
- [x] **STEP 1 (Contract tests)**: in `tests/hooks/catalog/test_catalog.py`, adapt
      the six `len(...) == 34` assertion sites (lines ~161, 201, 285, 304, 333,
      486) to the new total 49, and extend the pipeline-group exact-list assertion
      (~line 328, `pipeline == [...]`) to the eighteen sorted pipeline names (the
      suite already asserts per-domain groupings; keep its structure) — and add
      `test_declared_actions_carries_the_fifteen_bridge_records` (class
      `TestCatalogLogic` or a new `class TestBridgeRecords:`): `pipeline_records =
      [a for a in declared_actions() if a.domain == "pipeline"]` → exactly 18
      elements; `("pipeline", "run_resumed", "soft")` and `("pipeline",
      "run_interrupted", "soft")` present; for each of the thirteen stage names
      (`stage_planning_started`, `stage_plan_ready`, `stage_approved`,
      `stage_revision_started`, `stage_execution_started`,
      `stage_question_asked`, `stage_question_answered`,
      `stage_retry_scheduled`, `stage_retry_started`, `stage_paused`,
      `stage_resumed`, `stage_finished`, `stage_failed`): `("pipeline", <name>,
      "soft")` present; the three pre-existing records (`amend_workflow` hard,
      `run_created` soft, `run_completed` soft) unchanged and present;
      `pipeline_records == sorted(pipeline_records, key=lambda a: a.name)` (the
      derived order). Expected to fail at this stage — this is correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL — evaluate
      `declared_actions()` and confirm where the 15 names land under
      `sorted(key=(domain, name))` (design-verified order:
      `run_interrupted`, `run_resumed`, then `stage_*` alphabetically with
      `stage_resumed` BEFORE `stage_revision_started`); then in
      `goga/hooks/catalog/catalog.py`, append to `_DECLARED_ACTIONS` in the
      pipeline group, after the `run_completed` record (D6): 15
      `Action(domain="pipeline", name=..., error_class="soft")` records — the two
      run-level names and the thirteen stage names, afm catalog order within the
      group is irrelevant (the public sort derives the order); change nothing else
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/hooks/catalog/test_catalog.py -v` — all pass, including the adapted
      counts; facade check `.venv/bin/python -c "from goga.hooks.catalog import
      declared_actions; assert len(declared_actions()) == 49"`
- [x] **STEP 4 (Logic tests)**: none beyond STEP 1 — the catalog is maintained
      data; the record test IS the logic coverage (mock-free, per the suite's own
      header)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — the full battery
      stays green (downstream suites must not depend on the count; any failure is
      fixed in code, never by weakening an unrelated test)
- [x] **STEP 6 (Contract re-verification)**: `declared_actions()` returns 49
      records, deterministic `(domain, name)` order, no existing record rewritten;
      the 15 new addresses resolve (`emit_hook_event` resolution is data-driven —
      no dispatch change needed)
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations; fix formatting if necessary
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit with all gates green and
      NO `Co-Authored-By:` trailer → REVIEW → APPROVAL → NEXT TASK

### Task 2: Zone contexts — the four bridged models + zone facade (TDD coding)

<Context: the cell `goga/pipeline/hooks` (dir `goga/pipeline/hooks/`) gains the
four passthrough context models in `contexts.py` and exports them from the zone
facade. Entities: `RunIdentity`, `StageTransition`, `RunEvent`, `StageEvent`
(exact signatures in the Contract Surface above — `reason: str = ""` last in both
event models). They are pure fact bundles: `@dataclass(kw_only=True)`, no methods,
no validation, no frozen — the identical shape as the existing
`CompositionStage` / `RunCreated` / `RunCompleted` in the same file (which already
imports `dataclass` and uses `from __future__ import annotations`). The zone
facade `__init__.py` grows `__all__` 11 → 15 (+ the four names, imported from
`.contexts`, alphabetical) and the test scaffolding mirrors it (`ZONE_ALL`
11 → 15 in `tests/pipeline/hooks/conftest.py`). Placement: the four classes join
`contexts.py` after `RunCompleted`.>

**Usages relevant to this task:**
- `convention`: `kw_only=True` dataclasses with Google docstrings (`Args:` block
  per field — the file's own precedent), relative imports (`.identity` untouched
  here), blank-line block formatting.
- `declaring-actions` (imported by the zone): the contexts are the fact vocabulary
  the emission of Task 3 delivers — field names match the manifest signatures
  exactly so consumers locate them unambiguously.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm the Task 1 gates are
      green (the venv exists)
- [x] **STEP 1 (Contract tests)**: in `tests/pipeline/hooks/` (extend the existing
      contexts suite or add `tests/pipeline/hooks/test_bridged_events.py` with a
      contract class): the four names are importable from
      `goga.pipeline.hooks`; `sorted(goga.pipeline.hooks.__all__)` equals the
      updated `ZONE_ALL` of 15 names; each class passes `is_kw_only_dataclass`
      (from `tests.conftest`); `field_defaults(RunEvent)` /
      `field_defaults(StageEvent)` show `("reason", "")` as the LAST field with
      every earlier field `MISSING`; constructor signatures match the contract
      (`inspect.signature` parameter order). Expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      construct `RunEvent(pipeline="deploy", run=RunIdentity(...), event_id="e",
      occurred_at="t")` without `reason` and confirm the default, and confirm no
      non-default field follows `reason` (dataclass ordering rule); then in
      `goga/pipeline/hooks/contexts.py` append the four dataclasses with the
      declared fields in the declared order, `@dataclass(kw_only=True)`, Google
      docstrings carrying each field's contract description (e.g. `occurred_at`:
      "the event moment as an ISO-8601 UTC string"); update
      `goga/pipeline/hooks/__init__.py`: import `RunCompleted, RunCreated,
      RunEvent, RunIdentity, StageEvent, StageTransition` grouping with
      `CompositionStage` from `.contexts`, `__all__` 11 → 15 alphabetical;
      update `ZONE_ALL` in `tests/pipeline/hooks/conftest.py` to the same 15
      names (and its docstring "eleven-name" → "fifteen-name")
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/hooks/ -v` — all pass; facade checks: `.venv/bin/python -c
      "from goga.pipeline.hooks import RunEvent, RunIdentity, StageEvent,
      StageTransition"`
- [x] **STEP 4 (Logic tests)**: construction passthrough — build each model with
      keyword arguments and assert every field carries its value verbatim;
      `RunIdentity` equality comparison of two identical constructions
      (dataclass `__eq__`); `StageTransition` carries `from_status` / `to_status`
      (no `from` / `to` attribute exists — `not hasattr(transition, "from")`)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix implementation
      code until all pass (do NOT fix test code)
- [x] **STEP 6 (Contract re-verification)**: facade obligation met (the four names
      on `goga.pipeline.hooks` and in `__all__`); field names/types/defaults match
      the CODEMANIFEST signatures exactly; no other zone entity touched
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 3: Zone surface — `emit_run_event` / `emit_stage_event` (TDD coding)

<Context: the cell `goga/pipeline/hooks` (dir `goga/pipeline/hooks/`) adds the two
soft-emission methods to `PipelineHooks` in `events.py`. Both delegate to the
platform's `emit_hook_event` with the caller-built context — the whole point of
the bridged methods (unlike `emit_run_created`, they do NOT construct the
context). Signatures: `emit_run_event(self, action: str, context: RunEvent) ->
None` and `emit_stage_event(self, action: str, context: StageEvent) -> None` —
intentionally symmetric, one per context type, no union parameter. Algorithm:
`registry ← self._ensure_registry()` then
`emit_hook_event(registry, "pipeline", action, context_for=lambda _tool:
context)`. The address resolves against `declared_actions()` — Task 1's records
must already exist. Subscriber soft failures warn inside the platform and never
surface as a raise; an unknown action raises `ValueError` from the platform's
address resolution. The methods add no logging of their own. New test home:
`tests/pipeline/hooks/test_bridged_events.py`.>

**Usages relevant to this task:**
- `declaring-actions` (from `goga/hooks`): the emission contract — "Emit at the
  checkpoint": `emit_hook_event` with the shared `context_for`; one shared
  read-only context instance per emission.
- `registering-hooks` (from `goga/hooks`): the hook signature behind the
  checkpoint — subscribers declare `context` (and optionally `self`) parameters;
  `build_hook_arguments` projects exactly those.
- `checkpoints` (the zone's own practice, `goga/pipeline/hooks/.usages/
  checkpoints.md`): the "Emit the bridged run-interior events" section documents
  the consumption shape these methods implement.
- `per-tool-delivery` (from `goga/hooks`): explicitly NOT applied here — that
  practice governs the staged amendment loop of `amend_workflow` only; the
  bridged emissions are fire-and-forget with no staged commit. Do not import its
  loop skeleton into these methods.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Tasks 1–2 gates green
- [x] **STEP 1 (Contract tests)**: in the new
      `tests/pipeline/hooks/test_bridged_events.py`: both methods exist on
      `PipelineHooks` with the exact signatures (`inspect.signature` —
      `(action: str, context: RunEvent)` / `(action: str, context: StageEvent)`,
      return annotation `None`); `PipelineHooks()` construction stays cheap (no
      registry attribute after `__init__` — `hooks._registry is None`). Expected
      to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL with the
      boundary fixtures' building blocks — register one fake tool subscribed to
      `("pipeline", "stage_execution_started", "notify", hook)`, call
      `emit_hook_event` directly with a `context_for` lambda, and confirm (a) the
      hook receives a `_DeliveryProxy` (not the raw instance), (b) a DIRECT
      assignment on the delivered view raises `AttributeError`, (c) a nested read
      resolves the raw nested object; then implement both methods in
      `goga/pipeline/hooks/events.py` after `emit_run_completed`, importing
      `RunEvent` / `StageEvent` from `.contexts`, each a 2-statement body
      (`registry = self._ensure_registry()`; `emit_hook_event(registry,
      "pipeline", action, context_for=lambda _tool: context)`) with Google
      docstrings (fire-and-forget, shared read-only context, soft failure
      semantics)
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/hooks/test_bridged_events.py tests/pipeline/hooks/ -v` — all
      pass
- [x] **STEP 4 (Logic tests)**: in `test_bridged_events.py`:
      `test_emit_stage_event_delivers_shared_read_only_context` (design,
      verbatim) — setup: `pin_package_environment({"goga_tool_reporter":
      ["goga-tool-reporter"], "goga_tool_mirror": ["goga-tool-mirror"]})`, two
      installed tools each subscribing `("pipeline", "stage_execution_started",
      "notify", hook)`; each hook captures its own `context` parameter and probes
      a DIRECT assignment (`try: context.reason = "x"` → capture
      `AttributeError`) — a nested write such as `context.stage.name = "x"` would
      resolve `stage` through the proxy onto the raw dataclass and mutate it
      silently, so the probe must assign on the delivered view itself; input: a
      `StageEvent` built from the design's payload facts; call
      `hooks.emit_stage_event("stage_execution_started", context)`;
      assertions: `reporter_ctx.stage is context.stage` and `mirror_ctx.stage is
      context.stage` (nested facts read through the proxy are the very same
      objects — one shared context behind the per-subscription proxies);
      `reporter_ctx.stage is mirror_ctx.stage`; `reporter_ctx.stage.name ==
      "Build"`; `mirror_ctx.event_id == "run-42:transition:7:
      stage_execution_started"`; `write_error is AttributeError`; the emit
      returned `None` and raised nothing. NOTE: `captured is context` is asserted
      nowhere ON PURPOSE — the subscriber receives the `_DeliveryProxy`, never
      the raw instance; the shared-instance rule is observable through the
      nested-fact identity. Plus
      `test_emit_run_event_unknown_action_raises_clean_error` — package
      environment pinned empty; `pytest.raises(ValueError, match="unknown hook
      action")` around `PipelineHooks().emit_run_event("not_an_action",
      RunEvent(...))`. Plus
      `test_bridged_surface_registry_built_once_per_process` — one subscribed
      tool, the enumeration boundary mocked with a call counter;
      `emit_run_event("run_resumed", ctx1)` then `emit_stage_event(
      "stage_paused", ctx2)` on the SAME surface; assert the boundary call count
      == 1
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — fix implementation
      code until all pass
- [x] **STEP 6 (Contract re-verification)**: methods on the facade class, exact
      signatures, fire-and-forget (`None` return), no new logging, no context
      construction inside the methods, `_ensure_registry` reuse untouched
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 4: The bridge module — `hook_bridge.py` (TDD coding)

<Context: the cell `goga/pipeline` (dir `goga/pipeline/`) gains the new file
`goga/pipeline/hook_bridge.py` with four routines — `run_hook`, `map_event_action`,
`build_run_event`, `build_stage_event` — the afm-facing bridge entry. THE LAZY
IMPORT DISCIPLINE IS THE CONTRACT (D1 item 1): the module top imports stdlib only
(`json`, `os`, `sys`, `typing.Any`, `__future__` annotations); every `goga` import
lives inside a function body (`from .hooks import PipelineHooks` inside `run_hook`,
function-local, AFTER the curated filter); annotations for the zone types use a
`TYPE_CHECKING` block. Never hoist a `goga` import "for cleanliness" — the
fast-path test of Task 8 fails the moment one rises to the top. Module-level
data: `_EVENT_ACTION_MAP: dict[str, str]` (the 15-pair curated mapping — 13
verbatim stage names, `flow_resumed → run_resumed`, `flow_interrupted →
run_interrupted`) and `_RUN_LEVEL_ACTIONS: frozenset[str] =
frozenset({"run_resumed", "run_interrupted"})` (D3). Shared private helpers
`_flow_block`, `_run_identity`, `_event_facts`, `_stage_block` keep the two
builders in step (a divergence is structurally impossible). Full algorithms in
the Contract Surface above — implement them exactly. New test home:
`tests/pipeline/test_hook_bridge.py` (all bridge tests EXCEPT the Task 8
subprocess proof).>

**Usages relevant to this task:**
- `afm` (`.goga/usages/cooks/afm.md`): the execution model of the hook command —
  the launch shape (`sh -c "python3 -m goga.pipeline hook"`, CWD = flow root_dir,
  JSON payload on stdin, `AFM_*` in the inherited env) and the failure semantics
  (non-zero exit recorded in the per-hook log, the run unaffected).
- `convention`: Google docstrings with `Args`/`Returns`/`Raises`, relative
  imports, blank-line block formatting, type hints (`dict[str, Any]`, `str |
  None`).
- `checkpoints` (imported from the zone): the "Emit the bridged run-interior
  events" consumption shape — build the surface per event process, emit once,
  exit.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Tasks 1–3 gates green
- [x] **STEP 1 (Contract tests)**: in the new `tests/pipeline/test_hook_bridge.py`:
      the four names defined on the module; `map_event_action` signature
      `(event: str) -> str | None`; `build_run_event` / `build_stage_event`
      signatures `(payload: dict[str, Any]) -> RunEvent / StageEvent`; `run_hook`
      signature `() -> int`; the module top is stdlib-only — assert
      `hook_bridge`'s import introduces no `goga.hooks`/`goga.pipeline.hooks`
      module into `sys.modules` (probe in a FRESH `python -c` child:
      `import goga.pipeline.hook_bridge; import sys; assert not [m for m in
      sys.modules if m.startswith(("goga.hooks", "goga.pipeline.hooks"))]`).
      Expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL against
      the design's afm-shaped payload dict — `json.loads` round-trip, the
      `payload.get("reason") or ""` JSON-null behavior (`{"reason": None}` →
      `""`), the `KeyError`-free named-`ValueError` reads; then create
      `goga/pipeline/hook_bridge.py`: module docstring; stdlib-only imports;
      `from __future__ import annotations`; `TYPE_CHECKING` block importing
      `RunEvent` / `StageEvent` from `.hooks.contexts`; the two module-level
      literals; the four private helpers (each raising its clean `ValueError`
      naming the missing fact: "lifecycle event payload carries no flow block" /
      "stage-level lifecycle event payload carries no stage block" / naming the
      missing event fact); the four public routines per the Contract Surface
      algorithms — `run_hook` catches exactly `(ValueError, ImportError,
      OSError)` and renders `Error: <reason>` to stderr; the reason reader uses
      `payload.get("reason") or ""`
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/test_hook_bridge.py -v` (contract classes) — pass; the
      fresh-child stdlib-only probe passes
- [x] **STEP 4 (Logic tests)**: in `tests/pipeline/test_hook_bridge.py`
      (manipulate the two process inputs directly: `monkeypatch.setenv(
      "AFM_HOOK_EVENT", …)` and `monkeypatch.setattr("sys.stdin",
      io.StringIO(...))`):
      `test_map_event_action_resolves_the_curated_vocabulary` — parametrized over
      all fifteen pairs: the thirteen (`"stage_plan_ready"`, `"stage_failed"`,
      …) mapping to themselves; `("flow_resumed", "run_resumed")`;
      `("flow_interrupted", "run_interrupted")`;
      `test_map_event_action_returns_none_outside_the_curated_vocabulary` —
      parametrized: `"flow_started"`, `"flow_finished"`, `"flow_failed"`,
      `"stage_script_started"`, `"stage_script_after_finished"`,
      `"agent_action"`, `"script_output"`, `""`, `"not_an_event"` → all `None`;
      `test_build_stage_event_composes_the_transition_context` (design, verbatim)
      — payload `{"schema_version": 1, "event_id": "run-42:transition:7:
      stage_execution_started", "event": "stage_execution_started",
      "occurred_at": "2026-10-21T12:00:00Z", "flow": {"name": "deploy",
      "run_id": "run-42", "resumed": False, "run_dir":
      "/home/goga/pipeline/runs/run-42", "root_dir": "/workspace"}, "stage":
      {"id": "build", "name": "Build", "from": "approved", "to": "executing",
      "phase": "execution"}}`; assert `context.pipeline == "deploy"`;
      `context.run == RunIdentity(run_id="run-42", run_dir="/home/goga/
      pipeline/runs/run-42", root_dir="/workspace", resumed=False)`;
      `context.stage.from_status == "approved"` and `context.stage.to_status ==
      "executing"`; `context.stage.id == "build"`, `.name == "Build"`,
      `.phase == "execution"`; `context.event_id == "run-42:transition:7:
      stage_execution_started"`; `context.occurred_at == "2026-10-21T12:00:00Z"`;
      `context.reason == ""` (absent in the payload); `not
      hasattr(context, "schema_version")` and `not hasattr(context, "event")`;
      `test_run_hook_bridges_a_curated_stage_event_end_to_end` — env
      `AFM_HOOK_EVENT=stage_execution_started`; stdin = the payload JSON above;
      one subscribed capturing fake tool; assert `result == 0`;
      `captured.pipeline == "deploy"` and `captured.stage.to_status ==
      "executing"`; `capsys.readouterr().out == ""` (happy path prints nothing);
      `test_run_hook_non_curated_event_exits_zero_without_reading_stdin` — env
      `AFM_HOOK_EVENT=stage_script_started`; `sys.stdin` monkeypatched to an
      object whose `read` raises `AssertionError` if called; package environment
      pinned empty with the enumeration boundary mocked; assert `result == 0`,
      stdin untouched, enumeration boundary not called (the registry never
      built);
      `test_run_hook_damaged_stdin_returns_nonzero_with_clean_message` — env
      `AFM_HOOK_EVENT=flow_resumed`; parametrized stdin `"{not json"` and `""`
      (empty stdin travels the same `JSONDecodeError` path); assert `result ==
      1`; `"Error:" in capsys.readouterr().err` and `"Traceback" not in err`;
      `test_run_hook_missing_flow_block_returns_nonzero` — env
      `AFM_HOOK_EVENT=stage_finished`; parametrized stdin: (a) payload with event
      facts and a `stage` block but no `flow` key, (b) payload with `"flow":
      "not-a-dict"`; assert `result == 1`; `"flow block" in
      capsys.readouterr().err` and `"Traceback" not in err`;
      `test_run_hook_missing_stage_block_returns_nonzero` — env
      `AFM_HOOK_EVENT=stage_paused`; payload with the flow block and event facts
      but no `stage` key; assert `result == 1`; `"stage block" in
      capsys.readouterr().err`;
      `test_run_hook_missing_event_fact_names_the_fact` — env
      `AFM_HOOK_EVENT=flow_interrupted`; payload whose top level lacks
      `occurred_at`; assert `result == 1`; `"occurred_at" in
      capsys.readouterr().err`;
      `test_run_hook_non_object_json_is_a_bridge_failure` — env
      `AFM_HOOK_EVENT=stage_finished`; stdin `"[1, 2, 3]"`; assert `result == 1`;
      `"not a JSON object" in err`;
      `test_run_hook_null_reason_lands_as_empty_string` — env
      `AFM_HOOK_EVENT=flow_resumed`; payload with `"reason": None`; a capturing
      subscriber; assert `result == 0`; `captured.reason == ""`;
      `test_run_hook_subscriber_failure_and_empty_registry_exit_zero` — two
      scenarios: (a) `pin_package_environment({"goga_tool_boom":
      ["goga-tool-boom"]})` with a tool subscribed to `pipeline / stage_paused`
      whose hook raises `RuntimeError("boom")`; `caplog` at the platform logger
      level; env `AFM_HOOK_EVENT=stage_paused`; a full valid stage payload;
      assert `result == 0`, `"Error:" not in capsys.readouterr().err`, one
      WARNING record in caplog carrying "stage_paused" and "boom"; (b)
      `pin_package_environment({})` — empty registry; same curated event; assert
      `result == 0`; `capsys.readouterr() == ("", "")`
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/pipeline/ -x` then the full
      battery — fix implementation code until all pass
- [x] **STEP 6 (Contract re-verification)**: every `goga` import still inside a
      function body; error discipline exactly 0/0/0-vs-1 per the ADR; the
      curated filter precedes any platform import at the function level; the
      raw payload never attaches to a context; only stdin and `AFM_*` read
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations (watch ARG/PL rules on the helpers; `# noqa` only with the
      family comment if truly needed)
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 5: Registration — the observer hook entry in `write_afm_config` (TDD coding)

<Context: the cell `goga/pipeline` (dir `goga/pipeline/`) extends
`write_afm_config(agent)` in `afm_config.py`: the composed content additionally
carries goga's observer hook entry in the global `hooks` layer —
`content["hooks"] = [{"id": "goga", "events": "all", "command": "python3 -m
goga.pipeline hook", "inherit_env": True}]` (D2, binary-verified field names).
`timeout` / `retries` are intentionally OMITTED (afm `omitempty` → defaults
30 s / 0); no `env` map. The entry is a fixed constant appended after the four
static fields; the whole-file rewrite discipline and `_AFM_CONFIG_PATH` stay
unchanged (tests redirect it via the existing `config_path` fixture /
`_in_container_run_context` autouse). Signature unchanged. Extend
`tests/pipeline/test_afm_config.py`.>

**Usages relevant to this task:**
- `afm`: the configuration-file contract — the lifecycle-hooks registration of
  the observer hook entry (global layer, field names, `omitempty` defaults) and
  goga's registration stance (whole-file authorship).
- `resolve-wrapper-path` (imported from `goga/agents`): the agent command
  resolution the hook entry does not touch — unchanged consumer.
- `convention`: docstring updates (`Returns:` describes the hooks entry),
  programmatic serialization only.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Task 4 gates green
- [x] **STEP 1 (Contract tests)**: the existing contract class of
      `tests/pipeline/test_afm_config.py` (importable from facade, `(agent) ->
      Path` signature) must keep passing unchanged — run it first and confirm it
      is red ONLY if the suite's own content assertions anticipate the entry;
      then add the failing logic test
      `test_write_afm_config_registers_the_observer_hook` (STEP 4 below) as the
      contract-shape driver
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL — call
      `write_afm_config("codex")` with `_AFM_CONFIG_PATH` redirected into a tmp
      dir, `yaml.safe_load` the file back, and confirm the entry shape and the
      field order; then edit `goga/pipeline/afm_config.py`: after the
      `content.update({...four static fields...})` block add the `hooks` list
      (a module-level constant dict is acceptable if it keeps the literal in one
      place — but keep it simple: the inline literal per the design algorithm);
      extend the docstring's content description with the observer entry; change
      nothing else (path constant, `resolve_wrapper_path` call, `safe_dump`
      arguments stay)
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/test_afm_config.py -v` — the existing with/without-agent
      tests pass (if any pre-existing exact-content assertion breaks, extend it
      with the `hooks` key — the live contract wins); facade check
      `.venv/bin/python -c "from goga.pipeline import write_afm_config"`
- [x] **STEP 4 (Logic tests)**:
      `test_write_afm_config_registers_the_observer_hook` (design, verbatim) —
      setup: the `config_path` fixture; input: `write_afm_config("codex")`;
      re-read via `yaml.safe_load(path.read_text())`; assertions:
      `parsed["hooks"] == [{"id": "goga", "events": "all", "command":
      "python3 -m goga.pipeline hook", "inherit_env": True}]`;
      `set(parsed["hooks"][0]) == {"id", "events", "command", "inherit_env"}`
      (no timeout/retries/env); `parsed["client"]["command"] ==
      "/home/goga/bin/codex-as-claude.sh"` (the unchanged fields intact —
      resolve_wrapper_path("codex") resolves this in the test environment);
      `parsed["theme"] == "goga"` and `parsed["open_browser"] is False`;
      `parsed["proxy"] == {"enabled": False}`; `parsed["prompts_dir"] ==
      "/home/goga/pipeline/prompts"`. Also: the agentless form still registers
      the hook (a `write_afm_config(None)` variant asserting `parsed["hooks"]`
      present and `"client" not in parsed`) and the idempotence invariant (two
      consecutive invocations leave exactly one entry)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — the full battery
      stays green (`run_pipeline` wiring tests that snapshot the written config
      may need the `hooks` key added to their expected documents — live run
      wins, report the disagreement)
- [x] **STEP 6 (Contract re-verification)**: exact D2 shape; nothing
      configurable; the file lands only at the fixed path; nothing printed
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 6: CLI — the `hook` subcommand + branch-local imports (TDD coding)

<Context: the cell `goga/pipeline` (dir `goga/pipeline/`) extends `pipeline_cli`
in `cli.py`: a third subparser `hook` with NO arguments, and a dispatch branch
that binds on `args.command` BEFORE any read of `args.info` (the hook subparser
declares no `--info`, so its Namespace carries no `info` attribute — a branch
placed after the unconditional `if args.info:` read would raise `AttributeError`
on every hook invocation). The branch is pure delegation: `return run_hook()`.
Simultaneously apply D1 item 2: move `from .describe_pipeline import
describe_pipeline` and `from .run_pipeline import run_pipeline` from the module
top INTO the branch functions that use them (`_run_card`, `_run_execution`) so
the `hook` fast path never loads them; add `from .hook_bridge import run_hook`
to the module top (its module is stdlib-only, so the import is cheap); the
remaining top-level imports are platform-free — do not restructure anything
else. Extend `tests/pipeline/test_pipeline_cli.py` (mind the sys.modules
shadowing mock pattern of that suite: `_cli_module = sys.modules[
"goga.pipeline.cli"]`).>

**Usages relevant to this task:**
- `argparse` (inline practice): three subcommands — `hook` has no options and
  receives the event through the process environment and stdin; extra tokens
  are argparse errors (exit 2).
- `cli_entrypoint` (inline practice): `__main__` stays a thin delegation with the
  docker guard — untouched here; the hook entry rides the same entrypoint.
- `convention`: docstring style; the `--help` strings are the user-facing
  surface.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task; confirm Task 5 gates green
- [x] **STEP 1 (Contract tests)**: in `tests/pipeline/test_pipeline_cli.py`:
      `--help` output lists the `hook` subcommand; the parser declares no option
      for it (parse `["hook"]` succeeds into `Namespace(command="hook")`);
      expected to fail — correct
- [x] **STEP 2 (REPL probe + implementation)**: probe in the venv REPL —
      scratch-call `pipeline_cli(["hook", "--port", "1"])` and confirm the
      `SystemExit(2)` + usage-on-stderr shape BEFORE writing the test; then edit
      `goga/pipeline/cli.py`: (a) in `_build_parser` add
      `subparsers.add_parser("hook", help="afm-facing machinery: bridge one
      lifecycle event")` — no arguments; (b) remove the two top-level imports
      (`describe_pipeline`, `run_pipeline`), add `from .hook_bridge import
      run_hook`; (c) move the two imports into `_run_card` / `_run_execution`
      as their first statement (function-local, per D1); (d) in `pipeline_cli`
      dispatch, add the hook branch BEFORE the unconditional `if args.info:`
      read: `if args.command == "hook": return run_hook()`; update the module
      and function docstrings (three subcommands / five operations)
- [x] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/test_pipeline_cli.py -v` — the pre-existing list/run suites
      pass unchanged (the import moves change no behavior)
- [x] **STEP 4 (Logic tests)**:
      `test_pipeline_cli_hook_dispatches_and_returns_the_code` (design,
      verbatim) — setup: `mock.patch.object(_cli_module, "run_hook",
      return_value=0)` (the shadowing-safe pattern); input:
      `pipeline_cli(["hook"])`; assertions: `result == 0`;
      `mock.assert_called_once_with()`; `capsys.readouterr() == ("", "")`;
      `test_pipeline_cli_hook_rejects_options` (design, verbatim) — for both
      `["hook", "--port", "1"]` and `["hook", "extra"]`:
      `with pytest.raises(SystemExit) as exc_info: pipeline_cli(argv)`;
      `exc_info.value.code == 2`; `"usage:" in capsys.readouterr().err`
      (argparse errors are SystemExit, not returned codes — the suite's own
      precedent); plus a delegation-failure pass-through: a mocked
      `run_hook` returning 1 → `pipeline_cli(["hook"]) == 1` (pure delegation,
      no CLI-side catch)
- [x] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — the full battery
      stays green
- [x] **STEP 6 (CONTRACT RE-VERIFICATION + import trace)**: the dispatch order
      holds (hook binds before any `args.info` read); re-verify D1 item 2 by
      measurement in a fresh child: `python -c "import sys, goga.pipeline.cli
      as c; ..."` — assert `goga.pipeline.describe_pipeline` and
      `goga.pipeline.run_pipeline` are NOT in `sys.modules` after importing the
      cli module
- [x] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [x] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 7: Facades — the four bridge names + the lazy re-export pairs (TDD coding)

<Context: the final D1 pieces. (A) `goga/pipeline/__init__.py`: add the four
STATIC imports from `.hook_bridge` (`build_run_event`, `build_stage_event`,
`map_event_action`, `run_hook`) — the module top is stdlib-only so the facade
import stays cheap — and grow `__all__` 15 → 19, alphabetical (D5). (B) The two
platform-carrying re-exports of the same facade (`describe_pipeline`,
`run_pipeline`) become LAZY via a PEP 562 module `__getattr__` that
`importlib.import_module`s the submodule on first attribute access (D1 item 3);
every other facade import stays static; the surface is unchanged —
`from goga.pipeline import run_pipeline` keeps working. (C) `goga/__init__.py`:
BOTH root re-exports (`AST` from `.ast`, `app` from `.cli`) become lazy via the
same mechanism; `__all__ = ["AST", "app"]` unchanged (D1 item 4) — this is the
dominant carrier (measured: all 17 platform modules, ~0.39 s after a bare
`import goga`); the interpreter imports `goga` before
`goga.pipeline.__main__` runs, so without this item the Task 8 fast-path test
cannot pass. Verified facts to rely on: the console script `goga =
"goga.cli:app"` imports `goga.cli` directly (unaffected); `from goga import app,
commands` keeps working (the import system falls back to importing the submodule
when the attribute lookup raises); no goga-internal module reads
`goga.app`/`goga.AST` at import time. Update the facade contract suite
`tests/pipeline/test_pipeline_contract.py` (fifteen → nineteen).>

**Usages relevant to this task:**
- `convention`: facade rules — `__all__` alphabetical, only listed identifiers
  constitute the facade; the `convention` REPL rule (fresh `python -c` child per
  probe — module-state changes demand a fresh interpreter).
- Language rule (`goga-cell-python`): the facade exposes the full contract API
  through `__all__`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task; confirm Task 6 gates green
- [ ] **STEP 1 (Contract tests)**: in `tests/pipeline/test_pipeline_contract.py`:
      update `test_facade_all_has_fifteen_names` → nineteen (rename accordingly)
      and add the four bridge names to the membership assertions; add
      `test_zone_and_cell_facades_export_the_new_names` (design, verbatim):
      `sorted(goga.pipeline.hooks.__all__) == ZONE_ALL` (15 names, incl. the
      four new); `"run_hook", "map_event_action", "build_run_event",
      "build_stage_event" in goga.pipeline.__all__` (19 total);
      `from goga.pipeline import run_pipeline` still resolves (the lazy pair) —
      `hasattr(pipeline_facade, "run_pipeline")` and `... "describe_pipeline"`;
      plus `from goga import app, AST` resolves and `goga.__all__ == ["AST",
      "app"]`. Expected to fail — correct
- [ ] **STEP 2 (REPL probe + implementation)**: probe PEP 562 semantics in a
      FRESH `python -c` child per check (never a warm REPL): `import goga;
      goga.app` triggers the submodule import and binds the attribute;
      `from goga import app, commands` works; `import goga.cli` still works;
      then implement: `goga/pipeline/__init__.py` — add the four static
      `.hook_bridge` imports, extend `__all__` to 19 alphabetical, add the
      module `__getattr__(name)` that maps `"describe_pipeline"` /
      `"run_pipeline"` to `importlib.import_module(".describe_pipeline" /
      ".run_pipeline", __name__)` attribute fetches and raises
      `AttributeError` for unknown names; `goga/__init__.py` — same mechanism
      for `AST` (`.ast`) and `app` (`.cli`), `__all__` unchanged; keep both
      module docstrings
- [ ] **STEP 3 (Interface verification)**: `.venv/bin/pytest
      tests/pipeline/test_pipeline_contract.py tests/pipeline/hooks/ -v` — pass;
      facade checks: `.venv/bin/python -c "from goga.pipeline import run_hook,
      map_event_action, build_run_event, build_stage_event, run_pipeline,
      describe_pipeline"` and `.venv/bin/python -c "from goga import app, AST"`
      and the console script `.venv/bin/goga --help` works
- [ ] **STEP 4 (Logic tests)**: laziness itself — a fresh-child probe (in the
      contract suite as a subprocess test or via the Task 8 home): `import
      goga` alone leaves NO `goga.commands.*` / `goga.hooks*` module in
      `sys.modules`; `import goga.pipeline` leaves `goga.pipeline.hooks`
      unimported; after touching `goga.pipeline.run_pipeline` the attribute is
      bound and `__getattr__` does not fire again for it
- [ ] **STEP 5 (Debugging)**: `.venv/bin/pytest tests/ -x` — the FULL battery
      green (this task touches every import path in the project; any regression
      is fixed in the facade code, never by deleting a test)
- [ ] **STEP 6 (Contract re-verification)**: both `__all__` surfaces exact
      (19 / ["AST", "app"]); every facade name importable; no behavior change
      anywhere else (the mechanical lazy-`__getattr__` change of
      `goga/__init__.py` is facade mechanics only)
- [ ] **STEP 7 (LINT + gates)**: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations
- [ ] **STEP 8 (COMPLETION)**: mark checkboxes; commit (gates green, no
      `Co-Authored-By:`) → REVIEW → APPROVAL → NEXT TASK

### Task 8: Integration — the process-level fast path + post-implementation verification (integration tests)

<Context: the cross-entity proof spanning all four D1 changes (hook_bridge stdlib
top, cli branch-local imports, the two lazy facades) and the post-implementation
verification checklist of the architecture plan (Docs + Cross-cutting items —
post-suite verifications, not unit tests). The whole feature is now implemented;
this task proves the process-level import discipline the design made a
performance requirement, then closes the verification checklist.>

**Usages relevant to this task:**
- `afm`: the execution model — one short-lived process per event; the per-hook
  log; observer semantics end-to-end.
- `convention`: integration tests live with the mirrored suite (the bridge
  suite); subprocess checks spawn REAL children — no mocks at this boundary.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify
them. If implementation does not match the contract, fix the implementation —
never fix the contract.**

- [ ] Create/extend the integration section of
      `tests/pipeline/test_hook_bridge.py` with
      `test_run_hook_platform_free_fast_path` (design, verbatim): spawn
      `subprocess.run([sys.executable, "-c", child_code], env={**os.environ,
      "GOGA_DOCKER": "1", "AFM_HOOK_EVENT": "stage_script_started",
      "PYTHONPATH": <repo root>}, stdin=DEVNULL, capture_output=True)` where
      `child_code` runs `runpy.run_module("goga.pipeline", run_name="__main__")`
      with `sys.argv = ["goga.pipeline", "hook"]`, catches `SystemExit`, and
      prints the exit code plus `sorted(m for m in sys.modules if m ==
      "goga.hooks" or m.startswith("goga.hooks.") or m == "goga.pipeline.hooks"
      or m.startswith("goga.pipeline.hooks."))`; assertions: first stdout line
      == "0"; second stdout line == "[]" (no platform modules in `sys.modules`).
      This is the design's checklist verification verbatim — it fails if any
      static import chain (cli, either package facade) reintroduces the
      platform, which is exactly the regression class D1 guards against
- [ ] End-to-end curated path re-verified in-process: the Task 4
      end-to-end test plus this subprocess proof together cover env → filter →
      stdin → builder → emission in both process shapes
- [ ] Run validation: `.venv/bin/pytest tests/pipeline/test_hook_bridge.py -v`
      then the full battery `pytest tests/ -x` — green
- [ ] Post-implementation verification — Docs item (verification only, already
      applied in the working tree): confirm `docs/features/pipelines/hooks.md`
      carries the 15 actions, the `StageEvent` / `RunEvent` contexts, the
      delivery contract, and the env-visibility note; the two "hooks"
      vocabularies stay distinct
- [ ] Post-implementation verification — Cross-cutting items: `goga lint` clean
      (91 cells / 0 errors); `goga schema` parses the three manifests (retry
      once — the command is flaky in this tree); with no tool packages
      installed the full battery is green (identical CLI output, exit codes —
      the byte-identity net); the bridged emission never fires `run_created` /
      `run_completed` (grep-level check: the bridge maps only the fifteen
      curated names)
- [ ] Record the two LIVE checks as post-suite results (not unit tests — they
      need a real run): live run with a subscribed tool (stage events arrive
      mid-run with the full context; `event_id` stable; `reason` present when
      afm provides one) and older afm binary without the hooks key (launch
      unaffected, no bridge, no errors). If a live environment is unavailable in
      the session, record them as PENDING with the exact commands to run
- [ ] Lint gates: `.venv/bin/ruff check goga/ tests/` &&
      `.venv/bin/ruff format --check goga/ tests/` && `goga lint` — zero
      violations; commit (gates green, no `Co-Authored-By:`)

---

## Validation Commands

(All inside the virtualenv created in Task 1 — `.venv/bin/...`)

- `.venv/bin/pytest tests/ -x`: Run all tests (the full battery)
- `.venv/bin/pytest tests/hooks/catalog/test_catalog.py tests/pipeline/hooks/
  test_bridged_events.py tests/pipeline/test_hook_bridge.py
  tests/pipeline/test_afm_config.py tests/pipeline/test_pipeline_cli.py
  tests/pipeline/test_pipeline_contract.py -v`: The focused suites of this feature
- `.venv/bin/ruff check goga/ tests/`: Lint check (the CI gate)
- `.venv/bin/ruff format --check goga/ tests/`: Format check (run
  `ruff format goga/ tests/` to fix)
- `goga lint`: Cell-level lint — 0 errors over 91 cells
- `.venv/bin/python -c "from goga.hooks.catalog import declared_actions; assert
  len(declared_actions()) == 49"`: Catalog carries the 15 new records
- `.venv/bin/python -c "from goga.pipeline.hooks import PipelineHooks,
  RunEvent, RunIdentity, StageEvent, StageTransition"`: Zone facade (15 names)
- `.venv/bin/python -c "from goga.pipeline import run_hook, map_event_action,
  build_run_event, build_stage_event, run_pipeline, describe_pipeline"`:
  Pipeline facade (19 names, lazy pair included)
- `.venv/bin/python -c "from goga import app, AST"`: Root facade lazy pair
- `.venv/bin/goga --help`: The console script still works (imports `goga.cli`
  directly)
- `goga schema` (retry once on a flaky failure): The three manifests parse

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
      (`catalog.py`, `contexts.py`, `events.py`, `hook_bridge.py`, `afm_config.py`,
      `cli.py`, both `__init__.py` facades)
- [ ] Every contract entity is accessible from its facade (zone 15, pipeline 19,
      root pair lazy)
- [ ] Properties and methods match the declared API (signatures exact, `reason`
      last with `""` default, `from_status`/`to_status` renames)
- [ ] Descriptions are reflected in behavior (curated filter before any platform
      import; shared read-only context; soft failures never change the exit
      code; clean named `ValueError`s; the D2 entry shape byte-exact)
- [ ] Contract dependencies are met (catalog records precede the emissions;
      platform reused, not duplicated)
- [ ] Re-exports are accessible from the facade (four zone names, four bridge
      names, both lazy pairs)
- [ ] Every coding task followed the TDD workflow (contract tests → code →
      verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each
      coding task (all 21 design test scenarios implemented:
      `test_declared_actions_carries_the_fifteen_bridge_records`,
      `test_map_event_action_resolves_the_curated_vocabulary`,
      `test_map_event_action_returns_none_outside_the_curated_vocabulary`,
      `test_build_stage_event_composes_the_transition_context`,
      `test_emit_stage_event_delivers_shared_read_only_context`,
      `test_emit_run_event_unknown_action_raises_clean_error`,
      `test_bridged_surface_registry_built_once_per_process`,
      `test_run_hook_bridges_a_curated_stage_event_end_to_end`,
      `test_run_hook_non_curated_event_exits_zero_without_reading_stdin`,
      `test_run_hook_damaged_stdin_returns_nonzero_with_clean_message`,
      `test_run_hook_missing_flow_block_returns_nonzero`,
      `test_run_hook_missing_stage_block_returns_nonzero`,
      `test_run_hook_missing_event_fact_names_the_fact`,
      `test_run_hook_non_object_json_is_a_bridge_failure`,
      `test_run_hook_null_reason_lands_as_empty_string`,
      `test_run_hook_subscriber_failure_and_empty_registry_exit_zero`,
      `test_run_hook_platform_free_fast_path`,
      `test_write_afm_config_registers_the_observer_hook`,
      `test_pipeline_cli_hook_dispatches_and_returns_the_code`,
      `test_pipeline_cli_hook_rejects_options`,
      `test_zone_and_cell_facades_export_the_new_names`)
- [ ] Integration tests exist where cross-entity scenarios require them (the
      subprocess fast-path proof)
- [ ] No package boundary was expanded; no new cells; `run_pipeline`,
      `describe_*`, the compiler, the workflow layer, and the host-side launcher
      untouched (sole exception: the mechanical lazy-`__getattr__` of
      `goga/__init__.py`)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (battery, ruff check + format, `goga lint`,
      facade imports, console script)
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `afm`,
      `argparse`, `cli_entrypoint`, `checkpoints`, `declaring-actions`,
      `registering-hooks`, `per-tool-delivery`, `resolve-wrapper-path`)
- [ ] The Mandatory Rules were enforced at every task boundary and every local
      commit (style, tests, linters/formatters, REPL cycle; no `Co-Authored-By:`
      trailers)
