"""Shared param→flag translation rule for docker CLI invocation."""

from __future__ import annotations


def translate_params(params: dict[str, str | bool | list[str]]) -> list[str]:
    """Translate a params dict into docker CLI flag tokens, preserving dict order.

    Args:
        params: Mapping of parameter names to flags — booleans toggle a flag,
            lists repeat it per element, other values become the flag argument.

    Returns:
        Docker CLI flag tokens in dict order.
    """
    flags: list[str] = []
    for key, value in params.items():
        flag = f"-{key}" if len(key) == 1 else f"--{key.replace('_', '-')}"
        if value is True:
            flags.append(flag)
        elif value is False:
            continue
        elif isinstance(value, list):
            for element in value:
                flags.append(flag)
                flags.append(str(element))
        else:
            flags.append(flag)
            flags.append(str(value))
    return flags
