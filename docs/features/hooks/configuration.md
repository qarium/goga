# Hooks — Configuration

The hooks domain reads **no section of `.goga/config.yml`** — it is configured by nothing.

The registry assembles from the `goga_tool_*` packages installed in the running interpreter (see [Install](../install/index.md)); its shape is fully derived from their `register_hooks` callbacks. The general configuration model of the product is covered in [Configuration](../../configuration/index.md).
