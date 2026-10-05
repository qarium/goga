"""Action catalog cell — the map of subscription addresses of the domains."""

from .catalog import Action, declared_actions

__all__: list[str] = [
    "Action",
    "declared_actions",
]
