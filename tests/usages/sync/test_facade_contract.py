"""Facade contract lock of the ``goga.usages.sync`` package.

The cell's CODEMANIFEST declares the sync operation surface: the entry
routine ``sync`` and the three deployment steps it composes —
``clean_usages_dir``, ``clone_repository``, and ``deploy_usages``.

The ``goga.usages`` facade re-exports the ``sync`` routine, shadowing the
submodule attribute, so the package is resolved through
``importlib.import_module`` — the same pattern as the command zones.
"""

from __future__ import annotations

import importlib

CONTRACT_FACADE_NAMES = [
    "clean_usages_dir",
    "clone_repository",
    "deploy_usages",
    "sync",
]


def _sync_package():
    """Return the goga.usages.sync package despite the facade shadowing.

    Returns:
        The goga.usages.sync module object.
    """
    return importlib.import_module("goga.usages.sync")


class TestUsagesSyncFacade:
    def test_facade_all_is_exact_contract_set(self) -> None:
        """__all__ carries exactly the CODEMANIFEST-declared names."""
        assert _sync_package().__all__ == CONTRACT_FACADE_NAMES

    def test_facade_all_is_alphabetical(self) -> None:
        """__all__ keeps the alphabetical ordering convention."""
        package = _sync_package()

        assert package.__all__ == sorted(package.__all__)

    def test_every_name_resolves_on_the_package(self) -> None:
        """Every facade name is defined on the package."""
        package = _sync_package()

        for name in CONTRACT_FACADE_NAMES:
            assert hasattr(package, name), f"{name} is not defined on goga.usages.sync"

    def test_deployment_steps_are_callable(self) -> None:
        """The three deployment-step routines export callables."""
        package = _sync_package()

        assert callable(package.clean_usages_dir)
        assert callable(package.clone_repository)
        assert callable(package.deploy_usages)
