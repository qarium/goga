from __future__ import annotations

from pathlib import Path

from ..agents import resolve_wrapper_path
from .run_settings import RunSettings

ROLE_WHITELIST: frozenset[str] = frozenset(
    {"quality", "implementation", "testing", "simplification", "documentation"},
)

STRATEGY_WHITELIST: frozenset[str] = frozenset({"full", "medium", "short"})


def validate_review_config(settings: RunSettings) -> None:
    """Semantically validate the review configuration of a run whose review pass will execute.

    Raises ValueError naming the invalid value: an unknown reviewer role (the
    whitelist is synchronized with the default ralphex review agents), a
    non-empty review env declared without a review agent (the
    env-requires-agent gate), a review agent that resolved to None at all
    (reachable only on direct in-container invocation — the host launcher
    requires build.agent up front), a review-agent wrapper script that does
    not exist, an additional-agent wrapper that does not exist when the
    strategy engages the external review (short always; full with an
    additional agent), or a strategy outside the full | medium | short
    whitelist. A skipped run returns without any checks — no review pass of
    it will execute, so no review field of it is validated.

    The checks run in a fixed order — roles, then the env gate, then the
    review-agent wrapper, then the additional-agent wrapper, then the
    strategy — so the first violated rule is the one reported. All of them
    live here by design: this routine is what must fail before any side
    effect — before .ralphex/ is written and before the first checkpoint
    fires. `resolve_wrapper_path` stays a pure string builder (the boundary
    owned by goga/agents); the tasks-pass agent wrapper is deliberately not
    validated, its absence surfaces at ralphex time.

    Args:
        settings: Resolved run plan of the build; skip and every review fact
            the checks read (roles, env, agent, additional, strategy) come
            from its review part.
    """
    if settings.skip:
        return

    review = settings.review

    for role in review.roles or []:
        if role not in ROLE_WHITELIST:
            raise ValueError(f"unknown review role: {role!r}; expected one of {sorted(ROLE_WHITELIST)}")

    if review.env and review.agent is None:
        raise ValueError("review env requires a review agent: set build.review.agent")

    if review.agent is None:
        raise ValueError("no review agent resolved: set build.agent or build.review.agent")

    wrapper = resolve_wrapper_path(review.agent)

    if not Path(wrapper).is_file():
        raise ValueError(f"review agent wrapper not found: {wrapper} (agent {review.agent!r})")

    additional_agent = review.additional.agent

    if review.strategy == "short" or (review.strategy == "full" and additional_agent is not None):
        additional_wrapper = resolve_wrapper_path(additional_agent)

        if not Path(additional_wrapper).is_file():
            raise ValueError(
                f"additional review agent wrapper not found: {additional_wrapper} "
                f"(agent {additional_agent!r})",
            )

    if review.strategy not in STRATEGY_WHITELIST:
        raise ValueError(
            f"unknown review strategy: {review.strategy!r}; expected one of {sorted(STRATEGY_WHITELIST)}",
        )
