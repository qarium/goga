# Custom YAML scalar constructors — environment references via `!ENV`

## Library

**PyYAML (`yaml`)** — YAML parsing for the project's configuration loaders.

**IMPORTANT** — the library is already in the project dependencies.

## Mechanism

A custom YAML tag (for example the scalar tag `!ENV`) is resolved **at load
time** through the library's standard constructor mechanism — no text
preprocessing, no post-parse walk. The constructor is a function registered on
a **loader class**; every node carrying the tag is passed to it while the
document is being constructed.

### Registering a scalar-tag constructor

```python
import os
import yaml


def _construct_env(loader: yaml.Loader, node: yaml.Node) -> str:
    return os.environ.get(node.value, "")


class EnvLoader(yaml.SafeLoader):
    """SafeLoader plus the `!ENV` scalar tag."""


EnvLoader.add_constructor("!ENV", _construct_env)

data = yaml.load(text, Loader=EnvLoader)
```

- Subclass the base loader (`yaml.SafeLoader`) and register the tag on the
  subclass — the tag then applies only where this loader is used, and other
  `yaml.safe_load` call sites stay unaffected.
- `add_constructor` is a classmethod of the loader; it mutates the class's
  constructor registry, so registering on the global `yaml.SafeLoader` would
  leak the tag into every `safe_load` of the process.

### Constructor contract

- Signature: `(loader, node) -> value`. For a scalar tag, `node.value` is the
  scalar's text — the argument of the reference (`!ENV NAME` → `node.value`
  is `"NAME"`).
- The constructor runs during document construction, so the parsed result
  carries **resolved** values — downstream code sees plain strings, never the
  tag.
- Return a string for `!ENV` — no type coercion. An unset variable resolves to
  the empty string `""`; each field's own validation then applies its
  empty-value semantics.
- Resolution is environment-dependent: the same file parses to different
  values under different environments. That is the feature (one committed
  file, many environments), and tests must control the environment explicitly.

### Error handling — the library's own machinery

```python
from yaml.constructor import ConstructorError


def _construct_env(loader: yaml.Loader, node: yaml.Node) -> str:
    if not node.value:
        raise ConstructorError(
            None,
            None,
            "expected a variable name in !ENV",
            node.start_mark,
        )

    return os.environ.get(node.value, "")
```

- Raise `yaml.constructor.ConstructorError` for malformed use (an empty
  argument, a non-scalar node) — it is a `yaml.YAMLError` subclass, so
  existing `except yaml.YAMLError` handlers keep working unchanged.
- `ConstructorError` carries a **mark** (the node's `start_mark`): pass it as
  the last argument so the rendered error names the file position. The library
  formats it into the standard `while constructing ... in "<file>", line N`
  message.
- Do not invent a custom exception type for tag failures — the yaml error
  channel is the established one, and it already carries position info.

## Constraints

- Register custom tags on a **loader subclass**, never on the global
  `yaml.SafeLoader` / `yaml.Loader` classes.
- Resolve at load time only — never rewrite the file text or walk the parsed
  tree afterwards; a node the loader meets is a node the constructor resolves.
- The tag participates in normal YAML composition: placing it in a non-scalar
  position (a mapping key, a list item where a scalar is impossible) surfaces
  through the same constructor/composer errors — do not special-case it.
- Keep the resolution pure: read the environment, return the value; no
  logging of resolved values (they may carry secrets).
