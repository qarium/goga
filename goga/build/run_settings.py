from __future__ import annotations

from dataclasses import dataclass, field

from ..config import AdditionalReviewConfig, BuildConfig, ReviewConfig


@dataclass(kw_only=True, frozen=True)
class PassSettings:
    """The resolved tasks-pass part of the run plan.

    Args:
        agent: The tasks-pass executor agent name, None when unset.
        env: The tasks-pass env layer, verbatim; the review pass never
            receives it.
        max_iterations: The tasks-pass iteration cap; None when unset.
        session_timeout: The tasks-pass session timeout; None when unset.
        idle_timeout: The tasks-pass idle timeout; None when unset.
        wait: The tasks-pass rate-limit wait; None when unset.
    """

    agent: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    max_iterations: int | None = None
    session_timeout: str | None = None
    idle_timeout: str | None = None
    wait: str | None = None


@dataclass(kw_only=True, frozen=True)
class ReviewPassSettings(PassSettings):
    """The resolved review-pass part — a concretization of ``PassSettings``; its env never inherits the root env.

    Args:
        roles: The declared reviewer composition, verbatim; None or an empty
            list mean the full default set to the consumer.
        base_ref: The resolved review diff base; None when unset.
        strategy: The resolved review strategy — full, medium, or short.
        finalize: The finalize prompt; None leaves the step at the ralphex
            default (off).
        additional: The resolved external-review block; its agent field
            carries the inherited review agent when unset in config.
        max_iterations: The review-pass iteration cap, resolved from
            ``build.review.max_iterations`` verbatim; None when unset — the
            root value and the CLI flag never reach it.
    """

    roles: list[str] | None = None
    base_ref: str | None = None
    strategy: str
    finalize: str | None = None
    additional: AdditionalReviewConfig


@dataclass(kw_only=True, frozen=True)
class RunSettings:
    """The resolved run plan of a single build — an immutable value object.

    Args:
        skip: The final skip decision (False when no source set it).
        tasks: The resolved tasks-pass part.
        review: The resolved review-pass part with root inheritance applied —
            always present, even on a skipped run.
    """

    skip: bool = False
    tasks: PassSettings = field(default_factory=PassSettings)
    review: ReviewPassSettings


def resolve_run_settings(config: BuildConfig, cli_options: dict) -> RunSettings:
    """Resolve the run settings of one build from the two-part configuration and the CLI options — a pure function.

    Args:
        config: Build configuration in the two-part form; a None review part
            resolves as fully unset with the root values inherited.
        cli_options: In-container CLI options; the keys read here are
            ``skip_review`` (bool | None), ``base_ref`` (str | None), and
            ``review_patience``, ``session_timeout``, ``idle_timeout``,
            ``wait``, ``max_iterations`` (each None when the flag was not
            given).

    Returns:
        The resolved run plan: the skip decision, the tasks part, and the
        review part with root inheritance applied — every knob resolves with
        the precedence CLI > config > default > omit, and unset knobs stay
        None so the key stays absent from the ralphex options.
    """
    review = config.review

    tasks = PassSettings(
        agent=config.agent,
        env=config.env,
        max_iterations=_cli_or_value(cli_options, "max_iterations", config.max_iterations),
        session_timeout=_cli_or_value(cli_options, "session_timeout", config.session_timeout),
        idle_timeout=_cli_or_value(cli_options, "idle_timeout", config.idle_timeout),
        wait=_cli_or_value(cli_options, "wait", config.wait),
    )

    review_agent = _review_value(review, "agent") or config.agent

    return RunSettings(
        skip=_resolve_skip(cli_options, review),
        tasks=tasks,
        review=ReviewPassSettings(
            agent=review_agent,
            env=review.env if review is not None else {},
            session_timeout=_resolve_review_knob(cli_options, "session_timeout", review, config),
            idle_timeout=_resolve_review_knob(cli_options, "idle_timeout", review, config),
            wait=_resolve_review_knob(cli_options, "wait", review, config),
            max_iterations=_review_value(review, "max_iterations"),
            roles=_review_value(review, "roles"),
            base_ref=_resolve_base_ref(cli_options, review),
            strategy=_review_value(review, "strategy") or "medium",
            finalize=_review_value(review, "finalize"),
            additional=_resolve_additional(cli_options, review, review_agent),
        ),
    )


def _resolve_skip(cli_options: dict, review: ReviewConfig | None) -> bool:
    """Tri-state skip resolution: CLI, else config, else False.

    Args:
        cli_options: In-container CLI options; ``skip_review`` is read.
        review: Review configuration part, or None when absent.

    Returns:
        The final skip decision — False when no source set it.
    """
    cli_skip = cli_options.get("skip_review")

    if cli_skip is not None:
        return cli_skip

    config_skip = _review_value(review, "skip")

    return config_skip if config_skip is not None else False


def _resolve_review_knob(
    cli_options: dict,
    key: str,
    review: ReviewConfig | None,
    config: BuildConfig,
) -> str | None:
    """Session-knob resolution for the review part: CLI, else review, else root.

    Args:
        cli_options: In-container CLI options; ``key`` is read from them.
        key: Knob field name resolved on the review part.
        review: Review configuration part, or None when absent.
        config: Root build configuration — the fallback source.

    Returns:
        The resolved knob value, or None when unset at every level.
    """
    cli_value = cli_options.get(key)

    if cli_value is not None:
        return cli_value

    review_value = _review_value(review, key)

    return review_value if review_value is not None else getattr(config, key)


def _resolve_additional(
    cli_options: dict,
    review: ReviewConfig | None,
    review_agent: str | None,
) -> AdditionalReviewConfig:
    """Additional-block resolution: agent inherits the review agent, patience is CLI > config.

    Args:
        cli_options: In-container CLI options; ``review_patience`` is read.
        review: Review configuration part, or None when absent.
        review_agent: The resolved review agent — the fallback agent.

    Returns:
        The resolved external-review block — its agent carries the review
        agent when unset in config.
    """
    block = review.additional if review is not None else None

    cli_patience = cli_options.get("review_patience")

    if cli_patience is None and block is not None:
        cli_patience = block.patience

    return AdditionalReviewConfig(
        agent=(block.agent if block is not None else None) or review_agent,
        patience=cli_patience,
        max_iterations=block.max_iterations if block is not None else None,
    )


def _resolve_base_ref(cli_options: dict, review: ReviewConfig | None) -> str | None:
    """Diff-base resolution: a non-empty stripped CLI value, else the config value.

    Args:
        cli_options: In-container CLI options; ``base_ref`` is read.
        review: Review configuration part, or None when absent.

    Returns:
        The stripped CLI value when non-empty, else the config value, else None.
    """
    cli_base_ref = cli_options.get("base_ref")

    if cli_base_ref is not None:
        stripped = cli_base_ref.strip()

        if stripped:
            return stripped

    return _review_value(review, "base_ref")


def _cli_or_value(cli_options: dict, key: str, value: str | int | None) -> str | int | None:
    """Root-level knob resolution for the tasks part: the CLI value when given, else the root value.

    Args:
        cli_options: In-container CLI options; ``key`` is read from them.
        key: Knob field name read from the CLI options.
        value: The root configuration value — the fallback.

    Returns:
        The CLI value when given, else ``value`` unchanged.
    """
    cli_value = cli_options.get(key)

    return cli_value if cli_value is not None else value


def _review_value(review: ReviewConfig | None, key: str):
    """The verbatim review-part value of ``key``; None when the part is absent.

    Args:
        review: Review configuration part, or None when absent.
        key: Field name read from the review part.
    """
    return getattr(review, key) if review is not None else None
