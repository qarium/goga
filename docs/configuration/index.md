# Configuration

goga reads configuration from two files: the **project** config `.goga/config.yml` in the project root (created by `goga init`) and the optional machine-wide **home** config `~/.goga/config.yml`.

| File | Scope | Required |
|---|---|---|
| [Project Configuration](project.md) — `.goga/config.yml` | One project: language, image, build and pipeline executors, codemanifest, tools, usages, lint, topics | Required for `goga build` / `goga pipeline` |
| [Home Configuration](home.md) — `~/.goga/config.yml` | Whole machine: base env layer, extra `docker run` / `docker build` arguments | Optional — absent by default |

## Pages in this section

| Page | Content |
|---|---|
| [Project Configuration](project.md) | `.goga/config.yml` — global fields, the `codemanifest` section, and the map of domain-owned sections |
| [Home Configuration](home.md) | `~/.goga/config.yml` — the machine-wide layer |
| [Agents](agents.md) | How `agent: <name>` values in both configs resolve into wrapper scripts inside the Docker container |
| [`goga config`](cli.md) | Read configuration values back from the command line |

The home config is the lower-priority layer: `home.env` is the base of the env layering formula `{**home.env, **project_env, **cli_env}`, and `docker.run` / `docker.build` fragments are appended to every container invocation regardless of the project. See [Home Configuration](home.md#env-layering) for the layering details.

Every domain-owned section of the project config (`build`, `pipeline`, `tools`, `usages`, `lint`, `topics`) is documented in full in its domain's **Configuration** page — see [Project Configuration — Domain sections](project.md#domain-sections).
