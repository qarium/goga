from __future__ import annotations


def parse_template_ref(
    template_input: str,
    ref_override: str | None,
) -> tuple[str, str | None]:
    """Parse a raw template source string into clean copier inputs.

    Splits ``template_input`` on its ref fragment and resolves the effective
    ref with ``ref_override`` precedence. Pure parser — no fetch or validation.

    Args:
        template_input: raw template source — a git URL, optionally carrying a
            ref fragment (``url.git#ref``).
        ref_override: explicit git ref from ``--ref``, or ``None`` when not
            given. Takes precedence over the URL fragment when both are present.

    Returns:
        The clean ``(template_url, effective_ref)`` pair. ``effective_ref`` is
        ``ref_override`` when not ``None``, else the fragment (``None`` when the
        input carried no fragment).
    """
    if "#" in template_input:
        template_url, base_ref = template_input.rsplit("#", 1)
    else:
        template_url, base_ref = template_input, None

    effective_ref = ref_override if ref_override is not None else base_ref
    return template_url, effective_ref
