from __future__ import annotations

import logging
from pathlib import Path

from ..config import BuildConfig

logger = logging.getLogger(__name__)

_DEFAULT_CLAUDE_ARGS = "--dangerously-skip-permissions --output-format stream-json --verbose"


def write_ralphex_config(config: BuildConfig, wrapper_path: str) -> None:
    """Write the .ralphex/config INI for one ralphex pass.

    Populates the ralphex config keys covered by the agent-wrappers contract:
    `claude_command` set to the resolved absolute wrapper path of THE CURRENT
    PASS, `claude_args` set to its fixed default (no config field overrides it
    today), `codex_enabled` derived from `BuildConfig`, and
    `preserve_anthropic_api_key` pinned to `true` so the ralphex runner does not
    unset `ANTHROPIC_API_KEY` before invoking the agent wrapper.
    `move_plan_on_completion` is pinned to `false` — goga relocates the plan
    itself via `move_completed_plan`, so ralphex must never move it (its own
    default is true, which would relocate the plan after pass 1 of a two-pass
    run). No codex-specific ralphex keys are written.

    In a two-pass run this routine is called twice — each pass passes its own
    executor wrapper (task wrapper for pass 1, review wrapper for pass 2), so
    the `claude_command` rewrite between the passes is expressed by the two
    calls themselves: the file is rewritten whole, never merged into.

    Args:
        config: Build configuration carrying the codex_review field.
        wrapper_path: Resolved absolute in-container wrapper path of this pass.
    """
    ralphex_dir = Path(".ralphex")
    ralphex_dir.mkdir(exist_ok=True)

    codex_enabled = str(config.codex_review or False).lower()

    config_lines = [
        f"claude_command = {wrapper_path}",
        f"claude_args = {_DEFAULT_CLAUDE_ARGS}",
        f"codex_enabled = {codex_enabled}",
        "preserve_anthropic_api_key = true",
        "move_plan_on_completion = false",
    ]

    (ralphex_dir / "config").write_text("\n".join(config_lines) + "\n")
    logger.info("wrote .ralphex/config", extra={"claude_command": wrapper_path})
