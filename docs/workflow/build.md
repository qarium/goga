# Build

Execute the implementation plan via ralphex inside a Docker container. This is the bridge between the workflow and actual code — ralphex reads the plan and produces the implementation.

## Synopsis

```bash
goga build <plan> [OPTIONS]
```

## Output artifact

Implemented code in the project tree, produced by ralphex executing each plan task in sequence. CODEMANIFEST files remain **read-only** throughout the build.

## Algorithm

`goga build` runs a deterministic pipeline:

| Step | Action |
|---|---|
| 1. Docker check | Verify Docker is installed and accessible. Halt on failure. |
| 2. Config loading | Read `.goga/config.yml` for build settings (image, agent, env, timeouts). |
| 3. Uncommitted manifest check | Scan `git status` for uncommitted CODEMANIFEST files. Reject if any are found (skip with `--skip-manifest-check`). |
| 4. Agent preconditions | Set up agent-specific files. For `claude`: merge `.claude/settings.json` (inject env, set attribution), create `.ralphex/claude-wrapper.sh` with `chmod +x`, update `.ralphex/config`. |
| 5. Defaults copy | Copy default prompts and agent configurations to `.ralphex/`. |
| 6. Docker execution | Launch ralphex inside the configured Docker image with `python -m goga.build` as the entry point. |

Inside the container, ralphex executes the plan: one task per iteration, following the ralphex execution protocol (declaration → contract tests → implementation → interface verification → logic tests → debugging → contract re-verification → lint → completion → review → approval → next task).

## When to use

- After `plan` and `review(plan)`, when the plan is approved.
- Whenever an execution plan exists in `docs/plans/` and is ready to be executed.

## Inputs and outputs

| | |
|---|---|
| **Input** | `docs/plans/<topic>.md` — the execution plan |
| **Output** | Implemented code in the project tree |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | off | Print the assembled command without executing |
| `--worktree` | flag | off | Enable ralphex worktree mode |
| `--skip-finalize` | flag | off | Skip finalization step |
| `--skip-manifest-check` | flag | off | Skip check for uncommitted CODEMANIFEST files |
| `--session-timeout` | string | config | Session timeout duration |
| `--idle-timeout` | string | config | Idle timeout duration |
| `--wait` | string | config | Wait time before starting |
| `--max-iterations` | int | config | Maximum number of build iterations |
| `--review-patience` | int | config | Review patience count |
| `-e`, `--env` | string | -- | Additional environment variable (`KEY=VALUE`, repeatable) |

Timeout and iteration options fall back to `.goga/config.yml` when not provided on the command line.

## Examples

```bash
goga build docs/plans/json-export.md
goga build docs/plans/json-export.md --dry-run
goga build docs/plans/json-export.md --skip-manifest-check
goga build docs/plans/json-export.md -e ANTHROPIC_API_KEY=sk-xxx
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Build completed successfully |
| `1` | Build failed (Docker not found, config error, precondition failure, or ralphex error) |

## What happens next

- Test the produced implementation manually.
- If bugs or defects are found — fix them with [`change`](change.md).
- Once the implementation is stable — run [`accept`](accept.md) for final sign-off.

See the full CLI reference: [`goga build`](../cli/build.md).
