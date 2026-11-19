# Rendering workflow-files with jinja2

## Domain

The two rendering surfaces of the goga contributor-profiles feature, both rendered with one fixed Jinja environment and exactly the active profile's content as the context:

- **Authored workflow-files** — whole-file rendering before YAML parsing. The template engine treats an entire workflow-file as a single Jinja template; after rendering, the resulting text is parsed and validated by the standard workflow grammar without any changes.
- **Committed contributions** — field-level rendering of the strings of a `pipeline.amend_workflow` contribution at the tool's commit inside the amendment walk (see the pattern below).

Target audience: agents implementing or modifying the workflow rendering path, the workflow grammar, or the pipeline amendment layer.

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

### Field-level render of a committed contribution

The strings of a tool contribution delivered through the `pipeline.amend_workflow` hook render at the tool's commit moment, before the authored-wins merge. The surface is type-driven: every string leaf and every string mapping key of the contributed workflow document, at any depth — including the extend-stage bodies and the never-merging global fields (`profile`, `build`, `agent`, `env`). Non-string scalars are not template surfaces. Each string renders individually with the same fixed environment and the same context as the whole-file render — exactly the active profile's content, empty without activation, and no ambient variables (tool, pipeline, workflow name):

```python
rendered_prompt = env.from_string(contributed_prompt).render(**profile)
```

A stage prompt contributed as `Model: {{ model }}` renders against the profile content exactly as an authored workflow-file prompt would.

A template error anywhere in a contribution — dead fields included — is a hard pre-run failure in the existing amendment-failure format (naming the tool and the action — and the hook when a hook failed; a render failure names no hook) carrying the template cause: the error class, the message, and a document path — the dot-path of the string within the contribution built from the source (pre-render) keys, list elements indexed, and `gates` disambiguated positionally (`gates.patience` vs `stages.<name>.gates[0].script`). A rendered-key collision inside one contribution map (two distinct source keys rendering to the same result key) is the same hard failure naming the tool, the map, the source keys, and the colliding result.

## Workflow authoring stance

- Templates may appear anywhere in a workflow-file — any string value (agent, env, prompt, title, …) may reference profile data.
- The process author defines the profile data model through what the templates read; the team commits a project profile with recommended values so the workflow runs out of the box.
- Rendering never bypasses validation: a rendered workflow passes the standard structural validation, and the existing structural errors apply unchanged.
- Pipeline-files (`.goga/pipelines/*.yml`), `.goga/config.yml`, and profile files themselves are never templated.

## Anti-patterns

- `StrictUndefined` or `ChainableUndefined` — they break the "missing key is falsy/empty" semantics the feature depends on
- `autoescape=True` — it corrupts YAML content (HTML-escapes it)
- Rendering an authored workflow-file after parsing, or rendering fragments of one — authored files render whole-file before parsing only; the one sanctioned rendering of an already-parsed document is the field-level render of a committed contribution at its amendment commit
- Building a second environment, dialect, or ambient context (tool, pipeline, workflow name) for contribution rendering — one environment, one context: the profile content
- Swallowing `TemplateSyntaxError` or reporting it without a location — always a strict failure with the file name and line (or the document path, for a contribution string)
- Tempting pipeline-files, `.goga/config.yml`, or profile files into the template path — out of the rendering contract
- Building a multi-profile or cross-profile template context — the context is exactly the single active profile
