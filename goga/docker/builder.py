"""Image acquisition — goga/docker."""

from __future__ import annotations

import logging
import re
import subprocess

from ._flags import translate_params

logger = logging.getLogger(__name__)

# Python snippet the image-version probe runs inside the container (see
# docker_image_goga_version): print the goga version reported by the image's
# own importlib.metadata — one line on stdout is the whole probe protocol.
PROBE_SNIPPET = "from importlib.metadata import version; print(version('goga'))"

# Shape the probe accepts for the first stdout line: an ASCII-digit major
# segment, optionally ".digits", before any dev/pre/post/local tail — the same
# leading release-segment shape the version-cell comparator reduces. re.ASCII
# keeps \d to 0-9 (Unicode decimal digits are not PEP 440).
_PROBE_VERSION_RE = re.compile(r"\d+(?:\.\d+)?", re.ASCII)


class DockerBuildError(RuntimeError):
    """Raised by ``DockerBuilder.build`` when ``docker build`` exits non-zero."""


class DockerBuilder:
    """Stateful Docker image builder."""

    def __init__(self, image: str, dockerfile: str = "Dockerfile", context: str = ".") -> None:
        self.image = image
        self.dockerfile = dockerfile
        self.context = context

    def build(self, extra_args: list[str] | None = None, **params: str | bool | list[str]) -> None:
        """Run ``docker build`` for this builder's image/dockerfile/context.

        Args:
            extra_args: Raw extra docker tokens appended verbatim after the
                translated params flags and before ``-f`` (structural-only —
                docker surfaces conflicts). ``None`` normalizes to an empty list
                (mutable-default avoidance).
            **params: Additional docker build CLI options, translated to flags by
                the shared param→flag rule (e.g. ``add_host`` → ``--add-host``,
                ``pull=True`` → ``--pull``).

        Raises:
            DockerBuildError: When ``docker build`` exits non-zero. Fatal by
                contract — the caller surfaces it as exit 1.
        """
        extra_args = list(extra_args or [])
        flags = translate_params(params)
        argv = [
            "docker",
            "build",
            *flags,
            *extra_args,
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

    Args:
        image: image:tag to pull (non-None; the caller passes the validated
            ``config.image``).

    Returns:
        True on success; False on pull failure (network / auth / not-found) —
        logged as a WARNING; never raises.
    """
    result = subprocess.run(["docker", "pull", image], check=False)  # streamed
    if result.returncode == 0:
        return True
    logger.warning(f"failed to pull image '{image}'")
    return False


def docker_update(image: str, dockerfile: str | None, extra_args: list[str] | None = None) -> None:
    """The ``--update`` decision point: fatal build when a Dockerfile is declared, else non-fatal pull.

    Args:
        image: image:tag — non-None (caller-validated); used as the build tag
            and the pull target.
        dockerfile: path to a project Dockerfile. None → pull branch.
        extra_args: Raw extra docker tokens forwarded verbatim to
            ``DockerBuilder.build`` in the build branch (appended before ``-f``);
            ignored by the pull branch. ``None`` normalizes inside ``build``.
    """
    if dockerfile is not None:
        DockerBuilder(image, dockerfile, context=".").build(pull=True, extra_args=extra_args)
    else:
        docker_pull(image)


def _image_exists(image: str) -> bool:
    """Check whether ``image`` is present in the local docker image store.

    Args:
        image: image:tag to probe in the local image store.

    Returns:
        True when the image is present locally, False when absent or when the
        docker binary is unavailable.
    """
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            check=False,
        )
    except (FileNotFoundError, PermissionError, OSError):
        return False

    return result.returncode == 0


def docker_build_if_not_exist(image: str, dockerfile: str | None, extra_args: list[str] | None = None) -> None:
    """First-run safety net: unconditionally build the local image when absent and a Dockerfile is declared.

    Args:
        image: image:tag — non-None (caller-validated); used as the local-image
            probe target and the build tag.
        dockerfile: path to a project Dockerfile. None → no-op when the image is
            absent (this routine never pulls — a registry image is pulled by
            ``docker run`` itself or by an explicit ``--update``).
        extra_args: Raw extra docker tokens forwarded verbatim to
            ``DockerBuilder.build`` in the build branch (appended before ``-f``);
            ignored by the no-op branches. ``None`` normalizes inside ``build``.
    """
    if _image_exists(image):
        return

    if dockerfile is not None:
        DockerBuilder(image, dockerfile, context=".").build(pull=True, extra_args=extra_args)


def docker_image_goga_version(image: str) -> str | None:
    """Read the goga package version inside ``image`` with a one-shot probe container.

    Args:
        image: image:tag — non-None (caller-validated); the probe target.

    Returns:
        The image's goga version string (e.g. ``"1.2.1"``, ``"1.2.1.dev3"``,
        ``"0.0.0"``), or ``None`` when the image could not answer — never
        raises.
    """
    argv = ["docker", "run", "--rm", "--entrypoint", "python3", image, "-c", PROBE_SNIPPET]

    # 1. One minimal probe container; a missing binary is a None answer, not a
    #    crash (the caller has already verified docker availability).
    try:
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
    except (FileNotFoundError, PermissionError, OSError):
        return None

    # 2. The image must answer cleanly — docker's own failures stay captured.
    if result.returncode != 0:
        return None

    # 3. First stdout line only, stripped; whitespace-only output is no answer.
    lines = result.stdout.splitlines()

    if not lines:
        return None

    stripped = lines[0].strip()

    if not stripped:
        return None

    # 4. Shape recognition — leading release segments, tails pass through.
    if _PROBE_VERSION_RE.match(stripped) is None:
        return None

    return stripped
