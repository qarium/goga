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
    """
    if not profiles:
        return ""

    payload = json.dumps(profiles, separators=(",", ":"), sort_keys=True)

    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


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
