"""In-container materialization of the packaged goga dashboard skin."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# The fixed in-container skins directory the afm configuration's ``skin_dir``
# field points at — never under /workspace or the project directory. A module
# constant so the tests (and only they) can relocate it.
_SKIN_TARGET_BASE = Path("/home/goga/.afm/skins")

# The skin name — the dashboard theme goga writes (``theme: goga``) resolves
# to <base>/<name>/ inside the skins directory.
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

    The afm configuration points the engine at ``/home/goga/.afm/skins`` (the
    static ``skin_dir`` field of :func:`goga.pipeline.afm_config.write_afm_config`);
    this routine populates the ``goga`` entry of that directory from the
    installed goga package so the written ``theme: goga`` resolves from the
    user-side skins directory instead of the engine's built-in copy. Called by
    the run coordination on every launch, next to the configuration write.

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
