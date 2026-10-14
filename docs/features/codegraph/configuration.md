# Codegraph — Configuration

The codegraph domain reads **no section of its own** in `.goga/config.yml` — it consumes two existing fields:

- the root **`language`** field — one of `python`, `golang`, `javascript`, `kotlin`, `swift`; any other value stops the command with a clean error before a single file is parsed (see [Project Configuration](../../configuration/project.md));
- the **`lint.ignore`** exclusion list — the same entries that prune the lint walk also prune the codegraph source discovery (see [Lint — Configuration](../lint/configuration.md)).

```yaml
language: python

lint:
  ignore:
    - generated/
```

Without a `lint` section every discovered source file of the language is analyzed; the idiomatic per-language test files (`test_*.py`, `*_test.go`, `*.test.js`, `*Test.kt`, `*Tests.swift`) are always skipped.
