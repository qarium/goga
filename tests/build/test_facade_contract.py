"""Facade contract lock of the ``goga.build`` package.

The cell's CODEMANIFEST declares the full contract surface — the entry
orchestration (``build``, ``main``), the workflow selection and build
merging, the two-part settings resolution (``RunSettings`` with its two
pass blocks and ``resolve_run_settings``), the pass ladder support
(``run_build_pass``, ``compose_pass_options``, ``validate_review_config``),
the ralphex config/runtime routines (``write_ralphex_config``,
``sync_ralphex_defaults``), the plan relocation, and the wrapper
materialization. Only identifiers listed in ``__all__`` constitute the
facade — per the language rule, every contract type is exported there.
"""

from __future__ import annotations

import inspect

import goga.build

CONTRACT_FACADE_NAMES = [
    "PassSettings",
    "ReviewPassSettings",
    "RunSettings",
    "build",
    "compose_pass_options",
    "main",
    "merge_workflow_build",
    "move_completed_plan",
    "resolve_build_workflow",
    "resolve_run_settings",
    "run_build_pass",
    "sync_ralphex_defaults",
    "validate_review_config",
    "write_ralphex_config",
    "write_role_env_wrappers",
]

ROUTINE_NAMES = [
    "build",
    "compose_pass_options",
    "main",
    "merge_workflow_build",
    "move_completed_plan",
    "resolve_build_workflow",
    "resolve_run_settings",
    "run_build_pass",
    "sync_ralphex_defaults",
    "validate_review_config",
    "write_ralphex_config",
    "write_role_env_wrappers",
]

ENTITY_NAMES = [
    "PassSettings",
    "ReviewPassSettings",
    "RunSettings",
]


class TestBuildFacade:
    def test_facade_all_is_exact_contract_set(self) -> None:
        """__all__ carries exactly the CODEMANIFEST-declared names."""
        assert goga.build.__all__ == CONTRACT_FACADE_NAMES

    def test_facade_all_is_alphabetical(self) -> None:
        """__all__ keeps the alphabetical ordering convention (uppercase first)."""
        assert goga.build.__all__ == sorted(goga.build.__all__)

    def test_every_name_resolves_on_the_package(self) -> None:
        """Every facade name is defined on the package."""
        for name in CONTRACT_FACADE_NAMES:
            assert hasattr(goga.build, name), f"{name} is not defined on goga.build"

    def test_routines_are_callable(self) -> None:
        """Every declared routine exports a callable."""
        for name in ROUTINE_NAMES:
            assert callable(getattr(goga.build, name)), f"{name} is not callable"

    def test_entities_are_types(self) -> None:
        """Every declared entity exports a class."""
        for name in ENTITY_NAMES:
            assert inspect.isclass(getattr(goga.build, name)), f"{name} is not a class"

    def test_pass_settings_hierarchy(self) -> None:
        """ReviewPassSettings is a PassSettings mutation, per the contract."""
        assert issubclass(goga.build.ReviewPassSettings, goga.build.PassSettings)
