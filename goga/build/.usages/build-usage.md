# Build API — goga/build

## Overview

The `goga.build` module orchestrates code builds through ralphex — handling environment
preparation, ralphex config generation, default prompt/agent copying, ralphex option
resolution, and delegation of the launch to `run_ralphex` (goga/ralphex).

The AI agent is selected via `.goga/config.yml` `build.task_executor.agent`. The agent name
is resolved at runtime to the absolute in-container path of its `*-as-claude.sh` wrapper,
and that path is written into `.ralphex/config` `claude_command`. ralphex option precedence
(CLI > ProjectConfig > omit) is resolved in `build()` before delegating the launch.

## Usage

```python
from goga.config import load_project_config
from goga.build import build

config = load_project_config()

exit_code = build(
    plan="docs/plans/my-plan.md",
    config=config,
    cli_options={
        "dry_run": False,
        "worktree": True,
        "skip_finalize": False,
        "skip_manifest_check": False,
    },
)
```

## Parameters

- `plan` — path to the plan file (markdown)
- `config` — ProjectConfig object loaded via `load_project_config`
- `cli_options` — options dictionary (dry_run, worktree, skip_finalize, skip_manifest_check,
  skip_review, session_timeout, idle_timeout, wait, max_iterations, review_patience)

## Review-phase control

### Skipping review

cli_options={'skip_review': True} or .goga/config.yml build.review_executor.skip: true
→ the run executes tasks only (ralphex --tasks-only); codex_enabled stays as configured.

### Two-pass (different review executor)

build.review_executor.agent != build.task_executor.agent → pass 1 --tasks-only (task
wrapper), pass 2 --review (review wrapper). Pass-1 failure exits with its code.

### Reviewer roles

build.review_executor.roles filters {{agent:X}} lines in both review prompts; empty list
or absent = full default set; files of all 5 agents are always present in .ralphex/agents/.

## Plan relocation

After ANY successful run (full / skip / two-pass) the plan moves to <plan_dir>/completed/;
on failure or --dry-run it stays in place. .ralphex/config always has
move_plan_on_completion = false — goga moves the plan itself.

## Agent resolution

`.goga/config.yml` field `build.task_executor.agent` is the agent name. `build()` resolves it
through `resolve_wrapper_path` and writes the absolute path into `.ralphex/config`
`claude_command`. ralphex then invokes the wrapper directly (launched via `run_ralphex`).

## Return value

- `0` — success
- `1` — failure (uncommitted manifests, ralphex not found, build error)

## Side effects

- Creates `.ralphex/config` with `claude_command` set to the resolved wrapper path and
  `move_plan_on_completion = false`
- Fully rewrites prompts and agents in `.ralphex/` from the vendored ralphex defaults
  (or the configured custom directories) on every run
- Delegates the launch to `run_ralphex` (goga/ralphex), which spawns the `ralphex` subprocess
  (the build env is delivered through the container env-file by the host launcher)
- Relocates the plan file to `<plan_dir>/completed/` after a successful run

## .ralphex/ lifecycle

The `.ralphex/` directory lifecycle is owned by the host launcher (goga/commands/build): it
prepares the mount before launch and wipes it only on `goga build --clean`. The in-container
`build()` reuses whatever state the mounted `.ralphex/` provides.

## Docker entry point

`main()` calls `ensure_in_docker()` first, then argparse handles parsing and calls `build()`.
