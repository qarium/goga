"""Compare primitives for the cell-level usages status domain.

Read-only helpers with a git boundary only on :func:`compute_dep_status`:

* :func:`hash_tree` builds a deterministic content-hash map of a directory tree.
* :func:`_diff_entries` classifies every node (file and directory) of the two
  hash maps into an :class:`EntryChange` verdict (``unchanged`` / ``modified``
  / ``added`` / ``removed``).
* :func:`compute_dep_status` rebuilds the expected usages tree from the remote and
  compares it to the synced target for one declared dep.

``hash_tree`` mirrors :func:`goga.usages.sync.deploy.deploy_usages`'s verbatim-copy
model: symlinks are hashed by their *readlink target string*, never by the content
they point at — dereferencing them would aggregate arbitrary local files, the same
local-file-disclosure class ``deploy_usages`` defends against. Symlinks that point
at directories are hashed the same way and are never descended into
(``os.walk(followlinks=False)``).
"""

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

    Iteration order is fixed (``os.walk`` with sorted ``dirnames``/``filenames``)
    so two structurally identical trees always produce identical maps. Each
    regular file is hashed by chunked ``sha256`` of its content (read in 64 KiB
    chunks, never loaded whole into memory); its key is its path relative to
    ``root`` in posix form. Symlinks — whether file- or dir-pointing — are hashed
    by ``sha256`` of their readlink target string and are *never* followed,
    matching ``deploy_usages``'s verbatim-copy model and defending local-file
    disclosure. A symlink that points at a directory lives in ``dirnames``
    (``followlinks=False``) and is hashed by readlink without descending.

    Args:
        root: Directory to hash (need not exist; a missing/empty dir yields ``{}``).

    Returns:
        Mapping of relative posix path to the hex ``sha256`` digest of the entry
        (content for regular files, readlink target string for symlinks).
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
    """Return the chunked ``sha256`` hex digest of a regular file's content."""
    digest = hashlib.sha256()
    with entry.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_readlink(entry: Path) -> str:
    """Return ``sha256`` of a symlink's readlink target string (never followed)."""
    return hashlib.sha256(str(entry.readlink()).encode("utf-8")).hexdigest()


def _aggregate_dir(changes: list[EntryChange]) -> EntryChange:
    """Fold a directory's per-file verdicts into one :class:`EntryChange`.

    Aggregation rules:

    * every file ``unchanged``  → ``unchanged``
    * every file ``added``      → ``added`` (the directory is remote-only)
    * every file ``removed``    → ``removed`` (the directory is local-only)
    * otherwise (mixed)         → ``modified``

    The fold is order-independent: only the *set* of member verdicts matters, so
    the iteration order of the member files does not affect the result.

    Args:
        changes: Verdicts of every file beneath the directory (non-empty).

    Returns:
        The single aggregated :class:`EntryChange` for the directory.
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

    Files are classified by membership and hash equality:

    * in both, equal   → ``unchanged``
    * in both, differ  → ``modified``
    * expected only    → ``added``
    * local only       → ``removed``

    Directories are derived from the ancestor prefixes of every file path and
    carry an aggregated verdict (:func:`_aggregate_dir`) over the files beneath
    them — so a remote-only folder rolls up to ``added`` rather than collapsing
    into ``out_of_date``. A directory that contains only matching files is
    ``unchanged``; a mix of verdicts is ``modified``.

    Args:
        expected: Hash map of the rebuilt (remote) tree.
        local: Hash map of the on-disk (synced) tree.

    Returns:
        A flat, path-sorted list of :class:`EntryStatus` covering every file and
        every directory touched by either tree.
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
    """Rebuild the expected usages tree from the remote and compare it to ``target``.

    Read-only with respect to ``target``: the remote is cloned into a first temp
    directory (``temp#1``) and its usages deployed into a *second* temp directory
    (``temp#2``) — never into the real ``.goga/usages/<group>/<dep>/``. Both rebuilt
    trees are hashed (:func:`hash_tree`) and compared: identical hash maps →
    ``up_to_date``, otherwise ``out_of_date``. Per-node entries (files and
    directories, each with its own verdict) are derived from the two maps via
    :func:`_diff_entries`.

    Both temp directories are removed in nested ``finally`` blocks — ``temp#2``
    (inner) then ``temp#1`` (outer) — so a clone, checkout, or deploy failure still
    cleans up everything before the exception propagates. ``clone_repository`` is
    invoked *before* the outer ``try`` and self-cleans ``temp#1`` on its own
    failure, so ``repo`` is always bound when the outer ``finally`` runs (an
    ``UnboundLocalError`` here would mask the original clone failure).

    Args:
        group: Group name of the dep.
        dep: Dep name.
        depcfg: Declared git dependency (URL/ref/root).
        target: On-disk synced tree to compare against
            (``.goga/usages/<group>/<dep>``).

    Returns:
        ``DepStatus`` with state ``up_to_date`` or ``out_of_date`` and the per-node
        entry diff.

    Raises:
        Propagates any clone/checkout/deploy error (the caller owns best-effort
        handling); both temp directories are cleaned first.
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
