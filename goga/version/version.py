"""Version-form domain — version grammar plus the host-side consistency check."""

from __future__ import annotations

import importlib.metadata
import os
import re
import sys

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

# User-facing messages of the version check (see ensure_version_match). Every
# refusal names the escape hatch GOGA_SKIP_VERSION_CHECK=1 so the remedy is
# discoverable from the error alone; all messages go to sys.stderr only.
MSG_HOST_FAILED = (
    "goga version check: cannot determine the goga version installed on the "
    "host ({exc}). Reinstall goga, or set GOGA_SKIP_VERSION_CHECK=1 to skip "
    "this check."
)
MSG_PROBE_FAILED = (
    "goga version check: could not determine the goga version inside the "
    "project image — the image must be able to run python3 and report "
    "importlib.metadata.version('goga'). Fix the image, or set "
    "GOGA_SKIP_VERSION_CHECK=1 to skip this check."
)
MSG_UNKNOWN_VERSION = (
    "goga version check: the image reports goga version 0.0.0 (a locally "
    "built image without a stamped version) — skipping the comparison."
)
MSG_MISMATCH = (
    "goga version check: host goga {host} and image goga {image} differ at "
    "the (major, minor) level. Align the host CLI and the project image "
    "(goga upgrade / rebuild or re-pull the image), or set "
    "GOGA_SKIP_VERSION_CHECK=1 to skip this check."
)


def _is_ascii_digits(segment: str) -> bool:
    """Return ``True`` for a non-empty run of ASCII digits ``0-9``.

    Args:
        segment: Version segment to test.

    Returns:
        True when the segment is a non-empty ASCII-digit run.
    """
    return segment != "" and segment.isascii() and segment.isdigit()


def _release_segments(version: str) -> tuple[str, str | None]:
    """Reduce a version string to its leading release segments.

    Args:
        version: Version string to reduce.

    Returns:
        Tuple of the major and the optional minor segment (``None`` when
        absent); pre/post/local/dev tails are discarded, never rejected.

    Raises:
        ValueError: If ``version`` has no leading numeric major segment.
    """
    m = _RELEASE_PREFIX_RE.match(version)

    if m is None:
        raise ValueError(f"cannot determine version line from {version!r}")

    return m.group(1), m.group(2)


def resolve_version(form: str | None) -> str | None:
    """Resolve a four-form version string into a pip specifier.

    Args:
        form: Version-form string — ``"latest"``, x-range ``"N.x"`` or
            ``"N.M.x"``, or concrete ``"N"``/``"N.M"``/``"N.M.K"``; ``None``
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

    Args:
        base_version: Installed version string of the package being upgraded;
            pre/post/local/dev tails are discarded, never rejected.
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

    Args:
        host_version: First version string (release segments, possibly with
            dev/pre/post/local tails).
        image_version: Second version string (same forms).

    Returns:
        True when both ``(major, minor)`` pairs coincide, False otherwise; a
        missing minor counts as ``0``, so a patch difference never changes the verdict.

    Raises:
        ValueError: If either argument has no leading numeric major segment.
    """

    def pair(version: str) -> tuple[int, int]:
        """Reduce one version string to its comparable ``(major, minor)`` pair.

        Args:
            version: The version string to reduce; must carry a leading numeric
                major segment.

        Returns:
            The ``(major, minor)`` tuple with ``minor`` defaulting to ``0`` when
            the segment is absent.
        """
        major, minor = _release_segments(version)
        minor_int = int(minor) if minor is not None else 0

        return int(major), minor_int

    return pair(host_version) == pair(image_version)


def host_goga_version() -> str:
    """Read the version of the goga distribution installed on the host.

    Returns:
        The installed version string of the goga package.

    Raises:
        importlib.metadata.PackageNotFoundError: When the goga distribution
            is not installed in the current interpreter; translating the
            failure into a user-facing error belongs to the caller.
    """
    return importlib.metadata.version("goga")


def minor_version(version: str) -> str:
    """Reduce a version string to its minor line — the ``N.M`` form.

    Args:
        version: Version string to reduce (release segments, possibly with
            dev/pre/post/local tails).

    Returns:
        The minor line ``N.M`` of ``version``; a missing minor segment counts
        as ``0`` (``"2"`` → ``"2.0"``).

    Raises:
        ValueError: If ``version`` has no leading numeric major segment.
    """
    major, minor_seg = _release_segments(version)
    minor = minor_seg if minor_seg is not None else "0"

    return f"{major}.{minor}"


def version_check_enabled() -> bool:
    """Decide whether the host-side version check must run.

    Returns:
        True when the check must run (the probe and the comparison), False
        only when ``GOGA_SKIP_VERSION_CHECK`` equals the exact string ``"1"``.
    """
    return os.environ.get("GOGA_SKIP_VERSION_CHECK") != "1"


def ensure_version_match(image_version: str | None) -> None:
    """Apply the outcome matrix of the host-image version consistency check.

    Args:
        image_version: Version string reported for the goga package inside
            the project image, or ``None`` when the probe could not
            determine it.

    Returns:
        ``None`` — agreement and the ``0.0.0`` warning path return normally.

    Raises:
        SystemExit: with code ``1`` when the host version is undeterminable,
            the probe failed (``image_version is None``), or the versions
            differ at the (major, minor) level.
    """
    # 1. Host side: the version must be determinable (missing dist or broken
    #    dist-info are the same refusal).
    try:
        host = host_goga_version()
    except importlib.metadata.PackageNotFoundError as exc:
        print(MSG_HOST_FAILED.format(exc=exc), file=sys.stderr)
        sys.exit(1)

    if not host:
        print(MSG_HOST_FAILED.format(exc="version metadata is unreadable"), file=sys.stderr)
        sys.exit(1)

    # 2. Image side: the probe must have answered.
    if image_version is None:
        print(MSG_PROBE_FAILED, file=sys.stderr)
        sys.exit(1)

    # 3. Locally built image without a stamped version — an unknown version
    #    is not a confirmed mismatch; the launch continues.
    if image_version == "0.0.0":
        print(MSG_UNKNOWN_VERSION, file=sys.stderr)
        return None

    # 4. Refuse on (major, minor) divergence — a patch difference agrees.
    if not compare_versions(host, image_version):
        print(MSG_MISMATCH.format(host=host, image=image_version), file=sys.stderr)
        sys.exit(1)

    # 5. Agreement — silent return.
    return None
