# Drift — Configuration

The drift domain reads **no section of its own** in `.goga/config.yml` — its report is fully scoped by the CLI arguments (the positional cells, `--max-depth`, `--depends-on`). The two view domains it composes consume the existing fields:

- the root **`language`** field — read by the code-derived view; one of `python`, `golang`, `javascript`, `kotlin`, `swift`; any other value stops the command with a clean error before a single file is parsed (see [Codegraph — Configuration](../codegraph/configuration.md) and [Project Configuration](../../configuration/project.md));
- the **`lint.ignore`** exclusion list — the same entries that prune the lint walk also prune the code-derived view's source discovery (see [Lint — Configuration](../lint/configuration.md)).

```yaml
language: python

lint:
  ignore:
    - generated/
```

The declared view reads no configuration section — the cells it walks come from the project structure itself (see [Schema — Configuration](../schema/configuration.md)). A source file excluded from the code-derived view is invisible to the comparison: its cells and type names surface as `schema_only` discrepancies.
