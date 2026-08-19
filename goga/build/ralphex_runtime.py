from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..config import BuildConfig
from .review_options import ReviewOptions

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
    """Bring `dest` to exactly the regular files of `src` (full rewrite, no accumulation)."""
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    for src_file in sorted(src.iterdir()):
        if src_file.is_file():
            shutil.copy2(src_file, dest / src_file.name)


def _agent_name(line: str) -> str | None:
    """Role name of a `{{agent:X}}` line, None for any other line."""
    stripped = line.strip()
    if not (stripped.startswith(_AGENT_LINE_PREFIX) and stripped.endswith(_AGENT_LINE_SUFFIX)):
        return None
    return stripped[len(_AGENT_LINE_PREFIX) : -len(_AGENT_LINE_SUFFIX)]


def _filter_review_prompt(text: str, selected: list[str]) -> str:
    """Drop `{{agent:X}}` lines of unselected roles and adapt the accompanying text.

    Composition is determined ONLY by the `{{agent:X}}` lines (per the `ralphex`
    practice); the counter rewrites are a fixed list of literal fragments of the
    ralphex v1.6.1 templates — a fragment that does not match is a no-op, never
    an error, so each group is safe to run against either review prompt. `n`
    counts the REMAINING agent lines (a role may be absent from a given phase),
    not `len(selected)`. With no remaining agent lines the phase runs without
    subagents and the accompanying text is left as filtered, no counter rewrites.
    """
    lines = text.splitlines(keepends=True)
    kept = [line for line in lines if (name := _agent_name(line)) is None or name in selected]
    n = sum(1 for line in kept if _agent_name(line) is not None)

    result = "".join(kept)

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


def sync_ralphex_defaults(config: BuildConfig, review: ReviewOptions) -> None:
    """Fully rewrite .ralphex/prompts/ and .ralphex/agents/ from their sources.

    Sources are the configured custom `prompts_dir`/`agents_dir` of `BuildConfig`
    when set, otherwise the vendored ralphex defaults under goga/assets/ralphex/.
    Both target directories are cleared before copying, so stale files from a
    previous run never survive. The agents directory is always copied whole (all
    review-agent definitions), regardless of the declared roles.

    When `review.roles` is a non-empty list, both review prompts are filtered to
    the selected roles: unselected `{{agent:X}}` lines are dropped and the
    accompanying text (agent counters, launch wording) is adapted to the number
    of remaining agent lines. With the full default set — or no roles at all —
    the prompts land byte-identical to their sources; custom directories are
    copied as-is, without filtering.

    Args:
        config: Build configuration with the optional prompts_dir / agents_dir fields.
        review: Resolved review options; only `roles` is read (duck-typed).
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

    roles = review.roles
    if not roles:
        logger.info("synced ralphex defaults", extra={"prompts": str(prompts_src), "agents": str(agents_src)})
        return

    custom = config.prompts_dir is not None
    for name in ("review_first.txt", "review_second.txt"):
        if custom:
            continue
        prompt_file = ralphex_dir / "prompts" / name
        filtered = _filter_review_prompt(prompt_file.read_text(), list(roles))
        prompt_file.write_text(filtered)

    logger.info(
        "synced ralphex defaults",
        extra={"prompts": str(prompts_src), "agents": str(agents_src), "roles": list(roles)},
    )
