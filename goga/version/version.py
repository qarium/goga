"""Version-form domain — routines mapping version inputs to pip specifiers.

Sole owner of the version grammar: every mapping from a version form (or a
relative version-line constraint) to a PEP 440 pip specifier lives here;
consumers compose package identifiers from the returned specifiers. No I/O
lives here — all routines are pure transformers.
"""

from __future__ import annotations

import re

# Four-form version grammar — segment-count thresholds (see resolve_version).
# A version form splits on "." into segments; the segment count fixes the form:
#   2 segments → major x-range "N.x"; 3 segments with a trailing "x" → minor
#   x-range "N.M.x"; 1-3 numeric segments → concrete "N(.M)?(.K)?".
_XRANGE_MAJOR_SEGMENTS = 2
_XRANGE_MINOR_SEGMENTS = 3
_CONCRETE_MIN_SEGMENTS = 1
_CONCRETE_MAX_SEGMENTS = 3

# Leading release segments of an installed version (see resolve_relative_spec):
# the first numeric segment is the major, the optional second numeric segment
# is the minor; anything after them (pre/post/local/dev tails) is not consumed.
_RELEASE_PREFIX_RE = re.compile(r"(\d+)(?:\.(\d+))?")


def resolve_version(form: str | None) -> str | None:
    """Resolve a four-form version string into a pip specifier.

    Sole owner of the version grammar. Maps a version-form string to the pip
    specifier appended to a package identifier, or returns ``None`` when no
    specifier should be appended (the ``latest`` / absent case). Raises
    ``ValueError`` on operator-prefixed or malformed input — this routine owns
    the operator and emits it from the resolved grammar form.

    Accepted forms:
      * ``None`` or the literal ``"latest"`` → ``None`` (pip selects newest).
      * Major x-range ``"N.x"`` (one dot, last segment ``"x"``) → ``"~=N.0"``
        (PEP 440 compatible-release, upper bound ``<(N+1).0``).
      * Minor x-range ``"N.M.x"`` (two dots, last segment ``"x"``) → ``"~=N.M.0"``
        (PEP 440 compatible-release, upper bound ``<N.(M+1).0``). The trailing
        ``.0`` is required: ``~=N.M`` alone is a major-only bound.
      * Concrete ``"N"``, ``"N.M"``, or ``"N.M.K"`` (dot-separated non-empty
        numeric segments, no trailing ``"x"``) → ``"==<form>"``.

    Everything else — operator prefixes (``==``, ``>=``, ``<=``, ``~=``,
    ``!=``, ``<``, ``>``, ``===``), pre/post/local segments (``1.0.0a1``,
    ``1.0.0.post1``, ``1.0.0+local``), and any other shape — raises
    ``ValueError``. This is a pure transformer: no I/O, no logging, no config
    reading, no PEP 440 existence check (shape only).

    Args:
        form: Version-form string in one of the four grammar forms, or ``None``
            when no version was supplied.

    Returns:
        The resolved pip specifier (operator-prefixed), or ``None`` when the
        latest / no-specifier marker is requested.

    Raises:
        ValueError: If ``form`` is operator-prefixed or does not match any of
            the four grammar forms.
    """
    # 1. None / "latest" → no specifier; pip selects the newest under -U.
    if form is None or form == "latest":
        return None

    # 2. Operator-prefixed forms are rejected — this routine owns the operator.
    if form.startswith(("==", ">=", "<=", "~=", "!=", "<", ">", "===")):
        raise ValueError("operator-prefixed forms are rejected")

    segments = form.split(".")

    # 3. Major x-range "N.x": exactly one dot, last segment "x", major numeric.
    if len(segments) == _XRANGE_MAJOR_SEGMENTS and segments[1] == "x" and segments[0].isdigit() and segments[0] != "":
        return f"~={segments[0]}.0"

    # 4. Minor x-range "N.M.x": exactly two dots, last segment "x", both numeric.
    if (
        len(segments) == _XRANGE_MINOR_SEGMENTS
        and segments[2] == "x"
        and segments[0].isdigit()
        and segments[1].isdigit()
    ):
        return f"~={segments[0]}.{segments[1]}.0"

    # 5. Concrete "N(.M)?(.K)?": 1-3 numeric segments, no trailing "x".
    if _CONCRETE_MIN_SEGMENTS <= len(segments) <= _CONCRETE_MAX_SEGMENTS and all(
        s.isdigit() and s != "" for s in segments
    ):
        return f"=={form}"

    # 6. Anything else is malformed.
    raise ValueError("malformed version form")


def resolve_relative_spec(base_version: str, patch: bool = False, minor: bool = False) -> str:
    """Resolve an installed version and a selected line into a pip specifier.

    Relative version-line constraint builder: maps the installed version of
    the package being upgraded and a selected version line to the pip
    specifier that keeps an upgrade inside that line — ``patch`` selects the
    latest patch of the current minor (line ``X.Y.*``, ``~=X.Y.0``), ``minor``
    selects the latest release within the current major (line ``X.*``,
    ``~=X.0``). Resolution goes through ``resolve_version``, so the emitted
    specifier always carries the compatible-release operator.

    The base is reduced to its leading release segments: the first numeric
    segment is the major, the optional second numeric segment is the minor;
    anything after them (pre-release, post-release, local, dev tails) is
    discarded — rich bases are truncated, never rejected. This is a pure
    transformer: the caller owns the metadata boundary (reading the installed
    version) and composes the package identifier from the returned specifier.

    Args:
        base_version: Installed version string of the package being upgraded.
        patch: When True, constrain the target to the latest patch of the
            current minor line (``X.Y.*``).
        minor: When True, constrain the target to the latest release within
            the current major line (``X.*``).

    Returns:
        The resolved pip specifier (compatible-release form) that keeps the
        upgrade inside the selected version line.

    Raises:
        ValueError: If both or neither of ``patch``/``minor`` is selected; if
            ``base_version`` has no leading numeric segments (the line is
            undeterminable); if ``patch`` is selected but the base carries no
            minor segment; or — defensively, unreachable for synthesized
            forms — if the synthesized form resolves without a specifier.
    """
    # 1. Exactly one line flag must be selected.
    if patch == minor:
        raise ValueError("exactly one of patch/minor must be selected")

    # 2. Reduce the base to its leading release segments; rich tails are discarded.
    m = _RELEASE_PREFIX_RE.match(base_version)
    if m is None:
        raise ValueError(f"cannot determine version line from {base_version!r}")

    major, minor_seg = m.group(1), m.group(2)

    # 3. Synthesize the x-range form for the selected line.
    if patch:
        if minor_seg is None:
            raise ValueError(f"patch line is undeterminable from {base_version!r}: no minor segment")
        form = f"{major}.{minor_seg}.x"
    else:  # minor is True — guaranteed by step 1.
        form = f"{major}.x"

    # 4. Resolve through the grammar owner; the synthesized form always resolves.
    spec = resolve_version(form)
    if spec is None:  # unreachable: the synthesized "N(.M)?.x" form always resolves
        raise ValueError("synthesized form resolved without a specifier")

    return spec
