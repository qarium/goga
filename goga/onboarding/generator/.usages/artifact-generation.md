# Artifact generation — goga/onboarding/generator

## Domain

Writing the onboarding session artifacts from the committed answer space
and the committed tool contributions: `.goga/config.yml`, the Dockerfile,
the base conventions file, and the tool config files. Target audience: the
session orchestrator.

## Public API

    from goga.onboarding import FileGenerator

- `FileGenerator().generate(answers, contributions) -> list[CreatedFile]` —
  every artifact in generation order with attribution (`CreatedFile.tool`
  is None for engine files, the tool identity for tool files). An existing
  `.goga/config.yml` skips the config and Dockerfile generation — never
  rewritten, whoever created it first wins.
- `generate_goga_config(answers)` — the project config from the answer
  snapshot: field order language, image, dockerfile, build, pipeline,
  codemanifest, tools, usages; empty build/pipeline blocks omitted;
  annotations rendered as a literal block. An empty required `language` is
  a clean session error naming the field; the conventions download failure
  is a clean error with the URL and the cause.
- `generate_tool_configs(contributions)` — every buffered tool file
  serialized as YAML into `.goga/tools/<tool>/<file>`; the same file name
  written again replaces the file.

## Ready-to-use pattern

### Generate after the survey and the committed contributions

```python
from goga.onboarding import FileGenerator

files = FileGenerator().generate(answers, contributions)
for entry in files:
    if entry.tool is None:
        print(f"created {entry.path}")
    else:
        print(f"created {entry.path} (tool: {entry.tool})")
```

## Notes for the consumer

- Call `generate` once, after the tool contributions are committed — the
  snapshot is read at that moment.
- The return value is the single source of the final file report — render
  it with the tool attribution.
- The written config must pass the project config loader — the mapping
  above is normative.
