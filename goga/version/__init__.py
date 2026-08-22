"""Version-form domain — pure transformers from version forms to pip specifiers."""

from .version import (
    compare_versions,
    host_goga_version,
    resolve_relative_spec,
    resolve_version,
    version_check_enabled,
)

__all__: list[str] = [
    "compare_versions",
    "host_goga_version",
    "resolve_relative_spec",
    "resolve_version",
    "version_check_enabled",
]
