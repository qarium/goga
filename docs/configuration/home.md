# Home Configuration

In addition to the per-project `.goga/config.yml` (see [Project Configuration](project.md)), goga reads an optional
machine-wide configuration from `~/.goga/config.yml`. This file is entirely
optional — when it is absent (the normal state), an empty home config is used
and nothing changes. A malformed file surfaces as a clean error and exits
non-zero; a missing file is never an error.

```yaml
# ~/.goga/config.yml — optional, machine-wide
env:
  HTTP_PROXY: http://corp:3128     # applied as the lowest-priority env base layer
docker:
  run:                            # appended to every `docker run` (build + pipeline)
    - "--network=host"
    - "-v /Users/me/.ssh:/home/goga/.ssh:ro"   # shell-like: flag + value split into two tokens
  build: ["--squash"]              # appended to image builds only (`goga build`/`--update`)
```

Each `docker.run` / `docker.build` entry is parsed as a **shell fragment**:
`-v /host:/container` becomes two argv tokens (`-v` and the volume spec), so you
can write them the same way you would on the command line. The `--flag=value`
form and already-split single tokens are unchanged. Quote a value that contains
whitespace (e.g. `-v "/host with space:/c"`); `$VAR` and `~` are not expanded. A
malformed entry (an unterminated quote) fails to load with a clean error.

| Field | Type | Description |
|-------|------|-------------|
| `env` | mapping | Environment variables applied as the **lowest-priority base layer** in the container env-file. Project config and CLI `-e`/`extra_env` override these on key conflict. Applied to `docker run` containers (`goga build` and `goga pipeline <name>`); not applied to `docker build` |
| `docker.run` | list of strings | Shell fragments appended to every `docker run` invocation in both `goga build` and `goga pipeline`. Each entry is shell-tokenized (e.g. `-v /host:/container` → `-v` + volume spec) |
| `docker.build` | list of strings | Shell fragments appended to image builds only — forwarded by both `goga build` and `goga pipeline` (`docker_build_if_not_exist` / `docker_update`, build branch only; ignored on image pull). Each entry is shell-tokenized like `docker.run` |

The env layering formula is `{**home.env, **project_env, **cli_env}` — `home.env`
is the base, project config wins over it, and CLI extra env wins last. Unknown
keys are ignored.
