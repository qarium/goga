"""Config-driven synchronization of cell-level usages from git dependencies."""

import logging
import shutil
from pathlib import Path

from ..config import load_project_config
from .clean import clean_usages_dir
from .clone import clone_repository
from .deploy import deploy_usages

logger = logging.getLogger(__name__)


def sync(force: bool = False) -> int:
    """Synchronize declared cell-level usages into ``.goga/usages``.

    Loads project config and, for each declared ``<group>/<dep>`` git dependency,
    clones the repository and deploys its cell-level usages into
    ``.goga/usages/<group>/<dep>/``. Failures are best-effort: a single dep's
    error does not abort the rest and is reflected only in the exit code; config
    load errors propagate fail-loud at the boundary.

    Args:
        force: True clears ``.goga/usages/`` (except ``cooks`` and root files)
            via ``clean_usages_dir`` and re-syncs every dep; False (default) is
            incremental — deps whose target dir already exists are skipped.

    Returns:
        exit_code: ``0`` on success (including "nothing to sync" when the
        ``usages`` section is absent), ``1`` if any dep failed to sync.

    Raises:
        FileNotFoundError, KeyError, ValueError, yaml.YAMLError: propagated
            fail-loud from ``load_project_config`` at the config boundary.
    """
    config = load_project_config()

    if config.usages is None:
        return 0

    usages_root = Path(".goga/usages")

    if force:
        clean_usages_dir(usages_root)

    exit_code = 0
    for group, deps in config.usages.items():
        for dep, depcfg in deps.items():
            target = usages_root / group / dep
            if (not force) and target.exists():
                continue

            repo: Path | None = None
            try:
                repo = clone_repository(depcfg.git, depcfg.ref)
                deploy_usages(repo, target)
            except Exception:
                logger.error(
                    "usages sync failed",
                    extra={"group": group, "dep": dep},
                )
                exit_code = 1
                continue
            finally:
                if repo is not None:
                    shutil.rmtree(repo, ignore_errors=True)

    return exit_code
