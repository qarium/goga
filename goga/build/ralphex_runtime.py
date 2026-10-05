from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..config import BuildConfig
from .run_settings import RunSettings

logger = logging.getLogger(__name__)

_VENDORED_PROMPTS = Path(__file__).resolve().parent.parent / "assets" / "ralphex" / "prompts"
_VENDORED_AGENTS = Path(__file__).resolve().parent.parent / "assets" / "ralphex" / "agents"

_AGENT_LINE_PREFIX = "{{agent:"
_AGENT_LINE_SUFFIX = "}}"

# Default agent-line counts of the ralphex v1.6.1 review templates; the counter
# rewrites are skipped exactly at these values to keep the default composition
# byte-identical to its source.
_FIRST_PASS_AGENT_COUNT = 5
_SECOND_PASS_AGENT_COUNT = 2


def _rewrite_dir(src: Path, dest: Path) -> None:
    """Bring ``dest`` to exactly the regular files of ``src`` (full rewrite, no accumulation).

    Args:
        src: Source directory whose regular files are copied.
        dest: Destination directory, cleared and recreated first.
    """
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(src.iterdir()):
        if src_file.is_file():
            shutil.copy2(src_file, dest / src_file.name)


def _agent_name(line: str) -> str | None:
    """Role name of a ``{{agent:X}}`` line, None for any other line.

    Args:
        line: Prompt line to inspect.

    Returns:
        The role name of a ``{{agent:X}}`` line, or None for any other line.
    """
    stripped = line.strip()

    if not (stripped.startswith(_AGENT_LINE_PREFIX) and stripped.endswith(_AGENT_LINE_SUFFIX)):
        return None
    return stripped[len(_AGENT_LINE_PREFIX) : -len(_AGENT_LINE_SUFFIX)]


def _filter_review_prompt(text: str, selected: list[str]) -> str:
    """Drop ``{{agent:X}}`` lines of unselected roles and adapt the accompanying text.

    Args:
        text: Review prompt text of one phase.
        selected: Selected role names; the ``{{agent:X}}`` lines of other roles drop.

    Returns:
        The filtered text — the counter rewrites follow the number of
        remaining agent lines (not ``len(selected)``) and are no-ops for
        fragments that do not match, never errors.
    """
    lines = text.splitlines(keepends=True)
    kept = [line for line in lines if (name := _agent_name(line)) is None or name in selected]
    n = sum(1 for line in kept if _agent_name(line) is not None)

    result = "".join(kept)

    if n == 0:
        # A phase without subagents is a regular case — the accompanying text
        # is left as filtered, with no counter rewrites.
        return result

    if n != _FIRST_PASS_AGENT_COUNT:
        # review_first counters — each rewrite is a no-op for the full 5-role set
        # and for any text not carrying the fragment; the guard preserves
        # byte-identity of the default composition.
        result = result.replace("Launch ALL 5 Review Agents", f"Launch ALL {n} Review Agents")
        result = result.replace("All 5 agent invocations", f"All {n} agent invocations")
        result = result.replace("until ALL 5 agents", f"until ALL {n} agents")
        result = result.replace("launches 5 parallel reviewer agents", f"launches {n} parallel reviewer agents")

    if n != _SECOND_PASS_AGENT_COUNT:
        # review_second counters — the BOTH/both wording of the 2-agent template
        # only fits n == 2; n > 2 gets the ALL forms, n == 1 the singular ones.
        plural = n > _SECOND_PASS_AGENT_COUNT
        result = result.replace("uses 2 agents", f"uses {n} agents")
        result = result.replace("until BOTH agents", f"until ALL {n} agents" if plural else "until the agent")
        result = result.replace(
            "Both agent invocations", f"All {n} agent invocations" if plural else "The agent invocation"
        )
        result = result.replace("until both complete", f"until all {n} complete" if plural else "until it completes")
        result = result.replace(
            "emit them both in one response", "emit them all in one response" if plural else "emit it in one response"
        )

    return result


def sync_ralphex_defaults(config: BuildConfig, settings: RunSettings) -> None:
    """Fully rewrite .ralphex/prompts/ and .ralphex/agents/ from their sources.

    Args:
        config: Build configuration; ``prompts_dir`` / ``agents_dir`` select
            custom sources, else the vendored ralphex defaults apply.
        settings: Resolved run plan — its review roles and finalize prompt
            drive the prompt filtering and the finalize materialization.

    Raises:
        ValueError: When a resolved source directory is missing — the error
            names the vendoring remedy.

    Note:
        Non-empty review roles filter both vendored review prompts to the
        selected roles; custom directories and the full default set are copied
        without filtering. The agents directory is always copied whole. A set
        finalize prompt is written verbatim to ``.ralphex/agents/finalize.txt``;
        unset leaves the step at the ralphex default (off).
    """
    prompts_src = Path(config.prompts_dir) if config.prompts_dir else _VENDORED_PROMPTS
    agents_src = Path(config.agents_dir) if config.agents_dir else _VENDORED_AGENTS

    for src in (prompts_src, agents_src):
        if not src.is_dir():
            logger.error("vendored ralphex defaults not found", extra={"path": str(src)})
            raise ValueError(
                f"vendored ralphex defaults not found at {src} — "
                "run ralphex --dump-defaults <repo>/goga/assets/ralphex to vendor them"
            )

    ralphex_dir = Path(".ralphex")

    _rewrite_dir(prompts_src, ralphex_dir / "prompts")
    _rewrite_dir(agents_src, ralphex_dir / "agents")

    roles = settings.review.roles

    if roles and config.prompts_dir is None:
        for name in ("review_first.txt", "review_second.txt"):
            prompt_file = ralphex_dir / "prompts" / name
            filtered = _filter_review_prompt(prompt_file.read_text(), roles)
            prompt_file.write_text(filtered)

    if settings.review.finalize is not None:
        (ralphex_dir / "agents" / "finalize.txt").write_text(settings.review.finalize)

    extra: dict[str, object] = {"prompts": str(prompts_src), "agents": str(agents_src)}

    if roles:
        extra["roles"] = list(roles)

    logger.info("synced ralphex defaults", extra=extra)
