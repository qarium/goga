# Environment references in configuration YAML (!ENV)

Domain: authoring environment-driven values in goga configuration files
and consuming the env-aware loader. Audience: authors of
.goga/config.yml and tool configuration files, and implementers of
configuration loaders that parse through `parse_env_yaml`.

## What the tag does

A scalar tagged `!ENV NAME` resolves, at load time, to the value of the
environment variable `NAME` — always as a plain string.

```yaml
# .goga/config.yml
pipeline:
  agent: !ENV PIPELINE_AGENT
```

- `PIPELINE_AGENT=claude` → `agent` parses to the string `"claude"`.
- `PIPELINE_AGENT` unset → `agent` parses to the empty string `""`;
  each field's own empty-value semantics then applies (the `agent`
  fields treat `""` as absence).
- No type coercion ever happens: `PORT: !ENV PORT` is the string
  value, and a field expecting an int rejects it per its own validation.

## Calling the loader

```python
from ..yaml import parse_env_yaml   # from a sibling sub-cell of goga/config

text = Path(".goga/config.yml").read_text()
raw = parse_env_yaml(text)   # plain Python value; tags already resolved
```

Relative import from a sibling sub-cell of `goga/config` goes one level
up (`..yaml`); a module directly inside `goga/config` uses
`from .yaml import …`.

The result carries resolved strings only — no tag objects survive the
load. Downstream code never sees `!ENV`.

## Where the tag applies

- Project configuration (`.goga/config.yml`) — yes.
- Tool configuration files (`.goga/tools/<tool>/<file>`) — yes.
- Home configuration (`~/.goga/config.yml`) — NO: the home loader stays
  on plain `yaml.safe_load` by product decision.

## Malformed use

An empty argument (`!ENV` with nothing) or a non-scalar position raises
the yaml library's own constructor error naming the file position —
fix the YAML, not the loader.

## Testing note

Resolution is environment-dependent: tests control the environment
(monkeypatch the variable) and must not rely on ambient values.
