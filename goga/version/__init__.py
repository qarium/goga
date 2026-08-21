"""Version-form domain — pure transformers from version forms to pip specifiers."""

from .version import resolve_relative_spec, resolve_version

__all__: list[str] = ["resolve_relative_spec", "resolve_version"]
