# Build — API

The facade of the domain package **`goga.build`** — the two-pass orchestration of a plan execution through ralphex.

The signatures below are the CODEMANIFEST contract of the cell.

## Entry points

```python
build(plan: str, config: ProjectConfig, cli_options: dict) -> int
main() -> int
```

`build` is the full cycle — manifest pre-check, settings resolution with the pre-side-effect validations, the `build/validate_build` hooks gate, the tasks pass, the review pass (skipped on `skip` or a failed tasks pass), plan relocation, and the completion notification; the exit code of the last executed pass is returned. `main` is the in-container console entry point. The `cli_options` dict carries the in-container CLI-surface values (tri-state `skip_review`, `base_ref`, the session knobs, `review_patience`, …).

## Run settings

```python
resolve_run_settings(config: BuildConfig, cli_options: dict) -> RunSettings
validate_review_config(settings: RunSettings) -> None
compose_pass_options(settings: RunSettings, stage: str) -> dict[str, str | int | bool]
RunSettings(skip: bool, tasks: PassSettings, review: ReviewPassSettings)
PassSettings(agent, env, max_iterations, session_timeout, idle_timeout, wait)
ReviewPassSettings(PassSettings, roles, base_ref, strategy, finalize, additional)
```

`resolve_run_settings` is the pure resolver of the two-part configuration with the precedence CLI > config > default > omit (root→review inheritance applied; the review env never inherits the root env; the additional block is always constructed, its agent inheriting the review agent). `validate_review_config` runs the semantic checks (roles whitelist, the env-requires-agent gate, agent wrapper existence, strategy whitelist) before any side effect. `compose_pass_options` maps the resolved settings onto the ralphex options of one pass — exactly one mode flag (`tasks_only`, `review`, or `external_only` under `strategy: short`); the agent and env never appear in the composition.

## Run plumbing

```python
sync_ralphex_defaults(config: BuildConfig, settings: RunSettings) -> None
write_ralphex_config(settings: RunSettings, wrapper_path: str) -> None
run_build_pass(plan: str, settings: RunSettings, options: dict[str, str | int | bool],
               wrapper_path: str, dry_run: bool,
               env: dict[str, str] | None = None) -> int
move_completed_plan(plan: str, outcome: bool, dry_run: bool) -> RelocationOutcome
```

`sync_ralphex_defaults` rewrites `.ralphex/prompts/` and `.ralphex/agents/` from the configured or vendored defaults (filtering review prompts to the selected `roles`, materializing the finalize step when `review.finalize` is set). `write_ralphex_config` writes the engine config for one pass — the executor wrapper of the current pass plus the external-review surface derived from the review part (strategy `medium` disables the external review; `full`/`short` with an additional agent set it to that agent's wrapper). `run_build_pass` launches one ralphex pass (tasks or review) — `dry_run=True` prints the assembled command; the env layer reaches the subprocess only, never options or logs. `move_completed_plan` relocates a successfully completed plan into `<plan_dir>/completed/` and returns the `RelocationOutcome` that feeds the completion event.

## Hooks

The `goga.build.hooks` facade exports the checkpoint surface of the build domain — `BuildHooks` (the `validate_build` gate and the four notifications) plus the fact types (`BuildMoment`, `StageFacts`, `WorkIdentity`, `GateVerdict`, `Violation`, `RelocationOutcome`, `AdditionalFacts`, and the five context types). See [Hooks](hooks.md).

## Example

```python
from goga.build import build
from goga.config import load_project_config

exit_code = build("plan.md", load_project_config(), {"dry_run": False, "skip_review": None})
```
