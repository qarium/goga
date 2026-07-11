"""Docker cell — in-container environment assertions, image building, container launching.

The seed-cell for everything Docker in the project. The body holds the
in-container guard routine ``ensure_in_docker``; the image-acquisition surface
``DockerBuilder`` (build), ``docker_pull`` (pull), and ``docker_update`` (the
single ``--update`` build-vs-pull decision point); and the stateful container
launcher ``DockerRunner`` (``docker run`` + SIGTERM/SIGINT lifecycle).
"""

from .builder import DockerBuilder, docker_pull, docker_update
from .env import ensure_in_docker
from .runner import DockerRunner

__all__ = [
    "DockerBuilder",
    "DockerRunner",
    "docker_pull",
    "docker_update",
    "ensure_in_docker",
]
