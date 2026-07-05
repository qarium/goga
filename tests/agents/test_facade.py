from __future__ import annotations

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
