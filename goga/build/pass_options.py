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
    """Compose the ralphex options of one pass from the resolved run settings — pure mapping.

    Args:
        settings: The resolved run plan of the build.
        stage: The pass stage — exactly ``tasks`` or ``review``.

    Returns:
        The ralphex options of the pass, consumed by ``run_build_pass`` —
        exactly one pass-mode flag (``tasks_only``, or ``review`` /
        ``external_only`` under the short strategy); unset knobs (None) stay
        absent, and neither the agent nor env values ever appear.

    Raises:
        ValueError: When ``stage`` is neither ``tasks`` nor ``review``.
    """
    if stage == "tasks":
        return _compose_tasks(settings)

    if stage == "review":
        return _compose_review(settings)

    raise ValueError(f"unknown build pass stage: {stage}")


def _compose_tasks(settings: RunSettings) -> dict[str, str | int | bool]:
    """Compose the tasks-pass options: the mode flag plus the resolved tasks knobs.

    Args:
        settings: The resolved run plan of the build.

    Returns:
        The tasks-pass options — ``tasks_only`` True plus the set tasks knobs.
    """
    options: dict[str, str | int | bool] = {"tasks_only": True}

    for key in _TASKS_KNOB_KEYS:
        value = getattr(settings.tasks, key)

        if value is not None:
            options[key] = value

    return options


def _compose_review(settings: RunSettings) -> dict[str, str | int | bool]:
    """Compose the review-pass options: the strategy-bound mode flag plus the review surface.

    Args:
        settings: The resolved run plan of the build.

    Returns:
        The review-pass options — the strategy-bound mode flag plus the set
        review knobs, ``base_ref``, and the external-review counters.
    """
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
