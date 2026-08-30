# Configuration

goga reads configuration from two files: the **project** config `.goga/config.yml` in the project root (created by `goga init`) and the optional machine-wide **home** config `~/.goga/config.yml`.

| File | Scope | Required |
|---|---|---|
| [Project Configuration](project.md) — `.goga/config.yml` | One project: language, image, build and pipeline executors, codemanifest, tools, usages, lint, topics | Required for `goga build` / `goga pipeline` |
| [Home Configuration](home.md) — `~/.goga/config.yml` | Whole machine: base env layer, extra `docker run` / `docker build` arguments | Optional — absent by default |

The home config is the lower-priority layer: `home.env` is the base of the env layering formula `{**home.env, **project_env, **cli_env}`, and `docker.run` / `docker.build` fragments are appended to every container invocation regardless of the project. See [Home Configuration](home.md#env-layering) for the layering details.

See also [Agents](agents.md) for how `agent: <name>` values in both configs resolve into wrapper scripts inside the Docker container.
