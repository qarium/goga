# Home Configuration (~/.goga/config.yml)

Consumer guide for the machine-wide goga home configuration. Target audience:
host-side launchers (goga/commands/pipeline, goga/commands/build) that assemble
docker container environments and docker CLI commands.

The home config is an OPTIONAL, narrow docker-only layer. Its absence is normal —
load_home_config() returns an empty HomeConfig and never raises.

## Schema

env:
  KEY: VALUE        # base environment layer for docker run containers
docker:
  run: [...]        # extra tokens appended to every `docker run`
  build: [...]      # extra tokens appended to `docker build` (image build)

## Loading

from goga.config import load_home_config, HomeConfig

home: HomeConfig = load_home_config()   # empty when ~/.goga/config.yml is absent

## Environment layering (lowest priority)

home.env is the BASE layer of the container environment. Project config
(config.pipeline.env / config.build.task_executor.env) and CLI (--env / extra_env)
override it on key conflict:

container_env = {**home.env, **project_env, **cli_env}   # home is the base

## Docker tokens

home.docker.run tokens are appended to every docker run (pipeline + build
containers); home.docker.build tokens to docker build (image build). Each YAML
list entry is shell-tokenized at load (shlex.split), so it is authored as a
shell-like fragment:

    docker:
      run:
        - "-v /host/path:/container/path"   # → ["-v", "/host/path:/container/path"]
        - "--network=host"                  # → ["--network=host"] (unchanged)

The resulting argv tokens are appended after goga's own flags; docker surfaces
conflicts. Quote a value that contains whitespace (e.g.
`-v "/host with space:/c"`). `$VAR` and `~` are NOT expanded. A malformed entry
(an unterminated quote) raises ValueError at load.

## Consumer constraints

- Treat absence as empty (never fail on a missing file).
- home.env applies ONLY to docker run containers, NOT to docker build.
- Pass the already-tokenized docker.run/docker.build lists through verbatim —
  do not re-split, quote, or validate them; docker surfaces conflicts.
