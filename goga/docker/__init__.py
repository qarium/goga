"""Docker cell — in-container environment assertions, container launching, image building.

The current body holds the in-container guard routine ``ensure_in_docker``.
"""

from .env import ensure_in_docker

__all__ = ["ensure_in_docker"]
