# Direct in-container execution — `run_direct`

Domain: executing a composed goga command as a child process inside the
goga Docker image. Audience: implementers of dual-surface launchers
(commands that run the same composed command line through docker run on
the host and directly inside the image).

## When to use it

A dual-surface launcher composes its command line (argv) and its env
contract ONCE, then executes them through one of two substrates:

- host substrate — `DockerRunner.run` launches `docker run <flags>
  <image> <args>` with an env-file;
- direct substrate — `run_direct` spawns the same command as a child
  process of the current environment (the `is_in_docker` marker resolved
  True).

The composition code is shared; only the executor differs. Divergence
between the two surfaces is a defect.

## Calling the executor

```python
from goga.docker import is_in_docker, run_direct

argv = ["python3", "-m", "goga.pipeline", "run", name, "--port", str(port)]
env = compose_env_layer(...)  # the SAME composition that builds env-file lines

if is_in_docker():
    return run_direct(argv, env=env)
return DockerRunner(image).run(args, extra_args=..., **params)
```

- `argv` carries the full child command INCLUDING the program token
  (`python3 ...`) — the docker substrate's entrypoint prefix becomes the
  first token here.
- `env` is a mapping applied on top of the inherited process
  environment for the child only. Compose it from the same layer code
  that produces the env-file lines (parse each `KEY=VALUE` line on the
  first `=`; apply in order — last write wins, mirroring the
  `--env-file` semantics). `None` means the inherited environment
  unchanged.
- The caller's own process environment is never modified.
- Output streams live to the caller's stdio — the same bytes the docker
  substrate streams from the container.

## Lifecycle contract

- SIGTERM/SIGINT during the child run: the signal is forwarded to the
  child (it terminates), and the launcher process exits with
  `128 + signum` (130 SIGINT, 143 SIGTERM) — the same shell convention
  `DockerRunner` applies.
- The child's exit code is returned verbatim; no exit machinery of its
  own exists on this path.

## Constraints

- No docker-CLI check, no image acquisition, no version consistency
  check on this path — those gate the docker substrate only; the direct
  path already runs inside the image.
- The env layer values are secret-safe: never logged, never printed,
  never included in any diagnostic output.
- Do not compose the argv or the env layer inside the executor — the
  caller owns both compositions (one composition, two substrates).

## Testing note

Tests spawn a real short-lived child (for example `python3 -c ...`) or a
fake binary placed on PATH; signal-forwarding tests send SIGTERM to the
launcher process and assert the `128 + signum` exit and the child's
termination.
