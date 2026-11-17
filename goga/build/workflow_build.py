"""The ``merge_workflow_build`` routine — layering the workflow layers onto the configuration."""

from __future__ import annotations

from ..config import AdditionalReviewConfig, BuildConfig, ReviewConfig
from ..pipeline.workflow import WorkflowBuild


def _merge_env(base: dict[str, str], *overlays: dict[str, str] | None) -> dict[str, str]:
    """Overlay env maps onto a base, key-wise.

    Args:
        base: The base env layer.
        overlays: The upper layers, later winning per key; ``None`` overlays
            (absent layers) are skips.

    Returns:
        A new map — every later-layer key wins, the rest of the base survives.
    """
    merged = dict(base)

    for overlay in overlays:
        if overlay:
            merged.update(overlay)

    return merged


def _merge_additional(
    additional: AdditionalReviewConfig | None,
    block: WorkflowBuild | None,
    global_agent: str | None,
    global_env: dict[str, str] | None,
) -> AdditionalReviewConfig | None:
    """Layer the additional-pass sources onto the config additional part.

    Args:
        additional: The config ``review.additional`` part, or ``None``.
        block: The workflow build block, or ``None`` when the workflow
            carries no block.
        global_agent: The workflow's global agent, or ``None``.
        global_env: The workflow's global env map, or ``None``.

    Returns:
        A new :class:`AdditionalReviewConfig` — the agent resolving
        build-block > global > configuration, the key-wise layered env
        (configuration < global < block), and the config
        patience/max_iterations verbatim; ``None`` when no source at any
        layer sets an additional field.
    """
    block_agent = block.review_additional_agent if block is not None else None
    block_env = block.review_additional_env if block is not None else None

    if additional is None:
        if block_agent is None and block_env is None and global_agent is None and global_env is None:
            return None

        return AdditionalReviewConfig(agent=block_agent or global_agent, env=_merge_env({}, global_env, block_env))

    return AdditionalReviewConfig(
        agent=block_agent or global_agent or additional.agent,
        env=_merge_env(additional.env, global_env, block_env),
        patience=additional.patience,
        max_iterations=additional.max_iterations,
    )


def _merge_review(
    review: ReviewConfig | None,
    block: WorkflowBuild | None,
    global_agent: str | None,
    global_env: dict[str, str] | None,
) -> ReviewConfig | None:
    """Layer the review-pass sources onto the config review part.

    Args:
        review: The config ``build.review`` part, or ``None``.
        block: The workflow build block, or ``None`` when the workflow
            carries no block.
        global_agent: The workflow's global agent, or ``None``.
        global_env: The workflow's global env map, or ``None``.

    Returns:
        A new :class:`ReviewConfig` — agents resolving build-block >
        global > configuration per pass, env maps key-wise
        (configuration < global < block; the global env is the only
        cross-pass base), every other field verbatim. A ``None`` config
        review stays ``None`` unless a review-sourced value is set at any
        layer; it is then constructed from the layered set fields only, so
        the settings resolution receives a well-formed layered
        configuration.
    """
    block_agent = block.review_agent if block is not None else None
    block_env = block.review_env if block is not None else None

    if review is None:
        block_additional_agent = block.review_additional_agent if block is not None else None
        block_additional_env = block.review_additional_env if block is not None else None
        review_fields_set = any(
            field is not None
            for field in (
                block_agent,
                block_env,
                block_additional_agent,
                block_additional_env,
                global_agent,
                global_env,
            )
        )

        if not review_fields_set:
            return None

        return ReviewConfig(
            agent=block_agent or global_agent,
            env=_merge_env({}, global_env, block_env),
            additional=_merge_additional(None, block, global_agent, global_env),
        )

    return ReviewConfig(
        skip=review.skip,
        agent=block_agent or global_agent or review.agent,
        env=_merge_env(review.env, global_env, block_env),
        roles=review.roles,
        base_ref=review.base_ref,
        strategy=review.strategy,
        finalize=review.finalize,
        additional=_merge_additional(review.additional, block, global_agent, global_env),
        session_timeout=review.session_timeout,
        idle_timeout=review.idle_timeout,
        wait=review.wait,
        max_iterations=review.max_iterations,
    )


def merge_workflow_build(
    config: BuildConfig,
    build_block: WorkflowBuild | None,
    global_agent: str | None = None,
    global_env: dict[str, str] | None = None,
) -> BuildConfig:
    """Overlay the workflow layers onto the effective build configuration.

    The two global run settings are the middle layer and the six-field
    build block sits above them, composing the law
    ``config < workflow global < workflow build:`` that the CLI flags
    later top at the settings resolution.

    Args:
        config: The effective build configuration — the base layer; always a
            non-``None`` :class:`BuildConfig` (the no-build-section guard
            lives in the caller).
        build_block: The workflow build block model, or ``None`` when the
            workflow carries no block (the globals still layer).
        global_agent: The workflow's global agent, or ``None``.
        global_env: The workflow's global env map, or ``None``.

    Returns:
        A new layered :class:`BuildConfig` — each pass agent resolving
        build-block > global > configuration (a truthiness cascade: an
        authored empty-string block agent falls through, exactly as the
        block-only law), each pass env merging key-wise
        configuration < global < block, and every other field passing
        through verbatim. An absent value at every layer never overrides.
        The inputs are never mutated; the nested models are new.
    """
    block_agent = build_block.agent if build_block is not None else None
    block_env = build_block.env if build_block is not None else None

    return BuildConfig(
        agent=block_agent or global_agent or config.agent,
        env=_merge_env(config.env, global_env, block_env),
        max_iterations=config.max_iterations,
        session_timeout=config.session_timeout,
        idle_timeout=config.idle_timeout,
        wait=config.wait,
        prompts_dir=config.prompts_dir,
        agents_dir=config.agents_dir,
        proxy=config.proxy,
        hosts=config.hosts,
        review=_merge_review(config.review, build_block, global_agent, global_env),
    )
