# Onboarding contexts — goga/onboarding

## Domain

What a tool package receives inside a `goga init` session and the member
contract of the two onboarding actions. Target audience: authors of
`goga_tool_*` packages that need project configuration.

## Subscribing

Register hooks for the two actions in the package facade — the tool
identity is assigned by goga from the package name:

```python
def register_hooks(hooks):
    hooks.subscribe("onboarding", "declare_session", "declare", declare_session)
    hooks.subscribe("onboarding", "amend_config", "amend", amend_config)
```

A hook declares `context` (and optionally `self`) by name; values land by
name. Subscribing to one action only is fine — the moments are
independent.

## Moment one — declare_session(context)

Declare the tool's questions and skips as data; the engine asks them
itself after the core questions, under a heading with the tool's name.

```python
from goga.onboarding import Question, QuestionGroup

def declare_session(context):
    if not context.invited:
        return                      # contract rule: return immediately
    context.declare(Question(id="token", kind="input", prompt="Service token"))
    context.declare(QuestionGroup(id="reporting", prompt="Reporting",
                                  children=[Question(id="enabled", kind="confirm",
                                                     prompt="Enable reporting?", default=False)]))
    context.skip("docker_image.base_image")   # unprefixed — core tree or own block
```

- `context.invited` — False means the session did not invite this tool:
  return immediately, call nothing.
- `context.declare(item)` — a `Question` or a one-level `QuestionGroup`;
  local names, the engine qualifies them with the tool identity. A
  repeated local name is rejected with a warning; the rest of the
  declaration stands.
- `context.skip(path)` — unprefixed for the core tree or the tool's own
  block, `<tool>.`-prefixed for another tool's block. A skip removes the
  whole subtree; unknown paths are a no-op with a warning.

## Moment two — amend_config(context)

Read the isolated answers and buffer the contribution.

```python
def amend_config(context):
    if not context.invited:
        return
    if context.answers.get("reporting", {}).get("enabled"):
        context.answer("pipeline.env", {"REPORT_URL": "https://example.com"})
        context.answer("tools", {"my-tool": "latest"})
        context.write_config("service.yml", {"token_source": "env", "interval": 60})
```

- `context.answers` — the core answers plus this tool's own answers under
  local names; other tools' answers are never visible.
- `context.answer(id, value)` — buffer an amendment: mappings merge
  recursively, scalars and lists replace; substituting a user's answer is
  silent; registrations in `tools`/`usages` are ordinary amendments.
- `context.write_config(file, data)` — buffer a config file; the engine
  serializes YAML and writes `.goga/tools/<tool>/<file>`; the same file
  written again is replaced.

## Failure behavior

- An exception in a hook drops the tool's whole contribution with a
  warning naming the tool and the reason; `goga init` continues and exits
  0.
- A broken package import is the single fatal case — a clean session
  error naming the package.
