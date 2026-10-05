"""Container launching — goga/docker."""

from __future__ import annotations

import signal
import subprocess

from ..version import ensure_version_match, version_check_enabled
from ._flags import translate_params
from .builder import docker_image_goga_version


class DockerRunner:
    """Stateful Docker container runner."""

    def __init__(self, image: str) -> None:
        self.image = image

    def run(
        self,
        args: list[str],
        extra_args: list[str] | None = None,
        **params: str | bool | list[str],
    ) -> int:
        """Run ``docker run <params-flags> <extra_args> <image> <args>`` and manage lifecycle.

        Args:
            args: The command and its arguments placed after the image.
            extra_args: Raw extra docker tokens appended verbatim after the
                translated params flags and before the image (structural-only —
                docker surfaces flag conflicts).
            **params: docker run CLI options translated by the shared param→flag
                rule; ``name`` is required — emitted as ``--name`` and captured
                as the ``docker kill`` target.

        Returns:
            The container exit code.

        Raises:
            SystemExit: with code ``1`` when the host-image version-check gate
                refuses, before any handler install or launch.
        """
        # `name` is the kill target — required and special (emitted as `--name`
        # AND captured as the `docker kill` target). Validate it BEFORE the
        # version gate, handler installs, and Popen so a missing name never
        # launches a container we then cannot identify for teardown — nor a
        # side probe container for a call doomed to fail programmatically.
        name = params.get("name")
        if name is None:
            raise ValueError("DockerRunner.run requires a 'name' param (the docker kill target)")

        # Step 0 — version-check gate: decide → probe → verify. The probe sees
        # ONLY the constructor image (no params/extra_args); the escape is read
        # exactly once, here — never re-read past the gate.
        if version_check_enabled():
            ensure_version_match(docker_image_goga_version(self.image))

        extra_args = list(extra_args or [])
        flags = translate_params(params)
        argv = ["docker", "run", *flags, *extra_args, self.image, *args]

        def _on_signal(signum: int, _frame: object) -> None:
            # Convert an asynchronous signal into a synchronous SystemExit so it
            # unwinds through `finally` (docker kill + handler restore) rather
            # than terminating the process on the spot. 128 + signum is the
            # shell convention (130 SIGINT, 143 SIGTERM).
            raise SystemExit(128 + signum)

        # Install BOTH handlers and save the previous ones so they are restored
        # in `finally` — this lets the runner nest correctly under a
        # caller-installed handler (D7): when the caller's handler is restored
        # here it is restored to whatever the caller had set, not overwritten.
        prev_term = signal.signal(signal.SIGTERM, _on_signal)
        prev_int = signal.signal(signal.SIGINT, _on_signal)
        try:
            proc = subprocess.Popen(argv)  # inherited stdio → streamed
            exit_code = proc.wait()
        finally:
            # Unconditional + error-suppressed: `run()` is only reached when the
            # caller intends to launch, so a kill is always appropriate teardown
            # (the container may already be gone on the normal-exit path).
            subprocess.run(
                ["docker", "kill", name],
                check=False,
                capture_output=True,
            )
            signal.signal(signal.SIGTERM, prev_term)
            signal.signal(signal.SIGINT, prev_int)
        return exit_code
