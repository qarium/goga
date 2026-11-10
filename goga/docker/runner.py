"""Container launching and direct child execution — goga/docker."""

from __future__ import annotations

import os
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


def run_direct(argv: list[str], env: dict[str, str] | None = None) -> int:
    """Run a composed command line as a child of the current environment.

    The direct-execution counterpart of ``DockerRunner.run``: a dual-surface
    launcher that composed its command line and env contract once executes
    them through this routine when ``is_in_docker`` resolved ``True`` — the
    same composed argv the docker substrate hands to the image entrypoint,
    prefixed with the program token, spawned with inherited stdio.

    Args:
        argv: The full child command line INCLUDING the program token (for
            example ``["python3", "-m", "goga.pipeline", "run", ...]``).
        env: Optional env layer applied on top of the inherited process
            environment for this child only, composed by the caller from the
            same layer code that produces the env-file lines of the docker
            substrate; ``None`` runs the child with the inherited environment
            untouched. The caller's own process environment is never written.

    Returns:
        The child's exit code, verbatim.

    Raises:
        OSError: propagated raw from the spawn (for example
            ``FileNotFoundError`` when the program token names no existing
            program) — the caller wraps.
    """
    child_env = {**os.environ, **env} if env else None

    proc = None

    def _on_signal(signum: int, _frame: object) -> None:
        # Forward FIRST so the child terminates (the docker substrate's
        # `docker kill` analogue), then convert the asynchronous signal into
        # a synchronous SystemExit so it unwinds through `finally` (handler
        # restore) rather than terminating the process on the spot.
        # 128 + signum is the shell convention (130 SIGINT, 143 SIGTERM).
        # A signal arriving before the spawn completes finds proc None and
        # exits without a forward.
        if proc is not None and proc.poll() is None:
            proc.send_signal(signum)

        raise SystemExit(128 + signum)

    # Install BOTH handlers and save the previous ones so they are restored
    # in `finally` — the runner nests correctly under a caller-installed
    # handler (D7), same as DockerRunner.run.
    prev_term = signal.signal(signal.SIGTERM, _on_signal)
    prev_int = signal.signal(signal.SIGINT, _on_signal)

    try:
        proc = subprocess.Popen(argv, env=child_env)  # inherited stdio → streamed

        return proc.wait()
    finally:
        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)
