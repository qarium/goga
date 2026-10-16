# Rendering workflow-files with jinja2

## Domain

Whole-file rendering of workflow-files before YAML parsing, for the goga contributor-profiles feature. The template engine treats an entire workflow-file as a single Jinja template; after rendering, the resulting text is parsed and validated by the standard workflow grammar without any changes. Target audience: agents implementing or modifying the workflow rendering path and the workflow grammar.

## Library

jinja2 >= 3.1 — declared in `pyproject.toml` with a minimum version per project convention.

## Environment configuration

The rendering environment is fixed by an accepted ADR decision; do not deviate:

- `trim_blocks=True` — a block tag followed by a newline does not leave a blank line in the output
- `lstrip_blocks=True` — block tags are stripped of preceding whitespace up to the line start
- `keep_trailing_newline=True` — the rendered file keeps its final newline
- the standard `Undefined` (do NOT substitute `StrictUndefined` or `ChainableUndefined`): a missing key is falsy/empty, and nested access on a missing key fails at render time — standard Jinja semantics
- `autoescape=False` — the engine renders YAML text, not HTML

```python
from jinja2 import Environment

env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    autoescape=False,
)
rendered = env.from_string(workflow_text).render(**profile)
```

The template context is the entire content of the active profile: every top-level key of the profile mapping is a template variable. With no activation, rendering runs with an empty context.

## Usage patterns

### Whole-file render before parsing

Render the complete file text, then hand the rendered text to the ordinary YAML parser and the standard structural validation. Rendering is a step before parsing — never after, never fragmentary:

```python
rendered = env.from_string(text).render(**profile)
document = parse_workflow(rendered)  # unchanged grammar and error rules
```

### Missing keys are not errors

Standard Jinja semantics apply to absent profile keys — guards and defaults work as usual:

```yaml
{% if worker %}
worker:
  agent: {{ worker.agent }}
{% endif %}
review:
  prompt: "Review using {{ review.model | default('sonnet') }}."
```

A missing key is falsy in `{% if %}` and empty when interpolated; nested access on a missing key raises at render time. This enables profile-driven stage skipping and optional personalization.

### Iterating a mapping inside an env block

Per-stage environment maps can be produced from profile data with the standard mapping iteration:

```yaml
stages:
  worker:
    agent: {{ worker.agent }}
    env:
      {% for k, v in worker.env.items() %}
      {{ k }}: {{ v }}
      {% endfor %}
```

Thanks to `trim_blocks` + `lstrip_blocks`, block tags vanish cleanly from the output and the rendered text stays valid YAML.

### Strict failure on syntax errors

A Jinja syntax error in a workflow-file is a strict pre-run failure with an actionable location. Catch `TemplateSyntaxError` and surface the exception's `lineno` and message together with the workflow file name — never swallow it:

```python
from jinja2 import TemplateSyntaxError

try:
    rendered = env.from_string(text).render(**profile)
except TemplateSyntaxError as exc:
    fail_strict(f"{workflow_name}: template syntax error at line {exc.lineno}: {exc.message}")
```

## Workflow authoring stance

- Templates may appear anywhere in a workflow-file — any string value (agent, env, prompt, title, …) may reference profile data.
- The process author defines the profile data model through what the templates read; the team commits a project profile with recommended values so the workflow runs out of the box.
- Rendering never bypasses validation: a rendered workflow passes the standard structural validation, and the existing structural errors apply unchanged.
- Pipeline-files (`.goga/pipelines/*.yml`), `.goga/config.yml`, and profile files themselves are never templated.

## Anti-patterns

- `StrictUndefined` or `ChainableUndefined` — they break the "missing key is falsy/empty" semantics the feature depends on
- `autoescape=True` — it corrupts YAML content (HTML-escapes it)
- Rendering after parsing, or rendering fragments of an already-parsed document — only whole-file rendering before parsing
- Swallowing `TemplateSyntaxError` or reporting it without a location — always a strict failure with the file name and line
- Tempting pipeline-files, `.goga/config.yml`, or profile files into the template path — out of the rendering contract
- Building a multi-profile or cross-profile template context — the context is exactly the single active profile
