"""The tool-package access of the hooks platform.

The entities declared in the cell CODEMANIFEST with ``location: packages.py``:
the package identity ``ToolPackage``, the environment enumeration
``enumerate_tool_packages``, and the facade callback invocation
``call_register_hooks``. This module is the only place in the platform that
reaches the installed packages: identities are read from the environment, the
enumeration imports nothing, and the single import of a facade happens inside
the callback invocation. A package runs at the trust level of its
installation — no isolation, no sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import packages_distributions
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # the registration envelope lives in the sibling module
    from .registration import HookRegistrar

_TOOL_PACKAGE_PREFIX = "goga_tool_"


@dataclass(frozen=True, kw_only=True)
class ToolPackage:
    """The identity of one installed tool package.

    The identity is assigned by the environment — a package never names
    itself. The record stores the top-level module name and derives the
    canonical hyphen form from it; both are computed reads, never fields.

    Attributes:
        module_name: The top-level module name of the installed package.

    Requirements:
        ``tool`` drops the ``goga_tool_`` prefix and turns underscores into
        hyphens; ``facade`` is ``module_name`` verbatim.
    """

    module_name: str

    @property
    def tool(self) -> str:
        """The tool identity — the canonical hyphen form without the prefix."""
        return self.module_name.removeprefix(_TOOL_PACKAGE_PREFIX).replace("_", "-")

    @property
    def facade(self) -> str:
        """The importable name of the facade module."""
        return self.module_name


def enumerate_tool_packages() -> list[ToolPackage]:
    """Enumerate the installed tool packages of the environment.

    One identity per installed package, in alphabetical order of the
    top-level module name. The environment is only read here — no package is
    imported: the facade import belongs to the callback invocation. An
    environment without tool packages yields an empty list, not an error.

    Returns:
        One identity per installed tool package, alphabetically ordered.
    """
    names = sorted(name for name in packages_distributions() if name.startswith(_TOOL_PACKAGE_PREFIX))

    return [ToolPackage(module_name=name) for name in names]


def call_register_hooks(package: ToolPackage, registrar: HookRegistrar) -> bool:
    """Import the facade of one tool package and run its registration callback.

    The single import of a tool package in the whole platform. A missing
    facade module and a facade without a callable ``register_hooks`` are
    normal conditions — a quiet skip, no warning and no error. A broken
    import of an existing package is the single fatal case of the platform:
    a clean error naming the package. An exception of the callback itself
    propagates unchanged — the isolation decision belongs to the caller.

    Args:
        package: The identity of the target package.
        registrar: The registration surface scoped to the package's tool.

    Returns:
        True when the callback ran, False on a quiet skip.

    Raises:
        ImportError: The package exists but its facade fails to import — the
            message names the package.
    """
    try:
        module = import_module(package.facade)

    except ModuleNotFoundError as exc:
        # The import machinery records on `exc.name` the module it could not
        # resolve, and that equals the facade only when the tool package
        # itself is missing. A deeper miss means the package was found — the
        # honest cause must not be masked by a quiet skip.
        if exc.name == package.facade:
            return False

        raise ImportError(f"package {package.facade} failed to import: {exc}") from exc

    except Exception as exc:  # a facade that fails to parse, and the like
        raise ImportError(f"package {package.facade} failed to import: {exc}") from exc

    callback = getattr(module, "register_hooks", None)

    if not callable(callback):
        return False

    callback(registrar)

    return True
