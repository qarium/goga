"""Shared fixtures and helpers of the config hooks zone tests.

The zone suites pin the two outside-world points of the hooks platform
(``pin_package_environment`` / ``install_tool_package``) with the platform
code under test running for real; both fixtures live once in the root
``tests/conftest.py`` and are inherited by every test, so no re-export
shim lives here.

The ``_authored(**overrides)`` factory below is the zone's shared minimal
authored ``ProjectConfig`` — every optional branch absent — layered with the
overrides a scenario needs.
"""

from __future__ import annotations

from goga.config.project import ProjectConfig


def _authored(**overrides: object) -> ProjectConfig:
    """A minimal authored configuration — every optional branch absent.

    Args:
        overrides: authored fields to set over the minimal base (a present
            section, an authored ``""``/``False``, an authored usages tree,
            ...).

    Returns:
        The authored configuration of the run.
    """
    fields: dict[str, object] = {
        "language": "python",
        "image": None,
        "dockerfile": None,
        "build": None,
        "pipeline": None,
    }
    fields.update(overrides)

    return ProjectConfig(**fields)  # type: ignore[arg-type]
