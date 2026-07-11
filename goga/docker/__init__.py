"""Docker cell — in-container environment assertions, container launching, image building.

The seed-cell for everything Docker in the project. The body currently holds the
in-container guard routine ``ensure_in_docker`` plus the image-acquisition
surface: ``DockerBuilder`` (build), ``docker_pull`` (pull), and ``docker_update``
(the single ``--update`` build-vs-pull decision point). Container launching
(``DockerRunner``) is wired in by the runner task.
"""

from .builder import DockerBuilder, docker_pull, docker_update
from .env import ensure_in_docker

__all__ = ["DockerBuilder", "docker_pull", "docker_update", "ensure_in_docker"]
