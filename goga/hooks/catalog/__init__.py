"""Action catalog cell — the map of subscription addresses of the domains.

The owner of the action catalog: every known address with its error class.
The catalog is data only — a registration envelope is validated against it
and an emitted address resolves through it. Importing the package imports
no packages and enumerates nothing.
"""

from .catalog import Action, declared_actions

__all__: list[str] = [
    "Action",
    "declared_actions",
]
