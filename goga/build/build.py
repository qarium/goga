from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from ..config import BuildConfig, ProjectConfig
from ..docker import decode_extra_env, decode_home_profiles
from ..history import collect_topic_statuses, resolve_current_branch_name, resolve_topic_dir
from .build_pass import run_build_pass
from .hooks import AdditionalFacts, BuildHooks, BuildMoment, StageFacts, WorkIdentity
from .pass_options import compose_pass_options
from .plan_relocation import move_completed_plan
from .ralphex_runtime import sync_ralphex_defaults
from .resolve_build_workflow import resolve_build_workflow
from .review_config import validate_review_config
from .role_env_wrappers import write_role_env_wrappers
from .run_settings import RunSettings, resolve_run_settings
from .workflow_build import merge_workflow_build

logger = logging.getLogger(__name__)


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


def _prepare_run_settings(build_config: BuildConfig, cli_options: dict) -> RunSettings | None:
    """Steps 5-8: resolve the run settings and run every pre-side-effect check.

    Args:
        build_config: The LAYERED effective build configuration in the
            two-part form (a workflow ``build:`` overlay, when any, already
            applied by the caller; guaranteed non-None by the host structural
            guard or the workflow build-section guard).
        cli_options: CLI flags from the build invocation.

    Returns:
        The resolved run settings, or None when a check failed — the failure
        is already logged and nothing has been written; the caller returns 1
        without firing any event.
    """
    settings = resolve_run_settings(build_config, cli_options)

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
        sync_ralphex_defaults(build_config, settings)
    except ValueError as error:
        logger.error("ralphex defaults unavailable", extra={"detail": str(error)})
        return None

    return settings


