from __future__ import annotations

from pathlib import Path

# Fixed credential path table: (host_path_with_leading_tilde, container_path).
# The container paths mirror the host layout under /home/goga so the
# in-container CLI finds each credential file through its native lookup logic.
# The table is the single source of truth — adding or updating a credential
# path is a one-line change here.
_CREDENTIAL_PATH_TABLE: tuple[tuple[str, str], ...] = (
    ("~/.claude/.credentials.json", "/home/goga/.claude/.credentials.json"),
    ("~/.codex/auth.json", "/home/goga/.codex/auth.json"),
    ("~/.local/share/opencode/auth.json", "/home/goga/.local/share/opencode/auth.json"),
)


def resolve_credential_mounts() -> list[tuple[str, str]]:
    """Detect AI-agent credential files on the host and return host→container path pairs.

    Each row of the fixed credential path table is expanded (leading `~` to the
    current user's home) and checked for existence on the host filesystem. For
    every file that exists, a `(host_path, container_path)` pair is appended so
    the consumer can assemble a read-only bind-mount. Detection is
    host-filesystem-only (`Path.exists()`); no content is read, parsed, or
    validated.

    The routine takes no arguments: detection is agent-agnostic by design, so
    all three agents are checked unconditionally. Absent files are never an
    error — they simply contribute no tuple, and an empty list is returned when
    nothing exists. macOS Keychain caveat for claude: when web-login stores the
    token in the Keychain, `~/.claude/.credentials.json` is auto-deleted and no
    claude tuple is returned; the user must create the file manually (or supply
    `ANTHROPIC_API_KEY` via the consumer's `-e/--env` option) to enable claude
    credential-mounting on macOS.

    Returns:
        A list of `(host_path, container_path)` tuples for every credential
        file that exists on the host, in the table order (claude, codex,
        opencode). Empty when none exist. Never raises.
    """
    result: list[tuple[str, str]] = []
    for host_rel, container_path in _CREDENTIAL_PATH_TABLE:
        host_path = Path(host_rel).expanduser()
        if host_path.exists():
            result.append((str(host_path), container_path))
    return result
