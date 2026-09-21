from __future__ import annotations

import logging
from pathlib import Path

from ..agents import resolve_wrapper_path
from .run_settings import RunSettings

logger = logging.getLogger(__name__)

_DEFAULT_CLAUDE_ARGS = "--dangerously-skip-permissions --output-format stream-json --verbose"


def write_ralphex_config(settings: RunSettings, wrapper_path: str) -> None:
    """Write the .ralphex/config INI for one ralphex pass.

    Rewrites the file whole, never merged into a previous copy. The fixed
    key block: `claude_command` set to the resolved absolute wrapper path of
    THE CURRENT PASS, `claude_args` set to its fixed default (no settings
    field overrides it today), `preserve_anthropic_api_key` pinned to `true`
    so the ralphex runner hands `ANTHROPIC_API_KEY` to the agent wrapper, and
    `move_plan_on_completion` pinned to `false` — goga relocates the plan
    itself via `move_completed_plan`, so ralphex must never move it after
    pass 1 of a two-pass run.

    The external-review surface derives only from the review part of the
    settings: strategy `medium` writes `codex_enabled = false` (the external
    review explicitly disabled) and no external keys; `full` and `short`
    leave `codex_enabled` unwritten (the ralphex default, enabled) and, when
    an additional agent is resolved, write `external_review_tool = custom`
    with `custom_review_script` set to that agent's wrapper path — a None
    additional agent leaves both unwritten (the ralphex default, codex). A
    set finalize prompt writes `finalize_enabled = true`; when unset the key
    stays unwritten and the step remains at the ralphex default (off).

    In a two-pass run this routine is called twice — the same settings, only
    the executor wrapper differs (task wrapper for pass 1, review wrapper for
    pass 2), so the `claude_command` rewrite between the passes is expressed
    by the two calls themselves. The tasks-pass copy carries the review keys
    too — harmless, `--tasks-only` ignores every review-phase key — which
    keeps this routine a pure function of (settings, wrapper).

    Args:
        settings: Resolved run plan; the external-review surface and the
            finalize flag derive from its review part.
        wrapper_path: Resolved absolute in-container wrapper path of this pass.
    """
    review = settings.review

    config_lines = [
        f"claude_command = {wrapper_path}",
        f"claude_args = {_DEFAULT_CLAUDE_ARGS}",
        "preserve_anthropic_api_key = true",
        "move_plan_on_completion = false",
    ]

    additional_agent = review.additional.agent if review.additional is not None else None

    if review.strategy == "medium":
        config_lines.append("codex_enabled = false")
    elif additional_agent is not None:
        config_lines.append("external_review_tool = custom")
        config_lines.append(f"custom_review_script = {resolve_wrapper_path(additional_agent)}")

    if review.finalize is not None:
        config_lines.append("finalize_enabled = true")

    ralphex_dir = Path(".ralphex")
    ralphex_dir.mkdir(exist_ok=True)

    (ralphex_dir / "config").write_text("\n".join(config_lines) + "\n")
    logger.info("wrote .ralphex/config", extra={"claude_command": wrapper_path})