def _resolve_work_identity() -> WorkIdentity:
    """Resolve the work identity of the run — the branch and its hosted topic.

    Returns:
        The work identity — topic-hosting (branch, slug, year) or branch-only;
        an unsluggable branch hosts no topic.
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

    Args:
        settings: The resolved run plan of the run.

    Returns:
        The tasks stage facts — review-only members None, env as sorted names
        (secret-free).
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

    Args:
        settings: The resolved run plan of the run.

    Returns:
        The review stage facts — always constructed; a skipped review still
        delivers its resolved facts.
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


def _pass_role(settings: RunSettings, stage: str) -> str:
    """The executor role of one pass: tasks, review — or additional under short.

    Args:
        settings: The resolved run plan of the run.
        stage: The stage identity — exactly ``tasks`` or ``review``.

    Returns:
        The role name whose generated closure executes the pass — the
        additional role under the short strategy (the external-only pass).
    """
    if stage == "tasks":
        return "tasks"

    if settings.review.strategy == "short":
        return "additional"

    return "review"


def _launch_pass(  # noqa: PLR0913, PLR0917 — the signature carries the step-12 pass ladder inputs
    hooks: BuildHooks,
    moment: BuildMoment,
    settings: RunSettings,
    facts: StageFacts,
    stage: str,
    cli_entries: dict[str, str],
) -> int:
    """Run one pass: compose, generate the closures, write the pass config, emit, launch.

    Args:
        hooks: The checkpoint surface of the run.
        moment: The uniform envelope of the run (plan path and dry-run flag).
        settings: The resolved run plan of the run.
        facts: The stage facts of the pass being launched.
        stage: The stage identity — exactly ``tasks`` or ``review``.
        cli_entries: The decoded CLI entries payload — applied above each
            role's env layer inside the generated closures (the CLI wins per
            key, engine-variable keys dropped silently).

    Returns:
        The exit code of the pass, propagated unchanged — the launch carries
        no env layer; the subprocess inherits the container environment. The
        pass executor owns the pass-config write (both wrapper paths), so the
        surviving on-disk config is the one ralphex reads.
    """
    options = compose_pass_options(settings, stage)
    wrappers = write_role_env_wrappers(settings, cli_entries)
    wrapper = wrappers[_pass_role(settings, stage)]

    hooks.emit_pass_started(moment, facts)
    exit_code = run_build_pass(
        moment.plan,
        settings,
        options,
        str(wrapper),
        moment.dry_run,
        str(wrappers["additional"]),
    )
    hooks.emit_pass_completed(moment, facts, exit_code)

    return exit_code


def _completion_statuses(work: WorkIdentity) -> list[str]:
    """Re-read the history statuses of the work at the completion moment.

    Args:
        work: The work identity of the run.

    Returns:
        The maximal present statuses of the work's topic, in scale order —
        empty in the branch-only form and for a topic absent from the listing.
    """
    if work.slug is None:
        return []

    for record in collect_topic_statuses(year=work.year):
        if record.topic == work.slug:
            return record.statuses

    return []


def build(plan: str, config: ProjectConfig, cli_options: dict) -> int:  # noqa: C901, PLR0911 — the 17-step CODEMANIFEST algorithm owns its guard branches
    """Execute the stable two-pass build cycle for a plan through ralphex — a skipped review yields one tasks pass.

    Algorithm:
        0. Git pre-check on uncommitted CODEMANIFEST files — a failure
           returns 1 before any event fires (the moment never happened)
        1. Decode both carriage payloads once (the CLI entries via
           ``decode_extra_env``, the home bundle via ``decode_home_profiles``)
           and read ``GOGA_WORKFLOW``/``GOGA_PROFILE`` once each — exactly
           these four environment reads on the whole path; a damaged payload
           or bundle is one clean error, nothing partially applied, no events
        2. Workflow resolution via ``resolve_build_workflow`` (the CLI flag
           beats the environment value; no selection means no workflow and
           profile activation is ignored entirely) — a strict failure is one
           clean error, exit 1, no events
        3. The launch feedback line to stderr — ``Build running with
           workflow "<w>" and profile "<p>"`` — ONLY when a workflow is in
           effect AND a profile resolved; every other run prints no line
        4. Layering: a workflow ``build:`` block overlays the effective build
           section via ``merge_workflow_build`` (config < workflow build: <
           CLI); a build block over a configuration without a build section
           is one clean error naming the requirement, exit 1, no events —
           the layered configuration feeds every downstream step
        5. Settings resolution via ``resolve_run_settings`` over the layered
           configuration
        6. Review-config validation
        7. The agent value guard on the layered effective configuration
           (before the ``.ralphex/`` rewrite)
        8. The ralphex defaults sync
        9. Fact resolution — the work identity and both stage facts with
           inheritance already applied
        10. The validation gate before the first pass — not approved means
            one merged error, exit 1, no pass, no relocation, no further
            events
        11. The start notification
        12. The tasks pass: compose the options, generate the per-role
            closures (``write_role_env_wrappers`` with the decoded CLI
            entries), emit, launch via ``run_build_pass`` with the tasks
            wrapper and the additional wrapper path — the pass writes the
            config (``write_ralphex_config`` with both paths, the last write
            before the launch) and carries no env layer; a wrapper-generation
            ValueError (an illegal env name) is one clean error, exit 1
        13. The review pass when the tasks pass succeeded and the review is
            not skipped — the additional closure under the short strategy —
            with the same wrapper ladder
        14. Plan relocation on final-pass success
        15. The history-status re-read
        16. The completion notification
        17. The exit code of the last executed pass

    Args:
        plan: Path to the build plan file.
        config: Project configuration; its two-part ``build`` section is the
            settings source of the cycle.
        cli_options: CLI flags such as dry_run, skip_manifest_check,
            skip_review, base_ref, the session knobs, workflow, and profile.

    Returns:
        The exit code of the last executed pass; 1 on a pre-launch failure
        (including a damaged carriage payload or a workflow-layering guard)
        or a vetoed gate.
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

    # Step 1: decode both carriage payloads once and read the two selection
    # variables once each — the only environment reads on the whole path. A
    # damaged payload or bundle is one clean error BEFORE the facts and the
    # gate: no events fire, no pass launches, nothing is partially applied.
    # The decoded values never reach the process environment, the argv, or a
    # log line; the passes launch with no env layer — the subprocess inherits
    # the container environment, and the env layers ride the role closures.
    try:
        cli_entries = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))
        home_profiles = decode_home_profiles(os.environ.get("GOGA_HOME_PROFILES", ""))
    except ValueError as error:
        logger.error("environment payload damaged: %s", error)
        return 1

    workflow_env = os.environ.get("GOGA_WORKFLOW")
    profile_env = os.environ.get("GOGA_PROFILE")

    # Step 2: resolve the workflow — an explicit selection is strict (a
    # missing file or an escaping name is one clean error, exit 1, no
    # events); no selection means no workflow and activation is ignored.
    try:
        loaded = resolve_build_workflow(
            cli_options.get("workflow"),
            workflow_env,
            cli_options.get("profile"),
            profile_env,
            home_profiles,
        )
    except ValueError as error:
        logger.error("workflow resolution failed", extra={"reason": str(error)})
        return 1

    # Step 3: the launch feedback line — a workflow in effect AND a resolved
    # profile; every other run stays silent (the build/pipeline asymmetry is
    # contractual).
    if loaded is not None and loaded.profile is not None:
        workflow_name = cli_options.get("workflow") or workflow_env
        print(f'Build running with workflow "{workflow_name}" and profile "{loaded.profile.name}"', file=sys.stderr)

    # Step 4: layer the workflow build block onto the effective build
    # section. The D2 guard: a build block requires a build section to layer
    # onto — one clean error instead of the raw attribute failure.
    build_config = config.build

    if loaded is not None and loaded.document.build is not None:
        if build_config is None:
            logger.error(
                "workflow build block requires a build section",
                extra={"remedy": "set the build section in .goga/config.yml"},
            )
            return 1

        build_config = merge_workflow_build(build_config, loaded.document.build)

    settings = _prepare_run_settings(build_config, cli_options)

    if settings is None:
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

    # The pass ladder — a wrapper-generation ValueError (an illegal env
    # variable name in a config/workflow/CLI layer) is one clean error and
    # exit 1, never a traceback: the generation validates every role before
    # writing any closure, so no partial pass state exists.
    try:
        exit_code = _launch_pass(hooks, moment, settings, tasks_facts, "tasks", cli_entries)

        if exit_code == 0 and not settings.skip:
            exit_code = _launch_pass(hooks, moment, settings, review_facts, "review", cli_entries)
            stages.append("review")
    except ValueError as error:
        logger.error("pass wrapper generation failed", extra={"reason": str(error)})
        return 1

    relocation = move_completed_plan(plan, outcome=(exit_code == 0), dry_run=dry_run)
    statuses = _completion_statuses(work)

    hooks.emit_build_completed(moment, exit_code, stages, relocation, statuses)

    return exit_code
