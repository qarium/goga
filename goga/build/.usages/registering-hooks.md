# build — registering hooks

How a `goga_tool_*` package subscribes its hooks to the build domain actions.
For tool package authors; no goga code changes are needed.

The domain opens five actions. One is the validation gate — a read-and-veto
view over the resolved run facts, delivered before the first pass; it is a hard
action with verdict collection: every subscribed tool's hooks run and all
vetoes merge into one error. Four are notifications — the read-only facts of
the run: at the start, around each pass, and at the completion.

## The events

| Address | Error class | Fires |
|---|---|---|
| `build / validate_build` | hard | After goga's own pre-checks (manifest check, settings resolution, review-config validation, ralphex defaults sync) and before the first pass launch — including dry-run runs. |
| `build / build_started` | soft | Immediately after the gate passes, before the first pass launch. |
| `build / pass_started` | soft | Before each pass launch — tasks and review. |
| `build / pass_completed` | soft | On every pass return — zero, non-zero, and spawn-failure codes alike, carrying the actual exit code. |
| `build / build_completed` | soft | On every return of a started build — after the relocation attempt and the status recompute. |

A failing moment fires nothing: goga pre-launch failures (uncommitted
manifests, invalid review config, unavailable defaults, missing build section
or agent) return before any checkpoint. A blocked (vetoed) run fires nothing
after the gate.

## Subscribe

    def register_hooks(hooks):
        hooks.subscribe("build", "validate_build", "policy", enforce_policy)
        hooks.subscribe("build", "build_completed", "reporter", report_build)

- `domain` — always `"build"`; `action` — from the table; `name` — unique per
  tool per address; `hook` — the callable executed when the event fires.
- A hook receives values only for the parameters it declares by the fixed
  offered names: `context`, `self`.

## The gate view

`validate_build` delivers a `BuildValidation` view per tool: `moment` (plan,
work, dry_run), `tasks` and `review` — the resolved stage facts (the executor
agent, env presence as names, the option facts; review adds roles, base_ref,
strategy, the additional facts, and the finalize prompt text), `skip`.

    def enforce_policy(context):
        if violates(context):
            context.veto("reason")

- `veto(reason)` buffers your tool's single veto; a repeat call replaces the
  reason whole.
- Your tool's hooks all run even when another tool already vetoed — verdict
  collection requires every tool's outcome.
- A crashing hook counts as your tool's veto with the crash reason — never a
  raw traceback.
- All vetoes merge into one clean error (tool, hook, reason); the run stops
  before any pass: exit code 1, the plan stays in place, no
  started/pass/completed events fire.

## The notifications

All four deliver read-only facts; a failing hook warns naming your tool, the
action, and the reason — the run's outcome is never affected.

- `build_started` — `BuildStarted`: the same facts as the gate.
- `pass_started` — `PassStarted`: the stage facts of the pass about to launch.
- `pass_completed` — `PassCompleted`: the stage facts plus the actual
  `exit_code`. Completion is a fact, not a success claim.
- `build_completed` — `BuildCompleted`: the final `exit_code`, `stages` (the
  executed sequence), `relocation` (moved + destination), `statuses` (the
  work's current history statuses recomputed after the relocation attempt —
  empty in the branch-only form), `dry_run`.

Env values are never delivered — presence as names only, in every context.

## Integration scenarios

- **Build reporting, automation, external notifications** — subscribe to the
  four notifications; read the stage facts, the exit codes, the relocation
  outcome, `dry_run`; keep state in your `self` context.
- **Artifact → history-status on completion** — subscribe to
  `build_completed`; read `relocation` and `work`; register your status on the
  statuses domain keyed by your artifact.
- **Policy enforcement** — subscribe to `validate_build`; inspect the resolved
  facts; `context.veto(reason)` when policy is violated — or stay silent to use
  the gate as a pre-start notification.
