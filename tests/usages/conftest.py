"""Shared fixtures of the usages suites — the hooks platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the status/sync
suites pin the same two outside-world points — the ``packages_distributions``
read and the ``sys.modules`` entry of a fake ``goga_tool_*`` package — with
the platform delivery under test running for real. The ``recorder`` fixture
composes the two into the all-addresses usages moment capture shared by every
moment suite, and ``_of`` projects that capture onto one address.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401


@pytest.fixture
def recorder(
    # The parameters shadow the re-exported fixture names on purpose — pytest
    # injects the two boundary fixtures by parameter name.
    pin_package_environment: Callable[[dict[str, list[str]]], object],  # noqa: F811
    install_tool_package: Callable[..., object],  # noqa: F811
) -> list[tuple[str, object]]:
    """Install the all-addresses usages moment recorder.

    The fake ``goga_tool_rec`` package imitates the consumer practice's
    subscribe sketch over the four ``usages`` addresses, appending every
    delivered context to a capture owned by the test — the shared capture of
    the sync, status, and cross-operation moment suites.

    Returns:
        The capture — ``(action, context)`` pairs, one per delivered
        context, in delivery order.
    """
    captured: list[tuple[str, object]] = []

    def _register(hooks: Any) -> None:
        def _recorder_of(action: str) -> Callable[[object], None]:
            def _record(context: object) -> None:
                captured.append((action, context))

            return _record

        for action in ("sync_started", "sync_completed", "status_started", "status_completed"):
            hooks.subscribe("usages", action, f"rec_{action}", _recorder_of(action))

    pin_package_environment({"goga_tool_rec": ["goga-tool-rec"]})
    install_tool_package("goga_tool_rec", register_hooks=_register)

    return captured


def _of(captured: list[tuple[str, object]], action: str) -> list[object]:
    """Project the moment capture onto one address's delivered contexts."""
    return [context for name, context in captured if name == action]
