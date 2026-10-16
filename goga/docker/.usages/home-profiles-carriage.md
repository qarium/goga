# The home-profiles carriage across the docker boundary

How a domain threads the personal home profiles (~/.goga/profiles/)
across the docker launch boundary. For the host-side launchers that
write the container env-file (goga/commands/pipeline,
goga/commands/build) and the in-container domains that resolve profiles
against the bundle (goga/pipeline, goga/build).

## The carriage contract

Host home directories are never mounted. The whole home bundle travels
as ONE derived value, the engine variable `GOGA_HOME_PROFILES`:

- the host launcher reads and strictly parses the bundle
  (`load_home_profiles` from goga/pipeline/workflow — a malformed home
  profile fails on the host before any container launches);
- the same launcher encodes the mapping (`encode_home_profiles`) and
  writes the single payload line into the container env-file;
- the in-container domain reads the variable once, decodes it
  (`decode_home_profiles`), and passes the mapping into its profile
  resolution.

The whole bundle — not just one profile — crosses the boundary because
the effective profile name may only become known in-container (the
workflow `profile:` default).

## Host half — write the payload line

```python
from goga.pipeline.workflow import load_home_profiles
from goga.docker import encode_home_profiles

home_profiles = load_home_profiles(home_dir)  # strict on malformed
if home_profiles:
    lines.append(f"GOGA_HOME_PROFILES={encode_home_profiles(home_profiles)}")
```

- Write the line only when the bundle is non-empty — an empty bundle
  writes nothing.
- The line follows the CLI entries in the env-file and respects the
  engine-skip rule: an explicit user `-e GOGA_HOME_PROFILES=...` entry
  keeps winning over the launcher-produced value.

## Container half — decode once, resolve against

```python
import os
from goga.docker import decode_home_profiles

bundle = decode_home_profiles(os.environ.get("GOGA_HOME_PROFILES", ""))
loaded = load_workflow(path, cli_profile, env_profile, home_profiles=bundle)
```

- The variable is read once per launch; a damaged payload fails as one
  clean error naming the variable — nothing partially applied, no stage
  or pass launches.
- The decoded mapping is passed as a parameter into profile resolution;
  the container's process environment is never mutated.

## Ladder position and secrecy

`GOGA_HOME_PROFILES` is an engine variable — launch mechanics: nothing
overrides it, and task-layer or CLI keys colliding with it are dropped
silently (the inherited launch value stands). Payload and decoded
values are never printed or logged.
