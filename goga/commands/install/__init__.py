"""Install command cell — CLI wrappers for the goga tool package lifecycle."""

from .install import install
from .uninstall import uninstall

__all__: list[str] = ["install", "uninstall"]
