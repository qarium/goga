"""The ``resolve_activation`` routine — folding the three activation channels."""

from __future__ import annotations


def resolve_activation(
    cli_profile: str | None,
    env_profile: str | None,
    workflow_default: str | None,
) -> str | None:
    """Resolve the effective profile name from the three activation sources, strongest first.

    Args:
        cli_profile: the ``--profile`` flag value, or None when the flag was
            not passed.
        env_profile: the ``GOGA_PROFILE`` value, or None when the variable is
            unset.
        workflow_default: the workflow's top-level ``profile:`` default, or
            None when the workflow-file carries none.

    Returns:
        The effective profile name — the first non-empty value among the three
        channels in CLI > environment > workflow-default order — or None when
        every source is unset. Empty and whitespace-only strings count as
        unset; a non-empty value is returned whitespace-trimmed.
    """
    for candidate in (cli_profile, env_profile, workflow_default):
        if candidate is None:
            continue

        stripped = candidate.strip()

        if stripped:
            return stripped

    return None
