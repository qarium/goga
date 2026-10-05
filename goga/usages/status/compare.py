"""Compare primitives for the cell-level usages status domain."""

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from ...config import DepConfig
from ..sync.clone import clone_repository
from ..sync.deploy import deploy_usages
from .models import DepStatus, EntryChange, EntryKind, EntryStatus, UsageState

_READ_CHUNK = 65536


def hash_tree(root: Path) -> dict[str, str]:
    """Walk ``root`` deterministically and return a relative-path -> sha256 map.

    Args:
        root: Directory to hash (need not exist; a missing/empty dir yields ``{}``).

    Returns:
        Mapping of relative posix path to the hex ``sha256`` digest of the entry — content for
        regular files, readlink target string for symlinks (never followed or descended into).
    """
    hashes: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            entry = Path(dirpath) / name
            rel = entry.relative_to(root).as_posix()
            if entry.is_symlink():
                hashes[rel] = _hash_readlink(entry)
            else:
                hashes[rel] = _hash_file(entry)
        for name in dirnames:
            entry = Path(dirpath) / name
            if entry.is_symlink():
                hashes[entry.relative_to(root).as_posix()] = _hash_readlink(entry)

    return hashes


def _hash_file(entry: Path) -> str:
    """Return the chunked ``sha256`` hex digest of a regular file's content.

    Args:
        entry: The regular file to hash.

    Returns:
        The hex ``sha256`` digest of the file's bytes.
    """
    digest = hashlib.sha256()
    with entry.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _hash_readlink(entry: Path) -> str:
    """Return ``sha256`` of a symlink's readlink target string (never followed).

    Args:
        entry: The symlink entry to hash.

    Returns:
        The hex ``sha256`` digest of the readlink target string.
    """
    return hashlib.sha256(str(entry.readlink()).encode("utf-8")).hexdigest()


def _aggregate_dir(changes: list[EntryChange]) -> EntryChange:
    """Fold a directory's per-file verdicts into one :class:`EntryChange`.

    Args:
        changes: Verdicts of every file beneath the directory (non-empty).

    Returns:
        The single aggregated :class:`EntryChange` for the directory — all members ``unchanged``
        yields ``unchanged``, all ``added`` yields ``added``, all ``removed`` yields ``removed``,
        any mix yields ``modified``.
    """
    unique = set(changes)
    if unique == {EntryChange.added}:
        return EntryChange.added
    if unique == {EntryChange.removed}:
        return EntryChange.removed
    if unique == {EntryChange.unchanged}:
        return EntryChange.unchanged
    return EntryChange.modified


def _diff_entries(expected: dict[str, str], local: dict[str, str]) -> list[EntryStatus]:
    """Classify every node (file and directory) of ``expected | local`` into an entry.

    Args:
        expected: Hash map of the rebuilt (remote) tree.
        local: Hash map of the on-disk (synced) tree.

    Returns:
        A flat, path-sorted list of :class:`EntryStatus` covering every file and every directory
        touched by either tree. Files: in both and equal → ``unchanged``, in both and differing →
        ``modified``, expected-only → ``added``, local-only → ``removed``. Directories: derived
        from the ancestor prefixes of every file path, each with the aggregated verdict of the
        files beneath it.
    """
    # 1. file-level verdicts (every hash key is a leaf: regular file or symlink).
    file_change: dict[str, EntryChange] = {}
    for key in expected.keys() | local.keys():
        if key in expected and key in local:
            change = EntryChange.unchanged if expected[key] == local[key] else EntryChange.modified
        elif key in expected:
            change = EntryChange.added
        else:
            change = EntryChange.removed
        file_change[key] = change

    # 2. directory nodes: every ancestor prefix of a file path, with its member
    #    verdicts collected for aggregation.
    dir_members: dict[str, list[EntryChange]] = {}
    for key, change in file_change.items():
        parts = Path(key).parts
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            dir_members.setdefault(ancestor, []).append(change)

    entries: list[EntryStatus] = [
        EntryStatus(path=key, kind=EntryKind.file, change=change) for key, change in file_change.items()
    ]
    for path, members in dir_members.items():
        entries.append(EntryStatus(path=path, kind=EntryKind.dir, change=_aggregate_dir(members)))

    entries.sort(key=lambda entry: entry.path)
    return entries


def compute_dep_status(group: str, dep: str, depcfg: DepConfig, target: Path) -> DepStatus:
    """Rebuild the expected usages tree from the remote and compare it to ``target`` — read-only over ``target``.

    Args:
        group: Group name of the dep.
        dep: Dep name.
        depcfg: Declared git dependency (URL/ref/root).
        target: On-disk synced tree to compare against
            (``.goga/usages/<group>/<dep>``).

    Returns:
        ``DepStatus`` with state ``up_to_date`` when the two hash maps are identical, otherwise
        ``out_of_date``, and the per-node entry diff.

    Raises:
        Exception: Propagates any clone/checkout/deploy failure from
            ``clone_repository``/``deploy_usages`` (e.g.
            ``subprocess.CalledProcessError``, ``FileNotFoundError``,
            ``NotADirectoryError``, ``ValueError``); both temp directories are
            cleaned first. The caller owns best-effort handling.
    """
    repo = clone_repository(depcfg.git, depcfg.ref)  # temp#1, before the outer try
    try:
        expected = Path(tempfile.mkdtemp())  # temp#2
        try:
            deploy_usages(repo, expected, depcfg.root)

            expected_hashes = hash_tree(expected)
            local_hashes = hash_tree(target)

            state = UsageState.up_to_date if expected_hashes == local_hashes else UsageState.out_of_date
            entries = _diff_entries(expected_hashes, local_hashes)

            return DepStatus(group=group, dep=dep, state=state, entries=entries)
        finally:
            shutil.rmtree(expected, ignore_errors=True)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
