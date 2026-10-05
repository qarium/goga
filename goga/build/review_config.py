from __future__ import annotations

from pathlib import Path

from ..agents import resolve_wrapper_path
from .run_settings import RunSettings

ROLE_WHITELIST: frozenset[str] = frozenset(
    {"quality", "implementation", "testing", "simplification", "documentation"},
)

STRATEGY_WHITELIST: frozenset[str] = frozenset({"full", "medium", "short"})


def validate_review_config(settings: RunSettings) -> None:
    """Semantically validate the review configuration of the review pass — a skipped run returns without checks.

    Args:
        settings: Resolved run plan of the build; skip and every review fact
            the checks read (roles, env, agent, additional, strategy) come
            from its review part.

    Raises:
        ValueError: Naming the invalid value — an unknown reviewer role, a
            non-empty review env without a review agent, a review agent that
            resolved to None, a missing review-agent or additional-agent
            wrapper (the latter when the strategy engages the external review:
            short always, full with an additional agent), or a strategy
            outside full | medium | short. The checks run in that fixed
            order, so the first violated rule is the one reported.
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
                f"additional review agent wrapper not found: {additional_wrapper} (agent {additional_agent!r})",
            )

    if review.strategy not in STRATEGY_WHITELIST:
        raise ValueError(
            f"unknown review strategy: {review.strategy!r}; expected one of {sorted(STRATEGY_WHITELIST)}",
        )
