# Build — API

The facade of the domain package **`goga.build`** — the host-side orchestration of a plan execution through the ralph-loop in a Docker container.

The signatures below are the CODEMANIFEST contract of the cell.

## Entry points

```python
build(plan: str, config: ProjectConfig, cli_options: dict) -> int
main() -> int
```

`build` is the full orchestration — precondition checks (Docker, config, uncommitted manifests), agent wrapper resolution, ralphex defaults sync, optional image refresh, and the container launch; the exit code is returned. `main` is the console entry point. The `cli_options` dict carries the CLI-surface values (timeouts, `--update`, review flags, …) resolved by the command layer.

## Review options

```python
resolve_review_options(config: BuildConfig, cli_options: dict) -> ReviewOptions
validate_review_config(config: BuildConfig, review: ReviewOptions) -> None
ReviewOptions(skip: bool, review_agent: str | None, roles: list[str] | None,
              two_pass: bool, review_env: dict[str, str],
              base_ref: str | None, patience: int | None)
```

`resolve_review_options` composes the review-scoped settings with the precedence CLI > `build.review_executor.*` > omit. `validate_review_config` enforces the host-side guards — among them the rejection of a two-pass review form combined with an active worktree.

## Run plumbing

```python
sync_ralphex_defaults(config: BuildConfig, review: ReviewOptions) -> None
write_ralphex_config(config: BuildConfig, wrapper_path: str) -> None
run_build_pass(plan: str, config: BuildConfig, options: dict[str, str | int | bool],
               wrapper_path: str, dry_run: bool,
               env: dict[str, str] | None = None) -> int
move_completed_plan(plan: str, outcome: bool, dry_run: bool) -> None
```

`sync_ralphex_defaults` rewrites `.ralphex/prompts/` and `.ralphex/agents/` from the configured or vendored defaults (filtering review prompts to the selected `roles`); `write_ralphex_config` writes the ralph-loop config with the resolved wrapper. `run_build_pass` launches one container pass (tasks or review) — `dry_run=True` prints the assembled command. `move_completed_plan` moves the plan into the topic's `completed/` directory after the run.

## Example

```python
from goga.build import build
from goga.config import load_project_config

exit_code = build("plan.md", load_project_config(), {"update": False, "dry_run": False})
```
