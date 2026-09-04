# Pipelines — Configuration

The pipelines domain reads one optional section of `.goga/config.yml` — `pipeline`, the afm execution settings. The section must be present for the run form: `goga pipeline <name>` exits with a `ClickException` naming `pipeline` when it is absent (the list/info forms do not read it).

```yaml
pipeline:
  agent: claude        # the agent that runs the stages inside the container
  env: {}              # environment variables of the pipeline container
  proxy: http://corp:3128
  hosts: {foo.local: "127.0.0.1"}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `pipeline.agent` | `string` | No | AI agent that runs the pipeline stages inside the container. Optional at the loader level — absent/YAML-null/empty/whitespace resolves to `None`. When `None`, the agent may be supplied by a per-stage workflow override or afm's own default, so `goga pipeline` does not require it. Same resolution mechanic and baseline set as `build.task_executor.agent` — see [Agents](../../configuration/agents.md) |
| `pipeline.env` | mapping | No | Environment variables passed into the pipeline container. Keys and values must be strings. Defaults to `{}` |
| `pipeline.proxy` | `string` | No | HTTP/HTTPS proxy URL for the pipeline container. When set, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` are written to the container env-file. Overridden by the `--proxy` CLI option |
| `pipeline.hosts` | mapping | No | Host→IP mapping for `docker run --add-host`. Defaults to `{}`. Augmented by the repeatable `--add-host` CLI option (CLI wins on key conflict) |

Two adjacent settings the domain consumes live at the top level of the file, not inside the section: `image` — the container image both `goga build` and `goga pipeline` launch — and `dockerfile` — the project Dockerfile `goga pipeline --update` builds from when set (see [Project Configuration](../../configuration/project.md)).

The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md).
