"""Pure encode/decode of the home-profiles bundle carriage for the docker boundary."""

from __future__ import annotations

import base64
import json
from typing import Any

_HOME_PROFILES_VARIABLE = "GOGA_HOME_PROFILES"


def encode_home_profiles(profiles: dict[str, dict[str, Any]]) -> str:
    """Encode the home profiles bundle into the engine payload value.

    Args:
        profiles: the whole home bundle — profile name to content mapping;
            contents are carried verbatim (the host loader owns strictness).

    Returns:
        The single-line payload string: compact sorted JSON of the bundle,
        base64-encoded with padding; an empty string when the bundle is
        empty. Deterministic — identical bundles produce the identical
        value.

    Raises:
        ValueError: when a profile value is not JSON-representable (e.g. a
            YAML date) — the message names the engine variable only, so the
            host launchers surface one clean error.
    """
    if not profiles:
        return ""

    try:
        payload = json.dumps(profiles, separators=(",", ":"), sort_keys=True)
    except TypeError:
        raise ValueError(f"{_HOME_PROFILES_VARIABLE}: non-JSON-representable profile value") from None

    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def profile_carriage_lines(
    ambient_profile: str,
    home_profiles: dict[str, dict[str, Any]] | None,
    workflow_name: str | None = None,
    skip_keys: frozenset[str] | set[str] = frozenset(),
) -> list[str]:
    """Compose the contributor-profile carriage env-file lines.

    Args:
        ambient_profile: the ambient host ``GOGA_PROFILE`` value (an empty
            string when unset).
        home_profiles: the loaded home bundle (None or empty when absent).
        workflow_name: the effective workflow name of the run decision —
            carried only by the pipeline run launcher (the build and info
            launchers pass None and never write the line).
        skip_keys: the engine-skip rule — env-file keys the CLI supplied
            explicitly; a skipped key keeps the user's own line winning.

    Returns:
        The carriage lines — ``GOGA_PROFILE`` when the ambient value is
        non-empty, ``GOGA_HOME_PROFILES`` (the ``encode_home_profiles``
        value) when the bundle is non-empty, ``GOGA_WORKFLOW`` when a
        workflow name is given — each written only when it carries cargo and
        its key is not skipped; an empty list means no cargo. The payload
        values never appear in any message.
    """
    lines: list[str] = []

    if ambient_profile and "GOGA_PROFILE" not in skip_keys:
        lines.append(f"GOGA_PROFILE={ambient_profile}")

    if home_profiles and "GOGA_HOME_PROFILES" not in skip_keys:
        lines.append(f"GOGA_HOME_PROFILES={encode_home_profiles(home_profiles)}")

    if workflow_name is not None and "GOGA_WORKFLOW" not in skip_keys:
        lines.append(f"GOGA_WORKFLOW={workflow_name}")

    return lines


def decode_home_profiles(value: str) -> dict[str, dict[str, Any]]:
    """Decode the engine payload value back into the home profiles bundle.

    Args:
        value: the payload string of the dedicated engine variable; an absent
            or empty variable arrives as an empty string.

    Returns:
        The decoded home profiles bundle; empty when the payload carried
        nothing. Inner maps may hold any scalars — only the name keys and
        the nesting shape are checked.

    Raises:
        ValueError: when the payload fails base64 decoding or JSON parsing,
            carries a non-mapping root, or carries a value that is not
            itself a mapping. The message names the engine variable only —
            no payload content appears in it.
    """
    if value == "":
        return {}

    try:
        payload = json.loads(base64.b64decode(value, validate=True))
    except ValueError:
        # binascii.Error and json.JSONDecodeError are both ValueError
        # subclasses — a single arm covers the whole decode failure set.
        raise ValueError(f"{_HOME_PROFILES_VARIABLE}: invalid payload") from None

    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(item, dict) for key, item in payload.items()
    ):
        raise ValueError(f"{_HOME_PROFILES_VARIABLE}: invalid payload")

    return dict(payload)
