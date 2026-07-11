"""Image acquisition — goga/docker.

Holds the stateful image builder ``DockerBuilder`` plus the standalone routines
``docker_pull`` and ``docker_update``. ``docker_update`` is the single
``--update`` decision point shared by the three host-side call sites (build,
pipeline discovery, pipeline run): BUILD when a project Dockerfile is declared
(fatal on failure), otherwise PULL (non-fatal — WARNING on failure). All docker
CLI invocations stream the CLI's own stdout/stderr to the host.
"""

from __future__ import annotations

import logging
import subprocess

from ._flags import translate_params

logger = logging.getLogger(__name__)


class DockerBuildError(RuntimeError):
    """Raised by ``DockerBuilder.build`` when ``docker build`` exits non-zero.

    Fatal by contract — the caller surfaces it as exit 1 so a half-built image
    never silently launches. Internal to the cell (not a declared contract
    entity nor a facade re-export).
    """


class DockerBuilder:
    """Stateful Docker image builder.

    The image tag, Dockerfile path, and build context are concrete per build, so
    they are held as constructor state. ``build`` runs ``docker build`` tagging
    the result as ``image`` (so the locally built image shadows the registry tag
    consumed by ``docker run``); build failure is fatal.
    """

    def __init__(self, image: str, dockerfile: str = "Dockerfile", context: str = ".") -> None:
        self.image = image
        self.dockerfile = dockerfile
        self.context = context

    def build(self, **params: str | bool | list[str]) -> None:
        """Run ``docker build`` for this builder's image/dockerfile/context.

        Extra CLI options arrive as ``params`` and are translated to flags by the
        shared param→flag rule. Docker output is streamed (inherited stdio). On a
        non-zero docker exit, raise ``DockerBuildError`` (fatal — do NOT swallow).
        """
        flags = translate_params(params)
        argv = [
            "docker",
            "build",
            *flags,
            "-f",
            self.dockerfile,
            "-t",
            self.image,
            self.context,
        ]
        result = subprocess.run(argv, check=False)  # streamed
        if result.returncode != 0:
            raise DockerBuildError(f"docker build failed for image '{self.image}' (exit code {result.returncode})")


def docker_pull(image: str) -> bool:
    """Pull ``image`` from the registry, streaming docker output.

    NON-fatal: returns True on success; on failure logs a WARNING and returns
    False. Never raises.
    """
    result = subprocess.run(["docker", "pull", image], check=False)  # streamed
    if result.returncode == 0:
        return True
    logger.warning(f"failed to pull image '{image}'")
    return False


def docker_update(image: str, dockerfile: str | None) -> None:
    """The ``--update`` decision point: build when a Dockerfile is declared, else pull.

    Takes PRIMITIVES (``image``, ``dockerfile``), never a ``Config`` — so this
    cell stays a pure leaf with no dependency on goga/config. Exactly one of
    build/pull runs: ``dockerfile`` non-None → fatal build (propagates); None →
    non-fatal pull (WARNING, bool discarded). ``image`` non-None is a
    caller-validated precondition.
    """
    if dockerfile is not None:
        DockerBuilder(image, dockerfile, context=".").build()
    else:
        docker_pull(image)
