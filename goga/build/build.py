from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..agents import resolve_wrapper_path
from ..config import ProjectConfig
from .build_pass import run_build_pass
from .plan_relocation import move_completed_plan
from .ralphex_runtime import sync_ralphex_defaults
from .review_config import validate_review_config
from .review_options import resolve_review_options

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


def _resolve_options(config: ProjectConfig, cli_options: dict) -> dict[str, str | int | bool]:
    """Resolve ralphex options with precedence CLI > BuildConfig > omit.

    Applies the precedence HERE in the build domain so `run_ralphex` performs no
    resolution. For store_true bool keys, a CLI value of False is treated as
    "not set -> defer to config" — bit-identical to the original
    ``if cli_value or getattr(config.build, ...)`` semantics. For scalar keys the
    CLI value wins when present (not None) and otherwise falls back to BuildConfig.
    This helper knows no ralphex flag names; `run_ralphex` maps the resolved keys.

    The pass-mode keys `tasks_only`/`review` are deliberately NOT resolved here —
    they are mode flags of a single pass, laid on top of the base options by the
    orchestrator with a dict copy, never read from config or CLI passthrough.

    Args:
        config: Project configuration carrying BuildConfig option defaults.
        cli_options: CLI flags from the build invocation.

    Returns:
        Resolved option dict keyed by ralphex option name.
    """
    resolved: dict[str, str | int | bool] = {}

    for key in ("worktree", "skip_finalize"):
        resolved[key] = bool(cli_options.get(key) or getattr(config.build, key))

    for key in ("session_timeout", "idle_timeout", "wait", "max_iterations", "review_patience"):
        cli_value = cli_options.get(key)
        resolved[key] = cli_value if cli_value is not None else getattr(config.build, key)

    return resolved


def build(plan: str, config: ProjectConfig, cli_options: dict) -> int:
    """Execute the build pipeline for a plan, orchestrating its review phase.

    Algorithm 0-9: git pre-check on uncommitted CODEMANIFEST files; task wrapper
    resolution; review-option reduction (`resolve_review_options`); semantic
    validation of the review configuration and the defaults sync — both before
    any launch side effect; base option resolution (CLI > BuildConfig > omit);
    the pass loop, where each pass writes its own `.ralphex/config` and delegates
    the launch to `run_ralphex` via `run_build_pass`; plan relocation on success
    of the final pass; the exit code of the last pass is returned.

    Pass modes: a skipped run makes exactly one tasks-only pass (no review phase
    of any kind, the review env ignored entirely); a two-pass run (review
    executor with a differing agent OR a non-empty review env) runs tasks-only
    first — without an env layer — and, when it succeeds, a review-only pass
    with the review wrapper and the review env as its environment layer; a
    pass-1 failure exits with its code and skips pass 2 (and its env layer);
    anything else is one full pass, without a layer.

    Args:
        plan: Path to the build plan file.
        config: Project configuration with build settings and task executor.
        cli_options: CLI flags such as dry_run, skip_manifest_check,
            skip_review, worktree, etc.

    Returns:
        The exit code of the last executed pass; 1 on a pre-launch failure.
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

    task_wrapper = resolve_wrapper_path(config.build.task_executor.agent)

    review = resolve_review_options(config.build, cli_options)

    if not review.skip:
        try:
            validate_review_config(config.build, review)
        except ValueError as error:
            logger.error("invalid review configuration", extra={"detail": str(error)})
            return 1

    try:
        sync_ralphex_defaults(config.build, review)
    except ValueError as error:
        logger.error("ralphex defaults unavailable", extra={"detail": str(error)})
        return 1

    base = _resolve_options(config, cli_options)

    logger.info("launching build passes", extra={"plan": plan, "dry_run": dry_run})

    if review.skip:
        exit_code = run_build_pass(plan, config.build, {**base, "tasks_only": True}, task_wrapper, dry_run)
    elif review.two_pass:
        review_wrapper = resolve_wrapper_path(review.review_agent)
        exit_code = run_build_pass(plan, config.build, {**base, "tasks_only": True}, task_wrapper, dry_run)
        if exit_code == 0:
            exit_code = run_build_pass(
                plan, config.build, {**base, "review": True}, review_wrapper, dry_run, env=review.review_env
            )
    else:
        exit_code = run_build_pass(plan, config.build, base, task_wrapper, dry_run)

    move_completed_plan(plan, outcome=(exit_code == 0), dry_run=dry_run)

    return exit_code
