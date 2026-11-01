"""The ``resolve_profile`` routine — validating and resolving one profile name."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .profile_source import ProfileSource
from .resolved_profile import ResolvedProfile

# The profile-name grammar — a single filesystem path component. The first
# character must be alphanumeric and the rest may carry dots, underscores, and
# hyphens, so the traversal names "." and ".." (and any "/"-carrying name)
# fail the pattern by construction; the check is the path-traversal guard.
_PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def resolve_profile(
    name: str,
    project_dir: Path,
    home_profiles: dict[str, dict[str, Any]],
) -> ResolvedProfile:
    """Validate a profile name and resolve it: project lookup first, then the home bundle.

    Args:
        name: the requested profile name.
        project_dir: the project profiles directory (typically
            ``<cwd>/.goga/profiles/``).
        home_profiles: the decoded home bundle mapping (name → content).

    Returns:
        The resolved profile — its name, its whole content mapping as the
        rendering context, and the origin. On the same name in both lookup
        locations the project file wins.

    Raises:
        ValueError: If ``name`` violates the profile-name grammar
            (``[A-Za-z0-9][A-Za-z0-9._-]*``; "." and ".." forbidden — the name
            becomes a filesystem path component), if the existing project file
            is invalid YAML, its root is not a mapping, or it carries a
            non-string key (the rendering context is keyword arguments — a
            non-str key would crash the render with a raw ``TypeError``), or
            if the profile exists in neither lookup location.
    """
    if not _PROFILE_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"invalid profile name: {name}")

    path = project_dir / f"{name}.yml"

    # A malformed project file is a strict failure with NO home fall-through —
    # the author committed a broken file, and silently masking it with the
    # personal bundle would hide the defect.
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text())

        except yaml.YAMLError:
            raise ValueError(f"invalid YAML in profile {name}: {path}") from None

        if not isinstance(data, dict):
            raise ValueError(f"profile {name} must be a mapping: {path}")

        if not all(isinstance(key, str) for key in data):
            raise ValueError(f"profile {name} must have string keys: {path}")

        return ResolvedProfile(name=name, data=data, source=ProfileSource.PROJECT)

    if name in home_profiles:
        return ResolvedProfile(name=name, data=home_profiles[name], source=ProfileSource.HOME)

    raise ValueError(f"profile {name} not found in {project_dir} or the home bundle")
