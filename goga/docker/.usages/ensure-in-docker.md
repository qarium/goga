# In-container guard — goga/docker

## Domain

Guard routine for in-container entrypoints. Refuses to proceed when the process
is not running inside the goga Docker image, so host-side invocations of
in-container entrypoints fail loudly instead of producing silent broken behavior
(missing binaries, wrong paths, missing runtime dirs).

Target audience: implementers of in-container entrypoints (`python -m <pkg>`
runpy entrypoints designed to run only inside the goga Docker container).

## Public API

    from goga.docker import ensure_in_docker

- `ensure_in_docker() -> None` — read the `GOGA_DOCKER` env marker; when it is
  not exactly `"1"`, print a clear message to stderr and exit the process with
  code 1. Returns normally (no value) when the marker is present.

## Typical usage

### Guard at the top of an in-container entrypoint

Call `ensure_in_docker()` as the FIRST statement of an in-container entrypoint —
before any filesystem, subprocess, or configuration work. Two common shapes:

    # Shape 1 — a routine entrypoint (a function called from __main__)
    from .docker import ensure_in_docker

    def main() -> int:
        ensure_in_docker()
        # ... rest of the entrypoint
        return 0

    # Shape 2 — a runpy __main__ guard block (no routine wrapper)
    from .docker import ensure_in_docker

    if __name__ == "__main__":
        ensure_in_docker()
        # ... delegate to the entrypoint routine

In both shapes the guard call MUST come before any work that assumes an
in-container environment (binaries, paths, and runtime state only present
inside the goga Docker image).

### What the consumer sees

Inside the goga Docker image (`GOGA_DOCKER=1` is set at image build time):

    $ python -m <in-container-entrypoint> <args>
    # proceeds normally

From the host (no `GOGA_DOCKER` marker):

    $ python -m <in-container-entrypoint> <args>
    <clear stderr message about running inside the goga Docker image>
    $ echo $?
    1

The exact set of entrypoints that use this guard is defined by those
entrypoints' own contracts, not by this practice.

## Preconditions

- The entrypoint that calls `ensure_in_docker()` MUST be an in-container
  entrypoint — one designed to run only inside the goga Docker image. Host-side
  launchers MUST NOT call this guard; they run on the host where `GOGA_DOCKER`
  is absent by design.

## Side effects

- On the refusal path: writes a message to `sys.stderr` and raises `SystemExit`
  with code 1. No filesystem or subprocess work is performed before the exit.
- On the success path (`GOGA_DOCKER == "1"`): no side effects — returns `None`.

## Failure modes

- Missing or non-`"1"` `GOGA_DOCKER` value → process exits with code 1 and a
  clear stderr message. This is the intended behavior, not an error in the guard.

## Anti-patterns

- Do NOT call `ensure_in_docker()` from host-side launchers.
  The guard's contract is in-container-only.
- Do NOT wrap `ensure_in_docker()` in a try/except that catches `SystemExit` to
  bypass the refusal — the guard is terminal by design.
- Do NOT replace the env marker check with a softer signal (logging a warning
  and continuing). The whole point is to fail fast.
