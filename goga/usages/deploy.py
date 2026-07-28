"""Deploy cell-level usages from a cloned repo into a target directory."""

import os
import shutil
from pathlib import Path

_VCS_DIRS = (".git", ".hg", ".svn")


def deploy_usages(source_repo: Path, target_dir: Path, root: str | None = None) -> int:
    """Discover ``.usages`` folders under ``source_repo`` and deploy their contents.

    Used by ``sync`` to copy cell-level usages out of a freshly cloned repository
    into ``.goga/usages/<group>/<dep>/``. The walk origin is ``source_repo`` when
    ``root`` is None, otherwise ``source_repo/root``. Discovery skips VCS
    directories (``.git``/``.hg``/``.svn``).

    Each discovered ``.usages`` is copied deterministically into
    ``target_dir``/<rel>/ where ``<rel>`` is the ``.usages`` parent path relative
    to the walk origin, with the ``.usages`` segment dropped from every
    destination path. A ``.usages`` directly in the origin copies into the
    ``target_dir`` root (empty ``<rel>``); non-cell intermediate directories are
    preserved.

    There is NO smoothing: a single ``.usages`` is NOT flattened into the target
    root — it lands at its origin-relative path (root only when directly in the
    origin). This is a deliberate breaking change from the previous single-
    ``.usages``-flattens rule.

    When ``root`` is given but the resolved origin is missing or not a directory,
    this raises rather than silently returning ``0`` — walking a missing path or
    a file yields no ``.usages``, which is treated as a misconfiguration rather
    than an empty deploy. The origin is verified BEFORE ``target_dir`` is created,
    so a bad ``root`` leaves no half-created target behind. The target is also
    NOT deleted beforehand (``sync`` owns the incremental skip and
    ``clean_usages_dir`` owns destructive removal).

    Symlinks inside a ``.usages`` directory are copied verbatim
    (``symlinks=True``): the source is a freshly cloned third-party repository,
    and dereferencing its symlinks (``copytree``'s default) would copy the
    *contents* of arbitrary local files/dirs the links point at into the synced
    output — a local-file-disclosure / aggregation vector from untrusted remote
    content. Copying the links themselves never reads those targets.

    The same disclosure class is defended at the *origin* boundary too:
    ``os.walk`` always resolves its top, so a symlink placed at the declared
    ``root`` (or an absolute ``root`` from a loader-bypassing caller) that points
    outside the clone would be followed into host-local directories and its
    ``.usages`` aggregated. Any origin that resolves outside the clone is
    rejected before the walk.

    Args:
        source_repo: Path to the cloned repository root.
        target_dir: Destination directory (created if missing).
        root: Optional subpath of ``source_repo`` to walk from instead of the
            repo root (None → walk from the clone root). Already structurally
            validated by the config loader (no absolute / UNC / ``..`` forms);
            resolving it to an existing directory inside the clone is this
            function's responsibility.

    Returns:
        The number of ``.usages`` folders deployed (``0`` when none are found).

    Raises:
        FileNotFoundError: When ``root`` is given but the resolved origin does
            not exist under ``source_repo``.
        NotADirectoryError: When the resolved origin exists but is not a
            directory (e.g. a regular file).
        ValueError: When the resolved origin lies outside the cloned repository
            (e.g. a symlink at ``root`` pointing out of the clone, or an
            absolute ``root`` string) — an untrusted-clone disclosure guard.
    """
    # 1. resolve the walk origin relative to the clone, verifying it BEFORE the
    #    target is touched (a missing/file root raises instead of silently
    #    deploying nothing). The origin is then checked for clone containment:
    #    os.walk resolves its top, so a symlink/absolute root that escapes the
    #    untrusted clone would walk host-local dirs. Resolve the clone root once
    #    and reject any origin that does not stay inside it.
    clone_root = source_repo.resolve(strict=True)
    origin = clone_root if root is None else clone_root / root
    if not origin.exists():
        raise FileNotFoundError(f"usages root {root!r} not found in {source_repo}")
    if not origin.is_dir():
        raise NotADirectoryError(f"usages root {root!r} in {source_repo} is not a directory")
    if not origin.resolve(strict=True).is_relative_to(clone_root):
        raise ValueError(f"usages root {root!r} escapes the cloned repository {source_repo}")

    # 2. discover every .usages directory, skipping VCS dirs.
    found: list[tuple[str, Path]] = []
    for dirpath, dirnames, _ in os.walk(origin):
        dirnames[:] = [d for d in dirnames if d not in _VCS_DIRS]

        if ".usages" in dirnames:
            usages_dir = Path(dirpath) / ".usages"
            rel = str(Path(dirpath).relative_to(origin))
            if rel == ".":  # normalize origin-root rel to ""
                rel = ""
            found.append((rel, usages_dir))
            dirnames.remove(".usages")  # do not descend into .usages

    # 3. ensure the target exists.
    target_dir.mkdir(parents=True, exist_ok=True)

    # 4. copy each .usages to its origin-relative destination (NO smoothing).
    for rel, usages_dir in found:
        dest = target_dir if rel == "" else target_dir / rel
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(usages_dir, dest, dirs_exist_ok=True, symlinks=True)  # preserve hierarchy

    # 5. return the number of deployed .usages folders.
    return len(found)
