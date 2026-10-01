# Lint — Hooks

The lint domain exposes **no hook actions** of its own for tool packages today.

The rule set is fixed by the goga AST; a project extends validation through its conventions (`.goga/usages/`) rather than through hooks. `goga lint` does deliver the config amendment checkpoint at its configuration load — `lint.ignore` derives from the effective configuration (see [Configuration — Hooks](../../configuration/hooks.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
