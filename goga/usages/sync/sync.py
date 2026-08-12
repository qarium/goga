"""Config-driven synchronization of cell-level usages from git dependencies."""

import logging
import shutil
from pathlib import Path

from ...config import load_project_config
from .clean import clean_usages_dir
from .clone import clone_repository
from .deploy import deploy_usages

logger = logging.getLogger(__name__)


def sync(force: bool = False, group: str | None = None, dep: str | None = None) -> int:
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
        group: When set, only sync deps under this group; non-matching groups
            are skipped (never an error). ``None`` (default) syncs all groups.
        dep: When set, only sync deps with this name; non-matching deps are
            skipped (never an error). ``dep`` without ``group`` applies across
            every group. ``None`` (default) syncs all deps.

    Returns:
        exit_code: ``0`` on success (including "nothing to sync" when the
        ``usages`` section is absent or no dep matches the filters), ``1`` if
        any dep failed to sync.

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
    for group_name, deps in config.usages.items():
        if group is not None and group_name != group:
            continue
        for dep_name, depcfg in deps.items():
            if dep is not None and dep_name != dep:
                continue
            target = usages_root / group_name / dep_name
            if (not force) and target.exists():
                continue

            repo: Path | None = None
            try:
                repo = clone_repository(depcfg.git, depcfg.ref)
                deploy_usages(repo, target, depcfg.root)
            except Exception:
                # Log without the raw exception: a clone failure raises
                # ``subprocess.CalledProcessError`` whose ``str()`` embeds the
                # full git URL, which may contain embedded credentials (e.g.
                # ``https://<token>@host/...``). Its ``stderr`` would be safe,
                # but the exception text/traceback is not, so we omit it.
                # Use the loop variables (group_name/dep_name), NOT the filter
                # params (group/dep) — logging the filters would report the
                # filter (or ``None``), not the failing dep.
                logger.error(
                    "usages sync failed for %s/%s",
                    group_name,
                    dep_name,
                    extra={"group": group_name, "dep": dep_name},
                )
                exit_code = 1
                continue
            finally:
                if repo is not None:
                    shutil.rmtree(repo, ignore_errors=True)

    return exit_code
