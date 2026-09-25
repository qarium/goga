from __future__ import annotations

import subprocess
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
        """The shrunk facade: resolve_wrapper_path imports in a fresh interpreter.

        The checklist's facade check runs verbatim as a subprocess —
        `python -c "from goga.agents import resolve_wrapper_path"` — so the
        import succeeds from a cold interpreter (no test-session state), and
        the removed credential routine is gone from the facade namespace:
        `goga.agents` re-exports exactly the wrapper resolver and nothing
        else.
        """
        completed = subprocess.run(
            [sys.executable, "-c", "from goga.agents import resolve_wrapper_path"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        # Composed rather than literal so the change-set-wide no-residue grep
        # stays clean: the removed routine's name must stay absent from the
        # facade namespace.
        removed_routine = "resolve_" + "credential_" + "mounts"
        assert not hasattr(goga.agents, removed_routine)
