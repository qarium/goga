# Contract — Hooks

The contract domain exposes **no hook actions** of its own for tool packages today.

The comparison is a read-only analysis over the project files and the parsed manifests. `goga contract` does deliver the config amendment checkpoint at its configuration load — the language resolution reads the effective configuration (see [Configuration — Hooks](../../configuration/hooks.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
