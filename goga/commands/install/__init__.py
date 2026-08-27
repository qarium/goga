"""Install command cell — CLI wrappers for the goga tool package lifecycle."""

from .hook import call_install_hook, resolve_initiating_user, run_install_hooks
from .install import install
from .uninstall import uninstall

__all__: list[str] = ["call_install_hook", "install", "resolve_initiating_user", "run_install_hooks", "uninstall"]
