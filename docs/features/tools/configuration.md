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

The convention is an agreement between tools, not a content standard: goga
never validates, interprets, or cleans these directories. It reads exactly
one standardized file — a `main` declaring a keyword-capable `config`
parameter receives `.goga/tools/<tool>/config.yml` loaded raw as-is
(`None` when absent) through the `config` injection of `goga tool` (see
[Optional injections](cli.md#optional-injections)); everything else in the
directory stays tool-owned. A tool that wants a different filename — or
several files — reads them itself from the project root at invocation
time; the CLI invocation, the optional AST injection, and the hook
contexts are unaffected.

The standard read is also a library procedure on the `goga.config` facade:

```python
from goga.config import load_tool_config

data = load_tool_config("hello-world", "config.yml")  # raw parsed YAML, or None when absent
```

`load_tool_config(tool, filename, root=None)` composes
`<root>/.goga/tools/<tool>/<filename>` with `filename` taken verbatim (a
non-flat name segment — empty, `.`/`..`, or containing a separator — is a
clean `ValueError`), returns the raw parsed content as-is, and propagates a
parse failure (`yaml.YAMLError`) or a read failure (`OSError`,
`UnicodeDecodeError`) raw; `root=None` anchors at the current directory.
The same composition the onboarding engine writes under — the write-side
counterpart of this read.

The general configuration model of the product is covered in [Configuration](../../configuration/index.md).
