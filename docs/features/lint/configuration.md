# Lint — Configuration

The lint domain reads one optional section of `.goga/config.yml` — `lint`, consumed by [`goga lint`](cli.md).

```yaml
lint:
  ignore:
    - .venv/
    - build/dist
```

| Field | Type | Required | Description |
|---|---|---|---|
| `lint.ignore` | list of strings | No | Directory relative paths to skip during lint traversal, stored verbatim. A directory matches when its exact normalized relative path equals an entry; glob patterns are not interpreted and a trailing separator is insignificant. Defaults to `[]` when `lint` is present but `ignore` is absent |

When the section is absent (or the config cannot be loaded), lint behavior is unchanged — every directory is linted. Structural type errors (a non-mapping `lint`, a non-list `lint.ignore`, or a non-string element) raise `ValueError` at load time.

The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md).
