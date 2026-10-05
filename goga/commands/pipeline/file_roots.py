"""Producer of the afm file-manager roots (the ``AFM_DOCKER_FILE_ROOTS`` payload)."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

# Recognized volume-declaration flag forms: ``-v VALUE`` / ``--volume VALUE``
# (two tokens) and ``--volume=VALUE`` (one token). The ``-v=VALUE`` shape is
# not documented by the docker CLI and is deliberately NOT recognized.
_VOLUME_FLAGS = ("-v", "--volume")
_VOLUME_EQ_PREFIX = "--volume="

# A ``source:target[:mode]`` declaration splits into at most 3 colon-separated
# parts; anything longer is an unrecognized form and is skipped.
_MAX_VOLUME_PARTS = 3


@dataclass(frozen=True, kw_only=True)
class FileRoot:
    """One browsable directory root surfaced to the afm dashboard — an immutable record of the ``afm`` payload schema.

    Args:
        id: Stable identifier, unique within the roots list; ``"project"``
            for the project root.
        label: Display name: ``"project"`` for the project root; the full
            container path for extra roots.
        container_path: In-container mount point of the browsable directory.
        mount_read_only: True when the mount is read-only (a ``ro`` mode
            segment on the declaration).
        kind: ``"project"`` or ``"extra"``.

    Note:
        All five fields are required — default empty values (e.g.
        ``id=""``) would violate the payload contract, so no field carries
        a default.
    """

    id: str
    label: str
    container_path: str
    mount_read_only: bool
    kind: str


def _host_is_dir(host: str) -> bool:
    """Probe whether the host side of a mount declaration is an existing directory.

    Args:
        host: Host-side path of a volume declaration, consumed verbatim —
            ``~`` and ``$VAR`` are NOT expanded (a literal non-existent path
            simply fails the existence check).

    Returns:
        True when the host path resolves to an existing directory (symlinks
        are followed, mirroring docker's resolved bind mounts); False on any
        other outcome. Every ``OSError`` — e.g. ``PermissionError``/EACCES
        on a ``-v /root/...`` mount probed by a non-root launcher, where
        ``Path.is_dir()`` propagates — is swallowed, so an inaccessible
        host path degrades to a skipped root instead of crashing the
        launch.
    """
    try:
        return Path(host).is_dir()
    except OSError:
        return False


def _next_volume_value(tokens: list[str], i: int) -> tuple[str | None, int]:
    """Recognize the volume declaration starting at ``tokens[i]`` (scanner step).

    Args:
        tokens: The already-tokenized ``home.docker.run`` list — never re-split
            or re-quoted (``home-configuration`` contract).
        i: Index of the candidate token.

    Returns:
        ``(value, next_i)`` — the declaration's value string and the index to
        resume scanning from, or ``(None, i + 1)`` when the token is not a
        recognized volume declaration. A dangling flag at the end of the list
        (``i + 1`` out of range) also yields ``None``.
    """
    token = tokens[i]
    if token in _VOLUME_FLAGS and i + 1 < len(tokens):
        return tokens[i + 1], i + 2
    if token.startswith(_VOLUME_EQ_PREFIX):
        return token[len(_VOLUME_EQ_PREFIX) :], i + 1
    return None, i + 1


def _parse_volume(value: str) -> tuple[str, str, str | None] | None:
    """Split a volume declaration value into ``(host, container, mode)``.

    Args:
        value: The declaration value, e.g. ``/host/dir:/ctr:ro``.

    Returns:
        The three-way split with ``mode`` present only for the 3-part form,
        or ``None`` for forms outside the ``source:target[:mode]`` contract:
        a single part (anonymous volume ``/ctr``) or more than three parts.
    """
    parts = value.split(":")
    if len(parts) == 1 or len(parts) > _MAX_VOLUME_PARTS:
        return None
    mode = parts[2] if len(parts) == _MAX_VOLUME_PARTS else None
    return parts[0], parts[1], mode


def _mode_is_read_only(mode: str | None) -> bool:
    """Whether the declaration's mode list contains an exact ``ro`` segment.

    Args:
        mode: The optional third part of a volume declaration (e.g. ``ro``,
            ``ro,z``, ``rw``), already split away from the paths.

    Returns:
        True only when a comma-separated segment strips to exactly ``"ro"``
        (``"ro"`` in ``"ro,z"`` → True; ``"rw"`` → False). False when the
        declaration carries no mode at all.
    """
    if mode is None:
        return False
    return "ro" in [segment.strip() for segment in mode.split(",")]


def _root_id_for(container: str, taken_ids: set[str]) -> str:
    """Derive a list-unique id for an extra root from its container path.

    Args:
        container: The in-container mount point (unique within a launch).
        taken_ids: Ids already claimed by earlier roots (always contains
            ``"project"``).

    Returns:
        The id for the new extra root; the caller adds it to ``taken_ids``.
        The base id strips the leading ``/`` and maps every remaining ``/``
        to ``-`` (``/home/goga/data`` → ``home-goga-data``; the degenerate
        mount point ``/`` maps to ``"root"``). On collision — the reserved
        ``"project"`` id or an id already taken by an earlier root — the id
        is suffixed with ``-`` plus the first 8 hex characters of the
        sha256 of the EXACT container path, so distinct container paths
        never collide in the list.
    """
    base = container.lstrip("/").replace("/", "-") or "root"
    if base == "project" or base in taken_ids:
        suffix = hashlib.sha256(container.encode("utf-8")).hexdigest()[:8]
        return f"{base}-{suffix}"
    return base


def collect_file_roots(tokens: list[str]) -> list[FileRoot]:
    """Compose the ordered file-manager roots of a launch.

    Args:
        tokens: The ``home.docker.run`` token list, consumed verbatim —
            already shell-tokenized at config load (``home-configuration``);
            never re-split, re-quoted, or validated here.

    Returns:
        The roots list: the project root (``/workspace``) first, then one
        extra root per surviving directory mount in declaration order. A
        mount survives only when its host side contains ``/`` (named
        volumes and the ambiguous Windows ``C:`` prefix do not) AND
        resolves to an existing host directory (``~``/``$VAR`` never
        expand — literal non-existent paths are skipped). Deduplicated by
        container path: a later declaration into an already-rooted path
        REPLACES the earlier record and its position — including when the
        later declaration yields no root (a named volume shadowing a
        bind), which removes the path's root entirely.

    Note:
        Deterministic and total: identical tokens produce an identical
        list (order, fields, and ids) on every call, and nothing is raised
        on any input. Engine mounts (the project bind-mount, the
        persistent afm state) never appear in the token stream, so they
        can never become roots.
    """
    project = FileRoot(
        id="project",
        label="project",
        container_path="/workspace",
        mount_read_only=False,
        kind="project",
    )
    roots: dict[str, FileRoot] = {}
    taken_ids = {"project"}
    i = 0

    while i < len(tokens):
        value, i = _next_volume_value(tokens, i)
        # An unrecognized token, a dangling flag at the end, or an empty value
        # (``-v ""`` / ``--volume=``) — skip without failing.
        if value is None or value == "":
            continue
        parsed = _parse_volume(value)
        if parsed is None:
            continue
        host, container, mode = parsed
        # A host side without "/" is a named volume (or the ambiguous Windows
        # drive-letter form); only existing host directories become roots.
        eligible = "/" in host and _host_is_dir(host)
        read_only = _mode_is_read_only(mode)
        # Supersede: a later declaration into a rooted path removes the earlier
        # record first — only the LAST declaration of a container path survives
        # (with its fields, re-inserted at the end of the order).
        roots.pop(container, None)
        if eligible:
            root_id = _root_id_for(container, taken_ids)
            roots[container] = FileRoot(
                id=root_id,
                label=container,
                container_path=container,
                mount_read_only=read_only,
                kind="extra",
            )
            taken_ids.add(root_id)

    return [project, *roots.values()]


def encode_file_roots(roots: list[FileRoot]) -> str:
    """Encode the roots list into the ``AFM_DOCKER_FILE_ROOTS`` value.

    Args:
        roots: The composed roots list (e.g. the ``collect_file_roots``
            output; the empty list is a valid degenerate payload).

    Returns:
        The single-line base64 value for the environment variable — never
        wrapped or split. Canonical form (fixed by the ``afm`` practice):
        a compact UTF-8 JSON payload — ``,``/``:`` separators without
        spaces, key order ``version``, ``roots``, and ``id``, ``label``,
        ``container_path``, ``mount_read_only``, ``kind`` inside each
        root, non-ASCII kept literal (``ensure_ascii=False``) — encoded as
        standard base64 with padding preserved; identical roots give the
        identical string, and nothing is raised.
    """
    payload = {
        "version": 1,
        "roots": [
            {
                "id": root.id,
                "label": root.label,
                "container_path": root.container_path,
                "mount_read_only": root.mount_read_only,
                "kind": root.kind,
            }
            for root in roots
        ],
    }
    compact = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    return base64.b64encode(compact.encode("utf-8")).decode("ascii")
