"""Host-side read-only docker launcher for the informational pipeline forms."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import click
import yaml

from ...config import HomeConfig, ProjectConfig, load_home_config
from ...docker import DockerRunner, docker_build_if_not_exist, docker_update
from .run_pipeline_container import _check_docker

logger = logging.getLogger(__name__)


def _compose_argv(
    name: str | None,
    info: bool,
    workflow: str | None,
    no_workflow: bool,
    skip: tuple[str, ...],
) -> list[str]:
    """Compose the in-container argv for the requested informational form.

    Args:
        name: Pipeline name for the card form; ``None`` for the listing forms.
        info: ``True`` for the overview and card forms; ``False`` for the flat
            list.
        workflow: Optional workflow name from the ``-w`` CLI flag.
        no_workflow: Flag from the ``--no-workflow`` CLI flag.
        skip: Stage names from the repeatable ``-s/--skip`` CLI flag — one
            ``-s`` argument per entry in the card argv; the listing forms
            deliberately do not represent skip.

    Returns:
        The post-image argv for ``docker run``. ``name is None`` addresses
        the listing subcommand (``-m goga.pipeline list``, plus ``--info``
        for the overview); a provided ``name`` addresses the card
        (``-m goga.pipeline run NAME --info``), which carries the workflow
        decision exactly as given — ``-w <workflow>`` when one is supplied,
        else ``--no-workflow`` when set, else nothing (the in-container
        auto-match applies) — followed by one ``-s <name>`` per skip entry;
        never resolved or validated here.
    """
    if name is None:
        argv = ["-m", "goga.pipeline", "list"]

        if info:
            argv += ["--info"]
        return argv

    argv = ["-m", "goga.pipeline", "run", name, "--info"]

    if workflow is not None:
        argv += ["-w", workflow]
    elif no_workflow:
        argv += ["--no-workflow"]

    for skip_name in skip:
        argv += ["-s", skip_name]

    return argv


def run_pipeline_info_container(  # noqa: PLR0913, PLR0917
    name: str | None,
    info: bool,
    config: ProjectConfig,
    hosts: dict[str, str],
    update: bool,
    workflow: str | None,
    no_workflow: bool,
    skip: tuple[str, ...] = (),
) -> int:
    """Launch the container in a minimal read-only shape for an informational form.

    Args:
        name: Pipeline name without extension for the card form; ``None`` for
            the listing forms.
        info: ``True`` for the overview and card forms; ``False`` for the flat
            list.
        config: Loaded project configuration (provides ``image`` and
            ``dockerfile``).
        hosts: Resolved host→IP mapping (from ``config.pipeline.hosts``);
            each entry becomes a docker ``--add-host HOST:IP`` flag.
        update: When True and ``info`` is False, refresh the image before the
            listing via ``docker_update``. Ignored in the overview and card
            forms.
        workflow: Optional workflow name forwarded to the card form as an
            explicit ``-w`` argument (file existence validated by the caller).
        no_workflow: When True, ``--no-workflow`` is forwarded to the card
            form (mutually exclusive with ``workflow``, enforced by the
            caller).
        skip: Stage names forwarded to the card form — one ``-s <name>``
            argument appended to the card argv per entry; the listing forms
            ignore ``skip`` entirely. Defaults to the empty tuple, which the
            listing dispatch (which passes no skip) relies on.

    Returns:
        The container's exit code.

    Raises:
        click.ClickException: When docker is missing, ``config.image`` is None,
            the home config file is malformed (a missing file is the normal
            no-op state), or a fatal image build is surfaced (D5).

    Note:
        The first-run safety net ``docker_build_if_not_exist`` runs
        unconditionally; the ``docker_update`` refresh runs only in the flat
        list (``info`` False). The launch is the minimal read-only shape:
        ``--rm``, a unique name, the project bind-mount as ``/workspace``
        (the working directory), one ``--add-host`` per host, and the
        ``python3`` entrypoint — no port publish, no env-file, no extra
        mounts, no credentials, and no caller-side signal handler (no
        secret files are written, so only the runner's built-in
        SIGTERM/SIGINT lifecycle applies). Nothing is written on the host —
        no tmpfile, no env-file, no cleanup.
    """
    if not _check_docker():
        raise click.ClickException("docker not found in PATH")

    if config.image is None:
        raise click.ClickException("image in .goga/config.yml is not set")

    # Home (machine-wide) config preamble — an empty HomeConfig when the file
    # is absent (no-op). home.env does NOT apply here (no env-file is ever
    # written); only home.docker.run reaches the docker run and home.docker.build
    # reaches image building. A malformed home file surfaces as a clean
    # ClickException (absence is normal).
    try:
        home: HomeConfig = load_home_config()
    except (ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    # In-container argv composition per the form (see _compose_argv): the card
    # form carries the workflow decision "as given" — explicit -w,
    # --no-workflow, or neither (in-container auto-match) — followed by one
    # -s per skip name.
    argv = _compose_argv(name, info, workflow, no_workflow, skip)

    container_name = f"goga-pipeline-{os.getpid()}"

    # First-run safety net: build the local image if it is absent and a project
    # Dockerfile is declared. No-op when the image exists or no Dockerfile is
    # set. Fatal build surfaces as ClickException (D5 — clean message + exit 1).
    # This module writes no secret files, so no caller-side handler applies.
    # home.docker.build is forwarded to image build (build branch only).
    try:
        docker_build_if_not_exist(config.image, config.dockerfile, extra_args=home.docker.build)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    # Refresh only in the flat list — the overview and card forms skip it
    # entirely. docker_update owns the build-vs-pull branch (build when a
    # project Dockerfile is declared — fatal; else pull — WARNING, non-fatal).
    if update and not info:
        try:
            docker_update(config.image, config.dockerfile, extra_args=home.docker.build)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    logger.debug("launching read-only info container", extra={"argv": argv})

    # Minimal read-only shape: the project as /workspace (the working dir) and
    # one --add-host per resolved host — no port publish, no env-file, no afm
    # mounts, no credentials. extra_args is a SEPARATE keyword to
    # DockerRunner.run (NOT part of params, which is unpacked via **);
    # home.docker.run tokens are appended verbatim after the translated flags
    # and before the image, never translated to an --extra-args flag.
    return DockerRunner(config.image).run(
        argv,
        extra_args=home.docker.run,
        name=container_name,
        rm=True,
        entrypoint="python3",
        workdir="/workspace",
        v=[f"{Path.cwd().resolve()}:/workspace"],
        add_host=[f"{host}:{ip}" for host, ip in hosts.items()],
    )
