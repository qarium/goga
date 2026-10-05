"""The read side of the tool-config standard — the raw loader."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_tool_config(tool: str, filename: str, root: Path | None = None) -> object | None:
    """Load one tool config file — the read-side counterpart of the tool-config write standard.

    Algorithm:
        1. Compose ``<root>/.goga/tools/<tool>/<filename>`` with ``filename``
           taken verbatim.
        2. A ``filename`` that is empty, carries a path separator, or equals
           ``.``/``..`` — a non-flat name segment — is a clean error before
           any read.
        3. An absent file returns ``None`` — absence is the normal state of a
           tool config.
        4. A present file parses via the ``yaml`` practice and returns the raw
           value as-is.

    Requirements:
        - Path standardization only — the same standard as the write side.
        - No content models, no structural expectations, no validation.
        - No merging with any configuration layer, no caching.

    Constraints:
        - Do not interpret the content — interpreting is the consuming tool's
          responsibility.

    Args:
        tool: The tool identity — the directory name under ``.goga/tools``.
            Never validated; the platform owns the identity.
        filename: The config file name, verbatim with extension — an exact
            match, no suffix rules.
        root: Optional root-directory override for tests; ``None`` uses the
            project-root anchor of the configuration loaders (``Path(".")``).

    Returns:
        The raw parsed content as-is — a mapping, a string, a list, whatever
        the YAML parses to — or ``None`` when the file is absent (an empty
        file also parses to ``None``).

    Raises:
        ValueError: When ``filename`` is not a flat name segment (empty,
            ``.``, ``..``, or containing ``/`` or ``\\``) — raised before any
            filesystem access.
        yaml.YAMLError: When a present file fails to parse — propagated raw;
            interpreting is the consumer's job.
        OSError: When a present file cannot be read — propagated raw.
        UnicodeDecodeError: When a present file is not decodable as UTF-8 —
            propagated raw, never a silent fallback.
    """
    if filename == "" or filename in (".", "..") or "/" in filename or "\\" in filename:
        raise ValueError(f"tool config file name must be a flat segment: {filename!r}")

    base = root if root is not None else Path()
    path = base / ".goga" / "tools" / tool / filename

    if not path.exists():
        return None

    return yaml.safe_load(path.read_text(encoding="utf-8"))
