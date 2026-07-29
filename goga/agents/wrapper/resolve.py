from __future__ import annotations


def resolve_wrapper_path(agent: str) -> str:
    """Resolve an agent name into its in-container wrapper script path.

    The wrapper path is built per the `agent-wrappers` practice: the
    in-container wrappers directory `/home/goga/bin/` combined with the
    `<agent>-as-claude.sh` filename. The routine is pure string-building —
    the `agent` value is forwarded verbatim with no validation, normalization,
    or filesystem access.

    Args:
        agent: Agent name as declared in the consumer's configuration (e.g.
            "claude", "codex", "cursor", "opencode"). Forwarded as-is.

    Returns:
        The absolute in-container path of the wrapper script, e.g.
        "/home/goga/bin/codex-as-claude.sh".
    """
    filename = agent + "-as-claude.sh"
    return "/home/goga/bin/" + filename
