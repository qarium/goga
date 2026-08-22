"""Docker cell — in-container environment assertions, image building, container launching.

The seed-cell for everything Docker in the project. The body holds the
in-container guard routine ``ensure_in_docker``; the image-acquisition surface
``DockerBuilder`` (build), ``docker_pull`` (pull), ``docker_update`` (the
single ``--update`` build-vs-pull decision point), and
``docker_build_if_not_exist`` (the first-run safety net that builds the local
image when it is absent and a project Dockerfile is declared); the silent
image-version probe ``docker_image_goga_version`` (one short-lived capture
container reporting the goga version installed inside an image); and the
stateful container launcher ``DockerRunner`` (``docker run`` + SIGTERM/SIGINT
lifecycle).
"""

from .builder import (
    DockerBuilder,
    docker_build_if_not_exist,
    docker_image_goga_version,
    docker_pull,
    docker_update,
)
from .env import ensure_in_docker
from .runner import DockerRunner

__all__ = [
    "DockerBuilder",
    "DockerRunner",
    "docker_build_if_not_exist",
    "docker_image_goga_version",
    "docker_pull",
    "docker_update",
    "ensure_in_docker",
]
