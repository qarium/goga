from __future__ import annotations

from ..ralphex import run_ralphex
from .ralphex_config import write_ralphex_config
from .run_settings import RunSettings


def run_build_pass(  # noqa: PLR0913, PLR0917 — arity is CODEMANIFEST-mandated
    plan: str,
    settings: RunSettings,
    options: dict[str, str | int | bool],
    wrapper_path: str,
    dry_run: bool,
    env: dict[str, str] | None = None,
) -> int:
    """Execute one ralphex pass: write the pass config, delegate the launch.

    The unit of multi-passness: each pass writes its own `.ralphex/config`
    (so `claude_command` is the executor wrapper of THIS pass — the tasks
    wrapper for a tasks pass, the review wrapper for a review pass) and then
    delegates the launch to `run_ralphex`. The orchestrator composes passes on
    top of this routine; the ralphex command is never assembled or invoked
    here.

    Args:
        plan: Path to the plan file (markdown), passed verbatim to ralphex.
        settings: Resolved run plan (`RunSettings`) — carried to the config
            routine; the pass interprets nothing on it.
        options: Resolved ralphex options of the pass (composed by
            `compose_pass_options`; carries exactly one pass-mode bare flag),
            forwarded verbatim.
        wrapper_path: Executor wrapper of the current pass (tasks wrapper or
            review wrapper), written into `.ralphex/config`.
        dry_run: When True, print instead of launching (the pass config is
            still written — a harmless dry-run side effect matching the
            established behavior).
        env: Optional environment layer ({str: str}) forwarded verbatim to
            `run_ralphex` — the tasks pass receives the root env here, the
            review pass the review env. The pass adds no env logic of its
            own: the overlay composition lives in the launcher, and the
            layer never reaches the ralphex config written for this pass.

    Returns:
        The exit code returned by ralphex, propagated without transformation.
    """
    write_ralphex_config(settings, wrapper_path)

    return run_ralphex(plan, options, dry_run, env=env)
