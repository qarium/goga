# Version Forms — goga/version

## Overview

`resolve_version` is the single entry point for turning a version form string into a pip specifier. Use it whenever a
consumer accepts a user- or config-supplied version expression: CLI version options and declarative tool mappings both
resolve through this routine.

Audience: command cells that compose pip package identifiers from a name plus an optional version constraint.

## The four grammar forms

| Form | Example input | Resolved specifier | Meaning |
|---|---|---|---|
| `latest` / None | `latest` | None | no specifier — newest version under the upgrade request |
| Major x-range `N.x` | `1.x` | `~=1.0` | newest release within major 1 |
| Minor x-range `N.M.x` | `1.2.x` | `~=1.2.0` | newest patch within minor 1.2 |
| Concrete `N(.M)?(.K)?` | `1.2`, `1.2.3` | `==1.2`, `==1.2.3` | exact pin |

Every other shape raises `ValueError`: operator-prefixed forms (`==1.2`, `>=1`, `~=1.2.0`, …) and anything richer than
the grammar (pre-release, post-release, local segments such as `1.0.0a1`, `1.0.0.post1`, `1.0.0+local`). Catch
`ValueError` at the CLI layer and surface it as a user-facing error — the routine is a pure transformer and never
logs or prints.

## Ready-to-use pattern

```python
from goga.version import resolve_version

def compose_identifier(name: str, form: str | None) -> str:
    """Compose a pip package identifier from a name and a version form."""
    spec = resolve_version(form)
    return f"{name}{spec or ''}"
```

```python
compose_identifier("goga-tool-hello", "1.2.x")   # "goga-tool-hello~=1.2.0"
compose_identifier("goga-tool-hello", "latest")  # "goga-tool-hello"
compose_identifier("goga-tool-hello", None)      # "goga-tool-hello"
compose_identifier("goga-tool-hello", "==1.2")   # raises ValueError
```

## Consumer constraints

- Append the returned specifier directly to the package identifier; the routine already emits the operator.
- `None` and `"latest"` produce the same result — use `None` for an absent CLI value and `"latest"` as the canonical
  marker inside declarative configuration.
- Do not pre-validate or normalize the form before calling — the routine owns the grammar and is the single point of
  rejection.
