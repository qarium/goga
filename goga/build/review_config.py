from __future__ import annotations

from pathlib import Path

from ..agents import resolve_wrapper_path
from ..config import BuildConfig
from .review_options import ReviewOptions

ROLE_WHITELIST: frozenset[str] = frozenset(
    {"quality", "implementation", "testing", "simplification", "documentation"},
)


def validate_review_config(
    config: BuildConfig,  # noqa: ARG001 — part of the CODEMANIFEST signature
    review: ReviewOptions,
) -> None:
    """Semantically validate the review configuration of a run whose review phase will run.

    Raises ValueError naming the invalid value: an unknown reviewer role (the
    whitelist is synchronized with the default ralphex review agents), a
    non-empty review env declared without a review agent (the env-requires-
    agent gate), or, in a two-pass run, a review executor whose wrapper script
    does not exist. A skipped run returns without any checks — no review phase
    of it will execute, so no review field of it is validated.

    The checks run in a fixed order — roles, then the env gate, then the
    wrapper existence check — so the first violated rule is the one reported.
    All of them live here by design: this routine is what must fail before any
    side effect — before .ralphex/ is written and before ralphex is launched.
    `resolve_wrapper_path` stays a pure string builder (the boundary owned by
    goga/agents); the task executor wrapper is deliberately not validated, its
    absence surfaces at ralphex time.

    Args:
        config: Build configuration of the run (context of the review decision).
        review: Resolved review options; skip, roles, review_env, review_agent
            and two_pass are read.
    """
    if review.skip:
        return

    for role in review.roles or []:
        if role not in ROLE_WHITELIST:
            raise ValueError(f"unknown review role: {role!r}; expected one of {sorted(ROLE_WHITELIST)}")

    if review.review_env and review.review_agent is None:
        raise ValueError("review env requires a review agent: set build.review_executor.agent")

    if review.two_pass:
        wrapper = resolve_wrapper_path(review.review_agent)

        if not Path(wrapper).is_file():
            raise ValueError(
                f"review executor wrapper not found: {wrapper} (agent {review.review_agent!r})",
            )
