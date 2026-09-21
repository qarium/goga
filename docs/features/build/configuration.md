# Build — Configuration

The build domain reads one section of `.goga/config.yml` — `build`. The section is two-part: the `build` root carries the **tasks-pass** settings, and its optional `review` sub-mapping carries the **review-pass** settings. The section is optional at the loader level; `goga build` raises a `ClickException` when it is absent, and again when `build.agent` resolves to `None`.

```yaml
image: qarium/goga-python-3.12:1.3   # top-level image, shared with pipelines (build.image is rejected)
build:
  agent: claude                      # the agent that runs the tasks pass inside the container
  env: {}
  review:                            # optional review-pass settings
    agent: codex                     # inherits build.agent when unset
    roles: [quality, testing]
    base_ref: origin/1.3.x           # review diff base
    strategy: medium                 # full | medium | short (default medium)
    additional:
      patience: 3
```

A run with review on is always two passes — a tasks pass on the root agent's wrapper, then a review pass on the review agent's wrapper (`review.agent` inherits `build.agent` when unset). A skipped review (`review.skip: true` or `--skip-review`) collapses the cycle to the tasks pass alone; a failed tasks pass skips the review. The retired keys `worktree`, `skip_finalize`, `codex_review` and the retired block names `task_executor` / `review_executor` are silently ignored — a config still carrying them loses its build settings (`goga build` fails with `build.agent is required`).

### `build` root (the tasks-pass settings)

| Field | Type | Required | Description |
|---|---|---|---|
| `agent` | `string` | No | AI executor that runs the tasks pass inside the container. Optional at the loader level — absent/YAML-null/empty/whitespace resolves to `None`; `goga build` raises a `ClickException` when it is `None`. Resolved to `/home/goga/bin/<agent>-as-claude.sh` — no whitelist; any name whose wrapper file exists in the image works. Baseline wrappers: `claude`, `codex`, `cursor`, `opencode`, `qwen`. See [Agents](../../configuration/agents.md) |
| `env` | mapping | No | Tasks-pass environment layer (`{str: str}`). Keys and values must be strings. Defaults to `{}`; an empty mapping means pure inheritance — the layer reaches the container solely as the in-container tasks-pass env layer, never the env-file, and the values never reach logs or dry-run output |
| `session_timeout` | `string` | No | Session timeout (a duration string, e.g. `30m`, `1h`) — the tasks-pass value; the review knobs inherit it when their own is unset |
| `idle_timeout` | `string` | No | Idle timeout (a duration string, e.g. `10m`) — inherited by the review part the same way |
| `wait` | `string` | No | Wait time on rate limit (a duration string, e.g. `5m`) — inherited by the review part the same way |
| `max_iterations` | `int` | No | Maximum task iterations — root-only, never resolves onto the review part |
| `prompts_dir` | `string` | No | Path to custom build prompts (copied as-is, without role filtering) |
| `agents_dir` | `string` | No | Path to custom build agent definitions (copied as-is) |
| `proxy` | `string` | No | HTTP/HTTPS proxy URL for the build container. When set, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` are written to the container env-file. Overridden by the `--proxy` CLI option |
| `hosts` | mapping | No | Host→IP mapping for `docker run --add-host`. Defaults to `{}`. Augmented by the repeatable `--add-host` CLI option (CLI wins on key conflict) |
| `review` | mapping | No | Review-pass configuration — see [build.review](#buildreview) |

### `build.review`

| Field | Type | Required | Description |
|---|---|---|---|
| `skip` | `bool` | No | Skip the review phase entirely — the run executes the tasks pass only. Absent/YAML-null means "not set" (the CLI flag decides); must be a real bool — a YAML `1` is rejected |
| `agent` | `string` | No | Review executor agent name (same resolution mechanic as `build.agent`; inherits `build.agent` when unset, and its wrapper must exist in the image — validated in-container before the pass). The review pass always runs as its own pass on this agent's wrapper |
| `roles` | list of `string` | No | Reviewer composition for the review prompts: keeps only the `{{agent:X}}` lines of the selected roles and adapts the counters of the accompanying text. Whitelist: `quality`, `implementation`, `testing`, `simplification`, `documentation`. Absent or `[]` means the full default set (prompts stay byte-identical to the vendored defaults) |
| `env` | mapping of `string` | No | Review-pass environment layer (`{str: str}`) — never inherits the root env. Keys overlay same-named container variables for the review-pass subprocess only — the tasks pass and the container env-file are unaffected, and the values never reach logs or dry-run output. Absent/YAML-null/`{}` all resolve to `{}`; a non-empty layer requires `agent`; a skipped run ignores the layer entirely |
| `base_ref` | `string` | No | Review diff base — a branch name or commit hash, stored verbatim (no resolvability or format check; an unresolvable ref is reported at run time). Reaches ralphex as `--base-ref` on the review pass only. Overridden by the `--base-ref` CLI option |
| `strategy` | `string` | No | Review strategy: `full` (external review enabled; with an additional agent it runs on that agent's wrapper), `medium` (the default — external review explicitly disabled, internal reviewers only), or `short` (the external review alone, executed on the additional agent's wrapper) |
| `finalize` | `string` | No | A user-authored final review prompt; when set, the ralphex finalize step is materialized from this text and enabled. Unset leaves the step at the ralphex default (off) |
| `session_timeout` / `idle_timeout` / `wait` | `string` | No | Review-pass session knobs — inherit the corresponding `build` root values when unset; the CLI flags win over both |
| `additional` | mapping | No | External-review block — see [build.review.additional](#buildreviewadditional) |

### `build.review.additional`

| Field | Type | Required | Description |
|---|---|---|---|
| `agent` | `string` | No | The external-review agent (inherits `review.agent` when unset). Under `strategy: short` the review pass itself runs on this agent's wrapper; under `full` it carries the external review. Its wrapper must exist when the strategy engages the external review |
| `patience` | `int` | No | Stop the external review after N consecutive unchanged rounds; `0` disables the bound and passes verbatim. Absent/YAML-null resolves to `None` (unset); a YAML boolean is rejected. Overridden by the `--review-patience` CLI option |
| `max_iterations` | `int` | No | External-review iteration cap; `0` passes verbatim to ralphex's auto. Absent resolves to `None` (unset) |

The image itself is configured at the top level (`image`, `dockerfile`) — shared with [Pipelines](../pipelines/configuration.md). The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md); the validation errors of the section are listed there (see [validation errors](../../configuration/project.md#validation-errors)).
