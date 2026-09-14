"""The mediator of the tool participation of the session.

The entity declared in the cell CODEMANIFEST with ``location: participation.py``:
the mediator ``ToolParticipation`` of both onboarding action moments — the
session declaration and the config amendment — delivered per tool with staged
control. A failure of one tool never cancels another tool or the session;
every warning names the tool, the action, and the reason.
"""

from __future__ import annotations

import logging

from ...hooks import HookRegistry, build_hook_arguments, enumerate_tool_packages, wrap_context
from ..questions import SessionAnswers
from .contribution import ToolContribution
from .declaration import ToolDeclaration

logger = logging.getLogger(__name__)


class ToolParticipation:
    """The mediator of both onboarding action moments of one session.

    Owns the invitation set and the run registry — built once on the first
    moment and shared by both — and drives the per-tool delivery of the two
    actions over the public primitives of the hooks platform. Delivery is
    never filtered by invitation: the marker travels to the hook inside the
    delivered surface, and a subscribed tool without an invitation receives
    the not-invited marker and decides on its own.

    Requirements:
        - Every warning names the tool, the action, and the reason
        - An invited tool without a subscription to an action participates
          silently — no block, no warning
        - The buffered contribution of a tool applies only after every hook
          of the tool of the moment completed without failure
    """

    def __init__(self, invited: list[str]) -> None:
        """Create the mediator of one session.

        Args:
            invited: The invited tool identities — defensively deduplicated
                here, preserving the flag order.
        """
        self._invited = list(dict.fromkeys(invited))
        self._registry: HookRegistry | None = None

    @property
    def invited(self) -> list[str]:
        """The invited tool identities, deduplicated, in flag order — a read copy."""
        return list(self._invited)

    def _ensure_registry(self) -> HookRegistry:
        """Build the run registry once — the shared state of both moments.

        Returns:
            The assembled registry of the run — built on the first call and
            reused by both moments; never rebuilt on the same mediator.

        Raises:
            ImportError: A tool package exists but its facade fails to import
                — the single fatal case; the message names the package.
        """
        if self._registry is None:
            registry = HookRegistry()
            registry.build_once()
            self._registry = registry

        return self._registry

    def _warn_for_uninstalled_invited(self) -> None:
        """Warn for every invited identity that is not an installed tool package.

        The session continues without the tool's block — the warning names the
        identity and moves on. A subscribed tool without an invitation is a
        different, silent condition handled by the invitation marker.
        """
        installed = {package.tool for package in enumerate_tool_packages()}

        for name in self._invited:
            if name not in installed:
                logger.warning("invited tool %s is not installed; continuing without its block", name)

    def _subscriptions_by_tool(self, registry: HookRegistry, action: str) -> dict[str, list]:
        """Group the subscriptions of one onboarding action per tool.

        Args:
            registry: The assembled run registry.
            action: The onboarding action name — ``declare_session`` or
                ``amend_config``.

        Returns:
            The subscriptions of the address grouped by tool identity, the
            keys in enumeration order.
        """
        groups: dict[str, list] = {}

        for subscription in registry.subscriptions_for("onboarding", action):
            groups.setdefault(subscription.tool, []).append(subscription)

        return groups

    def _call_hooks_of(
        self,
        registry: HookRegistry,
        tool: str,
        subscriptions: list,
        surface: ToolDeclaration | ToolContribution,
        action: str,
    ) -> bool:
        """Deliver one onboarding action to every hook of one tool.

        Args:
            registry: The assembled run registry.
            tool: The tool identity of the receiving tool.
            subscriptions: The tool's subscriptions of the action, in
                enumeration order.
            surface: The tool's delivered surface — the buffer its hooks
                write through the delivery view.
            action: The onboarding action name, for the diagnostics.

        Returns:
            True when every hook of the tool completed — the surface carries
            the buffered contribution; False when a hook failed — the tool's
            whole contribution is discarded and the delivery continues with
            the next tool.
        """
        proxy = wrap_context(surface)

        try:
            for subscription in subscriptions:
                subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
        except Exception as reason:
            logger.warning("tool %s dropped from onboarding.%s: %s", tool, action, reason)
            return False

        return True

    def collect_declarations(self) -> list[ToolDeclaration]:
        """Deliver the moment one — the session declaration action.

        Algorithm:
            1. Build the run registry once for the whole session — a broken
               package import is a clean error naming the package, the single
               fatal case
            2. Warn for every invited identity that is not among the
               installed tool packages, naming it; the session continues
               without its block
            3. Deliver the declaration action to every subscriber per tool,
               in enumeration order: an invited tool receives an active
               surface, a subscribed tool without an invitation receives the
               not-invited marker and stays silent
            4. A failing hook of a tool drops that tool's whole declaration —
               a warning, the session continues; the other tools stand
            5. Return the declarations of the surviving invited tools — the
               blocks of the session plan; a delivered marker surface is not
               a block

        Returns:
            The declarations of the surviving invited tools, in enumeration
            order.
        """
        registry = self._ensure_registry()
        self._warn_for_uninstalled_invited()

        declarations: list[ToolDeclaration] = []

        for tool, subscriptions in self._subscriptions_by_tool(registry, "declare_session").items():
            surface = ToolDeclaration(tool=tool, invited=tool in self._invited)

            if not self._call_hooks_of(registry, tool, subscriptions, surface, "declare_session"):
                continue  # a failing hook dropped the tool's whole declaration

            if not surface.invited:
                continue  # delivered the marker — no block of the session plan

            declarations.append(surface)

        return declarations

    def collect_contributions(self, answers: SessionAnswers) -> list[ToolContribution]:
        """Deliver the moment two — the config amendment action — and commit.

        Algorithm:
            1. Deliver the amendment action to every subscriber per tool, in
               enumeration order, each tool with its isolated answer view
            2. A failing hook of a tool discards its whole contribution — the
               amendments and the files together — with a warning; the
               session continues; the other tools stand
            3. Commit every surviving contribution: apply its buffered
               amendments to ``answers`` in delivery order; collect its
               buffered files
            4. Return the committed contributions

        Args:
            answers: The session answer space after the survey.

        Returns:
            The committed contributions, in enumeration order — the file
            buffers are handed to the artifact generation.
        """

        def surface_for(tool: str) -> ToolContribution:
            return ToolContribution(tool=tool, invited=tool in self._invited, answers=answers.view_for(tool))

        registry = self._ensure_registry()

        contributions: list[ToolContribution] = []

        for tool, subscriptions in self._subscriptions_by_tool(registry, "amend_config").items():
            surface = surface_for(tool)

            if self._call_hooks_of(registry, tool, subscriptions, surface, "amend_config"):
                contributions.append(surface)

        for contribution in contributions:
            for path, value in contribution.amendments:
                answers.amend(path, value)

        return contributions
