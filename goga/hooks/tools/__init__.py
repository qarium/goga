"""Tool-package access and registration cell — the tool-facing surface.

The owner of the package identities, the environment enumeration, the facade
callback invocation, and the registration envelope. A subscription enters the
platform through this surface alone. Importing the package imports no tool
package and enumerates nothing.
"""

from .packages import ToolPackage, call_register_hooks, enumerate_tool_packages
from .registration import HookRegistrar, RejectedRegistration, Subscription

__all__: list[str] = [
    "HookRegistrar",
    "RejectedRegistration",
    "Subscription",
    "ToolPackage",
    "call_register_hooks",
    "enumerate_tool_packages",
]
