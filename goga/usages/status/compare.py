"""Compare primitives for the cell-level usages status domain.

Read-only helpers with a git boundary only on :func:`compute_dep_status`:

* :func:`hash_tree` builds a deterministic content-hash map of a directory tree.
* :func:`_rollup_folders` collapses two hash maps into per-folder statuses.
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
from .models import DepStatus, FolderStatus, UsageState

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


def _rollup_folders(
    expected: dict[str, str], local: dict[str, str]
) -> list[FolderStatus]:
    """Collapse two ``hash_tree`` maps into per-folder :class:`FolderStatus`.

    Each hash-map key's immediate-parent folder becomes one entry. The roll-up
    is *sticky*: a folder that has any differing, missing, or extra file is
    permanently ``out_of_date`` — a later matching file in the same folder never
    rolls it back, because the ``out_of_date`` assignment dominates the
    ``up_to_date`` :func:`setdefault`. That dominance makes the fold order-
    independent, so the iteration order of ``expected.keys() | local.keys()`` does
    not affect the result. The returned list is sorted by folder path.

    Args:
        expected: Hash map of the rebuilt (remote) tree.
        local: Hash map of the on-disk (synced) tree.

    Returns:
        A list of :class:`FolderStatus` sorted by path, one per folder touched by
        either tree; ``""`` is the root-level folder.
    """
    folders: dict[str, UsageState] = {}
    for key in expected.keys() | local.keys():
        parent = Path(key).parent
        folder = "" if str(parent) == "." else str(parent)
        ok = key in expected and key in local and expected[key] == local[key]
        if not ok:
            folders[folder] = UsageState.out_of_date
        else:
            folders.setdefault(folder, UsageState.up_to_date)
    return sorted(
        (FolderStatus(path=path, state=state) for path, state in folders.items()),
        key=lambda fs: fs.path,
    )


def compute_dep_status(group: str, dep: str, depcfg: DepConfig, target: Path) -> DepStatus:
    """Rebuild the expected usages tree from the remote and compare it to ``target``.

    Read-only with respect to ``target``: the remote is cloned into a first temp
    directory (``temp#1``) and its usages deployed into a *second* temp directory
    (``temp#2``) — never into the real ``.goga/usages/<group>/<dep>/``. Both rebuilt
    trees are hashed (:func:`hash_tree`) and compared: identical hash maps →
    ``up_to_date``, otherwise ``out_of_date``. Per-folder statuses are rolled up
    from the two maps.

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
        ``DepStatus`` with state ``up_to_date`` or ``out_of_date`` and the rolled-up
        per-folder statuses.

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
            state = (
                UsageState.up_to_date
                if expected_hashes == local_hashes
                else UsageState.out_of_date
            )
            folders = _rollup_folders(expected_hashes, local_hashes)
            return DepStatus(group=group, dep=dep, state=state, folders=folders)
        finally:
            shutil.rmtree(expected, ignore_errors=True)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
