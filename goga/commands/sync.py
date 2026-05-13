from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import click


def _is_git_url(source: str) -> bool:
    if source.startswith("http://"):
        return True
    if source.startswith("https://"):
        return True
    if source.startswith("git@"):
        return True
    return bool(source.startswith("ssh://"))


def _extract_dep_name(source: str) -> str:
    if source.startswith("git@"):
        try:
            path_part = source.split(":")[1].rstrip("/")
        except IndexError:
            raise ValueError(f"Cannot extract dependency name from: {source}") from None
        name = path_part.split("/")[-1]
        name = name.removesuffix(".git")
    else:
        path_part = urlparse(source).path
        name = path_part.rstrip("/").split("/")[-1]
        name = name.removesuffix(".git")
    if not name or name == "." or ".." in name.split("/"):
        raise ValueError(f"Cannot extract dependency name from: {source}")
    return name


def _prepare_clone_url(source: str, token: str | None) -> str:
    if token is not None and source.startswith("https://"):
        parsed = urlparse(source)
        host = parsed.netloc.rsplit("@", 1)[-1]
        new_netloc = f"{token}@{host}"
        return urlunparse(parsed._replace(netloc=new_netloc))
    return source


def _find_usages_dirs(root: Path) -> list[Path]:
    result: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".hg", ".svn")]
        if ".usages" in dirnames:
            result.append(Path(dirpath) / ".usages")
            dirnames.remove(".usages")
    return result


def _sync_usages(source: Path, dep_name: str, usages_dirs: list[Path]) -> int:
    target = Path(".goga/usages/deps") / dep_name
    shutil.rmtree(target, ignore_errors=True)
    for usages_dir in usages_dirs:
        rel = usages_dir.parent.relative_to(source)
        dest = target / rel / ".usages"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(usages_dir, dest, dirs_exist_ok=True)
    return len(usages_dirs)


def _sync_from_git(
    ctx: click.Context,
    source: str,
    token: str | None,
    branch: str | None,
) -> None:
    try:
        dep_name = _extract_dep_name(source)
    except ValueError as e:
        click.echo(str(e), err=True)
        ctx.exit(1)

    clone_url = _prepare_clone_url(source, token)
    tmp_dir: Path | None = None
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        clone_cmd = ["git", "clone"]
        if branch is not None:
            clone_cmd.extend(["--branch", branch])
        clone_cmd.extend([clone_url, str(tmp_dir)])
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            subprocess.run(clone_cmd, capture_output=True, check=True, env=env)
        except FileNotFoundError:
            click.echo("git is not installed or not in PATH", err=True)
            ctx.exit(1)
        except subprocess.CalledProcessError as e:
            raw = e.stderr.decode() if e.stderr else str(e)
            if token is not None:
                raw = raw.replace(token, "<TOKEN>")
            click.echo(raw, err=True)
            ctx.exit(1)

        usages_dirs = _find_usages_dirs(tmp_dir)
        if not usages_dirs:
            click.echo("No .usages/ found in repository", err=True)
            ctx.exit(1)

        count = _sync_usages(tmp_dir, dep_name, usages_dirs)
        click.echo(f"Synced {dep_name} from {source} ({count} usages)")
        ctx.exit(0)
    except OSError as e:
        click.echo(f"Sync failed: {e}", err=True)
        ctx.exit(1)
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _sync_from_local(ctx: click.Context, source: str) -> None:
    source_path = Path(source).resolve()
    if not source_path.is_dir():
        click.echo(f"Path does not exist or is not a directory: {source_path}", err=True)
        ctx.exit(1)

    usages_dirs = _find_usages_dirs(source_path)
    if not usages_dirs:
        click.echo(f"No .usages/ found in {source_path}", err=True)
        ctx.exit(1)

    dep_name = source_path.name
    if not dep_name:
        click.echo("Cannot extract dependency name from path", err=True)
        ctx.exit(1)
    try:
        count = _sync_usages(source_path, dep_name, usages_dirs)
        click.echo(f"Synced {dep_name} from {source_path} ({count} usages)")
        ctx.exit(0)
    except OSError as e:
        click.echo(f"Sync failed: {e}", err=True)
        ctx.exit(1)


@click.command()
@click.argument("source")
@click.option("--token", default=None, help="Token for private repository authentication")
@click.option("--branch", default=None, help="Branch to clone")
@click.pass_context
def sync(
    ctx: click.Context,
    source: str,
    token: str | None,
    branch: str | None,
) -> None:
    """Synchronize .usages/ from a local path or git repository into .goga/usages/deps/<dep_name>/."""
    if _is_git_url(source):
        _sync_from_git(ctx, source, token, branch)
    else:
        _sync_from_local(ctx, source)
