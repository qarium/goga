from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ..agents import resolve_wrapper_path
from ..config import ProjectConfig
from ..docker import decode_extra_env
from ..history import collect_topic_statuses, resolve_current_branch_name, resolve_topic_dir
from .build_pass import run_build_pass
from .hooks import AdditionalFacts, BuildHooks, BuildMoment, StageFacts, WorkIdentity
from .pass_options import compose_pass_options
from .plan_relocation import move_completed_plan
from .ralphex_runtime import sync_ralphex_defaults
from .review_config import validate_review_config
from .run_settings import RunSettings, resolve_run_settings

logger = logging.getLogger(__name__)

# The engine-variable keys that never enter a composed launch layer: launch
# mechanics belong to the launcher, so a task-env or CLI entry colliding with
# one of them is dropped silently — the inherited launch value stands, with no
# warning.
_ENGINE_ENV_KEYS = frozenset({"AFM_DIR", "AFM_DOCKER_FILE_ROOTS", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"})


def _unquote_git_path(raw: str) -> str | None:
    if not raw.startswith('"'):
        return raw
    end = raw.find('"', 1)
    if end == -1:
        return None
    return raw[1:end].replace('\\"', '"').replace("\\\\", "\\")


def _parse_porcelain_path(line: str) -> str | None:
    if len(line) < len("XY "):
        return None
    raw = line[3:]
    if not raw:
        return None
    if " -> " in raw:
        new_path = raw.split(" -> ", 1)[1]
        return _unquote_git_path(new_path)
    if raw.startswith('"'):
        return _unquote_git_path(raw)
    return raw


def _find_uncommitted_manifests() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown error"
        logger.error("git status failed", extra={"detail": detail})
        raise RuntimeError(f"git status failed: {detail}")

    uncommitted: list[str] = []

    for line in result.stdout.splitlines():
        path = _parse_porcelain_path(line)
        if path and Path(path).name == "CODEMANIFEST":
            uncommitted.append(path)

    return uncommitted


def _prepare_run_settings(config: ProjectConfig, cli_options: dict) -> RunSettings | None:
    """Steps 1-4: resolve the run settings and run every pre-side-effect check.

    Resolution first (``resolve_run_settings`` — pure), then the review-config
    semantic validation, then the agent value guard, then the ralphex defaults
    sync — all before any launch side effect and before the first checkpoint.
    The step-3 guard reads the effective configuration (an amendment supplying
    ``build.agent`` satisfies it) and runs BEFORE the defaults sync, so a run
    it rejects writes nothing at all — the ``.ralphex/`` rewrite never starts.
    Without the guard a degenerate skip-run would crash at the tasks wrapper
    resolution: ``validate_review_config`` returns early on a skipped review.

    Args:
        config: Project configuration; ``config.build`` is the two-part build
            configuration (guaranteed non-None by the host structural guard).
        cli_options: CLI flags from the build invocation.

    Returns:
        The resolved run settings, or None when a check failed — the failure
        is already logged; the caller returns 1 without firing any event.
    """
    settings = resolve_run_settings(config.build, cli_options)

    try:
        validate_review_config(settings)
    except ValueError as error:
        logger.error("invalid review configuration", extra={"detail": str(error)})
        return None

    if settings.tasks.agent is None:
        logger.error(
            "no build agent resolved",
            extra={"remedy": "set build.agent in .goga/config.yml"},
        )
        return None

    try:
        sync_ralphex_defaults(config.build, settings)
    except ValueError as error:
        logger.error("ralphex defaults unavailable", extra={"detail": str(error)})
        return None

    return settings


def _resolve_work_identity() -> WorkIdentity:
    """Resolve the work identity of the run — the branch and its hosted topic.

    The single git read of the cycle: the branch name with the ``"unknown"``
    fallback, then the pure topic-directory composition guarded against an
    unsluggable branch (such a branch hosts no topic — the branch-only form).
    A composed topic directory that exists as a directory hosts the topic;
    its name is the slug and its parent's name the year.

    Returns:
        The work identity — topic-hosting (branch, slug, year) or branch-only.
    """
    branch = resolve_current_branch_name() or "unknown"

    try:
        topic_dir = resolve_topic_dir(branch)
    except ValueError:
        topic_dir = None

    if topic_dir is not None and topic_dir.is_dir():
        return WorkIdentity(branch=branch, slug=topic_dir.name, year=topic_dir.parent.name)

    return WorkIdentity(branch=branch)


def _tasks_stage_facts(settings: RunSettings) -> StageFacts:
    """Project the resolved tasks part onto the delivered tasks facts.

    The review-only members are None on the tasks part and the env carries
    names only — ``sorted(env)`` — so the delivered facts stay deterministic
    and secret-free.
    """
    tasks = settings.tasks

    return StageFacts(
        stage="tasks",
        agent=tasks.agent,
        env=sorted(tasks.env),
        max_iterations=tasks.max_iterations,
        session_timeout=tasks.session_timeout,
        idle_timeout=tasks.idle_timeout,
        wait=tasks.wait,
        roles=None,
        base_ref=None,
        strategy=None,
        finalize=None,
        additional=None,
    )


def _review_stage_facts(settings: RunSettings) -> StageFacts:
    """Project the resolved review part onto the delivered review facts.

    Always constructed — a skipped review still delivers its resolved facts
    (the facts describe the resolved settings, not the execution); the
    additional block mirrors into ``AdditionalFacts``.
    """
    review = settings.review

    return StageFacts(
        stage="review",
        agent=review.agent,
        env=sorted(review.env),
        max_iterations=review.max_iterations,
        session_timeout=review.session_timeout,
        idle_timeout=review.idle_timeout,
        wait=review.wait,
        roles=review.roles,
        base_ref=review.base_ref,
        strategy=review.strategy,
        finalize=review.finalize,
        additional=AdditionalFacts(
            agent=review.additional.agent,
            patience=review.additional.patience,
            max_iterations=review.additional.max_iterations,
        ),
    )


def _stage_agent(settings: RunSettings, stage: str) -> str:
    """The executor agent of one stage: the tasks agent, or the review-stage agent.

    The review stage runs under the additional agent when the strategy is
    short (the external-only pass), otherwise under the review agent — both
    already resolved with inheritance applied.
    """
    if stage == "tasks":
        return settings.tasks.agent

    if settings.review.strategy == "short":
        return settings.review.additional.agent

    return settings.review.agent


def _compose_pass_env(task_env: dict[str, str], cli_entries: dict[str, str]) -> dict[str, str] | None:
    """Compose the env layer of one pass: task env ⊕ CLI entries ⊖ engine keys.

    The container half of the CLI environment carriage: the decoded CLI
    entries apply ABOVE the pass's effective task env layer (explicit CLI
    input beats configuration and tool amendments on key conflict), and every
    key colliding with an engine variable drops silently — the inherited
    launch value stands. An empty composition is no layer at all (``None`` —
    pure inheritance), never an empty dict. The task env of the tasks pass
    never reaches the review pass: each pass composes from its own part only,
    while the CLI entries (explicit user input, already in the inherited
    environment) reach both.

    Args:
        task_env: The effective task env layer of the pass being launched
            (``build.env`` for the tasks pass, ``build.review.env`` for the
            review pass).
        cli_entries: The CLI environment mapping decoded once from the engine
            payload by the orchestrator.

    Returns:
        The composed env layer, or ``None`` when nothing survives the
        composition — the launch then inherits the process environment.
    """
    merged = {
        key: value
        for key, value in {**task_env, **cli_entries}.items()
        if key not in _ENGINE_ENV_KEYS
    }

    return merged or None


def _launch_pass(  # noqa: PLR0913, PLR0917 — the cli_entries parameter is contract-mandated (one decode feeds both passes)
    hooks: BuildHooks,
    moment: BuildMoment,
    settings: RunSettings,
    facts: StageFacts,
    stage: str,
    cli_entries: dict[str, str],
) -> int:
    """Run one pass: emit its start, launch it, emit its completion.

    The emit/launch/emit triple of a stage — the completion emission fires on
    every return path with the actual exit code; completion is a fact, not a
    success claim. The launch itself is delegated to ``run_build_pass``
    (config write + ``run_ralphex``); the ralphex command is never assembled
    here. The plan path and the dry-run flag travel on the moment, and the
    env layer composes from the pass's own task env plus the decoded CLI
    entries — it travels as data through ``run_build_pass``'s env parameter
    only, never through the process environment, the argv, or a log line.

    Args:
        hooks: The checkpoint surface of the run.
        moment: The uniform envelope of the run (plan path and dry-run flag).
        settings: The resolved run plan of the run.
        facts: The stage facts of the pass being launched.
        stage: The stage identity — exactly ``tasks`` or ``review``.
        cli_entries: The CLI environment mapping decoded once by the
            orchestrator; applied above this pass's task env layer.

    Returns:
        The exit code of the pass, propagated unchanged.
    """
    options = compose_pass_options(settings, stage)
    wrapper = resolve_wrapper_path(_stage_agent(settings, stage))
    env_layer = _compose_pass_env(
        settings.tasks.env if stage == "tasks" else settings.review.env,
        cli_entries,
    )

    hooks.emit_pass_started(moment, facts)
    exit_code = run_build_pass(
        moment.plan,
        settings,
        options,
        wrapper,
        moment.dry_run,
        env=env_layer,
    )
    hooks.emit_pass_completed(moment, facts, exit_code)

    return exit_code


def _completion_statuses(work: WorkIdentity) -> list[str]:
    """Re-read the history statuses of the work at the completion moment.

    Called after the relocation attempt, so the listing reflects the tree as
    the completion event finds it. The branch-only form (no hosted topic)
    yields an empty list without reading the tree; a hosted topic absent
    from the listing yields an empty list too.

    Args:
        work: The work identity of the run.

    Returns:
        The maximal present statuses of the work's topic, in scale order.
    """
    if work.slug is None:
        return []

    for record in collect_topic_statuses(year=work.year):
        if record.topic == work.slug:
            return record.statuses

    return []


def build(plan: str, config: ProjectConfig, cli_options: dict) -> int:
    """Execute the stable two-pass build cycle for a plan through ralphex.

    Algorithm 0-14: git pre-check on uncommitted CODEMANIFEST files (a
    failure returns 1 before any event fires — the moment never happened);
    settings resolution with the pre-side-effect validations (review-config
    semantics, the agent value guard on the effective configuration BEFORE
    the ``.ralphex/`` rewrite, the ralphex defaults sync); the one-time CLI
    entries payload decode; fact resolution — the work identity (one git
    read) and both stage facts with inheritance already applied; the
    validation gate before the first pass (not approved → one merged error,
    exit 1, no pass, no relocation, no further events); the start
    notification; the tasks pass; the review pass when the tasks pass
    succeeded and the review is not skipped; plan relocation on final-pass
    success; the history-status re-read; the completion notification; the
    exit code of the last executed pass.

    Pass modes: a non-skipped run is exactly two passes — tasks-only first,
    review second (the external-only pass under the short strategy, carried
    by the additional agent's wrapper); a skipped review yields exactly one
    tasks pass. Each pass composes its own env layer — its effective task
    env (``build.env`` / ``build.review.env``) with the decoded CLI entries
    applied above it and the engine-variable keys dropped; an empty
    composition is pure inheritance. The tasks task env never reaches the
    review pass, and no layer ever appears in options, argv, or logs.

    Args:
        plan: Path to the build plan file.
        config: Project configuration; its two-part ``build`` section is the
            settings source of the cycle.
        cli_options: CLI flags such as dry_run, skip_manifest_check,
            skip_review, base_ref, and the session knobs.

    Returns:
        The exit code of the last executed pass; 1 on a pre-launch failure
        (including a damaged CLI entries payload) or a vetoed gate.
    """
    if not cli_options.get("skip_manifest_check"):
        try:
            uncommitted = _find_uncommitted_manifests()
        except RuntimeError:
            return 1

        if uncommitted:
            logger.error("uncommitted codemanifest files found", extra={"paths": uncommitted})
            return 1

    dry_run = cli_options.get("dry_run", False)

    settings = _prepare_run_settings(config, cli_options)

    if settings is None:
        return 1

    # Step 5: decode the CLI entries payload once — the container half of the
    # carriage. The single decoded mapping feeds both pass compositions, so the
    # two passes can never diverge on what the CLI supplied. A damaged payload
    # is one clean error BEFORE the facts and the gate: no events fire, no pass
    # launches, nothing is partially applied. The decoded values never reach
    # the process environment, the argv, or a log line.
    try:
        cli_entries = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))
    except ValueError as error:
        logger.error("cli environment payload damaged", extra={"reason": str(error)})
        return 1

    work = _resolve_work_identity()
    moment = BuildMoment(plan=plan, work=work, dry_run=dry_run)
    tasks_facts = _tasks_stage_facts(settings)
    review_facts = _review_stage_facts(settings)

    hooks = BuildHooks()
    verdict = hooks.validate_build(moment, tasks_facts, review_facts, settings.skip)

    if not verdict.approved:
        logger.error(
            "build blocked by hook vetoes",
            extra={"violations": [f"{v.tool}/{v.hook}: {v.reason}" for v in verdict.violations]},
        )
        return 1

    hooks.emit_build_started(moment, tasks_facts, review_facts, settings.skip)

    logger.info("launching build passes", extra={"plan": plan, "dry_run": dry_run})

    stages = ["tasks"]

    exit_code = _launch_pass(hooks, moment, settings, tasks_facts, "tasks", cli_entries)

    if exit_code == 0 and not settings.skip:
        exit_code = _launch_pass(hooks, moment, settings, review_facts, "review", cli_entries)
        stages.append("review")

    relocation = move_completed_plan(plan, outcome=(exit_code == 0), dry_run=dry_run)
    statuses = _completion_statuses(work)

    hooks.emit_build_completed(moment, exit_code, stages, relocation, statuses)

    return exit_code
