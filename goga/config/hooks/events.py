"""The checkpoint surface of the config domain — the events cell of the zone."""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass, replace
from types import MappingProxyType
from typing import Any

from ...hooks import (
    HookRegistry,
    build_hook_arguments,
    declared_actions,
    wrap_context,
)
from ..project import ProjectConfig
from .amendments import ConfigAmendment
from .overlay import ConfigOverlay, ToolAmendment, merge_config_amendments


def _read_only_view(value: Any) -> Any:
    """Build the delivery snapshot of one configuration value — closed for writes.

    Args:
        value: a configuration node — a frozen model instance, a
            mapping, a list, or a scalar.

    Returns:
        The read-only snapshot of ``value`` — every mapping rebuilt as a ``MappingProxyType`` over frozen
        copies, every list as a fresh copy; reads, equality, and iteration are unchanged.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return replace(value, **{f.name: _read_only_view(getattr(value, f.name)) for f in dataclass_fields(value)})
    if isinstance(value, dict):
        return MappingProxyType({key: _read_only_view(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_read_only_view(item) for item in value]
    return value


class ConfigHooks:
    """The checkpoint surface of the config domain — a tool's contribution commits only after all its hooks succeed.

    Requirements:
        - Cheap construction — no enumeration and no imports happen at
          construction
        - One ``HookRegistry`` per run carries every checkpoint of a
          command — the assembly runs once per run whatever the number of
          checkpoints
        - Every context is built from the values the caller passes — no
          repository, git, or file reads happen at the checkpoint
    """

    def __init__(self) -> None:
        """Create the checkpoint surface of one command."""
        self._registry: HookRegistry | None = None

    def _ensure_registry(self) -> HookRegistry:
        """Build the run registry once — the shared state of every checkpoint.

        Returns:
            The assembled registry of the run — built on the first call and
            reused by every checkpoint; never rebuilt on the same surface.

        Raises:
            ImportError: A tool package exists but its facade fails to
                import — the single fatal case; the message names the
                package.
        """
        if self._registry is None:
            registry = HookRegistry()
            registry.build_once()
            self._registry = registry

        return self._registry

    def amend_config(self, config: ProjectConfig) -> ConfigOverlay:
        """Deliver the config-amendment checkpoint and return the overlay.

        Algorithm:
            1. Resolve the address ``config.amend_config`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``ConfigAmendment`` view
               over the delivered configuration — every tool reads its own
               fresh read-only snapshot of the same authored object, so no
               tool's in-place write reaches another tool's view — wrap it
               via ``wrap_context``, project the call arguments via
               ``build_hook_arguments`` with the tool's own context, and
               call each hook of the tool
            3. A tool whose every hook returned without raising and whose
               buffer carries at least one amendment commits as one
               ``ToolAmendment``; an empty buffer commits nothing, silently
            4. A tool with a raising hook is a hard failure: a clean error
               naming the hook, the tool, and the action stops the command
               at the first failure; the tool's whole contribution is
               discarded together with its view
            5. Merge the committed contributions onto ``config`` via
               ``merge_config_amendments`` — a structural failure raised
               there is the same hard failure, its message wrapped with the
               action; nothing applies
            6. Return the overlay — an address without subscriptions
               returns the passthrough overlay

        Args:
            config: The authored loaded project configuration — operation
                data handed over by the calling command.

        Returns:
            The :class:`~goga.config.hooks.ConfigOverlay` — the effective configuration and its applied
            amendments; the overlay's summary lines are data the caller acts on — the zone never prints.

        Raises:
            ValueError: The address is not declared, a hook of the hard
                action failed — the message names the hook, the tool, and
                the reason — or a committed contribution is structurally
                malformed — the message names the tool, the path, and the
                action.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "config" and entry.name == "amend_config"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: config.amend_config")

        groups: dict[str, list] = {}
        for subscription in registry.subscriptions_for("config", "amend_config"):
            groups.setdefault(subscription.tool, []).append(subscription)

        contributions: list[ToolAmendment] = []

        for tool, subscriptions in groups.items():
            # A fresh read-only snapshot per tool — value-identical reads
            # of the authored tree, every mapping/list closed for writes,
            # so no in-place mutation reaches the authored base, the
            # effective configuration, or another tool's view: a list
            # write stays local to the tool's own snapshot and dies with
            # it. The view dies with the tool when a hook fails, taking
            # the buffer with it.
            amendment = ConfigAmendment(config=_read_only_view(config))
            proxy = wrap_context(amendment)

            for subscription in subscriptions:
                try:
                    subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
                except Exception as reason:
                    # Hard: stop at the first failure. The message copies the
                    # pipeline-zone format — hook name, tool, address, reason.
                    raise ValueError(
                        f"hook {subscription.name} of tool {tool} failed on config.amend_config: {reason}"
                    ) from reason

            # The commit granularity is the tool: only after every hook of
            # the tool succeeded, and only when something was buffered — an
            # empty buffer commits nothing, silently.
            if amendment._amendments:
                contributions.append(
                    ToolAmendment(tool=tool, amendments=list(amendment._amendments.values())),
                )

        try:
            return merge_config_amendments(config, contributions)
        except ValueError as reason:
            # The merge's own message already names the tool and the path;
            # the wrapper adds the action — never a duplicate tool name.
            raise ValueError(f"amendment rejected on config.amend_config: {reason}") from reason
