# Topics — Configuration

The topics domain reads one optional section of `.goga/config.yml` — `topics`, consumed by [`goga topics create`](cli.md), [`goga topics clear`](cli.md), [`goga topics update`](cli.md), [`goga topics propagate`](cli.md), and [`goga topics board`](cli.md) (the base of the divergence marker). The section is read lazily: only when a value no CLI flag provided has to come from it.

```yaml
topics:
  base_ref: origin/main            # default base of the exchange and the clear scope
  create:
    commit: "feat: {slug} todo"    # commit template of the published todo commit
  update:
    strategy: rebase               # merge | rebase | ff-else-merge | ff-else-rebase
    commit: "Update {slug} from {base}"
  propagate:
    strategy: merge                # merge | ff | squash
    commit: "Deliver {slug} into {base}"
```

| Field | Type | Required | Description |
|---|---|---|---|
| `topics.base_ref` | `string` | No | Base revision of the topic exchange (`update`, `propagate`), of a created topic branch, of a clear scope, and of the board's divergence marker — any revision string (branch, remote-tracking ref, tag, hash), stored verbatim with no resolvability check. Absent/YAML-null/empty/whitespace resolves to `None`; a non-string raises `ValueError`. Overridden by the `--base-ref` CLI option; the creation resolves as `--base-ref` > `topics.base_ref` > the current HEAD under `--from-current` (a creation with none of the three exits 1), the clear/update/propagate as `--base-ref` > `topics.base_ref` with no current-HEAD rung (a command with neither exits 1) |
| `topics.create.commit` | `string` | No | Commit message template of the published todo commit; the `{slug}` placeholder is replaced with the topic slug, and a template without it is used verbatim. Same typing rules as `base_ref`. Overridden by the `--commit`/`-c` CLI option (publication-only); the built-in default is `Create topic '{slug}'` |
| `topics.update.strategy` | `string` | No | The update strategy — one of `merge`, `rebase`, `ff-else-merge`, `ff-else-rebase`; any other value is a clean error naming the key (exit 1). Absent/YAML-null applies the domain default `merge` |
| `topics.update.commit` | `string` | No | Commit message template of the update's merge commit; `{slug}` and `{base}` are replaced. The built-in default is `Update topic '{slug}' from '{base}'` |
| `topics.propagate.strategy` | `string` | No | The propagation strategy — one of `merge`, `ff`, `squash`; any other value is a clean error naming the key (exit 1). Absent/YAML-null applies the domain default `merge` |
| `topics.propagate.commit` | `string` | No | Commit message template of the propagation's delivery commit; `{slug}` and `{base}` are replaced. The built-in default is `Propagate topic '{slug}' into '{base}'` |

When `topics` is absent, the configuration is "everything unset". Unknown keys inside the mapping are ignored — the same stance as `lint` and `codemanifest`. A non-mapping `topics` value, a non-mapping `topics.create`/`topics.update`/`topics.propagate` sub-section, or a non-string field raises `ValueError` at load time (see [Configuration — validation errors](../../configuration/project.md#validation-errors)).

The retired `topics.publish_commit` key — replaced by `topics.create.commit` — is silently ignored: a configuration still carrying it gets the built-in default instead. Move the template to `topics.create.commit`.

The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md).
