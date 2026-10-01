from __future__ import annotations

from .run_settings import RunSettings

# Resolved knob keys composed per stage. Both stages carry their own
# max_iterations — the tasks value resolves from the root/CLI, the review
# value from build.review.max_iterations (never the root, never the CLI).
# The additional block's counter stays a separate surface composed as
# max_external_iterations.
_TASKS_KNOB_KEYS: tuple[str, ...] = ("session_timeout", "idle_timeout", "wait", "max_iterations")
_REVIEW_KNOB_KEYS: tuple[str, ...] = ("session_timeout", "idle_timeout", "wait", "max_iterations")


def compose_pass_options(settings: RunSettings, stage: str) -> dict[str, str | int | bool]:
    """Compose the ralphex options of one pass from the resolved run settings.

    Pure mapping — no side effects, no reads beyond ``settings``: the
    resolution precedence (CLI > config > default > omit) and the root
    inheritance were applied by ``resolve_run_settings``, so every knob read
    here is final and an unset one (None) stays absent from the dict — the
    assembled ralphex command carries no flag for it. The agent never appears
    in the composition (it reaches the pass as the executor wrapper) and the
    env never appears either (it reaches the pass as the subprocess env
    layer — secret-safe, values never travel through options).

    The tasks stage emits the ``tasks_only`` mode flag plus the resolved
    tasks knobs. The review stage emits exactly one mode flag bound to the
    strategy — ``review``, or ``external_only`` under short — plus the
    resolved review session knobs and the review-sourced ``max_iterations``,
    ``base_ref``, and the external-review counters of the additional block,
    whose 0 values are meaningful (patience disabled / ralphex auto) and
    pass verbatim.

    Args:
        settings: The resolved run plan of the build.
        stage: The pass stage — exactly ``tasks`` or ``review``.

    Returns:
        The ralphex options of the pass, consumed by ``run_build_pass``;
        carries exactly one pass-mode flag.

    Raises:
        ValueError: When ``stage`` is neither ``tasks`` nor ``review``.
    """
    if stage == "tasks":
        return _compose_tasks(settings)

    if stage == "review":
        return _compose_review(settings)

    raise ValueError(f"unknown build pass stage: {stage}")


def _compose_tasks(settings: RunSettings) -> dict[str, str | int | bool]:
    """Compose the tasks-pass options: the mode flag plus the resolved tasks knobs."""
    options: dict[str, str | int | bool] = {"tasks_only": True}

    for key in _TASKS_KNOB_KEYS:
        value = getattr(settings.tasks, key)

        if value is not None:
            options[key] = value

    return options


def _compose_review(settings: RunSettings) -> dict[str, str | int | bool]:
    """Compose the review-pass options: the strategy-bound mode flag plus the review surface."""
    review = settings.review
    mode_flag = "external_only" if review.strategy == "short" else "review"
    options: dict[str, str | int | bool] = {mode_flag: True}

    for key in _REVIEW_KNOB_KEYS:
        value = getattr(review, key)

        if value is not None:
            options[key] = value

    if review.base_ref is not None:
        options["base_ref"] = review.base_ref

    # The two external-review counters keep 0 verbatim — patience 0 means
    # disabled and max_iterations 0 means ralphex auto; only None is unset.
    if review.additional.patience is not None:
        options["review_patience"] = review.additional.patience

    if review.additional.max_iterations is not None:
        options["max_external_iterations"] = review.additional.max_iterations

    return options
