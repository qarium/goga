# Build — Configuration

The build domain reads one section of `.goga/config.yml` — `build`. The section is optional at the loader level; `goga build` raises a `ClickException` when it is absent.

```yaml
image: qarium/goga-python-3.12:1.3   # top-level image, shared with pipelines (build.image is rejected)
build:
  task_executor:
    agent: claude                    # the agent that runs the build inside the container
    env: {}
  review_executor:
    agent: codex                     # optional: a separate review-pass agent
    roles: [quality, testing]
    base_ref: origin/1.3.x           # review diff base
    patience: 3
```

### `build`

| Field | Type | Required | Description |
|---|---|---|---|
| `task_executor` | mapping | Yes | AI agent configuration — see [build.task_executor](#buildtask_executor) |
| `worktree` | `bool` | No | Use an isolated git worktree for builds |
| `skip_finalize` | `bool` | No | Skip the ralph-loop finalization step |
| `session_timeout` | `string` | No | Session timeout in Go duration format (e.g. `30m`, `1h`) |
| `idle_timeout` | `string` | No | Idle timeout in Go duration format |
| `wait` | `string` | No | Wait time on rate limit in Go duration format |
| `max_iterations` | `int` | No | Maximum task iterations |
| `prompts_dir` | `string` | No | Path to custom ralph-loop prompts |
| `agents_dir` | `string` | No | Path to custom ralph-loop agents |
| `codex_review` | `bool` | No | Enable external codex review |
| `proxy` | `string` | No | HTTP/HTTPS proxy URL for the build container. When set, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` are written to the container env-file. Overridden by the `--proxy` CLI option |
| `hosts` | mapping | No | Host→IP mapping for `docker run --add-host`. Defaults to `{}`. Augmented by the repeatable `--add-host` CLI option (CLI wins on key conflict) |
| `review_executor` | mapping | No | Review-phase configuration — see [build.review_executor](#buildreview_executor) |

### `build.task_executor`

| Field | Type | Required | Description |
|---|---|---|---|
| `agent` | `string` | No | AI executor that runs the build inside the container. Optional at the loader level — absent/YAML-null/empty/whitespace resolves to `None`; `goga build` raises a `ClickException` when it is `None`. Resolved to `/home/goga/bin/<agent>-as-claude.sh` — no whitelist; any name whose wrapper file exists in the image works. Baseline wrappers: `claude`, `codex`, `cursor`, `opencode`, `qwen`. See [Agents](../../configuration/agents.md) |
| `env` | mapping | No | Environment variables passed to the agent. Keys and values must be strings. Defaults to `{}` |

### `build.review_executor`

| Field | Type | Required | Description |
|---|---|---|---|
| `skip` | `bool` | No | Skip the review phase entirely — the run executes tasks only (ralph-loop `--tasks-only`). Absent/YAML-null means "not set" (the CLI flag decides); must be a real bool — a YAML `1` is rejected |
| `agent` | `string` | No | Review executor agent name (same resolution mechanic as `build.task_executor.agent`; its wrapper must exist in the image). When it differs from `task_executor.agent`, **or when a non-empty `env` is declared alongside it**, the build runs two passes: tasks with the task wrapper, then the review pass with the review wrapper. Combining either two-pass form with an active worktree (`--worktree` or `build.worktree: true`) is rejected with exit 1 on the host |
| `roles` | list of `string` | No | Reviewer composition for the review prompts: keeps only the `{{agent:X}}` lines of the selected roles and adapts the counters of the accompanying text. Whitelist: `quality`, `implementation`, `testing`, `simplification`, `documentation`. Absent or `[]` means the full default set (prompts stay byte-identical to the vendored defaults) |
| `env` | mapping of `string` | No | Review-pass environment layer (`{str: str}`). Keys overlay same-named container variables for the review-pass subprocess only — the tasks pass and the container env-file are unaffected, and the values never reach logs or dry-run output. Absent/YAML-null/`{}` all resolve to `{}`. A non-empty `env` induces a two-pass run like a differing agent does, and requires `agent`; a skipped run ignores the layer entirely |
| `base_ref` | `string` | No | Review diff base — a branch name or commit hash, stored verbatim (no resolvability or format check; ralphex owns the diagnostics). Overrides ralphex's default-branch detection on review-carrying passes. Overridden by the `--base-ref` CLI option |
| `patience` | `int` | No | Stop the external review after N consecutive unchanged rounds. Absent/YAML-null resolves to `None`; a YAML boolean is rejected. Overridden by the `--review-patience` CLI option |

The image itself is configured at the top level (`image`, `dockerfile`) — shared with [Pipelines](../pipelines/configuration.md). The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md); the validation errors of the section are listed there (see [validation errors](../../configuration/project.md#validation-errors)).
