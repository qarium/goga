# Usages — Hooks

The usages domain exposes **no hook actions** of its own for tool packages today.

The sync is driven purely by the configuration declarations (see [Configuration](configuration.md)). Both `usages status` and `usages sync` deliver the config amendment checkpoint at their configuration load — the declared deps iterate the effective `usages` section (see [Configuration — Hooks](../../configuration/hooks.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
