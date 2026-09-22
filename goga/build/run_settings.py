from __future__ import annotations

from dataclasses import dataclass, field

from ..config import AdditionalReviewConfig, BuildConfig, ReviewConfig


@dataclass(kw_only=True, frozen=True)
class PassSettings:
    """The resolved tasks-pass part of the run plan.

    ``agent``: the tasks-pass executor agent name, None when unset.

    ``env``: the tasks-pass env layer, verbatim; the review pass never
    receives it.

    ``max_iterations``: the tasks-pass iteration cap; None when unset.

    ``session_timeout``: the tasks-pass session timeout; None when unset.

    ``idle_timeout``: the tasks-pass idle timeout; None when unset.

    ``wait``: the tasks-pass rate-limit wait; None when unset.
    """

    agent: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    max_iterations: int | None = None
    session_timeout: str | None = None
    idle_timeout: str | None = None
    wait: str | None = None


@dataclass(kw_only=True, frozen=True)
class ReviewPassSettings(PassSettings):
    """The resolved review-pass part — a concretization of the base pass part.

    Carries the inherited agent and session-knob fields of ``PassSettings``,
    the verbatim review env layer (never inherited from the root env — the
    root env is the tasks-pass layer only), the review-sourced iteration cap,
    plus the review-only members.

    ``roles``: the declared reviewer composition, verbatim; None or an empty
    list mean the full default set to the consumer.

    ``base_ref``: the resolved review diff base; None when unset.

    ``strategy``: the resolved review strategy — full, medium, or short.

    ``finalize``: the finalize prompt; None leaves the step at the ralphex
    default (off).

    ``additional``: the resolved external-review block; its agent field
    carries the inherited review agent when unset in config.

    ``max_iterations``: the review-pass iteration cap, resolved from
    ``build.review.max_iterations`` verbatim; None when unset — the root
    value and the CLI flag never reach it.
    """

    roles: list[str] | None = None
    base_ref: str | None = None
    strategy: str
    finalize: str | None = None
    additional: AdditionalReviewConfig


@dataclass(kw_only=True, frozen=True)
class RunSettings:
    """The resolved run plan of a single build.

    Immutable value-object computed by ``resolve_run_settings`` — never loaded
    from YAML directly. ``skip`` is the final skip decision of the tri-state
    resolution (False when neither the CLI nor the config set it). ``tasks``
    is the resolved tasks-pass part. ``review`` is the resolved review-pass
    part with root inheritance applied — always present, so a skipped run
    still carries the resolved review facts.

    ``skip``: the final skip decision (False when no source set it).

    ``tasks``: the resolved tasks-pass part.

    ``review``: the resolved review-pass part with root inheritance applied.
    """

    skip: bool = False
    tasks: PassSettings = field(default_factory=PassSettings)
    review: ReviewPassSettings


def resolve_run_settings(config: BuildConfig, cli_options: dict) -> RunSettings:
    """Resolve the run settings of one build from the two-part configuration and the CLI options.

    Pure function — no side effects, no validation of values (the semantic
    checks belong to ``validate_review_config``), no wrapper resolution (that
    belongs to the orchestrator and the validation routine). Every knob
    resolves with the precedence CLI > config > default > omit; unset at both
    levels stays None, so the key stays absent from the ralphex options.

    An absent ``build.review`` (``config.review`` is None) treats every review
    field as unset: skip resolves False, the agent and session knobs inherit
    the root values, base_ref/roles/finalize stay None, and the additional
    part resolves with the inherited review agent and unset counters — the
    additional block is always constructed (``ReviewPassSettings.additional``
    is non-optional).

    The env dicts pass verbatim: the review env never inherits the root env
    (secret-safe — the root env is the tasks-pass layer); an empty review env
    means no review layer. Review ``max_iterations`` resolves from
    ``build.review.max_iterations`` alone — the review value verbatim, None
    when unset; neither the root ``build.max_iterations`` nor the CLI
    ``--max-iterations`` flag (both tasks-pass sources) ever reaches the
    review part. A non-None ``cli_options`` base_ref wins
    over the config value — padded values strip, an empty or whitespace-only
    CLI value counts as unset.

    Args:
        config: Build configuration in the two-part form; the review part may
            be None.
        cli_options: In-container CLI options; the keys read here are
            `skip_review` (bool | None), `base_ref` (str | None), and
            `review_patience`, `session_timeout`, `idle_timeout`, `wait`,
            `max_iterations` (each None when the flag was not given).

    Returns:
        The resolved run plan: the skip decision, the tasks part, and the
        review part with root inheritance applied.
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
    """Tri-state skip resolution: CLI, else config, else False."""
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
    """Session-knob resolution for the review part: CLI, else review, else root."""
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
    """Additional-block resolution: agent inherits the review agent, patience is CLI > config."""
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
    """Diff-base resolution: a non-empty stripped CLI value, else the config value."""
    cli_base_ref = cli_options.get("base_ref")

    if cli_base_ref is not None:
        stripped = cli_base_ref.strip()

        if stripped:
            return stripped

    return _review_value(review, "base_ref")


def _cli_or_value(cli_options: dict, key: str, value: str | int | None) -> str | int | None:
    """Root-level knob resolution for the tasks part: the CLI value when given, else the root value."""
    cli_value = cli_options.get(key)

    return cli_value if cli_value is not None else value


def _review_value(review: ReviewConfig | None, key: str):
    """The verbatim review-part value of ``key``; None when the part is absent."""
    return getattr(review, key) if review is not None else None
