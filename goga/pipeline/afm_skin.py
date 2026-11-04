"""In-container materialization of the packaged goga dashboard skin."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# The fixed in-container skins base directory — the PARENT of the directory
# the afm configuration's ``skin_dir`` field points at. Never under /workspace
# or the project directory. A module constant so the tests (and only they) can
# relocate it.
_SKIN_TARGET_BASE = Path("/home/goga/.afm/skins")

# The skin directory name — the materialized ``<base>/<name>`` directory is
# what the afm configuration's ``skin_dir`` points at; afm serves it wholesale
# as the active skin while it holds ``index.css`` (``theme`` only names an
# engine-builtin fallback, it never resolves inside this directory).
_SKIN_NAME = "goga"


def _resolve_packaged_skin_dir() -> Path:
    """Resolve the in-package directory holding the goga dashboard skin files.

    Returns:
        The package-data directory ``goga/assets/afm/skin/``, resolved
        relative to this module so it holds in an installed image regardless
        of ``CWD``/``AFM_DIR``.
    """
    return Path(__file__).resolve().parent.parent / "assets" / "afm" / "skin"


def materialize_afm_skin() -> Path:
    """Materialize the packaged goga dashboard skin into the afm skins directory.

    The afm configuration points the engine's ``skin_dir`` at
    ``/home/goga/.afm/skins/goga`` (the static field of
    :func:`goga.pipeline.afm_config.write_afm_config`); afm serves that
    directory wholesale as the active dashboard skin when it holds an
    ``index.css``. This routine repopulates it from the installed goga
    package on every launch, so the dashboard shows the packaged skin
    instead of the engine's built-in one.

    Returns:
        The materialized skin directory
        (``/home/goga/.afm/skins/goga``) — the flat copy of the packaged skin
        files.

    Raises:
        ValueError: When the packaged skin directory is missing from the
            installed package or holds no regular file — raised BEFORE the
            target directory is touched, so no partial skin remains on disk.
        OSError: When the skins directory cannot be created or written —
            propagates unchanged (the caller returns before any run event
            fires).
    """
    source = _resolve_packaged_skin_dir()

    # Validate everything before touching the target — the prompts
    # materialization atomicity rule: a missing or empty package skin never
    # wipes a previously materialized skin.
    files = sorted(entry for entry in source.iterdir() if entry.is_file()) if source.is_dir() else []

    if not files:
        raise ValueError(
            f"the packaged goga skin is missing or empty: no files at {source} "
            "(the installed goga package is damaged — rebuild the image)"
        )

    target = _SKIN_TARGET_BASE / _SKIN_NAME

    _SKIN_TARGET_BASE.mkdir(parents=True, exist_ok=True)

    # Reset the skin entry — the whole file set is regenerated per launch so a
    # removed packaged file never lingers as a stale dashboard artifact.
    if target.exists():
        shutil.rmtree(target)

    target.mkdir(parents=True)

    for entry in files:
        shutil.copyfile(entry, target / entry.name)

    logger.info("materialized afm skin", extra={"skin": _SKIN_NAME, "files": len(files)})

    return target
