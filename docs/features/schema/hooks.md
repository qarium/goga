# Schema — Hooks

The schema domain exposes **no hook actions** for tool packages today.

A tool that needs the project structure receives it through the optional AST injection of its `main` entry point instead (see [Tools — CLI](../tools/cli.md#optional-injections)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
