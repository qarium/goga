from __future__ import annotations

_DYNAMIC_PARAM_PREFIX = "..."
_DYNAMIC_PARAM_PREFIX_LEN = len(_DYNAMIC_PARAM_PREFIX)


def signature_contains_type_name(signature: str, type_name: str) -> bool:
    """Check whether `type_name` appears as an exact match in `signature`.

    Args:
        signature: Signature text to scan.
        type_name: Type name to look for.

    Returns:
        True when the match is bounded by ``: > ( ) [ ] ,``, a space, the string
        edge, or a ``...`` dynamic-parameter prefix on the left.
    """
    if not type_name:
        return False
    allowed = {":", ">", "(", ")", "[", "]", ",", " "}
    start = 0
    while True:
        idx = signature.find(type_name, start)
        if idx == -1:
            return False
        end = idx + len(type_name)
        left_ok = (
            idx == 0
            or signature[idx - 1] in allowed
            or (
                idx >= _DYNAMIC_PARAM_PREFIX_LEN
                and signature[idx - _DYNAMIC_PARAM_PREFIX_LEN : idx] == _DYNAMIC_PARAM_PREFIX
            )
        )
        right_ok = end == len(signature) or signature[end] in allowed
        if left_ok and right_ok:
            return True
        start = idx + 1
