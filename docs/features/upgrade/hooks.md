# Upgrade — Hooks

The upgrade domain exposes **no hook actions** for tool packages today.

Its reach into the tool ecosystem is direct pip: `--tools` upgrades every installed `goga_tool_*` package and the run re-syncs the connected agents (see [Overview](index.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
