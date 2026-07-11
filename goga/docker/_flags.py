"""Shared param→flag translation rule for docker CLI invocation.

Single source of truth for the rule used by both ``DockerBuilder.build`` and
``DockerRunner.run``. This is internal infrastructure — an underscore-prefixed
module that is NOT re-exported through the ``goga.docker`` facade, so the two
peer modules (``builder.py`` and ``runner.py``) share one rule without either
importing the other.
"""

from __future__ import annotations


def translate_params(params: dict[str, str | bool | list[str]]) -> list[str]:
    """Translate a params dict into docker CLI flag tokens.

    The shared rule (codified once here):

    - a 1-character key becomes a short flag (``p`` → ``-p``, ``v`` → ``-v``)
    - a multi-char snake_case key becomes a long flag with underscores turned
      into hyphens (``add_host`` → ``--add-host``, ``env_file`` → ``--env-file``)
    - a ``str`` value (and any non-bool scalar) becomes ``flag value``
    - a ``True`` value becomes a bare boolean flag (flag emitted, no value)
    - a ``False`` value omits the flag entirely
    - a ``list`` value repeats the flag once per element

    Iteration is order-preserving (dict insertion order), so callers control
    the on-screen flag order deterministically.
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
