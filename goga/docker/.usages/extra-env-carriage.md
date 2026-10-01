# The CLI environment carriage across the docker boundary

How a domain threads the CLI environment entries (the repeatable `-e/--env`
option) across the docker launch boundary. For the host-side launchers that
write the container env-file (`goga/commands/pipeline`, `goga/commands/build`)
and the in-container domain launches that compose the target binary's
environment (`goga/pipeline`, `goga/build`).

## The carriage contract

The docker `--env-file` flattens every layer into one file, so the CLI entries
cannot be recognized on the container side once they land in it. The carriage
therefore travels twice, from one source:

- the env-file carries the raw `KEY=VALUE` lines verbatim — every reader of
  the inherited environment keeps seeing them;
- the dedicated engine variable `GOGA_EXTRA_ENV` carries the encoded form of
  the same entries — the value produced by `encode_extra_env` — so the
  container side can apply them as a distinguishable layer.

Both places compose from the same parsed CLI values on every launch; they
never diverge. Write the variable on every launch that writes the CLI lines.

## The environment ladder

The layers, lowest to highest, in both domains:

    home.env < git identity < task env layer (effective) < CLI -e < engine variables

Engine variables — `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`,
`HTTPS_PROXY`, `NO_PROXY` — are launch mechanics: nothing overrides them. In
the env-file they are written after the CLI lines; in the container the launch
composition drops a task-layer or CLI key that collides with one, silently —
the inherited launch value stands, with no warning.

## Host half — write the env-file and the payload

The launcher writes the env-file in ladder order and appends the payload line
built from the same entries:

```python
from goga.docker import encode_extra_env

env_file_lines = [
    *home_env_lines,          # home.env — the base layer
    *git_identity_lines,      # git identity
    *extra_env,               # the raw CLI entries, verbatim
    *engine_variable_lines,   # AFM_DIR, AFM_DOCKER_FILE_ROOTS, proxy — last
    f"GOGA_EXTRA_ENV={encode_extra_env(list(extra_env))}",
]
```

- The CLI lines and the payload come from the same tuple — never parse,
  filter, or re-format one of them independently of the other.
- The engine variables are written after the CLI lines so the env-file itself
  respects the ladder.

## Container half — decode and apply above the task env layer

The domain launch decodes the payload once and applies it above its effective
task env layer, for the target binary's launch only:

```python
import os
from goga.docker import decode_extra_env

payload = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))
merged = {**effective_task_env, **payload}      # CLI wins on key conflict
launch_layer = {k: v for k, v in merged.items() if k not in ENGINE_KEYS}
run_target(env=launch_layer)
```

- The task env layer is the domain's effective env mapping (for example
  `pipeline.env`); the payload wins on key conflict — explicit CLI input beats
  configuration and tool amendments.
- Keys colliding with the engine variables are dropped before the launch; the
  inherited launch values are never overridden.
- The layer applies to the target binary's subprocess only — the container's
  process environment stays untouched.
- The payload and the layer values are never printed or logged; a damaged
  payload fails as one clean error naming the variable — nothing partially
  applied, the target binary never launches.

