# build — delivering the build checkpoints

How the build operation consumes the hooks zone of the build domain: running the
validation gate before the first pass and emitting the four notifications around
the passes. For the in-container build orchestration.

## The checkpoint surface

One `BuildHooks` object serves every checkpoint of a run — the surface shares one
registry per run, so a run that reaches several checkpoints enumerates the tool
packages once.

    from goga.build.hooks import BuildHooks

    hooks = BuildHooks()

## Resolve the facts in the operation

Every context is built from the values the caller passes — the checkpoint reads
no repository. Resolve before the delivery:

- `WorkIdentity` — the current branch with the topic slug and year when the
  branch hosts a topic (`resolve_current_branch_name` with the `"unknown"`
  fallback — resolved before the checkpoint).
- `BuildMoment` — the plan, the work identity, `dry_run`.
- `StageFacts` (tasks and review) — the executor agent, env presence as NAMES
  (never values), the resolved option facts; the review facts carry roles,
  base_ref, strategy, the additional facts, and the finalize prompt text when
  configured.

## Gate before the first pass

After goga's own pre-checks (manifest check, settings resolution, review-config
validation, ralphex defaults sync) and before the first pass launch:

    verdict = hooks.validate_build(moment=moment, tasks=tasks_facts,
                                   review=review_facts, skip=skip)
    if not verdict.approved:
        # one merged error listing every violation (tool, hook, reason); exit 1;
        # no pass launches; the plan stays; no further events

- The gate walk runs to completion: every subscribed tool's validation hooks run
  — no early stop between tools; a non-vetoing subscriber is still invoked.
- A hook vetoes via the delivered view: `context.veto(reason)`. A crashing hook
  counts as its tool's veto with the crash reason.
- The gate modifies nothing — observe-and-veto only.

## Emit around the cycle

    hooks.emit_build_started(moment, tasks, review, skip)
    hooks.emit_pass_started(moment, tasks_facts)
    exit_code = run_build_pass(...)            # tasks pass
    hooks.emit_pass_completed(moment, tasks_facts, exit_code)
    if exit_code == 0 and not skip:
        hooks.emit_pass_started(moment, review_facts)
        exit_code = run_build_pass(...)        # review pass
        hooks.emit_pass_completed(moment, review_facts, exit_code)
    relocation = move_completed_plan(...)
    statuses = collect_topic_statuses(...)     # recompute after the relocation attempt
    hooks.emit_build_completed(moment, exit_code, stages, relocation, statuses)

- The four notifications are fire-and-forget: a failing hook warns naming the
  tool, the action, and the reason; the run's outcome is unaffected.
- `pass_completed` and `build_completed` fire on zero, non-zero, and
  spawn-failure codes alike — completion is a fact, not a success claim.
- Dry-run fires the identical structure with the `dry_run` fact; the gate runs;
  nothing executes.
- With no tool packages installed the whole surface is inert — an unsubscribed
  gate returns an approved verdict, emissions are unobservable.
