# Connect — Hooks

The connect domain exposes **no hook actions** for tool packages today.

A tool package reaches the agent layer through its artifacts, not hooks: its skills are installed into `~/.goga/skills/` and its pipeline-files into `~/.goga/pipelines/` by the connect run itself (see [Overview](index.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
