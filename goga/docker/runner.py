"""Container launching — goga/docker.

Holds the stateful container runner ``DockerRunner``. The image to run is
concrete per launch, so it is held as constructor state. ``run`` assembles the
``docker run`` command from the image + CLI-option params + post-image command
args, owns the launch lifecycle (a SIGTERM/SIGINT handler that exits the process
with ``128 + signum`` and a guaranteed, error-suppressed ``docker kill <name>``
in ``finally``), and returns the container exit code.

The runner is a THIN executor: it resolves nothing — mounts, hosts, env-file,
runtime-dir, and the ``--name`` target all arrive from the caller as ``params``.
Host-side cleanup (env-file/tmpfile unlink, ``.ralphex/`` removal) is the
CALLER's job, in its own outer ``finally`` — so the runner's ``finally`` (kill +
handler restore) always runs before the caller's. The runner is therefore safe
to nest under a caller-installed handler (D7).
"""

from __future__ import annotations

import signal
import subprocess

from ._flags import translate_params


class DockerRunner:
    """Stateful Docker container runner.

    Mirrors ``DockerBuilder``: the image is concrete, so it is constructor
    state. ``run`` builds the ``docker run`` argv from the image + translated
    params + args, installs a SIGTERM/SIGINT handler that converts a signal into
    a ``SystemExit(128 + signum)``, launches the container (streamed stdio),
    and in ``finally`` issues an unconditional error-suppressed ``docker kill``
    against the container name and restores the previous handlers.
    """

    def __init__(self, image: str) -> None:
        self.image = image

    def run(self, args: list[str], **params: str | bool | list[str]) -> int:
        """Run ``docker run <params-flags> <image> <args>`` and manage lifecycle.

        ``args`` is the COMMAND + ARGs after the image. ``params`` are docker run
        CLI options translated by the shared param→flag rule. ``name`` is
        REQUIRED and SPECIAL: emitted as ``--name`` AND captured as the
        ``docker kill`` target in ``finally`` (the one exception to the uniform
        rule). Returns the container exit code.
        """
        # `name` is the kill target — required and special (emitted as `--name`
        # AND captured as the `docker kill` target). Validate it BEFORE installing
        # handlers or Popen so a missing name never launches a container we then
        # cannot identify for teardown.
        name = params.get("name")
        if name is None:
            raise ValueError("DockerRunner.run requires a 'name' param (the docker kill target)")

        flags = translate_params(params)
        argv = ["docker", "run", *flags, self.image, *args]

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
