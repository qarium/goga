# Contract — Configuration

The contract domain reads **no dedicated section of `.goga/config.yml`** — it consumes the global top-level `language` field (the default of `--lang`; see [Project Configuration](../../configuration/project.md)).

The global `codemanifest:` section (named practices and agent annotations) belongs to no single domain and stays in the [Configuration](../../configuration/project.md#codemanifest) section.
