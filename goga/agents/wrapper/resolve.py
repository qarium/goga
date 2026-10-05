from __future__ import annotations


def resolve_wrapper_path(agent: str) -> str:
    """Resolve an agent name into its in-container wrapper script path.

    Args:
        agent: Agent name as declared in the consumer's configuration
            (e.g. "claude", "codex"); forwarded verbatim with no validation.

    Returns:
        The absolute in-container wrapper path, e.g.
        "/home/goga/bin/codex-as-claude.sh", built by string concatenation
        with no filesystem access.
    """
    filename = agent + "-as-claude.sh"
    return "/home/goga/bin/" + filename
