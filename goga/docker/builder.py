"""Image acquisition — goga/docker.

Holds the stateful image builder ``DockerBuilder`` plus the standalone routines
``docker_pull`` and ``docker_update``. ``docker_update`` is the single
``--update`` decision point shared by the three host-side call sites (build,
pipeline discovery, pipeline run): BUILD when a project Dockerfile is declared
(fatal on failure), otherwise PULL (non-fatal — WARNING on failure). Docker
build/pull invocations stream the CLI's own stdout/stderr to the host; the
silent probes (``_image_exists``, ``docker_image_goga_version``) capture output
instead.
"""

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

    def build(self, extra_args: list[str] | None = None, **params: str | bool | list[str]) -> None:
        """Run ``docker build`` for this builder's image/dockerfile/context.

        Extra CLI options arrive as ``params`` and are translated to flags by the
        shared param→flag rule. Raw extra docker tokens arrive as ``extra_args``
        and are appended verbatim AFTER the translated flags and BEFORE ``-f``
        (a separate channel from ``params`` — structural-only, no translation;
        docker surfaces flag conflicts). Docker output is streamed (inherited
        stdio). On a non-zero docker exit, raise ``DockerBuildError``
        (fatal — do NOT swallow).

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

    NON-fatal: returns True on success; on failure logs a WARNING and returns
    False. Never raises.

    Args:
        image: image:tag to pull (non-None; the caller passes the validated
            ``config.image``).

    Returns:
        True on success, False on pull failure (network / auth / not-found).
    """
    result = subprocess.run(["docker", "pull", image], check=False)  # streamed
    if result.returncode == 0:
        return True
    logger.warning(f"failed to pull image '{image}'")
    return False


def docker_update(image: str, dockerfile: str | None, extra_args: list[str] | None = None) -> None:
    """The ``--update`` decision point: build when a Dockerfile is declared, else pull.

    Takes PRIMITIVES (``image``, ``dockerfile``, ``extra_args``), never a
    ``Config`` — so this cell stays a pure leaf with no dependency on
    goga/config. Exactly one of build/pull runs: ``dockerfile`` non-None → fatal
    build (propagates); None → non-fatal pull (WARNING, bool discarded).
    ``image`` non-None is a caller-validated precondition.

    The build branch passes ``pull=True`` so ``docker build`` refreshes base
    images (``FROM ...``) from the registry instead of using the local cache.
    ``extra_args`` is forwarded to ``DockerBuilder.build`` in the build branch
    ONLY; it is ignored on the pull branch.

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

    Runs ``docker image inspect <image>`` capturing stdout/stderr (silent probe).
    ``returncode == 0`` means present. Tolerates a missing docker binary
    (``FileNotFoundError`` / ``PermissionError`` / ``OSError`` → ``False``): the
    caller has already verified docker availability via ``_check_docker`` at the
    command entry, so a missing binary here is treated as "image not present"
    rather than crashing the probe.

    Internal to the cell — not declared in CODEMANIFEST and not re-exported.

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
    """First-run safety net: build the local image if it is absent and a Dockerfile is declared.

    Complementary to ``docker_update``: ``docker_update`` is gated by the
    ``--update`` flag (force refresh); this routine runs UNCONDITIONALLY at launch
    entry — its purpose is to guarantee the image exists, not to refresh it.

    Takes PRIMITIVES (``image``, ``dockerfile``, ``extra_args``), never a
    ``Config`` — so this cell stays a pure leaf with no dependency on goga/config.
    ``image`` non-None is a caller-validated precondition.

    The build branch passes ``pull=True`` so ``docker build`` refreshes base
    images (``FROM ...``) from the registry instead of using the local cache.
    ``extra_args`` is forwarded to ``DockerBuilder.build`` in the build branch
    ONLY; it is ignored by the no-op branches (image present; absent + no
    dockerfile).

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

    Runs one short-lived container — ``docker run --rm --entrypoint python3
    <image> -c PROBE_SNIPPET`` — capturing stdout/stderr instead of streaming
    them (silent on the host). Returns the first stdout line, stripped, when
    the docker exit is 0 and the line carries the leading release-segment
    shape; every failure mode (missing docker binary, non-zero exit, empty
    stdout, unrecognizable output) reduces to ``None``. Never raises — the
    verdict on an unanswered probe belongs to the caller
    (``ensure_version_match``), as does the interpretation of the returned
    string.

    Args:
        image: image:tag — non-None (caller-validated); the probe target.

    Returns:
        The image's goga version string (e.g. ``"1.2.1"``, ``"1.2.1.dev3"``,
        ``"0.0.0"``), or ``None`` when the image could not answer.
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
