"""Contract and logic tests for the cell declared in
``goga/hooks/CODEMANIFEST`` — the facade of the hooks platform.

The facade declares no type of its own: it re-exports the four embeddings
consumers address the platform through — ``declared_actions``,
``HookRegistry``, ``ToolHooks``, and ``emit_hook_event`` — each identical to
the object its subcell package owns. The facade import is cheap: reloading
the package reads no installed-distribution mapping and builds no registry.
"""

from __future__ import annotations

import importlib

import goga.hooks
from goga.hooks import catalog as catalog_source
from goga.hooks import dispatch as dispatch_source
from goga.hooks import registry as registry_source

_FACADE_ALL = ["HookRegistry", "ToolHooks", "declared_actions", "emit_hook_event"]


class TestHooksPlatformFacade:
    def test_all_lists_exactly_the_four_reexports(self) -> None:
        """The facade declares exactly the four embeddings, alphabetically."""
        assert goga.hooks.__all__ == _FACADE_ALL

    def test_declared_actions_is_the_catalog_object(self) -> None:
        """declared_actions is the catalog routine, not a copy of it."""
        assert goga.hooks.declared_actions is catalog_source.declared_actions

    def test_hook_registry_is_the_registry_object(self) -> None:
        """HookRegistry is the registry class, not a copy of it."""
        assert goga.hooks.HookRegistry is registry_source.HookRegistry

    def test_tool_hooks_is_the_registry_object(self) -> None:
        """ToolHooks is the registry record, not a copy of it."""
        assert goga.hooks.ToolHooks is registry_source.ToolHooks

    def test_emit_hook_event_is_the_dispatch_object(self) -> None:
        """emit_hook_event is the emission routine, not a copy of it."""
        assert goga.hooks.emit_hook_event is dispatch_source.emit_hook_event

    def test_every_declared_name_is_importable(self) -> None:
        """Each name of ``__all__`` resolves to a real attribute of the facade."""
        for name in goga.hooks.__all__:
            assert getattr(goga.hooks, name) is not None

    def test_importing_the_facade_enumerates_no_packages(self, pin_package_environment) -> None:
        """The facade import reads no installed-distribution mapping."""
        boundary = pin_package_environment({})

        importlib.reload(goga.hooks)

        boundary.assert_not_called()
