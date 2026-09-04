"""The run registry of the hooks platform.

The entities declared in the cell CODEMANIFEST with ``location: state.py``:
the run registry ``HookRegistry``, the isolated runtime context
``ToolContext``, and the per-tool inspection entry ``ToolHooks``. The registry
is the state of one run: it assembles itself once — on the first
``build_once`` call — by walking the installed tool packages through the
tool-package access of the platform, and it offers the read side of what was
assembled. Pure state and read logic: the packages are reached through the
tools cell, the delivery belongs to the dispatch zone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..tools import (
    HookRegistrar,
    RejectedRegistration,
    Subscription,
    call_register_hooks,
    enumerate_tool_packages,
)

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class HookRegistry:
    """The run registry — the assembled state of one run, built on first use.

    Created empty and cheap: no package is enumerated and no module imported
    at construction. The single build happens on the first ``build_once``
    call and never repeats on the same object — every run works over a fresh
    registry, nothing is cached across runs.
    """

    _built: bool = field(init=False, default=False, repr=False)
    _subscriptions: list[Subscription] = field(init=False, default_factory=list, repr=False)
    _rejections: list[RejectedRegistration] = field(init=False, default_factory=list, repr=False)
    _contexts: dict[str, ToolContext] = field(init=False, default_factory=dict, repr=False)

    @property
    def subscriptions(self) -> list[Subscription]:
        """Every accepted subscription, in enumeration order — a read copy."""
        return list(self._subscriptions)

    @property
    def rejections(self) -> list[RejectedRegistration]:
        """Every refused envelope, in enumeration order — a read copy."""
        return list(self._rejections)

    def build_once(self) -> None:
        """Assemble the registry of the run — the single build.

        Algorithm:
            1. An already assembled registry does nothing — the flag is set
               before the enumeration, so a nested or repeated build never
               reads the environment twice
            2. Enumerate the installed tool packages via
               ``enumerate_tool_packages``
            3. For each package in order: create a ``HookRegistrar`` scoped
               to the package identity and run its callback via
               ``call_register_hooks``
            4. An exception of a callback ends that callback's registration
               only: a warning in the log naming the tool and the reason, the
               registrations made before the failure survive, the next
               package is processed
            5. A broken package import — the platform-wrapped ``ImportError``
               naming the package — is the single fatal case and leaves the
               build as a clean error
            6. The accepted subscriptions and the refused envelopes of every
               registrar, also of a crashed one, join this registry in
               enumeration order

        Requirements:
            One tool's failure never cancels another tool's registrations.

        Raises:
            ImportError: A tool package exists but its facade fails to
                import — the message names the package.
        """
        if self._built:
            return

        self._built = True

        for package in enumerate_tool_packages():
            registrar = HookRegistrar(tool=package.tool)

            try:
                call_register_hooks(package, registrar)

            except ImportError as exc:
                # The import wrapper of the platform names the broken package;
                # an ImportError raised by the tool callback itself is a crash
                # like any other and is told apart by that message prefix.
                if str(exc).startswith(f"package {package.facade} failed to import:"):
                    raise

                logger.warning("skipping hook registration of tool %s: %s", package.tool, exc)

            except Exception as exc:
                logger.warning("skipping hook registration of tool %s: %s", package.tool, exc)

            self._subscriptions.extend(registrar.subscriptions)
            self._rejections.extend(registrar.rejections)

    def subscriptions_for(self, domain: str, action: str) -> list[Subscription]:
        """Return the subscriptions of one action address.

        Args:
            domain: The owner domain of the action.
            action: The action name within the domain.

        Returns:
            The subscriptions of the address, in enumeration order — an
            empty list when the address carries none, never an error.
        """
        return [
            subscription
            for subscription in self._subscriptions
            if subscription.domain == domain and subscription.action == action
        ]

    def self_context(self, tool: str) -> ToolContext:
        """Return the isolated runtime context of one tool.

        Args:
            tool: The tool identity of the owner.

        Returns:
            The tool's own context — one instance per tool per run, so the
            invocations of its hooks share their state.
        """
        if tool not in self._contexts:
            self._contexts[tool] = ToolContext(tool=tool)

        return self._contexts[tool]

    def by_tool(self) -> list[ToolHooks]:
        """Return the per-tool inspection view of the registry.

        Returns:
            One entry per tool with a subscription or a refusal, ordered
            alphabetically by tool. The view states the fact of registration,
            never the application.
        """
        tools = sorted(
            {subscription.tool for subscription in self._subscriptions}
            | {rejection.tool for rejection in self._rejections}
        )

        return [
            ToolHooks(
                tool=tool,
                subscriptions=[subscription for subscription in self._subscriptions if subscription.tool == tool],
                rejections=[rejection for rejection in self._rejections if rejection.tool == tool],
            )
            for tool in tools
        ]


@dataclass(kw_only=True)
class ToolContext:
    """The isolated runtime context of one tool — its own state within a run.

    The only state a hook may write without restriction, unlike a delivered
    domain context: a tool links the invocations of its hooks here and stays
    invisible to the domains.

    Attributes:
        tool: The environment-assigned tool identity of the owner.
    """

    tool: str


@dataclass(frozen=True, kw_only=True)
class ToolHooks:
    """The per-tool inspection entry — one tool with its registrations.

    Attributes:
        tool: The tool identity of the entry.
        subscriptions: The tool's accepted subscriptions.
        rejections: The tool's refused envelopes.
    """

    tool: str
    subscriptions: list[Subscription]
    rejections: list[RejectedRegistration]
