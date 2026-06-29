"""AFM cell — thin subprocess-only wrapper over the external flowmanager binary."""

from .run_flow import run_flow

__all__: list[str] = [
    "run_flow",
]
