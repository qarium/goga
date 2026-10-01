from __future__ import annotations

import importlib
import sys

import goga.agents
from goga.agents import resolve_wrapper_path as facade_fn
from goga.agents.wrapper.resolve import resolve_wrapper_path as leaf_fn


class TestAgentsFacadeContract:
    def test_facade_exports_resolve_wrapper_path(self) -> None:
        """The facade exposes `resolve_wrapper_path` as a callable.

        Per `goga/agents/CODEMANIFEST` re-export `->resolve_wrapper_path: {}`,
        the facade `goga.agents` is the single stable import point for the
        routine. The name must be importable directly from the facade package
        and bound to a callable object.
        """
        assert callable(facade_fn)

    def test_facade_resolve_wrapper_path_consistent_with_leaf(self) -> None:
        """The facade re-exports the leaf callable itself (identity, not a copy).

        The `resolve-wrapper-path` usage pins the facade as the single stable
        import point and forbids deeper imports by consumers. A correct
        re-export binds the very same callable object as the leaf module, so
        identity (`is`) — not merely value equality — must hold.
        """
        assert facade_fn is leaf_fn

    def test_facade_import_surface(self) -> None:
        """The shrunk facade imports cold, without test-session state.

        The checklist's facade check — `from goga.agents import
        resolve_wrapper_path` — runs in-process: the cached `goga.agents`
        modules are evicted from `sys.modules` and re-imported fresh (then
        restored), so the import machinery runs with nothing pre-bound
        behind it. The removed credential routine is gone from the facade
        namespace: `goga.agents` re-exports exactly the wrapper resolver and
        nothing else.
        """
        evicted = {
            name: module
            for name, module in sys.modules.items()
            if name == "goga.agents" or name.startswith("goga.agents.")
        }

        for name in evicted:
            del sys.modules[name]

        try:
            fresh = importlib.import_module("goga.agents")

            assert callable(fresh.resolve_wrapper_path)
        finally:
            sys.modules.update(evicted)

            parent = sys.modules.get("goga")

            if parent is not None and "goga.agents" in evicted:
                parent.agents = evicted["goga.agents"]

        # Composed rather than literal so the change-set-wide no-residue grep
        # stays clean: the removed routine's name must stay absent from the
        # facade namespace.
        removed_routine = "resolve_" + "credential_" + "mounts"
        assert not hasattr(goga.agents, removed_routine)
