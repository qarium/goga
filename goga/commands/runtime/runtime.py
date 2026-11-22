"""The ``goga runtime`` command group — the CLI surface of the runtime state."""

from __future__ import annotations

from dataclasses import dataclass

import click

from ...docker import is_in_docker
from .archive import package_runtime_archive, resolve_archive_destination
from .targets import (
    resolve_build_target_dir,
    resolve_effective_branch,
    resolve_pipeline_target_dir,
    sanitize_pipeline_name,
)

_HOST_ONLY_MESSAGE = (
    "goga runtime is a host-side command — the runtime state does not live "
    "inside the goga image; run it on the host where the runs happened"
)


@dataclass(kw_only=True)
class _RuntimeScope:
    """The branch scope shared by every subcommand of the group."""

    branch: str | None = None


@click.group()
@click.option(
    "--branch",
    "-b",
    default=None,
    help="Branch segment replacing the git-derived one, applied to every "
    "subcommand (placed before the subcommand token; an empty value means "
    "not given; the literal '.' and '..' are refused)",
)
@click.pass_context
def runtime(ctx: click.Context, branch: str | None = None) -> None:
    """Query and archive the host-side runtime state of the current project.

    build prints the build artifacts directory, pipeline NAME the named
    pipeline's artifacts directory — each exactly one stdout line and
    nothing else, for scripting: dir=$(goga runtime build). archive
    packages exactly one target into a single wrapper-rooted .tar.gz and
    prints the created archive's path. Every subcommand is host-side only.

    The short alias -b carries two meanings at two parse positions: before
    the subcommand token it is this group's --branch option; after the
    archive token it is the archive subcommand's --build flag. The two
    positions never collide during parsing.

    The branch value is slugified and trusted — no git consultation — with
    one refusal: the literal "." and ".." cannot form a single
    filesystem-safe path component (no git branch can carry them either),
    and composed into the location they would silently escape the
    project/branch scope — for archive, packaging a wider tree than the
    one target.
    """
    if branch in {".", ".."}:
        raise click.ClickException(f"invalid branch name {branch!r}")

    ctx.ensure_object(_RuntimeScope)
    ctx.obj.branch = branch


@runtime.command("build")
@click.pass_obj
def build(scope: _RuntimeScope) -> None:
    """Print the build artifacts directory of the current project and branch — and nothing else.

    The directory the build run uses, resolved from the current working
    directory and the effective branch (the group's -b/--branch, else the
    current git branch). The path is printed even when the directory does
    not exist yet; nothing is created, modified, or deleted on disk. The
    path and only the path — exactly one stdout line.
    """
    if is_in_docker():
        raise click.ClickException(_HOST_ONLY_MESSAGE)

    segment = resolve_effective_branch(scope.branch)
    target_dir = resolve_build_target_dir(segment)
    click.echo(target_dir)


@runtime.command("pipeline")
@click.argument("name")
@click.pass_obj
def pipeline(scope: _RuntimeScope, name: str) -> None:
    """Print the named pipeline's artifacts directory — and nothing else.

    NAME is the pipeline name as used at run time, sanitized exactly as
    the run composes its state segment (":" becomes "-"), so the printed
    path is the directory the run actually uses. The path is printed even
    when the directory does not exist yet; nothing is created on disk. A
    name starting with "-" is passed after -- (goga runtime pipeline --
    NAME); an empty name or the literal "."/".." is a clean error — neither
    addresses one pipeline's artifacts. The path and only the path —
    exactly one stdout line.
    """
    if is_in_docker():
        raise click.ClickException(_HOST_ONLY_MESSAGE)

    # "." and ".." compose into the branch-/project-level directory, not
    # one pipeline's artifacts — the same addressability refusal as "".
    if name == "" or name.startswith("-") or name in {".", ".."}:
        raise click.ClickException(f"invalid pipeline name {name!r}")

    segment = resolve_effective_branch(scope.branch)
    target_dir = resolve_pipeline_target_dir(name, segment)
    click.echo(target_dir)


@runtime.command("archive")
@click.option(
    "-b",
    "--build",
    "build",
    is_flag=True,
    default=False,
    help="Select the build artifacts directory as the target.",
)
@click.option(
    "-p",
    "--pipeline",
    "pipeline",
    default=None,
    help="Select the named pipeline's artifacts directory as the target.",
)
@click.option(
    "-o",
    "--output",
    "output",
    default=None,
    help="Write the archive to this path instead of the default name in the current directory.",
)
@click.pass_obj
def archive(
    scope: _RuntimeScope,
    build: bool = False,
    pipeline: str | None = None,
    output: str | None = None,
) -> None:
    """Package exactly one runtime target into a .tar.gz and print its path.

    -b/--build selects the build artifacts directory, -p/--pipeline NAME
    the named pipeline's — exactly one of them per invocation. The archive
    holds the target's full recursive contents under the single wrapper
    root goga-runtime-<target>-<branch> and opens with standard tools.
    The default name lands in the current directory; -o/--output chooses
    another path (an existing file there is overwritten — the flag is the
    overwrite decision). The packaged state itself is never modified. The
    created archive's absolute path — exactly one stdout line.
    """
    if is_in_docker():
        raise click.ClickException(_HOST_ONLY_MESSAGE)

    if build == (pipeline is not None):
        raise click.ClickException("exactly one target is required: -b/--build or -p/--pipeline NAME")

    # Beyond the empty/dash guards: "." and ".." would package the branch-
    # or project-level directory (a whole-branch/project sweep, not one
    # target), and a "/" survives the colon sanitization into the archive
    # stem and wrapper root — both must be a single directory name.
    if pipeline is not None and (
        pipeline == "" or pipeline.startswith("-") or pipeline in {".", ".."} or "/" in pipeline
    ):
        raise click.ClickException(f"invalid pipeline name {pipeline!r}")

    segment = resolve_effective_branch(scope.branch)

    if build:
        target_dir = resolve_build_target_dir(segment)
        label = "build"
    else:
        target_dir = resolve_pipeline_target_dir(pipeline, segment)
        label = sanitize_pipeline_name(pipeline)

    if not target_dir.is_dir():
        raise click.ClickException(f"target directory does not exist: {target_dir}")

    stem = f"goga-runtime-{label}-{segment}"
    destination = resolve_archive_destination(stem, output)

    try:
        archive_path = package_runtime_archive(target_dir, wrapper_root=stem, destination=destination)
    except OSError as exc:
        raise click.ClickException(f"cannot write archive to {destination}") from exc

    click.echo(archive_path)
