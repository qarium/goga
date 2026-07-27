"""Deploy cell-level usages from a cloned repo into a target directory."""

import os
import shutil
from pathlib import Path

_VCS_DIRS = (".git", ".hg", ".svn")


def deploy_usages(source_repo: Path, target_dir: Path) -> int:
    """Discover ``.usages`` folders under ``source_repo`` and deploy their contents.

    Used by ``sync`` to copy cell-level usages out of a freshly cloned repository
    into ``.goga/usages/<group>/<dep>/``. Discovery skips VCS directories
    (``.git``/``.hg``/``.svn``). The smoothing rule decides placement:

    - exactly one ``.usages`` → its contents flatten directly into ``target_dir``;
    - multiple ``.usages`` → each one's contents are copied into
      ``target_dir``/<rel>/ where ``<rel>`` is the parent's path relative to the
      repo root (an empty ``<rel>`` means the repo-root ``.usages`` flattens into
      ``target_dir``). Non-cell intermediate directories are preserved, and the
      ``.usages`` segment itself is dropped from every destination path.

    The target is NOT deleted beforehand (``sync`` owns the incremental skip and
    ``clean_usages_dir`` owns destructive removal).

    Args:
        source_repo: Path to the cloned repository root.
        target_dir: Destination directory (created if missing).

    Returns:
        The number of ``.usages`` folders deployed (``0`` when none are found).
    """
    # 1. discover every .usages directory, skipping VCS dirs.
    found: list[tuple[str, Path]] = []
    for dirpath, dirnames, _ in os.walk(source_repo):
        dirnames[:] = [d for d in dirnames if d not in _VCS_DIRS]

        if ".usages" in dirnames:
            usages_dir = Path(dirpath) / ".usages"
            rel = str(Path(dirpath).relative_to(source_repo))
            if rel == ".":  # normalize repo-root rel to ""
                rel = ""
            found.append((rel, usages_dir))
            dirnames.remove(".usages")  # do not descend into .usages

    # 2. ensure the target exists.
    target_dir.mkdir(parents=True, exist_ok=True)

    # 3. apply the smoothing rule.
    count = 0
    if len(found) == 1:
        _, usages_dir = found[0]
        shutil.copytree(usages_dir, target_dir, dirs_exist_ok=True)  # flatten to dep root
        count = 1
    else:
        for rel, usages_dir in found:
            dest = target_dir if rel == "" else target_dir / Path(rel)
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(usages_dir, dest, dirs_exist_ok=True)  # preserve hierarchy
            count += 1

    # 4. return the number of deployed .usages folders.
    return count
