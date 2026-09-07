# Pipelines — Hooks

The pipelines domain exposes **no hook actions** for tool packages today.

A tool package reaches the pipeline surface not through hooks but through its own artifacts: its skills merge into pipeline stages via the workflow `skills:` mechanism, and its pipeline-files install namespaced as `<tool>:<name>.yml` and run as `goga pipeline <tool>:<name>` (see [Tools](../tools/index.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
