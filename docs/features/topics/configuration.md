# Topics — Configuration

The topics domain reads one optional section of `.goga/config.yml` — `topics`, consumed by [`goga topics create`](cli.md). The section is read lazily: only when a value no CLI flag provided has to come from it.

```yaml
topics:
  base_ref: origin/main       # default base of created topic branches
  publish_commit: "feat: {slug} todo"  # commit template of the published todo commit
```

| Field | Type | Required | Description |
|---|---|---|---|
| `topics.base_ref` | `string` | No | Base revision of a created topic branch — any revision string (branch, remote-tracking ref, tag, hash), stored verbatim with no resolvability check. Absent/YAML-null/empty/whitespace resolves to `None`; a non-string raises `ValueError`. Overridden by the `--base-ref` CLI option; the base resolves as `--base-ref` > `topics.base_ref` > the current HEAD under `--from-current` — a creation with none of the three exits 1 |
| `topics.publish_commit` | `string` | No | Commit message template of the published todo commit; the optional `{slug}` placeholder is replaced with the topic slug, and a template without it is used verbatim. Same normalization and typing rules as `base_ref`. Overridden by the `--commit`/`-c` CLI option (publication-only); the built-in default is `goga: create topic {slug}` |

When `topics` is absent, the configuration is "everything unset". Unknown keys inside the mapping are ignored — the same stance as `lint` and `codemanifest`. A non-mapping `topics` value, or a non-string field, raises `ValueError` at load time (see [Configuration — validation errors](../../configuration/project.md#validation-errors)).

The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md).
