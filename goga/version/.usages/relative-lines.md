# Relative Version Lines — goga/version

## Overview

`resolve_relative_spec` builds the pip specifier that keeps an upgrade inside the version line of an already installed
package. Use it when the user asks to "upgrade without leaving my line" and cannot be expected to know the installed
version by heart.

Audience: command cells that upgrade an installed package under a relative constraint (patch line or minor line).

## Semantics

| Flag | Line | From installed `1.2.3` |
|---|---|---|
| `patch=True` | newest patch of the current minor | `~=1.2.0` |
| `minor=True` | newest release within the current major | `~=1.0` |

The base is truncated to its leading release segments, so development and pre-release installations still resolve:
`1.2.0rc1`, `1.2.0.post1`, `1.2.0+local`, `1.2.1.dev0` all reduce to the `1.2` line.

## Ready-to-use pattern

The caller owns the metadata boundary — read the installed version first, then hand it to the routine:

```python
from importlib.metadata import version

from goga.version import resolve_relative_spec

base = version("goga")                    # may raise PackageNotFoundError
spec = resolve_relative_spec(base, patch=True)
identifier = f"goga{spec}"                # e.g. "goga~=1.2.0"
```

## Error cases to surface at the CLI layer

| Input | Result |
|---|---|
| `patch=True, minor=True` | `ValueError` — exactly one line must be selected |
| neither flag | `ValueError` — call only when a line flag is active |
| base without a minor segment under `patch=True` (e.g. `"1"`) | `ValueError` — the patch line is undeterminable |
| base without leading numeric segments | `ValueError` — the line is undeterminable |

Catch `ValueError` and the metadata exception where they occur and convert both into user-facing CLI errors before any
side effects run. The routine itself never reads metadata, logs, or prints.

## Consumer constraints

- Pass the installed version string as `base_version` — not an image tag, not a config value.
- Do not append the returned specifier to anything other than the constrained package's identifier; sibling packages
  in the same pip invocation stay unconstrained.
