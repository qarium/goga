"""Deploy cell-level usages from a cloned repo into a target directory."""

import os
import shutil
from pathlib import Path

_VCS_DIRS = (".git", ".hg", ".svn")


def deploy_usages(source_repo: Path, target_dir: Path, root: str | None = None) -> int:
    """Discover ``.usages`` folders under ``source_repo`` and deploy them at their origin-relative paths.

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
        ValueError: When the resolved origin, or any discovered ``.usages``
            source, lies outside the cloned repository (e.g. a symlink at
            ``root`` pointing out of the clone, an absolute ``root`` string, or
            a ``.usages`` symlink to a host directory) — an untrusted-clone
            disclosure guard.
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
            # os.walk(followlinks=False) does not descend into symlinked dirs,
            # but it DOES list a symlink-to-dir named ".usages" here — and
            # copytree follows the symlink at its top src (symlinks=True only
            # governs links INSIDE the copied tree). Resolve each source and
            # reject any that escape the clone, closing the same disclosure
            # vector the origin check above defends: a ".usages" symlink to an
            # out-of-clone host directory would otherwise have its contents
            # copied verbatim into the sync output.
            if not usages_dir.resolve(strict=True).is_relative_to(clone_root):
                raise ValueError(f"usages source {usages_dir} escapes the cloned repository {source_repo}")
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
