"""The ``load_home_profiles`` routine — collecting the personal bundle directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_home_profiles(home_dir: Path) -> dict[str, dict[str, Any]]:
    """Read and strictly parse the whole home profiles bundle: every flat ``*.yml`` file.

    Args:
        home_dir: the home profiles directory (typically ``~/.goga/profiles/``).

    Returns:
        The collected name → content mapping (file stem → parsed mapping),
        deterministic for unchanged directory contents; a missing directory
        resolves to an empty mapping.

    Raises:
        ValueError: If a ``*.yml`` file under ``home_dir`` is invalid YAML or
            its root is not a mapping — a malformed home profile is a strict
            failure on the host before any container launches.
    """
    if not home_dir.is_dir():
        return {}

    profiles: dict[str, dict[str, Any]] = {}

    # The flat non-recursive glob plus the sorted walk keep the bundle
    # deterministic; nested directories and non-yml files are invisible here.
    for path in sorted(home_dir.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text())

        except yaml.YAMLError:
            raise ValueError(f"invalid YAML in home profile: {path}") from None

        if not isinstance(data, dict):
            raise ValueError(f"home profile must be a mapping: {path}")

        profiles[path.stem] = data

    return profiles
