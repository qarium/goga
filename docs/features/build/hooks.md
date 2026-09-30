# Build — Hooks

The build domain exposes **five hook actions** for tool packages: one hard validation gate delivered before the first pass, and four soft notifications carrying the run's facts.

A tool subscribes through its `register_hooks` callable — no goga code changes are needed (see the [registration contract](../hooks/hooks.md)):

```python
def register_hooks(hooks):
    hooks.subscribe("build", "validate_build", "policy", enforce_policy)
    hooks.subscribe("build", "build_completed", "reporter", report_build)
```

## The events

| Address | Error class | Fires |
|---|---|---|
| `build / validate_build` | **hard** | After goga's own pre-checks (manifest check, settings resolution, review-config validation, ralphex defaults sync) and before the first pass launch — including dry-run runs |
| `build / build_started` | soft | Immediately after the gate passes, before the first pass launch |
| `build / pass_started` | soft | Before each pass launch — tasks and review |
| `build / pass_completed` | soft | On every pass return — zero, non-zero, and spawn-failure codes alike, carrying the actual exit code |
| `build / build_completed` | soft | On every return of a started build — after the relocation attempt and the status recompute |

A failing moment fires nothing: goga pre-launch failures (uncommitted manifests, invalid review config, unavailable defaults, missing build section or agent) return before any checkpoint. A blocked (vetoed) run fires nothing after the gate.

## The contexts

Every context is delivered read-only — attribute assignment is blocked on every instance. The four soft notifications carry plain facts: a failing hook warns naming your tool, the action, and the reason — the run's outcome is never affected.

### `validate_build` — `BuildValidation` (hard)

One fresh view per tool — the walk never stops between tools: verdict collection requires every tool's outcome, so your tool's hooks run even when another tool already vetoed.

| Read | Type | Meaning |
|---|---|---|
| `moment` | `BuildMoment` | the run's envelope — plan, work identity, `dry_run` |
| `tasks` | `StageFacts` | the resolved stage facts of the tasks stage |
| `review` | `StageFacts` | the resolved stage facts of the review stage — always present, including a skipped review; the facts describe the resolved settings, not the execution |
| `skip` | `bool` | the resolved review skip state of the run |

| Method | Effect |
|---|---|
| `veto(reason)` | buffers your tool's single veto; a repeat call replaces the reason whole |

```python
def enforce_policy(context):
    if violates(context):
        context.veto("reason")
```

- A crashing hook counts as your tool's veto with the crash reason — never a raw traceback.
- All vetoes merge into one clean error (tool, hook, reason); the run stops before any pass: exit code 1, the plan stays in place, no started/pass/completed events fire.

### `build_started` — `BuildStarted` (soft)

One shared read-only instance for every tool — the same facts the gate saw.

| Read | Type | Meaning |
|---|---|---|
| `moment` | `BuildMoment` | the run's envelope — plan, work identity, `dry_run` |
| `tasks` | `StageFacts` | the resolved stage facts of the tasks stage |
| `review` | `StageFacts` | the resolved stage facts of the review stage |
| `skip` | `bool` | the resolved review skip state of the run |

Read-only facts; no methods.

### `pass_started` — `PassStarted` (soft)

One shared read-only instance for every tool.

| Read | Type | Meaning |
|---|---|---|
| `moment` | `BuildMoment` | the run's envelope — plan, work identity, `dry_run` |
| `facts` | `StageFacts` | the stage facts of the pass about to launch |

Read-only facts; no methods.

### `pass_completed` — `PassCompleted` (soft)

One shared read-only instance for every tool.

| Read | Type | Meaning |
|---|---|---|
| `moment` | `BuildMoment` | the run's envelope — plan, work identity, `dry_run` |
| `facts` | `StageFacts` | the stage facts of the finished pass |
| `exit_code` | `int` | the actual exit code of the pass — zero, non-zero, and spawn-failure codes alike |

Read-only facts; no methods. Completion is a fact, not a success claim.

### `build_completed` — `BuildCompleted` (soft)

One shared read-only instance for every tool.

| Read | Type | Meaning |
|---|---|---|
| `moment` | `BuildMoment` | the run's envelope — plan, work identity, `dry_run` |
| `exit_code` | `int` | the final exit code of the run — the last executed pass's code |
| `stages` | `list[str]` | the executed stage sequence in execution order — a skipped review is absent |
| `relocation` | `RelocationOutcome` | the outcome of the plan relocation attempt — moved plus destination |
| `statuses` | `list[str]` | the work's current history statuses recomputed after the relocation attempt — empty in the branch-only form |

Read-only facts; no methods.

## Integration scenarios

- **Build reporting, automation, external notifications** — subscribe to the four notifications; read the stage facts, the exit codes, the relocation outcome, `dry_run`; keep state in your `self` context.
- **Artifact → history-status on completion** — subscribe to `build_completed`; read `relocation` and `work`; register your status on the statuses domain keyed by your artifact.
- **Policy enforcement** — subscribe to `validate_build`; inspect the resolved facts; `context.veto(reason)` when policy is violated — or stay silent to use the gate as a pre-start notification.

## The fact records

| Record | Fields |
|---|---|
| `BuildMoment` | `plan`, `work: WorkIdentity`, `dry_run` |
| `WorkIdentity` | `branch` (`"unknown"` on resolution failure), `slug`, `year` |
| `StageFacts` | `stage` (exactly `tasks` or `review`), `agent`, `env` (names only — values never delivered), `max_iterations`, `session_timeout`, `idle_timeout`, `wait`, `roles`, `base_ref`, `strategy`, `finalize`, `additional: AdditionalFacts | None` |
| `AdditionalFacts` | `agent`, `patience`, `max_iterations` |
| `RelocationOutcome` | `moved: bool`, `destination: str | None` |

The review-only members of `StageFacts` — `roles`, `base_ref`, `strategy`, `finalize`, `additional` — are `None` on the tasks part. Env values are never delivered — presence as names only, in every context.

The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md); the build's configuration-shaped extension surface (custom prompts, custom agent definitions) is covered in [Configuration](configuration.md). Host-side, `goga build` also delivers the config amendment checkpoint at its configuration load (see [Configuration — Hooks](../../configuration/hooks.md)) — the in-container load stays authored-only.
