# Image version probe — goga/docker

## Domain

Reading the goga package version from inside a Docker image with a
short-lived capture container. This practice covers the
`docker_image_goga_version` entry point on the goga/docker facade.

Target audience: launch paths that must learn which goga version an image
carries before starting a work container (today the `DockerRunner` version
check gate), and any future consumer that needs the image-side version
string.

## Public API

    from goga.docker import docker_image_goga_version

- `docker_image_goga_version(image: str) -> str | None` — run
  `docker run --rm --entrypoint python3 <image> -c "from importlib.metadata import version; print(version('goga'))"`
  with captured output and return the printed version string; None on any
  failure (non-zero docker exit, missing docker binary, empty or
  non-version-shaped output — accepted shape: the stripped first stdout
  line begins with a non-empty ASCII-digit major segment, the leading
  release-segment shape `compare_versions` reduces).

## Ready-to-use pattern

    from goga.docker import docker_image_goga_version

    version = docker_image_goga_version(config.image)
    if version is None:
        ...  # the image could not answer — treat as undeterminable
    else:
        ...  # a version string, e.g. "1.2.0"

Interpretation of the result belongs to the caller — the probe only
obtains the string.

## Preconditions

- `image` MUST be non-None (callers validate config.image first).
- The image must already exist locally — acquire it before probing;
  probing a nonexistent image returns None.

## Side effects

- One short-lived container per call (`--rm`); nothing is printed or
  streamed — output is captured.

## Failure modes

- Non-zero docker exit (no python3, no goga installed, image problems) →
  None, never an exception.
- Missing docker binary → None (the caller is expected to have verified
  docker availability).

## Anti-patterns

- Do NOT retry the probe on None — one call, one container.
- Do NOT cache results between calls.
- Do NOT pass mounts, env-file, or raw docker tokens — the probe is
  deliberately minimal.
