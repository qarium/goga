# Build API — goga/build

## Overview

The `goga.build` module orchestrates code builds through ralphex — handling
environment preparation, ralphex config generation, and build process
execution.

The AI agent is selected via `.goga/config.yml` `build.task_executor.agent`.
The agent name is resolved at runtime to the absolute in-container path of
its `*-as-claude.sh` wrapper, and that path is written into `.ralphex/config`
`claude_command`.

## Usage

```python
from goga.config import load_project_config
from goga.build import build

# Load project configuration
config = load_project_config()

# Execute build
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
- `cli_options` — options dictionary:
  - `dry_run` (bool) — print the command without executing
  - `worktree` (bool) — enable git worktree isolation mode
  - `skip_finalize` (bool) — skip the finalization step
  - `skip_manifest_check` (bool) — skip CODEMANIFEST commit verification
  - `session_timeout`, `idle_timeout`, `wait` (str) — timeout settings
  - `max_iterations`, `review_patience` (int) — iteration limits

## Agent resolution

`.goga/config.yml` field `build.task_executor.agent` is the agent name as
declared in the goga image (`claude`, `codex`, `opencode`, or any other name
matching the `/home/goga/bin/<agent>-as-claude.sh` wrapper convention).

`build()` resolves this name through `resolve_wrapper_path` and writes the
resulting absolute path into `.ralphex/config` `claude_command`. ralphex
then invokes the wrapper directly.

`resolve_wrapper_path(agent: str) -> str` is a pure string-building routine —
it concatenates the in-container wrappers directory (`/home/goga/bin/`), the
`agent` value verbatim, and the `-as-claude.sh` suffix. It performs no
validation and no filesystem access; absence of the wrapper file is surfaced
by ralphex at invocation time.

No agent-name validation is performed by `build()`. If the wrapper file is
missing from the image, ralphex surfaces the error.

## Return value

- `0` — success
- `1` — failure (uncommitted manifests, ralphex not found, build error)

## Side effects

- Creates `.ralphex/config` with `claude_command` set to the resolved wrapper
  path (wrappers live in the image, not under .ralphex/)
- Delivers build env (`ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, etc.) through
  the `ralphex` subprocess environment
- Copies prompts and agents into `.ralphex/`
- Spawns a subprocess (`ralphex`)

## .ralphex/ lifecycle

The `.ralphex/` directory lifecycle is owned by the host launcher:

- The host launcher prepares the `.ralphex/` mount before container launch and
  wipes it only when the `--clean` flag is passed on `goga build`.
- The in-container `build()` reuses whatever state the mounted `.ralphex/`
  provides, so ralphex progress files survive across runs of the same project
  on the same branch — useful for resuming interrupted builds.
- When invoked directly via `python -m goga.build` (e.g. for development), the
  cwd's `.ralphex/` is reused across runs; the operator wipes it manually when a
  fresh start is needed.

This means ralphex progress files survive across runs of the same project on
the same branch by default, which is useful for resuming interrupted builds.

## Docker entry point

The module supports invocation via `python -m goga.build` for use inside Docker
containers through the `goga build` CLI command. In this mode, `main()` first
calls `ensure_in_docker()` as its very first statement to verify the process
is running inside the goga Docker image — host-side invocations fail with a
clear stderr message and exit code 1 before any work begins. After the guard
passes, argparse handles CLI option parsing and calls `build()` directly.

```bash
# Inside the goga Docker image (GOGA_DOCKER=1 is set):
python -m goga.build plan.md --worktree --skip-manifest-check

# From the host (fails — use `goga build` instead):
python -m goga.build plan.md
# → stderr message, exit code 1
```

