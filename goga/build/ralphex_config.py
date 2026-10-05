from __future__ import annotations

import logging
from pathlib import Path

from ..agents import resolve_wrapper_path
from .run_settings import RunSettings

logger = logging.getLogger(__name__)

_DEFAULT_CLAUDE_ARGS = "--dangerously-skip-permissions --output-format stream-json --verbose"


def write_ralphex_config(settings: RunSettings, wrapper_path: str) -> None:
    """Write the .ralphex/config INI for one ralphex pass.

    Args:
        settings: Resolved run plan; the external-review surface and the
            finalize flag derive from its review part.
        wrapper_path: Resolved absolute in-container wrapper path of this pass.

    Note:
        The tasks-pass copy carries the review keys too — ``--tasks-only``
        ignores every review-phase key — keeping this routine a pure function
        of (settings, wrapper).
    """
    review = settings.review

    config_lines = [
        f"claude_command = {wrapper_path}",
        f"claude_args = {_DEFAULT_CLAUDE_ARGS}",
        "preserve_anthropic_api_key = true",
        "move_plan_on_completion = false",
    ]

    additional_agent = review.additional.agent

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
