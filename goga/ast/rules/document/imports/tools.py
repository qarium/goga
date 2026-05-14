from __future__ import annotations


def signature_contains_type_name(signature: str, type_name: str) -> bool:
    """Check whether `type_name` appears as an exact match in `signature`.

    Allowed boundary characters adjacent to the match: : > ( ) [ ] , space or string edge.
    Any other character (letter, digit, _, -, ", =, etc.) makes the match invalid.
    """
    if not type_name:
        return False
    allowed = {":", ">", "(", ")", "[", "]", ",", " ", "<"}
    start = 0
    while True:
        idx = signature.find(type_name, start)
        if idx == -1:
            return False
        end = idx + len(type_name)
        left_ok = idx == 0 or signature[idx - 1] in allowed
        right_ok = end == len(signature) or signature[end] in allowed
        if left_ok and right_ok:
            return True
        start = idx + 1
