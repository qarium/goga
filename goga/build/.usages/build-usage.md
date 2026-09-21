# Build API — goga/build

## Overview

The `goga.build` module orchestrates the stable two-pass build cycle through
ralphex — settings resolution with root inheritance, the five hooks checkpoints,
ralphex config generation with the external-review surface, vendored
defaults sync with finalize materialization, and delegation of the launch to
`run_ralphex` (goga/ralphex).

Every non-skipped run is exactly two ralphex invocations: a tasks pass
(`--tasks-only`) then a review pass (`--review`, or `-e` under the short
strategy). A skipped review yields exactly one tasks pass. The combined full
pass does not exist.

The executor agent comes from `.goga/config.yml`: the `build.agent` root key
for the tasks pass, `build.review.agent` for the review pass (inheriting the
root agent when unset). The agent name is resolved at runtime to the absolute
in-container path of its `*-as-claude.sh` wrapper, and that path is written
into `.ralphex/config` `claude_command`.

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
        "skip_manifest_check": False,
        "skip_review": None,          # tri-state: True / False / None
        "base_ref": "origin/1.2.x",   # review diff base (review pass only)
        "review_patience": 3,
        "session_timeout": None,
        "idle_timeout": None,
        "wait": None,
        "max_iterations": None,
    },
)
```

## Parameters

- `plan` — path to the plan file (markdown)
- `config` — ProjectConfig object loaded via `load_project_config`
- `cli_options` — options dictionary (`dry_run`, `skip_manifest_check`,
  `skip_review`, `base_ref`, `review_patience`, `session_timeout`,
  `idle_timeout`, `wait`, `max_iterations`); each knob is None when the CLI
  flag was not given

## Two-part settings and inheritance

The build section of `.goga/config.yml` is two-part. The `build` root carries
the tasks-pass settings (agent, env, max_iterations, session_timeout,
idle_timeout, wait, prompts_dir, agents_dir, proxy, hosts); the `build.review`
key carries the review-pass settings (skip, agent, env, roles, base_ref,
strategy, finalize, additional, and the session knobs).

Resolution (in `resolve_run_settings`, precedence CLI > config > default >
omit):

- `skip` — cli_options `skip_review` when not None, else `build.review.skip`,
  else False
- `strategy` — `build.review.strategy` when set, else medium
- review agent and session knobs — the review value when set, else the root
  value
- `max_iterations` — root-only (the tasks-pass knob)
- review env — exactly `build.review.env`; it NEVER inherits the root env
  (the root env is the tasks-pass layer, secret-safe)
- `additional.agent` — the additional value when set, else the resolved
  review agent

## Strategies

- **full** — the review pass runs internal review with the external review
  enabled (ralphex default); an `additional.agent` customizes it
  (`external_review_tool: custom` + the agent's wrapper script)
- **medium** (default) — the external review is explicitly disabled
  (`codex_enabled: false`); internal reviewer agents only
- **short** — the review pass runs as the external-only pass (`-e`) under
  the additional agent's wrapper (falling back to the review agent)

## additional (external-review block)

`build.review.additional` carries `agent` (inherits `build.review.agent`),
`patience` (stop after N consecutive unchanged rounds; 0 = disabled; forwarded
as `--review-patience`), and `max_iterations` (external review iteration cap;
0 = ralphex auto; forwarded as `--max-external-iterations`).

## finalize

`build.review.finalize` is the user-authored final review prompt, stored
verbatim. When set, `sync_ralphex_defaults` materializes the ralphex finalize
step files and `.ralphex/config` sets `finalize_enabled: true`. Unset leaves
the finalize step at the ralphex default (off).

## Reviewer roles

`build.review.roles` filters {{agent:X}} lines in both review prompts; None or
an empty list = full default set; files of all 5 agents are always present in
.ralphex/agents/.

## The five checkpoints

The cycle delivers five hooks checkpoints (see the `checkpoints` practice of
goga/build/hooks and `registering-hooks` here for subscribing):

1. `validate_build` (hard gate) — after goga's pre-checks, before the first
   pass; every subscribed tool's hooks run to completion, vetoes merge into
   one error (tool, hook, reason), exit 1, nothing launches
2. `build_started` (soft) — immediately after the gate passes
3. `pass_started` (soft) — before each pass launch
4. `pass_completed` (soft) — on every pass return, with the actual exit code
5. `build_completed` (soft) — after the relocation attempt and the status
   recompute

On dry-run the identical event structure fires with the `dry_run` fact; the
gate runs; nothing executes. Pre-launch failures (uncommitted manifests,
invalid review config, unavailable defaults) and a blocked (vetoed) run fire
no events.

## Review-pass environment

`build.review.env` (mapping of strings) overrides same-named variables for the
review pass subprocess only; every other container variable passes through
unchanged. The tasks pass receives `build.env` as its env layer the same way.
Neither layer is printed on dry-run (secret-safe).

## Plan relocation

After a successful run the plan moves to <plan_dir>/completed/; on failure or
dry-run it stays in place. .ralphex/config always has
move_plan_on_completion = false — goga moves the plan itself.

## Agent resolution

`.goga/config.yml` field `build.agent` is the tasks-pass agent name;
`build.review.agent` (default: the root agent) is the review-pass agent name.
`build()` resolves each through `resolve_wrapper_path` and writes the absolute
path into `.ralphex/config` `claude_command` of the respective pass. ralphex
then invokes the wrapper directly (launched via `run_ralphex`).

## Return value

- `0` — success
- `1` — failure (uncommitted manifests, a vetoed gate, ralphex not found,
  build error)

## Side effects

- Creates `.ralphex/config` per pass with `claude_command` set to the pass's
  resolved wrapper path and `move_plan_on_completion = false`
- Fully rewrites prompts and agents in `.ralphex/` from the vendored ralphex
  defaults (or the configured custom directories) on every run; materializes
  the finalize step files when `build.review.finalize` is set
- Delegates each launch to `run_ralphex` (goga/ralphex), which spawns the
  `ralphex` subprocess (the pass env layers are applied in-container, not
  through the host env-file)
- Relocates the plan file to `<plan_dir>/completed/` after a successful run

## .ralphex/ lifecycle

The `.ralphex/` directory lifecycle is owned by the host launcher (goga/commands/build): it
prepares the mount before launch and wipes it only on `goga build --clean`. The in-container
`build()` reuses whatever state the mounted `.ralphex/` provides.

## Docker entry point

`main()` calls `ensure_in_docker()` first, then argparse handles parsing
(`--skip-review`/`--no-skip-review`, `--base-ref`, `--dry-run`,
`--skip-manifest-check`, `--session-timeout`, `--idle-timeout`, `--wait`,
`--max-iterations`, `--review-patience`) and calls `build()`.
