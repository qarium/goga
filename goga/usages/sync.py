"""Config-driven synchronization of cell-level usages.

Facade stub. The full orchestrator — config loading, clone/deploy/clean
orchestration, best-effort per-dep error handling, and incremental vs force
modes — is implemented in the orchestrator task. This module exposes the
``sync`` callable so the ``goga.usages`` facade is importable while the sibling
routines (``clean``, ``clone``, ``deploy``) are filled in.
"""


def sync(force: bool = False) -> int:  # noqa: ARG001
    """Synchronize declared cell-level usages into ``.goga/usages``.

    Stub returning the success exit code; the orchestrator task replaces this
    body with the full clone/deploy/clean loop described in the contract.

    Args:
        force: True re-syncs all declared deps; False (default) is incremental.

    Returns:
        exit_code: ``0`` on success, ``1`` if any declared dep failed.
    """
    return 0
