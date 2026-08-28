"""Post-install hook routines for ``goga install``.

The three hook routines declared in the cell CODEMANIFEST with ``location:
hook.py``: the initiating-user resolver (the actual person behind a possibly
sudo-ed install), the single-tool hook invocation (a dynamic
``goga_tool_<tool>`` facade import with signature-projected ``user``
injection), and the sequential runner (one initiating user per run, stop at
the first failure). The hook is optional per tool: a missing facade module or
a missing ``install`` callable is a quiet skip — silent for the user and
visible in the debug log only.
"""

from __future__ import annotations

import getpass
import importlib
import inspect
import logging
import os

logger = logging.getLogger(__name__)

# The signature projection's opt-in set: only a ``user`` parameter declared
# POSITIONAL_OR_KEYWORD or KEYWORD_ONLY receives the value — ``**kwargs``
# alone is NOT an opt-in (the offered-name set is the single source).
_KEYWORD_CAPABLE_KINDS = frozenset({inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY})


def resolve_initiating_user() -> str:
    """Resolve the user who initiated the installation.

    The actual person, not the root account the installer may run under: a
    set and non-empty ``SUDO_USER`` environment variable wins (the
    installation runs under sudo and sudo recorded the caller); otherwise
    the operating-system user name of the current process is the canonical
    answer.

    Returns:
        The initiating user name.

    Raises:
        OSError: when the operating-system identity cannot be resolved — the
            failure propagates, no fallback name is invented.
        KeyError: when the user database has no entry for the current
            process — propagates for the same reason.
    """
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        return sudo_user
    return getpass.getuser()


def call_install_hook(tool: str, user: str) -> bool:
    """Run the post-install hook of one installed tool when it provides one.

    Imports the tool facade ``goga_tool_<tool>`` and calls its optional
    ``install`` callable. The identifier is normalized to a module name first —
    hyphens and dots become underscores and the result is lowercased, so the
    canonical hyphenated tool name (``hello-world``) imports
    ``goga_tool_hello_world``, the spelling pip lays out on disk (pip resolves
    distribution names case-insensitively, the import lookup does not). The
    injection follows the signature projection:
    only a declared keyword-capable ``user`` parameter receives the value — a
    positional-only ``user`` or a bare ``**kwargs`` is not an opt-in and the
    hook is called without arguments. No argument other than ``user`` is
    ever passed, and the hook runs unsandboxed, with the trust level of the
    installed package.

    Args:
        tool: Tool name without the ``goga_tool_`` prefix.
        user: Initiating user to inject when the hook asks for it.

    Returns:
        True when the hook ran; False when it was skipped (a missing facade
        module or a missing/non-callable ``install`` — a quiet skip).

    Raises:
        ModuleNotFoundError: when the facade exists but its own imports are
            broken — the missing module is a different one (``exc.name``
            differs), a failure rather than a skip.
        Exception: whatever the hook itself raises, propagated unchanged.
    """
    # The pip-style tool identifier is hyphenated (``hello-world``) while the
    # installed top-level module is underscored (``goga_tool_hello_world``) —
    # the same duality `goga connect` normalizes for pipeline namespacing.
    # pip resolves distribution names case-insensitively but the import lookup
    # is case-sensitive, so the identifier is lowercased too (the canonical
    # tool spelling is lowercase-hyphenated). Without this a case-variant or
    # multi-word identifier makes the facade import miss and the hook degrade
    # to the quiet-skip path.
    module_name = f"goga_tool_{tool.replace('-', '_').replace('.', '_').lower()}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return False
        raise

    install = getattr(module, "install", None)
    if install is None or not callable(install):
        return False

    user_parameter = inspect.signature(install).parameters.get("user")
    if user_parameter is not None and user_parameter.kind in _KEYWORD_CAPABLE_KINDS:
        install(user=user)
    else:
        install()
    return True


def run_install_hooks(tools: list[str]) -> None:
    """Run the post-install hook for every freshly installed tool.

    Resolves the initiating user exactly once — every hook of the run sees
    the same value — then invokes each tool's hook in installation order.
    A hook failure stops the loop: the exception is wrapped with the tool's
    name as context and the hooks of the remaining tools are not run. An
    empty list is a quiet no-op: no user resolution, no log lines. The agent
    re-sync never runs here; activation stays the command's own step.

    Args:
        tools: Names of the installed tools in installation order.

    Raises:
        RuntimeError: a hook raised — ``install hook for tool '<tool>'
            failed: <message>``, with the original exception as its cause.
        Exception: a failure of the user-resolution step propagates as-is —
            it is not a hook failure and carries no tool context.
    """
    if not tools:
        return

    user = resolve_initiating_user()
    for tool in tools:
        try:
            invoked = call_install_hook(tool, user)
        except Exception as exc:
            raise RuntimeError(f"install hook for tool {tool!r} failed: {exc}") from exc
        if invoked:
            logger.info("install hook invoked", extra={"tool": tool})
        else:
            logger.debug("install hook skipped", extra={"tool": tool})
