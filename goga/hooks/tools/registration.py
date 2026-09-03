"""The registration envelope of the hooks platform.

The entities declared in the cell CODEMANIFEST with ``location:
registration.py``: the registration surface ``HookRegistrar`` and the two
value records ``Subscription`` and ``RejectedRegistration``. This module is
the only way a subscription enters the platform — an address is resolved
against the catalog, the envelope is validated, and a refusal is recorded as
data with a stderr warning, never raised. The registrar never calls a hook
and never resolves a tool identity: the identity is assigned by the caller
that owns the package.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from ..catalog import declared_actions


@dataclass(kw_only=True)
class HookRegistrar:
    """The controlled registration surface handed to one tool.

    Scoped to one tool identity: every registration made through the surface
    is qualified by it. An invalid envelope is refused as data — the registrar
    never raises on one, and a refusal never cancels the accepted
    registrations of the same tool.

    Attributes:
        tool: The tool identity every registration made through this surface
            is qualified with — assigned by the caller, never resolved here.
    """

    tool: str
    _subscriptions: list[Subscription] = field(init=False, default_factory=list, repr=False)
    _rejections: list[RejectedRegistration] = field(init=False, default_factory=list, repr=False)

    @property
    def subscriptions(self) -> list[Subscription]:
        """The accepted subscriptions, in registration order — a read copy."""
        return list(self._subscriptions)

    @property
    def rejections(self) -> list[RejectedRegistration]:
        """The rejected envelopes, in attempted order — a read copy."""
        return list(self._rejections)

    def subscribe(self, domain: str, action: str, name: str, hook: Callable[..., object]) -> None:
        """Register one hook subscription — the registration envelope.

        Args:
            domain: The owner domain of the action.
            action: The action name within the domain.
            name: The hook name — unique per tool per address.
            hook: The callable executed when the action fires.

        Algorithm:
            1. Resolve ``domain`` and ``action`` against ``declared_actions``
               — an unknown address is rejected
            2. Validate the envelope — a non-empty ``name`` and a callable
               ``hook``; a violation is rejected
            3. Reject a repeated registration of the same ``name`` on the
               same address by this tool
            4. Every rejection is recorded and announced as a warning on
               stderr naming the tool, the action, and the reason
            5. An accepted envelope appends one subscription

        Requirements:
            A rejected envelope never cancels the accepted subscriptions of
            the same tool, and the registrar never raises on an invalid
            envelope — rejection is data, not an exception.

        Constraints:
            Do not call ``hook`` or inspect its signature — the delivery
            projection belongs to the delivery zone.

        A rejection carries the attempted name as an empty string when the
        envelope did not carry a usable one, so the inspection view states
        what was refused even for an ill-formed name.
        """

        def reject(reason: str) -> None:
            self._rejections.append(
                RejectedRegistration(
                    tool=self.tool,
                    domain=domain,
                    action=action,
                    name=name if isinstance(name, str) else "",
                    reason=reason,
                )
            )

            print(f"Warning: rejected hook of tool {self.tool} on {domain}.{action}: {reason}", file=sys.stderr)

        known = any(record.domain == domain and record.name == action for record in declared_actions())

        if not known:
            reject(f"unknown action {domain}.{action}")

            return

        if not (isinstance(name, str) and name):
            reject("name must be a non-empty string")

            return

        if not callable(hook):
            reject("hook must be callable")

            return

        repeated = any(
            subscription.domain == domain and subscription.action == action and subscription.name == name
            for subscription in self._subscriptions
        )

        if repeated:
            reject("repeated name on the same address")

            return

        self._subscriptions.append(Subscription(tool=self.tool, domain=domain, action=action, name=name, hook=hook))


@dataclass(frozen=True, kw_only=True)
class Subscription:
    """One accepted subscription — a hook bound to an address, qualified by a tool.

    The record carries no behavior: the delivery decides how the hook is
    called, the registry decides when.

    Attributes:
        tool: The tool identity that registered the subscription.
        domain: The owner domain of the subscribed action.
        action: The subscribed action name.
        name: The hook name within its tool.
        hook: The registered callable.

    Requirements:
        The identity of the record is the triple ``tool``, ``domain``,
        ``action`` with the ``name`` — the registrar enforces its uniqueness
        per tool per address before a subscription exists.
    """

    tool: str
    domain: str
    action: str
    name: str
    hook: Callable[..., object]


@dataclass(frozen=True, kw_only=True)
class RejectedRegistration:
    """One refused registration envelope with the reason of the refusal.

    The data behind the inspection view of refused registrations — it states
    what was attempted and why it did not apply, nothing more.

    Attributes:
        tool: The tool identity that attempted the registration.
        domain: The owner domain of the addressed action.
        action: The addressed action name.
        name: The attempted hook name — an empty string when the envelope did
            not carry a usable one.
        reason: The reason of the refusal.

    Requirements:
        The reason is one of the platform refusal strings, so the inspection
        view stays stable for the reader.
    """

    tool: str
    domain: str
    action: str
    name: str
    reason: str
