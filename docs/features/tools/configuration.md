# Tools — Configuration

The tools domain reads **no dedicated section of `.goga/config.yml`**.

The `tools:` mapping of the project configuration — the version declarations consumed by `goga install` in bulk mode — belongs to the [Install](../install/configuration.md) domain (the command that reads it). A tool package's own behavior is configured by nothing in the project: it receives its inputs through the CLI invocation, the optional AST injection, and the hook contexts.

The general configuration model of the product is covered in [Configuration](../../configuration/index.md).
