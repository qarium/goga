# Lint — Hooks

The lint domain exposes **no hook actions** for tool packages today.

The rule set is fixed by the goga AST; a project extends validation through its conventions (`.goga/usages/`) rather than through hooks. The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
