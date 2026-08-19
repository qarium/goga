from __future__ import annotations

from ..config import BuildConfig
from ..ralphex import run_ralphex
from .ralphex_config import write_ralphex_config


def run_build_pass(
    plan: str,
    config: BuildConfig,
    options: dict,
    wrapper_path: str,
    dry_run: bool,
) -> int:
    """Execute one ralphex pass: write the pass config, delegate the launch.

    The unit of multi-passness: each pass writes its own `.ralphex/config`
    (so `claude_command` is the executor wrapper of THIS pass — the task
    wrapper for a tasks pass, the review wrapper for a review pass) and then
    delegates the launch to `run_ralphex`. The orchestrator composes passes on
    top of this routine; the ralphex command is never assembled or invoked
    here.

    Args:
        plan: Path to the plan file (markdown), passed verbatim to ralphex.
        config: Build configuration (`BuildConfig`) of the run.
        options: Resolved ralphex options of the pass; may carry the pass-mode
            bare flags `tasks_only` or `review`, forwarded verbatim.
        wrapper_path: Executor wrapper of the current pass (task wrapper or
            review wrapper), written into `.ralphex/config`.
        dry_run: When True, print instead of launching (the pass config is
            still written — a harmless dry-run side effect matching the
            established behavior).

    Returns:
        The exit code returned by ralphex, propagated without transformation.
    """
    write_ralphex_config(config, wrapper_path)

    return run_ralphex(plan, options, dry_run)
