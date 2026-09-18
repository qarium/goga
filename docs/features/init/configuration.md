# Init — Configuration

The init domain reads **no section of `.goga/config.yml`** — it **writes** the file: the questionnaire's answers become the initial `language`, `image`, `build`, `pipeline`, `codemanifest`, `tools`, and `usages` values (and, optionally, a project Dockerfile plus the invited tools' configs under `.goga/tools/<tool>/`).

What each written field means afterwards is covered by the domains that read it — see [Project Configuration](../../configuration/project.md) and the per-domain [Configuration](../index.md#the-page-model) pages.
