from __future__ import annotations

from dataclasses import dataclass

from ..config import BuildConfig


@dataclass(kw_only=True, frozen=True)
class ReviewOptions:
    """Fully reduced review-phase decision for a single `goga build` run.

    Immutable value-object produced by `resolve_review_options` — never loaded
    from YAML directly. `skip` is the final skip decision (False when no source
    set it); `review_agent` and `roles` are verbatim from `build.review_executor`;
    `two_pass` is True when a review executor agent is set and either differs
    from the task executor agent or carries a non-empty review env;
    `review_env` is the review-pass environment layer, verbatim (an empty dict
    when the section declares no env). Branch priority between `skip` and
    `two_pass` belongs to the orchestrator, not to this value-object.
    """

    skip: bool
    review_agent: str | None
    roles: list[str] | None
    two_pass: bool
    review_env: dict[str, str]


def resolve_review_options(config: BuildConfig, cli_options: dict) -> ReviewOptions:
    """Reduce the tri-state skip flag and the review executor section to a decision.

    Pure function — no I/O, no validation, no normalization. Precedence for
    `skip` is CLI > ProjectConfig > omit: a non-None `cli_options["skip_review"]`
    wins, otherwise `build.review_executor.skip` (when the section exists),
    otherwise False. An empty roles list travels to the consumer as an empty
    list (the "full default set" reading belongs to the consumer).

    `two_pass` is True when a review agent is set and it differs from the task
    executor agent OR the review env is non-empty (dictionary equality with
    `task_executor.env` is irrelevant — only non-emptiness is checked).
    `review_env` is `build.review_executor.env` verbatim (shared by reference,
    like `TaskExecutorConfig.env`) — an empty dict when there is no section.

    Args:
        config: Build configuration with the optional review_executor section.
        cli_options: In-container CLI options; only `skip_review` is read.
    """
    review_executor = config.review_executor

    cli_skip = cli_options.get("skip_review")

    if cli_skip is not None:
        skip = cli_skip
    elif review_executor is not None and review_executor.skip is not None:
        skip = review_executor.skip
    else:
        skip = False

    review_agent = review_executor.agent if review_executor is not None else None
    roles = review_executor.roles if review_executor is not None else None
    review_env = review_executor.env if review_executor is not None else {}
    two_pass = review_agent is not None and (review_agent != config.task_executor.agent or bool(review_env))

    return ReviewOptions(
        skip=skip,
        review_agent=review_agent,
        roles=roles,
        two_pass=two_pass,
        review_env=review_env,
    )
