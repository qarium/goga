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
        "base_ref": "origin/1.2.x",  # review diff base (review-scoped)
    },
)
```

## Parameters

- `plan` — path to the plan file (markdown)
- `config` — ProjectConfig object loaded via `load_project_config`
- `cli_options` — options dictionary (dry_run, worktree, skip_finalize, skip_manifest_check,
  skip_review, session_timeout, idle_timeout, wait, max_iterations, review_patience,
  base_ref)

## Review-phase control

### Skipping review

cli_options={'skip_review': True} or .goga/config.yml build.review_executor.skip: true
→ the run executes tasks only (ralphex --tasks-only); codex_enabled stays as configured.

### Two-pass (different review executor or review env)

build.review_executor.agent != build.task_executor.agent OR a non-empty
build.review_executor.env (with agent set) → pass 1 --tasks-only (task wrapper,
no env layer), pass 2 --review (review wrapper, review env layered over the
container environment). Pass-1 failure exits with its code. Review env requires
agent: a non-empty env without agent fails validation when the review phase
runs. With skip: true the review env is ignored entirely.

### Reviewer roles

build.review_executor.roles filters {{agent:X}} lines in both review prompts; empty list
or absent = full default set; files of all 5 agents are always present in .ralphex/agents/.

### Review-scoped options

`base_ref` (review diff base — branch name or commit hash) and `patience`
(external-review stop threshold) are review-scoped: they resolve with
precedence CLI > `build.review_executor.*` > omit and join the ralphex
options of review-carrying passes only — the full-mode single pass and the
two-pass review pass. A skipped run and the tasks-only pass never carry
them.

cli_options={'base_ref': 'origin/1.2.x'} or .goga/config.yml
build.review_executor.base_ref: origin/1.2.x → ralphex receives
--base-ref origin/1.2.x on the review-carrying pass. The same precedence
holds for the review_patience cli_options key /
build.review_executor.patience → --review-patience.

When neither source sets them, the keys stay absent and the assembled
ralphex command carries no extra flags. The build.review_patience config
key is not parsed — declare build.review_executor.patience instead.

## Review-pass environment

build.review_executor.env (mapping of strings) overrides same-named variables
for the review pass only; every other container variable (home.env, git
identity, task_executor.env, CLI -e) passes through unchanged. The tasks pass
is unaffected. Dry-run does not print the layer (secret-safe); an active
worktree combined with an env-induced two-pass run is rejected by the host
launcher before the container starts.

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

`main()` calls `ensure_in_docker()` first, then argparse handles parsing (including `--base-ref`) and calls `build()`.
