"""The ``merge_workflow_build`` routine — layering the workflow build block onto the configuration."""

from __future__ import annotations

from ..config import AdditionalReviewConfig, BuildConfig, ReviewConfig
from ..pipeline.workflow import WorkflowBuild


def _merge_env(base: dict[str, str], overlay: dict[str, str] | None) -> dict[str, str]:
    """Overlay one env map onto another, key-wise.

    Args:
        base: The configuration env layer.
        overlay: The workflow block env layer, or ``None`` when absent.

    Returns:
        A new map — every overlay key wins, the rest of the base survives.
    """
    return {**base, **(overlay or {})}


def _merge_additional(
    additional: AdditionalReviewConfig | None,
    block: WorkflowBuild,
) -> AdditionalReviewConfig | None:
    """Layer the additional fields of the workflow block onto the config additional part.

    Args:
        additional: The config ``review.additional`` part, or ``None``.
        block: The workflow build block.

    Returns:
        A new :class:`AdditionalReviewConfig` — the block agent when set
        (otherwise the config agent), the key-wise merged env, and the config
        patience/max_iterations verbatim; ``None`` when neither side sets any
        additional field.
    """
    if additional is None:
        if block.review_additional_agent is None and block.review_additional_env is None:
            return None

        return AdditionalReviewConfig(agent=block.review_additional_agent, env=block.review_additional_env or {})

    return AdditionalReviewConfig(
        agent=block.review_additional_agent or additional.agent,
        env=_merge_env(additional.env, block.review_additional_env),
        patience=additional.patience,
        max_iterations=additional.max_iterations,
    )


def _merge_review(
    review: ReviewConfig | None,
    block: WorkflowBuild,
) -> ReviewConfig | None:
    """Layer the review fields of the workflow block onto the config review part.

    Args:
        review: The config ``build.review`` part, or ``None``.
        block: The workflow build block.

    Returns:
        A new :class:`ReviewConfig` — agents ``block or config``, env maps
        key-wise, every other field verbatim. A ``None`` config review stays
        ``None`` unless the block sets a review field; it is then constructed
        from the set fields only, so the settings resolution receives a
        well-formed layered configuration.
    """
    if review is None:
        review_fields_set = any(
            field is not None
            for field in (
                block.review_agent,
                block.review_env,
                block.review_additional_agent,
                block.review_additional_env,
            )
        )

        if not review_fields_set:
            return None

        return ReviewConfig(
            agent=block.review_agent,
            env=block.review_env or {},
            additional=_merge_additional(None, block),
        )

    return ReviewConfig(
        skip=review.skip,
        agent=block.review_agent or review.agent,
        env=_merge_env(review.env, block.review_env),
        roles=review.roles,
        base_ref=review.base_ref,
        strategy=review.strategy,
        finalize=review.finalize,
        additional=_merge_additional(review.additional, block),
        session_timeout=review.session_timeout,
        idle_timeout=review.idle_timeout,
        wait=review.wait,
        max_iterations=review.max_iterations,
    )


def merge_workflow_build(config: BuildConfig, build_block: WorkflowBuild) -> BuildConfig:
    """Overlay the six-field workflow build block onto the effective build configuration.

    Args:
        config: The effective build configuration — the base layer; always a
            non-``None`` :class:`BuildConfig` (the workflow block layers only
            onto an existing build section).
        build_block: The workflow build block model.

    Returns:
        A new layered :class:`BuildConfig` — agent fields override when set
        (an absent block field never overrides), env maps merge key-wise with
        the block winning per key, and every other field passes through
        verbatim. The inputs are never mutated; the nested models are new.
    """
    return BuildConfig(
        agent=build_block.agent or config.agent,
        env=_merge_env(config.env, build_block.env),
        max_iterations=config.max_iterations,
        session_timeout=config.session_timeout,
        idle_timeout=config.idle_timeout,
        wait=config.wait,
        prompts_dir=config.prompts_dir,
        agents_dir=config.agents_dir,
        proxy=config.proxy,
        hosts=config.hosts,
        review=_merge_review(config.review, build_block),
    )
