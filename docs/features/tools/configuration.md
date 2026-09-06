# Tools — Configuration

The tools domain reads **no dedicated section of `.goga/config.yml`**.

The `tools:` mapping of the project configuration — the version declarations consumed by `goga install` in bulk mode — belongs to the [Install](../install/configuration.md) domain (the command that reads it).

## Per-tool project files

A tool that carries its own configuration into a project follows one
convention: **a tool's project files live under
`.goga/tools/<tool-name>/`** — one directory per tool, checked into the
project. The name is the canonical hyphenated tool identity
(`goga_tool_hello_world` → `hello-world`), the same identity used for
namespaced pipelines and skills.

The convention is an agreement between tools, not a goga mechanism: goga
neither reads nor validates nor cleans these directories. A tool's
`main(argv)` resolves its configuration from the project root at
invocation time; the CLI invocation, the optional AST injection, and the
hook contexts are unaffected.

The general configuration model of the product is covered in [Configuration](../../configuration/index.md).
