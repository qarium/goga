"""Install command cell — CLI wrapper for the goga install command."""

from .install import install, resolve_version

__all__: list[str] = ["install", "resolve_version"]
