"""Archive destination resolution and packaging for the goga runtime command cell."""

from __future__ import annotations

import tarfile
from pathlib import Path

import click


def resolve_archive_destination(archive_stem: str, output: str | None = None) -> Path:
    """Resolve the archive destination path under strict destination semantics.

    Args:
        archive_stem: The archive stem — the base of the default filename.
        output: The -o/--output value; None means the default.

    Returns:
        The absolute path the archive is written to: without ``output``, the
        deterministic ``<cwd>/<archive_stem>.tar.gz`` default; with it, the
        explicit override resolved against the current working directory
        (an existing file there expresses the intent to overwrite). Nothing
        is written or created — this routine resolves and validates only;
        the unwritable-destination failure surfaces at the packaging step.

    Raises:
        click.ClickException: The default name is already taken by an
            existing file or symlink (the error names the path and points
            to -o/--output), or the explicit output is an existing
            directory or lives under a missing parent directory — no
            implicit creation.
    """
    if output is None:
        destination = Path.cwd() / f"{archive_stem}.tar.gz"

        # is_symlink catches a dangling link too — exists() follows the
        # link target, and the packaging open would write through it.
        if destination.exists() or destination.is_symlink():
            raise click.ClickException(
                f"archive destination already exists: {destination} — pass -o/--output to choose another"
            )

        return destination

    path = Path(output)
    destination = path if path.is_absolute() else Path.cwd() / path

    if destination.is_dir():
        raise click.ClickException(f"archive destination is a directory: {destination}")

    if not destination.parent.is_dir():
        raise click.ClickException(f"archive destination parent directory does not exist: {destination.parent}")

    return destination


def package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> Path:
    """Package the full recursive contents of the target directory into one archive.

    Args:
        target_dir: The target directory — guaranteed by the caller to exist.
        wrapper_root: The single root directory name holding the whole tree
            inside the archive.
        destination: The resolved destination path — validated by the caller.

    Returns:
        The path of the created archive — the file exists there on success.
        The source directory is read only; the failure cleanup removes only
        an archive file this routine created (unlink only after a
        successful open — a failure before the destination is opened leaves
        any pre-existing file at the destination untouched).

    Raises:
        OSError: The destination is unwritable (raised at open, before any
            data is written) or any packaging-time failure after a partial
            file was created — the command layer wraps both into a clean
            error.
    """
    opened = False

    try:
        with tarfile.open(destination, "w:gz") as tar:
            opened = True
            tar.add(target_dir, arcname=wrapper_root)
    except BaseException:
        if opened:
            destination.unlink(missing_ok=True)

        raise

    return destination
