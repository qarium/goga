"""Facade contract lock of the ``goga.usages.status`` package.

The cell's CODEMANIFEST declares the status operation surface: the
report model records, the entry routine ``status``, and the two
comparison routines the report is computed from — ``compute_dep_status``
and ``hash_tree``.

The ``goga.usages`` facade re-exports the ``status`` routine, shadowing
the submodule attribute, so the package is resolved through
``importlib.import_module``.
"""

from __future__ import annotations

import importlib

CONTRACT_FACADE_NAMES = [
    "DepStatus",
    "EntryChange",
    "EntryKind",
    "EntryStatus",
    "UsageState",
    "UsageStatusReport",
    "compute_dep_status",
    "hash_tree",
    "status",
]


def _status_package():
    """Return the goga.usages.status package despite the facade shadowing.

    Returns:
        The goga.usages.status module object.
    """
    return importlib.import_module("goga.usages.status")


class TestUsagesStatusFacade:
    def test_facade_all_is_exact_contract_set(self) -> None:
        """__all__ carries exactly the CODEMANIFEST-declared names."""
        assert _status_package().__all__ == CONTRACT_FACADE_NAMES

    def test_facade_all_is_alphabetical(self) -> None:
        """__all__ keeps the alphabetical ordering convention (uppercase first)."""
        package = _status_package()

        assert package.__all__ == sorted(package.__all__)

    def test_every_name_resolves_on_the_package(self) -> None:
        """Every facade name is defined on the package."""
        package = _status_package()

        for name in CONTRACT_FACADE_NAMES:
            assert hasattr(package, name), f"{name} is not defined on goga.usages.status"

    def test_comparison_routines_are_callable(self) -> None:
        """The two comparison routines export callables."""
        package = _status_package()

        assert callable(package.compute_dep_status)
        assert callable(package.hash_tree)
