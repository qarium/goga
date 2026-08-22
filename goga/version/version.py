"""Version-form domain — routines mapping version inputs to pip specifiers.

Sole owner of the version grammar: every mapping from a version form (or a
relative version-line constraint) to a PEP 440 pip specifier lives here;
consumers compose package identifiers from the returned specifiers. No I/O
lives here — all routines are pure transformers.
"""

from __future__ import annotations

import importlib.metadata
import os
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
# re.ASCII keeps \d to 0-9: without it \d also matches Unicode decimal digits
# (e.g. Arabic-Indic U+0661), which are not PEP 440.
_RELEASE_PREFIX_RE = re.compile(r"(\d+)(?:\.(\d+))?", re.ASCII)


def _is_ascii_digits(segment: str) -> bool:
    """Return ``True`` for a non-empty run of ASCII digits ``0-9``.

    ``str.isdigit`` alone also accepts non-ASCII Unicode digits (Arabic-Indic
    U+0661, superscript U+00B2); those pass a shape check yet are not PEP 440,
    so the grammar rejects them.
    """
    return segment != "" and segment.isascii() and segment.isdigit()


def _release_segments(version: str) -> tuple[str, str | None]:
    """Reduce a version string to its leading release segments.

    The first numeric segment is the major, the optional second numeric
    segment is the minor; anything after them (pre-release, post-release,
    local, dev tails) is discarded — rich versions are truncated, never
    rejected. Shared reduction step of ``resolve_relative_spec`` and
    ``compare_versions``.

    Args:
        version: Version string to reduce.

    Returns:
        Tuple of the major segment and the optional minor segment (``None``
        when the version carries no minor segment).

    Raises:
        ValueError: If ``version`` has no leading numeric major segment.
    """
    m = _RELEASE_PREFIX_RE.match(version)
    if m is None:
        raise ValueError(f"cannot determine version line from {version!r}")
    return m.group(1), m.group(2)


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
    if len(segments) == _XRANGE_MAJOR_SEGMENTS and segments[1] == "x" and _is_ascii_digits(segments[0]):
        return f"~={segments[0]}.0"

    # 4. Minor x-range "N.M.x": exactly two dots, last segment "x", both numeric.
    if (
        len(segments) == _XRANGE_MINOR_SEGMENTS
        and segments[2] == "x"
        and _is_ascii_digits(segments[0])
        and _is_ascii_digits(segments[1])
    ):
        return f"~={segments[0]}.{segments[1]}.0"

    # 5. Concrete "N(.M)?(.K)?": 1-3 numeric segments, no trailing "x".
    if _CONCRETE_MIN_SEGMENTS <= len(segments) <= _CONCRETE_MAX_SEGMENTS and all(_is_ascii_digits(s) for s in segments):
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
    major, minor_seg = _release_segments(base_version)

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


def compare_versions(host_version: str, image_version: str) -> bool:
    """Compare two version strings at the (major, minor) level.

    Pure comparator for the host-image consistency check: both arguments are
    reduced to their leading release segments (rich dev/pre/post/local tails
    are discarded) and compared as integer ``(major, minor)`` pairs. A missing
    minor segment counts as ``0`` (``"1"`` ≡ ``"1.0"``), so a patch
    difference never affects the verdict — only a major or minor difference
    does. Shape recognition only: no PEP 440 existence check, no metadata or
    environment reads, no logging.

    Args:
        host_version: First version string (release segments, possibly with
            dev/pre/post/local tails).
        image_version: Second version string (same forms).

    Returns:
        True when both ``(major, minor)`` pairs coincide, False otherwise.

    Raises:
        ValueError: If either argument has no leading numeric major segment.
    """

    def pair(version: str) -> tuple[int, int]:
        major, minor = _release_segments(version)
        minor_int = int(minor) if minor is not None else 0
        return int(major), minor_int

    return pair(host_version) == pair(image_version)


def host_goga_version() -> str:
    """Read the version of the goga distribution installed on the host.

    Single reading point for the host goga version — every consumer of the
    host version goes through this routine. Reads the installed distribution
    metadata via the standard library ``importlib.metadata`` and returns the
    version string unchanged.

    Returns:
        The installed version string of the goga package.

    Raises:
        importlib.metadata.PackageNotFoundError: When the goga distribution
            is not installed in the current interpreter; translating the
            failure into a user-facing error belongs to the caller.
    """
    return importlib.metadata.version("goga")


def version_check_enabled() -> bool:
    """Decide whether the host-side version check must run.

    Companion of ``ensure_version_match``: when this predicate returns False,
    the caller skips both the probe and the comparison — one gate, one place;
    ``ensure_version_match`` runs only on the True path. The check is
    disabled only by the exact value ``"1"`` of the ``GOGA_SKIP_VERSION_CHECK``
    environment variable; an unset, empty, ``"0"``, or any other value leaves
    the check enabled (exact comparison — no stripping, no case folding).
    Nothing is printed or logged.

    Returns:
        True when the check must run (the probe and the comparison), False
        only when ``GOGA_SKIP_VERSION_CHECK`` equals the exact string ``"1"``.
    """
    return os.environ.get("GOGA_SKIP_VERSION_CHECK") != "1"
