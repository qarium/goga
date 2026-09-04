# Install — Configuration

The install domain reads one optional section of `.goga/config.yml` — `tools`, the version declarations consumed by [`goga install`](cli.md) in bulk mode (a bare `goga install` with no name and no `--local`).

```yaml
tools:
  viewer: latest
  mkdocs: 1.0.x
```

| Field | Type | Required | Description |
|---|---|---|---|
| `tools` | mapping | No | goga-tool version declarations. Keys are tool names (without the `goga-tool-` prefix); values are version-form strings. Values are stored verbatim — the four-form grammar (`1.0.x`, `1.x`, `1.0.1`, `latest`) is validated by `goga install`, not the loader. Defaults to `None` (absent); an empty mapping is `{}`. YAML-null values (`viewer:`) are rejected |

Single and local modes ignore the section entirely — the version comes from `--version` or the local path.

The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md).
