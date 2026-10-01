"""Pure encode/decode of the CLI environment carriage payload for the docker boundary."""

from __future__ import annotations

import base64
import json

_EXTRA_ENV_VARIABLE = "GOGA_EXTRA_ENV"


def encode_extra_env(entries: list[str]) -> str:
    """Encode the CLI environment entries into the engine payload value.

    Turns the raw ``KEY=VALUE`` strings of the CLI environment option into the
    single-line payload carried across the docker boundary by the dedicated
    engine variable. Each entry splits at the first ``=``; an entry without a
    separator is skipped silently — no validation, no warning. A repeated key
    resolves last-wins, the same rule the env-file itself applies.

    Args:
        entries: raw ``KEY=VALUE`` strings of the CLI environment option,
            verbatim.

    Returns:
        The single-line payload string: compact sorted JSON of the resolved
        mapping, base64-encoded with padding. Deterministic — identical
        entries produce the identical value.
    """
    resolved: dict[str, str] = {}

    for pair in entries:
        key, separator, value = pair.partition("=")

        if separator == "":
            continue

        resolved[key] = value

    payload = json.dumps(resolved, separators=(",", ":"), sort_keys=True)

    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def decode_extra_env(value: str) -> dict[str, str]:
    """Decode the engine payload value back into the CLI environment mapping.

    The inverse of :func:`encode_extra_env`: the payload of the dedicated
    engine variable comes back as the mapping a domain launch applies above
    its effective task env layer. An empty ``value`` resolves to an empty
    mapping — nothing to apply. Nothing is applied, printed, or logged here;
    application belongs to the consuming domain launch.

    Args:
        value: the payload string of the dedicated engine variable; an absent
            or empty variable arrives as an empty string.

    Returns:
        The decoded CLI environment mapping; empty when the payload carried
        nothing.

    Raises:
        ValueError: when the payload fails base64 decoding or JSON parsing, or
            does not carry a string-to-string mapping. The message names the
            engine variable only — no payload content appears in it.
    """
    if value == "":
        return {}

    try:
        payload = json.loads(base64.b64decode(value, validate=True))
    except ValueError:
        # binascii.Error and json.JSONDecodeError are both ValueError
        # subclasses — a single arm covers the whole decode failure set.
        raise ValueError(f"{_EXTRA_ENV_VARIABLE}: invalid payload") from None

    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in payload.items()
    ):
        raise ValueError(f"{_EXTRA_ENV_VARIABLE}: invalid payload")

    return dict(payload)
