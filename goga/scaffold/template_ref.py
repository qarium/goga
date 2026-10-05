from __future__ import annotations


def parse_template_ref(
    template_input: str,
    ref_override: str | None,
) -> tuple[str, str | None]:
    """Parse a raw template source string into clean copier inputs.

    Args:
        template_input: raw template source — a git URL, optionally carrying a
            ref fragment (``url.git#ref``).
        ref_override: explicit git ref from ``--ref``, or ``None`` when not
            given. Takes precedence over the URL fragment when both are present.
            An empty string is treated as "not given".

    Returns:
        The clean ``(template_url, effective_ref)`` pair. ``effective_ref`` is
        ``ref_override`` when it is a non-empty string, else the fragment when
        it is non-empty (``None`` when the input carried no fragment or an empty
        one).
    """
    if "#" in template_input:
        template_url, base_ref = template_input.rsplit("#", 1)
        if not base_ref:
            base_ref = None
    else:
        template_url, base_ref = template_input, None

    effective_ref = ref_override if ref_override else base_ref
    return template_url, effective_ref
