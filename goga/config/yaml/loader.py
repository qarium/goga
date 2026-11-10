"""The environment-aware YAML load of the configuration family — the ``!ENV`` scalar tag.

Every ``!ENV NAME`` scalar in a parsed text resolves from the process
environment at load time into a plain string; the parsed value is returned
as-is. The tag is registered on a private loader subclass only, so every
other ``yaml.safe_load`` site of the process stays unaffected.
"""

from __future__ import annotations

import os

import yaml
from yaml.constructor import ConstructorError


def _construct_env(_loader: yaml.Loader, node: yaml.Node) -> str:
    """Resolve one ``!ENV NAME`` scalar node from the process environment.

    Args:
        _loader: The constructing loader instance (unused — the environment
            is the only resolution source).
        node: The tagged node; for a scalar tag its ``value`` is the
            variable name.

    Returns:
        The referenced variable's value — always a string, ``""`` when the
        variable is unset (no type coercion; downstream validation owns the
        empty-value semantics).

    Raises:
        yaml.constructor.ConstructorError: When the tagged node is not a
            scalar or carries an empty argument — the yaml error channel
            carrying the node position.
    """
    if not isinstance(node, yaml.ScalarNode):
        raise ConstructorError(None, None, "expected a scalar argument in !ENV", node.start_mark)

    if node.value == "":
        raise ConstructorError(None, None, "expected a variable name in !ENV", node.start_mark)

    return os.environ.get(node.value, "")


class _EnvLoader(yaml.SafeLoader):
    """The safe loader subclass carrying the ``!ENV`` scalar constructor.

    The constructor is registered on this subclass only (never on the global
    ``yaml.SafeLoader``): the tag applies exclusively where this loader is
    used, and plain ``yaml.safe_load`` sites keep rejecting it as an
    unknown tag.
    """


_EnvLoader.add_constructor("!ENV", _construct_env)


def parse_env_yaml(text: str) -> object:
    """Parse a configuration YAML text with environment references resolved.

    Every ``!ENV NAME`` scalar resolves from the process environment at load
    time into a plain string (``""`` when unset); resolution happens through
    the yaml constructor mechanism — no text preprocessing, no post-parse
    walk. The parsed value is returned as-is: interpretation and validation
    belong to the consuming configuration loader.

    Args:
        text: The raw YAML text of a configuration file.

    Returns:
        The parsed value as-is — a mapping, a list, or a scalar, whatever
        the YAML parses to (``None`` for an empty text).

    Raises:
        yaml.YAMLError: On malformed YAML, including the constructor errors
            of malformed ``!ENV`` use (an empty argument, a non-scalar
            tagged node) — carrying the node position.
    """
    return yaml.load(text, Loader=_EnvLoader)
